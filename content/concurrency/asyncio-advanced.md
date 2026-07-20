# 4.7 asyncio 실전

::: lead
[4.6 asyncio 기초](#/asyncio-basics)에서 코루틴과 이벤트 루프가 무엇인지 봤다면, 이 절에서는 실전에서 반드시 마주치는 세 가지 문제를 다룬다. 여러 코루틴을 동시에 돌리다가 하나가 실패하면 나머지는 어떻게 되는가, 오래 걸리는 작업을 어떻게 강제로 멈추는가, 그리고 동시에 너무 많이 돌리지 않으려면 어떻게 제한하는가. 전부 "말로 설명하면 그럴듯하지만 실제로는 다르게 동작하는" 영역이다. 그래서 이 절의 모든 주장은 실행한 로그로 증명한다.
:::

## gather의 문제와 TaskGroup의 등장

`asyncio.gather()` 로 여러 코루틴을 동시에 돌려본 적이 있을 것이다. 잘 동작할 때는 문제가 없다. 문제는 하나가 실패했을 때다. `gather` 는 기본적으로 첫 예외가 뜨는 즉시 그 예외를 밖으로 던지지만, **나머지 태스크를 취소하지는 않는다.** 백그라운드에서 계속 돈다. `return_exceptions=True` 를 주면 예외를 모으긴 하지만, 이번엔 반대로 "무엇 하나가 실패해도 나머지는 계속 실행해야 한다"는 것을 코드로 명시해야 하고, 실패를 판단하는 책임이 호출자에게 넘어간다.

3.11에서 추가된 `asyncio.TaskGroup` 은 이 문제를 구조적으로 푼다. 규칙은 단순하다.

> **`async with TaskGroup()` 블록 안에서 만든 모든 태스크가 끝나야 블록을 빠져나간다. 하나라도 실패하면 나머지는 전부 취소된다.**

이걸 **구조적 동시성**(structured concurrency)이라고 부른다. 태스크의 생애가 코드 블록의 생애에 묶인다는 뜻이다. 함수를 호출하면 그 함수가 끝날 때까지 기다리는 게 당연하듯, 태스크 그룹도 그 블록이 끝날 때까지 모든 자식 태스크의 종료를 보장한다. 블록 밖으로 태스크가 "새어나가는" 일이 없다.

```python title="TaskGroup 기본 사용"
import asyncio
import time


async def worker(name, delay):
    print(f"[{time.perf_counter():.3f}] {name} 시작")
    await asyncio.sleep(delay)
    print(f"[{time.perf_counter():.3f}] {name} 끝 ({delay}초)")
    return f"{name} 결과"


async def main():
    start = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(worker("A", 1.0))
        t2 = tg.create_task(worker("B", 0.5))
        t3 = tg.create_task(worker("C", 1.5))
    print(f"전체 소요: {time.perf_counter() - start:.3f}초")
    print(t1.result(), t2.result(), t3.result())


asyncio.run(main())
```

실행 결과다.

```text
[118975.057] A 시작
[118975.057] B 시작
[118975.057] C 시작
[118975.564] B 끝 (0.5초)
[118976.060] A 끝 (1.0초)
[118976.571] C 끝 (1.5초)
전체 소요: 1.514초
A 결과 B 결과 C 결과
```

세 태스크가 **동시에 시작**했고(타임스탬프가 전부 같다), 전체 소요 시간은 가장 오래 걸린 C의 1.5초와 거의 같다(1.0 + 0.5 + 1.5 = 3.0초가 아니다). 순차 실행이 아니라 진짜 동시 실행이라는 뜻이다. `TaskGroup` 을 빠져나온 뒤에야 `t1.result()` 를 안전하게 호출할 수 있다 — 이 시점엔 모든 태스크가 이미 끝났다고 보장되기 때문이다.

::: note gather도 여전히 쓸모가 있다
결과 리스트를 순서대로 받고 싶고, 실패 시 나머지를 취소할 필요가 없는 단순한 경우엔 `asyncio.gather()` 가 더 짧다. `TaskGroup` 은 **실패 시 취소가 필요할 때**, 그리고 **여러 예외를 모아서 보고**해야 할 때 확실한 우위를 가진다.
:::

## 취소가 실제로 어떻게 전파되는가

`task.cancel()` 을 호출하면 정확히 무슨 일이 일어나는가? 많은 사람이 "그 태스크가 즉시 멈춘다"고 생각하는데, 틀렸다. **다음번 await 지점에서 `CancelledError` 가 발생한다.** 태스크는 이 예외를 자유롭게 처리할 수 있고, 자유롭게 무시할 수도 있다 — 정말로.

```python title="취소 전파 관찰"
import asyncio


async def child():
    try:
        print("child: 시작, 5초 대기 진입")
        await asyncio.sleep(5)
        print("child: 여기 도달하면 안 됨")
    except asyncio.CancelledError:
        print("child: CancelledError 받음, 정리 시작")
        await asyncio.sleep(0.1)  # 정리 작업 흉내
        print("child: 정리 끝, 재전파")
        raise


async def parent():
    task = asyncio.create_task(child())
    await asyncio.sleep(0.3)
    print("parent: task.cancel() 호출")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("parent: task가 취소됨을 확인 (CancelledError 전파됨)")
    print(f"parent: task.cancelled() = {task.cancelled()}")


asyncio.run(parent())
```

```text
child: 시작, 5초 대기 진입
parent: task.cancel() 호출
child: CancelledError 받음, 정리 시작
child: 정리 끝, 재전파
parent: task가 취소됨을 확인 (CancelledError 전파됨)
parent: task.cancelled() = True
```

여기서 두 가지가 중요하다. 첫째, `cancel()` 은 **요청**이지 즉발 종료가 아니다. `child` 가 `await asyncio.sleep(5)` 에서 멈춰 있다가, 그 지점에서 `CancelledError` 가 발생한 것이다. 둘째, `except` 블록 안에서도 `await` 를 쓸 수 있다 — 정리 작업(파일 닫기, 연결 해제)을 위한 유예 시간이다. 다만 **`raise` 로 다시 던져야 한다.** 이건 [1.16 예외와 예외 그룹](#/exceptions)에서 본 예외 체이닝과 같은 원리다: 예외를 잡았다고 해서 삼켜도 된다는 뜻은 아니다.

::: danger CancelledError를 삼키면 취소가 조용히 무효화된다
```python
import asyncio


async def bad_child():
    try:
        await asyncio.sleep(5)
    except asyncio.CancelledError:
        print("bad_child: 취소 신호를 삼켰다 (재전파 안 함)")
        return "그래도 결과를 반환"  # 취소를 무시했다


async def main():
    task = asyncio.create_task(bad_child())
    await asyncio.sleep(0.2)
    task.cancel()
    result = await task  # 예외 대신 결과가 온다!
    print("main: task.cancelled() =", task.cancelled())
    print("main: 받은 결과 =", result)


asyncio.run(main())
```

실제 실행 결과다.

```text
bad_child: 취소 신호를 삼켰다 (재전파 안 함)
main: task.cancelled() = False
main: 받은 결과 = 그래도 결과를 반환
```

`cancel()` 을 호출한 쪽은 태스크가 취소됐다고 믿고 다음 로직을 짜지만, 실제로는 **정상 종료**로 처리된다. `task.cancelled()` 가 `False` 다. 타임아웃으로 강제 종료하려던 작업이 배경에서 계속 결과를 반환하며 살아남는 버그가 이렇게 생긴다. `CancelledError` 를 잡을 땐 로그를 남기거나 정리를 하는 것까지만 하고, **반드시 `raise` 로 다시 던져라.**
:::

## asyncio.timeout — 타임아웃도 결국 취소다

3.11부터는 `asyncio.timeout()` 컨텍스트 매니저로 타임아웃을 건다. 내부적으로 하는 일은 방금 본 취소와 정확히 같다: 시간이 다 되면 블록 안에서 실행 중인 태스크에 `cancel()` 을 건다.

```python title="타임아웃 실측"
import asyncio
import time


async def slow_query():
    await asyncio.sleep(2.0)
    return "결과"


async def main():
    start = time.perf_counter()
    try:
        async with asyncio.timeout(0.5):
            result = await slow_query()
            print("성공:", result)
    except TimeoutError:
        print(f"[{time.perf_counter() - start:.3f}] TimeoutError 발생 (0.5초 제한)")

    # 중첩 타임아웃: 바깥이 더 짧으면 바깥이 이긴다
    start = time.perf_counter()
    try:
        async with asyncio.timeout(1.0):
            async with asyncio.timeout(5.0):
                await asyncio.sleep(3.0)
    except TimeoutError:
        print(f"[{time.perf_counter() - start:.3f}] 바깥 타임아웃(1.0초)이 먼저 걸림")


asyncio.run(main())
```

```text
[0.508] TimeoutError 발생 (0.5초 제한)
[1.012] 바깥 타임아웃(1.0초)이 먼저 걸림
```

0.5초로 건 타임아웃이 정확히 그 근처에서 걸렸다. 두 번째 케이스는 5초짜리 안쪽 타임아웃이 1초짜리 바깥 타임아웃에 감싸여 있는데, **바깥쪽이 먼저 만료되면 바깥쪽이 이긴다** — 각 `timeout()` 은 독립적으로 자기 마감을 감시하고, 먼저 온 것이 취소를 건다.

::: deep TimeoutError는 파이썬 내장 예외다
3.11부터 `asyncio.TimeoutError` 는 내장 `TimeoutError` 의 별칭이다.

```pyrepl
>>> import asyncio
>>> asyncio.TimeoutError is TimeoutError
True
```

3.10 이전에는 `asyncio.TimeoutError` 가 별개의 클래스였다. `except TimeoutError` 하나로 `asyncio.timeout()`, 소켓 타임아웃, `concurrent.futures.TimeoutError` 계열까지 넓게 잡을 수 있게 정리된 것이다. 옛날 코드에서 `except asyncio.TimeoutError` 를 보면 그대로 둬도 되지만, 새 코드는 그냥 `TimeoutError` 를 쓴다.
:::

`asyncio.wait_for()` 와 뭐가 다른가 궁금할 수 있다. `wait_for` 는 **태스크 하나**에 타임아웃을 걸지만, `timeout()` 은 **블록 전체**에 건다. 블록 안에 `TaskGroup` 이 있든 여러 개의 `await` 가 순차적으로 있든 상관없이 전체 경과 시간을 하나의 마감으로 감시한다. 여러 단계로 나뉜 작업(연결 → 인증 → 조회)에 타임아웃 하나로 우산을 씌우고 싶을 때 `timeout()` 이 훨씬 자연스럽다.

## TaskGroup: 하나가 실패하면 전부 취소된다

이제 TaskGroup의 핵심 동작을 직접 확인한다. 자식 태스크 중 하나가 예외를 던지면 나머지는 **자동으로 취소**된다. 명시적으로 취소 코드를 쓸 필요가 없다.

```python title="하나의 실패가 전체를 취소시킨다"
import asyncio
import time


async def ok_worker(name, delay):
    try:
        print(f"[{time.perf_counter():.3f}] {name} 시작 ({delay}초 대기 예정)")
        await asyncio.sleep(delay)
        print(f"[{time.perf_counter():.3f}] {name} 정상 종료")
        return name
    except asyncio.CancelledError:
        print(f"[{time.perf_counter():.3f}] {name} 취소됨 (아직 {delay}초 안 지남)")
        raise


async def bad_worker(delay):
    print(f"[{time.perf_counter():.3f}] BAD 시작 ({delay}초 후 예외)")
    await asyncio.sleep(delay)
    raise ValueError("BAD가 터졌다")


async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(ok_worker("A", 3.0))
            tg.create_task(ok_worker("B", 3.0))
            tg.create_task(bad_worker(0.3))
    except* ValueError as eg:
        print("main: ExceptionGroup 잡음:", [str(e) for e in eg.exceptions])


asyncio.run(main())
```

```text
[118999.885] A 시작 (3.0초 대기 예정)
[118999.885] B 시작 (3.0초 대기 예정)
[118999.885] BAD 시작 (0.3초 후 예외)
[119000.195] A 취소됨 (아직 3.0초 안 지남)
[119000.195] B 취소됨 (아직 3.0초 안 지남)
main: ExceptionGroup 잡음: ['BAD가 터졌다']
```

A와 B는 3초를 기다릴 예정이었지만, 0.3초 만에 BAD가 예외를 던지자 **곧바로 취소됐다.** 3초를 다 채우지 않았다. `TaskGroup` 이 자동으로 나머지 자식들에게 `cancel()` 을 건 것이다. 그리고 바깥으로 나온 예외는 평범한 `ValueError` 가 아니라 `ExceptionGroup` 이다 — 자식이 여러 개 동시에 실패할 수 있으므로, 하나의 예외로는 전부를 표현할 수 없기 때문이다. 이걸 받는 문법이 `except*` 이고, [1.16 예외와 예외 그룹](#/exceptions)에서 다룬 그 문법이다.

::: warn 자식이 둘 다 실패하면 ExceptionGroup에 둘 다 담긴다
`bad_worker` 를 두 개 동시에 실패하게 만들면 `eg.exceptions` 의 길이가 2가 된다. `try/except ValueError` 처럼 단일 예외로 잡으려 하면 놓친다. 여러 실패 원인을 한꺼번에 취급해야 하는 게 동시성 코드의 기본값이라고 생각하는 게 안전하다.
:::

## 세마포어로 백프레셔 걸기

동시에 too many 태스크를 만들면 문제가 생긴다. 외부 API를 호출하는 코드라면 rate limit에 걸리고, DB 커넥션 풀을 쓰는 코드라면 풀이 고갈된다. `TaskGroup` 자체는 몇 개까지 동시에 실행할지 제한하지 않는다 — **의도적으로 던진 만큼 전부 동시에 시작한다.**

**백프레셔**(backpressure)는 상류가 하류의 처리 속도에 맞춰 스스로 속도를 늦추는 것을 말한다. asyncio에서 가장 간단한 구현이 `asyncio.Semaphore` 다. 정해진 수의 "허가증"만 발급하고, 허가증이 없으면 태스크는 `await sem.acquire()` 에서 잠들어 순서를 기다린다.

```python title="세마포어 유무 비교"
import asyncio
import time

active = 0
peak = 0


async def call_fake_api(i, sem=None):
    global active, peak
    if sem is not None:
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.2)
            active -= 1
    else:
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.2)
        active -= 1


async def run(sem, label):
    global active, peak
    active = 0
    peak = 0
    start = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        for i in range(20):
            tg.create_task(call_fake_api(i, sem))
    elapsed = time.perf_counter() - start
    print(f"{label}: 동시 최고 {peak}개, 총 소요 {elapsed:.3f}초")


async def main():
    await run(None, "세마포어 없음 (제한 없음)")
    await run(asyncio.Semaphore(5), "세마포어 5로 제한")


asyncio.run(main())
```

```text
세마포어 없음 (제한 없음): 동시 최고 20개, 총 소요 0.201초
세마포어 5로 제한: 동시 최고 5개, 총 소요 0.813초
```

숫자가 정직하게 그 트레이드오프를 보여준다. 제한이 없으면 20개가 한꺼번에 몰려서 0.2초(가짜 API 한 번의 지연) 만에 끝난다 — 그런데 실제 서버라면 이 20개 동시 요청이 그대로 부하가 된다. 세마포어로 5개까지만 허용하면 20개를 5개씩 4묶음으로 나눠 처리하므로 대략 `4 × 0.2 = 0.8초` 가 걸린다. 실측값 0.813초가 정확히 이 계산과 맞는다. **동시성을 줄이는 대신 처리량이 예측 가능해진다.**

::: cote 코딩테스트/실무 감각
힙으로 "k개의 자원을 유지하며 최댓값/최솟값을 뽑는" 문제를 [7.8 힙과 우선순위 큐](#/heap)에서 풀어봤다면, 세마포어의 역할이 비슷하게 느껴질 것이다 — **동시에 살아있는 것의 개수를 정해진 한도로 유지**한다는 점에서. 다만 힙은 자료구조이고 세마포어는 동기화 프리미티브라는 차이가 있다.
:::

::: tip 세마포어는 몇으로 잡아야 하나
정답은 없다. 외부 서비스의 rate limit 문서를 보고 그 이하로 잡거나, DB 커넥션 풀 크기와 맞추거나, 직접 여러 값으로 실측해서 처리량이 꺾이는 지점을 찾는다. `TaskGroup` + `Semaphore` 조합이 이런 실험을 몇 줄로 가능하게 해 준다는 게 핵심이다.
:::

## 흔한 실수: 블로킹 코드가 이벤트 루프를 멈춘다

asyncio에서 가장 흔하고, 가장 알아채기 어려운 실수다. **`async def` 로 감쌌다고 그 안의 코드가 자동으로 논블로킹이 되는 게 아니다.** `time.sleep()`, 동기 `requests.get()`, CPU를 오래 쓰는 계산 — 이런 것들은 `await` 가 없으므로 이벤트 루프에게 제어권을 넘기지 않는다. **이벤트 루프는 단일 스레드에서 도는 협력적 스케줄러**다. 코루틴이 스스로 양보(`await`)하지 않으면 다른 코루틴은 실행될 기회조차 얻지 못한다. [4.6 asyncio 기초](#/asyncio-basics)에서 본 "이벤트 루프" 개념이 여기서 실전 버그로 돌아온다.

직접 재현해 본다. 0.2초마다 하트비트를 찍는 태스크와, 함께 도는 작업 하나를 붙인다.

```python title="블로킹 vs 논블로킹 비교"
import asyncio
import time


async def heartbeat():
    for i in range(6):
        print(f"[{time.perf_counter():.3f}] 하트비트 {i}")
        await asyncio.sleep(0.2)


async def bad_blocking_job():
    print(f"[{time.perf_counter():.3f}] bad_job: time.sleep(1) 시작 (블로킹)")
    time.sleep(1.0)          # 이벤트 루프를 통째로 멈춘다
    print(f"[{time.perf_counter():.3f}] bad_job: 끝")


async def good_job():
    print(f"[{time.perf_counter():.3f}] good_job: asyncio.sleep(1) 시작")
    await asyncio.sleep(1.0)
    print(f"[{time.perf_counter():.3f}] good_job: 끝")


async def main():
    print("=== 블로킹 버전 (time.sleep) ===")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(heartbeat())
        tg.create_task(bad_blocking_job())

    print("\n=== 논블로킹 버전 (asyncio.sleep) ===")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(heartbeat())
        tg.create_task(good_job())


asyncio.run(main())
```

```text
=== 블로킹 버전 (time.sleep) ===
[119042.251] 하트비트 0
[119042.251] bad_job: time.sleep(1) 시작 (블로킹)
[119043.251] bad_job: 끝
[119043.251] 하트비트 1
[119043.455] 하트비트 2
[119043.658] 하트비트 3
[119043.860] 하트비트 4
[119044.064] 하트비트 5

=== 논블로킹 버전 (asyncio.sleep) ===
[119044.268] 하트비트 0
[119044.268] good_job: asyncio.sleep(1) 시작
[119044.472] 하트비트 1
[119044.678] 하트비트 2
[119044.882] 하트비트 3
[119045.086] 하트비트 4
[119045.274] good_job: 끝
[119045.290] 하트비트 5
```

증거가 타임스탬프에 그대로 남는다. 블로킹 버전에서는 **하트비트 0**을 찍은 직후 `time.sleep(1)` 이 시작되고, 정확히 1초 뒤 `bad_job` 이 끝나고 나서야 **하트비트 1**이 찍힌다. 그 사이 0.2초, 0.4초, 0.6초, 0.8초 지점에서 찍혔어야 할 하트비트 네 개가 전부 증발했다. 반면 논블로킹 버전에서는 `good_job` 이 `asyncio.sleep(1)` 로 기다리는 동안에도 하트비트가 0.2초 간격으로 정확히 찍힌다. 두 코드의 유일한 차이는 `time.sleep` 이냐 `await asyncio.sleep` 이냐뿐이다.

::: danger 이 버그는 프로덕션에서 조용히 자란다
로컬 테스트에서는 동시 요청이 적어서 안 드러난다. 트래픽이 늘어나면 한 요청 안의 블로킹 호출 하나가 **그 이벤트 루프에 걸린 다른 모든 요청**을 지연시킨다. 스레드가 아니라 단일 이벤트 루프이기 때문에 영향 범위가 프로세스 전체다. `time.sleep`, 동기 DB 드라이버, 동기 `requests`, 무거운 JSON 파싱, 압축 — 전부 후보다.
:::

### 고치는 법: 별도 스레드로 위임한다

블로킹 코드를 없앨 수 없다면(동기 라이브러리만 있는 경우), `asyncio.to_thread()` 로 별도 스레드에 던진다. 이벤트 루프는 그 스레드가 끝나길 기다리는 동안에도 다른 태스크를 계속 돌린다.

```python title="to_thread로 블로킹 코드 격리"
import asyncio
import time


async def heartbeat():
    for i in range(6):
        print(f"[{time.perf_counter():.3f}] 하트비트 {i}")
        await asyncio.sleep(0.2)


def blocking_job():
    time.sleep(1.0)
    return "완료"


async def fixed_job():
    print(f"[{time.perf_counter():.3f}] fixed_job: to_thread로 위임")
    result = await asyncio.to_thread(blocking_job)
    print(f"[{time.perf_counter():.3f}] fixed_job: {result}")


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(heartbeat())
        tg.create_task(fixed_job())


asyncio.run(main())
```

```text
[119056.628] 하트비트 0
[119056.628] fixed_job: to_thread로 위임
[119056.836] 하트비트 1
[119057.040] 하트비트 2
[119057.241] 하트비트 3
[119057.442] 하트비트 4
[119057.631] fixed_job: 완료
[119057.646] 하트비트 5
```

`time.sleep(1)` 은 그대로인데 하트비트가 멈추지 않는다. `to_thread` 가 스레드 풀에 작업을 넘기고, 이벤트 루프는 그 결과를 기다리는 `await` 지점에서 다른 코루틴에게 제어권을 넘기기 때문이다. 여기서 [4.3 GIL, 그리고 free-threaded 파이썬](#/gil)이 왜 중요한지가 보인다 — 스레드로 넘긴다고 해도 GIL이 걸린 일반 빌드에서는 CPU 바운드 작업이 진짜로 병렬 실행되진 않는다. `to_thread` 가 효과를 보는 것은 그 블로킹 호출이 **I/O 대기**(파일, 네트워크, 동기 DB 드라이버)일 때다. 이 경우 스레드가 커널의 I/O 완료를 기다리는 동안 GIL을 놓아 주므로 다른 스레드(그리고 메인 스레드의 이벤트 루프)가 계속 돈다. 진짜 CPU 바운드 작업이라면 `to_thread` 로는 부족하고 [4.4 multiprocessing과 공유 메모리](#/multiprocessing)가 필요하다.

## 종합: 언제 무엇을 쓰는가

지금까지 나온 도구를 정리한다.

| 상황 | 도구 |
| --- | --- |
| 여러 코루틴을 동시에 돌리고 전부 끝나길 기다린다 | `TaskGroup` |
| 하나가 실패하면 나머지도 정리하고 싶다 | `TaskGroup` (자동으로 해 준다) |
| 블록 전체에 마감 시간을 건다 | `asyncio.timeout()` |
| 태스크 하나에만 마감 시간을 건다 | `asyncio.wait_for()` |
| 동시 실행 개수를 제한한다 | `asyncio.Semaphore` |
| 동기 블로킹 코드를 피할 수 없다(I/O 바운드) | `asyncio.to_thread()` |
| 동기 블로킹 코드가 CPU 바운드다 | asyncio를 버리고 [4.4 multiprocessing](#/multiprocessing) |

이 도구들의 공통점은 전부 **취소**(`CancelledError`)라는 하나의 메커니즘 위에 서 있다는 것이다. `TaskGroup` 의 자동 정리도, `timeout()` 의 마감도, 결국 내부적으로 `task.cancel()` 을 호출한다. 그래서 이 절에서 가장 먼저 취소 전파를 실측한 것이다. 취소가 어떻게 도는지 이해하면 나머지는 전부 그 위에 얹힌 응용일 뿐이다.

[1.18 이터레이터와 제너레이터](#/iterators)에서 `yield` 로 실행을 중단하고 재개하는 제너레이터를 봤다면, 코루틴은 그 아이디어의 연장이라는 게 이제 보일 것이다. `await` 는 "여기서 멈추고, 기다리는 것이 끝나면 정확히 이 지점부터 재개해 달라"는 요청이고, 이벤트 루프는 그 재개 시점을 관리하는 스케줄러다. `CancelledError` 는 그 재개 시점에 스케줄러가 "재개하지 말고 여기서 예외를 던져라"라고 끼워 넣는 신호일 뿐이다.

## 요약

- `TaskGroup` 은 블록이 끝날 때 모든 자식 태스크의 종료를 보장하는 구조적 동시성이다.
- `cancel()` 은 즉시 멈추지 않는다. **다음 await 지점**에서 `CancelledError` 가 발생할 뿐이다.
- `CancelledError` 를 잡아서 정리 작업을 해도 되지만, **반드시 `raise` 로 재전파**해야 한다. 삼키면 취소가 조용히 무효화된다.
- `TaskGroup` 안에서 하나가 예외를 던지면 나머지가 자동으로 취소되고, 바깥으로는 `ExceptionGroup` 이 나온다 — `except*` 로 받는다.
- `asyncio.timeout()` 은 블록 전체에 마감을 걸고, 내부적으로 취소를 사용한다. 중첩되면 더 짧은 쪽이 이긴다.
- `Semaphore` 로 동시 실행 개수를 제한하면 처리량은 줄지만 부하가 예측 가능해진다(백프레셔).
- `async def` 안이라고 자동으로 논블로킹이 되지 않는다. `time.sleep` 같은 진짜 블로킹 호출은 이벤트 루프 전체를 멈춘다. I/O 바운드라면 `to_thread`, CPU 바운드라면 별도 프로세스로 옮겨라.

::: quiz 연습문제
1. 다음 코드를 실행하기 전에 출력 순서를 예측하라. 그리고 실제로 실행해서 확인하라.

   ```python
   import asyncio

   async def job(name, delay):
       await asyncio.sleep(delay)
       print(name)

   async def main():
       async with asyncio.TaskGroup() as tg:
           tg.create_task(job("A", 0.3))
           tg.create_task(job("B", 0.1))
           tg.create_task(job("C", 0.2))

   asyncio.run(main())
   ```

2. `TaskGroup` 안에서 두 개의 자식 태스크가 각각 다른 예외(`ValueError`, `KeyError`)를 던지면, `main()` 을 감싼 `except*` 블록은 몇 번 실행되는가? 직접 코드를 짜서 확인하라.

3. `asyncio.Semaphore(3)` 으로 제한된 상태에서 0.5초짜리 작업 9개를 돌리면 전체 소요 시간은 대략 얼마로 예측되는가? 계산한 뒤 실제로 실행해서 확인하라.

4. 아래 함수의 문제를 찾아라. 어떤 상황에서 이벤트 루프 전체가 멈추는가?

   ```python
   async def fetch_and_process(path):
       with open(path) as f:          # 동기 파일 I/O
           data = f.read()
       await asyncio.sleep(0)          # 여기 있는 await는 문제를 가리나?
       return len(data)
   ```

5. `except asyncio.CancelledError: pass` (재전파 없이 그냥 넘김)로 취소를 처리하는 코드가 있다고 하자. 이 태스크를 `task.cancel()` 로 취소한 뒤 `await task` 를 하면 어떤 값이 반환되는가? `task.cancelled()` 는 `True`, `False` 중 무엇인가?
:::

**다음 절**: [4.8 비동기 생태계](#/async-eco) — httpx, anyio, trio, 그리고 동기 코드와의 경계를 어디에 그어야 하는가.
