import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class PatientDto(OrmBase):
    id: uuid.UUID
    given_name: str
    family_name: str
    birth_date: date | None
    gender: str | None
    active: bool
    identifier: str | None
    created_at: datetime
    is_favorite: bool = False
    has_photo: bool = False

    # Identification (CPF only as last4 — the full value is encrypted at rest)
    cpf_last4: str | None = None
    cns: str | None = None
    email: str | None = None
    phone: str | None = None

    # Address (Brazilian format)
    cep: str | None = None
    street: str | None = None
    street_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city_name: str | None = None
    state_code: str | None = None


class _PatientContactFields(BaseModel):
    cns: str | None = None
    email: str | None = None
    phone: str | None = None
    cep: str | None = None
    street: str | None = None
    street_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city_name: str | None = None
    state_code: str | None = None


class PatientCreateRequest(_PatientContactFields):
    given_name: str
    family_name: str
    birth_date: date | None = None
    gender: str | None = None
    identifier: str | None = None
    # Store-only: encrypted before it reaches the database.
    cpf: str | None = None


class PatientUpdateRequest(_PatientContactFields):
    given_name: str | None = None
    family_name: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    active: bool | None = None
    identifier: str | None = None
    cpf: str | None = None