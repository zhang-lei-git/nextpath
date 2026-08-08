from pathlib import Path
import os


class Settings:
    app_name = "NextPath API"
    api_prefix = "/api/v1"
    data_dir = Path(__file__).resolve().parents[2] / "var"
    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{data_dir / 'nextpath.db'}",
    )
    upload_dir = Path(os.getenv("UPLOAD_DIR", data_dir / "uploads"))
    max_upload_size = 10 * 1024 * 1024
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    data_admin_key = os.getenv("DATA_ADMIN_KEY")
    public_api_base_url = os.getenv("PUBLIC_API_BASE_URL", "https://nextpath.top/api/v1").rstrip("/")
    wechat_app_id = os.getenv("WECHAT_APP_ID")
    wechat_app_secret = os.getenv("WECHAT_APP_SECRET")
    auth_signing_secret = os.getenv("AUTH_SIGNING_SECRET")
    report_signing_secret = os.getenv("REPORT_SIGNING_SECRET")
    auth_token_ttl_seconds = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(30 * 24 * 60 * 60)))
    report_token_ttl_seconds = int(os.getenv("REPORT_TOKEN_TTL_SECONDS", "600"))
    allow_demo_identity = os.getenv("ALLOW_DEMO_IDENTITY", "true").lower() in {"1", "true", "yes"}


settings = Settings()
