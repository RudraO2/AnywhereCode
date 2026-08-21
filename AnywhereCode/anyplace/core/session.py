"""
Session persistence -- so a returning phone user is one keypress from where
they left off.

Design constraints, in order of importance:

1. **Never lose the app to bad state.** A corrupt file, a file holding a JSON
   list, a version from the future, or a missing directory all degrade to a
   fresh default. `load()` never raises.
2. **Never corrupt the file.** Writes go to a temp file in the same directory
   and are moved into place with `os.replace`, which is atomic on POSIX -- a
   phone dying mid-write leaves either the old file or the new one.
3. **Private.** The file is chmod 0600; it can hold project paths.

Pure logic: no rich, no click, no CLI/UI imports, no network. Python 3.8 safe.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

__all__ = ["SessionState", "SessionStore", "CURRENT_VERSION", "MAX_RECENT"]

CURRENT_VERSION = 1
MAX_RECENT = 10
FILE_MODE = 0o600
DIR_MODE = 0o700

PathLike = Union[str, "os.PathLike[str]", Path]


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out = []  # type: List[str]
    for item in value:
        text = _as_str(item)
        if text and text not in out:
            out.append(text)
    return out


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


@dataclass
class SessionState:
    last_template: str = ""
    last_provider: str = ""
    last_project_name: str = ""
    last_mode: str = ""
    recent_projects: List[str] = field(default_factory=list)
    saved_answers: Dict[str, Any] = field(default_factory=dict)
    run_count: int = 0
    updated_at: str = ""
    version: int = CURRENT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_template": self.last_template,
            "last_provider": self.last_provider,
            "last_project_name": self.last_project_name,
            "last_mode": self.last_mode,
            "recent_projects": list(self.recent_projects),
            "saved_answers": dict(self.saved_answers),
            "run_count": int(self.run_count),
            "updated_at": self.updated_at,
            "version": int(self.version),
        }

    @classmethod
    def from_dict(cls, d: Any) -> "SessionState":
        """Tolerant reader: wrong types are coerced, junk becomes a default."""
        if not isinstance(d, dict):
            return cls()
        answers = d.get("saved_answers")
        return cls(
            last_template=_as_str(d.get("last_template", "")),
            last_provider=_as_str(d.get("last_provider", "")),
            last_project_name=_as_str(d.get("last_project_name", "")),
            last_mode=_as_str(d.get("last_mode", "")),
            recent_projects=_as_str_list(d.get("recent_projects"))[:MAX_RECENT],
            saved_answers=dict(answers) if isinstance(answers, dict) else {},
            run_count=_as_int(d.get("run_count"), 0),
            updated_at=_as_str(d.get("updated_at", "")),
            version=_as_int(d.get("version"), CURRENT_VERSION),
        )

    def is_fresh(self) -> bool:
        return self == SessionState(updated_at=self.updated_at, version=self.version)


class SessionStore:
    """Reads/writes a single JSON file holding the last-used session state."""

    def __init__(self, path: Optional[PathLike] = None):
        if path is None:
            # Imported lazily: get_config_dir() creates directories, and tests
            # must never touch the real home.
            from ..config.environment import get_config_dir

            path = Path(get_config_dir()) / "session.json"
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # -- read -----------------------------------------------------------

    def load(self) -> SessionState:
        """Always returns a usable state -- never raises."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except (OSError, IOError, ValueError):
            return SessionState()
        if not raw.strip():
            return SessionState()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return SessionState()
        if not isinstance(data, dict):
            return SessionState()
        version = _as_int(data.get("version"), CURRENT_VERSION)
        if version > CURRENT_VERSION:
            # Written by a newer Anywhere Code: don't guess at its shape.
            return SessionState()
        try:
            return SessionState.from_dict(data)
        except Exception:
            return SessionState()

    # -- write ----------------------------------------------------------

    def save(self, state: SessionState) -> None:
        """Atomically write `state`, 0600, creating the directory if needed."""
        if not isinstance(state, SessionState):
            state = SessionState.from_dict(state)
        state.updated_at = _now()
        state.version = CURRENT_VERSION
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True, default=str)

        directory = self._path.parent
        directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(directory), DIR_MODE)
        except OSError:
            pass

        handle, tmp_name = tempfile.mkstemp(
            prefix=self._path.name + ".", suffix=".tmp", dir=str(directory)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp_name, FILE_MODE)
            os.replace(tmp_name, str(self._path))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        try:
            os.chmod(str(self._path), FILE_MODE)
        except OSError:
            pass

    def update(self, **fields: Any) -> SessionState:
        """Merge `fields` into the stored state and save it.

        Scalars replace, `saved_answers` merges key-by-key, and unknown field
        names are ignored so an older build never chokes on a newer caller.
        """
        state = self.load()
        known = {f.name for f in dataclass_fields(SessionState)}
        for key, value in fields.items():
            if key not in known:
                continue
            if key == "saved_answers":
                merged = dict(state.saved_answers)
                if isinstance(value, dict):
                    merged.update(value)
                    state.saved_answers = merged
                elif value is None:
                    state.saved_answers = {}
                continue
            if key == "recent_projects":
                state.recent_projects = _as_str_list(value)[:MAX_RECENT]
                continue
            if key == "run_count":
                state.run_count = _as_int(value, state.run_count)
                continue
            if key == "version":
                continue
            setattr(state, key, _as_str(value))
        self.save(state)
        return state

    def remember_project(self, path: PathLike) -> SessionState:
        """Push a project path to the front of the recent list (deduped, cap 10)."""
        try:
            resolved = str(Path(path).expanduser().resolve())
        except (OSError, RuntimeError, TypeError, ValueError):
            resolved = _as_str(path)
        state = self.load()
        recent = [p for p in state.recent_projects if p != resolved]
        recent.insert(0, resolved)
        state.recent_projects = recent[:MAX_RECENT]
        if not state.last_project_name:
            state.last_project_name = os.path.basename(resolved)
        self.save(state)
        return state

    def bump_run_count(self) -> SessionState:
        state = self.load()
        state.run_count = _as_int(state.run_count, 0) + 1
        self.save(state)
        return state

    def clear(self) -> None:
        """Forget everything. Missing file is not an error."""
        try:
            os.unlink(str(self._path))
        except OSError:
            pass


def _mode_of(path: PathLike) -> int:
    return stat.S_IMODE(os.stat(str(path)).st_mode)
