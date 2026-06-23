from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    database_test_url: str = ""

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str = ""
    # Clerk authorized party (azp claim). Set to the frontend origin registered in Clerk.
    # If set, every JWT must carry a matching azp claim.
    clerk_expected_azp: str = ""

    anthropic_api_key: str = ""

    # ── Embedding settings ────────────────────────────────────────────────────
    # Defaults to "mock" so dev/test environments never hit external APIs.
    # Production must set EMBEDDING_PROVIDER=openai (or another supported value).
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    openai_api_key: str = ""

    # ── RAG settings ──────────────────────────────────────────────────────────
    # rag_top_k: number of chunks retrieved per query.
    # rag_max_context_chars: hard cap on total characters injected into the prompt
    #   (chunks are dropped by rank, never split mid-text).
    rag_top_k: int = 5
    rag_max_context_chars: int = 8000

    # ── Storage settings ──────────────────────────────────────────────────────
    # storage_provider: "local" for dev/test/MVP; "s3" for production (not yet implemented).
    storage_provider: str = "local"
    storage_local_root: str = "./storage"
    storage_bucket: str = ""
    storage_region: str = ""
    storage_endpoint_url: str = ""
    storage_access_key_id: str = ""
    storage_secret_access_key: str = ""

    # ── Upload settings ───────────────────────────────────────────────────────
    # Global fallback when the workspace plan has no max_file_size_bytes set.
    max_file_size_bytes: int = 10_485_760  # 10 MB

    # Comma-separated list of allowed CORS origins.
    # Example: "http://localhost:3000,https://app.nexbrain.com"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
