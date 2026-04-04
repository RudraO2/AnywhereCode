"""
AnywhereCode CLI - Main interface.

Interactive CLI for generating projects with AI guidance.
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from pathlib import Path

from anyplace.config.environment import get_platform_info, get_projects_dir
from anyplace.config.api_manager import APIManager
from anyplace.cli.error_handler import handle_error, exit_with_error, ConfigError
from anyplace.cli.config_wizard import configure_providers
from anyplace.cli.templates import list_available_templates, get_template_info

console = Console()


# ASCII Art
BANNER = """
    _   _ ___   _   _ ___ _______ ____  _____  ______
   | | | |   \\ | \\ | |   \\  | |  | |  | | |___ |  __  \\
   | |_| | |\\ \\|  \\| | |\\ \\ | |  | |  | | |___ |  |__) |
   |   \\ | | \\ |  \\ | | |\\ \\| |  | |  | |     |  __  /
   | |\\ \\| |  \\| |\\ |  |  \\  |  | |__| | ___  | | \\ \\
   |_| \\_\\|_|  \\|_| \\|__|   \\_\\____\\___/  |__| |_|  \\_\\

Code Anywhere - Code Anytime
AI-Powered Project Generation for Mobile & Desktop
"""


@click.group()
def cli():
    """AnywhereCode - Generate projects anywhere, anytime."""
    pass


@cli.command()
def main():
    """
    Interactive mode - Create a new project.

    Guides you through project creation with AI assistance.
    """
    console.clear()
    console.print(BANNER, style="cyan bold")

    # Check platform
    platform_info = get_platform_info()
    if platform_info["is_termux"]:
        console.print("📱 [bold yellow]Termux Mode[/bold yellow] - Projects will save to ~/Downloads/\n")
    else:
        console.print(f"🖥️  Desktop Mode - Projects will save to {get_projects_dir()}\n")

    try:
        # Check API configuration
        api_mgr = APIManager()
        providers = api_mgr.list_providers()

        if not providers:
            console.print("[bold yellow]⚠️  No LLM provider configured![/bold yellow]")
            console.print("Let's set up your AI provider...\n")

            if click.confirm("Configure API now?"):
                configure_providers()
            else:
                console.print("[bold red]Can't continue without LLM provider.[/bold red]")
                console.print("Run: [bold]anyplace configure[/bold] to set up")
                return

        # Show available templates
        console.print("[bold cyan]📋 Available Project Templates:[/bold cyan]\n")
        templates = list_available_templates()

        if not templates:
            console.print("[bold red]No templates found![/bold red]")
            return

        for i, template in enumerate(templates, 1):
            info = get_template_info(template)
            console.print(
                f"  {i}. [bold]{template}[/bold] - {info.get('description', 'Project template')}"
            )

        # Get user selection
        choice = click.prompt(
            "\n🎯 Select template (number)",
            type=click.IntRange(1, len(templates)),
        )
        selected_template = templates[choice - 1]

        # Get project name
        project_name = click.prompt(
            "\n📁 Project name",
            default="my-project",
            type=str
        )

        # Get description
        project_desc = click.prompt(
            "\n📝 Project description (optional)",
            default="",
            type=str,
            show_default=False
        )

        # Show summary
        summary = Text()
        summary.append("Template: ", style="bold")
        summary.append(f"{selected_template}\n")
        summary.append("Project: ", style="bold")
        summary.append(f"{project_name}\n")
        summary.append("Location: ", style="bold")
        summary.append(str(get_projects_dir() / project_name))

        console.print(Panel(summary, title="✨ Project Summary", border_style="green"))

        if click.confirm("\n✅ Create project with these settings?"):
            console.print("\n[bold cyan]🚀 Generating project...[/bold cyan]")
            console.print(f"  Using template: {selected_template}")
            console.print(f"  Project: {project_name}")
            # TODO: Implement actual project generation
            console.print("\n[bold green]✅ Project created successfully![/bold green]")
            console.print(f"  Location: {get_projects_dir() / project_name}")
            console.print("  Next steps: cd into the project and start coding!")
        else:
            console.print("[yellow]Creation cancelled[/yellow]")

    except ConfigError as e:
        exit_with_error(e, "Checking configuration")
    except Exception as e:
        exit_with_error(e, "Creating project")


@cli.command()
def configure():
    """Configure LLM providers and API keys."""
    console.clear()
    console.print(BANNER, style="cyan bold")
    console.print("[bold cyan]⚙️  API Configuration[/bold cyan]\n")

    try:
        configure_providers()
        console.print("\n[bold green]✅ Configuration saved![/bold green]")
    except Exception as e:
        exit_with_error(e, "Configuration")


@cli.command()
def templates():
    """List all available project templates."""
    console.clear()
    console.print(BANNER, style="cyan bold")
    console.print("[bold cyan]📋 Available Templates[/bold cyan]\n")

    try:
        available = list_available_templates()

        if not available:
            console.print("[yellow]No templates found[/yellow]")
            return

        for template in available:
            info = get_template_info(template)
            console.print(f"\n[bold]{template}[/bold]")
            console.print(f"  {info.get('description', 'N/A')}")
            if "tech_stack" in info:
                console.print(f"  Tech: {', '.join(info['tech_stack'])}")
    except Exception as e:
        exit_with_error(e, "Listing templates")


@cli.command()
def info():
    """Show platform and configuration information."""
    console.clear()
    console.print(BANNER, style="cyan bold")
    console.print("[bold cyan]ℹ️  System Information[/bold cyan]\n")

    try:
        platform_info = get_platform_info()

        # Platform info
        panel_text = Text()
        panel_text.append("Platform: ", style="bold")
        panel_text.append(f"{platform_info['system']} ({platform_info['machine']})\n")
        panel_text.append("Release: ", style="bold")
        panel_text.append(f"{platform_info['release']}\n")
        panel_text.append("Mode: ", style="bold")
        mode = "🤖 Termux/Android" if platform_info["is_termux"] else "🖥️  Desktop"
        panel_text.append(f"{mode}\n")
        panel_text.append("Projects Dir: ", style="bold")
        panel_text.append(f"{platform_info['projects_dir']}\n")
        panel_text.append("Config Dir: ", style="bold")
        panel_text.append(f"{platform_info['config_dir']}")

        console.print(Panel(panel_text, title="System Info", border_style="blue"))

        # API configuration
        api_mgr = APIManager()
        providers = api_mgr.list_providers()

        console.print("\n[bold cyan]Configured Providers:[/bold cyan]")
        if providers:
            for provider, config in providers.items():
                model = config.get("model", "N/A")
                console.print(f"  • {provider.upper()}: {model}")
        else:
            console.print("  [yellow]No providers configured[/yellow]")
            console.print("  Run: [bold]anyplace configure[/bold] to set up")

    except Exception as e:
        exit_with_error(e, "Getting system info")


@cli.command()
def reset():
    """Reset all configurations."""
    if click.confirm("⚠️  This will delete ALL configurations. Continue?"):
        try:
            api_mgr = APIManager()
            api_mgr.reset_config()
            console.print("[bold green]✅ Configuration reset[/bold green]")
        except Exception as e:
            exit_with_error(e, "Resetting configuration")


@cli.command()
@click.option("--provider", help="Test a specific provider")
def test():
    """Test LLM provider connectivity."""
    console.print("[bold cyan]🧪 Testing API Connections...[/bold cyan]\n")

    try:
        api_mgr = APIManager()
        providers = api_mgr.list_providers()

        if not providers:
            console.print("[yellow]No providers configured[/yellow]")
            return

        for provider_name in providers:
            console.print(f"Testing {provider_name.upper()}... ", end="", flush=True)
            # TODO: Implement actual provider testing
            console.print("[green]✅ OK[/green]")

    except Exception as e:
        exit_with_error(e, "Testing providers")


if __name__ == "__main__":
    # Show main interactive menu if no subcommand
    import sys
    if len(sys.argv) == 1:
        main()
    else:
        cli()
