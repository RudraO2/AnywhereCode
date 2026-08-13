"""
Deploy config generator.

Generates EAS configs, GitHub Actions workflows, and backend deployment configs.
"""

import json
from pathlib import Path
from typing import List

from anyplace.core.llm_provider import LLMProvider
from anyplace.core.build_runner import BuildRunner
from anyplace.cli.error_handler import GenerationError


class DeployGenerator:
    """Generates deployment configurations for generated projects."""

    def __init__(self, project_dir: Path, llm_provider: LLMProvider):
        self.project_dir = Path(project_dir)
        self.llm_provider = llm_provider
        self.build_runner = BuildRunner(self.project_dir)

    def generate_eas_config(self) -> str:
        """
        Generate eas.json content for Expo/React Native projects.

        Delegates to EASBuilder so this and `anyplace apk` can never disagree
        about the profiles — in particular the preview profile has to produce
        an APK, since EAS defaults Android to an AAB you cannot sideload.
        """
        from anyplace.core.eas_builder import EASBuilder

        builder = EASBuilder(self.project_dir)
        builder.ensure_eas_json()
        return (self.project_dir / "eas.json").read_text()

    def generate_pm2_config(self) -> str:
        """Generate ecosystem.config.js for Node.js backends using PM2."""
        return """module.exports = {
  apps: [
    {
      name: 'app',
      script: './dist/index.js',
      instances: 'max',
      exec_mode: 'cluster',
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
}
"""

    def generate_github_actions_workflow(self, project_type: str) -> str:
        """Generate a GitHub Actions deploy workflow YAML using LLM."""
        scripts = {}
        pkg_path = self.project_dir / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                scripts = pkg.get("scripts", {})
            except (json.JSONDecodeError, OSError):
                pass

        system = (
            "You are a DevOps engineer. Generate a production-ready GitHub Actions "
            "workflow YAML. Output only valid YAML content, no markdown fences, "
            "no extra commentary."
        )

        prompt = (
            f"Generate a GitHub Actions deploy workflow for a {project_type} project.\n"
            f"Available npm scripts: {list(scripts.keys()) or ['build', 'test']}\n"
            "Include: checkout, setup-node (v20), npm ci, build step, "
            "and a deploy step with a TODO placeholder comment."
        )

        return self.llm_provider.generate_text(
            prompt=prompt,
            system=system,
            temperature=0.3,
            max_tokens=1024,
        )

    def deploy(self, target: str) -> dict:
        """
        Generate deployment config for the given target.

        Args:
            target: One of "eas", "github"

        Returns:
            Dict with "files_written" (list of str) and "next_steps" (list of str)

        Raises:
            GenerationError: If target/project-type combination is unsupported
        """
        project_type = self.build_runner._detect_project_type()
        files_written: List[str] = []
        next_steps: List[str] = []

        if project_type == "expo-rn" and target == "eas":
            from anyplace.core.eas_builder import EASBuilder

            builder = EASBuilder(self.project_dir)
            files_written.extend(builder.ensure_app_config(self.project_dir.name))
            files_written.extend(builder.ensure_eas_json())
            if not files_written:
                files_written.append(str(self.project_dir / "eas.json"))

            next_steps = [
                "anyplace login-expo   (paste a token from expo.dev/settings/access-tokens)",
                "anyplace apk          (builds an installable APK in the cloud)",
                "anyplace apk --profile production   (AAB for the Play Store)",
            ]

        elif target == "github":
            workflow_dir = self.project_dir / ".github" / "workflows"
            workflow_dir.mkdir(parents=True, exist_ok=True)
            workflow_path = workflow_dir / "deploy.yml"
            yaml_content = self.generate_github_actions_workflow(project_type)
            workflow_path.write_text(yaml_content)
            files_written.append(str(workflow_path))

            if project_type == "nodejs":
                pm2_path = self.project_dir / "ecosystem.config.js"
                pm2_path.write_text(self.generate_pm2_config())
                files_written.append(str(pm2_path))
                next_steps = [
                    "Push to GitHub to trigger the workflow",
                    "Set up repository secrets (SSH_KEY, SERVER_HOST, etc.)",
                    "Install PM2 on your server: npm install -g pm2",
                ]
            else:
                next_steps = [
                    "Push to GitHub to trigger the workflow",
                    "Configure repository secrets as needed",
                ]

        else:
            raise GenerationError(
                f"Unsupported deploy target '{target}' for project type '{project_type}'.\n"
                "Supported combinations:\n"
                "  - expo-rn + eas\n"
                "  - any type + github"
            )

        return {
            "files_written": files_written,
            "next_steps": next_steps,
        }
