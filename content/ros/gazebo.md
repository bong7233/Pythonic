# 10.11 Gazebo 시뮬레이션

::: lead
[10.10 URDF](#/urdf)에서 로봇의 뼈대를 만들었다. 그런데 그 URDF를 실제 로봇에 바로 올려서 첫 테스트를 하는 회사는 없다. 모터 배선이 잘못돼도, 제어 게인이 잘못돼도, 코드가 무한 루프에 빠져도 — 실물 로봇은 그 대가를 팔이 부러지거나 배터리가 타는 것으로 치른다. Gazebo(정확히는 지금의 Gazebo Sim, 옛 이름 Ignition)는 물리 엔진과 센서 모델을 붙여서 그 URDF를 **가짜 세계 안에서** 움직여 본다. 이 절은 월드 파일이 어떻게 세계를 기술하는지, URDF에 무엇을 더 붙여야 시뮬레이터가 그것을 로봇으로 인식하는지, 그리고 `ros2_control`이 왜 시뮬레이션과 실물 사이의 이음매 역할을 하는지를 본다. 마지막은 이 절에서 가장 정직해야 하는 부분이다 — 시뮬레이션에서 완벽하게 도는 코드가 실물에서 왜 그대로 통하지 않는가.
:::

## 왜 시뮬레이션인가

[10.1 ROS 2 개요](#/ros-intro)에서 ROS 2가 여러 노드가 토픽·서비스·액션으로 통신하는 분산 시스템이라고 배웠다. 그 노드들을 처음 짜고 고치는 단계에서 매번 실물 로봇을 켜야 한다면 개발 속도는 바닥을 친다. 이유는 단순하다.

- **위험하다.** 잘못된 속도 명령 하나가 로봇을 벽이나 사람에게 박게 만든다.
- **느리다.** 배터리 충전, 센서 캘리브레이션, 로봇을 시작 위치로 되돌리는 시간이 코드 한 줄 고치는 시간보다 훨씬 길다.
- **재현이 안 된다.** [10.15 rosbag과 디버깅](#/ros-debug)에서 본 대로, 실물에서 마주친 조명·마찰·배터리 전압은 다시 똑같이 만들 수 없다.
- **병렬화가 안 된다.** 로봇은 한 대인데 개발자는 여럿이다. 시뮬레이터는 각자의 노트북에서 몇 개든 동시에 띄울 수 있다.

Gazebo가 하는 일은 결국 하나다. **물리 엔진으로 세계를 굴리고, 그 세계 안에 놓인 로봇 모델의 관절과 센서에서 나올 법한 값을 계산해서, 그 값을 진짜 하드웨어가 내놓는 것과 똑같은 ROS 2 토픽으로 발행한다.** 노드 입장에서는 `/scan`에 `sensor_msgs/msg/LaserScan`이 날아오는 게 전부다 — 그 뒤에 진짜 LiDAR가 있는지 물리 엔진의 광선 투사(ray casting)가 있는지는 구분할 방법이 없다. 이 "구분이 안 된다"는 성질이 시뮬레이션 전체를 성립시키는 전제다.

::: hist Gazebo Classic에서 Gazebo Sim으로
"Gazebo"라는 이름은 두 세대를 가리킨다. **Gazebo Classic**(버전 11까지)은 ROS 1 시절부터 쓰이던 원조고, 2025년 1월 31일부로 수명이 끝났다. 그 후속으로 재작성된 것이 **Gazebo Sim**(개발 중에는 Ignition이라는 이름을 썼다)이고, 배포판마다 코드네임이 붙는다 — ROS 2 Jazzy는 Gazebo Harmonic과 짝을 이룬다. 이 절은 Gazebo Sim(Harmonic 이후)을 기준으로 쓴다. 오래된 튜토리얼에서 `gazebo_ros`, `libgazebo_ros_*.so` 같은 이름을 보게 되면 그건 Classic용이다 — 지금은 `ros_gz_sim`, `libgz-sim-*-system.so` 계열을 찾아야 한다.
:::

## 월드 파일: SDF로 세계를 기술한다

URDF가 **로봇 하나**를 기술하는 포맷이라면, Gazebo가 쓰는 **SDF**(Simulation Description Format)는 **로봇을 포함한 세계 전체** — 바닥, 조명, 물리 법칙, 다른 로봇들 — 를 기술하는 포맷이다.

```xml title="empty_world.sdf — 최소한의 월드 파일"
<?xml version="1.0" ?>
<sdf version="1.8">
  <world name="demo_world">

    <!-- 물리 스텝: 얼마나 잘게 시간을 쪼개 시뮬레이션할지 -->
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- 이 세 플러그인이 없으면 물리도, 씬 정보 조회도, 모델 스폰도 안 된다 -->
    <plugin filename="gz-sim-physics-system"
            name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system"
            name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system"
            name="gz::sim::systems::SceneBroadcaster"/>
    <!-- 센서를 쓸 거라면 이 플러그인도 필요하다 -->
    <plugin filename="gz-sim-sensors-system"
            name="gz::sim::systems::Sensors"/>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal></plane></geometry>
        </visual>
      </link>
    </model>

  </world>
</sdf>
```

(공식 문서 [Gazebo SDF worlds](https://gazebosim.org/docs/latest/sdf_worlds/)의 최소 예제를 기준으로 구성했다.)

세계 안에서 물리·센서·씬 그래프 조회 같은 기능은 전부 **플러그인**으로 켜고 끈다. Gazebo Sim의 설계 철학은 [10.15](#/ros-debug)에서 rosbag2가 저장소를 플러그인으로 뗀 것과 같다 — 물리 엔진 자체(DART, Bullet 등)도 교체 가능한 부품으로 취급한다. `<physics>`의 `max_step_size`가 이 절 뒤에서 실행 검증할 핵심 숫자다. 얼마나 잘게 시간을 쪼개서 뉴턴 방정식을 적분하느냐가 시뮬레이션의 안정성과 정확도를 정한다.

```bash
gz sim empty_world.sdf     # GUI로 월드를 띄운다
gz sim -r empty_world.sdf  # -r: 뜨자마자 바로 재생(run) 시작
```

::: note gz 도구는 ROS 2 CLI가 아니다
`gz sim`, `gz topic`, `gz service`는 **Gazebo 자체의 명령줄 도구**다. `ros2` 계열 명령이 아니다. Gazebo는 ROS 없이도 독립적으로 동작하는 시뮬레이터이고, ROS 2와의 연결은 다음 절에서 볼 `ros_gz_bridge`가 별도로 담당한다. 이 분리 때문에 "gz topic list에는 보이는데 ros2 topic list에는 안 보인다"는 증상이 자주 나온다 — 다리(bridge)를 놓지 않았다는 뜻이다.
:::

## URDF에 물리와 감각을 심는다

URDF만으로는 로봇이 시각적으로 어떻게 생겼고 관절이 어떻게 연결됐는지만 안다. **질량이 얼마인지, 마찰이 얼마인지, 센서가 어디 달렸는지**는 URDF의 표준 태그에 없다. 그래서 Gazebo 전용 확장인 `<gazebo>` 태그를 URDF 안에 끼워 넣는다.

```xml title="lidar_link 정의 + Gazebo 센서 확장"
<link name="lidar_link">
  <visual>
    <geometry><cylinder radius="0.05" length="0.04"/></geometry>
  </visual>
  <collision>
    <geometry><cylinder radius="0.05" length="0.04"/></geometry>
  </collision>
  <inertial>
    <mass value="0.15"/>
    <inertia ixx="0.0001" iyy="0.0001" izz="0.0001" ixy="0" ixz="0" iyz="0"/>
  </inertial>
</link>

<joint name="lidar_joint" type="fixed">
  <parent link="base_link"/>
  <child link="lidar_link"/>
  <origin xyz="0.1 0 0.15" rpy="0 0 0"/>
</joint>

<!-- 여기부터가 Gazebo 전용 확장이다. lidar_link를 참조해서 센서를 붙인다 -->
<gazebo reference="lidar_link">
  <sensor name="gpu_lidar" type="gpu_lidar">
    <update_rate>10</update_rate>
    <topic>scan</topic>
    <always_on>true</always_on>
    <visualize>true</visualize>
    <lidar>
      <scan>
        <horizontal>
          <samples>360</samples>
          <min_angle>-3.14159</min_angle>
          <max_angle>3.14159</max_angle>
        </horizontal>
      </scan>
      <range>
        <min>0.12</min>
        <max>10.0</max>
      </range>
    </lidar>
  </sensor>
</gazebo>
```

(`gz-sim-sensors-system` 플러그인이 세계에 로드돼 있어야 이 센서가 실제로 값을 낸다. 센서 태그 구조는 [Gazebo Sensors 문서](https://gazebosim.org/docs/latest/sensors/)를 기준으로 했다.)

`<gazebo reference="lidar_link">`는 "이 링크에 대해 다음 시뮬레이션 전용 속성을 추가한다"는 뜻이다. `xacro`([10.10 URDF](#/urdf))로 로봇마다 다른 LiDAR 스펙을 매크로 인자로 넘기면, 실물이 바뀌어도 이 블록 하나만 고치면 된다.

::: warn 시뮬레이터가 낸 토픽은 그냥 gz 세계 안의 것이다
방금 만든 `/scan`은 **Gazebo Transport**라는 별도의 통신 계층에 발행된다. ROS 2 노드가 `rclpy`로 구독해도 아무것도 안 잡히는 게 정상이다. Gazebo 쪽 토픽을 ROS 2 쪽 토픽으로 옮기는 다리를 반드시 놓아야 한다.

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan
```

`@`는 양방향, `[`는 Gazebo→ROS 단방향, `]`는 ROS→Gazebo 단방향이다. 여러 토픽을 한 번에 다리 놓을 때는 YAML로 `ros_topic_name`/`gz_topic_name`/`ros_type_name`/`gz_type_name`/`direction`을 나열해서 `ros_gz_bridge.launch.py`에 넘긴다. (공식 [ros2_integration 문서](https://gazebosim.org/docs/latest/ros2_integration/) 기준.)
:::

로봇을 세계에 등록하는 방법은 `ros_gz_sim`의 `create` 실행 파일이다. 소스(`ros_gz_sim/src/create.cpp`)에서 직접 확인한 인자는 다음과 같다.

```bash
# robot_description 파라미터로 발행된 URDF를 그대로 스폰한다
ros2 run ros_gz_sim create -topic robot_description -name my_robot -z 0.1

# 또는 SDF/URDF 파일을 직접 지정
ros2 run ros_gz_sim create -file my_robot.sdf -name my_robot -x 1.0 -y 2.0
```

`-topic`으로 넘기면 [10.10 URDF](#/urdf)와 [10.7 파라미터와 launch](#/params-launch)에서 본 `robot_state_publisher`가 이미 발행 중인 `/robot_description`을 그대로 읽어서 스폰한다 — xacro로 매번 파일을 다시 생성할 필요 없이, 노드가 발행하는 최신 URDF를 그대로 시뮬레이션에 반영할 수 있다.

## ros2_control: 하드웨어 인터페이스라는 추상화

지금까지는 센서(입력)만 다뤘다. 로봇을 **움직이려면**(출력) 관절에 토크나 속도 명령을 내려야 한다. 이 명령 경로를 관절마다, 로봇마다 따로 짜면 코드가 하드웨어에 종속된다. `ros2_control`은 여기에 표준 계층을 하나 끼운다.

```text nolines
 사용자 노드
     │  cmd_vel, 궤적 등 고수준 명령
     ▼
┌─────────────────┐
│ Controller       │   diff_drive_controller,
│ Manager          │   joint_trajectory_controller ...
└────────┬─────────┘
         │  command_interface / state_interface (표준화된 값)
         ▼
┌─────────────────┐
│ Hardware         │   실물: 시리얼/CAN으로 모터에 값을 쓴다
│ Interface        │   시뮬: Gazebo에 값을 쓴다
│ (plugin)         │   -- 이 플러그인 교체가 실물/시뮬을 가른다
└─────────────────┘
```

핵심은 **Controller Manager 위의 코드는 자신이 실물을 움직이는지 시뮬레이션을 움직이는지 모른다**는 것이다. 그 차이는 맨 아래 `Hardware Interface` 플러그인 하나로만 결정된다. URDF의 `<ros2_control>` 태그가 이 계층의 배선표다.

```xml title="ros2_control 태그 — 관절 하나의 인터페이스 선언"
<ros2_control name="GazeboSimSystem" type="system">
  <hardware>
    <!-- 이 한 줄이 실물이냐 시뮬이냐를 가른다 -->
    <plugin>gz_ros2_control/GazeboSimSystem</plugin>
  </hardware>
  <joint name="wheel_left_joint">
    <command_interface name="velocity">
      <param name="min">-10</param>
      <param name="max">10</param>
    </command_interface>
    <state_interface name="position"/>
    <state_interface name="velocity"/>
  </joint>
</ros2_control>
```

(태그 구조는 [ROS2_Control 공식 문서 Jazzy판 gz_ros2_control](https://control.ros.org/jazzy/doc/gz_ros2_control/doc/index.html)에서 대조했다.) `command_interface`는 컨트롤러가 **써 넣을** 값(속도, 힘, 위치), `state_interface`는 하드웨어가 **읽어 낼** 값이다. 실물 모터 드라이버로 갈 때는 `<plugin>`을 그 회사가 제공하는 하드웨어 플러그인 이름으로 바꾸기만 하면 되고, 나머지 컨트롤러 설정(YAML)은 그대로 재사용한다.

## gz_ros2_control: 시뮬레이션을 하드웨어처럼 속인다

`gz_ros2_control/GazeboSimSystem`이라는 하드웨어 플러그인이 실제로 무엇을 하는지가 이 절의 마지막 퍼즐 조각이다. 이건 URDF 쪽이 아니라 **Gazebo 쪽**에 심는 플러그인이다.

```xml title="URDF 안, world 스폰 후 로드되는 Gazebo 플러그인"
<gazebo>
  <plugin filename="libgz_ros2_control-system.so"
          name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>$(find my_robot_bringup)/config/diff_drive_controller.yaml</parameters>
  </plugin>
</gazebo>
```

이 플러그인은 매 물리 스텝마다 두 방향으로 값을 오간다. Controller Manager가 계산한 `command_interface` 값을 읽어서 **Gazebo 관절에 힘/속도를 적용**하고, 반대로 Gazebo 물리 엔진이 계산한 관절 위치·속도를 `state_interface`로 되돌려 준다. 즉 `GazeboSimSystem`은 "나는 하드웨어다"라고 Controller Manager를 속이는 어댑터이고, 그 뒤에 진짜 모터 대신 물리 엔진의 적분 결과가 앉아 있을 뿐이다.

::: tip 왜 이 구조가 이 책 전체와 연결되는가
`ros2_control`의 컨트롤러 매니저는 고정 주기로 도는 실행기다 — [4.6 asyncio 기초](#/asyncio-basics)에서 본 이벤트 루프, [10.3 rclpy 노드](#/rclpy-node)에서 본 executor 스핀과 본질이 같다. 매 사이클 "상태 읽기 → 제어 로직 계산 → 명령 쓰기"를 반복한다는 점에서, 뒤에서 볼 PID 제어나 [10.14 MoveIt 2](#/moveit)의 모션 플래닝도 결국 이 루프 위에 얹힌다. 시뮬레이션이든 실물이든 **이 루프의 모양은 똑같다** — 아래에 뭐가 있는지만 다르다.
:::

## 실행 검증 — 물리 스텝과 센서 노이즈를 직접 계산해 본다

`gz sim`도, `gz_ros2_control`도 이 환경에서 실행할 수 없다. 하지만 그 안에서 벌어지는 수학은 순수 파이썬으로 재현할 수 있다. 두 가지를 직접 돌려서 확인한다 — 방금 본 `<physics><max_step_size>`가 왜 중요한지, 그리고 "시뮬레이션의 센서 값"과 "실물 센서 값"이 왜 근본적으로 다른 종류의 숫자인지.

### 물리 스텝 크기와 에너지 드리프트

`max_step_size`는 물리 엔진이 뉴턴 방정식을 얼마나 잘게 쪼개 적분하는지를 정한다. 감쇠 없는 스프링-질량계는 에너지가 보존돼야 정상인데, 적분 스텝이 크면 그 보존이 깨진다.

```python title="step_size.py"
def simulate(dt, steps, k=20.0, m=1.0, x0=1.0):
    # 감쇠 없는 스프링-질량계: F = -kx, semi-implicit(symplectic) Euler
    # gz-sim 물리 엔진도 내부적으로 이런 종류의 시간 적분을 매 스텝 수행한다
    x, v = x0, 0.0
    for _ in range(steps):
        a = -k / m * x
        v += a * dt          # 속도부터 갱신 (symplectic 순서가 안정성을 좌우한다)
        x += v * dt          # 그다음 위치 갱신
    return 0.5 * m * v**2 + 0.5 * k * x**2  # 최종 에너지


e0 = 0.5 * 20.0 * 1.0 ** 2  # 초기 에너지 (x0=1, v0=0)
print(f"초기 에너지: {e0:.4f}")

for dt, steps in [(0.001, 5000), (0.01, 500), (0.1, 50)]:
    final = simulate(dt, steps)
    drift = (final - e0) / e0 * 100
    print(f"dt={dt:>5} (총 {steps*dt:.1f}s, {steps}스텝) -> "
          f"최종 에너지 {final:.4f}, 드리프트 {drift:+.2f}%")
```

```pyrepl
초기 에너지: 10.0000
dt=0.001 (총 5.0s, 5000스텝) -> 최종 에너지 9.9850, 드리프트 -0.15%
dt= 0.01 (총 5.0s, 500스텝) -> 최종 에너지 9.8500, 드리프트 -1.50%
dt=  0.1 (총 5.0s, 50스텝) -> 최종 에너지 8.2318, 드리프트 -17.68%
```

(Python 3.14.5 기준 실측.) 같은 5초를 시뮬레이션해도 `dt`를 100배 키우면 드리프트가 100배 넘게 커진다 — 선형이 아니라 그보다 나쁘게 발화한다. 이게 바로 월드 파일의 `max_step_size`를 함부로 키우면 안 되는 이유다. 스텝을 크게 잡으면 물리 엔진이 계산을 빨리 끝내서 `real_time_factor`(벽시계 대비 시뮬레이션 시간 배율)를 1.0 이상으로 밀어붙일 수 있지만, 그 대가로 물체가 서로 뚫고 지나가거나 로봇이 미세하게 떨리는 수치적 불안정이 나타난다.

::: perf real_time_factor는 공짜가 아니다
`real_time_factor`를 1.0보다 크게(예: 2.0) 설정하면 시뮬레이션이 벽시계보다 빠르게 진행되는 것처럼 보이지만, 실제로는 **CPU가 그만큼 더 짧은 시간 안에 같은 양의 물리 계산을 끝내야 한다**는 요구일 뿐이다. 물리 엔진이 그 속도를 못 따라가면 `real_time_factor`는 목표치보다 낮게 관측된다. [5.1 측정 없이 최적화 없다](#/profiling)의 원칙이 여기서도 그대로 적용된다 — "설정값"과 "실제로 나온 값"은 다른 것이고, `gz topic echo /stats`(또는 GUI의 통계 패널)로 실측치를 확인해야 한다.
:::

### 센서 시뮬레이션의 정직성 — 노이즈 없는 값과 현실적인 값

시뮬레이션의 기본값은 **완벽한 정답**이다. 실물 LiDAR는 그렇지 않다. 노이즈, 유한한 해상도(양자화), 가끔 있는 반사 실패(드롭아웃)가 항상 낀다.

```python title="sensor_sim.py"
import random


def ideal_lidar(true_range):
    return true_range  # 시뮬레이션이 아무 설정도 안 하면 이렇게 된다


def realistic_lidar(true_range, sigma=0.02, dropout_p=0.05, rng=None):
    if rng.random() < dropout_p:
        return None                          # 반사 실패 -> 실측값 없음
    noisy = true_range + rng.gauss(0, sigma)  # 가우시안 노이즈
    resolution = 0.005                        # 실제 라이다의 양자화 간격
    return round(round(noisy / resolution) * resolution, 4)


true_range = 2.0
rng = random.Random(7)

print("이상적 시뮬 5회:", [ideal_lidar(true_range) for _ in range(5)])

samples = [realistic_lidar(true_range, rng=rng) for _ in range(10)]
print("현실적 모델(노이즈+양자화+드롭아웃) 10회:", samples)

valid = [s for s in samples if s is not None]
mean = sum(valid) / len(valid)
print(f"유효 샘플 {len(valid)}/{len(samples)}, 평균 {mean:.4f} "
      f"(참값 대비 오차 {mean - true_range:+.4f})")
```

```pyrepl
이상적 시뮬 5회: [2.0, 2.0, 2.0, 2.0, 2.0]
현실적 모델(노이즈+양자화+드롭아웃) 10회: [2.015, 2.025, 1.995, 2.005, None, 2.01, 2.005, 2.01, 2.01, 1.98]
유효 샘플 9/10, 평균 2.0061 (참값 대비 오차 +0.0061)
```

(Python 3.14.5 기준 실측. `random.Random(7)`로 시드를 고정해 재현 가능하다.) `ideal_lidar`는 5번 다 똑같은 `2.0`을 낸다 — 이 값만 보고 짠 필터·컨트롤러는 노이즈에 대한 방어 코드를 짤 이유 자체를 못 느낀다. Gazebo의 센서 플러그인에는 이 절의 예제처럼 `<noise>` 태그로 가우시안 노이즈를 직접 넣을 수 있지만, 기본값으로 두면 노이즈 없는 이상적 신호가 나온다는 걸 기억해야 한다.

## sim-to-real gap — 정직하게 짚는다

지금까지 본 두 실험이 sim-to-real gap(시뮬레이션-실물 격차)의 정체를 이미 보여줬다. **시뮬레이션은 물리 법칙과 센서 모델을 근사한 것이지, 그 자체가 현실이 아니다.** 근사가 어긋나는 지점은 최소 네 군데다.

1. **마찰·접촉 모델링의 부정확함.** 물리 엔진은 접촉을 단순화된 공식으로 계산한다. 바퀴가 미끄러지는 정도, 로봇 팔이 물체를 집을 때의 미세한 변형은 실물마다 다르고 시뮬레이터가 정확히 맞히기 어렵다.
2. **센서 노이즈 모델의 한계.** 방금 본 것처럼 노이즈를 직접 켜지 않으면 시뮬레이션 값은 지나치게 깨끗하다. 켜더라도 그 노이즈 모델(가우시안, 균일 등)이 실제 하드웨어의 노이즈 특성과 정확히 같으리라는 보장이 없다.
3. **타이밍과 지연.** 시뮬레이션에서는 명령을 내리면 다음 물리 스텝에 바로 반영되지만, 실물은 통신 지연, 모터 드라이버의 응답 지연, [4.3 GIL](#/gil)과 스케줄러가 만드는 지터가 끼어든다. [10.15](#/ros-debug)에서 본 "실시간성"의 한계가 실물에서만 나타나는 변수다.
4. **모델링되지 않은 것 자체.** 케이블이 걸리거나, 배터리 전압이 떨어지며 모터 토크가 줄거나, 부품이 마모되는 것은 애초에 URDF/SDF 어디에도 적혀 있지 않다.

::: danger 시뮬레이션에서만 통과한 코드를 실물에 바로 올리지 마라
이 절의 예제들이 보여주는 결론은 하나다. **시뮬레이션 통과는 필요조건이지 충분조건이 아니다.** 실전에서 쓰는 완화 전략을 알아 두면 실물 단계에서 놀랄 일이 줄어든다.

- **도메인 랜덤화**: 마찰 계수, 질량, 센서 노이즈 파라미터를 시뮬레이션 안에서 매번 무작위로 바꿔가며 학습·검증한다. 실물의 불확실성을 시뮬레이션 쪽에서 흉내 내는 접근이다.
- **노이즈를 의도적으로 켠다.** 위 `<sensor>` 태그에 `<noise>`를 넣어, 이상적인 값이 아니라 현실적인 값으로 파이프라인을 검증한다.
- **점진적 전이.** 시뮬레이션 → 실물의 안전한 환경(패드로 감싼 테스트베드) → 실제 현장 순으로 단계를 밟는다. 한 번에 건너뛰지 않는다.
- **결과를 의심하는 습관.** 시뮬레이션에서 "완벽하게" 동작한다는 결과 자체를, 노이즈·지연·마찰이 빠진 값이라는 걸 항상 염두에 두고 읽는다.
:::

## 요약

- Gazebo(정확히는 Gazebo Sim)는 물리 엔진과 센서 모델로 URDF 로봇을 가상 세계에서 굴려서, 진짜 하드웨어와 구분되지 않는 ROS 2 토픽을 발행한다.
- 월드는 **SDF** 파일로 기술한다. `<physics>`의 `max_step_size`, 물리·씬·센서 시스템 플러그인이 세계의 뼈대다.
- URDF에 `<gazebo reference="...">` 태그로 센서(카메라, LiDAR 등)를 붙인다. Gazebo의 값은 Gazebo Transport에 있으므로 `ros_gz_bridge`로 ROS 2 쪽에 다리를 놓아야 노드가 받을 수 있다.
- `ros2_control`은 컨트롤러 로직과 하드웨어를 `command_interface`/`state_interface`로 분리한 추상화다. `<plugin>` 한 줄만 바꾸면 시뮬레이션과 실물 사이를 오갈 수 있다.
- `gz_ros2_control`은 이 하드웨어 플러그인을 Gazebo 물리 엔진에 연결하는 어댑터다.
- 물리 스텝 크기가 크면 에너지 드리프트가 비선형적으로 커진다. 센서 시뮬레이션의 기본값은 노이즈가 없다 — 노이즈를 켜지 않으면 파이프라인이 현실을 마주할 준비가 안 된다.
- sim-to-real gap은 마찰·접촉 근사, 노이즈 모델의 부정확함, 타이밍 지연, 애초에 모델링되지 않은 현상에서 온다. 시뮬레이션 통과는 필요조건일 뿐 충분조건이 아니다.

::: quiz 연습문제
1. `ros2 run ros_gz_sim create -topic robot_description ...`와 `-file my_robot.sdf ...`는 각각 언제 쓰는 게 맞는가? `xacro`로 매개변수화된 로봇을 자주 고치는 개발 초기 단계를 기준으로 답하라.
2. `ros_gz_bridge`에서 `@`, `[`, `]` 세 방향 기호의 차이를 설명하고, 카메라 이미지를 Gazebo에서 ROS 2로만 받아오면 되는 경우 어느 것을 써야 하는지 답하라.
3. 이 절의 `simulate()` 함수를 고쳐서 `dt=0.001`부터 `dt=0.2`까지 10개 구간의 드리프트를 계산하고, 드리프트가 5%를 처음 넘는 `dt` 값을 찾아라. 실제로 실행해서 확인하라.
4. `ros2_control`의 `<plugin>gz_ros2_control/GazeboSimSystem</plugin>` 한 줄을 실물 하드웨어 드라이버 플러그인으로 바꾸는 것만으로 왜 컨트롤러 매니저 쪽 코드는 전혀 손대지 않아도 되는지, 이 절의 계층 구조를 근거로 설명하라.
5. `realistic_lidar()`에 드롭아웃이 발생했을 때 `None`을 반환하는 대신 이전 유효 샘플을 그대로 반환(hold)하도록 고쳐라. 이 방식이 로봇 제어 코드 입장에서 왜 위험할 수 있는지 — 특히 로봇이 실제로 움직이고 있어서 참값이 계속 바뀌는 상황을 기준으로 — 설명하라.
:::

**다음 절**: [10.12 센서 데이터 처리](#/sensors) — 카메라·LiDAR·IMU에서 실제로 흘러나오는 메시지를 어떻게 동기화하고 가공하는가, 그리고 이 절에서 본 노이즈가 그 처리 파이프라인에 어떻게 나타나는가.
