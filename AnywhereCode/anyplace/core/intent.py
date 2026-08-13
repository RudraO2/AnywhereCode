"""
Turn one sentence into a build request.

The old flow asked the user to pick a template from a numbered menu, invent a
project name, then type a description. That is three decisions before anything
happens, and a beginner cannot make the first one — they do not yet know what
"Vite" or "Expo" means.

This module removes all three. Given "a habit tracker with streaks" it decides
the template, the project name and the slug on its own.

Template choice falls back to keyword matching when the LLM is unavailable or
returns something unusable, so `anyplace create` still works when the model is
rate-limited — a dumb-but-correct answer beats a crash.
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from anyplace.cli.templates import list_available_templates, get_template_info


# Ordered most-specific first: the first rule whose keywords appear wins.
# Native mobile is checked before web so "an offline android note app" does not
# get caught by the generic web rule.
_KEYWORD_RULES = [
    (
        "mobile-expo-rn",
        (
            "android app", "ios app", "mobile app", "native app", "phone app",
            "react native", "expo", "apk", "play store", "app store",
            "push notification", "camera app", "offline app",
        ),
    ),
    (
        "backend-python-fastapi",
        (
            "fastapi", "python api", "python backend", "ml api", "machine learning",
            "data api", "scraper", "flask",
        ),
    ),
    (
        "backend-nodejs",
        (
            "rest api", "graphql", "backend", "server", "microservice",
            "express", "webhook", "api endpoint",
        ),
    ),
    (
        "fullstack-nextjs",
        (
            "full stack", "fullstack", "next.js", "nextjs", "ssr",
            "with a database", "with auth", "login", "dashboard with backend",
            "saas", "blog with cms", "e-commerce", "ecommerce",
        ),
    ),
    (
        "web-react-vite",
        (
            "website", "web app", "webapp", "landing page", "portfolio",
            "tracker", "todo", "to-do", "calculator", "game", "quiz",
            "timer", "dashboard", "notes", "chat ui", "react",
        ),
    ),
]

_DEFAULT_TEMPLATE = "web-react-vite"

# Words that add nothing to a project name.
_STOPWORDS = {
    "a", "an", "the", "app", "application", "that", "which", "with", "for",
    "and", "or", "to", "of", "in", "on", "my", "me", "i", "want", "need",
    "make", "build", "create", "simple", "basic", "small", "little", "please",
    "some", "it", "is", "can", "should", "would", "like",
}


@dataclass
class BuildIntent:
    """What the user actually asked for, resolved into build parameters."""

    prompt: str
    template: str
    project_name: str
    slug: str
    reasoning: str = ""
    inferred_by: str = "keywords"  # "llm" | "keywords" | "explicit"

    def to_dict(self) -> Dict:
        return {
            "prompt": self.prompt,
            "template": self.template,
            "project_name": self.project_name,
            "slug": self.slug,
            "reasoning": self.reasoning,
            "inferred_by": self.inferred_by,
        }


def slugify(text: str, fallback: str = "my-app") -> str:
    """Convert free text into a filesystem- and URL-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:40].strip("-") or fallback


def name_from_prompt(prompt: str, max_words: int = 3) -> str:
    """
    Derive a short project name from a free-text prompt.

        "a habit tracker with streaks"  -> "habit-tracker"
        "build me a tip calculator"     -> "tip-calculator"
    """
    words = re.findall(r"[a-zA-Z0-9]+", prompt.lower())
    meaningful = [w for w in words if w not in _STOPWORDS]
    chosen = meaningful[:max_words] or words[:max_words]
    return slugify("-".join(chosen)) if chosen else "my-app"


def template_from_keywords(prompt: str) -> str:
    """
    Pick a template by keyword match. Never fails.

    Used as the fallback whenever the LLM path is unavailable or returns a
    template that does not exist.
    """
    lowered = prompt.lower()
    available = set(list_available_templates())

    for template, keywords in _KEYWORD_RULES:
        if template not in available:
            continue
        if any(keyword in lowered for keyword in keywords):
            return template

    if _DEFAULT_TEMPLATE in available:
        return _DEFAULT_TEMPLATE
    return sorted(available)[0] if available else _DEFAULT_TEMPLATE


def _template_catalogue() -> List[Dict]:
    """Describe the installed templates for the model to choose between."""
    catalogue = []
    for name in list_available_templates():
        try:
            info = get_template_info(name)
        except Exception:
            continue
        catalogue.append({
            "template": name,
            "description": info.get("description", ""),
            "tech_stack": info.get("tech_stack", []),
        })
    return catalogue


def infer_intent(
    prompt: str,
    llm_provider=None,
    template_override: Optional[str] = None,
    name_override: Optional[str] = None,
) -> BuildIntent:
    """
    Resolve a free-text prompt into a template + project name.

    Args:
        prompt: What the user typed, e.g. "a habit tracker with streaks".
        llm_provider: Optional LLMProvider. Keyword matching is used without it.
        template_override: Skip inference and use this template.
        name_override: Skip inference and use this project name.

    Returns:
        A BuildIntent. This function does not raise — an unusable LLM response
        degrades to keyword matching rather than blocking the build.
    """
    prompt = (prompt or "").strip()
    available = list_available_templates()

    # Explicit wins over everything.
    if template_override and template_override in available:
        name = name_override or name_from_prompt(prompt)
        return BuildIntent(
            prompt=prompt,
            template=template_override,
            project_name=name,
            slug=slugify(name),
            reasoning="Template specified explicitly.",
            inferred_by="explicit",
        )

    fallback_template = template_from_keywords(prompt)
    fallback_name = name_override or name_from_prompt(prompt)

    if llm_provider is None:
        return BuildIntent(
            prompt=prompt,
            template=fallback_template,
            project_name=fallback_name,
            slug=slugify(fallback_name),
            reasoning="Matched on keywords (no model available).",
            inferred_by="keywords",
        )

    system = (
        "You route app ideas to project templates. Reply with JSON only: "
        '{"template": "<one of the given template names>", '
        '"project_name": "<short-kebab-case-name>", '
        '"reasoning": "<one short sentence>"}'
    )
    user_prompt = (
        f"App idea: {prompt}\n\n"
        f"Available templates:\n{json.dumps(_template_catalogue(), indent=2)}\n\n"
        "Pick the single best template. Prefer a web template unless the idea "
        "clearly needs native device features (camera, push notifications, "
        "app store distribution). Keep project_name to 2-3 words, kebab-case."
    )

    try:
        response = llm_provider.generate_json(
            prompt=user_prompt,
            system=system,
            temperature=0.1,
            max_tokens=300,
        )
    except Exception:
        # Rate limits, malformed JSON, network — all non-fatal here.
        return BuildIntent(
            prompt=prompt,
            template=fallback_template,
            project_name=fallback_name,
            slug=slugify(fallback_name),
            reasoning="Matched on keywords (model call failed).",
            inferred_by="keywords",
        )

    template = response.get("template", "")
    if template not in available:
        template = fallback_template

    raw_name = name_override or response.get("project_name") or fallback_name
    name = slugify(str(raw_name), fallback=fallback_name)

    return BuildIntent(
        prompt=prompt,
        template=template,
        project_name=name,
        slug=slugify(name),
        reasoning=str(response.get("reasoning", ""))[:200],
        inferred_by="llm",
    )
