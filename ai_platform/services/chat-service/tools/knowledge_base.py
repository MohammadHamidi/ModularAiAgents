"""
Knowledge Base Tool - Query LightRAG Server for information.
"""
import os
import httpx
from tools.registry import Tool
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class KnowledgeBaseTool(Tool):
    """Query the LightRAG knowledge base for information."""
    
    name: str = "knowledge_base_query"
    description: str = """Query the LightRAG knowledge base for factual, product-specific, internal, or document-grounded information.
    Use this tool when you need to look up information from documents, SOPs, specs, meeting notes, configs, features, pricing, roadmap, policies, or domain text.
    Returns relevant information with source citations."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant information (minimum 3 characters)"
            },
            "mode": {
                "type": "string",
                "description": "Retrieval mode",
                "enum": ["mix", "hybrid", "local", "global", "naive", "bypass"],
                "default": "mix"
            },
            "include_references": {
                "type": "boolean",
                "description": "Include source references in response",
                "default": True
            },
            "include_chunk_content": {
                "type": "boolean",
                "description": "Include raw chunk content (for evaluation/debug only)",
                "default": False
            },
            "response_type": {
                "type": "string",
                "description": "Format of the response",
                "enum": ["Bullet Points", "Single Paragraph", "Multiple Paragraphs"],
                "default": "Multiple Paragraphs"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top results to retrieve",
                "default": 10
            },
            "chunk_top_k": {
                "type": "integer",
                "description": "Number of top chunks per result",
                "default": 8
            },
            "max_total_tokens": {
                "type": "integer",
                "description": "Maximum total tokens in response",
                "default": 6000
            },
            "conversation_history": {
                "type": "array",
                "description": "Optional conversation history for context",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"}
                    }
                }
            }
        },
        "required": ["query"]
    })
    
    def __post_init__(self):
        """Initialize LightRAG configuration from environment variables."""
        self.base_url = os.getenv("LIGHTRAG_BASE_URL", "").rstrip("/")
        self.username = os.getenv("LIGHTRAG_USERNAME")
        self.password = os.getenv("LIGHTRAG_PASSWORD")
        self.api_key = os.getenv("LIGHTRAG_API_KEY_HEADER_VALUE")
        self.bearer_token = os.getenv("LIGHTRAG_BEARER_TOKEN")
        self._cached_token = None
    
    async def _get_auth_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get authentication token using OAuth2 password flow if needed."""
        if self.bearer_token:
            return self.bearer_token
        
        if self._cached_token:
            return self._cached_token
        
        if self.username and self.password:
            try:
                response = await client.post(
                    f"{self.base_url}/login",
                    data={
                        "username": self.username,
                        "password": self.password
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    self._cached_token = data.get("access_token")
                    return self._cached_token
            except Exception:
                pass
        
        return None
    
    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to LightRAG API."""
        if not self.base_url:
            return {"error": "LIGHTRAG_BASE_URL not configured"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            params = {}
            
            # Try bearer token first
            token = await self._get_auth_token(client)
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Try API key as query param
            if self.api_key and not token:
                params["api_key_header_value"] = self.api_key
            
            # If no auth method, try /auth-status for guest token
            if not token and not self.api_key:
                try:
                    auth_status = await client.get(f"{self.base_url}/auth-status", timeout=5.0)
                    if auth_status.status_code == 200:
                        guest_token = auth_status.json().get("guest_token")
                        if guest_token:
                            headers["Authorization"] = f"Bearer {guest_token}"
                except Exception:
                    pass
            
            try:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=headers,
                    params=params if params else None,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
            except httpx.RequestError as e:
                return {"error": f"Request failed: {str(e)}"}
            except Exception as e:
                return {"error": f"Unexpected error: {str(e)}"}
    
    async def execute(
        self,
        query: str,
        mode: str = "mix",
        include_references: bool = True,
        include_chunk_content: bool = False,
        response_type: str = "Multiple Paragraphs",
        top_k: int = 10,
        chunk_top_k: int = 8,
        max_total_tokens: int = 6000,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Execute LightRAG query."""
        if len(query.strip()) < 3:
            return "[Knowledge Base] Error: Query must be at least 3 characters"
        
        payload = {
            "query": query.strip(),
            "mode": mode,
            "include_references": include_references,
            "include_chunk_content": include_chunk_content,
            "response_type": response_type,
            "top_k": top_k,
            "chunk_top_k": chunk_top_k,
            "max_total_tokens": max_total_tokens
        }
        
        if conversation_history:
            payload["conversation_history"] = conversation_history
        
        result = await self._make_request("/query", payload)
        
        if "error" in result:
            error_msg = result['error']
            if "LIGHTRAG_BASE_URL not configured" in error_msg:
                return "[Knowledge Base] UNAVAILABLE: LightRAG server is not configured. Please configure LIGHTRAG_BASE_URL environment variable. I cannot access the Knowledge Base to answer this question."
            elif "timeout" in error_msg.lower() or "Request failed" in error_msg:
                return "[Knowledge Base] UNAVAILABLE: Could not access the Knowledge Base (timeout/connection error). I cannot retrieve information from the Knowledge Base at this time."
            else:
                return f"[Knowledge Base] UNAVAILABLE: {error_msg}. I cannot access the Knowledge Base to answer this question."
        
        # Format response
        response_text = result.get("response", "")
        references = result.get("references", [])
        
        formatted = response_text
        
        # Add citations if references exist
        if references and include_references:
            formatted += "\n\nSources: "
            citation_parts = []
            for i, ref in enumerate(references, 1):
                file_path = ref.get("file_path", ref.get("path", "unknown"))
                citation_parts.append(f"[{i}] {file_path}")
            formatted += ", ".join(citation_parts)
        
        return formatted


@dataclass  
class GetLearningResourceTool(Tool):
    """Get learning resources for educational topics."""
    
    name: str = "get_learning_resource"
    description: str = """Get learning resources for a specific topic.
    Use this when students ask for tutorials, exercises, or learning materials."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic to find resources for"
            },
            "level": {
                "type": "string",
                "description": "Difficulty level",
                "enum": ["beginner", "intermediate", "advanced"]
            },
            "type": {
                "type": "string",
                "description": "Type of resource",
                "enum": ["tutorial", "exercise", "video", "book"]
            }
        },
        "required": ["topic"]
    })
    
    async def execute(self, topic: str, level: str = "beginner", type: str = "tutorial") -> str:
        """MOCK: Get learning resources."""
        # Mock responses
        resources = {
            "python": {
                "beginner": "📚 Recommended: 'Python Crash Course' book, Codecademy Python course",
                "intermediate": "📚 Recommended: 'Fluent Python', Real Python tutorials",
                "advanced": "📚 Recommended: 'Python Cookbook', Contributing to open source"
            },
            "math": {
                "beginner": "📚 Khan Academy - Basic Math, Math is Fun website",
                "intermediate": "📚 Khan Academy - Algebra & Geometry, PatrickJMT videos",
                "advanced": "📚 MIT OpenCourseWare, 3Blue1Brown videos"
            }
        }
        
        topic_lower = topic.lower()
        for key, levels in resources.items():
            if key in topic_lower:
                return f"[Learning Resources for {topic}]\n{levels.get(level, levels['beginner'])}"
        
        return f"[Learning Resources] Generic recommendation for {topic} ({level}): Search YouTube tutorials, Coursera courses, or relevant books."

