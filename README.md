# 파이썬 완전 정복

기초부터 ROS 2까지 다루는 개인용 학습 가이드북. 브라우저에서 도는 단일 웹앱이다.

## 여는 법

**PC** — `index.html` 을 더블클릭한다. 서버도 인터넷도 필요 없다.

**휴대폰** — PC에서 아래를 실행하고, 같은 와이파이에 연결된 폰에서 출력된 `http://192.168.x.x:8800` 주소를 연다.

```bash
python build.py --serve
```

## 고치는 법

본문은 `content/` 아래 마크다운이다. 고친 뒤 빌드하면 앱에 반영된다.

```bash
python build.py           # 한 번 빌드
python build.py --watch   # 저장할 때마다 자동 빌드
```

## 구조

```
index.html          앱 껍데기
assets/
  style.css         스타일 (라이트/다크)
  markdown.js       이 책 전용 마크다운 렌더러 (의존성 없음)
  highlight.js      구문 강조기 (의존성 없음)
  app.js            라우팅 · 목차 · 검색 · 진도
  bundle.js         빌드 산출물 (build.py 가 생성)
content/
  toc.json          책의 목차 — 여기가 뼈대다
  <part>/<id>.md    각 절의 본문
build.py            content/ → assets/bundle.js
```

`content/toc.json` 의 챕터 `id` 와 마크다운 파일 이름(`<id>.md`)이 짝이다. 빌드 스크립트가 `content/` 아래를 뒤져 자동으로 연결하므로 폴더 구조는 자유롭게 바꿔도 된다.

### 왜 번들을 만드나

`file://` 로 열면 브라우저가 `fetch()` 를 CORS로 막는다. 마크다운을 JS 파일 안에 JSON으로 박아 `<script>` 로 읽히면 서버 없이도 동작한다. 그래서 `assets/bundle.js` 는 빌드 산출물이지만 일부러 커밋한다 — 휴대폰에서는 `build.py` 를 돌릴 수 없기 때문이다.

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

## 단축키

| 키 | 동작 |
| --- | --- |
| <kbd>/</kbd> 또는 <kbd>Ctrl</kbd>+<kbd>K</kbd> | 전체 검색 |
| <kbd>[</kbd> / <kbd>]</kbd> | 이전 / 다음 절 |
| <kbd>Esc</kbd> | 닫기 |

## 진도

브라우저 `localStorage` 에 저장된다. 따라서 PC와 휴대폰의 진도는 따로 집계된다.
