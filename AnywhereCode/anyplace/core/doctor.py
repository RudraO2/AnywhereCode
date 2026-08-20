"""
Environment diagnostics for Anywhere Code.

Pure logic: no ``rich``, no ``click``, no imports from ``anyplace.cli`` or
``anyplace.ui``.  The caller renders the report however it likes.

Every check accepts injectable dependencies so tests never touch the real
system, never shell out and never hit the network.  ``run_all()`` never
raises: a check that blows up is reported as a WARN.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

PASS = "pass"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

STATUSES = (PASS, WARN, FAIL, SKIP)

#: Minimum interpreter this tool supports.
MIN_PYTHON = (3, 8)
#: Below this we nag (some deps are much happier on 3.9+).
RECOMMENDED_PYTHON = (3, 9)

#: Terminal width thresholds (columns).
TERMINAL_FAIL_WIDTH = 25
TERMINAL_WARN_WIDTH = 32

#: Free disk thresholds (megabytes).
DISK_FAIL_MB = 100
DISK_WARN_MB = 500

_MB = 1024 * 1024


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------


@dataclass
class Check:
    """The result of a single diagnostic."""

    id: str
    title: str
    status: str
    detail: str = ""
    fix: str = ""
    critical: bool = False

    @property
    def ok(self) -> bool:
        """True when the check did not find a problem (pass or skip)."""
        return self.status in (PASS, SKIP)


@dataclass
class DoctorReport:
    """A full diagnostic run."""

    checks: List[Check] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """True when nothing failed (warnings are tolerated)."""
        return not any(c.status == FAIL for c in self.checks)

    @property
    def blockers(self) -> List[Check]:
        """Failing checks that make the tool unusable."""
        return [c for c in self.checks if c.status == FAIL and c.critical]

    def by_status(self, status: str) -> List[Check]:
        """All checks with the given status, in run order."""
        return [c for c in self.checks if c.status == status]

    def get(self, check_id: str) -> Optional[Check]:
        """Look up a single check by id."""
        for check in self.checks:
            if check.id == check_id:
                return check
        return None

    def summary(self) -> Dict[str, int]:
        """Counts per status plus a ``total`` key."""
        counts = dict((s, 0) for s in STATUSES)
        for check in self.checks:
            if check.status in counts:
                counts[check.status] += 1
            else:  # defensive: unknown status still counts toward the total
                counts[check.status] = counts.get(check.status, 0) + 1
        counts["total"] = len(self.checks)
        return counts


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _detect_termux() -> bool:
    """Best-effort Termux detection (never raises)."""
    try:
        from anyplace.config.environment import is_termux

        return bool(is_termux())
    except Exception:
        return (
            os.path.exists("/data/data/com.termux")
            or os.environ.get("TERMUX_APP_PID") is not None
            or "/com.termux" in os.environ.get("PREFIX", "")
        )


def _default_which(name: str) -> Optional[str]:
    return shutil.which(name)


def _default_run(args: Sequence[str]) -> str:
    """Run a command and return its combined output as text."""
    import subprocess  # local import: keeps module import cheap

    completed = subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    return completed.stdout.decode("utf-8", "replace").strip()


def _install_fix(package: str, termux: bool, system: Optional[str] = None) -> str:
    """Platform-appropriate, copy-pasteable install command."""
    if termux:
        return "pkg install {0}".format(package)
    sysname = (system or platform.system() or "").lower()
    if sysname == "darwin":
        return "brew install {0}".format(package)
    if sysname == "windows":
        return "winget install {0}  (or download the official installer)".format(package)
    return "sudo apt install {0}   # or your distro's package manager".format(package)


def _parse_version(text: str) -> Tuple[int, ...]:
    """Pull the first dotted number out of a version string.

    ``"git version 2.39.2"`` -> ``(2, 39, 2)``.  Returns ``()`` when nothing
    numeric can be found, so callers can degrade gracefully.
    """
    import re

    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    if not match:
        return ()
    return tuple(int(g) for g in match.groups() if g is not None)


def _default_writable(path: Path) -> bool:
    """Actually try to write, walking up to the nearest existing ancestor."""
    import tempfile

    probe = Path(path)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if not probe.is_dir():
        return False
    try:
        handle = tempfile.NamedTemporaryFile(dir=str(probe), prefix=".anyplace-", delete=True)
        handle.close()
        return True
    except Exception:
        return False


def _rc_file_for_shell(shell: str) -> str:
    """Which rc file the user should append their PATH export to."""
    name = os.path.basename(shell or "").lower()
    if "zsh" in name:
        return "~/.zshrc"
    if "fish" in name:
        return "~/.config/fish/config.fish"
    if "bash" in name:
        return "~/.bashrc"
    return "~/.profile"


def _default_network_probe() -> bool:
    """Cheap reachability probe.  Only used when nothing is injected."""
    import socket

    try:
        conn = socket.create_connection(("api.anthropic.com", 443), timeout=4)
        conn.close()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def check_python(version_info: Optional[Sequence[int]] = None) -> Check:
    """Interpreter version: >= 3.8 required, 3.9+ recommended."""
    info = tuple(version_info if version_info is not None else sys.version_info[:3])
    shown = ".".join(str(part) for part in info[:3]) or "unknown"

    if info[:2] < MIN_PYTHON:
        return Check(
            id="python",
            title="Python version",
            status=FAIL,
            detail="Python {0} found, 3.8+ required.".format(shown),
            fix="pkg install python   (Termux)  /  sudo apt install python3   (desktop)",
            critical=True,
        )
    if info[:2] < RECOMMENDED_PYTHON:
        return Check(
            id="python",
            title="Python version",
            status=PASS,
            detail="Python {0} works, but 3.9+ is smoother.".format(shown),
            fix="pkg upgrade python   # optional, 3.9+ recommended",
        )
    return Check(
        id="python",
        title="Python version",
        status=PASS,
        detail="Python {0}".format(shown),
    )


def check_git(
    which: Optional[Callable[[str], Optional[str]]] = None,
    run: Optional[Callable[[Sequence[str]], str]] = None,
    termux: Optional[bool] = None,
    system: Optional[str] = None,
) -> Check:
    """git installed, and a version new enough to be usable."""
    which = which or _default_which
    run = run or _default_run
    on_termux = _detect_termux() if termux is None else bool(termux)

    path = which("git")
    if not path:
        return Check(
            id="git",
            title="Git",
            status=FAIL,
            detail="git is not installed, so projects cannot be version controlled.",
            fix=_install_fix("git", on_termux, system),
        )

    try:
        raw = run(["git", "--version"])
    except Exception as exc:
        return Check(
            id="git",
            title="Git",
            status=WARN,
            detail="git found at {0} but 'git --version' failed: {1}".format(
                path, exc.__class__.__name__
            ),
            fix="Reinstall git: {0}".format(_install_fix("git", on_termux, system)),
        )

    version = _parse_version(raw)
    if not version:
        return Check(
            id="git",
            title="Git",
            status=WARN,
            detail="git found at {0} but its version could not be read.".format(path),
            fix="Reinstall git: {0}".format(_install_fix("git", on_termux, system)),
        )
    if version[0] < 2:
        return Check(
            id="git",
            title="Git",
            status=WARN,
            detail="git {0} is old; 2.x is expected.".format(
                ".".join(str(p) for p in version)
            ),
            fix="Upgrade git: {0}".format(_install_fix("git", on_termux, system)),
        )
    return Check(
        id="git",
        title="Git",
        status=PASS,
        detail="git {0}".format(".".join(str(p) for p in version)),
    )


def check_node(
    which: Optional[Callable[[str], Optional[str]]] = None,
    run: Optional[Callable[[Sequence[str]], str]] = None,
    termux: Optional[bool] = None,
    system: Optional[str] = None,
    min_major: int = 18,
) -> Check:
    """Node.js: only needed for the JavaScript templates, so never a FAIL."""
    which = which or _default_which
    run = run or _default_run
    on_termux = _detect_termux() if termux is None else bool(termux)

    path = which("node")
    if not path:
        return Check(
            id="node",
            title="Node.js",
            status=WARN,
            detail="node is not installed. Only needed for JavaScript templates.",
            fix=_install_fix("nodejs", on_termux, system),
        )

    try:
        raw = run(["node", "--version"])
    except Exception as exc:
        return Check(
            id="node",
            title="Node.js",
            status=WARN,
            detail="node found at {0} but 'node --version' failed: {1}".format(
                path, exc.__class__.__name__
            ),
            fix="Reinstall node: {0}".format(_install_fix("nodejs", on_termux, system)),
        )

    version = _parse_version(raw)
    if not version:
        return Check(
            id="node",
            title="Node.js",
            status=WARN,
            detail="node found at {0} but its version could not be read.".format(path),
            fix="Reinstall node: {0}".format(_install_fix("nodejs", on_termux, system)),
        )
    if version[0] < min_major:
        return Check(
            id="node",
            title="Node.js",
            status=WARN,
            detail="node {0} is older than {1}; some templates need {1}+.".format(
                ".".join(str(p) for p in version), min_major
            ),
            fix="Upgrade node: {0}".format(_install_fix("nodejs", on_termux, system)),
        )
    return Check(
        id="node",
        title="Node.js",
        status=PASS,
        detail="node {0}".format(".".join(str(p) for p in version)),
    )


def check_storage(
    home: Optional[Any] = None,
    termux: Optional[bool] = None,
    writable: Optional[Callable[[Path], bool]] = None,
    projects_dir: Optional[Any] = None,
) -> Check:
    """Somewhere to actually put generated projects, and it must be writable."""
    home_path = Path(home) if home is not None else Path.home()
    on_termux = _detect_termux() if termux is None else bool(termux)
    is_writable = writable or _default_writable

    if on_termux:
        target = Path(projects_dir) if projects_dir is not None else home_path / "storage" / "downloads"
        if not target.exists():
            return Check(
                id="storage",
                title="Storage access",
                status=FAIL,
                detail="{0} is missing, so projects cannot be saved where you can see them.".format(
                    target
                ),
                fix="termux-setup-storage   # then tap Allow, and reopen Termux",
            )
        if not is_writable(target):
            return Check(
                id="storage",
                title="Storage access",
                status=FAIL,
                detail="{0} exists but is not writable.".format(target),
                fix="termux-setup-storage   # re-grant storage permission",
            )
        return Check(
            id="storage",
            title="Storage access",
            status=PASS,
            detail="Projects will be saved to {0}".format(target),
        )

    target = Path(projects_dir) if projects_dir is not None else home_path / ".anyplace" / "projects"
    if not is_writable(target):
        return Check(
            id="storage",
            title="Storage access",
            status=FAIL,
            detail="Cannot write to the projects directory {0}".format(target),
            fix='mkdir -p "{0}" && chmod u+w "{0}"'.format(target),
        )
    return Check(
        id="storage",
        title="Storage access",
        status=PASS,
        detail="Projects will be saved to {0}".format(target),
    )


def check_path_entry(
    path_env: Optional[str] = None,
    home: Optional[Any] = None,
    shell: Optional[str] = None,
) -> Check:
    """``~/.local/bin`` on PATH - the #1 cause of 'command not found'."""
    raw_path = os.environ.get("PATH", "") if path_env is None else path_env
    home_path = Path(home) if home is not None else Path.home()
    shell_name = os.environ.get("SHELL", "") if shell is None else shell

    target = home_path / ".local" / "bin"
    entries = [e for e in (raw_path or "").split(os.pathsep) if e]
    expanded = set()
    for entry in entries:
        try:
            expanded.add(os.path.normpath(os.path.expanduser(entry)))
        except Exception:
            expanded.add(entry)

    if os.path.normpath(str(target)) in expanded:
        return Check(
            id="path",
            title="PATH entry",
            status=PASS,
            detail="{0} is on your PATH.".format(target),
        )

    rc_file = _rc_file_for_shell(shell_name)
    if rc_file.endswith("config.fish"):
        export_line = 'fish_add_path "$HOME/.local/bin"'
    else:
        export_line = 'export PATH="$HOME/.local/bin:$PATH"'
    return Check(
        id="path",
        title="PATH entry",
        status=WARN,
        detail="{0} is not on your PATH, so 'anyplace' may say 'command not found'.".format(
            target
        ),
        fix="echo '{0}' >> {1} && . {1}".format(export_line, rc_file),
    )


def check_terminal(width: Optional[int] = None) -> Check:
    """Terminal width - below 25 columns the UI cannot lay out at all."""
    if width is None:
        try:
            width = shutil.get_terminal_size((80, 24)).columns
        except Exception:
            width = 80
    try:
        cols = int(width)
    except (TypeError, ValueError):
        return Check(
            id="terminal",
            title="Terminal size",
            status=WARN,
            detail="Terminal width could not be determined.",
            fix="Set COLUMNS, e.g. export COLUMNS=60",
        )

    if cols < TERMINAL_FAIL_WIDTH:
        return Check(
            id="terminal",
            title="Terminal size",
            status=FAIL,
            detail="{0} columns is too narrow; {1}+ is required.".format(
                cols, TERMINAL_FAIL_WIDTH
            ),
            fix="Rotate the phone to landscape, or lower the Termux font size "
            "(long-press the screen > Style > Font size).",
        )
    if cols < TERMINAL_WARN_WIDTH:
        return Check(
            id="terminal",
            title="Terminal size",
            status=WARN,
            detail="{0} columns is very cramped; {1}+ reads much better.".format(
                cols, TERMINAL_WARN_WIDTH
            ),
            fix="Rotate the phone to landscape, or lower the Termux font size "
            "(long-press the screen > Style > Font size).",
        )
    return Check(
        id="terminal",
        title="Terminal size",
        status=PASS,
        detail="{0} columns".format(cols),
    )


def check_disk_space(
    path: Optional[Any] = None,
    usage_fn: Optional[Callable[[str], Any]] = None,
) -> Check:
    """Free disk space - node_modules is brutal on a phone."""
    target = str(path) if path is not None else str(Path.home())
    usage_fn = usage_fn or shutil.disk_usage

    try:
        usage = usage_fn(target)
        free = getattr(usage, "free", None)
        if free is None:
            free = usage[2]
        free_mb = int(free) // _MB
    except Exception as exc:
        return Check(
            id="disk",
            title="Disk space",
            status=WARN,
            detail="Free space could not be determined ({0}).".format(
                exc.__class__.__name__
            ),
            fix="Check available space manually: df -h {0}".format(target),
        )

    if free_mb < DISK_FAIL_MB:
        return Check(
            id="disk",
            title="Disk space",
            status=FAIL,
            detail="Only {0} MB free; {1} MB is the bare minimum.".format(
                free_mb, DISK_FAIL_MB
            ),
            fix="Free up space, then retry: pkg clean && rm -rf ~/.npm ~/.cache/pip",
        )
    if free_mb < DISK_WARN_MB:
        return Check(
            id="disk",
            title="Disk space",
            status=WARN,
            detail="{0} MB free; installs like node_modules want {1} MB+.".format(
                free_mb, DISK_WARN_MB
            ),
            fix="Free up space: pkg clean && rm -rf ~/.npm ~/.cache/pip",
        )
    return Check(
        id="disk",
        title="Disk space",
        status=PASS,
        detail="{0} MB free".format(free_mb),
    )


def check_providers(api_manager: Optional[Any] = None) -> Check:
    """An LLM provider is configured and has a model set.

    Never makes a network call and never puts key material in the report.
    """
    manager = api_manager
    if manager is None:
        try:
            from anyplace.config.api_manager import APIManager

            manager = APIManager()
        except Exception as exc:
            return Check(
                id="providers",
                title="LLM provider",
                status=WARN,
                detail="Provider config could not be read ({0}).".format(
                    exc.__class__.__name__
                ),
                fix="anywhere configure",
            )

    try:
        providers = manager.list_providers() or {}
    except Exception as exc:
        return Check(
            id="providers",
            title="LLM provider",
            status=WARN,
            detail="Provider config could not be read ({0}).".format(
                exc.__class__.__name__
            ),
            fix="anywhere configure",
        )

    names = sorted(str(n) for n in providers.keys())
    if not names:
        return Check(
            id="providers",
            title="LLM provider",
            status=FAIL,
            detail="No LLM provider is configured, so nothing can be generated.",
            fix="anywhere configure",
            critical=True,
        )

    try:
        active = manager.get_active_provider()
    except Exception:
        active = None
    active = str(active).lower() if active else names[0]

    config = None
    try:
        config = manager.get_provider(active)
    except Exception:
        config = None
    if not isinstance(config, dict):
        config = providers.get(active) if isinstance(providers, dict) else None
    if not isinstance(config, dict):
        config = {}

    listed = ", ".join(names)
    model = config.get("model") or ""
    has_key = bool(config.get("api_key"))

    if not has_key:
        return Check(
            id="providers",
            title="LLM provider",
            status=FAIL,
            detail="Provider '{0}' has no API key stored (configured: {1}).".format(
                active, listed
            ),
            fix="anywhere configure",
            critical=True,
        )
    if not model:
        return Check(
            id="providers",
            title="LLM provider",
            status=WARN,
            detail="Provider '{0}' has a key but no model selected.".format(active),
            fix="anywhere configure",
        )
    return Check(
        id="providers",
        title="LLM provider",
        status=PASS,
        detail="{0} configured; active: {1} ({2})".format(len(names), active, model),
    )


def check_network(probe: Optional[Callable[[], Any]] = None) -> Check:
    """Reachability.  A warning, never a failure - offline use is supported."""
    probe = probe or _default_network_probe
    try:
        reachable = probe()
    except Exception as exc:
        return Check(
            id="network",
            title="Network",
            status=WARN,
            detail="Network check failed ({0}). Offline commands still work.".format(
                exc.__class__.__name__
            ),
            fix="Check wifi or mobile data, then retry: anywhere doctor",
        )

    if not reachable:
        return Check(
            id="network",
            title="Network",
            status=WARN,
            detail="No connection to the LLM API. Offline commands still work.",
            fix="Check wifi or mobile data, then retry: anywhere doctor",
        )
    return Check(
        id="network",
        title="Network",
        status=PASS,
        detail="LLM API reachable",
    )


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

#: (check id, module-level function name, human title) in display order.
CHECK_REGISTRY = (
    ("python", "check_python", "Python version"),
    ("git", "check_git", "Git"),
    ("node", "check_node", "Node.js"),
    ("storage", "check_storage", "Storage access"),
    ("path", "check_path_entry", "PATH entry"),
    ("terminal", "check_terminal", "Terminal size"),
    ("disk", "check_disk_space", "Disk space"),
    ("providers", "check_providers", "LLM provider"),
    ("network", "check_network", "Network"),
)

CHECK_IDS = tuple(entry[0] for entry in CHECK_REGISTRY)


def run_all(**overrides: Any) -> DoctorReport:
    """Run every check.  Never raises.

    ``overrides`` is keyed by check id.  A value may be:

    * a ``dict`` - passed as keyword arguments to that check,
    * a ``Check`` - used verbatim (handy for fixtures),
    * a callable - used in place of the check function.

    A check that raises becomes a WARN whose detail names the exception.
    """
    checks: List[Check] = []
    module_globals = globals()

    for check_id, func_name, title in CHECK_REGISTRY:
        override = overrides.get(check_id)
        try:
            if isinstance(override, Check):
                result = override
            else:
                func = override if callable(override) else module_globals[func_name]
                kwargs = override if isinstance(override, dict) else {}
                result = func(**kwargs)
            if not isinstance(result, Check):
                raise TypeError(
                    "{0} returned {1}, expected Check".format(
                        func_name, type(result).__name__
                    )
                )
        except Exception as exc:  # noqa: BLE001 - doctor must never explode
            result = Check(
                id=check_id,
                title=title,
                status=WARN,
                detail="Check crashed: {0}: {1}".format(exc.__class__.__name__, exc),
                fix="Report this at the project issue tracker, then rerun: anywhere doctor",
            )
        checks.append(result)

    return DoctorReport(checks=checks)
