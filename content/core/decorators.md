# 1.11 데코레이터

::: lead
데코레이터는 파이썬에서 가장 많이 쓰이면서 가장 오해받는 문법이다. `@app.route`, `@pytest.fixture`, `@torch.no_grad`, `@dataclass` — 당신이 앞으로 쓸 모든 프레임워크가 데코레이터로 API를 만든다. 그런데 데코레이터에는 새로운 기능이 하나도 없다. **함수가 일급 객체이고 클로저가 있으면 자동으로 따라 나오는 결과**일 뿐이다. 이 절의 목표는 `@` 를 마법이 아니라 **`f = deco(f)` 한 줄**로 읽는 눈을 만드는 것이다. 그러면 프레임워크 소스가 갑자기 읽히기 시작한다.
:::

## 문제부터

함수 몇 개의 실행 시간을 재고 싶다.

```python title="처음엔 이렇게 시작한다"
import time


def load_map(path):
    start = time.perf_counter()
    result = _real_load(path)
    print(f"load_map: {time.perf_counter() - start:.3f}s")
    return result


def plan_path(grid, goal):
    start = time.perf_counter()
    result = _real_plan(grid, goal)
    print(f"plan_path: {time.perf_counter() - start:.3f}s")
    return result
```

함수가 스무 개면 같은 네 줄을 스무 번 쓴다. 로깅을 붙이고 싶어지면 스무 군데를 고친다. 나중에 타이밍을 끄고 싶으면 또 스무 군데다.

문제의 정체는 이렇다. **"시간을 재는 일"은 `load_map` 이 하는 일이 아니다.** 함수 본체와 아무 관계 없는 관심사가 함수 본체에 섞여 있다. 이걸 떼어내려면, "함수를 받아서 시간 재기가 덧씌워진 함수를 돌려주는 것"이 필요하다.

파이썬에서는 그게 가능하다. **함수도 객체이기 때문이다.** ([1.1 객체, 이름, 참조](#/objects-names))

```python title="함수를 받아서 함수를 돌려준다"
def timed(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__}: {time.perf_counter() - start:.3f}s")
        return result
    return wrapper


def load_map(path):
    return _real_load(path)


load_map = timed(load_map)          # ← 이게 전부다
```

마지막 줄이 데코레이터의 전부다. 그리고 `@` 는 저 줄을 **함수 정의 위로 옮겨 적는 문법**이다.

```python
@timed
def load_map(path):
    return _real_load(path)
```

::: hist 왜 @ 기호가 생겼나
데코레이터 자체는 파이썬 2.2(2001)부터 `staticmethod`, `classmethod` 형태로 이미 있었다. 다만 문법이 없어서 `get_count = classmethod(get_count)` 처럼 함수 본체 **아래**에 적어야 했다. 함수가 길면 독자는 그 사실을 모른 채 본체를 다 읽는다.

PEP 318(2003)이 `@` 를 도입해 **선언을 이름 앞으로** 끌어올렸다. 기호를 고르는 데만 1년 넘게 논쟁이 붙었고, `@` 가 이긴 건 자바 어노테이션과의 시각적 유사성 때문이다.

PEP 614(3.9)에서 문법 제약이 풀려, 이제 `@` 뒤에는 **아무 표현식이나** 올 수 있다.

```pyrepl
>>> decos = {"log": lambda f: f}
>>> @decos["log"]                    # 3.8까지는 SyntaxError
... def g(): return 1
...
>>> g()
1
```
:::

## `@` 는 문법 설탕이다 — 다만 완전히 같지는 않다

"`@deco` 는 `f = deco(f)` 와 같다"는 설명은 95% 맞다. 나머지 5%를 바이트코드로 확인해 보자. ([3.7 바이트코드](#/bytecode))

```pyrepl
>>> import dis
>>> dis.dis(compile("@deco\ndef f():\n    pass\n", "<x>", "exec"))
  0           RESUME                   0
  1           LOAD_NAME                0 (deco)
  2           LOAD_CONST               0 (<code object f ...>)
              MAKE_FUNCTION
  1           CALL                     0
  2           STORE_NAME               1 (f)
```

이번엔 손으로 쓴 버전이다.

```pyrepl
>>> dis.dis(compile("def f():\n    pass\nf = deco(f)\n", "<x>", "exec"))
  0           RESUME                   0
  1           LOAD_CONST               0 (<code object f ...>)
              MAKE_FUNCTION
              STORE_NAME               0 (f)
  3           LOAD_NAME                1 (deco)
              PUSH_NULL
              LOAD_NAME                0 (f)
              CALL                     1
              STORE_NAME               0 (f)
```

차이가 보인다. 손으로 쓴 쪽에는 `STORE_NAME f` 가 **두 번** 나온다. 즉 이름 `f` 가 **잠깐 원본 함수에 묶였다가** 다시 덮어쓰인다. `@` 를 쓰면 원본은 스택 위에만 잠깐 존재하고 이름에 묶이는 일이 없다.

::: deep CALL 0 인데 왜 인자가 전달되나
데코레이터 형태에서 `CALL 0` — 인자 개수가 0이다. 그런데 `deco` 는 함수를 받는다. 모순처럼 보인다.

3.11 이후 CPython의 호출 규약은 스택에 `[callable, self_or_NULL, arg1, ...]` 를 쌓는다. `CALL n` 의 `n` 은 **명시적 인자 개수**이고, `self` 자리는 세지 않는다. 메서드 호출 `obj.m(x)` 를 `LOAD_METHOD` 로 최적화하기 위한 구조다.

데코레이터 형태에서 컴파일러는 `deco` 를 callable 자리에, 방금 만든 함수를 **`self` 자리**에 넣는다. 그래서 `CALL 0` 이다. 손으로 쓴 쪽은 `PUSH_NULL` 로 `self` 자리를 비우고 함수를 진짜 인자로 넘기므로 `CALL 1` 이다. **결과는 똑같고, 데코레이터 쪽이 `PUSH_NULL` 하나만큼 짧다.**
:::

이 5%가 실제로 문제가 되는 경우는 거의 없다. 하지만 **읽을 때는 항상 `f = deco(f)` 로 치환해서 읽어라.** 데코레이터에 관한 거의 모든 혼란이 이 치환 하나로 풀린다.

::: warn 데코레이터는 import 시점에 실행된다
`@deco` 의 `deco(f)` 호출은 **함수를 호출할 때가 아니라 함수를 정의할 때** 일어난다. 즉 모듈을 import하는 순간이다.

```python
def deco(f):
    print("데코레이터 본체 실행")      # import 시점
    def wrapper(*a, **k):
        print("래퍼 실행")              # 호출 시점
        return f(*a, **k)
    return wrapper
```

그래서 데코레이터 본체에서 무거운 일(DB 연결, 모델 로딩, 파일 읽기)을 하면 **import가 느려진다.** 플라스크의 `@app.route` 가 하는 일이 라우팅 테이블에 등록만 하는 이유이기도 하다. 무거운 준비는 첫 호출로 미뤄라. ([1.19 import 시스템](#/imports))
:::

## 클로저가 전부다

`wrapper` 안에서 `func` 를 어떻게 아는가? `wrapper` 가 반환된 뒤에는 `timed` 의 지역 이름 공간이 사라졌을 텐데.

사라지지 않는다. **클로저 셀**에 잡혀 있다. ([1.10 함수: 인자, 스코프, 클로저](#/functions))

```pyrepl
>>> def deco(f):
...     def wrapper(*a, **k):
...         return f(*a, **k)
...     return wrapper
...
>>> def orig(): pass
...
>>> d = deco(orig)
>>> d.__code__.co_freevars
('f',)
>>> d.__closure__
(<cell at 0x...: function object at 0x...>,)
>>> d.__closure__[0].cell_contents is orig
True
```

`wrapper` 는 `f` 를 **자유 변수**로 쓰므로, 컴파일러가 `f` 를 셀에 올린다. 반환된 `wrapper` 함수 객체는 그 셀을 `__closure__` 에 들고 다닌다. 원본 함수는 이 셀 하나 때문에 계속 살아 있다.

```text nolines
   d ──▶ ┌──────────────────────┐
         │ function: wrapper    │
         │ __code__  ──────────────▶ code object (co_freevars = ('f',))
         │ __closure__ ─────────────▶ ( cell )
         └──────────────────────┘         │
                                          ▼
                                   ┌──────────────┐
                                   │ function     │   <- 원본 orig
                                   └──────────────┘
```

**데코레이터에 새 개념은 하나도 없다.** 일급 함수 + 클로저 + `@` 문법. 끝이다.

## `functools.wraps` — 없으면 무엇을 잃는가

방금 만든 데코레이터에는 조용한 버그가 있다.

```pyrepl
>>> def deco(f):
...     def wrapper(*a, **kw):
...         return f(*a, **kw)
...     return wrapper
...
>>> @deco
... def greet(name: str, greeting: str = "안녕") -> str:
...     """인사한다."""
...     return f"{greeting}, {name}"
...
>>> greet.__name__
'wrapper'
>>> greet.__doc__
>>> greet.__qualname__
'deco.<locals>.wrapper'
>>> import inspect
>>> inspect.signature(greet)
<Signature (*a, **kw)>
```

**함수의 정체가 통째로 지워졌다.** `greet` 이 아니라 `wrapper` 다. 독스트링은 없다. 시그니처는 `(*a, **kw)`.

이게 왜 심각한가. `deco(greet)` 이 돌려준 것은 **완전히 다른 함수 객체**다. `greet` 이라는 이름만 그 객체로 옮겨 갔을 뿐이다. 그 객체는 자기가 무엇을 감쌌는지 모른다. 그래서:

- `help(greet)` 이 쓸모없어진다
- Sphinx로 뽑은 API 문서에 함수가 전부 `wrapper` 로 나온다
- 로그에 함수 이름을 찍는 코드가 전부 `wrapper` 를 찍는다
- pickle이 깨진다 (`__qualname__` 으로 원본을 못 찾는다)
- pytest가 픽스처를 이름으로 못 찾는다

`functools.wraps` 가 이걸 고친다.

```pyrepl
>>> import functools
>>> def deco(f):
...     @functools.wraps(f)
...     def wrapper(*a, **kw):
...         return f(*a, **kw)
...     return wrapper
...
>>> @deco
... def greet(name: str, greeting: str = "안녕") -> str:
...     """인사한다."""
...     return f"{greeting}, {name}"
...
>>> greet.__name__
'greet'
>>> greet.__doc__
'인사한다.'
>>> inspect.signature(greet)
<Signature (name: str, greeting: str = '안녕') -> str>
>>> greet.__wrapped__
<function greet at 0x...>
```

::: deep wraps 가 정확히 무엇을 복사하는가
`wraps` 는 `functools.partial(update_wrapper, wrapped=f, ...)` 일 뿐이다. 실제 일은 `update_wrapper` 가 한다. 복사 목록은 모듈 상수로 공개돼 있다.

```pyrepl
>>> import functools
>>> functools.WRAPPER_ASSIGNMENTS
('__module__', '__name__', '__qualname__', '__doc__', '__annotate__', '__type_params__')
>>> functools.WRAPPER_UPDATES
('__dict__',)
```

정확히 세 가지 일을 한다.

1. `WRAPPER_ASSIGNMENTS` 의 속성을 **대입**한다 (`wrapper.__name__ = f.__name__`).
2. `WRAPPER_UPDATES` 의 속성을 **갱신**한다 (`wrapper.__dict__.update(f.__dict__)`) — 대입이 아니라 update다. 원본에 붙은 커스텀 속성이 따라온다.
3. 마지막에 `wrapper.__wrapped__ = f` 를 **설정한다.**

3번이 마지막인 게 중요하다. 2번에서 원본의 `__dict__` 를 통째로 복사하는데, 원본이 이미 데코레이트된 함수라면 그 안에 `__wrapped__` 가 들어 있다. 3번이 그걸 덮어써서 **`__wrapped__` 가 항상 바로 한 겹 아래**를 가리키게 한다.

```pyrepl
>>> one = deco(base)
>>> two = deco(one)
>>> two.__wrapped__ is one          # 한 겹 아래
True
>>> two.__wrapped__ is base         # __dict__ 복사본이 이겼다면 이게 True였을 것
False
```

`WRAPPER_ASSIGNMENTS` 의 내용은 **버전마다 바뀐다.** 3.12에서 `__type_params__` 가 들어왔고, 3.14에서는 PEP 649(어노테이션 지연 평가) 때문에 `__annotations__` 자리가 `__annotate__` 로 바뀌었다. 그래도 `greet.__annotations__` 는 그대로 동작한다 — `__annotate__` 를 호출해 만들어 내기 때문이다. ([2.9 런타임 타입 정보](#/runtime-typing))

없는 속성은 조용히 건너뛴다. 그래서 `__name__` 이 없는 객체(예: `functools.partial`)를 감싸도 `AttributeError` 가 나지 않는다. 대신 `wrapper.__name__` 이 `'wrapper'` 로 남는다 — 고쳐지지 않은 것을 조용히 넘어간다는 뜻이니 주의하라.
:::

::: warn __wrapped__ 는 signature 를 거짓말시킬 수 있다
`inspect.signature` 는 기본적으로 `__wrapped__` 체인을 **끝까지 따라간다.** 래퍼가 시그니처를 **바꿨다면** 보고되는 시그니처는 거짓말이 된다.

```pyrepl
>>> def add_verbose(func):
...     @functools.wraps(func)
...     def wrapper(*args, verbose=False, **kwargs):
...         if verbose: print("호출:", func.__name__)
...         return func(*args, **kwargs)
...     return wrapper
...
>>> @add_verbose
... def area(w, h): return w * h
...
>>> inspect.signature(area)
<Signature (w, h)>
>>> inspect.signature(area, follow_wrapped=False)
<Signature (*args, verbose=False, **kwargs)>
>>> area(3, 4, verbose=True)
호출: area
12
```

`verbose` 라는 인자가 **실제로 받아지는데 시그니처에는 없다.** 타입 체커, IDE 자동완성, 그리고 시그니처로 인자를 채워 넣는 프레임워크(FastAPI, click, pytest)가 전부 속는다.

**규칙**: 시그니처를 바꾸는 래퍼에는 `wraps` 를 쓰되 `__wrapped__` 를 지우거나, `wrapper.__signature__` 를 직접 설정해 진실을 말해라. `__signature__` 가 `__wrapped__` 보다 우선한다.

원본을 손에 넣고 싶으면 `inspect.unwrap(f)` 를 쓴다. `f.__wrapped__.__wrapped__...` 를 손으로 타지 마라 — 순환 참조에 빠지면 무한 루프다. `unwrap` 은 그걸 검사한다.
:::

## 인자 있는 데코레이터 — 왜 3중 중첩인가

`@retry(times=3)` 를 만들고 싶다. 여기서 대부분이 막힌다. 막히는 이유는 **치환을 안 하기 때문**이다. 치환해 보자.

```python
@retry(times=3)
def fetch(): ...

# ↓ 문법 설탕을 벗기면

fetch = retry(times=3)(fetch)
```

`retry(times=3)` 가 먼저 평가되고, **그 결과를** `fetch` 에 적용한다. 즉 `retry(times=3)` 는 **데코레이터를 반환해야 한다.** `retry` 자체는 데코레이터가 아니다. **데코레이터 공장**이다.

```text nolines
   retry(times=3)          -> decorator      <- 설정을 클로저에 가둔다
   decorator(fetch)        -> wrapper        <- 원본을 클로저에 가둔다
   wrapper(*args)          -> 실제 실행
```

층이 세 개인 이유는 **가둘 것이 두 개**이기 때문이다. 설정(`times`)과 원본 함수(`fetch`). 클로저 한 층당 하나씩 가둔다.

```python title="retry.py — 실행 가능"
import functools
import time


def retry(times=3, delay=0.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last = e
                    if attempt < times and delay:
                        time.sleep(delay * 2 ** (attempt - 1))   # 지수 백오프
            raise last          # 마지막 예외를 그대로 올린다
        return wrapper
    return decorator


calls = 0


@retry(times=3)
def flaky():
    global calls
    calls += 1
    if calls < 3:
        raise ValueError(f"실패 {calls}")
    return f"성공 (시도 {calls}회)"


print(flaky())          # 성공 (시도 3회)
```

두 클로저를 직접 볼 수 있다. 최종 `wrapper` 는 자유 변수를 네 개 들고 있다. `func`(원본 함수)와 `times`(설정) 말고도 `wrapper` 안에서 실제로 참조하는 `delay`, `exceptions` 까지 전부 셀에 올라간다 — 컴파일러는 개념 두 개(설정, 원본)가 아니라 **실제로 참조되는 이름 하나하나**를 독립된 셀로 가둔다.

```pyrepl
>>> flaky.__code__.co_freevars
('delay', 'exceptions', 'func', 'times')
>>> [c.cell_contents for c in flaky.__closure__]
[0.0, (<class 'Exception'>,), <function flaky at 0x...>, 3]
```

::: danger 괄호를 빼먹으면 조용히 망가진다
```pyrepl
>>> @retry            # ❌ 괄호가 없다
... def oops(): return 1
...
>>> oops()
Traceback (most recent call last):
  ...
TypeError: retry.<locals>.decorator() missing 1 required positional argument: 'func'
```

치환해 보면 명백하다. `oops = retry(oops)` 다. 함수 `oops` 가 **`times` 인자로** 들어가고, `retry` 는 `decorator` 를 반환한다. 이제 이름 `oops` 는 `decorator` 를 가리킨다.

**에러가 정의 시점이 아니라 호출 시점에 난다.** 그리고 에러 메시지에 `oops` 라는 단어가 없다. 코드베이스가 크면 이걸 찾는 데 30분이 간다.

더 나쁜 경우: 데코레이터의 첫 인자가 `bool` 이거나 `Callable` 이면 아무 에러 없이 **조용히 잘못 동작한다.**
:::

::: tip 괄호를 선택적으로 만드는 관용구
`@trace` 와 `@trace(prefix="DEBUG")` 를 둘 다 받고 싶다면, **설정 인자를 키워드 전용으로 강제하고** 첫 인자로 함수가 왔는지 검사한다.

```python title="flexible.py"
import functools


def trace(func=None, *, prefix="TRACE"):
    if func is None:                        # @trace(...) 로 불렸다
        return functools.partial(trace, prefix=prefix)

    @functools.wraps(func)                  # @trace 로 불렸다
    def wrapper(*args, **kwargs):
        print(f"[{prefix}] {func.__name__}")
        return func(*args, **kwargs)
    return wrapper


@trace
def a(): pass


@trace()
def b(): pass


@trace(prefix="DEBUG")
def c(): pass


a()      # [TRACE] a
b()      # [TRACE] b
c()      # [DEBUG] c
```

`*` 가 핵심이다. 이게 없으면 `@trace("DEBUG")` 가 `func="DEBUG"` 로 해석돼 버린다. `functools.partial` 로 자기 자신을 부분 적용하면 중첩 한 층을 아낄 수 있다.

표준 라이브러리가 이 패턴을 쓴다. `functools.lru_cache` 와 `dataclasses.dataclass` 를 열어 보면 똑같은 구조다.
:::

## 스택 순서 — 아래에서 위로

데코레이터를 여러 개 쌓으면 순서가 헷갈린다. 규칙은 하나다. **치환하라.**

```python
@A
@B
def target(): ...

# ↓
target = A(B(target))
```

`B` 가 먼저, `A` 가 나중이다. **가장 가까운 것이 먼저 적용된다.**

```python title="stack.py"
def A(f):
    print("A 적용")
    def w(*a, **k):
        print("A 진입"); r = f(*a, **k); print("A 이탈"); return r
    return w


def B(f):
    print("B 적용")
    def w(*a, **k):
        print("B 진입"); r = f(*a, **k); print("B 이탈"); return r
    return w


@A
@B
def target():
    print("target 실행")


print("--- 호출 ---")
target()
```

```text nolines
B 적용
A 적용
--- 호출 ---
A 진입
B 진입
target 실행
B 이탈
A 이탈
```

**적용은 아래에서 위로, 실행은 위에서 아래로.** 모순처럼 보이지만 당연하다. `A` 가 나중에 적용됐으니 `A` 의 래퍼가 **가장 바깥**이고, 바깥이 먼저 실행된다. 양파를 생각하면 된다 — 마지막에 씌운 껍질이 제일 겉이다.

```text nolines
   target ──▶ ┌─ A's wrapper ──────────────┐
              │  ┌─ B's wrapper ────────┐  │
              │  │  ┌─ original ─────┐  │  │
              │  │  └────────────────┘  │  │
              │  └──────────────────────┘  │
              └────────────────────────────┘
```

::: danger property 와 데코레이터의 순서 — 에러도 안 난다
```pyrepl
>>> class D:
...     @property
...     @deco                    # ✅ deco 가 함수에 먼저, property 가 나중
...     def x(self): return 1
...
>>> D().x
1

>>> class E:
...     @deco
...     @property                # ❌ property 객체를 deco 가 감쌌다
...     def x(self): return 1
...
>>> E().x
<bound method deco.<locals>.w of <__main__.E object at 0x...>>
```

**예외가 안 난다.** `E().x` 가 값이 아니라 **바운드 메서드 객체**를 돌려준다. `deco` 가 `property` 객체를 감싸 평범한 함수 `w` 를 반환했고, 함수는 그 자체로 디스크립터라 인스턴스 접근 시 바운드 메서드가 되기 때문이다. ([3.3 디스크립터](#/descriptors))

`if E().x:` 같은 코드는 바운드 메서드가 항상 참이므로 **조용히 통과한다.** 이게 실제 장애가 되는 방식이다.

**규칙: 디스크립터를 만드는 데코레이터(`property`, `staticmethod`, `classmethod`, `cached_property`)는 항상 가장 위(가장 바깥)에 둔다.**
:::

::: note staticmethod 와 classmethod 는 3.14에서 다르게 동작한다
```pyrepl
>>> callable(staticmethod(lambda x: x))
True
>>> callable(classmethod(lambda cls: 1))
False
```

`staticmethod` 객체는 3.10부터 **직접 호출 가능**해졌다. 그래서 `@deco` 를 `@staticmethod` 위에 잘못 얹어도 3.14에서는 동작한다. `classmethod` 는 여전히 호출 불가라 `TypeError: 'classmethod' object is not callable` 이 난다.

즉 같은 실수가 한쪽은 통과하고 한쪽은 터진다. **동작한다고 올바른 게 아니다.** 순서 규칙을 지켜라.
:::

## 클래스 데코레이터

데코레이터는 함수 전용이 아니다. `@` 뒤의 것이 **무엇이든 호출해서 결과를 이름에 다시 묶을 뿐**이다. 클래스 정의 위에도 얹을 수 있다.

```python
@register("lidar")
class Lidar: ...

# ↓
Lidar = register("lidar")(Lidar)
```

가장 흔한 실전 용도는 **레지스트리**다. ROS 노드, 플러그인, 모델 아키텍처, 직렬화 포맷 — 전부 이 패턴이다.

```python title="registry.py"
REGISTRY = {}


def register(name):
    def deco(cls):
        REGISTRY[name] = cls
        cls.registry_name = name        # 클래스를 제자리에서 수정한다
        return cls                      # 원본을 그대로 돌려준다
    return deco


@register("lidar")
class Lidar: pass


@register("camera")
class Camera: pass


print(REGISTRY)
# {'lidar': <class '__main__.Lidar'>, 'camera': <class '__main__.Camera'>}
print(Lidar.registry_name)      # lidar
```

**여기서 핵심은 `return cls` 다.** 클래스를 수정만 하고 원본을 돌려주면 아무것도 깨지지 않는다. `isinstance`, 상속, `__name__` 전부 그대로다. 표준 라이브러리의 클래스 데코레이터가 대부분 이 방식이다 — `functools.total_ordering` 은 비교 메서드를 채워 넣고 클래스를 돌려주고, `@dataclass` 는 `__init__`/`__repr__`/`__eq__` 를 만들어 붙이고 클래스를 돌려준다. ([2.6 dataclasses](#/dataclasses))

::: danger 클래스를 함수로 바꿔치기하면 클래스가 아니게 된다
인터넷에서 가장 흔한 싱글턴 레시피다. 그리고 틀렸다.

```python title="broken_singleton.py"
import functools


def singleton(cls):
    instances = {}

    @functools.wraps(cls)
    def get(*a, **k):
        if cls not in instances:
            instances[cls] = cls(*a, **k)
        return instances[cls]
    return get                          # ❌ 클래스가 아니라 함수를 돌려준다


@singleton
class Config: pass
```

```pyrepl
>>> Config() is Config()
True                                    # 여기까지는 잘 된다
>>> type(Config)
<class 'function'>                      # Config 는 이제 클래스가 아니다
>>> isinstance(Config(), Config)
TypeError: isinstance() arg 2 must be a type, ...
>>> class Sub(Config): pass
TypeError: function() argument 'code' must be code, not str
```

마지막 에러 메시지를 보라. `Sub` 의 베이스가 함수이므로 파이썬이 메타클래스를 `type(Config)` = `function` 으로 잡고, `function('Sub', (), {...})` 를 호출한 것이다. **원인과 아무 관계없는 메시지**가 나온다.

`@functools.wraps(cls)` 가 `__name__` 과 `__doc__` 을 베껴 놔서 **디버깅할 때 더 헷갈린다.** `repr` 만 보면 클래스처럼 생겼는데 클래스가 아니다.

싱글턴이 정말 필요하면 모듈 수준 인스턴스를 하나 만들어라. 파이썬 모듈은 이미 싱글턴이다. 클래스 자체를 바꿔야 한다면 `__init_subclass__` 나 메타클래스가 맞는 도구다. ([3.4 메타클래스](#/metaclass))
:::

## 실전: 캐시

`functools.cache` 는 데코레이터가 만들어 내는 가치를 가장 극적으로 보여준다.

```python title="fib.py"
import functools
import time


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@functools.cache
def cfib(n):
    return n if n < 2 else cfib(n - 1) + cfib(n - 2)


t = time.perf_counter(); fib(30);  print(f"naive : {(time.perf_counter()-t)*1000:.1f} ms")
t = time.perf_counter(); cfib(30); print(f"cached: {(time.perf_counter()-t)*1e6:.1f} us")
print(cfib.cache_info())
```

```text nolines
naive : 62.7 ms
cached: 29.3 us
CacheInfo(hits=28, misses=31, maxsize=None, currsize=31)
```

**2,000배 이상이다.** 함수 본체는 한 글자도 안 바뀌었다. $O(\varphi^n)$ 이 $O(n)$ 이 됐다.

한 줄 위에서 벌어진 일: `cfib` 라는 이름이 캐시 래퍼를 가리키고, **재귀 호출도 그 이름을 거친다.** 그래서 모든 하위 호출이 캐시를 탄다. 이게 데코레이터가 아니라 `memo_fib = cache(fib)` 였다면 내부 재귀는 여전히 `fib` 를 불러 캐시를 못 탄다. **데코레이터가 이름을 갈아 끼운다는 사실이 여기서 결정적이다.**

::: perf lru_cache 는 C로 구현돼 있다
직접 만든 `dict` 메모이제이션과 비교해 보자. 이미 캐시가 채워진 상태에서 **적중 1회의 비용**이다.

```text nolines
   직접 만든 dict 메모   42.5 ns/hit
   functools.lru_cache   34.9 ns/hit      <- 더 빠르다
   functools.cache       33.3 ns/hit
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르다.)

이유는 `functools.lru_cache` 가 순수 파이썬이 아니기 때문이다.

```pyrepl
>>> import functools
>>> @functools.cache
... def q(n): return n
...
>>> type(q)
<class 'functools._lru_cache_wrapper'>
```

함수가 아니라 **C 확장 타입의 인스턴스**다. 키 생성, 해시 조회, LRU 연결 리스트 갱신이 전부 C 레벨에서 일어나 파이썬 프레임을 하나도 만들지 않는다.

`functools.cache` 는 `lru_cache(maxsize=None)` 의 별칭이다. `maxsize=None` 이면 LRU 순서 관리(이중 연결 리스트 조작)를 통째로 건너뛰는 별도 경로를 타므로, **크기 제한이 필요 없으면 `cache` 가 항상 더 낫다.** 대신 캐시가 무한히 자란다. ([3.1 functools](#/functools))
:::

::: danger lru_cache 를 메서드에 붙이면 인스턴스가 안 죽는다
```python title="leak.py"
import functools, gc, weakref


class Heavy:
    def __init__(self, n): self.n = n

    @functools.lru_cache(maxsize=None)      # ❌
    def calc(self, x): return self.n * x


h = Heavy(2)
h.calc(3)
r = weakref.ref(h)
del h
gc.collect()
print("살아 있나?:", r() is not None)      # True — 죽지 않았다
```

`calc` 는 **클래스 속성**이다. 캐시 하나가 클래스에 붙어 모든 인스턴스가 공유하고, 캐시 키에 `self` 가 들어간다. 즉 **캐시가 인스턴스에 강한 참조를 영구히 잡는다.** `del h` 를 해도, GC를 돌려도 죽지 않는다.

장시간 도는 서비스에서 이건 순수한 메모리 누수다. 게다가 캐시 크기가 `인스턴스 수 × 인자 조합 수` 로 곱해진다.

대안:

1. 인자 없는 값이면 **`functools.cached_property`** — 캐시를 인스턴스 `__dict__` 에 저장하므로 인스턴스와 함께 죽는다.
2. 인자가 있으면 **`__init__` 안에서 인스턴스별 캐시를 만든다**: `self.calc = functools.cache(self._calc)`.
3. `self` 를 안 쓰면 `@staticmethod` 로 내리고 캐시한다.

`cached_property` 에도 함정은 있다. `__slots__` 클래스에는 못 쓴다. 저장할 `__dict__` 가 없기 때문이다.

```pyrepl
>>> class Slotted:
...     __slots__ = ("n",)
...     @functools.cached_property
...     def x(self): return 1
...
>>> Slotted().x
TypeError: No '__dict__' attribute on 'Slotted' instance to cache 'x' property.
```
([1.12 클래스와 데이터 모델](#/classes))
:::

::: cote 코딩테스트 포인트
**메모이제이션 DP는 `@functools.cache` 한 줄이면 끝난다.** 직접 `dict` 를 관리하지 마라 — 느리고, 코드가 길고, 실수한다.

```python
import sys
from functools import cache

sys.setrecursionlimit(10 ** 6)      # 재귀 DP는 이게 필수다


@cache
def dp(i, w):
    if i == n or w == 0:
        return 0
    best = dp(i + 1, w)
    if weights[i] <= w:
        best = max(best, dp(i + 1, w - weights[i]) + values[i])
    return best
```

시험장에서 반드시 기억할 세 가지.

1. **인자는 해시 가능해야 한다.** 리스트를 넘기면 `TypeError: unhashable type: 'list'` 다. 튜플로 바꾸거나, 전역 리스트를 두고 인덱스만 넘겨라 (위 코드처럼).
2. **캐시는 전역이다.** 테스트 케이스가 여러 개면 케이스마다 `dp.cache_clear()` 를 부르지 않으면 이전 케이스의 답이 나온다. 이것 때문에 틀리는 사람이 매년 나온다.
3. **재귀 DP는 파이썬에서 프레임 비용이 크다.** 상태 수가 수백만이면 `@cache` 재귀보다 반복문 타뷸레이션이 안전하다. ([7.20 동적 계획법 기초](#/dp-basics), [8.3 시간 초과를 피하는 관용구](#/tle))
:::

## 실전: 타이밍과 검증

타이밍 데코레이터를 제대로 쓰면 이렇다. 처음의 코드와 비교해 보라.

```python title="timed.py"
import functools
import time


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()     # time.time() 은 시스템 시계라 뒤로 갈 수 있다
        try:
            return func(*args, **kwargs)
        finally:                        # 예외가 나도 시간은 남긴다
            elapsed = time.perf_counter() - start
            print(f"[{func.__qualname__}] {elapsed * 1000:.3f} ms")
    return wrapper


@timed
def work(n):
    return sum(i * i for i in range(n))


work(100_000)          # [work] 3.453 ms
```

세 가지가 의도적이다.

- **`perf_counter`**: `time.time()` 은 벽시계라 NTP 동기화로 뒤로 갈 수 있다. 경과 시간 측정은 항상 단조 증가 시계로. ([5.1 측정 없이 최적화 없다](#/profiling))
- **`try/finally`**: 함수가 예외를 던져도 시간이 찍히고, 예외는 그대로 전파된다. `except` 로 삼키면 안 된다.
- **`__qualname__`**: 메서드일 때 `Robot.move` 로 나온다. `__name__` 은 그냥 `move` 라 어느 클래스인지 모른다.

검증 데코레이터는 `inspect.signature` 로 인자를 이름으로 잡는다.

```python title="validate.py"
import functools
import inspect


def validate(**rules):
    def decorator(func):
        sig = inspect.signature(func)              # 정의 시점에 딱 한 번 계산한다
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()                 # 기본값도 검사 대상이다
            for name, check in rules.items():
                value = bound.arguments[name]
                if not check(value):
                    raise ValueError(f"{func.__name__}: 인자 {name}={value!r} 가 조건을 만족하지 않는다")
            return func(*bound.args, **bound.kwargs)
        return wrapper
    return decorator


@validate(n=lambda v: v > 0, name=lambda v: isinstance(v, str) and v)
def make(n, name="robot"):
    return [name] * n


print(make(2))                # ['robot', 'robot']
print(make(2, name="arm"))    # ['arm', 'arm']
make(-1)                      # ValueError: make: 인자 n=-1 가 조건을 만족하지 않는다
make(n=3, name="")            # ValueError: make: 인자 name='' 가 조건을 만족하지 않는다
```

`sig.bind` 가 핵심이다. `make(-1)` 로 부르든 `make(n=-1)` 로 부르든 **`bound.arguments["n"]` 으로 통일**된다. 위치 인자와 키워드 인자를 손으로 구분하려 들면 지옥이 열린다. `sig` 를 `decorator` 안(정의 시점)에서 만든 것도 의도적이다 — `wrapper` 안에 넣으면 호출마다 시그니처를 다시 판다.

::: perf inspect.signature.bind 는 70배 느리다
```text nolines
   f(a, b, c=3) 직접 호출     약 38 ns
   sig.bind 경유 호출        약 2750 ns      <- 약 70배
```

(Python 3.14.5 / Windows 기준. `f(a, b, c=3)` 에 대해 `bind` + `apply_defaults` + 호출. 3회 반복 측정에서 direct 36.7~40.5 ns, bind 2717.5~2853.8 ns, 배수 67~75배로 일관됐다 — 절대값은 기기마다 다르지만 배수는 노이즈가 아니다.)

`bind` 는 매번 `BoundArguments` 객체와 `dict` 를 새로 만들고 파라미터를 순회한다. **핫 루프 안의 함수에는 절대 쓰지 마라.** 초당 수백 회 이하로 불리는 진입점(API 핸들러, CLI 명령, ROS 서비스 콜백)에서는 2.7마이크로초가 무의미하다. 거기서만 써라.

이건 pydantic이 왜 검증 로직을 Rust로 옮겼는지에 대한 답이기도 하다. ([2.7 attrs와 pydantic v2](#/pydantic))
:::

## 데코레이터의 실제 비용

데코레이터는 공짜가 아니다. 래퍼 한 겹은 **함수 호출 한 번 + 인자 재포장**을 추가한다.

```python title="bench.py"
import functools, timeit

def plain(x): return x + 1

def deco(f):
    @functools.wraps(f)
    def w(*a, **kw): return f(*a, **kw)         # 가변 인자
    return w

def deco_fixed(f):
    @functools.wraps(f)
    def w(x): return f(x)                       # 시그니처 고정
    return w
```

```text nolines
   plain(1)          26.5 ns/call     기준
   wfix(1)           41.5 ns/call     1.6x   (시그니처 고정 래퍼 1겹)
   wrapped(1)        76.8 ns/call     2.9x   (*args/**kwargs 래퍼 1겹)
   wrapped3(1)      167.2 ns/call     6.3x   (*args 래퍼 3겹)
```

(Python 3.14.5 / Windows 기준 실측. 자릿수는 어디서나 같다.)

읽어야 할 것이 세 가지다.

1. **래퍼 한 겹이 약 50ns.** 함수 본체가 `x + 1` 이라 상대 배수가 커 보이지만, **절대값은 수십 나노초다.** 함수 본체가 1마이크로초만 돼도 오차 범위다. 배수가 아니라 절대값으로 판단하라.
2. **`*args, **kwargs` 가 오버헤드의 대부분을 차지한다.** 시그니처 고정 래퍼의 순수 오버헤드는 15ns(41.5-26.5)인데, `*args` 래퍼는 50ns(76.8-26.5)다. `*args` 는 매 호출마다 **튜플을 새로 할당**하고, `**kwargs` 는 **딕셔너리를 새로 할당**한다. 그리고 안쪽 호출에서 다시 푼다. 인자가 고정된 함수만 감싸는 데코레이터라면 시그니처를 고정하는 것만으로 오버헤드를 3분의 1 이하로 줄일 수 있다.
3. **겹치면 곱이 아니라 합이다.** 3겹이 6.3배지 2.9의 세제곱(약 24배)이 아니다. 각 층이 자기 몫(약 47ns)을 더할 뿐이다.

::: tip 언제 데코레이터를 쓰지 말아야 하는가
데코레이터는 강력해서 남용되기 쉽다. 다음 경우엔 쓰지 마라.

- **호출당 100ns가 문제가 되는 핫 루프.** NumPy 내부 루프, 파티클 필터 갱신, 렌더링 루프. 인라인이 답이다.
- **한 곳에서만 쓰는 로직.** 데코레이터는 **횡단 관심사**(여러 함수에 공통으로 걸치는 것)를 위한 도구다. 한 함수에만 필요하면 그냥 그 함수 안에 써라.
- **호출 흐름을 이해하기 어렵게 만들 때.** 데코레이터 5개가 쌓인 함수는 트레이스백이 5겹으로 나온다. 디버깅 비용이 재사용 이득을 넘으면 진 것이다.
- **상태를 숨길 때.** 클로저 안의 `cache = {}` 는 밖에서 보이지 않는다. 테스트에서 초기화할 방법을 반드시 제공하라 (`lru_cache` 의 `cache_clear` 처럼).
:::

## 요약

한 문단으로 압축하면 이렇다.

> `@deco` 는 **`f = deco(f)` 의 문법 설탕**이다. 데코레이터는 함수를 받아 함수를 돌려주는 평범한 호출 가능 객체이고, **클로저**로 원본과 설정을 가둔다. 인자가 있으면 `f = deco(args)(f)` 가 되므로 **한 층이 더 필요하다**(공장 → 데코레이터 → 래퍼). 래퍼는 원본과 **다른 객체**이므로 `functools.wraps` 로 정체(`__name__`, `__doc__`, `__wrapped__`)를 옮겨 줘야 한다. 스택은 **아래에서 위로 적용되고 위에서 아래로 실행된다.** 클래스에도 붙일 수 있는데, **클래스를 수정하고 돌려주는** 것만 안전하다.

체크리스트:

- [ ] `@` 를 보면 항상 `f = deco(f)` 로 치환해서 읽어라.
- [ ] 데코레이터 본체는 **import 시점**에 실행된다. 무거운 일을 넣지 마라.
- [ ] `functools.wraps` 를 **항상** 붙여라. 안 붙이면 함수의 정체가 지워진다.
- [ ] 인자 있는 데코레이터는 3층. 괄호를 빼먹으면 **호출 시점에** 이상한 에러가 난다.
- [ ] `property`/`staticmethod`/`classmethod` 는 **가장 바깥**에.
- [ ] 클래스 데코레이터는 `return cls`. 함수로 바꿔치기하면 클래스가 아니게 된다.
- [ ] `lru_cache` 를 메서드에 붙이지 마라. 인스턴스가 안 죽는다.
- [ ] 래퍼 한 겹은 약 50ns. 배수가 아니라 **절대값**으로 판단하라.

::: quiz 연습문제
1. 다음 각각을 `@` 없는 형태로 치환해 쓴 뒤, 실행 순서를 예측하고 확인하라.

   ```python
   @A
   @B(1)
   @C
   def f(): ...
   ```

2. 아래 데코레이터에는 버그가 두 개 있다. 찾아서 고쳐라.

   ```python
   def count_calls(func):
       calls = 0
       def wrapper(*args, **kwargs):
           calls += 1
           print(f"{func.__name__} 호출 {calls}회")
           return func(*args, **kwargs)
       return wrapper
   ```

   (힌트: 하나는 `UnboundLocalError` 다. 다른 하나는 에러가 안 난다.)

3. 다음 코드는 왜 `wrapper` 를 출력하는가? `functools.wraps` 를 붙였는데도 그런 이유를 설명하라.

   ```python
   import functools

   def deco(f):
       def wrapper(*a, **k): return f(*a, **k)
       return functools.wraps(wrapper)(f)      # 인자 순서를 보라
   ```

4. `@functools.cache` 를 붙인 함수의 캐시를 **밖에서 들여다볼** 방법이 있는가? `cache_info()` 말고, 실제 저장된 키-값 쌍을 얻을 수 있는가? 예측한 뒤 `dir()` 로 확인하라. 없다면 왜 없게 설계했겠는가?

5. **깊이 생각해 볼 문제.** 다음 두 데코레이터는 기능이 같다. 하나는 클로저를, 하나는 클래스를 쓴다. `count` 를 밖에서 읽고 싶다면 어느 쪽이 나은가? 그리고 `Counter` 버전을 **메서드에 붙이면** 왜 깨지는가? (힌트: `Counter` 인스턴스는 디스크립터가 아니다.)

   ```python
   def counted(func):
       def wrapper(*a, **k):
           wrapper.count += 1
           return func(*a, **k)
       wrapper.count = 0
       return wrapper


   class Counter:
       def __init__(self, func):
           self.func = func
           self.count = 0
       def __call__(self, *a, **k):
           self.count += 1
           return self.func(*a, **k)
   ```
:::

**다음 절**: [1.12 클래스와 데이터 모델](#/classes) — 인스턴스 속성은 왜 딕셔너리이고, `__slots__` 는 무엇을 얼마나 아끼는가.
