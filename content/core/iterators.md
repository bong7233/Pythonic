# 1.18 이터레이터와 제너레이터

::: lead
`for x in something` 을 수천 번 썼을 것이다. 그런데 저 한 줄이 실제로 무슨 함수를 호출하는지 설명할 수 있나. 이 절은 파이썬에서 가장 널리 쓰이면서 가장 덜 이해된 프로토콜을 뜯는다. 이터레이터 프로토콜은 `for` 문, 컴프리헨션, `zip`, `sum`, 언패킹, `in` 연산자, 그리고 **`async`/`await` 전체**가 서 있는 토대다. 여기를 넘기면 [4.6 asyncio 기초](#/asyncio-basics)의 코루틴이 마법이 아니라 이 절에서 배운 `send()` 의 다른 이름이라는 게 보인다.
:::

## 문제부터: 1억 줄짜리 로그

로그 파일에서 에러 줄 수를 세야 한다. 이렇게 쓴다.

```python
lines = open("app.log").readlines()      # ❌
errors = [ln for ln in lines if "ERROR" in ln]
print(len(errors))
```

파일이 8GB면 이 코드는 죽는다. `readlines()` 가 전부를 메모리에 올리기 때문이다. 크기를 재 보자.

```pyrepl
>>> import sys
>>> sys.getsizeof(list(range(1_000_000)))
8000056
>>> sys.getsizeof(range(1_000_000))
48
```

100만 개 정수를 **리스트**로 들고 있으면 8MB다. 원소가 가리키는 int 객체는 여기 포함도 안 됐다. 그런데 `range` 는 **48바이트**다. 100만이든 1조든 48바이트다.

`range` 는 값을 저장하지 않는다. **시작·끝·간격만 기억하고 필요할 때 계산한다.** 이게 이 절의 주제인 **게으름**(laziness)이다. 그리고 파이썬은 이 게으름을 아무나 구현할 수 있게 프로토콜로 열어 뒀다.

## 이터러블과 이터레이터는 다른 것이다

이 둘을 뭉개면 이 절의 나머지가 전부 안 보인다.

| | 이터러블(iterable) | 이터레이터(iterator) |
| --- | --- | --- |
| 가진 메서드 | `__iter__` | `__iter__` **그리고** `__next__` |
| 하는 일 | *"나를 훑을 이터레이터를 줄게"* | *"다음 값 하나를 줄게"* |
| 상태 | 보통 없음 | **커서를 들고 있다** |
| 재사용 | 여러 번 훑을 수 있다 | **한 번 쓰면 끝** |
| 예 | `list`, `str`, `dict`, `range` | `list_iterator`, 제너레이터, 파일 객체 |

```pyrepl
>>> lst = [1, 2, 3]
>>> it = iter(lst)
>>> type(it)
<class 'list_iterator'>
>>> next(it)
1
>>> next(it)
2
>>> next(it)
3
>>> next(it)
Traceback (most recent call last):
  ...
StopIteration
```

리스트 자체는 `__next__` 가 없다. 커서를 안 들고 있다는 뜻이다. 그래서 리스트는 **몇 번이든** 훑을 수 있다. `iter()` 를 호출할 때마다 커서를 하나씩 새로 만들어 주기 때문이다.

```text nolines
   lst ──▶ ┌─────────────┐
           │ [1, 2, 3]   │◀───┐
           └─────────────┘    │
                              │  each iter(lst) makes a fresh cursor
   it1 ──▶ ┌──────────────┐   │
           │ list_iterator│───┤       <- 이터레이터는 원본 + 인덱스만 들고 있다
           │ index: 2     │   │
           └──────────────┘   │
   it2 ──▶ ┌──────────────┐   │
           │ list_iterator│───┘
           │ index: 0     │
           └──────────────┘
```

그래서 이터레이터는 원본 크기와 무관하게 작다.

```pyrepl
>>> import sys
>>> sys.getsizeof(iter(list(range(1_000_000))))
48
```

100만 원소 리스트의 이터레이터가 48바이트다. **원본을 가리키는 포인터 하나 + 인덱스 하나**가 전부이기 때문이다. 이터레이터는 복사하지 않는다.

### 이터레이터는 왜 자기 자신을 반환하는가

프로토콜의 두 번째 규칙이 이상해 보인다. **이터레이터는 `__iter__` 도 가져야 하고, 그것은 `self` 를 반환해야 한다.**

```pyrepl
>>> it = iter([1, 2, 3])
>>> iter(it) is it
True
>>> iter([1, 2, 3]) is [1, 2, 3]
False
```

::: deep 왜 이런 규칙을 뒀나
`for` 문은 받은 대상에 무조건 `iter()` 를 호출한다. 이터러블을 받았는지 이터레이터를 받았는지 신경 쓰지 않기 위해서다.

```python
def my_sum(iterable):
    it = iter(iterable)        # 리스트든 제너레이터든 여기서 통일된다
    ...
```

만약 이터레이터가 `__iter__` 를 안 가지면 `for x in some_generator:` 가 에러가 난다. 그래서 **"이터레이터도 이터러블이다"** 라는 규칙을 뒀고, `iter(it) is it` 은 그 규칙의 필연적 결과다.

대가가 있다. **이터레이터에 `for` 를 두 번 돌리면 두 번째는 빈다.** 프로토콜이 통일된 값으로 치른 비용이다. 이 절 뒤쪽의 **소진의 함정**이 전부 여기서 나온다.
:::

## `for` 문이 실제로 하는 일

`for` 는 문법 설탕이다. 벗겨 보자.

```python
for x in data:
    body(x)
```

이건 정확히 아래와 같다.

```python title="for 문의 디슈가링 (개념적으로 동등한 코드)"
_it = iter(data)              # ① 이터레이터를 얻는다
while True:
    try:
        x = next(_it)         # ② 다음 값
    except StopIteration:     # ③ 끝나면 조용히 빠져나온다
        break
    body(x)
```

세 줄로 요약하면 이렇다.

1. `iter(data)` — `data.__iter__()` 를 호출한다.
2. `next(_it)` — `_it.__next__()` 를 호출한다.
3. `StopIteration` 이 나오면 **예외를 잡아서 정상 종료로 바꾼다.**

3번이 핵심이다. **`StopIteration` 은 에러가 아니다.** *"값이 더 없다"* 를 알리는 신호이고, `for` 문이 그걸 잡아 준다. 그래서 `for` 안에서 `StopIteration` 을 본 적이 없는 것이다.

바이트코드를 보면 실제로 그렇게 되어 있다.

```pyrepl
>>> import dis
>>> dis.dis("for x in data: body(x)")
  0           RESUME                   0

  1           LOAD_NAME                0 (data)
              GET_ITER
      L1:     FOR_ITER                11 (to L2)
              STORE_NAME               1 (x)
              LOAD_NAME                2 (body)
              PUSH_NULL
              LOAD_NAME                1 (x)
              CALL                     1
              POP_TOP
              JUMP_BACKWARD           13 (to L1)
      L2:     END_FOR
              POP_ITER
              LOAD_CONST               0 (None)
              RETURN_VALUE
```

`GET_ITER` 가 `iter()` 고, `FOR_ITER` 가 `next()` + `StopIteration` 처리를 **한 개의 옵코드 안에서** 한다. 그래서 `for` 문은 손으로 쓴 `while` + `try` 보다 빠르다. 예외 객체를 만들고 던지고 잡는 과정을 인터프리터 루프 안에서 우회하기 때문이다.

뒤의 `END_FOR` 와 `POP_ITER` 는 소진된 이터레이터를 스택에서 걷어내는 뒷정리다. 3.11까지는 `FOR_ITER` 하나가 다 했는데, 스택 상태를 예측 가능하게 만들어 특수화 인터프리터([3.7 바이트코드](#/bytecode))가 최적화하기 좋도록 쪼갠 결과다. **옵코드 이름은 버전마다 바뀐다. 의미는 안 바뀐다.**

### 프로토콜을 직접 구현해 보면 확실해진다

```python title="이터레이터 클래스 — 원리를 보기 위한 것. 실무에서는 이렇게 안 쓴다"
class Countdown:
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return self          # 나는 이터레이터다

    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


print(list(Countdown(3)))    # [3, 2, 1]
```

동작한다. 그런데 여기에 **버그가 숨어 있다.**

::: danger `__iter__` 가 self 를 반환하는 클래스는 중첩 루프에서 깨진다
```python
class Bad:
    def __init__(self, data):
        self.data = data
        self.i = 0

    def __iter__(self):
        return self                  # ❌ 커서를 하나만 갖는다

    def __next__(self):
        if self.i >= len(self.data):
            raise StopIteration
        self.i += 1
        return self.data[self.i - 1]
```

```pyrepl
>>> b = Bad([1, 2, 3])
>>> [(x, y) for x in b for y in b]
[(1, 2), (1, 3)]
```

`[(1,1), (1,2), ..., (3,3)]` 9개를 기대했는데 2개가 나왔다. 바깥 루프와 안쪽 루프가 **같은 커서를 공유**하기 때문이다. 바깥이 1을 꺼내고, 안쪽이 2와 3을 다 써 버리고, 바깥은 다음 값이 없어 끝난다.

`list` 는 이 문제가 없다. `list.__iter__` 는 `self` 가 아니라 **새 `list_iterator` 를 만들어** 반환하기 때문이다.

**규칙**: 컬렉션 클래스를 만들 때 `__iter__` 에서 `self` 를 반환하지 마라. 매번 새 이터레이터를 반환하라. 제너레이터를 쓰면 공짜로 해결된다.

```python
class Squares:
    def __init__(self, n):
        self.n = n

    def __iter__(self):              # ✅ 호출될 때마다 새 제너레이터 객체
        for i in range(self.n):
            yield i * i
```

```pyrepl
>>> s = Squares(4)
>>> list(s)
[0, 1, 4, 9]
>>> list(s)
[0, 1, 4, 9]
>>> [(a, b) for a in Squares(2) for b in Squares(2)]
[(0, 0), (0, 1), (1, 0), (1, 1)]
```
:::

### 잊혀진 옛 프로토콜

`__iter__` 가 없어도 `for` 가 도는 객체가 있다. 파이썬 2.1 이전의 유물이다.

```pyrepl
>>> class Old:
...     def __getitem__(self, i):
...         if i > 3:
...             raise IndexError
...         return i * 10
...
>>> list(Old())
[0, 10, 20, 30]
>>> hasattr(Old(), "__iter__")
False
```

`iter()` 는 `__iter__` 가 없으면 `__getitem__` 을 `0, 1, 2, ...` 로 호출하다가 `IndexError` 가 나면 멈추는 이터레이터를 자동으로 만들어 준다.

::: warn 이 폴백은 isinstance 검사를 통과하지 못한다
```pyrepl
>>> from collections.abc import Iterable
>>> isinstance(Old(), Iterable)
False
```

`for` 는 돌지만 `Iterable` 은 아니다. `collections.abc.Iterable` 의 `__subclasshook__` 은 `__iter__` 만 보기 때문이다. **"`isinstance(x, Iterable)` 로 순회 가능 여부를 판단"** 하는 코드는 이 경우에 틀린다. 확실히 알려면 `iter(x)` 를 `try` 로 감싸는 수밖에 없다. 자세한 건 [1.15 프로토콜](#/protocols)에서.
:::

### `iter()` 의 두 번째 얼굴

`iter()` 에 인자를 두 개 주면 완전히 다른 물건이 나온다.

```pyrepl
>>> import io
>>> buf = io.StringIO("a\nb\nc\n")
>>> list(iter(buf.readline, ""))
['a\n', 'b\n', 'c\n']
```

`iter(callable, sentinel)` 은 *"인자 없이 `callable()` 을 계속 부르다가 결과가 `sentinel` 과 같아지면 멈춘다"* 는 이터레이터다. 블록 단위 파일 읽기의 표준 관용구다.

```python
with open("big.bin", "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        process(chunk)
```

## 제너레이터: 상태를 보존하는 함수

위의 `Countdown` 클래스를 제너레이터로 다시 쓰면 이렇다.

```python
def countdown(n):
    while n > 0:
        yield n
        n -= 1
```

클래스 8줄이 3줄이 됐다. `__iter__`, `__next__`, `StopIteration`, 인스턴스 변수로 상태 관리 — 전부 사라졌다. **파이썬이 대신 해 준다.**

### `yield` 가 함수를 바꿔 버린다

이게 핵심이다. 함수 몸통 어디에든 `yield` 가 하나라도 있으면 **컴파일 시점에** 그 함수는 다른 종류가 된다.

```pyrepl
>>> import inspect
>>> def countdown(n):
...     while n > 0:
...         yield n
...         n -= 1
...
>>> bool(countdown.__code__.co_flags & inspect.CO_GENERATOR)
True
>>> countdown(3)
<generator object countdown at 0x000001F2C4A66D40>
```

**`countdown(3)` 은 몸통을 한 줄도 실행하지 않는다.** 제너레이터 객체 하나를 만들고 즉시 반환한다. 이걸 직접 볼 수 있다.

```pyrepl
>>> def noisy():
...     print("여기 실행됨!")
...     yield 1
...
>>> g = noisy()          # 아무것도 안 찍힌다
>>> next(g)
여기 실행됨!
1
```

바이트코드가 이유를 말해 준다.

```pyrepl
>>> import dis
>>> def g():
...     yield 1
...
>>> dis.dis(g)
   1           RETURN_GENERATOR
               POP_TOP
       L1:     RESUME                   0

   2           LOAD_SMALL_INT           1
               YIELD_VALUE              0
               RESUME                   5
               POP_TOP
               LOAD_CONST               1 (None)
               RETURN_VALUE

  --   L2:     CALL_INTRINSIC_1         3 (INTRINSIC_STOPITERATION_ERROR)
               RERAISE                  1
```

첫 옵코드가 `RETURN_GENERATOR` 다. 함수를 부르면 **첫 명령에서 바로 제너레이터를 반환하고 끝난다.** 몸통 코드는 `next()` 가 불릴 때 `RESUME` 지점부터 실행된다.

::: deep 제너레이터 객체 안에는 프레임이 통째로 들어 있다
보통 함수는 호출이 끝나면 프레임(지역 변수 + 실행 위치)이 사라진다. 제너레이터는 **그 프레임을 자기 안에 붙들고 있다.** 그래서 `yield` 에서 멈췄다가 다시 그 자리에서 이어갈 수 있는 것이다.

```pyrepl
>>> import sys
>>> def g0(): yield 1
...
>>> def g5():
...     a = b = c = d = e = 1
...     yield 1
...
>>> sys.getsizeof(g0())
184
>>> sys.getsizeof(g5())
224
```

지역 변수 5개를 늘렸더니 정확히 40바이트가 늘었다. **지역 변수 하나당 8바이트** — 포인터 하나 크기다. 제너레이터 객체 크기는 `co_nlocals` 에 선형으로 비례한다.

`inspect` 로 상태를 볼 수 있다.

```pyrepl
>>> import inspect
>>> def g():
...     yield 1
...     yield 2
...
>>> it = g()
>>> inspect.getgeneratorstate(it)
'GEN_CREATED'
>>> next(it)
1
>>> inspect.getgeneratorstate(it)
'GEN_SUSPENDED'
>>> list(it)
[2]
>>> inspect.getgeneratorstate(it)
'GEN_CLOSED'
>>> it.gi_frame
```

마지막 줄이 `None` 을 반환한다(REPL은 `None` 을 안 찍는다). **소진된 제너레이터는 프레임을 놓아준다.** 그래서 다 쓴 제너레이터를 붙들고 있어도 메모리 누수는 안 난다 — 껍데기 184바이트만 남는다.

```text nolines
   g = countdown(3)

   ┌────────────────────────┐
   │ generator object       │
   │  gi_frame ─────────────┼──▶ ┌──────────────────┐
   │  gi_code               │    │ frame            │
   │  gi_running: False     │    │  locals: n = 3   │  <- 지역 변수가 여기 산다
   └────────────────────────┘    │  lasti: 12       │  <- 어디서 멈췄는지
                                 └──────────────────┘
   next(g) -> lasti 부터 재개, yield 만나면 다시 멈춤
   소진 -> gi_frame = None (프레임 해제)
```
:::

### `StopIteration` 은 제너레이터의 `return` 이다

제너레이터가 `return` 을 만나면 `StopIteration` 이 나는데, **반환값이 예외에 실려 온다.**

```pyrepl
>>> def g():
...     yield 1
...     return "done"
...
>>> it = g()
>>> next(it)
1
>>> try:
...     next(it)
... except StopIteration as e:
...     print("value =", e.value)
...
value = done
```

`for` 문은 이 값을 **버린다.** 꺼낼 수 있는 건 `yield from` 뿐이다. 곧 본다.

::: danger PEP 479 — 제너레이터 안에서 새는 StopIteration
제너레이터 안에서 `next()` 를 직접 부르면 사고가 난다.

```python
def g():
    it = iter([1])
    while True:
        yield next(it)          # ❌ it이 소진되면 StopIteration이 밖으로 샌다
```

3.6 이전에는 이게 **조용히 루프를 끝냈다.** `next(it)` 이 던진 `StopIteration` 이 제너레이터를 통과해 나가서 `for` 문에게 *"끝났다"* 로 읽혔기 때문이다. 버그가 정상 종료로 위장하는 최악의 형태다.

지금은 잡힌다.

```pyrepl
>>> list(g())
Traceback (most recent call last):
  ...
RuntimeError: generator raised StopIteration
```

이 변환이 바로 위 바이트코드에 보이던 `CALL_INTRINSIC_1 (INTRINSIC_STOPITERATION_ERROR)` 다. 제너레이터 프레임 전체를 감싸는 예외 테이블 핸들러가 새어 나가는 `StopIteration` 을 `RuntimeError` 로 바꿔 준다. 원래 예외는 `__cause__` 에 남는다([1.16 예외](#/exceptions)).

**교훈**: 제너레이터 안에서 `next()` 를 쓰려면 반드시 `try/except StopIteration` 으로 감싸거나 `next(it, default)` 를 써라.
:::

## 게으름의 값 — 실측

::: perf 게으름이 이기는 두 지점 — 실측
### 메모리: 38MB vs 0.5KB

```python title="lazy_mem.py"
import tracemalloc

tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
data = [i * i for i in range(1_000_000)]        # 리스트 컴프리헨션
peak_list = tracemalloc.get_traced_memory()[1] - base
del data
tracemalloc.stop()

tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
total = sum(i * i for i in range(1_000_000))    # 제너레이터 표현식
peak_gen = tracemalloc.get_traced_memory()[1] - base
tracemalloc.stop()

print(f"list comp peak: {peak_list / 1024 / 1024:.2f} MB")
print(f"genexp   peak: {peak_gen / 1024:.2f} KB")
```

```text nolines
list comp peak: 38.57 MB
genexp   peak: 0.47 KB
```

**8만 배 차이다.** 리스트는 100만 개 int 객체 + 포인터 배열을 전부 들고 있어야 하고, 제너레이터는 한 번에 한 개만 살아 있다.

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

### 조기 종료: 18.9ms vs 0.36µs

게으름의 두 번째 이득은 **안 만드는 것**이다.

```python
import timeit

setup = "data = list(range(1_000_000))"
t1 = timeit.timeit("any([x > 10 for x in data])", setup, number=100) / 100
t2 = timeit.timeit("any(x > 10 for x in data)", setup, number=100) / 100
print(f"list comp: {t1 * 1000:.3f} ms")
print(f"genexp   : {t2 * 1e6:.3f} us")
```

```text nolines
list comp: 18.867 ms
genexp   : 0.359 us
```

**5만 배.** `any()` 는 첫 참에서 멈춘다. 제너레이터는 12번째 원소에서 끝나지만, 리스트 컴프리헨션은 **`any()` 가 호출되기도 전에** 100만 개를 전부 만든다. 대괄호 두 개의 차이다.

`any`, `all`, `next`, `in`, `zip` — 조기 종료하는 모든 함수에 대괄호를 넣지 마라.
:::

::: perf 그런데 게으름은 공짜가 아니다
전부 소비할 거라면 제너레이터가 **더 느리다.**

```python
import timeit

t1 = timeit.timeit("sum([i*i for i in range(1000)])", number=10000)
t2 = timeit.timeit("sum(i*i for i in range(1000))", number=10000)
print(f"listcomp {t1:.3f}")
print(f"genexp   {t2:.3f}")
```

```text nolines
listcomp 0.208 ~ 0.242
genexp   0.233 ~ 0.249
```

genexp가 listcomp보다 느리긴 한데, **정확한 퍼센트를 못 박기엔 노이즈가 크다.** 6회 연속 재실행에서 비율은 0.99배 ~ 1.15배 사이를 오갔다 — 방향(genexp가 느리다)은 매번 같았지만 "8% 느리다" 같은 한 자리 숫자는 재현되지 않았다. 반복 횟수가 낮고(1000개) 원소당 오버헤드 차이가 절대시간으로 작을 때는 이런 흔들림이 정상이다.

`sum(range(100000))` 처럼 원소 수를 늘리면 이 노이즈를 덮을 만큼 차이가 커진다.

| 방식 | 시간(20회) | 배수 |
| --- | --- | --- |
| `sum(range(100000))` | 0.0099s | 1.0x |
| `sum(i for i in range(100000))` | 0.0349s | 3.5x |
| 손으로 쓴 `while` 제너레이터 | 0.0538s | 5.5x |

(Python 3.14.5 / Windows, 4회 반복 실측. genexp 배수는 3.4x~3.7x, while 제너레이터는 4.9x~6.2x 사이에서 흔들렸다. 위 표는 그 중 대표값이고, "몇 배"는 실행마다 바뀌어도 "listcomp < genexp < while제너레이터" 순서와 "3~6배대"라는 자릿수는 매번 같았다.)

이유는 **재개 비용**이다. 값 하나마다 인터프리터가 제너레이터 프레임을 스택에 올리고, `RESUME` 하고, `yield` 에서 다시 내려온다. C로 구현된 `range_iterator` 는 그 왕복이 없다.

**결론**: 게으름은 *"전부 필요하지 않거나"* *"전부 담을 수 없을 때"* 이긴다. 둘 다 아니면 진다. 제너레이터는 최적화 기법이 아니라 **메모리와 CPU를 바꾸는 거래**다.
:::

::: cote 코딩테스트에서 언제 제너레이터를 쓰나
게으름은 코테에서 **메모리 초과를 막지만 시간 초과를 만들 수 있다.**

```python
# ✅ 입력 파싱 — 값을 두 번 안 쓴다면 게으르게
import sys
data = map(int, sys.stdin.read().split())

# ✅ 조기 탈출
if any(check(x) for x in candidates):
    ...

# ❌ 뜨거운 이중 루프 안 — 제너레이터 재개 비용이 매번 붙는다
for i in range(n):
    total = sum(grid[i][j] for j in range(m))     # 느리다
    total = sum(grid[i])                          # C 레벨. 이게 낫다
```

경험칙 세 가지.

1. **`sum`/`min`/`max` 에 넘길 게 이미 리스트면 그냥 리스트를 넘겨라.** 제너레이터로 감싸면 손해다.
2. **`map`/`filter`/`zip` 은 3부터 게으르다.** `list()` 로 감싸는 순간 이득이 사라진다. 인덱싱이 필요할 때만 감싸라.
3. **`map` 을 두 번 순회하면 두 번째는 빈다.** 아래 **소진의 함정**을 반드시 읽어라. 시험장에서 이걸로 30분을 날린다.
:::

## `yield from` — 위임

중첩 구조를 평탄화한다고 하자. 이렇게 쓴다.

```python
def flatten(x):
    if isinstance(x, (list, tuple)):
        for item in x:
            for sub in flatten(item):     # 손으로 되풀이
                yield sub
    else:
        yield x
```

`yield from` 은 저 두 줄을 한 줄로 만든다.

```python title="flatten.py"
def flatten(x):
    if isinstance(x, (list, tuple)):
        for item in x:
            yield from flatten(item)      # 위임
    else:
        yield x


print(list(flatten([1, [2, [3, [4, [5]]]], 6])))    # [1, 2, 3, 4, 5, 6]
```

트리 순회에서 진가가 나온다.

```python title="tree.py"
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

    def __iter__(self):
        yield self.value
        for child in self.children:
            yield from child          # 자식 노드에게 통째로 위임


tree = Node(1, [Node(2, [Node(4), Node(5)]), Node(3)])
print(list(tree))                     # [1, 2, 4, 5, 3]
```

전위 순회가 4줄이다. 재귀 호출 결과를 리스트로 모아 `+` 로 합치는 코드와 비교해 보라. **중간 리스트가 하나도 안 만들어진다.**

### `yield from` 은 축약이 아니다

`yield from g` 를 `for x in g: yield x` 의 축약이라고 설명하는 글이 많다. **틀렸다.** [PEP 380](https://peps.python.org/pep-0380/)이 정의한 완전한 형태는 이 네 가지를 더 한다.

1. **반환값을 꺼내 준다.** `for` 루프 버전은 `StopIteration.value` 를 버린다.
2. **`send()` 를 안쪽 제너레이터까지 전달한다.**
3. **`throw()` 를 안쪽으로 던진다.**
4. **`close()` 를 안쪽까지 전파한다.**

1번을 보자.

```pyrepl
>>> def g():
...     yield 1
...     return "done"
...
>>> def outer():
...     r = yield from g()
...     print("yield from gave:", r)
...     yield 99
...
>>> list(outer())
yield from gave: done
[1, 99]
```

`yield from` 은 **값을 내는 동시에 값을 받는 표현식**이다. `for` 루프로는 이걸 흉내 낼 수 없다. 그리고 이 반환값 통로가 바로 `await` 가 결과를 받아오는 메커니즘이다. 곧 본다.

::: perf yield from 은 얼마나 빠른가 — 통념보다 덜 빠르다
깊이 $d$ 로 위임을 중첩하고 원소 10,000개를 흘려 보냈다.

| 깊이 | `for x in g: yield x` | `yield from g` | 배수 |
| --- | --- | --- | --- |
| 1 | 0.0023s | 0.0021s | 1.09x |
| 5 | 0.0049s | 0.0042s | 1.16x |
| 20 | 0.0178s | 0.0131s | 1.36x |
| 50 | 0.0396s | 0.0270s | 1.47x |

(Python 3.14.5 / Windows, `timeit` number=10 실측)

*"`yield from` 은 중간 프레임을 건너뛰므로 훨씬 빠르다"* 는 흔한 설명이 있는데, 실측은 **깊이 50에서도 1.4배 안팎**이다. CPython은 위임 체인을 여전히 프레임 하나씩 되짚어 올라간다 — 상수만 작을 뿐 둘 다 $O(d)$ 다.

이 배수는 딱 떨어지지 않는다. 4회 재실행해 보면 깊이 1은 0.9배~1.1배 사이(오히려 `yield from` 이 근소하게 느리게 나온 적도 있다), 깊이 20~50은 대개 1.36배~1.55배인데 한 번은 1.75배까지 튄 적도 있다. **perf 측정 특유의 변동성이다.** 안정적인 결론은 정확한 배수가 아니라 "깊이가 깊어질수록 격차가 조금씩 벌어지되, 몇 배씩 벌어지지는 않는다"는 자릿수 자체다.

**`yield from` 을 쓰는 이유는 속도가 아니다.** 반환값·`send`·`throw`·`close` 의 올바른 전파다. 속도는 덤이다.

위임 체인은 밖에서 볼 수도 있다.

```pyrepl
>>> def inner():
...     yield 1
...     yield 2
...
>>> def outer():
...     yield from inner()
...
>>> o = outer()
>>> next(o)
1
>>> o.gi_yieldfrom
<generator object inner at 0x000002A638066D40>
```

`gi_yieldfrom` 이 지금 누구에게 위임 중인지 가리킨다. `asyncio` 가 스택 트레이스를 재구성할 때 쓰는 것과 같은 필드다.
:::

## `send` / `throw` / `close` — 여기가 코루틴의 뿌리다

지금까지 제너레이터는 **값을 내보내기만** 했다. 그런데 `yield` 는 문(statement)이 아니라 **식(expression)** 이다. 값을 반환한다.

```python
received = yield        # yield 가 값을 돌려준다?
```

돌려준다. `send()` 가 넣어 주는 값이다.

```python title="echo.py"
def echo():
    print("시작")
    try:
        while True:
            received = yield          # 여기서 멈추고, send()가 준 값을 받는다
            print("받음:", received)
    except GeneratorExit:
        print("닫힘")


g = echo()
g.send(None)        # 첫 yield까지 진행시킨다 (= next(g))
g.send("a")
g.send("b")
g.close()
```

```text nolines
시작
받음: a
받음: b
닫힘
```

**제너레이터가 값을 소비하는 쪽이 됐다.** 방향이 뒤집혔다.

```text nolines
   pull model (지금까지)                push model (send)

   caller ──── next() ───▶ gen         caller ─── send(v) ──▶ gen
          ◀─── value ─────                    ◀── (None) ────

   caller 가 주도한다                    gen 이 소비자다
```

::: warn 첫 send 는 반드시 None 이어야 한다
```pyrepl
>>> def g():
...     yield 1
...
>>> it = g()
>>> it.send("x")
Traceback (most recent call last):
  ...
TypeError: can't send non-None value to a just-started generator
```

갓 만들어진 제너레이터는 **아직 첫 `yield` 에 도달하지 않았다.** 값을 받을 자리가 없다. 그래서 `send(None)` 또는 `next(g)` 로 첫 `yield` 까지 밀어 주는 **점화(priming)** 가 필요하다.

이걸 자동화하는 데코레이터가 실무의 관용구다.

```python
from functools import wraps

def coroutine(func):
    @wraps(func)
    def primed(*args, **kwargs):
        g = func(*args, **kwargs)
        next(g)                 # 점화
        return g
    return primed
```

([1.11 데코레이터](#/decorators))
:::

누산기를 만들면 `send` 의 양방향성이 선명해진다.

```pyrepl
>>> def accumulator():
...     total = 0
...     while True:
...         x = yield total        # total 을 내보내고, x 를 받는다
...         total += x
...
>>> a = accumulator()
>>> next(a)
0
>>> a.send(10)
10
>>> a.send(5)
15
```

**한 줄이 출력과 입력을 동시에 한다.** `yield total` 의 `total` 은 나가는 값이고, `x = yield` 의 `x` 는 들어오는 값이다.

### `throw` — 밖에서 안으로 예외 던지기

```pyrepl
>>> def g():
...     try:
...         yield 1
...         yield 2
...     except ValueError as e:
...         print("안에서 잡음:", e)
...         yield 99
...
>>> it = g()
>>> next(it)
1
>>> it.throw(ValueError("보낸 예외"))
안에서 잡음: 보낸 예외
99
```

`throw()` 는 **멈춰 있는 `yield` 자리에서 예외가 발생한 것처럼** 만든다. 제너레이터가 잡으면 계속 살고, 안 잡으면 밖으로 전파된다. `asyncio` 의 취소(`CancelledError`)가 정확히 이 메커니즘이다([4.7 asyncio 실전](#/asyncio-advanced)).

### `close` — 그리고 `finally` 가 실행된다는 사실

```pyrepl
>>> def resource():
...     print("열기")
...     try:
...         yield 1
...         yield 2
...     finally:
...         print("닫기")
...
>>> g = resource()
>>> next(g)
열기
1
>>> g.close()
닫기
```

`close()` 는 멈춘 자리에 `GeneratorExit` 를 던진다. `finally` 가 돌고 제너레이터가 끝난다.

**`close()` 를 명시적으로 안 불러도 된다.** 참조 카운트가 0이 되면 CPython이 대신 불러 준다([1.1 객체, 이름, 참조](#/objects-names)).

```pyrepl
>>> def r2():
...     try:
...         yield 1
...     finally:
...         print("r2 닫기")
...
>>> g2 = r2()
>>> next(g2)
1
>>> del g2
r2 닫기
```

::: danger 이게 왜 위험한가 — 정리 시점이 GC에 달려 있다
```python
def read_lines(path):
    f = open(path)
    try:
        for line in f:
            yield line
    finally:
        f.close()               # 언제 실행되나?

for line in read_lines("big.log"):
    if "ERROR" in line:
        break                   # 여기서 나가면?
```

`break` 로 나가면 제너레이터는 **소진되지 않은 채로 남는다.** `finally` 는 제너레이터 객체가 회수될 때 실행된다 — CPython에서는 참조 카운트가 0이 되는 즉시라 대개 바로다. 그런데:

- 제너레이터가 **순환 참조**에 끼면 GC 주기까지 지연된다.
- **PyPy·Jython**은 참조 카운팅을 안 쓴다. 언제 닫힐지 아무도 모른다.
- 예외 트레이스백이 프레임을 붙들고 있으면 살아남는다.

파일 핸들 수백 개가 그동안 열려 있다. **`contextlib.closing` 또는 `with` 로 명시하라.**

```python
from contextlib import closing

with closing(read_lines("big.log")) as lines:     # ✅ 스코프를 벗어나면 확실히 close
    for line in lines:
        if "ERROR" in line:
            break
```

[1.17 컨텍스트 매니저](#/context-managers)의 `@contextmanager` 는 사실 **`yield` 하나짜리 제너레이터**를 컨텍스트 매니저로 감싸는 물건이다. `__enter__` 가 `next()` 고, `__exit__` 가 `throw()`/`close()` 다. 지금 배운 것 그대로다.

### 그리고 GeneratorExit 를 무시하면 안 된다

```pyrepl
>>> def bad():
...     try:
...         yield 1
...     except GeneratorExit:
...         yield 2              # ❌ 죽으라고 했는데 또 yield
...
>>> g = bad()
>>> next(g)
1
>>> g.close()
Traceback (most recent call last):
  ...
RuntimeError: generator ignored GeneratorExit
```

`GeneratorExit` 를 잡는 것은 **정리하기 위해서지 살아남기 위해서가 아니다.** 잡았으면 반드시 다시 던지거나 그냥 끝내라.
:::

### 그래서 코루틴이 여기서 나온다

지금 가진 것을 세어 보자. 제너레이터는

- 중간에 **멈출 수 있고**(`yield`),
- 밖에서 **값을 넣어 재개할 수 있고**(`send`),
- 밖에서 **예외를 던져 취소할 수 있고**(`throw`),
- **정리할 수 있고**(`close`),
- **다른 제너레이터에게 위임하며 결과를 받아올 수 있다**(`yield from`).

이건 **협력적 멀티태스킹의 완전한 명세**다. 스케줄러 하나만 붙이면 된다. 실제로 파이썬 3.4의 `asyncio` 는 정확히 이렇게 만들어졌다.

```python
@asyncio.coroutine          # 3.4~3.7 스타일. 지금은 제거됐다
def fetch():
    data = yield from read()
    return data
```

3.5에서 `async def` / `await` 가 나왔지만, **바뀐 것은 문법뿐이다.**

```pyrepl
>>> async def coro():
...     return 42
...
>>> c = coro()
>>> type(c)
<class 'coroutine'>
>>> [m for m in ("send", "throw", "close") if hasattr(c, m)]
['send', 'throw', 'close']
```

코루틴 객체에 `send`, `throw`, `close` 가 그대로 있다. 그리고 결과를 받는 방법도 같다.

```pyrepl
>>> c = coro()
>>> try:
...     c.send(None)
... except StopIteration as e:
...     print("StopIteration value =", e.value)
...
StopIteration value = 42
```

**`await` 의 결과값은 `StopIteration.value` 로 온다.** 이벤트 루프가 하는 일은 결국 *"코루틴들에게 `send(None)` 을 돌아가며 호출하고 `StopIteration` 이 나면 결과를 꺼내는 것"* 이다. 마법은 없다.

```pyrepl
>>> import inspect
>>> async def c(): return 1
>>> bool(c.__code__.co_flags & inspect.CO_COROUTINE)
True
>>> async def ag():
...     yield 1
...
>>> bool(ag.__code__.co_flags & inspect.CO_ASYNC_GENERATOR)
True
```

컴파일러 플래그 하나 차이다. `CO_GENERATOR`, `CO_COROUTINE`, `CO_ASYNC_GENERATOR` — 셋 다 같은 기계 위에 얹혀 있다.

::: hist 왜 async/await 를 따로 만들었나
`yield from` 으로 다 되는데 왜 새 문법을 만들었을까. [PEP 492](https://peps.python.org/pep-0492/)의 이유는 **구분 불가능성**이었다.

```python
def f():
    yield from g()      # g가 데이터 제너레이터인가, 비동기 작업인가?
```

똑같이 생겼는데 의미가 전혀 다르다. 데이터를 흘리는 제너레이터와 I/O를 기다리는 코루틴이 같은 문법을 쓰면, 실수로 `for x in coro()` 를 써도 컴파일러가 못 잡는다. 그래서 `async def` 로 **타입을 분리**하고, `await` 로 **의도를 명시**했다.

대가는 색깔 문제(function coloring)다. `async` 함수는 `async` 함수에서만 부를 수 있어서, 한 번 비동기가 되면 호출 스택 전체가 비동기가 된다. 이 얘기는 [4.6 asyncio 기초](#/asyncio-basics)에서.
:::

## 소진의 함정

이 절에서 **실무 버그를 가장 많이 만드는 지점**이다.

```pyrepl
>>> data = (x for x in range(5))
>>> list(data)
[0, 1, 2, 3, 4]
>>> list(data)
[]
>>> sum(data)
0
>>> max(data, default="EMPTY")
'EMPTY'
```

**두 번째부터는 조용히 빈다.** 예외도 경고도 없다. `sum` 은 `0` 을, `list` 는 `[]` 를 반환한다. **정상적인 답처럼 생긴 틀린 답**이다.

::: danger map/filter/zip 도 전부 이터레이터다
```python
def report(scores):
    print(f"평균: {sum(scores) / len(list(scores))}")     # ❌
    print(f"최고: {max(scores)}")                          # ❌


report(map(int, ["10", "20", "30"]))
```

`sum(scores)` 가 이미 다 써 버렸다. `len(list(scores))` 는 0이 되고 `ZeroDivisionError` 가 난다. 운이 좋아 예외가 나면 다행이다. `max` 는 `ValueError: max() arg is an empty sequence` 를 던지고, `sum` 은 **조용히 0**을 반환한다.

**규칙**: 함수가 이터러블을 받아 **두 번 이상 순회한다면, 받자마자 구체화하라.**

```python
def report(scores):
    scores = list(scores)                                  # ✅ 경계에서 한 번
    print(f"평균: {sum(scores) / len(scores)}")
    print(f"최고: {max(scores)}")
```

이터레이터인지 아닌지 판단하려면:

```pyrepl
>>> from collections.abc import Iterator
>>> isinstance([1, 2, 3], Iterator)
False
>>> isinstance(map(int, "123"), Iterator)
True
>>> isinstance(iter([1, 2, 3]), Iterator)
True
```

`isinstance(x, Iterator)` 가 `True` 면 **한 번 쓰면 사라진다.**
:::

::: deep zip(it, it) — 소진이 기능이 되는 순간
같은 이터레이터를 두 번 넘기면 재미있는 일이 벌어진다.

```pyrepl
>>> it = iter([1, 2, 3, 4, 5])
>>> list(zip(it, it))
[(1, 2), (3, 4)]
```

`zip` 은 인자를 **왼쪽부터 차례로** `next()` 한다. 커서가 하나뿐이라 `1` 다음에 `2` 가 나오고, 홀수 개면 마지막이 버려진다. **2개씩 묶기** 관용구다.

```python
it = iter(data)
pairs = list(zip(it, it))                # 2개씩
triples = list(zip(*[iter(data)] * 3))   # 3개씩 — 같은 이터레이터 3개 참조
```

똑똑해 보이지만 **읽는 사람을 괴롭힌다.** 3.12부터는 이게 있다.

```pyrepl
>>> import itertools
>>> list(itertools.batched("abcdefg", 3))
[('a', 'b', 'c'), ('d', 'e', 'f'), ('g',)]
```

`batched` 를 써라.
:::

### 제너레이터에는 `len` 도 `reversed` 도 없다

```pyrepl
>>> g = (i for i in range(3))
>>> len(g)
Traceback (most recent call last):
  ...
TypeError: object of type 'generator' has no len()
>>> reversed(g)
Traceback (most recent call last):
  ...
TypeError: 'generator' object is not reversible
```

당연하다. **끝을 모르는데 길이를 알 수 없고, 뒤로 갈 수 없는데 뒤집을 수 없다.** 둘 중 하나라도 필요하면 그건 이터레이터가 아니라 시퀀스가 필요한 상황이다.

### 순회 중 수정

이터레이터가 원본을 **가리키기만** 한다는 사실의 결과다.

```pyrepl
>>> d = {"a": 1, "b": 2}
>>> for k in d:
...     d[k + "!"] = 0
...
Traceback (most recent call last):
  ...
RuntimeError: dictionary changed size during iteration
```

`dict` 와 `set` 은 버전 카운터를 들고 있어 잡아 준다. **리스트는 안 잡는다.**

```pyrepl
>>> lst = [1, 2, 3]
>>> out = []
>>> for x in lst:
...     out.append(x)
...     if x == 1:
...         lst.remove(2)
...
>>> out
[1, 3]
```

`2` 가 조용히 사라졌다. `list_iterator` 는 **인덱스만** 들고 있어서, 인덱스 0을 읽은 뒤 리스트가 `[1, 3]` 으로 줄어들면 인덱스 1은 이제 `3` 이다. 예외 없이 원소를 건너뛴다.

**규칙**: 순회 중인 컨테이너를 수정하지 마라. 필요하면 사본을 순회하거나(`for x in lst[:]`), 새 리스트를 만들어라.

## itertools 예고

여기까지 왔으면 `itertools` 를 읽을 준비가 됐다. 표준 라이브러리에서 **가장 밀도 높은 모듈**이고, 전부 C로 구현된 게으른 이터레이터다.

```pyrepl
>>> import itertools
>>> list(itertools.islice(itertools.count(10, 5), 4))    # 무한 수열에서 4개만
[10, 15, 20, 25]
>>> list(itertools.chain([1, 2], [3]))                   # 이어 붙이기
[1, 2, 3]
>>> [list(g) for k, g in itertools.groupby("aaabbc")]    # 연속 그룹
[['a', 'a', 'a'], ['b', 'b'], ['c']]
>>> list(itertools.pairwise([1, 2, 3, 4]))               # 인접 쌍 (3.10+)
[(1, 2), (2, 3), (3, 4)]
>>> list(itertools.accumulate([1, 2, 3, 4]))             # 누적합
[1, 3, 6, 10]
```

`itertools.count()` 는 무한하다. 그런데 크기는 이렇다.

```pyrepl
>>> import sys
>>> sys.getsizeof(itertools.count())
56
```

**무한 수열이 56바이트다.** 이게 게으름이다.

::: warn tee 는 게으르지 않다
`itertools.tee(it, 2)` 는 이터레이터 하나를 두 개로 복제해 준다. 이름만 보면 공짜 같다. **아니다.**

```python
import itertools, tracemalloc

tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
x, y = itertools.tee(iter(range(200_000)))
list(x)                                            # 한쪽만 끝까지 소비
peak = tracemalloc.get_traced_memory()[1] - base
print(f"tee 한쪽만 소비 시 peak: {peak / 1024 / 1024:.2f} MB")
```

```text nolines
tee 한쪽만 소비 시 peak: 9.36 MB
```

`y` 가 아직 안 읽은 값 20만 개를 **`tee` 가 내부 버퍼에 전부 쌓아 두기** 때문이다. 두 갈래의 진행 속도 차이만큼 메모리를 먹는다. 한쪽을 먼저 다 소비하는 패턴이면 `tee` 는 **리스트를 만드는 것보다 나쁘다** — 버퍼 + 이터레이터 오버헤드가 붙는다.

`tee` 는 **두 갈래가 비슷한 속도로 나란히 갈 때만** 쓴다. 자세한 건 [3.2 itertools](#/itertools)에서.
:::

## 요약

> 이터러블은 `__iter__` 로 **커서를 만들어 주는 것**이고, 이터레이터는 `__next__` 로 **다음 값을 내주는 커서**다. `for` 문은 `iter()` → `next()` 반복 → `StopIteration` 잡기의 설탕이다. 제너레이터는 이 프로토콜을 컴파일러가 자동 구현해 주는 문법이고, **프레임을 통째로 보존**해서 `yield` 자리에서 재개한다. `yield from` 은 반환값·`send`·`throw`·`close` 를 안쪽까지 올바르게 전파하는 위임이고, 이 다섯 가지가 모여 **코루틴**이 된다. `async def` 는 그 위에 얹힌 문법일 뿐이다. 게으름은 메모리와 CPU를 바꾸는 거래이며, **커서는 하나뿐이라 한 번 쓰면 사라진다.**

체크리스트:

- [ ] 이터러블 ≠ 이터레이터. `isinstance(x, Iterator)` 가 `True` 면 **한 번 쓰면 끝**이다.
- [ ] `__iter__` 에서 `self` 를 반환하는 컬렉션 클래스는 중첩 루프에서 깨진다. 제너레이터를 반환하라.
- [ ] `StopIteration` 은 에러가 아니라 신호다. 제너레이터 안에서 새면 `RuntimeError` 가 된다(PEP 479).
- [ ] `any`/`all`/`next`/`in` 에 대괄호를 넣지 마라. 조기 종료가 죽는다. **5만 배 차이**.
- [ ] 전부 소비할 거면 제너레이터가 **3~6배 느리다** (원소 수·반복 방식에 따라 갈린다). 게으름은 최적화가 아니라 거래다.
- [ ] `yield from` 을 쓰는 이유는 속도(1.1~1.5배 안팎, 변동 있음)가 아니라 **올바른 전파**다.
- [ ] `send`/`throw`/`close` 는 `await`/취소/정리의 원형이다. 코루틴은 새 물건이 아니다.
- [ ] 이터러블을 받아 두 번 순회할 함수는 **경계에서 `list()` 로 구체화**하라.

::: quiz 연습문제

1. 다음 각각의 출력을 **먼저 예측한 뒤** 실행하라. 틀린 것이 있다면 왜인지 설명하라.

   ```python
   it = iter([1, 2, 3, 4, 5, 6])
   print(list(zip(it, it, it)))
   print(list(it))

   g = (x * 2 for x in [1, 2, 3])
   print(3 in g)
   print(6 in g)
   print(2 in g)
   ```

2. 아래 함수는 왜 위험한가? 두 가지 문제가 있다. 각각 찾아 고쳐라.

   ```python
   def stats(values):
       n = sum(1 for _ in values)
       return sum(values) / n, max(values)
   ```

3. 다음 제너레이터의 출력을 예측하라. `finally` 는 언제 실행되는가?

   ```python
   def gen():
       try:
           yield 1
           yield 2
       finally:
           print("정리")

   for x in gen():
       print(x)
       break
   print("루프 이후")
   ```

4. `yield from` 없이 아래를 구현하되 **동작이 완전히 같게** 만들어라. 무엇을 구현해야 하는지 세어 보고, 왜 `for x in inner(): yield x` 로는 부족한지 설명하라.

   ```python
   def outer():
       result = yield from inner()
       return result * 2
   ```

5. **깊이 생각해 볼 문제.** 아래는 `Countdown` 이터레이터다. `sys.getsizeof` 로 이 인스턴스와, 같은 일을 하는 제너레이터 객체의 크기를 비교하라. 어느 쪽이 큰가? 그리고 왜 그런가? (힌트: 제너레이터가 프레임 안에 무엇을 들고 있는지 세어 보라.)

   ```python
   class Countdown:
       def __init__(self, n):
           self.n = n
       def __iter__(self):
           return self
       def __next__(self):
           if self.n <= 0:
               raise StopIteration
           self.n -= 1
           return self.n + 1

   def countdown(n):
       while n > 0:
           yield n
           n -= 1
   ```

6. `itertools.count()` 가 56바이트인데 무한 수열을 표현할 수 있는 이유를 설명하라. 그리고 `list(itertools.count())` 를 **절대 실행하지 마라.** 왜 안 되는지 설명하라.
:::

**다음 절**: [1.19 모듈, 패키지, import 시스템](#/imports) — `import` 한 줄이 실제로 훑는 경로, 순환 import가 나는 진짜 이유, 그리고 지연 import.
