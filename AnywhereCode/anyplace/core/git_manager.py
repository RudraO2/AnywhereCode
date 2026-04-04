"""
Git repository management.

Handles repository initialization and auto-commits during generation.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from anyplace.cli.error_handler import GenerationError


class GitManager:
    """Manages git operations for generated projects."""

    def __init__(self, project_dir: Path):
        """
        Initialize git manager.

        Args:
            project_dir: Path to project directory
        """
        self.project_dir = Path(project_dir)
        self.repo_initialized = False

    def init_repo(self) -> bool:
        """
        Initialize git repository in project.

        Returns:
            True if successful

        Raises:
            GenerationError: If git init fails
        """
        try:
            self._run_git("init")
            self.repo_initialized = True  # Mark initialized before config (config is optional)
        except GenerationError as e:
            raise GenerationError(f"Failed to initialize git: {e}")

        # Set local identity — non-fatal on Termux where git config can fail right after init
        try:
            self._run_git("config", "--local", "user.email", "anyplace@example.com")
            self._run_git("config", "--local", "user.name", "AnywhereCode")
        except GenerationError:
            pass  # Git works fine without explicit local config if global config exists

        return True

    def add_and_commit(
        self,
        file_path: str,
        message: str,
    ) -> bool:
        """
        Add file to git and commit.

        Args:
            file_path: Path relative to project root
            message: Commit message

        Returns:
            True if successful

        Raises:
            GenerationError: If git operation fails
        """
        if not self.repo_initialized:
            return False

        try:
            # Add file
            self._run_git("add", file_path)

            # Commit with message
            self._run_git("commit", "-m", message)

            return True

        except GenerationError:
            # Commit might fail if nothing to commit, that's ok
            return False

    def commit_bulk(
        self,
        files: list,
        message: str,
    ) -> bool:
        """
        Commit multiple files at once.

        Args:
            files: List of file paths
            message: Commit message

        Returns:
            True if successful
        """
        if not self.repo_initialized or not files:
            return False

        try:
            for file_path in files:
                self._run_git("add", file_path)

            self._run_git("commit", "-m", message)
            return True

        except GenerationError:
            return False

    def create_gitignore(self) -> bool:
        """
        Create a default .gitignore file.

        Returns:
            True if successful
        """
        gitignore_path = self.project_dir / ".gitignore"

        default_ignores = """# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/
env/

# Build outputs
dist/
build/
.next/
out/
.expo/
.eas/

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Logs
*.log
logs/
npm-debug.log*

# OS
Thumbs.db
.DS_Store

# Project specific
.anyplace/
.logs/
"""

        try:
            with open(gitignore_path, "w") as f:
                f.write(default_ignores)
            return True
        except Exception:
            return False

    def _run_git(self, *args: str) -> str:
        """
        Run a git command.

        Args:
            *args: Git command and arguments

        Returns:
            Command output

        Raises:
            GenerationError: If git command fails
        """
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            # Check for actual errors
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown git error"
                raise GenerationError(error_msg)

            return result.stdout

        except GenerationError:
            raise
        except FileNotFoundError:
            raise GenerationError(
                "Git not installed or not in PATH.\n"
                "Install git: https://git-scm.com/downloads"
            )
        except Exception as e:
            raise GenerationError(f"Git error: {e}")

    def check_git_installed(self) -> bool:
        """Check if git is installed."""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def get_repo_status(self) -> Optional[str]:
        """Get repository status."""
        if not self.repo_initialized:
            return None

        try:
            return self._run_git("status", "--short")
        except GenerationError:
            return None


if __name__ == "__main__":
    # Test git manager
    import tempfile
    import shutil

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "test-project"
        project_dir.mkdir()

        try:
            git = GitManager(project_dir)

            # Check git installed
            if not git.check_git_installed():
                print("❌ Git not installed")
            else:
                print("✅ Git installed")

                # Initialize repo
                git.init_repo()
                print("✅ Repository initialized")

                # Create gitignore
                git.create_gitignore()
                print("✅ .gitignore created")

                # Create test file
                test_file = project_dir / "test.txt"
                test_file.write_text("Test content")

                # Commit
                if git.add_and_commit("test.txt", "Initial commit"):
                    print("✅ File committed")
                else:
                    print("⚠️  Commit failed or nothing to commit")

        except Exception as e:
            print(f"❌ Error: {e}")
