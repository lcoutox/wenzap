"""Messaging provider abstraction — outbound delivery.

Providers implement transport-specific delivery (Meta Cloud API, Evolution API, …)
behind one common interface, so the core (agent reply, inbox) stays
provider-agnostic. Switching a channel between providers is a config change
(``channel.config_json["provider"]``), not a code change.
"""

from typing import Protocol

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage


class OutboundProvider(Protocol):
    """Delivers an outbound ``ConversationMessage`` to its channel.

    Contract: implementations MUST NOT raise. Errors are caught and recorded on
    ``message.metadata_json["delivery"]`` (same contract as the legacy
    ``deliver_human_message``), so an Inbox message is never lost.
    """

    def deliver(
        self,
        db: Session,
        message: ConversationMessage,
        conversation: Conversation,
    ) -> None: ...
