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

#: Anthropic model families that removed the sampling parameters
#: (``temperature``, ``top_p``, ``top_k``). Sending ``temperature`` to one of
#: these is a 400 from the API, not a warning that can be ignored -- so the
#: parameter has to be left out of the request body entirely.
NO_SAMPLING_PARAMS = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
)


def supports_sampling(model: str) -> bool:
    """Does this Anthropic model still accept ``temperature``?"""
    name = (model or "").strip().lower()
    # OpenRouter-style "anthropic/claude-..." ids name the same models.
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return not name.startswith(NO_SAMPLING_PARAMS)


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
        "messages": user_messages,
    }
    if supports_sampling(model):
        body["temperature"] = temperature
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
    response_schema: Optional[Dict] = None,
) -> str:
    """Call the Google Generative Language API directly."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{model}:generateContent?key={api_key}"
    )

    # Contents: user/model turns only (no fake system injection)
    contents = []
    for msg in user_messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    gen_config: Dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
    }
    if json_mode:
        gen_config["responseMimeType"] = "application/json"
        if response_schema:
            gen_config["responseSchema"] = response_schema

    body: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": gen_config,
    }

    # Use Gemini's dedicated system_instruction field (snake_case per REST API docs)
    sys_text = system or ""
    if json_mode and not response_schema:
        # Only add text reminder when no schema is enforcing structure
        sys_text = (
            sys_text
            + "\nReturn ONLY a raw JSON object — no markdown fences, no explanation, no extra text."
        ).strip()
    if sys_text:
        body["system_instruction"] = {"parts": [{"text": sys_text}]}

    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise APIError(f"Unexpected Gemini response: {data}")


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
            self.model = config.get("model", "claude-opus-5")

        elif provider_name == "gemini":
            model_name = config.get("model", "gemini-2.0-flash")
            # Strip "google/" prefix if user added it — we use the bare name
            if model_name.startswith("google/"):
                model_name = model_name[len("google/"):]
            self.model = model_name

        elif provider_name == "openrouter":
            self.model = config.get("model", "anthropic/claude-sonnet-5")
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
        response_schema: Optional[Dict] = None,
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
                response_schema=response_schema,
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
        response_schema: Optional[Dict] = None,
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
            return self._dispatch(
                user_messages, system, temperature, max_tokens, json_mode,
                response_schema=response_schema,
            )

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
        response_schema: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate and parse a JSON response with robust extraction.

        Args:
            response_schema: Optional Gemini responseSchema (OpenAPI subset, UPPERCASE types).
                             When provided to Gemini, forces exact JSON structure.

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
            response_schema=response_schema,
        )

        # Try multiple extraction strategies — always yields a dict or None
        json_obj = self._extract_json_from_response(response)
        if json_obj is not None:
            return json_obj  # already guaranteed to be a dict by _extract_json_from_response

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
                response_schema=response_schema,
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

    def _as_dict(self, parsed: Any) -> Optional[Dict[str, Any]]:
        """
        Coerce a parsed JSON value to a dict, or return None.

        If the LLM returned a list with one dict inside (e.g. Gemini sometimes
        wraps the object in an array), unwrap it automatically.
        """
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            # Unwrap single-element list containing a dict
            if len(parsed) == 1 and isinstance(parsed[0], dict):
                return parsed[0]
            # List of dicts — merge them (edge case, rarely correct but better than crash)
            merged: Dict[str, Any] = {}
            for item in parsed:
                if isinstance(item, dict):
                    merged.update(item)
            if merged:
                return merged
        return None

    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Extract a JSON *object* (dict) from various response formats.

        Always returns a dict or None — never returns a list, so callers
        can safely call .get() without a TypeError.
        """
        if not response or not response.strip():
            return None

        # Strategy 1: parse as-is
        try:
            return self._as_dict(json.loads(response))
        except json.JSONDecodeError:
            pass

        # Strategy 2: strip markdown fences
        for fence in ("```json", "```"):
            if fence in response:
                try:
                    inner = response.split(fence)[1].split("```")[0].strip()
                    return self._as_dict(json.loads(inner))
                except (json.JSONDecodeError, IndexError):
                    pass

        # Strategy 3: walk from each '{' to its matching '}'.
        #
        # The brace counting has to know about string literals: a model that
        # writes {"note": "use } carefully"} would otherwise close the object at
        # the brace inside the string and produce garbage.
        for start_idx, ch in enumerate(response):
            if ch != "{":
                continue

            end_idx = self._matching_brace(response, start_idx)
            if end_idx is None:
                continue

            try:
                result = self._as_dict(json.loads(response[start_idx : end_idx + 1]))
            except json.JSONDecodeError:
                continue

            # `is not None` rather than truthiness: {} is a valid parse and
            # discarding it sends the caller down the retry path for nothing.
            if result is not None:
                return result

        return None

    @staticmethod
    def _matching_brace(text: str, start: int) -> Optional[int]:
        """Index of the '}' that closes the '{' at `start`, ignoring braces inside strings."""
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index

        return None

    def list_models(self) -> List[str]:
        """Return known model IDs for the active provider."""
        models = {
            "claude": [
                "claude-opus-5",
                "claude-sonnet-5",
                "claude-haiku-4-5",
            ],
            "gemini": [
                "gemini-2.0-flash",
                "gemini-2.0-pro",
                "gemini-1.5-pro",
            ],
            "openrouter": [
                "anthropic/claude-sonnet-5",
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
