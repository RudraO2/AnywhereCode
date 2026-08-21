"""End-to-end width test: run real commands, measure what lands on screen.

The component suites already check every primitive at every breakpoint, and
they all passed while `anywhere templates` was drawing an 80-column table into
a 60-column terminal. They could not catch it, because they construct the
console themselves and hand it to the component -- so console and layout always
agreed. In the real CLI they did not: `Layout` honoured `ANYWHERE_WIDTH` and
rich did not, and the gap only appeared once a command was actually run.

So these tests go through `main()` and count characters in the output, which is
the thing a user would see going wrong.
"""

from __future__ import annotations

import re
import subprocess
import sys

import pytest


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

#: Commands that render something without needing a key, network or a project.
READ_ONLY_COMMANDS = ["templates", "recipes", "info", "doctor", "--help"]

#: Real phone widths, plus the extremes the layout claims to survive.
WIDTHS = [24, 30, 34, 40, 46, 52, 60, 72, 80, 90, 120]

#: `--help` on a subcommand goes through click's option formatter too, which
#: reserves a fixed first column for names like `--width INTEGER`.
SUBCOMMAND_HELP = ["doctor --help", "commit --help", "run --help", "new --help"]


def render(command, width):
    """Run one command at a pinned width; return its plain-text output."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from anyplace.cli.main import main;"
            "sys.argv = ['anywhere', %r];"
            "\ntry:\n    main()\nexcept SystemExit:\n    pass" % command,
        ],
        capture_output=True,
        text=True,
        env=_env(width),
    )
    return ANSI_RE.sub("", result.stdout + result.stderr)


def _env(width):
    import os

    env = dict(os.environ)
    env["ANYWHERE_WIDTH"] = str(width)
    env["COLUMNS"] = str(width)
    env.pop("NO_COLOR", None)
    return env


def overflowing(text, width):
    return [line for line in text.splitlines() if len(line) > width]


# ---------------------------------------------------------------------------
# The harness itself
# ---------------------------------------------------------------------------


def test_render_returns_output():
    assert render("templates", 40).strip()


def test_overflowing_detects_a_long_line():
    assert overflowing("x" * 50, 40) == ["x" * 50]
    assert overflowing("short", 40) == []


# ---------------------------------------------------------------------------
# Nothing may exceed the terminal width
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("command", READ_ONLY_COMMANDS)
def test_command_output_fits_the_terminal(command, width):
    text = render(command, width)
    too_long = overflowing(text, width)
    assert not too_long, "`anywhere %s` at %d columns overflowed:\n%s" % (
        command,
        width,
        "\n".join("  %3d cols: %r" % (len(l), l[:90]) for l in too_long[:5]),
    )


@pytest.mark.parametrize("width", [34, 40, 60, 80])
@pytest.mark.parametrize("command", ["templates", "recipes"])
def test_command_output_is_not_mostly_blank(command, width):
    """A layout can 'fit' by rendering nothing. Check it still says something."""
    text = render(command, width)
    filled = [line for line in text.splitlines() if line.strip()]
    assert len(filled) >= 5, "`anywhere %s` at %d columns printed almost nothing" % (
        command,
        width,
    )


@pytest.mark.parametrize("width", [34, 60, 90])
def test_templates_names_every_scaffold_at_any_width(width):
    """Narrowing may reflow the layout; it may not drop content."""
    import json
    import pathlib

    import anyplace

    text = render("templates", width)
    templates_dir = pathlib.Path(anyplace.__file__).resolve().parent / "templates"
    for directory in sorted(templates_dir.iterdir()):
        structure = directory / "structure.json"
        if not (directory.is_dir() and structure.exists()):
            continue
        display = json.loads(structure.read_text())["display_name"]
        # Long names may be truncated with an ellipsis on the narrowest screens,
        # so match on a prefix rather than the whole string.
        assert display[:12] in text, "%r missing at %d columns" % (display, width)


# ---------------------------------------------------------------------------
# The specific regression: console and layout must agree
# ---------------------------------------------------------------------------


def test_the_console_is_built_at_the_layout_width():
    from anyplace.cli.main import _ctx

    console, layout = _ctx(width=52)
    assert console.width == layout.width == 52


def test_anywhere_width_reaches_the_console():
    """The variable users set when Termux misreports its own size."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from anyplace.cli.main import _ctx;"
            "c, l = _ctx();"
            "print(c.width, l.width)",
        ],
        capture_output=True,
        text=True,
        env=_env(58),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["58", "58"]


# ---------------------------------------------------------------------------
# Subcommand help goes through click's option formatter too
# ---------------------------------------------------------------------------


def render_args(args, width):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from anyplace.cli.main import main;"
            "sys.argv = ['anywhere'] + %r;"
            "\ntry:\n    main()\nexcept SystemExit:\n    pass" % args,
        ],
        capture_output=True,
        text=True,
        env=_env(width),
    )
    return ANSI_RE.sub("", result.stdout + result.stderr)


@pytest.mark.parametrize("width", [24, 30, 40, 60, 100])
@pytest.mark.parametrize("command", SUBCOMMAND_HELP)
def test_subcommand_help_fits_the_terminal(command, width):
    text = render_args(command.split(), width)
    too_long = overflowing(text, width)
    assert not too_long, "`anywhere %s` at %d columns overflowed:\n%s" % (
        command,
        width,
        "\n".join("  %3d cols: %r" % (len(l), l[:90]) for l in too_long[:5]),
    )


@pytest.mark.parametrize("width", [24, 30, 40])
def test_subcommand_help_still_documents_its_options(width):
    text = render_args(["commit", "--help"], width)
    assert "--dry-run" in text
    assert "--dir" in text
    assert "Options:" in text
