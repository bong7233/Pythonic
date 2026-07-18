# 8.7 실전 풀이 II — 탐색/그래프

::: lead
[7.14 BFS/DFS 응용](#/bfs-dfs)과 [7.15 최단 경로](#/shortest-path)에서 이론과 관용구는 이미 봤다. 이 절은 그걸 실전 문제 세 개에 그대로 붙여서, 어디서 틀리는지를 직접 만들어서 보여준다. 세 문제 모두 같은 질문을 던진다 — **"방문 처리를 정확히 언제 하는가?"** 가중치 없는 그래프에서는 이 실수가 "느려질" 뿐이지만, 다중 시작점이나 상태가 늘어난 그래프, 가중치가 있는 그래프에서는 **답 자체가 틀린다.** 그 경계가 어디인지 이 절의 핵심이다.
:::

## 이 절에서 확인할 것

세 문제 모두 같은 틀을 따른다. 문제 설명 → 브루트포스(느리지만 명백히 맞는 버전) → 최적화 → 실행 결과, 그리고 실전에서 실제로 저지르는 실수 하나를 코드로 재현해서 브루트포스와 대조한다. 대조 검증 방식 자체는 [7.11 트라이](#/trie)와 [8.6 실전 풀이 I](#/drill-impl)에서 쓴 것과 같다 — "무작위 입력을 많이 돌려서 두 구현이 항상 같은 답을 내는가"를 실제로 실행해서 확인한다.

| 문제 | 그래프 종류 | 다루는 실수 |
| --- | --- | --- |
| 1. 배양균 확산 시간 | 가중치 없음, 다중 시작점 | 시작점을 전부 큐에 넣지 않고 하나만 시딩 |
| 2. 배송 네트워크 최단 시간 | 가중치 있음(다익스트라) | 방문 마킹을 **꺼낼 때**가 아니라 **넣을 때** 하는 실수 |
| 3. 벽 부수기 최단 경로 | 가중치 없음, 상태 확장 | 방문 배열에서 상태 차원(부순 벽 개수)을 빠뜨림 |

문제 1은 [7.14절](#/bfs-dfs)에서 이미 다룬 "언제 마킹하는가"가 **다중 시작점**을 만나면 왜 더 예민해지는지를 보여준다. 문제 2는 같은 질문을 **가중치 그래프**로 가져가면 마킹 시점이 성능이 아니라 **정답 여부**를 가른다는 걸 보여준다. 문제 3은 마킹의 "시점"이 아니라 "무엇을 기준으로" 마킹하는지 자체가 틀리는 경우다 — 셋을 이어 보면 방문 처리라는 하나의 개념이 문제 성격에 따라 완전히 다른 방식으로 사람을 함정에 빠뜨린다는 게 보인다.

## 문제 1: 배양균 확산 시간 — 다중 시작점 BFS

**문제.** $R \times C$ 배양 접시가 격자로 주어진다. 각 칸은 빈 칸(0), 벽(1), 또는 이미 배양균이 있는 칸(2) 중 하나다. 매 분마다 배양균이 있는 모든 칸에서 상하좌우로 동시에 한 칸씩 퍼진다(벽은 통과하지 못한다). 모든 빈 칸에 균이 퍼지는 데 걸리는 시간(분)을 구하라. 벽에 막혀 영원히 도달할 수 없는 빈 칸이 있으면 `-1`을 반환한다.

이건 백준 "토마토"류 문제의 자기완결적 재구성이다. 배양균 칸이 **여러 개** 동시에 주어진다는 것이 핵심이다 — 이게 이 문제를 [7.14절](#/bfs-dfs)의 단일 시작점 BFS와 구분 짓는다.

### 브루트포스: 분 단위로 격자 전체를 스캔

지문을 그대로 옮기면 이렇다. 매 분, 격자 전체를 훑어서 "이번 분에 새로 감염될 칸"을 찾고 한꺼번에 갱신한다.

```python title="spread_brute.py — 분 단위 시뮬레이션"
def spread_time_brute(grid):
    rows, cols = len(grid), len(grid[0])
    g = [row[:] for row in grid]
    minute = 0
    while True:
        to_infect = []
        for r in range(rows):
            for c in range(cols):
                if g[r][c] == 2:
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and g[nr][nc] == 0:
                            to_infect.append((nr, nc))
        if not to_infect:
            break
        for nr, nc in to_infect:
            g[nr][nc] = 2
        minute += 1
    if any(g[r][c] == 0 for r in range(rows) for c in range(cols)):
        return -1
    return minute
```

이 코드는 "왜 맞는가"를 설명할 필요조차 없다 — 지문 그대로다. 다만 매 분마다 격자 전체를 다시 스캔하므로, 답이 $T$ 분이면 총 비용이 $O(T \cdot R \cdot C)$ 다.

### 최적화: 모든 시작점을 동시에 큐에 넣는 멀티소스 BFS

핵심 통찰은 이렇다. **"동시에 퍼진다"는 지문은 "모든 시작점을 거리 0으로 큐에 한꺼번에 넣고 BFS를 한 번 돌린다"와 정확히 같다.** 여러 시작점에서 각각 BFS를 따로 돌릴 필요가 없다 — 큐 하나에 시작점을 전부 넣어 두면, 큐가 알아서 "다음 층"을 올바른 순서로 처리해 준다.

```python title="spread_bfs.py — 멀티소스 BFS (최종 코드)"
from collections import deque

def spread_time_bfs(grid):
    rows, cols = len(grid), len(grid[0])
    dist = [[-1] * cols for _ in range(rows)]
    q = deque()
    total_empty = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2:
                dist[r][c] = 0
                q.append((r, c))          # 시작점을 '전부' 넣는다
            elif grid[r][c] == 0:
                total_empty += 1
    reached = 0
    maxd = 0
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 and dist[nr][nc] == -1:
                dist[nr][nc] = dist[r][c] + 1   # 방문 마킹 = 큐에 넣는 시점
                maxd = max(maxd, dist[nr][nc])
                reached += 1
                q.append((nr, nc))
    if reached < total_empty:
        return -1
    return maxd
```

`dist[nr][nc] == -1` 검사와 큐에 넣는 것이 같은 줄에 붙어 있다. 이게 [7.14절](#/bfs-dfs)에서 강조한 "**큐에 넣을 때 마킹**"의 정확한 적용이다.

### 실전에서 자주 저지르는 실수: 시작점 하나만 시딩

다중 시작점 문제에서 실제로 자주 나오는 버그는 "방문 마킹 시점"이 아니라 **"시작점을 전부 큐에 넣지 않는 것"**이다. 격자를 훑다가 배양균 칸을 발견하는 대로 큐에 넣는 코드를 짜다가, 반복문 안에 `break`나 플래그를 잘못 둬서 **첫 번째로 찾은 시작점만** 큐에 들어가는 실수가 실제로 자주 난다.

```python title="spread_buggy.py — 시작점을 하나만 시딩(실전에서 실제로 나는 실수)"
def spread_time_buggy_single_source(grid):
    rows, cols = len(grid), len(grid[0])
    dist = [[-1] * cols for _ in range(rows)]
    q = deque()
    started = False
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2 and not started:
                dist[r][c] = 0
                q.append((r, c))
                started = True   # ❌ 첫 번째 시작점만 큐에 들어가고 나머지는 무시된다
    total_empty = sum(row.count(0) for row in grid)
    reached = 0
    maxd = 0
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 and dist[nr][nc] == -1:
                dist[nr][nc] = dist[r][c] + 1
                maxd = max(maxd, dist[nr][nc])
                reached += 1
                q.append((nr, nc))
    if reached < total_empty:
        return -1
    return maxd
```

BFS 로직 자체는 완벽하다. 문제는 큐에 애초에 들어가는 시작점이 하나뿐이라는 것이다. 나머지 배양균 칸들은 "자기 자신에게서 거리 0으로 퍼져야 할 존재"가 아니라, 어쩌다 첫 시작점의 BFS가 도달하면 그 지점부터 다시 퍼지는 **평범한 빈 칸**(사실은 `dist == -1`인 칸이니 나머지 배양균 칸 자체가 감염되지 않은 것으로 취급된다)처럼 잘못 처리된다.

### 실행 결과

손으로 확인 가능한 작은 예제부터 본다.

```pyrepl
>>> example = [[2, 0, 0], [0, 1, 0], [0, 0, 2]]
>>> spread_time_brute([row[:] for row in example])
2
>>> spread_time_bfs(example)
2
>>> spread_time_buggy_single_source(example)
3
```

버그 버전은 `2`가 아니라 `3`을 낸다 — 오른쪽 아래 시작점을 무시하고 왼쪽 위 시작점 하나만으로 퍼뜨렸기 때문에 더 오래 걸린 것처럼 계산된다.

무작위 격자 300개($3{\times}3$~$8{\times}8$, 시작점 1~3개, 벽 비율 20%, `random.seed(999)`)에서 세 버전을 대조했다. 격자 생성 방식은 이렇다 — 칸마다 독립적으로 20% 확률로 벽(1)을 놓고, 남은 빈 칸 중에서 시작점 개수만큼 무작위로 뽑아 배양균(2)으로 표시한다.

```text nolines
brute vs bfs mismatches: 0 / 300
brute vs buggy(single-source) mismatches: 125 / 300
```

(실제로 실행해서 확인한 결과다.) 300개 중 시작점이 2개 이상인 경우는 196개였고, 그중 125개(약 63.8%)에서 답이 틀렸다 — 시작점이 하나뿐이면 버그가 애초에 드러나지 않으니(실제로 단일 시작점 격자 104개에서는 전부 일치했다), 시작점 개수가 늘어날수록 이 버그가 걸릴 확률도 높아진다.

::: danger 다중 시작점 BFS는 "시작점을 다 모았는가"부터 확인한다
BFS 자체(방문 마킹 시점, 큐 자료구조)가 완벽해도 **초기화가 틀리면** 전부 소용없다. 다중 시작점 문제를 풀 때는 코드를 짜기 전에 이렇게 자문하라. *"격자를 한 번 훑을 때, 시작점 후보를 만날 때마다 빠짐없이 큐에 넣고 있는가?"* 조건문 안에 `break`, 조기 `return`, 또는 이 예시처럼 한 번만 실행되는 플래그가 끼어 있으면 이 실수가 조용히 일어난다. 겉보기엔 BFS가 정상 동작하는 것처럼 보이기 때문에(에러도 없고 답도 나온다) 발견하기가 특히 어렵다.
:::

큰 격자에서 브루트포스와 BFS의 속도 차이를 실측했다(벽 없이 시작점 8개, 정사각 격자).

```text nolines
20x20  : brute=0.0013s(답=14)  bfs=0.000181s  배수=6.9x
50x50  : brute=0.0148s(답=30)  bfs=0.001070s  배수=13.8x
100x100: brute=0.1237s(답=68)  bfs=0.004279s  배수=28.9x
```

::: perf 격자가 커질수록 배수가 커진다
(Python 3.14.5 / Windows 기준 실측. 절대값과 배수는 기기·시작점 배치마다 달라지지만, 격자가 커질수록 배수가 벌어지는 추세는 어디서나 같다.) 브루트포스는 답(분)이 커질 때마다 격자 전체를 한 번 더 훑으므로 $O(T \cdot R \cdot C)$ 이고, 격자가 커지면 $T$ 도 격자 한 변에 비례해서 커진다. 결국 브루트포스는 격자 한 변 $n$ 에 대해 대략 $O(n^3)$, BFS는 칸 하나를 한 번씩만 큐에 넣으므로 $O(n^2)$ 다. $n$ 이 5배(20→100) 커지는 동안 배수가 6.9배에서 28.9배로 벌어진 것이 이 차수 차이의 실물이다. [7.1 복잡도](#/complexity)에서 다룬 "브루트포스가 겉보기엔 단순해도 차수가 다르면 큰 입력에서 무너진다"의 또 다른 사례다.
:::

## 문제 2: 배송 네트워크 최단 시간 — 다익스트라와 마킹 시점

**문제.** $N$ 개의 물류 거점이 방향 그래프로 연결돼 있다. 각 간선 $(u, v, w)$ 는 "$u$ 에서 $v$ 로 배송하는 데 $w$ 시간이 걸린다"는 뜻이다($w > 0$). 거점 0에서 출발해 모든 거점까지의 최단 배송 시간을 구하라. 도달 불가능한 거점은 무한대로 취급한다.

가중치가 있는 그래프의 최단 거리이므로 [7.15 최단 경로](#/shortest-path)의 다익스트라가 표준 도구다. 여기서는 다익스트라를 "왜 정확한가"부터 "방문 마킹을 어디서 하느냐가 왜 정답 여부를 가르는가"까지 코드로 확인한다.

### 브루트포스: 모든 경로를 나열

작은 그래프에서 정확성의 기준점을 세운다. 모든 단순 경로를 나열하고 각 정점까지의 최소 비용을 기록한다.

```python title="delivery_brute.py — 모든 단순 경로 나열 (느리지만 명백히 맞다)"
def brute_shortest_all(adj, n, start):
    INF = float("inf")
    best = [INF] * n
    best[start] = 0

    def dfs(u, visited, cost):
        if cost < best[u]:
            best[u] = cost
        for v, w in adj[u]:
            if v not in visited:
                visited.add(v)
                dfs(v, visited, cost + w)
                visited.remove(v)

    dfs(start, {start}, 0)
    return best
```

[7.14절](#/bfs-dfs)에서 본 것처럼 단순 경로 나열은 $O(n!)$ 급으로 폭발하지만, 정점이 몇 개뿐인 검증용 그래프에서는 "명백히 맞다"는 확신을 준다.

### 최적화: 힙 기반 다익스트라 — 방문 마킹은 꺼낼 때

```python title="delivery_dijkstra.py — 힙 기반 다익스트라 (최종 코드)"
import heapq

def dijkstra_correct(adj, n, start):
    INF = float("inf")
    dist = [INF] * n
    dist[start] = 0
    visited = [False] * n
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if visited[u]:          # 이미 확정된 정점이면 무시 (오래된 힙 항목)
            continue
        visited[u] = True       # 방문 확정은 '꺼낼 때'
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
```

이 코드에는 [7.8 힙과 우선순위 큐](#/heap)에서 다룬 관용구가 그대로 있다 — 같은 정점이 다른 거리값으로 힙에 여러 번 들어갈 수 있다("오래된 항목", stale entry). 그래서 힙에서 꺼낸 직후 `visited[u]` 를 확인해 이미 확정된 정점이면 버린다. **확정(visited = True)은 반드시 이 시점, 즉 힙에서 꺼낸 뒤에 해야 한다.** 이유는 다음 항에서 정확히 보인다.

### 실전에서 자주 저지르는 실수: 확정을 "넣을 때" 해버리는 것

BFS에서는 "넣을 때 마킹"이 정석이었다([7.14절](#/bfs-dfs)). 그래서 다익스트라에도 같은 습관을 그대로 옮겨 "후보를 힙에 넣는 순간 방문 처리해서 중복 삽입을 막자"는 생각을 하기 쉽다. **가중치 그래프에서는 이게 틀린 답을 만든다.**

```python title="delivery_buggy.py — 방문 마킹을 넣을 때 하는 실수"
def dijkstra_buggy_mark_on_push(adj, n, start):
    INF = float("inf")
    dist = [INF] * n
    dist[start] = 0
    visited = [False] * n
    pq = [(0, start)]
    visited[start] = True
    while pq:
        d, u = heapq.heappop(pq)
        for v, w in adj[u]:
            nd = d + w
            if not visited[v] and nd < dist[v]:
                dist[v] = nd
                visited[v] = True    # ❌ 힙에 넣는 순간 확정해 버린다
                heapq.heappush(pq, (nd, v))
    return dist
```

왜 틀리는지 그래프 하나로 정확히 짚을 수 있다.

```text nolines
0 --2--> 1
0 --5--> 2
1 --1--> 2
2 --1--> 3
3 --1--> 4
1 --10-> 3
```

정점 0에서 시작한다. `dijkstra_buggy_mark_on_push` 는 이렇게 진행한다.

1. 정점 0을 꺼낸다. 이웃 1(거리 2), 2(거리 5)를 힙에 넣으면서 **그 자리에서 곧바로 `visited[1] = True`, `visited[2] = True`로 확정한다.**
2. 정점 1(거리 2)을 꺼낸다. 이웃 2로 가는 더 짧은 경로(`2 + 1 = 3 < 5`)를 찾았지만, `visited[2]` 가 이미 `True` 라서 갱신을 건너뛴다. **이 시점에 이미 정점 2의 최종 답이 5로 굳어 버렸다.**
3. 이후 정점 2, 3, 4가 전부 이 잘못된 5를 기준으로 이어져서 계산된다.

```pyrepl
>>> adj = [[(1, 2), (2, 5)], [(2, 1), (3, 10)], [(3, 1)], [(4, 1)], []]
>>> dijkstra_correct(adj, 5, 0)
[0, 2, 3, 4, 5]
>>> dijkstra_buggy_mark_on_push(adj, 5, 0)
[0, 2, 5, 12, 13]
>>> brute_shortest_all(adj, 5, 0)
[0, 2, 3, 4, 5]
```

정답은 `0→1→2→3→4` 경로로 $2+1+1+1=5$ 인데, 버그 버전은 정점 2를 `0→2` 직행(비용 5)으로 잘못 확정해 버려서 이후 전부 어긋난다. **BFS에서 "넣을 때 마킹"이 옳았던 이유는 모든 간선의 가중치가 1로 같아서, 큐에 먼저 들어간 정점이 항상 더 가깝다는 게 보장됐기 때문이다.** 가중치가 다르면 이 보장이 깨진다 — 나중에 힙에 들어간 항목이 먼저 들어간 항목보다 더 짧은 거리를 가리킬 수 있고, 그 갱신 기회를 "넣을 때 마킹"이 미리 막아 버린다.

무작위 그래프 200개(정점 4~8개, 간선 수는 정점 수의 1~2배, 가중치 1~10, `random.seed(777)`)에서 실제로 대조했다.

```text nolines
correct vs brute mismatches: 0 / 200
buggy   vs brute mismatches: 27 / 200
```

(실제로 실행해서 확인한 결과다. 시드를 고정했으므로 같은 그래프 생성 방식으로는 재실행해도 같은 수치가 나오지만, 정점 수·간선 수·가중치 범위를 다르게 잡으면 절대 수치는 달라진다.) 약 13.5%의 그래프에서 답이 틀렸다 — 이 버그는 드문 예외가 아니라 흔한 실패다.

::: danger BFS의 "넣을 때 마킹"을 다익스트라에 그대로 옮기지 마라
가중치 없는 그래프(BFS)와 가중치 있는 그래프(다익스트라)에서 방문 확정 시점의 규칙이 다르다.

| | 방문 확정 시점 | 이유 |
| --- | --- | --- |
| BFS (가중치 없음/균일) | 큐에 **넣을 때** | 먼저 들어간 정점이 항상 더 가깝다는 게 보장된다 |
| 다익스트라 (가중치 있음) | 힙에서 **꺼낼 때** | 나중에 들어간 항목이 더 짧은 거리를 가리킬 수 있다 — 확정을 미뤄야 그 갱신을 놓치지 않는다 |

두 규칙을 헷갈리면 다익스트라에서 조용히 틀린 답이 나온다. 컴파일 에러도, 런타임 에러도 없이 **그럴듯하게 틀린 숫자**가 나온다는 점이 가장 위험하다.
:::

정점 10만 개, 평균 차수 4인 희소 그래프에서 `dijkstra_correct` 의 실행 시간을 쟀다.

```text nolines
n=   1000: 0.0005s
n=  10000: 0.0069s
n= 100000: 0.1311s
```

(Python 3.14.5 / Windows 기준 실측.) 정점이 10배씩 늘 때 시간이 대략 10~19배 느는 정도로, $O(E \log V)$ 가 실전에서 거의 선형에 가깝게 동작함을 보여준다. [7.15절](#/shortest-path)에서 이 복잡도의 근거를 자세히 다룬다.

## 문제 3: 벽 부수기 최단 경로 — 상태를 늘린 BFS

**문제.** $R \times C$ 격자가 있다. 빈 칸(0)과 벽(1)으로 이뤄져 있고, 좌상단 $(0,0)$ 에서 출발해 우하단 $(R-1, C-1)$ 까지 가야 한다. 상하좌우로 한 칸씩 이동할 수 있고, **벽은 최대 $K$ 번까지 부수고 지나갈 수 있다**(부순 벽은 그 이후로도 지나갈 수 있는 빈 칸이 된다고 가정할 필요 없이, 그냥 그 순간 한 번 지나가는 데 "부순 횟수"를 하나 쓴다고 생각하면 된다). 최단 이동 횟수를 구하라. $K$ 번을 다 써도 도달할 수 없으면 `-1`.

이 유형(백준 "벽 부수고 이동하기" 계열)이 앞의 두 문제와 다른 점은 **"방문했는가"라는 질문 자체가 칸 하나로 결정되지 않는다**는 것이다. 같은 칸이라도 "벽을 몇 번 부순 채로 왔는가"에 따라 그 이후에 갈 수 있는 곳이 달라진다.

### 브루트포스: 상태 전체를 되돌리며 전수 탐색

작은 격자에서 모든 단순 경로를 나열해 기준을 세운다. [7.14절](#/bfs-dfs)에서 다룬 백트래킹과 정확히 같은 틀이다 — 갔다가 되돌린다.

```python title="wall_brute.py — 백트래킹 전수 탐색 (느리지만 명백히 맞다)"
def brute_dfs(grid, K):
    rows, cols = len(grid), len(grid[0])
    target = (rows - 1, cols - 1)
    best = [None]

    def dfs(r, c, rem, dist, visited):
        if best[0] is not None and dist >= best[0]:
            return
        if (r, c) == target:
            if best[0] is None or dist < best[0]:
                best[0] = dist
            return
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or (nr, nc) in visited:
                continue
            if grid[nr][nc] == 0:
                visited.add((nr, nc))
                dfs(nr, nc, rem, dist + 1, visited)
                visited.discard((nr, nc))
            elif rem > 0:
                visited.add((nr, nc))
                dfs(nr, nc, rem - 1, dist + 1, visited)
                visited.discard((nr, nc))

    dfs(0, 0, K, 0, {(0, 0)})
    return best[0] if best[0] is not None else -1
```

### 최적화: 방문 배열에 "부순 횟수" 차원을 추가한 BFS

BFS로 최단 거리를 구하려면 "지금까지 본 상태"를 정확히 정의해야 한다. 이 문제의 상태는 `(r, c)` 만이 아니라 **`(r, c, 남은 벽 부수기 횟수)`** 다. 같은 칸이라도 남은 횟수가 다르면 **다른 상태**로 취급해야, 나중에 그 칸을 다시 지나면서 벽을 부술 여지를 잃지 않는다.

```python title="wall_bfs.py — 3차원 방문 배열 BFS (최종 코드)"
from collections import deque

def break_walls_bfs_correct(grid, K):
    rows, cols = len(grid), len(grid[0])
    visited = [[[False] * (K + 1) for _ in range(cols)] for _ in range(rows)]
    visited[0][0][K] = True
    q = deque([(0, 0, K, 0)])
    while q:
        r, c, rem, dist = q.popleft()
        if (r, c) == (rows - 1, cols - 1):
            return dist
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] == 0:
                if not visited[nr][nc][rem]:
                    visited[nr][nc][rem] = True
                    q.append((nr, nc, rem, dist + 1))
            else:
                if rem > 0 and not visited[nr][nc][rem - 1]:
                    visited[nr][nc][rem - 1] = True
                    q.append((nr, nc, rem - 1, dist + 1))
    return -1
```

`visited` 가 `[[bool] * cols] * rows` 가 아니라 `rem` 축이 하나 더 붙은 3차원 배열이라는 게 이 코드의 전부다. 방문 배열의 크기가 $R \times C \times (K+1)$ 이 됐을 뿐, BFS 자체의 로직(큐에 넣을 때 마킹)은 앞의 두 문제와 동일하다.

### 실전에서 자주 저지르는 실수: 방문 배열에서 상태 차원을 빼먹는 것

이 유형에서 실제로 가장 흔한 실수는 `visited` 를 그냥 `(r, c)` 2차원으로만 잡는 것이다. "이미 지나간 칸을 또 지날 이유가 있나?"라는 직관이 유혹적이지만, **남은 벽 부수기 횟수가 다르면 같은 칸이라도 다른 이야기다.**

```python title="wall_buggy.py — 방문 배열에서 rem 차원을 빼먹은 버전"
def break_walls_bfs_buggy_2d_visited(grid, K):
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]   # ❌ rem 차원이 없다
    visited[0][0] = True
    q = deque([(0, 0, K, 0)])
    while q:
        r, c, rem, dist = q.popleft()
        if (r, c) == (rows - 1, cols - 1):
            return dist
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or visited[nr][nc]:
                continue
            if grid[nr][nc] == 0:
                visited[nr][nc] = True
                q.append((nr, nc, rem, dist + 1))
            elif rem > 0:
                visited[nr][nc] = True
                q.append((nr, nc, rem - 1, dist + 1))
    return -1
```

작은 예제에서 이 실수가 실제로 답을 틀리게 만드는 장면을 볼 수 있다.

```pyrepl
>>> grid = [
...     [0, 0, 0, 0],
...     [1, 1, 0, 0],
...     [0, 1, 0, 1],
...     [0, 0, 1, 0],
... ]
>>> break_walls_bfs_correct(grid, K=1)
6
>>> break_walls_bfs_buggy_2d_visited(grid, K=1)
-1
>>> brute_dfs(grid, K=1)
6
```

정답은 `6`인데 버그 버전은 `-1`(도달 불가능)을 낸다. 왜 이런 일이 벌어지는가: BFS는 거리 순서로 진행되므로, 어떤 칸에 **처음** 도달했을 때 그 상태의 `rem` 값이 항상 "최선"은 아니다. 더 돌아가는 경로로 그 칸에 나중에 도착하면서 벽을 덜 썼을 수 있고, 그 여유분(남은 `rem`)이 있어야만 뒤쪽의 벽을 마저 부수고 목적지에 도달할 수 있는 경우가 있다. `visited[nr][nc]` 를 칸 하나로만 잠그면, 그 칸에 먼저 도착한 상태(벽을 더 많이 쓴 상태)가 뒤에 오는 "벽을 아낀" 상태의 진입을 막아 버린다 — 그 뒤로 이어지는 진짜 최단 경로 자체가 탐색에서 사라진다.

무작위 격자 800개($3{\times}3$~$6{\times}6$, 벽 비율 45%, $K \in \{0,1,2,3\}$, `random.seed(2024)`)에서 대조했다. 시작 칸 $(0,0)$ 과 도착 칸 $(R{-}1, C{-}1)$ 은 벽 후보에서 제외하고(경로 자체가 막혀 있으면 비교가 무의미해지므로), 나머지 칸은 각각 독립적으로 45% 확률로 벽을 놓았다.

```text nolines
correct vs brute mismatches: 0 / 800
buggy   vs brute mismatches: 50 / 800
```

(실제로 실행해서 확인한 결과다.) 벽이 촘촘한 격자의 약 6.2%에서 버그 버전이 틀렸다. 그중 대부분(49개)은 **존재하는 경로를 놓치고 `-1`을 반환**하는 방향이었지만, 나머지 1개는 그렇지 않았다 — `-1`이 아니라 **더 긴 오답**을 낸 경우다. 실제 반례는 이렇다.

```pyrepl
>>> grid = [
...     [0, 0, 0, 1, 0],
...     [0, 0, 0, 1, 0],
...     [1, 0, 1, 1, 0],
...     [0, 0, 1, 0, 0],
...     [0, 1, 1, 0, 1],
...     [0, 1, 0, 0, 0],
... ]
>>> brute_dfs(grid, K=1)
9
>>> break_walls_bfs_correct(grid, K=1)
9
>>> break_walls_bfs_buggy_2d_visited(grid, K=1)
11
```

정답은 `9`인데 버그 버전은 `-1`이 아니라 `11`을 낸다 — 경로 자체는 찾아내지만, `visited[nr][nc]` 가 칸 하나만 잠그는 바람에 "벽을 아낀" 더 빠른 상태의 진입을 막아서 결국 더 돌아가는 경로로 도착한다. 그러니 이 버그의 결과는 **"있는 답을 없다고 말하거나(대부분), 있는 답을 실제보다 더 크게 말하거나(드물게) 둘 중 하나"**다 — "전부 `-1`"이라고 단정하면 틀린다.

::: cote 상태가 늘어난 문제는 "방문"의 정의부터 다시 써라
"벽을 K번까지 부술 수 있다", "특정 아이템을 가진 채로", "이 시각 이전에 도착해야" 같은 조건이 붙으면, `visited[r][c]` 만으로는 부족하다는 신호다. 그 문제에서 **"같은 칸을 다시 방문하는 게 의미가 있는 경우"**가 무엇인지 먼저 따져라. 답은 대개 "방문 배열에 그 여분의 조건(남은 자원, 소지한 아이템, 시각 구간)을 차원으로 추가한다"이다. 이 패턴은 [7.14절](#/bfs-dfs)의 0-1 BFS(가중치 0/1을 상태 없이 처리)와는 다른 축이다 — 0-1 BFS는 간선 가중치 문제고, 이건 **"방문"이라는 개념 자체를 어떤 좌표로 나눌 것인가**의 문제다.
:::

상태 공간이 $R \times C \times (K+1)$ 이므로, $K$ 가 커지면 메모리와 시간이 그만큼 늘어난다. 실제로 격자 크기와 $K$ 를 함께 키우며 시간을 쟀다.

```text nolines
50x50   K=5 : 0.0064s (상태 수 = 50*50*6  = 15,000)
100x100 K=10: 0.0465s (상태 수 = 100*100*11 = 110,000)
200x200 K=15: 0.2740s (상태 수 = 200*200*16 = 640,000)
```

(Python 3.14.5 / Windows 기준 실측.) 상태 수가 약 7.3배(15,000→110,000), 다시 약 5.8배(110,000→640,000) 늘 때 시간도 비슷한 비율로 늘었다 — 상태 공간 크기에 선형으로 비례한다는 뜻이다. $K$ 가 문제에서 크게 주어지면($K \le 10$ 정도면 안전하지만 $K \le 1000$ 처럼 크면) 상태 공간 자체가 감당 안 될 만큼 커질 수 있으니, 제약 조건에서 $R \times C \times K$ 를 미리 계산해 보는 습관을 들여라. [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 이런 제약 조건 역추론을 더 다룬다.

## 세 문제를 관통하는 원칙

- BFS의 "큐에 넣을 때 마킹"은 **가중치가 균일할 때만** 성립하는 규칙이다. 다익스트라처럼 가중치가 다르면 확정은 반드시 **꺼낼 때** 해야 한다. 규칙을 그래프 종류와 무관하게 기계적으로 옮기면 조용히 틀린다.
- 다중 시작점 문제에서는 BFS 로직보다 **초기화**(모든 시작점을 빠짐없이 큐에 넣었는가)에서 더 자주 틀린다.
- 상태가 늘어난 문제(자원 제한, 소지품, 시간 창)에서는 "방문"의 정의 자체를 몇 차원으로 잡을지부터 다시 생각해야 한다. 칸 하나로만 방문을 정의하면 진짜 최적해로 가는 경로를 스스로 막아 버릴 수 있다.
- 세 실수 모두 **에러 없이 조용히 틀린 답을 낸다.** 그래서 브루트포스와의 대조 검증이 필수다 — 예제 하나 통과한 걸로는 이런 버그를 못 잡는다.

## 요약

- 다중 시작점 BFS는 "모든 시작점을 거리 0으로 큐에 동시에 넣고 한 번 BFS를 돈다"로 처리한다. 실전에서는 로직보다 **시작점을 빠짐없이 시딩했는가**에서 더 자주 틀린다(무작위 검증에서 300개 중 125개가 틀렸다).
- BFS의 "넣을 때 마킹"은 가중치가 균일할 때만 옳다. 다익스트라에서 같은 습관을 쓰면(넣을 때 확정) 나중에 더 짧은 경로를 찾아도 갱신을 놓쳐서 **틀린 최단 거리**를 낸다(무작위 검증에서 200개 중 27개가 틀렸다).
- 상태가 늘어난 BFS(예: 벽 K번까지 부수기)에서는 방문 배열에 그 상태 차원(남은 자원)을 반드시 포함해야 한다. 칸 하나로만 방문을 정의하면 대부분은 존재하는 경로를 놓치고 `-1`을 잘못 반환하지만, 드물게는 더 긴 오답을 내기도 한다(무작위 검증에서 800개 중 50개가 틀렸고, 그중 1개는 `-1`이 아니라 더 큰 값이었다).
- 세 경우 모두 컴파일도 되고 실행도 되고 그럴듯한 답도 나온다. **무작위 입력으로 브루트포스와 대조하는 습관만이** 이런 버그를 확실히 잡는다.
- 다익스트라의 힙 기반 구현은 $O(E \log V)$ 로 실전에서 거의 선형에 가깝게 동작한다(정점 10만 개에서 0.13초). BFS 계열은 $O(V+E)$ 로 더 빠르지만 가중치가 균일할 때만 쓸 수 있다.

::: quiz 연습문제
1. 문제 1의 `spread_time_buggy_single_source` 에서 `started` 플래그를 지우고 대신 `for` 루프에 `break` 를 걸어 같은 버그를 재현하라. 다른 코드로 같은 증상(시작점 하나만 시딩)이 나오는지 확인하라.
2. 문제 2의 `dijkstra_buggy_mark_on_push` 가 **음수 가중치가 없는데도** 틀린 답을 낸다는 것을 확인했다. 그런데 모든 간선의 가중치가 똑같이 1이라면 이 버그 버전도 정답을 낼까? 코드를 돌려서 확인하고 이유를 설명하라.
3. 문제 3에서 $K = 0$ 이면(벽을 전혀 못 부순다) `break_walls_bfs_correct` 는 사실상 무엇과 동일한 코드가 되는가? [7.14절](#/bfs-dfs)의 어떤 함수와 같아지는지 확인하라.
4. 문제 3의 상태를 `(r, c, rem)` 대신 `(r, c, 지금까지 부순 벽 개수)` 로 정의해도 같은 답이 나오는가? 두 정의의 차이를 코드로 구현해서 비교하라.
5. 세 문제 각각에 대해, 브루트포스 버전이 "느리지만 명백히 맞다"고 확신할 수 있는 근거가 무엇인지 한 문장씩 설명하라. (힌트: 무엇을 하지 않아서 안전한가?)
:::

**다음 절**: [8.8 실전 풀이 III — DP](#/drill-dp) — 점화식을 세우는 것 자체를 훈련한다. 브루트포스 점화식에서 메모이제이션으로 넘어가는 과정을 실행 결과로 확인한다.
