# 0.4 린터·포매터·타입체커 세팅

::: lead
사람은 공백 개수를 세는 데 시간을 쓰면 안 되고, 오타를 찾는 데 집중력을 쓰면 안 된다. 그건 기계가 훨씬 잘한다. 이 절에서 만드는 설정은 앞으로 이 책의 모든 코드에 적용되며, 실무에서 그대로 쓸 수 있다.
:::

## 세 가지 도구, 세 가지 다른 일

용어부터 정리하자. 자주 뒤섞여 쓰인다.

| 도구 | 하는 일 | 대답하는 질문 |
| --- | --- | --- |
| **포매터** (formatter) | 코드 모양을 정해진 규칙대로 다시 씀 | "줄바꿈과 따옴표를 어떻게?" |
| **린터** (linter) | 의심스러운 패턴을 찾아냄 | "이거 버그 아니야?" |
| **타입체커** (type checker) | 타입이 맞는지 정적으로 검증 | "이 함수에 str을 넘겨도 돼?" |

셋은 겹치지 않는다. 포매터는 코드의 **의미를 절대 바꾸지 않고** 모양만 바꾼다. 린터는 모양이 아니라 **논리적 냄새**를 잡는다. 타입체커는 **실행하지 않고** 타입 오류를 찾는다.

2026년 기준 선택은 단순하다.

- **ruff** — 포매터 + 린터. Rust로 만들어서 압도적으로 빠르다. 옛날의 `black` + `flake8` + `isort` + `pyupgrade` 를 하나로 대체한다.
- **pyright** (또는 mypy) — 타입체커.

::: hist ruff 이전
과거 표준 조합은 이랬다: `black`(포매터) + `flake8`(린터) + `isort`(import 정렬) + `pyupgrade`(문법 현대화) + `pydocstyle`(독스트링) …. 각각 설정 파일이 따로 있고, 서로 규칙이 충돌해서 "black과 flake8이 싸우지 않게 하는 설정"이 관용구처럼 돌아다녔다.

ruff는 이 도구들의 규칙을 하나의 Rust 바이너리로 재구현했다. 큰 코드베이스에서 flake8이 수십 초 걸리던 검사를 수십 밀리초에 끝낸다. **속도가 충분히 빨라지면 사용 방식이 바뀐다** — 저장할 때마다 전체 검사를 돌려도 아무렇지 않다.
:::

## 설치

```bash
uv add --dev ruff
uv add --dev pyright
```

`--dev` 인 이유: 이 도구들은 **개발할 때만** 필요하다. 내 라이브러리를 쓰는 사람이 ruff를 받을 이유는 없다.

## ruff 설정

`pyproject.toml` 에 이어서 쓴다. 설정 파일을 따로 만들지 않아도 된다.

```toml title="pyproject.toml"
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = [
    "E", "W",    # pycodestyle — 기본 스타일
    "F",         # pyflakes — 미사용 변수, 정의 안 된 이름 등 진짜 버그
    "I",         # isort — import 정렬
    "UP",        # pyupgrade — 옛 문법을 현대 문법으로
    "B",         # flake8-bugbear — 흔한 버그 패턴
    "SIM",       # flake8-simplify — 불필요하게 복잡한 코드
    "C4",        # flake8-comprehensions — 컴프리헨션 개선
    "RUF",       # ruff 고유 규칙
]
ignore = [
    "E501",      # 줄 길이 — 포매터가 알아서 한다
]

[tool.ruff.format]
quote-style = "double"
```

::: note 왜 E501을 끄는가
`E501`("줄이 너무 김")은 린터의 규칙이다. 그런데 포매터가 이미 `line-length = 100` 에 맞춰 줄을 나눈다. 포매터가 도저히 못 나누는 줄(긴 URL이 든 문자열, 긴 주석)만 남는데, 그건 사람이 어쩔 수 없는 것들이다. 그래서 경고해 봐야 소음만 된다.

**린터 규칙을 끄는 건 패배가 아니다.** 소음이 많으면 사람은 전부 무시하기 시작하고, 그러면 진짜 경고도 놓친다. 규칙은 **지킬 것만** 켜라.
:::

### 쓰는 법

```bash
uv run ruff format .          # 포맷 적용
uv run ruff format --check .  # 확인만 (CI용)
uv run ruff check .           # 린트
uv run ruff check --fix .     # 자동으로 고칠 수 있는 건 고침
uv run ruff check --watch .   # 파일 저장할 때마다 재검사
```

### 린터가 실제로 잡는 것들

린터를 "스타일 잔소리꾼"으로 생각하면 오해다. 아래는 전부 **진짜 버그**다.

```python title="ruff가 잡아내는 실제 버그들"
import os                      # F401: 안 쓰는 import


def f(items=[]):               # B006: 가변 기본값 — 이 책 최대의 함정
    items.append(1)
    return items


def g(x):
    for i in range(3):
        pass
    return i                   # F821 계열: 루프 변수 누출 (x는 안 쓰임 → ARG001)


def h(a, b):
    if a == None:              # E711: is None 을 써야 한다
        return
    if type(b) == int:         # E721: isinstance 를 써야 한다
        return
    result = a + b
    return result              # 그냥 return a + b (RET504)
```

`B006`(가변 기본값) 하나만으로도 ruff를 쓸 이유가 충분하다. 이건 파이썬 초심자가 반드시 한 번 당하는 버그이고, 눈으로는 절대 안 보인다. 왜 그런지는 [1.10 함수](#/functions)에서 자세히 다룬다.

::: tip 규칙 코드를 검색하라
경고가 뜨면 코드(`B006`, `SIM108` …)가 같이 나온다. 그 코드로 검색하면 **왜 그게 문제인지**를 설명한 문서가 나온다. 린터 경고는 잔소리가 아니라 **공짜 교육**이다. 특히 배우는 단계에서는 경고 하나하나가 배울 거리다.

```bash
uv run ruff rule B006     # 터미널에서 바로 설명 보기
```
:::

### 경고를 무시해야 할 때

가끔은 린터가 틀린다. 그럴 때만 억제하되, **이유를 적어라.**

```python
import numpy as np  # noqa: F401  # 사이드이펙트 등록 목적으로 import함
```

::: warn 파일 전체에 noqa를 걸지 마라
`# ruff: noqa` 를 파일 맨 위에 박으면 그 파일은 영원히 검사되지 않는다. 나중에 들어온 진짜 버그도 조용히 지나간다. **한 줄에, 규칙 코드를 명시해서** 억제하는 게 원칙이다.
:::

## 타입체커: pyright

```toml title="pyproject.toml"
[tool.pyright]
include = ["src"]
pythonVersion = "3.14"
typeCheckingMode = "standard"     # off | basic | standard | strict
reportMissingImports = "warning"
```

```bash
uv run pyright
```

::: warn 처음부터 strict로 가지 마라
`typeCheckingMode = "strict"` 를 켜면 기존 코드에서 수백 개 오류가 쏟아진다. 그러면 사람은 도구를 꺼 버린다.

권장 경로: **`basic` → `standard` → 새 코드만 `strict`**. 파이썬의 타입 시스템은 **점진적 타이핑**(gradual typing)이라는 철학 위에 있다 — 전부 다는 아니어도, 붙인 만큼 이득이 있다. [2.8 mypy와 pyright 실전](#/typecheckers)에서 도입 전략을 제대로 다룬다.
:::

::: note pyright vs mypy
**pyright**(마이크로소프트, TypeScript로 작성)는 빠르고 VS Code의 파이썬 확장(Pylance)에 내장돼 있다. 에디터에서 실시간으로 돈다.

**mypy**(파이썬 재단 쪽, 파이썬으로 작성)는 더 오래됐고 생태계 호환이 넓다. 큰 기업 코드베이스에서 여전히 표준이다.

둘은 미묘하게 다른 판정을 내리기도 한다. **둘 다 켤 필요는 없다.** 에디터를 VS Code로 쓴다면 pyright가 자연스럽고, 팀이 mypy를 쓰면 mypy에 맞춘다.
:::

## 에디터 연결

도구를 명령줄에서만 쓰면 반쯤 손해다. 진짜 가치는 **타이핑하는 동안 즉시 피드백**에서 나온다.

### VS Code

확장 두 개를 깐다: **Ruff** (`charliermarsh.ruff`), **Python** (`ms-python.python`, Pylance 포함).

프로젝트에 `.vscode/settings.json` 을 만든다.

```json title=".vscode/settings.json"
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.analysis.typeCheckingMode": "standard",
  "python.defaultInterpreterPath": ".venv/bin/python"
}
```

::: danger Windows에서 인터프리터 경로
Windows의 가상환경 파이썬은 `.venv/bin/python` 이 아니라 **`.venv/Scripts/python.exe`** 다. 위 설정을 그대로 쓰면 VS Code가 인터프리터를 못 찾는다.

가장 확실한 방법은 경로를 적는 대신 <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> → *Python: Select Interpreter* → 프로젝트의 `.venv` 를 고르는 것이다. 그러면 VS Code가 알아서 올바른 경로를 기록한다.
:::

### 다른 에디터

- **PyCharm** — 내장 검사기가 강력하다. Ruff 플러그인을 추가로 깔면 된다.
- **Neovim / Helix** — `ruff server`(LSP)와 `pyright-langserver` 를 붙인다.

## pre-commit: 커밋 전에 자동으로

에디터 설정은 **내 컴퓨터에만** 적용된다. 팀원이 설정을 안 했다면? 그래서 커밋 시점에 강제하는 장치를 둔다.

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files    # 실수로 데이터셋 커밋 방지
      - id: check-merge-conflict
```

```bash
uv add --dev pre-commit
uv run pre-commit install       # git hook 등록 — 한 번만
uv run pre-commit run --all-files
```

이제 `git commit` 할 때마다 자동으로 돈다. 검사에 걸리면 커밋이 멈춘다.

::: tip check-added-large-files 는 생각보다 중요하다
ML/비전 작업을 하다 보면 실수로 데이터셋이나 모델 가중치(수백 MB)를 커밋한다. **git 히스토리에 한 번 들어간 큰 파일은 지우기가 매우 번거롭다** — 히스토리를 다시 써야 하고, 이미 푸시했다면 협업자 전원이 영향을 받는다. 사전에 막는 게 압도적으로 싸다.
:::

## 전체 설정 파일

지금까지의 모든 것을 합치면 이렇다. 앞으로의 연습 프로젝트에 그대로 쓰면 된다.

```toml title="pyproject.toml — 이 책의 표준 설정"
[project]
name = "pybook-practice"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = ["ruff>=0.14", "pyright>=1.1.400", "pytest>=8.0", "pre-commit>=4.0"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "C4", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]          # 테스트에서 assert 는 정상

[tool.ruff.format]
quote-style = "double"

[tool.pyright]
include = ["src"]
pythonVersion = "3.14"
typeCheckingMode = "standard"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

::: cote 코딩테스트 포인트
**시험장에서는 이 절의 도구를 하나도 쓰지 않는다.** 온라인 저지의 편집기에는 린터가 없고, 있어도 점수와 무관하다.

하지만 **평소 연습할 때는 켜 두는 게 이득**이다. 이유는 하나: `F821`(정의되지 않은 이름), `F841`(값을 넣었는데 안 쓰는 변수) 같은 경고가 **오타로 인한 틀림**을 미리 잡아 준다. 시험장에서 30분 디버깅할 것을 평소에 습관으로 없애 두는 것이다.

반대로 시험장에서 **하지 말아야 할 것**: 변수명을 예쁘게 짓기, 타입 힌트 달기, 함수로 잘게 쪼개기. 점수는 정확성과 시간복잡도로만 매겨진다. ([8.1 코딩테스트 전략](#/cote-strategy))
:::

## 요약

- **포매터·린터·타입체커는 각각 다른 일**을 한다. 모양, 냄새, 타입.
- **ruff** 하나로 포매터와 린터를 끝낸다. 설정은 `pyproject.toml` 안에.
- 린터 경고는 잔소리가 아니라 **공짜 교육**이다. `ruff rule <코드>` 로 이유를 읽어라.
- 규칙은 **지킬 것만** 켠다. 소음이 많으면 전부 무시하게 되고, 그게 최악이다.
- 타입체커는 **낮은 단계부터 점진적으로**. 처음부터 strict는 실패한다.
- 에디터 연결(즉시 피드백) + pre-commit(강제)의 조합이 실전 구성이다.

::: quiz 연습문제
1. 이 절의 `pyproject.toml` 설정을 넣은 프로젝트를 만들고, 위 "ruff가 잡아내는 실제 버그들" 코드를 파일로 저장한 뒤 `ruff check` 를 돌려라. 몇 개의 서로 다른 규칙이 걸리는가? 각각 `ruff rule <코드>` 로 이유를 읽어라.
2. `def f(items=[])` 가 왜 위험한지 지금 설명할 수 있는가? 못 하겠다면 아래 코드를 실행해 보고 결과를 예측한 것과 비교하라.

   ```python
   def f(items=[]):
       items.append(1)
       return items

   print(f())
   print(f())
   print(f())
   ```

3. `ruff format` 은 코드의 의미를 바꾸지 않는다고 했다. 그런데 포매터가 **의미를 바꿀 수 있는** 상황이 하나 있다. 무엇일까? (힌트: 문자열 안, 그리고 `\` 로 줄을 잇는 경우를 생각해 보라.)
:::

**다음 절**: [0.5 REPL, pdb, 주피터](#/repl-debug) — 실행 중인 프로그램 안을 들여다보는 법.
