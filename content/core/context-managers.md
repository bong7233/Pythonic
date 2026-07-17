# 1.17 컨텍스트 매니저

::: lead
파일을 열었으면 닫아야 한다. 락을 잡았으면 놓아야 한다. 트랜잭션을 시작했으면 커밋하거나 롤백해야 한다. 이 "반드시 짝을 맞춰야 하는 일"을 사람의 기억력에 맡기면 반드시 사고가 난다. `with` 는 그 짝맞춤을 **문법으로 강제하는** 장치다. 이 절은 `with` 가 실제로 어떤 코드로 번역되는지, `__exit__` 의 반환값이 왜 그렇게 위험한지, 그리고 정리할 자원의 **개수를 컴파일 시점에 모를 때** 무엇을 써야 하는지를 다룬다.
:::

## 문제: 자원은 돌려줘야 한다

```python title="어디가 잘못됐을까"
def read_config(path):
    f = open(path, encoding="utf-8")
    data = parse(f.read())      # 여기서 예외가 나면?
    f.close()
    return data
```

`parse` 가 예외를 던지면 `f.close()` 는 영원히 실행되지 않는다. 파일 디스크립터가 샌다. 서버 프로세스에서 이게 반복되면 언젠가 `OSError: [Errno 24] Too many open files` 로 죽는다.

"그럼 `try/finally` 를 쓰면 되잖아"가 첫 번째 답이다. 맞다. 그리고 `with` 는 정확히 그 `try/finally` 다. 다만 **잊을 수 없게** 만든 것이다.

### "가비지 컬렉터가 알아서 닫아 주지 않나?"

CPython은 참조 카운팅을 쓰니까([1.1 객체, 이름, 참조](#/objects-names)), 마지막 참조가 사라지는 순간 파일 객체의 `__del__` 이 불려 닫힌다. 실제로 그렇게 동작한다. 그런데 CPython은 **이걸 믿지 말라고 경고까지 한다.**

```python title="닫지 않은 파일"
def leak():
    f = open(__file__)
    f.read(1)

leak()
```

```bash
$ python -W always::ResourceWarning leak.py
leak.py:5: ResourceWarning: unclosed file <_io.TextIOWrapper name='leak.py' ...>
```

경고가 나오는 이유는 셋이다.

**첫째, 참조 카운팅은 CPython의 구현 세부사항이다.** PyPy, Jython, GraalPy는 참조 카운팅을 쓰지 않는다. 이 코드는 CPython에서만 우연히 동작한다.

**둘째, 순환 참조에 끼면 소멸이 지연된다.** 언제 GC가 도는지는 아무도 모른다.

```python title="cycle.py"
import gc

class Res:
    def __init__(self, n): self.n = n
    def __del__(self): print(f"__del__ {self.n}")

a, b = Res("A"), Res("B")
a.other = b
b.other = a          # 서로를 참조한다
del a, b
print("del 직후")
gc.collect()
print("gc.collect() 이후")
```

```text nolines
del 직후
__del__ A
__del__ B
gc.collect() 이후
```

`del` 을 했는데 `__del__` 이 그 자리에서 불리지 않았다. `gc.collect()` 를 **명시적으로 부를 때까지** 파일은 열린 채로 있었다.

**셋째, 예외가 나면 트레이스백이 프레임을 붙잡는다.** 이게 제일 안 보이는 함정이다.

```python title="traceback_holds.py"
class R:
    def __del__(self): print("R __del__")

def boom():
    r = R()
    raise ValueError("x")

try:
    boom()
except ValueError:
    print("except 블록 안")
print("except 블록 밖")
```

```text nolines
except 블록 안
R __del__
except 블록 밖
```

`boom()` 이 이미 끝났는데도 `r` 은 살아 있다. 예외 객체의 트레이스백이 `boom` 의 프레임을 붙잡고 있고, 그 프레임이 지역 변수 `r` 을 붙잡고 있기 때문이다. 예외 처리가 끝나야 풀린다. **하필 자원 정리가 가장 중요한 상황인 예외 발생 시점에, `__del__` 방식이 가장 늦어진다.** ([1.16 예외](#/exceptions))

::: danger `__del__` 에 자원 정리를 맡기지 마라
`__del__` 은 **최후의 방어선**이지 정리 전략이 아니다. 표준 라이브러리의 `__del__` 이 하는 일은 "닫아 주는 것"이 아니라 "닫지 않았다고 경고하는 것"에 가깝다.

게다가 `__del__` 안에서 예외가 나면 **전파되지 않고 stderr로 무시된다.** 정리 실패를 알아챌 방법이 없다. 소멸 순서도 보장되지 않아서, 인터프리터 종료 중에는 `__del__` 이 참조하는 전역이 이미 `None` 이 된 경우도 있다.

정리는 `with` 로 한다. 예외 없다.
:::

## `with` 는 무엇으로 번역되는가

`with` 는 문법 설탕이다. 컴파일러가 다음과 같이 펼친다.

```python title="with EXPR as VAR: BODY 의 등가 코드"
mgr = EXPR
exit_fn = type(mgr).__exit__          # ① 먼저 찾아 둔다
value = type(mgr).__enter__(mgr)     # ② 그 다음에 진입
hit_except = False
try:
    VAR = value
    BODY
except BaseException:
    hit_except = True
    if not exit_fn(mgr, *sys.exc_info()):    # ③ 반환값이 참이면 삼킨다
        raise
finally:
    if not hit_except:
        exit_fn(mgr, None, None, None)
```

바이트코드로 확인하면 이 순서가 그대로 보인다.

```pyrepl
>>> import dis
>>> dis.dis(compile('with open("f") as f:\n    print(f)', "<w>", "exec"))
  0           RESUME                   0

  1           LOAD_NAME                0 (open)
              PUSH_NULL
              LOAD_CONST               0 ('f')
              CALL                     1
              COPY                     1
              LOAD_SPECIAL             1 (__exit__)
              SWAP                     2
              SWAP                     3
              LOAD_SPECIAL             0 (__enter__)
              CALL                     0
      L1:     STORE_NAME               1 (f)
...
      L3:     PUSH_EXC_INFO
              WITH_EXCEPT_START
              TO_BOOL
              POP_JUMP_IF_TRUE         2 (to L4)
              NOT_TAKEN
              RERAISE                  2
```

여기서 세 가지를 읽어야 한다.

::: deep `LOAD_SPECIAL` — 특수 메서드는 타입에서 찾는다
`LOAD_SPECIAL __exit__` 이 `LOAD_SPECIAL __enter__` 보다 **먼저** 나온다. 이 순서는 우연이 아니다. `__exit__` 이 없는 객체에 `with` 를 걸면 **`__enter__` 는 아예 실행되지 않는다.**

```pyrepl
>>> class OnlyEnter:
...     def __enter__(self):
...         print("__enter__ 실행됨!")
...         return self
...
>>> with OnlyEnter():
...     pass
...
Traceback (most recent call last):
  ...
TypeError: 'OnlyEnter' object does not support the context manager protocol (missed __exit__ method)
```

"실행됨!"이 찍히지 않았다. 진입해 놓고 나올 방법이 없어서 자원이 새는 상황을 원천 봉쇄한 것이다.

그리고 `LOAD_SPECIAL` 은 **인스턴스 딕셔너리를 건너뛰고 타입에서 찾는다.** 다른 모든 특수 메서드와 같은 규칙이다([1.14 특수 메서드](#/dunder)). 결과가 이렇다.

```pyrepl
>>> class Proxy:
...     def __init__(self, target): self._t = target
...     def __getattr__(self, name): return getattr(self._t, name)
...
>>> class Real:
...     def __enter__(self): return self
...     def __exit__(self, *a): return False
...
>>> p = Proxy(Real())
>>> p.__enter__                      # 속성 접근으로는 잘 보인다
<bound method Real.__enter__ of <__main__.Real object at 0x...>>
>>> with p:
...     pass
...
Traceback (most recent call last):
  ...
TypeError: 'Proxy' object does not support the context manager protocol (missed __exit__ method)
```

**`__getattr__` 로는 컨텍스트 매니저 프로토콜을 위임할 수 없다.** 프록시를 만들 때 실제로 당하는 함정이다. `__enter__`/`__exit__` 를 클래스에 명시적으로 정의해야 한다. ([3.5 동적 속성](#/dynamic-attrs))
:::

::: hist `__exit__` 은 왜 인자를 세 개나 받나
`__exit__(self, exc_type, exc_value, traceback)` 의 3-튜플은 **PEP 343(2005)이 만들어질 당시의 `sys.exc_info()` 를 그대로 옮긴 것**이다. 그 시절 파이썬 2에서는 예외 객체가 자기 타입과 트레이스백을 들고 있지 않았다. 셋 다 필요했다.

지금은 `exc_value.__class__` 와 `exc_value.__traceback__` 으로 나머지 둘을 복원할 수 있다. 즉 두 인자는 **완전히 잉여**다. 그래도 20년째 그대로인 이유는 하위 호환뿐이다. 당신이 `__exit__` 을 쓸 일이 있다면 `def __exit__(self, exc_type, exc_value, tb)` 를 그냥 받고, 대개는 `def __exit__(self, *exc)` 로 충분하다.
:::

## `__exit__` 의 반환값이 예외를 삼킨다

바이트코드의 `WITH_EXCEPT_START` → `TO_BOOL` → `POP_JUMP_IF_TRUE` 를 다시 보라. `__exit__` 의 반환값에 **`TO_BOOL` 이 걸린다.** `True` 인지 검사하는 게 아니라 **진리값**을 본다.

```python title="swallow.py"
class Swallow:
    def __init__(self, ret): self.ret = ret
    def __enter__(self): return self
    def __exit__(self, et, ev, tb): return self.ret

for r in (True, False, None, 1, 0, "yes", "", []):
    try:
        with Swallow(r):
            raise ValueError("boom")
        print(f"{r!r:8} -> 삼킴")
    except ValueError:
        print(f"{r!r:8} -> 전파")
```

```text nolines
True     -> 삼킴
False    -> 전파
None     -> 전파
1        -> 삼킴
0        -> 전파
'yes'    -> 삼킴
''       -> 전파
[]       -> 전파
```

`"yes"` 가 예외를 삼켰다. 이게 실제 버그의 씨앗이다.

::: danger `__exit__` 에서 실수로 값을 반환하지 마라
```python
class Conn:
    def __exit__(self, *exc):
        return self.sock.close()      # ❌ close() 가 뭘 반환하는지 아는가?
```

`close()` 가 우연히 참인 값을 반환하면 **이 컨텍스트 매니저는 모든 예외를 조용히 삼킨다.** 로그도 없이. 이런 버그는 몇 달 뒤 "왜 에러가 안 잡히지?"로 돌아온다.

`__exit__` 의 마지막 줄에 `return` 이 있으면 항상 의심하라. **삼킬 의도가 없으면 아무것도 반환하지 마라**(`None` → 거짓 → 전파). 삼킬 의도가 있으면 반드시 `return True` 라고 명시적으로 쓰고, 왜 삼키는지 주석을 남겨라.
:::

::: warn `__exit__` 은 `BaseException` 도 삼킨다
`with` 의 등가 코드는 `except BaseException:` 이다. `Exception` 이 아니다.

```pyrepl
>>> class Eater:
...     def __enter__(self): return self
...     def __exit__(self, *a): return True
...
>>> def h():
...     with Eater():
...         raise KeyboardInterrupt
...     return "삼켜짐"
...
>>> h()
'삼켜짐'
```

<kbd>Ctrl</kbd>+<kbd>C</kbd> 가 먹히지 않는 프로그램이 이렇게 만들어진다. `SystemExit` 도 마찬가지다. 삼킬 거라면 **타입을 반드시 확인하고 삼켜라.**

```python
def __exit__(self, exc_type, exc_value, tb):
    return exc_type is not None and issubclass(exc_type, MyRetryable)   # ✅
```
:::

정상 종료 — `return`, `break`, `continue`, 그냥 끝 — 는 모두 `__exit__(None, None, None)` 이다. 예외가 아니므로 삼킬 것도 없다.

```pyrepl
>>> class CM:
...     def __enter__(self): return self
...     def __exit__(self, *a): print("exit args:", a); return True
...
>>> def f():
...     with CM():
...         return "returned"
...
>>> f()
exit args: (None, None, None)
'returned'
```

::: warn `__exit__` 이 예외를 내면 원래 예외를 덮는다
```pyrepl
>>> class Boom:
...     def __enter__(self): return self
...     def __exit__(self, *a): raise RuntimeError("정리 실패")
...
>>> try:
...     with Boom():
...         raise ValueError("본문 예외")
... except RuntimeError as e:
...     print(repr(e), "<-", repr(e.__context__))
...
RuntimeError('정리 실패') <- ValueError('본문 예외')
```

원인(`ValueError`)이 아니라 증상(`RuntimeError`)이 밖으로 나온다. 원본은 `__context__` 에 남지만, 로그를 대충 찍는 코드는 그걸 놓친다. **`__exit__` 안의 정리 코드는 예외를 내지 않도록 방어하라.** ([1.16 예외](#/exceptions))
:::

## `contextlib.contextmanager` — 제너레이터로 쓰는 컨텍스트 매니저

클래스 하나에 메서드 두 개는 짝맞춤 로직을 **두 군데로 찢어 놓는다.** 진입 코드와 정리 코드가 멀어지면 읽기 어렵다. `@contextmanager` 는 이걸 하나의 함수로 되돌린다.

```python title="같은 것을 두 방식으로"
# 클래스 방식
class Timed:
    def __init__(self, label): self.label = label
    def __enter__(self):
        self.t = time.perf_counter()
        return self
    def __exit__(self, *exc):
        print(f"{self.label}: {time.perf_counter() - self.t:.3f}s")


# 제너레이터 방식
from contextlib import contextmanager

@contextmanager
def timed(label):
    t = time.perf_counter()
    try:
        yield
    finally:
        print(f"{label}: {time.perf_counter() - t:.3f}s")
```

`yield` 앞이 `__enter__`, 뒤가 `__exit__` 이다. `yield` 가 내놓는 값이 `as` 뒤에 묶인다. 구현은 정확히 그대로다 — `__enter__` 는 `next(gen)`, `__exit__` 은 `gen.throw(...)` 아니면 `next(gen)` 이다. ([1.18 이터레이터와 제너레이터](#/iterators))

```text nolines
   __enter__  ==  next(gen)          ──▶  yield 까지 실행하고 멈춤
                                          yield 의 값을 as 로 넘김

   __exit__   ==  next(gen)               <- 정상 종료
              ==  gen.throw(exc)          <- 예외 발생: yield 자리에서 raise
```

::: danger `try/finally` 없는 `@contextmanager` 는 컨텍스트 매니저가 아니다
```python
@contextmanager
def broken():
    conn = connect()
    yield conn
    conn.close()        # ❌ 본문이 예외를 내면 절대 실행 안 된다
```

`__exit__` 은 예외를 `yield` **자리로 던진다.** `try` 로 감싸지 않았으면 그 예외가 그대로 제너레이터를 뚫고 나가고, `conn.close()` 는 실행되지 않는다. **`with` 를 썼는데도 자원이 새는** 최악의 상황이다.

```python
@contextmanager
def fixed():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()    # ✅
```

`@contextmanager` 를 쓸 때 `yield` 는 **항상 `try` 안에** 있어야 한다. 예외 없다.
:::

예외를 삼키려면 잡고 빠져나오면 된다. 제너레이터가 `StopIteration` 으로 정상 종료하면 `contextlib` 이 `True` 를 반환해 준다.

```python title="삼키기"
@contextmanager
def ignore_missing():
    try:
        yield
    except FileNotFoundError:
        pass            # 그냥 빠져나오면 삼켜진다
```

### 프로토콜을 어기면 나는 오류들

```pyrepl
>>> @contextmanager
... def noyield():
...     if False: yield
...
>>> with noyield(): pass
Traceback (most recent call last):
  ...
RuntimeError: generator didn't yield

>>> @contextmanager
... def twice():
...     yield 1
...     yield 2
...
>>> with twice(): pass
Traceback (most recent call last):
  ...
RuntimeError: generator didn't stop
```

::: warn `@contextmanager` 객체는 한 번 쓰면 끝이다
```pyrepl
>>> @contextmanager
... def once():
...     yield 1
...
>>> c = once()
>>> with c as v: print(v)
1
>>> with c as v: print(v)
Traceback (most recent call last):
  ...
AttributeError: '_GeneratorContextManager' object has no attribute 'args'
```

`RuntimeError: cannot reuse` 같은 친절한 메시지를 기대했다면 실망할 것이다. CPython의 `_GeneratorContextManager.__enter__` 는 첫 줄에서 `del self.args, self.kwds, self.func` 를 한다. 재생성용 인자를 오래 붙들지 않으려는 최적화인데, 그 부작용으로 **두 번째 진입은 정체 불명의 `AttributeError` 로 터진다.**

해법은 간단하다. **`@contextmanager` 로 만든 객체를 변수에 저장해 두고 재사용하지 마라.** 매번 `with once():` 처럼 새로 호출하라.
:::

### `ContextDecorator` — 데코레이터로도 쓰인다

`@contextmanager` 가 만든 객체는 `ContextDecorator` 를 상속한다. 그래서 함수에 바로 붙일 수 있다.

```python
@timed("작업")
def work():
    sum(range(100_000))

work()
work()      # 두 번 호출해도 된다
```

방금 "재사용 불가"라고 했는데 왜 두 번 호출이 되나? `ContextDecorator.__call__` 이 호출할 때마다 `_recreate_cm()` 으로 **새 제너레이터를 만들기** 때문이다. 저장된 인자(`self.args`)가 그때 쓰인다.

::: danger 제너레이터 함수에 컨텍스트 매니저 데코레이터를 붙이면 거짓말을 한다
```python
@timed("제너레이터")
def gen():
    for i in range(3):
        time.sleep(0.05)     # 총 150ms 걸린다
        yield i

g = gen()
print(list(g))
```

```text nolines
제너레이터: 0.000s
[0, 1, 2]
```

`gen()` 호출은 **제너레이터 객체를 만들 뿐 본문을 실행하지 않는다.** 데코레이터가 감싼 것은 그 "만드는 행위"뿐이라, `with` 는 0.000초 만에 끝난다. 실제 150ms는 `list(g)` 에서 흐른다.

**`ContextDecorator` 로 제너레이터 함수를 감싸지 마라.** 계측이든 락이든 트랜잭션이든, 전부 엉뚱한 구간을 감싼다. 제너레이터 **본문 안에서** `with` 를 열어야 한다.
:::

::: perf `@contextmanager` 는 클래스 방식보다 6배 느리다
```python title="bench_cm.py"
import timeit
from contextlib import contextmanager, nullcontext

class ClassCM:
    def __enter__(self): return self
    def __exit__(self, *a): return False

@contextmanager
def GenCM():
    yield None

def use_nothing():     pass
def use_tryfinally():
    try: pass
    finally: pass
def use_class():
    with ClassCM(): pass
def use_null():
    with nullcontext(): pass
def use_gen():
    with GenCM(): pass

N = 2_000_000
for name, fn in [("아무것도 안 함", use_nothing), ("try/finally", use_tryfinally),
                 ("클래스 CM", use_class), ("nullcontext", use_null),
                 ("@contextmanager", use_gen)]:
    print(f"{name:18s} {timeit.timeit(fn, number=N) / N * 1e9:7.1f} ns")
```

| 형태 | 1회 비용 |
| --- | --- |
| 아무것도 안 함 | 12.6 ns |
| `try/finally` | 13.5 ns |
| 클래스 기반 CM | 87 ns |
| `nullcontext()` | 118 ns |
| `@contextmanager` | 530 ns |

(Python 3.14.5 / Windows, `timeit` 2,000,000회 실측. 절대값은 기기마다 다르지만 비율은 어디서나 비슷하다.)

`@contextmanager` 는 진입할 때마다 **제너레이터 프레임을 새로 만들고**, `_GeneratorContextManager` 인스턴스도 만든다. 그래서 클래스 방식의 6배다.

그런데 이 숫자를 어떻게 읽어야 하는가? **500ns는 파일 열기(수십 µs)나 락 경합에 비하면 없는 것과 같다.** 컨텍스트 매니저가 감싸는 일은 원래 비싼 일이다. 가독성을 버릴 이유가 없다.

문제가 되는 건 딱 하나다. **뜨거운 반복문 안에서 `with` 를 돌리는 경우.** 100만 번 도는 루프 안이라면 0.5초가 통째로 사라진다. 그때만 클래스 방식으로 바꾸거나, `with` 를 루프 밖으로 빼라. ([5.1 프로파일링](#/profiling))
:::

## 재진입성과 재사용성은 다른 문제다

컨텍스트 매니저를 두고 흔히 뭉뚱그려 말하는 두 성질을 갈라야 한다.

- **재사용 가능**(reusable): 같은 객체로 `with` 를 **순차적으로 여러 번** 열 수 있다.
- **재진입 가능**(reentrant): 같은 객체의 `with` 블록 **안에서 다시** 그 객체로 `with` 를 열 수 있다.

재진입 가능하면 재사용도 가능하다. 역은 성립하지 않는다.

```pyrepl
>>> from contextlib import suppress, redirect_stdout
>>> import io
>>> s = suppress(ValueError)
>>> with s:
...     with s:              # 같은 객체로 재진입
...         raise ValueError("inner")
...
>>> buf = io.StringIO()
>>> r = redirect_stdout(buf)
>>> with r:
...     print("A")
...     with r:              # 재진입 — 내부에 스택을 둔다
...         print("B")
...     print("C")
...
>>> buf.getvalue()
'A\nB\nC\n'
```

| 객체 | 재사용 | 재진입 | 이유 |
| --- | --- | --- | --- |
| `threading.Lock` | O | **X** | 재진입하면 자기 자신과 데드락 |
| `threading.RLock` | O | O | 소유 스레드와 카운트를 기록한다 |
| `suppress(...)` | O | O | 상태가 없다 |
| `redirect_stdout(f)` | O | O | 이전 대상을 리스트에 쌓는다 |
| `contextlib.chdir(p)` | O | O | 이전 경로를 리스트에 쌓는다 |
| 열린 파일 객체 | **X** | **X** | `__exit__` 이 닫아 버린다 |
| `@contextmanager` 결과 | **X** | **X** | 제너레이터는 한 번만 소진된다 |
| `ExitStack()` | O | O | `close()` 후 다시 쓸 수 있다 |

::: warn `redirect_stdout` 은 재진입 가능하지만 스레드 안전하지 않다
`sys.stdout` 은 **프로세스 전역**이다. `redirect_stdout` 은 그 전역을 바꿔치기한다. 다른 스레드가 같은 순간에 `print` 를 하면 그 출력도 함께 리다이렉트된다.

`chdir` 도 똑같다. 작업 디렉터리는 **프로세스 전역**이다. 재진입은 되지만, 멀티스레드나 `asyncio` 에서 쓰면 다른 태스크의 상대 경로가 조용히 깨진다. ([4.2 threading](#/threading))

전역 상태를 건드리는 컨텍스트 매니저는 "재진입 가능"이라는 딱지에 속지 마라. **단일 스레드 스크립트나 테스트에서만 안전하다.**
:::

## 여러 개를 한 `with` 에

콤마로 나열하면 중첩과 **정확히 같다.**

```python
with A() as a, B() as b:      # 이것은
    ...

with A() as a:                # 이것과 완전히 같다
    with B() as b:
        ...
```

`B()` 의 `__enter__` 가 예외를 던져도 `A.__exit__` 은 실행된다. 안전하다. 다만 3.10 이전에는 줄이 길어지면 괄호로 감쌀 수 없어서 백슬래시를 써야 했다. 3.10부터는 괄호가 정식 문법이다.

```python
with (
    open("in.txt", encoding="utf-8") as src,
    open("out.txt", "w", encoding="utf-8") as dst,
):
    dst.write(src.read())
```

::: warn 콤마와 튜플을 헷갈리지 마라
`with (A(), B()):` 는 3.10+ 에서는 "괄호로 묶은 두 컨텍스트 매니저"로 파싱된다. 하지만 3.8/3.9에서는 **튜플 하나**로 파싱되고, 튜플에는 `__enter__` 가 없어서 `TypeError` 가 난다.

라이브러리를 3.9까지 지원해야 한다면 이 문법을 쓰지 마라. `ruff` 의 target-version 설정이 잡아 준다. ([0.4 도구](#/tooling))
:::

## `ExitStack` — 개수를 컴파일 시점에 모를 때

`with` 의 근본적인 한계는 **정리할 자원의 개수가 소스 코드에 박혀 있어야 한다**는 것이다. 파일 3개면 3줄, N개면? 재귀나 수동 `try/finally` 로 풀 수는 있지만 끔찍하다.

```python title="N개 파일을 동시에 열어 한 줄씩 나란히 읽기"
from contextlib import ExitStack
import glob

paths = sorted(glob.glob("p*.txt"))

with ExitStack() as stack:
    files = [stack.enter_context(open(p, encoding="utf-8")) for p in paths]
    for rows in zip(*files):
        print(" | ".join(r.strip() for r in rows))

print("전부 닫혔나:", all(f.closed for f in files))
```

```text nolines
line1-a | line2-a | line3-a
line1-b | line2-b | line3-b
전부 닫혔나: True
```

`ExitStack` 은 이름 그대로 **스택**이다. `enter_context(cm)` 은 `cm.__enter__()` 를 호출하고 `cm.__exit__` 을 스택에 밀어 넣는다. `ExitStack` 자신의 `__exit__` 이 그걸 **LIFO로** 꺼내 부른다.

```text nolines
   stack.enter_context(A)   ──▶  ┌───┐
   stack.enter_context(B)   ──▶  │ C │  ──┐
   stack.enter_context(C)   ──▶  │ B │    ├──▶  __exit__ 은 C, B, A 순
                                 │ A │  ──┘
                                 └───┘
```

역순인 이유는 중첩된 `with` 와 동작을 맞추기 위해서다. 나중에 얻은 자원이 먼저 얻은 자원에 의존할 수 있으니, 푸는 것도 반대 순서여야 한다.

### 중간에서 실패해도 이미 연 것은 닫힌다

```python title="partial.py"
class Bad:
    def __enter__(self): raise OSError("열기 실패")
    def __exit__(self, *a): return False

try:
    with ExitStack() as stack:
        stack.enter_context(R(0))
        stack.enter_context(R(1))
        stack.enter_context(Bad())      # 여기서 터진다
except OSError as e:
    print("OSError:", e)
```

```text nolines
open 0
open 1
close 1
close 0
OSError: 열기 실패
```

`ExitStack` 을 손으로 짠 `try/finally` 로 대체하려 할 때 사람들이 가장 많이 틀리는 지점이 바로 이거다.

### `callback` — `__exit__` 이 없는 것도 태운다

정리가 그냥 함수 호출이면 컨텍스트 매니저를 만들 필요가 없다.

```python
with ExitStack() as stack:
    tmp = tempfile.mkdtemp()
    stack.callback(shutil.rmtree, tmp)      # 나갈 때 rmtree(tmp)

    handle = acquire_gpu()
    stack.callback(release_gpu, handle)
    ...
```

`callback(fn, *args, **kwargs)` 은 나갈 때 `fn(*args, **kwargs)` 를 부른다. **반환값은 무시되므로 예외를 삼킬 수 없다.** 이 점에서 `callback` 은 `enter_context` 보다 안전하다.

### `pop_all` — 성공했을 때만 정리를 넘긴다

이게 `ExitStack` 의 가장 영리한 기능이고, 가장 덜 알려진 기능이다. **초기화 중에 실패하면 롤백하고, 성공하면 정리 책임을 호출자에게 넘기는** 패턴이다.

```python title="pop_all.py"
def make_pipeline():
    with ExitStack() as stack:
        src = stack.enter_context(open("in.txt", encoding="utf-8"))
        dst = stack.enter_context(open("out.txt", "w", encoding="utf-8"))
        validate(src)                    # 여기서 터지면 둘 다 닫힌다
        return src, dst, stack.pop_all() # 성공하면 정리를 미룬다

src, dst, cleanup = make_pipeline()
try:
    ...
finally:
    cleanup.close()
```

`pop_all()` 은 콜백 전부를 **새 `ExitStack` 으로 옮기고** 원래 스택을 비운다. 원래 스택이 `with` 를 빠져나올 때 할 일이 없으니 아무것도 닫히지 않는다. `__init__` 이 여러 자원을 잡아야 하는 클래스에서 특히 유용하다.

### 예외 체인을 보존한다

`__exit__` 이 여러 개 연달아 터지면 `ExitStack` 은 손으로 `__context__` 를 엮어 준다.

```pyrepl
>>> try:
...     with ExitStack() as st:
...         st.enter_context(Boom(1))
...         st.enter_context(Boom(2))
...         raise ValueError("본문")
... except BaseException as e:
...     cur = e
...     while cur is not None:
...         print(repr(cur)); cur = cur.__context__
...
RuntimeError('정리 실패 1')
RuntimeError('정리 실패 2')
ValueError('본문')
```

원본 `ValueError` 가 체인 끝에 살아 있다. `contextlib` 소스의 `_fix_exception_context` 가 이걸 위해 존재한다. 손으로 짠 `try/finally` 중첩으로는 얻기 어려운 품질이다.

::: cote 코딩테스트에서 `ExitStack` 을 쓸 일은 거의 없다
컨텍스트 매니저 자체가 코딩테스트의 주제가 되는 일은 없다. 다만 실전에서 하나는 유용하다.

```python
import sys
from contextlib import redirect_stdout
import io

# 로컬에서 여러 테스트케이스를 돌릴 때 출력만 가로채기
buf = io.StringIO()
with redirect_stdout(buf):
    solve()
print(buf.getvalue() == expected)
```

그리고 `with open(...)` 은 습관으로 굳혀라. 채점 서버에서 파일을 안 닫아 감점되는 일은 없지만, `sys.stdin` 을 다루는 [8.2 입출력 최적화](#/io-optimize)에서 파일 객체의 수명이 실제로 문제가 된다.
:::

## `contextlib` 의 나머지 도구들

### `suppress` — `try/except/pass` 를 한 줄로

```python
# ❌ 4줄, 그리고 pass 가 눈에 안 띈다
try:
    os.remove(path)
except FileNotFoundError:
    pass

# ✅ 의도가 이름에 있다
with suppress(FileNotFoundError):
    os.remove(path)
```

`suppress` 는 **블록을 재개하지 않는다.** 예외가 난 지점에서 `with` 블록 전체를 빠져나온다.

```pyrepl
>>> with suppress(ValueError):
...     print("1")
...     raise ValueError
...     print("2 — 절대 실행 안 됨")
...
1
```

그래서 `with suppress(...)` 로 감싸는 블록은 **짧아야 한다.** 여러 문장을 감싸면 어디까지 실행됐는지 알 수 없는 코드가 된다.

::: deep 3.12부터 `suppress` 는 `ExceptionGroup` 안까지 들어간다
```pyrepl
>>> try:
...     with suppress(ValueError):
...         raise ExceptionGroup("g", [ValueError("v"), TypeError("t")])
... except ExceptionGroup as eg:
...     print(eg.exceptions)
...
(TypeError('t'),)
```

`ValueError` 만 그룹에서 **떼어내고** 나머지를 다시 던진다. `except*` 와 같은 규칙이다([1.16 예외](#/exceptions)). 지정한 타입이 그룹을 전부 덮으면 그룹째 사라진다.

이건 `try/except ValueError: pass` 로는 절대 흉내 낼 수 없는 동작이다. `asyncio.TaskGroup` 이 `ExceptionGroup` 을 던지는 시대([4.7 asyncio 실전](#/asyncio-advanced))에는 이 차이가 실제로 중요해진다.
:::

### `closing` — `close()` 는 있는데 `with` 를 모르는 객체

```python
from contextlib import closing
from urllib.request import urlopen

with closing(urlopen(url)) as page:
    data = page.read()
```

구현은 다섯 줄이다. `__exit__` 에서 `self.thing.close()` 를 부를 뿐이다. 오래된 라이브러리나 직접 만든 리소스 클래스에 쓴다.

::: note `with conn:` 이 연결을 닫는다고 착각하지 마라
```pyrepl
>>> import sqlite3
>>> conn = sqlite3.connect(":memory:")
>>> with conn:
...     conn.execute("CREATE TABLE t (x)")
...
<sqlite3.Cursor object at 0x...>
>>> conn.execute("SELECT 1")      # 아직 살아 있다!
<sqlite3.Cursor object at 0x...>
```

`sqlite3.Connection` 의 `with` 는 **트랜잭션**이다. 성공하면 커밋, 예외면 롤백. 연결은 그대로 열려 있다. 닫으려면 `with closing(conn):` 을 한 겹 더 씌우거나 `conn.close()` 를 직접 불러야 한다.

`with` 가 무엇을 정리하는지는 **객체마다 다르다.** 문서를 읽어라. `threading.Lock.__enter__` 가 `self` 가 아니라 `True` 를 반환하는 것도 같은 종류의 놀라움이다.

```pyrepl
>>> import threading
>>> lk = threading.Lock()
>>> with lk as x:
...     print(repr(x))
...
True
```
:::

### `nullcontext` — 조건부 `with`

```python
def process(path, verbose=False):
    with open(path) if path else nullcontext(sys.stdin) as f:
        ...
```

"어떤 때는 컨텍스트 매니저, 어떤 때는 그냥 객체"인 상황에서 코드가 두 갈래로 갈라지는 걸 막는다. `nullcontext(x)` 의 `__enter__` 는 `x` 를 반환하고 `__exit__` 은 아무것도 안 한다.

### `AbstractContextManager` — 프로토콜 확인

```pyrepl
>>> from contextlib import AbstractContextManager
>>> class Mine:
...     def __enter__(self): return self
...     def __exit__(self, *a): return False
...
>>> isinstance(Mine(), AbstractContextManager)     # 상속 안 했는데도
True
>>> issubclass(int, AbstractContextManager)
False
```

`__subclasshook__` 이 `__enter__`/`__exit__` 의 존재만 보는 구조적 검사다([1.15 프로토콜](#/protocols)). 상속하면 `__enter__` 기본 구현(`return self`)을 공짜로 얻는다.

## 요약

- `with EXPR as VAR:` 는 `type(mgr).__exit__` 를 **먼저** 찾아 두고 `type(mgr).__enter__(mgr)` 를 부른다. 특수 메서드라 **타입에서만** 찾는다 — 인스턴스 속성도 `__getattr__` 도 통하지 않는다.
- `__exit__` 의 반환값에는 `TO_BOOL` 이 걸린다. `True` 만이 아니라 **모든 참인 값**이 예외를 삼킨다. `BaseException` 도 삼킨다. 삼킬 의도가 없으면 아무것도 반환하지 마라.
- `__del__` 은 정리 전략이 아니다. CPython 전용이고, 순환 참조에서 지연되고, **예외가 났을 때 트레이스백이 프레임을 붙잡아 가장 늦게 실행된다.**
- `@contextmanager` 의 `yield` 는 **반드시 `try` 안**에 있어야 한다. 밖에 있으면 `with` 를 썼는데도 자원이 샌다.
- `@contextmanager` 로 만든 객체는 재사용 불가다. 두 번 진입하면 `AttributeError` 로 터진다. 데코레이터로 쓸 때만 `_recreate_cm` 이 살려 준다 — 단 **제너레이터 함수에 붙이면 엉뚱한 구간을 잰다.**
- 정리할 개수가 **런타임에 정해지면 `ExitStack`**. `enter_context`, `callback`, `pop_all` 셋을 기억하라. 중간 실패 시 부분 롤백과 예외 체인 보존을 공짜로 준다.
- `@contextmanager` 는 클래스 방식의 약 6배(530ns vs 87ns)지만, 뜨거운 루프가 아니면 신경 쓸 값이 아니다.

::: quiz 연습문제
1. 다음 코드의 출력을 예측하고 실행해서 확인하라. 세 개 중 몇 개가 예외를 삼키는가?

   ```python
   class CM:
       def __init__(self, r): self.r = r
       def __enter__(self): return self
       def __exit__(self, *a): return self.r

   for r in (0.0, "0", [0]):
       try:
           with CM(r): raise ValueError
           print(f"{r!r}: 삼킴")
       except ValueError:
           print(f"{r!r}: 전파")
   ```

2. 아래 컨텍스트 매니저에는 **서로 다른 버그가 두 개** 있다. 각각 찾아 고쳐라.

   ```python
   @contextmanager
   def transaction(conn):
       conn.execute("BEGIN")
       yield conn
       conn.execute("COMMIT")
   ```

3. 다음이 왜 `TypeError` 를 내는지, 그리고 `p.__enter__` 는 왜 정상적으로 보이는지 설명하라.

   ```python
   class Proxy:
       def __init__(self, t): self._t = t
       def __getattr__(self, n): return getattr(self._t, n)

   with Proxy(open("f")) as f:
       pass
   ```

4. `ExitStack` 없이 다음을 구현해 보라. `paths` 의 파일을 **전부** 열고, 중간에 하나라도 실패하면 **이미 연 것을 역순으로 닫고** 예외를 전파해야 한다. 다 짜고 나서 `ExitStack` 버전과 줄 수를 비교하라.

5. **깊이 생각해 볼 문제.** 다음 두 함수의 차이를 설명하라. 어느 쪽이 옳은가? 왜 파이썬은 두 번째를 막지 않는가?

   ```python
   @contextmanager
   def a():
       try:
           yield
       except Exception:
           return          # 삼킨다

   @contextmanager
   def b():
       try:
           yield
       finally:
           pass            # 안 삼킨다
   ```
:::

**다음 절**: [1.18 이터레이터와 제너레이터](#/iterators) — `@contextmanager` 를 떠받치는 `yield` 가 실제로 무엇인지, 그리고 `gen.throw()` 는 어떻게 `yield` 자리에서 예외를 일으키는지.
