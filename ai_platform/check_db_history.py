import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import json

# Fix Unicode encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
db_url = os.getenv('DATABASE_URL')

async def check():
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text('SELECT session_id, jsonb_array_length(messages) as msg_count, messages FROM chat_sessions ORDER BY updated_at DESC LIMIT 1')
        )
        row = result.fetchone()
        if row:
            print(f'Session: {row[0]}')
            print(f'Messages: {row[1]}')
            print('\nFirst 2 messages:')
            msgs = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            for i, msg in enumerate(msgs[:2]):
                content = msg.get("content", "")
                content_preview = content[:80] + "..." if len(content) > 80 else content
                print(f'  {i+1}. {msg.get("role")}: {content_preview}')
        else:
            print("No sessions found")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())

