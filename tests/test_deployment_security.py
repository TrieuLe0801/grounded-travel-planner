"""Regression checks for deployment security configuration."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ngrok_limits_session_allocation_by_client_ip() -> None:
    policy = json.loads(
        (ROOT / "deploy" / "ngrok-traffic-policy.json").read_text(encoding="utf-8")
    )
    rules = policy["on_http_request"]
    expected_expressions = {
        (
            "req.method == 'POST'",
            "req.url.path in ['/api/session', '/api/session/reset']",
        ),
        ("req.method == 'POST'", "req.url.path == '/api/turns'"),
    }

    assert {tuple(rule["expressions"]) for rule in rules} == expected_expressions
    for rule in rules:
        action = rule["actions"][0]
        assert action["type"] == "rate-limit"
        assert action["config"]["algorithm"] == "sliding_window"
        assert action["config"]["capacity"] == 20
        assert action["config"]["rate"] == "60m"
        assert action["config"]["bucket_key"] == ["conn.client_ip"]


def test_ngrok_compose_service_uses_the_checked_in_policy() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "--traffic-policy-file" in compose
    assert (
        "./deploy/ngrok-traffic-policy.json:/etc/ngrok/traffic-policy.json:ro"
        in compose
    )


def test_uvicorn_runtime_disables_access_logs() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))

    assert "--no-access-log" in command
