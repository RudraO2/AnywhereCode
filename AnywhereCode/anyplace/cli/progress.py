"""
Live progress during generation.

Generating 20 files over a mobile connection takes minutes. The screen has to
answer "is it stuck?" at a glance, in 32 columns, without scrolling away the
thing you were reading.
"""

from __future__ import annotations

import time
from typing import List, Optional

from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.theme import get_theme


def format_duration(seconds: float) -> str:
    """Human duration, always short enough for a status line."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "{0}s".format(seconds)
    if seconds < 3600:
        return "{0}m {1:02d}s".format(seconds // 60, seconds % 60)
    return "{0}h {1:02d}m".format(seconds // 3600, (seconds % 3600) // 60)


class GenerationProgress:
    """Progress display for a run of file generation."""

    def __init__(self, total_files: int, project_name: str, console=None, layout: Optional[Layout] = None):
        if console is None:
            from rich.console import Console

            console = Console()
        self.console = console
        self.layout = layout or Layout.detect()
        self.total_files = max(0, total_files)
        self.project_name = project_name
        self.generated_files: List[str] = []
        self.current_file = ""
        self.current_index = 0
        self.started_at: Optional[float] = None

    # ── lifecycle ────────────────────────────────────────────────────────

    def show_generation_start(self) -> None:
        self.started_at = time.time()
        theme = get_theme()
        self.console.print()
        pad = " " * self.layout.gutter
        self.console.print(
            pad + "{0} Writing {1} — {2} file{3}".format(
                theme.icon("run", emoji=self.layout.emoji),
                ui.truncate(self.project_name, max(8, self.layout.body_width - 20)),
                self.total_files,
                "" if self.total_files == 1 else "s",
            ),
            style=theme.style("accent"),
        )
        if not self.layout.narrow:
            self.console.print(pad + "Each file is written in dependency order.", style=theme.style("muted"))
        self.console.print()

    def show_file_progress(self, file_path: str, index: int, total: int) -> None:
        self.current_file = file_path
        self.current_index = index
        self.generated_files.append(file_path)
        ui.progress_line(self.console, index, total, file_path, layout=self.layout)

    def show_generation_complete(self, project_dir: str) -> None:
        theme = get_theme()
        pairs = [
            ("Project", self.project_name),
            ("Files", str(len(self.generated_files) or self.total_files)),
            ("Where", str(project_dir)),
        ]
        if self.started_at:
            pairs.append(("Took", format_duration(time.time() - self.started_at)))
        self.console.print()
        ui.kv(
            self.console,
            pairs,
            layout=self.layout,
            title="{0} Written".format(theme.icon("ok", emoji=self.layout.emoji)),
        )

    def show_generation_error(self, error_msg: str, file_path: Optional[str] = None) -> None:
        body = error_msg
        if file_path:
            body = "Stopped at: {0}\n\n{1}".format(file_path, error_msg)
        if self.current_index:
            body += "\n\n{0} of {1} files were written before this.".format(self.current_index, self.total_files)
        ui.card(self.console, body, title="Generation failed", tone="err", layout=self.layout)

    # ── extras ───────────────────────────────────────────────────────────

    def show_file_list(self, files: List[str]) -> None:
        self.console.print()
        ui.rule(self.console, "Written", layout=self.layout)
        icon = get_theme().icon("check", emoji=self.layout.emoji)
        for file_path in files:
            self.console.print("  {0} {1}".format(icon, ui.truncate(file_path, self.layout.body_width - 4)))

    def eta(self, avg_secs_per_file: float = 2.0) -> str:
        """Best-guess remaining time, measured rather than assumed once we have data."""
        remaining = max(0, self.total_files - self.current_index)
        if self.started_at and self.current_index:
            avg_secs_per_file = (time.time() - self.started_at) / self.current_index
        return format_duration(remaining * avg_secs_per_file)


class ProgressTracker:
    """Headless counter, handy for callers that render their own output."""

    def __init__(self, total: int):
        self.total = max(0, total)
        self.current = 0
        self.items: List[str] = []

    def add(self, item: str) -> None:
        self.current += 1
        self.items.append(item)

    def get_progress_percent(self) -> int:
        if self.total == 0:
            return 0
        return int((self.current / self.total) * 100)

    def get_summary(self) -> str:
        return "{0}/{1} ({2}%)".format(self.current, self.total, self.get_progress_percent())
