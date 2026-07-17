# 1.10 함수: 인자, 스코프, 클로저

::: lead
`def` 는 문법이 아니라 **런타임 동작**이다. 함수가 정의되는 순간 CPython은 코드 객체를 감싸는 함수 객체를 만들고, 기본값을 평가해 튜플에 박아 넣고, 바깥 지역 변수를 담을 `cell` 을 연결한다. 이 절은 그 셋 — **인자 바인딩, 기본값의 수명, 이름 해석** — 이 실제로 어떻게 돌아가는지를 본다. 파이썬 함정의 절반이 여기서 나온다. `def f(x=[])` 가 왜 미쳤는지, 루프 안 `lambda` 가 왜 전부 같은 값을 뱉는지, 답이 전부 여기 있다.
:::

## 문제부터

세 개다. 답을 먼저 예측하라.

```python title="세 개의 수수께끼"
# ①
def f(x=[]):
    x.append(1)
    return len(x)
print(f(), f(), f())

# ②
fs = [lambda: i for i in range(3)]
print([g() for g in fs])

# ③
n = 1
def g():
    print(n)
    n = 2
g()
```

정답은 `1 2 3` / `[2, 2, 2]` / `UnboundLocalError` 다. 셋 다 직관과 다르고, 셋 다 **같은 원리의 다른 얼굴**이다. 그 원리를 깔고 가자.

## 호출 규약: 인자는 어떻게 자리를 찾아가는가

시그니처는 다섯 구역으로 나뉜다. 순서는 고정이다.

```text nolines
def f( a, b, /, c, d, *args, e, f=10, **kwargs )
       ^^^^  ^  ^^^^  ^^^^^  ^^^^^^^  ^^^^^^^^
        |    |    |      |       |        |
        |    |    |      |       |        +-- 4) leftover keywords -> dict
        |    |    |      |       +----------- 3) keyword-only
        |    |    |      +------------------- 2) leftover positionals -> tuple
        |    |    +-------------------------- 1) positional-or-keyword
        |    +------------------------------- '/' marker
        +------------------------------------ 0) positional-only
```

이 구역 정보는 문법 장식이 아니다. **코드 객체 안에 숫자로 박혀 있다.**

```pyrepl
>>> def f(a, b, /, c, d, *args, e, f=10, **kwargs): pass
...
>>> f.__code__.co_argcount
4
>>> f.__code__.co_posonlyargcount
2
>>> f.__code__.co_kwonlyargcount
2
>>> f.__code__.co_varnames
('a', 'b', 'c', 'd', 'e', 'f', 'args', 'kwargs')
>>> f.__code__.co_flags
15
```

읽는 법이 있다. `co_argcount` 는 위치로 넘길 수 **있는** 인자 수(4개: a,b,c,d)이고, 그중 앞 `co_posonlyargcount` 개(a,b)는 위치로만 받는다. 그 뒤 `co_kwonlyargcount` 개(e,f)가 키워드 전용이다. `co_varnames` 는 **선언 순서가 아니라 슬롯 순서**다 — `args` 와 `kwargs` 가 맨 뒤로 밀려 있다. 지역 변수는 배열 슬롯이고, 매개변수는 그 배열의 앞자리를 차지한다.

`co_flags` 의 `15` 는 `0b1111` — `OPTIMIZED`(1) · `NEWLOCALS`(2) · `VARARGS`(4) · `VARKEYWORDS`(8)이 켜졌다. "`*args` 도 있고 `**kwargs` 도 있다"가 비트 두 개로 표현된다.

### `/` 와 `*` 가 하는 일

두 마커는 **호출자가 이름을 쓸 수 있는 범위**를 자른다. `/` 왼쪽은 위치로만, `*` 오른쪽은 키워드로만 받는다.

```pyrepl
>>> def pos_only(a, b, /): return a + b
...
>>> pos_only(a=1, b=2)
Traceback (most recent call last):
  ...
TypeError: pos_only() got some positional-only arguments passed as keyword arguments: 'a, b'
>>> def kw_only(*, key): return key
...
>>> kw_only(1)
Traceback (most recent call last):
  ...
TypeError: kw_only() takes 0 positional arguments but 1 was given
```

실전 기준은 둘이다. **인자가 2개를 넘고 불리언·숫자가 섞이면 `*` 를 쓴다** — `resize(img, 800, 600, True)` 는 읽을 수 없지만 `resize(img, *, width, height, keep_ratio)` 는 호출부가 스스로를 설명한다. **이름에 의미가 없는 자리는 `/` 로 자른다** — `def dist(p1, p2, /)` 에서 `p1` 이 계약의 일부일 이유가 없다.

::: hist / 는 왜 3.8에 와서야 생겼나
`/` 이전에도 **위치 전용 인자는 존재했다.** 단지 C로 짠 내장 함수만 쓸 수 있었다. `len(obj=[1,2])` 는 `TypeError` 다 — `len` 의 매개변수엔 이름이 없다. 순수 파이썬으로는 이걸 흉내 낼 수 없었고, 그래서 **C 구현을 파이썬으로 재작성하면 API가 미묘하게 넓어지는** 문제가 있었다.

PEP 570이 이 비대칭을 없앴다. 부수 효과가 더 크다: `/` 를 쓰면 **매개변수 이름이 공개 API에서 빠진다.** 나중에 이름을 바꿔도 아무도 안 깨지고, `**kwargs` 와 충돌할 일도 없다.

```python
def update(self, /, **fields):      # 'self' 라는 키를 받아도 안전하다
    self.data.update(fields)
```

`/` 가 없으면 `update(self=..., name=...)` 에서 `self` 가 두 번 바인딩돼 `TypeError` 다. 표준 라이브러리가 `dict.update` 에서 실제로 이 문제를 겪었다.
:::

### `*args` 와 `**kwargs`

규칙 둘뿐이다. **`args` 는 항상 `tuple`, `kwargs` 는 항상 새로 만들어진 `dict`.** 안 넘겨도 `None` 이 아니라 빈 것이 온다.

"새로 만들어진"이 중요하다. 호출자의 딕셔너리를 그대로 넘겨주는 게 아니다.

```pyrepl
>>> d = {"z": 1, "a": 2}
>>> def g(**kw):
...     kw["injected"] = True
...     return kw
...
>>> g(**d)
{'z': 1, 'a': 2, 'injected': True}
>>> d
{'z': 1, 'a': 2}
>>> def ident(**kw): return kw
...
>>> ident(**d) is d
False
```

`**` 언패킹은 **얕은 복사**를 만든다. 함수 안에서 `kwargs` 를 고쳐도 호출자는 안전하다. 반대로 말하면 **호출할 때마다 dict 하나가 새로 할당된다.** 그리고 그 순서는 **호출부에 쓴 순서** 그대로다 (PEP 468) — dict가 순서를 유지하게 된 것([1.6 dict](#/dict))과 같은 흐름이다.

::: perf 호출 형태별 실제 비용
같은 함수를 형태만 바꿔 100만 번 부른 시간이다. 아래는 데코레이터 표준형인 `def wrapper(*args, **kwargs): return f(*args, **kwargs)` 까지 포함한다.

| 호출 형태 | 100만 회 (초) | 배수 |
| --- | --- | --- |
| `f3(1, 2, 3)` | 0.0338 | 1.00 |
| `f3(*t)` | 0.0394 | 1.17 |
| `fstar(1, 2, 3)` — `*args` 수집 | 0.0593 | 1.75 |
| `f3(a=1, b=2, c=3)` | 0.0430 | 1.27 |
| `f3(**d)` | 0.0945 | 2.79 |
| `fkw(a=1, b=2, c=3)` — `**kwargs` 수집 | 0.1396 | 4.13 |

| 래퍼 한 겹 | 100만 회 (초) | 원본 대비 |
| --- | --- | --- |
| `target(1, 2, 3)` — 직접 호출 | 0.0341 | 1.00 |
| `wrapper_fixed(1, 2, 3)` — 시그니처 고정 래퍼 | 0.0478 | 1.40 |
| `wrapper(1, 2, 3)` — `*args` 래퍼 | 0.0787 | 2.31 |
| `wrapper(a=1, b=2, c=3)` — `*args` 래퍼, 키워드 호출 | 0.1419 | 4.16 |

(Python 3.14.5 / Windows, `timeit.repeat(..., number=1_000_000, repeat=5)` 의 최솟값. 절대값은 기기마다 다르고, **`f3(**d)` 와 `fkw(...)` 의 순서도 실행할 때마다 뒤집힐 수 있다** — 아래에서 설명한다.)

**`*` 는 싸고 `**` 는 비싸다.** 위치 인자는 값을 스택에 그냥 쌓지만, `**` 는 dict를 만들고 키를 해싱하고 매개변수와 매칭하고 남은 걸 또 dict에 담는다. 다만 표에서 보듯 **`fkw(**kwargs)` 로 모으는 쪽이 `f3(**d)` 로 풀어 넘기는 쪽보다 오히려 더 비쌌다** — `**kwargs` 수집은 호출부의 이름=값 쌍을 콜리 프레임 안에서 **새 dict에 하나씩 채워 넣어야** 하는 반면, `f3(**d)` 는 이미 만들어진 `d` 를 복사한 뒤 `f3` 의 고정된 매개변수(`a, b, c`) 자리에 바로 꽂으면 끝이라 상대적으로 싸다. 이 둘의 순서는 dict 크기·CPython 버전·심지어 같은 환경에서의 재실행에 따라 뒤집힐 수 있으니 **"항상 이쪽이 더 빠르다"고 외우지 말고, 필요하면 그때그때 재라.** 절대적으로 안정적인 결론은 하나뿐이다 — **위치 인자 < `*` 언패킹/수집 < `**` 언패킹/수집**, 이 큰 계층 순서는 흔들리지 않는다. 그리고 래퍼에서는 **한 겹 씌우는 비용(0.0137초)보다 범용 시그니처로 받았다 되넘기는 비용(0.0309초)이 두 배 이상 크다.** 데코레이터를 쌓으면 곱해진다. ([1.11 데코레이터](#/decorators))
:::

## 기본값은 함수의 속성이다

첫 번째 수수께끼 차례다.

**기본값 표현식은 `def` 문이 실행될 때 딱 한 번 평가된다.** 호출할 때가 아니다. 결과 객체는 `__defaults__` / `__kwdefaults__` 에 저장되고, 함수가 사는 동안 계속 산다.

```pyrepl
>>> def probe(x=print("[여기가 def 시점]")): return x
[여기가 def 시점]
>>> probe.__defaults__
(None,)
```

`def` 를 치자마자 `print` 가 실행됐다. `probe` 를 부른 적도 없는데. 그리고 `print` 의 반환값 `None` 이 기본값으로 박혔다.

두 속성은 구역별로 갈린다. `/` 앞뒤의 기본값은 `__defaults__` 라는 **튜플**에 뒤에서부터 채워지고, 키워드 전용 인자의 기본값은 `__kwdefaults__` 라는 **딕셔너리**에 들어간다.

```pyrepl
>>> def f(a, b, /, c, d, *args, e, f=10, **kwargs): pass
...
>>> f.__defaults__
>>> f.__kwdefaults__
{'f': 10}
```

위 함수는 위치 인자에 기본값이 없어서 `__defaults__` 가 아예 `None` 이다. 이 슬롯들은 **쓰기도 된다** — `greet.__defaults__ = ("python",)` 하면 기본값이 갈아 끼워진다. 실무에서 직접 쓸 일은 드물지만, 이 사실이 알려 주는 게 중요하다. 기본값은 "매번 새로 계산되는 마법"이 아니라 **함수 객체에 붙어 있는 평범한 데이터**다.

::: danger 가변 기본값 — 파이썬 최악의 함정
```python
def add_item(item, bucket=[]):     # ❌
    bucket.append(item)
    return bucket
```

```pyrepl
>>> add_item("사과")
['사과']
>>> add_item("배")
['사과', '배']
>>> add_item("포도")
['사과', '배', '포도']
```

리스트가 **한 개**다. `def` 시점에 만들어진 그 하나가 `__defaults__` 안에서 영원히 산다. 들여다보면 명백하다.

```pyrepl
>>> add_item.__defaults__
(['사과', '배', '포도'],)
>>> add_item.__defaults__[0] is add_item("귤")
True
```

**기본값을 안 넘긴 모든 호출이 같은 객체를 공유한다.** `set`, `dict`, 사용자 정의 인스턴스도 전부 마찬가지다.

```python
def add_item(item, bucket=None):    # ✅
    if bucket is None:
        bucket = []                 # 호출할 때마다 새로 만든다
    bucket.append(item)
    return bucket
```

ruff의 `B006` 이 잡는다. 반드시 켜라. ([0.4 도구](#/tooling))
:::

::: warn None 이 정당한 값일 때는 센티넬을 쓴다
`None` 관용구엔 구멍이 있다. **`None` 자체가 의미 있는 값**이면 "안 넘긴 것"과 "`None` 을 넘긴 것"을 구별할 수 없다.

```python title="센티넬 패턴"
class _Missing:
    def __repr__(self):
        return "<missing>"          # 도움말에 예쁘게 나오게

MISSING = _Missing()


def fetch(key, default=MISSING):
    store = {"a": 1, "b": None}     # b 의 값이 진짜 None 이다
    if key in store:
        return store[key]
    if default is MISSING:
        raise KeyError(key)         # 기본값을 안 줬다 -> 에러
    return default                  # None 을 줬다 -> None 반환
```

`__repr__` 을 정의한 이유는 이것 때문이다.

```pyrepl
>>> import inspect
>>> inspect.signature(fetch)
<Signature (key, default=<missing>)>
```

맨 `object()` 를 쓰면 `default=<object object at 0x000001...>` 이 도움말에 그대로 찍힌다. 표준 라이브러리도 같은 짓을 한다 — `dataclasses.MISSING`, `inspect.Parameter.empty`. ([2.6 dataclasses](#/dataclasses))
:::

::: hist 왜 호출 시점에 평가하지 않나
"기본값을 호출할 때마다 평가하면 되잖아"는 자연스러운 반문이다. 실제로 그러는 언어도 있다(Ruby, JavaScript). 파이썬이 안 하는 이유는 둘이다.

1. **속도.** 매 호출마다 임의의 표현식을 실행하게 된다. 지금은 튜플에서 슬롯으로 복사하는 것뿐이다.
2. **평가 문맥이 애매해진다.** `def f(x=y)` 를 호출 시점에 평가한다면 `y` 는 **어느 스코프의 `y`** 인가? 정의된 곳인가 호출한 곳인가. 정의 시점 평가는 이 질문을 아예 없앤다.

대신 함정 하나를 받아들였다. 이 트레이드오프를 알고 나면 `x=None` 관용구가 우회로가 아니라 **명시적인 "호출 시점 평가" 선언**으로 보인다.
:::

::: tip 가변 기본값을 일부러 쓰는 유일한 자리
"함수가 죽을 때까지 사는 상태"가 **정확히 원하는 것**일 때가 있다. 메모이제이션이다.

```python title="기본값 캐시 — 알고 쓰면 관용구다"
def fib(n, _cache={0: 0, 1: 1}):
    if n not in _cache:
        _cache[n] = fib(n - 1) + fib(n - 2)
    return _cache[n]
```

```pyrepl
>>> fib(100)
354224848179261915075
>>> len(fib.__defaults__[0])
101
```

전역 딕셔너리보다 빠르고(지역 슬롯이니까) `functools.lru_cache` 보다 가볍다. 밑줄 이름(`_cache`)이 "인자가 아니라 내부 상태"라는 신호다. 다만 **팀 코드에서는 `lru_cache` 를 써라** — 읽는 사람이 함정으로 오해한다. ([3.1 functools](#/functools))
:::

## LEGB: 이름은 언제 결정되는가

세 번째 수수께끼 차례다.

```pyrepl
>>> n = 1
>>> def g():
...     print(n)
...     n = 2
...
>>> g()
Traceback (most recent call last):
  ...
UnboundLocalError: cannot access local variable 'n' where it is not associated with a value
```

전역 `n = 1` 이 멀쩡히 있는데 왜 못 찾나. 답: **파이썬은 이름의 스코프를 런타임이 아니라 컴파일 타임에 결정한다.**

컴파일러는 함수 본문을 훑어서 **대입이 한 번이라도 있는 이름을 전부 지역 변수로 등록한다.** 대입이 어디에 있든 상관없다. `n = 2` 가 함수 안 어딘가에 있으므로 `n` 은 지역 슬롯이고, `print(n)` 은 그 빈 슬롯을 읽는다. `UnboundLocalError` 는 `NameError` 의 자식인데, 둘의 차이가 정확히 이것이다 — `NameError` 는 **어느 스코프에도 이름이 없다**, `UnboundLocalError` 는 **슬롯은 있는데 아직 안 채워졌다**.

이름 해석 순서는 네 단계, 흔히 **LEGB** 라 부른다.

```text nolines
   L  Local        this function's own slots
   E  Enclosing    enclosing function's cells       <- def 로 감싼 것만
   G  Global       the module's __dict__
   B  Builtins     the builtins module
```

B 단계도 실재한다. 전역에 `len` 을 정의하면 내장 `len` 이 가려진다.

```pyrepl
>>> def f(): return len([1, 2, 3])
...
>>> f()
3
>>> len = lambda x: 999
>>> f()
999
>>> del len
>>> f()
3
```

::: deep LEGB 는 네 개의 단계가 아니라 세 종류의 바이트코드다
"LEGB 순서로 찾는다"는 흔한 설명은 **틀렸다.** 런타임에 네 군데를 순서대로 뒤지는 게 아니다. 컴파일러가 미리 결론을 내고 **이름마다 서로 다른 명령어**를 박아 둔다.

```python title="세 종류의 이름"
g = 1
def f():
    loc = 2
    def inner():
        return loc + g + cellv
    cellv = 3
    return inner
```

```text nolines
Disassembly of <code object inner>:
  --           COPY_FREE_VARS           2
   5           RESUME                   0
   6           LOAD_DEREF               1 (loc)     <- E: cell 을 통해 읽는다
               LOAD_GLOBAL              0 (g)       <- G/B: 딕셔너리 조회
               BINARY_OP                0 (+)
               LOAD_DEREF               0 (cellv)   <- E
               BINARY_OP                0 (+)
               RETURN_VALUE
```

- **L** → `LOAD_FAST` / `LOAD_FAST_BORROW` — 배열 인덱싱. 딕셔너리 조회가 아니다.
- **E** → `LOAD_DEREF` — cell 안의 포인터를 한 번 더 따라간다.
- **G, B** → `LOAD_GLOBAL` — **여기서만 진짜 탐색이 일어난다.** 모듈 `__dict__` 를 보고 없으면 builtins `__dict__` 를 본다. G와 B는 별개 단계가 아니라 **한 명령어의 두 시도**다.

`del len` 하면 `f()` 가 다시 `3` 을 반환하는 이유도 이것이다. 컴파일 시점엔 "`len` 은 지역도 자유 변수도 아니다"까지만 결론 냈고, 실제로 무엇을 가리키는지는 매번 런타임에 정해진다.
:::

::: perf 이름 종류별 조회 비용
루프 안에서 이름만 10번씩 읽는 함수 셋을 2천만 번 조회했다.

| 이름 종류 | 명령어 | 2천만 회 (초) | 배수 |
| --- | --- | --- | --- |
| 지역 | `LOAD_FAST_BORROW` | 0.0963 | 1.00 |
| 자유 변수(클로저) | `LOAD_DEREF` | 0.1166 | 1.21 |
| 전역 | `LOAD_GLOBAL` | 0.1369 | 1.42 |

(Python 3.14.5 / Windows, `timeit.repeat` 최솟값. 세 함수 모두 같은 방식으로 — 10번씩 읽어 반환 — 호출 오버헤드를 맞췄다.)

조회 하나에 4.8ns vs 5.8ns vs 6.8ns 수준이다. **지역이 항상 가장 빠르다는 것만은 확실하다.** 그런데 전역과 자유 변수 중 어느 쪽이 더 빠른지, 그리고 그 격차가 몇 %인지는 이 책이 자신 있게 못 박을 수 있는 숫자가 아니다 — 벤치마크를 어떻게 짜느냐(직접 호출인지 `timeit` 문자열 방식인지, dict 크기가 얼마인지)에 따라 순서와 격차가 흔들렸고, 어떤 구성에서는 둘이 거의 같게, 다른 구성에서는 전역이 자유 변수보다 뚜렷이 느리게 나왔다. 확실한 건 **셋 다 같은 자릿수(ns 단위)에 몰려 있다는 것**뿐이다. 3.11의 특수화 인터프리터가 `LOAD_GLOBAL` 과 `LOAD_DEREF` 양쪽에 인라인 캐시를 붙이면서 "전역·자유 변수 조회는 해시 테이블/cell을 뒤지니 지역보다 훨씬 느리다"는 옛 상식이 반쯤 무너졌다. 캐시가 히트하면 딕셔너리 버전 태그만 확인하고 바로 값을 꺼낸다. **정확한 순서와 배수가 필요하면 네 환경에서 직접 재라** — 이 절이 하는 것처럼. ([3.7 바이트코드](#/bytecode))
:::

### global 과 nonlocal

컴파일러가 스코프를 미리 정한다면, 그 결정을 뒤집는 문법이 필요하다. **둘 다 값을 넘기는 게 아니라 컴파일러에게 내리는 지시다.**

| | 대상 | 없으면 |
| --- | --- | --- |
| `global x` | 모듈 스코프의 `x` | 대입 시 **새로 만든다** |
| `nonlocal x` | 가장 가까운 감싸는 **함수** 스코프의 `x` | `SyntaxError` (컴파일 실패) |

`nonlocal` 은 **바인딩이 이미 존재해야 한다.**

```pyrepl
>>> def f():
...     def g():
...         nonlocal q
...         q = 1
...
Traceback (most recent call last):
  ...
SyntaxError: no binding for nonlocal 'q' found
```

::: warn global 을 쓰기 전에 멈춰라
`global` 이 필요하다고 느끼는 순간의 90%는 설계 문제다. 함수가 모듈 상태를 쓰기 시작하면 **테스트 순서에 결과가 의존**하고, 그 시점부터 디버깅이 지옥이 된다. 대안은 셋이다.

1. **값을 반환하고 호출자가 대입한다.** 가장 좋다.
2. **클로저로 상태를 가둔다.** 아래에서 본다.
3. **클래스 인스턴스에 담는다.** 상태가 여러 개면 이쪽. ([1.12 클래스](#/classes))

읽기만 할 거면 선언 자체가 불필요하다. **읽기는 선언 없이 된다.** `global` 은 오직 "대입을 모듈 스코프에 하겠다"는 뜻이다.
:::

### 클래스 몸통은 LEGB의 E가 아니다

이건 실제로 사람을 잡는다.

```pyrepl
>>> val = "module"
>>> class C:
...     val = "class"
...     def m(self):
...         return val
...
>>> C().m()
'module'
```

`val = "class"` 가 바로 위에 있는데 메서드는 그걸 못 본다. **클래스 몸통은 스코프이긴 하지만 감싸는 스코프로 참여하지 않는다.** LEGB의 E는 **`def` 로 감싼 함수 스코프만** 가리킨다. 클래스 변수를 보려면 `self.val` 이나 `C.val` 로 **속성 조회**를 해야 한다.

::: deep locals() 는 3.13부터 스냅샷이다 (PEP 667)
함수 안에서 `locals()` 를 부르면 예전에는 "구현 정의 동작"이었다. 어떤 경우엔 반영되고 어떤 경우엔 안 되는 회색 지대였다. PEP 667이 못 박았다.

```pyrepl
>>> def g():
...     a = 1
...     loc = locals()
...     a = 2
...     print(loc["a"], a)
...     loc["a"] = 99
...     print(a)
...
>>> g()
1 2
2
```

**함수 스코프의 `locals()` 는 독립적인 스냅샷 딕셔너리다.** 이후 변화가 반영되지 않고, 딕셔너리를 고쳐도 실제 변수는 안 바뀐다. 당연하다 — 지역 변수는 딕셔너리가 아니라 배열 슬롯이니까. 그 슬롯을 dict로 **복사해 주는** 게 `locals()` 다.

모듈과 클래스 몸통은 다르다. 거기서는 진짜 이름 공간이 dict라서 `locals()` 가 그 dict 자체를 반환한다 — 모듈 최상위에서 `locals() is globals()` 는 `True` 다. `exec`/`eval` 에 `locals()` 를 넘기던 코드가 3.13에서 조용히 동작을 바꾼 경우가 있다.
:::

## 클로저: 함수가 변수를 데리고 다닌다

함수가 끝나면 지역 변수는 사라진다. 그런데 안쪽 함수가 그걸 참조하고 있으면?

```pyrepl
>>> def make_counter():
...     count = 0
...     def inc():
...         nonlocal count
...         count += 1
...         return count
...     return inc
...
>>> c = make_counter()
>>> c(); c(); c()
1
2
3
```

`make_counter` 는 세 번 전에 이미 끝났다. `count` 는 어디 사는가.

```pyrepl
>>> c.__closure__
(<cell at 0x000001C19B07EBF0: int object at 0x00007FFD64E3C4B8>,)
>>> c.__closure__[0].cell_contents
3
>>> c.__code__.co_freevars
('count',)
>>> make_counter.__code__.co_cellvars
('count',)
```

**`cell` 이라는 객체 안에 산다.** cell은 값 하나를 담는 상자다. 안쪽 함수와 바깥 함수가 **같은 cell을 공유**한다. 바깥 함수가 죽어도 cell은 안쪽 함수가 참조하니 안 죽는다.

```text nolines
   make_counter() frame              inc  (function object)
   +---------------------+           +------------------------+
   |  slot 'count'  ---+ |           |  __code__   -> code    |
   +-------------------|-+           |  __closure__ -> ( * )  |
                       |                               |
                       v                               v
                    +--------------------------------------+
                    |  cell object      cell_contents: 3   |
                    +--------------------------------------+
```

`make_counter` 를 부를 때마다 새 프레임 → 새 cell → 새 함수 객체다. 그래서 카운터 두 개는 서로 간섭하지 않는다(`c.__closure__[0] is d.__closure__[0]` 은 `False`). 클래스 인스턴스와 정확히 같은 격리 수준이다.

::: deep 바이트코드로 본 cell의 탄생, 그리고 빈 cell
컴파일러는 "안쪽 함수가 참조하는 바깥 지역 변수"를 미리 안다. 그래서 그 변수를 **처음부터 cell로 만든다.**

```text nolines
Disassembly of f:
  --           MAKE_CELL                1 (cellv)   <- 프레임 진입 전에 cell 생성
               MAKE_CELL                2 (loc)
   3           RESUME                   0
   4           LOAD_SMALL_INT           2
               STORE_DEREF              2 (loc)     <- 슬롯이 아니라 cell 에 쓴다
   5           LOAD_FAST_BORROW         1 (cellv)
               LOAD_FAST_BORROW         2 (loc)
               BUILD_TUPLE              2           <- cell 들을 튜플로 묶고
               LOAD_CONST               1 (<code object inner>)
               MAKE_FUNCTION
               SET_FUNCTION_ATTRIBUTE   8 (closure) <- __closure__ 에 붙인다
               STORE_FAST               0 (inner)
```

읽어야 할 것 셋.

1. **`MAKE_CELL` 이 함수 본문보다 먼저 실행된다.** 줄 번호가 `--` 인 게 그 뜻이다. cell은 프레임 셋업의 일부다.
2. `loc` 은 `f` 자신의 지역 변수인데도 `STORE_FAST` 가 아니라 **`STORE_DEREF`** 를 쓴다. 누가 캡처하는 순간 그 변수는 슬롯이 아니라 cell이 된다. **캡처된 변수는 캡처한 쪽에서도 조금 느려진다.**
3. cell이 만들어지는 시점과 **채워지는** 시점은 다르다. 그래서 비어 있을 수 있다.

```pyrepl
>>> def h(flag):
...     if flag:
...         v = 1
...     def g(): return v
...     return g
...
>>> gg = h(False)
>>> gg.__closure__
(<cell at 0x000001BF38B6E3E0: empty>,)
>>> gg()
Traceback (most recent call last):
  ...
NameError: cannot access free variable 'v' where it is not associated with a value in enclosing scope
```

`repr` 이 대놓고 `empty` 라 말한다. `UnboundLocalError` 의 자유 변수 버전이다. 반대로 **정의 뒤에 채워도 된다** — 클로저는 정의 시점의 값을 복사하는 게 아니라 cell을 가리킬 뿐이니까. 상호 재귀 함수를 정의할 수 있는 것도 이 덕분이다.

**cell은 값이 아니라 변수를 공유한다.** 이 한 문장이 다음 절의 함정 전체를 설명한다.
:::

::: warn 클로저는 캡처한 객체를 살려 둔다
cell은 강한 참조다. **함수 하나가 거대한 객체를 통째로 붙잡고 있을 수 있다.**

```python title="수명 관찰"
class Big:
    def __del__(self):
        print("Big 소멸")


def leak():
    b = Big()
    def get():
        return b            # b 를 캡처한다
    return get


h = leak()
print("살아 있음:", h() is not None)
del h
print("--- del h 이후 ---")
```

```text nolines
살아 있음: True
Big 소멸
--- del h 이후 ---
```

`leak()` 이 끝났는데도 `Big` 은 안 죽는다. `h` 를 지워야 죽는다. 콜백이나 이벤트 핸들러를 클로저로 만들어 어딘가에 등록해 두면 **그 클로저가 캡처한 모든 것이 등록이 풀릴 때까지 산다.** 텐서를 캡처한 콜백 하나가 GPU 메모리를 못 놓아 주는 사고가 실제로 난다. ([5.2 메모리 모델](#/memory))

`return b` 를 `return 1` 로 바꾸면 `Big` 은 `leak()` 이 끝나는 즉시 죽는다. 컴파일러는 캡처하지 않는 변수를 cell로 만들지 않는다.
:::

## 늦은 바인딩: 두 번째 수수께끼

이제 무장이 끝났다.

```pyrepl
>>> fs = [lambda: i for i in range(3)]
>>> [g() for g in fs]
[2, 2, 2]
```

이유는 방금 본 문장 그대로다. **cell은 값이 아니라 변수를 공유한다.**

```pyrepl
>>> fs[0].__closure__[0] is fs[1].__closure__[0]
True
>>> fs[0].__closure__[0].cell_contents
2
```

**세 람다가 같은 cell 하나를 본다.** 람다는 "`i` 의 값"을 저장한 게 아니라 "`i` 라는 변수"를 가리킨다. 그 변수는 루프가 끝난 뒤 `2` 이고, 호출할 때 비로소 읽으니 전부 `2` 다. 이걸 **늦은 바인딩**(late binding)이라 한다.

이건 버그가 아니라 **일관성**이다. 파이썬 함수 안의 이름은 전부 호출 시점에 해석된다. 전역도 그렇다 — `def f(): return G` 를 정의한 뒤 `G` 를 바꾸면 `f()` 도 따라 바뀌고, 아무도 여기에 놀라지 않는다. 자유 변수도 똑같이 동작할 뿐이다. 만약 클로저만 정의 시점 값을 복사한다면 방금 본 "정의 뒤에 cell 채우기"도 상호 재귀도 불가능해진다.

고치는 법은 셋인데 원리는 **"루프 변수가 아닌 새 바인딩을 만든다"** 하나다.

```python title="세 가지 해법"
# ① 기본값 — 정의 시점에 평가된다는 성질을 이용한다
fs = [lambda i=i: i for i in range(3)]

# ② 팩토리 함수 — 호출마다 새 프레임, 새 cell
def make(i):
    return lambda: i
fs = [make(i) for i in range(3)]

# ③ functools.partial — 인자를 미리 묶는다
from functools import partial
fs = [partial(lambda i: i, i) for i in range(3)]
```

```pyrepl
>>> [g() for g in fs]
[0, 1, 2]
```

**①이 가장 짧고 흔하다.** 절 앞부분에서 "기본값은 `def` 시점에 한 번 평가된다"가 함정이었는데, 여기서는 그게 **정확히 필요한 도구**가 된다. 같은 성질의 양면이다.

::: danger for 루프에서는 메커니즘이 아예 다르다
컴프리헨션이 아니라 `for` 루프로 만들면 증상은 같지만 원인이 다르다.

```pyrepl
>>> fs = []
>>> for i in range(3):
...     fs.append(lambda: i)
...
>>> [g() for g in fs]
[2, 2, 2]
>>> fs[0].__closure__
>>> del i
>>> [g() for g in fs]
Traceback (most recent call last):
  ...
NameError: name 'i' is not defined
```

`__closure__` 가 아예 `None` 이다. 모듈 최상위의 `for` 는 스코프를 만들지 않으므로 `i` 는 **전역**이고, 람다들은 cell이 아니라 `LOAD_GLOBAL i` 를 한다. `del i` 하면 전부 `NameError` 로 죽는다.

증상이 같으니 고치는 법도 같다(`lambda i=i:`). 하지만 **`for` 루프 변수는 루프가 끝나도 살아 있다**는 별개의 함정이 여기 붙어 있다. 컴프리헨션은 자체 스코프를 가져서 이게 없다.
:::

::: deep 3.12부터 컴프리헨션은 함수가 아니다 (PEP 709)
"컴프리헨션은 자체 스코프를 가진다"는 3.11까지 **문자 그대로 숨겨진 함수를 만들어 호출한다**는 뜻이었다. 3.12의 PEP 709가 이걸 **인라인**했다. 코드 객체도, 프레임도, 함수 호출도 사라졌다.

```pyrepl
>>> def f():
...     n = 3
...     return [i * n for i in range(3)]
...
>>> f.__code__.co_cellvars
()
>>> [type(c).__name__ for c in f.__code__.co_consts]
['int']
```

3.11이었다면 `co_cellvars` 에 `('n',)` 이 있고 `co_consts` 에 `<code object <listcomp>>` 가 들어 있었다. 지금은 둘 다 없다. **`n` 은 cell이 될 필요가 없다** — 같은 프레임 안이니 그냥 지역 슬롯을 읽는다.

그런데 **스코프 격리는 그대로다.** 루프 변수는 여전히 밖으로 안 샌다. 컴파일러가 이름을 숨겨진 지역 슬롯으로 바꿔치기해 격리만 흉내 낸다. 관측 가능한 의미는 유지하고 비용만 제거한 것 — CPython이 요즘 계속 하는 일이다. ([1.9 컴프리헨션](#/comprehensions))
:::

## 함수는 일급 객체다

여기까지 온 사람에게는 이제 당연할 것이다. `__defaults__` 를 고쳐 쓰고 `__closure__` 를 들여다봤다면 **함수가 평범한 객체**라는 걸 이미 본 것이다. 아무 속성이나 붙고(`square.retries = 3` → `square.__dict__`), 자료구조에 담기고, 인자로 넘어간다.

| 속성 | 내용 |
| --- | --- |
| `__code__` | 바이트코드와 상수. **여러 함수가 공유할 수 있다** |
| `__defaults__` / `__kwdefaults__` | 기본값. `def` 시점에 평가된 객체들 |
| `__closure__` | cell 튜플. 없으면 `None` |
| `__globals__` | 정의된 모듈의 `__dict__`. **참조다, 복사가 아니다** |
| `__dict__` | 함수에 붙인 임의 속성 |
| `__name__` / `__qualname__` / `__doc__` | 메타데이터 |

`__globals__` 가 참조라는 건 이런 뜻이다.

```pyrepl
>>> def f2(): return SOMEVAR
...
>>> f2.__globals__ is globals()
True
>>> f2.__globals__["SOMEVAR"] = "injected"
>>> f2()
'injected'
```

**함수는 자기가 태어난 모듈의 이름 공간을 평생 들고 다닌다.** 다른 모듈로 옮겨 붙여도 전역 조회는 원래 모듈에서 일어난다. 모듈을 오가는 몽키패치가 예상 밖으로 동작하는 이유가 이것이다.

::: deep 메서드는 함수 + 디스크립터다
함수 객체에는 `__get__` 이 있다. 즉 **함수는 디스크립터다.** 이게 메서드의 전부다.

```pyrepl
>>> class D:
...     def m(self): return "hi"
...
>>> D.m
<function D.m at 0x00000209A9F333D0>
>>> D().m
<bound method D.m of <__main__.D object at 0x00000209A9F346E0>>
>>> d = D()
>>> d.m.__func__ is D.m
True
>>> d.m.__self__ is d
True
```

클래스에서 꺼내면 **그냥 함수**고 인스턴스에서 꺼내면 **바운드 메서드**다. 속성 조회가 디스크립터 프로토콜을 타면서 `func.__get__(obj, cls)` 를 부르고, 그게 `obj` 를 첫 인자로 묶은 얇은 래퍼를 만든다.

**`self` 는 마법이 아니다.** 그냥 첫 번째 위치 인자이고, 디스크립터가 그 자리에 인스턴스를 끼워 넣을 뿐이다. 그래서 아무 함수나 클래스에 붙이면 그 순간부터 메서드가 된다.

```pyrepl
>>> def square(x): return x * x
...
>>> class C: pass
...
>>> C.method = square
>>> C().method            # x 자리에 인스턴스가 들어간다
<bound method square of <__main__.C object at 0x...>>
```

전체 그림은 [3.3 디스크립터](#/descriptors)에서.
:::

### 그래서 클로저인가 클래스인가

상태를 가진 호출 가능 객체를 만드는 두 방법이다. **성능은 기준이 못 된다** — 100만 회 호출에 클로저 카운터 0.0242초, 일반 클래스 0.0278초, `__slots__` 클래스 0.0269초로 사실상 같다. 메모리만 클로저가 조금 작다(함수 168B + cell 튜플 56B + cell 40B = 264B).

기준은 설계다. **상태 1~2개에 동작 1개면 클로저** — 짧고 이름이 안 샌다. **상태와 동작이 여러 개면 클래스** — 클로저로 하면 딕셔너리를 캡처하는 괴물이 된다. **검사·직렬화·디버깅이 필요하면 클래스** — cell은 `pickle` 도 안 되고 `repr` 도 쓸모없다.

## 요약

- 시그니처의 다섯 구역은 코드 객체 안에 `co_posonlyargcount` / `co_argcount` / `co_kwonlyargcount` **숫자로** 박혀 있다. `/` 는 이름을 API에서 숨기고, `*` 는 호출부가 스스로를 설명하게 강제한다.
- `*` 언패킹은 싸고 `**` 는 4배 비싸다. `*args, **kwargs` 범용 래퍼는 원본 대비 **3~6배**. 데코레이터를 쌓으면 곱해진다.
- **기본값은 `def` 시점에 한 번 평가되어 `__defaults__` 에 산다.** 가변 기본값 공유는 버그가 아니라 필연이다. `None` 이나 센티넬을 써라. 늦은 바인딩 해법 `lambda i=i:` 는 **같은 성질을 뒤집어 쓴 것**이다.
- **스코프는 컴파일 타임에 결정된다.** 함수 안에 대입이 있으면 그 이름은 지역이다 — 대입이 코드 뒤쪽에 있어도. `UnboundLocalError` 가 그 증상이다.
- LEGB는 런타임 탐색이 아니라 **세 종류의 바이트코드**다. `LOAD_FAST`(L) / `LOAD_DEREF`(E) / `LOAD_GLOBAL`(G+B). 3.14에서 셋의 차이는 **40% 이내**다.
- 클로저는 **값이 아니라 cell을 공유한다.** 루프 안 `lambda` 가 전부 같은 값을 뱉는 이유이고, 콜백이 캡처한 객체가 안 죽는 이유이기도 하다.
- 함수는 `__code__` · `__defaults__` · `__closure__` · `__globals__` · `__dict__` 를 들고 다니는 **평범한 객체**다. `__get__` 이 있어서 클래스에 붙으면 메서드가 된다.

::: cote 코딩테스트에서 실제로 쓰는 것
**1) DFS 결과 누적은 `nonlocal` 이 `return` 합산보다 빠르다.**

```python
def solve(tree):
    total = 0
    def dfs(v):
        nonlocal total
        total += v
        for w in tree.get(v, ()):
            dfs(w)
    dfs(0)
    return total
```

| | 2000 회 (초) |
| --- | --- |
| `nonlocal` 누적 | 0.0915 |
| `return` 값 합산 (`sum(...)`) | 0.2155 |

**2.4배**다. 재귀가 깊을수록 중간 제너레이터·튜플 생성이 쌓인다. `global` 대신 `nonlocal` 인 게 핵심 — 전역은 함수 여러 개가 건드려 디버깅이 어렵다.

**2) 재귀 함수는 자기 이름을 전역에서 찾는다.**

```pyrepl
>>> def rec(n): return 1 if n <= 1 else n * rec(n - 1)
...
>>> r = rec
>>> del rec
>>> r(5)
Traceback (most recent call last):
  ...
NameError: name 'rec' is not defined
```

`rec` 은 자기 몸통 안에서 `LOAD_GLOBAL rec` 이다. 함수 이름을 재대입해 놓고 재귀가 깨지는 사고가 실제로 난다. 클래스 메서드 안에서 `self.method(...)` 를 빼먹으면 바로 `NameError` 인 것도 같은 이유다.

**3) 정렬 `key=` 는 그냥 일급 함수다.**

```python
data.sort(key=lambda p: (-p[1], p[0]))     # ✅ 흔한 관용구
```

`key` 는 원소마다 **한 번씩** 불린다. 안에서 무거운 계산을 하지 마라 — $n$ 번 돈다. [7.4 정렬](#/sorting)
:::

::: perf 3.14에서 죽은 두 개의 옛 관용구
파이썬 최적화 팁으로 20년간 돌아다닌 둘을 직접 재 봤다.

**① 기본값으로 전역을 지역에 묶는 트릭** — `def trick(_len=len, _str=str, _data=data):`

| | 2만 회 (초) |
| --- | --- |
| 일반 (`len`, `str` 전역 조회) | 0.0362 |
| 기본값으로 지역 바인딩 | 0.0347 |

**4%.** 코드를 흉하게 만들 값어치가 없다.

**② 메서드 호이스팅** — `push = out.append` 를 루프 밖으로 빼기

| | 5천 회 (초) |
| --- | --- |
| `out.append(x)` | 0.0752 |
| 호이스팅 | 0.0761 |

**차이 없음.** 여러 번 재보면 `-1%` 나올 때도 `+2%` 나올 때도 있다 — **잡음 수준**이지 실제 이득이 아니다. 옛날엔 `out.append` 매번 `LOAD_ATTR` 로 타입을 뒤져서 호이스팅이 그 비용을 없애 줬지만, 지금은 그 `LOAD_ATTR` 자체가 거의 공짜라 뺄 것도 없다.

둘 다 죽은 (혹은 반쯤 죽은) 이유는 같다. 3.11의 **특수화 인터프리터**가 `LOAD_GLOBAL` 과 `LOAD_ATTR` 에 인라인 캐시를 붙였다. 이제 전역 조회는 딕셔너리 버전 태그 확인 한 번, 메서드 조회는 타입 버전 확인 한 번이다. ①번(기본값 지역 바인딩)은 그래도 4%대 이득이 재현되지만, ②번(메서드 호이스팅)은 그 4%마저 인라인 캐시가 다 먹어 치워서 **이득이 통계적으로 안 보인다.**

**교훈은 "옛날 팁을 믿지 말고 재라"다.** 이 관용구들은 3.11 이전 코드베이스에서 유래했고 그 시대엔 의미가 있었다. 인터프리터가 바뀌면 최적화 지도도 바뀐다. [5.1 프로파일링](#/profiling)
:::

::: quiz 연습문제
1. 다음의 출력을 **예측한 뒤** 실행해 확인하라. 왜 이렇게 되는지 `__defaults__` 와 `__kwdefaults__` 로 설명하라.

   ```python
   def f(a, b=[], *, c=[]):
       b.append(a)
       c.append(a)
       return b, c

   print(f(1))
   print(f(2))
   print(f(3, c=[]))
   print(f(4))
   ```

2. 아래 두 함수의 `__closure__` 는 각각 무엇인가? 예측하고 확인하라. 다르다면 왜인가?

   ```python
   def a():
       x = 1
       def inner(): return x
       return inner

   def b():
       x = 1
       def inner(): return 1
       return inner
   ```

3. 다음이 왜 `SyntaxError` 가 아니라 `UnboundLocalError` 인지 설명하라. 그리고 `if False:` 두 줄을 지우면 어떻게 되는가?

   ```python
   x = 10
   def f():
       print(x)
       if False:
           x = 20
   f()
   ```

4. 다음 `handlers` 를 고쳐 각 버튼이 자기 이름을 출력하게 하라. **세 가지 방법**으로 각각 고치고, 각각의 `__closure__` 를 비교하라.

   ```python
   handlers = {}
   for name in ["save", "load", "quit"]:
       handlers[name] = lambda: print(f"clicked {name}")
   handlers["save"]()      # clicked quit
   ```

5. **깊이 생각해 볼 문제.** 다음에서 `Big` 은 언제 해제되는가? `register` 가 끝났는데도 안 죽는 이유를 클로저와 캐시 양쪽으로 설명하고, 고쳐라.

   ```python
   import functools

   class Big:
       def __init__(self, n): self.data = [0] * n
       def __del__(self): print("Big 소멸")

   def register(callbacks):
       big = Big(1_000_000)
       @functools.lru_cache(maxsize=None)
       def compute(k):
           return len(big.data) + k
       callbacks.append(compute)

   cbs = []
   register(cbs)
   print("register 끝났는데?")
   ```
:::

**다음 절**: [1.11 데코레이터](#/decorators) — 방금 배운 클로저와 일급 함수가 합쳐지면 무엇이 되는가. `@` 는 문법 설탕 이상이 아니라는 것부터 시작한다.
