"""
LLM Provider abstraction using LiteLLM.

Handles communication with multiple LLM providers (Claude, Gemini, OpenRouter, etc.)
"""

from typing import Optional, Dict, Any, List
import litellm
from litellm import completion, acompletion
import json

from anyplace.config.api_manager import APIManager
from anyplace.cli.error_handler import APIError


class LLMProvider:
    """
    Unified interface for LLM providers.

    Supports Claude, Gemini, OpenRouter, and custom endpoints via LiteLLM.
    """

    def __init__(self, api_manager: Optional[APIManager] = None):
        """
        Initialize LLM provider.

        Args:
            api_manager: APIManager instance for credentials
        """
        self.api_manager = api_manager or APIManager()
        self.config = self.api_manager.get_active_config()
        self._setup_provider()

    def _setup_provider(self):
        """Setup the LLM provider based on configuration."""
        provider_name = self.api_manager.get_active_provider()
        config = self.config

        if not config:
            raise APIError("No LLM provider configured. Run: anyplace configure")

        api_key = config.get("api_key")
        if not api_key:
            raise APIError(f"No API key for {provider_name}")

        # Configure LiteLLM
        if provider_name == "claude":
            litellm.api_key = api_key
            self.model = config.get("model", "claude-3-5-sonnet-20241022")
            self.provider = "claude"

        elif provider_name == "gemini":
            litellm.api_key = api_key
            model_name = config.get("model", "gemini-2.0-flash")
            # Gemini models need "google/" prefix for LiteLLM
            if not model_name.startswith("google/"):
                model_name = f"google/{model_name}"
            self.model = model_name
            self.provider = "gemini"

        elif provider_name == "openrouter":
            litellm.api_key = api_key
            self.model = config.get("model", "anthropic/claude-3.5-sonnet")
            self.provider = "openrouter"

        elif provider_name == "custom":
            litellm.api_key = api_key
            self.model = config.get("model", "custom-model")
            self.base_url = config.get("base_url", "http://localhost:8000")
            self.provider = "custom"

        else:
            raise APIError(f"Unknown provider: {provider_name}")

    def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        Generate text using the configured LLM.

        Args:
            prompt: User prompt
            system: System message for context
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            json_mode: If True, request JSON output

        Returns:
            Generated text

        Raises:
            APIError: If API call fails
        """
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            # Build kwargs for LiteLLM
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add custom base URL if configured
            if self.provider == "custom" and hasattr(self, "base_url"):
                kwargs["api_base"] = self.base_url

            # Request JSON mode if needed
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = completion(**kwargs)

            return response.choices[0].message.content

        except Exception as e:
            error_msg = str(e).lower()

            if "unauthorized" in error_msg or "invalid" in error_msg:
                raise APIError("API key invalid or expired")
            elif "rate_limit" in error_msg or "quota" in error_msg:
                raise APIError("API quota exceeded or rate limited")
            elif "connection" in error_msg or "timeout" in error_msg:
                raise APIError("Connection failed. Check internet and API status")
            else:
                raise APIError(f"LLM API error: {e}")

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: User prompt
            system: System message
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Parsed JSON response

        Raises:
            APIError: If generation fails
        """
        response = self.generate_text(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        try:
            # Try to extract JSON from response
            # Sometimes LLM wraps it in markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse JSON response: {e}")

    def list_models(self) -> List[str]:
        """Get list of available models for current provider."""
        provider = self.api_manager.get_active_provider()

        models = {
            "claude": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20250219",
            ],
            "gemini": [
                "gemini-2.0-flash",
                "gemini-2.0-pro",
                "gemini-1.5-pro",
            ],
            "openrouter": [
                "anthropic/claude-3.5-sonnet",
                "google/gemini-2.0-flash-exp",
                "mistralai/mistral-large",
            ],
            "custom": ["your-custom-model"],
        }

        return models.get(provider, [])

    def test_connection(self) -> bool:
        """
        Test connection to the LLM provider.

        Returns:
            True if connection successful

        Raises:
            APIError: If connection fails
        """
        try:
            response = self.generate_text(
                prompt="Say 'OK' only.",
                max_tokens=10,
                temperature=0,
            )
            return response.strip().upper() == "OK"
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Connection test failed: {e}")


if __name__ == "__main__":
    # Test LLM provider
    try:
        provider = LLMProvider()
        print(f"Provider: {provider.provider}")
        print(f"Model: {provider.model}")

        # Test connection
        if provider.test_connection():
            print("✅ Connection successful!")
        else:
            print("❌ Connection test failed")

    except APIError as e:
        print(f"Error: {e}")
