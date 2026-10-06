"""Tests for rate limiting on prescription write routes (T4.3).

Covers the ``enforce`` function from ``app.core.ratelimit`` applied to
``memed-session`` and ``capture`` endpoints.  Since ``RATE_LIMIT_ENABLED=false``
in the test environment (``.env.test``), these tests mock Redis to exercise the
rate-limit path directly.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.ratelimit import enforce


class TestRateLimitEnforce:
    """Unit tests for the ``enforce`` rate-limit function."""

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_enforce_passes_when_under_limit(self):
        """enforce() does nothing when the count is under the limit."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)  # under limit of 10
        mock_redis.ttl = AsyncMock(return_value=250)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock(return_value=None)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            # Should not raise
            await enforce("test:under", limit=10, window_seconds=60)

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_enforce_raises_429_when_limit_exceeded(self):
        """enforce() raises 429 when the count exceeds the limit."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=11)  # over limit of 10
        mock_redis.ttl = AsyncMock(return_value=250)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock(return_value=None)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await enforce("test:over", limit=10, window_seconds=60)
            assert exc_info.value.status_code == 429
            assert "Too many attempts" in exc_info.value.detail

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_enforce_returns_retry_after_header(self):
        """enforce() includes Retry-After header in the 429 response."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=11)
        mock_redis.ttl = AsyncMock(return_value=42)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock(return_value=None)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await enforce("test:retry", limit=10, window_seconds=60)
            assert exc_info.value.headers
            assert exc_info.value.headers.get("Retry-After") == "42"

    async def test_enforce_skipped_when_disabled(self):
        """enforce() is a no-op when rate_limit_enabled is False."""
        # Should not raise even with a high count
        await enforce("test:disabled", limit=1, window_seconds=60)

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_enforce_fails_open_when_redis_down(self):
        """enforce() fails open when Redis is unreachable."""
        with patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis down")):
            # Should not raise — fails open
            await enforce("test:redis-down", limit=10, window_seconds=60)


class TestRetryRateLimit:
    """Tests for the retry endpoint rate limit (rl:retry:ip:*)."""

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_retry_rate_limit_passes_when_under_limit(self):
        """Retry rate limit passes when count is under 10."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)
        mock_redis.ttl = AsyncMock(return_value=250)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock(return_value=None)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            await enforce("rl:retry:ip:127.0.0.1", limit=10, window_seconds=300)

    @patch("app.core.ratelimit.settings.rate_limit_enabled", True)
    async def test_retry_rate_limit_returns_429_when_exceeded(self):
        """Retry rate limit raises 429 when count exceeds 10."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=11)
        mock_redis.ttl = AsyncMock(return_value=250)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock(return_value=None)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await enforce("rl:retry:ip:127.0.0.1", limit=10, window_seconds=300)
            assert exc_info.value.status_code == 429
            assert "Too many attempts" in exc_info.value.detail