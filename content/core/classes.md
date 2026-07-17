# 1.12 클래스와 데이터 모델

::: lead
`class` 문을 쓸 줄 아는 것과 클래스가 무엇인지 아는 것은 다르다. `obj.x` 한 줄이 실행될 때 CPython은 최소 세 군데를 순서대로 뒤진다. 그 순서를 모르면 프로퍼티가 왜 안 먹히는지, 클래스 변수가 왜 혼자 바뀌는지, `__slots__` 가 왜 자식 클래스에서 무력해지는지 설명할 수 없다. 이 절은 속성 하나를 읽는 데 드는 실제 비용부터 시작해서, 인스턴스가 메모리에서 어떻게 생겼는지까지 내려간다.
:::

## 속성 하나 읽는 데 무슨 일이 벌어지나

문제부터 보자. 아래 코드의 출력을 예측해 보라.

```python title="predict.py"
class Desc:
    def __get__(self, obj, objtype=None):
        return "클래스의 디스크립터"
    def __set__(self, obj, value):
        raise AttributeError("읽기 전용")


class NonData:
    def __get__(self, obj, objtype=None):
        return "클래스의 비데이터 디스크립터"


class T:
    d = Desc()
    nd = NonData()


t = T()
t.__dict__["d"] = "인스턴스 dict"
t.__dict__["nd"] = "인스턴스 dict"

print(t.d)
print(t.nd)
```

두 줄 다 `t.__dict__` 에 값이 들어 있다. 그런데 출력은 이렇다.

```text nolines
클래스의 디스크립터
인스턴스 dict
```

**같은 자리에 같은 방식으로 넣었는데 하나는 인스턴스 값이 이기고 하나는 진다.** 이걸 설명할 수 있으면 이 절의 절반은 이미 아는 것이다.

### 탐색 순서

`obj.x` 는 문법적 설탕이 아니다. `type(obj).__getattribute__(obj, 'x')` 를 호출한다. 그 안에서 벌어지는 일은 이렇다.

```text nolines
obj.x
  │
  ▼
type(obj).__getattribute__(obj, 'x')
  │
  ├── 1  type(obj).__mro__ 를 훑어 'x' 를 찾아 둔다 (찾아만 두고 반환하지 않는다)
  ├── 2  찾은 것이 data descriptor 라면 -> __get__() 을 호출하고 끝
  ├── 3  obj.__dict__ 에 'x' 가 있으면 -> 그 값을 반환하고 끝
  ├── 4  1에서 찾은 것이 있으면 -> non-data descriptor 면 __get__(), 아니면 그대로 반환
  ├── 5  type(obj).__getattr__ 이 있으면 -> 호출
  │
  ▼
AttributeError
```

결정적인 것은 **1번이 3번보다 먼저**라는 사실이다. 클래스를 먼저 뒤진다. 다만 클래스에서 찾은 것이 **데이터 디스크립터**(`__get__` 과 `__set__`/`__delete__` 를 함께 가진 객체)일 때만 인스턴스 딕셔너리를 건너뛰고 즉시 이긴다. `Desc` 는 `__get__` + `__set__` 이라 데이터 디스크립터고, `NonData` 는 `__get__` 만 있어 비데이터 디스크립터다.

`property` 는 항상 `__get__`/`__set__`/`__delete__` 를 전부 가진다. **그래서 property는 언제나 데이터 디스크립터고, 인스턴스 딕셔너리로는 절대 덮을 수 없다.** 반대로 **함수는 `__get__` 만 가진 비데이터 디스크립터**라 `obj.method = something` 으로 인스턴스별 교체가 된다. 이 둘이 다르게 동작하는 이유가 여기 하나뿐이다.

```pyrepl
>>> class C:
...     @property
...     def v(self): return "prop"
...
>>> c = C()
>>> c.__dict__['v'] = "hacked"
>>> c.__dict__
{'v': 'hacked'}
>>> c.v
'prop'
>>> c.v = 1
Traceback (most recent call last):
  ...
AttributeError: property 'v' of 'C' object has no setter
```

왜 이렇게 복잡한가. 인스턴스 dict를 먼저 보게 하면 `property` 가 무의미해진다 — 세터에서 검증을 해도 `obj.__dict__['x'] = -1` 로 우회되니까. 반대로 **전부** 클래스 우선으로 하면 메서드를 인스턴스별로 바꿔 끼우는 것(몽키패칭, 프록시)이 불가능해진다. 그래서 파이썬은 **"클래스가 `__set__` 을 정의해 소유권을 주장했으면 클래스가 이기고, 아니면 인스턴스가 이긴다"** 로 타협했다. 데이터 디스크립터 우선순위는 이 타협의 이름이다. 프로토콜 자체는 [3.3 디스크립터](#/descriptors)에서 전부 뜯는다.

::: warn 특수 메서드는 이 경로를 타지 않는다
`len(obj)` 는 `obj.__len__()` 이 아니다. **타입에서 직접** 찾고 인스턴스 딕셔너리를 아예 보지 않는다.

```pyrepl
>>> class Z:
...     def __len__(self): return 1
...
>>> z = Z()
>>> z.__len__ = lambda: 99
>>> len(z)
1
>>> z.__len__()
99
```

이유는 성능이다. 모든 연산자마다 인스턴스 dict를 뒤지면 파이썬은 훨씬 느려진다. [1.14 특수 메서드](#/dunder)에서 다시 만난다.
:::

## 클래스 변수와 인스턴스 변수

이제 탐색 순서를 알았으니 가장 흔한 함정이 저절로 설명된다.

```python title="counter.py"
class K:
    n = 0

    def inc(self):
        self.n += 1          # 함정
```

```pyrepl
>>> k1, k2 = K(), K()
>>> k1.inc(); k1.inc()
>>> k1.n, k2.n, K.n
(2, 0, 0)
>>> k1.__dict__
{'n': 2}
>>> k2.__dict__
{}
```

`self.n += 1` 은 `self.n = self.n + 1` 이다. **오른쪽 읽기는 클래스에서 찾고**(`K.n` = 0), **왼쪽 쓰기는 인스턴스에 만든다**. 첫 대입 순간 `k1` 에 `n` 이라는 인스턴스 속성이 새로 생겨 클래스 변수를 그림자처럼 가린다. `K.n` 은 영원히 0이다.

핵심은 비대칭이다. **속성 읽기는 MRO를 타지만, 속성 쓰기는 인스턴스에 그냥 꽂는다.**

::: danger 가변 클래스 변수는 모든 인스턴스가 공유한다
불변 클래스 변수에서는 위 함정이 오히려 안전판이 된다. 대입이 인스턴스를 만들어 주니까. 가변이면 정반대다.

```python
class Reg:
    items = []              # ❌

    def add(self, x):
        self.items.append(x)   # 대입이 아니라 '수정'이다
```

```pyrepl
>>> a, b = Reg(), Reg()
>>> a.add(1); b.add(2)
>>> a.items, b.items, Reg.items
([1, 2], [1, 2], [1, 2])
>>> a.items is Reg.items
True
>>> a.__dict__
{}
```

`self.items.append(x)` 에는 **대입이 없다.** `self.items` 를 읽어서(→ 클래스 변수를 찾아서) 그 객체를 제자리 수정할 뿐이다. 인스턴스 dict는 영원히 비어 있고, 리스트 하나를 전 인스턴스가 나눠 쓴다. [1.1 객체, 이름, 참조](#/objects-names)의 가변 기본값 함정과 완전히 같은 병이다.

```python
class Reg:
    def __init__(self):
        self.items = []        # ✅ 인스턴스마다 새 리스트
```
:::

그렇다고 클래스 변수가 나쁜 게 아니다. **모든 인스턴스가 같은 값을 갖고 그 값이 불변이면** 클래스 변수가 정답이다. `color = "red"` 를 클래스에 두면 72 B, `self.color = "red"` 로 인스턴스마다 두면 80 B다(20만 개 `tracemalloc` 실측). 8 B 차이지만 인스턴스 100만 개면 8 MB다.

판단 기준은 하나다. **"인스턴스마다 달라질 수 있는가?"** 아니면 클래스 변수.

## 인스턴스 `__dict__` 의 진짜 비용

한 층 더 내려간다. "인스턴스 속성은 딕셔너리에 들어간다"는 설명은 2011년쯤엔 맞았다. 지금은 절반만 맞다.

```pyrepl
>>> class Plain:
...     def __init__(self, x, y, z):
...         self.x, self.y, self.z = x, y, z
...
>>> p = Plain(1, 2, 3)
>>> p.__dict__
{'x': 1, 'y': 2, 'z': 3}
```

그럼 인스턴스마다 진짜 dict 객체가 하나씩 있을까? **아니다.** `sys.getsizeof` 로 확인하려 들면 즉시 함정에 빠진다.

::: danger getsizeof 는 인스턴스에 대해 거짓말한다
속성이 1개든 8개든 `sys.getsizeof(인스턴스)` 는 48로 고정이다.

```pyrepl
>>> import sys
>>> class A1:
...     def __init__(self): self.a = 1
...
>>> class A8:
...     def __init__(self):
...         self.a = self.b = self.c = self.d = 1
...         self.e = self.f = self.g = self.h = 1
...
>>> sys.getsizeof(A1()), sys.getsizeof(A8())
(48, 48)
```

`getsizeof` 는 `type.__basicsize__` 를 기반으로 답한다. 그런데 CPython 3.11+ 의 일반 클래스는 속성 값을 **인라인 값 배열**(inline values)에 담고, 이 배열은 `__basicsize__` 에 잡히지 않는다.

```pyrepl
>>> A1.__basicsize__, A1.__dictoffset__, A1.__weakrefoffset__
(16, -1, -32)
```

`__dictoffset__` 이 `-1` 이면 **관리형 딕셔너리**(managed dict)라는 뜻이다. 값은 객체 본체 앞쪽 프리헤더와 인라인 배열에 흩어져 있고 `getsizeof` 는 그걸 세지 않는다.

**개별 객체 크기를 `getsizeof` 로 재지 마라.** N개를 만들어 놓고 `tracemalloc` 으로 총량을 재는 게 3.11 이후의 유일한 정직한 측정법이다. ([5.2 메모리 모델](#/memory))
:::

정직하게 재면 이렇게 나온다.

```python title="honest_measure.py"
import tracemalloc

N = 200_000

def per_instance(factory):
    tracemalloc.start()
    objs = [factory() for _ in range(N)]
    used = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    del objs
    return used / N - 8          # 리스트 포인터 8 B 제외
```

| 속성 개수 | 일반 클래스 | `__slots__` |
| --- | --- | --- |
| 1 | 80 B | 40 B |
| 3 | 96 B | 56 B |
| 5 | 112 B | 72 B |
| 8 | 144 B | 96 B |

일반 클래스가 속성 3개에 96 B다. 인스턴스마다 진짜 dict 하나(빈 dict가 이미 64 B)를 달고 있다면 나올 수 없는 숫자다.

::: deep 키 공유 딕셔너리와 인라인 값
CPython은 같은 클래스의 인스턴스들이 **거의 항상 같은 속성 이름 집합**을 갖는다는 점을 이용한다.

- **키 공유**(key-sharing, PEP 412, 3.3+): 속성 이름과 해시 테이블 구조는 **클래스에 딱 한 벌만** 저장한다. 인스턴스는 값 포인터 배열만 갖는다.
- **인라인 값**(inline values, 3.11+): 그 값 배열마저 별도 할당이 아니라 **객체 본체에 함께 할당**한다. dict 객체는 아예 만들어지지 않는다.

`p.__dict__` 를 읽으면 그때서야 인라인 값 배열을 감싸는 dict 객체가 **물질화**(materialize)된다. **`__dict__` 는 대부분 존재하지 않다가 당신이 보려는 순간 생긴다.** 대가는 크다.

```python title="__dict__ 를 건드리면"
def with_dict():
    o = Plain(1, 2, 3)
    o.__dict__          # 이 한 줄이 dict 객체를 만든다
    return o
```

인스턴스당 실측: `Plain(1, 2, 3)` **96 B** → `__dict__` 접근 후 **160 B**. 속성 3개짜리 객체를 `vars(obj)` 로 한 번 훑었다는 이유만으로 **67% 늘어난다.** 대용량 객체를 `{**vars(o)}` 로 직렬화하는 코드가 갑자기 메모리를 먹는 이유가 이것이다.

관찰하기도 까다롭다. 인스턴스를 하나씩 만들면서 `sys.getsizeof(p.__dict__)` 를 찍으면 3.14.5에서 296, 288, 280… 으로 8씩 **줄어들다** 26번째부터 96으로 고정된다. 미리 30개 만들어 두고 재면 처음부터 96이다. 키 공유 구조가 자리 잡아 가는 과도기가 그대로 노출되는 것이다. **이런 숫자에 의존하는 코드나 테스트를 쓰지 마라.**
:::

## `__slots__`

`__slots__` 는 클래스에게 **"내 인스턴스가 가질 속성은 이게 전부다"** 라고 선언하는 것이다. 그러면 CPython은 dict를 위한 자리를 아예 만들지 않고, 속성마다 고정된 오프셋을 배정한다.

```python title="slots.py"
class Plain:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Slotted:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
```

```text nolines
Plain(1, 2, 3)  = 96 B              Slotted(1, 2, 3) = 56 B

  ┌──────────────────┐                ┌──────────────────┐
  │ GC head          │                │ GC head          │
  ├──────────────────┤                ├──────────────────┤
  │ pre-header       │                │ PyObject_HEAD    │
  │  values / dict   │                ├──────────────────┤
  │  weakref         │                │ slot x   -> 1    │
  ├──────────────────┤                │ slot y   -> 2    │
  │ PyObject_HEAD    │                │ slot z   -> 3    │
  ├──────────────────┤                └──────────────────┘
  │ inline values    │
  │  x -> 1          │
  │  y -> 2          │
  │  z -> 3          │
  └──────────────────┘
```

인스턴스가 지는 부담만 그린 그림이다. 키 공유 이름 테이블과 슬롯 이름은 양쪽 다 클래스에 한 벌씩만 있다.

::: perf 절감폭은 1.5~2배지, 5배가 아니다
| 속성 개수 | 일반 | `__slots__` | 비율 |
| --- | --- | --- | --- |
| 1 | 80 B | 40 B | 2.00배 |
| 3 | 96 B | 56 B | 1.71배 |
| 5 | 112 B | 72 B | 1.56배 |
| 8 | 144 B | 96 B | 1.50배 |

(Python 3.14.5 / Windows, 20만 개 `tracemalloc` 실측)

인터넷에는 `__slots__` 가 메모리를 4~5배 줄인다는 글이 널려 있다. **그건 인라인 값이 없던 시절 이야기다.** 지금은 일반 클래스가 이미 최적화돼 있어 격차가 좁다.

속성이 많아질수록 비율이 1에 수렴하는 것도 봐라. `__slots__` 가 없애는 것은 **속성 개수와 무관한 고정 오버헤드 40 B**(dict/values 포인터 + 물질화 여지)다. 속성이 많으면 그 40 B의 비중이 줄어든다.

**속도는 거의 차이 없다.** `timeit.repeat` (300만 회 호출 × 7반복, `gc.disable()`, 최솟값 채택)으로 `pass` 기준선(3.5~3.6 ns)을 뺀 순수 비용을 재면 일반 속성 `p.x` 가 **3.4~3.8 ns**, 슬롯 속성 `s.x` 가 **3.4~3.5 ns** 다. 두 값은 반복 시행마다 순서가 뒤바뀔 만큼 붙어 있어, "슬롯이 항상 더 빠르다/느리다" 라고 단정할 근거가 없다. 3.11의 특수화 인터프리터가 `LOAD_ATTR` 을 `LOAD_ATTR_INSTANCE_VALUE` 로 특수화해서, 일반 클래스도 인라인 배열에서 오프셋으로 바로 꺼내기 때문이다. **`__slots__` 를 속도 때문에 쓴다는 말은 3.11 이후로 근거가 없다.** ([3.7 바이트코드](#/bytecode))
:::

### `__slots__` 의 제약

`__slots__` 를 넣는 순간 딸려 오는 것들이 많다. 이게 진짜 비용이다.

**1. 상속 체인의 한 곳만 빠져도 전부 무효다.**

```pyrepl
>>> class S:
...     __slots__ = ('x',)
...
>>> class Sub(S):          # __slots__ 없음
...     pass
...
>>> b = Sub()
>>> b.y = 1                # 되네?
>>> b.__dict__
{'y': 1}
```

**`__slots__` 는 상속되지 않는다.** 자식이 선언하지 않으면 자식에게 `__dict__` 가 다시 붙고 절감은 0이 된다. 반대로 부모에 `__slots__` 가 없으면 자식이 뭘 선언하든 소용없다. 상속 체인 **전부**가 선언해야 하고, 추가 속성이 없는 중간 클래스에는 `__slots__ = ()` 를 명시해야 한다.

**2. 다중 상속에서 레이아웃이 충돌한다.**

```pyrepl
>>> class A: __slots__ = ('a',)
>>> class B: __slots__ = ('b',)
>>> class C(A, B): __slots__ = ()
Traceback (most recent call last):
  ...
TypeError: multiple bases have instance lay-out conflict
```

슬롯은 고정 오프셋이다. 두 부모가 각자 오프셋을 주장하면 합칠 방법이 없다. **비어 있지 않은 `__slots__` 를 가진 두 클래스는 다중 상속할 수 없다.** 믹스인 설계와 정면으로 부딪힌다.

**3. 약한 참조가 막힌다.**

```pyrepl
>>> import weakref
>>> class W: __slots__ = ('x',)
>>> weakref.ref(W())
Traceback (most recent call last):
  ...
TypeError: cannot create weak reference to 'W' object
```

`__slots__ = ('x', '__weakref__')` 처럼 직접 넣어야 한다. 캐시나 옵저버 패턴에서 이게 조용히 터진다.

**4. `cached_property` 가 죽는다.**

```pyrepl
>>> from functools import cached_property
>>> class S:
...     __slots__ = ('r',)
...     def __init__(self, r): self.r = r
...     @cached_property
...     def area(self): return 3.14 * self.r ** 2
...
>>> S(2).area
Traceback (most recent call last):
  ...
TypeError: No '__dict__' attribute on 'S' instance to cache 'area' property.
```

`cached_property` 는 **인스턴스 `__dict__` 에 계산 결과를 써 넣는 것**으로 캐싱을 구현한다. dict가 없으면 캐시할 곳이 없다.

**5. 같은 이름의 클래스 변수를 둘 수 없다.**

```pyrepl
>>> class Bad:
...     __slots__ = ('x',)
...     x = 5
Traceback (most recent call last):
  ...
ValueError: 'x' in __slots__ conflicts with class variable
```

슬롯은 클래스에 디스크립터를 만든다. 같은 이름의 클래스 변수를 두면 그걸 덮어써 버리니 파이썬이 아예 막는다. **결과적으로 `__slots__` 클래스는 기본값을 클래스 변수로 줄 수 없다.**

::: deep 슬롯은 사실 데이터 디스크립터다
`__slots__` 는 마법이 아니다. 클래스 생성 시점에 이름마다 `member_descriptor` 를 만들어 클래스에 꽂는 것이 전부다.

```pyrepl
>>> class D:
...     __slots__ = ('x',)
...
>>> D.x
<member 'x' of 'D' objects>
>>> hasattr(type(D.x), '__set__')
True
>>> D().x
Traceback (most recent call last):
  ...
AttributeError: 'D' object has no attribute 'x'
```

`__set__` 이 있으니 **데이터 디스크립터**다. 이 절 첫머리 탐색 순서의 2번에 걸린다. 그래서 `__slots__ = ('x', '__dict__')` 처럼 둘이 공존해도 슬롯이 항상 이긴다. 값이 없는 슬롯을 읽으면 `AttributeError` 다 — C 구조체와 달리 **슬롯은 "비어 있음"(`NULL`) 상태를 가진다.**

그리고 `__slots__` 에 문자열 하나를 주면 문자를 쪼개지 않고 **이름 하나로** 본다. `__slots__ = 'xy'` 는 슬롯 `xy` 하나다. 항상 튜플로 써라.
:::

::: tip __slots__ 를 쓸 때
쓸 값이 있는 경우는 좁다. 셋을 **전부** 만족할 때만 써라.

1. **같은 클래스의 인스턴스를 수십만 개 이상 만든다.** 그래프 노드, 파티클, 파싱된 레코드.
2. **속성 집합이 확정적이다.**
3. **다중 상속이 필요 없다.**

인스턴스 1,000개에서 40 KB 아끼자고 위 제약을 전부 떠안는 건 손해다.

그리고 직접 쓰기보다 `@dataclass(slots=True)` 가 낫다. 슬롯 선언과 필드 선언이 갈라지지 않고 기본값도 정상 동작한다. 필드 2개 기준 실측으로 48 B vs 일반 dataclass 88 B. ([2.6 dataclasses](#/dataclasses))

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Node:
    x: int
    y: int
```
:::

::: cote 코딩테스트에서 클래스는 대체로 손해다
인스턴스 생성 비용 실측(`timeit`, 변수로 넘겨 상수 폴딩을 피한 값, 100만 회):

```text nolines
Plain(a, b, c)         ~70 ns
Slotted(a, b, c)       ~60 ns
namedtuple NT(a,b,c)  ~120 ns
{'x':a,'y':b,'z':c}    ~50 ns
(a, b, c)              ~23 ns
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기·실행마다 흔들리지만 순서는 안정적이다.)

**튜플이 클래스 인스턴스보다 대략 3배 빠르다.** 시험장에서는 클래스를 만들지 마라. 인접 리스트는 `list[list[int]]`, 좌표는 튜플, 우선순위 큐 원소는 `(dist, node)` 튜플이면 끝난다. `namedtuple` 은 가독성이 좋지만 생성이 가장 느리다 — 병목이 아닌 곳에만 써라. [8.3 시간 초과를 피하는 관용구](#/tle)에서 더 다룬다.

::: warn 리터럴 튜플 벤치마크의 함정
`timeit.timeit(lambda: (1, 2, 3), number=...)` 처럼 **리터럴 상수만으로 튜플을 만들면** 컴파일러가 그 튜플 자체를 `co_consts` 에 통째로 넣어 버린다. 매번 새로 만드는 게 아니라 미리 만들어진 상수를 그냥 로드하는 것이라 `pass` 한 줄과 비슷한 속도(수 ns)가 나온다. **실제 값(변수)으로 튜플을 만들 때의 비용**을 재려면 위처럼 지역 변수를 넣어야 한다. [1.1 객체, 이름, 참조](#/objects-names)에서 다룬 상수 폴딩이 여기서도 벤치마크를 왜곡시킨다.
:::

예외: 세그먼트 트리처럼 인스턴스를 몇 개만 만드는 자료구조는 클래스가 낫다. 생성이 몇 번뿐이면 70 ns는 아무것도 아니다.
:::

## `property` — 파이썬이 게터·세터를 안 쓰는 이유

Java 사람들은 필드를 `private` 로 만들고 `getX()`/`setX()` 를 처음부터 단다. 나중에 검증을 넣으려면 API를 바꿔야 하기 때문이다. 파이썬은 그 문제가 없다.

```python title="처음엔 이렇게 시작한다"
class Temp:
    def __init__(self, celsius):
        self.celsius = celsius       # 그냥 공개 속성
```

요구사항이 생겼다. 절대영도 아래는 막아야 한다. **호출부를 한 줄도 안 고치고** 바꿀 수 있다.

```python title="나중에 이렇게 바꾼다"
class Temp:
    def __init__(self, celsius):
        self.celsius = celsius       # 이제 세터를 탄다

    @property
    def celsius(self):
        return self._c

    @celsius.setter
    def celsius(self, v):
        if v < -273.15:
            raise ValueError("절대영도 미만")
        self._c = v

    @property
    def fahrenheit(self):            # 저장하지 않는 계산 속성
        return self._c * 9 / 5 + 32
```

```pyrepl
>>> t = Temp(25)
>>> t.fahrenheit
77.0
>>> Temp(-300)
Traceback (most recent call last):
  ...
ValueError: 절대영도 미만
```

이게 **"단순한 것부터 시작하라"** 라는 파이썬 격언의 실체다. 미리 게터·세터를 다는 것은 일어나지 않을 미래에 대한 세금이다. 필요해지면 그때 `property` 로 바꾸면 된다. 인터페이스가 그대로다.

단, **`property` 는 반드시 클래스에 붙여야 한다.** 인스턴스에 붙이면 아무 일도 안 일어난다.

```pyrepl
>>> class Q: pass
>>> q = Q()
>>> q.p = property(lambda self: 1)
>>> q.p
<property object at 0x0000014E0E10FCE0>
```

디스크립터 프로토콜은 **`type(obj)` 의 MRO에서 찾았을 때만** 발동한다. 인스턴스 딕셔너리에 든 디스크립터는 그냥 객체다.

::: perf property 는 공짜가 아니다
| 접근 | 순수 비용 |
| --- | --- |
| 일반 속성 `p.x` | 3.4~3.8 ns |
| 슬롯 속성 `s.x` | 3.4~3.5 ns |
| 프로퍼티 `r.x` | 11.1~11.3 ns |
| 메서드 호출 `m.get_x()` | 13.0~13.3 ns |

(Python 3.14.5 / Windows, `timeit.repeat` 300만 회 호출 × 7반복을 3세트 반복, `gc.disable()`, `pass` 기준선 3.5~3.6 ns를 뺀 최솟값 범위)

**프로퍼티는 일반 속성보다 대략 3배 느리다.** 파이썬 함수 호출이 한 번 끼기 때문이다. (예전에 흔히 인용되던 "5~6배"는 더 오래된 CPython 버전이나 다른 하드웨어에서의 측정치로 보이며, 이 환경에서는 재현되지 않았다 — 벤치마크 수치는 항상 자신의 환경에서 다시 재라.) 절대값은 10 ns대니 대부분의 코드에서 무의미하지만, 루프 안에서 수천만 번 읽는다면 이야기가 다르다. 관용구는 하나다 — **루프 밖에서 지역 변수로 뽑아라.** [5.3 파이썬 레벨 최적화](#/py-optimize)에서 일반화한다.
:::

### `cached_property`

계산이 비싸고 결과가 안 변하면 `functools.cached_property` 를 쓴다. 동작 원리를 알면 함정도 보인다.

```pyrepl
>>> from functools import cached_property
>>> class P:
...     def __init__(self, r): self.r = r
...     @cached_property
...     def area(self):
...         print("  계산 실행")
...         return 3.14 * self.r ** 2
...
>>> p = P(2)
>>> p.area
  계산 실행
12.56
>>> p.area
12.56
>>> p.__dict__
{'r': 2, 'area': 12.56}
```

두 번째 호출에서 "계산 실행"이 안 찍힌다. **`cached_property` 는 비데이터 디스크립터다** — `__set__` 이 없다. 첫 호출 때 결과를 `p.__dict__['area']` 에 써 넣으면, 그 다음부터는 탐색 순서 3번(인스턴스 dict)이 4번(클래스의 비데이터 디스크립터)보다 먼저 걸려 디스크립터가 아예 호출되지 않는다. **이 절 첫머리의 데이터/비데이터 구분이 표준 라이브러리 설계에 그대로 쓰인 자리다.**

::: danger cached_property 는 무효화되지 않는다
```pyrepl
>>> p.r = 10
>>> p.area
12.56
```

`r` 을 바꿔도 캐시는 그대로다. 아무도 지워 주지 않는다. **의존하는 속성이 절대 안 바뀔 때만 써라.** 바뀔 수 있다면 `del p.area` 로 직접 무효화하거나 애초에 쓰지 마라. 그리고 앞에서 봤듯 `__slots__` 클래스에서는 `TypeError` 다.
:::

## `classmethod` 와 `staticmethod`

둘 다 데코레이터로 쓰지만 하는 일이 전혀 다르다. **`classmethod` 는 첫 인자를 자동으로 채워 주고, `staticmethod` 는 아무것도 안 한다.**

```pyrepl
>>> class Base:
...     @classmethod
...     def create(cls): return cls()
...     @staticmethod
...     def helper(): return "static"
...
>>> class Child(Base): pass
...
>>> type(Base.create()).__name__
'Base'
>>> type(Child.create()).__name__
'Child'
```

**`cls` 는 "정의된 클래스"가 아니라 "호출된 클래스"다.** `Child.create()` 는 `cls` 에 `Child` 를 받는다. 이 하나 때문에 `classmethod` 가 존재한다고 봐도 된다. 대체 생성자를 이걸로 만들면 자식이 자동으로 물려받는다.

```python title="대체 생성자 — classmethod 의 정당한 용도"
class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    @classmethod
    def zero(cls):
        return cls(0, 0)            # Vector 가 아니라 cls


class Vector3(Vector):
    def __init__(self, x, y, z=0):
        super().__init__(x, y)
        self.z = z


Vector3.zero()                      # Vector3 를 만든다. 코드 재작성 없음.
```

`return Vector(0, 0)` 이라고 하드코딩했다면 `Vector3.zero()` 가 `Vector` 를 뱉는다. 조용한 버그다.

::: deep 둘 다 디스크립터다. 하는 일이 다를 뿐
```pyrepl
>>> Base.__dict__['create']
<classmethod(<function Base.create at 0x00000190BF0835E0>)>
>>> Base.create
<bound method Base.create of <class '__main__.Base'>>
>>> Base.__dict__['helper']
<staticmethod(<function Base.helper at 0x00000190BF090300>)>
>>> Base.helper
<function Base.helper at 0x00000190BF090300>
```

`__dict__` 에서 직접 꺼내면 래퍼 객체가 나온다. `Base.create` 로 접근하면 그 객체의 `__get__` 이 불려 **클래스에 바인딩된 메서드**가 나오고, `Base.helper` 는 `__get__` 이 원본 함수를 **그대로** 돌려준다.

즉 `staticmethod` 는 **"평범한 함수가 클래스 안에 있어도 `self` 바인딩을 당하지 않게 막는 방패"** 다. 함수가 비데이터 디스크립터라 자동 바인딩되는 것을, 감싸서 취소하는 것이다. 만들어지는 원리 전체는 [3.3 디스크립터](#/descriptors)에서.

3.10부터는 `staticmethod` 객체 자체도 호출 가능하다. 그전에는 `Base.__dict__['helper']()` 가 `TypeError` 였다.

```pyrepl
>>> sm = staticmethod(lambda: 42)
>>> callable(sm), sm()
(True, 42)
```
:::

그래서 `staticmethod` 는 대부분 불필요하다. `self` 도 `cls` 도 안 쓴다면 **왜 클래스 안에 있어야 하나?** 정당한 이유는 둘뿐이다 — 이름 공간을 묶는 게 문서적으로 명백히 이득이거나(`Path.cwd()`), 자식이 오버라이드할 훅 지점이거나. 파이썬은 Java가 아니다. 클래스가 함수의 컨테이너일 필요가 없다.

## `__init__` 과 `__new__`

`Point(1, 2)` 라고 썼을 때 실제로 불리는 것은 `Point.__call__` 이 아니다. **`type(Point).__call__`**, 즉 `type.__call__` 이다. 그 안이 이렇게 생겼다.

```text nolines
Point(1, 2)
  │
  ▼
type.__call__(Point, 1, 2)
  │
  ├── 1  obj = Point.__new__(Point, 1, 2)      <- 객체를 '만든다'
  │
  ├── 2  isinstance(obj, Point) 인가?
  │        아니면 여기서 끝. __init__ 을 부르지 않는다.
  │
  ├── 3  Point.__init__(obj, 1, 2)             <- 만들어진 객체를 '채운다'
  │
  ▼
obj 반환
```

**`__new__` 는 생성자, `__init__` 은 초기화자다.** 대부분의 경우 `__new__` 는 `object.__new__` 로 충분하고, 당신이 건드릴 일이 없다.

```pyrepl
>>> class N:
...     def __new__(cls, *a, **kw):
...         print("  __new__ 호출, cls =", cls.__name__, "args =", a)
...         return super().__new__(cls)
...     def __init__(self, v):
...         print("  __init__ 호출, v =", v)
...         self.v = v
...
>>> n = N(10)
  __new__ 호출, cls = N args = (10,)
  __init__ 호출, v = 10
```

**같은 인자가 양쪽에 다 간다.** `__new__` 는 그래서 `*args, **kwargs` 를 받아 넘기는 형태가 된다.

::: danger __new__ 가 다른 타입을 반환하면 __init__ 이 조용히 건너뛰어진다
```pyrepl
>>> class M:
...     def __new__(cls, v):
...         return 42
...     def __init__(self, v):
...         print("__init__ 호출됨!")
...
>>> m = M(1)
>>> m, type(m)
(42, <class 'int'>)
```

`__init__` 이 불리지 않았다. 예외도, 경고도 없다. 위 흐름도 2번 때문이다. **`__new__` 에서 실수로 `return` 을 빠뜨리면 `None` 이 반환되고 `__init__` 은 영원히 안 불린다.** 그리고 `M(1)` 은 `None` 을 준다. 디버깅이 지옥이다. `__new__` 를 정의했으면 **반환문을 세 번 확인하라.**
:::

### `__new__` 가 진짜 필요한 경우

**1. 불변 타입을 상속할 때.** 선택이 아니라 필수다. `int`, `str`, `tuple`, `frozenset` 의 값은 객체가 만들어지는 순간 고정된다. `__init__` 이 불릴 때는 이미 늦었다.

```python title="불변 타입 상속"
class Pos(int):
    def __new__(cls, v):
        if v < 0:
            raise ValueError("음수 불가")
        return super().__new__(cls, v)
```

```pyrepl
>>> p = Pos(5)
>>> p, type(p).__name__
(5, 'Pos')
>>> Pos(-1)
Traceback (most recent call last):
  ...
ValueError: 음수 불가
```

`__init__` 으로 하려 들면 이렇게 된다.

```pyrepl
>>> class BadPair(tuple):
...     def __init__(self, a, b):
...         super().__init__()
...
>>> BadPair(1, 2)
Traceback (most recent call last):
  ...
TypeError: tuple expected at most 1 argument, got 2
```

`tuple.__new__` 가 인자 2개를 못 받아 `__init__` 에 닿기도 전에 터진다. 올바른 형태는 `def __new__(cls, a, b): return super().__new__(cls, (a, b))` 다.

그리고 이렇게 만들어도 끝이 아니다.

```pyrepl
>>> p + 1, type(p + 1).__name__
(6, 'int')
```

`int.__add__` 는 `int` 를 반환하도록 C 레벨에 하드코딩돼 있다. 서브클래스를 유지하려면 연산자를 전부 오버라이드해야 한다. **불변 내장 타입 상속은 생각보다 손이 많이 간다.** 대부분은 컴포지션이나 `NewType` 이 정답이다. ([2.5 TypedDict, NamedTuple, Literal, Final](#/typed-containers))

**2. 인스턴스 재사용(싱글턴, 캐싱, 인터닝).** 여기에 유명한 함정이 있다.

::: danger 싱글턴에서 __init__ 이 매번 다시 실행된다
```python title="흔히 보는 (틀린) 싱글턴"
class Config:
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __init__(self):
        self.values = {}          # ❌ 매번 초기화된다
```

```pyrepl
>>> c1 = Config()
>>> c1.values['a'] = 1
>>> c2 = Config()
>>> c1 is c2
True
>>> c1.values
{}
```

**저장한 값이 사라졌다.** `type.__call__` 흐름도의 2번을 보라. `__new__` 가 반환한 객체는 `Config` 의 인스턴스가 맞다. 그러니 3번이 실행된다. `Config()` 를 부를 때마다 `__init__` 이 같은 객체 위에 다시 돈다. 캐싱 `__new__` 를 쓰는 모든 코드가 이 병에 걸린다.

해결책은 애초에 이 패턴을 안 쓰는 것이다. **파이썬에서 싱글턴이 필요한 상황은 거의 없다. 모듈이 이미 싱글턴이다.**

```python
# ✅ 함수 인터페이스가 꼭 필요하면 이걸로 충분하다
from functools import cache

@cache
def get_config():
    return Config()
```

굳이 `__new__` 로 해야 한다면 `__init__` 을 아예 두지 말고 초기화를 `__new__` 안에서 처리하라.
:::

::: warn object.__new__ 의 인자 규칙
```pyrepl
>>> class A:
...     def __new__(cls, v):
...         return super().__new__(cls, v)     # v 를 넘기면?
...     def __init__(self, v): self.v = v
...
>>> A(1)
Traceback (most recent call last):
  ...
TypeError: object.__new__() takes exactly one argument (the type to instantiate)
```

`object.__new__` 는 클래스 하나만 받는다. `super().__new__(cls)` 로 끝내라. 반대로 `__new__` 만 정의하고 `__init__` 을 두지 않은 클래스는 여분 인자를 받아도 된다 — **둘 중 하나라도 오버라이드하면 CPython이 "알아서 처리했겠지" 하고 인자 검사를 느슨하게 한다.**

그리고 `__init__` 은 `None` 외의 것을 반환할 수 없다.

```pyrepl
>>> class R:
...     def __init__(self): return 1
...
>>> R()
Traceback (most recent call last):
  ...
TypeError: __init__() should return None, not 'int'
```
:::

::: hist 왜 두 개로 나뉘어 있나
파이썬 2.2 이전에는 `__new__` 가 없었다. 사용자 클래스가 `int` 나 `str` 을 상속할 수도 없었다. 2.2의 "new-style class"가 내장 타입 상속을 열면서 **불변 타입의 값을 정할 시점**이 필요해졌고, 그게 `__new__` 다.

2단계로 나뉜 이유는 두 단계가 **서로 다른 클래스에서 올 수 있어야** 하기 때문이다. `Pos` 는 `__new__` 만 정의하고 `__init__` 은 `int` 것을 쓴다. 하나로 합쳐져 있었다면 불가능하다.

일상적인 클래스에서 `__new__` 를 만지고 있다면 십중팔구 잘못된 길이다.
:::

## 컴파일러가 당신의 `__init__` 을 읽고 있다

마지막으로 한 층 더. 3.14의 클래스 딕셔너리를 열어 보면 낯선 키가 있다.

```pyrepl
>>> class Point:
...     dim = 2
...     def __init__(self, x, y):
...         self.x = x
...         self.y = y
...
>>> list(Point.__dict__)
['__module__', '__firstlineno__', 'dim', '__init__', '__static_attributes__', '__dict__', '__weakref__', '__doc__']
>>> Point.__static_attributes__
('x', 'y')
```

`__static_attributes__` 는 3.13에서 추가됐다. **컴파일러가 메서드 본문의 `self.이름 = ...` 를 전부 긁어모아 만든 튜플**이다. 키 공유 딕셔너리의 이름 테이블을 처음부터 맞는 크기로 잡기 위한 정보다. 앞 절에서 본 96 B라는 숫자는 이 정적 분석 덕분에 나온다.

`Point.__dict__` 가 `mappingproxy` 라는 읽기 전용 뷰인 것도 이유가 있다. `Point.b = 2` 는 되지만 `Point.__dict__['b'] = 2` 는 `TypeError` 다. 클래스 속성이 바뀌면 그 클래스와 모든 자식의 **메서드 캐시를 무효화**하고 특수화된 바이트코드를 되돌려야 하는데, `type.__setattr__` 이 그 뒷정리를 한다. dict를 직접 고치면 그 훅을 건너뛰어 인터프리터가 낡은 캐시를 믿게 된다. 그래서 아예 막아 놨다. 클래스 생성 과정을 가로채는 이야기는 [3.4 메타클래스](#/metaclass)에서 한다.

## 요약

- **속성 읽기 순서는 데이터 디스크립터 → 인스턴스 `__dict__` → 클래스에서 찾은 값 → `__getattr__` 이다.** `property` 가 인스턴스 dict를 이기고 `cached_property` 가 지는 이유가 전부 여기서 나온다.
- **읽기는 MRO를 타고 쓰기는 인스턴스에 꽂는다.** 이 비대칭이 `self.n += 1` 함정을 만든다. 대입이 없는 가변 클래스 변수는 전 인스턴스가 공유한다.
- **3.11+ 의 일반 인스턴스에는 dict가 없다.** 키 공유 + 인라인 값이고, `__dict__` 를 읽는 순간 물질화되며 96 B → 160 B가 된다. `sys.getsizeof(인스턴스)` 는 거짓말한다 — `tracemalloc` 으로 총량을 재라.
- **`__slots__` 의 절감은 1.5~2배지 5배가 아니다.** 속도 이득은 사실상 0. 대신 상속·다중상속·weakref·`cached_property`·클래스 변수 기본값을 전부 포기한다. 인스턴스 수십만 개가 아니면 쓰지 마라.
- **`property` 는 나중에 넣어도 호출부가 안 깨진다.** 미리 게터·세터를 달지 마라. 비용은 접근당 10 ns.
- **`classmethod` 의 `cls` 는 호출된 클래스다.** 대체 생성자에 쓰면 상속이 저절로 따라온다. `staticmethod` 는 대부분 모듈 함수가 맞다.
- **`__new__` 는 만들고 `__init__` 은 채운다.** `__new__` 가 필요한 경우는 불변 타입 상속과 인스턴스 재사용, 둘뿐이다.

::: quiz 연습문제
1. 다음 출력을 **먼저 예측한 뒤** 확인하라. 틀렸다면 탐색 순서 어느 단계에서 갈렸는가.

   ```python
   class A:
       tags = []
       count = 0

       def add(self, t):
           self.tags.append(t)
           self.count += 1

   a, b = A(), A()
   a.add("x")
   b.add("y")
   print(a.tags, a.count)
   print(b.tags, b.count)
   print(A.tags, A.count)
   print(a.__dict__, b.__dict__)
   ```

2. 아래 클래스는 `__slots__` 를 선언했는데도 메모리가 전혀 안 준다. 이유가 **두 가지** 있다. 찾아 고쳐라.

   ```python
   class Base:
       def __init__(self, x):
           self.x = x

   class Node(Base):
       __slots__ = ("left", "right")
   ```

3. `cached_property` 가 `__set__` 을 정의했다면 무슨 일이 벌어졌을지 탐색 순서로 설명하라.

4. 다음이 `None` 을 출력하는 이유는? 고쳐라.

   ```python
   class Wrapper:
       def __new__(cls, value):
           obj = super().__new__(cls)
           obj.value = value

       def __repr__(self):
           return f"Wrapper({self.value})"

   print(Wrapper(3))
   ```

5. **깊이 생각해 볼 문제.** `__slots__` 클래스와 `@dataclass(frozen=True)` 클래스 모두 속성을 마음대로 못 붙인다. 하지만 막는 메커니즘이 다르다. 각각 무엇으로 막는지, 그리고 아래가 왜 통하는지 설명하라.

   ```python
   from dataclasses import dataclass

   @dataclass(frozen=True)
   class F:
       x: int

   f = F(1)
   object.__setattr__(f, "x", 99)     # 이게 왜 되는가?
   print(f)
   ```
:::

**다음 절**: [1.13 상속, MRO, 컴포지션](#/inheritance) — 이 절에서 "MRO를 훑는다"고 넘어간 그 순서가 어떻게 정해지는가. C3 선형화와 `super()` 의 진짜 의미.
