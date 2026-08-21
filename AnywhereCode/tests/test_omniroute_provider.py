"""Tests for the OmniRoute provider.

OmniRoute is an OpenAI-compatible gateway you run yourself. It matters here for
one reason: it needs *no API key*, and every other provider in this codebase
does. The config stack refused an empty key, the request builder always sent an
`Authorization` header, and doctor reported a missing key as a critical
failure -- so "no key" had to become a first-class state rather than an error.

These tests pin that state end to end: config, request, and diagnosis.
"""

from __future__ import annotations

import pytest

from anyplace.cli.error_handler import ConfigError, validate_api_key
from anyplace.config.providers import KEYLESS_PROVIDERS, needs_api_key
from anyplace.core import llm_provider as lp
from anyplace.core.llm_provider import OMNIROUTE_DEFAULT_URL

from .helpers import fake_requests_post


# ---------------------------------------------------------------------------
# The keyless fact itself
# ---------------------------------------------------------------------------


def test_omniroute_is_keyless():
    assert needs_api_key("omniroute") is False
    assert "omniroute" in KEYLESS_PROVIDERS


@pytest.mark.parametrize("provider", ["claude", "gemini", "openrouter", "custom"])
def test_every_other_provider_still_wants_a_key(provider):
    assert needs_api_key(provider) is True


@pytest.mark.parametrize("spelling", ["OmniRoute", "OMNIROUTE", "  omniroute  "])
def test_keyless_check_is_case_and_space_insensitive(spelling):
    assert needs_api_key(spelling) is False


@pytest.mark.parametrize("bad", [None, "", "   "])
def test_a_missing_provider_name_is_treated_as_needing_a_key(bad):
    """Fail towards asking for a key rather than silently skipping auth."""
    assert needs_api_key(bad) is True


def test_the_constants_module_pulls_in_nothing():
    """It is imported by pure-logic modules; it must stay dependency-free."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "import anyplace.config.providers;"
        "bad = [m for m in ('rich', 'click', 'requests', 'yaml') if m in sys.modules];"
        "assert not bad, bad"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["", "   ", None])
def test_an_empty_key_is_valid_for_omniroute(key):
    assert validate_api_key(key, "omniroute") is True


def test_an_empty_key_is_still_rejected_for_claude():
    assert validate_api_key("", "claude") is False


def test_a_key_is_accepted_for_omniroute_if_someone_supplies_one():
    """OmniRoute can be put behind auth; don't refuse a key that was given."""
    assert validate_api_key("whatever-token", "omniroute") is True


# ---------------------------------------------------------------------------
# Storing it
# ---------------------------------------------------------------------------


def test_api_manager_accepts_omniroute_without_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from anyplace.config.api_manager import APIManager

    mgr = APIManager()
    mgr.set_provider("omniroute", "", "auto", base_url=OMNIROUTE_DEFAULT_URL)

    stored = mgr.get_provider("omniroute")
    assert stored["api_key"] == ""
    assert stored["model"] == "auto"
    assert stored["base_url"] == OMNIROUTE_DEFAULT_URL


def test_api_manager_still_refuses_a_keyless_claude(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from anyplace.config.api_manager import APIManager

    with pytest.raises(ConfigError):
        APIManager().set_provider("claude", "", "claude-opus-5")


# ---------------------------------------------------------------------------
# Using it
# ---------------------------------------------------------------------------


class KeylessManager:
    """An api_manager whose active provider is OmniRoute with no key."""

    def __init__(self, **overrides):
        self.config = {"api_key": "", "model": "auto"}
        self.config.update(overrides)

    def get_active_provider(self):
        return "omniroute"

    def get_active_config(self):
        return dict(self.config)

    def get_provider(self, _name):
        return dict(self.config)

    def list_providers(self):
        return {"omniroute": dict(self.config)}


def omniroute_payload(text):
    return {"choices": [{"message": {"content": text}}]}


def test_provider_builds_without_a_key():
    provider = lp.LLMProvider(api_manager=KeylessManager())
    assert provider.provider == "omniroute"
    assert provider.api_key == ""


def test_provider_defaults_to_the_local_gateway():
    provider = lp.LLMProvider(api_manager=KeylessManager())
    assert provider.base_url == OMNIROUTE_DEFAULT_URL
    assert provider.model == "auto"


def test_a_custom_base_url_is_respected():
    provider = lp.LLMProvider(
        api_manager=KeylessManager(base_url="http://192.168.1.5:9000/v1")
    )
    assert provider.base_url == "http://192.168.1.5:9000/v1"


def test_request_goes_to_the_openai_compatible_path(monkeypatch):
    post = fake_requests_post(omniroute_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    lp.LLMProvider(api_manager=KeylessManager()).generate_text("hello")

    assert post.last["url"] == OMNIROUTE_DEFAULT_URL + "/chat/completions"


def test_no_authorization_header_is_sent_without_a_key(monkeypatch):
    """An empty 'Bearer ' header makes some servers reject the request."""
    post = fake_requests_post(omniroute_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    lp.LLMProvider(api_manager=KeylessManager()).generate_text("hello")

    assert "Authorization" not in post.last["headers"]
    assert post.last["headers"]["Content-Type"] == "application/json"


def test_an_authorization_header_is_sent_when_a_key_exists(monkeypatch):
    post = fake_requests_post(omniroute_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    lp.LLMProvider(api_manager=KeylessManager(api_key="tok")).generate_text("hello")

    assert post.last["headers"]["Authorization"] == "Bearer tok"


def test_the_reply_is_read_back(monkeypatch):
    post = fake_requests_post(omniroute_payload("hello from omniroute"))
    monkeypatch.setattr(lp.requests, "post", post)

    reply = lp.LLMProvider(api_manager=KeylessManager()).generate_text("hi")

    assert reply == "hello from omniroute"


def test_omniroute_does_not_get_the_openrouter_referer_headers(monkeypatch):
    post = fake_requests_post(omniroute_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    lp.LLMProvider(api_manager=KeylessManager()).generate_text("hello")

    assert "HTTP-Referer" not in post.last["headers"]
    assert "X-Title" not in post.last["headers"]


def test_list_models_offers_something_for_omniroute():
    models = lp.LLMProvider(api_manager=KeylessManager()).list_models()
    assert models
    assert "auto" in models


# ---------------------------------------------------------------------------
# Diagnosing it
# ---------------------------------------------------------------------------


def test_doctor_does_not_call_a_keyless_provider_misconfigured():
    from anyplace.core import doctor

    check = doctor.check_providers(api_manager=KeylessManager())
    assert check.status == doctor.PASS, check.detail


def test_doctor_still_fails_a_keyed_provider_with_no_key():
    from anyplace.core import doctor

    class NoKeyClaude:
        def list_providers(self):
            return {"claude": {"api_key": "", "model": "claude-opus-5"}}

        def get_active_provider(self):
            return "claude"

        def get_provider(self, _name):
            return {"api_key": "", "model": "claude-opus-5"}

    check = doctor.check_providers(api_manager=NoKeyClaude())
    assert check.status == doctor.FAIL
    assert check.critical is True


def test_doctor_warns_when_omniroute_has_no_model():
    from anyplace.core import doctor

    check = doctor.check_providers(api_manager=KeylessManager(model=""))
    assert check.status == doctor.WARN
    assert "model" in check.detail.lower()


def test_doctor_never_reports_a_key_for_a_keyless_provider():
    from anyplace.core import doctor

    check = doctor.check_providers(api_manager=KeylessManager())
    assert "api key" not in check.detail.lower()


# ---------------------------------------------------------------------------
# Offering it
# ---------------------------------------------------------------------------


def test_the_wizard_lists_omniroute():
    from anyplace.cli.config_wizard import PROVIDER_ORDER, PROVIDERS

    assert "omniroute" in PROVIDER_ORDER
    assert "omniroute" in PROVIDERS


def test_the_wizard_says_no_key_is_needed():
    from anyplace.cli.config_wizard import PROVIDERS

    assert "no key" in PROVIDERS["omniroute"]["key_format"].lower()


def test_the_wizard_note_tells_the_user_how_to_start_it():
    """It is not a hosted service -- the note has to say what to run."""
    from anyplace.cli.config_wizard import OMNIROUTE_NOTE

    assert "npm install -g omniroute" in OMNIROUTE_NOTE
    assert "yourself" in OMNIROUTE_NOTE.lower()


def test_every_wizard_provider_has_at_least_one_model():
    from anyplace.cli.config_wizard import PROVIDERS

    for name, info in PROVIDERS.items():
        assert info["models"], "%s offers no models" % name


# ---------------------------------------------------------------------------
# The wizard flow, driven end to end
# ---------------------------------------------------------------------------


def run_wizard(provider, answers, tmp_path, monkeypatch, width=40):
    """Drive configure_single_provider with scripted answers; return (ok, mgr, output)."""
    import io

    from rich.console import Console

    from anyplace.cli.config_wizard import configure_single_provider
    from anyplace.config.api_manager import APIManager
    from anyplace.ui.layout import Layout
    from anyplace.ui.prompts import scripted_input

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    console = Console(file=io.StringIO(), width=width)
    manager = APIManager()
    ok = configure_single_provider(
        console, manager, provider, Layout.detect(width=width), scripted_input(answers)
    )
    return ok, manager, console.file.getvalue()


def test_wizard_configures_omniroute_without_asking_for_a_key(tmp_path, monkeypatch):
    # model "1" (auto), Enter for the default URL, "n" to skip the live test.
    ok, manager, output = run_wizard("omniroute", ["1", "", "n"], tmp_path, monkeypatch)

    assert ok is True
    assert "Paste your API key" not in output
    stored = manager.get_provider("omniroute")
    assert stored["api_key"] == ""
    assert stored["model"] == "auto"
    assert stored["base_url"] == OMNIROUTE_DEFAULT_URL


def test_wizard_makes_omniroute_active_when_it_is_the_only_provider(tmp_path, monkeypatch):
    _, manager, _ = run_wizard("omniroute", ["1", "", "n"], tmp_path, monkeypatch)
    assert manager.get_active_provider() == "omniroute"


def test_wizard_explains_that_omniroute_must_be_running(tmp_path, monkeypatch):
    _, _, output = run_wizard("omniroute", ["1", "", "n"], tmp_path, monkeypatch)
    assert "npm install -g omniroute" in output


def test_wizard_does_not_show_an_empty_key_line(tmp_path, monkeypatch):
    """A bare 'Key:' with nothing after it reads like something failed."""
    _, _, output = run_wizard("omniroute", ["1", "", "n"], tmp_path, monkeypatch)
    assert "Key: not needed" in output
    for line in output.splitlines():
        assert line.rstrip() != "Key:"


def test_wizard_accepts_a_different_omniroute_url(tmp_path, monkeypatch):
    ok, manager, _ = run_wizard(
        "omniroute", ["1", "http://192.168.1.5:9000/v1", "n"], tmp_path, monkeypatch
    )
    assert ok is True
    assert manager.get_provider("omniroute")["base_url"] == "http://192.168.1.5:9000/v1"


@pytest.mark.parametrize("width", [30, 40, 60, 90])
def test_the_omniroute_wizard_screen_fits_every_width(width, tmp_path, monkeypatch):
    _, _, output = run_wizard(
        "omniroute", ["1", "", "n"], tmp_path, monkeypatch, width=width
    )
    too_long = [line for line in output.splitlines() if len(line) > width]
    assert not too_long, "overflowed %d columns: %r" % (width, too_long[:3])
