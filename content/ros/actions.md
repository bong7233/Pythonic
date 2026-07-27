# 10.6 액션

::: lead
[10.5 서비스](#/services)는 "질문 하나, 답 하나"였다. 로봇에게 "지금 배터리 몇 퍼센트야?"라고 묻는 데는 그걸로 충분하다. 하지만 "저기 있는 문 앞까지 가"라고 시키면 얘기가 달라진다. 그 일은 몇 초가 아니라 몇 분이 걸리고, 그동안 로봇이 어디쯤 왔는지 알고 싶고, 사람이 갑자기 앞을 가로막으면 멈춰야 한다. 서비스도 토픽도 혼자서는 이 요구를 만족시키지 못한다. **액션은 이 셋 — 시작·진행·취소 — 을 위해 서비스와 토픽을 조합해 만든 세 번째 통신 패턴**이다. 그리고 이 절 끝에서 보겠지만, [Nav2](#/nav2)와 [MoveIt 2](#/moveit)가 로봇을 움직이는 모든 요청은 결국 액션이다.
:::

## 서비스로는 안 되는 이유 — 문제부터

[10.5 서비스](#/services)에서 배운 대로 서비스 호출을 그대로 "로봇을 목표 지점까지 이동시켜라"에 써 본다고 하자.

```python
# 이런 서비스가 있다고 가정하자 — 실제로는 이렇게 안 만든다
response = navigate_client.call(NavigateToPose.Request(pose=goal_pose))
print(response.result)
```

이 한 줄에는 세 가지 구멍이 있다.

1. **블로킹.** 로봇이 목적지까지 가는 데 2분이 걸린다면, 동기 호출은 2분간 멈춰 있다. [10.5절의 `call()` 경고](#/services)를 그대로 다시 만난다 — 싱글 스레드 executor에서 이 안에 spin이 필요한 콜백이 있으면 그대로 교착 상태다.
2. **피드백이 없다.** 응답은 끝났을 때 딱 한 번 온다. "지금 몇 미터 남았어?"를 서비스로 물으려면 별도의 폴링용 서비스나 토픽을 직접 만들어야 하고, 그 둘을 하나의 "목표"로 묶어 관리하는 책임은 통째로 당신 몫이다.
3. **취소할 수 없다.** 서비스는 요청을 보내고 응답을 받는 것 말고 다른 상호작용이 없다. 사람이 로봇 앞을 가로막았다고 "방금 그 요청 취소해"라고 말할 창구가 애초에 없다.

액션은 이 세 가지 구멍을 표준화된 방식으로 메운다. 그리고 표준화됐다는 것 자체가 중요하다 — Nav2, MoveIt 2, 당신이 만드는 커스텀 태스크 매니저가 전부 **같은 프로토콜**로 "장시간 작업"을 표현하게 되고, 그래서 `ros2 action` 이라는 하나의 CLI로 전부 다룰 수 있다.

## 액션의 정체: 서비스 셋 + 토픽 둘

액션은 새로운 통신 계층이 아니다. **서비스 3개와 토픽 2개를 정해진 방식으로 조합한 관례**다. 이건 [10.5 서비스](#/services)와 [10.4 토픽](#/topics)을 이미 알고 있다면 새로 배울 게 거의 없다는 뜻이기도 하다.

```text nolines
   action client                                action server

   │ ── send_goal    (service) ───────────────▶ │    목표 제출, 수락/거부 응답
   │ ◀── feedback    (topic, repeated) ───────  │    실행 중 진행 상황 계속 발행
   │ ── cancel_goal  (service) ───────────────▶ │    진행 중인 목표의 취소 요청
   │ ── get_result   (service) ───────────────▶ │    완료 후 최종 결과 요청
   │ ◀── status      (topic, broadcast) ──────  │    모든 목표의 상태를 공지
```

| 이름 | 종류 | 방향 | 역할 |
| --- | --- | --- | --- |
| Send Goal | 서비스 | 클라이언트 → 서버 | 목표를 제출하고 수락/거부 응답을 받는다 |
| Cancel Goal | 서비스 | 클라이언트 → 서버 | 진행 중인 목표의 취소를 요청한다 |
| Get Result | 서비스 | 클라이언트 → 서버 | 완료된 목표의 최종 결과를 받는다 (완료 전엔 응답이 보류된다) |
| Feedback | 토픽 | 서버 → 클라이언트 | 실행 중 진행 상황을 계속 발행한다 |
| Status | 토픽 | 서버 → 모든 클라이언트 | 이 서버가 관리하는 모든 목표의 상태를 broadcast한다 |

::: hist 왜 서비스 하나로 안 만들고 다섯 개나 썼나
서비스는 "요청 하나에 응답 하나"라는 계약이 코드에 박혀 있다 — [10.5절](#/services)에서 본 `Trigger.srv` 처럼 `---` 위아래로 딱 두 블록뿐이다. 여기에 "진행 중 여러 번 오는 메시지"나 "다른 클라이언트도 볼 수 있는 상태 broadcast"를 욱여넣으려면 서비스의 의미 자체를 깨야 한다.

ROS 2 설계팀은 대신 **이미 검증된 두 프리미티브(서비스, 토픽)를 합성**하는 쪽을 택했다. 새 전송 계층을 만들지 않았으므로 [10.8 QoS](#/qos)의 신뢰성·역사 정책이 액션의 각 서비스·토픽에도 그대로 적용되고, DDS 디버깅 도구로 액션 트래픽도 그대로 들여다볼 수 있다. "새 프로토콜을 발명하는 대신 기존 것을 조합한다"는 이 판단은 이 책 전체에서 반복해서 본 패턴이다 — [1.18 제너레이터](#/iterators)가 새 문법 없이 이터레이터 프로토콜의 합성으로 코루틴 흉내를 낸 것과 같은 결의 선택이다.
:::

::: note 목표 하나마다 UUID가 붙는다
액션 서버는 **동시에 여러 목표**를 받을 수 있다(정책은 서버가 정한다). 그래서 Send Goal 서비스가 목표를 수락하면 그 목표를 가리키는 **UUID(goal_id)** 를 함께 돌려준다. 이후의 취소·피드백·결과 요청은 전부 이 UUID로 "어느 목표를 말하는지" 구분한다. 여러 목표를 큐에 쌓아 순차 처리할지, 새 목표가 오면 이전 걸 취소할지, 거부할지는 전적으로 서버 구현이 정한다 — rclpy 기본값은 **동시에 여러 목표를 그냥 다 받아 병렬 실행**한다.
:::

## 액션 정의: `.action` 파일

메시지가 `.msg`, 서비스가 `.srv`였다면 액션은 `.action`이다. `---`로 구분된 **세 블록**을 가진다.

```text title="Fibonacci.action — example_interfaces 패키지"
# Goal
int32 order
---
# Result
int32[] sequence
---
# Feedback
int32[] sequence
```

`.srv`와 비교하면 블록이 하나 늘었을 뿐이다. 첫 블록이 목표(클라이언트가 보내는 것), 둘째가 결과(끝났을 때 한 번 오는 것), 셋째가 피드백(실행 중 계속 오는 것)이다. 빌드 시스템(`rosidl_generate_interfaces`, [10.2 워크스페이스](#/ros-workspace))이 이 파일 하나로부터 `Fibonacci.Goal`, `Fibonacci.Result`, `Fibonacci.Feedback` 세 개의 메시지 타입과, 이들을 엮는 액션 타입 `Fibonacci`를 자동으로 생성한다.

::: cote 여기서도 재귀적 정의가 나온다
`Fibonacci.action`의 목표는 그냥 정수 하나(`order`)지만, 실행 로직은 여러분이 [7.20 DP 기초](#/dp-basics)에서 본 피보나치 점화식 그 자체다 — 다만 이번엔 각 항을 계산할 때마다 그 중간값을 **피드백으로 흘려보낸다.** "장시간 계산을 하면서 중간 결과를 계속 알린다"는 액션의 본질을 보여주기 위해 ROS 2 공식 튜토리얼이 골라 쓰는 예제가 바로 이 피보나치 액션이다.
:::

## 액션 서버 작성

아래 코드는 ROS 2 공식 튜토리얼(`ros2/demos` 저장소의 `fibonacci_action_server.py`, rolling 브랜치 기준)의 핵심 구조를 그대로 따른다. 이 절에서는 원본에 있는 파라미터 introspection 관련 코드는 액션의 본질과 무관해 생략했다 — 실제로 rosidl 인트로스펙션까지 쓰려면 원본 소스를 참고하라.

```python title="fibonacci_action_server.py"
import time

from example_interfaces.action import Fibonacci
import rclpy
from rclpy.action import ActionServer, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


class FibonacciActionServer(Node):
    def __init__(self):
        super().__init__('fibonacci_action_server')
        self._action_server = ActionServer(
            self,
            Fibonacci,
            'fibonacci',
            execute_callback=self.execute_callback,
            cancel_callback=self.cancel_callback,
        )

    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')

        feedback_msg = Fibonacci.Feedback()
        feedback_msg.sequence = [0, 1]

        for i in range(1, goal_handle.request.order):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                self.get_logger().info('Goal canceled')
                return Fibonacci.Result()

            feedback_msg.sequence.append(
                feedback_msg.sequence[i] + feedback_msg.sequence[i - 1])
            goal_handle.publish_feedback(feedback_msg)
            time.sleep(1)   # 실제로는 모터 제어, 경로 추종 같은 진짜 작업

        goal_handle.succeed()

        result = Fibonacci.Result()
        result.sequence = feedback_msg.sequence
        return result

    def cancel_callback(self, goal_handle):
        self.get_logger().info('Canceling goal...')
        return CancelResponse.ACCEPT


def main(args=None):
    rclpy.init(args=args)
    server = FibonacciActionServer()
    executor = MultiThreadedExecutor()      # 반드시 필요하다 — 아래 참고
    rclpy.spin(server, executor=executor)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

(클래스·메서드 시그니처는 `docs.ros.org` 의 rclpy API 문서(`rclpy.action.server` 모듈, rolling 기준)와 `ros2/demos` GitHub 저장소의 `action_tutorials_py` 패키지 소스로 대조했다. `ActionServer.__init__` 은 `execute_callback`, `goal_callback`, `handle_accepted_callback`, `cancel_callback`, 각종 QoS 프로파일, `result_timeout` 을 키워드 인자로 받는다 — 이 절에서는 필수적인 것만 지정했고 나머지는 rclpy 기본값을 쓴다.)

`ActionServer` 생성자는 세 가지 콜백을 받는다. **`goal_callback`을 생략하면 기본값이 모든 목표를 무조건 수락**하고(`GoalResponse.ACCEPT`), **`cancel_callback`을 생략하면 기본값이 모든 취소 요청을 거부**한다. 이 예제는 `cancel_callback`을 직접 구현해서 취소를 받아들이게 만들었지만, `goal_callback`은 생략했으므로 들어오는 목표를 전부 수락한다.

::: warn 목표를 거부하고 싶으면 goal_callback을 직접 써라
```python
from rclpy.action import GoalResponse

def goal_callback(self, goal_request):
    if goal_request.order > 100:
        return GoalResponse.REJECT      # 너무 큰 요청은 애초에 안 받는다
    return GoalResponse.ACCEPT
```

`goal_callback`은 아직 실행되지 않은 목표를 **받을지 말지**만 결정한다. 이미 실행 중인 목표를 멈추는 것은 `cancel_callback`과 `execute_callback` 안의 `is_cancel_requested` 검사가 하는 일이다. 이 둘을 혼동해서 "취소가 안 먹힌다"는 버그를 만드는 경우가 흔하다.
:::

::: danger execute_callback은 취소를 스스로 확인해야 한다
`cancel_callback`이 `CancelResponse.ACCEPT`를 반환한다고 해서 실행 중인 `execute_callback`이 저절로 멈추지 않는다. **취소는 요청일 뿐이고, 실제로 멈추는 것은 실행 중인 코드 자신의 책임이다.** 그래서 위 예제가 반복문 안에서 매번 `goal_handle.is_cancel_requested` 를 확인하는 것이다.

만약 `execute_callback` 안에 이 검사 없이 `time.sleep(60)` 같은 긴 블로킹 호출이 있다면, 클라이언트가 취소를 요청해도 그 60초가 끝날 때까지 아무 일도 일어나지 않는다. **긴 작업은 반드시 잘게 쪼개서 취소 확인 지점을 자주 두거나, 실행 중인 하위 작업(모터 명령 등) 자체에 타임아웃과 중단 신호를 심어야 한다.** 이건 [4.7 asyncio 취소](#/asyncio-advanced)에서 본 "취소는 협조적이다"라는 원칙과 정확히 같은 이야기다 — asyncio의 `Task.cancel()`도, rclpy 액션의 취소도, 실행 중인 코드가 스스로 확인하지 않으면 아무 효과가 없다.
:::

`goal_handle`은 매 콜백에 전달되는 `ServerGoalHandle` 인스턴스다. 실전에서 자주 쓰는 메서드·속성은 이렇다.

| 멤버 | 의미 |
| --- | --- |
| `.request` | 클라이언트가 보낸 목표 메시지 (`Fibonacci.Goal`) |
| `.is_cancel_requested` | 취소가 요청됐는지 (상태가 `CANCELING`인지) |
| `.publish_feedback(msg)` | 피드백 토픽에 발행한다 |
| `.succeed(response=None)` | 상태를 `SUCCEEDED`로 바꾼다 |
| `.abort(response=None)` | 상태를 `ABORTED`로 바꾼다 (서버가 실패를 인정) |
| `.canceled(response=None)` | 상태를 `CANCELED`로 바꾼다 |
| `.status` | 현재 상태 (`GoalStatus` 값) |

::: danger 목표는 반드시 종결 상태로 끝나야 한다
`execute_callback`이 `succeed()`/`abort()`/`canceled()` 중 아무것도 호출하지 않고 그냥 `return`하면, 그 목표는 **`EXECUTING` 상태에 영원히 멈춘다.** 클라이언트는 결과를 영원히 못 받고, `ros2 action list -t`로 봐도 서버가 왜 응답이 없는지 알 수 없다. 예외가 나서 콜백이 죽는 경로도 마찬가지다 — 그래서 `execute_callback`은 `try/except`로 감싸고 예외 상황에서도 `goal_handle.abort()`를 호출하는 습관을 들여야 한다.
:::

## 액션 클라이언트 작성

```python title="fibonacci_action_client.py"
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from example_interfaces.action import Fibonacci


class FibonacciActionClient(Node):
    def __init__(self):
        super().__init__('fibonacci_action_client')
        self._client = ActionClient(self, Fibonacci, 'fibonacci')

    def send_goal(self, order):
        goal_msg = Fibonacci.Goal()
        goal_msg.order = order

        self._client.wait_for_server()

        future = self._client.send_goal_async(
            goal_msg, feedback_callback=self.feedback_callback)
        future.add_done_callback(self.goal_response_callback)

    def feedback_callback(self, feedback_msg):
        self.get_logger().info(f'피드백: {feedback_msg.feedback.sequence}')

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('목표가 거부됐다')
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f'결과: {result.sequence}')
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    client = FibonacciActionClient()
    client.send_goal(10)
    rclpy.spin(client)
```

(위 구조는 `ros2/demos` 저장소의 `fibonacci_action_client.py`(rolling 브랜치)와 rclpy 공식 API 문서로 대조했다. `send_goal_async` 는 `Future`를 반환하고 그 결과가 `ClientGoalHandle`이다 — `goal_handle.accepted` 로 수락 여부를, `get_result_async()` 로 다시 `Future`를 받아 최종 결과를 얻는다. 이 이중 `Future` 구조가 핵심이다: 하나는 "목표가 수락됐는가", 다른 하나는 "실행이 끝났는가"에 대한 것이다.)

::: deep 콜백 체인이 낯설다면 — 이건 4.7절의 콜백 지옥과 같은 모양이다
`send_goal_async` → `add_done_callback` → 그 안에서 `get_result_async` → 다시 `add_done_callback`. 이 중첩은 [4.6 asyncio 기초](#/asyncio-basics)에서 `await`가 감춰 주는 바로 그 콜백 체인이다. rclpy도 내부적으로는 `Future`를 쓰지만(`rclpy.task.Future`), asyncio의 이벤트 루프와 통합돼 있지 않으므로 `await`를 못 쓰고 `add_done_callback`을 직접 쌓아야 한다. 콜백이 두 단계만 돼도 이렇게 읽기 번거로운데, 이게 `asyncio`가 왜 만들어졌는지에 대한 가장 직접적인 답이다.

일부 프로젝트는 `rclpy`의 콜백 스타일 위에 `async`/`await`를 얹는 래퍼를 직접 짜기도 한다(`send_goal_async`의 `Future`를 `asyncio.Future`로 감싸는 식). 표준은 아니지만 액션 클라이언트 코드가 복잡해질수록 실전에서 자주 보게 되는 패턴이다.
:::

## 실행기와 콜백 그룹 — 왜 MultiThreadedExecutor가 필요한가

[10.3 rclpy 노드](#/rclpy-node)에서 본 싱글 스레드 executor를 액션 서버에 그대로 쓰면 함정에 빠진다. `execute_callback`이 `time.sleep(1)`을 포함해 몇 초씩 걸리는 동안, **같은 스레드에서 처리돼야 할 `cancel_callback`도 멈춰 있다.** 취소 요청이 와도 실행 중인 콜백이 끝날 때까지 처리되지 않는다 — 취소라는 기능 자체가 무의미해진다.

```text nolines
싱글 스레드 executor의 콜백 처리 순서

  execute_callback ─────────────────────────▶   (1초 sleep 동안 스레드를 점유)
                              │
                              ▼
  cancel_callback 대기                          (같은 스레드라 끼어들 수 없다)
```

그래서 위 서버 예제는 `MultiThreadedExecutor`를 쓴다. `execute_callback`과 `cancel_callback`이 **서로 다른 스레드**에서 동시에 돌 수 있어야, 실행 중인 목표에 대해 취소 요청이 제때 처리된다. 이건 [4.2 threading](#/threading)에서 배운 것 그대로다 — 콜백 두 개가 같은 상태(`goal_handle`)를 동시에 건드리므로, `ServerGoalHandle` 내부는 이미 락으로 보호돼 있지만 **당신이 콜백 안에서 직접 만지는 공유 상태**(예: 서버 클래스의 인스턴스 변수)는 당신이 직접 보호해야 한다. [4.3 GIL](#/gil)이 "동시에 실행되는 두 스레드도 파이썬 바이트코드 단위 원자성은 보장하지만 여러 줄에 걸친 연산은 아니다"라고 한 것과 정확히 같은 문제다.

::: perf 콜백 그룹으로 더 세밀하게 제어한다
`MultiThreadedExecutor`를 쓰되 노드 전체가 무제한으로 병렬 실행되길 원하지 않는다면 [10.3절](#/rclpy-node)의 콜백 그룹(`ReentrantCallbackGroup`, `MutuallyExclusiveCallbackGroup`)을 액션별로 지정한다. 예를 들어 액션 서버의 콜백들은 `ReentrantCallbackGroup`에 두고 다른 안전-critical 토픽 콜백은 별도의 `MutuallyExclusiveCallbackGroup`에 둬서, 액션이 다른 실시간성 요구가 있는 콜백을 방해하지 않게 격리할 수 있다.
:::

## CLI로 액션 들여다보기

디버깅할 때는 클라이언트 코드를 짜지 않고 `ros2 action` 서브커맨드로 먼저 찔러 본다.

```bash
ros2 action list -t
```

```text nolines
/fibonacci [example_interfaces/action/Fibonacci]
```

```bash
ros2 action info /fibonacci
```

```text nolines
Action: /fibonacci
Action clients: 0
Action servers: 1
    /fibonacci_action_server
```

목표를 직접 보내고 `--feedback`으로 진행 상황까지 볼 수 있다.

```bash
ros2 action send_goal /fibonacci example_interfaces/action/Fibonacci "{order: 5}" --feedback
```

```text nolines
Waiting for an action server to become available...
Sending goal:
     order: 5

Goal accepted with ID: 8f3a1c2e...

Feedback:
    sequence: [0, 1, 1]

Feedback:
    sequence: [0, 1, 1, 2]

Feedback:
    sequence: [0, 1, 1, 2, 3]

Result:
    sequence: [0, 1, 1, 2, 3]

Goal finished with status: SUCCEEDED
```

(위 형식은 `ros2/ros2_documentation` 공식 튜토리얼 "Understanding actions"에서 확인된 실제 출력 형태를 따른 예시다. 실제 시퀀스 값과 goal ID는 실행마다 다르다.)

::: tip Ctrl+C로 취소가 된다
`ros2 action send_goal`이 피드백을 기다리는 동안 <kbd>Ctrl</kbd>+C를 누르면, 그 목표에 대해 자동으로 취소 요청을 보낸다. 코드 한 줄 없이 "취소가 실제로 동작하는지"를 즉석에서 확인할 수 있는 가장 빠른 방법이다.
:::

## 순수 파이썬으로 취소 프로토콜 검증하기

rclpy는 이 샌드박스에 설치할 수 없지만, `execute_callback`이 별도 스레드에서 돌면서 `is_cancel_requested`를 폴링하는 구조 자체는 표준 라이브러리 `threading`만으로 그대로 재현할 수 있다. 아래 코드는 실제로 실행해서 확인한 결과다.

```python title="action_sim.py — 실제로 실행해서 검증"
import enum
import threading
import time


class GoalStatus(enum.IntEnum):
    """정수값은 실제 action_msgs/msg/GoalStatus.msg와 동일하게 맞춘다.
    (STATUS_UNKNOWN=0은 이 시뮬레이션에서 쓰지 않아 생략)"""
    ACCEPTED, EXECUTING, CANCELING, SUCCEEDED, CANCELED, ABORTED = range(1, 7)


class FakeGoalHandle:
    """rclpy.action.server.ServerGoalHandle의 핵심 동작만 축소 재현."""

    def __init__(self):
        self.status = GoalStatus.ACCEPTED
        self._cancel_event = threading.Event()

    @property
    def is_cancel_requested(self):
        return self._cancel_event.is_set()

    def request_cancel(self):
        self.status = GoalStatus.CANCELING
        self._cancel_event.set()

    def publish_feedback(self, value):
        print(f"  [feedback] {value}")

    def succeed(self):
        self.status = GoalStatus.SUCCEEDED

    def canceled(self):
        self.status = GoalStatus.CANCELED


def execute_callback(goal_handle, order):
    sequence = [0, 1]
    for i in range(1, order):
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            return sequence
        sequence.append(sequence[i] + sequence[i - 1])
        goal_handle.publish_feedback(list(sequence))
        time.sleep(0.05)
    goal_handle.succeed()
    return sequence


def run_case(order, cancel_after):
    goal_handle = FakeGoalHandle()
    result = {}
    t = threading.Thread(target=lambda: result.update(
        seq=execute_callback(goal_handle, order)))
    t.start()
    if cancel_after is not None:
        time.sleep(cancel_after)
        goal_handle.request_cancel()
    t.join()
    return goal_handle.status, result["seq"]


status1, seq1 = run_case(order=6, cancel_after=None)
assert status1 == GoalStatus.SUCCEEDED

status2, seq2 = run_case(order=10, cancel_after=0.12)
assert status2 == GoalStatus.CANCELED
print(status1.name, seq1)
print(status2.name, seq2)
```

```text nolines
SUCCEEDED [0, 1, 1, 2, 3, 5, 8]
CANCELED [0, 1, 1, 2, 3]
```

(Python 3.14.5 기준 실제 실행 결과. 취소 시점은 `time.sleep`에 의존하므로 실행할 때마다 정확한 마지막 피드백 개수는 조금 달라질 수 있지만, "취소 전까지의 결과가 남고 이후는 중단된다"는 구조는 항상 같다.)

위 `GoalStatus`의 정수값(`ACCEPTED=1, EXECUTING=2, CANCELING=3, SUCCEEDED=4, CANCELED=5, ABORTED=6`)은 실제 `action_msgs/msg/GoalStatus.msg`(ros2/rcl_interfaces, rolling 기준: `STATUS_UNKNOWN=0`부터 `STATUS_ABORTED=6`까지)와 동일하게 맞췄다 — `STATUS_UNKNOWN=0`만 이 시뮬레이션엔 없다.

이 축소판이 실제 rclpy와 다른 점은, 진짜 `ServerGoalHandle`은 상태 전이를 락으로 보호하고 DDS로 status 토픽을 broadcast한다는 것이다. 하지만 **"콜백이 별도 스레드에서 돌고, 취소는 플래그를 세우는 것뿐이며, 실행 중인 코드가 그 플래그를 스스로 확인해야 멈춘다"는 핵심 로직**과 상태값 정수 자체는 정확히 이거다. 액션의 취소 메커니즘을 글로만 읽어서는 "그냥 멈추겠지"라고 오해하기 쉬운데, 이렇게 직접 스레드 두 개를 굴려서 타이밍을 관찰하면 왜 폴링 지점을 촘촘히 둬야 하는지가 체감된다.

## 왜 네비게이션은 액션이어야 하는가

[10.13 Nav2](#/nav2)의 `NavigateToPose`가 서비스가 아니라 액션인 이유를 이제 정확히 답할 수 있다.

- **몇 초에서 몇 분까지 걸린다** — 서비스로 만들면 그 시간 내내 블로킹 호출이거나, 폴링용 보조 인터페이스를 직접 설계해야 한다.
- **진행 상황이 유의미하다** — "지금 몇 미터 남았다", "이 웨이포인트를 통과했다" 같은 피드백이 있어야 상위 태스크(예: 배달 로봇의 작업 스케줄러)가 판단을 내릴 수 있다.
- **취소가 필수다** — 사람이 갑자기 튀어나오거나 더 급한 목표가 생기면 진행 중인 이동을 즉시 멈춰야 한다. 서비스에는 이 창구가 아예 없다.

반대로 "지금 배터리 몇 퍼센트인지 알려줘"처럼 **즉시 끝나고, 진행 상황이랄 게 없고, 취소할 대상도 없는** 요청까지 액션으로 만들면 서비스 3개 + 토픽 2개라는 오버헤드만 남는다. **작업이 얼마나 걸릴지 예측할 수 없고, 그 사이에 진행 상황과 취소가 의미를 가지는가** — 이 두 질문에 둘 다 "그렇다"일 때만 액션을 쓴다.

## 요약

- 액션은 새 전송 계층이 아니라 **서비스 3개(목표 전송·취소·결과) + 토픽 2개(피드백·상태)의 조합**이다.
- `.action` 파일은 `---`로 구분된 **세 블록**(Goal / Result / Feedback)이다.
- `ActionServer`는 `execute_callback`(필수), `goal_callback`(생략 시 전부 수락), `cancel_callback`(생략 시 전부 거부)을 받는다.
- 목표는 `goal_handle.succeed()`/`abort()`/`canceled()` 중 하나로 반드시 **종결 상태**에 도달해야 한다. 안 그러면 영원히 `EXECUTING`에 멈춘다.
- **취소는 요청일 뿐이다.** `execute_callback`이 `is_cancel_requested`를 스스로 확인하지 않으면 취소는 아무 효과가 없다 — [4.7 asyncio의 협조적 취소](#/asyncio-advanced)와 같은 원칙이다.
- 실행 중인 콜백이 취소 요청 처리를 막지 않으려면 **`MultiThreadedExecutor`가 사실상 필수**다.
- `ros2 action list/info/send_goal --feedback`으로 코드 없이 액션을 검사·호출할 수 있다.
- 작업 시간이 예측 불가능하고, 피드백과 취소가 실제로 의미 있을 때만 액션을 쓴다. Nav2와 MoveIt 2가 액션인 이유가 바로 이거다.

::: quiz 연습문제
1. 서비스 대신 액션을 써야 하는 신호 두 가지를 이 절의 기준으로 설명하라. 그리고 반대로 액션 대신 서비스를 써야 하는 예를 하나 들어라.
2. `ActionServer` 생성 시 `cancel_callback`을 지정하지 않으면 어떤 일이 일어나는가? `goal_callback`을 지정하지 않으면?
3. 다음 `execute_callback`은 왜 취소가 절대 먹히지 않는가? 고쳐라.

   ```python
   def execute_callback(self, goal_handle):
       time.sleep(30)          # 긴 블로킹 작업
       goal_handle.succeed()
       return Result()
   ```

4. 이 절의 `action_sim.py`를 고쳐서, 취소 요청이 온 뒤 실제로 `canceled()`가 호출되기까지 몇 번의 루프가 더 도는지 로그를 찍어 확인하라. 왜 정확히 그 시점에 멈추는지 설명하라.
5. 싱글 스레드 executor에서 액션 서버를 돌리면 어떤 콜백과 어떤 콜백이 서로를 막는가? [4.2 threading](#/threading)의 락과 어떤 점이 비슷하고 어떤 점이 다른가?
:::

**다음 절**: [10.7 파라미터와 launch](#/params-launch) — 지금까지 하드코딩했던 토픽 이름·주기·좌표를 실행 시점에 바꾸는 법, 그리고 노드 여러 개를 한 번에 띄우는 파이썬 launch 파일.
