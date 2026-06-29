"""
S3-compatible storage provider — used for Cloudflare R2 (and standard AWS S3).

Instantiated by the factory when STORAGE_PROVIDER=r2 (or =s3).
Requires boto3 to be installed.
"""

from __future__ import annotations

from app.services.storage.base import StorageError, StorageProvider


class S3StorageProvider(StorageProvider):
    """
    Storage provider backed by any S3-compatible object store (AWS S3, Cloudflare R2, etc.).

    All files are stored in *bucket* under *key_prefix* (optional).
    Presigned URLs are generated via the boto3 client.
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
        public_base_url: str = "",
    ) -> None:
        if not bucket:
            raise StorageError("S3StorageProvider: bucket name is required.")
        if not endpoint_url:
            raise StorageError("S3StorageProvider: endpoint_url is required.")
        if not access_key_id or not secret_access_key:
            raise StorageError(
                "S3StorageProvider: access_key_id and secret_access_key are required."
            )

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise StorageError("boto3 is not installed. Run: uv add boto3") from exc

        self._bucket = bucket
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else ""
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    # ── StorageProvider interface ──────────────────────────────────────────────

    def put_file(self, key: str, data: bytes, content_type: str | None = None) -> None:
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        try:
            self._client.put_object(**kwargs)
        except Exception as exc:
            raise StorageError(f"S3 put_file failed for key {key!r}: {exc}") from exc

    def get_file(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except self._client.exceptions.NoSuchKey:
            raise StorageError(f"File not found: {key!r}")
        except Exception as exc:
            raise StorageError(f"S3 get_file failed for key {key!r}: {exc}") from exc

    def delete_file(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"S3 delete_file failed for key {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        if self._public_base_url:
            return f"{self._public_base_url}/{key}"
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            raise StorageError(
                f"S3 generate_presigned_url failed for key {key!r}: {exc}"
            ) from exc
