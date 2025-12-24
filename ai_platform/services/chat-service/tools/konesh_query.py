"""
Konesh Query Tool
Custom tool for querying the کنش (Quranic Actions) database
"""
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class KoneshQueryTool:
    """Tool for querying the کنش (Quranic Actions) database."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Konesh Query Tool.

        Args:
            config_path: Path to konesh_database.yaml. If None, uses default path.
        """
        if config_path is None:
            # Default to config/konesh_database.yaml relative to tools directory
            tools_dir = Path(__file__).parent
            config_dir = tools_dir.parent / "config"
            config_path = config_dir / "konesh_database.yaml"
        
        self.config_path = Path(config_path)
        self._konesh_data = None
        self._load_data()

    def _load_data(self):
        """Load کنش data from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._konesh_data = data.get('konesh_list', [])
                logger.info(f"Loaded {len(self._konesh_data)} کنش from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load کنش data from {self.config_path}: {e}")
            self._konesh_data = []

    @property
    def name(self) -> str:
        return "query_konesh"

    @property
    def description(self) -> str:
        return """
        Query the کنش (Quranic Actions) database to find information about available actions.

        Use this tool to:
        - Search for کنش by name, category, or keywords
        - Get detailed information about a specific کنش
        - List all کنش in a category
        - Find کنش suitable for specific contexts (home, school, mosque, etc.)

        Parameters:
        - query (str, required): Search query. Can be:
          * A کنش name or ID (e.g., "محفل خانگی", "1")
          * A category (e.g., "خانه", "مدرسه", "مسجد", "فضای مجازی")
          * Keywords (e.g., "قصه", "بازی", "کودک")
          * Context (e.g., "home", "school", "mosque", "virtual")
        - category (str, optional): Filter by category. Options: "خانه", "مدرسه", "مسجد", "فضای مجازی", "محیط کار", "عمومی"
        - is_primary (bool, optional): Filter by primary status
        - limit (int, optional): Maximum number of results (default: 10)

        Returns: JSON string with matching کنش information
        """

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for کنش (name, ID, category, keywords, or context)"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category: خانه, مدرسه, مسجد, فضای مجازی, محیط کار, عمومی",
                    "enum": ["خانه", "مدرسه", "مسجد", "فضای مجازی", "محیط کار", "عمومی", None]
                },
                "is_primary": {
                    "type": "boolean",
                    "description": "Filter by primary status (true for primary actions only)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10
                }
            },
            "required": ["query"]
        }

    @property
    def enabled(self) -> bool:
        return True

    def _normalize_query(self, query: str) -> str:
        """Normalize query for searching."""
        return query.lower().strip()

    def _matches_query(self, konesh: Dict[str, Any], query: str) -> bool:
        """Check if a کنش matches the query."""
        query_lower = self._normalize_query(query)
        
        # Check ID
        if str(konesh.get('id', '')) == query:
            return True
        
        # Check name (Persian and English)
        name_fa = konesh.get('name', '').lower()
        name_en = konesh.get('name_en', '').lower()
        if query_lower in name_fa or query_lower in name_en:
            return True
        
        # Check category
        category_fa = konesh.get('category', '').lower()
        category_en = konesh.get('category_en', '').lower()
        if query_lower in category_fa or query_lower in category_en:
            return True
        
        # Check keywords
        keywords = [kw.lower() for kw in konesh.get('keywords', [])]
        if any(query_lower in kw or kw in query_lower for kw in keywords):
            return True
        
        # Check description
        description = konesh.get('description', '').lower()
        if query_lower in description:
            return True
        
        # Check main_platform
        platform = konesh.get('main_platform', '').lower()
        if query_lower in platform:
            return True
        
        # Check actor and target_audience
        actor = konesh.get('actor', '').lower()
        target = konesh.get('target_audience', '').lower()
        if query_lower in actor or query_lower in target:
            return True
        
        return False

    async def execute(
        self,
        query: str,
        category: Optional[str] = None,
        is_primary: Optional[bool] = None,
        limit: int = 10
    ) -> str:
        """
        Execute the query and return matching کنش.

        Args:
            query: Search query
            category: Optional category filter
            is_primary: Optional primary status filter
            limit: Maximum results to return

        Returns:
            JSON string with matching کنش
        """
        if not self._konesh_data:
            return '{"error": "کنش data not loaded", "results": []}'
        
        results = []
        query_lower = self._normalize_query(query)
        
        for konesh in self._konesh_data:
            # Apply filters
            if category and konesh.get('category') != category and konesh.get('category_en') != category:
                continue
            
            if is_primary is not None and konesh.get('is_primary') != is_primary:
                continue
            
            # Check if matches query
            if self._matches_query(konesh, query):
                results.append(konesh)
            
            # Limit results
            if len(results) >= limit:
                break
        
        # If no results, try a broader search (partial matches)
        if not results:
            for konesh in self._konesh_data:
                if category and konesh.get('category') != category and konesh.get('category_en') != category:
                    continue
                
                if is_primary is not None and konesh.get('is_primary') != is_primary:
                    continue
                
                # Partial match in any field
                konesh_text = ' '.join([
                    str(konesh.get('name', '')),
                    str(konesh.get('name_en', '')),
                    str(konesh.get('description', '')),
                    str(konesh.get('main_platform', '')),
                    ' '.join(konesh.get('keywords', []))
                ]).lower()
                
                if query_lower in konesh_text:
                    results.append(konesh)
                
                if len(results) >= limit:
                    break
        
        # Format results
        import json
        response = {
            "query": query,
            "count": len(results),
            "results": results
        }
        
        return json.dumps(response, ensure_ascii=False, indent=2)

    def get_konesh_by_id(self, konesh_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific کنش by ID."""
        for konesh in self._konesh_data:
            if konesh.get('id') == konesh_id:
                return konesh
        return None

    def get_konesh_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all کنش in a category."""
        results = []
        for konesh in self._konesh_data:
            if konesh.get('category') == category or konesh.get('category_en') == category:
                results.append(konesh)
        return results

    def get_primary_konesh(self) -> List[Dict[str, Any]]:
        """Get all primary کنش."""
        return [k for k in self._konesh_data if k.get('is_primary', False)]

    def list_categories(self) -> List[str]:
        """List all available categories."""
        categories = set()
        for konesh in self._konesh_data:
            cat = konesh.get('category')
            if cat:
                categories.add(cat)
        return sorted(list(categories))

