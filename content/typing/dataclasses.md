# 2.6 dataclasses 완전 정복

::: lead
클래스 하나에 필드가 세 개만 있어도 `__init__`, `__repr__`, `__eq__` 를 손으로 쓰는 순간 코드는 로직보다 보일러플레이트가 더 길어진다. `@dataclass` 는 이 세 메서드를 **어노테이션에서 자동 생성**하는 데코레이터다. 그런데 정확히 무엇을 만들어 주는지, 왜 가변 기본값을 함수처럼 방치하지 않는지, `frozen`이 정말 객체를 통째로 얼리는지는 소스를 까 보지 않으면 절반은 짐작으로 남는다. 이 절에서는 실제로 생성된 코드를 들여다보고, 함정을 실측하고, 타입 힌트가 이 모든 과정에서 정확히 어떤 역할(과 무역할)을 하는지 증명한다.
:::

## 손으로 쓴 클래스의 문제

3차원 벡터 하나만 표현해 보자.

```python title="수작업 클래스"
class Vector:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"Vector(x={self.x!r}, y={self.y!r}, z={self.z!r})"

    def __eq__(self, other):
        if not isinstance(other, Vector):
            return NotImplemented
        return (self.x, self.y, self.z) == (other.x, other.y, other.z)
```

필드 3개에 코드 12줄. 필드가 늘어날 때마다 세 메서드를 동시에 고쳐야 하고, 하나라도 빠뜨리면 `print(v)` 가 `<Vector object at 0x...>` 를 뱉거나 `v1 == v2` 가 항상 `False` 를 반환하는 조용한 버그가 된다. 같은 클래스를 `@dataclass` 로 쓰면 이렇다.

```python title="dataclass 버전"
from dataclasses import dataclass


@dataclass
class Vector:
    x: float
    y: float
    z: float
```

이게 전부다. `Vector(1, 2, 3) == Vector(1, 2, 3)` 이 `True` 이고 `repr` 도 나온다. 마법처럼 보이지만 마법이 아니다. 실제로 무엇이 생겼는지 확인해 보자.

## 무엇이 실제로 생성되는가

```pyrepl
>>> import inspect
>>> inspect.signature(Vector.__init__)
<Signature (self, x: float, y: float, z: float) -> None>
>>> inspect.getsource(Vector.__init__)
Traceback (most recent call last):
  ...
OSError: could not get source code
```

`getsource` 가 실패한다. **파일 어디에도 이 코드가 텍스트로 존재하지 않기 때문**이다. `@dataclass` 는 소스 문자열을 `exec()` 로 즉석 컴파일해서 메서드를 만든다. 그 흔적은 코드 객체의 파일명에 남는다.

```pyrepl
>>> Vector.__init__.__code__.co_filename
'<string>'
>>> Vector.__eq__.__code__.co_filename
'<string>'
```

`dis` 로 실제 바이트코드를 보면 손으로 쓴 것과 다르지 않다.

```pyrepl
>>> import dis
>>> dis.dis(Vector.__init__)
  2           RESUME                   0
  3           LOAD_FAST_BORROW_LOAD_FAST_BORROW 16 (x, self)
              STORE_ATTR               0 (x)
  4           LOAD_FAST_BORROW_LOAD_FAST_BORROW 32 (y, self)
              STORE_ATTR               1 (y)
  ...
```

(3.14 기준. 바이트코드 명령 이름은 버전마다 달라질 수 있지만 `self.x = x` 3줄이 `STORE_ATTR` 3번으로 컴파일된다는 사실은 동일하다.)

`__repr__` 은 조금 더 흥미롭다.

```pyrepl
>>> Vector.__repr__.__code__.co_filename
'C:\\...\\Lib\\reprlib.py'
```

`reprlib.py`라니 이상하지 않은가? `@dataclass` 는 생성한 `__repr__` 을 그냥 두지 않고 `reprlib.recursive_repr()` 로 한 번 감싼다. 자기 자신을 참조하는 객체를 만들어 보면 이유가 보인다.

```pyrepl
>>> @dataclass
... class Node:
...     val: int
...     nxt: object = None
...
>>> n = Node(1)
>>> n.nxt = n              # 순환 참조
>>> repr(n)
'Node(val=1, nxt=...)'      # 무한 재귀 대신 '...'
```

보호 장치가 없었다면 `repr(n)` 이 `n.nxt` 의 repr을 부르고 그게 다시 `n` 의 repr을 부르는 무한 루프에 빠졌을 것이다. 순환 참조는 [1.1 객체·이름·참조](#/objects-names)에서 본 참조 카운팅의 맹점과 같은 종류의 문제다 — 여기서는 GC가 아니라 `recursive_repr` 이 해결한다.

## 타입 힌트는 정말 아무 일도 안 한다

Part II의 전제를 여기서 직접 증명한다. `Vector` 의 필드는 `float` 라고 선언했다. 정수나 문자열을 넣으면 어떻게 될까.

```python title="wrong_type.py"
from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int


p = Point(1, "oops")     # y에 str을 넣었다
print(p)                 # 실행된다. 아무 예외도 없다.
print(type(p.y))
```

```text nolines
Point(x=1, y='oops')
<class 'str'>
```

**에러가 없다.** `@dataclass` 가 생성한 `__init__` 은 `self.y = y` 를 실행할 뿐, `y`가 `int`인지 검사하는 코드는 단 한 줄도 없다. 타입 힌트는 인터프리터에게 전달되는 순간 그냥 버려지는 메타데이터다.

이걸 잡는 건 인터프리터가 아니라 별도로 실행하는 정적 검사기다. 위 파일을 그대로 pyright와 mypy에 넣으면 이렇게 나온다.

```bash
$ uvx pyright wrong_type.py
```
```text nolines
wrong_type.py:10:14 - error: Argument of type "Literal['oops']" cannot be
  assigned to parameter "y" of type "int" in function "__init__"
    "Literal['oops']" is not assignable to "int" (reportArgumentType)
1 error, 0 warnings, 0 informations
```

```bash
$ uvx mypy wrong_type.py
```
```text nolines
wrong_type.py:10: error: Argument 2 to "Point" has incompatible type "str";
  expected "int"  [arg-type]
Found 1 error in 1 file (checked 1 source file)
```

같은 파일, 같은 줄, 같은 결론을 두 검사기가 독립적으로 낸다. 하지만 `python wrong_type.py` 로 직접 실행하면 둘 다 관여하지 않고 방금 봤듯 조용히 통과한다. **타입 힌트 → 정적 검사기가 읽어서 오류를 낸다 / 런타임 → 아예 무시된다.** 이 둘은 완전히 분리된 세계다. 검사기 실전 활용은 [2.8 mypy와 pyright 실전](#/typecheckers)에서 깊이 다룬다.

::: note dataclass는 어노테이션을 "읽긴" 한다 — 검사는 아니다
`@dataclass` 가 예외처럼 보이는 지점이 하나 있다. 데코레이터는 클래스 본문의 어노테이션을 **문자열로 스캔**해서 `typing.ClassVar` 나 `dataclasses.InitVar` 로 시작하는 것을 찾아낸다. 이렇게 표시된 필드는 `__init__` 파라미터에서 제외되거나(`ClassVar`) 인스턴스에 저장되지 않는다(`InitVar`).

```pyrepl
>>> from typing import ClassVar
>>> @dataclass
... class Counter:
...     name: str
...     total_created: ClassVar[int] = 0
...
>>> [f.name for f in dataclasses.fields(Counter)]
['name']              # total_created는 필드가 아니다
```

이건 **타입 검사가 아니다.** `ClassVar` 라는 이름 자체를 신호로 쓰는 것뿐이다. `y: int` 가 `int` 를 강제하지 않는 것과 똑같이, `ClassVar[int]` 도 `int` 부분은 그냥 장식이다. 데코레이터가 관심 있는 건 오직 "이게 `ClassVar` 로 시작하는가" 뿐이다.
:::

## `field(default_factory=)` — 가변 기본값을 원천 차단한다

[1.1절](#/objects-names)과 [1.10 함수](#/functions)에서 이미 만난 함정이다. 함수의 기본값은 정의 시점에 딱 한 번 평가되므로, 가변 객체를 기본값으로 쓰면 모든 호출이 같은 객체를 공유한다. `@dataclass` 에서 똑같은 실수를 하면 무슨 일이 벌어질까.

```pyrepl
>>> from dataclasses import dataclass, field
>>> @dataclass
... class Bad:
...     items: list = []
...
Traceback (most recent call last):
  ...
ValueError: mutable default <class 'list'> for field items is not allowed:
use default_factory
```

**함수는 조용히 버그를 심지만, `@dataclass` 는 클래스 정의 시점에 즉시 예외를 던진다.** `list`, `dict`, `set` 처럼 알려진 가변 타입을 기본값으로 감지하면 아예 클래스 생성을 막는다. 함수의 기본값 함정보다 한 단계 더 안전하게 설계된 것이다. 올바른 방법은 팩토리 함수를 넘기는 것이다.

```pyrepl
>>> @dataclass
... class Good:
...     items: list = field(default_factory=list)
...
>>> a, b = Good(), Good()
>>> a.items.append(1)
>>> a.items, b.items, a.items is b.items
([1], [], False)
```

`default_factory` 로 넘긴 `list` 는 **인스턴스를 만들 때마다 새로 호출**된다. `__init__` 안에서 `self.items = list()` 를 매번 실행하는 것과 같다. 커스텀 클래스의 인스턴스가 필요하면 `field(default_factory=MyClass)` 처럼 아무 인자 없이 호출 가능한 것이면 뭐든 넘길 수 있다.

## `__post_init__` — 생성 직후 검증과 파생 값 계산

`@dataclass` 가 만드는 `__init__` 은 필드를 그대로 대입하는 것 이상을 모른다. 값 검증이나 다른 필드로부터 계산해야 하는 필드가 있으면 `__post_init__` 이 자동 호출된다.

```python title="post_init.py"
@dataclass
class Rectangle:
    width: float
    height: float
    area: float = field(init=False)   # __init__ 인자에서 제외

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width, height must be positive")
        self.area = self.width * self.height
```

```pyrepl
>>> r = Rectangle(3, 4)
>>> r.area
12
>>> Rectangle(-1, 2)
Traceback (most recent call last):
  ...
ValueError: width, height must be positive
```

`field(init=False)` 는 "이 필드는 생성자 인자로 받지 않는다"는 뜻이다. 대신 `__post_init__` 안에서 직접 채운다. 생성자에만 필요하고 인스턴스에는 남기고 싶지 않은 값이 있다면 `InitVar` 로 선언해 `__post_init__` 의 인자로만 받을 수도 있다.

## `frozen=True` — 불변 객체 만들기

[1.1절](#/objects-names)에서 본 가변/불변 분류를 떠올려 보자. 사용자 정의 클래스는 기본적으로 **가변**이다. `frozen=True` 는 그 분류를 뒤집는다.

```pyrepl
>>> @dataclass(frozen=True)
... class Point:
...     x: int
...     y: int
...
>>> p = Point(1, 2)
>>> p.x = 10
Traceback (most recent call last):
  ...
dataclasses.FrozenInstanceError: cannot assign to field 'x'
```

내부적으로는 `object.__setattr__` 을 가로채는 `__setattr__` 하나를 더 생성해서 모든 대입을 막는 것뿐이다. `__post_init__` 안에서 파생 값을 계산해 넣어야 한다면 `self.x = ...` 대신 `object.__setattr__(self, "x", ...)` 로 우회해야 한다 — frozen 클래스는 자기 자신의 `__init__`·`__post_init__` 안에서도 예외가 아니다.

::: warn frozen은 얕다
`frozen=True` 는 **필드 재대입**을 막을 뿐, 필드가 가리키는 객체까지 불변으로 만들지 않는다.

```pyrepl
>>> @dataclass(frozen=True)
... class Basket:
...     items: list
...
>>> b = Basket([1, 2, 3])
>>> b.items.append(4)      # 필드 재대입이 아니라 내부 객체 변경
>>> b.items
[1, 2, 3, 4]                # 막지 못한다
>>> b.items = [9]           # 이건 막힌다
Traceback (most recent call last):
  ...
dataclasses.FrozenInstanceError: cannot assign to field 'items'
```

진짜 불변 객체를 원하면 필드 타입 자체를 불변으로 골라야 한다 — `list` 대신 `tuple`, `dict` 대신 `types.MappingProxyType` 이나 `frozenset`. `frozen`은 "이 이름표는 못 바꾼다"이지 "이 객체는 안 바뀐다"가 아니다.
:::

### frozen과 해시

`==` 를 정의한 객체를 `set`이나 `dict`의 키로 쓰려면 `__hash__` 가 필요하다. `@dataclass` 는 `eq`와 `frozen` 조합에 따라 해시를 다르게 처리한다. 실제로 만들어지는 걸 조합별로 확인해 보자.

| `eq` | `frozen` | `__hash__` | 의미 |
| --- | --- | --- | --- |
| `True` (기본) | `False` (기본) | `None` | 해시 불가 — `set`/`dict` 키로 못 씀 |
| `True` | `True` | 필드 기반으로 생성 | 해시 가능 |
| `False` | 무관 | `object.__hash__` 상속 | 정체성 기반 해시 |

```pyrepl
>>> @dataclass
... class A: x: int
...
>>> A.__hash__ is None
True
>>> {A(1)}
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'A'
```

이유는 명확하다. **해시 가능한 객체는 존재하는 동안 해시값이 바뀌면 안 된다** ([1.6 dict](#/dict)의 해시 테이블 불변식). 가변 객체에 `__eq__` 만 정의하고 해시를 자동 생성하면, 필드를 바꾼 뒤 `set`에 넣었을 때 그 객체를 다시 찾을 수 없는 사고가 난다. 그래서 `@dataclass` 는 "값으로 비교하면서 동시에 가변"인 조합에서는 아예 해시를 죽여 버린다. `frozen=True` 로 값이 안 바뀐다고 보장해야 비로소 해시를 만들어 준다. 정말 위험을 감수하고 가변 객체에 해시를 강제하고 싶다면 `unsafe_hash=True` 로 명시해야 한다 — 이름 자체가 경고다.

## `slots=True` — 메모리 실측

`__slots__` 를 직접 선언하는 방법은 [1.12 클래스와 데이터 모델](#/classes)에서 다뤘다. `@dataclass(slots=True)`(3.10+)는 그걸 자동화한 것이다. 필드 2개짜리 클래스로 직접 재 보자.

```python title="slots_bench.py"
import dataclasses, tracemalloc


@dataclasses.dataclass
class Node:
    x: int
    y: int


@dataclasses.dataclass(slots=True)
class NodeS:
    x: int
    y: int


def per_instance(cls, n=30):
    warm = [cls(1, 2) for _ in range(n)]     # 키 공유 구조를 먼저 자리잡힌다
    tracemalloc.start()
    objs = [cls(i, i) for i in range(n)]
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del objs, warm
    return current / n - 8                    # 리스트 포인터 8B 제외


print("regular:", per_instance(Node))
print("slots  :", per_instance(NodeS))
```

```text nolines
regular: 88.5
slots  : 48.5
```

(Python 3.14.5 / Windows 실측. [1.12절](#/classes)에서 같은 방식으로 잰 값과 일치한다 — 필드 2개에서 일반 88B, `__slots__` 48B.) `slots=True` 는 `__dict__` 를 아예 만들지 않고 필드마다 고정 오프셋을 배정한다. 대량으로 실측해도 방향은 같다.

```text nolines
50만 개 인스턴스 tracemalloc 실측
  regular dataclass: 64.16 MB (128.3 B/개)
  slots   dataclass: 44.16 MB ( 88.3 B/개)
  절감 비율: 1.45배
```

절감폭은 필드 개수와 무관한 고정 오버헤드에서 나오므로, 필드가 많아질수록 비율은 1에 가까워진다. 자세한 이유는 [1.12절](#/classes)의 키 공유·인라인 값 설명을 참고하라.

::: warn slots과 클래스 변수 기본값은 공존 못 한다
직접 쓴 `__slots__` 와 마찬가지로, `slots=True` 클래스는 상속·다중 상속·`weakref`·`cached_property`에서 같은 제약을 그대로 물려받는다. 단 `field(default_factory=...)` 는 문제없다 — 클래스 변수가 아니라 `__init__` 안에서 호출되기 때문이다.

```pyrepl
>>> @dataclass(slots=True)
... class OK:
...     items: list = field(default_factory=list)
...
>>> OK()
OK(items=[])
```

문제가 되는 건 "`x = 5`" 처럼 **클래스 변수로 직접** 기본값을 주는 옛날 `__slots__` 관용구뿐이다. `@dataclass`는 필드 기본값을 클래스 변수가 아니라 `__init__` 매개변수의 기본값으로 넣으므로 이 문제 자체가 생기지 않는다. `직접 `__slots__` 를 쓰기보다 `@dataclass(slots=True)` 를 쓰라`는 [1.12절](#/classes)의 권고가 여기서 확인된다.
:::

## `kw_only` — 위치 인자 실수를 막는다

필드가 5개, 6개로 늘어나면 `Config(True, False, 3, "utf-8", None)` 같은 호출은 무엇이 무엇인지 코드만 봐서는 알 수 없다. `kw_only=True` 는 모든 필드를 키워드 전용으로 만든다.

```pyrepl
>>> @dataclass(kw_only=True)
... class Config:
...     debug: bool
...     retries: int
...
>>> Config(True, 3)
Traceback (most recent call last):
  ...
TypeError: Config.__init__() takes 1 positional argument but 3 were given
>>> Config(debug=True, retries=3)
Config(debug=True, retries=3)
```

필드 단위로도 지정할 수 있다. `field(kw_only=True)` 를 개별 필드에 붙이면 그 필드부터만 키워드 전용이 되고, 나머지는 위치 인자를 허용한다. 이건 필드에 기본값이 있는 게 뒤섞여 있을 때 특히 유용하다 — 기본값 없는 필드가 기본값 있는 필드보다 먼저 와야 한다는 일반 규칙을, `kw_only` 필드는 순서와 무관하게 우회한다.

## `order=True` — 비교 연산자 생성

기본 `@dataclass` 는 `==`, `!=` 만 만든다. 정렬이 필요하면 `order=True` 를 켠다.

```pyrepl
>>> @dataclass(order=True)
... class Card:
...     rank: int
...     suit: str
...
>>> cards = [Card(3, "spade"), Card(1, "heart"), Card(2, "club")]
>>> sorted(cards)
[Card(rank=1, suit='heart'), Card(rank=2, suit='club'), Card(rank=3, suit='spade')]
```

비교는 필드를 선언한 순서대로 튜플처럼 이뤄진다 — 먼저 `rank`, 같으면 `suit`. 특정 필드를 비교에서 빼고 싶으면 `field(compare=False)` 를 쓴다. `compare=False` 인 필드는 `__eq__`와 정렬 메서드 양쪽에서 모두 무시된다. 캐시나 로그처럼 "값의 일부가 아닌" 필드에 붙이면 된다.

## 자주 쓰는 유틸리티

`dataclasses` 모듈은 인스턴스를 다루는 함수도 함께 제공한다.

```pyrepl
>>> p1 = Point(1, 2)   # frozen 버전
>>> p2 = dataclasses.replace(p1, x=99)   # 새 인스턴스, 일부 필드만 교체
>>> p1, p2
(Point(x=1, y=2), Point(x=99, y=2))
>>> dataclasses.asdict(p1)
{'x': 1, 'y': 2}
>>> dataclasses.astuple(p1)
(1, 2)
```

`replace` 는 frozen 객체를 "수정"하는 표준 방법이다 — 실제로는 새 객체를 만든다. [1.1절](#/objects-names)의 원칙 그대로다. 불변 객체를 바꾸는 모든 연산은 새 객체를 만드는 것이지 제자리 수정이 아니다.

## 요약

- `@dataclass` 는 `exec()` 로 `__init__`/`__repr__`/`__eq__` 를 즉석 생성한다. 소스는 존재하지 않고(`co_filename == '<string>'`) `getsource` 도 실패한다.
- `__repr__` 은 `reprlib.recursive_repr()` 로 감싸져 순환 참조에서 무한 재귀 대신 `...` 를 출력한다.
- 타입 힌트는 런타임에서 완전히 무시된다. 틀린 타입을 넣어도 예외 없이 실행된다 — 잡는 건 `uvx pyright`/`uvx mypy` 같은 정적 검사기뿐이다. `ClassVar`/`InitVar` 인식은 예외처럼 보이지만 이름 자체를 신호로 쓰는 것이지 타입 검사가 아니다.
- 가변 기본값(`items: list = []`)은 함수와 달리 클래스 정의 시점에 `ValueError` 로 즉시 차단된다. `field(default_factory=list)` 로 우회한다.
- `frozen=True` 는 필드 재대입만 막는다. 내부 가변 객체까지 얼리지 않는다. `eq=True`와 `frozen=True`가 함께일 때만 해시가 자동 생성된다.
- `slots=True`(3.10+)는 `__dict__` 를 없애 인스턴스당 고정 오버헤드를 줄인다(실측 88.5B → 48.5B, 필드 2개 기준). 직접 `__slots__` 를 쓸 때의 제약(상속, weakref, cached_property)을 그대로 물려받되 기본값 문제는 없다.
- `kw_only`, `order`, `compare=False` 로 호출 안전성과 정렬 가능성을 제어한다.
- `dataclasses.replace`/`asdict`/`astuple` 로 인스턴스를 다룬다. `replace`는 항상 새 객체를 만든다.

::: quiz 연습문제
1. 다음 클래스가 `TypeError: unhashable type` 없이 `set`에 들어가려면 무엇을 바꿔야 하는가? 두 가지 서로 다른 방법을 제시하라.

   ```python
   @dataclass
   class Tag:
       name: str
   ```

2. 아래 코드를 실행한 결과를 예측한 뒤 실제로 실행해 확인하라. 그리고 `uvx pyright` 로도 검사해서 정적 검사기가 뭐라고 하는지 비교하라.

   ```python
   @dataclass
   class Money:
       amount: int
       currency: str = "KRW"

   m = Money("천원", 100)
   print(m)
   ```

3. `field(default_factory=list)` 대신 `field(default_factory=lambda: [1, 2, 3])` 을 쓸 수 있는가? 왜 되는지, 되지 않는 경우가 있다면 무엇인지 설명하라.

4. `frozen=True` 인 클래스의 `__post_init__` 안에서 `self.total = self.x + self.y` 를 실행하면 무슨 일이 일어나는가? 실행해서 확인하고, 이걸 우회하는 방법을 찾아라.

5. **깊이 생각해 볼 문제.** `@dataclass(eq=False)` 인 클래스는 `frozen=True` 를 줘도 해시가 필드 기반으로 바뀌지 않는다. 왜 이게 합리적인 기본값인지, `eq`와 `hash`가 어떤 계약 관계에 있는지 설명하라. ([1.14 특수 메서드](#/dunder)의 `__eq__`/`__hash__` 관계를 참고하라.)
:::

**다음 절**: [2.7 attrs와 pydantic v2](#/pydantic) — dataclass가 못 하는 런타임 검증과 직렬화를 어떻게 채우는가.
