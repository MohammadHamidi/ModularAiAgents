# AI Platform API Contract

Documentation of the chat service API contract for migration compatibility. Chain-based executor must preserve these contracts.

## Request: AgentRequest

**Source:** `shared/base_agent.AgentRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | str | Yes | User's message |
| `session_id` | str \| None | No | Session UUID for conversation continuity |
| `context` | Dict[str, Any] | No | Request-level context (default: {}) |
| `use_shared_context` | bool | No | Whether to load shared context (default: True) |
| `user_data` | Dict[str, Any] | No | User data from app, saved immediately (default: {}) |

## Response: AgentResponse

**Source:** `shared/base_agent.AgentResponse`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | str | Yes | Session UUID |
| `output` | str | Yes | Agent's text response |
| `metadata` | Dict[str, Any] | No | Additional data (default: {}) |
| `context_updates` | Dict[str, Any] | No | Context to merge (default: {}) |

**metadata** typically includes:
- `model`: str - Model name used
- `history`: List[Dict] - Updated conversation history with `role`, `content`, `timestamp`

**context_updates** format: `{normalized_field_name: {"value": ...}}` per context_manager schema

## Process Interface

**Source:** `shared/base_agent.BaseAgent.process()`

```python
async def process(
    self,
    request: AgentRequest,
    history: List[Dict] | None = None,
    shared_context: Dict[str, Any] | None = None
) -> AgentResponse
```

- `history`: List of messages `[{"role": "user"|"assistant", "content": str, "timestamp": str}, ...]`
- `shared_context`: `{normalized_name: {"value": ...}}` from ContextManager

## SSE Streaming Format

**Endpoint:** `POST /chat/{agent_key}/stream`

**Event types** (one per line, `data: {...}\n\n`):

| Event | Payload | When |
|-------|---------|------|
| `session_id` | `{"session_id": "uuid"}` | First event |
| `chunk` | `{"chunk": "word "}` | Streaming output (word-by-word) |
| `done` | `{"done": true}` | Stream complete |
| `error` | `{"error": "message"}` | On failure |

## REST Chat Endpoint

**Endpoint:** `POST /chat/{agent_key}`

**Request body:** Same as AgentRequest (JSON)

**Response:** AgentResponse as JSON

## Shared Context Format

**Source:** `shared/context_manager.ContextManager`

- `get_context(session_id)` returns: `{context_key: value}` 
- `merge_context(session_id, context, agent_type)` accepts: `{normalized_name: {"value": ...}}`
- Values stored in PostgreSQL `agent_context` table as JSONB
