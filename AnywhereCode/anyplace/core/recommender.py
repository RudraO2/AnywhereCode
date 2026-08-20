"""
Template recommender -- deterministic, explainable, offline.

Given a ProjectBrief and the template `structure.json` dicts, score every
template, sort them stably, and say *in plain words* why the winner won and
what it will cost.

Pure logic: no rich, no click, no CLI/UI imports, no network, no LLM.
Never raises on missing keys, empty briefs, or junk entries. Python 3.8 safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .brief import FEATURE_LABELS, ProjectBrief

__all__ = ["Recommendation", "recommend", "best_match", "explain"]

# ---------------------------------------------------------------------------
# Weights (relative importance of each signal). Sum is the normaliser.
# ---------------------------------------------------------------------------

W_KIND = 4.0
W_BACKEND = 2.0
W_FEATURES = 1.6
W_DATABASE = 1.2
W_COMPLEXITY = 1.0
W_KEYWORDS = 1.4
_TOTAL_WEIGHT = W_KIND + W_BACKEND + W_FEATURES + W_DATABASE + W_COMPLEXITY + W_KEYWORDS

# project_kind -> {template type: affinity 0..1}
KIND_AFFINITY = {
    "web": {"web": 1.0, "fullstack": 0.62, "mobile": 0.18, "backend": 0.08, "cli": 0.02},
    "mobile": {"mobile": 1.0, "web": 0.34, "fullstack": 0.24, "backend": 0.08, "cli": 0.02},
    "backend": {"backend": 1.0, "fullstack": 0.5, "cli": 0.2, "web": 0.05, "mobile": 0.02},
    "fullstack": {"fullstack": 1.0, "backend": 0.52, "web": 0.46, "mobile": 0.1, "cli": 0.02},
    "cli": {"cli": 1.0, "backend": 0.5, "fullstack": 0.15, "web": 0.08, "mobile": 0.02},
    "unsure": {"fullstack": 0.55, "web": 0.5, "backend": 0.36, "mobile": 0.3, "cli": 0.2},
    "": {"fullstack": 0.5, "web": 0.48, "backend": 0.34, "mobile": 0.28, "cli": 0.2},
}

SERVER_TYPES = ("backend", "fullstack")
CLIENT_TYPES = ("web", "mobile")

# Words that mark a template as covering a feature.
FEATURE_KEYWORDS = {
    "auth": ("auth", "login", "nextauth", "jwt", "session", "user", "account", "oauth"),
    "storage": ("database", "prisma", "sqlalchemy", "postgres", "sqlite", "mongo", "orm", "persist"),
    "payments": ("stripe", "payment", "checkout", "billing"),
    "uploads": ("upload", "multipart", "file", "s3", "storage"),
    "admin": ("admin", "dashboard", "role", "rbac"),
    "search": ("search", "index", "query"),
    "realtime": ("websocket", "socket", "realtime", "sse", "stream"),
    "notifications": ("notification", "push", "email", "expo"),
    "offline": ("offline", "pwa", "service worker", "local", "native", "asyncstorage"),
    "darkmode": ("dark", "theme", "tailwind", "css", "ui"),
}

DATABASE_KEYWORDS = {
    "postgres": ("postgres", "postgresql", "prisma", "sqlalchemy", "alembic"),
    "sqlite": ("sqlite", "sqlalchemy", "prisma", "file"),
    "mongo": ("mongo", "mongodb", "mongoose"),
}

# Short, honest blurbs keyed by a token in the template name or tech stack.
STACK_BLURBS = (
    ("expo", "Expo lets you run it on iOS and Android from one codebase."),
    ("react native", "React Native means one codebase for both phone platforms."),
    ("next", "Next.js puts the pages and the API routes in a single project."),
    ("vite", "Vite starts instantly and keeps rebuilds fast on slow hardware."),
    ("fastapi", "FastAPI gives you typed endpoints and API docs for free."),
    ("express", "Express is the smallest step from nothing to a working API."),
    ("django", "Django brings the admin, auth and ORM in the box."),
    ("flask", "Flask stays out of the way when the API is small."),
    ("react", "React is the safest bet for finding help and examples."),
)

STACK_CAVEATS = (
    ("next", "Next.js needs a Node host -- heavier to run from Termux."),
    ("expo", "Testing on a real phone needs the Expo Go app and a network link."),
    ("postgres", "Expects a PostgreSQL server you have to run or pay for."),
    ("mongo", "Expects a MongoDB server you have to run or pay for."),
    ("prisma", "Prisma downloads a native engine binary on install."),
    ("docker", "Docker is not available inside plain Termux."),
)

_WORD_RE = re.compile(r"[a-z0-9+#]+")
_STOPWORDS = frozenset(
    """
    a an and are as at be build building but by can create do does for from get
    has have how i i'd i'm in into is it its just let like make me my need needs
    of on or should simple small so some that the their them then there they
    thing this to up use user users want wants was we what when where which who
    will with would you your app application project site thing stuff something
    """.split()
)


# ---------------------------------------------------------------------------
# Safe accessors -- templates come from disk and may be anything
# ---------------------------------------------------------------------------

def _get(template: Any, key: str, default: Any = "") -> Any:
    if not isinstance(template, dict):
        return default
    value = template.get(key, default)
    return default if value is None else value


def _text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text_of(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_text_of(v) for v in value.values())
    if value is None:
        return ""
    return str(value)


def _template_name(template: Any) -> str:
    name = _text_of(_get(template, "name", "")).strip()
    return name


def _template_type(template: Any) -> str:
    value = _text_of(_get(template, "type", "")).strip().lower()
    return value


def _haystack(template: Any) -> str:
    parts = [
        _template_name(template),
        _template_type(template),
        _text_of(_get(template, "description", "")),
        _text_of(_get(template, "tech_stack", [])),
        _text_of(_get(template, "keywords", [])),
        _text_of(_get(template, "key_features", [])),
    ]
    return " ".join(parts).lower()


def _size_of(template: Any) -> int:
    files = _get(template, "files_to_generate", [])
    if isinstance(files, (list, tuple, set)):
        return len(files)
    return 0


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if len(w) > 2 and w not in _STOPWORDS]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    template: str
    score: float
    reasons: List[str]
    caveats: List[str] = field(default_factory=list)
    #: filled in by recommend(); how far ahead of the runner-up this pick is
    margin: float = 0.0

    @property
    def confidence(self) -> str:
        """Derived from the score *and* how far clear of the runner-up it is."""
        if self.score >= 0.60 and self.margin >= 0.10:
            return "high"
        if self.score >= 0.50 and self.margin >= 0.05:
            return "medium"
        if self.score >= 0.65:
            return "medium"
        return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "score": round(self.score, 4),
            "reasons": list(self.reasons),
            "caveats": list(self.caveats),
            "margin": round(self.margin, 4),
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Scoring components -- each returns 0..1
# ---------------------------------------------------------------------------

def _score_kind(brief: ProjectBrief, ttype: str) -> Tuple[float, List[str]]:
    kind = brief.project_kind if isinstance(brief.project_kind, str) else ""
    table = KIND_AFFINITY.get(kind, KIND_AFFINITY[""])
    score = table.get(ttype, 0.05)
    reasons = []  # type: List[str]
    if score >= 0.9:
        reasons.append(_kind_reason(kind))
    elif score >= 0.45 and kind:
        reasons.append("Close enough to " + _kind_phrase(kind) + " to be worth it.")
    return score, reasons


def _kind_reason(kind: str) -> str:
    return {
        "web": "You said you're building a website people visit.",
        "mobile": "You said you're building a phone app.",
        "backend": "You said you're building a backend other things talk to.",
        "fullstack": "You said you want a website with its own backend.",
        "cli": "You said you're building a terminal tool.",
    }.get(kind, "It fits the kind of thing you described.")


def _kind_phrase(kind: str) -> str:
    return {
        "web": "the website you described",
        "mobile": "the phone app you described",
        "backend": "the backend you described",
        "fullstack": "the web + backend build you described",
        "cli": "the terminal tool you described",
        "unsure": "what you described",
    }.get(kind, "what you described")


def _knows_shape(brief: ProjectBrief) -> bool:
    """Did the user say anything at all about server/data needs?"""
    return bool(
        brief.project_kind
        or brief.features
        or brief.needs_backend
        or brief.needs_auth
        or brief.database
    )


def _score_backend(brief: ProjectBrief, ttype: str) -> Tuple[float, List[str], List[str]]:
    reasons = []  # type: List[str]
    caveats = []  # type: List[str]
    if not _knows_shape(brief):
        # Nothing was said either way -- stay neutral instead of rewarding
        # client-only templates for a silence.
        return 0.5, reasons, caveats
    wants = bool(brief.needs_backend) or brief.implies_backend()
    if wants:
        if ttype in SERVER_TYPES:
            reasons.append("It has a server side, which your features need.")
            return 1.0, reasons, caveats
        if ttype in CLIENT_TYPES:
            caveats.append("No server side here -- you'd add an API separately.")
            return 0.2, reasons, caveats
        return 0.4, reasons, caveats
    if ttype in CLIENT_TYPES or ttype == "cli":
        reasons.append("Nothing to run on a server, so it starts with one command.")
        return 0.9, reasons, caveats
    caveats.append("Brings a server you said you don't need yet.")
    return 0.35, reasons, caveats


def _score_features(brief: ProjectBrief, hay: str) -> Tuple[float, List[str]]:
    features = [f for f in brief.features if isinstance(f, str)]
    if not features:
        return 0.5, []
    hits = 0
    reasons = []  # type: List[str]
    for feature in features:
        # Known ids match on their synonym list; free-text features (recipes
        # describe features in the user's own words) match on their own words.
        words = FEATURE_KEYWORDS.get(feature)
        if words is None:
            words = tuple(_tokens(feature)) or (feature.lower(),)
        if any(word in hay for word in words):
            hits += 1
            if len(reasons) < 2:
                reasons.append(
                    "It already covers " + FEATURE_LABELS.get(feature, feature) + "."
                )
    return _clamp(float(hits) / float(len(features))), reasons


def _score_database(brief: ProjectBrief, hay: str, ttype: str) -> Tuple[float, List[str], List[str]]:
    db = brief.database if isinstance(brief.database, str) else ""
    reasons = []  # type: List[str]
    caveats = []  # type: List[str]
    if not db or db == "unsure":
        return 0.5, reasons, caveats
    if db == "none":
        if any(word in hay for word in ("postgres", "mongo", "prisma", "sqlalchemy")):
            caveats.append("Ships with database wiring you said you don't want.")
            return 0.25, reasons, caveats
        reasons.append("No database to set up, matching what you asked for.")
        return 0.9, reasons, caveats
    words = DATABASE_KEYWORDS.get(db, (db,))
    if any(word in hay for word in words):
        reasons.append("Comes wired for " + db + ", the storage you picked.")
        return 1.0, reasons, caveats
    if ttype in SERVER_TYPES:
        return 0.55, reasons, caveats
    caveats.append("You'd have to add " + db + " yourself.")
    return 0.25, reasons, caveats


def _score_complexity(brief: ProjectBrief, template: Any, ttype: str) -> Tuple[float, List[str], List[str]]:
    complexity = brief.complexity or "simple"
    size = _size_of(template)
    reasons = []  # type: List[str]
    caveats = []  # type: List[str]
    if brief.is_empty():
        return 0.5, reasons, caveats
    if complexity == "simple":
        if ttype == "fullstack":
            caveats.append("More moving parts than a minimal build needs.")
            return 0.3, reasons, caveats
        if size and size <= 8:
            reasons.append("Small enough to read end to end in one sitting.")
            return 1.0, reasons, caveats
        return 0.6, reasons, caveats
    if complexity == "ambitious":
        if ttype == "fullstack" or size >= 10:
            reasons.append("Enough structure already there to build out properly.")
            return 1.0, reasons, caveats
        return 0.5, reasons, caveats
    return 0.7, reasons, caveats


def _score_keywords(brief: ProjectBrief, hay: str) -> Tuple[float, List[str]]:
    text = " ".join(
        part for part in (brief.idea, brief.notes, brief.audience) if isinstance(part, str)
    )
    words = _tokens(text)
    if not words:
        return 0.35, []
    seen = []  # type: List[str]
    for word in words:
        if word in hay and word not in seen:
            seen.append(word)
    if not seen:
        return 0.3, []
    ratio = _clamp(0.5 + 0.25 * len(seen))
    reasons = [
        "Your idea mentions "
        + ", ".join('"%s"' % w for w in seen[:2])
        + ", which this stack handles directly."
    ]
    return ratio, reasons


def _stack_notes(hay: str) -> Tuple[List[str], List[str]]:
    reasons = [blurb for token, blurb in STACK_BLURBS if token in hay][:1]
    caveats = [note for token, note in STACK_CAVEATS if token in hay][:2]
    return reasons, caveats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _score_one(brief: ProjectBrief, template: Any) -> Optional[Recommendation]:
    name = _template_name(template)
    if not name:
        return None
    ttype = _template_type(template)
    hay = _haystack(template)

    reasons = []  # type: List[str]
    caveats = []  # type: List[str]

    kind_score, kind_reasons = _score_kind(brief, ttype)
    reasons.extend(kind_reasons)

    backend_score, backend_reasons, backend_caveats = _score_backend(brief, ttype)
    reasons.extend(backend_reasons)
    caveats.extend(backend_caveats)

    feature_score, feature_reasons = _score_features(brief, hay)
    reasons.extend(feature_reasons)

    db_score, db_reasons, db_caveats = _score_database(brief, hay, ttype)
    reasons.extend(db_reasons)
    caveats.extend(db_caveats)

    complexity_score, complexity_reasons, complexity_caveats = _score_complexity(
        brief, template, ttype
    )
    reasons.extend(complexity_reasons)
    caveats.extend(complexity_caveats)

    keyword_score, keyword_reasons = _score_keywords(brief, hay)
    reasons.extend(keyword_reasons)

    stack_reasons, stack_caveats = _stack_notes(hay)
    reasons.extend(stack_reasons)
    caveats.extend(stack_caveats)

    raw = (
        W_KIND * kind_score
        + W_BACKEND * backend_score
        + W_FEATURES * feature_score
        + W_DATABASE * db_score
        + W_COMPLEXITY * complexity_score
        + W_KEYWORDS * keyword_score
    )
    score = _clamp(raw / _TOTAL_WEIGHT)

    if not reasons:
        description = _text_of(_get(template, "description", "")).strip()
        reasons.append(
            description
            if description
            else "A reasonable general-purpose starting point."
        )

    return Recommendation(
        template=name,
        score=round(score, 6),
        reasons=_dedupe(reasons)[:5],
        caveats=_dedupe(caveats)[:3],
    )


def _dedupe(items: Sequence[str]) -> List[str]:
    out = []  # type: List[str]
    for item in items:
        text = (item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def recommend(
    brief: Optional[ProjectBrief], templates: Sequence[Dict[str, Any]]
) -> List[Recommendation]:
    """Score every template. Highest first; ties broken by name for determinism."""
    if brief is None:
        brief = ProjectBrief()
    elif isinstance(brief, dict):
        brief = ProjectBrief.from_dict(brief)
    if not templates:
        return []

    results = []  # type: List[Recommendation]
    for template in templates:
        try:
            rec = _score_one(brief, template)
        except Exception:
            rec = None
        if rec is not None:
            results.append(rec)

    results.sort(key=lambda r: (-r.score, r.template))
    for index, rec in enumerate(results):
        if index + 1 < len(results):
            rec.margin = round(max(0.0, rec.score - results[index + 1].score), 6)
        elif len(results) == 1:
            rec.margin = rec.score          # uncontested
        else:
            rec.margin = 0.0                # last place is never a clear winner
    return results


def best_match(
    brief: Optional[ProjectBrief], templates: Sequence[Dict[str, Any]]
) -> Optional[Recommendation]:
    results = recommend(brief, templates)
    return results[0] if results else None


def explain(rec: Optional[Recommendation]) -> str:
    """One short paragraph a phone screen can show under the pick."""
    if rec is None:
        return "No template matched."
    lines = ["%s (%s confidence)" % (rec.template, rec.confidence)]
    for reason in rec.reasons:
        lines.append("- " + reason)
    for caveat in rec.caveats:
        lines.append("! " + caveat)
    return "\n".join(lines)
