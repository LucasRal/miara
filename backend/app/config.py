"""Application settings, loaded from environment / .env via pydantic-settings.

Access the singleton `settings` anywhere: `from app.config import settings`.
Every configurable value belongs here — never read os.environ directly in
routers or services.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Thesis API"
    API_VERSION: str = "v1"

    # Comma-separated list of allowed browser origins for CORS.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Uncomment and populate when you add a database / auth layer.
    # To add an async SQLAlchemy + Alembic Postgres layer, use the
    # `fastapi-db-layer` skill (it uncomments DATABASE_URL for you).
    # DATABASE_URL: str = ""
    # JWT_SECRET: str = ""


settings = Settings()
