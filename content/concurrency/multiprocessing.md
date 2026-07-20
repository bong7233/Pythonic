# 4.4 multiprocessing과 공유 메모리

::: lead
[4.2 threading](#/threading)와 [4.3 GIL](#/gil)에서 스레드로는 CPU 바운드 작업이 빨라지지 않는다는 것을 봤다. GIL이 파이썬 바이트코드를 한 번에 하나씩만 실행하게 막기 때문이다. 이 절은 그 벽을 우회하는 표준 수단이다 — 아예 별개의 인터프리터를, 별개의 프로세스로 띄운다. 대신 그 대가로 프로세스 경계라는 진짜 벽이 생긴다. 메모리를 공유하지 않고, 통신은 피클링을 거치고, 시작 방식에 따라 동작이 달라진다. 이 절은 그 벽의 정체를 실측으로 보여준다.
:::

## GIL을 피해 진짜 병렬화하기

`Pool` 은 여러 워커 프로세스를 미리 띄워 놓고 작업을 나눠주는 도구다. 각 워커는 **완전히 별개의 파이썬 인터프리터**이고, 각자 자기 GIL을 가진다. 그래서 CPU 코어 수만큼 진짜로 동시에 바이트코드를 실행할 수 있다.

말로만 하지 말고 재보자. 순수 계산 작업을 순차 실행, 스레드, 프로세스 풀로 각각 돌린다.

```python title="bench.py"
import time
import threading
from multiprocessing import Pool


def cpu_task(n):
    total = 0
    for i in range(n):
        total += i * i
    return total


def run_serial(n, times):
    t0 = time.perf_counter()
    for _ in range(times):
        cpu_task(n)
    return time.perf_counter() - t0


def run_threads(n, times):
    t0 = time.perf_counter()
    threads = [threading.Thread(target=cpu_task, args=(n,)) for _ in range(times)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - t0


def run_pool(n, times, procs):
    t0 = time.perf_counter()
    with Pool(procs) as p:
        p.map(cpu_task, [n] * times)
    return time.perf_counter() - t0


if __name__ == "__main__":
    N, TIMES = 5_000_000, 8
    print("serial  :", run_serial(N, TIMES))
    print("threads :", run_threads(N, TIMES))
    print("pool(4) :", run_pool(N, TIMES, 4))
    print("pool(8) :", run_pool(N, TIMES, 8))
```

```text nolines
serial  : 1.110초
threads : 1.102초    <- GIL 때문에 스레드 8개를 써도 그대로다
pool(4) : 0.442초    <- 약 2.5배
pool(8) : 0.300초    <- 약 3.7배
```

(Python 3.14.5 / Windows, 물리 8코어·논리 16스레드(하이퍼스레딩) 머신 기준 실측. `os.cpu_count()` 는 16을 반환하지만 이건 "16코어"가 아니라 "8코어 16스레드"다 — `Pool()` 이 기본으로 띄우는 워커 수는 논리 프로세서 수를 따르므로 이 차이를 알아둬야 한다. 절대값은 기기마다 다르지만 스레드가 못 하는 일을 프로세스가 해낸다는 방향은 어디서나 같다.)

::: cote 코딩테스트 포인트
`Pool()` 을 인자 없이 생성하면 `os.cpu_count()` 만큼 워커를 띄운다. 로컬에서 4코어인데 서버 채점 환경은 2코어일 수 있다. 코딩테스트에서 `multiprocessing` 을 실제로 쓸 일은 거의 없다 — 프로세스 생성 자체의 오버헤드(수 ms~수십 ms)가 시분초 단위 시간 제한을 잡아먹는다. 이 절의 지식은 코테보다는 **실무에서 큰 배치 작업을 병렬화**할 때 쓴다.
:::

`pool(4)` 가 정확히 4배가 아니라 2.5배인 이유는 두 가지다. **프로세스 생성 비용**(각 워커를 새로 띄우는 데 걸리는 시간)과 **작업 분배·결과 수집 비용**(피클링을 거친 통신, 바로 아래에서 다룬다)이 순수 계산 시간 위에 얹힌다. 작업 하나하나가 작을수록 이 오버헤드의 비중이 커진다. 그래서 `multiprocessing` 은 **워커당 처리할 덩어리(chunk)가 통신 비용보다 훨씬 커야** 이득이다.

## spawn과 fork — 시작 방식의 차이

워커 프로세스를 만드는 방법이 하나가 아니다. **어떻게 만드느냐**가 이 장 전체의 행동을 결정한다.

| 시작 방식 | 동작 | 지원 플랫폼 |
| --- | --- | --- |
| `fork` | 현재 프로세스를 통째로 복제한다(메모리 포함) | Unix 계열만 |
| `spawn` | 새 인터프리터를 깨끗하게 띄우고 **모듈을 처음부터 다시 import** 한다 | Windows, macOS, Unix 전부 |
| `forkserver` | 서버 프로세스를 하나 띄워두고 거기서 fork한다 | Unix 계열만 |

이 환경(Windows)에서 직접 확인하면 이렇다.

```pyrepl
>>> import multiprocessing as mp
>>> mp.get_start_method()
'spawn'
>>> mp.get_all_start_methods()
['spawn']
```

**Windows에는 `spawn` 밖에 없다.** 그럴 만한 이유가 있다. `fork` 는 Unix의 `fork()` 시스템 콜에 의존하는데, 이건 프로세스의 메모리 전체를 (실제로는 copy-on-write로) 그대로 복제한다. Windows 커널에는 이런 개념이 없다. 그래서 Windows는 항상 `spawn` 을 쓴다 — 새 파이썬 프로세스를 처음부터 실행하고, **부모가 넘겨준 정보만 가지고 필요한 것을 다시 만든다.**

::: deep spawn은 모듈을 처음부터 다시 실행한다
"필요한 것을 다시 만든다"는 게 정확히 무슨 뜻인지 실행으로 보자. 워커 함수 안에서 `os.getpid()` 를 찍고, **모듈 최상단**에서도 찍는다.

```python title="reimport_demo.py"
import os, time

print(f"모듈 최상단 실행됨 (pid={os.getpid()})", flush=True)


def worker(x):
    print(f"worker 실행 (pid={os.getpid()})", flush=True)
    return x


if __name__ == "__main__":
    from multiprocessing import Pool
    print(f"__main__ 진입 (pid={os.getpid()})", flush=True)
    with Pool(3) as p:
        p.map(worker, [1, 2, 3])
```

```text nolines
모듈 최상단 실행됨 (pid=23208)   <- 부모 프로세스, 모듈 import
__main__ 진입 (pid=23208)       <- 부모, __main__ 블록
모듈 최상단 실행됨 (pid=25228)   <- 자식 1, 모듈을 처음부터 다시 import!
모듈 최상단 실행됨 (pid=16892)   <- 자식 2, 마찬가지
모듈 최상단 실행됨 (pid=3048)    <- 자식 3, 마찬가지
worker 실행 (pid=25228)
worker 실행 (pid=25228)
worker 실행 (pid=25228)
```

자식 프로세스 3개 각각이 **모듈 최상단의 `print` 를 한 번씩 더 실행했다.** `Pool` 이 뭔가 신기한 방법으로 메모리를 복제한 게 아니다. 자식 프로세스는 텅 빈 인터프리터로 시작해서, 부모가 어떤 스크립트를 실행 중이었는지 알아낸 뒤 그 스크립트를 `runpy.run_path` 로 **처음부터 다시 읽어서 실행**한다. 이때 모듈 이름은 `__main__` 이 아니라 `__mp_main__` 이라서, `if __name__ == "__main__":` 아래 코드는 건너뛴다.

`worker 실행` 세 줄이 모두 **같은 pid(25228)** 에서 나온 걸 눈여겨봐라 — 자식 1, 2, 3이 하나씩 나눠 처리한 게 아니다. 5회 반복 실행해도 매번 셋 중 하나의 자식이 작업 3개를 전부 가져갔고, 나머지 두 자식은 `worker` 를 한 번도 실행하지 않았다. `Pool.map` 은 기본 `chunksize=1` 로 작업을 공용 큐에 넣고, 각 워커가 놀 때마다 큐에서 하나씩 꺼내가는 방식이다. 이번처럼 작업 하나(`return x`)가 순식간에 끝나면, 먼저 준비를 마친 워커 하나가 큐를 비우기 전에 다음 항목까지 채가는 경쟁에서 매번 이겨버린다. 워커 3개에 작업이 고르게 분배되는 그림을 기대했다면 틀렸다 — **분배는 보장이 아니라 경쟁의 결과**다. 작업이 오래 걸릴수록, 또는 항목 수가 워커 수보다 훨씬 많을수록 이 쏠림은 옅어진다.
:::

::: danger __main__ 가드 없이 Pool을 만들면 폭탄이 된다
방금 본 메커니즘의 당연한 귀결이다. `if __name__ == "__main__":` 가드 **없이** 모듈 최상단에서 `Pool` 을 만들면 어떻게 될까? 직접 재현했다.

```python title="no_guard.py — 절대 이렇게 쓰지 마라"
from multiprocessing import Pool


def square(x):
    return x * x


p = Pool(2)              # 가드 없이 최상단에!
print(p.map(square, [1, 2, 3]))
```

이걸 실행하면(주의: 6초만 돌렸는데도 python.exe 프로세스가 계속 늘어나서 강제 종료해야 했다):

```text nolines
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from multiprocessing.spawn import spawn_main; spawn_main(...)
  File "...\spawn.py", line 131, in _main
    prepare(preparation_data)
  File "...\spawn.py", line 246, in prepare
    _fixup_main_from_path(data['init_main_from_path'])
  File "...\spawn.py", line 297, in _fixup_main_from_path
    main_content = runpy.run_path(main_path, run_name="__mp_main__")
  File "no_guard.py", line 8, in <module>
    p = Pool(2)                              <- 자식이 또 Pool을 만든다
  File "...\pool.py", line 215, in __init__
    self._repopulate_pool()
  File "...\pool.py", line 306, in _repopulate_pool
    return self._repopulate_pool_static(...)
  File "...\context.py", line ..., in _Popen
    ...
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
        ...
Traceback (most recent call last):                 <- 손자 프로세스도 같은 자리에서 걸려 죽는다
  ...(같은 패턴과 같은 RuntimeError가 반복된다 — 6초간 캡처한 로그에만 약 140번 나왔다)...
```

**자식이 모듈을 다시 실행하다가 `Pool(2)` 줄에 도달하면, 자식이 또 자기 자식(손자)을 만들려고 시도한다.** 그런데 이 시도는 이론상 무한 재귀로 이어지기 전에 실제로는 **`_check_not_importing_main`** (`multiprocessing/spawn.py`)에 매번 걸려 넘어진다. `_main()` 은 `process.current_process()._inheriting = True` 를 설정한 채로 `prepare()` 를 호출하고, `prepare()` 가 `runpy.run_path` 로 모듈 최상단 코드 — 가드 없는 `Pool(2)` 줄 포함 — 를 실행한다. 즉 `Pool(2)` 생성은 재귀의 매 단계에서 **항상 `_inheriting=True` 인 부트스트래핑 창 안에서** 일어나므로, 안전장치가 매번 정상 작동해 `RuntimeError` 를 던진다. "부트스트래핑이 끝난 뒤라 안전장치를 우회한다"는 건 틀렸다 — 이 안전장치는 여기서 정확히 설계된 대로 동작한다. 문제는 그 에러가 **자식을 멈추지 못한다는 것**이다. 에러가 나서 그 자식은 죽지만, 부모(또는 그 위 조상)는 이미 다음 자식을 또 만들려던 참이라 실패·재시도가 계속 반복되고, 그 사이에도 매번 새 python.exe 프로세스가 뜨고 죽기를 반복하면서 살아있는 프로세스 수가 계속 늘어난다. 결과적으로 콘솔에는 같은 `RuntimeError` 트레이스백이 수십~수백 번 쏟아지고, 작업 관리자에는 python.exe 가 계속 늘어나 있는 걸 보게 된다 — "에러 없이 조용히 불어난다"가 아니라 "같은 에러를 반복해서 내면서 불어난다."

**가드 없는 최상위 `Pool`/`Process` 는 실험조차 위험하다.** `if __name__ == "__main__":` 은 장식이 아니라 이 반복 실패-재시도 폭증을 막는 유일한 안전장치다.
:::

이 사실은 [1.19 모듈, 패키지, import](#/imports) 에서 본 "모듈은 처음 import될 때 최상단 코드가 실행된다"는 규칙의 직접적인 응용이다. `spawn` 은 자식 프로세스에서 그 규칙을 **한 번 더** 발동시킨다.

::: note fork였다면 달랐을 것이다
Unix에서 `fork` 를 쓰면 자식은 부모의 메모리를 그대로 물려받은 채로 **`fork()` 호출 지점 바로 다음부터** 실행을 재개한다. 모듈을 다시 import하지 않으므로 최상단 코드가 다시 실행되지 않고, 가드 없는 `Pool` 도 이런 식의 폭발은 일으키지 않는다(대신 다른 문제 — 스레드/락 상태를 불완전하게 물려받는 문제 — 가 생길 수 있다). 이 환경은 Windows라 fork를 직접 실행해 비교할 수는 없지만, `spawn` 이 항상 안전한 상위 호환은 아니라는 것만은 분명하다. 3.14부터 macOS와 마찬가지로 여러 플랫폼이 `spawn` 을 기본값으로 굳히는 추세이고, 이유는 `fork` 가 멀티스레드 프로그램에서 데드락을 일으킬 수 있기 때문이다 — 자세한 배경은 [4.3 GIL](#/gil)의 free-threaded 논의와 함께 봐라.
:::

## 프로세스 경계는 피클링이라는 관문이다

스레드는 메모리를 공유하므로 함수 객체를 그냥 넘기면 됐다. 프로세스는 메모리가 분리돼 있다. **`Pool`/`Process` 에 넘기는 모든 것 — 함수, 인자, 반환값 — 은 파이프를 통해 바이트로 직렬화된 뒤 다른 프로세스에서 복원된다.** 그 직렬화 수단이 `pickle` 이다.

이게 왜 중요한지는 실패를 봐야 감이 온다. 세 가지를 직접 깨뜨려 보자.

```python title="pickle_error.py"
from multiprocessing import Pool


def make_worker():
    def inner(x):          # 클로저 — 지역 함수
        return x * x
    return inner


class HasLock:
    def __init__(self):
        import threading
        self.lock = threading.Lock()


if __name__ == "__main__":
    worker = make_worker()
    try:
        with Pool(2) as p:
            p.map(worker, [1, 2, 3])
    except Exception as e:
        print("1) 클로저:", type(e).__name__, "-", e)

    try:
        with Pool(2) as p:
            p.map(lambda x: x * x, [1, 2, 3])
    except Exception as e:
        print("2) 람다:", type(e).__name__, "-", e)

    try:
        with Pool(2) as p:
            p.map(len, [HasLock()])
    except Exception as e:
        print("3) Lock 포함 객체:", type(e).__name__, "-", e)
```

```text nolines
1) 클로저: PicklingError - Can't pickle local object <function make_worker.<locals>.inner at 0x...>
2) 람다: PicklingError - Can't pickle <function <lambda> at 0x...>: it's not found as __main__.<lambda>
3) Lock 포함 객체: TypeError - cannot pickle '_thread.lock' object
```

세 실패 모두 같은 근본 원인이다. **pickle은 함수를 "코드"로 저장하지 않는다. 모듈 경로와 이름으로 저장한다.** 자식 프로세스는 그 이름으로 자기 쪽 모듈을 다시 import해서 같은 이름의 객체를 찾아낸다. 그런데 클로저(`inner`)와 람다는 **어디서도 그 이름으로 다시 찾을 수 있는 최상위 이름이 아니다.** `Lock` 은 아예 운영체제 자원(뮤텍스 핸들)을 감싼 객체라 개념적으로 복제할 방법이 없다.

::: warn 피클 가능성 규칙
- **모듈 최상위(top-level)에 정의된 함수·클래스만** 안전하게 넘길 수 있다.
- 지역 함수, 클로저, 람다, `__main__` 에서만 정의된 것들은 위험하다(특히 `__main__` 은 자식이 재현하는 방식이 미묘해서 되다 안 되다 한다).
- 열린 파일, 소켓, 락, 스레드, DB 커넥션처럼 **운영체제 자원을 감싼 객체**는 절대 못 넘긴다.
- [1.18 이터레이터와 제너레이터](#/iterators)에서 만든 제너레이터도 피클 불가능하다.

```pyrepl
>>> import pickle
>>> def gen():
...     yield 1
>>> pickle.dumps(gen())
TypeError: cannot pickle 'generator' object
```

그래서 제너레이터로 지연 생성한 데이터를 워커에 통째로 넘기려 하면 실패한다. `list(gen())` 으로 먼저 값을 뽑아내거나, 애초에 데이터 자체가 아니라 **데이터를 만드는 방법(인자)**을 넘기고 워커 안에서 생성하는 구조로 설계해야 한다.
:::

::: tip 클래스 메서드는 왜 되는데 클로저는 안 되는가
`Pool.map(instance.method, ...)` 처럼 바운드 메서드를 넘기는 건 된다. pickle이 "이 클래스를 모듈 경로로 찾고, 그 인스턴스의 `__dict__` 를 복원한 뒤, 메서드를 다시 바인딩"하는 절차를 알기 때문이다. 클래스는 최상위 이름을 갖지만 클로저는 갖지 않는다는 차이다. 단, 인스턴스의 속성들도 전부 피클 가능해야 한다는 조건은 그대로 붙는다.
:::

## Queue와 Pipe — 메시지로 주고받기

값을 한 번 넘기고 받는 게 아니라 계속 주고받아야 하면 `Queue` 나 `Pipe` 를 쓴다. 둘 다 내부적으로 파이프 + 피클링이지만 쓰임이 다르다.

- **`Queue`** — 여러 생산자·소비자가 써도 안전하다(내부에 락이 있다). FIFO.
- **`Pipe`** — 1대1 연결. `Queue` 보다 가볍고 빠르다.

```python title="queue_pipe_demo.py"
from multiprocessing import Process, Queue, Pipe


def producer(q):
    for i in range(5):
        q.put(i * i)
    q.put(None)               # 종료 신호를 직접 보낸다


def pipe_worker(conn):
    conn.send("자식에서 보냄")
    print("자식이 받음:", conn.recv())
    conn.close()


if __name__ == "__main__":
    q = Queue()
    p = Process(target=producer, args=(q,))
    p.start()
    results = []
    while (item := q.get()) is not None:
        results.append(item)
    p.join()
    print("Queue로 받은 값:", results)

    parent_conn, child_conn = Pipe()
    p2 = Process(target=pipe_worker, args=(child_conn,))
    p2.start()
    print("부모가 받음:", parent_conn.recv())
    parent_conn.send("부모에서 보냄")
    p2.join()
```

```text nolines
자식이 받음: 부모에서 보냄
Queue로 받은 값: [0, 1, 4, 9, 16]
부모가 받음: 자식에서 보냄
```

`Queue` 에는 `None` 같은 **종료 신호(sentinel)를 직접 넣어야 한다.** 자식이 몇 개를 만들어낼지 부모가 미리 모르기 때문에, "더 이상 없다"는 것도 데이터로 보내야 한다. [7.7 스택과 큐](#/stack-queue)에서 본 `collections.deque` 기반 큐와는 이름만 같을 뿐 완전히 다른 물건이다 — 저건 스레드 하나 안에서 도는 메모리 구조, 이건 프로세스 경계를 넘는 통신 채널이다.

## 진짜 공유 메모리: shared_memory

지금까지 본 모든 방법(인자 전달, `Queue`, `Pipe`)은 데이터를 **복사**한다. 큰 배열을 여러 워커가 나눠 읽기만 해도 매번 피클링 비용을 낸다. `multiprocessing.shared_memory` 는 다르다. **운영체제가 제공하는 공유 메모리 영역을 파이썬에서 그대로 매핑**해서, 프로세스 여러 개가 **같은 물리 메모리**를 바이트 단위로 공유한다.

먼저 공유가 안 되는 기본 상황부터 확인하자.

```python title="no_share.py"
from multiprocessing import Process


def modify(lst):
    lst.append(999)
    print("자식 안에서:", lst)


if __name__ == "__main__":
    data = [1, 2, 3]
    p = Process(target=modify, args=(data,))
    p.start()
    p.join()
    print("부모에서:", data)
```

```text nolines
자식 안에서: [1, 2, 3, 999]
부모에서: [1, 2, 3]        <- 그대로다. 자식은 피클된 사본을 받았다
```

[1.1 객체, 이름, 참조](#/objects-names)에서 배운 별칭(aliasing) 개념이 프로세스 경계에서는 아예 성립하지 않는다는 걸 보여준다. `lst` 라는 이름은 부모와 자식에서 **서로 다른 객체**를 가리킨다. 이제 `shared_memory` 로 진짜 같은 메모리를 만든다.

```python title="shm_demo.py"
from multiprocessing import Process, shared_memory
import numpy as np


def worker(shm_name, shape, dtype):
    existing = shared_memory.SharedMemory(name=shm_name)
    arr = np.ndarray(shape, dtype=dtype, buffer=existing.buf)
    arr[:] = arr * 2          # 진짜 같은 메모리를 고친다
    existing.close()


if __name__ == "__main__":
    shape, dtype = (5,), np.int64
    shm = shared_memory.SharedMemory(create=True, size=8 * 5)
    arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
    arr[:] = [1, 2, 3, 4, 5]
    print("작업 전:", arr[:])

    p = Process(target=worker, args=(shm.name, shape, dtype))
    p.start()
    p.join()
    print("작업 후:", arr[:])   # 자식이 고친 값이 그대로 보인다

    shm.close()
    shm.unlink()
```

```text nolines
작업 전: [1 2 3 4 5]
작업 후: [ 2  4  6  8 10]
```

핵심은 **자식에게 넘긴 건 배열 자체가 아니라 `shm.name` 이라는 이름표 하나뿐**이라는 것이다. 자식은 그 이름으로 같은 공유 메모리 블록을 열어서(`SharedMemory(name=...)`), `np.ndarray` 로 **같은 바이트를 다시 해석**한다. `np.ndarray(shape, dtype, buffer=...)` 는 새 배열을 만드는 게 아니라 기존 버퍼를 배열처럼 보이게 해줄 뿐이다 — [1.5 bytes, bytearray, memoryview](#/bytes)에서 다룬 버퍼 프로토콜을 여기서 다시 만난다.

::: perf 얼마나 빠른가 — 8개 워커로 실측
피클로 큰 배열을 8개 워커에 매번 통째로 복사하는 것과, `shared_memory` 로 이름만 넘기고 워커가 같은 메모리를 직접 읽는 것을 비교했다.

```python title="shm_bench2.py — 핵심 부분"
N, WORKERS = 20_000_000, 8       # float64 배열, 약 160MB

# 방법 1: 배열 자체를 8번 피클해서 넘긴다
with Pool(WORKERS) as p:
    p.map(sum_via_pickle, [data] * WORKERS)

# 방법 2: shared_memory 이름만 8번 넘긴다
with Pool(WORKERS) as p:
    p.map(sum_via_shm, [(shm.name, data.shape, data.dtype)] * WORKERS)
```

```text nolines
피클 복사 x8         : 0.910초
shared_memory 참조 x8 : 0.297초
배 수                : 약 3.1배
```

(Python 3.14.5 / Windows, NumPy 기준 실측. 배열이 클수록, 워커 수가 많을수록 차이는 더 벌어진다 — 피클 비용은 "배열 크기 × 워커 수"로 늘어나지만 공유 메모리 비용은 늘어나지 않기 때문이다.)
:::

::: warn shared_memory는 동기화를 대신해 주지 않는다
`shared_memory` 는 **같은 메모리에 접근하게만** 해준다. 여러 워커가 동시에 같은 영역을 쓰면 [4.2 threading](#/threading)에서 본 경쟁 상태가 프로세스 버전으로 그대로 재현된다. 필요하면 `multiprocessing.Lock` 을 별도로 넘겨서 직접 잠가야 한다. 또한 `unlink()` 를 반드시 호출해서 정리해야 한다 — 안 하면 프로세스가 다 끝나도 운영체제에 공유 메모리 블록이 남는다(Windows에서는 마지막 핸들이 닫히면 자동 정리되지만, Unix 계열은 `/dev/shm` 에 파일로 남아 수동 정리가 필요할 수 있다).
:::

::: deep 왜 일반 리스트·딕셔너리는 shared_memory로 못 만드나
`shared_memory.SharedMemory` 가 주는 건 **날것의 바이트 버퍼**뿐이다. 그 위에 `int`, `list`, `dict` 같은 파이썬 객체를 얹으려면 참조 카운트, 타입 포인터, 가변 크기 같은 CPython 객체 헤더 전체가 필요한데, 이건 프로세스마다 별도의 힙에서 관리되는 값이라 공유 메모리에 그대로 얹을 수 없다. 그래서 `shared_memory` 는 **고정 크기 바이트 배열**(NumPy처럼 레이아웃이 고정된 것)에는 잘 맞고, 가변 크기 파이썬 객체에는 안 맞는다. 프로세스 간에 진짜 파이썬 객체(리스트, 딕셔너리)를 공유하고 싶으면 `multiprocessing.Manager()` 를 쓴다 — 다만 이건 내부적으로 별도 서버 프로세스와 프록시를 통해 **매 접근마다 통신**하므로 `shared_memory` 보다 훨씬 느리다. 크고 고정된 수치 배열은 `shared_memory`, 작고 복잡한 구조는 `Manager`, 그 중간은 애초에 공유하지 말고 결과만 모으는 설계(`Pool.map` 의 반환값)가 낫다.
:::

## 요약

- 스레드로 못 얻는 CPU 병렬성을 `Pool` 로 얻는다 — 실측상 4워커에서 약 2.5배, 8워커에서 약 3.7배(오버헤드 때문에 선형은 아니다).
- Windows는 `spawn` 만 지원한다. 자식은 모듈을 **처음부터 다시 import** 하므로 `if __name__ == "__main__":` 가드가 없으면 최상위 코드가 반복 실행되고, 그 안에 `Pool`/`Process` 생성이 있으면 무한 재귀로 프로세스가 폭증한다.
- 프로세스 경계를 넘는 모든 것은 `pickle` 을 거친다. 클로저·람다·락·소켓·제너레이터는 못 넘긴다. 모듈 최상위 함수·클래스만 안전하다.
- `Queue` 는 다대다 통신에 안전하고, `Pipe` 는 1대1에 더 가볍다. 종료 신호는 직접 데이터로 보내야 한다.
- `shared_memory` 는 진짜로 같은 물리 메모리를 여러 프로세스가 공유한다. 이름(`shm.name`)만 넘기면 되므로 큰 배열을 반복 전달할 때 피클 복사보다 몇 배 빠르다(실측 약 3배). 단 동기화는 별도로 해야 하고, `unlink()` 로 직접 정리해야 한다.
- 고정 크기 수치 데이터는 `shared_memory`, 임의의 파이썬 객체는 `Manager`(느림), 가장 흔한 패턴은 애초에 공유하지 않고 결과만 모으는 것이다.

::: quiz 연습문제
1. 다음 코드를 실행하면 어떤 예외가 나는가? 이유를 pickle의 동작 방식으로 설명하라.

   ```python
   from multiprocessing import Pool

   if __name__ == "__main__":
       adders = [lambda x, n=n: x + n for n in range(3)]
       with Pool(2) as p:
           print(p.map(adders[0], [1, 2, 3]))
   ```

2. Windows에서 아래 코드를 `if __name__ == "__main__":` 가드 없이 저장하고 실행하면 어떤 일이 벌어지는지, 이 절에서 실행한 결과를 근거로 예측하라. **실제로 실행하지는 마라.**

   ```python
   from multiprocessing import Pool
   p = Pool(4)
   print(p.map(lambda x: x, range(4)))
   ```

3. `shared_memory` 로 만든 `int64` 배열을 두 워커가 동시에 `arr[:] += 1` 로 100만 번씩 증가시키면 최종 값이 정확히 200만이 될까? [4.2 threading](#/threading)의 경쟁 상태 논의를 프로세스 버전으로 다시 적용해 설명하라.

4. `Queue` 에서 종료 신호(sentinel)로 `None` 대신 실제 데이터로 쓰일 수 있는 값(예: `0`)을 잘못 골랐다고 하자. 어떤 버그가 생기는가?

5. 큰 딕셔너리(수십만 키)를 여러 워커가 읽기 전용으로 참조해야 한다. `shared_memory` 를 쓸 수 없는 이유와, 대안으로 무엇을 쓸 수 있는지 이 절의 `deep` 상자 내용을 근거로 답하라.
:::

**다음 절**: [4.5 concurrent.futures](#/futures) — `threading` 과 `multiprocessing` 을 같은 인터페이스로 다루는 법.
