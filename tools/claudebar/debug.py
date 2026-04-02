#!/usr/bin/env python3
"""ClaudeBar 동기화 진단 / sessionKey 설정 도우미"""
import json, urllib.request, sys
from pathlib import Path

SESSION_FILE = Path.home() / ".claudebar_session"

def test_session(session_key):
    cookie_str = f"sessionKey={session_key}"
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    print("  org 정보 가져오는 중...")
    req = urllib.request.Request("https://claude.ai/api/organizations", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        orgs = json.loads(r.read())
    if not orgs:
        print("  ❌ 로그인 실패 — sessionKey가 올바른지 확인하세요")
        return

    org_id = orgs[0]["uuid"]
    print(f"  ✅ 로그인 성공! org_id = {org_id}")

    for path in [
        f"/api/organizations/{org_id}/rate_limits",
        f"/api/organizations/{org_id}/usage",
        f"/api/organizations/{org_id}/limits",
    ]:
        try:
            req2 = urllib.request.Request(f"https://claude.ai{path}", headers=headers)
            with urllib.request.urlopen(req2, timeout=5) as r:
                data = json.loads(r.read())
            print(f"\n  ✅ {path}")
            print(f"  {json.dumps(data, indent=2)[:500]}")
        except Exception as e:
            print(f"  ❌ {path}: {e}")

if __name__ == "__main__":
    print("=== ClaudeBar 세션 키 설정 ===\n")
    print("1. Chrome에서 claude.ai 열기")
    print("2. 우클릭 → 검사(Inspect) → Application 탭 → Cookies → https://claude.ai")
    print("3. 'sessionKey' 항목의 Value 복사")
    print("4. 아래에 붙여넣기 후 엔터\n")

    if SESSION_FILE.exists():
        existing = SESSION_FILE.read_text().strip()
        print(f"현재 저장된 키: {existing[:20]}...")
        ans = input("다시 입력? (y/N): ").strip().lower()
        if ans != "y":
            print("\n기존 키로 테스트합니다...")
            try:
                test_session(existing)
            except Exception as e:
                print(f"  ❌ 오류: {e}")
            sys.exit(0)

    key = input("sessionKey 값 붙여넣기: ").strip()
    if not key:
        print("입력 없음, 종료")
        sys.exit(1)

    print(f"\n테스트 중...")
    try:
        test_session(key)
        SESSION_FILE.write_text(key)
        print(f"\n✅ 저장 완료: {SESSION_FILE}")
        print("ClaudeBar가 자동으로 동기화를 시작합니다 (1분 이내)")
        # Clear cache to force refresh
        cache = Path.home() / ".claudebar_live.json"
        if cache.exists():
            cache.unlink()
    except Exception as e:
        print(f"\n❌ 실패: {e}")
