# 10.10 URDF와 로봇 모델

::: lead
지금까지 이 파트는 로봇이 무엇을 **주고받는지**를 다뤘다 — 토픽으로 데이터를, 서비스로 요청을, TF2로 좌표를([10.9](#/tf2)). 그런데 그 좌표 변환은 애초에 어디서 나오는가? `lookup_transform("base_link", "gripper")` 를 호출하면 누군가 그 프레임 트리를 채워 넣어야 한다. 이 절은 그 답이다. URDF는 로봇의 뼈대(링크)와 관절(조인트)을 XML로 적은 명세서고, `robot_state_publisher`는 그 명세서와 실시간 관절 각도를 곱해 TF 트리를 자동으로 채운다. 이 절을 넘기면 RViz에 뜨는 로봇 팔이 어디서 왔는지, 그 좌표가 왜 그렇게 움직이는지 손으로 계산할 수 있게 된다.
:::

## 문제: 좌표는 누가 채우는가

[10.9절](#/tf2)에서 TF2가 프레임 트리를 관리한다고 배웠다. `base_link` → `arm_base` → `arm_link1` → `gripper` 같은 부모-자식 관계와, 그 사이의 변환(translation + rotation)을 누군가 지속적으로 발행해야 트리가 존재한다.

당장 두 가지 방법이 떠오를 것이다.

- 코드로 `TransformBroadcaster` 를 직접 써서 매 프레임 좌표를 계산해 발행한다.
- 그런데 관절이 30개짜리 매니퓰레이터라면, 이 코드를 30번 반복해야 하고 로봇 구조가 바뀔 때마다 코드를 고쳐야 한다.

둘 다 나쁜 선택이다. 로봇의 **기하학적 구조**(어떤 링크가 어디에 붙어 있고, 어떤 관절이 어느 축으로 얼마나 움직이는가)는 코드가 아니라 **선언적 데이터**로 있어야 한다. 그래야 시뮬레이터(Gazebo, [10.11](#/gazebo)), 모션 플래너([10.14 MoveIt](#/moveit)), 시각화 도구(RViz)가 전부 같은 하나의 명세를 공유해서 쓸 수 있다. 이 명세가 **URDF**(Unified Robot Description Format)다.

## URDF의 뼈대: link와 joint

URDF는 두 종류의 태그만 가지고 로봇 전체를 표현한다. **`<link>`는 강체(rigid body) 하나**, **`<joint>`는 두 링크를 잇는 관절 하나**다. 로봇은 결국 링크를 정점, 조인트를 간선으로 하는 **트리**다 — 그래프가 아니라 트리라는 게 중요하다. 루프가 있으면(사족보행 로봇의 폐쇄 링크 같은) URDF만으로는 표현이 안 된다.

다음은 ROS 2 공식 `urdf_tutorial` 저장소의 예제(`ros2` 브랜치, `urdf/07-physics.urdf`)에서 그대로 가져온 조각이다.

```xml title="link의 세 부분 — 공식 urdf_tutorial 예제에서 발췌"
<link name="right_leg">
  <visual>
    <geometry>
      <box size="0.6 0.1 0.2"/>
    </geometry>
    <origin rpy="0 1.57075 0" xyz="0 0 -0.3"/>
    <material name="white"/>
  </visual>
  <collision>
    <geometry>
      <box size="0.6 0.1 0.2"/>
    </geometry>
    <origin rpy="0 1.57075 0" xyz="0 0 -0.3"/>
  </collision>
  <inertial>
    <mass value="10"/>
    <inertia ixx="1e-3" ixy="0.0" ixz="0.0" iyy="1e-3" iyz="0.0" izz="1e-3"/>
  </inertial>
</link>
```

한 링크 안에는 목적이 다른 세 블록이 있다. 이걸 구분하지 못하면 나중에 "RViz에는 보이는데 충돌 감지가 안 된다" 같은 버그를 디버깅할 수 없다.

| 블록 | 역할 | 누가 읽는가 |
| --- | --- | --- |
| `<visual>` | 화면에 그려지는 모양 | RViz, Gazebo 렌더러 |
| `<collision>` | 충돌 판정에 쓰는 모양 | 물리 엔진, MoveIt 충돌 체크 |
| `<inertial>` | 질량, 관성 텐서 | 물리 시뮬레이터(Gazebo), 동역학 계산 |

::: tip visual과 collision을 다르게 만드는 이유
정밀한 메시(mesh)를 `<visual>`에 쓰고, 그걸 감싸는 단순한 상자나 실린더를 `<collision>`에 쓰는 게 실전 관행이다. 메시 대 메시 충돌 검사는 느리고 정밀도가 필요 없는 곳에 계산량만 쓴다. 로봇 팔의 실제 케이블 다발까지 시각적으로는 보여주고 싶지만, 충돌 검사는 팔을 감싸는 원기둥 하나로 충분한 경우가 많다.
:::

`<geometry>` 안에 들어갈 수 있는 원시 도형은 `<box size="x y z"/>`, `<cylinder radius="" length=""/>`, `<sphere radius=""/>`, 그리고 외부 3D 모델 파일을 참조하는 `<mesh filename="package://패키지명/meshes/파일.dae"/>` 다. `package://` 는 ROS 2 패키지 경로를 가리키는 URDF 전용 URI 스킴이다 — `ament_index`가 이 경로를 실제 파일시스템 경로로 풀어 준다([10.2 워크스페이스](#/ros-workspace)).

`<origin xyz="x y z" rpy="roll pitch yaw"/>` 는 이 절 전체에서 가장 자주 쓰이는 태그다. `xyz`는 미터 단위 평행이동, `rpy`는 라디안 단위 롤-피치-요다. **원점을 안 쓰면 기본값은 전부 0** — 즉 부모 프레임 원점과 정확히 겹친다.

::: warn rpy는 라디안이다, 도가 아니다
`rpy="0 90 0"` 라고 쓰면 90**라디안**을 의미한다. 90도를 쓰고 싶으면 `1.5708`(π/2)이라고 써야 한다. 실전에서 로봇이 알 수 없는 각도로 홱 꺾여 있으면 십중팔구 이 실수다. xacro를 쓰면 `${pi/2}` 로 쓸 수 있어서 이 함정을 크게 줄인다 — 아래에서 다룬다.
:::

## 조인트: 링크를 잇는 관절, 그리고 그 자유도

조인트는 부모 링크와 자식 링크를 연결하면서, **몇 자유도로 어떻게 움직이는지**를 정의한다. URDF가 정의하는 조인트 타입은 정확히 여섯 가지다.

| 타입 | 자유도 | 축 필요 | limit 필요 | 실제 예 |
| --- | --- | --- | --- | --- |
| `fixed` | 0 | 없음 | 없음 | 센서를 몸체에 고정 장착 |
| `revolute` | 1 (회전, 범위 제한) | O | O (필수) | 로봇 팔 관절 |
| `continuous` | 1 (회전, 무제한) | O | 선택 | 바퀴 축 |
| `prismatic` | 1 (직선 이동, 범위 제한) | O | O (필수) | 그리퍼 슬라이드 |
| `planar` | 2 (평면 내 이동) | 평면 법선 | 드묾 | 평면 위를 미끄러지는 대차 |
| `floating` | 6 (완전 자유) | 없음 | 없음 | 부유체, 드론 베이스 |

실전에서 압도적으로 많이 쓰는 건 앞의 네 가지다. `revolute`와 `continuous`의 차이를 헷갈리는 사람이 많은데, **`revolute`는 회전 각도에 상한·하한이 있고 그래서 `<limit>`가 필수**다. `continuous`는 바퀴처럼 끝없이 돌 수 있어서 각도 제한이 없다.

역시 공식 `urdf_tutorial`(`07-physics.urdf`)에서 조인트 네 종류를 실제 문법 그대로 가져온다.

```xml title="네 가지 조인트 타입 — 공식 예제 그대로"
<!-- fixed: 자유도 없음. axis, limit 둘 다 필요 없다 -->
<joint name="base_to_right_leg" type="fixed">
  <parent link="base_link"/>
  <child link="right_leg"/>
  <origin xyz="0 -0.22 0.25"/>
</joint>

<!-- continuous: 바퀴처럼 무한 회전. limit 없이 axis만 있다 -->
<joint name="right_front_wheel_joint" type="continuous">
  <axis rpy="0 0 0" xyz="0 1 0"/>
  <parent link="right_base"/>
  <child link="right_front_wheel"/>
  <origin rpy="0 0 0" xyz="0.133333333333 0 -0.085"/>
</joint>

<!-- prismatic: 직선 이동. limit의 lower/upper가 이동 범위(미터) -->
<joint name="gripper_extension" type="prismatic">
  <parent link="base_link"/>
  <child link="gripper_pole"/>
  <limit effort="1000.0" lower="-0.38" upper="0" velocity="0.5"/>
  <origin rpy="0 0 0" xyz="0.19 0 0.2"/>
</joint>

<!-- revolute: 제한된 회전. limit의 lower/upper가 각도(라디안) -->
<joint name="left_gripper_joint" type="revolute">
  <axis xyz="0 0 1"/>
  <limit effort="1000.0" lower="0.0" upper="0.548" velocity="0.5"/>
  <origin rpy="0 0 0" xyz="0.2 0.01 0"/>
  <parent link="gripper_pole"/>
  <child link="left_gripper"/>
</joint>
```

`<parent>`, `<child>`는 링크 이름을 가리키는 참조일 뿐이다 — 이게 TF 트리의 부모-자식 관계 그 자체가 된다. `<axis xyz="0 0 1"/>`은 회전축(또는 이동축)을 **조인트(자식 링크) 좌표계 기준**으로 나타낸 단위 벡터다. `<limit>`의 `effort`는 최대 토크/힘(N·m 또는 N), `velocity`는 최대 속도, `lower`/`upper`는 이동 가능 범위다. `revolute`와 `prismatic`은 이 넷 중 `effort`/`velocity`/`lower`/`upper`가 사실상 필수다 — 없으면 파서가 기본값(보통 0)을 넣어서 관절이 전혀 안 움직이는 것처럼 보인다.

::: danger origin의 기준 프레임을 착각하면 로봇이 폭발한다
`<joint>` 안의 `<origin>`은 **부모 링크 프레임에서 이 조인트(=자식 링크 원점)까지의 변환**이다. `<link>` 안의 `<visual>`/`<collision>` origin은 **그 링크 자신의 원점에서 시각적 모양까지의 오프셋**이다. 이 둘을 혼동해서 조인트 origin에 시각 오프셋을 넣거나 반대로 하면, 링크들이 서로 관통하거나 우주로 날아간 것처럼 벌어진 채로 RViz에 뜬다. 처음 URDF를 짜는 사람 거의 전부가 한 번은 겪는 디버깅이다.
:::

### 순수 파이썬으로 확인하는 조인트 체인의 수학

`robot_state_publisher`가 실제로 하는 일은 결국 **각 조인트의 원점 변환과 현재 관절값을 행렬로 곱해 나가는 것**이다. rclpy 없이, 이 수학만 따로 파이썬으로 짜서 검증해 보자. 2관절 평면 팔 — `base_link`에서 1m 떨어진 `link1`, 거기서 다시 1m 떨어진 `link2` 끝점 — 을 생각한다.

```python title="fk_chain.py — TF가 매 프레임 계산하는 것과 같은 종류의 행렬 합성"
import math


def rpy_to_matrix(roll, pitch, yaw):
    """URDF의 origin rpy를 3x3 회전 행렬로. R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def mat_mul(a, b):
    n, m, k = len(a), len(b[0]), len(b)
    return [[sum(a[i][t] * b[t][j] for t in range(k)) for j in range(m)] for i in range(n)]


def homogeneous(xyz, rpy):
    r = rpy_to_matrix(*rpy)
    h = [row[:] + [xyz[i]] for i, row in enumerate(r)]
    h.append([0.0, 0.0, 0.0, 1.0])
    return h


def rot_z(theta):
    c, s = math.cos(theta), math.sin(theta)
    return [[c, -s, 0.0, 0.0], [s, c, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


# <joint origin>에 해당 -- URDF에 고정된 값
joint1_origin = homogeneous((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
joint2_origin = homogeneous((1.0, 0.0, 0.0), (0.0, 0.0, 0.0))

# joint_states 토픽으로 매 순간 들어오는 값 -- robot_state_publisher가 구독하는 바로 그 데이터
theta1 = math.radians(90)
theta2 = math.radians(-90)

T1 = mat_mul(joint1_origin, rot_z(theta1))          # base_link -> link1
T2 = mat_mul(T1, mat_mul(joint2_origin, rot_z(theta2)))  # base_link -> link2

tip_local = [1.0, 0.0, 0.0, 1.0]                     # link2 프레임에서 팔 끝점
tip_world = [sum(T2[i][j] * tip_local[j] for j in range(4)) for i in range(4)]

print("tip position in base_link frame:", [round(v, 4) for v in tip_world])
```

```text nolines
tip position in base_link frame: [1.0, 1.0, 0.0, 1.0]
```

(Python 3.14.5 실행 결과.) 손으로도 검산된다 — link1이 90도 꺾여 y축 방향으로 1m 뻗고, link2가 다시 -90도 꺾여 x축 방향으로 1m 더 뻗으니 끝점은 `(1, 1, 0)`이 맞다. **`robot_state_publisher`가 하는 일의 본질은 딱 이것뿐이다.** URDF에서 고정된 `joint_origin` 행렬들과, `joint_states` 토픽으로 매번 갱신되는 회전/이동 행렬을 체인 순서대로 곱해서 각 링크의 `base_link` 기준 위치를 계산하고, 그 결과를 `/tf`로 발행한다. 조인트가 30개든 300개든 원리는 똑같다 — 체인을 따라 4x4 행렬을 계속 곱하는 것뿐이다.

::: cote 코딩테스트 포인트 — 이건 트리 문제다
URDF 문서 하나를 파싱하면 링크가 정점, 조인트가 간선인 **트리**가 나온다. "이 링크에서 저 링크까지 경로를 찾아라"는 순수하게 [7.13 그래프 표현](#/graph)과 [7.14 BFS/DFS](#/bfs-dfs)의 문제다. `lookup_transform`이 내부적으로 하는 일도 이 탐색과 본질적으로 같다 — 공통 조상까지 올라갔다가 다시 내려오는 경로를 찾는다.

```python
from collections import defaultdict

joints = [
    ("base_link", "right_leg", "fixed"),
    ("right_leg", "right_base", "fixed"),
    ("right_base", "right_front_wheel", "continuous"),
    ("base_link", "head", "continuous"),
]

children = defaultdict(list)
for parent, child, _ in joints:
    children[parent].append(child)


def find_path(start, target, path=None):
    path = path or [start]
    if start == target:
        return path
    for child in children.get(start, []):
        if result := find_path(child, target, path + [child]):
            return result
    return None


print(find_path("base_link", "right_front_wheel"))
```

```text nolines
['base_link', 'right_leg', 'right_base', 'right_front_wheel']
```

(실행 결과. `assert` 로 직접 검증했다.) 이 경로 찾기가 실제로 아주 큰 로봇 — 조인트 수백 개짜리 인간형 로봇 — 에서는 트리 깊이와 폭이 커지므로, `find_path`를 재귀로 순진하게 짜면 [7.13절](#/graph)에서 배운 재귀 깊이 한계에 부딪힐 수 있다. 실전 TF2 구현은 물론 이것보다 훨씬 정교하지만, **개념적으로는 트리 탐색**이라는 사실은 변하지 않는다.
:::

## xacro: URDF의 반복을 매크로로 지운다

네 다리 달린 로봇, 양팔 로봇을 순수 URDF로 쓰면 어떻게 될까? 다리 하나에 링크 5개, 조인트 5개가 필요하다면 네 다리는 20개씩을 손으로 복사-붙여넣기 해야 한다. 이름만 `right_front`, `left_front`, `right_back`, `left_back`으로 바꾸면서. 복사-붙여넣기의 필연적 결과 — 하나를 고치고 나머지 세 개 고치는 걸 잊는다 — 가 그대로 일어난다.

**xacro**(XML Macro)는 이 문제를 매크로 전처리로 푼다. URDF를 직접 쓰는 대신 `.urdf.xacro` 파일을 쓰고, xacro가 그걸 전개해서 최종 순수 URDF XML을 만들어낸다. 아래는 공식 `urdf_tutorial` 저장소(`ros2` 브랜치, `urdf/08-macroed.urdf.xacro`)에서 발췌한 조각이다 — 원본은 그리퍼(gripper)와 머리(head) 부분까지 포함해 더 길지만, 매크로 정의와 호출의 핵심 구조만 보이도록 그 뒤쪽은 생략했다.

```xml title="08-macroed.urdf.xacro — 공식 예제에서 발췌 (그리퍼·머리 부분은 생략)"
<?xml version="1.0"?>
<robot name="macroed" xmlns:xacro="http://ros.org/wiki/xacro">

  <xacro:property name="width" value="0.2" />
  <xacro:property name="leglen" value="0.6" />
  <xacro:property name="polelen" value="0.2" />
  <xacro:property name="bodylen" value="0.6" />
  <xacro:property name="baselen" value="0.4" />
  <xacro:property name="wheeldiam" value="0.07" />

  <material name="blue">
    <color rgba="0 0 0.8 1"/>
  </material>
  <material name="black">
    <color rgba="0 0 0 1"/>
  </material>
  <material name="white">
    <color rgba="1 1 1 1"/>
  </material>

  <xacro:macro name="default_inertial" params="mass">
    <inertial>
      <mass value="${mass}" />
      <inertia ixx="1e-3" ixy="0.0" ixz="0.0" iyy="1e-3" iyz="0.0" izz="1e-3" />
    </inertial>
  </xacro:macro>

  <link name="base_link">
    <visual>
      <geometry>
        <cylinder radius="${width}" length="${bodylen}"/>
      </geometry>
      <material name="blue"/>
    </visual>
    <collision>
      <geometry>
        <cylinder radius="${width}" length="${bodylen}"/>
      </geometry>
    </collision>
    <xacro:default_inertial mass="10"/>
  </link>

  <xacro:macro name="wheel" params="prefix suffix reflect">
    <link name="${prefix}_${suffix}_wheel">
      <visual>
        <origin xyz="0 0 0" rpy="${pi/2} 0 0" />
        <geometry>
          <cylinder radius="${wheeldiam/2}" length="0.1"/>
        </geometry>
        <material name="black"/>
      </visual>
      <collision>
        <origin xyz="0 0 0" rpy="${pi/2} 0 0" />
        <geometry>
          <cylinder radius="${wheeldiam/2}" length="0.1"/>
        </geometry>
      </collision>
      <xacro:default_inertial mass="1"/>
    </link>
    <joint name="${prefix}_${suffix}_wheel_joint" type="continuous">
      <axis xyz="0 1 0" rpy="0 0 0" />
      <parent link="${prefix}_base"/>
      <child link="${prefix}_${suffix}_wheel"/>
      <origin xyz="${baselen*reflect/3} 0 -${wheeldiam/2+.05}" rpy="0 0 0"/>
    </joint>
  </xacro:macro>

  <xacro:macro name="leg" params="prefix reflect">
    <link name="${prefix}_leg">
      <visual>
        <geometry>
          <box size="${leglen} 0.1 0.2"/>
        </geometry>
        <origin xyz="0 0 -${leglen/2}" rpy="0 ${pi/2} 0"/>
        <material name="white"/>
      </visual>
      <collision>
        <geometry>
          <box size="${leglen} 0.1 0.2"/>
        </geometry>
        <origin xyz="0 0 -${leglen/2}" rpy="0 ${pi/2} 0"/>
      </collision>
      <xacro:default_inertial mass="10"/>
    </link>

    <joint name="base_to_${prefix}_leg" type="fixed">
      <parent link="base_link"/>
      <child link="${prefix}_leg"/>
      <origin xyz="0 ${reflect*(width+.02)} 0.25" />
    </joint>

    <link name="${prefix}_base">
      <visual>
        <geometry>
          <box size="${baselen} 0.1 0.1"/>
        </geometry>
        <material name="white"/>
      </visual>
      <collision>
        <geometry>
          <box size="${baselen} 0.1 0.1"/>
        </geometry>
      </collision>
      <xacro:default_inertial mass="10"/>
    </link>

    <joint name="${prefix}_base_joint" type="fixed">
      <parent link="${prefix}_leg"/>
      <child link="${prefix}_base"/>
      <origin xyz="0 0 ${-leglen}" />
    </joint>
    <xacro:wheel prefix="${prefix}" suffix="front" reflect="1"/>
    <xacro:wheel prefix="${prefix}" suffix="back" reflect="-1"/>
  </xacro:macro>

  <xacro:leg prefix="right" reflect="-1" />
  <xacro:leg prefix="left" reflect="1" />

  <!-- 이 아래로 그리퍼(gripper_extension, gripper_pole, gripper 매크로)와
       머리(head, head_swivel, box) 정의가 이어지지만, 매크로 개념 설명에는
       불필요해 생략했다. 전체 파일은 원본 저장소를 참고. -->

</robot>
```

핵심 문법은 세 가지뿐이다.

- **`<xacro:property name="..." value="..."/>`** — 상수를 이름으로 선언한다. `${width}` 처럼 `${}` 안에 이름을 넣으면 값으로 치환된다. `${pi/2}`, `${width*reflect/3}` 같은 산술식도 그 안에서 그대로 계산된다.
- **`<xacro:macro name="..." params="...">...</xacro:macro>`** — 반복될 XML 조각을 함수처럼 정의한다. `params`는 매크로가 받을 매개변수 목록(공백으로 구분)이다.
- **`<xacro:매크로이름 매개변수="값"/>`** — 매크로를 호출한다. 호출할 때마다 매개변수만 바뀐 채 매크로 본문 전체가 그 자리에 전개(expand)된다.

이건 파이썬의 함수 정의·호출과 정확히 같은 개념이다. **다른 게 있다면 xacro는 실행 시점이 아니라 XML을 만드는 시점, 즉 전처리 단계에서 전개된다는 것뿐이다.** `${...}` 치환도 결국 문자열 템플릿 치환이다 — 파이썬으로 같은 개념을 흉내내면 이렇게 된다.

```python title="xacro_analog.py — xacro 매크로 전개를 파이썬 함수 호출로 흉내내기"
WHEEL_TEMPLATE = """\
<link name="{prefix}_{suffix}_wheel">
  <visual><geometry><cylinder radius="{radius}" length="0.1"/></geometry></visual>
</link>
<joint name="{prefix}_{suffix}_wheel_joint" type="continuous">
  <parent link="{prefix}_base"/>
  <child link="{prefix}_{suffix}_wheel"/>
  <axis xyz="0 {reflect} 0"/>
</joint>
"""


def make_wheel(prefix, suffix, reflect, radius=0.035):
    # xacro:macro name="wheel" params="prefix suffix reflect" 를 함수로 옮긴 것
    return WHEEL_TEMPLATE.format(prefix=prefix, suffix=suffix, reflect=reflect, radius=radius)


snippets = [
    make_wheel("right", "front", reflect=1),
    make_wheel("left", "front", reflect=-1),
]

names = [s.split('"')[1] for s in snippets]
print(names)
print(len(set(names)) == 2, len({len(s.splitlines()) for s in snippets}) == 1)
```

```text nolines
['right_front_wheel', 'left_front_wheel']
True True
```

(실행 결과.) 이름은 두 개 다 다르지만(매크로가 제대로 작동했다는 증거), 줄 수·태그 구조는 완전히 같다(같은 매크로 본문에서 나왔다는 증거). xacro가 실제로 하는 일도 이것과 본질적으로 같다 — 다만 문자열 포맷팅이 아니라 XML 트리 수준에서 훨씬 정교하게 한다.

::: note 아직도 남아 있는 이름: `ament_python`이 아니라 `ament_cmake`?
xacro 파일은 빌드 시점이 아니라 **launch 시점**(또는 그 이전에 `xacro` CLI로 미리)에 전개된다. `ros2 launch` 안에서 `Command(["xacro", " ", xacro_file])`로 결과를 `robot_description` 파라미터에 바로 넣는 방식이 흔하다. 즉 xacro 파일 자체를 colcon이 컴파일하는 게 아니라, 실행 시점에 순수 URDF 문자열로 변환해서 넘긴다.
:::

::: perf xacro는 런타임 비용이 아니다
xacro 전개는 노드가 뜨기 **전에** 한 번 일어난다. `revolute` 조인트가 300개짜리 복잡한 인간형 로봇이라도, 전개된 결과 URDF가 크다는 것만 문제가 될 뿐(파싱 시간이 조금 늘어난다) 실행 중 매 프레임 비용은 전혀 없다. 매크로 전개는 시작 시점에 끝나는 일이고, 그 뒤로는 완전히 평평한 XML만 남는다.
:::

## robot_state_publisher: URDF와 관절 상태를 TF로 잇는다

이제 조각을 모은다. **`robot_state_publisher` 노드는 URDF(고정된 기하 구조)와 `joint_states` 토픽(실시간으로 바뀌는 관절값)을 입력으로 받아, 그 둘을 곱한 결과를 `/tf`와 `/tf_static`으로 발행한다.**

```text nolines
   robot_description (파라미터, URDF 문자열)
          │
          ▼
   ┌────────────────────┐        joint_states (topic, sensor_msgs/JointState)
   │ robot_state_publisher├◀──────────────────────────────────
   └──────────┬──────────┘
              │
      ┌───────┴────────┐
      ▼                ▼
   /tf_static        /tf
   (fixed 조인트)     (revolute/continuous/prismatic 조인트,
                       매 joint_states 콜백마다 갱신)
```

핵심 구분이 하나 있다 — **`fixed` 조인트는 `/tf_static`으로, 그 외(움직이는) 조인트는 `/tf`로 나뉘어 발행된다.** `fixed` 조인트의 변환은 로봇이 살아 있는 동안 절대 바뀌지 않으니, 매 프레임 다시 보낼 필요가 없다. `/tf_static`은 노드가 시작할 때 딱 한 번(래치된 형태로) 발행되고, 새로 구독을 시작한 노드는 그 마지막 값을 즉시 받는다. 반면 `/tf`는 `joint_states`가 갱신될 때마다 계속 발행된다. 이 구분은 [10.8 QoS](#/qos)에서 배운 **내구성(durability)** 정책이 실제로 쓰이는 대표 사례다 — `/tf_static`은 `TRANSIENT_LOCAL`로 발행돼서, 늦게 붙은 구독자도 과거에 발행된 고정 변환을 놓치지 않는다.

`robot_state_publisher`는 rclpy가 아니라 C++로 구현된 표준 ROS 2 패키지다. 파이썬에서 직접 다룰 일은 거의 없고, 대개 launch 파일로 실행한다.

```python title="launch 파일에서 robot_state_publisher를 띄우는 흔한 패턴"
from launch import LaunchDescription
from launch.actions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    robot_description = ParameterValue(
        Command(["xacro", " ", "/path/to/robot.urdf.xacro"]),
        value_type=str,
    )

    rsp_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"robot_description": robot_description}],
    )

    return LaunchDescription([rsp_node])
```

`Command(["xacro", " ", ...])`가 바로 위에서 말한 "launch 시점에 xacro를 전개한다"는 것을 그대로 보여준다 — xacro CLI를 서브프로세스로 실행하고, 그 표준출력(순수 URDF XML 문자열)을 `robot_description` 파라미터 값으로 넣는다. `robot_state_publisher`는 시작할 때 이 파라미터가 **반드시** 설정돼 있어야 한다 — 없으면 노드가 뜨지 않는다. 이건 [10.7 파라미터와 launch](#/params-launch)에서 다룬 "필수 파라미터" 패턴의 실전 사례다.

::: warn joint_states가 안 오면 로봇이 원점에 뭉쳐 있다
`robot_state_publisher`가 `joint_states`를 한 번도 못 받으면, 움직이는 조인트들은 URDF에 적힌 **기본 위치**(보통 0)로 간주된다. RViz를 켰는데 로봇 팔이 다 접혀서 하나로 뭉쳐 있다면, 십중팔구 `joint_state_publisher`(또는 실제 하드웨어 드라이버, 시뮬레이터)가 안 떠 있어서 `joint_states`가 발행되지 않고 있는 것이다. 실제 로봇이 없을 때는 `joint_state_publisher_gui` 패키지가 슬라이더로 각 관절값을 손으로 조절해 볼 수 있게 해 준다 — URDF 하나 짜 놓고 관절이 제대로 움직이는지 눈으로 확인하는 가장 빠른 방법이다.
:::

## RViz로 확인하기

URDF를 다 짜고 나면 코드 한 줄 없이 확인할 수 있다. 공식 `urdf_tutorial` 패키지가 제공하는 launch 파일이 표준적인 확인 절차를 보여준다 — `robot_state_publisher`, (선택적으로) `joint_state_publisher_gui`, `rviz2`를 한 번에 띄운다.

```bash
ros2 launch urdf_tutorial display.launch.py model:=/path/to/robot.urdf.xacro
```

이 명령이 뜨면 다음이 동시에 일어난다.

1. xacro가 지정한 파일을 순수 URDF로 전개해 `robot_description` 파라미터에 넣는다.
2. `robot_state_publisher`가 그 URDF를 파싱하고 `joint_states`를 구독하기 시작한다.
3. `joint_state_publisher_gui`가 뜨면서 움직이는 각 조인트마다 슬라이더가 생긴다 — 슬라이더를 움직이면 `joint_states`가 발행된다.
4. RViz가 열리고, `RobotModel` 디스플레이가 `/robot_description`을 읽어 링크의 `<visual>` 형상을 그린 뒤, `/tf`를 구독해서 매 프레임 각 링크를 올바른 위치에 배치한다.

RViz에서 확인할 때 실전에서 자주 걸리는 지점 두 가지가 있다.

- **Fixed Frame이 로봇에 없는 프레임으로 잡혀 있으면 아무것도 안 보인다.** RViz의 `Fixed Frame` 설정을 URDF의 루트 링크 이름(보통 `base_link`)과 맞춰야 한다.
- **RobotModel 디스플레이의 `Description Topic`이 `robot_description`을 가리키는지 확인한다.** 여러 로봇을 네임스페이스로 나눠 띄우는 멀티 로봇 구성에서는 이 파라미터 이름이 꼬여서 "URDF는 맞게 짰는데 RViz에 아무것도 안 뜬다"는 증상이 흔하게 나온다.

::: hist 왜 시각화 형식이 통신 프로토콜과 같이 갔는가
URDF는 원래 ROS 1 시절, PR2 로봇 프로젝트에서 나왔다. 당시 목표는 단순했다 — 시뮬레이터, 시각화 도구, 모션 플래너가 **각자 다른 방식으로 로봇 모양을 정의하면** 셋이 서로 다른 로봇을 상상하게 된다는 문제를 풀어야 했다. 그래서 "로봇의 기하학적 진실은 파일 하나"라는 원칙이 URDF의 존재 이유가 됐다. `robot_state_publisher`가 이 원칙을 실시간 시스템으로 확장한 것이다 — URDF라는 정적 진실과 `joint_states`라는 동적 진실을 합쳐서, TF라는 하나의 통일된 좌표계 창구로 흘려보낸다.
:::

## 요약

- URDF는 로봇을 `<link>`(강체)와 `<joint>`(관절)로 이뤄진 **트리**로 표현하는 XML이다.
- 링크 안의 `<visual>`, `<collision>`, `<inertial>`은 목적이 다른 세 블록이다. 정밀 메시는 visual에, 단순 도형은 collision에 두는 게 실전 관행이다.
- 조인트 타입은 `fixed`, `revolute`, `continuous`, `prismatic`, `planar`, `floating` 여섯 가지다. `revolute`/`prismatic`은 `<limit>`가 사실상 필수다.
- xacro는 `<xacro:property>`, `<xacro:macro>`, `${...}` 치환으로 반복되는 URDF를 매크로화한다 — 개념적으로 파이썬 함수와 같지만 실행이 아니라 launch 시점 전개다.
- `robot_state_publisher`는 URDF(정적 구조)와 `joint_states`(동적 값)를 곱해 `/tf`(움직이는 조인트)와 `/tf_static`(고정 조인트)을 자동 발행한다.
- `joint_states`가 없으면 움직이는 조인트는 기본값(보통 0)에 멈춰 있다 — RViz에서 로봇이 뭉쳐 있으면 이걸 먼저 의심한다.
- RViz의 `RobotModel` 디스플레이는 `robot_description` 파라미터와 `/tf`를 함께 읽어서 매 프레임 로봇을 그린다.

::: quiz 연습문제
1. `<joint>` 안의 `<origin>`과 `<link><visual><origin>`은 각각 무엇을 기준으로 한 변환인지 설명하라. 이 둘을 혼동하면 RViz에서 어떤 증상이 나타나는가?
2. `revolute`와 `continuous`의 차이를 `<limit>` 태그의 필요 여부로 설명하고, 각각 실제 로봇의 어떤 부품에 대응하는지 예를 들어라.
3. 이 절의 `fk_chain.py`에서 `theta2`를 `-90도`가 아니라 `0도`로 바꾸면 팔 끝점 좌표는 어떻게 되는가? 손으로 계산한 뒤 코드를 고쳐서 검증하라.
4. xacro의 `<xacro:property>`와 `<xacro:macro>`를 각각 파이썬의 어떤 언어 요소에 대응시킬 수 있는가? [1.10 함수](#/functions)에서 배운 개념을 근거로 답하라.
5. `robot_state_publisher`가 `fixed` 조인트의 변환을 `/tf` 대신 `/tf_static`으로 보내는 이유를 [10.8 QoS](#/qos)의 내구성(durability) 개념으로 설명하라.
:::

**다음 절**: [10.11 Gazebo 시뮬레이션](#/gazebo) — 이 절에서 만든 URDF에 `<inertial>`과 충돌 형상이 왜 필요했는지, 물리 엔진이 그걸 어떻게 쓰는지 확인한다.
