"""Capa do Prontuário: campos de vínculo empregatício + reveal auditado do CPF.

Os campos de vínculo (bloco B) são colunas novas em `patients` (migration
`m4e5f6a7b8c9`). O CPF continua cifrado em repouso: o DTO só expõe `cpf_last4`,
e o valor completo sai apenas por `GET /patients/{id}/cpf`, que exige acesso e
deixa trilha de auditoria.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.user import User

CPF = "52998224725"


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_employment_fields_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_emp@test.com")
    auth = await _auth(client, "admin_emp@test.com")

    created = await client.post("/api/patients", headers=auth, json={"given_name": "Ana", "family_name": "Lima"})
    assert created.status_code in (200, 201), created.text
    pid = created.json()["id"]

    r = await client.put(
        f"/api/patients/{pid}",
        headers=auth,
        json={
            "registration": "MAT-0042",
            "company": "COPAMAC",
            "contract": "CT-2026-07",
            "job_title": "Técnico de Segurança",
            "admission_date": "2021-03-15",
            "cost_center": "CC-100",
            "work_location": "Macaé",
            "shift": "Diurno",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registration"] == "MAT-0042"
    assert body["company"] == "COPAMAC"
    assert body["job_title"] == "Técnico de Segurança"
    assert body["admission_date"] == "2021-03-15"
    assert body["shift"] == "Diurno"

    # Releitura persiste (o DTO expõe os campos na capa).
    got = await client.get(f"/api/patients/{pid}", headers=auth)
    assert got.status_code == 200, got.text
    assert got.json()["cost_center"] == "CC-100"
    assert got.json()["work_location"] == "Macaé"


async def test_reveal_cpf_is_full_and_audited(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_cpf@test.com")
    auth = await _auth(client, "admin_cpf@test.com")

    created = await client.post(
        "/api/patients", headers=auth, json={"given_name": "Rui", "family_name": "Costa", "cpf": CPF}
    )
    assert created.status_code in (200, 201), created.text
    pid = created.json()["id"]
    assert created.json()["cpf_last4"] == "4725"
    assert "cpf" not in created.json()

    r = await client.get(f"/api/patients/{pid}/cpf", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["cpf"] == CPF

    logs = (
        await db.execute(
            select(AuditLog).where(AuditLog.entity_type == "Patient", AuditLog.action == "revealed")
        )
    ).scalars().all()
    assert logs, "reveal must write an audit entry"
    assert str(pid) == logs[-1].entity_id


async def test_reveal_cpf_404_when_absent(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_nocpf@test.com")
    auth = await _auth(client, "admin_nocpf@test.com")

    created = await client.post("/api/patients", headers=auth, json={"given_name": "Sem", "family_name": "Cpf"})
    assert created.status_code in (200, 201), created.text
    pid = created.json()["id"]

    r = await client.get(f"/api/patients/{pid}/cpf", headers=auth)
    assert r.status_code == 404, r.text
