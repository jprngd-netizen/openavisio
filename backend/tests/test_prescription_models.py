"""Tests for prescription domain models — singleton, enums, relationships."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionDocument,
    PrescriptionItem,
    PrescriptionStatus,
)


class TestPrescriberSingleton:
    """The Prescriber row is a singleton — only one row ever exists."""

    async def test_two_merges_one_row(self, db):
        """Two merges with the singleton ID result in exactly one row."""
        p1 = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name="Alice",
            family_name="Silva",
        )
        await db.merge(p1)
        await db.flush()

        p2 = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name="Alice",
            family_name="Silva",
        )
        await db.merge(p2)
        await db.flush()

        result = await db.execute(select(func.count()).select_from(Prescriber))
        assert result.scalar() == 1

    async def test_prescriber_has_fixed_id(self):
        """PRESCRIBER_SINGLETON_ID is the well-known fixed UUID."""
        assert PRESCRIBER_SINGLETON_ID == uuid.UUID("00000000-0000-0000-0000-000000000001")

    async def test_external_id_matches_str_id(self):
        """external_id should be set to str(id) at create time."""
        p = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name="Bob",
            family_name="Souza",
        )
        assert p.external_id == str(PRESCRIBER_SINGLETON_ID)


class TestPrescriptionStatus:
    """PrescriptionStatus enum values."""

    def test_enum_values(self):
        assert PrescriptionStatus.draft == "draft"
        assert PrescriptionStatus.issued == "issued"
        assert PrescriptionStatus.failed == "failed"
        assert PrescriptionStatus.deleted == "deleted"

    def test_enum_length(self):
        assert len(PrescriptionStatus) == 4

    def test_enum_is_strenum(self):
        assert issubclass(PrescriptionStatus, str)


class TestPrescriptionModel:
    """Prescription model creation and defaults."""

    def test_default_status_is_draft(self):
        assert Prescription.__table__.c.status.default.arg == "draft"

    def test_default_version_is_one(self):
        assert Prescription.__table__.c.version.default.arg == 1


class TestPrescriptionItemModel:
    """PrescriptionItem model creation."""

    def test_default_sort_order_zero(self):
        assert PrescriptionItem.__table__.c.sort_order.default.arg == 0


class TestPrescriptionDocumentModel:
    """PrescriptionDocument model creation."""

    def test_default_content_type(self):
        assert PrescriptionDocument.__table__.c.content_type.default.arg == "application/pdf"

    def test_default_kek_version(self):
        assert PrescriptionDocument.__table__.c.kek_version.default.arg == 1

    def test_default_signed_false(self):
        assert PrescriptionDocument.__table__.c.signed.default.arg is False


class TestModelImport:
    """All prescription models can be imported from app.models."""

    def test_import_prescriber(self):
        from app.models import Prescriber  # noqa: F811
        assert Prescriber is not None

    def test_import_prescription(self):
        from app.models import Prescription  # noqa: F811
        assert Prescription is not None

    def test_import_prescription_item(self):
        from app.models import PrescriptionItem  # noqa: F811
        assert PrescriptionItem is not None

    def test_import_prescription_document(self):
        from app.models import PrescriptionDocument  # noqa: F811
        assert PrescriptionDocument is not None

    def test_import_singleton_id(self):
        from app.models import PRESCRIBER_SINGLETON_ID  # noqa: F811
        assert PRESCRIBER_SINGLETON_ID == uuid.UUID("00000000-0000-0000-0000-000000000001")

    def test_import_status(self):
        from app.models import PrescriptionStatus  # noqa: F811
        assert PrescriptionStatus is not None