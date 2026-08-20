"""
Command line entry point for Anywhere Code.

Typing `anywhere` with no arguments opens the interactive shell. Every screen in
that shell is also a plain subcommand, so anything you can tap you can also
script.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from anyplace import DESCRIPTION, NAME, TAGLINE, __version__
from anyplace.cli.error_handler import (
    APIError,
    ConfigError,
    GenerationError,
    exit_with_error,
    handle_error,
)
from anyplace.ui.layout import Layout
from anyplace.ui.theme import get_theme


def _console(layout: Optional[Layout] = None):
    """
    A console that renders at the width the app has decided on.

    Rich detects its own width, which is *not* the same number: ANYWHERE_WIDTH
    (documented for users whose Termux font reports nonsense) is invisible to
    it. Leaving them to disagree meant a 60-column layout being padded out to
    rich's 80, so tables ran off the side of the screen -- for exactly the
    users who set the variable to stop that happening.

    Layout is the single source of truth; the console follows it.
    """
    from rich.console import Console

    layout = layout or Layout.detect()
    return Console(width=layout.width, no_color=not layout.color)


def _ctx(width: Optional[int] = None):
    """Console + layout, resolved once per command, always in agreement."""
    layout = Layout.detect(width=width)
    return _console(layout), layout


dir_option = click.option(
    "--dir",
    "project_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project directory to work in.",
)


#: `anywhere --help` groups commands by what the user is trying to do, rather
#: than listing 20-odd names alphabetically. Order here is the order shown.
#: Anything not listed falls into "More" automatically, so adding a command
#: never silently drops it from the help.
COMMAND_GROUPS = (
    ("Start here", ("start", "new", "recipes", "templates", "open")),
    ("Work on a project", ("run", "build", "commit", "explain", "guide", "docs")),
    ("Ship it", ("deploy", "ci", "docker", "env")),
    ("Setup", ("configure", "doctor", "test-providers", "info", "reset")),
)


def _render_sections(sections) -> str:
    """
    Render `(heading, [(name, description), ...])` pairs as help text.

    Click's built-in definition list is a two-column table: on a phone the
    name column eats most of the width and every description is truncated to
    "Build the project...", or -- for options, whose names are longer -- simply
    overflows the screen. Below a usable width we stack instead: name on its
    own line, description wrapped beneath.

    Rendered through rich but returned as text, so callers can hand it to
    click's formatter and keep it in the right place relative to the usage
    block click writes itself.
    """
    import io

    from rich.console import Console

    stdout, layout = _ctx()
    theme = get_theme()
    from anyplace.ui import components as ui

    sections = [(h, rows) for h, rows in sections if rows]
    if not sections:
        return ""

    buffer = Console(
        file=io.StringIO(),
        width=layout.width,
        force_terminal=stdout.is_terminal,
        no_color=not layout.color,
        highlight=False,
        soft_wrap=True,
    )

    # Two columns only when the widest name still leaves room to read.
    widest = max(len(name) for _, rows in sections for name, _ in rows)
    stacked = layout.narrow or (layout.body_width - widest - 4) < 24

    for heading, rows in sections:
        buffer.print()
        buffer.print(heading + ":", style=theme.style("accent"))
        for name, help_text in rows:
            if stacked:
                buffer.print("  " + name, style=theme.style("value"))
                if help_text:
                    buffer.print(
                        ui.wrap(help_text, max(12, layout.body_width - 4), indent="    "),
                        style=theme.style("muted"),
                    )
            else:
                pad = " " * (widest + 4)
                body = ui.wrap(
                    help_text, max(12, layout.body_width - widest - 4), indent=pad
                ).lstrip()
                buffer.print(
                    "  " + name + " " * (widest - len(name) + 2) + body,
                    style=theme.style("muted"),
                )

    return buffer.file.getvalue().rstrip("\n")


class NarrowHelp:
    """Mixin: render the options list so it survives a narrow screen.

    Click reserves a fixed first column for option names like
    ``--width INTEGER``. Below about 30 columns the help text beside it no
    longer fits and simply runs off the edge -- on the one command a stuck
    user is most likely to reach for.
    """

    def format_options(self, ctx, formatter):
        records = []
        for param in self.get_params(ctx):
            record = param.get_help_record(ctx)
            if record is not None:
                records.append(record)

        text = _render_sections([("Options", records)])
        if text:
            formatter.write(text)

        # Groups list their subcommands after the options, as click does.
        commands = getattr(self, "format_commands", None)
        if commands is not None:
            commands(ctx, formatter)


class AnywhereCommand(NarrowHelp, click.Command):
    """A subcommand whose --help fits the screen."""


class AnywhereGroup(NarrowHelp, click.Group):
    """A group whose bare invocation opens the interactive shell."""

    #: Subcommands get the same narrow-screen help treatment.
    command_class = AnywhereCommand

    def resolve_command(self, ctx, args):
        return super().resolve_command(ctx, args)

    def grouped_commands(self, ctx):
        """
        (heading, [(name, short help), ...]) pairs covering every command.

        Commands missing from COMMAND_GROUPS are collected under "More" so a
        newly added command can never disappear from `--help`.
        """
        names = set(self.list_commands(ctx))
        sections = []

        for heading, wanted in COMMAND_GROUPS:
            rows = []
            for name in wanted:
                if name in names:
                    names.discard(name)
                    command = self.get_command(ctx, name)
                    if command is not None and not command.hidden:
                        rows.append((name, command.get_short_help_str(limit=200)))
            if rows:
                sections.append((heading, rows))

        leftovers = []
        for name in sorted(names):
            command = self.get_command(ctx, name)
            if command is not None and not command.hidden:
                leftovers.append((name, command.get_short_help_str(limit=200)))
        if leftovers:
            sections.append(("More", leftovers))

        return sections

    def format_commands(self, ctx, formatter):
        """
        Render the command list so it survives a 40-column screen.

        Click's default is a two-column table: on a phone the name column eats
        most of the width and every description is truncated to "Build the
        project...", which tells the reader nothing. On a narrow screen we
        stack instead -- name on its own line, description wrapped beneath --
        and fall back to the familiar two-column form when there is room.

        The output is rendered through rich but written into click's own
        formatter, so it keeps its colours *and* stays in the right place
        relative to the usage and options blocks click writes itself.
        """
        text = _render_sections(self.grouped_commands(ctx))
        if text:
            formatter.write(text)

    def format_help(self, ctx, formatter):
        console, layout = _ctx()
        from anyplace.ui import components as ui

        ui.banner(console, layout=layout, subtitle=TAGLINE)
        console.print()
        console.print(ui.wrap(DESCRIPTION, layout.body_width), style=get_theme().style("muted"))
        console.print()
        super().format_help(ctx, formatter)


def _click_context_settings():
    """
    Make click wrap its own help to the real terminal.

    Click defaults to 80 columns, so on a 40-column phone every command
    description in `--help` runs off the edge.
    """
    width = Layout.detect().width
    return {
        "help_option_names": ["-h", "--help"],
        "max_content_width": width,
        "terminal_width": width,
    }


@click.group(cls=AnywhereGroup, invoke_without_command=True, context_settings=_click_context_settings())
@click.option("--auto", "auto_accept", is_flag=True, default=False, help="Don't ask before each pipeline step.")
@click.option("--width", type=int, default=None, help="Force a terminal width (useful on odd Termux setups).")
@click.version_option(__version__, "-V", "--version", prog_name=NAME)
@click.pass_context
def cli(ctx, auto_accept, width):
    """Anywhere Code — build and ship from your phone."""
    ctx.ensure_object(dict)
    ctx.obj["auto_accept"] = auto_accept
    ctx.obj["width"] = width

    if ctx.invoked_subcommand is None:
        ctx.exit(_launch_shell(auto_accept=auto_accept, width=width))


def _launch_shell(auto_accept: bool = False, width: Optional[int] = None) -> int:
    from anyplace.cli.app import App

    console = _console()
    layout = Layout.detect(width=width)
    try:
        return App(console=console, layout=layout, auto_accept=auto_accept).run()
    except KeyboardInterrupt:
        console.print()
        console.print("Bye.", style=get_theme().style("muted"))
        return 130


# ─────────────────────────────────────────────────────────────────────────
# Interactive entry points
# ─────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--auto", "auto_accept", is_flag=True, default=False, help="Don't ask before each pipeline step.")
def start(auto_accept):
    """Open the interactive shell (same as running `anywhere` alone)."""
    sys.exit(_launch_shell(auto_accept=auto_accept))


@cli.command()
@click.option("--auto", "auto_accept", is_flag=True, default=False, help="Don't ask before each pipeline step.")
def new(auto_accept):
    """Start a new project — asks what you want, then builds it."""
    from anyplace.cli import flows

    console, layout = _ctx()
    try:
        flows.new_project(console, layout=layout, auto_accept=auto_accept)
    except (ConfigError, GenerationError, APIError) as exc:
        exit_with_error(exc, "creating your project", console=console, layout=layout)
    except KeyboardInterrupt:
        console.print()
        console.print("Cancelled.", style=get_theme().style("warn"))


@cli.command(name="open")
def open_cmd():
    """Reopen one of your projects."""
    from anyplace.cli import flows

    console, layout = _ctx()
    flows.open_project(console, layout=layout)


@cli.command()
def doctor():
    """Check this device for anything that will get in the way."""
    from anyplace.cli.doctor_screen import render_report
    from anyplace.core.doctor import run_all

    console, layout = _ctx()
    from anyplace.ui import components as ui

    ui.rule(console, "Checking your setup", layout=layout)
    report = run_all()
    render_report(console, report, layout=layout)
    sys.exit(0 if report.healthy else 1)


@cli.command()
@click.option("--tag", default=None, help="Only show one kind of idea.")
@click.option("--search", "query", default=None, help="Find an idea by name.")
def recipes(tag, query):
    """Show the ready-made project ideas you can start from."""
    from anyplace.core.recipes import list_recipes, search_recipes
    from anyplace.ui import components as ui

    console, layout = _ctx()
    found = search_recipes(query) if query else list_recipes(tag=tag)

    if not found:
        ui.card(console, "Nothing matched.", title="No ideas found", tone="warn", layout=layout)
        return

    ui.data_table(
        console,
        ["Idea", "What it is", "Scaffold"],
        [[recipe.title, recipe.subtitle, recipe.template] for recipe in found],
        layout=layout,
        title="Start from an idea",
    )
    console.print()
    console.print("Run `anywhere new` and pick one.", style=get_theme().style("muted"))


# ─────────────────────────────────────────────────────────────────────────
# Setup and info
# ─────────────────────────────────────────────────────────────────────────

@cli.command()
def configure():
    """Add or change your AI provider and model."""
    from anyplace.cli.config_wizard import configure_providers
    from anyplace.ui import components as ui

    console, layout = _ctx()
    ui.banner(console, layout=layout, subtitle="Set up your AI")
    try:
        configure_providers(console=console, layout=layout)
    except Exception as exc:  # noqa: BLE001
        exit_with_error(exc, "saving your settings", console=console, layout=layout)


@cli.command()
def templates():
    """List the project scaffolds available."""
    from anyplace.cli.templates import get_template_info, list_available_templates
    from anyplace.ui import components as ui

    console, layout = _ctx()
    available = list_available_templates()
    if not available:
        ui.card(console, "No templates found — try reinstalling.", title="Nothing here", tone="err", layout=layout)
        return

    rows = []
    for name in available:
        try:
            info = get_template_info(name)
        except Exception:
            continue
        rows.append(
            [
                info.get("display_name") or name,
                info.get("tagline") or info.get("description", ""),
                info.get("difficulty", "—"),
                "yes" if info.get("mobile_friendly", True) else "desktop",
            ]
        )

    ui.data_table(console, ["Scaffold", "What it's for", "Level", "On a phone"], rows, layout=layout, title="Scaffolds")


@cli.command()
def info():
    """Show what this device looks like to Anywhere Code."""
    from anyplace.config.api_manager import APIManager
    from anyplace.config.environment import get_platform_info
    from anyplace.ui import components as ui

    console, layout = _ctx()
    platform_info = get_platform_info()

    ui.banner(console, layout=layout, subtitle=TAGLINE)
    ui.kv(
        console,
        [
            ("Version", __version__),
            ("System", "{0} ({1})".format(platform_info["system"], platform_info["machine"])),
            ("Mode", "Termux / Android" if platform_info["is_termux"] else "Desktop"),
            ("Terminal", "{0}x{1} ({2})".format(layout.width, layout.height, layout.bp)),
            ("Projects", platform_info["projects_dir"]),
            ("Config", platform_info["config_dir"]),
        ],
        layout=layout,
        title="This device",
    )

    api_mgr = APIManager()
    providers = api_mgr.list_providers()
    console.print()
    if providers:
        active = api_mgr.get_active_provider()
        rows = [
            [name, config.get("model", "?"), "default" if name == active else ""]
            for name, config in providers.items()
        ]
        ui.data_table(console, ["Provider", "Model", ""], rows, layout=layout, title="AI providers")
    else:
        ui.card(console, "No AI provider yet.\nRun: anywhere configure", title="AI providers", tone="warn", layout=layout)


@cli.command(name="test-providers")
def test_providers():
    """Check that your API keys actually work."""
    from anyplace.cli.config_wizard import test_provider
    from anyplace.config.api_manager import APIManager
    from anyplace.ui import components as ui

    console, layout = _ctx()
    api_mgr = APIManager()
    providers = api_mgr.list_providers()

    if not providers:
        ui.card(console, "Nothing to test.\nRun: anywhere configure", title="No providers", tone="warn", layout=layout)
        return

    results = [test_provider(console, api_mgr, name, layout=layout) for name in providers]
    console.print()
    if all(results):
        ui.card(console, "Every provider answered.", title="All good", tone="ok", layout=layout)
    else:
        ui.card(console, "At least one provider failed — see above.", title="Some failed", tone="warn", layout=layout)
        sys.exit(1)


@cli.command()
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation.")
def reset(yes):
    """Forget your API keys and settings."""
    from anyplace.config.api_manager import APIManager
    from anyplace.core.session import SessionStore
    from anyplace.ui import components as ui
    from anyplace.ui.prompts import confirm_danger

    console, layout = _ctx()
    if not yes and not confirm_danger(console, "Delete all saved keys and settings?", layout=layout):
        console.print("Left everything alone.", style=get_theme().style("muted"))
        return

    APIManager().reset_config()
    SessionStore().clear()
    ui.card(console, "Settings cleared. Your projects are untouched.", title="Reset", tone="ok", layout=layout)


# ─────────────────────────────────────────────────────────────────────────
# Project commands
# ─────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "-a", "stage_all", is_flag=True, default=False, help="Stage everything first.")
@click.option("--dry-run", is_flag=True, default=False, help="Show the message, don't commit.")
@dir_option
def commit(stage_all, dry_run, project_dir):
    """Write a commit message from your changes, then commit."""
    import subprocess

    from anyplace.cli import flows
    from anyplace.config.api_manager import APIManager
    from anyplace.core.commit_generator import CommitGenerator
    from anyplace.core.llm_provider import LLMProvider
    from anyplace.ui import components as ui
    from anyplace.ui.prompts import ask_yes_no

    console, layout = _ctx()
    path = Path(project_dir).resolve()

    if not (path / ".git").exists():
        ui.card(console, "{0}\nisn't a git repository.\n\nRun: git init".format(path), title="No repo", tone="err", layout=layout)
        sys.exit(1)

    try:
        llm = LLMProvider(APIManager())
        commit_gen = CommitGenerator(llm)

        if stage_all:
            subprocess.run(["git", "add", "-A"], cwd=str(path), check=True)

        diff = commit_gen.get_staged_diff(path)
        if not diff.strip():
            ui.card(console, "Nothing staged.\n\nUse -a to stage everything.", title="No changes", tone="warn", layout=layout)
            return

        with flows.thinking(console, "Reading your changes…", layout):
            message = commit_gen.generate_message(diff)

        ui.card(console, message, title="Proposed message", tone="info", layout=layout)

        if dry_run:
            console.print("Dry run — nothing committed.", style=get_theme().style("muted"))
            return

        if ask_yes_no(console, "Commit with this?", default=True, layout=layout):
            result = subprocess.run(["git", "commit", "-m", message], cwd=str(path), capture_output=True, text=True)
            if result.returncode == 0:
                ui.card(console, "Committed.", title="Done", tone="ok", layout=layout)
            else:
                ui.card(console, result.stderr.strip(), title="Commit failed", tone="err", layout=layout)
                sys.exit(1)

    except (GenerationError, APIError, ConfigError) as exc:
        exit_with_error(exc, "writing your commit message", console=console, layout=layout)


@cli.command()
@dir_option
@click.option("--install", is_flag=True, default=False, help="Install dependencies first.")
def build(project_dir, install):
    """Build the project in this directory."""
    import subprocess

    from anyplace.core.build_runner import BuildRunner
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()
    runner = BuildRunner(path)

    ui.kv(console, [("Project", path.name), ("Type", runner._detect_project_type())], layout=layout, title="Building")

    try:
        if install:
            console.print("Installing dependencies…", style=get_theme().style("accent"))
            if subprocess.run(runner.get_install_command(), cwd=str(path)).returncode != 0:
                ui.card(console, "Install failed — build not attempted.", title="Stopped", tone="err", layout=layout)
                sys.exit(1)

        ok = runner.run_build(progress_callback=lambda line: console.print("  " + line, style=get_theme().style("dim_rule")))
        if ok:
            ui.card(console, "Build finished.", title="Done", tone="ok", layout=layout)
        else:
            ui.card(console, "Build failed — see the output above.", title="Failed", tone="err", layout=layout)
            sys.exit(1)
    except GenerationError as exc:
        exit_with_error(exc, "building", console=console, layout=layout)


@cli.command()
@click.option("--target", type=click.Choice(["eas", "github", "auto"]), default="auto", show_default=True)
@dir_option
def deploy(target, project_dir):
    """Generate deployment config for this project."""
    from anyplace.config.api_manager import APIManager
    from anyplace.core.build_runner import BuildRunner
    from anyplace.core.deploy_generator import DeployGenerator
    from anyplace.core.llm_provider import LLMProvider
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()
    project_type = BuildRunner(path)._detect_project_type()

    if target == "auto":
        target = "eas" if project_type == "expo-rn" else "github"

    try:
        result = DeployGenerator(path, LLMProvider(APIManager())).deploy(target)
        ui.kv(console, [("Target", target), ("Type", project_type)], layout=layout, title="Deployment")
        console.print()
        for written in result["files_written"]:
            console.print("  " + written, style=get_theme().style("key"))
        console.print()
        for index, step in enumerate(result["next_steps"], 1):
            console.print(ui.wrap("  {0}. {1}".format(index, step), layout.body_width, indent="     "))
    except (GenerationError, APIError, ConfigError) as exc:
        exit_with_error(exc, "generating deployment config", console=console, layout=layout)


@cli.command()
@click.option("--platform", type=click.Choice(["github", "gitlab", "bitbucket", "circle"]), default="github", show_default=True)
@dir_option
def ci(platform, project_dir):
    """Add a CI pipeline to this project."""
    from anyplace.core.ci_generator import CIGenerator
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()
    generator = CIGenerator(path)

    try:
        files = generator.generate(platform)
        ui.kv(console, [("Platform", platform), ("Type", generator.project_type)], layout=layout, title="CI")
        for rel_path in files:
            console.print("  " + str(rel_path), style=get_theme().style("key"))
    except GenerationError as exc:
        exit_with_error(exc, "generating CI config", console=console, layout=layout)


@cli.command()
@click.option("--type", "docker_type", type=click.Choice(["dockerfile", "compose", "all"]), default="all", show_default=True)
@dir_option
def docker(docker_type, project_dir):
    """Add Docker config to this project."""
    from anyplace.core.docker_generator import DockerGenerator
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()
    generator = DockerGenerator(path)

    try:
        files = generator.generate(docker_type)
        ui.kv(console, [("Type", generator.project_type)], layout=layout, title="Docker")
        for rel_path in files:
            console.print("  " + str(rel_path), style=get_theme().style("key"))
        console.print()
        console.print("  docker compose up --build", style=get_theme().style("muted"))
    except GenerationError as exc:
        exit_with_error(exc, "generating Docker config", console=console, layout=layout)


@cli.command()
@click.option("--validate", is_flag=True, default=False, help="Check .env against .env.example.")
@dir_option
def env(validate, project_dir):
    """Create or check this project's environment variables."""
    from anyplace.core.build_runner import BuildRunner
    from anyplace.core.env_manager import EnvManager
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()
    manager = EnvManager()

    if validate:
        try:
            result = manager.validate_env(path)
        except GenerationError as exc:
            exit_with_error(exc, "checking your .env", console=console, layout=layout)
            return

        if result["missing"]:
            ui.card(console, "\n".join("• " + name for name in result["missing"]), title="Missing", tone="err", layout=layout)
        else:
            ui.card(console, "Nothing missing.", title="Looks good", tone="ok", layout=layout)

        if result["extra"]:
            console.print()
            ui.card(console, "\n".join("• " + name for name in result["extra"]), title="Extra (not in the example)", tone="warn", layout=layout)
        if result["missing"]:
            sys.exit(1)
        return

    project_type = BuildRunner(path)._detect_project_type()
    env_path = manager.write_env_example(path, project_type, path.name)
    ui.card(
        console,
        "Wrote {0}\n\nNext:\n  cp .env.example .env\n  anywhere env --validate".format(Path(env_path).name),
        title="Environment",
        tone="ok",
        layout=layout,
    )


@cli.command()
@dir_option
def guide(project_dir):
    """Read (or write) the learning guide for this project."""
    from anyplace.core.build_runner import BuildRunner
    from anyplace.core.guide_generator import GuideGenerator
    from anyplace.ui import components as ui
    from anyplace.ui.prompts import ask_yes_no

    console, layout = _ctx()
    path = Path(project_dir).resolve()

    learning_path = path / "LEARNING.md"
    if learning_path.exists():
        console.print(learning_path.read_text(errors="ignore"))
        return

    template_map = {"react-vite": "web-react-vite", "expo-rn": "mobile-expo-rn", "nodejs": "backend-nodejs"}
    template_name = template_map.get(BuildRunner(path)._detect_project_type(), "web-react-vite")

    content = GuideGenerator().generate_learning_md(template_name, path.name)
    console.print(content)

    if ask_yes_no(console, "Save this as LEARNING.md?", default=True, layout=layout):
        learning_path.write_text(content)
        ui.card(console, "Saved LEARNING.md", title="Done", tone="ok", layout=layout)


@cli.command()
@click.option("--type", "doc_type", type=click.Choice(["contributing", "changelog", "api", "all"]), default="all", show_default=True)
@dir_option
def docs(doc_type, project_dir):
    """Write the project's documentation."""
    from anyplace.config.api_manager import APIManager
    from anyplace.core.doc_generator import DocGenerator
    from anyplace.core.llm_provider import LLMProvider
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()

    llm = None
    try:
        api_mgr = APIManager()
        if api_mgr.list_providers():
            llm = LLMProvider(api_mgr)
    except Exception:  # noqa: BLE001 - docs still work without an LLM
        llm = None

    try:
        written = DocGenerator(path, llm).generate_all(path.name, doc_type)
        ui.kv(console, [(name, Path(file_path).name) for name, file_path in written.items()], layout=layout, title="Docs written")
    except Exception as exc:  # noqa: BLE001
        exit_with_error(exc, "writing documentation", console=console, layout=layout)


@cli.command()
@click.argument("file", required=False)
@dir_option
def explain(file, project_dir):
    """Explain what a file does."""
    from anyplace.cli import flows
    from anyplace.config.api_manager import APIManager
    from anyplace.core.llm_provider import LLMProvider
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()

    if not file:
        ui.card(console, "Tell me which file:\n\n  anywhere explain src/App.tsx", title="Which file?", tone="warn", layout=layout)
        return

    file_path = path / file
    if not file_path.exists():
        file_path = Path(file)
    if not file_path.exists():
        ui.card(console, "Can't find {0}".format(file), title="No such file", tone="err", layout=layout)
        sys.exit(1)

    content = file_path.read_text(errors="ignore")
    if len(content) > 4000:
        content = content[:4000] + "\n… (truncated)"

    try:
        llm = LLMProvider(APIManager())
        with flows.thinking(console, "Reading {0}…".format(file_path.name), layout):
            explanation = llm.generate_text(
                prompt="Explain this file (`{0}`):\n\n```\n{1}\n```".format(file, content),
                system=(
                    "You are a senior developer explaining code to someone reading it on a phone. "
                    "Short paragraphs, plain language, no preamble. Say what it does, why it exists, "
                    "and the one thing a newcomer would get wrong."
                ),
                temperature=0.3,
                max_tokens=1024,
            )
        ui.card(console, explanation, title=file_path.name, tone="info", layout=layout)
    except (ConfigError, APIError) as exc:
        exit_with_error(exc, "explaining that file", console=console, layout=layout)


@cli.command()
@dir_option
@click.option("--skip-deploy", is_flag=True, default=False, help="Don't generate deployment config.")
@click.option("--auto", "auto_accept", is_flag=True, default=False, help="Don't ask before each step.")
def run(project_dir, skip_deploy, auto_accept):
    """Set up and run the project in this directory, end to end."""
    from anyplace.cli import flows
    from anyplace.core.agent_executor import AgentExecutor
    from anyplace.ui import components as ui

    console, layout = _ctx()
    path = Path(project_dir).resolve()

    def on_step(step: str, message: str) -> None:
        console.print(
            "  {0} {1} {2}".format(get_theme().icon("spark", emoji=layout.emoji), step, ui.truncate(message, max(10, layout.body_width - 12))),
            style=get_theme().style("muted"),
        )

    executor = AgentExecutor(project_dir=path, progress_callback=on_step, human_accept=not auto_accept)

    ui.kv(
        console,
        [("Project", path.name), ("Type", executor.project_type), ("Mode", "auto" if auto_accept else "you approve each step")],
        layout=layout,
        title="Setting up",
    )
    console.print()

    result = executor.run_full_pipeline(skip_deploy=skip_deploy)
    flows.show_pipeline_results(console, result, layout=layout)
    flows.wait_for_server(console, result, layout=layout)


@cli.command()
def serve():
    """Run the MCP server so Claude can drive Anywhere Code."""
    from anyplace.ui import components as ui

    console, layout = _ctx()
    try:
        from anyplace.mcp.server import mcp
    except ImportError:
        ui.card(
            console,
            "The MCP extra isn't installed.\n\nRun: pip install 'anyplace[mcp]'",
            title="Missing dependency",
            tone="err",
            layout=layout,
        )
        sys.exit(1)

    console.print("MCP server listening.", style=get_theme().style("accent"))
    mcp.run()


def main() -> None:
    """Console-script entry point."""
    cli(prog_name="anywhere", obj={})


if __name__ == "__main__":
    main()
