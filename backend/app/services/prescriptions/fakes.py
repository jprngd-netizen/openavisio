"""Deterministic fake implementation of MemedClient for testing.

``FakeMemedClient`` implements the full ``MemedClient`` protocol without
network access. It records all calls in ``.calls`` for assertion and serves
PDF bytes from memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.prescriptions.ports import (
    DigitalLinkResult,
    MemedClient,
    PrescriberResult,
    ReferenceItem,
)

_FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF\n"


class FakeMemedClient:
    """Deterministic fake Memed client.

    All methods return predictable data based on their inputs. Every call is
    recorded in ``.calls`` as a ``(method_name, kwargs)`` tuple.

    ``download_pdf`` returns valid ``%PDF...`` bytes regardless of the URL.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _record(self, method: str, **kwargs: object) -> None:
        self.calls.append((method, kwargs) if kwargs else (method,))

    # -- cities / specialties -------------------------------------------------

    _CITIES: list[ReferenceItem] = [
        ReferenceItem(id=1, name="São Paulo"),
        ReferenceItem(id=2, name="Rio de Janeiro"),
        ReferenceItem(id=3, name="Belo Horizonte"),
        ReferenceItem(id=4, name="Salvador"),
    ]

    _SPECIALTIES: list[ReferenceItem] = [
        ReferenceItem(id=10, name="Pediatria"),
        ReferenceItem(id=20, name="Cardiologia"),
        ReferenceItem(id=30, name="Clínica Geral"),
        ReferenceItem(id=40, name="Neurologia"),
    ]

    # -- MemedClient implementation -------------------------------------------

    async def check_key(self) -> bool:
        self._record("check_key")
        return True

    async def list_cities(self, q: str | None = None) -> list[ReferenceItem]:
        self._record("list_cities", q=q)
        if q:
            ql = q.lower()
            return [c for c in self._CITIES if ql in c.name.lower()]
        return list(self._CITIES)

    async def list_specialties(self, q: str | None = None) -> list[ReferenceItem]:
        self._record("list_specialties", q=q)
        if q:
            ql = q.lower()
            return [s for s in self._SPECIALTIES if ql in s.name.lower()]
        return list(self._SPECIALTIES)

    async def create_prescriber(self, payload: dict) -> PrescriberResult:
        self._record("create_prescriber", payload=payload)
        return PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_001",
            status="Ativo",
            token="fake-token-001",
        )

    async def get_prescriber(self, external_id: str) -> PrescriberResult:
        self._record("get_prescriber", external_id=external_id)
        return PrescriberResult(
            external_id=external_id,
            memed_user_id="usr_001",
            status="Ativo",
            token="fake-token-001",
        )

    async def get_prescription_pdf_url(
        self, token: str, memed_prescription_id: str
    ) -> str:
        self._record("get_prescription_pdf_url", token=token, memed_prescription_id=memed_prescription_id)
        return f"https://memed.fake.storage/{memed_prescription_id}.pdf"

    async def get_digital_link(
        self, token: str, memed_prescription_id: str
    ) -> DigitalLinkResult:
        self._record("get_digital_link", token=token, memed_prescription_id=memed_prescription_id)
        return DigitalLinkResult(
            link=f"https://memed.fake.com/r/{memed_prescription_id}",
            unlock_code="999999",
        )

    async def download_pdf(self, url: str) -> bytes:
        self._record("download_pdf", url=url)
        return _FAKE_PDF