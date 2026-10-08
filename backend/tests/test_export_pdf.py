"""Impressão de Prontuário (PDF): o registro + os documentos originais anexados.

O endpoint `/patients/{id}/export/pdf` renderiza o prontuário no servidor e
concatena as páginas dos documentos selecionados — o "documento em si" precisa
aparecer no impresso, o que um `window.print()` do navegador não faz com PDFs.
"""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


def _one_page_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=300, height=400)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def _page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(BytesIO(pdf_bytes)).pages)


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_export_pdf_is_a_pdf(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_exp@test.com")
    auth = await _auth(client, "admin_exp@test.com")
    created = await client.post("/api/patients", headers=auth, json={"given_name": "Ana", "family_name": "Lima"})
    pid = created.json()["id"]

    r = await client.get(f"/api/patients/{pid}/export/pdf?sections=", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"
    assert _page_count(r.content) >= 1


async def test_selected_document_pages_are_appended(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_exp2@test.com")
    auth = await _auth(client, "admin_exp2@test.com")
    created = await client.post("/api/patients", headers=auth, json={"given_name": "Rui", "family_name": "Costa"})
    pid = created.json()["id"]

    # baseline: no sections → header only
    base = await client.get(f"/api/patients/{pid}/export/pdf?sections=", headers=auth)
    base_pages = _page_count(base.content)

    # upload one real PDF document
    up = await client.post(
        f"/api/patients/{pid}/documents/upload",
        headers=auth,
        files={"file": ("laudo.pdf", _one_page_pdf(), "application/pdf")},
    )
    assert up.status_code in (200, 201), up.text

    r = await client.get(f"/api/patients/{pid}/export/pdf?sections=documents", headers=auth)
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
    # the document's page(s) are merged in after the record
    assert _page_count(r.content) >= base_pages + 1
