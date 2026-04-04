# AnywhereCode - Project Context

**Repository**: `rudrao2/classic-snake-made-using-qwen-`  
**Branch**: `claude/clear-repo-fresh-start-GnCWi`  
**Status**: MVP 70% Complete (Phases 1-3 Done ✅)

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

### ⏳ Pending (Phases 4-6)

**Phase 4: Claude Skills Integration**
- `/commit` skill for auto-commit messages
- `/build` skill for build orchestration
- `/deploy` skill for EAS/GitHub Actions
- `.claude/hooks/` for auto-operations
- MCP server implementation

**Phase 5: Build Services**
- EAS Build for mobile apps
- GitHub Actions CI/CD templates
- Deployment automation

**Phase 6: Teaching & Documentation**
- Interactive guides per template
- Learning resource links
- Best practices documentation

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

**Overall MVP**: 70% Complete
- ✅ Core functionality done
- ✅ Fully tested
- ✅ Ready for Phase 4-6

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

**Last Updated**: April 2026  
**Session ID**: Latest development session  
**Branch**: `claude/clear-repo-fresh-start-GnCWi`
