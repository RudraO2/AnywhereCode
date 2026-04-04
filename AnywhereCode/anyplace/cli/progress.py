"""
Progress display during code generation.

Shows progress bars, current file, and generation status.
"""

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from typing import Optional, List

console = Console()


class GenerationProgress:
    """Manages progress display during code generation."""

    def __init__(self, total_files: int, project_name: str):
        """
        Initialize progress display.

        Args:
            total_files: Total number of files to generate
            project_name: Name of the project being generated
        """
        self.total_files = total_files
        self.project_name = project_name
        self.generated_files: List[str] = []
        self.current_file = ""
        self.current_index = 0

    def show_generation_start(self):
        """Show start of generation."""
        console.print(f"\n[bold cyan]🚀 Generating {self.project_name}[/bold cyan]")
        console.print(f"[dim]{self.total_files} files to generate...[/dim]\n")

    def show_file_progress(self, file_path: str, index: int, total: int):
        """
        Show progress for current file.

        Args:
            file_path: Path of current file being generated
            index: Current file index (1-based)
            total: Total files
        """
        self.current_file = file_path
        self.current_index = index

        # Calculate percentage
        percent = int((index / total) * 100)

        # Show progress bar
        bar_length = 30
        filled = int(bar_length * index / total)
        bar = "█" * filled + "░" * (bar_length - filled)

        status_line = (
            f"[cyan]{bar}[/cyan] "
            f"[bold]{index:2d}/{total}[/bold] "
            f"[yellow]{percent:3d}%[/yellow] "
            f"[dim]|[/dim] "
            f"[green]{file_path}[/green]"
        )

        console.print(status_line)

    def show_generation_complete(self, project_dir: str):
        """
        Show generation completion.

        Args:
            project_dir: Directory where project was generated
        """
        summary = Text()
        summary.append(f"\n✅ [bold green]Project generated![/bold green]\n\n")
        summary.append(f"Project: ", style="bold cyan")
        summary.append(f"{self.project_name}\n")
        summary.append(f"Location: ", style="bold cyan")
        summary.append(f"{project_dir}\n")
        summary.append(f"Files: ", style="bold cyan")
        summary.append(f"{self.total_files}")

        console.print(Panel(summary, border_style="green", padding=(1, 2)))

    def show_generation_error(self, error_msg: str, file_path: Optional[str] = None):
        """
        Show generation error.

        Args:
            error_msg: Error message
            file_path: File where error occurred (if known)
        """
        error_text = Text()
        if file_path:
            error_text.append(f"While generating: ", style="bold yellow")
            error_text.append(f"{file_path}\n\n")

        error_text.append(error_msg)

        console.print(Panel(
            error_text,
            title="❌ Generation Failed",
            border_style="red",
        ))

    def show_file_list(self, files: List[str]):
        """
        Show summary of files generated.

        Args:
            files: List of generated file paths
        """
        console.print(f"\n[bold cyan]📁 Generated Files:[/bold cyan]\n")
        for file_path in files:
            console.print(f"  ✅ {file_path}")

    def show_estimated_time(self, files: int, avg_secs_per_file: float = 2.0):
        """Show estimated time remaining."""
        remaining = max(1, files - self.current_index)
        estimated_secs = int(remaining * avg_secs_per_file)

        if estimated_secs < 60:
            time_str = f"{estimated_secs}s"
        elif estimated_secs < 3600:
            time_str = f"{estimated_secs // 60}m {estimated_secs % 60}s"
        else:
            time_str = f"{estimated_secs // 3600}h {(estimated_secs % 3600) // 60}m"

        return f"[dim]ETA: {time_str}[/dim]"


class ProgressTracker:
    """Simple progress tracker without live updating."""

    def __init__(self, total: int):
        """Initialize progress tracker."""
        self.total = total
        self.current = 0
        self.items: List[str] = []

    def add(self, item: str):
        """Add a completed item."""
        self.current += 1
        self.items.append(item)

    def get_progress_percent(self) -> int:
        """Get progress as percentage."""
        if self.total == 0:
            return 0
        return int((self.current / self.total) * 100)

    def get_summary(self) -> str:
        """Get summary of progress."""
        return f"{self.current}/{self.total} ({self.get_progress_percent()}%)"


if __name__ == "__main__":
    # Test progress display
    progress = GenerationProgress(5, "test-app")
    progress.show_generation_start()

    for i in range(1, 6):
        progress.show_file_progress(f"src/file{i}.ts", i, 5)

    progress.show_file_list([f"src/file{i}.ts" for i in range(1, 6)])
    progress.show_generation_complete("/home/user/projects/test-app")
