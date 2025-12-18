"""
Configuration loader for chat agents.
Loads and validates agent configuration from YAML files.
"""
import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UserDataField:
    """Configuration for a user data field."""
    field_name: str
    normalized_name: str
    description: str
    data_type: str  # "string", "integer", "list"
    enabled: bool = True
    aliases: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    accumulate: bool = False  # For list types
    validation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Complete agent configuration."""
    # Metadata
    agent_name: str
    agent_version: str
    description: str

    # Instructions
    system_prompt: str
    silent_operation_instructions: str
    tool_usage_instructions: str

    # User data fields
    user_data_fields: List[UserDataField]

    # Context display
    context_display: Dict[str, Any]
    recent_messages_context: Dict[str, Any]

    # Model config
    model_config: Dict[str, Any]

    # Privacy
    privacy: Dict[str, Any]

    # Experimental (optional)
    experimental: Dict[str, Any] = field(default_factory=dict)

    def get_enabled_fields(self) -> List[UserDataField]:
        """Get only enabled user data fields."""
        return [f for f in self.user_data_fields if f.enabled]

    def get_field_by_name(self, name: str) -> Optional[UserDataField]:
        """Get field configuration by field name or alias."""
        name_lower = name.lower()
        for field_config in self.user_data_fields:
            if field_config.field_name.lower() == name_lower:
                return field_config
            if name_lower in [a.lower() for a in field_config.aliases]:
                return field_config
        return None

    def build_field_map(self) -> Dict[str, str]:
        """Build mapping from field_name/aliases to normalized_name."""
        field_map = {}
        for field_config in self.get_enabled_fields():
            # Add main field name
            field_map[field_config.field_name.lower()] = field_config.normalized_name
            # Add aliases
            for alias in field_config.aliases:
                field_map[alias.lower()] = field_config.normalized_name
        return field_map

    def get_complete_system_prompt(self) -> str:
        """Build complete system prompt with all instructions."""
        parts = []

        if self.system_prompt:
            parts.append(self.system_prompt)

        if self.silent_operation_instructions:
            parts.append(self.silent_operation_instructions)

        if self.tool_usage_instructions:
            parts.append(self.tool_usage_instructions)

        return "\n\n".join(parts)


class ConfigLoader:
    """Loads and validates agent configuration from YAML files."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            config_dir: Directory containing config files.
                       Defaults to ./config relative to this file.
        """
        if config_dir is None:
            # Default to config/ directory next to this file
            self.config_dir = Path(__file__).parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

    def load_config(self, config_name: str = "agent_config.yaml") -> AgentConfig:
        """
        Load agent configuration from YAML file.

        Args:
            config_name: Name of config file. Can be:
                        - "agent_config.yaml" (default)
                        - "personalities/friendly_tutor.yaml"
                        - Absolute path to config file

        Returns:
            AgentConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        # Handle absolute paths
        if os.path.isabs(config_name):
            config_path = Path(config_name)
        else:
            config_path = self.config_dir / config_name

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Load YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        # Parse and validate
        return self._parse_config(config_data, config_path)

    def _parse_config(self, data: Dict[str, Any], source_path: Path) -> AgentConfig:
        """Parse and validate configuration data."""

        # Required fields
        required_fields = [
            'agent_name', 'agent_version', 'description',
            'system_prompt', 'user_data_fields'
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in {source_path}")

        # Parse user data fields
        user_data_fields = []
        for field_data in data.get('user_data_fields', []):
            user_data_fields.append(UserDataField(
                field_name=field_data['field_name'],
                normalized_name=field_data['normalized_name'],
                description=field_data['description'],
                data_type=field_data.get('data_type', 'string'),
                enabled=field_data.get('enabled', True),
                aliases=field_data.get('aliases', []),
                examples=field_data.get('examples', []),
                accumulate=field_data.get('accumulate', False),
                validation=field_data.get('validation', {}),
            ))

        # Create AgentConfig
        return AgentConfig(
            agent_name=data['agent_name'],
            agent_version=data['agent_version'],
            description=data['description'],
            system_prompt=data['system_prompt'],
            silent_operation_instructions=data.get('silent_operation_instructions', ''),
            tool_usage_instructions=data.get('tool_usage_instructions', ''),
            user_data_fields=user_data_fields,
            context_display=data.get('context_display', {}),
            recent_messages_context=data.get('recent_messages_context', {}),
            model_config=data.get('model_config', {}),
            privacy=data.get('privacy', {}),
            experimental=data.get('experimental', {}),
        )

    def list_available_configs(self) -> Dict[str, List[str]]:
        """List all available configuration files."""
        configs = {
            'main': [],
            'personalities': []
        }

        # Main config directory
        if self.config_dir.exists():
            for file in self.config_dir.glob('*.yaml'):
                configs['main'].append(file.name)

        # Personalities directory
        personalities_dir = self.config_dir / 'personalities'
        if personalities_dir.exists():
            for file in personalities_dir.glob('*.yaml'):
                configs['personalities'].append(f"personalities/{file.name}")

        return configs


# Convenience function for easy loading
def load_agent_config(config_name: str = "agent_config.yaml") -> AgentConfig:
    """
    Load agent configuration.

    Args:
        config_name: Name or path of config file
                    Examples: "agent_config.yaml",
                             "personalities/friendly_tutor.yaml"

    Returns:
        AgentConfig object
    """
    loader = ConfigLoader()
    return loader.load_config(config_name)


# Example usage
if __name__ == "__main__":
    # Load default config
    config = load_agent_config()
    print(f"Loaded: {config.agent_name} v{config.agent_version}")
    print(f"Description: {config.description}")
    print(f"\nEnabled fields: {[f.field_name for f in config.get_enabled_fields()]}")
    print(f"\nField map: {config.build_field_map()}")

    # List available configs
    loader = ConfigLoader()
    available = loader.list_available_configs()
    print(f"\nAvailable configs:")
    print(f"  Main: {available['main']}")
    print(f"  Personalities: {available['personalities']}")
