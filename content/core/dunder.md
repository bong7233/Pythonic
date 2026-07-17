# 1.14 특수 메서드 총정리

::: lead
`len(x)` 는 왜 `x.len()` 이 아닌가. 파이썬은 **연산자와 내장 함수를 문법이 아니라 프로토콜로 만들었다.** `+`, `[]`, `in`, `len()`, `for` 는 전부 정해진 이름의 메서드를 호출하는 껍데기다. 그 이름들이 특수 메서드, 흔히 **던더**(dunder — double underscore)다. 이 절의 목표는 던더 목록을 외우는 게 아니라 **호출 규칙을 정확히 아는 것**이다. 규칙 하나를 모르면 프록시가 조용히 깨지고, `__eq__` 하나 정의했다가 객체가 dict 키로 못 들어가고, 정렬이 4배 느려진다.
:::

## 문제부터: 프록시가 깨진다

리스트를 감싸서 모든 접근을 기록하는 프록시를 만든다고 하자. 처음 쓰는 코드는 대개 이렇게 생겼다.

```python title="proxy.py — 어디가 잘못됐나?"
class Proxy:
    def __init__(self, target):
        self._t = target

    def __getattr__(self, name):
        print(f"  __getattr__({name!r})")
        return getattr(self._t, name)
```

`__getattr__` 은 없는 속성을 찾을 때 불린다. 그러니 **모든 것이** `self._t` 로 넘어가야 한다. 실제로 그런가?

```pyrepl
>>> p = Proxy([1, 2, 3])
>>> p.append
  __getattr__('append')
<built-in method append of list object at 0x18d9228b900>
>>> len(p)
Traceback (most recent call last):
  ...
TypeError: object of type 'Proxy' has no len()
>>> p.__len__()
  __getattr__('__len__')
3
```

`p.__len__()` 은 되는데 `len(p)` 는 안 된다. **같은 메서드를 부르는데 결과가 다르다.** 이 한 줄이 이 절 전체의 열쇠다.

## 규칙 1: 특수 메서드는 타입에서 조회된다

파이썬이 특수 메서드를 **암묵적으로** 부를 때 — `len(x)`, `a + b`, `x[i]`, `for i in x` 처럼 문법이나 내장 함수를 통할 때 — 인스턴스는 쳐다보지도 않는다. `type(x)` 와 그 MRO에서만 찾는다.

```text nolines
     x.__len__()           len(x)
         │                    │
         ▼                    ▼
   x.__dict__ 를 먼저      type(x) 의 슬롯만 본다
         │                    │
         ▼                    ▼
   없으면 type(x)         x.__dict__ 는 절대 안 본다
         │                    │
         ▼                    ▼
   없으면 __getattr__     없으면 곧바로 TypeError
```

증명은 간단하다.

```pyrepl
>>> class C:
...     pass
...
>>> c = C()
>>> c.__len__ = lambda: 42       # 인스턴스에 직접 붙인다
>>> c.__len__()
42
>>> len(c)
Traceback (most recent call last):
  ...
TypeError: object of type 'C' has no len()
```

인스턴스에 `__len__` 이 멀쩡히 있는데 `len()` 이 못 찾는다. 반대로 **클래스에 붙이면 즉시 반영된다.** 이미 만들어진 인스턴스에도.

```pyrepl
>>> C.__len__ = lambda self: 7
>>> len(c)
7
>>> del C.__len__
>>> len(c)
Traceback (most recent call last):
  ...
TypeError: object of type 'C' has no len()
```

::: deep 왜 타입에서만 찾는가 — 슬롯이라는 물건
CPython에서 모든 타입은 C 구조체 `PyTypeObject` 다. 그 안에 `tp_hash`, `tp_call`, `tp_iter` 같은 **함수 포인터 필드**가 줄지어 있다. 이걸 슬롯(slot)이라 부른다.

```text nolines
len(x)
  │
  ▼
PyObject_Size(x)
  │
  ▼
Py_TYPE(x)->tp_as_sequence->sq_length      <- 구조체 필드 하나를 읽는다
  │
  ▼
C 함수 포인터를 그냥 호출
```

`list` 처럼 C로 짠 타입은 슬롯에 C 함수가 직접 들어 있다. 딕셔너리 탐색이 **한 번도** 일어나지 않는다. 파이썬 클래스는 생성 시점에 `slot_sq_length` 라는 어댑터가 슬롯에 꽂히고, 그 어댑터가 MRO를 뒤져 `__len__` 을 찾는다.

`C.__len__ = ...` 이 즉시 먹히는 이유도 여기 있다. `type.__setattr__` 은 특수 메서드 이름을 감지하면 **해당 슬롯을 다시 채운다**(`update_one_slot`). 인스턴스에 붙이는 건 이 경로를 건드리지 않으니 아무 효과가 없다.

즉 이 규칙은 성능 최적화의 결과다. `a + b` 마다 인스턴스 `__dict__` → 클래스 → MRO 전체를 훑는다면 산술 연산이 지금의 몇 배는 느렸을 것이다. **슬롯은 그 탐색을 포인터 하나 읽기로 압축했고, 대가로 "인스턴스별 특수 메서드"를 포기했다.**
:::

::: perf 슬롯을 거치는 비용
파이썬으로 정의한 `__len__` 은 슬롯 → 어댑터 → 파이썬 함수 3단계를 탄다. 그래서 **직접 부르는 것보다 오히려 느리다.**

```python title="세 가지 호출 경로"
import timeit

setup = """
class C:
    def __len__(self): return 3
    def size(self): return 3
c = C()
lst = [1, 2, 3]
"""
for stmt in ["len(c)", "c.size()", "c.__len__()", "len(lst)"]:
    print(stmt, min(timeit.repeat(stmt, setup, number=1_000_000, repeat=5)))
```

```text nolines
len(c)         0.0311s / 100만회      <- 슬롯 어댑터를 경유
c.size()       0.0155s / 100만회
c.__len__()    0.0147s / 100만회
len(lst)       0.0081s / 100만회      <- C 슬롯 직행
```

(Python 3.14.5 / Windows 실측. 절대값은 기기마다 다르다.)

둘을 읽어라. **하나**, 내장 타입의 `len()` 은 사실상 공짜다. **둘**, 직접 정의한 던더는 일반 메서드보다 두 배쯤 비싸다. 그렇다고 `len(x)` 대신 `x.size()` 를 쓰라는 말은 아니다 — 프로토콜을 따르는 값이 이 차이보다 훨씬 크다. **1억 번 도는 루프 안이라면** 알아야 하는 숫자일 뿐이다.
:::

이제 프록시가 왜 깨졌는지 답할 수 있다. `Proxy` 에 `__len__` 이 없으니 슬롯이 비어 있고, `len()` 은 슬롯이 비면 **`__getattr__` 을 물어보지 않고 그냥 TypeError를 낸다.**

::: danger 던더를 위임하는 프록시는 하나씩 손으로 써야 한다
`__getattr__` 로 던더를 위임할 수 없다. 필요한 던더를 **클래스에 직접** 나열하는 수밖에 없다. 표준 라이브러리 `unittest.mock` 이 그렇게 한다.

```python title="지루하지만 정확하다"
class Proxy:
    def __init__(self, target):
        self._t = target

    def __getattr__(self, name):
        return getattr(self._t, name)

    # 던더는 자동으로 안 넘어간다. 필요한 것만 명시한다.
    def __len__(self):
        return len(self._t)

    def __getitem__(self, k):
        return self._t[k]

    def __iter__(self):
        return iter(self._t)
```
:::

규칙이 "타입에서 찾는다"이므로, **클래스 객체**에 연산을 걸면 그 클래스의 타입 — 즉 메타클래스에서 찾는다.

```pyrepl
>>> class Meta(type):
...     def __len__(cls): return 99
...
>>> class C(metaclass=Meta):
...     def __len__(self): return 1
...
>>> len(C)
99
>>> len(C())
1
```

`C()` 가 인스턴스를 내는 것도 같은 규칙이다. `type(C).__call__(C)` = `type.__call__` 이 `__new__` 와 `__init__` 을 부른다. ([3.4 메타클래스](#/metaclass))

## `__repr__` 과 `__str__` — 대상이 다르다

둘 다 문자열을 만든다. 그런데 **독자가 다르다.**

| | `__repr__` | `__str__` |
| --- | --- | --- |
| 독자 | 개발자 | 최종 사용자 |
| 목표 | 명확함, 디버깅 | 읽기 좋음 |
| 호출 | `repr()`, REPL, 컨테이너 안, `!r`, 디버거 | `str()`, `print()`, f-string 기본 |
| 이상 | `eval(repr(x)) == x` | 자유 |
| 없으면 | `<__main__.C object at 0x...>` | **`__repr__` 으로 대체** |

**핵심 비대칭**: `__str__` 이 없으면 `__repr__` 이 대신 불린다. 반대는 아니다.

```pyrepl
>>> class OnlyRepr:
...     def __repr__(self): return "OnlyRepr()"
...
>>> class OnlyStr:
...     def __str__(self): return "I am str"
...
>>> str(OnlyRepr())          # __str__ 이 없다 → __repr__ 이 대신
'OnlyRepr()'
>>> repr(OnlyStr())          # __repr__ 이 없다 → 기본 repr
'<__main__.OnlyStr object at 0x193044c46e0>'
>>> print([OnlyStr()])       # 컨테이너는 원소의 repr 을 쓴다
[<__main__.OnlyStr object at 0x193044c46e0>]
```

**둘 중 하나만 쓸 거라면 반드시 `__repr__` 이다.** `__str__` 만 정의하면 로그와 디버거에서 아무 정보도 못 얻는다. 리스트에 담긴 순간 정체 불명의 주소가 쏟아진다.

::: deep 폴백은 탐색 실패가 아니다
"`__str__` 을 못 찾아서 `__repr__` 으로 간다"고 생각하기 쉽다. 틀렸다. `__str__` 은 **항상 찾아진다** — `object.__str__` 이 있고, 그 구현이 C 레벨에서 `PyObject_Repr(self)` 를 반환할 뿐이다.

```pyrepl
>>> object.__str__ is object.__repr__
False
>>> class OnlyRepr:
...     def __repr__(self): return "OnlyRepr()"
...
>>> OnlyRepr.__str__ is object.__str__
True
```

구분이 중요한 이유: `__str__` 을 정의한 **부모를 상속하면 그 `__str__` 이 이긴다.** MRO에서 `object` 보다 먼저 나오기 때문이다. `__repr__` 만 새로 써도 `str()` 은 부모 것을 쓴다.
:::

`eval(repr(x)) == x` 는 강제가 아니라 규범이다. 표준 라이브러리는 가능한 한 지킨다.

```pyrepl
>>> import datetime, decimal, fractions
>>> repr(datetime.date(2026, 7, 17))
'datetime.date(2026, 7, 17)'
>>> repr(decimal.Decimal('1.5'))
"Decimal('1.5')"
>>> repr(fractions.Fraction(1, 3))
'Fraction(1, 3)'
```

전부 `eval` 하면 원본과 같은 객체가 나온다. 당신의 클래스도 이 형태를 따라라. 못 지키겠으면 **꺾쇠**로 감싸는 게 관례다: `<Connection host='db01' state=closed>`.

손으로 쓰기 싫으면 `@dataclass` 가 만들어 준다 — 필드가 늘 때마다 갱신을 잊는 것보다 낫다. ([2.6 dataclasses](#/dataclasses)) 직접 쓸 때는 `f"Point({self.x!r}, {self.y!r})"` 처럼 **`!r` 을 붙여라.** 그래야 문자열 필드에 따옴표가 살아남는다.

::: note 사실 축은 셋이다
f-string의 `{x:spec}` 은 `str()` 도 `repr()` 도 아닌 **`type(x).__format__(x, spec)`** 이다.

```pyrepl
>>> class Show:
...     def __str__(self): return "STR"
...     def __repr__(self): return "REPR"
...     def __format__(self, s): return "FORMAT"
...
>>> x = Show()
>>> f"{x} {x!s} {x!r}"
'FORMAT STR REPR'
>>> f"{x=}"
'x=REPR'
```

`{x=}` 디버그 문법은 `!r` 이 기본이다. 여기서도 `__repr__` 이 이긴다.
:::

## 비교 — `__eq__` 는 특별 대우를 받는다

비교 연산자 6개는 각각 던더에 대응한다: `__lt__`, `__le__`, `__eq__`, `__ne__`, `__gt__`, `__ge__`. 여기서 첫 번째 놀라움 — **`object` 는 이미 이 6개를 다 갖고 있다.**

```pyrepl
>>> object.__lt__
<slot wrapper '__lt__' of 'object' objects>
>>> object.__lt__(object(), object())
NotImplemented
```

`<` 가 "없는" 게 아니다. **정의는 되어 있고 `NotImplemented` 를 반환한다.** 그래서 에러가 `AttributeError` 가 아니다.

```pyrepl
>>> object() < object()
Traceback (most recent call last):
  ...
TypeError: '<' not supported between instances of 'object' and 'object'
```

`object.__eq__` 만은 다르다. **정체성 비교로 폴백한다.** 그래서 `__eq__` 를 정의하지 않은 클래스도 `==` 가 동작하고, 그 의미는 `is` 다.

### `__ne__` 는 쓰지 마라

파이썬 3에서 `__ne__` 는 **`__eq__` 에서 자동 파생된다.** `object.__ne__` 가 `__eq__` 를 호출하고 결과를 뒤집는다.

```pyrepl
>>> class E:
...     def __init__(self, v): self.v = v
...     def __eq__(self, o):
...         print("  __eq__ 호출")
...         return self.v == o.v
...
>>> E(1) != E(2)
  __eq__ 호출
True
>>> '__ne__' in E.__dict__
False
```

`__ne__` 를 직접 정의하면 `__eq__` 와 어긋날 위험만 생긴다. 파이썬 2에서 넘어온 습관이다. **버려라.**

### `total_ordering` — 편의와 비용

정렬, `min`, `max`, `heapq` 는 **`__lt__` 하나만** 쓴다. `<=`, `>`, `>=` 까지 원하면 `functools.total_ordering` 이 나머지를 채운다.

```pyrepl
>>> import functools
>>> @functools.total_ordering
... class V:
...     def __init__(self, v): self.v = v
...     def __eq__(self, o): return self.v == o.v
...     def __lt__(self, o): return self.v < o.v
...
>>> [m for m in ('__lt__', '__le__', '__gt__', '__ge__') if m in V.__dict__]
['__lt__', '__le__', '__gt__', '__ge__']
>>> V(1) <= V(2), V(3) > V(2), V(2) >= V(2)
(True, True, True)
```

`__eq__` 와 넷 중 하나가 있어야 한다. 없으면 클래스 정의 시점에 터진다.

```pyrepl
>>> @functools.total_ordering
... class B:
...     pass
Traceback (most recent call last):
  ...
ValueError: must define at least one ordering operation: < > <= >=
```

::: perf total_ordering 이 채운 메서드는 1.7배 느리다
파생된 `__le__` 는 `not (other < self)` 같은 **파이썬 코드**다. 원본 던더를 한 번 더 호출한다.

```text nolines
total_ordering __le__ : 0.0613s / 100만회
직접 구현     __le__ : 0.0363s / 100만회      <- 1.69배 빠르다
원본         __lt__ : 0.0361s / 100만회
```

(Python 3.14.5 / Windows 실측.)

대부분의 코드에서는 무의미한 차이다. **비교가 뜨거운 루프 안에 있을 때만** 손으로 4개를 쓴다.
:::

그리고 `total_ordering` 은 `__hash__` 를 되살려 주지 않는다. `__eq__` 를 정의했으니 `V.__hash__` 는 `None` 이다. 바로 다음 절의 주제다.

::: cote 정렬은 __lt__ 로 하지 말고 key= 로 하라
객체 2만 개를 정렬해 보자.

```text nolines
__lt__ 로 정렬     :  9.1 ms
key= 로 정렬       :  2.1 ms      <- 4.3배 빠르다
raw float 정렬     :  1.4 ms
```

(Python 3.14.5 / Windows 실측. 원소는 난수 float 2만 개.)

이유는 호출 횟수다. `key=` 는 **원소당 한 번** 키를 뽑고($n$번), 그 뒤의 $O(n \log n)$번 비교는 **C 레벨 float 비교**다. `__lt__` 방식은 그 $n \log n$번이 전부 **파이썬 함수 호출**이다. 2만 개면 약 28만 번.

```python
# ❌ 시험장에서 이거 쓰면 TLE 난다
tasks.sort()

# ✅ 정렬 키를 튜플로 뽑는다
tasks.sort(key=lambda t: (t.pri, t.name))
```

`heapq` 는 `key=` 를 안 받는다. 그래서 **튜플을 넣는 게 관용구**이고, 타이 브레이커를 끼워야 한다 — `heappush(h, (priority, counter, task))`. `counter` 없이 `priority` 가 같으면 파이썬이 **두 번째 원소를 비교**하는데, `task` 가 `__lt__` 를 지원하지 않으면 그 순간 터진다.

```pyrepl
>>> import heapq
>>> class NoCmp: pass
>>> h = []
>>> heapq.heappush(h, (1, NoCmp()))
>>> heapq.heappush(h, (1, NoCmp()))
Traceback (most recent call last):
  ...
TypeError: '<' not supported between instances of 'NoCmp' and 'NoCmp'
```

**첫 번째 push는 성공하고 두 번째에서 터진다.** 힙 크기가 1일 때는 비교할 상대가 없기 때문이다. 그래서 테스트 케이스가 작으면 통과하고 큰 입력에서만 죽는다. [7.8 힙](#/heap)에서 다시 본다.
:::

## `__eq__` 를 정의하면 `__hash__` 가 사라진다

함정이 아니라 **의도된 안전장치**다. 처음 당하면 무슨 일인지 모른다.

```pyrepl
>>> class P:
...     def __init__(self, x): self.x = x
...     def __eq__(self, o): return isinstance(o, P) and self.x == o.x
...
>>> print(P.__hash__)
None
>>> {P(1)}
Traceback (most recent call last):
  ...
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
>>> class Child(P): pass
...
>>> print(Child.__hash__)              # 상속으로도 전파된다
None
```

`__eq__` 를 클래스 본문에 쓰는 순간, 파이썬이 **같은 클래스에 `__hash__ = None` 을 넣는다.**

::: hist 왜 이런 짓을 하는가 — 해시 계약
해시 기반 컨테이너(`dict`, `set`)는 이 계약 위에서 동작한다.

> **`a == b` 이면 반드시 `hash(a) == hash(b)`.**

역은 성립하지 않아도 된다(해시 충돌). 하지만 이 방향이 깨지면 dict가 조용히 틀린 답을 낸다. 같은 값인데 다른 버킷에 들어가서, 넣은 키를 못 찾는다.

`object.__hash__` 는 **id 기반**이다. `__eq__` 만 값 기반으로 바꾸면 계약이 즉시 깨진다 — `P(1) == P(1)` 은 `True` 인데 `hash` 는 다르다. 파이썬 2는 이걸 방치했고 조용한 버그의 온상이었다. 파이썬 3은 **시끄럽게 실패하는 쪽**을 택했다.
:::

셋 중 하나를 고른다.

```python title="선택지 세 가지"
# ✅ 1. 값 기반 해시를 준다 — __eq__ 가 쓰는 필드로 튜플을 만든다
class P:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __eq__(self, o):
        return isinstance(o, P) and (self.x, self.y) == (o.x, o.y)

    def __hash__(self):
        return hash((self.x, self.y))     # __eq__ 와 같은 필드!


# ✅ 2. 해시 불가를 받아들인다 — 아무것도 안 하면 이게 기본
#    가변 객체라면 이게 옳은 선택인 경우가 많다


# ⚠️ 3. id 기반 해시를 되살린다 — == 와 hash 의 의미가 갈라진다
class Q:
    def __eq__(self, o): ...
    __hash__ = object.__hash__            # 계약 위반. 정말 필요할 때만
```

`dataclass` 는 이 규칙을 그대로 따른다.

```pyrepl
>>> from dataclasses import dataclass
>>> @dataclass                       # eq=True 가 기본
... class A:
...     x: int
...
>>> print(A.__hash__)
None
>>> @dataclass(frozen=True)          # 불변 → 해시 안전 → 생성해 준다
... class B:
...     x: int
...
>>> hash(B(1)) == hash(B(1))
True
```

::: danger 가변 객체에 값 기반 해시를 달면
계약을 지켰어도 **필드를 바꾸는 순간** 깨진다. 해시는 넣을 때 계산되고, 그 뒤로 갱신되지 않는다.

```pyrepl
>>> class P:
...     def __init__(self, x): self.x = x
...     def __eq__(self, o): return isinstance(o, P) and self.x == o.x
...     def __hash__(self): return hash(self.x)
...     def __repr__(self): return f"P({self.x})"
...
>>> p = P(1)
>>> s = {p}
>>> p.x = 999              # 해시에 쓰이는 필드를 바꿨다
>>> p in s
False
>>> s
{P(999)}
>>> len(s)
1
```

**집합 안에 있는데 `in` 이 False다.** 순회하면 보이는데 찾을 수는 없다. 원소는 옛 해시값의 버킷에 있고, 검색은 새 해시값의 버킷을 보기 때문이다. 여기서 더 나간다.

```pyrepl
>>> s.add(p)
>>> s
{P(999), P(999)}
>>> len(s)
2
```

**같은 객체 하나가 집합에 두 번 들어갔다.** `set` 의 유일성 보장이 무너졌다.

교훈: **해시 가능한 것은 불변이어야 한다.** `@dataclass(frozen=True)`, `tuple`, `NamedTuple` 을 써라. 파이썬이 `list` 와 `dict` 를 해시 불가로 만든 이유가 정확히 이것이다.
:::

::: deep hash() 가 당신의 __hash__ 반환값에 하는 일
`__hash__` 가 반환한 정수는 그대로 쓰이지 않는다. `Py_hash_t`(64비트)에 안 들어가면 **정수의 해시를 다시 취한다.**

```pyrepl
>>> class H:
...     def __hash__(self): return 2**70
...
>>> hash(H())
512
```

512가 왜 나오나. `hash(2**70)` 이 512이기 때문이다. 파이썬 int의 해시는 **메르센 소수 $2^{61}-1$ 에 대한 나머지**다. $2^{70} = 2^{61} \cdot 2^{9} \equiv 1 \cdot 512 \pmod{2^{61}-1}$.

```pyrepl
>>> import sys
>>> sys.hash_info.modulus
2305843009213693951
>>> sys.hash_info.modulus == 2**61 - 1
True
```

그리고 이 유명한 것.

```pyrepl
>>> hash(-1)
-2
```

`-1` 은 CPython C API에서 **에러 신호**로 예약돼 있다 — `tp_hash` 가 `-1` 을 반환하면 "예외 발생"이라는 뜻이다. 그래서 진짜 해시가 `-1` 이면 `-2` 로 바꿔 내보낸다. 당신의 `__hash__` 가 `-1` 을 반환해도 똑같다.
:::

::: warn NaN — 해시 계약의 유일한 합법적 예외
`float('nan')` 은 자기 자신과 같지 않다(IEEE 754). 그런데 컨테이너 안에서는 다르게 보인다.

```pyrepl
>>> nan = float('nan')
>>> nan == nan
False
>>> nan in [nan]
True
>>> float('nan') in [float('nan')]
False
```

`in`, `index`, 리스트의 `==` 는 원소를 비교하기 전에 **정체성 지름길**을 탄다. CPython의 `PyObject_RichCompare` 계열이 `x is y or x == y` 로 동작하기 때문이다.

```pyrepl
>>> class Never:
...     def __eq__(self, o):
...         print("  __eq__ 호출됨")
...         return False
...
>>> n = Never()
>>> n in [n]
True
>>> Never() in [n]
  __eq__ 호출됨
False
```

`__eq__` 가 `False` 만 반환하는데도 `n in [n]` 이 `True` 다. **`__eq__` 가 아예 호출되지 않았다.** 성능 최적화이자 실용적 결정이다 — `lst.remove(x)` 가 방금 넣은 그 객체를 못 지우면 곤란하니까.

곁들여서, 3.10부터 `hash(float('nan'))` 은 **객체마다 다르다**(id 기반). 단, 같은 줄에서 `hash(float('nan')), hash(float('nan'))` 처럼 임시 객체를 바로 버리면 첫 번째 nan이 죽자마자 그 주소를 두 번째 nan이 재사용해서 **오히려 같은 값**이 나올 수 있다 — [1.1](#/objects-names)에서 본 `id()` 재사용과 똑같은 함정이다. 이름을 붙여 살려 두면 진짜 차이가 보인다.

```pyrepl
>>> a, b = float('nan'), float('nan')
>>> hash(a), hash(b)
(150630390597, 150630617579)
>>> hash(float('nan')), hash(float('nan'))    # 임시 객체는 즉시 죽고 주소가 재사용된다
(101791408745, 101791408745)
```

NaN 여러 개를 dict 키로 넣으면 전부 다른 버킷에 흩어지게 하려는 조치다. 예전에는 전부 0이라 최악의 해시 충돌이 났다. (`sys.hash_info.nan` 이 아직 `0` 을 보고하지만, 이건 갱신되지 않은 값이다.)
:::

## 산술 연산자와 반사 연산

`a + b` 는 `a.__add__(b)` 로 끝나지 않는다. 정확한 규칙은 이렇다.

```text nolines
a + b
  │
  ├─ 1. type(b) 가 type(a) 의 진짜 서브클래스이고
  │        __radd__ 를 오버라이드했으면 -> b.__radd__(a) 먼저
  │
  ├─ 2. a.__add__(b)
  │        NotImplemented 가 아니면 -> 그 값이 답
  │
  ├─ 3. b.__radd__(a)                    <- type(a) is not type(b) 일 때만
  │        NotImplemented 가 아니면 -> 그 값이 답
  │
  └─ 4. TypeError: unsupported operand type(s) for +
```

`NotImplemented` 는 **"나는 이 조합을 모른다, 상대에게 물어봐라"** 라는 신호다. `None` 이 아니고 예외도 아니다. 반환하면 인터프리터가 다음 단계로 넘어간다.

```pyrepl
>>> class Money:
...     def __init__(self, w): self.w = w
...     def __add__(self, o):
...         if isinstance(o, Money): return Money(self.w + o.w)
...         if o == 0: return self               # sum() 의 시작값
...         return NotImplemented
...     def __radd__(self, o): return self.__add__(o)
...     def __repr__(self): return f"Money({self.w})"
...
>>> sum([Money(100), Money(200)])
Money(300)
>>> Money(1) + "x"
Traceback (most recent call last):
  ...
TypeError: unsupported operand type(s) for +: 'Money' and 'str'
```

`sum()` 이 왜 되는지 보라. `sum` 은 `0 + Money(100)` 으로 시작한다. `int.__add__(0, Money)` 가 `NotImplemented` 를 내고, `Money.__radd__(0)` 이 받아서 `o == 0` 분기로 `self` 를 반환한다. **`__radd__` 를 안 만들었으면 `sum()` 이 TypeError로 터진다.**

::: warn NotImplemented 를 예외로 던지지 마라. raise 도 하지 마라.
```python
# ❌ 좋은 에러 메시지를 잃는다
def __add__(self, o):
    if not isinstance(o, Money):
        raise TypeError("Money만 더할 수 있다")
    ...

# ✅ 파이썬이 반사 연산을 시도하고, 실패하면 표준 메시지를 만든다
def __add__(self, o):
    if not isinstance(o, Money):
        return NotImplemented
    ...
```

직접 `raise` 하면 **상대 타입의 `__radd__` 가 호출될 기회를 뺏는다.** `Money + NumPyArray` 같은 협업이 불가능해진다. 라이브러리를 만든다면 치명적이다.

`NotImplemented` 와 `NotImplementedError` 는 완전히 다른 물건이다. 전자는 값, 후자는 예외 클래스다. 이름이 비슷해서 자주 헷갈린다.
:::

### 서브클래스 우선 규칙

1번 규칙이 미묘하다. **오른쪽이 왼쪽의 서브클래스이고, 반사 메서드를 실제로 오버라이드했을 때만** 순서가 뒤집힌다.

```pyrepl
>>> class Base:
...     def __add__(self, o): print("  Base.__add__"); return "base add"
...     def __radd__(self, o): print("  Base.__radd__"); return "base radd"
...
>>> class Sub(Base):
...     pass                                 # 오버라이드 안 함
...
>>> Base() + Sub()
  Base.__add__
'base add'
>>> class Sub2(Base):
...     def __radd__(self, o): print("  Sub2.__radd__"); return "sub2 radd"
...
>>> Base() + Sub2()
  Sub2.__radd__
'sub2 radd'
```

이유는 이렇다. **서브클래스는 부모보다 더 많이 안다.** `Base` 는 `Sub2` 가 세상에 있는지도 모르고 짜인 코드다. `Base.__add__` 가 먼저 성공해 버리면 `Sub2` 는 자기 타입에 맞는 결과를 낼 기회를 영영 잃는다. NumPy가 이 규칙 위에 서 있다.

```pyrepl
>>> import numpy as np
>>> issubclass(np.float64, float)     # float 의 서브클래스다
True
>>> type(1.0 + np.float64(2.0))       # 그래서 오른쪽이 이긴다
<class 'numpy.float64'>
```

### 같은 타입끼리는 반사가 없다

```pyrepl
>>> class X:
...     def __add__(self, o):
...         print("  X.__add__"); return NotImplemented
...     def __radd__(self, o):
...         print("  X.__radd__"); return "r"
...
>>> X() + X()
  X.__add__
Traceback (most recent call last):
  ...
TypeError: unsupported operand type(s) for +: 'X' and 'X'
```

`__radd__` 가 있는데 안 불린다. 같은 타입이면 `__radd__` 를 물어봐야 답이 같을 게 뻔하므로 CPython이 건너뛴다. **`X + X` 를 지원하려면 `__add__` 에서 처리해야 한다.**

## `__iadd__` — 제자리 연산의 두 얼굴

`a += b` 의 규칙은 [1.1 객체와 이름](#/objects-names)에서 봤다. 여기서는 던더 구현자 입장에서 본다.

```text nolines
a += b
  │
  ├─ 1. type(a).__iadd__ 가 있으면 -> a = a.__iadd__(b)
  │                                        반환값을 a 에 다시 대입한다
  └─ 2. 없으면 -> a = a + b
```

**2단계가 함정의 근원이다.** `__iadd__` 는 값을 반환하는 것으로 끝나지 않는다. 그 반환값이 **왼쪽 이름에 다시 대입된다.**

::: danger __iadd__ 에서 return self 를 빼먹으면
```python
class Bag:
    def __init__(self, items):
        self.items = list(items)

    def __iadd__(self, o):
        self.items.extend(o)
        # ❌ return self 를 안 썼다
```

```pyrepl
>>> b = Bag([1, 2])
>>> b += [3]
>>> print(b)
None
```

**객체가 `None` 으로 바뀌었다.** `__iadd__` 가 암묵적으로 `None` 을 반환했고, 그게 `b` 에 대입됐다. `extend` 는 성공했지만 그 객체를 가리키던 이름이 사라졌다.

`__iadd__`, `__isub__`, `__imul__` 계열은 **전부 `return self` 로 끝나야 한다.** 예외 없다.
:::

### 튜플 함정 — 에러가 났는데 값이 바뀐다

```pyrepl
>>> t = ([1, 2], 3)
>>> t[0] += [9]
Traceback (most recent call last):
  ...
TypeError: 'tuple' object does not support item assignment
>>> t
([1, 2, 9], 3)
```

바이트코드를 보면 왜인지 정확히 보인다.

```pyrepl
>>> import dis
>>> dis.dis(compile("t[0] += [9]", "<s>", "exec"))
  0           RESUME                   0

  1           LOAD_NAME                0 (t)
              LOAD_SMALL_INT           0
              COPY                     2
              COPY                     2
              BINARY_OP               26 ([])
              LOAD_SMALL_INT           9
              BUILD_LIST               1
              BINARY_OP               13 (+=)
              SWAP                     3
              SWAP                     2
              STORE_SUBSCR
              ...
```

맨 위 `RESUME 0` 은 3.11부터 모든 코드 객체 맨 앞에 붙는 명령이다 — 인터프리터가 함수 진입 시 트레이싱/시그널을 처리하는 훅이고, 이 예제의 논리와는 무관하니 이후로는 생략한다. 진짜 핵심은 그 다음 줄부터다. `BINARY_OP 13 (+=)` 가 리스트를 **이미 제자리 확장했다.** 그 다음 `STORE_SUBSCR` 이 튜플에 대입을 시도하다 터진다. **1번은 이미 일어난 뒤다.** 예외를 잡아도 되돌릴 방법이 없다.

이 함정은 `+=` 가 **읽기-수정-쓰기** 세 동작이라는 사실에서 나온다. 파이썬은 `__iadd__` 가 제자리 수정이라는 걸 알아도 `STORE` 를 생략하지 않는다. 그래야 `int` 처럼 `__iadd__` 가 없는 타입에서도 같은 바이트코드가 동작하기 때문이다.

::: danger 클래스 변수에 += 를 하면
```python
class Team:
    members = []              # 클래스 변수

    def add(self, m):
        self.members += [m]   # ← 함정
```

```pyrepl
>>> a, b = Team(), Team()
>>> a.add("A")
>>> b.members
['A']
>>> Team.members
['A']
```

`b` 는 손대지도 않았는데 멤버가 생겼다. `self.members += [m]` 은 이렇게 풀린다.

1. `self.members` 읽기 → 인스턴스에 없으니 **클래스 변수**를 찾는다
2. 그 리스트에 `__iadd__` → **제자리 확장**. 클래스 변수가 바뀌었다
3. `self.members = <그 리스트>` → **인스턴스 속성**을 새로 만든다

```pyrepl
>>> 'members' in a.__dict__
True
```

인스턴스 속성이 생기긴 했다. 하지만 **클래스 변수와 같은 객체를 가리킨다.** 최악의 조합이다 — 인스턴스 속성이 생겨 문제가 숨겨지고, 실제로는 전부 공유된다.

`self.members = self.members + [m]` 로 바꾸면 3단계에서 **새 리스트**가 대입되므로 클래스 변수는 안전하다. 애초에 클래스 변수를 가변으로 두지 마라. ([1.12 클래스](#/classes))
:::

## 컨테이너 프로토콜

파이썬은 "컨테이너"를 인터페이스로 정의하지 않는다. **던더 몇 개를 구현하면 컨테이너다.** 그리고 던더끼리 폴백 관계가 있다.

```text nolines
for x in obj        __iter__  -> __getitem__(0), (1), (2), ... IndexError
x in obj            __contains__ -> __iter__ -> __getitem__
len(obj)            __len__ (폴백 없음)
obj[k]              __getitem__ (폴백 없음)
bool(obj)           __bool__ -> __len__ -> 항상 True
reversed(obj)       __reversed__ -> (__len__ + __getitem__)
next(it)            __next__ (폴백 없음)
```

### 옛날 프로토콜은 아직 살아 있다

`__iter__` 가 없어도 `__getitem__` 만 있으면 순회된다. 파이썬 2 시절의 유산이다.

```pyrepl
>>> class Old:
...     def __init__(self, data): self.data = data
...     def __getitem__(self, i):
...         print(f"  __getitem__({i})")
...         return self.data[i]
...
>>> list(Old([10, 20, 30]))
  __getitem__(0)
  __getitem__(1)
  __getitem__(2)
  __getitem__(3)
[10, 20, 30]
```

**0부터 정수를 넣어 보다가 `IndexError` 가 나면 멈춘다.** 네 번째 호출이 있는 이유다. `in` 도 같은 경로를 탄다.

::: warn 이 폴백이 만드는 실제 버그
`__getitem__` 을 딕셔너리처럼 **키 조회**로 구현하면 그 객체가 갑자기 순회 가능해진다. 그런데 `KeyError` 는 `IndexError` 가 아니므로 **순회가 멈추질 못한다.**

```python
class Config:
    def __init__(self, d): self._d = d
    def __getitem__(self, key):
        return self._d[key]      # 0 을 넣으면 KeyError → 순회가 예외로 죽는다
```

`for k in config:` 는 `TypeError: not iterable` 이 아니라 `KeyError: 0` 을 낸다. 에러 메시지가 원인을 전혀 안 알려 준다. **`__getitem__` 을 매핑용으로 쓸 거면 `__iter__` 를 반드시 함께 정의하라.**
:::

### `__contains__` 는 없어도 되지만, 있어야 한다

`__contains__` 가 없으면 `in` 은 `__iter__` 로 전수 조사한다. $O(1)$ 이 $O(n)$ 이 된다.

::: perf 폴백의 대가
```python title="원소 1만 개, 최악 케이스 조회"
class WithContains:
    def __init__(self, data): self.s = set(data)
    def __contains__(self, x): return x in self.s

class WithIterOnly:
    def __init__(self, data): self.data = list(data)
    def __iter__(self): return iter(self.data)
```

```text nolines
__contains__ 구현   :   0.041 us
__iter__ 폴백       :  44.1 us          <- 1084배
```

(Python 3.14.5 / Windows 실측. 원소 1만 개.)

**폴백은 동작을 보장하지 성능을 보장하지 않는다.** 코드는 똑같이 `x in obj` 인데 세 자릿수가 달라진다. `in` 이 자주 불리는 클래스라면 `__contains__` 를 직접 써라.
:::

### `__bool__` 과 `__len__`

```pyrepl
>>> class Empty:
...     def __len__(self): return 0
...
>>> bool(Empty())
False
>>> class NoLen: pass
...
>>> bool(NoLen())
True
```

`__bool__` 도 `__len__` 도 없으면 **항상 참**이다. 커스텀 컨테이너에 `__len__` 을 빼먹으면 빈 컨테이너가 참이 된다. `if not container:` 로 짠 코드가 조용히 죽는다.

::: deep __len__ 은 아무 정수나 받지 않는다
반환값은 C의 `Py_ssize_t` 에 맞아야 한다. 음수는 `ValueError`, `float` 는 `TypeError`, 그리고 **$2^{63}$ 이상은 `OverflowError`** 다. 세 번째가 진짜 함정인데, **`bool()` 이 같은 제약을 물려받기 때문**이다.

```pyrepl
>>> class Big:
...     def __len__(self): return 10**20
...
>>> bool(Big())
Traceback (most recent call last):
  ...
OverflowError: cannot fit 'int' into an index-sized integer
```

`if obj:` 가 OverflowError를 낸다. 무한 시퀀스나 거대한 게으른 컬렉션을 모델링한다면 `__len__` 을 **정의하지 말고** `__bool__` 을 따로 줘라.
:::

::: tip collections.abc 를 상속하면 나머지가 딸려 온다
`__len__` 과 `__getitem__` 두 개만 쓰면 `Sequence` 가 채워 준다.

```python
from collections.abc import Sequence

class Deck(Sequence):
    def __init__(self, cards): self._c = list(cards)
    def __len__(self): return len(self._c)
    def __getitem__(self, i): return self._c[i]
```

```pyrepl
>>> d = Deck("ABCDE")
>>> list(reversed(d)), 'C' in d, d.index('D'), d.count('A')
(['E', 'D', 'C', 'B', 'A'], True, 3, 1)
```

`__contains__`, `__iter__`, `__reversed__`, `index`, `count` 를 믹스인으로 받았다. 다만 **믹스인 구현은 일반해라 느리다** — 방금 본 `__contains__` 벤치마크가 그 얘기다. 뜨거운 경로는 직접 오버라이드하라. ([1.15 프로토콜과 ABC](#/protocols))
:::

### `__getitem__` 이 받는 것

`obj[...]` 의 대괄호 안은 **하나의 객체로 포장돼** 넘어온다.

```pyrepl
>>> class S:
...     def __getitem__(self, key): return type(key).__name__, key
...
>>> S()[1]
('int', 1)
>>> S()[1:5]
('slice', slice(1, 5, None))
>>> S()[1, 2]
('tuple', (1, 2))
>>> S()[1:2, ::3]
('tuple', (slice(1, 2, None), slice(None, None, 3)))
>>> S()[...]
('ellipsis', Ellipsis)
```

`a[1:2, ::3]` 이 튜플로 온다는 것 — 이게 NumPy의 `arr[0:2, ::-1]` 이 동작하는 원리다. 파이썬 문법이 다차원을 지원하는 게 아니라, **NumPy가 튜플을 해석하는 것**이다. `...`(Ellipsis)도 마찬가지다. ([9.1 NumPy](#/numpy-basics))

슬라이스를 직접 처리할 때는 `slice.indices(len)` 을 써라. 음수와 `None` 을 정규화해 준다.

```pyrepl
>>> slice(None, None, -1).indices(5)
(4, -1, -1)
```

## `__call__` — 객체를 함수로

`obj(...)` 는 `type(obj).__call__(obj, ...)` 이다. 이게 있으면 `callable(obj)` 이 참이다.

```pyrepl
>>> class Counter:
...     def __init__(self): self.n = 0
...     def __call__(self, x):
...         self.n += 1
...         return x * 2
...
>>> c = Counter()
>>> c(3), c(5), c.n
(6, 10, 2)
>>> callable(c)
True
```

**함수와 다른 점은 상태를 갖는다는 것이다.** 클로저로도 상태를 가질 수 있지만, `__call__` 쪽은 상태를 **바깥에서 들여다보고 고칠 수 있다.** `c.n` 을 읽고, 리셋하고, 테스트에서 검증할 수 있다. 클로저의 셀 변수는 그게 어렵다. ([1.10 함수](#/functions))

비용은 `__len__` 과 같은 이야기다. `c(3)` 은 `tp_call` 슬롯 → 어댑터 → 파이썬 함수를 거쳐 **50만 회에 0.0282초**, 같은 일을 하는 일반 메서드 `c.run(3)` 은 **0.0145초**다(Python 3.14.5 / Windows 실측, `timeit.repeat(number=500_000, repeat=10)` 최솟값 기준). 약 1.9배 — 문법의 우아함에 대한 대가이고, 대부분은 낼 만한 값이다.

쓰이는 곳은 생각보다 많다. **클래스 자체**가 그렇고(`C()` = `type.__call__(C)`), 인자 받는 **데코레이터**를 클래스로 짤 때 `__call__` 이 감싸기를 맡고([1.11 데코레이터](#/decorators)), `functools.partial` 과 `operator.itemgetter` 도 전부 이것이다.

가장 중요한 예는 PyTorch다. `model(x)` 는 `Module.__call__` 이고, 그게 **훅을 실행한 뒤** `forward(x)` 를 부른다. `model.forward(x)` 를 직접 부르면 훅이 안 돈다 — 그래서 절대 그렇게 쓰지 않는다. ([11.4 nn.Module](#/nn-module))

## 요약

- **특수 메서드는 `type(x)` 에서만 조회된다.** 인스턴스 `__dict__` 도 `__getattr__` 도 안 본다. 이름 탐색을 슬롯(C 함수 포인터)으로 압축한 대가다. 프록시는 던더를 손으로 나열해야 한다.
- **`__repr__` 을 먼저 써라.** `__str__` 이 없으면 `__repr__` 이 대신하지만 반대는 없다.
- **`__ne__` 는 쓰지 마라.** `__eq__` 에서 자동 파생된다. 정렬·`heapq` 는 `__lt__` 하나만 쓴다. `total_ordering` 은 편의를 주고 1.7배를 가져간다.
- **`__eq__` 를 정의하면 `__hash__` 가 `None` 이 된다.** 해시 계약(`a == b` → `hash(a) == hash(b)`)을 지키라는 강제다. 해시 가능한 것은 불변이어야 한다.
- **산술은 `NotImplemented` 로 사양한다.** `raise` 하면 상대의 `__radd__` 기회를 뺏는다. 오른쪽이 서브클래스이고 반사 메서드를 오버라이드했으면 그쪽이 먼저다.
- **`__iadd__` 는 `return self` 로 끝난다.** `a[i] += x` 는 읽기-수정-쓰기라, 튜플 안 리스트에서는 **수정에 성공하고 쓰기에 실패**한다.
- **폴백은 동작을 보장하지 성능을 보장하지 않는다.** `__contains__` 없이 `in` 을 쓰면 1000배 느려질 수 있다.

::: quiz 연습문제
1. 다음 코드의 출력을 예측하라. 왜 그런가?

   ```python
   class C:
       def __init__(self):
           self.__str__ = lambda: "인스턴스"
       def __str__(self):
           return "클래스"

   c = C()
   print(c)
   print(c.__str__())
   ```

2. 아래 클래스는 `sum([Vec(1), Vec(2)])` 에서 터진다. 왜인가? 던더 하나를 추가해 고쳐라.

   ```python
   class Vec:
       def __init__(self, v): self.v = v
       def __add__(self, o):
           if isinstance(o, Vec): return Vec(self.v + o.v)
           return NotImplemented
   ```

3. 다음 세 줄의 결과를 예측한 뒤 실행하라. 셋 중 하나만 다르다. 어느 것이고 왜인가?

   ```python
   nan = float('nan')
   print(nan in [nan])
   print(nan in {nan})
   print(float('nan') in [float('nan')])
   ```

4. 아래 클래스를 `dict` 키로 쓰면 무슨 일이 생기는가? 두 가지 문제를 찾고 각각 고쳐라.

   ```python
   class Key:
       def __init__(self, tags): self.tags = tags       # tags 는 list
       def __eq__(self, o): return self.tags == o.tags
       def __hash__(self): return hash(tuple(self.tags))
   ```

5. **깊이 생각해 볼 문제.** 다음이 왜 `TypeError` 를 내지 않고 `KeyError: 0` 을 내는지 설명하라. 그리고 `TypeError: 'Config' object is not iterable` 이 나오게 고쳐라.

   ```python
   class Config:
       def __init__(self, d): self._d = d
       def __getitem__(self, key): return self._d[key]

   for k in Config({'a': 1}):
       print(k)
   ```
:::

**다음 절**: [1.15 프로토콜, ABC, 덕 타이핑](#/protocols) — 던더를 모아 놓은 것이 프로토콜이다. `collections.abc` 는 그 프로토콜에 이름과 검사를 붙인다.
