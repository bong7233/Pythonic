# 4.1 동시성 모델 지도

::: lead
"동시성을 배우자"는 말은 사실 네 가지 서로 다른 기술을 뭉뚱그린 것이다. 스레드, 프로세스, asyncio, 서브인터프리터는 겉보기엔 전부 "여러 일을 동시에 하는 방법"이지만, 실제로 해결하는 문제도, 비용도, 심지어 "동시에"의 의미도 다르다. 이 절은 코드를 깊이 파기 전에 지도를 먼저 그린다. 당신의 프로그램이 **왜** 느린지 먼저 구분하고, 그다음 이 파트의 나머지 여덟 절이 각각 무엇을 답하는지 순서를 잡는다.
:::

## 프로그램이 느려지는 두 가지 이유는 완전히 다르다

다음 두 프로그램을 비교해 보자. 둘 다 "느리다"는 증상은 같지만 원인은 정반대다.

```python title="느린 이유 ①: 기다린다"
import time

def download(url):
    time.sleep(0.3)   # 실제로는 네트워크 응답을 기다리는 시간
    return f"{url} 내용"

for url in ["a.com", "b.com", "c.com", "d.com"]:
    download(url)
```

```python title="느린 이유 ②: 계산한다"
def sum_of_squares(n):
    total = 0
    for i in range(n):
        total += i * i   # CPU가 쉬지 않고 돌아간다
    return total

for _ in range(4):
    sum_of_squares(15_000_000)
```

첫 번째 프로그램은 CPU를 거의 쓰지 않는다. `time.sleep`이 실행되는 0.3초 동안 CPU는 완전히 놀고 있다. 커널이 "이 스레드는 잠들었다"고 표시하고 다른 일을 처리할 수 있다. 이런 작업을 **I/O 바운드**(I/O-bound)라고 한다 — 병목이 CPU가 아니라 디스크, 네트워크, 다른 프로세스의 응답을 **기다리는 시간**에 있다.

두 번째 프로그램은 정확히 반대다. 대기 시간은 0이고, CPU는 처음부터 끝까지 계속 계산만 한다. 이런 작업을 **CPU 바운드**(CPU-bound)라고 한다 — 병목이 순수한 계산량이다.

이 구분이 왜 중요한가. **두 문제의 해법이 정반대이기 때문**이다. I/O 바운드 문제는 "기다리는 동안 다른 일을 하게 만들면" 풀린다. CPU 바운드 문제는 "실제로 여러 CPU 코어가 동시에 계산하게 만들어야만" 풀린다. 이 차이를 무시하고 아무 동시성 도구나 골라 쓰면 — 예를 들어 CPU 바운드 작업에 스레드를 쓰면 — 셋째 절인 [4.3 GIL](#/gil)에서 볼 이유로 아무 효과가 없다.

::: tip 내 작업이 어느 쪽인지 판단하는 법
확신이 안 서면 `time.perf_counter()`로 감싸고 CPU 사용률을 보면 된다. 작업 도중 CPU 사용률이 100%에 가까우면 CPU 바운드, 특정 코어 하나만 간헐적으로 튀고 대부분 낮으면 I/O 바운드다. 대부분의 실무 코드는 **둘이 섞여 있다** — 파일을 읽고(I/O) 파싱한다(CPU). 어느 쪽이 병목인지는 실제로 측정해야 안다. [5.1 측정 없이 최적화 없다](#/profiling)에서 이 측정법을 자세히 다룬다.
:::

## I/O 바운드: 기다리는 동안 다른 일을 시킨다

I/O 바운드 작업에서 스레드를 쓰면 무슨 일이 벌어지는지 직접 실행해서 확인하자.

```python title="io_bound_demo.py"
import time
from concurrent.futures import ThreadPoolExecutor


def fake_network_call(n):
    time.sleep(0.3)          # 실제로는 소켓에서 응답을 기다리는 시간
    return n * 2


N = 8

start = time.perf_counter()
results = [fake_network_call(i) for i in range(N)]
print(f"순차 실행: {time.perf_counter() - start:.3f}초")
# 순차 실행: 2.402초

start = time.perf_counter()
with ThreadPoolExecutor(max_workers=N) as ex:
    results = list(ex.map(fake_network_call, range(N)))
print(f"스레드 실행: {time.perf_counter() - start:.3f}초")
# 스레드 실행: 0.302초  (약 7.94배)
```

8개의 "네트워크 호출"을 순차로 하면 8 × 0.3초 = 2.4초가 걸린다. 스레드 8개에 나눠 던지면 0.3초 만에 전부 끝난다 (실측 7.94배). 스레드가 8개인데 CPU 코어가 8개 없어도 이게 가능하다. **CPU를 쓰지 않고 기다리기만 하는 작업이기 때문이다.** 스레드 A가 `sleep`으로 잠들어 있는 동안 스레드 B, C, D가 각자의 대기를 동시에 시작할 수 있다.

여기서 미리 짚을 게 있다. 뒤에서 배울 [4.3 GIL](#/gil)은 "파이썬은 한 번에 한 스레드만 바이트코드를 실행한다"고 말한다. 그런데 방금 스레드로 7.94배가 나왔다. 모순이 아니다. `time.sleep`이나 실제 네트워크 I/O는 **GIL을 놓아 준다.** 대기하는 동안은 다른 스레드가 GIL을 가져가도 안전하다 — 어차피 아무 파이썬 바이트코드도 실행하고 있지 않으니까. 이 메커니즘의 정확한 동작은 [4.2 threading과 동기화](#/threading)에서 다룬다.

같은 일을 asyncio로도 할 수 있다. 스레드를 여러 개 만드는 대신, **하나의 스레드 안에서 대기 지점마다 다른 작업으로 넘어간다.**

```python title="asyncio_demo.py"
import asyncio
import time


async def fake_network_call(n):
    await asyncio.sleep(0.3)
    return n * 2


async def main():
    start = time.perf_counter()
    for i in range(8):
        await fake_network_call(i)
    print(f"순서대로 await: {time.perf_counter() - start:.3f}초")
    # 순서대로 await: 2.495초

    start = time.perf_counter()
    await asyncio.gather(*(fake_network_call(i) for i in range(8)))
    print(f"gather로 동시에: {time.perf_counter() - start:.3f}초")
    # gather로 동시에: 0.311초  (약 8.03배)


asyncio.run(main())
```

`await`를 하나씩 순서대로 하면 스레드 없는 순차 실행과 똑같이 2.5초가 걸린다. `asyncio.gather`로 한꺼번에 던지면 0.311초, 스레드 버전과 거의 같은 배속(8.03배)이 나온다. **스레드도, asyncio도 I/O 바운드 문제에서는 비슷한 효과를 낸다.** 어느 쪽을 쓸지는 성능이 아니라 다른 기준으로 갈린다 — 이건 뒤에서 표로 정리한다.

::: note 왜 asyncio 결과가 스레드보다 근소하게 빠른가
스레드는 OS가 각 스레드를 실제로 만들고 스케줄링하는 비용이 있다. asyncio는 스레드를 하나도 만들지 않고 이벤트 루프 하나가 콜백을 돌려가며 처리하므로 그 오버헤드가 없다. 작업 개수가 수백~수천 개로 늘어나면 이 차이가 커진다. 스레드는 개수가 늘면 메모리(스레드당 스택)와 컨텍스트 스위칭 비용이 선형으로 늘지만, asyncio의 태스크는 훨씬 가볍다. [4.6 asyncio 기초](#/asyncio-basics)에서 `await`가 실제로 무엇을 하는지, 이벤트 루프가 어떻게 도는지 낱낱이 본다.
:::

## CPU 바운드: 기다림 없이 순수하게 계산한다

이번엔 앞서 본 `sum_of_squares` 같은 순수 계산 작업에 같은 방식을 적용해 보자. 결과가 사뭇 다르다.

```python title="cpu_bound_demo.py — 일반 GIL 빌드에서 실행"
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def cpu_work(n):
    total = 0
    for i in range(n):
        total += i * i
    return total


N_TASKS = 4
WORK = 15_000_000

if __name__ == "__main__":
    start = time.perf_counter()
    for _ in range(N_TASKS):
        cpu_work(WORK)
    print(f"순차 실행:     {time.perf_counter() - start:.3f}초")
    # 순차 실행:     1.798초

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=N_TASKS) as ex:
        list(ex.map(cpu_work, [WORK] * N_TASKS))
    print(f"스레드 실행:   {time.perf_counter() - start:.3f}초")
    # 스레드 실행:   1.797초  (배속 1.00배 — 전혀 안 빨라졌다!)

    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=N_TASKS) as ex:
        list(ex.map(cpu_work, [WORK] * N_TASKS))
    print(f"프로세스 실행: {time.perf_counter() - start:.3f}초")
    # 프로세스 실행: 0.584초  (배속 3.08배)
```

(Python 3.14.5 / Windows / 16코어 머신 기준 실측.)

숫자를 보라. **스레드 4개를 썼는데 순차 실행과 완전히 동일하다(1.00배).** I/O 바운드에서는 스레드가 7.94배를 냈는데, CPU 바운드에서는 아무 효과가 없다. 반면 **프로세스 4개는 3.08배** 빨라졌다. 이게 이 챕터 전체의 핵심 질문으로 이어진다 — 왜 스레드는 CPU 작업에서 무용지물인가?

답은 **GIL**(Global Interpreter Lock)이다. CPython은 한 순간에 딱 하나의 스레드만 파이썬 바이트코드를 실행하도록 잠가 둔다. `sum_of_squares`처럼 순수 파이썬 계산만 하는 코드는 이 잠금을 놓을 일이 없다 — I/O처럼 "기다리는" 지점이 없으니까. 그래서 스레드 4개를 만들어도 실제로는 번갈아 가며 하나씩 실행되고, 스레드 전환 오버헤드까지 더해져 순차 실행보다 나아질 게 없다.

프로세스는 다르다. `ProcessPoolExecutor`는 완전히 별개의 파이썬 인터프리터를 4개 띄운다. 각자 자기만의 GIL을 가지므로 진짜로 4개 코어에서 동시에 돈다. 대신 프로세스를 새로 띄우는 비용, 데이터를 프로세스 사이에 주고받기 위해 피클링(pickling)하는 비용이 든다 — 그래서 4배가 아니라 3.08배가 나왔다. 이 트레이드오프는 [4.4 multiprocessing과 공유 메모리](#/multiprocessing)에서 자세히 다룬다.

::: hist GIL은 왜 있는가
GIL은 버그가 아니라 1990년대 초 CPython을 단순하고 안전하게 만들기 위한 설계 결정이다. 참조 카운팅([1.1 객체, 이름, 참조](#/objects-names)에서 본 그 참조 카운트)을 여러 스레드가 동시에 건드리면 경쟁 상태가 생겨 카운트가 어긋나고 메모리가 이르게 해제되거나 영원히 새는 사고가 난다. 모든 접근을 잠그는 대신, "바이트코드 실행 자체"를 하나의 락으로 감싸 버리면 참조 카운트도 안전해지고 C 확장을 작성하기도 쉬워진다. 30년간 이 트레이드오프가 유지된 이유이자, [4.3 GIL, 그리고 free-threaded 파이썬](#/gil)에서 그 대가와 최근의 변화를 다룰 이유다.
:::

## 자유로워진 GIL — free-threaded 빌드로 같은 실험을 반복하면

3.13부터 파이썬은 **GIL 없이 빌드하는 옵션**(free-threaded build, PEP 703)을 실험적으로 제공한다. 3.14에서는 한 단계 더 성숙했다. 이 환경(Windows, 일반 빌드)에서는 GIL이 항상 켜져 있다.

```pyrepl
>>> import sys
>>> sys._is_gil_enabled()
True
```

`uv python install 3.14t`로 free-threaded 빌드를 설치하고, 같은 CPU 바운드 벤치마크를 그 위에서 그대로 돌려 보자.

```bash
uv python install 3.14t
uv run --python 3.14t python cpu_bound_demo.py
```

```text nolines
GIL enabled: False  (python 3.14.5)
순차 실행:        1.792초
스레드 실행:      0.473초  (배속 3.79배)
프로세스 실행:    0.799초  (배속 2.24배)
```

결과가 완전히 뒤집힌다. **같은 코드, 같은 스레드 4개인데 free-threaded 빌드에서는 3.79배가 나온다** — GIL 빌드의 1.00배와 극명하게 갈린다. 4개 스레드가 4개 코어에서 진짜로 동시에 계산했다는 뜻이다(이 머신은 16코어라 4개 스레드를 동시에 굴릴 여유가 충분하다). 반대로 프로세스는 2.24배로 오히려 GIL 빌드(3.08배)보다 낮게 나왔는데, 이건 이 실행에서 프로세스를 새로 띄우는 고정 비용이 상대적으로 더 크게 잡혔기 때문이다 — 스레드가 이미 실제 병렬성을 얻었으니 프로세스의 장점(별도의 GIL)이 스레드에서도 공짜로 따라온 셈이다.

::: warn 이 벤치마크를 과장해서 읽지 마라
free-threaded 빌드는 아직 실험적이다. 단일 스레드 성능이 일반 빌드보다 떨어질 수 있고(참조 카운팅을 원자적 연산으로 바꾼 대가), C 확장 생태계가 아직 완전히 따라오지 않았다. 이 절의 숫자는 "GIL이 스레드의 병렬성을 막는다"는 사실을 보여주는 것이지, "지금 당장 프로덕션을 free-threaded로 옮겨라"는 뜻이 아니다. 실제로 무엇이 준비됐고 무엇이 아직 아닌지는 [4.3 GIL, 그리고 free-threaded 파이썬](#/gil)에서 판단한다.
:::

## 네 가지 축을 한눈에

지금까지 스레드, 프로세스, asyncio 세 가지를 실행해 봤다. 파이썬 3.13부터는 네 번째 축인 **서브인터프리터**도 있다. 넷을 한 표로 정리한다.

| 축 | 병렬 단위 | GIL 영향 | 메모리 공유 | 강점 | 약점 |
| --- | --- | --- | --- | --- | --- |
| **스레드**(`threading`) | OS 스레드 | I/O 중엔 놓임, CPU 계산 중엔 하나만 | 자동 공유 | I/O 바운드에 가볍고 빠름 | CPU 바운드엔 무용(GIL 빌드), 경쟁 상태 위험 |
| **프로세스**(`multiprocessing`) | OS 프로세스 | 프로세스마다 별도 GIL | 기본 격리, 명시적 IPC 필요 | CPU 바운드에 진짜 병렬 | 시작 비용, 피클링 비용, 메모리 배(倍)로 사용 |
| **asyncio** | 이벤트 루프의 태스크 | 단일 스레드 → GIL 경쟁 자체가 없음 | 자동 공유 (같은 스레드) | 수천 개의 I/O 대기를 가볍게 처리 | CPU 바운드엔 그대로 막힘, `await` 누락 시 전체 블로킹 |
| **서브인터프리터**(PEP 734, 3.13+) | 인터프리터별 상태 | 인터프리터마다 독립 GIL 가능 | 기본 격리, 채널로 명시적 전달 | 프로세스보다 가벼운 격리형 병렬 | 아직 신생, 생태계·도구 지원 부족 |

::: cote 코딩테스트에서는 대부분 무관하다
알고리즘 문제 풀이에서 동시성을 직접 쓸 일은 거의 없다. 시간 제한을 맞추는 건 이 파트가 아니라 [7.1 시간·공간 복잡도](#/complexity)와 [8.3 시간 초과를 피하는 관용구](#/tle)의 영역이다. 다만 실무 백엔드·크롤러·배치 파이프라인 문제가 나오는 기업 코딩테스트([8.5 기업별 출제 경향](#/company-types))에서는 "동시에 N개의 요청을 처리하라" 같은 문제에 asyncio나 스레드 풀 지식이 그대로 나온다.
:::

## 어느 축을 언제 쓰는가

표를 결정 트리로 압축하면 이렇다.

```text nolines
bound?
│
├── CPU ──▶ multiprocessing            <- 코어를 여러 개 쓰고 싶다
│           (또는 free-threaded + threading)
│
└── I/O ──┬─ many tasks ──▶ asyncio     <- 수백~수천 개를 동시에 처리
           ├─ sync libs  ──▶ threading  <- 기존 블로킹 코드를 그대로 써야 함
           └─ isolation  ──▶ subinterp  <- 가벼운 격리 병렬 (아직 신중하게)
```

실무 규칙은 더 짧다. **웹 요청 수천 개를 동시에 기다려야 하면 asyncio, 기존 블로킹 코드를 손대지 않고 I/O를 겹치고 싶으면 스레드, 순수 계산을 여러 코어로 밀고 싶으면 프로세스.** 이 세 가지 조합이 실무의 90%를 커버한다. 서브인터프리터는 아직 그 나머지 10%에서도 조심스럽게 접근해야 하는 신생 기능이다.

::: deep 스레드와 코루틴은 이미 만난 개념이다
[1.18 이터레이터와 제너레이터](#/iterators)에서 `yield`가 함수 실행을 **중간에 멈췄다가 나중에 재개**할 수 있게 한다는 걸 봤다. asyncio의 코루틴(`async def`)은 정확히 그 메커니즘 위에 세워졌다 — `await`는 "여기서 멈추고, 기다리는 게 끝나면 정확히 이 지점부터 재개하라"는 신호다. 제너레이터를 이해하고 있다면 asyncio의 절반은 이미 알고 있는 셈이다. [4.6 asyncio 기초](#/asyncio-basics)에서 이 연결을 명시적으로 다시 짚는다.
:::

## 이 파트의 로드맵

여기서부터 여덟 개 절이 이어진다. 순서에는 의도가 있다 — 얕은 이해로 다음 절을 읽으면 반드시 막힌다.

1. [4.2 threading과 동기화](#/threading) — 스레드를 실제로 쓰는 법과, 여러 스레드가 같은 데이터를 건드릴 때 생기는 경쟁 상태(race condition)를 실행해서 잡아 본다.
2. [4.3 GIL, 그리고 free-threaded 파이썬](#/gil) — 이 절에서 예고한 GIL의 정체를 CPython 소스 수준까지 파고들고, free-threaded 빌드의 실제 성숙도를 판단한다.
3. [4.4 multiprocessing과 공유 메모리](#/multiprocessing) — 프로세스를 나눌 때의 진짜 비용(피클링, `spawn` vs `fork`)과 데이터를 공유하는 방법.
4. [4.5 concurrent.futures](#/futures) — 스레드와 프로세스를 같은 인터페이스로 다루는 법.
5. [4.6 asyncio 기초: 코루틴과 이벤트 루프](#/asyncio-basics) — `await`가 내부적으로 무엇을 하는지.
6. [4.7 asyncio 실전](#/asyncio-advanced) — `TaskGroup`, 취소, 타임아웃 같은 실무 패턴.
7. [4.8 비동기 생태계](#/async-eco) — `httpx`, `anyio` 등 asyncio 위에 세워진 도구들.
8. [4.9 서브인터프리터](#/subinterpreters) — 가장 신생인 네 번째 축을 신중하게 살펴본다.

이 로드맵을 따라가면, 나중에 [7.15 최단 경로](#/shortest-path)의 다익스트라를 병렬화하거나, [10.3 rclpy 노드](#/rclpy-node)에서 ROS 2의 콜백이 왜 스레드나 코루틴으로 설계됐는지 이해할 준비가 끝난다.

## 요약

- 동시성 문제는 항상 **I/O 바운드인지 CPU 바운드인지**부터 구분한다. 해법이 정반대다.
- I/O 바운드는 스레드나 asyncio로 풀린다. 실측 약 8배 빨라졌다 — 기다리는 동안 다른 작업이 진행되기 때문이다.
- CPU 바운드는 일반 GIL 빌드의 스레드로는 전혀 빨라지지 않는다(실측 1.00배). GIL이 한 번에 한 스레드만 바이트코드를 실행하게 막기 때문이다.
- CPU 바운드는 프로세스로 풀린다(실측 3.08배, 4개 프로세스). free-threaded 빌드에서는 스레드만으로도 풀린다(실측 3.79배).
- 네 가지 축 — 스레드, 프로세스, asyncio, 서브인터프리터 — 은 각자 다른 문제를 푼다. 표와 결정 트리로 고르는 기준을 삼는다.
- free-threaded 빌드는 실험적이다. 원리를 이해하는 용도로 쓰고, 프로덕션 판단은 [4.3 GIL](#/gil)에서 다시 한다.

::: quiz 연습문제
1. 다음 작업이 I/O 바운드인지 CPU 바운드인지 각각 판단하고 이유를 설명하라.
   - 이미지 10만 장을 디스크에서 읽어 리사이즈한 뒤 저장한다.
   - 초당 수천 건의 웹훅 요청을 받아 각각 외부 API 하나씩 호출하고 응답을 기다린다.
   - 100만 개 정수 리스트를 정렬한다.

2. 이 절의 `cpu_bound_demo.py`를 스레드 개수를 8개, 16개로 늘려 가며 일반 GIL 빌드에서 실행해 보라. 배속이 어떻게 변하는가? 예측한 뒤 실행해서 확인하라.

3. 왜 `time.sleep`은 GIL을 놓아 주는데 `sum_of_squares`의 `for` 루프는 놓아 주지 않는가? 한 문장으로 설명하라.

4. 아래 결정을 각각 스레드/프로세스/asyncio/서브인터프리터 중 하나로 내려 보라. 정답은 하나가 아닐 수 있다 — 근거를 대라.
   - 10,000개의 REST API를 동시에 호출해 응답을 모은다.
   - 8코어 CPU에서 대용량 행렬 곱셈 4개를 동시에 돌린다.
   - 기존의 블로킹 DB 드라이버를 고치지 않고 요청 10개를 동시에 처리하고 싶다.
:::

**다음 절**: [4.2 threading과 동기화](#/threading) — 여러 스레드가 같은 리스트를 동시에 건드리면 정말로 무슨 일이 벌어지는지, 직접 경쟁 상태를 만들어서 확인한다.
