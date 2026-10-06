"""HTTP implementation of the MemedClient port.

Uses ``httpx.AsyncClient`` with query-string authentication
(``api-key`` / ``secret-key``). Suppresses ``httpx`` and ``httpcore``
loggers to ``WARNING`` to prevent leaking secrets in DEBUG-level logs.
"""
from __future__ import annotations

import logging
from typing import Self
from urllib.parse import urlparse

import httpx

from app.services.prescriptions.ports import (
    DigitalLinkResult,
    MemedClient,
    PrescriberResult,
    ReferenceItem,
)

# Suppress httpx/httpcore DEBUG logging — they would log the full URL
# including query params (api-key, secret-key, token).
_logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class NonPdfResponseError(RuntimeError):
    """Raised when ``download_pdf`` receives content that is not a PDF."""


class MemedHTTPClient:
    """HTTP client for the Memed Sinapse Prescrição API.

    Every request includes ``?api-key=...&secret-key=...`` in the query string.
    Methods that require a ``token`` parameter add it as an additional query param.

    Parameters
    ----------
    api_url:
        Base URL for the Memed API (e.g. ``https://api.memed.com.br``).
    api_key:
        Memed API key.
    secret_key:
        Memed secret key.
    _client_override:
        Internal — used by tests to inject an ``httpx.AsyncClient`` with
        ``MockTransport``. Not for production use.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        secret_key: str,
        _client_override: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._secret_key = secret_key

        if _client_override is not None:
            self._client = _client_override
        else:
            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )

    # -- internal helpers -----------------------------------------------------

    def _auth_params(self) -> dict[str, str]:
        """Return the authentication query params for every request."""
        return {"api-key": self._api_key, "secret-key": self._secret_key}

    async def _get(
        self, path: str, extra_params: dict[str, str] | None = None
    ) -> httpx.Response:
        """Perform a GET with auth params and optional extra params."""
        params = self._auth_params()
        if extra_params:
            params.update(extra_params)
        url = f"{self._api_url}{path}"
        _logger.debug("Memed GET %s", path)  # path only, never full URL
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response

    async def _post(
        self, path: str, json_body: dict | None = None
    ) -> httpx.Response:
        """Perform a POST with auth params and optional JSON body."""
        params = self._auth_params()
        url = f"{self._api_url}{path}"
        _logger.debug("Memed POST %s", path)  # path only, never full URL
        response = await self._client.post(url, params=params, json=json_body)
        response.raise_for_status()
        return response

    @staticmethod
    def _parse_json_api_prescriber(data: dict) -> PrescriberResult:
        """Parse a JSON:API prescriber response into a PrescriberResult."""
        attrs = data["data"]["attributes"]
        return PrescriberResult(
            external_id=attrs.get("external_id", ""),
            memed_user_id=data["data"]["id"],
            status=attrs.get("status", ""),
            token=attrs.get("token", ""),
            cpf=attrs.get("cpf"),
        )

    @staticmethod
    def _parse_reference_list(data: dict) -> list[ReferenceItem]:
        """Parse a JSON:API list response into ReferenceItem list."""
        items: list[ReferenceItem] = []
        for entry in data.get("data", []):
            items.append(ReferenceItem(id=entry["id"], name=entry.get("nome", "")))
        return items

    # -- MemedClient implementation -------------------------------------------

    async def check_key(self) -> bool:
        """Verify API credentials.

        Returns True on HTTP 200, False on 401/403.
        """
        try:
            await self._get("/sinapse-prescricao/check-key")
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                return False
            raise

    async def list_cities(self, q: str | None = None) -> list[ReferenceItem]:
        """Search cities by name."""
        params = {"q": q} if q else None
        response = await self._get("/cidades", extra_params=params)
        return self._parse_reference_list(response.json())

    async def list_specialties(self, q: str | None = None) -> list[ReferenceItem]:
        """Search specialties by name."""
        params = {"q": q} if q else None
        response = await self._get("/especialidades", extra_params=params)
        return self._parse_reference_list(response.json())

    async def create_prescriber(self, payload: dict) -> PrescriberResult:
        """Create a prescriber on Memed.

        ``payload`` is the full JSON:API request body.
        """
        response = await self._post("/sinapse-prescricao/usuarios", json_body=payload)
        return self._parse_json_api_prescriber(response.json())

    async def get_prescriber(self, external_id: str) -> PrescriberResult:
        """Fetch a prescriber by external_id.

        Raises:
            LookupError: if the prescriber is not found on Memed (HTTP 404).
            httpx.HTTPStatusError: on any other HTTP error.
        """
        try:
            response = await self._get(f"/sinapse-prescricao/usuarios/{external_id}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise LookupError("Prescriber not found on Memed") from exc
            raise
        return self._parse_json_api_prescriber(response.json())

    async def get_prescription_pdf_url(
        self, token: str, memed_prescription_id: str
    ) -> str:
        """Get the signed PDF download URL."""
        response = await self._get(
            f"/prescricoes/{memed_prescription_id}/url-document/full",
            extra_params={"token": token},
        )
        data = response.json()
        return data["url"]

    async def get_digital_link(
        self, token: str, memed_prescription_id: str
    ) -> DigitalLinkResult:
        """Get the digital prescription link and unlock code."""
        response = await self._get(
            f"/prescricoes/{memed_prescription_id}/get-digital-prescription-link",
            extra_params={"token": token},
        )
        data = response.json()
        return DigitalLinkResult(
            link=data["link"],
            unlock_code=data.get("codigo_desbloqueio", ""),
        )

    async def download_pdf(self, url: str) -> bytes:
        """Download raw PDF bytes from a URL.

        Accepts ``application/pdf`` or ``application/octet-stream`` content types.
        Validates the ``%PDF`` magic bytes and raises ``NonPdfResponseError``
        if they are missing.

        Uses the instance's ``_client`` (which may be a ``MockTransport`` in tests).
        The URL is absolute so ``base_url`` is not applied.
        """
        _parsed = urlparse(url)
        _logger.debug("Downloading PDF from %s://%s%s", _parsed.scheme, _parsed.netloc, _parsed.path)
        response = await self._client.get(url, params=None)
        response.raise_for_status()
        data = response.content

        if not data.startswith(b"%PDF"):
            raise NonPdfResponseError(
                f"Response content does not start with %PDF magic bytes "
                f"(content-type={response.headers.get('content-type')}, "
                f"first_bytes={data[:20]!r})"
            )
        return data

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()