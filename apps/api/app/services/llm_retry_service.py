"""LLM Retry Service — handles retries with exponential backoff."""

import asyncio
import logging
from typing import TypeVar

from app.llm.schemas import LLMProviderError, LLMRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retry configuration
MAX_RETRIES = 2
INITIAL_BACKOFF_MS = 500
MAX_BACKOFF_MS = 5000


async def call_llm_with_retry(request: LLMRequest):
    """
    Call LLM with automatic retries on transient errors.

    Retries on:
    - LLMProviderError with transient=True
    - Rate limit errors
    - Timeout errors

    Does NOT retry on:
    - Authentication errors (auth_error=True in exception)
    - Invalid model
    - Other permanent errors
    """
    from app.llm import client as llm_client

    last_error = None
    backoff_ms = INITIAL_BACKOFF_MS

    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug(
                "llm_call attempt=%d/%d model=%s",
                attempt + 1, MAX_RETRIES + 1, request.model_name,
            )
            return llm_client.complete(request)

        except LLMProviderError as exc:
            last_error = exc

            # Don't retry on authentication errors
            if exc.auth_error:
                logger.warning(
                    "llm_auth_error model=%s attempt=%d (no retry)",
                    request.model_name, attempt + 1,
                )
                raise

            # Don't retry on permanent errors
            if not exc.transient:
                logger.warning(
                    "llm_permanent_error model=%s attempt=%d error=%s",
                    request.model_name, attempt + 1, exc.message,
                )
                raise

            # Transient error — retry if attempts remain
            if attempt < MAX_RETRIES:
                logger.warning(
                    "llm_transient_error model=%s attempt=%d (retry in %dms) error=%s",
                    request.model_name, attempt + 1, backoff_ms, exc.message,
                )
                await asyncio.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, MAX_BACKOFF_MS)
            else:
                logger.error(
                    "llm_max_retries_exceeded model=%s attempts=%d error=%s",
                    request.model_name, MAX_RETRIES + 1, exc.message,
                )
                raise

    # Should not reach here
    raise last_error or RuntimeError("LLM call failed without exception")
