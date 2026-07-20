# 4.5 concurrent.futures

::: lead
[4.2 threading](#/threading)와 [4.4 multiprocessing](#/multiprocessing)은 API가 다르다. `threading.Thread` 를 만들고 `join` 하는 것과, `multiprocessing.Process` 를 만들고 `join` 하는 것은 표면적으로는 비슷하지만, 풀(pool)을 쓰려는 순간부터 갈라진다. `concurrent.futures` 는 이 둘을 **하나의 인터페이스** 뒤로 숨긴다. `ThreadPoolExecutor` 를 `ProcessPoolExecutor` 로 한 줄만 바꾸면 스레드 기반 병렬 코드가 프로세스 기반 병렬 코드가 된다. 이 절은 그 인터페이스의 정확한 동작 — `submit`과 `map`의 차이, 결과를 기다리는 두 가지 전략, 예외가 어떻게 실행 스레드/프로세스의 경계를 넘어오는지 — 를 전부 실행해서 확인한다.
:::

## 하나의 인터페이스, 두 개의 구현

`ThreadPoolExecutor` 와 `ProcessPoolExecutor` 는 둘 다 `Executor` 라는 추상 클래스를 상속한다. 그래서 쓰는 코드는 완전히 동일하다.

```python title="basic_interface.py"
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def work(n):
    time.sleep(0.3)
    return n * n


def run(executor_cls, label):
    t0 = time.perf_counter()
    with executor_cls(max_workers=4) as ex:
        futures = [ex.submit(work, i) for i in range(4)]
        results = [f.result() for f in futures]
    print(f"{label}: {results}  ({time.perf_counter() - t0:.2f}s)")


if __name__ == "__main__":
    run(ThreadPoolExecutor, "Thread")
    run(ProcessPoolExecutor, "Process")
```

```text nolines
Thread: [0, 1, 4, 9]  (0.30s)
Process: [0, 1, 4, 9]  (0.42s)
```

`run` 함수는 `executor_cls` 가 스레드풀인지 프로세스풀인지 전혀 모른다. `submit`, `result`, `with` 블록의 컨텍스트 매니저 프로토콜([1.17 컨텍스트 매니저](#/context-managers)) 모두 동일하게 동작한다. 프로세스풀 쪽이 0.12초 더 걸린 이유는 작업 자체가 아니라 **프로세스를 새로 띄우는 고정 비용** 때문이다 — 이건 뒤에서 다시 다룬다.

::: note Executor는 왜 추상 클래스인가
`Executor` 는 `submit`, `map`, `shutdown` 세 메서드의 계약만 정의한다. `concurrent.futures` 밖에서도 이 계약을 구현하면 같은 방식으로 쓸 수 있다. 예를 들어 `asyncio` 는 [4.6 asyncio 기초](#/asyncio-basics)에서 볼 `loop.run_in_executor()` 를 통해 바로 이 `Executor` 를 받아 코루틴 세계와 스레드/프로세스 세계를 잇는다. 이 절에서 배우는 인터페이스가 동시성 챕터 전체의 접착제인 셈이다.
:::

## `submit()` vs `map()` — 즉시 반환과 지연 반복자

`submit(fn, *args)` 는 작업 하나를 큐에 넣고 **즉시 `Future` 객체를 반환한다.** 작업이 끝났는지 여부와 무관하게 호출은 논블로킹이다.

`map(fn, iterable)` 은 겉보기엔 내장 `map` 처럼 보이지만 동작이 다르다. 소스를 보면 답이 나온다.

```pyrepl
>>> import inspect
>>> from concurrent.futures import _base
>>> print(inspect.getsource(_base.Executor.map))
    def map(self, fn, *iterables, timeout=None, chunksize=1, buffersize=None):
        ...
        else:
            fs = [self.submit(fn, *args) for args in zipped_iterables]
        ...
        def result_iterator():
            try:
                fs.reverse()
                while fs:
                    ...
                    yield _result_or_cancel(fs.pop())
            finally:
                for future in fs:
                    future.cancel()
        return result_iterator()
```

`map()` 은 호출되는 즉시 **모든 작업을 `submit` 해 버린다.** (3.13부터 생긴 `buffersize` 인자로 이 즉시-제출을 제한할 수 있지만 기본은 전량 제출이다.) 그런 다음 `result_iterator()` 라는 제너레이터를 반환한다. 이 제너레이터를 실제로 순회하기 전까지는 결과를 하나도 꺼내지 않는다 — [1.18 이터레이터와 제너레이터](#/iterators)에서 본 지연 평가 그대로다. 즉 **작업 실행은 즉시, 결과 소비는 지연** 이다. 그리고 결과는 **완료 순서가 아니라 제출 순서**로 나온다.

이걸 실행으로 확인해 보자. 각 작업은 `n` 이 클수록 빨리 끝나도록 만들었다.

```python title="submit_vs_map.py"
import time
from concurrent.futures import ThreadPoolExecutor

START = time.perf_counter()


def work(n):
    time.sleep(0.5 - n * 0.1)  # 역순으로 끝난다: 3번이 제일 먼저 끝남
    print(f"  worker({n}) 완료 at {time.perf_counter()-START:.2f}")
    return n * n


if __name__ == "__main__":
    print("=== map() ===")
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = ex.map(work, range(4))
        print(f"map() 호출 직후 (t=0.00) — 아직 실행 안 됐어도 반환됨")
        for r in results:
            print(f"  받음: {r}")

    print()
    print("=== submit() + 제출 순서대로 .result() ===")
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(work, i) for i in range(4)]
        for f in futures:
            print(f"  받음: {f.result()}")
```

```text nolines
=== map() ===
map() 호출 직후 (t=0.00) — 아직 실행 안 됐어도 반환됨
  worker(3) 완료 at 0.20
  worker(2) 완료 at 0.30
  worker(1) 완료 at 0.40
  worker(0) 완료 at 0.50
  받음: 0
  받음: 1
  받음: 4
  받음: 9

=== submit() + 제출 순서대로 .result() ===
  worker(3) 완료 at 0.70
  worker(2) 완료 at 0.80
  worker(1) 완료 at 0.90
  worker(0) 완료 at 1.00
  받음: 0
  받음: 1
  받음: 4
  받음: 9
```

`worker(3)` 이 가장 먼저(0.20초) 끝났는데도 `받음` 은 항상 `worker(0)` 부터 순서대로 나온다. 두 경우 모두 네 개의 `완료` 로그가 전부 찍힌 **다음에야** 첫 `받음` 이 찍혔다 — `for f in futures: f.result()` 는 리스트의 앞에서부터 순서대로 기다리기 때문에, 정작 가장 오래 걸리는 `worker(0)` 을 기다리는 동안 나머지는 이미 끝나 있었던 것이다. **입력 순서를 지켜야 하면 `map()` 이나 `submit()` + 순서대로 `result()` 를 쓴다.**

## `as_completed()` — 먼저 끝나는 것부터 처리

반대로 **끝나는 순서대로** 처리하고 싶다면 `as_completed()` 를 쓴다. 인자로 `Future` 들의 컬렉션을 받아, 하나가 완료될 때마다 그 `Future` 를 내놓는 이터레이터를 반환한다.

```python title="as_completed_demo.py"
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def work(n):
    time.sleep(0.5 - n * 0.1)
    return n


if __name__ == "__main__":
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(work, i): i for i in range(4)}
        for f in as_completed(futures):
            n = futures[f]
            print(f"submit 순서 {n} -> 완료 순서로 받음, 결과={f.result()}  (t={time.perf_counter()-t0:.2f})")
```

```text nolines
submit 순서 3 -> 완료 순서로 받음, 결과=3  (t=0.20)
submit 순서 2 -> 완료 순서로 받음, 결과=2  (t=0.30)
submit 순서 1 -> 완료 순서로 받음, 결과=1  (t=0.40)
submit 순서 0 -> 완료 순서로 받음, 결과=0  (t=0.50)
```

`futures` 를 `dict`로 만든 이유는 `Future` 객체 자체는 "몇 번째 작업이었는지" 를 모르기 때문이다. `{Future: 원래_인자}` 로 매핑을 만들어 두면, `as_completed` 가 완료된 `Future` 를 넘겨줄 때 원래 어떤 입력이었는지 역추적할 수 있다. **이건 실전 패턴이다** — 여러 URL을 병렬로 가져오면서 어느 URL이 먼저 응답했는지 로그를 남기고 싶을 때 정확히 이 모양을 쓴다.

::: cote 코딩테스트 포인트
경쟁 코딩에서 `concurrent.futures` 를 직접 쓸 일은 드물지만, **"먼저 끝나는 순서로 처리한다"** 는 개념 자체는 [7.8 힙과 우선순위 큐](#/heap)의 다익스트라식 사고와 닮았다. 다만 `as_completed` 내부는 힙이 아니라 조건 변수(condition variable)로 완료 신호를 기다리는 방식이다 — "먼저 끝난 것부터" 라는 결과는 같아도 구현 원리는 다르다는 것을 구분해서 알아 둬라.
:::

## `Future` 객체의 상태 머신

`Future` 는 비동기 작업의 진행 상태와 결과를 담는 상자다. 내부적으로 `PENDING → RUNNING → (CANCELLED | FINISHED)` 라는 상태를 거친다. `_state` 속성(사적 API지만 디버깅에 유용하다)과 `done()`, `running()`, `cancel()` 로 직접 관찰할 수 있다.

```python title="future_states.py"
import time
from concurrent.futures import ThreadPoolExecutor


def slow():
    time.sleep(0.3)
    return 42


def boom():
    time.sleep(0.1)
    raise ValueError("작업 중 실패")


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=1) as ex:
        f = ex.submit(slow)
        print("제출 직후 state:", f._state)
        print("done()?", f.done())
        print("running()?", f.running())
        time.sleep(0.4)
        print("완료 후 state:", f._state)
        print("result():", f.result())

        print()
        print("=== 취소 시도 (워커 1개짜리 풀) ===")
        f2 = ex.submit(slow)
        f3 = ex.submit(slow)  # 워커가 f2를 처리 중이라 f3는 대기
        time.sleep(0.01)
        print("f2 state:", f2._state, "cancel 결과:", f2.cancel())
        print("f3 state:", f3._state, "cancel 결과:", f3.cancel())
        print("f3.cancelled()?", f3.cancelled())
        f2.result()

        print()
        print("=== 예외 전파 ===")
        fe = ex.submit(boom)
        try:
            fe.result()
        except ValueError as e:
            print(f"result()에서 예외를 다시 던짐: {type(e).__name__}: {e}")
        print("exception():", fe.exception())
```

```text nolines
제출 직후 state: RUNNING
done()? False
running()? True
완료 후 state: FINISHED
result(): 42

=== 취소 시도 (워커 1개짜리 풀) ===
f2 state: RUNNING cancel 결과: False
f3 state: PENDING cancel 결과: True
f3.cancelled()? True

=== 예외 전파 ===
result()에서 예외를 다시 던짐: ValueError: 작업 중 실패
exception(): 작업 중 실패
```

`f2.cancel()` 은 `False` 를 반환한다. **이미 실행이 시작된 작업은 취소할 수 없다.** `f3.cancel()` 은 `True` 다 — 워커가 하나뿐이라 `f3` 는 아직 큐에서 대기(`PENDING`) 중이었기 때문이다. `concurrent.futures` 의 취소는 "실행 중인 스레드를 강제로 죽이는" 기능이 아니라 **"아직 시작 안 한 작업을 큐에서 빼는" 기능**이다. 이 차이를 착각하면 실행 중인 무거운 작업을 취소로 멈출 수 있다고 오해하게 된다.

::: warn 실행 중인 작업은 취소되지 않는다
`threading.Thread` 에 `stop()` 메서드가 없는 것과 같은 이유다. 파이썬은 실행 중인 스레드를 외부에서 강제 종료하는 안전한 방법을 제공하지 않는다. 정말 중단 가능한 작업이 필요하면 작업 함수 안에 취소 플래그(예: `threading.Event`)를 두고 스스로 확인하게 설계해야 한다. [4.2 threading](#/threading)에서 다룬다.
:::

## 예외는 어떻게 경계를 넘어오는가

작업 함수 안에서 예외가 나면 그 예외는 사라지지 않는다. `Future` 객체 안에 **저장**되고, `result()` 를 호출하는 순간 **그 자리에서 다시 던져진다.** 위 실행에서 정확히 그렇게 됐다 — `boom()` 은 워커 스레드 안에서 `ValueError` 를 던졌지만, 그 예외가 메인 스레드의 `try/except` 에서 잡혔다. 스레드 경계를 예외가 "건너온" 것이다.

`ThreadPoolExecutor` 는 같은 프로세스 안이라 예외 객체 자체를 그대로 전달하면 된다. `ProcessPoolExecutor` 는 사정이 다르다 — 워커가 **별도의 프로세스**([4.4 multiprocessing](#/multiprocessing)에서 본 것처럼, Windows에서는 `spawn`)이므로 예외 객체를 그대로 넘길 수 없다. **피클(pickle)로 직렬화해서 파이프로 되돌려 보낸 뒤, 부모 프로세스에서 역직렬화해 다시 던진다.**

```python title="process_exception.py"
from concurrent.futures import ProcessPoolExecutor


def boom(n):
    if n == 2:
        raise ValueError(f"n={n}에서 실패")
    return n * n


if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(boom, i) for i in range(4)]
        for i, f in enumerate(futures):
            try:
                print(f"{i}: {f.result()}")
            except ValueError as e:
                print(f"{i}: 예외 전파됨 -> {type(e).__name__}: {e}")
```

```text nolines
0: 0
1: 1
2: 예외 전파됨 -> ValueError: n=2에서 실패
3: 9
```

프로세스 하나가 죽은 나머지 작업들에는 영향을 주지 않는다. 하지만 **워커 프로세스가 예외가 아니라 통째로 죽어버리면** 얘기가 다르다.

```python title="프로세스가 통째로 죽으면?"
import os
from concurrent.futures import ProcessPoolExecutor


def crash():
    os._exit(1)  # 세그폴트나 강제 종료 흉내


if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=2) as ex:
        f = ex.submit(crash)
        f.result()
```

```text nolines
concurrent.futures.process.BrokenProcessPool: A process in the process pool was terminated abruptly while the future was running or pending.
```

이건 일반 예외가 아니다. **`BrokenProcessPool`** 이라는 별도의 예외이고, 발생 즉시 그 풀 자체가 재사용 불가능해진다 — 이미 제출됐지만 아직 안 끝난 다른 작업들도 전부 이 예외로 실패 처리된다. `ThreadPoolExecutor` 에는 이런 개념이 없다. 스레드가 죽는다는 건 곧 인터프리터 전체가 죽는다는 뜻이라 "풀만 깨지는" 중간 상태가 존재하지 않기 때문이다. **프로세스풀을 쓴다는 것은 이런 부분적 장애 모드까지 처리 대상에 넣는다는 뜻이다.**

## 스레드풀이냐 프로세스풀이냐 — 실측으로 결정한다

[4.1 동시성 모델 지도](#/concurrency-map)에서 I/O 바운드와 CPU 바운드를 구분했고, [4.3 GIL](#/gil)에서 일반 빌드는 CPU 바운드 코드에서 스레드 하나만 파이썬 바이트코드를 실행할 수 있다는 것을 봤다. `concurrent.futures` 는 이 구분을 감추지 않는다 — 어떤 풀을 골랐는지가 성능에 그대로 드러난다.

### CPU 바운드: 일반 GIL 빌드

```python title="thread_vs_process_cpu.py — CPU 바운드"
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def cpu_bound(n):
    x = 0
    for i in range(n):
        x += i * i
    return x


N = 20_000_000
WORKERS = 4
```

같은 작업을 4개 워커로 실행한 실측 결과다.

```text nolines
단일 스레드 1회: 0.60s (참고: 이걸 4번 하면 순차로는 2.41s)
ThreadPoolExecutor (workers=4): 2.37s   -> 순차 대비 1.02배
ProcessPoolExecutor (workers=4): 0.74s  -> 순차 대비 3.28배
```

(Python 3.14.5 / Windows, 일반 GIL 빌드 기준 실측. 절대값은 기기마다 다르지만 배수 차이의 자릿수는 재현된다.)

`ThreadPoolExecutor` 는 4개 스레드를 돌려도 **거의 순차 실행과 같은 시간**이 걸렸다. GIL이 한 번에 한 스레드만 바이트코드를 실행하게 막았기 때문이다. `ProcessPoolExecutor` 는 프로세스마다 독립된 인터프리터와 GIL을 갖기 때문에 실제로 코어 4개를 다 쓴다 — 3.28배로 스케일링했다.

### I/O 바운드: 정반대 결과

```python title="thread_io_bound.py — I/O 바운드"
def io_bound(_):
    time.sleep(0.3)  # 네트워크/디스크 대기 흉내. GIL을 놓아 준다.
    return _
```

```text nolines
ThreadPoolExecutor (I/O 바운드, workers=8): 0.30s
ProcessPoolExecutor (I/O 바운드, workers=8): 0.53s
```

`time.sleep` 은 대기하는 동안 GIL을 놓아준다. 그래서 스레드 8개가 진짜로 동시에 잠들었다가 동시에 깬다 — 총 0.3초. 프로세스풀은 여기서 오히려 손해다. **프로세스를 새로 띄우는 고정 비용**(0.2초가량, 앞서 `basic_interface.py` 에서도 봤다)이 이득 없이 그대로 더해진다.

::: perf 언제 어느 풀을 쓰는가 — 결론
- **I/O 바운드**(네트워크 호출, 파일 읽기, DB 쿼리) → `ThreadPoolExecutor`. GIL은 대기 시간에 방해되지 않고, 프로세스 생성 비용도 없다.
- **CPU 바운드**(순수 계산, 이미지 처리, 파싱) → `ProcessPoolExecutor`. 일반 GIL 빌드에서 병렬 계산 성능을 얻는 유일한 표준 라이브러리 경로다.
- 단, 프로세스풀은 인자와 반환값을 **피클로 직렬화**해야 하므로, 큰 객체를 자주 주고받는 작업에서는 이 비용이 계산 이득을 갉아먹을 수 있다. [4.4 multiprocessing](#/multiprocessing)의 `shared_memory` 가 그 해법이다.
:::

### free-threaded 빌드에서는 결론이 바뀐다

[4.3 GIL](#/gil)에서 다룬 free-threaded 빌드(3.14t)로 **완전히 같은 CPU 바운드 코드**를 돌리면 어떻게 될까. 실제로 설치해서 비교했다.

```bash
uv python install 3.14t
uv run --python 3.14t python thread_vs_process_cpu.py
```

```text nolines
단일 스레드 1회: 0.58s (참고: 이걸 4번 하면 순차로는 2.31s)
ThreadPoolExecutor (workers=4): 0.66s   -> 순차 대비 3.52배
ProcessPoolExecutor (workers=4): 0.91s  -> 순차 대비 2.55배
```

(Python 3.14.5 free-threading 빌드 / Windows 기준 실측. `sys._is_gil_enabled()` 는 이 빌드에서 `False`다.)

일반 GIL 빌드에서 1.02배에 그쳤던 `ThreadPoolExecutor` 가 free-threaded 빌드에서는 **3.52배**로 스케일링했다. 심지어 `ProcessPoolExecutor` (2.55배)보다도 앞섰다 — 프로세스 생성·피클링 오버헤드가 없는 스레드 쪽이 GIL만 없다면 원래 더 유리하기 때문이다. **`concurrent.futures` 코드는 한 줄도 바꾸지 않았다.** 바뀐 건 인터프리터 빌드뿐이다. 이게 이 인터페이스가 갖는 진짜 값어치다 — GIL이 있는 시대에도, 없는 시대에도 같은 코드가 그대로 통한다.

## Windows와 프로세스풀 — `__main__` 가드는 선택이 아니다

[4.4 multiprocessing](#/multiprocessing)에서 다뤘듯 Windows는 `fork` 가 없어 `spawn` 방식을 쓴다. 자식 프로세스가 **모듈을 처음부터 다시 import** 한다는 뜻이다. `ProcessPoolExecutor` 생성과 `submit` 호출이 `if __name__ == "__main__":` 가드 없이 모듈 최상위에 있으면 실제로 무슨 일이 일어나는지 확인해 보자.

```python title="no_guard.py — 가드 없이 최상위에서 실행"
from concurrent.futures import ProcessPoolExecutor


def work(n):
    return n * n


ex = ProcessPoolExecutor(max_workers=2)  # 최상위 코드
futures = [ex.submit(work, i) for i in range(4)]
for f in futures:
    print(f.result())
```

```text nolines
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
        ...
        To fix this issue, refer to the "Safe importing of main module"
        section in https://docs.python.org/3/library/multiprocessing.html
...
concurrent.futures.process.BrokenProcessPool: A process in the process pool was terminated abruptly while the future was running or pending.
```

자식 프로세스가 `no_guard.py` 를 다시 import 하면서 최상위의 `ProcessPoolExecutor(...)` 와 `submit` 호출을 **또 실행**하려 든다. 파이썬이 이걸 감지하고 즉시 `RuntimeError` 로 막아서 무한 프로세스 생성을 방지하지만, 결과적으로 원래 작업도 `BrokenProcessPool` 로 실패한다. **`ProcessPoolExecutor` 를 스크립트 최상위에서 만들거나 쓰지 마라. 항상 `if __name__ == "__main__":` 블록 안에 둬라.** 이 절의 모든 예제 코드가 그 가드를 지키고 있는 이유다.

## 요약

- `ThreadPoolExecutor` 와 `ProcessPoolExecutor` 는 `Executor` 라는 같은 인터페이스(`submit`, `map`, `shutdown`)를 공유한다. 코드는 그대로 두고 클래스만 바꿔서 실행 모델을 바꿀 수 있다.
- `submit()` 은 즉시 `Future` 를 반환한다. `map()` 은 모든 작업을 **즉시 전량 제출**하지만, 결과는 **제출 순서대로 지연 반환**한다 — 먼저 끝나도 순서를 지킨다.
- 끝나는 순서대로 처리하려면 `as_completed()` 를 쓰고, `{Future: 원래_인자}` 딕셔너리로 역추적한다.
- `Future` 는 `PENDING → RUNNING → (CANCELLED|FINISHED)` 상태를 갖는다. `cancel()` 은 아직 시작 안 한 작업에만 통한다.
- 작업 중 예외는 사라지지 않고 `Future` 에 저장됐다가 `result()` 호출 시 재발생한다. 프로세스풀에서는 피클로 직렬화해 프로세스 경계를 넘어온다. 워커 프로세스가 통째로 죽으면 `BrokenProcessPool` 이 뜬다.
- I/O 바운드는 `ThreadPoolExecutor`, CPU 바운드는 (일반 GIL 빌드에서) `ProcessPoolExecutor`. free-threaded 빌드에서는 스레드풀이 CPU 바운드에서도 스케일링하고, 프로세스 생성 비용이 없어 오히려 더 유리할 수 있다.
- Windows의 `ProcessPoolExecutor` 는 반드시 `if __name__ == "__main__":` 가드 안에서 생성하고 써야 한다.

::: quiz 연습문제
1. `ex.map(work, range(4))` 를 호출한 직후, 아직 결과를 하나도 꺼내지 않은 시점에도 네 개의 작업이 이미 실행 중이라는 것을 어떻게 확인할 수 있는가? 코드로 증명하라.
2. `as_completed()` 대신 `submit()` 결과 리스트를 순서대로 `.result()` 로 기다리면 어떤 상황에서 실질적인 손해가 생기는가? "먼저 끝난 결과를 즉시 화면에 출력해야 하는 웹 크롤러"를 예로 설명하라.
3. `ThreadPoolExecutor(max_workers=1)` 로 두 개의 작업을 연달아 `submit` 했다. 첫 번째 작업이 실행 중일 때 두 번째 `Future` 의 `cancel()` 을 호출하면 성공하는가? 실행 중인 작업이라면?
4. CPU 바운드 작업과 I/O 바운드 작업이 섞인 함수(예: 계산 후 결과를 파일에 쓰는 함수)가 있다면, `ThreadPoolExecutor` 와 `ProcessPoolExecutor` 중 어느 쪽이 유리할지 이 절의 실측 수치를 근거로 논하라.
5. `ProcessPoolExecutor` 로 실행하는 함수가 람다(`lambda x: x*2`)라면 어떤 예외가 나는가? 직접 실행해서 확인하고, 그 이유를 프로세스 간 통신 방식과 연결해 설명하라.
:::

**다음 절**: [4.6 asyncio 기초: 코루틴과 이벤트 루프](#/asyncio-basics) — `await` 가 스레드나 프로세스 없이 어떻게 동시성을 만드는가.
