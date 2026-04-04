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
from anyplace.cli.error_handler import handle_error, exit_with_error, ConfigError, GenerationError, APIError
from anyplace.cli.config_wizard import configure_providers
from anyplace.cli.templates import list_available_templates, get_template_info
from anyplace.core.plan_generator import PlanGenerator
from anyplace.core.llm_provider import LLMProvider
from anyplace.core.build_orchestrator import BuildOrchestrator
from anyplace.cli.plan_preview import show_plan_approval_screen, display_plan_error
from anyplace.cli.progress import GenerationProgress

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

        # Generate plan
        try:
            console.print("\n[bold cyan]🤖 Generating project plan...[/bold cyan]")
            api_mgr = APIManager()
            llm = LLMProvider(api_mgr)
            generator = PlanGenerator(llm)

            plan = generator.generate_plan(
                template_name=selected_template,
                project_name=project_name,
                description=project_desc,
            )

            console.print("[bold green]✅ Plan generated![/bold green]")

            # Show plan for approval
            if show_plan_approval_screen(plan):
                # Build project
                try:
                    orchestrator = BuildOrchestrator(
                        plan=plan,
                        llm_provider=llm,
                        use_git=True,
                    )

                    progress = GenerationProgress(len(plan.files), project_name)
                    progress.show_generation_start()

                    # Generate with progress callback
                    success = orchestrator.build(
                        progress_callback=progress.show_file_progress,
                    )

                    if success:
                        project_info = orchestrator.get_project_info()
                        progress.show_generation_complete(project_info["project_dir"])

                        console.print("\n[bold]Next steps:[/bold]")
                        for i, step in enumerate(plan.next_steps, 1):
                            console.print(f"  {i}. {step}")

                except (GenerationError, APIError) as e:
                    progress.show_generation_error(str(e))
                    if click.confirm("\nKeep generated files for manual review?"):
                        pass  # Keep files
                    else:
                        console.print("[dim]Files cleaned up[/dim]")

            else:
                console.print("[yellow]Generation cancelled[/yellow]")

        except APIError as e:
            exit_with_error(e, "Connecting to LLM provider")
        except GenerationError as e:
            display_plan_error(str(e))
            if click.confirm("\nTry again with different parameters?"):
                # Recursively call main to restart
                return
        except click.Abort:
            console.print("[yellow]Cancelled[/yellow]")

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
def test_providers():
    """Test LLM provider connectivity."""
    console.clear()
    console.print(BANNER, style="cyan bold")
    console.print("[bold cyan]🧪 Testing API Connections[/bold cyan]\n")

    try:
        api_mgr = APIManager()
        providers = api_mgr.list_providers()

        if not providers:
            console.print("[yellow]⚠️  No providers configured[/yellow]")
            console.print("Run: [bold]anyplace configure[/bold] to set up\n")
            return

        all_ok = True

        for provider_name in providers:
            config = api_mgr.get_provider(provider_name)
            model = config.get("model", "unknown")

            console.print(f"Testing {provider_name.upper()} ({model})... ", end="", flush=True)

            try:
                llm = LLMProvider(api_mgr)
                if llm.test_connection():
                    console.print("[green]✅ OK[/green]")
                else:
                    console.print("[yellow]⚠️  Connection test returned unexpected result[/yellow]")
                    all_ok = False
            except (APIError, ConfigError) as e:
                console.print(f"[red]❌ Failed[/red]")
                console.print(f"   Error: {e}\n")
                all_ok = False

        if all_ok:
            console.print("\n[bold green]✅ All providers working![/bold green]")
        else:
            console.print("\n[bold yellow]⚠️  Some providers failed. Check your API keys.[/bold yellow]")

    except Exception as e:
        exit_with_error(e, "Testing providers")


if __name__ == "__main__":
    # Show main interactive menu if no subcommand
    import sys
    if len(sys.argv) == 1:
        main()
    else:
        cli(prog_name="anyplace")
