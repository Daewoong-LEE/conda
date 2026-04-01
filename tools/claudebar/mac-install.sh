#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ClaudeBar macOS installer
# 실행: bash mac-install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/claudebar.2s.py"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         ClaudeBar Installer          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. macOS 확인 ─────────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌  macOS에서만 실행 가능합니다."
    exit 1
fi

# ── 2. Homebrew 확인 / 설치 ────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "==> Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "✓  Homebrew 확인"

# ── 3. SwiftBar 설치 ──────────────────────────────────────────────────────────
if ! brew list --cask swiftbar &>/dev/null 2>&1; then
    echo "==> SwiftBar 설치 중..."
    brew install --cask swiftbar
fi
echo "✓  SwiftBar 확인"

# ── 4. 플러그인 디렉토리 생성 ─────────────────────────────────────────────────
PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/plugins"
mkdir -p "$PLUGIN_DIR"

# ── 5. 플러그인 복사 & 실행 권한 부여 ─────────────────────────────────────────
cp "$PLUGIN_SRC" "$PLUGIN_DIR/claudebar.2s.py"
chmod +x "$PLUGIN_DIR/claudebar.2s.py"
echo "✓  플러그인 설치 완료: $PLUGIN_DIR/claudebar.2s.py"

# ── 6. SwiftBar 실행 ──────────────────────────────────────────────────────────
echo "==> SwiftBar 실행 중..."
open -a SwiftBar || open "$PLUGIN_DIR"

echo ""
echo "✅  완료! 상태바에 ☁ 표시가 나타납니다."
echo "   (처음 실행 시 '허용' 클릭 필요)"
echo ""
