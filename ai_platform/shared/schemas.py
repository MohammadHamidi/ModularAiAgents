from pydantic import BaseModel
from typing import List, Dict, Any

class ServiceInfo(BaseModel):
    name: str
    version: str
    capabilities: List[str]
    agents: List[str]

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str | None = None

class SessionData(BaseModel):
    session_id: str
    agent_type: str
    messages: List[Dict]
    metadata: Dict[str, Any] = {}