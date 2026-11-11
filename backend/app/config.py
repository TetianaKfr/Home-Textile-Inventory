import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://textile:textile@localhost:5432/textile",
        )
        self.jwt_secret = os.environ.get("JWT_SECRET", "dev-only-change-this-secret")
        self.storage_dir = os.environ.get("STORAGE_DIR", "/data/photos")
        self.public_base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")
        self.token_hours = int(os.environ.get("TOKEN_HOURS", "72"))
        self.seed_demo = os.environ.get("SEED_DEMO", "true").lower() in {"1", "true", "yes"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
