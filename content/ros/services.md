# 10.5 서비스

::: lead
[10.4 토픽](#/topics)은 "말하고 싶은 사람이 말한다"였다. 듣는 사람이 있든 없든 발행자는 신경 쓰지 않는다. 그런데 로봇 소프트웨어에는 분명히 **질문하고 답을 받아야 하는** 상황이 있다. "지금 배터리 몇 퍼센트야?", "이 좌표로 역기구학 풀어줘", "맵 저장해줘." 이런 건 발행-구독으로 억지로 흉내 낼 수는 있어도 자연스럽지 않다. 서비스가 이 자리를 위한 통신 패턴이다. 그리고 이 절에는 이 책 전체를 통틀어 가장 잘 알려진 rclpy 함정 하나가 나온다 — 겉보기엔 멀쩡한 코드가 영원히 멈춰버리는 그 함정이다.
:::

## 토픽과 서비스는 다른 질문에 답한다

토픽을 다시 떠올려 보자. 발행자는 메시지를 큐에 던지고 끝이다. 구독자가 몇 명이든, 아예 없든 상관없다. **1:N, 비동기, 단방향.**

서비스는 정반대의 계약이다.

```text nolines
   [토픽 (10.4)]  1:N, 응답 없음

   publisher ──▶ [topic]
                 │  │  │
                 ▼  ▼  ▼
              sub1 sub2 sub3


   [서비스 (이 절)]  1:1, 반드시 응답 있음

   client ──▶ request ──▶ server (딱 하나)
   client ◀── response ◀──┘
```

이 차이는 사소해 보이지만 설계 결정 하나하나에 영향을 준다.

- **1:1이다.** 같은 이름의 서비스 서버가 여러 개 떠 있으면 어느 쪽이 요청을 받을지는 정해져 있지 않다 — 토픽처럼 "다 받는" 게 아니라 로드밸런싱처럼 **한 곳만** 받는다. 그래서 서비스는 보통 노드 하나가 소유하는 단일 창구로 설계한다.
- **요청에는 반드시 응답이 온다.** 서버가 죽었거나 응답을 안 보내면 클라이언트는 (타임아웃을 걸지 않는 한) 계속 기다린다. 토픽에는 이런 "누가 기다린다"는 개념 자체가 없다.
- **요청-응답 한 쌍이 하나의 상호작용이다.** 상태를 스트리밍하는 용도가 아니다. 배터리 잔량을 1초마다 알고 싶다면 그건 서비스가 아니라 토픽으로 발행해야 한다 ([10.4 토픽](#/topics)). 서비스는 "지금 딱 한 번 물어보고 답을 받는" 상호작용용이다.

::: note 왜 REST API랑 비슷하게 느껴지는가
서비스는 HTTP의 요청-응답 모델과 정신적으로 가깝다. 클라이언트가 요청을 보내고 서버가 처리해서 응답을 돌려준다는 점에서 그렇다. 다만 전송 계층은 DDS([10.8 QoS](#/qos)에서 다룬다)이고, 프로세스 경계·기계 경계를 넘나드는 로컬 네트워크 통신이라는 점은 같다.
:::

## 서비스 정의: `.srv` 파일

토픽에 `.msg` 파일이 있듯, 서비스에는 `.srv` 파일이 있다. 요청과 응답을 `---` 한 줄로 가른다.

```text title="srv/AddTwoInts.srv"
int64 a
int64 b
---
int64 sum
```

위쪽이 요청 필드, 아래쪽이 응답 필드다. 패키지를 빌드하면 ROS 2의 인터페이스 생성기가 이 텍스트 파일로부터 파이썬 클래스 두 개를 만들어 낸다 — `AddTwoInts.Request` 와 `AddTwoInts.Response`. 각각 [1.1 객체와 이름](#/objects-names)에서 다룬 평범한 가변 객체다. 필드에 값을 넣고 꺼내는 것도 보통의 속성 접근과 다르지 않다.

```python
from example_interfaces.srv import AddTwoInts

req = AddTwoInts.Request()
req.a = 41
req.b = 1
# req는 그냥 파이썬 객체다. dataclass처럼 필드에 값을 대입할 뿐이다.
```

::: warn 커스텀 인터페이스는 별도 패키지가 필요하다
`.srv` 파일은 순수 파이썬 패키지가 아니라 `rosidl_default_generators` 를 쓰는 CMake 기반 인터페이스 패키지에 넣어야 한다. `example_interfaces`, `std_srvs` 처럼 ROS 2가 기본 제공하는 서비스 타입(`std_srvs/srv/SetBool`, `std_srvs/srv/Trigger` 등)으로 충분하다면 새 인터페이스 패키지를 만들 필요가 없다. 실무에서는 "굳이 새 타입이 필요한가"부터 먼저 따진다 — 인터페이스 하나 추가할 때마다 빌드 그래프와 배포 대상이 늘어난다 ([10.2 워크스페이스와 colcon](#/ros-workspace)).
:::

## 서버: `create_service`

서버 쪽 코드는 콜백 하나로 끝난다. 요청을 받아서 응답 객체를 채우고 돌려주면 된다.

```python title="minimal_service.py"
from example_interfaces.srv import AddTwoInts
import rclpy
from rclpy.node import Node


class MinimalService(Node):
    def __init__(self):
        super().__init__("minimal_service")
        self.srv = self.create_service(
            AddTwoInts, "add_two_ints", self.add_two_ints_callback
        )

    def add_two_ints_callback(self, request, response):
        response.sum = request.a + request.b
        self.get_logger().info(f"요청: {request.a} + {request.b}")
        return response  # 반드시 response 객체를 반환한다


def main():
    rclpy.init()
    node = MinimalService()
    rclpy.spin(node)
    rclpy.shutdown()
```

여기서 눈여겨볼 것 하나. `add_two_ints_callback` 은 다른 콜백([10.3 rclpy 노드](#/rclpy-node)에서 본 타이머·구독 콜백)과 똑같이 **executor가 스핀하는 도중에 호출된다.** 서비스 콜백이라고 특별할 게 없다 — 콜백 큐에 들어온 작업 하나일 뿐이다. 이 사실이 뒤에서 함정의 원인이 된다.

## 클라이언트: 동기 호출 vs 비동기 호출

여기서부터가 이 절의 핵심이다. rclpy의 `Client` 객체는 요청을 보내는 방법을 **두 가지** 제공한다. 이 두 가지가 겉보기엔 비슷해 보이지만 실행 모델 수준에서 완전히 다르게 동작한다.

```python title="client_call_async.py"
from example_interfaces.srv import AddTwoInts
import rclpy
from rclpy.node import Node


class MinimalClientAsync(Node):
    def __init__(self):
        super().__init__("minimal_client_async")
        self.cli = self.create_client(AddTwoInts, "add_two_ints")
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("서비스가 아직 안 떴다. 계속 기다린다...")
        self.req = AddTwoInts.Request()

    def send_request(self, a, b):
        self.req.a = a
        self.req.b = b
        return self.cli.call_async(self.req)  # 즉시 Future를 반환한다


def main():
    rclpy.init()
    node = MinimalClientAsync()
    future = node.send_request(41, 1)
    rclpy.spin_until_future_complete(node, future)  # 메인 스레드에서 기다린다
    response = future.result()
    node.get_logger().info(f"결과: {response.sum}")
    rclpy.shutdown()
```

`call_async(req)` 는 요청을 보내고 **즉시 `rclpy.task.Future` 객체를 돌려준다.** 응답이 아직 안 왔어도 함수는 바로 리턴한다. 결과를 얻는 방법은 두 가지다.

1. `rclpy.spin_until_future_complete(node, future)` 로 **executor 바깥, 메인 스레드**에서 future가 채워질 때까지 스핀시킨다.
2. `future.add_done_callback(콜백)` 으로 "다 되면 이걸 실행해라"만 등록하고, 지금 실행 중인 콜백은 바로 끝낸다.

`rclpy.task.Future` 는 `add_done_callback`, `done()`, `result()`, `exception()`, `cancel()` 같은 메서드를 제공한다. [4.5 concurrent.futures](#/futures)에서 본 `Future` 와 정신적으로 같은 설계다 — "지금은 없지만 나중에 채워질 값"을 객체로 다루는 방식은 스레드 풀이든 ROS 2 서비스든 똑같다. 다만 rclpy의 Future는 스레드 풀이 아니라 **executor의 스핀 사이클**이 채운다는 점이 다르다.

`Client` 는 `call(req)` 라는 **동기(블로킹) 메서드**도 제공한다. 요청을 보내고 응답이 올 때까지 그 자리에서 멈춰 있다가 응답 객체를 바로 돌려준다. 코드만 보면 훨씬 직관적이다.

```python
response = self.cli.call(req)  # 응답이 올 때까지 이 줄에서 멈춘다
```

문제는 바로 이 한 줄이다.

## 함정: 왜 콜백 안에서 동기 호출을 하면 멈추는가

::: danger 노드 콜백 안에서 call()을 쓰면 대부분 데드락이 난다
```python
class BadTimerNode(Node):
    def __init__(self):
        super().__init__("bad_timer_node")
        self.cli = self.create_client(AddTwoInts, "add_two_ints")
        self.create_timer(1.0, self.timer_callback)   # ❌

    def timer_callback(self):
        req = AddTwoInts.Request()
        req.a, req.b = 1, 2
        response = self.cli.call(req)   # 여기서 영원히 멈춘다
        self.get_logger().info(f"결과: {response.sum}")
```
:::

이 코드는 컴파일 에러도, 런타임 예외도 없다. **그냥 조용히 멈춘다.** 원인을 이해하려면 [10.3 rclpy 노드](#/rclpy-node)에서 본 executor의 실행 모델을 다시 꺼내야 한다.

`rclpy.spin(node)` 는 노드에 등록된 콜백(타이머, 구독, 서비스 서버, 서비스 클라이언트의 응답 처리)을 **큐에서 하나씩 꺼내 실행하는 루프**다. 기본 `SingleThreadedExecutor` 는 이 루프를 스레드 하나로 돈다. 그리고 노드의 모든 콜백은 특별히 지정하지 않는 한 **같은 `MutuallyExclusiveCallbackGroup`** 에 속한다 — 이름 그대로, 그 그룹 안의 콜백은 **동시에 두 개가 실행될 수 없다.**

`timer_callback` 이 실행되기 시작하면 executor의 유일한 실행 슬롯은 그 콜백이 점유한다. 그 콜백 안에서 `self.cli.call(req)` 를 부르면, rclpy는 내부적으로 "응답이 올 때까지 spin을 계속 돌려서 응답 콜백을 처리해라"는 식으로 기다린다. 그런데 **응답을 처리하는 것 역시 콜백이고, 같은 노드의 같은 콜백 그룹에 속해 있다.** 지금 실행 중인 `timer_callback` 이 아직 안 끝났으니, 같은 그룹의 다른 콜백(응답 처리)은 실행될 차례가 절대 오지 않는다.

```text nolines
   executor thread (단 하나):

   |<-- timer_callback 실행 중, 그 안에서 call() 대기 중, 영원히 -->|
                              ^
                              |  이 대기를 풀어 줄 응답 콜백은
                              |  '같은 그룹'이라 실행 기회를 못 받는다
                              |
   응답 콜백: [ 대기열에 갇혀서 못 나옴 ]
```

**직접 서로를 기다리는 두 콜백이 하나의 실행 슬롯을 두고 경쟁하는 것**이다. 스레드 두 개가 서로의 락을 기다리는 전형적인 데드락([4.2 threading](#/threading)에서 본 그 문제)과 구조가 똑같다. 다른 점은, 이건 `Lock` 이 아니라 **executor의 콜백 그룹이 락 역할**을 한다는 것뿐이다.

::: note rclpy를 실행하지 않고 이 함정을 확인하는 법
이 환경에는 ROS 2가 없어서 위 코드를 실제로 돌려 데드락을 재현할 수는 없다. 대신 executor의 핵심 구조 — "콜백 큐 하나, 실행 스레드 하나, 콜백 안에서 같은 큐의 다른 항목을 기다림" — 만 뽑아내 순수 파이썬으로 축소 모델을 만들면 왜 멈추는지 그대로 확인할 수 있다. 영원히 멈추면 곤란하니 스핀 횟수에 상한을 뒀다. 실제 rclpy에는 이 상한이 없다 — 그래서 진짜로 멈춘다.

```python title="executor_deadlock_demo.py — 순수 파이썬 축소 모델 (rclpy 아님)"
import queue
import time


class TinySingleThreadedExecutor:
    """rclpy.executors.SingleThreadedExecutor의 극단적 단순화 모델.
    콜백을 큐에 쌓고, 스레드 하나가 하나씩 꺼내 실행한다."""

    def __init__(self):
        self.callback_queue = queue.Queue()
        self.futures = {}

    def create_job(self, fn):
        self.callback_queue.put(fn)

    def deliver_response(self, future_id, value):
        # 서비스 응답을 처리하는 것도 '콜백 하나'로 같은 큐에 들어간다
        self.callback_queue.put(lambda: self.futures.__setitem__(future_id, value))

    def spin_once(self, timeout=0.2):
        try:
            self.callback_queue.get(timeout=timeout)()
            return True
        except queue.Empty:
            return False


def broken_callback(executor):
    future_id = "req-1"
    executor.deliver_response(future_id, 42)   # 응답 처리 콜백을 큐에 넣음
    spins = 0
    while future_id not in executor.futures:    # call()의 내부 대기 루프를 흉내
        spins += 1
        if spins > 5:                           # 실제 rclpy에는 이 상한이 없다
            return None
        time.sleep(0.05)
    return executor.futures[future_id]


executor = TinySingleThreadedExecutor()
executor.create_job(lambda: print("결과:", broken_callback(executor)))
for _ in range(4):
    executor.spin_once()
```

```text nolines
결과: None
```

`broken_callback` 이 실행되는 동안 executor 스레드는 딴 일을 못 한다. `deliver_response` 가 큐에 넣어 둔 응답 처리 job은 `broken_callback` 이 스스로 리턴하기 전까지 절대 실행되지 않는다 — 실행할 스레드가 없으니까. 위 코드는 상한 5번을 넘기면 포기하도록 만들어서 `None` 을 출력했지만, 실제 rclpy의 `call()` 은 이 상한이 없어서 **정말로 영원히 멈춘다.**
:::

## 데드락을 피하는 법

공식 문서(`Sync-Vs-Async` 가이드)의 결론은 명확하다. **동기 `call()` 을 콜백 안에서 쓰지 마라.** 세 가지 선택지가 있다.

1. **가장 안전함 — 항상 `call_async()` 를 쓴다.** 콜백은 요청만 보내고 `add_done_callback` 으로 이어질 작업을 등록한 뒤 즉시 리턴한다. 콜백을 절대 블로킹하지 않으므로 `SingleThreadedExecutor` 에서도 안전하다.
2. **콜백 그룹을 분리한다.** 요청을 보내는 콜백과 클라이언트(따라서 그 응답 처리)를 **서로 다른 콜백 그룹**에 두고, `MultiThreadedExecutor` 로 스핀한다. 서로 다른 그룹의 콜백은 동시에 실행될 수 있으니 응답 처리가 막히지 않는다.
3. **`ReentrantCallbackGroup` 을 쓴다.** 이 그룹에 속한 콜백들은 서로 겹쳐 실행되는 것을 허용한다. ROS 2 공식 예제(`examples_rclpy_minimal_client`)가 정확히 이 패턴을 쓴다 — 타이머 콜백과 클라이언트를 **같은** `ReentrantCallbackGroup` 에 등록해서, 타이머 콜백이 `await` 로 기다리는 동안에도 응답 콜백이 끼어들어 실행될 수 있게 한다.

```python title="reentrant_client.py — 공식 예제 패턴 요약"
from rclpy.callback_groups import ReentrantCallbackGroup

cb_group = ReentrantCallbackGroup()
cli = node.create_client(AddTwoInts, "add_two_ints", callback_group=cb_group)


async def call_service():
    req = AddTwoInts.Request()
    req.a, req.b = 41, 1
    future = cli.call_async(req)
    result = await future                       # 콜백이지만 여기서 실행을 양보한다
    node.get_logger().info(f"결과: {result.sum}")


node.create_timer(0.5, call_service, callback_group=cb_group)
```

`await future` 는 [4.6 asyncio 기초](#/asyncio-basics)에서 본 것과 같은 원리다 — 스레드를 블로킹하는 게 아니라 **제어를 이벤트 루프(여기서는 executor)에 돌려준다.** 그래서 같은 그룹에 있어도 다른 콜백이 그 사이에 실행될 여지가 생긴다.

::: tip 실전 감각: 왜 이 버그는 발견하기 어려운가
테스트 환경에서는 서비스 서버가 항상 빠르게 응답하고, 콜백 몇 개만 등록돼 있어서 우연히 안 걸리는 경우가 많다. 노드가 커지고 콜백이 늘어나서 큐에 경합이 생기기 시작하면 그제야 "가끔 멈춘다"는 증상으로 나타난다. 예외가 안 나니 로그도 없고, 프로파일러를 붙여도 "그냥 대기 중"이라 원인을 짚기 어렵다. **처음부터 `call_async()` 만 쓰기로 정하는 것**이 가장 값싼 예방책이다. 동기 `call()` 은 진짜 메인 스레드(콜백 바깥, 예를 들어 `main()` 함수)에서 딱 한 번 쓸 때만 안전하다는 것을 기억해라.
:::

## 서비스가 안 맞는 경우: 액션으로

서비스는 "빨리 끝나는 질문"에 맞는 도구다. 그런데 다음 같은 요청은 서비스로 억지로 밀어 넣으면 문제가 생긴다.

- **오래 걸린다.** 경로 계획, 지도 저장, 팔 이동은 몇 초에서 몇 분까지 걸릴 수 있다. 그동안 클라이언트는 `call_async()` 의 Future 하나만 들고 응답을 기다려야 하는데, **진행 상황을 알 방법이 없다.**
- **중간에 취소하고 싶다.** 서비스는 "요청 보냈다 → 응답 왔다"만 있다. 도중에 "그만해"를 보낼 창구가 없다.
- **진행률을 스트리밍하고 싶다.** "지금 40% 이동했다"를 실시간으로 알려주는 건 서비스의 1:1 요청-응답 모델로는 표현할 수 없다.

이 세 가지가 필요한 순간이 바로 **액션**이 서비스를 대체하는 지점이다. 액션은 서비스(목표 설정, 결과 받기)와 토픽(진행률 스트리밍)을 조합하고, 취소 프로토콜까지 표준화한 상위 패턴이다. 자세한 건 다음 절 [10.6 액션](#/actions)에서 다룬다.

::: tip 판단 기준 한 줄
"이 요청, 콜백 안에서 몇 밀리초~몇 초 안에 끝나는가?"가 예/아니오로 갈리면 서비스와 액션의 선택도 갈린다. 확신이 안 서면 **타임아웃을 넉넉히 걸어 두고 서비스로 시작**하되, 실제 운영 중 응답 지연이 문제가 되면 그때 액션으로 옮기는 게 현실적인 경로다.
:::

## 요약

- 서비스는 **1:1 요청-응답**이다. 토픽의 1:N 발행-구독과 반대되는 통신 패턴이다.
- `.srv` 파일은 `---` 로 요청과 응답 필드를 나눈다. 생성된 `Request`/`Response` 는 평범한 가변 파이썬 객체다.
- 서버는 `create_service(타입, 이름, 콜백)`, 콜백은 `(request, response) -> response` 시그니처를 따른다.
- 클라이언트는 `call_async()` 로 즉시 `Future` 를 받는 것이 기본이다. `spin_until_future_complete` 는 메인 스레드에서만 안전하다.
- **콜백 안에서 동기 `call()` 을 쓰면 대부분 데드락이 난다.** 같은 콜백 그룹이 실행 슬롯 하나를 두고 자기 자신을 기다리기 때문이다.
- 해결책은 `call_async()` 를 항상 쓰거나, 콜백 그룹을 분리하거나, `ReentrantCallbackGroup` 을 쓰는 것이다.
- 오래 걸리고, 취소가 필요하고, 진행률을 알려야 하는 작업은 서비스가 아니라 액션으로 만든다.

::: quiz 연습문제
1. 서비스와 토픽의 차이를 "1:N vs 1:1", "응답 유무" 두 축으로 표로 정리하라.
2. `AddTwoInts.srv` 를 참고해서, 문자열 하나를 받아 그 길이를 반환하는 `.srv` 파일을 직접 작성하라.
3. 다음 코드가 왜 위험한지, 어떤 상황에서 실제로 멈추는지 설명하라.

   ```python
   def odom_callback(self, msg):
       req = SetBool.Request()
       req.data = True
       response = self.safety_client.call(req)  # ❌
   ```

4. 위 3번 코드를 두 가지 다른 방법으로 고쳐라. 하나는 `call_async()` + `add_done_callback`, 다른 하나는 콜백 그룹 분리를 쓴다.
5. 배터리 잔량을 1초마다 확인하는 기능과, 로봇 팔을 특정 좌표로 옮기는 기능이 있다. 각각 토픽·서비스·액션 중 어느 것으로 설계할지 근거와 함께 답하라.
:::

**다음 절**: [10.6 액션](#/actions) — 서비스로는 안 되는 장시간 작업, 어떻게 진행률을 스트리밍하고 중간에 취소하는가.
