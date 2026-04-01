#!/bin/bash
# ClaudeBar 자동 실행 설치 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PY="$SCRIPT_DIR/claudebar_app.py"
PYTHON="$(which python3)"
PLIST="$HOME/Library/LaunchAgents/com.claudebar.plist"

echo "🔧 ClaudeBar 설치 중..."

# pyobjc 설치
echo "📦 pyobjc 설치 확인..."
"$PYTHON" -m pip install pyobjc -q

# LaunchAgent plist 생성
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.claudebar</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$APP_PY</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardErrorPath</key>
  <string>$HOME/.claudebar.log</string>
  <key>StandardOutPath</key>
  <string>$HOME/.claudebar.log</string>
</dict>
</plist>
EOF

# 기존 실행 중인 앱 종료
launchctl unload "$PLIST" 2>/dev/null || true

# 등록 및 실행
launchctl load "$PLIST"

echo ""
echo "✅ 설치 완료!"
echo "   - 상태바에 ☁ 아이콘이 나타납니다"
echo "   - 맥북을 켤 때마다 자동으로 실행됩니다"
echo "   - 제거하려면: launchctl unload $PLIST"
