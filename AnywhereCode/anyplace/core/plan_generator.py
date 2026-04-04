"""
Project plan generation using AI.

Generates structured plans showing all files, dependencies, and architecture decisions.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from anyplace.core.llm_provider import LLMProvider
from anyplace.cli.templates import get_template_info, get_template_path
from anyplace.cli.error_handler import GenerationError, APIError


@dataclass
class FileInfo:
    """Information about a file to be generated."""
    path: str
    description: str
    file_type: str  # "config", "source", "test", "doc", "other"
    dependencies: List[str]  # Other files this depends on


@dataclass
class ProjectPlan:
    """Structured project plan."""
    project_name: str
    template: str
    description: str
    tech_stack: List[str]
    files: List[FileInfo]
    key_features: List[str]
    estimated_time: str
    architecture_notes: str
    next_steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class PlanGenerator:
    """Generates AI-powered project plans."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize plan generator.

        Args:
            llm_provider: LLMProvider instance
        """
        self.llm_provider = llm_provider or LLMProvider()

    def generate_plan(
        self,
        template_name: str,
        project_name: str,
        description: str = "",
    ) -> ProjectPlan:
        """
        Generate a project plan.

        Args:
            template_name: Name of the project template
            project_name: Desired project name
            description: Optional project description

        Returns:
            ProjectPlan with all details

        Raises:
            GenerationError: If plan generation fails
        """
        try:
            # Get template information
            template_info = get_template_info(template_name)

            # Build context about the template
            context = self._build_template_context(template_info, project_name, description)

            # Generate plan from LLM
            plan_json = self.llm_provider.generate_json(
                prompt=self._build_plan_prompt(context),
                system=self._build_system_prompt(),
                temperature=0.5,
                max_tokens=2000,
            )

            # Parse and validate plan
            plan = self._parse_plan_response(plan_json, template_name, project_name)

            if not self.validate_plan(plan):
                raise GenerationError(
                    "Generated plan is invalid: missing required fields or unresolved file dependencies."
                )

            return plan

        except APIError as e:
            raise GenerationError(f"Failed to generate plan: {e}")
        except Exception as e:
            raise GenerationError(f"Plan generation error: {e}")

    def _build_system_prompt(self) -> str:
        """Build system prompt for plan generation."""
        return """You are an expert software architect helping generate project plans.

Your job is to:
1. Analyze the project template and requirements
2. Design a complete file structure with clear purposes
3. Identify dependencies between files
4. Explain architectural decisions
5. Provide actionable next steps

CRITICAL: You MUST respond with ONLY valid JSON.
- No markdown code fences
- No explanatory text before or after
- No comments
- Just the pure JSON object
- Ensure all JSON is properly formatted and valid"""

    def _build_template_context(
        self,
        template_info: Dict,
        project_name: str,
        description: str,
    ) -> Dict[str, Any]:
        """Build context about the template."""
        return {
            "template_name": template_info.get("name"),
            "template_type": template_info.get("type"),
            "template_description": template_info.get("description"),
            "tech_stack": template_info.get("tech_stack", []),
            "key_features": template_info.get("key_features", []),
            "estimated_time": template_info.get("estimated_time"),
            "files_to_generate": template_info.get("files_to_generate", []),
            "project_name": project_name,
            "project_description": description or "No additional description",
        }

    def _build_plan_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for generating a plan."""
        return f"""Generate a detailed project plan for:

Project Name: {context['project_name']}
Template: {context['template_name']} ({context['template_type']})
Template Description: {context['template_description']}
Project Description: {context['project_description']}

Tech Stack: {', '.join(context['tech_stack'])}
Key Features: {', '.join(context['key_features'])}

Core Files to Generate:
{chr(10).join(f"- {f}" for f in context['files_to_generate'])}

Please provide a complete JSON plan with:

{{
  "project_name": "{context['project_name']}",
  "template": "{context['template_name']}",
  "description": "Brief description of what will be built",
  "tech_stack": ["technology1", "technology2", ...],
  "files": [
    {{
      "path": "path/to/file.ext",
      "description": "What this file does",
      "file_type": "config|source|test|doc|other",
      "dependencies": ["other/file.ts", ...]
    }},
    ...
  ],
  "key_features": ["feature1", "feature2", ...],
  "estimated_time": "15 minutes",
  "architecture_notes": "Explanation of the architecture and design decisions",
  "next_steps": ["Step 1 after generation", "Step 2", ...]
}}

Ensure:
- Files have clear descriptions
- Dependencies are properly listed (e.g., "src/main.tsx" depends on "src/App.tsx")
- All files are accounted for
- Architecture is clearly explained"""

    def _parse_plan_response(
        self,
        plan_json: Dict[str, Any],
        template_name: str,
        project_name: str,
    ) -> ProjectPlan:
        """Parse and validate plan response from LLM."""
        try:
            # Parse files
            files = []
            for file_dict in plan_json.get("files", []):
                files.append(
                    FileInfo(
                        path=file_dict.get("path", ""),
                        description=file_dict.get("description", ""),
                        file_type=file_dict.get("file_type", "other"),
                        dependencies=file_dict.get("dependencies", []),
                    )
                )

            plan = ProjectPlan(
                project_name=plan_json.get("project_name", project_name),
                template=template_name,
                description=plan_json.get("description", ""),
                tech_stack=plan_json.get("tech_stack", []),
                files=files,
                key_features=plan_json.get("key_features", []),
                estimated_time=plan_json.get("estimated_time", "Unknown"),
                architecture_notes=plan_json.get("architecture_notes", ""),
                next_steps=plan_json.get("next_steps", []),
            )

            return plan

        except (KeyError, TypeError) as e:
            raise GenerationError(f"Invalid plan response format: {e}")

    def validate_plan(self, plan: ProjectPlan) -> bool:
        """
        Validate a generated plan.

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not plan.project_name or not plan.template:
            return False

        # Check files
        if not plan.files:
            return False

        # Check dependencies exist
        file_paths = {f.path for f in plan.files}
        for file_info in plan.files:
            for dep in file_info.dependencies:
                if dep not in file_paths:
                    # Dependency not found
                    return False

        return True

    def topological_sort_files(self, files: List[FileInfo]) -> List[FileInfo]:
        """
        Sort files by dependencies (topological sort).

        Files with no dependencies come first, then files that depend on them, etc.

        Args:
            files: List of file info

        Returns:
            Sorted list (safe to generate in order)
        """
        from collections import defaultdict, deque

        # Build dependency graph
        graph = defaultdict(list)  # file -> files that depend on it
        in_degree = defaultdict(int)  # file -> number of dependencies
        file_map = {f.path: f for f in files}

        # Initialize
        for f in files:
            if f.path not in in_degree:
                in_degree[f.path] = 0

        # Build graph
        for f in files:
            for dep in f.dependencies:
                if dep in file_map:
                    graph[dep].append(f.path)
                    in_degree[f.path] += 1

        # Topological sort using Kahn's algorithm
        queue = deque([f for f in files if in_degree[f.path] == 0])
        sorted_files = []

        while queue:
            current = queue.popleft()
            sorted_files.append(current)

            for dependent in graph[current.path]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(file_map[dependent])

        # Check for cycles
        if len(sorted_files) != len(files):
            raise GenerationError(
                "Circular dependency detected in file dependencies"
            )

        return sorted_files


if __name__ == "__main__":
    # Test plan generation
    try:
        generator = PlanGenerator()

        plan = generator.generate_plan(
            template_name="web-react-vite",
            project_name="my-react-app",
            description="A modern web application",
        )

        print("Plan generated successfully!")
        print(f"Project: {plan.project_name}")
        print(f"Files: {len(plan.files)}")
        print(f"Time: {plan.estimated_time}")

        # Test sorting
        sorted_files = generator.topological_sort_files(plan.files)
        print(f"\nFile generation order:")
        for i, f in enumerate(sorted_files, 1):
            print(f"  {i}. {f.path}")

    except Exception as e:
        print(f"Error: {e}")
