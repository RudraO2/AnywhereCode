# AnywhereCode - Project Context

**Repository**: `rudrao2/classic-snake-made-using-qwen-` (name is stale — the
repo originally held a Snake game; it now holds AnywhereCode only)  
**Branch**: `main`  
**Status**: Agentic pipeline ✅ + Cloud APK builds ✅ + Keyless free tier ✅

> **Read this first if you are picking the project up cold.** Sections below
> marked *(historical)* describe the phase-by-phase MVP build-out and are kept
> for context. The current shape of the project is in
> **[Cloud APK builds + free tokens](#-cloud-apk-builds--free-tokens-august-2026)**
> at the bottom, which supersedes anything above it that disagrees.

---

## 🎯 Vision: Termux-Based Android Coding Solution

**AnywhereCode** is an AI-powered project generator designed for developers who code **anywhere, anytime** - especially on mobile phones via Termux/Android. No laptop needed.

### Core Values:
- ✅ **Accessible** - Works on phones, laptops, anywhere
- ✅ **Mobile-First** - Safe paths on Android (~/Downloads)
- ✅ **AI-Powered** - Uses Claude, Gemini, OpenRouter
- ✅ **No Barriers** - No approval processes, just code
- ✅ **Educational** - Built for beginners to learn by doing

---

## 📊 Progress *(historical — phases 1-6)*

### ✅ Completed (Phases 1-3)

**Phase 1: CLI Framework + Mobile Safety**
- Multi-provider LLM support (Claude, Gemini, OpenRouter, custom)
- Mobile detection (Termux auto-detection)
- Safe paths (~/.anyplace/projects on desktop, ~/Downloads on Termux)
- Beautiful CLI with Rich formatting
- Configuration wizard for API keys
- ~500 lines of code

**Phase 2: Plan Generation Engine**
- AI-powered planning with Claude/Gemini
- Structured project plans showing all files
- File dependency analysis (topological sorting)
- Beautiful plan preview with approval gate
- Comprehensive error handling
- ~600 lines of code

**Phase 3: Code Generation + Git**
- Sequential file generation respecting dependencies
- LLM-powered content generation
- Git repository initialization
- Auto-commit per file (+ final bulk commit)
- Progress display with real-time feedback
- Error recovery with checkpoints
- ~1000 lines of code

**Total Code**: ~3000 lines, well-organized and tested

### ✅ Completed (Phases 4-6)

**Phase 4: Claude Skills Integration** ✅
- `anyplace commit` — LLM commit messages from git diff
- `anyplace build` — project-type-aware build runner
- `anyplace deploy` — EAS / GitHub Actions / PM2 configs
- `anyplace serve` — FastMCP server (list_templates, generate_plan, generate_project)
- Auto-injected `.claude/settings.json` + `.claude/commands/` in every project

**Phase 5: Build Services** ✅
- `anyplace ci` — GitHub Actions, GitLab CI, Bitbucket Pipelines, CircleCI
- `anyplace docker` — multi-stage Dockerfile + docker-compose (Postgres + Redis)
- `anyplace env` — .env.example generation + validation
- 2 new templates: `fullstack-nextjs`, `backend-python-fastapi`

**Phase 6: Teaching & Documentation** ✅
- `anyplace guide` — LEARNING.md with curated docs, tutorials, tips per template
- `anyplace docs` — CONTRIBUTING.md, CHANGELOG.md, API_DOCS.md
- `anyplace explain <file>` — LLM explanation of any file
- Auto-generated QUICKSTART.md + LEARNING.md in every project
- Auto-generated CONTRIBUTING.md + CHANGELOG.md in every project

---

## 🏗️ Architecture Overview

```
┌─ CLI Layer (main.py)
│  ├─ Template selection menu
│  ├─ Configuration wizard
│  └─ Command interface
│
├─ Core Generation (Plan → Code)
│  ├─ plan_generator.py (Claude/Gemini AI)
│  ├─ code_generator.py (Sequential file writing)
│  ├─ build_orchestrator.py (Coordination)
│  └─ git_manager.py (Auto-commit)
│
├─ LLM Integration
│  ├─ llm_provider.py (Multi-provider abstraction)
│  ├─ mock_llm.py (Testing without API keys)
│  └─ config/ (API key management)
│
├─ Templates (boilerplate only, NOT UI constraints)
│  ├─ web-react-vite/
│  ├─ mobile-expo-rn/
│  └─ backend-nodejs/
│
└─ Support
   ├─ error_handler.py (Comprehensive errors)
   ├─ progress.py (Beautiful display)
   └─ plan_preview.py (User approval)
```

---

## 🧪 Testing Status

### E2E Test Results: 4/4 PASSING ✅

1. **Plan Generation**: ✅ PASS
   - Generates complete project structure
   - Tech stack, features, architecture notes
   - All files listed with dependencies

2. **Plan Approval Workflow**: ✅ PASS
   - Beautiful preview with Rich formatting
   - Files grouped by type
   - Dependency visualization

3. **Code Generation**: ✅ PASS
   - Sequential file generation working
   - Progress bar (0-100%) functional
   - 5+ files generated in order

4. **Git Integration**: ✅ PASS
   - Repository initialization
   - Auto-commit per file
   - .gitignore creation

**Run test**: `python3 test_e2e.py` (uses mock LLM)

---

## 🛠️ Project Templates

Currently available (more can be added):

1. **web-react-vite** - React SPA with Vite
2. **mobile-expo-rn** - React Native cross-platform
3. **backend-nodejs** - Node.js REST API

**Important**: Templates are **boilerplate only**. Users have **full UI control** - templates don't constrain design.

---

## 🔑 Key Technical Decisions

### LLM Strategy
- **Multi-provider** via LiteLLM abstraction
- **No vendor lock-in** - switch providers easily
- **Direct API key input** - users control credentials
- **Custom endpoint support** - self-hosted LLMs possible

### Code Generation
- **Sequential** - respects file dependencies
- **Topological sorting** - prevents broken imports
- **Error recovery** - checkpoints at each file
- **Git integration** - auto-commit per file

### Mobile First
- **Termux detection** - automatic
- **Safe paths** - ~/Downloads on mobile
- **No permission hassles** - just works
- **Full CLI** - no GUI needed

### Error Handling
- **Comprehensive** - every operation covered
- **User-friendly** - no stack traces by default
- **Actionable** - suggests fixes
- **Logged** - saves to .logs/ for debugging

---

## 📝 Important Files

### Entry Points
- `anyplace/cli/main.py` - Main CLI interface
- `anyplace/__init__.py` - Package initialization

### Core Modules
- `anyplace/core/llm_provider.py` - LLM abstraction
- `anyplace/core/plan_generator.py` - AI planning
- `anyplace/core/code_generator.py` - File generation
- `anyplace/core/build_orchestrator.py` - Coordination
- `anyplace/core/git_manager.py` - Git operations

### Config & Error Handling
- `anyplace/config/api_manager.py` - API key management
- `anyplace/config/environment.py` - Mobile detection
- `anyplace/cli/error_handler.py` - Error system
- `anyplace/cli/config_wizard.py` - Setup wizard

### Testing
- `test_e2e.py` - End-to-end tests (4/4 passing)

### Documentation
- `README.md` - Project overview
- `CLAUDE.md` - This file (context for new sessions)

---

## 🚀 How to Use AnywhereCode

### Installation
```bash
cd /home/user/Classic-Snake-Made-using-Qwen-/AnywhereCode
pip install -e .
```

### Basic Usage
```bash
# Configure LLM provider
anyplace configure

# Generate a new project
anyplace main

# List templates
anyplace templates

# Test connection
anyplace test-providers

# Show system info
anyplace info
```

### Testing
```bash
# Run end-to-end tests
python3 test_e2e.py

# Test with mock LLM (no API key needed)
# - Uses MockLLMProvider internally
```

---

## 🔐 API Key Configuration

Supports multiple providers - **choose one**:

**1. Claude (Anthropic)** - Best code quality
- Get key: https://console.anthropic.com
- Format: `sk-ant-...`

**2. Gemini (Google)** - Free tier available
- Get key: https://aistudio.google.com/apikey
- Format: `AIza...`
- Note: Needs "Generative Language API" enabled

**3. OpenRouter** - Access 100+ models
- Get key: https://openrouter.ai/keys
- Format: `sk-or-...`
- No extra setup needed

**4. Custom** - Self-hosted or other APIs
- Provide: API key + custom endpoint URL

---

## ⚙️ Environment Detection

**Desktop**:
- Projects: `~/.anyplace/projects/`
- Config: `~/.config/anyplace/`

**Termux/Android**:
- Projects: `~/storage/downloads/` or `~/Downloads/`
- Config: `~/.config/anyplace/`
- Auto-detected, no manual setup

---

## 🎓 Development Guidelines

### Code Style
- Clean, well-organized Python
- Type hints where helpful
- Docstrings for public functions
- Error handling comprehensive

### Adding Features
1. Update relevant modules
2. Add to appropriate phase
3. Update E2E tests
4. Commit to branch
5. Write context in CLAUDE.md

### Adding Templates
1. Create folder: `anyplace/templates/{name}/`
2. Add `structure.json` with metadata
3. Add template files
4. Update template list in `cli/templates.py`

### Testing New Features
```bash
python3 test_e2e.py  # Run full test suite
```

---

## 📚 Next Steps for New Sessions

**If continuing Phase 4-6:**
1. Read this file for context
2. Check `anyplace/core/` for current architecture
3. Review Phase 3 in this file for dependencies
4. Run `test_e2e.py` to verify system works
5. Start building Phase 4 features

**If debugging/fixing:**
1. Identify which phase/module
2. Check error_handler.py for error patterns
3. Review test_e2e.py for test structure
4. Add new tests for new features

**If testing LLM integration:**
1. Use `anyplace configure` to add API key
2. Use `anyplace test-providers` to verify
3. Use `anyplace main` to test full flow
4. Or use `python3 test_e2e.py` with mock LLM

---

## 🎯 Success Criteria Checklist

**Phase 1**: ✅ Complete
- [ ] CLI framework working
- [ ] Mobile detection functioning
- [ ] Configuration wizard operational
- [x] All working

**Phase 2**: ✅ Complete
- [ ] Plan generation with LLM
- [ ] Plan preview system
- [ ] User approval gate
- [x] All working

**Phase 3**: ✅ Complete
- [ ] Sequential code generation
- [ ] Git integration
- [ ] Progress display
- [ ] Error recovery
- [x] All working

**Phase 4**: ⏳ Ready to Start
- [ ] Claude Skills integration
- [ ] MCP server implementation
- [ ] Auto-commit hooks

**Overall MVP**: 100% Complete ✅
- ✅ All 6 phases implemented
- ✅ 9/9 e2e tests passing
- ✅ 5 project templates
- ✅ 15 CLI commands
- ✅ MCP server for Claude integration

---

## 📞 Quick Reference

**What is AnywhereCode?**
An AI project generator for mobile developers using Termux/Android

**How does it work?**
1. User selects template
2. AI generates development plan
3. User approves plan
4. Files generated sequentially
5. Git auto-commits
6. Project ready to code

**What's unique?**
- Works on phones (Termux)
- No laptop needed
- Mobile-safe output paths
- Multiple LLM providers
- Fully open-source
- Beginner-friendly

**Current Status?**
70% MVP complete. Phases 1-3 fully tested. Phases 4-6 pending.

---

---

## ⚡ Agentic Pipeline (April 2026 — Latest Update)

**AnywhereCode is now a fully agentic CLI — like Claude Code.**

Previously, after generating files it would print "Next steps" telling the user
to manually run `npm install`, `npm run build`, etc. **No more.** The CLI now
does everything autonomously end-to-end.

### What Changed

**New file: `anyplace/core/agent_executor.py`**
- Central autonomous execution engine
- Detects project type (Node.js, Python, Rust, Go, Django, Next.js, Expo)
- Runs full pipeline: install → build → env → CI → Docker → deploy → verify
- Each step is resilient — failures don't block the pipeline
- All configs auto-committed to git

**Updated: `anyplace/core/build_orchestrator.py`**
- New `agentic=True` flag (default)
- After code generation, automatically runs the full AgentExecutor pipeline
- New `agent_callback` for live progress feedback

**Updated: `anyplace/core/build_runner.py`**
- Now detects Python, Django, Rust, Go, Next.js, Express/Fastify projects
- New `auto_install()` and `auto_build()` methods (safe, no-raise)
- `get_install_command()` returns correct command for each project type

**Updated: `anyplace/cli/main.py`**
- `anyplace main` now shows agentic pipeline results table instead of manual steps
- New `anyplace run` command — runs the agentic pipeline on any existing project
- Beautiful Rich table output showing each pipeline step status

**Updated: `anyplace/mcp/server.py`**
- `generate_project` is now fully agentic (install + build + CI + Docker + deploy)
- New `setup_project` tool — run agentic pipeline on existing project
- New `install_dependencies` tool — auto-detect and install deps
- New `build_project` tool — auto-detect and build

### How It Works Now

```
User: "anyplace main" → select template → describe project → approve plan
  ↓
AnywhereCode (AUTONOMOUS):
  1. Generate all source files
  2. Git init + commit each file
  3. npm install / pip install (auto-detected)
  4. npm run build / python -m build (auto-detected)
  5. Create .env from .env.example
  6. Generate GitHub Actions CI/CD
  7. Generate Dockerfile + docker-compose.yml
  8. Generate deployment config
  9. Verify project works
  10. Git commit all configs
  ↓
Result: Fully ready project — just `cd` into it and start coding
```

### Safety Guardrails

The agent checks EVERY command against a blocklist before executing:
- `rm -rf`, `rm --force` — **BLOCKED**
- `chmod 777`, `chmod -R` — **BLOCKED**
- `sudo`, `su -`, `killall`, `shutdown`, `reboot` — **BLOCKED**
- `git push --force`, `git reset --hard` — **BLOCKED**
- `curl | bash`, `eval`, `exec` — **BLOCKED**
- Fork bombs, disk overwrites — **BLOCKED**

Safe commands: `npm install`, `pip install`, `npm run build`, `git add`, `git commit`, etc.

### Accept Modes

- **Human-accept (default)**: User approves each pipeline step with Y/n
- **Auto-accept (`--auto`)**: Everything runs without confirmation

### Auto-Serve on Localhost

After build, the pipeline auto-starts a dev server:
- React/Vite → `npx vite --host 0.0.0.0 --port 3000`
- Next.js → `npx next dev -p 3000`
- Express/Node.js → `npm run dev` or `npm start`
- Expo → `npx expo start`
- Django → `python3 manage.py runserver 0.0.0.0:8000`
- Flask → `python3 -m flask run --host=0.0.0.0`
- FastAPI → `python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`

### One-Command Install (Termux)

```bash
curl -sL https://raw.githubusercontent.com/RudraO2/Classic-Snake-Made-using-Qwen-/main/install.sh | bash
```

This installs Python, git, Node.js, clones the repo, sets up the `anyplace` command,
and starts the config wizard. Works on Termux and Linux.

### New/Updated CLI Commands

```bash
# Just type 'anyplace' to start (no subcommand needed)
anyplace

# Create project in auto-accept mode (no confirmations)
anyplace main --auto

# Run full agentic pipeline on existing project
anyplace run --dir /path/to/project

# Auto-accept mode
anyplace run --dir /path/to/project --auto

# Skip deployment config
anyplace run --dir /path/to/project --skip-deploy
```

### New MCP Tools

```
generate_project     — FULLY AGENTIC: plan → files → install → build → CI → Docker → deploy → serve
setup_project        — Run agentic pipeline on existing project
install_dependencies — Auto-detect and install deps
build_project        — Auto-detect and build
```

---

## 🐛 Bugs Fixed (April 2026 — Latest Session)

All changes are on `main` branch. Full history in git log.

### 1. Termux install failure — `litellm` removed ✅
`litellm` pulled in `fastuuid` → `maturin` (Rust build required), which fails on `aarch64-unknown-linux-android`.  
**Fix**: Replaced `litellm` with direct `requests` HTTP calls in `llm_provider.py`. Deps now: `requests`, `click`, `pyyaml`, `rich`.

### 2. Gemini returns bullet points instead of JSON ✅
Two root causes:
- `systemInstruction` (camelCase) was silently ignored by the REST API — correct key is `system_instruction` (snake_case)
- Without `responseSchema`, Gemini treats JSON as optional ("preferred but optional")

**Fix** (`llm_provider.py` + `plan_generator.py`):
- Renamed `systemInstruction` → `system_instruction`
- Added `response_schema` parameter through the full call chain: `generate_json` → `generate_text` → `_dispatch` → `_call_gemini`
- Defined `PLAN_RESPONSE_SCHEMA` in `plan_generator.py` with UPPERCASE OpenAPI types (`"STRING"`, `"ARRAY"`, `"OBJECT"`)
- Passed schema to `generate_json` so Gemini is forced to output exact plan JSON structure

### 3. `'list' object has no attribute 'get'` ✅
Gemini occasionally wraps JSON in `[{...}]` array. `_parse_plan_response` called `.get()` on a list.  
**Fix**: `_as_dict()` helper coerces single-element list → dict. `_extract_json_from_response` only walks `{` not `[`.

### 4. `git config` fails after `git init` on Termux ✅
Error: `Failed to initialize git: fatal: not in a git directory`  
`git config user.email` ran after `git init` but Termux git couldn't find the local config immediately.  
**Fix** (`git_manager.py`): Set `self.repo_initialized = True` right after `git init` succeeds. Moved `git config` calls into a separate try/except (non-fatal). Used `--local` flag explicitly.

---

## 🚧 Known Remaining Issues

None known at time of writing. If the next session finds new bugs, add them here.

---

## 📋 What the Next Model Should Know

1. **All 6 phases are complete and on `main`** + **Agentic Pipeline is live**.
2. **AnywhereCode is now fully agentic** — no manual steps after plan approval.
3. **Safety guardrails** block `rm -rf`, `chmod 777`, `sudo`, `git push --force`, etc.
4. **Two modes**: human-accept (default, user approves each step) and auto-accept (`--auto`).
5. **Auto-serve**: After build, dev server starts on localhost automatically.
6. **One-command install**: `curl -sL .../install.sh | bash` for Termux beginners.
7. **Gemini is properly configured** — `system_instruction` + `responseSchema` both set.
8. **Install works on Termux** — no Rust deps, just `requests`, `click`, `pyyaml`, `rich`.
9. **Test flow**: `anyplace` → pick template → describe → approve plan → *everything automatic*.
10. **Key file**: `anyplace/core/agent_executor.py` — autonomous pipeline + safety + accept modes.
11. **New commands**: `anyplace run --dir <path>`, `anyplace main --auto`.
12. **MCP server** has `setup_project`, `install_dependencies`, `build_project` tools.
13. **If Gemini errors**, check `llm_provider.py:_call_gemini()` and `plan_generator.py:PLAN_RESPONSE_SCHEMA`.
14. **Mobile paths**: Termux uses `~/storage/downloads/` or `~/Downloads/`.

---

---

## 📱 Cloud APK builds + free tokens (August 2026)

**This section supersedes anything above it.** Two changes reframe what the
project is for.

### 1. `anyplace apk` — Android builds from a phone

New file: **`anyplace/core/eas_builder.py`**.

Gradle cannot realistically run inside Termux, which used to make "build an
Android app on your phone" impossible. EAS runs Gradle on Expo's servers, so
the phone only uploads source and downloads an APK.

Four failure modes are handled explicitly — each one is load-bearing, do not
"simplify" them away:

| Problem | Why it breaks | Fix in `eas_builder.py` |
|---|---|---|
| EAS defaults Android to **AAB** | An App Bundle cannot be sideloaded — you wait 15 min for an uninstallable file | `preview` profile pinned to `buildType: "apk"` |
| Missing `android.package` | eas-cli stops to ask, deadlocking `--non-interactive` | Derived via `sanitize_package_name()` |
| Missing `appVersionSource` | Same deadlock, different prompt | Defaulted to `"remote"` in `eas.json` |
| First build has no keystore | eas-cli **refuses** to generate one in `--non-interactive` | Detect that error, retry attached to the tty |

`ensure_eas_json()` and `ensure_app_config()` **merge, never overwrite** — a
user's own profiles and package name survive. Both are idempotent, so builds
don't dirty git.

Getting the APK onto a device: a terminal QR code (`anyplace/cli/qr.py`,
half-block rendering so it fits a phone screen) for a second device, or
`--install` which downloads and calls `termux-open` to launch Android's
installer on the build device itself.

Auth is via `EXPO_TOKEN` (`anyplace login-expo`), because interactive
`eas login` needs a browser round-trip that is awkward in Termux.

### 2. OmniRoute — zero-signup free tier

[OmniRoute](https://github.com/diegosouzapw/OmniRoute) is a local
OpenAI-compatible gateway pooling 90+ providers' free tiers (~1.5B
tokens/month). Its `auto` model works **with no API key**, so a new user can go
from install to generated project without an account.

- `KEYLESS_PROVIDERS` in `llm_provider.py` lets `_setup_provider` accept an
  empty key; `_call_openai_compat` omits the `Authorization` header entirely
  when there is no key (an empty bearer token gets rejected).
- `response_format` is **not** sent for omniroute — `auto` can land on any
  upstream provider and many reject it with a hard 400. JSON is coaxed via the
  system prompt plus the existing tolerant extractor instead.
- `validate_api_key()` returns True for an empty omniroute key.
- It is listed **first** in the config wizard; `quick_setup()` makes it the
  default branch on first run.

### 3. Onboarding fixes

- **Bare `anyplace` was broken.** The `__main__` guard that dispatched to
  interactive mode never ran via the `console_scripts` entry point, so
  `anyplace` printed help. Now `@click.group(invoke_without_command=True)`.
- **`curl | bash` install prompt was broken.** stdin is the script itself when
  piped, so the trailing `read` could never work. Now reads from `/dev/tty`,
  and skips when there's no terminal.
- `anyplace doctor` — checks python/git/node/storage/provider/Expo token/QR
  and prints the exact fix command for each.
- Ctrl+C in the interactive menu no longer renders an empty red error panel.

### Testing

```bash
python3 test_e2e.py     # 9 tests  — pre-existing, still green
python3 test_eas.py     # 42 tests — new, fully offline
```

`test_eas.py` fakes the subprocess boundary, so no eas-cli, network or
credentials are needed. The assertion that matters most is
*"preview profile builds an APK"* — if that ever flips to `app-bundle`, the
core promise of the project silently breaks.

### Known gaps / good next steps

- **iOS builds** — plumbing is platform-agnostic (`--platform ios`), but the
  Apple Developer credential flow is untested.
- **The repo name** is still `Classic-Snake-Made-using-Qwen-`, which costs
  discoverability. Renaming to `AnywhereCode` is an owner action.
- `eas-cli` JSON output is parsed defensively (`_parse_build_json`) because its
  shape has changed across versions — re-check against new eas-cli releases.
- OmniRoute model IDs in the wizard are illustrative; the gateway's real
  catalogue is discoverable via `omniroute_list_models()`.

---

**Last Updated**: August 2026  
**Branch**: `main`
