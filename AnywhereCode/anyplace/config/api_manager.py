"""
API key and model configuration management.

Handles secure storage and validation of LLM provider credentials.
"""

import json
from pathlib import Path
from typing import Dict, Optional
import yaml

from anyplace.config.environment import get_config_dir
from anyplace.cli.error_handler import ConfigError, validate_api_key


class APIManager:
    """Manages API keys and model configurations."""

    def __init__(self):
        """Initialize API manager."""
        self.config_dir = get_config_dir()
        self.config_file = self.config_dir / "config.yaml"
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from file."""
        if not self.config_file.exists():
            return {"providers": {}}

        try:
            with open(self.config_file, "r") as f:
                loaded = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config.yaml: {e}")

        if loaded is None:
            return {"providers": {}}

        # A hand-edited config that parses to a list or a bare string used to
        # sail through here and blow up later on the first .get() call.
        if not isinstance(loaded, dict):
            raise ConfigError(
                f"{self.config_file} should contain a mapping, not a "
                f"{type(loaded).__name__}. Delete it and run: anywhere configure"
            )

        providers = loaded.get("providers")
        if providers is None:
            loaded["providers"] = {}
        elif not isinstance(providers, dict):
            raise ConfigError(
                f"'providers' in {self.config_file} should be a mapping. "
                "Delete the file and run: anywhere configure"
            )

        return loaded

    def _save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            # Set secure permissions (user read/write only)
            self.config_file.chmod(0o600)
        except IOError as e:
            raise ConfigError(f"Can't save config: {e}")

    def set_provider(self, provider: str, api_key: str, model: str, **kwargs):
        """
        Set provider configuration.

        Args:
            provider: Provider name (claude, gemini, openrouter, custom)
            api_key: API key for the provider
            model: Model ID to use
            **kwargs: Additional provider-specific settings
        """
        # Validate API key format
        if not validate_api_key(api_key, provider):
            raise ConfigError(
                f"Invalid API key format for {provider}.\n"
                f"Expected format: sk-xxx for Claude, AIza... for Gemini, etc."
            )

        # Store configuration
        if "providers" not in self.config:
            self.config["providers"] = {}

        self.config["providers"][provider.lower()] = {
            "api_key": api_key,
            "model": model,
            **kwargs
        }

        self._save_config()

    def get_provider(self, provider: str) -> Optional[Dict]:
        """Get provider configuration."""
        return self.config.get("providers", {}).get(provider.lower())

    def list_providers(self) -> Dict[str, Dict]:
        """Get all configured providers."""
        return self.config.get("providers", {})

    def get_active_provider(self) -> Optional[str]:
        """Get the active/default provider."""
        return self.config.get("active_provider")

    def set_active_provider(self, provider: str):
        """Set the active/default provider."""
        if provider.lower() not in self.config.get("providers", {}):
            raise ConfigError(f"Provider '{provider}' not configured")

        self.config["active_provider"] = provider.lower()
        self._save_config()

    def get_active_config(self) -> Dict:
        """Get active provider configuration."""
        active = self.get_active_provider()

        if not active:
            providers = self.list_providers()
            if not providers:
                raise ConfigError(
                    "No LLM provider configured.\n"
                    "Run: anywhere configure"
                )
            active = list(providers.keys())[0]

        config = self.get_provider(active)
        if not config:
            raise ConfigError(f"Provider '{active}' not configured")

        return config

    def validate_provider_config(self, provider: str) -> bool:
        """Validate that a provider is properly configured."""
        config = self.get_provider(provider)
        if not config:
            return False

        # Check required fields
        required = ["api_key", "model"]
        return all(config.get(field) for field in required)

    def reset_config(self):
        """Reset configuration to default."""
        self.config = {"providers": {}}
        self._save_config()

    def get_config_file_path(self) -> Path:
        """Get path to config file."""
        return self.config_file


if __name__ == "__main__":
    # Test configuration management
    mgr = APIManager()

    # Set a test provider
    try:
        mgr.set_provider(
            "claude",
            "sk-ant-test-key-123",
            "claude-opus-5"
        )
        print("Provider configured successfully")
        print(f"Providers: {list(mgr.list_providers().keys())}")
    except ConfigError as e:
        print(f"Error: {e}")
