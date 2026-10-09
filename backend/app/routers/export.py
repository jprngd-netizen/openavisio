import json
import re
import uuid
from html import escape as _esc
from io import BytesIO

from fastapi import APIRouter, Depends, Query
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
                "effectiveDateTime": obs.effective_date_time.isoformat() if obs.effective_date_time else None,
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
                "onsetDateTime": cond.onset_date_time.isoformat() if cond.onset_date_time else None,
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
                "start": evt.start_at.isoformat(),
                "end": evt.end_at.isoformat() if evt.end_at else None,
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


# --- PDF export: the full record + the original documents appended -----------
#
# "Impressão de Prontuário" must also carry the *documents themselves* (their
# real pages), not just their metadata. A browser print cannot embed PDFs, so
# the record is rendered server-side (weasyprint) from the same database rows
# the JSON/FHIR export uses, and the original files are merged in with pypdf.

_EXPORT_SECTIONS = (
    "encounters",
    "conditions",
    "medications",
    "measurements",
    "lab-results",
    "documents",
    "prescriptions",
)

_RECORD_CSS = """
@page { size: A4; margin: 16mm }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5px; color: #111 }
h1 { font-size: 18px; margin: 0 0 2px }
.meta { color: #555; font-size: 10px; margin-bottom: 6px }
h2 { font-size: 13px; margin: 16px 0 6px; border-bottom: 1px solid #bbb; padding-bottom: 2px }
table { width: 100%; border-collapse: collapse }
th { text-align: left; font-size: 9px; color: #666; padding: 2px 4px }
td { border-top: 1px solid #e2e2e2; padding: 3px 4px; vertical-align: top }
.card { border: 1px solid #ccc; border-radius: 4px; padding: 6px 8px; margin: 6px 0; page-break-inside: avoid }
.field { margin: 2px 0 }
.field .k { font-weight: 600; color: #555 }
.nodata { color: #666 }
footer { margin-top: 14px; border-top: 1px solid #bbb; padding-top: 4px; text-align: center; font-size: 9px; color: #666 }
"""

_LABELS: dict[str, dict[str, str]] = {
    "pt": {
        "record": "Prontuário", "birthDate": "Data de nascimento", "sex": "Sexo",
        "generatedOn": "Gerado em", "noData": "Nenhum dado.",
        "male": "Masculino", "female": "Feminino", "other": "Outro",
        "sec.encounters": "Atendimentos", "sec.conditions": "Diagnósticos",
        "sec.medications": "Medicamentos", "sec.measurements": "Sinais vitais",
        "sec.lab-results": "Exames laboratoriais", "sec.documents": "Documentos",
        "sec.prescriptions": "Receitas",
        "enc.chief": "Queixa", "enc.history": "Anamnese", "enc.exam": "Exame físico",
        "enc.assessment": "Avaliação", "enc.plan": "Plano", "enc.notes": "Notas",
        "enc.vitals": "Sinais vitais", "enc.cid": "CID-10",
        "cond.name": "Diagnóstico", "cond.onset": "Início", "cond.severity": "Gravidade",
        "cond.status": "Status", "sev.mild": "leve", "sev.moderate": "moderado", "sev.severe": "grave",
        "cst.active": "ativo", "cst.inactive": "inativo", "cst.resolved": "resolvido",
        "med.name": "Medicamento", "med.dosage": "Posologia", "med.period": "Período",
        "med.status": "Status", "med.active": "Ativo", "med.ended": "Encerrado", "med.ongoing": "em uso",
        "meas.type": "Tipo", "meas.date": "Data", "meas.value": "Valor",
        "lab.test": "Exame", "lab.panel": "Painel", "lab.result": "Resultado",
        "lab.ref": "Referência", "lab.date": "Data",
        "doc.file": "Arquivo", "doc.type": "Tipo", "doc.issued": "Data de emissão",
        "rx.status": "Status", "rx.date": "Data", "rx.med": "Medicamento",
        "rx.posology": "Posologia", "rx.qty": "Quantidade", "rx.noitems": "Nenhum item.",
        "rx.s.draft": "Rascunho", "rx.s.issued": "Emitida", "rx.s.failed": "Falha", "rx.s.deleted": "Excluída",
    },
    "en": {
        "record": "Medical record", "birthDate": "Date of birth", "sex": "Sex",
        "generatedOn": "Generated on", "noData": "No data.",
        "male": "Male", "female": "Female", "other": "Other",
        "sec.encounters": "Encounters", "sec.conditions": "Conditions",
        "sec.medications": "Medications", "sec.measurements": "Measurements",
        "sec.lab-results": "Lab results", "sec.documents": "Documents",
        "sec.prescriptions": "Prescriptions",
        "enc.chief": "Chief complaint", "enc.history": "History", "enc.exam": "Physical exam",
        "enc.assessment": "Assessment", "enc.plan": "Plan", "enc.notes": "Notes",
        "enc.vitals": "Vitals", "enc.cid": "ICD-10",
        "cond.name": "Diagnosis", "cond.onset": "Onset", "cond.severity": "Severity",
        "cond.status": "Status", "sev.mild": "mild", "sev.moderate": "moderate", "sev.severe": "severe",
        "cst.active": "active", "cst.inactive": "inactive", "cst.resolved": "resolved",
        "med.name": "Medication", "med.dosage": "Dosage", "med.period": "Period",
        "med.status": "Status", "med.active": "Active", "med.ended": "Ended", "med.ongoing": "ongoing",
        "meas.type": "Type", "meas.date": "Date", "meas.value": "Value",
        "lab.test": "Test", "lab.panel": "Panel", "lab.result": "Result",
        "lab.ref": "Reference", "lab.date": "Date",
        "doc.file": "File", "doc.type": "Type", "doc.issued": "Issued",
        "rx.status": "Status", "rx.date": "Date", "rx.med": "Medication",
        "rx.posology": "Posology", "rx.qty": "Quantity", "rx.noitems": "No items.",
        "rx.s.draft": "Draft", "rx.s.issued": "Issued", "rx.s.failed": "Failed", "rx.s.deleted": "Deleted",
    },
    "de": {
        "record": "Patientenakte", "birthDate": "Geburtsdatum", "sex": "Geschlecht",
        "generatedOn": "Erstellt am", "noData": "Keine Daten.",
        "male": "Männlich", "female": "Weiblich", "other": "Divers",
        "sec.encounters": "Konsultationen", "sec.conditions": "Diagnosen",
        "sec.medications": "Medikamente", "sec.measurements": "Messwerte",
        "sec.lab-results": "Laborwerte", "sec.documents": "Dokumente",
        "sec.prescriptions": "Rezepte",
        "enc.chief": "Beschwerde", "enc.history": "Anamnese", "enc.exam": "Körperliche Untersuchung",
        "enc.assessment": "Beurteilung", "enc.plan": "Plan", "enc.notes": "Notizen",
        "enc.vitals": "Vitalwerte", "enc.cid": "ICD-10",
        "cond.name": "Diagnose", "cond.onset": "Beginn", "cond.severity": "Schwere",
        "cond.status": "Status", "sev.mild": "leicht", "sev.moderate": "moderat", "sev.severe": "schwer",
        "cst.active": "aktiv", "cst.inactive": "inaktiv", "cst.resolved": "abgeklungen",
        "med.name": "Medikament", "med.dosage": "Dosierung", "med.period": "Zeitraum",
        "med.status": "Status", "med.active": "Aktiv", "med.ended": "Beendet", "med.ongoing": "laufend",
        "meas.type": "Typ", "meas.date": "Datum", "meas.value": "Wert",
        "lab.test": "Test", "lab.panel": "Panel", "lab.result": "Ergebnis",
        "lab.ref": "Referenz", "lab.date": "Datum",
        "doc.file": "Datei", "doc.type": "Typ", "doc.issued": "Ausgestellt am",
        "rx.status": "Status", "rx.date": "Datum", "rx.med": "Medikament",
        "rx.posology": "Posologie", "rx.qty": "Menge", "rx.noitems": "Keine Positionen.",
        "rx.s.draft": "Entwurf", "rx.s.issued": "Ausgestellt", "rx.s.failed": "Fehlgeschlagen", "rx.s.deleted": "Gelöscht",
    },
}


def _labels(locale: str) -> dict[str, str]:
    return _LABELS.get(locale, _LABELS["pt"])


def _fmt_date(value, locale: str) -> str:
    """ISO date (YYYY-MM-DD) → a calendar date, timezone-proof (same rule as the UI)."""
    if not value:
        return "—"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    if not m:
        return str(value)
    y, mo, d = m.groups()
    return f"{mo}/{d}/{y}" if locale == "en" else f"{d}/{mo}/{y}"


def _block(label: str, value) -> str:
    if value in (None, ""):
        return ""
    return f'<div class="field"><span class="k">{_esc(label)}:</span> {_esc(str(value))}</div>'


async def _decrypted_doc_bytes(db: AsyncSession, patient_id: uuid.UUID, doc: DocumentReference) -> bytes | None:
    from app.core.encryption import decrypt_document
    from app.core.patient_keys import get_patient_kek
    from app.core.storage import get_storage

    if not doc.storage_path or not doc.encrypted_dek:
        return None
    try:
        kek = await get_patient_kek(db, patient_id)
        return decrypt_document(get_storage().read(doc.storage_path), doc.encrypted_dek, kek)
    except Exception:
        return None  # a single unreadable file must not break the whole export


def _merge_pdfs(record_pdf: bytes, blobs: list[bytes]) -> bytes:
    """Append each original file's pages after the record: PDFs as-is, images as a page."""
    from pypdf import PdfReader, PdfWriter
    from PIL import Image

    writer = PdfWriter()
    for page in PdfReader(BytesIO(record_pdf)).pages:
        writer.add_page(page)
    for data in blobs:
        if not data:
            continue
        try:
            if data[:5] == b"%PDF-":
                for page in PdfReader(BytesIO(data)).pages:
                    writer.add_page(page)
                continue
            img = Image.open(BytesIO(data))
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="PDF")
            buf.seek(0)
            for page in PdfReader(buf).pages:
                writer.add_page(page)
        except Exception:
            continue  # skip a file pypdf/PIL cannot read rather than failing the export
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _build_record_html(patient, selected: set[str], data: dict, L: dict[str, str], locale: str) -> str:
    esc = _esc
    parts: list[str] = ['<!DOCTYPE html><html><head><meta charset="utf-8">', f"<style>{_RECORD_CSS}</style></head><body>"]

    name = f"{patient.given_name if patient else ''} {patient.family_name if patient else ''}".strip()
    parts.append(f"<h1>{esc(name)}</h1>")
    meta = []
    if patient and patient.birth_date:
        meta.append(f"{esc(L['birthDate'])}: {esc(_fmt_date(patient.birth_date, locale))}")
    if patient and patient.gender:
        g = str(patient.gender).lower()
        meta.append(f"{esc(L['sex'])}: {esc(L.get(g, str(patient.gender)))}")
    meta.append(f"{esc(L['generatedOn'])}: {esc(__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M'))}")
    parts.append(f'<div class="meta">{" &middot; ".join(meta)}</div>')

    def section(slug: str, body: str) -> None:
        parts.append(f'<h2>{esc(L[f"sec.{slug}"])}</h2>')
        parts.append(body)

    def nodata() -> str:
        return f'<p class="nodata">{esc(L["noData"])}</p>'

    if "encounters" in selected:
        items = data["encounters"]
        if not items:
            section("encounters", nodata())
        else:
            cards = []
            for e in items:
                head = esc(_fmt_date(e.encounter_date, locale))
                if e.encounter_type:
                    head += f" &middot; {esc(e.encounter_type)}"
                if e.cid10_code or e.cid10_display:
                    head += f" &middot; {esc((e.cid10_code or '') + (' · ' if e.cid10_code and e.cid10_display else '') + (e.cid10_display or ''))}"
                fields = "".join(
                    _block(L[k], v)
                    for k, v in (
                        ("enc.chief", e.chief_complaint), ("enc.history", e.history),
                        ("enc.exam", e.physical_exam), ("enc.assessment", e.assessment),
                        ("enc.plan", e.plan), ("enc.notes", e.notes),
                    )
                )
                vitals = [m for m in (e.measurements or []) if m.value_quantity is not None]
                vhtml = ""
                if vitals:
                    cells = " ".join(
                        f"{esc(m.code_display or m.code)}: {esc(m.value_quantity)}{' ' + esc(m.value_unit) if m.value_unit else ''}"
                        for m in vitals
                    )
                    vhtml = f'<div class="field"><span class="k">{esc(L["enc.vitals"])}:</span> {cells}</div>'
                cards.append(f'<div class="card"><div><strong>{head}</strong></div>{vhtml}{fields}</div>')
            section("encounters", "".join(cards))

    if "conditions" in selected:
        items = data["conditions"]
        if not items:
            section("conditions", nodata())
        else:
            rows = "".join(
                "<tr>"
                f"<td>{esc(c.code_display or c.code or '')}</td>"
                f"<td>{esc(_fmt_date(c.onset_date_time, locale))}</td>"
                f"<td>{esc(L.get(f'sev.{c.severity}', c.severity or ''))}</td>"
                f"<td>{esc(L.get(f'cst.{c.clinical_status}', c.clinical_status or ''))}</td>"
                "</tr>"
                for c in items
            )
            head = "".join(f"<th>{esc(L[k])}</th>" for k in ("cond.name", "cond.onset", "cond.severity", "cond.status"))
            section("conditions", f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    if "medications" in selected:
        items = data["medications"]
        if not items:
            section("medications", nodata())
        else:
            rows = ""
            for m in items:
                dosage = m.dosage_text or (f"{m.dose_quantity} {m.dose_unit or ''}".strip() if m.dose_quantity else "—")
                start = _fmt_date(m.effective_start, locale) if m.effective_start else "—"
                end = _fmt_date(m.effective_end, locale) if m.effective_end else L["med.ongoing"]
                status = L["med.active"] if m.is_active else L["med.ended"]
                rows += (
                    "<tr>"
                    f"<td>{esc(m.medication_display)}</td><td>{esc(dosage)}</td>"
                    f"<td>{esc(start)} – {esc(end)}</td><td>{esc(status)}</td>"
                    "</tr>"
                )
            head = "".join(f"<th>{esc(L[k])}</th>" for k in ("med.name", "med.dosage", "med.period", "med.status"))
            section("medications", f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    def obs_table(slug: str, items: list, with_ref: bool) -> None:
        if not items:
            section(slug, nodata())
            return
        rows = ""
        for o in items:
            val = f"{o.value_quantity}{' ' + o.value_unit if o.value_unit else ''}" if o.value_quantity is not None else (o.value_string or "—")
            ref = ""
            if with_ref:
                if o.reference_range:
                    ref = o.reference_range
                elif o.ref_low is not None and o.ref_high is not None:
                    ref = f"{o.ref_low}–{o.ref_high}"
                elif o.ref_high is not None:
                    ref = f"< {o.ref_high}"
                elif o.ref_low is not None:
                    ref = f"> {o.ref_low}"
                ref = ref or "—"
            rows += (
                "<tr>"
                f"<td>{esc(o.code_display or o.code)}</td>"
                + (f"<td>{esc(o.panel or '—')}</td>" if with_ref else "")
                + f"<td>{esc(val)}</td>"
                + (f"<td>{esc(ref)}</td>" if with_ref else "")
                + f"<td>{esc(_fmt_date(o.effective_date_time, locale))}</td>"
                "</tr>"
            )
        keys = ("lab.test", "lab.panel", "lab.result", "lab.ref", "lab.date") if with_ref else ("meas.type", "meas.date", "meas.value")
        # keep the column order matching the header for measurements (type, date, value)
        head = "".join(f"<th>{esc(L[k])}</th>" for k in keys)
        section(slug, f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    if "measurements" in selected:
        # measurements table header is (Type, Date, Value) — rebuild rows in that order
        items = data["measurements"]
        if not items:
            section("measurements", nodata())
        else:
            rows = "".join(
                "<tr>"
                f"<td>{esc(o.code_display or o.code)}</td>"
                f"<td>{esc(_fmt_date(o.effective_date_time, locale))}</td>"
                f"<td>{esc(f'{o.value_quantity}' + ((' ' + o.value_unit) if o.value_unit else '') if o.value_quantity is not None else (o.value_string or '—'))}</td>"
                "</tr>"
                for o in items
            )
            head = "".join(f"<th>{esc(L[k])}</th>" for k in ("meas.type", "meas.date", "meas.value"))
            section("measurements", f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    if "lab-results" in selected:
        obs_table("lab-results", data["lab_results"], with_ref=True)

    if "documents" in selected:
        items = data["documents"]
        if not items:
            section("documents", nodata())
        else:
            rows = "".join(
                "<tr>"
                f"<td>{esc(d.file_name or '—')}</td>"
                f"<td>{esc(d.type or d.document_classification or '—')}</td>"
                f"<td>{esc(_fmt_date(d.issued_date or d.created_at, locale))}</td>"
                "</tr>"
                for d in items
            )
            head = "".join(f"<th>{esc(L[k])}</th>" for k in ("doc.file", "doc.type", "doc.issued"))
            section("documents", f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")

    if "prescriptions" in selected:
        items = data["prescriptions"]
        if not items:
            section("prescriptions", nodata())
        else:
            cards = []
            for p in items:
                status = L.get(f"rx.s.{p.status}", p.status or "")
                date = _fmt_date(p.issued_at or p.created_at, locale)
                head = f"{esc(L['rx.status'])}: {esc(status)} &middot; {esc(L['rx.date'])}: {esc(date)}"
                if p.notes:
                    head += f" &middot; {esc(p.notes)}"
                rows = "".join(
                    f"<tr><td>{esc(it.medication_name or '—')}</td><td>{esc(it.posology or '—')}</td><td>{esc(it.quantity or '—')}</td></tr>"
                    for it in (p.items or [])
                )
                body = (
                    f"<table><thead><tr><th>{esc(L['rx.med'])}</th><th>{esc(L['rx.posology'])}</th><th>{esc(L['rx.qty'])}</th></tr></thead><tbody>{rows}</tbody></table>"
                    if rows else f'<div class="nodata">{esc(L["rx.noitems"])}</div>'
                )
                cards.append(f'<div class="card"><div><strong>{head}</strong></div><div style="margin-top:4px">{body}</div></div>')
            section("prescriptions", "".join(cards))

    parts.append("</body></html>")
    return "".join(parts)


@router.get("/patients/{patient_id}/export/pdf")
async def export_pdf(
    patient_id: uuid.UUID,
    sections: str | None = Query(None),
    locale: str = Query("pt"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-rendered PDF of the record, with the selected documents' original
    pages appended — "Impressão de Prontuário" carries the documents themselves.

    The record is built from the same database rows the JSON/FHIR export uses
    (no duplicated data); the original files are merged in afterwards with pypdf.
    """
    from app.models.encounter import Encounter
    from app.models.prescription import Prescription

    await require_patient_access(patient_id, user, db)
    if locale not in ("pt", "en", "de"):
        locale = "pt"
    L = _labels(locale)

    selected = (
        set(_EXPORT_SECTIONS)
        if sections is None
        else {s.strip() for s in sections.split(",") if s.strip() in _EXPORT_SECTIONS}
    )

    patient = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()

    async def _list(model, extra=()):
        q = select(model).where(model.patient_id == patient_id, model.is_deleted == False)  # noqa: E712
        for clause in extra:
            q = q.order_by(clause)
        return (await db.execute(q)).scalars().all()

    data: dict[str, list] = {
        "encounters": await _list(Encounter, (Encounter.encounter_date,)) if "encounters" in selected else [],
        "conditions": await _list(Condition, (Condition.onset_date_time,)) if "conditions" in selected else [],
        "medications": await _list(MedicationStatement) if "medications" in selected else [],
        "measurements": await _list(Observation, (Observation.effective_date_time,)) if "measurements" in selected else [],
        "lab_results": await _list(Observation, (Observation.effective_date_time,)) if "lab-results" in selected else [],
        "documents": await _list(DocumentReference, (DocumentReference.issued_date,)) if "documents" in selected else [],
        "prescriptions": await _list(Prescription) if "prescriptions" in selected else [],
    }
    # measurements/lab are both Observations — filter by category
    if "measurements" in selected:
        data["measurements"] = [o for o in data["measurements"] if o.category == "measurement"]
    if "lab-results" in selected:
        data["lab_results"] = [o for o in data["lab_results"] if o.category == "lab"]

    html = _build_record_html(patient, selected, data, L, locale)

    try:
        import weasyprint
        record_pdf = weasyprint.HTML(string=html).write_pdf() or b""
    except Exception:
        return Response(content=html, media_type="text/html")

    if "documents" in selected and data["documents"]:
        blobs = []
        for doc in data["documents"]:
            raw = await _decrypted_doc_bytes(db, patient_id, doc)
            if raw:
                blobs.append(raw)
        if blobs:
            record_pdf = _merge_pdfs(record_pdf, blobs)

    return Response(
        content=record_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="patient-{patient_id}.pdf"'},
    )
