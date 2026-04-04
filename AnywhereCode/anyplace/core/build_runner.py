"""
Build runner.

Detects project type and executes the appropriate build/install commands.
Supports Node.js, Python, Rust, Go, and more.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from anyplace.cli.error_handler import GenerationError


class BuildRunner:
    """Detects project type and runs build/install commands."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    def _detect_project_type(self) -> str:
        """
        Detect project type from files present.

        Returns:
            One of: "expo-rn", "react-vite", "nextjs", "nodejs-backend",
                    "nodejs", "django", "python", "rust", "go", "unknown"
        """
        pkg_path = self.project_dir / "package.json"
        req_txt = self.project_dir / "requirements.txt"
        setup_py = self.project_dir / "setup.py"
        pyproject = self.project_dir / "pyproject.toml"
        manage_py = self.project_dir / "manage.py"
        cargo = self.project_dir / "Cargo.toml"
        go_mod = self.project_dir / "go.mod"

        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
            except (json.JSONDecodeError, OSError):
                return "nodejs"

            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "expo" in deps:
                return "expo-rn"
            if "next" in deps:
                return "nextjs"
            if "vite" in deps:
                return "react-vite"
            if any(d in deps for d in ("express", "fastify", "koa", "hapi")):
                return "nodejs-backend"
            return "nodejs"

        if manage_py.exists():
            return "django"
        if pyproject.exists() or setup_py.exists() or req_txt.exists():
            return "python"
        if cargo.exists():
            return "rust"
        if go_mod.exists():
            return "go"

        return "unknown"

    def get_build_command(self) -> List[str]:
        """Get the correct build command for the detected project type."""
        project_type = self._detect_project_type()

        if project_type == "expo-rn":
            return ["npx", "expo", "export"]

        if project_type in ("react-vite", "nextjs", "nodejs", "nodejs-backend"):
            pkg_path = self.project_dir / "package.json"
            try:
                pkg = json.loads(pkg_path.read_text())
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    return ["npm", "run", "build"]
                if "start" in scripts:
                    return ["npm", "run", "start"]
            except (json.JSONDecodeError, OSError):
                pass
            return ["npm", "run", "build"]

        if project_type == "django":
            return ["python3", "manage.py", "migrate", "--run-syncdb"]

        if project_type == "python":
            return ["python3", "-m", "py_compile", "*.py"]

        if project_type == "rust":
            return ["cargo", "build", "--release"]

        if project_type == "go":
            return ["go", "build", "./..."]

        raise GenerationError(
            f"Cannot detect project type in: {self.project_dir}\n"
            "Ensure a package.json, requirements.txt, or similar config exists."
        )

    def get_install_command(self) -> List[str]:
        """Get the dependency install command."""
        project_type = self._detect_project_type()

        if project_type in ("expo-rn", "react-vite", "nextjs", "nodejs", "nodejs-backend"):
            return ["npm", "install", "--legacy-peer-deps"]

        if project_type in ("python", "django"):
            pip_cmd = "pip3" if shutil.which("pip3") else "pip"
            req = self.project_dir / "requirements.txt"
            if req.exists():
                return [pip_cmd, "install", "-r", "requirements.txt"]
            return [pip_cmd, "install", "-e", "."]

        if project_type == "rust":
            return ["cargo", "build"]

        if project_type == "go":
            return ["go", "mod", "download"]

        raise GenerationError(
            f"Cannot detect project type in: {self.project_dir}"
        )

    def auto_install(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Automatically install dependencies. Returns True on success, False on failure.
        Does not raise — safe to call in pipeline.
        """
        try:
            cmd = self.get_install_command()
        except GenerationError:
            return False

        if not shutil.which(cmd[0]):
            if progress_callback:
                progress_callback(f"Command not found: {cmd[0]}")
            return False

        return self._run_cmd(cmd, progress_callback)

    def auto_build(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Automatically build the project. Returns True on success, False on failure.
        Does not raise — safe to call in pipeline.
        """
        try:
            cmd = self.get_build_command()
        except GenerationError:
            return False

        if not shutil.which(cmd[0]):
            if progress_callback:
                progress_callback(f"Command not found: {cmd[0]}")
            return False

        return self._run_cmd(cmd, progress_callback)

    def _run_cmd(self, cmd: List[str], progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Run a command, stream output, return success bool."""
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in process.stdout:
                if progress_callback:
                    progress_callback(line.rstrip())

            process.wait()
            return process.returncode == 0

        except (FileNotFoundError, OSError):
            return False

    def run_build(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Run the build command, streaming output line by line.

        Returns:
            True on success

        Raises:
            GenerationError: If build fails or command not found
        """
        cmd = self.get_build_command()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in process.stdout:
                if progress_callback:
                    progress_callback(line.rstrip())

            process.wait()

            if process.returncode != 0:
                raise GenerationError(
                    f"Build command {' '.join(cmd)} failed with exit code {process.returncode}"
                )

            return True

        except FileNotFoundError:
            raise GenerationError(
                f"Command not found: {cmd[0]}\n"
                "Make sure the required tools are installed."
            )
