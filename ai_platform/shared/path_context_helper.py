"""
Helper to get Persian descriptions for website paths.
Used to provide context to agents about where the user came from.
"""
import yaml
from pathlib import Path
from typing import Optional, Dict


def _get_path_mapping_path() -> Path:
    """Resolve path to path_agent_mapping.yaml."""
    base = Path(__file__).parent.parent  # ai_platform
    p = base / "services" / "chat-service" / "config" / "path_agent_mapping.yaml"
    if p.exists():
        return p
    return base / "config" / "path_agent_mapping.yaml"


def _get_website_routes_path() -> Path:
    """Resolve path to website_routes.yaml."""
    base = Path(__file__).parent.parent  # ai_platform
    p = base / "services" / "chat-service" / "config" / "website_routes.yaml"
    if p.exists():
        return p
    return base / "config" / "website_routes.yaml"


_path_descriptions_cache: Optional[Dict[str, str]] = None


def _load_path_descriptions() -> Dict[str, str]:
    """Load path descriptions from config files."""
    global _path_descriptions_cache
    if _path_descriptions_cache is not None:
        return _path_descriptions_cache

    descriptions = {}

    # Load from path_agent_mapping.yaml
    mapping_path = _get_path_mapping_path()
    if mapping_path.exists():
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                mappings = data.get("mappings", [])
                for m in mappings:
                    path = m.get("path", "")
                    desc = m.get("description", "")
                    if path and desc:
                        # Extract Persian part if exists
                        if " - " in desc:
                            persian_part = desc.split(" - ")[-1]
                            if any(ord(c) > 127 for c in persian_part):  # Has Persian chars
                                descriptions[path] = persian_part
                            else:
                                descriptions[path] = desc
                        else:
                            descriptions[path] = desc
        except Exception:
            pass

    # Load from website_routes.yaml (more detailed descriptions)
    routes_path = _get_website_routes_path()
    if routes_path.exists():
        try:
            with open(routes_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                routes = data.get("routes", [])
                for r in routes:
                    path = r.get("path", "")
                    title = r.get("title_fa", "")
                    desc = r.get("description", "")
                    if path:
                        # Prefer title_fa + description
                        if title and desc:
                            descriptions[path] = f"{title} - {desc}"
                        elif title:
                            descriptions[path] = title
                        elif desc:
                            descriptions[path] = desc
        except Exception:
            pass

    _path_descriptions_cache = descriptions
    return descriptions


def get_path_description(path: str) -> str:
    """
    Get Persian description for a website path.
    
    Args:
        path: Website path (e.g., "/action-list", "konesh/list/")
    
    Returns:
        Persian description or the path itself if not found
    
    Examples:
        >>> get_path_description("/action-list")
        "لیست کنش‌ها"
        >>> get_path_description("/my-profile/saved-actions")
        "کنش‌های ذخیره‌شده"
    """
    if not path:
        return "صفحه اصلی"
    
    # Normalize path
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    
    descriptions = _load_path_descriptions()
    
    # Try exact match first
    if path in descriptions:
        return descriptions[path]
    
    # Try matching with wildcards (e.g., "/konesh/*" matches "/konesh/list")
    for pattern, desc in descriptions.items():
        if "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(path, pattern):
                return desc
    
    # Fallback: generate description from path
    path_parts = [p for p in path.split("/") if p]
    if not path_parts:
        return "صفحه اصلی"
    
    # Common path translations
    translations = {
        "action-list": "لیست کنش‌ها",
        "actions": "کنش‌ها",
        "konesh": "کنش",
        "my-profile": "پروفایل من",
        "saved-actions": "کنش‌های ذخیره‌شده",
        "saved-contents": "محتوای ذخیره‌شده",
        "report-form": "فرم گزارش",
        "done-task": "وظایف انجام‌شده",
        "contents": "کتابخانه محتوا",
        "mobaleghan": "مبلغین",
        "ai": "هوش مصنوعی",
    }
    
    last_part = path_parts[-1]
    if last_part in translations:
        return translations[last_part]
    
    # Return path as-is if no translation found
    return path


def format_entry_path_context(path: str) -> str:
    """
    Format entry path as context string for agent prompt.
    
    Args:
        path: Website path where user opened chat
    
    Returns:
        Formatted context string in Persian
    """
    if not path:
        return ""
    
    description = get_path_description(path)
    
    # Normalize path for display
    display_path = path.strip()
    if not display_path.startswith("/"):
        display_path = "/" + display_path
    
    # Simplify description if too long
    if len(description) > 60:
        # Try to extract just the title part
        if " - " in description:
            description = description.split(" - ")[0]
        elif len(description) > 60:
            description = description[:60] + "..."
    
    # Check if path contains action ID (e.g., /actions/40)
    action_id_match = None
    if "/actions/" in display_path:
        import re
        match = re.search(r'/actions/(\d+)', display_path)
        if match:
            action_id_match = match.group(1)
    
    context_text = f"📍 کاربر چت را از صفحه «{description}» ({display_path}) باز کرده است."
    
    if action_id_match:
        context_text += f"\n⚠️ مهم: کاربر در حال دیدن کنش شماره {action_id_match} است."
    
    context_text += "\nاین یعنی کاربر احتمالاً در حال دیدن این صفحه است و ممکن است به محتوای این صفحه اشاره کند (مثلاً «همین کنش»، «این صفحه»، «اینجا»).\nوقتی کاربر می‌گوید «همین» یا «این»، منظور او احتمالاً محتوای همین صفحه است."
    
    return context_text

