"""
The home screen and the router that hangs off it.

`anywhere` with no arguments lands here. Everything is reachable in at most two
taps from this screen, because on a phone the thing you cannot do is scroll back
to find where you were.
"""

from __future__ import annotations

from typing import Callable, Optional

from anyplace import NAME, TAGLINE, __version__
from anyplace.cli import flows
from anyplace.cli.doctor_screen import render_report
from anyplace.cli.error_handler import handle_error
from anyplace.config.api_manager import APIManager
from anyplace.config.environment import get_projects_dir, is_termux
from anyplace.core.doctor import FAIL, run_all
from anyplace.core.session import SessionStore
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import Choice, GoBack, QuitApp, ask_choice, ask_yes_no, pause
from anyplace.ui.theme import get_theme

HOME_HINTS = (("1-6", "pick"), ("q", "quit"), ("?", "help"))


class App:
    """The interactive shell. Holds the console, layout and session."""

    def __init__(
        self,
        console=None,
        layout: Optional[Layout] = None,
        input_fn: Optional[Callable[[str], str]] = None,
        auto_accept: bool = False,
    ):
        if console is None:
            from rich.console import Console

            console = Console()
        self.console = console
        self.layout = layout or Layout.detect()
        self.input_fn = input_fn
        self.auto_accept = auto_accept
        self.store = SessionStore()

    # ── chrome ───────────────────────────────────────────────────────────

    def status_pairs(self):
        api_mgr = APIManager()
        providers = api_mgr.list_providers()
        active = api_mgr.get_active_provider()

        if not providers:
            provider_line = "not set up yet"
        elif active:
            provider_line = "{0} · {1}".format(active, providers[active].get("model", "?"))
        else:
            provider_line = ", ".join(providers)

        pairs = [("AI", provider_line)]
        pairs.append(("Where", "Termux" if is_termux() else "Desktop"))
        if not self.layout.narrow:
            pairs.append(("Projects", str(get_projects_dir())))
        return pairs

    def show_home(self) -> None:
        ui.banner(self.console, layout=self.layout, subtitle=TAGLINE)
        ui.kv(self.console, self.status_pairs(), layout=self.layout)

    # ── first run ────────────────────────────────────────────────────────

    def maybe_welcome(self) -> None:
        """A one-time orientation, so the first screen isn't a wall of choices."""
        state = self.store.load()
        if state.run_count > 0:
            self.store.update(run_count=state.run_count + 1)
            return

        self.store.update(run_count=1)
        ui.card(
            self.console,
            "I ask a few questions, then write and run a real project for you.\n\n"
            "It all happens on this device. Your API key never leaves it.\n\n"
            "Anything I'm about to run, you approve first.",
            title="Welcome to {0}".format(NAME),
            tone="info",
            layout=self.layout,
        )

        report = run_all()
        blockers = report.by_status(FAIL)
        if blockers:
            self.console.print()
            ui.card(
                self.console,
                "{0} thing(s) on this device will get in the way. Worth two minutes now.".format(len(blockers)),
                title="Quick check",
                tone="warn",
                layout=self.layout,
            )
            if ask_yes_no(self.console, "Show me?", default=True, layout=self.layout, input_fn=self.input_fn):
                render_report(self.console, report, layout=self.layout)
                pause(self.console, layout=self.layout, input_fn=self.input_fn)

    # ── screens ──────────────────────────────────────────────────────────

    def screen_help(self) -> None:
        theme = get_theme()
        ui.card(
            self.console,
            "Build something new — I ask what you want, then write it and run it.\n\n"
            "Open a project — come back to anything you made before.\n\n"
            "Check my setup — finds the Termux gotchas and tells you the fix.\n\n"
            "Everything here also works as a plain command, e.g.\n"
            "  anywhere new\n"
            "  anywhere doctor\n"
            "  anywhere run --dir .\n\n"
            "In any question: Enter takes the default, b goes back, q quits.",
            title="How this works",
            tone="info",
            layout=self.layout,
        )
        self.console.print()
        self.console.print(
            "{0} v{1}".format(NAME, __version__),
            style=theme.style("dim_rule"),
        )
        pause(self.console, layout=self.layout, input_fn=self.input_fn)

    def screen_settings(self) -> None:
        from anyplace.cli.config_wizard import configure_providers

        configure_providers(console=self.console, layout=self.layout, input_fn=self.input_fn)

    def screen_doctor(self) -> None:
        self.console.print()
        with flows.thinking(self.console, "Checking this device…", self.layout):
            report = run_all()
        render_report(self.console, report, layout=self.layout)
        pause(self.console, layout=self.layout, input_fn=self.input_fn)

    def screen_here(self) -> None:
        """Run the pipeline over the current directory."""
        from pathlib import Path

        flows.run_subcommand(self.console, "run", [], Path.cwd(), layout=self.layout)
        pause(self.console, layout=self.layout, input_fn=self.input_fn)

    # ── loop ─────────────────────────────────────────────────────────────

    def run(self) -> int:
        self.maybe_welcome()

        while True:
            self.console.print()
            self.show_home()

            project_count = len(flows.list_projects(self.console, self.layout))
            choices = [
                Choice(value="new", label="Build something new", description="Answer a few questions"),
                Choice(
                    value="open",
                    label="Open a project",
                    description="{0} saved".format(project_count) if project_count else "nothing yet",
                ),
                Choice(value="here", label="Run this folder", description="Set up the project you're standing in"),
                Choice(value="doctor", label="Check my setup", description="Find and fix problems"),
                Choice(value="settings", label="AI provider", description="Keys and models"),
                Choice(value="help", label="What is this?", description="A one-screen tour"),
                Choice(value="quit", label="Quit", description=""),
            ]

            try:
                choice = ask_choice(
                    self.console,
                    "What now?",
                    choices,
                    default="new",
                    layout=self.layout,
                    input_fn=self.input_fn,
                    allow_back=False,
                    help_text="Enter picks the highlighted option. q quits from anywhere.",
                )
            except QuitApp:
                return self._goodbye()

            try:
                if choice == "quit":
                    return self._goodbye()
                if choice == "new":
                    flows.new_project(
                        self.console,
                        layout=self.layout,
                        input_fn=self.input_fn,
                        auto_accept=self.auto_accept,
                    )
                elif choice == "open":
                    flows.open_project(self.console, layout=self.layout, input_fn=self.input_fn)
                elif choice == "here":
                    self.screen_here()
                elif choice == "doctor":
                    self.screen_doctor()
                elif choice == "settings":
                    self.screen_settings()
                elif choice == "help":
                    self.screen_help()
            except QuitApp:
                return self._goodbye()
            except GoBack:
                continue
            except KeyboardInterrupt:
                self.console.print()
                self.console.print("Cancelled.", style=get_theme().style("warn"))
            except Exception as exc:  # noqa: BLE001 - the shell must not die on one bad screen
                handle_error(exc, context="Running {0}".format(choice), console=self.console, layout=self.layout)
                pause(self.console, layout=self.layout, input_fn=self.input_fn)

    def _goodbye(self) -> int:
        self.console.print()
        self.console.print(
            "{0} See you.".format(get_theme().icon("spark", emoji=self.layout.emoji)),
            style=get_theme().style("accent"),
        )
        return 0
