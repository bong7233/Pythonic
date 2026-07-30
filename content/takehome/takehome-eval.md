# 12.1 과제형 문제가 진짜 평가하는 것

::: lead
알고리즘 시험은 채점이 자동이다. 통과 아니면 실패고, 코드가 어떻게 생겼는지는 아무도 안 본다. 과제형은 정반대다. **사람이 당신의 저장소를 열어서 읽는다.** 그 사람은 "이 문제를 풀 수 있는가"를 이미 서류에서 판단했고, 지금은 다른 것을 본다 — **이 사람이 짠 코드를 내가 6개월 뒤에 고칠 수 있는가.** 이 절은 그 사람이 실제로 무엇을 어떤 순서로 보는지, 그리고 당신이 그 순서에 맞춰 시간을 어떻게 나눠 써야 하는지를 다룬다.
:::

## 같은 과제, 두 개의 제출물

과제는 이렇다. 이 절과 이어지는 절들에서 계속 쓸 예제다.

> **단일 엘리베이터 호출 처리기**
>
> 1. 건물은 1층부터 N층까지다. 엘리베이터는 한 대다.
> 2. 층에서 호출이 들어오고, 차 안에서 목적 층 요청이 들어온다.
> 3. 엘리베이터는 진행 방향을 유지한 채, 그 방향에 남은 요청을 층 순서대로 처리한다. 그 방향에 요청이 없으면 방향을 뒤집는다.
> 4. 정원(기본 10명)을 넘는 탑승은 거부한다.
> 5. 점검 모드에서는 새 호출을 받지 않고, 남은 요청을 마친 뒤 1층으로 내려가 멈춘다.
> 6. 실제 모터 제어 장치 없이 테스트할 수 있어야 한다.
>
> 제한 시간 4시간. 언어는 파이썬. 제출은 저장소 링크.

두 사람이 제출했다.

**A.** 클래스 9개, 추상 베이스 클래스 3개, 전략 패턴, 이벤트 버스. 디렉터리가 5단계다. 요구사항 1~3은 훌륭하게 구현돼 있다. 4·5는 손대다 말았고 테스트는 한 개다. README에는 `# Elevator Challenge` 한 줄.

**B.** 소스 파일 셋, 테스트 파일 둘. 클래스 하나와 함수 두 개가 전부다. 요구사항 1~5가 다 동작하고, 6은 남겨 둔 뒤 **왜 못 했는지와 어떻게 할 계획이었는지**를 README에 세 줄로 적었다. 테스트 8개가 0.01초에 통과한다.

평가자는 B를 고른다. A가 더 많이 알고 더 오래 일한 것이 눈에 보이는데도 그렇다. **왜 그런지를 설명하는 것이 이 절 전체다.**

## 평가자는 순서대로 떨어뜨린다

평가는 항목별 점수 합산이 아니다. **관문이다.** 앞 관문에서 걸리면 뒤는 아예 안 본다.

| 관문 | 질문 | 걸리면 |
| --- | --- | --- |
| 0 | 5분 안에 뭘 만들었는지 파악되는가 | 나머지를 읽을 의욕이 사라진다 |
| 1 | 내 머신에서 **실행되는가** | 여기서 끝. 코드는 안 읽힌다 |
| 2 | 요구사항을 만족하는가 | 문제를 안 읽은 사람으로 분류된다 |
| 3 | 읽히는가 | 같이 일하기 힘든 사람이 된다 |
| 4 | 테스트가 있는가 | "돌려는 봤나?" |
| 5 | 확장 가능한가 | 여기서만 가점이 붙는다 |

이 순서가 중요한 이유는 **시간 배분이 여기서 나오기 때문**이다. 관문 5(확장성)에 4시간 중 3시간을 쓰고 관문 1(실행)에서 걸리는 것이 A가 한 일이다. **관문은 건너뛸 수 없다.** 아래쪽 관문에 아무리 공을 들여도 위쪽에서 걸리면 그 공은 읽히지 않는다.

::: note 이 파트가 Part VI·Part II와 다루는 각도
[6.1 pytest](#/pytest)는 pytest를 **도구로서** 가르친다. `assert` 를 어떻게 쓰고 fixture가 무엇인지는 거기 있다. 여기서는 그 도구를 **평가 대상으로서** 본다 — 무엇을 테스트하고 무엇을 테스트하지 않을지의 판단이다. 마찬가지로 [2.4 Protocol](#/protocol-typing)은 타입 시스템 이야기이고, [12.4](#/boundaries-di)에서는 같은 `Protocol` 을 **경계를 끊는 설계 도구로** 쓴다. 문법을 다시 설명하지 않으니, 막히면 링크를 따라가라.
:::

### 관문 0 — 첫 5분에 보이는 것

평가자가 저장소를 열고 처음 하는 일은 셋이다. **README를 연다. 파일 트리를 훑는다. 테스트를 돌린다.** 코드는 그다음이다.

그러니 트리 자체가 첫인상이다. A의 트리는 이렇게 생겼다.

```text nolines
elevator-challenge/
├── src/
│   └── elevator/
│       ├── domain/
│       │   ├── entities/
│       │   │   ├── car.py
│       │   │   └── request.py
│       │   ├── value_objects/
│       │   │   └── floor.py
│       │   └── services/
│       │       └── dispatch_service.py
│       ├── application/
│       │   ├── use_cases/
│       │   │   └── handle_call.py
│       │   └── dto/
│       │       └── call_dto.py
│       ├── infrastructure/
│       │   ├── repositories/
│       │   └── adapters/
│       └── interfaces/
│           └── cli.py
├── docs/
│   └── architecture.md
├── tests/
│   └── unit/
│       └── domain/
│           └── test_car.py          <- 테스트는 이것 하나뿐이다
└── README.md
```

이 트리를 보는 사람의 머릿속에 뜨는 질문은 "이 사람 설계를 잘하는군"이 아니다. **"정원 검사 로직이 어디 있지?"** 다. 그리고 그걸 찾는 데 30초가 걸리면, 그 30초가 평가다.

B의 트리다.

```text nolines
elevator-challenge/
├── README.md                        <- 무엇을/어떻게 실행/어떤 결정/한계
├── pyproject.toml                   <- 실행·테스트 방법이 여기 박혀 있다
├── elevator/
│   ├── __init__.py
│   ├── rules.py                     <- 순수한 이동 규칙. 상태도 장치도 없다
│   └── car.py                       <- 상태를 들고 규칙을 부른다
└── tests/
    ├── test_rules.py
    └── test_car.py
```

파일 이름만 보고 **어디에 무엇이 있는지 짐작이 된다.** 4시간짜리 과제에서 이것 이상은 필요 없다. 디렉터리 구조 자체는 [12.7](#/project-structure)에서 더 다루지만, 판단 기준은 하나다 — **디렉터리 하나가 파일 하나만 담고 있으면 그 디렉터리는 없는 게 낫다.**

## 실행되는가 — 가장 흔한 탈락 사유

관문 1이 가장 많이 사람을 떨어뜨린다. 이유가 어이없다. **당신 머신에서는 되기 때문이다.**

위의 B 구조를 그대로 만들고, 테스트 8개를 짜고, 로컬에서 확인했다고 하자. 당신은 `python -m pytest` 로 돌렸다. 평가자는 `pytest` 라고 친다. 결과가 다르다.

```bash
$ python -m pytest -q
........                                                                 [100%]
8 passed in 0.01s
```

```bash
$ pytest -q
==================================== ERRORS ====================================
______________________ ERROR collecting tests/test_car.py ______________________
ImportError while importing test module '.../tests/test_car.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
...                                                            <- 중간 생략
tests/test_car.py:3: in <module>
    from elevator.car import Elevator
E   ModuleNotFoundError: No module named 'elevator'
_____________________ ERROR collecting tests/test_rules.py _____________________
...                                                            <- 같은 내용
=========================== short test summary info ============================
ERROR tests/test_car.py
ERROR tests/test_rules.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
2 errors in 0.12s
```

(pytest 9.1.1 / Python 3.14.0rc2 기준 실제 출력. 경로와 스택 일부만 줄였다.)

::: danger `python -m pytest` 는 되고 `pytest` 는 안 된다
`python -m 모듈` 은 **현재 디렉터리를 `sys.path` 맨 앞에 넣는다.** 그래서 프로젝트 루트에서 실행하면 `elevator` 패키지가 그냥 보인다. 반면 `pytest` 실행 파일을 직접 부르면 그런 삽입이 없다. pytest는 테스트 파일에서 위로 올라가며 `__init__.py` 가 없는 첫 디렉터리(`tests/`)를 `sys.path` 에 넣을 뿐이라, 그 위의 프로젝트 루트는 들어가지 않는다.

**이건 당신이 절대 스스로 발견하지 못하는 종류의 사고다.** 당신은 한 가지 방법으로만 돌리기 때문이다. 그리고 평가자는 수집 단계에서 죽은 화면을 보고 "테스트를 안 돌려 보고 제출했군"이라고 결론 내린다. 실제로는 8개 다 통과하는데도 그렇다.
:::

고치는 방법은 둘이다. **둘 다 맞고, 고르는 기준이 있다.**

```toml title="pyproject.toml — 안 1"
[project]
name = "elevator"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```bash
# 안 2 — 프로젝트 루트에 빈 conftest.py 를 하나 둔다. 그게 전부다.
touch conftest.py
```

| | 안 1 `pythonpath` | 안 2 빈 `conftest.py` |
| --- | --- | --- |
| 어떻게 동작하나 | pytest가 지정된 경로를 `sys.path` 에 넣는다 | pytest가 `conftest.py` 가 있는 디렉터리를 넣는다 |
| 의도가 드러나나 | 파일을 열면 바로 보인다 | **빈 파일이라 아무 설명이 없다** |
| 다른 설정과 같이 두나 | 테스트 경로·마커를 한곳에 모을 수 있다 | 못 한다 |
| 언제 쓰나 | 기본. 과제 제출에는 이쪽 | 이미 fixture 때문에 `conftest.py` 가 있을 때 |

**과제형이면 안 1을 써라.** 이유는 동작이 아니라 **평가자가 파일 하나를 열어 실행 방법을 알 수 있다**는 데 있다. 빈 파일은 "왜 여기 있는지"를 설명해 주지 않는다. `pyproject.toml` 자체는 [6.5 패키징](#/packaging)에 있다.

주의할 것 하나. `pyproject.toml` **을 두는 것만으로는 안 고쳐진다.** `[tool.pytest.ini_options]` 에 `pythonpath` 를 실제로 적어야 한다. `testpaths` 만 적고 `pythonpath` 를 빼면 위와 똑같이 `ModuleNotFoundError` 가 난다 — 직접 확인했다.

::: tip 제출 직전 5분 — clean 복사본 검사
로컬에서 되는 것은 증거가 아니다. **당신 프로젝트 폴더 밖에서, 새로 복제한 사본으로** 돌려라.

```bash
git clone . /tmp/check && cd /tmp/check
pytest -q                     # 평가자가 실제로 치는 명령
python -m pytest -q           # 다른 방법으로도 되는지
```

`git clone` 을 쓰는 이유는 **커밋되지 않은 파일이 자동으로 빠지기 때문**이다. `.gitignore` 에 실수로 소스 파일을 넣었거나, `git add` 를 빼먹은 파일이 있으면 여기서 잡힌다. 복사(`cp -r`)로는 안 잡힌다.
:::

## 요구사항을 만족하는가 — 역추적 표

관문 2에서 사람들이 지는 이유는 능력이 아니라 **기억력**이다. 4시간 동안 코드를 짜다 보면 요구사항 4번을 잊는다. 잊었다는 사실조차 모른다.

해결책은 단순하다. **요구사항 문장을 그대로 표로 옮기고, 각 줄에 코드 위치와 테스트 이름을 채운다.** 이 표를 README에 그대로 붙인다.

| 요구사항 | 구현 | 테스트 |
| --- | --- | --- |
| 1. 1~N층, 엘리베이터 한 대 | `Elevator.__init__` | `test_calling_a_floor_that_does_not_exist_is_an_error` |
| 2. 층 호출과 차내 요청을 받는다 | `Elevator.call` | 직접 테스트 없음. 3·5의 테스트가 간접적으로 쓴다 |
| 3. 진행 방향 유지, 없으면 반전 | `rules.next_stop` | `test_going_up_serves_the_lowest_request_above_first`<br>`test_reverses_when_nothing_remains_ahead` |
| 4. 정원 초과 탑승 거부 | `Elevator.board` | `test_boarding_is_capped_by_capacity` |
| 5. 점검 모드 | `Elevator.enter_maintenance`, `step` | `test_maintenance_mode_rejects_new_calls`<br>`test_maintenance_mode_returns_to_the_ground_floor` |
| 6. 장치 없이 테스트 | **미구현** | — |

이 표가 하는 일은 셋이다.

1. **빈칸이 곧 할 일 목록이다.** 표를 먼저 만들면 뭘 안 했는지 4시간 내내 보인다.
2. **평가자의 채점 시간을 5분에서 1분으로 줄인다.** 평가자도 같은 표를 만들면서 채점한다. 당신이 대신 만들어 준 것이다.
3. **테스트 이름이 요구사항 문장과 일대일로 붙는다.** 테스트를 명세로 쓰는 습관이 여기서 시작한다([12.6](#/test-strategy)).

::: warn 이 표에 거짓말을 쓰면 최악이 된다
"6. 미구현"이라고 쓰인 줄은 감점이 **작다.** 그러나 6번 칸에 그럴듯한 함수 이름을 적어 놨는데 열어 보니 빈 껍데기면, 그 순간 표의 나머지 다섯 줄도 전부 못 믿을 것이 된다. **정직한 미구현 한 줄이, 부풀린 구현 다섯 줄보다 싸다.**

요구사항 문장은 **당신 말로 요약하지 말고 원문을 그대로 옮겨라.** 요약하는 순간 당신이 이해한 범위로 요구사항이 줄어든다. 요구사항을 모델로 바꾸는 절차 자체는 [12.2](#/requirements-to-model)에서 다룬다.
:::

::: tip 요구사항에 없는 것을 마주치면
엘리베이터가 4층에 정지해 있고 2층과 6층 호출이 동시에 들어왔다. 거리가 같다. 어디로 가는가? **요구사항에 없다.** 이럴 때 할 일은 셋 중 하나다.

1. 아무거나 고르고 넘어간다 → 평가자가 "이 경우를 생각 안 했군"으로 읽는다.
2. 메일로 물어본다 → 4시간짜리 과제에서는 답이 안 온다.
3. **고르고, 고른 이유를 코드 주석과 README에 한 줄 남긴다.** ← 이게 정답이다.

3번은 "모호함을 발견했고, 결정했고, 기록했다"를 동시에 증명한다. 이 셋은 실무에서 매일 하는 일이고, 과제형이 진짜 보려는 것이다.
:::

## 읽히는가

관문 3이 이 절에서 가장 설득하기 어려운 부분이다. **동작이 같기 때문**이다.

아래 두 함수는 똑같이 요구사항 3(방향 유지, 없으면 반전)을 구현한 것이다. 먼저 나쁜 쪽이다.

```python title="읽히지 않는 쪽"
def next_stop(current, heading, pending):
    if len(pending) == 0:
        return None
    else:
        if current in pending:
            return current
        else:
            a = []
            b = []
            for f in pending:
                if f > current:
                    a.append(f)
                else:
                    if f < current:
                        b.append(f)
            if heading == 1 and len(a) > 0:
                return min(a)
            elif heading == -1 and len(b) > 0:
                return max(b)
            elif heading == 0:
                if len(a) == 0:
                    return max(b)
                elif len(b) == 0:
                    return min(a)
                else:
                    if current - max(b) < min(a) - current:
                        return max(b)
                    else:
                        return min(a)
            else:
                if heading == 1:
                    return max(b)
                else:
                    return min(a)
```

```python title="elevator/rules.py"
"""엘리베이터의 이동 규칙. 시간도 장치도 여기 없다 — 그래서 테스트가 빠르다."""


def next_stop(current: int, heading: int, pending: set[int]) -> int | None:
    """다음에 멈출 층. 요청이 없으면 None.

    heading 은 +1(위) / -1(아래) / 0(정지)이다.
    """
    if not pending:
        return None
    if current in pending:
        return current

    above = {f for f in pending if f > current}
    below = {f for f in pending if f < current}

    if heading > 0 and above:
        return min(above)
    if heading < 0 and below:
        return max(below)
    if heading == 0:
        return _nearest(current, above, below)
    # 진행 방향에 남은 요청이 없다 -> 방향을 뒤집는다
    return max(below) if heading > 0 else min(above)


def _nearest(current: int, above: set[int], below: set[int]) -> int:
    """정지 상태에서 고르는 규칙. 거리가 같으면 위쪽을 먼저 간다(요구사항 밖의 결정)."""
    up = min(above) if above else None
    down = max(below) if below else None
    if up is None:
        return down
    if down is None:
        return up
    return down if (current - down) < (up - current) else up
```

**두 함수의 결과는 같다.** 6층 건물의 모든 요청 조합(공집합 포함) × 모든 현재 층 × 방향 셋(`-1`, `0`, `+1`) = 1,152가지를 전수 대조했고 불일치는 0이다. 테스트를 어느 쪽에 붙여도 다 통과한다.

그런데 평가는 갈린다. 갈리는 지점을 정확히 짚으면 이렇다.

- **이름이 없다.** `a`, `b` 는 "위쪽 요청"과 "아래쪽 요청"이다. 그 이름을 읽는 사람이 머릿속에서 복원해야 한다. `above`/`below` 는 복원할 게 없다.
- **`else` 안에 본문이 들어 있다.** 조기 반환(`return None`)으로 끝낼 수 있는 것을 들여쓰기 한 단으로 만들었다. 들여쓰기 깊이는 **읽는 사람이 동시에 기억해야 하는 조건의 수**다.
- **결정이 기록되지 않았다.** "거리가 같으면 위쪽"은 요구사항에 없는 결정인데, 나쁜 쪽에는 그 사실이 어디에도 없다. 좋은 쪽은 함수 이름과 docstring이 말한다.
- **경계가 섞여 있다.** 좋은 쪽은 "정지 상태의 선택"만 `_nearest` 로 떼어 냈다. 그 규칙이 바뀌면 고칠 자리가 한 곳이다.
- **약속한 입력 범위를 벗어나면 갈라진다.** `heading` 에 `-5` 가 들어오면 나쁜 쪽은 `heading == -1` 검사에 안 걸려 **위로 가는 것처럼** 답하고, 아래쪽 요청만 남은 상태에서는 `ValueError: min() iterable argument is empty` 로 터진다. 좋은 쪽은 부호만 보므로 의도가 유지된다. 즉 **위의 "완전히 같다"는 `heading ∈ {-1, 0, 1}` 안에서만 참이다.** 동등성 검사를 할 때 어떤 범위를 가정했는지 밝히지 않으면 그 검사는 절반만 한 것이다.

::: warn "읽히는가"는 취향 문제가 아니다
포매터가 다 정리해 주는 것(줄 길이, 따옴표, import 순서)은 평가 항목이 아니다. `ruff format` 한 번이면 끝난다([0.4](#/tooling)). 평가되는 것은 포매터가 절대 못 고치는 것 — **이름, 함수의 크기, 조건의 깊이, 그리고 결정이 기록됐는가**다. 제출 전에 포매터와 린터는 당연히 돌리되, 그것으로 관문 3을 통과했다고 착각하지 마라.
:::

동작을 확인하는 것은 이렇게 짧다.

```pyrepl
>>> from elevator.rules import next_stop
>>> next_stop(current=3, heading=1, pending={5, 7, 2})
5
>>> next_stop(current=8, heading=1, pending={2, 5})
5
>>> next_stop(current=4, heading=0, pending={2, 6})
6
>>> next_stop(current=4, heading=1, pending=set()) is None
True
```

두 번째 줄이 요구사항 3의 후반부다. 8층에서 위로 가는 중인데 위쪽에 아무것도 없으니 방향을 뒤집어 5층으로 간다. **이 네 줄이 그대로 테스트 네 개가 된다.**

## 테스트가 있는가

관문 4에서 평가자가 보는 것은 **개수도 커버리지도 아니다.** 두 가지다 — 돌아가는가, 그리고 **이름만 읽어서 명세가 보이는가.**

```bash
$ pytest -v --no-header
============================= test session starts ==============================
collecting ... collected 8 items

tests/test_car.py::test_boarding_is_capped_by_capacity PASSED            [ 12%]
tests/test_car.py::test_maintenance_mode_rejects_new_calls PASSED        [ 25%]
tests/test_car.py::test_maintenance_mode_returns_to_the_ground_floor PASSED [ 37%]
tests/test_car.py::test_calling_a_floor_that_does_not_exist_is_an_error PASSED [ 50%]
tests/test_rules.py::test_going_up_serves_the_lowest_request_above_first PASSED [ 62%]
tests/test_rules.py::test_reverses_when_nothing_remains_ahead PASSED     [ 75%]
tests/test_rules.py::test_idle_car_breaks_a_tie_by_going_up PASSED       [ 87%]
tests/test_rules.py::test_no_request_means_no_stop PASSED                [100%]

============================== 8 passed in 0.02s ===============================
```

이 출력만 읽어도 **이 프로그램이 무엇을 보장하는지 알 수 있다.** 정원은 막힌다, 점검 모드는 호출을 거부한다, 점검 모드는 1층으로 돌아간다, 없는 층은 오류다, 위로 갈 때는 위쪽부터, 앞이 비면 뒤집는다, 동률이면 위쪽, 요청이 없으면 멈추지 않는다. **여덟 줄이 요구사항 문장 그대로다.**

테스트 하나를 옮겨 온다. 구조는 **given-when-then** 이고, `assert` 가 하나일 필요는 없다([12.6](#/test-strategy)).

```python title="tests/test_car.py"
def test_boarding_is_capped_by_capacity():
    car = Elevator(top_floor=10, capacity=3)
    assert car.board(2) == 2
    assert car.board(5) == 1  # 남은 자리만큼만
    assert car.riders == 3
```

::: perf 테스트가 느린 것은 대개 설계 문제다
같은 테스트 8개를, `Elevator.step()` 이 실제 모터 드라이버를 부르도록 바꿔서 다시 돌렸다(한 층 이동에 0.3초 걸리는 장치를 가정).

| 무엇 | `pytest -q` 보고 시간 |
| --- | --- |
| 규칙만 테스트 (장치 호출 없음) | 0.01 ~ 0.02 초 |
| `step()` 이 장치를 직접 호출 | 1.81 ~ 1.82 초 |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

테스트 8개에서 이미 100배 안팎이고, 이 차이는 **장치를 부르는 횟수에 정비례해서 커진다.** 여기서 중요한 건 초가 아니다. **느린 테스트는 안 돌리게 되고, 안 돌리는 테스트는 없는 테스트다.** 요구사항 6("장치 없이 테스트")은 편의 요청이 아니라 설계 요청이다 — 어떻게 끊는지는 [12.4](#/boundaries-di)에서 한다.
:::

무엇을 테스트할지의 판단은 [12.6](#/test-strategy)의 몫이지만, 관문 4를 통과하는 최소선만 못 박아 둔다.

- **요구사항 하나당 최소 하나.** 위의 역추적 표에서 테스트 칸이 빈 줄이 없어야 한다.
- **실패 경로를 하나는 넣어라.** 없는 층 호출, 정원 초과 — "잘 되는 경우"만 있는 테스트 묶음은 안 짠 것과 비슷하게 읽힌다.
- **`len(list)` 같은 파이썬 기능은 테스트하지 마라.** 도메인 규칙만 테스트한다.

## 확장 가능한가 — 그리고 그 함정

관문 5는 **가점 항목**이다. 앞의 넷을 통과한 다음에만 의미가 있다. 그런데 과제형에서 가장 많이 나오는 실수가 여기 있다. **확장성을 미리 만들어 두는 것.**

요구사항 3을 "전략 패턴"으로 열어 두면 이렇게 된다.

```python title="dispatch.py — 아무도 요구하지 않은 확장점"
from abc import ABC, abstractmethod


class DispatchStrategy(ABC):
    @abstractmethod
    def choose(self, current: int, heading: int, pending: set[int]) -> int | None: ...


class NearestFirstStrategy(DispatchStrategy):
    def choose(self, current, heading, pending):
        if not pending:
            return None
        return min(pending, key=lambda f: abs(f - current))


class DirectionalStrategy(DispatchStrategy):
    def choose(self, current, heading, pending):
        ...                      # rules.next_stop 과 같은 내용


class StrategyFactory:
    _registry: dict[str, type[DispatchStrategy]] = {
        "nearest": NearestFirstStrategy,
        "directional": DirectionalStrategy,
    }

    @classmethod
    def register(cls, name: str, strategy: type[DispatchStrategy]) -> None:
        cls._registry[name] = strategy

    @classmethod
    def create(cls, name: str) -> DispatchStrategy:
        try:
            return cls._registry[name]()
        except KeyError:
            raise ValueError(f"알 수 없는 전략: {name}") from None
```

두 안을 나란히 놓는다.

| | 함수 하나 (`rules.next_stop`) | 전략 + 팩토리 |
| --- | --- | --- |
| 줄 수(빈 줄·주석 제외) | 27 | 38 |
| 읽는 사람이 붙잡을 개념 | **함수 2개**(하나는 비공개 헬퍼) | 추상 클래스 1 + 구현 2 + 팩토리 1 |
| 새 정책 추가 비용 | 함수를 고친다 | 클래스를 추가하고 등록한다 |
| 정책이 **하나뿐**일 때 | 딱 맞다 | 쓰이지 않는 분기를 유지해야 한다 |
| 요구사항에 "여러 정책 비교" 가 **있을 때** | 조건문이 불어난다 | **이쪽이 맞다** |

줄 수는 27 대 38로 극적이지 않다. **문제는 줄이 아니다.** 오른쪽을 읽으려면 클래스 넷의 관계를 머리에 올려야 하고, 그러고 나서야 실제 규칙 한 줄에 도달한다. 그 대가로 얻는 것은 **요구사항에 없는 유연성**이다.

::: danger 요구사항에 없는 확장점은 감점이다
"나중에 바뀔 수 있으니까"는 이유가 아니다. 과제 문서에 적힌 것만이 요구사항이다. 아래 신호가 하나라도 보이면 되돌려라.

- 추상 클래스의 **구현이 하나뿐**이다.
- 인터페이스를 정의했는데 **주입하는 곳이 한 군데**다.
- 설정 파일에 **바꾼 적 없는 값**이 들어 있다.
- `**kwargs` 로 받아서 아무 데도 안 쓴다.
- 디렉터리 안에 파일이 **하나**다.

각각이 평가자에게 보내는 신호는 같다. **"이 사람은 필요를 확인하기 전에 구조부터 만든다."** 실무에서 이건 위험 신호다. 없는 요구를 미리 만들지 않는 원칙(YAGNI)은 [12.2](#/requirements-to-model)에서 절차로 다룬다.
:::

::: tip 그러면 확장성은 어디서 보여 주나
**분리로 보여 준다. 추상화로 보여 주지 마라.**

`rules.py` 에는 상태도 장치도 시간도 없다. 순수 함수 둘뿐이다. `car.py` 는 상태를 들고 그 함수를 부른다. 이 분리 하나로 "정책을 갈아 끼울 수 있다"가 이미 증명된다 — `next_stop` 을 다른 함수로 바꾸면 끝이기 때문이다. **추상 클래스를 만들지 않고도 같은 유연성을 얻었고, 읽는 비용은 0이다.**

그리고 확장 계획은 **코드가 아니라 README에 쓴다.** "정책이 여러 개로 늘어나면 `next_stop` 을 `Callable` 로 주입받게 바꾸면 된다" 한 줄이, 안 쓰는 팩토리 40줄보다 높게 평가된다. 실제로 주입이 필요한 경우는 [12.4](#/boundaries-di)에 있다.
:::

## 시간을 어디에 쓰는가

4시간 과제 기준이다. 시간이 다르면 비율만 유지해라.

| 구간 | 하는 일 | 끝났을 때의 상태 |
| --- | --- | --- |
| 0:00 ~ 0:30 | 요구사항을 표로 쪼갠다. 모호한 곳에 표시 | **코드 한 줄도 안 짰다.** 정상이다 |
| 0:30 ~ 1:00 | 프로젝트 뼈대 + 가장 위험한 규칙 하나를 테스트와 함께 | `pytest` 가 돌아간다 |
| 1:00 ~ 2:30 | 요구사항 순서대로 구현 | 표의 구현 칸이 찬다 |
| 2:30 ~ 3:15 | 실패 경로·경계값 테스트 | 표의 테스트 칸이 찬다 |
| 3:15 ~ 3:45 | README. 결정과 한계를 적는다 | 제출 가능 상태 |
| 3:45 ~ 4:00 | clean 복사본에서 실행 확인 | 끝 |

여기서 지켜야 할 규칙 셋이다.

1. **0:30까지 코드를 안 짜는 것을 견뎌라.** 요구사항을 반쯤 이해한 채 짠 코드는 나중에 통째로 버린다. 백지 앞의 절차 자체는 [11.7](#/blank-page-routine)에 있다.
2. **1:00에 `pytest` 가 돌아가야 한다.** 이때 테스트는 하나여도 된다. 중요한 건 **실행 경로가 뚫렸다는 것**이다. 마지막 30분에 처음 `pytest` 를 치면 관문 1에서 죽는다.
3. **마지막 30분에는 새 기능을 시작하지 마라.** 절대적이다. 이유는 바로 다음 절 제목에 있다.

::: warn 시간이 없다는 것을 3:00에 알게 된다
사람은 남은 일을 항상 과소평가한다. **2:30 지점에서 한 번 멈추고, 표에서 아직 빈 줄을 세라.** 남은 시간을 남은 줄 수로 나눠 보고, 안 되면 그때 **무엇을 버릴지 고른다.** 3:50에 강제로 고르는 것보다 2:30에 스스로 고르는 편이 언제나 낫다.

버릴 것을 고르는 기준은 명확하다. **요구사항 번호가 앞선 것부터 지킨다.** 과제를 낸 사람이 중요한 순서대로 적었을 확률이 높다.
:::

## 완벽한 미완성보다 정직한 TODO

이 절의 마지막 주장이자 가장 중요한 주장이다. **미구현은 감점이 작고, 숨긴 미구현은 감점이 크다.**

요구사항 4(정원)를 시간에 쫓겨 다 못 했다고 하자. 세 가지 제출 방식이 있다.

```python
# ❌ 조용히 빠뜨린다
def board(self, count: int = 1) -> int:
    self.riders += count      # 정원 검사가 없다
    return count
```

```python
# ❌ 반쯤 하고 아무 말도 안 한다
def board(self, count: int = 1) -> int:
    if self.riders >= self.capacity:
        return 0              # 9명 있는데 5명 타면? 14명이 된다
    self.riders += count
    return count
```

```python
# ✅ 되는 데까지 하고, 못 한 것을 코드가 말한다
def board(self, count: int = 1) -> int:
    """탑승시킨 인원 수를 반환한다. 정원을 넘는 만큼은 거부한다.

    한계: 초과분은 그냥 버린다. 대기열로 남겨 다음 정차 때 태우는 동작은
    요구사항에 명시되지 않아 구현하지 않았다(README '알려진 한계' 참고).
    """
    allowed = max(0, min(count, self.capacity - self.riders))
    self.riders += allowed
    return allowed
```

첫 번째는 **평가자가 버그로 읽는다.** 두 번째가 가장 나쁘다 — 검사를 했으니 신경 쓴 티는 나는데 결과가 틀린다. **"조심했는데 틀렸다"는 "안 했다"보다 낮게 평가된다.** 세 번째는 요구사항을 지키면서, 정하지 않은 부분을 명시적으로 남겼다.

아예 손도 못 댄 요구사항이라면 이렇게 남긴다.

```python
def return_to_ground(self) -> None:
    """점검 모드에서 1층으로 복귀한다(요구사항 5의 후반부)."""
    raise NotImplementedError(
        "요구사항 5의 '1층 복귀'는 시간 안에 구현하지 못했다. README 참고."
    )
```

::: danger 함수가 조용히 None 을 반환하게 두지 마라
`pass` 로 비워 둔 함수는 **아무 일도 안 하고 성공한 것처럼 보인다.** 호출한 쪽은 정상 동작으로 받아들이고, 버그는 세 단계 떨어진 곳에서 터진다. 미구현은 **호출 즉시 시끄럽게 터져야** 한다.

```python
def return_to_ground(self): pass                    # ❌ 조용히 성공한다
def return_to_ground(self): raise NotImplementedError("아직")  # ✅ 즉시 터진다
```

실패를 어떻게 표현할지는 [12.5](#/error-design)의 주제이고, 예외 계층 자체는 [1.16](#/exceptions)에 있다. 여기서 기억할 것은 하나다 — **모르는 것을 조용히 넘기는 코드가 과제형에서 가장 크게 깎인다.**
:::

그리고 README에 세 줄을 적는다. README 전체 구성은 [12.8](#/readme-submit)에서 다루지만, **한계 항목만은 지금 외워라.**

```text nolines
## 알려진 한계
- 요구사항 6(장치 없이 테스트): step() 이 아직 모터 드라이버를 직접 부른다.
  Protocol 로 경계를 정의하고 생성자로 주입하면 되지만, 시간 안에 못 했다.
  현재는 rules.py 만 장치 없이 테스트된다.
- 동시 호출(엘리베이터 여러 대)은 요구사항 밖이라 고려하지 않았다.
```

이 몇 줄이 하는 일은 **"못 했다"의 고백이 아니다.** 셋 다 증명한다 — 무엇을 못 했는지 안다, 어떻게 하면 되는지 안다, 요구사항의 경계를 안다. **앞의 A 제출물에는 이 세 줄이 없다.** 클래스 아홉 개가 대신할 수 없는 것이다.

## 요약

- 과제형 평가는 점수 합산이 아니라 **관문**이다. **실행 → 요구사항 → 가독성 → 테스트 → 확장성** 순이고, 앞에서 걸리면 뒤는 읽히지도 않는다.
- 가장 흔한 탈락은 실력이 아니라 **환경 차이**다. `python -m pytest` 는 되고 `pytest` 는 안 되는 사고가 대표적이다. **제출 전에 clean 복사본에서 평가자가 칠 명령 그대로 돌려라.**
- **요구사항 원문 → 코드 위치 → 테스트 이름**의 역추적 표를 만들어라. 빈칸이 할 일 목록이고, 그대로 README가 된다. 그 표에 거짓말을 쓰면 나머지 줄까지 못 믿을 것이 된다.
- 가독성은 취향이 아니다. 포매터가 고치는 것(줄 길이·따옴표)은 평가 대상이 아니고, **이름·함수 크기·조건 깊이·기록된 결정**이 평가 대상이다.
- 테스트는 개수가 아니라 **이름만 읽어서 명세가 보이는가**다. 그리고 **느린 테스트는 안 돌리게 되고, 안 돌리는 테스트는 없는 테스트다.**
- **요구사항에 없는 확장점은 감점이다.** 확장성은 추상 클래스가 아니라 **분리**로 증명하고, 확장 계획은 코드가 아니라 README에 적는다.
- **완벽하지만 미완성인 제출보다, 동작하고 정직한 TODO가 이긴다.** 조용한 미구현이 가장 크게 깎인다.

::: quiz 실습 과제 — 읽지 말고 손을 움직여라
전부 **직접 만들고 실행**해라. 정답이 하나인 문제가 아니다. 판단과 근거를 함께 남겨라.

**1. 탈락을 재현해라 (30분)**
`elevator/rules.py`, `elevator/car.py`, `tests/test_rules.py` 로 이루어진 최소 프로젝트를 만들어라. `tests/` 에는 `__init__.py` 를 두지 마라. 그다음:

- `python -m pytest -q` 와 `pytest -q` 를 **둘 다** 돌려 결과가 다른 것을 눈으로 확인해라.
- `pyproject.toml` 의 `pythonpath` 로 고쳐라. 그리고 되돌린 뒤 빈 `conftest.py` 로도 고쳐라.
- **어느 쪽을 제출하겠는가.** 이유를 한 문장으로 적어라. 이유가 "둘 다 되니까"면 다시 생각해라.

**2. 역추적 표를 채워라 (20분)**
본문의 요구사항 6개에 대해 표를 만들어라. 칸은 `요구사항 원문 | 구현 위치 | 테스트 이름 | 상태`. 당신이 1번에서 만든 코드 기준으로 **정직하게** 채워라. 빈칸이 세 개 이상이면 잘 만든 것이다 — 그게 남은 할 일이다.

**3. 읽히게 고치고, 같음을 증명해라 (40분)**
본문의 "읽히지 않는 쪽" 함수를 그대로 옮겨 적고, 당신 방식으로 리팩터링해라. 그리고 **두 함수가 정말 같은지 전수 비교하는 스크립트를 짜라.**

```python
# 힌트: 6층 건물이면 요청 조합 2**6 가지 × 현재 층 6 × 방향 3 = 1152 가지
# itertools.combinations 로 pending 집합을 전부 만들어라
```

불일치가 0으로 나와야 한다. **0이 아니면 리팩터링이 아니라 재작성을 한 것이다.**

**4. 오버엔지니어링을 되돌려라 (20분)**
본문의 `DispatchStrategy` + `StrategyFactory` 코드를 요구사항에 맞게 줄여라. 목표는 **함수 하나**다. 줄인 뒤, 다음 두 가지를 적어라.

- 이 구조를 **줄이면 안 되는** 요구사항 문장은 어떻게 생겼겠는가. 실제로 한 문장 써 봐라.
- 팩토리의 `register()` 는 누가 부르고 있었는가. 아무도 안 부르고 있었다면 그건 무슨 신호인가.

**5. 30분 남았다 (25분)**
요구사항 5(점검 모드)를 **절반만** 구현한 상태라고 하자. 새 호출 거부는 되지만 1층 복귀는 안 된다. 남은 시간은 30분이다. 아래 셋 중 하나를 골라 **코드로** 표현하고, 고른 이유를 두 문장으로 적어라.

- (a) 30분을 써서 1층 복귀를 마저 구현한다.
- (b) 지금 상태를 그대로 두고 README '알려진 한계'에 적는다.
- (c) `enter_maintenance()` 를 `NotImplementedError` 로 바꿔 요구사항 5를 통째로 미구현 처리한다.

**힌트:** (c)를 고른 사람은 거의 없겠지만, **(c)가 맞는 조건**이 존재한다. 그 조건이 무엇인지 생각해 보고 적어라.

**6. 확장 과제.** 1번의 프로젝트를 `git clone . /tmp/check` 로 복제해서 `pytest -q` 를 돌려라. 통과했다면, 소스 파일 하나를 일부러 `.gitignore` 에 넣고 다시 해 봐라. **복사(`cp -r`)로는 이 사고가 왜 안 잡히는지** 한 문장으로 적어라.
:::

**다음 절**: [12.2 요구사항에서 모델로](#/requirements-to-model) — 요구사항 문장에서 명사와 동사를 뽑아 클래스와 메서드로 바꾸는 절차를, 이 엘리베이터 요구사항 위에서 그대로 시연한다.
