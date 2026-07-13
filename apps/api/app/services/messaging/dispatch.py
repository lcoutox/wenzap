"""Outbound message dispatch.

Routes an outbound message to the provider configured on its channel
(``channel.config_json["provider"]``, default ``meta_cloud_api``). This is the
single entry point the core calls; it never raises.
"""

import logging

from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.messaging.base import OutboundProvider
from app.services.messaging.evolution_provider import EvolutionOutboundProvider
from app.services.messaging.meta_provider import MetaOutboundProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_KEY = "meta_cloud_api"

# Registry of outbound providers by key. Adding a new provider is a registry
# entry here — no changes needed at the call sites.
_PROVIDERS: dict[str, OutboundProvider] = {
    "meta_cloud_api": MetaOutboundProvider(),
    "evolution_api": EvolutionOutboundProvider(),
}


def _resolve_provider_key(db: Session, conversation: Conversation) -> str:
    """Read the provider key from the conversation's channel config.

    Falls back to the default (Meta) when there is no channel or no provider set,
    which preserves behavior for channels/conversations created before providers
    were configurable.
    """
    channel_id = getattr(conversation, "channel_id", None)
    if channel_id:
        channel = db.get(Channel, channel_id)
        if channel is not None:
            provider = (channel.config_json or {}).get("provider")
            if provider:
                return provider
    return DEFAULT_PROVIDER_KEY


def get_outbound_provider(provider_key: str) -> OutboundProvider:
    provider = _PROVIDERS.get(provider_key)
    if provider is None:
        logger.warning(
            "outbound_dispatch unknown provider=%s, falling back to %s",
            provider_key,
            DEFAULT_PROVIDER_KEY,
        )
        return _PROVIDERS[DEFAULT_PROVIDER_KEY]
    return provider


def deliver_outbound_message(
    db: Session,
    message: ConversationMessage,
    conversation: Conversation,
) -> None:
    """Deliver an outbound message via the provider configured on its channel.

    Never raises — providers record the delivery outcome on
    ``message.metadata_json["delivery"]``.
    """
    provider_key = _resolve_provider_key(db, conversation)
    provider = get_outbound_provider(provider_key)
    provider.deliver(db, message, conversation)
