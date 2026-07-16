import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organization(Base):
    """Singleton — one row, no soft delete."""

    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="OpenAvisio")
    description: Mapped[str | None] = mapped_column(Text)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    license_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Operator's legal details (#112). OpenAvisio is self-hosted: the duty under
    # §5 DDG and Art. 13 GDPR is the OPERATOR's, not the project's — so these are
    # configured per instance and never baked into the repository.
    legal_name: Mapped[str | None] = mapped_column(String(256))
    legal_street: Mapped[str | None] = mapped_column(String(256))
    legal_postcode: Mapped[str | None] = mapped_column(String(32))
    legal_city: Mapped[str | None] = mapped_column(String(128))
    legal_country: Mapped[str | None] = mapped_column(String(128))
    legal_email: Mapped[str | None] = mapped_column(String(256))
    legal_phone: Mapped[str | None] = mapped_column(String(64))
    legal_responsible: Mapped[str | None] = mapped_column(String(256))
    legal_vat_id: Mapped[str | None] = mapped_column(String(64))
    legal_register: Mapped[str | None] = mapped_column(String(256))
    dpo_contact: Mapped[str | None] = mapped_column(Text)
