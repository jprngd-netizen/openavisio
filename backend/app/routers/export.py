import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.calendar import CalendarEvent
from app.models.chat import ChatMessage
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.recommendation import Recommendation
from app.models.diary import DiaryEntry
from app.models.user import User

router = APIRouter()

_PATIENT_REF = lambda pid: {"reference": f"urn:uuid:{pid}"}  # noqa: E731


@router.get("/patients/{patient_id}/export/fhir")
async def export_fhir(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)

    entries = []

    # --- Patient ---
    patient_result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )
    patient = patient_result.scalar_one_or_none()
    if patient:
        entries.append({
            "fullUrl": f"urn:uuid:{patient.id}",
            "resource": {
                "resourceType": "Patient",
                "id": str(patient.id),
                "name": [{"family": patient.family_name, "given": [patient.given_name]}],
                "birthDate": str(patient.birth_date) if patient.birth_date else None,
                "gender": patient.gender,
            },
        })

    pid = patient_id

    # --- Observations (Measurements + Lab Results) ---
    for obs in (await db.execute(
        select(Observation).where(Observation.patient_id == pid, Observation.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{obs.id}",
            "resource": {
                "resourceType": "Observation",
                "id": str(obs.id),
                "status": obs.status or "final",
                "category": [{"coding": [{"code": obs.category}]}] if obs.category else [],
                "code": {
                    "text": obs.code_display,
                    "coding": [{"code": obs.code}] if obs.code else [],
                },
                "subject": _PATIENT_REF(pid),
                "effectiveDateTime": obs.effective_date_time,
                "valueQuantity": {"value": obs.value_quantity, "unit": obs.value_unit} if obs.value_quantity is not None else None,
                "valueString": obs.value_string,
            },
        })

    # --- Conditions (Diagnoses) ---
    for cond in (await db.execute(
        select(Condition).where(Condition.patient_id == pid, Condition.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{cond.id}",
            "resource": {
                "resourceType": "Condition",
                "id": str(cond.id),
                "subject": _PATIENT_REF(pid),
                "code": {"text": cond.code_display, "coding": [{"code": cond.code}] if cond.code else []},
                "clinicalStatus": {"coding": [{"code": cond.clinical_status}]} if cond.clinical_status else None,
                "severity": {"text": cond.severity} if cond.severity else None,
                "onsetDateTime": cond.onset_date_time,
            },
        })

    # --- MedicationStatements (Medications) ---
    for med in (await db.execute(
        select(MedicationStatement).where(MedicationStatement.patient_id == pid, MedicationStatement.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{med.id}",
            "resource": {
                "resourceType": "MedicationStatement",
                "id": str(med.id),
                "status": med.status or "active",
                "subject": _PATIENT_REF(pid),
                "medicationCodeableConcept": {"text": med.medication_display},
                "dosage": [{"text": med.dosage_text}] if med.dosage_text else [],
            },
        })

    # --- AdverseEvents (Incidents) ---
    for inc in (await db.execute(
        select(Incident).where(Incident.patient_id == pid, Incident.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{inc.id}",
            "resource": {
                "resourceType": "AdverseEvent",
                "id": str(inc.id),
                "actuality": "actual",
                "subject": _PATIENT_REF(pid),
                "event": {"text": inc.incident_type_display or inc.incident_type},
                "date": inc.occurred_at,
                "severity": {"text": inc.severity} if inc.severity else None,
                "outcome": {"text": inc.outcome} if inc.outcome else None,
                "description": inc.note,
                "suspectEntity": [{"instance": {"display": t.strip()}} for t in (inc.suspected_trigger or "").split(",") if t.strip()],
            },
        })

    # --- Appointments (Events / CalendarEvents) ---
    for evt in (await db.execute(
        select(CalendarEvent).where(CalendarEvent.patient_id == pid, CalendarEvent.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{evt.id}",
            "resource": {
                "resourceType": "Appointment",
                "id": str(evt.id),
                "status": evt.status or "booked",
                "description": evt.title,
                "comment": evt.purpose,
                "start": evt.start_at,
                "end": evt.end_at,
                "participant": [{"actor": _PATIENT_REF(pid), "status": "accepted"}],
                "serviceType": [{"text": evt.provider}] if evt.provider else [],
                "location": [{"location": {"display": evt.location}}] if evt.location else [],
            },
        })

    # --- Observations (Health Logs / DiaryEntries, category: survey) ---
    # diary notes are ciphertext at rest (ADR-031); decrypt for the export
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    try:
        _diary_kek = await get_patient_kek(db, pid)
    except KeyError:
        _diary_kek = None  # patient never had encrypted free text
    for entry in (await db.execute(
        select(DiaryEntry).where(DiaryEntry.patient_id == pid, DiaryEntry.is_deleted == False)  # noqa: E712
    )).scalars().all():
        components = []
        _field = lambda code, display, val: components.append({  # noqa: E731
            "code": {"text": display},
            "valueInteger": val,
        }) if val is not None else None
        _field("mood", "Mood", entry.mood)
        _field("pain", "Pain Level", entry.pain_level)
        _field("mobility", "Mobility", entry.mobility)
        _field("sleep-quality", "Sleep Quality", entry.sleep_quality)
        if entry.sleep_hours is not None:
            components.append({"code": {"text": "Sleep Hours"}, "valueQuantity": {"value": entry.sleep_hours, "unit": "h"}})
        if entry.bowel_movement is not None:
            components.append({"code": {"text": "Bowel Movement"}, "valueBoolean": entry.bowel_movement})
        if entry.medication_compliance is not None:
            components.append({"code": {"text": "Medication Compliance"}, "valueBoolean": entry.medication_compliance})
        if entry.nutrition_notes:
            components.append({"code": {"text": "Nutrition Notes"}, "valueString": decrypt_str(entry.nutrition_notes, _diary_kek)})
        if entry.general_notes:
            components.append({"code": {"text": "General Notes"}, "valueString": decrypt_str(entry.general_notes, _diary_kek)})

        effective = entry.entry_date
        if entry.entry_time:
            effective = f"{entry.entry_date}T{entry.entry_time}"

        entries.append({
            "fullUrl": f"urn:uuid:{entry.id}",
            "resource": {
                "resourceType": "Observation",
                "id": str(entry.id),
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
                "code": {"text": entry.subject or "Daily Health Log"},
                "subject": _PATIENT_REF(pid),
                "effectiveDateTime": effective,
                "component": components,
            },
        })

    # --- Tasks (Recommendations) ---
    for rec in (await db.execute(
        select(Recommendation).where(Recommendation.patient_id == pid, Recommendation.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{rec.id}",
            "resource": {
                "resourceType": "Task",
                "id": str(rec.id),
                "status": rec.status or "requested",
                "intent": "proposal",
                "for": _PATIENT_REF(pid),
                "description": rec.text,
            },
        })

    # --- Communications (AI Health Assistant messages) ---
    for msg in (await db.execute(
        select(ChatMessage).where(ChatMessage.patient_id == pid)
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{msg.id}",
            "resource": {
                "resourceType": "Communication",
                "id": str(msg.id),
                "status": "completed",
                "subject": _PATIENT_REF(pid),
                "sender": {"display": "AI Health Assistant"} if msg.role == "assistant" else _PATIENT_REF(pid),
                # chat content is ciphertext at rest (ADR-031); _diary_kek is the same patient KEK
                "payload": [{"contentString": decrypt_str(msg.content, _diary_kek)}],
            },
        })

    # --- DocumentReferences (Document metadata) ---
    for doc in (await db.execute(
        select(DocumentReference).where(DocumentReference.patient_id == pid, DocumentReference.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{doc.id}",
            "resource": {
                "resourceType": "DocumentReference",
                "id": str(doc.id),
                "status": "current",
                "subject": _PATIENT_REF(pid),
                "date": str(doc.issued_date) if doc.issued_date else None,
                "description": doc.description,
                "type": {"text": doc.type} if doc.type else None,
                "content": [{"attachment": {"title": doc.file_name, "contentType": doc.content_type}}],
            },
        })

    # GDPR governance metadata: lawful basis + retention per data category (#15/#16)
    from app.models.governance import DataCategory
    cats = (await db.execute(select(DataCategory).order_by(DataCategory.label))).scalars().all()
    governance = {
        "categories": [
            {
                "code": c.code,
                "label": c.label,
                "lawful_basis": c.lawful_basis,
                "retention_days": c.retention_days,
            }
            for c in cats
        ],
    }

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total": len(entries),
        "entry": entries,
        "_governance": governance,
    }
    return Response(
        content=json.dumps(bundle, indent=2),
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="patient-{patient_id}-fhir.json"'},
    )


@router.get("/patients/{patient_id}/export/pdf")
async def export_pdf(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    patient_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = patient_result.scalar_one_or_none()

    html = f"""
    <html><body>
    <h1>Patient Record: {patient.given_name if patient else ''} {patient.family_name if patient else ''}</h1>
    <p>Generated: {__import__('datetime').datetime.utcnow().isoformat()}</p>
    <p>For a complete machine-readable export, use the FHIR export endpoint.</p>
    </body></html>
    """
    try:
        import weasyprint
        pdf = weasyprint.HTML(string=html).write_pdf()
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="patient-{patient_id}.pdf"'},
        )
    except Exception:
        return Response(content=html, media_type="text/html")
