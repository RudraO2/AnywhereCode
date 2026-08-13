"""
Tests for the EAS cloud-build path and the OmniRoute provider.

Everything here runs offline: no eas-cli, no network, no API keys. The
subprocess boundary is faked so the config-repair and output-parsing logic —
the parts that actually break in the field — are covered.

Run with: python3 test_eas.py
"""

import json
import sys
import tempfile
from pathlib import Path

from anyplace.core.eas_builder import EASBuilder, sanitize_package_name
from anyplace.cli import qr
from anyplace.cli.error_handler import validate_api_key


PASSED = []
FAILED = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASSED.append(name)
        print(f"  ✅ {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


def make_expo_project(tmp: Path) -> Path:
    """Create a minimal directory that reads as an Expo project."""
    project = tmp / "my cool app"
    project.mkdir(parents=True, exist_ok=True)
    (project / "package.json").write_text(json.dumps({
        "name": "mycoolapp",
        "dependencies": {"expo": "~52.0.0", "react-native": "0.76.0"},
    }))
    return project


def test_package_name_sanitizing():
    print("\n[1] Android package name derivation")
    check("strips spaces and punctuation",
          sanitize_package_name("my cool app!") == "com.anyplace.mycoolapp",
          sanitize_package_name("my cool app!"))
    check("prefixes leading digits (invalid in Android ids)",
          sanitize_package_name("2048") == "com.anyplace.app2048",
          sanitize_package_name("2048"))
    check("handles an all-punctuation name",
          sanitize_package_name("---") == "com.anyplace.app",
          sanitize_package_name("---"))
    check("every segment starts with a letter",
          all(seg[0].isalpha() for seg in sanitize_package_name("9lives").split(".")),
          sanitize_package_name("9lives"))


def test_project_detection():
    print("\n[2] Expo project detection")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        project = make_expo_project(tmp)
        check("detects an Expo project", EASBuilder(project).is_expo_project())

        plain = tmp / "plain"
        plain.mkdir()
        (plain / "package.json").write_text(json.dumps({"dependencies": {"react": "18"}}))
        check("rejects a non-Expo Node project", not EASBuilder(plain).is_expo_project())

        empty = tmp / "empty"
        empty.mkdir()
        check("rejects a directory with no package.json",
              not EASBuilder(empty).is_expo_project())


def test_app_config_repair():
    print("\n[3] app.json repair")
    with tempfile.TemporaryDirectory() as tmpdir:
        project = make_expo_project(Path(tmpdir))
        builder = EASBuilder(project)

        written = builder.ensure_app_config("my cool app")
        check("writes app.json when missing", len(written) == 1, str(written))

        config = json.loads((project / "app.json").read_text())["expo"]
        check("sets android.package",
              config["android"]["package"] == "com.anyplace.mycoolapp",
              config.get("android", {}).get("package", "<missing>"))
        check("sets a version", config.get("version") == "1.0.0", config.get("version"))
        check("sets a slug", bool(config.get("slug")), config.get("slug"))

        # Second run must be a no-op, otherwise every build dirties git.
        check("is idempotent", builder.ensure_app_config("my cool app") == [])

        # A user-chosen package must survive.
        config_path = project / "app.json"
        data = json.loads(config_path.read_text())
        data["expo"]["android"]["package"] = "com.example.mine"
        config_path.write_text(json.dumps(data))
        builder.ensure_app_config("my cool app")
        kept = json.loads(config_path.read_text())["expo"]["android"]["package"]
        check("preserves an existing package name", kept == "com.example.mine", kept)


def test_eas_json():
    print("\n[4] eas.json generation")
    with tempfile.TemporaryDirectory() as tmpdir:
        project = make_expo_project(Path(tmpdir))
        builder = EASBuilder(project)

        builder.ensure_eas_json()
        config = json.loads((project / "eas.json").read_text())

        # The single most important assertion in this file: a preview build
        # must be an APK, because an AAB cannot be sideloaded onto a phone.
        check("preview profile builds an APK",
              config["build"]["preview"]["android"]["buildType"] == "apk",
              json.dumps(config["build"]["preview"]))
        check("production profile builds an AAB for the Play Store",
              config["build"]["production"]["android"]["buildType"] == "app-bundle",
              json.dumps(config["build"]["production"]))
        check("sets appVersionSource so non-interactive builds don't prompt",
              config["cli"].get("appVersionSource") == "remote",
              json.dumps(config["cli"]))
        check("is idempotent", builder.ensure_eas_json() == [])

        # Merging must not clobber a user's own profile.
        config["build"]["preview"]["android"]["buildType"] = "app-bundle"
        config["build"]["staging"] = {"distribution": "internal"}
        (project / "eas.json").write_text(json.dumps(config))
        builder.ensure_eas_json()
        merged = json.loads((project / "eas.json").read_text())
        check("keeps a user's custom profile",
              "staging" in merged["build"], list(merged["build"]))
        check("does not override a user's explicit buildType",
              merged["build"]["preview"]["android"]["buildType"] == "app-bundle",
              merged["build"]["preview"]["android"]["buildType"])


def test_build_json_parsing():
    print("\n[5] eas-cli output parsing")
    with tempfile.TemporaryDirectory() as tmpdir:
        builder = EASBuilder(make_expo_project(Path(tmpdir)))

        check("parses a bare object",
              builder._parse_build_json('{"id": "abc", "status": "IN_QUEUE"}')["id"] == "abc")

        check("unwraps a single-element array",
              builder._parse_build_json('[{"id": "xyz"}]')["id"] == "xyz")

        noisy = 'Uploading to EAS Build...\n✔ Compressed\n{"id": "n1", "status": "NEW"}\n'
        parsed = builder._parse_build_json(noisy)
        check("skips progress lines before the JSON",
              parsed is not None and parsed["id"] == "n1", str(parsed))

        check("returns None on garbage", builder._parse_build_json("not json at all") is None)
        check("returns None on empty output", builder._parse_build_json("") is None)

        check("reads applicationArchiveUrl",
              EASBuilder._artifact_url(
                  {"artifacts": {"applicationArchiveUrl": "https://x/app.apk"}}
              ) == "https://x/app.apk")
        check("falls back to buildUrl",
              EASBuilder._artifact_url({"artifacts": {"buildUrl": "https://x/b"}}) == "https://x/b")
        check("returns empty string when there is no artifact",
              EASBuilder._artifact_url({}) == "")


def test_preflight():
    print("\n[6] Preflight checks")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plain = tmp / "plain"
        plain.mkdir()
        (plain / "package.json").write_text('{"dependencies": {}}')

        problems = EASBuilder(plain, expo_token="fake").preflight()
        check("rejects a non-Expo project",
              any("Expo project" in p for p in problems), str(problems))

        # build_apk must refuse before touching the network.
        result = EASBuilder(plain, expo_token="fake").build_apk()
        check("build_apk fails closed without running eas-cli",
              not result.success and "Expo project" in result.error, result.error)


def test_qr():
    print("\n[7] Terminal QR rendering")
    if not qr.is_available():
        print("  ○ skipped — `qrcode` not installed")
        return

    rendered = qr.render("https://expo.dev/artifacts/eas/example.apk")
    check("renders something", bool(rendered))
    lines = rendered.splitlines()
    check("uses half-block characters", any(c in rendered for c in "▀▄█"))
    check("is roughly square (half-height rows)",
          len(lines) * 2 >= len(lines[0]) * 0.8, f"{len(lines)} rows x {len(lines[0])} cols")
    check("every row is the same width", len({len(l) for l in lines}) == 1)


def test_omniroute_provider():
    print("\n[8] OmniRoute provider wiring")
    from anyplace.core.llm_provider import (
        OMNIROUTE_DEFAULT_URL,
        OMNIROUTE_DEFAULT_MODEL,
        KEYLESS_PROVIDERS,
    )
    from anyplace.cli.config_wizard import PROVIDERS

    check("omniroute is keyless", "omniroute" in KEYLESS_PROVIDERS)
    check("an empty key validates for omniroute", validate_api_key("", "omniroute"))
    check("an empty key still fails for claude", not validate_api_key("", "claude"))
    check("defaults to the auto router", OMNIROUTE_DEFAULT_MODEL == "auto")
    check("defaults to the documented port", "20128" in OMNIROUTE_DEFAULT_URL)

    check("omniroute is offered in the wizard", "omniroute" in PROVIDERS)
    check("omniroute is listed first for new users",
          list(PROVIDERS)[0] == "omniroute", list(PROVIDERS)[0])
    check("openrouter offers free models",
          any(":free" in m for m, _ in PROVIDERS["openrouter"]["models"]))

    # A keyless provider must construct without raising.
    from anyplace.core.llm_provider import LLMProvider

    class FakeManager:
        def get_active_provider(self):
            return "omniroute"

        def get_active_config(self):
            return {"api_key": "", "model": "auto"}

    provider = LLMProvider(FakeManager())
    check("builds a client with no API key",
          provider.base_url == OMNIROUTE_DEFAULT_URL and provider.model == "auto",
          f"{provider.base_url} / {provider.model}")


def main():
    print("=" * 62)
    print("  AnywhereCode — EAS + OmniRoute tests")
    print("=" * 62)

    test_package_name_sanitizing()
    test_project_detection()
    test_app_config_repair()
    test_eas_json()
    test_build_json_parsing()
    test_preflight()
    test_qr()
    test_omniroute_provider()

    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    print("=" * 62)

    if FAILED:
        for failure in FAILED:
            print(f"  ❌ {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
