"""
MCP server for AnywhereCode.

Exposes fully agentic tools: generate a complete project end-to-end,
install dependencies, build, deploy — all without manual steps.

Any MCP client can call these tools to autonomously create
and set up projects.

Usage:
    anyplace serve
    # or directly:
    python -m anyplace.mcp.server
"""

from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP package not installed.\n"
        "Run: pip install 'anyplace[mcp]'\n"
        "Or:  pip install mcp>=1.0.0"
    )

from anyplace.cli.templates import list_available_templates, get_template_info
from anyplace.config.api_manager import APIManager
from anyplace.config.environment import get_projects_dir
from anyplace.core.llm_provider import LLMProvider
from anyplace.core.plan_generator import PlanGenerator
from anyplace.core.build_orchestrator import BuildOrchestrator
from anyplace.core.hooks_injector import HooksInjector
from anyplace.cli.error_handler import GenerationError, APIError

mcp = FastMCP("AnywhereCode")


@mcp.tool()
def list_templates() -> list:
    """List all available project templates with descriptions and tech stacks."""
    result = []
    for name in list_available_templates():
        info = get_template_info(name)
        result.append({"name": name, **info})
    return result


@mcp.tool()
def generate_plan(
    template_name: str,
    project_name: str,
    description: str = "",
) -> dict:
    """
    Generate an AI-powered project plan.

    Args:
        template_name: Template to use (e.g. 'web-react-vite', 'mobile-expo-rn', 'backend-nodejs')
        project_name: Name for the project
        description: Optional description of what the project should do

    Returns:
        Project plan with files, tech stack, architecture notes, and next steps
    """
    try:
        api_mgr = APIManager()
        llm = LLMProvider(api_mgr)
        generator = PlanGenerator(llm)
        plan = generator.generate_plan(
            template_name=template_name,
            project_name=project_name,
            description=description,
        )
        return plan.to_dict()
    except (GenerationError, APIError) as e:
        raise ValueError(str(e))


@mcp.tool()
def generate_project(
    template_name: str,
    project_name: str,
    description: str = "",
    output_dir: Optional[str] = None,
) -> dict:
    """
    FULLY AGENTIC: Generate a complete project end-to-end.

    This does EVERYTHING autonomously:
    1. Generates an AI project plan
    2. Creates all source files
    3. Initializes git repo with commits
    4. Installs all dependencies (npm install / pip install)
    5. Builds the project
    6. Sets up .env from .env.example
    7. Generates CI/CD pipeline (GitHub Actions)
    8. Generates Docker config
    9. Generates deployment config
    10. Verifies the project works

    No manual steps needed — just call this and get a ready-to-use project.

    Args:
        template_name: Template to use
        project_name: Name for the project
        description: Optional project description
        output_dir: Output directory path (defaults to ~/.anyplace/projects/)

    Returns:
        Dict with project_dir, files_generated, total_files, git_enabled, pipeline_results
    """
    try:
        from pathlib import Path

        api_mgr = APIManager()
        llm = LLMProvider(api_mgr)
        generator = PlanGenerator(llm)

        plan = generator.generate_plan(
            template_name=template_name,
            project_name=project_name,
            description=description,
        )

        base_dir = Path(output_dir) if output_dir else get_projects_dir()
        project_dir = base_dir / project_name

        orchestrator = BuildOrchestrator(
            plan=plan,
            llm_provider=llm,
            project_dir=project_dir,
            use_git=True,
            agentic=True,  # Full autonomous pipeline
        )

        success = orchestrator.build()

        result = orchestrator.get_project_info()

        # Include pipeline results
        if orchestrator.pipeline_result:
            result["pipeline"] = orchestrator.pipeline_result.summary

        return result

    except (GenerationError, APIError) as e:
        raise ValueError(str(e))


@mcp.tool()
def setup_project(
    project_dir: str,
    skip_deploy: bool = False,
) -> dict:
    """
    Run the agentic pipeline on an EXISTING project directory.

    Automatically installs dependencies, builds, sets up CI/CD,
    Docker, environment, and deployment configs.

    Use this when you have an existing project that needs to be set up.

    Args:
        project_dir: Path to the project directory
        skip_deploy: Skip deployment config generation

    Returns:
        Pipeline results with status of each step
    """
    try:
        from pathlib import Path
        from anyplace.core.agent_executor import AgentExecutor

        path = Path(project_dir)
        if not path.exists():
            raise ValueError(f"Project directory does not exist: {project_dir}")

        executor = AgentExecutor(project_dir=path)
        result = executor.run_full_pipeline(skip_deploy=skip_deploy)
        return result.summary

    except Exception as e:
        raise ValueError(str(e))


@mcp.tool()
def install_dependencies(project_dir: str) -> dict:
    """
    Auto-detect and install project dependencies.

    Supports: npm (Node.js), pip (Python), cargo (Rust), go mod (Go).

    Args:
        project_dir: Path to the project directory

    Returns:
        Result with success status and output
    """
    try:
        from pathlib import Path
        from anyplace.core.agent_executor import AgentExecutor

        executor = AgentExecutor(project_dir=Path(project_dir))
        result = executor.install_dependencies()
        return {
            "success": result.success,
            "skipped": result.skipped,
            "output": result.output,
            "error": result.error,
        }
    except Exception as e:
        raise ValueError(str(e))


@mcp.tool()
def build_project(project_dir: str) -> dict:
    """
    Auto-detect project type and build.

    Args:
        project_dir: Path to the project directory

    Returns:
        Result with success status and output
    """
    try:
        from pathlib import Path
        from anyplace.core.agent_executor import AgentExecutor

        executor = AgentExecutor(project_dir=Path(project_dir))
        result = executor.build_project()
        return {
            "success": result.success,
            "skipped": result.skipped,
            "output": result.output,
            "error": result.error,
        }
    except Exception as e:
        raise ValueError(str(e))


if __name__ == "__main__":
    mcp.run()
