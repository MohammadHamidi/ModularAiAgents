"""
Safiran action tool.
Fetches action list from Safiran API for action recommendation flows.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

from tools.registry import Tool
from integrations.safiranayeha_client import get_safiranayeha_client

logger = logging.getLogger(__name__)


@dataclass
class SafiranActionTool(Tool):
    """Query Safiran actions with filters and return context payload."""

    name: str = "query_safiran_actions"
    description: str = (
        "Query Safiran action list with filters (query, platform, level, audience, campaign, hashtag)."
    )
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "is_special": {"type": "boolean"},
            "platforms": {"type": "array", "items": {"type": "integer", "format": "int32"}},
            "levels": {"type": "array", "items": {"type": "integer", "format": "int32"}},
            "audiences": {"type": "array", "items": {"type": "integer", "format": "int64"}},
            "activists": {"type": "array", "items": {"type": "integer", "format": "int64"}},
            "campaigns": {"type": "array", "items": {"type": "integer", "format": "int64"}},
            "hashtags": {"type": "array", "items": {"type": "integer", "format": "int64"}},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 10},
        },
        "required": [],
    })

    async def execute(self, **kwargs) -> str:
        client = get_safiranayeha_client()
        page = int(kwargs.get("page") or 1)
        page_size = int(kwargs.get("page_size") or 10)
        filters = {
            "Title": kwargs.get("query"),
            "IsSpecial": kwargs.get("is_special"),
            "Platforms": kwargs.get("platforms"),
            "Levels": kwargs.get("levels"),
            "Audiences": kwargs.get("audiences"),
            "Activists": kwargs.get("activists"),
            "Campaigns": kwargs.get("campaigns"),
            "Hashtags": kwargs.get("hashtags"),
            "PageNumber": page,
            "PageSize": page_size,
        }
        try:
            payload = await client.get_action_list(**filters)
            if not payload:
                return "[]"
            return json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"SafiranActionTool failed: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)
