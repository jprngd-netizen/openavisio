"""Prescription domain models — Prescriber, Prescription, PrescriptionItem, PrescriptionDocument.

Prescriber is a singleton (one row per Organization) enforced by the fixed
PRESCRIBER_SINGLETON_ID.  Prescription is an OwnedResource (tracks the creating
User).  Items and Document are child aggregates cascaded from Prescription.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnedResource

PRESCRIBER_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
"""Fixed UUID that forces the Prescriber table to hold at most one row."""


class PrescriptionStatus(StrEnum):
    draft = "draft"
    issued = "issued"
    failed = "failed"
    deleted = "deleted"


class Prescriber(BaseModel):
    """Singleton prescriber — exactly one row per Organization.

    The fixed id (PRESCRIBER_SINGLETON_ID) enforces the singleton.
    external_id must be set explicitly to str(id) at create time so that
    the Memed API receives a stable, reproducible identifier.
    """

    __tablename__ = "prescribers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=PRESCRIBER_SINGLETON_ID,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True,
    )
    # external_id is set explicitly to str(id) at create time — it is the
    # stable identifier the Memed API uses to recognise this prescriber.
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    cpf_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    cpf_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    board_code: Mapped[str | None] = mapped_column(String(10))
    board_number: Mapped[str | None] = mapped_column(String(30))
    board_state: Mapped[str | None] = mapped_column(String(2))
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    city_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specialty_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memed_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memed_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    prescriptions: Mapped[list["Prescription"]] = relationship(
        "Prescription", back_populates="prescriber", lazy="select",
    )


class Prescription(OwnedResource):
    """A prescription draft or issued prescription for a Patient.

    Status machine: draft → issued | failed, failed → draft, and any
    non-deleted status → deleted (via prescricaoExcluida event).
    """

    __tablename__ = "prescriptions"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True,
    )
    prescriber_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescribers.id"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default=PrescriptionStatus.draft, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    memed_prescription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memed_prescription_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_by_memed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prescriber: Mapped["Prescriber"] = relationship("Prescriber", back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        "PrescriptionItem", back_populates="prescription",
        cascade="all, delete-orphan",
    )
    document: Mapped["PrescriptionDocument | None"] = relationship(
        "PrescriptionDocument", back_populates="prescription",
        uselist=False, cascade="all, delete-orphan",
    )


class PrescriptionItem(BaseModel):
    """A single line item on a Prescription draft.

    This is a local scratch snapshot — the authoritative content of an issued
    Prescription is the signed PDF stored in PrescriptionDocument.
    """

    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False, index=True,
    )
    medication_name: Mapped[str] = mapped_column(String(512), nullable=False)
    posology: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    prescription: Mapped["Prescription"] = relationship("Prescription", back_populates="items")


class PrescriptionDocument(BaseModel):
    """The archived signed PDF of an issued Prescription.

    Downloaded from Memed at capture time, encrypted with the patient's KEK
    (per-patient envelope encryption, ADR-031), and stored separately from the
    Document vault.  Never processed through OCR or the AI Pipeline.
    """

    __tablename__ = "prescription_documents"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False, unique=True,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_version: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    signed: Mapped[bool] = mapped_column(Boolean, default=False)
    memed_prescription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    digital_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    unlock_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    prescription: Mapped["Prescription"] = relationship("Prescription", back_populates="document")