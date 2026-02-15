#!/usr/bin/env python3
"""
Build local knowledge YAML files from CSV and docx sources.
Run from project root or chat-service directory.
"""
import csv
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths relative to script
SCRIPT_DIR = Path(__file__).resolve().parent
CHAT_SERVICE_DIR = SCRIPT_DIR.parent
CONFIG_DIR = CHAT_SERVICE_DIR / "config"
LOCAL_DIR = CONFIG_DIR / "local"
AI_PLATFORM_DIR = CHAT_SERVICE_DIR.parent.parent

# Source file candidates (in order of preference)
def _csv_candidates():
    return [
        AI_PLATFORM_DIR / "۳۰آیه رمضان۱۴۰۴ برای نشر.csv",
        AI_PLATFORM_DIR / "۳۰آیه رمضان۱۴۰۴ برای نشر .csv",
        Path.home() / "Desktop" / "۳۰آیه رمضان۱۴۰۴ برای نشر.csv",
        Path.home() / "Desktop" / "۳۰آیه رمضان۱۴۰۴ برای نشر .csv",
    ]


CSV_CANDIDATES = _csv_candidates()

DOCX_CANDIDATES = [
    AI_PLATFORM_DIR / "فهرست کنش_های ویژه.docx",
    AI_PLATFORM_DIR / "فهرست کنش‌های ویژه.docx",
]

KONESH_CSV_CANDIDATES = [
    AI_PLATFORM_DIR / "Konesh.csv",
    CHAT_SERVICE_DIR.parent.parent / "Konesh.csv",
]


def find_csv(csv_path: Path | str | None = None) -> Path | None:
    if csv_path:
        p = Path(csv_path)
        if p.exists():
            return p
    for p in CSV_CANDIDATES:
        if p.exists():
            return p
    return None


def find_docx() -> Path | None:
    for p in DOCX_CANDIDATES:
        if p.exists():
            return p
    return None


def find_konesh_csv(csv_path: Path | str | None = None) -> Path | None:
    if csv_path:
        p = Path(csv_path)
        if p.exists():
            return p
    for p in KONESH_CSV_CANDIDATES:
        if p.exists():
            return p
    return None


# Map Persian category to English
_CATEGORY_EN = {
    "خانه": "home",
    "مدرسه": "school",
    "مسجد": "mosque",
    "فضای مجازی": "virtual",
    "محیط کار": "work",
    "عمومی": "general",
}


def build_konesh_from_csv(csv_path: Path) -> list[dict]:
    """
    Parse Konesh.csv (tab-delimited, UTF-8).
    Columns: بستر انجام, عنوان کنش, سطح سختی, کنش‌گر, مخاطب, شرح و الگوی اجرا, هشتگ‌ها, محتواهای مرتبط, دیتای لازم, ویژه
    """
    import re
    konesh_list = []
    try:
        with open(csv_path, encoding="utf-8", newline="", errors="replace") as f:
            reader = csv.reader(f, delimiter="\t")
            rows = list(reader)
    except Exception as e:
        logger.error(f"Failed to read Konesh.csv: {e}")
        return []

    if len(rows) < 2:
        logger.warning("Konesh.csv has no data rows")
        return []

    for idx, row in enumerate(rows[1:], start=1):  # Skip header
        if len(row) < 6:
            continue
        # Cols: 0=بستر, 1=عنوان, 2=سطح سختی, 3=کنشگر, 4=مخاطب, 5=شرح, 6=هشتگ, 7=محتوا, 8=دیتا, 9=ویژه
        bastar = (row[0] or "").strip()
        name = (row[1] or "").strip()
        if not name:
            continue
        difficulty = (row[2] or "").strip()
        actor = (row[3] or "").strip()
        audience = (row[4] or "").strip()
        desc_full = (row[5] or "").strip()
        hashtags = (row[6] or "").strip()
        content = (row[7] or "").strip() if len(row) > 7 else ""
        vije = (row[9] or "").strip().lower() if len(row) > 9 else ""

        # Parse keywords from hashtags (#tag -> tag)
        keywords = []
        for m in re.finditer(r"#([^\s#]+)", hashtags):
            kw = m.group(1).replace("_", " ")
            if kw and kw not in keywords:
                keywords.append(kw)
        if not keywords and name:
            keywords = [w for w in name.split() if len(w) > 1][:5]

        category_en = _CATEGORY_EN.get(bastar, bastar.lower() if bastar else "")

        konesh_list.append({
            "id": idx,
            "name": name,
            "name_en": name,  # CSV has no English name; use Persian for search
            "category": bastar or "عمومی",
            "category_en": category_en or "general",
            "is_primary": vije in ("بله", "yes", "1", "true"),
            "description": desc_full[:500] + ("..." if len(desc_full) > 500 else ""),
            "main_platform": bastar or "عمومی",
            "actor": actor or "سفیر",
            "target_audience": audience or "عموم",
            "execution_format": desc_full[:2000],  # Truncate for YAML
            "content": content[:500] if content else "",
            "keywords": keywords[:15],
        })

    logger.info(f"Parsed {len(konesh_list)} konesh from {csv_path}")
    return konesh_list


def build_verses_from_csv(csv_path: Path) -> list[dict]:
    verses = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            row_id = row.get("ردیف", "").strip()
            if not row_id or not row_id.isdigit():
                continue
            vid = int(row_id)
            verses.append({
                "id": vid,
                "surah_name": (row.get("نام سوره") or "").strip(),
                "surah_number": (row.get("شماره سوره") or "").strip(),
                "ayah_number": (row.get("آیه") or "").strip(),
                "verse_text_ar": (row.get("بخش اصلی آیه") or row.get("کل آیه") or "").strip(),
                "translation_fa": (row.get("ترجمه آیه") or "").strip(),
                "attractive_title": (row.get("عنوان جذاب") or "").strip(),
                "analytical_notes": (row.get("نکات تحلیلی و دلیل انتخاب (با رویکرد جامع‌تر و مطابق با بیانات رهبری)") or "").strip(),
                "angareh": (row.get("محور") or "").strip(),
                "contextual_100_word": (row.get("متن ۱۰۰کلمه‌ای") or "").strip(),
            })
    return verses


def build_special_actions_from_docx(docx_path: Path) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed; skipping docx. Run: pip install python-docx")
        return []

    actions = []
    try:
        doc = Document(docx_path)
        # Extract paragraphs; structure depends on docx layout
        for i, para in enumerate(doc.paragraphs):
            text = (para.text or "").strip()
            if text:
                actions.append({
                    "id": i + 1,
                    "name": text[:100],
                    "session_type": "مبسوط",  # default; can be refined from content
                })
        logger.info(f"Extracted {len(actions)} items from docx")
    except Exception as e:
        logger.warning(f"Failed to parse docx: {e}")
    return actions


def build_konesh_type_mapping() -> dict[str, str]:
    """Map konesh names to session type (مبسوط or فشرده) based on konesh_database."""
    konesh_yaml = CONFIG_DIR / "konesh_database.yaml"
    if not konesh_yaml.exists():
        return {}

    with open(konesh_yaml, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    konesh_list = data.get("konesh_list", [])
    mapping = {}

    # Short session keywords (فشرده)
    feshorde_keywords = [
        "قبل از جزء", "جزء‌خوانی", "بین دو نماز", "صبحگاه",
        "سفره", "دعوت نزدیکان", "کد معرف", "هفته", "تخته کلاس",
    ]
    # Long session keywords (مبسوط)
    mobsut_keywords = [
        "محفل", "فضاسازی", "منبر", "مهمونی", "قصه شب",
    ]

    for k in konesh_list:
        name = (k.get("name") or "").strip()
        if not name:
            continue
        session_type = "مبسوط"
        for kw in feshorde_keywords:
            if kw in name:
                session_type = "فشرده"
                break
        if session_type == "مبسوط":
            for kw in mobsut_keywords:
                if kw in name:
                    session_type = "مبسوط"
                    break
        mapping[name] = session_type

    return mapping


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Path to 30 verses CSV file")
    parser.add_argument("--konesh-csv", help="Path to Konesh.csv (tab-delimited)")
    args = parser.parse_args()

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    # 0. Build konesh_database.yaml from Konesh.csv (if available)
    konesh_csv_path = find_konesh_csv(args.konesh_csv)
    if konesh_csv_path:
        logger.info(f"Reading konesh from {konesh_csv_path}")
        konesh_list = build_konesh_from_csv(konesh_csv_path)
        if konesh_list:
            konesh_out = CONFIG_DIR / "konesh_database.yaml"
            konesh_data = {"konesh_list": konesh_list}
            with open(konesh_out, "w", encoding="utf-8") as f:
                yaml.dump(konesh_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            logger.info(f"Wrote {len(konesh_list)} konesh to {konesh_out}")

    # 1. Build verses_30.yaml from CSV
    csv_path = find_csv(args.csv)
    if not csv_path:
        logger.error("CSV file not found. Please copy '۳۰آیه رمضان۱۴۰۴ برای نشر.csv' to ai_platform/")
        return 1

    logger.info(f"Reading verses from {csv_path}")
    verses = build_verses_from_csv(csv_path)
    verses_data = {"verses": verses}
    verses_out = LOCAL_DIR / "verses_30.yaml"
    with open(verses_out, "w", encoding="utf-8") as f:
        yaml.dump(verses_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    logger.info(f"Wrote {len(verses)} verses to {verses_out}")

    # 2. Build special_actions.yaml from docx (optional)
    docx_path = find_docx()
    if docx_path:
        actions = build_special_actions_from_docx(docx_path)
        actions_data = {"special_actions": actions}
        actions_out = LOCAL_DIR / "special_actions.yaml"
        with open(actions_out, "w", encoding="utf-8") as f:
            yaml.dump(actions_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"Wrote {len(actions)} special actions to {actions_out}")
    else:
        # Create empty placeholder
        actions_out = LOCAL_DIR / "special_actions.yaml"
        with open(actions_out, "w", encoding="utf-8") as f:
            yaml.dump({"special_actions": []}, f, allow_unicode=True)
        logger.info(f"Docx not found; created empty {actions_out}")

    # 3. Build konesh_type_mapping.yaml
    konesh_mapping = build_konesh_type_mapping()
    mapping_out = LOCAL_DIR / "konesh_type_mapping.yaml"
    with open(mapping_out, "w", encoding="utf-8") as f:
        yaml.dump({"konesh_session_types": konesh_mapping}, f, allow_unicode=True, sort_keys=False)
    logger.info(f"Wrote konesh type mapping ({len(konesh_mapping)} entries) to {mapping_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
