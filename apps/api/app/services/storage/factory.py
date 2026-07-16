from app.config import settings
from app.services.storage.base import StorageError, StorageProvider


def get_storage_provider() -> StorageProvider:
    """
    Return a StorageProvider instance based on the current settings.

    Supported providers:
    - "local"  → LocalStorageProvider (dev / test / MVP)
    - "r2"     → S3StorageProvider configured for Cloudflare R2
    - "s3"     → S3StorageProvider configured for AWS S3
    """
    from app.services.storage.local import LocalStorageProvider

    provider = (settings.storage_provider or "").strip().lower()

    if provider == "local":
        return LocalStorageProvider(root_path=settings.storage_local_root)

    if provider in ("r2", "s3"):
        from app.services.storage.s3 import S3StorageProvider

        if provider == "r2":
            # R2-specific vars take precedence over generic storage_* vars.
            account_id = settings.r2_account_id
            endpoint_url = (
                settings.r2_endpoint_url
                or (f"https://{account_id}.r2.cloudflarestorage.com" if account_id else "")
                or settings.storage_endpoint_url
            )
            return S3StorageProvider(
                bucket=settings.r2_bucket_name or settings.storage_bucket,
                endpoint_url=endpoint_url,
                access_key_id=settings.r2_access_key_id or settings.storage_access_key_id,
                secret_access_key=(
                    settings.r2_secret_access_key or settings.storage_secret_access_key
                ),
                region="auto",
                public_base_url=settings.r2_public_base_url,
            )

        # Generic S3
        return S3StorageProvider(
            bucket=settings.storage_bucket,
            endpoint_url=settings.storage_endpoint_url,
            access_key_id=settings.storage_access_key_id,
            secret_access_key=settings.storage_secret_access_key,
            region=settings.storage_region or "us-east-1",
        )

    raise StorageError(
        f"Provedor de armazenamento desconhecido: {provider!r}. "
        "Valores suportados: 'local', 'r2', 's3'."
    )
