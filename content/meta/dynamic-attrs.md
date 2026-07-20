# 3.5 __getattr__ 계열과 동적 속성

::: lead
DB 연결, 설정 객체, ORM의 필드 — 이런 것들은 흔히 "쓰기 전엔 존재하지 않다가, 처음 건드리는 순간 나타나는" 것처럼 동작한다. 이건 마법이 아니다. 파이썬이 `obj.x` 라는 한 줄 뒤에 숨겨 둔 훅(hook) 몇 개를 이용한 것이다. 이 절은 그 훅 — `__getattr__`, `__getattribute__`, `__setattr__` — 을 하나씩 직접 켜 보고, 언제 불리고 언제 안 불리는지를 실행으로 확인한다. [1.19 import](#/imports)에서 예고했던 "모듈 레벨 `__getattr__` 을 클래스 레벨로 확장하는 이야기"도 여기서 끝을 낸다.
:::

## 문제: 만들기 비싼 자원을 미루고 싶다

DB 연결을 예로 들자. 객체를 만드는 순간 실제로 연결을 맺으면, 그 객체를 만들기만 하고 한 번도 쓰지 않는 코드 경로에서도 비용을 낸다.

```python title="비용을 미루고 싶은 상황"
class DBConnection:
    def __init__(self, dsn):
        print(f"실제 연결 수립: {dsn}")   # 비싸다고 가정
        self.dsn = dsn
```

이상적으로는 "객체는 지금 만들되, 진짜 연결은 처음 속성에 접근하는 순간까지 미룬다"를 원한다. 이걸 하려면 **속성 접근이라는 행위 자체를 가로챌 수 있어야 한다.** 파이썬은 그걸 위한 훅을 세 개 준다. `__getattr__`, `__getattribute__`, `__setattr__`. 셋의 차이를 정확히 모르면 이 패턴은 반드시 무한 재귀나 조용한 버그로 끝난다.

## `__getattr__`: 실패했을 때만 켜지는 스위치

[1.14 특수 메서드](#/dunder)에서 이미 프록시 예제로 `__getattr__` 을 한 번 만났다. 그 절의 핵심은 "던더는 `__getattr__` 을 거치지 않는다"였다. 여기서는 `__getattr__` 자체가 **언제 불리는가**를 정확히 본다.

```python title="getattr_demo.py"
class A:
    def __init__(self):
        self.x = 1

    def __getattr__(self, name):
        print(f"  __getattr__({name!r}) 호출됨")
        return f"<no {name}>"


a = A()
print(a.x)   # 정상 탐색으로 찾아진다
print(a.y)   # 정상 탐색 실패 -> 여기서만 호출된다
```

```text nolines
1
  __getattr__('y') 호출됨
<no y>
```

(3.14.5 실측.) `a.x` 에서는 아무것도 찍히지 않는다. **`__getattr__` 은 인스턴스 `__dict__` 와 클래스(그리고 MRO)를 다 뒤진 다음, 그래도 못 찾았을 때만 호출되는 최후의 수단이다.** [1.12 클래스와 데이터 모델](#/classes)에서 다룬 속성 탐색 순서의 맨 마지막 단계가 바로 이것이다.

::: note 이름이 오해를 부른다
`__getattr__` 은 "속성을 가져오는 메서드"가 아니라 "속성을 못 찾았을 때 대신 실행되는 폴백"이다. 정상적으로 찾아지는 속성에는 절대 관여하지 않는다. `getattr(obj, name, default)` 내장 함수와 이름이 비슷해서 자주 헷갈리는데, 관계는 있지만 같은 것이 아니다.
:::

## `__getattribute__`: 예외 없이 항상 켜지는 스위치

`__getattr__` 옆에 있는 `__getattribute__` 는 이름이 세 글자 다를 뿐인데 동작은 정반대다. **성공하든 실패하든, 모든 점(`.`) 속성 접근이 반드시 이걸 통과한다.**

```python title="getattribute_demo.py"
class B:
    def __init__(self):
        self.x = 1

    def __getattribute__(self, name):
        print(f"  __getattribute__({name!r}) 호출됨")
        return object.__getattribute__(self, name)


b = B()
print(b.x)
try:
    print(b.y)
except AttributeError as e:
    print("AttributeError:", e)
```

```text nolines
  __getattribute__('x') 호출됨
1
  __getattribute__('y') 호출됨
AttributeError: 'B' object has no attribute 'y'
```

(3.14.5 실측.) `b.x` 접근 때도 찍혔다는 걸 놓치지 마라. 심지어 `b.y` 처럼 결국 실패하는 접근도 **`__getattribute__` 를 통과한 뒤에** 실패한다 — `AttributeError` 를 던지는 것도 결국 `object.__getattribute__` 내부에서 일어나는 일이기 때문이다.

이 안에서 `object.__getattribute__(self, name)` 을 호출한 이유가 중요하다. 저게 바로 [1.12 클래스와 데이터 모델](#/classes)에서 본 "MRO 훑기 → 데이터 디스크립터 → 인스턴스 `__dict__` → 비데이터 디스크립터 → `__getattr__`" 전체 알고리즘의 진짜 구현체다. `__getattribute__` 를 오버라이드한다는 건 **그 알고리즘 전체를 손에 쥔다**는 뜻이다. 원래 동작을 유지하고 싶으면 반드시 `object.__getattribute__` 를 불러 위임해야 한다.

::: perf __getattribute__ 오버라이드는 모든 접근에 세금을 매긴다
`__getattr__` 은 실패할 때만 켜지니 정상 경로에는 공짜다. `__getattribute__` 는 다르다. 그냥 통과시키기만 해도 매 접근마다 파이썬 함수 호출 한 겹이 끼어든다.

```python title="세 가지를 100만 번씩"
import timeit

setup = """
class Plain:
    def __init__(self): self.x = 1

class WithGetattribute:
    def __init__(self): self.x = 1
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)

class WithGetattr:
    def __init__(self): self.x = 1
    def __getattr__(self, name):
        return None

p = Plain(); g = WithGetattribute(); a = WithGetattr()
"""
for stmt in ["p.x", "g.x", "a.x"]:
    t = min(timeit.repeat(stmt, setup, number=1_000_000, repeat=5))
    print(f"{stmt:10s} {t:.4f}s / 100만회")
```

```text nolines
p.x        0.0059s / 100만회      <- 오버라이드 없음
g.x        0.0433s / 100만회      <- __getattribute__ 오버라이드, 약 7.3배
a.x        0.0057s / 100만회      <- __getattr__ 은 x 를 정상적으로 찾으니 공짜
```

(Python 3.14.5 / Windows 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.) `WithGetattr` 은 `__getattr__` 을 정의만 했을 뿐 `x` 접근에서는 한 번도 안 불렸으니 `Plain` 과 사실상 같은 속도다. `WithGetattribute` 는 아무 일도 안 하고 그대로 위임했는데도 **7배** 넘게 느려졌다. `dis` 로 보면 이 차이는 바이트코드 수준에서는 전혀 안 드러난다.

```pyrepl
>>> import dis
>>> def access(obj): return obj.x
>>> dis.dis(access)
  1           RESUME                   0
              LOAD_FAST_BORROW         0 (obj)
              LOAD_ATTR                0 (x)
              RETURN_VALUE
```

`obj.x` 는 어떤 클래스든 항상 같은 `LOAD_ATTR` 명령 하나로 컴파일된다. 세 클래스의 차이는 이 명령이 **런타임에** `type(obj).__getattribute__` 슬롯을 통해 무엇을 실행하느냐에 있다 — 그래서 소스만 보고는 이 7배 차이가 안 보인다. 실행해야 보인다.

**결론**: 정상 경로를 건드릴 필요가 없으면 `__getattribute__` 대신 `__getattr__` 을 써라. 정말 모든 접근에 개입해야 할 때만(로깅, 접근 통제, 프록시의 극단적인 형태) `__getattribute__` 를 쓰고, 그 비용을 감수해라.
:::

## `__setattr__`: 할당을 가로챈다

읽기에 `__getattr__`/`__getattribute__` 짝이 있듯, 쓰기에는 `__setattr__` 이 있다. 이건 `__getattr__` 과 달리 **폴백이 아니라 항상 켜지는 스위치**다. `obj.attr = value` 형태의 대입은 예외 없이 전부 `type(obj).__setattr__(obj, 'attr', value)` 를 거친다.

```python title="setattr_demo.py"
class Validated:
    def __setattr__(self, name, value):
        if name == "age" and value < 0:
            raise ValueError(f"age는 음수일 수 없다: {value}")
        print(f"  __setattr__({name!r}, {value!r})")
        object.__setattr__(self, name, value)   # 실제 저장은 object에 위임


v = Validated()
v.age = 30
print(v.age)
v.age = -5
```

```text nolines
  __setattr__('age', 30)
30
Traceback (most recent call last):
  ...
ValueError: age는 음수일 수 없다: -5
```

(3.14.5 실측.) 이게 검증 로직을 property의 세터 없이도 클래스 전체에 걸 수 있는 방법이다. `pydantic` 이나 `attrs` 가 검증을 붙이는 원리도 결국 이 훅(또는 [3.3 디스크립터](#/descriptors)) 위에 있다.

::: danger 저장 자체를 self.name = value 로 하면 즉시 무한 재귀
`object.__setattr__` 을 안 쓰고 그냥 `self.name = value` 라고 쓰면, 그 대입 자체가 다시 `__setattr__` 을 호출한다. 끝없이.

```python
class WorseValidated:
    def __setattr__(self, name, value):
        self.name = value    # ❌ 자기 자신을 다시 호출한다


w = WorseValidated()
w.x = 1
```

```text nolines
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

(3.14.5 실측, `sys.setrecursionlimit(200)` 으로 빨리 재현.) `__setattr__` 안에서 실제 저장을 하려면 **반드시** `object.__setattr__(self, name, value)` 를 쓰거나, `self.__dict__[name] = value` 로 딕셔너리를 직접 건드려야 한다. 자기 자신을 우회 없이 다시 부르면 반드시 이렇게 죽는다.
:::

## 무한 재귀라는 함정

방금 `__setattr__` 에서 본 재귀는 사실 `__getattr__`/`__getattribute__` 에서 훨씬 더 흔하게, 그리고 훨씬 더 교묘하게 일어난다. 원리는 하나다. **훅 내부에서 `self.무언가` 에 접근했는데, 그 `무언가` 를 찾는 과정이 다시 같은 훅을 호출하면 재귀가 멈추지 않는다.**

가장 흔한 실수는 `__getattr__` 안에서 **존재하지 않는** 속성을 잘못 참조하는 것이다.

```python title="getattr 재귀 함정"
class Bad:
    def __init__(self, value):
        self.value = value

    def __getattr__(self, name):
        return self.missing_attr   # 오타! 없는 속성 -> 다시 __getattr__ 호출
```

```pyrepl
>>> b = Bad(1)
>>> b.anything
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

`__getattribute__` 는 훨씬 더 잘 걸린다. **정상적으로 존재하는 속성을 `self.x` 형태로 참조하는 것조차 재귀를 일으킨다** — `self.x` 라는 접근 자체가 다시 `__getattribute__` 를 부르기 때문이다.

```python title="getattribute 재귀 함정 — 이건 있는 속성도 위험하다"
class BadGetattribute:
    def __init__(self, value):
        self.value = value

    def __getattribute__(self, name):
        return self.value          # ❌ self.value 도 __getattribute__를 다시 탄다
```

```pyrepl
>>> bg = BadGetattribute(1)
>>> bg.value
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

`__getattribute__` 안에서 속성을 읽을 때는 **반드시 `object.__getattribute__(self, name)` 을 거쳐야 한다.** 이게 이 절 앞부분에서 계속 그렇게 쓴 이유다.

::: warn 실전에서 훨씬 자주 만나는 형태: __init__ 이 아직 안 끝났을 때
프록시를 만들 때 진짜로 자주 걸리는 경우는 오타가 아니라 **초기화 순서**다. `copy.copy`, `pickle` 역직렬화, 일부 ORM은 `__init__` 을 거치지 않고 `object.__new__` 로 빈 인스턴스를 만든 뒤 나중에 속성을 채운다.

```python
class Proxy:
    def __init__(self, target):
        self._target = target

    def __getattr__(self, name):
        return getattr(self._target, name)


p = object.__new__(Proxy)   # __init__ 이 아직 실행 안 됨 -> self._target 이 없다
p.anything
```

```text nolines
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

(3.14.5 실측.) `_target` 이 없으니 `self._target` 조회가 실패하고 → `__getattr__` 이 다시 불리고 → 그 안에서 또 `self._target` 을 찾고 → 다시 실패 → 무한히 반복된다. 겉보기엔 멀쩡한 코드가 "이 객체를 어떻게 만드느냐"에 따라 죽는다. `__getattr__` 안에서 `self.` 로 접근하는 이름은 **항상 존재가 보장되는 이름**이어야 한다. 확신이 안 서면 `self.__dict__.get('_target')` 처럼 실패해도 재귀하지 않는 경로로 확인해라.
:::

## 프록시 패턴 제대로 만들기

지금까지의 세 훅을 합치면 이 절 도입부의 "지연 연결"을 정확히 구현할 수 있다.

```python title="lazy_proxy.py"
class LazyConnection:
    def __init__(self, dsn):
        print(f"  [진짜 연결 생성] dsn={dsn!r}")
        self.dsn = dsn

    def query(self, sql):
        return f"({self.dsn}) 실행: {sql}"


class LazyProxy:
    """첫 속성 접근 전까지 실제 객체를 만들지 않는다."""

    def __init__(self, factory):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_target", None)

    def _ensure(self):
        if self._target is None:                      # _target은 __dict__에 이미 있다 -> 정상 탐색으로 찾아짐
            object.__setattr__(self, "_target", self._factory())
        return self._target

    def __getattr__(self, name):
        return getattr(self._ensure(), name)

    def __setattr__(self, name, value):
        setattr(self._ensure(), name, value)


conn = LazyProxy(lambda: LazyConnection("postgres://localhost/db"))
print("프록시는 만들어졌지만 아직 연결 안 됨")
print(conn.query("SELECT 1"))
print(conn.query("SELECT 2"))
```

```text nolines
프록시는 만들어졌지만 아직 연결 안 됨
  [진짜 연결 생성] dsn='postgres://localhost/db'
(postgres://localhost/db) 실행: SELECT 1
(postgres://localhost/db) 실행: SELECT 2
```

(3.14.5 실측.) `_factory` 와 `_target` 을 `object.__setattr__` 로 직접 박아 넣은 게 핵심이다. 그래야 `self._factory` 조회가 앞서 본 재귀 함정에 안 걸리고 정상 탐색(`__dict__`)으로 바로 끝난다. 두 번째 `conn.query(...)` 에서는 "진짜 연결 생성" 로그가 다시 안 찍힌다 — `_target` 이 이미 채워져 있어 `_ensure` 가 캐시를 그대로 돌려주기 때문이다. [1.19 import](#/imports)의 모듈 레벨 `__getattr__` 이 `globals()[name] = value` 로 캐싱했던 것과 정확히 같은 아이디어다.

::: danger 이 프록시로는 던더를 흉내 낼 수 없다
[1.14 특수 메서드](#/dunder)에서 이미 증명했듯, `len()`, `+`, `[]` 같은 연산은 `type(obj)` 의 슬롯만 보고 `__getattr__` 은 아예 물어보지 않는다. `LazyProxy` 가 감싼 대상이 `list` 라 해도 `len(conn)` 은 실패한다. 던더까지 위임하려면 필요한 것을 클래스에 **직접, 하나씩** 정의해야 한다. 표준 라이브러리 `unittest.mock.MagicMock` 이 그렇게 수십 개의 던더를 일일이 나열해 둔 이유다.
:::

## 클래스 레벨로 확장하기: 메타클래스의 `__getattr__`

지금까지 본 `__getattr__` 은 전부 **인스턴스** 속성 접근을 가로챘다. `Config.TIMEOUT` 처럼 **클래스 자체**의 속성에 접근할 때는 다른 이야기가 된다.

```pyrepl
>>> class Config:
...     def __getattr__(self, name):
...         print(f"  (인스턴스) __getattr__({name!r})")
...         return "instance-level"
...
>>> c = Config()
>>> c.UNKNOWN
  (인스턴스) __getattr__('UNKNOWN')
'instance-level'
>>> Config.TIMEOUT
Traceback (most recent call last):
  ...
AttributeError: type object 'Config' has no attribute 'TIMEOUT'
```

(3.14.5 실측.) `Config` 안에 정의한 `__getattr__` 은 인스턴스 `c` 에는 먹히지만 `Config` 자체에는 아무 효과가 없다. 왜인가. `obj.x` 는 `type(obj).__getattribute__(obj, 'x')` 를 부른다는 걸 앞서 봤다. 그런데 `Config.TIMEOUT` 에서 `obj` 는 `Config` **자신**이고, `type(obj)` 는 `Config` 의 클래스, 즉 **메타클래스**([3.4 메타클래스](#/metaclass))다. 클래스 자체의 속성 조회를 가로채려면 그 조회를 실제로 수행하는 메타클래스에 `__getattr__` 을 정의해야 한다.

```python title="class_level_getattr.py"
class ConfigMeta(type):
    def __getattr__(cls, name):
        print(f"  (클래스) ConfigMeta.__getattr__({name!r})")
        if name in cls._DEFAULTS:
            return cls._DEFAULTS[name]
        raise AttributeError(name)


class Config2(metaclass=ConfigMeta):
    _DEFAULTS = {"TIMEOUT": 30, "RETRIES": 3}


print(Config2.TIMEOUT)
print(Config2.RETRIES)
```

```text nolines
  (클래스) ConfigMeta.__getattr__('TIMEOUT')
30
  (클래스) ConfigMeta.__getattr__('RETRIES')
3
```

(3.14.5 실측.) 그리고 인스턴스 쪽에서는 정확히 반대로 실패한다.

```pyrepl
>>> inst = Config2()
>>> inst.TIMEOUT
Traceback (most recent call last):
  ...
AttributeError: 'Config2' object has no attribute 'TIMEOUT'
```

`inst.TIMEOUT` 은 `type(inst).__getattribute__`, 즉 **`Config2` 의** 속성 탐색 알고리즘을 타지 `ConfigMeta` 를 보지 않는다. `ConfigMeta.__getattr__` 은 오직 `Config2` 자신에 대한 속성 접근(`Config2.무언가`)에만 관여한다.

::: hist 이게 왜 PEP 562(모듈 레벨 `__getattr__`)의 연장선인가
[1.19 import](#/imports)에서 본 모듈 레벨 `__getattr__` 을 떠올려 보자. `module.attr` 에 접근할 때 정상 탐색이 실패하면 그 모듈 파일 안의 `__getattr__` 함수가 불렸다. 구조를 그대로 겹쳐 보면 대응 관계가 보인다.

| 무엇의 속성인가 | 정상 탐색 실패 시 누구의 `__getattr__` 이 불리나 |
| --- | --- |
| 인스턴스 (`obj.x`) | `type(obj)` 에 정의된 `__getattr__` |
| 모듈 (`mod.x`) | 그 모듈 **안에** 정의된 `__getattr__` 함수 (PEP 562) |
| 클래스 자신 (`Cls.x`) | `type(Cls)`, 즉 메타클래스에 정의된 `__getattr__` |

"객체의 속성을 못 찾으면 그 객체를 만든 것(class)에게 물어본다"는 하나의 규칙이 인스턴스·모듈·클래스 세 층위에 반복해서 나타난다. 모듈은 특별 취급을 받는 것처럼 보이지만, 사실 "모듈도 객체이고, `sys.modules` 안의 그 객체에 대한 속성 조회일 뿐"이라는 같은 이야기다. PEP 562 이전에는 이걸 흉내 내려고 모듈 객체의 클래스를 몰래 바꿔치기하는 트릭을 썼는데, 그게 정확히 지금 여기서 메타클래스로 하는 일과 같다 — **"이 객체의 속성 조회 실패를 대신 처리해 줄 타입"을 붙이는 것.**
:::

## 언제 쓰지 말아야 하는가

이 절의 도구들은 강력한 만큼 대가가 크다. 남용하면 이 책이 지금까지 쌓아 온 것들을 스스로 무너뜨린다.

- **정적 분석이 죽는다.** pyright/mypy는 `__getattr__` 로 만들어지는 속성을 추론할 수 없다. `obj.아무이름` 이 전부 타입 에러 없이 통과해 버리면, [Part II 타입 시스템](#/why-typing) 전체가 무력화된다. 최소한 `__getattr__` 의 반환 타입을 어노테이션하고, 가능하면 아예 진짜 속성이나 [3.3 디스크립터](#/descriptors) 기반 property로 바꿔라.
- **디버깅이 지옥이 된다.** `obj.total_price` 를 쳤는데 그게 실제로는 DB 쿼리를 날린다면, 스택 트레이스만 봐서는 그 사실을 알 수 없다. 호출부 코드는 평범한 속성 접근처럼 보이는데 실제로는 숨은 부수 효과가 있다 — "명시적인 것이 암묵적인 것보다 낫다"는 파이썬 철학과 정면으로 부딪힌다.
- **오타가 예외 대신 값이 된다.** `__getattr__` 이 없는 이름에도 기본값을 돌려주게 짜면, `obj.usre_name` 같은 오타가 `AttributeError` 대신 조용히 엉뚱한 값을 반환한다. **없는 이름은 반드시 `AttributeError` 로 끝나야 한다.** 조용히 기본값을 주는 것은 버그를 숨기는 것이다.
- **IDE 자동완성이 무의미해진다.** 동적으로 생기는 속성은 어떤 정적 도구도 목록을 알 수 없다. `__dir__` 을 같이 오버라이드해서 최소한의 힌트라도 주는 게 낫다.
- **메타클래스는 특히 신중해야 한다.** 클래스 레벨 `__getattr__` 은 위력이 크지만, 여러 메타클래스를 조합하려 하면 [1.13 상속, MRO](#/inheritance)의 C3 선형화 문제가 그대로 메타클래스 계층에도 옮겨붙는다. 라이브러리를 만드는 게 아니라면, 정말 필요한지 세 번 되물어라. 대부분의 "동적 속성"은 그냥 `dict`, `dataclass`, 또는 평범한 `property` 로 충분하다.

**경험칙**: `__getattr__`/`__getattribute__`/`__setattr__` 은 "다른 방법이 진짜로 없을 때" 쓰는 마지막 수단이다. 프레임워크나 라이브러리의 경계(ORM, 설정 로더, 테스트 목)에서는 쓸 가치가 있다. 애플리케이션 코드 안에서는 거의 항상 더 나은 선택지가 있다.

## 요약

- **`__getattr__`** 은 정상 탐색(인스턴스 `__dict__` → 클래스/MRO)이 **실패했을 때만** 불리는 폴백이다. 성공하는 접근에는 관여하지 않아 사실상 공짜다.
- **`__getattribute__`** 는 성공·실패와 무관하게 **모든** 점 접근에서 불린다. 오버라이드하면 정상 접근까지 실측 약 7배 느려진다. 내부에서는 반드시 `object.__getattribute__` 로 위임해야 한다.
- **`__setattr__`** 은 모든 대입을 가로챈다. 내부 저장은 `object.__setattr__` 이나 `self.__dict__[name] = value` 로 해야 한다. `self.attr = value` 로 저장하면 즉시 무한 재귀다.
- **무한 재귀의 근본 원인은 하나다**: 훅 안에서 `self.무언가` 를 참조했는데, 그 조회가 다시 같은 훅을 부른다. 특히 `__init__` 을 거치지 않고 만들어진 인스턴스(역직렬화, `copy`)에서 자주 터진다.
- 이 훅들을 조합하면 **지연 로딩 프록시**를 만들 수 있다. 단, 던더는 위임되지 않으니 필요한 것을 직접 정의해야 한다.
- 모듈 레벨 `__getattr__`(PEP 562)과 같은 아이디어를 **클래스 자체**에 쓰려면 클래스가 아니라 **메타클래스**에 `__getattr__` 을 정의해야 한다. `type(Cls)` 가 그 조회의 주체이기 때문이다.
- 이 모든 도구는 **정적 분석, 디버깅 가능성, 오타 검출**을 희생시킨다. 라이브러리 경계에서만 신중히 쓴다.

::: quiz 연습문제
1. 다음 코드를 실행하기 전에 출력을 예측하라. `__getattr__` 과 `__getattribute__` 를 동시에 정의하면 어느 것이 먼저 불리는가?

   ```python
   class Both:
       def __getattribute__(self, name):
           print(f"getattribute: {name}")
           return object.__getattribute__(self, name)

       def __getattr__(self, name):
           print(f"getattr: {name}")
           return None

   b = Both()
   b.x
   ```

2. `LazyProxy` 예제에서 `_factory` 와 `_target` 을 `object.__setattr__` 대신 그냥 `self._factory = factory` 로 초기화하면 무슨 일이 일어나는가? 직접 고쳐서 재현하고, 왜 그런지 설명하라.

3. 아래 메타클래스는 클래스 레벨 상수를 대문자 이름으로만 노출하려 한다. `Settings.DEBUG` 는 되고 `Settings.debug`(소문자)는 `AttributeError` 가 나도록 `ConfigMeta.__getattr__` 을 완성하라.

   ```python
   class ConfigMeta(type):
       def __getattr__(cls, name):
           ...  # 여기를 채워라

   class Settings(metaclass=ConfigMeta):
       _DEFAULTS = {"DEBUG": True}
   ```

4. `__getattr__` 로 없는 속성에 대해 항상 `0` 을 반환하도록 만든 클래스가 있다고 하자. 이게 왜 위험한지, 실제로 어떤 종류의 버그를 숨기는지 예시 코드로 보여라.

5. **생각해 볼 문제.** `functools.cached_property` 는 첫 접근 때 값을 계산해 인스턴스 `__dict__` 에 저장하고, 그다음부터는 그 값을 그대로 돌려준다. 이걸 `__getattr__` 로 구현하는 것과 [3.3 디스크립터](#/descriptors)로 구현하는 것은 결과가 같아 보이지만 한 가지 결정적 차이가 있다. 클래스에 `__slots__` 를 쓰면 어느 쪽이 깨지는가?
:::

**다음 절**: [3.6 AST와 코드 생성](#/ast) — 파이썬 코드를 문자열이 아니라 트리로 다루면 무엇이 가능해지는가.
