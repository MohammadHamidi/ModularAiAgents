"""
Verify that session memory (database) and LightRAG knowledge retrieval work.

Usage:
  From ai_platform: python test_memory_and_lightrag.py
  Or set CHAT_SERVICE_URL to your chat-service base (e.g. http://localhost:8001 or via gateway proxy).
"""
import asyncio
import os
import sys

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

# Chat service base URL: direct to chat-service or via gateway
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")
# If using gateway for chat, use GATEWAY_URL and /chat/... proxy
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")


async def check_dependencies(base_url: str) -> dict:
    """Call /health/dependencies on chat-service. Use base_url of chat-service (e.g. :8001)."""
    try:
        r = await httpx.AsyncClient(timeout=15.0).get(f"{base_url}/health/dependencies")
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "body": r.text[:300]}
        return r.json()
    except Exception as e:
        return {"error": str(e)}


async def main():
    print("=" * 60)
    print("Memory & LightRAG dependency check")
    print("=" * 60)

    # /health/dependencies is on the chat-service. Prefer CHAT_SERVICE_URL (e.g. http://localhost:8001).
    chat_base = CHAT_SERVICE_URL.rstrip("/")
    try:
        r = await httpx.AsyncClient(timeout=5.0).get(f"{chat_base}/health")
        if r.status_code != 200:
            chat_base = None
    except Exception:
        chat_base = None

    if not chat_base:
        try:
            r = await httpx.AsyncClient(timeout=5.0).get(f"{GATEWAY_URL.rstrip('/')}/health")
            if r.status_code == 200:
                chat_base = GATEWAY_URL.rstrip("/")
        except Exception:
            pass

    if not chat_base:
        print("Could not reach chat service or gateway. Tried:")
        print(f"  CHAT_SERVICE_URL={CHAT_SERVICE_URL}")
        print(f"  GATEWAY_URL={GATEWAY_URL}")
        print("Start the stack (e.g. docker-compose up) or set CHAT_SERVICE_URL to your chat-service URL (e.g. http://localhost:8001).")
        sys.exit(1)

    print(f"Using base URL: {chat_base}")
    print(f"Checking: {chat_base}/health/dependencies")
    deps = await check_dependencies(chat_base)
    if "error" in deps:
        print(f"Dependencies check failed: {deps['error']}")
        if deps.get("body"):
            print(deps["body"])
        sys.exit(1)

    db = deps.get("database", "unknown")
    lightrag = deps.get("lightrag", "unknown")

    print()
    print("Results:")
    print(f"  Session memory (database): {db}")
    if db != "ok":
        print(f"    -> Fix: DATABASE_URL must point to PostgreSQL with chat_sessions (and agent_context) tables.")
    print(f"  LightRAG knowledge retrieval: {lightrag}")
    if lightrag == "not_configured":
        print("    -> LIGHTRAG_BASE_URL is not set. Set it in .env / Coolify to enable knowledge base.")
    elif lightrag == "unavailable":
        print("    -> LightRAG is configured but unreachable or returned an error.")
        if deps.get("lightrag_detail"):
            print(f"    -> Detail: {deps['lightrag_detail']}")
    else:
        print("    -> OK: context retrieval is working.")
    print()

    if db == "ok" and lightrag in ("ok", "not_configured"):
        print("Memory and (if configured) LightRAG checks passed.")
        sys.exit(0)
    if db != "ok":
        print("Session memory check failed. Conversation history may not persist.")
        sys.exit(1)
    if lightrag == "unavailable":
        print("LightRAG check failed. Knowledge retrieval may be unavailable.")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
