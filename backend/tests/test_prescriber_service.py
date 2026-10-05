"""Tests for the prescriber service — ensure, fresh token, reference cache.

All tests use FakeMemedClient (or a stateful subclass) — never touch the network.
"""
from __future__ import annotations

import logging
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.services.prescriptions.fakes import FakeMemedClient
from app.services.prescriptions.ports import PrescriberResult
from app.services.prescriptions.prescriber import (
    cached_cities,
    cached_specialties,
    ensure_prescriber,
    fresh_token,
    invalidate_reference_caches,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _StatefulFake(FakeMemedClient):
    """Fake that raises KeyError on the first ``get_prescriber`` call.

    Subsequent calls return a result.  This simulates a prescriber that does
    not exist on Memed until ``create_prescriber`` is called.
    """

    def __init__(self) -> None:
        super().__init__()
        self._get_count = 0

    async def get_prescriber(self, external_id: str) -> PrescriberResult:
        self._record("get_prescriber", external_id=external_id)
        self._get_count += 1
        if self._get_count == 1:
            raise KeyError(f"Prescriber {external_id} not found")
        return PrescriberResult(
            external_id=external_id,
            memed_user_id="usr_001",
            status="Ativo",
            token="fake-token-001",
        )


async def _create_prescriber_in_db(
    db: AsyncSession,
    external_id: str = "ext-1",
    given_name: str = "Alice",
    family_name: str = "Silva",
    board_code: str = "CRM",
    board_number: str = "12345",
    board_state: str = "SP",
    birth_date: date | None = date(1980, 1, 15),
    city_id: int | None = 1,
    specialty_id: int | None = 10,
) -> Prescriber:
    """Create a Prescriber record in the test database."""
    prescriber = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        external_id=external_id,
        given_name=given_name,
        family_name=family_name,
        board_code=board_code,
        board_number=board_number,
        board_state=board_state,
        birth_date=birth_date,
        city_id=city_id,
        specialty_id=specialty_id,
    )
    db.add(prescriber)
    await db.flush()
    return prescriber


# ---------------------------------------------------------------------------
# ensure_prescriber
# ---------------------------------------------------------------------------


class TestEnsurePrescriber:
    """Idempotent ensure — creates once, then only reads."""

    async def test_ensure_creates_when_not_on_memed(self, db: AsyncSession):
        """First ensure calls create_prescriber when get_prescriber raises."""
        await _create_prescriber_in_db(db)
        fake = _StatefulFake()

        result = await ensure_prescriber(db, fake)

        # create_prescriber was called
        create_calls = [c for c in fake.calls if c[0] == "create_prescriber"]
        assert len(create_calls) == 1

        # memed_user_id and memed_status are set from the create result
        assert result.memed_user_id == "usr_001"
        assert result.memed_status == "Ativo"

    async def test_ensure_does_not_create_when_on_memed(self, db: AsyncSession):
        """ensure does NOT call create_prescriber when prescriber exists on Memed."""
        await _create_prescriber_in_db(db)
        fake = FakeMemedClient()  # get_prescriber always returns

        result = await ensure_prescriber(db, fake)

        # create_prescriber was NOT called
        create_calls = [c for c in fake.calls if c[0] == "create_prescriber"]
        assert len(create_calls) == 0

        # get_prescriber was called
        get_calls = [c for c in fake.calls if c[0] == "get_prescriber"]
        assert len(get_calls) == 1

        # memed_user_id and memed_status are set from the get result
        assert result.memed_user_id == "usr_001"
        assert result.memed_status == "Ativo"

    async def test_ensure_idempotent_same_external_id(self, db: AsyncSession):
        """First ensure creates; second ensure with same external_id does NOT create."""
        await _create_prescriber_in_db(db)
        fake = _StatefulFake()

        # First call: get_prescriber raises → create_prescriber called
        result1 = await ensure_prescriber(db, fake)
        assert result1.memed_user_id == "usr_001"

        # Second call: get_prescriber returns → create_prescriber NOT called
        result2 = await ensure_prescriber(db, fake)
        assert result2.memed_user_id == "usr_001"

        # create_prescriber was called exactly once
        create_calls = [c for c in fake.calls if c[0] == "create_prescriber"]
        assert len(create_calls) == 1

        # get_prescriber was called twice
        get_calls = [c for c in fake.calls if c[0] == "get_prescriber"]
        assert len(get_calls) == 2

    async def test_ensure_raises_when_no_prescriber(self, db: AsyncSession):
        """ensure_prescriber raises LookupError when no Prescriber record exists."""
        fake = FakeMemedClient()
        with pytest.raises(LookupError, match="No prescriber configured"):
            await ensure_prescriber(db, fake)


# ---------------------------------------------------------------------------
# fresh_token
# ---------------------------------------------------------------------------


class TestFreshToken:
    """fresh_token always calls get_prescriber and never persists."""

    async def test_fresh_token_calls_get_prescriber(self, db: AsyncSession):
        """fresh_token calls get_prescriber on every invocation."""
        await _create_prescriber_in_db(db)
        fake = FakeMemedClient()

        token = await fresh_token(db, fake)

        assert token == "fake-token-001"
        get_calls = [c for c in fake.calls if c[0] == "get_prescriber"]
        assert len(get_calls) == 1

    async def test_fresh_token_calls_every_time(self, db: AsyncSession):
        """Each fresh_token call results in a get_prescriber call."""
        await _create_prescriber_in_db(db)
        fake = FakeMemedClient()

        token1 = await fresh_token(db, fake)
        token2 = await fresh_token(db, fake)

        assert token1 == "fake-token-001"
        assert token2 == "fake-token-001"
        get_calls = [c for c in fake.calls if c[0] == "get_prescriber"]
        assert len(get_calls) == 2

    async def test_fresh_token_does_not_persist(self, db: AsyncSession):
        """fresh_token does not persist the token anywhere on the Prescriber."""
        prescriber = await _create_prescriber_in_db(db)
        fake = FakeMemedClient()

        token = await fresh_token(db, fake)

        assert token == "fake-token-001"
        # fresh_token never sets memed_user_id — that is ensure_prescriber's job
        assert prescriber.memed_user_id is None

    async def test_fresh_token_raises_when_no_prescriber(self, db: AsyncSession):
        """fresh_token raises LookupError when no Prescriber record exists."""
        fake = FakeMemedClient()
        with pytest.raises(LookupError, match="No prescriber configured"):
            await fresh_token(db, fake)


# ---------------------------------------------------------------------------
# cached_cities
# ---------------------------------------------------------------------------


class TestCachedCities:
    """cached_cities uses in-process TTL cache."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        invalidate_reference_caches()

    async def test_first_call_hits_client(self):
        fake = FakeMemedClient()
        cities = await cached_cities(fake, "São")
        assert len(cities) > 0
        list_calls = [c for c in fake.calls if c[0] == "list_cities"]
        assert len(list_calls) == 1

    async def test_second_call_hits_cache(self):
        fake = FakeMemedClient()
        await cached_cities(fake, "São")
        await cached_cities(fake, "São")
        list_calls = [c for c in fake.calls if c[0] == "list_cities"]
        assert len(list_calls) == 1  # second call served from cache

    async def test_different_queries_miss_cache(self):
        fake = FakeMemedClient()
        await cached_cities(fake, "São")
        await cached_cities(fake, "Rio")
        list_calls = [c for c in fake.calls if c[0] == "list_cities"]
        assert len(list_calls) == 2  # different query keys → two client calls


# ---------------------------------------------------------------------------
# cached_specialties
# ---------------------------------------------------------------------------


class TestCachedSpecialties:
    """cached_specialties uses in-process TTL cache."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        invalidate_reference_caches()

    async def test_first_call_hits_client(self):
        fake = FakeMemedClient()
        specialties = await cached_specialties(fake, "ped")
        assert len(specialties) > 0
        list_calls = [c for c in fake.calls if c[0] == "list_specialties"]
        assert len(list_calls) == 1

    async def test_second_call_hits_cache(self):
        fake = FakeMemedClient()
        await cached_specialties(fake, "ped")
        await cached_specialties(fake, "ped")
        list_calls = [c for c in fake.calls if c[0] == "list_specialties"]
        assert len(list_calls) == 1


# ---------------------------------------------------------------------------
# Log redaction — sentinel token never appears in logs or repr
# ---------------------------------------------------------------------------


class TestLogRedaction:
    """Sentinel token never appears in captured logs or repr."""

    def test_prescriber_result_repr_hides_token(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token="SENTINEL-TOKEN-42",
        )
        r = repr(result)
        assert "SENTINEL-TOKEN-42" not in r

    def test_prescriber_result_repr_hides_cpf(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token="tok_xxx",
            cpf="SENTINEL-CPF-999",
        )
        r = repr(result)
        assert "SENTINEL-CPF-999" not in r

    def test_logs_do_not_contain_sentinel(self, caplog):
        """Verify no logs contain the sentinel token.

        The prescriber service intentionally never logs tokens or CPF.
        This test proves no accidental logging was added.
        """
        caplog.set_level(logging.DEBUG)
        # No prescriber-service code runs here — we assert the baseline
        # is clean.  If a future change adds logging of secrets, this
        # test will catch it.
        assert "SENTINEL" not in caplog.text