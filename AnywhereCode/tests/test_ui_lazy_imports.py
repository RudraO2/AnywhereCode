"""The `anyplace.ui` package re-exports lazily, and that is load-bearing.

Its docstring promises three layers "importable independently", with `layout`
as pure stdlib. That promise was false while `__init__` eagerly imported
`components`: any module touching `anyplace.ui.layout` paid for `rich`,
including `anyplace.core.doctor`, which is supposed to be pure logic.

On a phone that import cost is not academic -- it is on the path of every
command, on a CPU several times slower than the one running these tests.

These tests pin both halves: the laziness, and the re-exports still working.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from anyplace import ui


def run_probe(code):
    """Run `code` in a clean interpreter; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


LOADED = (
    "import sys;"
    "%s;"
    "print('rich' if 'rich' in sys.modules else 'clean')"
)


# ---------------------------------------------------------------------------
# Laziness
# ---------------------------------------------------------------------------


def test_importing_layout_does_not_load_rich():
    code, out, err = run_probe(LOADED % "import anyplace.ui.layout")
    assert code == 0, err
    assert out == "clean"


def test_importing_theme_does_not_load_rich():
    code, out, err = run_probe(LOADED % "import anyplace.ui.theme")
    assert code == 0, err
    assert out == "clean"


def test_importing_the_ui_package_does_not_load_rich():
    code, out, err = run_probe(LOADED % "import anyplace.ui")
    assert code == 0, err
    assert out == "clean"


def test_touching_a_layout_export_does_not_load_rich():
    code, out, err = run_probe(LOADED % "from anyplace import ui; ui.terminal_size()")
    assert code == 0, err
    assert out == "clean"


def test_touching_a_component_export_does_load_rich():
    """The other direction: laziness must not mean the export is broken."""
    code, out, err = run_probe(LOADED % "from anyplace import ui; ui.card")
    assert code == 0, err
    assert out == "rich"


def test_layout_is_cheaper_to_import_than_components():
    code, out, err = run_probe(
        "import sys, time;"
        "t = time.perf_counter();"
        "import anyplace.ui.layout;"
        "a = time.perf_counter() - t;"
        "t = time.perf_counter();"
        "import anyplace.ui.components;"
        "b = time.perf_counter() - t;"
        "print('ok' if b > a else 'components was not slower')"
    )
    assert code == 0, err
    assert out == "ok"


# ---------------------------------------------------------------------------
# The re-exports still behave like ordinary attributes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ui.__all__))
def test_every_advertised_export_resolves(name):
    assert getattr(ui, name) is not None


@pytest.mark.parametrize("name", sorted(ui.__all__))
def test_every_advertised_export_matches_its_source_module(name):
    import importlib

    module = importlib.import_module(ui._EXPORTS[name])
    assert getattr(ui, name) is getattr(module, name)


def test_all_and_the_export_table_agree():
    assert set(ui.__all__) == set(ui._EXPORTS)


def test_dir_lists_the_exports():
    listed = dir(ui)
    for name in ui.__all__:
        assert name in listed


def test_an_unknown_attribute_raises_attribute_error():
    with pytest.raises(AttributeError) as excinfo:
        ui.definitely_not_exported
    assert "definitely_not_exported" in str(excinfo.value)


def test_a_resolved_export_is_cached_on_the_module():
    code, out, err = run_probe(
        "from anyplace import ui;"
        "first = ui.truncate;"
        "print('cached' if ui.__dict__.get('truncate') is first else 'not cached')"
    )
    assert code == 0, err
    assert out == "cached"


def test_star_import_still_works():
    code, out, err = run_probe(
        "exec('from anyplace.ui import *');"
        "print('ok' if 'card' in dir() and 'terminal_size' in dir() else 'missing')"
    )
    assert code == 0, err
    assert out == "ok"


def test_submodules_are_still_importable_directly():
    code, out, err = run_probe(
        "from anyplace.ui.layout import Layout;"
        "from anyplace.ui.theme import get_theme;"
        "from anyplace.ui.components import card;"
        "from anyplace.ui.prompts import ask_text;"
        "print('ok')"
    )
    assert code == 0, err
    assert out == "ok"
