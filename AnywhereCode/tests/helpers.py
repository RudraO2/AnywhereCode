"""Small shared utilities for the anyplace test-suite.

Nothing in here talks to the network, the real filesystem outside ``tmp_path``,
or a real LLM.  Everything is deliberately dumb so that a failing test points at
the code under test rather than at the helper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

import requests


class FakeResponse:
    """A stand-in for :class:`requests.Response`.

    Only the surface that ``anyplace`` actually uses is implemented:
    ``status_code``, ``json()``, ``text`` and ``raise_for_status()``.

    ``raise_for_status`` follows real ``requests`` semantics: it is a no-op for
    2xx/3xx and raises :class:`requests.exceptions.HTTPError` with ``.response``
    pointing back at this object for 4xx/5xx, which is exactly what
    ``LLMProvider.generate_text`` inspects when mapping errors.
    """

    def __init__(
        self,
        payload: Any = None,
        status_code: int = 200,
        text: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.text = text if text is not None else str(payload)

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("No JSON object could be decoded")
        return self._payload

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def raise_for_status(self) -> None:
        if 400 <= self.status_code < 500:
            raise requests.exceptions.HTTPError(
                "%s Client Error" % self.status_code, response=self
            )
        if self.status_code >= 500:
            raise requests.exceptions.HTTPError(
                "%s Server Error" % self.status_code, response=self
            )


class RecordingPost:
    """Callable replacement for ``requests.post`` that records every call.

    Each recorded call is a dict with ``url``, ``headers``, ``json``, ``kwargs``.
    """

    def __init__(self, payload: Any = None, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": kwargs.get("headers") or {},
                "json": kwargs.get("json"),
                "timeout": kwargs.get("timeout"),
                "kwargs": kwargs,
            }
        )
        return FakeResponse(self.payload, status_code=self.status)

    # Convenience accessors -------------------------------------------------
    @property
    def last(self) -> Dict[str, Any]:
        if not self.calls:
            raise AssertionError("requests.post was never called")
        return self.calls[-1]

    @property
    def call_count(self) -> int:
        return len(self.calls)


def fake_requests_post(payload: Any = None, status: int = 200) -> RecordingPost:
    """Factory returning a recording ``requests.post`` replacement."""
    return RecordingPost(payload=payload, status=status)


def claude_payload(text: str = '{"ok": true}') -> Dict[str, Any]:
    """A minimal Anthropic Messages API success body."""
    return {"content": [{"type": "text", "text": text}]}


def gemini_payload(text: str = '{"ok": true}') -> Dict[str, Any]:
    """A minimal Google Generative Language API success body."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def openai_payload(text: str = '{"ok": true}') -> Dict[str, Any]:
    """A minimal OpenAI-compatible chat/completions success body."""
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def error_payload(message: str) -> Dict[str, Any]:
    """The error envelope every supported provider happens to share."""
    return {"error": {"message": message}}


def write_files(root: Union[str, Path], mapping: Mapping[str, str]) -> Path:
    """Write ``{relative_path: content}`` under ``root``, creating parents.

    Returns ``root`` as a :class:`Path` so calls can be chained/inlined.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in mapping.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return root


class StubLLM:
    """A deterministic LLM stand-in that records prompts.

    Unlike ``MockLLMProvider`` it accepts (and ignores) every keyword argument
    the production code passes, including ``response_schema``.
    """

    def __init__(self, text: str = "stub content", json_value: Any = None) -> None:
        self.text = text
        self.json_value = json_value if json_value is not None else {}
        self.text_calls: List[Dict[str, Any]] = []
        self.json_calls: List[Dict[str, Any]] = []

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        self.text_calls.append({"prompt": prompt, **kwargs})
        if callable(self.text):
            return self.text(prompt, **kwargs)
        return self.text

    def generate_json(self, prompt: str, **kwargs: Any) -> Any:
        self.json_calls.append({"prompt": prompt, **kwargs})
        if callable(self.json_value):
            return self.json_value(prompt, **kwargs)
        return self.json_value

    def test_connection(self) -> bool:
        return True


class ExplodingLLM:
    """An LLM stand-in whose every call raises the supplied exception."""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def generate_text(self, *args: Any, **kwargs: Any) -> str:
        raise self.exc

    def generate_json(self, *args: Any, **kwargs: Any) -> Any:
        raise self.exc
