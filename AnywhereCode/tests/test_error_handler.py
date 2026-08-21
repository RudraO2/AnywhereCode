"""Tests for anyplace.cli.error_handler.

The exception hierarchy is imported by every core module, so it must stay
importable without pulling in rich or the UI layer -- that is asserted here
too. The message-enhancement helpers are pure string functions.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from anyplace.cli import error_handler as eh
from anyplace.cli.error_handler import (
    AnyplaceError,
    APIError,
    ConfigError,
    FileSystemError,
    GenerationError,
    describe,
    enhance_api_error,
    enhance_config_error,
    enhance_fs_error,
    enhance_generation_error,
    exit_with_error,
    get_recovery_suggestion,
    validate_api_key,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc_type", [APIError, ConfigError, FileSystemError, GenerationError]
)
def test_every_error_type_derives_from_anyplace_error(exc_type):
    assert issubclass(exc_type, AnyplaceError)
    assert issubclass(exc_type, Exception)


def test_error_types_are_distinct_from_each_other():
    assert not issubclass(APIError, ConfigError)
    assert not issubclass(ConfigError, APIError)


def test_error_message_survives_str():
    assert str(APIError("boom")) == "boom"


def test_error_handler_module_imports_without_rich_or_click():
    # A pure-logic import must not drag in the UI stack (spec constraint 3).
    code = (
        "import sys;"
        "import anyplace.cli.error_handler;"
        "assert 'rich' not in sys.modules, sorted(m for m in sys.modules if 'rich' in m);"
        "assert 'click' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(eh.__file__).rsplit("/anyplace/", 1)[0],
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# enhance_api_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message, needle",
    [
        ("invalid_api_key supplied", "rejected"),
        ("401 Unauthorized", "rejected"),
        ("API key invalid or unauthorised", "rejected"),
        ("rate_limit exceeded", "rate limit"),
        ("429 too many requests", "rate limit"),
        ("You have exceeded your quota", "rate limit"),
        ("Request timed out", "too long"),
        ("Connection failed", "reach"),
        ("model gpt-9 not found", "model id"),
    ],
)
def test_enhance_api_error_rewrites_known_failures(message, needle):
    assert needle in enhance_api_error(message).lower()


def test_enhance_api_error_passes_through_unknown_messages():
    assert enhance_api_error("something entirely novel") == "something entirely novel"


def test_enhance_api_error_is_case_insensitive():
    assert enhance_api_error("RATE_LIMIT EXCEEDED") == enhance_api_error("rate_limit exceeded")


def test_enhance_api_error_prefers_auth_over_connection():
    assert "rejected" in enhance_api_error("401 unauthorized on connection").lower()


# ---------------------------------------------------------------------------
# enhance_config_error / enhance_fs_error / enhance_generation_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message, needle",
    [
        ("No api_key configured", "provider"),
        ("LLM provider not configured", "provider"),
        ("Template 'x' not found", "template"),
    ],
)
def test_enhance_config_error_rewrites_known_failures(message, needle):
    assert needle in enhance_config_error(message).lower()


def test_enhance_config_error_passes_through_unknown_messages():
    assert enhance_config_error("weird config problem") == "weird config problem"


@pytest.mark.parametrize(
    "message, needle",
    [
        ("Permission denied", "permission denied"),
        ("No space left on device", "storage"),
        ("disk full", "storage"),
        ("Directory already exists", "already exists"),
    ],
)
def test_enhance_fs_error_rewrites_known_failures(message, needle):
    assert needle in enhance_fs_error(message).lower()


def test_enhance_fs_error_passes_through_unknown_messages():
    assert enhance_fs_error("odd io problem") == "odd io problem"


@pytest.mark.parametrize(
    "message, needle",
    [
        ("Generation timed out", "time"),
        ("Circular dependency detected", "loop"),
        ("version conflict between packages", "loop"),
    ],
)
def test_enhance_generation_error_rewrites_known_failures(message, needle):
    assert needle in enhance_generation_error(message).lower()


def test_enhance_generation_error_passes_through_unknown_messages():
    assert enhance_generation_error("mystery failure") == "mystery failure"


@pytest.mark.parametrize(
    "func", [enhance_api_error, enhance_config_error, enhance_fs_error, enhance_generation_error]
)
def test_enhancers_always_return_a_string(func):
    for message in ("", "   ", "unmatched", "PERMISSION denied\n\nrate_limit"):
        assert isinstance(func(message), str)


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------


def test_describe_routes_each_error_type_to_its_enhancer():
    assert describe(APIError("429 rate limited")) == enhance_api_error("429 rate limited")
    assert describe(ConfigError("no provider")) == enhance_config_error("no provider")
    assert describe(FileSystemError("permission denied")) == enhance_fs_error("permission denied")
    assert describe(GenerationError("timed out")) == enhance_generation_error("timed out")


def test_describe_returns_the_message_for_a_plain_exception():
    assert describe(ValueError("plain problem")) == "plain problem"


def test_describe_falls_back_to_the_class_name_for_an_empty_message():
    assert describe(ValueError()) == "ValueError"


def test_describe_falls_back_for_a_plain_exception_with_no_message():
    assert describe(RuntimeError("")) == "RuntimeError"


@pytest.mark.parametrize("error", [APIError(""), ConfigError(""), GenerationError("")])
def test_describe_never_returns_an_empty_string(error):
    # An anyplace error carrying an empty message still has to render as
    # something -- an empty panel body tells the user nothing.
    assert describe(error) == error.__class__.__name__


# ---------------------------------------------------------------------------
# get_recovery_suggestion
# ---------------------------------------------------------------------------


def test_get_recovery_suggestion_points_at_configure_for_config_errors():
    assert get_recovery_suggestion(ConfigError("anything")) == "anywhere configure"


def test_get_recovery_suggestion_points_at_configure_for_api_key_problems():
    assert get_recovery_suggestion(APIError("API key rejected")) == "anywhere configure"


def test_get_recovery_suggestion_points_at_templates_for_template_problems():
    assert get_recovery_suggestion(GenerationError("template missing")) == "anywhere templates"


@pytest.mark.parametrize(
    "message", ["No space left on device", "disk is full", "Permission denied"]
)
def test_get_recovery_suggestion_points_at_doctor_for_local_problems(message):
    assert get_recovery_suggestion(FileSystemError(message)) == "anywhere doctor"


@pytest.mark.parametrize("message", ["Connection failed", "Request timed out"])
def test_get_recovery_suggestion_points_at_doctor_for_network_problems(message):
    assert get_recovery_suggestion(APIError(message)) == "anywhere doctor"


def test_get_recovery_suggestion_offers_an_install_command_for_missing_git():
    suggestion = get_recovery_suggestion(GenerationError("Git not installed or not in PATH"))
    assert "install git" in suggestion.lower()


def test_get_recovery_suggestion_returns_none_when_nothing_applies():
    assert get_recovery_suggestion(RuntimeError("totally unrelated")) is None


def test_get_recovery_suggestion_never_returns_an_empty_string():
    for error in (ConfigError("x"), APIError("timed out"), RuntimeError("x")):
        suggestion = get_recovery_suggestion(error)
        assert suggestion is None or suggestion.strip()


# ---------------------------------------------------------------------------
# handle_error / exit_with_error
# ---------------------------------------------------------------------------


@pytest.fixture
def recording_console():
    pytest.importorskip("anyplace.ui.components")
    from rich.console import Console

    return Console(width=80, record=True, force_terminal=False)


def test_handle_error_renders_the_enhanced_message(recording_console):
    eh.handle_error(APIError("429 rate limited"), console=recording_console)
    output = recording_console.export_text()
    assert "rate limit" in output.lower()


def test_handle_error_includes_the_context_when_given(recording_console):
    eh.handle_error(APIError("boom"), context="Generating the plan", console=recording_console)
    assert "generating the plan" in recording_console.export_text().lower()


def test_handle_error_renders_the_recovery_suggestion(recording_console):
    eh.handle_error(ConfigError("no provider"), console=recording_console)
    assert "anywhere configure" in recording_console.export_text()


def test_handle_error_does_not_raise_for_a_plain_exception(recording_console):
    eh.handle_error(RuntimeError("plain"), console=recording_console)
    assert "plain" in recording_console.export_text()


def test_exit_with_error_exits_with_status_one(recording_console):
    with pytest.raises(SystemExit) as excinfo:
        exit_with_error(APIError("boom"), console=recording_console)
    assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# validate_api_key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "provider, key, expected",
    [
        ("claude", "sk-ant-api03-abcdef", True),
        ("claude", "sk-proj-abcdef", False),
        ("claude", "AIzaSomething", False),
        ("gemini", "AIzaSyABCDEFG", True),
        ("gemini", "sk-ant-abcdef", False),
        ("openrouter", "sk-or-v1-abcdef", True),
        ("openrouter", "sk-ant-abcdef", False),
        ("custom", "a-long-enough-key", True),
        ("custom", "short", False),
        ("some-new-provider", "a-long-enough-key", True),
        ("some-new-provider", "tiny", False),
    ],
)
def test_validate_api_key_checks_provider_prefixes(provider, key, expected):
    assert validate_api_key(key, provider) is expected


@pytest.mark.parametrize("provider", ["claude", "gemini", "openrouter", "custom", ""])
@pytest.mark.parametrize("key", ["", "   ", "\n\t"])
def test_validate_api_key_rejects_blank_keys(provider, key):
    assert validate_api_key(key, provider) is False


def test_validate_api_key_rejects_none():
    assert validate_api_key(None, "claude") is False


def test_validate_api_key_is_case_insensitive_about_the_provider():
    assert validate_api_key("sk-ant-abcdef", "CLAUDE") is True


def test_validate_api_key_tolerates_surrounding_whitespace():
    assert validate_api_key("  sk-ant-abcdef  ", "claude") is True


def test_validate_api_key_tolerates_a_none_provider():
    assert validate_api_key("a-long-enough-key", None) is True


def test_validate_api_key_always_returns_a_bool():
    assert isinstance(validate_api_key("sk-ant-x", "claude"), bool)
    assert isinstance(validate_api_key("", "claude"), bool)
