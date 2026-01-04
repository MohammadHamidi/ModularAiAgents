"""
Path-based Agent Router

Maps website paths to appropriate AI agents based on configuration.
"""
import yaml
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import fnmatch

logger = logging.getLogger(__name__)


@dataclass
class PathMapping:
    """A single path-to-agent mapping."""
    path: str
    agent: str
    description: str = ""

    def matches(self, path: str) -> bool:
        """
        Check if this mapping matches the given path.

        Supports:
        - Exact match: "/konesh/list"
        - Wildcard: "/konesh/*"
        - Prefix: "/profile*"

        Args:
            path: Path to check

        Returns:
            True if path matches this mapping
        """
        # Exact match
        if self.path == path:
            return True

        # Wildcard match using fnmatch
        if '*' in self.path:
            return fnmatch.fnmatch(path, self.path)

        return False

    def get_specificity(self) -> int:
        """
        Get specificity score for sorting.

        Higher score = more specific pattern.
        Used to prioritize exact matches over wildcards.

        Returns:
            Specificity score
        """
        if '*' not in self.path:
            # Exact match - highest priority
            return 1000 + len(self.path)
        else:
            # Wildcard - priority based on prefix length before wildcard
            prefix = self.path.split('*')[0]
            return len(prefix)


class PathRouter:
    """Routes paths to appropriate agents based on configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize path router.

        Args:
            config_path: Path to path_agent_mapping.yaml file
                        Defaults to config/path_agent_mapping.yaml
        """
        if config_path is None:
            # Default to config directory
            self.config_path = Path(__file__).parent.parent / "config" / "path_agent_mapping.yaml"
        else:
            self.config_path = Path(config_path)

        self.mappings: List[PathMapping] = []
        self.default_agent: str = "orchestrator"
        self._load_config()

    def _load_config(self):
        """Load path mapping configuration from YAML."""
        if not self.config_path.exists():
            logger.warning(f"Path mapping config not found: {self.config_path}")
            logger.warning("Using default agent 'orchestrator' for all paths")
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Load default agent
            self.default_agent = config.get('default_agent', 'orchestrator')

            # Load mappings
            mappings_data = config.get('mappings', [])
            self.mappings = [
                PathMapping(
                    path=m['path'],
                    agent=m['agent'],
                    description=m.get('description', '')
                )
                for m in mappings_data
            ]

            # Sort by specificity (most specific first)
            self.mappings.sort(key=lambda m: m.get_specificity(), reverse=True)

            logger.info(f"Loaded {len(self.mappings)} path mappings from {self.config_path}")
            logger.info(f"Default agent: {self.default_agent}")

        except Exception as e:
            logger.error(f"Failed to load path mapping config: {e}", exc_info=True)
            logger.warning("Using default agent 'orchestrator' for all paths")

    def get_agent_for_path(self, path: str) -> str:
        """
        Get the appropriate agent key for a given path.

        Args:
            path: Website path (e.g., "/konesh/list", "/profile/complete")

        Returns:
            Agent key (e.g., "action_expert", "journey_register")

        Examples:
            >>> router = PathRouter()
            >>> router.get_agent_for_path("/konesh/list")
            'action_expert'
            >>> router.get_agent_for_path("/profile/complete")
            'journey_register'
            >>> router.get_agent_for_path("/unknown")
            'orchestrator'
        """
        # Normalize path
        path = path.strip()
        if not path.startswith('/'):
            path = '/' + path

        # Try to find matching mapping (already sorted by specificity)
        for mapping in self.mappings:
            if mapping.matches(path):
                logger.info(f"Path '{path}' matched pattern '{mapping.path}' → agent '{mapping.agent}'")
                return mapping.agent

        # No match found, use default
        logger.info(f"Path '{path}' has no specific mapping → using default agent '{self.default_agent}'")
        return self.default_agent

    def get_all_mappings(self) -> List[Dict[str, str]]:
        """
        Get all path mappings.

        Returns:
            List of mapping dictionaries
        """
        return [
            {
                "path": m.path,
                "agent": m.agent,
                "description": m.description
            }
            for m in self.mappings
        ]

    def reload_config(self):
        """Reload configuration from file."""
        logger.info("Reloading path mapping configuration")
        self.mappings = []
        self._load_config()


# Global router instance
_global_router: Optional[PathRouter] = None


def get_path_router() -> PathRouter:
    """
    Get global path router instance.

    Returns:
        PathRouter instance
    """
    global _global_router
    if _global_router is None:
        _global_router = PathRouter()
    return _global_router


def set_path_router(router: PathRouter):
    """Set global path router instance."""
    global _global_router
    _global_router = router


# Example usage
if __name__ == "__main__":
    # Test path router
    router = PathRouter()

    test_paths = [
        "/",
        "/konesh/list",
        "/konesh/create",
        "/profile/complete",
        "/rewards/history",
        "/unknown-page",
        "/faq",
        "/محفل/برگزاری"
    ]

    print("Path Mapping Tests:")
    print("=" * 60)
    for test_path in test_paths:
        agent = router.get_agent_for_path(test_path)
        print(f"{test_path:30} → {agent}")
