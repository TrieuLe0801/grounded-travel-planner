"""Optional integration contract for the PostgreSQL saved-tour archive.

This test never starts a database or contacts providers.  Set the
``GTP_POSTGRES_TEST_DSN`` environment variable to run it against an explicitly
provisioned disposable PostgreSQL database.
"""

from __future__ import annotations

import os
from datetime import date, time

import pytest

from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)


def _plan(plan_id: str, *, destination: str = "Hue") -> SightseeingPlan:
    source = SourceReference(
        source_id=f"{plan_id}-source",
        title="Official visitor information",
        url="https://example.test/visitor-information",
        snippet="Deterministic offline fixture.",
        retrieval_query=destination,
    )
    return SightseeingPlan(
        plan_id=plan_id,
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=1,
        revision=1,
        entries=[
            ScheduleEntry(
                id=f"{plan_id}-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id=f"{plan_id}-place",
                    name="Imperial City",
                    description="Saved fixture stop.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
    )


@pytest.fixture
def postgres_repository() -> object:
    """Build a repository only when caller explicitly enables integration tests."""

    dsn = os.getenv("GTP_POSTGRES_TEST_DSN")
    psycopg = pytest.importorskip("psycopg")
    from grounded_travel_planner.postgres_saved_tours import PostgresSavedTourRepository

    if dsn:
        connection_info = psycopg.conninfo.conninfo_to_dict(dsn)
    elif os.getenv("GTP_POSTGRES_TEST") == "1":
        connection_info = {
            "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
            "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
            "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
            "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
            "port": os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"),
        }
    else:
        pytest.skip(
            "set GTP_POSTGRES_TEST_DSN or GTP_POSTGRES_TEST=1 "
            "to run PostgreSQL integration tests"
        )
    required = ("host", "dbname", "user", "password")
    if any(not connection_info.get(key) for key in required):
        pytest.fail("PostgreSQL integration settings are incomplete")
    try:
        port = int(connection_info.get("port", 5432))
    except (TypeError, ValueError) as error:
        pytest.fail(f"PostgreSQL integration port is invalid: {error}")
    repository = PostgresSavedTourRepository(
        host=str(connection_info["host"]),
        database=str(connection_info["dbname"]),
        user=str(connection_info["user"]),
        password=str(connection_info["password"]),
        port=port,
    )
    try:
        yield repository
    finally:
        try:
            with (
                psycopg.connect(**connection_info) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("DELETE FROM saved_tours WHERE plan_id LIKE 'pytest-%'")
        finally:
            repository.close()


def test_postgres_repository_save_list_detail_delete_and_owner_isolation(
    postgres_repository: object,
) -> None:
    """Verify archive contract on a caller-provided disposable PostgreSQL DB."""

    repository = postgres_repository
    owner_one = "pytest-owner-one"
    owner_two = "pytest-owner-two"
    plan = _plan("pytest-postgres-plan")

    saved = repository.save(owner_one, plan)  # type: ignore[attr-defined]
    repeated = repository.save(owner_one, plan)  # type: ignore[attr-defined]

    assert repeated.id == saved.id
    first_page = repository.list(owner_one, limit=1)  # type: ignore[attr-defined]
    assert [item.id for item in first_page.items] == [saved.id]
    assert first_page.has_more is False
    assert first_page.next_cursor is None

    detail = repository.get(owner_one, saved.id)  # type: ignore[attr-defined]
    assert detail is not None
    assert detail.plan.model_dump(mode="json") == plan.model_dump(mode="json")
    assert repository.list(owner_two).items == []  # type: ignore[attr-defined]
    assert repository.get(owner_two, saved.id) is None  # type: ignore[attr-defined]
    assert repository.delete(owner_two, saved.id) is False  # type: ignore[attr-defined]
    assert repository.delete(owner_one, saved.id) is True  # type: ignore[attr-defined]
    assert repository.get(owner_one, saved.id) is None  # type: ignore[attr-defined]
