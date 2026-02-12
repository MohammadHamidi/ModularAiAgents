"""
Logging Service - Persists logs to PostgreSQL for log viewer.
Logs API requests, traces, and conversation events.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class LogService:
    """Persists service logs to PostgreSQL."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def append_log(
        self,
        log_type: str,
        session_id: Optional[UUID] = None,
        agent_key: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        request_body: Optional[Dict[str, Any]] = None,
        response_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """
        Append a log entry to service_logs table.
        Truncates/sanitizes large fields.
        """
        if request_body is not None:
            body_str = json.dumps(request_body, ensure_ascii=False)[:2000]
        else:
            body_str = None

        stmt = text("""
            INSERT INTO service_logs (
                log_type, session_id, agent_key, method, path,
                status_code, request_body, response_summary, metadata, duration_ms
            ) VALUES (
                :log_type, :session_id, :agent_key, :method, :path,
                :status_code, CAST(:request_body AS jsonb), :response_summary,
                CAST(:metadata AS jsonb), :duration_ms
            )
        """)
        params = {
            "log_type": log_type,
            "session_id": str(session_id) if session_id else None,
            "agent_key": agent_key,
            "method": method,
            "path": path,
            "status_code": status_code,
            "request_body": body_str or "null",
            "response_summary": (response_summary or "")[:2000] if response_summary else None,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "duration_ms": duration_ms,
        }
        try:
            async with self.engine.begin() as conn:
                await conn.execute(stmt, params)
        except Exception as e:
            logger.warning(f"Failed to persist log: {e}")

    async def get_logs(
        self,
        page: int = 1,
        limit: int = 50,
        session_id: Optional[str] = None,
        agent_key: Optional[str] = None,
        log_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        sort: str = "desc",
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query logs with filters and pagination.
        Returns {items: [...], total: N, page: N, limit: N}.
        """
        conditions = []
        params = {"limit": limit, "offset": (page - 1) * limit}

        if session_id:
            conditions.append("session_id::text = :session_id")
            params["session_id"] = session_id
        if agent_key:
            conditions.append("agent_key = :agent_key")
            params["agent_key"] = agent_key
        if log_type:
            conditions.append("log_type = :log_type")
            params["log_type"] = log_type
        if from_date:
            conditions.append("created_at >= :from_date::timestamptz")
            params["from_date"] = from_date
        if to_date:
            conditions.append("created_at <= :to_date::timestamptz")
            params["to_date"] = to_date
        if search:
            conditions.append("(request_body::text ILIKE :search OR response_summary ILIKE :search OR metadata::text ILIKE :search)")
            params["search"] = f"%{search}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order = "DESC" if sort.lower() == "desc" else "ASC"

        count_sql = text(f"SELECT COUNT(*) FROM service_logs WHERE {where_clause}")
        select_sql = text(f"""
            SELECT id, created_at, log_type, session_id, agent_key, method, path,
                   status_code, request_body, response_summary, metadata, duration_ms
            FROM service_logs
            WHERE {where_clause}
            ORDER BY created_at {order}
            LIMIT :limit OFFSET :offset
        """)

        try:
            async def _query():
                async with self.engine.begin() as conn:
                    total_row = (await conn.execute(count_sql, params)).fetchone()
                    total = total_row[0] if total_row else 0
                    rows = (await conn.execute(select_sql, params)).fetchall()
                    return total, rows
            total, rows = await asyncio.wait_for(_query(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            # If query times out or fails, return empty result
            logger.warning(f"Log query failed or timed out: {e}")
            return {"items": [], "total": 0, "page": page, "limit": limit}

        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "created_at": r[1].isoformat() if r[1] else None,
                "log_type": r[2],
                "session_id": str(r[3]) if r[3] else None,
                "agent_key": r[4],
                "method": r[5],
                "path": r[6],
                "status_code": r[7],
                "request_body": r[8],
                "response_summary": r[9],
                "metadata": r[10],
                "duration_ms": r[11],
            })

        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_stats(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregate stats: count by type, by agent."""
        conditions = []
        params = {}
        if from_date:
            conditions.append("created_at >= :from_date::timestamptz")
            params["from_date"] = from_date
        if to_date:
            conditions.append("created_at <= :to_date::timestamptz")
            params["to_date"] = to_date
        where = " AND ".join(conditions) if conditions else "1=1"

        try:
            async def _query():
                async with self.engine.begin() as conn:
                    total = (await conn.execute(
                        text(f"SELECT COUNT(*) FROM service_logs WHERE {where}"),
                        params,
                    )).fetchone()[0]
                    by_type = dict((await conn.execute(
                        text(f"SELECT log_type, COUNT(*) FROM service_logs WHERE {where} GROUP BY log_type"),
                        params,
                    )).fetchall())
                    by_agent = dict((await conn.execute(
                        text(f"SELECT agent_key, COUNT(*) FROM service_logs WHERE {where} AND agent_key IS NOT NULL GROUP BY agent_key"),
                        params,
                    )).fetchall())
                    return total, by_type, by_agent
            total, by_type, by_agent = await asyncio.wait_for(_query(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Log stats query failed or timed out: {e}")
            return {"total": 0, "by_type": {}, "by_agent": {}}

        return {
            "total": total,
            "by_type": by_type,
            "by_agent": by_agent,
        }
