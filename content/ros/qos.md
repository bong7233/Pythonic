# 10.8 QoS와 DDS

::: lead
[10.4 토픽](#/topics)에서 발행자와 구독자를 만들었다. 코드는 문법 오류 없이 돌아가고, 노드도 정상적으로 뜬다. 그런데 메시지가 한 개도 도착하지 않는다. 에러도, 예외도, 로그 한 줄도 없이 그냥 조용하다. ROS 2를 처음 만지는 사람이 거의 반드시 한 번은 당하는 이 증상의 원인은 대개 하나다 — **QoS(Quality of Service) 설정 불일치.** 이 절은 그 불일치가 왜 생기고, 왜 아무 에러도 안 나는지, 그리고 진단하는 법을 다룬다. 그 전에 이 모든 걸 가능하게 하는 통신 계층 DDS부터 봐야 한다.
:::

## ROS 1과 ROS 2를 가르는 결정

ROS 1에는 `roscore`라는 중앙 서버가 있었다. 모든 노드가 이 서버에 접속해서 "나는 이런 토픽을 발행한다", "나는 이런 토픽을 구독하고 싶다"를 등록했다. `roscore`가 죽으면 시스템 전체가 죽는다. 단일 장애점(single point of failure)이다.

ROS 2는 이 구조를 통째로 버렸다. 대신 **DDS**(Data Distribution Service)라는, 원래 국방·항공·금융 업계에서 쓰던 산업 표준 미들웨어를 통신 기반으로 그대로 가져다 썼다. DDS는 OMG(Object Management Group)가 정의한 명세이고, ROS 2는 그 명세를 구현한 여러 벤더 중 하나를 골라 쓴다 — 기본값은 Fast DDS, 그 외에 Cyclone DDS, RTI Connext 등을 골라 쓸 수 있다.

DDS의 핵심 아이디어는 **중앙 서버 없는 발견**(decentralized discovery)이다. 각 노드는 자신이 발행/구독하는 토픽 정보를 네트워크에 주기적으로 알린다(멀티캐스트). 같은 이름의 토픽에 관심 있는 노드끼리 서로를 찾아서 **직접** 연결을 맺는다. `roscore` 같은 중개자가 없다. 노드 하나가 죽어도 나머지는 서로 계속 대화한다.

```text nolines
ROS 1                              ROS 2

  node_a                             node_a ◀──────┐
     │                                              │
     ▼                                              ▼
  roscore  ◀──── 모든 등록/조회         (DDS 발견 프로토콜로
     ▲            이 서버를 거친다)      서로 직접 찾는다)
     │                                              ▲
  node_b                             node_b ◀──────┘

  roscore 죽음 = 전체 마비           참가자 하나 죽어도 나머지는 무관
```

::: hist 왜 하필 DDS였나
ROS 2를 설계할 때(2014년경) 팀이 원한 것은 실시간성, 보안, 다중 벤더 상호운용성을 이미 검증받은 통신 계층이었다. 이걸 처음부터 새로 만드는 대신, 이미 항공기 시스템과 금융 거래소에서 15년 넘게 실전 검증된 DDS 표준을 채택했다. 대가도 있다 — DDS는 원래 로봇을 위해 설계되지 않았고, 그 개념(QoS, 발견 프로토콜, 직렬화)을 ROS 2 위에 그대로 노출하다 보니 러닝 커브가 늘었다. 이 절에서 배우는 QoS 정책들이 ROS 2 고유 개념이 아니라 **DDS 표준 자체의 개념**인 이유다.
:::

## rmw: DDS 벤더를 감추는 층

ROS 2는 특정 DDS 구현체에 종속되지 않으려고 `rmw`(ROS middleware) 라는 추상화 계층을 하나 더 끼워 넣었다. [10.16 다음 단계](#/ros-next)에서 본 아키텍처를 다시 가져오면 이렇다.

```text nolines
        rclpy / rclcpp        <- 당신이 짜는 코드
              │
              ▼
             rcl               <- 언어 중립 공통 코어
              │
              ▼
             rmw               <- DDS 벤더를 감추는 추상 인터페이스
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
Fast DDS  Cyclone DDS  RTI Connext   <- 실제 DDS 구현체
```

`RMW_IMPLEMENTATION` 환경 변수 하나로 밑에 깔린 DDS 벤더를 통째로 바꿀 수 있다. 이게 가능한 이유는 당신의 `create_publisher` 호출이 `rmw`가 정의한 공통 인터페이스만 거치기 때문이다. 그런데 이 추상화가 완전하지는 않다. **QoS 정책은 DDS 표준의 개념을 그대로 노출**하고 있어서, `rmw` 층을 넘어가도 사라지지 않는다. 오히려 여기서부터가 이 절의 본론이다.

## QoS란 무엇을 결정하는가

토픽으로 메시지를 주고받을 때 당신이 실제로 결정해야 하는 것들이 있다. "메시지가 유실돼도 되는가?", "새로 구독을 시작한 노드가 과거 메시지를 받아야 하는가?", "큐가 넘치면 오래된 걸 버릴 것인가, 아예 안 받을 것인가?" 이런 질문에 대한 답의 묶음이 **QoS 프로파일**이다.

중요한 건 이 답이 **발행자와 구독자 양쪽에 각각 따로** 설정된다는 점이다. 그리고 둘이 서로 호환되지 않으면 — **연결 자체가 성립하지 않는다.** 에러가 나는 게 아니라, 그냥 아무 일도 안 일어난다. 이게 이 절 전체를 관통하는 핵심 사실이다.

### Reliability — 유실을 허용할 것인가

| 값 | 의미 |
| --- | --- |
| `RELIABLE` | 메시지가 도착했는지 확인(ACK)하고, 유실되면 재전송한다. 순서와 도착을 보장한다 |
| `BEST_EFFORT` | 보내고 끝. 확인도, 재전송도 없다. 네트워크가 나쁘면 조용히 사라진다 |

```python title="rclpy.qos — Reliability 열거형"
from rclpy.qos import QoSReliabilityPolicy

QoSReliabilityPolicy.RELIABLE       # 확인 응답 + 재전송
QoSReliabilityPolicy.BEST_EFFORT    # 확인 없음, 유실 허용
```

`RELIABLE`이 항상 더 좋아 보이지만 공짜가 아니다. 확인 응답을 주고받고 필요하면 재전송하는 데 시간이 걸린다. **최신 데이터가 계속 밀려오는 상황에서는 그 지연이 오히려 해롭다** — 뒤에서 센서 데이터를 다룰 때 이 이유를 자세히 본다.

### Durability — 늦게 온 구독자도 과거 데이터를 받는가

| 값 | 의미 |
| --- | --- |
| `VOLATILE` | 과거 메시지는 안 남긴다. 구독을 시작한 **이후** 발행분만 받는다 |
| `TRANSIENT_LOCAL` | 발행자가 마지막 N개(History로 정한 개수)를 들고 있다가, 새 구독자가 붙으면 즉시 넘겨준다 |

```python title="rclpy.qos — Durability 열거형"
from rclpy.qos import QoSDurabilityPolicy

QoSDurabilityPolicy.VOLATILE          # 지나간 건 안 남는다 (기본값)
QoSDurabilityPolicy.TRANSIENT_LOCAL   # "마지막 상태"를 새 구독자에게도 전달
```

이게 왜 필요한지는 지도(map) 토픽을 생각하면 바로 이해된다. 지도는 SLAM 노드가 시작할 때 한 번 발행하고 그 뒤로는 잘 안 바뀐다. 만약 RViz를 지도 발행 **이후**에 켰다면, `VOLATILE`로는 영원히 지도를 못 본다 — 발행자는 이미 그 메시지를 보냈고 잊어버렸다. `TRANSIENT_LOCAL`은 발행자가 마지막 메시지를 붙잡고 있다가, 늦게 붙은 구독자에게도 넘겨준다. `nav_msgs/OccupancyGrid` 지도 토픽이 관행적으로 `TRANSIENT_LOCAL`을 쓰는 이유다.

::: note TRANSIENT_LOCAL은 진짜 영속 저장소가 아니다
발행자 프로세스가 살아 있는 동안만 유효하다. 발행자가 죽었다 다시 뜨면 히스토리는 사라진다. 진짜로 디스크에 남기고 재생하려면 [10.15 rosbag](#/ros-debug)을 쓴다.
:::

### History와 Depth — 큐를 얼마나, 어떻게 채우는가

| 값 | 의미 |
| --- | --- |
| `KEEP_LAST(depth=N)` | 최근 N개만 큐에 유지. 넘치면 **오래된 것부터 버린다** |
| `KEEP_ALL` | 모두 유지 (DDS 리소스 한도 안에서) |

`KEEP_LAST`는 정확히 `collections.deque(maxlen=N)`과 같은 동작이다. 직접 확인해 보자.

```python title="history_depth.py"
from collections import deque

depth = 3
queue = deque(maxlen=depth)

for i in range(1, 8):
    queue.append(f"msg-{i}")
    print(f"발행 msg-{i} 이후 큐 상태: {list(queue)}")
```

```text nolines
발행 msg-1 이후 큐 상태: ['msg-1']
발행 msg-2 이후 큐 상태: ['msg-1', 'msg-2']
발행 msg-3 이후 큐 상태: ['msg-1', 'msg-2', 'msg-3']
발행 msg-4 이후 큐 상태: ['msg-2', 'msg-3', 'msg-4']
발행 msg-5 이후 큐 상태: ['msg-3', 'msg-4', 'msg-5']
발행 msg-6 이후 큐 상태: ['msg-4', 'msg-5', 'msg-6']
발행 msg-7 이후 큐 상태: ['msg-5', 'msg-6', 'msg-7']
```

(Python 3.14.5 기준 실행 결과. `deque(maxlen=N)`의 동작 자체가 `KEEP_LAST(depth=N)`이 큐 레벨에서 뜻하는 바를 그대로 보여준다 — DDS 내부 구현이 정확히 이 자료구조를 쓴다는 뜻은 아니고, 동작 의미가 같다는 뜻이다.)

`depth`를 너무 낮게 잡으면 구독자 콜백이 느려서 밀리는 순간 최신 메시지가 다 밀려 나간다. 너무 높게 잡으면 밀린 오래된 메시지를 뒤늦게 처리하느라 오히려 지연이 쌓인다. 제어 루프처럼 "낡은 값을 처리하느니 최신 값만 원한다"면 `depth=1`이 정답인 경우가 많다.

## 프리셋 프로파일 — 매번 다 고를 필요는 없다

정책이 여러 개라 매번 다 지정하는 건 번거롭다. `rclpy`는 자주 쓰는 조합을 미리 만들어 뒀다.

```python title="rclpy.qos — 자주 쓰는 프리셋"
from rclpy.qos import QoSPresetProfiles

QoSPresetProfiles.SYSTEM_DEFAULT.value    # 미들웨어에 위임 — 값을 정하지 않고 DDS 벤더 기본값을 따른다
QoSPresetProfiles.SENSOR_DATA.value       # 센서용 — Best Effort, Volatile, depth 5
QoSPresetProfiles.SERVICES_DEFAULT.value  # 서비스용 — Reliable, Volatile, depth 10
```

여기서 `SYSTEM_DEFAULT`를 "Reliable, Volatile, depth 10"이라고 오해하기 쉬운데 틀렸다. `rclpy/qos.py`(`ros2/rclpy` 저장소, rolling 기준)를 보면 `QoSPresetProfiles.SYSTEM_DEFAULT`는 `rmw_qos_profile_system_default`를 감싼 것이고, 이 프로파일은 history/depth/reliability/durability 네 필드가 전부 `RMW_QOS_POLICY_*_SYSTEM_DEFAULT`라는 "값을 정하지 않았음"을 뜻하는 상수로 채워져 있다 — 즉 구체적인 정책값이 아니라 "DDS 벤더의 기본 설정에 그대로 맡긴다"는 신호다. 반면 "Reliable, Volatile, depth 10"이라는 구체적인 값은 별개의 `rmw_qos_profile_default`에 해당하며, 이건 `QoSProfile()`을 인자 없이 만들 때 적용되는 기본값이지 `QoSPresetProfiles.SYSTEM_DEFAULT`가 반환하는 값이 아니다. 이 둘을 헷갈리지 않는 게 중요하다.

기본 프로파일(`rmw_qos_profile_default`)과 센서 데이터 프로파일(`rmw_qos_profile_sensor_data`)의 실제 값은 `rmw`가 정의한 아래 표를 따른다 (`ros2/rmw` 저장소의 `rmw/include/rmw/qos_profiles.h` 기준).

| 정책 | 기본(default) | 센서 데이터(sensor_data) | 시스템 기본(system_default) |
| --- | --- | --- | --- |
| History | KEEP_LAST | KEEP_LAST | SYSTEM_DEFAULT (미들웨어 위임) |
| Depth | 10 | 5 | SYSTEM_DEFAULT (미들웨어 위임) |
| Reliability | RELIABLE | BEST_EFFORT | SYSTEM_DEFAULT (미들웨어 위임) |
| Durability | VOLATILE | VOLATILE | SYSTEM_DEFAULT (미들웨어 위임) |

직접 프로파일을 만들 때는 이렇게 쓴다.

```python title="qos_publisher.py — 발행자에 QoS 지정 (문법은 예시, rclpy.qos 공식 API와 대조함)"
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import LaserScan


class ScanPublisher(Node):
    def __init__(self):
        super().__init__("scan_publisher")
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self.publisher_ = self.create_publisher(LaserScan, "scan", qos)
```

`create_publisher`의 세 번째 인자로 정수를 주면(`self.create_publisher(LaserScan, "scan", 10)`) 그건 `QoSProfile(depth=10)`의 축약형이다 — depth만 지정하고 나머지는 기본값을 쓴다는 뜻이다. [10.4 토픽](#/topics)에서 이미 써 본 그 코드가 사실은 QoS를 암묵적으로 지정하고 있었던 것이다.

## 왜 통신이 안 되는가 — 호환성 규칙

여기가 이 절의 핵심이다. 발행자와 구독자가 정한 QoS는 **DDS의 요청/제공(Request vs Offered) 모델**로 비교된다. 구독자는 "나는 최소 이 정도 수준을 요구한다"고 하고, 발행자는 "나는 이 정도 수준을 제공한다"고 한다. **발행자가 제공하는 수준이 구독자가 요구하는 수준보다 낮으면 연결이 성립하지 않는다.**

Reliability와 Durability는 각각 이런 "강도" 순서를 갖는다.

```text nolines
Reliability:  BEST_EFFORT  <  RELIABLE       (RELIABLE이 더 강한 보장)
Durability:   VOLATILE     <  TRANSIENT_LOCAL (TRANSIENT_LOCAL이 더 강한 보장)
```

규칙은 하나다. **발행자의 수준 ≥ 구독자의 수준일 때만 호환된다.** 이 규칙을 코드로 그대로 옮기면 이렇게 된다 — 순수 파이썬 로직이라 실제로 실행해서 확인할 수 있다.

```python title="qos_check.py — 호환성 규칙을 그대로 코드로"
from enum import IntEnum


class Reliability(IntEnum):
    BEST_EFFORT = 1
    RELIABLE = 2


class Durability(IntEnum):
    VOLATILE = 1
    TRANSIENT_LOCAL = 2


def compatible(offered, requested) -> bool:
    # 발행자(offered)가 구독자(requested)보다 강하거나 같아야 연결된다.
    return requested <= offered


print("발행 RELIABLE, 구독 RELIABLE     ->", compatible(Reliability.RELIABLE, Reliability.RELIABLE))
print("발행 RELIABLE, 구독 BEST_EFFORT  ->", compatible(Reliability.RELIABLE, Reliability.BEST_EFFORT))
print("발행 BEST_EFFORT, 구독 RELIABLE  ->", compatible(Reliability.BEST_EFFORT, Reliability.RELIABLE))
print("발행 BEST_EFFORT, 구독 BEST_EFFORT ->", compatible(Reliability.BEST_EFFORT, Reliability.BEST_EFFORT))
```

```text nolines
발행 RELIABLE, 구독 RELIABLE     -> True
발행 RELIABLE, 구독 BEST_EFFORT  -> True
발행 BEST_EFFORT, 구독 RELIABLE  -> False
발행 BEST_EFFORT, 구독 BEST_EFFORT -> True
```

(Python 3.14.5 기준 실행 결과. `IntEnum` 값 비교 `requested <= offered`가 그대로 DDS의 QoS 호환 규칙이다.)

**"발행 BEST_EFFORT, 구독 RELIABLE" 조합만 `False`다.** 이게 실전에서 가장 흔하게 마주치는 사고 패턴이다. 예를 들어 LiDAR 드라이버가 `BEST_EFFORT`로 `/scan`을 발행하는데, 당신이 만든 노드가 `create_subscription`에 정수(`10`)만 넘겨서 **기본값인 `RELIABLE`** 구독자를 만들었다면, 정확히 이 조합에 걸린다.

Durability도 같은 규칙이다.

```python title="durability도 같은 규칙"
print("발행 TRANSIENT_LOCAL, 구독 TRANSIENT_LOCAL ->",
      compatible(Durability.TRANSIENT_LOCAL, Durability.TRANSIENT_LOCAL))
print("발행 TRANSIENT_LOCAL, 구독 VOLATILE         ->",
      compatible(Durability.TRANSIENT_LOCAL, Durability.VOLATILE))
print("발행 VOLATILE, 구독 TRANSIENT_LOCAL         ->",
      compatible(Durability.VOLATILE, Durability.TRANSIENT_LOCAL))
print("발행 VOLATILE, 구독 VOLATILE                 ->",
      compatible(Durability.VOLATILE, Durability.VOLATILE))
```

```text nolines
발행 TRANSIENT_LOCAL, 구독 TRANSIENT_LOCAL -> True
발행 TRANSIENT_LOCAL, 구독 VOLATILE         -> True
발행 VOLATILE, 구독 TRANSIENT_LOCAL         -> False
발행 VOLATILE, 구독 VOLATILE                 -> True
```

(Python 3.14.5 기준 실행 결과.)

여기서도 딱 한 조합만 막힌다. **발행자가 `VOLATILE`인데 구독자가 `TRANSIENT_LOCAL`을 요구하면** 연결되지 않는다 — 구독자가 "과거 메시지도 달라"고 하는데, 발행자는 애초에 과거 메시지를 들고 있지 않기 때문이다.

::: danger 왜 에러가 안 나는가 — 이게 진짜 함정이다
QoS 불일치는 **컴파일 에러도, 런타임 예외도 아니다.** DDS 발견 프로토콜 단계에서 "이 둘은 짝이 안 맞는다"고 판단하고, 조용히 연결을 만들지 않을 뿐이다. 노드는 정상적으로 뜨고, `ros2 node list`에도 나오고, `ros2 topic list`에도 토픽이 보인다. 다만 `ros2 topic echo`를 해도, 콜백을 등록해도 **아무 메시지도 오지 않는다.**

초심자가 이 증상을 마주치면 자연스럽게 의심하는 곳은 전부 틀렸다: 메시지 타입 오타? 아니다. 토픽 이름 오타? 아니다. 노드가 죽었나? 아니다. 코드에는 아무 문제가 없다 — **QoS가 안 맞을 뿐이다.** 이게 왜 위험한가 하면, 코드 리뷰로도 못 잡고, 단위 테스트로도 못 잡고(모킹하면 QoS가 아예 안 걸린다), 오직 **실제로 두 노드를 같이 띄워 봐야만** 드러나기 때문이다.
:::

## 진단하는 법

증상이 "메시지가 안 온다"로 나타나면, 순서대로 확인한다.

**1. 토픽이 실제로 존재하고 양쪽이 붙어 있는지 확인한다.**

```bash
ros2 topic info /scan --verbose
```

이 명령은 그 토픽에 붙은 모든 발행자·구독자의 QoS 프로파일을 각각 보여준다. 공식 문서와 커뮤니티에 보고된 전형적인 출력 형태는 이렇다 (실제 필드명은 배포판에 따라 약간 다를 수 있다).

```text nolines
Type: sensor_msgs/msg/LaserScan

Publisher count: 1

Node name: lidar_driver
Node namespace: /
Topic type: sensor_msgs/msg/LaserScan
Endpoint type: PUBLISHER
GID: ...
QoS profile:
  Reliability: BEST_EFFORT
  Durability: VOLATILE
  Lifespan: Infinite
  Deadline: Infinite
  Liveliness: AUTOMATIC
  Liveliness lease duration: Infinite

Subscription count: 1

Node name: my_listener
Node namespace: /
Topic type: sensor_msgs/msg/LaserScan
Endpoint type: SUBSCRIPTION
GID: ...
QoS profile:
  Reliability: RELIABLE          <- 발행자는 BEST_EFFORT인데 구독자는 RELIABLE
  Durability: VOLATILE
  ...
```

두 블록의 `Reliability`, `Durability` 줄을 눈으로 대조하는 것만으로 불일치를 바로 찾을 수 있다.

**2. 노드 로그에서 불일치 경고를 찾는다.** ROS 2는 QoS가 안 맞는 상대를 발견하면 경고 로그를 남긴다. 커뮤니티에 실제로 보고된 형태는 이렇다.

```text nolines
New subscription discovered on topic '/scan', requesting incompatible QoS.
No messages will be sent to it.
Last incompatible policy: RELIABILITY_QOS_POLICY
```

`Last incompatible policy` 뒤에 붙는 이름(`RELIABILITY_QOS_POLICY`, `DURABILITY_QOS_POLICY` 등)이 정확히 어느 정책이 문제인지 알려준다. 이 로그가 안 보인다면 로그 레벨을 확인하라 — 기본 레벨에서 보이지만, 필터링 설정에 따라 묻힐 수 있다.

**3. 코드 레벨에서 발행자·구독자 양쪽의 QoS 생성 지점을 대조한다.** `create_publisher`/`create_subscription`의 세 번째 인자가 정수인지, `QoSProfile` 객체인지, 프리셋인지 확인한다. 정수 하나만 넘기면 **기본 프로파일(`RELIABLE`)**이 적용된다는 걸 잊기 쉽다.

::: tip 실무에서 통하는 규칙
발행자와 구독자를 **각자 다른 사람이 짜는 경우가 많다.** 그래서 QoS를 아예 안 맞는 조합으로 배포하는 사고가 실제로 자주 일어난다. 이걸 막는 실무 규칙은 하나다 — **드라이버·센서 패키지가 어떤 QoS로 발행하는지 항상 문서화하고, 구독자는 그 프리셋을 그대로 가져다 쓴다.** `QoSPresetProfiles.SENSOR_DATA.value`처럼 이름이 있는 프리셋을 쓰면, 숫자를 외울 필요 없이 "이 토픽은 센서 데이터 취급"이라는 의도가 코드에 그대로 드러난다.
:::

## 왜 센서 데이터엔 best_effort를 쓰는가

이 질문에 대한 답은 [4.1 동시성 모델 지도](#/concurrency-map)에서 이미 배운 개념과 정확히 같다 — **최신성이 완전성보다 중요한 상황이 있다.**

카메라가 30Hz로 프레임을 발행한다고 하자. `RELIABLE`을 쓰면 프레임 하나가 유실될 때마다 DDS가 재전송을 시도한다. 그런데 재전송이 끝나기 전에 다음 프레임, 그다음 프레임이 이미 카메라에서 나오고 있다. 재전송에 쓴 시간과 대역폭은 **이미 낡아버린 데이터**를 살리는 데 들어간다. 구독자 입장에서는 30ms 전 프레임을 뒤늦게 받느니, 그냥 그 프레임은 포기하고 지금 들어오는 최신 프레임을 받는 게 낫다.

LiDAR, IMU, 카메라처럼 **높은 빈도로 계속 새 데이터가 나오는 센서**는 전부 이 논리를 따른다. 프레임 하나, 스캔 한 번 유실되는 건 다음 것이 100ms 안에 또 온다면 치명적이지 않다. 반대로 목표 지점 명령, 긴급 정지 신호, 서비스 호출처럼 **한 번만 오고 반드시 도착해야 하는 메시지**는 `RELIABLE`이 맞다. 이게 [10.5 서비스](#/services)가 항상 `RELIABLE` 기본값을 쓰는 이유이기도 하다 — 요청이 조용히 사라지면 클라이언트는 응답을 영원히 기다린다.

::: cote 코딩테스트와의 연결은 아니지만, 트레이드오프 감각은 같다
"완벽하지만 느린 것 vs 대충이지만 빠른 것" 사이의 선택은 알고리즘에서도 익숙하다. [7.19 그리디](#/greedy)에서 최적해를 포기하고 근사해를 빠르게 얻는 감각, [5.1 프로파일링](#/profiling)에서 "측정 없이 최적화 없다"고 배운 감각과 같은 줄기다. QoS 선택도 결국 **"이 상황에서 무엇을 포기할 수 있는가"를 먼저 묻는 설계 결정**이다.
:::

## 실전에서 자주 나는 QoS 사고 두 가지

**RViz가 지도를 안 보여준다.** RViz의 기본 구독 QoS는 `RELIABLE` + `VOLATILE`이다. SLAM 노드가 지도를 `TRANSIENT_LOCAL`로 발행하는데 RViz가 `VOLATILE`로 구독하면 — 잠깐, 이 조합은 방금 배운 규칙으로는 **호환된다** (`TRANSIENT_LOCAL ≥ VOLATILE`이므로 구독자가 더 약한 걸 요구하는 셈). 그런데 실전에서 이 조합이 문제가 되는 경우는 보통 반대다: 커스텀 노드가 지도를 `VOLATILE`로 발행하면서 "한 번만 보내면 되겠지" 하고 넘어갔을 때, RViz를 지도 발행 이후에 켠 사용자는 영원히 못 본다. 원인은 QoS 불일치가 아니라 **애초에 지도 발행자가 `TRANSIENT_LOCAL`을 안 썼다**는 설계 실수다.

**센서 드라이버 교체 후 갑자기 구독이 끊긴다.** 기존 드라이버는 `RELIABLE`로 발행했는데, 새 드라이버(혹은 새 버전)가 성능 이유로 `BEST_EFFORT`로 바꿨다. 기존 구독 코드가 정수 depth만 넘겨서 암묵적으로 `RELIABLE`을 요구하고 있었다면, 드라이버 교체 순간 아무 코드도 안 건드렸는데 통신이 끊긴다. 이런 사고를 피하려면 **구독자도 명시적으로 QoS를 선언**해서, 어떤 조건에서 통신이 성립하는지 코드에 드러내야 한다.

## 요약

- ROS 2는 중앙 서버(`roscore`) 없이 **DDS**라는 표준 미들웨어로 노드끼리 직접 통신한다. `rmw` 층이 DDS 벤더(Fast DDS, Cyclone DDS 등)를 감춘다.
- QoS는 발행자와 구독자가 **각자 따로** 설정하며, 대표 정책은 Reliability(RELIABLE/BEST_EFFORT), Durability(TRANSIENT_LOCAL/VOLATILE), History(KEEP_LAST/KEEP_ALL) + Depth다.
- 호환 규칙은 하나다. **발행자가 제공하는 수준 ≥ 구독자가 요구하는 수준**일 때만 연결된다. 어긋나면 연결이 아예 안 만들어진다.
- **에러도 예외도 없이 조용히 실패한다.** `ros2 topic info --verbose`로 양쪽 QoS를 대조하고, 노드 로그의 `Last incompatible policy` 경고를 확인하는 게 표준 진단 절차다.
- 센서 데이터는 **최신성이 완전성보다 중요**해서 `BEST_EFFORT`를 쓴다. 서비스·중요 명령은 반드시 도착해야 하므로 `RELIABLE`을 쓴다.
- `create_publisher`/`create_subscription`에 정수만 넘기면 **기본 프로파일(RELIABLE, VOLATILE, depth=10)**이 암묵적으로 적용된다는 걸 잊지 마라.

::: quiz 연습문제
1. 발행자가 `Reliability=RELIABLE`, `Durability=TRANSIENT_LOCAL`로 설정돼 있다. 구독자가 각각 다음과 같을 때 연결이 되는지 안 되는지, 그리고 그 이유를 규칙에 따라 설명하라.
   - (a) `Reliability=BEST_EFFORT`, `Durability=VOLATILE`
   - (b) `Reliability=RELIABLE`, `Durability=TRANSIENT_LOCAL`
   - (c) `Reliability=RELIABLE`, `Durability=VOLATILE`이고 발행자가 반대로 `Durability=VOLATILE`인 경우

2. 본문의 `compatible(offered, requested)` 함수를 확장해서, `History`/`Depth`까지 포함한 세 가지 정책을 한 번에 검사하는 함수 `all_compatible(pub_qos, sub_qos)`를 작성하고 몇 가지 조합으로 직접 실행해 확인하라. (힌트: History/Depth는 Reliability·Durability와 달리 호환성 자체를 막지 않고, 도착 후 처리 방식만 바꾼다 — 이 차이를 코드에 반영해 보라.)

3. LiDAR 드라이버를 `BEST_EFFORT`에서 `RELIABLE`로 바꾸면 어떤 상황에서 오히려 성능이 나빠질 수 있는가? [4.1 동시성 모델 지도](#/concurrency-map)의 지연(latency)과 처리량(throughput) 개념을 가져와 설명하라.

4. `ros2 topic info /odom --verbose`를 실행했더니 발행자 QoS에 `Durability: VOLATILE`, 구독자(당신이 만든 노드) QoS에 `Durability: TRANSIENT_LOCAL`이 찍혀 있다. 통신이 될까, 안 될까? 고치려면 어느 쪽을, 어떻게 바꿔야 하는가?

5. **생각해 볼 문제.** QoS 불일치가 컴파일 에러나 런타임 예외로 즉시 드러나지 않고 "조용히 실패"하도록 설계된 데는 DDS 발견 프로토콜의 분산적 특성이 관련 있다. 중앙 서버가 없는 시스템에서 "이 조합은 잘못됐다"는 사실을 **누가, 언제** 알려줄 수 있을지 생각해 보고, 왜 즉각적인 에러 알림이 어려운지 설명하라.
:::

**다음 절**: [10.9 TF2 좌표 변환](#/tf2) — 로봇 곳곳의 좌표계를 하나로 잇는 프레임 트리, 그리고 시간 동기화가 낳는 흔한 오류.
