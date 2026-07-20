# 2.4 Protocol과 구조적 서브타이핑

::: lead
[1.15 프로토콜](#/protocols)에서 ABC의 진짜 정체를 봤다. `ABCMeta` 가 돌리는 캐시, 훅, 등록부 — 전부 **런타임 기계**다. 그런데 그 절 마지막에 이상한 문장이 있었다. "Protocol의 진짜 힘은 타입 체커의 영역이다." 이 절은 그 약속을 지킨다. `typing.Protocol` 은 ABC와 겉모습이 비슷하지만 태생이 다르다. **기본적으로 아무 런타임 검사도 하지 않는다.** `isinstance` 조차 거부한다. 그런데도 이게 파이썬 타입 시스템에서 가장 실용적인 도구 중 하나인 이유를 끝까지 파헤친다.
:::

## 먼저: 타입 힌트는 코드가 아니라 주석이다

Part II를 시작하기 전에 반드시 눈으로 봐야 할 사실이 있다. **타입 힌트는 런타임에 아무 일도 하지 않는다.**

```python title="exp1_no_runtime_effect.py"
def add(a: int, b: int) -> int:
    return a + b


print(add("hello", "world"))
print(add.__annotations__)
```

```text nolines
helloworld
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

`int` 라고 써 놓고 문자열 두 개를 넘겼는데 그대로 실행됐고, 심지어 결과까지 나왔다. 인터프리터는 `a: int` 를 보고 아무것도 검사하지 않는다. `__annotations__` 라는 딕셔너리에 값을 채워 넣을 뿐이다. [1.1 객체, 이름, 참조](#/objects-names)의 언어로 말하면, 어노테이션은 이름에 붙는 또 하나의 **메모**지 객체의 정체성이나 실제 능력을 바꾸는 장치가 아니다.

이제 같은 코드를 정적 검사기에 넘겨 보자.

```bash
uvx pyright exp1_no_runtime_effect.py
```

```text nolines
exp1_no_runtime_effect.py:5:11 - error: Argument of type "Literal['hello']"
  cannot be assigned to parameter "a" of type "int" in function "add"
    "Literal['hello']" is not assignable to "int" (reportArgumentType)
exp1_no_runtime_effect.py:5:20 - error: Argument of type "Literal['world']"
  cannot be assigned to parameter "b" of type "int" in function "add"
    "Literal['world']" is not assignable to "int" (reportArgumentType)
2 errors, 0 warnings, 0 informations
```

pyright는 실행하지 않고도 잘못을 잡는다. 코드를 **실행**하는 파이썬 인터프리터와, 코드를 **읽기만** 하는 pyright는 완전히 분리된 두 세계다. 이 절 전체가 그 분리 위에서 성립한다. `Protocol` 은 그 갈라진 두 세계 사이에서 벌어지는 일이다.

## Protocol은 기본적으로 정적 전용이다

`typing.Protocol` (PEP 544, 2017)로 앞서 [1.15](#/protocols)의 `CloseableProto` 를 다시 만들어 보자.

```python title="exp2_structural.py"
from typing import Protocol


class SupportsClose(Protocol):
    def close(self) -> None: ...


class Door:
    def close(self) -> None:
        print("문 닫음")


class FileLike:
    def close(self) -> None:
        print("파일 닫음")


def shut(x: SupportsClose) -> None:
    x.close()


shut(Door())
shut(FileLike())
print(issubclass(Door, SupportsClose))
```

앞의 세 줄은 실행된다. `Door` 와 `FileLike` 는 `SupportsClose` 를 상속한 적도, 들어 본 적도 없다. 그런데 마지막 줄에서 터진다.

```text nolines
문 닫음
파일 닫음
Traceback (most recent call last):
  ...
TypeError: Instance and class checks can only be used with @runtime_checkable protocols
```

**`Protocol` 을 그냥 정의하면 `isinstance` 도 `issubclass` 도 못 쓴다.** ABC는 최소한 `__subclasshook__` 이 없어도 상속과 등록으로 `isinstance` 가 항상 작동했다. `Protocol` 은 그 기본 통로 자체가 막혀 있다. 이게 우연이 아니다. **`Protocol` 은 타입 체커가 읽으라고 만든 것이지, 인터프리터가 검사하라고 만든 게 아니다.** `shut(Door())` 가 성공한 이유도 런타임 검사를 통과해서가 아니다. **애초에 아무 검사도 없었다.** `x.close()` 를 그냥 불렀고 `Door` 에 `close` 가 있어서 됐을 뿐이다 — 어노테이션이 없어도 똑같이 성공했을 코드다.

pyright에게는 완전히 다른 이야기다.

```bash
uvx pyright exp2_structural.py
```

```text nolines
exp2_structural.py:24:24 - error: Second argument to "issubclass" must be a class or tuple of classes
  Protocol class must be @runtime_checkable to be used with instance and class checks
  (reportArgumentType)
```

pyright는 `shut(Door())` 와 `shut(FileLike())` 두 줄에는 아무 말이 없다. **정적으로도 문제가 없기 때문이다.** `Door` 와 `FileLike` 는 `close(self) -> None` 을 갖고 있으니 `SupportsClose` 의 모양에 맞는다. 상속 관계는 물어보지 않았다.

## 구조적 타이핑이란 무엇인가

여기서 이 절의 핵심 개념이 나온다.

> **구조적 타이핑(structural typing)**: 타입 호환 여부를 "무엇을 상속했는가"가 아니라 "무엇을 갖고 있는가"로 정한다.

[1.13 상속, MRO, 컴포지션](#/inheritance)에서 다룬 상속 관계, 그리고 ABC의 등록부(1.15)는 전부 **명목적 타이핑**(nominal typing)이다. `A` 가 `B` 의 서브타입이려면 코드 어딘가에 `class A(B)` 나 `B.register(A)` 라는 **선언**이 있어야 한다. 선언이 곧 계약이고, 그 계약은 **타입을 정의하는 쪽**이 쓴다.

`Protocol` 은 정반대다. `SupportsClose` 를 만족하는 데 필요한 건 `close(self) -> None` 이라는 **모양**뿐이다. `Door` 를 짠 사람은 `SupportsClose` 라는 이름을 들어본 적조차 없어도 된다. 계약은 **그 타입을 쓰는 쪽**이 나중에 마음대로 만든다. [1.15](#/protocols)에서 이미 이 문장을 봤다 — 여기서 실제로 어떻게 동작하는지를 본 것이다.

이 방향이 실전에서 왜 중요한가는 함수에서 가장 잘 드러난다. **함수는 클래스가 아니라서 애초에 무엇을 상속할 수가 없다.**

```python title="함수도 구조적으로는 그냥 하나의 타입이다"
from typing import Protocol
import functools


class Comparator(Protocol):
    def __call__(self, a: int, b: int) -> int: ...


def sort_with(data: list[int], cmp: Comparator) -> list[int]:
    return sorted(data, key=functools.cmp_to_key(cmp))


def by_value(a: int, b: int) -> int:      # 평범한 함수. 상속할 대상이 없다
    return a - b


print(sort_with([3, 1, 2], by_value))
```

```text nolines
[1, 2, 3]
```

pyright도 통과한다. `by_value` 가 `Comparator` 의 인스턴스일 방법은 없다 — 함수는 `function` 타입의 인스턴스지 사용자 클래스의 인스턴스가 아니다. `Protocol` 은 그 질문 자체를 안 한다. `__call__(self, a: int, b: int) -> int` 라는 시그니처만 맞으면 함수든, 람다든, `__call__` 을 구현한 객체든 전부 같은 자격이다. **ABC로는 이걸 할 수 없다.** 함수 객체를 사용자 정의 ABC에 `register` 할 방법이 없기 때문이다.

## @runtime_checkable — 이름만 본다, 시그니처는 안 본다

`isinstance` 를 꼭 써야 한다면 `@runtime_checkable` 을 붙인다. 그런데 이걸 붙이면 무엇을 검사하게 되는지 실측으로 확인해야 한다.

```python title="exp3_runtime_checkable.py"
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None: ...


class Door:
    def close(self) -> None:
        print("문 닫음")


class WrongSignature:
    def close(self, force: bool) -> None:      # 인자가 하나 더 있다
        print("강제로 닫음" if force else "닫음")


class NotEvenCallable:
    close = 42                                  # 메서드가 아니라 정수다


print("Door:", isinstance(Door(), SupportsClose))
print("WrongSignature:", isinstance(WrongSignature(), SupportsClose))
print("NotEvenCallable:", isinstance(NotEvenCallable(), SupportsClose))
```

```text nolines
Door: True
WrongSignature: True
NotEvenCallable: True
```

**셋 다 `True` 다.** `close(self, force: bool)` 처럼 인자 개수가 다른 것도 통과하고, `close = 42` 처럼 메서드조차 아닌 것도 통과한다. `runtime_checkable` 은 `getattr(x, "close", None) is not None` 과 크게 다르지 않다 — **속성 이름의 존재만** 확인하고 콜러블인지, 시그니처가 맞는지는 전혀 보지 않는다. 실제로 불러 보면 바로 드러난다.

```python title="이어서 실행"
w = WrongSignature()
w.close()             # TypeError: close() missing 1 required positional argument: 'force'

n = NotEvenCallable()
n.close()              # TypeError: 'int' object is not callable
```

```text nolines
Traceback (most recent call last):
  ...
TypeError: WrongSignature.close() missing 1 required positional argument: 'force'
```

```text nolines
Traceback (most recent call last):
  ...
TypeError: 'int' object is not callable
```

`isinstance` 가 `True` 를 줬는데 정확히 그 이유로 믿고 부른 코드가 터진다. **[1.15](#/protocols)에서 본 "isinstance는 할 수 있는가가 아니라 그렇다고 주장하는가를 묻는다"는 문장이 여기서도 그대로 적용된다.** 다만 ABC는 최소한 이름이 메서드인지, `None` 인지는 구분했다(`__hash__ = None` 관용구). `runtime_checkable Protocol` 은 그 구분조차 없다.

::: warn pyright는 이 위험을 알고 미리 알려 준다
방금 코드를 pyright에 넘기면 실행 에러가 나지 않았던 `isinstance` 줄에서 진단이 뜬다. `WrongSignature` 와 `NotEvenCallable` 둘 다 걸려서 각각 하나씩, 총 두 개가 나온다(uvx pyright 1.1.411 / Python 3.14.5 실측).

```text nolines
exp3.py:24:37 - error: Class overlaps "SupportsClose" unsafely and could produce a match at runtime
  Attributes of "WrongSignature" have the same names as the protocol (reportGeneralTypeIssues)
exp3.py:25:38 - error: Class overlaps "SupportsClose" unsafely and could produce a match at runtime
  Attributes of "NotEvenCallable" have the same names as the protocol (reportGeneralTypeIssues)
2 errors, 0 warnings, 0 informations
```

여기서 정정할 게 하나 있다: 이 진단은 `warning:` 이 아니라 **`error:`** 로 찍힌다. 실행 요약도 "2 errors, 0 warnings, 0 informations"이고 프로세스 종료 코드도 1이다 — pyright 자신은 이걸 경고가 아니라 에러로 취급한다. 다만 종류가 `reportGeneralTypeIssues` 라는 하나의 규칙에 묶여 있어서, strict 모드가 아닌 기본 설정에서도 걸린다는 점, 그리고 (뒤에서 볼 `reportAbstractUsage` 류의 "명백한 계약 위반" 에러와 달리) "지금 당장 틀렸다"가 아니라 "런타임에 거짓 매치가 날 수 있다"는 **예방적 경고성 판단**이라는 점에서 이 책은 편의상 '경고'라고 불러 왔다. pyright의 실제 심각도 등급은 에러라는 걸 분명히 해 둔다.

pyright는 `WrongSignature` 가 `SupportsClose` 의 시그니처를 만족하지 못한다는 걸 **정적으로는** 안다. 그런데도 `isinstance` 는 이름만 보고 통과시킬 걸 알기 때문에, "이 클래스는 런타임에 거짓으로 매치될 수 있다"고 미리 알려 준다. 정적 검사가 런타임의 구멍을 대신 메워 주는 드문 사례다. 이 진단을 무시하지 마라.
:::

::: note 데이터 멤버가 있으면 issubclass는 아예 막힌다
[1.15](#/protocols)에서 이미 확인했다. `x: int` 처럼 메서드가 아닌 속성이 프로토콜에 있으면 `issubclass` 는 `TypeError` 를 낸다. `isinstance` 는 인스턴스를 들여다볼 수 있지만 `issubclass` 는 클래스만 보므로 속성값의 존재를 확인할 방법이 없기 때문이다. `runtime_checkable` 은 메서드 이름 확인기에 가깝다.
:::

비용도 짚고 넘어가야 한다. [1.15](#/protocols)에서 같은 환경(Python 3.14.5 / Windows)으로 이미 실측했다. `isinstance(x, list)` 약 14ns, ABC `isinstance(x, Iterable)` 약 83ns, `runtime_checkable Protocol` 은 약 137ns — 구체 타입 검사의 약 10배였다. 뜨거운 루프에서 `isinstance(x, SomeProtocol)` 를 반복하면 이 비용이 그대로 쌓인다.

## 명시적으로 상속하면 무슨 일이 일어나는가

`Protocol` 을 대놓고 상속할 수도 있다. 그러면 ABC처럼 구현을 강제해 줄까?

```python title="exp5_broken_call.py"
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    def close(self) -> None: ...


class BrokenDoor(SupportsClose):
    pass                       # close를 구현하지 않았다


d = BrokenDoor()
print("인스턴스화 성공:", d)
print(d.close())
```

```text nolines
인스턴스화 성공: <__main__.BrokenDoor object at 0x0000016CF07F8D70>
None
```

**아무 에러도 없다.** `d.close()` 는 `None` 을 반환하고 끝난다. `SupportsClose.close` 의 본문이 `...` (Ellipsis 문장) 하나뿐이었는데, `BrokenDoor` 가 그걸 오버라이드하지 않았으니 **그 빈 본문을 그대로 물려받아 실행**한 것이다. [1.15](#/protocols)의 ABC였다면 `@abstractmethod` 가 붙은 메서드를 안 채운 순간 인스턴스화 자체가 `TypeError` 로 막혔다. `Protocol` 을 명시적으로 상속해도 **그 강제력은 따라오지 않는다.** `Protocol` 은 `abc.ABCMeta` 를 쓰지 않는다 — 메서드가 실제로 구현됐는지 검사하는 코드가 런타임에 아예 없다.

이제 pyright에 같은 파일을 넘겨 보자.

```bash
uvx pyright exp5_broken_call.py
```

```text nolines
exp5_broken_call.py:13:5 - error: Cannot instantiate abstract class "BrokenDoor"
  "SupportsClose.close" is not implemented (reportAbstractUsage)
1 error, 0 warnings, 0 informations
```

**여기서 정적과 런타임이 정반대로 갈라진다.** pyright는 `Protocol` 을 명시적으로 상속한 클래스를 ABC처럼 취급해서, 메서드를 안 채우면 인스턴스화 자체를 막는다. 그런데 실제로 실행하면 파이썬은 아무 불평 없이 인스턴스를 만들고 `None` 을 반환하는 메서드를 조용히 물려준다.

::: danger 정적 검사기를 통과했다고 런타임이 안전하다는 뜻이 아니다
이 절 전체에서 가장 위험한 함정이다. pyright가 "이 클래스는 추상이라 못 만든다"고 하는데, 실제 파이썬은 만들어 준다. CI에서 pyright를 건너뛰거나, `# type: ignore` 로 이 경고를 지운 코드가 있다면 `BrokenDoor()` 는 배포 환경에서 조용히 살아남아 `close()` 를 부를 때마다 아무 일도 안 하고 `None` 을 돌려준다. **타입 체커의 통과는 문서 검토를 통과한 것이지, 실행이 안전하다는 증명이 아니다.** 자세한 도구 설정은 [2.8 mypy와 pyright 실전](#/typecheckers)에서 다룬다.
:::

## Protocol을 실전에서 언제 쓰는가

지금까지의 사실을 모으면 선택 기준이 또렷해진다. `Protocol` 이 유리한 상황은 **"내가 정의하지 않은, 혹은 정의할 수 없는 타입"** 을 계약에 묶어야 할 때다.

**1. 내가 소유하지 않은 타입을 계약에 넣을 때.** 표준 라이브러리 파일 객체, 서드파티 라이브러리 반환값, 함수 객체 — 이런 것들은 상속시킬 수도 `register` 할 수도 없다(혹은 하기 싫다). 위의 `by_value` 예시가 정확히 이 경우다.

```python title="써 본 적 없는 타입도 구조로 검증한다"
from typing import Protocol


class HasWrite(Protocol):
    def write(self, s: str) -> int: ...


def log_to(target: HasWrite, message: str) -> None:
    target.write(message + "\n")


class ListSink:                      # io.TextIOBase 를 전혀 모른다
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, s: str) -> int:
        self.lines.append(s)
        return len(s)


sink = ListSink()
log_to(sink, "hello")
print(sink.lines)
```

```text nolines
['hello\n']
```

`ListSink` 는 파일도, `io` 모듈의 무엇도 아니다. `write(self, s: str) -> int` 라는 모양만 맞을 뿐인데 통과한다. 테스트에서 진짜 파일 대신 이런 **가짜 객체(fake)** 를 쓸 때 상속이 필요 없다는 게 핵심이다. [6.2 fixture, 파라미터화, mocking](#/pytest-advanced)에서 이 패턴을 다시 쓴다.

::: deep 구조가 맞아도 시그니처 세부가 다르면 pyright는 거부한다
같은 `HasWrite` 에 실제 파일 객체(`sys.stdout`)를 넘기면 어떻게 될까? 런타임은 문제없이 실행된다 — `sys.stdout.write("...")` 는 원래 되는 호출이다. 그런데 pyright는 거부한다. 실측(uvx pyright 1.1.411 / Python 3.14.5)한 전체 메시지는 이렇다.

```text nolines
error: Argument of type "TextIO | Any" cannot be assigned to parameter "target" of type "HasWrite" in function "log_to"
  Type "TextIO | Any" is not assignable to type "HasWrite"
    "TextIO" is incompatible with protocol "HasWrite"
      Could not bind method "write" because "TextIO" is not assignable to parameter "self"
        "TextIO" is not assignable to "IO[bytes]"
          Type parameter "AnyStr@IO" is invariant, but "str" is not the same as "bytes"
      "write" is an incompatible type
        Type "(s: str, /) -> int" is not assignable to type "(s: str) -> int"
          Missing keyword parameter "s" (reportArgumentType)
1 error, 0 warnings, 0 informations
```

이 메시지는 사실 **원인이 하나가 아니라 둘**이다. 뒤쪽 원인은 `/` 다. 표준 라이브러리의 실제 시그니처는 `write(self, s: str, /) -> int` — `s` 가 **위치 전용**(positional-only)이다. 내가 쓴 `HasWrite.write(self, s: str)` 는 위치 전용이 아니라서, `target.write(s="x")` 처럼 키워드로 부를 가능성까지 계약에 포함된다. `TextIO` 는 그 호출 방식을 지원하지 않으므로 구조가 "완전히" 맞다고 볼 수 없다는 것이다. **구조적 타이핑은 메서드 이름뿐 아니라 매개변수 전달 방식까지 계약에 넣는다.** 표준 라이브러리 프로토콜을 흉내 낼 때는 `/` 를 그대로 베껴야 한다.

그런데 메시지 앞쪽에는 이것과 **무관한 두 번째 불만**이 섞여 있다: `Could not bind method "write" because "TextIO" is not assignable to parameter "self"` 부터 이어지는 줄들이다. `io.TextIO` 는 실제로 `io.IO[str]` 계열이 아니라 제네릭 `IO[AnyStr]` 을 바탕으로 타입 스텁이 짜여 있고, `AnyStr` 은 **불변(invariant)** 타입 파라미터라서 `str` 과 `bytes` 가 서로 대입 가능하지 않다고 pyright가 판단한다. 즉 pyright는 `self` 바인딩 단계에서 한 번, `write` 의 매개변수 전달 방식에서 또 한 번, **서로 다른 두 지점**에서 `HasWrite` 와 `TextIO` 가 어긋난다고 말하고 있는 것이다. 실전에서 이 메시지를 마주치면 첫 줄만 보고 "아 위치 전용 문제구나" 하고 넘어가기 쉽지만, 전체를 다 읽지 않으면 `self` 바인딩 실패라는 별개의 원인을 놓친다.
:::

**2. 콜백·전략 함수의 타입을 표현할 때.** `Callable[[int, int], int]` 보다 `Comparator` 처럼 `__call__` 을 가진 `Protocol` 이 인자 이름과 의미를 문서로 남긴다.

**3. 계약이 메서드 한두 개뿐이고, 공짜 믹스인이 필요 없을 때.** `MutableMapping` 처럼 다섯 메서드로 스무 개를 얻는 상황([1.15](#/protocols))이 아니라면 ABC의 존재 이유가 없다. `Protocol` 은 어떤 구현도 강요하지 않고 형태만 요구한다.

**4. 함수 인자로 "가변 기본값 없이 새로 만든 값을 채워 넣을 수 있는 것" 같은, [1.10 함수](#/functions)에서 본 관용구를 타입으로 굳히고 싶을 때.** 예: `def merge(target: MutableMapping[str, int], ...)` 처럼 표준 프로토콜을 그대로 재사용하면 사용자 클래스든 `dict` 든 다 받는다.

반대로 **런타임에 "이 객체가 실제로 그 능력이 있는가"를 물어야 한다면 `Protocol` 이 답이 아니다.** [1.15](#/protocols)의 결론이 여기서도 유효하다. `isinstance(x, SomeProtocol)` 로 능력을 보장받으려 하지 말고, 그 능력을 그냥 써 보고 예외를 처리해라(EAFP, [1.16 예외와 예외 그룹](#/exceptions)). `runtime_checkable` 은 디스패치(타입에 따라 분기)에는 쓸 만하지만 입력 검증에는 적합하지 않다.

| 상황 | 선택 |
| --- | --- |
| 내가 소유하지 않은 타입(표준 라이브러리, 서드파티, 함수)을 계약에 넣는다 | **Protocol** |
| 계약이 메서드 하나·둘뿐이고 구현을 공유할 필요가 없다 | **Protocol** |
| 콜백/전략 함수의 시그니처를 이름 있는 형태로 문서화한다 | **Protocol** (`__call__`) |
| 여러 클래스에 공통 메서드(믹스인)를 실제로 나눠 주고 싶다 | **ABC** ([1.15](#/protocols)) |
| 런타임에 진짜로 그 능력이 있는지 보장받아야 한다 | **둘 다 아님** — 써 보고 예외 처리 |
| 제네릭한 계약(타입 매개변수가 있는 프로토콜)이 필요하다 | **Protocol** + [2.3 PEP 695](#/pep695) 문법 |

::: cote 코딩테스트에서
`Protocol` 을 직접 정의할 일은 거의 없다. 그러나 정렬 키 함수, DFS/BFS의 방문 콜백처럼 "함수를 인자로 받는 헬퍼"를 라이브러리 스타일로 짤 때, `Callable` 대신 이름 있는 `Protocol` 을 쓰면 팀 코드나 채점 리뷰에서 시그니처 실수를 pyright가 먼저 잡아 준다. 단, 시험장에서는 시간 대비 이득이 적다 — 타입 힌트 자체를 생략하는 편이 낫다.
:::

## 요약

- **타입 힌트는 실행에 관여하지 않는다.** `add("hello", "world")` 처럼 틀린 타입을 넘겨도 인터프리터는 그대로 실행한다. 검사는 pyright 같은 별도 도구가 코드를 **읽기만** 하며 한다.
- **`Protocol` 은 기본적으로 정적 전용이다.** `isinstance`/`issubclass` 는 `@runtime_checkable` 없이는 `TypeError` 다. ABC와 달리 애초에 런타임 통로가 막혀 있다.
- **구조적 타이핑은 "무엇을 상속했는가"가 아니라 "무엇을 갖고 있는가"로 타입을 맞춘다.** 계약을 쓰는 쪽이 나중에 정의할 수 있고, 상속이 불가능한 함수 객체도 만족시킬 수 있다.
- **`@runtime_checkable` 의 `isinstance` 는 메서드 이름의 존재만 본다.** 인자 개수가 다르거나 메서드가 아니어도(`close = 42`) 통과한다. pyright는 이런 "위험하게 겹치는" 클래스를 `reportGeneralTypeIssues` 로 미리 경고해 준다.
- **`Protocol` 을 명시적으로 상속해도 구현을 강제하지 않는다.** pyright는 추상 클래스로 취급해 인스턴스화를 막지만, 실제 파이썬은 빈 본문(`...`)을 그대로 물려주고 조용히 실행한다. 정적 통과가 런타임 안전을 보장하지 않는 대표 사례다.
- **구조가 맞아도 매개변수 전달 방식(위치 전용 여부 등)까지 일치해야 pyright가 통과시킨다.** 표준 라이브러리 프로토콜을 흉내 낼 때는 `/` 표기까지 그대로 옮겨야 한다.
- **선택 기준**: 소유하지 않은 타입, 콜백 시그니처, 최소 계약에는 Protocol. 믹스인이 필요하거나 런타임 능력 보장이 목적이면 ABC. 입력 검증 자체는 둘 다 아니고 EAFP다.

::: quiz 연습문제
1. 다음 코드가 예외 없이 끝까지 실행되는지 먼저 예측하고, 실행해서 확인하라. 예측이 틀렸다면 왜인지 설명하라.

   ```python
   def area(width: str, height: str) -> str:
       return width * height

   print(area(3, 4))
   ```

2. 아래 `Protocol` 과 클래스가 있다. `isinstance(Cache(), Store)` 의 결과를 예측하고, 왜 그런 결과가 나오는지 `@runtime_checkable` 의 검사 범위로 설명하라.

   ```python
   from typing import Protocol, runtime_checkable

   @runtime_checkable
   class Store(Protocol):
       def get(self, key: str) -> object: ...
       def set(self, key: str, value: object) -> None: ...

   class Cache:
       def get(self, key): ...
       set = None
   ```

3. `Protocol` 을 명시적으로 상속한 클래스가 메서드를 구현하지 않으면 pyright와 실제 실행 결과가 다르다. 이 절의 `BrokenDoor` 예시를 참고해, 왜 이 차이가 "타입 체커만 돌리고 실행은 안 해 보는" 팀에서 특히 위험한지 두 문장으로 설명하라.

4. **깊이 생각해 볼 문제.** `Comparator` 예시에서 `by_value` 는 어떤 클래스도 상속하지 않았는데 `Comparator` 타입 자리에 들어갈 수 있었다. 만약 `Comparator` 가 `Protocol` 이 아니라 평범한 ABC였다면, `by_value` 를 그 타입 자리에 넣기 위해 어떤 방법이 있었을지(있기는 한지) 생각해 보라.
:::

**다음 절**: [2.5 TypedDict, NamedTuple, Literal, Final](#/typed-containers) — 구조를 검사하는 `Protocol`을 넘어, 구조 자체에 이름을 붙이는 타입들.
