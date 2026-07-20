# 2.5 TypedDict, NamedTuple, Literal, Final

::: lead
`dict` 는 편하다. 아무 키나 넣고 아무 값이나 담는다. 그런데 그 자유가 그대로 함정이다. 함수가 `{"name": ..., "age": ...}` 모양의 딕셔너리를 기대하는데 호출자가 `"age"` 를 `"Age"` 로 잘못 써도, 파이썬은 실행이 그 줄에 닿기 전까지 아무 말도 하지 않는다. 이 절은 `dict`, `tuple`, 상수에 **정적으로만** 존재하는 구조를 입히는 네 가지 도구를 다룬다. 그리고 이 챕터 전체를 관통하는 사실 하나를 여기서도 다시 확인한다. **타입 힌트는 런타임에 아무것도 하지 않는다.**
:::

## 문제: dict는 구조를 기억하지 못한다

이런 함수가 있다고 하자.

```python title="user.py"
def greet(user: dict) -> str:
    return f"{user['name']} 님, 안녕하세요 ({user['age']}세)"


greet({"name": "지민", "age": 27})     # 정상
greet({"name": "지민", "Age": 27})     # 오타 — KeyError는 호출 시점에야 터진다
```

`user: dict` 라는 힌트는 "딕셔너리다" 라는 것만 말해줄 뿐, **어떤 키가 있어야 하는지, 값의 타입이 뭔지는 아무것도 말해주지 않는다.** 오타는 `greet` 을 호출하는 순간, 그것도 `user['age']` 에 접근하는 줄에서만 드러난다. 코드 리뷰로 이런 오타를 매번 잡을 수는 없다. [1.6 dict](#/dict)에서 봤듯 dict 자체는 아주 빠르고 유연한 자료구조지만, 그 유연함이 "이 dict는 정확히 이런 모양이어야 한다" 는 계약을 표현하지는 못한다. 그 계약을 타입 검사기가 읽을 수 있는 형태로 적는 것이 `TypedDict` 다.

## TypedDict — dict에 스키마를 얹는다

```python title="typed_user.py"
from typing import TypedDict


class User(TypedDict):
    name: str
    age: int


def greet(user: User) -> str:
    return f"{user['name']} 님, 안녕하세요 ({user['age']}세)"
```

겉보기엔 클래스를 정의하는 것 같지만 `User` 는 **런타임에 존재하는 새 타입이 아니다.** `User({"name": "지민", "age": 27})` 처럼 생성자로 쓰지 않는다. 그냥 평범한 dict 리터럴을 만들고, 그 리터럴이 `User` 모양과 일치하는지는 **타입 검사기가 정적으로 검사**한다.

```text nolines
런타임이 보는 것
   ┌────────────┐
   │    dict    │   <- name, age 키가 있는지 확인 안 함
   └────────────┘

타입 검사기가 보는 것
   ┌────────────┐
   │    User    │   <- name: str, age: int 두 키가 다 있어야 함
   └────────────┘
```

### 핵심 사실: TypedDict는 런타임에 아무것도 검증하지 않는다

말로 하지 말고 직접 깨 보자.

```python title="typed_break.py"
from typing import TypedDict


class Point(TypedDict):
    x: int
    y: int


def show(p: Point) -> None:
    print(p, type(p))


bad: Point = {"x": "hello", "y": [1, 2, 3]}   # x는 int여야 하는데 str, y는 list
show(bad)

worse: Point = {"이건": "완전히", "다른": "구조"}   # 키 자체가 다르다
show(worse)

print(isinstance(bad, dict))
try:
    isinstance(bad, Point)
except TypeError as e:
    print("isinstance 에러:", e)
```

실행 결과다.

```pyrepl
>>> exec(open("typed_break.py", encoding="utf-8").read())
{'x': 'hello', 'y': [1, 2, 3]} <class 'dict'>
{'이건': '완전히', '다른': '구조'} <class 'dict'>
True
isinstance 에러: TypedDict does not support instance and class checks
```

`x` 가 문자열이든, `y` 가 리스트든, 아예 다른 나라 키를 쓰든 **아무 에러도 나지 않는다.** `type(bad)` 는 `Point` 가 아니라 그냥 `dict` 다. `TypedDict` 는 파이썬 타입 시스템이 만든 **가짜 클래스**(pseudo-class)다. `__init__` 도, 인스턴스도, `isinstance` 대상도 아니다. 오직 타입 검사기가 코드를 읽을 때만 의미를 가지는 **주석에 가까운 것**이다. 이건 [1.1 객체, 이름, 참조](#/objects-names)에서 본 원칙의 연장선이다 — 파이썬은 실행 시점에 타입을 강제하지 않는다. `TypedDict` 도 예외가 아니다.

### 그럼 pyright는 뭘 잡아 주는가

같은 코드를 `pyright` 로 검사하면 얘기가 완전히 달라진다.

```bash
uvx pyright typed_break.py
```

```text nolines
typed_break.py:13:14 - error: Type "dict[str, str | list[int]]" is not
  assignable to declared type "Point"
    "Literal['hello']" is not assignable to "int"
    "list[int]" is not assignable to "int" (reportAssignmentType)
typed_break.py:16:16 - error: Type "dict[str, str]" is not assignable
  to declared type "Point"
    "이건" is an undefined item in type "Point"
    "다른" is an undefined item in type "Point" (reportAssignmentType)
typed_break.py:21:21 - error: Second argument to "isinstance" must be
  a class or tuple of classes
    TypedDict class not allowed for instance or class checks
    (reportArgumentType)
3 errors, 0 warnings, 0 informations
```

(`uvx pyright` 1.1.411 기준. 버전이 바뀌면 메시지 문구가 조금 달라질 수 있다.)

이게 바로 이 절의 요점이다. **런타임은 아무 말도 안 하지만, 정적 분석기는 정확히 어느 줄, 어느 키, 어느 타입이 틀렸는지 짚어 준다.** 세 에러는 각각 다른 종류다. 첫 번째는 `x`, `y` 값의 **타입 불일치**(13행), 두 번째는 `Point` 에 없는 **키 이름 자체가 틀린 것**(16행, `이건`/`다른`은 `Point` 가 아는 키가 아니다), 세 번째는 51행에서 이미 실행 시점에 `TypeError` 로 확인한 바로 그 `isinstance(bad, Point)` 를 pyright도 **정적으로 미리** 걸러낸다는 것(21행) — 즉 pyright는 런타임 에러가 나기도 전에 "이 줄은 애초에 타입이 안 맞는다" 고 알려준다. `TypedDict` 의 가치는 실행 중 방어가 아니라 **코드를 작성하는 순간의 피드백**과 **에디터 자동완성**에 있다. `user['nam']` 처럼 오타를 내면 pyright가 그 자리에서 빨간 줄을 긋는다. [2.8 타입체커 실전](#/typecheckers)에서 이걸 CI에 박아 넣는 법을 다룬다.

### total=False, NotRequired, Required

기본적으로 `TypedDict` 의 모든 키는 필수다. 부분적으로만 채워진 dict를 표현하고 싶으면 `total=False` 를 쓴다.

```python title="partial_keys.py"
from typing import TypedDict, NotRequired, Required


class UserPartial(TypedDict, total=False):
    id: int
    name: str


class UserMixed(TypedDict):
    id: int                      # 항상 필수
    nickname: NotRequired[str]   # 있어도 되고 없어도 됨


class UserMixed2(TypedDict, total=False):
    id: Required[int]    # total=False 구역인데 이 키만 다시 필수로
    nickname: str
```

`total=False` 는 클래스 **전체**의 기본 방침을 바꾸고, `NotRequired`/`Required` (3.11+)는 **키 하나 단위**로 그 방침을 뒤집는다. 실제로 확인해 보자.

```pyrepl
>>> u1: UserPartial = {}                 # 키가 하나도 없어도 통과
>>> u2: UserPartial = {"id": 1}          # 일부만 있어도 통과
>>> bad: UserMixed2 = {"nickname": "abc"}  # id가 없다 — Required라서 에러여야 함
```

`bad` 줄을 pyright에 통과시키면 이렇게 잡는다.

```text nolines
demo4b.py:9:19 - error: Type "dict[str, str]" is not assignable to
  declared type "UserMixed2"
    "id" is required in "UserMixed2" (reportAssignmentType)
1 error, 0 warnings, 0 informations
```

`total=False` 를 켠 클래스 안에서도 `Required[int]` 로 표시한 키는 여전히 강제된다는 것, 이게 정확히 검증됐다.

::: cote JSON을 다루는 코드에 TypedDict를 써라
API 응답이나 설정 파일을 파싱한 뒤 `dict` 그대로 여기저기 넘기지 마라. 함수 시그니처마다 `dict[str, Any]` 라고 쓰는 순간 그 함수가 어떤 키를 기대하는지는 함수 본문을 읽어야만 안다. `TypedDict` 로 한 번 선언해 두면 에디터가 키 이름을 자동완성해 주고, 존재하지 않는 키에 접근하면 그 자리에서 빨간 줄이 뜬다. 코딩테스트에서는 크게 중요하지 않지만, 실무 데이터 파이프라인에서는 이게 버그를 가장 많이 줄여 주는 습관이다.
:::

## NamedTuple, namedtuple, dataclass — 셋 다 "필드 이름 있는 튜플/객체"인데 뭐가 다른가

구조화된 데이터를 표현하는 또 다른 축은 "이름 붙은 값 묶음" 이다. 파이썬에는 이걸 만드는 방법이 최소 세 가지 있고, 헷갈리기 딱 좋다.

```python title="세 가지 Point"
from typing import NamedTuple
from collections import namedtuple
from dataclasses import dataclass


class PointNT(NamedTuple):        # ① typing.NamedTuple
    x: int
    y: int = 0


PointClassic = namedtuple("PointClassic", ["x", "y"])  # ② collections.namedtuple


@dataclass                         # ③ dataclasses.dataclass
class PointDC:
    x: int
    y: int = 0
```

실제로 어떻게 다른지 하나씩 찔러 보자.

```pyrepl
>>> p1 = PointNT(1, 2)
>>> p2 = PointClassic(1, 2)
>>> p3 = PointDC(1, 2)
>>> p1, p1.x, p1[0]
(PointNT(x=1, y=2), 1, 1)
>>> p2, p2.x, p2[0]
(PointClassic(x=1, y=2), 1, 1)
>>> p3, p3.x
(PointDC(x=1, y=2), 1)
>>> isinstance(p1, tuple), isinstance(p3, tuple)
(True, False)
>>> p1.x = 99
Traceback (most recent call last):
  ...
AttributeError: can't set attribute
>>> p3.x = 99          # dataclass는 기본적으로 가변이라 조용히 성공
>>> p3
PointDC(x=99, y=2)
```

`PointNT` 와 `PointClassic` 은 **튜플**이다. 인덱스로도 접근되고(`p1[0]`), 언패킹도 되고(`x, y = p1`), **불변**이라 `p1.x = 99` 는 `AttributeError` 를 낸다. `PointDC` 는 평범한 객체다. `isinstance(p3, tuple)` 이 `False` 인 게 그 증거이고, 기본적으로 속성을 자유롭게 바꿀 수 있다(`frozen=True` 를 주면 막을 수 있다 — [2.6 dataclasses](#/dataclasses)에서 자세히 다룬다).

### 정적 타입 검사 지원 여부가 진짜 차이다

`typing.NamedTuple` 과 `collections.namedtuple` 은 런타임에서는 사실상 같은 물건(둘 다 `tuple` 서브클래스를 동적으로 만든다)이지만, **타입 검사기가 다루는 방식은 다르다.**

```python title="필드 오타를 잡을 수 있는가"
class PointNT(NamedTuple):
    x: int
    y: int


PointClassic = namedtuple("PointClassic", ["x", "y"])

p1 = PointNT(1, 2)
p2 = PointClassic(1, 2)

print(p1.z)              # 없는 필드
print(p2.z)               # 이것도 없는 필드
print(p1.x + "문자열")     # 타입 불일치
```

```text nolines
demo5.py:15:10 - error: Cannot access attribute "z" for class "PointNT"
    Attribute "z" is unknown (reportAttributeAccessIssue)
demo5.py:16:10 - error: Cannot access attribute "z" for class "PointClassic"
    Attribute "z" is unknown (reportAttributeAccessIssue)
demo5.py:17:7 - error: Operator "+" not supported for types "int" and
  "Literal['문자열']" (reportOperatorIssue)
3 errors, 0 warnings, 0 informations
```

의외로 `collections.namedtuple` 도 필드 오타를 잡아낸다 — pyright가 `namedtuple` 팩토리 함수를 특별 취급하도록 내장 스텁을 갖고 있기 때문이다. 하지만 이건 **pyright가 봐주는 특수 케이스**일 뿐, `namedtuple` 이 만드는 필드에는 애초에 타입을 적을 방법이 없다(`["x", "y"]` 는 문자열 리스트지 `x: int` 가 아니다). 필드 타입 자체를 명시하고 싶다면 `typing.NamedTuple` 이 유일한 선택지다.

### 메모리도 다르다

```pyrepl
>>> import sys
>>> sys.getsizeof(PointNT(1, 2))
64
>>> sys.getsizeof(PointDC(1, 2))
48
>>> sys.getsizeof({"x": 1, "y": 2})
184
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 **자릿수 차이**는 어디서나 같다.) 같은 정보를 담는 세 가지 방법 중 `dict` 가 가장 무겁다 — 해시 테이블은 키 이름 자체를 저장해야 하기 때문이다. 튜플 계열(`NamedTuple`)은 값만 순서대로 저장하므로 훨씬 가볍고, `dataclass` 는 일반 객체라 `__dict__` 오버헤드가 있지만 여기서는 `slots=True` 없이도 `NamedTuple` 보다 작게 나왔다(3.14에서 `dataclass` 인스턴스 레이아웃이 개선된 결과다). `@dataclass(slots=True)` 를 쓰면 `__dict__` 자체가 없어져 더 줄어든다 — 이건 [2.6 dataclasses](#/dataclasses)에서 실측한다.

### 언제 무엇을 쓰는가

| | `collections.namedtuple` | `typing.NamedTuple` | `@dataclass` |
| --- | --- | --- | --- |
| 베이스 | `tuple` | `tuple` | 일반 객체 |
| 가변성 | 불변 | 불변 | 가변 (기본), `frozen=True`로 불변화 가능 |
| 필드 타입 명시 | 불가 | 가능 | 가능 |
| 인덱싱/언패킹 | 가능 (`p[0]`) | 가능 | 불가 |
| 기본값 | `defaults=` 인자 | `= 값` | `= 값` |
| 메서드 추가 | 상속으로 우회 | 클래스 본문에 직접 | 클래스 본문에 직접 |
| `__eq__`, `__repr__` | 자동 생성 | 자동 생성 | 자동 생성 |

경험칙은 이렇다. **튜플처럼 다뤄야 하고(언패킹, 인덱싱) 절대 안 바뀌어야 하면** `NamedTuple`. **필드가 늘어날 수도 있고, 메서드가 많이 붙고, 상속을 쓰고 싶으면** `dataclass`. `collections.namedtuple` 은 타입 힌트 없이 빠르게 즉석에서 튜플에 이름을 붙일 때만 쓴다 — 새 코드에서는 대부분 `typing.NamedTuple` 이 우월한 선택이다. 이 세 도구 모두 `==` 비교와 `repr` 을 자동으로 만들어 주는데, 그 동작 원리는 [1.14 특수 메서드](#/dunder)에서 다룬 `__eq__`/`__repr__` 자동 생성 규칙과 같다.

## Literal — 문자열 하나 대신 값의 집합을 타입으로 만든다

`str` 타입은 지나치게 넓다. "이 매개변수는 `str` 이지만 실제로는 `"r"`, `"w"`, `"a"` 셋 중 하나만 와야 한다" 는 계약을 `str` 만으로는 표현할 수 없다.

```python title="Literal로 값 집합 제한"
from typing import Literal

Mode = Literal["r", "w", "a"]


def open_file(path: str, mode: Mode) -> None:
    print(f"{path} 을 {mode} 모드로 연다")


open_file("data.txt", "완전히 잘못된 모드")
open_file("data.txt", 123)   # 문자열도 아니다
```

이 코드를 그냥 `python` 으로 실행하면 다음과 같이 **아무 문제 없이 돈다.**

```pyrepl
>>> exec(open("literal_break.py", encoding="utf-8").read())
data.txt 을 완전히 잘못된 모드 모드로 연다
data.txt 을 123 모드로 연다
```

f-string은 어떤 타입이든 `str()` 으로 바꿔서 넣어 줄 뿐, `mode` 가 `Mode` 에 속하는지 검사하지 않는다. 반면 pyright는 정확히 이렇게 잡는다.

```text nolines
demo3.py:12:23 - error: Argument of type "Literal['완전히 잘못된 모드']"
  cannot be assigned to parameter "mode" of type "Mode" in function
  "open_file"
    "Literal['완전히 잘못된 모드']" is not assignable to type "Mode"
      "Literal['완전히 잘못된 모드']" is not assignable to type "Literal['r']"
      "Literal['완전히 잘못된 모드']" is not assignable to type "Literal['w']"
      "Literal['완전히 잘못된 모드']" is not assignable to type "Literal['a']"
      (reportArgumentType)
demo3.py:13:23 - error: Argument of type "Literal[123]" cannot be
  assigned to parameter "mode" of type "Mode" in function "open_file"
    ... (같은 이유로 3줄 더)
```

`Literal` 은 "문자열이면 다 된다" 는 헐거운 계약을 "이 값들 중 하나만 된다" 는 빡빡한 계약으로 바꾼다. `enum.Enum` 과 겹치는 용도지만, `Literal` 은 새 런타임 타입을 만들지 않고 **기존 문자열/숫자/불리언 리터럴 그대로** 쓸 수 있어서 JSON을 다루거나 외부 라이브러리 시그니처를 흉내 낼 때 가볍다. [1.8 제어 흐름과 match 문](#/control-flow)의 구조적 패턴 매칭과 `Literal` 을 같이 쓰면 `match mode: case "r": ...` 각 분기에서 pyright가 **남은 값이 있는지**(exhaustiveness)까지 검사해 줄 수 있다.

## Final — "재할당 금지" 라고 타입 검사기에게만 말한다

`Final` 은 이름이 주는 인상과 실제 동작 사이의 간극이 이 절에서 가장 크다.

```python title="Final은 최종적이지 않다"
from typing import Final


MAX_RETRIES: Final = 3
MAX_RETRIES = 99          # 재할당
print("MAX_RETRIES:", MAX_RETRIES)


class Config:
    VERSION: Final[str] = "1.0"


c = Config()
c.VERSION = "2.0"          # 인스턴스 속성 재할당
print("Config.VERSION:", c.VERSION)
```

```pyrepl
>>> exec(open("final_break.py", encoding="utf-8").read())
MAX_RETRIES: 99
Config.VERSION: 2.0
```

둘 다 **성공적으로 재할당된다.** `Final` 은 `const` 나 `readonly` 같은 언어 차원의 강제가 아니다. "이 이름은 다시 대입되면 안 된다" 는 **약속을, 타입 검사기에게만** 하는 것이다. pyright로 검사하면 정확히 그 약속 위반 두 건을 잡는다.

```text nolines
demo3.py:17:1 - error: "MAX_RETRIES" is declared as Final and cannot
  be reassigned (reportGeneralTypeIssues)
demo3.py:26:3 - error: Cannot assign to attribute "VERSION" for class
  "Config"
    Attribute "VERSION" cannot be assigned through a class instance
    because it is a ClassVar
    "VERSION" is declared as Final and cannot be reassigned
    (reportAttributeAccessIssue)
```

두 번째 에러 메시지를 잘 보면 pyright가 `Config.VERSION` 을 **`ClassVar`** 로도 취급한다는 걸 알 수 있다. 클래스 본문에 `Final[str]` 로 선언된 속성은 인스턴스마다 다른 값을 가지는 게 아니라 클래스 전체가 공유하는 상수라고 간주되기 때문이다. 이건 [1.12 클래스와 데이터 모델](#/classes)에서 다룬 클래스 변수와 인스턴스 변수의 구분과 정확히 맞물린다 — `Final` 을 클래스 본문에 쓰면 "이건 클래스 변수이고, 게다가 아무도 다시 대입해선 안 된다" 는 이중의 의미가 된다.

::: warn Final은 불변을 만들지 않는다
`Final` 이 막는 건 **이름의 재할당**뿐이다. 객체 자체가 가변이면 내용은 얼마든지 바뀐다.

```python
SETTINGS: Final = {"debug": False}
SETTINGS["debug"] = True     # 재할당이 아니라 내용 수정 — 이건 Final도 막지 못한다
SETTINGS = {}                # 이것만 pyright가 잡는다 (재할당)
```

정말 내용까지 못 바꾸게 하려면 애초에 불변 객체를 담아야 한다 — `tuple`, `frozenset`, 또는 `MappingProxyType`. [1.1 객체, 이름, 참조](#/objects-names)에서 다룬 가변/불변의 구분이 여기서도 그대로 적용된다.
:::

::: deep 왜 파이썬은 진짜 상수를 안 만들었나
C++의 `const`, Rust의 불변 기본값처럼 컴파일러(또는 인터프리터)가 재할당을 물리적으로 막는 설계도 가능했다. 파이썬이 그 대신 "타입 검사기만 보는 약속" 을 택한 이유는 [2.1 왜 타입 힌트인가](#/why-typing)에서 다루는 **점진적 타이핑**(gradual typing) 철학과 같다. 타입 힌트 전체가 "기존 런타임 동작을 하나도 바꾸지 않으면서 별도의 도구가 위에서 검사한다" 는 원칙 위에 서 있다. `Final` 을 런타임에서도 강제하려면 이름 대입이라는 파이썬의 가장 근본적인 연산(`=`)에 특별 케이스를 심어야 하는데, 이는 언어를 무겁게 만들고 기존 코드와의 호환성도 깨뜨린다. 대신 파이썬은 "검사는 프로덕션에 배포하기 전에, 별도의 빠른 정적 도구가 한다" 는 쪽을 선택했다.
:::

## 넷을 한 문장으로 정리하면

`TypedDict` 는 **dict**의 구조를, `NamedTuple` 은 **tuple**의 필드 이름과 타입을, `Literal` 은 **값의 집합**을, `Final` 은 **재할당 여부**를 타입 검사기에게 알려주는 도구다. 넷 다 공통점이 하나 있다. **런타임 동작을 조금도 바꾸지 않는다.** 이 넷을 실제 검증 도구로 착각하고 "타입을 이렇게 선언해 뒀으니 잘못된 데이터는 안 들어올 것" 이라고 안심하면 안 된다. 외부 입력(JSON, 사용자 입력, DB 조회 결과)을 실제로 검증하려면 런타임 검사가 필요하고, 그건 [2.7 attrs와 pydantic v2](#/pydantic)가 다루는 영역이다. 이 절의 넷은 **개발 중 실수를 잡아 주는 안전망**이지, **프로덕션 방어벽**이 아니다.

이 구분을 명확히 해 두면 다음 절 [2.6 dataclasses 완전 정복](#/dataclasses)에서 `frozen=True`, `field(default_factory=...)`, `__post_init__` 같은 옵션이 왜 필요한지가 자연스럽게 이어진다 — `dataclass` 는 이 절에서 다룬 정적 안전망 위에 **런타임에도 뭔가를 실행하는** 층을 얹은 도구이기 때문이다.

## 요약

- `dict` 는 어떤 키가 있어야 하는지 스스로 기억하지 못한다. `TypedDict` 는 그 스키마를 타입 검사기에게만 알려주는 **가짜 클래스**다 — 인스턴스도, `isinstance` 대상도 아니다.
- `TypedDict`, `Literal`, `Final` 모두 **런타임 검증을 하지 않는다.** 틀린 값을 넣어도 프로그램은 멀쩡히 돈다. 오직 `uvx pyright`/`uvx mypy` 같은 정적 검사기만 잡아낸다.
- `total=False` 는 클래스 전체의 필수 여부를 바꾸고, `NotRequired`/`Required` (3.11+)는 키 하나 단위로 그걸 뒤집는다.
- `collections.namedtuple` 과 `typing.NamedTuple` 은 런타임에서는 거의 같은 물건(둘 다 불변 튜플)이지만, 필드 타입을 명시할 수 있는 건 `typing.NamedTuple` 뿐이다. `dataclass` 는 튜플이 아니라 일반 객체이고 기본적으로 가변이다.
- `Literal["r", "w", "a"]` 는 `str` 보다 좁은 값의 집합을 표현한다. [1.8 match 문](#/control-flow)의 완전성 검사와 잘 어울린다.
- `Final` 은 재할당만 막겠다는 약속이고, 그마저도 타입 검사기만 안다. 객체 내용물의 가변성은 별개다.
- 이 넷은 개발 중 실수를 잡는 안전망이지 외부 입력을 막는 방어벽이 아니다. 진짜 런타임 검증은 [2.7 pydantic](#/pydantic)에서.

::: quiz 연습문제
1. 다음 `TypedDict` 를 정의하고, 일부러 틀린 타입의 dict를 대입한 뒤 `uvx pyright` 로 검사해 실제 에러 메시지를 확인하라. 그다음 같은 코드를 `python` 으로 실행해 아무 에러도 나지 않는 것을 직접 확인하라.

   ```python
   from typing import TypedDict

   class Task(TypedDict):
       title: str
       done: bool
       priority: int
   ```

2. `collections.namedtuple("P", ["x", "y"])` 로 만든 객체와 `class P(NamedTuple): x: int; y: int` 로 만든 객체 각각에 존재하지 않는 필드로 접근하는 코드를 작성하라. 파이썬 실행 결과와 pyright 검사 결과가 어떻게 다른지 비교하라.

3. 아래 코드에서 `Final` 로 선언한 이름을 재할당하는 줄과, 그 이름이 가리키는 리스트의 **내용**을 바꾸는 줄을 각각 만들어라. `uvx pyright` 가 어느 쪽만 잡는지, 그리고 왜 그런지 설명하라.

   ```python
   from typing import Final

   CACHE: Final = []
   ```

4. `Literal["GET", "POST", "PUT", "DELETE"]` 타입의 매개변수를 받는 함수를 만들고, [1.8 match 문](#/control-flow)의 `match`/`case` 로 네 값을 모두 분기 처리하되 일부러 `"PUT"` 분기를 빠뜨려 보라. pyright의 `reportMatchNotExhaustive` (strict 모드에서)가 이를 잡는지 확인하라.

5. **깊이 생각해 볼 문제.** `TypedDict` 로 선언한 값에 `isinstance(x, MyTypedDict)` 를 호출하면 `TypeError` 가 난다. 반면 `isinstance(x, dict)` 는 잘 동작한다. 이 차이가 `TypedDict` 가 "가짜 클래스" 라는 사실과 어떻게 연결되는지 설명하라.
:::

**다음 절**: [2.6 dataclasses 완전 정복](#/dataclasses) — `field`, `__post_init__`, `frozen`, `slots` 로 이 절의 정적 안전망 위에 실제 동작을 얹는다.
