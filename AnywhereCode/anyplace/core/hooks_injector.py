"""
Claude Code hooks injector.

Writes .claude/settings.json and .claude/commands/ into generated projects
so they have Claude Code integration out of the box.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from anyplace.core.build_runner import BuildRunner


class HooksInjector:
    """Injects Claude Code integration files into a project directory."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    def _build_settings(self, project_type: str) -> dict:
        """Build the .claude/settings.json content."""
        hooks: dict = {
            "PostToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "npm run lint --if-present 2>/dev/null || true",
                        }
                    ],
                }
            ],
            "PostSaveFiles": [
                {
                    "matcher": ".*\\.(ts|tsx|js|jsx)$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "npx --yes prettier --write $CLAUDE_FILE_PATH "
                                "2>/dev/null || true"
                            ),
                        }
                    ],
                }
            ],
        }

        if project_type == "expo-rn":
            hooks["PostToolUse"].append(
                {
                    "matcher": "app\\.json|eas\\.json",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "npx expo-doctor 2>/dev/null || true",
                        }
                    ],
                }
            )

        return {"hooks": hooks}

    def _get_commands(self, project_type: str) -> Dict[str, dict]:
        """Get slash command definitions keyed by filename (without .md)."""
        commands: Dict[str, dict] = {
            "build": {
                "heading": "Build Project",
                "command": "npm run build",
            },
            "dev": {
                "heading": "Start Dev Server",
                "command": "npm run dev",
            },
            "lint": {
                "heading": "Lint Code",
                "command": "npm run lint",
            },
        }

        if project_type == "expo-rn":
            commands["eas-build"] = {
                "heading": "EAS Build",
                "command": "eas build --platform all",
            }
            commands["preview"] = {
                "heading": "Start Expo Preview",
                "command": "npx expo start",
            }

        return commands

    def write_claude_settings(self, project_type: str) -> Path:
        """Write .claude/settings.json and return its path."""
        claude_dir = self.project_dir / ".claude"
        claude_dir.mkdir(exist_ok=True)

        settings_path = claude_dir / "settings.json"
        settings = self._build_settings(project_type)
        settings_path.write_text(json.dumps(settings, indent=2))

        return settings_path

    def write_claude_commands(self, project_type: str) -> List[Path]:
        """Write .claude/commands/*.md files and return their paths."""
        commands_dir = self.project_dir / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        written: List[Path] = []
        for name, info in self._get_commands(project_type).items():
            cmd_path = commands_dir / f"{name}.md"
            content = f"# {info['heading']}\n\n```bash\n{info['command']}\n```\n"
            cmd_path.write_text(content)
            written.append(cmd_path)

        return written

    def inject(self, project_type: Optional[str] = None) -> dict:
        """
        Inject all Claude Code integration files into the project directory.

        Args:
            project_type: Override auto-detection ("expo-rn", "react-vite", "nodejs")

        Returns:
            Dict with "settings" (path str) and "commands" (list of path strs)
        """
        if project_type is None:
            runner = BuildRunner(self.project_dir)
            project_type = runner._detect_project_type()

        settings_path = self.write_claude_settings(project_type)
        command_paths = self.write_claude_commands(project_type)

        return {
            "settings": str(settings_path),
            "commands": [str(p) for p in command_paths],
        }
