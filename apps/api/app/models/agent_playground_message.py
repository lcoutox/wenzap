import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# role values: 'user' | 'assistant'
# agent_test_run_id is NULL for user messages and for assistant messages
# produced before reaching the LLM (should not happen by design — assistant
# messages are only saved on a successful LLM response).


class AgentPlaygroundMessage(Base):
    __tablename__ = "agent_playground_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_playground_sessions.id", ondelete="CASCADE"), nullable=False
    )

    # 'user' | 'assistant'
    role: Mapped[str] = mapped_column(nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # NULL for user messages; references the run that produced this response.
    agent_test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_test_runs.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
