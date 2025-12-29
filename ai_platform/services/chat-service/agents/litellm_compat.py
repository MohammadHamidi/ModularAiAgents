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
    
    # Debug: Log request body to see if tools are being sent
    try:
        req_body = json.loads(resp.request.content)
        has_tools = "tools" in req_body
        tool_count = len(req_body.get("tools", []))
        message_count = len(req_body.get("messages", []))
        print(f"[HOOK] REQUEST has_tools={has_tools} tool_count={tool_count} message_count={message_count}", flush=True)
        # Log message roles to debug history
        messages = req_body.get("messages", [])
        if messages:
            roles = [f"{m.get('role', '?')}" for m in messages]
            print(f"[HOOK] MESSAGE_ROLES: {roles}", flush=True)
        if has_tools:
            for t in req_body.get("tools", []):
                fn = t.get("function", {})
                name = fn.get("name", "?")
                desc = fn.get("description", "")[:200]  # First 200 chars
                print(f"[HOOK] TOOL: {name}", flush=True)
                print(f"[HOOK] TOOL_DESC: {desc}...", flush=True)
    except Exception as e:
        print(f"[HOOK] req parse error: {e}", flush=True)

    await resp.aread()
    try:
        data = json.loads(resp.content)
    except Exception as e:
        print(f"[HOOK] json parse failed: {e}", flush=True)
        return

    st = data.get("service_tier")
    print(f"[HOOK] service_tier={st!r}", flush=True)
    
    # Debug: Log response to see if tool_calls are returned
    choices = data.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        finish_reason = choices[0].get("finish_reason", "?")
        print(f"[HOOK] RESPONSE finish_reason={finish_reason} tool_calls_count={len(tool_calls)}", flush=True)
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                print(f"[HOOK] TOOL_CALL: {fn.get('name')} args={fn.get('arguments')}", flush=True)

    if st and st not in ALLOWED:
        data["service_tier"] = MAP.get(st, "default")
        new_bytes = json.dumps(data).encode("utf-8")
        resp._content = new_bytes
        resp.headers["content-length"] = str(len(new_bytes))
        print(f"[HOOK] patched to {data['service_tier']!r}", flush=True)


def create_litellm_compatible_client() -> httpx.AsyncClient:
    """Create an httpx client with LiteLLM compatibility fixes"""
    return httpx.AsyncClient(event_hooks={"response": [rewrite_service_tier]})
