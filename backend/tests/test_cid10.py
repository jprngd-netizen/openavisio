"""CID-10 catalogue search (diagnosis picker).

Backed by the DATASUS pt-BR dataset shipped at `app/data/cid10.json`
(12,451 subcategory codes). Search matches the code (exact, then prefix) and,
falling back, the description text (accent-insensitive).
"""

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


async def test_cid10_search_by_code(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_cid@test.com")
    auth = await _auth(client, "admin_cid@test.com")

    r = await client.get("/api/cid10/search", headers=auth, params={"q": "I10"})
    assert r.status_code == 200, r.text
    results = r.json()
    assert results and results[0]["code"] == "I10"
    assert "Hipertensão" in results[0]["description"]


async def test_cid10_search_by_description_is_accent_insensitive(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_cid2@test.com")
    auth = await _auth(client, "admin_cid2@test.com")

    # "hipertensao" (no accent) must still find "Hipertensão".
    r = await client.get("/api/cid10/search", headers=auth, params={"q": "hipertensao essencial"})
    assert r.status_code == 200, r.text
    codes = [e["code"] for e in r.json()]
    assert "I10" in codes


async def test_cid10_search_by_code_without_dot(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_cid3@test.com")
    auth = await _auth(client, "admin_cid3@test.com")

    # Codes typed from memory, without the separator dot.
    r = await client.get("/api/cid10/search", headers=auth, params={"q": "F320"})
    assert r.status_code == 200, r.text
    assert r.json() and r.json()[0]["code"] == "F32.0"

    r2 = await client.get("/api/cid10/search", headers=auth, params={"q": "a000"})
    assert r2.status_code == 200, r2.text
    assert r2.json() and r2.json()[0]["code"] == "A00.0"


async def test_cid10_search_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    assert (await client.get("/api/cid10/search", params={"q": "I10"})).status_code == 401
