from app.config import settings
from app.services.storage.base import StorageError, StorageProvider


def get_storage_provider() -> StorageProvider:
    """
    Return a StorageProvider instance based on the current settings.

    Supported providers:
    - "local"  → LocalStorageProvider (dev / test / MVP)
    - "s3"     → not yet implemented; raises StorageError
    - anything else → raises StorageError
    """
    from app.services.storage.local import LocalStorageProvider

    provider = (settings.storage_provider or "").strip().lower()

    if provider == "local":
        return LocalStorageProvider(root_path=settings.storage_local_root)

    if provider == "s3":
        raise StorageError(
            "S3 storage provider is not implemented yet. "
            "Use STORAGE_PROVIDER=local for dev/test environments."
        )

    raise StorageError(
        f"Unknown storage provider: {provider!r}. "
        "Supported values: 'local'."
    )
