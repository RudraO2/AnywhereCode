"""
Environment variable manager.

Generates .env.example with documented variables per project type,
and validates that a .env file isn't missing any required variables.
"""

from pathlib import Path
from typing import Dict, List

from anyplace.cli.error_handler import GenerationError


# Curated env vars per template — key: var name, value: description + example
_TEMPLATE_ENV_VARS: Dict[str, List[Dict]] = {
    "react-vite": [
        {
            "name": "VITE_APP_TITLE",
            "description": "Application display name",
            "example": "My App",
            "required": False,
        },
        {
            "name": "VITE_API_URL",
            "description": "Backend API base URL",
            "example": "http://localhost:3000/api",
            "required": True,
        },
        {
            "name": "VITE_APP_ENV",
            "description": "Environment (development | staging | production)",
            "example": "development",
            "required": False,
        },
    ],
    "expo-rn": [
        {
            "name": "EXPO_PUBLIC_API_URL",
            "description": "Backend API base URL (exposed to the app bundle)",
            "example": "https://api.example.com",
            "required": True,
        },
        {
            "name": "EXPO_PUBLIC_APP_NAME",
            "description": "Application display name",
            "example": "My App",
            "required": False,
        },
        {
            "name": "EXPO_TOKEN",
            "description": "EAS / Expo authentication token (CI only, never commit)",
            "example": "your-expo-token-here",
            "required": False,
        },
    ],
    "nodejs": [
        {
            "name": "NODE_ENV",
            "description": "Runtime environment (development | test | production)",
            "example": "development",
            "required": True,
        },
        {
            "name": "PORT",
            "description": "HTTP server port",
            "example": "3000",
            "required": False,
        },
        {
            "name": "DATABASE_URL",
            "description": "PostgreSQL connection string",
            "example": "postgresql://user:password@localhost:5432/mydb",
            "required": True,
        },
        {
            "name": "JWT_SECRET",
            "description": "Secret key for signing JWT tokens — use a long random string",
            "example": "change-me-to-a-long-random-secret",
            "required": True,
        },
        {
            "name": "REDIS_URL",
            "description": "Redis connection URL (optional — for caching/sessions)",
            "example": "redis://localhost:6379",
            "required": False,
        },
        {
            "name": "CORS_ORIGIN",
            "description": "Allowed CORS origin(s), comma-separated",
            "example": "http://localhost:5173",
            "required": False,
        },
        {
            "name": "LOG_LEVEL",
            "description": "Logging verbosity (debug | info | warn | error)",
            "example": "info",
            "required": False,
        },
    ],
    "unknown": [
        {
            "name": "NODE_ENV",
            "description": "Runtime environment",
            "example": "development",
            "required": False,
        },
    ],
}


class EnvManager:
    """Manages environment variable configuration for generated projects."""

    def get_vars_for_type(self, project_type: str) -> List[Dict]:
        """Return the env var definitions for a project type."""
        return _TEMPLATE_ENV_VARS.get(project_type, _TEMPLATE_ENV_VARS["unknown"])

    def generate_env_example(
        self,
        project_type: str,
        project_name: str = "app",
    ) -> str:
        """
        Generate a well-documented .env.example file.

        Args:
            project_type: Detected project type string
            project_name: Name of the project (used in header)

        Returns:
            .env.example content as a string
        """
        vars_list = self.get_vars_for_type(project_type)

        lines = [
            f"# Environment variables for {project_name}",
            "# Copy this file to .env and fill in the values.",
            "# Lines starting with # are comments.",
            "# Variables marked REQUIRED must be set before running.",
            "",
        ]

        required = [v for v in vars_list if v.get("required")]
        optional = [v for v in vars_list if not v.get("required")]

        if required:
            lines += ["# ── Required ──────────────────────────────────────────", ""]
            for var in required:
                lines.append(f"# {var['description']}")
                lines.append(f"{var['name']}={var['example']}")
                lines.append("")

        if optional:
            lines += ["# ── Optional ──────────────────────────────────────────", ""]
            for var in optional:
                lines.append(f"# {var['description']}")
                lines.append(f"# {var['name']}={var['example']}")
                lines.append("")

        return "\n".join(lines)

    def write_env_example(
        self,
        project_dir: Path,
        project_type: str,
        project_name: str = "app",
    ) -> Path:
        """Write .env.example to the project directory and return its path."""
        env_path = Path(project_dir) / ".env.example"
        env_path.write_text(
            self.generate_env_example(project_type, project_name)
        )
        return env_path

    def validate_env(self, project_dir: Path) -> Dict:
        """
        Compare .env against .env.example and report missing/extra/ok vars.

        Args:
            project_dir: Project directory containing .env and .env.example

        Returns:
            Dict with keys "missing", "extra", "ok" — each a list of var names

        Raises:
            GenerationError: If .env.example does not exist
        """
        project_dir = Path(project_dir)
        example_path = project_dir / ".env.example"
        env_path = project_dir / ".env"

        if not example_path.exists():
            raise GenerationError(
                ".env.example not found. Run 'anyplace env' to generate one."
            )

        def _parse_env_file(path: Path) -> Dict[str, str]:
            result = {}
            if not path.exists():
                return result
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    result[key.strip()] = val.strip()
            return result

        # Parse .env.example — only lines that are NOT commented out
        example_vars = _parse_env_file(example_path)
        env_vars = _parse_env_file(env_path)

        example_keys = set(example_vars)
        env_keys = set(env_vars)

        return {
            "missing": sorted(example_keys - env_keys),
            "extra": sorted(env_keys - example_keys),
            "ok": sorted(example_keys & env_keys),
        }

    def list_vars(self, project_dir: Path) -> List[str]:
        """List all variable names defined in .env.example."""
        example_path = Path(project_dir) / ".env.example"
        if not example_path.exists():
            return []

        names = []
        for line in example_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, _ = line.partition("=")
                names.append(key.strip())
        return names
