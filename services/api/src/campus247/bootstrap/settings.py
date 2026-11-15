from __future__ import annotations

from pathlib import Path
from typing import Literal
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from campus247.application.retrieval.profile import PROFILE_VERSION, RetrievalProfile, load_retrieval_profile
from campus247.application.retrieval.runtime_config import RuntimeDeadlines

ROOT_DIR = Path(__file__).resolve().parents[5]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Validated environment configuration for Campus 24/7 API service."""

    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = Field(default="Campus 24/7 API", description="Tên ứng dụng")
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = Field(
        default="development",
        description="Môi trường triển khai",
    )
    HOST: str = Field(default="127.0.0.1", description="Host lắng nghe")
    PORT: int = Field(default=8000, ge=1, le=65535, description="Port dịch vụ")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://campus247:campus247_local_dev@localhost:5433/campus247_local",
        description="Chuỗi kết nối PostgreSQL pgvector",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6380/0",
        description="Chuỗi kết nối Redis cache & queue",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Mức ghi log hệ thống")
    rag_engine: Literal["v1", "v2"] = Field(default="v1",
        validation_alias=AliasChoices("CAMPUS247_RAG_ENGINE", "rag_engine"))
    # Where the abuse limiter counts requests. "memory" counts per process (tests, one process); "postgres" is shared
    # by every API process, so N processes still allow exactly the configured rate. Needs the knowledge platform pool.
    rate_limit_store: Literal["memory", "postgres"] = Field(default="memory",
        validation_alias=AliasChoices("CAMPUS247_RATE_LIMIT_STORE", "rate_limit_store"))
    # Admission control for chat turns, per API process. 0 disables the bound (tests, tools).
    chat_max_in_flight: int = Field(default=0, ge=0,
        validation_alias=AliasChoices("CAMPUS247_CHAT_MAX_IN_FLIGHT", "chat_max_in_flight"))
    chat_admission_wait_s: float = Field(default=4.0, ge=0, le=30,
        validation_alias=AliasChoices("CAMPUS247_CHAT_ADMISSION_WAIT_S", "chat_admission_wait_s"))
    # Issue the safety classification and the intent routing together (only used with the v2 engine). The final
    # measured configuration of the v2 evaluation ran this way; sequential calls only added waiting time.
    parallel_classify: bool = Field(default=True,
        validation_alias=AliasChoices("CAMPUS247_PARALLEL_CLASSIFY", "parallel_classify"))
    rag_v2_index_dir: Path = Field(default=Path("data/rag_v2_index"),
        validation_alias=AliasChoices("CAMPUS247_RAG_V2_INDEX", "rag_v2_index_dir"))
    RETRIEVAL_PROFILE_VERSION: str = Field(default=PROFILE_VERSION, strict=True)
    RETRIEVAL_RUNTIME_DEADLINES: RuntimeDeadlines | None = None
    DEMO_MODE: bool = Field(
        default=True,
        description="Cờ chế độ thử nghiệm HUCE Demo (dữ liệu tổng hợp)",
    )
    CONVERSATION_STORAGE_MODE: Literal["ephemeral", "sqlite", "injected"] = "ephemeral"
    CONVERSATION_SQLITE_PATH: Path | None = None
    CONSENT_STORAGE_MODE: Literal["ephemeral", "sqlite", "injected"] = "ephemeral"
    CONSENT_SQLITE_PATH: Path | None = None
    ACTOR_STATE_STORAGE_MODE: Literal["ephemeral", "sqlite", "injected"] = "ephemeral"
    ACTOR_STATE_SQLITE_PATH: Path | None = None
    AGENT_RUN_STORAGE_MODE: Literal["disabled", "sqlite", "injected"] = "disabled"
    AGENT_RUN_SQLITE_PATH: Path | None = None
    IDENTITY_SECRET_KEY: str = Field(
        default="campus247-demo-secret-key-huce",
        description="Khóa ký danh tính demo",
    )
    CONFIRMATION_SIGNING_KEY: str = Field(
        default="campus247-secret-signing-key",
        description="Khóa ký token xác nhận hành động",
    )
    # LLM Multi-Provider Configurations
    GEMINI_API_KEY: str | None = Field(default=None, description="Khóa API Gemini (Free)")
    OPENAI_API_KEY: str | None = Field(default=None, description="Khóa API OpenAI endpoint")
    OPENAI_BASE_URL: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Base URL endpoint cho OpenAI-compatible API",
    )
    LAB_MODEL: str = Field(default="gemini-3.6-flash", description="Mô hình LLM chính")
    LAB_MINI_MODEL: str = Field(default="gemini-3.6-flash", description="Mô hình LLM nhẹ/mini")
    DEEPSEEK_API_KEY: str | None = Field(default=None, description="Khóa API DeepSeek (Paid)")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com", description="Base URL DeepSeek API")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat", description="Mô hình DeepSeek")
    LLM_PRIMARY_PROVIDER: str = Field(default="deepseek", description="Nhà cung cấp LLM chính (deepseek, gemini, auto)")

    _INSECURE_DEFAULTS = frozenset({
        "campus247-demo-secret-key-huce",
        "campus247-secret-signing-key",
    })

    @property
    def retrieval_profile(self) -> RetrievalProfile:
        profile = load_retrieval_profile(self.RETRIEVAL_PROFILE_VERSION)
        if self.RETRIEVAL_RUNTIME_DEADLINES is not None:
            if self.ENVIRONMENT not in {"development", "testing"} or not self.DEMO_MODE:
                raise ValueError("runtime deadline overlay requires local synthetic environment")
            return self.RETRIEVAL_RUNTIME_DEADLINES.apply(profile)
        return profile

    @model_validator(mode="after")
    def _validate_retrieval_profile(self) -> "Settings":
        _ = self.retrieval_profile
        return self

    @model_validator(mode="after")
    def _reject_default_keys_in_production(self) -> "Settings":
        """Block startup with default insecure keys in production/staging."""
        if self.ENVIRONMENT in ("production", "staging"):
            for field_name in ("IDENTITY_SECRET_KEY", "CONFIRMATION_SIGNING_KEY"):
                value = getattr(self, field_name, "")
                if value in self._INSECURE_DEFAULTS:
                    raise ValueError(
                        f"{field_name} uses an insecure default value in {self.ENVIRONMENT}. "
                        f"Set a secure secret via environment variable."
                    )
        return self


def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
