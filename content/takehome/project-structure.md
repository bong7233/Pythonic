# 12.7 프로젝트 구조 만들기

::: lead
[12.6](#/test-strategy)에서 스무 개 남짓한 테스트를 짰다. 이제 그 파일들을 어디에 둘 것인가. 이 질문은 취향처럼 보이지만 아니다. 평가자가 저장소를 열고 **처음 30초에 보는 것**이 파일 트리이고, 그 트리에서 "이 사람은 자기가 만든 것의 모양을 아는가"가 먼저 읽힌다. 이 절은 `src/` 를 쓸지 말지 같은 유행 논쟁을 다루지 않는다. **파일을 언제 쪼개는가, `__init__.py` 가 실제로 무슨 문제를 푸는가, 그리고 4시간짜리 과제에 맞는 크기는 어디까지인가**를 정한다. 패키징 자체는 [6.5 패키징](#/packaging), import 시스템의 원리는 [1.19 모듈, 패키지, import](#/imports)에 있다. 여기서는 **판단**만 한다.
:::

## 두 개의 제출물

같은 주차장 과제([12.6](#/test-strategy)에서 쓰던 그 과제다)를 두 사람이 냈다.

```text nolines
A                                  B
parking-lot/                       parking-lot/
└── main.py                        ├── README.md
                                   ├── pyproject.toml
                                   ├── src/
                                   │   └── parking/
                                   │       ├── domain/
                                   │       │   ├── entities/
                                   │       │   │   ├── ticket.py
                                   │       │   │   └── lot.py
                                   │       │   ├── value_objects/
                                   │       │   │   └── plate.py
                                   │       │   └── services/
                                   │       │       └── fee_service.py
                                   │       ├── application/
                                   │       │   └── use_cases/
                                   │       │       └── settle.py
                                   │       ├── infrastructure/
                                   │       └── interfaces/
                                   │           └── cli.py
                                   └── tests/
                                       └── unit/
                                           └── domain/
                                               └── test_lot.py
```

둘 다 감점이다. **그런데 이유가 정반대라서, 하나를 고치는 방법으로 다른 하나를 고칠 수 없다.**

A는 요금 계산과 상태 관리와 입출력이 한 파일에 섞여 있다. 평가자가 "요금 상한 규칙이 어디 있냐"고 물으면 스크롤을 해야 한다. 더 나쁜 건 테스트다. 요금표만 검증하고 싶은데 `main.py` 를 import 하는 순간 `input()` 이 걸린 코드까지 딸려 온다.

B는 반대다. 디렉터리가 **열세 개**인데 그중 **파일이 두 개 이상 들어 있는 것은 `entities/` 하나뿐**이다. `infrastructure/` 는 비어 있다. `plate.py` 는 정규식 한 줄이다. 평가자가 요금 상한 규칙을 찾으려면 `domain/services/fee_service.py` 를 열어야 하는데, 그걸 알아내는 데 30초가 걸린다. 그리고 **디렉터리 열세 개를 만든 사람이 테스트 파일을 하나 냈다**는 사실이 마지막에 눈에 들어온다.

이 절은 A와 B 사이 어디에 서야 하는지를 정한다. 결론부터 말하면 **대부분의 과제에서 정답은 A 쪽에 훨씬 가깝다.**

## 한 파일로 끝나는 과제가 실제로 있다

주차장 과제의 도메인 전체 — 예외 다섯 개, 요금 함수, `Ticket`, `ParkingLot` — 를 한 파일에 넣으면 이만큼이다.

```bash
$ wc -l parking.py
110 parking.py
```

빈 줄과 주석을 빼면 80줄이다. **이 규모에서 파일을 쪼갤 이유는 없다.** "파일이 하나면 아마추어처럼 보인다"는 걱정 때문에 디렉터리를 만드는 것은, 읽는 사람에게 아무것도 주지 않으면서 찾는 비용만 올리는 일이다.

::: tip 한 파일로 내도 되는 조건
셋 다 맞으면 `parking.py` 하나로 내라. 부끄러워할 것이 없다.

1. **코드가 150줄 아래다.**
2. **테스트 파일이 하나로 충분하다.** 테스트를 쓰다가 "이건 다른 파일이어야 하는데"가 안 나온다.
3. **외부 시스템이 없다.** 결제 API도, 파일 저장도, 시계도 없다([12.4](#/boundaries-di)).

다만 **패키지 디렉터리는 만들어라.** `parking.py` 하나여도 `parking/__init__.py` + `parking/lot.py` 로 두는 편이 낫다. 나중에 파일이 하나 더 생겼을 때 import 문을 안 고쳐도 되고, `python -m parking` 을 붙일 자리가 생긴다. 비용은 빈 파일 하나다.
:::

## 쪼개는 신호는 줄 수가 아니다

그럼 언제 쪼개는가. **"파일이 길어져서"가 아니다.** 길이는 결과지 원인이 아니다. 실제 신호는 두 개고, 둘 다 코드가 아니라 **당신이 하고 있는 행동**에서 나온다.

### 신호 ① 테스트가 두 무리로 갈린다

이 절에서 실제로 돌리는 스위트는 22개다. 그 22개가 이렇게 갈린다.

| 테스트 | `ParkingLot` 을 만드는가 | 검증 대상 | 수 |
| --- | --- | --- | --- |
| 요금 경계, 일 상한, 도장 할인, 음수 거부 | **안 만든다** | 정수 → 정수 | 13 |
| 만차·중복·미등록 거부, 정산·출차 전이 | 만든다 | 상태 전이 | 9 |

**앞의 13개는 객체를 하나도 안 만든다.** 정수를 넣고 정수를 받는다. 뒤의 9개는 전부 `ParkingLot(capacity=...)` 로 시작한다. 테스트 파일을 쓰다가 `import` 줄이 두 무리로 갈리는 순간이 왔다면, **소스도 이미 두 개다.** 당신은 그걸 테스트를 통해 발견한 것뿐이다.

12.6의 요구사항–테스트 대응표를 여기 다시 옮기지는 않는다. 여기서 중요한 건 개수가 아니라 **`import` 줄이 갈린다는 사실**이다.

### 신호 ② import 화살표가 한 방향으로만 간다

두 번째 신호는 기계로 확인할 수 있다. 각 모듈이 무엇을 import 하는지 뽑아 봐라.

```python title="tools/deps.py — 열한 줄짜리 자가 진단"
import ast
import pathlib

for path in sorted(pathlib.Path("parking").glob("*.py")):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    print(f"{path.name:12} {sorted(names)}")
```

```text nolines
$ python tools/deps.py
__init__.py  ['.errors', '.fees', '.lot']
errors.py    []
fees.py      []
lot.py       ['.errors', '.fees', 'dataclasses']
```

이 네 줄이 설계 문서다. **`errors.py` 와 `fees.py` 의 import 목록이 비어 있다.** 아무것도 의존하지 않는다는 뜻이고, 그래서 아무 데서나 부를 수 있고, 테스트가 가장 싸다. `lot.py` 는 그 둘을 쓴다. 화살표가 한 방향으로만 간다.

```text nolines
   errors.py      fees.py         <- import 가 없다. 표준 라이브러리조차 안 쓴다
       ^             ^
       |             |
       +------+------+
              |
           lot.py                 <- 규칙과 상태. 위의 둘만 안다
              ^
              |
        __main__.py               <- 조립. 여기서만 프로그램이 된다
```

**파일 경계는 이 화살표를 눈에 보이게 만드는 선이다.** 그 이상도 이하도 아니다. 화살표가 양쪽으로 가는 두 덩어리라면 그건 사실 한 파일이었던 것이고, 억지로 나누면 순환 import가 난다(아래에서 실제로 낸다).

::: warn 쪼개면 안 되는 축 세 가지
1. **클래스마다 파일 하나.** 자바 습관이다. 파이썬에서 `Ticket` 과 `ParkingLot` 은 같은 파일에 있어야 한다 — 함께 변하기 때문이다.
2. **레이어 이름으로.** `entities/`, `services/`, `repositories/` 는 **당신 도메인의 단어가 아니다.** 요구사항 문장에 "엔티티"라는 말이 나오는가? 안 나온다. 파일 이름은 요구사항에서 뽑아라([12.2](#/requirements-to-model)).
3. **`utils.py` 로 몰아넣기.** `utils` 는 "어디 둘지 안 정했다"는 뜻이다. 그 안에 함수가 셋을 넘으면 반드시 두 종류 이상이 섞여 있다.

공통점은 **쪼갠 뒤에 화살표가 더 잘 보이지 않는다**는 것이다. 그게 유일한 판정 기준이다.
:::

쪼갠 결과는 이렇게 된다. 파일 다섯 개다.

```text nolines
parking-lot/
├── README.md
├── pyproject.toml
├── parking/
│   ├── __init__.py               <- 공개 API 선언. 열 줄이다
│   ├── errors.py                 <- 도메인 예외. import 가 없다
│   ├── fees.py                   <- 순수 계산. import 가 없다
│   ├── lot.py                    <- 상태와 규칙
│   └── __main__.py               <- python -m parking 데모
└── tests/
    ├── test_fees.py
    └── test_lot.py
```

## `__init__.py` 가 실제로 푸는 문제

여기서 미신 하나를 먼저 깬다. **"`__init__.py` 가 없으면 import 가 안 된다"는 파이썬 3.2까지의 이야기다.** 3.3부터는 그냥 된다.

```text nolines
ns/
├── submit/
│   └── parking/
│       ├── fees.py               <- __init__.py 가 없다
│       └── errors.py
└── elsewhere/
    └── parking/                  <- 무관한 다른 프로젝트의 폴더
        ├── fees.py
        └── legacy.py
```

```pyrepl
>>> import sys
>>> sys.path[:0] = ["submit", "elsewhere"]
>>> import parking, parking.fees, parking.legacy
>>> parking.__file__
>>> parking.fees.__file__
'/.../ns/submit/parking/fees.py'
>>> parking.legacy.audit()
'stub'
```

`import` 는 전부 성공했다. 그리고 **두 가지가 조용히 망가졌다.**

첫째, `parking.__file__` 이 `None` 이다(위 REPL에서 아무것도 출력되지 않은 줄이 그것이다). 이건 진짜 패키지가 아니라 **네임스페이스 패키지**라는 뜻이다.

둘째가 진짜 문제다. **당신 제출물의 `parking` 안에 남의 디렉터리 내용이 섞여 들어왔다.** `parking.legacy` 는 `elsewhere/` 에 있는 파일인데 당신 패키지의 일부처럼 import 됐다.

```pyrepl
>>> parking.__path__
_NamespacePath(['/.../ns/submit/parking', '/.../ns/elsewhere/parking'])
```

빈 `__init__.py` 하나를 `submit/parking/` 에 넣고 새 인터프리터에서 같은 것을 해 보면 병합이 끊긴다.

```pyrepl
>>> import sys
>>> sys.path[:0] = ["submit", "elsewhere"]
>>> import parking
>>> parking.__file__
'/.../ns/submit/parking/__init__.py'
>>> parking.__path__
['/.../ns/submit/parking']
>>> import parking.legacy
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    import parking.legacy
ModuleNotFoundError: No module named 'parking.legacy'
```

(경로는 `/.../` 로 줄였다. 나머지는 Python 3.14.0rc2 / Linux 에서 나온 그대로다.)

::: danger `__init__.py` 가 없으면 sys.path 맨 앞에 있어도 진다
이게 가장 아픈 경우다. 당신 소스 디렉터리를 `sys.path` **맨 앞**에 넣었다. 그런데 뒤쪽 어딘가에 같은 이름의 **설치된 패키지**가 있다.

```pyrepl
>>> import sys
>>> sys.path[:0] = ["submit", "installed"]   # 내 소스가 맨 앞이다
>>> import parking.fees as f
>>> f.__file__
'/.../ns2/installed/parking/fees.py'
>>> f.fee(150)
999999
```

**맨 앞에 둔 내 코드가 아니라 뒤쪽의 남의 코드가 실행됐다.** `__init__.py` 가 없는 디렉터리는 정규 패키지가 아니라 "네임스페이스 조각"으로만 기록되고, 파인더는 `sys.path` 를 끝까지 훑는다. 그 도중에 정규 패키지가 하나라도 나오면 **그쪽이 무조건 이긴다.** 조각들은 정규 패키지를 아무 데서도 못 찾았을 때만 합쳐진다.

`submit/parking/__init__.py` 를 만들고 새 인터프리터에서 똑같이 하면 뒤집힌다.

```pyrepl
>>> import sys
>>> sys.path[:0] = ["submit", "installed"]
>>> import parking.fees as f
>>> f.__file__
'/.../ns2/submit/parking/fees.py'
>>> f.fee(150)
5500
```

**당신 로컬에서는 이런 일이 안 일어난다.** 같은 이름의 패키지가 설치돼 있지 않으니까. 평가자 환경에서만 일어나고, 그때 나오는 값은 예외가 아니라 **틀린 숫자**다. 빈 파일 하나로 막을 수 있는 사고를 굳이 열어 둘 이유가 없다.
:::

::: deep PEP 420 — 왜 이렇게 만들었나
파이썬 3.3(2012)의 [PEP 420](https://peps.python.org/pep-0420/)이 암묵적 네임스페이스 패키지를 넣었다. 목적은 **하나의 패키지 이름을 여러 배포물이 나눠 갖는 것**이었다. `zope.interface` 와 `zope.component` 를 따로 설치해도 `import zope.x` 가 둘 다 되게 하려면, `zope/` 디렉터리가 여러 곳에 흩어져 있어도 합쳐져야 한다.

그러니까 위에서 본 "조용한 병합"은 버그가 아니라 **설계 목표 그 자체**다. 문제는 이 기능이 필요한 사람은 대형 프레임워크 배포자뿐인데, 기본 동작이 그쪽으로 맞춰져 있다는 것이다. 당신 과제는 패키지 이름을 나눠 가질 일이 없다. **`__init__.py` 를 두는 것은 "이 디렉터리는 나눠 갖지 않는다"는 선언**이다. 파인더의 탐색 순서와 `sys.meta_path` 의 동작은 [1.19](#/imports)에 있다.
:::

### `__init__.py` 에 무엇을 쓸 것인가

빈 파일도 되지만, 과제형에서는 **공개 API를 여기서 선언하는 편이 낫다.**

```python title="parking/__init__.py"
"""상가 주차장 정산기."""

from .errors import AlreadyParked, LotFull, NotParked, NotSettled, ParkingError
from .fees import fee
from .lot import ParkingLot, Ticket

__all__ = [
    "AlreadyParked", "LotFull", "NotParked", "NotSettled", "ParkingError",
    "ParkingLot", "Ticket", "fee",
]
```

열 줄이 하는 일은 **"이 패키지를 밖에서 쓸 때 알아야 할 이름은 여덟 개다"** 라고 못 박는 것이다. 평가자가 가장 먼저 여는 파일이 되고, 여기에 `_find_ticket` 같은 내부 이름이 없다는 사실이 곧 설계 의도를 말한다.

::: danger `__init__.py` 를 두껍게 만들면 순환 import 가 난다
`__init__.py` 가 하위 모듈을 import 하는 순간, **하위 모듈끼리의 순환이 패키지 import 자체를 죽인다.** `fees.py` 에 편의 함수를 하나 붙였다고 하자.

```python title="parking/fees.py — 한 줄 추가했을 뿐이다"
from .lot import Ticket          # 편의 함수를 만들려고 추가했다

# ... 상수와 fee() 는 그대로 ...


def fee_for(ticket: Ticket, at: int) -> int:
    return fee(at - ticket.entered_at, ticket.stamps)
```

`lot.py` 는 이미 `fees.py` 를 쓰고 있다. 결과는 이렇다.

```text nolines
$ python -c "from parking.lot import ParkingLot"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from parking.lot import ParkingLot
  File "/.../parking/__init__.py", line 4, in <module>
    from .fees import fee
  File "/.../parking/fees.py", line 3, in <module>
    from .lot import Ticket          # 편의 함수를 만들려고 추가했다
    ^^^^^^^^^^^^^^^^^^^^^^^
  File "/.../parking/lot.py", line 6, in <module>
    from .fees import MAX_STAMPS, fee
ImportError: cannot import name 'MAX_STAMPS' from partially initialized module
'parking.fees' (most likely due to a circular import) (/.../parking/fees.py)
```

(경로를 `/.../` 로 줄이고 마지막 줄만 두 줄로 접었다. 나머지는 실제 출력이다.)

**고칠 곳은 `__init__.py` 가 아니라 `fees.py` 다.** `fee_for` 는 순수 계산 모듈이 도메인 객체를 알게 만든다. 화살표를 거꾸로 놓은 것이다. `lot.py` 안에 두거나, 그냥 만들지 마라 — `fee(at - ticket.entered_at, ticket.stamps)` 는 이미 한 줄이다.

이 예외의 스택 트레이스가 **정확히 순환의 경로를 보여 준다**는 점도 기억해라. `__init__` → `fees` → `lot` → `fees`. 순환 import를 만나면 메시지를 읽지 말고 **파일 이름의 순서**를 읽어라.
:::

## `tests/` 를 왜 패키지 밖에 두는가

두 안이 있다. 실무에서 둘 다 본다.

```text nolines
   안 1                            안 2
parking/                        parking/
├── __init__.py                 ├── __init__.py
├── fees.py                     ├── fees.py
├── lot.py                      ├── lot.py
└── ...                         └── tests/
tests/                              ├── test_fees.py
├── test_fees.py                    └── test_lot.py
└── test_lot.py
```

| | 안 1 — 밖 | 안 2 — 패키지 안 |
| --- | --- | --- |
| 배포물 | 테스트가 안 들어간다 | 사용자가 테스트까지 설치한다 |
| 첫인상 | 트리 최상단에서 테스트가 보인다 | 소스를 헤집어야 보인다 |
| 테스트 실행 | 소스가 import 가능해야 한다 | 패키지 경로로 그냥 된다 |
| 쓰는 곳 | 애플리케이션, 과제 제출물 | 배포되는 라이브러리(`numpy` 등) |

**과제형은 안 1이다.** 이유가 기술이 아니다. 평가자가 저장소를 열었을 때 **`tests/` 가 최상단에 보이는 것 자체가 신호**이기 때문이다. 12.1에서 본 관문 4("테스트가 있는가")를 트리만 보고 통과한다.

### `tests/` 에 `__init__.py` 를 둘 것인가

**기본은 두지 않는다.** 그런데 두어야 하는 경우가 정확히 하나 있고, 안 겪어 보면 절대 모른다.

```text nolines
tests/
├── fees/
│   └── test_rules.py
└── lot/
    └── test_rules.py          <- 파일 이름이 같다
```

```text nolines
$ pytest -q
==================================== ERRORS ====================================
___________________ ERROR collecting tests/lot/test_rules.py ___________________
import file mismatch:
imported module 'test_rules' has this __file__ attribute:
  /.../tests/fees/test_rules.py
which is not the same as the test file we want to collect:
  /.../tests/lot/test_rules.py
HINT: remove __pycache__ / .pyc files and/or use a unique basename for your test file modules
=========================== short test summary info ============================
ERROR tests/lot/test_rules.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.11s
```

(pytest 9.1.1 / Python 3.14.0rc2 기준 실제 출력. 경로만 줄였다.)

pytest의 기본 import 모드(`prepend`)는 테스트 파일에서 위로 올라가며 `__init__.py` 가 있는 동안 계속 올라간다. **`__init__.py` 가 없는 첫 디렉터리**가 `sys.path` 에 들어가고, 모듈 이름은 거기서부터의 상대 경로가 된다. `tests/fees/` 에 `__init__.py` 가 없으니 두 파일 다 모듈 이름이 그냥 `test_rules` 가 되고, 두 번째를 수집할 때 충돌한다.

해법이 셋이다. **셋 다 실제로 통과시켰다.**

| 해법 | 하는 일 | 대가 |
| --- | --- | --- |
| 파일 이름을 유일하게 (`test_fee_rules.py`) | 충돌 자체를 없앤다 | 없다 |
| `tests/` 전체에 `__init__.py` | 모듈 이름이 `tests.fees.test_rules` 가 된다 | 빈 파일이 디렉터리 수만큼 는다 |
| `--import-mode=importlib` | 모듈 이름을 `sys.path` 와 무관하게 만든다 | 설정 한 줄, 동작이 덜 알려져 있다 |

**과제형에서는 첫째다.** 애초에 하위 디렉터리를 만들 규모가 아니고, 파일 이름이 유일하면 문제가 생기지 않는다. 하위 디렉터리가 정말 필요할 만큼 테스트가 많아졌다면 그때는 **테스트가 아니라 과제 범위를 다시 봐야 할 때**다.

::: note 실행이 안 되는 문제는 여기서 다루지 않는다
`python -m pytest` 는 되는데 `pytest` 는 `ModuleNotFoundError` 로 죽는 문제, 그리고 `pyproject.toml` 의 `pythonpath` 와 빈 `conftest.py` 중 무엇을 고를지는 [12.1](#/takehome-eval)에서 이미 실측과 함께 정했다. 요약만 하면 **`[tool.pytest.ini_options]` 에 `pythonpath` 를 적어라.** 이 절의 모든 트리는 그 설정이 있다고 가정한다.
:::

## src 레이아웃 — 무엇을 사고 무엇을 내는가

`src/` 를 한 겹 씌우는 배치다. [6.5 패키징](#/packaging)에서 배포 관점으로 다뤘다. 여기서는 **과제 제출물에 쓸 것인가**만 판단한다.

`src/` 가 실제로 사는 것은 하나다. **테스트가 "소스 디렉터리"가 아니라 "설치된 패키지"를 보게 만든다.**

평평한 배치에서 패키지를 설치하고, **그 뒤에 소스 파일에만** `MARKER` 한 줄을 추가해 보자. 그리고 프로젝트 루트에서 그 가상환경의 파이썬을 띄운다.

```bash
$ uv pip install .                     # 설치 완료
$ echo 'MARKER = "설치 후에 소스만 고쳤다"' >> parking/fees.py
```

```pyrepl
>>> import parking.fees as f
>>> f.__file__
'/.../inst/parking/fees.py'
>>> f.MARKER
'설치 후에 소스만 고쳤다'
```

**설치했는데 설치본이 안 쓰인다.** 프로젝트 루트에서 실행하면 현재 디렉터리가 `sys.path` 앞에 있고, 거기 `parking/` 이 있으니 그쪽이 이긴다. 그래서 **배포물에 파일이 빠져 있어도 로컬에서는 영원히 모른다.**

같은 실험을 `src/` 배치에서 하면 이렇게 된다.

```pyrepl
>>> import parking.fees as f
>>> f.__file__
'/.../srcl/.venv/lib/python3.14/site-packages/parking/fees.py'
>>> getattr(f, "MARKER", "<설치본에는 없다>")
'<설치본에는 없다>'
```

현재 디렉터리에 `parking/` 이 없으니 그림자가 안 생긴다. **테스트한 것이 곧 배포한 것**이 된다.

대가도 분명하다. `src/` 배치는 **설치하지 않으면 아무것도 안 돈다.**

```text nolines
$ pytest -q
==================================== ERRORS ====================================
_____________________ ERROR collecting tests/test_fees.py ______________________
ImportError while importing test module '/.../srcl3/tests/test_fees.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
...                                                            <- 중간 생략
tests/test_fees.py:3: in <module>
    from parking.fees import fee
E   ModuleNotFoundError: No module named 'parking'
______________________ ERROR collecting tests/test_lot.py ______________________
...                                                            <- 같은 내용
=========================== short test summary info ============================
ERROR tests/test_fees.py
ERROR tests/test_lot.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
2 errors in 0.14s
```

::: warn 두 배치가 갈리는 지점
| | 평평한 배치 | `src/` 배치 |
| --- | --- | --- |
| 테스트가 보는 것 | 작업 디렉터리의 소스 | 설치된 패키지 |
| 패키징 실수 | **로컬에서 절대 안 드러난다** | 즉시 드러난다 |
| 실행 전 준비 | 없음 (`pytest` 만) | `pip install -e .` 또는 `pythonpath` 설정 |
| 트리 깊이 | 한 단계 얕다 | 한 단계 깊다 |
| 이길 때 | **4시간짜리 과제 제출물** | 배포되는 라이브러리, 여러 패키지를 담는 저장소 |

**과제형이면 평평한 배치다.** `src/` 가 사는 것은 "배포물의 정확성"인데, 과제 제출물은 배포되지 않는다. 반대로 `src/` 가 내는 대가는 "평가자가 한 단계를 더 해야 한다"인데, 그건 [12.1](#/takehome-eval)의 관문 1을 직접 위협한다. **사는 것이 없는 곳에서 대가만 치르는 배치**다.

과제 지시문에 "패키지로 배포 가능하게 만들라"거나 "wheel 을 만들어 제출하라"가 있으면 그때는 `src/` 를 써라. 그리고 그때도 **README 첫 줄에 설치 명령을 적어라.**
:::

::: tip src 를 쓰면서 설치를 강요하지 않는 중간안
`src/` 를 꼭 쓰고 싶다면 pytest 설정 한 줄로 설치 없이도 돌게 만들 수 있다.

```toml title="pyproject.toml"
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```text nolines
$ pytest -q
......................                                                   [100%]
22 passed in 0.03s
```

다만 이렇게 하면 `src/` 가 사려던 것(설치본을 테스트한다)을 다시 포기하는 것이다. **얻는 것 없이 디렉터리만 한 겹 깊어진다.** 이 설정을 쓰고 있다면 애초에 평평한 배치가 맞았다는 신호로 읽어라.
:::

## 실행되는 자리를 하나 만들어라

평가자는 테스트만 돌리지 않는다. **프로그램을 한 번 굴려 본다.** 그 자리를 만드는 방법이 둘이다.

```python title="parking/__main__.py"
"""python -m parking 으로 도는 데모. 조립은 여기서만 한다."""

from .errors import ParkingError
from .lot import ParkingLot

SCRIPT = [
    ("enter", "11A1111", 0),
    ("enter", "22B2222", 5),
    ("enter", "33C3333", 7),      # 만차 — 거부된다
    ("stamp", "11A1111", 2),
    ("settle", "11A1111", 150),
    ("leave", "11A1111", 155),
]


def main() -> None:
    lot = ParkingLot(capacity=2)
    for action, plate, arg in SCRIPT:
        try:
            result = getattr(lot, action)(plate, arg)
        except ParkingError as exc:
            print(f"{action:7} {plate}  거부: {type(exc).__name__}")
            continue
        tail = "" if result is None or action == "enter" else f"-> {result}"
        print(f"{action:7} {plate}  {tail:9} 빈자리 {lot.free_spaces}")


if __name__ == "__main__":
    main()
```

```text nolines
$ python -m parking
enter   11A1111            빈자리 1
enter   22B2222            빈자리 0
enter   33C3333  거부: LotFull
stamp   11A1111  -> 2      빈자리 0
settle  11A1111  -> 2500   빈자리 0
leave   11A1111            빈자리 1
```

| | `__main__.py` | `cli.py` + `[project.scripts]` |
| --- | --- | --- |
| 실행 | `python -m parking` — 설치 불필요 | `parking-cli` — **설치해야 생긴다** |
| 평가자가 하는 일 | 명령 하나 | 설치 후 명령 하나 |
| 쓰는 곳 | 과제 제출물 | 배포되는 도구 |

**과제형은 `__main__.py` 다.** 그리고 이 파일이 하는 일은 **조립 하나뿐**이어야 한다. 요금 규칙이나 상태 판정이 여기 들어가면 그 로직은 테스트에서 영원히 빠진다. 위 파일에 요금 계산도 규칙 판정도 한 줄 없는 이유가 그것이다 — 출력 형식을 맞추는 삼항 연산 하나가 전부다. 무엇을 어디서 조립하는지는 [12.4 경계 설계](#/boundaries-di)에서 다뤘다.

## 과제 규모별 최소 구조

세 개면 충분하다. 지시문을 읽고 이 중 하나를 고르고 나면 구조 고민은 끝이다.

**규모 A — 함수 하나~둘, 1시간 이내.** "문자열을 파싱해 통계를 내라" 류.

```text nolines
log-stats/
├── README.md
├── pyproject.toml
├── logstats.py                   <- 패키지도 만들지 않는다
└── test_logstats.py              <- tests/ 도 만들지 않는다
```

이 배치는 `pythonpath` 설정도 필요 없다. 테스트 파일이 있는 디렉터리가 그대로 `sys.path` 에 들어가고 거기 `logstats.py` 가 있기 때문이다. `pytest -q` 한 줄로 끝난다.

**규모 B — 상태를 가진 시스템 하나, 3~5시간.** 주차장, 자판기, 도서 대출. **과제형의 절대 다수가 여기다.**

```text nolines
parking-lot/
├── README.md
├── pyproject.toml
├── parking/
│   ├── __init__.py
│   ├── errors.py
│   ├── fees.py
│   ├── lot.py
│   └── __main__.py
└── tests/
    ├── test_fees.py
    └── test_lot.py
```

**규모 C — 외부 시스템이 있다.** "결제 API 없이 테스트 가능하게", "하드웨어 없이 동작하게". [12.4](#/boundaries-di)의 구조가 여기다.

```text nolines
charging-station/
├── README.md
├── pyproject.toml
├── charger/
│   ├── __init__.py
│   ├── pricing.py                <- 순수 계산
│   ├── errors.py
│   ├── ports.py                  <- Protocol 로 정의한 경계
│   ├── station.py                <- 규칙. ports 만 안다
│   ├── adapters.py               <- 진짜 구현. socket 이 여기에만
│   ├── fakes.py                  <- 가짜 구현
│   └── __main__.py
└── tests/
    ├── test_pricing.py
    └── test_station.py
```

C에서도 **디렉터리는 여전히 두 개**(`charger/`, `tests/`)다. 패키지 안 파일이 여덟 개로 늘었을 뿐이다. 요구사항이 늘어날 때 늘려야 하는 것은 **파일 수지 디렉터리 깊이가 아니다.** 이게 이 절 전체에서 가장 중요한 한 문장이다.

| 지시문에 이런 말이 있으면 | 고를 것 |
| --- | --- |
| "함수를 구현하라", "스크립트를 작성하라" | A |
| "~를 관리하는 프로그램", "상태를 유지한다", "규칙 5~8개" | B |
| "외부 API 없이 테스트 가능하게", "하드웨어를 흉내 내어" | C |
| "여러 저장 방식을 지원하라" | C ([12.10](#/case-domain-repo)) |
| 위 어디에도 안 맞음 | **B로 시작해라.** 늘리는 것이 줄이는 것보다 싸다 |

::: danger 트리에서 바로 감점되는 다섯 가지
평가자는 코드를 읽기 전에 트리를 본다. 아래가 보이면 그 시점에 판단이 한 번 내려진다.

1. **파일이 하나뿐인 디렉터리.** `domain/` 안에 `lot.py` 하나. 그 디렉터리는 이름표일 뿐이고 import 문만 길어진다. [12.1](#/takehome-eval)에서 나온 기준이 그대로 적용된다.
2. **빈 디렉터리.** `infrastructure/` 에 `__init__.py` 만 있다. **만들 예정이었던 것**은 설계가 아니라 미완성이다.
3. **요구사항에 없는 최상위 디렉터리.** `docs/`, `scripts/`, `.github/workflows/`, `Dockerfile`. 4시간 과제에서 CI 설정([6.6](#/ci))과 도커([6.7](#/docker))는 **본 문제를 안 풀고 곁가지를 했다**는 뜻으로 읽힌다.
4. **`config/settings.py` 와 환경변수 로딩.** 설정할 것이 `capacity` 하나인데 설정 계층이 있다.
5. **`base/`, `common/`, `core/`, `utils/`.** 넷 다 "여기 뭘 넣을지 안 정했다"는 이름이다. 도메인 단어를 써라.

공통 진단은 하나다. **당신 구조가 요구사항 문장 수보다 많은 개념을 도입했다면 그건 설계가 아니라 장식이다.** 요구사항이 여섯 문장인 과제에서 디렉터리 열세 개를 정당화할 방법은 없다.
:::

## 다 되는지 확인하는 3분

구조를 다 잡았으면 **네 줄을 순서대로 쳐라.** 하나라도 걸리면 평가자 환경에서도 걸린다.

```bash
python -c "import parking; print(parking.__file__)"   # None 이면 __init__.py 가 없다
python -m parking                                     # 프로그램이 도는가
pytest -q                                             # 평가자가 실제로 치는 명령
python -m pytest -q                                   # 다른 경로로도 되는가
```

```text nolines
$ pytest -q
......................                                                   [100%]
22 passed in 0.03s
```

첫 줄이 특히 값어치가 있다. **`None` 이 나오면 네임스페이스 패키지**고, 위에서 본 조용한 사고가 열려 있다는 뜻이다. 이 한 줄로 3초 만에 확인된다.

그리고 이 넷을 **저장소를 새로 복제한 사본에서** 돌려라. 이유(커밋 안 된 파일이 자동으로 빠진다)와 방법은 [12.1](#/takehome-eval)에 있다.

::: cote 이 구조 감각이 쓰이는 다른 곳
알고리즘 문제 풀이에서는 파일이 하나라 이 절이 필요 없어 보인다. 그런데 **같은 판단이 함수 경계에서 그대로 반복된다.** 입력 파싱, 순수 계산, 출력 형식을 한 함수에 섞으면 계산만 따로 검증할 수 없다([11.7](#/blank-page-routine)). 파일을 쪼개는 기준(화살표가 한 방향인가)과 함수를 쪼개는 기준은 같은 것이다.

ROS 패키지 구조([10.2](#/ros-workspace))도 정확히 같은 문제다. 순수한 제어 로직을 노드 클래스에서 분리해 두면 ROS 없이 테스트할 수 있고, 안 해 두면 하드웨어를 켜야 한 줄을 확인한다.
:::

## 요약

- **구조는 취향이 아니라 첫인상이다.** 평가자는 코드보다 트리를 먼저 보고, 거기서 "이 사람이 자기 결과물의 모양을 아는가"가 읽힌다.
- **150줄 아래면 한 파일도 정답이다.** 파일을 쪼개는 신호는 길이가 아니라 두 가지다 — **테스트가 두 무리로 갈릴 때**, 그리고 **import 화살표가 한 방향으로만 갈 때**. 열한 줄짜리 `ast` 스크립트로 화살표를 직접 확인할 수 있다.
- **`__init__.py` 는 "이 디렉터리를 남과 나눠 갖지 않는다"는 선언이다.** 없어도 import 는 되지만, 다른 경로의 동명 디렉터리와 조용히 병합되고, `sys.path` 맨 앞에 있어도 뒤쪽의 정규 패키지에 진다. 그때 나오는 건 예외가 아니라 **틀린 값**이다.
- **`__init__.py` 는 공개 API 선언 자리로 쓰되 얇게 유지해라.** 두꺼워지면 하위 모듈의 순환이 패키지 import 자체를 죽인다. 순환 import 를 만나면 메시지가 아니라 **스택의 파일 순서**를 읽어라.
- **`tests/` 는 패키지 밖, `__init__.py` 없이.** 예외는 서로 다른 디렉터리에 같은 이름의 테스트 파일이 있을 때뿐이고, 그때도 **파일 이름을 유일하게 바꾸는 것**이 가장 싸다.
- **`src/` 는 "테스트한 것이 곧 배포한 것"을 사고 "설치 한 단계"를 낸다.** 과제 제출물은 배포되지 않으므로 사는 것이 없다. 평평한 배치를 써라. 지시문이 배포를 요구할 때만 예외다.
- **실행되는 자리를 `__main__.py` 하나로 만들고, 거기에는 조립만 둬라.** `python -m parking` 은 설치 없이 돈다.
- **요구사항이 늘면 파일을 늘리고 디렉터리 깊이는 늘리지 마라.** 파일 하나짜리 디렉터리, 빈 디렉터리, `utils/`, 요구사항에 없는 CI·도커는 전부 트리만 보고 감점된다.

::: quiz 설계 과제 — 트리를 그리고 실제로 돌려라
전부 **구조를 결정하고 그 결정을 코드로 확인하는** 과제다. 정답 트리는 없다. 근거 없는 트리만 틀린 것이다.

**1. 쪼개기 판단 (15분, 코드 없음 → 그 다음 코드)**
아래 요구사항을 읽고 **파일 목록**을 먼저 적어라. 파일마다 "이 파일이 import 하는 것"을 함께 적고, 화살표가 한 방향인지 확인해라. 그 다음 규모 A·B·C 중 무엇인지 판정하고 이유를 한 줄로 써라.

> **[과제] 도서 대출 관리**
> ① 회원은 최대 5권까지 빌린다. ② 대출 기간은 14일이고, 연장은 1회 7일. ③ 연체 중인 회원은 대출도 연장도 못 한다. ④ 연체료는 하루 100원, 권당 최대 3,000원. ⑤ 예약된 책은 연장할 수 없다. ⑥ 반납은 언제나 가능하다.

**2. 화살표 검사 (15분, 코드)**
1번의 구조를 실제로 만들고, 본문의 `tools/deps.py` 를 그대로 써서 각 모듈의 import 목록을 출력해라. **import 목록이 비어 있는 모듈이 최소 하나 있어야 한다.** 없다면 순수 계산을 분리하지 못한 것이다 — 분리하고 다시 돌려라.

**3. 네임스페이스 패키지 사고 재현 (20분, 코드)**
본문의 실험을 직접 재현해라. ① `__init__.py` 없는 `library/` 를 만들고 ② 다른 디렉터리에 같은 이름의 `library/` 를 만들어 그 안에만 있는 모듈을 import 해 보라. ③ `library.__file__` 과 `library.__path__` 를 출력해라. ④ `__init__.py` 를 추가하고 셋을 다시 출력해 무엇이 달라졌는지 적어라.

그다음 **더 아픈 쪽**을 재현해라. 두 번째 디렉터리에만 `__init__.py` 를 두고, 당신 소스를 `sys.path` **맨 앞**에 넣은 뒤 import 해라. **어느 쪽이 이기는가.** 결과를 보고 한 줄로 설명해라.

**4. 두 배치 비교 (25분, 코드)**
1번 프로젝트를 평평한 배치와 `src/` 배치로 **둘 다** 만들어라. 각각에서 가상환경에 설치한 뒤 소스 파일에 `MARKER = "..."` 한 줄을 추가하고, `python -c "import library.x as m; print(m.__file__, getattr(m, 'MARKER', '없음'))"` 를 돌려라. 두 결과가 다른 이유를 한 문장으로 적고, **이 과제에 어느 쪽을 낼 것인지와 그 이유**를 README 형식으로 세 줄 적어라.

**5. 순환 만들고 풀기 (15분, 코드)**
1번 구조에 **일부러 순환 import 를 만들어라.** 순수 계산 모듈이 도메인 객체를 import 하게 만들면 된다. `ImportError` 전문을 출력으로 남기고, 스택에 찍힌 파일 순서로 순환 경로를 그려라. 그다음 **`__init__.py` 를 고치지 말고** 순환을 풀어라.

**6. 과잉 구조 되돌리기 (20분, 코드 + 문장)**
아래 트리를 받았다고 하자. **규모 B로 줄여라.** 줄인 트리를 그리고, 없앤 디렉터리마다 "이게 사라져도 잃는 것이 없는 이유"를 한 줄씩 적어라. 반대로 **하나는 남기고** 왜 남기는지도 적어라.

```text nolines
library-system/
├── src/
│   └── library/
│       ├── core/
│       │   └── base/
│       │       └── entity.py
│       ├── domain/
│       │   ├── models/
│       │   │   ├── member.py
│       │   │   └── book.py
│       │   └── services/
│       │       └── loan_service.py
│       ├── application/
│       │   └── dto/
│       ├── infrastructure/
│       │   └── repositories/
│       │       └── memory_repo.py
│       └── utils/
│           └── helpers.py
├── config/
│   └── settings.py
├── docs/
├── scripts/
└── tests/
    └── unit/
        └── test_loan_service.py
```

**7. 3분 점검 자동화 (10분, 코드)**
본문의 네 줄 점검을 `check.sh` 또는 파이썬 스크립트 하나로 묶고, **하나라도 실패하면 0이 아닌 종료 코드**를 내게 만들어라. 그다음 일부러 `__init__.py` 를 지우고 돌려서 실제로 잡히는지 확인해라.
:::

**다음 절**: [12.8 README와 제출 패키징](#/readme-submit) — 이 트리를 5분 안에 실행 가능한 것으로 만드는 문서.
