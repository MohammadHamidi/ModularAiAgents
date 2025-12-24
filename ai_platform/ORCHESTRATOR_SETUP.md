# 🎯 Orchestrator Agent Setup Guide

This guide shows you how to integrate the Orchestrator Agent that automatically routes user requests to specialist agents.

## 📋 Files Created

1. ✅ `config/personalities/orchestrator.yaml` - Orchestrator configuration
2. ✅ `tools/agent_router.py` - Routing tool implementation

## 🔧 Changes Needed in `main.py`

### Step 1: Import the Routing Tool

Add this import at the top of `main.py` (around line 29):

```python
from tools.agent_router import AgentRouterTool, AgentRouterToolSync
```

### Step 2: Add Orchestrator to Persona Configs

Find the `persona_configs` dictionary (around line 261) and add:

```python
persona_configs = {
    "default": "agent_config.yaml",
    "tutor": "personalities/friendly_tutor.yaml",
    "professional": "personalities/professional_assistant.yaml",
    "minimal": "personalities/minimal_assistant.yaml",
    "orchestrator": "personalities/orchestrator.yaml",  # ✅ ADD THIS
}
```

### Step 3: Initialize Agents Registry (IMPORTANT!)

Before the loop that registers agents (around line 268), add this:

```python
# ==========================================================================
# Initialize AGENTS registry BEFORE registering personas
# This is needed so the orchestrator can access other agents
# ==========================================================================
AGENTS = {}  # This should already exist, but make sure it's defined

# First pass: Register all agents WITHOUT orchestrator
logging.info("First pass: Registering all specialist agents...")
for agent_key, config_path in persona_configs.items():
    if agent_key == "orchestrator":  # Skip orchestrator in first pass
        continue

    try:
        persona_config = load_agent_config(config_path)
        persona_model_config = persona_config.model_config

        # Get tools for this persona
        tool_names = persona_tool_assignments.get(agent_key, [])
        persona_tools = [ToolRegistry.get_tool(name) for name in tool_names if ToolRegistry.get_tool(name)]

        # Create agent config
        agent_config = AgentConfig(
            name=persona_config.agent_name,
            model=default_model,
            max_turns=persona_model_config.get("max_turns", max_turns),
            temperature=persona_model_config.get("temperature", temperature),
            extra={
                **base_config,
                "system_prompt": persona_config.get_complete_system_prompt()
            }
        )

        # Create agent with custom tools
        agent = ChatAgent(agent_config, context_manager, persona_config, custom_tools=persona_tools)
        AGENTS[agent_key] = agent
        AGENT_CONFIGS[agent_key] = persona_config

        logging.info(f"Registered agent '{agent_key}': {persona_config.agent_name} with {len(persona_tools)} tools")
    except Exception as e:
        logging.warning(f"Failed to load persona '{agent_key}' from {config_path}: {e}")
        import traceback
        traceback.print_exc()

# Second pass: Register orchestrator with routing tool
logging.info("Second pass: Registering orchestrator agent...")
if "orchestrator" in persona_configs:
    try:
        orchestrator_config_path = persona_configs["orchestrator"]
        orchestrator_persona_config = load_agent_config(orchestrator_config_path)
        orchestrator_model_config = orchestrator_persona_config.model_config

        # Create the routing tool with access to all agents
        routing_tool = AgentRouterToolSync(AGENTS, context_manager)

        # Wrap it in a Tool-like object for compatibility
        from tools.registry import Tool

        class RouterToolWrapper(Tool):
            def __init__(self, router):
                self.router = router
                self._name = router.name
                self._description = router.description
                self._enabled = True

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return self._description

            @property
            def enabled(self) -> bool:
                return self._enabled

            @property
            def parameters(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "agent_key": {
                            "type": "string",
                            "description": "The key of the specialist agent to route to (doctor, tutor, professional, default, minimal)"
                        },
                        "user_message": {
                            "type": "string",
                            "description": "The user's original message to forward"
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID for context"
                        }
                    },
                    "required": ["agent_key", "user_message"]
                }

            async def execute(self, agent_key: str, user_message: str, session_id: str = None) -> str:
                return self.router.run(agent_key, user_message, session_id)

        routing_tool_wrapped = RouterToolWrapper(routing_tool)

        # Create orchestrator agent config
        orchestrator_agent_config = AgentConfig(
            name=orchestrator_persona_config.agent_name,
            model=default_model,
            max_turns=orchestrator_model_config.get("max_turns", 3),
            temperature=orchestrator_model_config.get("temperature", 0.3),
            extra={
                **base_config,
                "system_prompt": orchestrator_persona_config.get_complete_system_prompt()
            }
        )

        # Create orchestrator agent with routing tool
        orchestrator_agent = ChatAgent(
            orchestrator_agent_config,
            context_manager,
            orchestrator_persona_config,
            custom_tools=[routing_tool_wrapped]
        )

        AGENTS["orchestrator"] = orchestrator_agent
        AGENT_CONFIGS["orchestrator"] = orchestrator_persona_config

        logging.info(f"Registered orchestrator agent with routing to {len(AGENTS)-1} specialists")
    except Exception as e:
        logging.warning(f"Failed to load orchestrator: {e}")
        import traceback
        traceback.print_exc()
```

### Step 4: Update Startup Event

The existing startup code should be REPLACED with the code above. Find the section that looks like:

```python
# Register each persona as a separate agent with their tools
for agent_key, config_path in persona_configs.items():
    try:
        persona_config = load_agent_config(config_path)
        # ... rest of the code
```

Replace it with the two-pass approach shown above.

## 🎯 Usage

### Option 1: Use Orchestrator Directly (Recommended for Users)

Users can chat with the orchestrator, and it will automatically route to specialists:

```bash
# User doesn't need to know which agent to use!
curl -X POST http://localhost:8000/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "سلام، سردرد دارم و تب کردم",
    "session_id": null
  }'

# Orchestrator automatically routes to "doctor" agent
```

```bash
# Another example - educational query
curl -X POST http://localhost:8000/chat/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "می‌خوام درباره ریاضی یاد بگیرم",
    "session_id": null
  }'

# Orchestrator automatically routes to "tutor" agent
```

### Option 2: Direct Agent Access (Still Available)

Users can still directly access specialist agents if they want:

```bash
curl -X POST http://localhost:8000/chat/doctor \
  -H "Content-Type: application/json" \
  -d '{"message": "سلام", "session_id": null}'
```

## 🧪 Testing

### 1. Start Services

```bash
cd ai_platform
docker-compose down
docker-compose up -d --build
```

### 2. Check Logs

```bash
docker-compose logs -f chat-service | grep -i orchestrator
```

You should see:
```
Registered orchestrator agent with routing to 4 specialists
```

### 3. Test Routing

Create a test file `test_orchestrator.py`:

```python
import httpx
import json

BASE_URL = "http://localhost:8000"

test_cases = [
    {
        "message": "سلام، سردرد دارم",
        "expected_agent": "doctor",
        "description": "Medical query"
    },
    {
        "message": "Help me with my homework",
        "expected_agent": "tutor",
        "description": "Educational query"
    },
    {
        "message": "درباره آیه 12 بگو",
        "expected_agent": "default",
        "description": "Religious query"
    },
    {
        "message": "I need help with a business proposal",
        "expected_agent": "professional",
        "description": "Professional query"
    }
]

async def test_orchestrator():
    async with httpx.AsyncClient() as client:
        for test in test_cases:
            print(f"\n{'='*60}")
            print(f"Test: {test['description']}")
            print(f"Message: {test['message']}")
            print(f"Expected: Routes to '{test['expected_agent']}'")

            response = await client.post(
                f"{BASE_URL}/chat/orchestrator",
                json={
                    "message": test["message"],
                    "session_id": None
                }
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Response received:")
                print(f"   {data['output'][:100]}...")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_orchestrator())
```

Run it:
```bash
python test_orchestrator.py
```

## 🔍 How It Works

```
User: "سلام، سردرد دارم"
  ↓
Orchestrator Agent
  ↓
Analyzes keywords: "سردرد" (headache)
  ↓
Decision: Medical topic → route to "doctor"
  ↓
Calls: route_to_agent(agent_key="doctor", user_message="سلام، سردرد دارم")
  ↓
Doctor Agent processes request
  ↓
Doctor Agent returns response
  ↓
Orchestrator returns response to user
  ↓
User sees: "سلام! خوب به نظر می‌رسه سردرد داری..."
```

## 🎨 Advanced: Custom Routing Logic

If you want more sophisticated routing (e.g., based on user history, sentiment, etc.):

1. Modify the `system_prompt` in `orchestrator.yaml`
2. Add more context to routing decisions
3. Use user data fields to remember preferred agents

Example enhancement in `orchestrator.yaml`:

```yaml
system_prompt: |
  # ... existing prompt ...

  🔍 Advanced Routing Rules:

  - If user has "preferred_agent" set → always use that unless they explicitly ask for different topic
  - If user previously talked to a specialist → consider context continuity
  - If query spans multiple topics → choose PRIMARY topic or ask user to clarify
  - If user seems frustrated → route to most patient agent (tutor)
```

## 🚀 Benefits

✅ **Better UX**: Users don't need to know which agent to choose
✅ **Automatic**: Intelligent routing based on content
✅ **Flexible**: Can still access agents directly if needed
✅ **Maintainable**: Easy to add new specialist agents
✅ **Context-Aware**: Can use user history for routing

## 📊 Monitoring

Check routing statistics in logs:

```bash
docker-compose logs chat-service | grep "Routing request to agent"
```

You'll see patterns like:
```
Routing request to agent 'doctor': سلام، سردرد دارم...
Routing request to agent 'tutor': Help me with math...
Routing request to agent 'default': درباره آیه 12...
```

---

**Ready to implement? Follow the steps above!** 🎉
