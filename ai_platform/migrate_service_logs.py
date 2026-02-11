#!/usr/bin/env python3
"""
One-off migration: Create service_logs table if it doesn't exist.
Run this if the log viewer returns 500 (UndefinedTableError).
Usage: python migrate_service_logs.py
Requires: DATABASE_URL in .env
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

SERVICE_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS service_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    log_type VARCHAR(50) NOT NULL,
    session_id UUID,
    agent_key VARCHAR(100),
    method VARCHAR(10),
    path VARCHAR(500),
    status_code INTEGER,
    request_body JSONB,
    response_summary TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    duration_ms FLOAT
);
CREATE INDEX IF NOT EXISTS idx_service_logs_created_at ON service_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_logs_session_id ON service_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_service_logs_agent_key ON service_logs(agent_key);
CREATE INDEX IF NOT EXISTS idx_service_logs_log_type ON service_logs(log_type);
"""


async def migrate():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        return 1
    try:
        engine = create_async_engine(url, pool_pre_ping=True)
        async with engine.begin() as conn:
            for raw in SERVICE_LOGS_SQL.strip().split(";"):
                stmt = raw.strip()
                if stmt:
                    await conn.execute(text(stmt))
                    print("OK:", stmt[:60] + "..." if len(stmt) > 60 else stmt)
        await engine.dispose()
        print("\nDone. service_logs table is ready.")
        return 0
    except Exception as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    exit(asyncio.run(migrate()))
