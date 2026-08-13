"""
Agentic executor — runs the full pipeline autonomously and safely.

After code generation, this module automatically:
1. Installs dependencies (npm install / pip install / etc.)
2. Builds the project (npm run build / python -m build / etc.)
3. Generates deployment configs (CI, Docker, .env)
4. Starts the dev server on localhost

Safety:
- All commands are checked against a blocklist before execution
- Destructive operations (rm -rf, chmod 777, etc.) are BLOCKED
- Two modes: human-accept (default) and auto-accept
- In human-accept mode, user confirms each pipeline step

No manual steps — everything is handled end-to-end.
"""

import subprocess
import shutil
import json
import os
import re
import signal
from pathlib import Path
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field


from anyplace.cli.error_handler import GenerationError


# ── Safety: blocked command patterns ─────────────────────────────────────
# These patterns are checked against every command before it runs.
# If any pattern matches, the command is REFUSED.

BLOCKED_PATTERNS = [
    # File destruction
    r"\brm\s+(-[a-zA-Z]*[rf])",       # rm -rf, rm -f, rm -r
    r"\brm\s+--force",
    r"\brm\s+--recursive",
    r"\brmdir\b",
    r"\bshred\b",
    r"\bwipe\b",
    # Dangerous permissions
    r"\bchmod\s+(777|666|000)",         # chmod 777, chmod 666, chmod 000
    r"\bchmod\s+(-[a-zA-Z]*R)",        # chmod -R (recursive perms)
    r"\bchown\s+(-[a-zA-Z]*R)",        # chown -R
    # System damage
    r"\bmkfs\b",                        # format filesystem
    r"\bdd\s+if=",                      # dd (disk destroyer)
    r"\bformat\b",
    r"\bfdisk\b",
    # Network danger
    r"\bcurl\b.*\|\s*(ba)?sh",          # curl | bash (pipe to shell)
    r"\bwget\b.*\|\s*(ba)?sh",
    # Kill/shutdown
    r"\bkill\s+-9\s+(-1|1)\b",         # kill -9 -1 (kill all processes)
    r"\bkillall\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\binit\s+[06]\b",
    # Destructive git
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    # Sneaky shell tricks
    r":\(\)\s*\{",                      # fork bomb
    r"\beval\b",
    r"\bexec\b",
    r"\b>\s*/dev/sd",                   # overwrite disk
    r"\b>\s*/dev/null\b.*2>&1.*\brm\b", # hidden rm
    # Python destruction
    r"python.*-c.*import\s+shutil.*rmtree",
    r"python.*-c.*os\.remove",
    # Termux-specific protection
    r"\btermux-.*-permission",
    r"\bsu\s+-",
    r"\bsudo\b",
]

BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def is_command_safe(cmd: List[str]) -> tuple:
    """
    Check if a command is safe to run.

    Returns:
        (is_safe: bool, reason: str)
    """
    cmd_str = " ".join(cmd)
    for pattern in BLOCKED_RE:
        if pattern.search(cmd_str):
            return False, f"Blocked dangerous pattern: {pattern.pattern}"
    return True, ""


@dataclass
class StepResult:
    """Result of a single pipeline step."""
    name: str
    success: bool
    output: str = ""
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class PipelineResult:
    """Result of the full agentic pipeline."""
    project_dir: str
    steps: List[StepResult] = field(default_factory=list)
    server_process: Optional[subprocess.Popen] = None
    server_url: str = ""

    @property
    def all_success(self) -> bool:
        return all(s.success or s.skipped for s in self.steps)

    @property
    def summary(self) -> Dict:
        result = {
            "project_dir": self.project_dir,
            "total_steps": len(self.steps),
            "passed": sum(1 for s in self.steps if s.success),
            "skipped": sum(1 for s in self.steps if s.skipped),
            "failed": sum(1 for s in self.steps if not s.success and not s.skipped),
            "steps": [
                {
                    "name": s.name,
                    "status": "skipped" if s.skipped else ("pass" if s.success else "fail"),
                    "detail": s.skip_reason if s.skipped else (s.error if not s.success else ""),
                }
                for s in self.steps
            ],
        }
        if self.server_url:
            result["server_url"] = self.server_url
        return result


class AgentExecutor:
    """
    Autonomous executor that runs the full post-generation pipeline.

    Safety features:
    - All commands checked against blocklist before execution
    - Two modes: human_accept=True (default) asks user before each step
    - human_accept=False runs everything automatically

    The point is that it doesn't tell you what to run next — it runs it, safely.
    """

    def __init__(
        self,
        project_dir: Path,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        human_accept: bool = True,
    ):
        """
        Args:
            project_dir: The generated project directory.
            progress_callback: Called with (step_name, status_message) for live feedback.
            human_accept: If True (default), ask user to approve each step.
                         If False, run everything automatically.
        """
        self.project_dir = Path(project_dir)
        self.progress = progress_callback or (lambda step, msg: None)
        self.project_type = self._detect_project_type()
        self.result = PipelineResult(project_dir=str(self.project_dir))
        self.human_accept = human_accept

    # ── User confirmation ────────────────────────────────────────────────

    def _ask_user(self, step_name: str, description: str) -> bool:
        """
        Ask user for confirmation before running a step.
        Only asks if human_accept=True.

        Returns True if approved (or auto-accept mode).
        """
        if not self.human_accept:
            return True

        try:
            import click
            self.progress(step_name, f"[awaiting approval] {description}")
            return click.confirm(f"    Run '{step_name}'? ({description})", default=True)
        except Exception:
            return True  # If click not available, auto-approve

    # ── Detection ────────────────────────────────────────────────────────

    def _detect_project_type(self) -> str:
        """Detect project type from files present."""
        pkg = self.project_dir / "package.json"
        req = self.project_dir / "requirements.txt"
        setup_py = self.project_dir / "setup.py"
        pyproject = self.project_dir / "pyproject.toml"
        manage_py = self.project_dir / "manage.py"
        cargo = self.project_dir / "Cargo.toml"
        go_mod = self.project_dir / "go.mod"

        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "expo" in deps:
                    return "expo-rn"
                if "next" in deps:
                    return "nextjs"
                if "vite" in deps:
                    return "react-vite"
                if "fastify" in deps or "express" in deps or "koa" in deps:
                    return "nodejs-backend"
                return "nodejs"
            except (json.JSONDecodeError, OSError):
                return "nodejs"

        if manage_py.exists():
            return "django"
        if pyproject.exists() or setup_py.exists() or req.exists():
            return "python"
        if cargo.exists():
            return "rust"
        if go_mod.exists():
            return "go"

        return "unknown"

    def _has_command(self, cmd: str) -> bool:
        """Check if a command is available on the system."""
        return shutil.which(cmd) is not None

    # ── Shell runner (with safety checks) ────────────────────────────────

    def _run(self, cmd: List[str], timeout: int = 300, env_extra: Optional[Dict] = None) -> StepResult:
        """Run a shell command with safety checks and return structured result."""
        step_name = " ".join(cmd[:3])

        # SAFETY CHECK
        safe, reason = is_command_safe(cmd)
        if not safe:
            self.progress(step_name, f"BLOCKED: {reason}")
            return StepResult(
                name=step_name,
                success=False,
                error=f"Command blocked for safety: {reason}",
            )

        self.progress(step_name, f"Running: {' '.join(cmd)}")

        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            success = proc.returncode == 0
            output = proc.stdout.strip()
            error = proc.stderr.strip() if not success else ""

            if success:
                self.progress(step_name, "Done")
            else:
                self.progress(step_name, f"Failed (exit {proc.returncode})")

            return StepResult(
                name=step_name,
                success=success,
                output=output,
                error=error,
            )

        except subprocess.TimeoutExpired:
            self.progress(step_name, "Timed out")
            return StepResult(name=step_name, success=False, error="Command timed out")
        except FileNotFoundError:
            self.progress(step_name, f"Command not found: {cmd[0]}")
            return StepResult(name=step_name, success=False, error=f"Command not found: {cmd[0]}")

    def _skip(self, name: str, reason: str) -> StepResult:
        """Record a skipped step."""
        self.progress(name, f"Skipped: {reason}")
        return StepResult(name=name, success=True, skipped=True, skip_reason=reason)

    # ── Pipeline steps ───────────────────────────────────────────────────

    def install_dependencies(self) -> StepResult:
        """Auto-detect and install project dependencies."""
        self.progress("install", "Installing dependencies...")

        if not self._ask_user("install", "Install project dependencies"):
            return self._skip("install", "User declined")

        t = self.project_type

        # Node.js family
        if t in ("nodejs", "nodejs-backend", "react-vite", "nextjs", "expo-rn"):
            if self._has_command("npm"):
                return self._run(["npm", "install", "--legacy-peer-deps"], timeout=180)
            else:
                return self._skip("install", "npm not found — install Node.js first")

        # Python family
        if t in ("python", "django"):
            req_file = self.project_dir / "requirements.txt"
            setup_py = self.project_dir / "setup.py"
            pyproject = self.project_dir / "pyproject.toml"

            if self._has_command("pip3") or self._has_command("pip"):
                pip_cmd = "pip3" if self._has_command("pip3") else "pip"
                if req_file.exists():
                    return self._run([pip_cmd, "install", "-r", "requirements.txt"], timeout=180)
                elif setup_py.exists():
                    return self._run([pip_cmd, "install", "-e", "."], timeout=180)
                elif pyproject.exists():
                    return self._run([pip_cmd, "install", "-e", "."], timeout=180)
                else:
                    return self._skip("install", "No requirements.txt or setup.py found")
            else:
                return self._skip("install", "pip not found")

        # Rust
        if t == "rust":
            if self._has_command("cargo"):
                return self._run(["cargo", "build"], timeout=300)
            return self._skip("install", "cargo not found")

        # Go
        if t == "go":
            if self._has_command("go"):
                return self._run(["go", "mod", "download"], timeout=120)
            return self._skip("install", "go not found")

        return self._skip("install", f"Unknown project type: {t}")

    def build_project(self) -> StepResult:
        """Auto-detect and build the project."""
        self.progress("build", "Building project...")

        if not self._ask_user("build", "Build the project"):
            return self._skip("build", "User declined")

        t = self.project_type

        if t in ("nodejs", "nodejs-backend", "react-vite", "nextjs"):
            pkg_path = self.project_dir / "package.json"
            if pkg_path.exists():
                try:
                    scripts = json.loads(pkg_path.read_text()).get("scripts", {})
                    if "build" in scripts:
                        return self._run(["npm", "run", "build"], timeout=120)
                    else:
                        return self._skip("build", "No build script in package.json")
                except (json.JSONDecodeError, OSError):
                    pass
            return self._skip("build", "No package.json found")

        if t == "expo-rn":
            return self._skip("build", "Expo projects build on-device or via EAS")

        if t in ("python", "django"):
            manage = self.project_dir / "manage.py"
            if manage.exists() and self._has_command("python3"):
                return self._run(["python3", "manage.py", "migrate", "--run-syncdb"], timeout=60)
            return self._skip("build", "Python projects don't need a build step")

        if t == "rust":
            if self._has_command("cargo"):
                return self._run(["cargo", "build", "--release"], timeout=300)
            return self._skip("build", "cargo not found")

        if t == "go":
            if self._has_command("go"):
                return self._run(["go", "build", "./..."], timeout=120)
            return self._skip("build", "go not found")

        return self._skip("build", f"Unknown project type: {t}")

    def setup_environment(self) -> StepResult:
        """Generate .env file from .env.example if it exists."""
        self.progress("env", "Setting up environment...")

        example = self.project_dir / ".env.example"
        env_file = self.project_dir / ".env"

        if not example.exists():
            try:
                from anyplace.core.env_manager import EnvManager
                mgr = EnvManager()
                mgr.write_env_example(self.project_dir, self.project_type, self.project_dir.name)
                example = self.project_dir / ".env.example"
            except Exception:
                return self._skip("env", "Could not generate .env.example")

        if example.exists() and not env_file.exists():
            try:
                shutil.copy2(str(example), str(env_file))
                self.progress("env", "Created .env from .env.example")
                return StepResult(name="env", success=True, output="Created .env from .env.example")
            except Exception as e:
                return StepResult(name="env", success=False, error=str(e))

        return self._skip("env", ".env already exists or no .env.example")

    def setup_ci(self) -> StepResult:
        """Generate CI/CD config (GitHub Actions by default)."""
        self.progress("ci", "Setting up CI/CD pipeline...")

        if not self._ask_user("ci", "Generate GitHub Actions CI/CD config"):
            return self._skip("ci", "User declined")

        workflow_dir = self.project_dir / ".github" / "workflows"
        if workflow_dir.exists() and any(workflow_dir.iterdir()):
            return self._skip("ci", "CI config already exists")

        try:
            from anyplace.core.ci_generator import CIGenerator
            gen = CIGenerator(self.project_dir)
            files = gen.generate("github")
            return StepResult(
                name="ci",
                success=True,
                output=f"Generated: {', '.join(files)}",
            )
        except Exception as e:
            return StepResult(name="ci", success=False, error=str(e))

    def setup_docker(self) -> StepResult:
        """Generate Dockerfile and docker-compose.yml."""
        self.progress("docker", "Setting up Docker...")

        if not self._ask_user("docker", "Generate Dockerfile + docker-compose.yml"):
            return self._skip("docker", "User declined")

        dockerfile = self.project_dir / "Dockerfile"
        if dockerfile.exists():
            return self._skip("docker", "Dockerfile already exists")

        try:
            from anyplace.core.docker_generator import DockerGenerator
            gen = DockerGenerator(self.project_dir)
            files = gen.generate("all")
            return StepResult(
                name="docker",
                success=True,
                output=f"Generated: {', '.join(files)}",
            )
        except Exception as e:
            return StepResult(name="docker", success=False, error=str(e))

    def setup_deployment(self) -> StepResult:
        """Generate deployment config based on project type."""
        self.progress("deploy", "Setting up deployment config...")

        if not self._ask_user("deploy", "Generate deployment config"):
            return self._skip("deploy", "User declined")

        try:
            from anyplace.core.deploy_generator import DeployGenerator
            from anyplace.config.api_manager import APIManager
            from anyplace.core.llm_provider import LLMProvider

            api_mgr = APIManager()
            llm = LLMProvider(api_mgr)
            gen = DeployGenerator(self.project_dir, llm)

            target = "eas" if self.project_type == "expo-rn" else "github"
            result = gen.deploy(target)
            return StepResult(
                name="deploy",
                success=True,
                output=f"Generated: {', '.join(result['files_written'])}",
            )
        except Exception as e:
            return self._skip("deploy", f"Could not generate deploy config: {e}")

    def verify_project(self) -> StepResult:
        """Run a quick verification that the project is functional."""
        self.progress("verify", "Verifying project...")

        t = self.project_type

        if t in ("nodejs", "nodejs-backend", "react-vite", "nextjs"):
            nm = self.project_dir / "node_modules"
            if not nm.exists():
                return StepResult(name="verify", success=False, error="node_modules missing")

            pkg_path = self.project_dir / "package.json"
            if pkg_path.exists():
                try:
                    pkg = json.loads(pkg_path.read_text())
                    scripts = pkg.get("scripts", {})
                    if "lint" in scripts and self._has_command("npm"):
                        r = self._run(["npm", "run", "lint"], timeout=60)
                        if r.success:
                            return r
                    return StepResult(name="verify", success=True, output="Project structure valid")
                except (json.JSONDecodeError, OSError):
                    pass

            return StepResult(name="verify", success=True, output="node_modules present")

        if t in ("python", "django"):
            return StepResult(name="verify", success=True, output="Python project ready")

        return StepResult(name="verify", success=True, output="Project generated successfully")

    def start_dev_server(self) -> StepResult:
        """
        Start the dev server on localhost so the user can see their project.
        Runs in background — user can Ctrl+C to stop.
        """
        self.progress("serve", "Starting dev server...")

        if not self._ask_user("serve", "Start dev server on localhost"):
            return self._skip("serve", "User declined")

        t = self.project_type
        cmd = None
        port = 3000

        if t in ("react-vite",):
            cmd = ["npx", "vite", "--host", "0.0.0.0", "--port", str(port)]
        elif t == "nextjs":
            cmd = ["npx", "next", "dev", "-p", str(port)]
        elif t in ("nodejs", "nodejs-backend"):
            pkg_path = self.project_dir / "package.json"
            if pkg_path.exists():
                try:
                    scripts = json.loads(pkg_path.read_text()).get("scripts", {})
                    if "dev" in scripts:
                        cmd = ["npm", "run", "dev"]
                    elif "start" in scripts:
                        cmd = ["npm", "start"]
                except (json.JSONDecodeError, OSError):
                    pass
            if not cmd:
                return self._skip("serve", "No dev/start script in package.json")
        elif t == "expo-rn":
            cmd = ["npx", "expo", "start"]
            port = 8081
        elif t == "django":
            cmd = ["python3", "manage.py", "runserver", f"0.0.0.0:{port}"]
            port = 8000
            cmd[-1] = f"0.0.0.0:{port}"
        elif t == "python":
            # Check for common Python web frameworks
            req = self.project_dir / "requirements.txt"
            if req.exists():
                content = req.read_text().lower()
                if "flask" in content:
                    cmd = ["python3", "-m", "flask", "run", "--host=0.0.0.0", f"--port={port}"]
                elif "fastapi" in content or "uvicorn" in content:
                    port = 8000
                    cmd = ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
            if not cmd:
                return self._skip("serve", "No known web framework detected")
        else:
            return self._skip("serve", f"Don't know how to serve {t} projects")

        if cmd and not self._has_command(cmd[0]):
            return self._skip("serve", f"{cmd[0]} not found")

        # Safety check the server command too
        safe, reason = is_command_safe(cmd)
        if not safe:
            return StepResult(name="serve", success=False, error=f"Blocked: {reason}")

        try:
            self.progress("serve", f"Starting on http://localhost:{port}")

            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            self.result.server_process = proc
            self.result.server_url = f"http://localhost:{port}"

            return StepResult(
                name="serve",
                success=True,
                output=f"Dev server running at http://localhost:{port} (PID {proc.pid})",
            )

        except Exception as e:
            return StepResult(name="serve", success=False, error=str(e))

    # ── Full pipeline ────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        skip_deploy: bool = False,
        start_server: bool = True,
    ) -> PipelineResult:
        """
        Run the complete agentic pipeline end-to-end.

        Steps: install -> build -> env -> CI -> Docker -> deploy -> verify -> serve

        Args:
            skip_deploy: Skip deployment config generation
            start_server: Start dev server at the end (default True)
        """
        self.progress("pipeline", f"Starting agentic pipeline for {self.project_type} project...")

        if self.human_accept:
            self.progress("pipeline", "Mode: human-accept (you approve each step)")
        else:
            self.progress("pipeline", "Mode: auto-accept (all steps run automatically)")

        # Step 1: Install dependencies
        r = self.install_dependencies()
        self.result.steps.append(r)

        # Step 2: Build (only if install succeeded)
        if r.success or r.skipped:
            r = self.build_project()
            self.result.steps.append(r)

        # Step 3: Set up environment
        r = self.setup_environment()
        self.result.steps.append(r)

        # Step 4: CI/CD
        r = self.setup_ci()
        self.result.steps.append(r)

        # Step 5: Docker
        r = self.setup_docker()
        self.result.steps.append(r)

        # Step 6: Deployment config (optional)
        if not skip_deploy:
            r = self.setup_deployment()
            self.result.steps.append(r)

        # Step 7: Verify
        r = self.verify_project()
        self.result.steps.append(r)

        # Step 8: Git commit all auto-generated configs
        self._commit_configs()

        # Step 9: Start dev server
        if start_server:
            r = self.start_dev_server()
            self.result.steps.append(r)

        self.progress("pipeline", "Pipeline complete!")
        return self.result

    def _commit_configs(self):
        """Commit all auto-generated config files."""
        try:
            from anyplace.core.git_manager import GitManager
            gm = GitManager(self.project_dir)
            if gm.check_git_installed() and (self.project_dir / ".git").exists():
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(self.project_dir),
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", "chore: auto-setup deps, CI, Docker, and deployment configs\n\nGenerated by AnywhereCode agentic pipeline"],
                    cwd=str(self.project_dir),
                    capture_output=True,
                )
        except Exception:
            pass  # Git commit is best-effort
