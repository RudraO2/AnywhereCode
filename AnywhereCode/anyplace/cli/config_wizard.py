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

# Provider information
PROVIDERS = {
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
        "display_name": "OpenRouter (Access 100+ Models)",
        "docs_url": "https://openrouter.ai",
        "key_format": "sk-or-...",
        "key_help": "Get your API key from https://openrouter.ai/keys",
        "models": [
            ("anthropic/claude-3.5-sonnet", "Claude via OpenRouter"),
            ("google/gemini-2.0-flash-exp", "Gemini via OpenRouter"),
            ("mistralai/mistral-large", "Mistral - Alternative"),
            ("meta-llama/llama-3.1-405b-instruct", "Llama - Open source"),
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


def configure_single_provider(api_mgr: APIManager, provider: str):
    """Configure a single provider."""
    info = PROVIDERS[provider]

    console.print(f"\n[bold cyan]Setting up {info['display_name']}[/bold cyan]\n")
    console.print(f"Documentation: {info['docs_url']}\n")

    # Get API key
    console.print(info["key_help"])
    api_key = click.prompt(
        "\nEnter API key",
        hide_input=True,
        confirmation_prompt=False
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

    # Handle custom endpoint
    kwargs = {}
    if provider == "custom":
        base_url = click.prompt(
            "Base URL (e.g., https://api.example.com)",
            type=str
        )
        kwargs["base_url"] = base_url

    # Save configuration
    try:
        api_mgr.set_provider(provider, api_key, model_id, **kwargs)

        # Set as active if first provider
        if len(api_mgr.list_providers()) == 1:
            api_mgr.set_active_provider(provider)

        panel_text = Text()
        panel_text.append(f"Provider: {provider.upper()}\n")
        panel_text.append(f"Model: {model_id}\n")
        if provider == "custom" and kwargs:
            panel_text.append(f"Endpoint: {kwargs['base_url']}")

        console.print(
            Panel(panel_text, title="✅ Configured", border_style="green")
        )

    except ConfigError as e:
        console.print(f"\n[bold red]Configuration Error:[/bold red] {e}")


if __name__ == "__main__":
    configure_providers()
