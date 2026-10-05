"""Tests for the MemedClient port, HTTP implementation, and fake.

All tests use httpx.MockTransport — never touch the network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.prescriptions.fakes import FakeMemedClient
from app.services.prescriptions.memed_client import (
    MemedHTTPClient,
    NonPdfResponseError,
)
from app.services.prescriptions.ports import (
    DigitalLinkResult,
    MemedClient,
    PrescriberResult,
    ReferenceItem,
)


# ---------------------------------------------------------------------------
# repr / log redaction
# ---------------------------------------------------------------------------


class TestReprRedaction:
    """Secrets must never appear in repr()."""

    def test_prescriber_result_repr_hides_token(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token="super-secret-token-42",
        )
        r = repr(result)
        assert "super-secret-token-42" not in r
        assert "token" not in r or "token=" not in r

    def test_digital_link_result_repr_hides_unlock_code(self):
        result = DigitalLinkResult(
            link="https://memed.com/r/abc",
            unlock_code="123456",
        )
        r = repr(result)
        assert "123456" not in r
        assert "unlock_code" not in r or "unlock_code=" not in r

    def test_prescriber_result_repr_hides_cpf(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token="tok_xxx",
            cpf="12345678901",
        )
        r = repr(result)
        assert "12345678901" not in r
        assert "cpf" not in r or "cpf=" not in r


# ---------------------------------------------------------------------------
# FakeMemedClient
# ---------------------------------------------------------------------------


class TestFakeMemedClient:
    """Deterministic fake — no network, records calls."""

    async def test_check_key_returns_true(self):
        fake = FakeMemedClient()
        assert await fake.check_key() is True

    async def test_list_cities_returns_items(self):
        fake = FakeMemedClient()
        cities = await fake.list_cities(q="São")
        assert len(cities) > 0
        assert all(isinstance(c, ReferenceItem) for c in cities)
        assert any("São Paulo" in c.name for c in cities)

    async def test_list_specialties_returns_items(self):
        fake = FakeMemedClient()
        specialties = await fake.list_specialties(q="ped")
        assert len(specialties) > 0
        assert any("pediatria" in s.name.lower() for s in specialties)

    async def test_create_prescriber_returns_result(self):
        fake = FakeMemedClient()
        result = await fake.create_prescriber({"data": {"attributes": {"nome": "Alice"}}})
        assert isinstance(result, PrescriberResult)
        assert result.external_id == "ext-1"
        assert result.token == "fake-token-001"

    async def test_get_prescriber_returns_result(self):
        fake = FakeMemedClient()
        result = await fake.get_prescriber("ext-1")
        assert isinstance(result, PrescriberResult)
        assert result.memed_user_id == "usr_001"
        assert result.token == "fake-token-001"

    async def test_get_prescription_pdf_url_returns_url(self):
        fake = FakeMemedClient()
        url = await fake.get_prescription_pdf_url("tok_xxx", "presc_42")
        assert isinstance(url, str)
        assert "presc_42" in url

    async def test_get_digital_link_returns_result(self):
        fake = FakeMemedClient()
        result = await fake.get_digital_link("tok_xxx", "presc_42")
        assert isinstance(result, DigitalLinkResult)
        assert result.link.startswith("https://")

    async def test_download_pdf_returns_bytes(self):
        fake = FakeMemedClient()
        data = await fake.download_pdf("https://example.com/doc.pdf")
        assert isinstance(data, bytes)
        assert data.startswith(b"%PDF")
        assert len(data) > 10

    async def test_records_calls(self):
        fake = FakeMemedClient()
        await fake.check_key()
        await fake.list_cities(q="Rio")
        await fake.download_pdf("http://x.pdf")
        assert len(fake.calls) == 3
        assert fake.calls[0] == ("check_key",)
        assert fake.calls[1] == ("list_cities", {"q": "Rio"})
        assert fake.calls[2] == ("download_pdf", {"url": "http://x.pdf"})


# ---------------------------------------------------------------------------
# MemedHTTPClient with MockTransport
# ---------------------------------------------------------------------------


def _mock_transport(handler):
    """Build an httpx.AsyncClient with MockTransport from a request handler."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.memed.test")


class TestMemedHTTPClient:
    """HTTP implementation tested via MockTransport — no network."""

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _json_api_prescriber(
        external_id: str = "ext-1",
        memed_user_id: str = "usr_abc",
        status: str = "Ativo",
        token: str = "tok_secret",
    ) -> dict:
        return {
            "data": {
                "id": memed_user_id,
                "type": "usuario-prescritor",
                "attributes": {
                    "token": token,
                    "status": status,
                    "external_id": external_id,
                },
            }
        }

    @staticmethod
    def _json_api_list(items: list[dict]) -> dict:
        return {"data": items}

    # -- querystring carries api-key / secret-key -----------------------------

    async def test_querystring_has_api_key_and_secret_key(self):
        """Every request must carry ?api-key=...&secret-key=..."""

        async def handler(request: httpx.Request) -> httpx.Response:
            assert "api-key" in request.url.params, f"Missing api-key in {request.url}"
            assert "secret-key" in request.url.params, f"Missing secret-key in {request.url}"
            assert request.url.params["api-key"] == "test-api-key"
            assert request.url.params["secret-key"] == "test-secret-key"
            return httpx.Response(200, json={"status": "ok"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="test-api-key",
            secret_key="test-secret-key",
        )
        # Replace the internal client's transport
        client._client = _mock_transport(handler)

        await client.check_key()

    # -- check_key ------------------------------------------------------------

    async def test_check_key_returns_true_on_200(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        assert await client.check_key() is True

    async def test_check_key_returns_false_on_401(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "unauthorized"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        assert await client.check_key() is False

    # -- list_cities / list_specialties ---------------------------------------

    async def test_list_cities_returns_reference_items(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/cidades" in str(request.url)
            return httpx.Response(
                200,
                json=self._json_api_list([
                    {"id": 1, "nome": "São Paulo"},
                    {"id": 2, "nome": "Rio de Janeiro"},
                ]),
            )

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        cities = await client.list_cities(q="São")
        assert len(cities) == 2
        assert cities[0].id == 1
        assert cities[0].name == "São Paulo"

    async def test_list_specialties_returns_reference_items(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/especialidades" in str(request.url)
            return httpx.Response(
                200,
                json=self._json_api_list([
                    {"id": 10, "nome": "Pediatria"},
                    {"id": 20, "nome": "Cardiologia"},
                ]),
            )

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        specialties = await client.list_specialties(q="ped")
        assert len(specialties) == 2
        assert specialties[0].name == "Pediatria"

    # -- create_prescriber ----------------------------------------------------

    async def test_create_prescriber_parses_json_api(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/sinapse-prescricao/usuarios" in str(request.url)
            assert request.method == "POST"
            body = request.read()
            assert b"nome" in body
            return httpx.Response(201, json=self._json_api_prescriber(token="tok_new"))

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        result = await client.create_prescriber({"data": {"attributes": {"nome": "Alice"}}})
        assert isinstance(result, PrescriberResult)
        assert result.token == "tok_new"
        assert result.memed_user_id == "usr_abc"

    # -- get_prescriber -------------------------------------------------------

    async def test_get_prescriber_reads_data_attributes_token(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/sinapse-prescricao/usuarios/ext-1" in str(request.url)
            return httpx.Response(200, json=self._json_api_prescriber(token="tok_fresh"))

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        result = await client.get_prescriber("ext-1")
        assert result.token == "tok_fresh"
        assert result.external_id == "ext-1"

    # -- get_prescription_pdf_url ---------------------------------------------

    async def test_get_prescription_pdf_url_returns_url(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/prescricoes/presc_42/url-document/full" in str(request.url)
            assert "token" in request.url.params
            return httpx.Response(200, json={"url": "https://memed.storage/presc_42.pdf"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        url = await client.get_prescription_pdf_url("tok_xxx", "presc_42")
        assert url == "https://memed.storage/presc_42.pdf"

    # -- get_digital_link -----------------------------------------------------

    async def test_get_digital_link_returns_result(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/prescricoes/presc_42/get-digital-prescription-link" in str(request.url)
            assert "token" in request.url.params
            return httpx.Response(
                200,
                json={
                    "link": "https://memed.com/r/abc",
                    "codigo_desbloqueio": "654321",
                },
            )

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        result = await client.get_digital_link("tok_xxx", "presc_42")
        assert isinstance(result, DigitalLinkResult)
        assert result.link == "https://memed.com/r/abc"
        assert result.unlock_code == "654321"

    # -- download_pdf ---------------------------------------------------------

    async def test_download_pdf_returns_bytes_for_pdf_content_type(self):
        pdf_bytes = b"%PDF-1.4\nsome pdf content here\n"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=pdf_bytes, headers={"content-type": "application/pdf"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        data = await client.download_pdf("https://memed.storage/doc.pdf")
        assert data == pdf_bytes

    async def test_download_pdf_accepts_octet_stream(self):
        pdf_bytes = b"%PDF-1.4\ncontent"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=pdf_bytes, headers={"content-type": "application/octet-stream"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        data = await client.download_pdf("https://memed.storage/doc.pdf")
        assert data == pdf_bytes

    async def test_download_pdf_raises_on_non_pdf_content(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not a pdf at all", headers={"content-type": "application/pdf"})

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        with pytest.raises(NonPdfResponseError, match="%PDF"):
            await client.download_pdf("https://memed.storage/doc.pdf")

    async def test_download_pdf_raises_on_http_error(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"not found")

        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(handler),
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.download_pdf("https://memed.storage/missing.pdf")

    # -- logger suppression ---------------------------------------------------

    async def test_loggers_are_suppressed(self):
        """httpx and httpcore loggers should be at WARNING level."""
        # Instantiate a client — this sets up logger suppression
        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(lambda r: httpx.Response(200)),
        )
        _ = client  # used
        httpx_logger = logging.getLogger("httpx")
        httpcore_logger = logging.getLogger("httpcore")
        assert httpx_logger.level >= logging.WARNING
        assert httpcore_logger.level >= logging.WARNING


# ---------------------------------------------------------------------------
# Protocol conformance — FakeMemedClient satisfies MemedClient
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """FakeMemedClient must satisfy the MemedClient protocol."""

    def test_fake_is_memed_client(self):
        fake = FakeMemedClient()
        assert isinstance(fake, MemedClient)

    async def test_http_client_is_memed_client(self):
        client = MemedHTTPClient(
            api_url="https://api.memed.test",
            api_key="k",
            secret_key="s",
            _client_override=_mock_transport(lambda r: httpx.Response(200)),
        )
        assert isinstance(client, MemedClient)