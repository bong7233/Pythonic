# 4.6 asyncio 기초: 코루틴과 이벤트 루프

::: lead
`async def` 를 쓰고 `await` 를 붙이면 뭔가 "동시에" 돌아간다고 믿기 쉽다. 틀렸다. 스레드는 하나도 안 늘어난다. **단일 스레드가 여러 작업 사이를 정교하게 오간다.** 이 절은 그 오가는 지점이 정확히 어디인지, `await` 가 실제로 무슨 함수를 호출하는지를 로그로 증명한다. [1.18 이터레이터와 제너레이터](#/iterators)에서 `send`/`throw`/`close`/`yield from` 을 다뤘다면 이 절은 새 문법이 아니라 **그 위에 얹힌 이름표**를 벗기는 작업이다.
:::

## 코루틴 함수를 불러도 아무 일도 안 일어난다

`async def` 로 정의한 함수를 호출하면 몸통이 실행될 거라고 생각하기 쉽다.

```python title="never_run.py"
async def hello():
    print("실행됨!")
    return 42

c = hello()
print(type(c))
```

```text nolines
<class 'coroutine'>
```

**"실행됨!" 이 안 찍힌다.** `hello()` 호출은 몸통을 한 줄도 돌리지 않고 **코루틴 객체 하나만 만들어 즉시 반환**한다. [1.18](#/iterators)에서 본 제너레이터와 정확히 같은 이야기다 — `countdown(3)` 이 몸통을 안 돌리고 제너레이터 객체만 반환했던 것과 같은 메커니즘이다. 컴파일러가 `co_flags` 에 표시를 남기고, 인터프리터는 그 표시를 보고 다르게 다룬다.

```pyrepl
>>> import inspect
>>> async def hello(): ...
...
>>> bool(hello.__code__.co_flags & inspect.CO_COROUTINE)
True
>>> inspect.iscoroutine(hello())
True
```

만든 코루틴 객체를 아무도 실행시키지 않으면 어떻게 될까.

```python title="forgotten.py"
async def hello():
    print("실행됨")

hello()  # 호출만 하고 끝 — await도 안 하고 create_task도 안 함
```

```text nolines
forgotten.py:4: RuntimeWarning: coroutine 'hello' was never awaited
  hello()
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

파이썬은 이걸 **버그로 의심한다.** 코루틴 객체가 참조 카운트 0이 되어 소멸하는데, 한 번도 실행(`send`)된 적이 없으면 "만들어 놓고 잊어버린 것 아니냐"는 경고를 띄운다. 실전에서 이 경고가 뜨면 십중팔구 `await` 를 빼먹은 것이다.

## 코루틴은 제너레이터가 진화한 것이다

코루틴 객체가 뭘 들고 있는지 뜯어 보면 낯이 익다.

```pyrepl
>>> async def coro(): return 42
...
>>> c = coro()
>>> [m for m in ("send", "throw", "close") if hasattr(c, m)]
['send', 'throw', 'close']
>>> try:
...     c.send(None)
... except StopIteration as e:
...     print("StopIteration value =", e.value)
...
StopIteration value = 42
```

`send`, `throw`, `close` 가 그대로 있다. 그리고 **결과값은 여전히 `StopIteration.value` 로 온다.** [1.18](#/iterators)에서 `yield from` 이 반환값을 꺼내 주는 통로라고 했던 바로 그 값이다. `await` 가 실제로 하는 일은 결국 *"코루틴을 `send(None)` 으로 계속 돌리다가 `StopIteration` 이 나면 그 `value` 를 결과로 쓰는 것"* 이다.

3.4 시절의 `asyncio` 는 실제로 제너레이터 그 자체였다.

```python
@asyncio.coroutine          # 3.4~3.7. 3.11에서 완전히 제거됐다
def fetch():
    data = yield from read_socket()
    return data
```

3.5에서 `async def`/`await` 문법이 따로 생겼지만, [PEP 492](https://peps.python.org/pep-0492/)가 밝힌 이유는 속도가 아니라 **구분**이었다. `yield from g()` 는 `g` 가 데이터를 흘리는 제너레이터인지 I/O를 기다리는 코루틴인지 코드만 봐서는 알 수 없다. `async def` 로 타입을 갈라 놓으면 실수로 코루틴을 `for` 문에 넣는 걸 인터프리터가 즉시 잡아 준다.

```pyrepl
>>> async def coro(): return 1
...
>>> for x in coro():   # 코루틴을 그냥 순회하려 하면
...     pass
...
Traceback (most recent call last):
  ...
TypeError: 'coroutine' object is not iterable
```

문법은 바뀌었어도 기계는 하나다.

```pyrepl
>>> import inspect
>>> async def c(): return 1
...
>>> async def ag():
...     yield 1
...
>>> bool(c.__code__.co_flags & inspect.CO_COROUTINE)
True
>>> bool(ag.__code__.co_flags & inspect.CO_ASYNC_GENERATOR)
True
```

`CO_GENERATOR`, `CO_COROUTINE`, `CO_ASYNC_GENERATOR` — 셋 다 "프레임을 보존한 채 멈췄다 재개하는" 같은 능력 위에 붙은 서로 다른 이름표일 뿐이다.

## `await` 는 정확히 어디서 제어를 넘기는가

`await coro()` 를 만나면 파이썬이 코루틴 체인을 타고 내려간다. 그런데 **어디서든 멈추는 게 아니다.** 진짜로 대기가 필요한 지점(소켓, 타이머)에 도달할 때만 이벤트 루프에게 제어를 돌려준다. 실행 중인 코루틴이 지금 어디서 멈춰 있는지 직접 들여다볼 수 있다.

```python title="await_chain.py"
import asyncio

async def inner():
    await asyncio.sleep(0.05)

async def outer():
    await inner()               # outer는 inner에게 통째로 위임한 상태

async def main():
    c = outer()
    task = asyncio.ensure_future(c)
    await asyncio.sleep(0.01)   # outer가 실행되고 멈출 시간을 준다
    print("cr_await:", c.cr_await)
    print("cr_frame.f_lineno:", c.cr_frame.f_lineno)
    await task

asyncio.run(main())
```

```text nolines
cr_await: <coroutine object inner at 0x000001E7F871ED40>
cr_frame.f_lineno: 7
```

`outer` 는 지금 `inner()` 를 기다리는 중이고, `inner` 는 그 안에서 `asyncio.sleep(0.05)` 를 기다리는 중이다. `cr_await` 가 이 위임 사슬을 그대로 드러낸다 — [1.18](#/iterators)의 `gi_yieldfrom` 과 이름만 다른 같은 필드다.

::: deep 진짜로 멈추는 지점은 Future 뿐이다
`await coro()` 는 `coro` 몸통 안으로 들어가 다시 `coro` 가 만나는 `await` 를 따라간다 — 재귀적으로. 이 재귀는 결국 바닥에 있는 `Future` (또는 그걸 감싼 `Task`)의 `__await__` 에 도달한다. **거기서만** 진짜로 `yield` 가 일어나 이벤트 루프까지 제어가 올라간다.

`asyncio.sleep(0)` 이 아닌 `asyncio.sleep(n>0)` 을 예로 들면, 내부적으로 `Future` 를 만들고 `call_later(n, ...)` 로 타이머를 이벤트 루프에 등록한 뒤 그 `Future` 를 `await` 한다. 등록된 콜백이 타이머 만료 시 `Future` 를 완료시키기 전까지, 이 코루틴 체인 전체는 **이벤트 루프의 할 일 목록에서 빠져 있다.** 그래서 `await asyncio.sleep(1)` 을 건 코루틴은 1초 동안 CPU를 전혀 안 쓴다 — 스레드를 안 쓰는 것과 같은 원리다.

반대로 순수 계산만 하고 `await` 가 하나도 없는 `async def` 함수는, 아무리 코루틴이어도 **끝까지 한 번에 실행된다.** 바로 다음 절에서 실측한다.
:::

## `asyncio.run`, `create_task`, `gather`

세 함수의 역할을 정확히 나누면 이렇다.

- **`asyncio.run(coro)`** — 새 이벤트 루프를 만들고, `coro` 를 완료될 때까지 돌리고, 루프를 닫는다. 프로그램에서 **딱 한 번**, 최상위에서만 부른다.
- **`asyncio.create_task(coro)`** — 코루틴을 **즉시 스케줄**에 올린다. `await` 하지 않아도 다음에 이벤트 루프가 한 바퀴 돌 때 실행이 시작된다.
- **`asyncio.gather(*aws)`** — 여러 어웨이터블을 동시에 기다리고, 전부 끝나면 결과를 **순서대로** 묶어 반환한다.

`create_task` 없이 그냥 `await` 를 두 번 쓰면 순차 실행이라는 걸 실측으로 비교해 보자.

```python title="sequential.py — create_task 없이 순서대로 await"
import asyncio, time

start = time.perf_counter()

def log(msg):
    print(f"[{time.perf_counter() - start:6.3f}s] {msg}")

async def worker(name, delay):
    log(f"{name} 시작")
    await asyncio.sleep(delay)
    log(f"{name} 재개, 종료")
    return name

async def main():
    r1 = await worker("A", 0.3)
    r2 = await worker("B", 0.1)
    log(f"끝: {[r1, r2]}")

asyncio.run(main())
```

```text nolines
[ 0.001s] A 시작
[ 0.309s] A 재개, 종료
[ 0.309s] B 시작
[ 0.417s] B 재개, 종료
[ 0.417s] 끝: ['A', 'B']
```

`A` 가 끝나야 `B` 가 시작한다. 총 `0.3 + 0.1 = 0.417초`(로그 오버헤드 포함) 걸렸다.

(Python 3.14 / Windows 기준 실측. 절대값은 실행할 때마다 몇 ms씩 흔들린다 — 같은 코드를 다시 돌리면 `0.309s` 대신 `0.303~0.313s` 가 나올 수도 있다. 하지만 "A가 끝나야 B가 시작한다"는 순서, 그리고 총 시간이 `0.3 + 0.1` 초에 근접한다는 패턴은 몇 번을 돌려도 똑같다.)

이제 `create_task` 로 둘 다 미리 스케줄에 올려 보자.

```python title="concurrent.py — create_task + gather"
import asyncio, time

start = time.perf_counter()

def log(msg):
    print(f"[{time.perf_counter() - start:6.3f}s] {msg}")

async def worker(name, delay):
    log(f"{name} 시작")
    await asyncio.sleep(delay)
    log(f"{name} 재개, 종료")
    return name

async def main():
    t1 = asyncio.create_task(worker("A", 0.3))
    t2 = asyncio.create_task(worker("B", 0.1))
    log("두 태스크 예약 완료. gather로 기다린다")
    results = await asyncio.gather(t1, t2)
    log(f"둘 다 끝남: {results}")

asyncio.run(main())
```

```text nolines
[ 0.001s] main 시작 — 두 워커를 태스크로 예약한다
[ 0.001s] 두 태스크 예약 완료. gather로 기다린다
[ 0.001s] A 시작
[ 0.001s] B 시작
[ 0.115s] B 재개, 종료
[ 0.301s] A 재개, 종료
[ 0.301s] 둘 다 끝남: ['A', 'B']
```

`A` 와 `B` 가 **같은 0.001초에 둘 다 시작**했다. 총 시간은 `0.417초` 가 아니라 `0.301초` — `max(0.3, 0.1)` 에 근접한다. `B` 가 `A` 보다 먼저 시작했는데도 `gather` 가 반환한 결과 순서는 `['A', 'B']` 다. **완료 순서가 아니라 넘긴 순서**를 지킨다.

(위 두 실측 모두 Python 3.14 / Windows 기준. 다시 돌리면 `0.301s` 가 `0.302~0.305s` 정도로 흔들린다 — 그래도 `0.417s` 근처와 `0.3s` 근처라는 자릿수 차이, 그리고 순차 실행이 동시 실행보다 항상 느리다는 관계는 변하지 않는다.)

::: warn create_task 는 스레드를 만들지 않는다
"태스크를 두 개 예약했다"는 말이 "두 스레드가 생겼다"는 뜻이 아니다. 여전히 **스레드 하나**가 `A` 를 `0.001s` 까지 돌리다가 `await asyncio.sleep(0.3)` 을 만나 제어를 이벤트 루프에 넘기고, 루프가 그 틈에 `B` 를 `0.001s` 까지 돌린 것이다. `B` 도 `await asyncio.sleep(0.1)` 에서 제어를 넘기니, 그때부터는 **아무 코루틴도 실행 중이 아니다.** 이벤트 루프는 타이머만 감시하다가 `0.1초` 뒤 `B` 를, `0.3초` 뒤 `A` 를 깨운다.
:::

## 이벤트 루프가 번갈아 실행한다는 것의 진짜 의미

방금 본 동시성은 `asyncio.sleep` 이 **친절하게** 제어를 넘겨준 덕이다. `await` 가 하나도 없는 `async def` 를 태스크로 여러 개 만들면 어떻게 될까.

```python title="cpu_hog.py"
import asyncio, time

start = time.perf_counter()

def log(msg):
    print(f"[{time.perf_counter() - start:6.3f}s] {msg}")

async def cpu_hog(name):
    log(f"{name} 시작 — CPU 작업, await 없음")
    total = 0
    for i in range(30_000_000):
        total += i
    log(f"{name} 끝")
    return total

async def main():
    log("두 CPU 작업을 태스크로 예약")
    t1 = asyncio.create_task(cpu_hog("X"))
    t2 = asyncio.create_task(cpu_hog("Y"))
    await asyncio.gather(t1, t2)

asyncio.run(main())
```

```text nolines
[ 0.001s] 두 CPU 작업을 태스크로 예약
[ 0.001s] X 시작 — CPU 작업, await 없음
[ 0.604s] X 끝
[ 0.604s] Y 시작 — CPU 작업, await 없음
[ 1.187s] Y 끝
```

**태스크 두 개를 예약했는데 완전히 순차로 돌았다.** `X` 가 `0.001s` 부터 `0.604s` 까지 이벤트 루프를 통째로 붙들고 있다가, 끝나서야 `Y` 가 시작한다.

(Python 3.14 / Windows 기준 실측. CPU 클럭·발열 상태에 따라 `0.594~0.604s`, `1.169~1.188s` 사이에서 흔들린다 — 그래도 "X가 끝나기 전엔 Y가 한 줄도 안 돈다"는 사실과 "Y 종료 시각이 X 종료 시각의 거의 정확히 2배"라는 관계는 매번 똑같다.) `create_task` 는 "언젠가 실행해라"는 예약일 뿐, 실제로 번갈아 실행되려면 **실행 중인 코루틴이 스스로 `await` 로 제어를 내놓아야 한다.** 협력적(cooperative) 멀티태스킹이라는 말의 "협력"이 바로 이 뜻이다 — 자원을 뺏는 스케줄러가 없다. 이건 [4.2 threading](#/threading)의 선점형 스레드와 정반대다.

```text nolines
   asyncio.run(main())  ── 단일 스레드, 이벤트 루프 하나

   ready queue: [X, Y]
   X.send(None)  -> 루프 안 반납, 0.603s 동안 CPU 독점
   X 완료 (StopIteration)
   Y.send(None)  -> 이제야 시작, 다시 CPU 독점
   Y 완료
```

CPU를 오래 쓰는 작업은 asyncio로 병렬화되지 않는다. [4.4 multiprocessing](#/multiprocessing)이나 [4.3 GIL](#/gil)에서 다루는 접근이 필요하다. asyncio가 잘 듣는 건 **I/O 대기**뿐이다.

## `sleep(0)` — 강제로 양보하기

CPU 작업이라도 중간중간 제어를 넘기고 싶으면 명시적으로 양보하면 된다. `asyncio.sleep(0)` 은 **"실제로 쉬지는 않되, 지금 한 번 이벤트 루프에 순서를 넘긴다"** 는 뜻이다.

```python title="chunked.py — sleep(0)으로 CPU 작업 쪼개기"
import asyncio, time

start = time.perf_counter()

def log(msg):
    print(f"[{time.perf_counter() - start:6.3f}s] {msg}")

async def chunked_work(name):
    log(f"{name} 시작")
    total = 0
    for chunk in range(3):
        for i in range(10_000_000):
            total += i
        log(f"{name} 청크 {chunk} 끝 — sleep(0)으로 양보")
        await asyncio.sleep(0)
    log(f"{name} 완전히 끝")
    return total

async def main():
    t1 = asyncio.create_task(chunked_work("X"))
    t2 = asyncio.create_task(chunked_work("Y"))
    await asyncio.gather(t1, t2)

asyncio.run(main())
```

```text nolines
[ 0.001s] X 시작
[ 0.234s] X 청크 0 끝 — sleep(0)으로 양보
[ 0.234s] Y 시작
[ 0.457s] Y 청크 0 끝 — sleep(0)으로 양보
[ 0.724s] X 청크 1 끝 — sleep(0)으로 양보
[ 0.992s] Y 청크 1 끝 — sleep(0)으로 양보
[ 1.200s] X 청크 2 끝 — sleep(0)으로 양보
[ 1.413s] Y 청크 2 끝 — sleep(0)으로 양보
[ 1.413s] X 완전히 끝
[ 1.413s] Y 완전히 끝
```

`X` 와 `Y` 가 청크 단위로 번갈아 실행되는 게 로그에 그대로 찍힌다. 총 시간은 `1.413초` — `cpu_hog.py` 의 `1.187초` 보다 오히려 **길다.** 코루틴을 멈추고 재개하는 데도 비용이 들기 때문이다([1.18](#/iterators)에서 본 "제너레이터 재개 비용"과 같은 이야기다). `sleep(0)` 은 병렬성을 만들어 주는 게 아니라 **응답성**을 사 오는 것이다 — 다른 태스크(특히 진짜 I/O를 기다리는 태스크)가 굶지 않게 숨 쉴 틈을 준다.

(Python 3.14 / Windows 기준 실측. 절대값은 실행마다 `1.17~1.26초` 사이에서 흔들려서 `cpu_hog.py` 와의 차이가 실행마다 크게 벌어지기도 하고 거의 붙기도 한다 — `sleep(0)` 호출 6번의 재개 비용은 원래 총 실행 시간에 비하면 작다. 그래도 청크 단위로 번갈아 실행된다는 패턴과, 재개 비용이 공짜가 아니라는 방향성은 항상 같다.)

::: deep sleep(0) 과 sleep(n) 은 다른 큐에 들어간다
`asyncio.sleep(0)` 은 특별 취급된다. 내부적으로 `loop.call_soon` 에 해당하는 경로를 타서 **"다음 루프 반복에서 즉시"** 재개되도록 예약된다. `asyncio.sleep(n > 0)` 은 `loop.call_later(n, ...)` 로 타이머 힙에 등록된다 — 이 힙은 [7.15 다익스트라](#/shortest-path)에서 쓴 `heapq` 최소 힙과 같은 구조다. 만료 시각이 가장 이른 타이머가 항상 맨 위에 있어야 하기 때문이다. 이벤트 루프의 한 반복은 대략 *"타이머 힙에서 만료된 것들을 깨우고 → ready 큐를 전부 소진하고 → 다음 타이머까지 대기"* 를 반복하는 구조다.
:::

## 진짜 I/O에서 확인하기 — 로컬 서버

지금까지는 `asyncio.sleep` 으로 I/O 대기를 흉내 냈다. 실제 소켓으로도 같은 일이 벌어지는지 로컬 서버를 직접 띄워 확인해 보자 (외부 네트워크 없이 자기완결적으로 돈다).

```python title="local_server.py"
import asyncio, time

start = time.perf_counter()

def log(msg):
    print(f"[{time.perf_counter() - start:6.3f}s] {msg}")

async def handle_client(reader, writer):
    data = await reader.read(100)
    delay = float(data.decode())
    await asyncio.sleep(delay)          # 서버가 일부러 느리게 응답 (실제 I/O 대기 흉내)
    writer.write(f"슬립 {delay}초 후 응답".encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def fetch(port, delay, name):
    log(f"{name} 요청 시작 (지연 {delay}s)")
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(str(delay).encode())
    await writer.drain()
    writer.write_eof()
    resp = await reader.read(200)
    writer.close()
    log(f"{name} 응답 받음: {resp.decode()}")

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        asyncio.create_task(server.serve_forever())
        log("서버 기동 완료. 세 요청을 동시에 보낸다")
        await asyncio.gather(
            fetch(port, 0.3, "req-A"),
            fetch(port, 0.1, "req-B"),
            fetch(port, 0.2, "req-C"),
        )
    log("전부 완료")

asyncio.run(main())
```

```text nolines
[ 0.001s] req-A 요청 시작 (지연 0.3s)
[ 0.001s] req-B 요청 시작 (지연 0.1s)
[ 0.001s] req-C 요청 시작 (지연 0.2s)
[ 0.110s] req-B 응답 받음: 슬립 0.1초 후 응답
[ 0.205s] req-C 응답 받음: 슬립 0.2초 후 응답
[ 0.313s] req-A 응답 받음: 슬립 0.3초 후 응답
[ 0.313s] 전부 완료
```

세 요청이 **모두 `0.001s` 에 발사**됐고, 응답은 지연 시간이 짧은 순서(`B → C → A`)로 도착했다. 총 소요 시간은 `0.313초` — `0.3 + 0.2 + 0.1 = 0.6초` 가 아니라 `max(0.3, 0.2, 0.1)` 에 근접한다. 소켓 read/write 도 `asyncio.sleep` 과 똑같이 **`Future` 를 통해 이벤트 루프에 제어를 넘기고, OS가 데이터를 준비해 주면 콜백으로 재개된다.** 원리는 하나다.

(Python 3.14 / Windows 기준 실측. 절대값은 실행마다 `0.10/0.20/0.31초` 안팎에서 몇 ms씩 흔들린다 — 실제 소켓을 거쳐도 세 요청이 동시에 발사된다는 사실과, 응답 순서가 지연이 짧은 순으로 온다는 순서는 매번 똑같다.)

## 함정: `await` 를 빼먹으면 조용히 사라진다

`create_task` 로 만든 태스크를 아무도 기다리지 않으면, 그 안에서 난 예외가 어디로도 보고되지 않는다.

```python title="swallowed.py"
import asyncio

async def background():
    await asyncio.sleep(0.1)
    raise ValueError("배경 작업에서 터진 에러")

async def main():
    task = asyncio.create_task(background())   # 결과를 한 번도 await 안 함
    await asyncio.sleep(0.3)
    print("main 끝 — 에러를 본 적이 없다")

asyncio.run(main())
```

```text nolines
main 끝 — 에러를 본 적이 없다
Task exception was never retrieved
future: <Task finished name='Task-2' coro=<background() done, ...
  exception=ValueError('배경 작업에서 터진 에러')>
Traceback (most recent call last):
  ...
ValueError: 배경 작업에서 터진 에러
```

::: danger 순서를 보라 — 에러가 프로그램이 끝난 뒤에야 나타난다
`"main 끝"` 이 **먼저** 찍히고, `Task exception was never retrieved` 는 그 뒤 — 태스크 객체가 가비지 컬렉션될 때 나타난다. `main` 은 `background` 가 던진 예외를 **한 번도 보지 못한 채** 정상 종료된 것처럼 진행한다. 실전에서 이건 "분명히 실패했는데 로그에 아무것도 안 남는" 장애로 나타난다.

**태스크를 만들었으면 반드시 `await` 하거나, `gather`/`TaskGroup` 으로 결과를 거둬라.** "그냥 실행만 시켜 두고 신경 안 쓸 것"처럼 보여도, 예외는 어딘가에서 반드시 확인돼야 한다. `TaskGroup` 을 쓰면 이 실수 자체가 구조적으로 막힌다 — [4.7 asyncio 실전](#/asyncio-advanced)에서 다룬다.
:::

## 요약

> `async def` 함수를 호출해도 몸통은 실행되지 않는다. **코루틴 객체 하나만 생긴다** — [1.18](#/iterators)의 제너레이터 객체와 같은 메커니즘이다. `await` 는 그 코루틴 체인을 타고 내려가 결국 `Future` 에 닿았을 때만 **진짜로 제어를 이벤트 루프에 반납**한다. `asyncio.run` 은 루프를 만들고 최상위 코루틴을 끝까지 돌리며, `create_task` 는 코루틴을 스케줄에 올리고, `gather` 는 여러 태스크의 완료를 순서대로 모은다. 이벤트 루프는 **단일 스레드**에서 협력적으로 작업을 번갈아 돌린다 — `await` 가 없는 코루틴은 끝날 때까지 루프를 독점한다. `sleep(0)` 은 실제로 쉬지 않고 딱 한 번 순서만 양보한다.

체크리스트:

- [ ] `hello()` 호출은 실행이 아니라 **코루틴 객체 생성**이다. `await`, `create_task`, `asyncio.run` 중 하나로 넘겨야 실행된다.
- [ ] 코루틴은 `send`/`throw`/`close` 를 그대로 가진 제너레이터다. 결과는 `StopIteration.value` 로 온다.
- [ ] `await` 는 실제 대기 지점(`Future`)에서만 이벤트 루프에 제어를 넘긴다. `await` 없는 `async def` 는 끝까지 독점 실행된다.
- [ ] `create_task` + `gather` 는 동시에 시작한다. 순서대로 `await` 하면 시간이 더해진다 — 실측 `0.301s` vs `0.417s`(둘 다 근사치, 기기마다 몇 ms씩 다르다).
- [ ] `sleep(0)` 은 CPU 작업을 쪼개 다른 태스크에 숨 쉴 틈을 주지만, 재개 비용 때문에 총 시간은 오히려 늘 수 있다.
- [ ] `create_task` 로 만든 태스크는 반드시 `await`/`gather` 로 거둬라. 안 그러면 예외가 조용히 사라진다.

::: quiz 연습문제
1. 다음 코드를 실행하기 **전에** 출력 순서와 대략적인 총 시간을 예측하라. 그리고 실행해 확인하라.

   ```python
   import asyncio, time

   async def task(name, delay):
       print(f"{name} 시작")
       await asyncio.sleep(delay)
       print(f"{name} 끝")

   async def main():
       await asyncio.gather(task("A", 0.2), task("B", 0.05), task("C", 0.1))

   start = time.perf_counter()
   asyncio.run(main())
   print(f"총 {time.perf_counter() - start:.2f}초")
   ```

2. 아래 함수를 `asyncio.run` 없이 직접 `send(None)` 으로 손으로 굴려서 반환값을 꺼내 보라. `try/except StopIteration` 을 써야 한다.

   ```python
   async def compute():
       return 1 + 1
   ```

3. `for i in range(50_000_000): pass` 만 있고 `await` 가 없는 `async def busy()` 를 두 개 태스크로 만들어 `gather` 하면, 로그를 안 찍어도 실행 시간이 순차 실행과 같은 이유를 설명하라.

4. 아래 코드는 태스크의 예외를 삼킨다. 두 가지 방법으로 고쳐라 — 하나는 `await task` 를 추가하는 방법, 다른 하나는 `asyncio.gather` 를 쓰는 방법.

   ```python
   async def risky():
       raise RuntimeError("문제 발생")

   async def main():
       asyncio.create_task(risky())
       await asyncio.sleep(0.1)
   ```

5. **깊이 생각해 볼 문제.** `asyncio.sleep(0)` 을 반복 호출하는 루프와, 아예 `await` 를 안 넣은 순수 계산 루프를 비교했을 때 왜 전자가 (1) 다른 태스크와 번갈아 실행되지만 (2) 총 실행 시간은 더 걸릴 수 있는지, 이 절에서 실측한 두 수치(`1.187s` vs `1.413s`)를 근거로 설명하라.
:::

**다음 절**: [4.7 asyncio 실전](#/asyncio-advanced) — `TaskGroup`, 취소, 타임아웃, 백프레셔.
