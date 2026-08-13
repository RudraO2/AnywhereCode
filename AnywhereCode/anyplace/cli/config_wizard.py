"""
Configuration wizard for setting up LLM providers.

Interactive setup for API keys and model selection.
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from anyplace.config.api_manager import APIManager
from anyplace.cli.error_handler import ConfigError

console = Console()

# Provider information.
#
# Order matters — this is the list a first-time user sees, and OmniRoute is
# first because it is the only option that needs no signup, no credit card
# and no API key at all.
PROVIDERS = {
    "omniroute": {
        "display_name": "OmniRoute — FREE, no API key, no signup ⭐",
        "docs_url": "https://github.com/diegosouzapw/OmniRoute",
        "key_format": "(optional)",
        "key_help": (
            "OmniRoute is a free MIT-licensed gateway you run locally. It pools\n"
            "the free tiers of 90+ providers (~1.5 billion tokens/month) behind\n"
            "one endpoint, and the `auto` model works with NO API key at all."
        ),
        "keyless": True,
        "models": [
            ("auto", "Recommended - auto-routes across free providers, falls over on quota"),
            ("google/gemini-2.0-flash", "Pin to Gemini Flash"),
            ("groq/llama-3.3-70b-versatile", "Pin to Llama on Groq (very fast)"),
        ],
    },
    "claude": {
        "display_name": "Claude (Anthropic)",
        "docs_url": "https://console.anthropic.com",
        "key_format": "sk-ant-...",
        "key_help": "Get your API key from https://console.anthropic.com",
        "models": [
            ("claude-3-5-sonnet-20241022", "Recommended - Fast & smart"),
            ("claude-3-5-haiku-20241022", "Cheap - Good for learning"),
            ("claude-3-opus-20250219", "Most powerful"),
        ]
    },
    "gemini": {
        "display_name": "Google Gemini",
        "docs_url": "https://aistudio.google.com",
        "key_format": "AIza...",
        "key_help": "Get your API key from https://aistudio.google.com/apikey",
        "models": [
            ("gemini-2.0-flash", "Recommended - Fast & cheap"),
            ("gemini-2.0-pro", "More powerful"),
            ("gemini-1.5-pro", "Alternative"),
        ]
    },
    "openrouter": {
        "display_name": "OpenRouter (100+ models, free tier available)",
        "docs_url": "https://openrouter.ai",
        "key_format": "sk-or-...",
        "key_help": (
            "Get a free API key from https://openrouter.ai/keys\n"
            "No credit card needed — `:free` models work on a $0 balance."
        ),
        "models": [
            # `:free` variants first: a new user with a $0 balance can run
            # these immediately, which is the whole point of listing them.
            ("deepseek/deepseek-chat-v3-0324:free", "FREE - strong at code"),
            ("qwen/qwen-2.5-coder-32b-instruct:free", "FREE - code specialist"),
            ("meta-llama/llama-3.3-70b-instruct:free", "FREE - general purpose"),
            ("anthropic/claude-3.5-sonnet", "Paid - best quality"),
            ("google/gemini-2.0-flash-exp", "Paid - fast"),
        ]
    },
    "custom": {
        "display_name": "Custom API Endpoint",
        "docs_url": "https://docs.yourapi.com",
        "key_format": "your-api-key",
        "key_help": "Provide your custom API endpoint details",
        "models": [
            ("gpt-4", "Example: OpenAI compatible"),
            ("your-model-id", "Your custom model ID"),
        ]
    }
}


def quick_setup() -> bool:
    """
    First-run fast path: get to a working provider in as few taps as possible.

    A newcomer on a phone will not go and create an Anthropic account before
    trying the tool, so the default branch here is the one that needs nothing.

    Returns:
        True if a provider ended up configured.
    """
    api_mgr = APIManager()

    console.print(Panel(
        Text.from_markup(
            "[bold]1.[/bold] 🆓 Free, no signup — OmniRoute gateway "
            "[dim](~1.5B free tokens/month)[/dim]\n"
            "[bold]2.[/bold] 🔑 I already have an API key "
            "[dim](Claude, Gemini, OpenRouter…)[/dim]"
        ),
        title="⚡ Pick how you want to power AnywhereCode",
        border_style="cyan",
    ))

    choice = click.prompt("\nChoice", type=click.IntRange(1, 2), default=1)

    if choice == 1:
        configure_single_provider(api_mgr, "omniroute")
    else:
        configure_providers()

    return bool(api_mgr.list_providers())


def configure_providers():
    """Interactive provider configuration wizard."""
    api_mgr = APIManager()

    while True:
        console.print("[bold cyan]Which provider would you like to configure?[/bold cyan]\n")

        providers_list = list(PROVIDERS.keys())
        for i, provider in enumerate(providers_list, 1):
            display = PROVIDERS[provider]["display_name"]
            console.print(f"  {i}. {display}")

        console.print(f"  {len(providers_list) + 1}. Done (skip)")

        choice = click.prompt(
            "Select (number)",
            type=click.IntRange(1, len(providers_list) + 1)
        )

        if choice == len(providers_list) + 1:
            break

        provider_key = providers_list[choice - 1]
        configure_single_provider(api_mgr, provider_key)


def _check_omniroute() -> bool:
    """
    Probe for a local OmniRoute gateway, printing setup help if it is absent.

    Returns True when the gateway is reachable.
    """
    from anyplace.core.llm_provider import omniroute_is_running, OMNIROUTE_DEFAULT_URL

    console.print("[dim]Looking for a local OmniRoute gateway…[/dim]")

    if omniroute_is_running():
        console.print(f"[bold green]✅ Found OmniRoute[/bold green] at {OMNIROUTE_DEFAULT_URL}\n")
        return True

    console.print("[yellow]No gateway running yet.[/yellow] Start one with:\n")
    console.print("  [bold]npm install -g omniroute && omniroute[/bold]\n")
    console.print(
        "[dim]It runs on port 20128 and needs no account. Leave it running in a\n"
        "second Termux session (swipe from the left edge → New session).[/dim]\n"
    )
    return False


def configure_single_provider(api_mgr: APIManager, provider: str):
    """Configure a single provider."""
    info = PROVIDERS[provider]
    keyless = info.get("keyless", False)

    console.print(f"\n[bold cyan]Setting up {info['display_name']}[/bold cyan]\n")
    console.print(f"Documentation: {info['docs_url']}\n")
    console.print(info["key_help"])
    console.print()

    if provider == "omniroute":
        running = _check_omniroute()
        if not running and not click.confirm(
            "Save this config anyway and start the gateway later?", default=True
        ):
            return

    if keyless:
        # The gateway accepts anonymous requests for free providers, so an
        # empty key is a valid answer here — not a cancelled setup.
        api_key = click.prompt(
            "API key (press Enter to skip — free providers need none)",
            hide_input=True,
            default="",
            show_default=False,
        )
    else:
        api_key = click.prompt(
            "Enter API key",
            hide_input=True,
            confirmation_prompt=False,
        )

        if not api_key:
            console.print("[yellow]Skipped[/yellow]")
            return

    # Select model
    console.print(f"\n[bold]Available models:[/bold]")
    for i, (model_id, description) in enumerate(info["models"], 1):
        console.print(f"  {i}. {model_id}")
        console.print(f"     {description}")

    model_choice = click.prompt(
        "\nSelect model (number or custom)",
        type=str,
        default="1"
    )

    if model_choice.isdigit():
        idx = int(model_choice) - 1
        if 0 <= idx < len(info["models"]):
            model_id = info["models"][idx][0]
        else:
            console.print("[red]Invalid choice[/red]")
            return
    else:
        model_id = model_choice

    # Endpoint URL — required for custom, overridable for OmniRoute
    kwargs = {}
    if provider == "custom":
        kwargs["base_url"] = click.prompt(
            "Base URL (e.g., https://api.example.com/v1)",
            type=str,
        )
    elif provider == "omniroute":
        from anyplace.core.llm_provider import OMNIROUTE_DEFAULT_URL

        kwargs["base_url"] = click.prompt(
            "Gateway URL",
            type=str,
            default=OMNIROUTE_DEFAULT_URL,
        )

    # Save configuration
    try:
        api_mgr.set_provider(provider, api_key, model_id, **kwargs)

        # Set as active if first provider
        if len(api_mgr.list_providers()) == 1:
            api_mgr.set_active_provider(provider)

        panel_text = Text()
        panel_text.append(f"Provider: {provider.upper()}\n")
        panel_text.append(f"Model: {model_id}\n")
        if kwargs.get("base_url"):
            panel_text.append(f"Endpoint: {kwargs['base_url']}\n")
        if keyless and not api_key:
            panel_text.append("Auth: none (keyless free tier)")

        console.print(
            Panel(panel_text, title="✅ Configured", border_style="green")
        )

    except ConfigError as e:
        console.print(f"\n[bold red]Configuration Error:[/bold red] {e}")


if __name__ == "__main__":
    configure_providers()
