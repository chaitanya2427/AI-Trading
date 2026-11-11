"""
Unit tests for configuration guardrails and secret masking.
"""

import pytest
from pydantic import ValidationError
from backend.app.core.config import Settings
from backend.app.core.logging import SecretMaskingFilter


def test_settings_default_safety_locks():
    settings = Settings(
        EXECUTION_MODE="PAPER",
        LIVE_TRADING_ENABLED=False,
        AGENT_BYPASS_ALLOWED=False,
    )
    assert settings.EXECUTION_MODE == "PAPER"
    assert settings.LIVE_TRADING_ENABLED is False
    assert settings.AGENT_BYPASS_ALLOWED is False
    assert settings.DAILY_LOSS_LIMIT_INR == 250.00


def test_settings_prevents_live_trading_in_paper_mode():
    with pytest.raises(ValidationError):
        Settings(
            EXECUTION_MODE="PAPER",
            LIVE_TRADING_ENABLED=True,  # Conflict: cannot be True in paper mode
        )


def test_settings_strictly_prevents_agent_bypass():
    with pytest.raises(ValidationError):
        Settings(AGENT_BYPASS_ALLOWED=True)


def test_settings_secret_redaction_in_repr():
    settings = Settings(
        UPSTOX_API_SECRET="super_secret_key_12345",
        UPSTOX_ACCESS_TOKEN="secret_access_token_abcdef",
    )
    repr_str = repr(settings)
    assert "super_secret_key_12345" not in repr_str
    assert "secret_access_token_abcdef" not in repr_str


def test_secret_masking_log_filter():
    filter_ = SecretMaskingFilter()
    msg = "Connecting with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and secret UPSTOX_API_SECRET=mysecretkey123"
    masked = filter_.mask_secrets(msg)
    assert "mysecretkey123" not in masked
    assert "Bearer ***REDACTED***" in masked

