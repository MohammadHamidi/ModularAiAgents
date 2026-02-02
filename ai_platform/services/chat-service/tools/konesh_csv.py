"""
Konesh CSV Tool - Query کنش (Quranic Actions) from the full CSV reference.
Supports filtering by بستر انجام, سطح سختی, کنش‌گر, هشتگ‌ها, and ویژه.
Returns محتواهای مرتبط for optional LightRAG knowledge-base lookup.
"""
import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# CSV columns (semicolon-delimited)
COL_BESTAR = "بستر انجام"
COL_TITLE = "عنوان کنش"
COL_SATHE = "سطح سختی"
COL_KONESHGAR = "کنش‌گر"
COL_MOKHATAB = "مخاطب"
COL_SHARH = "شرح و الگوی اجرا"
COL_HASHTAG = "هشتگ‌ها"
COL_MOTEVALI = "محتواهای مرتبط"
COL_DATAYE_SABT = "دیتای لازم برای ثبت کنش"
COL_VIZHE = "ویژه"

# Normalize ویژه values
VIZHE_YES = ("بله", "yes", "1", "true", "آری")
VIZHE_NO = ("نه", "no", "0", "false", "خیر")

# Colloquial -> canonical for matching (so "خونه" matches rows with "خانه")
QUERY_NORMALIZE = {"خونه": "خانه"}

# Min word length for "any word" match (avoid matching on single chars)
MIN_WORD_LEN = 2


def _default_csv_path() -> Path:
    """Resolve path to کنش_های سفیران آیه_ها.csv (ai_platform root)."""
    # tools/konesh_csv.py -> chat-service -> services -> ai_platform
    base = Path(__file__).resolve().parent.parent.parent.parent
    return base / "کنش_های سفیران آیه_ها.csv"


class KoneshCSVTool:
    """Tool for querying the full کنش CSV with filters and محتواهای مرتبط for KB."""

    def __init__(self, csv_path: Optional[str] = None):
        if csv_path is None:
            csv_path = os.getenv("KONESH_CSV_PATH", str(_default_csv_path()))
        self.csv_path = Path(csv_path)
        self._rows: List[Dict[str, str]] = []
        self._load_data()

    def _load_data(self) -> None:
        """Load CSV with semicolon delimiter and quoted multiline fields."""
        self._rows = []
        if not self.csv_path.exists():
            logger.warning(f"Konesh CSV not found: {self.csv_path}")
            return
        try:
            with open(self.csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
                if reader.fieldnames:
                    # Normalize keys (strip BOM/spaces)
                    fieldnames = [k.strip().replace("\ufeff", "") for k in reader.fieldnames]
                    reader.fieldnames = fieldnames
                for row in reader:
                    # DictReader gives dict; ensure we have all columns as str
                    clean = {}
                    for k, v in (row or {}).items():
                        key = (k or "").strip().replace("\ufeff", "")
                        clean[key] = (v or "").strip()
                    if clean.get(COL_TITLE) or clean.get(COL_BESTAR):
                        self._rows.append(clean)
            logger.info(f"Loaded {len(self._rows)} کنش rows from {self.csv_path}")
        except Exception as e:
            logger.error(f"Failed to load Konesh CSV from {self.csv_path}: {e}")
            self._rows = []

    @property
    def name(self) -> str:
        return "query_konesh_csv"

    @property
    def description(self) -> str:
        return """
        Query the full کنش (Quranic Actions) reference from CSV.

        Use for questions about کنش, کنش ویژه, بستر انجام (خانه، مدرسه، مسجد، فضای مجازی، ...),
        سطح سختی (آسان، متوسط، سخت), کنش‌گر, or هشتگ‌ها.

        Filters:
        - bestar_anjam: بستر انجام (e.g. خانه, مدرسه, مسجد, فضای مجازی)
        - sathe_sakhti: سطح سختی (آسان, متوسط, سخت)
        - koneshgar: کنش‌گر (partial match)
        - hashtags: search in هشتگ‌ها (partial match)
        - vizhe: True = only کنش ویژه (ویژه: بله), False = only non-ویژه, None = all

        Returns عنوان کنش, بستر انجام, سطح سختی, کنش‌گر, مخاطب, short شرح, هشتگ‌ها,
        محتواهای مرتبط (use these terms to fetch from knowledge_base_query for LightRAG).
        """

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (عنوان کنش, شرح, هشتگ, or free text)",
                },
                "bestar_anjam": {
                    "type": "string",
                    "description": "Filter by بستر انجام: خانه, مدرسه, مسجد, فضای مجازی, محیط کار, عمومی",
                },
                "sathe_sakhti": {
                    "type": "string",
                    "description": "Filter by سطح سختی: آسان, متوسط, سخت",
                },
                "koneshgar": {
                    "type": "string",
                    "description": "Filter by کنش‌گر (partial match)",
                },
                "hashtags": {
                    "type": "string",
                    "description": "Search in هشتگ‌ها (partial match)",
                },
                "vizhe": {
                    "type": "boolean",
                    "description": "True = only کنش ویژه (ویژه: بله), False = only non-ویژه, omit = all",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 15,
                },
            },
            "required": ["query"],
        }

    @property
    def enabled(self) -> bool:
        return True

    def _vizhe_match(self, row: Dict[str, str], vizhe: Optional[bool]) -> bool:
        if vizhe is None:
            return True
        val = (row.get(COL_VIZHE) or "").strip().lower()
        if vizhe is True:
            return val in [v.lower() for v in VIZHE_YES]
        return val in [v.lower() for v in VIZHE_NO]

    def _query_words(self, query: str) -> List[str]:
        """Extract significant words from query for meaning-based match. Normalize colloquial forms."""
        q = query.strip()
        if not q:
            return []
        # Normalize colloquial
        for colloquial, canonical in QUERY_NORMALIZE.items():
            q = q.replace(colloquial, canonical)
        # Split on spaces and common punctuation (Persian/English)
        tokens = re.split(r"[\s،؟?\.,;:!\-]+", q)
        return [t.lower() for t in tokens if len(t) >= MIN_WORD_LEN]

    def _text_match(self, row: Dict[str, str], query: str) -> bool:
        """
        Match row by query: (1) full query in text, or (2) any significant word from
        query in row text, so meaning-related questions match even without exact phrase.
        """
        q = query.strip().lower()
        if not q:
            return True
        searchable = " ".join([
            row.get(COL_TITLE, ""),
            row.get(COL_BESTAR, ""),
            row.get(COL_SHARH, "")[:800],
            row.get(COL_HASHTAG, ""),
            row.get(COL_KONESHGAR, ""),
            row.get(COL_MOKHATAB, ""),
            row.get(COL_MOTEVALI, ""),
        ]).lower()
        # Exact phrase match (works for short queries like "خانه" or "کنش ویژه")
        if q in searchable:
            return True
        # Long query: match if any significant word from the question appears in the row
        words = self._query_words(query)
        if not words:
            return False
        return any(w in searchable for w in words)

    def _filter_match(
        self,
        row: Dict[str, str],
        bestar_anjam: Optional[str],
        sathe_sakhti: Optional[str],
        koneshgar: Optional[str],
        hashtags: Optional[str],
    ) -> bool:
        if bestar_anjam and (bestar_anjam.strip() not in (row.get(COL_BESTAR) or "")):
            return False
        if sathe_sakhti and (sathe_sakhti.strip() not in (row.get(COL_SATHE) or "")):
            return False
        if koneshgar:
            k = (row.get(COL_KONESHGAR) or "").lower()
            if koneshgar.strip().lower() not in k:
                return False
        if hashtags:
            h = (row.get(COL_HASHTAG) or "").lower()
            if hashtags.strip().lower() not in h:
                return False
        return True

    def _to_result_item(self, row: Dict[str, str], max_sharh: int = 400) -> Dict[str, Any]:
        """One result entry with short شرح and full محتواهای مرتبط for KB."""
        sharh = (row.get(COL_SHARH) or "").strip()
        if len(sharh) > max_sharh:
            sharh = sharh[:max_sharh] + "..."
        return {
            "عنوان کنش": row.get(COL_TITLE, ""),
            "بستر انجام": row.get(COL_BESTAR, ""),
            "سطح سختی": row.get(COL_SATHE, ""),
            "کنش‌گر": row.get(COL_KONESHGAR, ""),
            "مخاطب": row.get(COL_MOKHATAB, ""),
            "شرح (خلاصه)": sharh,
            "هشتگ‌ها": row.get(COL_HASHTAG, ""),
            "محتواهای مرتبط": row.get(COL_MOTEVALI, ""),
            "ویژه": row.get(COL_VIZHE, ""),
        }

    async def execute(
        self,
        query: str,
        bestar_anjam: Optional[str] = None,
        sathe_sakhti: Optional[str] = None,
        koneshgar: Optional[str] = None,
        hashtags: Optional[str] = None,
        vizhe: Optional[bool] = None,
        limit: int = 15,
    ) -> str:
        """
        Execute query with optional filters. Use vizhe=True for کنش ویژه only.
        """
        if not self._rows:
            return json.dumps({"query": query, "count": 0, "results": [], "motevali_for_kb": []}, ensure_ascii=False, indent=2)

        results = []
        for row in self._rows:
            if not self._vizhe_match(row, vizhe):
                continue
            if not self._filter_match(row, bestar_anjam, sathe_sakhti, koneshgar, hashtags):
                continue
            if not self._text_match(row, query):
                continue
            results.append(self._to_result_item(row))
            if len(results) >= limit:
                break

        # If no results with query match, try filter-only (e.g. "همه کنش‌های ویژه")
        if not results and (vizhe is not None or bestar_anjam or sathe_sakhti or koneshgar or hashtags):
            for row in self._rows:
                if not self._vizhe_match(row, vizhe):
                    continue
                if not self._filter_match(row, bestar_anjam, sathe_sakhti, koneshgar, hashtags):
                    continue
                if not query.strip() or self._text_match(row, query):
                    results.append(self._to_result_item(row))
                    if len(results) >= limit:
                        break

        # Collect محتواهای مرتبط for KB lookup (unique phrases)
        motevali_for_kb: List[str] = []
        seen = set()
        for r in results:
            m = (r.get("محتواهای مرتبط") or "").strip()
            if m and m not in seen:
                seen.add(m)
                motevali_for_kb.append(m)

        out = {
            "query": query,
            "filters": {
                "بستر انجام": bestar_anjam,
                "سطح سختی": sathe_sakhti,
                "کنش‌گر": koneshgar,
                "هشتگ‌ها": hashtags,
                "ویژه (کنش ویژه)": vizhe,
            },
            "count": len(results),
            "results": results,
            "motevali_for_kb": motevali_for_kb,
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    def list_bestars(self) -> List[str]:
        """Return distinct بستر انجام values."""
        s = set()
        for row in self._rows:
            b = (row.get(COL_BESTAR) or "").strip()
            if b:
                s.add(b)
        return sorted(s)

    def list_sathe(self) -> List[str]:
        """Return distinct سطح سختی values."""
        s = set()
        for row in self._rows:
            b = (row.get(COL_SATHE) or "").strip()
            if b:
                s.add(b)
        return sorted(s)
