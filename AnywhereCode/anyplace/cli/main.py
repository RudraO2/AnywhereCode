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
from anyplace.cli.config_wizard import configure_providers, quick_setup
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


def _show_pipeline_results(result):
    """Display the agentic pipeline results in a nice table."""
    from rich.table import Table

    console.print("\n[bold cyan]⚡ Agentic Pipeline Results[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Step", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    for step in result.summary["steps"]:
        name = step["name"]
        status = step["status"]
        detail = step["detail"]

        if status == "pass":
            status_str = "[bold green]✅ Done[/bold green]"
        elif status == "skipped":
            status_str = "[yellow]⏭ Skipped[/yellow]"
        else:
            status_str = "[bold red]❌ Failed[/bold red]"

        table.add_row(name, status_str, detail[:80] if detail else "")

    console.print(table)

    passed = result.summary["passed"]
    total = result.summary["total_steps"]
    skipped = result.summary["skipped"]
    failed = result.summary["failed"]

    if failed == 0:
        console.print(f"\n[bold green]🎉 All done! {passed} passed, {skipped} skipped.[/bold green]")
        console.print(f"[bold]Your project is ready at:[/bold] {result.project_dir}")
        console.print("\n[bold cyan]What was done automatically:[/bold cyan]")
        console.print("  - Dependencies installed")
        console.print("  - Project built")
        console.print("  - Environment configured (.env)")
        console.print("  - CI/CD pipeline generated (GitHub Actions)")
        console.print("  - Docker config generated")
        console.print("  - Deployment config generated")
        console.print("  - Everything committed to git")

        # Show server info if running
        server_url = result.summary.get("server_url", "")
        if server_url:
            console.print(f"\n[bold green]🌐 Dev server running at:[/bold green] [bold]{server_url}[/bold]")
            console.print("[dim]Press Ctrl+C to stop the server[/dim]")
        else:
            console.print(f"\n[bold]To start developing:[/bold]")
            console.print(f"  cd {result.project_dir}")
    else:
        console.print(f"\n[yellow]⚠️ {passed} passed, {skipped} skipped, {failed} failed[/yellow]")
        console.print("[dim]Some steps failed but your project files are generated.[/dim]")
        console.print(f"\nProject at: {result.project_dir}")


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


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """AnywhereCode - Generate projects anywhere, anytime."""
    # Bare `anyplace` should start the interactive flow, not print help.
    # The console_scripts entry point calls this group directly, so the
    # dispatch has to live here rather than under a __main__ guard.
    if ctx.invoked_subcommand is None:
        ctx.invoke(main)


def _show_existing_project_menu():
    """
    Let the user pick an existing project and show available actions.
    Returns True if handled, False if user wants to go back.
    """
    from pathlib import Path
    projects_dir = get_projects_dir()

    # Collect existing projects (any directory inside projects_dir)
    if not projects_dir.exists():
        console.print("[yellow]No projects directory found yet.[/yellow]")
        return False

    projects = [p for p in sorted(projects_dir.iterdir()) if p.is_dir()]

    if not projects:
        console.print("[yellow]No existing projects found in:[/yellow]")
        console.print(f"  {projects_dir}")
        return False

    console.print("[bold cyan]📁 Your Existing Projects:[/bold cyan]\n")
    for i, p in enumerate(projects, 1):
        # Quick status: does it have .git?
        git_mark = "🔀" if (p / ".git").exists() else "  "
        # Count generated source files (rough estimate)
        try:
            file_count = sum(1 for _ in p.rglob("*") if _.is_file()
                             and not any(part.startswith(".") for part in _.parts[-3:])
                             and "node_modules" not in str(_))
        except Exception:
            file_count = 0
        console.print(f"  {i}. {git_mark} [bold]{p.name}[/bold]  [dim]({file_count} files)[/dim]")

    console.print(f"\n  0. ← Back to main menu")
    choice = click.prompt("\nSelect project (number)", type=int, default=0)

    if choice == 0 or choice > len(projects):
        return False

    project = projects[choice - 1]
    console.print(f"\n[bold green]📂 {project.name}[/bold green] — {project}\n")

    # Show what you can do
    actions = [
        ("apk",     "anyplace apk --dir",     "📱 Build an installable Android APK in the cloud"),
        ("run",     "anyplace run --dir",     "Run the full agentic pipeline"),
        ("commit",  "anyplace commit --dir",  "Generate AI commit message & commit"),
        ("build",   "anyplace build --dir",   "Run the project build"),
        ("deploy",  "anyplace deploy --dir",  "Generate deployment config"),
        ("ci",      "anyplace ci --dir",      "Add CI/CD pipeline"),
        ("docker",  "anyplace docker --dir",  "Add Docker config"),
        ("env",     "anyplace env --dir",     "Manage environment variables"),
        ("guide",   "anyplace guide --dir",   "Open learning guide"),
        ("docs",    "anyplace docs --dir",    "Generate documentation"),
        ("explain", "anyplace explain",       "Explain a file with AI"),
    ]

    console.print("[bold cyan]What do you want to do?[/bold cyan]\n")
    for i, (cmd, _, desc) in enumerate(actions, 1):
        console.print(f"  {i}. [bold]{cmd}[/bold] — {desc}")
    console.print(f"\n  0. ← Back")

    action_choice = click.prompt("\nChoose action (number)", type=int, default=0)
    if action_choice == 0 or action_choice > len(actions):
        return True  # Handled (went back)

    cmd_name, _, _ = actions[action_choice - 1]
    dir_str = str(project)

    # Dispatch to the right command
    import subprocess, sys
    extra = []
    if cmd_name == "explain":
        filename = click.prompt("  File to explain (relative path)")
        extra = [filename]

    console.print(f"\n[dim]Running: anyplace {cmd_name} {' '.join(extra)} --dir \"{dir_str}\"[/dim]\n")
    subprocess.run(
        ["anyplace", cmd_name, *extra, "--dir", dir_str],
        check=False,
    )
    return True


@cli.command()
@click.option("--auto", "auto_accept", is_flag=True, default=False,
              help="Auto-accept all pipeline steps (no confirmations)")
def main(auto_accept):
    """
    Interactive mode - Create a new project or continue an existing one.

    Guides you through project creation with AI assistance.
    By default, asks for confirmation before each pipeline step (human-accept mode).
    Use --auto to run everything without confirmations.
    """
    console.clear()
    console.print(BANNER, style="cyan bold")

    if auto_accept:
        console.print("[bold yellow]Mode: AUTO-ACCEPT[/bold yellow] — all steps run without confirmation\n")
    else:
        console.print("[dim]Mode: human-accept (you approve each step)[/dim]\n")

    # Check platform
    platform_info = get_platform_info()
    if platform_info["is_termux"]:
        console.print("📱 [bold yellow]Termux Mode[/bold yellow] - Projects will save to ~/Downloads/\n")
    else:
        console.print(f"🖥️  Desktop Mode - Projects will save to {get_projects_dir()}\n")

    # ── Top-level choice: new project OR continue existing ──────────────────
    console.print("[bold]What would you like to do?[/bold]")
    console.print("  1. 🆕 Create a new project")
    console.print("  2. 📂 Continue an existing project")
    top_choice = click.prompt("\nChoice", type=click.IntRange(1, 2), default=1)

    if top_choice == 2:
        _show_existing_project_menu()
        return

    try:
        # Check API configuration
        api_mgr = APIManager()
        providers = api_mgr.list_providers()

        if not providers:
            console.print("[bold yellow]👋 First time here — let's get you a model.[/bold yellow]\n")

            if not quick_setup():
                console.print("[bold red]Can't continue without an LLM provider.[/bold red]")
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
                    # Build project — fully agentic
                    try:
                        def agent_progress(step: str, msg: str):
                            """Live feedback from the agentic pipeline."""
                            console.print(f"  [cyan]⚡ {step}[/cyan] {msg}")

                        orchestrator = BuildOrchestrator(
                            plan=plan,
                            llm_provider=llm,
                            use_git=True,
                            agentic=True,
                            human_accept=not auto_accept,
                        )

                        progress = GenerationProgress(len(plan.files), project_name)
                        progress.show_generation_start()

                        # Generate + auto-install + auto-build + auto-deploy
                        success = orchestrator.build(
                            progress_callback=progress.show_file_progress,
                            agent_callback=agent_progress,
                        )

                        if success:
                            project_info = orchestrator.get_project_info()
                            progress.show_generation_complete(project_info["project_dir"])

                            # Show agentic pipeline results
                            if orchestrator.pipeline_result:
                                _show_pipeline_results(orchestrator.pipeline_result)
                                # Wait for dev server if running
                                _wait_for_server(orchestrator.pipeline_result)
                            else:
                                # Fallback if agentic mode was off
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

    except (click.Abort, EOFError, KeyboardInterrupt):
        # Ctrl+C / Ctrl+D is a normal way to leave an interactive menu, not a
        # crash — an empty red error panel here just looks broken.
        console.print("\n[yellow]Cancelled. Run [bold]anyplace[/bold] any time to come back.[/yellow]")
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
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
@click.option("--skip-deploy", is_flag=True, default=False,
              help="Skip deployment config generation")
@click.option("--auto", "auto_accept", is_flag=True, default=False,
              help="Auto-accept all steps (no confirmations)")
def run(project_dir, skip_deploy, auto_accept):
    """Run the full agentic pipeline on an existing project (install, build, CI, Docker, deploy, serve)."""
    from pathlib import Path
    from anyplace.core.agent_executor import AgentExecutor

    path = Path(project_dir).resolve()

    console.print(BANNER, style="cyan bold")
    console.print(f"[bold cyan]⚡ Running agentic pipeline on:[/bold cyan] {path}\n")

    def agent_progress(step: str, msg: str):
        console.print(f"  [cyan]⚡ {step}[/cyan] {msg}")

    executor = AgentExecutor(
        project_dir=path,
        progress_callback=agent_progress,
        human_accept=not auto_accept,
    )

    console.print(f"[bold]Detected project type:[/bold] {executor.project_type}\n")

    result = executor.run_full_pipeline(skip_deploy=skip_deploy)
    _show_pipeline_results(result)

    # If dev server is running, wait for Ctrl+C
    _wait_for_server(result)


@cli.command("login-expo")
@click.option("--token", default=None, help="Expo access token (prompted if omitted)")
def login_expo(token):
    """Save an Expo access token so `anyplace apk` can build without a browser."""
    console.print("[bold cyan]🔑 Expo login[/bold cyan]\n")
    console.print("Create an access token at:")
    console.print("  [bold]https://expo.dev/settings/access-tokens[/bold]\n")
    console.print(
        "[dim]A token is the phone-friendly option — interactive `eas login`\n"
        "needs a browser round-trip that is awkward inside Termux.[/dim]\n"
    )

    if not token:
        token = click.prompt("Paste your Expo access token", hide_input=True, default="")

    if not token.strip():
        console.print("[yellow]No token entered — nothing saved.[/yellow]")
        return

    try:
        api_mgr = APIManager()
        api_mgr.set_expo_token(token)
        console.print("\n[bold green]✅ Token saved[/bold green] to ~/.config/anyplace/config.yaml")
        console.print("Now run: [bold]anyplace apk[/bold]")
    except Exception as e:
        exit_with_error(e, "Saving Expo token")


@cli.command()
@click.option("--dir", "project_dir", type=click.Path(exists=True),
              default=".", show_default=True, help="Project directory")
@click.option("--profile", default="preview", show_default=True,
              help="EAS build profile (preview=APK, production=AAB for Play Store)")
@click.option("--platform", type=click.Choice(["android", "ios"]),
              default="android", show_default=True, help="Target platform")
@click.option("--no-wait", is_flag=True, default=False,
              help="Queue the build and exit instead of waiting for it")
@click.option("--install", is_flag=True, default=False,
              help="Download the APK and open Android's installer (Termux only)")
@click.option("--clear-cache", is_flag=True, default=False,
              help="Ignore EAS build caches")
def apk(project_dir, profile, platform, no_wait, install, clear_cache):
    """
    Build an installable Android APK in the cloud — no Android Studio, no Gradle.

    Gradle cannot realistically run on a phone, so the build happens on Expo's
    servers (EAS). Your device only uploads the source and downloads the APK.
    """
    from anyplace.core.eas_builder import EASBuilder
    from anyplace.cli import qr

    path = Path(project_dir).resolve()

    console.print("[bold cyan]📱 Cloud APK build[/bold cyan]")
    console.print(f"[dim]Project: {path}[/dim]\n")

    try:
        api_mgr = APIManager()
        expo_token = api_mgr.get_expo_token()
    except Exception:
        expo_token = None

    def progress(step: str, msg: str):
        console.print(f"  [cyan]⚡ {step}[/cyan] {msg}")

    builder = EASBuilder(path, progress_callback=progress, expo_token=expo_token)

    # Check the prerequisites before promising a 20-minute wait.
    problems = builder.preflight()
    if problems:
        console.print("[bold red]❌ Not ready to build[/bold red]\n")
        for problem in problems:
            console.print(f"  • {problem}\n")
        return

    if not no_wait:
        console.print(
            "[dim]Cloud builds usually take 8–20 minutes. Leave this running —\n"
            "the build continues on Expo's servers even if you disconnect.[/dim]\n"
        )

    try:
        result = builder.build_apk(
            platform=platform,
            profile=profile,
            wait=not no_wait,
            clear_cache=clear_cache,
        )
    except (GenerationError, APIError) as e:
        exit_with_error(e, "Building APK")
        return

    if result.files_written:
        console.print("\n[bold]Config prepared:[/bold]")
        for f in result.files_written:
            console.print(f"  📄 {f}")

    if not result.success:
        console.print(f"\n[bold red]❌ Build failed[/bold red]\n")
        console.print(result.error)
        if result.logs_url:
            console.print(f"\nLogs: {result.logs_url}")
        return

    if no_wait:
        console.print(f"\n[bold green]✅ Build queued![/bold green]")
        console.print(f"  Build ID: {result.build_id}")
        if result.logs_url:
            console.print(f"  Track it: {result.logs_url}")
        console.print("\n[dim]Come back later and run:[/dim] [bold]anyplace apk --no-wait[/bold] "
                      "[dim]to queue another, or check the link above.[/dim]")
        return

    console.print(f"\n[bold green]🎉 APK ready![/bold green]\n")
    console.print(f"  Download: [bold]{result.artifact_url}[/bold]")
    if result.logs_url:
        console.print(f"  Details:  {result.logs_url}")

    # A QR is the fastest way to move the APK to a *second* device.
    if result.artifact_url:
        console.print()
        drew = qr.print_qr(
            result.artifact_url,
            console=console,
            label="[bold cyan]Scan to install on another phone:[/bold cyan]\n",
        )
        if not drew:
            console.print("[dim]Install `qrcode` for a scannable code: pip install qrcode[/dim]")

    # On the phone that ran the build, skip the QR entirely and just install.
    if install and result.artifact_url:
        try:
            downloads = get_projects_dir()
            apk_path = builder.download_artifact(result.artifact_url, downloads)
            console.print(f"\n[bold green]⬇️  Saved:[/bold green] {apk_path}")

            if builder.open_on_device(apk_path):
                console.print("[bold green]📲 Opening Android installer…[/bold green]")
            else:
                console.print("[dim]Open that file in your file manager to install.[/dim]")
        except Exception as e:
            console.print(f"[yellow]Could not download automatically: {e}[/yellow]")
            console.print(f"[dim]Use the URL above instead.[/dim]")


@cli.command()
def doctor():
    """Check that everything AnywhereCode needs is installed and configured."""
    import shutil
    import subprocess
    from rich.table import Table

    from anyplace.core.llm_provider import omniroute_is_running

    console.print("[bold cyan]🩺 AnywhereCode doctor[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Fix / detail", style="dim")

    problems = 0

    def add(name: str, ok: bool, detail: str = "", optional: bool = False):
        nonlocal problems
        if ok:
            table.add_row(name, "[green]✅[/green]", detail)
        elif optional:
            table.add_row(name, "[yellow]○ optional[/yellow]", detail)
        else:
            problems += 1
            table.add_row(name, "[red]❌[/red]", detail)

    def version_of(binary: str, *args) -> str:
        try:
            out = subprocess.run(
                [binary, *args], capture_output=True, text=True, timeout=20
            )
            return (out.stdout or out.stderr).strip().splitlines()[0][:40]
        except (subprocess.SubprocessError, OSError, IndexError):
            return ""

    # Core tooling
    import sys
    py_ok = sys.version_info >= (3, 8)
    add("Python ≥ 3.8", py_ok, f"found {sys.version.split()[0]}")

    git_ok = shutil.which("git") is not None
    add("git", git_ok, version_of("git", "--version") or "install: pkg install git")

    node_ok = shutil.which("node") is not None
    add("Node.js", node_ok,
        version_of("node", "--version") if node_ok else "needed for JS projects & EAS: pkg install nodejs")

    # Platform
    platform_info = get_platform_info()
    if platform_info["is_termux"]:
        storage_ok = (Path.home() / "storage").exists()
        add("Termux storage access", storage_ok,
            "projects save to ~/storage/downloads" if storage_ok
            else "run: termux-setup-storage")
    else:
        add("Projects directory", True, str(get_projects_dir()))

    # LLM provider
    try:
        api_mgr = APIManager()
        providers = api_mgr.list_providers()
        if providers:
            active = api_mgr.get_active_provider() or list(providers)[0]
            model = providers[active].get("model", "?")
            add("LLM provider", True, f"{active} ({model})")
        else:
            add("LLM provider", False, "run: anyplace configure")
    except Exception as e:
        add("LLM provider", False, str(e)[:60])

    # Free gateway
    add("OmniRoute gateway", omniroute_is_running(),
        "free tokens, no key — start with: npm i -g omniroute && omniroute",
        optional=True)

    # Mobile build chain
    expo_token = None
    try:
        expo_token = APIManager().get_expo_token()
    except Exception:
        pass
    add("Expo token (APK builds)", bool(expo_token),
        "run: anyplace login-expo" if not expo_token else "configured",
        optional=True)

    qr_ok = _qr_available()
    add("QR rendering", qr_ok,
        "available" if qr_ok else "scannable APK links: pip install qrcode",
        optional=True)

    console.print(table)

    if problems == 0:
        console.print("\n[bold green]✅ All good — you're ready to build.[/bold green]")
        console.print("Start with: [bold]anyplace[/bold]")
    else:
        console.print(f"\n[bold yellow]⚠️  {problems} thing(s) need attention.[/bold yellow]")
        console.print("Fix the ❌ rows above, then re-run [bold]anyplace doctor[/bold].")


def _qr_available() -> bool:
    """Whether the optional QR dependency is importable."""
    from anyplace.cli import qr

    return qr.is_available()


@cli.command()
def serve():
    """Start the AnywhereCode MCP server so AI agents can drive the tool."""
    console.print("[bold cyan]🔌 Starting AnywhereCode MCP server...[/bold cyan]")
    console.print("[dim]MCP clients can now call: list_templates, generate_plan, generate_project[/dim]")

    try:
        from anyplace.mcp.server import mcp
        mcp.run()
    except ImportError:
        console.print("[bold red]MCP package not installed.[/bold red]")
        console.print("Run: [bold]pip install 'mcp>=1.0.0'[/bold]")


def _wait_for_server(result):
    """If a dev server process was started, wait for user to Ctrl+C."""
    if not hasattr(result, 'server_process') or not result.server_process:
        return

    proc = result.server_process
    if proc.poll() is not None:
        return  # Already exited

    console.print(f"\n[bold green]🌐 Dev server is running at {result.server_url}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        # Stream server output to console
        for line in proc.stdout:
            console.print(f"  [dim]{line.rstrip()}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping dev server...[/yellow]")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        console.print("[green]Server stopped.[/green]")


if __name__ == "__main__":
    cli(prog_name="anyplace")
