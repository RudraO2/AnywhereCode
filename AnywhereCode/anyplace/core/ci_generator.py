"""
CI/CD pipeline generator.

Generates complete CI/CD configurations for GitHub Actions, GitLab CI,
Bitbucket Pipelines, and CircleCI — adapted per project type.
"""

from pathlib import Path
from typing import Dict

from anyplace.core.build_runner import BuildRunner


class CIGenerator:
    """Generates CI/CD pipeline configs for multiple platforms."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.runner = BuildRunner(self.project_dir)
        self.project_type = self.runner._detect_project_type()

    # ─────────────────────────────────────────────
    # GitHub Actions
    # ─────────────────────────────────────────────

    def _github_ci_yml(self) -> str:
        """CI workflow: lint + test on every PR."""
        node_version = "20"
        if self.project_type == "expo-rn":
            test_step = "      - run: npx expo-doctor"
        else:
            test_step = "      - run: npm test --if-present"

        return f"""name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '{node_version}'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint --if-present

{test_step}

      - name: Build
        run: npm run build --if-present
"""

    def _github_deploy_yml(self) -> str:
        """Deploy workflow triggered on push to main."""
        if self.project_type == "expo-rn":
            deploy_steps = """
      - name: Setup Expo & EAS
        uses: expo/expo-github-action@v8
        with:
          eas-version: latest
          token: ${{ secrets.EXPO_TOKEN }}

      - name: Build & submit to EAS
        run: eas build --platform all --non-interactive
"""
        elif self.project_type == "react-vite":
            deploy_steps = """
      - name: Build
        run: npm run build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist
"""
        else:  # nodejs
            deploy_steps = """
      - name: Build
        run: npm run build

      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd ~/app
            git pull
            npm ci --production
            pm2 restart app
"""

        return f"""name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci
{deploy_steps}
"""

    def generate_github_actions(self) -> Dict[str, str]:
        """Return dict of filepath -> content for GitHub Actions workflows."""
        return {
            ".github/workflows/ci.yml": self._github_ci_yml(),
            ".github/workflows/deploy.yml": self._github_deploy_yml(),
        }

    # ─────────────────────────────────────────────
    # GitLab CI
    # ─────────────────────────────────────────────

    def generate_gitlab_ci(self) -> Dict[str, str]:
        """Return .gitlab-ci.yml content."""
        if self.project_type == "expo-rn":
            build_script = "npx expo export"
            deploy_script = "eas build --platform all --non-interactive"
        else:
            build_script = "npm run build"
            deploy_script = "# TODO: add deploy command"

        content = f"""stages:
  - install
  - lint
  - build
  - deploy

variables:
  NODE_VERSION: "20"

cache:
  key: $CI_COMMIT_REF_SLUG
  paths:
    - node_modules/

install:
  stage: install
  image: node:$NODE_VERSION
  script:
    - npm ci

lint:
  stage: lint
  image: node:$NODE_VERSION
  script:
    - npm run lint --if-present

build:
  stage: build
  image: node:$NODE_VERSION
  script:
    - {build_script}
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour

deploy:
  stage: deploy
  image: node:$NODE_VERSION
  script:
    - {deploy_script}
  only:
    - main
  when: manual
"""
        return {".gitlab-ci.yml": content}

    # ─────────────────────────────────────────────
    # Bitbucket Pipelines
    # ─────────────────────────────────────────────

    def generate_bitbucket_pipelines(self) -> Dict[str, str]:
        """Return bitbucket-pipelines.yml content."""
        build_cmd = (
            "npx expo export"
            if self.project_type == "expo-rn"
            else "npm run build"
        )

        content = f"""image: node:20

pipelines:
  default:
    - step:
        name: Install & Lint
        caches:
          - node
        script:
          - npm ci
          - npm run lint --if-present

    - step:
        name: Build
        caches:
          - node
        script:
          - npm ci
          - {build_cmd}

  branches:
    main:
      - step:
          name: Install & Lint
          caches:
            - node
          script:
            - npm ci
            - npm run lint --if-present

      - step:
          name: Build & Deploy
          deployment: production
          caches:
            - node
          script:
            - npm ci
            - {build_cmd}
            - echo "Add deploy commands here"

definitions:
  caches:
    node: node_modules
"""
        return {"bitbucket-pipelines.yml": content}

    # ─────────────────────────────────────────────
    # CircleCI
    # ─────────────────────────────────────────────

    def generate_circleci(self) -> Dict[str, str]:
        """Return .circleci/config.yml content."""
        build_cmd = (
            "npx expo export"
            if self.project_type == "expo-rn"
            else "npm run build"
        )

        content = f"""version: 2.1

orbs:
  node: circleci/node@5

jobs:
  build-and-test:
    docker:
      - image: cimg/node:20.0

    steps:
      - checkout

      - node/install-packages:
          pkg-manager: npm

      - run:
          name: Lint
          command: npm run lint --if-present

      - run:
          name: Test
          command: npm test --if-present

      - run:
          name: Build
          command: {build_cmd}

      - persist_to_workspace:
          root: .
          paths:
            - dist

  deploy:
    docker:
      - image: cimg/node:20.0

    steps:
      - checkout
      - attach_workspace:
          at: .
      - run:
          name: Deploy
          command: echo "Add deploy command here"

workflows:
  ci-cd:
    jobs:
      - build-and-test
      - deploy:
          requires:
            - build-and-test
          filters:
            branches:
              only: main
"""
        return {".circleci/config.yml": content}

    # ─────────────────────────────────────────────
    # Unified entry point
    # ─────────────────────────────────────────────

    def generate(self, platform: str) -> Dict[str, str]:
        """
        Generate CI/CD config for the given platform.

        Args:
            platform: "github" | "gitlab" | "bitbucket" | "circle"

        Returns:
            Dict of {relative_filepath: content} — files are also written to disk.
        """
        platform_map = {
            "github": self.generate_github_actions,
            "gitlab": self.generate_gitlab_ci,
            "bitbucket": self.generate_bitbucket_pipelines,
            "circle": self.generate_circleci,
        }

        if platform not in platform_map:
            from anyplace.cli.error_handler import GenerationError
            raise GenerationError(
                f"Unknown platform '{platform}'. "
                f"Supported: {', '.join(platform_map)}"
            )

        files = platform_map[platform]()

        # Write files to disk
        for rel_path, content in files.items():
            full_path = self.project_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        return files
