# ADR 036: Prescription domain — Memed integration

**Status:** Accepted (2026-10-05)

## Context

OpenAvisio needs to support issuing medical prescriptions for Patients. A
prescription is a legal document: it carries a number from the SNCR (ANVISA's
national controlled-substance registry), must be signed with an ICP-Brasil digital
certificate, and must comply with RDC 1000/25 layout requirements. Building this
in-house would mean opening a CNPJ, integrating directly with the SNCR API,
implementing a PDF generator that matches the official layout, and managing digital
certificates — all outside the project's core competency as a health-record
management tool.

After evaluating the options (direct SNCR integration, Prescreve, Prescri/BirdID,
and Memed), the decision was made to integrate with **Memed (Sinapse Prescricao)**
as the prescription and signing platform. This ADR documents the domain model that
results from that integration and the architectural decisions that follow.

### Verified facts (Memed official documentation, 2026-10-05)

- Memed's API provides endpoints for prescriber registration, city/specialty
  reference data, prescription PDF download (`GET /v1/prescricoes/{id}/url-document/full?token=`),
  and digital link retrieval.
- The frontend module (`sinapse-prescricao.min.js`) embeds as an iframe and
  communicates via `postMessage` events (`core:moduleInit`, `prescricaoImpressa`,
  `prescricaoExcluida`).
- The SNCR number is not exposed as an API field — it appears only in the PDF
  header/footer. The plan does not assume an SNCR field in the API.
- The prescriber's digital certificate is BYOC (bring your own certificate) via
  BirdID; Memed consumes the certificate's signing credits.
- The `prescricaoImpressa` event payload is documented but unverified at runtime
  — the adapter parses it defensively by candidate keys.

## Decisions

### 1. Memed resolves SNCR/ANVISA numbering and ICP-Brasil signing

Memed handles everything that makes a prescription legally valid in Brazil:

- **SNCR numbering:** obtained by Memed through the prescriber's Gov.br
  authentication within the Memed flow. OpenAvisio never calls the SNCR API.
- **ICP-Brasil signing:** executed by Memed using the prescriber's own BirdID
  certificate (BYOC). Memed does not charge for the signature; it consumes credits
  from the Organization's BirdID plan.
- **PDF generation:** Memed produces the signed PDF with the official RDC 1000/25
  layout. OpenAvisio does not generate or sign PDFs.

OpenAvisio's responsibility begins after the PDF is signed: it downloads the
signed PDF, archives it encrypted per-patient, and exposes it in a dedicated
Prescriptions section.

### 2. OpenAvisio stores the signed PDF encrypted per-patient

The signed PDF is the authoritative record of what was prescribed. It is:

- Downloaded via the official Memed endpoint (`url-document/full`) using a fresh
  `data-token` at capture time.
- Encrypted with the patient's KEK (per-patient envelope encryption, ADR-031)
  before storage.
- Stored as a `PrescriptionDocument` — a dedicated model separate from the
  `Document`/`DocumentReference` pipeline.
- Never processed through OCR, classification, or extraction (no `ocr_stage.delay`).

### 3. Three owner decisions

These decisions were made by the project owner and are not subject to further
debate within implementation:

#### 3a. Dedicated `PrescriptionDocument` section, separate from Documents/OCR

Prescriptions are not uploaded files — they are system-generated artifacts. They
live in their own API namespace (`/api/prescriptions/{id}/document`), their own
frontend section ("Prescricoes"), and their own database model. They do not appear
in the Document vault, are not processed by the AI pipeline, and are not subject
to Document retention policies.

#### 3b. Local hard-delete with tombstone on patient erasure

When a Patient is erased (GDPR Article 17), prescription data is hard-deleted as
part of the cascade: `PrescriptionItem`, `PrescriptionDocument` (including the
encrypted blob), and `Prescription` rows are removed. A single tombstone
AuditLog entry records that erasure occurred.

**Tension with legal retention:** Issued prescriptions are legal records. A
prescription signed and issued through Memed exists as a PDF on the patient's
device and in Memed's systems. Hard-deleting the local copy in OpenAvisio does
not erase those external copies. The erasure claim is honest: OpenAvisio removes
its own copy and any reference to it, but cannot recall what has been downloaded,
printed, or forwarded. This mirrors the existing position for shared files
(ADR-017, ADR-021): external copies survive.

#### 3c. Only the User linked to the configured Prescriber may issue

The Organization has exactly one `Prescriber` record (singleton). A single User
is linked to it as the authorized issuer. Only that User may:

- Start a Memed session (`POST /api/prescriptions/{id}/memed-session`)
- Capture a signed PDF (`POST /api/prescriptions/{id}/capture`)

Other Users with Caregiver access to the Patient can create and edit draft
prescriptions, but cannot issue them. This is enforced at the API layer (403 if
`user.id != prescriber.user_id`).

### 4. Domain model

Four new models, all following `BaseModel`/`OwnedResource` conventions:

- **`Prescriber`** (`prescribers`, `BaseModel`): singleton per Organization with
  fixed ID `00000000-0000-0000-0000-000000000001`. Stores the prescriber's
  professional data (name, board registration, CPF encrypted with master KEK,
  contact info) and Memed-specific fields (`memed_user_id`, `memed_status`).
  CPF is encrypted at rest and masked in API responses (`cpf_last4`).

- **`Prescription`** (`prescriptions`, `OwnedResource`): per-Patient record with
  status machine (`draft -> issued | failed`, `failed -> draft`, any -> `deleted`).
  Carries optimistic concurrency (`version` integer, compare-and-swap on write).
  Items are a local draft snapshot; the authoritative content is the signed PDF.

- **`PrescriptionItem`** (`prescription_items`, `BaseModel`): a line item in a
  prescription draft (medication name, posology, quantity). Local scratch only
  — the issued PDF is the source of truth.

- **`PrescriptionDocument`** (`prescription_documents`, `BaseModel`): the
  archived signed PDF. Stores the encrypted blob path, hash (sha256 of the
  original), encryption metadata (`encrypted_dek`, `kek_version`), and
  Memed-originated metadata (`memed_prescription_id`, `signed` flag from event,
  `digital_link`, `unlock_code`).

### 5. Erasure and retention

**Patient erasure** extends the cascade (ADR-017) to include all four
prescription models. The `PrescriptionDocument`'s storage blob is deleted
synchronously. A tombstone AuditLog entry is written.

**User erasure** (GDPR Article 17 for the prescriber): if the erased User is
the linked prescriber, the `Prescriber` record is **not** deleted (it is a
legal record). Instead, PII fields are anonymized (`given_name`/`family_name`
to `[erased]`, `cpf_encrypted`/`cpf_last4`/`birth_date`/`email`/`phone` to
null), while professional data (`board_code`, `board_number`, `board_state`)
is preserved — these are public professional credentials that appear on issued
prescriptions and cannot be retroactively removed from external copies.

**Retention purge** explicitly excludes prescriptions. The governance module
does not register prescription models in `CATEGORY_MODELS`, so the automatic
retention purge never touches them. This is a deliberate choice: issued
prescriptions are legal records that must not be automatically deleted by a
retention schedule.

## Consequences

**Good:**
- OpenAvisio stays out of the SNCR, ICP-Brasil signing, and PDF layout business
  — all delegated to Memed, which is the established platform for this in Brazil.
- The prescription domain is cleanly separated from the Document pipeline: no
  OCR, no classification, no extraction, no risk of the AI pipeline misreading
  a prescription.
- Per-patient encryption covers prescriptions consistently with the existing
  document encryption strategy (ADR-031).
- The erasure cascade is honest about its limits: local copy gone, external
  copies acknowledged as outside reach.

**Trade-offs:**
- The Organization must have a BirdID certificate (BYOC) and a Memed partner
  agreement. This is a dependency on external services that the rest of
  OpenAvisio does not have.
- The SNCR number is not available as structured data — it lives only in the
  PDF. Any feature that needs to query or display the SNCR number must parse
  the PDF or extract it from the rendered document.
- The `prescricaoImpressa` event payload is unverified at runtime; the
  defensive adapter may fail on unexpected payload shapes, requiring a `retry`
  flow.
- Memed's homologation environment has limited availability (offline nights and
  weekends), which constrains manual end-to-end testing.

**Regulatory:**
- Issuing prescriptions moves OpenAvisio outside the current "not a medical device"
  positioning (see `docs/regulatory-positioning.md`). The prescription
  feature is closer to what a medical device is under EU MDR 2017/745 and
  Brazilian ANVISA regulations. This ADR does not assert compliance. A formal
  regulatory review is recommended before any production deployment of the
  prescription feature.