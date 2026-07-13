"""Provider-agnostic messaging layer (outbound dispatch + providers)."""

from app.services.messaging.dispatch import (
    deliver_outbound_message,
    get_outbound_provider,
)

__all__ = ["deliver_outbound_message", "get_outbound_provider"]
