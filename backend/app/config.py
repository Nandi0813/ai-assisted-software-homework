import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    jwt_secret: str
    access_token_minutes: int = 60


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("SPLITLEDGER_DATABASE_URL", "sqlite:///./splitledger.db"),
        jwt_secret=os.environ.get("SPLITLEDGER_JWT_SECRET") or secrets.token_urlsafe(32),
        access_token_minutes=int(os.environ.get("SPLITLEDGER_ACCESS_TOKEN_MINUTES", "60")),
    )
