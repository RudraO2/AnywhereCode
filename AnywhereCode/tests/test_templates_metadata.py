"""Tests for the enriched template structure.json metadata.

The original keys are load-bearing for plan_generator / cli.templates, so they
are asserted alongside the new recommender/UI metadata.
"""

import json
from pathlib import Path

import pytest

import anyplace

TEMPLATES_DIR = Path(anyplace.__file__).resolve().parent / "templates"

#: Keys that existed before enrichment and must never disappear.
ORIGINAL_KEYS = (
    "name",
    "type",
    "description",
    "tech_stack",
    "files_to_generate",
    "key_features",
    "estimated_time",
)

#: Keys added for the recommender and the phone UI.
NEW_KEYS = (
    "keywords",
    "display_name",
    "tagline",
    "good_for",
    "not_for",
    "mobile_friendly",
    "runs_on_phone",
    "difficulty",
)

DIFFICULTIES = ("beginner", "intermediate", "advanced")

EXPECTED_TEMPLATES = (
    "android-native-kotlin",
    "backend-nodejs",
    "backend-python-fastapi",
    "fullstack-nextjs",
    "mobile-expo-rn",
    "web-react-vite",
)

MAX_DISPLAY_NAME = 18
MAX_TAGLINE = 48


def template_paths():
    return sorted(
        p / "structure.json"
        for p in TEMPLATES_DIR.iterdir()
        if p.is_dir() and (p / "structure.json").exists()
    )


def load(path):
    return json.loads(path.read_text())


PATHS = template_paths()
IDS = [p.parent.name for p in PATHS]


def test_all_expected_templates_are_present():
    assert tuple(IDS) == EXPECTED_TEMPLATES


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_structure_json_is_valid_json(path):
    data = load(path)
    assert isinstance(data, dict)


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_structure_json_is_two_space_indented(path):
    lines = path.read_text().splitlines()
    indented = [ln for ln in lines if ln.startswith(" ")]
    assert indented
    for line in indented:
        leading = len(line) - len(line.lstrip(" "))
        assert leading % 2 == 0, "odd indent in {0}: {1!r}".format(path, line)


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_original_keys_are_preserved(path):
    data = load(path)
    for key in ORIGINAL_KEYS:
        assert key in data, "{0} lost key {1}".format(path.parent.name, key)


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_original_key_types_are_unchanged(path):
    data = load(path)
    assert isinstance(data["name"], str) and data["name"]
    assert isinstance(data["type"], str) and data["type"]
    assert isinstance(data["description"], str) and data["description"]
    assert isinstance(data["tech_stack"], list) and data["tech_stack"]
    assert isinstance(data["files_to_generate"], list) and data["files_to_generate"]
    assert isinstance(data["key_features"], list) and data["key_features"]
    assert isinstance(data["estimated_time"], str) and data["estimated_time"]


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_name_matches_directory(path):
    assert load(path)["name"] == path.parent.name


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_new_metadata_keys_are_present(path):
    data = load(path)
    for key in NEW_KEYS:
        assert key in data, "{0} is missing {1}".format(path.parent.name, key)


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_keywords_are_lowercase_strings_within_range(path):
    keywords = load(path)["keywords"]
    assert isinstance(keywords, list)
    assert 8 <= len(keywords) <= 15
    assert len(set(keywords)) == len(keywords)
    for word in keywords:
        assert isinstance(word, str)
        assert word.strip()
        assert word == word.lower()


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_display_name_fits_a_narrow_screen(path):
    display = load(path)["display_name"]
    assert isinstance(display, str)
    assert display.strip()
    assert len(display) <= MAX_DISPLAY_NAME


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_tagline_is_one_short_line(path):
    tagline = load(path)["tagline"]
    assert isinstance(tagline, str)
    assert tagline.strip()
    assert len(tagline) <= MAX_TAGLINE
    assert "\n" not in tagline


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_good_for_is_three_to_five_short_phrases(path):
    good_for = load(path)["good_for"]
    assert isinstance(good_for, list)
    assert 3 <= len(good_for) <= 5
    for phrase in good_for:
        assert isinstance(phrase, str)
        assert phrase.strip()
        assert len(phrase) <= 40


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_not_for_is_one_to_three_honest_phrases(path):
    not_for = load(path)["not_for"]
    assert isinstance(not_for, list)
    assert 1 <= len(not_for) <= 3
    for phrase in not_for:
        assert isinstance(phrase, str)
        assert phrase.strip()
        assert len(phrase) <= 40


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_mobile_friendly_is_a_bool(path):
    assert isinstance(load(path)["mobile_friendly"], bool)


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_runs_on_phone_is_a_short_explanation(path):
    text = load(path)["runs_on_phone"]
    assert isinstance(text, str)
    assert text.strip()
    assert len(text) <= 60


@pytest.mark.parametrize("path", PATHS, ids=IDS)
def test_difficulty_is_in_the_allowed_set(path):
    assert load(path)["difficulty"] in DIFFICULTIES


def test_heavy_templates_are_marked_not_mobile_friendly():
    """Honesty check: Next.js, React Native and Gradle cannot really be built on a phone."""
    heavy = {"fullstack-nextjs", "mobile-expo-rn", "android-native-kotlin"}
    for path in PATHS:
        data = load(path)
        if path.parent.name in heavy:
            assert data["mobile_friendly"] is False


def test_light_templates_are_marked_mobile_friendly():
    light = {"web-react-vite", "backend-python-fastapi", "backend-nodejs"}
    for path in PATHS:
        data = load(path)
        if path.parent.name in light:
            assert data["mobile_friendly"] is True


def test_display_names_are_unique():
    names = [load(p)["display_name"] for p in PATHS]
    assert len(set(names)) == len(names)


def test_keyword_sets_are_distinctive_per_template():
    """Every template needs at least a few keywords no other template claims."""
    keyword_sets = dict((p.parent.name, set(load(p)["keywords"])) for p in PATHS)
    for name, words in keyword_sets.items():
        others = set()
        for other_name, other_words in keyword_sets.items():
            if other_name != name:
                others |= other_words
        assert len(words - others) >= 3, "{0} has too few distinctive keywords".format(name)


def test_metadata_is_deterministic_on_reload():
    first = [json.dumps(load(p), sort_keys=True) for p in PATHS]
    second = [json.dumps(load(p), sort_keys=True) for p in PATHS]
    assert first == second


def test_every_recipe_template_has_enriched_metadata():
    from anyplace.core.recipes import RECIPES

    available = dict((p.parent.name, load(p)) for p in PATHS)
    for recipe in RECIPES:
        assert recipe.template in available
        assert available[recipe.template]["difficulty"] in DIFFICULTIES
