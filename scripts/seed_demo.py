#!/usr/bin/env python3
"""Seed the demo instance with Lena Hoffmann and 6 synthetic documents.

Run from the repo root after setting env vars:
  DOCUMENT_ENCRYPTION_KEY=<base64-32-bytes>  (required)
  DATABASE_URL=postgresql+asyncpg://...      (optional, defaults to dev URL)
  DOCUMENT_STORAGE_PATH=/path/to/storage    (optional, defaults to backend/data/documents)

Generate PDFs first if docs/demo/*.pdf are missing:
  python scripts/generate_demo_pdfs.py

Generate real embeddings before deploying the demo (optional but recommended):
  AI_SERVICE_URL=http://localhost:8001 python scripts/generate_demo_embeddings.py

Idempotent — safe to run multiple times. Skips all creation if Lena Hoffmann already exists.
"""

import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import date as DateType
from datetime import datetime, timezone
from pathlib import Path

# Allow importing from the backend package when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb",
)
os.environ.setdefault(
    "DOCUMENT_STORAGE_PATH",
    str(Path(__file__).parent.parent / "backend" / "data" / "documents"),
)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.encryption import encrypt_document  # noqa: E402
from app.core.patient_keys import ensure_patient_kek  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.models import (  # noqa: E402
    CalendarEvent,
    Condition,
    Correspondent,
    DocumentChunk,
    DocumentReference,
    Incident,
    MedicationStatement,
    Observation,
    Organization,
    Patient,
    PatientAccess,
    Recommendation,
    User,
    UserRole,
)

DOCS_DIR = Path(__file__).parent.parent / "docs" / "demo"
EMBEDDINGS_FILE = Path(__file__).parent / "demo_data" / "embeddings.json"

# ──────────────────────────────────────────────────────────────
# Demo data
# ──────────────────────────────────────────────────────────────

CORRESPONDENTS = [
    "Hausarztpraxis Dr. Schmidt",
    "St. Marien-Kinderklinik",
    "Zentrallabor Nordbaden",
    "Schulärztlicher Dienst Grundschule Am Fluss",
]

# Chunk texts must stay in sync with generate_demo_embeddings.py.
CHUNK_TEXTS: dict[str, list[str]] = {
    "01_gp_referral": [
        (
            "Hausarzt Dr. Klaus Schmidt überweist Lena Hoffmann, geboren am 14. Mai 2019, an die "
            "Abteilung für Neuropädiatrie der St. Marien-Kinderklinik. Lena hatte zwei fragliche "
            "generalisierte tonisch-klonische Anfallsereignisse: das erste am 15. Januar 2024 mit einer "
            "Dauer von circa 2 Minuten, das zweite am 28. Februar 2024. "
            "Im Intervall ist sie altersentsprechend entwickelt."
        ),
        (
            "Keine aktuelle Medikation. Keine Epilepsie in der Familienanamnese. Kein kürzlicher "
            "fieberhafter Infekt. Diagnose: Verdacht auf kindliche Epilepsie. Dr. Schmidt bittet um EEG "
            "und klinisch-neurologische Untersuchung. Um zeitnahe Vergabe eines neuropädiatrischen "
            "Termins wird gebeten."
        ),
    ],
    "02_eeg_report": [
        (
            "EEG bei Lena Hoffmann (geb. 14. Mai 2019) in der Neuropädiatrie der St. Marien-Kinderklinik "
            "am 2. April 2024. Die Ableitung zeigt bilateral synchrone 3-Hz-Spike-Wave-Komplexe im "
            "Wachzustand und im Schlaf, vereinbar mit einer Absence-Epilepsie des Kindesalters (CAE). "
            "Die Grundaktivität ist im Übrigen altersentsprechend unauffällig."
        ),
        (
            "Beurteilung: Pathologisches EEG, vereinbar mit einer Absence-Epilepsie des Kindesalters. "
            "Klinische Empfehlung: Beginn einer antikonvulsiven Therapie mit Valproat als Mittel der "
            "ersten Wahl. Neurologische Verlaufskontrolle in 3 Monaten."
        ),
    ],
    "03_neurology_followup": [
        (
            "Neuropädiatrische Verlaufskontrolle bei Lena Hoffmann am 15. Juli 2024 in der "
            "St. Marien-Kinderklinik. Beginn der Valproat-Therapie mit 300 mg/Tag in zwei Einzeldosen "
            "am 15. April 2024. Seit Therapiebeginn berichtet die Mutter Anna Hoffmann über keine "
            "weiteren Anfallsereignisse. Gewicht: 22.0 kg, Größe: 119 cm."
        ),
        (
            "Lena verträgt Valproat 300 mg/Tag gut, keine Nebenwirkungen berichtet. Aktuelle Dosis "
            "fortführen. Blutentnahme in 6 Monaten empfohlen: Valproat-Serumspiegel, Leberwerte und "
            "Blutbild. Wiedervorstellung in der Ambulanz in 6–12 Monaten."
        ),
    ],
    "04_blood_panel": [
        (
            "Laborbefund für Lena Hoffmann (geb. 14. Mai 2019), Probenentnahme am 20. Januar 2025. "
            "Valproat-Spiegel (Serum): 75.0 mcg/mL (therapeutischer Bereich 50–100 mcg/mL). "
            "ALT (GPT): 18 U/L (normal). AST (GOT): 22 U/L (normal)."
        ),
        (
            "Blutbild: Leukozyten 6.8 × 10⁹/L (normal), Hämoglobin 12.4 g/dL (normal). Alle Werte im "
            "Normbereich. Der Valproat-Spiegel liegt im therapeutischen Bereich; aktuelle Dosis "
            "fortführen. Kontrolle des Laborpanels in 6 Monaten."
        ),
    ],
    "05_school_health_check": [
        (
            "Jährliche Gesundheitsuntersuchung bei Lena Hoffmann (geb. 14. Mai 2019) zur Einschulung in "
            "die 1. Klasse, durchgeführt am 8. September 2025 durch den Schulärztlichen Dienst der "
            "Grundschule Am Fluss. Gewicht: 24.5 kg, Größe: 123 cm, BMI 16.2 kg/m² (normal). "
            "Visus: 6/6 rechts und links. Hörscreening: beidseits bestanden."
        ),
        (
            "Lenas Mutter berichtet, dass Lena unter Valproat bei Absence-Epilepsie des Kindesalters "
            "gut eingestellt ist. Keine Anfälle in den letzten 12 Monaten. Entwicklung "
            "altersentsprechend: Sprache, Feinmotorik, Grobmotorik und soziale Entwicklung unauffällig. "
            "Meilenstein Einschulung dokumentiert (1. Klasse, September 2025). Keine Auffälligkeiten."
        ),
    ],
    "06_hospital_discharge": [
        (
            "Entlassungsbericht für Lena Hoffmann (geb. 14. Mai 2019), stationäre Aufnahme am "
            "12. Februar 2026 nach beobachtetem Durchbruchanfall — generalisiert tonisch-klonisch, "
            "Dauer 3 Minuten, spontan sistierend. Vorgeschichte: Absence-Epilepsie des Kindesalters "
            "unter Valproat 300 mg/Tag seit April 2024."
        ),
        (
            "Valproat-Dosis erhöht auf 400 mg/Tag in zwei Einzeldosen (200 mg morgens, 200 mg abends), "
            "gültig ab 14. Februar 2026. Entlassung am 14. Februar 2026 in gutem Allgemeinzustand. "
            "Ambulante neuropädiatrische Kontrolle vereinbart für den 14. März 2026. Bei erneuten "
            "Anfällen umgehende Kontaktaufnahme mit der Neuropädiatrie."
        ),
    ],
}

DOCUMENTS: list[dict] = [
    {
        "key": "01_gp_referral",
        "filename": "01_gp_referral.pdf",
        "type": "referral",
        "issued_date": "2024-03-10",
        "correspondent": "Hausarztpraxis Dr. Schmidt",
        "description": "Hausärztliche Überweisung an die Neuropädiatrie bei fraglichen Anfallsereignissen",
        "document_classification": "referral",
        "detected_provider": "Hausarztpraxis Dr. Schmidt",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.95,
        "conditions": [
            {
                "code_display": "Verdacht auf kindliche Epilepsie",
                "clinical_status": "active",
                "onset_date_time": "2024-01-15",
            }
        ],
        "medications": [],
        "observations": [],
        "events": [
            {
                "title": "Neuropädiatrischer Termin in der St. Marien-Kinderklinik",
                "start_at": "2024-04-01",
                "all_day": True,
                "source": "pipeline",
                "status": "completed",
            }
        ],
        "recommendations": [
            "Neurologische Abklärung vereinbaren; EEG empfohlen",
        ],
        "incidents": [
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Anfall",
                "severity": "moderate",
                "occurred_at": "2024-01-15",
                "duration_minutes": 2,
                "status": "resolved",
                "symptoms": "Nicht ansprechbar, generalisierte tonisch-klonische Bewegungen",
                "outcome": "Spontan sistierend; postiktal circa 10 Minuten",
                "reported_to_provider": True,
            },
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Anfall",
                "severity": "moderate",
                "occurred_at": "2024-02-28",
                "duration_minutes": 2,
                "status": "resolved",
                "symptoms": "Nicht ansprechbar, generalisierte tonisch-klonische Bewegungen",
                "outcome": "Spontan sistierend",
                "reported_to_provider": True,
            },
        ],
    },
    {
        "key": "02_eeg_report",
        "filename": "02_eeg_report.pdf",
        "type": "diagnostic-report",
        "issued_date": "2024-04-02",
        "correspondent": "St. Marien-Kinderklinik",
        "description": "EEG-Befund — pathologisch, vereinbar mit Absence-Epilepsie des Kindesalters",
        "document_classification": "diagnostic-report",
        "detected_provider": "St. Marien-Kinderklinik",
        "ocr_confidence": 0.99,
        "extraction_confidence": 0.96,
        "conditions": [
            {
                "code_display": "Absence-Epilepsie des Kindesalters (CAE)",
                "clinical_status": "active",
                "severity": "moderate",
                "onset_date_time": "2024-01-15",
            }
        ],
        "medications": [],
        "observations": [
            {
                "code_display": "EEG (Elektroenzephalogramm)",
                "category": "laboratory",
                "effective_date_time": "2024-04-02",
                "value_string": (
                    "Pathologisch — bilateral synchrone 3-Hz-Spike-Wave-Komplexe, "
                    "vereinbar mit einer Absence-Epilepsie des Kindesalters"
                ),
            }
        ],
        "events": [],
        "recommendations": [
            "Beginn einer antikonvulsiven Therapie — Valproat als Mittel der ersten Wahl bei CAE empfohlen",
            "Wiedervorstellung in der neuropädiatrischen Ambulanz in 3 Monaten",
        ],
    },
    {
        "key": "03_neurology_followup",
        "filename": "03_neurology_followup.pdf",
        "type": "clinical-note",
        "issued_date": "2024-07-15",
        "correspondent": "St. Marien-Kinderklinik",
        "description": "Neuropädiatrische Verlaufskontrolle — Valproat begonnen, keine Anfälle seit April 2024",
        "document_classification": "clinical-note",
        "detected_provider": "St. Marien-Kinderklinik",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.94,
        "conditions": [],
        "medications": [
            {
                "medication_display": "Valproat",
                "dosage_text": "300 mg/Tag in zwei Einzeldosen (150 mg morgens, 150 mg abends)",
                "dose_quantity": 300.0,
                "dose_unit": "mg",
                "route": "oral",
                "effective_start": "2024-04-15",
                "status": "active",
                "reason_code": "Absence-Epilepsie des Kindesalters",
            }
        ],
        "observations": [
            {
                "code_display": "Körpergewicht",
                "category": "vital-signs",
                "effective_date_time": "2024-07-15",
                "value_quantity": 22.0,
                "value_unit": "kg",
            },
            {
                "code_display": "Körpergröße",
                "category": "vital-signs",
                "effective_date_time": "2024-07-15",
                "value_quantity": 119.0,
                "value_unit": "cm",
            },
        ],
        "events": [],
        "recommendations": [
            "Valproat 300 mg/Tag fortführen — sehr gutes frühes Ansprechen",
            "Blutentnahme in 6 Monaten: Valproat-Spiegel, Leberwerte, Blutbild",
        ],
    },
    {
        "key": "04_blood_panel",
        "filename": "04_blood_panel.pdf",
        "type": "laboratory-report",
        "issued_date": "2025-01-20",
        "correspondent": "Zentrallabor Nordbaden",
        "description": "Laborbefund — Valproat-Spiegel therapeutisch, Leberwerte unauffällig",
        "document_classification": "laboratory-report",
        "detected_provider": "Zentrallabor Nordbaden",
        "ocr_confidence": 0.99,
        "extraction_confidence": 0.97,
        "conditions": [],
        "medications": [],
        "observations": [
            {
                "code_display": "Valproat-Spiegel (Serum)",
                "category": "laboratory",
                "effective_date_time": "2025-01-20",
                "value_quantity": 75.0,
                "value_unit": "mcg/mL",
            },
            {
                "code_display": "ALT (GPT)",
                "category": "laboratory",
                "effective_date_time": "2025-01-20",
                "value_quantity": 18.0,
                "value_unit": "U/L",
            },
            {
                "code_display": "AST (GOT)",
                "category": "laboratory",
                "effective_date_time": "2025-01-20",
                "value_quantity": 22.0,
                "value_unit": "U/L",
            },
            {
                "code_display": "Leukozyten",
                "category": "laboratory",
                "effective_date_time": "2025-01-20",
                "value_quantity": 6.8,
                "value_unit": "10^9/L",
            },
            {
                "code_display": "Hämoglobin",
                "category": "laboratory",
                "effective_date_time": "2025-01-20",
                "value_quantity": 12.4,
                "value_unit": "g/dL",
            },
        ],
        "events": [],
        "recommendations": [
            "Valproat-Spiegel im therapeutischen Bereich (50–100 mcg/mL); aktuelle Dosis fortführen",
            "Laborkontrolle in 6 Monaten",
        ],
    },
    {
        "key": "05_school_health_check",
        "filename": "05_school_health_check.pdf",
        "type": "health-assessment",
        "issued_date": "2025-09-08",
        "correspondent": "Schulärztlicher Dienst Grundschule Am Fluss",
        "description": "Jährliche Schulgesundheitsuntersuchung — Einschulung 1. Klasse",
        "document_classification": "health-assessment",
        "detected_provider": "Schulärztlicher Dienst Grundschule Am Fluss",
        "ocr_confidence": 0.97,
        "extraction_confidence": 0.93,
        "conditions": [],
        "medications": [],
        "observations": [
            {
                "code_display": "Körpergewicht",
                "category": "vital-signs",
                "effective_date_time": "2025-09-08",
                "value_quantity": 24.5,
                "value_unit": "kg",
            },
            {
                "code_display": "Körpergröße",
                "category": "vital-signs",
                "effective_date_time": "2025-09-08",
                "value_quantity": 123.0,
                "value_unit": "cm",
            },
            {
                "code_display": "Visus (rechtes Auge)",
                "category": "vital-signs",
                "effective_date_time": "2025-09-08",
                "value_string": "6/6 (normal)",
            },
            {
                "code_display": "Visus (linkes Auge)",
                "category": "vital-signs",
                "effective_date_time": "2025-09-08",
                "value_string": "6/6 (normal)",
            },
            {
                "code_display": "Hörscreening (beidseits)",
                "category": "vital-signs",
                "effective_date_time": "2025-09-08",
                "value_string": "Bestanden",
            },
        ],
        "events": [
            {
                "title": "Einschulung 1. Klasse — Entwicklungs-Meilenstein",
                "start_at": "2025-09-01",
                "all_day": True,
                "source": "pipeline",
                "status": "completed",
                "purpose": "Meilenstein — Einschulung (6 Jahre)",
            }
        ],
        "recommendations": [
            "Keine Auffälligkeiten bei der Einschulung; routinemäßige Verlaufskontrollen fortführen",
        ],
    },
    {
        "key": "06_hospital_discharge",
        "filename": "06_hospital_discharge.pdf",
        "type": "discharge-summary",
        "issued_date": "2026-02-14",
        "correspondent": "St. Marien-Kinderklinik",
        "description": "Entlassungsbericht — Durchbruchanfall, Valproat-Dosis auf 400 mg/Tag erhöht",
        "document_classification": "discharge-summary",
        "detected_provider": "St. Marien-Kinderklinik",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.95,
        "conditions": [],
        "medications": [
            {
                "medication_display": "Valproat",
                "dosage_text": "400 mg/Tag in zwei Einzeldosen (200 mg morgens, 200 mg abends)",
                "dose_quantity": 400.0,
                "dose_unit": "mg",
                "route": "oral",
                "effective_start": "2026-02-14",
                "status": "active",
                "reason_code": "Absence-Epilepsie des Kindesalters — Durchbruchanfall",
            }
        ],
        "observations": [],
        "incidents": [
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Durchbruchanfall",
                "severity": "moderate",
                "occurred_at": "2026-02-12",
                "duration_minutes": 3,
                "status": "resolved",
                "symptoms": "Generalisiert tonisch-klonisch, spontan sistierend",
                "actions_taken": "Rettungsdienst alarmiert; stationäre Aufnahme in der St. Marien-Kinderklinik",
                "outcome": "Stationär aufgenommen; Valproat-Dosis auf 400 mg/Tag erhöht; Entlassung am 14. Feb 2026",
                "reported_to_provider": True,
                "reported_to_provider_at": "2026-02-12",
            },
        ],
        "events": [
            {
                "title": "Ambulante neuropädiatrische Kontrolle — nach Durchbruchanfall",
                "start_at": "2026-03-14",
                "all_day": True,
                "source": "pipeline",
                "status": "scheduled",
                "purpose": "Neuropädiatrische Kontrolle nach Entlassung wegen Durchbruchanfall",
            }
        ],
        "recommendations": [
            "Valproat-Dosis auf 400 mg/Tag in zwei Einzeldosen erhöht",
            "Ambulante neuropädiatrische Kontrolle in 4 Wochen (14. März 2026)",
            "Bei erneuten Anfällen vor dem Kontrolltermin umgehende Kontaktaufnahme mit der Neuropädiatrie",
        ],
    },
]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _load_embeddings() -> tuple[dict[str, list[list[float]]], bool]:
    """Return (embeddings_dict, is_placeholder).

    embeddings_dict maps doc_key → list of embedding vectors.
    Returns empty dict and is_placeholder=True if the file is missing or is a placeholder.
    """
    if not EMBEDDINGS_FILE.exists():
        return {}, True
    data = json.loads(EMBEDDINGS_FILE.read_text())
    if data.get("placeholder", True):
        return {}, True
    return data.get("embeddings", {}), False


async def _get_or_create_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization))
    org = result.scalars().first()
    if not org:
        org = Organization(name="OpenAvisio")
        db.add(org)
        await db.flush()
    return org


async def _get_or_create_user(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: UserRole,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=True,
            email_confirmed=True,
        )
        db.add(user)
        await db.flush()
    return user


async def _get_or_create_correspondent(
    db: AsyncSession, name: str, org_id: uuid.UUID
) -> Correspondent:
    result = await db.execute(
        select(Correspondent).where(
            Correspondent.name == name,
            Correspondent.organization_id == org_id,
        )
    )
    corr = result.scalar_one_or_none()
    if not corr:
        corr = Correspondent(name=name, organization_id=org_id)
        db.add(corr)
        await db.flush()
    return corr


def _encrypt_and_store(pdf_path: Path, patient_id: uuid.UUID, doc_id: uuid.UUID, kek: bytes) -> tuple[bytes, bytes, str, int, str]:
    """Encrypt PDF and write to storage. Returns (ciphertext, wrapped_dek, storage_key, size)."""
    data = pdf_path.read_bytes()
    size = len(data)
    file_hash = hashlib.sha256(data).hexdigest()
    ciphertext, wrapped_dek = encrypt_document(data, kek)
    storage_key = f"{patient_id}/{doc_id}.enc"
    get_storage().write(storage_key, ciphertext)
    return ciphertext, wrapped_dek, storage_key, size, file_hash


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    embeddings, is_placeholder = _load_embeddings()
    if is_placeholder:
        print(
            "WARNING: scripts/demo_data/embeddings.json is a placeholder.\n"
            "  The AI Health Assistant will not work semantically on the demo instance.\n"
            "  Run: AI_SERVICE_URL=http://... python scripts/generate_demo_embeddings.py\n"
        )

    # Verify PDFs exist before starting DB work
    missing = [d["filename"] for d in DOCUMENTS if not (DOCS_DIR / d["filename"]).exists()]
    if missing:
        print("ERROR: Missing demo PDFs. Run: python scripts/generate_demo_pdfs.py", file=sys.stderr)
        for f in missing:
            print(f"  {DOCS_DIR / f}", file=sys.stderr)
        sys.exit(1)

    async with Session() as db:
        # Idempotency guard
        existing = await db.execute(
            select(Patient).where(
                Patient.given_name == "Lena",
                Patient.family_name == "Hoffmann",
            )
        )
        if existing.scalar_one_or_none():
            print("Lena Hoffmann already exists — nothing to do.")
            return

        print("Seeding demo data …")

        org = await _get_or_create_org(db)
        print(f"  Organization: {org.name}")

        admin = await _get_or_create_user(
            db,
            email="admin@demo.openavisio.org",
            password="Demo123!Admin",
            first_name="Admin",
            last_name="User",
            role=UserRole.admin,
        )
        caregiver_user = await _get_or_create_user(
            db,
            email="caregiver@demo.openavisio.org",
            password="Demo123!Care",
            first_name="Anna",
            last_name="Hoffmann",
            role=UserRole.user,
        )
        print(f"  Users: {admin.email}, {caregiver_user.email}")

        # Patient
        patient = Patient(
            created_by=admin.id,
            given_name="Lena",
            family_name="Hoffmann",
            birth_date="2019-05-14",
            gender="female",
            active=True,
        )
        db.add(patient)
        await db.flush()
        # per-patient KEK (ADR 031) — documents are encrypted to it
        kek = await ensure_patient_kek(db, patient.id)
        print(f"  Patient: Lena Hoffmann ({patient.id})")

        # The admin ROLE confers no clinical access (ADR 025) — the demo admin
        # needs an explicit grant like anyone else
        db.add(
            PatientAccess(
                patient_id=patient.id,
                user_id=admin.id,
                access_level="admin",
                granted_by_user_id=admin.id,
                granted_at=datetime.now(timezone.utc),
            )
        )

        # Caregiver access
        db.add(
            PatientAccess(
                patient_id=patient.id,
                user_id=caregiver_user.id,
                access_level="view",
                granted_by_user_id=admin.id,
                granted_at=datetime.now(timezone.utc),
                relationship="mother",
                purpose="Primäre Bezugsperson — Lenas Mutter",
            )
        )

        # Correspondents
        corr_map: dict[str, Correspondent] = {}
        for name in CORRESPONDENTS:
            corr_map[name] = await _get_or_create_correspondent(db, name, org.id)
        print(f"  Correspondents: {len(corr_map)}")

        # Documents
        for doc_def in DOCUMENTS:
            key = doc_def["key"]
            pdf_path = DOCS_DIR / doc_def["filename"]
            doc_id = uuid.uuid4()

            _, wrapped_dek, storage_key, size, file_hash = _encrypt_and_store(
                pdf_path, patient.id, doc_id, kek
            )

            correspondent = corr_map[doc_def["correspondent"]]
            extracted_text = " ".join(CHUNK_TEXTS[key])

            doc = DocumentReference(
                id=doc_id,
                patient_id=patient.id,
                owner_id=admin.id,
                status="current",
                type=doc_def["type"],
                description=doc_def["description"],
                issued_date=DateType.fromisoformat(doc_def["issued_date"]),
                file_name=doc_def["filename"],
                content_type="application/pdf",
                size=size,
                storage_path=storage_key,
                hash=file_hash,
                encrypted_dek=wrapped_dek,
                processing_status="completed",
                verification_status="verified",
                document_classification=doc_def["document_classification"],
                detected_provider=doc_def["detected_provider"],
                ocr_confidence=doc_def["ocr_confidence"],
                extraction_confidence=doc_def["extraction_confidence"],
                extracted_text=extracted_text,
                correspondent_id=correspondent.id,
                extraction_json={
                    "summary": doc_def["description"],
                    "observations": [],
                    "diagnoses": [],
                    "medications": [],
                    "appointments": [],
                    "recommendations": doc_def["recommendations"],
                },
            )
            db.add(doc)
            await db.flush()

            # Clinical data
            for c in doc_def["conditions"]:
                db.add(Condition(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    code_display=c["code_display"],
                    clinical_status=c.get("clinical_status", "active"),
                    severity=c.get("severity"),
                    onset_date_time=c.get("onset_date_time"),
                    recorded_date=doc_def["issued_date"],
                ))

            for m in doc_def["medications"]:
                db.add(MedicationStatement(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    medication_display=m["medication_display"],
                    status=m.get("status", "active"),
                    dosage_text=m.get("dosage_text"),
                    dose_quantity=m.get("dose_quantity"),
                    dose_unit=m.get("dose_unit"),
                    route=m.get("route"),
                    effective_start=m.get("effective_start"),
                    reason_code=m.get("reason_code"),
                    date_asserted=doc_def["issued_date"],
                ))

            for o in doc_def["observations"]:
                db.add(Observation(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    code_display=o["code_display"],
                    category=o.get("category"),
                    effective_date_time=o.get("effective_date_time"),
                    value_quantity=o.get("value_quantity"),
                    value_unit=o.get("value_unit"),
                    value_string=o.get("value_string"),
                    status="final",
                ))

            for e in doc_def["events"]:
                db.add(CalendarEvent(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    title=e["title"],
                    start_at=e["start_at"],
                    all_day=e.get("all_day", True),
                    source=e.get("source", "pipeline"),
                    status=e.get("status", "scheduled"),
                    purpose=e.get("purpose"),
                ))

            for rec_text in doc_def["recommendations"]:
                db.add(Recommendation(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    text=rec_text,
                    status="active",
                ))

            for inc in doc_def.get("incidents", []):
                db.add(Incident(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    incident_type=inc["incident_type"],
                    incident_type_display=inc.get("incident_type_display"),
                    severity=inc.get("severity", "mild"),
                    status=inc.get("status", "resolved"),
                    occurred_at=inc["occurred_at"],
                    duration_minutes=inc.get("duration_minutes"),
                    symptoms=inc.get("symptoms"),
                    actions_taken=inc.get("actions_taken"),
                    outcome=inc.get("outcome"),
                    reported_to_provider=inc.get("reported_to_provider", False),
                    reported_to_provider_at=inc.get("reported_to_provider_at"),
                ))

            # Document chunks (embeddings)
            doc_vectors = embeddings.get(key, [])
            for i, chunk_text in enumerate(CHUNK_TEXTS[key]):
                vector = doc_vectors[i] if i < len(doc_vectors) else None
                db.add(DocumentChunk(
                    document_reference_id=doc_id,
                    patient_id=patient.id,
                    chunk_index=i,
                    content=chunk_text,
                    embedding=vector,
                ))

            print(f"  Document: {doc_def['filename']}")

        await db.commit()

    print("\nDone. Demo credentials:")
    print("  Admin:     admin@demo.openavisio.org / Demo123!Admin")
    print("  Caregiver: caregiver@demo.openavisio.org / Demo123!Care")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
