"""
Plan review — the last gate before we spend tokens and disk.

The old version printed five full sections plus a fixed-width table, which on a
40-column phone became several screens of wrapped mush. This version shows a
scannable summary that fits one screen, and puts the detail behind a keypress.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from anyplace.core.plan_generator import ProjectPlan
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import Choice, ask_choice, pause
from anyplace.ui.theme import get_theme

APPROVE = "approve"
DETAILS = "details"
REVISE = "revise"
CANCEL = "cancel"

_TYPE_LABELS: Dict[str, str] = {
    "config": "Config",
    "source": "Source",
    "test": "Tests",
    "doc": "Docs",
    "other": "Other",
}
_TYPE_ORDER = ("config", "source", "test", "doc", "other")


def _group_by_type(plan: ProjectPlan) -> Dict[str, List]:
    grouped: Dict[str, List] = {}
    for file_info in plan.files:
        grouped.setdefault(file_info.file_type or "other", []).append(file_info)
    return grouped


def _preview_count(layout: Layout) -> int:
    if layout.bp == "xs":
        return 4
    if layout.narrow:
        return 6
    return 12


def display_plan_summary(plan: ProjectPlan, console, layout: Optional[Layout] = None) -> None:
    """The one-screen version: what you're getting, in plain words."""
    layout = layout or Layout.detect()

    ui.kv(
        console,
        [
            ("Project", plan.project_name),
            ("Scaffold", plan.template),
            ("Files", str(len(plan.files))),
            ("Time", plan.estimated_time or "a few minutes"),
        ],
        layout=layout,
        title="The plan",
    )

    if plan.description:
        console.print()
        ui.card(console, plan.description, title="What it is", tone="info", layout=layout)

    if plan.tech_stack:
        console.print()
        if layout.narrow:
            pad = " " * layout.gutter
            console.print(ui.wrap(pad + "Built with: " + ", ".join(plan.tech_stack), layout.body_width, indent=pad))
        else:
            ui.rule(console, "Built with", layout=layout)
            pad = " " * layout.gutter
            for tech in plan.tech_stack:
                console.print(pad + get_theme().icon("bullet", emoji=layout.emoji) + " " + tech)

    if plan.key_features:
        console.print()
        ui.rule(console, "You get", layout=layout)
        bullet = get_theme().icon("check", emoji=layout.emoji)
        for feature in plan.key_features[: 4 if layout.narrow else 8]:
            console.print(ui.wrap("  " + bullet + " " + feature, layout.body_width, indent="    "))


def display_file_plan(plan: ProjectPlan, console, layout: Optional[Layout] = None) -> None:
    """File counts by kind, plus a taste of the actual paths."""
    layout = layout or Layout.detect()
    grouped = _group_by_type(plan)

    console.print()
    ui.rule(console, "Files it will write", layout=layout)

    for file_type in _TYPE_ORDER:
        files = grouped.get(file_type)
        if not files:
            continue
        label = _TYPE_LABELS.get(file_type, file_type.title())
        console.print("  {0} ({1})".format(label, len(files)), style=get_theme().style("heading"))
        for file_info in files[: _preview_count(layout)]:
            console.print("    " + ui.truncate(file_info.path, layout.body_width - 4), style=get_theme().style("muted"))
        if len(files) > _preview_count(layout):
            console.print(
                "    +{0} more".format(len(files) - _preview_count(layout)),
                style=get_theme().style("dim_rule"),
            )


def display_next_steps(plan: ProjectPlan, console, layout: Optional[Layout] = None) -> None:
    layout = layout or Layout.detect()
    if not plan.next_steps:
        return
    console.print()
    ui.rule(console, "Afterwards", layout=layout)
    for index, step in enumerate(plan.next_steps[:5], 1):
        console.print(ui.wrap("  {0}. {1}".format(index, step), layout.body_width, indent="     "))


def show_detailed_file_review(plan: ProjectPlan, console, layout: Optional[Layout] = None,
                              input_fn: Optional[Callable[[str], str]] = None) -> None:
    """
    Every file with its purpose — paged, not one-Enter-per-file.

    The old flow asked you to press Enter after each of ~20 files. On a phone
    that is 20 taps to read a list.
    """
    layout = layout or Layout.detect()
    per_page = 5 if layout.narrow else 12
    total = len(plan.files)

    for start in range(0, total, per_page):
        window = plan.files[start : start + per_page]
        console.print()
        ui.rule(console, "Files {0}-{1} of {2}".format(start + 1, min(start + per_page, total), total), layout=layout)
        for file_info in window:
            console.print("  " + ui.truncate(file_info.path, layout.body_width - 2), style=get_theme().style("key"))
            if file_info.description:
                console.print(ui.wrap("    " + file_info.description, layout.body_width, indent="    "),
                              style=get_theme().style("muted"))
            if file_info.dependencies:
                deps = ", ".join(file_info.dependencies[:3])
                if len(file_info.dependencies) > 3:
                    deps += ", +{0}".format(len(file_info.dependencies) - 3)
                console.print(ui.wrap("    after: " + deps, layout.body_width, indent="    "),
                              style=get_theme().style("dim_rule"))
        if start + per_page < total:
            pause(console, "More files", layout=layout, input_fn=input_fn)


def show_plan_approval_screen(
    plan: ProjectPlan,
    console=None,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Show the plan and ask what to do with it.

    Returns one of APPROVE / DETAILS-resolved / REVISE / CANCEL. DETAILS loops
    internally, so callers only ever see APPROVE, REVISE or CANCEL.
    """
    if console is None:
        from rich.console import Console

        console = Console()
    layout = layout or Layout.detect()

    while True:
        display_plan_summary(plan, console, layout)
        display_file_plan(plan, console, layout)
        display_next_steps(plan, console, layout)

        console.print()
        answer = ask_choice(
            console,
            "Build this?",
            [
                Choice(value=APPROVE, label="Yes, build it", description="Generate every file"),
                Choice(value=DETAILS, label="Show me every file", description="Read the full list first"),
                Choice(value=REVISE, label="Change the description", description="Re-plan with different wording"),
                Choice(value=CANCEL, label="Cancel", description="Go back, write nothing"),
            ],
            default=APPROVE,
            layout=layout,
            input_fn=input_fn,
            allow_back=False,
            help_text="Nothing is written to disk until you say yes.",
        )

        if answer == DETAILS:
            show_detailed_file_review(plan, console, layout, input_fn)
            continue
        return answer


def display_plan_error(error_msg: str, console=None, layout: Optional[Layout] = None) -> None:
    if console is None:
        from rich.console import Console

        console = Console()
    ui.card(console, error_msg, title="Couldn't make a plan", tone="err", layout=layout or Layout.detect())
