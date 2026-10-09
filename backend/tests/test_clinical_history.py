"""História clínica (antecedentes): anamnese longitudinal 1:1.

Um registro por paciente (`clinical_histories`, migration `n5f6a7b8c9d0`).
Campos narrativos em texto livre. O PUT faz upsert — recria uma única linha por
paciente. Os antecedentes derivados (diagnósticos/medicações) NÃO são duplicados
aqui: são os próprios recursos `conditions`/`medications`, editáveis na seção.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.clinical_history import ClinicalHistory
from app.models.user import User


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_clinical_history_upsert_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_ch@test.com")
    auth = await _auth(client, "admin_ch@test.com")

    created = await client.post("/api/patients", headers=auth, json={"given_name": "Ivo", "family_name": "Nunes"})
    assert created.status_code in (200, 201), created.text
    pid = created.json()["id"]

    # Nada ainda: GET devolve nulo (a seção renderiza o form vazio).
    empty = await client.get(f"/api/patients/{pid}/clinical-history", headers=auth)
    assert empty.status_code == 200, empty.text
    assert empty.json() is None

    payload = {
        "personal_history": "Hipertensão desde 2015.",
        "family_history": "Pai com cardiopatia.",
        "surgical_history": "Apendicectomia em 2009.",
        "allergies": "Dipirona.",
        "habits": "Ex-tabagista (parou em 2018); etilismo social.",
    }
    first = await client.put(f"/api/patients/{pid}/clinical-history", headers=auth, json=payload)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["allergies"] == "Dipirona."
    assert body["personal_history"] == "Hipertensão desde 2015."

    # Segundo PUT: continua UMA linha (upsert, não duplica).
    payload["allergies"] = "Dipirona; látex."
    second = await client.put(f"/api/patients/{pid}/clinical-history", headers=auth, json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == body["id"]

    n = (await db.execute(
        select(func.count()).select_from(ClinicalHistory).where(ClinicalHistory.patient_id == pid)
    )).scalar_one()
    assert n == 1

    got = await client.get(f"/api/patients/{pid}/clinical-history", headers=auth)
    assert got.status_code == 200, got.text
    assert got.json()["allergies"] == "Dipirona; látex."


async def test_clinical_history_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_ch_auth@test.com")
    auth = await _auth(client, "admin_ch_auth@test.com")
    created = await client.post("/api/patients", headers=auth, json={"given_name": "Zoe", "family_name": "Reis"})
    pid = created.json()["id"]

    assert (await client.get(f"/api/patients/{pid}/clinical-history")).status_code == 401
