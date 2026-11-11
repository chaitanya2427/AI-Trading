"""
Core Configuration & Settings
Managed via Pydantic Settings with strict secret redaction and safety boundaries.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core System Environment
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "Asia/Kolkata"
    LOG_LEVEL: str = "INFO"

    # Execution Guardrails (Live trading fail-closed)
    EXECUTION_MODE: str = Field(default="PAPER", description="PAPER or LIVE")
    LIVE_TRADING_ENABLED: bool = Field(
        default=False,
        description="Must remain FALSE in research/paper trading mode",
    )
    AGENT_BYPASS_ALLOWED: bool = Field(
        default=False,
        description="Whether an AI agent can bypass risk controls (Strictly False)",
    )

    # Capital & Risk Controls
    STARTING_CAPITAL_INR: float = Field(
        default=25000.00,
        description="Strict available capital cap (must be <= 25,000 for initial safety)",
    )
    DAILY_LOSS_LIMIT_INR: float = Field(
        default=250.00,
        description="Maximum daily loss in INR. Triggers hard halt on reach.",
    )
    MAX_RISK_PER_TRADE_INR: float = Field(
        default=250.00,
        description="Maximum risk per single trade",
    )
    MAX_OPEN_POSITIONS: int = 2
    MAX_DAILY_TRADES: int = 6
    INTRADAY_SQUARE_OFF_TIME: str = "15:15"
    MAX_QUOTE_AGE_SECONDS: float = Field(
        default=5.0,
        description="Max acceptable market quote age in seconds before circuit breaker",
    )

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///data/trading_system.db"

    # Upstox API Configuration (Redacted from logs and representation)
    UPSTOX_API_KEY: Optional[str] = Field(default=None, repr=False)
    UPSTOX_API_SECRET: Optional[str] = Field(default=None, repr=False)
    UPSTOX_REDIRECT_URI: str = "http://127.0.0.1:8000/api/v1/auth/upstox/callback"
    UPSTOX_ACCESS_TOKEN: Optional[str] = Field(default=None, repr=False)

    # Optional TOTP-based credentials (Redacted)
    UPSTOX_USER_ID: Optional[str] = Field(default=None, repr=False)
    UPSTOX_USER_PIN: Optional[str] = Field(default=None, repr=False)
    UPSTOX_TOTP_SECRET: Optional[str] = Field(default=None, repr=False)

    # Optional Telegram Configuration (Redacted)
    TELEGRAM_BOT_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, repr=False)
    TELEGRAM_ALLOWED_CHAT_IDS: Optional[str] = Field(default=None, repr=False)
    TELEGRAM_NOTIFICATION_CHAT_ID: Optional[str] = Field(default=None, repr=False)

    # Web Server & Dashboard
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("LIVE_TRADING_ENABLED")
    @classmethod
    def validate_safety_lock(cls, v: bool, info) -> bool:
        if v:
            # Enforce that live trading cannot be set if execution mode is PAPER
            values = info.data
            if values.get("EXECUTION_MODE", "").upper() != "LIVE":
                raise ValueError("LIVE_TRADING_ENABLED cannot be True when EXECUTION_MODE is not LIVE.")
        return v

    @field_validator("AGENT_BYPASS_ALLOWED")
    @classmethod
    def enforce_no_agent_bypass(cls, v: bool) -> bool:
        if v:
            raise ValueError("AGENT_BYPASS_ALLOWED is strictly prohibited by system architecture.")
        return False

    @field_validator("DAILY_LOSS_LIMIT_INR")
    @classmethod
    def validate_loss_limit(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("DAILY_LOSS_LIMIT_INR must be positive.")
        if v > 1000.0:
            raise ValueError("DAILY_LOSS_LIMIT_INR exceeds safe initial conservative bounds (<= 1000 INR).")
        return v


settings = Settings()

