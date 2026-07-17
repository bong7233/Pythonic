#!/usr/bin/env python3
"""content/ 의 마크다운을 브라우저가 바로 읽는 번들로 묶는다.

왜 번들인가: file:// 로 index.html 을 열면 fetch()가 CORS로 막힌다.
<script> 태그로 읽히는 JS 파일에 JSON을 박아두면 서버 없이도 동작한다.

사용법:
    python build.py            # 한 번 빌드
    python build.py --watch    # 파일 변경 시 자동 재빌드
    python build.py --serve    # 로컬 서버 (휴대폰에서 접속용)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
import time
from pathlib import Path

# Windows 콘솔 기본 코드페이지(cp949)로는 이 스크립트의 한글 출력이 깨진다.
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
TOC_PATH = CONTENT / "toc.json"
OUT = ROOT / "assets" / "bundle.js"
INDEX = ROOT / "index.html"

# index.html 안에서 버전 도장을 찍을 자산들
ASSETS = ["assets/style.css", "assets/highlight.js", "assets/markdown.js",
          "assets/bundle.js", "assets/app.js"]


def stamp_versions() -> str:
    """index.html 의 자산 URL에 내용 해시를 붙인다.

    브라우저(특히 휴대폰)는 같은 이름의 JS/CSS를 공격적으로 캐싱한다.
    내용이 바뀌면 URL이 바뀌어야 새로 받는다.
    """
    h = hashlib.sha256()
    for rel in ASSETS:
        p = ROOT / rel
        if p.exists():
            h.update(p.read_bytes())
    ver = h.hexdigest()[:10]

    html = INDEX.read_text(encoding="utf-8")
    for rel in ASSETS:
        html = re.sub(
            rf'({re.escape(rel)})(\?v=[0-9a-f]+)?',
            rf"\1?v={ver}",
            html,
        )
    INDEX.write_text(html, encoding="utf-8")
    return ver


def find_doc(chapter_id: str) -> Path | None:
    """content/ 어디에 있든 <id>.md 를 찾는다."""
    hits = [p for p in CONTENT.rglob(f"{chapter_id}.md")]
    if len(hits) > 1:
        raise SystemExit(f"[에러] '{chapter_id}.md' 가 여러 곳에 있습니다: {hits}")
    return hits[0] if hits else None


def word_count(md: str) -> int:
    """코드 블록을 제외한 본문 글자 수 (분량 추정용)."""
    body = re.sub(r"```[\s\S]*?```", "", md)
    return len(re.sub(r"\s+", "", body))


def build() -> dict:
    toc = json.loads(TOC_PATH.read_text(encoding="utf-8"))

    docs: dict[str, str] = {}
    seen: set[str] = set()
    missing: list[str] = []
    total_chars = 0

    for part in toc["parts"]:
        for ch in part["chapters"]:
            cid = ch["id"]
            if cid in seen:
                raise SystemExit(f"[에러] 챕터 id 중복: {cid}")
            seen.add(cid)

            path = find_doc(cid)
            if path is None:
                missing.append(f'{ch["num"]} {ch["title"]}')
                continue
            md = path.read_text(encoding="utf-8")
            docs[cid] = md
            total_chars += word_count(md)

    # 목차에 없는 고아 마크다운 경고
    for p in CONTENT.rglob("*.md"):
        if p.stem not in seen and not p.name.startswith("_"):
            print(f"[경고] 목차에 없는 파일: {p.relative_to(ROOT)}")

    payload = {
        "meta": toc["meta"],
        "toc": [
            {
                "id": p["id"],
                "num": p["num"],
                "title": p["title"],
                "desc": p.get("desc", ""),
                "chapters": p["chapters"],
            }
            for p in toc["parts"]
        ],
        "docs": docs,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "/* 자동 생성 파일 — 직접 고치지 말 것. `python build.py` 로 다시 만든다. */\n"
        "window.BOOK = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    OUT.write_text(js, encoding="utf-8")
    ver = stamp_versions()

    return {
        "written": len(docs),
        "total": len(seen),
        "missing": missing,
        "chars": total_chars,
        "size": OUT.stat().st_size,
        "ver": ver,
    }


def report(st: dict) -> None:
    pages = st["chars"] / 1400  # 한글 기준 대략 한 페이지
    print(
        f"빌드 완료: {st['written']}/{st['total']} 절 · "
        f"본문 {st['chars']:,}자 (약 {pages:,.0f}쪽) · "
        f"번들 {st['size'] / 1024:,.0f} KB · v{st['ver']}"
    )
    if st["missing"]:
        print(f"  아직 비어 있는 절 {len(st['missing'])}개")


def snapshot() -> dict[Path, float]:
    # bundle.js 와 index.html 은 빌드가 직접 쓰므로 감시 대상에서 뺀다 (무한 루프 방지).
    watched = [ROOT / a for a in ASSETS if not a.endswith("bundle.js")]
    files = list(CONTENT.rglob("*.md")) + [TOC_PATH] + watched
    return {p: p.stat().st_mtime for p in files if p.exists()}


def watch() -> None:
    report(build())
    print("변경 감시 중… (Ctrl+C 로 종료)")
    prev = snapshot()
    try:
        while True:
            time.sleep(0.7)
            cur = snapshot()
            if cur != prev:
                prev = cur
                try:
                    report(build())
                except SystemExit as e:
                    print(e)
    except KeyboardInterrupt:
        print("\n종료합니다.")


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def serve(port: int) -> None:
    import http.server
    import socketserver

    report(build())

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"\n  PC     :  http://localhost:{port}/")
        print(f"  휴대폰 :  http://{lan_ip()}:{port}/   (같은 와이파이)")
        print("\nCtrl+C 로 종료합니다.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n종료합니다.")


def main() -> None:
    ap = argparse.ArgumentParser(description="파이썬 완전 정복 — 빌드 스크립트")
    ap.add_argument("--watch", action="store_true", help="파일 변경 시 자동 재빌드")
    ap.add_argument("--serve", action="store_true", help="로컬 서버 실행 (휴대폰 접속용)")
    ap.add_argument("--port", type=int, default=8800)
    args = ap.parse_args()

    if args.serve:
        serve(args.port)
    elif args.watch:
        watch()
    else:
        report(build())


if __name__ == "__main__":
    sys.exit(main())
