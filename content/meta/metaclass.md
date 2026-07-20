# 3.4 메타클래스와 __init_subclass__

::: lead
`type(Point)` 를 찍어 보면 `<class 'type'>` 이 나온다. 클래스도 객체이고, 그 객체를 만든 건 `type` 이라는 또 다른 클래스다. 이 절은 그 사실을 끝까지 밀어붙인다. `class` 문이 실제로 무엇을 호출하는지 dis로 뜯어보고, 그 호출에 손을 넣는 메타클래스를 직접 만들고, 마지막엔 **대부분의 경우 메타클래스가 필요 없다는 것**을 증명한다. 이 절의 실제 목적은 메타클래스를 쓰게 만드는 게 아니라, 언제 쓰지 말아야 하는지 알게 하는 것이다.
:::

## type은 클래스의 클래스다

[1.1 객체, 이름, 참조](#/objects-names)에서 모든 객체는 정체성·타입·값을 가진다고 했다. 정수도, 리스트도, **클래스 자신도** 예외가 아니다. 클래스는 객체이고, 객체이면 타입이 있어야 한다.

```pyrepl
>>> class Point:
...     def __init__(self, x, y):
...         self.x = x
...         self.y = y
...
>>> p = Point(1, 2)
>>> type(p)
<class '__main__.Point'>
>>> type(Point)
<class 'type'>
```

`p` 의 타입은 `Point` 다. 그럼 `Point` 의 타입은? `type` 이다. 인스턴스를 만드는 클래스가 있듯, **클래스를 만드는 클래스**가 있다. 그게 `type` 이고, 그런 걸 통틀어 **메타클래스**(metaclass)라 부른다.

이 사슬은 어디서 끝날까.

```pyrepl
>>> type(int)
<class 'type'>
>>> type(object)
<class 'type'>
>>> type(type)
<class 'type'>
```

`type` 은 자기 자신의 타입이다. 이게 CPython 타입 시스템의 바닥이다. 모든 클래스 — 내장 타입이든 사용자 정의든 — 는 결국 `type` 이 만든다. **`type` 은 파이썬에서 가장 상위에 있는 "클래스 공장"** 이다.

::: note object와 type의 관계는 순환이 아니다
`type(object)` 가 `type` 이고, `object.__bases__` 를 확인하면 `type` 자체도 `object` 를 상속한다.

```pyrepl
>>> type.__bases__
(<class 'object'>,)
>>> object.__bases__
()
```

**상속** 관계와 **타입(인스턴스)** 관계는 서로 다른 축이다. `type` 은 `object` 의 서브클래스이면서, 동시에 `object` 를 포함한 모든 클래스의 타입이다. 헷갈리면 이렇게 구분하라: "A는 B를 상속한다"는 `__bases__` 를 따라가는 것이고, "A는 B의 인스턴스다"는 `type(A)` 를 따라가는 것이다.
:::

## class 문은 type() 호출의 문법 설탕이다

`type` 은 클래스이므로 직접 호출해서 인스턴스, 즉 **새 클래스**를 만들 수 있다. `type()` 은 인자 개수에 따라 동작이 갈린다.

```pyrepl
>>> type(42)
<class 'int'>
>>> type("Point", (), {"__init__": lambda self, x, y: (setattr(self, "x", x), setattr(self, "y", y))})
<class '__main__.Point'>
```

인자 하나면 "이 객체의 타입이 뭐야?"를 묻는 것이고, 인자 셋(이름, 부모 클래스들, 네임스페이스 딕셔너리)이면 "이 스펙으로 클래스를 만들어 줘"다. 뒤의 형태로 `class` 문과 동치인 클래스를 만들 수 있는지 직접 확인해 보자.

```python title="type() 을 직접 호출해서 class 문 없이 클래스 만들기"
def __init__(self, x, y):
    self.x = x
    self.y = y

Point2 = type("Point2", (), {"__init__": __init__})

p = Point2(1, 2)
print(p.x, p.y)          # 1 2
print(type(Point2))      # <class 'type'>
print(Point2.__mro__)    # (<class '__main__.Point2'>, <class 'object'>)
```

이건 비유가 아니다. `Point2` 는 `class Point2: def __init__(self, x, y): ...` 를 써서 만든 것과 **완전히 동일한 종류의 객체**다. 그럼 `class` 문은 정확히 뭘 하고 있는 걸까. 컴파일된 바이트코드를 직접 봐야 답이 나온다.

```python title="컴파일해서 dis로 들여다보기"
import dis

src = """
class Point:
    def __init__(self, x, y):
        self.x = x
"""
dis.dis(compile(src, "<string>", "exec"))
```

실행하면(3.14.5 기준, 일부 생략) 이렇게 나온다.

```text nolines
  2           LOAD_BUILD_CLASS
              PUSH_NULL
              LOAD_CONST     0 (<code object Point ...>)
              MAKE_FUNCTION
              LOAD_CONST     1 ('Point')
              CALL           2
              STORE_NAME     0 (Point)
```

`class Point: ...` 는 **`__build_class__(<Point의 본문을 실행하는 함수>, 'Point')` 라는 함수 호출**로 컴파일된다. `LOAD_BUILD_CLASS` 는 내장 함수 `builtins.__build_class__` 를 스택에 올리는 명령이다.

```pyrepl
>>> import builtins
>>> builtins.__build_class__.__doc__
'__build_class__(func, name, /, *bases, [metaclass], **kwds) -> class\n\nInternal helper function used by the class statement.'
```

`__build_class__` 가 하는 일은 세 단계다.

1. `bases` 와 `metaclass` 키워드(명시 안 하면 생략)를 보고 **실제로 쓸 메타클래스를 결정한다.** 아무 부모도 없고 `metaclass=` 도 없으면 기본값은 `type` 이다. 부모가 있으면 그 부모들의 타입 중 **가장 파생된 것**을 고른다.
2. 결정된 메타클래스의 `__prepare__` 를 호출해 클래스 본문을 실행할 네임스페이스(보통 그냥 `dict`)를 받는다.
3. 그 네임스페이스 위에서 `func`(클래스 본문)를 실행한 뒤, **`메타클래스(name, bases, namespace)` 를 호출**해서 진짜 클래스 객체를 만든다.

즉 `class Point: ...` 는 결국 `Point = type("Point", (), {...})` 를 (본문 실행 순서까지 포함해) 정확히 재현하는 문법 설탕이다. **"파이썬은 인터프리터 언어라 클래스도 런타임에 만들어진다"** 는 흔한 설명을 여기서는 코드로 확인한 것이다. 이게 중요한 이유는, `type` 자리에 다른 메타클래스를 넣으면 **클래스가 만들어지는 그 순간에 개입할 수 있다**는 뜻이기 때문이다.

## 메타클래스 만들기: __new__ vs __init__

`type` 을 상속해서 메타클래스를 정의하면, `class` 문이 호출하는 게 `type` 대신 그 메타클래스가 된다. 인스턴스에 `__new__`/`__init__` 이 있듯, 메타클래스에도 똑같은 두 훅이 있다 — 다만 여기서 "인스턴스"는 **클래스 자체**다.

```python title="세 훅을 모두 찍어 보기"
class Meta(type):
    def __new__(mcs, name, bases, ns, **kwargs):
        print(f"Meta.__new__ 호출: name={name!r}, kwargs={kwargs}")
        return super().__new__(mcs, name, bases, ns)

    def __init__(cls, name, bases, ns, **kwargs):
        print(f"Meta.__init__ 호출: name={name!r}")
        super().__init__(name, bases, ns)

    def __call__(cls, *args, **kwargs):
        print(f"Meta.__call__ 호출: {cls} 인스턴스 생성 시작")
        return super().__call__(*args, **kwargs)


class Base(metaclass=Meta, extra_flag=True):
    x = 1

print("---")
b = Base()
```

실제 출력(3.14.5).

```text nolines
Meta.__new__ 호출: name='Base', kwargs={'extra_flag': True}
Meta.__init__ 호출: name='Base'
---
Meta.__call__ 호출: <class '__main__.Base'> 인스턴스 생성 시작
```

세 훅의 역할이 완전히 다르다.

| 훅 | 실행 시점 | 할 수 있는 일 |
| --- | --- | --- |
| `Meta.__new__` | `Base` **클래스 객체가 만들어지기 직전** | 네임스페이스(`ns`)를 고쳐서 다른 속성으로 클래스를 만들 수 있다 |
| `Meta.__init__` | `Base` 클래스 객체가 **만들어진 직후** | 이미 완성된 `cls` 를 검사·등록할 수 있다. 구조 자체는 못 바꾼다 |
| `Meta.__call__` | `Base(...)` 로 **인스턴스를 만들 때마다** | `Base.__new__`/`__init__` 이 불리기 전후에 개입할 수 있다 |

여기서 `extra_flag=True` 는 `class Base(metaclass=Meta, extra_flag=True)` 의 키워드 인자다. `__build_class__` 는 이걸 그대로 `Meta(name, bases, ns, extra_flag=True)` 로 전달한다 — 클래스 정의 시점에 임의의 설정값을 메타클래스로 흘려보낼 수 있다는 뜻이다. 이건 [1.12 클래스와 데이터 모델](#/classes)에서 본 일반 클래스의 키워드 인자(`class Foo(Base, key=value)`)와 같은 메커니즘이며, [1.13 상속, MRO, 컴포지션](#/inheritance)의 `super()` 도 메타클래스 레벨에서 똑같이 동작한다 — `Meta.__new__` 안의 `super().__new__` 는 `type.__new__` 를 부른다.

::: warn __new__ 에서 네임스페이스를 고치면 결과가 완전히 달라진다
```python
class UpperAttrMeta(type):
    def __new__(mcs, name, bases, ns):
        upper_ns = {
            (k.upper() if not k.startswith("__") else k): v
            for k, v in ns.items()
        }
        return super().__new__(mcs, name, bases, upper_ns)


class Config(metaclass=UpperAttrMeta):
    timeout = 30
    retries = 3

print(Config.TIMEOUT, Config.RETRIES)   # 30 3
print(hasattr(Config, "timeout"))       # False — 원래 이름은 사라졌다
```

메타클래스는 클래스 본문에 쓴 것과 **완전히 다른 속성 이름을 가진 클래스**를 만들어 낼 수 있다. `Meta.__init__` 시점엔 이미 늦다 — `ns` 를 아무리 고쳐도 클래스는 원래 이름 그대로 만들어진 뒤다.
:::

## __prepare__: 클래스 본문이 실행되는 동안 개입하기

`Meta.__new__` 는 클래스 본문이 **다 실행되고 난 뒤** 결과 딕셔너리를 받는다. 본문이 실행되는 **도중**에 개입하려면 `__prepare__` 가 필요하다. 이건 `__init_subclass__` 로는 절대 흉내 낼 수 없는 유일한 능력이다.

```python title="클래스 본문 실행 중 중복 정의를 즉시 잡아내기"
class NoDupNamespace(dict):
    def __setitem__(self, key, value):
        if key in self and not key.startswith("__"):
            raise TypeError(f"중복 정의: {key!r}")
        super().__setitem__(key, value)


class StrictMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        return NoDupNamespace()          # 본문 실행에 이 딕셔너리를 쓴다

    def __new__(mcs, name, bases, ns, **kwargs):
        return super().__new__(mcs, name, bases, dict(ns))


class Config(metaclass=StrictMeta):
    timeout = 30
    timeout = 60      # NoDupNamespace.__setitem__ 이 여기서 즉시 터진다
```

실제 실행 결과.

```text nolines
TypeError: 중복 정의: 'timeout'
```

`enum.EnumMeta` 가 정확히 이 트릭으로 멤버 이름 중복을 막는다. 비교를 위해 같은 걸 `__init_subclass__` 로 시도하면 어떻게 되는지 보자.

```python title="__init_subclass__ 는 본문이 끝난 뒤에야 호출된다"
class Base:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        print(f"{cls.__name__} 생성 완료, timeout={cls.timeout}")


class Config2(Base):
    timeout = 30
    timeout = 60      # 그냥 조용히 덮어써진다
```

```text nolines
Config2 생성 완료, timeout=60
```

`__init_subclass__` 가 불릴 때 `timeout = 30` 이라는 정보는 이미 사라지고 없다. 클래스 본문은 순서대로 실행되는 **평범한 코드 블록**이라, 같은 이름을 두 번 대입하면 첫 번째 값은 흔적도 없이 지워진다. `__prepare__` 만이 그 대입이 일어나는 **바로 그 순간**을 가로챌 수 있다.

## 더 쉬운 대안: __init_subclass__

지금까지 본 메타클래스는 셋 다 무겁다. 클래스 생성 파이프라인 전체(`__prepare__`, `__new__`, `__init__`, `__call__`)에 손을 댈 수 있는 대신, `metaclass=` 를 명시해야 하고 다중 상속에서 충돌 위험을 떠안는다. PEP 487(3.6)은 **서브클래스가 만들어질 때 알림을 받는 것**만 필요한 압도적 다수의 경우를 위해 `__init_subclass__` 를 도입했다.

메타클래스로 만든 "서브클래스 등록" 패턴을 그대로 옮겨 보자.

```python title="메타클래스 없이 서브클래스 자동 등록"
class Plugin:
    registry = {}

    def __init_subclass__(cls, *, name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        key = name or cls.__name__.lower()
        Plugin.registry[key] = cls
        print(f"등록: {key} -> {cls}")


class CsvPlugin(Plugin, name="csv"):
    pass


class JsonPlugin(Plugin):
    pass


print(Plugin.registry)
print(type(CsvPlugin))    # <class 'type'> — 메타클래스가 필요 없었다
```

```text nolines
등록: csv -> <class '__main__.CsvPlugin'>
등록: jsonplugin -> <class '__main__.JsonPlugin'>
{'csv': <class '__main__.CsvPlugin'>, 'jsonplugin': <class '__main__.JsonPlugin'>}
<class 'type'>
```

`class CsvPlugin(Plugin, name="csv")` 의 `name="csv"` 는 `Meta.__new__` 가 받던 것과 같은 종류의 키워드 인자다. 차이는 메타클래스가 아니라 **일반 클래스의 훅**이 받는다는 것뿐이다. `type(CsvPlugin)` 이 여전히 평범한 `type` 이라는 점을 주목하라 — 아무도 `type` 을 상속하지 않았다.

::: note __init_subclass__ 는 암묵적으로 classmethod다
```pyrepl
>>> type(Base.__dict__['__init_subclass__'])
<class 'classmethod'>
```
직접 `@classmethod` 를 붙이지 않아도 파이썬이 자동으로 그렇게 만들어 준다. 그리고 **`Base` 자기 자신에 대해서는 호출되지 않는다.** 오직 서브클래스가 정의될 때만 트리거된다 — 정확히 "서브클래싱 알림"이라는 이름값대로다.
:::

`__set_name__` 을 함께 쓰는 [3.3 디스크립터](#/descriptors)의 지식까지 더하면, 메타클래스 없이 갈 수 있는 범위는 훨씬 넓어진다. 필드 검증, 등록, 추상 메서드 강제 같은 요구의 대부분은 `__init_subclass__` + `__set_name__` 조합으로 끝난다.

## __init_subclass__로 안 되는 것 — 진짜 메타클래스가 필요한 경우

그럼 메타클래스가 정말 필요한 경우는 언제인가. 두 가지 조건 중 하나라도 걸리면 후보다.

**1. 클래스가 만들어지기 전에 네임스페이스 자체를 바꿔야 한다.** `__init_subclass__` 는 클래스가 **이미 만들어진 뒤** 호출된다. 위에서 본 `__prepare__` 중복 검출이 대표적이고, ORM의 필드 수집도 마찬가지다.

```python title="미니 ORM — Django 스타일 필드 수집"
class Field:
    def __init__(self, kind):
        self.kind = kind
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        if not isinstance(value, self.kind):
            raise TypeError(f"{self.name} 은 {self.kind.__name__} 이어야 한다")
        instance.__dict__[self.name] = value


class ModelMeta(type):
    def __new__(mcs, name, bases, ns):
        fields = {k: v for k, v in ns.items() if isinstance(v, Field)}
        cls = super().__new__(mcs, name, bases, ns)
        cls._fields = fields          # 클래스 자체에 메타데이터를 붙인다
        return cls


class Model(metaclass=ModelMeta):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        vals = ", ".join(f"{k}={getattr(self, k)!r}" for k in self._fields)
        return f"{type(self).__name__}({vals})"


class User(Model):
    name = Field(str)
    age = Field(int)


u = User(name="윤아", age=20)
print(u)
u.age = "스물"    # TypeError
```

```text nolines
User(name='윤아', age=20)
TypeError: age 은 int 이어야 한다
```

`Field` 는 [3.3 디스크립터](#/descriptors)에서 다룬 데이터 디스크립터 그대로다. `ModelMeta` 가 하는 일은 딱 하나, **`_fields` 라는 메타데이터를 클래스 생성 시점에 한 번 계산해서 붙여 두는 것**이다. 이건 `__init_subclass__` 로도 사실 할 수 있다(`cls.__dict__` 를 순회하면 그만이다). Django가 실제로 `ModelBase` 메타클래스를 쓰는 진짜 이유는 좀 더 깊다 — 추상 모델(`abstract = True`)끼리 다중 상속할 때 `Meta` 옵션을 병합해야 하고, 필드를 부모·자식에 걸쳐 **본문이 실행되는 동안** 재배치해야 하는 경우가 있어서다. 단순 수집만 필요하다면 `__init_subclass__` 로 충분하다.

**2. 서로 다른 메타클래스를 가진 클래스들을 조합해야 한다.** `abc.ABCMeta`, `enum.EnumMeta` 처럼 프레임워크 차원에서 공통 메타클래스를 강제해야 하는 경우다. 이건 다음 항목의 함정과 바로 연결된다.

## 메타클래스 오남용: 언제 쓰지 말아야 하는가

메타클래스는 강력한 만큼 대가가 있다. 두 가지를 실측으로 확인한다.

::: danger 메타클래스 충돌은 조합이 안 될 수도 있다는 뜻이다
```python
class MetaA(type):
    pass

class MetaB(type):
    pass

class A(metaclass=MetaA):
    pass

class B(metaclass=MetaB):
    pass

class C(A, B):    # 여기서 터진다
    pass
```

```text nolines
TypeError: metaclass conflict: the metaclass of a derived class must be
a (non-strict) subclass of the metaclasses of all its bases
```

`ABCMeta` 를 쓰는 클래스와 커스텀 메타클래스를 쓰는 클래스를 다중 상속해도 똑같은 에러가 난다. **메타클래스는 상속 트리 전체에 전파되는 성질**이라, 한 라이브러리가 메타클래스를 쓰면 그 클래스를 상속하는 모든 곳이 그 메타클래스의 제약을 받는다. `mixin` 클래스를 여러 개 조합하는 스타일과 메타클래스는 근본적으로 상성이 나쁘다.
:::

::: perf 인스턴스 생성 경로에 개입하면 그 비용은 매번 지불한다
`Meta.__call__` 을 오버라이드하면 클래스를 인스턴스화할 때마다 그 코드가 실행된다. 실측(3.14.5 / Windows, 100만 회).

```python title="메타클래스 __call__ 오버헤드"
import timeit

class Plain:
    __slots__ = ("x",)
    def __init__(self, x):
        self.x = x

class Meta(type):
    def __call__(cls, *args, **kwargs):
        return super().__call__(*args, **kwargs)

class WithMeta(metaclass=Meta):
    __slots__ = ("x",)
    def __init__(self, x):
        self.x = x

t1 = timeit.timeit(lambda: Plain(1), number=1_000_000)
t2 = timeit.timeit(lambda: WithMeta(1), number=1_000_000)
print(t1, t2, t2 / t1)
```

```text nolines
plain: 0.0500s
meta:  0.1757s
배수:  3.51x
```

`super().__call__` 을 그대로 통과시키기만 해도 약 3.5배 느려진다. 절대 시간(마이크로초 단위)은 대부분의 애플리케이션에서 무시할 수준이지만, **초당 수백만 개의 객체를 만드는 핫패스**(예: 파싱, 시뮬레이션 루프)에 무심코 메타클래스를 넣으면 그 배수가 그대로 병목이 된다.
:::

숫자보다 더 큰 비용은 따로 있다. **읽는 사람의 인지 부하**다. `class Foo(Bar):` 를 보고 무슨 일이 일어날지 예상하려면, 이제 `Bar` 뿐 아니라 `type(Bar)` 까지 추적해야 한다. `__new__`/`__init__`/`__call__` 중 어디서 무엇을 바꿨는지는 소스를 직접 읽지 않으면 알 수 없다. 팀에서 이 코드를 디버깅할 사람은 "왜 내가 정의한 대로 클래스가 안 만들어지지"라는 질문에서 시작해 메타클래스 체인을 거슬러 올라가야 한다.

**경험칙**은 이렇다.

1. 원하는 게 "서브클래스 만들어질 때 뭔가 하고 싶다"면 → `__init_subclass__`.
2. 원하는 게 "속성 접근을 가로채고 싶다"면 → [3.3 디스크립터](#/descriptors)나 `__getattr__`([3.5 __getattr__ 계열과 동적 속성](#/dynamic-attrs)).
3. 원하는 게 "여러 클래스에 같은 메서드를 넣고 싶다"면 → 믹스인 상속이나 [1.13 상속, MRO, 컴포지션](#/inheritance)의 컴포지션.
4. **정말로** 클래스 본문이 실행되는 동안 개입해야 하거나(`__prepare__`), 클래스 생성 자체의 규칙(다중 상속 시 옵션 병합 등)을 강제해야 할 때만 → 메타클래스.

`dataclasses`, `attrs`, 표준 라이브러리의 `NamedTuple` 은 메타클래스 없이 **데코레이터**([1.11 데코레이터](#/decorators))나 `__init_subclass__` 로 대부분의 프레임워크급 요구를 해결한다. `ABCMeta` 와 `EnumMeta` 정도가 표준 라이브러리에서 메타클래스를 실제로 정당화하는 예다. 당신의 코드가 그 정도로 근본적인 클래스 생성 규칙을 다시 쓰고 있는 게 아니라면, 메타클래스는 대개 과한 도구다.

## 요약

- 클래스도 객체다. 그 객체의 타입이 **메타클래스**이고, 기본값은 `type` 이다.
- `class` 문은 `__build_class__(func, name, *bases, metaclass=..., **kwds)` 호출로 컴파일되는 문법 설탕이다. dis로 직접 확인할 수 있다.
- 메타클래스 훅은 세 단계다: `__prepare__`(본문 실행 전 네임스페이스 결정) → `__new__`(클래스 객체 생성) → `__init__`(생성된 클래스 초기화). `__call__` 은 그 클래스의 **인스턴스**를 만들 때 불린다.
- `__init_subclass__` 는 "서브클래스가 만들어졌다"는 알림만 필요할 때 메타클래스보다 훨씬 가벼운 대안이다. 대부분의 요구는 이걸로 끝난다.
- `__init_subclass__` 로 안 되는 유일한 지점은 **클래스 본문이 실행되는 도중**에 개입하는 것(`__prepare__`)이다.
- 메타클래스는 상속 트리 전체에 전파되며, 서로 다른 메타클래스를 쓰는 클래스는 다중 상속에서 충돌한다. 도입 전에 이 비용을 감당할지 따져라.

::: quiz 연습문제
1. `type(type(type))` 은 무엇인가? 먼저 예측하고 실행해서 확인하라. 그 이유를 `type.__bases__` 와 연결해 설명하라.
2. 다음 코드를 실행하면 `Meta.__new__`, `Meta.__init__` 중 무엇이 몇 번 호출되는지 예측하라. `class C(A, B)` 처럼 다중 상속이 걸릴 때 호출 순서가 [1.13 상속, MRO, 컴포지션](#/inheritance)의 MRO와 어떻게 관련되는지도 설명하라.

   ```python
   class Meta(type):
       def __new__(mcs, name, bases, ns):
           print("new", name)
           return super().__new__(mcs, name, bases, ns)

   class A(metaclass=Meta): pass
   class B(A): pass
   class C(B): pass
   ```

3. `__init_subclass__` 를 써서, 서브클래스를 정의할 때 특정 메서드(`run`)를 반드시 오버라이드하지 않으면 `TypeError` 를 내는 `Task` 베이스 클래스를 작성하라. 메타클래스 없이 되는가?
4. 본문에서 본 `NoDupNamespace` 예제를 응용해, **클래스 본문 안에서 정의한 순서**를 기록하는 메타클래스를 만들어라. (힌트: 파이썬 3.7+ 의 `dict` 는 이미 삽입 순서를 보장하므로 `__prepare__` 가 특별한 자료구조를 반환할 필요는 없을 수도 있다. 정말 필요 없는지 확인하라.)
5. 이 절의 `ModelMeta` 예제에서 메타클래스를 완전히 걷어내고 `__init_subclass__` 만으로 같은 `_fields` 수집 기능을 구현하라. 정확히 어떤 지점에서 코드가 달라지는가?
:::

**다음 절**: [3.5 __getattr__ 계열과 동적 속성](#/dynamic-attrs) — 클래스 생성 시점이 아니라 속성 접근 시점에 개입하는 법.
