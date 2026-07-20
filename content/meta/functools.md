# 3.1 일급 함수와 functools

::: lead
[1.10 함수](#/functions)에서 함수가 "일급 객체"라고 배웠다. 이 절은 그게 **실전에서 뭘 의미하는지** 를 다룬다. 함수를 변수에 담을 수 있다는 사실 자체는 별로 놀랍지 않다. 진짜 쓸모는 함수를 **가공하는 함수** — 인자를 미리 발라두거나, 결과를 캐싱하거나, 타입에 따라 다른 함수로 갈아 끼우는 것 — 를 만들 수 있다는 데서 나온다. `functools` 는 그 가공 도구 상자다. 이 절에서는 네 개의 핵심 도구(`partial`, `reduce`, `lru_cache`, `singledispatch`)와 `cached_property` 를 직접 실행해 보면서, 겉보기엔 마법 같은 동작이 실제로 어떤 객체와 어떤 자료구조로 구현되는지 증명한다.
:::

## 일급 함수, 그래서 뭐가 되는가

"함수는 일급 객체다"를 실전 문장으로 바꾸면 이렇다. **함수는 int나 str과 똑같이 변수에 담기고, 리스트에 들어가고, 다른 함수의 인자로 넘어가고, 함수의 반환값이 될 수 있다.**

```pyrepl
>>> def double(x): return x * 2
>>> def triple(x): return x * 3
>>> ops = {"double": double, "triple": triple}   # 함수를 값으로 dict에 저장
>>> ops["double"](5)
10
>>> pipeline = [double, triple, double]           # 함수를 리스트에 저장
>>> value = 1
>>> for op in pipeline:
...     value = op(value)
>>> value
12
```

이 성질이 없으면 콜백, 전략 패턴, 데코레이터([1.11 데코레이터](#/decorators)) 전부 불가능하다. `functools` 의 모든 함수는 이 성질 위에서 동작한다 — **함수를 받아서 새로운 함수(또는 함수처럼 동작하는 객체)를 반환한다.**

## `functools.partial` — 인자를 미리 발라둔 새 객체

### 문제부터

같은 함수를 인자 하나만 고정해서 반복 호출하는 상황은 흔하다.

```python title="반복되는 인자"
def power(base, exp):
    return base ** exp

# 매번 exp=2를 반복해서 써야 한다
squares = [power(n, 2) for n in range(5)]
```

`lambda n: power(n, 2)` 로 감싸도 되지만, `functools.partial` 은 이걸 **함수 정의 없이** 처리한다.

```pyrepl
>>> import functools
>>> square = functools.partial(power, exp=2)
>>> square(5)
25
>>> square(10)
100
```

### `partial` 이 실제로 반환하는 것

여기서 흔한 오해가 있다. `partial(power, exp=2)` 가 **새 함수를 만든다**고 생각하기 쉽다. 아니다. **`functools.partial` 타입의 인스턴스**를 만든다.

```pyrepl
>>> square = functools.partial(power, exp=2)
>>> type(square)
<class 'functools.partial'>
>>> square
functools.partial(<function power at 0x000002AB99F33480>, exp=2)
>>> square.func
<function power at 0x000002AB99F33480>
>>> square.args
()
>>> square.keywords
{'exp': 2}
```

`partial` 객체는 원본 함수(`func`), 고정된 위치 인자(`args`), 고정된 키워드 인자(`keywords`)를 **속성으로 들고 있는 콜러블**이다. 호출하면 저장해 둔 인자와 새로 받은 인자를 합쳐서 원본 함수를 호출한다.

::: deep 손으로 재구현해서 증명한다
`partial` 이 마법이 아니라는 걸 확인하는 가장 확실한 방법은 직접 만들어 보는 것이다.

```python title="partial의 최소 재구현"
class MyPartial:
    def __init__(self, func, /, *args, **kwargs):
        self.func = func
        self.args = args
        self.keywords = kwargs

    def __call__(self, *more_args, **more_kwargs):
        kwargs = {**self.keywords, **more_kwargs}   # 호출 시점 인자가 우선
        return self.func(*self.args, *more_args, **kwargs)

    def __repr__(self):
        return f"MyPartial({self.func.__name__}, args={self.args}, keywords={self.keywords})"
```

```pyrepl
>>> square = MyPartial(power, exp=2)
>>> square(5)
25
>>> square
MyPartial(power, args=(), keywords={'exp': 2})
>>> official = functools.partial(power, exp=2)
>>> official(5) == square(5)
True
```

실제 `functools.partial` 은 C로 구현돼 있어 더 빠르지만(호출마다 파이썬 함수 프레임을 하나 덜 만든다), **개념적으로는 이 25줄짜리 클래스와 완전히 같다.** [1.12 클래스](#/classes)에서 본 `__call__` 이 콜러블을 만드는 바로 그 방법이다.
:::

### 호출할 때마다 새 객체가 아니다 — 만들 때 한 번

`partial` 이 반환한 객체는 **한 번 만들어지면 계속 재사용된다.** 호출은 그 객체의 `__call__` 을 실행할 뿐, 새 `partial` 을 만들지 않는다.

```pyrepl
>>> p1 = functools.partial(power, exp=2)
>>> p2 = functools.partial(power, exp=2)
>>> p1 is p2
False          # 같은 인자로 만들어도 매번 새 객체다
>>> p1 == p2
False          # partial은 __eq__를 정의하지 않는다 — 정체성으로만 비교된다
```

::: warn partial 객체는 값으로 비교되지 않는다
`functools.partial` 은 `__eq__` 를 오버라이드하지 않는다. 그래서 두 `partial` 이 똑같은 함수와 똑같은 인자로 만들어졌어도 `==` 는 `is` 와 같은 결과([1.1 객체·이름·참조](#/objects-names))를 낸다. `partial` 객체를 dict 키나 set 원소로 써서 "같은 설정이면 하나로 합쳐지겠지"라고 기대하면 틀린다.
:::

::: deep 중첩된 partial은 평평해진다
`partial` 로 만든 결과를 다시 `partial` 로 감싸면 어떻게 될까? 실측해 보면 놀라운 사실이 나온다.

```pyrepl
>>> p1 = functools.partial(power, exp=2)
>>> p2 = functools.partial(p1, base=10)
>>> p2.func is power        # p1이 아니라 power 자체다!
True
>>> p2.func
<function power at 0x0000024248A33480>
>>> p2.args, p2.keywords
() {'exp': 2, 'base': 10}
>>> p2()
100
```

`p2.func` 가 `p1` 이 아니라 `power` 다. `functools.partial` 은 생성자에서 **인자로 받은 게 또 다른 `partial` 이면, 그 안의 `func` 와 `args`/`keywords` 를 꺼내서 합쳐 버린다.** 겹겹이 감싼 래퍼를 한 겹으로 눌러 놓는 것이다. 호출 하나마다 파이썬 프레임이 하나씩 쌓이는 걸 막기 위한 최적화다. 위치 인자도 같은 방식으로 이어붙는다.

```pyrepl
>>> def f(a, b, c): return (a, b, c)
>>> p = functools.partial(f, 1)
>>> p2 = functools.partial(p, 2)
>>> p2.func is f, p2.args
(True, (1, 2))
>>> p2(3)
(1, 2, 3)
```
:::

::: perf partial이 람다보다 느릴 수 있다
100만 번 호출해서 실측했다.

```python
square = functools.partial(power, exp=2)
square_lambda = lambda base: power(base, exp=2)

timeit.timeit(lambda: square(5), number=1_000_000)          # 0.096초
timeit.timeit(lambda: square_lambda(5), number=1_000_000)   # 0.062초
```

(Python 3.14.5 / Windows 기준. 절대값은 기기마다 다르다.) 실측해 보면 오히려 **람다가 더 빠르다** — `partial.__call__` 은 C 레벨이지만 매 호출마다 `{**self.keywords, **more_kwargs}` 에 해당하는 딕셔너리 병합을 다시 해야 하기 때문이다. `partial` 을 쓰는 이유는 속도가 아니라 **의도 표현**이다. "이 함수의 이 인자는 고정됐다"는 사실이 이름에 드러난다.
:::

## `functools.reduce` — 그리고 왜 인기가 없는가

`reduce` 는 시퀀스를 왼쪽에서 오른쪽으로 접어 나가며 누적값 하나로 줄인다.

```pyrepl
>>> import functools
>>> nums = [1, 2, 3, 4, 5]
>>> functools.reduce(lambda acc, x: acc + x, nums)
15
>>> functools.reduce(lambda acc, x: acc * x, nums, 1)   # 세 번째 인자는 초깃값
120
```

`reduce(f, [x1, x2, x3])` 는 `f(f(x1, x2), x3)` 와 같다. 초깃값을 주면 `f(f(f(init, x1), x2), x3)` 다.

::: hist reduce는 원래 내장 함수였다
파이썬 2에서 `reduce` 는 `map`, `filter` 와 함께 **내장 함수**였다. 파이썬 3에서는 `functools` 로 옮겨졌다. 귀도 반 로섬이 직접 쓴 글("The fate of reduce() in Python 3000")에서 그 이유를 밝혔는데, 요지는 **"람다와 함께 쓰인 reduce는 대부분 for 루프보다 읽기 어렵다"** 는 것이다. 실제로 아래 두 코드는 같은 일을 한다.

```python
# reduce 버전 — "무엇을 누적하는지"가 람다 안에 숨는다
longest = functools.reduce(lambda a, b: a if len(a) >= len(b) else b, words)

# for 루프 버전 — 의도가 이름에 드러난다
longest = words[0]
for w in words[1:]:
    if len(w) > len(longest):
        longest = w

# 사실 이 문제엔 이미 답이 있다 — 표준 라이브러리에.
longest = max(words, key=len)
```

**교훈은 "reduce를 쓰지 마라"가 아니라 "먼저 `sum`, `max`, `min`, `any`, `all`, `math.prod` 를 의심하라"** 는 것이다. 이들은 파이썬 표준 라이브러리가 이미 최적화해 둔 **이름 붙은 reduce** 다. `reduce` 는 그 표준 도구가 없을 때만 꺼낸다.
:::

::: perf sum이 reduce보다 빠르다 — C 루프 vs 파이썬 호출
```python
nums = list(range(1000))
functools.reduce(lambda a, b: a + b, nums)   # 10000회 반복: 0.282초
sum(nums)                                     # 10000회 반복: 0.022초  → 약 13배
```

(Python 3.14.5 / Windows 기준.) `sum` 은 C 레벨 루프 안에서 덧셈을 하지만, `reduce` 는 매 원소마다 파이썬 람다 호출(프레임 생성 + 바이트코드 실행)을 거친다. **1000배 차이가 아니라 10배 남짓**인 이유는 덧셈 자체는 싸고 호출 오버헤드가 지배적이기 때문이다. 원소가 많을수록, 콜백이 무거울수록 이 격차는 좁혀진다.
:::

::: warn 초깃값 없는 reduce는 빈 시퀀스에서 터진다
```pyrepl
>>> functools.reduce(lambda a, b: a + b, [])
Traceback (most recent call last):
  ...
TypeError: reduce() of empty iterable with no initial value
>>> functools.reduce(lambda a, b: a + b, [], 0)
0
```

입력이 빈 리스트일 수 있는 코드에서는 **반드시 초깃값을 명시하라.** `sum([])` 이 조용히 `0` 을 반환하는 것과 대조적이다.
:::

## `functools.lru_cache` — 캐시 히트를 직접 세어 본다

`lru_cache` 는 함수 호출을 인자 기준으로 기억해 뒀다가, 같은 인자로 다시 불리면 **함수를 실행하지 않고** 저장된 결과를 돌려준다.

```python title="캐시가 없으면 지수 시간"
import functools

@functools.lru_cache(maxsize=None)
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
```

```pyrepl
>>> fib(30)
832040
>>> fib.cache_info()
CacheInfo(hits=28, misses=31, maxsize=None, currsize=31)
```

**추측하지 마라. `cache_info()` 가 사실을 말해 준다.** `fib(30)` 한 번 호출에 서로 다른 인자(`fib(0)` 부터 `fib(30)` 까지 31개)에 대해 미스가 31번, 그리고 재귀 트리에서 이미 계산된 값을 다시 요청한 게 28번이다.

```pyrepl
>>> fib.cache_clear()
>>> fib.cache_info()
CacheInfo(hits=0, misses=0, maxsize=None, currsize=0)
```

::: perf 캐시 있고 없고의 차이는 자릿수가 다르다
```python
fib_plain(28)      # 캐시 없음: 0.0241초
fib_cached(28)     # lru_cache: 0.0000268초  → 약 900배
```

(Python 3.14.5 / Windows 기준.) 캐시 없는 `fib` 는 $O(2^n)$, 캐시 있는 `fib` 는 각 `n` 을 한 번씩만 계산하므로 $O(n)$ 이다. 이게 [7.20 동적 계획법 기초](#/dp-basics)에서 말하는 **메모이제이션**이고, `lru_cache` 는 그 메모이제이션을 데코레이터 한 줄로 얻는 방법이다.
:::

### `maxsize` — 캐시는 무한하지 않다

`maxsize` 는 캐시에 넣어 둘 **서로 다른 인자 조합의 최대 개수**다. 꽉 차면 **가장 오래전에 쓰인(least recently used) 항목부터 버린다.**

```pyrepl
>>> @functools.lru_cache(maxsize=2)
... def track(x): return x * 10
...
>>> track(1); track(2)
>>> track.cache_info()
CacheInfo(hits=0, misses=2, maxsize=2, currsize=2)
>>> track(3)                    # 캐시가 꽉 참 → 가장 안 쓰인 1을 밀어낸다
>>> track.cache_info()
CacheInfo(hits=0, misses=3, maxsize=2, currsize=2)
>>> track(1)                    # 밀려났으니 다시 계산해야 한다
>>> track.cache_info()
CacheInfo(hits=0, misses=4, maxsize=2, currsize=2)
```

`misses` 가 계속 늘어난다 — `track(1)` 이 캐시에서 밀려났기 때문에 다시 계산됐다. **`maxsize=None`(또는 데코레이터 인자 없이 사용) 은 무제한**이라는 뜻이고, 인자 조합이 무한하거나 아주 많을 수 있는 함수에 그냥 붙이면 캐시 자체가 메모리를 무한히 먹는다.

::: warn 캐시 키는 인자다 — 그리고 인자는 해시 가능해야 한다
```pyrepl
>>> @functools.lru_cache
... def f(x): return x
...
>>> f([1, 2, 3])
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'list'
```

`lru_cache` 는 내부적으로 `(args, kwargs)` 를 dict 키로 쓴다([1.6 dict](#/dict)의 해시 테이블). 리스트나 dict처럼 해시 불가능한 인자를 넘기면 캐싱 자체가 불가능하다.
:::

::: deep typed — int와 float은 같은 캐시 자리를 쓰는가
`typed=True` 를 주면 `1` 과 `1.0` 처럼 **값은 같아도 타입이 다른 인자를 다른 캐시 항목으로 취급한다.**

```pyrepl
>>> @functools.lru_cache(maxsize=None, typed=True)
... def g(x): return x
...
>>> g(1); g(1.0)
>>> g.cache_info()
CacheInfo(hits=0, misses=2, maxsize=None, currsize=2)
```

여기서 실측으로만 드러나는 함정이 하나 있다. **`typed=False`(기본값)라고 해서 `1` 과 `1.0` 이 항상 같은 자리를 쓰는 것도 아니다.**

```pyrepl
>>> @functools.lru_cache(maxsize=None, typed=False)
... def h(x): return x
...
>>> h(1)
1
>>> h(1.0)
1.0
>>> h.cache_info()
CacheInfo(hits=0, misses=2, maxsize=None, currsize=2)   # 히트가 아니라 미스!
```

이유는 CPython의 내부 최적화에 있다. `functools._make_key` 는 인자가 **하나뿐이고 그 타입이 `int` 또는 `str` 일 때**, 튜플로 감싸지 않고 **그 값 자체를 캐시 키로 바로 쓴다**(할당을 하나 아끼는 최적화). `1` 은 이 빠른 경로를 타서 키가 정수 `1` 이 되지만, `1.0` 은 `float` 이라 빠른 경로를 타지 않고 `_HashedSeq((1.0,))` 라는 다른 종류의 객체가 키가 된다. `1 == 1.0` 이 `True` 여도 **정수 `1` 과 `_HashedSeq` 객체는 타입이 달라 `dict` 에서 같은 자리로 취급되지 않는다.** `bool` 도 마찬가지다 — `True == 1` 이지만 `type(True)` 는 `int` 가 아니므로 같은 함정에 걸린다. **`typed` 옵션 이름만 보고 "false면 값이 같으면 항상 캐시가 재사용된다"고 믿지 마라.** 인자 타입을 애초에 통일하는 게 안전하다.
:::

::: danger 메서드에 lru_cache를 직접 붙이면 인스턴스가 새지 않는다
```python title="숨은 메모리 누수"
class Widget:
    def __init__(self, name):
        self.name = name

    @functools.lru_cache(maxsize=None)
    def compute(self, x):
        return x * 2

    def __del__(self):
        print(f"{self.name} 소멸")

w = Widget("A")
w.compute(1)
del w
```

```text nolines
del 이후
A 소멸           <- 이 줄이 훨씬 나중에, 인터프리터 종료 시점에야 찍힌다
```

실행해 보면 `del w` 직후에도, 심지어 `gc.collect()` 를 호출해도 `__del__` 이 바로 실행되지 않는다. 프로그램이 끝날 때가 돼서야 소멸된다. 이유는 `lru_cache` 의 캐시 키가 `(self, x)` — **`self` 자체를 인자로 포함**하기 때문이다. 캐시 딕셔너리가 `self` 를 계속 참조하는 한, [1.1 참조 카운트](#/objects-names)는 0이 되지 않는다. 인스턴스가 아무리 많이 생기고 죽어도 `compute` 가 한 번이라도 불린 인스턴스는 **클래스에 붙은 캐시 안에서 영원히 산다.**

인스턴스 메서드를 캐싱하려면 인스턴스별로 캐시를 두거나(`functools.cached_property`, 아래에서 다룬다), `maxsize` 를 제한해 강제로 밀려나게 하거나, 아예 순수 함수로 빼서 `self` 대신 필요한 값만 인자로 넘겨라.
:::

## `functools.singledispatch` — 타입에 따라 다른 함수로

`if isinstance(x, int): ... elif isinstance(x, list): ...` 를 함수 하나에 쌓는 대신, **타입별로 함수를 따로 정의하고 자동으로 갈아 끼울** 수 있다.

```python title="타입별 렌더러"
import functools

@functools.singledispatch
def render(value):
    return f"기본: {value!r}"

@render.register
def _(value: int):
    return f"정수: {value}"

@render.register
def _(value: list):
    return f"리스트({len(value)}개): {value}"

@render.register(dict)
def _render_dict(value):
    return f"딕셔너리({len(value)}개 키)"
```

```pyrepl
>>> render(3.14)
'기본: 3.14'
>>> render(42)
'정수: 42'
>>> render([1, 2, 3])
'리스트(3개): [1, 2, 3]'
>>> render({"a": 1})
'딕셔너리(1개 키)'
```

`@render.register` 는 함수의 타입 힌트를 읽어서 등록한다(그래서 함수 이름이 `_` 여도 상관없다 — 진짜 이름은 `render.registry` 에 등록된 타입이다). 힌트 대신 `@render.register(dict)` 처럼 타입을 직접 줘도 된다.

```pyrepl
>>> render.registry.keys()
dict_keys([<class 'object'>, <class 'int'>, <class 'list'>, <class 'dict'>])
```

### 등록되지 않은 타입은 MRO를 따라간다

`register` 하지 않은 타입이 들어오면, [1.13 상속](#/inheritance)에서 다룬 **MRO를 따라 올라가며** 가장 가까운 등록 타입을 찾는다.

```pyrepl
>>> class MyList(list): pass
...
>>> render(MyList([1, 2]))
'리스트(2개): [1, 2]'
>>> render(True)
'정수: True'
```

`MyList` 는 `list` 를 등록해 뒀으니 그걸 쓴다. `bool` 은 등록한 적 없지만 `bool` 이 `int` 의 서브클래스이므로 `int` 핸들러로 간다. **일치하는 등록이 없으면 `object` 핸들러(`@singledispatch` 를 붙인 원본 함수)로 떨어진다** — 그래서 `render(3.14)` 가 "기본:"으로 처리됐다.

### 메서드 버전: `singledispatchmethod`

클래스 안에서 같은 패턴을 쓰려면 `self` 가 첫 인자로 끼기 때문에 `singledispatch` 를 그대로 못 쓴다. `singledispatchmethod` 가 그 문제를 해결한다.

```pyrepl
>>> class Formatter:
...     @functools.singledispatchmethod
...     def format(self, value):
...         return f"?{value}"
...     @format.register
...     def _(self, value: int):
...         return f"int:{value}"
...     @format.register
...     def _(self, value: str):
...         return f"str:{value}"
...
>>> f = Formatter()
>>> f.format(5)
'int:5'
>>> f.format("hi")
'str:hi'
```

::: tip 언제 singledispatch를, 언제 그냥 isinstance를 쓸까
분기가 **두세 개**뿐이고 한 파일 안에서 끝난다면 `isinstance` 체인이 오히려 더 읽기 쉽다. `singledispatch` 가 진짜 값어치를 하는 상황은 **새 타입이 추가될 때마다 원본 함수를 건드리지 않고 별도로 등록만 하고 싶을 때** — 플러그인 구조, 외부에서 확장 가능한 라이브러리를 만들 때다. 등록이 여기저기 흩어지면(어떤 타입이 어디서 등록됐는지 찾기 어려워지면) 오히려 `isinstance` 체인보다 못하다.
:::

## `cached_property` — 인스턴스마다 한 번만 계산한다

`lru_cache` 를 메서드에 직접 붙이면 안 되는 이유를 방금 봤다. **인스턴스 하나에 속하는 계산 결과를 한 번만 만들고 재사용하고 싶을 때** 쓰는 게 `functools.cached_property` 다.

```python title="비싼 계산을 한 번만"
import functools, time

class DataSet:
    def __init__(self, values):
        self.values = values

    @functools.cached_property
    def total(self):
        print("계산 중...")
        time.sleep(0.1)
        return sum(self.values)
```

```pyrepl
>>> d = DataSet([1, 2, 3, 4, 5])
>>> d.total
계산 중...
15
>>> d.total          # 두 번째부터는 계산 없이 바로 반환
15
```

### 어떻게 "한 번만"이 되는가 — `__dict__` 에 값을 심는다

```pyrepl
>>> d.__dict__
{'values': [1, 2, 3, 4, 5], 'total': 15}
```

비밀은 여기 있다. **`total` 이라는 이름이 인스턴스의 `__dict__` 에 직접 박혔다.** 이건 [3.3 디스크립터](#/descriptors)에서 다룰 **비-데이터 디스크립터**(non-data descriptor)의 동작 방식이다 — `__get__` 만 있고 `__set__` 이 없는 디스크립터는, 인스턴스 `__dict__` 에 같은 이름이 있으면 **그쪽이 우선**이다. `cached_property` 는 처음 접근할 때 계산해서 그 결과를 **인스턴스 `__dict__` 에 직접 써 버린다.** 그러면 다음 접근부터는 디스크립터의 `__get__` 이 호출되기도 전에 인스턴스 속성 조회가 먼저 값을 찾아 끝낸다. 이게 [1.12 클래스](#/classes)의 `@property` 와 결정적으로 다른 점이다 — `property` 는 매번 `__get__` 을 다시 실행한다.

무효화하고 싶으면 그 속성을 지우면 된다.

```pyrepl
>>> del d.total
>>> d.total
계산 중...
15
```

::: warn __slots__ 를 쓰는 클래스에는 못 붙인다
```pyrepl
>>> class Slotted:
...     __slots__ = ("values",)
...     @functools.cached_property
...     def total(self):
...         return sum(self.values)
...
>>> s = Slotted()
>>> s.values = [1, 2, 3]
>>> s.total
Traceback (most recent call last):
  ...
TypeError: No '__dict__' attribute on 'Slotted' instance to cache 'total' property.
```

`cached_property` 는 결과를 저장할 인스턴스 `__dict__` 가 반드시 필요하다. `__slots__` 를 쓰는 클래스는 `__dict__` 를 없애서 메모리를 아끼는 게 목적이므로 — 둘은 근본적으로 상충한다. `__slots__` 를 쓰면서 캐시가 필요하면, 슬롯 하나를 직접 만들어 수동으로 캐싱해야 한다.
:::

::: note 스레드 안전성
`cached_property` 의 기본 구현은 락을 걸지 않는다. 여러 스레드가 동시에 처음 접근하면 계산 함수가 두 번 이상 실행될 수 있다(값 자체는 결국 하나로 안착하지만, 부수 효과가 있는 계산이면 위험하다). [4.2 threading](#/threading)의 `Lock` 으로 감싸거나, 계산이 순수 함수인지 먼저 확인해라.
:::

## `wraps` — 짧게 복습

[1.11 데코레이터](#/decorators)에서 `functools.wraps` 를 이미 자세히 다뤘다. 여기서 이 절과 연결되는 지점만 다시 짚는다. **`wraps` 도 결국 `partial` 이다.**

```pyrepl
>>> import functools, inspect
>>> inspect.signature(functools.wraps)
<Signature (wrapped, assigned=('__module__', '__name__', '__qualname__', '__doc__', '__annotate__', '__type_params__'), updated=('__dict__',))>
```

`wraps(f)` 는 `partial(update_wrapper, wrapped=f, ...)` 를 반환한다. 즉 이 절에서 배운 "함수를 미리 발라둔 콜러블을 만든다"는 `partial` 의 정의를 데코레이터 자신에게 적용한 것이다. `functools` 안의 도구들이 서로를 재료로 쓰고 있다는 뜻이다.

## 요약

- 함수는 값이다. 변수·리스트·dict에 담기고, 인자로도 반환값으로도 쓰인다 — 이 성질 위에 `functools` 전체가 서 있다.
- `partial(f, ...)` 은 새 함수가 아니라 `func`/`args`/`keywords` 를 들고 있는 **`functools.partial` 인스턴스**다. `==` 로 비교되지 않고, 중첩하면 자동으로 평평해진다.
- `reduce` 는 대부분 `sum`/`max`/`min`/`math.prod` 로 대체된다. 굳이 쓸 땐 빈 시퀀스를 대비해 초깃값을 명시하라.
- `lru_cache` 는 `cache_info()` 로 히트/미스를 직접 확인할 수 있다. `maxsize` 는 LRU 정책으로 오래된 항목부터 버린다. 인스턴스 메서드에 직접 붙이면 `self` 가 캐시에 붙들려 죽지 않는다.
- `singledispatch` 는 MRO를 따라 타입별 함수를 찾는다. 분기가 몇 개 안 되면 `isinstance` 가 더 낫다.
- `cached_property` 는 인스턴스 `__dict__` 에 결과를 심어서 "한 번만 계산"을 구현한다. `__slots__` 클래스에는 못 쓴다.

::: quiz 연습문제
1. `functools.partial(f, a, b)` 로 만든 객체를 다시 `functools.partial(그 결과, c)` 로 감쌌다. 최종 객체의 `.func` 와 `.args` 는 무엇인가? 실행해서 확인하라.
2. 빈 리스트에 `reduce(lambda a, b: a + b, lst)` 를 초깃값 없이 호출하면 왜 에러가 나는가? `sum([])` 은 왜 에러가 안 나는가?
3. `maxsize=1` 인 `lru_cache` 함수에 `f(1)`, `f(2)`, `f(1)` 을 순서대로 호출했다. `cache_info()` 의 `hits`, `misses` 는 각각 몇인가? 예측한 뒤 실행해서 확인하라.
4. 어떤 클래스의 메서드에 `lru_cache` 를 직접 붙였더니, 그 클래스의 인스턴스가 프로그램이 끝날 때까지 메모리에서 사라지지 않는다는 걸 발견했다. 원인을 설명하고, `cached_property` 를 써서 고쳐라.
5. `singledispatch` 로 등록된 타입이 `int`, `list` 뿐인 함수에 `bool` 값을 넘기면 어떤 핸들러가 실행되는가? 그 이유를 MRO 관점에서 설명하라.
:::

**다음 절**: [3.2 itertools 완전 정복](#/itertools) — 무한 이터레이터, 조합론, 그룹핑. 리스트를 만들지 않고도 조합을 세는 법.
