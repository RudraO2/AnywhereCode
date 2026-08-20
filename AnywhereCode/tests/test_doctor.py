"""Tests for anyplace.core.doctor.

Every check is driven purely through injected fakes: no subprocess, no
filesystem outside tmp_path, no network.
"""

import pytest

from anyplace.core import doctor
from anyplace.core.doctor import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    Check,
    DoctorReport,
)

FAKE_KEY = "sk-ant-supersecret-DO-NOT-LEAK-0123456789"


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------


def which_none(_name):
    return None


def which_found(_name):
    return "/usr/bin/" + _name


class FakeAPIManager:
    """Stands in for anyplace.config.api_manager.APIManager."""

    def __init__(self, providers=None, active=None):
        self._providers = providers or {}
        self._active = active

    def list_providers(self):
        return dict(self._providers)

    def get_active_provider(self):
        return self._active

    def get_provider(self, name):
        return self._providers.get(str(name).lower())


class ExplodingAPIManager:
    def list_providers(self):
        raise RuntimeError("config.yaml is shredded")


class FakeUsage(object):
    def __init__(self, free_mb):
        self.total = 8 * 1024 * doctor._MB
        self.used = self.total - free_mb * doctor._MB
        self.free = free_mb * doctor._MB


def usage_with(free_mb):
    return lambda _path: FakeUsage(free_mb)


def report_text(report):
    """Everything the user could ever see, as one string."""
    parts = []
    for check in report.checks:
        parts.extend([check.id, check.title, check.status, check.detail, check.fix])
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Check / DoctorReport
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected", [(PASS, True), (SKIP, True), (WARN, False), (FAIL, False)]
)
def test_check_ok_reflects_status(status, expected):
    assert Check(id="x", title="X", status=status).ok is expected


def test_report_healthy_when_no_failures():
    report = DoctorReport(
        checks=[
            Check(id="a", title="A", status=PASS),
            Check(id="b", title="B", status=WARN, fix="do a thing"),
            Check(id="c", title="C", status=SKIP),
        ]
    )
    assert report.healthy is True


def test_report_unhealthy_when_any_failure():
    report = DoctorReport(
        checks=[
            Check(id="a", title="A", status=PASS),
            Check(id="b", title="B", status=FAIL, fix="fix me"),
        ]
    )
    assert report.healthy is False


def test_report_by_status_returns_only_matching_checks_in_order():
    warn_one = Check(id="a", title="A", status=WARN, fix="f")
    warn_two = Check(id="c", title="C", status=WARN, fix="f")
    report = DoctorReport(
        checks=[warn_one, Check(id="b", title="B", status=PASS), warn_two]
    )
    assert report.by_status(WARN) == [warn_one, warn_two]
    assert report.by_status(FAIL) == []


def test_report_summary_counts_every_status_and_total():
    report = DoctorReport(
        checks=[
            Check(id="a", title="A", status=PASS),
            Check(id="b", title="B", status=PASS),
            Check(id="c", title="C", status=WARN, fix="f"),
            Check(id="d", title="D", status=FAIL, fix="f"),
            Check(id="e", title="E", status=SKIP),
        ]
    )
    summary = report.summary()
    assert summary[PASS] == 2
    assert summary[WARN] == 1
    assert summary[FAIL] == 1
    assert summary[SKIP] == 1
    assert summary["total"] == 5


def test_report_summary_of_empty_report_is_all_zero():
    summary = DoctorReport(checks=[]).summary()
    assert summary == {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0, "total": 0}


def test_report_blockers_only_lists_critical_failures():
    critical = Check(id="a", title="A", status=FAIL, fix="f", critical=True)
    report = DoctorReport(
        checks=[critical, Check(id="b", title="B", status=FAIL, fix="f")]
    )
    assert report.blockers == [critical]


def test_report_get_returns_check_or_none():
    check = Check(id="python", title="Python", status=PASS)
    report = DoctorReport(checks=[check])
    assert report.get("python") is check
    assert report.get("nope") is None


# --------------------------------------------------------------------------
# check_python
# --------------------------------------------------------------------------


def test_check_python_passes_on_modern_version():
    check = doctor.check_python(version_info=(3, 11, 5))
    assert check.status == PASS
    assert check.id == "python"
    assert "3.11.5" in check.detail


def test_check_python_passes_with_note_on_38():
    check = doctor.check_python(version_info=(3, 8, 10))
    assert check.status == PASS
    assert "3.9" in check.detail


def test_check_python_fails_below_minimum():
    check = doctor.check_python(version_info=(3, 7, 9))
    assert check.status == FAIL
    assert check.critical is True
    assert check.fix


def test_check_python_uses_real_interpreter_by_default():
    # The test suite itself runs on a supported interpreter.
    assert doctor.check_python().status == PASS


# --------------------------------------------------------------------------
# check_git
# --------------------------------------------------------------------------


def test_check_git_passes_when_installed():
    check = doctor.check_git(
        which=which_found, run=lambda a: "git version 2.39.2", termux=False
    )
    assert check.status == PASS
    assert check.id == "git"
    assert "2.39.2" in check.detail


def test_check_git_fails_when_missing_with_termux_fix():
    check = doctor.check_git(which=which_none, termux=True)
    assert check.status == FAIL
    assert check.fix == "pkg install git"


def test_check_git_fails_when_missing_with_desktop_fix():
    check = doctor.check_git(which=which_none, termux=False, system="Linux")
    assert check.status == FAIL
    assert "apt install git" in check.fix
    assert "pkg install" not in check.fix


def test_check_git_fix_is_brew_on_macos():
    check = doctor.check_git(which=which_none, termux=False, system="Darwin")
    assert "brew install git" in check.fix


def test_check_git_warns_when_version_command_fails():
    def boom(_args):
        raise OSError("no exec")

    check = doctor.check_git(which=which_found, run=boom, termux=True)
    assert check.status == WARN
    assert check.fix


def test_check_git_warns_when_version_unparseable():
    check = doctor.check_git(
        which=which_found, run=lambda a: "git version unknown", termux=False
    )
    assert check.status == WARN
    assert check.fix


def test_check_git_warns_on_ancient_version():
    check = doctor.check_git(
        which=which_found, run=lambda a: "git version 1.8.3", termux=False
    )
    assert check.status == WARN
    assert check.fix


# --------------------------------------------------------------------------
# check_node
# --------------------------------------------------------------------------


def test_check_node_passes_on_modern_version():
    check = doctor.check_node(
        which=which_found, run=lambda a: "v20.11.0", termux=False
    )
    assert check.status == PASS
    assert check.id == "node"


def test_check_node_warns_not_fails_when_missing():
    check = doctor.check_node(which=which_none, termux=True)
    assert check.status == WARN
    assert check.critical is False
    assert check.fix == "pkg install nodejs"


def test_check_node_missing_fix_is_platform_specific_off_termux():
    check = doctor.check_node(which=which_none, termux=False, system="Linux")
    assert "apt install nodejs" in check.fix


def test_check_node_warns_on_old_major():
    check = doctor.check_node(
        which=which_found, run=lambda a: "v14.21.3", termux=False, min_major=18
    )
    assert check.status == WARN
    assert check.fix


def test_check_node_warns_when_version_command_fails():
    def boom(_args):
        raise OSError("nope")

    check = doctor.check_node(which=which_found, run=boom, termux=False)
    assert check.status == WARN
    assert check.fix


# --------------------------------------------------------------------------
# check_storage
# --------------------------------------------------------------------------


def test_check_storage_passes_on_termux_with_storage_linked(tmp_path):
    (tmp_path / "storage" / "downloads").mkdir(parents=True)
    check = doctor.check_storage(
        home=tmp_path, termux=True, writable=lambda p: True
    )
    assert check.status == PASS
    assert check.id == "storage"


def test_check_storage_fails_on_termux_without_setup_storage(tmp_path):
    check = doctor.check_storage(
        home=tmp_path, termux=True, writable=lambda p: True
    )
    assert check.status == FAIL
    assert check.fix.startswith("termux-setup-storage")


def test_check_storage_fails_on_termux_when_not_writable(tmp_path):
    (tmp_path / "storage" / "downloads").mkdir(parents=True)
    check = doctor.check_storage(
        home=tmp_path, termux=True, writable=lambda p: False
    )
    assert check.status == FAIL
    assert "termux-setup-storage" in check.fix


def test_check_storage_passes_on_desktop_when_writable(tmp_path):
    check = doctor.check_storage(
        home=tmp_path, termux=False, writable=lambda p: True
    )
    assert check.status == PASS
    assert ".anyplace" in check.detail


def test_check_storage_fails_on_desktop_when_not_writable(tmp_path):
    check = doctor.check_storage(
        home=tmp_path, termux=False, writable=lambda p: False
    )
    assert check.status == FAIL
    assert check.fix


def test_check_storage_actually_tests_writability_not_existence(tmp_path):
    """The default writability probe must write, not just stat."""
    target = tmp_path / "projects"
    target.mkdir()
    assert doctor._default_writable(target) is True
    # nothing left behind
    assert list(target.iterdir()) == []


def test_default_writable_walks_up_to_existing_ancestor(tmp_path):
    assert doctor._default_writable(tmp_path / "a" / "b" / "c") is True


def test_default_writable_false_for_unwritable_location():
    assert doctor._default_writable("/proc/definitely/not/here") is False


def test_check_storage_uses_injected_projects_dir(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    check = doctor.check_storage(
        home=tmp_path, termux=False, projects_dir=custom, writable=lambda p: True
    )
    assert str(custom) in check.detail


# --------------------------------------------------------------------------
# check_path_entry
# --------------------------------------------------------------------------


def test_check_path_entry_passes_when_local_bin_present(tmp_path):
    path_env = "/usr/bin:{0}/.local/bin:/bin".format(tmp_path)
    check = doctor.check_path_entry(path_env=path_env, home=tmp_path)
    assert check.status == PASS
    assert check.id == "path"


def test_check_path_entry_warns_when_missing(tmp_path):
    check = doctor.check_path_entry(path_env="/usr/bin:/bin", home=tmp_path)
    assert check.status == WARN
    assert check.critical is False
    assert 'export PATH="$HOME/.local/bin:$PATH"' in check.fix


def test_check_path_entry_fix_names_bashrc_for_bash(tmp_path):
    check = doctor.check_path_entry(
        path_env="/usr/bin", home=tmp_path, shell="/data/data/com.termux/files/usr/bin/bash"
    )
    assert "~/.bashrc" in check.fix


def test_check_path_entry_fix_names_zshrc_for_zsh(tmp_path):
    check = doctor.check_path_entry(path_env="/usr/bin", home=tmp_path, shell="/bin/zsh")
    assert "~/.zshrc" in check.fix


def test_check_path_entry_fix_uses_fish_syntax_for_fish(tmp_path):
    check = doctor.check_path_entry(
        path_env="/usr/bin", home=tmp_path, shell="/usr/bin/fish"
    )
    assert "fish_add_path" in check.fix
    assert "config.fish" in check.fix


def test_check_path_entry_falls_back_to_profile_for_unknown_shell(tmp_path):
    check = doctor.check_path_entry(path_env="/usr/bin", home=tmp_path, shell="")
    assert "~/.profile" in check.fix


def test_check_path_entry_handles_empty_path_env(tmp_path):
    check = doctor.check_path_entry(path_env="", home=tmp_path)
    assert check.status == WARN
    assert check.fix


def test_check_path_entry_normalizes_trailing_slash(tmp_path):
    path_env = "{0}/.local/bin/".format(tmp_path)
    check = doctor.check_path_entry(path_env=path_env, home=tmp_path)
    assert check.status == PASS


# --------------------------------------------------------------------------
# check_terminal (boundary tests at the exact cutoffs)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("width", [1, 20, 24])
def test_check_terminal_fails_below_25_columns(width):
    check = doctor.check_terminal(width=width)
    assert check.status == FAIL
    assert check.fix


def test_check_terminal_warns_exactly_at_25():
    assert doctor.check_terminal(width=25).status == WARN


def test_check_terminal_warns_exactly_at_31():
    assert doctor.check_terminal(width=31).status == WARN


def test_check_terminal_passes_exactly_at_32():
    check = doctor.check_terminal(width=32)
    assert check.status == PASS
    assert check.id == "terminal"


@pytest.mark.parametrize("width", [40, 60, 80, 120])
def test_check_terminal_passes_on_roomy_widths(width):
    assert doctor.check_terminal(width=width).status == PASS


def test_check_terminal_warn_fix_mentions_rotating_or_font():
    check = doctor.check_terminal(width=28)
    assert "landscape" in check.fix or "font" in check.fix


def test_check_terminal_warns_on_unusable_width_value():
    check = doctor.check_terminal(width="wide")
    assert check.status == WARN
    assert check.fix


# --------------------------------------------------------------------------
# check_disk_space (boundary tests at the exact cutoffs)
# --------------------------------------------------------------------------


def test_check_disk_space_fails_below_100mb():
    check = doctor.check_disk_space(path="/x", usage_fn=usage_with(99))
    assert check.status == FAIL
    assert check.fix


def test_check_disk_space_warns_exactly_at_100mb():
    assert doctor.check_disk_space(path="/x", usage_fn=usage_with(100)).status == WARN


def test_check_disk_space_warns_exactly_at_499mb():
    assert doctor.check_disk_space(path="/x", usage_fn=usage_with(499)).status == WARN


def test_check_disk_space_passes_exactly_at_500mb():
    check = doctor.check_disk_space(path="/x", usage_fn=usage_with(500))
    assert check.status == PASS
    assert check.id == "disk"


def test_check_disk_space_passes_with_plenty_free():
    check = doctor.check_disk_space(path="/x", usage_fn=usage_with(20000))
    assert check.status == PASS
    assert "20000 MB" in check.detail


def test_check_disk_space_accepts_tuple_style_usage():
    check = doctor.check_disk_space(path="/x", usage_fn=lambda p: (0, 0, 800 * doctor._MB))
    assert check.status == PASS


def test_check_disk_space_warns_when_usage_fn_raises():
    def boom(_path):
        raise OSError("statvfs failed")

    check = doctor.check_disk_space(path="/x", usage_fn=boom)
    assert check.status == WARN
    assert check.fix


# --------------------------------------------------------------------------
# check_providers
# --------------------------------------------------------------------------


def test_check_providers_passes_when_configured():
    manager = FakeAPIManager(
        providers={"claude": {"api_key": FAKE_KEY, "model": "claude-3-5-sonnet"}},
        active="claude",
    )
    check = doctor.check_providers(api_manager=manager)
    assert check.status == PASS
    assert check.id == "providers"
    assert "claude-3-5-sonnet" in check.detail


def test_check_providers_fails_when_none_configured():
    check = doctor.check_providers(api_manager=FakeAPIManager(providers={}))
    assert check.status == FAIL
    assert check.critical is True
    # The fix has to be a command the user can actually type -- this used to
    # read `anyplace --configure`, a flag that never existed. See
    # tests/test_command_hints_are_real.py for the sweep that keeps it honest.
    assert check.fix == "anywhere configure"


def test_check_providers_warns_when_model_missing():
    manager = FakeAPIManager(
        providers={"gemini": {"api_key": FAKE_KEY, "model": ""}}, active="gemini"
    )
    check = doctor.check_providers(api_manager=manager)
    assert check.status == WARN
    assert check.fix


def test_check_providers_fails_when_key_missing():
    manager = FakeAPIManager(
        providers={"gemini": {"api_key": "", "model": "gemini-2.0"}}, active="gemini"
    )
    check = doctor.check_providers(api_manager=manager)
    assert check.status == FAIL
    assert check.fix


def test_check_providers_falls_back_to_first_provider_when_no_active():
    manager = FakeAPIManager(
        providers={"claude": {"api_key": FAKE_KEY, "model": "m1"}}, active=None
    )
    check = doctor.check_providers(api_manager=manager)
    assert check.status == PASS
    assert "claude" in check.detail


def test_check_providers_warns_when_manager_raises():
    check = doctor.check_providers(api_manager=ExplodingAPIManager())
    assert check.status == WARN
    assert check.fix


def test_check_providers_never_leaks_api_key():
    manager = FakeAPIManager(
        providers={"claude": {"api_key": FAKE_KEY, "model": "claude-3-5-sonnet"}},
        active="claude",
    )
    check = doctor.check_providers(api_manager=manager)
    blob = " ".join([check.detail, check.fix, check.title, check.id])
    assert FAKE_KEY not in blob
    assert "supersecret" not in blob


def test_check_providers_never_leaks_key_even_when_model_missing():
    manager = FakeAPIManager(
        providers={"claude": {"api_key": FAKE_KEY, "model": ""}}, active="claude"
    )
    check = doctor.check_providers(api_manager=manager)
    assert FAKE_KEY not in (check.detail + check.fix)


# --------------------------------------------------------------------------
# check_network
# --------------------------------------------------------------------------


def test_check_network_passes_when_probe_true():
    check = doctor.check_network(probe=lambda: True)
    assert check.status == PASS
    assert check.id == "network"


def test_check_network_warns_not_fails_when_probe_false():
    check = doctor.check_network(probe=lambda: False)
    assert check.status == WARN
    assert check.critical is False
    assert check.fix


def test_check_network_warns_when_probe_raises():
    def boom():
        raise OSError("dns")

    check = doctor.check_network(probe=boom)
    assert check.status == WARN
    assert check.fix


# --------------------------------------------------------------------------
# run_all
# --------------------------------------------------------------------------


def healthy_overrides(tmp_path):
    (tmp_path / "storage" / "downloads").mkdir(parents=True)
    return {
        "python": {"version_info": (3, 11, 5)},
        "git": {"which": which_found, "run": lambda a: "git version 2.40.0", "termux": True},
        "node": {"which": which_found, "run": lambda a: "v20.0.0", "termux": True},
        "storage": {"home": tmp_path, "termux": True, "writable": lambda p: True},
        "path": {"path_env": "{0}/.local/bin".format(tmp_path), "home": tmp_path},
        "terminal": {"width": 45},
        "disk": {"path": str(tmp_path), "usage_fn": usage_with(4000)},
        "providers": {
            "api_manager": FakeAPIManager(
                providers={"claude": {"api_key": FAKE_KEY, "model": "sonnet"}},
                active="claude",
            )
        },
        "network": {"probe": lambda: True},
    }


def test_run_all_returns_one_check_per_registered_id(tmp_path):
    report = doctor.run_all(**healthy_overrides(tmp_path))
    assert [c.id for c in report.checks] == list(doctor.CHECK_IDS)


def test_run_all_healthy_environment_reports_healthy(tmp_path):
    report = doctor.run_all(**healthy_overrides(tmp_path))
    assert report.healthy is True
    assert report.summary()[FAIL] == 0
    assert report.summary()["total"] == len(doctor.CHECK_IDS)


def test_run_all_hostile_environment_reports_failures(tmp_path):
    overrides = healthy_overrides(tmp_path)
    overrides["git"] = {"which": which_none, "termux": True}
    overrides["node"] = {"which": which_none, "termux": True}
    overrides["terminal"] = {"width": 20}
    overrides["disk"] = {"path": str(tmp_path), "usage_fn": usage_with(50)}
    overrides["providers"] = {"api_manager": FakeAPIManager(providers={})}
    report = doctor.run_all(**overrides)

    assert report.healthy is False
    assert report.get("git").status == FAIL
    assert report.get("node").status == WARN
    assert report.get("terminal").status == FAIL
    assert report.get("disk").status == FAIL
    assert report.get("providers").status == FAIL
    assert [c.id for c in report.blockers] == ["providers"]


def test_run_all_every_non_passing_check_has_a_fix(tmp_path):
    overrides = healthy_overrides(tmp_path)
    overrides["git"] = {"which": which_none, "termux": True}
    overrides["node"] = {"which": which_none, "termux": True}
    overrides["terminal"] = {"width": 20}
    overrides["disk"] = {"path": str(tmp_path), "usage_fn": usage_with(10)}
    overrides["providers"] = {"api_manager": FakeAPIManager(providers={})}
    overrides["network"] = {"probe": lambda: False}
    overrides["path"] = {"path_env": "/usr/bin", "home": tmp_path}
    report = doctor.run_all(**overrides)

    non_passing = report.by_status(WARN) + report.by_status(FAIL)
    assert non_passing, "expected this environment to have problems"
    for check in non_passing:
        assert check.fix.strip(), "check {0} has no fix text".format(check.id)


def test_run_all_never_leaks_api_key_material(tmp_path):
    report = doctor.run_all(**healthy_overrides(tmp_path))
    assert FAKE_KEY not in report_text(report)
    assert "supersecret" not in report_text(report)


def test_run_all_survives_a_check_that_raises(tmp_path, monkeypatch):
    def exploding_check(**_kwargs):
        raise RuntimeError("git check imploded")

    monkeypatch.setattr(doctor, "check_git", exploding_check)
    report = doctor.run_all(**healthy_overrides(tmp_path))

    crashed = report.get("git")
    assert crashed.status == WARN
    assert "RuntimeError" in crashed.detail
    assert "git check imploded" in crashed.detail
    assert crashed.fix
    assert len(report.checks) == len(doctor.CHECK_IDS)


def test_run_all_survives_a_check_returning_the_wrong_type(tmp_path):
    overrides = healthy_overrides(tmp_path)
    overrides["network"] = lambda: "not a check"
    report = doctor.run_all(**overrides)
    assert report.get("network").status == WARN
    assert "TypeError" in report.get("network").detail


def test_run_all_accepts_a_prebuilt_check_override(tmp_path):
    overrides = healthy_overrides(tmp_path)
    overrides["network"] = Check(id="network", title="Network", status=SKIP, detail="offline mode")
    report = doctor.run_all(**overrides)
    assert report.get("network").status == SKIP
    assert report.healthy is True


def test_run_all_ignores_unknown_override_keys(tmp_path):
    overrides = healthy_overrides(tmp_path)
    overrides["not_a_check"] = {"whatever": 1}
    report = doctor.run_all(**overrides)
    assert [c.id for c in report.checks] == list(doctor.CHECK_IDS)


def test_run_all_check_ids_are_unique():
    assert len(set(doctor.CHECK_IDS)) == len(doctor.CHECK_IDS)


def test_run_all_produces_only_known_statuses(tmp_path):
    report = doctor.run_all(**healthy_overrides(tmp_path))
    for check in report.checks:
        assert check.status in doctor.STATUSES


def test_doctor_module_imports_no_ui_or_cli_dependencies():
    source = open(doctor.__file__, "r").read()
    assert "import rich" not in source
    assert "import click" not in source
    assert "from anyplace.cli" not in source
    assert "from anyplace.ui" not in source


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("git version 2.39.2", (2, 39, 2)),
        ("v20.11.0", (20, 11, 0)),
        ("nonsense", ()),
        ("", ()),
    ],
)
def test_parse_version_extracts_numbers(text, expected):
    assert doctor._parse_version(text) == expected


def test_install_fix_prefers_pkg_on_termux():
    assert doctor._install_fix("git", termux=True) == "pkg install git"


def test_install_fix_uses_apt_on_linux():
    assert "apt install git" in doctor._install_fix("git", termux=False, system="Linux")
