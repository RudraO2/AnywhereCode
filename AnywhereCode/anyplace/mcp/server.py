"""
MCP server for AnywhereCode.

Exposes list_templates, generate_plan, and generate_project as MCP tools
so Claude can call them directly without the CLI.

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
    Generate a complete project: plan, all files, git repo, and Claude Code integration.

    Args:
        template_name: Template to use
        project_name: Name for the project
        description: Optional project description
        output_dir: Output directory path (defaults to ~/.anyplace/projects/)

    Returns:
        Dict with project_dir, files_generated, total_files, git_enabled
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
        )

        success = orchestrator.build()

        if success:
            # Inject Claude Code integration (already done by orchestrator,
            # but explicit call here ensures it runs even if orchestrator changes)
            try:
                injector = HooksInjector(project_dir)
                injector.inject()
            except Exception:
                pass

        return orchestrator.get_project_info()

    except (GenerationError, APIError) as e:
        raise ValueError(str(e))


if __name__ == "__main__":
    mcp.run()
