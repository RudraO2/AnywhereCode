#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# AnywhereCode — One-command installer for Termux / Linux / macOS
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/RudraO2/AnywhereCode/main/install.sh | bash
#
# Or, after cloning:
#   bash install.sh
#
# Set ANYPLACE_NO_PROMPT=1 to skip the interactive setup at the end.
# ──────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}${BOLD}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║     AnywhereCode Installer            ║"
    echo "  ║     Code Anywhere — Code Anytime      ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

info()  { echo -e "  ${CYAN}▸${NC} $1"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }

banner

# ── Step 1: Detect environment ────────────────────────────
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_APP_PID" ]; then
    IS_TERMUX=true
    info "Detected: Termux on Android"
else
    info "Detected: $(uname -s)"
fi

# ── Step 2: Install system dependencies ───────────────────
info "Installing system packages..."

if $IS_TERMUX; then
    pkg update -y >/dev/null 2>&1 || true
    # nodejs is not optional: it powers both JS project builds and the
    # eas-cli that produces APKs.
    pkg install -y python git nodejs >/dev/null 2>&1 || {
        warn "Some packages may already be installed"
    }

    # Without storage access there is nowhere safe to drop a built APK.
    if [ ! -d "$HOME/storage" ]; then
        info "Requesting storage access (approve the Android prompt)..."
        termux-setup-storage 2>/dev/null || \
            warn "Run 'termux-setup-storage' manually to save projects to Downloads"
        sleep 2
    fi
else
    command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.8+ first."
    command -v git >/dev/null 2>&1 || fail "git not found. Install git first."
    command -v node >/dev/null 2>&1 || \
        warn "Node.js not found — needed for JS projects and APK builds"
fi

ok "System packages ready"

# ── Step 3: Clone or update the repo ─────────────────────
INSTALL_DIR="$HOME/.anyplace/app"
REPO_URL="https://github.com/RudraO2/AnywhereCode.git"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    git -C "$INSTALL_DIR" pull origin main >/dev/null 2>&1 || \
        warn "Could not pull latest changes — keeping current version"
    ok "Up to date"
else
    info "Downloading AnywhereCode..."
    mkdir -p "$HOME/.anyplace"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>&1 || {
        fail "Failed to clone repository. Check your internet connection."
    }
    ok "Downloaded"
fi

# ── Step 4: Install Python dependencies ──────────────────
info "Installing Python dependencies..."

PIP=pip3
command -v pip3 >/dev/null 2>&1 || PIP=pip

# Every one of these is pure Python — nothing here needs a Rust or C
# toolchain, which is what keeps the install working on Termux/aarch64.
$PIP install --quiet requests click pyyaml rich qrcode 2>/dev/null || {
    fail "Failed to install Python packages"
}

ok "Python dependencies installed"

# ── Step 5: Create the 'anyplace' command ────────────────
info "Setting up 'anyplace' command..."

WRAPPER_DIR="$HOME/.local/bin"
mkdir -p "$WRAPPER_DIR"

cat > "$WRAPPER_DIR/anyplace" << 'WRAPPER'
#!/usr/bin/env python3
import sys, os

app_dir = os.path.expanduser("~/.anyplace/app/AnywhereCode")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from anyplace.cli.main import cli
cli(prog_name="anyplace")
WRAPPER

chmod +x "$WRAPPER_DIR/anyplace"

# Make sure ~/.local/bin is on PATH, without duplicating the export line
# on every re-run of this installer.
if [[ ":$PATH:" != *":$WRAPPER_DIR:"* ]]; then
    SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

    if ! grep -q 'AnywhereCode' "$SHELL_RC" 2>/dev/null; then
        {
            echo ""
            echo "# AnywhereCode"
            echo 'export PATH="$HOME/.local/bin:$PATH"'
        } >> "$SHELL_RC"
        warn "Added ~/.local/bin to PATH in $SHELL_RC"
    fi
    export PATH="$WRAPPER_DIR:$PATH"
fi

ok "'anyplace' command installed"

# ── Step 6: Wrap up ──────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo ""
echo -e "  ${BOLD}Quick start:${NC}"
echo -e "    ${CYAN}anyplace${NC}              — Create a project (guides you through setup)"
echo -e "    ${CYAN}anyplace doctor${NC}       — Check everything is working"
echo -e "    ${CYAN}anyplace apk${NC}          — Build an installable Android APK"
echo ""

if $IS_TERMUX; then
    echo -e "  ${YELLOW}If 'anyplace' is not found:${NC} ${CYAN}source ~/.bashrc${NC}"
    echo -e "  ${YELLOW}Projects save to:${NC} ~/storage/downloads/"
else
    echo -e "  ${YELLOW}Projects save to:${NC} ~/.anyplace/projects/"
fi
echo ""

# When this script is piped into bash (`curl … | bash`), stdin is the script
# itself — a plain `read` would consume script text or hit EOF instantly. Read
# from the terminal directly, and skip the prompt when there is no terminal.
if [ -n "$ANYPLACE_NO_PROMPT" ]; then
    exit 0
fi

if [ ! -t 0 ] && [ ! -r /dev/tty ]; then
    info "Non-interactive install — run 'anyplace' when you're ready."
    exit 0
fi

echo -e -n "  Set up your AI provider now? [Y/n] "
if [ -t 0 ]; then
    read -r CONFIGURE
else
    read -r CONFIGURE < /dev/tty
fi

case "$CONFIGURE" in
    n|N|no|NO) echo -e "  Run ${CYAN}anyplace${NC} whenever you're ready." ;;
    *) "$WRAPPER_DIR/anyplace" configure < /dev/tty ;;
esac
