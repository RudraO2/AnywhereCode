"""
EAS cloud builds — turn an Expo project into an installable Android APK
without a laptop, without Android Studio, without Gradle running locally.

The whole point: Gradle cannot realistically run inside Termux on a phone.
EAS (Expo Application Services) runs the Gradle build on Expo's servers and
hands back a download URL. So the phone only ever does two cheap things —
upload the source, download the APK.

This module handles the parts that normally make that flow fail:

1. `eas.json` defaults to an **AAB** for Android, which cannot be sideloaded.
   We force `buildType: "apk"` on the preview profile so the artifact is
   something you can actually tap and install.
2. Android builds require `android.package`. Without it eas-cli stops and
   asks a question, which deadlocks a `--non-interactive` run. We derive a
   valid package name up front.
3. The very first Android build needs a signing keystore, and eas-cli
   refuses to generate one in `--non-interactive` mode. We detect that
   specific failure and transparently retry attached to the terminal.
"""

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from anyplace.cli.error_handler import GenerationError


# Terminal states reported by `eas build:view --json`
_TERMINAL_STATES = {"FINISHED", "ERRORED", "CANCELED"}

# Polling cadence for a cloud build. Android builds typically land in
# 8-20 minutes; the queue can add more on the free tier.
_POLL_INTERVAL_SECONDS = 20
_POLL_TIMEOUT_SECONDS = 60 * 60


@dataclass
class BuildResult:
    """Outcome of one EAS cloud build."""

    success: bool
    status: str = ""
    build_id: str = ""
    artifact_url: str = ""
    logs_url: str = ""
    error: str = ""
    files_written: List[str] = field(default_factory=list)

    @property
    def is_installable(self) -> bool:
        """True when we have an artifact a phone can actually install."""
        return self.success and self.artifact_url.endswith(".apk")


def sanitize_package_name(project_name: str, prefix: str = "com.anyplace") -> str:
    """
    Derive a valid Android application id from a project name.

    Android requires each dot-separated segment to start with a letter and
    contain only letters, digits and underscores, with at least two segments.

        "my cool app!"  -> "com.anyplace.mycoolapp"
        "2048"          -> "com.anyplace.app2048"
    """
    slug = re.sub(r"[^a-zA-Z0-9]", "", project_name).lower()
    if not slug:
        slug = "app"
    if not slug[0].isalpha():
        slug = f"app{slug}"
    return f"{prefix}.{slug}"


class EASBuilder:
    """Drives Expo Application Services builds for a project directory."""

    def __init__(
        self,
        project_dir: Path,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        expo_token: Optional[str] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.progress_callback = progress_callback
        self.expo_token = expo_token or os.environ.get("EXPO_TOKEN", "")

    # ── plumbing ────────────────────────────────────────────────────────

    def _report(self, step: str, message: str):
        if self.progress_callback:
            self.progress_callback(step, message)

    def _env(self) -> Dict[str, str]:
        """Subprocess environment, with EXPO_TOKEN injected when we have one."""
        env = os.environ.copy()
        if self.expo_token:
            env["EXPO_TOKEN"] = self.expo_token
        # Stop eas-cli from emitting spinner escape codes into captured output.
        env.setdefault("CI", "1")
        return env

    def eas_command(self) -> List[str]:
        """
        Return the command prefix used to invoke eas-cli.

        Prefers a globally installed `eas` binary; falls back to `npx`, which
        downloads eas-cli on demand. On Termux the npx path is the common one.
        """
        if shutil.which("eas"):
            return ["eas"]
        return ["npx", "--yes", "eas-cli@latest"]

    def _run(
        self,
        args: List[str],
        capture: bool = True,
        timeout: int = 1800,
    ) -> subprocess.CompletedProcess:
        """Run an eas-cli subcommand inside the project directory."""
        cmd = self.eas_command() + args
        return subprocess.run(
            cmd,
            cwd=self.project_dir,
            env=self._env(),
            capture_output=capture,
            text=True,
            timeout=timeout,
        )

    # ── preflight ───────────────────────────────────────────────────────

    def is_expo_project(self) -> bool:
        """True when this directory looks like an Expo/React Native app."""
        pkg_path = self.project_dir / "package.json"
        if not pkg_path.exists():
            return False
        try:
            pkg = json.loads(pkg_path.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        return "expo" in deps

    def is_logged_in(self) -> bool:
        """Check whether eas-cli has usable credentials."""
        try:
            result = self._run(["whoami"], timeout=120)
        except (subprocess.SubprocessError, OSError):
            return False
        # `eas whoami` exits non-zero and prints "Not logged in" when anonymous.
        return result.returncode == 0 and "not logged in" not in (
            result.stdout or ""
        ).lower()

    def preflight(self) -> List[str]:
        """
        Return a list of blocking problems, empty when ready to build.

        Checked here rather than mid-build so the user learns about a missing
        login before waiting on an upload.
        """
        problems: List[str] = []

        if not self.is_expo_project():
            problems.append(
                "Not an Expo project (no `expo` dependency in package.json). "
                "EAS builds only work for Expo / React Native apps."
            )

        if not shutil.which("node"):
            problems.append(
                "Node.js is not installed. On Termux run: pkg install nodejs"
            )

        if not self.expo_token and not self.is_logged_in():
            problems.append(
                "Not signed in to Expo. Either:\n"
                "  • run `anyplace login-expo` and paste an access token from\n"
                "    https://expo.dev/settings/access-tokens  (best on a phone), or\n"
                "  • run `npx eas-cli login` to sign in interactively."
            )

        return problems

    # ── config repair ───────────────────────────────────────────────────

    def ensure_app_config(self, project_name: Optional[str] = None) -> List[str]:
        """
        Make sure app.json carries the fields an Android build requires.

        Only app.json is patched. A project using app.config.js/ts owns its
        own config generation, so we leave it alone and let eas-cli validate.

        Returns:
            List of files written (empty when nothing needed changing).
        """
        if (self.project_dir / "app.config.js").exists() or (
            self.project_dir / "app.config.ts"
        ).exists():
            self._report(
                "config",
                "app.config.js detected — skipping auto-patch, make sure "
                "android.package is set there",
            )
            return []

        app_json_path = self.project_dir / "app.json"
        name = project_name or self.project_dir.name

        if app_json_path.exists():
            try:
                config = json.loads(app_json_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                raise GenerationError(f"Can't parse app.json: {e}")
        else:
            config = {}

        expo = config.setdefault("expo", {})
        changed = False

        if not expo.get("name"):
            expo["name"] = name
            changed = True
        if not expo.get("slug"):
            expo["slug"] = re.sub(r"[^a-zA-Z0-9-]", "-", name).strip("-").lower() or "app"
            changed = True
        if not expo.get("version"):
            expo["version"] = "1.0.0"
            changed = True

        android = expo.setdefault("android", {})
        if not android.get("package"):
            android["package"] = sanitize_package_name(name)
            changed = True
            self._report("config", f"Set android.package = {android['package']}")

        if not changed:
            return []

        app_json_path.write_text(json.dumps(config, indent=2) + "\n")
        return [str(app_json_path)]

    def ensure_eas_json(self) -> List[str]:
        """
        Write or patch eas.json so the preview profile produces an APK.

        An existing eas.json is merged into, never overwritten — a user who
        tuned their own profiles keeps them. We only fill in what is missing.
        """
        eas_path = self.project_dir / "eas.json"

        if eas_path.exists():
            try:
                config = json.loads(eas_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                raise GenerationError(f"Can't parse eas.json: {e}")
        else:
            config = {}

        before = json.dumps(config, sort_keys=True)

        cli = config.setdefault("cli", {})
        cli.setdefault("version", ">= 5.0.0")
        # Without this eas-cli asks how versions should be managed, which
        # hangs a non-interactive build.
        cli.setdefault("appVersionSource", "remote")

        build = config.setdefault("build", {})

        development = build.setdefault("development", {})
        development.setdefault("developmentClient", True)
        development.setdefault("distribution", "internal")
        development.setdefault("android", {}).setdefault("buildType", "apk")

        # The profile that matters: an internally-distributed APK you can
        # download and sideload straight onto the phone that built it.
        preview = build.setdefault("preview", {})
        preview.setdefault("distribution", "internal")
        preview.setdefault("android", {}).setdefault("buildType", "apk")

        production = build.setdefault("production", {})
        production.setdefault("autoIncrement", True)
        # Play Store wants an app bundle, not an APK.
        production.setdefault("android", {}).setdefault("buildType", "app-bundle")

        config.setdefault("submit", {}).setdefault("production", {})

        if json.dumps(config, sort_keys=True) == before:
            return []

        eas_path.write_text(json.dumps(config, indent=2) + "\n")
        return [str(eas_path)]

    # ── building ────────────────────────────────────────────────────────

    def _parse_build_json(self, stdout: str) -> Optional[Dict]:
        """
        Pull the build object out of eas-cli JSON output.

        eas-cli sometimes prefixes JSON with progress lines, and returns
        either a bare object or a single-element array.
        """
        candidates = []
        stripped = stdout.strip()
        if stripped:
            candidates.append(stripped)

        # Fall back to the last {...} or [...] block in the stream.
        for opener, closer in (("[", "]"), ("{", "}")):
            start = stdout.find(opener)
            end = stdout.rfind(closer)
            if start != -1 and end > start:
                candidates.append(stdout[start : end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else None
            if isinstance(parsed, dict):
                return parsed

        return None

    @staticmethod
    def _artifact_url(build: Dict) -> str:
        """Extract the downloadable artifact URL from a build object."""
        artifacts = build.get("artifacts") or {}
        return (
            artifacts.get("applicationArchiveUrl")
            or artifacts.get("buildUrl")
            or build.get("artifactUrl")
            or ""
        )

    def start_build(
        self,
        platform: str = "android",
        profile: str = "preview",
        clear_cache: bool = False,
    ) -> Dict:
        """
        Queue a cloud build and return the build object (does not wait).

        Raises:
            GenerationError: If the build could not be queued.
        """
        args = [
            "build",
            "--platform", platform,
            "--profile", profile,
            "--non-interactive",
            "--no-wait",
            "--json",
        ]
        if clear_cache:
            args.append("--clear-cache")

        self._report("build", f"Queuing {platform} build (profile: {profile})…")

        try:
            result = self._run(args, timeout=1800)
        except subprocess.TimeoutExpired:
            raise GenerationError("Timed out uploading the project to EAS.")
        except FileNotFoundError:
            raise GenerationError(
                "Could not run eas-cli. Install Node.js first "
                "(Termux: pkg install nodejs)."
            )

        if result.returncode != 0:
            combined = f"{result.stdout or ''}\n{result.stderr or ''}"

            # First Android build for an account has no signing keystore, and
            # eas-cli will not create one while --non-interactive. Retry
            # attached to the terminal so the user can approve generating it.
            if "keystore" in combined.lower() or "non-interactive" in combined.lower():
                self._report(
                    "build",
                    "First build needs a signing keystore — switching to "
                    "interactive mode (answer Y to let EAS generate one)",
                )
                interactive = self._run(
                    [
                        "build",
                        "--platform", platform,
                        "--profile", profile,
                        "--no-wait",
                    ],
                    capture=False,
                    timeout=1800,
                )
                if interactive.returncode != 0:
                    raise GenerationError(
                        "EAS build failed during keystore setup. "
                        "Run `npx eas-cli credentials` to configure signing."
                    )
                # Interactive run printed to the terminal rather than to us,
                # so recover the build we just queued from the build list.
                latest = self.latest_build(platform)
                if latest:
                    return latest
                raise GenerationError(
                    "Build was queued but its ID could not be read back. "
                    "Check https://expo.dev for status."
                )

            raise GenerationError(
                f"EAS build failed to queue:\n{combined.strip()[:800]}"
            )

        build = self._parse_build_json(result.stdout or "")
        if not build:
            raise GenerationError(
                f"Could not parse eas-cli output:\n{(result.stdout or '')[:400]}"
            )
        return build

    def latest_build(self, platform: str = "android") -> Optional[Dict]:
        """Return the most recent build for this project, if any."""
        try:
            result = self._run(
                [
                    "build:list",
                    "--platform", platform,
                    "--limit", "1",
                    "--non-interactive",
                    "--json",
                ],
                timeout=180,
            )
        except (subprocess.SubprocessError, OSError):
            return None

        if result.returncode != 0:
            return None
        return self._parse_build_json(result.stdout or "")

    def view_build(self, build_id: str) -> Optional[Dict]:
        """Fetch the current state of one build."""
        try:
            result = self._run(
                ["build:view", build_id, "--json", "--non-interactive"],
                timeout=180,
            )
        except (subprocess.SubprocessError, OSError):
            return None

        if result.returncode != 0:
            return None
        return self._parse_build_json(result.stdout or "")

    def wait_for_build(
        self,
        build_id: str,
        timeout: int = _POLL_TIMEOUT_SECONDS,
        poll_interval: int = _POLL_INTERVAL_SECONDS,
    ) -> Dict:
        """
        Poll until the build reaches a terminal state or the timeout expires.

        Returns the final build object. A timeout returns the last known
        state rather than raising — the build keeps running on Expo's side
        and the user can check back later.
        """
        deadline = time.time() + timeout
        last: Dict = {"status": "UNKNOWN", "id": build_id}
        previous_status = ""

        while time.time() < deadline:
            build = self.view_build(build_id)
            if build:
                last = build
                status = build.get("status", "UNKNOWN")
                if status != previous_status:
                    self._report("build", f"Status: {status}")
                    previous_status = status
                if status in _TERMINAL_STATES:
                    return build
            time.sleep(poll_interval)

        self._report(
            "build",
            "Still building after the wait limit — it will finish on Expo's "
            "servers. Check `anyplace apk --status` later.",
        )
        return last

    def build_apk(
        self,
        platform: str = "android",
        profile: str = "preview",
        wait: bool = True,
        project_name: Optional[str] = None,
        clear_cache: bool = False,
    ) -> BuildResult:
        """
        Full flow: repair config, queue the cloud build, optionally wait.

        This is the one call the CLI makes.
        """
        problems = self.preflight()
        if problems:
            return BuildResult(
                success=False,
                error="\n\n".join(problems),
            )

        files_written: List[str] = []
        files_written.extend(self.ensure_app_config(project_name))
        files_written.extend(self.ensure_eas_json())

        if files_written:
            self._report("config", f"Prepared {len(files_written)} config file(s)")

        build = self.start_build(platform, profile, clear_cache=clear_cache)
        build_id = build.get("id", "")
        logs_url = build.get("buildDetailsPageUrl", "")

        if not wait:
            return BuildResult(
                success=True,
                status=build.get("status", "IN_QUEUE"),
                build_id=build_id,
                logs_url=logs_url,
                files_written=files_written,
            )

        if not build_id:
            return BuildResult(
                success=False,
                error="EAS did not return a build ID.",
                files_written=files_written,
            )

        final = self.wait_for_build(build_id)
        status = final.get("status", "UNKNOWN")

        return BuildResult(
            success=status == "FINISHED",
            status=status,
            build_id=build_id,
            artifact_url=self._artifact_url(final),
            logs_url=final.get("buildDetailsPageUrl", logs_url),
            error="" if status == "FINISHED" else f"Build ended with status {status}",
            files_written=files_written,
        )

    # ── getting the APK onto the phone ──────────────────────────────────

    def download_artifact(self, url: str, dest_dir: Path) -> Path:
        """
        Download a built APK to `dest_dir` and return the local path.

        Streamed to disk so a 60 MB APK never has to fit in memory — Termux
        on a low-end phone will thank us.
        """
        import requests

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = url.split("/")[-1].split("?")[0] or "app.apk"
        if not filename.endswith((".apk", ".aab")):
            filename += ".apk"
        dest = dest_dir / filename

        self._report("download", f"Downloading {filename}…")

        with requests.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if chunk:
                        handle.write(chunk)

        return dest

    @staticmethod
    def open_on_device(apk_path: Path) -> bool:
        """
        Hand the APK to Android's package installer via termux-open.

        Returns False when termux-open is unavailable (i.e. not on a phone),
        so the caller can fall back to printing the path.
        """
        if not shutil.which("termux-open"):
            return False
        try:
            subprocess.run(["termux-open", str(apk_path)], check=False, timeout=60)
            return True
        except (subprocess.SubprocessError, OSError):
            return False
