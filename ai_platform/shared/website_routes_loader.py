"""
Load website routes reference for injection into agent prompts.
Enables agents to correctly redirect users to safiranayeha.ir pages.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


def _get_routes_path() -> Path:
    """Resolve path to website_routes.yaml."""
    # shared/ is sibling of services/ under ai_platform
    base = Path(__file__).parent.parent  # ai_platform
    p = base / "services" / "chat-service" / "config" / "website_routes.yaml"
    if p.exists():
        return p
    return base / "config" / "website_routes.yaml"


def get_website_routes_context() -> str:
    """
    Load website routes and format as context block for system prompt.
    Returns a string that agents can use when redirecting users.
    """
    import yaml

    path = _get_routes_path()
    if not path.exists():
        return ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return ""

    if not data or "routes" not in data:
        return ""

    base = data.get("base_url", "https://safiranayeha.ir")
    routes: List[Dict[str, Any]] = data.get("routes", [])

    lines = [
        "📌 آدرس‌های وب‌سایت سفیران آیه‌ها (برای هدایت کاربر):",
        "وقتی کاربر را به صفحه‌ای هدایت می‌کنی، از این آدرس‌های دقیق استفاده کن:",
        "",
    ]
    for r in routes:
        url = r.get("url") or f"{base}{r.get('path', '')}"
        title = r.get("title_fa", "")
        desc = r.get("description", "")
        when = r.get("when_to_use", "")
        line = f"• {url}"
        if title:
            line += f" — {title}"
        if desc:
            line += f" ({desc})"
        if when:
            line += f" — استفاده: {when}"
        lines.append(line)

    lines.extend([
        "",
        "⚠️ مهم: هرگز آدرس اشتباه یا حدسی نده. فقط از لیست بالا استفاده کن.",
    ])
    return "\n".join(lines)


def get_routes_summary() -> str:
    """Shorter summary for compact injection."""
    import yaml

    path = _get_routes_path()
    if not path.exists():
        return ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return ""

    routes = data.get("routes", [])
    if not routes:
        return ""

    pairs = []
    for r in routes:
        url = r.get("url") or f"{data.get('base_url','')}{r.get('path','')}"
        title = r.get("title_fa", r.get("path", ""))
        pairs.append(f"{title}: {url}")

    return "آدرس‌های سایت: " + " | ".join(pairs[:15]) + (" ..." if len(pairs) > 15 else "")
