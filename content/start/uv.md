# 0.3 uv로 프로젝트·가상환경·의존성 관리

::: lead
"내 컴퓨터에선 되는데요"는 농담이 아니라 실제 비용이다. 이 절은 그 문장이 나올 수 없는 프로젝트를 만드는 법을 다룬다. 도구는 uv를 쓰지만, 진짜 배울 것은 **가상환경이 무엇이고 왜 필요한가**, 그리고 **의존성을 어떻게 고정하는가**다. 이건 도구가 바뀌어도 남는 지식이다.
:::

## 문제: 왜 격리가 필요한가

파이썬을 처음 배울 때는 그냥 `pip install` 하고 쓴다. 프로젝트가 하나일 때는 문제가 없다. 둘이 되는 순간 깨진다.

프로젝트 A는 `numpy 1.26` 을 요구하고, 프로젝트 B는 `numpy 2.2` 를 요구한다고 하자. 전역에 하나만 깔 수 있다면 **둘 중 하나는 반드시 깨진다**. 이게 전부다. 가상환경(virtual environment)은 이 문제 하나를 풀기 위해 존재한다.

```text nolines
전역에 설치           프로젝트마다 격리

  시스템 파이썬          시스템 파이썬 (건드리지 않음)
       │                       │
   numpy 2.2  ← 충돌!      ┌───┴───┐
   numpy 1.26              │       │
                        프로젝트A  프로젝트B
                        numpy1.26  numpy2.2
```

::: deep 가상환경의 정체는 놀랄 만큼 단순하다
가상환경은 마법이 아니다. 컨테이너도 아니고, 샌드박스도 아니다. **디렉터리 하나**다.

```text nolines
.venv/
├── pyvenv.cfg          ← "진짜 파이썬은 여기 있다"고 적힌 텍스트 파일
├── Scripts/            (Windows) 또는 bin/ (Unix)
│   ├── python.exe      ← 시스템 파이썬을 가리키는 얇은 껍데기
│   └── pip.exe
└── Lib/site-packages/  ← 이 환경에 설치된 패키지들이 실제로 사는 곳
```

동작 원리는 이렇다. `.venv/Scripts/python.exe` 를 실행하면, 인터프리터는 자기 자신의 위치를 보고 옆의 `pyvenv.cfg` 를 찾는다. 그 파일이 있으면 **`sys.prefix` 를 이 디렉터리로 잡고, `sys.path` 의 `site-packages` 를 여기 것으로 바꾼다.** 표준 라이브러리는 원래 파이썬 것을 그대로 쓴다.

즉 가상환경은 *"패키지를 어디서 찾을지"* 만 바꾸는 장치다. 이걸 알면 아래 것들이 전부 자명해진다.

- 가상환경은 **복사해서 옮기면 대체로 깨진다** (`pyvenv.cfg` 의 절대 경로가 원본을 가리킨다). 그래서 `.venv` 는 git에 넣지 않고 **잠금 파일로부터 재생성**한다.
- `activate` 는 그저 `PATH` 앞에 `.venv/Scripts` 를 끼워 넣는 셸 스크립트일 뿐이다. 신비로운 게 없다.
- 가상환경 안의 `python` 을 **전체 경로로 직접 실행하면 activate 없이도 그 환경이 쓰인다.**
:::

## uv의 두 가지 사용법

uv에는 결이 다른 두 가지 방식이 있다. 이걸 구분하지 못하면 문서를 읽어도 헷갈린다.

| 방식 | 명령 | 쓰는 때 |
| --- | --- | --- |
| **프로젝트 방식** | `uv init`, `uv add`, `uv run`, `uv sync` | 거의 항상. 재현 가능한 프로젝트를 만들 때 |
| **pip 호환 방식** | `uv venv`, `uv pip install` | 기존 `requirements.txt` 프로젝트를 빠르게 다룰 때 |

**프로젝트 방식을 기본으로 써라.** pip 호환 방식은 옛 프로젝트를 위한 탈출구다.

## 프로젝트 만들기

```bash
uv init --python 3.14 pybook-practice
cd pybook-practice
```

만들어진 것을 보자.

```text nolines
pybook-practice/
├── .python-version      3.14
├── pyproject.toml       프로젝트 정의 — 이 파일이 핵심이다
├── README.md
├── main.py
└── .git/
```

`pyproject.toml` 은 이렇게 생겼다.

```toml title="pyproject.toml"
[project]
name = "pybook-practice"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.14"
dependencies = []
```

::: note pyproject.toml 은 uv의 것이 아니다
이건 **PEP 621이 정한 표준**이다. uv, poetry, pdm, hatch, pip 모두 이 파일을 읽는다. 그래서 uv로 시작한 프로젝트를 나중에 다른 도구로 옮길 수 있다. `[tool.uv]` 처럼 `[tool.*]` 섹션만 각 도구의 전용 영역이다.

이게 중요한 이유: **도구는 유행을 타지만 표준은 남는다.** uv 이전에 poetry가 있었고, poetry 이전에 pipenv가 있었다. `pyproject.toml` 을 이해해 두면 다음 도구가 뭐가 되든 30분이면 적응한다. 자세한 건 [6.5 패키징](#/packaging)에서.
:::

## 패키지 추가

```bash
uv add numpy
```

이 한 줄이 실제로 한 일:

1. `.venv/` 가 없으면 만든다 (3.14 인터프리터로).
2. numpy와 그 의존성의 버전을 **해결(resolve)** 한다.
3. `.venv/Lib/site-packages/` 에 설치한다.
4. `pyproject.toml` 의 `dependencies` 에 `numpy>=2.2.0` 를 추가한다.
5. **`uv.lock` 에 해결된 정확한 버전 전부를 기록한다.**

4번과 5번의 차이가 핵심이다.

::: warn 선언과 잠금은 다르다 — 이게 이 절에서 제일 중요하다
`pyproject.toml` 의 `dependencies` 는 **의도**다. "나는 numpy 2.2 이상이면 된다."

`uv.lock` 은 **사실**이다. "이 프로젝트는 numpy 2.2.4, 그리고 그게 끌고 온 의존성 전부를 정확히 이 버전으로 쓴다."

왜 둘 다 필요한가? `pyproject.toml` 만 있으면, 오늘 설치한 사람과 6개월 뒤 설치한 사람이 **다른 버전을 받는다**. numpy 2.3이 나왔을 테니까. 그러면 "내 컴퓨터에선 되는데"가 시작된다.

| 파일 | 내용 | git에 넣나 | 사람이 고치나 |
| --- | --- | --- | --- |
| `pyproject.toml` | 느슨한 범위 (의도) | ✅ | ✅ |
| `uv.lock` | 정확한 버전 (사실) | ✅ | ❌ 절대 |
| `.venv/` | 실제 설치된 파일 | ❌ | ❌ |

**`.venv` 는 git에 넣지 않는다.** 잠금 파일이 있으면 언제든 똑같이 재생성되기 때문이다. 그게 잠금 파일의 존재 이유다.
:::

의존성 종류를 나눌 수도 있다. 테스트 도구는 라이브러리 사용자에게 필요 없다.

```bash
uv add --dev pytest ruff        # 개발할 때만 필요
uv add "torch>=2.6"             # 버전 제약 직접 지정
uv add "fastapi[standard]"      # 선택적 추가 기능(extra)
uv remove numpy
```

## 실행: uv run

여기서 습관 하나를 들이면 평생 편하다.

```bash
uv run python main.py
uv run pytest
uv run python -c "import numpy; print(numpy.__version__)"
```

::: tip activate를 잊어라
전통적으로는 `source .venv/bin/activate` 를 먼저 하고 `python` 을 쳤다. `uv run` 은 그 단계를 없앤다. 매번 다음을 자동으로 한다.

1. `.venv` 가 없거나 낡았으면 만든다/맞춘다.
2. `uv.lock` 과 실제 설치 상태가 다르면 동기화한다.
3. 그 환경의 파이썬으로 명령을 실행한다.

**"활성화하는 걸 깜빡해서 전역에 설치했다"** 는 사고가 구조적으로 불가능해진다. 편의 기능이 아니라 안전장치다.
:::

물론 activate도 여전히 된다. 대화형으로 이것저것 해볼 때는 편하다.

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

deactivate     # 나가기
```

::: danger PowerShell 실행 정책 오류
Windows에서 `Activate.ps1` 이 *"이 시스템에서 스크립트를 실행할 수 없으므로"* 오류를 내면, PowerShell의 기본 실행 정책이 스크립트를 막고 있는 것이다.

```bash
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`RemoteSigned` 는 "인터넷에서 받은 스크립트는 서명이 있어야 하고, 내가 만든 로컬 스크립트는 그냥 실행"이라는 뜻이다. `Unrestricted` 로 풀지 마라 — 굳이 방어막을 걷어낼 이유가 없다.

애초에 `uv run` 만 쓰면 이 문제를 만날 일이 없다.
:::

## 팀원이 프로젝트를 받았을 때

이게 전부다.

```bash
git clone <repo>
cd <repo>
uv sync           # uv.lock 그대로 환경을 만든다
uv run pytest
```

`uv sync` 는 **잠금 파일에 적힌 것과 정확히 일치하는 환경**을 만든다. 더 최신 버전이 나왔어도 무시한다. 그래서 6개월 뒤에 받은 사람도 같은 환경을 얻는다.

의존성을 의도적으로 올리고 싶을 때만 명시적으로 한다.

```bash
uv lock --upgrade                # 전부 최신으로 다시 해결
uv lock --upgrade-package numpy  # numpy만
```

::: note 재현성의 한계
`uv.lock` 이 보장하는 것은 **파이썬 패키지 버전**까지다. 다음은 보장하지 못한다.

- OS와 시스템 라이브러리 (`libGL`, CUDA 드라이버 …)
- CPU 아키텍처 (x86-64 / arm64)
- 컴파일된 확장 모듈의 빌드 옵션

그래서 딥러닝처럼 GPU·드라이버까지 얽히는 환경은 도커까지 가야 진짜 재현이 된다. [6.7 도커](#/docker)에서 다룬다.
:::

## 도구 실행: uvx

프로젝트에 넣기는 싫고 명령줄 도구로만 쓰고 싶을 때가 있다.

```bash
uvx ruff check .          # ruff를 설치하지 않고 일회성 실행
uvx --from httpie http GET example.com
uv tool install ruff      # 전역 도구로 영구 설치
```

`uvx` 는 도구를 격리된 임시 환경에 받아 실행하고 캐시해 둔다. **프로젝트의 의존성을 오염시키지 않으면서** 도구를 쓸 수 있다.

## 단일 파일 스크립트 (PEP 723)

의외로 잘 안 알려진 기능인데, 알아 두면 대단히 편하다. 파일 하나짜리 스크립트에 의존성을 **주석으로** 적을 수 있다.

```python title="fetch.py"
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "rich"]
# ///

import httpx
from rich import print

r = httpx.get("https://api.github.com/repos/python/cpython")
print({"stars": r.json()["stargazers_count"]})
```

```bash
uv run fetch.py     # 의존성을 자동으로 갖춘 임시 환경에서 실행
```

프로젝트 폴더도, 가상환경도, `pyproject.toml` 도 필요 없다. **스크립트 파일 하나만 주고받으면 상대방도 그냥 실행된다.** 잡일 자동화 스크립트에 최적이다.

## 기존 프로젝트: pip 호환 방식

`requirements.txt` 를 쓰는 옛 프로젝트를 만나면:

```bash
uv venv                                  # .venv 생성
uv pip install -r requirements.txt       # pip처럼 설치 (훨씬 빠름)
uv pip compile requirements.in -o requirements.txt   # 잠금 파일 생성
uv pip list
```

`uv pip` 는 pip의 인터페이스를 흉내 낸 것이다. 익숙한 명령을 그대로 쓰되 속도만 얻는다. **다만 이 방식에는 `uv.lock` 이 없다** — 재현성은 `uv pip compile` 로 직접 챙겨야 한다.

::: cote 코딩테스트 포인트
코딩테스트에서는 이 절의 내용이 **거의 쓸모없다**. 채점 서버에는 표준 라이브러리와 (가끔) numpy 정도만 있고, 당신이 패키지를 설치할 수 없다.

대신 알아 둘 것:

- **표준 라이브러리만으로 푸는 습관**을 들여라. `collections`, `heapq`, `bisect`, `itertools`, `functools`, `math` — 이것들은 어디에나 있다. ([7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost))
- 로컬 연습 환경은 `uv init` 으로 하나 만들어 두고 계속 쓰면 된다. 문제 풀이용으로는 `uv add pytest` 정도면 충분하다.
:::

## 자주 쓰는 명령 정리

| 명령 | 하는 일 |
| --- | --- |
| `uv init <이름>` | 새 프로젝트 |
| `uv add <패키지>` | 의존성 추가 (+ 잠금 갱신) |
| `uv add --dev <패키지>` | 개발 전용 의존성 |
| `uv remove <패키지>` | 제거 |
| `uv sync` | 잠금 파일대로 환경 맞추기 |
| `uv lock --upgrade` | 의존성 최신으로 재해결 |
| `uv run <명령>` | 프로젝트 환경에서 실행 |
| `uv tree` | 의존성 트리 보기 |
| `uvx <도구>` | 도구 일회성 실행 |
| `uv python list` | 설치된 파이썬 목록 |
| `uv cache clean` | 캐시 정리 (디스크가 부족할 때) |

## 요약

- 가상환경은 마법이 아니라 **`sys.path` 를 바꾸는 디렉터리 하나**다. 이 사실을 알면 관련 문제 대부분이 자명해진다.
- **`pyproject.toml`(의도)과 `uv.lock`(사실)은 다르다.** 둘 다 커밋하고, `.venv` 는 커밋하지 않는다.
- **`uv run` 을 기본 습관으로** 삼으면 "활성화를 깜빡해서" 생기는 사고가 사라진다.
- 잠금 파일은 파이썬 패키지까지만 재현한다. 시스템·GPU까지 필요하면 도커로 간다.
- `pyproject.toml` 은 표준이다. 도구는 바뀌어도 이 지식은 남는다.

::: quiz 연습문제
1. `.venv` 폴더를 통째로 다른 경로에 복사한 뒤 그 안의 `python` 을 실행하면 어떻게 되는가? 왜 그런지 `pyvenv.cfg` 를 열어 확인하고 설명하라.
2. `uv add numpy` 만 하고 `uv.lock` 을 커밋하지 않았다. 3개월 뒤 팀원이 `uv sync` 했을 때 벌어질 수 있는 일을 구체적으로 서술하라.
3. PEP 723 스크립트를 하나 만들어라. `httpx` 로 아무 공개 API나 호출해 결과를 출력하는 10줄짜리면 된다. 가상환경을 직접 만들지 않고 `uv run` 만으로 동작하는지 확인하라.
4. `uv run python -c "import sys; print(sys.prefix)"` 를 프로젝트 안과 밖에서 각각 실행해 비교하라. 이전 절의 연습문제 2번 답이 여기 있다.
:::

**다음 절**: [0.4 린터·포매터·타입체커 세팅](#/tooling) — 실수를 사람이 아니라 도구가 잡게 만드는 법.
