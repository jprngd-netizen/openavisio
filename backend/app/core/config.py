from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_APP_SECRET = "dev-secret-not-for-production-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    app_secret: str = DEV_APP_SECRET
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # AI service
    ai_service_url: str = "http://localhost:8001"
    aiservice_token: str = ""  # shared secret for backend→aiservice calls (#46)

    @property
    def ai_service_headers(self) -> dict[str, str]:
        return {"X-AI-Service-Token": self.aiservice_token} if self.aiservice_token else {}

    # Document storage
    document_storage_path: str = "./data/documents"
    storage_backend: str = "local"  # "local" | "minio"

    # MinIO (used when storage_backend = "minio")
    minio_endpoint: str = ""
    minio_bucket: str = "openavisio"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000"

    # OCR / Pipeline
    embedding_scheduler_batch_size: int = 50
    embedding_scheduler_cron: str = "*/15 * * * *"

    # WebAuthn / Passkeys
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "OpenAvisio"
    webauthn_origin: str = "http://localhost:3000"

    # Document encryption (envelope scheme — see ADR 018)
    # Generate with: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
    document_encryption_key: str = ""

    # Licensing
    license_public_key: str = ""  # Ed25519 public key (raw 32 bytes, base64); empty = use embedded production key

    # Frontend URL used in email links (e.g. https://app.example.com)
    app_url: str = ""

    # One-time token gating POST /organization/init in production (see setup.sh)
    bootstrap_token: str = ""

    # Demo instances: when set, document upload accepts ONLY a file with exactly
    # this sha256 (the bundled sample), and patient photos are refused entirely.
    demo_locked_upload_sha256: str = ""

    # Environment
    environment: str = "development"
    # Off for test runs only: the suite logs in dozens of times from one client
    # and would trip its own limiter. Never disable this in production (#109).
    rate_limit_enabled: bool = True

    # Memed — Sinapse Prescrição integration
    memed_api_url: str = ""
    memed_script_url: str = ""
    memed_api_key: str = ""
    memed_secret_key: str = ""
    memed_environment: str = "integration"  # "integration" | "production"
    memed_use_fake: bool = False  # dev/e2e: use FakeMemedClient instead of real HTTP
    memed_emission_policy: str = "linked_user"  # "linked_user" | "any_admin"

    # Age encryption key for backup encryption (age binary, age-keygen to generate)
    age_pubkey: str = ""

    # Deployment mode — only "personal" is implemented in this version.
    # "clinic" and "multi_tenant" are reserved for future use and rejected explicitly.
    deployment_mode: str = "personal"

    # Extension hooks (OFF by default, no wiring yet)
    terms_url: str = ""
    telemetry_enabled: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    @model_validator(mode="after")
    def _validate_deployment_mode(self):
        """Reject unimplemented deployment modes explicitly — never a silent no-op."""
        valid = {"personal", "clinic", "multi_tenant"}
        if self.deployment_mode not in valid:
            raise ValueError(
                f"DEPLOYMENT_MODE={self.deployment_mode!r} is invalid; "
                f"must be one of {valid}"
            )
        if self.deployment_mode in ("clinic", "multi_tenant"):
            raise ValueError(
                f"DEPLOYMENT_MODE={self.deployment_mode!r} is not yet implemented. "
                "Only 'personal' is supported in this version."
            )
        return self

    @model_validator(mode="after")
    def _validate_emission_policy(self):
        """Reject invalid memed_emission_policy values."""
        valid = {"linked_user", "any_admin"}
        if self.memed_emission_policy not in valid:
            raise ValueError(
                f"MEMED_EMISSION_POLICY={self.memed_emission_policy!r} is invalid; "
                f"must be one of {valid}"
            )
        return self

    @model_validator(mode="after")
    def _guard_production(self):
        """Fail closed: never boot a non-dev instance with dev defaults.

        IMPORTANT — coherence over blanket rejection:
        The plan originally said "abort if MEMED_ENVIRONMENT != production".
        However, a legitimate explicit homolog deployment
        (ENVIRONMENT=production, MEMED_ENVIRONMENT=integration, homolog URLs)
        is a valid configuration for dry-run / staging.  We therefore enforce
        *coherence* instead: an explicit, coherent integration config is allowed;
        the dangerous mismatches (production env + homolog URLs, integration env
        + production URLs) abort.  See ADR / plan §T0.1.
        """
        if self.is_dev:
            return self
        problems = []
        if self.app_secret == DEV_APP_SECRET:
            problems.append("APP_SECRET is the built-in dev default")
        if not self.document_encryption_key:
            problems.append("DOCUMENT_ENCRYPTION_KEY is unset")
        if "devpassword123" in self.database_url:
            problems.append("DATABASE_URL uses the dev default password")
        if not self.rate_limit_enabled:
            problems.append("RATE_LIMIT_ENABLED=false — that switch exists for the test suite only")

        # ── Memed critical vars ────────────────────────────────────────────
        if not self.memed_api_url:
            problems.append("MEMED_API_URL is empty — required in production")
        if not self.memed_script_url:
            problems.append("MEMED_SCRIPT_URL is empty — required in production")
        if not self.memed_api_key:
            problems.append("MEMED_API_KEY is empty — required in production")
        if not self.memed_secret_key:
            problems.append("MEMED_SECRET_KEY is empty — required in production")

        # ── MEMED_USE_FAKE guard ───────────────────────────────────────────
        if self.memed_use_fake:
            problems.append("MEMED_USE_FAKE=true — that switch exists for dev/e2e only")

        # ── MEMED_ENVIRONMENT validity ─────────────────────────────────────
        if self.memed_environment not in ("integration", "production"):
            problems.append(
                f"MEMED_ENVIRONMENT={self.memed_environment!r} is invalid; "
                "must be 'integration' or 'production'"
            )

        # ── AGE_PUBKEY guard ───────────────────────────────────────────────
        if not self.age_pubkey:
            problems.append("AGE_PUBKEY is empty — backups cannot be encrypted")

        # ── Base/script coherence ──────────────────────────────────────────
        if self.memed_environment == "production":
            if "integrations.api.memed.com.br" in self.memed_api_url:
                problems.append(
                    "MEMED_API_URL points at homolog (integrations.api.memed.com.br) "
                    "but MEMED_ENVIRONMENT=production"
                )
            if "integrations.memed.com.br" in self.memed_script_url:
                problems.append(
                    "MEMED_SCRIPT_URL points at homolog (integrations.memed.com.br) "
                    "but MEMED_ENVIRONMENT=production"
                )
        elif self.memed_environment == "integration":
            # Check for production API URL, excluding homolog URLs which contain
            # "integrations.api.memed.com.br" (a superset of "api.memed.com.br").
            if "api.memed.com.br" in self.memed_api_url and "integrations.api.memed.com.br" not in self.memed_api_url:
                problems.append(
                    "MEMED_API_URL points at production (api.memed.com.br) "
                    "but MEMED_ENVIRONMENT=integration"
                )
            if "partners.memed.com.br" in self.memed_script_url:
                problems.append(
                    "MEMED_SCRIPT_URL points at production (partners.memed.com.br) "
                    "but MEMED_ENVIRONMENT=integration"
                )

        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=" + self.environment
                + ": " + "; ".join(problems)
            )
        return self


settings = Settings()
