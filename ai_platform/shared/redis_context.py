# shared/redis_context.py
import json
import redis.asyncio as redis
from typing import Optional

class RedisContextManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
    
    async def set_context(self, session_id: str, key: str, value: dict, ttl: int = 3600):
        """Set context with TTL"""
        full_key = f"context:{session_id}:{key}"
        await self.redis.setex(full_key, ttl, json.dumps(value))
    
    async def get_context(self, session_id: str, key: str = None) -> dict:
        """Get context"""
        if key:
            full_key = f"context:{session_id}:{key}"
            val = await self.redis.get(full_key)
            return json.loads(val) if val else None
        else:
            # Get all keys for session
            pattern = f"context:{session_id}:*"
            keys = await self.redis.keys(pattern)
            if not keys:
                return {}
            values = await self.redis.mget(keys)
            return {
                k.split(":")[-1]: json.loads(v) 
                for k, v in zip(keys, values) if v
            }
    
    async def merge_context(self, session_id: str, context: dict, ttl: int = 3600):
        """Merge context"""
        pipeline = self.redis.pipeline()
        for key, value in context.items():
            full_key = f"context:{session_id}:{key}"
            pipeline.setex(full_key, ttl, json.dumps(value))
        await pipeline.execute()