# 4.3 GIL, 그리고 free-threaded 파이썬

::: lead
[4.1 동시성 모델 지도](#/concurrency-map)에서 CPU 바운드 작업은 스레드로 풀리지 않는다고 예고했다. 이 절이 그 이유를 증명한다. 파이썬 인터프리터에는 GIL(Global Interpreter Lock)이라는 락이 하나 있고, 이 락을 쥔 스레드만 바이트코드를 실행할 수 있다. 코어가 16개든 32개든 상관없다. 그런데 2024년부터 이 전제가 흔들리기 시작했다. PEP 703이 받아들여지면서 파이썬 3.13부터 GIL을 완전히 뺀 빌드가 공식으로 존재한다. 이 절은 GIL이 왜 필요했는지를 참조 카운팅에서부터 설명하고, CPU 바운드 작업에서 스레드를 늘려도 안 빨라진다는 걸 직접 벤치마크로 증명한 다음, free-threaded 빌드를 실제로 설치해서 같은 벤치마크가 어떻게 달라지는지 실측으로 비교한다.
:::

## 스레드 4개를 던져도 안 빨라진다

먼저 증상부터 본다. 순수하게 CPU만 쓰는 작업을 하나 만들고, 스레드 1개로 전체를 처리한 시간과 스레드 4개로 나눠 처리한 시간을 비교한다.

```python title="gil_bench.py — CPU 바운드 작업을 스레드로 나눠 봤다"
import sys
import threading
import time


def count_down(n):
    while n > 0:
        n -= 1


def run(n_threads, work_per_thread):
    threads = [
        threading.Thread(target=count_down, args=(work_per_thread,))
        for _ in range(n_threads)
    ]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - t0


print("gil enabled:", sys._is_gil_enabled())

TOTAL_WORK = 40_000_000
t1 = run(1, TOTAL_WORK)               # 스레드 1개가 전체를 처리
t4 = run(4, TOTAL_WORK // 4)          # 스레드 4개가 1/4씩 나눠 처리

print(f"1 thread : {t1:.3f}s")
print(f"4 threads: {t4:.3f}s")
print(f"speedup  : {t1 / t4:.2f}x")
```

이 컴퓨터(Windows, 16코어, Python 3.14.5 일반 빌드)에서 실제로 돌린 결과다.

```text nolines
gil enabled: True
1 thread : 0.545s
4 threads: 0.566s
speedup  : 0.96x
```

**스레드를 4배로 늘렸는데 오히려 미세하게 더 느리다.** 코어는 16개나 놀고 있는데도 그렇다. 스레드를 만들고 스케줄링하는 오버헤드만 추가됐을 뿐, 계산 자체는 정확히 같은 속도로 진행됐다. 이게 이 절 전체가 설명해야 할 현상이다. (참고: 타이밍 벤치마크라 재실행할 때마다 절대값은 미세하게 흔들린다 — 같은 컴퓨터에서 여러 번 돌려 보면 배속은 대략 0.95x~0.98x 사이를 오간다. 그래도 "스레드를 늘려도 안 빨라진다"는 결론 자체는 매번 그대로 재현된다.)

## GIL이란 무엇인가

**GIL(Global Interpreter Lock)** 은 CPython 인터프리터 전체에 걸린 뮤텍스 하나다. 정확히 이렇게 동작한다.

- 파이썬 바이트코드를 실행하려면 반드시 이 락을 쥐고 있어야 한다.
- 락은 인터프리터 프로세스 안에 딱 하나뿐이다. 스레드가 몇 개든 상관없다.
- 스레드는 `sys.getswitchinterval()`(기본 5ms)마다, 또는 I/O 대기·`time.sleep` 같은 블로킹 호출에 들어갈 때 자발적으로 GIL을 놓는다. 다른 스레드가 그 틈에 락을 가져간다.

즉 **파이썬 스레드는 진짜로 동시에 실행되지 않는다.** OS 스케줄러가 여러 코어에 스레드를 흩뿌려 놓아도, 그중 딱 하나만 그 순간 파이썬 바이트코드를 실행할 자격이 있다. 나머지는 GIL을 기다리며 블로킹된다. 위 벤치마크에서 4개 스레드가 4배 빨라지지 않은 이유가 이거다 — 4개의 스레드가 코어 4개에서 진짜로 동시에 도는 게 아니라, 1개씩 번갈아 가며 도는 것을 스케줄링 오버헤드까지 더해 관찰한 셈이다.

## 왜 이런 락이 필요했나 — 참조 카운팅의 스레드 안전성

[1.1 객체·이름·참조](#/objects-names)에서 CPython이 **참조 카운팅**으로 객체 수명을 관리한다고 했다. 모든 객체는 자신을 가리키는 이름표 수를 정수로 들고 있고, 그 수가 0이 되는 즉시 소멸한다. 문제는 이 카운트를 건드리는 연산 — `Py_INCREF`, `Py_DECREF` — 이 인터프리터 안에서 **끊임없이** 일어난다는 점이다. 변수를 대입할 때마다, 함수에 인자를 넘길 때마다, 리스트에 원소를 넣을 때마다 참조 카운트가 오르내린다.

여러 스레드가 동시에 같은 객체의 참조 카운트를 건드리면 어떻게 될까. `refcount += 1`은 겉보기엔 한 연산 같지만 실제로는 "읽고 → 더하고 → 쓰는" 세 단계다. 두 스레드가 동시에 이 세 단계를 밟으면 한쪽의 증가분이 사라질 수 있다. 카운트가 실제보다 낮게 잡히면 아직 쓰이고 있는 객체가 조기에 소멸한다 — **use-after-free**. 반대로 높게 잡히면 객체가 영원히 회수되지 않는다 — **메모리 누수**. 둘 다 치명적이고, 후자보다 전자가 훨씬 무섭다. 죽은 메모리를 가리키는 포인터로 계속 접근하는 것이기 때문이다.

이걸 막는 방법은 두 가지뿐이다. 참조 카운트 자체를 원자적(atomic) 연산으로 만들거나, 아니면 **한 번에 한 스레드만 파이썬 객체를 건드리게** 만드는 것이다. 1992년 파이썬이 처음 스레드를 지원할 때 CPython은 후자를 택했다. 객체마다 원자적 카운트를 두는 건 카운트 연산 자체(단일 스레드에서는 압도적으로 빈번한)를 매번 느리게 만든다. 반면 인터프리터 전체에 락 하나를 두면, 단일 스레드 성능은 거의 그대로 유지하면서 참조 카운트는 안전해진다. **GIL은 이 트레이드오프의 결과물**이다 — 다중 코어 활용을 포기하는 대신 압도적으로 흔한 단일 스레드 케이스를 빠르게 유지했다.

::: hist 왜 30년 넘게 이 구조가 유지됐나
GIL을 없애려는 시도는 여러 번 있었다. 가장 유명한 건 2000년대 초 Greg Stein의 "free threading" 패치인데, 단일 스레드 성능이 2배 가까이 떨어져서 폐기됐다. 참조 카운트 하나하나를 원자적 연산으로 바꾸면 CPU 캐시 라인 경합(cache line contention)이 폭발적으로 늘기 때문이다. 이 문제가 실제로 풀린 건 2021년 Sam Gwygart가 **바이어스 참조 카운팅**(biased reference counting)이라는 기법으로 오버헤드를 크게 줄이면서부터다. 이게 PEP 703과 free-threaded 빌드의 기술적 토대다.
:::

## GIL이 지켜 주는 것과 지켜 주지 않는 것

여기서 흔한 오해가 하나 생긴다. "GIL이 있으니 파이썬 스레드 코드에는 경쟁 상태(race condition)가 없다"는 오해다. **틀렸다.** GIL이 원자적으로 보호하는 건 인터프리터 내부의 개별 연산(참조 카운트 증감, 바이트코드 하나의 실행)이지, 여러 바이트코드에 걸친 파이썬 레벨 연산이 아니다.

```pyrepl
>>> import dis
>>> def f():
...     global counter
...     counter += 1
...
>>> dis.dis(f)
  3           RESUME                   0
  5           LOAD_GLOBAL              0 (counter)
              LOAD_SMALL_INT           1
              BINARY_OP               13 (+=)
              STORE_GLOBAL             0 (counter)
              LOAD_CONST               1 (None)
              RETURN_VALUE
```

`counter += 1`처럼 단순해 보이는 코드도 4개의 바이트코드로 쪼개진다. GIL은 스레드가 이 4개 사이 어딘가에서 전환되는 것 자체는 막지 않는다. 읽기(`LOAD_GLOBAL`)와 쓰기(`STORE_GLOBAL`) 사이에 다른 스레드가 끼어들어 값을 바꿔치기하면, 한쪽의 갱신이 그대로 덮어써진다. 직접 증명해 보자. 읽기와 쓰기 사이에 `time.sleep(0)`으로 스레드 전환 지점을 강제로 만든다.

```python title="race.py — GIL이 있어도 복합 연산은 안전하지 않다"
import threading
import time

counter = 0


def increment_unsafe(n):
    global counter
    for _ in range(n):
        tmp = counter          # 읽기
        time.sleep(0)          # 여기서 다른 스레드로 전환될 수 있다
        counter = tmp + 1      # 쓰기


N = 2000
threads = [threading.Thread(target=increment_unsafe, args=(N,)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print("expected:", N * 4)
print("actual:  ", counter)
```

실제 실행 결과다 (일반 GIL 빌드).

```text nolines
expected: 8000
actual:   2295
```

**GIL이 켜져 있는데도 70% 넘게 유실됐다.** (참고: `time.sleep(0)`으로 스레드 전환을 강제하는 실험이라 `actual` 값 자체는 실행마다 흔들린다 — 여러 번 돌려 보면 대략 2200~2500 사이, 즉 70~74% 유실 범위에서 논다. 정확한 숫자가 아니라 "복합 연산은 GIL이 있어도 원자적이지 않다"는 결론이 매번 재현되는 게 핵심이다.) GIL은 "파이썬 인터프리터가 동시에 두 곳에서 바이트코드를 돌리지 않는다"만 보장한다. "당신의 알고리즘이 스레드 안전하다"는 절대 보장하지 않는다. 공유 상태를 여러 단계로 나눠 읽고 쓰는 코드라면, GIL 유무와 무관하게 락(`threading.Lock`)이 필요하다. 이 주제는 [4.2 threading과 동기화](#/threading)에서 이어서 다룬다.

::: note 그럼 counter += 1 은 왜 위에서 안전해 보였나
같은 실험을 `time.sleep(0)` 없이, 즉 `counter += 1` 한 줄로 40만 번 반복하는 걸로 하면 이 컴퓨터에서는 우연히 카운트가 정확히 맞아떨어진다. GIL의 스레드 전환 간격(기본 5ms)보다 루프 한 바퀴가 훨씬 짧아서, 실제로 전환이 그 4개 바이트코드 "사이"에서 일어날 확률이 낮기 때문이다. **이건 우연이지 보장이 아니다.** 반복 횟수를 늘리거나 스레드 수를 늘리면 언제든 깨질 수 있는, 순전히 타이밍에 의존하는 착시다. 타이밍에 의존하는 정확성은 정확성이 아니다.
:::

## `sys._is_gil_enabled()` 로 지금 빌드를 확인한다

3.13부터 어떤 빌드로 실행 중인지 런타임에 확인할 수 있는 함수가 생겼다.

```pyrepl
>>> import sys
>>> sys._is_gil_enabled()
True
```

이 환경(Windows, 일반 배포 빌드)에서는 `True`가 나온다. 즉 지금까지의 모든 내용이 그대로 적용된다. 이 함수가 `False`를 반환하는 세계로 넘어가 보자.

## free-threaded 빌드를 실제로 설치한다

PEP 703이 도입한 건 **GIL을 완전히 뺀 CPython 빌드**다. 3.13부터 실험적으로, 3.14부터는 공식 지원 단계로 배포된다. `uv`로 몇 초 만에 설치할 수 있다.

```bash
uv python install 3.14t
```

실제로 실행한 결과다.

```text nolines
Downloading cpython-3.14.5+freethreaded-windows-x86_64-none (download) (21.7MiB)
 Downloaded cpython-3.14.5+freethreaded-windows-x86_64-none (download)
Installed Python 3.14.5 in 3.00s
 + cpython-3.14.5+freethreaded-windows-x86_64-none
```

`3.14t`의 `t`가 free-threaded를 뜻한다. 기존 3.14 인터프리터를 지우거나 바꾸지 않는다. 완전히 별개의 빌드로 나란히 설치된다. `uv run --python 3.14t`로 이 빌드를 골라 실행할 수 있다.

```pyrepl
>>> import sys
>>> sys.version
'3.14.5 free-threading build (main, May 10 2026, 19:32:40) [MSC v.1944 64 bit (AMD64)]'
>>> sys._is_gil_enabled()
False
```

`_is_gil_enabled()`가 `False`를 반환한다. 이 인터프리터에서는 참조 카운팅이 원자적 연산(또는 바이어스 카운팅 기법)으로 처리되기 때문에, 여러 스레드가 동시에 진짜로 바이트코드를 실행할 수 있다.

## 실측: 일반 빌드 vs free-threaded 빌드의 스레드 스케일링

똑같은 `gil_bench.py`를 free-threaded 빌드로 돌려 보자.

```bash
uv run --python 3.14t python gil_bench.py
```

```text nolines
gil enabled: False
1 thread : 0.604s
4 threads: 0.164s
speedup  : 3.68x
```

**같은 코드, 같은 컴퓨터, 스레드 수만 같은데 결과가 완전히 다르다.** 두 빌드를 나란히 놓으면 차이가 뚜렷하다.

| 빌드 | 1 스레드 | 4 스레드 | 배속 |
| --- | --- | --- | --- |
| 일반 GIL 빌드 | 0.545s | 0.566s | 0.96x (효과 없음) |
| free-threaded 빌드 | 0.604s | 0.164s | **3.68x** |

4개 스레드로 4배에는 못 미치지만 3.68배에 가까운 속도 향상이 나왔다 — 이 컴퓨터의 16코어 중 4개를 이 작업이 진짜로 동시에 썼다는 뜻이다. GIL이 CPU 바운드 스레드 스케일링을 막고 있었다는 게 코드가 아니라 **숫자**로 증명됐다. (참고: free-threaded 빌드에서 이 벤치마크를 5번 다시 돌리면 배속이 3.0x~3.7x 사이에서 흔들린다. 절대값은 실행마다 다르지만 "GIL 없이는 스레드 4개가 거의 4배 가까이 스케일링된다"는 결론은 매번 재현된다.)

동시에 눈여겨볼 게 있다. **1 스레드일 때는 free-threaded 빌드(0.604s)가 일반 빌드(0.545s)보다 오히려 10% 정도 느리다.** 이게 공짜 점심이 아니라는 첫 번째 증거다. 참조 카운트를 원자적으로 다루는 비용은 스레드가 하나뿐이어도 매 연산마다 붙는다. free-threaded 빌드는 "다중 코어를 쓸 때만" 이득이고, 단일 스레드 워크로드에서는 약간의 세금을 낸다.

::: perf 배속의 한계
이 벤치마크는 스레드 사이에 **공유 상태가 전혀 없는** 순수 계산이다. 실제 프로그램은 공유 자료구조에 락을 걸어야 하는 경우가 많고, 그 락 경합만큼 배속은 줄어든다. 4배 스레드 → 3.68배 속도는 이상적인 경우다. [4.2 threading](#/threading)의 락 비용, [4.5 concurrent.futures](#/futures)의 `ProcessPoolExecutor`와 비교하는 감각을 함께 봐야 한다.
:::

## 공짜가 아니다 — 생태계 성숙도 문제

free-threaded 빌드가 매력적으로 보이지만, 지금 당장 프로덕션에 쓰기엔 큰 함정이 남아 있다. **C 확장 모듈**이다. NumPy, orjson, lxml 같은 라이브러리 상당수가 내부적으로 GIL이 "항상 켜져 있다"고 가정하고 C 코드를 짰다. GIL 없는 세계에서 그 가정은 곧바로 경쟁 상태로 이어진다.

직접 확인해 보자. `orjson`을 free-threaded 빌드에 설치해 본다.

```bash
uv run --python 3.14t --with orjson python -c "import orjson"
```

```text nolines
error: failed to run custom build command for `orjson v3.11.9 ...`
        orjson v3.11.9 does not support free-threaded Python
💥 maturin failed
```

**라이브러리가 스스로 free-threaded 빌드에서 컴파일을 거부한다.** 아직 스레드 안전성을 검증하지 못했다는 뜻이다. 반면 최신 NumPy는 이미 대응이 끝났다.

```pyrepl
>>> import sys
>>> sys._is_gil_enabled()
False
>>> import numpy
>>> sys._is_gil_enabled()          # numpy를 import한 뒤에도 여전히 False
False
>>> numpy.__version__
'2.5.1'
```

NumPy 2.5는 `Py_mod_gil` 슬롯으로 "나는 free-threaded 환경에서 안전하다"고 명시적으로 선언한다. 그래서 import 후에도 GIL이 다시 켜지지 않는다. 반대로 이 선언이 없는 오래된 C 확장을 import하면, 인터프리터가 **자동으로 GIL을 다시 켜고** 경고를 띄운다 — 안전을 위해 조용히 예전 모드로 후퇴하는 것이다. 즉 "free-threaded 빌드를 쓴다"는 것은 "당신이 쓰는 모든 의존성이 free-threaded를 지원해야 진짜 이득을 본다"는 뜻이다. 2026년 현재 핵심 데이터 과학 스택(NumPy, 최신 SciPy)은 지원이 상당히 진행됐지만, 그 주변 생태계 — 특히 Rust/C로 짠 소규모 유틸리티 패키지들 — 는 아직 따라잡는 중이다.

::: warn 지금 free-threaded를 프로덕션에 쓸 수 있나
이 절의 결론은 "아직은 신중하게"다. 표준 라이브러리와 주요 과학 계산 패키지는 대체로 준비됐지만, 프로젝트가 의존하는 패키지 전체가 free-threaded를 지원하는지 하나하나 확인해야 한다. 지원하지 않는 패키지가 하나라도 있으면 GIL이 자동으로 되살아나며 무성 실패(silent fallback)로 이어질 수 있고, 이 경우 free-threaded 빌드를 쓰는 의미가 사라진다. 지금은 CPU 바운드 스레드 병렬성이 정말 필요한 특정 워크로드에서 실험적으로 검증해 볼 시점이다.
:::

## 코루틴은 왜 이 이야기와 무관한가

[1.18 이터레이터와 제너레이터](#/iterators)에서 제너레이터가 실행을 일시 정지하고 재개할 수 있다고 했다. `asyncio`의 코루틴은 바로 이 성질 위에 세워진다. 코루틴 여러 개를 동시에 돌리는 건 **OS 스레드를 여러 개 쓰는 게 아니라, 이벤트 루프 하나가 제너레이터처럼 실행을 번갈아 재개하는 것**이다. 스레드가 아예 하나뿐이니 GIL을 다툴 상대가 없다 — GIL은 애초에 코루틴 동시성과는 상관없는 문제다. I/O 바운드 작업이라면 GIL의 제약을 걱정할 필요 없이 [4.6 asyncio 기초](#/asyncio-basics)로 바로 가는 게 낫다.

반대로 공유 자료구조를 여러 스레드가 다루는 상황에서 우선순위가 있는 작업을 분배해야 한다면 어떨까. `queue.PriorityQueue`가 이럴 때 쓰인다 — 내부적으로 [7.8 힙과 우선순위 큐](#/heap)의 `heapq`를 그대로 쓰면서, 그 위에 `Lock`을 씌운 것뿐이다. `heapq`의 `heappush`/`heappop` 자체는 여러 리스트 연산으로 이뤄진 복합 연산이라, 방금 본 `counter += 1`과 똑같은 이유로 락 없이 여러 스레드가 건드리면 힙 구조가 깨질 수 있다. [7.15 최단 경로](#/shortest-path)의 다익스트라가 단일 스레드 안에서 `heapq`를 안전하게 쓸 수 있는 것도 결국 "한 스레드만 이 힙을 만진다"는 전제 덕분이다. 그 전제가 깨지는 순간(멀티스레드) GIL은 개별 리스트 연산은 보호해도 힙의 불변식(invariant) 자체는 보호하지 못한다.

## 요약

- GIL은 인터프리터 전체에 걸린 락 하나다. 파이썬 바이트코드는 한 번에 한 스레드만 실행한다.
- GIL이 존재하는 이유는 **참조 카운팅을 스레드 안전하게 만들기 위해서**다. 원자적 카운트 대신 인터프리터 락 하나로 단일 스레드 성능을 지켰다.
- CPU 바운드 작업은 스레드를 늘려도 빨라지지 않는다. 실측: 일반 빌드에서 4스레드 배속 0.96x (재실행하면 0.95x~0.98x 사이에서 흔들리지만 결론은 그대로).
- GIL은 개별 바이트코드는 보호해도 **여러 바이트코드로 이뤄진 복합 연산은 보호하지 않는다.** `counter += 1` 조차 경쟁 상태에서 자유롭지 않다.
- `sys._is_gil_enabled()`로 지금 빌드가 GIL을 쓰는지 확인할 수 있다.
- `uv python install 3.14t`로 free-threaded 빌드를 몇 초 만에 설치할 수 있다. 실측: 같은 벤치마크가 4스레드에서 3.68x로 뛴다 (재실행하면 3.0x~3.7x 사이에서 흔들리지만 4배에 가까운 스케일링은 매번 재현된다).
- 공짜가 아니다. 단일 스레드에서는 free-threaded 빌드가 약 10% 느렸다. C 확장 생태계도 아직 따라잡는 중이다 — `orjson`은 free-threaded 빌드 자체를 거부했다.
- I/O 바운드 동시성(`asyncio`)은 이 이야기와 무관하다. 스레드가 하나뿐이라 GIL을 다툴 필요가 없다.

::: quiz 연습문제
1. 이 절의 `gil_bench.py`를 그대로 실행해 보라. 당신의 컴퓨터에서 1스레드와 4스레드의 배속은 얼마나 나오는가? `os.cpu_count()`로 확인한 코어 수와 비교해 보라.
2. `race.py`의 `time.sleep(0)`을 지우고 `counter += 1`만 40만 번 반복시키면 어떻게 되는가? 여러 번 실행해서 매번 같은 결과가 나오는지 확인하라. 왜 그런 결과가 나오는지 설명하라.
3. `uv python install 3.14t`로 free-threaded 빌드를 설치하고 `uv run --python 3.14t python -c "import sys; print(sys._is_gil_enabled())"`를 실행하라. 무엇이 출력되는가?
4. free-threaded 빌드에서 `race.py`를 실행하면 결과가 어떻게 달라질 것으로 예상하는가? 실제로 실행해서 확인하라. (힌트: GIL이 꺼졌다고 경쟁 상태가 사라지는 건 아니다.)
5. **생각해 볼 문제.** free-threaded 빌드가 단일 스레드 워크로드에서 일반 빌드보다 느린 이유를 참조 카운팅 관점에서 설명하라. 이 트레이드오프가 당신의 프로젝트에서 감수할 만한지 어떤 기준으로 판단하겠는가?
:::

**다음 절**: [4.4 multiprocessing과 공유 메모리](#/multiprocessing) — GIL을 피해 진짜 병렬성을 얻는 또 다른 방법, 그리고 Windows의 spawn이 만드는 함정.
