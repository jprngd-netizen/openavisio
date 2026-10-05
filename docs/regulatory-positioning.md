# OpenAvisio - Regulatory positioning

*Positioning summary for funding reviewers and partners. **Not legal advice** -
a formal regulatory/legal assessment is recommended before any market or medical
claims. This documents our current stance and the open questions a reviewer will
ask.*

## Short version

OpenAvisio is an **information-management and decision-support tool for
caregivers**, not a medical device. It **organises, transcribes and retrieves a
patient's own existing records** and surfaces information the patient's own
clinicians already produced. It does **not** diagnose, treat, monitor, predict,
or generate new medical advice.

## Medical Device (EU MDR 2017/745)

The MDR treats software as a medical device when it has a medical *purpose*
(diagnosis, prevention, monitoring, prediction, treatment). Our position:

- **In scope of "not a medical device":** OCR/transcription of documents,
  structuring and search of the patient's own data, plain-language summaries of
  what a document says, and surfacing recommendations **that the treating
  clinician wrote** (we extract and display them - we do not author medical
  recommendations).
- **What we deliberately avoid** (would risk MDSW classification): generating
  diagnoses, therapy suggestions, dosage advice, risk scores, alerts on clinical
  values, or any output a user would rely on for a medical decision that the
  software itself produced.
- **Guardrails in product & copy** (as they ACTUALLY exist, #117):
  - The chat system prompt forbids assessment outright: no "is this value
    normal/worrying", no ranking by urgency, no diagnosis, prognosis, dosage or
    recommendation of its own, no "you should see a doctor". It may quote a
    recommendation **a clinician wrote**, attributed. Asked to judge, it declines
    and points to the treating clinician.
  - Every chat answer carries a disclaimer **in the API response**, so no client
    can quietly drop it. Until #117 this document claimed such a disclaimer
    existed while the code had none — a guardrail that lives only in a document
    is worse than none, because it makes us believe we are covered.
  - The chat UI itself is currently **removed** from the app; only the backend
    endpoints remain.
  - Every screen that shows extracted data (summaries, lab values, diagnoses,
    medications) states that it was read out by OCR and a language model, that
    both make mistakes, and that the original document is what counts.

## Precedent: the abnormal-value chips (2026-07, #113)

The documents list briefly surfaced lab values outside their reference range:
it scored them by deviation, **picked the four worst**, and showed those as
red/amber chips. Removed — not because comparing numbers is forbidden, but
because selecting a subset and highlighting it is emphasis the software itself
authors. Nothing in the document says "these four matter most".

**What stays, deliberately:** the lab pages colour a value that falls outside
the range **printed on that same report** (#69). The lab flags those values
itself ("H"/"L"); showing that faithfully is presentation, not a new claim.
Removing it was proposed and rejected — it is established, useful behaviour and
the call is not ours to make unilaterally.

**Open question for the regulatory advisor** (do not decide this in a PR):
where the line sits between *reproducing* a document's own out-of-range marking
and *authoring* an assessment. Working rule until then:

- Do **not add** new features that select, rank, or warn on clinical values.
- Do **not remove** existing behaviour on an engineer's own reading of the MDR.

**Open question for a formal assessment:** where exactly the line sits for the
AI assistant's summarisation/answering. This is the one area to validate with a
regulatory advisor; the mitigations above are designed to stay on the
non-device side.

## DiGA (Digitale Gesundheitsanwendung, §33a SGB V)

- DiGA reimbursement requires being a **low-risk medical device** (roughly class
  I / IIa) listed by BfArM. Since we position OpenAvisio as **not** a medical
  device, DiGA is **not** a current path.
- It remains a **possible future option** *if* a specifically scoped, clearly
  medical feature were built and deliberately taken through MDR + BfArM. Out of
  scope for now; noted so reviewers know we've considered it.

## GDPR / data protection

- Health data is a **special category** (Art. 9 GDPR). OpenAvisio is
  **GDPR-native by design**: lawful-basis tracking, consent-based sharing,
  Article 17 erasure cascades, per-patient envelope encryption with
  crypto-shredding (ADR-031), retention purge, and full audit logging.
- **Self-hosting model:** the operator (a household or a care organisation) is
  typically the data **controller**; OpenAvisio is the software they run. This
  keeps data under the user's control and simplifies the processor/controller
  story compared with a cloud SaaS.

## EU AI Act

- If OpenAvisio is **not** a medical device, it is unlikely to fall in the
  AI Act's **high-risk** category (which centres on AI as a safety component of
  regulated products). It would then sit under **transparency obligations** for
  AI systems - clearly disclosing to users that they are interacting with an AI
  assistant, which we do.
- If the product were ever repositioned as a medical device, high-risk
  obligations would need re-evaluation.

## Summary for reviewers

- **Not a medical device / not a DiGA** as currently scoped - an assistive,
  document-grounded information tool.
- **Privacy is a feature, not an afterthought** - GDPR-native, self-hostable,
  data under the user's control.
- **Clear guardrails** keep the AI on the "understand your own records" side of
  the line, with disclaimers and citations.
- A **formal regulatory review** is planned as the product matures (budgeted
  under legal/data-protection).

## Prescription issuing (Memed integration, 2026-10-05)

Issuing medical prescriptions through the Memed integration (ADR-036) moves
OpenAvisio into territory that the "not a medical device" positioning above
does **not** cover. Generating and issuing a signed prescription document is
a regulated act in most jurisdictions, including Brazil (ANVISA RDC 1000/25)
and the EU (MDR 2017/745).

**This feature is outside the current "not a medical device" claim and
requires a formal regulatory review before any production deployment.** The
review should determine whether issuing prescriptions through the platform
triggers medical device classification, and if so, what conformity assessment
route applies. This note does not constitute legal advice or a compliance
assertion.
