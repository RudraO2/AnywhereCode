"""
Plan preview and approval workflow.

Displays generated plans with diffs and gets user approval before code generation.
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from anyplace.core.plan_generator import ProjectPlan

console = Console()


def display_plan_summary(plan: ProjectPlan):
    """
    Display plan summary with all key details.

    Args:
        plan: ProjectPlan to display
    """
    # Title panel
    title_text = Text()
    title_text.append(f"Project: ", style="bold cyan")
    title_text.append(f"{plan.project_name}\n")
    title_text.append(f"Template: ", style="bold cyan")
    title_text.append(f"{plan.template}\n")
    title_text.append(f"Time: ", style="bold cyan")
    title_text.append(plan.estimated_time)

    console.print(Panel(
        title_text,
        title="📋 Project Plan",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Description
    if plan.description:
        console.print(f"\n[bold]Description:[/bold]\n{plan.description}")

    # Tech stack
    console.print(f"\n[bold cyan]🛠️  Tech Stack:[/bold cyan]")
    for tech in plan.tech_stack:
        console.print(f"  • {tech}")

    # Key features
    console.print(f"\n[bold cyan]✨ Key Features:[/bold cyan]")
    for feature in plan.key_features:
        console.print(f"  • {feature}")

    # Architecture
    if plan.architecture_notes:
        console.print(f"\n[bold cyan]🏗️  Architecture:[/bold cyan]")
        console.print(plan.architecture_notes)


def display_file_plan(plan: ProjectPlan):
    """
    Display files that will be generated.

    Args:
        plan: ProjectPlan with file information
    """
    console.print(f"\n[bold cyan]📁 Files to Generate ({len(plan.files)}):[/bold cyan]\n")

    # Group files by type
    by_type = {}
    for file_info in plan.files:
        ftype = file_info.file_type
        if ftype not in by_type:
            by_type[ftype] = []
        by_type[ftype].append(file_info)

    type_names = {
        "config": "📋 Configuration",
        "source": "📄 Source Code",
        "test": "🧪 Tests",
        "doc": "📚 Documentation",
        "other": "🗂️  Other",
    }

    for ftype in ["config", "source", "test", "doc", "other"]:
        if ftype in by_type:
            console.print(f"\n{type_names[ftype]}:")
            for file_info in by_type[ftype]:
                deps = f" → depends on: {', '.join(file_info.dependencies)}" \
                    if file_info.dependencies else ""
                console.print(f"  📦 {file_info.path}")
                console.print(f"     {file_info.description}{deps}")


def display_generation_order(plan: ProjectPlan):
    """
    Display the order files will be generated.

    Args:
        plan: ProjectPlan
    """
    console.print(f"\n[bold cyan]⚡ Generation Order:[/bold cyan]\n")
    console.print("[yellow]Files will be generated in this order to ensure dependencies are met:[/yellow]\n")

    for i, file_info in enumerate(plan.files, 1):
        status = "✅"
        console.print(f"  {i:2}. {status} {file_info.path}")


def display_next_steps(plan: ProjectPlan):
    """
    Display next steps after generation.

    Args:
        plan: ProjectPlan
    """
    if not plan.next_steps:
        return

    console.print(f"\n[bold cyan]📍 Next Steps:[/bold cyan]\n")
    for i, step in enumerate(plan.next_steps, 1):
        console.print(f"  {i}. {step}")


def display_plan_diff(plan: ProjectPlan):
    """
    Display what will change (like a git diff).

    Args:
        plan: ProjectPlan
    """
    console.print(f"\n[bold cyan]📊 What Will Be Created:[/bold cyan]\n")

    table = Table(title="File Summary", show_header=True, header_style="bold cyan")
    table.add_column("File", style="cyan", width=30)
    table.add_column("Type", style="green")
    table.add_column("Description", style="white")

    for file_info in plan.files:
        table.add_row(
            file_info.path,
            file_info.file_type,
            file_info.description[:50] + "..." if len(file_info.description) > 50 else file_info.description
        )

    console.print(table)


def show_plan_approval_screen(plan: ProjectPlan) -> bool:
    """
    Show full plan and ask for user approval.

    Args:
        plan: ProjectPlan to approve

    Returns:
        True if approved, False if rejected
    """
    console.clear()

    # Show all plan details
    display_plan_summary(plan)
    display_file_plan(plan)
    display_generation_order(plan)
    display_next_steps(plan)
    display_plan_diff(plan)

    # Approval prompt
    console.print("\n" + "="*80)
    console.print("[bold yellow]⚠️  Review the plan above carefully[/bold yellow]")
    console.print("="*80)

    choice = click.prompt(
        "\n[bold]Approve this plan?[/bold]\n"
        "  1. ✅ Yes, generate project\n"
        "  2. 📝 Review files in detail\n"
        "  3. ❌ Cancel (start over)\n",
        type=click.Choice(["1", "2", "3"]),
        default="1",
    )

    if choice == "1":
        return True
    elif choice == "2":
        show_detailed_file_review(plan)
        return show_plan_approval_screen(plan)  # Show approval again
    else:
        console.print("[yellow]Generation cancelled[/yellow]")
        return False


def show_detailed_file_review(plan: ProjectPlan):
    """
    Show detailed review of each file.

    Args:
        plan: ProjectPlan
    """
    console.clear()
    console.print("[bold cyan]📄 File Details[/bold cyan]\n")

    for i, file_info in enumerate(plan.files, 1):
        console.print(f"\n[bold]File {i}/{len(plan.files)}: {file_info.path}[/bold]")
        console.print(f"  Type: {file_info.file_type}")
        console.print(f"  Description: {file_info.description}")

        if file_info.dependencies:
            console.print(f"  Dependencies:")
            for dep in file_info.dependencies:
                console.print(f"    → {dep}")

        if i < len(plan.files):
            click.prompt("Press Enter to continue", default="", show_default=False)


def show_plan_editing_prompt(plan: ProjectPlan) -> bool:
    """
    Ask if user wants to edit the plan.

    Args:
        plan: ProjectPlan

    Returns:
        True if user wants to proceed, False to regenerate
    """
    console.print("\n[bold cyan]Edit Plan Options:[/bold cyan]")
    console.print("  1. Proceed with generation")
    console.print("  2. Regenerate with different description")
    console.print("  3. Cancel")

    choice = click.prompt(
        "Choose option",
        type=click.Choice(["1", "2", "3"]),
        default="1",
    )

    if choice == "1":
        return True
    elif choice == "2":
        return False  # Signal to regenerate
    else:
        raise click.Abort()


def display_plan_error(error_msg: str):
    """
    Display an error during plan generation.

    Args:
        error_msg: Error message to display
    """
    console.print(Panel(
        f"[red]{error_msg}[/red]",
        title="❌ Plan Generation Error",
        border_style="red",
    ))


if __name__ == "__main__":
    # Test plan display
    from anyplace.core.plan_generator import ProjectPlan, FileInfo

    test_plan = ProjectPlan(
        project_name="test-app",
        template="web-react-vite",
        description="A test application",
        tech_stack=["React", "Vite"],
        files=[
            FileInfo(
                path="src/main.tsx",
                description="Entry point",
                file_type="source",
                dependencies=[],
            ),
            FileInfo(
                path="src/App.tsx",
                description="Root component",
                file_type="source",
                dependencies=["src/main.tsx"],
            ),
        ],
        key_features=["Fast builds", "Hot reload"],
        estimated_time="10 minutes",
        architecture_notes="Component-based architecture",
        next_steps=["Install dependencies", "Start dev server"],
    )

    show_plan_approval_screen(test_plan)
