"""
Docker config generator.

Generates Dockerfile, docker-compose.yml, and .dockerignore
adapted to the project type.
"""

from pathlib import Path
from typing import Dict

from anyplace.core.build_runner import BuildRunner


class DockerGenerator:
    """Generates Docker configuration files for a project."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.runner = BuildRunner(self.project_dir)
        self.project_type = self.runner._detect_project_type()

    # ─────────────────────────────────────────────
    # Dockerfile
    # ─────────────────────────────────────────────

    def generate_dockerfile(self) -> str:
        """Generate a multi-stage Dockerfile for the project type."""

        if self.project_type == "react-vite":
            return """# ── Stage 1: Build ────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Serve with nginx ──────────────────────────
FROM nginx:alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html

# Optional: custom nginx config
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
"""

        if self.project_type == "nodejs":
            return """# ── Stage 1: Build ────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json tsconfig*.json ./
RUN npm ci

COPY src ./src
RUN npm run build

# ── Stage 2: Production image ─────────────────────────
FROM node:20-alpine AS runner

ENV NODE_ENV=production
WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

EXPOSE 3000

USER node
CMD ["node", "dist/index.js"]
"""

        if self.project_type == "expo-rn":
            # Expo can't be containerized like a server, but we can containerize
            # the web export
            return """# ── Expo Web Export + nginx ───────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npx expo export --platform web

# ── Stage 2: Serve ────────────────────────────────────
FROM nginx:alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

        # Fallback
        return """FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

EXPOSE 3000
CMD ["npm", "start"]
"""

    # ─────────────────────────────────────────────
    # docker-compose.yml
    # ─────────────────────────────────────────────

    def generate_compose(self) -> str:
        """Generate docker-compose.yml with app + common services."""

        if self.project_type == "react-vite":
            return """version: '3.9'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "80:80"
    restart: unless-stopped
"""

        if self.project_type == "nodejs":
            return """version: '3.9'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-appuser}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secret}
      POSTGRES_DB: ${DB_NAME:-appdb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  postgres_data:
"""

        if self.project_type == "expo-rn":
            return """version: '3.9'

# Expo web build served via nginx
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "80:80"
    restart: unless-stopped
"""

        return """version: '3.9'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    restart: unless-stopped
"""

    # ─────────────────────────────────────────────
    # .dockerignore
    # ─────────────────────────────────────────────

    def generate_dockerignore(self) -> str:
        """Generate .dockerignore to keep image lean."""
        return """node_modules
npm-debug.log*
dist
build
.next
out
.expo

.env
.env.local
.env.*.local

.git
.gitignore
.dockerignore
Dockerfile
docker-compose*.yml

*.md
.DS_Store
.vscode
.idea

coverage
.nyc_output
__tests__
*.test.ts
*.spec.ts
"""

    # ─────────────────────────────────────────────
    # Unified entry point
    # ─────────────────────────────────────────────

    def generate(self, docker_type: str = "all") -> Dict[str, str]:
        """
        Generate Docker files.

        Args:
            docker_type: "dockerfile" | "compose" | "all"

        Returns:
            Dict of {relative_filepath: content} — files also written to disk.
        """
        files: Dict[str, str] = {}

        if docker_type in ("dockerfile", "all"):
            files["Dockerfile"] = self.generate_dockerfile()

        if docker_type in ("compose", "all"):
            files["docker-compose.yml"] = self.generate_compose()

        if docker_type == "all":
            files[".dockerignore"] = self.generate_dockerignore()

        for rel_path, content in files.items():
            full_path = self.project_dir / rel_path
            full_path.write_text(content)

        return files
