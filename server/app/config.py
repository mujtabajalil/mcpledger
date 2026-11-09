from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    env: str = field(default_factory=lambda: os.environ.get("MCPLEDGER_ENV", "development"))
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./mcpledger.db"))
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/"))
    # Comma-separated origins allowed to make cookie-authenticated writes (CSRF guard).
    allowed_origins: list[str] = field(default_factory=lambda: [o.strip().rstrip("/") for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:4200").split(",") if o.strip()])
    secure_cookies: bool = field(default_factory=lambda: _bool("SECURE_COOKIES", False))
    session_days: int = field(default_factory=lambda: int(os.environ.get("SESSION_DAYS", "14")))
    static_dir: str = field(default_factory=lambda: os.environ.get("STATIC_DIR", ""))
    signups_open: bool = field(default_factory=lambda: _bool("SIGNUPS_OPEN", True))
    # Paddle Billing (merchant of record: works for sellers based in Pakistan).
    paddle_env: str = field(default_factory=lambda: os.environ.get("PADDLE_ENV", "sandbox"))
    paddle_client_token: str = field(default_factory=lambda: os.environ.get("PADDLE_CLIENT_TOKEN", ""))
    paddle_webhook_secret: str = field(default_factory=lambda: os.environ.get("PADDLE_WEBHOOK_SECRET", ""))
    paddle_price_team: str = field(default_factory=lambda: os.environ.get("PADDLE_PRICE_TEAM", ""))
    paddle_price_business: str = field(default_factory=lambda: os.environ.get("PADDLE_PRICE_BUSINESS", ""))
    max_report_bytes: int = field(default_factory=lambda: int(os.environ.get("MAX_REPORT_BYTES", str(8 * 1024 * 1024))))

    @property
    def is_prod(self) -> bool:
        return self.env == "production"


settings = Settings()

PLANS = {
    "free": {"label": "Free", "price": 0, "max_devices": 3, "slack": False, "audit_export": False, "history_days": 14},
    "team": {"label": "Team", "price": 29, "max_devices": 25, "slack": True, "audit_export": False, "history_days": 365},
    "business": {"label": "Business", "price": 199, "max_devices": 10_000, "slack": True, "audit_export": True,
                 "history_days": 730},
}
