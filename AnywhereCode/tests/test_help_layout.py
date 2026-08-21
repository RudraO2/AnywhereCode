"""Tests for how `anywhere --help` lays itself out.

Help text is the one screen every user reads, and it is the screen most likely
to be read on a 40-column phone in a hurry. Two things have to hold:

  * every command the CLI has appears somewhere in the help, and
  * its description is readable, not truncated to "Build the project...".

Click's default two-column table fails the second on a narrow screen, which is
what COMMAND_GROUPS and the stacked renderer exist to fix.
"""

from __future__ import annotations

import re

import click
import pytest

from anyplace.cli.main import COMMAND_GROUPS, AnywhereGroup, cli
from anyplace.ui.layout import Layout


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def plain(text):
    return ANSI_RE.sub("", text)


@pytest.fixture
def ctx():
    return click.Context(cli, info_name="anywhere")


def help_at(width, monkeypatch):
    """Render the group's help as if the terminal were `width` columns."""
    layout = Layout.detect(width=width)
    monkeypatch.setattr(
        "anyplace.cli.main._ctx", lambda: (_silent_console(width), layout)
    )
    with click.Context(cli, info_name="anywhere", terminal_width=width, max_content_width=width) as c:
        return plain(cli.get_help(c))


def _silent_console(width):
    import io

    from rich.console import Console

    return Console(file=io.StringIO(), width=width, force_terminal=False)


# ---------------------------------------------------------------------------
# COMMAND_GROUPS as data
# ---------------------------------------------------------------------------


def test_command_groups_is_not_empty():
    assert COMMAND_GROUPS


def test_command_group_headings_are_unique():
    headings = [heading for heading, _ in COMMAND_GROUPS]
    assert len(set(headings)) == len(headings)


def test_command_group_headings_fit_a_narrow_screen():
    for heading, _ in COMMAND_GROUPS:
        assert heading.strip()
        assert len(heading) <= 24


def test_no_command_is_listed_in_two_groups():
    seen = []
    for _, names in COMMAND_GROUPS:
        seen.extend(names)
    assert len(set(seen)) == len(seen), "a command appears in more than one group"


def test_every_grouped_name_is_a_real_command():
    known = set(cli.commands)
    for heading, names in COMMAND_GROUPS:
        for name in names:
            assert name in known, "%s lists %r, which is not a command" % (heading, name)


# ---------------------------------------------------------------------------
# grouped_commands
# ---------------------------------------------------------------------------


def test_grouped_commands_covers_every_command(ctx):
    listed = set()
    for _, rows in cli.grouped_commands(ctx):
        listed.update(name for name, _ in rows)
    assert listed == set(cli.commands)


def test_grouped_commands_never_repeats_a_command(ctx):
    names = [name for _, rows in cli.grouped_commands(ctx) for name, _ in rows]
    assert len(set(names)) == len(names)


def test_grouped_commands_preserves_the_declared_order(ctx):
    sections = dict(cli.grouped_commands(ctx))
    for heading, wanted in COMMAND_GROUPS:
        if heading in sections:
            got = [name for name, _ in sections[heading]]
            assert got == [n for n in wanted if n in set(cli.commands)]


def test_an_ungrouped_command_still_appears(ctx):
    """The safety net: a new command must not vanish from --help."""

    group = AnywhereGroup(name="demo")
    group.add_command(click.Command("configure", help="Set up."))
    group.add_command(click.Command("brand-new-thing", help="Something nobody grouped."))

    sections = group.grouped_commands(click.Context(group))
    listed = set(name for _, rows in sections for name, _ in rows)

    assert "brand-new-thing" in listed
    assert ("More" in dict(sections))


def test_hidden_commands_are_not_listed():
    group = AnywhereGroup(name="demo")
    group.add_command(click.Command("configure", help="Set up."))
    group.add_command(click.Command("secret", help="Internal.", hidden=True))

    sections = group.grouped_commands(click.Context(group))
    listed = set(name for _, rows in sections for name, _ in rows)

    assert "secret" not in listed


def test_grouped_commands_on_an_empty_group_is_empty():
    group = AnywhereGroup(name="demo")
    assert group.grouped_commands(click.Context(group)) == []


# ---------------------------------------------------------------------------
# Rendered output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width", [32, 40, 52, 60, 80, 120])
def test_every_command_appears_in_the_rendered_help(width, monkeypatch):
    text = help_at(width, monkeypatch)
    for name in cli.commands:
        assert name in text, "`%s` missing from --help at %d columns" % (name, width)


@pytest.mark.parametrize("width", [32, 40, 52, 60, 80, 120])
def test_rendered_help_never_truncates_a_description(width, monkeypatch):
    """
    The bug this layout exists to fix: descriptions cut to 'Build the...'.

    Checked by asserting each description survives *in full*, rather than by
    looking for an ellipsis -- the usage line legitimately ends in '[ARGS]...'.
    Wrapping is normalised away first, since a wrapped description is fine and
    a truncated one is not.
    """
    text = " ".join(help_at(width, monkeypatch).split())
    for name, command in cli.commands.items():
        description = " ".join(command.get_short_help_str(limit=200).split())
        assert description in text, (
            "`%s` description truncated at %d columns: %r" % (name, width, description)
        )


def test_the_truncation_check_would_catch_clicks_default(monkeypatch):
    """Guard the guard: click's own limit really does truncate at phone width."""
    doctor = cli.commands["doctor"]
    assert doctor.get_short_help_str(limit=22).endswith("...")
    assert doctor.get_short_help_str(limit=200) != doctor.get_short_help_str(limit=22)


@pytest.mark.parametrize("width", [32, 40, 52, 60, 80, 120])
def test_rendered_help_respects_the_terminal_width(width, monkeypatch):
    text = help_at(width, monkeypatch)
    too_long = [line for line in text.splitlines() if len(line) > width]
    assert not too_long, "lines overflow %d columns: %r" % (width, too_long[:3])


@pytest.mark.parametrize("width", [32, 40, 52, 60, 80, 120])
def test_every_group_heading_appears(width, monkeypatch):
    text = help_at(width, monkeypatch)
    for heading, names in COMMAND_GROUPS:
        if any(n in cli.commands for n in names):
            assert heading in text, "%r missing at %d columns" % (heading, width)


def test_narrow_help_stacks_the_description_below_the_name(monkeypatch):
    lines = help_at(40, monkeypatch).splitlines()
    idx = next(i for i, line in enumerate(lines) if line.strip() == "doctor")
    # The next non-blank line is the description, indented further than the name.
    following = lines[idx + 1]
    assert following.strip()
    assert len(following) - len(following.lstrip()) > len(lines[idx]) - len(lines[idx].lstrip())


def test_wide_help_keeps_the_name_and_description_on_one_line(monkeypatch):
    text = help_at(100, monkeypatch)
    assert re.search(r"^\s+doctor\s+Check this device", text, re.M)


def test_usage_block_comes_before_the_command_list(monkeypatch):
    text = help_at(40, monkeypatch)
    assert text.index("Usage:") < text.index("Start here:")


def test_options_block_comes_before_the_command_list(monkeypatch):
    text = help_at(40, monkeypatch)
    assert text.index("Options:") < text.index("Start here:")
