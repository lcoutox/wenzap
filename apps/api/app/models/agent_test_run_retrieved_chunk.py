import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentTestRunRetrievedChunk(Base):
    """
    Records each chunk that was a candidate during a RAG retrieval for a test run.

    - knowledge_chunk_id is SET NULL on chunk deletion so audit rows are kept.
    - knowledge_base_id and source_id are stored as plain UUIDs (no FK) so they
      survive KB/source archival without cascade complications.
    - injected_into_prompt=False means the chunk was retrieved but filtered out
      (e.g. by prompt injection detection) before being sent to the LLM.
    """

    __tablename__ = "agent_test_run_retrieved_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    agent_test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_test_runs.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable so the row survives chunk deletion (SET NULL).
    knowledge_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True
    )

    # Stored directly (not as FKs) to preserve audit data across archival.
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # False when the chunk was filtered (e.g. by prompt injection detection).
    injected_into_prompt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
