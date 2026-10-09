"""WS-3: multiple diagnoses per consultation, linked to the problem list.

Domain tests for the find-or-create/reconcile service and the migration backfill
that turns the legacy single CID-10 into a Condition + link.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.condition import Condition
from app.models.encounter import Encounter
from app.models.encounter_condition import EncounterCondition
from app.models.patient import Patient
from app.models.user import User
from app.services.encounter_diagnoses import (
    backfill_encounter_diagnoses,
    resolve_condition,
    sync_encounter_diagnoses,
)


async def _setup(db: AsyncSession):
    u = User(email="ws3@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="W", last_name="Three")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Diag", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _conditions(db: AsyncSession, patient_id):
    return (await db.execute(
        select(Condition).where(Condition.patient_id == patient_id, Condition.is_deleted == False)  # noqa: E712
    )).scalars().all()


async def _links(db: AsyncSession, encounter_id):
    return (await db.execute(
        select(EncounterCondition).where(EncounterCondition.encounter_id == encounter_id)
    )).scalars().all()


# --- service: find-or-create -------------------------------------------------


async def test_resolve_condition_finds_or_creates_by_code(db: AsyncSession):
    u, p = await _setup(db)

    first = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code="E11",
                                    code_display="Diabetes mellitus tipo 2")
    second = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code="E11",
                                     code_display="Outro nome")
    assert first.id == second.id  # same code → same problem, name not duplicated

    # free text (no code) dedupes by display
    a = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code=None, code_display="Suspeita clínica")
    b = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code=None, code_display="Suspeita clínica")
    assert a.id == b.id
    assert len(await _conditions(db, p.id)) == 2


async def test_resolve_condition_pins_to_explicit_condition_id(db: AsyncSession):
    u, p = await _setup(db)
    own = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code="I10",
                                  code_display="Hipertensão essencial")
    pinned = await resolve_condition(db, patient_id=p.id, owner_id=u.id, code="IGNORED",
                                     code_display="x", condition_id=own.id)
    assert pinned.id == own.id


# --- service: reconciliation -------------------------------------------------


async def test_sync_is_idempotent_and_never_deletes_a_condition(db: AsyncSession):
    u, p = await _setup(db)
    enc = Encounter(patient_id=p.id, owner_id=u.id, encounter_date=datetime(2026, 10, 1, 12, tzinfo=UTC))
    db.add(enc)
    await db.flush()

    await sync_encounter_diagnoses(db, enc, u.id, [
        {"cid10_code": "E11", "cid10_display": "Diabetes mellitus tipo 2"},
        {"cid10_code": "I10", "cid10_display": "Hipertensão essencial"},
    ])
    await db.commit()
    assert len(await _links(db, enc.id)) == 2
    assert len(await _conditions(db, p.id)) == 2

    # re-running with the same set changes nothing
    await sync_encounter_diagnoses(db, enc, u.id, [
        {"cid10_code": "E11", "cid10_display": "Diabetes mellitus tipo 2"},
        {"cid10_code": "I10", "cid10_display": "Hipertensão essencial"},
    ])
    await db.commit()
    assert len(await _links(db, enc.id)) == 2

    # drop I10 from the consultation: the link goes, the Condition stays
    await sync_encounter_diagnoses(db, enc, u.id, [
        {"cid10_code": "E11", "cid10_display": "Diabetes mellitus tipo 2"},
    ])
    await db.commit()
    active = await _links(db, enc.id)
    assert [lnk.cid10_code for lnk in active if not lnk.is_deleted] == ["E11"]
    assert len(await _conditions(db, p.id)) == 2  # problem list intact

    # re-add I10: the soft-deleted link is reactivated, not duplicated
    await sync_encounter_diagnoses(db, enc, u.id, [
        {"cid10_code": "E11", "cid10_display": "Diabetes mellitus tipo 2"},
        {"cid10_code": "I10", "cid10_display": "Hipertensão essencial"},
    ])
    await db.commit()
    active = [lnk for lnk in await _links(db, enc.id) if not lnk.is_deleted]
    assert {lnk.cid10_code for lnk in active} == {"E11", "I10"}
    assert len(await _links(db, enc.id)) == 2  # no duplicate rows


# --- migration backfill ------------------------------------------------------


async def test_backfill_links_legacy_cid_and_reuses_condition(db: AsyncSession):
    u, p = await _setup(db)
    # a problem that already exists for one code — the backfill must reuse it
    existing = Condition(patient_id=p.id, owner_id=u.id, clinical_status="active",
                         code="J45", code_display="Asma")
    db.add(existing)
    enc_a = Encounter(patient_id=p.id, owner_id=u.id, encounter_date=datetime(2026, 9, 1, tzinfo=UTC),
                      cid10_code="J45", cid10_display="Asma")
    enc_b = Encounter(patient_id=p.id, owner_id=u.id, encounter_date=datetime(2026, 9, 2, tzinfo=UTC),
                      cid10_code="G44.2", cid10_display="Cefaleia tensional")
    db.add_all([enc_a, enc_b])
    await db.commit()

    created = await db.run_sync(lambda s: backfill_encounter_diagnoses(s))
    await db.commit()
    assert created == 1  # only G44.2 was new; J45 reused

    links = (await db.execute(select(EncounterCondition))).scalars().all()
    assert len(links) == 2
    codes = {lnk.cid10_code for lnk in links}
    assert codes == {"J45", "G44.2"}
    # the pre-existing condition was reused, not duplicated
    assert len([c for c in await _conditions(db, p.id) if c.code == "J45"]) == 1

    # idempotent: a second run adds nothing
    again = await db.run_sync(lambda s: backfill_encounter_diagnoses(s))
    await db.commit()
    assert again == 0
    assert len((await db.execute(select(EncounterCondition))).scalars().all()) == 2
