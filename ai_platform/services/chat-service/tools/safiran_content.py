"""
Safiran content tool.
Fetches content list from Safiran API for content-focused agents.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from tools.registry import Tool
from integrations.safiranayeha_client import get_safiranayeha_client

logger = logging.getLogger(__name__)


@dataclass
class SafiranContentTool(Tool):
    """Query Safiran content library and return concise context."""

    name: str = "query_safiran_content"
    description: str = (
        "Query Safiran content library for related content (by action, type, category, verse, and query term)."
    )
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "action_ids": {
                "type": "array",
                "items": {"type": "integer", "format": "int64"},
            },
            "type_ids": {
                "type": "array",
                "items": {"type": "integer", "format": "int32"},
            },
            "category_ids": {
                "type": "array",
                "items": {"type": "integer", "format": "int64"},
            },
            "verse_ids": {
                "type": "array",
                "items": {"type": "integer", "format": "int64"},
            },
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
            "PageNumber": page,
            "PageSize": page_size,
            "Title": kwargs.get("query"),
            "ActionIds": kwargs.get("action_ids"),
            "TypeIds": kwargs.get("type_ids"),
            "CategoryIds": kwargs.get("category_ids"),
            "VerseIds": kwargs.get("verse_ids"),
        }
        try:
            payload = await client.get_content_list(**filters)
            if not payload:
                return "[]"
            return json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"SafiranContentTool failed: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)
