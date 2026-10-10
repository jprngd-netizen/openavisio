import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Where the app itself talks to Postgres, read before .env.test can shadow it.
# Inside a container that host is `postgres`; .env.test hardcodes `localhost`
# for bare-metal runs, which made every test fail to connect in Docker.
_APP_DATABASE_URL = os.getenv("DATABASE_URL")

# Local test settings (dev DB URL, encryption key). Real env vars win.
# Must run before app imports so settings pick up the values.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.test")

_pg_password = os.getenv("POSTGRES_PASSWORD", "devpassword123")

if _APP_DATABASE_URL:
    # same server the app uses, but never the app's database
    TEST_DATABASE_URL = _APP_DATABASE_URL.rsplit("/", 1)[0] + "/vaultdb_test"
else:
    TEST_DATABASE_URL = os.getenv(
        "TEST_DATABASE_URL",
        f"postgresql+asyncpg://openavisio:{_pg_password}@postgres:5432/vaultdb_test",
    )

# Safety guard: never run against the production database
assert "vaultdb_test" in TEST_DATABASE_URL, (
    f"Refusing to run tests against a non-test database.\n"
    f"TEST_DATABASE_URL={TEST_DATABASE_URL}\n"
    f"Database name must contain 'vaultdb_test'."
)

# Bind the app's OWN session factory (``AsyncSessionLocal`` / ``get_session_factory``,
# created at import from ``settings.database_url``) to the same test database the
# suite uses. Without this, code paths that do not go through the injected
# ``get_db`` (e.g. prescription capture's ``session_factory``) silently read and
# write whatever database ``DATABASE_URL`` points at — the dev database in a
# bare-metal run, or an unmigrated one in CI — which both leaks state between
# tests and lets the migration path pass only by accident.
from app.core.config import settings  # noqa: E402

settings.database_url = TEST_DATABASE_URL

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Schema-building mode (WS-12). Default keeps the historical behaviour
# (``Base.metadata.create_all``) so nothing changes for day-to-day runs.
# Set ``OA_TEST_SCHEMA=migrations`` to build the schema from the real Alembic
# chain instead — the only mode that would have caught the WS-5b drift
# (a migration-created NOT NULL column the ORM no longer writes).
#
#   OA_TEST_SCHEMA=migrations TEST_DATABASE_URL=... uv run pytest -q
#
# In migration mode the schema is dropped and rebuilt from ``alembic upgrade
# head`` once per session; ``create_all`` is NOT run.
OA_TEST_SCHEMA = os.getenv("OA_TEST_SCHEMA", "create_all").strip().lower()
USE_MIGRATIONS = OA_TEST_SCHEMA == "migrations"


def _alembic_upgrade_head(url: str) -> None:
    """Run the real migration chain into ``url`` on a clean env.

    Subprocess + explicit ``DATABASE_URL`` keeps Alembic's settings isolated
    from the test process (mirrors ``test_migration_parity``).
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = url
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"alembic upgrade head failed ({proc.returncode}) for {url}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


async def _reset_schema(conn) -> None:
    """Drop everything Alembic manages so ``upgrade head`` starts from zero."""
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    if USE_MIGRATIONS:
        # Build the schema straight from the migration chain — no create_all.
        async with eng.begin() as conn:
            await _reset_schema(conn)
        _alembic_upgrade_head(TEST_DATABASE_URL)
        async with eng.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    else:
        async with eng.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
    yield eng
    if not USE_MIGRATIONS:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    """Transactional DB session — rolls back after each test."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
async def client(db: AsyncSession):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
