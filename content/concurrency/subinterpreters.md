# 4.9 서브인터프리터 (PEP 734)

::: lead
[4.3 GIL](#/gil)에서 GIL이 스레드를 어떻게 묶어 두는지 봤다. 그 해법은 두 가지였다 — GIL을 없애거나(free-threaded 빌드), GIL을 여러 개로 쪼개거나. 서브인터프리터는 후자다. 프로세스 하나 안에 **완전히 격리된 파이썬 인터프리터를 여러 개** 띄우고, 각자에게 자기만의 GIL을 준다. 3.14의 `concurrent.interpreters`(PEP 734)로 표준 라이브러리에 들어왔다. 이 절은 이 기능을 직접 돌려 보고, 스레드·프로세스와 정확히 무엇이 다른지, 그리고 아직 무엇이 안 되는지를 있는 그대로 확인한다.
:::

## 문제: 스레드는 왜 안 늘어나는가

먼저 늘 보던 것부터 다시 확인하자. CPU 바운드 작업을 스레드로 나누면 코어가 여러 개여도 빨라지지 않는다.

```python title="bench_threads.py"
import threading, time

def cpu_task(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

N = 20_000_000

def bench_threads(workers):
    threads = [threading.Thread(target=cpu_task, args=(N,)) for _ in range(workers)]
    start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    return time.perf_counter() - start
```

이 환경(Windows, Python 3.14.5, 일반 GIL 빌드)에서 워커 수를 늘려 가며 실측하면 이렇다.

```text nolines
workers=1  직렬=0.744s  threading=0.596s  speedup=1.25x
workers=2  직렬=1.150s  threading=1.142s  speedup=1.01x
workers=4  직렬=2.276s  threading=2.332s  speedup=0.98x
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 **워커를 늘려도 속도가 그대로**라는 패턴은 GIL이 있는 한 어디서나 같다.)

워커가 4개여도 속도는 그대로다. **모든 스레드가 같은 GIL 하나를 두고 순서를 기다리기 때문**이다. [4.2 threading](#/threading)에서 봤듯 스레드는 I/O 대기 중에만 서로를 앞지를 수 있고, 순수 계산에서는 한 번에 하나만 달릴 수 있다.

선택지는 두 가지였다. `multiprocessing`으로 완전히 별도의 프로세스를 띄우거나(무겁다 — 각자 인터프리터 전체를 새로 굽는다), free-threaded 빌드로 GIL 자체를 없애거나([4.3 GIL](#/gil)). 서브인터프리터는 세 번째 길이다. **프로세스처럼 격리하되, 프로세스보다 가볍게.**

## concurrent.interpreters 기초

3.14부터 표준 라이브러리에 `concurrent.interpreters` 모듈이 들어왔다. 임포트해서 바로 확인할 수 있다.

```pyrepl
>>> import concurrent.interpreters as ci
>>> ci.get_main()
Interpreter(0)
>>> ci.get_current()
Interpreter(0)
```

새 인터프리터를 만들고, 그 안에서 코드를 돌려 보자.

```python title="sub1.py"
import concurrent.interpreters as ci

interp = ci.create()
print(interp, interp.id, interp.whence)
print(interp.is_running())

interp.exec("x = 1 + 1; print('서브 인터프리터 안에서 x =', x)")

try:
    print(x)                # 메인에서 x를 참조하면?
except NameError as e:
    print("메인 NameError:", e)

interp.close()
```

실제로 실행하면 이렇게 나온다.

```text nolines
Interpreter(1) 1 _interpreters module
False
서브 인터프리터 안에서 x = 2
메인 NameError: name 'x' is not defined
```

여기서 확인해야 할 것은 딱 하나다. **`interp.exec()` 안에서 만든 `x`는 메인 인터프리터에서 절대 보이지 않는다.** 스레드였다면 `x`는 (GIL로 순서만 맞춰질 뿐) 같은 프로세스 메모리, 같은 이름공간을 공유했을 것이다. 서브인터프리터는 처음부터 **별개의 `__main__` 모듈, 별개의 전역 상태**를 가진다.

```text nolines
   main.__main__.x   -> 정의된 적 없음 (NameError)
   interp.__main__.x -> 2

   같은 프로세스 안에 두 인터프리터, 각자 별개의 __main__ 이름공간 — 메모리를 공유하지 않는다
```

`interp.close()`로 인터프리터를 닫으면 그 상태는 통째로 사라진다. 닫힌 뒤에 다시 쓰려고 하면 바로 걸린다.

```pyrepl
>>> interp.close()
>>> interp.is_running()
Traceback (most recent call last):
  ...
concurrent.interpreters.InterpreterNotFoundError: unrecognized interpreter ID 1
```

## 스레드와 무엇이 다른가 — 각자의 GIL

이름표만 다른 격리라면 별 의미가 없다. 진짜 차이는 **GIL이 인터프리터마다 따로 있다는 것**이다. 저수준 모듈로 내려가서 직접 확인할 수 있다.

```pyrepl
>>> import _interpreters as _i
>>> _i.get_config(_i.get_main()[0])
namespace(use_main_obmalloc=True, allow_fork=True, allow_exec=True,
          allow_threads=True, allow_daemon_threads=True,
          check_multi_interp_extensions=False, gil='own')
>>> new = _i.create()
>>> _i.get_config(new)
namespace(use_main_obmalloc=False, allow_fork=False, allow_exec=False,
          allow_threads=True, allow_daemon_threads=False,
          check_multi_interp_extensions=True, gil='own')
```

두 인터프리터 모두 `gil='own'`이다. **인터프리터마다 자기 GIL을 하나씩 가진다.** 이건 PEP 684(멀티 GIL 지원)가 놓은 기반이고, PEP 734는 그 위에 `concurrent.interpreters`라는 사용하기 쉬운 API를 얹은 것이다.

::: warn sys._is_gil_enabled()는 이걸 보여주지 않는다
[4.3 GIL](#/gil)에서 쓴 `sys._is_gil_enabled()`은 **free-threaded 빌드인지**(PEP 703, GIL 자체가 빌드에서 빠졌는지)를 묻는 질문이다. 서브인터프리터가 "각자 GIL을 가지는가"와는 다른 질문이다. 실제로 확인해 보면 일반 GIL 빌드에서는 서브인터프리터 안에서도 `True`가 나온다.

```pyrepl
>>> import sys
>>> sys._is_gil_enabled()             # 메인 인터프리터
True
>>> interp = ci.create()
>>> interp.exec("import sys; print(sys._is_gil_enabled())")
True
```

두 값 다 `True`지만, 그 GIL은 **서로 다른 객체**다. 그래서 아래 벤치마크처럼 실제로 동시에 계산이 진행된다. `sys._is_gil_enabled()`로는 이 사실이 드러나지 않는다 — 반드시 실측으로 확인해야 하는 이유다.
:::

직접 실측해서 증명해 보자. `interp.call_in_thread()`는 서브인터프리터에서 함수를 실행할 새 스레드를 반환한다.

```python title="bench_subinterp.py"
import concurrent.interpreters as ci
import time

def cpu_task(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

N = 20_000_000

def bench_subinterpreters(workers):
    interps = [ci.create() for _ in range(workers)]
    start = time.perf_counter()
    threads = [interp.call_in_thread(cpu_task, N) for interp in interps]
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start
    for interp in interps:
        interp.close()
    return elapsed
```

같은 `cpu_task`, 같은 `N`으로 앞의 `threading` 벤치마크와 나란히 비교한 실측값이다.

```text nolines
workers=1  threading=0.596s   subinterpreters=0.622s
workers=2  threading=1.142s   subinterpreters=0.645s
workers=4  threading=2.332s   subinterpreters=0.740s
```

(Python 3.14.5 / Windows, 일반 GIL 빌드 기준 실측.) `threading`은 워커를 4개로 늘려도 2.3초 근처에 멈춰 있다. `subinterpreters`는 워커 4개에서도 0.74초 — **약 3배 빠르다.** 완벽한 4배가 아닌 이유는 인터프리터 생성·정리 오버헤드와 이 환경의 코어 수·스케줄링 때문이지만, 방향은 명확하다. **일반 GIL 빌드에서도 서브인터프리터는 CPU 바운드 작업을 여러 코어에 실제로 분산시킨다.** free-threaded 빌드가 없어도 이 이점을 얻는다는 게 PEP 734의 핵심 주장이고, 방금 실측으로 확인했다.

::: cote 이터레이터·코루틴과의 관계
[1.18 이터레이터·제너레이터](#/iterators)에서 코루틴이 "실행을 중간에 멈췄다 재개하는" 함수라고 배웠다. 서브인터프리터는 그것과 층위가 다르다. 코루틴은 **하나의 인터프리터, 하나의 스레드 안에서 실행 순서를 협조적으로 넘기는 것**이고, 서브인터프리터는 **여러 개의 독립된 실행 환경을 만드는 것**이다. `asyncio`가 I/O 바운드를 위한 답이라면([4.6 asyncio 기초](#/asyncio-basics)), 서브인터프리터는 CPU 바운드를 위한 새로운 선택지다.
:::

## 프로세스보다 가벼운 격리 — 정말 그런가

"프로세스보다 가볍다"는 서브인터프리터를 설명할 때 가장 많이 나오는 말이다. 검증해 보자. Windows는 `multiprocessing`의 기본 시작 방식이 `spawn`이다 — 자식마다 파이썬 인터프리터를 처음부터 새로 띄운다([4.4 multiprocessing](#/multiprocessing)). 생성 비용을 나란히 재 보자.

```python title="create_cost.py"
import concurrent.interpreters as ci
import time
import multiprocessing as mp

def noop():
    pass

if __name__ == "__main__":
    start = time.perf_counter()
    interps = [ci.create() for _ in range(20)]
    t_create = time.perf_counter() - start
    for i in interps:
        i.close()

    start = time.perf_counter()
    procs = [mp.Process(target=noop) for _ in range(20)]
    for p in procs: p.start()
    for p in procs: p.join()
    t_proc = time.perf_counter() - start
```

```text nolines
subinterpreter 20개 생성: 0.163s  (개당 8.2ms)
process 20개 생성/종료: 0.199s  (개당 10.0ms)
```

(Python 3.14.5 / Windows 기준, 3회 반복해 확인한 값의 범위 안. 절대값은 기기마다 다르다.)

숫자만 보면 실망스러울 수 있다. **개당 2ms, 20% 차이 — "프로세스보다 훨씬 가볍다"는 인상과는 거리가 멀다.** 이유는 명확하다. Windows의 `spawn`은 이미 자식마다 파이썬 인터프리터 전체를 새로 부팅하는 방식이라, 리눅스의 `fork`(부모 메모리를 그대로 복사)보다 훨씬 무겁다. 그리고 서브인터프리터도 결국 **인터프리터 하나를 처음부터 초기화하는 비용**은 그대로 진다 — `use_main_obmalloc=False`가 보여주듯 메인과 별도의 메모리 할당자(obmalloc arena)를 새로 준비해야 한다.

::: warn 과장하지 마라
서브인터프리터가 가벼운 진짜 이유는 **생성 속도**가 아니라 **프로세스 간 통신(IPC) 비용이 없다는 것**이다. 프로세스는 서로 다른 주소 공간이라 데이터를 주고받으려면 반드시 피클링 + 소켓/파이프를 거친다([4.4 multiprocessing](#/multiprocessing)). 서브인터프리터는 같은 프로세스 안에 있으므로 `Queue`나 `call()`로 오가는 데이터가 그 경로를 안 탄다. 그리고 위에서 본 `allow_fork=False`, `allow_exec=False` 설정처럼 **새 인터프리터는 fork나 exec를 스스로 하지 않는다** — 운영체제 프로세스 생성 경로 자체를 안 탄다. "프로세스보다 무조건 빠르다"가 아니라 **"통신·조율 비용의 성격이 다르다"**가 정확한 설명이다.
:::

## 데이터 주고받기

인터프리터끼리 격리돼 있다는 건, 아무 객체나 그냥 넘길 수 없다는 뜻이다. `concurrent.interpreters`는 세 가지 방법을 준다.

### `exec()` — 코드 문자열만

가장 원시적이다. 소스 코드 문자열을 넘기고 반환값은 없다. 위에서 이미 써 봤다.

### `call()` — 함수 호출, pickle로 폴백

`interp.call(func, *args)`은 "공유 가능한(shareable)" 객체는 직접, 아니면 **pickle로 직렬화해서** 넘긴다.

```pyrepl
>>> def make_list(n):
...     return list(range(n))
...
>>> interp = ci.create()
>>> interp.call(make_list, 5)
[0, 1, 2, 3, 4]
```

리스트는 공유 가능한 타입이 아니지만 결과가 제대로 돌아온다. 내부적으로 인자와 반환값을 pickle로 감싸 보낸 것이다. `multiprocessing`이 프로세스 경계를 넘길 때 쓰는 것과 같은 메커니즘이다([4.4 multiprocessing](#/multiprocessing)) — 편해 보이지만 공짜가 아니다.

### `prepare_main()` — 공유 가능한 것만, 예외 없이

`prepare_main()`은 인터프리터의 `__main__` 네임스페이스에 값을 직접 박아 넣는다. 여기는 pickle 폴백이 없다. **진짜로 공유 가능한 객체만** 받는다.

```pyrepl
>>> interp = ci.create()
>>> ci.is_shareable(3)
True
>>> ci.is_shareable("hi")
True
>>> ci.is_shareable([1, 2])
False
>>> interp.prepare_main({"x": 10, "y": 20})
>>> interp.exec("print('x + y =', x + y)")
x + y = 30
>>> interp.prepare_main({"bad": [1, 2, 3]})
Traceback (most recent call last):
  ...
concurrent.interpreters.NotShareableError: [1, 2, 3] does not support cross-interpreter data
```

**공유 가능한 것은 대체로 불변 객체와 몇 가지 특수 타입**(`int`, `str`, `bytes`, `None`, `bool`, 그리고 아래에서 볼 `Queue`)로 제한된다. [1.1 객체, 이름, 참조](#/objects-names)에서 본 가변/불변 구분이 여기서 그대로 다시 나온다 — 불변 객체는 어차피 값이 안 바뀌므로 인터프리터 경계를 넘겨도 안전하다.

### `Queue` — 진행 중인 통신

한 번 값을 박아 넣는 게 아니라 계속 주고받으려면 `ci.create_queue()`를 쓴다.

```python title="sub3.py"
import concurrent.interpreters as ci

q = ci.create_queue()

def worker(q):
    for i in range(3):
        q.put(f"작업 {i} 완료")

interp = ci.create()
t = interp.call_in_thread(worker, q)
t.join()

while True:
    try:
        print("받음:", q.get(timeout=0.1))
    except ci.QueueEmpty:
        break
```

```text nolines
받음: 작업 0 완료
받음: 작업 1 완료
받음: 작업 2 완료
```

`Queue` 자체가 공유 가능한 특수 객체라서 `call_in_thread`의 인자로 그대로 넘길 수 있다. 워커가 서브인터프리터 안에서 결과를 넣으면, 메인 인터프리터가 그걸 꺼내 간다 — [4.2 threading](#/threading)의 `queue.Queue`와 쓰는 법이 거의 같다.

## 함정: 예외도 그대로 못 넘어온다

인터프리터 경계는 예외에도 적용된다. 서브인터프리터 안에서 일어난 예외 객체는 그대로 메인으로 못 넘어온다 — 예외 객체도 결국 파이썬 객체이고, 임의의 객체는 공유 가능하지 않기 때문이다.

```python title="sub2.py"
def boom():
    raise ValueError("서브인터프리터 내부 에러")

interp = ci.create()
try:
    interp.call(boom)
except ci.ExecutionFailed as e:
    print("ExecutionFailed:", e)
    print("타입:", type(e))
```

```text nolines
ExecutionFailed: ValueError: 서브인터프리터 내부 에러

Uncaught in the interpreter:

Traceback (most recent call last):
  File "sub2.py", line 2, in boom
    raise ValueError("서브인터프리터 내부 에러")
ValueError: 서브인터프리터 내부 에러
타입: <class 'concurrent.interpreters.ExecutionFailed'>
```

원래 예외(`ValueError`)가 아니라 **항상 `ExecutionFailed`**가 올라온다. 원본 예외의 **문자열 표현**(트레이스백 포함)만 담겨서 재구성된 것이다. `except ValueError:`로 서브인터프리터 안의 에러를 잡으려 하면 안 잡힌다 — `ExecutionFailed`를 잡아야 한다. [1.16 예외와 예외 그룹](#/exceptions)에서 다룬 예외 체이닝과 비슷한 발상이지만, 여기서는 **원본 예외 객체 자체가 인터프리터 경계를 넘을 수 없어서** 생기는 제약이다.

## 생태계는 아직 이르다

여기가 이 절에서 가장 냉정하게 봐야 할 부분이다. 서브인터프리터는 **표준 라이브러리 차원에서 3.14에 갓 들어온 기능**이고, C 확장 생태계는 아직 따라오지 못했다. 직접 확인해 보자.

```python title="sub_numpy.py"
import concurrent.interpreters as ci

interp = ci.create()
try:
    interp.exec("import numpy")
except ci.ExecutionFailed as e:
    print("실패:", e)
```

이 환경에 설치된 NumPy 2.5.1로 실행하면 이렇게 실패한다.

```text nolines
실패: ImportError:
  ...
  Original error was: module numpy._core._multiarray_umath
  does not support loading in subinterpreters
  ...
```

**NumPy의 C 확장 모듈이 서브인터프리터에서 로드되는 걸 스스로 거부한다.** 앞서 본 `check_multi_interp_extensions=True` 설정이 바로 이걸 감시하는 스위치다 — C 확장이 "나는 서브인터프리터를 지원한다"고 명시적으로 선언(`Py_MOD_MULTIPLE_INTERPRETERS_SUPPORTED`)하지 않으면 임포트 자체를 막는다. NumPy는 아직 그 선언을 하지 않았다.

::: danger 과장해서 쓰면 안 되는 지점
"서브인터프리터로 NumPy 연산을 병렬화한다" 같은 이야기는 **지금은 안 된다.** 순수 파이썬 코드, 그리고 서브인터프리터를 지원하도록 명시적으로 고쳐진 소수의 C 확장만 안전하다. `Py_GIL_DISABLED`(free-threaded, [4.3 GIL](#/gil))도 똑같은 문제를 겪었다 — C 확장 생태계가 새 실행 모델을 따라잡는 데는 몇 년이 걸린다. 서브인터프리터도 지금 그 초기 구간에 있다. **직접 돌려서 안 되는 걸 확인하고 쓰는 태도가 안전하다.**
:::

## 언제 쓰나

지금 시점(3.14)에서 실용적인 결론은 이렇다.

- 순수 파이썬으로 짠 CPU 바운드 작업을 여러 코어에 분산하고 싶은데, `multiprocessing`의 IPC·피클링 비용이 부담스럽다 → 서브인터프리터가 후보다. 위 벤치마크처럼 실제로 스케일링이 나온다.
- NumPy·pandas 같은 C 확장에 크게 의존하는 계산 → 아직 이르다. [4.4 multiprocessing](#/multiprocessing)이나 [9.1 NumPy](#/numpy-basics)의 벡터화가 여전히 정답이다.
- I/O 바운드 작업 → 서브인터프리터는 애초에 답이 아니다. [4.6 asyncio 기초](#/asyncio-basics)를 써라. GIL 유무와 무관하게 I/O 대기는 이벤트 루프가 훨씬 효율적으로 처리한다.
- 이미 `concurrent.futures`에 손이 익었다면, `InterpreterPoolExecutor`가 3.14부터 같은 인터페이스로 서브인터프리터 풀을 제공한다 — [4.5 concurrent.futures](#/futures)에서 이어서 다룬다.

## 요약

- `concurrent.interpreters`(PEP 734)는 3.14 표준 라이브러리에 들어온 서브인터프리터 API다. `ci.create()`로 만들고 `exec()`/`call()`로 코드를 돌린다.
- 서브인터프리터는 스레드와 달리 **완전히 별개의 `__main__` 네임스페이스**를 가진다 — 메모리를 공유하지 않는다.
- `_interpreters.get_config()`로 확인하면 `gil='own'` — **인터프리터마다 자기 GIL을 가진다.** 그래서 일반 GIL 빌드에서도 CPU 바운드 작업이 실제로 여러 코어에 분산된다(실측: 워커 4개에서 threading 대비 약 3배).
- 생성 비용은 Windows의 `spawn` 프로세스보다 살짝 낮은 정도다(실측 8.2ms vs 10.0ms) — "훨씬 가볍다"보다는 "통신 비용의 구조가 다르다"가 정확하다.
- 데이터는 `call()`의 pickle 폴백, `prepare_main()`의 엄격한 공유 가능 객체, 또는 `Queue`로 주고받는다. 예외는 원본 타입이 아니라 항상 `ExecutionFailed`로 올라온다.
- NumPy 같은 주요 C 확장은 아직 서브인터프리터를 지원하지 않는다. 순수 파이썬 CPU 바운드 작업에 우선 써 보고, 생태계가 따라오는 걸 지켜봐야 한다.

::: quiz 연습문제
1. `ci.create()`로 인터프리터를 만들고 `interp.exec("import sys; print(sys.modules.keys())")`를 실행한 뒤, 메인 인터프리터에서 `import sys; print(sys.modules.keys())`를 실행해서 비교하라. 두 목록이 왜 다른지 설명하라.
2. 아래 코드는 왜 `NotShareableError`를 내는가? `Queue`를 써서 고쳐라.

   ```python
   interp = ci.create()
   interp.prepare_main({"log": []})
   interp.exec("log.append('hi')")
   ```

3. `interp.call()`과 `interp.exec()`의 차이를 반환값 유무와 인자 전달 방식 두 가지 기준으로 설명하라.
4. 이 절의 CPU 바운드 벤치마크를 당신의 기기에서 직접 실행하라. `threading`과 `subinterpreters`의 배수 차이가 이 절의 값과 다르다면, 코어 수 차이로 설명할 수 있는지 확인하라.
5. **생각해 볼 문제.** NumPy가 서브인터프리터 지원을 선언하기 전까지, "서브인터프리터로 데이터 분석 파이프라인을 병렬화하자"는 제안을 받는다면 어떻게 답할 것인가? [4.4 multiprocessing](#/multiprocessing)과 비교해 답하라.
:::

**다음 절**: [5.1 측정 없이 최적화 없다](#/profiling) — 지금까지 본 모든 벤치마크가 왜 "느낌"이 아니라 "측정"이어야 하는지, 그 도구들을 제대로 배운다.
