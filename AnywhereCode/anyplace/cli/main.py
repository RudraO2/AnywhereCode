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
from anyplace.core.commit_generator import CommitGenerator
from anyplace.core.build_runner import BuildRunner
from anyplace.core.deploy_generator import DeployGenerator
from anyplace.core.ci_generator import CIGenerator
from anyplace.core.docker_generator import DockerGenerator
from anyplace.core.env_manager import EnvManager
from anyplace.core.guide_generator import GuideGenerator
from anyplace.core.doc_generator import DocGenerator

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

        # Generate plan (loop allows retry on GenerationError)
        while True:
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

                break  # Done - exit retry loop

            except APIError as e:
                exit_with_error(e, "Connecting to LLM provider")
                break
            except GenerationError as e:
                display_plan_error(str(e))
                if click.confirm("\nTry again with different parameters?"):
                    project_name = click.prompt("\n📁 Project name", default=project_name, type=str)
                    project_desc = click.prompt("\n📝 Project description (optional)", default=project_desc, type=str, show_default=False)
                    continue  # Retry
                break
            except click.Abort:
                console.print("[yellow]Cancelled[/yellow]")
                break

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


@cli.command()
@click.option("--all", "-a", "stage_all", is_flag=True, default=False,
              help="Stage all changes before committing")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show generated message without committing")
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def commit(stage_all, dry_run, project_dir):
    """Generate a smart AI commit message and commit staged changes."""
    from pathlib import Path

    path = Path(project_dir).resolve()

    if not (path / ".git").exists():
        console.print(f"[bold red]Not a git repository:[/bold red] {path}")
        console.print("Run [bold]git init[/bold] first.")
        return

    try:
        api_mgr = APIManager()
        llm = LLMProvider(api_mgr)
        commit_gen = CommitGenerator(llm)

        if stage_all:
            console.print("[dim]Staging all changes...[/dim]")

        diff = commit_gen.get_staged_diff(path) if not stage_all else commit_gen.get_unstaged_diff(path)

        if not diff.strip() and not stage_all:
            console.print("[yellow]No staged changes. Use [bold]-a[/bold] to stage everything.[/yellow]")
            return

        console.print("\n[bold cyan]🤖 Generating commit message...[/bold cyan]")
        message = commit_gen.generate_message(diff) if not stage_all else None

        if stage_all:
            import subprocess
            subprocess.run(["git", "add", "-A"], cwd=path, check=True)
            diff = commit_gen.get_staged_diff(path)
            message = commit_gen.generate_message(diff)

        from rich.panel import Panel
        console.print(Panel(message, title="📝 Proposed Commit Message", border_style="green"))

        if dry_run:
            console.print("[dim]Dry run - no commit made[/dim]")
            return

        if click.confirm("Commit with this message?"):
            import subprocess
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print("[bold green]✅ Committed![/bold green]")
            else:
                console.print(f"[bold red]Commit failed:[/bold red] {result.stderr.strip()}")

    except (GenerationError, APIError) as e:
        exit_with_error(e, "Generating commit message")
    except ConfigError as e:
        exit_with_error(e, "Checking configuration")


@cli.command()
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
@click.option("--install", is_flag=True, default=False,
              help="Run npm install before building")
def build(project_dir, install):
    """Detect project type and run the appropriate build command."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    runner = BuildRunner(path)
    project_type = runner._detect_project_type()

    console.print(f"[bold cyan]🔍 Detected project type:[/bold cyan] [bold]{project_type}[/bold]")

    try:
        if install:
            console.print("[bold cyan]📦 Installing dependencies...[/bold cyan]")
            import subprocess
            result = subprocess.run(
                runner.get_install_command(),
                cwd=path,
                capture_output=False,
            )
            if result.returncode != 0:
                console.print("[bold red]Install failed[/bold red]")
                return

        console.print(f"[bold cyan]🔨 Running build...[/bold cyan]")
        success = runner.run_build(progress_callback=lambda line: console.print(f"  [dim]{line}[/dim]"))

        if success:
            console.print("[bold green]✅ Build complete![/bold green]")

    except GenerationError as e:
        exit_with_error(e, "Building project")


@cli.command()
@click.option("--target", type=click.Choice(["eas", "github", "auto"]),
              default="auto", show_default=True, help="Deploy target")
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def deploy(target, project_dir):
    """Generate deployment configuration (EAS, GitHub Actions, etc.)."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    runner = BuildRunner(path)
    project_type = runner._detect_project_type()

    # Auto-select target based on project type
    if target == "auto":
        target = "eas" if project_type == "expo-rn" else "github"

    console.print(f"[bold cyan]🚀 Generating deploy config[/bold cyan] → [bold]{target}[/bold]")

    try:
        api_mgr = APIManager()
        llm = LLMProvider(api_mgr)
        deploy_gen = DeployGenerator(path, llm)

        result = deploy_gen.deploy(target)

        console.print("\n[bold green]✅ Deploy config generated![/bold green]")
        console.print("\n[bold]Files written:[/bold]")
        for f in result["files_written"]:
            console.print(f"  📄 {f}")

        console.print("\n[bold]Next steps:[/bold]")
        for i, step in enumerate(result["next_steps"], 1):
            console.print(f"  {i}. {step}")

    except GenerationError as e:
        exit_with_error(e, "Generating deploy config")
    except (APIError, ConfigError) as e:
        exit_with_error(e, "Checking configuration")


@cli.command()
@click.option(
    "--platform",
    type=click.Choice(["github", "gitlab", "bitbucket", "circle"]),
    default="github",
    show_default=True,
    help="CI/CD platform to generate config for",
)
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def ci(platform, project_dir):
    """Generate CI/CD pipeline configuration."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    generator = CIGenerator(path)

    console.print(f"[bold cyan]⚙️  Generating {platform} CI/CD config...[/bold cyan]")
    console.print(f"   Detected project type: [bold]{generator.project_type}[/bold]")

    try:
        files = generator.generate(platform)
        console.print(f"\n[bold green]✅ CI/CD config generated![/bold green]")
        for rel_path in files:
            console.print(f"  📄 {rel_path}")
    except GenerationError as e:
        exit_with_error(e, "Generating CI/CD config")


@cli.command()
@click.option(
    "--type", "docker_type",
    type=click.Choice(["dockerfile", "compose", "all"]),
    default="all",
    show_default=True,
    help="Which Docker files to generate",
)
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def docker(docker_type, project_dir):
    """Generate Docker and docker-compose configuration."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    generator = DockerGenerator(path)

    console.print(f"[bold cyan]🐳 Generating Docker config ({docker_type})...[/bold cyan]")
    console.print(f"   Detected project type: [bold]{generator.project_type}[/bold]")

    try:
        files = generator.generate(docker_type)
        console.print(f"\n[bold green]✅ Docker config generated![/bold green]")
        for rel_path in files:
            console.print(f"  📄 {rel_path}")

        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Review the generated Dockerfile and docker-compose.yml")
        console.print("  2. docker compose up --build")
    except GenerationError as e:
        exit_with_error(e, "Generating Docker config")


@cli.command()
@click.option("--validate", is_flag=True, default=False,
              help="Validate .env against .env.example")
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def env(validate, project_dir):
    """Generate .env.example or validate your .env file."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    manager = EnvManager()

    if validate:
        console.print("[bold cyan]🔍 Validating .env against .env.example...[/bold cyan]")
        try:
            result = manager.validate_env(path)

            if result["missing"]:
                console.print(f"\n[bold red]❌ Missing variables ({len(result['missing'])}):[/bold red]")
                for var in result["missing"]:
                    console.print(f"  • {var}")
            else:
                console.print("\n[bold green]✅ No missing variables![/bold green]")

            if result["ok"]:
                console.print(f"\n[green]✅ Present ({len(result['ok'])}):[/green]")
                for var in result["ok"]:
                    console.print(f"  • {var}")

            if result["extra"]:
                console.print(f"\n[yellow]⚠️  Extra (not in .env.example) ({len(result['extra'])}):[/yellow]")
                for var in result["extra"]:
                    console.print(f"  • {var}")

        except GenerationError as e:
            exit_with_error(e, "Validating environment")
    else:
        runner = BuildRunner(path)
        project_type = runner._detect_project_type()

        console.print(f"[bold cyan]📋 Generating .env.example...[/bold cyan]")
        console.print(f"   Detected project type: [bold]{project_type}[/bold]")

        project_name = path.name
        env_path = manager.write_env_example(path, project_type, project_name)

        console.print(f"\n[bold green]✅ Created: {env_path}[/bold green]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. cp .env.example .env")
        console.print("  2. Edit .env and fill in your values")
        console.print("  3. Run [bold]anyplace env --validate[/bold] to check for missing vars")


@cli.command()
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def guide(project_dir):
    """Show the learning guide for the project."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    runner = BuildRunner(path)
    project_type = runner._detect_project_type()

    # Try to detect template from project type
    template_map = {
        "react-vite": "web-react-vite",
        "expo-rn": "mobile-expo-rn",
        "nodejs": "backend-nodejs",
    }
    template_name = template_map.get(project_type, "web-react-vite")

    # Check if LEARNING.md exists, show it; otherwise generate on the fly
    learning_path = path / "LEARNING.md"
    if learning_path.exists():
        console.print(learning_path.read_text())
        return

    generator = GuideGenerator()
    project_name = path.name

    console.print(f"[bold cyan]📚 Generating learning guide for {project_name}...[/bold cyan]")
    content = generator.generate_learning_md(template_name, project_name)
    console.print(content)

    if click.confirm("\nSave LEARNING.md to project?"):
        learning_path.write_text(content)
        console.print(f"[bold green]✅ Saved: {learning_path}[/bold green]")


@cli.command()
@click.option(
    "--type", "doc_type",
    type=click.Choice(["contributing", "changelog", "api", "all"]),
    default="all",
    show_default=True,
    help="Which documentation to generate",
)
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def docs(doc_type, project_dir):
    """Generate project documentation (CONTRIBUTING.md, CHANGELOG.md, API docs)."""
    from pathlib import Path

    path = Path(project_dir).resolve()
    project_name = path.name

    console.print(f"[bold cyan]📝 Generating documentation ({doc_type})...[/bold cyan]")

    try:
        # Try to use LLM for API docs if configured
        llm = None
        try:
            api_mgr = APIManager()
            if api_mgr.list_providers():
                llm = LLMProvider(api_mgr)
        except Exception:
            pass

        generator = DocGenerator(path, llm)
        written = generator.generate_all(project_name, doc_type)

        console.print(f"\n[bold green]✅ Documentation generated![/bold green]")
        for name, file_path in written.items():
            console.print(f"  📄 {file_path.name}")

    except Exception as e:
        exit_with_error(e, "Generating documentation")


@cli.command()
@click.argument("file", required=False)
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
def explain(file, project_dir):
    """Explain what a file does using AI."""
    from pathlib import Path

    path = Path(project_dir).resolve()

    if not file:
        console.print("[yellow]Usage:[/yellow] anyplace explain <filename>")
        console.print("\nExample: anyplace explain src/App.tsx")
        return

    file_path = path / file
    if not file_path.exists():
        file_path = Path(file)  # Try as absolute path

    if not file_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {file}")
        return

    content = file_path.read_text(errors="ignore")
    if len(content) > 4000:
        content = content[:4000] + "\n... (truncated)"

    try:
        api_mgr = APIManager()
        llm = LLMProvider(api_mgr)

        console.print(f"[bold cyan]🔍 Explaining {file}...[/bold cyan]\n")

        system = (
            "You are a senior developer giving a code review. "
            "Explain the file clearly: what it does, why it exists, "
            "key functions/exports, and anything a new developer should know. "
            "Be concise but thorough. Use plain language."
        )
        prompt = f"Explain this file (`{file}`):\n\n```\n{content}\n```"

        explanation = llm.generate_text(
            prompt=prompt,
            system=system,
            temperature=0.3,
            max_tokens=1024,
        )

        from rich.panel import Panel
        console.print(Panel(explanation, title=f"📄 {file}", border_style="cyan"))

    except (ConfigError, APIError) as e:
        exit_with_error(e, "Explaining file")


@cli.command()
def serve():
    """Start the AnywhereCode MCP server for Claude integration."""
    console.print("[bold cyan]🔌 Starting AnywhereCode MCP server...[/bold cyan]")
    console.print("[dim]Claude can now call: list_templates, generate_plan, generate_project[/dim]")

    try:
        from anyplace.mcp.server import mcp
        mcp.run()
    except ImportError:
        console.print("[bold red]MCP package not installed.[/bold red]")
        console.print("Run: [bold]pip install 'mcp>=1.0.0'[/bold]")


if __name__ == "__main__":
    # Show main interactive menu if no subcommand
    import sys
    if len(sys.argv) == 1:
        main()
    else:
        cli(prog_name="anyplace")
