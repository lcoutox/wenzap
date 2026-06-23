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

    # Comma-separated list of allowed CORS origins.
    # Example: "http://localhost:3000,https://app.nexbrain.com"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
