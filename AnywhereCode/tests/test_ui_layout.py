"""Tests for anyplace.ui.layout -- breakpoints, capability + env detection."""

import dataclasses

import pytest

from anyplace.ui.layout import (
    LG,
    MD,
    MIN_WIDTH,
    SM,
    XS,
    Layout,
    breakpoint_for,
    content_width,
    is_narrow,
    is_termux,
    supports_color,
    supports_emoji,
    supports_unicode,
    terminal_size,
)

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
    "NO_UNICODE",
    "TERMUX_VERSION",
    "PREFIX",
    "COLUMNS",
    "LINES",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts from a known-empty environment."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# -- breakpoints -----------------------------------------------------------


@pytest.mark.parametrize(
    "width,expected",
    [
        (20, XS),
        (30, XS),
        (39, XS),
        (40, SM),
        (45, SM),
        (59, SM),
        (60, MD),
        (80, MD),
        (89, MD),
        (90, LG),
        (120, LG),
        (400, LG),
    ],
)
def test_breakpoint_for_maps_width_to_tier(width, expected):
    assert breakpoint_for(width) == expected


def test_breakpoint_for_boundary_xs_sm_is_exactly_40():
    assert breakpoint_for(39) == XS
    assert breakpoint_for(40) == SM


def test_breakpoint_for_boundary_sm_md_is_exactly_60():
    assert breakpoint_for(59) == SM
    assert breakpoint_for(60) == MD


def test_breakpoint_for_boundary_md_lg_is_exactly_90():
    assert breakpoint_for(89) == MD
    assert breakpoint_for(90) == LG


def test_breakpoint_for_junk_width_falls_back_to_md():
    assert breakpoint_for("not-a-number") == MD


def test_is_narrow_boundary_is_exactly_60():
    assert is_narrow(59) is True
    assert is_narrow(60) is False


def test_is_narrow_without_width_uses_env_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "32")
    assert is_narrow() is True
    monkeypatch.setenv("ANYWHERE_WIDTH", "100")
    assert is_narrow() is False


# -- terminal_size ---------------------------------------------------------


def test_terminal_size_uses_env_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "37")
    monkeypatch.setenv("ANYWHERE_HEIGHT", "11")
    assert terminal_size() == (37, 11)


def test_terminal_size_clamps_absurdly_small_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "3")
    width, _ = terminal_size()
    assert width == MIN_WIDTH


def test_terminal_size_ignores_junk_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "wide-ish")
    monkeypatch.setenv("COLUMNS", "77")
    monkeypatch.setenv("LINES", "21")
    assert terminal_size() == (77, 21)


def test_terminal_size_falls_back_to_defaults(monkeypatch):
    def boom(fallback=(0, 0)):
        raise OSError("no tty")

    monkeypatch.setattr("anyplace.ui.layout.shutil.get_terminal_size", boom)
    assert terminal_size(default_width=64, default_height=18) == (64, 18)


# -- capability detection --------------------------------------------------


def test_supports_unicode_respects_ascii_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    assert supports_unicode() is False


def test_supports_unicode_respects_unicode_override(monkeypatch):
    monkeypatch.setenv("ANYWHERE_UNICODE", "1")
    monkeypatch.setenv("ANYWHERE_ASCII", "1")  # explicit unicode wins
    assert supports_unicode() is True


def test_supports_unicode_false_when_stdout_is_ascii(monkeypatch):
    class FakeOut:
        encoding = "ascii"

    monkeypatch.setattr("anyplace.ui.layout.sys.stdout", FakeOut())
    assert supports_unicode() is False


def test_supports_emoji_false_when_unicode_unavailable(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    assert supports_emoji() is False


def test_supports_emoji_false_for_mono_theme(monkeypatch):
    monkeypatch.setenv("ANYWHERE_THEME", "mono")
    assert supports_emoji() is False


def test_supports_emoji_respects_explicit_off(monkeypatch):
    monkeypatch.setenv("ANYWHERE_EMOJI", "0")
    assert supports_emoji() is False


def test_supports_color_false_when_no_color_set(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    assert supports_color() is False


def test_supports_color_true_by_default():
    assert supports_color() is True


def test_supports_color_force_color_beats_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert supports_color() is True


def test_is_termux_detects_prefix(monkeypatch):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert is_termux() is True


def test_is_termux_detects_version_var(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    assert is_termux() is True


def test_is_termux_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    monkeypatch.setenv("ANYWHERE_TERMUX", "0")
    assert is_termux() is False


def test_is_termux_false_on_a_normal_machine():
    assert is_termux() is False


# -- content_width ---------------------------------------------------------


def test_content_width_caps_at_max_width():
    assert content_width(200, max_width=100) == 100


def test_content_width_passes_through_small_widths():
    assert content_width(45) == 45


def test_content_width_never_below_minimum():
    assert content_width(5) == MIN_WIDTH


# -- Layout ----------------------------------------------------------------


@pytest.mark.parametrize(
    "width,bp,gutter",
    [(30, XS, 0), (38, XS, 0), (45, SM, 1), (55, SM, 1), (62, MD, 2), (80, MD, 2), (120, LG, 2)],
)
def test_layout_detect_reports_tier_and_gutter(width, bp, gutter):
    layout = Layout.detect(width=width)
    assert layout.width == width
    assert layout.bp == bp
    assert layout.gutter == gutter
    assert layout.pad == " " * gutter


@pytest.mark.parametrize("width", [30, 38, 45, 55, 62, 80, 120])
def test_layout_body_width_leaves_room_for_gutters(width):
    layout = Layout.detect(width=width)
    assert layout.body_width <= width
    assert layout.body_width >= MIN_WIDTH
    assert layout.body_width == max(MIN_WIDTH, width - 2 * layout.gutter)


def test_layout_narrow_matches_breakpoint():
    assert Layout.detect(width=59).narrow is True
    assert Layout.detect(width=60).narrow is False


def test_layout_detect_without_width_uses_env(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "34")
    monkeypatch.setenv("ANYWHERE_HEIGHT", "12")
    layout = Layout.detect()
    assert (layout.width, layout.height, layout.bp) == (34, 12, XS)


def test_layout_explicit_width_beats_env(monkeypatch):
    monkeypatch.setenv("ANYWHERE_WIDTH", "34")
    assert Layout.detect(width=100).width == 100


def test_layout_is_frozen():
    layout = Layout.detect(width=80)
    with pytest.raises(dataclasses.FrozenInstanceError):
        layout.width = 20  # type: ignore[misc]


def test_layout_with_width_returns_remeasured_copy():
    layout = Layout.detect(width=100)
    narrow = layout.with_width(32)
    assert narrow.bp == XS and narrow.narrow is True
    assert layout.width == 100  # original untouched


def test_layout_carries_capability_flags(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    layout = Layout.detect(width=80)
    assert layout.unicode is False
    assert layout.emoji is False
    assert layout.color is False
