"""Process-local request quota for model-consuming planning turns.

The limiter deliberately keeps only timestamps and opaque principal keys.  It
resets when the process restarts and is not shared by multiple application
replicas; a distributed deployment needs a shared rate-limit store at ingress
or in a separate operational service.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic

DEFAULT_TURN_LIMIT_PER_HOUR = 20
TURN_WINDOW_SECONDS = 60 * 60
MAX_TRACKED_PRINCIPALS = 4096


class TurnRateLimitConfigurationError(ValueError):
    """Raised when a turn-rate environment setting is invalid."""


@dataclass(frozen=True)
class TurnQuotaReservation:
    """An accepted slot that can be returned if work was not scheduled."""

    identifier: int


@dataclass(frozen=True)
class TurnRateLimitExceeded:
    """The scope and wait period for a rejected turn."""

    scope: str
    retry_after_seconds: int


class TurnRateLimiter:
    """Thread-safe sliding-window limits for principals and the whole process."""

    def __init__(
        self,
        *,
        per_principal_limit: int = DEFAULT_TURN_LIMIT_PER_HOUR,
        global_limit: int | None = None,
        max_principals: int = MAX_TRACKED_PRINCIPALS,
        window_seconds: float = TURN_WINDOW_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if per_principal_limit < 1:
            raise ValueError("per_principal_limit must be positive")
        if global_limit is not None and global_limit < 1:
            raise ValueError("global_limit must be positive when configured")
        if max_principals < 1:
            raise ValueError("max_principals must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._per_principal_limit = per_principal_limit
        self._global_limit = global_limit
        self._max_principals = max_principals
        self._window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._next_identifier = 0
        self._principal_entries: dict[str, deque[tuple[float, int]]] = {}
        self._global_entries: deque[tuple[float, int]] = deque()

    @classmethod
    def from_environment(cls) -> TurnRateLimiter:
        """Read explicit process limits without exposing them to browser input."""

        def read_positive(name: str, *, default: int | None) -> int | None:
            raw = os.getenv(name)
            if raw is None or not raw.strip():
                return default
            try:
                value = int(raw)
            except ValueError as error:
                raise TurnRateLimitConfigurationError(
                    f"{name} must be a positive integer"
                ) from error
            if value < 1:
                raise TurnRateLimitConfigurationError(
                    f"{name} must be a positive integer"
                )
            return value

        per_principal = read_positive(
            "GTP_TURN_LIMIT_PER_HOUR", default=DEFAULT_TURN_LIMIT_PER_HOUR
        )
        global_limit = read_positive("GTP_TURN_GLOBAL_LIMIT_PER_HOUR", default=None)
        assert per_principal is not None
        return cls(per_principal_limit=per_principal, global_limit=global_limit)

    def reserve(self, principal: str) -> TurnQuotaReservation | TurnRateLimitExceeded:
        """Reserve one accepted turn, checking global capacity before principal use."""

        if not principal:
            raise ValueError("principal must not be blank")
        with self._lock:
            now = self._clock()
            self._prune(self._global_entries, now)
            self._prune_principals(now)
            if (
                self._global_limit is not None
                and len(self._global_entries) >= self._global_limit
            ):
                return TurnRateLimitExceeded(
                    scope="global",
                    retry_after_seconds=self._retry_after(self._global_entries, now),
                )
            entries = self._principal_entries.get(principal)
            if entries is None:
                if len(self._principal_entries) >= self._max_principals:
                    return TurnRateLimitExceeded(
                        scope="principal_capacity",
                        retry_after_seconds=self._principal_capacity_retry_after(now),
                    )
                entries = deque()
                self._principal_entries[principal] = entries
            if len(entries) >= self._per_principal_limit:
                return TurnRateLimitExceeded(
                    scope="principal",
                    retry_after_seconds=self._retry_after(entries, now),
                )
            self._next_identifier += 1
            reservation = TurnQuotaReservation(self._next_identifier)
            entry = (now, reservation.identifier)
            entries.append(entry)
            self._global_entries.append(entry)
            return reservation

    def refund(self, reservation: TurnQuotaReservation) -> None:
        """Return a reservation when scheduling failed before provider work began."""

        with self._lock:
            self._global_entries = deque(
                entry
                for entry in self._global_entries
                if entry[1] != reservation.identifier
            )
            for principal, entries in tuple(self._principal_entries.items()):
                kept = deque(
                    entry for entry in entries if entry[1] != reservation.identifier
                )
                if kept:
                    self._principal_entries[principal] = kept
                else:
                    self._principal_entries.pop(principal, None)

    def _prune(self, entries: deque[tuple[float, int]], now: float) -> None:
        cutoff = now - self._window_seconds
        while entries and entries[0][0] <= cutoff:
            entries.popleft()

    def _prune_principals(self, now: float) -> None:
        for principal, entries in tuple(self._principal_entries.items()):
            self._prune(entries, now)
            if not entries:
                self._principal_entries.pop(principal, None)

    def _principal_capacity_retry_after(self, now: float) -> int:
        oldest = min(entries[0][0] for entries in self._principal_entries.values())
        remaining = oldest + self._window_seconds - now
        return max(1, int(remaining) + (0 if remaining.is_integer() else 1))

    def _retry_after(self, entries: deque[tuple[float, int]], now: float) -> int:
        if not entries:
            return 1
        remaining = entries[0][0] + self._window_seconds - now
        return max(1, int(remaining) + (0 if remaining.is_integer() else 1))
