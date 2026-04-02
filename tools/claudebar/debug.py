#!/usr/bin/env python3
"""ClaudeBar 동기화 진단 스크립트"""
import json, sqlite3, shutil, tempfile, hashlib, urllib.request
from pathlib import Path

COOKIE_DB = Path.home() / "Library/Application Support/Claude/Cookies"

def _try_decrypt(enc_val):
    """Try decrypting Electron cookie with 'peanuts' password (no keychain)."""
    if not enc_val or not enc_val.startswith(b"v10"):
        return None
    try:
        from Cryptodome.Cipher import AES
        key = hashlib.pbkdf2_hmac("sha1", b"peanuts", b"saltysalt", 1003, dklen=16)
        iv  = b" " * 16
        raw = enc_val[3:]
        # Pad to 16-byte boundary
        pad_len = 16 - (len(raw) % 16)
        if pad_len != 16:
            raw += b"\x00" * pad_len
        decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(raw)
        pad = decrypted[-1]
        result = decrypted[:-pad].decode("utf-8", errors="ignore")
        return result if result.isprintable() and len(result) > 2 else None
    except Exception as e:
        return None

print("=== 1. 쿠키 DB 암호화 확인 ===")
if not COOKIE_DB.exists():
    print(f"  ❌ 파일 없음: {COOKIE_DB}")
else:
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(COOKIE_DB), tmp)
    conn = sqlite3.connect(tmp)
    rows = conn.execute(
        "SELECT host_key, name, value, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
    ).fetchall()
    conn.close()
    Path(tmp).unlink()

    decrypted_cookies = {}
    for host, name, value, enc_val in rows:
        if value:
            decrypted_cookies[name] = value
        elif enc_val:
            dec = _try_decrypt(enc_val)
            if dec:
                decrypted_cookies[name] = dec
                print(f"  ✅ 복호화 성공: {name} = {dec[:40]}")
            else:
                print(f"  🔒 복호화 실패 (키체인 필요): {name}")

    print(f"\n  복호화된 쿠키: {len(decrypted_cookies)}개")

    if decrypted_cookies:
        cookie_str = "; ".join(f"{k}={v}" for k,v in decrypted_cookies.items())
        print("\n=== 2. claude.ai API 테스트 ===")
        try:
            req = urllib.request.Request(
                "https://claude.ai/api/organizations",
                headers={"Cookie": cookie_str, "Accept": "application/json",
                         "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            print(f"  ✅ 응답: {json.dumps(data)[:300]}")
        except Exception as e:
            print(f"  ❌ 오류: {e}")
    else:
        print("\n=== 2. 키체인 없이 접근 불가 ===")
        print("  모든 쿠키가 macOS 키체인으로 암호화되어 있습니다.")
        print("  다른 방법을 시도합니다...")

        # Try ~/.claude/ for any stored tokens
        print("\n=== 3. ~/.claude/ 인증 토큰 확인 ===")
        claude_dir = Path.home() / ".claude"
        for f in claude_dir.glob("*.json"):
            try:
                content = json.loads(f.read_text())
                print(f"  {f.name}: {str(content)[:200]}")
            except:
                pass

