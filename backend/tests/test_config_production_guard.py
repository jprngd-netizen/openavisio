"""Tests for production config guard (_guard_production).

T0.1 — Extend _guard_production with Memed/AGE_PUBKEY/coherence checks.
T0.2 — MEMED_ENVIRONMENT accepted values.
"""
from __future__ import annotations

import pytest
from app.core.config import Settings


def _prod_settings(**kwargs) -> Settings:
    """Build a Settings instance with valid production defaults.

    Every field that _guard_production checks is set to a passing value.
    Individual tests override the field under test to trigger failures.
    """
    defaults = dict(
        environment="production",
        app_secret="a" * 32,  # not the dev default
        document_encryption_key="a" * 44,  # base64 32 bytes, not empty
        database_url="postgresql+asyncpg://user:pass@localhost:5432/vaultdb",
        rate_limit_enabled=True,
        # Memed — valid production config
        memed_api_url="https://api.memed.com.br",
        memed_script_url="https://partners.memed.com.br/integration.js",
        memed_api_key="test-key",
        memed_secret_key="test-secret",
        memed_environment="production",
        memed_use_fake=False,
        age_pubkey="age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )
    defaults.update(kwargs)
    return Settings(**defaults, _env_file=None)


class TestProductionGuard:
    """T0.1 — Production config guard rules."""

    # ── baseline ───────────────────────────────────────────────────────────

    def test_dev_mode_passes(self):
        """Dev mode should never trigger production guard."""
        s = Settings(environment="development", _env_file=None)
        assert s.is_dev

    def test_production_with_valid_config_passes(self):
        """All valid production values should pass without error."""
        s = _prod_settings()
        assert not s.is_dev
        assert s.memed_environment == "production"

    # ── rule 1: empty critical Memed vars ──────────────────────────────────

    def test_empty_memed_api_url_fails(self):
        with pytest.raises(ValueError, match="MEMED_API_URL"):
            _prod_settings(memed_api_url="")

    def test_empty_memed_script_url_fails(self):
        with pytest.raises(ValueError, match="MEMED_SCRIPT_URL"):
            _prod_settings(memed_script_url="")

    def test_empty_memed_api_key_fails(self):
        with pytest.raises(ValueError, match="MEMED_API_KEY"):
            _prod_settings(memed_api_key="")

    def test_empty_memed_secret_key_fails(self):
        with pytest.raises(ValueError, match="MEMED_SECRET_KEY"):
            _prod_settings(memed_secret_key="")

    # ── rule 2: MEMED_USE_FAKE must be false in production ─────────────────

    def test_memed_use_fake_true_fails(self):
        with pytest.raises(ValueError, match="MEMED_USE_FAKE"):
            _prod_settings(memed_use_fake=True)

    # ── rule 3: MEMED_ENVIRONMENT must be integration | production ─────────

    def test_invalid_memed_environment_fails(self):
        with pytest.raises(ValueError, match="MEMED_ENVIRONMENT"):
            _prod_settings(memed_environment="staging")

    # ── rule 4: AGE_PUBKEY must not be empty ───────────────────────────────

    def test_empty_age_pubkey_fails(self):
        with pytest.raises(ValueError, match="AGE_PUBKEY"):
            _prod_settings(age_pubkey="")

    # ── rule 5: base/script coherence ──────────────────────────────────────

    def test_production_env_with_homolog_api_url_fails(self):
        """MEMED_ENVIRONMENT=production but MEMED_API_URL points at homolog."""
        with pytest.raises(ValueError, match="MEMED_API_URL.*homolog"):
            _prod_settings(memed_api_url="https://integrations.api.memed.com.br")

    def test_production_env_with_homolog_script_url_fails(self):
        """MEMED_ENVIRONMENT=production but MEMED_SCRIPT_URL points at homolog."""
        with pytest.raises(ValueError, match="MEMED_SCRIPT_URL.*homolog"):
            _prod_settings(
                memed_script_url="https://integrations.memed.com.br/script.js"
            )

    def test_integration_env_with_prod_api_url_fails(self):
        """MEMED_ENVIRONMENT=integration but MEMED_API_URL points at production."""
        with pytest.raises(ValueError, match="MEMED_API_URL.*production"):
            _prod_settings(
                memed_environment="integration",
                memed_api_url="https://api.memed.com.br",
                memed_script_url="https://integrations.memed.com.br/script.js",
            )

    def test_integration_env_with_prod_script_url_fails(self):
        """MEMED_ENVIRONMENT=integration but MEMED_SCRIPT_URL points at production."""
        with pytest.raises(ValueError, match="MEMED_SCRIPT_URL.*production"):
            _prod_settings(
                memed_environment="integration",
                memed_api_url="https://integrations.api.memed.com.br",
                memed_script_url="https://partners.memed.com.br/integration.js",
            )

    # ── coherent configs must pass ─────────────────────────────────────────

    def test_integration_env_with_homolog_urls_passes(self):
        """Coherent integration config (env=integration + homolog URLs)."""
        s = _prod_settings(
            memed_environment="integration",
            memed_api_url="https://integrations.api.memed.com.br",
            memed_script_url="https://integrations.memed.com.br/script.js",
        )
        assert s.memed_environment == "integration"

    def test_production_env_with_prod_urls_passes(self):
        """Coherent production config (env=production + prod URLs)."""
        s = _prod_settings(
            memed_environment="production",
            memed_api_url="https://api.memed.com.br",
            memed_script_url="https://partners.memed.com.br/integration.js",
        )
        assert s.memed_environment == "production"