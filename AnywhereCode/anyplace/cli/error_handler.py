"""
Error handling for AnywhereCode CLI.

Provides user-friendly error messages and recovery suggestions.
"""

import sys
from typing import Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class AnyplaceError(Exception):
    """Base exception for AnywhereCode."""
    pass


class APIError(AnyplaceError):
    """API/LLM provider error."""
    pass


class ConfigError(AnyplaceError):
    """Configuration error."""
    pass


class FileSystemError(AnyplaceError):
    """File system operation error."""
    pass


class GenerationError(AnyplaceError):
    """Code generation error."""
    pass


def handle_error(error: Exception, context: Optional[str] = None):
    """
    Handle error with user-friendly message.

    Args:
        error: The exception that occurred
        context: Additional context about what was happening
    """
    error_title = "❌ Error"
    error_msg = str(error)

    # Categorize and enhance error messages
    if isinstance(error, APIError):
        error_title = "🔌 API Error"
        error_msg = enhance_api_error(error_msg)
    elif isinstance(error, ConfigError):
        error_title = "⚙️ Configuration Error"
        error_msg = enhance_config_error(error_msg)
    elif isinstance(error, FileSystemError):
        error_title = "📁 File System Error"
        error_msg = enhance_fs_error(error_msg)
    elif isinstance(error, GenerationError):
        error_title = "🔨 Generation Error"
        error_msg = enhance_generation_error(error_msg)

    # Build error panel
    panel_text = Text()
    if context:
        panel_text.append(f"While: {context}\n\n")
    panel_text.append(error_msg)

    console.print(Panel(
        panel_text,
        title=error_title,
        border_style="red",
    ))

    # Print recovery suggestion if available
    suggestion = get_recovery_suggestion(error)
    if suggestion:
        console.print(Panel(
            suggestion,
            title="💡 Try This",
            border_style="yellow",
        ))


def enhance_api_error(msg: str) -> str:
    """Enhance API error messages."""
    msg_lower = msg.lower()

    if "invalid_api_key" in msg_lower or "unauthorized" in msg_lower:
        return "API key is invalid or expired.\n\nCheck your credentials in ~/.config/anyplace/config.yaml"

    if "rate_limit" in msg_lower or "quota" in msg_lower:
        return "API quota exceeded or rate limited.\n\nWait a moment and try again, or switch to a different provider."

    if "connection" in msg_lower or "timeout" in msg_lower:
        return "Can't connect to API provider.\n\nCheck your internet connection and try again."

    if "model" in msg_lower and "not found" in msg_lower:
        return "Model ID not found with this provider.\n\nVerify the model ID is correct for your provider."

    return msg


def enhance_config_error(msg: str) -> str:
    """Enhance configuration error messages."""
    msg_lower = msg.lower()

    if "api_key" in msg_lower:
        return "API key not configured.\n\nRun: anyplace --configure\nOr edit: ~/.config/anyplace/config.yaml"

    if "provider" in msg_lower:
        return "LLM provider not configured.\n\nAvailable: claude, gemini, openrouter, custom\nRun: anyplace --configure"

    if "template" in msg_lower:
        return "Template not found.\n\nRun: anyplace --list-templates\nOr upgrade: anyplace --upgrade"

    return msg


def enhance_fs_error(msg: str) -> str:
    """Enhance file system error messages."""
    msg_lower = msg.lower()

    if "permission" in msg_lower:
        return "Permission denied.\n\nCheck that you have write permissions for the target directory."

    if "space" in msg_lower or "disk full" in msg_lower:
        return "Not enough disk space.\n\nFree up storage and try again."

    if "exists" in msg_lower:
        return "Project directory already exists.\n\nChoose a different name or delete the existing directory."

    return msg


def enhance_generation_error(msg: str) -> str:
    """Enhance generation error messages."""
    msg_lower = msg.lower()

    if "timeout" in msg_lower:
        return "Generation took too long and timed out.\n\nTry with a simpler project or check your internet connection."

    if "dependency" in msg_lower or "conflict" in msg_lower:
        return "Dependency conflict detected.\n\nConsider removing conflicting packages or updating versions."

    return msg


def get_recovery_suggestion(error: Exception) -> Optional[str]:
    """Get recovery suggestion for error."""
    msg = str(error).lower()

    if "api" in msg and "key" in msg:
        return "1. Run: anyplace --configure\n2. Enter your API key\n3. Try again"

    if "template" in msg:
        return "1. Run: anyplace --list-templates\n2. Choose an available template\n3. Try again"

    if "space" in msg or "disk" in msg:
        return "1. Free up storage space\n2. Run: anyplace again"

    if "permission" in msg:
        return "1. Check directory permissions\n2. Try a different output location\n3. Run: anyplace --help"

    return None


def exit_with_error(error: Exception, context: Optional[str] = None):
    """Print error and exit."""
    handle_error(error, context)
    sys.exit(1)


def validate_api_key(api_key: str, provider: str) -> bool:
    """
    Validate API key format.

    Args:
        api_key: The API key to validate
        provider: The provider name

    Returns:
        True if valid, False otherwise
    """
    if not api_key or not api_key.strip():
        return False

    provider = provider.lower()

    if provider == "claude":
        return api_key.startswith("sk-ant-")
    elif provider == "gemini":
        return api_key.startswith("AIza")
    elif provider == "openrouter":
        return api_key.startswith("sk-or-")
    elif provider == "custom":
        return len(api_key) > 10  # Basic check for custom keys

    return len(api_key) > 10


if __name__ == "__main__":
    # Test error handling
    try:
        raise APIError("Invalid API key: sk-invalid")
    except AnyplaceError as e:
        handle_error(e, "Testing API configuration")
