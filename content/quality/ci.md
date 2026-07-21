# 6.6 CI/CD와 pre-commit

::: lead
[0.4 도구 세팅](#/tooling)에서 pre-commit을 로컬에 설치했다. 그런데 "내 컴퓨터에 설치했다"와 "팀 전체가 항상 지킨다"는 다른 이야기다. 어떤 팀원은 `pre-commit install`을 까먹고, 어떤 팀원은 `--no-verify`로 훅을 건너뛴다. 이 절은 그 구멍을 서버 쪽에서 막는 방법 — GitHub Actions로 모든 커밋과 PR을 자동 검증하는 CI(Continuous Integration) — 을 다룬다. 로컬 훅과 서버 검사를 이중으로 걸어야 진짜로 안전하다.
:::

## 로컬 훅만으로는 부족한 이유

[0.4절](#/tooling)에서 만든 `.pre-commit-config.yaml`은 `git commit` 시점에 ruff를 돌려 준다. 이게 완벽해 보이지만 구멍이 세 개 있다.

1. **설치를 깜빡할 수 있다.** `pre-commit install`은 그 저장소를 새로 클론한 사람마다 한 번씩 실행해야 한다. 안 하면 훅이 조용히 동작하지 않는다.
2. **우회할 수 있다.** `git commit --no-verify`는 모든 훅을 건너뛴다. 급할 때 누구나 한 번쯤 쓴다.
3. **커밋 이후의 문제를 못 잡는다.** 로컬 훅은 각자의 컴퓨터에서, 각자의 파이썬 버전으로 돈다. "내 컴퓨터에서는 되는데" 문제 — 다른 파이썬 버전에서는 실패하는 코드 — 를 잡지 못한다.

CI는 이 세 구멍을 전부 막는다. **깃허브 서버가** PR이 열릴 때마다 강제로 검사를 돌린다. 로컬 설정과 무관하고, 우회할 수 없고(브랜치 보호 규칙과 엮으면), 여러 환경에서 동시에 검증한다.

::: note CI/CD 용어 정리
**CI**(Continuous Integration, 지속적 통합) — 코드가 합쳐질 때마다 자동으로 빌드·테스트한다. 이 절에서 다루는 것.
**CD**(Continuous Deployment/Delivery, 지속적 배포) — 검증을 통과한 코드를 자동으로 배포한다. 패키지 배포는 [6.5 패키징](#/packaging)에서 다룬 내용과 이어지고, 컨테이너 배포는 [6.7 도커](#/docker)에서 이어진다.

이 둘은 하나의 파이프라인으로 묶이는 경우가 많아서 보통 "CI/CD"라고 붙여 부르지만, 이 절은 CI에 집중한다.
:::

## GitHub Actions 워크플로의 구조

GitHub Actions는 `.github/workflows/` 아래의 YAML 파일로 정의한다. 뼈대는 이렇다.

```yaml title=".github/workflows/ci.yml"
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv sync
      - name: Test
        run: uv run pytest -q
```

네 계층으로 읽는다.

- **`on`** — 언제 돈다. 여기서는 `main`에 푸시할 때, 그리고 모든 PR에서.
- **`jobs`** — 병렬로 도는 작업 단위. 하나의 워크플로 안에 여러 `job`을 둘 수 있고, 기본적으로 서로 독립된 가상 머신에서 동시에 실행된다.
- **`runs-on`** — 어떤 운영체제의 가상 머신을 쓸지. `ubuntu-latest`가 가장 빠르고 싸다.
- **`steps`** — job 안에서 순서대로 실행되는 명령들. `uses`는 남이 만든 재사용 가능한 액션을, `run`은 셸 명령을 직접 쓴다.

`actions/checkout@v4`는 저장소 코드를 가상 머신에 내려받는 첫 단계로 거의 항상 필요하다. `astral-sh/setup-uv@v4`는 uv를 설치해 준다 — [0.3 uv](#/uv)에서 로컬에 깔았던 것과 같은 도구를 CI 환경에도 준비하는 것이다.

::: warn YAML의 `on:` 은 함정이 있다
방금 쓴 워크플로를 표준 YAML 파서로 그냥 읽으면 무슨 일이 벌어지는지 직접 확인해 보자.

```pyrepl
>>> import yaml
>>> data = yaml.safe_load(open(".github/workflows/ci.yml", encoding="utf-8"))
>>> list(data.keys())
['name', True, 'jobs']
>>> type(list(data.keys())[1])
<class 'bool'>
```

`on` 이라는 키가 **불리언 `True`로 파싱됐다.** YAML 1.1 명세에서는 `on`, `off`, `yes`, `no`, `y`, `n` 같은 단어가 전부 불리언 리터럴이기 때문이다. `pyyaml`의 `safe_load`는 이 규칙을 그대로 따른다.

실전에서 이게 왜 중요한가? **GitHub Actions 자체는 이 문제가 없다** — GitHub는 자체 YAML 스키마로 워크플로를 해석하고 `on`을 문자열 키로 취급하도록 고정해 뒀다. 하지만 **당신이 파이썬 스크립트로 워크플로 YAML을 파싱해서 검증하거나 생성하는 도구를 만든다면** `pyyaml`의 기본 로더가 이 함정에 그대로 걸린다. 값을 딕셔너리 키로 조회하려다 `KeyError: 'on'`을 만나고 원인을 못 찾아 헤매는 경우가 실제로 있다. 안전하게 다루려면 `ruamel.yaml`을 쓰거나, `yaml.safe_load`로 읽은 뒤 `True` 키를 명시적으로 다시 매핑해야 한다.
:::

이 워크플로 파일이 실제로 유효한 YAML인지는 커밋하기 전에 로컬에서 확인할 수 있다.

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"
```

에러 없이 끝나면 문법은 맞다. 다만 이건 **YAML 문법 검증**일 뿐, GitHub Actions만의 스키마(어떤 키가 허용되는지, `uses`에 어떤 형식이 필요한지)까지 검증하지는 않는다. 그건 실제로 GitHub에 푸시해서 워크플로가 도는 것으로만 확인된다 — 이 환경은 깃허브 서버에 접속할 수 없으므로, 이 절의 워크플로 파일은 **문법 검증까지만** 이 환경에서 직접 확인했고, 실제 트리거·실행 로그는 확인하지 못했다.

## 매트릭스 테스트: 여러 파이썬 버전을 한 번에

라이브러리를 만든다면 "내 파이썬 3.14에서만 되는 코드"를 배포하면 안 된다. 사용자는 3.11을 쓸 수도, 3.13을 쓸 수도 있다. **매트릭스**(matrix) 전략은 같은 job을 여러 조합으로 병렬 실행한다.

```yaml title=".github/workflows/ci.yml — 매트릭스 추가"
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --python ${{ matrix.python-version }} --all-groups

      - name: Lint
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Test
        run: uv run pytest -q
```

이 YAML도 실제로 문법을 검증했다.

```pyrepl
>>> import yaml
>>> data = yaml.safe_load(open(".github/workflows/ci.yml", encoding="utf-8"))
>>> data["jobs"]["test"]["strategy"]["matrix"]["python-version"]
['3.11', '3.12', '3.13', '3.14']
```

`matrix.python-version`에 나열한 네 개 값마다 **독립된 가상 머신 하나씩, 총 네 개의 job**이 동시에 뜬다. `${{ matrix.python-version }}`은 각 job 안에서 그 job에 배정된 값으로 치환된다.

::: tip fail-fast: false 를 꺼 두는 이유
기본값(`fail-fast: true`)은 매트릭스 중 **하나라도 실패하면 나머지를 즉시 취소한다.** 빠르게 실패를 알고 싶을 때는 좋지만, "3.11에서는 실패하고 3.14에서는 성공한다" 같은 **버전별 차이를 전부 보고 싶을 때는 방해가 된다.** `false`로 끄면 네 버전 모두 끝까지 돌리고 전체 결과를 한 번에 본다.
:::

::: cote Python 버전 차이가 실제로 문제 되는 지점
매트릭스 테스트가 왜 필요한지는 문법 하나만 봐도 안다. `match` 문([1.8 제어 흐름](#/control-flow))은 3.10부터, PEP 695 제네릭 문법(`def f[T](...)`, [2.3절](#/pep695))은 3.12부터다. 3.11을 지원한다고 선언한 라이브러리에서 `def f[T](x: T) -> T:` 를 썼다면, 3.11 환경에서는 `SyntaxError`로 즉시 죽는다. 매트릭스가 없으면 이 버그는 **사용자의 컴퓨터에서** 발견된다.
:::

## 캐싱으로 CI 속도 높이기

매트릭스가 네 배 늘어나면 의존성 설치도 네 번 반복된다. `uv sync`가 매번 패키지를 새로 내려받으면 그만큼 CI가 느려지고, 무료 플랜의 실행 시간 한도도 빨리 닳는다.

`astral-sh/setup-uv` 액션은 `enable-cache: true` 하나로 uv의 다운로드 캐시를 GitHub Actions의 캐시 저장소에 올렸다 내렸다 해 준다. `cache-dependency-glob`에 지정한 파일(`uv.lock`)의 해시가 캐시 키가 된다 — **락파일이 안 바뀌면 캐시를 그대로 재사용**하고, 바뀌면 새로 받는다.

::: perf 캐시가 실제로 아끼는 것
이 환경은 GitHub 서버에 접속할 수 없어 실제 CI 실행 시간을 측정하지는 못했다. 다만 로컬에서 같은 의존성을 캐시 있는 상태와 없는 상태로 설치해 비교하면 캐싱의 효과가 어느 정도인지 감을 잡을 수 있다.

측정할 때 주의할 점이 하나 있다. `.venv`가 이미 lock과 일치하는 상태에서 `uv sync`를 다시 부르면, uv는 "이미 설치돼 있다"고 보고 아무것도 새로 받지 않은 채 그대로 끝난다 — 이건 캐시 효과가 아니라 **설치 스킵**이다. 캐시 유무를 공정하게 비교하려면 CI가 매번 그러듯 `.venv`를 통째로 지우고 처음부터 새로 만들게 해야 한다.

```pyrepl
>>> import subprocess, time, shutil, os
>>> def fresh_venv():
...     if os.path.exists(".venv"): shutil.rmtree(".venv")
...
>>> subprocess.run(["uv", "cache", "clean"])
>>> fresh_venv()
>>> t0 = time.perf_counter(); subprocess.run(["uv", "sync"]); round(time.perf_counter() - t0, 2)
1.16   # 캐시 없이: venv를 새로 만들고 패키지를 전부 내려받음
>>> fresh_venv()
>>> t0 = time.perf_counter(); subprocess.run(["uv", "sync"]); round(time.perf_counter() - t0, 2)
0.5    # 캐시 있음: venv는 새로 만들지만 wheel은 캐시에서 그대로 복사
```

(Python 3.14.5 / Windows, ruff·pytest·pre-commit 세 개짜리 작은 프로젝트 기준 실측. `.venv`를 매번 지우고 새로 만드는 조건에서 캐시 없이 1.16초, 캐시로 0.5초 — 약 2.3배 차이다. 반대로 `.venv`를 지우지 않고 그대로 둔 채 같은 코드를 돌리면 첫 `uv sync`가 "이미 일치함"만 확인하고 0.15초에 끝나 버려 캐시 효과를 전혀 보여주지 못하니 주의하라. 절대 초는 네트워크 상태·패키지 개수마다 다르고, 의존성이 많은 실제 프로젝트에서는 이 격차가 훨씬 커진다. CI 환경에서는 매번 새 가상 머신에서 시작하므로 이 문서의 "venv를 지우고 새로 만드는" 조건과 정확히 같고, 여기에 매트릭스 개수(4)가 곱해지므로 체감 효과는 더 크다.)
:::

## 브랜치 보호 규칙: 실패하면 머지를 막는다

CI가 돌기만 하고 결과를 아무도 안 보면 의미가 없다. **브랜치 보호 규칙**(branch protection rule)은 "이 검사를 통과하지 못하면 `main`에 머지 자체를 못 하게" 강제한다.

GitHub 저장소의 *Settings → Branches → Add branch protection rule*에서 `main`을 대상으로 다음을 켠다.

- **Require a pull request before merging** — `main`에 직접 push를 막고, 반드시 PR을 거치게 한다.
- **Require status checks to pass before merging** — 앞서 만든 워크플로의 job 이름(`test`)을 필수 검사로 지정한다. 이 job이 실패하거나 아직 실행 중이면 **머지 버튼 자체가 비활성화**된다.
- **Require branches to be up to date before merging** — PR 브랜치가 최신 `main`을 반영하지 않았으면 머지를 막는다. `main`에서 다른 변경이 먼저 들어가 충돌 가능성이 생긴 상태로 머지되는 걸 방지한다.

이 조합이 로컬 pre-commit 훅과 다른 결정적인 지점은 하나다. **로컬 훅은 개발자가 우회할 수 있지만, 브랜치 보호 규칙은 저장소 관리자만 바꿀 수 있다.** `--no-verify`로 커밋해서 로컬 검사를 건너뛰어도, PR을 열면 서버의 CI가 다시 돈다. 여기서 막히면 관리자 권한 없이는 머지할 방법이 없다.

::: warn 이 환경에서 실제로 확인하지 못한 것
브랜치 보호 규칙은 GitHub 저장소 설정이고, 실제로 PR을 열어 머지가 막히는 것을 보려면 GitHub 서버와 웹 UI가 필요하다. 이 환경은 로컬 git 저장소와 로컬 명령 실행만 가능해서, **이 규칙이 실제로 머지를 막는 동작 자체는 이 세션에서 실행해 확인하지 못했다.** 위 설정 항목과 동작 설명은 GitHub의 공개된 기능 명세를 정확히 옮긴 것이지, 이 환경에서 재현한 실측이 아니다. 반면 pre-commit 훅이 커밋을 막는 것은 바로 아래에서 실제로 재현한다.
:::

## pre-commit을 실제로 로컬 git 저장소에 걸어 본다

CI는 이 환경에서 트리거할 수 없지만, pre-commit은 **로컬 git 저장소만 있으면** 실제로 동작을 재현할 수 있다. 임시 디렉터리에 작은 프로젝트를 만들어 확인했다.

```toml title="pyproject.toml"
[project]
name = "ci-demo"
version = "0.1.0"
requires-python = ">=3.10"

[dependency-groups]
dev = ["ruff>=0.14", "pytest>=8.0", "pre-commit>=4.0"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "C4", "RUF"]
```

`.pre-commit-config.yaml`은 [0.4절](#/tooling)의 것을 그대로 썼다. 그리고 일부러 [1.1 객체, 이름, 참조](#/objects-names)에서 다룬 그 함정을 담은 파일을 커밋해 봤다.

```python title="bad.py"
import os


def f(items=[]):
    items.append(1)
    return items
```

`git init` 후 `uv run pre-commit install`로 훅을 등록하고, `git add -A && git commit -m "add bad.py"`를 실행한 결과다. **아래는 실제로 이 환경에서 나온 출력 그대로다.**

```text nolines
ruff check...............................................................Failed
- hook id: ruff-check
- exit code: 1

B006 Do not use mutable data structures for argument defaults
 --> bad.py:1:13
  |
1 | def f(items=[]):
  |             ^^
2 |     items.append(1)
3 |     return items
  |
help: Replace with `None`; initialize within function

Found 1 error.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).

ruff format..............................................................Passed
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
```

**커밋 자체가 실패했다.** `ruff-check` 훅이 0이 아닌 종료 코드를 반환했고, git은 그걸 보고 커밋을 만들지 않았다. `import os`(안 쓰는 import)는 `--fix` 옵션 덕분에 이전 실행에서 자동으로 지워졌지만, `B006`(가변 기본값)은 자동으로 고칠 수 없는 종류의 문제라 사람이 직접 고쳐야 한다.

코드를 [1.1절](#/objects-names)에서 배운 방식대로 고쳤다.

```python title="bad.py — 수정"
def f(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

다시 커밋하면 이렇게 통과한다.

```text nolines
ruff check...............................................................Passed
ruff format..............................................................Passed
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
[master (root-commit) 664fa1c] fix bad.py
 4 files changed, 394 insertions(+)
```

이게 이 절 전체가 말하려는 것의 축소판이다. **로컬 훅이 커밋을, CI가 머지를 막는다.** 하나는 개발자의 컴퓨터에서, 다른 하나는 서버에서 — 같은 검사를 두 번 걸어서 어느 한쪽이 뚫려도 다른 쪽이 잡는다.

::: deep 왜 pre-commit은 커밋을 "막을 수" 있는가
git은 커밋이 만들어지기 직전에 실행되는 여러 훅 지점을 제공한다. `pre-commit` 프레임워크는 그중 `.git/hooks/pre-commit` 파일 자리에 자기 자신을 등록해 둔다. `git commit`을 실행하면 git이 이 스크립트를 먼저 실행하고, **0이 아닌 종료 코드를 반환하면 커밋 생성을 중단한다.** 이건 pre-commit 라이브러리의 마법이 아니라 git 자체의 오래된 메커니즘이다. `pre-commit install`이 하는 일은 이 스크립트 자리에 pre-commit 실행기를 심어 두는 것뿐이다.

그래서 `.git/hooks/`는 **저장소를 클론해도 따라오지 않는다** — `.git` 디렉터리 자체가 복제되지 않기 때문이다(정확히는, hooks 디렉터리는 기본적으로 git이 추적하는 대상이 아니다). 팀원 각자가 클론 후 `pre-commit install`을 실행해야 하는 이유가 여기 있다. 이 한계를 CI가 보완한다 — 훅 설치를 깜빡한 사람의 커밋도, 서버의 CI에서는 반드시 걸린다.
:::

## 요약

- **로컬 pre-commit 훅과 서버 CI는 같은 검사를 이중으로 건다.** 하나는 우회 가능하고(`--no-verify`), 다른 하나는 우회 불가능하다.
- GitHub Actions 워크플로는 `on`(언제) → `jobs`(무엇을, 어디서) → `steps`(어떻게) 구조다.
- `yaml.safe_load`로 워크플로의 **문법**은 검증할 수 있지만, GitHub Actions 고유 스키마 검증과 실제 실행은 GitHub 서버에서만 확인된다.
- YAML 1.1의 `on`/`off`/`yes`/`no`는 불리언으로 파싱된다 — 직접 YAML을 다루는 도구를 짤 때 함정이 된다.
- **매트릭스**는 여러 파이썬 버전(또는 OS)에서 같은 job을 병렬로 돌려, "내 버전에서만 되는" 코드를 잡는다.
- `setup-uv`의 캐시 기능은 락파일이 그대로면 의존성 재다운로드를 건너뛰어 CI 시간을 줄인다.
- **브랜치 보호 규칙**은 지정한 상태 검사가 실패하면 `main`으로의 머지를 관리자 권한 없이는 못 하게 막는다.
- Docker 이미지 안에서 이 모든 것을 재현 가능하게 굳히는 이야기는 [6.7 도커](#/docker)로 이어진다.

::: quiz 연습문제
1. 이 절의 `.pre-commit-config.yaml`과 가변 기본값이 있는 `bad.py`를 그대로 로컬 git 저장소에 만들어라. `pre-commit install` 후 커밋을 시도해 실패하는 것을 직접 확인하고, 코드를 고쳐 통과시켜라.
2. `yaml.safe_load`로 이 절의 워크플로 YAML을 읽어서 `matrix.python-version` 리스트의 길이를 출력하는 스크립트를 짜라. 그리고 `on` 키가 어떤 타입으로 파싱되는지도 확인하라.
3. `fail-fast: true`(기본값)와 `fail-fast: false`의 차이를 설명하라. 매트릭스에 파이썬 버전 4개가 있고 3.11에서만 실패한다면, 각 설정에서 최종적으로 몇 개의 job 결과를 보게 되는가?
4. 브랜치 보호 규칙에서 "Require branches to be up to date before merging"을 켜지 않으면 어떤 상황이 생길 수 있는지, `main`에 동시에 들어오는 두 PR을 예로 들어 설명하라.
5. `.git/hooks/pre-commit`이 왜 저장소를 클론해도 함께 오지 않는지, 그리고 이게 CI가 반드시 필요한 이유와 어떻게 연결되는지 서술하라.
:::

**다음 절**: [6.7 도커와 재현 가능한 환경](#/docker) — pre-commit과 CI로 코드 품질을 지켰다면, 이제 실행 환경 자체를 고정하는 법.
