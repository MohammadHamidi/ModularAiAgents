# Configuration System Documentation

## Overview

The ModularAiAgents chat system now uses a **flexible YAML-based configuration system** that allows you to fully customize:

- ✅ Agent personality and instructions
- ✅ User data fields to extract and save
- ✅ Context display format
- ✅ Privacy and security settings
- ✅ Model parameters
- ✅ Recent messages tracking

---

## Quick Start

###Step 1: Choose a Configuration

```bash
# Use default config
AGENT_CONFIG_FILE=agent_config.yaml

# Use professional assistant personality
AGENT_CONFIG_FILE=personalities/professional_assistant.yaml

# Use friendly tutor personality
AGENT_CONFIG_FILE=personalities/friendly_tutor.yaml

# Use minimal/privacy-focused config
AGENT_CONFIG_FILE=personalities/minimal_assistant.yaml
```

### Step 2: Set Environment Variable

Edit `.env` file:
```bash
AGENT_CONFIG_FILE=personalities/friendly_tutor.yaml
```

### Step 3: Restart Services

```bash
cd ai_platform
docker-compose restart chat-service
```

That's it! Your agent now has a new personality!

---

## Configuration File Structure

### Location

Configuration files are in:
```
ai_platform/services/chat-service/config/
├── agent_config.yaml              # Default config
└── personalities/
    ├── professional_assistant.yaml
    ├── friendly_tutor.yaml
    └── minimal_assistant.yaml
```

### Main Sections

```yaml
# 1. Metadata
agent_name: "Your Agent Name"
agent_version: "2.0"
description: "Agent description"

# 2. Personality & Instructions
system_prompt: |
  Your agent's personality and behavior instructions...

silent_operation_instructions: |
  Rules for silent data saving...

tool_usage_instructions: |
  How to use the save_user_info tool...

# 3. User Data Fields (what to extract)
user_data_fields:
  - field_name: name
    normalized_name: user_name
    enabled: true
    # ... more config

# 4. Display Configuration
context_display:
  enabled: true
  header: "📋 User Information:"
  # ...

# 5. Recent Messages Context
recent_messages_context:
  enabled: true
  count: 2

# 6. Model Configuration
model_config:
  temperature: 0.7
  max_turns: 12

# 7. Privacy & Security
privacy:
  data_ttl: 14400  # 4 hours
```

---

## Customizing Agent Personality

### Example: Create a "Tech Support Bot"

Create `config/personalities/tech_support.yaml`:

```yaml
agent_name: "Tech Support Assistant"
agent_version: "2.0"
description: "Helpful technical support chatbot"

system_prompt: |
  You are a patient, knowledgeable technical support assistant.

  🎭 Personality:
  - Patient and understanding
  - Clear step-by-step instructions
  - Uses simple language
  - Asks clarifying questions

  🧠 Smart Memory:
  - Save user's name, device type, OS, issue category
  - Use save_user_info tool silently
  - Never mention data saving

  📋 Context:
  - User information shown at top
  - Use it for personalized support

silent_operation_instructions: |
  ⚠️ NEVER say:
    ❌ "I've saved your device information"

  DO say:
    ✅ "Hi Sarah! Let's fix that Windows issue together."

tool_usage_instructions: |
  Use save_user_info to save:
  - User's name
  - Device type (laptop, phone, etc.)
  - Operating system
  - Issue category

user_data_fields:
  - field_name: name
    normalized_name: user_name
    enabled: true

  - field_name: device
    aliases: [device_type, computer, phone]
    normalized_name: user_device
    description: "User's device type"
    enabled: true

  - field_name: os
    aliases: [operating_system, system]
    normalized_name: user_os
    description: "Operating system"
    enabled: true

  - field_name: issue
    aliases: [problem, category]
    normalized_name: user_issue_category
    description: "Type of technical issue"
    enabled: true

context_display:
  enabled: true
  header: "🔧 User Profile:"
  field_labels:
    user_name: "Name"
    user_device: "Device"
    user_os: "OS"
    user_issue_category: "Issue"

model_config:
  temperature: 0.6  # Lower for more consistent support
  max_turns: 20     # Longer conversations for support

privacy:
  data_ttl: 7200  # 2 hours for support session
```

Use it:
```bash
AGENT_CONFIG_FILE=personalities/tech_support.yaml
docker-compose restart chat-service
```

---

## User Data Fields Configuration

### Field Definition

```yaml
user_data_fields:
  - field_name: hobby           # What LLM will call it
    aliases: [interest, like]   # Alternative names
    normalized_name: user_hobbies  # Internal storage name
    description: "User's hobbies"
    examples:
      - "reading"
      - "gaming"
    data_type: list            # string, integer, or list
    accumulate: true           # For lists: add to existing
    enabled: true              # Can be disabled
    validation:                # Optional validation
      pattern: "regex..."
      min: 1
      max: 100
```

### Data Types

**string:**
```yaml
- field_name: name
  data_type: string
  validation:
    pattern: "^[a-zA-Z]+$"  # Optional regex
```

**integer:**
```yaml
- field_name: age
  data_type: integer
  validation:
    min: 1
    max: 120
```

**list (accumulative):**
```yaml
- field_name: interest
  data_type: list
  accumulate: true  # Adds to existing list
```

### Enable/Disable Fields

```yaml
# Disable a field (won't be extracted)
- field_name: email
  enabled: false

# Enable only essential fields for privacy
user_data_fields:
  - field_name: name
    enabled: true
  - field_name: age
    enabled: false  # Don't collect age
  - field_name: location
    enabled: false  # Don't collect location
```

---

## Context Display Configuration

### Display Modes

**Bullet Format (default):**
```yaml
context_display:
  format: "bullet"
  header: "📋 User Information:"

# Result:
# 📋 User Information:
#   • Name: Mohammad
#   • Age: 25
#   • Location: Tehran
```

**Inline Format:**
```yaml
context_display:
  format: "inline"
  header: "ℹ️ Context:"

# Result:
# ℹ️ Context: Name: Mohammad, Age: 25, Location: Tehran
```

### Custom Field Labels

```yaml
context_display:
  field_labels:
    user_name: "👤 Name"
    user_age: "🎂 Age"
    user_location: "📍 From"
    user_occupation: "💼 Job"
    user_interests: "❤️ Likes"
```

### Disable Context Display

```yaml
context_display:
  enabled: false  # Don't show user info in prompt
```

---

## Recent Messages Configuration

```yaml
recent_messages_context:
  enabled: true
  count: 3           # Show last 3 user messages
  max_length: 200    # Truncate long messages
  header: "💬 Recent:"
```

Example output in system prompt:
```
💬 Recent:
  1. I need help with Python
  2. Specifically asyncio programming
  3. How do I create a task?
```

---

## Model Configuration

```yaml
model_config:
  default_model: "gemini-2.5-flash-lite-preview-09-2025"
  temperature: 0.7  # 0.0-1.0, higher = more creative
  max_turns: 12     # Max conversation turns
  max_tokens: null  # null = no limit
```

**Temperature Guidelines:**
- `0.3-0.5`: Factual, consistent (support, professional)
- `0.6-0.7`: Balanced (default, general chat)
- `0.8-1.0`: Creative, varied (tutoring, storytelling)

---

## Privacy & Security

```yaml
privacy:
  # TTL for user data (seconds)
  data_ttl: 14400  # 4 hours

  # Auto-delete sensitive fields after session
  auto_delete_sensitive_fields: true

  # Mark fields as sensitive
  sensitive_fields:
    - user_email
    - user_phone
    - user_address

  # Require explicit consent for these fields
  require_consent_for:
    - user_email
    - user_phone
```

**TTL Examples:**
- `3600` = 1 hour
- `7200` = 2 hours
- `14400` = 4 hours (default)
- `86400` = 24 hours
- `null` = never expires (not recommended)

---

## Pre-built Personalities

### 1. Default (agent_config.yaml)

**Best for:** General-purpose chatbot
**Collects:** Name, age, location, occupation, interests, language
**Tone:** Friendly, Persian-first
**TTL:** 4 hours

```bash
AGENT_CONFIG_FILE=agent_config.yaml
```

### 2. Professional Assistant

**Best for:** Business, enterprise, customer service
**Collects:** Name, occupation, company, location, email, phone
**Tone:** Formal, professional, efficient
**TTL:** 8 hours

```bash
AGENT_CONFIG_FILE=personalities/professional_assistant.yaml
```

### 3. Friendly Tutor

**Best for:** Education, learning, student support
**Collects:** Name, age, grade, subjects, interests, learning style
**Tone:** Warm, encouraging, uses emojis
**TTL:** 24 hours (for learning continuity)

```bash
AGENT_CONFIG_FILE=personalities/friendly_tutor.yaml
```

### 4. Minimal Assistant

**Best for:** Privacy-focused, minimal data collection
**Collects:** Name (optional), language preference only
**Tone:** Helpful but respect privacy
**TTL:** 1 hour

```bash
AGENT_CONFIG_FILE=personalities/minimal_assistant.yaml
```

---

## Creating Custom Configurations

### Step 1: Copy Template

```bash
cd ai_platform/services/chat-service/config/personalities
cp ../agent_config.yaml my_custom_agent.yaml
```

### Step 2: Edit Configuration

```yaml
agent_name: "My Custom Agent"
agent_version: "1.0"
description: "Your custom agent description"

system_prompt: |
  Your custom personality instructions...

  # Be specific about:
  - How the agent should behave
  - What kind of responses to give
  - When to use save_user_info tool
  - Language preferences

# Customize user_data_fields
user_data_fields:
  - field_name: my_custom_field
    normalized_name: user_custom_field
    description: "Custom field description"
    data_type: string
    enabled: true

# Adjust other settings as needed
```

### Step 3: Use It

```bash
AGENT_CONFIG_FILE=personalities/my_custom_agent.yaml
docker-compose restart chat-service
```

---

## Configuration Validation

The system validates your configuration on startup. Check logs:

```bash
docker-compose logs chat-service
```

**Success:**
```
INFO: Loaded agent config: My Custom Agent v1.0
```

**Error:**
```
ERROR: Failed to load agent config: Missing required field 'system_prompt'
INFO: Falling back to default config
```

---

## Testing Your Configuration

### 1. Test config loading:

```bash
cd ai_platform/services/chat-service
python -c "from agents.config_loader import load_agent_config; config = load_agent_config('agent_config.yaml'); print(f'Loaded: {config.agent_name}')"
```

### 2. List available configs:

```bash
python -c "from agents.config_loader import ConfigLoader; loader = ConfigLoader(); print(loader.list_available_configs())"
```

### 3. Test agent behavior:

```bash
# Start services with your config
AGENT_CONFIG_FILE=personalities/friendly_tutor.yaml docker-compose up chat-service

# In another terminal:
cd ai_platform
python test_tool_based_memory.py
```

---

## Environment Variables

```bash
# .env file

# Choose configuration file
AGENT_CONFIG_FILE=agent_config.yaml

# Can override specific settings
LITELLM_MODEL=gemini-2.5-flash-lite-preview-09-2025
LITELLM_API_KEY=your_key_here

# Session settings (applies to all configs)
MAX_SESSION_MESSAGES=30
SESSION_TTL_SECONDS=14400
```

---

## Advanced: Multiple Agents

You can register multiple agents with different configs:

```python
# In main.py

# Load different configs
default_config = load_agent_config("agent_config.yaml")
tutor_config = load_agent_config("personalities/friendly_tutor.yaml")
professional_config = load_agent_config("personalities/professional_assistant.yaml")

# Register multiple agents
register_agent("default", ChatAgent, {...}, full_config=default_config)
register_agent("tutor", ChatAgent, {...}, full_config=tutor_config)
register_agent("professional", ChatAgent, {...}, full_config=professional_config)
```

Access via different endpoints:
```
POST /chat/default      # Uses default config
POST /chat/tutor        # Uses tutor config
POST /chat/professional # Uses professional config
```

---

## Best Practices

1. **Start with a pre-built personality** - Modify instead of creating from scratch
2. **Test thoroughly** - Ensure your custom config loads without errors
3. **Use descriptive names** - Make field names clear and intuitive
4. **Respect privacy** - Only enable fields you actually need
5. **Set appropriate TTLs** - Balance between context persistence and privacy
6. **Document your changes** - Add comments to your custom config
7. **Version control** - Keep your configs in git
8. **Back up configs** - Before making major changes

---

## Troubleshooting

**Config won't load:**
- Check YAML syntax (indentation, colons, quotes)
- Verify file path is correct
- Check logs for specific error message

**Fields not being extracted:**
- Ensure `enabled: true`
- Check field_name and aliases match what LLM might use
- Verify system_prompt instructs LLM to use the tool

**Agent mentions saving data:**
- Strengthen `silent_operation_instructions`
- Add more examples of what NOT to say
- Lower temperature for more consistent behavior

**Context not displaying:**
- Check `context_display.enabled: true`
- Verify field_labels are defined
- Ensure user data is actually being saved

---

## Summary

The configuration system allows you to:

✅ **Customize personality** - Change how your agent behaves
✅ **Control data collection** - Enable/disable specific fields
✅ **Adjust privacy** - Set TTLs and sensitive field handling
✅ **Modify display** - Change how context is shown
✅ **Fine-tune model** - Adjust temperature, max turns, etc.
✅ **Create multiple agents** - Different personalities for different use cases

**All without changing code** - just edit YAML files!

---

*Implemented: 2025-12-18*
*Author: Claude (AI Assistant)*
