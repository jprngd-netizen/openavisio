"""add prescription tables and patient contact fields

Creates the four prescription-domain tables (prescribers, prescriptions,
prescription_items, prescription_documents) and adds the Memed-required
contact/CPF columns to patients.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "8f7e7b475af4"
down_revision = "g3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Prescriber (singleton) ---
    op.create_table(
        "prescribers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("external_id", sa.String(64), unique=True, nullable=False),
        sa.Column("given_name", sa.String(120), nullable=False),
        sa.Column("family_name", sa.String(120), nullable=False),
        sa.Column("cpf_encrypted", sa.Text, nullable=True),
        sa.Column("cpf_last4", sa.String(4), nullable=True),
        sa.Column("birth_date", sa.Date, nullable=True),
        sa.Column("board_code", sa.String(10), nullable=True),
        sa.Column("board_number", sa.String(30), nullable=True),
        sa.Column("board_state", sa.String(2), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("sex", sa.String(1), nullable=True),
        sa.Column("city_id", sa.Integer, nullable=True),
        sa.Column("specialty_id", sa.Integer, nullable=True),
        sa.Column("memed_user_id", sa.String(64), nullable=True),
        sa.Column("memed_status", sa.String(30), nullable=True),
    )

    # --- Prescription ---
    op.create_table(
        "prescriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("prescriber_id", UUID(as_uuid=True), sa.ForeignKey("prescribers.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), default="draft", index=True, nullable=False),
        sa.Column("version", sa.Integer, default=1, nullable=False),
        sa.Column("memed_prescription_id", sa.String(64), nullable=True),
        sa.Column("memed_prescription_uuid", sa.String(64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_by_memed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- PrescriptionItem ---
    op.create_table(
        "prescription_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("prescription_id", UUID(as_uuid=True), sa.ForeignKey("prescriptions.id"), nullable=False, index=True),
        sa.Column("medication_name", sa.String(512), nullable=False),
        sa.Column("posology", sa.Text, nullable=True),
        sa.Column("quantity", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer, default=0, nullable=False),
    )

    # --- PrescriptionDocument ---
    op.create_table(
        "prescription_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("prescription_id", UUID(as_uuid=True), sa.ForeignKey("prescriptions.id"), nullable=False, unique=True),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(100), default="application/pdf", nullable=False),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary, nullable=False),
        sa.Column("kek_version", sa.SmallInteger, default=1, nullable=False),
        sa.Column("signed", sa.Boolean, default=False, nullable=False),
        sa.Column("memed_prescription_id", sa.String(64), nullable=True),
        sa.Column("digital_link", sa.String(1024), nullable=True),
        sa.Column("unlock_code", sa.String(16), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- Patient columns for Memed integration ---
    op.add_column("patients", sa.Column("cpf_encrypted", sa.Text, nullable=True))
    op.add_column("patients", sa.Column("cpf_last4", sa.String(4), nullable=True))
    op.add_column("patients", sa.Column("email", sa.String(256), nullable=True))
    op.add_column("patients", sa.Column("phone", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "phone")
    op.drop_column("patients", "email")
    op.drop_column("patients", "cpf_last4")
    op.drop_column("patients", "cpf_encrypted")
    op.drop_table("prescription_documents")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
    op.drop_table("prescribers")