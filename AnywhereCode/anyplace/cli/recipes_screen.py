"""
Recipe browser — the fastest path from "I want a thing" to a running project.

A recipe is a pre-answered interview: tap "Habit tracker" and you skip straight
to the plan. On a phone this is the difference between 30 seconds and 3 minutes
of thumb typing.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from anyplace.core.recipes import Recipe, list_recipes, recipe_tags, search_recipes
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import Choice, GoBack, ask_choice, ask_text

PAGE_SIZE_NARROW = 6
PAGE_SIZE_WIDE = 10


def _page_size(layout: Layout) -> int:
    return PAGE_SIZE_NARROW if layout.narrow else PAGE_SIZE_WIDE


def _recipe_choices(recipes: List[Recipe], layout: Layout) -> List[Choice]:
    return [
        Choice(
            value=recipe.id,
            label=recipe.title,
            description="" if layout.bp == "xs" else recipe.subtitle,
        )
        for recipe in recipes
    ]


def pick_recipe(
    console,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
) -> Optional[Recipe]:
    """
    Browse, filter and pick a recipe.

    Returns the chosen Recipe, or None if the user wants to describe something
    of their own instead. Raises GoBack to return to the previous screen.
    """
    layout = layout or Layout.detect()
    recipes = list_recipes()
    heading = "Pick something to build"
    page = 0

    while True:
        page_size = _page_size(layout)
        total_pages = max(1, (len(recipes) + page_size - 1) // page_size)
        page = min(page, total_pages - 1)
        window = recipes[page * page_size : (page + 1) * page_size]

        choices = _recipe_choices(window, layout)
        if total_pages > 1:
            choices.append(Choice(value="__more__", label="More ideas", description="Show the next page"))
        choices.append(Choice(value="__search__", label="Search", description="Find it by name"))
        choices.append(Choice(value="__filter__", label="Filter by kind", description="Web, backend, mobile…"))
        choices.append(Choice(value="__own__", label="Something else", description="Describe it in your own words"))

        title = heading
        if total_pages > 1:
            title = "{0}  ({1}/{2})".format(heading, page + 1, total_pages)

        picked = ask_choice(
            console,
            title,
            choices,
            layout=layout,
            input_fn=input_fn,
            help_text="These are starting points. You can change anything afterwards.",
        )

        if picked == "__more__":
            page = (page + 1) % total_pages
            continue

        if picked == "__own__":
            return None

        if picked == "__search__":
            query = ask_text(
                console,
                "What are you building?",
                layout=layout,
                input_fn=input_fn,
                allow_empty=True,
                placeholder="notes, shop, api…",
            )
            found = search_recipes(query) if query else list_recipes()
            if not found:
                ui.card(
                    console,
                    "Nothing matched \"{0}\". Showing everything again.".format(query),
                    title="No matches",
                    tone="warn",
                    layout=layout,
                )
                recipes = list_recipes()
            else:
                recipes = found
                heading = "Matches for \"{0}\"".format(query)
            page = 0
            continue

        if picked == "__filter__":
            tags = recipe_tags()
            tag_choices = [Choice(value=tag, label=tag.replace("-", " ").title()) for tag in tags]
            tag_choices.append(Choice(value="__all__", label="Show everything"))
            try:
                tag = ask_choice(console, "Which kind?", tag_choices, layout=layout, input_fn=input_fn)
            except GoBack:
                continue
            if tag == "__all__":
                recipes = list_recipes()
                heading = "Pick something to build"
            else:
                recipes = list_recipes(tag=tag)
                heading = tag.replace("-", " ").title()
            page = 0
            continue

        for recipe in recipes:
            if recipe.id == picked:
                return recipe


def show_recipe(console, recipe: Recipe, layout: Optional[Layout] = None) -> None:
    """Show what a recipe will actually give you."""
    layout = layout or Layout.detect()
    pairs = [
        ("Building", recipe.title),
        ("In short", recipe.subtitle),
        ("Scaffold", recipe.template),
        ("Roughly", "{0} min".format(recipe.est_minutes)),
    ]
    ui.kv(console, pairs, layout=layout, title=recipe.title)
