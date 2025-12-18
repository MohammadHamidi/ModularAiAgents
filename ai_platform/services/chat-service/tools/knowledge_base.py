"""
Knowledge Base Tool - Search and retrieve information from a knowledge base.
This is a MOCK implementation - replace with real database/vector search later.
"""
from tools.registry import Tool
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class KnowledgeBaseTool(Tool):
    """Search a knowledge base for information."""
    
    name: str = "knowledge_base_search"
    description: str = """Search the knowledge base for relevant information.
    Use this tool when you need to look up facts, documentation, or stored information.
    Returns relevant articles/documents matching the query."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant information"
            },
            "category": {
                "type": "string",
                "description": "Optional category to filter results (e.g., 'technical', 'general', 'faq')",
                "enum": ["technical", "general", "faq", "tutorial"]
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 3)",
                "default": 3
            }
        },
        "required": ["query"]
    })
    
    async def execute(self, query: str, category: str = None, limit: int = 3) -> str:
        """
        MOCK: Search knowledge base.
        TODO: Replace with real implementation (e.g., vector DB, Elasticsearch)
        """
        # Mock knowledge base responses
        mock_kb = {
            "python": {
                "title": "Python Programming Guide",
                "content": "Python is a high-level programming language known for its simplicity. Key features: easy syntax, extensive libraries, great for beginners.",
                "category": "tutorial"
            },
            "machine learning": {
                "title": "Machine Learning Basics",
                "content": "Machine learning is a subset of AI that enables systems to learn from data. Types: supervised, unsupervised, reinforcement learning.",
                "category": "technical"
            },
            "api": {
                "title": "API Documentation",
                "content": "Our API supports REST endpoints. Base URL: /api/v1/. Authentication: Bearer token required.",
                "category": "technical"
            },
            "pricing": {
                "title": "Pricing FAQ",
                "content": "We offer three plans: Free (limited), Pro ($10/mo), Enterprise (custom). All plans include basic support.",
                "category": "faq"
            },
            "contact": {
                "title": "Contact Information",
                "content": "Email: support@example.com, Phone: +1-234-567-8900, Hours: 9 AM - 5 PM EST",
                "category": "general"
            }
        }
        
        # Simple keyword matching (mock)
        results = []
        query_lower = query.lower()
        
        for key, doc in mock_kb.items():
            if key in query_lower or query_lower in doc["content"].lower():
                if category is None or doc["category"] == category:
                    results.append(doc)
                    if len(results) >= limit:
                        break
        
        if not results:
            return f"[Knowledge Base] No results found for: '{query}'"
        
        # Format results
        formatted = f"[Knowledge Base] Found {len(results)} result(s):\n\n"
        for i, doc in enumerate(results, 1):
            formatted += f"{i}. **{doc['title']}**\n   {doc['content']}\n\n"
        
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

