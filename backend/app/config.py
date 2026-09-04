"""Application settings, loaded from environment / .env via pydantic-settings.

Access the singleton `settings` anywhere: `from app.config import settings`.
Every configurable value belongs here — never read os.environ directly in
routers or services. Secrets live in `.env` (git-ignored); the defaults below
are local-dev conveniences only.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Miara API"
    API_VERSION: str = "v1"

    # Comma-separated list of allowed browser origins for CORS.
    ALLOWED_ORIGINS: str = "http://localhost:3010"

    # Infra native Ubuntu (PostgreSQL / RabbitMQ / Redis) — voir scripts/setup_ubuntu.sh.
    # Runtime = rôle miara_app (soumis au RLS). Migrations = miara_admin (BYPASSRLS).
    DATABASE_URL: str = "postgresql+asyncpg://miara_app:CHANGE_ME@localhost:5432/miara"
    DATABASE_URL_ADMIN: str = "postgresql+asyncpg://miara_admin:CHANGE_ME@localhost:5432/miara"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Clé Fernet pour les credentials d'intégration (ADR-005). Générer :
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # --- Auth (ADR-003) ---------------------------------------------------
    # Secret HS256 des JWT d'accès. Générer : openssl rand -hex 32
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 7
    # Rate limiting du login : 5 tentatives / 15 min par (email, IP).
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 900
    # True en production derrière TLS (cookies Secure) — carte déploiement.
    COOKIE_SECURE: bool = False


settings = Settings()
