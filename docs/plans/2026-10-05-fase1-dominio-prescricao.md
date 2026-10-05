# openavisio-prescricoes-fase1 - Work Plan

## TL;DR (For humans)
**What you'll get:** A Prescription domain inside OpenAvisio — a doctor (prescriber) can assemble a draft prescription for a Patient, the draft autosaves while editing, and the moment it is issued the system asks ANVISA's SNCR for an official number, has it signed by an ICP-Brasil aggregator, and files the signed PDF against the Patient. Phase 1 builds the domain, storage, state machine and the *ports* for SNCR and the signer — wired to fakes, so it runs and tests without touching ANVISA.

**Why this approach:** ANVISA's access token lives only 30 seconds and there is no refresh token, and SNCR hands out *blocks* of numbers (10–50 at a time, or 1000 for controlled retention receipts) rather than one number per call. Both facts mean numbering must happen at issue time, not while drafting — so the domain is split into an editable `draft` and an irreversible issued artefact, and the two external systems are hidden behind interfaces so the domain is testable.

**What it will NOT do:** It will not call the real SNCR or the real signing aggregator (that is Phase 2+); it will not generate or sign a PDF; it will not implement the RDC 1.000/2025 layout or QR; it will not change the existing Document upload/OCR pipeline.

**Effort:** Large (10 implementation todos + 4 final-verification tasks)
**Risk:** High — the SNCR token/session contract and the RCE/RET CNPJ gate are external, and the project's current "not a medical device" positioning is contradicted by generating prescriptions.
**Decisions to sanity-check:** which receipt types are in scope (RCE/RET need an entity CNPJ); who is allowed to sign; and whether patient erasure may hard-delete a legally-retained prescription.

Your next move: review the three decisions above. To run the plan, start a **separate worker session** with `$start-work openavisio-prescricoes-fase1` — this planner session will not execute it.

---

> TL;DR (machine): Large/High. Phase 1 = prescription domain + persistence + state machine + SNCR/signer ports with fakes + draft autosave + frontend editor; no live external calls.

## Scope

### Must have
- Domain vocabulary settled and recorded (ADR-036 + `CONTEXT.md`): **Prescription**, **Prescriber**, the seven receipt types, numbering, issuance, signature.
- Persistence for: `Prescriber`, `Prescription`, `PrescriptionItem`, `PrescriptionNumberAllocation`, `PrescriptionNumber`, `PrescriptionSignature`; one Alembic revision on top of the current head `g3b4c5d6e7f8`.
- A state machine `draft → numbering → numbered → signing → signed → dispensed` with `failed`/`voided`, its invariants, and optimistic-concurrency autosave.
- Ports (Python `Protocol`) + fakes for `SncrNumberingPort` (the two manual endpoints only) and `PrescriptionSignerPort`.
- A numbering service that consumes a block and burns exactly one number per prescription, idempotently.
- Archival of the signed artefact into the existing `DocumentReference` envelope-encryption path, explicitly bypassing the OCR pipeline.
- Patient-erasure cascade participation + audit entries for issue/sign/void.
- A minimal frontend: patient prescriptions list + draft editor with debounced autosave, and i18n keys in `pt`/`en`/`de`.
- Tests that run with fakes only (zero network).

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No live HTTP call to `api-gateway.*.anvisa.gov.br` (Phase 2/3).
- No live call to any signing aggregator (Phase 5); no vendor SDK chosen or imported.
- No PDF generation and no RDC 1.000/2025 template/QR (Phase 4).
- No changes to `DocumentReference`'s upload, OCR, extraction or verification behaviour.
- No new i18n locale files beyond the three that exist (`pt`, `en`, `de`).
- No multi-prescriber, multi-tenant, or SaaS billing work.
- No invented SNCR or aggregator endpoints: only the four paths documented in the v5 manual (`/auth/login`, `/auth/token`, `/numeracoes/notificacao-receita`, `/numeracoes/receita-especial-retencao`).

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: **TDD** for the state machine and numbering service (pure logic, fast); **tests-after** for the router/archival/frontend slices. Framework: `pytest` + `httpx.ASGITransport` (existing `backend/tests/conftest.py`), `pnpm` + Vitest/Playwright for the frontend page.
- Every test must run with `FakeSncrNumbering`/`FakeSigner`; no test may reach the network. A test that requires ANVISA credentials is out of scope for Phase 1.
- Evidence: `.omo/evidence/task-<N>-openavisio-prescricoes-fase1.<ext>` (outside ulw-loop) — capture the exact command and its output; a passing summary is a claim until the command output is attached.

## Execution strategy
### Parallel execution waves
- **Wave 1 (foundation):** I1 docs/vocabulary; I2 persistence + migration.
- **Wave 2 (domain core):** I3 state machine; I4 ports + fakes. (both depend on I2)
- **Wave 3 (services):** I5 numbering service; I6 archival service. (depend on I3/I4)
- **Wave 4 (edges):** I7 schemas + router + autosave; I8 erasure cascade + audit.
- **Wave 5 (surface):** I9 frontend page + i18n.
- **Wave 6:** final verification wave (F1–F4).

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | - | 2 (vocabulary used by code) | 2 |
| 2 | - | 3,4,5,6,7,8 | 1 |
| 3 | 2 | 5 | 4 |
| 4 | 2 | 5,6 | 3 |
| 5 | 3,4 | 7 | 6 |
| 6 | 4 | 7 | 5 |
| 7 | 5,6 | 9 | 8 |
| 8 | 2 | - | 7 |
| 9 | 7 | - | 8 |

## Todos
> Implementation + Test = ONE todo. Never separate.

- [ ] 1. Record the prescription domain vocabulary, ADR-036 and the regulatory-positioning consequence
  What to do / Must NOT do: Add ADR-036 describing Prescription/Prescriber/receipt types/numbering/issuance and the "SNCR numbers, the platform signs" split. Add the new terms to `CONTEXT.md` under a new "Prescription" subsection (Prescription, Prescriber, Receipt type, Numbering, Issuance, Signature token). Amend `docs/regulatory-positioning.md` to state explicitly that generating prescriptions is out of the current "not a medical device" claim and needs a formal review. Do NOT change any code; do NOT rewrite the existing domain terms.
  Parallelization: Wave 1 | Blocked by: - | Blocks: 2
  References (executor has NO interview context - be exhaustive): `CONTEXT.md` (domain glossary, "Clinical data" section ends at "Health Log"); `docs/adr/` (existing numbering: last is `035-mobile-capacitor-7-for-fdroid-node.md`, so use `036-pharmacy-curated-from-medication-...`-style naming — actually `036-prescription-domain.md`); `docs/regulatory-positioning.md:26-29` (deliberately avoids generating dosage advice) and `README.md` ("Not a medical device — deliberately"); `docs/sncr/manual-api-sncr-v5.pdf` §2.2.1 ("SNCR only numbers").
  Acceptance criteria (agent-executable): `test -f docs/adr/036-prescription-domain.md`; `grep -q "Privacy-by-design" ...` no — instead assert `grep -qi "Prescription" CONTEXT.md` and `grep -qi "not a medical device" docs/adr/036-prescription-domain.md`. Run `rg -n "036" docs/adr/036-prescription-domain.md` to confirm the ADR number is unused elsewhere.
  QA scenarios (name the exact tool + invocation): happy — `pnpm --dir frontend exec -- next build` unaffected, and markdown lint of the three files; failure — grep for a term the ADR must NOT introduce (e.g. redefining Caregiver). Evidence `.omo/evidence/task-1-openavisio-prescricoes-fase1.md`.
  Commit: Y | docs(domain): add prescription domain ADR-036 and glossary terms

- [ ] 2. Add the prescription persistence layer: six models, enums, one migration, and config
  What to do / Must NOT do: Create `backend/app/models/prescription.py` with `Prescriber`, `Prescription`, `PrescriptionItem`, `PrescriptionNumberAllocation`, `PrescriptionNumber`, `PrescriptionSignature`, plus StrEnum types `PrescriptionType` (`simple`, `NRA`, `NRB`, `NRB2`, `NRR`, `NRT`, `RCE`, `RET`), `PrescriptionStatus` (`draft`, `numbering`, `numbered`, `signing`, `signed`, `dispensed`, `failed`, `voided`), `PrescriptionEnvironment` (`hmg`, `prd`), `SignerProvider`. Follow existing conventions exactly: `BaseModel`/`OwnedResource` from `backend/app/models/base.py`, `Mapped`/`mapped_column`, PostgreSQL `UUID(as_uuid=True)`, `String(n)` not native ENUM (see `backend/app/models/share_link.py:19-39`), `JSONB` from `sqlalchemy.dialects.postgresql`. Register every class in `backend/app/models/__init__.py` `__all__`. Add `backend/alembic/versions/<newhash>_add_prescriptions.py` with `down_revision = "g3b4c5d6e7f8"`. Add settings to `backend/app/core/config.py` (`sncr_base_url_hmg`, `sncr_base_url_prd`, `sncr_cnpj`, `prescription_signer_provider`, `prescription_signer_api_key`) and mirror them in `.env.example`. Prescriber `cpf` must be encrypted at rest using `app.core.encryption.encrypt_setting`/`decrypt_setting` (master KEK). Prescription must store a `prescriber_snapshot` JSONB so the legal record survives User erasure. Do NOT native-Postgres-ENUM; do NOT cascade-delete the prescriber snapshot; do NOT add a pipeline enqueue path.
  Parallelization: Wave 1 | Blocked by: - | Blocks: 3,4,5,6,7,8
  References: `backend/app/models/base.py:11-25`; `backend/app/models/document.py:12-54`; `backend/app/models/share_link.py:19-65`; `backend/app/models/patient.py:30-39` (relationship style); `backend/app/models/__init__.py:1-80`; `backend/app/core/config.py:7-105`; `backend/app/core/encryption.py:70-76`; `backend/alembic/versions/g3b4c5d6e7f8_condition_merged_into.py:8` (head); `docs/sncr/manual-api-sncr-v5.pdf` §2.3.1/§2.3.2 (field shapes, enums, 50/1000).
  Acceptance criteria (agent-executable): `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` exits 0; `cd backend && uv run python -c "from app.models import Prescription, Prescriber, PrescriptionItem, PrescriptionNumberAllocation, PrescriptionNumber, PrescriptionSignature"` exits 0; `uv run pytest backend/tests/test_health.py -q` still passes.
  QA scenarios: happy — migration creates all six tables (assert with `uv run python -c` reflecting `Base.metadata.tables`); failure — `down_revision` set to a non-head revision must fail `alembic heads` (assert single head: `uv run alembic heads | wc -l == 1`). Evidence `.omo/evidence/task-2-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): add prescription persistence models and migration

- [ ] 3. Implement the prescription state machine and invariants
  What to do / Must NOT do: Add `backend/app/services/prescriptions/state.py` with the allowed-transition table and a `transition(prescription, target, *, actor_is_prescriber)` function that raises a typed `InvalidTransition` on any illegal move. Invariants: items are immutable once `status != draft`; `number_allocated` is write-once; `signed` requires both `document_id` and `signature_id`; `signed` is terminal except `dispensed`; `voided` allowed from any pre-`signed` state; a burned number is never reused. Add an optimistic-concurrency `version` column usage (increment on every autosave/patch) and reject stale writes with `StalePrescription`. Do NOT put HTTP or SQL in this module — it must be pure and unit-testable.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 5
  References: model file from todo 2; `backend/app/routers/medications.py:28-33` (derived-state helper pattern); `docs/plans/2026-10-05-prontuario-receitas-plano.md:67` (target states).
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescription_state.py -q` passes a full transition matrix (every legal pair allowed; every illegal pair raises) and the four invariants.
  QA scenarios: happy — draft→numbering→numbered→signing→signed→dispensed accepted; failure — signed→draft raises `InvalidTransition`; editing an item on a `numbered` prescription raises. Evidence `.omo/evidence/task-3-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): add prescription state machine

- [ ] 4. Define the SNCR and signer ports, result types, and fakes
  What to do / Must NOT do: Add `backend/app/services/prescriptions/ports.py` with `typing.Protocol` definitions: `SncrNumberingPort.request_notificacao(*, receita, conselho, uf, documento, quantidade, bearer_token) -> NotificacaoResult` and `request_especial(*, conselho, tipo, documento, uf, cnpj, bearer_token) -> EspecialResult`; `PrescriptionSignerPort.sign(pdf_bytes, *, prescriber_snapshot, prescription_number, validation_required) -> SignatureResult`. Result dataclasses mirror the manual exactly: `NotificacaoResult(numbers: list[str], saldo_receitas: int | None, mensagem: str | None)`; `EspecialResult(inicio, fim, quantidade, mensagem)`. Add `backend/app/services/prescriptions/fakes.py` with `FakeSncrNumbering` (deterministic, records calls) and `FakeSigner` (returns a fixed token/URL and a hash). Do NOT implement real HTTP; do NOT invent endpoints beyond the two numbering paths.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 5,6
  References: `docs/sncr/manual-api-sncr-v5.pdf` §1.3 (exact request/response field names: `numeracoesReceita`, `saldoReceitas`, `mensagem`, `inicio`, `fim`, `quantidade`); `docs/sncr/exemplo-integracao-v2.zip` → `/tmp/sncr-exemplo/src/app/app.component.ts:19,72` (payload shape) and `README.md:263-271` (response shape); `backend/app/services/lab_codes.py` (existing pure-service module convention).
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescription_ports.py -q` passes; a test asserts `FakeSncrNumbering` returns exactly `quantidade` numbers and that calling the wrong method for a type is a type error.
  QA scenarios: happy — fake returns a 1000-range for `request_especial`; failure — `request_notificacao(quantidade=9)` must raise `ValueError` (manual min 10). Evidence `.omo/evidence/task-4-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): define SNCR and signer ports with fakes

- [ ] 5. Implement the numbering service (pool allocation and single-number burn, idempotent)
  What to do / Must NOT do: Add `backend/app/services/prescriptions/numbering.py` with `ensure_numbers(db, prescriber, receipt_type, bearer_token, port)` that: picks the correct port method by `PrescriptionType` (`simple` needs no number; NRA/NRB/NRB2/NRR/NRT → notificacao with default quantidade 10; RCE/RET → especial), persists a `PrescriptionNumberAllocation` with `raw_response`, and `burn_number(db, prescription, allocation)` that assigns the next unused number to the prescription (creating a `PrescriptionNumber` row, unique on `number`). Enforce manual limits: notificacao 10–50 per call; especial exactly 1000; NRA daily 50/type/prescriber; RCE/RET 3 calls per inscription per month. Make `ensure_numbers` idempotent via an `idempotency_key` (prescription id + attempt) so a retried issue never double-allocates. Do NOT call the real port in tests; do NOT reuse or un-burn an allocated number.
  Parallelization: Wave 3 | Blocked by: 3,4 | Blocks: 7
  References: manual §2.3.1.5 (50/day), §2.3.2.5 (1000, 3/month); `docs/sncr/manual-api-sncr-v5.pdf` §1.3 error table (`Limite diário de 50 receitas atingido`, `A quantidade mínima permitida é 10`, `Quantidade de números excedida`); ports from todo 4; models from todo 2.
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescription_numbering.py -q` passes: a 10-number pool burns exactly 10 prescriptions then raises `PoolExhausted`; a repeated `ensure_numbers` with the same idempotency key allocates once; a `simple` prescription never calls the port.
  QA scenarios: happy — 10 prescriptions get 10 distinct numbers; failure — 11th raises `PoolExhausted`, and an RCE call without CNPJ configured raises `MissingCnpj`. Evidence `.omo/evidence/task-5-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): add SNCR numbering allocation and burn service

- [ ] 6. Implement the signed-artefact archival service into DocumentReference
  What to do / Must NOT do: Add `backend/app/services/prescriptions/archive.py` with `archive_signed_pdf(db, prescription, signed_pdf: bytes. user) -> DocumentReference` that: gets/creates the patient KEK (`app.core.patient_keys.ensure_patient_kek`), envelope-encrypts with `app.core.encryption.encrypt_document`, writes via `app.core.storage.get_storage()` to `{patient_id}/{doc_id}.enc`, and creates a `DocumentReference` with `type="prescription"`, `processing_status="complete"`, `verification_status="verified"`, `correspondent_id=None`, so the Celery OCR pipeline is **not** enqueued. Link it back to `prescription.document_id`. Add a read helper that streams the decrypted signed PDF for the prescription endpoint. Do NOT enqueue `ocr_stage`; do NOT overwrite an existing document; do NOT store the PDF unencrypted.
  Parallelization: Wave 3 | Blocked by: 4 | Blocks: 7
  References: `backend/app/routers/documents.py:110-176` (upload/encrypt/write pattern), `:179-194` (decrypt/stream), `:146-160` (DocumentReference construction); `backend/app/core/patient_keys.py`; `backend/app/core/encryption.py:79-91`; `backend/app/core/storage.py`.
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescription_archive.py -q` passes: after archival the raw storage bytes are ciphertext (do not contain `%PDF`), the decrypted bytes equal the input, and no Celery task was enqueued (assert with `unittest.mock.patch` on `ocr_stage.delay` and `delay.assert_not_called()`).
  QA scenarios: happy — round-trip decrypt equals input; failure — missing patient KEK path still creates one; a second archive for the same prescription is rejected. Evidence `.omo/evidence/task-6-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): archive signed PDF into encrypted Document store

- [ ] 7. Expose the prescriptions API: CRUD, versioned autosave, and the issue endpoint
  What to do / Must NOT do: Add `backend/app/schemas/prescription.py` (Pydantic v2, mirror `backend/app/schemas/medication.py`) and `backend/app/routers/prescriptions.py` with: `GET/POST /api/patients/{patient_id}/prescriptions`, `GET/PATCH/DELETE /api/prescriptions/{id}`, `POST /api/prescriptions/{id}/issue`, `POST /api/prescriptions/{id}/void`, `GET /api/prescriptions/{id}/file`. Guard every route with `require_patient_access` from `backend/app/auth/access.py` (`contribute` to author, `admin` to issue/sign); the issue endpoint must additionally require the current User to be the configured Prescriber. PATCH is the autosave: it must accept `version` and return `409` on stale writes. Inject the ports via FastAPI dependencies so tests override fake implementations. Register the router in `backend/app/main.py` next to `medications`. Write audit entries on issue/void. Do NOT expose a route that calls the network directly from the request without the service layer; do NOT allow editing items after `numbered`.
  Parallelization: Wave 4 | Blocked by: 5,6 | Blocks: 9
  References: `backend/app/routers/medications.py:1-124` (router, DTO, access pattern); `backend/app/deps.py:19-61` (`get_current_user`, `patient_access_dep`); `backend/app/auth/access.py:17-84`; `backend/app/models/audit.py` and how routers in `backend/app/core/audit*` write entries; `backend/app/schemas/common.py:10-18`; `backend/app/main.py:63-84` (router registration).
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescriptions_api.py -q` passes: create draft → autosave (version increments) → stale autosave returns 409 → issue with fakes yields `signed` + a `document_id` + a `signature_id` → non-granted user gets 404 → a non-prescriber gets 403 on issue.
  QA scenarios: happy — full draft→signed via the API with fakes; failure — PATCH with an old `version` → 409 and no mutation; GET file for a non-granted user → 404. Evidence `.omo/evidence/task-7-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): add prescriptions API with autosave and issue

- [ ] 8. Integrate prescriptions into erasure cascade and retention governance
  What to do / Must NOT do: Add the new tables to `backend/app/services/erasure.py:erase_patient` (collect ids, hard-delete `PrescriptionItem`, `PrescriptionSignature`, `Prescription`, `PrescriptionNumber` consumed by the patient's prescriptions; retain the prescriber's `PrescriptionNumberAllocation` because it is not patient PHI but document the decision). Include the new entity ids in the `AuditLog` purge list. Handle `erase_user`: do **not** null the `prescription.prescriber_snapshot` (legal record); do delete a prescriber profile only if not referenced, otherwise anonymise its CPF. Register a governance data category or an explicit retention exemption for prescriptions so the existing `run_retention_purge` (`backend/app/workers/scheduler.py:135-146`) does not silently purge them. Do NOT crypto-shred references to already-issued external numbers (impossible); document that externally-held copies survive.
  Parallelization: Wave 4 | Blocked by: 2 | Blocks: -
  References: `backend/app/services/erasure.py:34-146` (patient cascade), `:149-236` (user erasure); `backend/app/workers/scheduler.py:135-146`; `backend/app/services/governance.py`; `docs/adr/017-patient-erasure-cascade-hard-delete.md`; `docs/adr/031-per-patient-kek-crypto-shredding.md`.
  Acceptance criteria: `cd backend && uv run pytest backend/tests/test_prescription_erasure.py -q` passes: erasing a patient removes their prescriptions, items, signatures and consumed numbers; the prescriber snapshot on another patient's prescription is untouched; a prescription is not purged by the retention job.
  QA scenarios: happy — cascade removes all new rows; failure — asserting a referenced prescriber profile survives user erasure. Evidence `.omo/evidence/task-8-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(prescriptions): integrate prescriptions with erasure and retention

- [ ] 9. Frontend: patient prescriptions list + draft editor with autosave
  What to do / Must NOT do: Add `frontend/src/app/patients/[id]/prescriptions/page.tsx` modelled on `.../medications/page.tsx`, with a list of prescriptions and a draft editor (add/remove/order items, patient fields) that debounce-saves via PATCH and surfaces `409` as a conflict. Add typed wrappers to `frontend/src/lib/api.ts` next to the medication wrappers. Add all new UI strings to `frontend/src/messages/pt.json`, `en.json`, `de.json` (no new locale files). The issue button must be disabled unless the draft is valid and, in Phase 1, explain that SNCR/signing is not yet connected. Do NOT call ANVISA or the aggregator from the browser in Phase 1; do NOT add a new locale.
  Parallelization: Wave 5 | Blocked by: 7 | Blocks: -
  References: `frontend/src/app/patients/[id]/medications/page.tsx`; `frontend/src/lib/api.ts:82-85`; `frontend/src/messages/pt.json:660` (`class_prescription` already exists); `frontend/AGENTS.md` (Next.js 16 — read `node_modules/next/dist/docs/` before coding).
  Acceptance criteria: `cd frontend && pnpm exec tsc --noEmit` passes; a Playwright/Vitest test renders the page, edits a draft, waits for the debounce, and asserts a PATCH with an incrementing `version`; `409` shows the conflict message.
  QA scenarios: happy — autosave fires once after debounce and updates version; failure — forcing a 409 renders the conflict state and does not drop the user's text. Evidence `.omo/evidence/task-9-openavisio-prescricoes-fase1.txt`.
  Commit: Y | feat(frontend): add prescriptions list and draft autosave editor

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit — every todo's Acceptance criteria was actually executed and its evidence recorded; no live external call exists in Phase 1 code (`rg -n "anvisa|api-gateway|sncr-api" backend/app` returns only docstrings/ports, no HTTP client).
- [ ] F2. Code quality review — `cd backend && uv run ruff check . && uv run pytest -q`; `cd frontend && pnpm exec tsc --noEmit && pnpm lint`.
- [ ] F3. Real manual QA — with fakes, exercise draft→autosave→issue→file-download end to end against the running dev stack and attach the transcript.
- [ ] F4. Scope fidelity — confirm no PDF/RDC-1.000 template, no aggregator SDK, and no live SNCR call were introduced; confirm `simple` prescriptions never request a number.

## Commit strategy
One conventional commit per todo (`feat(prescriptions):`, `docs(domain):`), migration and models in the same commit as their tests. Todos 3–4 may share a commit only if both green. No commit may contain a live ANVISA credential or a real aggregator key.

## Success criteria
- `uv run alembic heads` shows one head on top of `g3b4c5d6e7f8`; migration up/down/up clean.
- `uv run pytest -q` is green with the new `test_prescription_*.py` files, all offline.
- A prescription can be created, autosaved with conflict detection, issued through `FakeSncrNumbering` + `FakeSigner`, producing an encrypted `DocumentReference` and a `PrescriptionSignature`, with audit entries.
- Patient erasure removes all prescription rows; a `simple` prescription consumes no SNCR number.
- Frontend builds and the draft editor autosaves against the real backend.
