#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Anywhere Code — one-command installer for Termux, Linux and macOS.
#
#   curl -sL https://raw.githubusercontent.com/RudraO2/Classic-Snake-Made-using-Qwen-/main/install.sh | bash
#
# Re-running this is safe: it updates in place.
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_URL="${ANYWHERE_REPO:-https://github.com/RudraO2/Classic-Snake-Made-using-Qwen-.git}"
BRANCH="${ANYWHERE_BRANCH:-main}"
INSTALL_DIR="${ANYWHERE_HOME:-$HOME/.anyplace}/app"
BIN_DIR="$HOME/.local/bin"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C='\033[0;36m'; G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[1m'; N='\033[0m'
else
    C=''; G=''; Y=''; R=''; B=''; N=''
fi

info() { printf "  ${C}>${N} %s\n" "$1"; }
ok()   { printf "  ${G}v${N} %s\n" "$1"; }
warn() { printf "  ${Y}!${N} %s\n" "$1"; }
fail() { printf "  ${R}x${N} %s\n" "$1" >&2; exit 1; }

printf "${C}${B}\n"
printf "   ANYWHERE CODE\n"
printf "   Build and ship from your phone.\n"
printf "${N}\n"

# ── 1. Where are we? ─────────────────────────────────────────────────
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "${TERMUX_APP_PID:-}" ]; then
    IS_TERMUX=true
    info "Termux on Android"
else
    info "$(uname -s) desktop"
fi

# ── 2. System packages ───────────────────────────────────────────────
if $IS_TERMUX; then
    info "Installing python, git and node (this takes a minute)..."
    pkg update -y >/dev/null 2>&1 || warn "Couldn't refresh package lists — carrying on"
    pkg install -y python git nodejs-lts >/dev/null 2>&1 \
        || pkg install -y python git nodejs >/dev/null 2>&1 \
        || warn "Some packages may already be installed"
else
    command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.8 or newer first."
    command -v git     >/dev/null 2>&1 || fail "git not found. Install git first."
fi

PYTHON="$(command -v python3 || command -v python)"
[ -n "$PYTHON" ] || fail "No Python interpreter found."

PY_OK="$("$PYTHON" -c 'import sys; print(1 if sys.version_info[:2] >= (3, 8) else 0)')"
[ "$PY_OK" = "1" ] || fail "Python 3.8 or newer is required. Found: $("$PYTHON" --version 2>&1)"
ok "Python $("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

# ── 3. Get the code ──────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating your existing install..."
    git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH" || warn "Couldn't reach GitHub — using what's on disk"
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH" 2>/dev/null || true
    git -C "$INSTALL_DIR" merge --quiet --ff-only "origin/$BRANCH" 2>/dev/null || warn "Local changes kept — not fast-forwarding"
    ok "Up to date"
else
    info "Downloading Anywhere Code..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" \
        || fail "Couldn't clone the repository. Check your connection."
    ok "Downloaded"
fi

APP_DIR="$INSTALL_DIR/AnywhereCode"
[ -d "$APP_DIR" ] || fail "Install looks incomplete: $APP_DIR is missing."

# ── 4. Python dependencies ───────────────────────────────────────────
info "Installing Python dependencies..."
PIP_ARGS="--quiet --disable-pip-version-check"
# Termux's Python has no externally-managed marker; desktop distros often do.
if ! "$PYTHON" -m pip install $PIP_ARGS -r "$APP_DIR/requirements.txt" 2>/dev/null; then
    "$PYTHON" -m pip install $PIP_ARGS --user --break-system-packages -r "$APP_DIR/requirements.txt" 2>/dev/null \
        || "$PYTHON" -m pip install $PIP_ARGS --user -r "$APP_DIR/requirements.txt" \
        || fail "Couldn't install Python packages. Try: $PYTHON -m pip install -r $APP_DIR/requirements.txt"
fi
ok "Dependencies ready"

# ── 5. The commands ──────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
write_wrapper() {
    cat > "$BIN_DIR/$1" <<WRAPPER
#!/usr/bin/env python3
"""Launcher for Anywhere Code (installed at $APP_DIR)."""
import os
import sys

APP_DIR = os.path.expanduser("$APP_DIR")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from anyplace.cli.main import cli

sys.exit(cli(prog_name="$1", obj={}))
WRAPPER
    chmod +x "$BIN_DIR/$1"
}
write_wrapper anywhere
write_wrapper anyplace
ok "'anywhere' command installed"

# ── 6. PATH (idempotently) ───────────────────────────────────────────
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        SHELL_RC="$HOME/.bashrc"
        [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
        if ! grep -qs 'Anywhere Code' "$SHELL_RC" 2>/dev/null; then
            {
                echo ''
                echo '# Anywhere Code'
                echo 'export PATH="$HOME/.local/bin:$PATH"'
            } >> "$SHELL_RC"
            warn "Added ~/.local/bin to PATH in $(basename "$SHELL_RC")"
            warn "Run:  source $SHELL_RC   (or just reopen the terminal)"
        fi
        export PATH="$BIN_DIR:$PATH"
        ;;
esac

# ── 7. Storage on Termux ─────────────────────────────────────────────
if $IS_TERMUX && [ ! -d "$HOME/storage" ]; then
    warn "Your projects will land in ~/Downloads until you run: termux-setup-storage"
fi

# ── 8. Check it actually works ───────────────────────────────────────
printf "\n"
if "$BIN_DIR/anywhere" doctor >/dev/null 2>&1; then
    ok "Everything checks out"
else
    warn "Installed, but the setup check found something — run: anywhere doctor"
fi

printf "\n${G}${B}  Done.${N}\n\n"
printf "  ${B}Start here:${N}\n"
printf "    ${C}anywhere${N}             open the app\n"
printf "    ${C}anywhere configure${N}   add your AI key (Gemini has a free tier)\n"
printf "    ${C}anywhere doctor${N}      check this device\n\n"

printf "  Set up your AI provider now? [Y/n] "
read -r REPLY </dev/tty 2>/dev/null || REPLY="n"
case "$REPLY" in
    n|N) printf "  No problem — run 'anywhere configure' when you're ready.\n\n" ;;
    *)   "$BIN_DIR/anywhere" configure ;;
esac
