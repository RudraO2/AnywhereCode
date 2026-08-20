"""Tests for anyplace.cli.templates.

Two layers: the real templates that ship in the package (a consistency check
that catches a broken or half-added template), and the discovery/loading
functions driven against a synthetic templates directory in tmp_path.
"""

from __future__ import annotations

import json

import pytest

from anyplace.cli import templates as templates_mod
from anyplace.cli.error_handler import ConfigError
from anyplace.cli.templates import (
    DEFAULT_TEMPLATES,
    get_default_template_info,
    get_template_files,
    get_template_info,
    get_template_path,
    get_templates_dir,
    list_available_templates,
    validate_template,
)

REQUIRED_FIELDS = ("name", "type", "description")


@pytest.fixture
def fake_templates_dir(tmp_path, monkeypatch):
    """Point template discovery at a synthetic directory we fully control."""
    root = tmp_path / "templates"
    root.mkdir()
    monkeypatch.setattr(templates_mod, "get_templates_dir", lambda: root)
    return root


def make_template(root, name, payload=None, structure_text=None):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    if structure_text is not None:
        (d / "structure.json").write_text(structure_text)
    elif payload is not None:
        (d / "structure.json").write_text(json.dumps(payload))
    return d


def valid_payload(name):
    return {
        "name": name,
        "type": "web",
        "description": "A test template",
        "tech_stack": ["React"],
        "key_features": ["fast"],
        "estimated_time": "10 minutes",
        "files_to_generate": ["package.json", "src/App.tsx"],
    }


# ---------------------------------------------------------------------------
# The templates that actually ship
# ---------------------------------------------------------------------------


def test_get_templates_dir_lives_inside_the_package():
    templates_dir = get_templates_dir()
    assert templates_dir.name == "templates"
    assert templates_dir.parent.name == "anyplace"


def test_shipped_templates_are_discoverable():
    found = list_available_templates()
    assert found, "no templates ship with the package"
    assert "web-react-vite" in found


def test_list_available_templates_returns_sorted_names():
    found = list_available_templates()
    assert found == sorted(found)


@pytest.mark.parametrize("name", sorted(list_available_templates()))
def test_every_shipped_template_is_valid(name):
    info = get_template_info(name)
    for field in REQUIRED_FIELDS:
        assert info.get(field), "%s is missing %s" % (name, field)
    assert validate_template(name) is True


@pytest.mark.parametrize("name", sorted(list_available_templates()))
def test_every_shipped_template_declares_files_to_generate(name):
    files = get_template_files(name)
    assert isinstance(files, list)
    assert files, "%s generates no files" % name


@pytest.mark.parametrize("name", sorted(list_available_templates()))
def test_shipped_template_name_field_matches_its_directory(name):
    assert get_template_info(name)["name"] == name


# ---------------------------------------------------------------------------
# Discovery against a synthetic directory
# ---------------------------------------------------------------------------


def test_list_available_templates_is_empty_when_the_dir_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(templates_mod, "get_templates_dir", lambda: tmp_path / "gone")
    assert list_available_templates() == []


def test_list_available_templates_is_empty_for_an_empty_dir(fake_templates_dir):
    assert list_available_templates() == []


def test_list_available_templates_skips_dirs_without_structure_json(fake_templates_dir):
    make_template(fake_templates_dir, "good", valid_payload("good"))
    (fake_templates_dir / "not-a-template").mkdir()
    assert list_available_templates() == ["good"]


def test_list_available_templates_skips_loose_files(fake_templates_dir):
    make_template(fake_templates_dir, "good", valid_payload("good"))
    (fake_templates_dir / "README.md").write_text("hi")
    assert list_available_templates() == ["good"]


def test_list_available_templates_sorts_synthetic_templates(fake_templates_dir):
    for name in ("zebra", "alpha", "middle"):
        make_template(fake_templates_dir, name, valid_payload(name))
    assert list_available_templates() == ["alpha", "middle", "zebra"]


# ---------------------------------------------------------------------------
# get_template_info
# ---------------------------------------------------------------------------


def test_get_template_info_returns_the_parsed_structure(fake_templates_dir):
    make_template(fake_templates_dir, "demo", valid_payload("demo"))
    info = get_template_info("demo")
    assert info["name"] == "demo"
    assert info["tech_stack"] == ["React"]


def test_get_template_info_raises_for_a_missing_template(fake_templates_dir):
    with pytest.raises(ConfigError) as excinfo:
        get_template_info("nope")
    assert "nope" in str(excinfo.value)


def test_get_template_info_raises_for_a_dir_without_structure_json(fake_templates_dir):
    (fake_templates_dir / "hollow").mkdir()
    with pytest.raises(ConfigError):
        get_template_info("hollow")


def test_get_template_info_raises_for_corrupt_json(fake_templates_dir):
    make_template(fake_templates_dir, "broken", structure_text="{ not json at all")
    with pytest.raises(ConfigError) as excinfo:
        get_template_info("broken")
    assert "invalid" in str(excinfo.value).lower()


def test_get_template_info_raises_for_an_empty_structure_file(fake_templates_dir):
    make_template(fake_templates_dir, "empty", structure_text="")
    with pytest.raises(ConfigError):
        get_template_info("empty")


# ---------------------------------------------------------------------------
# get_template_files / get_template_path
# ---------------------------------------------------------------------------


def test_get_template_files_returns_the_declared_list(fake_templates_dir):
    make_template(fake_templates_dir, "demo", valid_payload("demo"))
    assert get_template_files("demo") == ["package.json", "src/App.tsx"]


def test_get_template_files_defaults_to_empty_when_undeclared(fake_templates_dir):
    payload = {k: v for k, v in valid_payload("demo").items() if k != "files_to_generate"}
    make_template(fake_templates_dir, "demo", payload)
    assert get_template_files("demo") == []


def test_get_template_files_raises_for_a_missing_template(fake_templates_dir):
    with pytest.raises(ConfigError):
        get_template_files("nope")


def test_get_template_path_points_inside_the_templates_dir(fake_templates_dir):
    assert get_template_path("demo") == fake_templates_dir / "demo"


def test_get_template_path_does_not_require_the_template_to_exist(fake_templates_dir):
    assert get_template_path("ghost").name == "ghost"


# ---------------------------------------------------------------------------
# validate_template
# ---------------------------------------------------------------------------


def test_validate_template_true_for_a_complete_structure(fake_templates_dir):
    make_template(fake_templates_dir, "demo", valid_payload("demo"))
    assert validate_template("demo") is True


@pytest.mark.parametrize("missing", REQUIRED_FIELDS)
def test_validate_template_false_when_a_required_field_is_missing(
    fake_templates_dir, missing
):
    payload = {k: v for k, v in valid_payload("demo").items() if k != missing}
    make_template(fake_templates_dir, "demo", payload)
    assert validate_template("demo") is False


def test_validate_template_false_for_a_missing_template(fake_templates_dir):
    assert validate_template("nope") is False


def test_validate_template_false_for_corrupt_json(fake_templates_dir):
    make_template(fake_templates_dir, "broken", structure_text="{{{")
    assert validate_template("broken") is False


# ---------------------------------------------------------------------------
# DEFAULT_TEMPLATES fallback table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DEFAULT_TEMPLATES))
def test_default_template_entry_has_the_required_fields(name):
    entry = DEFAULT_TEMPLATES[name]
    for field in REQUIRED_FIELDS:
        assert entry.get(field), "%s is missing %s" % (name, field)
    assert entry["name"] == name


def test_get_default_template_info_returns_a_known_entry():
    info = get_default_template_info("web-react-vite")
    assert info is not None
    assert info["type"] == "web"


def test_get_default_template_info_returns_none_for_an_unknown_name():
    assert get_default_template_info("not-a-template") is None


def test_default_template_types_are_from_the_known_set():
    known = {"web", "mobile", "backend", "fullstack", "cli"}
    for name, entry in DEFAULT_TEMPLATES.items():
        assert entry["type"] in known, "%s has type %r" % (name, entry["type"])


def test_every_shipped_template_has_a_default_table_entry():
    # The fallback table exists for when the template files are unreadable, so
    # anything that ships must be represented there.
    missing = sorted(set(list_available_templates()) - set(DEFAULT_TEMPLATES))
    assert missing == [], "shipped templates absent from DEFAULT_TEMPLATES: %s" % missing


def test_every_default_table_entry_has_a_shipped_template():
    # The fallback table must not advertise a template that cannot be loaded:
    # picking one would raise ConfigError at plan time, after the user has
    # already answered every question.
    missing = sorted(set(DEFAULT_TEMPLATES) - set(list_available_templates()))
    assert missing == [], "DEFAULT_TEMPLATES entries with no template dir: %s" % missing
