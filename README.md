# AnywhereCode

**Build a real Android app on your phone. No laptop. No Android Studio. No credit card.**

You describe an app. AI plans it, writes it, installs the dependencies, builds
it — and then hands you an APK you can tap to install. The whole thing runs in
[Termux](https://termux.dev) on the phone in your hand.

```bash
curl -sL https://raw.githubusercontent.com/RudraO2/AnywhereCode/main/install.sh | bash
anyplace
```

That's the entire setup. It works with **zero API keys** — see [Free tokens](#free-tokens-no-api-key-needed).

---

## Why this exists

Millions of people have a phone and no laptop. Every "learn to code" path assumes
otherwise. The blocker was never the editor — it's the *build*: Gradle cannot
realistically run on a phone, so an Android app was out of reach.

AnywhereCode moves that build to the cloud. Your phone uploads source and
downloads an APK. That's it.

| | Without AnywhereCode | With AnywhereCode |
|---|---|---|
| **Write code on a phone** | Possible, painful | `anyplace` — AI scaffolds the whole project |
| **Install dependencies** | Manual `npm install` guessing | Automatic, project-type aware |
| **Build an Android APK** | ❌ Gradle won't run on Android | ✅ Built on Expo's servers |
| **Get the app onto a phone** | Transfer from a laptop | ✅ Tap to install, right there |
| **Cost** | API keys, subscriptions | ✅ Free tier, no signup |

---

## Build an APK from your phone

This is the part that didn't used to be possible.

```bash
anyplace                 # pick "React Native + Expo", describe your app
anyplace login-expo      # paste a token from expo.dev/settings/access-tokens
anyplace apk --install   # cloud build → download → Android installer opens
```

`anyplace apk` handles the things that normally make this fail:

- **Forces an APK, not an AAB.** EAS defaults Android builds to an App Bundle,
  which *cannot be sideloaded*. You'd wait 15 minutes for a file you can't
  install. The `preview` profile is pinned to `buildType: "apk"`.
- **Fills in `android.package`.** Missing it makes eas-cli stop and ask a
  question, which deadlocks a non-interactive build. It's derived from your
  project name automatically.
- **Handles the first-build keystore.** eas-cli refuses to generate a signing
  key in `--non-interactive` mode. That specific failure is detected and the
  build transparently retries attached to your terminal.
- **Prints a QR code** of the finished APK, so a second phone can scan and
  install without touching a cable.

```
🎉 APK ready!

  Download: https://expo.dev/artifacts/eas/xY3k....apk

Scan to install on another phone:

  █████████████████████████████████
  ██ ▄▄▄▄▄ █▄▄▄ ▀▄▀█▄▄ ▀▀█ ▄▄▄▄▄ ██
  ██ █   █ ██▄▀ █  █▄▀██ █ █   █ ██
  ██ █▄▄▄█ ██▀▄ ▄  ██▄ ▄▀█ █▄▄▄█ ██
  ██▄▄▄▄▄▄▄█ ▀▄█ ▀ █▄█▄▀ █▄▄▄▄▄▄▄██
  ...
```

| Command | What you get |
|---|---|
| `anyplace apk` | Installable APK (`preview` profile) |
| `anyplace apk --install` | …downloaded and opened in Android's installer |
| `anyplace apk --no-wait` | Queue the build, close the terminal, check back later |
| `anyplace apk --profile production` | AAB, signed and ready for the Play Store |

Builds run on [EAS](https://expo.dev) and take 8–20 minutes. They keep going
if your connection drops.

---

## Free tokens, no API key needed

AnywhereCode ships with [OmniRoute](https://github.com/diegosouzapw/OmniRoute)
as the default provider — a free, MIT-licensed gateway you run locally that
pools the free tiers of 90+ providers behind one endpoint (**~1.5 billion
tokens/month**, aggregated across Mistral, Gemini, Groq, Cerebras, Cloudflare
and others).

```bash
npm install -g omniroute && omniroute    # runs on :20128, no account needed
anyplace configure                       # pick option 1
```

The `auto` model routes across keyless free providers and fails over when one
runs out of quota — so you can build all day without signing up for anything.

**Prefer your own key?** All of these work too:

| Provider | Notes |
|---|---|
| **OmniRoute** ⭐ | Free, local, no key, no signup |
| **OpenRouter** | Free `:free` models on a $0 balance, no credit card |
| **Claude** | Best code quality |
| **Gemini** | Generous free tier |
| **Custom** | Any OpenAI-compatible endpoint, including self-hosted |

---

## What it does after you approve the plan

Nothing is left as a "next step" for you to run by hand:

```
describe app → AI plan → you approve
     ↓
  generate every source file (dependency-ordered, so imports never break)
  git init + commit as it goes
  npm install / pip install       (auto-detected)
  npm run build                   (auto-detected)
  .env from .env.example
  GitHub Actions CI/CD
  Dockerfile + docker-compose
  deployment config
  start the dev server
     ↓
  working project
```

By default you approve each step. `--auto` skips the confirmations.

Every command the agent runs is checked against a blocklist first — `rm -rf`,
`chmod 777`, `sudo`, `git push --force`, `curl | bash` and friends are refused
outright, so an LLM suggestion can't wipe your phone.

---

## Templates

React Native + Expo · React SPA (Vite) · Next.js · Node.js API · FastAPI (Python)

Templates are **boilerplate only** — they set up structure, not design. Your UI
is entirely yours.

---

## Commands

```bash
anyplace                  # interactive — start here
anyplace doctor           # check your setup, get exact fixes
anyplace apk              # build an installable Android APK
anyplace login-expo       # save an Expo token for headless builds
anyplace run --dir .      # run the full pipeline on an existing project
anyplace commit -a        # AI commit message from your diff
anyplace explain <file>   # understand any file
anyplace guide            # learning guide for your stack
anyplace serve            # MCP server, so AI agents can drive it
```

Stuck? `anyplace doctor` tells you exactly what's missing and the command to fix it.

---

## Requirements

- Python 3.8+
- git
- Node.js (for JS projects and APK builds)
- An Expo account for APK builds — [free](https://expo.dev/signup)

On Termux the installer sets all of this up for you.

---

## Contributing

This project exists so that someone with only a phone can ship real software.
Contributions that widen that door are especially welcome:

- **New templates** — add `anyplace/templates/<name>/structure.json`
- **New providers** — extend `PROVIDERS` in `anyplace/cli/config_wizard.py`
- **iOS builds** — the EAS plumbing is there, it needs an Apple Developer flow
- **Translations** — most of the target audience doesn't read English first

```bash
git clone https://github.com/RudraO2/AnywhereCode.git
cd AnywhereCode/AnywhereCode
pip install -e .
python3 test_e2e.py     # 9 tests, no API key needed (mock LLM)
python3 test_eas.py     # 42 tests, fully offline
```

Both suites run without network access or credentials.

## License

MIT
