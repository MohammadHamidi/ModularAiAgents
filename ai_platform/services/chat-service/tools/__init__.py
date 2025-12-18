# Tools package for AI agents
# Each tool can be assigned to specific personas

from tools.registry import ToolRegistry, Tool
from tools.knowledge_base import KnowledgeBaseTool
from tools.calculator import CalculatorTool
from tools.weather import WeatherTool
from tools.web_search import WebSearchTool

__all__ = [
    'ToolRegistry',
    'Tool',
    'KnowledgeBaseTool',
    'CalculatorTool', 
    'WeatherTool',
    'WebSearchTool',
]

