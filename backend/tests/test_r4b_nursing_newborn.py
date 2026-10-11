"""R4 Fase 1 (itens 3 e 4): FExEO-SUS nursing subcategory + newborn record.

Covers the additive contract for the two workstreams:

* ``NursingCare`` gains ``subcategory`` / ``instrument_type`` / ``structured_data``
  — optional, round-tripping, out-of-vocabulary subcategory → 422.
* ``NewbornRecord`` (1:1 with ``PregnancyOutcome``) — created under a live-birth
  outcome, at-most-one (duplicate → 409), same-patient only (cross-patient → 422),
  newborn data refused for a loss (422), enum-guarded, optional fields default to
  ``None`` and survive a partial PATCH, and the delete round trip.
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

EMAIL = "r4b@test.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    u = User(
        email=EMAIL,
        hashed_password=hash_password(PASSWORD),
        role="user",
        is_active=True,
        first_name="R4",
        last_name="B",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Neonatal", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(
        PatientAccess(
            patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)
        )
    )
    await db.commit()
    return u, p


async def _other_patient(db: AsyncSession, owner: User) -> Patient:
    other = Patient(given_name="Other", family_name="Person", created_by=owner.id)
    db.add(other)
    await db.commit()
    await db.refresh(other)
    db.add(
        PatientAccess(
            patient_id=other.id,
            user_id=owner.id,
            access_level="admin",
            granted_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return other


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _pregnancy(client: AsyncClient, auth: dict, pid, lmp: str = "2026-01-01") -> str:
    r = await client.post(f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": lmp})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _outcome(
    client: AsyncClient, auth: dict, pid, preg: str, outcome_type: str = "vaginal_delivery"
) -> None:
    r = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={"outcome_type": outcome_type, "outcome_date": "2026-10-01"},
    )
    assert r.status_code == 201, r.text


# ----------------------------- NursingCare (item 3) -----------------------------


async def test_nursing_new_fields_optional_and_default_none(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)

    created = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={"occurred_at": "2026-09-01T08:30:00-03:00", "category": "general"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    for field in ("subcategory", "instrument_type", "structured_data"):
        assert body[field] is None, field


async def test_nursing_new_fields_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    structured = {
        "labor_onset": "spontaneous",
        "robson_class": 1,
        "non_pharmacological_methods": ["banheira", "bola"],
        "perineal_laceration_grade": 0,
    }
    payload = {
        "occurred_at": "2026-10-01T05:10:00-03:00",
        "category": "obstetric",
        "pregnancy_id": preg,
        "subcategory": "labor",
        "instrument_type": "fexeo_labor_birth_record",
        "structured_data": structured,
    }
    created = await client.post(f"/api/patients/{p.id}/nursing-care", headers=auth, json=payload)
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    for key, value in payload.items():
        assert created.json()[key] == value, key

    single = await client.get(f"/api/nursing-care/{rid}", headers=auth)
    assert single.status_code == 200, single.text
    assert single.json()["subcategory"] == "labor"
    assert single.json()["structured_data"] == structured

    patched = await client.patch(
        f"/api/nursing-care/{rid}",
        headers=auth,
        json={"subcategory": "postpartum", "instrument_type": "fexeo_postpartum_rooming_record"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["subcategory"] == "postpartum"
    assert patched.json()["structured_data"] == structured  # untouched


async def test_nursing_rejects_invalid_subcategory(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)

    r = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={
            "occurred_at": "2026-09-01T08:30:00-03:00",
            "category": "general",
            "subcategory": "not_a_subcategory",
        },
    )
    assert r.status_code == 422, r.text


# ----------------------------- NewbornRecord (item 4) -----------------------------


async def test_newborn_requires_outcome(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json={},
    )
    assert r.status_code == 404, r.text


async def test_newborn_reluctant_to_non_live_birth(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg, outcome_type="miscarriage")

    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json={},
    )
    assert r.status_code == 422, r.text


async def test_newborn_minimal_create_defaults_none(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg)

    created = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json={},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    for field in (
        "birth_datetime",
        "sex",
        "delivery_type",
        "gestational_age_weeks",
        "classification",
        "apgar_1",
        "apgar_5",
        "apgar_10",
        "weight_g",
        "length_cm",
        "pc_cm",
        "pt_cm",
        "pa_cm",
        "physical_exam",
        "reflexes",
        "feeding",
        "eliminations",
        "hypoglycemia",
        "hypothermia",
        "immunization",
        "congenital_malformation",
        "reanimation",
        "skin_to_skin_1h",
        "cord_clamping",
        "notes",
    ):
        assert body[field] is None, field


async def test_newborn_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg)

    physical_exam = {
        "pele": {"alteracao": False},
        "polo_cefalico": {"fontanela_anterior": "normotensa"},
        "abdome": {"coto_umbilical": "seco"},
        "genitalia": {"testiculos_palpaveis": True},
    }
    payload = {
        "birth_datetime": "2026-10-01T05:05:00-03:00",
        "sex": "F",
        "delivery_type": "vaginal",
        "gestational_age_weeks": 39.5,
        "classification": "AIG",
        "apgar_1": 8,
        "apgar_5": 9,
        "apgar_10": 10,
        "weight_g": 3250,
        "length_cm": 49.5,
        "pc_cm": 34.0,
        "pt_cm": 33.0,
        "pa_cm": 31.0,
        "physical_exam": physical_exam,
        "reflexes": {"succao": "presente", "moro": "presente"},
        "feeding": "leite_materno_livre_demanda",
        "eliminations": {"diurese": "presente", "meconio": "presente"},
        "hypoglycemia": False,
        "hypothermia": True,
        "immunization": {"BCG": True, "HepB": True},
        "congenital_malformation": False,
        "reanimation": {"passos_iniciais": True, "VPP": False},
        "skin_to_skin_1h": True,
        "cord_clamping": "1-3",
        "notes": "RN vigoroso.",
    }
    created = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json=payload,
    )
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    for key, value in payload.items():
        assert created.json()[key] == value, key

    # Read back through the outcome-nested route and the by-id route.
    nested = await client.get(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn", headers=auth
    )
    assert nested.status_code == 200, nested.text
    assert nested.json()["physical_exam"] == physical_exam
    assert nested.json()["gestational_age_weeks"] == 39.5

    single = await client.get(f"/api/newborn-records/{rid}", headers=auth)
    assert single.status_code == 200, single.text
    assert single.json()["apgar_1"] == 8
    assert single.json()["immunization"] == {"BCG": True, "HepB": True}

    # Partial PATCH; a free-text malformation replaces the boolean.
    patched = await client.patch(
        f"/api/newborn-records/{rid}",
        headers=auth,
        json={"congenital_malformation": "labio leporino", "hypothermia": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["congenital_malformation"] == "labio leporino"
    assert patched.json()["hypothermia"] is False
    assert patched.json()["weight_g"] == 3250  # untouched


async def test_newborn_duplicate_is_conflict(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg)

    first = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn", headers=auth, json={}
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn", headers=auth, json={}
    )
    assert second.status_code == 409, second.text


async def test_newborn_cross_patient_is_422(client: AsyncClient, db: AsyncSession) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    other = await _other_patient(db, owner)
    foreign_preg = await _pregnancy(client, auth, other.id)

    # p is the record's patient; citing `other`'s episode is a 422, never a
    # silent cross-patient write.
    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{foreign_preg}/outcome/newborn",
        headers=auth,
        json={},
    )
    assert r.status_code == 422, r.text


async def test_newborn_rejects_invalid_enums(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg)

    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json={"sex": "X"},
    )
    assert r.status_code == 422, r.text

    r2 = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn",
        headers=auth,
        json={"classification": "XYZ"},
    )
    assert r2.status_code == 422, r2.text


async def test_newborn_delete_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    await _outcome(client, auth, p.id, preg)

    rid = (
        await client.post(
            f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn", headers=auth, json={}
        )
    ).json()["id"]

    deleted = await client.delete(f"/api/newborn-records/{rid}", headers=auth)
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"/api/newborn-records/{rid}", headers=auth)).status_code == 404
    # After deletion a fresh record may be opened for the same outcome.
    again = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/outcome/newborn", headers=auth, json={}
    )
    assert again.status_code == 201, again.text
