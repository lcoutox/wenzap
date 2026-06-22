"""
Validates Clerk JWT tokens via JWKS.

The token's `sub` claim carries the Clerk user_id — never trusted from request body.

Audience validation: Clerk tokens typically do not set a standard `aud` claim.
Instead, we validate the `azp` (authorized party) claim when CLERK_EXPECTED_AZP
is configured. This prevents tokens issued for other Clerk applications from being
accepted here.
"""

import jwt
from jwt import PyJWKClient

from app.config import settings

# Module-level singleton. PyJWKClient internally caches JWKS with its own TTL.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # cache_keys=True and lifespan control JWKS refresh; defaults are safe.
        _jwks_client = PyJWKClient(settings.clerk_jwks_url, cache_keys=True)
    return _jwks_client


def verify_clerk_token(token: str) -> dict:
    """
    Verifies a Clerk JWT and returns the decoded claims.
    Raises jwt.InvalidTokenError on any verification failure.
    """
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)

    payload: dict = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},  # Clerk does not use standard `aud`
    )

    # Validate azp when configured — prevents tokens from other Clerk apps being accepted.
    expected_azp = settings.clerk_expected_azp
    if expected_azp:
        azp = payload.get("azp", "")
        if azp != expected_azp:
            raise jwt.InvalidTokenError(
                f"Token azp '{azp}' does not match expected '{expected_azp}'"
            )

    return payload
