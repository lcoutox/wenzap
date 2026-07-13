"""Meta Cloud API outbound provider.

Thin adapter over the existing ``whatsapp_outbound_service``. It calls the
delegate through the module attribute (not a bound ``from ... import``) so tests
that patch ``app.services.whatsapp_outbound_service.deliver_human_message`` keep
intercepting the call.
"""

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services import whatsapp_outbound_service

PROVIDER_KEY = "meta_cloud_api"


class MetaOutboundProvider:
    """Delivers outbound messages via the WhatsApp Cloud API (Meta)."""

    provider_key = PROVIDER_KEY

    def deliver(
        self,
        db: Session,
        message: ConversationMessage,
        conversation: Conversation,
    ) -> None:
        whatsapp_outbound_service.deliver_human_message(db, message, conversation)
