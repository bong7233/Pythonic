# 10.3 rclpy 노드

::: lead
지금까지 이 책에서 짠 코드는 전부 **끝이 있었다.** 함수는 값을 반환하고, 스크립트는 마지막 줄을 실행하면 끝난다. 로봇 소프트웨어는 다르다. 노드는 켜지면 죽을 때까지 콜백을 기다린다 — `for` 문도 없이, `while True`도 없이, 그냥 멈춰 있는 것처럼 보이는 코드가 실제로는 계속 일한다. 이 절은 그 "멈춰 있는 것처럼 보이는" 코드, `rclpy.spin(node)` 한 줄 안에서 실제로 무슨 일이 벌어지는지를 뜯어본다. `Node` 를 상속하는 게 왜 클래스 문법 연습이 아니라 [1.13 상속](#/inheritance)이 실제로 필요한 설계인지, 콜백이 도대체 어느 스레드에서 실행되는지 — [4.1 동시성 모델 지도](#/concurrency-map)에서 배운 개념이 여기서 그대로, 그러나 훨씬 위험하게 다시 나온다 — 그리고 콜백 그룹이라는 것을 왜 만들었는지를 다룬다. 이 셋을 정확히 모르면, 노드가 아무 이유 없이 멈춘 것처럼 보이는 사고를 반드시 겪는다.

**참고**: 이 절의 rclpy 클래스명·메서드 시그니처는 ROS 2 Jazzy 기준 `ros2/rclpy` 저장소의 `rclpy/rclpy/node.py`, `rclpy/rclpy/executors.py`, `rclpy/rclpy/callback_groups.py` 소스와 대조해 작성했다. 실제 노드를 실행한 로그가 아니라, 문서화된 동작을 바탕으로 구성한 예시임을 미리 밝힌다. 이 환경에는 rclpy가 설치되어 있지 않다 — PyPI에 배포되지 않고, ROS 2 배포판 전체를 리눅스에 설치해야만 얻을 수 있는 패키지다.
:::

## Node를 상속한다는 것

ROS 2에서 노드는 클래스다. 관용적인 형태는 이렇다.

```python title="minimal_node.py"
import rclpy
from rclpy.node import Node


class MinimalNode(Node):
    def __init__(self):
        super().__init__("minimal_node")     # ①
        self.count = 0
        self.timer = self.create_timer(1.0, self.on_timer)   # ②

    def on_timer(self):
        self.count += 1
        self.get_logger().info(f"tick {self.count}")


def main():
    rclpy.init()                # ③
    node = MinimalNode()
    try:
        rclpy.spin(node)         # ④
    finally:
        node.destroy_node()      # ⑤
        rclpy.shutdown()         # ⑥


if __name__ == "__main__":
    main()
```

여섯 지점을 순서대로 뜯어본다.

**①** `super().__init__("minimal_node")` — [1.13 상속](#/inheritance)에서 배운 `super()` 가 문자 그대로 필요하다. `rclpy.node.Node.__init__` 이 이 노드를 ROS 2 그래프에 등록하고, 이름·네임스페이스·파라미터·로거를 초기화하는 코드를 전부 실행한다. 이걸 건너뛰면 `self.create_timer` 같은 메서드가 아예 존재하지 않는 인스턴스가 된다 — 부모 클래스가 아직 자신을 초기화하지 않았기 때문이다. 이 실수는 흔하다. 초심자는 `Node.__init__` 호출을 잊고 자기 초기화 코드부터 쓰다가 `AttributeError` 를 만난다.

**②** `create_timer`, 그리고 뒤에서 다룰 `create_publisher`, `create_subscription`, `create_service`, `create_client` — 이 다섯은 전부 **"콜백을 실행 대상으로 등록한다"**는 같은 패턴을 따른다. 함수(또는 바운드 메서드)를 넘기면, 그 함수는 지금 당장 호출되는 게 아니라 **나중에 executor가 호출할 목록에 걸린다.** 이게 이 절 전체의 핵심 그림이다 — 노드를 만드는 것과 콜백이 실행되는 것은 완전히 분리된 두 단계다.

**③④⑤⑥** 이 네 줄의 순서는 고정이다. 대부분의 실수가 여기서 난다.

::: warn init → 노드 생성 → spin → destroy_node → shutdown, 순서를 바꾸면 예외가 난다
```python
node = MinimalNode()    # ❌ rclpy.init() 전에 Node를 만들면
rclpy.init()             # RCLError: rcl_node_init 실패
```

`Node.__init__` 내부는 ROS 2의 C 레벨 컨텍스트(`rcl_context_t`)를 참조한다. `rclpy.init()` 이 그 컨텍스트를 만들기 전에는 참조할 대상이 없다. 그래서 항상 **`rclpy.init()` 이 제일 먼저, `rclpy.shutdown()` 이 제일 마지막**이다.

`try/finally` 로 감싸는 이유도 명확하다. `spin()` 은 `Ctrl+C`(`KeyboardInterrupt`)나 예외로 중간에 끊길 수 있는데, 그래도 `destroy_node()` 와 `shutdown()` 은 반드시 실행돼야 한다. 안 하면 노드가 DDS(뒤에서 다룰 통신 계층, [10.8 QoS와 DDS](#/qos)) 참가자 목록에 좀비로 남을 수 있다.
:::

## rclpy.spin — "멈춰 있다"는 착각

`rclpy.spin(node)` 를 처음 보면 이상하다. 인자를 하나 받고, 반환값도 없고, 호출한 줄에서 프로그램이 그냥 멈춘 것처럼 보인다. 실제로는 이렇게 동작한다. (ROS 2 Jazzy `rclpy/rclpy/__init__.py` 기준 시그니처.)

```python
def spin(node: "Node", executor: "Executor | None" = None) -> None:
    ...
```

`spin` 은 **executor가 종료될 때까지 블로킹하는 무한 루프**다. 내부적으로 하는 일은 이렇다.

```text nolines
spin(node) 호출
  │
  ▼
executor 없으면 전역 SingleThreadedExecutor를 하나 만든다
  │
  ▼
executor.add_node(node)
  │
  ▼
루프 {
    1. node에 걸린 모든 항목(타이머, 구독, 서비스, 액션)의
       "준비됨" 상태를 OS 레벨에서 기다린다 (wait set, epoll 계열)
    2. 준비된 콜백 하나(또는 여러 개, executor 종류에 따라)를 실행한다
    3. context가 shutdown될 때까지 1로 되돌아간다
}
```

**콜백을 직접 부르는 코드는 어디에도 없다.** 당신이 쓴 `on_timer` 메서드는 executor의 내부 루프가 조건이 맞을 때 호출해 주는 것이다. `create_timer(1.0, self.on_timer)` 라고 등록해 놓고 실제로 1.0초 뒤에 실행되는 것도 이 루프 때문이다 — 정확히 1.0초가 아니라 **"1.0초가 지났고, 그 시점에 마침 이 executor 스레드가 여유가 있을 때"** 실행된다는 점을 기억해 둬라. `spin` 이 도는 스레드가 다른 일로 바쁘면 타이머는 밀린다.

::: note spin_once와 spin_until_future_complete
`spin()` 은 영원히 블로킹한다. 한 번만 처리하고 제어를 돌려받고 싶으면 `rclpy.spin_once(node, timeout_sec=...)` 를, 특정 `Future` 가 완료될 때까지만 기다리고 싶으면 `rclpy.spin_until_future_complete(node, future, timeout_sec=...)` 를 쓴다. [10.5 서비스](#/services)에서 서비스 호출 결과를 기다릴 때 바로 이 함수가 나온다 — 그리고 뒤에서 볼 것처럼, **이 함수를 콜백 안에서 잘못 쓰면 데드락이 난다.**
:::

## 콜백은 어느 스레드에서 실행되는가

[4.1 동시성 모델 지도](#/concurrency-map)에서 I/O 바운드와 CPU 바운드를 구분했다. rclpy의 executor는 그 지도 위의 특정 지점에 정확히 대응한다.

### SingleThreadedExecutor — 스레드 하나가 전부 처리한다

기본값이다. `rclpy.spin(node)` 를 그냥 부르면 이게 쓰인다. 공식 소스의 클래스 docstring 요지는 "spin()을 호출한 바로 그 스레드 안에서 콜백을 실행한다"는 것이다. 즉 타이머 콜백, 구독 콜백, 서비스 콜백 — **전부 한 스레드가 순서대로, 하나씩만** 실행한다. 동시에 두 콜백이 실행되는 일은 절대 없다.

이건 [4.6 asyncio 기초](#/asyncio-basics)에서 본 이벤트 루프와 그림이 거의 같다. 한 스레드가 "준비된 일"을 골라서 순서대로 처리한다는 점에서. 다만 결정적인 차이가 있다. **asyncio는 `await` 지점에서 협조적으로 양보하지만, rclpy 콜백 함수 안에는 그런 지점이 없다.** 콜백이 오래 걸리는 계산을 하면 — 예를 들어 `on_timer` 안에서 이미지 처리에 200ms를 쓰면 — 그동안 다른 모든 콜백(다른 토픽 구독, 다른 타이머)이 200ms 동안 밀린다. 이건 이 절 뒷부분에서 실제 사고로 이어진다.

### MultiThreadedExecutor — 스레드 풀이 나눠 처리한다

```python
from rclpy.executors import MultiThreadedExecutor

executor = MultiThreadedExecutor(num_threads=4)
executor.add_node(node)
executor.spin()
```

이름 그대로, 콜백을 스레드 풀에 나눠서 동시에 실행할 수 있다. `num_threads` 를 안 주면 CPU 코어 수를 기준으로 자동 결정한다. 이건 [4.5 concurrent.futures](#/futures)의 `ThreadPoolExecutor` 와 구조가 사실상 같다 — 실제로 rclpy의 `MultiThreadedExecutor` 내부 구현이 `ThreadPoolExecutor` 를 그대로 쓴다.

여기서 [4.3 GIL](#/gil)이 곧바로 걸린다. 스레드가 여러 개 있어도 **파이썬 바이트코드는 한 번에 한 스레드만 실행한다.** 그래서 `MultiThreadedExecutor` 가 실제로 도움이 되는 상황은 [4.1](#/concurrency-map)에서 배운 구분과 똑같다.

- **I/O 바운드 콜백** (네트워크 대기, 파일 읽기, 다른 노드의 서비스 응답 대기) — GIL을 놓아주는 동안 다른 스레드가 일할 수 있다. 여기서 진짜 이득을 본다.
- **CPU 바운드 콜백** (이미지 처리, 대량 수치 계산) — GIL 때문에 스레드를 늘려도 실제 병렬 계산은 안 된다. 이런 작업은 [4.4 multiprocessing](#/multiprocessing)으로 별도 프로세스에 빼거나, NumPy 벡터화([9.2 브로드캐스팅](#/broadcasting))로 GIL을 풀어주는 C 레벨 연산에 맡기는 게 맞다.

::: perf 스레드 수를 늘린다고 처리량이 비례해서 늘지 않는다
콜백 자체가 순수 파이썬 루프로 무거운 계산을 한다면 `num_threads=8` 로 늘려도 GIL 경합만 늘고 처리량은 거의 그대로다. 이건 [4.3 GIL](#/gil)에서 실측한 것과 동일한 현상이다. free-threaded(no-GIL) 빌드를 쓰면 사정이 달라지지만, 2026년 시점에 ROS 2 배포판 자체가 free-threaded 파이썬을 공식 지원하는지는 배포판별로 확인이 필요하다 — 아직 표준이 아니다.
:::

## 콜백 그룹 — executor가 있어도 왜 여전히 직렬화되는가

`MultiThreadedExecutor` 를 쓰면 콜백이 자동으로 병렬 실행될 거라고 생각하기 쉽다. **틀렸다.** 기본적으로는 여전히 하나씩만 실행된다. 이유는 **콜백 그룹**(callback group) 때문이다.

`create_timer`, `create_subscription` 같은 메서드는 전부 `callback_group` 인자를 받는다. 명시하지 않으면 `None` 이 전달되고, 내부적으로 **노드의 기본 콜백 그룹**으로 대체된다 — 그리고 그 기본 그룹은 `MutuallyExclusiveCallbackGroup` 이다. 즉 **한 노드 안의 모든 콜백은, 별도로 그룹을 지정하지 않는 한, 전부 같은 상호 배제 그룹에 속한다.**

콜백 그룹의 규칙은 두 가지뿐이다.

| 그룹 | 동작 |
| --- | --- |
| `MutuallyExclusiveCallbackGroup` | 이 그룹에 속한 콜백은 **한 번에 하나만** 실행된다. 실행 중인 콜백이 있으면 나머지는 대기한다 |
| `ReentrantCallbackGroup` | 이 그룹에 속한 콜백은 **동시에 여러 개** 실행될 수 있다. 자기 자신과의 재귀 실행도 허용한다 |

`MultiThreadedExecutor` 가 스레드를 4개 갖고 있어도, 콜백이 전부 같은 `MutuallyExclusiveCallbackGroup` 에 속해 있으면 **한 번에 스레드 하나만 일하고 나머지 셋은 놀게 된다.** 스레드 풀의 크기와 실제 동시 실행 콜백 수는 별개의 문제다.

::: deep 왜 기본값이 상호 배제인가
설계 이유는 명확하다. 대부분의 노드 코드는 여러 콜백이 동시에 `self.` 속성을 건드려도 안전하도록 짜여 있지 않다. [4.2 threading과 동기화](#/threading)에서 본 경쟁 상태 — 카운터 하나를 여러 스레드가 동시에 건드리는 문제 — 가 아무 보호 장치 없이 그대로 재현된다. ROS 2 설계자들은 "기본값은 안전하게, 필요할 때만 명시적으로 위험을 감수하게" 라는 원칙을 택했다. 그래서 기본은 직렬 실행이고, 병렬이 필요하면 `ReentrantCallbackGroup` 을 **직접** 만들어서 넘겨야 한다.
:::

## 왜 이게 실전에서 데드락으로 터지는가

여기가 이 절에서 가장 중요한 부분이다. rclpy를 실제로 써 본 사람이 거의 예외 없이 한 번은 당하는 패턴이다.

시나리오: 타이머 콜백 안에서 다른 노드의 서비스를 호출하고, 그 응답을 **그 자리에서 기다리고** 싶다. `rclpy.spin_until_future_complete(node, future)` 를 쓰면 될 것 같다.

```python title="deadlock_pattern.py — 실제로 걸리는 코드 (개념 예시)"
class BadNode(Node):
    def __init__(self):
        super().__init__("bad_node")
        self.cli = self.create_client(SomeService, "some_service")
        self.timer = self.create_timer(1.0, self.on_timer)   # 기본 그룹

    def on_timer(self):
        future = self.cli.call_async(SomeService.Request())
        rclpy.spin_until_future_complete(self, future)       # ← 여기서 멈춘다
        self.get_logger().info(f"응답: {future.result()}")
```

`on_timer` 는 (기본 콜백 그룹인) `MutuallyExclusiveCallbackGroup` 소속이다. 서비스 응답이 도착했을 때 그걸 처리할 콜백도 **같은 노드, 같은 기본 그룹**에 걸린다. 그런데 `SingleThreadedExecutor`(기본값)로 돈다면 — 스레드는 하나뿐이다. `on_timer` 가 `spin_until_future_complete` 로 그 하나뿐인 스레드를 붙잡고 기다리는 동안, **응답을 처리할 콜백은 영원히 실행될 기회를 얻지 못한다.** 응답을 기다리는 콜백 자신이 응답을 처리할 스레드를 막고 있는 것이다. 이게 데드락이다.

이 개념을 rclpy 없이 순수 파이썬으로 재현할 수 있다. "단일 스레드가 콜백 큐를 하나씩 처리한다"는 executor 모델만 흉내낸 것이다 — 실제 rclpy 코드가 아니라 동시성 구조를 보여주는 시뮬레이션임을 분명히 해 둔다.

```python title="single_worker_deadlock.py — SingleThreadedExecutor 개념 재현 (실행 결과 실측)"
import threading
import queue
import time


class SingleWorker:
    """SingleThreadedExecutor 흉내: 워커 스레드 하나가 콜백 큐를 순서대로 처리한다."""

    def __init__(self):
        self.queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            self.queue.get()()

    def post(self, cb):
        self.queue.put(cb)


executor = SingleWorker()
response = queue.Queue()


def service_reply_callback():
    response.put("응답 도착")          # 응답 콜백. 하지만 이 함수는 큐에서 실행될 차례가 안 온다


def timer_callback():
    executor.post(service_reply_callback)   # 응답 콜백을 같은 큐에 넣는다
    try:
        result = response.get(timeout=1.0)   # spin_until_future_complete 흉내
        print("결과 수신:", result)
    except queue.Empty:
        print("1초 대기 후에도 응답 없음 -> 데드락 재현")


executor.post(timer_callback)
time.sleep(1.5)
```

```text nolines
1초 대기 후에도 응답 없음 -> 데드락 재현
```

`timer_callback` 자신이 워커 스레드를 점유한 채 큐에서 빠져나오지 않으므로, 뒤에 넣은 `service_reply_callback` 은 영원히 큐에서 꺼내지지 않는다. (Python 3.14.5 실측 — 이 구조는 스레드 하나로 처리되는 한 몇 번을 반복해도 항상 데드락이다.)

같은 코드를 워커 두 개로 바꾸면 즉시 풀린다.

```python title="pool_resolves.py — MultiThreadedExecutor 개념 재현 (실행 결과 실측)"
class Pool:
    """MultiThreadedExecutor 흉내: 워커 스레드 여러 개가 같은 큐를 나눠 처리한다."""

    def __init__(self, n):
        self.queue = queue.Queue()
        for _ in range(n):
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            self.queue.get()()

    def post(self, cb):
        self.queue.put(cb)


executor = Pool(2)
response = queue.Queue()


def service_reply_callback():
    response.put("응답 도착")


def timer_callback():
    executor.post(service_reply_callback)
    result = response.get(timeout=1.0)      # 이번엔 다른 워커가 처리해 준다
    print("결과 수신:", result)


executor.post(timer_callback)
time.sleep(0.5)
```

```text nolines
결과 수신: 응답 도착
```

(둘 다 Python 3.14.5 / Windows 기준 실측. `queue.Queue` 와 `threading.Thread` 만으로 만든 최소 재현이며, rclpy의 실제 wait-set 구현과는 세부 구조가 다르다. 하지만 "스레드 하나가 큐를 처리하는 도중 자기 자신이 필요한 다른 항목을 못 꺼낸다"는 핵심 구조는 동일하다.)

실제 rclpy에서 이 문제의 표준 해법은 세 가지다.

1. **`MultiThreadedExecutor` 로 바꾸고, 서비스 응답 콜백을 `on_timer` 와 다른 콜백 그룹(`ReentrantCallbackGroup` 또는 별도의 `MutuallyExclusiveCallbackGroup`)에 둔다.** 이러면 서로 다른 스레드가 각자 처리할 수 있다.
2. **`spin_until_future_complete` 로 동기 대기하지 말고, `future.add_done_callback(...)` 으로 비동기 콜백을 등록한다.** 응답이 오면 그때 알아서 호출되고, `on_timer` 는 즉시 반환한다. [4.6 asyncio 기초](#/asyncio-basics)에서 배운 "블로킹 대기 대신 콜백/await로 넘긴다"는 원칙이 여기서도 그대로 적용된다.
3. **서비스 호출 자체를 콜백 밖, 별도 스레드에서 한다.**

::: danger 같은 콜백 그룹 안에서 동기 대기 = 잠재적 데드락
`SingleThreadedExecutor` 를 쓰든 `MultiThreadedExecutor` 를 쓰든, **같은 `MutuallyExclusiveCallbackGroup` 안에 있는 콜백 두 개가 서로를 기다리면 항상 데드락 가능성이 있다.** 스레드 개수는 이 문제를 해결해 주지 않는다. 콜백 그룹을 나누거나 동기 대기를 없애야 한다. 이건 문서에 흩어져 있어서 처음 겪으면 몇 시간을 태운다 — "spin_until_future_complete가 그냥 멈춘다"는 증상으로 검색하면 이 패턴이 계속 나온다.
:::

## 노드 생명주기 개요

이 절에서 다룬 `Node` 는 **생성되면 바로 살아 움직이는** 노드다. 코드가 실행되자마자 퍼블리셔가 광고되고 서비스가 열린다. 이걸 실전에서는 "일반 노드"라고 부른다.

ROS 2에는 이것과 별도로 **관리형 노드**(managed node, `LifecycleNode`)라는 게 있다. `Unconfigured → Inactive → Active → Finalized` 같은 명시적 상태 기계를 갖고, `configure()`, `activate()` 같은 전환 함수로 상태를 옮긴다. 예를 들어 카메라 드라이버 노드를 만들어 놓고도 "설정만 끝내고 실제 스트리밍은 나중에 시작"하고 싶을 때 쓴다. 대규모 로봇 시스템(전원 인가 순서, 안전 점검을 거쳐야 하는 하드웨어)에서 중요해지지만, 이 책에서 다루는 범위를 넘는 별도의 API(`rclpy_lifecycle`, C++에서는 `rclcpp_lifecycle`)다 — 노드가 "즉시 켜지는 것"과 "상태를 관리하며 켜지는 것" 두 갈래가 있다는 것만 여기서 기억해 두면 된다.

일반 노드의 실질적인 생명주기는 이 절 첫머리에서 본 여섯 줄이 전부다.

```text nolines
rclpy.init()
    │
    ▼
Node.__init__() (super().__init__)   -> ROS 그래프에 등록, 이름·파라미터 초기화
    │
    ▼
create_publisher/subscription/timer/... -> 콜백이 executor 큐에 걸린다
    │
    ▼
rclpy.spin(node)   -> 여기서 대부분의 수명을 보낸다 (블로킹)
    │  (Ctrl+C, 예외, 또는 명시적 shutdown)
    ▼
node.destroy_node()   -> 퍼블리셔/구독/타이머를 명시적으로 정리
    │
    ▼
rclpy.shutdown()   -> 컨텍스트 종료, 전역 executor 정리
```

::: tip destroy_node를 꼭 호출해야 하는 이유
[1.17 컨텍스트 매니저](#/context-managers)에서 배운 원칙 — "자원 정리는 `__del__` 이 아니라 명시적으로" — 이 여기서도 적용된다. 파이썬 객체가 가비지 컬렉트된다고 그 노드가 쓰던 DDS 참가자, 소켓, 타이머가 즉시 정리된다는 보장이 없다. `destroy_node()` 를 명시적으로 부르는 습관을 들여라. 여러 노드를 한 프로세스에서 띄우는 [10.2 워크스페이스](#/ros-workspace) 이후의 실전 코드에서는 이 차이가 실제로 자원 고갈로 이어진다.
:::

## 요약

- `Node` 는 상속해서 쓴다. `super().__init__(name)` 을 반드시 먼저 호출해야 `create_*` 메서드가 동작한다.
- 순서는 고정이다: `rclpy.init()` → 노드 생성 → `rclpy.spin(node)` → `node.destroy_node()` → `rclpy.shutdown()`.
- `spin()` 은 콜백을 직접 부르지 않는다. executor가 "준비된 콜백"을 기다렸다가 대신 호출해 주는 블로킹 루프다.
- `SingleThreadedExecutor`(기본값)는 한 스레드가 모든 콜백을 순서대로 실행한다. `MultiThreadedExecutor` 는 스레드 풀을 쓰지만 [4.3 GIL](#/gil) 때문에 CPU 바운드 콜백에서는 이득이 제한적이다.
- 콜백 그룹이 실제 동시성을 결정한다. 기본은 `MutuallyExclusiveCallbackGroup` — 스레드가 몇 개든 한 번에 하나만 실행된다. `ReentrantCallbackGroup` 을 명시해야 동시 실행이 가능하다.
- **같은 콜백 그룹 안에서 동기 대기(`spin_until_future_complete`)를 하면 데드락 가능성이 있다.** 이게 rclpy에서 가장 흔한 "노드가 멈췄다" 사고의 원인이다.
- 일반 `Node` 는 만들어지면 즉시 동작한다. 상태를 관리하며 켜지는 `LifecycleNode` 는 별도의 API다.

::: quiz 연습문제
1. 다음 코드는 실행되지 않는다. 어디가 문제인지, 왜 그 순서여야 하는지 설명하라.

   ```python
   class MyNode(Node):
       def __init__(self):
           self.count = 0
           super().__init__("my_node")
   ```

2. `SingleThreadedExecutor` 로 도는 노드에 타이머 콜백이 두 개 있다. 하나는 0.1초마다, 하나는 1초마다 실행되도록 등록했다. 0.1초짜리 콜백이 매번 300ms씩 걸리는 무거운 계산을 한다면, 1초짜리 콜백의 실제 호출 간격은 어떻게 될지 예측하고 이유를 설명하라.

3. 이 절의 `SingleWorker` / `Pool` 시뮬레이션 코드를 직접 실행해 보라. `Pool(1)` 로 바꾸면 어떤 결과가 나올지 예측한 뒤 실행해서 확인하라.

4. 어떤 노드에 구독 콜백 A와 B가 있다. 둘 다 기본 콜백 그룹에 속한다. `MultiThreadedExecutor(num_threads=4)` 로 돌리면 A와 B가 동시에 실행될 수 있는가? 왜 그런지, 어떻게 하면 동시 실행이 가능해지는지 설명하라.

5. `node.destroy_node()` 를 호출하지 않고 `rclpy.shutdown()` 만 호출하면 어떤 문제가 생길 수 있는지, [5.2 메모리 모델](#/memory)의 참조 카운팅·GC 개념과 연결해 설명하라.
:::

**다음 절**: [10.4 토픽](#/topics) — 노드가 이제 살아 움직인다. 다음은 노드끼리 데이터를 주고받는 가장 기본적인 방법인 발행/구독이다.
