"""Paciente: CPF cifrado em repouso e contato/endereco persistidos.

`cpf_encrypted`/`cpf_last4` ja existiam no modelo; o que faltava era exposicao
na API. Estes testes garantem que o CPF nao fica em claro no banco e que o DTO
devolve apenas os 4 ultimos digitos (mesmo contrato do prescritor).
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_setting
from app.core.security import hash_password
from app.models.patient import Patient
from app.models.user import User

CPF = "52998224725"


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_create_patient_with_cpf_and_address(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_addr@test.com")
    auth = await _auth(client, "admin_addr@test.com")

    r = await client.post(
        "/api/patients",
        headers=auth,
        json={
            "given_name": "Maria",
            "family_name": "Silva",
            "cpf": CPF,
            "cns": "123456789012345",
            "email": "maria@example.com",
            "phone": "+55 22 99999-0000",
            "cep": "27910-000",
            "street": "Rua das Flores",
            "street_number": "120",
            "complement": "apto 301",
            "district": "Centro",
            "city_name": "Macae",
            "state_code": "RJ",
        },
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()

    # Contrato do DTO: nunca o CPF inteiro.
    assert body["cpf_last4"] == "4725"
    assert "cpf" not in body
    assert body["city_name"] == "Macae"
    assert body["state_code"] == "RJ"
    assert body["cns"] == "123456789012345"

    row = (await db.execute(select(Patient).where(Patient.id == body["id"]))).scalar_one()
    assert row.cpf_encrypted != CPF
    assert CPF not in row.cpf_encrypted
    assert decrypt_setting(row.cpf_encrypted) == CPF
    assert row.cep == "27910-000"


async def test_update_patient_contact_and_address(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_addr2@test.com")
    auth = await _auth(client, "admin_addr2@test.com")

    created = await client.post(
        "/api/patients", headers=auth, json={"given_name": "Joao", "family_name": "Souza"}
    )
    assert created.status_code in (200, 201), created.text
    pid = created.json()["id"]
    # Sem CPF no create: nada de cpf_last4 no DTO.
    assert created.json()["cpf_last4"] is None

    r = await client.put(
        f"/api/patients/{pid}",
        headers=auth,
        json={"city_name": "Campos", "state_code": "RJ", "cpf": "11144477735"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["cpf_last4"] == "7735"
    assert r.json()["city_name"] == "Campos"

    row = (await db.execute(select(Patient).where(Patient.id == pid))).scalar_one()
    assert decrypt_setting(row.cpf_encrypted) == "11144477735"
    assert row.state_code == "RJ"