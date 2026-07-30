# 12.5 예외와 오류 설계

::: lead
과제형 제출물에서 가장 먼저 무너지는 곳은 성공 경로가 아니다. **실패 경로**다. 좌석이 이미 팔렸을 때, 좌석 코드가 이상할 때, 결제가 거절됐을 때 — 그 세 줄을 어떻게 쓰느냐가 "이 사람과 같이 일할 수 있는가"를 가장 빨리 드러낸다. 예외 문법 자체는 [1.16 예외와 예외 그룹](#/exceptions)에서 끝냈다. 이 절은 문법이 아니라 **판단**이다. 무엇을 예외로 할 것인가, 예외에 무엇을 담을 것인가, 어디서 잡을 것인가. 그리고 어디까지만 설계할 것인가.
:::

## 예약이 실패했는데 티켓이 나왔다

공연 좌석 예약을 만든다. `reserve` 는 성공하면 `True`, 실패하면 `False` 를 돌려준다. 흔한 설계다.

```python title="reserve 가 bool 을 반환한다"
class Hall:
    def __init__(self, codes):
        self.taken = {}          # 좌석 코드 -> 예약자
        self.seats = set(codes)

    def reserve(self, code, customer) -> bool:
        """성공하면 True, 실패하면 False."""
        if code not in self.seats:
            return False
        if code in self.taken:
            return False
        self.taken[code] = customer
        return True


def book_group(hall, codes, customer):
    """일행 좌석을 한꺼번에 잡는다."""
    for code in codes:
        hall.reserve(code, customer)      # 반환값을 안 본다
    return codes


hall = Hall(["A-1", "A-2", "A-3"])
hall.reserve("A-2", "kim")
got = book_group(hall, ["A-1", "A-2", "A-9"], "lee")

print("예약했다고 알려준 좌석:", got)
print("실제 예약 상태      :", hall.taken)
```

```text nolines
예약했다고 알려준 좌석: ['A-1', 'A-2', 'A-9']
실제 예약 상태      : {'A-2': 'kim', 'A-1': 'lee'}
```

`book_group` 은 세 자리를 잡았다고 말했다. 실제로는 하나만 잡았다. `A-2` 는 kim 것이고 `A-9` 는 이 공연장에 없는 좌석이다. **아무 데서도 예외가 나지 않았고, 아무 로그도 남지 않았고, 티켓은 세 장 발권된다.**

`book_group` 이 게을러서 이렇게 됐다고 생각하기 쉽다. 아니다. **`reserve` 가 "무시할 수 있는 실패"를 만들었기 때문**이다. 반환값은 안 봐도 코드가 돌아간다. 이게 이 절의 출발점이다.

> 실패의 표현을 고르는 것은 **"호출자가 이 실패를 무시할 수 있게 할 것인가"** 를 고르는 일이다.

## 실패를 표현하는 네 가지 방법

같은 실패를 네 가지로 써 보고, 호출자가 무엇을 알 수 있는지 비교한다.

```python title="같은 실패, 네 가지 표현"
SEATS = {"A-1", "A-2", "A-3"}
taken = {"A-2": "kim"}


def reserve_bool(code, who):
    if code not in SEATS or code in taken:
        return False
    taken[code] = who
    return True


def reserve_none(code, who):
    if code not in SEATS or code in taken:
        return None
    taken[code] = who
    return code


def reserve_tuple(code, who):
    if code not in SEATS:
        return False, "없는 좌석"
    if code in taken:
        return False, "이미 예약됨"
    taken[code] = who
    return True, ""


class BookingError(Exception):
    pass


def reserve_raise(code, who):
    if code not in SEATS:
        raise BookingError(f"{code}: 없는 좌석")
    if code in taken:
        raise BookingError(f"{code}: 이미 예약됨")
    taken[code] = who
    return code


print("bool :", reserve_bool("A-2", "lee"), "<- 이유를 모른다")
print("None :", reserve_none("A-9", "lee"), "<- 이유를 모른다. 성공값과 타입도 다르다")
ok, why = reserve_tuple("A-2", "lee")
print("tuple:", ok, repr(why), "<- 이유가 문자열이다. 비교하려면 파싱해야 한다")
try:
    reserve_raise("A-2", "lee")
except BookingError as e:
    print("raise:", e, "<- 무시할 수 없다")
```

```text nolines
bool : False <- 이유를 모른다
None : None <- 이유를 모른다. 성공값과 타입도 다르다
tuple: False '이미 예약됨' <- 이유가 문자열이다. 비교하려면 파싱해야 한다
raise: A-2: 이미 예약됨 <- 무시할 수 없다
```

네 방식이 호출자에게 요구하는 것이 전부 다르다.

| 표현 | 실패 이유 | 무시할 수 있나 | 어울리는 자리 |
| --- | --- | --- | --- |
| `bool` | 없다 | 그냥 무시된다 | 실패가 한 종류이고 호출자가 이유를 안 궁금해할 때 |
| `None` | 없다 | 다음 줄에서 `AttributeError` 로 늦게 터진다 | **조회**. "없는 것이 정상"일 때 |
| `(bool, str)` | 문자열 | 언팩을 빼먹으면 튜플이 참으로 평가된다 | 거의 없다. 아래 참고 |
| `raise` | 예외 객체 | **못 한다** | **실행**. 규칙을 어겼을 때 |

`(성공여부, 메시지)` 튜플이 특히 위험하다.

```python
# ❌ 언팩을 빼먹으면 조용히 통과한다. 비어 있지 않은 튜플은 항상 참이다.
if reserve_tuple("A-2", "lee"):
    print("예약 성공")          # 실패했는데 여기가 실행된다
```

::: danger `None` 은 실패를 **다음 줄로 미룬다**
`None` 반환의 진짜 비용은 정보 손실이 아니라 **터지는 위치가 옮겨지는 것**이다.

```python
seat = find_seat(code)      # 못 찾으면 None
print(seat.row)             # AttributeError: 'NoneType' object has no attribute 'row'
```

`AttributeError` 는 `find_seat` 이 아니라 그 다음 줄에서 난다. 함수 세 개를 지나서 터지면 트레이스백만 보고는 원인을 못 찾는다. `None` 을 돌려주려면 **호출자가 반드시 `None` 을 검사할 것**이라는 확신이 있어야 한다. 확신이 없으면 예외다.
:::

## 예외인가 반환값인가

기준을 외우기 전에, **표준 라이브러리가 이미 답을 정해 뒀다**는 것을 보는 게 빠르다.

```pyrepl
>>> seats = {"A-1": "kim"}
>>> seats.get("A-9")
>>> seats["A-9"]
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
KeyError: 'A-9'
>>> "A-1".find("Z")
-1
>>> "A-1".index("Z")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: substring not found
>>> int("A-1")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: invalid literal for int() with base 10: 'A-1'
```

같은 라이브러리가 **둘 다** 제공한다. `get`/`find` 는 "없을 수 있다"는 걸 호출자가 이미 알고 부르는 함수고, `[]`/`index` 는 "있다"는 전제로 부르는 함수다. `int()` 에는 `try_int()` 가 없다 — 문자열을 정수로 바꿔 달라고 했으면 정수가 나와야 하기 때문이다.

여기서 판단 기준 셋이 나온다.

1. **호출자가 이 실패를 예상하고 부르는가.** 예상하면 반환값, 예상 못 하면 예외.
2. **실패가 정상 흐름의 일부인가.** 검색이 빈손인 건 정상이다. 예약 규칙을 어긴 건 정상이 아니다.
3. **호출자가 실패를 무시하면 무슨 일이 생기는가.** 티켓이 잘못 나가면 예외다.

이 셋을 한 문장으로 줄이면 이렇게 된다.

> **조회는 `None` 을 돌려주고, 실행은 예외를 던진다.**

좌석 예약에 그대로 적용한다.

| 함수 | 실패 | 표현 | 왜 |
| --- | --- | --- | --- |
| `holder_of(code)` | 예약자 없음 | `None` | 빈자리인 것이 정상이다 |
| `free_seats()` | 빈자리 없음 | `[]` | 빈 목록이 정확한 답이다 |
| `parse_seat_code(raw)` | 형식 오류 | 예외 | 코드를 달라고 했으면 코드가 나와야 한다 |
| `reserve(codes, who)` | 이미 예약됨 | 예외 | 호출자가 무시하면 이중 예약이 된다 |

::: warn 빈 결과와 실패를 같은 값으로 표현하지 마라
`free_seats()` 가 빈자리 없음도 `[]`, 공연장 코드가 틀린 것도 `[]` 를 돌려주면 호출자는 둘을 구별할 수 없다. **"결과가 없다"와 "질문이 잘못됐다"는 다른 사건이다.** 앞은 빈 컬렉션, 뒤는 예외다.
:::

::: perf "예외는 느리니까 반환값" 은 과제형에서 성립하지 않는다
좌석 코드 10만 건을 파싱하면서, 형식 오류를 예외로 알리는 쪽과 `None` 으로 알리는 쪽을 비교했다. 두 함수 모두 같은 `re.fullmatch` 를 쓰고 차이는 실패 통보 방식뿐이다.

| 실패율 | 예외 | `None` 반환 |
| --- | --- | --- |
| 0% | 44.0 ~ 46.6 ms | 44.5 ~ 45.2 ms |
| 10% | 46.0 ~ 47.7 ms | 41.6 ~ 42.2 ms |
| 100% | 45.0 ~ 46.6 ms | 18.0 ~ 18.7 ms |

(각 값은 7회 반복 중 최솟값, 프로세스를 5번 새로 띄워 얻은 범위. Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**실패가 드물면 차이가 사실상 없다.** 전부 성공할 때는 두 방식이 같고, 10만 건 중 1만 건이 깨져 있어도 **전체에서 4~6 ms** 차이다. 100% 구간에서 역산하면 예외 하나를 만들고 던지고 잡는 데 **0.26~0.29 µs** 가 든다. 과제형 제출물이 다루는 규모에서는 이 숫자가 설계를 바꿀 근거가 되지 못한다.

**차이가 2.5배로 벌어지는 것은 실패율 100%에서뿐이다.** 그리고 그 지점이 진짜 신호다. 실패가 매번 일어난다면 그건 예외적인 사건이 아니라 **정상 흐름**이고, 애초에 예외로 표현할 게 아니었다. 비용 계산의 결론과 설계의 결론이 같은 곳을 가리킨다. 예외 자체의 비용 구조는 [1.16](#/exceptions)의 EAFP/LBYL 측정에 있다.
:::

## 도메인 예외 계층 — 뿌리 하나, 잎 몇 개

예외 클래스를 만드는 이유는 이름이 예뻐서가 아니다. **호출자가 골라서 잡을 수 있게 하려고**다([1.16](#/exceptions)). 그래서 계층은 호출자가 구별하고 싶어 하는 만큼만 판다.

```python title="seatbook/errors.py"
"""이 패키지가 던지는 모든 예외. 호출자가 봐야 할 목록이 여기 한 파일에 다 있다."""


class BookingError(Exception):
    """예약 도메인이 거부한 요청. 호출자가 처리해야 하는 실패는 전부 이 아래에 있다."""


class InvalidSeatCode(BookingError):
    def __init__(self, raw: str) -> None:
        super().__init__(raw)
        self.raw = raw

    def __str__(self) -> str:
        return f"좌석 코드 형식이 아니다: {self.raw!r}"


class UnknownSeat(BookingError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __str__(self) -> str:
        return f"이 공연장에 없는 좌석이다: {self.code}"


class SeatTaken(BookingError):
    def __init__(self, code: str, held_by: str) -> None:
        super().__init__(code, held_by)
        self.code = code
        self.held_by = held_by          # 운영자용. 메시지에는 넣지 않는다

    def __str__(self) -> str:
        return f"이미 예약된 좌석이다: {self.code}"


class SeatLimitExceeded(BookingError):
    def __init__(self, customer: str, limit: int, requested: int) -> None:
        super().__init__(customer, limit, requested)
        self.customer = customer
        self.limit = limit
        self.requested = requested

    def __str__(self) -> str:
        return f"1인 예약 한도 {self.limit}석을 넘는다: {self.requested}석 요청"


class PaymentDeclined(BookingError):
    """결제가 거절됐다. 외부 게이트웨이의 실패를 이 도메인의 말로 옮긴 것."""

    def __init__(self, amount: int, reason: str) -> None:
        super().__init__(amount, reason)
        self.amount = amount
        self.reason = reason

    def __str__(self) -> str:
        return f"결제가 거절됐다({self.amount}원): {self.reason}"
```

여기에 외부 결제 SDK 가 던지는 예외까지 얹으면 그림은 이렇게 된다.

```text nolines
  Exception
    │
    ├── BookingError                <- 우리 도메인이 거부한 것. 진입점에서 잡는다
    │     ├── InvalidSeatCode
    │     ├── UnknownSeat
    │     ├── SeatTaken
    │     ├── SeatLimitExceeded
    │     └── PaymentDeclined
    │
    └── GatewayError                <- 남의 시스템이 실패한 것. 번역하거나 통과시킨다
          ├── CardRejected
          └── GatewayTimeout
```

**깊이는 2다.** 뿌리 하나, 잎 다섯. 이 구조가 호출자에게 주는 것은 정확히 두 가지다.

- 전부 처리하고 싶으면 `except BookingError`.
- 하나만 다르게 처리하고 싶으면 `except SeatTaken`.

### 무엇을 기준으로 나누는가

잎을 몇 개 팔지는 취향이 아니다. 기준이 둘 있고, **둘 중 하나만 만족해도 나눈다.**

1. **호출자가 다르게 반응하는가.** 이미 팔린 좌석은 "다른 자리 추천", 한도 초과는 "장바구니 정리 안내"다. 반응이 다르면 클래스가 다르다.
2. **담는 정보가 다른가.** `SeatTaken` 은 `held_by` 를, `SeatLimitExceeded` 는 `limit` 과 `requested` 를 담는다. 정보가 다르면 클래스가 다르다.

둘 다 아니면 합쳐라. `SeatNotInSectionA`, `SeatNotInSectionB` 같은 클래스는 아무도 구별해서 잡지 않고 담는 정보도 같다. **하나로 합치고 속성으로 구별해라.**

::: note 이름에 `Error` 를 붙일 것인가
PEP 8은 예외 이름에 `Error` 접미사를 권한다. 위 코드는 **뿌리에만** 붙였다. 잎은 `SeatTaken` 처럼 어긴 규칙을 그대로 읽히게 썼다 — `except SeatTaken:` 이 `except SeatTakenError:` 보다 짧게 읽히기 때문이다. [12.3](#/state-machine)의 `PurchaseError` / `InvalidTransition` 도 같은 방식이다.

이건 정답이 있는 문제가 아니다. **팀 규약이 있으면 그것을 따르고, 없으면 한 프로젝트 안에서 일관되기만 하면 된다.** 절반은 `Error` 로 끝나고 절반은 아닌 모듈이 가장 나쁘다.
:::

::: danger `except Exception` 은 도메인 실패와 내 오타를 구별하지 못한다
계층을 잘 파 놓고 잡는 쪽에서 무너지는 경우가 이것이다. 아래는 위 `errors.py` 와 `Hall` 이 이미 있는 상태에서의 조각이다.

```python
def summary(seats):
    return f"{len(seats)}석 / {seats[0]} 부터"


# ❌ 넓게 잡는다
def book_wide(codes, customer):
    try:
        seats = hall.reserve(codes, customer)
        return summary(seat)          # 오타: seat
    except Exception as e:
        return f"예약할 수 없습니다: {e}"


# ✅ 내가 정의한 실패만 잡는다
def book_narrow(codes, customer):
    try:
        seats = hall.reserve(codes, customer)
    except BookingError as e:
        return f"예약할 수 없습니다: {e}"
    return summary(seats)


print("넓게 잡기:", book_wide(["A-1"], "kim"))
print("좌석 상태:", hall.holder_of("A-1"), "<- 예약은 됐다")
print("좁게 잡기:", book_narrow(["A-2"], "lee"))
```

```text nolines
넓게 잡기: 예약할 수 없습니다: name 'seat' is not defined
좌석 상태: kim <- 예약은 됐다
좁게 잡기: 1석 / A-2 부터
```

**좌석은 예약됐는데 사용자에게는 "예약할 수 없습니다"가 나갔다.** 원인은 `NameError`, 즉 내 오타다. `except Exception` 이 그걸 도메인 실패로 둔갑시켰다. 이 버그는 테스트로도 잘 안 잡힌다 — 함수가 예외를 안 내고 문자열을 반환하기 때문이다.

`✅` 쪽은 `try` 블록을 **예외를 낼 수 있는 최소 단위로 좁혔다.** `summary` 를 `try` 밖으로 뺀 것이 핵심이다([1.16](#/exceptions)).
:::

## 예외에 무엇을 담는가

정보를 안 담으면 호출자는 **메시지 문자열을 읽는다.** 그리고 메시지는 반드시 바뀐다.

```python title="메시지를 파싱하는 호출자"
class BookingError(Exception):
    pass


def reserve_v1(code):
    raise BookingError(f"이미 예약된 좌석이다: {code}")


def reserve_v2(code):                     # 다음 스프린트에 문구만 다듬었다
    raise BookingError(f"{code} 좌석은 이미 예약되어 있습니다")


# ❌ 호출자가 메시지를 읽는다
def suggest_alternative(reserve, code):
    try:
        reserve(code)
    except BookingError as e:
        if "이미 예약된" in str(e):
            return "다른 좌석을 추천합니다"
        return "예약할 수 없습니다"
    return "예약 완료"


print("v1:", suggest_alternative(reserve_v1, "A-1"))
print("v2:", suggest_alternative(reserve_v2, "A-1"))
```

```text nolines
v1: 다른 좌석을 추천합니다
v2: 예약할 수 없습니다
```

**문구만 고쳤는데 기능이 죽었다.** 테스트가 메시지를 안 보고 있으면 아무도 모른다. 그래서 예외에는 이렇게 담는다.

- **판단에 쓸 값은 속성으로.** `e.code`, `e.limit`, `e.held_by`.
- **사람이 읽을 문장은 `__str__` 로.** 표시는 표시일 뿐, 계약이 아니다.
- **`super().__init__()` 에는 받은 인자를 그대로.** 이걸 안 지키면 `multiprocessing` 경계에서 피클링이 깨진다. 이유와 사고 사례는 [1.16](#/exceptions)에 있다.

```pyrepl
>>> import pickle
>>> from seatbook.errors import SeatTaken
>>> e = SeatTaken("A-1", "kim")
>>> e.args
('A-1', 'kim')
>>> str(e)
'이미 예약된 좌석이다: A-1'
>>> back = pickle.loads(pickle.dumps(e))
>>> back.code, back.held_by
('A-1', 'kim')
```

::: danger 사용자에게 보여줄 것과 로그에 남길 것을 나눠라
`SeatTaken` 은 `held_by` 를 **속성으로는 갖고 있지만 `__str__` 에는 안 넣었다.** 의도한 것이다.

```python
self.held_by = held_by          # 운영자용. 메시지에는 넣지 않는다

def __str__(self) -> str:
    return f"이미 예약된 좌석이다: {self.code}"
```

`str(e)` 는 그대로 화면에 나가는 경우가 대부분이다. 거기에 **다른 사람의 이름, 내부 파일 경로, SQL, API 키, 스택 정보**가 섞이면 그 자체로 사고다. 과제형에서도 이건 눈에 띈다 — "예외 메시지에 개인정보를 안 넣었네"는 코드 몇 줄로 신뢰를 사는 자리다.

필요한 정보는 사라지지 않았다. 운영자는 `e.held_by` 로 읽고, 로깅 설정은 [6.4](#/logging)에서 다룬다.
:::

## 어디서 잡고 어디서 통과시키는가

가장 흔한 실수는 **함수마다 `try/except` 를 두르는 것**이다. 규칙은 하나다.

> **던지는 곳은 여러 군데, 잡는 곳은 한 군데.**

```text nolines
  hall.py       규칙 위반을 raise 한다. 여기서는 절대 잡지 않는다.
     │
     ▼
  booking.py    외부 예외만 도메인 예외로 번역한다. 도메인 예외는 통과시킨다.
     │
     ▼
  cli.py        여기서 처음이자 마지막으로 잡는다. 종료 코드로 바꾼다.
```

진입점 코드는 이렇게 생긴다.

```python title="cli.py"
import sys

from seatbook.booking import book
from seatbook.errors import BookingError
from seatbook.gateway import CardRejected, GatewayError, GatewayTimeout
from seatbook.hall import Hall


class Gateway:
    """설명용 가짜 게이트웨이. 손님 이름으로 실패를 흉내 낸다."""

    def charge(self, customer, amount):
        if customer == "kim":
            raise CardRejected("INSUFFICIENT_FUNDS")
        if customer == "park":
            raise GatewayTimeout
        return "RCPT-1"


def main(argv: list[str]) -> int:
    hall = Hall(["A-1", "A-2", "A-3"])
    customer, *codes = argv
    try:
        receipt = book(hall, Gateway(), codes, customer, price=30_000)
    except BookingError as e:                 # 사용자가 고칠 수 있는 실패
        print(f"예약할 수 없습니다: {e}", file=sys.stderr)
        return 1
    except GatewayError:                      # 사용자가 못 고치는 실패
        print("결제 시스템에 연결할 수 없습니다. 잠시 후 다시 시도하세요.", file=sys.stderr)
        return 2
    print(f"예약 완료: {' '.join(codes)} / 영수증 {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

```text nolines
$ python cli.py lee A-1 A-2
예약 완료: A-1 A-2 / 영수증 RCPT-1
  종료 코드: 0
$ python cli.py lee A-1 Z-9
예약할 수 없습니다: 이 공연장에 없는 좌석이다: Z-9
  종료 코드: 1
$ python cli.py lee a-1
예약할 수 없습니다: 좌석 코드 형식이 아니다: 'a-1'
  종료 코드: 1
$ python cli.py kim A-1
예약할 수 없습니다: 결제가 거절됐다(30000원): INSUFFICIENT_FUNDS
  종료 코드: 1
$ python cli.py park A-1
결제 시스템에 연결할 수 없습니다. 잠시 후 다시 시도하세요.
  종료 코드: 2
```

`except` 가 두 개뿐이고, **두 개를 가르는 기준이 "사용자가 고칠 수 있는가"** 라는 게 중요하다. 잡는 절의 개수는 예외 클래스 수가 아니라 **대응 방식의 수**로 정해진다. 종료 코드를 나눠 놓으면 채점자가 셸에서 바로 확인할 수 있다([12.8](#/readme-submit)).

::: warn 층마다 잡아서 로그 찍고 다시 던지지 마라
```python
class BookingError(Exception):
    pass


def reserve():
    raise BookingError("이미 예약된 좌석이다: A-1")


def book():
    try:
        reserve()
    except BookingError as e:
        print(f"[log] booking: {e}")
        raise


def handle_request():
    try:
        book()
    except BookingError as e:
        print(f"[log] request: {e}")
        raise


try:
    handle_request()
except BookingError as e:
    print(f"[log] cli: {e}")
    print("사용자에게:", e)
```

```text nolines
[log] booking: 이미 예약된 좌석이다: A-1
[log] request: 이미 예약된 좌석이다: A-1
[log] cli: 이미 예약된 좌석이다: A-1
사용자에게: 이미 예약된 좌석이다: A-1
```

**사건 하나에 로그 세 줄.** 실제 서비스에서 이게 쌓이면 로그로 원인을 못 찾는다. 정보를 더할 게 없으면서 잡았다가 다시 던지는 층은 **없어도 되는 층**이다. 정말로 문맥을 덧붙이고 싶으면 잡지 말고 `e.add_note(...)` 를 쓰는 방법이 있다([1.16](#/exceptions)).
:::

### 경계에서는 번역한다

외부 시스템의 예외를 그대로 위로 올리면, 진입점이 결제 SDK의 예외 이름을 알아야 한다. 그러면 SDK를 바꾸는 순간 `cli.py` 를 고쳐야 한다. **경계에서 우리 말로 옮긴다.**

```python title="seatbook/booking.py"
from .errors import PaymentDeclined
from .gateway import CardRejected, GatewayTimeout
from .hall import Hall


def book(hall: Hall, gateway, codes, customer: str, price: int) -> str:
    """좌석을 잡고 결제한다. 결제가 실패하면 좌석도 풀린다."""
    seats = hall.reserve(codes, customer)
    amount = price * len(seats)
    try:
        return gateway.charge(customer, amount)
    except CardRejected as e:
        hall.release(seats, customer)
        raise PaymentDeclined(amount, e.code) from e
    except GatewayTimeout:
        # 결제가 됐는지 안 됐는지 모른다. 좌석은 풀고, 이 실패는 번역하지 않는다.
        hall.release(seats, customer)
        raise
```

`from e` 가 핵심이다. 번역해도 **원인이 지워지지 않는다.**

```text nolines
seatbook.gateway.CardRejected: INSUFFICIENT_FUNDS

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  ...
  File "seatbook/booking.py", line 14, in book
    raise PaymentDeclined(amount, e.code) from e
seatbook.errors.PaymentDeclined: 결제가 거절됐다(30000원): INSUFFICIENT_FUNDS
```

(경로와 중간 프레임은 줄였다. 체이닝의 내부 동작은 [1.16](#/exceptions)에 있다.)

**무엇을 번역하고 무엇을 통과시키는가.** 위 코드가 둘을 다르게 다룬 이유가 있다.

- `CardRejected` 는 **도메인 사건**이다. 잔액이 부족한 것은 예약 규칙의 일부고, 사용자에게 "결제가 거절됐습니다"라고 말할 수 있다. → 번역한다.
- `GatewayTimeout` 은 **인프라 사건**이다. 사용자가 할 수 있는 게 없고, 우리 도메인의 말로 옮기면 오히려 거짓말이 된다("거절됐다"가 아니라 "모른다"다). → 좌석만 정리하고 그대로 올린다.

::: tip 모르는 것은 모른다고 README에 적어라
타임아웃 뒤에 결제가 실제로 처리됐다면 이 코드는 **좌석은 풀고 돈은 받은 상태**가 된다. 과제형 범위에서 이걸 제대로 풀려면 멱등 키와 조회 API가 필요하다 — 요구사항에 없으면 만들 게 아니다.

대신 이렇게 쓴다.

> **알려진 한계** — 결제 게이트웨이 타임아웃 시 결제 성사 여부를 확인할 수 없어 좌석을 해제한다. 실제 서비스라면 멱등 키를 붙이고 결제 상태 조회로 보정해야 한다.

이 두 줄이 "생각을 안 한 사람"과 "생각하고 범위를 자른 사람"을 가른다([12.1](#/takehome-eval)).
:::

## 실패해도 상태는 그대로여야 한다

예외를 잘 정의해 놓고도 무너지는 지점이 있다. **검사와 변경을 섞어 쓰는 것**이다.

```python title="검사하면서 바꾼다"
class Hall:
    def __init__(self, codes):
        self._holder = {c: None for c in codes}

    def free_seats(self):
        return sorted(c for c, who in self._holder.items() if who is None)

    # ❌ 검사하면서 바꾼다
    def reserve_bad(self, codes, customer):
        for code in codes:
            if self._holder[code] is not None:
                raise RuntimeError(f"이미 예약된 좌석이다: {code}")
            self._holder[code] = customer
        return codes


hall = Hall(["A-1", "A-2", "A-3"])
hall.reserve_bad(["A-3"], "kim")

try:
    hall.reserve_bad(["A-1", "A-2", "A-3"], "lee")
except RuntimeError as e:
    print("거부:", e)

print("남은 자리:", hall.free_seats())
```

```text nolines
거부: 이미 예약된 좌석이다: A-3
남은 자리: []
```

`["A-1", "A-2", "A-3"]` 요청이 `A-3` 에서 거부됐는데 **`A-1`, `A-2` 는 이미 lee 이름으로 잡혔다.** 호출자는 예외를 받았으니 실패한 줄 알고 다시 시도하지 않는다. 그 두 자리는 lee 이름으로 잠긴 채 아무도 안 앉는다. 이런 종류의 버그는 데모에서는 안 보이고 채점자의 두 번째 시나리오에서 보인다.

고치는 방법은 하나다. **다 검사하고, 그 다음에 다 바꾼다.**

```python title="seatbook/hall.py — reserve() 메서드"
    def reserve(self, codes, customer: str) -> list[str]:
        """일행 좌석을 한꺼번에 잡는다. 하나라도 안 되면 아무것도 바뀌지 않는다."""
        codes = list(codes)
        for code in codes:                      # ① 형식 검사
            parse_seat_code(code)

        already = len(self.seats_of(customer))
        if already + len(codes) > self.seat_limit:
            raise SeatLimitExceeded(customer, self.seat_limit, already + len(codes))

        for code in codes:                      # ② 규칙 검사 — 아직 아무것도 안 바꾼다
            if code not in self._holder:
                raise UnknownSeat(code)
            holder = self._holder[code]
            if holder is not None:
                raise SeatTaken(code, holder)

        for code in codes:                      # ③ 여기서만 상태가 바뀐다
            self._holder[code] = customer
        return codes
```

루프를 세 번 도는 게 낭비처럼 보이면, 좌석 수를 생각해 봐라. 일행은 많아야 열 명이다. **여기서 아끼는 것은 시간이 아니라 정확성이다.**

::: note 되돌리는 것보다 안 바꾸는 것이 쉽다
"바꾸다가 실패하면 되돌린다"는 접근(보상 트랜잭션)도 있다. `booking.py` 의 `hall.release(...)` 가 그것이다. 하지만 그건 **외부 시스템이 끼어서 미리 검사할 수 없을 때 쓰는 최후 수단**이다. 내 메모리 안에서 끝나는 일이면 검사를 먼저 해라. 되돌리는 코드는 그 자체가 실패할 수 있고, 그때는 되돌릴 방법이 없다.
:::

### 실패 경로를 테스트한다

성공 경로만 테스트한 제출물은 아주 많다. 실패 경로 테스트가 있으면 그것만으로 눈에 띈다. 무엇을 얼마나 테스트할지는 [12.6](#/test-strategy)에서 본격적으로 다루고, 여기서는 **오류 설계가 테스트에 어떻게 드러나는지**만 본다.

```python title="tests/test_errors.py (일부)"
def test_이미_예약된_좌석은_SeatTaken_으로_거부한다(hall):
    hall.reserve(["A-1"], "kim")

    with pytest.raises(SeatTaken) as exc:
        hall.reserve(["A-1"], "lee")

    assert exc.value.code == "A-1"
    assert exc.value.held_by == "kim"


def test_SeatTaken_메시지는_다른_예약자를_노출하지_않는다(hall):
    hall.reserve(["A-1"], "kim")

    with pytest.raises(SeatTaken) as exc:
        hall.reserve(["A-1"], "lee")

    assert "kim" not in str(exc.value)


def test_실패한_예약은_아무_좌석도_잡지_않는다(hall):
    hall.reserve(["A-3"], "kim")

    with pytest.raises(SeatTaken):
        hall.reserve(["A-1", "A-2", "A-3"], "lee")

    assert hall.seats_of("lee") == []
    assert hall.free_seats() == ["A-1", "A-2", "B-1", "B-2"]


def test_결제가_거절되면_좌석이_풀리고_도메인_예외로_바뀐다(hall):
    gw = FakeGateway(fail=CardRejected("INSUFFICIENT_FUNDS"))

    with pytest.raises(PaymentDeclined) as exc:
        book(hall, gw, ["A-1", "A-2"], "kim", price=30_000)

    assert exc.value.amount == 60_000
    assert exc.value.reason == "INSUFFICIENT_FUNDS"
    assert isinstance(exc.value.__cause__, CardRejected)   # 원인이 지워지지 않았다
    assert hall.free_seats() == ["A-1", "A-2", "A-3", "B-1", "B-2"]
```

```bash
$ uv run --python 3.14 --with pytest pytest -q
.................                                                        [100%]
17 passed in 0.02s
```

네 테스트가 각각 다른 것을 지키고 있다.

1. **예외의 종류와 속성**을 본다. `pytest.raises(BookingError)` 로 뭉뚱그리면 계층을 만든 의미가 없다.
2. **메시지에 들어가면 안 되는 것**을 본다. 정책을 코드로 못 박은 자리다.
3. **실패 후의 상태**를 본다. 예외가 났다는 것만으로는 부족하다.
4. **`__cause__` 가 남아 있는지** 본다. `from e` 를 빠뜨리면 이 줄이 깨진다.

`FakeGateway` 는 실패를 생성자로 주입받는 가짜다. 이런 가짜를 어떻게 세우고 왜 `Protocol` 로 경계를 긋는지는 [12.4](#/boundaries-di)에 있다. 여기서 중요한 건 하나다 — **외부 시스템의 실패를 테스트하려면 실패를 만들어 낼 수 있어야 하고, 그러려면 경계가 끊겨 있어야 한다.**

::: warn `pytest.raises` 는 예외 타입만 확인한다
```python
def test_이미_예약된_좌석은_거부한다(hall):
    hall.reserve(["A-1"], "kim")

    with pytest.raises(BookingError):      # ❌ 어떤 도메인 실패든 통과한다
        hall.reserve(["A-l"], "lee")       # 좌석 코드에 오타. 숫자 1 이 아니라 소문자 l
```

이 테스트는 **초록불이다.** 실제로 난 예외는 `SeatTaken` 이 아니라 `InvalidSeatCode` 인데, 뿌리로 잡았으니 통과한다. 이름은 "이미 예약된 좌석"을 검증한다고 말하지만 아무것도 검증하지 않았다. **잡을 타입은 가장 좁은 것으로 쓰고, 속성이나 `match=` 로 한 겹 더 확인해라.** 반대로 "이 도메인의 모든 실패가 `BookingError` 로 잡히는가"를 확인하는 테스트는 뿌리로 쓰는 게 맞다 — 그게 그 테스트의 명세이기 때문이다.
:::

## 조용히 실패하는 코드

지금까지의 모든 논의가 겨냥하는 하나의 적이 있다. **실패했는데 아무 일도 안 일어난 것처럼 보이는 코드**다. 세 가지 얼굴로 나타난다.

```python title="조용한 실패 3종 (앞의 Hall 과 errors.py 를 그대로 쓴다)"
# ❌ ① 예외를 삼킨다
def book_quiet(codes, customer):
    try:
        return hall.reserve(codes, customer)
    except Exception:
        pass


# ❌ ② 실패를 기본값으로 덮는다
def seat_price(grade):
    prices = {"VIP": 150_000, "R": 100_000}
    return prices.get(grade, 0)


# ❌ ③ 실패를 로그로만 남긴다
def book_logged(codes, customer):
    try:
        return hall.reserve(codes, customer)
    except BookingError as e:
        print(f"  [log] 예약 실패: {e}")
    return []
```

```text nolines
① 반환값 : None  좌석 상태: kim
② 등급 오타 'R석' 의 가격: 0 원
  [log] 예약 실패: 이미 예약된 좌석이다: A-1
③ 발권 매수: 0 장 — 호출자는 성공한 줄 안다
```

- **①** 은 `None` 을 돌려주고 끝난다. 함수 시그니처만 보면 좌석 목록이 나올 것 같은데 `None` 이 나온다.
- **②** 가 가장 교활하다. 오타 하나에 **가격이 0원**이 된다. 예외도 없고 로그도 없다. `dict.get(k, 0)` 은 "없으면 0으로 세는" 집계에는 맞지만 **가격표 조회에는 틀린 도구**다. 여기서는 `prices[grade]` 로 `KeyError` 를 내는 게 맞다.
- **③** 은 로그를 남겼으니 괜찮아 보인다. 아니다. **호출자는 여전히 성공한 줄 안다.** 로그는 사람이 나중에 읽는 것이고, 프로그램의 흐름을 바꾸지 못한다.

::: danger `except: pass` 를 정당하게 쓸 수 있는 경우는 거의 없다
정말로 무시해도 되는 실패가 있긴 하다. 임시 파일 정리, 캐시 삭제 같은 것들이다. 그럴 때도 `pass` 로 두지 말고 **무시한다는 사실을 코드에 적어라.**

```python
# ✅ 무엇을, 왜 무시하는지 좁혀서 밝힌다
with contextlib.suppress(FileNotFoundError):
    tmp.unlink()          # 이미 지워졌으면 그만이다
```

`contextlib.suppress` 는 **예외 타입을 명시하도록 강제한다**는 점에서 `except: pass` 보다 낫다([1.17](#/context-managers)). 무엇을 무시하는지 못 적겠으면, 그건 무시하면 안 되는 것이다.
:::

## 모든 오류를 한 번에 보여 달라고 하면

여기까지의 결론은 "실행 경로의 실패는 예외"였다. 그런데 요구사항이 이렇게 오면 이야기가 달라진다.

> 예약 요청 폼을 검증해 **어긴 규칙을 모두** 사용자에게 보여 준다.

예외는 **첫 번째 실패에서 멈춘다.** 좌석 코드 오타를 고쳐 다시 냈더니 이번엔 "이미 예약됨"이 나오고, 또 고쳤더니 "없는 좌석"이 나온다. 사용자는 세 번 왕복한다.

두 가지 안을 나란히 놓는다.

**안 A — 예외 그대로.** 첫 실패에서 멈추고 그것만 보여 준다. 코드가 늘지 않는다. 사용자는 왕복한다.

**안 B — 규칙 검사를 예외 목록으로 뽑는다.** 규칙은 한 군데 두고, 던질지 모을지는 호출자가 고른다.

```python title="안 B — 규칙은 한 군데, 표현은 두 가지"
class ReviewedHall(Hall):
    def problems_with(self, codes, customer) -> list[BookingError]:
        """어긴 규칙을 전부 모아 돌려준다. 던지지는 않는다."""
        problems: list[BookingError] = []
        for code in codes:
            try:
                parse_seat_code(code)
            except InvalidSeatCode as e:
                problems.append(e)
                continue
            holder = self.holder_of(code)
            if code not in self._holder:
                problems.append(UnknownSeat(code))
            elif holder is not None:
                problems.append(SeatTaken(code, holder))

        total = len(self.seats_of(customer)) + len(codes)
        if total > self.seat_limit:
            problems.append(SeatLimitExceeded(customer, self.seat_limit, total))
        return problems

    def reserve(self, codes, customer):
        codes = list(codes)
        problems = self.problems_with(codes, customer)
        if problems:
            raise problems[0]                 # 실행 경로는 여전히 예외다
        for code in codes:
            self._holder[code] = customer
        return codes
```

```text nolines
예약 실행 경로가 보는 것: 좌석 코드 형식이 아니다: 'a-1'
검증 화면이 보는 것:
   - [InvalidSeatCode] 좌석 코드 형식이 아니다: 'a-1'
   - [SeatTaken] 이미 예약된 좌석이다: A-1
   - [UnknownSeat] 이 공연장에 없는 좌석이다: C-9
상태는 그대로: ['A-2', 'A-3']
```

**예외 객체를 던지지 않고 리스트에 담았다는 것**이 요점이다. 규칙 코드가 두 벌 생기지 않았고, 검증 화면과 실행 경로가 같은 판단을 공유한다.

| | 안 A (예외만) | 안 B (검사 분리) |
| --- | --- | --- |
| 코드량 | 그대로 | 메서드 하나, 15줄쯤 |
| 사용자 왕복 | 오류 수만큼 | 한 번 |
| 규칙의 진실 | 한 군데 | 한 군데 (분리해도 안 갈라진다) |
| 검사와 실행 사이 | — | 그 사이에 남이 좌석을 채 갈 수 있다 |

**요구사항에 "모든 오류를 함께 표시"가 있으면 안 B, 없으면 안 A다.** 마지막 행이 중요하다 — `problems_with` 가 통과했다고 `reserve` 가 성공한다는 보장은 없다. 그래서 `reserve` 는 **검사 결과를 신뢰하지 않고 자기가 다시 검사한다.** LBYL 로 미리 물어봤다고 EAFP 를 생략하면 안 되는 이유가 이것이다([1.16](#/exceptions)).

::: warn 파이썬에 `Result` 타입을 들여오지 마라
`Result`/`Either` 라이브러리를 설치하고 모든 함수의 반환 타입을 `Result[Seat, BookingError]` 로 바꾸고 싶어질 수 있다. 러스트나 하스켈에서 왔다면 특히 그렇다.

과제형에서는 하지 마라. 이유는 취향이 아니다.

- **표준 라이브러리가 예외를 쓴다.** `int()`, `open()`, `dict[]` 가 전부 예외를 던진다. 경계마다 변환 코드가 생긴다.
- **의존성이 하나 늘어난다.** 채점자가 `pip install` 을 한 번 더 해야 한다([12.1](#/takehome-eval)).
- **읽는 사람이 멈춘다.** 파이썬 코드를 읽으러 온 사람이 모나드 문법을 만난다.

정말 필요하면 위의 `problems_with` 처럼 **평범한 리스트**로 충분하다.
:::

## 과하게 설계하지 않는 선

오류 설계는 재미있어서 부풀리기 쉬운 주제다. 그리고 과제형에서 오버엔지니어링은 가산점이 아니라 **감점**이다([12.1](#/takehome-eval)). 실제로 자주 보이는 과잉을 모아 둔다.

```python title="❌ 좌석 예약 과제에 등장한 오류 프레임워크 (스케치)"
class ErrorSeverity(IntEnum):
    INFO = 1
    WARNING = 2
    CRITICAL = 3


class ErrorCode(StrEnum):
    SEAT_TAKEN = "E1001"
    SEAT_UNKNOWN = "E1002"
    ...                              # 열두 개


class BookingError(Exception):
    def __init__(self, code, severity, retryable, context=None, cause=None):
        ...

class SeatTakenError(BookingError): ...
class SeatTakenInVipSectionError(SeatTakenError): ...
class SeatTakenAfterHoldExpiredError(SeatTakenError): ...
```

무엇이 잘못됐는지는 요구사항을 보면 안다. **요구사항에 에러 코드도, 재시도도, 심각도 분류도 없었다.** 이건 오류 설계가 아니라 오류 프레임워크를 만든 것이고, 채점자가 읽어야 할 코드만 세 배가 됐다.

과잉을 감지하는 신호는 이렇다.

| 신호 | 뜻 |
| --- | --- |
| 예외 클래스인데 아무도 따로 잡지 않고, 담는 정보도 같다 | 상위로 합쳐라 |
| 예외에 `severity`, `error_code`, `retryable` 이 있다 | 요구사항에 그 단어가 있었는지 확인해라 |
| `try/except` 가 함수마다 있다 | 잡는 자리를 아직 안 정했다 |
| 잡아서 다른 예외로 바꾸기만 하는 층이 있다 | 그 층은 지워라 |
| 예외 계층 깊이가 3을 넘는다 | 잡는 쪽에서 그 깊이를 쓰지 않는다 |
| 예외 클래스 수가 요구사항의 규칙 수보다 많다 | 없는 실패를 상상해서 만들었다 |

::: tip 적정선을 재는 한 문장
**예외 클래스 하나를 추가할 때마다, 그 클래스를 `except` 로 따로 잡는 코드나 `pytest.raises` 로 따로 확인하는 테스트를 같이 만들 수 있는지 물어봐라.** 둘 다 못 만들겠으면 그 클래스는 아직 필요 없다.

이 절의 `seatbook` 은 잎이 다섯이다. `cli.py` 는 다섯을 구별하지 않지만(`except BookingError` 하나로 받는다) **테스트가 다섯을 구별하고, 각 클래스가 서로 다른 속성을 담는다.** 그래서 다섯이 정당하다. 만약 다섯 개가 전부 `code` 하나만 담고 테스트도 뭉뚱그려 잡았다면, 그건 클래스 하나로 충분했다는 뜻이다.
:::

::: cote 알고리즘 코딩테스트에서는 이 절을 전부 잊어라
제한 시간 안에 정답만 맞히면 되는 시험장에서 도메인 예외 계층을 설계하는 것은 순수한 손해다. 거기서 예외는 **설계 대상이 아니라 디버깅 신호**다 — `IndexError` 가 났다는 것은 경계 검사가 틀렸다는 뜻이고, 그 자리를 찾는 방법은 [11.14](#/exam-debug)에 있다. 두 시험은 평가 기준이 반대다. **무엇을 평가받는 자리인지 먼저 판단해라.**
:::

## 요약

- 실패의 표현을 고르는 것은 **호출자가 그 실패를 무시할 수 있게 할 것인가**를 고르는 일이다. `bool` 과 `None` 은 무시된다.
- **조회는 `None`, 실행은 예외.** 표준 라이브러리가 `dict.get`/`dict[]`, `str.find`/`str.index` 로 이미 그렇게 갈라 놨다.
- **"예외는 느리다"는 과제형 규모에서 판단 근거가 아니다.** 10만 건을 파싱하며 1만 번 실패해도 차이는 4~6 ms 다. 실패율이 100%에 가까워야 배수가 벌어지는데, 그 지점이면 애초에 예외가 아니라 정상 흐름이다.
- 도메인 예외는 **뿌리 하나 + 잎 몇 개, 깊이 2**로 충분하다. 나누는 기준은 **호출자가 다르게 반응하는가**와 **담는 정보가 다른가** 둘뿐이다.
- **예외에는 판단할 값을 속성으로 담고, 사람이 읽을 문장은 `__str__` 로 분리해라.** 메시지를 파싱하는 호출자가 생기면 문구 수정이 기능 장애가 된다. 그리고 남의 개인정보를 `__str__` 에 넣지 마라.
- **던지는 곳은 여러 군데, 잡는 곳은 한 군데.** 진입점에서만 잡고, 경계에서는 `raise ... from e` 로 번역한다. 도메인 사건은 번역하고 인프라 사건은 통과시켜라.
- **다 검사하고 그 다음에 다 바꿔라.** 검사와 변경이 섞이면 거부된 요청이 상태를 절반 바꿔 놓는다.
- `except Exception`, `except: pass`, `dict.get(k, 0)` — **조용한 실패 셋을 외워라.** 특히 `except Exception` 은 내 오타를 도메인 실패로 둔갑시킨다.
- **오류 프레임워크를 만들지 마라.** 예외 클래스를 추가할 때마다 그것을 따로 잡는 코드나 테스트를 함께 만들 수 있는지 물어라.

::: quiz 설계 과제 — 읽지 말고 짜고 결정해라
소재는 **주차장 정산기**다. 이 절의 좌석 예약 코드를 그대로 옮기지 말고, 아래 요구사항에서 다시 판단해라.

> ① 차량은 `12가3456` 형식의 번호로 식별한다. ② 입차하면 입차 시각이 기록된다. ③ 출차할 때 요금을 계산해 정산한다. ④ 요금은 최초 30분 1,000원, 이후 10분마다 500원이다. ⑤ 정기권 차량은 요금이 0원이다. ⑥ 결제는 외부 카드 단말기 SDK 를 호출한다. ⑦ 만차면 입차를 거부한다.

**1. 실패를 분류해라 (코드 없이, 표로).**
아래 일곱 가지 실패 각각에 대해 `예외` / `None` / `빈 컬렉션` / `기본값` 중 하나를 고르고, **한 줄로 근거**를 적어라. 근거에 "관례상"을 쓰지 마라.

1. `find_ticket("12가3456")` — 입차 기록이 없다
2. `enter("12가3456")` — 이미 입차해 있다
3. `enter("12가3456")` — 만차다
4. `parse_plate("12가")` — 번호 형식이 아니다
5. `fee(minutes=-5)` — 음수 시간
6. `exit_and_pay(...)` — 카드 단말기가 응답하지 않는다
7. `list_parked_cars()` — 주차된 차가 한 대도 없다

**2. 예외 계층을 코드로 써라.**
`errors.py` 한 파일. 클래스마다 **어떤 호출자가 그것만 따로 잡는지**를 독스트링에 한 줄로 적어라. 못 적는 클래스는 지워라. 완성한 뒤 클래스 개수를 세고, 그 숫자가 요구사항의 규칙 수를 넘지 않는지 확인해라.

**3. 원자성을 깨뜨려 봐라.**
`exit_and_pay(plate)` 를 **일부러 틀리게** 짜라 — 정산 기록을 먼저 지우고 결제를 나중에 호출하는 순서로. 그리고 결제가 거절되는 가짜 단말기를 주입해 **차는 나갔는데 돈은 안 받은 상태**를 재현하는 pytest 테스트를 써라. 테스트가 실패하는 것을 눈으로 본 뒤에 순서를 고쳐 통과시켜라.

**4. 경계를 번역해라.**
카드 단말기 SDK 가 `TerminalBusy`, `CardDeclined`, `TerminalOffline` 세 가지를 던진다고 하자. 각각을 **번역할 것 / 통과시킬 것**으로 나누고, 진입점의 `except` 절이 **최대 세 개를 넘지 않게** 설계해라. 나눈 기준을 README 형식의 한 문단으로 적어라.

**5. 이 절의 코드에 남은 구멍을 찾아라.**
`Hall.reserve(["A-1", "A-1"], "kim")` 처럼 **같은 좌석이 두 번 들어오면** 어떻게 되는가. 직접 돌려서 확인해라. 이것을 실패로 볼 것인가, 조용히 중복 제거할 것인가, 아니면 요구사항에 없으니 그대로 둘 것인가. **셋 중 하나를 고르고 근거를 한 문장으로 적어라.** 정답은 없다. 근거 없는 선택만 오답이다.
:::

**다음 절**: [12.6 테스트 전략 — 무엇을 얼마나](#/test-strategy) — 실패 경로까지 테스트했으면, 이제 무엇을 **안 테스트할지** 정할 차례다.
