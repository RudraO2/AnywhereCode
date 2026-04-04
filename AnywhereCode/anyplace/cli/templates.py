"""
Template management - List and load project templates.

Handles discovery and information about available project templates.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from anyplace.cli.error_handler import ConfigError


def get_templates_dir() -> Path:
    """Get the templates directory path."""
    # Templates are in the package
    pkg_dir = Path(__file__).parent.parent
    templates_dir = pkg_dir / "templates"
    return templates_dir


def list_available_templates() -> List[str]:
    """List all available project templates."""
    templates_dir = get_templates_dir()

    if not templates_dir.exists():
        return []

    # Find all template directories
    templates = []
    for item in templates_dir.iterdir():
        if item.is_dir() and (item / "structure.json").exists():
            templates.append(item.name)

    return sorted(templates)


def get_template_info(template_name: str) -> Dict:
    """
    Get information about a template.

    Args:
        template_name: Name of the template

    Returns:
        Dictionary with template information

    Raises:
        ConfigError: If template not found
    """
    template_dir = get_templates_dir() / template_name
    structure_file = template_dir / "structure.json"

    if not structure_file.exists():
        raise ConfigError(f"Template '{template_name}' not found")

    try:
        with open(structure_file, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid template structure: {e}")
    except IOError as e:
        raise ConfigError(f"Can't read template: {e}")


def get_template_files(template_name: str) -> List[str]:
    """
    Get list of files in a template.

    Args:
        template_name: Name of the template

    Returns:
        List of file paths relative to template root
    """
    info = get_template_info(template_name)
    return info.get("files_to_generate", [])


def get_template_path(template_name: str) -> Path:
    """Get the absolute path to a template directory."""
    return get_templates_dir() / template_name


def validate_template(template_name: str) -> bool:
    """
    Validate that a template is properly structured.

    Args:
        template_name: Name of the template

    Returns:
        True if valid, False otherwise
    """
    try:
        info = get_template_info(template_name)
        # Check required fields
        required = ["name", "type", "description"]
        return all(field in info for field in required)
    except ConfigError:
        return False


# Default template list (fallback if template files missing)
DEFAULT_TEMPLATES = {
    "android-native-kotlin": {
        "name": "android-native-kotlin",
        "type": "mobile",
        "description": "Android app with Kotlin and Jetpack Compose",
        "tech_stack": ["Kotlin", "Jetpack Compose", "Android Studio"],
        "key_features": [
            "Modern Android development",
            "Jetpack architecture components",
            "Material Design 3"
        ],
        "estimated_time": "20 minutes"
    },
    "mobile-expo-rn": {
        "name": "mobile-expo-rn",
        "type": "mobile",
        "description": "Cross-platform app with React Native & Expo",
        "tech_stack": ["React Native", "Expo", "TypeScript"],
        "key_features": [
            "One codebase for iOS & Android",
            "Easy deployment via EAS Build",
            "Hot reload during development"
        ],
        "estimated_time": "15 minutes"
    },
    "web-react-vite": {
        "name": "web-react-vite",
        "type": "web",
        "description": "Single-page app with React & Vite",
        "tech_stack": ["React", "Vite", "TypeScript"],
        "key_features": [
            "Fast build with Vite",
            "Component-based architecture",
            "Hot module replacement"
        ],
        "estimated_time": "10 minutes"
    },
    "fullstack-nextjs": {
        "name": "fullstack-nextjs",
        "type": "fullstack",
        "description": "Full-stack app with Next.js & PostgreSQL",
        "tech_stack": ["Next.js", "PostgreSQL", "TypeScript"],
        "key_features": [
            "API routes out of the box",
            "Server-side rendering",
            "Database integration"
        ],
        "estimated_time": "25 minutes"
    },
    "backend-nodejs": {
        "name": "backend-nodejs",
        "type": "backend",
        "description": "REST API with Node.js & Express",
        "tech_stack": ["Node.js", "Express", "PostgreSQL"],
        "key_features": [
            "RESTful API design",
            "Async/await patterns",
            "Database integration"
        ],
        "estimated_time": "15 minutes"
    },
    "backend-python-fastapi": {
        "name": "backend-python-fastapi",
        "type": "backend",
        "description": "Modern Python API with FastAPI",
        "tech_stack": ["Python", "FastAPI", "SQLAlchemy"],
        "key_features": [
            "Auto-generated documentation",
            "Type hints and validation",
            "ASGI server"
        ],
        "estimated_time": "15 minutes"
    },
}


def get_default_template_info(template_name: str) -> Optional[Dict]:
    """Get default template info if template files missing."""
    return DEFAULT_TEMPLATES.get(template_name)


if __name__ == "__main__":
    # Test template discovery
    templates = list_available_templates()
    print(f"Found {len(templates)} templates:")
    for template in templates:
        try:
            info = get_template_info(template)
            print(f"  • {template}: {info.get('description', 'N/A')}")
        except ConfigError:
            print(f"  • {template}: ERROR")
