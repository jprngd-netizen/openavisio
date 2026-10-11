import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class NewbornRecordSex(StrEnum):
    """Sex recorded for the newborn (FExEO I.3).

    A controlled ``StrEnum`` kept verbatim as the instrument charts it
    (``F`` / ``M`` / ``indeterminado``). Nullable — often not charted at once.
    """

    female = "F"
    male = "M"
    indeterminado = "indeterminado"


class NewbornClassification(StrEnum):
    """Weight-for-gestational-age classification (FExEO I.3).

    ``AIG`` (adequate), ``PIG`` (small) and ``GIG`` (large) for gestational age;
    nullable because it depends on a known IG and weight.
    """

    AIG = "AIG"
    PIG = "PIG"
    GIG = "GIG"


class NewbornRecord(OwnedResource):
    """The structured record of a live newborn (FExEO-SUS I.2/I.3).

    A **1:1 record with a ``PregnancyOutcome``**: the newborn data (birth data,
    Apgar, anthropometry, the first physical exam system by system, reflexes,
    feeding, eliminations, immunization, congenital malformation, reanimation)
    only exists once the episode has closed with a live-birth outcome. The unique
    constraint on ``pregnancy_outcome_id`` makes "at most one newborn record per
    outcome" a database invariant, so a second registration can never happen even
    under a race.

    It is deliberately a separate resource rather than a JSON blob on
    ``NursingCare``: the ~60 charted fields (a whole physical exam system by
    system) do not fit cleanly in a structured-data JSON and deserve first-class
    columns for the discrete measurements. Following the plan principle "the
    record is a snapshot of its date", ``birth_datetime`` is the instant the
    newborn was born and the one date the record is anchored to.

    Every field is **nullable/additive**: the record may be created with only the
    outcome link and filled in progressively. The structured sub-objects (directed
    physical exam, reflexes, eliminations, immunization, reanimation) are ``JSONB``
    per the repo's JSON convention; ``congenital_malformation`` accepts either a
    boolean (present/absent) or a free-text description (which malformation).
    Isolation is by patient, resolved through the outcome's pregnancy; a
    cross-patient link is refused at the router (422).
    """

    __tablename__ = "newborn_records"
    __table_args__ = (
        # 1:1 with the outcome; also the idempotency guard for "one record only".
        UniqueConstraint("pregnancy_outcome_id", name="uq_newborn_records_pregnancy_outcome"),
    )

    pregnancy_outcome_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pregnancy_outcomes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The instant the newborn was born — the record's anchor and its only date.
    birth_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sexo (F/M/indeterminado).
    sex: Mapped[str | None] = mapped_column(String(20))
    # Tipo de parto (vaginal/abdominal/fórceps/vácuo/…).
    delivery_type: Mapped[str | None] = mapped_column(String(30))
    # IG em semanas e classificação peso × IG (AIG/PIG/GIG).
    gestational_age_weeks: Mapped[float | None] = mapped_column(Numeric(4, 1))
    classification: Mapped[str | None] = mapped_column(String(10))
    # Apgar no 1º/5º/10º minuto.
    apgar_1: Mapped[int | None] = mapped_column(Integer)
    apgar_5: Mapped[int | None] = mapped_column(Integer)
    apgar_10: Mapped[int | None] = mapped_column(Integer)
    # Antropometria: peso (g), comprimento, PC, PT, PA (cm).
    weight_g: Mapped[int | None] = mapped_column(Integer)
    length_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pc_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pt_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pa_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    # 1º exame físico do RN, sistema por sistema — JSON.
    physical_exam: Mapped[dict | None] = mapped_column(JSONB)
    # Reflexos primitivos (sucção, busca, preensão, Moro, marcha…) — JSON.
    reflexes: Mapped[dict | None] = mapped_column(JSONB)
    # Alimentação (leite materno livre demanda / ordenhado / fórmula / mista…).
    feeding: Mapped[str | None] = mapped_column(String(256))
    # Eliminações (diurese, mecônio) — JSON.
    eliminations: Mapped[dict | None] = mapped_column(JSONB)
    # Hipoglicemia e hipotermia (< 36,5 °C).
    hypoglycemia: Mapped[bool | None] = mapped_column(Boolean)
    hypothermia: Mapped[bool | None] = mapped_column(Boolean)
    # Imunização (BCG, HepB) — JSON.
    immunization: Mapped[dict | None] = mapped_column(JSONB)
    # Malformação congênita: booleana (presente/ausente) ou descrição (qual).
    congenital_malformation: Mapped[bool | str | None] = mapped_column(JSONB)
    # Reanimação neonatal (passos, medicações…) — JSON.
    reanimation: Mapped[dict | None] = mapped_column(JSONB)
    # Contato pele a pele 1h ininterrupto e clampeamento do cordão.
    skin_to_skin_1h: Mapped[bool | None] = mapped_column(Boolean)
    cord_clamping: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    # Proveniência (R4 Fase 3): o documento FExEO que materializou este registro.
    # Nullable; permite ao re-verify retrair só o que ESTE documento criou.
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True, index=True
    )
