"""
Environment detection and configuration.

Detects platform (desktop vs Termux) and sets appropriate paths.
"""

import os
import platform
from pathlib import Path


def is_termux():
    """Detect if running in Termux environment."""
    return (
        os.path.exists("/data/data/com.termux") or
        os.environ.get("TERMUX_APP_PID") is not None or
        "/com.termux" in os.environ.get("PREFIX", "")
    )


def get_projects_dir():
    """Get safe projects directory based on platform."""
    if is_termux():
        # On Termux, use Downloads folder (safe location)
        downloads = Path.home() / "storage" / "downloads"
        if downloads.exists():
            return downloads

        # Fallback to ~/Downloads if storage link not available
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        return downloads
    else:
        # On desktop, use ~/.anyplace/projects
        projects = Path.home() / ".anyplace" / "projects"
        projects.mkdir(parents=True, exist_ok=True)
        return projects


def get_config_dir():
    """Get configuration directory."""
    config_dir = Path.home() / ".config" / "anyplace"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_platform_info():
    """Get platform information."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "is_termux": is_termux(),
        "projects_dir": str(get_projects_dir()),
        "config_dir": str(get_config_dir()),
    }


if __name__ == "__main__":
    info = get_platform_info()
    for key, value in info.items():
        print(f"{key}: {value}")
