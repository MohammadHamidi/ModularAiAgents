"""
Compatibility layer for LiteLLM with pydantic-ai
Fixes service_tier validation issue by transforming responses
Based on the working pattern from chat_session_memory.py
"""
import httpx
import json

ALLOWED = {"auto", "default", "flex", "scale", "priority"}
MAP = {"standard": "default", "on_demand": "default"}


async def rewrite_service_tier(resp: httpx.Response):
    path = resp.request.url.path

    # همیشه چاپ کن تا مطمئن شیم هوک اجرا میشه
    print(f"[HOOK] path={path} status={resp.status_code}", flush=True)

    if not path.endswith("/chat/completions"):
        return

    await resp.aread()
    try:
        data = json.loads(resp.content)
    except Exception as e:
        print(f"[HOOK] json parse failed: {e}", flush=True)
        return

    st = data.get("service_tier")
    print(f"[HOOK] service_tier={st!r}", flush=True)

    if st and st not in ALLOWED:
        data["service_tier"] = MAP.get(st, "default")
        new_bytes = json.dumps(data).encode("utf-8")
        resp._content = new_bytes
        resp.headers["content-length"] = str(len(new_bytes))
        print(f"[HOOK] patched to {data['service_tier']!r}", flush=True)


def create_litellm_compatible_client() -> httpx.AsyncClient:
    """Create an httpx client with LiteLLM compatibility fixes"""
    return httpx.AsyncClient(event_hooks={"response": [rewrite_service_tier]})
