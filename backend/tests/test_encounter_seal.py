"""WS-6: author + immutable seal/version of a consultation note.

Covers the seal contract end to end: signing appends an append-only, hashed
version; the hash is recomputable from the stored snapshot; editing the note
does not mutate an existing version; re-signing appends version+1 with a new
hash; and the DTO reports the last seal + whether the note changed since.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.encounter_version import EncounterVersion
from app.models.patient import Patient
from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.models.user import User
from app.services.encounter_seal import content_hash

OWNER_EMAIL = "seal-owner@t.com"
PASSWORD = "Pass1!"


async def _user(db: AsyncSession, email: str) -> User:
    u = User(email=email, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="S", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _setup(db: AsyncSession):
    owner = await _user(db, OWNER_EMAIL)
    p = Patient(given_name="Ana", family_name="Seal", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    # The responsible professional is the Prescriber singleton.
    db.add(Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        external_id=str(PRESCRIBER_SINGLETON_ID),
        given_name="Joana", family_name="Silva",
        board_code="CRM", board_number="123456", board_state="SP",
    ))
    await db.commit()
    return owner, p


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _versions(db: AsyncSession, encounter_id):
    rows = (
        await db.execute(
            select(EncounterVersion)
            .where(EncounterVersion.encounter_id == encounter_id)
            .order_by(EncounterVersion.version)
        )
    ).scalars().all()
    return rows


async def test_sign_creates_immutable_hashed_version(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    r = await client.post(f"/api/patients/{p.id}/encounters", json={
        "encounter_type": "consulta",
        "encounter_date": "2026-10-07T10:30:00",
        "assessment": "cefaleia tensional",
        "plan": "analgésico",
    }, headers=h)
    assert r.status_code == 201, r.text
    enc = r.json()
    eid = enc["id"]
    # WS-6 (1): the note carries the responsible professional + council.
    assert enc["prescriber_id"] == str(PRESCRIBER_SINGLETON_ID)
    assert enc["prescriber_name"] == "Joana Silva"
    assert (enc["board_code"], enc["board_number"], enc["board_state"]) == ("CRM", "123456", "SP")
    # Not signed yet.
    assert enc["last_version"] is None
    assert enc["modified_since_signed"] is False

    # sign → v1
    r = await client.post(f"/api/encounters/{eid}/sign", headers=h)
    assert r.status_code == 200, r.text
    signed = r.json()
    assert signed["last_version"]["version"] == 1
    assert signed["modified_since_signed"] is False
    assert signed["last_version"]["content_hash"]
    # The seal is self-sufficient: it snapshots the council at sign time.
    assert signed["last_version"]["board_number"] == "123456"
    assert signed["last_version"]["professional_name"] == "Joana Silva"

    rows = await _versions(db, eid)
    assert [v.version for v in rows] == [1]
    v1 = rows[0]
    # (5) the hash recomputed from the stored snapshot matches the seal.
    assert v1.content_hash == content_hash(v1.content)
    # and it certifies the note as it read at that moment.
    assert v1.content["assessment"] == "cefaleia tensional"
    assert v1.content["diagnoses"] == []


async def test_edit_does_not_mutate_seal_and_re_sign_versions(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    r = await client.post(f"/api/patients/{p.id}/encounters", json={
        "assessment": "quadro A", "plan": "conduta A",
    }, headers=h)
    eid = r.json()["id"]

    assert (await client.post(f"/api/encounters/{eid}/sign", headers=h)).status_code == 200
    v1 = (await _versions(db, eid))[0]
    v1_hash = v1.content_hash

    # Editing the note after the seal must NOT create or change a version, but
    # the DTO must flag that it drifted from the last seal.
    r = await client.patch(f"/api/encounters/{eid}", json={"assessment": "quadro B"}, headers=h)
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited["last_version"]["version"] == 1
    assert edited["last_version"]["content_hash"] == v1_hash
    assert edited["modified_since_signed"] is True

    rows = await _versions(db, eid)
    assert [v.version for v in rows] == [1]
    assert rows[0].content_hash == v1_hash  # untouched
    assert rows[0].content["assessment"] == "quadro A"  # historical snapshot preserved

    # Re-signing appends v2 with a NEW hash; v1 stays byte-for-byte.
    r = await client.post(f"/api/encounters/{eid}/sign", headers=h)
    assert r.status_code == 200, r.text
    re_signed = r.json()
    assert re_signed["last_version"]["version"] == 2
    assert re_signed["modified_since_signed"] is False
    v2_hash = re_signed["last_version"]["content_hash"]
    assert v2_hash != v1_hash

    rows = await _versions(db, eid)
    assert [v.version for v in rows] == [1, 2]
    assert rows[0].content_hash == v1_hash
    assert rows[1].content_hash == content_hash(rows[1].content)
    assert rows[1].content["assessment"] == "quadro B"


async def test_seal_includes_diagnoses_snapshot(client: AsyncClient, db: AsyncSession):
    """The version seals the diagnoses at sign time (WS-6 depends on WS-3)."""
    _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    r = await client.post(f"/api/patients/{p.id}/encounters", json={
        "assessment": "cefaleia",
        "diagnoses": [{"cid10_code": "G44.2", "cid10_display": "Cefaleia tensional"}],
    }, headers=h)
    eid = r.json()["id"]

    r = await client.post(f"/api/encounters/{eid}/sign", headers=h)
    assert r.status_code == 200, r.text

    v1 = (await _versions(db, eid))[0]
    assert v1.content["diagnoses"] == [
        {"cid10_code": "G44.2", "cid10_display": "Cefaleia tensional"}
    ]
    assert v1.content_hash == content_hash(v1.content)


async def test_sign_requires_contribute_access(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    stranger = await _user(db, "seal-stranger@t.com")
    db.add(PatientAccess(patient_id=p.id, user_id=stranger.id, access_level="view",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    h_owner = await _auth(client, OWNER_EMAIL)
    r = await client.post(f"/api/patients/{p.id}/encounters", json={"assessment": "x"}, headers=h_owner)
    eid = r.json()["id"]

    h_viewer = await _auth(client, "seal-stranger@t.com")
    r = await client.post(f"/api/encounters/{eid}/sign", headers=h_viewer)
    assert r.status_code in (403, 404), r.text
