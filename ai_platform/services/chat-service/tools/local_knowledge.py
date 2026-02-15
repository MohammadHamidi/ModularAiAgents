"""
Local Knowledge Tool - Fast in-memory lookup for 30 verses, angareh mapping, and konesh session types.
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class LocalKnowledgeTool:
    """Tool for fast lookup of verses, angareh, and konesh session types."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config" / "local"
        self.config_dir = Path(config_dir)
        self._verses: List[Dict[str, Any]] = []
        self._verses_by_id: Dict[int, Dict[str, Any]] = {}
        self._verses_by_angareh: Dict[str, List[Dict[str, Any]]] = {}
        self._konesh_session_types: Dict[str, str] = {}
        self._special_actions: List[Dict[str, Any]] = []
        self._load_data()

    def _load_data(self) -> None:
        verses_path = self.config_dir / "verses_30.yaml"
        if verses_path.exists():
            try:
                with open(verses_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._verses = data.get("verses", [])
                for v in self._verses:
                    vid = v.get("id")
                    if vid is not None:
                        self._verses_by_id[int(vid)] = v
                    ang = (v.get("angareh") or "").strip()
                    if ang:
                        self._verses_by_angareh.setdefault(ang, []).append(v)
                logger.info(f"Loaded {len(self._verses)} verses from {verses_path}")
            except Exception as e:
                logger.error(f"Failed to load verses: {e}")

        mapping_path = self.config_dir / "konesh_type_mapping.yaml"
        if mapping_path.exists():
            try:
                with open(mapping_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._konesh_session_types = data.get("konesh_session_types", {})
                logger.info(f"Loaded {len(self._konesh_session_types)} konesh session types")
            except Exception as e:
                logger.error(f"Failed to load konesh mapping: {e}")

        actions_path = self.config_dir / "special_actions.yaml"
        if actions_path.exists():
            try:
                with open(actions_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._special_actions = data.get("special_actions", [])
            except Exception as e:
                logger.warning(f"Failed to load special actions: {e}")

    @property
    def name(self) -> str:
        return "query_local_knowledge"

    @property
    def description(self) -> str:
        return """
        Query local knowledge for 30 verses, ayah-to-angareh mapping, and konesh session types.
        Use for: verse_id, konesh name, angareh lookup. Returns verse text, translation, angareh, contextual examples.
        """

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (verse number, konesh name, angareh keyword)"},
                "verse_id": {"type": "integer", "description": "Verse ID (1-30) for direct lookup"},
                "konesh_name": {"type": "string", "description": "Konesh name to get session type (مبسوط/فشرده)"},
                "angareh": {"type": "string", "description": "Angareh to list verses (معنویت و دعا, صبر و استقامت, etc.)"},
            },
            "required": [],
        }

    @property
    def enabled(self) -> bool:
        return True

    def get_verse_by_id(self, verse_id: int) -> Optional[Dict[str, Any]]:
        return self._verses_by_id.get(verse_id)

    def get_angareh_for_verse(self, verse_id: int) -> Optional[str]:
        v = self._verses_by_id.get(verse_id)
        return (v.get("angareh") or "").strip() or None if v else None

    def get_verses_by_angareh(self, angareh: str) -> List[Dict[str, Any]]:
        return self._verses_by_angareh.get(angareh, [])

    def get_konesh_session_type(self, konesh_name: str) -> str:
        name = (konesh_name or "").strip()
        if not name:
            return "مبسوط"
        for key, val in self._konesh_session_types.items():
            if key in name or name in key:
                return val
        return "مبسوط"

    def _extract_verse_id(self, text: str) -> Optional[int]:
        if not text:
            return None
        m = re.search(r"(?:آیه|verse)?\s*(\d{1,2})\b", text, re.I)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 30:
                return v
        m = re.search(r"\b(\d{1,2})\b", text)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 30:
                return v
        return None

    def _extract_angareh(self, text: str) -> Optional[str]:
        angarehs = ["معنویت و دعا", "صبر و استقامت", "نصرت و پیروزی", "وحدت و انسجام"]
        t = (text or "").lower()
        for a in angarehs:
            if a in text:
                return a
        return None

    async def execute(
        self,
        query: Optional[str] = None,
        verse_id: Optional[int] = None,
        konesh_name: Optional[str] = None,
        angareh: Optional[str] = None,
    ) -> str:
        result: Dict[str, Any] = {"verses": [], "angareh": None, "konesh_session_type": None}

        vid = verse_id or (self._extract_verse_id(query or "") if query else None)
        if vid:
            v = self.get_verse_by_id(vid)
            if v:
                result["verses"].append({
                    "id": v.get("id"),
                    "surah_name": v.get("surah_name"),
                    "ayah_number": v.get("ayah_number"),
                    "verse_text_ar": v.get("verse_text_ar"),
                    "translation_fa": v.get("translation_fa"),
                    "attractive_title": v.get("attractive_title"),
                    "angareh": v.get("angareh"),
                    "contextual_100_word": (v.get("contextual_100_word") or "")[:500],
                })
                result["angareh"] = v.get("angareh")

        a = angareh or (self._extract_angareh(query or "") if query else None)
        if a and not result["verses"]:
            verses = self.get_verses_by_angareh(a)
            result["verses"] = [
                {
                    "id": x.get("id"),
                    "surah_name": x.get("surah_name"),
                    "ayah_number": x.get("ayah_number"),
                    "attractive_title": x.get("attractive_title"),
                    "angareh": x.get("angareh"),
                }
                for x in verses[:10]
            ]
            result["angareh"] = a

        kname = konesh_name or (query.strip() if query else None)
        if kname:
            result["konesh_session_type"] = self.get_konesh_session_type(kname)

        return json.dumps(result, ensure_ascii=False, indent=2)
