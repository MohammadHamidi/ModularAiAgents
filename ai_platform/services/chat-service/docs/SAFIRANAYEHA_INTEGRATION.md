# Safiranayeha Website Integration Guide

This document describes how to integrate the AI chat interface with the Safiranayeha website.

---

## Overview

The chat service provides intelligent AI agents that can be embedded into the Safiranayeha website. When a user clicks on an AI link, they are redirected to the chat interface with their context automatically loaded and the appropriate AI agent selected based on which page they came from.

---

## Integration Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User clicks AI button on Safiranayeha website           │
│    (e.g., on /konesh/list page)                            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Safiranayeha encrypts user data                         │
│    Encrypted JSON: {UserId: "123", Path: "/konesh/list"}   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Redirect to chat interface with encrypted parameter      │
│    https://chat.example.com/{AES_JSON_QUERY_PARAM}         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Chat interface calls POST /chat/init                    │
│    Request: {encrypted_param: "..."}                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Chat service processes:                                  │
│    - Decrypts parameter → UserId + Path                    │
│    - Fetches user data from Safiranayeha API               │
│    - Maps Path to appropriate AI agent                     │
│    - Creates session with pre-loaded context               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Returns: {session_id, agent_key, user_data, welcome}    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Chat interface starts conversation with selected agent   │
│    All subsequent messages go to POST /chat/{agent_key}    │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Provide Chat Interface URL

You need to provide a URL that will host the chat interface. This URL should accept a path parameter for the encrypted data.

**Example URL format:**
```
https://chat.safiranayeha.ir/{AES_JSON_QUERY_PARAM}
```

Where `{AES_JSON_QUERY_PARAM}` is the encrypted parameter containing user information.

---

### Step 2: Encrypt User Data (Safiranayeha Website)

When a user clicks on an AI link, the Safiranayeha website should encrypt the user's information using AES encryption.

#### Encryption Parameters:

- **Algorithm**: AES (CBC mode)
- **Key**: `DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg` (32 bytes)
- **IV**: `nqcWgiLLZWJaFkZi` (16 bytes)
- **Output**: Base64 encoded, then URL encoded

#### JSON Data to Encrypt:

```json
{
  "UserId": "user_123",
  "Path": "/konesh/list"
}
```

**Fields:**
- `UserId`: User ID from your database
- `Path`: The page path where the user clicked the AI button

#### C# Example (from requirements):

```csharp
private static readonly string Key = "DLwXJz9yzC7Kk2J1M0Brp7snLTUEY1Fg";
private static readonly string IV = "nqcWgiLLZWJaFkZi";

public static string Encrypt<T>(T data)
{
    string json = JsonSerializer.Serialize(data);

    using var aes = Aes.Create();
    aes.Key = Encoding.UTF8.GetBytes(Key);
    aes.IV = Encoding.UTF8.GetBytes(IV);

    using var ms = new MemoryStream();
    using var cs = new CryptoStream(ms, aes.CreateEncryptor(), CryptoStreamMode.Write);
    using var sw = new StreamWriter(cs);
    sw.Write(json);
    sw.Flush();
    cs.FlushFinalBlock();

    byte[] encrypted = ms.ToArray();
    string base64 = Convert.ToBase64String(encrypted);
    return HttpUtility.UrlEncode(base64);
}
```

---

### Step 3: Redirect to Chat Interface

After encrypting the data, redirect the user to the chat interface URL with the encrypted parameter:

```
https://chat.safiranayeha.ir/{encrypted_param}
```

---

### Step 4: Chat Interface Initialization

The chat interface should:

1. Extract the encrypted parameter from the URL
2. Call the `/chat/init` endpoint
3. Receive session_id and agent_key
4. Start the conversation

#### JavaScript Example:

```javascript
// Extract encrypted parameter from URL path
const encryptedParam = window.location.pathname.substring(1); // Remove leading '/'

// Initialize chat session
async function initChat() {
  try {
    const response = await fetch('https://api.example.com/chat/init', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        encrypted_param: encryptedParam
      })
    });

    const data = await response.json();

    // data contains:
    // - session_id: Use for all subsequent chat messages
    // - agent_key: The AI agent assigned based on path
    // - user_data: User information (optional)
    // - welcome_message: Initial greeting (optional)

    console.log('Chat initialized:', data);

    // Store session info
    sessionStorage.setItem('chat_session_id', data.session_id);
    sessionStorage.setItem('chat_agent_key', data.agent_key);

    // Display welcome message
    if (data.welcome_message) {
      displayMessage('assistant', data.welcome_message);
    }

    // Enable chat input
    enableChatInput();

  } catch (error) {
    console.error('Failed to initialize chat:', error);
    displayError('خطا در برقراری ارتباط با سرور');
  }
}

// Call on page load
initChat();
```

---

### Step 5: Send Chat Messages

After initialization, send chat messages using the regular chat endpoint:

```javascript
async function sendMessage(userMessage) {
  const sessionId = sessionStorage.getItem('chat_session_id');
  const agentKey = sessionStorage.getItem('chat_agent_key');

  try {
    const response = await fetch(`https://api.example.com/chat/${agentKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: sessionId,
        use_shared_context: true  // Use loaded user data
      })
    });

    const data = await response.json();

    // Display AI response
    displayMessage('assistant', data.output);

  } catch (error) {
    console.error('Failed to send message:', error);
  }
}
```

---

### Step 6: Streaming Support (Optional)

For a better user experience, you can use the streaming endpoint:

```javascript
async function sendMessageStreaming(userMessage) {
  const sessionId = sessionStorage.getItem('chat_session_id');
  const agentKey = sessionStorage.getItem('chat_agent_key');

  const response = await fetch(`https://api.example.com/chat/${agentKey}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: userMessage,
      session_id: sessionId,
      use_shared_context: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentMessage = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.substring(6));

        if (data.chunk) {
          currentMessage += data.chunk;
          updateStreamingMessage(currentMessage);
        } else if (data.done) {
          finalizeMessage(currentMessage);
        }
      }
    }
  }
}
```

---

## API Endpoints

### POST /chat/init

Initialize chat session from encrypted parameter.

**Request:**
```json
{
  "encrypted_param": "base64_url_encoded_string"
}
```

**Alternative (for testing):**
```json
{
  "user_id": "123",
  "path": "/konesh/list"
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "agent_key": "action_expert",
  "user_data": {
    "fullName": "علی احمدی",
    "phoneNumber": "09123456789",
    "score": 150,
    ...
  },
  "welcome_message": "سلام! برای تولید محتوای کنش‌ها آماده‌ام. چه کنشی مد نظرته؟"
}
```

### GET /safiranayeha/path-mappings

Get all path-to-agent mappings.

**Response:**
```json
{
  "default_agent": "orchestrator",
  "mappings": [
    {
      "path": "/konesh/*",
      "agent": "action_expert",
      "description": "Action/Konesh pages - content creation"
    },
    ...
  ],
  "total_mappings": 15
}
```

### POST /safiranayeha/test-decrypt

Test decryption of encrypted parameter (for debugging).

**Request:**
```
encrypted_param=base64_url_encoded_string
```

**Response:**
```json
{
  "success": true,
  "decrypted": {
    "UserId": "123",
    "Path": "/konesh/list"
  }
}
```

---

## Path-to-Agent Mapping

The system automatically selects the appropriate AI agent based on the page path:

| Path Pattern | Agent | Purpose |
|--------------|-------|---------|
| `/` | `guest_faq` | Homepage - newcomer guide |
| `/faq` | `guest_faq` | FAQ page |
| `/konesh/*` | `action_expert` | Action/content creation |
| `/actions/*` | `action_expert` | Action pages |
| `/profile/*` | `journey_register` | Profile completion |
| `/rewards/*` | `rewards_invite` | Rewards & points |
| `/invite/*` | `rewards_invite` | Invitation system |
| (any other) | `orchestrator` | Default router agent |

You can view the complete mapping by calling `GET /safiranayeha/path-mappings`.

---

## User Data Fetching

The chat service automatically fetches user data from the Safiranayeha API:

### Authentication:

- **Endpoint**: `https://api.safiranayeha.ir/api/AI/AILogin`
- **Method**: Automatically attempts multiple methods (GET with query params, POST with JSON body, POST with form data, POST with query params)
- **Credentials**:
  - Username: `AI`
  - Password: `2025@GmAiL.com`
- **Returns**: JWT token
- **Note**: The client automatically tries different HTTP methods to ensure compatibility with the API

### User Data Retrieval:

- **Endpoint**: `https://api.safiranayeha.ir/api/AI/GetAIUserData`
- **Method**: GET
- **Parameters**: `UserId={user_id}`
- **Headers**: `Authorization: Bearer {token}`
- **Returns**: User data object

The fetched data is automatically saved to the chat session context and made available to all agents.

---

## Configuration

### Adding New Path Mappings

Edit `/config/path_agent_mapping.yaml`:

```yaml
mappings:
  - path: "/new-page/*"
    agent: "action_expert"
    description: "New page description"
```

Restart the service to apply changes.

### Customizing Welcome Messages

Edit the welcome messages in `main.py` (around line 695):

```python
if agent_key == "action_expert":
    welcome_message = "Your custom welcome message here"
```

---

## Testing

### 1. Test Decryption

Use the test endpoint to verify encryption/decryption:

```bash
curl -X POST "https://api.example.com/safiranayeha/test-decrypt" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "encrypted_param=YOUR_ENCRYPTED_STRING"
```

### 2. Test Path Mapping

Check path-to-agent mappings:

```bash
curl "https://api.example.com/safiranayeha/path-mappings"
```

### 3. Test Chat Initialization

Test with direct parameters (without encryption):

```bash
curl -X POST "https://api.example.com/chat/init" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_123",
    "path": "/konesh/list"
  }'
```

---

## Troubleshooting

### Common Issues:

**1. Decryption Fails**
- Verify AES key and IV are correct
- Check that Base64 encoding is proper
- Ensure URL encoding is applied

**2. User Data Not Loaded**
- Check Safiranayeha API credentials
- Verify API endpoints are accessible
- Check logs for API errors

**3. Wrong Agent Selected**
- Verify path in encrypted parameter
- Check path mapping configuration
- Review `/safiranayeha/path-mappings` endpoint

**4. Session Not Persisting**
- Ensure session_id is being stored and sent with each message
- Verify database connection is working

---

## Security Notes

1. **HTTPS Only**: Always use HTTPS in production
2. **Token Expiration**: JWT tokens expire after 1 hour (automatically refreshed)
3. **Encryption Keys**: Keep AES keys secure (currently hardcoded, consider moving to environment variables)
4. **CORS**: Configure CORS properly for production

---

## Support

For issues or questions, check:
- API documentation: `/doc` endpoint
- Health check: `GET /health`
- Logs: Check service logs for detailed error messages

---

## Complete Example

See `examples/safiranayeha_integration_example.html` for a complete working example of the frontend integration.
