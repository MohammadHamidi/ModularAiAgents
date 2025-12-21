# AI Platform Service Summary - سفیران آیه ها

## Overview

This AI Platform provides intelligent conversational services for the **سفیران آیه ها** (Safiran Ayat) website, enabling users to interact with specialized AI agents that help with Quranic education, religious activities, and community engagement.

## Service Architecture

The platform consists of two main services:

### 1. Gateway Service
- **Purpose**: Entry point for all API requests and UI serving
- **Key Features**:
  - Routes requests to backend chat services
  - Serves the Chat UI interface at `/ui`
  - Provides comprehensive API documentation at `/doc`
  - Health monitoring and service status

### 2. Chat Service
- **Purpose**: Core AI agent processing and conversation management
- **Key Features**:
  - Multiple AI personas (default, tutor, professional, minimal, translator)
  - Session management with conversation history
  - User data persistence and context sharing
  - Knowledge base integration (LightRAG)
  - Tool ecosystem for extended capabilities

## Core Capabilities

### 🤖 Multiple AI Agents
- **Default Agent**: General-purpose assistant for Quranic topics
- **Tutor Agent**: Educational support for teachers and students
- **Professional Agent**: Advanced assistance for content creators
- **Minimal Agent**: Lightweight interactions
- **Translator Agent**: Language translation services

### 📚 Knowledge Base Integration
- Connected to LightRAG knowledge base (`safiranlighrag.bedooncode.ir`)
- Retrieves factual information about:
  - Quranic verses and interpretations
  - Religious activities and programs
  - School and mosque activities
  - Social media content guidelines
  - Campaign information

### 🛠️ Available Tools
- **Knowledge Base Query**: Search internal documents and resources
- **Learning Resources**: Educational materials and tutorials
- **Calculator**: Mathematical operations
- **Weather**: Location-based weather information
- **Web Search**: Internet information retrieval
- **Company Info**: Business information lookup

### 💬 Conversation Features
- **Session Management**: Persistent conversations across multiple interactions
- **Context Sharing**: User information shared across all agents
- **User Data Persistence**: Stores user profile information (name, location, preferences, activities)
- **Follow-up Suggestions**: AI-generated contextual questions to guide users
- **Multi-agent Support**: Switch between different agents while maintaining context

### 📊 User Data Management
The platform tracks and manages:
- **Personal Information**: Name, phone number, gender, birth date
- **Location**: Province and city
- **Activities**: Registered actions, scores, pending reports, achievements
- **Saved Content**: Bookmarked actions and content

## API Endpoints

### Agent Endpoints
- `GET /agents` - List all available agents
- `GET /personas` - List all chat personas with configurations
- `POST /chat/{agent_key}` - Send messages to specific agents

### Tool Endpoints
- `GET /tools` - List all available tools
- `GET /tools/{tool_name}` - Get detailed tool information

### Session Endpoints
- `GET /session/{session_id}/context` - Get session context
- `GET /session/{session_id}/user-data` - Get user data
- `DELETE /session/{session_id}` - Delete session

### UI & Health
- `GET /ui` - Chat interface
- `GET /health` - Service health check
- `GET /doc` - API documentation (Swagger)

## Integration with Safiran Website

This service powers the AI chat functionality on the Safiran Ayat website, enabling:

1. **Interactive Q&A**: Users can ask questions about Quranic verses, religious activities, and platform features
2. **Activity Guidance**: Get help with school activities, mosque programs, and home-based religious activities
3. **Content Creation**: Assistance with social media posts, speeches, and educational materials
4. **Personalized Experience**: AI remembers user information and preferences across conversations
5. **Multi-channel Support**: Different agents for different user roles (teachers, parents, preachers, students)

## Technical Stack

- **Framework**: FastAPI (Python)
- **AI Models**: LiteLLM with Gemini 2.5 Flash Lite
- **Database**: PostgreSQL (async with asyncpg)
- **Knowledge Base**: LightRAG integration
- **Deployment**: Docker containers orchestrated via Docker Compose
- **Documentation**: OpenAPI/Swagger at `/doc`

## Deployment

The service is designed for deployment on Coolify with:
- External PostgreSQL database
- Environment variable configuration
- Health checks for service monitoring
- CORS support for web integration
- Static file serving for UI components

---

**For detailed API documentation, visit `/doc` endpoint after deployment.**

