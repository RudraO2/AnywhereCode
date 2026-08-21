"""Tests for anyplace.ui.theme -- tokens, icon fallbacks, theme resolution."""

import pytest
from rich.cells import cell_len

from anyplace.ui.theme import (
    DEFAULT_THEME,
    ICONS,
    THEMES,
    TOKENS,
    Theme,
    get_theme,
    theme_names,
)

REQUIRED_TOKENS = (
    "accent",
    "muted",
    "ok",
    "warn",
    "err",
    "info",
    "heading",
    "key",
    "panel",
    "dim_rule",
)

REQUIRED_ICONS = (
    "ok",
    "warn",
    "err",
    "info",
    "arrow",
    "bullet",
    "spark",
    "folder",
    "file",
    "gear",
    "rocket",
    "phone",
    "robot",
    "star",
    "back",
    "quit",
    "run",
    "plan",
    "edit",
    "search",
    "check",
    "cross",
    "dot",
)

ENV_VARS = ("ANYWHERE_THEME", "NO_COLOR", "FORCE_COLOR")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# -- tokens ----------------------------------------------------------------


def test_required_tokens_are_declared():
    assert set(REQUIRED_TOKENS) <= set(TOKENS)


@pytest.mark.parametrize("theme_name", sorted(THEMES))
@pytest.mark.parametrize("token", REQUIRED_TOKENS)
def test_every_theme_defines_every_token(theme_name, token):
    theme = THEMES[theme_name]
    assert theme.has_token(token), "{} missing token {}".format(theme_name, token)
    assert isinstance(theme.style(token), str)


@pytest.mark.parametrize("token", REQUIRED_TOKENS)
def test_colour_themes_have_non_empty_styles(token):
    assert THEMES["default"].style(token)
    assert THEMES["highcontrast"].style(token)


def test_mono_theme_uses_no_colour_names():
    for token in REQUIRED_TOKENS:
        style = THEMES["mono"].style(token)
        assert style in ("", "bold", "dim"), "mono leaked colour in {}: {}".format(token, style)


def test_style_of_unknown_token_is_empty_string():
    assert DEFAULT_THEME.style("no-such-token") == ""


# -- icons -----------------------------------------------------------------


@pytest.mark.parametrize("name", REQUIRED_ICONS)
def test_required_icon_resolves_in_both_modes(name):
    assert name in ICONS
    rich_glyph = DEFAULT_THEME.icon(name, emoji=True)
    ascii_glyph = DEFAULT_THEME.icon(name, emoji=False)
    assert rich_glyph, "no unicode glyph for {}".format(name)
    assert ascii_glyph, "no ascii glyph for {}".format(name)


@pytest.mark.parametrize("name", REQUIRED_ICONS)
def test_ascii_fallback_is_pure_ascii_and_narrow(name):
    fallback = DEFAULT_THEME.icon(name, emoji=False)
    assert all(ord(ch) < 128 for ch in fallback)
    assert cell_len(fallback) == len(fallback)
    assert cell_len(fallback) <= 3


@pytest.mark.parametrize("name", REQUIRED_ICONS)
def test_mono_theme_always_uses_ascii_icons(name):
    assert THEMES["mono"].icon(name, emoji=True) == DEFAULT_THEME.icon(name, emoji=False)


def test_unknown_icon_returns_empty_string_rather_than_raising():
    assert DEFAULT_THEME.icon("definitely-not-an-icon") == ""
    assert DEFAULT_THEME.icon("definitely-not-an-icon", emoji=False) == ""


def test_unicode_glyphs_are_at_most_two_cells():
    for name in REQUIRED_ICONS:
        assert cell_len(DEFAULT_THEME.icon(name, emoji=True)) <= 2


# -- resolution ------------------------------------------------------------


def test_get_theme_defaults_to_default():
    assert get_theme().name == "default"


@pytest.mark.parametrize("name", ["default", "mono", "highcontrast"])
def test_get_theme_by_explicit_name(name):
    assert get_theme(name).name == name


def test_get_theme_is_case_insensitive():
    assert get_theme("MONO").name == "mono"


def test_get_theme_unknown_name_falls_back_to_default():
    assert get_theme("neon-dreams").name == "default"


def test_get_theme_reads_env_var(monkeypatch):
    monkeypatch.setenv("ANYWHERE_THEME", "highcontrast")
    assert get_theme().name == "highcontrast"


def test_get_theme_explicit_name_beats_env(monkeypatch):
    monkeypatch.setenv("ANYWHERE_THEME", "highcontrast")
    assert get_theme("mono").name == "mono"


def test_no_color_forces_mono_theme(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert get_theme().name == "mono"
    assert get_theme("highcontrast").name == "mono"


def test_no_color_empty_value_still_counts(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    assert get_theme().name == "mono"


def test_theme_names_lists_all_themes():
    assert set(theme_names()) == set(THEMES)


def test_theme_is_hashable_and_frozen():
    theme = get_theme()
    assert hash(theme) == hash(Theme(theme.name, dict(theme.styles)))
    with pytest.raises(Exception):
        theme.name = "nope"  # type: ignore[misc]
