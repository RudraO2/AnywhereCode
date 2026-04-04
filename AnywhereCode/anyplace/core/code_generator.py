"""
Code generation engine.

Generates and writes project files sequentially using LLM.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

from anyplace.core.llm_provider import LLMProvider
from anyplace.core.plan_generator import ProjectPlan, FileInfo
from anyplace.cli.error_handler import GenerationError, APIError
from anyplace.config.environment import get_projects_dir


@dataclass
class GenerationCheckpoint:
    """Checkpoint for error recovery."""
    timestamp: str
    project_name: str
    files_generated: List[str]
    total_files: int
    current_index: int
    success: bool


class CodeGenerator:
    """Generates and writes project files."""

    def __init__(
        self,
        plan: ProjectPlan,
        llm_provider: Optional[LLMProvider] = None,
        project_dir: Optional[Path] = None,
    ):
        """
        Initialize code generator.

        Args:
            plan: The ProjectPlan to generate
            llm_provider: LLMProvider instance
            project_dir: Directory to create project in (defaults to get_projects_dir())
        """
        self.plan = plan
        self.llm_provider = llm_provider or LLMProvider()
        self.project_dir = project_dir or (get_projects_dir() / plan.project_name)
        self.files_generated: List[str] = []
        self.checkpoints: List[GenerationCheckpoint] = []

    def generate_all(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> bool:
        """
        Generate all files in the project.

        Args:
            progress_callback: Called with (current_file, index, total)

        Returns:
            True if successful, False otherwise

        Raises:
            GenerationError: If generation fails
        """
        # Project directory should already exist (created by BuildOrchestrator)
        # If called standalone, create it
        if not self.project_dir.exists():
            try:
                self.project_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise GenerationError(f"Can't create project directory: {e}")

        # Generate files in order
        total_files = len(self.plan.files)

        for i, file_info in enumerate(self.plan.files):
            current = i + 1

            try:
                # Notify progress
                if progress_callback:
                    progress_callback(file_info.path, current, total_files)

                # Generate file content
                content = self._generate_file_content(file_info)

                # Write file
                self._write_file(file_info.path, content)

                # Track progress
                self.files_generated.append(file_info.path)

                # Create checkpoint
                self._save_checkpoint(current, total_files, success=False)

            except (APIError, GenerationError) as e:
                # Save checkpoint and re-raise
                self._save_checkpoint(current, total_files, success=False)
                raise GenerationError(
                    f"Failed to generate {file_info.path}:\n{e}"
                )
            except Exception as e:
                self._save_checkpoint(current, total_files, success=False)
                raise GenerationError(
                    f"Unexpected error generating {file_info.path}:\n{e}"
                )

        # Mark as successful
        self._save_checkpoint(total_files, total_files, success=True)
        return True

    def _generate_file_content(self, file_info: FileInfo) -> str:
        """
        Generate content for a file using LLM.

        Args:
            file_info: FileInfo for the file to generate

        Returns:
            Generated file content

        Raises:
            APIError: If LLM call fails
            GenerationError: If content generation fails
        """
        prompt = self._build_generation_prompt(file_info)
        system = self._build_generation_system()

        try:
            content = self.llm_provider.generate_text(
                prompt=prompt,
                system=system,
                temperature=0.5,
                max_tokens=4096,
            )

            # Clean up markdown wrappers if present - extract first code block only
            if "```" in content:
                lines = content.split("\n")
                in_code = False
                code_lines = []
                for line in lines:
                    if line.strip().startswith("```"):
                        if not in_code:
                            in_code = True  # Enter first code block
                        else:
                            break  # Exit first code block and stop
                    elif in_code:
                        code_lines.append(line)

                if code_lines:
                    content = "\n".join(code_lines)

            return content.strip()

        except APIError:
            raise
        except Exception as e:
            raise GenerationError(f"Failed to generate content: {e}")

    def _build_generation_system(self) -> str:
        """Build system prompt for file generation."""
        return f"""You are an expert software engineer writing production-ready code.

Project: {self.plan.project_name}
Template: {self.plan.template}
Tech Stack: {', '.join(self.plan.tech_stack)}

Your task is to generate code that:
1. Follows best practices for the technology
2. Is clean, readable, and well-structured
3. Uses proper error handling
4. Includes helpful comments where logic is complex
5. Integrates with other files in the project

Generate ONLY the file content. No markdown, no explanations, no file names.
Just the pure code/configuration."""

    def _build_generation_prompt(self, file_info: FileInfo) -> str:
        """Build prompt for generating a specific file."""
        # Get context about already-generated files
        context_files = [f for f in self.plan.files if f.path in self.files_generated]
        context = ""
        if context_files:
            context = "\n\nAlready generated:\n"
            for f in context_files:
                context += f"- {f.path}: {f.description}\n"

        return f"""Generate the content for this file:

File: {file_info.path}
Type: {file_info.file_type}
Description: {file_info.description}

{context}

Dependencies on:
{chr(10).join(f"- {dep}" for dep in file_info.dependencies) if file_info.dependencies else "- No dependencies"}

Project description: {self.plan.description}

Architecture: {self.plan.architecture_notes}

Generate the complete, production-ready content for {file_info.path}."""

    def _write_file(self, relative_path: str, content: str):
        """
        Write a file to disk.

        Args:
            relative_path: Path relative to project root
            content: File content

        Raises:
            GenerationError: If write fails
        """
        file_path = self.project_dir / relative_path

        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "w") as f:
                f.write(content)

        except Exception as e:
            raise GenerationError(f"Can't write file {relative_path}: {e}")

    def _save_checkpoint(
        self,
        current_index: int,
        total_files: int,
        success: bool,
    ):
        """
        Save a checkpoint for error recovery.

        Args:
            current_index: Current file index
            total_files: Total number of files
            success: Whether generation was successful
        """
        checkpoint = GenerationCheckpoint(
            timestamp=datetime.now().isoformat(),
            project_name=self.plan.project_name,
            files_generated=self.files_generated.copy(),
            total_files=total_files,
            current_index=current_index,
            success=success,
        )

        self.checkpoints.append(checkpoint)

        # Save to project logs
        logs_dir = self.project_dir / ".logs"
        logs_dir.mkdir(exist_ok=True)

        checkpoint_file = logs_dir / "checkpoints.json"

        try:
            checkpoints_data = [
                {
                    "timestamp": cp.timestamp,
                    "files_generated": cp.files_generated,
                    "current_index": cp.current_index,
                    "total_files": cp.total_files,
                    "success": cp.success,
                }
                for cp in self.checkpoints
            ]

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoints_data, f, indent=2)

        except Exception as e:
            # Log errors don't block generation
            pass

    def can_resume(self) -> bool:
        """Check if generation can be resumed from checkpoint."""
        if not self.checkpoints:
            return False

        last_checkpoint = self.checkpoints[-1]
        return not last_checkpoint.success and len(last_checkpoint.files_generated) > 0

    def get_resume_info(self) -> Dict[str, Any]:
        """Get information about resumable checkpoint."""
        if not self.can_resume():
            return {}

        last = self.checkpoints[-1]
        return {
            "files_done": len(last.files_generated),
            "total_files": last.total_files,
            "next_file_index": last.current_index,
            "timestamp": last.timestamp,
        }

    def cleanup_on_failure(self):
        """Clean up partial project on failure."""
        try:
            if self.project_dir.exists():
                import shutil
                shutil.rmtree(self.project_dir)
        except Exception:
            pass  # Best effort cleanup


if __name__ == "__main__":
    # Test code generator
    from anyplace.core.plan_generator import ProjectPlan, FileInfo

    files = [
        FileInfo(
            path="package.json",
            description="Project dependencies",
            file_type="config",
            dependencies=[],
        ),
        FileInfo(
            path="src/main.ts",
            description="Entry point",
            file_type="source",
            dependencies=["package.json"],
        ),
    ]

    plan = ProjectPlan(
        project_name="test-gen",
        template="backend-nodejs",
        description="Test code generation",
        tech_stack=["Node.js", "TypeScript"],
        files=files,
        key_features=["Type safe"],
        estimated_time="5 min",
        architecture_notes="Simple API",
        next_steps=["npm install", "npm run dev"],
    )

    try:
        gen = CodeGenerator(plan)
        print(f"Generator ready for: {plan.project_name}")
        print(f"Project dir: {gen.project_dir}")
        print("✅ CodeGenerator initialized")
    except Exception as e:
        print(f"❌ Error: {e}")
