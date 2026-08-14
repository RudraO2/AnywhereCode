# AnywhereCode — Architecture & Design Notes

Internal notes for people working *on* AnywhereCode. For usage, see the
[README](../README.md).

---

## Why this project exists

Millions of people own a phone and no laptop. The blocker to shipping real
software from a phone was never the editor — it was the build. Gradle cannot
realistically run inside Termux on Android, which put native apps out of reach.

AnywhereCode closes that gap by moving builds to the cloud and making
everything else work on-device.

Design values, in priority order:

1. **Nothing may require a laptop.** If a feature only works on desktop, it is
   not done.
2. **Nothing may require a credit card.** The default path uses free providers.
3. **No native build dependencies.** Every Python dependency is pure Python —
   anything needing a Rust or C toolchain fails on Termux/aarch64 and locks out
   the platform this tool exists for. This is why `litellm` was removed in
   favour of direct `requests` calls.
4. **No unexplained manual steps.** After plan approval the pipeline runs to
   completion on its own.

---

## Layout

```
anyplace/
├── cli/
│   ├── main.py           command surface (~20 commands)
│   ├── config_wizard.py  provider setup, quick_setup() first-run path
│   ├── plan_preview.py   plan approval screen
│   ├── progress.py       generation progress display
│   ├── templates.py      template discovery
│   ├── qr.py             half-block terminal QR codes
│   └── error_handler.py  error types + validate_api_key()
├── core/
│   ├── llm_provider.py       multi-provider HTTP abstraction
│   ├── plan_generator.py     AI planning + PLAN_RESPONSE_SCHEMA
│   ├── code_generator.py     dependency-ordered file generation
│   ├── build_orchestrator.py coordinates plan → code → pipeline
│   ├── agent_executor.py     autonomous pipeline + command blocklist
│   ├── eas_builder.py        cloud APK builds
│   ├── build_runner.py       project-type detection, install/build
│   ├── git_manager.py        init + auto-commit
│   ├── ci_generator.py       GitHub Actions / GitLab / Bitbucket / Circle
│   ├── docker_generator.py   Dockerfile + compose
│   ├── deploy_generator.py   EAS / PM2 / Actions deploy configs
│   ├── env_manager.py        .env.example generation + validation
│   ├── guide_generator.py    LEARNING.md
│   ├── doc_generator.py      CONTRIBUTING / CHANGELOG / API docs
│   ├── commit_generator.py   commit messages from diffs
│   ├── hooks_injector.py     agent-tooling config for generated projects
│   └── mock_llm.py           deterministic LLM for offline tests
├── config/
│   ├── api_manager.py    config.yaml, chmod 600, provider + settings storage
│   └── environment.py    Termux detection, safe paths
├── templates/            5 templates, structure only
└── mcp/server.py         MCP server exposing the tool to agent clients
```

---

## Generation flow

```
template + description
   ↓  plan_generator      LLM → structured plan (files, deps, tech stack)
   ↓  plan_preview        user approves
   ↓  code_generator      topologically sorted file writes
   ↓  git_manager         init + commit per file
   ↓  agent_executor      install → build → env → CI → Docker → deploy → serve
```

Files are generated in dependency order so imports never reference a file that
does not exist yet.

---

## Cloud APK builds (`anyplace apk`)

`core/eas_builder.py`. The phone uploads source; Expo's servers run Gradle; the
phone downloads an APK.

Four workarounds here are **load-bearing — do not "simplify" them away**:

| Problem | Why it breaks | Fix |
|---|---|---|
| EAS defaults Android to **AAB** | App Bundles cannot be sideloaded — you'd wait 15 min for an uninstallable file | `preview` profile pinned to `buildType: "apk"` |
| Missing `android.package` | eas-cli stops to ask, deadlocking `--non-interactive` | Derived via `sanitize_package_name()` |
| Missing `appVersionSource` | Same deadlock, different prompt | Defaulted to `"remote"` |
| First build has no keystore | eas-cli **refuses** to generate one non-interactively | Detect that error, retry attached to the tty |

`ensure_eas_json()` and `ensure_app_config()` **merge, never overwrite**, so a
user's own profiles and package name survive. Both are idempotent — repeated
builds must not dirty git.

Delivery to a device: a terminal QR code (`cli/qr.py`, half-block rendering so
it fits a phone screen) for a second device, or `--install` to download and
hand the file to Android's installer via `termux-open`.

Auth uses `EXPO_TOKEN` (`anyplace login-expo`) because interactive
`eas login` needs a browser round-trip that is awkward inside Termux.

---

## LLM providers

`core/llm_provider.py` speaks four dialects over plain `requests`:

| Provider | Endpoint | Notes |
|---|---|---|
| OmniRoute | local `:20128/v1` | OpenAI-compatible, **works with no API key** |
| OpenRouter | `openrouter.ai/api/v1` | OpenAI-compatible, `:free` models on $0 balance |
| Anthropic | `api.anthropic.com/v1/messages` | native Messages API |
| Google | `generativelanguage.googleapis.com` | native, uses `responseSchema` |
| Custom | user-supplied | any OpenAI-compatible endpoint |

Provider-specific gotchas already solved — re-introducing any of these will
break JSON planning:

- **Google requires `system_instruction` (snake_case).** The camelCase
  `systemInstruction` is silently ignored by the REST API.
- **Google needs `responseSchema`** to treat JSON as mandatory rather than
  preferred. `PLAN_RESPONSE_SCHEMA` uses UPPERCASE OpenAPI types (`"STRING"`,
  `"ARRAY"`, `"OBJECT"`).
- **Responses are sometimes wrapped in a single-element array.** `_as_dict()`
  unwraps it so callers never hit `'list' object has no attribute 'get'`.
- **OmniRoute must not receive `response_format`.** Its `auto` model can route
  to any of hundreds of upstreams, many of which reject the field with a hard
  400. JSON is coaxed via the system prompt plus the tolerant extractor.
- **Keyless providers must omit the `Authorization` header entirely.** An empty
  bearer token is rejected; a missing header is accepted.

`KEYLESS_PROVIDERS` governs which providers may be configured without a key.

---

## Safety

`agent_executor.py` checks **every** command against `BLOCKED_PATTERNS` before
execution. Refused: `rm -rf`, `chmod 777`, `chmod -R`, `sudo`, `su -`,
`killall`, `shutdown`, `mkfs`, `dd if=`, `curl | bash`, `git push --force`,
`git reset --hard`, `git clean -f`, fork bombs, disk overwrites.

This matters more than usual here: the commands come from an LLM, and the
target is someone's personal phone.

Two accept modes — human-accept (default, confirm each step) and auto-accept
(`--auto`).

Config lives in `~/.config/anyplace/config.yaml`, written `chmod 600` because
it holds API keys and the Expo token.

---

## Platform paths

| | Projects | Config |
|---|---|---|
| Termux/Android | `~/storage/downloads/` (fallback `~/Downloads`) | `~/.config/anyplace/` |
| Desktop | `~/.anyplace/projects/` | `~/.config/anyplace/` |

Termux is detected via `/data/data/com.termux`, `TERMUX_APP_PID`, or `PREFIX`.

---

## Templates

Five ship today: `web-react-vite`, `mobile-expo-rn`, `backend-nodejs`,
`fullstack-nextjs`, `backend-python-fastapi`.

Templates are **boilerplate only** — structure, not design. They must never
constrain the generated UI.

Adding one: create `anyplace/templates/<name>/structure.json`. Discovery is
automatic (any directory containing `structure.json` is picked up), so no
registry edit is needed.

---

## Testing

```bash
python3 test_e2e.py      #  9 tests — full generation flow against mock_llm
python3 test_eas.py      # 42 tests — EAS config repair, parsing, QR, providers
python3 test_json_fix.py #      JSON extraction edge cases
```

All three run **offline with no API keys**. `test_eas.py` fakes the subprocess
boundary, so eas-cli is never invoked.

The single most important assertion is *"preview profile builds an APK"*. If
that ever flips to `app-bundle`, the core promise of the project breaks
silently — users wait 15 minutes for a file they cannot install.

---

## Known gaps

- **A live `anyplace apk` run against real eas-cli is unverified.** Config
  generation, output parsing and failure paths are covered by tests, but the
  end-to-end cloud build needs an Expo account to exercise.
- **iOS builds** — `--platform ios` is plumbed through but the Apple Developer
  credential flow is untested.
- **eas-cli JSON output shape has changed across versions.** `_parse_build_json`
  is deliberately defensive; re-check against new releases.
- **OmniRoute model IDs in the wizard are illustrative.** The gateway's real
  catalogue is discoverable via `omniroute_list_models()`.
- **No CI on this repo itself** — the test suites are offline and fast, so a
  GitHub Actions workflow running all three would be cheap to add.

---

## Conventions

- Pure-Python dependencies only (see design value 3).
- Errors raise the typed exceptions in `cli/error_handler.py`; the CLI renders
  them through `handle_error` / `exit_with_error` rather than printing
  tracebacks.
- Pipeline steps are resilient: one failure records a failed step and continues,
  rather than aborting the run.
