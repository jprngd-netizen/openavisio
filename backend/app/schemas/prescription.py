"""Pydantic v2 schemas for the prescription domain.

Mirrors the structure of ``schemas/medication.py`` and follows the domain
vocabulary from ``CONTEXT.md`` (Prescription, Prescriber, PrescriptionDocument).
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


# ---------------------------------------------------------------------------
# Prescription item
# ---------------------------------------------------------------------------


class PrescriptionItemDto(OrmBase):
    id: uuid.UUID
    prescription_id: uuid.UUID
    medication_name: str
    posology: str | None
    quantity: str | None
    sort_order: int


class PrescriptionItemRequest(BaseModel):
    medication_name: str
    posology: str | None = None
    quantity: str | None = None
    sort_order: int = 0


# ---------------------------------------------------------------------------
# Prescription document
# ---------------------------------------------------------------------------


class PrescriptionDocumentDto(OrmBase):
    id: uuid.UUID
    prescription_id: uuid.UUID
    file_name: str
    content_type: str
    size: int
    hash: str
    signed: bool
    memed_prescription_id: str | None
    digital_link: str | None
    unlock_code: str | None
    captured_at: datetime


# ---------------------------------------------------------------------------
# Prescription
# ---------------------------------------------------------------------------


class PrescriptionDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    prescriber_id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    version: int
    memed_prescription_id: str | None
    memed_prescription_uuid: str | None
    issued_at: datetime | None
    notes: str | None
    deleted_by_memed_at: datetime | None
    failure_reason: str | None
    signature_state: str | None
    created_at: datetime
    updated_at: datetime
    items: list[PrescriptionItemDto] = []
    document: PrescriptionDocumentDto | None = None


class PrescriptionUpdateRequest(BaseModel):
    version: int
    notes: str | None = None
    items: list[PrescriptionItemRequest] | None = None


# ---------------------------------------------------------------------------
# Prescriber (admin)
# ---------------------------------------------------------------------------


class PrescriberDto(OrmBase):
    id: uuid.UUID
    user_id: uuid.UUID | None
    given_name: str
    family_name: str
    cpf_last4: str | None
    birth_date: date | None
    board_code: str | None
    board_number: str | None
    board_state: str | None
    email: str | None
    phone: str | None
    sex: str | None
    city_id: int | None
    specialty_id: int | None
    memed_user_id: str | None
    memed_status: str | None
    sync_status: str | None
    sync_error: str | None
    cep: str | None
    street: str | None
    street_number: str | None
    complement: str | None
    district: str | None
    city_name: str | None
    state_code: str | None


class PrescriberUpdateRequest(BaseModel):
    user_id: uuid.UUID | None = None
    given_name: str
    family_name: str
    cpf: str | None = None
    birth_date: str | None = None
    board_code: str | None = None
    board_number: str | None = None
    board_state: str | None = None
    email: str | None = None
    phone: str | None = None
    sex: str | None = None
    city_id: int | None = None
    specialty_id: int | None = None
    cep: str | None = None
    street: str | None = None
    street_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city_name: str | None = None
    state_code: str | None = None


# ---------------------------------------------------------------------------
# Memed session
# ---------------------------------------------------------------------------


class MemedSessionResponse(BaseModel):
    data_token: str
    script_url: str
    patient: dict


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


class ReferenceDataItem(BaseModel):
    id: int
    name: str