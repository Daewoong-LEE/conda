#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ClaudeBar — install & run (Swift / macOS 13+)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Building ClaudeBar …"
cd "$SCRIPT_DIR"
swift build -c release 2>&1

BIN=".build/release/ClaudeBar"
echo ""
echo "==> Build complete: $SCRIPT_DIR/$BIN"
echo ""
echo "Run now:"
echo "  $SCRIPT_DIR/$BIN &"
echo ""
echo "── Auto-start at login ─────────────────────────────────────────────────"
echo "  1. Edit com.claudebar.app.plist — set <string> under ProgramArguments"
echo "     to the full path:  $SCRIPT_DIR/$BIN"
echo "  2. cp com.claudebar.app.plist ~/Library/LaunchAgents/"
echo "  3. launchctl load ~/Library/LaunchAgents/com.claudebar.app.plist"
