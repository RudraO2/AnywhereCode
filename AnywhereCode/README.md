# AnywhereCode

**Code anywhere, anytime - Generate projects on your phone, laptop, or anywhere in between.**

A CLI tool for generating production-ready projects using AI. Create Android apps, web applications, full-stack projects, and more with intelligent scaffolding and guidance.

## Features

- 🎯 **AI-Powered Planning** - Plan before code: see all files before generation
- 📱 **Mobile-First** - Optimized for Termux/Android, generates to ~/Downloads for safety
- 🔌 **Multi-Provider LLM** - Use Claude, Gemini, OpenRouter, or custom models
- 🎨 **Template Boilerplate** - Templates are just structure, you control the design
- ⚡ **Sequential Generation** - Safe file dependencies with intelligent ordering
- 🛠️ **Claude Skills** - Integration with /commit, /build, /deploy skills
- 🔗 **MCP Servers** - Extensible via MCP for more capabilities

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
anyplace
```

Follow the menu to:
1. Select a project type (Web, Mobile, Backend, etc.)
2. Choose your AI provider (Claude, Gemini, OpenRouter)
3. Review the plan before generation
4. Watch as AnywhereCode generates your project
5. Start coding!

## Project Types

- **Android Native** (Kotlin)
- **React Native + Expo** (Cross-platform mobile)
- **React SPA** (Single Page App)
- **Next.js** (Full-stack)
- **Node.js API** (Backend)
- **FastAPI** (Python backend)

## Configuration

Set your API keys in `~/.config/anyplace/config.yaml`:

```yaml
# Claude
providers:
  claude:
    api_key: sk-ant-...
    model: claude-3-5-sonnet

# Google Gemini
  gemini:
    api_key: AIza...
    model: gemini-2.0-flash

# OpenRouter (access 100+ models)
  openrouter:
    api_key: sk-or-...
    model: anthropic/claude-3.5-sonnet

# Custom API endpoint
  custom:
    api_key: your-key
    base_url: https://custom-api.example.com
    model: your-model-id
```

## Docs

- [Architecture](./docs/architecture.md)
- [Templates](./docs/templates.md)
- [Contributing](./docs/contributing.md)
