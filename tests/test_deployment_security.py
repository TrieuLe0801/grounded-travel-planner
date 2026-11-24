"""Regression checks for deployment security configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_uvicorn_runtime_disables_access_logs() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))

    assert "--no-access-log" in command


def test_schema_gate_rejects_missing_column_before_container_swap() -> None:
    script = ROOT / "scripts" / "check_deploy_schema.py"
    spec = importlib.util.spec_from_file_location("check_deploy_schema", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Cursor:
        def __init__(self, columns):
            self.columns = columns

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query):
            assert "information_schema.columns" in query

        def fetchall(self):
            return self.columns

    class Connection:
        def __init__(self, columns):
            self.columns = columns

        def cursor(self):
            return Cursor(self.columns)

    with pytest.raises(RuntimeError, match="auth_sessions.remember_login"):
        module.check_required_columns(Connection([("auth_sessions", "verifier_hash")]))
    module.check_required_columns(Connection([("auth_sessions", "remember_login")]))

    deploy = (ROOT / "scripts" / "deploy_macos.sh").read_text(encoding="utf-8")
    build = deploy.index("compose build app")
    gate = deploy.index(
        "compose run --rm --no-deps app python /app/scripts/check_deploy_schema.py"
    )
    replace = deploy.index(
        "compose up --detach --no-deps --wait --wait-timeout 180 app"
    )
    assert build < gate < replace
    assert (
        'docker image tag "$old_image_id" grounded-travel-planner:local'
        in deploy[gate:replace]
    )
