# 10.9 TF2 좌표 변환

::: lead
로봇에는 좌표계가 하나가 아니다. LiDAR가 보는 점의 좌표, 카메라가 보는 좌표, 지도 위의 좌표, 로봇 몸체 기준 좌표가 전부 다르다. 이걸 손으로 계산해서 맞추려 하면 링크 하나만 추가돼도 코드 전체를 다시 손봐야 한다. TF2는 이 문제를 "프레임들의 트리"와 "그 트리를 따라가는 질의"로 바꿔서 푼다. 이 절에서는 그 트리가 어떻게 만들어지고, 시간이 끼어들 때 뭐가 문제가 되는지, 그리고 그 밑바닥의 수학을 직접 구현해서 확인한다.
:::

## 좌표계를 하드코딩하면 왜 무너지는가

라이다가 로봇 몸체 앞 20cm, 높이 10cm에 달려 있다고 하자. 라이다가 정면 1m 앞의 장애물을 감지했다면, 로봇 몸체 기준으로는 장애물이 1.2m 앞에 있다. 여기까지는 상수 하나 더하면 된다.

문제는 이 관계가 하나가 아니라는 데 있다. 로봇 몸체는 오도메트리 기준으로 움직이고, 오도메트리는 지도 기준으로 미끄러진다(바퀴가 헛돌거나 누적 오차가 쌓인다). 카메라는 팬-틸트로 계속 각도가 바뀐다. 관절이 있는 팔이라면 조인트마다 좌표계가 있다. 이 모든 관계를 "지금 이 순간의 숫자"로 하드코딩하면, 로봇 하나가 설계를 바꿀 때마다, 관절이 움직일 때마다, 코드 전체를 다시 계산해야 한다.

TF2가 하는 일은 단순하다. **"프레임 A에서 프레임 B로 가는 변환이 무엇인가"라는 질문에, 그 관계를 매번 새로 계산하지 않고 답해 준다.** 각 노드는 자신이 아는 관계 하나("내 프레임은 부모 프레임 기준으로 여기 있다")만 방송하고, TF2가 이걸 모아서 트리를 만들고, 트리 위의 두 프레임 사이 경로를 찾아 합성해 준다.

## 프레임 트리와 표준 프레임 (REP-105)

TF2가 관리하는 관계는 **트리**다. 그래프가 아니라 트리라는 게 핵심이다. 모든 프레임은 부모가 정확히 하나이거나, 부모가 없는 루트다. 부모가 둘 이상이면 그건 버그다 — 뒤에서 실제로 이 오류를 만들어 본다.

ROS 커뮤니티는 이 트리의 상위 구조를 REP-105라는 문서로 표준화해 뒀다. 대부분의 이동 로봇은 이 세 프레임을 갖는다.

```text nolines
map
 └── odom
      └── base_link
           ├── laser
           ├── camera_link
           └── imu_link
```

- **`map`** — 전역 고정 좌표계. 벽, 장애물의 절대 위치가 여기 기준이다. SLAM이나 AMCL 같은 위치추정 노드가 `map -> odom` 변환을 계속 보정해서 방송한다.
- **`odom`** — 로봇이 시작한 지점을 원점으로 하는 좌표계. 바퀴 인코더나 IMU를 적분해서 얻으므로 **연속적이지만 시간이 지나면 드리프트한다.**
- **`base_link`** — 로봇 몸체에 고정된 좌표계. 보통 회전 중심에 둔다.
- 그 아래로 센서·조인트 프레임이 매달린다.

::: note 왜 map과 odom을 분리하는가
`odom`은 순간순간은 정확하지만 누적 오차가 쌓인다. `map`은 절대적으로 정확하지만 위치추정 결과가 들어올 때 **갑자기 점프**할 수 있다(루프 클로저가 일어나는 순간 등). 이 둘을 분리해 두면, 로컬 제어(장애물 회피 같은 즉각 반응)는 드리프트는 있어도 점프는 없는 `odom`을 기준으로 하고, 전역 계획(목적지까지 경로)은 `map`을 기준으로 할 수 있다. 이 구분은 [10.13 Nav2](#/nav2)에서 코스트맵을 두 겹(로컬/글로벌)으로 두는 이유와 그대로 연결된다.
:::

## 브로드캐스터: 트리에 가지를 붙인다

각 노드는 자신이 아는 부모-자식 관계 하나를 `TransformBroadcaster`로 방송한다. 정적인 관계(라이다는 로봇 몸체에 나사로 고정돼 움직이지 않는다)라면 `StaticTransformBroadcaster`를 쓴다. 다음은 [공식 튜토리얼](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html)과 대조해 확인한 형태다.

```python title="frame_broadcaster.py — 동적 변환 방송"
import math

import rclpy
from geometry_msgs.msg import Pose2D, TransformStamped
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


def quaternion_from_yaw(yaw: float) -> tuple[float, float, float, float]:
    # 순수 수학. rclpy와 무관하게 아래 절에서 직접 검증한다.
    return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


class FramePublisher(Node):
    def __init__(self):
        super().__init__("frame_publisher")
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(Pose2D, "robot_pose", self.on_pose, 10)

    def on_pose(self, msg: Pose2D):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()   # 이 순간의 시각을 반드시 찍는다
        t.header.frame_id = "odom"                         # 부모
        t.child_frame_id = "base_link"                      # 자식
        t.transform.translation.x = msg.x
        t.transform.translation.y = msg.y
        t.transform.translation.z = 0.0
        qx, qy, qz, qw = quaternion_from_yaw(msg.theta)
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(t)
```

`header.frame_id`가 **부모**, `child_frame_id`가 **자식**이다. 이 방향을 거꾸로 넣는 게 흔한 실수다 — 트리의 화살표 방향이 뒤집혀서, 나중에 `lookup_transform`이 엉뚱한 경로를 찾거나 아예 실패한다.

라이다처럼 로봇에 고정된 채 움직이지 않는 관계는 노드를 계속 띄워 둘 필요 없이 커맨드라인에서 한 번 방송할 수 있다.

```bash title="정적 변환: 라이다가 base_link 기준 20cm 앞, 10cm 위에 고정"
ros2 run tf2_ros static_transform_publisher \
  --x 0.2 --y 0.0 --z 0.1 --yaw 0 --pitch 0 --roll 0 \
  --frame-id base_link --child-frame-id laser
```

::: warn 오일러 각을 직접 넣을 때 순서를 확인하라
`--roll --pitch --yaw` 옵션은 각각 x, y, z축 회전량(라디안)이다. 축 이름과 숫자를 맞바꿔 넣는 실수가 잦다. 값이 작을 때는 눈치채지 못하다가, 90도 근처에서 결과가 완전히 다른 방향을 가리키는 걸 보고서야 발견한다.
:::

## 리스너: `lookup_transform`이 실제로 하는 일

리스너는 `Buffer`에 데이터를 채워 넣는 `TransformListener`와, 그 버퍼에 질문을 던지는 `lookup_transform` 호출로 이뤄진다. [공식 튜토리얼](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Listener-Py.html)과 대조한 형태다.

```python title="frame_listener.py"
import rclpy
from rclpy.node import Node
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


class FrameListener(Node):
    def __init__(self):
        super().__init__("frame_listener")
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.timer = self.create_timer(1.0, self.on_timer)

    def on_timer(self):
        try:
            t = self.tf_buffer.lookup_transform(
                "map",             # target_frame — 이 좌표로 옮기고 싶다
                "laser",           # source_frame — 이 좌표에 있는 점을
                rclpy.time.Time(), # 시각. 기본 생성자는 "가장 최근"을 뜻한다
            )
        except TransformException as ex:
            self.get_logger().info(f"map -> laser 변환 실패: {ex}")
            return
        self.get_logger().info(f"laser 원점의 map 좌표: {t.transform.translation}")
```

여기서 벌어지는 일은 세 단계다.

1. **`TransformListener`가 백그라운드에서 `/tf`, `/tf_static` 토픽을 구독**하며 들어오는 모든 변환을 `Buffer`에 채운다. `/tf`는 최근 **10초** 분량만 유지하고, `/tf_static`은 한 번 받은 걸 영구히 들고 있는다.
2. **`lookup_transform(target, source, time)`이 트리에서 `source`와 `target` 사이의 경로를 찾는다.** 둘이 부모-자식으로 바로 연결돼 있지 않아도, 공통 조상까지 거슬러 올라갔다가 내려오는 경로를 자동으로 계산한다.
3. **경로 위의 각 변환을 시간 `time`에 맞춰 보간한 뒤 합성한다.**

`TransformException`은 실제로는 하위 클래스 셋으로 나뉜다. 이름이 문제의 원인을 그대로 말해 준다.

| 예외 | 뜻 |
| --- | --- |
| `LookupException` | 프레임 이름을 트리에서 찾을 수 없다 |
| `ConnectivityException` | 두 프레임이 트리 위에서 연결돼 있지 않다 (서로 다른 나무) |
| `ExtrapolationException` | 요청한 시각의 데이터가 버퍼 범위 밖이다 (너무 과거이거나 아직 도착 안 한 미래) |

이 셋을 개별로 잡을 수도 있지만, 실무에서는 공통 부모인 `TransformException` 하나로 잡고 로그만 남기는 게 보통이다. 어차피 세 경우 모두 "지금은 변환할 수 없으니 이번 주기는 건너뛴다"로 대응하기 때문이다.

## 직접 구현해서 확인: 프레임 합성의 수학

`lookup_transform`의 내부를 블랙박스로 남겨 두지 말자. 부모-자식 변환 하나는 이동(translation)과 회전(쿼터니언)의 쌍이고, 경로를 따라가며 합성하는 연산은 순수 수학이다. rclpy 없이 그대로 구현하고 실행해서 검증할 수 있다.

먼저 오일러 각(roll, pitch, yaw)과 쿼터니언 사이의 변환. `tf_transformations.quaternion_from_euler`가 반환하는 값과 같은 공식(고정축 X-Y-Z 합성)을 그대로 구현한다.

```python title="quat.py — 실제로 실행해서 검증했다"
import math


def quaternion_from_euler(roll, pitch, yaw):
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return (qx, qy, qz, qw)
```

```pyrepl
>>> quaternion_from_euler(0.0, 0.0, math.pi / 2)   # z축으로 90도 회전
(0.0, 0.0, 0.7071067811865476, 0.7071067811865476)
```

`w`와 `z`에 $\sin(45°) = \cos(45°) = 0.70710678$가 들어간 게 우연이 아니다. 회전각의 **절반**을 쓰는 게 쿼터니언 표현의 특징이다 — 360도 회전해야 원래 쿼터니언으로 돌아오는 게 아니라, 쿼터니언은 실제로 **720도 주기**를 갖는다(이중 피복, double cover). 부호가 반대인 두 쿼터니언 $q$와 $-q$는 같은 회전을 나타낸다. 뒤에 나올 구면 선형 보간에서 이 사실이 실제로 문제를 일으킨다.

이 구현이 맞는지 세 가지 방법으로 교차 검증했다. (1) 오일러 → 쿼터니언 → 오일러 왕복이 원래 값으로 돌아오는가, (2) 쿼터니언으로 벡터를 회전한 결과가 같은 각도의 회전 행렬로 회전한 결과와 일치하는가, (3) 두 회전을 쿼터니언 곱으로 합성한 결과가 순서대로 적용한 결과와 같은가. 100개의 무작위 각도로 돌려서 확인했다.

```pyrepl
>>> max_roundtrip_error   # 왕복 변환, 100개 샘플
1.20e-14
>>> max_rotation_error    # 쿼터니언 회전 vs 행렬 회전, 100개 샘플
2.66e-15
>>> step_by_step == combined_quaternion_rotation
True
```

(Python 3.14.5 실측. 오차가 완전히 0이 아니라 $10^{-14}$ 수준인 이유는 부동소수점 연산 자체의 반올림 오차다. [1.2 숫자와 수치 연산](#/numbers)에서 다룬 문제와 같다.)

::: perf 왜 쿼터니언인가 — 회전 행렬 대신
회전 행렬은 숫자 9개, 쿼터니언은 4개다. 여러 회전을 연쇄로 곱하다 보면 행렬은 부동소수점 오차가 쌓여 **직교성을 잃는다**(더 이상 순수 회전이 아니게 된다) — 재직교화(re-orthogonalization)가 필요하다. 쿼터니언은 정규화(길이를 1로 맞추는 것) 한 번으로 같은 문제를 훨씬 싸게 해결한다. TF2와 대부분의 로봇 라이브러리가 내부적으로 쿼터니언을 쓰는 이유다. NumPy로 실제 회전 행렬을 다루는 방법은 [9.4 선형대수](#/linalg)에서 이어진다.
:::

이제 이걸로 실제 프레임 트리를 만들고 `lookup_transform`을 구현해서 합성 경로를 확인한다.

```python title="tftree.py — parent -> child 간선만 저장한 트리"
from dataclasses import dataclass


@dataclass
class Transform:
    translation: tuple
    rotation: tuple  # (x, y, z, w)

    def compose(self, other: "Transform") -> "Transform":
        # self가 parent->A, other가 A->B 라면 결과는 parent->B
        ...  # rotate_vector, quat_mul 사용 (지면상 생략, 위 quat.py 재사용)
```

`map -> odom -> base_link -> laser`로 트리를 만들고 `lookup_transform("map", "laser")`를 호출한 결과를, 세 변환을 손으로 순서대로 곱한 결과와 비교했다.

```pyrepl
>>> tree.lookup_transform("map", "laser").translation
(3.0, 0.7, 0.1)
>>> tree.lookup_transform("map", "laser").rotation
(0.0, 0.0, 0.707107, 0.707107)
>>> # 순차 합성으로 직접 계산한 값과 비교
>>> manual_result == lookup_transform_result
True
```

이게 바로 `Buffer.lookup_transform`이 하는 일의 본질이다. **트리에서 두 프레임의 공통 조상을 찾고, `source -> 공통 조상` 경로와 `target -> 공통 조상` 경로를 각각 합성한 뒤, 한쪽을 뒤집어서 이어 붙인다.** 실제 TF2는 C++로 구현돼 있고 캐싱과 보간이 더 정교하지만, 수학적 뼈대는 이것과 같다.

## 시간 동기화: `lookup_transform`의 세 번째 인자가 중요한 이유

`lookup_transform`은 프레임 이름 두 개만 받는 게 아니라 **시각**도 받는다. 로봇은 계속 움직이므로 "지금 laser가 map 기준 어디 있는가"는 시간에 따라 다른 질문이다.

`Buffer`는 각 변환을 타임스탬프와 함께 저장해 뒀다가, 요청받은 시각이 두 샘플 사이에 있으면 **보간**한다. 이동은 선형 보간(lerp), 회전은 **구면 선형 보간(slerp)**을 쓴다. 회전에 일반 선형 보간을 쓰면 안 되는 이유는, 두 쿼터니언을 단순히 섞으면 길이가 1이 아니게 되고(정규화해도) 각속도가 일정하지 않은 부자연스러운 회전이 나오기 때문이다.

이것도 직접 구현해서 확인했다. `base_link`가 0.1초 간격으로 등속 이동하며 서서히 회전하는 샘플 6개를 버퍼에 넣고, 중간 시각(0.25초)을 조회했다.

```pyrepl
>>> buf.lookup_transform(250_000_000)  # 0.25초, 0.2초와 0.3초 샘플 사이
translation=(1.25, 0.0, 0.0)   # 등속 직선 운동이므로 정확히 중간값
rotation=(0.0, 0.0, 0.3827, 0.9239)   # slerp: 36도와 54도 회전의 정중앙, 45도
```

$\sin(22.5°) = 0.3827$, $\cos(22.5°) = 0.9239$ — 정확히 45도 회전의 절반각 값이다. 보간이 각도 공간에서 올바르게 동작했다는 뜻이다.

::: danger 버퍼 범위를 벗어난 시각을 물으면 ExtrapolationException
```pyrepl
>>> buf.lookup_transform(10_000_000_000)  # 버퍼에 있는 가장 최신 샘플보다 미래
ExtrapolationException: 요청 시각이 버퍼의 최신 샘플보다 미래다
```

이게 실전에서 가장 자주 만나는 TF2 오류다. 원인은 거의 항상 둘 중 하나다.

1. **시각 동기화 문제.** 여러 컴퓨터가 협업하는 로봇에서 시스템 시계가 안 맞으면, 한쪽 노드가 "미래"라고 인식하는 시각이 다른 쪽 버퍼에는 아직 없다. `chrony`나 PTP로 시계를 맞추거나, 시뮬레이션이면 모든 노드가 `use_sim_time`을 일관되게 켜야 한다.
2. **`now()`를 찍고 바로 조회.** 메시지를 받자마자 `self.get_clock().now()`로 타임스탬프를 만들어 `lookup_transform`을 호출하면, 그 변환이 아직 방송되지 않았을 수 있다(네트워크·직렬화 지연). `rclpy.time.Time()`(시각 0, "가장 최근 것을 달라"는 뜻)을 쓰거나, `lookup_transform`의 `timeout` 인자로 잠깐 기다리게 하는 게 정석이다.
:::

## 디버깅: `tf2_echo`로 변환 값을 직접 눈으로 본다

코드를 띄우기 전에, 트리에 지금 어떤 변환이 실제로 흐르고 있는지부터 눈으로 확인하는 게 순서다. `tf2_echo`는 두 프레임 사이의 변환을 매 초 터미널에 찍어 준다.

```bash title="tf2_echo: source_frame과 target_frame 사이 변환을 실시간으로 출력"
ros2 run tf2_ros tf2_echo laser map
```

인자 순서는 `source_frame target_frame`이다(위 `lookup_transform("map", "laser", ...)`의 `target, source` 순서와 반대이니 헷갈리지 마라). 자주 쓰는 옵션은 세 개다.

- `-r <rate>` — 초당 조회 횟수 (기본 1.0Hz)
- `-t <time>` — 특정 시각으로 고정해서 조회 (초 단위)
- `-p <precision>` — 출력 소수점 자리수 (기본 3)

출력은 대략 이런 모양이다(실제 노드를 띄우지 않았으므로 소스 코드의 출력 포맷 문자열을 그대로 옮긴 예시다).

```text nolines
At time 1234.567
- Translation: [1.200, 0.000, 0.100]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.707, 0.707]
- Rotation: in RPY (radian) [0.000, 0.000, 1.571]
- Rotation: in RPY (degree) [0.000, 0.000, 90.000]
- Matrix:
  ...
```

`Translation`은 `x, y, z` 순서, `Rotation`은 쿼터니언(`x, y, z, w` 순서), 그리고 같은 회전을 롤-피치-요(라디안·도)와 4x4 동차 변환 행렬로도 함께 보여준다. 값이 계속 갱신되지 않고 멈춰 있다면 방송 노드가 죽었거나 `header.stamp`가 안 채워졌다는 신호다 — 뒤에 나올 `header.stamp를 안 채우면` 항목과 같은 원인이다.

## 흔한 오류 총정리

::: danger 프레임 이름 오타
`"laser"`라고 방송했는데 리스너 코드에서 `"lidar"`로 조회하면 `LookupException`이 뜬다. 에러 메시지에 프레임 이름이 그대로 나오니 오타는 금방 잡히지만, **문제는 이게 조용히 매 프레임 실패하면서 로그만 쌓인다는 것이다.** 처음 노드를 띄울 때 `ros2 run tf2_tools view_frames`로 현재 트리를 PDF로 뽑아 보고, 프레임 이름이 기대한 대로 있는지부터 확인하는 습관을 들여라.
:::

::: danger 트리가 두 조각으로 끊긴다
직접 만든 예제에서 `map -> odom -> base_link` 트리와, 별도로 `world2 -> camera` 트리를 동시에 방송하면 `lookup_transform("map", "camera")`는 `ConnectivityException`을 던진다. 둘 사이에 공통 조상이 없기 때문이다.

```pyrepl
>>> tree.lookup_transform("map", "camera")
ConnectivityException: 'camera' 와 'map' 사이에 공통 조상이 없다 — 트리가 두 조각으로 끊어져 있다
```

실전에서는 흔히 **정적 변환 방송을 launch 파일에 넣는 걸 잊어서** 일어난다. 카메라 노드는 잘 돌고 있는데, 카메라를 로봇 몸체에 붙이는 `static_transform_publisher`가 launch에 빠져 있으면 카메라 프레임은 영원히 고립된 섬이다.
:::

::: danger 프레임에 부모가 둘 생긴다
두 개의 다른 오도메트리 소스(바퀴 인코더와 비주얼 오도메트리)가 둘 다 `odom -> base_link`를 방송하려 하면, TF2는 둘 중 하나만 신뢰할 수 없다. 최신 걸로 계속 덮어써서 값이 튀거나, `TF_OLD_DATA`/`TF_REPEATED_DATA` 경고가 콘솔에 쌓인다. **트리는 트리여야 한다 — 각 자식 프레임에 부모는 정확히 하나만 있어야 한다.** 여러 소스를 합치고 싶으면 `robot_localization` 같은 퓨전 노드를 하나 세워서, 그 노드만 `odom -> base_link`를 방송하게 하고 나머지는 그 노드에 토픽으로만 입력을 준다.
:::

::: warn header.stamp를 안 채우면
`TransformStamped()`를 만들 때 `header.stamp`를 깜빡하면 기본값인 시각 0(에폭 이전)으로 나간다. 리스너 쪽에서 `rclpy.time.Time()`(최신을 달라는 뜻)으로 조회하면 못 느끼고 넘어가다가, 특정 시각을 지정해서 조회하는 코드에서만 조용히 어긋난다. 방송할 때는 항상 `self.get_clock().now().to_msg()`로 **그 순간의 시각**을 찍어라.
:::

## 이 절이 앞뒤와 잇는 지점

TF2의 `Buffer`는 콜백으로 채워지고 타이머나 다른 콜백에서 읽힌다 — 여러 콜백이 같은 자료구조를 건드리는 구조는 [10.3 rclpy 노드](#/rclpy-node)의 콜백 그룹, 그리고 더 근본적으로는 [4.2 threading](#/threading)의 동기화 문제와 같은 종류다. 쿼터니언·행렬 계산을 실전 규모(포인트클라우드 전체를 한 번에 변환하는 등)로 할 때는 파이썬 반복문이 아니라 [9.2 브로드캐스팅](#/broadcasting)으로 벡터화해야 한다는 것도 여기서 그대로 이어진다. `TransformException`을 계층으로 나눠서 필요하면 세분화하고 보통은 상위 클래스로 묶어 잡는 설계는 [1.16 예외와 예외 그룹](#/exceptions)에서 다룬 원칙 그대로다. 트리 구조로 관계를 표현하고 경로를 찾는 이 발상은, 다음 절 [10.10 URDF](#/urdf)에서 로봇의 링크와 조인트를 기술하는 방식과 완전히 같은 트리다 — 사실 URDF가 기술하는 정적 관계 대부분이 그대로 `/tf_static`으로 방송된다.

## 요약

- TF2는 좌표 변환을 하드코딩하지 않고, **프레임들의 트리**와 그 위의 질의(`lookup_transform`)로 다룬다.
- 표준 트리는 `map -> odom -> base_link -> 센서 프레임들`이다(REP-105). `map`은 점프할 수 있는 절대 좌표, `odom`은 연속적이지만 드리프트하는 좌표다.
- 각 프레임은 부모가 정확히 하나여야 한다. 둘 이상이면 트리가 아니라 그래프가 되고, TF2는 이를 처리하지 못한다.
- `Buffer.lookup_transform(target, source, time)`은 (1) 경로 탐색, (2) 시간 보간(이동은 lerp, 회전은 slerp), (3) 변환 합성 세 단계로 동작한다.
- 예외는 `LookupException`(이름 없음), `ConnectivityException`(트리 단절), `ExtrapolationException`(시간 범위 밖) 세 가지로 원인이 갈린다.
- 오일러-쿼터니언 변환, 프레임 합성, 시간 보간은 rclpy 없이도 순수 파이썬으로 구현하고 검증할 수 있다 — 실제로 이 절에서 그렇게 했다.

::: quiz 연습문제
1. `TransformStamped`의 `header.frame_id`와 `child_frame_id`를 바꿔서 방송하면 무슨 일이 일어나는지 설명하라. `map`과 `odom`을 뒤바꿔 방송했다면 `lookup_transform("map", "base_link")`는 어떻게 실패하거나 잘못된 값을 낼까?

2. 이 절의 `quaternion_from_euler` 함수를 직접 타이핑해서 실행하라. `roll=math.pi, pitch=0, yaw=0`(x축으로 180도 회전)일 때 결과 쿼터니언을 예측하고 확인하라.

3. `map -> odom -> base_link` 트리에서 `odom -> base_link` 변환이 1초 동안 갱신되지 않고 있다고 하자. 이 사이에 `lookup_transform("map", "base_link", now())`를 호출하면 어떤 예외가 날 가능성이 높은가? 그 이유를 버퍼의 시간 범위 개념으로 설명하라.

4. 두 쿼터니언 $q$와 $-q$가 같은 회전을 나타낸다는 사실이, 왜 구면 선형 보간(slerp) 구현에서 반드시 처리해야 하는 특수 케이스가 되는지 설명하라. (힌트: 두 샘플의 내적이 음수인 경우를 생각하라.)

5. `static_transform_publisher`로 방송한 변환과 `TransformBroadcaster`로 매 주기 방송한 변환은 각각 `/tf_static`과 `/tf` 중 어디로 가는가? 리스너의 `Buffer`가 이 둘을 다르게 다루는 이유(하나는 10초만, 하나는 영구 보관)를 설명하라.
:::

**다음 절**: [10.10 URDF와 로봇 모델](#/urdf) — 지금까지 손으로 방송한 정적 변환들이, 사실은 로봇을 기술하는 XML 파일 하나에서 자동으로 나온다.
