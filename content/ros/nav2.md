# 10.13 Nav2 자율주행

::: lead
[10.9 TF2](#/tf2)에서 로봇은 자기 팔다리가 어디 있는지 아는 법을 배웠다. 이 절은 그 다음 질문이다 — **로봇은 자기가 서 있는 방이 어떻게 생겼는지, 그리고 그 방 안에서 자기가 어디에 있는지 어떻게 아는가.** 지도가 없으면 갈 곳을 못 정하고, 위치를 모르면 지도가 있어도 소용없다. Nav2는 이 두 문제와, 그 위에 얹히는 "어디로 어떻게 갈 것인가"까지 통째로 푸는 스택이다. 겉보기엔 `goToPose()` 한 줄이지만 그 아래에는 지도를 만드는 SLAM, 장애물을 격자로 표현하는 코스트맵, 경로를 계산하는 전역 플래너, 그 경로를 실시간으로 따라가는 지역 컨트롤러, 그리고 이 전부를 조율하는 비헤이비어 트리가 있다. 이 책에서 배운 그래프 탐색([7.13](#/graph)~[7.15](#/shortest-path)), 큐와 콜백([4.1 동시성 모델](#/concurrency-map)), 그리고 액션 프로토콜([10.6 액션](#/actions))이 전부 여기서 실전으로 만난다.
:::

## Nav2가 푸는 문제

로봇에게 "저기로 가"라고 말하는 것은 사람에게는 쉽다. 로봇에게는 최소 세 가지를 순서대로 풀어야 하는 문제다.

1. **지금 여기가 어디 붙어 있는 방인지** — 지도가 있어야 한다.
2. **지도 안에서 내가 지금 어디 있는지** — 위치 추정(localization)이 있어야 한다.
3. **거기서 목표까지 뭘 피해서 어떻게 갈지** — 경로 계획과 실시간 추종이 있어야 한다.

Nav2는 이 세 문제 각각을 담당하는 독립된 서버들의 묶음이다. 하나의 거대한 프로그램이 아니라, [10.6 액션](#/actions)으로 서로 대화하는 **여러 개의 별도 노드**다. 이 구조 자체가 이 절 전체를 관통하는 설계 원칙이다 — 계획을 담당하는 서버가 죽어도 추종 중이던 컨트롤러는 (짧은 시간이나마) 계속 돌 수 있고, 각 서버는 독립적으로 교체·튜닝·재시작할 수 있다.

## 아키텍처: 비헤이비어 트리가 지휘하는 서버들

Nav2 공식 문서는 이 구조를 "행동 트리를 통해 여러 개의 독립적인 모듈형 서버를 조율함으로써 커스터마이즈 가능하고 지능적인 내비게이션 행동을 만든다"고 설명한다.[^1] 핵심 서버는 다음과 같다.

| 서버 | 역할 |
| --- | --- |
| `planner_server` | 전역 경로 계획 (시작점 → 목표점의 전체 경로) |
| `controller_server` | 지역 경로 추종 (그 경로를 따라가며 속도 명령 생성) |
| `behavior_server` | 복구 동작 (막혔을 때 후진, 제자리 회전, 코스트맵 초기화 등) |
| `smoother_server` | 계획된 경로를 부드럽게 다듬기 |
| `bt_navigator` | 위 서버들을 행동 트리로 조율하는 최상위 지휘자 |

이 서버들을 지휘하는 것이 `bt_navigator` 노드다. `NavigateToPose` 같은 상위 액션 요청을 받으면, 이 노드는 **XML로 정의된 행동 트리(behavior tree)** 를 하나 로드해서 매 주기(tick)마다 그 트리를 실행한다. 트리의 리프 노드 하나하나가 `ComputePathToPose`, `FollowPath`, `ClearEntireCostmap` 같은 **또 다른 액션 호출**이다. 즉 `bt_navigator`는 스스로 경로를 계산하지도, 로봇을 움직이지도 않는다. 각 서버에게 "너 일해" 라고 액션 목표를 보내고 결과를 받아서 다음에 뭘 할지 결정할 뿐이다.

```text nolines
                  NavigateToPose 목표
                          │
                          ▼
                  ┌───────────────┐
                  │  bt_navigator │        <- 행동 트리를 tick하는 지휘자
                  └───────┬───────┘
                          │  각각을 액션으로 호출
        ┌─────────┬───────┼────────┬───────────┐
        ▼         ▼       ▼        ▼           ▼
   planner_   controller_ behavior_ smoother_
     server      server     server    server
   (전역 경로)  (지역 추종)  (복구)   (경로 평활)
```

::: note 왜 하나의 거대한 상태 기계가 아니라 트리인가
"계획 실패 시 3번 재시도 후 실패 보고"나 "추종 중 막히면 후진 후 재계획" 같은 로직을 `if`/`else`로 손코딩하면 조건이 몇 개만 늘어도 스파게티가 된다. 행동 트리는 **Sequence**(모두 성공해야 진행)와 **Fallback**(하나만 성공하면 진행, 나머지는 복구 시도)이라는 단 두 가지 조합자로 이런 로직을 선언적으로 표현한다. XML 파일만 바꾸면 "복구 전략"을 코드 재컴파일 없이 바꿀 수 있다는 게 실전에서 진짜 이점이다.
:::

::: tip 직접 실행해서 확인하는 행동 트리의 본질
`bt_navigator`는 내부적으로 [BehaviorTree.CPP](https://www.behaviortree.dev) 라이브러리를 쓰지만, **Sequence/Fallback이 하는 일 자체는 파이썬 30줄로 재현할 수 있다.** 뒤에서 직접 실행해 본다 — rclpy 없이도 Nav2가 "왜 저렇게 재시도하다가 실패로 끝났는지"를 눈으로 볼 수 있다.
:::

## SLAM: 지도를 만들면서 동시에 위치를 추정한다

여기서 닭과 달걀 문제가 나온다. 위치를 알려면 지도가 있어야 하고, 지도를 만들려면 센서가 관측한 것들을 정확한 위치에 붙여야 하는데 그러려면 위치를 알아야 한다. **SLAM**(Simultaneous Localization and Mapping)은 이 순환을 "동시에 둘 다 추정한다"는 방식으로 깬다.

직관적으로 이렇게 진행된다.

1. 로봇이 조금 움직인다. 바퀴 오도메트리와 IMU([10.12 센서 데이터 처리](#/sensors))로 "대충 이만큼 움직였겠다"를 추정한다.
2. LiDAR나 카메라로 주변을 관측한다.
3. 방금 관측한 것이 **이전에 이미 지도에 그려 둔 특징들과 얼마나 잘 들어맞는지**를 비교한다(스캔 매칭).
4. 잘 들어맞도록 위치 추정을 보정하고, 새로 본 부분을 지도에 추가한다.

이 과정에서 오차는 누적된다. 오도메트리만으로 100미터를 이동하면 누적 오차가 미터 단위로 벌어질 수 있다. SLAM은 **루프 클로저(loop closure)** — 로봇이 예전에 지나간 곳을 다시 지나갈 때 "여기 와봤다"를 인식하는 것 — 로 그 누적 오차를 한 번에 되돌린다. ROS 2 생태계에서는 `slam_toolbox` 패키지가 이 역할을 맡고, Nav2 자체는 지도를 **소비**하는 쪽이다.

::: hist SLAM과 순수 위치 추정(AMCL)은 다른 문제다
지도가 이미 있고 로봇 위치만 모르는 상황이라면 SLAM 전체가 필요 없다. **AMCL**(Adaptive Monte Carlo Localization)은 파티클 필터로 "이 지도 위에서 지금 관측과 가장 잘 맞는 위치가 어디인가"만 추정한다. 지도를 만드는 SLAM은 매핑 단계에서 한 번, 매일 반복되는 주행에서는 저장해 둔 지도 위에 AMCL만 도는 것이 일반적인 운영 방식이다. `waitUntilNav2Active()` 같은 API가 `localizer` 인자로 `'amcl'`을 기본값으로 받는 이유가 이것이다 — 지도는 이미 있다고 가정한다.
:::

## 코스트맵: 장애물을 격자로 표현한다

플래너와 컨트롤러가 실제로 들여다보는 것은 지도 그 자체가 아니라 **코스트맵**(costmap)이다. 코스트맵은 세계를 고정 크기 셀의 2차원 격자로 나누고, 각 셀에 "여기로 로봇 중심이 지나가는 게 얼마나 위험한가"를 0~255 사이의 정수 하나로 담는다. `nav2_costmap_2d`가 정의하는 특수 값들이 있다.

| 값 | 의미 |
| --- | --- |
| `FREE_SPACE` (0) | 완전히 비어 있음 |
| `INSCRIBED_INFLATED_OBSTACLE` (253) | 로봇의 내접원 반경 안 — 여기 중심을 두면 반드시 부딪힘 |
| `LETHAL_OBSTACLE` (254) | 장애물 그 자체 |
| `NO_INFORMATION` (255) | 아직 관측하지 못한 미지 영역 |

코스트맵은 **레이어**를 쌓아서 만든다. 대표적으로 세 겹이다.

- **정적 레이어(static layer)** — SLAM이 만든(또는 저장해 둔) 지도에서 벽 같은 고정 장애물을 가져온다.
- **장애물 레이어(obstacle layer)** — LiDAR나 포인트클라우드가 지금 이 순간 감지한 동적 장애물을 얹는다.
- **인플레이션 레이어(inflation layer)** — 장애물 주변에 "여기도 위험하다"는 비용을 거리에 따라 지수적으로 퍼뜨린다.

인플레이션이 핵심이다. 로봇은 점이 아니라 부피가 있으므로, 벽에서 딱 붙어 지나가는 경로를 플래너가 고르면 실제로는 충돌한다. 인플레이션 레이어는 장애물로부터의 거리 $d$에 로봇의 내접 반경(inscribed radius)과 감쇠 계수(cost scaling factor)를 적용해 비용을 계산한다.[^2]

$$\text{cost}(d) = \begin{cases} 254 & d = 0 \\ 253 & d \le r_{\text{inscribed}} \\ 252 \cdot e^{-\,\alpha (d - r_{\text{inscribed}})} & d > r_{\text{inscribed}} \end{cases}$$

말로 풀면 이렇다. 장애물에 딱 붙으면 최댓값, 로봇이 확실히 부딪힐 거리 안이면 두 번째로 높은 고정값, 그보다 멀어지면 거리에 따라 **지수적으로** 비용이 줄어든다. 여기서 계수 252는 `INSCRIBED_INFLATED_OBSTACLE - 1`이다 — 253(그 자체) 대신 253보다 1 작은 값에서 지수 감쇠를 시작해야, 감쇠 구간의 최댓값이 "내접 반경 안" 고정값 253과 겹치지 않고 딱 그 밑에서 이어진다. 이 공식을 순수 파이썬으로 그대로 재현해서, BFS로 거리를 구하고 셀마다 비용을 매겨 보자 ([7.14 BFS/DFS 응용](#/bfs-dfs)의 다중 시작점 BFS와 정확히 같은 패턴이다 — 장애물 셀 전부를 큐에 넣고 동시에 확산시킨다).

```python title="inflation_demo.py — 실제로 실행한 결과"
import math
from collections import deque

LETHAL_OBSTACLE = 254
INSCRIBED_INFLATED_OBSTACLE = 253


def inflate(grid, resolution, inscribed_radius, cost_scaling_factor):
    rows, cols = len(grid), len(grid[0])
    dist = [[math.inf] * cols for _ in range(rows)]
    q = deque()
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == LETHAL_OBSTACLE:
                dist[r][c] = 0
                q.append((r, c))          # ✅ 장애물 전부를 동시에 큐에 넣는다 (다중 시작점 BFS)

    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and dist[nr][nc] > dist[r][c] + 1:
                dist[nr][nc] = dist[r][c] + 1
                q.append((nr, nc))

    cost = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            d = dist[r][c]
            if d == 0:
                cost[r][c] = LETHAL_OBSTACLE
            elif d * resolution <= inscribed_radius:
                cost[r][c] = INSCRIBED_INFLATED_OBSTACLE
            else:
                factor = math.exp(-cost_scaling_factor * (d * resolution - inscribed_radius))
                cost[r][c] = int((INSCRIBED_INFLATED_OBSTACLE - 1) * factor)
    return cost


grid = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 254, 0, 0, 0, 0],   # 장애물 한 칸
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
]

for row in inflate(grid, resolution=0.1, inscribed_radius=0.2, cost_scaling_factor=3.0):
    print(" ".join(f"{v:3d}" for v in row))
```

```text nolines
102 138 186 253 186 138 102  75
138 186 253 253 253 186 138 102
186 253 253 254 253 253 186 138
138 186 253 253 253 186 138 102
102 138 186 253 186 138 102  75
```

(Python 3.14.5 기준 실측. 격자 해상도 0.1m, 내접 반경 0.2m — 장애물에서 2칸 이내는 전부 253으로 고정되고, 그 바깥은 지수적으로 감쇠하는 것이 숫자로 보인다.)

::: perf 코스트맵은 매 주기마다 다시 계산되지 않는다
전역 코스트맵은 지도 크기 전체를 담기 때문에 크다. 매번 전체를 다시 인플레이션하면 느리다. 실제 구현은 **변경된 셀 주변만** 갱신하는 롤링 윈도우/부분 업데이트 전략을 쓴다. 지역 코스트맵은 애초에 로봇 주변 몇 미터짜리 작은 창(rolling window)만 유지해서, 크기 자체를 작게 유지하는 쪽을 택한다.
:::

::: cote 이분 탐색이 아니라 다중 시작점 BFS인 이유
단일 시작점에서의 최단 거리라면 이분 탐색이 낄 자리가 없다. 여기서 구하는 것은 "**모든 장애물 셀 중 가장 가까운 것까지의 거리**"다. 장애물이 여러 개일 때 각각에서 따로 BFS를 돌리고 최솟값을 취하면 $O(k \cdot n)$인데, 장애물 전부를 큐의 초기 상태로 한꺼번에 넣고 한 번만 BFS를 돌리면 $O(n)$이다. 여러 시작점에서 동시에 물이 차오르듯 퍼진다고 생각하면 된다 — [7.13 그래프 표현과 순회](#/graph)에서 이 패턴을 "0-1 BFS"의 이웃 사례로 다시 만난다.
:::

## 전역 플래너와 지역 컨트롤러: 역할을 왜 나누는가

코스트맵이 전역/지역 두 장인 이유는 플래너와 컨트롤러가 완전히 다른 시간 스케일에서 일하기 때문이다.

**전역 플래너**(`planner_server`)는 시작점에서 목표점까지 **전체 경로**를 계산한다. 정적 장애물만 반영된 전역 코스트맵 위에서 $A^*$나 Dijkstra 계열 알고리즘([7.15 최단 경로](#/shortest-path))으로 최적 경로 하나를 뽑는다. 지도 전체를 훑어야 하니 무겁고, 그래서 목표가 바뀌거나 경로를 크게 벗어났을 때만, 즉 초당 몇 번 수준의 낮은 빈도로 다시 계산한다.

**지역 컨트롤러**(`controller_server`)는 그 전역 경로를 "지금 이 순간 어떤 속도 명령(선속도·각속도)을 낼 것인가"로 변환한다. 로봇 바로 앞의 작은 지역 코스트맵만 보되, 이 코스트맵에는 지금 막 LiDAR가 감지한 사람이나 카트 같은 **동적 장애물**이 실시간으로 얹혀 있다. 그래서 컨트롤러는 초당 수십 번씩 다시 계산한다 — 정확한 값은 `controller_server`의 `controller_frequency` 파라미터로 정해지며 배포판·튜닝에 따라 다르지만, DWB든 MPPI든 전역 플래너보다 한 자릿수 이상 높은 빈도로 도는 것이 일반적이다.[^5] 전역 경로를 큰 틀에서는 따르되, 눈앞에 갑자기 나타난 장애물은 지역 판단으로 피한다.

::: warn 두 코스트맵이 다른 답을 낼 때
전역 플래너가 "이 복도로 쭉 가라"고 계산했는데, 지역 컨트롤러가 보는 지역 코스트맵에는 방금 누가 지나가서 그 복도 입구가 막혀 있다고 하자. 컨트롤러는 잠깐 우회하거나 멈추지만, 전역 경로 자체는 안 바뀐다. 이 상태가 일정 시간 지속되면(진행이 없다고 `progress_checker`가 판단하면) `bt_navigator`가 전역 재계획을 다시 트리거한다. **"경로는 있는데 로봇이 안 움직인다"는 증상을 보면, 전역 계획이 틀린 게 아니라 지역 코스트맵이 뭔가로 막혀 있고 재계획 트리거 조건이 아직 안 채워진 경우가 많다.**
:::

::: deep 왜 두 빈도가 서로 다른 실행기 콜백 그룹에서 돈다
전역 계획은 무겁고 가끔 돈다. 지역 제어는 가볍지만 실시간성이 중요하다. [10.3 rclpy 노드](#/rclpy-node)에서 본 콜백 그룹과 멀티스레드 실행기(executor) 개념이 여기서 실전으로 쓰인다 — 무거운 전역 재계획 콜백이 지역 제어 루프를 밀어내면 로봇이 순간적으로 반응을 멈춘다. [4.1 동시성 모델 지도](#/concurrency-map)에서 본 "무엇이 I/O 바운드고 무엇이 CPU 바운드인가"의 구분이 그대로 적용된다. 전역 계획은 CPU 바운드에 가깝고, 짧게 끝나야 하는 지역 제어 콜백과 같은 스레드에서 돌면 안 된다.
:::

## 비헤이비어 트리를 직접 실행해서 확인한다

Nav2의 `bt_navigator`는 BehaviorTree.CPP를 쓰지만, Sequence와 Fallback이라는 핵심 개념은 파이썬으로 그대로 재현할 수 있다. 아래는 "경로를 따라가다가 막히면 지역 코스트맵을 비우고 한 번 더 시도한다"는 실제 Nav2의 기본 복구 패턴을 흉내 낸 것이다.

```python title="bt_demo.py — 실제로 실행한 결과"
from enum import Enum, auto


class Status(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    RUNNING = auto()


class Sequence:
    """자식을 순서대로 실행한다. 하나라도 실패하면 즉시 실패."""

    def __init__(self, name, children):
        self.name, self.children = name, children

    def tick(self):
        for child in self.children:
            result = child.tick()
            if result != Status.SUCCESS:
                return result
        return Status.SUCCESS


class Fallback:
    """자식을 순서대로 시도한다. 하나라도 성공하면 즉시 성공 — 복구 로직의 핵심."""

    def __init__(self, name, children):
        self.name, self.children = name, children

    def tick(self):
        for child in self.children:
            result = child.tick()
            if result != Status.FAILURE:
                return result
        return Status.FAILURE


class Action:
    def __init__(self, name, fn):
        self.name, self.fn = name, fn

    def tick(self):
        result = self.fn()
        print(f"  [{self.name}] -> {result.name}")
        return result


attempt = {"n": 0}


def follow_path():
    attempt["n"] += 1
    return Status.FAILURE if attempt["n"] == 1 else Status.SUCCESS   # 첫 시도만 실패하게 흉내


tree = Sequence("NavigateWithReplanning", [
    Action("ComputePathToPose", lambda: Status.SUCCESS),
    Fallback("FollowPathOrRecover", [
        Action("FollowPath", follow_path),
        Sequence("RecoveryThenRetry", [
            Action("ClearLocalCostmap", lambda: Status.SUCCESS),
            Action("FollowPath", follow_path),
        ]),
    ]),
])

print("최종 결과:", tree.tick().name)
```

```text nolines
  [ComputePathToPose] -> SUCCESS
  [FollowPath] -> FAILURE
  [ClearLocalCostmap] -> SUCCESS
  [FollowPath] -> SUCCESS
최종 결과: SUCCESS
```

(Python 3.14.5 기준 실측.) `FollowPath`가 처음엔 실패하지만, `Fallback`이 실패를 곧바로 전체 실패로 만들지 않고 `RecoveryThenRetry`라는 `Sequence`를 대신 시도한다. 그 안에서 코스트맵을 비우고 재시도해 성공한다. 실제 Nav2의 기본 XML 트리도 이 모양을 그대로 따른다 — 다만 리프 노드 하나하나가 진짜 액션 서버 호출이고, 재시도 횟수 제한과 타임아웃이 노드마다 파라미터로 붙어 있을 뿐이다.

## Nav2에 목표 전송하기: action client 코드 패턴

Nav2에게 "저기로 가"를 실제로 시키는 방법은 두 층위가 있다. 하나는 [10.6 액션](#/actions)에서 배운 순수 `rclpy.action.ActionClient`를 직접 쓰는 것이고, 다른 하나는 그걸 감싼 `nav2_simple_commander`의 `BasicNavigator`를 쓰는 것이다.

### 원리 그대로: rclpy ActionClient

`NavigateToPose`는 `nav2_msgs/action`에 정의된 액션이다. 요청(goal)은 목표 자세와 어떤 행동 트리를 쓸지, 결과(result)는 에러 코드, 피드백(feedback)은 남은 거리 같은 진행 상황을 담는다.[^3] 액션 클라이언트를 쓰는 방식은 [10.6](#/actions)에서 본 것과 완전히 같은 패턴이다 — `send_goal_async` → 수락 여부 콜백 → `get_result_async`.

```python title="navigate_client.py — ROS 2 공식 액션 클라이언트 예제(examples_rclpy_minimal_action_client)와 동일한 구조"
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose


class NavigateClient(Node):
    def __init__(self):
        super().__init__("navigate_client")
        self._client = ActionClient(self, NavigateToPose, "navigate_to_pose")

    def send_goal(self, x: float, y: float):
        self._client.wait_for_server()

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0   # 회전 없음 (단위 쿼터니언)

        self._send_goal_future = self._client.send_goal_async(
            goal_msg, feedback_callback=self._on_feedback
        )
        self._send_goal_future.add_done_callback(self._on_goal_response)

    def _on_feedback(self, feedback_msg):
        remaining = feedback_msg.feedback.distance_remaining
        self.get_logger().info(f"남은 거리: {remaining:.2f} m")

    def _on_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info("목표가 거부됐다")
            return
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self._on_result)

    def _on_result(self, future):
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info("도착했다")
        else:
            self.get_logger().info(f"실패, status={status}")
        rclpy.shutdown()


def main():
    rclpy.init()
    node = NavigateClient()
    node.send_goal(x=2.0, y=1.0)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
```

이 코드는 [10.1절](#/ros-intro)의 [4.6 asyncio 기초](#/asyncio-basics)와 같은 감각으로 읽으면 된다 — `send_goal_async`가 즉시 반환하는 것은 결과가 아니라 **미래(future)**다. `add_done_callback`으로 "나중에 완료되면 이걸 실행해"를 등록해 두고, `rclpy.spin`이 이벤트 루프처럼 이 콜백들을 실제로 호출해 준다. [1.10 함수](#/functions)에서 본 클로저가 여기서 콜백 등록의 형태로 그대로 쓰인다.

### 실전에서는: nav2_simple_commander

매번 저 콜백 배관을 손으로 짜는 건 번거롭다. `nav2_simple_commander` 패키지의 `BasicNavigator`가 그 배관을 감춘 동기 스타일 API를 제공한다.[^4]

```python title="simple_commander_demo.py"
import rclpy
from rclpy.duration import Duration
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult


def main():
    rclpy.init()
    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()          # amcl + bt_navigator가 활성화될 때까지 대기

    goal_pose = PoseStamped()
    goal_pose.header.frame_id = "map"
    goal_pose.header.stamp = navigator.get_clock().now().to_msg()
    goal_pose.pose.position.x = 2.0
    goal_pose.pose.position.y = 1.0
    goal_pose.pose.orientation.w = 1.0

    navigator.goToPose(goal_pose)

    while not navigator.isTaskComplete():
        feedback = navigator.getFeedback()
        if feedback and Duration.from_msg(feedback.navigation_time).nanoseconds / 1e9 > 600:
            navigator.cancelTask()           # 10분 넘으면 포기

    result = navigator.getResult()
    if result == TaskResult.SUCCEEDED:
        print("도착!")
    elif result == TaskResult.CANCELED:
        print("취소됨")
    else:
        print("실패")

    rclpy.shutdown()


if __name__ == "__main__":
    main()
```

`isTaskComplete()`는 내부적으로 `rclpy.spin_until_future_complete(self, result_future, timeout_sec=0.10)`를 짧은 타임아웃으로 반복 호출하는 폴링 루프다. `while not navigator.isTaskComplete():` 자체가 하나의 블로킹 대기처럼 보이지만 실제로는 0.1초 단위로 깨어나 상태를 확인하는 루프라는 점을 알아 두면, "왜 취소 요청이 즉시 반영되지 않고 최대 0.1초쯤 늦게 먹히는지" 같은 질문에 답할 수 있다.

::: warn 시뮬레이션 시간과 실제 시간을 섞으면 전부 어긋난다
Gazebo([10.11](#/gazebo))에서 시뮬레이션할 때는 `use_sim_time:=true`로 모든 노드가 `/clock` 토픽을 시간의 기준으로 삼게 맞춰야 한다. `waitUntilNav2Active`나 `feedback.navigation_time` 계산은 내부적으로 ROS 시간(`self.get_clock().now()`)을 쓰는데, 이 파라미터가 일부 노드에만 켜져 있으면 어떤 노드는 시뮬레이션 시간, 어떤 노드는 벽시계를 기준으로 움직인다. 그러면 TF 타임스탬프가 안 맞아서 "TF_ERROR"가 나거나(`NavigateToPose.action`의 결과 에러 코드 중 하나가 바로 이것이다), 타임아웃 판정이 조용히 틀어진다. **Nav2가 이상하게 굴 때 가장 먼저 의심할 것은 알고리즘이 아니라 `use_sim_time`이 모든 노드에 일관되게 걸려 있는지다.**
:::

## 실전 감각: 자주 틀리는 것, 디버깅이 어려운 이유

::: danger 인플레이션 반경을 로봇의 실제 크기보다 작게 잡으면
좁은 통로를 지나가려고 `inscribed_radius`(또는 `robot_radius`)를 실제보다 줄여서 설정하는 경우가 있다. 시뮬레이션에서는 통과하는 것처럼 보이지만, 실제로는 로봇의 모서리가 벽에 닿는다. 인플레이션 반경은 **안전 마진이지 통과 가능 여부를 만드는 트릭이 아니다.** 좁은 통로 문제는 반경을 줄이는 게 아니라 플래너/컨트롤러 플러그인을 좁은 공간에 맞는 것으로 바꾸거나 코스트맵 해상도를 높여서 풀어야 한다.
:::

::: warn "경로는 계산됐는데 로봇이 안 움직인다"의 흔한 원인 셋
1. **TF 트리가 안 이어짐** — `map` → `odom` → `base_link` 체인 중 하나가 없거나 타임스탬프가 오래됐다([10.9 TF2](#/tf2)와 같은 문제). Nav2는 로봇의 현재 위치를 TF로 조회하므로, 이게 실패하면 컨트롤러가 시작조차 못 한다.
2. **QoS 불일치** — 코스트맵이 구독하는 LiDAR 토픽의 QoS가 발행자와 안 맞으면 메시지가 조용히 안 온다([10.8 QoS](#/qos)). 코스트맵은 비어 있고, 플래너는 "장애물이 없다"고 착각한 채 경로를 만든다.
3. **속도 명령이 드라이버까지 안 감** — `controller_server`는 `/cmd_vel`을 발행할 뿐, 실제 모터를 돌리는 건 별도 드라이버 노드다. 시뮬레이션에선 Gazebo 플러그인이 이 역할을 하고, 실물에서는 이 연결 자체가 설정에서 빠져 있는 경우가 흔하다.
:::

::: perf 디버깅이 유독 어려운 이유
명령이 나가는 걸 봐도 로봇이 안 움직이면, 원인이 최소 다섯 계층(플래너 → 컨트롤러 → cmd_vel → 드라이버 → 모터) 중 어디인지 하나씩 좁혀야 한다. [10.15 rosbag, 디버깅, 성능](#/ros-debug)의 `ros2 topic hz`/`bw`로 각 계층의 토픽이 실제로 흐르는지 확인하는 게 순서다. 로그만 보고 추측하지 말고 실측으로 좁혀 가라 — [5.1 측정 없이 최적화 없다](#/profiling)와 같은 태도다.
:::

## 요약

- Nav2는 하나의 프로그램이 아니라 `planner_server`/`controller_server`/`behavior_server`/`smoother_server`를 `bt_navigator`가 행동 트리로 조율하는 구조다.
- 행동 트리의 핵심은 Sequence(모두 성공해야 진행)와 Fallback(하나만 성공해도 진행 — 복구 로직의 기반)이다.
- SLAM은 위치와 지도를 동시에 추정해 닭과 달걀 문제를 깬다. 지도가 이미 있으면 AMCL 같은 순수 위치 추정만 돌리는 것이 일반적인 운영 방식이다.
- 코스트맵은 정적/장애물/인플레이션 레이어를 쌓아 만들고, 인플레이션은 장애물로부터의 거리에 지수 감쇠 공식을 적용한다.
- 전역 플래너는 정적 코스트맵 위에서 낮은 빈도로 전체 경로를, 지역 컨트롤러는 동적 장애물이 반영된 지역 코스트맵 위에서 높은 빈도로 속도 명령을 낸다.
- action client로 목표를 보낼 때는 `send_goal_async` → 수락 콜백 → `get_result_async`의 futures 체인이거나, 그걸 감싼 `nav2_simple_commander.BasicNavigator`의 동기 스타일 API를 쓴다.
- "경로는 있는데 안 움직인다"는 증상은 대개 알고리즘이 아니라 TF, QoS, 또는 cmd_vel 이후 계층의 문제다.

::: quiz 연습문제
1. 인플레이션 데모 코드에서 `cost_scaling_factor`를 3.0에서 1.0으로 바꾸면 비용이 퍼지는 반경이 넓어질까 좁아질까? 코드를 고쳐 실제로 실행해서 확인하라.
2. `Fallback`의 자식 중 하나가 항상 `Status.RUNNING`을 반환한다면 이 `tick()` 구현은 그 자식에서 멈추고 반환하는가? 코드를 다시 읽고, 필요하다면 `RUNNING`을 올바르게 처리하도록 `Sequence`/`Fallback`을 고쳐라.
3. 전역 코스트맵과 지역 코스트맵이 굳이 따로 있어야 하는 이유를, "매 주기 계산 비용"과 "반영해야 하는 장애물의 종류" 두 가지 관점에서 각각 한 문장으로 설명하라.
4. `NavigateClient` 예제에서 `_on_goal_response` 콜백이 `goal_handle.accepted`를 확인하지 않고 바로 `get_result_async()`를 호출하면 어떤 상황에서 문제가 생기는가?
5. `use_sim_time`이 일부 노드에만 켜져 있을 때 TF 타임스탬프에 어떤 문제가 생기는지, [10.9 TF2](#/tf2)에서 배운 내용을 근거로 설명하라.
:::

[^1]: [Nav2 공식 문서 — Behavior-Tree Navigator](https://docs.nav2.org/configuration/packages/configuring-bt-navigator.html) 및 [Nav2 개요](https://docs.nav2.org/) 기준. Nav2는 최신 릴리스에서 Route Server, Smoother Server 등 추가 서버도 제공하지만 이 절은 핵심 서버 구성에 집중했다.
[^2]: 공식 저장소 `nav2_costmap_2d`의 인플레이션 레이어 비용 계산 로직(`inflation_layer.hpp`/`.cpp`, GitHub `ros-navigation/navigation2` main 브랜치 원문 대조) 기준. `computeCost()`는 `cost = static_cast<unsigned char>((INSCRIBED_INFLATED_OBSTACLE - 1) * factor)`로 계산하므로 지수 감쇠 구간의 계수는 253이 아니라 252다. `LETHAL_OBSTACLE=254`, `INSCRIBED_INFLATED_OBSTACLE=253`은 `nav2_costmap_2d/cost_values.hpp`에 정의된 상수다.
[^3]: `nav2_msgs/action/NavigateToPose.action` 정의 기준(goal: `pose`, `behavior_tree`; result: `error_code`, `error_msg`; feedback: `current_pose`, `navigation_time`, `estimated_time_remaining`, `number_of_recoveries`, `distance_remaining`). 배포판에 따라 필드가 추가될 수 있다.
[^4]: `nav2_simple_commander/nav2_simple_commander/robot_navigator.py`의 `BasicNavigator` 클래스 구조(`goToPose`, `waitUntilNav2Active`, `isTaskComplete`, `getResult`) 기준.
[^5]: `docs.nav2.org`의 "Configuring Controller Server" 페이지 기준. `controller_frequency`는 노드 파라미터로 노출돼 있어 배포판 기본값이 고정돼 있지 않고 로봇/플러그인마다 튜닝 대상이다 — 이 절의 "초당 수십 번"은 실측 스펙이 아니라 실전에서 흔히 잡는 범위를 가리키는 예시로 읽어야 한다.

**다음 절**: [10.14 MoveIt 2 매니퓰레이션](#/moveit) — 바퀴로 가는 문제를 풀었으니, 이번엔 팔로 잡는 문제다.
