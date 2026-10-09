"""WS-3: N diagnoses per consultation, linked to canonical problem-list Conditions.

Two responsibilities:

* ``resolve_condition`` / ``sync_encounter_diagnoses`` — the live write path. A
  diagnosis recorded in a consultation finds-or-creates the patient's Condition
  (the problem list) by CID-10 code and links it through ``encounter_conditions``.
  On edit the links are reconciled: ones that left are soft-deleted, new ones are
  added, existing ones are re-activated. The Condition is never deleted — only the
  link is.
* ``backfill_encounter_diagnoses`` — the migration path. Legacy consultations that
  carry a single ``cid10_code`` are turned into a Condition + link, conservatively
  (an existing Condition for the same patient/code is reused) and idempotently.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.condition import Condition
from app.models.encounter import Encounter
from app.models.encounter_condition import EncounterCondition

_PLACEHOLDER_DISPLAY = "—"


async def resolve_condition(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    owner_id: uuid.UUID,
    code: str | None,
    code_display: str,
    recorded_date: Any = None,
    condition_id: uuid.UUID | None = None,
) -> Condition:
    """Return the problem-list Condition for a diagnosis, creating it if absent.

    An explicit ``condition_id`` wins when it points at a live Condition of the
    same patient; otherwise the lookup is by code (or, for free-text with no code,
    by display with a NULL code). Never resurrects a soft-deleted Condition.
    """
    if condition_id is not None:
        pinned = (
            await db.execute(
                select(Condition).where(Condition.id == condition_id, Condition.is_deleted == False)  # noqa: E712
            )
        ).scalar_one_or_none()
        if pinned is not None and pinned.patient_id == patient_id:
            return pinned

    q = select(Condition).where(Condition.patient_id == patient_id, Condition.is_deleted == False)  # noqa: E712
    if code:
        q = q.where(Condition.code == code)
    else:
        q = q.where(Condition.code.is_(None), Condition.code_display == code_display)
    existing = (await db.execute(q)).scalars().first()
    if existing is not None:
        return existing

    cond = Condition(
        patient_id=patient_id,
        owner_id=owner_id,
        clinical_status="active",
        code=code,
        code_display=code_display,
        recorded_date=recorded_date,
    )
    db.add(cond)
    await db.flush()
    return cond


async def sync_encounter_diagnoses(
    db: AsyncSession,
    encounter: Encounter,
    owner_id: uuid.UUID,
    diagnoses: list[dict],
) -> None:
    """Reconcile a consultation's diagnosis links with the desired set.

    Idempotent: re-running with the same input changes nothing. Links that left
    the set are soft-deleted (the Condition stays); re-adding a diagnosis
    re-activates the existing link instead of inserting a duplicate.
    """
    existing = (
        await db.execute(select(EncounterCondition).where(EncounterCondition.encounter_id == encounter.id))
    ).scalars().all()
    by_condition: dict[uuid.UUID, EncounterCondition] = {link.condition_id: link for link in existing}

    desired: set[uuid.UUID] = set()
    for d in diagnoses:
        code = d.get("cid10_code") or None
        display = d.get("cid10_display") or code or _PLACEHOLDER_DISPLAY
        cond = await resolve_condition(
            db,
            patient_id=encounter.patient_id,
            owner_id=owner_id,
            code=code,
            code_display=display,
            recorded_date=encounter.encounter_date,
            condition_id=d.get("condition_id"),
        )
        desired.add(cond.id)
        link = by_condition.get(cond.id)
        if link is not None:
            link.is_deleted = False
            link.cid10_code = code
            link.cid10_display = d.get("cid10_display")
        else:
            link = EncounterCondition(
                encounter_id=encounter.id,
                condition_id=cond.id,
                cid10_code=code,
                cid10_display=d.get("cid10_display"),
            )
            db.add(link)
            by_condition[cond.id] = link

    for condition_id, link in by_condition.items():
        if condition_id not in desired:
            link.is_deleted = True
    await db.flush()


def backfill_encounter_diagnoses(bind) -> int:
    """Link legacy single-CID consultations to a Condition (migration + tests).

    Runs against any SQLAlchemy connection/session (``bind.execute`` sync API).
    For every non-deleted encounter with a ``cid10_code`` it reuses — or creates —
    the patient's Condition for that code and ensures one link. Returns the number
    of Conditions created. Idempotent: a second run creates nothing.
    """
    rows = bind.execute(
        sa.text(
            "SELECT id, patient_id, owner_id, cid10_code, cid10_display, encounter_date_ts "
            "FROM encounters WHERE cid10_code IS NOT NULL AND is_deleted = FALSE"
        )
    ).fetchall()
    created = 0
    for enc_id, patient_id, owner_id, code, display, encounter_date in rows:
        found = bind.execute(
            sa.text(
                "SELECT id FROM conditions WHERE patient_id = :p AND code = :c AND is_deleted = FALSE LIMIT 1"
            ),
            {"p": patient_id, "c": code},
        ).fetchone()
        if found is not None:
            condition_id = found[0]
        else:
            condition_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO conditions "
                    "(id, owner_id, patient_id, clinical_status, code, code_display, "
                    " recorded_date_ts, is_deleted, created_at, updated_at) "
                    "VALUES (:id, :o, :p, 'active', :c, :d, :rd, FALSE, now(), now())"
                ),
                {
                    "id": condition_id,
                    "o": owner_id,
                    "p": patient_id,
                    "c": code,
                    "d": display or code,
                    "rd": encounter_date,
                },
            )
            created += 1

        link = bind.execute(
            sa.text(
                "SELECT id FROM encounter_conditions WHERE encounter_id = :e AND condition_id = :c"
            ),
            {"e": enc_id, "c": condition_id},
        ).fetchone()
        if link is None:
            bind.execute(
                sa.text(
                    "INSERT INTO encounter_conditions "
                    "(id, encounter_id, condition_id, cid10_code, cid10_display, "
                    " is_deleted, created_at, updated_at) "
                    "VALUES (:id, :e, :c, :code, :display, FALSE, now(), now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "e": enc_id,
                    "c": condition_id,
                    "code": code,
                    "display": display,
                },
            )
    return created
