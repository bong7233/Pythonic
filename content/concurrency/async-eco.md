# 4.8 비동기 생태계

::: lead
[4.6 asyncio 기초](#/asyncio-basics)와 [4.7 asyncio 실전](#/asyncio-advanced)에서 코루틴과 이벤트 루프, `TaskGroup` 을 배웠다. 그런데 실전 코드는 `asyncio` 혼자 짜지 않는다. HTTP 요청을 보내야 하고, 파일을 읽어야 하고, 남이 만든 동기 라이브러리를 불러다 써야 한다. 문제는 파이썬 생태계의 태반이 **동기로 짜여 있다는 것**이다. `requests`, 대부분의 DB 드라이버, `PIL`, 거의 모든 과학 계산 라이브러리가 그렇다. 이 절은 그 동기 세계와 비동기 세계 사이의 국경을 다룬다. 국경을 잘못 넘으면 이벤트 루프 전체가 멎는다 — 이 절은 그 순간을 직접 눈으로 보여준다.
:::

## 왜 동기 라이브러리를 코루틴 안에 그냥 넣으면 안 되는가

`asyncio` 는 **협력적 멀티태스킹**(cooperative multitasking)이다. 하나의 OS 스레드 위에서, 코루틴들이 `await` 지점마다 자발적으로 제어권을 이벤트 루프에 반납하며 번갈아 실행된다. 핵심은 **자발적**이라는 단어다. 코루틴이 `await` 없이 시간을 잡아먹으면, 이벤트 루프는 그걸 끊고 다른 작업으로 넘어갈 방법이 없다. 강제로 빼앗는 선점형 스케줄러가 아니기 때문이다.

`requests.get()` 같은 동기 함수는 내부에서 블로킹 소켓 호출을 한다. 이건 `await` 가 아니다. 그냥 그 자리에서 멈춰 선다. 코루틴 안에 이런 함수를 넣으면 응답이 올 때까지 **이벤트 루프 전체가 얼어붙는다.** 다른 코루틴이 100개 대기 중이어도 소용없다.

말로만 하면 안 믿기니 직접 재본다. 0.5초짜리 블로킹 작업 하나를 실행하는 동안, 0.1초마다 찍히기로 한 "심장박동" 코루틴이 실제로 멈추는지 본다.

```python title="event_loop_freeze.py"
import asyncio
import time


def blocking_io(seconds: float) -> str:
    """동기 라이브러리가 하는 일을 흉내낸다 (예: requests.get, 동기 DB 드라이버)."""
    time.sleep(seconds)
    return f"{seconds}s 블로킹 작업 끝"


async def heartbeat(tag: str, ticks: int = 10, interval: float = 0.1):
    for i in range(ticks):
        print(f"  [{tag}] 심장박동 {i} @ {time.perf_counter():.2f}")
        await asyncio.sleep(interval)


async def bad_version():
    start = time.perf_counter()
    hb = asyncio.create_task(heartbeat("bad"))
    result = blocking_io(0.5)          # ❌ 이벤트 루프를 그대로 막는다
    print(f"  결과: {result}")
    await hb
    print(f"  전체 소요: {time.perf_counter() - start:.2f}s")
```

실행 결과다.

```text nolines
[bad] 심장박동 0 @ 119068.60   <- blocking_io(0.5)가 이미 끝난 뒤에야 첫 박동이 찍힌다
[bad] 심장박동 1 @ 119068.71
...
[bad] 심장박동 9 @ 119069.58
전체 소요: 1.59s
```

심장박동 0번이 `blocking_io` 가 끝난 **다음에야** 찍힌다. 0.5초 동안 `heartbeat` 태스크는 스케줄될 기회조차 얻지 못했다. `create_task` 로 태스크를 만들어도, 그 태스크가 실행되려면 현재 실행 중인 코루틴이 먼저 `await` 로 제어권을 넘겨야 한다. `blocking_io` 는 그걸 넘기지 않았다.

::: danger 이벤트 루프를 막는 흔한 범인
`time.sleep()`, `requests.get()`, 동기 psycopg2/pymysql 호출, `input()`, 무거운 CPU 연산(정렬, 이미지 처리) — 전부 `await` 없이 코루틴 안에서 실행되면 그 순간만큼은 **서버 전체가 다른 모든 요청을 멈춘다.** FastAPI 같은 프레임워크에서 `async def` 핸들러 안에 동기 DB 호출을 그대로 넣는 것은 실전에서 가장 흔한 사고 원인이다.
:::

## `asyncio.to_thread` — 블로킹을 다른 곳으로 치운다

해법은 단순하다. 블로킹 호출을 **별도의 OS 스레드**에 맡기고, 코루틴은 그 결과를 `await` 로 기다린다. 3.9부터 이 패턴이 `asyncio.to_thread()` 로 표준화됐다.

```python title="event_loop_freeze.py (계속)"
async def good_version():
    start = time.perf_counter()
    hb = asyncio.create_task(heartbeat("good"))
    result = await asyncio.to_thread(blocking_io, 0.5)  # ✅ 워커 스레드에서 실행
    print(f"  결과: {result}")
    await hb
    print(f"  전체 소요: {time.perf_counter() - start:.2f}s")
```

```text nolines
[good] 심장박동 0 @ 119069.69
[good] 심장박동 1 @ 119069.80
[good] 심장박동 2 @ 119069.90
[good] 심장박동 3 @ 119070.01
[good] 심장박동 4 @ 119070.12
결과: 0.5s 블로킹 작업 끝        <- 5번째 박동 직후, 블로킹 작업이 백그라운드에서 끝났다
[good] 심장박동 5 @ 119070.23
...
전체 소요: 1.09s
```

이번엔 심장박동이 **끊기지 않고** 계속 찍힌다. `blocking_io` 가 실행되는 0.5초 동안 다른 스레드가 그 일을 하고, 메인 스레드의 이벤트 루프는 계속 다른 코루틴을 돌린다. 전체 소요 시간도 1.59초에서 1.09초로 줄었다 — 블로킹 작업과 심장박동이 **겹쳐서** 실행됐기 때문이다.

(이 두 수치는 벤치마크라 실행할 때마다 0.02~0.06초 정도 흔들린다. 이 글을 쓰면서 다시 돌려 보니 `bad_version` 1.53s, `good_version` 1.04s가 나왔다 — 위 1.59s/1.09s와 자릿수·방향은 똑같고, 심장박동 0번이 `blocking_io` 종료 뒤에야 찍히는 현상도 재실행마다 그대로 재현됐다. 벤치마크 수치를 볼 때는 소수점 둘째 자리 하나하나보다 **이 차이가 매번 재현되는가**를 봐야 한다.)

::: deep to_thread는 사실 run_in_executor의 얇은 포장이다
`asyncio.to_thread(func, *args)` 는 내부적으로 `loop.run_in_executor(None, functools.partial(func, *args))` 를 호출할 뿐이다. `None` 을 넘기면 이벤트 루프가 **기본 스레드 풀**(default executor)을 쓴다. 이 풀의 크기는 직접 확인할 수 있다.

```pyrepl
>>> import asyncio
>>> async def main():
...     loop = asyncio.get_running_loop()
...     await loop.run_in_executor(None, lambda: None)  # 기본 executor를 강제로 생성
...     print(loop._default_executor._max_workers)
...
>>> asyncio.run(main())
20
```

이 컴퓨터는 논리 코어 16개다. 기본값 공식은 $\min(32,\ \text{cpu\_count} + 4)$ — $\min(32, 20) = 20$. 딱 맞는다. 스레드 풀이니 CPU 코어 수보다 많은 작업을 동시에 넘겨도 스레드가 대기하며 순서대로 처리한다. 다만 **일반 GIL 빌드에서는 스레드가 늘어도 CPU 연산 자체가 빨라지지 않는다** — 한 번에 파이썬 바이트코드를 실행하는 스레드는 여전히 하나뿐이다. `to_thread` 가 실제로 이득을 보는 것은 **블로킹되는 동안 GIL을 놓아주는 연산**(대부분의 I/O, `time.sleep`, C 확장의 블로킹 시스템 콜)이다. CPU를 실제로 많이 쓰는 순수 파이썬 코드라면 [4.3 GIL](#/gil)과 [4.4 multiprocessing](#/multiprocessing)을 봐야 한다.
:::

::: warn to_thread가 만능은 아니다
스레드 풀은 유한하다. 기본 20개짜리 풀에 21번째 블로킹 작업을 넘기면 **먼저 넣은 작업이 끝날 때까지 대기한다.** 초당 수백 건의 블로킹 호출을 처리해야 한다면 스레드 풀 자체가 병목이 된다. 이럴 땐 애초에 비동기 네이티브 라이브러리(`httpx`, `asyncpg`, `aiomysql`)로 바꾸는 게 근본 해법이다.
:::

## httpx — 비동기 HTTP 클라이언트

`requests` 는 `async def` 를 지원하지 않는다. 블로킹 소켓 위에 설계됐기 때문에 애초에 그럴 수가 없다. `httpx` 는 같은 API를 동기·비동기 양쪽으로 제공하는 라이브러리다. `Client` 대신 `AsyncClient` 를 쓰고, 메서드 앞에 `await` 를 붙이면 된다 — 나머지는 거의 동일하다.

```python title="httpx 동기 vs 비동기 API"
import httpx

# 동기
with httpx.Client() as client:
    r = client.get(url)

# 비동기 — 메서드 이름도 시그니처도 그대로, await만 붙는다
async with httpx.AsyncClient() as client:
    r = await client.get(url)
```

이 대칭성이 중요한 이유는 단순하다. **비동기라고 해서 요청 하나가 더 빨라지지 않는다.** 네트워크 왕복 시간은 그대로다. 비동기가 버는 것은 **여러 요청을 동시에 기다릴 수 있다**는 것뿐이다. 직접 재 보자. 외부 네트워크에 의존하지 않도록 로컬 `asyncio.start_server` 로 응답에 0.5초 걸리는 가짜 서버를 하나 띄우고, 같은 요청 5개를 순차로 보낼 때와 동시에 보낼 때를 비교한다.

```python title="httpx_concurrency.py"
import asyncio
import time
import httpx

DELAY = 0.5


async def handle(reader, writer):
    await reader.readuntil(b"\r\n\r\n")
    await asyncio.sleep(DELAY)               # 원격 API 호출을 흉내
    body = b"ok"
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
        b"Content-Length: " + str(len(body)).encode() +
        b"\r\nConnection: close\r\n\r\n" + body
    )
    await writer.drain()
    writer.close()


def sequential(url: str, n: int) -> float:
    start = time.perf_counter()
    with httpx.Client() as client:           # 동기 클라이언트
        for _ in range(n):
            client.get(url)
    return time.perf_counter() - start


async def concurrent(url: str, n: int) -> float:
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(client.get(url) for _ in range(n)))
    return time.perf_counter() - start
```

서버는 별도 스레드의 별도 이벤트 루프에서 돌려서, 클라이언트 쪽 동기·비동기 비교에만 집중했다. (서버와 클라이언트를 같은 루프에 넣으면 바로 위에서 본 "이벤트 루프가 멎는" 현상 때문에 동기 클라이언트가 서버 자신을 굶겨 죽인다 — 직접 겪어 본 함정이다.)

```text nolines
요청 5개, 요청당 서버 지연 0.5s
순차(동기 httpx.Client)      : 2.847s
동시(비동기 httpx.AsyncClient): 0.718s
배수: 4.0배
```

$5 \times 0.5\text{s} = 2.5\text{s}$ 에 근접한 순차 시간과, 거의 한 번의 왕복 시간에 수렴하는 동시 시간. 이게 I/O 바운드 작업에서 비동기가 버는 전부다. **CPU 연산이 아니라 대기 시간을 겹치는 것.**

(이것도 재실행하면 조금씩 흔들린다. 다시 재 보니 순차 2.820s, 동시 0.736s, 배수 3.8배가 나왔다 — 위 2.847s/0.718s/4.0배와 자릿수·방향이 같다. 순차는 항상 $2.5\text{s}$ 남짓에, 동시는 항상 $0.5\sim0.7\text{s}$대에 머문다는 게 핵심이지 소수점 하나가 핵심이 아니다.)

::: perf 클라이언트를 재사용하라 — 52배 차이
`AsyncClient` 는 내부에 커넥션 풀을 들고 있다. 매 요청마다 새로 만들면 그 풀도 매번 새로 만들어지고 버려진다. 같은 로컬 서버에 지연 없이(응답 즉시) 200번 요청을 보내서 재 봤다.

```text nolines
요청 200회
매번 새 AsyncClient : 38.642s
클라이언트 재사용    : 0.740s
배수: 52.2배
```

(Python 3.14.5 / Windows / 로컬 루프백 기준 실측. 절대값은 기기와 OS의 소켓 처리 방식에 따라 크게 갈리지만, **한 요청마다 클라이언트를 새로 만들면 안 된다는 결론**은 어디서나 같다. 실제로 이 실험을 다시 돌려 보니 매번 새로 만드는 쪽이 41.725s, 재사용하는 쪽이 0.719s로 배수가 58.1배까지 벌어졌다 — 위 38.642s/0.740s/52.2배와 자릿수는 같지만 절대 배수는 수십 배 단위에서 그때그때 크게 움직인다는 뜻이다. 이 실험에서 믿을 건 "수십 배 차이가 난다"는 결론이지 "정확히 52.2배"라는 숫자가 아니다.) 요청 함수 하나짜리 스크립트를 짤 때 `async with httpx.AsyncClient() as client:` 를 함수 안에 넣는 게 제일 흔한 실수다. 클라이언트는 애플리케이션 생명주기 동안 **하나만 만들어 재사용**해야 한다.
:::

`AsyncClient` 도 기본 동시 연결 수 제한(`httpx.Limits`)이 있다. 요청을 수천 개씩 한꺼번에 `gather` 로 던지면 다 동시에 나가는 게 아니라 풀 크기만큼만 동시에 나가고 나머지는 대기한다. 요청 수를 실제로 제한하고 싶다면 `asyncio.Semaphore` 를 직접 씌우는 패턴이 흔하다. 취소·타임아웃·배압(backpressure)을 구조적으로 다루는 법은 [4.7 asyncio 실전](#/asyncio-advanced)에서 다뤘다.

## sync와 async의 경계를 넘나드는 실전 패턴

지금까지는 "비동기 코드에서 블로킹 코드를 어떻게 다루는가"였다. 반대 방향도 있다. **동기 스레드에서 이벤트 루프로 다시 들어가야 하는 경우**다. 콜백 기반 레거시 라이브러리가 진행 상황을 알려줄 때, 그 콜백은 보통 워커 스레드에서 호출된다.

여기서 실수하기 쉬운 게 하나 있다. "코루틴을 그냥 호출하면 실행되겠지"라는 생각이다. 아니다. 코루틴 함수를 호출하면 **코루틴 객체가 생성될 뿐, 아무것도 실행되지 않는다.**

```pyrepl
>>> import asyncio
>>> async def fetch():
...     await asyncio.sleep(0.1)
...     return 42
...
>>> async def main():
...     result = fetch()          # await를 빠뜨렸다
...     print(type(result), result)
...
>>> asyncio.run(main())
<stdin>:2: RuntimeWarning: coroutine 'fetch' was never awaited
<class 'coroutine'> <coroutine object fetch at 0x000001D0D99E5F00>
```

`await` 를 빠뜨리면 예외가 나지 않는다. 그냥 `<coroutine object ...>` 를 손에 쥐고 아무 일도 안 일어난다. 파이썬은 이걸 알아채고 나중에 그 객체가 가비지 컬렉션될 때 `RuntimeWarning` 으로 경고해 줄 뿐이다. **CI에서 이 경고를 에러로 승격시켜라.** 조용히 넘어가면 실전에서 "왜 이 요청이 전송이 안 됐지"로 몇 시간을 날린다.

경고 메시지의 위치 표기(`<stdin>:2:`)는 진짜 대화형 REPL에 한 줄씩 직접 타이핑했을 때 나오는 표기다. 파일로 실행하거나(`python script.py`), 입력을 파이프로 흘려 넣거나, 비대화형으로 재현하면 파이썬이 코루틴 객체를 실제로 회수하는 시점이 이벤트 루프 내부이기 때문에 위치가 `asyncio` 자체의 소스 파일(예: `events.py`의 특정 줄)로 찍힐 수 있다. `RuntimeWarning: coroutine '...' was never awaited` 라는 문구와 `<class 'coroutine'>` 객체가 출력된다는 사실 자체는 실행 방식과 무관하게 항상 재현된다 — 달라지는 건 위치 표기뿐이다.

워커 스레드에서 코루틴을 실행하려는 또 다른 실수는 그 스레드 안에서 `asyncio.run()` 을 다시 부르는 것이다. 이미 실행 중인 루프 안에서 `asyncio.run()` 을 부르면 이렇게 죽는다.

```pyrepl
>>> import asyncio
>>> async def inner():
...     return 1
...
>>> async def main():
...     result = asyncio.run(inner())   # 이미 루프 안인데 또 run()을?
...     print(result)
...
>>> asyncio.run(main())
Traceback (most recent call last):
  ...
RuntimeError: asyncio.run() cannot be called from a running event loop
```

::: danger asyncio.run()은 진입점에 딱 한 번만
`asyncio.run()` 은 프로그램 전체에서 **최상위 진입점 하나에만** 쓴다. 이미 루프가 돌고 있는 곳(코루틴 내부, 다른 스레드가 아닌 같은 스레드)에서 다시 부르면 위 에러가 난다. 코루틴 안에서 다른 코루틴을 실행하고 싶으면 그냥 `await` 하면 된다.
:::

**진짜 정답**은 `asyncio.run_coroutine_threadsafe()` 다. 메인 스레드의 이벤트 루프 객체를 워커 스레드에 넘겨 두면, 워커 스레드는 그 루프에 코루틴을 안전하게 "예약"할 수 있다.

```python title="sync_to_async_bridge.py"
import asyncio
import threading
import time


async def report_progress(pct: int):
    print(f"  [progress] {pct}%")


def legacy_worker(loop: asyncio.AbstractEventLoop):
    """다른 스레드에서 도는 동기 코드. loop는 메인 스레드의 이벤트 루프."""
    for pct in (25, 50, 75, 100):
        time.sleep(0.1)
        fut = asyncio.run_coroutine_threadsafe(report_progress(pct), loop)
        fut.result(timeout=1)          # 완료까지 기다려 순서를 보장 (선택)


async def main():
    loop = asyncio.get_running_loop()
    await asyncio.to_thread(legacy_worker, loop)
```

```text nolines
[progress] 25%
[progress] 50%
[progress] 75%
[progress] 100%
```

이게 **경계를 넘는 두 방향**을 완성한다.

| 방향 | 도구 | 언제 |
| --- | --- | --- |
| 비동기 → 동기 | `asyncio.to_thread(func, ...)` | 코루틴 안에서 블로킹 함수를 호출해야 할 때 |
| 동기 → 비동기 | `asyncio.run_coroutine_threadsafe(coro, loop)` | 워커 스레드에서 이벤트 루프에 결과를 보고해야 할 때 |

::: tip 실전 패턴 — 동기 프레임워크 안에서 비동기 클라이언트 쓰기
Flask 같은 WSGI 기반 동기 프레임워크의 요청 핸들러(동기 함수) 안에서 `httpx.AsyncClient` 를 쓰고 싶다면, 매 요청마다 `asyncio.run()` 으로 새 루프를 만드는 게 제일 단순하다. 다만 이건 매번 이벤트 루프를 새로 만드는 비용이 붙는다 — 커넥션 풀도 요청마다 새로 생긴다는 뜻이라 위에서 본 52배 함정을 그대로 만난다. 요청량이 많다면 처음부터 FastAPI/Starlette 같은 ASGI 프레임워크로 가는 게 정답에 가깝다. "동기 프레임워크에 비동기를 끼워 넣기"는 임시방편이지 설계가 아니다.
:::

## aiofiles — 파일 I/O도 결국 스레드풀이다

`aiofiles` 는 `open()` 을 비동기 컨텍스트 매니저로 감싼 라이브러리다. 사용법은 짐작한 그대로다.

```python title="aiofiles_demo.py"
import aiofiles


async def write_and_read():
    async with aiofiles.open("data.txt", "w") as f:
        await f.write("hello async file\n" * 1000)

    async with aiofiles.open("data.txt", "r") as f:
        content = await f.read()
    return len(content)
```

```pyrepl
>>> import asyncio
>>> asyncio.run(write_and_read())
17000
```

::: deep aiofiles의 정체 — to_thread와 완전히 같은 트릭
운영체제 대부분에서 **파일 시스템 I/O는 진짜 비동기 API가 없다.** (리눅스의 `io_uring` 정도가 예외지만 표준 라이브러리 수준에서 널리 쓰이진 않는다.) 그래서 `aiofiles` 가 하는 일은 마법이 아니다. 소스를 까 보면 이렇게 돼 있다.

```python title="aiofiles/threadpool/utils.py (실제 소스)"
def _make_delegate_method(attr_name):
    async def method(self, *args, **kwargs):
        cb = functools.partial(getattr(self._file, attr_name), *args, **kwargs)
        return await self._loop.run_in_executor(self._executor, cb)
    return method
```

`f.write()`, `f.read()` 호출 하나하나가 내부적으로 **평범한 동기 파일 객체 메서드를 스레드 풀에 넘기고 기다리는 것**이다. 방금 위에서 본 `asyncio.to_thread` 와 정확히 같은 메커니즘이다. 그러니 `aiofiles` 를 쓴다고 파일 I/O 자체가 빨라지지 않는다. 얻는 것은 **파일을 읽는 동안 다른 코루틴이 이벤트 루프를 계속 쓸 수 있다는 것**뿐이다. 스레드 하나를 옮겨 쓰는 값이 있으니, 아주 작은 설정 파일 하나를 여닫는 정도라면 그냥 동기 `open()` 을 쓰는 편이 스레드 전환 오버헤드도 없고 더 빠르다. `aiofiles` 는 **파일 I/O가 자주, 크게 일어나서 이벤트 루프를 막을 만한** 상황에서만 값어치를 한다.
:::

::: note anyio, trio는 어떤가
`asyncio` 만 있는 게 아니다. `trio` 는 구조적 동시성(structured concurrency)을 처음부터 언어로 강제한 대안 이벤트 루프이고, `anyio` 는 `asyncio`/`trio` 위에서 동작하는 공통 추상 계층이다. `httpx`, `starlette` 같은 라이브러리가 내부적으로 `anyio` 를 쓸 수 있게 설계돼 있다. 다만 실무에서 표준 선택은 여전히 `asyncio` 다. `trio` 의 구조적 동시성 아이디어 상당수는 이미 [4.7 asyncio 실전](#/asyncio-advanced)의 `TaskGroup` 으로 `asyncio` 본체에 들어왔다.
:::

## 협력적 스케줄링의 뿌리 — 제너레이터와의 관계

`async def` 와 `await` 는 파이썬 3.5에서 새 문법으로 들어왔지만, 그 실행 모델은 새로운 게 아니다. [1.18 이터레이터와 제너레이터](#/iterators)에서 본 제너레이터의 `send()` 메서드가 코루틴의 원형이다. 제너레이터가 `yield` 에서 멈췄다가 `send()` 로 재개되듯, 코루틴은 `await` 에서 멈췄다가 이벤트 루프가 다시 스케줄할 때 재개된다. `bad_version()` 이 `blocking_io` 때문에 멈춰 선 것도 결국 **제어권을 넘길 지점 자체가 없었기 때문**이다. `time.sleep()` 안에는 `yield` 도 `await` 도 없다 — 이터레이터 프로토콜 바깥에서 시간을 다 써 버린 것이다.

이 관점에서 보면 [4.2 threading](#/threading)과의 차이도 선명해진다. 스레드는 OS가 강제로 스케줄을 뺏는 **선점형**이고, 코루틴은 스스로 넘겨야 하는 **협력형**이다. 협력형이라 경쟁 상태(race condition)에 대한 걱정이 훨씬 적지만, 그 대가로 **누군가 `await` 를 빼먹으면 프로그램 전체가 멎는다.** 이 절 첫머리의 실험이 바로 그 대가를 보여준 것이다.

## 요약

- `asyncio` 는 협력적 스케줄링이다. `await` 없는 코루틴은 제어권을 넘기지 않고, 그 시간만큼 이벤트 루프 전체가 멎는다 — 실측으로 1.59초 대 1.09초 차이를 봤다.
- 블로킹 함수는 `asyncio.to_thread()` 로 감싸 별도 스레드에 맡긴다. 이건 `loop.run_in_executor(None, ...)` 의 얇은 포장이고, 기본 스레드 풀 크기는 $\min(32, \text{cpu\_count}+4)$ 다.
- `httpx.AsyncClient` 는 `requests` 의 비동기 버전이다. 비동기가 버는 건 요청 하나의 속도가 아니라 **여러 요청의 대기 시간을 겹치는 것**이고, 5개 동시 요청에서 실측 4.0배를 봤다.
- `AsyncClient` 는 반드시 재사용하라. 매번 새로 만들면 커넥션 풀도 매번 새로 만들어져 52배 느려지는 걸 직접 쟀다.
- 코루틴 함수를 `await` 없이 호출하면 코루틴 객체만 생기고 아무 일도 안 일어난다. `asyncio.run()` 은 최상위 진입점 하나에만 쓴다 — 실행 중인 루프 안에서 또 부르면 `RuntimeError` 다.
- 동기 스레드에서 이벤트 루프로 다시 들어가려면 `asyncio.run_coroutine_threadsafe()` 를 쓴다.
- `aiofiles` 도 결국 파일 메서드를 스레드 풀에 넘기는 `to_thread` 와 같은 트릭이다. 파일 I/O가 이벤트 루프를 막을 만큼 크고 잦을 때만 쓸 가치가 있다.

::: quiz 연습문제
1. 다음 코드를 실행하면 콘솔에 아무것도 안 찍히고 프로그램이 즉시 끝난다. 왜인지 이 절의 지식으로 설명하고 고쳐라.

   ```python
   async def greet():
       print("hello")

   async def main():
       greet()

   asyncio.run(main())
   ```

2. `httpx.AsyncClient` 를 함수 안에서 매번 새로 만드는 코드와, 모듈 레벨에서 하나만 만들어 재사용하는 코드를 각각 짜서 100번 요청을 보내 걸리는 시간을 직접 재 보라. 이 절의 52배와 자릿수가 비슷하게 나오는지 확인하라.

3. `asyncio.to_thread(time.sleep, 3)` 을 동시에 25개 던지면 어떻게 될지 예측하라. 기본 스레드 풀 크기가 20이라는 걸 감안해서, 전체 소요 시간이 대략 몇 초일지 계산하고 실제로 실행해 확인하라.

4. 워커 스레드 안에서 `asyncio.run_coroutine_threadsafe()` 없이 코루틴 객체를 그냥 만들기만 하면 무슨 일이 일어나는가? `RuntimeWarning` 이 뜨는 지점을 직접 재현하라.

5. **생각해 볼 문제.** `aiofiles` 로 1GB짜리 파일 하나를 읽는 것과, `asyncio.to_thread(open(...).read)` 로 읽는 것은 성능이 어떻게 다를까. 이 절의 aiofiles 소스 코드를 근거로 답하라.
:::

**다음 절**: [4.9 서브인터프리터 (PEP 734)](#/subinterpreters) — GIL도 스레드도 아닌 세 번째 병렬 실행 축은 실제로 무엇을 해결하는가.
