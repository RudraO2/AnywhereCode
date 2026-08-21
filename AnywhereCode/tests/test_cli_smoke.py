"""Smoke tests: every command loads, and `--help` works on all of them.

Most of this CLI's modules are imported lazily inside the command bodies, to
keep startup fast on a phone. That is the right trade, but it means a broken
import or a renamed function in, say, `plan_preview` stays invisible until a
user runs that one command. These tests invoke every command through click's
own runner so the whole surface is exercised on every test run.

They deliberately only touch commands that are safe without arguments, network
or API keys -- anything that would generate a project is covered by the unit
suites for the modules underneath.
"""

from __future__ import annotations

import re

import pytest
from click.testing import CliRunner

from anyplace.cli.main import cli


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def runner():
    return CliRunner()


COMMAND_NAMES = sorted(cli.commands)


# ---------------------------------------------------------------------------
# --help on everything
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_every_command_help_exits_cleanly(name, runner):
    result = runner.invoke(cli, [name, "--help"])
    assert result.exit_code == 0, "`%s --help` failed:\n%s" % (name, result.output)


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_every_command_help_says_something(name, runner):
    result = runner.invoke(cli, [name, "--help"])
    body = ANSI_RE.sub("", result.output)
    assert "Usage:" in body
    assert len(body.strip()) > len("Usage:") + 10


@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_no_command_help_raises(name, runner):
    """A lazy import that broke shows up here as an exception, not a message."""
    result = runner.invoke(cli, [name, "--help"])
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        "`%s --help` raised %r" % (name, result.exception)
    )


def test_group_help_exits_cleanly(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in ANSI_RE.sub("", result.output)


def test_version_flag_reports_a_version(runner):
    from anyplace import __version__

    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_unknown_command_fails_without_a_traceback(runner):
    result = runner.invoke(cli, ["definitely-not-a-command"])
    assert result.exit_code != 0
    assert not isinstance(result.exception, (ImportError, AttributeError))


# ---------------------------------------------------------------------------
# Read-only commands actually run
#
# These are the ones a user hits before anything is configured -- the exact
# path where a stale import hurts most, because the tool has not done anything
# for them yet.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["templates", "recipes", "info", "doctor"])
def test_read_only_command_runs_without_configuration(name, runner, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(cli, [name])
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        "`%s` raised %r" % (name, result.exception)
    )
    assert result.output.strip(), "`%s` printed nothing" % name


@pytest.mark.parametrize("width", [32, 40, 80])
def test_read_only_commands_respect_a_narrow_terminal(width, runner, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("COLUMNS", str(width))
    for name in ("templates", "recipes", "info"):
        result = runner.invoke(cli, [name])
        body = ANSI_RE.sub("", result.output)
        too_long = [line for line in body.splitlines() if len(line) > width]
        assert not too_long, "`%s` overflowed %d columns: %r" % (name, width, too_long[:2])


# ---------------------------------------------------------------------------
# plan_preview keeps the signature its callers use
#
# `test_e2e.py` drifted out of sync with these once already: the functions grew
# a required `console` argument and the script kept calling them with one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func_name",
    [
        "display_plan_summary",
        "display_file_plan",
        "display_next_steps",
        "show_detailed_file_review",
    ],
)
def test_plan_preview_renderers_take_plan_and_console(func_name):
    import inspect

    from anyplace.cli import plan_preview

    func = getattr(plan_preview, func_name)
    params = list(inspect.signature(func).parameters)
    assert params[0] == "plan"
    assert params[1] == "console"


def test_plan_preview_renderers_accept_a_capture_console():
    import io

    from rich.console import Console

    from anyplace.cli.plan_preview import display_file_plan, display_plan_summary
    from anyplace.core.plan_generator import FileInfo, ProjectPlan

    plan = ProjectPlan(
        project_name="smoke",
        template="web-react-vite",
        description="A smoke-test plan",
        tech_stack=["React"],
        files=[
            FileInfo(
                path="src/main.tsx",
                description="Entry",
                file_type="source",
                dependencies=[],
            )
        ],
        key_features=["Fast"],
        estimated_time="10 minutes",
        architecture_notes="Nothing unusual.",
        next_steps=["npm install"],
    )

    console = Console(file=io.StringIO(), width=40)
    display_plan_summary(plan, console)
    display_file_plan(plan, console)

    output = console.file.getvalue()
    assert "smoke" in output
    assert "main.tsx" in output
