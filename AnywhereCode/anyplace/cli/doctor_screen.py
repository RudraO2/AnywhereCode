"""
`anywhere doctor`, on screen.

Termux breaks in a handful of predictable ways — no storage permission, no node,
`~/.local/bin` missing from PATH. `anyplace.core.doctor` finds them; this renders
the findings with the exact command that fixes each one.
"""

from __future__ import annotations

from typing import Optional

from anyplace.core.doctor import FAIL, PASS, SKIP, WARN, DoctorReport
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.theme import get_theme

_TONE = {PASS: "ok", WARN: "warn", FAIL: "err", SKIP: "muted"}
_ICON = {PASS: "ok", WARN: "warn", FAIL: "err", SKIP: "dot"}


def render_report(console, report: DoctorReport, layout: Optional[Layout] = None) -> None:
    """Print the full checkup, then the fixes that matter."""
    layout = layout or Layout.detect()
    theme = get_theme()

    rows = []
    for check in report.checks:
        icon = theme.icon(_ICON.get(check.status, "dot"), emoji=layout.emoji)
        rows.append((icon, check.title, check.detail))

    ui.steps(console, rows, layout=layout)

    problems = report.by_status(FAIL) + report.by_status(WARN)
    if problems:
        console.print()
        ui.rule(console, "How to fix", layout=layout)
        for check in problems:
            if not check.fix:
                continue
            tone = _TONE.get(check.status, "info")
            ui.card(console, check.fix, title=check.title, tone=tone, layout=layout)

    counts = report.summary()
    console.print()
    if report.healthy and not report.by_status(WARN):
        ui.card(console, "Everything checks out. You're ready to build.", title="All good", tone="ok", layout=layout)
    elif report.healthy:
        ui.card(
            console,
            "{0} thing(s) worth a look, but nothing blocking.".format(counts.get(WARN, 0)),
            title="Mostly fine",
            tone="warn",
            layout=layout,
        )
    else:
        ui.card(
            console,
            "{0} thing(s) need fixing before this will work properly.".format(counts.get(FAIL, 0)),
            title="Needs attention",
            tone="err",
            layout=layout,
        )
