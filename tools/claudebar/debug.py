#!/usr/bin/env python3
"""ClaudeBar 동기화 진단 스크립트"""
import json, sqlite3, shutil, tempfile, urllib.request
from pathlib import Path

COOKIE_DB = Path.home() / "Library/Application Support/Claude/Cookies"

print("=== 1. Claude 앱 쿠키 DB 확인 ===")
if not COOKIE_DB.exists():
    print(f"  ❌ 파일 없음: {COOKIE_DB}")
    print("  → Claude 데스크탑 앱이 설치되어 있지 않거나 경로가 다릅니다")
    import os
    base = Path.home() / "Library/Application Support"
    matches = list(base.glob("*/Cookies"))
    print(f"  발견된 Cookies 파일들: {matches}")
else:
    print(f"  ✅ 발견: {COOKIE_DB}")
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(COOKIE_DB), tmp)
    conn = sqlite3.connect(tmp)
    rows = conn.execute("SELECT host_key, name, value FROM cookies").fetchall()
    conn.close()
    Path(tmp).unlink()
    print(f"  전체 쿠키 수: {len(rows)}")
    claude_rows = [(h,n,v) for h,n,v in rows if "claude" in h.lower() or "anthropic" in h.lower()]
    print(f"  claude.ai 쿠키 수: {len(claude_rows)}")
    for h, n, v in claude_rows[:5]:
        encrypted = v.startswith("v1") if v else False
        print(f"    {h} | {n} | {'[암호화됨]' if encrypted else v[:30]}")

print()
print("=== 2. claude.ai 접근 테스트 ===")
if COOKIE_DB.exists():
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(COOKIE_DB), tmp)
    conn = sqlite3.connect(tmp)
    rows = conn.execute("SELECT name, value FROM cookies WHERE host_key LIKE '%claude.ai%'").fetchall()
    conn.close()
    Path(tmp).unlink()
    pairs = [f"{n}={v}" for n,v in rows if v and not v.startswith("v1")]
    if not pairs:
        print("  ❌ 사용 가능한 쿠키 없음 (모두 암호화되어 있을 수 있음)")
    else:
        cookie_str = "; ".join(pairs)
        print(f"  쿠키 {len(pairs)}개 사용 시도...")
        try:
            req = urllib.request.Request(
                "https://claude.ai/api/organizations",
                headers={"Cookie": cookie_str, "Accept": "application/json",
                         "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            print(f"  ✅ 응답: {json.dumps(data)[:200]}")
        except Exception as e:
            print(f"  ❌ 오류: {e}")
else:
    print("  (쿠키 DB 없어서 건너뜀)")

print()
print("=== 3. 캐시 파일 확인 ===")
live = Path.home() / ".claudebar_live.json"
if live.exists():
    print(f"  {live.read_text()}")
else:
    print("  캐시 없음")
