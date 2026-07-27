# 10.14 MoveIt 2 매니퓰레이션

::: lead
[10.13 Nav2](#/nav2)는 바퀴 달린 로봇을 2차원 평면 위에서 목적지까지 옮기는 문제였다. 이번엔 축이 하나 늘어난다. 로봇 팔은 관절이 5개, 6개, 7개씩 있고, 목표는 "이 위치로 가라"가 아니라 "이 손끝을 저 좌표에, 저 각도로 갖다 대라"다. 여기서 파이썬 코드로 넘긴 숫자 여섯 개(위치 3 + 자세 3)를 관절 여섯 개의 각도로 바꾸는 계산이 **역기구학**이고, 이게 왜 어려운지 아는 것이 이 절의 절반이다. 나머지 절반은 그 관절각까지 가는 동안 팔이 자기 몸이나 테이블에 부딪히지 않게 경로를 찾는 **모션 플래닝**이다. MoveIt 2는 이 둘을 실제로 돌려 주는 프레임워크이고, `moveit_py` 라는 파이썬 바인딩으로 이 책 전체에서 배운 것 — 객체와 별칭([1.1](#/objects-names)), 실행자와 콜백([10.3](#/rclpy-node)), 좌표 변환([10.9 TF2](#/tf2)), 행렬 계산([9.4 선형대수](#/linalg)) — 이 한곳에 모인다.
:::

## 순기구학과 역기구학 — 방향이 다르면 난이도가 다르다

로봇 팔의 관절이 $n$ 개라고 하자. 각 관절의 회전각을 $\theta_1, \theta_2, \dots, \theta_n$ 이라 쓰면, 팔 끝(엔드이펙터)의 위치와 자세는 이 각도들의 함수다.

$$\text{pose} = f(\theta_1, \theta_2, \dots, \theta_n)$$

**이 방향, 관절각에서 위치를 구하는 것이 순기구학(forward kinematics, FK)이다.** 각 링크의 길이와 관절의 회전을 순서대로 곱해 나가는 행렬 연산일 뿐이라, 계산이 명확하고 항상 유일한 답이 나온다. 관절각을 알면 손끝이 어디 있는지는 무조건 계산된다.

```text nolines
FK: (theta_1, theta_2, ..., theta_n)  ──▶  pose (x, y, z, orientation)
    <- 순기구학. 관절각을 넣으면 손끝 위치가 나온다. 유일한 답, 계산이 싸다.

IK: pose (x, y, z, orientation)  ──▶  (theta_1, theta_2, ..., theta_n)
    <- 역기구학. 손끝 위치를 넣으면 관절각을 구한다. 답이 0개, 1개, 여러 개일 수 있다.
```

**역기구학(inverse kinematics, IK)은 그 반대다.** "손끝이 여기 있으려면 관절들이 몇 도씩 꺾여야 하는가." 언뜻 대칭적인 문제처럼 보이지만 난이도가 완전히 다르다. $f$ 는 비선형 함수(회전에 sin·cos가 곱으로 얽혀 있다)라서, 역함수 $f^{-1}$ 이 깔끔한 공식으로 안 나오는 경우가 대부분이다. 그리고 결정적으로, **해가 몇 개인지가 상황마다 다르다.**

### 왜 해가 여러 개이거나 없을 수 있는가

2차원 평면 위에 관절이 두 개뿐인 팔로 직접 확인해 보자. 링크 길이가 각각 $l_1, l_2$ 이고, 목표 좌표 $(x, y)$ 까지의 거리가 $d$ 라면 코사인 법칙으로 두 번째 관절각을 구할 수 있다.

```python title="2관절 평면 팔의 IK — 해의 개수가 왜 다른가"
import math


def fk(l1, l2, t1, t2):
    """관절각 -> 엔드이펙터 위치. 유일한 답."""
    x1 = l1 * math.cos(t1)
    y1 = l1 * math.sin(t1)
    x2 = x1 + l2 * math.cos(t1 + t2)
    y2 = y1 + l2 * math.sin(t1 + t2)
    return x2, y2


def ik(l1, l2, x, y):
    """목표 위치 -> 관절각 후보 목록. 0개, 1개, 2개가 나올 수 있다."""
    d2 = x * x + y * y
    d = math.sqrt(d2)
    if d > l1 + l2 or d < abs(l1 - l2):
        return []  # 도달 불가능 — 해가 없다

    cos_t2 = (d2 - l1 * l1 - l2 * l2) / (2 * l1 * l2)
    cos_t2 = max(-1.0, min(1.0, cos_t2))  # 부동소수점 오차로 [-1, 1]을 벗어나는 것 방지
    t2_candidate = math.acos(cos_t2)

    solutions = []
    for t2 in (t2_candidate, -t2_candidate):  # 팔꿈치를 위로 굽히거나 아래로 굽히거나
        k1 = l1 + l2 * math.cos(t2)
        k2 = l2 * math.sin(t2)
        t1 = math.atan2(y, x) - math.atan2(k2, k1)
        solutions.append((t1, t2))
    return solutions


l1, l2 = 1.0, 1.0

for x, y, label in [(1.2, 0.6, "일반 위치"), (3.0, 0.0, "팔 길이 합보다 멀다"), (2.0, 0.0, "완전히 뻗은 경계")]:
    sols = ik(l1, l2, x, y)
    print(f"{label} 목표=({x}, {y}) -> 해 {len(sols)}개")
    for t1, t2 in sols:
        fx, fy = fk(l1, l2, t1, t2)
        print(f"  t1={math.degrees(t1):6.2f}도  t2={math.degrees(t2):6.2f}도  (FK로 되짚으면 {fx:.4f}, {fy:.4f})")
```

```text nolines
일반 위치 목표=(1.2, 0.6) -> 해 2개
  t1= -21.30도  t2=  95.74도  (FK로 되짚으면 1.2000, 0.6000)
  t1=  74.43도  t2= -95.74도  (FK로 되짚으면 1.2000, 0.6000)
팔 길이 합보다 멀다 목표=(3.0, 0.0) -> 해 0개
완전히 뻗은 경계 목표=(2.0, 0.0) -> 해 2개
  t1=   0.00도  t2=   0.00도  (FK로 되짚으면 2.0000, 0.0000)
  t1=   0.00도  t2=  -0.00도  (FK로 되짚으면 2.0000, 0.0000)
```

(위는 실제로 이 환경의 Python 3.14로 실행해서 나온 출력이다.) 세 가지가 한 번에 보인다.

- **같은 목표에 해가 2개**: 팔꿈치를 위로 굽힌 자세와 아래로 굽힌 자세가 둘 다 손끝을 같은 곳에 놓는다. 로봇에 "여기로 가라"고만 하면 어느 쪽을 골라야 할지는 IK 함수가 정하지 않는다.
- **해가 0개**: 목표가 팔이 닿을 수 있는 범위(작업공간, workspace) 밖이면 아무리 관절을 꺾어도 갈 수 없다. 코사인 법칙의 입력이 $[-1, 1]$ 범위를 벗어나 `acos` 가 정의되지 않는 것으로 드러난다.
- **경계에서는 해가 겹친다**: 팔을 완전히 뻗은 지점(작업공간의 경계)에서는 팔꿈치를 위로 굽히나 아래로 굽히나 같은 자세로 수렴한다 — 이게 **특이점**(singularity)이다. 이 근처에서는 목표를 살짝만 옮겨도 필요한 관절 속도가 무한대로 치솟는다.

::: deep 관절이 6개, 7개로 늘어나면
방금 예제는 관절 2개짜리 평면 팔이라 코사인 법칙으로 닫힌 형태 해(closed-form solution)를 구했다. 산업용 로봇 팔처럼 관절 6개가 3차원에서 움직이면, 관절 배치가 딱 맞아떨어지는 경우(마지막 세 축이 한 점에서 만나는 "손목 분리" 구조)에만 닫힌 형태 해가 존재한다. 관절이 7개(중복 자유도, redundant DOF)면 같은 손끝 자세에 도달하는 팔꿈치 자세가 **무한히 많아진다** — 사람 팔로 컵을 쥔 채 팔꿈치만 위아래로 흔들어 보면 그 감각이다. 이런 경우 MoveIt은 수치적으로 반복해서 답을 좁혀 가는 IK 솔버(KDL 기반의 반복 자코비안法, 또는 TRAC-IK 같은 수치 최적화 솔버)를 쓴다. **수치 솔버는 초기값에 따라 다른 해로 수렴하고, 수렴을 보장하지 못할 수도 있다.** "IK가 실패했다"는 로그를 만나면 목표가 진짜 도달 불가능한 것인지, 초기 관절 상태가 나빠서 솔버가 못 찾은 것인지부터 구분해야 한다.
:::

## MoveIt 2의 아키텍처

MoveIt 2는 하나의 거대한 노드가 아니라, 역할이 나뉜 몇 개의 구성 요소가 [10.4 토픽](#/topics)과 [10.5 서비스](#/services), [10.6 액션](#/actions)으로 통신하는 구조다.

```text nolines
user code (moveit_py / MoveItPy)
        │
        ▼  action, service 요청
   ┌───────────────┐
   │  move_group    │   <- 플래닝을 조율하는 중앙 노드
   └───────────────┘
        │
   ┌────┴────────────────────────┐
   ▼                             ▼
planning scene monitor      planning pipeline
(충돌 검사용 환경 모델)       (OMPL / Pilz / CHOMP 등)
```

**`move_group` 노드**가 중심이다. 사용자 코드(`moveit_py`)나 RViz의 Motion Planning 플러그인이 여기에 "이 자세로 가는 계획을 짜 달라"는 요청을 액션이나 서비스로 보내면, `move_group` 이 아래 구성 요소들을 조율해서 답을 만든다.

**플래닝 씬(planning scene)**은 로봇 자신의 형상([10.10 URDF](#/urdf)에서 정의한 링크와 충돌 지오메트리), 로봇이 인식한 주변 장애물(카메라·LiDAR에서 들어온 [10.12 센서 데이터](#/sensors)를 옥트리로 합친 것), 그리고 사용자가 코드로 직접 추가한 충돌 객체(테이블, 상자 등)를 합친 **하나의 세계 모델**이다. 모션 플래닝은 이 씬 안에서 "부딪히지 않는 경로"를 찾는 문제로 정의된다. 플래닝 씬은 `/monitored_planning_scene` 토픽으로 계속 갱신되며, RViz가 이걸 구독해서 로봇 주변에 반투명한 충돌 형상을 그려 준다.

::: warn 플래닝 씬이 낡아 있으면 계획은 성공하는데 로봇은 부딪힌다
플래닝 씬은 **센서가 마지막으로 본 순간의 스냅샷**이다. 카메라가 가려지거나 갱신 주기가 느리면, 방금 누가 팔 앞에 놓은 상자를 씬이 아직 모른다. 이 상태에서 계획을 요청하면 충돌 검사기는 "장애물 없음"으로 판단하고 완벽하게 유효한 궤적을 내놓는다 — 그런데 그 궤적이 실제 세계에서는 방금 놓인 상자를 관통한다. **플래닝이 성공했다는 것은 "플래닝 씬 기준으로" 안전하다는 뜻이지, 실제 세계 기준이 아니다.** 실행 직전 씬이 최신인지 확인하는 습관이 여기서 갈린다.
:::

## 모션 플래닝: 관절각 공간에서 길을 찾는다

IK로 목표 관절각을 구했다고 끝이 아니다. 지금 자세에서 목표 자세까지 **관절들을 어떻게 움직여야** 도중에 아무것도 안 부딪히는지가 남는다. 관절이 $n$ 개면 이 문제는 $n$ 차원 공간(configuration space, C-space)에서 "충돌하는 영역을 피해 시작점에서 목표점까지 가는 경로"를 찾는 문제가 된다.

이 공간을 격자로 쪼개서 촘촘히 탐색하는 건 관절이 몇 개만 넘어가도 차원의 저주에 걸린다. 관절 6개를 각 10도 단위로만 쪼개도 $36^6 \approx 22$억 개의 격자점이 나온다. 그래서 MoveIt이 기본으로 쓰는 **OMPL**(Open Motion Planning Library)은 격자를 다 훑는 대신 **무작위로 점을 뽑아 가며 길을 만드는 샘플링 기반(sampling-based) 알고리즘**을 쓴다.

가장 널리 쓰이는 **RRT**(Rapidly-exploring Random Tree) 계열의 동작 방식은 이렇다.

1. 시작 관절각을 트리의 뿌리로 둔다.
2. C-space에서 무작위 점을 하나 뽑는다.
3. 트리에서 그 점에 가장 가까운 노드를 찾는다 — 이건 [7.10 트리](#/tree)에서 본 최근접 탐색과 같은 문제다.
4. 그 노드에서 무작위 점 방향으로 정해진 만큼만 뻗어서 새 노드를 만든다.
5. 새 노드까지의 짧은 구간이 충돌 검사를 통과하면 트리에 추가한다. 실패하면 버린다.
6. 목표 근처에 도달할 때까지, 또는 시간 제한이 될 때까지 반복한다.

::: deep RRT는 "최선"이 아니라 "빠르게 아무 답"을 찾는다
RRT가 찾는 경로는 **충돌 없는 경로 중 하나**일 뿐, 최단 경로라는 보장이 없다. 실제로 초기 RRT 경로는 삐뚤빼뚤하다. `RRTConnect`(양쪽 끝에서 트리를 동시에 뻗어 서로 만나게 하는 변형)는 속도를 더 올린 버전이고, `RRT*` 는 시간을 더 쓰는 대신 점근적으로 최적 경로에 가까워지는 변형이다. **MoveIt 전체의 "기본 플래너"라고 못 박을 수 있는 단일 알고리즘은 없다** — `moveit/moveit_resources` 저장소의 Panda 데모 설정(`panda_moveit_config/config/ompl_planning.yaml`)을 보면 `panda_arm` 그룹 하나에만도 `RRTConnectkConfigDefault`를 포함해 24가지 플래너 구성이 나열돼 있고, 그중 실제로 무엇이 쓰이는지는 `move_group`에 넘기는 요청(`planner_id`)이 정한다. 다만 `RRTConnect`는 여러 공식 데모·튜토리얼에서 기본값으로 선택돼 있어서 사실상 "제일 먼저 마주치는 플래너"이기는 하다. MoveIt은 계획이 끝난 뒤 **경로 단순화(shortcutting)** 단계를 거쳐 불필요하게 꺾인 구간을 직선으로 편다 — 이게 없으면 로봇 팔이 눈에 띄게 부자연스럽게 떨었을 것이다.

이 탐색 구조는 [7.18 백트래킹](#/backtracking)에서 본 "가지치기를 하며 트리를 뻗어 나가는" 감각과 본질적으로 같다. 차이는 백트래킹이 결정적으로 모든 분기를 체계적으로 훑는 데 반해, RRT는 **무작위성**으로 그 넓은 공간을 감당한다는 점이다. 그래서 같은 시작·목표에 대해 같은 플래너를 두 번 돌려도 **다른 경로**가 나올 수 있다. 재현성이 필요한 테스트에서는 난수 시드를 고정해야 한다.
:::

::: perf 관절각 계산을 파이썬 반복문 대신 NumPy로
FK 자체는 행렬 곱셈의 연속이다. 궤적 하나에 웨이포인트가 수백 개씩 있을 때, 각 지점마다 파이썬 함수 호출로 FK를 계산하는 것과 [9.2 브로드캐스팅](#/broadcasting)으로 한꺼번에 계산하는 것의 차이를 실측해 보자.

```python title="FK 배치 계산 — 반복문 vs 벡터화"
import math
import time
import numpy as np


def fk_loop(l1, l2, thetas1, thetas2):
    out = []
    for t1, t2 in zip(thetas1, thetas2):
        x = l1 * math.cos(t1) + l2 * math.cos(t1 + t2)
        y = l1 * math.sin(t1) + l2 * math.sin(t1 + t2)
        out.append((x, y))
    return out


def fk_vectorized(l1, l2, thetas1, thetas2):
    x = l1 * np.cos(thetas1) + l2 * np.cos(thetas1 + thetas2)
    y = l1 * np.sin(thetas1) + l2 * np.sin(thetas1 + thetas2)
    return x, y


n = 100_000
thetas1 = [i * 0.0001 for i in range(n)]
thetas2 = [i * 0.0002 for i in range(n)]
arr1 = np.array(thetas1)
arr2 = np.array(thetas2)

t0 = time.perf_counter()
fk_loop(1.0, 1.0, thetas1, thetas2)
t1 = time.perf_counter()
fk_vectorized(1.0, 1.0, arr1, arr2)
t2 = time.perf_counter()

print(f"반복문: {t1 - t0:.4f}초")
print(f"벡터화: {t2 - t1:.4f}초")
print(f"배수: {(t1 - t0) / (t2 - t1):.1f}배")
```

```text nolines
반복문: 0.0220초
벡터화: 0.0019초
배수: 11.4배
```

(Python 3.14 / Windows 기준 10만 개 웨이포인트 실측. 같은 스크립트를 5번 다시 돌려도 반복문은 0.021~0.024초, 벡터화는 0.0019~0.0023초 사이를 오갔고, 배수는 매번 10~12배 선이었다. 절대값과 배수는 기기·파이썬 버전·NumPy 빌드마다 달라진다 — "몇 배"라는 숫자 자체보다 "벡터화가 자릿수 하나만큼은 항상 빠르다"는 방향성만 챙기면 된다.) 궤적 로그를 분석하거나 여러 IK 후보를 한꺼번에 평가할 때, 파이썬 반복문으로 짜기 쉽다고 그대로 두면 이 정도 배수를 그냥 버리는 것이다.
:::

## moveit_py — MoveIt 2의 파이썬 API

ROS 1 시절 `moveit_commander` 를 써 봤다면, ROS 2의 공식 파이썬 바인딩은 `moveit_py` 라는 별도 패키지로 다시 만들어졌다는 걸 알아 둬야 한다. 핵심 클래스는 `MoveItPy` 와 `PlanningComponent` 다. 아래는 MoveIt 공식 튜토리얼 저장소(`moveit/moveit2_tutorials`, `motion_planning_python_api_tutorial.py`)를 대조해서 옮긴 코드다 — 클래스명·메서드명·인자명(`MoveItPy(node_name=...)`, `get_planning_component`, `set_start_state_to_current_state()`, `set_goal_state(pose_stamped_msg=..., pose_link=...)`, `plan()`, `robot.execute(trajectory, controllers=[])`)은 원문과 정확히 일치하되, 원문의 `plan_and_execute` 함수가 받는 `single_plan_parameters`, `multi_plan_parameters` 같은 추가 매개변수는 이 절에서는 생략하고 `sleep_time`만 쓰는 축약판으로 실었다. **이 책 환경에는 rclpy/moveit_py가 설치돼 있지 않아 직접 실행해서 검증할 수는 없고, 공식 저장소의 코드와 문서를 대조해 옮겼다.**

```python title="moveit_py 기본 패턴 (공식 튜토리얼 기반)"
import rclpy
from rclpy.logging import get_logger

from moveit.core.robot_state import RobotState
from moveit.planning import MoveItPy


def plan_and_execute(robot, planning_component, logger, sleep_time=0.0):
    """계획을 세우고, 성공하면 실행한다."""
    logger.info("Planning trajectory")
    plan_result = planning_component.plan()

    if plan_result:
        logger.info("Executing plan")
        robot_trajectory = plan_result.trajectory
        robot.execute(robot_trajectory, controllers=[])
    else:
        logger.error("Planning failed")


def main():
    rclpy.init()
    logger = get_logger("moveit_py.pose_goal")

    # MoveItPy 인스턴스 하나가 move_group과의 연결을 감싼다
    panda = MoveItPy(node_name="moveit_py")
    panda_arm = panda.get_planning_component("panda_arm")  # 플래닝 그룹 이름

    # 시작 상태: 현재 로봇 상태 그대로
    panda_arm.set_start_state_to_current_state()

    # 목표: PoseStamped 메시지로 손끝 위치와 자세를 지정
    from geometry_msgs.msg import PoseStamped

    pose_goal = PoseStamped()
    pose_goal.header.frame_id = "panda_link0"
    pose_goal.pose.orientation.w = 1.0
    pose_goal.pose.position.x = 0.28
    pose_goal.pose.position.y = -0.2
    pose_goal.pose.position.z = 0.5
    panda_arm.set_goal_state(pose_stamped_msg=pose_goal, pose_link="panda_link8")

    plan_and_execute(panda, panda_arm, logger, sleep_time=3.0)


if __name__ == "__main__":
    main()
```

읽는 순서가 곧 문제 해결 순서다. **(1)** `MoveItPy` 인스턴스가 `move_group` 과의 통신을 감싼다. **(2)** `get_planning_component("panda_arm")` 으로 URDF에 정의된 특정 관절 그룹(SRDF의 플래닝 그룹)을 골라낸다. **(3)** `set_start_state_to_current_state()` 로 시작점을 정한다 — 이걸 빠뜨리면 이전 계획이 끝난 위치가 아니라 엉뚱한 기본값에서 계획이 시작될 수 있다. **(4)** `set_goal_state()` 는 목표를 여러 형태로 받는다 — 미리 정의된 자세 이름(`configuration_name`), `RobotState` 객체, `PoseStamped` 메시지, 관절 제약 조건까지. **(5)** `plan()` 은 성공하면 `trajectory` 를 담은 결과 객체를, 실패하면 falsy한 값을 반환한다. **(6)** `execute()` 가 실제 컨트롤러에 궤적을 보낸다.

::: note 왜 `plan` 과 `execute` 가 분리돼 있는가
계획 따로, 실행 따로인 데는 이유가 있다. 시뮬레이션이나 RViz 미리보기로 궤적을 **먼저 확인**하고, 사람이 승인한 뒤에 실제 하드웨어에 보내는 워크플로를 강제하기 위해서다. `plan()` 이 반환하는 궤적을 검사(속도 한계 초과 여부, 예상 밖의 큰 관절 이동 등)한 뒤에만 `execute()` 를 부르는 것이 실전에서 안전한 패턴이다.
:::

::: warn RobotState 객체를 함부로 공유하지 마라
`RobotState` 는 [1.1 객체, 이름, 참조](#/objects-names)에서 다룬 가변 객체다. `robot_state = RobotState(robot_model)` 로 만든 뒤 이 객체를 여러 함수에 그대로 넘기면, 한 함수가 `robot_state.set_to_random_positions()` 로 값을 바꾼 게 다른 곳에서도 그대로 보인다 — 별칭 문제가 로봇 팔의 관절값에서 그대로 재현된다. "목표 자세를 여러 개 시도해 보려고 같은 `RobotState` 를 재활용했는데 이전 시도의 값이 남아 있었다"는 버그는 흔하다. 새 후보가 필요하면 `RobotState(robot_model)` 로 매번 새로 만들거나, 명시적으로 값을 복사해라.
:::

## 그리퍼와 파지

팔이 목표 자세에 도달하는 것과 물건을 실제로 쥐는 것은 다른 문제다. **그리퍼(gripper)** 는 대개 팔과는 별도의 플래닝 그룹으로 URDF/SRDF에 정의되고, MoveIt은 이걸 여닫는 것 자체는 단순한 관절 이동으로 다룬다(그리퍼도 `PlanningComponent` 하나로 취급되거나, 컨트롤러에 직접 열림/닫힘 명령을 보낸다). 어려운 부분은 그 앞뒤다.

- **파지 자세 생성(grasp pose generation)**: 물체의 어느 면을, 어느 각도로, 어느 깊이까지 집을지 정하는 것. 물체 모양과 그리퍼 폭에 따라 후보가 여러 개 나오고, 각 후보에 대해 IK가 풀리는지 + 충돌이 없는지를 다시 검사해야 한다.
- **부착(attach)**: 물체를 쥔 순간, 플래닝 씬 안에서 그 물체를 로봇의 일부로 취급하도록 바꿔야 한다. 그래야 팔을 옮기는 동안 "손에 쥔 물체가 자기 자신과 충돌한다"는 오탐이 나지 않고, 반대로 "쥔 물체가 주변 장애물과 충돌하는지"는 계속 검사된다. 물체를 놓을 때는 반대로 다시 분리(detach)한다.
- **힘 제어**: MoveIt의 모션 플래닝 자체는 위치·궤적을 다루지, 그리퍼가 물체를 얼마나 세게 쥐는지는 다루지 않는다. 그건 그리퍼 드라이버나 별도의 힘/토크 제어 루프의 몫이다.

::: cote 파지 후보를 순위 매기는 문제
물체를 집을 수 있는 파지 후보가 여러 개 나왔을 때 "어느 것부터 시도할까"는 정렬 문제다. 접근 각도가 현재 팔 자세에서 가까운 순서, IK가 풀릴 확률이 높은 순서, 충돌 여유(clearance)가 큰 순서 등 여러 기준을 합친 점수로 [7.4 정렬](#/sorting)하고, 위에서부터 하나씩 IK와 충돌 검사를 통과하는 첫 번째 후보를 채택하는 방식이 실전에서 흔히 쓰인다. 모든 후보의 IK를 다 풀어 보는 건 낭비다 — 앞에서 이미 실패를 확인한 자세와 비슷한 후보는 건너뛰는 가지치기가 [7.18 백트래킹](#/backtracking)의 감각과 같다.
:::

## 실전에서 자주 틀리는 것들

MoveIt을 처음 붙일 때 겪는 사고는 몇 가지로 수렴한다.

::: danger "Planning failed" 인데 코드는 맞아 보인다
가장 흔한 원인 셋. **(1)** 목표 자세가 작업공간 밖이거나 특이점 근처다 — 위에서 본 IK의 "해 없음"이 여기서 조용히 재현된다. **(2)** 플래닝 씬에 예상 못 한 충돌 객체가 남아 있다 — 이전 실행에서 추가한 충돌 물체를 지우지 않고 다음 실행을 하면 로봇이 자기가 만든 유령 장애물에 막힌다. **(3)** 플래닝 시간 제한이 너무 짧다 — 샘플링 기반 알고리즘은 시간이 더 있으면 찾을 수도 있는 경로를 시간 제한에 걸려 포기한다. 에러 메시지가 세 경우 모두 비슷하게 뭉뚱그려 나오는 경우가 많아서, 어느 원인인지는 플래닝 씬을 RViz로 직접 들여다보고 확인해야 한다.
:::

::: warn 좌표계를 착각하면 계획은 성공하고 팔이 엉뚱한 곳으로 간다
`PoseStamped.header.frame_id` 를 빠뜨리거나 잘못 지정하면, 숫자는 똑같은데 기준 좌표계가 다른 곳을 가리킨다. [10.9 TF2](#/tf2)에서 다룬 프레임 트리 문제가 여기서도 그대로 나타난다 — `panda_link0`(로봇 베이스) 기준 좌표를 카메라 프레임 기준으로 착각해서 넘기면, IK도 플래닝도 전부 "성공"하지만 팔은 사용자가 의도한 곳이 아니라 그 프레임이 실제로 가리키는 곳으로 움직인다. 계획이 실패하는 것보다 **성공했는데 틀린 경우**가 디버깅하기 훨씬 어렵다.
:::

::: hist 왜 MoveIt 1의 moveit_commander가 아니라 moveit_py인가
ROS 1의 `moveit_commander` 는 파이썬에서 C++ MoveGroupInterface를 감싼 얇은 래퍼였다. ROS 2로 넘어오면서 MoveIt 팀은 파이썬 바인딩을 pybind11 기반으로 다시 설계해 `moveit_py` 로 냈고, `MoveItPy`/`PlanningComponent` 라는 새 이름의 API가 됐다 — 이 계보 자체는 ROS 커뮤니티에서 널리 통용되는 사실이지만, 이 책에서 1차 문서(공식 마이그레이션 가이드)로 재확인하지는 못했으니 정확한 버전별 시점이 궁금하면 `moveit/moveit2_tutorials` 저장소의 변경 이력을 직접 찾아보는 게 좋다. 오래된 블로그나 스택오버플로 답변에서 `moveit_commander` 나 `MoveGroupCommander` 를 보게 되면, 그건 ROS 1 코드이거나 ROS 2에서도 남아 있는 C++ `MoveGroupInterface` 를 가리키는 것이지 이 절에서 다룬 `moveit_py` 가 아니다. ROS 생태계 전반이 이렇게 "이름은 비슷한데 세대가 다른" 자료가 뒤섞여 있어서, 문서를 볼 때 ROS 1인지 2인지부터 확인하는 습관이 필요하다.

이 절의 `moveit_py` 예제는 `moveit2_tutorials` 저장소의 `main`(Rolling을 추적하는) 브랜치를 대조해서 만들었다 — 이 책이 기준으로 삼는 최신 LTS(Jazzy 이후)를 겨냥한 `jazzy` 전용 브랜치는 이 저장소에 따로 존재하지 않는다. `MoveItPy`/`PlanningComponent`의 핵심 API는 배포판이 바뀌어도 잘 안 흔들리는 편이지만, 실제 배포판에 설치해 쓸 때는 그 배포판의 `moveit2_tutorials` 태그(또는 릴리스 브랜치)를 별도로 확인하는 게 안전하다.
:::

## 요약

- **순기구학(FK)**은 관절각에서 위치를 구한다 — 유일한 답, 계산이 싸다. **역기구학(IK)**은 그 반대라서 어렵다 — 해가 0개(도달 불가능), 1개, 여러 개(팔꿈치 방향 등)일 수 있다.
- MoveIt 2는 `move_group` 노드를 중심으로, **플래닝 씬**(충돌 검사용 세계 모델)과 **플래닝 파이프라인**(OMPL 등)이 협력하는 구조다.
- 기본 모션 플래너 OMPL은 격자 탐색 대신 **샘플링 기반**(RRT, RRTConnect)으로 관절각 공간에서 충돌 없는 경로를 찾는다. 최적 경로가 아니라 "빠르게 찾은 유효한 경로"다.
- 파이썬 API는 `moveit_py`(`MoveItPy`, `PlanningComponent`)다. `set_start_state` → `set_goal_state` → `plan()` → `execute()` 순서가 기본 골격이다.
- 플래닝 씬이 낡았거나 좌표계를 착각하면, **계획은 성공하는데 실제로는 틀리거나 위험한** 궤적이 나온다 — 계획 실패보다 이쪽이 더 위험하다.
- 파지는 IK·충돌 검사에 더해 **부착/분리(attach/detach)** 로 플래닝 씬을 갱신하는 과정이 따라붙는다.

::: quiz 연습문제
1. 링크 길이 $l_1 = 0.5, l_2 = 0.3$ 인 2관절 평면 팔에서, 목표 $(0.9, 0.0)$ 은 해가 몇 개인가? 본문의 `ik` 함수를 고쳐서 직접 확인하라. (힌트: $l_1 + l_2$ 와 비교하라.)
2. 본문의 `ik` 함수가 반환하는 두 해 중 하나를 골라 `fk` 로 되짚었을 때 원래 목표와 정확히 같지 않고 아주 작은 오차가 남는 경우가 있다. 왜 그런지 부동소수점 관점에서 설명하라.
3. `set_start_state_to_current_state()` 를 호출하지 않고 `plan()` 을 두 번 연달아 부르면 어떤 문제가 생길 수 있는가? 본문의 어떤 원칙과 연결되는가?
4. RRT와 [7.18 백트래킹](#/backtracking)의 트리 탐색은 어떤 점에서 같고, 어떤 점에서 다른가? 최소 두 가지씩 써라.
5. 파지 후보 10개 중 IK가 풀리는 후보를 찾고 싶다. 후보를 무작위 순서로 시도하는 것과, 접근 각도가 현재 팔 자세와 가까운 순서로 정렬해서 시도하는 것 중 무엇이 평균적으로 더 빠를지, 그리고 왜 그런지 설명하라.
:::

**다음 절**: [10.15 rosbag, 디버깅, 성능](#/ros-debug) — 팔이 계획대로 안 움직였을 때, 그 순간을 기록하고 되감아 원인을 찾는 법.
