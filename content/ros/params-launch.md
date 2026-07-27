# 10.7 파라미터와 launch

::: lead
[10.3 rclpy 노드](#/rclpy-node)에서 만든 노드는 지금까지 `max_speed = 1.5` 처럼 값을 코드 안에 박아 넣었다. 시뮬레이터에서는 그 속도가 맞아도 실제 로봇에서는 위험할 수 있고, 로봇 A와 로봇 B의 바퀴 반지름이 다를 수도 있다. 그때마다 소스를 고치고 다시 빌드할 것인가? ROS 2는 이 문제를 **파라미터**(설정값을 노드 밖에서 주입하는 장치)와 **launch**(여러 노드와 그 설정을 한 번에 기술하고 실행하는 파이썬 프로그램)로 푼다. 이 절이 특별한 이유는, launch 파일이 곧 **파이썬 코드**라는 데 있다 — [1.10 함수](#/functions)와 [4.4 multiprocessing](#/multiprocessing)에서 배운 것이 여기서 그대로 다시 쓰인다.
:::

## 하드코딩을 걷어내야 하는 이유

노드 코드 안에 상수를 박아 두면 생기는 문제는 뻔하다. 시뮬레이터용 값과 실제 로봇용 값이 다르고, 로봇마다 하드웨어 스펙이 다르고, 배포 환경(연구실 vs 필드)마다 로그 레벨이나 토픽 이름을 바꾸고 싶다. 이 모든 것을 조건 분기로 처리하면 코드는 금방 `if is_simulation: ... elif is_robot_a: ...` 로 뒤덮인다.

ROS 2의 답은 **설정과 로직을 분리**하는 것이다. 노드는 "나는 `max_speed` 라는 설정값이 필요하다"고 선언만 하고, 그 값이 시뮬레이터 YAML에서 오는지, 실제 로봇 launch 인자에서 오는지, `ros2 run` 커맨드라인에서 오는지는 신경 쓰지 않는다. 이 구조는 [2.7 pydantic](#/pydantic)의 `Settings` 클래스가 환경 변수·`.env` 파일·기본값 중 어디서 값이 왔는지 신경 쓰지 않는 것과 정확히 같은 발상이다.

## declare_parameter 와 get_parameter — 선언이 곧 타입을 고정한다

rclpy에서 파라미터를 쓰려면 반드시 두 단계를 거친다. **선언**하고, 그다음에 **읽는다**. 순서를 지키지 않으면 예외가 난다.

```python title="선언하지 않고 읽으면 나는 예외"
import rclpy
from rclpy.node import Node


class MinimalParam(Node):
    def __init__(self):
        super().__init__("minimal_param_node")
        self.declare_parameter("my_parameter", "world")
        self.timer = self.create_timer(1.0, self.timer_callback)

    def timer_callback(self):
        value = self.get_parameter("my_parameter").get_parameter_value().string_value
        self.get_logger().info(f"Hello {value}!")
```

(공식 튜토리얼 *Using Parameters in a Class (Python)* — docs.ros.org/en/jazzy — 의 예제를 기준으로 확인한 형태다.)

`declare_parameter(name, default_value)` 를 호출하면 rclpy는 **`default_value` 의 파이썬 타입을 보고 ROS 파라미터 타입을 추론**한다. `"world"` 는 문자열 타입으로, `1.5` 는 실수(double) 타입으로 고정된다. 그리고 이 타입은 **그 노드가 살아 있는 동안 바뀌지 않는다.** 나중에 다른 타입 값으로 `set_parameters` 를 시도하면 (버전에 따라 예외 또는 실패 결과로) 거부당한다.

::: warn bool은 int의 서브클래스다 — 타입 추론 순서에 주의
[1.1 객체, 이름, 참조](#/objects-names)에서 `isinstance(True, int)` 가 `True` 라는 걸 봤다. 파라미터 타입을 추론하는 코드를 직접 짜야 한다면(또는 rclpy 내부 동작을 이해하려면) 이 순서를 지켜야 한다 — **`bool` 을 `int` 보다 먼저 검사해야 한다.** 순서를 바꾸면 `True` 가 정수 파라미터로 잘못 추론된다.
:::

이 규칙이 실제로 왜 중요한지, 순수 파이썬으로 재현해서 확인해 보자. rclpy 소스가 아니라 **타입 추론의 원리만** 뽑아낸 것이다.

```python title="param_type_demo.py — 타입 추론 순서 검증"
def infer_ros_type(value):
    # 순서가 중요하다: bool은 int의 서브클래스라서 bool을 먼저 검사해야 한다
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    raise TypeError(f"지원하지 않는 타입: {type(value)}")


print(infer_ros_type(True))
print(infer_ros_type(1))
print(isinstance(True, int))
```

```text nolines
bool
integer
True
```

(Python 3.14.5 실행 확인.) `isinstance(True, int)` 가 `True` 인데도 `infer_ros_type(True)` 가 `"integer"` 가 아니라 `"bool"` 을 반환하는 건, 검사 순서를 bool 먼저로 뒀기 때문이다. rclpy도 같은 함정을 피하려고 내부적으로 같은 순서를 지킨다.

값을 읽을 때는 `get_parameter(name)` 이 `rclpy.parameter.Parameter` 객체를 돌려준다. 여기서 실제 값을 꺼내려면 `.get_parameter_value()` 로 메시지 래퍼를 얻고, 타입에 맞는 필드(`string_value`, `integer_value`, `double_value`, `bool_value`, `*_array_value`)를 골라야 한다. 짧게 쓰고 싶으면 `.value` 프로퍼티가 타입에 맞춰 알아서 꺼내 준다.

```python title="get_parameter 두 가지 방법"
name = self.get_parameter("robot_name").value                     # 짧은 방법
speed = self.get_parameter("max_speed").get_parameter_value().double_value  # 명시적인 방법
```

여러 개를 한 번에 선언하고 싶으면 `declare_parameters` 를 쓴다.

```python
self.declare_parameters(
    namespace="",
    parameters=[
        ("max_speed", 1.5),
        ("robot_name", "turtle1"),
    ],
)
```

## 콜백으로 파라미터를 검증한다

`ros2 param set` 이나 launch 인자로 파라미터가 바뀔 때, "0보다 커야 한다" 같은 조건을 강제하고 싶을 수 있다. rclpy는 `add_on_set_parameters_callback` 으로 **값이 실제로 반영되기 직전에** 끼어들 훅을 준다.

```python title="파라미터 변경을 검증하는 콜백"
from rcl_interfaces.msg import SetParametersResult


class SpeedLimiter(Node):
    def __init__(self):
        super().__init__("speed_limiter")
        self.declare_parameter("max_speed", 1.5)
        self.add_on_set_parameters_callback(self.on_parameter_change)

    def on_parameter_change(self, params):
        for p in params:
            if p.name == "max_speed" and p.value <= 0.0:
                return SetParametersResult(successful=False, reason="max_speed는 양수여야 한다")
        return SetParametersResult(successful=True)
```

콜백은 변경하려는 파라미터 목록을 받아서 `SetParametersResult(successful=..., reason=...)` 를 반환한다. `False` 를 반환하면 그 변경은 **커밋되지 않는다** — 노드 내부 상태는 그대로다. 이 구조("검사를 통과해야만 실제로 반영된다")를 순수 파이썬으로 재현해서 동작을 직접 확인할 수 있다.

```python title="param_store_demo.py — 선언·타입 고정·콜백 검증의 원리"
from dataclasses import dataclass


class ParameterNotDeclaredException(Exception):
    pass


@dataclass
class SetParametersResult:
    successful: bool
    reason: str = ""


class TinyParamStore:
    """rclpy 파라미터 서브시스템의 핵심 규칙만 뽑아낸 모형이다.
    실제 rclpy 구현이 아니라 동작 원리를 보여주기 위한 순수 파이썬 재현이다."""

    def __init__(self):
        self._values = {}
        self._types = {}
        self._callbacks = []

    def declare_parameter(self, name, default_value):
        self._values[name] = default_value
        self._types[name] = type(default_value)

    def get_parameter(self, name):
        if name not in self._values:
            raise ParameterNotDeclaredException(name)
        return self._values[name]

    def add_on_set_parameters_callback(self, callback):
        self._callbacks.append(callback)

    def set_parameters(self, updates: dict):
        for name, value in updates.items():
            if type(value) is not self._types[name]:
                return SetParametersResult(False, f"{name}: 타입 불일치")
        for callback in self._callbacks:
            result = callback(updates)
            if not result.successful:
                return result
        self._values.update(updates)
        return SetParametersResult(True)


def validate_speed(updates):
    if "max_speed" in updates and updates["max_speed"] <= 0:
        return SetParametersResult(False, "max_speed는 양수여야 한다")
    return SetParametersResult(True)


node = TinyParamStore()
node.declare_parameter("max_speed", 1.5)
node.add_on_set_parameters_callback(validate_speed)

print(node.set_parameters({"max_speed": 2.0}), node.get_parameter("max_speed"))
print(node.set_parameters({"max_speed": "fast"}))   # 타입 불일치
print(node.set_parameters({"max_speed": -1.0}))      # 콜백이 거부
```

```text nolines
SetParametersResult(successful=True, reason='') 2.0
SetParametersResult(successful=False, reason='max_speed: 타입 불일치')
SetParametersResult(successful=False, reason='max_speed는 양수여야 한다')
```

(Python 3.14.5 실행 확인.) 실제 rclpy에서는 타입 검사가 `set_parameters` 호출 전에 rcl 레이어에서 먼저 일어나고, 그다음에 사용자 콜백이 호출된다는 순서까지 이 모형과 같다. **타입이 틀리면 콜백까지 가지도 않는다** — 위 예제에서 두 번째 호출이 `validate_speed` 를 거치지 않고 곧바로 실패한 이유다.

## YAML로 설정을 코드 밖으로 꺼낸다

파라미터 값을 소스 코드가 아니라 **YAML 파일**에 적어 두면, 노드를 다시 빌드하지 않고도 설정을 바꿀 수 있다. 형식은 정해져 있다 — 노드 이름, 그 아래 `ros__parameters` 키, 그 아래 실제 값.

```yaml title="config/driver_params.yaml"
/robot1/driver:
  ros__parameters:
    max_speed: 2.0
    wheel_radius: 0.033

/robot2/driver:
  ros__parameters:
    max_speed: 1.0
    wheel_radius: 0.05

/**:
  ros__parameters:
    log_level: "info"
```

`/**` 는 **모든 노드에 적용되는 전역 설정**을 뜻하는 와일드카드다. 실무 관례는 "구체적인 이름을 가진 항목이 전역값을 덮어쓴다"는 것이고, 위 예제(`/**` 를 파일 맨 끝에 두는 관례적 배치)에서는 실제로 그렇게 동작한다. 하지만 이 규칙을 곧이곧대로 믿으면 안 된다 — rcl/rclcpp 쪽에도 와일드카드와 구체 이름 사이의 병합 순서가 항목이 **YAML에 쓰인 순서**에 좌우된다는 이슈(ros2/rclcpp#953, "Odd parameter overrides ordering when using wildcards")가 열려 있을 정도로, "이름이 구체적일수록 항상 이긴다"는 건 확정된 사양이라기보다 배포판·구현에 따라 갈릴 수 있는 지점이다. `fnmatch` 로 그 병합 로직 자체를 재현해서, 이게 "이름의 구체성"이 아니라 "등장 순서"로 결정된다는 것을 직접 확인해 보자.

```python title="yaml_param_demo.py — 와일드카드 매칭은 이름 구체성이 아니라 등장 순서로 병합된다"
import fnmatch
import yaml

raw = """
/**:
  ros__parameters:
    log_level: "info"
/robot1/driver:
  ros__parameters:
    max_speed: 2.0
    wheel_radius: 0.033
/robot2/driver:
  ros__parameters:
    max_speed: 1.0
    wheel_radius: 0.05
"""
config = yaml.safe_load(raw)


def resolve_params(fq_node_name: str, config: dict) -> dict:
    # 이 함수는 "이름이 구체적이면 이긴다"는 규칙을 구현하지 않는다.
    # config.items()를 순서대로 훑으면서 나중에 매칭된 항목으로 update()할 뿐이다.
    merged = {}
    for pattern, body in config.items():
        if fnmatch.fnmatch(fq_node_name, pattern):
            merged.update(body.get("ros__parameters", {}))
    return merged


print(resolve_params("/robot1/driver", config))
print(resolve_params("/unrelated_node", config))

# /** 를 맨 뒤로 옮기면(관례와 반대로) 어떻게 되는지 확인해 보자.
raw_reversed = """
/robot1/driver:
  ros__parameters:
    max_speed: 2.0
    wheel_radius: 0.033
/**:
  ros__parameters:
    max_speed: 99.0
    log_level: "info"
"""
config_reversed = yaml.safe_load(raw_reversed)
print(resolve_params("/robot1/driver", config_reversed))
```

```text nolines
{'log_level': 'info', 'max_speed': 2.0, 'wheel_radius': 0.033}
{'log_level': 'info'}
{'max_speed': 99.0, 'wheel_radius': 0.033, 'log_level': 'info'}
```

(PyYAML 6.0.3 / Python 3.14.5 실행 확인.) 첫 두 줄만 보면 "구체적인 이름이 이긴다"는 규칙이 맞는 것처럼 보인다. 그런데 세 번째 줄이 문제다 — `/**` 를 파일 맨 뒤로 옮겼더니 `max_speed` 가 명시적으로 `2.0` 을 준 `/robot1/driver` 값이 아니라 전역값 `99.0` 으로 덮어써졌다. `resolve_params` 는 이름의 구체성을 전혀 보지 않는다. 그냥 `config` 를 위에서 아래로 훑으면서 매칭되는 대로 `dict.update()` 를 반복할 뿐이라, **나중에 나오는 항목이 이긴다.** 앞의 두 줄이 "정답"처럼 나온 건 원본 YAML이 우연히 `/**` 를 맨 앞에 뒀기 때문이지, 이 함수가 "이름이 구체적일수록 우선한다"는 규칙을 실제로 구현해서가 아니다. 실무에서 `/**` 를 관례적으로 파일 끝에 적는 것도 이 순서 의존성을 우연히 피해 가는 배치일 뿐, ROS 2가 이름 구체성만으로 확정된 우선순위를 보장한다는 뜻은 아니다 — 위에서 언급한 rclcpp#953 이슈가 그 증거다. 결론적으로 이 절이 실행으로 확인해 주는 건 "YAML 병합은 등장 순서를 따르는 `dict.update()` 다"라는 점이고, "구체적 이름이 전역값을 이긴다"는 실무 관례는 **그 순서를 지켰을 때만** 성립하는 이차적 결과다. 실제 노드에서 이게 헷갈릴 때는 짐작하지 말고 `ros2 param dump` 로 최종 병합 결과를 직접 확인해라.

::: danger 노드 이름 오타는 아무 경고 없이 조용히 무시된다
YAML의 최상위 키가 실제 노드의 **정규화된 이름**(fully-qualified name, 네임스페이스 포함)과 한 글자라도 다르면, ROS 2는 에러를 내지 않는다. 그냥 그 파라미터를 안 읽고, 노드는 `declare_parameter` 에 준 **기본값으로 조용히 돌아간다.** 실제 로봇 위에서 "설정을 바꿨는데 왜 그대로지?"라는 질문의 절반은 이거다. `ros2 param list <노드이름>` 으로 지금 노드가 실제로 어떤 값을 들고 있는지 먼저 확인하는 습관을 들여라.
:::

`ros2 param` CLI로 실행 중인 노드의 파라미터를 직접 조회·변경할 수 있다.

```bash
ros2 param list /robot1/driver
ros2 param get /robot1/driver max_speed
ros2 param set /robot1/driver max_speed 1.8
ros2 param dump /robot1/driver          # 현재 값을 YAML 형식으로 출력
```

(이 형태는 공식 ROS 2 CLI 문서와 여러 튜토리얼에서 일관되게 확인된다. 정확한 출력 문구는 배포판마다 조금씩 다를 수 있으니 `--help` 로 그때그때 확인하라.)

## 파이썬 launch 파일 — LaunchDescription과 Node

launch 파일은 확장자만 `.launch.py` 일 뿐, **평범한 파이썬 모듈**이다. 딱 하나, `generate_launch_description()` 이라는 이름의 함수를 정의해야 한다는 규칙만 있다. `ros2 launch` 는 이 함수를 호출해서 반환된 `LaunchDescription` 객체를 실행한다.

```python title="minimal.launch.py"
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="turtlesim",
            executable="turtlesim_node",
            name="sim",
            output="screen",
        ),
    ])
```

```bash
ros2 launch my_package minimal.launch.py
```

`Node(...)` 는 노드를 **직접 실행하는 게 아니라, "이런 프로세스를 띄워라"는 명세**다. `package` 와 `executable` 로 어떤 프로그램을 실행할지 지정하고, `name` 으로 실행 시점의 노드 이름을 덮어쓸 수 있고(`ros2 run` 커맨드라인 인자 없이도), `parameters` 로 앞서 만든 YAML 경로나 딕셔너리를 넘긴다.

::: deep launch 파일 하나 = 프로세스 여러 개
여기서 [4.4 multiprocessing](#/multiprocessing)과 [4.3 GIL](#/gil)에서 배운 것이 그대로 돌아온다. `LaunchDescription` 안의 `Node` 액션 하나하나는 **완전히 독립된 OS 프로세스**로 실행된다. 파이썬 노드 셋을 launch로 띄우면, GIL을 공유하지도 않고 메모리도 공유하지 않는 별개의 인터프리터 셋이 뜨는 것과 같다. 노드끼리 데이터를 주고받는 유일한 통로는 [10.4 토픽](#/topics)·[10.5 서비스](#/services)의 DDS 통신뿐이다 — 프로세스 안의 파이썬 객체를 직접 넘길 방법은 없다.

`launch` 패키지 자체는 내부적으로 자체 이벤트 루프로 여러 프로세스의 시작·종료·출력을 비동기적으로 조율한다. [4.6 asyncio 기초](#/asyncio-basics)에서 본 "이벤트 루프가 여러 작업을 하나의 스레드에서 관리한다"는 그림이 여기서도 그대로 유효하다 — 다만 관리 대상이 코루틴이 아니라 **자식 프로세스**라는 점이 다르다.
:::

## 여러 노드를 한 번에 띄우기

launch의 진짜 힘은 노드 하나가 아니라 **시스템 전체**를 한 파일로 기술하는 데서 나온다. 실제 로봇은 드라이버, 센서 퍼블리셔, 상태 추정, 컨트롤러 같은 노드 여러 개가 동시에 필요하다.

```python title="bringup.launch.py — 여러 노드 + YAML 설정"
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory("my_robot_bringup"),
        "config",
        "driver_params.yaml",
    )

    driver_node = Node(
        package="my_robot_driver",
        executable="driver_node",
        name="driver",
        parameters=[config],
        output="screen",
    )

    state_estimator = Node(
        package="my_robot_estimation",
        executable="estimator_node",
        name="estimator",
        parameters=[{"use_sim_time": False}],
    )

    return LaunchDescription([driver_node, state_estimator])
```

`get_package_share_directory` 는 [10.2 워크스페이스, 패키지, colcon](#/ros-workspace)에서 다룬 설치 구조와 맞물린다. `config/driver_params.yaml` 이 실제로 이 경로에서 찾아지려면, 빌드 타입에 맞게 `config/` 와 `launch/` 디렉터리를 **설치 대상으로 등록**해 둬야 한다. 등록 방식은 패키지 빌드 타입에 따라 다르다.

- **ament_python** 패키지(이 절 예제처럼 launch/노드가 순수 파이썬인 경우 보통 이쪽): `setup.py` 의 `data_files` 에 `config/` 와 `launch/` 를 나열한다.
- **ament_cmake** 패키지: `setup.py` 자체가 없고, 대신 `CMakeLists.txt` 에 `install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})` 구문으로 같은 일을 한다.

둘 다 핵심은 같다 — 소스 트리의 파일 위치가 아니라 **설치된 `share/<패키지명>/` 아래**에서 파일을 찾는다는 것. 이 등록을 빼먹으면 소스 트리에는 파일이 멀쩡히 있는데도 `colcon build` 이후 `ros2 launch` 가 그 파일을 못 찾는, 아주 흔하고 아주 헷갈리는 실패가 난다.

`parameters` 리스트에는 YAML 파일 경로뿐 아니라 파이썬 딕셔너리도 섞어 넣을 수 있다. 뒤에 오는 항목이 앞의 항목을 덮어쓴다 — [1.6 dict](#/dict)에서 본 병합 규칙과 같다.

```text nolines
ros2 launch my_robot_bringup bringup.launch.py
        │
        ├─▶ driver 노드     (별도 프로세스, PID 예: 20481)
        └─▶ estimator 노드  (별도 프로세스, PID 예: 20482)
```

## launch 인자로 재사용 가능한 launch 만들기

같은 launch 파일을 시뮬레이터에도, 실제 로봇에도 쓰고 싶다면 값을 하드코딩하지 말고 **launch 인자**로 받아야 한다. `DeclareLaunchArgument` 로 선언하고 `LaunchConfiguration` 으로 그 값을 참조한다.

```python title="configurable.launch.py — 재사용 가능한 launch"
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="true면 /clock 토픽 기준 시간을 쓴다 (시뮬레이터용)",
    )

    driver_node = Node(
        package="my_robot_driver",
        executable="driver_node",
        name="driver",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    return LaunchDescription([use_sim_time_arg, driver_node])
```

```bash
# 기본값(false)으로 실행
ros2 launch my_robot_bringup configurable.launch.py

# 인자를 덮어쓴다 — 커맨드라인에서 key:=value 형식
ros2 launch my_robot_bringup configurable.launch.py use_sim_time:=true
```

`LaunchConfiguration("use_sim_time")` 은 그 자체로 값이 아니라 **지연 평가되는 자리표시자**(substitution)다. launch가 실제로 이 트리를 실행하는 시점에야 문자열로 치환된다. 이건 [1.18 이터레이터와 제너레이터](#/iterators)에서 본 "제너레이터는 만들 때가 아니라 소비될 때 계산한다"는 지연 평가 발상과 결이 같다 — launch 파일을 실행해도 즉시 로봇이 움직이는 게 아니라, **어떻게 실행할지에 대한 계획(그래프)만 먼저 만들어지고**, `ros2 launch` 가 그 계획을 실제로 밟아 나간다.

### 다른 launch 파일 안에 포함하기

큰 시스템에서는 launch 파일도 계층으로 나눈다. `IncludeLaunchDescription` 으로 다른 패키지의 launch 파일을 통째로 가져와 쓸 수 있다.

```python title="full_system.launch.py — launch 파일 조합"
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("my_robot_bringup"),
                "launch",
                "bringup.launch.py",
            )
        )
    )

    return LaunchDescription([bringup_launch])
```

Nav2([10.13 Nav2 자율주행](#/nav2))나 MoveIt 2([10.14 MoveIt 2 매니퓰레이션](#/moveit)) 같은 대규모 스택을 실제로 열어 보면, 최상위 launch 파일 하나가 `IncludeLaunchDescription` 을 수십 번 호출해서 하위 launch 파일들을 엮어 놓은 구조를 보게 된다. 이 절에서 본 세 가지 조각 — `Node`, `DeclareLaunchArgument`/`LaunchConfiguration`, `IncludeLaunchDescription` — 이 전부다. 나머지는 규모의 문제일 뿐이다.

## 실전 감각: 왜 launch 디버깅이 유독 괴로운가

파라미터·launch 관련 버그가 유독 잡기 힘든 이유는 [10.15 rosbag, 디버깅, 성능](#/ros-debug)에서 다룰 문제의 축소판이다.

- **에러가 조용하다.** YAML 노드 이름 오타, 잘못된 `data_files` 등록, 타입이 안 맞는 파라미터 대부분이 예외를 던지지 않고 "그냥 기본값을 쓴다"로 끝난다. 콘솔에 빨간 글씨가 없다고 설정이 먹혔다는 뜻이 아니다.
- **각 노드가 별도 프로세스다.** `pdb` 로 브레이크포인트를 걸어도 그 프로세스만 멈춘다. 여러 노드가 얽힌 문제(파라미터가 A 노드에서는 맞는데 B 노드에서 이상하다)는 노드마다 따로 붙어서 봐야 한다 — [4.2 threading](#/threading)의 락 경합 디버깅보다 오히려 프로세스 경계가 있어서 **개별적으로는 쉽지만 전체 그림을 맞추기는 더 어렵다.**
- **launch 자체의 에러 메시지는 파이썬 트레이스백을 그대로 노출한다.** `generate_launch_description()` 안에서 흔한 실수(리스트에 `Node` 객체 대신 함수를 담아 버리는 것, 오타로 없는 패키지를 `get_package_share_directory` 에 넘기는 것)는 `PackageNotFoundError` 같은 익숙한 파이썬 예외로 나타난다. launch도 결국 파이썬 코드라는 걸 기억하면 이 트레이스백이 낯설지 않다.
- **로그는 콘솔에서 사라져도 디스크에는 남는다.** 기본적으로 `~/.ros/log/` 아래에 실행마다 타임스탬프가 붙은 디렉터리가 생기고, 노드별 stdout/stderr가 그 안에 그대로 쌓인다. 터미널을 이미 닫아 버렸어도 여기를 뒤지면 된다.

::: cote 이분 탐색과 launch 디버깅
노드가 10개 넘게 얽힌 launch에서 "어느 노드의 어느 파라미터가 문제인가"를 하나씩 껐다 켰다 하며 찾는 건 사실상 [7.5 이분 탐색](#/binary-search)이다. `LaunchDescription` 에 넣는 액션 리스트를 반씩 잘라 가며 재현되는지 확인하면, 노드를 하나씩 지우는 $O(n)$ 대신 $O(\log n)$ 번 만에 범인을 좁힐 수 있다.
:::

## 요약

- `declare_parameter(name, default)` 는 필수다. 선언 안 된 파라미터를 읽으면 예외가 난다.
- 파라미터 타입은 **기본값의 파이썬 타입에서 추론되고, 선언 후 고정**된다. `bool` 은 `int` 의 서브클래스라 추론 순서에 주의해야 한다.
- `add_on_set_parameters_callback` 으로 값이 실제로 반영되기 전에 검증할 수 있다. `SetParametersResult(successful=False)` 를 반환하면 변경이 취소된다.
- YAML 파라미터 파일은 `노드이름: ros__parameters: ...` 구조다. `/**` 는 모든 노드에 적용되는 전역 설정이고, 관례상 구체적인 이름을 가진 항목이 이를 덮어쓰도록 배치하지만 실제 병합은 YAML에 **등장한 순서**를 따르는 `dict.update()` 이므로 이름 구체성만으로 우선순위가 보장되는 건 아니다. **노드 이름이 한 글자라도 틀리면 조용히 무시된다.**
- launch 파일은 `generate_launch_description()` 을 정의하는 평범한 파이썬 모듈이다. `Node` 액션 하나가 **독립된 OS 프로세스** 하나에 대응한다.
- `DeclareLaunchArgument` + `LaunchConfiguration` 으로 같은 launch 파일을 여러 상황(시뮬레이터/실기, 로봇 A/B)에 재사용한다.
- `IncludeLaunchDescription` 으로 launch 파일을 계층적으로 조합한다. Nav2·MoveIt 2 같은 대규모 스택도 결국 이 조합이다.

::: quiz 연습문제
1. `declare_parameter("count", 0)` 으로 선언한 파라미터에 `ros2 param set` 으로 `3.5` 를 넣으려 하면 어떤 일이 벌어지는지, 그리고 왜 그런지 설명하라.
2. 아래 YAML에서 `/robot/camera` 노드가 실제로 받는 파라미터 값을 전부 적어라.

   ```yaml
   /**:
     ros__parameters:
       fps: 30
   /robot/camera:
     ros__parameters:
       fps: 60
       resolution: "1080p"
   ```

3. `param_store_demo.py` 의 `TinyParamStore.set_parameters` 에서, 타입 검사와 콜백 검증의 순서를 바꾸면(콜백을 먼저 실행하면) 어떤 문제가 생길 수 있을지 생각해 보라. 실제로 순서를 바꿔서 실행하고 확인하라.
4. `Node` 액션 여러 개를 하나의 `LaunchDescription` 에 넣어 띄웠을 때, 그 노드들이 서로 파이썬 전역 변수를 공유하지 못하는 이유를 [4.4 multiprocessing](#/multiprocessing)의 개념으로 설명하라.
5. `IncludeLaunchDescription` 으로 포함한 하위 launch 파일에 `DeclareLaunchArgument` 로 선언된 인자가 있다면, 상위 launch 파일에서 그 값을 어떻게 넘겨줄 수 있을지 공식 문서를 찾아 조사하라. (힌트: `launch_arguments` 키워드 인자)
:::

**다음 절**: [10.8 QoS와 DDS](#/qos) — 왜 어떤 토픽은 완벽하게 통신되고 어떤 토픽은 아무 이유 없이 메시지가 끊기는가, 그 답은 파라미터가 아니라 통신 계층의 설정에 있다.
