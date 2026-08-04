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


settings = Settings()
