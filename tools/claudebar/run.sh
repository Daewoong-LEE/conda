#!/usr/bin/env bash
# ClaudeBar 실행 스크립트 (macOS)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> PyObjC 설치 확인 중..."
pip install pyobjc -q

echo "==> ClaudeBar 실행 중..."
python3 "$SCRIPT_DIR/claudebar_app.py" &

echo "✅ 상태바에 ☁ 아이콘이 나타납니다!"
