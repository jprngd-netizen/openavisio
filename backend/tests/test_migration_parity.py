"""Regression: the schema built by ALEMBIC MIGRATIONS must accept ORM inserts.

The rest of the suite builds its schema with ``Base.metadata.create_all`` (see
``tests/conftest.py``), which silently hides migration/model parity bugs: a
column created NOT NULL by a migration but no longer written by the ORM never
exists under ``create_all``, so nothing fails.

That is exactly what WS-5 caused. ``w5a1b2c3d4e5`` added the typed
``calendar_events.start_at_ts`` and remapped the ORM attribute onto it, leaving
the legacy ISO-8601 ``start_at`` String column (created NOT NULL in the initial
migration ``ea27601363a6``) unwritten — so every ``CalendarEvent`` insert against
a migrated schema raised ``NotNullViolationError: null value in column
"start_at"``. The corrective migration ``z7v8w9x0y1z2`` relaxes it to nullable.

This test exercises the migration path directly and is therefore the only test
that would have caught the bug:

1. create a scratch database (``vaultdb_migrationtest``) on the same server the
   suite already talks to;
2. run ``alembic upgrade head`` into it (subprocess, so a clean DATABASE_URL env
   is isolated from the test process settings);
3. insert a CalendarEvent, an Encounter and an Observation through the ORM and
   assert none raises a NOT NULL violation;
4. drop the scratch database.

It is self-contained and idempotent: it never touches ``vaultdb_test``, creates
its own DB, and drops it before and after, so a previous crashed run cannot
poison the next.
"""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]

SCRATCH_DB = "vaultdb_migrationtest"


def _base_url() -> str:
    """Server URL with the db name stripped, from the suite's TEST_DATABASE_URL.

    conftest guarantees that URL points at ``vaultdb_test`` (it asserts the
    name), which gives us host/credentials for the same Postgres server.
    """
    from tests.conftest import TEST_DATABASE_URL

    return TEST_DATABASE_URL.rsplit("/", 1)[0]


def _admin_url() -> str:
    return _base_url() + "/postgres"


def _scratch_url() -> str:
    return _base_url() + "/" + SCRATCH_DB


async def _run_sql(url: str, *statements: str) -> None:
    eng = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with eng.connect() as conn:
            for stmt in statements:
                await conn.execute(sa.text(stmt))
    finally:
        await eng.dispose()


async def _create_scratch_db() -> None:
    await _run_sql(
        _admin_url(),
        f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)',
        f'CREATE DATABASE "{SCRATCH_DB}"',
    )


async def _drop_scratch_db() -> None:
    await _run_sql(_admin_url(), f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')


def _upgrade_head() -> None:
    """Run the real migration chain into the scratch DB on a clean env."""
    env = dict(os.environ)
    env["DATABASE_URL"] = _scratch_url()
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"alembic upgrade head failed ({proc.returncode})\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


async def _smoke_insert() -> None:
    """Insert the rows that tripped the WS-5 parity bug, through the ORM."""
    from app.models import CalendarEvent, Encounter, Observation, Patient, User

    eng = create_async_engine(_scratch_url())
    maker = async_sessionmaker(eng, expire_on_commit=False)
    try:
        async with maker() as session:
            user = User(email="parity@test.local", hashed_password="x")
            session.add(user)
            await session.flush()

            patient = Patient(
                created_by=user.id, given_name="Parity", family_name="Check"
            )
            session.add(patient)
            await session.flush()

            now = datetime.now(UTC)
            # The exact trigger of the bug: the ORM must be able to persist a
            # CalendarEvent without writing the retired legacy `start_at`.
            session.add(
                CalendarEvent(
                    patient_id=patient.id,
                    owner_id=user.id,
                    title="Consulta",
                    start_at=now,
                )
            )
            session.add(
                Encounter(
                    patient_id=patient.id,
                    owner_id=user.id,
                    encounter_date=now,
                )
            )
            session.add(Observation(patient_id=patient.id, owner_id=user.id))
            # A NOT NULL violation surfaces here, at flush/commit time.
            await session.commit()
    finally:
        await eng.dispose()


async def test_migrated_schema_accepts_orm_inserts():
    await _create_scratch_db()
    try:
        _upgrade_head()

        # The retired legacy column must end up nullable under migrations.
        eng = create_async_engine(_scratch_url())
        try:
            async with eng.connect() as conn:
                nullable = (
                    await conn.execute(
                        sa.text(
                            "SELECT is_nullable FROM information_schema.columns "
                            "WHERE table_name='calendar_events' "
                            "AND column_name='start_at'"
                        )
                    )
                ).scalar_one()
            assert nullable == "YES", (
                "legacy calendar_events.start_at must be nullable after the "
                "corrective migration"
            )
        finally:
            await eng.dispose()

        await _smoke_insert()
    finally:
        await _drop_scratch_db()
