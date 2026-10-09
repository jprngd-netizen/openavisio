"""Embedding scheduler, diary embedding, and event reminder tasks."""

import asyncio
import uuid

from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task
def embedding_scheduler():
    """Find docs that need (re-)embedding and enqueue them."""
    from app.core.config import settings

    async def _scan():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.document import DocumentReference

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentReference).where(
                    DocumentReference.is_deleted == False,  # noqa: E712
                    DocumentReference.processing_status == "extracted",
                    DocumentReference.extracted_text != None,  # noqa: E711
                ).limit(settings.embedding_scheduler_batch_size)
            )
            docs = result.scalars().all()
            from app.workers.pipeline import embedding_stage
            for doc in docs:
                embedding_stage.delay(str(doc.id))
            return len(docs)

    count = _run(_scan())
    return {"enqueued": count}


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def diary_embedding_job(self, entry_id: str):
    """Embed a diary entry for RAG."""
    from app.core.config import settings
    import httpx

    async def _embed():
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.diary import DiaryEntry
        from app.models.chat import DocumentChunk

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DiaryEntry).where(DiaryEntry.id == uuid.UUID(entry_id)))
            entry = result.scalar_one_or_none()
            if not entry:
                return

            if not (entry.general_notes or entry.nutrition_notes):
                return

            # diary notes are ciphertext at rest (ADR-031): decrypt to embed,
            # re-encrypt the chunk copy under the same patient KEK
            from app.core.encryption import decrypt_str, encrypt_str
            from app.core.patient_keys import get_patient_kek
            kek = await get_patient_kek(db, entry.patient_id)
            text_parts = [decrypt_str(v, kek) for v in (entry.general_notes, entry.nutrition_notes) if v]
            text = " ".join(text_parts)
            async with httpx.AsyncClient(timeout=30, headers=settings.ai_service_headers) as client:
                resp = await client.post(f"{settings.ai_service_url}/embed", json={"texts": [text]})
                if resp.status_code != 200:
                    return
                embedding = resp.json()["embeddings"][0]

            # Remove old chunks
            existing = await db.execute(select(DocumentChunk).where(DocumentChunk.diary_entry_id == uuid.UUID(entry_id)))
            for chunk in existing.scalars().all():
                await db.delete(chunk)

            db.add(DocumentChunk(
                diary_entry_id=uuid.UUID(entry_id),
                patient_id=entry.patient_id,
                chunk_index=0,
                content=encrypt_str(text, kek),
                embedding=embedding,
            ))
            await db.commit()

    _run(_embed())


@celery_app.task
def event_reminder_scheduler():
    """Find calendar events starting in ~24 hours and send reminder emails."""

    async def _scan():
        from datetime import UTC, datetime, timedelta
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.calendar import CalendarEvent
        from app.services.email import send_event_reminder

        window_start = datetime.now(UTC) + timedelta(hours=23)
        window_end = datetime.now(UTC) + timedelta(hours=25)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.is_deleted.is_(False),
                    CalendarEvent.status == "scheduled",
                    CalendarEvent.reminder_sent_at.is_(None),
                )
            )
            events = result.scalars().all()

            to_remind = [
                e for e in events
                if e.start_at
                and _parse_event_dt(e.start_at, window_start, window_end)
            ]

            for event in to_remind:
                await send_event_reminder(str(event.id))
                event.reminder_sent_at = datetime.now(UTC)

            if to_remind:
                await db.commit()

        return {"reminded": len(to_remind)}

    return _run(_scan())


@celery_app.task
def retention_purge_scheduler():
    """Enforce per-category retention: soft-delete records past their window (#16)."""

    async def _purge():
        from app.core.database import AsyncSessionLocal
        from app.services.governance import ensure_categories_seeded, run_retention_purge

        async with AsyncSessionLocal() as db:
            await ensure_categories_seeded(db)
            return await run_retention_purge(db)

    return _run(_purge())


def _parse_event_dt(start_at, window_start, window_end) -> bool:
    """Return True if start_at (a typed datetime) falls within the reminder window."""
    from datetime import UTC
    if start_at is None:
        return False
    dt = start_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return window_start <= dt <= window_end
