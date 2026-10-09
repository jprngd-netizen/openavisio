import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import OrmBase
from app.services.share_link import EXPIRY_CHOICES


class ShareLinkCreateRequest(BaseModel):
    document_ids: list[uuid.UUID]
    expiry_days: int = 30

    @field_validator("expiry_days")
    @classmethod
    def _valid_expiry(cls, v: int) -> int:
        if v not in EXPIRY_CHOICES:
            raise ValueError(f"expiry_days must be one of {sorted(EXPIRY_CHOICES)}")
        return v


class ShareLinkAddDocumentsRequest(BaseModel):
    document_ids: list[uuid.UUID]


class ShareLinkDocumentDto(BaseModel):
    """A Document included in a link, as shown to the managing Caregiver."""

    document_id: uuid.UUID
    file_name: str | None
    content_type: str | None
    size: int | None


class ShareLinkDto(OrmBase):
    """Caregiver-side management view of a share link. Never carries the token."""

    id: uuid.UUID
    status: str            # active | revoked | expired (computed)
    expires_at: datetime
    created_at: datetime
    created_by_user_id: uuid.UUID | None
    created_legal: bool
    revoked_at: datetime | None
    documents: list[ShareLinkDocumentDto] = []
    access_count: int = 0
    last_accessed_at: datetime | None = None


class ShareLinkCreatedDto(ShareLinkDto):
    """Returned once at creation — carries the one-time plaintext link URL."""

    url: str


# --- Public (external recipient) views ---------------------------------------

class PublicShareDocumentDto(BaseModel):
    id: uuid.UUID
    file_name: str | None
    content_type: str | None
    size: int | None
    type: str | None
    issued_date: str | None
    extraction: dict | None  # that document's own extracted clinical data (no raw OCR)


class PublicSharePatientDto(BaseModel):
    given_name: str
    family_name: str
    birth_date: date | None


class PublicShareLinkDto(BaseModel):
    patient: PublicSharePatientDto
    org_name: str
    expires_at: datetime
    documents: list[PublicShareDocumentDto]
