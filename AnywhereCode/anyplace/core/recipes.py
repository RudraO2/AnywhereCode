"""
One-tap starting points ("recipes") for Anywhere Code.

A recipe is a project idea in the user's own words - "Todo app that saves my
stuff" rather than "fullstack-nextjs".  Picking one pre-fills the interview so
a phone user can tap through instead of typing paragraphs.

Pure logic: no ``rich``, no ``click``, no imports from ``anyplace.cli`` or
``anyplace.ui``.  Icons are decoration only - nothing here depends on an emoji
rendering, and every recipe is fully usable with the icon stripped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Interview question ids a recipe may pre-fill (canonical list, see spec).
PREFILL_KEYS = (
    "project_name",
    "idea",
    "project_kind",
    "audience",
    "features",
    "needs_backend",
    "needs_auth",
    "database",
    "styling",
    "complexity",
    "deploy_target",
    "notes",
)

#: The controlled tag vocabulary.  Recipes may only use these.
TAG_VOCABULARY = (
    "api",
    "backend",
    "beginner",
    "bot",
    "business",
    "commerce",
    "content",
    "data",
    "fullstack",
    "mobile",
    "personal",
    "quick",
    "web",
)

#: Search ranking weights - a title hit always beats a tag hit.
SCORE_TITLE = 4
SCORE_TAG = 2
SCORE_SUBTITLE = 1
SCORE_ID = 2


@dataclass
class Recipe:
    """A pre-filled project starting point."""

    id: str
    title: str
    subtitle: str
    template: str
    icon: str = ""
    tags: List[str] = field(default_factory=list)
    prefill: Dict[str, Any] = field(default_factory=dict)
    est_minutes: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "template": self.template,
            "icon": self.icon,
            "tags": list(self.tags),
            "prefill": dict(self.prefill),
            "est_minutes": self.est_minutes,
        }


RECIPES: List[Recipe] = [
    Recipe(
        id="portfolio-site",
        title="Portfolio site",
        subtitle="Show your work, get hired",
        template="web-react-vite",
        icon="\U0001F3A8",
        tags=["web", "personal", "beginner"],
        est_minutes=10,
        prefill={
            "project_name": "my-portfolio",
            "idea": "A personal portfolio site with my projects, a short bio and a way to contact me.",
            "project_kind": "web",
            "audience": "recruiters and potential clients",
            "features": ["project gallery", "about page", "contact links", "resume download"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "none",
            "styling": "tailwind",
            "complexity": "simple",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="landing-page",
        title="Landing page",
        subtitle="Pitch an idea, collect emails",
        template="web-react-vite",
        icon="\U0001F680",
        tags=["web", "business", "quick", "beginner"],
        est_minutes=8,
        prefill={
            "project_name": "launch-page",
            "idea": "A one-page site that explains a product idea and collects email signups.",
            "project_kind": "web",
            "audience": "early adopters who click an ad or a link",
            "features": ["hero section", "feature list", "email signup form", "FAQ"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "none",
            "styling": "tailwind",
            "complexity": "simple",
            "deploy_target": "netlify",
        },
    ),
    Recipe(
        id="link-in-bio",
        title="Link in bio",
        subtitle="One page, all your links",
        template="web-react-vite",
        icon="\U0001F517",
        tags=["web", "personal", "quick", "beginner"],
        est_minutes=6,
        prefill={
            "project_name": "my-links",
            "idea": "A tiny page with my photo and buttons linking to all my profiles.",
            "project_kind": "web",
            "audience": "people who find me on social media",
            "features": ["avatar header", "link buttons", "click counter", "dark mode"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "none",
            "styling": "tailwind",
            "complexity": "simple",
            "deploy_target": "github-pages",
        },
    ),
    Recipe(
        id="countdown-timer",
        title="Countdown timer",
        subtitle="Count down to the big day",
        template="web-react-vite",
        icon="\U000023F3",
        tags=["web", "quick", "beginner", "personal"],
        est_minutes=6,
        prefill={
            "project_name": "countdown",
            "idea": "A page that counts down to a date I pick and celebrates when it hits zero.",
            "project_kind": "web",
            "audience": "friends and family sharing the link",
            "features": ["set a target date", "live ticking clock", "share link", "celebration screen"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "none",
            "styling": "css",
            "complexity": "simple",
            "deploy_target": "github-pages",
        },
    ),
    Recipe(
        id="data-dashboard",
        title="Data dashboard",
        subtitle="Charts from your spreadsheet",
        template="web-react-vite",
        icon="\U0001F4CA",
        tags=["web", "data", "business"],
        est_minutes=15,
        prefill={
            "project_name": "sheet-dashboard",
            "idea": "A dashboard that reads a CSV export of my spreadsheet and draws charts from it.",
            "project_kind": "web",
            "audience": "my team, on a laptop and on a phone",
            "features": ["CSV upload", "summary tiles", "line and bar charts", "date filter"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "none",
            "styling": "tailwind",
            "complexity": "standard",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="todo-app",
        title="Todo app",
        subtitle="Tasks that save between visits",
        template="fullstack-nextjs",
        icon="\U00002705",
        tags=["fullstack", "personal", "beginner"],
        est_minutes=20,
        prefill={
            "project_name": "my-todos",
            "idea": "A todo list where my tasks are saved to my account and are there when I come back.",
            "project_kind": "fullstack",
            "audience": "me, plus anyone who signs up",
            "features": ["add and complete tasks", "due dates", "lists or projects", "sign in"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "standard",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="notes-app",
        title="Notes app",
        subtitle="Jot it down, find it fast",
        template="fullstack-nextjs",
        icon="\U0001F4DD",
        tags=["fullstack", "personal", "content"],
        est_minutes=20,
        prefill={
            "project_name": "quick-notes",
            "idea": "A notes app where I can write, tag and search notes from any device.",
            "project_kind": "fullstack",
            "audience": "me on my phone and my laptop",
            "features": ["markdown editor", "tags", "full text search", "sign in"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "standard",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="blog",
        title="Blog",
        subtitle="Write posts, publish fast",
        template="fullstack-nextjs",
        icon="\U0001F4F0",
        tags=["fullstack", "content", "personal"],
        est_minutes=20,
        prefill={
            "project_name": "my-blog",
            "idea": "A blog where I write posts in markdown and readers can browse by tag.",
            "project_kind": "fullstack",
            "audience": "readers who find posts through search",
            "features": ["markdown posts", "tag pages", "RSS feed", "admin editor"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "standard",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="expense-tracker",
        title="Expense tracker",
        subtitle="See where the money goes",
        template="fullstack-nextjs",
        icon="\U0001F4B0",
        tags=["fullstack", "data", "personal"],
        est_minutes=25,
        prefill={
            "project_name": "expenses",
            "idea": "An expense tracker where I log spending, tag it by category and see monthly totals.",
            "project_kind": "fullstack",
            "audience": "me and my household",
            "features": ["log an expense", "categories", "monthly totals", "charts", "CSV export"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "standard",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="online-store",
        title="Online store",
        subtitle="Sell a few things online",
        template="fullstack-nextjs",
        icon="\U0001F6D2",
        tags=["fullstack", "commerce", "business"],
        est_minutes=30,
        prefill={
            "project_name": "my-shop",
            "idea": "A small shop with a product list, a cart and checkout for a handful of items.",
            "project_kind": "fullstack",
            "audience": "customers buying from a phone",
            "features": ["product catalog", "cart", "checkout", "order emails", "admin page"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "ambitious",
            "deploy_target": "vercel",
        },
    ),
    Recipe(
        id="business-api",
        title="Business API",
        subtitle="REST API for your app",
        template="backend-python-fastapi",
        icon="\U0001F9FE",
        tags=["backend", "api", "business"],
        est_minutes=20,
        prefill={
            "project_name": "business-api",
            "idea": "A REST API for a small business: customers, bookings and simple reporting.",
            "project_kind": "backend",
            "audience": "our own web and mobile front ends",
            "features": ["CRUD endpoints", "API docs", "token auth", "pagination", "health check"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "",
            "complexity": "standard",
            "deploy_target": "railway",
        },
    ),
    Recipe(
        id="bot-backend",
        title="Chat bot backend",
        subtitle="Powers a Discord or TG bot",
        template="backend-python-fastapi",
        icon="\U0001F916",
        tags=["backend", "bot", "api"],
        est_minutes=20,
        prefill={
            "project_name": "bot-backend",
            "idea": "A backend that receives Discord and Telegram bot updates and replies to commands.",
            "project_kind": "backend",
            "audience": "members of my chat server",
            "features": ["webhook endpoint", "command router", "per-user settings", "rate limiting"],
            "needs_backend": True,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "standard",
            "deploy_target": "fly.io",
        },
    ),
    Recipe(
        id="webhook-receiver",
        title="Webhook receiver",
        subtitle="Catch and log incoming hooks",
        template="backend-nodejs",
        icon="\U0001F50C",
        tags=["backend", "api", "quick"],
        est_minutes=12,
        prefill={
            "project_name": "hook-catcher",
            "idea": "A service that receives webhooks from other apps, verifies them and stores the payloads.",
            "project_kind": "backend",
            "audience": "the services that call my endpoint",
            "features": ["POST endpoint", "signature check", "payload log", "retry-safe handling"],
            "needs_backend": True,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "simple",
            "deploy_target": "render",
        },
    ),
    Recipe(
        id="url-shortener",
        title="URL shortener",
        subtitle="Short links you control",
        template="backend-nodejs",
        icon="\U0001F3AF",
        tags=["backend", "api", "quick"],
        est_minutes=12,
        prefill={
            "project_name": "short-links",
            "idea": "A URL shortener that makes tidy links on my own domain and counts the clicks.",
            "project_kind": "backend",
            "audience": "anyone I send a link to",
            "features": ["create short link", "redirect", "click counts", "custom slugs"],
            "needs_backend": True,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "simple",
            "deploy_target": "render",
        },
    ),
    Recipe(
        id="habit-tracker",
        title="Habit tracker",
        subtitle="Tick off streaks every day",
        template="mobile-expo-rn",
        icon="\U0001F4C8",
        tags=["mobile", "personal", "data"],
        est_minutes=25,
        prefill={
            "project_name": "habits",
            "idea": "A phone app where I tick off daily habits and watch my streaks grow.",
            "project_kind": "mobile",
            "audience": "me, every morning",
            "features": ["daily checklist", "streak counter", "reminders", "history chart"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "standard",
            "deploy_target": "expo",
        },
    ),
    Recipe(
        id="android-widget",
        title="Android home widget",
        subtitle="A native tile on your home screen",
        template="android-native-kotlin",
        icon="\U0001F9E9",
        tags=["mobile", "personal"],
        est_minutes=30,
        prefill={
            "project_name": "home-widget",
            "idea": (
                "A native Android app with a home-screen widget that shows one "
                "number I care about and refreshes in the background."
            ),
            "project_kind": "mobile",
            "audience": "me, glancing at my home screen",
            "features": [
                "home-screen widget",
                "background refresh",
                "settings screen",
                "Material 3 theming",
            ],
            "needs_backend": False,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "standard",
            "deploy_target": "apk",
            "notes": "Written on the phone, built by Android Studio or CI.",
        },
    ),
    Recipe(
        id="photo-journal",
        title="Photo journal",
        subtitle="A daily log with pictures",
        template="mobile-expo-rn",
        icon="\U0001F4F1",
        tags=["mobile", "personal", "content"],
        est_minutes=25,
        prefill={
            "project_name": "photo-journal",
            "idea": "A phone app for a one-photo-a-day journal with a short note attached.",
            "project_kind": "mobile",
            "audience": "just me, private by default",
            "features": ["camera capture", "note per entry", "calendar view", "offline storage"],
            "needs_backend": False,
            "needs_auth": False,
            "database": "sqlite",
            "styling": "",
            "complexity": "standard",
            "deploy_target": "expo",
        },
    ),
]


def list_recipes(tag: Optional[str] = None) -> List[Recipe]:
    """All recipes, optionally filtered by tag (case-insensitive)."""
    if tag is None:
        return list(RECIPES)
    wanted = str(tag).strip().lower()
    if not wanted:
        return list(RECIPES)
    return [r for r in RECIPES if wanted in [t.lower() for t in r.tags]]


def get_recipe(recipe_id: str) -> Optional[Recipe]:
    """Look up a recipe by id.  Returns None when unknown."""
    if not recipe_id:
        return None
    wanted = str(recipe_id).strip().lower()
    for recipe in RECIPES:
        if recipe.id == wanted:
            return recipe
    return None


def recipe_tags() -> List[str]:
    """Sorted list of tags actually used by at least one recipe."""
    seen = set()
    for recipe in RECIPES:
        for tag in recipe.tags:
            seen.add(tag.lower())
    return sorted(seen)


def _score(recipe: Recipe, token: str) -> int:
    """Best score for a single query token against one recipe."""
    if token in recipe.title.lower():
        return SCORE_TITLE
    if any(token in tag.lower() for tag in recipe.tags):
        return SCORE_TAG
    if token in recipe.id.lower():
        return SCORE_ID
    if token in recipe.subtitle.lower():
        return SCORE_SUBTITLE
    return 0


def search_recipes(query: str) -> List[Recipe]:
    """Case-insensitive search over title, subtitle and tags.

    Title hits outrank tag hits, which outrank subtitle hits.  An empty query
    returns every recipe; a query nothing matches returns ``[]``.
    """
    text = (query or "").strip().lower()
    if not text:
        return list(RECIPES)

    tokens = [t for t in text.split() if t]
    if not tokens:
        return list(RECIPES)

    scored: List[Tuple[int, int, Recipe]] = []
    for index, recipe in enumerate(RECIPES):
        total = 0
        for token in tokens:
            total += _score(recipe, token)
        # A whole-phrase hit is a stronger signal than the sum of its parts.
        if len(tokens) > 1:
            total += _score(recipe, text)
        if total > 0:
            scored.append((total, index, recipe))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]
