"""
ProjectBrief -- the structured product brief produced by the guided interview.

Pure logic: no rich, no click, no CLI/UI imports, no network. Python 3.8 safe.

The brief is the hand-off between "a human tapped some numbers on a phone" and
"the planner LLM knows exactly what to build". `to_prompt()` is the text the
planner actually sees, so it derives implications from the answers instead of
dumping raw key/value pairs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ProjectBrief",
    "KIND_LABELS",
    "FEATURE_LABELS",
    "DATABASE_LABELS",
    "COMPLEXITY_LABELS",
]

# ---------------------------------------------------------------------------
# Human labels (shared with interview.py / recommender.py wording)
# ---------------------------------------------------------------------------

KIND_LABELS = {
    "web": "a website people visit in a browser",
    "mobile": "an app that runs on a phone",
    "backend": "a backend/API that other software talks to",
    "fullstack": "a website with its own backend",
    "cli": "a command-line tool",
    "unsure": "something they have not pinned down yet",
}

FEATURE_LABELS = {
    "auth": "accounts & login",
    "storage": "saving data between visits",
    "payments": "taking payments",
    "uploads": "file uploads",
    "admin": "an admin dashboard",
    "darkmode": "dark mode",
    "offline": "working offline",
    "realtime": "live/realtime updates",
    "notifications": "notifications",
    "search": "search",
}

DATABASE_LABELS = {
    "none": "no database",
    "sqlite": "SQLite (a single file, ideal on a phone)",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "unsure": "an unspecified database (pick a sensible default)",
}

COMPLEXITY_LABELS = {
    "simple": "minimal -- the smallest thing that works",
    "standard": "standard -- a normal, complete starting point",
    "ambitious": "ambitious -- build it out properly",
}

# Features that mean "this thing has to remember something".
STORAGE_FEATURES = ("storage", "auth", "payments", "uploads", "admin", "search")
# Features that imply a server component.
BACKEND_FEATURES = ("auth", "payments", "storage", "admin", "realtime", "notifications")

_TRUE_STRINGS = ("1", "true", "yes", "y", "on")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    return bool(value)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(value, (list, tuple, set)):
        out = []  # type: List[str]
        for item in value:
            text = _as_str(item).strip()
            if text and text not in out:
                out.append(text)
        return out
    return [_as_str(value)]


def _shorten(text: str, width: int = 34) -> str:
    """Trim free text to a phone-width value, on a word boundary when possible."""
    text = " ".join(_as_str(text).split())
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    cut = text[: width - 3]
    if " " in cut[width // 2 :]:
        cut = cut[: cut.rstrip().rfind(" ")]
    return cut.rstrip(" ,.;:-") + "..."


def _feature_label(value: str) -> str:
    return FEATURE_LABELS.get(value, value.replace("_", " "))


@dataclass
class ProjectBrief:
    """Everything the planner needs to know, in one serialisable object."""

    name: str = ""
    idea: str = ""
    project_kind: str = ""      # "web"|"mobile"|"backend"|"fullstack"|"cli"|"unsure"
    audience: str = ""
    features: List[str] = field(default_factory=list)
    needs_backend: bool = False
    needs_auth: bool = False
    database: str = ""          # ""|"none"|"sqlite"|"postgres"|"mongo"|"unsure"
    styling: str = ""
    complexity: str = "simple"  # "simple"|"standard"|"ambitious"
    deploy_target: str = ""
    notes: str = ""
    answers: Dict[str, Any] = field(default_factory=dict)

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "idea": self.idea,
            "project_kind": self.project_kind,
            "audience": self.audience,
            "features": list(self.features),
            "needs_backend": bool(self.needs_backend),
            "needs_auth": bool(self.needs_auth),
            "database": self.database,
            "styling": self.styling,
            "complexity": self.complexity,
            "deploy_target": self.deploy_target,
            "notes": self.notes,
            "answers": dict(self.answers),
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "ProjectBrief":
        """Build a brief from a (possibly foreign / partial) dict.

        Unknown keys are ignored, missing keys fall back to defaults, and wrong
        types are coerced rather than raising -- this reads state written by
        older versions and by other tools.
        """
        if not isinstance(d, dict):
            return cls()
        known = {f.name for f in dataclass_fields(cls)}
        get = d.get
        answers = get("answers")
        brief = cls(
            name=_as_str(get("name", "")),
            idea=_as_str(get("idea", "")),
            project_kind=_as_str(get("project_kind", "")),
            audience=_as_str(get("audience", "")),
            features=_as_str_list(get("features")),
            needs_backend=_as_bool(get("needs_backend", False)),
            needs_auth=_as_bool(get("needs_auth", False)),
            database=_as_str(get("database", "")),
            styling=_as_str(get("styling", "")),
            complexity=_as_str(get("complexity", "")) or "simple",
            deploy_target=_as_str(get("deploy_target", "")),
            notes=_as_str(get("notes", "")),
            answers=dict(answers) if isinstance(answers, dict) else {},
        )
        # Preserve anything unrecognised so a round-trip does not lose data.
        extras = {k: v for k, v in d.items() if k not in known}
        if extras:
            merged = dict(extras)
            merged.update(brief.answers)
            brief.answers = merged
        return brief

    # -- helpers ------------------------------------------------------------

    def is_empty(self) -> bool:
        """True when there is nothing worth planning from."""
        if any(
            _as_str(v).strip()
            for v in (
                self.name,
                self.idea,
                self.project_kind,
                self.audience,
                self.database,
                self.styling,
                self.deploy_target,
                self.notes,
            )
        ):
            return False
        if self.features:
            return False
        if self.needs_backend or self.needs_auth:
            return False
        if self.complexity and self.complexity != "simple":
            return False
        return True

    def feature_labels(self) -> List[str]:
        return [_feature_label(f) for f in self.features]

    def implies_storage(self) -> bool:
        return bool(self.database and self.database not in ("none",)) or any(
            f in STORAGE_FEATURES for f in self.features
        )

    def implies_backend(self) -> bool:
        if self.needs_backend or self.needs_auth:
            return True
        if self.project_kind in ("backend", "fullstack"):
            return True
        if self.database and self.database not in ("none",):
            return True
        return any(f in BACKEND_FEATURES for f in self.features)

    def title(self) -> str:
        return self.name.strip() or "Untitled project"

    # -- outputs ------------------------------------------------------------

    def summary_pairs(self) -> List[Tuple[str, str]]:
        """Short label/value pairs for a phone-width review screen."""
        pairs = []  # type: List[Tuple[str, str]]
        pairs.append(("Name", _shorten(self.title(), 28)))
        if self.idea.strip():
            pairs.append(("Idea", _shorten(self.idea, 38)))
        if self.project_kind:
            pairs.append(("Type", _shorten(_kind_short(self.project_kind), 30)))
        if self.audience.strip():
            pairs.append(("For", _shorten(self.audience, 30)))
        if self.features:
            labels = ", ".join(self.feature_labels())
            pairs.append(("Features", _shorten(labels, 38)))
        pairs.append(("Backend", "yes" if self.needs_backend else "no"))
        pairs.append(("Accounts", "yes" if self.needs_auth else "no"))
        if self.database:
            pairs.append(("Database", _shorten(self.database, 20)))
        if self.styling.strip():
            pairs.append(("Styling", _shorten(self.styling, 24)))
        pairs.append(("Scope", _shorten(self.complexity or "simple", 20)))
        if self.deploy_target.strip():
            pairs.append(("Deploy", _shorten(self.deploy_target, 24)))
        if self.notes.strip():
            pairs.append(("Notes", _shorten(self.notes, 38)))
        return pairs

    def to_prompt(self) -> str:
        """A dense natural-language brief for the planner LLM.

        Written the way a senior engineer would brief a teammate: what it is,
        who it is for, what it must do, and the technical consequences that
        follow from those answers.
        """
        if self.is_empty():
            return (
                "PROJECT BRIEF\n"
                "The user has not described the project yet.\n\n"
                "Plan a small, self-contained starter project that is easy to run "
                "from a phone (Termux/Android): minimal dependencies, no build step "
                "that needs native compilation, and a single obvious entry point. "
                "Ask nothing; choose sensible, boring defaults and explain them in "
                "the plan."
            )

        lines = ["PROJECT BRIEF", ""]
        lines.append("Name: " + self.title())

        # -- what it is -----------------------------------------------------
        what = []  # type: List[str]
        if self.idea.strip():
            what.append("The user wants to build: " + " ".join(self.idea.split()) + ".")
        if self.project_kind:
            kind = KIND_LABELS.get(self.project_kind, self.project_kind)
            if self.project_kind == "unsure":
                what.append(
                    "They are not sure what form it should take (" + kind + "); "
                    "choose the simplest form that fits the idea and say why."
                )
            else:
                what.append("In their words this is " + kind + ".")
        if self.audience.strip():
            what.append("It is for: " + " ".join(self.audience.split()) + ".")
        if what:
            lines.append("")
            lines.append("WHAT IT IS")
            lines.extend(what)

        # -- what it must do ------------------------------------------------
        if self.features:
            lines.append("")
            lines.append("MUST DO")
            for feature in self.features:
                lines.append("- " + _feature_label(feature))

        # -- technical implications ----------------------------------------
        implications = self._implications()
        if implications:
            lines.append("")
            lines.append("TECHNICAL IMPLICATIONS")
            for item in implications:
                lines.append("- " + item)

        # -- scope ----------------------------------------------------------
        lines.append("")
        lines.append("SCOPE")
        lines.append(
            "Requested scope is "
            + COMPLEXITY_LABELS.get(self.complexity or "simple", self.complexity)
            + "."
        )
        lines.append(_scope_guidance(self.complexity or "simple"))
        if self.deploy_target.strip():
            lines.append("Target environment: " + " ".join(self.deploy_target.split()) + ".")
        if self.styling.strip():
            lines.append("Styling preference: " + " ".join(self.styling.split()) + ".")
        if self.notes.strip():
            lines.append("")
            lines.append("EXTRA NOTES FROM THE USER")
            lines.append(" ".join(self.notes.split()))

        lines.append("")
        lines.append(
            "Assume this may be built and run on a phone (Termux/Android): prefer "
            "dependencies that install without a native toolchain, keep the number "
            "of processes small, and note anything that will not run locally."
        )
        return "\n".join(lines).strip() + "\n"

    def _implications(self) -> List[str]:
        out = []  # type: List[str]
        db = self.database
        wants_backend = self.implies_backend()

        if self.needs_auth:
            if db in ("postgres", "mongo"):
                out.append(
                    "Accounts were requested with " + DATABASE_LABELS.get(db, db)
                    + ": needs a users table/collection, password hashing, and server-side "
                    "session or token handling."
                )
            elif db == "sqlite":
                out.append(
                    "Accounts were requested with SQLite: needs a users table, password "
                    "hashing, and session handling -- a single-file DB keeps this runnable "
                    "on a phone."
                )
            else:
                out.append(
                    "Accounts were requested, so a persistence layer is mandatory even "
                    "though no database was chosen: pick SQLite unless something else is "
                    "clearly better, and include password hashing plus session handling."
                )
        if "payments" in self.features:
            out.append(
                "Payments imply a server-side integration point and secrets that must "
                "never reach the client; stub the provider behind an interface and read "
                "keys from the environment."
            )
        if "uploads" in self.features:
            out.append(
                "File uploads need a size limit, a content-type check, and a storage "
                "location that is not the source tree."
            )
        if "realtime" in self.features:
            out.append(
                "Realtime updates need a long-lived connection (WebSocket or SSE); "
                "prefer SSE if a plain HTTP server keeps the setup smaller."
            )
        if "offline" in self.features:
            out.append(
                "Offline support means local-first storage and a sync/refresh path, not "
                "just a cache header."
            )
        if "notifications" in self.features:
            out.append(
                "Notifications need a delivery channel decided up front (in-app, email, "
                "or push) -- pick the cheapest one that satisfies the idea."
            )
        if "search" in self.features:
            out.append(
                "Search over stored data: start with a simple indexed query, and keep "
                "the query layer swappable."
            )
        if "admin" in self.features:
            out.append(
                "An admin dashboard implies at least two roles, so authorisation checks "
                "belong in the data layer, not only in the UI."
            )
        if wants_backend and self.project_kind in ("web", "mobile"):
            out.append(
                "The chosen client form has no server of its own, so the plan must "
                "include a separate API surface (or a framework that provides one)."
            )
        if db and db != "none" and db != "unsure":
            out.append(
                "Persistence: " + DATABASE_LABELS.get(db, db)
                + ". Include schema/migration setup and a single place that owns "
                "connection handling."
            )
        elif db == "none":
            out.append(
                "The user explicitly wants no database: keep state in memory or in "
                "local files, and do not add an ORM."
            )
        elif self.implies_storage():
            out.append(
                "The requested features need to store data but no database was chosen: "
                "default to SQLite and say so in the plan."
            )
        if not wants_backend and not self.needs_backend:
            out.append(
                "No backend was requested: keep this fully client-side/local so it can "
                "run with a single command."
            )
        return out


def _kind_short(kind: str) -> str:
    return {
        "web": "website",
        "mobile": "phone app",
        "backend": "backend / API",
        "fullstack": "web + backend",
        "cli": "command-line tool",
        "unsure": "not sure yet",
    }.get(kind, kind)


def _scope_guidance(complexity: str) -> str:
    return {
        "simple": (
            "Ship the smallest working version: one main screen or endpoint, no "
            "optional extras, and no abstractions that are not used twice."
        ),
        "standard": (
            "Scaffold a complete but ordinary starting point: the requested features "
            "wired end to end, basic error handling, and a README that says how to run it."
        ),
        "ambitious": (
            "Build it out properly: layered structure, tests for the core logic, "
            "configuration via environment variables, and clear extension points."
        ),
    }.get(complexity, "Use your judgement on scope and state the assumption in the plan.")
