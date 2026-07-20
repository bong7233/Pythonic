# 4.2 threading과 동기화

::: lead
파이썬에 GIL이 있으니 스레드 안에서는 안전하다고 생각하기 쉽다. 틀렸다. GIL은 **한 번에 하나의 바이트코드만** 실행되게 보장할 뿐, 여러 바이트코드로 이루어진 연산의 중간에 다른 스레드가 끼어드는 것까지 막아 주지는 않는다. 이 절은 그 틈을 실제로 코드로 열어 보이고, `Lock`, `RLock`, `Condition`, `queue.Queue`로 메우는 법을 다룬다. 그리고 왜 `threading`이 I/O 바운드 작업에서만 값을 내는지 직접 측정으로 확인한다.
:::

## 카운터가 틀리는 순간

가장 단순한 프로그램부터 보자. 스레드 4개가 전역 카운터를 각자 20만 번씩 증가시킨다.

```python title="race_naive.py"
import threading

counter = 0

def worker(n):
    global counter
    for _ in range(n):
        counter += 1

N = 2_000_000
threads = [threading.Thread(target=worker, args=(N,)) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print("expected:", 8 * N)
print("actual  :", counter)
```

실행해 보면 이렇게 나온다.

```text nolines
expected: 16000000
actual  : 16000000
```

**틀리지 않는다.** 8개 스레드에 2백만 번씩, 총 1,600만 번을 증가시켜도 값이 정확히 맞는다. 여러 번 반복 실행해도 마찬가지다. 여기서 "그럼 `threading`은 안전한 것 아닌가?"라고 결론 내리면 정확히 이 책이 경고하려는 함정에 빠진 것이다.

::: danger 재현되지 않는다고 안전한 게 아니다
경쟁 상태는 **타이밍 문제**다. 이 컴퓨터의 스레드 전환 빈도, 코어 수, 운영체제 스케줄러가 우연히 두 스레드가 "정확히 같은 순간"에 카운터를 건드리는 경우를 잘 안 만들었을 뿐이다. `sys.getswitchinterval()`(기본 0.005초, 5ms)마다 GIL을 다른 스레드에 넘길 기회가 생기는데, `counter += 1` 한 번은 그보다 훨씬 빨리 끝나서 전환이 정확히 그 세 줄 사이에서 일어날 확률이 낮다.

**낮다는 것이지 0이라는 뜻이 아니다.** 서버 부하가 높아지거나, 다른 스레드 수가 늘거나, 카운터 증가 사이에 조금이라도 시간이 걸리는 코드(속성 접근, 함수 호출)가 끼면 확률은 뛴다. 그리고 그렇게 며칠에 한 번, 로그에 찍히지 않는 방식으로 터지는 버그가 제일 무섭다.
:::

이 확률을 억지로 100%까지 끌어올려서 문제를 눈으로 보자. 방법은 하나다. **읽기와 쓰기 사이에 강제로 다른 스레드에게 GIL을 넘긴다.**

```python title="race_forced.py" {8,9,10}
import threading
import time

counter = 0

def worker(n):
    global counter
    for _ in range(n):
        temp = counter      # ① 읽기
        time.sleep(0)       # ② GIL을 강제로 반납 — 다른 스레드가 끼어들 시간을 준다
        counter = temp + 1  # ③ 쓰기

N = 2000
threads = [threading.Thread(target=worker, args=(N,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print("expected:", 4 * N)
print("actual  :", counter)
print("lost    :", 4 * N - counter)
```

```text nolines
expected: 8000
actual  : 2301
lost    : 5699
```

5번 반복 실행한 결과는 각각 2301, 2223, 2261, 2303, 2245 — 매번 다르지만 항상 크게 모자란다. (Python 3.14.5 / Windows 기준 실측. **정확한 숫자는 스레드 스케줄링 타이밍에 달려 있어 기기·실행마다 바뀐다.** 여기서 고정된 사실은 "손실이 매번 수천 개 단위로 발생한다"는 것이지 2301이라는 특정 값이 아니다.) 이게 경쟁 상태의 실체다. 스레드 A가 ①에서 `counter`를 5로 읽고 ②에서 잠깐 양보하는 사이, 스레드 B가 A~C를 통째로 실행해서 `counter`를 6, 7, 8로 올려놔도 A는 자기가 읽었던 낡은 값 5에 1을 더한 6을 ③에서 그대로 덮어쓴다. B가 만든 7, 8은 통째로 사라진다.

## GIL이 있는데 왜 이런 일이 생기는가 — 바이트코드로 증명

"GIL이 있으면 한 번에 한 스레드만 도는데 왜 안전하지 않은가?"라는 질문이 당연히 나온다. 답은 **GIL이 보호하는 단위가 파이썬 한 줄이 아니라 바이트코드 하나**이기 때문이다. `counter += 1` 은 한 줄이지만 여러 개의 바이트코드로 컴파일된다.

```pyrepl
>>> import dis
>>> def worker():
...     global counter
...     counter += 1
...
>>> dis.dis(worker)
  1           RESUME                   0

  3           LOAD_GLOBAL              0 (counter)
              LOAD_SMALL_INT           1
              BINARY_OP               13 (+=)
              STORE_GLOBAL             0 (counter)
              LOAD_CONST               1 (None)
              RETURN_VALUE
```

`LOAD_GLOBAL`로 값을 읽고, `BINARY_OP`로 더하고, `STORE_GLOBAL`로 다시 쓴다. **세 개의 별개 명령이다.** GIL은 이 명령 하나하나가 원자적으로 실행되는 것은 보장하지만, `LOAD_GLOBAL`과 `STORE_GLOBAL` 사이에 GIL을 다른 스레드에 넘기는 것까지 막지는 않는다. CPython의 인터프리터 루프는 일정 개수의 바이트코드(또는 `sys.setswitchinterval` 로 정한 시간)마다 "지금 GIL을 넘겨줄까?"를 검사하는 지점(eval breaker)을 두고 있고, 그 지점이 하필 `LOAD_GLOBAL` 직후에 걸리면 정확히 앞에서 본 시나리오가 벌어진다. 바이트코드 자체는 [3.7 바이트코드와 dis](#/bytecode)에서 더 깊이 다룬다.

::: deep 왜 하필 이 세 연산이 문제인가
정수 자체는 불변 객체다([1.1 객체·이름·참조](#/objects-names)). `counter += 1` 이 하는 일은 "5라는 객체를 고치는 것"이 아니라 "이름표 `counter`를 6이라는 **새 객체**로 옮겨 붙이는 것"이다. 문제는 그 사이에 낀 **읽기 → 계산 → 이름 재배치**라는 세 단계 자체가 하나로 묶여 있지 않다는 데 있다. 이런 패턴을 **읽기-수정-쓰기(read-modify-write)**라고 부르고, 공유 자원에 대한 모든 read-modify-write는 잠재적으로 경쟁 상태다. `+=`, `.append()` 뒤의 길이 갱신, `dict[key] = dict.get(key, 0) + 1` 같은 카운팅 관용구가 전부 여기 해당한다.
:::

## Lock — 임계 구역을 하나로 묶기

해결책은 "읽기부터 쓰기까지를 하나의 원자적인 덩어리로 만드는 것"이다. `threading.Lock`이 그 덩어리(임계 구역, critical section)를 만든다.

```python title="race_fixed.py"
import threading
import time

counter = 0
lock = threading.Lock()

def worker(n):
    global counter
    for _ in range(n):
        with lock:
            temp = counter
            time.sleep(0)
            counter = temp + 1

N = 2000
threads = [threading.Thread(target=worker, args=(N,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print("expected:", 4 * N)
print("actual  :", counter)
```

```text nolines
expected: 8000
actual  : 8000
```

일부러 `time.sleep(0)`으로 경쟁을 유발했던 코드에 `with lock:`만 둘렀는데 완전히 정확해졌다. 락을 쥔 스레드가 `time.sleep(0)`으로 GIL을 반납해도, 다른 스레드는 `lock.acquire()`에서 막혀 대기할 뿐 임계 구역 안으로 들어오지 못한다.

::: tip with 문을 써라, acquire/release를 직접 부르지 마라
```python
# ❌ 예외가 나면 release가 실행 안 될 수 있다
lock.acquire()
do_something()   # 여기서 예외가 나면?
lock.release()

# ✅ with는 예외가 나도 반드시 release한다
with lock:
    do_something()
```
`Lock`은 [1.17 컨텍스트 매니저](#/context-managers)에서 다룬 프로토콜을 그대로 구현한다. `__enter__`가 `acquire()`, `__exit__`가 `release()`다.
:::

::: perf 락은 공짜가 아니다
락 획득·해제 자체에도 비용이 있다. 임계 구역을 필요 이상으로 넓게 잡으면 스레드들이 병렬로 할 수 있었던 일까지 직렬화된다. **락은 공유 자원을 건드리는 최소한의 구간에만 건다.** 위 예제에서 `time.sleep(0)`을 락 밖으로 빼면 다시 경쟁이 재현되는지 직접 실험해 보라.
:::

## RLock — 같은 스레드의 재진입

`Lock`에는 함정이 하나 있다. **같은 스레드가 이미 쥔 락을 다시 획득하려 하면 그대로 멈춘다.** 재귀 함수 안에서 락을 걸면 바로 이 상황을 만든다.

```pyrepl
>>> import threading
>>> lock = threading.Lock()
>>> lock.acquire(timeout=1)
True
>>> lock.acquire(timeout=1)      # 같은 스레드, 이미 잠긴 락을 또 요청
False                             # 1초 기다렸다가 포기
>>> lock.release()
```

`timeout` 없이 그냥 `lock.acquire()`를 두 번 부르면 두 번째 호출에서 **영원히 멈춘다.** 자기 자신을 기다리는 데드락이다.

`threading.RLock`(reentrant lock, 재진입 락)은 "누가 몇 번 잠갔는지"를 스레드 단위로 센다. 같은 스레드가 다시 `acquire`하면 카운트만 올리고 통과시키고, `release`를 그만큼 호출해야 완전히 풀린다.

```python title="rlock_demo.py"
import threading

rlock = threading.RLock()

def recurse_with_rlock(n):
    if n == 0:
        return
    with rlock:
        recurse_with_rlock(n - 1)

recurse_with_rlock(5)
print("RLock 재귀 5회 통과")
```

```text nolines
RLock 재귀 5회 통과
```

::: warn 기본값으로는 RLock을 쓰지 마라
`RLock`이 더 관대해 보이지만 기본 선택은 여전히 `Lock`이어야 한다. 재진입을 허용한다는 것은 **"이 락이 지금 잠겨 있는가"를 보고 안전을 판단할 수 없다는 뜻**이다. 같은 스레드라면 몇 번이고 통과되니까. 정말로 재귀 호출 구조 안에서 같은 락을 거는 게 불가피할 때만 `RLock`을 쓴다.
:::

## Condition — 생산자-소비자 패턴

락은 "동시에 하나만"은 해결하지만, "조건이 될 때까지 기다려라"는 못 한다. 버퍼가 가득 찼으면 생산자가 기다리고, 버퍼가 비었으면 소비자가 기다리는 전형적인 **생산자-소비자** 문제를 락만으로 풀려면 락을 반복해서 걸었다 풀었다 하며 상태를 폴링해야 한다. 낭비다.

`threading.Condition`은 락 하나에 "누군가 상태를 바꿀 때까지 잠들어 있다가, 깨어나면 다시 락을 쥔 채로 돌아오는" 대기 큐를 더한 것이다.

```python title="condition_demo.py"
import threading
import time

buffer = []
CAPACITY = 3
condition = threading.Condition()

def producer(n):
    for i in range(n):
        with condition:
            while len(buffer) >= CAPACITY:
                condition.wait()          # 락을 놓고 잠든다. 깨면 락을 다시 쥔 채 돌아온다
            buffer.append(i)
            print(f"생산 {i} -> {buffer}")
            condition.notify_all()        # 기다리던 소비자를 깨운다
        time.sleep(0.01)

def consumer(n, results):
    for _ in range(n):
        with condition:
            while not buffer:
                condition.wait()
            item = buffer.pop(0)
            print(f"소비 {item} -> {buffer}")
            condition.notify_all()
        results.append(item)
        time.sleep(0.015)

results = []
N = 8
t_prod = threading.Thread(target=producer, args=(N,))
t_cons = threading.Thread(target=consumer, args=(N, results))
t_prod.start(); t_cons.start()
t_prod.join(); t_cons.join()
print("결과:", results)
print("순서 보존:", results == list(range(N)))
```

실제 실행 로그 한 번(타임스탬프는 초 단위 `perf_counter`, 뒤 네 자리만):

```text nolines
0.0005 생산 0 -> [0]
0.0006 소비 0 -> []
0.0110 생산 1 -> [1]
0.0157 소비 1 -> []
0.0212 생산 2 -> [2]
0.0309 소비 2 -> []
0.0314 생산 3 -> [3]
0.0417 생산 4 -> [3, 4]
0.0463 소비 3 -> [4]
0.0522 생산 5 -> [4, 5]
0.0616 소비 4 -> [5]
0.0622 생산 6 -> [5, 6]
0.0726 생산 7 -> [5, 6, 7]      <- 버퍼가 CAPACITY(3)에 도달
0.0767 소비 5 -> [6, 7]
0.0921 소비 6 -> [7]
0.1072 소비 7 -> []

결과: [0, 1, 2, 3, 4, 5, 6, 7]
순서 보존: True
```

(Python 3.14.5 / Windows 기준 실측. **버퍼가 정확히 몇 번째 생산 시점에 3에 도달하는지, 타임스탬프가 얼마인지는 스레드 스케줄링에 달려 있어 실행마다 바뀐다.** 같은 코드를 바로 다시 돌리면 `0.0622 생산 6 -> [4, 5, 6]` 줄에서 이미 3에 도달하기도 한다. 고정된 사실은 세 가지뿐이다 — 소비자가 생산 속도(10ms)보다 느리게(15ms) 소비하므로 버퍼가 점점 차오른다는 것, 버퍼 길이가 `CAPACITY`인 3을 절대 넘지 않는다는 것, 순서가 끝까지 `0, 1, 2, ..., 7`로 보존된다는 것이다.) 버퍼가 그 이상 쌓이지 않는 이유는 `producer`가 `len(buffer) >= CAPACITY`일 때 `condition.wait()`로 잠들기 때문이다.

::: warn wait()는 반드시 while로 감싼다, if가 아니다
```python
# ❌ 깨어난 이유를 다시 확인하지 않는다
if not buffer:
    condition.wait()

# ✅ 깨어나도 조건이 여전히 참인지 다시 검사한다
while not buffer:
    condition.wait()
```
`notify_all()`은 대기 중인 **모든** 스레드를 깨운다. 그런데 그중 하나만 실제로 아이템을 가져갈 수 있고, 나머지는 다시 확인했을 때 버퍼가 비어 있는 것을 보고 다시 잠들어야 한다. `if`로 쓰면 이미 다른 스레드가 채 가져간 빈 버퍼에서 `pop`을 시도해 `IndexError`가 난다. 이걸 **거짓 깨어남(spurious wakeup)**에 대비한 관용구라고 부르고, 예외 없이 항상 `while`을 쓴다.
:::

## queue.Queue — 이미 만들어진 Condition

방금 짠 `Condition` 기반 생산자-소비자 코드는 사실 표준 라이브러리에 이미 있다. `queue.Queue`다. CPython 소스를 보면 정확히 위와 같은 구조로 되어 있다.

```pyrepl
>>> import queue, inspect
>>> print(inspect.getsource(queue.Queue.__init__))
    def __init__(self, maxsize=0):
        ...
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)
        self.not_full = threading.Condition(self.mutex)
        self.all_tasks_done = threading.Condition(self.mutex)
        ...
```

`not_empty`, `not_full`이라는 이름에서 바로 알 수 있다. `put()`은 꽉 찼으면 `not_full`을 기다리고, `get()`은 비었으면 `not_empty`를 기다린다. 방금 손으로 짠 걸 그대로 감싸 놓은 것이다. 그러니 직접 `Condition`을 짤 필요 없이 **큐가 필요하면 `queue.Queue`를 써라.**

```python title="queue_demo.py"
import queue
import threading
import time

q = queue.Queue(maxsize=3)

def producer():
    for i in range(6):
        q.put(i)                # 꽉 차면 자동으로 블록
        print(f"put {i}")
    q.put(None)                 # 종료 신호

def consumer():
    while True:
        item = q.get()
        if item is None:
            break
        print(f"get {item}")
        time.sleep(0.02)
        q.task_done()
    q.task_done()

t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start(); t2.start()
t1.join(); t2.join()
```

실제 실행 로그(뒤 네 자리):

```text nolines
0.8043 put 0
0.8043 put 1
0.8044 put 2      <- maxsize=3, 여기서 큐가 가득 찬다
0.8045 get 0      <- 소비자가 하나 빼가야 다음 put이 풀린다
0.8045 put 3
0.8249 get 1
0.8249 put 4
0.8454 get 2
0.8454 put 5
0.8654 get 3
0.8857 get 4
0.9060 get 5
```

`maxsize=3`을 주자마자 처음 세 개(`0, 1, 2`)는 즉시 들어가고, 네 번째 `put(3)`은 소비자가 `get 0`으로 자리를 하나 비울 때까지 **블록**된다. 이게 바로 큐를 통한 **배압(backpressure)**이다 — 생산자가 소비자보다 빠르면 자동으로 속도가 맞춰진다.

::: cote 코딩테스트 포인트
`queue.Queue`는 스레드 간 통신용이다. 단일 스레드로 BFS를 돌릴 때는 이게 아니라 `collections.deque`를 써라. `Queue`는 내부에서 락과 `Condition`을 매번 획득·해제하므로 단일 스레드 BFS에 쓰면 그 오버헤드만 고스란히 손해다. `deque`는 [7.7 스택과 큐](#/stack-queue)와 [7.14 BFS/DFS 응용](#/bfs-dfs)에서 쓰는 바로 그 자료구조다.
:::

## threading이 잘 맞는 곳, 안 맞는 곳

지금까지는 "정확성"이었다. 이제 "그래서 빨라지긴 하는가"를 측정한다. CPU를 계속 쓰는 작업과, 대부분의 시간을 그냥 기다리는(I/O) 작업을 각각 스레드로 병렬화해서 비교한다.

```python title="io_vs_cpu.py"
import threading
import time

def cpu_bound(n):
    x = 0
    for i in range(n):
        x += i * i
    return x

def io_bound(sec):
    time.sleep(sec)

def bench(fn, args, workers):
    threads = [threading.Thread(target=fn, args=args) for _ in range(workers)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - t0

N_CPU, SLEEP, WORKERS = 20_000_000, 0.5, 4

t_seq_cpu = sum(bench(cpu_bound, (N_CPU,), 1) for _ in range(WORKERS))
t_par_cpu = bench(cpu_bound, (N_CPU,), WORKERS)
print(f"CPU 바운드 - 순차 합: {t_seq_cpu:.3f}s, 동시 {WORKERS}개: {t_par_cpu:.3f}s, 배수: {t_seq_cpu/t_par_cpu:.2f}x")

t_seq_io = sum(bench(io_bound, (SLEEP,), 1) for _ in range(WORKERS))
t_par_io = bench(io_bound, (SLEEP,), WORKERS)
print(f"I/O 바운드 - 순차 합: {t_seq_io:.3f}s, 동시 {WORKERS}개: {t_par_io:.3f}s, 배수: {t_seq_io/t_par_io:.2f}x")
```

```text nolines
CPU 바운드 - 순차 합: 2.291s, 동시 4개: 2.329s, 배수: 0.98x
I/O 바운드 - 순차 합: 2.002s, 동시 4개: 0.501s, 배수: 4.00x
```

(Python 3.14.5 / Windows 기준 실측, 3회 반복. I/O 바운드 배수는 `time.sleep` 기반이라 결정적이라서 3회 모두 정확히 4.00x로 재현됐다. **CPU 바운드 배수는 그렇지 않다** — 같은 조건으로 3번 돌리면 0.98x, 0.99x, 0.96x가 나왔다. 즉 스레드를 늘려도 빨라지지 않는 정도가 아니라 **오히려 순차 실행보다 느려질 때가 더 많다.** 절대 시간과 이 CPU 배수 자체는 기기·실행마다 다르지만 **CPU 바운드는 거의 안 빨라지거나 살짝 손해를 보고, I/O 바운드는 스레드 수만큼 빨라진다는 자릿수 차이**는 일반 GIL 빌드라면 어디서나 같다.)

CPU 바운드는 스레드를 4개 굴려도 0.98배 — 사실상 그대로거나 오히려 손해다. GIL이 "한 번에 한 스레드만 파이썬 바이트코드를 실행하게" 강제하기 때문에, CPU만 쓰는 작업은 스레드를 늘려도 그 하나의 GIL을 나눠 쓸 뿐 총 작업량은 그대로다. 여기에 스레드 전환 비용(컨텍스트 스위칭, GIL 인계 오버헤드)까지 더해지므로 배수가 1.0x 밑으로, 즉 순차 실행보다 느려지는 쪽으로도 흔히 떨어진다. 반면 I/O 바운드는 정확히 4.00배 — 스레드 수만큼 그대로 빨라졌다.

::: deep I/O 대기 중에는 GIL을 실제로 놓는다
`time.sleep`, 소켓 읽기, 파일 읽기처럼 운영체제 커널을 호출해 결과를 기다리는 연산은 CPython 내부에서 **GIL을 명시적으로 반납하고** 커널 호출을 한 뒤, 결과가 오면 다시 GIL을 얻어 돌아온다. 그동안 다른 스레드가 자유롭게 GIL을 쓴다. 직접 확인해 보자.

```python title="gil_release.py"
import threading
import time

def sleeper(name):
    start = time.perf_counter()
    print(f"{name} 시작 t={start:.3f}")
    time.sleep(1)
    end = time.perf_counter()
    print(f"{name} 종료 t={end:.3f} (걸린 시간 {end - start:.3f}s)")

t0 = time.perf_counter()
threads = [threading.Thread(target=sleeper, args=(f"스레드{i}",)) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"전체: {time.perf_counter() - t0:.3f}s")
```

```text nolines
스레드0 시작 t=119163.185
스레드1 시작 t=119163.186
스레드2 시작 t=119163.186
스레드0 종료 t=119164.186 (걸린 시간 1.000s)
스레드2 종료 t=119164.186 (걸린 시간 1.000s)
스레드1 종료 t=119164.186 (걸린 시간 1.000s)
전체: 1.001s
```

3개 스레드가 `time.sleep(1)`을 **동시에** 시작해서 **동시에** 끝난다. GIL이 정말로 하나뿐이고 한 번에 한 스레드만 실행한다면 전체 시간은 3초에 가까워야 한다. 1초로 끝났다는 것은 세 스레드가 잠든 동안 GIL을 서로 방해하지 않았다는 뜻이다. `sleep` 자체는 파이썬 바이트코드를 실행하지 않으니 GIL을 쥐고 있을 이유가 없다.

이게 바로 **`threading`이 I/O 바운드 작업에 적합하고 CPU 바운드 작업에는 소용없는** 근본 이유다. CPU 바운드 작업을 진짜로 병렬화하려면 GIL 자체를 우회해야 하는데, 그 선택지는 [4.3 GIL과 free-threaded 파이썬](#/gil)과 [4.4 multiprocessing](#/multiprocessing)에서 다룬다.
:::

::: note 언제 threading을 쓰는가
동시성 모델을 고르는 전체 지도는 [4.1 동시성 모델 지도](#/concurrency-map)에서 다뤘다. 요약하면: 여러 개의 느린 I/O(네트워크 요청, 파일, DB 쿼리)를 동시에 기다려야 하면 `threading`이 적합하고, 순수 계산이 병목이면 `threading`이 아니라 `multiprocessing`이나 [4.3 GIL](#/gil)에서 다룰 free-threaded 빌드를 봐야 한다. I/O 바운드 안에서도 요즘은 `asyncio`([4.6 asyncio 기초](#/asyncio-basics))가 스레드보다 가벼운 대안으로 많이 쓰인다 — 스레드는 OS가 스케줄링하는 무거운 실행 단위지만 코루틴은 사용자 공간에서 훨씬 싸게 전환된다.
:::

## 데드락을 피하는 습관

락을 여러 개 쓰기 시작하면 새로운 위험이 생긴다. 스레드 A가 락1을 쥐고 락2를 기다리는데, 스레드 B가 락2를 쥐고 락1을 기다리면 — 둘 다 영원히 멈춘다.

```python
# ❌ 락을 얻는 순서가 스레드마다 다르면 데드락 가능
def transfer_a_to_b():
    with lock_a:
        with lock_b:
            ...

def transfer_b_to_a():
    with lock_b:      # A는 lock_a -> lock_b, 여기는 lock_b -> lock_a
        with lock_a:
            ...
```

::: tip 데드락을 피하는 세 가지 규칙
1. **락을 얻는 순서를 프로그램 전체에서 통일한다.** 항상 `lock_a`를 먼저, `lock_b`를 나중에.
2. **가능하면 락 하나로 끝낸다.** 여러 자원을 동시에 잠가야 한다면 그것들을 하나의 락으로 묶는 것부터 검토한다.
3. **`acquire(timeout=...)`로 무한 대기를 피한다.** 타임아웃이 나면 이미 쥔 락을 풀고 재시도하는 편이, 조용히 멈춰 있는 것보다 훨씬 디버깅하기 쉽다.
:::

## 요약

- GIL은 바이트코드 하나의 원자성만 보장한다. `counter += 1` 같은 한 줄짜리 연산도 `LOAD` → `BINARY_OP` → `STORE` 세 단계로 쪼개져 있어 그 사이에 경쟁 상태가 생길 수 있다.
- 경쟁 상태는 확률적이다. 작은 예제에서 재현이 안 된다고 안전하다는 뜻이 아니다.
- `Lock`은 임계 구역을 원자적으로 만든다. `with lock:`으로 쓰고, 구간은 최소한으로 좁힌다.
- `RLock`은 같은 스레드의 재진입을 허용한다. 재귀 호출 안에서 락이 불가피할 때만 쓴다.
- `Condition`은 "상태가 바뀔 때까지 기다렸다가 락을 쥔 채로 깨어나는" 대기를 제공한다. `wait()`은 항상 `while`로 감싼다.
- `queue.Queue`는 `Lock` + `Condition` 세 개(`not_empty`, `not_full`, `all_tasks_done`)로 만든 스레드 안전 큐다. 스레드 간 통신에는 직접 `Condition`을 짜지 말고 이걸 써라.
- `threading`은 I/O 바운드에서 스레드 수만큼 실측 배수가 나온다(측정: 4스레드에서 4.00배, 재현성 있음). CPU 바운드에서는 거의 안 빨라지거나 스레드 전환 비용 때문에 오히려 손해를 본다(측정: 4스레드에서 0.96~0.99배, 실행마다 변동) — GIL이 계산 자체를 나눠 주지 않기 때문이다.

::: quiz 연습문제
1. `race_naive.py`(경쟁 유발 없이 순수 `counter += 1`)를 스레드 수와 반복 횟수를 늘려가며 여러 번 돌려서, 경쟁 상태가 실제로 재현되는 조합을 찾아보라. 안 나온다면 왜 안 나오는지 `sys.getswitchinterval()`과 반복문 한 번의 실행 시간으로 설명하라.

2. `Condition` 예제의 `while not buffer:`를 `if not buffer:`로 바꾸고 소비자 스레드를 2개로 늘려 실행하라. 어떤 예외가 나는가? 왜 `while`이 필요한지 실행 로그로 설명하라.

3. `Lock` 두 개(`lock_a`, `lock_b`)를 만들고, 스레드 하나는 `lock_a` → `lock_b` 순서로, 다른 하나는 `lock_b` → `lock_a` 순서로 잠그도록 짜서 실제로 데드락을 재현하라. `acquire(timeout=2)`를 걸어서 무한 대기 대신 타임아웃으로 감지되게 고쳐라.

4. `io_vs_cpu.py`의 `WORKERS`를 8, 16으로 늘려가며 I/O 바운드 배수가 어떻게 변하는지 측정하라. CPU 코어 수(`os.cpu_count()`)를 넘어서도 I/O 바운드는 계속 선형으로 빨라지는가? 왜 그런가?

5. `queue.Queue(maxsize=1)`로 `queue_demo.py`를 다시 실행하고 로그를 관찰하라. `maxsize=3`일 때와 비교해 생산자가 기다리는 빈도가 어떻게 달라지는가?
:::

**다음 절**: [4.3 GIL, 그리고 free-threaded 파이썬](#/gil) — 3.13/3.14의 no-GIL 빌드를 실제로 설치해 스레드 스케일링 차이를 측정한다.
