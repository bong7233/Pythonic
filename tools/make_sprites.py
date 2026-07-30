"""픽셀 스프라이트를 생성해 assets/style.css 에 심는다.

왜 이렇게 하는가
- 이 앱은 오프라인으로 돌아야 한다. 외부 이미지 파일도, CDN 도 못 쓴다.
  그래서 스프라이트를 인라인 SVG data URI 로 만들어 CSS 안에 넣는다.
- data URI 안의 SVG 는 CSS 변수를 못 받는다. 그래서 색을 박아 넣되,
  어두운 배경(동굴)과 밝은 배경(양피지) 양쪽에서 읽히는 색만 골랐다.
  실제 픽셀 아트가 그러듯 진한 외곽선 + 중간톤 본체 + 밝은 하이라이트 조합이다.
- 손으로 URL 인코딩한 SVG 를 CSS 에 직접 쓰면 오타를 잡을 수 없다.
  여기서 생성해서 심으면 도트를 고치고 다시 돌리기만 하면 된다.

    python tools/make_sprites.py

style.css 의 SPRITES-BEGIN / SPRITES-END 사이를 통째로 교체한다.
"""

from __future__ import annotations

import pathlib
import re
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "style.css"

BEGIN = "/* SPRITES-BEGIN — tools/make_sprites.py 가 생성한다. 손으로 고치지 마라. */"
END = "/* SPRITES-END */"

# ---------------------------------------------------------------- 팔레트
# 두 테마 모두에서 읽히도록 중간톤 위주로 골랐다.
OUT_D = "#161c22"   # 진한 외곽선
OUT_G = "#1f2f1c"   # 식물 외곽선
OUT_R = "#2b3137"   # 돌 외곽선

BOT_B = "#c3ccd4"   # 로봇 본체
BOT_S = "#7c8992"   # 로봇 그늘
LED = "#4fd3c4"
AMBER = "#f2b23e"

SLM_B = "#6fcf6a"   # 슬라임
SLM_H = "#a9e8a0"

BAT_B = "#9b7ce0"   # 박쥐
BAT_W = "#6a4fb0"

LEAF = "#4a8f4a"
LEAF_H = "#6fbf6a"
TRUNK = "#7a5230"

ROCK = "#828b93"
ROCK_H = "#a7b0b8"

CRY = "#6fd3f2"
CRY_H = "#b3ecfd"

FLAME_A = "#f2b23e"
FLAME_B = "#e5563d"

PETAL = "#e0708c"
POLLEN = "#f2d24a"


def svg(w: int, h: int, rects: list[tuple[int, int, int, int, str]]) -> str:
    """도트 목록 -> URL 인코딩된 data URI."""
    body = "".join(
        f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" fill="{c}"/>'
        for x, y, rw, rh, c in rects
    )
    doc = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'shape-rendering="crispEdges">{body}</svg>'
    )
    return "url(\"data:image/svg+xml," + quote(doc, safe="") + "\")"


# ---------------------------------------------------------------- 스프라이트
def robot(step: int) -> str:
    """걷는 로봇. step 0/1 로 다리가 바뀐다."""
    r = [
        (7, 0, 2, 1, AMBER),          # 안테나
        (7, 1, 1, 2, BOT_S),
        (3, 3, 10, 1, OUT_D),         # 머리 윗선
        (2, 4, 1, 6, OUT_D), (13, 4, 1, 6, OUT_D),
        (3, 4, 10, 6, BOT_B),
        (3, 8, 10, 2, BOT_S),         # 아래 그늘
        (4, 6, 2, 2, LED), (10, 6, 2, 2, LED),   # 눈
        (3, 10, 10, 1, OUT_D),
        (1, 5, 1, 3, BOT_S), (14, 5, 1, 3, BOT_S),  # 귀
        (4, 11, 8, 3, BOT_B),         # 몸통
        (4, 11, 8, 1, OUT_D),
        (6, 12, 4, 1, AMBER),         # 가슴 램프
    ]
    if step == 0:
        r += [(4, 14, 3, 2, OUT_D), (9, 14, 3, 2, BOT_S)]
    else:
        r += [(4, 14, 3, 2, BOT_S), (9, 14, 3, 2, OUT_D)]
    return svg(16, 16, r)


def slime(step: int) -> str:
    """통통 튀는 슬라임. 0=납작, 1=길쭉."""
    if step == 0:
        r = [
            (2, 6, 10, 1, OUT_G), (1, 7, 12, 4, OUT_G),
            (2, 7, 10, 3, SLM_B), (3, 7, 4, 1, SLM_H),
            (4, 8, 2, 2, OUT_G), (8, 8, 2, 2, OUT_G),
        ]
    else:
        r = [
            (4, 3, 6, 1, OUT_G), (3, 4, 8, 1, OUT_G),
            (2, 5, 10, 6, OUT_G),
            (3, 5, 8, 5, SLM_B), (4, 5, 3, 1, SLM_H),
            (4, 6, 2, 2, OUT_G), (8, 6, 2, 2, OUT_G),
        ]
    return svg(14, 12, r)


def bat(step: int) -> str:
    """나는 박쥐. 0=날개 위, 1=날개 아래."""
    body = [
        (6, 4, 4, 5, BAT_B), (6, 4, 4, 1, OUT_D),
        (5, 2, 1, 2, BAT_B), (10, 2, 1, 2, BAT_B),   # 귀
        (6, 5, 1, 1, AMBER), (9, 5, 1, 1, AMBER),    # 눈
        (6, 9, 4, 1, OUT_D),
    ]
    if step == 0:
        w = [(1, 2, 5, 2, BAT_W), (0, 3, 2, 2, BAT_W),
             (10, 2, 5, 2, BAT_W), (14, 3, 2, 2, BAT_W)]
    else:
        w = [(1, 6, 5, 2, BAT_W), (0, 5, 2, 2, BAT_W),
             (10, 6, 5, 2, BAT_W), (14, 5, 2, 2, BAT_W)]
    return svg(16, 12, body + w)


# 침엽수. 3단으로 층을 지어야 작은 크기에서도 '나무'로 읽힌다.
# 잎을 통짜 사각형으로 두면 초록 덩어리로만 보인다 — 실제로 그렇게 나왔다.
TREE = svg(16, 22, [
    (7, 0, 2, 1, OUT_G),                                  # 꼭대기
    (6, 1, 4, 1, LEAF), (6, 1, 4, 1, OUT_G),
    (6, 2, 4, 2, LEAF), (7, 2, 1, 2, LEAF_H),
    (5, 4, 6, 1, OUT_G),                                  # 1단 밑선
    (5, 5, 6, 2, LEAF), (6, 5, 2, 1, LEAF_H),
    (4, 7, 8, 1, LEAF), (3, 8, 10, 1, OUT_G),             # 2단
    (4, 9, 8, 2, LEAF), (5, 9, 2, 1, LEAF_H),
    (3, 11, 10, 1, LEAF), (2, 12, 12, 1, OUT_G),          # 3단
    (3, 13, 10, 2, LEAF), (4, 13, 3, 1, LEAF_H),
    (4, 15, 8, 1, OUT_G),
    (7, 16, 2, 5, TRUNK), (6, 18, 1, 2, TRUNK),           # 줄기
    (6, 21, 4, 1, OUT_G),
])

# 버섯. 빈 구간을 메우는 용도이자, 동굴 느낌을 더한다.
MUSHROOM = svg(12, 12, [
    (3, 0, 6, 1, OUT_R),
    (1, 1, 10, 1, OUT_R), (1, 2, 10, 3, PETAL),
    (2, 2, 3, 1, "#f09aae"),                              # 갓 하이라이트
    (3, 3, 2, 1, POLLEN), (7, 2, 2, 2, POLLEN),           # 반점
    (1, 5, 10, 1, OUT_R),
    (4, 6, 4, 5, "#efe3cc"), (4, 6, 1, 5, "#cfc2a8"),     # 대
    (4, 11, 4, 1, OUT_R),
])

BUSH = svg(14, 10, [
    (4, 1, 6, 1, OUT_G), (2, 2, 10, 1, OUT_G),
    (1, 3, 12, 5, LEAF), (2, 4, 3, 2, LEAF_H),
    (1, 8, 12, 1, OUT_G),
])

GRASS = svg(10, 8, [
    (1, 4, 1, 4, LEAF), (2, 3, 1, 5, LEAF_H), (3, 5, 1, 3, LEAF),
    (5, 2, 1, 6, LEAF), (6, 4, 1, 4, LEAF_H), (8, 3, 1, 5, LEAF),
])

FLOWER = svg(8, 10, [
    (3, 4, 1, 6, LEAF), (1, 6, 2, 1, LEAF_H), (5, 7, 2, 1, LEAF_H),
    (2, 1, 3, 1, PETAL), (1, 2, 5, 2, PETAL), (2, 4, 3, 1, PETAL),
    (3, 2, 1, 1, POLLEN),
])

ROCK_S = svg(12, 8, [
    (3, 1, 6, 1, OUT_R), (1, 2, 10, 1, OUT_R),
    (1, 3, 10, 4, ROCK), (3, 3, 3, 1, ROCK_H),
    (1, 7, 10, 1, OUT_R),
])

CRYSTAL = svg(10, 14, [
    (4, 0, 2, 2, CRY_H),
    (3, 2, 4, 9, CRY), (3, 3, 1, 6, CRY_H),
    (2, 5, 1, 5, CRY), (7, 6, 1, 4, CRY),
    (2, 11, 6, 2, OUT_R),
])


def ghost(step: int) -> str:
    """유령. 0/1 로 아랫자락이 흔들린다."""
    g = "#dfe7ef"
    gs = "#9fb0c2"
    body = [
        (4, 0, 6, 1, OUT_D),
        (2, 1, 10, 1, OUT_D), (2, 2, 10, 7, g), (3, 2, 3, 2, "#ffffff"),
        (1, 3, 1, 6, OUT_D), (12, 3, 1, 6, OUT_D),
        (4, 4, 2, 2, OUT_D), (8, 4, 2, 2, OUT_D),   # 눈
        (6, 7, 2, 1, gs),                            # 입
    ]
    if step == 0:
        tail = [(2, 9, 2, 2, g), (5, 9, 2, 3, g), (8, 9, 2, 2, g), (10, 9, 2, 3, g)]
    else:
        tail = [(2, 9, 2, 3, g), (5, 9, 2, 2, g), (8, 9, 2, 3, g), (10, 9, 2, 2, g)]
    return svg(14, 12, body + tail)


def bird(step: int) -> str:
    """작은 새. 0=날개 위, 1=날개 아래."""
    b = "#f2b23e"
    bs = "#c9871f"
    body = [
        (5, 3, 6, 1, OUT_D), (4, 4, 8, 4, b), (4, 4, 8, 1, OUT_D),
        (5, 8, 6, 1, OUT_D),
        (6, 5, 1, 1, OUT_D),                         # 눈
        (2, 5, 2, 1, bs), (1, 5, 1, 1, OUT_D),       # 부리
        (11, 4, 3, 1, bs), (12, 5, 2, 1, bs),        # 꼬리
    ]
    w = [(6, 2, 4, 2, bs)] if step == 0 else [(6, 7, 4, 2, bs)]
    return svg(15, 11, body + w)


def golem(step: int) -> str:
    """바위 골렘. 0/1 로 몸이 한 칸 들썩인다."""
    dy = 0 if step == 0 else 1
    return svg(14, 14, [
        (3, 1 + dy, 8, 1, OUT_R),
        (2, 2 + dy, 10, 6, ROCK), (2, 2 + dy, 10, 1, OUT_R),
        (3, 3 + dy, 3, 1, ROCK_H),
        (3, 4 + dy, 2, 2, CRY), (9, 4 + dy, 2, 2, CRY),   # 수정 눈
        (2, 8 + dy, 10, 1, OUT_R),
        (1, 9, 4, 4, ROCK), (1, 9, 4, 1, OUT_R),          # 팔·다리는 고정
        (9, 9, 4, 4, ROCK), (9, 9, 4, 1, OUT_R),
        (1, 13, 12, 1, OUT_R),
    ])


SAPLING = svg(10, 12, [
    (4, 3, 2, 1, OUT_G),
    (3, 4, 4, 3, LEAF), (4, 4, 1, 1, LEAF_H),
    (3, 7, 4, 1, OUT_G),
    (4, 8, 2, 3, TRUNK),
    (3, 11, 4, 1, OUT_G),
])

# 완료 이펙트용 별.
STAR = svg(8, 8, [
    (3, 0, 2, 8, AMBER), (0, 3, 8, 2, AMBER),
    (2, 2, 4, 4, AMBER), (3, 3, 2, 2, "#fff3d0"),
])


def fire(step: int) -> str:
    """모닥불. 0/1 로 불꽃이 흔들린다."""
    logs = [
        (1, 10, 12, 1, OUT_D), (2, 11, 10, 2, TRUNK),
        (3, 11, 3, 1, ROCK_H),
    ]
    if step == 0:
        fl = [
            (6, 1, 2, 2, FLAME_A), (5, 3, 4, 3, FLAME_A),
            (4, 5, 6, 5, FLAME_B), (5, 6, 2, 3, FLAME_A),
            (3, 8, 1, 2, FLAME_B), (10, 7, 1, 3, FLAME_B),
        ]
    else:
        fl = [
            (5, 0, 2, 2, FLAME_A), (5, 2, 3, 4, FLAME_A),
            (4, 4, 6, 6, FLAME_B), (6, 6, 2, 3, FLAME_A),
            (3, 7, 1, 3, FLAME_B), (10, 8, 1, 2, FLAME_B),
        ]
    return svg(14, 14, fl + logs)


SPRITES = {
    "--spr-robot-0": robot(0), "--spr-robot-1": robot(1),
    "--spr-slime-0": slime(0), "--spr-slime-1": slime(1),
    "--spr-bat-0": bat(0), "--spr-bat-1": bat(1),
    "--spr-fire-0": fire(0), "--spr-fire-1": fire(1),
    "--spr-tree": TREE, "--spr-bush": BUSH, "--spr-grass": GRASS,
    "--spr-flower": FLOWER, "--spr-rock": ROCK_S, "--spr-crystal": CRYSTAL,
    "--spr-mushroom": MUSHROOM,
    "--spr-ghost-0": ghost(0), "--spr-ghost-1": ghost(1),
    "--spr-bird-0": bird(0), "--spr-bird-1": bird(1),
    "--spr-golem-0": golem(0), "--spr-golem-1": golem(1),
    "--spr-sapling": SAPLING, "--spr-star": STAR,
}

# ---------------------------------------------------------------- CSS
DECL = "\n".join(f"  {k}: {v};" for k, v in SPRITES.items())

BLOCK = f"""{BEGIN}

:root {{
{DECL}
}}

/* 스프라이트 공통. 도트가 뭉개지지 않게 pixelated 로 확대한다. */
.spr {{
  position: absolute;
  background-repeat: no-repeat;
  background-size: 100% 100%;
  image-rendering: pixelated;
  pointer-events: none;
}}

/* ---------- 사이드바 하단 지면 ----------
   목차 아래에 늘 보이는 작은 풍경. 여기에 로봇이 걸어다닌다. */
#pixel-field {{
  position: relative;
  height: 74px;
  flex: none;
  overflow: hidden;
  border-top: var(--bw) solid var(--ink);
  background: var(--bg-sunken);
}}
/* 땅 */
#pixel-field::after {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0; height: 8px;
  background:
    repeating-linear-gradient(90deg,
      color-mix(in srgb, {LEAF} 70%, var(--bg-sunken)) 0 4px,
      color-mix(in srgb, {LEAF} 45%, var(--bg-sunken)) 4px 8px);
  border-top: 2px solid {OUT_G};
}}
#pixel-field .spr {{ bottom: 8px; }}

.pf-tree     {{ background-image: var(--spr-tree);     width: 40px; height: 55px; left: 6px; }}
.pf-bush     {{ background-image: var(--spr-bush);     width: 34px; height: 24px; right: 10px; }}
.pf-grass    {{ background-image: var(--spr-grass);    width: 24px; height: 19px; left: 56px; }}
.pf-flower   {{ background-image: var(--spr-flower);   width: 18px; height: 23px; right: 56px; }}
.pf-rock     {{ background-image: var(--spr-rock);     width: 30px; height: 20px; left: 94px; }}
.pf-mushroom {{ background-image: var(--spr-mushroom); width: 24px; height: 24px; left: 140px; }}

/* 걸어다니는 로봇 — 2프레임 교대 + 좌우 왕복.
   translateX 에도 steps() 를 걸어 픽셀 격자 위를 움직이는 느낌을 준다. */
.pf-robot {{
  background-image: var(--spr-robot-0);
  width: 40px; height: 40px; left: 0;
  animation: spr-walk .5s steps(1) infinite, pf-patrol 24s steps(48) infinite;
}}
@keyframes spr-walk {{
  50% {{ background-image: var(--spr-robot-1); }}
}}
@keyframes pf-patrol {{
  0%   {{ transform: translateX(4px) scaleX(1); }}
  45%  {{ transform: translateX(230px) scaleX(1); }}
  50%  {{ transform: translateX(230px) scaleX(-1); }}
  95%  {{ transform: translateX(4px) scaleX(-1); }}
  100% {{ transform: translateX(4px) scaleX(1); }}
}}

/* 통통 튀는 슬라임 */
.pf-slime {{
  background-image: var(--spr-slime-0);
  width: 34px; height: 29px; right: 92px;
  animation: spr-hop 1.1s steps(1) infinite;
}}
@keyframes spr-hop {{
  0%, 49%  {{ background-image: var(--spr-slime-0); transform: translateY(0); }}
  50%, 99% {{ background-image: var(--spr-slime-1); transform: translateY(-6px); }}
}}

/* ---------- 표지 풍경 띠 ---------- */
.home-scene {{
  position: relative;
  height: 132px;
  margin: 4px 0 22px;
  overflow: hidden;
  border: var(--bw) solid var(--ink);
  background: var(--bg-soft);
  box-shadow: inset var(--bw) var(--bw) 0 var(--bevel-hi),
              inset calc(var(--bw) * -1) calc(var(--bw) * -1) 0 var(--bevel-lo),
              var(--shadow);
}}
/* 먼 언덕 */
.home-scene::before {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 10px; height: 34px;
  background:
    radial-gradient(circle at 18% 100%, color-mix(in srgb, {LEAF} 34%, var(--bg-soft)) 0 46px, transparent 47px),
    radial-gradient(circle at 62% 100%, color-mix(in srgb, {LEAF} 26%, var(--bg-soft)) 0 58px, transparent 59px),
    radial-gradient(circle at 92% 100%, color-mix(in srgb, {LEAF} 30%, var(--bg-soft)) 0 40px, transparent 41px);
}}
/* 땅 */
.home-scene::after {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0; height: 10px;
  background:
    repeating-linear-gradient(90deg,
      color-mix(in srgb, {LEAF} 70%, var(--bg-soft)) 0 5px,
      color-mix(in srgb, {LEAF} 45%, var(--bg-soft)) 5px 10px);
  border-top: 2px solid {OUT_G};
}}
.home-scene .spr {{ bottom: 10px; }}

.hs-tree-a   {{ background-image: var(--spr-tree);     width: 56px; height: 77px; left: 18px; }}
.hs-tree-b   {{ background-image: var(--spr-tree);     width: 38px; height: 52px; left: 86px; opacity: .85; }}
.hs-bush     {{ background-image: var(--spr-bush);     width: 42px; height: 30px; left: 148px; }}
.hs-flower   {{ background-image: var(--spr-flower);   width: 22px; height: 28px; left: 208px; }}
.hs-mushroom {{ background-image: var(--spr-mushroom); width: 30px; height: 30px; left: 296px; }}
.hs-grass    {{ background-image: var(--spr-grass);    width: 28px; height: 22px; left: 356px; }}
.hs-rock     {{ background-image: var(--spr-rock);     width: 38px; height: 25px; right: 150px; }}
.hs-crystal  {{ background-image: var(--spr-crystal);  width: 30px; height: 42px; right: 40px; }}

.hs-robot {{
  background-image: var(--spr-robot-0);
  width: 46px; height: 46px; left: 0;
  animation: spr-walk .5s steps(1) infinite, hs-patrol 30s steps(60) infinite;
}}
@keyframes hs-patrol {{
  0%   {{ transform: translateX(430px) scaleX(-1); }}
  46%  {{ transform: translateX(24px) scaleX(-1); }}
  50%  {{ transform: translateX(24px) scaleX(1); }}
  96%  {{ transform: translateX(430px) scaleX(1); }}
  100% {{ transform: translateX(430px) scaleX(-1); }}
}}
.hs-slime {{
  background-image: var(--spr-slime-0);
  width: 38px; height: 33px; left: 248px;   /* 로봇 순찰 종점(~430px)을 피한다 */
  animation: spr-hop 1.3s steps(1) infinite;
}}
/* 박쥐는 땅에 안 붙는다 — 위쪽을 떠다닌다 */
.hs-bat {{
  background-image: var(--spr-bat-0);
  width: 40px; height: 30px; top: 14px; right: 64px; bottom: auto;
  animation: spr-flap .34s steps(1) infinite, hs-drift 13s steps(26) infinite alternate;
}}
@keyframes spr-flap {{
  50% {{ background-image: var(--spr-bat-1); }}
}}
@keyframes hs-drift {{
  0%   {{ transform: translate(0, 0); }}
  50%  {{ transform: translate(-90px, 16px); }}
  100% {{ transform: translate(-170px, -6px); }}
}}

/* ---------- 절 끝 모닥불 ---------- */
#page-foot {{ position: relative; }}
#page-foot::before {{
  content: "";
  display: block; width: 42px; height: 42px; margin: 0 auto 10px;
  background-image: var(--spr-fire-0);
  background-repeat: no-repeat; background-size: 100% 100%;
  image-rendering: pixelated;
  animation: spr-fire .28s steps(1) infinite;
}}
@keyframes spr-fire {{
  50% {{ background-image: var(--spr-fire-1); }}
}}

/* ---------- 검색 결과 없음 ---------- */
.sr-empty::before {{
  content: "";
  display: block; width: 42px; height: 36px; margin: 0 auto 12px;
  background-image: var(--spr-slime-0);
  background-repeat: no-repeat; background-size: 100% 100%;
  image-rendering: pixelated;
  opacity: .75;
}}

/* 움직임을 줄여 달라고 한 사용자에게는 전부 정지시킨다.
   장식이 접근성을 이기면 안 된다. */
@media (prefers-reduced-motion: reduce) {{
  .pf-robot, .pf-slime, .hs-robot, .hs-slime, .hs-bat,
  #page-foot::before {{
    animation: none !important;
  }}
  .pf-robot {{ transform: translateX(80px); }}
  .hs-robot {{ transform: translateX(250px); }}
}}

@media (max-width: 900px) {{
  /* 좁은 화면에서는 표지 풍경만 낮추고, 사이드바 지면은 서랍 안이라 그대로 둔다. */
  .home-scene {{ height: 104px; }}
  .hs-flower, .hs-tree-b, .hs-mushroom {{ display: none; }}
}}

@media print {{
  #pixel-field, .home-scene {{ display: none !important; }}
  #page-foot::before, .sr-empty::before {{ display: none !important; }}
}}

{END}"""


def main() -> None:
    css = CSS.read_text(encoding="utf-8")
    if BEGIN in css and END in css:
        css = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END),
            lambda _: BLOCK,
            css,
            flags=re.S,
        )
    else:
        css = css.rstrip() + "\n\n" + BLOCK + "\n"
    CSS.write_text(css, encoding="utf-8", newline="\n")
    print(f"스프라이트 {len(SPRITES)}개 심음 · style.css {CSS.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
