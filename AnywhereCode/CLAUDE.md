# AnywhereCode - Project Context

**Repository**: `rudrao2/classic-snake-made-using-qwen-`  
**Branch**: `claude/clear-repo-fresh-start-GnCWi`  
**Status**: MVP 100% Complete ✅ (All 6 Phases Done)

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

## 📊 Current Progress

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

1. **All 6 phases are complete and on `main`**.
2. **Gemini is now properly configured** — `system_instruction` + `responseSchema` both set.
3. **Install works on Termux** — `pip install -e .` in `AnywhereCode/` with no Rust deps.
4. **Test flow**: `anyplace configure` → `anyplace main` → pick template → enter description → approve plan → files generate → git commits.
5. **If any new Gemini errors appear**, check `llm_provider.py:_call_gemini()` and `plan_generator.py:PLAN_RESPONSE_SCHEMA`.
6. **Mobile paths**: Termux uses `~/storage/downloads/` or `~/Downloads/` for project output.

---

**Last Updated**: April 2026  
**Session ID**: Latest development session  
**Branch**: `main`
