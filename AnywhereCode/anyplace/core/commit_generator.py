"""
Commit message generator.

Analyzes git diff and generates meaningful commit messages using LLM.
"""

import subprocess
from pathlib import Path

from anyplace.core.llm_provider import LLMProvider
from anyplace.cli.error_handler import GenerationError


class CommitGenerator:
    """Generates smart commit messages from git diffs using LLM."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    def get_staged_diff(self, project_dir: Path) -> str:
        """Get diff of staged (cached) changes."""
        result = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GenerationError(f"Failed to get staged diff: {result.stderr.strip()}")
        return result.stdout

    def get_unstaged_diff(self, project_dir: Path) -> str:
        """Get diff of all tracked changes (staged + unstaged). Falls back to cached."""
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # HEAD may not exist yet (fresh repo) — fall back to staged
            return self.get_staged_diff(project_dir)
        return result.stdout

    def generate_message(self, diff: str) -> str:
        """
        Generate a conventional commit message from a diff string.

        Args:
            diff: Output of git diff

        Returns:
            Commit message string

        Raises:
            GenerationError: If diff is empty or LLM call fails
        """
        if not diff.strip():
            raise GenerationError(
                "No staged changes found. Stage files with 'git add' first, "
                "or use --all to stage everything."
            )

        system = (
            "You are a git commit message expert. Given a git diff, write a concise "
            "conventional commit message. Format: `<type>(<scope>): <summary>` on line 1 "
            "(max 72 chars), then a blank line, then an optional body. "
            "Types: feat, fix, refactor, docs, chore, style, test. "
            "Output the message only, no code fences, no extra commentary."
        )

        prompt = f"Write a commit message for this diff:\n\n{diff}"

        message = self.llm_provider.generate_text(
            prompt=prompt,
            system=system,
            temperature=0.3,
            max_tokens=256,
        )
        return message.strip()

    def generate_and_commit(self, project_dir: Path, stage_all: bool = False) -> str:
        """
        Optionally stage all changes, generate a message, and commit.

        Args:
            project_dir: Path to the git repository
            stage_all: If True, run git add -A before diffing

        Returns:
            The commit message used

        Raises:
            GenerationError: If diff is empty, message generation fails, or commit fails
        """
        if stage_all:
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise GenerationError(f"git add failed: {result.stderr.strip()}")

        diff = self.get_staged_diff(project_dir)
        message = self.generate_message(diff)

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GenerationError(f"Commit failed: {result.stderr.strip()}")

        return message
