"""Tests for anyplace.core.llm_provider.

Two halves:

* the hand-rolled JSON salvage code (``_extract_json_from_response`` /
  ``_as_dict``), which is what stands between a chatty LLM and a crash;
* provider dispatch and HTTP error mapping, exercised with a recording
  ``requests.post`` so nothing ever leaves the machine.
"""

from __future__ import annotations

import json

import pytest
import requests

from anyplace.cli.error_handler import APIError
from anyplace.core import llm_provider as lp
from anyplace.core.llm_provider import LLMProvider

try:
    from tests.helpers import (
        claude_payload,
        error_payload,
        fake_requests_post,
        gemini_payload,
        openai_payload,
    )
except ImportError:  # pragma: no cover - depends on rootdir layout
    from helpers import (
        claude_payload,
        error_payload,
        fake_requests_post,
        gemini_payload,
        openai_payload,
    )


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeAPIManager:
    """An APIManager that never touches disk."""

    def __init__(self, provider, config):
        self._provider = provider
        self._config = config

    def get_active_provider(self):
        return self._provider

    def get_active_config(self):
        return self._config


def make_provider(provider="claude", **config):
    config.setdefault("api_key", "sk-ant-test-key")
    return LLMProvider(api_manager=FakeAPIManager(provider, config))


@pytest.fixture
def parser():
    """A bare LLMProvider used only for its pure parsing helpers."""
    return object.__new__(LLMProvider)


# ---------------------------------------------------------------------------
# _as_dict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parsed, expected",
    [
        ({"a": 1}, {"a": 1}),
        ({}, {}),
        ([{"a": 1}], {"a": 1}),
        ([{"a": 1}, {"b": 2}], {"a": 1, "b": 2}),
        ([{"a": 1}, "junk", {"b": 2}], {"a": 1, "b": 2}),
        ([1, 2, 3], None),
        ([], None),
        ("a string", None),
        (42, None),
        (None, None),
        ([[{"a": 1}]], None),
    ],
    ids=[
        "dict",
        "empty_dict",
        "single_element_list",
        "list_of_dicts_merged",
        "list_with_non_dicts",
        "list_of_scalars",
        "empty_list",
        "string",
        "int",
        "none",
        "nested_list",
    ],
)
def test_as_dict_coerces_parsed_value(parser, parsed, expected):
    assert parser._as_dict(parsed) == expected


def test_as_dict_later_keys_win_when_merging_list_of_dicts(parser):
    assert parser._as_dict([{"a": 1}, {"a": 2}]) == {"a": 2}


def test_as_dict_returns_same_object_for_dict_input(parser):
    original = {"a": 1}
    assert parser._as_dict(original) is original


# ---------------------------------------------------------------------------
# _extract_json_from_response
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "response, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('  {"a": 1}  ', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('```JSON is fun```', None),
        ('```\n{"a": 1}\n```', {"a": 1}),
        ('Sure! Here you go:\n{"a": 1}\nHope that helps.', {"a": 1}),
        ('[{"a": 1}]', {"a": 1}),
        ('[{"a": 1}, {"b": 2}]', {"a": 1, "b": 2}),
        ('{"a": {"b": {"c": 1}}}', {"a": {"b": {"c": 1}}}),
        ('{"a": "}{"}', {"a": "}{"}),
        ('blah {bad json} more {"ok": 1} tail', {"ok": 1}),
        ("", None),
        ("   \n\t ", None),
        (None, None),
        ("[1, 2, 3]", None),
        ('{"a": 1, "b": [1, 2', None),
        ("42", None),
        ('"just a string"', None),
        ("```\nnot json at all\n```", None),
    ],
    ids=[
        "plain_json",
        "plain_json_with_whitespace",
        "json_fenced",
        "fence_without_newline",
        "bare_fenced",
        "prose_around_object",
        "list_wrapped_single_object",
        "list_of_objects_merged",
        "nested_braces",
        "braces_inside_string_value",
        "first_object_malformed_second_valid",
        "empty_string",
        "whitespace_only",
        "none_input",
        "array_of_scalars",
        "truncated_object",
        "bare_number",
        "bare_string",
        "fence_with_non_json",
    ],
)
def test_extract_json_from_response_handles_llm_output_shapes(parser, response, expected):
    assert parser._extract_json_from_response(response) == expected


def test_extract_json_from_response_returns_empty_dict_for_bare_empty_object(parser):
    # Strategy 1 parses "{}" directly, so an empty object survives.
    assert parser._extract_json_from_response("{}") == {}


def test_extract_json_from_response_picks_first_of_several_fenced_blocks(parser):
    response = '```json\n{"a": 1}\n```\nand also\n```json\n{"b": 2}\n```'
    assert parser._extract_json_from_response(response) == {"a": 1}


def test_extract_json_from_response_never_returns_a_list(parser):
    for response in ('[{"a": 1}]', "[1,2,3]", '[{"a": 1},{"b": 2}]', "[]"):
        result = parser._extract_json_from_response(response)
        assert result is None or isinstance(result, dict)


def test_extract_json_from_response_handles_realistic_plan_payload(parser):
    payload = {
        "project_name": "demo",
        "files": [{"path": "a.txt", "dependencies": []}],
        "architecture_notes": "Uses {braces} in prose",
    }
    response = "Here is the plan:\n```json\n" + json.dumps(payload) + "\n```\nEnjoy!"
    assert parser._extract_json_from_response(response) == payload


def test_extract_json_from_response_is_bounded_on_pathological_braces(parser):
    # Guards against the O(n^2) scan degenerating into a hang.
    assert parser._extract_json_from_response("{" * 500) is None


def test_extract_json_from_response_braces_in_string_with_surrounding_prose(parser):
    # Brace matching is string-aware, so a '}' inside a string value does not
    # close the object early.
    assert parser._extract_json_from_response('Note: {"a": "} x {"} end') == {"a": "} x {"}


def test_extract_json_from_response_empty_object_inside_prose(parser):
    # {} is a valid parse; discarding it would send the caller down the
    # stricter-reprompt path for nothing.
    assert parser._extract_json_from_response("result: {} done") == {}


# ---------------------------------------------------------------------------
# _setup_provider
# ---------------------------------------------------------------------------


def test_setup_provider_uses_default_model_per_provider():
    assert make_provider("claude").model == "claude-opus-5"
    assert make_provider("gemini", api_key="AIzaKey").model == "gemini-2.0-flash"
    assert make_provider("openrouter", api_key="sk-or-x").model == "anthropic/claude-sonnet-5"


def test_setup_provider_strips_google_prefix_from_gemini_model():
    provider = make_provider("gemini", api_key="AIzaKey", model="google/gemini-2.0-flash")
    assert provider.model == "gemini-2.0-flash"


def test_setup_provider_keeps_gemini_model_without_prefix():
    provider = make_provider("gemini", api_key="AIzaKey", model="gemini-1.5-pro")
    assert provider.model == "gemini-1.5-pro"


def test_setup_provider_sets_openrouter_base_url():
    assert make_provider("openrouter", api_key="sk-or-x").base_url == "https://openrouter.ai/api/v1"


def test_setup_provider_defaults_custom_base_url_to_localhost():
    assert make_provider("custom", api_key="x" * 20).base_url == "http://localhost:8000/v1"


def test_setup_provider_honours_custom_base_url():
    provider = make_provider("custom", api_key="x" * 20, base_url="https://llm.internal/v1")
    assert provider.base_url == "https://llm.internal/v1"


def test_setup_provider_claude_has_no_base_url():
    assert make_provider("claude").base_url is None


def test_setup_provider_raises_when_no_config():
    with pytest.raises(APIError) as excinfo:
        LLMProvider(api_manager=FakeAPIManager("claude", None))
    assert "configure" in str(excinfo.value).lower()


def test_setup_provider_raises_when_api_key_missing():
    with pytest.raises(APIError) as excinfo:
        LLMProvider(api_manager=FakeAPIManager("claude", {"model": "m"}))
    assert "api key" in str(excinfo.value).lower()


def test_setup_provider_raises_for_unknown_provider():
    with pytest.raises(APIError) as excinfo:
        make_provider("definitely-not-a-provider")
    assert "unknown provider" in str(excinfo.value).lower()


def test_list_models_returns_known_ids_for_active_provider():
    assert "claude-opus-5" in make_provider("claude").list_models()
    assert make_provider("gemini", api_key="AIzaKey").list_models()[0].startswith("gemini")


# ---------------------------------------------------------------------------
# Dispatch: URL / headers / body shape per provider
# ---------------------------------------------------------------------------


def test_generate_text_claude_uses_anthropic_endpoint_and_headers(monkeypatch):
    post = fake_requests_post(claude_payload("hello from claude"))
    monkeypatch.setattr(lp.requests, "post", post)

    provider = make_provider("claude", api_key="sk-ant-abc", model="claude-3-5-haiku-20241022")
    result = provider.generate_text("hi", system="be nice", temperature=0.2, max_tokens=64)

    assert result == "hello from claude"
    call = post.last
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "sk-ant-abc"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    body = call["json"]
    assert body["model"] == "claude-3-5-haiku-20241022"
    assert body["max_tokens"] == 64
    assert body["temperature"] == 0.2
    assert body["system"] == "be nice"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_generate_text_claude_omits_system_when_absent(monkeypatch):
    post = fake_requests_post(claude_payload("ok"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude").generate_text("hi")

    assert "system" not in post.last["json"]


def test_generate_text_claude_appends_json_instruction_in_json_mode(monkeypatch):
    post = fake_requests_post(claude_payload("{}"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude").generate_text("hi", system="base", json_mode=True)

    assert post.last["json"]["system"].startswith("base")
    assert "valid JSON only" in post.last["json"]["system"]


def test_generate_text_gemini_uses_generative_language_endpoint(monkeypatch):
    post = fake_requests_post(gemini_payload("hello from gemini"))
    monkeypatch.setattr(lp.requests, "post", post)

    provider = make_provider("gemini", api_key="AIzaSecret", model="google/gemini-2.0-flash")
    result = provider.generate_text("hi", system="be terse", temperature=0.4, max_tokens=32)

    assert result == "hello from gemini"
    call = post.last
    assert call["url"].startswith(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    )
    assert "key=AIzaSecret" in call["url"]
    # Gemini takes the key in the query string, not an auth header.
    assert "Authorization" not in call["headers"]
    body = call["json"]
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    assert body["system_instruction"] == {"parts": [{"text": "be terse"}]}
    assert body["generationConfig"]["temperature"] == 0.4
    assert body["generationConfig"]["maxOutputTokens"] == 32


def test_generate_text_gemini_sets_response_schema_in_json_mode(monkeypatch):
    post = fake_requests_post(gemini_payload("{}"))
    monkeypatch.setattr(lp.requests, "post", post)
    schema = {"type": "OBJECT", "properties": {"a": {"type": "STRING"}}}

    make_provider("gemini", api_key="AIzaKey").generate_text(
        "hi", json_mode=True, response_schema=schema
    )

    gen_config = post.last["json"]["generationConfig"]
    assert gen_config["responseMimeType"] == "application/json"
    assert gen_config["responseSchema"] == schema
    # With a schema enforcing structure there is no need for the prose reminder.
    assert "system_instruction" not in post.last["json"]


def test_generate_text_gemini_adds_prose_reminder_when_no_schema(monkeypatch):
    post = fake_requests_post(gemini_payload("{}"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("gemini", api_key="AIzaKey").generate_text("hi", json_mode=True)

    text = post.last["json"]["system_instruction"]["parts"][0]["text"]
    assert "ONLY a raw JSON object" in text


def test_generate_text_gemini_raises_api_error_on_unexpected_shape(monkeypatch):
    post = fake_requests_post({"promptFeedback": {"blockReason": "SAFETY"}})
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("gemini", api_key="AIzaKey").generate_text("hi")
    assert "gemini" in str(excinfo.value).lower()


def test_generate_text_openrouter_uses_openai_shape_and_attribution_headers(monkeypatch):
    post = fake_requests_post(openai_payload("hello from openrouter"))
    monkeypatch.setattr(lp.requests, "post", post)

    provider = make_provider("openrouter", api_key="sk-or-abc")
    result = provider.generate_text("hi", system="sys")

    assert result == "hello from openrouter"
    call = post.last
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-or-abc"
    assert "HTTP-Referer" in call["headers"]
    assert call["headers"]["X-Title"] == "AnywhereCode"
    # System goes in as a leading message for OpenAI-compatible endpoints.
    assert call["json"]["messages"][0] == {"role": "system", "content": "sys"}
    assert call["json"]["messages"][1] == {"role": "user", "content": "hi"}


def test_generate_text_custom_endpoint_strips_trailing_slash(monkeypatch):
    post = fake_requests_post(openai_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    provider = make_provider("custom", api_key="x" * 20, base_url="http://localhost:9000/v1/")
    provider.generate_text("hi")

    assert post.last["url"] == "http://localhost:9000/v1/chat/completions"


def test_generate_text_custom_endpoint_sends_no_attribution_headers(monkeypatch):
    post = fake_requests_post(openai_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("custom", api_key="x" * 20).generate_text("hi")

    assert "HTTP-Referer" not in post.last["headers"]


def test_generate_text_openai_compat_omits_system_message_when_absent(monkeypatch):
    post = fake_requests_post(openai_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("openrouter", api_key="sk-or-x").generate_text("hi")

    roles = [m["role"] for m in post.last["json"]["messages"]]
    assert roles == ["user"]


def test_generate_text_openai_compat_requests_json_object_in_json_mode(monkeypatch):
    post = fake_requests_post(openai_payload("{}"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("openrouter", api_key="sk-or-x").generate_text("hi", json_mode=True)

    assert post.last["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "provider_name, config, payload",
    [
        ("claude", {"api_key": "sk-ant-x"}, claude_payload("t")),
        ("gemini", {"api_key": "AIzaX"}, gemini_payload("t")),
        ("openrouter", {"api_key": "sk-or-x"}, openai_payload("t")),
        ("custom", {"api_key": "x" * 20}, openai_payload("t")),
    ],
)
def test_generate_text_sends_a_timeout_for_every_provider(
    monkeypatch, provider_name, config, payload
):
    post = fake_requests_post(payload)
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider(provider_name, **config).generate_text("hi")

    assert post.last["timeout"] == 120


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, needle",
    [
        (401, "unauthorised"),
        (403, "unauthorised"),
        (429, "rate limit"),
        (500, "server error"),
        (503, "server error"),
    ],
)
def test_generate_text_maps_http_status_to_friendly_api_error(monkeypatch, status, needle):
    post = fake_requests_post(error_payload("upstream said no"), status=status)
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    assert needle in str(excinfo.value).lower()


def test_generate_text_auth_error_includes_provider_message(monkeypatch):
    post = fake_requests_post(error_payload("invalid x-api-key"), status=401)
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    assert "invalid x-api-key" in str(excinfo.value)


def test_generate_text_other_4xx_reports_raw_status(monkeypatch):
    post = fake_requests_post(error_payload("model not found"), status=404)
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    message = str(excinfo.value)
    assert "404" in message and "model not found" in message


def test_generate_text_survives_error_body_that_is_not_json(monkeypatch):
    def post(url, **kwargs):
        class Broken:
            status_code = 502

            def json(self):
                raise ValueError("not json")

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("502 Server Error", response=self)

        return Broken()

    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    assert "server error" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "exc, needle",
    [
        (requests.exceptions.Timeout("slow"), "timed out"),
        (requests.exceptions.ConnectionError("no route"), "connection failed"),
    ],
)
def test_generate_text_maps_network_failures_to_friendly_api_error(monkeypatch, exc, needle):
    def post(*args, **kwargs):
        raise exc

    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    assert needle in str(excinfo.value).lower()


def test_generate_text_wraps_unexpected_exceptions_as_api_error(monkeypatch):
    def post(*args, **kwargs):
        raise RuntimeError("something odd")

    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_text("hi")
    assert "something odd" in str(excinfo.value)


def test_generate_text_wraps_malformed_success_body_as_api_error(monkeypatch):
    post = fake_requests_post({"unexpected": "shape"})
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError):
        make_provider("claude").generate_text("hi")


# ---------------------------------------------------------------------------
# generate_json
# ---------------------------------------------------------------------------


def test_generate_json_parses_fenced_response(monkeypatch):
    post = fake_requests_post(claude_payload('```json\n{"a": 1}\n```'))
    monkeypatch.setattr(lp.requests, "post", post)

    assert make_provider("claude").generate_json("hi") == {"a": 1}


def test_generate_json_retries_once_with_stricter_prompt(monkeypatch):
    responses = [claude_payload("total nonsense"), claude_payload('{"a": 1}')]

    calls = []

    def post(url, **kwargs):
        calls.append(kwargs.get("json"))
        payload = responses[min(len(calls) - 1, len(responses) - 1)]
        return type(
            "R", (), {"status_code": 200, "json": lambda self, p=payload: p,
                      "raise_for_status": lambda self: None}
        )()

    monkeypatch.setattr(lp.requests, "post", post)

    assert make_provider("claude").generate_json("hi") == {"a": 1}
    assert len(calls) == 2
    assert "ONLY valid JSON" in calls[1]["messages"][0]["content"]


def test_generate_json_raises_api_error_when_both_attempts_fail(monkeypatch):
    post = fake_requests_post(claude_payload("never any json here"))
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError) as excinfo:
        make_provider("claude").generate_json("hi")
    assert "failed to parse json" in str(excinfo.value).lower()
    assert post.call_count == 2


def test_generate_json_unwraps_gemini_list_wrapped_object(monkeypatch):
    post = fake_requests_post(gemini_payload('[{"project_name": "demo"}]'))
    monkeypatch.setattr(lp.requests, "post", post)

    assert make_provider("gemini", api_key="AIzaKey").generate_json("hi") == {
        "project_name": "demo"
    }


def test_generate_json_uses_lower_temperature_than_generate_text(monkeypatch):
    # Checked on a model that still accepts sampling parameters -- the current
    # default does not, and omits `temperature` entirely. See the sampling
    # tests below.
    post = fake_requests_post(claude_payload('{"a": 1}'))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude", model="claude-sonnet-4-6").generate_json("hi")

    assert post.last["json"]["temperature"] == 0.3


# ---------------------------------------------------------------------------
# Sampling parameters
#
# temperature/top_p/top_k were removed on the Claude 5 family and on Opus
# 4.7/4.8: sending one is a 400, not a warning. The request body has to leave
# the parameter out rather than pass a default through.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "anthropic/claude-opus-5",
        "CLAUDE-OPUS-5",
    ],
)
def test_models_without_sampling_are_recognised(model):
    assert lp.supports_sampling(model) is False


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "claude-3-5-sonnet-20241022",
        "some-other-model",
        "",
    ],
)
def test_models_that_still_accept_sampling_are_recognised(model):
    assert lp.supports_sampling(model) is True


def test_temperature_is_omitted_for_the_default_model(monkeypatch):
    post = fake_requests_post(claude_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude").generate_text("hello")

    assert "temperature" not in post.last["json"]
    assert post.last["json"]["model"] == "claude-opus-5"


def test_temperature_is_sent_for_a_model_that_accepts_it(monkeypatch):
    post = fake_requests_post(claude_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude", model="claude-sonnet-4-6").generate_text("hello", temperature=0.9)

    assert post.last["json"]["temperature"] == 0.9


def test_the_rest_of_the_body_is_unchanged_when_temperature_is_dropped(monkeypatch):
    post = fake_requests_post(claude_payload("hi"))
    monkeypatch.setattr(lp.requests, "post", post)

    make_provider("claude").generate_text("hello", system="be brief", max_tokens=512)

    body = post.last["json"]
    assert body["max_tokens"] == 512
    assert body["system"] == "be brief"
    assert body["messages"][-1]["content"] == "hello"


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------


def test_test_connection_returns_true_on_non_empty_reply(monkeypatch):
    post = fake_requests_post(claude_payload("OK"))
    monkeypatch.setattr(lp.requests, "post", post)

    assert make_provider("claude").test_connection() is True


def test_test_connection_returns_false_on_blank_reply(monkeypatch):
    post = fake_requests_post(claude_payload("   "))
    monkeypatch.setattr(lp.requests, "post", post)

    assert make_provider("claude").test_connection() is False


def test_test_connection_propagates_api_error(monkeypatch):
    post = fake_requests_post(error_payload("bad key"), status=401)
    monkeypatch.setattr(lp.requests, "post", post)

    with pytest.raises(APIError):
        make_provider("claude").test_connection()


def test_no_network_fixture_blocks_accidental_real_calls(no_network):
    with pytest.raises(AssertionError) as excinfo:
        requests.post("https://example.invalid/v1", json={})
    assert "real network call" in str(excinfo.value)


def test_no_network_fixture_also_blocks_requests_get(no_network):
    with pytest.raises(AssertionError):
        requests.get("https://example.invalid/v1")
