"""
The end-to-end journeys: start something new, reopen something old, run the
pipeline over a project.

Everything a user actually came here to do lives in this file. Screens compose
`anyplace.ui` widgets; decisions live in `anyplace.core`.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from anyplace.cli import plan_preview
from anyplace.cli.error_handler import APIError, ConfigError, GenerationError
from anyplace.cli.interview_screen import run_interview, show_brief
from anyplace.cli.progress import GenerationProgress
from anyplace.cli.recipes_screen import pick_recipe, show_recipe
from anyplace.cli.templates import get_template_info, list_available_templates
from anyplace.config.api_manager import APIManager
from anyplace.config.environment import get_projects_dir, is_termux
from anyplace.core.brief import ProjectBrief
from anyplace.core.build_orchestrator import BuildOrchestrator
from anyplace.core.interview import EXPERT, GUIDED, QUICK, Interview
from anyplace.core.llm_provider import LLMProvider
from anyplace.core.plan_generator import PlanGenerator
from anyplace.core.recommender import Recommendation, recommend
from anyplace.core.session import SessionStore
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import Choice, GoBack, QuitApp, ask_choice, ask_text, ask_yes_no, pause
from anyplace.ui.theme import get_theme


@contextlib.contextmanager
def thinking(console, message: str, layout: Optional[Layout] = None):
    """
    Spinner around a slow network call.

    A phone on 3G can sit on an LLM call for 40 seconds. Without this the app
    looks frozen and people kill it.
    """
    layout = layout or Layout.detect()
    if layout.narrow:
        console.print(get_theme().icon("robot", emoji=layout.emoji) + " " + message, style=get_theme().style("accent"))
        yield
        return
    with console.status("[bold cyan]{0}[/bold cyan]".format(message), spinner="dots"):
        yield


def _load_templates() -> List[dict]:
    """Template metadata dicts, tolerant of a broken template on disk."""
    templates = []
    for name in list_available_templates():
        try:
            info = dict(get_template_info(name))
        except Exception:
            continue
        info.setdefault("name", name)
        templates.append(info)
    return templates


def _template_label(info: dict) -> str:
    return info.get("display_name") or info.get("name", "template")


def _slugify(text: str, fallback: str = "my-project") -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned[:40] or fallback


# ─────────────────────────────────────────────────────────────────────────
# New project
# ─────────────────────────────────────────────────────────────────────────

def choose_start_mode(console, layout: Layout, store: SessionStore, input_fn) -> str:
    """How much does this user want to be asked?"""
    state = store.load()
    choices = [
        Choice(value="recipe", label="Pick from ideas", description="Fastest — tap a starting point"),
        Choice(value=GUIDED, label="Answer a few questions", description="I'll help you decide"),
        Choice(value=QUICK, label="Just the essentials", description="Three questions, then build"),
        Choice(value=EXPERT, label="I'll describe it", description="One line, you know what you want"),
    ]
    default = state.last_mode or "recipe"
    if default not in {"recipe", GUIDED, QUICK, EXPERT}:
        default = "recipe"

    return ask_choice(
        console,
        "How do you want to start?",
        choices,
        default=default,
        layout=layout,
        input_fn=input_fn,
        help_text="All roads end in the same place — this is just how much I ask.",
    )


def gather_brief(console, layout: Layout, store: SessionStore, input_fn) -> Tuple[ProjectBrief, str, Optional[str]]:
    """
    Work out what the user wants.

    Returns (brief, mode, forced_template) where forced_template is set when a
    recipe already decided the scaffold.
    """
    mode = choose_start_mode(console, layout, store, input_fn)
    forced_template: Optional[str] = None
    prefill = {}

    if mode == "recipe":
        recipe = pick_recipe(console, layout=layout, input_fn=input_fn)
        if recipe is not None:
            show_recipe(console, recipe, layout=layout)
            prefill = dict(recipe.prefill)
            forced_template = recipe.template
            mode = QUICK
        else:
            mode = GUIDED

    interview = Interview(mode=mode)
    if prefill:
        interview.prefill(prefill)

    brief = run_interview(console, interview, layout=layout, input_fn=input_fn)
    store.update(last_mode=mode, saved_answers=interview.answers)
    return brief, mode, forced_template


def choose_template(
    console,
    layout: Layout,
    brief: ProjectBrief,
    input_fn,
    forced: Optional[str] = None,
) -> str:
    """Recommend a scaffold, explain the reasoning, let the user overrule it."""
    templates = _load_templates()
    if not templates:
        raise GenerationError("No project templates found. Reinstall Anywhere Code.")

    names = {info["name"] for info in templates}
    if forced and forced in names:
        return forced

    ranked: List[Recommendation] = recommend(brief, templates)
    if not ranked:
        return templates[0]["name"]

    top = ranked[0]
    info = next((item for item in templates if item["name"] == top.template), {"name": top.template})

    console.print()
    body_lines = list(top.reasons[:3])
    if top.caveats:
        body_lines.append("")
        body_lines.append("Worth knowing: " + top.caveats[0])
    ui.card(
        console,
        "\n".join("• " + line if line else "" for line in body_lines),
        title="I'd use {0}".format(_template_label(info)),
        tone="info",
        layout=layout,
    )

    choices = [
        Choice(value="__accept__", label="Sounds good", description=_template_label(info)),
        Choice(value="__other__", label="Show me the others", description="Pick a different scaffold"),
    ]
    picked = ask_choice(
        console,
        "Use that?",
        choices,
        default="__accept__",
        layout=layout,
        input_fn=input_fn,
        allow_back=False,
        help_text="A scaffold is just the starting files. You can change anything after.",
    )
    if picked == "__accept__":
        return top.template

    by_name = {item["name"]: item for item in templates}
    alt_choices = []
    for rec in ranked:
        item = by_name.get(rec.template, {"name": rec.template})
        description = item.get("tagline") or item.get("description", "")
        if not item.get("mobile_friendly", True):
            description = (description + " · heavier on a phone").strip(" ·")
        alt_choices.append(Choice(value=rec.template, label=_template_label(item), description=description))

    return ask_choice(
        console,
        "Which scaffold?",
        alt_choices,
        default=top.template,
        layout=layout,
        input_fn=input_fn,
        allow_back=False,
    )


def _ensure_provider(console, layout: Layout, input_fn) -> APIManager:
    """No key, no build. Offer to fix it right here rather than dead-ending."""
    api_mgr = APIManager()
    if api_mgr.list_providers():
        return api_mgr

    ui.card(
        console,
        "You need an AI provider before I can write code.\nGemini has a free tier and takes about a minute to set up.",
        title="One thing first",
        tone="warn",
        layout=layout,
    )
    if not ask_yes_no(console, "Set one up now?", default=True, layout=layout, input_fn=input_fn):
        raise ConfigError("No LLM provider configured. Run: anywhere configure")

    from anyplace.cli.config_wizard import configure_providers

    api_mgr = configure_providers(console=console, layout=layout, input_fn=input_fn, api_mgr=api_mgr)
    if not api_mgr.list_providers():
        raise ConfigError("No LLM provider configured. Run: anywhere configure")
    return api_mgr


def new_project(
    console,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    auto_accept: bool = False,
) -> Optional[str]:
    """The full create-a-project journey. Returns the project dir, or None."""
    layout = layout or Layout.detect()
    store = SessionStore()

    api_mgr = _ensure_provider(console, layout, input_fn)

    brief, _mode, forced_template = gather_brief(console, layout, store, input_fn)
    show_brief(console, brief, layout=layout)

    if not ask_yes_no(console, "Got it right?", default=True, layout=layout, input_fn=input_fn):
        note = ask_text(
            console,
            "What did I miss?",
            layout=layout,
            input_fn=input_fn,
            allow_empty=True,
            help_text="Anything you add here goes straight to the planner.",
        )
        if note:
            brief.notes = (brief.notes + "\n" + note).strip()

    template = choose_template(console, layout, brief, input_fn, forced=forced_template)

    default_name = _slugify(brief.name or brief.idea or "my-project")
    project_name = ask_text(
        console,
        "Name the folder",
        default=default_name,
        layout=layout,
        input_fn=input_fn,
        validator=_validate_project_name,
        help_text="Lowercase, no spaces. This is the directory name.",
    )

    target = get_projects_dir() / project_name
    if target.exists():
        ui.card(
            console,
            "{0}\nalready exists.".format(target),
            title="Name taken",
            tone="warn",
            layout=layout,
        )
        project_name = ask_text(
            console,
            "Pick another name",
            default=project_name + "-2",
            layout=layout,
            input_fn=input_fn,
            validator=_validate_project_name,
        )

    brief.name = project_name

    llm = LLMProvider(api_mgr)
    generator = PlanGenerator(llm)

    while True:
        try:
            with thinking(console, "Planning your project…", layout):
                plan = generator.generate_plan(
                    template_name=template,
                    project_name=project_name,
                    description=brief.to_prompt(),
                )
        except GenerationError as exc:
            plan_preview.display_plan_error(str(exc), console=console, layout=layout)
            if not ask_yes_no(console, "Try again?", default=True, layout=layout, input_fn=input_fn):
                return None
            continue

        decision = plan_preview.show_plan_approval_screen(plan, console=console, layout=layout, input_fn=input_fn)

        if decision == plan_preview.CANCEL:
            ui.card(console, "Nothing was written.", title="Cancelled", tone="muted", layout=layout)
            return None

        if decision == plan_preview.REVISE:
            extra = ask_text(
                console,
                "Describe it differently",
                default=brief.idea,
                layout=layout,
                input_fn=input_fn,
            )
            brief.idea = extra
            continue

        break

    return _build(console, layout, plan, llm, project_name, template, auto_accept, store, input_fn)


def _validate_project_name(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return "Give it a name"
    if "/" in value or "\\" in value:
        return "No slashes — this is a folder name"
    if value.startswith("."):
        return "Can't start with a dot"
    if len(value) > 60:
        return "Too long, keep it under 60 characters"
    return None


def _build(
    console,
    layout: Layout,
    plan,
    llm,
    project_name: str,
    template: str,
    auto_accept: bool,
    store: SessionStore,
    input_fn,
) -> Optional[str]:
    """Generate the files, then run the agentic pipeline over them."""
    progress = GenerationProgress(len(plan.files), project_name, console=console, layout=layout)

    def on_step(step: str, message: str) -> None:
        console.print(
            "  {0} {1} {2}".format(get_theme().icon("spark", emoji=layout.emoji), step, ui.truncate(message, max(10, layout.body_width - 12))),
            style=get_theme().style("muted"),
        )

    orchestrator = BuildOrchestrator(
        plan=plan,
        llm_provider=llm,
        use_git=True,
        agentic=True,
        human_accept=not auto_accept,
    )

    progress.show_generation_start()

    try:
        success = orchestrator.build(
            progress_callback=progress.show_file_progress,
            agent_callback=on_step,
        )
    except (GenerationError, APIError) as exc:
        progress.show_generation_error(str(exc))
        return None

    if not success:
        progress.show_generation_error("Generation did not complete.")
        return None

    info = orchestrator.get_project_info()
    project_dir = str(info["project_dir"])
    progress.show_generation_complete(project_dir)

    store.update(last_template=template, last_project_name=project_name)
    store.remember_project(project_dir)

    if orchestrator.pipeline_result:
        show_pipeline_results(console, orchestrator.pipeline_result, layout=layout)
        wait_for_server(console, orchestrator.pipeline_result, layout=layout)
    else:
        show_next_steps(console, plan, project_dir, layout=layout)

    return project_dir


# ─────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────

def show_pipeline_results(console, result, layout: Optional[Layout] = None) -> None:
    """What the agent actually did, at a glance."""
    layout = layout or Layout.detect()
    theme = get_theme()
    summary = result.summary

    rows = []
    for step in summary["steps"]:
        status = step["status"]
        icon = theme.icon({"pass": "ok", "skipped": "dot"}.get(status, "err"), emoji=layout.emoji)
        rows.append((icon, step["name"], step.get("detail", "") or ""))

    console.print()
    ui.rule(console, "What I did", layout=layout)
    ui.steps(console, rows, layout=layout)

    passed, skipped, failed = summary["passed"], summary["skipped"], summary["failed"]
    console.print()

    if failed == 0:
        body = "{0} steps done, {1} skipped.\n\nYour project is at:\n{2}".format(passed, skipped, result.project_dir)
        ui.card(console, body, title="Ready", tone="ok", layout=layout)
    else:
        body = "{0} done, {1} skipped, {2} failed.\nThe files are still there — you can pick up where it stopped:\n{3}".format(
            passed, skipped, failed, result.project_dir
        )
        ui.card(console, body, title="Partly done", tone="warn", layout=layout)

    server_url = summary.get("server_url", "")
    if server_url:
        ui.card(console, "Open {0} in your browser.".format(server_url), title="It's running", tone="ok", layout=layout)


def show_next_steps(console, plan, project_dir: str, layout: Optional[Layout] = None) -> None:
    layout = layout or Layout.detect()
    console.print()
    ui.rule(console, "Next", layout=layout)
    console.print("  cd " + str(project_dir), style=get_theme().style("key"))
    for index, step in enumerate(getattr(plan, "next_steps", [])[:5], 1):
        console.print(ui.wrap("  {0}. {1}".format(index, step), layout.body_width, indent="     "))


def wait_for_server(console, result, layout: Optional[Layout] = None) -> None:
    """Stream dev-server output until the user stops it."""
    layout = layout or Layout.detect()
    proc = getattr(result, "server_process", None)
    if not proc or proc.poll() is not None:
        return

    console.print()
    console.print("Streaming server output. Ctrl+C stops it.", style=get_theme().style("muted"))
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                console.print("  " + ui.truncate(line.rstrip(), layout.body_width - 2), style=get_theme().style("dim_rule"))
    except KeyboardInterrupt:
        console.print()
        console.print("Stopping the server…", style=get_theme().style("warn"))
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        console.print("Stopped.", style=get_theme().style("ok"))


# ─────────────────────────────────────────────────────────────────────────
# Existing projects
# ─────────────────────────────────────────────────────────────────────────

PROJECT_ACTIONS: Sequence[Tuple[str, str, str]] = (
    ("run", "Set it up and run it", "Install, build, then start it"),
    ("commit", "Commit my changes", "Writes the message for you"),
    ("build", "Build it", "Just the build step"),
    ("explain", "Explain a file", "Ask what a file does"),
    ("docs", "Write the docs", "README, contributing, changelog"),
    ("guide", "Teach me this stack", "A learning guide for the project"),
    ("env", "Environment variables", "Generate or check .env"),
    ("deploy", "Deployment config", "Get it ready to ship"),
    ("ci", "Add CI", "GitHub Actions and friends"),
    ("docker", "Add Docker", "Dockerfile and compose"),
)


def _count_files(path: Path) -> int:
    """Rough size signal. Skips the usual noise so a phone doesn't stat 40k files."""
    skip = {"node_modules", ".git", "dist", "build", "__pycache__", ".next", "venv", ".venv"}
    total = 0
    for child in path.rglob("*"):
        if any(part in skip for part in child.parts):
            continue
        if child.is_file():
            total += 1
            if total > 999:
                return total
    return total


def list_projects(console, layout: Optional[Layout] = None) -> List[Path]:
    layout = layout or Layout.detect()
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []
    return [child for child in sorted(projects_dir.iterdir()) if child.is_dir() and not child.name.startswith(".")]


def open_project(
    console,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> None:
    """Pick a project, then pick something to do to it."""
    layout = layout or Layout.detect()
    store = SessionStore()
    projects = list_projects(console, layout)

    if not projects:
        ui.card(
            console,
            "Nothing here yet.\n\nProjects live in:\n{0}".format(get_projects_dir()),
            title="No projects",
            tone="info",
            layout=layout,
        )
        return

    recent = store.load().recent_projects
    order = {path: index for index, path in enumerate(recent)}
    projects.sort(key=lambda p: order.get(str(p), 10_000))

    theme = get_theme()
    choices = []
    for path in projects:
        marks = []
        if (path / ".git").exists():
            marks.append("git")
        count = _count_files(path)
        marks.append("{0}{1} files".format(count, "+" if count > 999 else ""))
        choices.append(Choice(value=str(path), label=path.name, description=" · ".join(marks)))

    try:
        chosen = ask_choice(
            console,
            "Which project?",
            choices,
            layout=layout,
            input_fn=input_fn,
            help_text="Most recently used first.",
        )
    except GoBack:
        return

    project = Path(chosen)
    store.remember_project(str(project))
    project_actions(console, project, layout, input_fn)


def project_actions(
    console,
    project: Path,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> None:
    """The menu of things you can do to an existing project."""
    layout = layout or Layout.detect()

    while True:
        ui.kv(
            console,
            [("Project", project.name), ("Where", str(project))],
            layout=layout,
            title=project.name,
        )
        choices = [
            Choice(value=command, label=label, description=description)
            for command, label, description in PROJECT_ACTIONS
        ]
        try:
            action = ask_choice(
                console,
                "What do you want to do?",
                choices,
                default="run",
                layout=layout,
                input_fn=input_fn,
            )
        except GoBack:
            return

        args = []
        if action == "explain":
            filename = ask_text(console, "Which file?", layout=layout, input_fn=input_fn, placeholder="src/App.tsx")
            args = [filename]

        run_subcommand(console, action, args, project, layout)
        pause(console, "Back to the menu", layout=layout, input_fn=input_fn)


def run_subcommand(console, command: str, args: List[str], project: Path, layout: Optional[Layout] = None) -> int:
    """
    Re-enter our own CLI for a subcommand.

    Uses `sys.executable -m anyplace.cli.main` rather than bare `anyplace`, which
    is what the old code did — that broke whenever the wrapper script wasn't on
    PATH, which on Termux is most of the time.
    """
    layout = layout or Layout.detect()
    cmd = [sys.executable, "-m", "anyplace.cli.main", command] + list(args) + ["--dir", str(project)]
    console.print()
    console.print("  " + " ".join([command] + list(args)), style=get_theme().style("muted"))
    console.print()
    try:
        return subprocess.run(cmd, check=False).returncode
    except KeyboardInterrupt:
        console.print("Stopped.", style=get_theme().style("warn"))
        return 130
