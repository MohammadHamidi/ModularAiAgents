"""
Tool Registry - Manages tools for AI agents.
Each persona can have different sets of tools.
"""
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Tool(ABC):
    """Base class for all tools."""
    name: str
    description: str
    enabled: bool = True
    
    # Parameters schema for the tool (OpenAI function format)
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": []
    })
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters."""
        pass
    
    def get_function_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible function schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class ToolRegistry:
    """Registry to manage tools for different personas."""
    
    # Global registry of all available tools
    _available_tools: Dict[str, Tool] = {}
    
    # Per-persona tool assignments
    _persona_tools: Dict[str, List[str]] = {}
    
    @classmethod
    def register_tool(cls, tool: Tool):
        """Register a tool globally."""
        cls._available_tools[tool.name] = tool
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return cls._available_tools.get(name)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """List all available tool names."""
        return list(cls._available_tools.keys())
    
    @classmethod
    def assign_tools_to_persona(cls, persona_key: str, tool_names: List[str]):
        """Assign specific tools to a persona."""
        cls._persona_tools[persona_key] = tool_names
    
    @classmethod
    def get_persona_tools(cls, persona_key: str) -> List[Tool]:
        """Get tools assigned to a persona."""
        tool_names = cls._persona_tools.get(persona_key, [])
        return [cls._available_tools[name] for name in tool_names if name in cls._available_tools]
    
    @classmethod
    def get_all_tools(cls) -> Dict[str, Tool]:
        """Get all registered tools."""
        return cls._available_tools.copy()


# Default tool assignments for personas
DEFAULT_PERSONA_TOOLS = {
    "default": ["knowledge_base_search", "calculator"],
    "tutor": ["knowledge_base_search", "calculator", "get_learning_resource"],
    "professional": ["knowledge_base_search", "web_search", "get_company_info"],
    "minimal": [],  # Privacy-focused, no external tools
}

