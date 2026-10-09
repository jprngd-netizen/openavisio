"""extraction_stage must not treat an empty/errored extraction as success.

When the aiservice answers 200 with {"entities": null, "confidence": 0.0,
"error": "..."} (the LLM returned malformed JSON) the old `or extraction`
fallback saved that error dict as if it were clinical data and marked the
document extracted/completed — a silent data loss. The stage must instead
fail (and, via autoretry_for, be retried) so nothing is saved as entities.
"""

import asyncio
import types

import pytest

from app.workers import pipeline


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    response = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, files=None):
        return _FakeAsyncClient.response


def _patch_pipeline(monkeypatch, response):
    """Wire extraction_stage against in-memory stand-ins; return recorded calls."""
    updates = []
    enqueued = []

    async def fake_get_doc(doc_id):
        return types.SimpleNamespace(
            extracted_text="encrypted-text",
            patient_id="patient-1",
            document_classification="lab_report",
        )

    async def fake_update_doc(doc_id, **kwargs):
        updates.append(kwargs)

    async def fake_kek(patient_id):
        return b"kek"

    async def fake_ai_model(stage):
        return None

    async def fake_lang():
        return "en"

    monkeypatch.setattr(pipeline, "_get_doc", fake_get_doc)
    monkeypatch.setattr(pipeline, "_update_doc", fake_update_doc)
    monkeypatch.setattr(pipeline, "_patient_kek", fake_kek)
    monkeypatch.setattr(pipeline, "_get_ai_model", fake_ai_model)
    monkeypatch.setattr(pipeline, "_get_org_language", fake_lang)
    # `_run` does asyncio.get_event_loop().run_until_complete(...), which needs a
    # current loop; on a bare interpreter there is none. Run the coroutine on a
    # throwaway loop instead (test-only shim; production is unchanged).
    monkeypatch.setattr(pipeline, "_run", lambda coro: asyncio.run(coro))
    # Never touch the broker.
    monkeypatch.setattr(
        pipeline, "embedding_stage", types.SimpleNamespace(delay=lambda d: enqueued.append(d))
    )

    import app.core.encryption as enc

    monkeypatch.setattr(enc, "decrypt_str", lambda value, kek: "plain text")
    monkeypatch.setattr(enc, "encrypt_str", lambda value, kek: "enc:" + value)

    _FakeAsyncClient.response = response
    monkeypatch.setattr(pipeline.httpx, "AsyncClient", _FakeAsyncClient)
    return updates, enqueued


def test_error_response_marks_failed_and_raises(monkeypatch):
    # The exact production symptom: HTTP 200 carrying an error, no entities.
    err = {
        "entities": None,
        "confidence": 0.0,
        "error": "Expecting ':' delimiter: line 620 column 5",
    }
    updates, enqueued = _patch_pipeline(monkeypatch, _FakeResponse(200, err))

    with pytest.raises(ValueError):
        pipeline.extraction_stage.run("doc-1")

    assert updates, "the document must be updated on failure"
    assert updates[-1]["processing_status"] == "failed"
    assert "Expecting ':' delimiter" in updates[-1]["processing_error"]
    assert not any(u.get("processing_status") == "extracted" for u in updates)
    assert not any("extraction_json" in u for u in updates)
    assert enqueued == [], "embedding_stage must not run after a failed extraction"


def test_null_entities_without_error_marks_failed(monkeypatch):
    updates, enqueued = _patch_pipeline(
        monkeypatch, _FakeResponse(200, {"entities": None, "confidence": 0.0})
    )

    with pytest.raises(ValueError):
        pipeline.extraction_stage.run("doc-1")

    assert updates[-1]["processing_status"] == "failed"
    assert enqueued == []


def test_empty_entities_marks_failed(monkeypatch):
    updates, enqueued = _patch_pipeline(monkeypatch, _FakeResponse(200, {"entities": {}}))

    with pytest.raises(ValueError):
        pipeline.extraction_stage.run("doc-1")

    assert updates[-1]["processing_status"] == "failed"
    assert enqueued == []


def test_valid_entities_are_saved_and_embedded(monkeypatch):
    entities = {
        "summary": "ok",
        "observations": [{"code": "Hb", "value_quantity": 14.0}],
        "diagnoses": [],
    }
    updates, enqueued = _patch_pipeline(monkeypatch, _FakeResponse(200, {"entities": entities}))

    pipeline.extraction_stage.run("doc-1")

    assert updates[-1]["processing_status"] == "extracted"
    assert updates[-1]["verification_status"] == "extracted"
    assert enqueued == ["doc-1"], "a successful extraction must continue to embedding"
