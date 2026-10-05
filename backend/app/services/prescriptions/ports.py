"""MemedClient port — Protocol + result dataclasses.

The MemedClient Protocol defines the contract for interacting with the Memed
Sinapse Prescrição API. All secrets (token, unlock_code, CPF) are marked
``field(repr=False)`` so they never appear in logs or error messages.

Domain terms (see CONTEXT.md):
- Prescriber: the licensed healthcare professional authorized to issue prescriptions
- Prescription: a draft or issued medical prescription for a Patient
- PrescriptionDocument: the archived signed PDF of an issued Prescription
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReferenceItem:
    """A reference-data item from Memed (city, specialty)."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class PrescriberResult:
    """Result of creating or fetching a prescriber from Memed.

    ``token`` and ``cpf`` are marked ``repr=False`` to prevent leaking secrets
    in logs, error messages, or debug output.
    """

    external_id: str
    memed_user_id: str
    status: str
    token: str = field(repr=False)
    cpf: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class DigitalLinkResult:
    """Digital prescription link from Memed.

    ``unlock_code`` is marked ``repr=False`` to prevent leaking the unlock code.
    """

    link: str
    unlock_code: str = field(repr=False)


# ---------------------------------------------------------------------------
# MemedClient Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemedClient(Protocol):
    """Port for the Memed Sinapse Prescrição API.

    All methods are async. Implementations must NOT log secrets (token,
    api-key, secret-key, CPF, unlock_code). The ``download_pdf`` method
    is part of this port so that the fake can serve PDF bytes from memory
    without network access.
    """

    async def check_key(self) -> bool:
        """Verify that the API key and secret key are valid.

        Returns True on 200, False on 401/403.
        """
        ...

    async def list_cities(self, q: str | None = None) -> list[ReferenceItem]:
        """Search cities by query string.

        Returns a list of matching ReferenceItem objects.
        """
        ...

    async def list_specialties(self, q: str | None = None) -> list[ReferenceItem]:
        """Search specialties by query string.

        Returns a list of matching ReferenceItem objects.
        """
        ...

    async def create_prescriber(self, payload: dict) -> PrescriberResult:
        """Create a prescriber on Memed.

        ``payload`` is the full JSON:API request body.
        Returns a PrescriberResult with the Memed user id, status, and token.
        """
        ...

    async def get_prescriber(self, external_id: str) -> PrescriberResult:
        """Fetch a prescriber by external_id.

        Returns a PrescriberResult with the current token and status.
        """
        ...

    async def get_prescription_pdf_url(
        self, token: str, memed_prescription_id: str
    ) -> str:
        """Get the signed PDF download URL for a prescription.

        Requires a fresh ``token`` from the prescriber lookup.
        Returns the URL string.
        """
        ...

    async def get_digital_link(
        self, token: str, memed_prescription_id: str
    ) -> DigitalLinkResult:
        """Get the digital prescription link and unlock code.

        Requires a fresh ``token`` from the prescriber lookup.
        Returns a DigitalLinkResult.
        """
        ...

    async def download_pdf(self, url: str) -> bytes:
        """Download raw PDF bytes from a URL.

        Validates that the response contains ``%PDF`` magic bytes.
        Raises ``NonPdfResponseError`` if the content is not a PDF.
        """
        ...