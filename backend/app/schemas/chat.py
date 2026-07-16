from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class ChatMessageDto(BaseModel):
    role: str
    content: str
    timestamp: datetime


# docs/regulatory-positioning.md claimed "a clear disclaimer states it does not
# replace professional medical judgement" — and no such disclaimer existed
# anywhere in the code (#117). A guardrail that lives only in a document is worse
# than none, because it makes us believe we are covered. It ships with every
# answer now, so a client cannot quietly drop it.
CHAT_DISCLAIMER = (
    "Diese Antwort gibt wieder, was in Ihren Dokumenten steht. Sie ist keine "
    "medizinische Beratung, keine Einschätzung und ersetzt kein ärztliches Urteil. "
    "Wenden Sie sich mit Fragen zu Befunden und Behandlung an die behandelnden "
    "Ärztinnen und Ärzte."
)


class ChatResponse(BaseModel):
    answer: str
    history: list[ChatMessageDto]
    disclaimer: str = CHAT_DISCLAIMER


class ChatHistoryDto(BaseModel):
    messages: list[ChatMessageDto]
