# 3.3 디스크립터

::: lead
`@property`, `@classmethod`, `@staticmethod` 는 파이썬을 배우면 가장 먼저 외우는 데코레이터들이다. 그런데 이것들이 **왜 동작하는지** 설명할 수 있는 사람은 드물다. 답은 하나의 메커니즘으로 수렴한다 — **디스크립터**(descriptor). `obj.attr` 이라는 점 하나 찍은 문법 뒤에서 실제로 무슨 함수가 호출되는지 이 절에서 끝까지 추적한다. property도, classmethod도, 심지어 함수가 메서드로 변신하는 것도 전부 디스크립터를 직접 만들어서 증명한다.
:::

## 검증 로직을 어디에 넣을 것인가

섭씨온도를 저장하는 클래스를 생각해 보자. 절대영도 아래 값은 막고 싶다.

```python title="게터/세터 없이 시작"
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius


t = Temperature(-500)   # 통과해 버린다. 물리적으로 불가능한 값인데.
```

Java식으로 `get_celsius()` / `set_celsius()` 메서드를 만들면 검증은 되지만 `t.celsius` 라는 자연스러운 문법을 잃는다. 파이썬은 `@property` 로 **문법은 속성 접근 그대로 두고, 뒤에서 함수를 실행**하게 해 준다.

```python
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("절대영도 아래는 불가능하다")
        self._celsius = value
```

`t.celsius = -500` 은 이제 `ValueError` 를 낸다. 그런데 `t.celsius` 라는 **평범한 속성 접근** 뒤에서 어떻게 함수 호출이 끼어드는가? `property` 가 특별 취급을 받는 키워드가 아니라 **디스크립터 프로토콜을 구현한 평범한 클래스**이기 때문이다. 지금부터 그 프로토콜을 하나씩 뜯는다.

## 디스크립터 프로토콜

**디스크립터란 `__get__`, `__set__`, `__delete__` 중 하나 이상을 정의한 클래스의 인스턴스**로서, **다른 클래스의 클래스 속성**으로 저장된 것을 말한다. "다른 클래스의 클래스 속성"이라는 조건이 핵심이다 — 인스턴스 속성으로 저장된 디스크립터는 발동하지 않는다.

| 메서드 | 호출 시점 | 시그니처 |
| --- | --- | --- |
| `__get__` | 속성을 **읽을 때** | `__get__(self, obj, objtype=None)` |
| `__set__` | 속성에 **대입할 때** | `__set__(self, obj, value)` |
| `__delete__` | `del obj.attr` 할 때 | `__delete__(self, obj)` |
| `__set_name__` | **클래스가 만들어질 때** 한 번 | `__set_name__(self, owner, name)` |

`__get__` 만 정의하면 **비데이터 디스크립터**(non-data descriptor), `__get__` 과 함께 `__set__` 이나 `__delete__` 를 정의하면 **데이터 디스크립터**(data descriptor)다. 이 구분이 우선순위를 가른다.

## 데이터 디스크립터 vs 비데이터 디스크립터 — 실측으로 우선순위 확인

`obj.attr` 을 조회할 때 파이썬은 이런 순서로 찾는다.

1. `type(obj).__mro__` 를 훑어 `attr` 을 찾는다.
2. 찾은 것이 **데이터 디스크립터**면 → 그 디스크립터의 `__get__` 을 호출한다. 여기서 끝난다. **항상 이긴다.**
3. 데이터 디스크립터가 아니면 → `obj.__dict__` 에 `attr` 이 있는지 본다. 있으면 그 값을 그대로 반환한다.
4. 없으면 → **비데이터 디스크립터**의 `__get__` 을 호출하거나, 그냥 클래스 속성을 반환한다.

말로 정리하면 **데이터 디스크립터 > 인스턴스 `__dict__` > 비데이터 디스크립터 > 클래스 속성** 순서다. 인스턴스 `__dict__` 가 중간에 낀다는 것이 함정이다. 직접 두 종류를 만들어서 확인한다.

```python title="데이터 디스크립터와 비데이터 디스크립터"
class DataDesc:
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        print(f"  DataDesc.__get__ 호출됨 (obj={obj!r})")
        return obj.__dict__.get(self.name, "기본값")

    def __set__(self, obj, value):
        print(f"  DataDesc.__set__ 호출됨 (value={value!r})")
        obj.__dict__[self.name] = value


class NonDataDesc:
    def __get__(self, obj, objtype=None):
        print("  NonDataDesc.__get__ 호출됨")
        return "non-data 결과"


class Demo:
    x = DataDesc("x")
    y = NonDataDesc()
```

```pyrepl
>>> d = Demo()
>>> d.x
  DataDesc.__get__ 호출됨 (obj=<__main__.Demo object at 0x...>)
'기본값'
>>> d.x = 100
  DataDesc.__set__ 호출됨 (value=100)
>>> d.__dict__
{'x': 100}
>>> d.x                       # 인스턴스 dict에 x=100 이 있는데도...
  DataDesc.__get__ 호출됨 (obj=<__main__.Demo object at 0x...>)
100                            # 여전히 디스크립터를 거쳐서 나온다
```

`d.__dict__` 에 `x` 라는 값이 분명히 있는데도 매번 `DataDesc.__get__` 을 통과한다. **데이터 디스크립터는 인스턴스 `__dict__` 보다 항상 우선한다.** 반대로 비데이터 디스크립터는 인스턴스 `__dict__` 에게 진다.

```pyrepl
>>> d.y
  NonDataDesc.__get__ 호출됨
'non-data 결과'
>>> d.__dict__["y"] = "인스턴스가 직접 넣은 값"
>>> d.y                       # 이번엔 __get__ 이 호출되지 않는다
'인스턴스가 직접 넣은 값'
```

(3.14.5 / Windows 기준 실측.) 이 우선순위가 `property` 가 `self.x = 5` 같은 코드로 무심코 덮어써지지 않는 이유다. `__set__` 을 정의한 순간 인스턴스 `__dict__` 로는 절대 이길 수 없는 위치에 서게 된다.

::: note 클래스 자체로 접근하면 어떻게 되나
`Demo.x` 처럼 인스턴스 없이 클래스로 접근하면 `__get__(None, Demo)` 가 호출된다. `obj` 인자가 `None` 이 된다는 뜻이다. `property` 는 이 경우를 감지해서 **디스크립터 객체 자기 자신을 반환**하도록 구현돼 있다. 뒤에서 직접 만들어 확인한다.
:::

## property는 디스크립터로 구현되어 있다 — 직접 만들어 증명

`property` 가 마법이 아니라는 것을 증명하는 가장 확실한 방법은 **똑같이 동작하는 것을 직접 만드는 것**이다.

```python title="MyProperty — property의 재구현"
class MyProperty:
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:          # Demo.celsius 처럼 클래스로 접근한 경우
            return self
        if self.fget is None:
            raise AttributeError(f"{self._name!r} 는 읽을 수 없다")
        return self.fget(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError(f"{self._name!r} 는 쓸 수 없다")
        self.fset(obj, value)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError(f"{self._name!r} 는 지울 수 없다")
        self.fdel(obj)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.__doc__)
```

`@MyProperty` 는 `celsius = MyProperty(celsius함수)` 와 같다. `@celsius.setter` 는 `fset` 을 채운 **새 `MyProperty` 인스턴스**를 만들어 같은 이름에 다시 대입하는 것뿐이다.

```python title="표준 property와 나란히"
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @MyProperty
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("절대영도 아래는 불가능하다")
        self._celsius = value
```

```pyrepl
>>> t = Temperature(25)
>>> t.celsius
25
>>> t.celsius = 30
>>> t.celsius
30
>>> t.celsius = -300
Traceback (most recent call last):
  ...
ValueError: 절대영도 아래는 불가능하다
```

표준 `property` 로 만든 `Temperature2` 와 완전히 같은 값을 낸다. `Temperature.celsius` (인스턴스 없이 클래스로 접근)를 찍어 보면 `__get__` 안의 `if obj is None: return self` 가 실제로 동작함이 보인다.

```pyrepl
>>> Temperature.celsius
<__main__.MyProperty object at 0x...>
```

::: deep 세터가 없는 property도 데이터 디스크립터다
`@property` 만 쓰고 `@x.setter` 를 안 붙인 "읽기 전용 속성"도 대입을 시도하면 `AttributeError` 를 낸다. `MyProperty.__set__` 이 정의돼 있기만 하면 — 안에서 예외를 던지더라도 — **타입 자체는 여전히 데이터 디스크립터로 분류된다.** `__get__`/`__set__` 이 정의돼 있다는 사실만으로 우선순위가 결정되지, 실제로 어떻게 동작하는지는 상관없다.

```pyrepl
>>> hasattr(type(Temperature.celsius), '__set__')
True
>>> hasattr(type(Temperature.celsius), '__delete__')
True
```

이래서 `class Foo: \n    @property \n    def x(self): return 1` 처럼 세터 없는 프로퍼티에 `foo.x = 5` 를 실행하면, "속성이 없다"가 아니라 **"세터가 없다"** 는 정확한 에러가 뜬다. `__dict__` 로 우회할 길도 막혀 있다 — 데이터 디스크립터가 항상 이기기 때문이다.
:::

## 함수가 메서드가 되는 원리

[1.10 함수](#/functions)에서 함수는 일급 객체라고 배웠다. [1.12 클래스](#/classes)에서 메서드 정의는 사실 클래스 네임스페이스에 함수를 넣는 것뿐이라는 것도 봤다. 그런데 `self` 는 어디서 채워지는가? 답은 **함수 객체 자체가 비데이터 디스크립터**라는 것이다.

```pyrepl
>>> def plain_func(self):
...     return "hi"
...
>>> hasattr(plain_func, "__get__")
True
>>> hasattr(plain_func, "__set__")
False
```

`__get__` 은 있고 `__set__` 은 없다 — 정확히 비데이터 디스크립터의 정의다. 클래스 본문에 정의한 메서드는 클래스의 `__dict__` 안에 **평범한 함수 객체**로 저장된다.

```python
class Foo:
    def bar(self):
        return "bar 호출됨"
```

```pyrepl
>>> Foo.__dict__["bar"]
<function Foo.bar at 0x...>
>>> type(Foo.__dict__["bar"])
<class 'function'>
```

인스턴스로 접근하는 순간 함수의 `__get__` 이 발동해서 **바운드 메서드**(bound method)라는 별개의 객체를 만든다.

```pyrepl
>>> f = Foo()
>>> f.bar
<bound method Foo.bar of <__main__.Foo object at 0x...>>
>>> type(f.bar)
<class 'method'>
```

이게 정말 `__get__` 호출인지, 손으로 직접 불러서 확인할 수 있다.

```pyrepl
>>> bound = Foo.__dict__["bar"].__get__(f, Foo)
>>> bound()
'bar 호출됨'
>>> bound() == f.bar()
True
>>> f.bar.__func__ is Foo.__dict__["bar"]
True                    # 바운드 메서드는 원본 함수를 감싼 래퍼일 뿐이다
```

(3.14.5 실측.) `function.__get__(instance, owner)` 는 `instance` 를 첫 번째 인자로 미리 채운 `method` 객체를 반환한다. `f.bar()` 가 `Foo.bar(f)` 와 같은 이유가 여기 있다 — **디스크립터가 `self` 를 자동으로 채우는 문법적 설탕이다.**

::: note staticmethod는 왜 self가 안 채워지나
클래스 본문의 함수는 전부 비데이터 디스크립터라서 인스턴스로 접근하면 자동으로 바인딩된다. `@staticmethod` 는 이 바인딩을 **의도적으로 막는** 별도의 디스크립터로 함수를 감싼다. 바로 다음 절에서 직접 만든다.
:::

::: warn 비데이터 디스크립터는 인스턴스 dict에 진다
함수가 비데이터 디스크립터라는 사실은 인스턴스에 같은 이름의 값을 넣으면 **메서드를 가릴 수 있다**는 뜻이기도 하다.

```pyrepl
>>> f2 = Foo()
>>> f2.bar = lambda: "몽키패치됨"
>>> f2.bar()
'몽키패치됨'                # 클래스의 bar 메서드는 무시된다
>>> Foo().bar()             # 다른 인스턴스는 영향 없다
'bar 호출됨'
```

앞서 `NonDataDesc` 예제에서 본 것과 완전히 같은 메커니즘이다. 인스턴스별로 메서드를 바꿔치기하는 몽키패치가 이렇게 가능하지만, 디버깅을 어렵게 만드는 대가가 따른다.
:::

## classmethod와 staticmethod를 직접 구현해서 증명

같은 원리로 `classmethod` 와 `staticmethod` 도 직접 만들 수 있다. 둘 다 함수가 원래 하는 자동 바인딩(`self` 채우기)을 **가로채서 다르게 바꾸는** 디스크립터다.

```python title="classmethod / staticmethod 재구현"
class MyClassMethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)

        def bound_method(*args, **kwargs):
            return self.func(objtype, *args, **kwargs)   # self 대신 cls를 채운다

        return bound_method


class MyStaticMethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        return self.func            # 아무것도 채우지 않고 원본 함수를 그대로 반환
```

```python title="사용"
class Pizza:
    def __init__(self, size):
        self.size = size

    @MyClassMethod
    def from_diameter(cls, diameter):
        return cls(diameter / 2)

    @MyStaticMethod
    def describe():
        return "피자 클래스입니다"
```

```pyrepl
>>> p = Pizza.from_diameter(20)
>>> p.size
10.0
>>> Pizza.describe()
'피자 클래스입니다'
```

표준 `@classmethod` / `@staticmethod` 로 만든 동일한 클래스와 나란히 실행하면 값이 똑같다.

```pyrepl
>>> class Pizza2:
...     def __init__(self, size): self.size = size
...     @classmethod
...     def from_diameter(cls, diameter): return cls(diameter / 2)
...     @staticmethod
...     def describe(): return "피자 클래스입니다"
...
>>> Pizza2.from_diameter(20).size
10.0
>>> Pizza2.describe()
'피자 클래스입니다'
```

(3.14.5 실측 — 두 구현의 출력이 완전히 일치한다.) `classmethod` 는 "함수가 원래 받는 첫 인자를 인스턴스가 아니라 **타입**으로 바꿔치기"하는 디스크립터, `staticmethod` 는 "**아무것도 바꿔치기하지 않는**" 디스크립터일 뿐이다.

::: cote 코딩테스트 포인트
`@classmethod` 를 이용한 **대안 생성자**(alternative constructor) 패턴은 실전에서 자주 쓴다.

```python
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    @classmethod
    def from_string(cls, s):
        x, y = map(int, s.split(","))
        return cls(x, y)


p = Point.from_string("3,4")
```

상속 관계에서도 `cls` 가 실제 호출한 서브클래스를 가리키므로 `Point.from_string` 을 오버라이드 없이 서브클래스에서 그대로 물려받아도 올바른 타입의 인스턴스가 만들어진다.
:::

## `__set_name__`: 디스크립터가 자기 이름을 아는 법

지금까지의 디스크립터는 생성자에 이름을 직접 넘겨야 했다 (`DataDesc("x")` 처럼). 3.6부터는 **클래스가 만들어지는 시점에 파이썬이 자동으로 이름을 알려준다.**

```python title="__set_name__ 실제 동작"
class LoggedAttr:
    def __set_name__(self, owner, name):
        self.name = name
        self.private_name = "_" + name
        print(f"  __set_name__ 호출: owner={owner.__name__}, name={name!r}")

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value):
        print(f"  {self.name} 에 {value!r} 설정")
        setattr(obj, self.private_name, value)


class Person:
    name = LoggedAttr()
    age = LoggedAttr()
```

```pyrepl
  __set_name__ 호출: owner=Person, name='name'
  __set_name__ 호출: owner=Person, name='age'
```

이 출력은 `class Person` 문이 끝나는 **즉시**, `Person()` 을 만들기도 전에 찍힌다. `type.__new__` 가 클래스 네임스페이스를 다 채운 뒤, `__set_name__` 을 정의한 속성들을 찾아 **본문에 나온 순서대로** 호출하기 때문이다.

```pyrepl
>>> pp = Person()
>>> pp.name = "철수"
  name 에 '철수' 설정
>>> pp.age = 20
  age 에 20 설정
>>> pp.name, pp.age
('철수', 20)
```

(3.14.5 실측.) `__set_name__` 이전에는 이런 클래스를 만들려면 메타클래스를 쓰거나 이름을 직접 반복해서 넘겨야 했다(`name = LoggedAttr("name")` 처럼 실수하기 쉬운 중복). 지금은 자동이다. dataclasses의 `field()`, Django ORM의 모델 필드, SQLAlchemy의 컬럼이 전부 이 훅으로 자기 이름을 알아낸다.

## 실전 비용: 디스크립터는 공짜가 아니다

디스크립터를 거치는 속성 접근은 일반 속성 접근보다 느리다. `__get__` 호출 자체가 함수 호출 하나를 더 얹기 때문이다.

```python title="측정"
import timeit

class WithDescriptor:
    class Desc:
        def __get__(self, obj, objtype=None):
            return obj._x
        def __set__(self, obj, value):
            obj._x = value
    x = Desc()

    def __init__(self, x):
        self.x = x


class Plain:
    def __init__(self, x):
        self.x = x


wd, pl = WithDescriptor(10), Plain(10)
timeit.timeit(lambda: wd.x, number=2_000_000)   # 0.0937초
timeit.timeit(lambda: pl.x, number=2_000_000)   # 0.0297초
```

::: perf 실측 결과
2백만 번 접근 기준 디스크립터 경유가 약 **3.2배** 느리다(3.14.5 / Windows 실측, 자릿수 차이는 기기마다 다를 수 있다). 절대 시간은 둘 다 마이크로초 단위라 대부분의 코드에서 체감되지 않는다. 다만 **핫 루프 안에서 수백만 번 접근하는 속성**이라면 이야기가 다르다. 검증이 필요 없는 단순 값 저장에는 디스크립터도, `property` 도 씌우지 말고 그냥 평범한 속성으로 둬라.
:::

## 언제 쓰지 말아야 하는가

디스크립터는 강력한 만큼 **읽는 사람에게 "이건 그냥 속성이 아니다"라는 경고 없이 몰래 함수를 실행시킨다.** 다음 상황에서는 피하라.

- **검증이나 계산이 필요 없는 단순 저장.** 그냥 `self.x = x` 로 충분하면 `property` 도 굳이 씌우지 마라. "나중에 검증이 필요할 수도 있으니 미리 property로"는 YAGNI 위반이다. 필요해지면 그때 `property` 로 바꿔도 **호출부 코드는 안 바뀐다** — 이게 애초에 property가 존재하는 이유다.
- **디스크립터 인스턴스에 상태를 저장하는 것.** 클래스 속성인 디스크립터 객체는 **그 클래스의 모든 인스턴스가 공유**한다. `self.value = x` 처럼 디스크립터 자신에 값을 저장하면 한 인스턴스의 값이 다른 인스턴스에도 새어 나간다. 반드시 `obj.__dict__` 나 `setattr(obj, ...)` 로 **인스턴스 쪽에** 저장해야 한다 — 이 절의 모든 예제가 그렇게 했다.
- **디버깅 난이도를 과소평가하는 것.** `__get__`/`__set__` 안에서 예외가 나면 스택 트레이스가 "속성 접근"이 아니라 디스크립터 내부 코드를 가리킨다. 팀 전체가 디스크립터 프로토콜을 이해하고 있지 않다면, 단순 검증에는 `__init__` 안의 assert 나 별도 검증 함수로 충분할 때가 많다.
- **성능이 민감한 핫 패스.** 방금 측정한 배수를 기억하라. 초당 수백만 번 접근되는 속성에 디스크립터를 씌우면 그 배수가 그대로 누적된다.

메타클래스처럼 "프레임워크를 만드는 사람"의 도구이지 "매 프로젝트마다 쓰는" 도구가 아니다. `dataclasses`, ORM, 검증 라이브러리를 직접 만들 게 아니라면 표준 `property` 만으로 대부분 해결된다. 커스텀 디스크립터가 정말 필요해지는 지점은 **같은 검증·변환 로직을 여러 속성에 반복해서 적용**해야 할 때다 — 그때는 `property` 를 클래스마다 다시 쓰는 대신 재사용 가능한 디스크립터 하나로 뽑아낼 가치가 있다.

## 요약

- 디스크립터는 `__get__`/`__set__`/`__delete__` 중 하나 이상을 정의하고 **다른 클래스의 클래스 속성**으로 저장된 객체다.
- 우선순위는 **데이터 디스크립터 > 인스턴스 `__dict__` > 비데이터 디스크립터 > 클래스 속성** 순이다. 실측으로 확인했다.
- `property` 는 마법이 아니라 `__get__`/`__set__`/`__delete__` 를 구현한 평범한 클래스다. 직접 만든 `MyProperty` 가 표준 `property` 와 동일하게 동작함을 확인했다.
- **함수 자체가 비데이터 디스크립터다.** `Foo.__dict__["bar"].__get__(instance, Foo)` 가 `instance.bar` 와 똑같은 바운드 메서드를 만든다.
- `classmethod` 는 첫 인자를 인스턴스 대신 타입으로 채우는 디스크립터, `staticmethod` 는 아무것도 채우지 않는 디스크립터다. 둘 다 직접 만들어 증명했다.
- `__set_name__` 은 클래스가 만들어지는 순간 파이썬이 자동으로 호출해서 디스크립터가 자기 이름을 알게 해 준다.
- 디스크립터 접근은 일반 속성 접근보다 느리다(실측 약 3.2배). 검증이 필요 없으면 쓰지 마라. 디스크립터 자신에 상태를 저장하면 모든 인스턴스가 공유하는 버그가 생긴다.

::: quiz 연습문제
1. 다음 클래스에서 `Foo().x` 와 `Foo().y` 는 각각 무엇을 출력하는가? 인스턴스 `__dict__` 에 `x`, `y` 를 직접 넣은 뒤에는 어떻게 달라지는가? 예측한 뒤 실행해서 확인하라.

   ```python
   class ReadOnly:
       def __get__(self, obj, objtype=None):
           return "readonly"

   class Writable:
       def __get__(self, obj, objtype=None):
           return obj.__dict__.get("_w", "default")
       def __set__(self, obj, value):
           obj.__dict__["_w"] = value

   class Foo:
       x = ReadOnly()
       y = Writable()
   ```

2. 왜 디스크립터 클래스 안에서 `self.value = x` 처럼 값을 저장하면 안 되는가? 서로 다른 두 인스턴스로 실제로 재현해서 증명하라.

3. `classmethod` 를 상속 관계에서 쓰면 `cls` 가 실제로 호출한 서브클래스를 가리킨다. 이 절의 `MyClassMethod` 구현이 이 동작을 그대로 재현하는지, `Pizza` 를 상속한 서브클래스로 확인하라.

4. `__set_name__` 이 없던 시절에는 이름을 어떻게 넘겼을지 생각해 보고, 이 절의 `DataDesc("x")` 처럼 이름을 직접 넘기는 방식과 `__set_name__` 을 쓰는 방식의 차이를 설명하라. 이름을 실수로 다르게 넘기면(`x = DataDesc("y")`) 어떤 버그가 생기는가?

5. **깊이 생각해 볼 문제.** `staticmethod` 로 감싼 함수는 `Foo.__dict__["static_method"]` 로 접근하면 무엇이 나오는가? `MyStaticMethod` 인스턴스인가, 원본 함수인가? `dis` 나 직접 출력으로 확인하고, 왜 그렇게 설계됐는지 설명하라.
:::

**다음 절**: [3.4 메타클래스와 __init_subclass__](#/metaclass) — 클래스가 만들어지는 순간 자체를 가로채는 법, 그리고 그 힘을 언제 쓰지 말아야 하는가.
