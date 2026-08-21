"""Tests for anyplace.core.recipes."""

import json
import re
from pathlib import Path

import pytest

from anyplace.core import recipes
from anyplace.core.recipes import (
    PREFILL_KEYS,
    RECIPES,
    TAG_VOCABULARY,
    Recipe,
    get_recipe,
    list_recipes,
    recipe_tags,
    search_recipes,
)

TEMPLATES_DIR = Path(recipes.__file__).resolve().parent.parent / "templates"

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

#: Phone screens are tiny - these are hard layout budgets.
MAX_TITLE = 24
MAX_SUBTITLE = 34


def real_template_names():
    return sorted(
        p.name for p in TEMPLATES_DIR.iterdir()
        if p.is_dir() and (p / "structure.json").exists()
    )


# --------------------------------------------------------------------------
# catalogue shape
# --------------------------------------------------------------------------


def test_recipe_catalogue_has_a_useful_number_of_entries():
    assert 12 <= len(RECIPES) <= 18


def test_recipe_ids_are_unique():
    ids = [r.id for r in RECIPES]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_id_is_lowercase_hyphenated(recipe):
    assert ID_RE.match(recipe.id), "bad id: {0}".format(recipe.id)


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_title_is_short_and_non_empty(recipe):
    assert recipe.title.strip()
    assert len(recipe.title) <= MAX_TITLE


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_subtitle_fits_a_phone_screen(recipe):
    assert recipe.subtitle.strip()
    assert len(recipe.subtitle) <= MAX_SUBTITLE


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_template_is_a_real_template_directory(recipe):
    assert recipe.template in real_template_names()


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_prefill_uses_only_canonical_question_ids(recipe):
    assert recipe.prefill, "recipe {0} pre-fills nothing".format(recipe.id)
    for key in recipe.prefill:
        assert key in PREFILL_KEYS, "unknown question id {0}".format(key)


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_prefill_core_values_have_sane_types(recipe):
    prefill = recipe.prefill
    assert isinstance(prefill.get("project_name", ""), str)
    assert isinstance(prefill.get("idea", ""), str)
    assert isinstance(prefill.get("features", []), list)
    assert isinstance(prefill.get("needs_backend", False), bool)
    assert isinstance(prefill.get("needs_auth", False), bool)
    assert prefill.get("complexity", "simple") in ("simple", "standard", "ambitious")
    assert prefill.get("project_kind", "web") in (
        "web", "mobile", "backend", "fullstack", "cli", "unsure"
    )
    assert prefill.get("database", "none") in (
        "", "none", "sqlite", "postgres", "mongo", "unsure"
    )


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_prefill_names_the_project(recipe):
    assert recipe.prefill.get("project_name", "").strip()
    assert recipe.prefill.get("idea", "").strip()


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_tags_come_from_the_controlled_vocabulary(recipe):
    assert recipe.tags
    for tag in recipe.tags:
        assert tag in TAG_VOCABULARY, "unknown tag {0}".format(tag)


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_icon_is_a_single_character(recipe):
    assert len(recipe.icon) == 1


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_is_usable_without_its_icon(recipe):
    """Nothing may depend on the emoji rendering."""
    stripped = Recipe(
        id=recipe.id,
        title=recipe.title,
        subtitle=recipe.subtitle,
        template=recipe.template,
        icon="",
        tags=list(recipe.tags),
        prefill=dict(recipe.prefill),
    )
    assert stripped.title and stripped.subtitle and stripped.template
    assert search_recipes(stripped.title.lower())


@pytest.mark.parametrize("recipe", RECIPES, ids=[r.id for r in RECIPES])
def test_recipe_est_minutes_is_positive(recipe):
    assert isinstance(recipe.est_minutes, int)
    assert 1 <= recipe.est_minutes <= 120


def test_recipes_cover_every_template():
    used = set(r.template for r in RECIPES)
    assert used == set(real_template_names())


def test_recipe_to_dict_is_json_serialisable():
    payload = [r.to_dict() for r in RECIPES]
    restored = json.loads(json.dumps(payload))
    assert restored[0]["id"] == RECIPES[0].id


# --------------------------------------------------------------------------
# list_recipes
# --------------------------------------------------------------------------


def test_list_recipes_returns_everything_by_default():
    assert len(list_recipes()) == len(RECIPES)


def test_list_recipes_returns_a_copy_not_the_module_list():
    result = list_recipes()
    result.pop()
    assert len(RECIPES) == len(list_recipes())


@pytest.mark.parametrize("tag", TAG_VOCABULARY)
def test_list_recipes_filters_by_each_tag(tag):
    matched = list_recipes(tag)
    assert matched, "tag {0} matches nothing".format(tag)
    for recipe in matched:
        assert tag in recipe.tags


def test_list_recipes_tag_filter_is_case_insensitive():
    assert list_recipes("WEB") == list_recipes("web")


def test_list_recipes_unknown_tag_returns_empty():
    assert list_recipes("blockchain") == []


def test_list_recipes_empty_tag_returns_everything():
    assert len(list_recipes("")) == len(RECIPES)


# --------------------------------------------------------------------------
# get_recipe
# --------------------------------------------------------------------------


def test_get_recipe_finds_a_known_id():
    recipe = get_recipe("todo-app")
    assert recipe is not None
    assert recipe.id == "todo-app"


def test_get_recipe_is_case_and_space_insensitive():
    assert get_recipe("  TODO-APP  ") is get_recipe("todo-app")


def test_get_recipe_returns_none_for_unknown_id():
    assert get_recipe("does-not-exist") is None


@pytest.mark.parametrize("bad", ["", None])
def test_get_recipe_returns_none_for_empty_input(bad):
    assert get_recipe(bad) is None


# --------------------------------------------------------------------------
# recipe_tags
# --------------------------------------------------------------------------


def test_recipe_tags_are_sorted_and_unique():
    tags = recipe_tags()
    assert tags == sorted(set(tags))


def test_recipe_tags_cover_the_whole_vocabulary():
    assert set(recipe_tags()) == set(TAG_VOCABULARY)


# --------------------------------------------------------------------------
# search_recipes
# --------------------------------------------------------------------------


def test_search_recipes_empty_query_returns_everything():
    assert len(search_recipes("")) == len(RECIPES)


def test_search_recipes_whitespace_query_returns_everything():
    assert len(search_recipes("   ")) == len(RECIPES)


def test_search_recipes_none_query_returns_everything():
    assert len(search_recipes(None)) == len(RECIPES)


def test_search_recipes_no_match_returns_empty_list():
    assert search_recipes("quantum blockchain metaverse") == []


def test_search_recipes_is_case_insensitive():
    assert [r.id for r in search_recipes("TODO")] == [r.id for r in search_recipes("todo")]


def test_search_recipes_matches_title_first():
    results = search_recipes("todo")
    assert results
    assert results[0].id == "todo-app"


def test_search_recipes_title_hit_outranks_tag_hit():
    """'web' is a tag on several recipes but appears in one title."""
    results = search_recipes("web")
    assert results[0].id == "webhook-receiver"
    assert len(results) > 1, "expected the tag matches to come along too"
    assert any("web" in r.tags for r in results[1:])


def test_search_recipes_ranks_title_match_above_tag_match():
    results = search_recipes("blog")
    assert results[0].id == "blog"
    assert all(r.id != "blog" for r in results[1:])


def test_search_recipes_matches_tags():
    results = search_recipes("mobile")
    ids = [r.id for r in results]
    assert "habit-tracker" in ids
    assert "photo-journal" in ids


def test_search_recipes_matches_subtitle_text():
    results = search_recipes("emails")
    assert [r.id for r in results] == ["landing-page"]


def test_search_recipes_multi_word_query_prefers_best_overall_match():
    results = search_recipes("todo app")
    assert results[0].id == "todo-app"


def test_search_recipes_ordering_is_deterministic():
    assert [r.id for r in search_recipes("api")] == [r.id for r in search_recipes("api")]


def test_search_recipes_result_scores_are_descending():
    query = "api"
    results = search_recipes(query)
    scores = [recipes._score(r, query) for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_recipes_matches_recipe_id_fragment():
    results = search_recipes("shortener")
    assert [r.id for r in results] == ["url-shortener"]


def test_recipes_module_imports_no_ui_or_cli_dependencies():
    source = open(recipes.__file__, "r").read()
    assert "import rich" not in source
    assert "import click" not in source
    assert "from anyplace.cli" not in source
    assert "from anyplace.ui" not in source
