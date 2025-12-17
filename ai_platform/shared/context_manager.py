import os, uuid, json
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.dialects.postgresql import JSONB

class ContextManager:
    """Manages shared context across agents"""
    
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
    
    async def set_context(
        self,
        session_id: uuid.UUID,
        key: str,
        value: dict,
        agent_type: str = None,
        ttl_seconds: int = None,
    ):
        """Set context value with optional TTL.

        If ttl_seconds is not provided, a default SESSION_TTL_SECONDS from env
        will be used to avoid keeping context forever.
        """
        if ttl_seconds is None:
            ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "14400"))  # 4 hours default

        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        stmt = text("""
            INSERT INTO agent_context (session_id, context_key, context_value, agent_type, expires_at, updated_at)
            VALUES (:sid, :key, :val, :agent, :exp, NOW())
            ON CONFLICT (session_id, context_key)
            DO UPDATE SET 
                context_value = EXCLUDED.context_value,
                agent_type    = EXCLUDED.agent_type,
                expires_at    = EXCLUDED.expires_at,
                updated_at    = NOW()
        """).bindparams(
            bindparam("val", type_=JSONB),
        )

        async with self.engine.begin() as conn:
            await conn.execute(
                stmt,
                {
                    "sid": session_id,
                    "key": key,
                    "val": value,
                    "agent": agent_type,
                    "exp": expires_at,
                },
            )
    
    async def get_context(self, session_id: uuid.UUID, key: str = None) -> dict:
        """Get context value(s)"""
        async with self.engine.begin() as conn:
            if key:
                row = (await conn.execute(text("""
                    SELECT context_value FROM agent_context 
                    WHERE session_id=:sid AND context_key=:key 
                    AND (expires_at IS NULL OR expires_at > NOW())
                """), {"sid": session_id, "key": key})).fetchone()
                return row[0] if row else None
            else:
                rows = (await conn.execute(text("""
                    SELECT context_key, context_value FROM agent_context 
                    WHERE session_id=:sid 
                    AND (expires_at IS NULL OR expires_at > NOW())
                """), {"sid": session_id})).fetchall()
                return {row[0]: row[1] for row in rows}
    
    async def merge_context(self, session_id: uuid.UUID, context: dict, agent_type: str = None):
        """Merge multiple context values"""
        for key, value in context.items():
            await self.set_context(session_id, key, value, agent_type)
    
    async def delete_context(self, session_id: uuid.UUID, key: str = None):
        """Delete context"""
        async with self.engine.begin() as conn:
            if key:
                await conn.execute(text("""
                    DELETE FROM agent_context WHERE session_id=:sid AND context_key=:key
                """), {"sid": session_id, "key": key})
            else:
                await conn.execute(text("""
                    DELETE FROM agent_context WHERE session_id=:sid
                """), {"sid": session_id})