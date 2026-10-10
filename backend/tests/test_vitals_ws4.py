"""WS-4: expanded vitals — plausibility validation + blood-pressure panel.

Covers:
- the new vital codes (respiratory rate, capillary glucose, pain EVA, head
  circumference) persisting through the encounter and observation endpoints;
- server-side plausibility validation (422) on create and update, for both the
  encounter measurements path and the standalone observation path, while lab
  analytes are left untouched;
- systolic/diastolic readings sharing one ``component_group_id``.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

OWNER_EMAIL = "vitals-owner@t.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    owner = User(
        email=OWNER_EMAIL,
        hashed_password=hash_password(PASSWORD),
        role="user",
        is_active=True,
        first_name="V",
        last_name="Owner",
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)
    p = Patient(given_name="Vita", family_name="Test", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(
        PatientAccess(
            patient_id=p.id, user_id=owner.id, access_level="admin", granted_at=datetime.now(UTC)
        )
    )
    await db.commit()
    return owner, p


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_new_vitals_accepted_and_persisted(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    body = {
        "encounter_type": "consulta",
        "encounter_date": "2026-10-09T10:00:00",
        "measurements": [
            {"code": "respiratory-rate", "value_quantity": 18, "value_unit": "/min"},
            {"code": "capillary-glucose", "value_quantity": 96, "value_unit": "mg/dL"},
            {"code": "pain-eva", "value_quantity": 3, "value_unit": "/10"},
            {"code": "head-circumference", "value_quantity": 55, "value_unit": "cm"},
        ],
    }
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text
    codes = {m["code"] for m in r.json()["measurements"]}
    assert codes == {"respiratory-rate", "capillary-glucose", "pain-eva", "head-circumference"}


async def test_bp_components_share_group_id(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    body = {
        "encounter_type": "consulta",
        "encounter_date": "2026-10-09T10:00:00",
        "measurements": [
            {"code": "blood-pressure-systolic", "value_quantity": 128, "value_unit": "mmHg"},
            {"code": "blood-pressure-diastolic", "value_quantity": 82, "value_unit": "mmHg"},
            {"code": "heart-rate", "value_quantity": 72, "value_unit": "bpm"},
        ],
    }
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text
    meas = {m["code"]: m for m in r.json()["measurements"]}
    sys = meas["blood-pressure-systolic"]["component_group_id"]
    dia = meas["blood-pressure-diastolic"]["component_group_id"]
    assert sys is not None
    assert sys == dia  # same panel
    assert meas["heart-rate"]["component_group_id"] is None


async def test_reject_implausible_vitals_on_create(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    bad_ranges = [
        ("body-weight", 0),          # below 0.5 kg
        ("body-height", 10),         # below 20 cm
        ("blood-pressure-systolic", 3000),
        ("blood-pressure-diastolic", 5),
        ("body-temperature", 400),
        ("oxygen-saturation", 150),
        ("heart-rate", 900),
        ("respiratory-rate", 200),
        ("capillary-glucose", 5000),
        ("pain-eva", 11),
        ("head-circumference", 5),
    ]
    for code, value in bad_ranges:
        body = {"encounter_date": "2026-10-09", "measurements": [
            {"code": code, "value_quantity": value}
        ]}
        r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
        assert r.status_code == 422, f"{code}={value} should be rejected, got {r.status_code}: {r.text}"


async def test_boundary_values_accepted(client: AsyncClient, db: AsyncSession):
    """Inclusive bounds: the extremes themselves are plausible."""
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    body = {"encounter_date": "2026-10-09", "measurements": [
        {"code": "body-weight", "value_quantity": 0.5},
        {"code": "body-temperature", "value_quantity": 45},
        {"code": "pain-eva", "value_quantity": 0},
        {"code": "oxygen-saturation", "value_quantity": 100},
    ]}
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text


async def test_reject_implausible_vitals_on_update(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    r = await client.post(
        f"/api/patients/{p.id}/encounters",
        json={"encounter_date": "2026-10-09", "measurements": [
            {"code": "heart-rate", "value_quantity": 72, "value_unit": "bpm"}
        ]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    eid = r.json()["id"]

    r = await client.patch(
        f"/api/encounters/{eid}",
        json={"measurements": [{"code": "body-temperature", "value_quantity": 400}]},
        headers=h,
    )
    assert r.status_code == 422, r.text
    # the valid original set is untouched by the rejected patch
    r = await client.get(f"/api/encounters/{eid}", headers=h)
    assert [m["code"] for m in r.json()["measurements"]] == ["heart-rate"]


async def test_observation_endpoint_validates_vitals(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    # implausible vital → 422
    r = await client.post(
        f"/api/patients/{p.id}/observations",
        json={"category": "measurement", "code": "body-weight", "value_quantity": 1000},
        headers=h,
    )
    assert r.status_code == 422, r.text

    # plausible vital → 201
    r = await client.post(
        f"/api/patients/{p.id}/observations",
        json={"category": "measurement", "code": "respiratory-rate", "value_quantity": 16, "value_unit": "/min"},
        headers=h,
    )
    assert r.status_code == 201, r.text

    # a lab analyte (not a vital) is never range-checked, however large
    r = await client.post(
        f"/api/patients/{p.id}/observations",
        json={"category": "lab", "code_display": "Kreatinin", "value_quantity": 900},
        headers=h,
    )
    assert r.status_code == 201, r.text
