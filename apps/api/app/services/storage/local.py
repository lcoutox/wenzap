import os

from app.services.storage.base import StorageError, StorageProvider


class LocalStorageProvider(StorageProvider):
    """
    Filesystem-backed storage provider for dev/test/MVP environments.

    All files are stored under *root_path*. Every key is resolved to an
    absolute path and checked to remain inside the root — path traversal
    attempts raise StorageError before any I/O is performed.
    """

    def __init__(self, root_path: str) -> None:
        if not root_path:
            raise StorageError("LocalStorageProvider requer um root_path não vazio.")
        self._root = os.path.abspath(root_path)

    # ── Public interface ──────────────────────────────────────────────────────

    def put_file(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._safe_resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def get_file(self, key: str) -> bytes:
        path = self._safe_resolve(key)
        if not os.path.isfile(path):
            raise StorageError(f"Arquivo não encontrado: {key!r}")
        with open(path, "rb") as fh:
            return fh.read()

    def delete_file(self, key: str) -> None:
        path = self._safe_resolve(key)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # idempotent: deleting a non-existent file is a no-op

    def exists(self, key: str) -> bool:
        path = self._safe_resolve(key)
        return os.path.isfile(path)

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        # Local storage has no network-accessible URLs; return the absolute path
        # so dev tooling can still display it.
        return f"file://{self._safe_resolve(key)}"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _safe_resolve(self, key: str) -> str:
        """
        Resolve *key* to an absolute path within the storage root.

        Raises StorageError for:
        - empty or blank keys
        - absolute paths (e.g. "/etc/passwd")
        - keys that escape the root after normalization (e.g. "../../evil")
        """
        if not key or not key.strip():
            raise StorageError("A chave de armazenamento não pode estar vazia.")

        # Reject keys that look like absolute paths before joining.
        if os.path.isabs(key):
            raise StorageError(
                f"A chave de armazenamento deve ser um caminho relativo, recebido: {key!r}"
            )

        resolved = os.path.abspath(os.path.join(self._root, key))

        # The resolved path must start with the root (with trailing sep to avoid
        # partial-directory false positives like /storage-root2 matching /storage-root).
        root_prefix = self._root + os.sep
        if resolved != self._root and not resolved.startswith(root_prefix):
            raise StorageError(
                f"A chave de armazenamento {key!r} resolve para fora da raiz de armazenamento."
            )

        return resolved
