# OpenAvisio

An open-source AI health assistant for caregivers — family members, nurses, and anyone responsible for another person's care. OpenAvisio helps caregivers understand, manage, and act on a patient's health records through a conversational AI interface. The document vault, Processing Pipeline, and structured clinical data exist to ground the AI Health Assistant in accurate, patient-specific data.

## Language

### System

**Organization**:
The entity that runs an OpenAvisio Deployment. Always exactly one per Deployment — a care home, a clinic, a household, or an individual in a homelab setup.
_Avoid_: tenant, instance, workspace

**Deployment**:
A complete running OpenAvisio stack (frontend, backend, AI service, database) serving exactly one Organization. Deployments are fully isolated from each other; there is no multi-tenancy. In user-facing UI text, "server" is acceptable ("connect to your server") — the canonical term applies to code, docs, and design discussions.
_Avoid_: instance, installation, server (in domain language)

### People

**Patient**:
The person whose health data is stored. A Patient is not a system login — they are the subject of all clinical data (observations, conditions, medications, documents, etc.).
_Avoid_: subject, record owner, health record

**User**:
A person with a system login. A User manages one or more Patient records. A User and a Patient can be the same physical person (self-management).
_Avoid_: account, member, actor

**Coordinator**:
A system role. A Coordinator can onboard new Patients and assign access to other Users. One person can be both a Coordinator and a Caregiver for the same Patient.
_Avoid_: manager, staff manager, system manager

**Caregiver**:
A person responsible for a specific Patient's day-to-day care. Caregiver is a patient-level relationship, not a system role — any User can be a Caregiver for a Patient regardless of their system role. Covers family members, nurses, paid carers, legal guardians, and anyone else in a Patient's care circle. A legal relationship (power of attorney, guardianship) is a flag on the Caregiver's access grant (`is_legal_representative`), recorded for compliance, not a separate access path (ADR 027).
_Avoid_: family member, nurse, caretaker, responsible person, representative

**Group**:
An optional, named set of Patients whose access is managed together. A Coordinator can add Users to a Group to grant them access to all Patients in it at once. Groups are a convenience shortcut — they generate access grants in bulk but do not add a separate access tier. Most homelab deployments don't need Groups; they are mainly useful in care homes or clinics managing many Patients.
_Avoid_: family, family group, care circle, ward

### Compliance

**Erasure**:
A GDPR Article 17 right-to-erasure action. Two variants:

- **Patient Erasure** — triggered by any holder of an admin-level PatientAccess grant on the Patient. Cascade hard-deletes all clinical data (Diagnoses, Medications, Measurements, Lab Results, Incidents, Events, Health Logs, Documents + storage files, Document embeddings, Recommendations, AI Health Assistant messages), all access records (Caregiver links, PatientAccess grants, pending invites), all Shares and Share declines for that Patient, all external Document Share Links and their items, and all prior AuditLog entries for that Patient's data (including external share-link access logs). A single tombstone AuditLog entry is written recording that erasure occurred. Immediate and irreversible. (Files a Purpose Manager already downloaded and forwarded externally are outside OpenAvisio's reach.)

- **User Erasure** — triggered by an admin or the User themselves. Anonymises all PII fields on the User record and hard-deletes login credentials (PasskeyCredentials) and access grants (GroupMemberships, PatientAccess). Blocked while the User is the last admin-level grant holder of any Patient — grant someone else admin level or erase those Patients first. A tombstone AuditLog entry is written and existing AuditLog entries for that User have `user_name` scrubbed to `[erased]`.

_Avoid_: deletion, account deletion, data removal, right to be forgotten

### Licensing

**License**:
A signed entitlement file that determines which Tier an Organization operates under. Uploaded by an admin via the admin UI. Absence of a License means the Organization operates under the Personal tier defaults.
_Avoid_: license key, activation key, serial number

**Tier**:
The operating mode of an Organization — either Personal (default, no License required, AGPL, limited to 10 Patients and 3 Users) or Commercial (requires a valid License, unlimited Patients and Users, additional features). A commercial License that has expired but is within a 30-day grace period still grants commercial limits. After the grace period, the Organization falls back to Personal limits.
_Avoid_: plan, edition, subscription

### AI & Processing

**Processing Pipeline**:
The automated AI workflow that runs when a Document is uploaded. Produces a Summary, Recommendations, and extracted clinical data (Diagnoses, Medications, Measurements, Lab Results) which go directly into the Patient's record. Also proposes Events for appointments and dates found in the Document (past and future) — these require User acceptance before appearing on the health timeline.
_Avoid_: AI pipeline, extraction pipeline, OCR pipeline

**Summary**:
A human-readable overview of a Document produced by the Processing Pipeline.
_Avoid_: abstract, description, overview

**Recommendation**:
An extracted next step or follow-up found in a Document — e.g. "return in three months", "take medication daily". Produced by the Processing Pipeline.
_Avoid_: suggestion, finding, action item

**AI Health Assistant**:
A conversational interface that answers questions about a Patient's health records using AI. Searches across all clinical data and Documents to generate answers.
_Avoid_: chat, RAG chat, AI assistant, health bot

### Clinical data

**Document**:
An uploaded medical file (PDF, image, scan). The source of truth from which clinical data is extracted. Processed through the AI pipeline to produce structured clinical data. Key metadata: `issued_date` (the date printed on the document, populated by the Processing Pipeline, overridable by the User) and `correspondent` (the issuing entity — see Correspondent).
_Avoid_: DocumentReference, record, file, attachment

**Correspondent**:
The named entity that issued or sent a Document — a hospital, clinic, lab, GP practice, or insurer. Correspondents are reusable across Documents within an Organization (not free-text per document). A Document may have at most one Correspondent.
_Avoid_: sender, provider, issuer, source

**Diagnosis**:
A medical condition or disease attributed to a Patient. Extracted from Documents or entered manually.
_Avoid_: Condition, problem, issue

**Medication**:
A drug or treatment a Patient is taking or has taken, including dosage and period. Medications can be entered manually or extracted by the Processing Pipeline.
_Avoid_: MedicationStatement, drug, prescription

**Measurement**:
A physical metric recorded for a Patient over time — weight, height, blood pressure, temperature, oxygen saturation, etc. Used to track growth and physical development as well as health trends.
_Avoid_: Observation, vital sign, vital

**Lab Result**:
An outcome from a clinical test performed on a sample — blood test, urine test, biopsy, etc. Reported by a lab or extracted from a Document.
_Avoid_: Observation, test result, lab value

**Incident**:
An adverse event involving a Patient — a seizure, fall, allergic reaction, or other notable occurrence. Includes context such as suspected triggers and correlated Medications. The date of the earliest Incident of a given type is its _onset_ — no separate field is needed; onset is derived by querying the first recorded Incident.
_Avoid_: event, episode, adverse event

**Event**:
A single entry on a Patient's health timeline — an appointment, hospital stay, therapy session, medication plan record, or any other health-related occurrence past or future. Events can be linked to Documents. Events proposed by the Processing Pipeline require User acceptance before appearing on the timeline.

Event categories include **milestone**: a developmental achievement (first word, first steps, first solid food, toilet training, etc.) benchmarked against expected age ranges. Milestones are specific to pediatric and developmental contexts and carry a developmental domain (motor, speech, cognitive, social). Do not use milestone for adverse medical firsts — those are Incidents.
_Avoid_: CalendarEvent, appointment, entry, item

**Health Log**:
A Patient's self-reported daily record — mood, pain level, sleep, bowel movement, medication compliance, and other subjective observations. Structured for trend tracking, not free-form journaling.
_Avoid_: DiaryEntry, diary, journal, daily log

### Prescription

**Prescriber**:
The licensed healthcare professional authorized to issue prescriptions for an Organization. Exactly one per Organization (singleton model with fixed ID). Stores the prescriber's professional registration (board code, number, state), contact information, and CPF (encrypted at rest, masked in API). A single User is linked as the authorized issuer.
_Avoid_: doctor, physician, healthcare provider, issuer

**Prescription**:
A draft or issued medical prescription for a Patient. Has a status machine: `draft` (editable, local scratch), `issued` (signed PDF captured from Memed, read-only), `failed` (capture error, retryable), `deleted` (deleted in Memed). The authoritative content of an issued Prescription is the signed PDF stored in the linked PrescriptionDocument. Items on a Prescription are a local snapshot only.
_Avoid_: receita, prescricao, order

**PrescriptionDocument**:
The archived signed PDF of an issued Prescription. Downloaded from Memed at capture time, encrypted with the patient's KEK (per-patient envelope encryption, ADR-031), and stored separately from the Document vault. Never processed through OCR or the AI Pipeline. Carries the Memed prescription ID, a `signed` flag from the event payload, and optional digital link data.
_Avoid_: signed prescription, PDF receipt, document

**PrescriptionItem**:
A single line item on a Prescription draft — medication name, posology, and quantity. Local scratch only; the issued PDF is the authoritative record. Items are replaceable as a set on each autosave.
_Avoid_: medication line, drug item, entry

### Data sharing

**Sharing Purpose**:
A named reason for which a User collects Patient files — typically a research study or registry submission. It owns the Share Requests sent out and the resulting Shares. A single Document can be shared to several Sharing Purposes independently, each with its own consent. It carries an **identification mode** set by the Purpose Manager: _identified_ (the Patient's name is shown alongside each shared file) or _anonymous_ (the Purpose Manager sees only a stable per-Patient pseudonym, never the name). Anonymous is pseudonymity at the metadata level only — file _contents_ are never altered and may still carry identifying information. (Distinct from the FHIR `survey` observation category used in exports, which is unrelated.)
_Avoid_: study, survey, project, campaign, research purpose

**Purpose Manager**:
Any Coordinator or admin acting on a Sharing Purpose. A Sharing Purpose belongs to the Organization, not to one person: any Coordinator/admin can create it, manage it, and download the files shared to it; the creating User is recorded only for accountability, and staff turnover orphans nothing. Managing a Sharing Purpose grants access solely to the files explicitly shared to that Purpose — nothing else in a Patient's record — and is independent of any Caregiver access the same person may hold.
_Avoid_: purpose-owner, requester, collector, study owner, researcher

**Share Request**:
The org-wide ask carried by a Sharing Purpose — "this study wants a kind of data (e.g. EEG)" — surfaced to every Caregiver against each of their Patients. It is _not_ materialised per Patient: a request is the derived "open" state of a Sharing Purpose for a Patient that has no response yet. Only responses are stored (a Share when fulfilled, a decline marker when refused); the Sharing Purpose's activation time records when everyone was asked. The Caregiver decides which Document(s) fulfil it.
_Avoid_: invitation, data request, ask

**Share**:
A consented link between one Document and one Sharing Purpose that lets a Purpose Manager access and download that file. Created when a Caregiver selects a Document and consents in response to a Share Request; the consenting User and time are always recorded. A Share is active or revoked, and its access also ends if the underlying Document is deleted. Closing the Sharing Purpose stops new Shares but leaves existing Shares downloadable. Revocation ends future access in OpenAvisio but cannot recall files a Purpose Manager has already downloaded and forwarded externally.
_Avoid_: grant, data share, file share, access grant

**Document Share Link**:
A time-limited, read-only, anonymous link a Caregiver generates to give an _external_ specialist (a doctor or therapist with no account) access to a chosen set of a Patient's Documents — the outbound counterpart to the inbound Sharing Purpose flow. Whoever holds the link URL can view and download the shared Documents (name, date of birth, and each Document's own summary + extracted data are shown) until it expires (7/30/90 days) or is revoked. Only the token's hash is stored; the link is shown once at creation. Creating one is reserved for a Patient's own Caregivers (active legal representative / non-staff with access) — staff acting only in an admin/manager capacity cannot. Every external access is audit-logged (recipient IP + user-agent); Patient Erasure cascades the links, their items, and those access logs. See ADR-021.
_Avoid_: public link, guest access, external share (as a noun for the Study Share)

## Example dialogue

> **Dev:** We need a way for the nurse to see all of Emma's records.
> **Domain expert:** Add her as a Caregiver for that Patient. She'll have access to all clinical data — Diagnoses, Medications, Measurements, Events.
>
> **Dev:** Emma's mum uploaded a neurology report. What happens?
> **Domain expert:** The Processing Pipeline runs — it produces a Summary, any Recommendations, and extracted clinical data. If the report mentions a follow-up appointment, the pipeline proposes an Event. The Caregiver accepts it and it appears on the health timeline.
>
> **Dev:** The care home has 30 residents. Do we grant the night nurse access to each Patient individually?
> **Domain expert:** No — create a Group for the ward, add all Patients to it, then add the nurse. That generates the access grants in bulk.
>
> **Dev:** Emma's grandmother has power of attorney. Does she need a different account type?
> **Domain expert:** No — she's a Caregiver like anyone else. The legal relationship gets recorded as an attribute on her access, but her permissions are the same.
>
> **Dev:** Emma had her first seizure at age 3. How do we record that, and how do we find when it first happened later?
> **Domain expert:** Record it as an Incident. Onset is the date of the earliest seizure Incident — no separate field. Just query the first one.
>
> **Dev:** Emma's mum wants to record when Emma said her first word.
> **Domain expert:** That's a milestone Event — category milestone, domain speech. Not an Incident, not a free-form note.

## Domain term → current code term mapping

The domain vocabulary above is the authoritative language for issues, ADRs, and PR descriptions. The codebase was written before some terms were finalised and uses different names in several places. When reading or modifying code, map as follows:

| Domain term | Code term | Notes |
|---|---|---|
| Group | `Family` / `FamilyMembership` | The domain term was settled after the model was built. A rename is tracked but not yet done. |
| Caregiver | `FamilyMembership` + `PatientAccess` | Family membership is the primary carrier; direct grants via `PatientAccess` cover non-family caregivers. |
| Coordinator | `manager` role | The `admin` role has all Coordinator permissions plus system administration (user management, org settings). Neither role grants any clinical data access — that always requires a PatientAccess grant; creating a Patient auto-creates a revocable admin-level grant for the creator (ADR 025/026). |
| Measurement / Lab Result | `Observation` | Both are stored as `Observation` rows; `category` distinguishes them at query time. |
| Diagnosis | `Condition` | SQLAlchemy model is `Condition`; API path is `/conditions`. |
| Health Log | `DiaryEntry` | SQLAlchemy model is `DiaryEntry`; API path is `/diary`. |
| Event | `CalendarEvent` | SQLAlchemy model is `CalendarEvent`; API path is `/calendar/events`. |

Do not use the code term in new written communication (issues, ADRs, PR descriptions). Do use it when referring to specific files, models, or routes.

