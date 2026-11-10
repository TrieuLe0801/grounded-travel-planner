"""Local SQLite file permission helpers."""

from __future__ import annotations

import os
import stat
from pathlib import Path

_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def prepare_private_sqlite_database(database_path: Path) -> None:
    """Restrict a SQLite database and existing sidecars before opening it."""

    if os.name != "posix":
        return
    database_path = Path(database_path)
    _create_private_parent(database_path.parent)
    _restrict_file(database_path, create=True)
    for suffix in _SIDECAR_SUFFIXES:
        _restrict_file(database_path.with_name(database_path.name + suffix))


def _create_private_parent(parent: Path) -> None:
    """Create missing storage directories privately without changing existing ones."""

    missing: list[Path] = []
    current = parent
    while not current.exists():
        missing.append(current)
        ancestor = current.parent
        if ancestor == current:
            break
        current = ancestor
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            continue
        os.chmod(directory, 0o700)


def _restrict_file(path: Path, *, create: bool = False) -> None:
    flags = os.O_RDONLY
    if create:
        flags |= os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileNotFoundError:
        return
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"SQLite storage path is not a regular file: {path}")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
