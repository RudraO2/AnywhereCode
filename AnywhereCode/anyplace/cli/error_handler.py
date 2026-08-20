"""
Errors people can act on.

A stack trace on a phone is four screens of noise you cannot copy out easily.
Every failure here becomes: what happened, in one line — and the command that
fixes it.
"""

from __future__ import annotations

import sys
from typing import Optional

# Exception types are imported by the core modules, so they must stay importable
# without pulling in rich or the UI layer.


class AnyplaceError(Exception):
    """Base for everything we raise on purpose."""


class APIError(AnyplaceError):
    """The LLM provider said no, or never answered."""


class ConfigError(AnyplaceError):
    """Something about the local setup is wrong."""


class FileSystemError(AnyplaceError):
    """Reading or writing failed."""


class GenerationError(AnyplaceError):
    """Planning or code generation failed."""


_TITLES = {
    APIError: ("The AI provider had a problem", "err"),
    ConfigError: ("Setup problem", "warn"),
    FileSystemError: ("File problem", "err"),
    GenerationError: ("Couldn't finish generating", "err"),
}


def _plain(message: str) -> str:
    return " ".join(str(message).split()).lower()


def enhance_api_error(msg: str) -> str:
    low = _plain(msg)
    if "invalid_api_key" in low or "unauthoris" in low or "unauthoriz" in low or "401" in low:
        return "Your API key was rejected.\n\nIt may be mistyped, expired, or for a different provider."
    if "rate limit" in low or "rate_limit" in low or "quota" in low or "429" in low:
        return "You've hit the provider's rate limit or run out of quota.\n\nWait a minute, or switch provider."
    if "timed out" in low or "timeout" in low:
        return "The provider took too long to answer.\n\nOn a weak signal this is common — try again."
    if "connection" in low:
        return "Couldn't reach the provider.\n\nCheck you're online."
    if "model" in low and "not found" in low:
        return "That model id isn't available on this provider.\n\nPick a different model."
    return str(msg)


def enhance_config_error(msg: str) -> str:
    low = _plain(msg)
    if "api key" in low or "api_key" in low or "provider" in low:
        return "No AI provider is set up yet."
    if "template" in low:
        return "That project template is missing or unreadable."
    return str(msg)


def enhance_fs_error(msg: str) -> str:
    low = _plain(msg)
    if "permission" in low:
        return "Permission denied writing there."
    if "space" in low or "disk full" in low or "no space" in low:
        return "The device is out of storage."
    if "exists" in low:
        return "That folder already exists."
    return str(msg)


def enhance_generation_error(msg: str) -> str:
    low = _plain(msg)
    if "timeout" in low or "timed out" in low:
        return "Generation ran out of time.\n\nA smaller project, or a faster model, will get through."
    if "dependency" in low or "conflict" in low:
        return "The plan had files depending on each other in a loop."
    if "already exists" in low:
        return str(msg)
    return str(msg)


_ENHANCERS = {
    APIError: enhance_api_error,
    ConfigError: enhance_config_error,
    FileSystemError: enhance_fs_error,
    GenerationError: enhance_generation_error,
}


def get_recovery_suggestion(error: Exception) -> Optional[str]:
    """The literal next command to type."""
    low = _plain(str(error))

    if isinstance(error, ConfigError) or ("api" in low and "key" in low) or "provider" in low:
        return "anywhere configure"
    if "template" in low:
        return "anywhere templates"
    if "space" in low or "disk" in low:
        return "anywhere doctor"
    if "permission" in low:
        return "anywhere doctor"
    if "git" in low and ("not installed" in low or "not found" in low):
        return "pkg install git      # Termux\napt install git      # Debian/Ubuntu"
    if "connection" in low or "timed out" in low or "timeout" in low:
        return "anywhere doctor"
    return None


def describe(error: Exception) -> str:
    """
    Human-readable body for an exception, without any rendering.

    Never returns an empty string: an error panel with nothing in it tells the
    user only that something broke, which is the one thing they already know.
    An enhancer that has nothing to add falls back to the message, and a
    message that is itself empty falls back to the exception's class name.
    """
    for exc_type, enhancer in _ENHANCERS.items():
        if isinstance(error, exc_type):
            enhanced = enhancer(str(error))
            if enhanced and enhanced.strip():
                return enhanced
            break
    return str(error).strip() or error.__class__.__name__


def handle_error(error: Exception, context: Optional[str] = None, console=None, layout=None) -> None:
    """Render an error the way a person can act on."""
    from anyplace.ui import components as ui
    from anyplace.ui.layout import Layout

    if console is None:
        from rich.console import Console

        console = Console()
    layout = layout or Layout.detect()

    title, tone = "Something went wrong", "err"
    for exc_type, (exc_title, exc_tone) in _TITLES.items():
        if isinstance(error, exc_type):
            title, tone = exc_title, exc_tone
            break

    body = describe(error)
    if context:
        body = "While {0}:\n\n{1}".format(context.lower(), body)

    console.print()
    ui.card(console, body, title=title, tone=tone, layout=layout)

    suggestion = get_recovery_suggestion(error)
    if suggestion:
        ui.card(console, suggestion, title="Try this", tone="warn", layout=layout)


def exit_with_error(error: Exception, context: Optional[str] = None, console=None, layout=None):
    """Report, then stop with a non-zero status so scripts notice."""
    handle_error(error, context, console=console, layout=layout)
    sys.exit(1)


def validate_api_key(api_key: str, provider: str) -> bool:
    """
    Cheap shape check, before we waste a network round trip on an obvious typo.

    Deliberately permissive: providers change their prefixes, and refusing a
    valid key is worse than accepting an invalid one we're about to test anyway.
    """
    if not api_key or not api_key.strip():
        return False

    api_key = api_key.strip()
    provider = (provider or "").lower()

    if provider == "claude":
        return api_key.startswith("sk-ant-")
    if provider == "gemini":
        return api_key.startswith("AIza")
    if provider == "openrouter":
        return api_key.startswith("sk-or-")
    return len(api_key) > 10
