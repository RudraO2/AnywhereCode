#!/data/data/com.termux/files/usr/bin/bash
# ──────────────────────────────────────────────────────────
# AnywhereCode — One-command installer for Termux / Linux
#
# Usage (Termux):
#   curl -sL https://raw.githubusercontent.com/RudraO2/Classic-Snake-Made-using-Qwen-/main/install.sh | bash
#
# Or manually:
#   bash install.sh
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
    info "Detected: Linux / Desktop"
fi

# ── Step 2: Install system dependencies ───────────────────
info "Installing system packages..."

if $IS_TERMUX; then
    pkg update -y >/dev/null 2>&1 || true
    pkg install -y python git nodejs >/dev/null 2>&1 || {
        warn "Some packages may already be installed"
    }
    # Setup storage access if not done
    if [ ! -d "$HOME/storage" ]; then
        warn "Run 'termux-setup-storage' if you want projects in Downloads"
    fi
else
    # Check python3
    if ! command -v python3 &>/dev/null; then
        fail "python3 not found. Install Python 3.8+ first."
    fi
    # Check git
    if ! command -v git &>/dev/null; then
        fail "git not found. Install git first."
    fi
fi

ok "System packages ready"

# ── Step 3: Clone or update the repo ─────────────────────
INSTALL_DIR="$HOME/.anyplace/app"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin main >/dev/null 2>&1 || true
    ok "Updated to latest version"
else
    info "Downloading AnywhereCode..."
    mkdir -p "$HOME/.anyplace"
    git clone https://github.com/RudraO2/Classic-Snake-Made-using-Qwen-.git "$INSTALL_DIR" >/dev/null 2>&1 || {
        fail "Failed to clone repository. Check your internet connection."
    }
    ok "Downloaded"
fi

# ── Step 4: Install Python dependencies ──────────────────
info "Installing Python dependencies..."
cd "$INSTALL_DIR/AnywhereCode"

pip install --quiet requests click pyyaml rich 2>/dev/null || \
pip3 install --quiet requests click pyyaml rich 2>/dev/null || {
    fail "Failed to install Python packages"
}

ok "Python dependencies installed"

# ── Step 5: Create the 'anyplace' command ────────────────
info "Setting up 'anyplace' command..."

# Create a simple wrapper script
WRAPPER_DIR="$HOME/.local/bin"
mkdir -p "$WRAPPER_DIR"

cat > "$WRAPPER_DIR/anyplace" << 'WRAPPER'
#!/usr/bin/env python3
import sys, os
# Add the app to Python path
app_dir = os.path.expanduser("~/.anyplace/app/AnywhereCode")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from anyplace.cli.main import cli
cli(prog_name="anyplace")
WRAPPER

chmod +x "$WRAPPER_DIR/anyplace"

# Make sure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$WRAPPER_DIR:"* ]]; then
    # Add to shell profile
    SHELL_RC="$HOME/.bashrc"
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_RC="$HOME/.zshrc"
    fi
    echo "" >> "$SHELL_RC"
    echo '# AnywhereCode' >> "$SHELL_RC"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
    export PATH="$WRAPPER_DIR:$PATH"
    warn "Added ~/.local/bin to PATH in $SHELL_RC"
fi

ok "'anyplace' command installed"

# ── Step 6: First-time setup prompt ──────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo ""
echo -e "  ${BOLD}Quick start:${NC}"
echo -e "    ${CYAN}anyplace${NC}              — Start creating a project"
echo -e "    ${CYAN}anyplace configure${NC}    — Set up your AI API key"
echo ""

if $IS_TERMUX; then
    echo -e "  ${YELLOW}Tip:${NC} If 'anyplace' command not found, run:"
    echo -e "    ${CYAN}source ~/.bashrc${NC}"
    echo ""
    echo -e "  ${YELLOW}Projects will save to:${NC} ~/Downloads/"
else
    echo -e "  ${YELLOW}Projects will save to:${NC} ~/.anyplace/projects/"
fi
echo ""

# Ask if user wants to configure now
echo -e -n "  Set up your AI provider now? [Y/n] "
read -r CONFIGURE
if [ "$CONFIGURE" != "n" ] && [ "$CONFIGURE" != "N" ]; then
    "$WRAPPER_DIR/anyplace" configure
fi
