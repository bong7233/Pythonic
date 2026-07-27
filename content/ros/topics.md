# 10.4 토픽

::: lead
[10.3](#/rclpy-node)에서 노드를 만들었다. 그런데 노드 혼자서는 아무것도 못 한다. 로봇은 카메라 노드가 본 것을 계획 노드가 알아야 하고, 계획 노드가 정한 속도를 모터 노드가 실행해야 한다. 노드끼리 정보를 주고받는 가장 기본적인 방법이 토픽이다. 이 절은 발행-구독이 왜 함수 호출보다 나은 설계인지부터 시작해서, 표준 메시지와 커스텀 메시지, 그리고 이미지 같은 큰 메시지를 흘려보낼 때 실제로 무슨 비용이 드는지까지 다룬다. Part I에서 배운 "객체는 이름표가 붙을 뿐"이라는 모델과 Part IV의 스레드 모델이 여기서 그대로 다시 나온다.
:::

## 함수 호출이 아니라 발행-구독인 이유

카메라가 이미지를 찍었고, 두 개의 노드가 그 이미지가 필요하다고 하자. 물체 인식 노드 하나, 기록용 노드 하나. 가장 단순하게 짜면 이렇게 될 것이다.

```python title="나쁜 설계 — 직접 호출"
class Camera:
    def __init__(self, detector, recorder):
        self.detector = detector      # 카메라가 구독자를 알아야 한다
        self.recorder = recorder

    def on_new_frame(self, frame):
        self.detector.process(frame)
        self.recorder.save(frame)
```

이 코드는 세 가지 문제를 동시에 만든다. 카메라가 구독자의 존재를 알아야 하고(결합), 구독자를 하나 추가하려면 카메라 코드를 고쳐야 하고(경직), 구독자 중 하나가 느리면 카메라의 다음 프레임 캡처까지 밀린다(동기 실행). 게다가 이 셋은 애초에 **같은 프로세스, 같은 언어로 짜여 있어야** 이 코드가 성립한다. 로봇 시스템에서는 카메라 드라이버가 C++이고 인식 노드가 파이썬인 경우가 흔하다.

발행-구독은 이 결합을 끊는다. 카메라는 "topic이라는 이름의 우체통에 이미지를 넣는다"는 것만 안다. 누가 읽는지, 몇 명이 읽는지, 그 노드가 파이썬인지 C++인지 전혀 모른다.

```text nolines
   Camera 노드                              Detector 노드
   ┌──────────┐        /image           ┌──────────┐
   │ publish  │ ───────────────────────▶ │ subscribe │   <- 토픽 이름: /image
   └──────────┘              │           └──────────┘
                              │
                              │           Recorder 노드
                              └─────────▶ ┌──────────┐
                                          │ subscribe │
                                          └──────────┘
```

이게 **다대다**(N:M) 통신이다. 발행자가 여럿이어도 되고(같은 토픽에 여러 카메라가 쏠 수 있다), 구독자가 여럿이어도 된다. 발행자와 구독자는 서로의 존재조차 모른 채 실행 순서도, 프로세스도, 언어도 다를 수 있다. 이 결합 해제의 대가는 **비동기성**이다 — 발행한 메시지가 언제 도착할지, 도착하긴 할지 발행자는 보장받지 못한다. 그 보장의 정도를 조절하는 게 [10.8 QoS](#/qos)다.

## 최소 발행자와 구독자

퍼블리셔/서브스크라이버 코드부터 보자. 공식 튜토리얼의 최소 예제를 그대로 따른다. ([`Writing-A-Simple-Py-Publisher-And-Subscriber`, ROS 2 문서 rolling/jazzy 브랜치](https://github.com/ros2/ros2_documentation/blob/rolling/source/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Publisher-And-Subscriber.rst) 기준으로 클래스명·메서드 시그니처 대조 완료.)

```python title="minimal_publisher.py"
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MinimalPublisher(Node):
    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher_ = self.create_publisher(String, 'topic', 10)
        self.timer = self.create_timer(0.5, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Hello World: {self.i}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.i += 1


def main(args=None):
    rclpy.init(args=args)
    node = MinimalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

```python title="minimal_subscriber.py"
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MinimalSubscriber(Node):
    def __init__(self):
        super().__init__('minimal_subscriber')
        self.subscription = self.create_subscription(
            String, 'topic', self.listener_callback, 10)

    def listener_callback(self, msg):
        self.get_logger().info(f'I heard: "{msg.data}"')


def main(args=None):
    rclpy.init(args=args)
    node = MinimalSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

`create_publisher(타입, 이름, 큐길이)` 와 `create_subscription(타입, 이름, 콜백, 큐길이)` 의 세 번째/네 번째 인자에 있는 정수 `10` 은 큐 깊이다. 정수 하나만 넘기면 rclpy가 그것을 QoS의 `depth` 값으로 채운 기본 프로파일을 만든다 — 뒤에서 다시 다룬다.

::: note 두 노드를 실행하면 이렇게 뜬다
직접 실행한 결과가 아니라, 공식 튜토리얼이 보여주는 전형적인 출력이다. 실제 타임스탬프·PID는 매번 다르다.

```text nolines
[INFO] [1234567890.123456789] [minimal_publisher]: Publishing: "Hello World: 0"
[INFO] [1234567891.234567890] [minimal_subscriber]: I heard: "Hello World: 0"
```
:::

## 토픽은 "이름 + 타입"이라는 계약이다

토픽에는 스키마가 없다. 이름과 메시지 타입, 이 둘이 전부다. `/image` 라는 이름에 `sensor_msgs/msg/Image` 를 발행하는 노드와 `std_msgs/msg/String` 을 기대하는 구독 노드는 **같은 이름을 썼다는 이유만으로 절대 연결되지 않는다.** DDS가 타입이 다른 발행자-구독자 쌍을 애초에 매칭시키지 않기 때문이다. 실행 중에 `ros2 topic list -t` 로 이름과 타입을 함께 확인하는 습관을 들여라.

```text nolines
$ ros2 topic list -t
/image [sensor_msgs/msg/Image]
/cmd_vel [geometry_msgs/msg/Twist]
```

::: warn 흔한 실전 함정: 이름은 맞는데 타입이 다르다
런치 파일을 리팩터링하다가 한쪽만 `Image`에서 `CompressedImage`로 바꾸는 실수가 실전에서 자주 일어난다. `ros2 node info`나 `ros2 topic info`로 보면 발행자·구독자 수는 잡히는데 메시지가 하나도 안 온다 — 왜냐면 애초에 매칭이 안 됐기 때문이다. "노드는 떠 있는데 데이터가 안 온다"는 증상을 보면 QoS 불일치([10.8](#/qos))와 함께 **타입 불일치부터 의심하라.**
:::

## 표준 메시지: 바퀴를 다시 만들지 마라

로봇 커뮤니티가 이미 20년 가까이 쓴 메시지 타입이 있다. 커스텀 메시지를 만들기 전에 먼저 이 세 패키지부터 뒤져라.

| 패키지 | 대표 타입 | 쓰임 |
| --- | --- | --- |
| `std_msgs` | `String`, `Int32`, `Float64`, `Bool`, `Header` | 원시 타입 하나를 그냥 보낼 때 |
| `geometry_msgs` | `Twist`, `Pose`, `Point`, `Vector3`, `PoseStamped` | 속도, 위치, 자세 — 로봇 상태의 대부분 |
| `sensor_msgs` | `Image`, `LaserScan`, `Imu`, `PointCloud2`, `JointState` | 센서 원시 데이터 |

`std_msgs`는 사실 잘 안 쓴다. `Header`를 제외하면 대부분 이름 정보가 없는 순수 원시값이라("이 `Float64`가 대체 뭘 뜻하는지" 코드를 봐야 안다), 실무에서는 의미가 붙은 `geometry_msgs`/`sensor_msgs` 쪽을 훨씬 많이 쓴다. 이동 로봇의 속도 명령이 표준 예다.

```python title="cmd_vel 발행 — geometry_msgs/Twist"
from geometry_msgs.msg import Twist

def stop_and_turn(self):
    msg = Twist()
    msg.linear.x = 0.0
    msg.angular.z = 0.5          # rad/s, 제자리 회전
    self.cmd_vel_pub.publish(msg)
```

`Twist`는 `linear`(Vector3)와 `angular`(Vector3) 두 필드만 가진 아주 단순한 메시지다. rclpy 안에서는 그냥 파이썬 객체라서, 필드에 값을 넣는 건 평범한 속성 대입이다. **평범한 속성 대입이라는 것이 이 절 뒤쪽 함정의 근원이다.**

## 커스텀 메시지: `.msg` 정의하기

표준 메시지로 표현이 안 되면 직접 만든다. `.msg` 파일은 자료구조 정의고, `rosidl` 빌드 도구가 이걸 파이썬 클래스와 C++ 클래스로 동시에 코드 생성한다.

```text nolines
tutorial_interfaces/
├── msg/
│   ├── Num.msg
│   └── Sphere.msg
├── CMakeLists.txt
└── package.xml
```

```text title="msg/Num.msg" nolines
int64 num
```

```text title="msg/Sphere.msg" nolines
geometry_msgs/Point center
float64 radius
```

`Sphere.msg`가 보여주듯, **다른 패키지의 메시지를 필드 타입으로 그대로 참조**할 수 있다. `package_name/TypeName` 형식이다. 두 파일 다 필드 타입과 이름을 한 줄에 하나씩 쓰는 것뿐이다.

빌드 설정은 `package.xml`과 `CMakeLists.txt` 양쪽에 필요하다.

```xml title="package.xml (발췌)"
<depend>geometry_msgs</depend>
<buildtool_depend>rosidl_default_generators</buildtool_depend>
<exec_depend>rosidl_default_runtime</exec_depend>
<member_of_group>rosidl_interface_packages</member_of_group>
```

```cmake title="CMakeLists.txt (발췌)"
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Num.msg"
  "msg/Sphere.msg"
  DEPENDENCIES geometry_msgs
)
```

([`Custom-ROS2-Interfaces`, ROS 2 문서 rolling/jazzy 브랜치](https://github.com/ros2/ros2_documentation/blob/rolling/source/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.rst) 기준으로 파일 내용·매니페스트 항목 대조 완료.) `colcon build`([10.2](#/ros-workspace))가 이 정의를 파이썬 모듈로 코드 생성한다. 빌드가 끝나면 평범한 import처럼 쓴다.

```python title="생성된 메시지 사용"
from tutorial_interfaces.msg import Num

msg = Num()
msg.num = 42
self.publisher_.publish(msg)
```

::: tip 커스텀 메시지는 반드시 별도 패키지에
`.msg`를 정의하는 패키지와 그것을 쓰는 노드 패키지를 분리하는 게 관례다. 같은 패키지 안에 두면 빌드 순서 문제(코드 생성 전에 노드 코드가 컴파일되려는 경합)가 생기기 쉽다. 정말 한 패키지로 끝내야 하면 `Single-Package-Define-And-Use-Interface` 방식이 따로 있지만, 실전에서는 대부분 인터페이스 패키지를 분리한다.
:::

## 콜백은 언제, 어떤 스레드에서 실행되는가

`rclpy.spin(node)`를 부르는 순간부터 콜백이 실행된다. 그런데 정확히 언제, 어느 스레드에서 실행되는지는 `Node`가 아니라 **executor**가 정한다. 기본 executor(`SingleThreadedExecutor`)는 큐에 쌓인 콜백을 **하나씩, 한 스레드에서** 순서대로 처리한다.

이게 뜻하는 바는 이렇다. 구독 콜백 안에서 무거운 연산을 돌리면 — 예를 들어 이미지 콜백 안에서 딥러닝 추론을 동기로 돌리면 — **그 시간 동안 같은 노드의 다른 모든 콜백(타이머, 다른 토픽 구독)이 멈춘다.** 이건 [4.6 asyncio 기초](#/asyncio-basics)에서 본 "이벤트 루프를 블로킹하면 안 된다"는 규칙과 정확히 같은 모양의 문제다. 이벤트 루프가 executor로, `await`가 `spin`으로 바뀌었을 뿐이다.

::: warn 콜백 안에서 `time.sleep`을 쓰지 마라
```python
def image_callback(self, msg):
    result = self.run_heavy_inference(msg)   # 200ms 걸린다고 하자
    self.publish_result(result)
```

이 콜백이 도는 200ms 동안 같은 노드의 다른 콜백은 전부 대기열에서 기다린다. 타이머 기반 하트비트 발행이 있다면 그 주기도 밀린다. 해법은 두 가지다. `MultiThreadedExecutor`로 콜백을 여러 스레드에 분산하거나(이때 [4.2 threading과 동기화](#/threading)의 Lock 규칙이 그대로 적용된다 — 공유 상태에 손을 대면 경쟁 상태가 생긴다), 무거운 작업을 별도 프로세스([4.4 multiprocessing](#/multiprocessing))로 떼어낸다. 콜백 그룹(callback group)으로 어떤 콜백이 병렬로 돌아도 되는지 지정하는 세부 내용은 [10.3 rclpy 노드](#/rclpy-node)에서 다룬다.
:::

## QoS 기본값: 안 보이는 계약

`create_publisher(String, 'topic', 10)`에서 정수 `10`을 넘겼다. 이게 QoS 프로파일 전체를 대신하는 축약형이다. 정수만 넘기면 rclpy는 다음 기본값으로 프로파일을 채운다. (ROS 2 공식 문서 [`About-Quality-of-Service-Settings`](https://github.com/ros2/ros2_documentation/blob/rolling/source/Concepts/About-Quality-of-Service-Settings.rst) 기준 대조.)

| 정책 | 기본값 | 의미 |
| --- | --- | --- |
| History | Keep last | 큐에 최근 N개만 보관 |
| Depth | 넘긴 정수(예: 10) | 큐 길이 |
| Reliability | Reliable | 유실 시 재전송 시도 |
| Durability | Volatile | 늦게 구독해도 과거 메시지 안 줌 |

**Reliable + Volatile**이 일반 토픽의 기본값이다. TCP와 비슷하게 순서를 보장하고 재전송하지만, 구독자가 늦게 붙으면 그 이전 메시지는 영영 못 받는다. 카메라나 라이다처럼 다음 프레임이 금방 또 오는 센서는 유실 하나쯤 재전송받으려 애쓰는 것보다 **최신 프레임을 놓치지 않는 게** 낫다. 그래서 센서 데이터에는 별도의 프리셋(`qos_profile_sensor_data`: Best Effort + Depth 5)을 쓰라고 권장한다.

::: danger 흔한 사고: 발행자와 구독자의 QoS가 안 맞으면 조용히 실패한다
Reliable 구독자가 Best Effort 발행자를 구독하려 하면 — 혹은 그 반대면 — **에러 메시지 없이 그냥 연결되지 않는다.** `ros2 topic list`에는 둘 다 나오고, `ros2 topic info`로 봐도 발행자·구독자 수는 맞게 잡히는데, 메시지가 하나도 전달되지 않는다. 이 절 앞에서 본 "타입은 맞는데 QoS가 안 맞는" 경우가 실전에서 가장 진단하기 짜증나는 버그 중 하나다. 원리와 호환 규칙은 [10.8 QoS와 DDS](#/qos)에서 표로 정리한다.
:::

## 대용량 메시지 성능: 이미지가 파이프라인을 무너뜨리는 법

여기서부터는 순수 파이썬 계산으로 실제 비용을 확인할 수 있다. `sensor_msgs/msg/Image`는 `height`, `width`, `encoding`, `step`(한 행의 바이트 수), `data`(`uint8[]`) 필드를 가진다. `step`과 전체 바이트 수는 해상도와 인코딩만으로 정확히 계산된다.

```python title="image_bandwidth.py — 실행 결과"
def image_bytes(width, height, channels=3, bytes_per_channel=1):
    step = width * channels * bytes_per_channel
    return step, step * height


configs = [
    ("VGA 640x480 rgb8", 640, 480, 3, 1),
    ("HD 1280x720 rgb8", 1280, 720, 3, 1),
    ("FHD 1920x1080 rgb8", 1920, 1080, 3, 1),
    ("FHD 뎁스 1920x1080 32FC1", 1920, 1080, 1, 4),
]

for name, w, h, c, b in configs:
    step, total = image_bytes(w, h, c, b)
    for fps in (10, 30):
        mbps = total * fps / 1_000_000
        print(f"{name:24s} frame={total/1_000_000:5.2f}MB  {fps:2d}fps -> {mbps:7.1f} MB/s")
```

```text nolines
VGA 640x480 rgb8         frame= 0.92MB  10fps ->     9.2 MB/s
VGA 640x480 rgb8         frame= 0.92MB  30fps ->    27.6 MB/s
HD 1280x720 rgb8         frame= 2.76MB  10fps ->    27.6 MB/s
HD 1280x720 rgb8         frame= 2.76MB  30fps ->    82.9 MB/s
FHD 1920x1080 rgb8       frame= 6.22MB  10fps ->    62.2 MB/s
FHD 1920x1080 rgb8       frame= 6.22MB  30fps ->   186.6 MB/s
FHD 뎁스 1920x1080 32FC1  frame= 8.29MB  10fps ->    82.9 MB/s
FHD 뎁스 1920x1080 32FC1  frame= 8.29MB  30fps ->   248.8 MB/s
```

(Python 3.14.5 기준 실행. 계산값이라 기기 무관하게 동일하다.) FHD 컬러 30fps 하나만 해도 **초당 187MB**다. 로컬 프로세스 간이면 공유 메모리 전송(intra-process 또는 SHM 기반 DDS)이 이 정도는 버티지만, 네트워크를 타는 순간 기가비트 이더넷 이론 대역폭(약 125MB/s)조차 위협한다. 카메라 토픽 하나 때문에 다른 토픽까지 밀리는 사고가 여기서 시작된다.

::: perf 배열 필드의 실제 표현: array.array가 항상 이기지 않는다
`rosidl_generator_py`는 메시지의 가변 길이 숫자 배열 필드(`LaserScan.ranges` 같은)를 파이썬 `list`가 아니라 **`array.array`**로 표현한다. 고정 길이 배열은 `numpy.ndarray`로 표현된다. 이유는 메모리다 — `array.array`는 C 배열처럼 값을 그대로 저장하고, 파이썬 `list`는 각 원소를 별개의 boxed 객체로 저장해 포인터만 늘어놓는다([1.3 시퀀스](#/sequences)에서 다룬 구조 그대로).

길이 1080짜리(`LaserScan.ranges` 전형적인 크기)에서 실제로 재보자.

```python
import sys, array
import numpy as np

n = 1080
data = [0.5] * n
lst = list(data)
arr = array.array('d', data)
npa = np.array(data, dtype=np.float64)

print(sys.getsizeof(lst) + sum(sys.getsizeof(x) for x in lst))  # list, 원소 포함
print(sys.getsizeof(arr))
print(npa.nbytes + (sys.getsizeof(npa) - npa.nbytes))            # 데이터 + 헤더
```

```text nolines
34616   # list — 원소 하나하나가 float 객체
 8720   # array.array
 8752   # numpy — 데이터 8640 + 헤더 112
```

리스트가 **4배 가까이 크다.** 원소 개수만큼 개별 `float` 객체를 만들고 포인터로 늘어놓기 때문이다([1.2 숫자](#/numbers)). 그런데 매 콜백마다 **새로 만드는 비용**은 반대다.

```python
import timeit, array
n = 1080
data = [0.5] * n

timeit.timeit(lambda: list(data), number=100_000)                 # list
timeit.timeit(lambda: array.array('d', data), number=100_000)     # array.array
```

실측(Python 3.14.5, 이 문서를 쓴 기기): `list(data)` 0.092초, `array.array('d', data)` 0.903초, `np.array(data)` 1.767초 — **list가 array.array보다 약 10배, numpy보다 약 19배 빠르게 만들어진다.** 절대 초 값과 배율은 CPU·파이썬 빌드·numpy 버전에 따라 달라지니 그대로 믿지 말고 네가 쓸 기기에서 재실행해서 확인해라(위 코드 그대로 복붙하면 된다) — 다만 "list가 array.array보다, array.array가 numpy보다 항상 빠르다"는 순서 자체는 여러 기기에서 일관되게 재현된다. 타입 변환·값 검사 오버헤드가 매번 붙기 때문이다. 즉 **저장할 때는 array/numpy가 작고, 매번 새로 만들 때는 list가 싸다.** 20Hz로 도는 라이다 콜백에서 매번 파이썬 `list`로 받은 뒤 필요할 때만 `np.asarray()`로 벡터 연산 구간에 진입하는 게 실전에서 흔한 절충이다. [9.1 ndarray](#/numpy-basics)에서 본 뷰 변환은 대개 복사 없이 일어난다.
:::

::: note "제로카피"는 있지만 rclpy에는 없다
DDS 미들웨어(Fast DDS, Cyclone DDS)는 같은 머신 안에서 공유 메모리 전송을 지원하고, `borrow_loaned_message()`로 발행자가 메시지를 아예 복사 없이 미들웨어 버퍼에 직접 쓰는 "loaned message" API도 있다. 그런데 **이 API는 rclcpp에만 노출돼 있고, 이 절 집필 시점 rclpy에는 대응하는 공개 API가 없다.** 그러니 파이썬 노드에서 이미지 파이프라인의 마지막 한 방울까지 쥐어짜야 한다면, 결국 [10.16 다음 단계: rclcpp로](#/ros-next)에서 다루는 이유로 넘어가게 된다.
:::

## 실전 함정: 메시지도 결국 파이썬 객체다

`Twist()`나 `Image()`는 그냥 파이썬 클래스 인스턴스다. [1.1 객체, 이름, 참조](#/objects-names)에서 배운 규칙이 하나도 빠짐없이 적용된다.

```python title="함정 — 메시지 객체를 재사용하며 공유 버퍼를 참조"
class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.buf = bytearray(1920 * 1080 * 3)   # 카메라 드라이버가 매 프레임 덮어쓰는 버퍼
        self.pub = self.create_publisher(Image, 'image_raw', 10)

    def frame_callback(self, raw_frame):
        msg = Image()
        msg.data = self.buf          # ❌ 복사가 아니라 참조를 붙였다
        self.pub.publish(msg)
```

`msg.data = self.buf`는 대입이지 복사가 아니다. `publish()` 호출 시점에 rclpy가 메시지를 즉시 직렬화하므로 대부분은 문제없이 지나간다. 문제는 **드라이버 콜백이 다른 스레드에서 `self.buf`를 계속 덮어쓸 때**다. `MultiThreadedExecutor`를 쓰거나 드라이버가 별도 스레드에서 콜백을 부르는 구성이라면, 직렬화가 끝나기 전에 다음 프레임이 같은 버퍼에 쓰이기 시작할 수 있다 — 화면이 반쯤 섞인 프레임으로 도착하는, 재현하기 지독히 어려운 버그다. 안전한 버전은 [1.1](#/objects-names)에서 배운 대로 **경계에서 복사**한다.

```python title="고친 버전 — 경계에서 명시적으로 복사"
def frame_callback(self, raw_frame):
    msg = Image()
    msg.data = bytes(self.buf)      # ✅ 새 불변 bytes 객체로 복사
    self.pub.publish(msg)
```

`bytearray` 대신 `bytes`로 감싸는 것 자체가 복사([1.5 bytes, bytearray, memoryview](#/bytes))이자 동시에 "이 이후로는 아무도 못 바꾼다"는 보장이 된다. 멀티스레드 콜백이 얽힌 노드에서 이 패턴을 습관으로 만들어라.

## 요약

- 발행-구독은 발행자와 구독자를 서로 모르게 만들어 N:M 통신과 언어 간 결합 해제를 가능하게 한다. 대가는 전달 보장이 약해진다는 것이다.
- 토픽은 "이름 + 타입"이 전부인 계약이다. 타입이 다르면 이름이 같아도 절대 연결되지 않는다.
- `std_msgs`보다 의미가 담긴 `geometry_msgs`/`sensor_msgs`를 우선 쓰고, 그래도 안 되면 `.msg`로 직접 정의한다.
- 콜백은 executor가 스케줄링한다. 콜백 안에서 무거운 작업을 동기로 돌리면 같은 노드의 다른 콜백이 전부 멈춘다.
- QoS 기본값은 Reliable + Volatile + Depth 10이다. 센서 데이터는 Best Effort 프리셋을 우선 검토한다. QoS 불일치는 에러 없이 조용히 실패한다.
- 이미지 같은 대용량 메시지는 대역폭을 숫자로 따져야 한다 — FHD 컬러 30fps는 초당 187MB다.
- 가변 길이 숫자 배열 필드는 `array.array`로 표현된다. 저장은 `list`보다 작지만 매번 새로 만드는 비용은 더 크다.
- 메시지는 평범한 파이썬 객체다. 공유 가변 버퍼를 그대로 대입하지 말고 경계에서 복사하라.

::: quiz 연습문제
1. `image_bytes()` 함수를 확장해서 `sensor_msgs/msg/PointCloud2`처럼 포인트당 바이트 수(`point_step`)와 포인트 개수를 받아 전체 바이트 수를 계산하는 함수를 짜라. XYZ(float32 3개) + intensity(float32)를 담는 포인트 클라우드가 초당 10만 포인트씩, 10Hz로 들어온다면 초당 몇 MB인가?
2. 발행자가 `qos_profile_sensor_data`(Best Effort)를 쓰고 구독자가 기본 프로파일(Reliable)을 쓰면 어떤 일이 벌어지는가? 반대의 경우는? [10.8](#/qos)을 읽기 전에 먼저 추론해 보라.
3. 아래 코드는 `msg.data = self.buf` 패턴의 변형이다. 무엇이 위험한지, 언제는 안전하고 언제는 안전하지 않은지 설명하라.

   ```python
   def frame_callback(self, raw_frame):
       self.buf[:] = raw_frame     # 버퍼 내용을 제자리에서 갱신
       msg = Image()
       msg.data = self.buf
       self.pub.publish(msg)
   ```

4. `create_publisher(String, 'topic', 10)`에서 정수 `10` 대신 `rclpy.qos.QoSProfile` 객체를 직접 넘기면 어떤 정책들을 개별적으로 조정할 수 있을지, 이 절에서 나온 표를 보고 필드 이름을 추측해 나열하라.
:::

**다음 절**: [10.5 서비스](#/services) — 발행-구독으로 안 되는 것: 요청을 보내고 응답을 기다려야 하는 상황.
