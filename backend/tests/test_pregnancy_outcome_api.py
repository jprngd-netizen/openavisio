"""Pregnancy-outcome (``PregnancyOutcome``) API — registering the outcome that
closes an episode, the adequate terminal status per outcome, newborn data for a
live birth (and only then), patient isolation and the one-outcome invariant
(OB-3 / OB-DEC-3)."""

from __future__ import annotations

import pytest
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


async def _pregnancy(client: AsyncClient, auth: dict, pid: str, lmp: str = "2026-01-01") -> str:
    created = await client.post(
        f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": lmp}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_delivery_outcome_with_newborn_closes_episode(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _admin(db, "admin_outcome_delivery@test.com")
    auth = await _auth(client, "admin_outcome_delivery@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)  # LMP 2026-01-01 -> DPP 2026-10-08

    # No outcome yet.
    assert (
        await client.get(f"/api/patients/{pid}/pregnancies/{preg}/outcome", headers=auth)
    ).status_code == 404

    created = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={
            "outcome_type": "vaginal_delivery",
            "outcome_date": "2026-09-10",
            "newborn_weight_g": 3150,
            "apgar_1": 8,
            "apgar_5": 9,
            "newborn_sex": "female",
            "notes": "parto sem intercorrências",
        },
    )
    assert created.status_code == 201, created.text
    episode = created.json()
    # Registering the outcome CLOSES the episode with the adequate terminal state.
    assert episode["status"] == "completed"
    assert episode["ended_at"] == "2026-09-10"

    outcome = episode["outcome"]
    assert outcome["outcome_type"] == "vaginal_delivery"
    assert outcome["outcome_date"] == "2026-09-10"
    assert outcome["newborn_weight_g"] == 3150
    assert outcome["apgar_1"] == 8
    assert outcome["apgar_5"] == 9
    assert outcome["newborn_sex"] == "female"
    assert outcome["notes"] == "parto sem intercorrências"
    # GA at the OUTCOME date (LMP 2026-01-01 -> 2026-09-10 = 36w0d), not today.
    assert outcome["gestational_age"] == {
        "weeks": 36,
        "days": 0,
        "total_days": 252,
        "as_of": "2026-09-10",
        "basis": "lmp",
    }
    # The episode's own frozen GA agrees with the outcome date.
    assert episode["gestational_age"]["as_of"] == "2026-09-10"

    # Readable on its own route too.
    single = await client.get(f"/api/patients/{pid}/pregnancies/{preg}/outcome", headers=auth)
    assert single.status_code == 200
    assert single.json()["outcome_type"] == "vaginal_delivery"
    assert single.json()["gestational_age"]["as_of"] == "2026-09-10"

    # And exposed in the episode listing (listagem coerente).
    listed = await client.get(f"/api/patients/{pid}/pregnancies", headers=auth)
    assert listed.status_code == 200
    assert listed.json()[0]["outcome"]["outcome_type"] == "vaginal_delivery"
    assert listed.json()[0]["status"] == "completed"


@pytest.mark.parametrize(
    ("outcome_type", "expected_status"),
    [
        ("cesarean_delivery", "completed"),
        ("miscarriage", "miscarriage"),
        ("induced_abortion", "terminated"),
        ("ectopic", "ectopic"),
        ("fetal_death", "fetal_death"),
    ],
)
async def test_loss_and_cesarean_outcomes_map_terminal_status(
    client: AsyncClient, db: AsyncSession, outcome_type: str, expected_status: str
) -> None:
    email = f"admin_outcome_{outcome_type}@test.com"
    await _admin(db, email)
    auth = await _auth(client, email)
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    r = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={"outcome_type": outcome_type, "outcome_date": "2026-05-02"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == expected_status
    assert body["ended_at"] == "2026-05-02"
    # No newborn data is invented for a loss.
    assert body["outcome"]["newborn_weight_g"] is None
    assert body["outcome"]["apgar_1"] is None
    assert body["outcome"]["apgar_5"] is None
    assert body["outcome"]["newborn_sex"] is None

    # The derived GOP counts these correctly (para only for deliveries).
    gop = await client.get(f"/api/patients/{pid}/obstetric-summary", headers=auth)
    assert gop.json()["gravida"] == 1
    assert gop.json()["para"] == (1 if outcome_type == "cesarean_delivery" else 0)


async def test_newborn_data_rejected_for_a_loss(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_outcome_guard@test.com")
    auth = await _auth(client, "admin_outcome_guard@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    r = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={
            "outcome_type": "fetal_death",
            "outcome_date": "2026-06-01",
            "newborn_weight_g": 900,
        },
    )
    assert r.status_code == 422, r.text


async def test_outcome_rejects_cross_patient(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_outcome_iso@test.com")
    auth = await _auth(client, "admin_outcome_iso@test.com")
    pid_a = await _patient(client, auth, "Ana")
    pid_b = await _patient(client, auth, "Bia")
    preg_a = await _pregnancy(client, auth, pid_a)

    # A is the episode's patient; recording under B must be refused (422).
    r = await client.post(
        f"/api/patients/{pid_b}/pregnancies/{preg_a}/outcome",
        headers=auth,
        json={"outcome_type": "miscarriage", "outcome_date": "2026-04-01"},
    )
    assert r.status_code == 422, r.text

    # Nothing leaked and A's episode is still open.
    assert (await client.get(f"/api/patients/{pid_b}/pregnancies", headers=auth)).json() == []
    a = (await client.get(f"/api/patients/{pid_a}/pregnancies", headers=auth)).json()[0]
    assert a["status"] == "active"
    assert a["outcome"] is None


async def test_second_outcome_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_outcome_dup@test.com")
    auth = await _auth(client, "admin_outcome_dup@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    first = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={"outcome_type": "vaginal_delivery", "outcome_date": "2026-09-10"},
    )
    assert first.status_code == 201, first.text

    # A second registration for the same episode is a conflict, not a silent overwrite.
    second = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/outcome",
        headers=auth,
        json={"outcome_type": "cesarean_delivery", "outcome_date": "2026-09-11"},
    )
    assert second.status_code == 409, second.text

    # The first outcome stands unchanged.
    single = await client.get(f"/api/patients/{pid}/pregnancies/{preg}/outcome", headers=auth)
    assert single.json()["outcome_type"] == "vaginal_delivery"
    assert single.json()["outcome_date"] == "2026-09-10"
