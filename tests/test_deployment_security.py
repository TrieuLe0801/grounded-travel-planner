"""Regression checks for deployment security configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_uvicorn_runtime_disables_access_logs() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))

    assert "--no-access-log" in command
