# 12.3 상태와 상태 머신

::: lead
[12.2](#/requirements-to-model)의 마지막 코드에는 고백이 하나 붙어 있었다. `Movement.kind` 가 `"IN"` / `"OUT"` 이라는 **맨 문자열**이라는 것. 이 절은 그 한 줄에서 시작한다. 먼저 문자열 상태가 조용히 틀리는 방식을 보고, `enum` 으로 값의 집합을 못 박는다. 그런데 여기서 멈추면 절반이다. `Enum` 은 **어떤 값이 있는가**만 정할 뿐 **어떤 순서로 갈 수 있는가**는 여전히 아무도 모른다. 진짜 평가받는 것은 전이 규칙을 코드에 어떻게 적어 두었는가다. 이 절은 `Enum`·`IntEnum`·`StrEnum`·`Flag`·`auto()` 를 이 책에서 유일하게 제대로 다루는 자리이면서, 동시에 **그것들을 언제 쓰지 말아야 하는지**를 다루는 자리다.
:::

## `kind = "IN"` 은 어디서 틀리는가

12.2의 `Movement` 는 이렇게 생겼다.

```python
@dataclass(frozen=True)
class Movement:
    code: str
    kind: str          # "IN" | "OUT"
    amount: int
```

주석이 계약을 대신하고 있다. 주석은 실행되지 않는다.

```pyrepl
>>> kind = "OUT"
>>> kind == "Out"
False
>>> total = sum(m for m in [3, 5] if kind == "OUt")
>>> total
0
```

두 번째 줄이 `False` 인 것은 맞다. 문제는 **아무도 안 물어봤다는 것**이다. `if kind == "OUt"` 은 예외를 내지 않고, 로그도 안 남기고, 그냥 `0` 을 반환한다. 출고 합계가 0으로 나온 코드를 보고 "출고가 없었나 보다"로 넘어가는 순간 끝이다.

문자열 상태가 무너지는 방식은 셋이다.

1. **오타가 값 검사에 걸리지 않는다.** 어떤 문자열이든 대입할 수 있다. `"IN "`(뒤 공백), `"in"`, `"입고"` 전부 통과한다.
2. **비교가 어디서나 성립한다.** `movement.kind == user_input` 처럼 전혀 다른 세계의 문자열과 비교해도 타입 오류가 없다.
3. **도메인 어휘가 흩어진다.** 이 프로그램에 존재하는 `kind` 값이 몇 개인지 알려면 `grep` 을 해야 한다. 새 값을 추가하는 사람은 기존 값을 다 못 본다.

못 박는 방법은 셋이고, 성격이 다르다.

| 방법 | 잘못된 값을 언제 잡는가 | 대가 |
| --- | --- | --- |
| 모듈 상수 (`KIND_IN = "IN"`) | **못 잡는다** — 오타가 나면 새 문자열일 뿐 | 없음. 이름만 생긴다 |
| `Literal["IN", "OUT"]` | **타입 체커가** 잡는다. 실행 중에는 못 잡는다 | 없음. 값은 여전히 `str` ([2.5](#/typed-containers)) |
| `enum.Enum` | **실행 중에** 잡는다 | 새 타입이 생긴다. 직렬화할 때 손이 간다 |

과제형에서는 평가자가 당신의 `mypy` 설정을 돌려 보지 않는다. **실행 중에 잡히는 것이 실제로 증명되는 것**이다. 그래서 상태에는 `Enum` 을 쓴다.

## Enum — 값이 아니라 이름이 정체성이다

```pyrepl
>>> from enum import Enum
>>> class Movement(Enum):
...     IN = "IN"
...     OUT = "OUT"
...
>>> Movement.IN
<Movement.IN: 'IN'>
>>> Movement.IN.name, Movement.IN.value
('IN', 'IN')
>>> list(Movement)
[<Movement.IN: 'IN'>, <Movement.OUT: 'OUT'>]
>>> Movement("OUT")
<Movement.OUT: 'OUT'>
>>> Movement["OUT"]
<Movement.OUT: 'OUT'>
>>> Movement.IN is Movement("IN")
True
>>> Movement.IN == "IN"
False
>>> Movement("Out")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    Movement("Out")
ValueError: 'Out' is not a valid Movement
```

여기 중요한 줄이 셋이다.

- **`Movement.IN is Movement("IN")` 이 `True`** — 같은 값으로 몇 번을 만들어도 **객체가 하나**다. 그래서 상태 비교는 `==` 가 아니라 `is` 로 쓸 수 있고, 그 편이 의도를 더 정확히 말한다.
- **`Movement.IN == "IN"` 이 `False`** — 문자열과 섞이지 않는다. 이게 3번 문제(어휘가 새는 것)를 막는다.
- **`Movement("Out")` 이 예외** — 오타가 조용히 통과하지 않는다. 외부 입력을 `Movement(...)` 로 통과시키는 것 자체가 검증이 된다.

그리고 `list(Movement)` 한 줄이 3번 문제를 완전히 닫는다. **이 프로그램에 존재하는 값의 전체 목록이 한 곳에 있고, 코드가 그것을 읽을 수 있다.**

::: deep Enum 은 클래스처럼 생겼지만 클래스 본문이 그대로 남지 않는다
`Enum` 의 메타클래스 `EnumType` 이 클래스 본문을 훑어서, 이름-값 쌍을 **인스턴스 하나씩**으로 바꿔 클래스 속성 자리에 되돌려 놓는다. 그래서 멤버는 싱글턴이고 `is` 가 통한다.

```pyrepl
>>> from enum import Enum, auto
>>> class Status(Enum):
...     DRAFT = auto()
...     APPROVED = auto()
...
>>> type(Status)
<class 'enum.EnumType'>
>>> Status.__members__
mappingproxy({'DRAFT': <Status.DRAFT: 1>, 'APPROVED': <Status.APPROVED: 2>})
>>> Status._value2member_map_
{1: <Status.DRAFT: 1>, 2: <Status.APPROVED: 2>}
```

`Status(1)` 이 빠른 이유는 `_value2member_map_` 이라는 역인덱스가 미리 만들어져 있어서다. 그리고 싱글턴이 얼마나 강한지 보여 주는 줄이 이것이다.

```pyrepl
>>> import copy
>>> from enum import Enum, auto
>>> class Status(Enum):
...     DRAFT = auto()
...
>>> copy.deepcopy(Status.DRAFT) is Status.DRAFT
True
```

`deepcopy` 조차 복사하지 않는다. 상태를 담은 객체를 통째로 깊은 복사해도 상태 값은 여전히 같은 객체다 — `is` 비교가 깨지지 않는다. 메타클래스가 이런 일을 하는 원리는 [3.4](#/metaclass)에 있다.
:::

::: danger 같은 값을 두 번 쓰면 멤버가 조용히 하나로 합쳐진다
```pyrepl
>>> from enum import Enum
>>> class Broken(Enum):
...     DRAFT = 1
...     SUBMITTED = 1
...
>>> list(Broken)
[<Broken.DRAFT: 1>]
>>> Broken.SUBMITTED is Broken.DRAFT
True
```

`SUBMITTED` 는 새 멤버가 아니라 `DRAFT` 의 **별칭(alias)** 이 됐다. 예외도 경고도 없다. 상태 여섯 개를 손으로 번호 매기다가 3을 두 번 쓰면, 두 상태가 같은 상태가 되고 전이 규칙이 통째로 무너진다. `list(Broken)` 의 길이가 줄어 있는 것으로만 눈치챌 수 있다.

별칭을 의도한 게 아니라면 `@unique` 를 붙여라. **클래스를 정의하는 순간** 터진다.

```pyrepl
>>> from enum import Enum, unique
>>> @unique
... class Guarded(Enum):
...     DRAFT = 1
...     SUBMITTED = 1
...
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    @unique
ValueError: duplicate values found in <enum 'Guarded'>: SUBMITTED -> DRAFT
```
:::

### `auto()` 는 무엇을 선언하는가

`auto()` 는 타자를 줄이는 도구가 아니다. **"이 값에는 의미가 없다"는 선언**이다.

```pyrepl
>>> from enum import Enum, auto
>>> class Status(Enum):
...     DRAFT = auto()
...     SUBMITTED = auto()
...     APPROVED = auto()
...
>>> [(s.name, s.value) for s in Status]
[('DRAFT', 1), ('SUBMITTED', 2), ('APPROVED', 3)]
```

값 `1, 2, 3` 은 나왔지만 그 숫자를 코드 어디에서도 쓰지 않겠다는 뜻이다. 그러면 상태를 추가하거나 순서를 바꿔도 **다른 파일을 열 이유가 없다.** 반대로 값을 손으로 적었다면, 읽는 사람은 "이 3에 무슨 뜻이 있나?"를 한 번 생각하게 된다. 뜻이 없는데 생각하게 만드는 것이 비용이다.

그래서 판단 기준은 하나다.

> **그 값이 이 프로그램 밖으로 나가는가.** 나가면 손으로 적고, 안 나가면 `auto()`.

밖으로 나가는 경우는 구체적이다. JSON 응답 필드, DB 컬럼, 파일 포맷, 외부 프로토콜 코드, 사양서에 번호가 박혀 있는 것(HTTP 상태 코드, 센서 모드 값). 이때는 값 자체가 계약이므로 `auto()` 를 쓰면 안 된다.

::: danger auto() 값을 저장하면 멤버 순서가 데이터 포맷이 된다
```python title="auto_danger.py"
from enum import Enum, auto

# 1차 제출 — 이 값으로 파일에 저장했다
class StatusV1(Enum):
    DRAFT = auto()
    SUBMITTED = auto()
    APPROVED = auto()

saved = StatusV1.APPROVED.value          # 3 이 파일에 적혔다
print("저장된 값:", saved)

# 2차 제출 — '검토중'을 중간에 끼워 넣었다. 표만 고쳤을 뿐이다.
class StatusV2(Enum):
    DRAFT = auto()
    SUBMITTED = auto()
    REVIEWING = auto()
    APPROVED = auto()

print("같은 값을 다시 읽으면:", StatusV2(saved).name)
```

```text nolines
저장된 값: 3
같은 값을 다시 읽으면: REVIEWING
```

**승인된 발주가 검토중으로 되살아났다.** 예외는 없다. `3` 은 여전히 유효한 값이기 때문이다.

`auto()` 는 "값에 의미가 없다"는 **약속**이고, 그 값을 저장하는 순간 당신이 그 약속을 깬 것이다. 저장이 필요하면 값을 손으로 적거나(`DRAFT = "DRAFT"`), 아니면 **값이 아니라 `name` 을 저장해라.** `name` 은 멤버를 삽입해도 안 밀린다.
:::

::: note 이름을 그대로 값으로 쓰고 싶을 때
`auto()` 가 무슨 값을 낼지는 `_generate_next_value_` 가 정한다. `Enum` 은 1부터 세지만 `StrEnum` 은 **멤버 이름을 소문자로** 낸다.

```pyrepl
>>> from enum import StrEnum, auto
>>> class Kind(StrEnum):
...     IN = auto()
...     OUT = auto()
...
>>> [(k.name, k.value) for k in Kind]
[('IN', 'in'), ('OUT', 'out')]
```

소문자로 바뀐다는 것을 모르고 쓰면 외부 시스템과 값이 안 맞는다. 대문자가 필요하면 `IN = "IN"` 처럼 그냥 적어라. 이 자리에서 `_generate_next_value_` 를 재정의하는 것은 과제형에서 거의 항상 과한 설계다.
:::

### IntEnum / StrEnum — 편의의 대가

`Enum` 멤버는 `int` 도 `str` 도 아니다. 그래서 외부와 값을 주고받을 때 한 번 걸린다.

```pyrepl
>>> import json
>>> from enum import Enum, IntEnum, StrEnum, auto
>>> class Status(Enum):
...     DRAFT = auto()
...
>>> class Level(IntEnum):
...     LOW = 1
...     HIGH = 2
...
>>> class Kind(StrEnum):
...     IN = "IN"
...     OUT = "OUT"
...
>>> str(Status.DRAFT), f"{Status.DRAFT}"
('Status.DRAFT', 'Status.DRAFT')
>>> str(Level.HIGH), f"{Level.HIGH}"
('2', '2')
>>> str(Kind.IN), f"{Kind.IN}"
('IN', 'IN')
>>> json.dumps({"level": Level.HIGH, "kind": Kind.IN})
'{"level": 2, "kind": "IN"}'
>>> json.dumps({"status": Status.DRAFT})
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    json.dumps({"status": Status.DRAFT})
TypeError: Object of type Status is not JSON serializable
when serializing dict item 'status'
```

`IntEnum` 과 `StrEnum` 은 각각 `int` 와 `str` 의 서브클래스다. 그래서 `json.dumps` 가 그대로 삼키고, 문자열 포매팅도 값으로 나온다. 순수 `Enum` 은 `Status.DRAFT` 라고 찍히고 JSON에서는 예외가 난다.

이 편의에는 정확한 대가가 있다.

::: danger IntEnum 은 남의 IntEnum 과도 같다고 말한다
```pyrepl
>>> from enum import Enum, IntEnum
>>> class Status(IntEnum):
...     DRAFT = 1
...     APPROVED = 2
...
>>> class Priority(IntEnum):
...     NORMAL = 1
...     URGENT = 2
...
>>> Status.DRAFT == Priority.NORMAL
True
>>> Status.APPROVED > Priority.NORMAL
True
>>> sorted([Status.APPROVED, Priority.NORMAL])
[<Priority.NORMAL: 1>, <Status.APPROVED: 2>]
```

**전혀 다른 두 도메인의 값이 같다고 나온다.** `IntEnum` 은 `int` 라서, 비교가 결국 정수 비교로 내려간다. 인자 순서를 바꿔 넣은 버그가 `if status == priority:` 에서 조용히 참이 된다.

같은 코드를 순수 `Enum` 으로 쓰면 이렇게 된다.

```pyrepl
>>> from enum import Enum
>>> class S2(Enum):
...     DRAFT = 1
...
>>> class P2(Enum):
...     NORMAL = 1
...
>>> S2.DRAFT == P2.NORMAL
False
```

`IntEnum` 은 **기존 정수 API와 섞여야 할 때만** 쓴다. 대표적으로 이 책의 [10.8 QoS](#/qos)에서 DDS의 정수 정책 값을 다룰 때가 그런 자리다. 도메인 상태에는 쓰지 마라.
:::

`StrEnum` 도 같은 성질을 갖는다. 다만 이쪽은 **기존 문자열 코드를 안 깨고 갈아 끼우는 사다리**로 쓸 값어치가 있다.

```pyrepl
>>> from enum import StrEnum
>>> class Kind(StrEnum):
...     IN = "IN"
...     OUT = "OUT"
...
>>> Kind.IN == "IN"
True
>>> Kind.IN == "in"
False
>>> [k for k in Kind if k == "Out"]
[]
```

`Kind.IN == "IN"` 이 참이므로 코드 곳곳에 흩어져 있는 `m.kind == "OUT"` 류의 기존 비교문이 **한 줄도 안 고치고 계속 동작한다.** 값을 만드는 쪽부터 바꾸고 비교문은 나중에 정리하는 이행이 가능하다.

그런데 마지막 두 줄을 봐라. `"Out"` 오타는 여전히 조용히 `False` 다. **`StrEnum` 은 문자열의 위험을 없애는 게 아니라 미룬다.** 이행이 끝나면 순수 `Enum` 으로 내려라.

| 고르는 것 | 조건 |
| --- | --- |
| `Enum` + `auto()` | **기본값.** 값이 프로그램 밖으로 안 나간다 |
| `Enum` + 손으로 적은 값 | 값이 밖으로 나가고, 그 값이 계약이다 |
| `StrEnum` | 외부 표현이 문자열이고, 기존 문자열 코드와 섞여 있다 |
| `IntEnum` | 기존 정수 API(프로토콜, C 라이브러리, DB 코드)와 섞인다 |
| `Flag` | 상태가 아니라 **동시에 여러 개가 켜지는 것** |

### Flag — 배타적이지 않은 것들

`Flag` 는 `auto()` 값을 2의 거듭제곱으로 낸다. 조합해서 하나의 값으로 들고 다니라는 뜻이다.

```pyrepl
>>> from enum import Flag, auto
>>> class Perm(Flag):
...     READ = auto()
...     WRITE = auto()
...     APPROVE = auto()
...
>>> [(p.name, p.value) for p in Perm]
[('READ', 1), ('WRITE', 2), ('APPROVE', 4)]
>>> staff = Perm.READ | Perm.WRITE
>>> staff
<Perm.READ|WRITE: 3>
>>> Perm.WRITE in staff
True
>>> Perm.APPROVE in staff
False
>>> list(staff)
[<Perm.READ: 1>, <Perm.WRITE: 2>]
```

`in` 이 그대로 "이 권한을 갖고 있는가"로 읽힌다. `staff & Perm.APPROVE` 같은 비트 연산 대신 `in` 을 써라 — 같은 일을 하는데 읽는 사람이 안 멈춘다.

::: warn 상태에 Flag 를 쓰면 존재할 수 없는 상태가 표현 가능해진다
상태 머신의 상태는 **배타적**이다. 발주서가 동시에 승인됨이면서 취소됨일 수는 없다. `Flag` 로 만들면 `Status.APPROVED | Status.CANCELLED` 라는 값이 **문법적으로 만들어진다.** 그런 값이 만들어질 수 있으면 언젠가 만들어진다.

`Flag` 가 맞는 자리는 권한, 옵션 조합, 열린 기능 목록처럼 **여러 개가 동시에 참일 수 있는 것**뿐이다. 과제형 요구사항에서 그런 문장은 드물다. 상태에는 `Enum`, 조합에는 `Flag`. 헷갈리면 요구사항 문장에 "동시에"나 "그리고"가 있는지 봐라.
:::

## Enum 만으로는 상태 머신이 아니다

이제 필드를 `Enum` 으로 바꿨다고 하자. 그런데 이건 여전히 상태 머신이 아니다. 아래 세션은 **이 절에서 곧 만들 `purchase` 패키지를 미리 쓴 것**이다. 지금 그대로 따라 치면 `ModuleNotFoundError` 가 난다 — 파일이 전부 나온 뒤에 돌려 봐라.

```pyrepl
>>> from purchase.order import PurchaseOrder
>>> from purchase.states import OrderStatus
>>> po = PurchaseOrder("PO-1", "A-1", 30)
>>> po.status
<OrderStatus.DRAFT: 1>
>>> po.status = OrderStatus.RECEIVED
>>> po.status
<OrderStatus.RECEIVED: 5>
>>> po.history
[]
```

**작성 중인 발주서가 승인 없이 입고 완료가 됐다.** `Enum` 이 막아 준 것은 "존재하지 않는 값"뿐이고, "존재하지만 지금은 갈 수 없는 값"은 하나도 막지 못했다. 리뷰어가 보는 것은 정확히 이 부분이다. 값의 집합이 아니라 **값 사이의 순서**를 코드에 적었는가.

이 절의 예제 요구사항이다. 12.2의 재고 관리에서 자연스럽게 이어지는 부분 — 보충 대상 품목에 대한 발주서다.

> **[과제 일부] 발주서**
>
> 1. 발주서는 작성 중 상태로 만들어진다.
> 2. 작성 중인 발주서는 **상신**할 수 있다.
> 3. 상신된 발주서는 **승인**되거나 **반려**된다.
> 4. 승인된 발주서만 **입고 처리**할 수 있다.
> 5. 입고 전이면 어느 단계에서든 **취소**할 수 있다.
> 6. 반려·입고·취소된 발주서는 더 이상 바뀌지 않는다.
> 7. 발주서가 지나온 상태 변화를 조회할 수 있다.

문장 여섯 개가 곧 전이 규칙이다. 그림으로 옮기면 이렇게 된다.

```text nolines
  DRAFT --submit--> SUBMITTED --approve--> APPROVED --receive--> RECEIVED *
                        |
                        +--reject--> REJECTED *

  DRAFT, SUBMITTED, APPROVED --cancel--> CANCELLED *

  * = final state (no outgoing transition)
```

상태 6개 × 사건 5개 = **30가지 조합 중 7가지만 허용된다.** 나머지 23가지를 어떻게 막을 것인가가 이 절의 본론이다.

이 절의 코드가 앉는 자리다. 12.2의 재고 관리와 같은 최소 형태이고, 패키지 이름만 `purchase` 로 바뀌었다.

```text nolines
purchase-task/
├── purchase/
│   ├── __init__.py
│   ├── states.py       OrderStatus, OrderEvent, TRANSITIONS, FINAL_STATES
│   ├── errors.py       PurchaseError, InvalidTransition
│   └── order.py        PurchaseOrder
├── tests/
│   └── test_order_states.py
├── run_demo.py
└── pyproject.toml      pythonpath = ["."] — tests 에서 purchase 를 import 할 수 있게 한다
```

```toml title="pyproject.toml"
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

**`pythonpath` 한 줄을 빼먹으면 이 절의 테스트는 한 개도 안 돈다.** `pytest` 는 테스트 파일에서 위로 올라가며 `__init__.py` 가 없는 첫 디렉터리(`tests/`)만 `sys.path` 에 넣으므로 프로젝트 루트가 안 들어가고, 수집 단계에서 `ModuleNotFoundError: No module named 'purchase'` 로 죽는다. `pythonpath` 대신 프로젝트 루트에 **빈 `conftest.py`** 를 하나 둬도 같은 일이 된다. 둘의 차이와 왜 과제 제출에는 `pythonpath` 쪽인지는 [12.1](#/takehome-eval)에 있다.

```python title="purchase/states.py"
from enum import Enum, auto


class OrderStatus(Enum):
    """발주서가 지날 수 있는 상태. 값에 의미가 없으므로 auto()."""

    DRAFT = auto()
    SUBMITTED = auto()
    APPROVED = auto()
    REJECTED = auto()
    RECEIVED = auto()
    CANCELLED = auto()


class OrderEvent(Enum):
    """상태를 바꾸는 사건. 상태가 아니라 '일어난 일'이다."""

    SUBMIT = auto()
    APPROVE = auto()
    REJECT = auto()
    RECEIVE = auto()
    CANCEL = auto()
```

**상태와 사건을 다른 `Enum` 으로 나눈 것**이 첫 번째 설계 결정이다. 하나로 합치면 `Status.SUBMITTED` 와 `Status.SUBMIT` 이 같은 목록에 섞여서, 읽는 사람이 매번 "이건 상태인가 동작인가"를 판단해야 한다. 상태는 **명사**, 사건은 **동사** — [12.2](#/requirements-to-model)의 명사·동사 분리가 여기서 그대로 이어진다.

### 안 A — 전이표를 `dict` 로

```python title="purchase/states.py (이어서)"
# (현재 상태, 사건) -> 다음 상태. 여기 없는 조합은 전부 금지다.
TRANSITIONS: dict[tuple[OrderStatus, OrderEvent], OrderStatus] = {
    (OrderStatus.DRAFT, OrderEvent.SUBMIT): OrderStatus.SUBMITTED,
    (OrderStatus.SUBMITTED, OrderEvent.APPROVE): OrderStatus.APPROVED,
    (OrderStatus.SUBMITTED, OrderEvent.REJECT): OrderStatus.REJECTED,
    (OrderStatus.APPROVED, OrderEvent.RECEIVE): OrderStatus.RECEIVED,
    (OrderStatus.DRAFT, OrderEvent.CANCEL): OrderStatus.CANCELLED,
    (OrderStatus.SUBMITTED, OrderEvent.CANCEL): OrderStatus.CANCELLED,
    (OrderStatus.APPROVED, OrderEvent.CANCEL): OrderStatus.CANCELLED,
}

# 나가는 전이가 하나도 없는 상태 = 종료 상태. 목록을 따로 적지 않고 표에서 뽑는다.
FINAL_STATES = frozenset(
    s for s in OrderStatus if not any(src is s for src, _ in TRANSITIONS)
)
```

일곱 줄이 요구사항 2~5를 그대로 옮긴 것이다. 그리고 마지막 세 줄이 중요하다. **요구사항 6(종료 상태)을 손으로 적지 않고 표에서 계산한다.** 종료 상태 목록을 따로 두면 표를 고칠 때 그 목록을 같이 고쳐야 하고, 언젠가 안 고친다. 진실의 출처는 하나여야 한다.

### 안 B — `match` 문으로

같은 규칙을 [1.8 match 문](#/control-flow)으로 쓸 수도 있다.

```python title="안 B — 전이를 match 로 (발췌)"
S, E = OrderStatus, OrderEvent


def next_status(order_id: str, status: S, event: E) -> S:
    match status, event:
        case S.DRAFT, E.SUBMIT:
            return S.SUBMITTED
        case S.SUBMITTED, E.APPROVE:
            return S.APPROVED
        case S.SUBMITTED, E.REJECT:
            return S.REJECTED
        case S.APPROVED, E.RECEIVE:
            return S.RECEIVED
        case (S.DRAFT | S.SUBMITTED | S.APPROVED), E.CANCEL:
            return S.CANCELLED
        case _:
            raise InvalidTransition(order_id, status, event)
```

두 안은 30가지 조합 전부에서 같은 답을 낸다(직접 대조해서 확인했다). 그런데 **성격이 다르다.**

| | 안 A — `dict` 표 | 안 B — `match` |
| --- | --- | --- |
| 규칙이 데이터인가 | **데이터다.** 순회·검사·문서화가 가능하다 | 코드다. 밖에서 볼 수 없다 |
| "지금 뭘 할 수 있나" 질의 | `(status, e) in TRANSITIONS` 한 줄 | 별도 함수를 또 쓴다 |
| 종료 상태 계산 | 표에서 뽑힌다 | 손으로 적어야 한다 |
| 전이할 때 부수 효과 | 넣을 자리가 없다 | `case` 안에 바로 쓴다 |
| 조건이 붙는 전이 | 표로 표현 못 한다 | `case ... if amount > 0:` 로 자연스럽다 |
| 상태가 20개로 늘면 | 표가 길어질 뿐 | `case` 가 20개 넘게 늘어난다 |

**판단 기준은 이것이다.**

> **전이가 (상태, 사건) → 상태로 끝나면 표, 전이마다 다른 일을 해야 하면 `match`.**

이 요구사항은 전자다. 전이할 때 하는 일이 "상태를 바꾸고 이력을 남긴다"로 전부 같다. 그래서 이 절은 안 A로 간다. 반대로 "승인 시 담당자에게 통지하고, 입고 시 재고를 증가시킨다" 같은 문장이 붙으면 전이마다 하는 일이 달라지므로 안 B가 유리해진다.

::: danger match 에서 점 없는 이름은 비교가 아니라 대입이다
`match` 의 `case` 에 **그냥 이름**을 쓰면 값을 비교하는 게 아니라 **그 이름에 값을 담는다**(캡처 패턴). 그래서 무조건 매치된다.

```pyrepl
>>> from enum import Enum, auto
>>> class Status(Enum):
...     DRAFT = auto()
...     SUBMITTED = auto()
...     APPROVED = auto()
...
>>> APPROVED = Status.APPROVED
>>> def label(status):
...     match status:
...         case Status.DRAFT:
...             return "작성중"
...         case APPROVED:
...             return "승인됨"
...     return "그 외"
...
>>> label(Status.APPROVED)
'승인됨'
>>> label(Status.SUBMITTED)
'승인됨'
```

**`SUBMITTED` 를 넣었는데 "승인됨"이 나왔다.** `case APPROVED:` 는 "`APPROVED` 와 같은가"가 아니라 "무엇이든 받아서 지역 변수 `APPROVED` 에 담아라"였다.

파이썬이 이걸 잡아 주는 경우도 있다. 캡처 패턴 **뒤에** 다른 `case` 가 남아 있으면 `SyntaxError: name capture 'DRAFT' makes remaining patterns unreachable` 로 컴파일 단계에서 막힌다. 위 예시는 캡처가 **마지막 `case`** 라 그 검사에 안 걸렸다. 이것이 상태 상수를 `from .states import DRAFT` 처럼 뜯어서 import 하면 안 되는 이유다. **`match` 에서 상수는 항상 점이 있는 이름(`Status.DRAFT`, `S.DRAFT`)으로 써라.** 패턴 매칭 규칙 전체는 [1.8](#/control-flow)에 있다.
:::

::: perf 두 안의 속도 차이는 판단 근거가 될 수 없다
**무엇을 쟀는지부터 밝힌다.** 셋 다 `(상태, 사건) -> 다음 상태` 를 돌려주는 **함수를 한 번 부르는 것**이 1회이고, 그 호출을 `timeit` 으로 10만 번 돌렸다(`step(st, ev)`, `number=100_000`, `repeat=15`, 하위 5개). 상태와 사건은 미리 지역 변수에 담아 뒀다 — `apply()` 안에서 `self.status` 와 인자를 쓰는 실제 모양에 맞춘 것이다. 함수 본문만 다르다.

- `step_dict` — 안 A 그대로. `apply` 의 본문인 `try: TRANSITIONS[status, event] / except KeyError: raise InvalidTransition`
- `step_match` — 안 B의 `next_status` 본문 그대로. 세 함수의 인자를 맞추려고 `order_id` 만 뺐다
- `step_str` — `step_dict` 과 같은 코드인데 표의 키와 값이 `("SUBMITTED", "APPROVE"): "APPROVED"` 처럼 전부 문자열이다

| 방식 | 10만 회 | 문자열 대비 |
| --- | --- | --- |
| 문자열 키 `dict` 표 | 5.9 ~ 6.2 ms | ×1.0 |
| `Enum` + `match` | 14.9 ~ 15.9 ms | ×2.5 ~ 2.6 |
| `Enum` + `dict` 표 | 16.9 ~ 19.1 ms | ×2.9 ~ 3.1 |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**절대값은 믿지 말고 마지막 열을 봐라.** 같은 기계에서도 다른 프로세스가 돌면 세 줄이 나란히 두 배로 뛴다. 흔들리지 않는 것은 배수다.

두 가지를 읽어야 한다.

**하나, `match` 와 `dict` 표의 차이는 10만 번에 2~3 ms 다.** 전이 하나당 25 나노초 안팎. 이 차이로 설계를 고르는 것은 근거 없는 선택을 근거 있는 것처럼 포장하는 일이다. 읽히는 쪽을 골라라.

**둘, `Enum` 은 문자열보다 3배쯤 느리다.** 이건 진짜 차이다. 원인도 분명하다 — `S.DRAFT` 같은 멤버 접근이 상수 로드보다 두 배 넘게 비싸고(`x = S.SUBMITTED` 대 `x = "SUBMITTED"`, 100만 회에 15.8~16.5 ms 대 7.2~7.7 ms), `Enum.__hash__` 는 내부적으로 이름 문자열을 해싱하므로 `hash(str)` 보다 세 배 든다(`hash(S.SUBMITTED)` 대 `hash("SUBMITTED")`, 100만 회에 72.8~77.3 ms 대 24.4~27.8 ms). 그래도 **10만 번에 12 ms** 다. 과제형이 다루는 데이터는 수천 건이고, 그 규모에서 이 차이는 사람이 인지할 수 없다([5.1](#/profiling)).
:::

::: cote 시간 제한이 걸린 코딩테스트에서는 이야기가 뒤집힌다
위 측정의 세 배는 데이터가 수백만 건이면 그대로 초 단위가 된다. 알고리즘 문제에서 방향이나 상태를 표현할 때 `Enum` 을 꺼내지 마라. 정수 상수나 문자열이 정답이다. **`Enum` 은 "여러 사람이 읽고 고치는 코드"의 도구이지 "한 번 제출하고 버리는 코드"의 도구가 아니다.** 같은 사람이 같은 주에 두 종류의 시험을 보면서 도구를 바꿔 잡아야 하는 대표적인 자리다([8.3](#/tle)).
:::

### 상태를 바꾸는 자리를 하나로 모아라

전이표가 있어도 `po.status = ...` 를 여기저기서 하면 아무 소용이 없다. **상태 대입은 딱 한 군데서만 일어나야 한다.**

```python title="purchase/errors.py"
from .states import OrderEvent, OrderStatus


class PurchaseError(Exception):
    """이 도메인이 거부한 요청."""


class InvalidTransition(PurchaseError):
    def __init__(self, order_id: str, state: OrderStatus, event: OrderEvent) -> None:
        super().__init__(f"{order_id}: {state.name} 상태에서는 {event.name} 할 수 없다")
        self.order_id = order_id
        self.state = state
        self.event = event
```

```python title="purchase/order.py"
from dataclasses import dataclass, field

from .errors import InvalidTransition
from .states import FINAL_STATES, TRANSITIONS, OrderEvent, OrderStatus


@dataclass
class PurchaseOrder:
    order_id: str
    code: str
    amount: int
    status: OrderStatus = OrderStatus.DRAFT
    history: list[tuple[OrderStatus, OrderEvent, OrderStatus]] = field(
        default_factory=list
    )

    def apply(self, event: OrderEvent) -> None:
        """status 를 바꾸는 유일한 자리. 다른 어디에서도 대입하지 않는다."""
        try:
            following = TRANSITIONS[self.status, event]
        except KeyError:
            raise InvalidTransition(self.order_id, self.status, event) from None
        self.history.append((self.status, event, following))
        self.status = following

    def can(self, event: OrderEvent) -> bool:
        return (self.status, event) in TRANSITIONS

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATES

    # 호출자가 읽기 좋으라고 붙인 얇은 이름. 규칙은 전부 apply 안에 있다.
    def submit(self) -> None:
        self.apply(OrderEvent.SUBMIT)

    def approve(self) -> None:
        self.apply(OrderEvent.APPROVE)

    def reject(self) -> None:
        self.apply(OrderEvent.REJECT)

    def receive(self) -> None:
        self.apply(OrderEvent.RECEIVE)

    def cancel(self) -> None:
        self.apply(OrderEvent.CANCEL)
```

여기서 지킨 것이 넷이다.

1. **`apply` 하나만이 `self.status` 에 대입한다.** 규칙을 바꿀 때 볼 곳이 한 군데다.
2. **거부는 예외이고, 예외에는 판단에 필요한 정보가 전부 들어 있다.** 메시지 문자열뿐 아니라 `state` 와 `event` 를 속성으로 남겼다. 호출자가 `except InvalidTransition as e:` 로 잡아 `e.state` 를 읽고 화면에 다르게 표시할 수 있다. 예외에 무엇을 담는가는 [12.5](#/error-design)에서 본격적으로 다룬다.
3. **거부되면 아무것도 안 바뀐다.** `history.append` 가 조회 뒤에 있으므로, 실패한 시도는 이력에 안 남는다. [12.2](#/requirements-to-model)에서 "거부된 출고는 이력에 남기지 않는다"로 내렸던 결정과 같은 결정이다.
4. **`can()` 이 있다.** UI가 버튼을 회색으로 만들 때 `try/except` 로 시험 삼아 호출하지 않아도 된다. 표가 데이터이기 때문에 한 줄로 끝난다.

```python title="run_demo.py"
from purchase.errors import InvalidTransition
from purchase.order import PurchaseOrder
from purchase.states import OrderEvent

po = PurchaseOrder("PO-1", "A-1", 30)
po.submit()
po.approve()
print("입고 가능:", po.can(OrderEvent.RECEIVE))
po.receive()
print("현재 상태:", po.status.name, "/ 종료됨:", po.is_final)

try:
    po.cancel()
except InvalidTransition as e:
    print("거부:", e)
    print("  잡아서 쓸 수 있는 정보:", e.state.name, e.event.name)

for before, event, after in po.history:
    print(f"  {before.name} --{event.name}--> {after.name}")
```

```text nolines
입고 가능: True
현재 상태: RECEIVED / 종료됨: True
거부: PO-1: RECEIVED 상태에서는 CANCEL 할 수 없다
  잡아서 쓸 수 있는 정보: RECEIVED CANCEL
  DRAFT --SUBMIT--> SUBMITTED
  SUBMITTED --APPROVE--> APPROVED
  APPROVED --RECEIVE--> RECEIVED
```

요구사항 7(지나온 상태 변화 조회)이 **별도 코드 없이** 나왔다. 전이가 한 자리를 지나가게 만들면 이력은 부산물로 생긴다.

## 과하게 설계하지 않는 선

여기까지 왔으면 상태 머신이 재미있어진다. 그게 위험한 지점이다. 과제형에서 **오버엔지니어링은 가산점이 아니라 감점**이라는 것을 [12.1](#/takehome-eval)에서 봤다. 상태 머신은 특히 부풀리기 쉬운 주제다.

### 불리언 두 개 대 `Enum` 하나

상태가 둘뿐이면 `bool` 이 정답일 때가 있다. 문제는 셋으로 늘 때다.

```python title="bool_two_flags.py"
from dataclasses import dataclass


# ❌ 불리언 두 개 = 표현 가능한 조합이 네 가지. 그중 하나는 존재할 수 없다.
@dataclass
class Order:
    approved: bool = False
    cancelled: bool = False


# approved=True, cancelled=True 를 막는 것이 아무것도 없다
print(Order(approved=True, cancelled=True))
```

```text nolines
Order(approved=True, cancelled=True)
```

승인되면서 동시에 취소된 발주서가 예외 하나 없이 만들어졌다.

판단 기준은 개수가 아니다.

> **표현할 수 있는 조합 중에 존재할 수 없는 것이 있는가.** 있으면 `Enum`.

`bool` 두 개는 네 가지를 표현하는데 실제 상태는 셋이다. **남는 하나가 버그의 자리다.** 그리고 `if not order.cancelled and order.approved:` 같은 조건이 코드 곳곳에 퍼지기 시작한다. 반대로 상태가 정확히 둘이고 이름이 서로의 부정형이면(문이 `열림`/`닫힘`) `bool` 이 더 짧고 정직하다. 그때도 필드 이름을 `is_open` 처럼 **참일 때의 뜻이 분명하게** 지어라.

### 상태마다 클래스를 만들지 마라 (아직은)

교과서에 나오는 State 패턴은 상태마다 클래스를 만들고 메서드를 재정의한다.

```python title="이 요구사항에 이걸 쓰면 (조각 — 구조만 본다)"
class State:
    def submit(self, order): raise InvalidTransition(...)
    def approve(self, order): raise InvalidTransition(...)
    def reject(self, order): raise InvalidTransition(...)
    def receive(self, order): raise InvalidTransition(...)
    def cancel(self, order): raise InvalidTransition(...)

class Draft(State): ...
class Submitted(State): ...
class Approved(State): ...
class Rejected(State): ...
class Received(State): ...
class Cancelled(State): ...
```

**클래스 7개와 메서드 자리 30개가 전이표 7줄을 대신한다.** 그리고 전체 규칙을 보려면 파일 여섯 개를 열어야 한다. 표는 한 화면이었다.

이 패턴이 이기기 시작하는 조건은 분명하다.

- 상태마다 **가지고 있는 데이터가 다르다**(승인 상태에만 승인자·승인 시각이 있다).
- 상태마다 **같은 이름의 동작이 실제로 다르게 동작한다**(전이가 아니라 계산까지).
- 전이 개수보다 **상태별 분기가 훨씬 많다.**

셋 중 하나도 아니면 표가 이긴다. 이 요구사항은 셋 다 아니다.

::: warn 상태 머신 라이브러리를 설치하지 마라
`transitions` 같은 좋은 라이브러리가 있다. 과제형에서는 쓰지 마라. 이유가 셋이다.

1. 평가자가 **의존성을 설치해야 한다.** [12.1](#/takehome-eval)의 첫 관문(실행되는가)에서 걸릴 위험을 스스로 만드는 것이다.
2. 규칙 일곱 줄을 표현하는 데 라이브러리가 필요하다면, **그 일곱 줄을 직접 못 짠다는 뜻으로 읽힌다.** 이 과제가 보려는 것이 정확히 그 일곱 줄이다.
3. 라이브러리의 DSL을 배우는 시간이 요구사항 하나를 더 구현하는 시간이다.

의존성을 추가할 때의 기준은 하나다. **직접 짜면 100줄이 넘고 틀리기 쉬운가.** 전이표는 7줄이고 틀리면 테스트가 잡는다.
:::

## 상태 머신을 테스트하는 법

상태 머신은 테스트하기 좋은 대상이다. **조합이 유한하기 때문**이다. 상태 6 × 사건 5 = 30가지. 전수로 돌 수 있다.

그런데 여기에 함정이 하나 있다. 테스트를 두 종류로 나눠서 봐야 한다.

```python title="tests/test_order_states.py — 규칙 검증 (손으로 쓴다)"
import pytest

from purchase.errors import InvalidTransition
from purchase.order import PurchaseOrder
from purchase.states import TRANSITIONS, OrderEvent, OrderStatus


def order(status=OrderStatus.DRAFT):
    return PurchaseOrder("PO-1", "A-1", 30, status=status)


def test_새_발주서는_작성중_상태로_시작한다():
    assert order().status is OrderStatus.DRAFT


def test_상신_승인_입고_순서로_진행된다():
    po = order()
    po.submit()
    assert po.status is OrderStatus.SUBMITTED
    po.approve()
    assert po.status is OrderStatus.APPROVED
    po.receive()
    assert po.status is OrderStatus.RECEIVED
    assert po.is_final


def test_상신하지_않은_발주서는_승인할_수_없다():
    with pytest.raises(InvalidTransition):
        order().approve()


def test_반려된_발주서는_다시_승인할_수_없다():
    po = order(OrderStatus.SUBMITTED)
    po.reject()
    with pytest.raises(InvalidTransition) as exc:
        po.approve()
    assert exc.value.state is OrderStatus.REJECTED
    assert exc.value.event is OrderEvent.APPROVE


@pytest.mark.parametrize(
    "status", [OrderStatus.DRAFT, OrderStatus.SUBMITTED, OrderStatus.APPROVED]
)
def test_입고_전이면_어느_단계에서든_취소할_수_있다(status):
    po = order(status)
    po.cancel()
    assert po.status is OrderStatus.CANCELLED


def test_입고된_발주서는_취소할_수_없다():
    po = order(OrderStatus.APPROVED)
    po.receive()
    with pytest.raises(InvalidTransition):
        po.cancel()
```

이름만 읽으면 요구사항 1~6이 재구성된다. **`assert` 를 여러 개 쓴 것에 주목해라** — `test_상신_승인_입고_순서로_진행된다` 는 중간 상태를 하나씩 확인한다. 마지막만 확인하면 어느 단계에서 어긋났는지 실패 메시지가 말해 주지 않는다.

```python title="tests/test_order_states.py (이어서) — 메커니즘 검증 (표에서 파생시킨다)"
@pytest.mark.parametrize("event", list(OrderEvent), ids=lambda e: e.name)
@pytest.mark.parametrize("status", list(OrderStatus), ids=lambda s: s.name)
def test_표에_있는_조합만_통과하고_나머지는_상태를_바꾸지_않는다(status, event):
    po = order(status)
    if (status, event) in TRANSITIONS:
        po.apply(event)
        assert po.status is TRANSITIONS[status, event]
    else:
        with pytest.raises(InvalidTransition):
            po.apply(event)
        assert po.status is status


def test_거부된_전이는_이력에_남지_않는다():
    po = order()
    with pytest.raises(InvalidTransition):
        po.approve()
    assert po.history == []


def test_이력은_지나온_전이를_순서대로_담는다():
    po = order()
    po.submit()
    po.cancel()
    assert po.history == [
        (OrderStatus.DRAFT, OrderEvent.SUBMIT, OrderStatus.SUBMITTED),
        (OrderStatus.SUBMITTED, OrderEvent.CANCEL, OrderStatus.CANCELLED),
    ]
```

```bash
pytest -q
```

```text nolines
........................................                                 [100%]
40 passed in 0.04s
```

`parametrize` 두 개를 겹치면 곱집합이 만들어져서 30가지가 전부 돈다. **`ids=lambda s: s.name` 을 붙인 것이 실제로 값을 한다** — 안 붙이면 `status0`, `event3` 같은 이름이 나와서 실패해도 어느 조합인지 모른다. `parametrize` 자체는 [6.2](#/pytest-advanced)에 있다.

::: danger 표에서 파생된 테스트는 표의 오류를 절대 못 잡는다
이 전수 테스트는 `TRANSITIONS` 를 읽어서 `TRANSITIONS` 대로 동작하는지 확인한다. **표에 `(APPROVED, REJECT)` 를 실수로 넣어도 이 테스트는 통과한다.** 표가 곧 기대값이기 때문이다.

이 테스트가 증명하는 것은 **메커니즘**뿐이다 — `apply` 가 표를 정확히 따르는가, 거부됐을 때 상태를 안 바꾸는가. 이게 30개나 되니까 커버리지는 예쁘게 나온다. 그 숫자에 속으면 안 된다([12.6](#/test-strategy)).

**요구사항이 표에 옳게 옮겨졌는지는 손으로 쓴 테스트만이 증명한다.** 그래서 앞의 여섯 개가 필요하다. 자동 생성 테스트와 손으로 쓴 테스트는 대체재가 아니라 다른 일을 한다.
:::

이 구분이 말장난이 아니라는 것은 실험으로 확인된다. 누군가 "취소는 언제나 되어야 한다"고 생각해서 `cancel()` 만 `apply` 를 우회하게 고쳤다고 하자.

```python title="purchase/order.py — cancel() 만 이렇게 바꾼다 (조각 — 메서드 본문)"
    def cancel(self) -> None:
        self.status = OrderStatus.CANCELLED   # apply 를 우회했다
```

```text nolines
(pytest -q 출력의 마지막 세 줄)
FAILED tests/test_order_states.py::test_입고된_발주서는_취소할_수_없다 - Fail...
FAILED tests/test_order_states.py::test_이력은_지나온_전이를_순서대로_담는다
2 failed, 38 passed in 0.06s
```

**전수 테스트 30개는 전부 통과했다.** 그것들은 `apply()` 를 직접 부르기 때문이다. 잡은 것은 공개 메서드 `cancel()` 을 부르는 손으로 쓴 테스트 두 개뿐이었다.

여기서 규칙이 하나 더 나온다. **규칙 테스트는 사용자가 실제로 부르는 이름으로 불러라.** 내부 함수를 직접 찌르는 테스트만 있으면, 그 함수를 우회하는 코드가 생겼을 때 아무도 모른다.

::: tip 상태 머신은 README에 그림 세 줄로 적어라
앞의 아스키 다이어그램을 README에 그대로 붙여라. 평가자가 코드를 읽기 전에 **당신의 상태 모델을 30초 만에 이해한다.** 그리고 "허용 전이 7가지 외에는 전부 `InvalidTransition` 으로 거부한다" 한 문장을 붙이면, 표에 없는 조합을 일일이 설명할 필요가 없다. 무엇을 어떻게 적을지는 [12.8](#/readme-submit)에 있다.
:::

## 요약

- 문자열 상태는 **틀렸을 때 예외를 안 낸다.** 오타가 그냥 다른 문자열이 되고, 조건문이 조용히 `False` 가 된다. `Enum` 은 이 실패를 **실행 중에** 잡는다.
- `Enum` 멤버는 **싱글턴**이라 `is` 로 비교할 수 있고, `deepcopy` 로도 복제되지 않는다. 같은 값을 두 번 쓰면 멤버가 조용히 **별칭으로 합쳐지므로** `@unique` 를 붙여라.
- **`auto()` 는 "이 값에는 의미가 없다"는 선언이다.** 값이 프로그램 밖으로 나가면 손으로 적어라. `auto()` 값을 저장하면 **멤버 순서가 곧 데이터 포맷**이 되고, 상태 하나를 중간에 끼우는 순간 저장된 데이터가 다른 뜻이 된다.
- `IntEnum` / `StrEnum` 은 직렬화 편의를 주는 대신 **문자열·정수와 다시 섞인다.** 특히 `IntEnum` 은 **전혀 다른 도메인의 `IntEnum` 과도 `==` 가 참**이다. 기존 API와 섞일 때만 써라.
- **`Flag` 는 상태가 아니라 조합에 쓴다.** 상태에 쓰면 `APPROVED | CANCELLED` 같은 존재할 수 없는 값이 표현 가능해진다.
- **`Enum` 은 값의 집합만 정한다. 상태 머신이 아니다.** 진짜 평가받는 것은 `(상태, 사건) → 상태` 전이 규칙을 코드에 명시했는가, 그리고 표에 없는 조합을 **예외로 막았는가**다.
- 전이가 (상태, 사건) → 상태로 끝나면 **`dict` 표**, 전이마다 하는 일이 다르면 **`match`**. `match` 에서 상수는 반드시 **점이 있는 이름**으로 써라 — 그냥 이름은 비교가 아니라 캡처다.
- **상태 대입은 한 자리에서만 한다.** 그러면 이력·`can()`·종료 상태가 전부 부산물로 나온다. 표에서 파생시킨 전수 테스트는 **메커니즘만** 증명하고, 요구사항이 옳게 옮겨졌는지는 **손으로 쓴 테스트**가 증명한다.
- 상태 머신은 부풀리기 쉽다. **상태별 클래스도, 상태 머신 라이브러리도 이 규모에서는 감점이다.** 표 일곱 줄이 이긴다.

::: quiz 설계 과제 — 읽지 말고 짜고 결정해라
전부 **실제로 코드를 짜고 `pytest` 로 돌려라.** 정답이 하나가 아닌 문제들이다. 판단에는 근거를 한 줄씩 남겨라.

**1. 상태를 골라내라 (설계, 10분)**

아래 요구사항에서 **상태가 되어야 할 것**과 **상태가 아닌 것**을 나눠라. 각각에 대해 `Enum` / `bool` / `Flag` / 그냥 필드 중 무엇으로 표현할지 정하고 이유를 적어라.

> **[과제] 사내 노트북 대여기**
>
> 노트북은 대여 가능, 대여 중, 점검 중, 폐기됨 중 하나의 상태다. 대여하면 대여 중이 되고, 반납하면 점검을 거쳐 대여 가능으로 돌아온다. 점검에서 문제가 발견되면 폐기할 수 있다. 대여 가능한 노트북도 곧바로 점검에 넣을 수 있다. 폐기된 노트북은 어떤 조작도 받지 않는다. 노트북마다 **개발용**, **디자인용**, **회의용** 표시가 붙을 수 있고 **여러 개가 동시에** 붙는다. 노트북에는 자산번호와 모델명이 있다.

**힌트:** 마지막에서 두 번째 문장이 이 절의 어느 도구를 부르는지 봐라.

**2. 전이표를 그리고 세라 (설계, 10분)**

1번의 상태와 사건으로 아스키 전이도를 그리고, **(상태 × 사건) 조합의 총 개수**와 **허용되는 개수**를 세라. 그다음 요구사항에 **답이 안 적힌 조합**을 최소 두 개 찾아내고, 어느 쪽으로 결정할지와 그 이유를 적어라.

> 예: "점검 중인 노트북을 곧바로 대여할 수 있는가?"

**3. 구현하고 전수 테스트를 붙여라 (코드, 40분)**

본문의 안 A(전이표 + `apply` 한 자리)로 구현하고 테스트를 붙여라. 반드시 다음 둘 다 있어야 한다.

- 요구사항 문장을 그대로 옮긴 **손으로 쓴 테스트** (공개 메서드로 호출할 것)
- 전이표에서 파생시킨 **전수 테스트** (`ids=` 를 붙여 실패했을 때 조합을 알 수 있게)

그리고 `pytest -q` 출력을 그대로 옮겨 적어라.

**4. 부수 효과가 붙었다 (설계 판단, 15분)**

요구사항이 하나 늘었다.

> 반납할 때 **반납 일시**를 기록한다. 폐기할 때는 **폐기 사유**를 반드시 받는다.

이제 전이마다 하는 일이 달라졌다. 당신의 표 기반 구현을 어떻게 고칠 것인가. 아래 셋 중 하나를 골라 **실제로 코드로** 짜고, 나머지 둘을 안 고른 이유를 적어라.

- (a) `apply(event, **payload)` 로 인자를 받아 전이 후 분기한다
- (b) 전이표를 `(다음 상태, 후처리 함수)` 로 바꾼다
- (c) 안 B(`match`)로 갈아탄다

**5. 오버엔지니어링을 되돌려라 (판단, 10분)**

누군가 1번 과제를 상태별 클래스 4개(`Available`, `Rented`, `Inspecting`, `Disposed`)와 추상 기반 클래스 하나로 제출했다. 이것을 표 기반으로 줄이고, **줄인 뒤 총 줄 수를 세서 비교해라.** 그다음 이 요구사항에 **어떤 문장 하나가 추가되면** 상태별 클래스가 오히려 유리해지는지 직접 써 봐라.

**6. IntEnum 사고를 재현해라 (코드, 10분)**

`NotebookStatus` 와 `NotebookGrade`(등급 A/B/C)를 **둘 다 `IntEnum` 으로** 만들고, 인자 순서를 바꿔 호출해도 `==` 비교가 참이 되어 조용히 통과하는 함수를 하나 만들어라. 그다음 순수 `Enum` 으로 바꿔 같은 코드가 어떻게 되는지 확인해라. **어느 쪽이 더 빨리 실패하는가**를 한 문장으로 적어라.

**7. 확장 과제 — 도달 불가능한 상태를 찾아라 (코드, 15분)**

전이표를 그래프로 보고, 시작 상태에서 **도달할 수 없는 상태**가 있는지 찾는 함수를 짜라. BFS면 충분하다([7.14](#/bfs-dfs)).

```python
unreachable(TRANSITIONS, start=OrderStatus.DRAFT)   # -> set()
```

그다음 표에서 `(SUBMITTED, APPROVE)` 한 줄을 지우고 다시 돌려 무엇이 나오는지 봐라. **이 검사를 테스트로 만들어 두면 무엇을 막을 수 있는가**를 적어라. 이건 상태가 열 개를 넘는 순간 사람 눈으로는 못 하는 일이다.
:::

**다음 절**: [12.4 경계 설계 — 외부 시스템 끊어내기](#/boundaries-di) — 상태는 잡았으니, 이제 그 상태를 바깥 세계(DB·API·하드웨어)와 어떻게 끊어 놓고 테스트할지를 다룬다.
