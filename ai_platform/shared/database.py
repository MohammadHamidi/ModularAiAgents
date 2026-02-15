import os
import uuid
from typing import List
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

    async def list_users(
        self,
        page: int = 1,
        limit: int = 25,
        search: str = None,
        from_date: str = None,
        to_date: str = None,
        min_sessions: int = None,
        sort: str = "desc",
    ):
        """
        List distinct users (safiran_user_id from metadata) with session count and last activity.
        Uses DB aggregation so all users are included; supports search, date range, min_sessions.
        Returns: (list of user dicts, total count).
        """
        conditions = ["metadata->>'safiran_user_id' IS NOT NULL AND (metadata->>'safiran_user_id') != ''"]
        params = {"limit": max(1, min(100, limit)), "offset": (max(1, page) - 1) * max(1, min(100, limit))}
        if search and search.strip():
            conditions.append("(metadata->>'safiran_user_id') ILIKE :search")
            params["search"] = f"%{search.strip()}%"
        if from_date:
            conditions.append("updated_at >= :from_date::timestamptz")
            params["from_date"] = from_date
        if to_date:
            conditions.append("updated_at <= :to_date::timestamptz")
            params["to_date"] = to_date
        where = " AND ".join(conditions)
        having = ""
        if min_sessions is not None and min_sessions >= 0:
            having = f" HAVING COUNT(*) >= {int(min_sessions)}"
        order = "DESC" if (sort or "desc").lower() == "desc" else "ASC"
        base_sql = f"""
            SELECT metadata->>'safiran_user_id' AS user_id,
                   COUNT(*) AS session_count,
                   MAX(updated_at) AS last_activity,
                   array_agg(session_id::text ORDER BY updated_at DESC) AS session_ids
            FROM chat_sessions
            WHERE {where}
            GROUP BY metadata->>'safiran_user_id'
            {having}
        """
        count_sql = text(f"SELECT COUNT(*) FROM ({base_sql}) AS u")
        select_sql = text(f"""
            {base_sql}
            ORDER BY last_activity {order}
            LIMIT :limit OFFSET :offset
        """)
        count_params = {k: v for k, v in params.items() if k in ("search", "from_date", "to_date")}
        async with self.engine.begin() as conn:
            total_row = (await conn.execute(count_sql, count_params)).fetchone()
            total = total_row[0] if total_row else 0
            rows = (await conn.execute(select_sql, params)).fetchall()
        return [
            {
                "user_id": str(r[0]),
                "session_count": r[1],
                "session_ids": list(r[3]) if r[3] else [],
                "last_activity": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ], total

    async def list_sessions_for_user(self, user_id: str, limit: int = 50) -> List[dict]:
        """
        List all sessions for a user (metadata.safiran_user_id = user_id).
        Returns list of dicts with session_id, title, created_at, updated_at, message_count, agent_type.
        """
        async with self.engine.begin() as conn:
            rows = (await conn.execute(
                text("""
                    SELECT session_id, messages, agent_type, metadata, created_at, updated_at
                    FROM chat_sessions
                    WHERE metadata->>'safiran_user_id' = :user_id
                    ORDER BY updated_at DESC
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": limit},
            )).fetchall()
        result = []
        for r in rows:
            sid, messages, agent_type, meta, created_at, updated_at = r
            meta = meta or {}
            title = meta.get("session_title")
            if not title and messages:
                for m in messages if isinstance(messages, list) else []:
                    if isinstance(m, dict) and m.get("role") == "user":
                        msg = (m.get("content") or "").strip()
                        title = (msg[:50] + "…") if len(msg) > 50 else (msg or "گفتگوی جدید")
                        break
            if not title:
                title = "گفتگوی جدید"
            msg_count = len(messages) if isinstance(messages, list) else 0
            result.append({
                "session_id": str(sid),
                "title": title,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "message_count": msg_count,
                "agent_type": agent_type or "orchestrator",
            })
        return result

    async def dispose(self):
        await self.engine.dispose()