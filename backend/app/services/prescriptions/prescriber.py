"""Prescriber service — idempotent ensure, fresh token, reference-data cache.

Provides the three operations the router layer needs to manage a prescriber
on the Memed Sinapse Prescrição API:

* ``ensure_prescriber`` — idempotent sync: reads the local singleton, calls
  ``get_prescriber`` on Memed, and creates it on Memed only when not found.
* ``fresh_token`` — always calls ``get_prescriber`` and returns the token
  **without** persisting it.
* ``cached_cities`` / ``cached_specialties`` — short-TTL in-process cache
  following the pattern from ``app.core.patient_keys``.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.services.prescriptions.ports import MemedClient, ReferenceItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference-data cache (in-process, short TTL)
# ---------------------------------------------------------------------------

_TTL_SECONDS = 300  # 5 min
_cities_cache: dict[str, tuple[list[ReferenceItem], float]] = {}
_specialties_cache: dict[str, tuple[list[ReferenceItem], float]] = {}


def invalidate_reference_caches() -> None:
    """Clear all reference-data caches.

    Used in tests to ensure a clean state between test cases.
    Follows the ``invalidate`` pattern from ``app.core.patient_keys``.
    """
    _cities_cache.clear()
    _specialties_cache.clear()


async def cached_cities(
    client: MemedClient, q: str | None = None
) -> list[ReferenceItem]:
    """Search cities with an in-process TTL cache.

    Follows the TTL-cache pattern from ``app.core.patient_keys`` (lines 22-41).
    The cache key is the query string (empty string for "all").
    """
    cache_key = q or ""
    hit = _cities_cache.get(cache_key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    items = await client.list_cities(q=q)
    _cities_cache[cache_key] = (items, time.monotonic() + _TTL_SECONDS)
    return items


async def cached_specialties(
    client: MemedClient, q: str | None = None
) -> list[ReferenceItem]:
    """Search specialties with an in-process TTL cache.

    Follows the TTL-cache pattern from ``app.core.patient_keys`` (lines 22-41).
    The cache key is the query string (empty string for "all").
    """
    cache_key = q or ""
    hit = _specialties_cache.get(cache_key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    items = await client.list_specialties(q=q)
    _specialties_cache[cache_key] = (items, time.monotonic() + _TTL_SECONDS)
    return items


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def _format_date(d: date) -> str:
    """Format a date as ``dd/mm/YYYY`` for the Memed API."""
    return d.strftime("%d/%m/%Y")


def _build_prescriber_payload(prescriber: Prescriber) -> dict:
    """Build the JSON:API request body for ``create_prescriber``.

    Reads the prescriber's fields from the ORM record and assembles the
    ``data.attributes`` block (including ``board``, ``data_nascimento``) and
    ``data.relationships`` for city and specialty.
    """
    attributes: dict[str, Any] = {
        "external_id": prescriber.external_id,
        "nome": prescriber.given_name,
        "sobrenome": prescriber.family_name,
        "board": (
            f"{prescriber.board_code}/{prescriber.board_number}/"
            f"{prescriber.board_state}"
        ),
    }
    if prescriber.birth_date is not None:
        attributes["data_nascimento"] = _format_date(prescriber.birth_date)
    if prescriber.email is not None:
        attributes["email"] = prescriber.email
    if prescriber.phone is not None:
        attributes["telefone"] = prescriber.phone
    if prescriber.sex is not None:
        attributes["sexo"] = prescriber.sex

    data: dict[str, Any] = {
        "data": {
            "type": "usuario-prescritor",
            "attributes": attributes,
        }
    }

    relationships: dict[str, Any] = {}
    if prescriber.city_id is not None:
        relationships["cidade"] = {
            "data": {"id": prescriber.city_id, "type": "cidade"}
        }
    if prescriber.specialty_id is not None:
        relationships["especialidade"] = {
            "data": {"id": prescriber.specialty_id, "type": "especialidade"}
        }
    if relationships:
        data["data"]["relationships"] = relationships

    return data


# ---------------------------------------------------------------------------
# ensure_prescriber
# ---------------------------------------------------------------------------


async def ensure_prescriber(
    db: AsyncSession,
    client: MemedClient,
) -> Prescriber:
    """Ensure the prescriber exists on Memed and is persisted locally.

    Reads the singleton ``Prescriber`` from the database, calls
    ``get_prescriber`` on Memed, and — if the prescriber is not found there
    (raises ``LookupError``) — creates it via ``create_prescriber``.

    Always updates ``memed_user_id`` / ``memed_status`` on the local record.
    On success, sets ``sync_status`` to ``"ok"`` and records
    ``token_issued_at``.  On failure (network error, etc.), sets
    ``sync_status`` to ``"error"`` with the reason in ``sync_error`` and
    **returns** the prescriber without updating Memed fields — the local
    record remains valid.

    Idempotent by ``external_id``: a second call with the same prescriber
    (already synced) will **not** call ``create_prescriber`` again.

    Raises:
        LookupError: if no ``Prescriber`` record exists in the database.
    """
    prescriber = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)
    if prescriber is None:
        raise LookupError("No prescriber configured")

    try:
        try:
            result = await client.get_prescriber(prescriber.external_id)
        except LookupError:
            # Prescriber not found on Memed — create it
            payload = _build_prescriber_payload(prescriber)
            result = await client.create_prescriber(payload)

        prescriber.memed_user_id = result.memed_user_id
        prescriber.memed_status = result.status
        prescriber.sync_status = "ok"
        prescriber.sync_error = None
        prescriber.token_issued_at = datetime.now(timezone.utc)
    except Exception as exc:
        prescriber.sync_status = "error"
        prescriber.sync_error = str(exc)
        logger.warning("Memed sync failed: %s", exc)
        # Local record remains valid — do not re-raise

    await db.flush()
    return prescriber


# ---------------------------------------------------------------------------
# fresh_token
# ---------------------------------------------------------------------------


async def fresh_token(
    db: AsyncSession,
    client: MemedClient,
) -> str:
    """Get a fresh ``data-token`` from Memed.

    **Always** calls ``get_prescriber`` at call time.  Records
    ``token_issued_at`` on the prescriber and flushes so the caller's
    commit persists it.  Returns the token **without** persisting it
    anywhere else.

    Raises:
        LookupError: if no ``Prescriber`` record exists in the database.
    """
    prescriber = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)
    if prescriber is None:
        raise LookupError("No prescriber configured")

    result = await client.get_prescriber(prescriber.external_id)
    prescriber.token_issued_at = datetime.now(timezone.utc)
    await db.flush()
    return result.token


# ---------------------------------------------------------------------------
# is_token_expired
# ---------------------------------------------------------------------------


def is_token_expired(
    prescriber: Prescriber,
    validity_hours: int = 12,
    now: datetime | None = None,
) -> bool:
    """Check whether the prescriber's BirdID token has expired.

    BirdID tokens are valid in a 1–12 h window.  Since BirdID failures carry
    no API error code (only a UI message), the only way to distinguish
    "token expired" from "signature failure" is to track the emission
    instant locally.

    Parameters
    ----------
    prescriber:
        The Prescriber record whose ``token_issued_at`` field is checked.
    validity_hours:
        Expected token validity in hours (default 12, the BirdID maximum).
    now:
        Override the current time for testing (clock control).  Defaults to
        ``datetime.now(timezone.utc)``.

    Returns
    -------
    bool
        ``True`` if the token has expired or was never issued.
    """
    if prescriber.token_issued_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    return now > prescriber.token_issued_at + timedelta(hours=validity_hours)