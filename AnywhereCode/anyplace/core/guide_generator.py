"""
Learning guide generator.

Creates QUICKSTART.md and LEARNING.md with curated resources, step-by-step
instructions, and tips tailored to each project template.
"""

from pathlib import Path
from typing import Dict, List, Optional

from anyplace.core.llm_provider import LLMProvider


# ─────────────────────────────────────────────────────────────────────────────
# Curated learning resources per template (no LLM needed — these are static)
# ─────────────────────────────────────────────────────────────────────────────

LEARNING_RESOURCES: Dict[str, Dict] = {
    "web-react-vite": {
        "docs": [
            ("React Docs", "https://react.dev"),
            ("Vite Docs", "https://vitejs.dev"),
            ("TypeScript Handbook", "https://www.typescriptlang.org/docs/"),
            ("React Router", "https://reactrouter.com"),
            ("TanStack Query", "https://tanstack.com/query"),
        ],
        "tutorials": [
            ("React Tutorial (official)", "https://react.dev/learn"),
            ("Full Stack Open", "https://fullstackopen.com"),
            ("The Odin Project", "https://www.theodinproject.com"),
        ],
        "tips": [
            "Use React DevTools browser extension to inspect component state.",
            "Start with `npm run dev` — Vite's HMR updates the browser instantly.",
            "Keep components small: one responsibility per component.",
            "Use `useState` for local state, `useContext` or Zustand for global state.",
            "Run `npm run build` and check `dist/` before deploying.",
        ],
        "next_steps": [
            "Add routing with `react-router-dom`",
            "Connect to an API with `fetch` or TanStack Query",
            "Add styling with Tailwind CSS or CSS Modules",
            "Deploy to Vercel, Netlify, or GitHub Pages",
        ],
    },
    "mobile-expo-rn": {
        "docs": [
            ("Expo Docs", "https://docs.expo.dev"),
            ("React Native Docs", "https://reactnative.dev/docs/getting-started"),
            ("EAS Build", "https://docs.expo.dev/build/introduction/"),
            ("Expo Router", "https://expo.github.io/router/docs/"),
            ("React Native Paper (UI)", "https://reactnativepaper.com"),
        ],
        "tutorials": [
            ("Expo Tutorial", "https://docs.expo.dev/tutorial/introduction/"),
            ("React Native Express", "https://www.reactnative.express"),
        ],
        "tips": [
            "Use `npx expo start` to open in Expo Go on your phone — no cable needed.",
            "Termux users: run `npx expo start --tunnel` for network access.",
            "Test on both iOS and Android simulators before submitting to EAS.",
            "Use `expo-constants` to read env vars inside the app bundle.",
            "`npx expo-doctor` will diagnose most dependency issues automatically.",
        ],
        "next_steps": [
            "Set up Expo Router for navigation",
            "Add authentication with Clerk or Supabase Auth",
            "Configure EAS Build for App Store / Play Store submission",
            "Add push notifications with `expo-notifications`",
        ],
    },
    "backend-nodejs": {
        "docs": [
            ("Node.js Docs", "https://nodejs.org/en/docs"),
            ("Express Docs", "https://expressjs.com"),
            ("TypeScript Docs", "https://www.typescriptlang.org/docs/"),
            ("Prisma ORM", "https://www.prisma.io/docs"),
            ("JWT Guide", "https://jwt.io/introduction"),
        ],
        "tutorials": [
            ("Node.js Best Practices", "https://github.com/goldbergyoni/nodebestpractices"),
            ("REST API Design Guide", "https://restfulapi.net"),
        ],
        "tips": [
            "Copy `.env.example` to `.env` and fill in your values before starting.",
            "Use `npm run dev` with nodemon/ts-node-dev for auto-restart on file changes.",
            "Always validate incoming request bodies — use Zod or Joi.",
            "Handle errors centrally with an Express error middleware.",
            "Use Prisma or Knex instead of raw SQL queries for type safety.",
        ],
        "next_steps": [
            "Set up a database (PostgreSQL with Prisma recommended)",
            "Add authentication with JWT or Passport.js",
            "Write integration tests with Supertest + Jest",
            "Deploy with Docker + PM2, or to Railway / Render / Fly.io",
        ],
    },
    "fullstack-nextjs": {
        "docs": [
            ("Next.js Docs", "https://nextjs.org/docs"),
            ("Vercel Deployment", "https://vercel.com/docs"),
            ("Prisma ORM", "https://www.prisma.io/docs"),
            ("NextAuth.js", "https://next-auth.js.org"),
        ],
        "tutorials": [
            ("Next.js Learn", "https://nextjs.org/learn"),
            ("T3 Stack", "https://create.t3.gg"),
        ],
        "tips": [
            "Use Server Components by default — opt into 'use client' only when needed.",
            "API routes live in `app/api/` — keep them thin, move logic to service files.",
            "Use `next/image` for all images for automatic optimization.",
            "Deploy to Vercel for zero-config Next.js hosting.",
        ],
        "next_steps": [
            "Set up a database with Prisma",
            "Add authentication with NextAuth.js",
            "Deploy to Vercel",
        ],
    },
    "backend-python-fastapi": {
        "docs": [
            ("FastAPI Docs", "https://fastapi.tiangolo.com"),
            ("SQLAlchemy Docs", "https://docs.sqlalchemy.org"),
            ("Pydantic Docs", "https://docs.pydantic.dev"),
            ("Alembic Migrations", "https://alembic.sqlalchemy.org"),
        ],
        "tutorials": [
            ("FastAPI Tutorial", "https://fastapi.tiangolo.com/tutorial/"),
            ("Full Stack FastAPI", "https://github.com/fastapi/full-stack-fastapi-template"),
        ],
        "tips": [
            "Run with `uvicorn main:app --reload` for development.",
            "Interactive API docs are auto-generated at `/docs` (Swagger) and `/redoc`.",
            "Use Pydantic models for request/response validation.",
            "Use `async def` for I/O-bound routes, `def` for CPU-bound ones.",
            "Manage migrations with Alembic — never edit the database schema manually.",
        ],
        "next_steps": [
            "Set up SQLAlchemy + Alembic for database migrations",
            "Add JWT auth with `python-jose`",
            "Write tests with pytest + httpx",
            "Deploy with Docker on Fly.io or Railway",
        ],
    },
}

_FALLBACK_RESOURCES = {
    "docs": [("Project Documentation", "https://docs.example.com")],
    "tutorials": [],
    "tips": ["Read the generated code carefully to understand the structure."],
    "next_steps": ["Customize the generated files for your use case."],
}


class GuideGenerator:
    """Generates learning guides for generated projects."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider

    def get_learning_resources(self, template_name: str) -> Dict:
        """Return curated learning resources for a template (no LLM)."""
        return LEARNING_RESOURCES.get(template_name, _FALLBACK_RESOURCES)

    def generate_learning_md(
        self,
        template_name: str,
        project_name: str,
    ) -> str:
        """
        Generate LEARNING.md with resources, tips, and next steps.

        Does NOT use the LLM — content is curated and deterministic.
        """
        res = self.get_learning_resources(template_name)

        lines = [
            f"# Learning Guide — {project_name}",
            "",
            f"> Generated by AnywhereCode · Template: `{template_name}`",
            "",
            "---",
            "",
            "## 📚 Official Documentation",
            "",
        ]

        for name, url in res.get("docs", []):
            lines.append(f"- [{name}]({url})")
        lines.append("")

        if res.get("tutorials"):
            lines += ["## 🎓 Tutorials & Courses", ""]
            for name, url in res["tutorials"]:
                lines.append(f"- [{name}]({url})")
            lines.append("")

        if res.get("tips"):
            lines += ["## 💡 Pro Tips", ""]
            for tip in res["tips"]:
                lines.append(f"- {tip}")
            lines.append("")

        if res.get("next_steps"):
            lines += ["## 🚀 Suggested Next Steps", ""]
            for i, step in enumerate(res["next_steps"], 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        lines += [
            "---",
            "",
            "## 🛠️ AnywhereCode Commands",
            "",
            "| Command | What it does |",
            "|---|---|",
            "| `anyplace commit` | Generate an AI commit message |",
            "| `anyplace build` | Run the project build |",
            "| `anyplace deploy` | Generate deployment config |",
            "| `anyplace ci --platform github` | Add GitHub Actions CI/CD |",
            "| `anyplace docker` | Add Docker + docker-compose |",
            "| `anyplace env` | Manage environment variables |",
            "| `anyplace docs` | Generate project documentation |",
            "",
            "_Happy coding!_",
        ]

        return "\n".join(lines)

    def generate_quickstart_md(
        self,
        template_name: str,
        project_name: str,
        tech_stack: List[str],
        next_steps: List[str],
    ) -> str:
        """
        Generate QUICKSTART.md with setup and run instructions.

        Does NOT use the LLM — content is derived from the plan.
        """
        res = self.get_learning_resources(template_name)

        # Pick the right run command per template
        run_commands = {
            "web-react-vite": "npm run dev",
            "mobile-expo-rn": "npx expo start",
            "backend-nodejs": "npm run dev",
            "fullstack-nextjs": "npm run dev",
            "backend-python-fastapi": "uvicorn main:app --reload",
        }
        run_cmd = run_commands.get(template_name, "npm start")

        install_cmd = (
            "pip install -r requirements.txt"
            if "Python" in tech_stack or "FastAPI" in tech_stack
            else "npm install"
        )

        lines = [
            f"# Quick Start — {project_name}",
            "",
            f"Tech Stack: {', '.join(tech_stack)}",
            "",
            "---",
            "",
            "## Prerequisites",
            "",
        ]

        if "Python" in tech_stack or "FastAPI" in tech_stack:
            lines += [
                "- Python 3.11+",
                "- pip",
            ]
        else:
            lines += [
                "- Node.js 20+",
                "- npm",
            ]

        if "expo-rn" in template_name or "Expo" in tech_stack:
            lines += [
                "- Expo Go app on your phone (for mobile preview)",
                "  - [iOS](https://apps.apple.com/app/expo-go/id982107779)",
                "  - [Android](https://play.google.com/store/apps/details?id=host.exp.exponent)",
            ]

        lines += [
            "",
            "## Setup",
            "",
            "```bash",
            f"# 1. Install dependencies",
            install_cmd,
            "",
            "# 2. Set up environment variables",
            "cp .env.example .env",
            "# Edit .env and fill in your values",
            "",
            f"# 3. Start development server",
            run_cmd,
            "```",
            "",
            "## Next Steps",
            "",
        ]

        if next_steps:
            for i, step in enumerate(next_steps, 1):
                lines.append(f"{i}. {step}")
        else:
            for i, step in enumerate(res.get("next_steps", []), 1):
                lines.append(f"{i}. {step}")

        lines += [
            "",
            "---",
            "",
            "> See [LEARNING.md](./LEARNING.md) for docs, tutorials, and tips.",
        ]

        return "\n".join(lines)

    def write_all(
        self,
        template_name: str,
        project_name: str,
        tech_stack: List[str],
        next_steps: List[str],
        project_dir: Path,
    ) -> List[Path]:
        """Write QUICKSTART.md and LEARNING.md to the project directory."""
        project_dir = Path(project_dir)
        written = []

        quickstart_path = project_dir / "QUICKSTART.md"
        quickstart_path.write_text(
            self.generate_quickstart_md(
                template_name, project_name, tech_stack, next_steps
            )
        )
        written.append(quickstart_path)

        learning_path = project_dir / "LEARNING.md"
        learning_path.write_text(
            self.generate_learning_md(template_name, project_name)
        )
        written.append(learning_path)

        return written
