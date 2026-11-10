"""Offline contracts for account-owned and legacy saved-tour storage."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date, time
from pathlib import Path
from uuid import uuid4

from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.saved_tours import SavedTourRepository


def _plan(destination: str) -> SightseeingPlan:
    source = SourceReference(
        source_id=f"source-{destination}",
        title=f"{destination} fixture source",
        url="https://example.test/source",
        retrieval_query=destination,
    )
    return SightseeingPlan(
        plan_id=f"plan-{destination.casefold()}",
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id=f"entry-{destination.casefold()}",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id=f"place-{destination.casefold()}",
                    name=destination,
                    description="Offline account-storage fixture.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
        summary=f"Offline {destination} plan.",
    )


def test_account_rows_are_isolated_from_other_accounts_and_legacy_access(
    tmp_path,
) -> None:
    repository = SavedTourRepository(tmp_path / "saved-tours.sqlite")
    first_user = str(uuid4())
    second_user = str(uuid4())
    legacy_token = "original-browser-owner"

    account_tour = repository.save_for_user(first_user, _plan("Hue"))
    legacy_tour = repository.save(legacy_token, _plan("Da Nang"))

    assert [item.id for item in repository.list_for_user(first_user).items] == [
        account_tour.id
    ]
    assert repository.get_for_user(second_user, account_tour.id) is None
    assert repository.delete_for_user(second_user, account_tour.id) is False
    assert repository.get(legacy_token, account_tour.id) is None

    claimed = repository.claim_for_user(first_user, legacy_token)
    assert claimed.claimed_count == 1
    assert claimed.already_claimed_count == 0
    assert claimed.conflicts == []
    assert repository.get(legacy_token, legacy_tour.id) is None
    assert repository.get_for_user(first_user, legacy_tour.id) is not None
    assert repository.get_for_user(second_user, legacy_tour.id) is None


def test_legacy_claim_is_idempotent_and_preserves_conflicting_snapshot(
    tmp_path,
) -> None:
    repository = SavedTourRepository(tmp_path / "saved-tours.sqlite")
    user_id = str(uuid4())
    legacy_token = "browser-cookie-proves-legacy-owner"
    duplicate = _plan("Hue")
    distinct = _plan("Hoi An")

    account_tour = repository.save_for_user(user_id, duplicate)
    legacy_conflict = repository.save(legacy_token, duplicate)
    legacy_claimable = repository.save(legacy_token, distinct)

    first = repository.claim_for_user(user_id, legacy_token)
    assert first.claimed_count == 1
    assert first.already_claimed_count == 0
    assert [
        (item.legacy_tour_id, item.account_tour_id) for item in first.conflicts
    ] == [(legacy_conflict.id, account_tour.id)]
    assert repository.get_for_user(user_id, legacy_claimable.id) is not None
    assert repository.get_for_user(user_id, legacy_conflict.id) is None
    assert repository.get(legacy_token, legacy_conflict.id) is not None

    repeated = repository.claim_for_user(user_id, legacy_token)
    assert repeated.claimed_count == 0
    assert repeated.already_claimed_count == 1
    assert [
        (item.legacy_tour_id, item.account_tour_id) for item in repeated.conflicts
    ] == [(legacy_conflict.id, account_tour.id)]


def test_explicit_sqlite_migration_initializes_auth_store(
    tmp_path, monkeypatch
) -> None:
    archive = tmp_path / "archive.sqlite"
    auth_database = tmp_path / "auth.sqlite"
    SavedTourRepository(archive)
    script = (
        Path(__file__).parents[1]
        / "scripts"
        / "migrate_saved_tours_account_ownership.py"
    )
    specification = importlib.util.spec_from_file_location(
        "account_migration_cli", script
    )
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_saved_tours_account_ownership.py",
            "--sqlite",
            str(archive),
            "--auth-db",
            str(auth_database),
        ],
    )

    assert module.main() == 0

    with sqlite3.connect(auth_database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"app_users", "auth_identities", "auth_sessions"} <= tables
