#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ClaudeBar — quick-install script for macOS
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing ClaudeBar dependencies …"
pip install --upgrade rumps watchdog

echo "==> Installing ClaudeBar …"
pip install -e "$SCRIPT_DIR"

echo "==> Done!  Run with:  claudebar"
echo ""
echo "Optional — auto-start at login:"
echo "  1. Edit com.claudebar.app.plist and update <ProgramArguments> to point"
echo "     to the full path of the 'claudebar' executable (which python -m shutil)"
echo "     e.g.  $(which claudebar 2>/dev/null || echo '/usr/local/bin/claudebar')"
echo "  2. cp $SCRIPT_DIR/com.claudebar.app.plist ~/Library/LaunchAgents/"
echo "  3. launchctl load ~/Library/LaunchAgents/com.claudebar.app.plist"
