"""
Knowledge Base Tool - Query LightRAG Server for information.
"""
import os
import logging
import httpx
import asyncio
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
                "description": "Retrieval mode (recommended: 'mix' for best results)",
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
            },
            "only_need_context": {
                "type": "boolean",
                "description": "Only return context without LLM-generated response",
                "default": False
            },
            "only_need_prompt": {
                "type": "boolean",
                "description": "Only return prompt without executing query",
                "default": False
            }
        },
        "required": ["query"]
    })
    
    def __post_init__(self):
        """Initialize LightRAG configuration from environment variables."""
        self.base_url = os.getenv("LIGHTRAG_BASE_URL", "").rstrip("/")
        self.username = os.getenv("LIGHTRAG_USERNAME")
        self.password = os.getenv("LIGHTRAG_PASSWORD")
        self.api_key = os.getenv("LIGHTRAG_API_KEY_HEADER_VALUE") or os.getenv("LIGHTRAG_API_KEY")
        self.bearer_token = os.getenv("LIGHTRAG_BEARER_TOKEN")
        self.workspace = os.getenv("LIGHTRAG_WORKSPACE")
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
    
    async def _make_request(self, endpoint: str, payload: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """Make authenticated request to LightRAG API with retry mechanism."""
        if not self.base_url:
            return {"error": "LIGHTRAG_BASE_URL not configured"}
        
        # Retry configuration
        retry_delays = [1.0, 2.0, 4.0]  # Exponential backoff: 1s, 2s, 4s
        
        for attempt in range(max_retries):
            if attempt > 0:
                logging.info(f"LightRAG retry attempt {attempt + 1}/{max_retries} for endpoint {endpoint}")
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {}
                    params = {}
                    
                    # Try bearer token first
                    token = await self._get_auth_token(client)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    
                    # Try API key header (X-API-Key as per LightRAG docs)
                    if self.api_key and not token:
                        headers["X-API-Key"] = self.api_key
                    
                    # Add workspace header if configured (for multi-workspace support)
                    if self.workspace:
                        headers["LIGHTRAG-WORKSPACE"] = self.workspace
                    
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
                    
                    response = await client.post(
                        f"{self.base_url}{endpoint}",
                        json=payload,
                        headers=headers,
                        params=params if params else None,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Log if response is empty or malformed (only for full responses, not context-only)
                    if not payload.get("only_need_context") and not payload.get("only_need_prompt"):
                        if not result.get("response"):
                            logging.warning(f"LightRAG query returned empty response for query: {payload.get('query', '')[:50]}")
                            logging.debug(f"LightRAG response: {result}")
                    else:
                        # For context-only queries, log what we got
                        context = result.get("response", result.get("context", ""))
                        if context:
                            logging.debug(f"LightRAG context retrieved: {len(context)} chars, {len(result.get('references', []))} references")
                        else:
                            logging.warning(f"LightRAG context-only query returned no context for: {payload.get('query', '')[:50]}")
                    
                    return result
            except httpx.HTTPStatusError as e:
                # Don't retry on client errors (4xx), only on server errors (5xx)
                if e.response.status_code < 500:
                    logging.error(f"LightRAG HTTP error {e.response.status_code}: {e.response.text}")
                    return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
                
                # Server error - retry
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                    logging.warning(f"LightRAG HTTP error {e.response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logging.error(f"LightRAG HTTP error {e.response.status_code} after {max_retries} attempts: {e.response.text}")
                    return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
            except httpx.RequestError as e:
                # Network/connection errors - retry
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                    logging.warning(f"LightRAG request error, retrying in {delay}s (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logging.error(f"LightRAG request error after {max_retries} attempts: {str(e)}")
                    return {"error": f"Request failed: {str(e)}"}
            except Exception as e:
                # Unexpected errors - retry
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                    logging.warning(f"LightRAG unexpected error, retrying in {delay}s (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logging.error(f"LightRAG unexpected error after {max_retries} attempts: {str(e)}")
                    return {"error": f"Unexpected error: {str(e)}"}
        
        # Should not reach here, but just in case
        return {"error": "Request failed after all retries"}
    
    async def execute(
        self,
        query: str,
        mode: str = "mix",
        include_references: bool = True,
        include_chunk_content: bool = True,
        response_type: str = "Multiple Paragraphs",
        top_k: int = 10,
        chunk_top_k: int = 8,
        max_total_tokens: int = 6000,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        only_need_context: bool = True,
        only_need_prompt: bool = False
    ) -> str:
        """Execute LightRAG query."""
        if len(query.strip()) < 3:
            return "[Knowledge Base] Error: Query must be at least 3 characters"
        
        payload = {
            "query": query.strip(),
            "mode": mode,
            "only_need_context": only_need_context,
            "include_references": include_references,
            "include_chunk_content": include_chunk_content,
            "top_k": top_k
        }
        
        # Only include these fields if not using only_need_context
        if not only_need_context:
            payload.update({
                "response_type": response_type,
                "chunk_top_k": chunk_top_k,
                "max_total_tokens": max_total_tokens,
                "only_need_prompt": only_need_prompt
            })
        
        if conversation_history:
            payload["conversation_history"] = conversation_history
        
        # Log the key parameters being used
        logging.info(f"LightRAG query: mode={mode}, only_need_context={only_need_context}, only_need_prompt={only_need_prompt}, query_length={len(query.strip())}")
        
        result = await self._make_request("/query", payload)
        
        if "error" in result:
            error_msg = result['error']
            if "LIGHTRAG_BASE_URL not configured" in error_msg:
                return "[Knowledge Base] UNAVAILABLE: LightRAG server is not configured. Please configure LIGHTRAG_BASE_URL environment variable. I cannot access the Knowledge Base to answer this question."
            elif "timeout" in error_msg.lower() or "Request failed" in error_msg:
                return "[Knowledge Base] UNAVAILABLE: Could not access the Knowledge Base (timeout/connection error). I cannot retrieve information from the Knowledge Base at this time."
            else:
                return f"[Knowledge Base] UNAVAILABLE: {error_msg}. I cannot access the Knowledge Base to answer this question."
        
        # Handle different response types based on parameters
        if only_need_prompt:
            # Return only the prompt if requested
            prompt = result.get("prompt", "")
            if prompt:
                return f"[Knowledge Base Prompt]\n{prompt}"
            else:
                return "[Knowledge Base] No prompt returned from knowledge base."
        
        if only_need_context:
            # Return only context without LLM-generated response
            # When only_need_context=true, LightRAG returns context in the "response" field
            context = result.get("response", result.get("context", ""))
            references = result.get("references", [])
            
            if context:
                formatted = f"[Knowledge Base Context]\n{context}"
                # Add citations if references exist
                if references and include_references:
                    formatted += "\n\nSources: "
                    citation_parts = []
                    for i, ref in enumerate(references, 1):
                        # Handle different reference formats
                        if isinstance(ref, str):
                            citation_parts.append(f"[{i}] {ref}")
                        elif isinstance(ref, dict):
                            file_path = ref.get("file_path", ref.get("path", ref.get("source", "unknown")))
                            citation_parts.append(f"[{i}] {file_path}")
                        else:
                            citation_parts.append(f"[{i}] {str(ref)}")
                    formatted += ", ".join(citation_parts)
                return formatted
            else:
                return "[Knowledge Base] No context returned from knowledge base."
        
        # Format normal response
        response_text = result.get("response", "")
        references = result.get("references", [])
        
        # Check if response is empty or just whitespace
        if not response_text or not response_text.strip():
            # Check if there are references but no response text
            if references:
                return "[Knowledge Base] No detailed response found, but references are available. The knowledge base may not have detailed information about this topic."
            else:
                return "[Knowledge Base] No information found in the knowledge base for this query. The knowledge base does not contain relevant information about this topic."
        
        formatted = response_text.strip()
        
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

