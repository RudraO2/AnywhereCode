# Anywhere Code

**Build and ship real projects from your phone.**

Anywhere Code is an AI coding CLI designed for a 40-column terminal and one
thumb. It runs in [Termux](https://termux.dev) on Android, on a laptop, or
anywhere else Python runs. You answer a few questions, it plans the project,
writes every file, installs the dependencies, builds it, and starts it.

No laptop. No IDE. No copy-pasting from a chat window.

```
 ███  █   █ █   █ █   █ █   █ █████ ████  █████     ████  ███  ████  █████
█   █ ██  █  █ █  █   █ █   █ █     █   █ █        █     █   █ █   █ █
█████ █ █ █   █   █ █ █ █████ ████  ████  ████     █     █   █ █   █ ████
█   █ █  ██   █   ██ ██ █   █ █     █  █  █        █     █   █ █   █ █
█   █ █   █   █   █   █ █   █ █████ █   █ █████     ████  ███  ████  █████
Build and ship from a phone.
```

…and this is the same app at 34 columns, which is where you'll actually be:

```
▌ ANYWHERE CODE
▌ Build and ship from a phone.

AI     gemini · gemini-2.0-flash
Where  Termux

What now?
1. Build something new
   Answer a few questions
2. Open a project
   3 saved
3. Run this folder
4. Check my setup
5. AI provider
6. What is this?
7. Quit
1-7 pick · q quit
```

---

## Install

**Termux, Linux or macOS — one command:**

```bash
curl -sL https://raw.githubusercontent.com/RudraO2/Classic-Snake-Made-using-Qwen-/main/install.sh | bash
```

It installs Python, git and Node if they're missing, sets up the `anywhere`
command, and offers to add your AI key. Re-running it updates in place.

**Or from a clone:**

```bash
git clone https://github.com/RudraO2/Classic-Snake-Made-using-Qwen-.git
cd Classic-Snake-Made-using-Qwen-/AnywhereCode
pip install -e .
anywhere
```

You need one AI provider key. [Google Gemini](https://aistudio.google.com/apikey)
has a free tier and is the fastest way to get going.

---

## Use it

```bash
anywhere              # open the app
```

That's the whole interface. Everything else is a shortcut:

```bash
anywhere new          # start a project
anywhere open         # reopen one you made
anywhere doctor       # check this device for problems
anywhere configure    # add or change your AI key
anywhere recipes      # see the ready-made ideas
anywhere run --dir .  # set up and run the project you're standing in
```

### What happens when you say "build something new"

1. **You pick a starting point.** Tap an idea ("Habit tracker", "Online store"),
   answer a handful of questions, or just describe it in one line — your call.
2. **It recommends a scaffold and tells you why.** Including the honest
   trade-offs: "Next.js needs a Node host — heavier to run from Termux."
3. **It plans first.** You see every file it intends to write, grouped by kind,
   before a single byte hits disk.
4. **It builds.** Files are written in dependency order, each one committed to
   git as it lands.
5. **It sets the project up.** Installs dependencies, builds, writes `.env`,
   adds CI and Docker config, and starts the dev server.

You approve each step. `--auto` skips the approvals if you'd rather it just ran.

---

## Built for a small screen

This is the part most CLI tools skip. Anywhere Code treats terminal width as a
first-class input:

| Width | What you get |
|---|---|
| **< 40 cols** | No boxes, no bars, no wasted column. Stacked records, short labels. |
| **40–59 cols** | Coloured edge bars instead of borders, one item per line. |
| **60–89 cols** | Tables return when the columns fit; otherwise records, in full. |
| **90+ cols** | The full desktop layout. |

Concretely:

- **Nothing ever wraps into mush.** Every component is width-tested from 30 to
  120 columns; a rendered line is never wider than the terminal.
- **Tables become records when a table would lie.** The choice isn't width
  alone: four columns of long text at 60 columns technically *fit*, as eleven
  characters each — `Native Andr…`, `A Python RE…` — which tells you nothing. A
  table is drawn only when every column that has to be trimmed still has enough
  room to read; otherwise the same data is stacked as `Label: value` records,
  in full.
- **Emoji have ASCII fallbacks.** Many Termux fonts render emoji as tofu, and a
  double-width glyph corrupts every layout calculation downstream. Set
  `ANYWHERE_THEME=mono` and you get `[ok]` instead of `✅`.
- **Enter always means "yes, the obvious one".** Every question has a default.
  Typing on a phone is expensive, so you shouldn't have to.
- **`b` goes back, `q` quits, `?` explains** — from any question, at any depth.
- **Options match on prefixes.** "we" picks "Web app". You don't have to hunt
  for the number.

- **`--help` fits too.** Click lays options and commands out as a two-column
  table with a fixed name column; below roughly 30 columns the descriptions run
  off the edge, on the one command a stuck user reaches for. Both lists stack
  instead, and the commands are grouped by task rather than listed
  alphabetically.

Environment variables: `ANYWHERE_WIDTH` forces a width, `ANYWHERE_THEME` picks
`default` / `mono` / `highcontrast`, and `NO_COLOR` is respected.
`ANYWHERE_WIDTH` reaches the renderer, not just the layout logic — so pinning it
genuinely changes what is drawn.

---

## `anywhere doctor`

Termux breaks in a small number of very predictable ways. Doctor finds them and
prints the exact command that fixes each one:

- Python too old, git or Node missing
- `termux-setup-storage` never run, so projects can't reach `~/Downloads`
- `~/.local/bin` not on `PATH` — the reason `anywhere: command not found`
  happens right after a successful install
- Terminal too narrow to render anything
- Under 500 MB free, which `node_modules` will eat instantly
- No AI provider configured, or a key that's set but unusable
- No network

It never prints your API key.

---

## Project ideas built in

Seventeen one-tap starting points across all six scaffolds — portfolio site,
landing page, link in bio, countdown timer, data dashboard, todo app, notes app,
blog, expense tracker, online store, business API, chat bot backend, webhook
receiver, URL shortener, habit tracker, photo journal, Android home widget.

Picking one pre-answers the interview. You can still change anything afterwards.

## Scaffolds

| Scaffold | What it's for | Level | Runs on a phone |
|---|---|---|---|
| React web app | A fast single-page site in the browser | beginner | yes |
| Express API | A Node REST API in TypeScript | intermediate | yes |
| FastAPI API | A Python REST API with docs built in | intermediate | yes |
| Next.js app | Pages plus a database in one project | intermediate | needs a real host |
| Expo mobile app | One app for iPhone and Android | advanced | build on desktop/CI |
| Android (Kotlin) | Native Android with Jetpack Compose | advanced | build on desktop/CI |

Scaffolds are starting files, not a cage. The AI writes the actual code, and you
own every line of it.

---

## Working on an existing project

```bash
anywhere open                    # pick from your projects
anywhere commit --dir .          # writes the commit message from your diff
anywhere build --dir .           # detect the project type and build it
anywhere explain src/App.tsx     # what does this file do?
anywhere docs --dir .            # README, CONTRIBUTING, CHANGELOG
anywhere guide --dir .           # a learning guide for this stack
anywhere env --validate          # check .env against .env.example
anywhere ci --dir .              # GitHub Actions, GitLab, Bitbucket, Circle
anywhere docker --dir .          # Dockerfile + compose
anywhere deploy --dir .          # EAS / GitHub Actions deployment config
```

---

## Safety

The agentic pipeline runs real commands on your device, so every command is
checked before it runs — against an **allowlist**, not a list of things to
avoid.

A denylist of dangerous spellings can never be complete: `rm` has a dozen
equivalents, and any interpreter with an inline-code flag (`python -c`,
`node -e`) can express all of them in a form no regex anticipates. So the gate
works the other way round. It knows the build tools this pipeline needs — npm,
pip, cargo, go, git and a handful more — and refuses everything else, including
every shell binary. On top of that sit per-tool rules (`git push --force`,
`chmod -R` and `python -c` are refused even though git, chmod and python are
allowed) and a residual check for a dangerous payload smuggled through an
allowed tool, like `npm run clean -- "rm -rf /"`.

Anything it cannot fully understand — a malformed argv, an unrecognised
program — is refused rather than guessed at.

**What this does not protect against.** The gate checks the commands *it*
issues. It cannot inspect what those commands then run: `npm install` executes
`postinstall` scripts from the dependency tree, and `npm run build` executes a
script the AI wrote into `package.json`. Setting up a generated project means
running that project's code, and no allowlist can change that.

So the gate is a guardrail against the agent being talked into something
destructive — not a sandbox. Treat a generated project the way you'd treat any
repository you just cloned: it is code you haven't read yet. If that matters for
what you're building, run it somewhere disposable.

By default you approve each step before it runs. Your API key is stored in
`~/.config/anyplace/config.yaml` with `0600` permissions and never leaves the
device except to reach the provider you chose.

---

## AI providers

| Provider | Key format | Notes |
|---|---|---|
| Google Gemini | `AIza…` | Free tier — start here |
| Claude | `sk-ant-…` | Best code quality; defaults to Claude Opus 5 |
| OpenRouter | `sk-or-…` | One key, 100+ models |
| OmniRoute | none | A gateway you run yourself — see below |
| Custom | anything | Any OpenAI-compatible endpoint, including local |

Configure with `anywhere configure`. It reads your key back masked so you can
spot a paste error, then tests the connection immediately instead of failing
three screens later.

### OmniRoute

[OmniRoute](https://github.com/diegosouzapw/OmniRoute) is an open-source AI
gateway: one OpenAI-compatible endpoint in front of ~340 providers. Anywhere
Code speaks to it as a first-class provider, and it is the only one that needs
**no API key** — the gateway holds whatever keys you gave *it*.

```bash
npm install -g omniroute      # Node is already installed by install.sh
omniroute                     # answers on localhost:20128
anywhere configure            # pick OmniRoute, no key to paste
```

Worth knowing before you rely on it:

- **It is self-hosted, not a service.** There is no URL to sign up for. It runs
  on your device, which on a phone means a Node process sitting in memory
  alongside everything else, and it has to be running whenever you build.
- **"Free tokens" means aggregated free tiers, not a pool someone hands you.**
  OmniRoute documents roughly 1.5B free tokens per month across ~43 provider
  free tiers — but about 1B of that is Mistral alone, and nearly all of it
  needs you to sign up with each provider and give OmniRoute the key. The
  genuinely keyless providers (Pollinations, DuckDuckGo, Uncloseai) are
  rate-limited rather than token-capped.
- **Free tiers move.** Gemini cut its free limits substantially in late 2025.
  Treat any headline number as a snapshot.

If you just want something that works with one key and no background service,
Gemini's free tier is still the shortest path.

---

## Development

```bash
cd AnywhereCode
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest        # the whole suite
```

The suite is real pytest with real assertions: rendering is verified at seven
terminal widths, prompts are driven by scripted input, and no test touches the
network, your home directory, or a real LLM.

```
anyplace/
  ui/          layout, theme, components, prompts — the phone-first toolkit
  cli/         screens and commands built on ui/
  core/        interview, recommender, planner, generator, doctor, pipeline
  templates/   the six scaffolds
  mcp/         MCP server, so Claude can drive all of this
tests/         pytest suite
```

`ui/` and `core/` are independent: `core/` never imports `rich` or `click`, so
every decision the product makes is testable without a terminal.

---

## MCP

```bash
pip install 'anywhere-code[mcp]'
anywhere serve
```

Exposes `list_templates`, `generate_plan`, `generate_project`, `setup_project`,
`install_dependencies` and `build_project` to any MCP client.

---

## Licence

MIT.
