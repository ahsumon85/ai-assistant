from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — PostgreSQL in production; SQLite for quick local dev
    database_url: str = "postgresql+psycopg://jobflow:jobflow@localhost:5432/jobflow"

    # Redis / background jobs
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    default_admin_email: str = "admin@jobflow.example"
    default_admin_password: str = "admin123"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8000"

    # LLM — ollama (local) or openai
    llm_provider: str = "ollama"  # ollama | openai
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout: float = 120.0
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    match_threshold: int = 70

    # Inbound email (IMAP) — job alerts from LinkedIn, Indeed, etc.
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_use_ssl: bool = True
    imap_mark_read: bool = True
    imap_fetch_limit: int = 50
    imap_linkedin_fetch_limit: int = 500
    imap_job_senders: str = "linkedin.com,indeed.com,notifications.linkedin.com,mail.indeed.com,jobs-noreply@linkedin.com"
    imap_subject_keywords: str = "job,alert,opening,position,hire,recruit"

    # Outbound email (Gmail/Outlook OAuth)
    email_provider: str = "dry_run"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/integrations/gmail/callback"
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = "http://localhost:8000/api/integrations/outlook/callback"

    # Webhook secrets (set in ATS dashboards)
    greenhouse_webhook_secret: str = ""
    lever_webhook_secret: str = ""
    ingest_api_key: str = ""

    # App
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    log_level: str = "INFO"
    rate_limit: str = "100/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def imap_job_senders_list(self) -> list[str]:
        return [s.strip() for s in self.imap_job_senders.split(",") if s.strip()]

    @property
    def imap_subject_keywords_list(self) -> list[str]:
        return [s.strip() for s in self.imap_subject_keywords.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
