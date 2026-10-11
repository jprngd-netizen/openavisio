"""R4 Fase 3: FExEO routing in ``POST /documents/{id}/verify``.

A document classified as an obstetric-nursing instrument is routed to the
matching clinical records — ``Pregnancy`` / ``PregnancyVisit`` / ``NursingCare``
/ ``NewbornRecord`` / ``PregnancyOutcome`` — with provenance so a re-verify
retracts only what this document created; the formative competency assessment
materialises nothing clinical, and every other document type is unchanged.

OCR values are suggestions: unknown keys and unparseable values are dropped
(never a 500).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.document import DocumentReference
from app.models.newborn_record import NewbornRecord
from app.models.nursing_care import NursingCare
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.pregnancy import Pregnancy, PregnancyOutcome, PregnancyVisit
from app.models.user import User

EMAIL = "r4e@test.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    u = User(email=EMAIL, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="R4", last_name="E")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Obstetrica", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    # verify ends in _reveal(), which needs the patient KEK — a keyless patient 500s
    from app.core.patient_keys import ensure_patient_kek
    await ensure_patient_kek(db, p.id)
    await db.commit()
    return u, p


async def _doc(db: AsyncSession, user: User, patient: Patient, classification: str,
               issued: str = "2026-10-01") -> DocumentReference:
    d = DocumentReference(patient_id=patient.id, owner_id=user.id,
                          file_name=f"{classification}.pdf",
                          issued_date=date.fromisoformat(issued),
                          processing_status="extracted", verification_status="extracted",
                          document_classification=classification)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _verify(client: AsyncClient, auth: dict, doc_id, *, fexeo=None, **extra) -> None:
    body: dict = dict(extra)
    body["fexeo"] = fexeo
    r = await client.post(f"/api/documents/{doc_id}/verify", json=body, headers=auth)
    assert r.status_code == 200, r.text


async def _live(db: AsyncSession, model, **where):
    conds = [model.is_deleted == False]  # noqa: E712
    conds += [getattr(model, key) == value for key, value in where.items()]
    rows = await db.execute(select(model).where(*conds))
    return list(rows.scalars().all())


# --------------------------------- Pré-natal ---------------------------------


async def test_prenatal_creates_pregnancy_and_visit(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "fexeo_prenatal_monitoring")

    await _verify(client, h, doc.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01", "risk_classification": "alto",
                      "bogus_key": "ignored"},
        "prenatal_visit": {"fundal_height_cm": 24.5, "complaints": ["náusea", "cólicas"],
                           "unknown_key": "drop-me"},
    })

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    assert len(pregnancies) == 1
    assert pregnancies[0].risk_classification == "alto"
    assert pregnancies[0].lmp_date == date(2026, 1, 1)

    visits = await _live(db, PregnancyVisit, pregnancy_id=pregnancies[0].id)
    assert len(visits) == 1
    visit = visits[0]
    assert float(visit.fundal_height_cm) == 24.5
    assert visit.complaints == ["náusea", "cólicas"]
    # Provenance: this document created the visit → a re-verify may retract it.
    assert visit.document_reference_id == doc.id

    # API round trip keeps working.
    r = await client.get(f"/api/patients/{p.id}/pregnancies", headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


async def test_prenatal_visit_dedupe_fills_only_empty(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc1 = await _doc(db, u, p, "fexeo_prenatal_monitoring")
    await _verify(client, h, doc1.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "prenatal_visit": {"visit_date": "2026-03-01", "fetal_heart_rate_bpm": 140,
                           "notes": "primeira"},
    })

    # A second document of the same gestation, same visit date.
    doc2 = await _doc(db, u, p, "fexeo_prenatal_monitoring", issued="2026-03-01")
    await _verify(client, h, doc2.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "prenatal_visit": {"visit_date": "2026-03-01", "fundal_height_cm": 25.0,
                           "notes": "should-not-overwrite"},
    })

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    assert len(pregnancies) == 1
    visits = await _live(db, PregnancyVisit, pregnancy_id=pregnancies[0].id)
    assert len(visits) == 1, "same (pregnancy, visit_date) must dedupe"
    visit = visits[0]
    assert visit.fetal_heart_rate_bpm == 140, "existing data is never overwritten"
    assert visit.notes == "primeira"
    assert float(visit.fundal_height_cm) == 25.0, "empty field gets filled"
    assert visit.document_reference_id == doc1.id, "provenance stays with the creator"


# --------------------------- Parto / nascimento ---------------------------


async def test_labor_creates_nursing_outcome_newborn(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "fexeo_labor_birth_record")

    await _verify(client, h, doc.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "nursing_care": {"subcategory": "labor", "structured_data": {"robson_class": 1}},
        "outcome": {"outcome_type": "vaginal_delivery", "outcome_date": "2026-10-01"},
        "newborn": {"apgar_1": 8, "apgar_5": 9, "weight_g": 3200, "sex": "F"},
    })

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    assert len(pregnancies) == 1
    assert pregnancies[0].status == "completed"
    assert pregnancies[0].ended_at == date(2026, 10, 1)

    outcomes = await _live(db, PregnancyOutcome, pregnancy_id=pregnancies[0].id)
    assert len(outcomes) == 1
    assert outcomes[0].outcome_type == "vaginal_delivery"
    assert outcomes[0].document_reference_id == doc.id

    nursing = await _live(db, NursingCare, patient_id=p.id)
    assert len(nursing) == 1
    assert nursing[0].subcategory == "labor"
    assert nursing[0].category == "obstetric"
    assert nursing[0].structured_data == {"robson_class": 1}
    assert nursing[0].document_reference_id == doc.id

    newborns = await _live(db, NewbornRecord, pregnancy_outcome_id=outcomes[0].id)
    assert len(newborns) == 1
    assert newborns[0].apgar_1 == 8
    assert newborns[0].weight_g == 3200
    assert newborns[0].sex == "F"
    assert newborns[0].document_reference_id == doc.id


async def test_labor_loss_does_not_create_newborn(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "fexeo_labor_birth_record")

    await _verify(client, h, doc.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "nursing_care": {"subcategory": "labor"},
        "outcome": {"outcome_type": "miscarriage", "outcome_date": "2026-02-01"},
        "newborn": {"apgar_1": 8},  # spurious; a loss never carries RN data
    })

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    assert pregnancies[0].status == "miscarriage"
    outcomes = await _live(db, PregnancyOutcome, pregnancy_id=pregnancies[0].id)
    assert len(outcomes) == 1
    assert await _live(db, NewbornRecord, pregnancy_outcome_id=outcomes[0].id) == []


# --------------------------------- Pós-parto ---------------------------------


async def test_postpartum_merges_into_existing_newborn(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    labor = await _doc(db, u, p, "fexeo_labor_birth_record")
    await _verify(client, h, labor.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "nursing_care": {"subcategory": "labor"},
        "outcome": {"outcome_type": "vaginal_delivery", "outcome_date": "2026-10-01"},
        "newborn": {"apgar_1": 8, "weight_g": 3200},
    })

    pp = await _doc(db, u, p, "fexeo_postpartum_rooming_record", issued="2026-10-02")
    await _verify(client, h, pp.id, fexeo={
        "nursing_care": {"subcategory": "postpartum"},
        "newborn": {"physical_exam": {"pele": {"alteracao": False}}, "feeding": "livre_demanda"},
    })

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    outcomes = await _live(db, PregnancyOutcome, pregnancy_id=pregnancies[0].id)
    newborns = await _live(db, NewbornRecord, pregnancy_outcome_id=outcomes[0].id)
    assert len(newborns) == 1, "the postpartum record merges, never duplicates"
    assert newborns[0].apgar_1 == 8, "labor data preserved"
    assert newborns[0].physical_exam == {"pele": {"alteracao": False}}
    assert newborns[0].feeding == "livre_demanda"

    nursing = await _live(db, NursingCare, patient_id=p.id)
    assert len(nursing) == 2
    assert {n.subcategory for n in nursing} == {"labor", "postpartum"}


# ---------------------------- Saúde sexual ----------------------------


async def test_sexual_reproductive_creates_nursing_only(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "fexeo_sexual_reproductive_visit")

    await _verify(client, h, doc.id, fexeo={
        "nursing_care": {"subcategory": "sexual_reproductive",
                         "structured_data": {"identidade_genero": "mulher_cis"}},
    })

    nursing = await _live(db, NursingCare, patient_id=p.id)
    assert len(nursing) == 1
    assert nursing[0].subcategory == "sexual_reproductive"
    assert nursing[0].category == "general"
    assert nursing[0].pregnancy_id is None
    assert nursing[0].structured_data == {"identidade_genero": "mulher_cis"}
    assert nursing[0].document_reference_id == doc.id
    assert await _live(db, Pregnancy, patient_id=p.id) == []


# ------------------------- Formativo (Parte II) -------------------------


async def test_competency_materializes_nothing(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "fexeo_competency_assessment")

    await _verify(
        client, h, doc.id,
        fexeo={"pregnancy": {"lmp_date": "2026-01-01"},
               "nursing_care": {"subcategory": "labor"},
               "newborn": {"apgar_1": 8}},
        observations=[{"type": "PA", "value": "120/80"}],
        diagnoses=[{"name": "Hipertensão"}],
        medications=[{"name": "Metildopa"}],
    )

    assert await _live(db, Pregnancy, patient_id=p.id) == []
    assert await _live(db, PregnancyVisit) == []
    assert await _live(db, NursingCare, patient_id=p.id) == []
    assert await _live(db, NewbornRecord) == []
    assert await _live(db, Observation, patient_id=p.id) == []

    refreshed = await db.get(DocumentReference, doc.id)
    assert refreshed.verification_status == "verified"


# --------------------------- Não-FExEO: inalterado ---------------------------


async def test_non_fexeo_classification_is_unchanged(client: AsyncClient, db: AsyncSession) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "lab_report")

    await _verify(
        client, h, doc.id,
        observations=[{"type": "Hemoglobina", "value": "13.5", "unit": "g/dL"}],
        fexeo={"pregnancy": {"lmp_date": "2026-01-01"}},  # present but ignored
    )

    obs = await _live(db, Observation, patient_id=p.id)
    assert len(obs) == 1
    assert obs[0].document_reference_id == doc.id
    # The generic path never routes FExEO records for a non-FExEO classification.
    assert await _live(db, Pregnancy, patient_id=p.id) == []
    assert await _live(db, NursingCare, patient_id=p.id) == []


# ------------------------- Idempotência / retração -------------------------


async def test_reverify_idempotent_and_scoped_to_own_document(
    client: AsyncClient, db: AsyncSession
) -> None:
    u, p = await _setup(db)
    h = await _auth(client)
    doc_x = await _doc(db, u, p, "fexeo_labor_birth_record")
    fexeo = {
        "pregnancy": {"lmp_date": "2026-01-01"},
        "nursing_care": {"subcategory": "labor"},
        "outcome": {"outcome_type": "vaginal_delivery", "outcome_date": "2026-10-01"},
        "newborn": {"apgar_1": 8},
    }
    await _verify(client, h, doc_x.id, fexeo=fexeo)

    # A second document on the same patient creates its own record.
    doc_y = await _doc(db, u, p, "fexeo_prenatal_monitoring", issued="2026-03-01")
    await _verify(client, h, doc_y.id, fexeo={
        "pregnancy": {"lmp_date": "2026-01-01"},
        "prenatal_visit": {"visit_date": "2026-03-01", "fetal_heart_rate_bpm": 140},
    })

    # Re-verify doc X: its own records are retracted and rebuilt — never a
    # duplicate, never a crash — and doc Y's record is untouched.
    await _verify(client, h, doc_x.id, fexeo=fexeo)

    pregnancies = await _live(db, Pregnancy, patient_id=p.id)
    assert len(pregnancies) == 1
    outcomes = await _live(db, PregnancyOutcome, pregnancy_id=pregnancies[0].id)
    assert len(outcomes) == 1, "the outcome is rebuilt, not duplicated"
    assert len(await _live(db, NewbornRecord, pregnancy_outcome_id=outcomes[0].id)) == 1
    assert len(await _live(db, NursingCare, patient_id=p.id)) == 1
    assert len(await _live(db, PregnancyVisit, pregnancy_id=pregnancies[0].id)) == 1

    # doc Y's visit survived doc X's re-verify — never retract another doc's data.
    y_visits = await _live(db, PregnancyVisit, document_reference_id=doc_y.id)
    assert len(y_visits) == 1
    assert y_visits[0].is_deleted is False
    assert y_visits[0].fetal_heart_rate_bpm == 140

    # The retraction is scoped: everything still live came from the latest verify.
    assert all(o.document_reference_id == doc_x.id for o in outcomes)
    assert not any(v.is_deleted for v in y_visits)
