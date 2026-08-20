"""Tests for anyplace.ui.components.

The load-bearing invariant: nothing this module renders may ever be wider than
the console it is printed to, at any width from 30 to 120 columns. Widths are
measured with ``rich.cells.cell_len`` so double-width emoji count as two.
"""

import pytest
from rich.cells import cell_len
from rich.console import Console

from anyplace.ui.components import (
    MenuItem,
    banner,
    card,
    data_table,
    hint_bar,
    kv,
    menu,
    progress_line,
    rule,
    steps,
    truncate,
    wrap,
)
from anyplace.ui.layout import Layout

WIDTHS = [30, 38, 45, 55, 62, 80, 120]
NARROW_WIDTHS = [30, 38, 45, 55]
WIDE_WIDTHS = [62, 80, 120]

ENV_VARS = (
    "ANYWHERE_WIDTH",
    "ANYWHERE_HEIGHT",
    "ANYWHERE_THEME",
    "ANYWHERE_UNICODE",
    "ANYWHERE_ASCII",
    "ANYWHERE_EMOJI",
    "ANYWHERE_TERMUX",
    "NO_COLOR",
    "FORCE_COLOR",
    "COLUMNS",
    "LINES",
)

LOREM = (
    "Anywhere Code turns a short interview into a working repo, then keeps "
    "going until the thing actually builds on your phone."
)

MENU_ITEMS = [
    MenuItem("1", "New project", "Answer a few questions and I build it"),
    MenuItem("2", "Open recent", "snake-game, pocket-api, notes-web"),
    MenuItem("3", "Doctor", "Check your phone's toolchain for problems"),
    MenuItem("4", "Deploy", "Push to Vercel or Fly", badge="beta"),
    MenuItem("5", "Sync", "Needs a network connection", disabled=True),
]

TABLE_COLS = ["Template", "Type", "Stack", "Files"]
TABLE_ROWS = [
    ["react-vite", "web", "React 18, Vite, Tailwind CSS", "24"],
    ["fastapi", "backend", "FastAPI, SQLAlchemy, Postgres, Alembic", "17"],
    ["expo-rn", "mobile", "React Native, Expo Router", "31"],
]

STEP_ITEMS = [
    ("pass", "Plan", "12 files, 3 folders"),
    ("run", "Generate", "src/components/Board.tsx"),
    ("todo", "Install", "npm install --legacy-peer-deps"),
    ("fail", "Deploy", "vercel: missing token"),
]

HINTS = [("1-5", "pick"), ("b", "back"), ("q", "quit"), ("?", "help")]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# -- shared rendering helper ----------------------------------------------
# (tests/conftest.py belongs to another agent, so this lives here.)


def render(component_call, width):
    """Render ``component_call(console)`` at ``width`` and return plain text."""
    console = Console(
        width=width,
        record=True,
        force_terminal=False,
        color_system=None,
        legacy_windows=False,
    )
    component_call(console)
    return console.export_text()


def lines_of(text):
    return [line for line in text.splitlines()]


def widest(text):
    return max([cell_len(line) for line in text.splitlines()] or [0])


def assert_fits(text, width):
    for i, line in enumerate(text.splitlines()):
        assert cell_len(line) <= width, "line {} is {} cells wide (max {}): {!r}".format(
            i, cell_len(line), width, line
        )


# -- pure text helpers -----------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_wrap_never_exceeds_width(width):
    for line in wrap(LOREM, width).splitlines():
        assert cell_len(line) <= width


@pytest.mark.parametrize("width", WIDTHS)
def test_wrap_respects_indent_within_width(width):
    for line in wrap(LOREM, width, indent="    ").splitlines():
        assert cell_len(line) <= width
        assert line.startswith("    ")


@pytest.mark.parametrize("width", [4, 8, 12, 30])
def test_wrap_hard_splits_words_longer_than_width(width):
    text = "https://example.com/a/very/long/path/that/never/breaks"
    out = wrap(text, width)
    for line in out.splitlines():
        assert cell_len(line) <= width
    assert "".join(out.split()) == text


@pytest.mark.parametrize("width", WIDTHS)
def test_wrap_handles_emoji_without_overflowing(width):
    text = "🚀 launch 📱 phone 🤖 robot " * 4
    for line in wrap(text, width).splitlines():
        assert cell_len(line) <= width


def test_wrap_preserves_explicit_newlines():
    assert wrap("one\ntwo", 40) == "one\ntwo"


def test_wrap_of_empty_text_is_empty():
    assert wrap("", 30) == ""


@pytest.mark.parametrize("width", [1, 2, 3, 5, 10, 30])
def test_truncate_never_exceeds_width(width):
    assert cell_len(truncate(LOREM, width)) <= width


@pytest.mark.parametrize("width", [1, 2, 4, 9, 20])
def test_truncate_never_exceeds_width_with_emoji(width):
    assert cell_len(truncate("🚀🚀🚀🚀🚀🚀🚀🚀", width)) <= width


def test_truncate_leaves_short_text_alone():
    assert truncate("short", 20) == "short"


def test_truncate_marks_elision():
    out = truncate("abcdefghij", 6)
    assert out.endswith(("…", "..."))
    assert cell_len(out) <= 6


def test_truncate_ascii_ellipsis_when_unicode_unavailable(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    assert truncate("abcdefghij", 6).endswith("...")


def test_truncate_zero_width_is_empty():
    assert truncate("anything", 0) == ""


def test_truncate_collapses_newlines():
    assert "\n" not in truncate("a\nb", 40)


# -- banner ----------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_banner_fits_every_width(width):
    out = render(lambda c: banner(c, subtitle="ship from your phone"), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_banner_fits_without_subtitle(width):
    assert_fits(render(banner, width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_banner_fits_with_absurd_subtitle(width):
    out = render(lambda c: banner(c, subtitle="x" * 300), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", [30, 38, 45, 55])
def test_banner_is_a_two_line_badge_when_narrow(width):
    out = render(lambda c: banner(c, subtitle="ship from your phone"), width)
    assert len(lines_of(out)) == 2
    assert "ANYWHERE CODE" in out


@pytest.mark.parametrize("width", [62, 80, 89])
def test_banner_is_a_one_line_lockup_at_md(width):
    out = render(lambda c: banner(c, subtitle="ship from your phone"), width)
    assert len(lines_of(out)) == 1
    assert "ANYWHERE CODE" in out


@pytest.mark.parametrize("width", [90, 120])
def test_banner_is_a_wordmark_at_lg(width):
    out = render(lambda c: banner(c, subtitle="ship from your phone"), width)
    rows = lines_of(out)
    assert len(rows) == 7  # five wordmark rows + tagline + rule
    assert "█" in out
    assert_fits(out, width)


def test_banner_boundary_89_is_lockup_and_90_is_wordmark():
    assert "█" not in render(banner, 89)
    assert "█" in render(banner, 90)


def test_banner_uses_ascii_art_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(banner, 100)
    assert "#" in out
    assert "█" not in out


def test_banner_badge_uses_ascii_bar_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(banner, 32)
    assert "▌" not in out
    assert "|" in out


# -- card ------------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_card_fits_every_width(width):
    out = render(lambda c: card(c, LOREM, title="What is this?"), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("tone", ["info", "ok", "warn", "err", "accent", "nonsense"])
def test_card_fits_for_every_tone(width, tone):
    out = render(lambda c: card(c, LOREM, title="Heads up", tone=tone), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", NARROW_WIDTHS)
def test_card_drops_the_box_when_narrow(width):
    out = render(lambda c: card(c, LOREM, title="Title"), width)
    assert "╭" not in out and "╰" not in out
    assert "▌" in out
    assert "Title" in out


@pytest.mark.parametrize("width", WIDE_WIDTHS)
def test_card_uses_a_rounded_box_when_wide(width):
    out = render(lambda c: card(c, LOREM, title="Title"), width)
    assert "╭" in out and "╰" in out


def test_card_boundary_59_is_bar_and_60_is_box():
    assert "▌" in render(lambda c: card(c, "hello", title="T"), 59)
    assert "╭" in render(lambda c: card(c, "hello", title="T"), 60)


@pytest.mark.parametrize("width", WIDTHS)
def test_card_accepts_a_list_of_lines(width):
    out = render(lambda c: card(c, ["first line", "second line"], title="List"), width)
    assert_fits(out, width)
    assert "first line" in out


@pytest.mark.parametrize("width", WIDTHS)
def test_card_fits_with_a_long_unbreakable_token(width):
    body = "/data/data/com.termux/files/home/projects/very-long-name/src/index.ts"
    assert_fits(render(lambda c: card(c, body, title="Path"), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_card_fits_with_a_long_title(width):
    assert_fits(render(lambda c: card(c, "body", title="T" * 200), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_card_with_empty_body_still_fits(width):
    assert_fits(render(lambda c: card(c, "", title="Empty"), width), width)


def test_card_uses_ascii_box_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(lambda c: card(c, "hello", title="T"), 80)
    assert "╭" not in out
    assert "+" in out


# -- menu ------------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_fits_every_width(width):
    out = render(lambda c: menu(c, MENU_ITEMS, title="MAIN MENU", footer="Tap a number."), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_shows_every_key_and_label(width):
    out = render(lambda c: menu(c, MENU_ITEMS, title="MAIN MENU"), width)
    for item in MENU_ITEMS:
        assert item.key in out
        assert item.label in out


@pytest.mark.parametrize("width", NARROW_WIDTHS)
def test_menu_puts_description_on_its_own_line_when_narrow(width):
    out = render(lambda c: menu(c, MENU_ITEMS), width)
    rows = lines_of(out)
    label_row = [i for i, line in enumerate(rows) if "New project" in line][0]
    assert "Answer a few questions" not in rows[label_row]
    assert "Answer" in rows[label_row + 1]


@pytest.mark.parametrize("width", WIDE_WIDTHS)
def test_menu_puts_description_beside_label_when_wide(width):
    out = render(lambda c: menu(c, MENU_ITEMS), width)
    row = [line for line in lines_of(out) if "New project" in line][0]
    assert "Answer" in row


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_renders_badges(width):
    out = render(lambda c: menu(c, MENU_ITEMS), width)
    assert "beta" in out


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_with_no_items_says_so(width):
    out = render(lambda c: menu(c, [], title="Empty"), width)
    assert "nothing" in out.lower()
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_fits_with_very_long_labels(width):
    items = [MenuItem("1", "L" * 120, "D" * 200), MenuItem("2", "short", "")]
    assert_fits(render(lambda c: menu(c, items), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_fits_with_emoji_labels(width):
    items = [MenuItem("1", "Deploy", "to the cloud", icon="🚀"), MenuItem("2", "Phone", "", icon="📱")]
    assert_fits(render(lambda c: menu(c, items), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_menu_fits_with_double_digit_keys(width):
    items = [MenuItem(str(i), "Item {}".format(i), "desc") for i in range(1, 13)]
    assert_fits(render(lambda c: menu(c, items), width), width)


# -- kv --------------------------------------------------------------------


PAIRS = [
    ("Name", "pocket-snake"),
    ("Kind", "web"),
    ("Stack", "React 18, Vite, Tailwind CSS, Zustand, Vitest, Playwright"),
    ("Deploy", ""),
]


@pytest.mark.parametrize("width", WIDTHS)
def test_kv_fits_every_width(width):
    assert_fits(render(lambda c: kv(c, PAIRS, title="Project"), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_kv_shows_all_keys(width):
    out = render(lambda c: kv(c, PAIRS), width)
    for key, _ in PAIRS:
        assert key in out


@pytest.mark.parametrize("width", WIDTHS)
def test_kv_with_no_pairs_renders_nothing_but_title(width):
    out = render(lambda c: kv(c, [], title="Nothing"), width)
    assert [line.strip() for line in lines_of(out)] == ["Nothing"]
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_kv_stacks_when_keys_are_enormous(width):
    pairs = [("A very long field label indeed", "value"), ("Short", "value")]
    out = render(lambda c: kv(c, pairs), width)
    assert_fits(out, width)
    assert "value" in out


# -- data_table ------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_fits_every_width(width):
    out = render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS, title="Templates"), width)
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDE_WIDTHS)
def test_data_table_uses_a_real_table_when_wide(width):
    out = render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS), width)
    assert "│" in out and "╭" in out


@pytest.mark.parametrize("width", NARROW_WIDTHS)
def test_data_table_stacks_records_when_narrow(width):
    out = render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS), width)
    assert "│" not in out
    assert "Template:" in out
    assert "Type:" in out


def test_data_table_boundary_59_stacks_and_60_tabulates():
    assert "│" not in render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS), 59)
    assert "│" in render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS), 60)


@pytest.mark.parametrize("width", NARROW_WIDTHS)
def test_data_table_separates_stacked_records_with_a_rule(width):
    out = render(lambda c: data_table(c, TABLE_COLS, TABLE_ROWS), width)
    assert any(set(line.strip()) == {"─"} for line in lines_of(out))


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_with_no_rows_says_so(width):
    out = render(lambda c: data_table(c, TABLE_COLS, []), width)
    assert "no rows" in out.lower()
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_tolerates_ragged_rows(width):
    rows = [["only-one"], ["a", "b", "c", "d", "e", "f"]]
    assert_fits(render(lambda c: data_table(c, TABLE_COLS, rows), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_fits_with_huge_cells(width):
    rows = [["x" * 200, "y" * 200, "z" * 200, "9" * 20]]
    assert_fits(render(lambda c: data_table(c, TABLE_COLS, rows), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_fits_with_emoji_cells(width):
    rows = [["🚀 rocket", "📱 phone", "🤖 robot bits", "3"]]
    assert_fits(render(lambda c: data_table(c, TABLE_COLS, rows), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_with_no_columns_renders_nothing(width):
    out = render(lambda c: data_table(c, [], []), width)
    assert out.strip() == ""


@pytest.mark.parametrize("width", WIDTHS)
def test_data_table_tolerates_none_cells(width):
    rows = [["a", None, "c", None]]
    assert_fits(render(lambda c: data_table(c, TABLE_COLS, rows), width), width)


# -- steps -----------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_steps_fits_every_width(width):
    assert_fits(render(lambda c: steps(c, STEP_ITEMS), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_steps_shows_every_name(width):
    out = render(lambda c: steps(c, STEP_ITEMS), width)
    for _, name, _ in STEP_ITEMS:
        assert name in out


@pytest.mark.parametrize("width", WIDTHS)
def test_steps_tolerates_unknown_status(width):
    out = render(lambda c: steps(c, [("banana", "Weird", "detail")]), width)
    assert "Weird" in out
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_steps_fits_with_long_details(width):
    items = [("pass", "N" * 60, "D" * 200)]
    assert_fits(render(lambda c: steps(c, items), width), width)


def test_steps_uses_ascii_icons_without_emoji(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(lambda c: steps(c, STEP_ITEMS), 80)
    assert "✓" not in out
    assert "+" in out


# -- hint_bar --------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_hint_bar_fits_every_width(width):
    assert_fits(render(lambda c: hint_bar(c, HINTS), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_hint_bar_is_a_single_line(width):
    out = render(lambda c: hint_bar(c, HINTS), width)
    assert len(lines_of(out)) == 1


@pytest.mark.parametrize("width", WIDTHS)
def test_hint_bar_always_keeps_the_first_hint(width):
    out = render(lambda c: hint_bar(c, HINTS), width)
    assert "1-5" in out


def test_hint_bar_drops_least_important_hints_when_cramped():
    out = render(lambda c: hint_bar(c, HINTS), 30)
    assert "pick" in out
    assert "help" not in out


def test_hint_bar_keeps_everything_when_wide():
    out = render(lambda c: hint_bar(c, HINTS), 120)
    for key, label in HINTS:
        assert key in out and label in out


def test_hint_bar_uses_middot_on_unicode_terminals():
    assert "·" in render(lambda c: hint_bar(c, HINTS), 80)


def test_hint_bar_uses_pipe_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(lambda c: hint_bar(c, HINTS), 80)
    assert "·" not in out
    assert "|" in out


def test_hint_bar_with_no_hints_renders_nothing():
    assert render(lambda c: hint_bar(c, []), 40).strip() == ""


@pytest.mark.parametrize("width", WIDTHS)
def test_hint_bar_fits_with_one_enormous_hint(width):
    out = render(lambda c: hint_bar(c, [("k" * 80, "l" * 80)]), width)
    assert_fits(out, width)


# -- rule ------------------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_rule_fits_every_width(width):
    assert_fits(render(lambda c: rule(c, "Project"), width), width)


@pytest.mark.parametrize("width", WIDTHS)
def test_rule_without_label_fills_the_line(width):
    out = render(rule, width)
    line = lines_of(out)[0]
    assert set(line.strip()) == {"─"}
    assert cell_len(line) <= width


@pytest.mark.parametrize("width", WIDTHS)
def test_rule_with_long_label_still_fits(width):
    assert_fits(render(lambda c: rule(c, "L" * 200), width), width)


def test_rule_uses_ascii_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(lambda c: rule(c, "Hi"), 60)
    assert "─" not in out
    assert "-" in out


# -- progress_line ---------------------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("index", [0, 3, 12])
def test_progress_line_fits_every_width(width, index):
    out = render(lambda c: progress_line(c, index, 12, "src/components/Board.tsx"), width)
    assert_fits(out, width)
    assert len(lines_of(out)) == 1


@pytest.mark.parametrize("width", WIDTHS)
def test_progress_line_always_shows_the_counter(width):
    out = render(lambda c: progress_line(c, 3, 12, "file.tsx"), width)
    assert "[3/12]" in out


@pytest.mark.parametrize("width", [30, 38])
def test_progress_line_has_no_bar_at_xs(width):
    out = render(lambda c: progress_line(c, 3, 12, "file.tsx"), width)
    assert "█" not in out and "░" not in out
    assert "file.tsx" in out


@pytest.mark.parametrize("width", [45, 62, 80, 120])
def test_progress_line_draws_a_bar_from_sm_upwards(width):
    out = render(lambda c: progress_line(c, 3, 12, "file.tsx"), width)
    assert "█" in out or "░" in out


def test_progress_line_boundary_39_has_no_bar_and_40_does():
    assert "░" not in render(lambda c: progress_line(c, 1, 4, "f"), 39)
    assert "░" in render(lambda c: progress_line(c, 1, 4, "f"), 40)


@pytest.mark.parametrize("width", WIDTHS)
def test_progress_line_survives_zero_total(width):
    out = render(lambda c: progress_line(c, 0, 0, "nothing"), width)
    assert_fits(out, width)
    assert "[0/0]" in out


@pytest.mark.parametrize("width", WIDTHS)
def test_progress_line_clamps_overflowing_index(width):
    out = render(lambda c: progress_line(c, 99, 12, "file.tsx"), width)
    assert "[12/12]" in out
    assert_fits(out, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_progress_line_fits_with_a_very_long_label(width):
    assert_fits(render(lambda c: progress_line(c, 1, 9, "x" * 300), width), width)


def test_progress_line_uses_ascii_bar_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    out = render(lambda c: progress_line(c, 1, 4, "f"), 80)
    assert "█" not in out
    assert "#" in out


# -- environment handling --------------------------------------------------


def test_no_color_switches_components_to_ascii_icons(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    out = render(lambda c: steps(c, STEP_ITEMS), 80)
    assert "✓" not in out
    assert "+" in out


def test_no_color_output_contains_no_ansi_escapes(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    console = Console(width=80, record=True, force_terminal=True)
    banner(console, subtitle="hi")
    menu(console, MENU_ITEMS)
    assert "\x1b[" not in console.export_text()


def test_anywhere_width_override_forces_narrow_rendering(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "32")
    out = render(lambda c: card(c, "hello", title="T"), 80)
    assert "╭" not in out
    assert "▌" in out
    assert_fits(out, 80)


def test_anywhere_width_override_cannot_exceed_the_console(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "200")
    out = render(lambda c: rule(c, "wide"), 45)
    assert_fits(out, 45)


# -- explicit layout injection --------------------------------------------


@pytest.mark.parametrize("width", WIDTHS)
def test_components_accept_an_explicit_layout(width):
    layout = Layout.detect(width=width)
    out = render(lambda c: menu(c, MENU_ITEMS, title="T", layout=layout), width)
    assert_fits(out, width)


def test_explicit_narrow_layout_wins_over_a_wide_console():
    layout = Layout.detect(width=32)
    out = render(lambda c: card(c, "hello", title="T", layout=layout), 100)
    assert "▌" in out and "╭" not in out


@pytest.mark.parametrize("width", range(30, 121, 7))
def test_every_component_fits_across_the_full_range(width):
    def draw(console):
        banner(console, subtitle="ship from your phone")
        card(console, LOREM, title="What is this?")
        menu(console, MENU_ITEMS, title="MAIN MENU", footer="Tap a number.")
        kv(console, PAIRS, title="Project")
        data_table(console, TABLE_COLS, TABLE_ROWS, title="Templates")
        steps(console, STEP_ITEMS)
        hint_bar(console, HINTS)
        rule(console, "End")
        progress_line(console, 3, 12, "src/components/Board.tsx")

    assert_fits(render(draw, width), width)
