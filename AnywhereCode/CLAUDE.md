# Anywhere Code — context for a new session

**Repository**: `RudraO2/Classic-Snake-Made-using-Qwen-` (the repo name predates
the project; see "Naming" below)
**Package**: `anyplace` (importable name, kept for compatibility)
**Command**: `anywhere` (and `anyplace`, the v1 alias)

---

## What this is

An AI coding CLI you drive from a phone. It runs in Termux on Android, or
anywhere else Python runs. You answer a few questions, it plans a project,
writes every file, installs dependencies, builds, and starts it.

The whole product is shaped by one constraint: **a 40-column terminal and one
thumb.** That is not a nice-to-have. It decides the layout system, the prompt
design, and what counts as a bug.

---

## Naming

The GitHub repository is still `Classic-Snake-Made-using-Qwen-`, left over from
an unrelated project. The product is **Anywhere Code**. Package internals use
`anyplace` and that is deliberate — renaming the import path would break every
existing install for no user-visible gain.

If the repository is ever renamed, GitHub redirects the old URL, so the
`install.sh` one-liner keeps working. `setup.py` and `README.md` both hardcode
the URL and should be updated at the same time.

---

## Architecture

```
anyplace/
  ui/          layout, theme, components, prompts — the phone-first toolkit
  cli/         screens and commands built on ui/
  core/        interview, recommender, planner, generator, doctor, pipeline
  templates/   the six scaffolds
  mcp/         MCP server, so Claude can drive all of this
tests/         pytest suite
```

**The one rule that matters:** `core/` never imports `rich` or `click`. Every
decision the product makes is testable without a terminal. `ui/` renders; it
does not decide. There are tests asserting this separation — see
`tests/test_error_handler.py::test_error_handler_module_imports_without_rich_or_click`.

### `ui/` — the layout system

`Layout.detect()` reads the real terminal size, whether this is Termux, and
whether the font can render unicode and emoji. Everything downstream branches on
that:

| Width | Behaviour |
|---|---|
| < 40 | No boxes or bars. Stacked records, short labels. |
| 40–59 | Coloured edge bars instead of borders, one item per line. |
| 60–89 | Tables return, descriptions beside labels. |
| 90+ | Full desktop layout. |

Components (`ui/components.py`) all take an explicit `console` and `layout` so
they can be rendered into a capture buffer in tests. Prompts (`ui/prompts.py`)
take an `input_fn`, so a whole flow can be driven by a scripted list of answers.

Env vars: `ANYWHERE_WIDTH`, `ANYWHERE_THEME` (`default`/`mono`/`highcontrast`),
`NO_COLOR`.

### `core/` — the decisions

- `interview.py` — the question flow. One question per screen, every question
  has a default, `b`/`q`/`?` work everywhere.
- `recipes.py` — 17 one-tap starting points, phrased as ideas rather than
  scaffold names. Picking one pre-fills the interview.
- `recommender.py` — maps interview answers to a scaffold, with the honest
  trade-off attached ("Next.js needs a Node host — heavier from Termux").
- `doctor.py` — device diagnostics. Every check that fails carries a `fix`
  string that is a literal command the user can type.
- `session.py` — remembers projects so `anywhere open` can resume one.
- `plan_generator.py` → `code_generator.py` → `agent_executor.py` — the build
  pipeline.

---

## The safety gate

`anyplace/core/agent_executor.py::is_command_safe` is the only thing between an
LLM-chosen command and `subprocess.run`. **It is an allowlist, and it must stay
one.**

This used to be a regex denylist. It let `rm /etc/passwd` through (every `rm`
pattern required a flag), and `node -e "require('fs').rmSync('/')"`, and
`perl -e "unlink glob '/*'"`. Meanwhile it *refused* `npm run format` and any
commit message containing the word "exec". Both failure directions were real.

Four layers, in order:

1. **Shape** — argv must be a sequence of strings, or it fails closed. It does
   not raise; a gate that throws is a gate the caller might catch and ignore.
2. **Program** — `argv[0]` must be in `ALLOWED_PROGRAMS`. No shell binary is on
   that list, which is why every `bash -c "..."` payload is refused without
   needing to understand it.
3. **Arguments** — per-tool rules for tools that stay dangerous even when the
   binary is legitimate: `git push --force`, `git reset --hard`, `git clean -f`,
   `chmod 777`/`chmod -R`, and any interpreter invoked with an inline-code flag
   (`python -c`, `node -e`, `php -r`).
4. **Content** — a residual denylist over the joined command, to catch a payload
   smuggled through an allowed program: `npm run clean -- "rm -rf /"`.

If you add a build tool the pipeline needs, add it to `ALLOWED_PROGRAMS` and add
a test in `tests/test_agent_executor_safety.py` proving the ordinary invocation
is allowed. Do not widen the content denylist to compensate.

**Be honest about its scope.** The gate checks the commands the pipeline issues;
it cannot inspect what those commands go on to run. `npm install` executes
postinstall scripts from the registry, and `npm run build` executes a script the
LLM wrote into `package.json`. That is inherent to setting up a generated
project. The gate is a guardrail against the agent issuing something
destructive, not a sandbox — don't let the README or the UI imply otherwise.

`tests/test_agent_executor_safety.py` also checks the gate against the pipeline
in the other direction: it scans the argv literals in `build_runner.py` and
`agent_executor.py` and asserts the gate allows every one. A gate that refuses a
command the pipeline itself issues isn't secure, it's broken — the build stops
halfway with a message the user can do nothing about.

---

## Providers

Four keyed providers (Gemini, Claude, OpenRouter, custom) and one keyless one
(OmniRoute). Claude and Gemini have bespoke request builders; OpenRouter,
OmniRoute and custom all share the OpenAI-compatible path in
`llm_provider._call_openai_compat`.

**Keyless providers are a real state, not an edge case.** `KEYLESS_PROVIDERS`
lives in `anyplace/config/providers.py` — a module that imports nothing, so
`core.doctor` (which may not import `anyplace.cli`) and the CLI can both use
it. Three places branch on it:

- `validate_api_key` accepts an empty key for those providers.
- `_call_openai_compat` omits the `Authorization` header entirely when there is
  no key — sending `Bearer ` with nothing after it makes some servers refuse.
- `check_providers` does not report a missing key as a failure for them.

If you add another keyless provider, adding it to that frozenset is the whole
change.

**Two Claude details that bite:** `temperature` is rejected with a 400 on the
Claude 5 family and Opus 4.7/4.8, so `supports_sampling()` gates whether it
goes in the body at all; and model ids are exact — never append a date suffix
to `claude-haiku-4-5` and friends.

---

## Tests

```bash
cd AnywhereCode
python -m pytest          # ~2170 tests, about 9 seconds
```

No test touches the network, your home directory, or a real LLM.

Three suites are worth knowing about because they catch classes of bug rather
than single defects:

- **`test_command_hints_are_real.py`** — reads every string literal in the
  user-facing modules and fails if it advertises a command or flag the CLI does
  not have. This found `anyplace --configure`, a flag that never existed, in
  five separate doctor checks. A wrong hint is worse than no hint: the user is
  already stuck, types what you told them, and the shell says "no such command".
- **`test_readme_is_accurate.py`** — checks the README's scaffold table, recipe
  count and command examples against what the code actually ships.
- **`test_cli_smoke.py`** — invokes `--help` on every command. Most modules are
  imported lazily inside command bodies to keep startup fast on a phone, so a
  broken import would otherwise stay invisible until a user ran that one
  command.

Also: `test_e2e.py` and `test_json_fix.py` at the package root are standalone
integration scripts (they use the mock LLM and real git). Run them directly with
`python test_e2e.py`. They are not collected by pytest.

### Writing tests here

Assert on behaviour the user could notice. The UI suites render components into
a capture console at each breakpoint and assert no line exceeds the terminal
width — that is a real bug users hit, so it is a real assertion. Prompt suites
use `scripted_input([...])` rather than mocking click.

If you find a bug, fix it and let the test pass. Do not leave a `xfail(strict)`
marker describing a defect you could have fixed — the suite had 18 of those and
every one was a real, fixable bug.

---

## Conventions

- Templates are starting files, not a cage. The LLM writes the real code.
- Every template's `structure.json` carries human-facing metadata: a
  `display_name` short enough for a narrow screen, a `tagline`, `good_for`,
  `not_for`, and an honest `mobile_friendly` flag. `tests/test_templates_metadata.py`
  enforces the lengths.
- Every recipe must reference a template that ships, and every template must
  have at least one recipe.
- Errors go through `cli/error_handler.py`. A stack trace on a phone is four
  screens of noise you cannot copy out. Every failure becomes one line plus the
  command that fixes it.
- Don't add a command without adding it to `COMMAND_GROUPS` in `cli/main.py`.
  It will still appear in `--help` under "More" — there's a test for that — but
  it belongs in a real group.
