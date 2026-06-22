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

    # Comma-separated list of allowed CORS origins.
    # Example: "http://localhost:3000,https://app.nexbrain.com"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
