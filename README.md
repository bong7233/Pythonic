# 파이썬 완전 정복

기초부터 코딩테스트·실무·ROS 2까지, **13개 부 148개 절**의 개인용 학습 가이드북.
브라우저에서 도는 단일 웹앱이다. 설치도, 서버도, 인터넷도 필요 없다.

## 여는 법

**PC** — `index.html` 을 더블클릭한다. 끝이다.

**휴대폰** — PC에서 아래를 실행하고, 같은 와이파이에 연결된 폰에서 출력된
`http://192.168.x.x:8800` 주소를 연다. 홈 화면에 추가하면 앱처럼 쓸 수 있다.

```bash
python build.py --serve
```

## 쓰는 법

- 왼쪽이 목차, 오른쪽이 현재 절의 소제목. 위쪽 칸으로 목차를 걸러낼 수 있다.
- 절 맨 아래 **완료** 버튼을 누르면 진도가 쌓인다. 레벨이 오르고, 표지의 풍경이
  자라고, 한 부를 끝낼 때마다 동료가 도감에 채워진다.
- 진도는 브라우저에 저장된다. **PC와 휴대폰은 따로 집계된다.**

| 키 | 동작 |
| --- | --- |
| <kbd>/</kbd> 또는 <kbd>Ctrl</kbd>+<kbd>K</kbd> | 전체 본문 검색 |
| <kbd>[</kbd> / <kbd>]</kbd> | 이전 / 다음 절 |
| <kbd>Esc</kbd> | 닫기 |

첫 절 **0.1 이 책을 읽는 법**에 목표별 학습 경로가 있다.
코딩테스트가 급하면 Part XI부터, 로봇이 목표면 Part I → IV → X 순이다.

## 본문을 고치고 싶을 때

본문은 `content/` 아래 마크다운이다. 고친 뒤 빌드하면 앱에 반영된다.

```bash
python build.py           # 한 번 빌드
python build.py --watch   # 저장할 때마다 자동 빌드
```

`content/toc.json` 의 챕터 `id` 와 파일 이름(`<id>.md`)이 짝이다. 빌드 스크립트가
`content/` 아래를 뒤져 자동으로 연결하므로 폴더 구조는 자유롭게 바꿔도 된다.

집필 규범은 [docs/STYLE.md](docs/STYLE.md), 작업 절차와 검증 방법은
[docs/WORKING-NOTES.md](docs/WORKING-NOTES.md)에 있다. 새 파트를 쓴다면 둘 다 읽어라.

## 구조

```
index.html          앱 껍데기
assets/
  style.css         스타일 (다크: 밤의 동굴 / 라이트: 양피지)
  markdown.js       이 책 전용 마크다운 렌더러 (의존성 없음)
  highlight.js      구문 강조기 (의존성 없음)
  app.js            라우팅 · 목차 · 검색 · 진도
  game.js           레벨 · 성장하는 세계 · 동료 도감 · 이펙트
  bundle.js         빌드 산출물 (build.py 가 생성)
content/
  toc.json          책의 목차 — 여기가 뼈대다
  <part>/<id>.md    각 절의 본문
build.py            content/ -> assets/bundle.js
tools/
  check_diagrams.py 아스키 다이어그램 정렬 검사
  make_sprites.py   픽셀 스프라이트를 style.css 에 심는다
```

`assets/game.js` 는 진도를 읽어 다르게 보여줄 뿐 책 내용에는 관여하지 않는다.
거슬리면 이 파일 하나만 지워도 앱은 그대로 돈다.

### 왜 번들을 만드나

`file://` 로 열면 브라우저가 `fetch()` 를 CORS로 막는다. 마크다운을 JS 파일 안에
JSON으로 박아 `<script>` 로 읽히면 서버 없이도 동작한다. 그래서 `assets/bundle.js` 는
빌드 산출물이지만 일부러 커밋한다 — 휴대폰에서는 `build.py` 를 돌릴 수 없기 때문이다.

## 마크다운 확장 문법

일반 마크다운에 더해 이 책에서만 쓰는 것들:

````text
```python title="예제.py" {3,5-7}     코드 제목과 강조할 줄
```pyrepl                             >>> 세션 (프롬프트/출력 구분)

::: note | tip | warn | danger        표시 상자
::: deep | perf | cote | hist
::: quiz | answer                     answer 는 접혀서 나온다
::: lead                              챕터 머리말
:::

$O(n \log n)$                         수식 (인라인)
==형광펜==
````
