# 1.15 프로토콜, ABC, 덕 타이핑

::: lead
`for x in obj` 는 되는데 `isinstance(obj, Iterable)` 은 `False` 다. `hash(t)` 는 터지는데 `isinstance(t, Hashable)` 은 `True` 다. `Sequence.register(Fake)` 를 했더니 `Fake` 가 `Sequence` 라고 나오는데 `.index()` 를 부르면 `AttributeError` 다. 이 셋은 전부 버그가 아니라 **설계된 동작**이다. 이 절은 파이썬이 "타입"을 판단하는 세 가지 서로 다른 기준 — 덕 타이핑, 명목적 상속, 가상 등록 — 이 어떻게 겹치고 어긋나는지를 끝까지 파헤친다.
:::

## 문제: 이 함수는 무엇을 받는가

```python title="이 함수의 인자 타입은 무엇인가?"
def total(items):
    result = 0
    for x in items:
        result += x
    return result
```

`list` 를 받는다. `tuple` 도 받는다. `set`, `dict` 의 키, 제너레이터, `range`, NumPy 배열, 아직 세상에 없는 당신의 클래스도 받는다. 조건은 하나다. **`for` 에 넣을 수 있으면 된다.**

이게 덕 타이핑이다.

> **오리처럼 걷고 오리처럼 꽥꽥거리면 오리다.** 무엇으로 **선언**됐는지가 아니라 무엇을 **할 수 있는지**로 판단한다.

C++이나 Java에서 `total` 이 받는 것은 `Iterable<int>` 를 **상속한** 타입뿐이다. 상속이 곧 계약이다. 파이썬은 상속을 요구하지 않는다. 계약은 **런타임에 메서드를 찾아보는 행위** 그 자체다.

```text nolines
 Java   :  타입 검사기가 "너 Iterable 를 implements 했니?" 를 묻는다   (컴파일 시각)
 Python :  인터프리터가 obj 에서 __iter__ 를 찾는다. 있으면 부른다.   (실행 시각)
           없으면 __getitem__ 을 찾는다. 그것도 없으면 TypeError.
```

::: hist 덕 타이핑이 먼저였고 ABC 는 나중에 붙었다
파이썬은 처음부터 덕 타이핑 언어였다. `collections.abc` 의 조상인 ABC 기계는 **2007년 PEP 3119**로 파이썬 3에 들어왔다. 즉 언어가 16년 굴러간 뒤에 추가됐다.

왜 필요해졌나. 덕 타이핑은 **"부르기 전에는 알 수 없다"** 는 치명적 약점이 있다. `total(x)` 가 x를 반쯤 순회한 뒤에 터지면 이미 늦다. 그리고 `total` 의 시그니처만 봐서는 무엇을 넣어야 하는지 아무도 모른다.

PEP 3119의 해답은 **"덕 타이핑을 없애지 말고, 덕임을 물어볼 수 있는 창구를 만들자"** 였다. 그래서 ABC는 상속을 **강제하지 않는다.** 상속해도 되고, 등록만 해도 되고, 아무것도 안 해도 통과할 수 있다. 이 유연함이 이 절의 복잡함 전부의 원인이다.
:::

## isinstance 가 실제로 하는 일

대부분의 사람이 `isinstance(x, C)` 를 "x의 타입이 C이거나 C의 자손인가"로 이해한다. **틀렸다.** 실제 절차는 이렇다.

1. `type(C).__instancecheck__(C, x)` 를 호출한다. ==isinstance 는 C의 **메타클래스**에 위임한다.==
2. `type` 이 메타클래스면(= 평범한 클래스) 기본 구현이 `type(x)` **와** `x.__class__` 를 MRO에서 찾는다.
3. `ABCMeta` 가 메타클래스면 완전히 다른 알고리즘이 돈다.

그래서 `__class__` 를 오버라이드하면 `isinstance` 를 속일 수 있다 — `unittest.mock.Mock(spec=SomeClass)` 가 이 틈으로 `isinstance` 검사를 통과한다. [6.2 fixture, 파라미터화, mocking](#/pytest-advanced)에서 다시 만난다. 이 절이 파고들 것은 3번, ABC 전용 경로다.

### ABCMeta 의 알고리즘

`ABCMeta.__subclasscheck__` 의 순서다. 이 순서가 이 절 나머지 전부를 설명한다.

```text nolines
issubclass(S, C)   where  type(C) is ABCMeta

  1. C 의 양성 캐시에 S 가 있나?          -> True
  2. C 의 음성 캐시에 S 가 있나?          -> False
     (전역 무효화 카운터가 바뀌었으면 음성 캐시를 통째로 버린다)
  3. ok = C.__subclasshook__(S)
     ok is not NotImplemented            -> ok 를 그대로 반환하고 끝
  4. C in S.__mro__ ?                    -> True    (진짜 상속)
  5. C 의 등록부(registry)를 순회:
     issubclass(S, 등록된클래스) ?         -> True    (가상 서브클래스)
  6. C.__subclasses__() 를 재귀 순회      -> True
  7. 전부 실패                            -> False (음성 캐시에 적어 둠)
```

::: deep 3번이 4번보다 위에 있다는 사실의 무게
`__subclasshook__` 이 `False` 를 반환하면 **4·5·6번은 아예 실행되지 않는다.** 진짜 상속도, `register()` 도 무시된다.

```pyrepl
>>> from abc import ABC, abstractmethod
>>> class Drawable(ABC):
...     @abstractmethod
...     def draw(self): ...
...     @classmethod
...     def __subclasshook__(cls, C):
...         if cls is Drawable:
...             return any('draw' in B.__dict__ for B in C.__mro__)
...         return NotImplemented
...
>>> class NoDraw: pass
>>> Drawable.register(NoDraw)
<class '__main__.NoDraw'>
>>> issubclass(NoDraw, Drawable)
False
```

**등록했는데 `False` 다.** 훅이 3번에서 잘라 버렸기 때문이다.

표준 라이브러리는 이 함정을 안다. 그래서 `collections.abc` 의 모든 훅은 **실패할 때 `False` 가 아니라 `NotImplemented` 를 반환한다.**

```python title="_collections_abc.py — 실제 소스"
def _check_methods(C, *methods):
    mro = C.__mro__
    for method in methods:
        for B in mro:
            if method in B.__dict__:
                if B.__dict__[method] is None:
                    return NotImplemented        # ← False 가 아니다
                break
        else:
            return NotImplemented                # ← 여기도
    return True
```

덕분에 `register()` 라는 탈출구가 살아남는다.

```pyrepl
>>> from collections.abc import Iterable
>>> class NoIter: pass
>>> issubclass(NoIter, Iterable)
False
>>> Iterable.register(NoIter)
<class '__main__.NoIter'>
>>> issubclass(NoIter, Iterable)
True
```

**당신이 훅을 직접 쓸 때도 이 규칙을 따라라.** 실패는 `NotImplemented` 로 돌려라. `False` 를 돌리면 당신의 ABC는 등록 불가능한 ABC가 된다.
:::

## ABC 를 만드는 부품

ABC는 마법이 아니다. 두 부품의 조합이다.

**부품 1: `@abstractmethod`.** 하는 일이 딱 하나뿐이다. 함수에 `__isabstractmethod__ = True` 라는 속성을 붙인다. 그게 전부다.

**부품 2: `ABCMeta`.** 클래스가 만들어질 때 네임스페이스와 모든 조상을 훑어서 `__isabstractmethod__` 가 참인 이름을 모아 `__abstractmethods__` 라는 frozenset 에 넣는다. `object.__new__` 이 이 집합이 비어 있지 않으면 인스턴스 생성을 거부한다.

둘 중 하나만 있으면 아무 일도 안 일어난다.

```pyrepl
>>> from abc import abstractmethod
>>> class NoMeta:              # ABCMeta 가 아니다
...     @abstractmethod
...     def f(self): ...
...
>>> NoMeta()                   # 조용히 성공한다
<__main__.NoMeta object at 0x...>
>>> NoMeta.f.__isabstractmethod__
True
```

::: danger 추상 검사는 클래스 정의 시점이 아니라 인스턴스 생성 시점이다
그리고 `__abstractmethods__` 는 **클래스 생성 때 딱 한 번** 계산된다. 나중에 메서드를 붙여도 갱신되지 않는다.

```pyrepl
>>> from collections.abc import Sequence
>>> class Late(Sequence):
...     def __len__(self): return 3
...
>>> Late.__getitem__ = lambda self, i: i     # 런타임에 채워 넣었다
>>> Late.__abstractmethods__
frozenset({'__getitem__'})
>>> Late()
Traceback (most recent call last):
  ...
TypeError: Can't instantiate abstract class Late without an implementation for abstract method '__getitem__'
```

동적으로 메서드를 주입하는 프레임워크(ORM, 플러그인 로더)에서 실제로 터지는 사고다. 해결책은 `Late.__abstractmethods__ = frozenset()` 로 직접 지우는 것이지만, 그러기 전에 **왜 ABC를 쓰고 있는지**를 다시 생각하는 편이 낫다.
:::

`@abstractmethod` 는 다른 데코레이터와 겹칠 때 **항상 가장 안쪽**이다.

```python
class C(ABC):
    @property           # ✅
    @abstractmethod
    def x(self): ...

    @staticmethod       # ✅
    @abstractmethod
    def s(): ...
```

순서를 뒤집으면 3.14는 즉시 터진다 — `AttributeError: attribute '__isabstractmethod__' of 'property' objects is not writable`. `abstractmethod` 가 `__isabstractmethod__ = True` 를 대입하려는데 `property` 의 그 속성이 읽기 전용이기 때문이다. 조용히 틀리는 것보다 낫다.

## collections.abc 계층

이제 지도다. `collections.abc.__all__` 에는 26개가 있다. 왼쪽이 상속 관계, 오른쪽이 **당신이 구현해야 하는 것**이다.

```text nolines
object
 |
 +- Hashable ....................... __hash__
 +- Sized .......................... __len__
 +- Callable ....................... __call__
 +- Container ...................... __contains__
 +- Buffer ......................... __buffer__          (3.12+, PEP 688)
 +- Iterable ....................... __iter__
 |   +- Iterator ................... __next__
 |   |   +- Generator .............. send, throw
 |   +- Reversible ................. __reversed__
 +- Awaitable ...................... __await__
 |   +- Coroutine ................. send, throw
 +- AsyncIterable .................. __aiter__
     +- AsyncIterator .............. __anext__
         +- AsyncGenerator ......... asend, athrow

Collection(Sized, Iterable, Container) .... __len__, __iter__, __contains__
 |
 +- Sequence(Reversible, Collection) ...... __getitem__, __len__
 |   +- MutableSequence ................... + __setitem__, __delitem__, insert
 +- Set(Collection) ....................... __contains__, __iter__, __len__
 |   +- MutableSet ........................ + add, discard
 +- Mapping(Collection) ................... __getitem__, __iter__, __len__
     +- MutableMapping .................... + __setitem__, __delitem__

MappingView(Sized)
 +- KeysView(MappingView, Set)
 +- ItemsView(MappingView, Set)
 +- ValuesView(MappingView, Collection)
```

이 지도에서 읽어야 할 것 두 가지.

**첫째, 요구사항이 놀랍도록 적다.** `MutableMapping` 을 완전히 구현하려면 다섯 개(`__getitem__`, `__setitem__`, `__delitem__`, `__iter__`, `__len__`)만 쓰면 된다. `get`, `pop`, `setdefault`, `update`, `keys`, `items`, `values`, `clear`, `popitem`, `__contains__`, `__eq__` 는 공짜다.

**둘째, 상속선이 곧 `__subclasshook__` 유무의 경계다.** 위쪽 블록(`Hashable`~`AsyncGenerator`, `Collection`, `Buffer`)은 전부 자신만의 `__subclasshook__` 을 가진다. 즉 **구조만 맞으면 자동 통과**한다. 아래쪽(`Sequence`, `Mapping`, `Set` 계열)은 훅이 없다. **상속하거나 등록해야만 통과**한다.

이 경계가 이 절 최대의 함정을 만든다.

## 함정: 순회되는데 Iterable 이 아닌 객체

```pyrepl
>>> from collections.abc import Iterable, Sequence, Container
>>> class MyList:
...     def __init__(self, d): self._d = list(d)
...     def __getitem__(self, i): return self._d[i]
...     def __len__(self): return len(self._d)
...
>>> m = MyList([1, 2, 3])
>>> list(m)
[1, 2, 3]
>>> 2 in m
True
>>> list(reversed(m))
[3, 2, 1]
>>> isinstance(m, Iterable)
False
>>> isinstance(m, Container)
False
>>> isinstance(m, Sequence)
False
```

**순회도 되고, `in` 도 되고, `reversed` 도 되는데 셋 다 `False` 다.**

이유는 CPython의 **구식 시퀀스 프로토콜**이다. `iter(obj)` 는 `__iter__` 가 없으면 `__getitem__` 을 찾아서 `0, 1, 2, ...` 를 넣어 보다가 `IndexError` 가 나면 멈추는 이터레이터를 자동으로 만들어 준다. `in` 과 `reversed` 도 마찬가지로 대체 경로가 있다. 이건 `__iter__` 가 존재하기 전인 파이썬 1.x 시절의 유물이고, 하위 호환 때문에 영원히 남아 있다.

그런데 `Iterable.__subclasshook__` 은 `__iter__` **딱 하나만** 본다. 구식 경로는 모른다. 그래서 어긋난다.

::: danger isinstance(x, Iterable) 로 "순회 가능한가"를 묻지 마라
이건 **거짓 음성**을 낸다. 진짜로 순회 가능한지 알고 싶으면 물어보지 말고 **해 봐라.**

```python
# ❌ 구식 __getitem__ 객체를 놓친다
if isinstance(x, Iterable):
    for i in x: ...

# ✅ 진짜 순회 가능성을 검사한다
try:
    it = iter(x)
except TypeError:
    ...
```

`hasattr(x, "__iter__")` 도 같은 함정에 걸린다 — 이름만 보기는 `isinstance` 와 마찬가지다. **순회 가능성은 물어보지 말고 `iter()` 를 직접 불러서 확인하라.**
:::

## 상속으로 얻는 것: 믹스인

ABC를 **상속**하면 추상 메서드라는 의무가 생기는 대신 **믹스인 메서드**를 받는다. 이게 ABC 상속의 진짜 대가다.

```python title="다섯 개만 쓰고 dict 흉내 내기"
from collections.abc import MutableMapping


class CaseInsensitiveDict(MutableMapping):
    __slots__ = ('_d',)

    def __init__(self, data=None):
        self._d = {}
        if data:
            self.update(data)          # update 는 믹스인이 준다

    def __getitem__(self, k):
        return self._d[k.lower()][1]

    def __setitem__(self, k, v):
        self._d[k.lower()] = (k, v)    # 원래 대소문자를 보존한다

    def __delitem__(self, k):
        del self._d[k.lower()]

    def __iter__(self):
        return (orig for orig, _ in self._d.values())

    def __len__(self):
        return len(self._d)
```

```pyrepl
>>> h = CaseInsensitiveDict({'Content-Type': 'json'})
>>> h['CONTENT-TYPE']
'json'
>>> h.get('nope', 'default')
'default'
>>> list(h.items())
[('Content-Type', 'json')]
>>> h == {'Content-Type': 'json'}
True
>>> h.setdefault('X-Trace', '1')
'1'
```

`get`, `items`, `==`, `setdefault` 를 한 줄도 안 썼다. 전부 `MutableMapping` 이 준 것이다.

::: deep ABC 는 __slots__ = () 를 갖는다
평범한 클래스를 상속하면 `__dict__` 가 따라붙어서 `__slots__` 최적화가 무력화된다. `collections.abc` 의 모든 ABC는 **`__slots__ = ()`** 로 선언돼 있다. 그래서 상속해도 인스턴스 딕셔너리가 생기지 않는다.

```pyrepl
>>> from collections.abc import Sequence
>>> class S(Sequence):
...     __slots__ = ('_d',)
...     def __getitem__(self, i): return 0
...     def __len__(self): return 0
...
>>> hasattr(S(), '__dict__')
False
>>> import sys; sys.getsizeof(S())
40
```

`__slots__` 없는 평범한 객체는 48바이트 + `__dict__` 다. ABC 설계자들이 여기까지 신경 썼다. [1.12 클래스와 데이터 모델](#/classes) 참고.
:::

::: perf 믹스인은 공짜가 아니다 — 파이썬으로 짠 범용 구현이다
`Mapping.__contains__` 의 실제 소스는 이렇다.

```python
def __contains__(self, key):
    try:
        self[key]
    except KeyError:
        return False
    else:
        return True
```

`dict` 의 C 구현과 비교하면 (Python 3.14.5 / Windows 실측, 원소 1000개. 절대값은 기기마다 다르지만 배수 자릿수는 어디서나 비슷하다):

| 연산 | `dict` | `Mapping` 믹스인 | 배수 |
| --- | --- | --- | --- |
| `k in m` | 약 16 ns | 약 58 ns | 약 3.6배 |
| `list(m.items())` | 약 9.2 us | 약 45 us | 약 5배 |

`Sequence.__contains__` 와 `Sequence.index` 는 더하다. `__getitem__` 을 0부터 하나씩 호출하는 $O(n)$ 파이썬 루프다. `list.index` 는 같은 $O(n)$ 이지만 상수가 한 자릿수 작다.

**결론**: 믹스인은 *올바름*을 준다. *속도*는 안 준다. 뜨거운 루프에 들어가는 컨테이너라면 믹스인 위에 직접 최적화 구현을 얹어라. 상속했다고 덮어쓰지 못하는 건 아니다.
:::

## register(): 가상 서브클래스

상속은 강제다. 이미 존재하는 남의 클래스, 또는 C로 짠 내장 타입은 상속시킬 수 없다. `register()` 가 그 구멍을 메운다.

```pyrepl
>>> from collections.abc import Sequence
>>> class Fake: pass
>>> Sequence.register(Fake)
<class '__main__.Fake'>
>>> isinstance(Fake(), Sequence)
True
>>> Sequence in Fake.__mro__
False
>>> Fake().index(1)
Traceback (most recent call last):
  ...
AttributeError: 'Fake' object has no attribute 'index'
```

**`register()` 는 아무것도 검사하지 않고 아무것도 주지 않는다.** 그냥 등록부에 이름을 적을 뿐이다. MRO는 그대로다. 믹스인도 안 온다. `isinstance` 의 대답만 바뀐다.

이게 얼마나 널리 쓰이는지는 표준 라이브러리를 열어 보면 안다.

```pyrepl
>>> import abc
>>> from collections.abc import MutableSequence
>>> reg, cache, neg, tok = abc._get_dump(MutableSequence)
>>> sorted(r().__name__ for r in reg)
['bytearray', 'deque', 'list']
>>> list.__mro__
(<class 'list'>, <class 'object'>)
```

==`list` 는 `MutableSequence` 를 상속하지 않는다.== 등록됐을 뿐이다. `list.append` 와 `MutableSequence.append` 는 완전히 다른 함수다. 전자는 C 슬롯, 후자는 `insert(len(self), v)` 를 부르는 파이썬 함수다.

`collections.abc` 의 전체 등록부는 이게 전부다.

| ABC | 등록된 내장 타입 |
| --- | --- |
| `Sequence` | `bytes`, `str`, `tuple`, `range`, `memoryview` |
| `MutableSequence` | `list`, `bytearray`, `deque` |
| `Mapping` | `mappingproxy`, `FrameLocalsProxy` |
| `MutableMapping` | `dict` |
| `Set` | `frozenset` |
| `MutableSet` | `set` |

나머지 ABC(`Iterable`, `Hashable`, `Callable`, `Iterator`, ...)의 등록부는 **비어 있다.** 전부 `__subclasshook__` 으로 판정한다.

`register()` 는 인자로 받은 클래스를 그대로 반환한다. 그래서 데코레이터로 쓸 수 있다.

```python
@Sequence.register
class MyThing:
    ...
```

등록은 **전이된다.** `MyThing` 의 서브클래스도 자동으로 `Sequence` 다 (알고리즘 5번의 `issubclass(S, 등록된클래스)` 가 재귀적이기 때문). 그리고 순환은 막힌다 — `A.register(B)` 후 `B.register(A)` 는 `RuntimeError: Refusing to create an inheritance cycle` 이다.

::: deep 캐시와 무효화 카운터
ABC 검사는 느리다. 그래서 `ABCMeta` 는 ABC마다 **양성 캐시**와 **음성 캐시**(둘 다 `WeakSet`)를 들고 있다. 문제는 `register()` 가 언제든 음성 캐시를 거짓말로 만든다는 것이다.

CPython의 해법은 캐시를 지우는 게 아니라 **전역 카운터를 1 올리는 것**이다. 각 ABC의 음성 캐시는 자기가 마지막으로 본 카운터 값을 기억한다. 값이 다르면 캐시를 통째로 버린다. $O(1)$ 무효화다.

```pyrepl
>>> import abc
>>> from collections.abc import Iterable
>>> class Q: pass
>>> issubclass(Q, Iterable)
False
>>> reg, cache, neg, negtok = abc._get_dump(Iterable)
>>> len(neg), negtok
(1, 18)
>>> abc.get_cache_token()
18
>>> Iterable.register(Q)
<class '__main__.Q'>
>>> abc.get_cache_token()
19
>>> issubclass(Q, Iterable)     # 음성 캐시가 통째로 무시된다
True
```

`abc.get_cache_token()` 은 공개 API다. ABC 판정을 직접 캐싱하려면 이 토큰으로 무효화 시점을 알아내야 한다 — `functools.singledispatch` 가 그렇게 한다.

`abc._reset_caches` 는 인자 없이 부를 수 없다. 시그니처가 `_reset_caches(self, /)` 라서 **대상 ABC 클래스를 반드시 넘겨야 한다** — `abc._reset_caches(Iterable)` 처럼.

```pyrepl
>>> import abc
>>> abc._reset_caches()
Traceback (most recent call last):
  ...
TypeError: _abc._reset_caches() takes exactly one argument (0 given)
>>> from collections.abc import Iterable
>>> abc._reset_caches(Iterable)          # 이게 맞는 호출이다
```

캐시 유무의 차이 (Python 3.14.5 / Windows 실측, 매회 `abc._reset_caches(Iterable)` 로 강제 미스를 재현. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다):

| 경로 | 1회 비용 |
| --- | --- |
| `isinstance(x, list)` — 구체 타입 | 약 14 ns |
| `isinstance(x, Iterable)` — 캐시 적중 | 약 83 ns |
| `isinstance(x, Iterable)` — 캐시 미스 | 약 980 ns |

캐시 미스는 구체 타입 검사의 **약 70배**, 캐시 적중의 **약 12배**다. `WeakSet` 조회 + 훅 호출 + MRO 순회 + 등록부 재귀가 전부 파이썬/C 혼합 경로로 돈다. 매번 새 클래스가 등장하는 코드(동적 클래스 생성, 플러그인 로딩)에서는 이 비용이 실제로 보인다.
:::

이 등록부를 실제로 활용하는 곳이 `functools.singledispatch` 다. 예상 밖의 타입도 걸린다.

```pyrepl
>>> from functools import singledispatch
>>> from collections.abc import Sequence, Mapping
>>> @singledispatch
... def size(x): return 'unknown'
...
>>> @size.register
... def _(x: Sequence): return f'seq of {len(x)}'
...
>>> @size.register
... def _(x: Mapping): return f'map of {len(x)}'
...
>>> size([1, 2, 3])
'seq of 3'
>>> size({'a': 1})
'map of 1'
>>> size('abc')
'seq of 3'
>>> size(42)
'unknown'
```

`list` 를 등록한 적이 없는데 `list` 가 `Sequence` 분기로 간다. `singledispatch` 는 실인자의 MRO를 ABC 등록부까지 확장해서 후보를 찾는다. [3.1 일급 함수와 functools](#/functools)에서 이 해석 알고리즘을 파헤친다.

## __subclasshook__: 구조로 판정하기

훅은 **`classmethod`** 여야 하고, 세 가지 중 하나를 반환한다.

- `True` — 서브클래스다. 즉시 확정.
- `False` — 아니다. 즉시 확정. **상속과 등록을 무시한다.**
- `NotImplemented` — 판단 안 함. 알고리즘 4~6번으로 넘긴다.

```python title="구조 기반 ABC 만들기"
from abc import ABC, abstractmethod


class Drawable(ABC):
    __slots__ = ()

    @abstractmethod
    def draw(self) -> str: ...

    @classmethod
    def __subclasshook__(cls, C):
        if cls is not Drawable:          # ← 이 가드가 핵심이다
            return NotImplemented
        if any('draw' in B.__dict__ for B in C.__mro__):
            return True
        return NotImplemented            # ← False 가 아니다
```

```pyrepl
>>> class Circle:                # Drawable 을 모른다
...     def draw(self): return 'o'
...
>>> issubclass(Circle, Drawable)
True
>>> isinstance(Circle(), Drawable)
True
```

::: danger cls is Drawable 가드를 빼면 서브클래스가 전부 망가진다
훅은 **상속된다.** 가드가 없으면 `Drawable` 의 서브클래스들이 부모의 훅을 그대로 물려받아, **자기 자신의 추가 요구사항을 검사하지 못한다.**

```pyrepl
>>> from abc import ABC, abstractmethod
>>> class Loose(ABC):
...     @abstractmethod
...     def draw(self): ...
...     @classmethod
...     def __subclasshook__(cls, C):        # 가드 없음
...         return any('draw' in B.__dict__ for B in C.__mro__)
...
>>> class Loose3D(Loose):
...     @abstractmethod
...     def draw3d(self): ...
...
>>> class OnlyDraw:
...     def draw(self): return 'o'
...
>>> issubclass(OnlyDraw, Loose3D)
True
```

`draw3d` 가 없는데 `Loose3D` 로 통과했다. `Loose3D.__subclasshook__(OnlyDraw)` 이 실행되면서 `cls` 는 `Loose3D` 지만 훅 본문은 여전히 `draw` 만 본다.

`cls is X` 가드는 **선택이 아니라 필수**다. 표준 라이브러리의 모든 훅에 이 가드가 있다.
:::

::: warn 훅은 이름만 본다. 시그니처도 타입도 안 본다
`_check_methods(C, "__iter__")` 는 MRO 어딘가에 `__iter__` 라는 **이름**이 있는지만 확인한다. 그게 함수인지 정수인지, 인자를 몇 개 받는지는 관심 없다. `__iter__ = 42` 도 통과한다.

유일한 예외가 `None` 이다. 값이 정확히 `None` 이면 `NotImplemented` 를 반환한다. 이게 `__hash__ = None` 으로 클래스를 언해셔블하게 만드는 관용구를 지탱한다. `__eq__` 를 정의하면 파이썬이 자동으로 `__hash__ = None` 을 넣는 이유이기도 하다. ([1.14 특수 메서드 총정리](#/dunder))

```pyrepl
>>> from collections.abc import Hashable
>>> isinstance([], Hashable)
False
>>> list.__hash__ is None
True
```
:::

## isinstance 가 거짓말하는 순간들

여기까지 오면 이 절의 결론이 보인다. **`isinstance(x, SomeABC)` 는 "x가 그 일을 할 수 있다"를 보장하지 않는다.** 실제 사례들이다.

**1. Hashable 인데 해시가 안 된다.**

```pyrepl
>>> from collections.abc import Hashable
>>> t = ([1, 2], 3)
>>> isinstance(t, Hashable)
True
>>> hash(t)
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'list'
```

`tuple.__hash__` 는 존재한다. 훅은 그것만 본다. 원소까지는 안 본다. 해시 가능성은 **재귀적 성질**인데 훅은 얕게만 검사한다.

**2. Decimal 은 Real 이 아니다.**

```pyrepl
>>> import numbers
>>> from decimal import Decimal
>>> isinstance(Decimal('1.5'), numbers.Number)
True
>>> isinstance(Decimal('1.5'), numbers.Real)
False
>>> Decimal('1.5') + 1
Decimal('2.5')
```

`numbers` 타워는 `Number` → `Complex` → `Real` → `Rational` → `Integral` 이다. `Decimal` 은 `Number` 에만 등록돼 있다. `float` 와 자동 혼합 연산이 안 되기 때문에(정밀도 오염) 의도적으로 뺀 것이다. 하지만 `+`, `<`, `abs` 는 전부 된다. **ABC 계층과 실제 능력이 어긋난 사례.** [1.2 숫자와 수치 연산](#/numbers)

**3. ndarray 는 Sequence 가 아니다.**

```pyrepl
>>> import numpy as np
>>> from collections.abc import Sequence, Iterable
>>> a = np.array([1, 2, 3])
>>> isinstance(a, Iterable)
True
>>> isinstance(a, Sequence)
False
>>> a[0], len(a), list(reversed(a))
(np.int64(1), 3, [np.int64(3), np.int64(2), np.int64(1)])
```

`Sequence` 는 훅이 없다. NumPy는 등록하지 않았다. `a[0]` 과 `len(a)` 는 되는데 `Sequence` 는 아니다. `isinstance(x, Sequence)` 로 입력을 검증하는 코드는 **NumPy 배열을 전부 거부한다.** [9.1 NumPy: ndarray의 모든 것](#/numpy-basics)

이 세 사례의 공통점은 하나다. `__subclasshook__` 이든 `register()` 든, 검사할 수 있는 것은 **선언된 이름**뿐이다. 실제로 호출했을 때 성공하는지는 아무도 보장하지 않는다.

::: danger 이 절의 핵심 문장
> **`isinstance` 는 "할 수 있는가"가 아니라 "그렇다고 주장하는가"를 묻는다.**

ABC 검사는 **선언**의 확인이지 **능력**의 확인이 아니다. 능력을 확인하는 유일한 방법은 **해 보는 것**이다.

그래서 실무 규칙은 이렇다.

- **함수 입력 검증**에 `isinstance(x, ABC)` 를 쓰지 마라. 거짓 양성과 거짓 음성이 둘 다 난다. 그냥 쓰고 `TypeError` 가 나게 둬라. 파이썬의 에러 메시지가 당신의 것보다 낫다.
- **디스패치**(타입에 따라 다른 코드로 가기)에는 써도 된다. 여기서는 "주장"이 정확히 알고 싶은 것이다. `singledispatch` 가 이 경우다.
- **정적 검사**가 목적이면 `isinstance` 가 아니라 타입 체커를 써라. 그게 다음 이야기다.
:::

## 언제 ABC 고 언제 Protocol 인가

파이썬에는 프로토콜을 표현하는 방법이 두 개다.

```text nolines
 ABC (PEP 3119, 2007)              Protocol (PEP 544, 2017)
 ---------------------------       ---------------------------
 런타임 기계                        정적 타입 기계
 상속 또는 register 가 필요          아무것도 필요 없다
   (__subclasshook__ 은 예외)
 믹스인 메서드를 준다                아무것도 주지 않는다
 isinstance 가 항상 동작             @runtime_checkable 이어야 동작
 이름만 검사                        타입 체커가 시그니처까지 검사
 정의하는 쪽이 계약을 만든다          쓰는 쪽이 계약을 만든다
```

마지막 줄이 본질이다.

**ABC는 명목적(nominal)이다.** `MutableMapping` 을 만족한다고 선언하려면 상속하거나 등록해야 한다. **정의하는 쪽에 권한이 있다.**

**Protocol은 구조적(structural)이다.** `close()` 가 있으면 그냥 `Closeable` 이다. 아무도 선언하지 않았고 아무도 몰라도 된다. **쓰는 쪽에 권한이 있다.** 덕 타이핑을 타입 체커가 이해할 수 있는 형태로 옮긴 것이다.

```python title="같은 계약, 두 가지 표현"
from abc import ABC, abstractmethod
from typing import Protocol


class CloseableABC(ABC):                  # 명목적
    @abstractmethod
    def close(self) -> None: ...


class CloseableProto(Protocol):           # 구조적
    def close(self) -> None: ...


class Door:                               # 아무것도 상속 안 함
    def close(self) -> None: ...


def shut(x: CloseableProto) -> None:      # pyright 통과
    x.close()


shut(Door())                              # ✅ 정적으로 검증됨
```

### 선택 기준

| 상황 | 선택 |
| --- | --- |
| 구현체에 **공짜 메서드**를 주고 싶다 | **ABC** — 믹스인은 Protocol에 없다 |
| **내가 정의한 계층**의 기반 클래스를 만든다 | **ABC** |
| 이미 존재하는 **남의 타입**을 계약에 넣고 싶다 | **Protocol** (또는 ABC + `register`) |
| 계약이 **메서드 하나**뿐이다 | **Protocol** |
| **정적 검사**가 목적이다 | **Protocol** |
| **런타임 디스패치**가 목적이다 | **ABC** |
| 구현을 강제하고 **일찍 실패**시키고 싶다 | **ABC** — 인스턴스화가 막힌다 |

::: warn runtime_checkable Protocol 의 isinstance 는 ABC보다 약하다
`@runtime_checkable` 을 붙이면 `isinstance` 가 동작한다. 하지만 **속성 이름의 존재만** 본다. 타입 체커가 정적으로 하는 시그니처 검사는 런타임에 하나도 안 한다.

```pyrepl
>>> from typing import Protocol, runtime_checkable
>>> @runtime_checkable
... class Closeable(Protocol):
...     def close(self) -> None: ...
...
>>> class G:
...     close = 42
...
>>> isinstance(G(), Closeable)
True
```

`close` 가 정수인데 통과한다. 그리고 데이터 멤버가 있으면 `issubclass` 는 아예 거부한다.

```pyrepl
>>> @runtime_checkable
... class HasX(Protocol):
...     x: int
...
>>> issubclass(int, HasX)
Traceback (most recent call last):
  ...
TypeError: Protocols with non-method members don't support issubclass(). Non-method members: 'x'.
```

`isinstance` 는 되고 `issubclass` 는 안 된다. 인스턴스는 `x` 를 들고 있는지 볼 수 있지만 클래스는 볼 수 없기 때문이다.

비용도 있다 (Python 3.14.5 / Windows 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다):

| 검사 | 1회 |
| --- | --- |
| `isinstance(x, list)` | 약 14 ns |
| `isinstance(x, Iterable)` — ABC | 약 83 ns |
| `isinstance(f, Closeable)` — Protocol | 약 137 ns |

Protocol의 런타임 검사는 **구체 타입의 약 10배**다. 뜨거운 경로에 넣지 마라.
:::

::: note 이건 2.4절의 예고편이다
Protocol의 진짜 힘 — 제네릭 프로토콜, 변성(variance), 자기 참조 프로토콜, `Protocol` 을 명시적으로 상속했을 때의 의미 — 은 전부 타입 체커의 영역이다. [2.4 Protocol과 구조적 서브타이핑](#/protocol-typing)에서 다룬다. 여기서 기억할 것은 하나다. **ABC는 런타임 도구, Protocol은 정적 도구.** 둘의 `isinstance` 가 비슷해 보인다고 같은 물건이라고 착각하지 마라.
:::

::: tip ABC를 쓰기 전에 세 번 물어라
1. **믹스인이 필요한가?** 아니면 ABC의 유일한 실익이 사라진다.
2. **구현을 강제해야 하는가?** 아니면 문서와 타입 힌트로 충분하다.
3. **런타임에 물어봐야 하는가?** 아니면 Protocol이 더 정확하다.

셋 다 아니면 ABC는 코드에 계층만 늘리는 장식이다. 파이썬에서 "인터페이스니까 추상 클래스를 만든다"는 Java 습관이다. `total(items)` 는 아무 ABC 없이 20년째 잘 동작하고 있다.
:::

::: cote 코딩테스트에서
ABC를 직접 정의할 일은 없다. 하지만 `collections.abc` 지식이 실제로 쓰이는 곳이 있다.

**1. 커스텀 컨테이너보다 내장이 항상 빠르다.** `MutableSequence` 를 상속해서 만든 자료구조는 믹스인이 파이썬 루프라 무조건 느리다. 세그먼트 트리, 유니온 파인드는 **평범한 list로** 짜라. ([7.25 세그먼트 트리와 펜윅 트리](#/segment-tree))

**2. `Sequence` 판정으로 입력을 분기하지 마라.** 문자열 함정이 여기서도 나온다.

```python
from collections.abc import Iterable

def flatten(x):
    if isinstance(x, Iterable):          # ❌ str 도 Iterable 이다
        for i in x:
            yield from flatten(i)        #    'ab' -> 'a' -> 'a' -> ... 무한 재귀
    else:
        yield x

def flatten2(x):
    if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):   # ✅
        for i in x:
            yield from flatten2(i)
    else:
        yield x
```

`flatten([1, ['ab', 2]])` 은 `RecursionError` 다. 길이 1인 문자열의 원소가 다시 자기 자신이기 때문이다. 중첩 리스트 평탄화 문제에서 실제로 나오는 사고다.

**3. `deque` 는 `MutableSequence` 지만 `list` 가 아니다.** `isinstance(dq, list)` 는 `False` 다. 라이브러리 함수에 넘길 때 확인하라. ([7.7 스택과 큐](#/stack-queue))
:::

## 요약

- **덕 타이핑**은 선언이 아니라 능력으로 판단한다. 파이썬의 기본값이고, `for x in items` 가 아무 타입이나 받는 이유다.
- **ABC**는 덕 타이핑을 없애지 않고 **"덕이냐고 물어볼 창구"** 를 추가한 것이다. `@abstractmethod` 는 플래그를 붙일 뿐이고, 실제 일은 `ABCMeta` 가 한다. 검사는 **인스턴스 생성 시점**에, `__abstractmethods__` 는 **클래스 생성 시점**에 계산된다.
- **`isinstance` 는 메타클래스에 위임한다.** `ABCMeta` 의 순서는 `캐시 → __subclasshook__ → __mro__ → 등록부 → __subclasses__` 다. 훅이 `False` 를 반환하면 나머지가 전부 무시되므로, 훅은 실패 시 **`NotImplemented`** 를 반환해야 한다.
- **상속하면 믹스인을 받는다.** `MutableMapping` 은 다섯 메서드로 dict 급 API를 만들어 준다. 대신 파이썬 구현이라 `dict` 보다 몇 배 느리다(연산에 따라 3~5배).
- **`register()` 는 아무것도 검사하지 않고 아무것도 주지 않는다.** `isinstance` 의 대답만 바꾼다. `list` 가 `MutableSequence` 인 것도 이 방식이다 — MRO에는 없다.
- **`isinstance(x, ABC)` 는 "할 수 있는가"가 아니라 "그렇다고 주장하는가"를 묻는다.** `Hashable` 인 튜플이 해시가 안 되고, `Decimal` 은 `Real` 이 아니고, `ndarray` 는 `Sequence` 가 아니고, `__getitem__` 만 있는 객체는 순회되는데 `Iterable` 이 아니다.
- **ABC는 명목적·런타임, Protocol은 구조적·정적.** 믹스인이 필요하거나 런타임 디스패치가 목적이면 ABC. 남의 타입을 계약에 넣거나 정적 검사가 목적이면 Protocol.

::: quiz 연습문제

1. 다음 각각의 출력을 **먼저 예측한 뒤** 실행하라. 틀린 것이 있으면 왜인지 설명하라.

   ```python
   from collections.abc import Iterable, Container, Sized, Sequence

   class Box:
       def __len__(self): return 3
       def __getitem__(self, i):
           if i >= 3: raise IndexError
           return i

   b = Box()
   print(list(b))
   print(2 in b)
   print(isinstance(b, Sized), isinstance(b, Iterable),
         isinstance(b, Container), isinstance(b, Sequence))
   ```

2. 아래 ABC는 두 군데가 틀렸다. 각각 어떤 상황에서 문제가 되는지 설명하고 고쳐라.

   ```python
   from abc import ABC, abstractmethod

   class Serializable(ABC):
       @abstractmethod
       def dump(self) -> bytes: ...

       @classmethod
       def __subclasshook__(cls, C):
           return any('dump' in B.__dict__ for B in C.__mro__)
   ```

3. 다음이 왜 `False` 인지, 그리고 어떻게 하면 `True` 로 만들 수 있는지 **두 가지 방법**을 제시하라. 각 방법의 대가는 무엇인가?

   ```python
   import numpy as np
   from collections.abc import Sequence
   print(isinstance(np.array([1, 2, 3]), Sequence))
   ```

4. **깊이 생각해 볼 문제.** 아래 코드는 `True`, `False` 중 무엇을 출력하는가? 예측하고 실행하라. 예측이 틀렸다면 `ABCMeta.__subclasscheck__` 의 7단계 중 몇 번에서 결정됐는지 짚어라.

   ```python
   from abc import ABC, abstractmethod

   class Duck(ABC):
       @abstractmethod
       def quack(self): ...

       @classmethod
       def __subclasshook__(cls, C):
           if cls is Duck:
               return any('quack' in B.__dict__ for B in C.__mro__)
           return NotImplemented

   class Robot:
       pass

   Duck.register(Robot)
   print(issubclass(Robot, Duck))

   Robot.quack = lambda self: 'beep'
   print(issubclass(Robot, Duck))
   ```

   힌트: 두 번째 출력이 첫 번째와 다르다면, 캐시는 왜 방해하지 않았는가?
:::

**다음 절**: [1.16 예외와 예외 그룹](#/exceptions) — EAFP가 파이썬의 기본 전략인 이유, 그리고 예외 하나로는 부족해진 시대의 `ExceptionGroup`.
