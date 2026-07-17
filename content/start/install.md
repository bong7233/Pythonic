# 0.2 파이썬 3.14 설치와 버전 관리

::: lead
"파이썬 설치"는 한 줄짜리 일이 아니다. 인터프리터가 무엇이고, 왜 시스템에 여러 개가 깔리며, `python` 이라고 쳤을 때 어느 것이 실행되는지를 모르면 앞으로 수백 번 헤맨다. 이 절은 그 혼란을 처음부터 없앤다.
:::

## 파이썬은 하나가 아니다

`python` 이라는 이름은 세 가지 다른 것을 가리킨다. 이걸 구분하는 게 시작이다.

| 층위 | 정체 | 예 |
| --- | --- | --- |
| 언어 명세 | 문법과 의미의 규칙 | "파이썬 3.14 언어 레퍼런스" |
| 구현체 | 그 명세를 실제로 실행하는 프로그램 | **CPython**, PyPy, GraalPy |
| 배포판 | 구현체 + 부가 패키지를 묶은 설치본 | python.org 공식, Anaconda, python-build-standalone |

우리가 쓰는 건 **CPython** 이다. C로 작성된 레퍼런스 구현이고, 사실상 표준이다. 이 책에서 "파이썬"이라고 하면 CPython을 뜻한다. `pip install numpy` 가 동작하는 것도, C 확장이 붙는 것도 CPython 기준이다.

::: note 다른 구현체는 언제 쓰나
**PyPy** 는 JIT 컴파일러가 있어 순수 파이썬 반복 연산이 CPython보다 몇 배 빠르다. 하지만 NumPy·PyTorch 같은 C 확장 생태계와의 궁합이 나쁘다. **GraalPy** 는 JVM 위에서 돈다. 우리 목표(ML·비전·ROS)는 전부 C 확장에 의존하므로 CPython 외의 선택지는 사실상 없다. 성능 문제는 [Part V](#/profiling)에서 다른 방법으로 푼다.
:::

## 왜 3.14인가

3.14는 2025년 10월에 나왔다. 이 책이 3.14를 기준으로 삼는 이유는 단순히 최신이라서가 아니라, **이 버전에서 파이썬의 성격이 바뀐 지점들이 있기 때문**이다.

- **자유 스레드(free-threaded) 빌드가 공식 지원 단계로 올라갔다.** 3.13에서 실험적으로 등장한 GIL 없는 파이썬이 3.14에서 정식 지원 대상이 됐다. 파이썬으로 진짜 멀티코어 병렬을 하는 이야기가 여기서 시작된다. ([4.3 GIL](#/gil))
- **어노테이션 평가 방식이 바뀌었다** (PEP 649/749). 타입 힌트가 게으르게(lazily) 평가되면서, 오랫동안 파이썬 타입 시스템을 괴롭힌 순환 참조 문제가 풀렸다. ([2.9 런타임 타입 정보](#/runtime-typing))
- **서브인터프리터가 표준 라이브러리에 들어왔다** (PEP 734, `concurrent.interpreters`). 스레드도 프로세스도 아닌 세 번째 병렬 축이다. ([4.9 서브인터프리터](#/subinterpreters))
- **t-string** (PEP 750) 이라는 새 문자열 리터럴이 생겼다. f-string이 즉시 문자열을 만든다면, t-string은 "보간 결과를 가로챌 수 있는 구조"를 만든다. SQL 인젝션·XSS 방어의 기반이 된다.

::: warn 3.14를 쓰면 안 되는 경우
**ROS 2는 배포판이 정한 파이썬 버전에 묶여 있다.** 예를 들어 Ubuntu 24.04 기반 배포판은 시스템 파이썬 3.12를 쓴다. ROS 노드를 만들 때는 3.14가 아니라 그 배포판의 파이썬을 써야 한다. 마찬가지로 회사 프로덕션 환경이 3.11이라면 거기에 맞춰야 한다.

그래서 **버전을 여러 개 깔고 프로젝트마다 갈아 끼우는 능력**이 필요하다. 이 절의 진짜 주제가 그것이다.
:::

이 책의 코드는 대부분 **3.10 이상**이면 돌아간다. 버전이 갈리는 지점은 그때마다 `3.12+` 처럼 표시한다.

## 설치: uv 하나로 끝낸다

전통적인 방법은 python.org에서 설치 프로그램을 받는 것이다. 하지만 2026년 현재 더 나은 방법이 있다.

**uv** 는 Rust로 만든 파이썬 도구다. 패키지 설치(`pip`), 가상환경(`venv`), 의존성 잠금(`poetry`), 그리고 **파이썬 인터프리터 자체의 설치와 버전 관리**(`pyenv`)까지 하나로 처리한다. 압도적으로 빠르고, 무엇보다 **파이썬이 없어도 설치된다** — uv는 파이썬으로 만들어지지 않았기 때문이다.

::: hist 왜 도구가 이렇게 많았나
파이썬의 패키징은 오랫동안 악명 높았다. `distutils` → `setuptools` → `pip` → `virtualenv` → `venv` → `pipenv` → `poetry` → `pdm` … 각각이 앞의 것의 문제를 고치려다 새 문제를 만들었다. 여기에 `pyenv`(버전 관리), `conda`(과학 계산용 별도 생태계)가 겹치면서 초심자가 "무엇을 써야 하나"에서 며칠을 잃었다.

uv는 이 전체를 하나로 흡수하려는 시도이고, 현재까지는 성공적이다. 이 책이 uv를 기본으로 삼는 이유다. 다만 **아래에 깔린 표준(PEP 517/518/621, `pyproject.toml`)은 그대로**이므로, uv를 쓰다가 다른 도구로 옮기는 건 어렵지 않다.
:::

### Windows

PowerShell을 열고:

```bash title="PowerShell"
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

::: warn 스크립트를 파이프로 실행하는 것에 대해
`curl ... | sh` 는 "인터넷에서 받은 스크립트를 즉시 실행"하는 것이므로 원칙적으로 위험한 관용구다. 신뢰하는 도메인(`astral.sh`)이라 관행적으로 쓰지만, 마음에 걸린다면 먼저 내용을 보고 실행해도 된다.

```bash
curl -LsSf https://astral.sh/uv/install.sh -o uv-install.sh
less uv-install.sh          # 눈으로 확인
sh uv-install.sh
```

**출처를 모르는 스크립트에는 절대 이 패턴을 쓰지 마라.** 이건 uv라서 하는 것이지, 일반적으로 괜찮은 게 아니다.
:::

패키지 매니저를 선호한다면 그쪽도 된다.

```bash
# Windows
winget install --id=astral-sh.uv -e

# macOS
brew install uv
```

설치 후 **터미널을 새로 열고** 확인한다. PATH 변경은 이미 열린 터미널에 반영되지 않는다.

```bash
uv --version
```

## 파이썬 인터프리터 설치

이제 파이썬 자체를 깐다.

```bash
uv python install 3.14
```

끝이다. 여러 버전을 동시에 깔 수 있다.

```bash
uv python install 3.12 3.13 3.14
uv python list          # 설치된 것과 설치 가능한 것 모두
```

::: deep uv가 설치하는 파이썬은 무엇인가
uv는 python.org 설치 프로그램을 실행하지 않는다. **python-build-standalone** 이라는 프로젝트가 미리 빌드해 둔, 재배치 가능한(relocatable) CPython 바이너리를 내려받는다. 시스템 어디에도 등록하지 않고 uv가 관리하는 디렉터리(`~/.local/share/uv/python/`)에 풀어 놓을 뿐이다.

이게 중요한 이유:

- **시스템 파이썬을 건드리지 않는다.** 리눅스에서 시스템 파이썬을 잘못 만지면 OS 도구가 깨진다. uv는 그 위험이 없다.
- **관리자 권한이 필요 없다.**
- **지우기 쉽다.** 그 디렉터리를 지우면 흔적이 남지 않는다.

대가도 있다. 이 빌드는 배포판 패키지 관리자가 만든 것과 컴파일 옵션이 미묘하게 다를 수 있다. 실무에서 문제가 되는 경우는 드물지만, ROS처럼 시스템 파이썬에 강하게 묶인 환경에서는 **uv 파이썬이 아니라 시스템 파이썬을 써야 한다**는 걸 기억해 두자.
:::

## `python` 을 쳤을 때 무엇이 실행되는가

여기가 초심자가 가장 오래 헤매는 지점이다. 원리는 단순하다.

**셸은 `PATH` 환경 변수에 나열된 디렉터리를 앞에서부터 순서대로 뒤져, `python` 이라는 이름의 실행 파일을 처음 찾은 순간 멈춘다.**

그래서 지금 어느 것이 잡히는지 항상 확인할 수 있다.

```bash
# Windows PowerShell
(Get-Command python).Source
Get-Command python -All      # 후보 전부, 우선순위 순

# macOS / Linux
which python
which -a python              # 후보 전부
```

::: danger 시스템에 파이썬이 여러 개 깔리는 흔한 경로
한 대의 PC에 이런 것들이 동시에 존재할 수 있다.

- OS가 기본 탑재한 파이썬 (리눅스/macOS)
- python.org 설치 프로그램으로 깐 것
- Microsoft Store에서 깐 것 (Windows)
- Anaconda / Miniconda
- uv가 관리하는 것
- 프로젝트별 가상환경 안의 것

`pip install` 했는데 `import` 가 안 되는 사고의 99%는 **pip이 설치한 파이썬과 코드를 실행한 파이썬이 서로 다른 것**이다. 위 명령으로 실체를 확인하는 습관을 들여라.
:::

### Windows: py 런처

Windows에는 `py` 라는 런처가 함께 깔린다. `python` 대신 `py` 를 쓰면 버전을 명시적으로 고를 수 있다.

```bash
py -0            # 설치된 파이썬 목록
py -3.12         # 3.12로 실행
py -3.14 script.py
```

::: warn Windows의 가짜 python.exe
Windows 10부터 `python` 을 치면 Microsoft Store가 열리는 경우가 있다. `C:\Users\<사용자>\AppData\Local\Microsoft\WindowsApps\python.exe` 라는 **앱 실행 별칭(app execution alias)** 이 PATH 앞쪽에 있어서다.

`설정 → 앱 → 고급 앱 설정 → 앱 실행 별칭` 에서 python.exe / python3.exe 항목을 끄면 사라진다. 이 책의 방식(uv)을 따르면 애초에 마주칠 일이 거의 없다.
:::

## 버전 전환의 올바른 방법

여기서 사고방식을 바꿔야 한다.

::: tip 전역 파이썬을 바꾸지 마라
초심자는 "지금 3.12를 써야 하니 시스템 기본 파이썬을 3.12로 바꾼다"고 생각한다. 이건 **프로젝트가 두 개 이상 되는 순간 무너진다**. 프로젝트 A는 3.12, 프로젝트 B는 3.14가 필요하면 매번 전역 설정을 오가야 하고, 언젠가 반드시 잘못된 상태에서 실행하게 된다.

올바른 모델은 **"파이썬 버전은 프로젝트의 속성이다"** 이다. 프로젝트 폴더에 들어가면 그 프로젝트의 파이썬이 자동으로 쓰이고, 나오면 원래대로 돌아온다. 전역 기본값은 신경 쓸 필요조차 없어진다.
:::

uv에서는 이렇게 표현한다.

```bash
uv init --python 3.12 myproject   # 이 프로젝트는 3.12를 쓴다
cd myproject
uv run python --version           # Python 3.12.x
```

`--python` 은 `pyproject.toml` 의 `requires-python` 과 `.python-version` 파일에 기록된다. 이후 이 폴더 안에서 `uv run` 하면 항상 3.12가 쓰인다. 다른 폴더에는 영향이 없다. 이게 다음 절([0.3 uv](#/uv))의 핵심 주제다.

## 설치 확인

```bash
uv run --python 3.14 python -c "import sys; print(sys.version)"
```

```text nolines
3.14.0 (main, Oct  7 2025, 00:00:00) [MSC v.1943 64 bit (AMD64)]
```

인터프리터의 실체가 궁금하면 파이썬에게 직접 물어보면 된다. 이건 앞으로 디버깅할 때 계속 쓸 도구다.

```pyrepl
>>> import sys
>>> sys.executable          # 지금 이 코드를 실행 중인 인터프리터의 경로
'C:\\Users\\USER\\.local\\share\\uv\\python\\cpython-3.14.0\\python.exe'
>>> sys.version_info        # 버전 비교에 쓰는 이름 있는 튜플
sys.version_info(major=3, minor=14, micro=0, releaselevel='final', serial=0)
>>> sys.version_info >= (3, 12)
True
>>> sys.prefix              # 이 인터프리터의 설치 루트 (가상환경이면 그 경로)
```

::: cote 코딩테스트 포인트
채점 서버의 파이썬 버전은 **당신이 고를 수 없다**. 백준은 여러 버전을 제공하지만, 기업 시험은 대개 하나로 고정이고 3.9~3.11인 경우가 흔하다.

그래서 시험용 코드에서는 최신 문법을 피하는 게 안전하다. 특히 조심할 것:

| 문법 | 필요 버전 | 시험장 대안 |
| --- | --- | --- |
| `match` 문 | 3.10+ | `if/elif` |
| `list[int]` (내장 제네릭) | 3.9+ | `from typing import List` |
| `int | None` (X 표기) | 3.10+ | `Optional[int]` |
| `tomllib` | 3.11+ | 쓸 일 없음 |
| `itertools.batched` | 3.12+ | 직접 슬라이싱 |

애초에 **시험장에서 타입 힌트는 쓰지 마라.** 점수에 도움이 안 되고 시간만 쓴다. 자세한 건 [8.1 코딩테스트 전략](#/cote-strategy)에서.
:::

## 요약

- 우리가 쓰는 파이썬은 **CPython**이다. C 확장 생태계 전체가 여기 묶여 있다.
- **uv** 하나로 인터프리터 설치·버전 관리·패키지·가상환경을 모두 처리한다.
- `python` 이 무엇을 가리키는지는 **PATH 탐색 순서**가 정한다. 헷갈리면 `which -a python` / `Get-Command python -All` 로 확인하라.
- **파이썬 버전은 전역 설정이 아니라 프로젝트의 속성이다.** 이 사고 전환이 앞으로의 모든 환경 문제를 예방한다.
- 최신 버전이 항상 답은 아니다. ROS와 프로덕션은 그쪽이 정한 버전을 따른다.

::: quiz 연습문제
1. 터미널에서 `pip install requests` 를 실행한 뒤 `python -c "import requests"` 가 `ModuleNotFoundError` 를 냈다. 원인으로 가능한 시나리오를 두 가지 이상 말하고, 각각을 어떤 명령으로 확인할지 적어라.
2. `sys.executable` 과 `sys.prefix` 는 각각 무엇을 알려주는가? 가상환경 안에서 실행하면 이 둘이 어떻게 달라지는가? (직접 확인해 보라 — 다음 절에서 가상환경을 만든다.)
3. 팀 동료가 "내 컴퓨터에선 되는데?" 라고 한다. 이 절의 내용만으로 확인해 볼 것 세 가지를 제시하라.
:::

**다음 절**: [0.3 uv로 프로젝트·가상환경·의존성 관리](#/uv) — 프로젝트를 만들고, 격리하고, 재현 가능하게 만드는 법.
