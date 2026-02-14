import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.dialects.postgresql import JSONB


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
            return {
                "messages": row[0],
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

        async with self.engine.begin() as conn:
            await conn.execute(
                stmt,
                {
                    "sid": session_id,
                    "msgs": trimmed_messages,
                    "agent_type": agent_type,
                    "meta": metadata or {},
                    "now": now,
                },
            )

    async def list_sessions(self, limit: int = 500):
        """
        List all chat sessions (for admin/monitoring).
        Returns list of dicts with session_id, messages, agent_type, metadata, created_at, updated_at.
        """
        async with self.engine.begin() as conn:
            rows = (await conn.execute(
                text("""
                    SELECT session_id, messages, agent_type, metadata, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )).fetchall()
        return [
            {
                "session_id": str(r[0]),
                "messages": r[1],
                "agent_type": r[2],
                "metadata": r[3] or {},
                "created_at": r[4].isoformat() if r[4] else None,
                "updated_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]

    async def dispose(self):
        await self.engine.dispose()