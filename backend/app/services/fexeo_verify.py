"""FExEO-SUS verify routing (R4 Fase 3).

When a document is classified as one of the FExEO obstetric-nursing instruments,
``POST /documents/{id}/verify`` materialises the matching clinical records
(``Pregnancy`` / ``PregnancyVisit`` / ``NursingCare`` / ``NewbornRecord`` /
``PregnancyOutcome``) instead of the generic extraction path.

Design rules (plan ``docs/plans/2026-10-11-fexeo-enfermagem-obstetrica.md``):

* **IA sugere → humano confirma** — nothing is written before the verify call.
* **OCR is a suggestion, never a 500** — every incoming sub-object is sanitised
  field by field against the real model columns; unknown keys and unparseable
  values are silently dropped. A strange value can never crash the request.
* **Formativo ≠ prontuário** — ``fexeo_competency_assessment`` materialises
  *nothing* clinical (the caller skips the whole clinical block).
* **Proveniência** — every record created here carries ``document_reference_id``
  so a re-verify retracts (soft-deletes) only what *this* document created,
  never another document's data.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetimes import parse_date, parse_datetime
from app.models.document import DocumentReference
from app.models.newborn_record import NewbornRecord
from app.models.nursing_care import (
    NursingCare,
    NursingCareCategory,
    NursingCareSubcategory,
)
from app.models.pregnancy import (
    LIVE_BIRTH_OUTCOMES,
    OUTCOME_STATUS,
    Pregnancy,
    PregnancyOutcome,
    PregnancyOutcomeType,
    PregnancyStatus,
    PregnancyVisit,
)
from app.models.user import User

# Classification keys emitted by the aiservice classifier.
CLASSIFICATION_PRENATAL = "fexeo_prenatal_monitoring"
CLASSIFICATION_LABOR = "fexeo_labor_birth_record"
CLASSIFICATION_POSTPARTUM = "fexeo_postpartum_rooming_record"
CLASSIFICATION_SEXUAL = "fexeo_sexual_reproductive_visit"
CLASSIFICATION_COMPETENCY = "fexeo_competency_assessment"

# Clinical instrument types — these materialise patient data.
FEXEO_CLINICAL = frozenset(
    {
        CLASSIFICATION_PRENATAL,
        CLASSIFICATION_LABOR,
        CLASSIFICATION_POSTPARTUM,
        CLASSIFICATION_SEXUAL,
    }
)
# Every recognised type (clinical + formative).
FEXEO_ALL = FEXEO_CLINICAL | {CLASSIFICATION_COMPETENCY}

# Keys never written from the payload: identity, ownership, tenancy, provenance
# and the episode/outcome links are set by the router, never by OCR.
_PROTECTED_KEYS = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "is_deleted",
        "owner_id",
        "patient_id",
        "pregnancy_id",
        "pregnancy_outcome_id",
        "document_reference_id",
        "condition_id",
    }
)

_LIVE_BIRTH_VALUES = frozenset(e.value for e in LIVE_BIRTH_OUTCOMES)

_TRUE = {"true", "1", "sim", "s", "yes", "y", "verdadeiro"}
_FALSE = {"false", "0", "nao", "não", "n", "no", "falso"}


def _coerce(value: Any, column) -> Any:
    """Best-effort coercion of a raw OCR value to a column's Python type.

    Returns ``None`` (→ the key is dropped) when the value cannot be read as the
    column's type. Never raises.
    """
    if value is None:
        return None
    typ = column.type
    try:
        if isinstance(typ, DateTime):
            return parse_datetime(value)
        if isinstance(typ, Date):
            return parse_date(value)
        if isinstance(typ, Boolean):
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            token = str(value).strip().lower()
            if token in _TRUE:
                return True
            if token in _FALSE:
                return False
            return None
        if isinstance(typ, Integer):
            if isinstance(value, bool):
                return None
            return int(value)
        if isinstance(typ, (Numeric, Float)):
            return float(value)
        if isinstance(typ, JSONB):
            if isinstance(value, (dict, list, str, int, float, bool)):
                return value
            return None
        if isinstance(typ, (String, Text)):
            return value if isinstance(value, str) else str(value)
        return value
    except (TypeError, ValueError):
        return None


def _sanitize(model, raw: Any) -> dict[str, Any]:
    """Keep only the keys the model actually has, coerced to its column types.

    Unknown keys, protected keys and unparseable values are dropped — the OCR
    payload is a suggestion, so a bad value is ignored, never fatal.
    """
    if not isinstance(raw, dict):
        return {}
    columns = model.__table__.columns
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _PROTECTED_KEYS:
            continue
        column = columns.get(key)
        if column is None:  # not a real field of the model → discard
            continue
        coerced = _coerce(value, column)
        if coerced is None:
            continue
        out[key] = coerced
    return out


def _raw_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        return None


# --------------------------------- Pregnancy ---------------------------------


async def _active_pregnancy(db: AsyncSession, patient_id: uuid.UUID) -> Pregnancy | None:
    return (
        await db.execute(
            select(Pregnancy)
            .where(
                Pregnancy.patient_id == patient_id,
                Pregnancy.status == PregnancyStatus.active.value,
                Pregnancy.is_deleted == False,  # noqa: E712
            )
            .order_by(Pregnancy.created_at.desc())
        )
    ).scalars().first()


async def _pregnancy_with_outcome(db: AsyncSession, patient_id: uuid.UUID) -> Pregnancy | None:
    return (
        await db.execute(
            select(Pregnancy)
            .join(PregnancyOutcome, PregnancyOutcome.pregnancy_id == Pregnancy.id)
            .where(
                Pregnancy.patient_id == patient_id,
                Pregnancy.is_deleted == False,  # noqa: E712
                PregnancyOutcome.is_deleted == False,  # noqa: E712
            )
            .order_by(Pregnancy.created_at.desc())
        )
    ).scalars().first()


async def _most_recent_pregnancy(db: AsyncSession, patient_id: uuid.UUID) -> Pregnancy | None:
    return (
        await db.execute(
            select(Pregnancy)
            .where(
                Pregnancy.patient_id == patient_id,
                Pregnancy.is_deleted == False,  # noqa: E712
            )
            .order_by(Pregnancy.created_at.desc())
        )
    ).scalars().first()


async def _resolve_pregnancy(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    owner_id: uuid.UUID,
    preg_payload: Any,
    delivery: bool,
) -> Pregnancy:
    """Resolve the target episode, or create one from the sub-object's fields.

    ``delivery`` selects the resolution order for labor/postpartum instruments
    (prefer the episode an outcome already closed); otherwise the active episode
    wins so a re-verify never opens a second gestation.
    """
    payload = _sanitize(Pregnancy, preg_payload)
    cited = _raw_uuid((preg_payload or {}).get("pregnancy_id") if isinstance(preg_payload, dict) else None)
    if cited is not None:
        found = await db.get(Pregnancy, cited)
        if found is not None and not found.is_deleted and found.patient_id == patient_id:
            return found

    if delivery:
        found = await _pregnancy_with_outcome(db, patient_id) or await _active_pregnancy(db, patient_id)
        if found is None:
            found = await _most_recent_pregnancy(db, patient_id)
        if found is not None:
            return found
    else:
        found = await _active_pregnancy(db, patient_id)
        if found is not None:
            return found

    # Vínculo por DUM: an episode already anchored on the same LMP (any status)
    # is the same gestation — reusing it avoids the unique-constraint duplicate.
    lmp = payload.get("lmp_date")
    if lmp is not None:
        found = (
            await db.execute(
                select(Pregnancy).where(
                    Pregnancy.patient_id == patient_id, Pregnancy.lmp_date == lmp
                )
            )
        ).scalars().first()
        if found is not None:
            return found

    fields = {"status": PregnancyStatus.active.value}
    fields.update(payload)
    pregnancy = Pregnancy(patient_id=patient_id, owner_id=owner_id, **fields)
    db.add(pregnancy)
    await db.flush()
    return pregnancy


# ------------------------------- Prenatal visit -------------------------------


async def _upsert_visit(
    db: AsyncSession,
    *,
    doc: DocumentReference,
    pregnancy: Pregnancy,
    owner_id: uuid.UUID,
    visit_payload: Any,
) -> None:
    """Create (or fill the empty fields of) the visit of ``visit_date``.

    Dedupe is by ``(pregnancy_id, visit_date)``. A visit created by this document
    is overwritten on re-verify; one owned by another document only receives
    values it did not yet have (never overwritten).
    """
    data = _sanitize(PregnancyVisit, visit_payload)
    visit_date = data.get("visit_date") or parse_date(
        (visit_payload or {}).get("date") if isinstance(visit_payload, dict) else None
    )
    if visit_date is None:
        visit_date = doc.issued_date
    if visit_date is None:
        return  # no date to anchor or dedupe on — skip rather than guess
    data["visit_date"] = visit_date

    existing = (
        await db.execute(
            select(PregnancyVisit).where(
                PregnancyVisit.pregnancy_id == pregnancy.id,
                PregnancyVisit.visit_date == visit_date,
            )
        )
    ).scalars().first()
    if existing is not None:
        ours = existing.document_reference_id == doc.id
        if existing.is_deleted and not ours:
            return
        for key, value in data.items():
            if ours or getattr(existing, key, None) is None:
                setattr(existing, key, value)
        existing.is_deleted = False
        if ours:
            existing.document_reference_id = doc.id
        return

    db.add(
        PregnancyVisit(
            pregnancy_id=pregnancy.id,
            owner_id=owner_id,
            document_reference_id=doc.id,
            **data,
        )
    )


# -------------------------------- Nursing care --------------------------------


async def _create_nursing_care(
    db: AsyncSession,
    *,
    doc: DocumentReference,
    patient_id: uuid.UUID,
    owner_id: uuid.UUID,
    pregnancy_id: uuid.UUID | None,
    payload: Any,
    default_subcategory: str,
) -> None:
    data = _sanitize(NursingCare, payload)
    occurred = data.get("occurred_at") or doc.issued_date
    occurred = parse_datetime(occurred)
    if occurred is None:
        return  # occurred_at is NOT NULL — skip rather than fabricate a date
    data["occurred_at"] = occurred

    subcategory = data.get("subcategory") or default_subcategory
    try:
        subcategory = NursingCareSubcategory(subcategory).value
    except ValueError:
        subcategory = default_subcategory
    data["subcategory"] = subcategory

    category = data.get("category")
    try:
        category = NursingCareCategory(category).value if category else None
    except ValueError:
        category = None
    if category is None:
        category = (
            NursingCareCategory.obstetric.value
            if pregnancy_id is not None
            else NursingCareCategory.general.value
        )
    data["category"] = category
    # A gestation link is only valid in the obstetric context (OB-5 invariant).
    link = pregnancy_id if category == NursingCareCategory.obstetric.value else None

    db.add(
        NursingCare(
            patient_id=patient_id,
            owner_id=owner_id,
            document_reference_id=doc.id,
            pregnancy_id=link,
            **data,
        )
    )


# ------------------------------ Pregnancy outcome ------------------------------


async def _resolve_outcome(
    db: AsyncSession,
    *,
    doc: DocumentReference,
    pregnancy: Pregnancy,
    owner_id: uuid.UUID,
    payload: Any,
) -> PregnancyOutcome | None:
    """Create/refresh the outcome that closes the episode, or return the live one.

    With no usable ``outcome`` sub-object the existing live outcome (if any) is
    returned so a newborn record can still be attached to it.
    """
    data = _sanitize(PregnancyOutcome, payload)
    outcome_type = data.get("outcome_type")
    try:
        outcome_type = PregnancyOutcomeType(outcome_type).value if outcome_type else None
    except ValueError:
        outcome_type = None
    outcome_date = data.get("outcome_date")

    existing = (
        await db.execute(
            select(PregnancyOutcome).where(PregnancyOutcome.pregnancy_id == pregnancy.id)
        )
    ).scalars().first()

    if outcome_type is None or outcome_date is None:
        # Nothing new to register: hand back the live outcome, if any.
        if existing is not None and not existing.is_deleted:
            return existing
        return None

    data["outcome_type"] = outcome_type
    data["outcome_date"] = outcome_date

    if existing is not None:
        ours = existing.document_reference_id == doc.id
        if existing.is_deleted and not ours:
            return None
        for key, value in data.items():
            if ours or getattr(existing, key, None) is None:
                setattr(existing, key, value)
        existing.is_deleted = False
        if ours:
            existing.document_reference_id = doc.id
        outcome = existing
    else:
        outcome = PregnancyOutcome(
            pregnancy_id=pregnancy.id,
            owner_id=owner_id,
            document_reference_id=doc.id,
            **data,
        )
        db.add(outcome)

    # Registering the outcome closes the episode (OB-3): terminal status + date.
    try:
        pregnancy.status = OUTCOME_STATUS[PregnancyOutcomeType(outcome.outcome_type)].value
    except (KeyError, ValueError):
        pass
    if outcome.outcome_date is not None:
        pregnancy.ended_at = outcome.outcome_date
    return outcome


async def _upsert_newborn(
    db: AsyncSession,
    *,
    doc: DocumentReference,
    outcome: PregnancyOutcome,
    owner_id: uuid.UUID,
    payload: Any,
) -> None:
    """Create or merge the newborn record of an outcome (1:1)."""
    data = _sanitize(NewbornRecord, payload)
    existing = (
        await db.execute(
            select(NewbornRecord).where(NewbornRecord.pregnancy_outcome_id == outcome.id)
        )
    ).scalars().first()
    if existing is not None:
        ours = existing.document_reference_id == doc.id
        if existing.is_deleted and not ours:
            return
        for key, value in data.items():
            if ours or getattr(existing, key, None) is None:
                setattr(existing, key, value)
        existing.is_deleted = False
        if ours:
            existing.document_reference_id = doc.id
        return

    db.add(
        NewbornRecord(
            pregnancy_outcome_id=outcome.id,
            owner_id=owner_id,
            document_reference_id=doc.id,
            **data,
        )
    )


# ------------------------------- Retraction -------------------------------


async def retract_fexeo(db: AsyncSession, doc_id: uuid.UUID) -> None:
    """Soft-delete the FExEO records this document created (re-verify idempotency).

    Mirrors the Observation/Condition/etc. retraction: only rows whose provenance
    points at *this* document are touched — another document's data is never
    retracted.
    """
    for model in (PregnancyVisit, NursingCare, NewbornRecord, PregnancyOutcome):
        rows = await db.execute(
            select(model).where(
                model.document_reference_id == doc_id,
                model.is_deleted == False,  # noqa: E712
            )
        )
        for row in rows.scalars().all():
            row.is_deleted = True


# --------------------------------- Entry point ---------------------------------


async def materialize_fexeo(
    db: AsyncSession,
    *,
    doc: DocumentReference,
    user: User,
    payload: Any,
) -> None:
    """Route a verified FExEO document to the clinical records it describes.

    A no-op for any classification that is not a FExEO clinical instrument, and
    for the formative competency assessment (which materialises nothing).
    """
    classification = doc.document_classification
    if classification not in FEXEO_CLINICAL:
        return
    data = payload if isinstance(payload, dict) else {}
    patient_id = doc.patient_id
    owner_id = user.id

    if classification == CLASSIFICATION_PRENATAL:
        pregnancy = await _resolve_pregnancy(
            db,
            patient_id=patient_id,
            owner_id=owner_id,
            preg_payload=data.get("pregnancy"),
            delivery=False,
        )
        await _upsert_visit(
            db,
            doc=doc,
            pregnancy=pregnancy,
            owner_id=owner_id,
            visit_payload=data.get("prenatal_visit") or data.get("visit"),
        )
        return

    if classification == CLASSIFICATION_LABOR:
        pregnancy = await _resolve_pregnancy(
            db,
            patient_id=patient_id,
            owner_id=owner_id,
            preg_payload=data.get("pregnancy"),
            delivery=True,
        )
        await _create_nursing_care(
            db,
            doc=doc,
            patient_id=patient_id,
            owner_id=owner_id,
            pregnancy_id=pregnancy.id,
            payload=data.get("nursing_care"),
            default_subcategory=NursingCareSubcategory.labor.value,
        )
        outcome = await _resolve_outcome(
            db,
            doc=doc,
            pregnancy=pregnancy,
            owner_id=owner_id,
            payload=data.get("outcome"),
        )
        if data.get("newborn") and outcome is not None and outcome.outcome_type in _LIVE_BIRTH_VALUES:
            await _upsert_newborn(
                db, doc=doc, outcome=outcome, owner_id=owner_id, payload=data.get("newborn")
            )
        return

    if classification == CLASSIFICATION_POSTPARTUM:
        pregnancy = await _resolve_pregnancy(
            db,
            patient_id=patient_id,
            owner_id=owner_id,
            preg_payload=data.get("pregnancy"),
            delivery=True,
        )
        await _create_nursing_care(
            db,
            doc=doc,
            patient_id=patient_id,
            owner_id=owner_id,
            pregnancy_id=pregnancy.id,
            payload=data.get("nursing_care"),
            default_subcategory=NursingCareSubcategory.postpartum.value,
        )
        outcome = await _resolve_outcome(
            db,
            doc=doc,
            pregnancy=pregnancy,
            owner_id=owner_id,
            payload=data.get("outcome"),
        )
        if data.get("newborn") and outcome is not None and outcome.outcome_type in _LIVE_BIRTH_VALUES:
            await _upsert_newborn(
                db, doc=doc, outcome=outcome, owner_id=owner_id, payload=data.get("newborn")
            )
        return

    if classification == CLASSIFICATION_SEXUAL:
        await _create_nursing_care(
            db,
            doc=doc,
            patient_id=patient_id,
            owner_id=owner_id,
            pregnancy_id=None,
            payload=data.get("nursing_care"),
            default_subcategory=NursingCareSubcategory.sexual_reproductive.value,
        )
        return
