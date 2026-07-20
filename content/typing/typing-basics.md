# 2.2 타입 문법의 기초

::: lead
[2.1 왜 타입 힌트인가](#/why-typing)에서 타입 힌트가 *"검사기를 위한 문서"* 라는 걸 봤다. 이 절은 그 문서를 쓰는 문법을 다룬다. 그런데 문법보다 먼저 확인해야 할 사실이 있다. **타입 힌트는 인터프리터에게 아무것도 하지 않는다.** 틀린 힌트를 써도 프로그램은 멀쩡히 돈다. 이걸 몸으로 확인하고 나서 문법으로 들어간다.
:::

## 힌트는 장식이다 — 실제로 증명한다

말로만 하지 않는다. 일부러 틀린 타입 힌트를 준 함수를 만들어 보자.

```python title="wrong_hints.py"
def add(a: int, b: int) -> int:
    return a + b


print(add("hello", "world"))
print(add.__annotations__)
```

```pyrepl
>>> add("hello", "world")
'helloworld'
>>> add.__annotations__
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

이 함수는 `int` 를 받아 `int` 를 돌려준다고 **선언**했다. 그런데 문자열 두 개를 넘겼더니 아무 에러 없이 문자열을 이어 붙여 돌려준다. 파이썬 인터프리터는 `a: int` 라는 부분을 **읽지도 않는다.** `+` 연산자는 그저 `a.__add__(b)` 를 호출할 뿐이고, `str.__add__` 는 다른 `str` 을 받으면 신나게 이어 붙인다.

::: danger 타입 힌트를 신뢰의 근거로 쓰지 마라
아래 함수는 인자를 검증하지 않는다. 힌트는 검사기에게 주는 약속일 뿐, **런타임 방어벽이 아니다.**

```python
def transfer(amount: int) -> None:
    print(f"{amount}원 송금")


transfer("전액")     # 아무 에러 없이 실행된다
```

```pyrepl
>>> transfer("전액")
전액원 송금
```

돈, 파일 경로, 사용자 입력처럼 **실제로 검증이 필요한 값**은 `isinstance` 로 직접 확인하거나, 아예 런타임 검증까지 해 주는 [2.7 attrs와 pydantic v2](#/pydantic)의 도구를 써야 한다. 타입 힌트만 믿고 방어 코드를 생략하면 그대로 사고가 난다.
:::

그럼 `a: int` 는 대체 무엇을 하는가? 함수 객체의 `__annotations__` 라는 딕셔너리에 값을 넣어 둘 뿐이다. [1.10 함수](#/functions)에서 본 것처럼 함수도 객체이고, 객체는 속성을 가진다. `__annotations__` 는 그중 하나일 뿐, 실행 경로에 끼어들지 않는다.

::: deep 그럼 누가 이걸 읽는가
`__annotations__` 를 실제로 읽는 주체는 세 부류다.

1. **정적 검사기**(pyright, mypy) — 코드를 실행하지 않고 텍스트로 분석해서 타입 불일치를 찾는다. 이 절 뒤에서 직접 돌려 본다.
2. **런타임 라이브러리** — `dataclasses`, `pydantic`, FastAPI 같은 것들이 `get_type_hints()` 로 어노테이션을 읽어 실제 동작(검증, 직렬화)을 만든다. [2.9 런타임 타입 정보와 리플렉션](#/runtime-typing)에서 다룬다.
3. **당신** — 코드를 읽을 때.

인터프리터 자신은 3번 부류에도 못 낀다. 그냥 무시한다.
:::

## 변수, 함수, 클래스에 다는 문법

기본 문법은 세 군데에서 조금씩 다르다.

```python title="세 가지 어노테이션 자리"
# 변수
count: int = 0
name: str
name = "김철수"        # 대입 없이 선언만 해도 된다

# 함수 — 매개변수와 반환값
def repeat(text: str, times: int) -> str:
    return text * times

# 클래스 — 속성
class Point:
    x: int
    y: int

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
```

`name: str` 처럼 대입 없는 변수 어노테이션은 `__annotations__` 라는 모듈/클래스 수준 딕셔너리에만 기록되고, **이름 자체는 아직 존재하지 않는다.**

```pyrepl
>>> age: int
>>> age
Traceback (most recent call last):
  ...
NameError: name 'age' is not defined
>>> __annotations__
Traceback (most recent call last):
  ...
NameError: name '__annotations__' is not defined. Did you mean: '__annotate__'?
>>> import sys
>>> sys.modules['__main__'].__annotations__
{'age': <class 'int'>}
```

`__annotations__` 를 맨 이름으로 바로 조회하면 되레 `NameError` 가 난다 — Python 3.14가 [PEP 649/749](https://peps.python.org/pep-0649/)로 도입한 **지연 어노테이션 평가** 때문이다. 모듈 최상위 코드는 `LOAD_NAME` 으로 globals 딕셔너리를 직접 뒤지는데, `__annotations__` 는 처음 접근되기 전까지는 그 딕셔너리 안에 아예 없다(내부적으로 `__annotate__` 함수가 호출돼야 채워진다). 대신 `sys.modules['__main__'].__annotations__` 처럼 **모듈 객체의 속성**으로 접근하면 모듈의 `__getattr__` 이 그 시점에 `__annotate__` 를 실행해 값을 만들어 주고, 그 뒤로는 globals()에도 캐시돼 맨 이름으로도 보인다. `age: int` 처럼 대입 없는 어노테이션은 이렇게 딕셔너리에만 기록되고, **이름 자체는 아직 존재하지 않는다.**

이건 [1.1 객체, 이름, 참조](#/objects-names)에서 배운 것과 정확히 들어맞는다. 이름은 객체에 붙는 이름표인데, 어노테이션만 쓰고 대입을 안 하면 **이름표를 걸 객체 자체가 없다.** 타입만 선언하고 실제로 대입은 나중에 하는 상황(클래스 속성 목록 선언 등)에서 이 차이가 중요해진다.

::: cote 코딩테스트에서는 대부분 안 써도 된다
경쟁 프로그래밍 코드에서는 타입 힌트를 생략하는 게 일반적이다. 짧은 스크립트에 문서를 다는 비용이 안 맞기 때문이다. 하지만 함수가 여러 개로 나뉘는 구현 문제(시뮬레이션형)에서는 반환 타입 하나만 달아도 실수를 줄인다.

```python
def solve(grid: list[list[int]]) -> int:
    ...
```
:::

## 내장 제네릭: `list[int]` (3.9+)

파이썬 3.8까지는 `list` 자체에 원소 타입을 표시할 방법이 없어서 `typing.List[int]` 라는 별도 타입을 써야 했다. [PEP 585](https://peps.python.org/pep-0585/)가 이걸 없앴다. 3.9부터는 **내장 타입 자체가 첨자(subscript)를 받는다.**

```pyrepl
>>> list[int]
list[int]
>>> type(list[int])
<class 'types.GenericAlias'>
>>> list[int] == list[int]
True
>>> isinstance([1, 2], list[int])
Traceback (most recent call last):
  ...
TypeError: isinstance() argument 2 cannot be a parameterized generic
```

마지막 줄이 중요하다. `list[int]` 는 **런타임에 존재하는 객체**(`types.GenericAlias`)이지만, `isinstance` 로 "리스트 안의 원소가 전부 int인지" 검사하는 데는 못 쓴다. 그 정보는 애초에 런타임에 검증할 대상이 아니라 **정적 검사기만을 위한 것**이기 때문이다. `list[int]` 를 만들어도 안에 문자열을 넣는 걸 막는 코드는 어디에도 없다.

```pyrepl
>>> nums: list[int] = [1, 2, 3]
>>> nums.append("문자열도 그냥 들어간다")
>>> nums
[1, 2, 3, '문자열도 그냥 들어간다']
```

3.9 이후로는 `dict[str, int]`, `tuple[int, ...]`, `set[str]` 처럼 표준 컬렉션에 전부 이 문법을 쓴다. `typing.List`, `typing.Dict` 는 이제 **레거시**다. 3.9+ 코드에서 새로 쓸 이유가 없다.

| 구식 (3.8 이하, 여전히 동작함) | 현대식 (3.9+) |
| --- | --- |
| `typing.List[int]` | `list[int]` |
| `typing.Dict[str, int]` | `dict[str, int]` |
| `typing.Tuple[int, str]` | `tuple[int, str]` |
| `typing.Set[str]` | `set[str]` |

::: hist 왜 3.9 전에는 안 됐나
`list[int]` 가 동작하려면 `list` 클래스가 `__class_getitem__` 이라는 특수 메서드를 구현해야 한다. 이건 [1.14 특수 메서드 총정리](#/dunder)에서 다루는 프로토콜 중 하나다. 3.9 이전에는 내장 타입들이 이 메서드를 구현하지 않았기 때문에, `typing` 모듈이 **타입 힌트 전용의 가짜 제네릭**(`List`, `Dict`, ...)을 별도로 만들어 제공했다. 3.9에서 내장 타입에 `__class_getitem__` 을 직접 추가하면서 그 대체물이 불필요해졌다.
:::

## `Union` 과 `|` — 같은 뜻, 다른 나이

"이거 아니면 저거"를 표현하는 타입이 `Union` 이다. [PEP 604](https://peps.python.org/pep-0604/)가 3.10부터 `|` 연산자로 같은 걸 쓸 수 있게 했다.

```python title="같은 타입을 두 가지로 쓴다"
from typing import Union


def parse_old(s: str) -> Union[int, float]:
    ...


def parse_new(s: str) -> int | float:      # 3.10+
    ...
```

실측해 보면 흥미로운 사실이 나온다.

```pyrepl
>>> from typing import Union, get_args, get_origin
>>> int | str
int | str
>>> (int | str) == Union[int, str]
True
>>> type(int | str)
<class 'typing.Union'>
```

Python 3.14 기준으로 `int | str` 과 `Union[int, str]` 은 **완전히 같은 객체 취급**을 받는다(`==` 가 `True`). 다만 `type(int | str)` 이 무엇으로 나오는지는 버전마다 다르다. 3.10~3.13에서는 `types.UnionType` 이라는 별개의 클래스였고, 이 책이 기준으로 삼는 3.14.5에서는 `typing.Union` 과 사실상 통합됐다. **이 세부사항에 코드를 의존시키지 마라** — [1.1절](#/objects-names)에서 본 정수 캐싱처럼, 언어 명세가 아니라 구현 디테일이라 버전이 바뀌면 또 달라질 수 있다.

바뀌지 않는 것은 이거다. **3.10 이상이 확실한 코드베이스라면 `|` 를 써라.** `import typing` 없이 쓸 수 있고, 더 짧고, 다른 언어(TypeScript, Kotlin)의 유니온 타입 문법과도 닮았다. `Union[...]` 은 3.9 이하를 지원해야 하는 라이브러리에서만 남는다.

::: warn `|` 를 런타임에도 쓰려면 3.10 이상이 필요하다
어노테이션이 아니라 **실제 값으로** `int | str` 을 평가하려면(`isinstance(x, int | str)` 처럼) 3.10 런타임이 필요하다. 어노테이션 위치에만 쓴다면 [2.9 런타임 타입 정보와 리플렉션](#/runtime-typing)에서 다루는 지연 평가(`from __future__ import annotations`) 덕분에 3.7까지도 문자열로만 저장돼 문제가 없다. 하지만 함수 기본값이나 `isinstance` 인자처럼 **즉시 평가되는 자리**에 쓰면 구버전에서 바로 `TypeError` 가 난다.
:::

## `Optional[X]` 는 `Union[X, None]` 의 별명일 뿐이다

"있거나 없거나"는 아주 흔한 패턴이라 전용 표기가 있다. 그런데 `Optional` 은 새로운 개념이 아니다. **별칭**이다. 추측하지 말고 확인해 보자.

```pyrepl
>>> from typing import Optional, Union
>>> Optional[int]
int | None
>>> Optional[int] == Union[int, None]
True
>>> get_origin(Optional[int])
<class 'typing.Union'>
>>> get_args(Optional[int])
(<class 'int'>, <class 'NoneType'>)
```

`Optional[int]` 를 출력하면 파이썬은 그걸 아예 `int | None` 으로 보여준다. `get_args` 로 뜯어 봐도 정확히 `(int, NoneType)` — `Union[int, None]` 과 원소가 같다. **"Optional"이라는 이름이 주는 착각을 조심해야 한다.** "선택적"이라는 단어 때문에 매개변수를 생략해도 된다는 뜻처럼 들리지만, 그런 뜻이 전혀 아니다. 순수하게 **"이 값이 `None` 일 수도 있다"** 는 뜻이다.

```python title="흔한 오해"
def greet(name: Optional[str]) -> str:
    return "hello " + name


greet()          # ❌ TypeError: 인자를 안 줬다 — Optional과 무관하게 에러
greet(None)      # 힌트상으로는 유효한 호출이지만...
```

두 번째 호출은 함수 시그니처상 **합법**이다. 그런데 함수 몸통은 `None` 을 처리하지 않는다. 검사기를 돌려 보면 바로 이 지점을 잡아낸다(뒤에서 실제로 돌려 본다). `Optional[X]` 를 매개변수에 쓴다는 건 *"당신이 이 매개변수 안에서 `None` 을 확인하는 코드를 짜야 한다"* 는 뜻이다.

```text nolines
              +----------------------+
Optional[X]   |  Union[X, None]      |   <- 완전히 같은 타입, 표기만 다름
              +----------------------+

Union[int, str, None]  ==  Optional[int | str]   (3.10+ 은 int | str | None)
```

## `Callable` — 함수를 값으로 넘길 때

[1.10 함수](#/functions)에서 함수가 일급 객체라는 걸 배웠다. 콜백, 정렬 키, 데코레이터 대상처럼 함수를 인자로 받는 곳에는 `Callable` 로 시그니처를 표시한다.

```python title="Callable[[매개변수들], 반환타입]"
from typing import Callable


def apply_twice(fn: Callable[[int], int], x: int) -> int:
    return fn(fn(x))


def compare(cb: Callable[[int, str], bool], n: int, s: str) -> bool:
    return cb(n, s)
```

`Callable[[int, str], bool]` 을 뜯어 읽으면 이렇다. **대괄호 안의 리스트**는 매개변수 타입 목록, **그 뒤의 마지막 타입**은 반환 타입이다. "int와 str을 받아서 bool을 반환하는 콜러블"이라는 뜻이다.

```pyrepl
>>> compare.__annotations__
{'cb': typing.Callable[[int, str], bool], 'n': <class 'int'>, 's': <class 'str'>, 'return': <class 'bool'>}
```

매개변수 개수나 타입을 신경 쓰지 않고 "아무 콜러블이면 된다"고 할 때는 `Callable[..., int]` 처럼 `...` (Ellipsis)를 쓴다. 매개변수 시그니처 자체를 다른 함수와 맞춰야 하는 정교한 경우(데코레이터가 원본 함수의 시그니처를 그대로 보존해야 할 때)는 `ParamSpec` 이 필요한데, 이건 데코레이터를 본격적으로 다루는 [1.11 데코레이터](#/decorators)와 이어지는 주제라 여기서는 존재만 짚고 넘어간다.

## `Any` — 타입 체크를 끄는 탈출구

`Any` 는 다른 타입들과 성격이 다르다. **"아무 타입이나 된다"** 가 아니라, **"이 값에 대해서는 검사기가 아무것도 확인하지 않는다"** 는 뜻이다. 미묘하지만 결정적인 차이다.

```python title="any_hole.py — 검사기가 눈감아 주는 코드"
from typing import Any


def process(x: Any) -> int:
    return x.존재하지_않는_메서드()      # 오타든 뭐든 통과된다
```

이게 왜 위험한지는 실제로 검사기를 돌려 봐야 실감 난다.

::: perf 실측: pyright가 무엇을 잡고 무엇을 놓치는가
아래 파일에는 일부러 틀린 코드 네 개를 넣었다.

```python title="check_demo.py"
def add(a: int, b: int) -> str:
    return a + b  # 실제로는 int를 반환


from typing import Optional, Callable, Any


def greet(name: Optional[str]) -> str:
    return "hello " + name  # name이 None일 수 있다


def apply(cb: Callable[[int, str], bool], n: int, s: str) -> bool:
    return cb(n, s)


def bad_call() -> bool:
    return apply(lambda n, s: n > 0, "3", "x")  # 첫 인자 타입이 틀림


def any_hole(x: Any) -> int:
    return x.존재하지_않는_메서드()  # Any라서 체크가 꺼진다
```

```bash
uvx pyright check_demo.py
```

실제 출력이다(Python 3.14.5, pyright 최신 버전).

```text
check_demo.py:2:12 - error: Type "int" is not assignable to return type "str"
    "int" is not assignable to "str" (reportReturnType)
check_demo.py:9:12 - error: Operator "+" not supported for types "Literal['hello ']" and "str | None"
    Operator "+" not supported for types "Literal['hello ']" and "None" when expected type is "str" (reportOperatorIssue)
check_demo.py:17:38 - error: Argument of type "Literal['3']" cannot be assigned to parameter "n" of type "int" in function "apply"
    "Literal['3']" is not assignable to "int" (reportArgumentType)
3 errors, 0 warnings, 0 informations
```

**세 개의 에러가 정확히 잡혔다** — 반환 타입 불일치, `Optional` 을 확인 안 하고 쓴 것, `Callable` 인자 타입 불일치. 그런데 **`any_hole` 함수의 존재하지 않는 메서드 호출은 에러 목록에 없다.** 4번째 함수는 조용히 통과했다. `x: Any` 라고 선언하는 순간 pyright는 그 값에 관해 아무것도 확인하지 않기로 약속한 것이다.
:::

`Any` 는 전염된다는 점도 알아야 한다. `Any` 타입 값에 어떤 연산을 해도 결과는 다시 `Any` 다. 그래서 코드베이스 여기저기에 `Any` 를 뿌리면, 타입 검사기를 켜 놓고도 실제로는 아무것도 검사받지 않는 구간이 조용히 넓어진다.

::: warn Any 와 object 를 혼동하지 마라
`object` 는 "모든 타입의 조상"이라는 뜻으로, `object` 타입 값에는 `object` 가 가진 메서드(`__str__`, `__eq__` 등)만 검사기가 허용한다. **진짜로 안전한 선택**이다.

`Any` 는 정반대다. 검사기의 눈을 완전히 감기고 **아무 메서드 호출이든 다 통과**시킨다.

```python
def f(x: object) -> None:
    x.upper()          # ❌ pyright: object에 upper 없음

def g(x: Any) -> None:
    x.upper()          # ✅ 통과 — 진짜 str인지는 런타임에나 안다
```

애매해서 뭘 쓸지 모르겠으면 `Any` 가 아니라 **더 좁은 타입**을 찾아라. 정말 여러 타입을 다 받아야 한다면 `Union` 을, 정해진 메서드만 있으면 되면 [2.4 Protocol과 구조적 서브타이핑](#/protocol-typing)의 `Protocol` 을 써라.
:::

## 타입에도 이름을 붙인다 — 타입 별칭

복잡한 타입 표현을 반복해서 쓰면 가독성이 떨어진다. 그럴 때 타입에 이름을 붙인다. 가장 오래된 방법은 그냥 대입이다.

```python title="전통적인 타입 별칭 — 3.9+에서도 동작"
Vector = list[float]
Matrix = list[list[float]]


def scale(v: Vector, factor: float) -> Vector:
    return [x * factor for x in v]
```

이건 사실 **어노테이션 전용 기능이 아니다.** `Vector` 는 그냥 `list[float]` 을 가리키는 평범한 이름이다. 3.12부터는 [PEP 695](https://peps.python.org/pep-0695/)가 전용 문법을 추가했다.

```pyrepl
>>> type IntList = list[int]
>>> IntList
IntList
>>> type(IntList)
<class 'typing.TypeAliasType'>
>>> IntList.__value__
list[int]
```

`type` 문으로 만든 별칭은 `list[int]` 자체가 아니라 **`TypeAliasType` 이라는 별도의 객체**다. `__value__` 속성으로 실제 타입에 접근할 수 있고, 재귀적인 타입 정의나 지연 평가가 필요한 제네릭 별칭에서 이전 방식보다 유리하다. 이 문법과 제네릭 함수(`def f[T](...)`) 문법은 [2.3 PEP 695: 새 제네릭 문법](#/pep695)에서 제대로 다룬다. 여기서는 **존재와 실측 결과만** 확인해 둔다.

## 요약

- **타입 힌트는 런타임에 아무 효과가 없다.** `add("hello", "world")` 처럼 틀린 힌트를 준 함수도 에러 없이 실행된다. 힌트는 `__annotations__` 딕셔너리에 저장될 뿐이다.
- `list[int]`, `dict[str, int]` 같은 **내장 제네릭**(3.9+)이 `typing.List` 등 구식 표기를 대체했다.
- `int | str` (3.10+)과 `Union[int, str]` 은 같은 타입이다. 3.10 이상이면 `|` 를 써라.
- `Optional[X]` 는 `Union[X, None]` 의 별칭이다. "선택적 매개변수"가 아니라 "`None` 일 수 있는 값"이라는 뜻이다.
- `Callable[[int, str], bool]` 의 대괄호 안은 매개변수 타입 목록, 그 뒤는 반환 타입이다.
- `Any` 는 검사기의 눈을 감긴다. `object` 와 다르다 — 되도록 쓰지 마라.
- `type 별칭 = 값` (3.12+)은 `TypeAliasType` 객체를 만든다. 자세한 문법은 [2.3 PEP 695](#/pep695)에서.

::: quiz 연습문제
1. 다음 함수를 실행하면 무슨 일이 일어나는지 **먼저 예측**하고 실행해서 확인하라. 그리고 `uvx pyright` 로 검사했을 때 몇 개의 에러가 나올지도 예측하라.

   ```python
   def divide(a: int, b: int) -> float:
       return a // b        # 정수 나눗셈인데 반환 타입은 float


   print(divide(7, 2))
   ```

2. `Optional[list[int]]` 와 `list[Optional[int]]` 는 완전히 다른 타입이다. 각각 어떤 값이 유효한지 예를 들어 설명하라.

3. 다음 코드에서 pyright가 에러를 낼 줄과 내지 않을 줄을 구분하라. 실제로 `uvx pyright` 를 돌려 확인하라.

   ```python
   from typing import Any

   def f(x: int) -> int:
       y: Any = x
       return y.upper()     # ?

   def g(x: int) -> int:
       return x.upper()     # ?
   ```

4. `Callable[[int, int], int]` 타입의 매개변수를 받는 함수 `reduce_pair` 를 작성하고, `lambda a, b: a + b` 를 넘겨 호출해 보라. 그다음 매개변수 개수가 다른 람다(`lambda a: a`)를 넘겼을 때 pyright가 뭐라고 하는지 확인하라.

5. `Vector = list[float]` 처럼 대입으로 만든 별칭과 `type Vector = list[float]` 로 만든 별칭의 `type()` 결과를 각각 확인하라. 왜 다른가?
:::

**다음 절**: [2.3 PEP 695: 새 제네릭 문법](#/pep695) — `type` 문과 `def f[T](...)` 로 제네릭 함수와 클래스를 3.12+ 스타일로 쓰는 법.
