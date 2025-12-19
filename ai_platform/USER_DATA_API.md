# User Data API Documentation

## Overview

The User Data API allows you to send user information from your app directly in chat requests. This data is saved immediately and made available to all AI agents in the session.

## User Data Schema

### 📋 Personal Information (اطلاعات فردی)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `phone_number` | string | شماره همراه | `"09123456789"` |
| `full_name` | string | نام و نام خانوادگی | `"محمد احمدی"` |
| `gender` | string | جنسیت | `"مرد"` or `"زن"` |
| `birth_month` | integer | ماه تولد | `5` (1-12) |
| `birth_year` | integer | سال تولد | `1995` |

### 🏠 Residence Information (اطلاعات محل سکونت)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `province` | string | استان | `"تهران"` |
| `city` | string | شهر | `"تهران"` |

### 🎯 Activity Information (اطلاعات Activities)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `registered_actions` | integer | کنش ثبت شده | `15` |
| `score` | integer | امتیاز | `1250` |
| `pending_reports` | integer | در انتظار ثبت گزارش | `2` |
| `level` | string | سطح من | `"intermediate"` |
| `my_actions` | array | کنش های من | `["action1", "action2"]` |
| `saved_actions` | array | کنش های ذخیره شده | `["saved1"]` |
| `saved_content` | array | محتوای ذخیره شده | `["content1", "content2"]` |
| `achievements` | array | دستاوردها | `["achievement1", "achievement2"]` |

## API Endpoints

### 1. Send User Data with Chat Request

**POST** `/chat/{agent_key}`

Send user data in the request body along with your message.

```json
{
  "message": "سلام!",
  "session_id": null,
  "use_shared_context": true,
  "user_data": {
    "phone_number": "09123456789",
    "full_name": "محمد احمدی",
    "gender": "مرد",
    "birth_month": 5,
    "birth_year": 1995,
    "province": "تهران",
    "city": "تهران",
    "registered_actions": 15,
    "score": 1250,
    "pending_reports": 2,
    "level": "intermediate",
    "my_actions": ["action1", "action2"],
    "saved_actions": ["saved1"],
    "saved_content": ["content1", "content2"],
    "achievements": ["achievement1", "achievement2"]
  }
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "output": "Agent response...",
  "metadata": {...},
  "context_updates": {...}
}
```

### 2. Get User Data by Session

**GET** `/session/{session_id}/user-data`

Retrieve all user data for a session in organized format.

**Response:**
```json
{
  "session_id": "uuid-here",
  "personal_info": {
    "phone_number": "09123456789",
    "full_name": "محمد احمدی",
    "gender": "مرد",
    "birth_month": 5,
    "birth_year": 1995
  },
  "residence_info": {
    "province": "تهران",
    "city": "تهران"
  },
  "activity_info": {
    "registered_actions": 15,
    "score": 1500,
    "pending_reports": 2,
    "level": "intermediate",
    "my_actions": ["action1", "action2"],
    "saved_actions": ["saved1"],
    "saved_content": ["content1", "content2"],
    "achievements": ["achievement1", "achievement2"]
  },
  "all_data": {
    // Complete flat structure
  }
}
```

### 3. Get Full Context

**GET** `/session/{session_id}/context`

Get all context data (includes user_data + extracted info from conversations).

## Usage Examples

### Example 1: Create Session with Full User Data

```bash
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{
    "message": "سلام!",
    "session_id": null,
    "use_shared_context": true,
    "user_data": {
      "phone_number": "09123456789",
      "full_name": "محمد احمدی",
      "gender": "مرد",
      "birth_month": 5,
      "birth_year": 1995,
      "province": "تهران",
      "city": "تهران",
      "score": 1250,
      "level": "intermediate"
    }
  }'
```

### Example 2: Update Partial User Data

```bash
curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{
    "message": "امتیازم رو به 1500 تغییر بده",
    "session_id": "existing-session-id",
    "use_shared_context": true,
    "user_data": {
      "score": 1500
    }
  }'
```

### Example 3: Fetch User Data

```bash
curl http://localhost:8001/session/{session_id}/user-data | jq .
```

### Example 4: Use with Different Personas

All personas in the same session share the same user_data:

```bash
# First message with DEFAULT persona
SESSION=$(curl -X POST http://localhost:8001/chat/default \
  -H "Content-Type: application/json" \
  -d '{
    "message": "سلام",
    "user_data": {"full_name": "محمد احمدی", "score": 1250}
  }' | jq -r '.session_id')

# Switch to TUTOR persona - has access to same data
curl -X POST http://localhost:8001/chat/tutor \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"اسمم چیه و چند امتیاز دارم؟\",
    \"session_id\": \"$SESSION\",
    \"use_shared_context\": true
  }"
```

## Key Features

✅ **Immediate Save**: User data is saved immediately when sent in request  
✅ **Cross-Persona Access**: All AI agents in same session can access the data  
✅ **Partial Updates**: Send only fields you want to update  
✅ **Organized Response**: GET endpoint returns data organized by categories  
✅ **Persistent**: Data persists across all messages in the session  

## Field Mapping

The system automatically maps between app field names and internal normalized names:

| App Field | Internal Field |
|-----------|----------------|
| `phone_number` | `user_phone` |
| `full_name` | `user_full_name` |
| `gender` | `user_gender` |
| `birth_month` | `user_birth_month` |
| `birth_year` | `user_birth_year` |
| `province` | `user_province` |
| `city` | `user_city` |
| `score` | `user_score` |
| `level` | `user_level` |
| ... | ... |

## Notes

- All user_data fields are optional - send only what you have
- Arrays (my_actions, saved_actions, etc.) are merged, not replaced
- Integer fields (score, registered_actions) are replaced with new values
- Data is available immediately to all agents after saving
- Use `use_shared_context: true` to ensure data is loaded

