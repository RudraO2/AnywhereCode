"""
LLM Provider abstraction using direct HTTP calls.

Handles Claude, Gemini, OpenRouter, and custom endpoints using only
the `requests` library — no native build dependencies, works on Termux/Android.
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests

from anyplace.config.api_manager import APIManager
from anyplace.cli.error_handler import APIError


# ─────────────────────────────────────────────────────────────────────────────
# Per-provider HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _call_claude(
    api_key: str,
    model: str,
    user_messages: List[Dict],
    system: Optional[str],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    """Call the Anthropic Messages API directly."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    sys_prompt = system or ""
    if json_mode:
        sys_prompt = (sys_prompt + "\nRespond with valid JSON only. No markdown fences.").strip()

    body: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": user_messages,
    }
    if sys_prompt:
        body["system"] = sys_prompt

    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_gemini(
    api_key: str,
    model: str,
    user_messages: List[Dict],
    system: Optional[str],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    """Call the Google Generative Language API directly."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{model}:generateContent?key={api_key}"
    )

    # Gemini uses a flat contents list; inject system as a leading exchange
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[System context]\n{system}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})

    for msg in user_messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    gen_config: Dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
    }
    if json_mode:
        gen_config["responseMimeType"] = "application/json"

    body = {"contents": contents, "generationConfig": gen_config}

    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai_compat(
    api_key: str,
    model: str,
    user_messages: List[Dict],
    system: Optional[str],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    base_url: str,
    extra_headers: Optional[Dict] = None,
) -> str:
    """Call any OpenAI-compatible endpoint (OpenRouter, custom, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    all_messages: List[Dict] = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(user_messages)

    body: Dict[str, Any] = {
        "model": model,
        "messages": all_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# Main provider class
# ─────────────────────────────────────────────────────────────────────────────

class LLMProvider:
    """
    Unified interface for LLM providers.

    Supports Claude (Anthropic), Gemini (Google), OpenRouter, and custom
    OpenAI-compatible endpoints using only the `requests` library.
    No native build dependencies — works on Termux/Android.
    """

    def __init__(self, api_manager: Optional[APIManager] = None):
        self.api_manager = api_manager or APIManager()
        self.config = self.api_manager.get_active_config()
        self._setup_provider()

    def _setup_provider(self):
        """Read config and set provider, model, key, and optional base_url."""
        provider_name = self.api_manager.get_active_provider()
        config = self.config

        if not config:
            raise APIError("No LLM provider configured. Run: anyplace configure")

        self.api_key = config.get("api_key", "")
        if not self.api_key:
            raise APIError(f"No API key for {provider_name}")

        self.provider = provider_name
        self.base_url: Optional[str] = None

        if provider_name == "claude":
            self.model = config.get("model", "claude-3-5-sonnet-20241022")

        elif provider_name == "gemini":
            model_name = config.get("model", "gemini-2.0-flash")
            # Strip "google/" prefix if user added it — we use the bare name
            if model_name.startswith("google/"):
                model_name = model_name[len("google/"):]
            self.model = model_name

        elif provider_name == "openrouter":
            self.model = config.get("model", "anthropic/claude-3.5-sonnet")
            self.base_url = "https://openrouter.ai/api/v1"

        elif provider_name == "custom":
            self.model = config.get("model", "custom-model")
            self.base_url = config.get("base_url", "http://localhost:8000/v1")

        else:
            raise APIError(f"Unknown provider: {provider_name}")

    def _dispatch(
        self,
        user_messages: List[Dict],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        """Route to the correct HTTP helper based on provider."""
        if self.provider == "claude":
            return _call_claude(
                self.api_key, self.model, user_messages,
                system, temperature, max_tokens, json_mode,
            )

        if self.provider == "gemini":
            return _call_gemini(
                self.api_key, self.model, user_messages,
                system, temperature, max_tokens, json_mode,
            )

        # OpenRouter or custom — both are OpenAI-compatible
        extra = (
            {"HTTP-Referer": "https://github.com/rudrao2/anywhereCode",
             "X-Title": "AnywhereCode"}
            if self.provider == "openrouter"
            else None
        )
        return _call_openai_compat(
            self.api_key, self.model, user_messages,
            system, temperature, max_tokens, json_mode,
            base_url=self.base_url,
            extra_headers=extra,
        )

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
            system: Optional system/context message
            temperature: Sampling temperature (0–1)
            max_tokens: Maximum tokens to generate
            json_mode: Ask provider to return valid JSON

        Returns:
            Generated text string

        Raises:
            APIError: On auth failure, quota, network error, etc.
        """
        user_messages = [{"role": "user", "content": prompt}]

        try:
            return self._dispatch(user_messages, system, temperature, max_tokens, json_mode)

        except requests.exceptions.Timeout:
            raise APIError("Request timed out. Check your internet connection.")

        except requests.exceptions.ConnectionError:
            raise APIError("Connection failed. Check your internet connection and API status.")

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            body = ""
            try:
                body = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                body = str(e)

            if status in (401, 403):
                raise APIError(f"API key invalid or unauthorised. ({body})")
            elif status == 429:
                raise APIError("API rate limit or quota exceeded. Wait a moment and try again.")
            elif status >= 500:
                raise APIError(f"Provider server error ({status}). Try again later.")
            else:
                raise APIError(f"HTTP {status}: {body}")

        except Exception as e:
            raise APIError(f"LLM API error: {e}")

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Generate and parse a JSON response with robust extraction.

        Returns:
            Parsed dict

        Raises:
            APIError: If generation or parsing fails
        """
        response = self.generate_text(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        # Try multiple extraction strategies
        json_obj = self._extract_json_from_response(response)
        if json_obj is not None:
            return json_obj

        # If all extraction attempts fail, try requesting JSON again with stricter prompt
        strict_prompt = (
            f"You MUST respond with ONLY valid JSON. No text before or after. No markdown.\n\n"
            f"Original request:\n{prompt}"
        )
        strict_system = (
            (system or "") +
            "\n\nIMPORTANT: You MUST respond with ONLY valid JSON. No markdown fences, no explanations."
        ).strip()

        try:
            response = self.generate_text(
                prompt=strict_prompt,
                system=strict_system,
                temperature=0.1,  # Lower temperature for more deterministic output
                max_tokens=max_tokens,
                json_mode=True,
            )
            json_obj = self._extract_json_from_response(response)
            if json_obj is not None:
                return json_obj
        except Exception:
            pass  # Fall through to final error

        raise APIError(
            f"Failed to parse JSON from LLM response. "
            f"Response was: {response[:200]}..."
        )

    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from various response formats.

        Handles:
        - Plain JSON
        - JSON in markdown code blocks
        - JSON with surrounding text
        - Partial JSON

        Returns:
            Parsed dict if found, None otherwise
        """
        # Strategy 1: Try parsing as-is
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Strip markdown fences
        if "```json" in response:
            try:
                json_str = response.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        if "```" in response:
            try:
                json_str = response.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # Strategy 3: Find JSON by looking for opening/closing braces
        response_stripped = response.strip()
        if response_stripped.startswith("{") or response_stripped.startswith("["):
            # Find the closing brace/bracket
            try:
                if response_stripped.startswith("{"):
                    # Find matching closing brace
                    depth = 0
                    for i, char in enumerate(response_stripped):
                        if char == "{":
                            depth += 1
                        elif char == "}":
                            depth -= 1
                            if depth == 0:
                                json_str = response_stripped[:i+1]
                                return json.loads(json_str)
                elif response_stripped.startswith("["):
                    # Find matching closing bracket
                    depth = 0
                    for i, char in enumerate(response_stripped):
                        if char == "[":
                            depth += 1
                        elif char == "]":
                            depth -= 1
                            if depth == 0:
                                json_str = response_stripped[:i+1]
                                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # Strategy 4: Look for JSON object/array anywhere in the response
        for start_idx in range(len(response)):
            if response[start_idx] in ("{", "["):
                try:
                    # Try to parse from this position onward
                    json_str = response[start_idx:]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Try with truncation (find closing brace/bracket)
                    try:
                        if response[start_idx] == "{":
                            depth = 0
                            for i in range(start_idx, len(response)):
                                if response[i] == "{":
                                    depth += 1
                                elif response[i] == "}":
                                    depth -= 1
                                    if depth == 0:
                                        json_str = response[start_idx:i+1]
                                        return json.loads(json_str)
                        elif response[start_idx] == "[":
                            depth = 0
                            for i in range(start_idx, len(response)):
                                if response[i] == "[":
                                    depth += 1
                                elif response[i] == "]":
                                    depth -= 1
                                    if depth == 0:
                                        json_str = response[start_idx:i+1]
                                        return json.loads(json_str)
                    except (json.JSONDecodeError, IndexError):
                        continue

        return None

    def list_models(self) -> List[str]:
        """Return known model IDs for the active provider."""
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
        return models.get(self.provider, [])

    def test_connection(self) -> bool:
        """
        Send a minimal request to verify the API key and connectivity.

        Returns:
            True if the provider responds successfully

        Raises:
            APIError: If the test call fails
        """
        try:
            response = self.generate_text(
                prompt="Reply with the single word OK.",
                max_tokens=16,
                temperature=0,
            )
            # Accept any non-empty response as a passing test
            return bool(response.strip())
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Connection test failed: {e}")
