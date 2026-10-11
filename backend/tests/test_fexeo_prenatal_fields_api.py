"""FExEO-SUS prenatal structured fields on ``Pregnancy`` / ``PregnancyVisit``
(R4 Fase 1, instrumento I.1).

Covers the additive contract: every new field is optional, round-trips through
create/read/update, defaults to ``None`` when omitted (so existing payloads are
untouched), and rejects an out-of-vocabulary value (422)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: AsyncClient, auth: dict, name: str = "Ana") -> str:
    created = await client.post(
        "/api/patients", headers=auth, json={"given_name": name, "family_name": "Alves"}
    )
    assert created.status_code in (200, 201), created.text
    return created.json()["id"]


async def test_pregnancy_new_fields_are_optional_and_default_none(
    client: AsyncClient, db: AsyncSession
) -> None:
    """An episode created with only the legacy payload reads the new fields as None."""
    await _admin(db, "admin_fexeo_opt@test.com")
    auth = await _auth(client, "admin_fexeo_opt@test.com")
    pid = await _patient(client, auth)

    created = await client.post(
        f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": "2026-01-01"}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    for field in (
        "risk_classification",
        "planned_pregnancy",
        "contraceptive_at_conception",
        "gravida",
        "para_vaginal",
        "para_cesarean",
        "abortions",
        "living_children",
        "preeclampsia_risk_factors",
        "preeclampsia_moderate_risk_factors",
        "aspirin_prophylaxis",
        "aspirin_start_week",
        "imc_pre_gestational_class",
        "perinatal_mental_health_history",
        "domestic_violence_investigated",
        "family_history",
        "reference_maternity",
        "linked_to_maternity",
    ):
        assert body[field] is None, field


async def test_pregnancy_fexeo_fields_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fexeo_preg@test.com")
    auth = await _auth(client, "admin_fexeo_preg@test.com")
    pid = await _patient(client, auth)

    payload = {
        "lmp_date": "2026-01-01",
        "risk_classification": "alto",
        "planned_pregnancy": False,
        "contraceptive_at_conception": "oral",
        "gravida": 3,
        "para_vaginal": 1,
        "para_cesarean": 1,
        "abortions": 0,
        "living_children": 2,
        "preeclampsia_risk_factors": ["hipertensao_cronica", "obesidade"],
        "preeclampsia_moderate_risk_factors": ["nuliparidade", "idade_maior_35"],
        "aspirin_prophylaxis": True,
        "aspirin_start_week": 13,
        "imc_pre_gestational_class": "sobrepeso",
        "perinatal_mental_health_history": True,
        "domestic_violence_investigated": True,
        "family_history": {"diabetes": True, "hipertensao": False, "gemelar": True},
        "reference_maternity": "Maternidade Central",
        "linked_to_maternity": True,
    }
    created = await client.post(f"/api/patients/{pid}/pregnancies", headers=auth, json=payload)
    assert created.status_code == 201, created.text
    preg = created.json()["id"]
    for key, value in payload.items():
        assert created.json()[key] == value, key

    # Read-back through the single-episode endpoint.
    single = await client.get(f"/api/pregnancies/{preg}", headers=auth)
    assert single.status_code == 200, single.text
    assert single.json()["risk_classification"] == "alto"
    assert single.json()["preeclampsia_risk_factors"] == ["hipertensao_cronica", "obesidade"]
    assert single.json()["family_history"] == {
        "diabetes": True,
        "hipertensao": False,
        "gemelar": True,
    }

    # Partial update via PATCH; untouched fields survive.
    patched = await client.patch(
        f"/api/pregnancies/{preg}",
        headers=auth,
        json={"risk_classification": "intermediario", "aspirin_start_week": 16},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["risk_classification"] == "intermediario"
    assert patched.json()["aspirin_start_week"] == 16
    assert patched.json()["gravida"] == 3  # untouched


async def test_pregnancy_rejects_invalid_risk_classification(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _admin(db, "admin_fexeo_bad@test.com")
    auth = await _auth(client, "admin_fexeo_bad@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/pregnancies",
        headers=auth,
        json={"lmp_date": "2026-01-01", "risk_classification": "not_a_class"},
    )
    assert r.status_code == 422, r.text

    r2 = await client.post(
        f"/api/patients/{pid}/pregnancies",
        headers=auth,
        json={"lmp_date": "2026-01-02", "imc_pre_gestational_class": "obeso"},
    )
    assert r2.status_code == 422, r2.text


async def test_visit_new_fields_are_optional_and_default_none(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _admin(db, "admin_fexeo_vopt@test.com")
    auth = await _auth(client, "admin_fexeo_vopt@test.com")
    pid = await _patient(client, auth)
    preg = (
        await client.post(
            f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": "2026-01-01"}
        )
    ).json()["id"]

    created = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/visits",
        headers=auth,
        json={"visit_date": "2026-03-12"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    for field in (
        "consultation_type",
        "first_visit_before_12w",
        "main_care_provider",
        "remote_consult",
        "dental_health_activity",
        "complaints",
        "warning_signs",
        "current_intercurrences",
        "edema_class",
        "leopold_done",
        "fundal_height_recorded_on_chart",
        "bcf_change",
        "physical_exam",
        "vaccination_status",
        "vaccines_in_gestation",
        "orientation_topics",
        "weight_gain_weekly_ok",
        "birth_plan_elaborated",
    ):
        assert body[field] is None, field


async def test_visit_fexeo_fields_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fexeo_visit@test.com")
    auth = await _auth(client, "admin_fexeo_visit@test.com")
    pid = await _patient(client, auth)
    preg = (
        await client.post(
            f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": "2026-01-01"}
        )
    ).json()["id"]

    physical_exam = {
        "pele_mucosas": {"avaliado": True, "alteracao": False},
        "tireoide": {"avaliado": True, "alteracao": False},
        "mamas": {"avaliado": True, "alteracao": True},
        "ausculta_cardiaca": {"avaliado": True, "alteracao": False},
        "ausculta_pulmonar": {"avaliado": True, "alteracao": False},
    }
    payload = {
        "visit_date": "2026-03-12",
        "consultation_type": "primeira",
        "first_visit_before_12w": True,
        "main_care_provider": "enfermeiro",
        "remote_consult": False,
        "dental_health_activity": True,
        "complaints": ["nauseas", "azia"],
        "warning_signs": ["cefaleia"],
        "current_intercurrences": [{"code": "O24.4", "display": "DMG"}],
        "edema_class": "++",
        "leopold_done": True,
        "fundal_height_recorded_on_chart": True,
        "bcf_change": False,
        "physical_exam": physical_exam,
        "vaccination_status": {"hepatite_b": "completo", "antitetanica": "completo"},
        "vaccines_in_gestation": {"dTpa": True, "dT": False, "VSR": False, "covid": True, "influenza": True},
        "orientation_topics": ["aleitamento", "sinais_de_alerta"],
        "weight_gain_weekly_ok": True,
        "birth_plan_elaborated": True,
    }
    created = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/visits", headers=auth, json=payload
    )
    assert created.status_code == 201, created.text
    vid = created.json()["id"]
    for key, value in payload.items():
        assert created.json()[key] == value, key

    single = await client.get(f"/api/pregnancy-visits/{vid}", headers=auth)
    assert single.status_code == 200, single.text
    assert single.json()["edema_class"] == "++"
    assert single.json()["physical_exam"] == physical_exam
    assert single.json()["vaccines_in_gestation"]["dTpa"] is True

    patched = await client.patch(
        f"/api/pregnancy-visits/{vid}",
        headers=auth,
        json={"edema_class": "ausente", "consultation_type": "subsequente"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["edema_class"] == "ausente"
    assert patched.json()["consultation_type"] == "subsequente"
    assert patched.json()["leopold_done"] is True  # untouched


async def test_visit_rejects_invalid_edema_class(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fexeo_vbad@test.com")
    auth = await _auth(client, "admin_fexeo_vbad@test.com")
    pid = await _patient(client, auth)
    preg = (
        await client.post(
            f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": "2026-01-01"}
        )
    ).json()["id"]

    r = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/visits",
        headers=auth,
        json={"visit_date": "2026-03-12", "edema_class": "muito"},
    )
    assert r.status_code == 422, r.text