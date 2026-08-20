"""
Provider setup.

Pasting a 100-character API key into a phone keyboard is the single most
error-prone thing a new user does. So: paste it once, see it masked back,
confirm it, and test it immediately — rather than discovering the typo three
screens later inside a failed generation.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from anyplace.cli.error_handler import ConfigError
from anyplace.config.providers import needs_api_key
from anyplace.config.api_manager import APIManager
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import Choice, GoBack, ask_choice, ask_text, ask_yes_no
from anyplace.ui.theme import get_theme

PROVIDERS: Dict[str, Dict] = {
    "gemini": {
        "display_name": "Google Gemini",
        "blurb": "Free tier — best place to start",
        "docs_url": "https://aistudio.google.com/apikey",
        "key_format": "AIza…",
        "models": [
            ("gemini-2.0-flash", "Fast and free-tier friendly"),
            ("gemini-2.0-pro", "Slower, stronger"),
            ("gemini-1.5-pro", "Older, still solid"),
        ],
    },
    "claude": {
        "display_name": "Claude (Anthropic)",
        "blurb": "Best code quality, paid",
        "docs_url": "https://console.anthropic.com",
        "key_format": "sk-ant-…",
        "models": [
            ("claude-opus-5", "Recommended — most capable"),
            ("claude-sonnet-5", "Faster and cheaper"),
            ("claude-haiku-4-5", "Cheapest, good for small jobs"),
        ],
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "blurb": "One key, 100+ models",
        "docs_url": "https://openrouter.ai/keys",
        "key_format": "sk-or-…",
        "models": [
            ("anthropic/claude-sonnet-5", "Claude via OpenRouter"),
            ("google/gemini-2.0-flash-exp", "Gemini via OpenRouter"),
            ("mistralai/mistral-large", "Mistral"),
            ("meta-llama/llama-3.1-405b-instruct", "Llama, open weights"),
        ],
    },
    "omniroute": {
        "display_name": "OmniRoute",
        "blurb": "Free models via a gateway you run",
        "docs_url": "https://github.com/diegosouzapw/OmniRoute",
        "key_format": "no key needed",
        "models": [
            ("auto", "Let OmniRoute pick"),
            ("openai/gpt-oss-120b", "Open-weights, free tiers"),
            ("google/gemini-2.0-flash", "Gemini via OmniRoute"),
            ("anthropic/claude-sonnet-5", "Claude via OmniRoute"),
        ],
    },
    "custom": {
        "display_name": "Custom endpoint",
        "blurb": "Self-hosted or OpenAI-compatible",
        "docs_url": "",
        "key_format": "any string",
        "models": [
            ("gpt-4o-mini", "Example OpenAI-compatible id"),
            ("local-model", "Whatever your server calls it"),
        ],
    },
}

#: Order shown to users — free-tier first, because that is the one that lets
#: someone with no credit card get started.
PROVIDER_ORDER: List[str] = ["gemini", "claude", "openrouter", "omniroute", "custom"]


#: Shown instead of a key prompt. OmniRoute is not a service you sign up for:
#: it runs on your own device, and Anywhere Code cannot start it for you.
OMNIROUTE_NOTE = (
    "OmniRoute is a gateway you run yourself — there is no hosted URL.\n\n"
    "Install and start it:\n"
    "  npm install -g omniroute\n"
    "  omniroute\n\n"
    "It answers on localhost:20128 and needs no key. Its free models come "
    "from provider free tiers, most of which you sign up for inside "
    "OmniRoute itself."
)


def mask_key(api_key: str) -> str:
    """Show enough of a key to spot a paste error, never enough to leak it."""
    if not api_key:
        return ""
    stripped = api_key.strip()
    if len(stripped) <= 10:
        return stripped[:2] + "…" + stripped[-2:]
    return stripped[:6] + "…" + stripped[-4:]


def configure_providers(
    console=None,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    api_mgr: Optional[APIManager] = None,
) -> APIManager:
    """Walk the user through adding one or more providers."""
    if console is None:
        from rich.console import Console

        console = Console()
    layout = layout or Layout.detect()
    api_mgr = api_mgr or APIManager()

    while True:
        configured = api_mgr.list_providers()
        active = api_mgr.get_active_provider()

        choices = []
        for key in PROVIDER_ORDER:
            info = PROVIDERS[key]
            badge = ""
            if key in configured:
                badge = "active" if key == active else "set up"
            choices.append(
                Choice(
                    value=key,
                    label=info["display_name"],
                    description=info["blurb"],
                    hint=badge,
                )
            )
        if len(configured) > 1:
            choices.append(Choice(value="__active__", label="Choose the default", description="Which one to use"))
        choices.append(Choice(value="__done__", label="Done", description="Back to the menu"))

        try:
            picked = ask_choice(
                console,
                "Which AI should write your code?",
                choices,
                default="__done__" if configured else "gemini",
                layout=layout,
                input_fn=input_fn,
                allow_back=False,
                help_text="You only need one. Gemini has a free tier.",
            )
        except GoBack:
            break

        if picked == "__done__":
            break
        if picked == "__active__":
            _choose_active(console, api_mgr, layout, input_fn)
            continue

        configure_single_provider(console, api_mgr, picked, layout, input_fn)

    return api_mgr


def _choose_active(console, api_mgr: APIManager, layout: Layout, input_fn) -> None:
    configured = list(api_mgr.list_providers().keys())
    if not configured:
        return
    choices = [
        Choice(value=name, label=PROVIDERS.get(name, {}).get("display_name", name.title()))
        for name in configured
    ]
    picked = ask_choice(
        console,
        "Use which one by default?",
        choices,
        default=api_mgr.get_active_provider() or configured[0],
        layout=layout,
        input_fn=input_fn,
        allow_back=False,
    )
    api_mgr.set_active_provider(picked)
    ui.card(console, "Default is now {0}.".format(picked), title="Saved", tone="ok", layout=layout)


def configure_single_provider(
    console,
    api_mgr: APIManager,
    provider: str,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> bool:
    """Set up one provider end to end. Returns True if it got saved."""
    layout = layout or Layout.detect()
    info = PROVIDERS[provider]
    theme = get_theme()

    console.print()
    ui.rule(console, info["display_name"], layout=layout)

    wants_key = needs_api_key(provider)

    if wants_key:
        if info["docs_url"]:
            console.print("Get a key: " + info["docs_url"], style=theme.style("info"))
            console.print("It looks like: " + info["key_format"], style=theme.style("muted"))

        try:
            api_key = ask_text(
                console,
                "Paste your API key",
                layout=layout,
                input_fn=input_fn,
                help_text="Long-press the terminal to paste. It is stored only on this device.",
            )
        except GoBack:
            return False

        api_key = api_key.strip()
        if not api_key:
            ui.card(console, "No key entered — skipping.", title="Skipped", tone="warn", layout=layout)
            return False

        console.print("Read back: " + mask_key(api_key), style=theme.style("muted"))
        if not ask_yes_no(console, "Does that look right?", default=True, layout=layout, input_fn=input_fn):
            return configure_single_provider(console, api_mgr, provider, layout, input_fn)
    else:
        # Nothing to paste: the gateway holds whatever keys it needs.
        api_key = ""
        ui.card(
            console,
            OMNIROUTE_NOTE,
            title="Before this works",
            tone="info",
            layout=layout,
        )

    model_choices = [Choice(value=model_id, label=model_id, description=desc) for model_id, desc in info["models"]]
    model_choices.append(Choice(value="__custom__", label="Type a model id", description="If yours isn't listed"))
    model_id = ask_choice(
        console,
        "Which model?",
        model_choices,
        default=info["models"][0][0],
        layout=layout,
        input_fn=input_fn,
        allow_back=False,
    )
    if model_id == "__custom__":
        model_id = ask_text(console, "Model id", layout=layout, input_fn=input_fn)

    kwargs = {}
    if provider == "custom":
        kwargs["base_url"] = ask_text(
            console,
            "Base URL",
            default="http://localhost:8000/v1",
            layout=layout,
            input_fn=input_fn,
            help_text="The OpenAI-compatible root, ending in /v1",
        )
    elif provider == "omniroute":
        # Imported here rather than at module scope: llm_provider pulls in
        # `requests`, and the wizard is on the startup path.
        from anyplace.core.llm_provider import OMNIROUTE_DEFAULT_URL

        kwargs["base_url"] = ask_text(
            console,
            "Where is OmniRoute?",
            default=OMNIROUTE_DEFAULT_URL,
            layout=layout,
            input_fn=input_fn,
            help_text="Keep the default unless you changed OmniRoute's port.",
        )

    try:
        api_mgr.set_provider(provider, api_key, model_id, **kwargs)
        if len(api_mgr.list_providers()) == 1:
            api_mgr.set_active_provider(provider)
    except ConfigError as exc:
        ui.card(console, str(exc), title="That key looks wrong", tone="err", layout=layout)
        if ask_yes_no(console, "Try again?", default=True, layout=layout, input_fn=input_fn):
            return configure_single_provider(console, api_mgr, provider, layout, input_fn)
        return False

    summary = [info["display_name"], "Model: {0}".format(model_id)]
    if api_key:
        summary.append("Key: {0}".format(mask_key(api_key)))
    elif not wants_key:
        # A bare "Key:" with nothing after it reads like something failed.
        summary.append("Key: not needed")
    if kwargs.get("base_url"):
        summary.append("At: {0}".format(kwargs["base_url"]))

    ui.card(
        console,
        "\n".join(summary),
        title="Saved",
        tone="ok",
        layout=layout,
    )

    if ask_yes_no(console, "Test it now?", default=True, layout=layout, input_fn=input_fn):
        test_provider(console, api_mgr, provider, layout)
    return True


def test_provider(console, api_mgr: APIManager, provider: str, layout: Optional[Layout] = None) -> bool:
    """Round-trip one tiny request so failures surface here, not mid-build."""
    layout = layout or Layout.detect()
    from anyplace.cli.error_handler import APIError
    from anyplace.core.llm_provider import LLMProvider

    previous_active = api_mgr.get_active_provider()
    try:
        api_mgr.set_active_provider(provider)
        console.print("Testing {0}…".format(provider), style=get_theme().style("muted"))
        llm = LLMProvider(api_mgr)
        if llm.test_connection():
            ui.card(console, "Connected. You're ready to build.", title="Works", tone="ok", layout=layout)
            return True
        ui.card(console, "The provider replied, but with nothing usable.", title="Odd reply", tone="warn", layout=layout)
        return False
    except (APIError, ConfigError) as exc:
        ui.card(console, str(exc), title="Couldn't connect", tone="err", layout=layout)
        return False
    finally:
        if previous_active and previous_active != provider:
            try:
                api_mgr.set_active_provider(previous_active)
            except ConfigError:
                pass
