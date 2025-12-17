import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.dialects.postgresql import JSONB
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter


def dump_messages(messages: list[ModelMessage]) -> list[dict]:
    """
    Serialize a list of ModelMessage objects to plain JSON-serializable dicts
    suitable for storing in a JSONB column.
    """
    if not messages:
        return []
    # Use pydantic-ai's adapter to produce standard Python data structures
    return ModelMessagesTypeAdapter.dump_python(messages)


def load_messages(raw_messages) -> list[ModelMessage]:
    """
    Deserialize JSON/JSONB data from the DB into a list[ModelMessage].
    Accepts either a list of dicts or a JSON-serializable structure.
    """
    if not raw_messages:
        return []
    return ModelMessagesTypeAdapter.validate_python(raw_messages)


class SessionManager:
    """Manages session persistence across services"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
    
    async def get_session(self, session_id: uuid.UUID):
        async with self.engine.begin() as conn:
            row = (await conn.execute(
                text("SELECT messages, agent_type, metadata FROM chat_sessions WHERE session_id=:sid"),
                {"sid": session_id}
            )).fetchone()
            if not row:
                return None

            raw_messages = row[0]
            messages = load_messages(raw_messages)

            return {
                "messages": messages,
                "agent_type": row[1],
                "metadata": row[2] or {},
            }
    
    async def upsert_session(
        self, session_id: uuid.UUID, messages, agent_type: str, metadata=None
    ):
        """Insert or update a chat session with JSONB-backed messages/metadata.

        Also trims very long histories based on MAX_SESSION_MESSAGES (from env)
        to keep context sizes manageable.
        """
        max_msgs = int(os.getenv("MAX_SESSION_MESSAGES", "30"))

        now = datetime.now(timezone.utc)

        stmt = text("""
            INSERT INTO chat_sessions (session_id, messages, agent_type, metadata, created_at, updated_at)
            VALUES (:sid, :msgs, :agent_type, :meta, :now, :now)
            ON CONFLICT (session_id)
            DO UPDATE SET
                messages   = EXCLUDED.messages,
                agent_type = EXCLUDED.agent_type,
                metadata   = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
        """).bindparams(
            bindparam("msgs", type_=JSONB),
            bindparam("meta", type_=JSONB),
        )

        # Trim message history if it exceeds configured max
        trimmed_messages = messages or []
        if isinstance(trimmed_messages, list) and len(trimmed_messages) > max_msgs:
            trimmed_messages = trimmed_messages[-max_msgs:]

        # Serialize messages into JSON-serializable format for JSONB storage
        serialized_messages = dump_messages(trimmed_messages)

        async with self.engine.begin() as conn:
            await conn.execute(
                stmt,
                {
                    "sid": session_id,
                    "msgs": serialized_messages,
                    "agent_type": agent_type,
                    "meta": metadata or {},
                    "now": now,
                },
            )

    async def dispose(self):
        await self.engine.dispose()