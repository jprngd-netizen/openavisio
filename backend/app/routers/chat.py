import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.deps import get_current_user
from app.models.chat import ChatMessage, DocumentChunk
from app.models.user import User
from app.schemas.chat import ChatHistoryDto, ChatMessageDto, ChatRequest, ChatResponse

router = APIRouter()


async def _get_context(patient_id: uuid.UUID, question: str, db: AsyncSession) -> list[str]:
    """Embed question and find top-K relevant chunks via pgvector."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30, headers=settings.ai_service_headers) as client:
            resp = await client.post(f"{settings.ai_service_url}/embed", json={"texts": [question]})
            if resp.status_code != 200:
                return []
            embedding = resp.json()["embeddings"][0]
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import text
        result = await db.execute(
            text(
                "SELECT content FROM document_chunks WHERE patient_id = :pid AND is_deleted = false "
                "ORDER BY embedding <-> :emb LIMIT 5"
            ),
            {"pid": str(patient_id), "emb": str(embedding)},
        )
        rows = result.fetchall()
        if not rows:
            return []
        # chunk content is ciphertext at rest (ADR-031); decrypt the top-K here
        from app.core.encryption import decrypt_str
        from app.core.patient_keys import get_patient_kek
        kek = await get_patient_kek(db, patient_id)
        return [decrypt_str(row[0], kek) for row in rows]
    except Exception:
        return []


@router.post("/patients/{patient_id}/chat", response_model=ChatResponse)
async def chat(
    patient_id: uuid.UUID,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    context = await _get_context(patient_id, body.question, db)

    import httpx
    answer = "AI service unavailable."
    try:
        async with httpx.AsyncClient(timeout=60, headers=settings.ai_service_headers) as client:
            resp = await client.post(f"{settings.ai_service_url}/chat", json={"question": body.question, "context": context})
            if resp.status_code == 200:
                answer = resp.json().get("answer", answer)
    except Exception:
        pass

    # Persist messages — content is encrypted under the patient KEK (ADR-031)
    from app.core.encryption import encrypt_str
    from app.core.patient_keys import ensure_patient_kek
    kek = await ensure_patient_kek(db, patient_id)
    for role, content in [("user", body.question), ("assistant", answer)]:
        db.add(ChatMessage(patient_id=patient_id, user_id=user.id, role=role, content=encrypt_str(content, kek)))
    await db.commit()

    history = await _get_history(patient_id, user.id, db)
    return ChatResponse(answer=answer, history=history)


@router.get("/patients/{patient_id}/chat/history", response_model=ChatHistoryDto)
async def get_chat_history(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    messages = await _get_history(patient_id, user.id, db)
    return ChatHistoryDto(messages=messages)


async def _get_history(patient_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> list[ChatMessageDto]:
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.patient_id == patient_id,
            ChatMessage.user_id == user_id,
            ChatMessage.is_deleted == False,  # noqa: E712
        ).order_by(ChatMessage.created_at.asc()).limit(50)
    )
    messages = result.scalars().all()
    if not messages:
        return []
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, patient_id)
    return [ChatMessageDto(role=m.role, content=decrypt_str(m.content, kek), timestamp=m.created_at) for m in messages]
