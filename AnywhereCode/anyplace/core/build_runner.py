"""
Build runner.

Detects project type from package.json and executes the appropriate build command.
"""

import json
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
        Detect project type from package.json.

        Returns:
            One of: "expo-rn", "react-vite", "nodejs", "unknown"
        """
        pkg_path = self.project_dir / "package.json"
        if not pkg_path.exists():
            return "unknown"

        try:
            pkg = json.loads(pkg_path.read_text())
        except (json.JSONDecodeError, OSError):
            return "unknown"

        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if "expo" in deps:
            return "expo-rn"
        if "vite" in deps:
            return "react-vite"
        return "nodejs"

    def get_build_command(self) -> List[str]:
        """
        Get the correct build command for the detected project type.

        Raises:
            GenerationError: If project type cannot be detected
        """
        project_type = self._detect_project_type()

        if project_type == "expo-rn":
            return ["npx", "expo", "export"]

        if project_type in ("react-vite", "nodejs"):
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

        raise GenerationError(
            f"Cannot detect project type in: {self.project_dir}\n"
            "Ensure a package.json exists with the correct dependencies."
        )

    def get_install_command(self) -> List[str]:
        """Get the dependency install command."""
        if self._detect_project_type() == "unknown":
            raise GenerationError(
                f"Cannot detect project type in: {self.project_dir}"
            )
        return ["npm", "install"]

    def run_build(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Run the build command, streaming output line by line.

        Args:
            progress_callback: Called with each output line

        Returns:
            True on success

        Raises:
            GenerationError: If build fails or command not found
        """
        cmd = self.get_build_command()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.project_dir,
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
                "Make sure Node.js and npm are installed."
            )
