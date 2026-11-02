"""Offline API contracts for durable, owner-scoped saved tour snapshots."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import date, time
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from grounded_travel_planner.contracts import (
    AgentResponse,
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    TripRequest,
)
from grounded_travel_planner.saved_tours import SavedTourRepository
from grounded_travel_planner.web.api import (
    COOKIE_NAME,
    SAVED_TOURS_OWNER_COOKIE_NAME,
    create_app,
)


def _plan(destination: str) -> SightseeingPlan:
    source = SourceReference(
        source_id="saved-tour-source",
        title=f"{destination} official visitor information",
        url="https://example.test/official-visitor-information",
        snippet="Grounded fixture source retained in the snapshot.",
        retrieval_query=destination,
        supports_opening_hours=True,
    )
    return SightseeingPlan(
        plan_id=f"saved-plan-{destination.casefold()}",
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=2,
        entries=[
            ScheduleEntry(
                id="saved-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=PlaceRecommendation(
                    place_id="saved-place",
                    name=f"{destination} landmark",
                    description="Deterministic offline recommendation.",
                    source_references=[source],
                    opening_hours="09:00-17:00",
                    opening_hours_verified=True,
                ),
            )
        ],
        summary=f"Offline {destination} itinerary.",
    )


class FakeTravelPlannerService:
    """A model- and search-free service fixture with an optional pending turn."""

    graph = object()

    def __init__(self) -> None:
        self.created_sessions = 0
        self.turns: list[dict[str, object]] = []
        self.block_started = Event()
        self.release_block = Event()

    def create_session(self) -> str:
        self.created_sessions += 1
        return f"saved-tour-thread-{self.created_sessions}"

    def handle_turn(self, **kwargs: object) -> AgentResponse:
        self.turns.append(kwargs)
        if kwargs["message"] == "block":
            self.block_started.set()
            assert self.release_block.wait(timeout=3)
        request = kwargs.get("request")
        destination = request.destination if isinstance(request, TripRequest) else "Hue"
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="Offline committed plan.",
            current_plan=_plan(destination),
            committed=True,
        )


class FakeVisualService:
    def resolve(self, plan: SightseeingPlan) -> dict[str, object]:
        return {}


def _client(
    database_path: Path,
    service: FakeTravelPlannerService,
    *,
    base_url: str = "https://localhost",
) -> TestClient:
    return TestClient(
        create_app(
            service,
            FakeVisualService(),
            saved_tour_repository=SavedTourRepository(database_path),
        ),
        base_url=base_url,
    )


def _start(client: TestClient) -> None:
    assert client.post("/api/session").status_code == 201


def _commit_plan(client: TestClient, destination: str = "Hue") -> dict[str, object]:
    accepted = client.post(
        "/api/turns",
        json={
            "message": f"Create {destination}",
            "request": {
                "destination": destination,
                "start_date": "2026-11-01",
                "day_count": 2,
            },
        },
    )
    assert accepted.status_code == 202
    state = client.get("/api/session")
    assert state.status_code == 200
    return state.json()


def _migration_function():
    script = Path(__file__).parents[1] / "scripts" / "migrate_saved_tours_index.py"
    specification = importlib.util.spec_from_file_location(
        "saved_tours_migration", script
    )
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.migrate


def _insert_summaries(
    database_path: Path,
    repository: SavedTourRepository,
    owner_token: str,
    rows: list[tuple[str, str]],
) -> None:
    """Insert list-only fixtures with caller-selected ordering keys."""

    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO saved_tours (
                id, owner_hash, plan_id, revision, title, destination,
                start_date, day_count, saved_at, plan_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    tour_id,
                    repository.owner_hash(owner_token),
                    f"fixture-plan-{tour_id}",
                    1,
                    "Fixture",
                    "Fixture",
                    "2026-11-01",
                    1,
                    saved_at,
                    '{"schema_version":1,"plan":{}}',
                )
                for tour_id, saved_at in rows
            ],
        )


def test_explicit_save_snapshots_sources_is_idempotent_and_can_be_deleted(
    tmp_path: Path,
) -> None:
    service = FakeTravelPlannerService()
    client = _client(tmp_path / "saved-tours.sqlite", service)
    _start(client)
    plan = _commit_plan(client)["plan"]

    saved = client.post("/api/saved-tours")
    assert saved.status_code == 200
    snapshot = saved.json()
    assert snapshot["plan"] == plan
    assert (
        snapshot["plan"]["entries"][0]["place"]["source_references"]
        == plan["entries"][0]["place"]["source_references"]
    )
    assert client.cookies.get(SAVED_TOURS_OWNER_COOKIE_NAME)

    repeated = client.post("/api/saved-tours")
    assert repeated.status_code == 200
    assert repeated.json() == snapshot

    turn_count = len(service.turns)
    listed = client.get("/api/saved-tours")
    assert listed.status_code == 200
    assert listed.json() == {
        "items": [{key: value for key, value in snapshot.items() if key != "plan"}],
        "has_more": False,
        "next_cursor": None,
    }
    detail = client.get(f"/api/saved-tours/{snapshot['id']}")
    assert detail.status_code == 200
    assert detail.json() == snapshot
    assert len(service.turns) == turn_count

    deleted = client.delete(f"/api/saved-tours/{snapshot['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/api/saved-tours").json() == {
        "items": [],
        "has_more": False,
        "next_cursor": None,
    }


def test_save_requires_an_accepted_non_pending_session_plan(tmp_path: Path) -> None:
    service = FakeTravelPlannerService()
    client = _client(tmp_path / "saved-tours.sqlite", service)
    _start(client)

    absent = client.post("/api/saved-tours")
    assert absent.status_code == 409
    assert absent.json()["detail"] == "Chưa có lịch trình hợp lệ để lưu."

    assert client.post("/api/turns", json={"message": "block"}).status_code == 202
    assert service.block_started.wait(timeout=1)
    pending = client.post("/api/saved-tours")
    assert pending.status_code == 409
    assert pending.json()["detail"] == "Một yêu cầu đang được xử lý."

    service.release_block.set()
    assert client.get("/api/session").status_code == 200


def test_saved_tours_are_owner_scoped_and_survive_a_new_app_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "saved-tours.sqlite"
    owner_service = FakeTravelPlannerService()
    owner = _client(database_path, owner_service)
    _start(owner)
    _commit_plan(owner, "Hue")
    saved = owner.post("/api/saved-tours").json()
    owner_token = owner.cookies.get(SAVED_TOURS_OWNER_COOKIE_NAME)
    assert owner_token

    other = _client(database_path, FakeTravelPlannerService())
    _start(other)
    assert other.get("/api/saved-tours").json() == {
        "items": [],
        "has_more": False,
        "next_cursor": None,
    }
    assert other.get(f"/api/saved-tours/{saved['id']}").status_code == 404
    assert other.delete(f"/api/saved-tours/{saved['id']}").status_code == 404

    restarted = _client(database_path, FakeTravelPlannerService())
    _start(restarted)
    restarted.cookies.set(SAVED_TOURS_OWNER_COOKIE_NAME, owner_token)
    assert restarted.get("/api/saved-tours").json()["items"][0]["id"] == saved["id"]
    assert restarted.get(f"/api/saved-tours/{saved['id']}").json() == saved


def test_saved_tours_use_stable_keyset_pages_across_duplicate_timestamps(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "saved-tours.sqlite"
    repository = SavedTourRepository(database_path)
    owner_token = "first-owner-token"
    other_owner_token = "second-owner-token"
    timestamp = "2026-11-01T12:00:00+00:00"
    saved_ids = [f"{index:032x}" for index in range(105)]
    _insert_summaries(
        database_path,
        repository,
        owner_token,
        [(tour_id, timestamp) for tour_id in saved_ids],
    )
    _insert_summaries(
        database_path,
        repository,
        other_owner_token,
        [("f" * 32, "2027-01-01T00:00:00+00:00")],
    )

    service = FakeTravelPlannerService()
    client = TestClient(
        create_app(
            service,
            FakeVisualService(),
            saved_tour_repository=SavedTourRepository(database_path),
        ),
        base_url="https://localhost",
    )
    client.cookies.set(SAVED_TOURS_OWNER_COOKIE_NAME, owner_token)
    first_page = client.get("/api/saved-tours?limit=50")

    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["has_more"] is True
    assert first_payload["next_cursor"]

    # A record inserted above the cursor must not move or duplicate older pages.
    _insert_summaries(
        database_path,
        repository,
        owner_token,
        [("e" * 32, "2027-01-01T00:00:00+00:00")],
    )
    second_page = client.get(
        "/api/saved-tours",
        params={"limit": 50, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(first_payload["items"]) == 50
    assert len(second_payload["items"]) == 50
    assert second_payload["has_more"] is True
    third_page = client.get(
        "/api/saved-tours",
        params={"cursor": second_payload["next_cursor"]},
    )
    assert third_page.status_code == 200
    third_payload = third_page.json()
    assert len(third_payload["items"]) == 5
    assert third_payload["has_more"] is False
    assert third_payload["next_cursor"] is None
    assert {item["id"] for item in first_payload["items"]}.isdisjoint(
        {item["id"] for item in second_payload["items"]}
    )
    assert {item["id"] for item in first_payload["items"]} | {
        item["id"] for item in second_payload["items"]
    } | {item["id"] for item in third_payload["items"]} == set(saved_ids)
    assert service.turns == []


def test_saved_tour_cursor_rejects_malformed_and_offset_inputs(tmp_path: Path) -> None:
    client = _client(tmp_path / "saved-tours.sqlite", FakeTravelPlannerService())
    for query in ("?cursor=invalid", "?offset=0"):
        response = client.get(f"/api/saved-tours{query}")
        assert response.status_code == 422
        assert response.json()["detail"] == "Cursor không hợp lệ."
    assert client.get("/api/saved-tours?cursor=" + "x" * 513).status_code == 422


def test_migration_upgrades_legacy_index_without_changing_snapshot_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.sqlite"
    plan = _plan("Hue")
    snapshot = json.dumps(
        {"schema_version": 1, "plan": plan.model_dump(mode="json")},
        separators=(",", ":"),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE saved_tours (
                id TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, plan_id TEXT NOT NULL,
                revision INTEGER NOT NULL, title TEXT NOT NULL, destination TEXT NOT NULL,
                start_date TEXT NOT NULL, day_count INTEGER NOT NULL, saved_at TEXT NOT NULL,
                plan_snapshot TEXT NOT NULL, UNIQUE(owner_hash, plan_id, revision)
            )
        """)
        connection.execute(
            "CREATE INDEX saved_tours_by_owner ON saved_tours(owner_hash, saved_at DESC)"
        )
        connection.execute(
            "INSERT INTO saved_tours VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "a" * 32,
                SavedTourRepository.owner_hash("legacy-owner"),
                plan.plan_id,
                plan.revision,
                "Hue",
                "Hue",
                "2026-11-01",
                2,
                "2026-11-01T12:00:00+00:00",
                snapshot,
            ),
        )
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(Exception, match="requires migration"):
        SavedTourRepository(database_path)
    _migration_function()(database_path)
    _migration_function()(database_path)

    repository = SavedTourRepository(database_path)
    assert repository.get("legacy-owner", "a" * 32).plan == plan
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert "saved_tours_by_owner" not in index_names
    assert "saved_tours_by_owner_saved_at_id" in index_names


def test_keyset_query_uses_composite_index_without_temp_sort(tmp_path: Path) -> None:
    database_path = tmp_path / "saved-tours.sqlite"
    repository = SavedTourRepository(database_path)
    owner_hash = repository.owner_hash("plan-owner")
    with sqlite3.connect(database_path) as connection:
        plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT id, title, destination, start_date, day_count, revision, saved_at
            FROM saved_tours
            WHERE owner_hash = ?
              AND (saved_at, id) < (?, ?)
            ORDER BY saved_at DESC, id DESC LIMIT ?
            """,
            (
                owner_hash,
                "2026-11-01T12:00:00+00:00",
                "f" * 32,
                51,
            ),
        ).fetchall()
    details = "\n".join(str(row[3]).upper() for row in plan)
    assert "SAVED_TOURS_BY_OWNER_SAVED_AT_ID" in details
    assert "TEMP B-TREE" not in details


def test_saved_tour_owner_cookie_secure_attribute_follows_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GTP_SAVED_TOURS_COOKIE_SECURE", "false")
    local_client = _client(
        tmp_path / "local.sqlite",
        FakeTravelPlannerService(),
        base_url="http://localhost",
    )
    _start(local_client)
    _commit_plan(local_client)
    local_save = local_client.post("/api/saved-tours")
    assert local_save.status_code == 200
    assert "; secure" not in local_save.headers["set-cookie"].casefold()
    forwarded = local_client.post(
        "/api/session", headers={"x-forwarded-proto": "https"}
    )
    assert "; secure" in forwarded.headers["set-cookie"].casefold()

    monkeypatch.setenv("GTP_SAVED_TOURS_COOKIE_SECURE", "TrUe")
    secure_client = _client(
        tmp_path / "secure.sqlite",
        FakeTravelPlannerService(),
        base_url="https://localhost",
    )
    _start(secure_client)
    _commit_plan(secure_client)
    secure_save = secure_client.post("/api/saved-tours")
    assert secure_save.status_code == 200
    assert "; secure" in secure_save.headers["set-cookie"].casefold()


def test_public_http_proxy_marks_session_and_owner_cookies_secure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GTP_SAVED_TOURS_COOKIE_SECURE", raising=False)
    client = TestClient(
        create_app(
            FakeTravelPlannerService(),
            FakeVisualService(),
            saved_tour_repository=SavedTourRepository(tmp_path / "proxy.sqlite"),
        ),
        base_url="http://planner.example",
    )
    started = client.post("/api/session")
    assert "; secure" in started.headers["set-cookie"].casefold()
    loopback_host = _client(
        tmp_path / "spoofed-host.sqlite",
        FakeTravelPlannerService(),
        base_url="http://localhost",
    )
    assert (
        "; secure"
        in loopback_host.post("/api/session").headers["set-cookie"].casefold()
    )
    session_id = started.cookies.get(COOKIE_NAME)
    assert session_id is not None
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, session_id)
    _commit_plan(client)
    saved = client.post("/api/saved-tours")
    assert saved.status_code == 200
    assert "; secure" in saved.headers["set-cookie"].casefold()

    reset = client.post("/api/session/reset")
    assert reset.status_code == 200
    assert "; secure" in reset.headers["set-cookie"].casefold()


def test_corrupt_saved_snapshot_fails_safe_without_exposing_it(tmp_path: Path) -> None:
    database_path = tmp_path / "saved-tours.sqlite"
    client = _client(database_path, FakeTravelPlannerService())
    _start(client)
    _commit_plan(client)
    saved = client.post("/api/saved-tours").json()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE saved_tours SET plan_snapshot = ? WHERE id = ?",
            ("{not valid json", saved["id"]),
        )

    detail = client.get(f"/api/saved-tours/{saved['id']}")
    assert detail.status_code == 503
    assert detail.json()["detail"] == "Không thể đọc tour đã lưu lúc này."
