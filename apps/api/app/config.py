from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    database_test_url: str = ""

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

    # ── Conversation settings ─────────────────────────────────────────────────
    # Maximum number of recent messages included in the conversation history
    # block sent to the LLM when the agent replies automatically in the Inbox.
    conversation_history_limit: int = 20

    # ── Storage settings ──────────────────────────────────────────────────────
    # storage_provider: "local" for dev/test/MVP; "r2" for production.
    storage_provider: str = "local"
    storage_local_root: str = "./storage"
    storage_bucket: str = ""
    storage_region: str = "auto"
    storage_endpoint_url: str = ""
    storage_access_key_id: str = ""
    storage_secret_access_key: str = ""

    # ── Cloudflare R2 settings ────────────────────────────────────────────────
    # Set STORAGE_PROVIDER=r2 to activate. These override the generic storage_*
    # equivalents when the R2 provider is active.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_base_url: str = ""
    r2_endpoint_url: str = ""

    # ── Upload settings ───────────────────────────────────────────────────────
    # Global fallback when the workspace plan has no max_file_size_bytes set.
    max_file_size_bytes: int = 10_485_760  # 10 MB

    # Per-type limits for catalog media uploads.
    catalog_media_max_image_bytes: int = 10_485_760    # 10 MB
    catalog_media_max_document_bytes: int = 20_971_520  # 20 MB

    # ── First-party auth ──────────────────────────────────────────────────────
    auth_session_ttl_days: int = 30
    auth_cookie_name: str = "wenzap_session"
    # Set to True in production (requires HTTPS). False in dev so localhost works.
    auth_cookie_secure: bool = False
    # Set to ".wenzap.com.br" (with leading dot) when frontend and API are on
    # different subdomains of the same root domain. Empty string means no Domain
    # attribute (cookie scoped to the exact host that set it).
    auth_cookie_domain: str = ""

    # Comma-separated list of allowed CORS origins.
    # Example: "http://localhost:3000,https://app.nexbrain.com"
    cors_origins: str = "http://localhost:3000"

    # ── WhatsApp / Meta ───────────────────────────────────────────────────────
    whatsapp_webhook_verify_token: str = ""

    # Meta App credentials — used by Embedded Signup exchange endpoint.
    # META_APP_SECRET must never be exposed to the frontend.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_api_version: str = "v25.0"

    # ── Evolution API (bridge WhatsApp provider — unofficial) ─────────────────
    # Base URL of the self-hosted Evolution server (shared across all workspaces).
    evolution_api_base_url: str = ""
    # Master/admin key (AUTHENTICATION_API_KEY on the Evolution server) — used
    # ONLY by this backend to provision/manage instances (create/delete).
    # NEVER exposed to the frontend. Distinct from each instance's own token,
    # which is generated per-instance at creation and stored per-channel via
    # ChannelCredential (resolved through config.api_key_ref).
    evolution_master_api_key: str = ""
    # Public base URL of THIS API, used to build the webhook URL registered on
    # each newly created Evolution instance, e.g. "https://api.wenzap.com.br".
    api_public_base_url: str = ""

    # ── Meta Review (App Review — single-tenant, provisório) ──────────────────
    # Credenciais da WABA oficial da Nexalt para gravação dos vídeos de App Review.
    # META_ACCESS_TOKEN nunca deve ser exposto no frontend nem logado.
    meta_review_waba_id: str = ""
    meta_review_phone_number_id: str = ""
    meta_review_access_token: str = ""
    meta_review_webhook_verify_token: str = ""
    # Validação de assinatura X-Hub-Signature-256 no webhook POST.
    # Em produção deve ser True. Pode ser False apenas em testes locais.
    meta_review_webhook_signature_required: bool = True
    # E-mails autorizados a acessar /admin/meta-review (CSV).
    # Restrição extra além de role=owner, pois owners de outros workspaces
    # não devem acessar configurações internas da Nexalt.
    meta_review_admin_emails: str = ""

    @property
    def meta_review_admin_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.meta_review_admin_emails.split(",") if e.strip()]

    # ── Credential encryption ─────────────────────────────────────────────────
    # Required for encrypted channel credentials (db: token refs).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # noqa: E501
    # Leave empty in dev/test when no db: credentials are used.
    app_encryption_key: str = ""

    # ── Observability ─────────────────────────────────────────────────────────
    sentry_dsn: str = ""

    # ── Email / Resend ────────────────────────────────────────────────────────
    resend_api_key: str = ""
    email_from: str = ""
    email_from_name: str = "Wenzap"
    # Base URL used to build verification links, e.g. https://app.wenzap.com.br
    app_url: str = "http://localhost:3000"
    # Set to True to log emails instead of sending via Resend (dev/test).
    email_sandbox_mode: bool = False

    # ── Stripe billing ────────────────────────────────────────────────────────
    # Secret API key from https://dashboard.stripe.com/apikeys.
    # Empty in dev/test — StripeService raises a clear error if used unconfigured.
    stripe_api_key: str = ""
    # Signing secret for the /webhooks/stripe endpoint (dashboard → Webhooks).
    stripe_webhook_secret: str = ""
    # Stripe Price IDs, one per paid plan code. Configured per-environment so
    # they never need a code change to add/rotate a price.
    stripe_price_id_growth: str = ""
    stripe_price_id_scale: str = ""
    stripe_price_id_enterprise: str = ""

    @property
    def stripe_price_by_plan_code(self) -> dict[str, str]:
        return {
            "growth": self.stripe_price_id_growth,
            "scale": self.stripe_price_id_scale,
            "enterprise": self.stripe_price_id_enterprise,
        }

    # ── AI prompt debug ───────────────────────────────────────────────────────
    # When True, logs a structured summary of each assembled system prompt
    # (sections included, lengths, flags). In dev only, also logs the first
    # 2000 chars of the assembled prompt. Never logs sensitive customer data.
    ai_prompt_debug: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
