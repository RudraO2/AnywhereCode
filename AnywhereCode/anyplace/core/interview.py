"""
The guided interview -- turns taps on a phone into a ProjectBrief.

Pure logic: no rich, no click, no CLI/UI imports, no input(). Python 3.8 safe.

Design notes
------------
* Questions are phrased for a non-expert. `project_kind` asks what they are
  building in plain words, never "pick a framework".
* Branching is declarative (`Question.when`) and re-evaluated against the
  *current* answers, so `applicable()`, `progress()` and `is_complete()` all
  move as the user answers.
* Some answers are *inferred* rather than asked twice: picking "accounts &
  login" pre-answers `needs_auth`, and picking a backend/fullstack project kind
  pre-answers `needs_backend`. Inferences are tracked so `back()` can undo them.
* Mode budgets (asserted in tests): EXPERT == 2, QUICK <= 4, GUIDED in 6..10
  for every reachable combination of answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .brief import BACKEND_FEATURES, STORAGE_FEATURES, ProjectBrief

__all__ = [
    "QUICK",
    "GUIDED",
    "EXPERT",
    "MODES",
    "Question",
    "QUESTION_BANK",
    "Interview",
    "get_question",
]

QUICK, GUIDED, EXPERT = "quick", "guided", "expert"
MODES = (QUICK, GUIDED, EXPERT)

_ALL_MODES = (QUICK, GUIDED, EXPERT)

#: Questions whose values drive scaffolding and template scoring. Their
#: vocabulary is closed: an unrecognised value is dropped rather than stored.
#: Everything else (audience, styling, deploy_target, features) accepts richer
#: free text from recipes and saved sessions.
CLOSED_VOCAB_IDS = ("project_kind", "complexity", "database")
_YES = ("y", "yes", "true", "1", "on", "yep", "yeah")
_NO = ("n", "no", "false", "0", "off", "nope")


@dataclass
class Question:
    id: str
    text: str
    kind: str                                   # "choice"|"text"|"yesno"|"multi"
    options: List[Tuple[str, str]] = field(default_factory=list)   # (value, label)
    default: Any = None
    help: str = ""
    modes: Tuple[str, ...] = _ALL_MODES
    when: Optional[Callable[[Dict[str, Any]], bool]] = None
    required: bool = True
    placeholder: str = ""

    def option_values(self) -> List[str]:
        return [str(v) for v, _ in self.options]

    def label_for(self, value: Any) -> str:
        for val, label in self.options:
            if val == value:
                return label
        return "" if value is None else str(value)

    def applies(self, answers: Dict[str, Any]) -> bool:
        if self.when is None:
            return True
        try:
            return bool(self.when(answers))
        except Exception:      # a broken predicate must not kill the interview
            return False


# ---------------------------------------------------------------------------
# Branch predicates
# ---------------------------------------------------------------------------

_SERVER_KINDS = ("backend", "fullstack")
_STYLED_KINDS = ("web", "fullstack", "mobile")


def _kind(answers: Dict[str, Any]) -> str:
    value = answers.get("project_kind")
    return value if isinstance(value, str) else ""


def _features(answers: Dict[str, Any]) -> List[str]:
    value = answers.get("features")
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _ask_needs_backend(answers: Dict[str, Any]) -> bool:
    """Skip it when the project kind already answers it."""
    return _kind(answers) not in _SERVER_KINDS


def _ask_needs_auth(answers: Dict[str, Any]) -> bool:
    """Skip it when the user already picked 'accounts & login'."""
    return "auth" not in _features(answers)


def _wants_storage(answers: Dict[str, Any]) -> bool:
    if _truthy(answers.get("needs_backend")):
        return True
    if _kind(answers) in _SERVER_KINDS:
        return True
    return any(f in STORAGE_FEATURES for f in _features(answers))


def _ask_styling(answers: Dict[str, Any]) -> bool:
    return _kind(answers) in _STYLED_KINDS


def _ask_deploy(answers: Dict[str, Any]) -> bool:
    # Deliberately disjoint from _ask_styling so the guided set can never
    # exceed 10 questions: things with a UI get asked about styling, things
    # without get asked where they will run.
    return _kind(answers) not in _STYLED_KINDS


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _YES
    return bool(value)


# ---------------------------------------------------------------------------
# The question bank
# ---------------------------------------------------------------------------

QUESTION_BANK = [
    Question(
        id="project_name",
        text="What should the project be called?",
        kind="text",
        modes=_ALL_MODES,
        placeholder="my-app",
        help="Used for the folder name and the README title. Letters, numbers and dashes work best.",
    ),
    Question(
        id="idea",
        text="In one line, what do you want to build?",
        kind="text",
        modes=_ALL_MODES,
        placeholder="a place to log my runs and see a weekly chart",
        help="Plain words are fine. This is the single most useful thing you can tell me.",
    ),
    Question(
        id="project_kind",
        text="What kind of thing is it?",
        kind="choice",
        options=[
            ("web", "A website people visit"),
            ("mobile", "An app on a phone"),
            ("backend", "A backend/API other things talk to"),
            ("fullstack", "A website with its own backend"),
            ("cli", "A tool you run in the terminal"),
            ("unsure", "Not sure -- help me decide"),
        ],
        default="web",
        modes=(QUICK, GUIDED),
        help="Pick the closest one. 'Not sure' is a real answer -- I'll choose for you and explain why.",
    ),
    Question(
        id="audience",
        text="Who is it for?",
        kind="choice",
        options=[
            ("me", "Just me"),
            ("friends", "Me and a few people I know"),
            ("public", "Anyone on the internet"),
            ("work", "My team or customers at work"),
        ],
        default="me",
        modes=(GUIDED,),
        required=False,
        help="This changes how careful the setup is about accounts, limits and errors.",
    ),
    Question(
        id="features",
        text="What does it need to do? (pick any)",
        kind="multi",
        options=[
            ("auth", "Accounts & login"),
            ("storage", "Save data between visits"),
            ("payments", "Take payments"),
            ("uploads", "Upload files or photos"),
            ("admin", "Admin dashboard"),
            ("search", "Search"),
            ("realtime", "Live updates"),
            ("notifications", "Notifications"),
            ("offline", "Work offline"),
            ("darkmode", "Dark mode"),
        ],
        default=[],
        modes=(GUIDED,),
        required=False,
        help="Choose several, e.g. '1,3 5'. 'none' is fine -- you can add things later.",
    ),
    Question(
        id="needs_backend",
        text="Does it need a server of its own?",
        kind="yesno",
        default=False,
        modes=(GUIDED,),
        when=_ask_needs_backend,
        help="Yes if data has to be shared between people or devices. No if everything can live on one device.",
    ),
    Question(
        id="needs_auth",
        text="Do people need to sign in?",
        kind="yesno",
        default=False,
        modes=(GUIDED,),
        when=_ask_needs_auth,
        help="Skipped automatically if you already picked 'Accounts & login'.",
    ),
    Question(
        id="database",
        text="Where should the data live?",
        kind="choice",
        options=[
            ("sqlite", "A single file on the device (SQLite)"),
            ("postgres", "A proper server database (PostgreSQL)"),
            ("mongo", "A document database (MongoDB)"),
            ("none", "Nowhere -- don't store anything"),
            ("unsure", "Not sure -- pick for me"),
        ],
        default="sqlite",
        modes=(GUIDED,),
        when=_wants_storage,
        help="SQLite needs nothing installed and works on a phone. Pick it unless you know you need more.",
    ),
    Question(
        id="styling",
        text="How should it look?",
        kind="choice",
        options=[
            ("default", "Whatever the template ships with"),
            ("tailwind", "Utility CSS (Tailwind)"),
            ("minimal", "Plain CSS, as little as possible"),
            ("component", "A component library"),
        ],
        default="default",
        modes=(GUIDED,),
        when=_ask_styling,
        required=False,
        help="Only affects the look, never the behaviour.",
    ),
    Question(
        id="complexity",
        text="How much should I build up front?",
        kind="choice",
        options=[
            ("simple", "Keep it minimal"),
            ("standard", "Standard"),
            ("ambitious", "Go big"),
        ],
        default="standard",
        modes=(QUICK, GUIDED),
        help="Minimal is fastest to read and run on a phone. Go big adds structure, config and tests.",
    ),
    Question(
        id="deploy_target",
        text="Where will it run?",
        kind="choice",
        options=[
            ("local", "On this device (Termux/laptop)"),
            ("cloud", "A free cloud host"),
            ("container", "Docker somewhere"),
            ("unsure", "Not sure yet"),
        ],
        default="local",
        modes=(GUIDED,),
        when=_ask_deploy,
        required=False,
        help="Running on the phone itself rules out anything that needs a heavy build step.",
    ),
    Question(
        id="notes",
        text="Anything else I should know?",
        kind="text",
        default="",
        modes=(),        # never asked; available for recipes/prefill and the API
        required=False,
        placeholder="must work without internet",
        help="Optional. Free text that is passed straight to the planner.",
    ),
]

_BY_ID = {q.id: q for q in QUESTION_BANK}

#: qid -> ProjectBrief attribute
FIELD_MAP = {
    "project_name": "name",
    "idea": "idea",
    "project_kind": "project_kind",
    "audience": "audience",
    "features": "features",
    "needs_backend": "needs_backend",
    "needs_auth": "needs_auth",
    "database": "database",
    "styling": "styling",
    "complexity": "complexity",
    "deploy_target": "deploy_target",
    "notes": "notes",
}


def get_question(qid: str) -> Optional[Question]:
    return _BY_ID.get(qid)


# ---------------------------------------------------------------------------
# Value coercion / validation
# ---------------------------------------------------------------------------

def _coerce(question: Question, value: Any) -> Any:
    """Normalise a raw answer, raising a clear error when it cannot be used."""
    kind = question.kind
    if kind == "yesno":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _YES:
                return True
            if text in _NO:
                return False
            raise ValueError(
                "Question '%s' expects yes or no, got %r" % (question.id, value)
            )
        if isinstance(value, int):
            return bool(value)
        raise TypeError(
            "Question '%s' expects a yes/no answer, got %s"
            % (question.id, type(value).__name__)
        )

    if kind == "multi":
        if isinstance(value, str):
            items = [p.strip() for p in value.replace(";", ",").split(",")]
            items = [p for p in items if p]
            if items and items[0].lower() in ("none", "no", ""):
                items = []
        elif isinstance(value, (list, tuple, set)):
            items = [str(v).strip() for v in value if str(v).strip()]
        elif value is None:
            items = []
        else:
            raise TypeError(
                "Question '%s' expects a list of choices, got %s"
                % (question.id, type(value).__name__)
            )
        allowed = question.option_values()
        out = []  # type: List[str]
        for item in items:
            if allowed and item not in allowed:
                raise ValueError(
                    "Question '%s' has no option %r. Valid options: %s"
                    % (question.id, item, ", ".join(allowed))
                )
            if item not in out:
                out.append(item)
        return out

    if kind == "choice":
        if value is None:
            raise ValueError("Question '%s' needs a choice, got None" % question.id)
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        allowed = question.option_values()
        if allowed and value not in allowed:
            raise ValueError(
                "Question '%s' has no option %r. Valid options: %s"
                % (question.id, value, ", ".join(allowed))
            )
        return value

    # text
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_free(question: Question, value: Any) -> Any:
    """Lenient coercion for prefilled values outside the offered options."""
    if question.kind == "multi":
        if isinstance(value, str):
            items = [p.strip() for p in value.replace(";", ",").split(",")]
        else:
            items = [str(v).strip() for v in value]
        out = []  # type: List[str]
        for item in items:
            if item and item not in out:
                out.append(item)
        return out
    return _as_text(value)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

class Interview:
    """Stateful walk through the applicable questions for a mode."""

    def __init__(self, mode: str = GUIDED, answers: Optional[Dict[str, Any]] = None):
        mode = (mode or GUIDED).strip().lower()
        if mode not in MODES:
            raise ValueError(
                "Unknown interview mode %r. Valid modes: %s" % (mode, ", ".join(MODES))
            )
        self._mode = mode
        self._answers = {}          # type: Dict[str, Any]
        self._history = []          # type: List[str]
        self._inferred = {}         # type: Dict[str, Set[str]]
        if answers:
            self.prefill(answers)

    # -- state ----------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def answers(self) -> Dict[str, Any]:
        return dict(self._answers)

    def questions_for_mode(self) -> List[Question]:
        return [q for q in QUESTION_BANK if self._mode in q.modes]

    def applicable(self) -> List[Question]:
        """Questions this mode asks, filtered by the current answers."""
        snapshot = self._answers
        return [q for q in self.questions_for_mode() if q.applies(snapshot)]

    def next_question(self) -> Optional[Question]:
        for question in self.applicable():
            if question.id not in self._answers:
                return question
        return None

    def progress(self) -> Tuple[int, int]:
        applicable = self.applicable()
        answered = sum(1 for q in applicable if q.id in self._answers)
        return answered, len(applicable)

    def is_complete(self) -> bool:
        for question in self.applicable():
            if question.required and question.id not in self._answers:
                return False
        return True

    # -- mutation -------------------------------------------------------

    def answer(self, qid: str, value: Any) -> None:
        question = _BY_ID.get(qid)
        if question is None:
            raise ValueError(
                "Unknown question id %r. Valid ids: %s"
                % (qid, ", ".join(sorted(_BY_ID)))
            )
        coerced = _coerce(question, value)
        self._drop_inferred(qid)
        self._answers[qid] = coerced
        if qid in self._history:
            self._history.remove(qid)
        self._history.append(qid)
        self._infer_from(qid, coerced)

    def prefill(self, values: Dict[str, Any]) -> None:
        """Best-effort pre-answering (recipes, saved sessions, CLI flags).

        Unknown ids and unusable values are ignored rather than raising, and
        prefilled answers are not part of the `back()` history. Values outside
        a question's offered options are kept as free text unless the question
        has a closed vocabulary (see CLOSED_VOCAB_IDS) -- recipes describe
        audiences and features in their own words.
        """
        if not isinstance(values, dict):
            return
        for qid, value in values.items():
            question = _BY_ID.get(qid)
            if question is None:
                continue
            try:
                coerced = _coerce(question, value)
            except TypeError:
                continue
            except ValueError:
                if qid in CLOSED_VOCAB_IDS:
                    continue
                try:
                    coerced = _coerce_free(question, value)
                except (ValueError, TypeError):
                    continue
            self._answers[qid] = coerced
            self._infer_from(qid, coerced)

    def back(self) -> Optional[Question]:
        """Un-answer the most recently answered question and re-expose it."""
        while self._history:
            qid = self._history.pop()
            self._drop_inferred(qid)
            self._answers.pop(qid, None)
            question = _BY_ID.get(qid)
            if question is None:
                continue
            if self._mode in question.modes and question.applies(self._answers):
                return question
            # The question no longer applies (a branch closed behind us) --
            # keep stepping back until something askable turns up.
            return self.next_question()
        return None

    def reset(self) -> None:
        self._answers = {}
        self._history = []
        self._inferred = {}

    # -- inference ------------------------------------------------------

    def _infer_from(self, qid: str, value: Any) -> None:
        """Pre-answer questions whose answer is already implied."""
        inferred = set()  # type: Set[str]
        if qid == "project_kind" and value in _SERVER_KINDS:
            if "needs_backend" not in self._history:
                self._answers["needs_backend"] = True
                inferred.add("needs_backend")
        if qid == "features" and isinstance(value, (list, tuple)):
            values = list(value)
            if "auth" in values and "needs_auth" not in self._history:
                self._answers["needs_auth"] = True
                inferred.add("needs_auth")
            if (
                "needs_backend" not in self._history
                and "needs_backend" not in self._answers
                and any(f in BACKEND_FEATURES for f in values)
                and _kind(self._answers) not in ("cli",)
            ):
                self._answers["needs_backend"] = True
                inferred.add("needs_backend")
        if inferred:
            self._inferred[qid] = inferred

    def _drop_inferred(self, qid: str) -> None:
        for target in self._inferred.pop(qid, set()):
            self._answers.pop(target, None)
            if target in self._history:
                self._history.remove(target)

    # -- output ---------------------------------------------------------

    def to_brief(self) -> ProjectBrief:
        brief = ProjectBrief()
        for qid, attr in FIELD_MAP.items():
            if qid not in self._answers:
                continue
            value = self._answers[qid]
            if attr == "features":
                brief.features = list(value) if isinstance(value, (list, tuple)) else []
            elif attr in ("needs_backend", "needs_auth"):
                setattr(brief, attr, _truthy(value))
            else:
                setattr(brief, attr, value if isinstance(value, str) else str(value))
        if not brief.complexity:
            brief.complexity = "simple"
        # Late inference for briefs assembled without going through answer().
        if not brief.needs_auth and "auth" in brief.features:
            brief.needs_auth = True
        if not brief.needs_backend and brief.project_kind in _SERVER_KINDS:
            brief.needs_backend = True
        brief.answers = dict(self._answers)
        return brief
