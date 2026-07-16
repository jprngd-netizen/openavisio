"""Transactional email service — reads SMTP config from SystemSetting at send time."""

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("openavisio.email")


async def _get_smtp_config(db) -> dict | None:
    from sqlalchemy import select
    from app.core.encryption import decrypt_setting
    from app.models.system import SystemSetting

    keys = ["smtp.host", "smtp.port", "smtp.user", "smtp.password", "smtp.from"]
    result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(keys)))
    cfg = {s.key: s.value for s in result.scalars().all()}

    host = cfg.get("smtp.host")
    if not host:
        return None

    return {
        "host": host,
        "port": int(cfg.get("smtp.port") or "587"),
        "user": cfg.get("smtp.user"),
        "password": decrypt_setting(cfg.get("smtp.password")),
        "from_address": cfg.get("smtp.from") or cfg.get("smtp.user") or "noreply@openavisio.app",
    }


def _send_smtp(smtp_cfg: dict, to_email: str, subject: str, html: str, text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["from_address"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=15) as s:
        s.ehlo()
        try:
            s.starttls()
            s.ehlo()
        except smtplib.SMTPNotSupportedError:
            pass
        if smtp_cfg["user"] and smtp_cfg["password"]:
            s.login(smtp_cfg["user"], smtp_cfg["password"])
        s.sendmail(smtp_cfg["from_address"], [to_email], msg.as_string())


async def send_document_processed_notification(doc_id: str) -> None:
    """Notify all caregivers with access to the patient that a document finished processing."""
    from datetime import UTC, datetime

    from sqlalchemy import select
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.access import PatientAccess
    from app.models.correspondent import Correspondent
    from app.models.document import DocumentReference
    from app.models.patient import Patient
    from app.models.user import User

    try:
        async with AsyncSessionLocal() as db:
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return

            doc_result = await db.execute(
                select(DocumentReference).where(DocumentReference.id == uuid.UUID(doc_id))
            )
            doc = doc_result.scalar_one_or_none()
            if not doc:
                return

            patient_result = await db.execute(
                select(Patient).where(Patient.id == doc.patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            if not patient:
                return

            correspondent_name: str | None = None
            if doc.correspondent_id:
                corr_result = await db.execute(
                    select(Correspondent).where(Correspondent.id == doc.correspondent_id)
                )
                corr = corr_result.scalar_one_or_none()
                if corr:
                    correspondent_name = corr.name

            # Collect recipient IDs: active direct access grants
            recipient_ids: set[uuid.UUID] = set()
            now = datetime.now(UTC)
            access_result = await db.execute(
                select(PatientAccess.user_id).where(
                    PatientAccess.patient_id == doc.patient_id,
                    PatientAccess.revoked_at.is_(None),
                    (PatientAccess.expires_at.is_(None)) | (PatientAccess.expires_at > now),
                )
            )
            for row in access_result:
                recipient_ids.add(row[0])

            users_result = await db.execute(
                select(User).where(
                    User.id.in_(recipient_ids),
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            )
            recipients = users_result.scalars().all()

        if not recipients:
            return

        patient_name = f"{patient.given_name} {patient.family_name}"
        doc_name = doc.file_name or doc.description or "Unnamed document"
        issued = str(doc.issued_date) if doc.issued_date else "—"
        doc_url = (
            f"{settings.app_url}/patients/{doc.patient_id}/documents/{doc.id}"
            if settings.app_url
            else None
        )
        subject = f"Document processed: {doc_name}"

        text = _build_text(patient_name, doc_name, issued, correspondent_name, doc_url)
        html = _build_html(patient_name, doc_name, issued, correspondent_name, doc_url)

        loop = asyncio.get_event_loop()
        for user in recipients:
            try:
                await loop.run_in_executor(None, _send_smtp, smtp_cfg, user.email, subject, html, text)
                logger.info("Document notification sent to %s (doc=%s)", user.email, doc_id)
            except Exception as exc:
                logger.warning("Failed to send document notification to %s: %s", user.email, exc)

    except Exception as exc:
        logger.warning("send_document_processed_notification failed (doc=%s): %s", doc_id, exc)


def _build_text(patient_name: str, doc_name: str, issued: str, correspondent: str | None, url: str | None) -> str:
    lines = [
        f"A document has been processed for {patient_name}.",
        "",
        f"Document: {doc_name}",
        f"Issued:   {issued}",
    ]
    if correspondent:
        lines.append(f"From:     {correspondent}")
    if url:
        lines += ["", f"View document: {url}"]
    lines += ["", "—", "OpenAvisio automated notification"]
    return "\n".join(lines)


def _build_html(patient_name: str, doc_name: str, issued: str, correspondent: str | None, url: str | None) -> str:
    rows = f"""
    <tr><td style="padding:6px 0;color:#6b7280;width:110px">Document</td>
        <td style="padding:6px 0;font-weight:500">{doc_name}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Issued</td>
        <td style="padding:6px 0">{issued}</td></tr>
    """
    if correspondent:
        rows += f"""
    <tr><td style="padding:6px 0;color:#6b7280">From</td>
        <td style="padding:6px 0">{correspondent}</td></tr>
    """
    button = (
        f'<p><a href="{url}" style="display:inline-block;background:#2563eb;color:#fff;'
        f'padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px">'
        f"View document</a></p>"
        if url
        else ""
    )
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:580px;margin:0 auto;padding:24px">
  <h2 style="font-size:17px;margin-bottom:2px">Document processed</h2>
  <p style="color:#6b7280;margin-top:0">for <strong>{patient_name}</strong></p>
  <table style="width:100%;border-collapse:collapse;margin:12px 0">{rows}</table>
  {button}
  <p style="color:#9ca3af;font-size:11px;margin-top:32px">OpenAvisio automated notification</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Notification settings helper
# ---------------------------------------------------------------------------

async def _is_notify_enabled(db, key: str) -> bool:
    from sqlalchemy import select
    from app.models.system import SystemSetting
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting is None or (setting.value or "true").lower() != "false"


async def _get_caregivers_for_patient(db, patient_id: uuid.UUID):
    """Return active User objects with access to the given patient (owner + direct grants)."""
    from datetime import UTC, datetime
    from sqlalchemy import select
    from app.models.access import PatientAccess
    from app.models.patient import Patient
    from app.models.user import User

    patient_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        return [], None

    recipient_ids: set[uuid.UUID] = set()
    now = datetime.now(UTC)
    access_result = await db.execute(
        select(PatientAccess.user_id).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.revoked_at.is_(None),
            (PatientAccess.expires_at.is_(None)) | (PatientAccess.expires_at > now),
        )
    )
    for row in access_result:
        recipient_ids.add(row[0])

    users_result = await db.execute(
        select(User).where(
            User.id.in_(recipient_ids),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    return users_result.scalars().all(), patient


# ---------------------------------------------------------------------------
# Caregiver added notification
# ---------------------------------------------------------------------------

async def send_caregiver_added_notification(patient_id: str, caregiver_user_id: str) -> None:
    """Notify the newly added caregiver that they now have access to a patient."""
    try:
        from sqlalchemy import select
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal
        from app.models.patient import Patient
        from app.models.user import User

        async with AsyncSessionLocal() as db:
            if not await _is_notify_enabled(db, "notify.caregiver_added"):
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return

            patient_result = await db.execute(select(Patient).where(Patient.id == uuid.UUID(patient_id)))
            patient = patient_result.scalar_one_or_none()
            if not patient:
                return

            user_result = await db.execute(select(User).where(User.id == uuid.UUID(caregiver_user_id)))
            caregiver = user_result.scalar_one_or_none()
            if not caregiver or not caregiver.is_active:
                return

        patient_name = f"{patient.given_name} {patient.family_name}"
        patient_url = f"{settings.app_url}/patients/{patient_id}" if settings.app_url else None
        subject = f"You have been added as a caregiver for {patient_name}"

        text = "\n".join(filter(None, [
            f"You have been granted access to the patient record for {patient_name} in OpenAvisio.",
            "",
            f"View patient: {patient_url}" if patient_url else None,
            "",
            "—",
            "OpenAvisio automated notification",
        ]))
        html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:580px;margin:0 auto;padding:24px">
  <h2 style="font-size:17px;margin-bottom:2px">Caregiver access granted</h2>
  <p>You have been granted access to the patient record for <strong>{patient_name}</strong> in OpenAvisio.</p>
  {"<p><a href='" + patient_url + "' style='display:inline-block;background:#2563eb;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px'>View patient</a></p>" if patient_url else ""}
  <p style="color:#9ca3af;font-size:11px;margin-top:32px">OpenAvisio automated notification</p>
</body>
</html>"""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _send_smtp, smtp_cfg, caregiver.email, subject, html, text)
        except Exception as exc:
            logger.warning("Failed to send caregiver-added notification to %s: %s", caregiver.email, exc)

    except Exception as exc:
        logger.warning("send_caregiver_added_notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Invitation email
# ---------------------------------------------------------------------------

async def send_invitation_email(to_email: str, token: str) -> None:
    """Send a registration invitation email containing the sign-up link."""
    try:
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            if not await _is_notify_enabled(db, "notify.invitation"):
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return

        register_url = f"{settings.app_url}/register?token={token}" if settings.app_url else None
        subject = "You have been invited to OpenAvisio"

        text = "\n".join(filter(None, [
            "You have been invited to join OpenAvisio.",
            "",
            f"Create your account here: {register_url}" if register_url else "Please contact your administrator for the registration link.",
            "",
            "This invitation expires in 7 days.",
            "",
            "—",
            "OpenAvisio automated notification",
        ]))
        html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:580px;margin:0 auto;padding:24px">
  <h2 style="font-size:17px;margin-bottom:2px">You have been invited to OpenAvisio</h2>
  <p>Click the button below to create your account. This invitation expires in 7 days.</p>
  {"<p><a href='" + register_url + "' style='display:inline-block;background:#2563eb;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px'>Create account</a></p>" if register_url else "<p>Please contact your administrator for the registration link.</p>"}
  <p style="color:#9ca3af;font-size:11px;margin-top:32px">OpenAvisio automated notification</p>
</body>
</html>"""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _send_smtp, smtp_cfg, to_email, subject, html, text)
        except Exception as exc:
            logger.warning("Failed to send invitation email to %s: %s", to_email, exc)

    except Exception as exc:
        logger.warning("send_invitation_email failed: %s", exc)


# ---------------------------------------------------------------------------
# Event reminder
# ---------------------------------------------------------------------------

async def send_event_reminder(event_id: str) -> None:
    """Send a 24-hour reminder to all caregivers for a calendar event."""
    try:
        from sqlalchemy import select
        from app.core.config import settings
        from app.core.database import AsyncSessionLocal
        from app.models.calendar import CalendarEvent

        async with AsyncSessionLocal() as db:
            if not await _is_notify_enabled(db, "notify.event_reminder"):
                return
            smtp_cfg = await _get_smtp_config(db)
            if not smtp_cfg:
                return

            event_result = await db.execute(
                select(CalendarEvent).where(CalendarEvent.id == uuid.UUID(event_id))
            )
            event = event_result.scalar_one_or_none()
            if not event:
                return

            recipients, patient = await _get_caregivers_for_patient(db, event.patient_id)

        if not recipients or not patient:
            return

        patient_name = f"{patient.given_name} {patient.family_name}"
        event_url = (
            f"{settings.app_url}/patients/{event.patient_id}/calendar"
            if settings.app_url
            else None
        )
        subject = f"Reminder: {event.title} tomorrow"

        details = []
        if event.start_at:
            details.append(f"When: {event.start_at}")
        if event.location:
            details.append(f"Where: {event.location}")
        if event.provider:
            details.append(f"Provider: {event.provider}")

        text = "\n".join(filter(None, [
            f"Reminder: '{event.title}' for {patient_name} is scheduled in approximately 24 hours.",
            "",
            *details,
            "",
            f"View calendar: {event_url}" if event_url else None,
            "",
            "—",
            "OpenAvisio automated notification",
        ]))
        detail_rows = "".join(
            f"<tr><td style='padding:4px 0;color:#6b7280;width:90px'>{k}</td>"
            f"<td style='padding:4px 0'>{v}</td></tr>"
            for k, v in [
                ("When", event.start_at),
                ("Where", event.location),
                ("Provider", event.provider),
            ]
            if v
        )
        html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#111;max-width:580px;margin:0 auto;padding:24px">
  <h2 style="font-size:17px;margin-bottom:2px">Reminder: {event.title}</h2>
  <p style="color:#6b7280;margin-top:0">for <strong>{patient_name}</strong> — tomorrow</p>
  {"<table style='width:100%;border-collapse:collapse;margin:12px 0'>" + detail_rows + "</table>" if detail_rows else ""}
  {"<p><a href='" + event_url + "' style='display:inline-block;background:#2563eb;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px'>View calendar</a></p>" if event_url else ""}
  <p style="color:#9ca3af;font-size:11px;margin-top:32px">OpenAvisio automated notification</p>
</body>
</html>"""

        loop = asyncio.get_event_loop()
        for user in recipients:
            try:
                await loop.run_in_executor(None, _send_smtp, smtp_cfg, user.email, subject, html, text)
                logger.info("Event reminder sent to %s (event=%s)", user.email, event_id)
            except Exception as exc:
                logger.warning("Failed to send event reminder to %s: %s", user.email, exc)

    except Exception as exc:
        logger.warning("send_event_reminder failed (event=%s): %s", event_id, exc)
