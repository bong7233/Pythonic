# 7.14 BFS/DFS 응용

::: lead
[7.13 그래프 표현과 순회](#/graph)에서 그래프를 인접 리스트로 표현하고 기본 순회를 봤다. 이 절은 그 순회를 **실전 문제**에 쓴다. 최단 거리, 연결 요소, 플러드 필, 그리고 코딩테스트에 자주 나오는 변형인 0-1 BFS까지. 겉보기엔 "그냥 큐 아니면 스택"으로 보이지만, 방문 배열을 언제 마킹하느냐, 되돌리느냐 하나로 정답이 틀리거나 시간 초과가 난다. 이 절의 절반은 그 실수 패턴을 직접 만들어서 검증하는 데 쓴다.
:::

## 브루트포스는 왜 막히는가 — 모든 경로를 다 만들어 보면

가중치 없는 그래프에서 두 정점 사이의 최단 거리를 구하는 문제부터 보자. 가장 직관적인 접근은 "모든 경로를 다 만들어서 가장 짧은 것을 고른다"이다.

```python title="브루트포스 — 모든 단순 경로 나열"
def brute_shortest(adj, n, start, end):
    best = [None]

    def dfs(u, visited, depth):
        if u == end:
            if best[0] is None or depth < best[0]:
                best[0] = depth
            return
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                dfs(v, visited, depth + 1)
                visited.remove(v)

    dfs(start, {start}, 0)
    return best[0] if best[0] is not None else -1
```

정점이 $n$개인 그래프에서 단순 경로의 개수는 최악의 경우 $O(n!)$ 에 가깝게 폭발한다. 정점 20개짜리 완전 그래프에서도 이미 현실적인 시간 안에 끝나지 않는다. 그런데 **최단 거리만** 알고 싶다면 이렇게까지 할 필요가 없다. 정답 후보를 다 만들지 않고도 구할 수 있다는 게 BFS의 핵심이다.

## BFS: 왜 첫 도달이 곧 최단 거리인가

BFS는 시작점에서 **거리 0, 1, 2, ...** 순서로 정점을 층층이 넓혀 간다. 큐를 쓰면 이 순서가 자동으로 보장된다 — 먼저 들어온 정점(가까운 정점)이 먼저 처리되고, 그 정점에서 뻗어 나간 정점들은 큐의 뒤쪽에 쌓이므로 항상 "다음 층"이 된다. 그래서 **어떤 정점에 처음 도달했을 때의 거리가 곧 최단 거리**다. 이미 방문한 정점을 다시 넣지 않으므로 더 긴 경로로 재방문할 일도 없다.

```python title="BFS 최단거리 — 가중치 없는 그래프"
from collections import deque

def bfs_shortest(adj, n, start, end):
    dist = [-1] * n
    dist[start] = 0
    q = deque([start])
    while q:
        u = q.popleft()
        if u == end:
            return dist[u]
        for v in adj[u]:
            if dist[v] == -1:              # 아직 방문 안 함
                dist[v] = dist[u] + 1
                q.append(v)
    return dist[end]                        # end 가 애초에 도달 불가능하면 -1
```

`brute_shortest` 와 대조해서 실제로 같은 답을 내는지 확인해 보자. 무작위 그래프 200개에서 두 함수를 돌려 비교한다.

```python title="정답 대조 — 200회 무작위 그래프"
import random

random.seed(0)
for _ in range(200):
    n = random.randint(2, 8)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if random.random() < 0.4]
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b); adj[b].append(a)
    s, e = random.sample(range(n), 2)
    assert bfs_shortest(adj, n, s, e) == brute_shortest(adj, n, s, e)
print("BFS vs 브루트포스 최단거리 200회 대조 통과")
```

```text
BFS vs 브루트포스 최단거리 200회 대조 통과
```

::: cote deque 를 쓰는 이유 — list 로 큐를 흉내 내면 시간 초과
BFS 큐는 `list` 로도 만들 수 있다. `q.append(x)` 로 넣고 `q.pop(0)` 으로 빼면 겉보기엔 똑같이 동작한다. 그런데 `list.pop(0)` 은 앞의 원소를 하나 지운 뒤 **나머지 전체를 한 칸씩 당긴다** — $O(n)$ 이다. `deque.popleft()` 는 양쪽 끝 연산이 $O(1)$ 이 되도록 만든 이중 연결 리스트 기반 구조라 이 비용이 없다. 실측으로 확인하면 원소를 다 비우는 데 걸리는 시간이 이렇게 벌어진다.

| $n$ | `deque.popleft` 전부 비우기 | `list.pop(0)` 전부 비우기 | 배수 |
| --- | --- | --- | --- |
| 2,000 | 0.00007s | 0.00019s | 2.7배 |
| 4,000 | 0.00014s | 0.00054s | 3.8배 |
| 8,000 | 0.00015s | 0.00135s | 8.8배 |

(Python 3.14.5 / Windows 기준 실측, best-of-21.) 이 배수 자체는 반복 실행할 때마다 흔들린다 — 마이크로초 단위라 타이머 분해능과 시스템 잡음의 영향을 크게 받아서, 같은 코드를 다시 돌리면 2,000에서 1.8~3.7배, 8,000에서 6~11배 사이를 오간다. 하지만 방향은 실행할 때마다 똑같다 — **$n$ 이 커질수록 배수가 커진다.** `deque.popleft()` 는 $n$ 과 무관하게 거의 일정한 시간이 걸리는데 `list.pop(0)` 은 매번 나머지 원소를 통째로 당기느라 $n$ 에 비례해서 느려지기 때문이다. 정점 10만 개짜리 그래프를 `list` 로 BFS 돌리면 큐 연산 자체가 $O(n^2)$ 이 되어 시간 초과를 받는다. **BFS 큐는 무조건 `collections.deque`.** [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)과 [7.7 스택과 큐](#/stack-queue)에서 더 다룬다.
:::

## 방문 배열 관리 실수 패턴 — 언제 마킹하는가

BFS에서 가장 흔한 실수는 방문 처리 시점이다. **큐에 넣을 때(enqueue) 마킹**해야지, **큐에서 뺄 때(dequeue) 마킹**하면 같은 정점이 큐에 중복으로 쌓인다.

```python title="enqueue 시점 마킹 — 정석"
def bfs_mark_on_enqueue(adj, n, start):
    visited = [False] * n
    visited[start] = True          # 큐에 넣기 직전에 마킹
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True
                q.append(v)
```

```python title="dequeue 시점 마킹 — 흔한 실수"
def bfs_mark_on_dequeue_buggy(adj, n, start):
    visited = [False] * n
    q = deque([start])
    while q:
        u = q.popleft()
        if visited[u]:
            continue
        visited[u] = True           # 꺼낼 때 마킹 → 그 사이 중복 push 가능
        for v in adj[u]:
            if not visited[v]:
                q.append(v)
```

두 버전 다 **최종 방문 순서는 같다.** 정답은 맞는다. 문제는 큐에 쌓이는 원소의 개수다. 정점 200개, 간선 확률 5%짜리 그래프에서 실제로 세어 보자.

```text
enqueue 마킹 push 횟수: 199 (정확히 n-1, 시드를 바꿔도 항상 이 값)
dequeue 마킹(버그) push 횟수: 시드에 따라 977 ~ 1068 (예: 977, 996, 997, 1025, 1030, 1068)
```

enqueue 마킹은 큐에 넣기 전에 이미 방문 처리를 끝내므로 push 횟수가 그래프 구조와 무관하게 정확히 $n-1$ 로 결정된다. 반대로 dequeue 마킹은 "꺼내기 전까지" 중복 push 가 허용되므로 정확한 횟수가 특정 무작위 그래프 인스턴스에 좌우된다 — 여러 시드로 돌려 보면 977부터 1068까지 흩어진다. 그래도 대략 $n$ 의 5배 안팎이라는 규모 자체는 안정적이다 — 노드 하나가 이웃에게 여러 번 발견될 때마다 마킹 전에 큐에 또 들어가기 때문이다. 간선이 촘촘한 그래프일수록 이 차이는 커진다. 정점 하나가 이웃 100개를 가지면 그 정점은 최악의 경우 100번 큐에 들어갈 수 있다. 결과는 같아도 **큐 크기와 반복 횟수가 불필요하게 부풀어서** 시간 초과의 원인이 된다.

::: danger 방문 마킹을 아예 빼먹으면 정답이 틀린다
위 두 버전은 "언제" 마킹하느냐의 차이지 마킹 자체를 빼먹은 건 아니다. 방문 배열을 아예 안 쓰면 사이클이 있는 그래프에서 **무한 루프**에 빠진다. 큐/스택 기반 순회에서 방문 배열은 선택이 아니라 필수다.
:::

## DFS로 연결 요소 찾기 — 재귀와 재귀 깊이 한계

연결 요소(connected component)는 "방문 안 한 정점을 만날 때마다 개수를 하나 늘리고, 거기서부터 갈 수 있는 곳을 전부 방문 처리"하면 된다. BFS로도 되지만 DFS가 더 흔히 쓰인다.

```python title="DFS 재귀 — 연결 요소 개수"
def count_components_recursive(adj, n):
    visited = [False] * n
    count = 0

    def dfs(u):
        visited[u] = True
        for v in adj[u]:
            if not visited[v]:
                dfs(v)

    for i in range(n):
        if not visited[i]:
            count += 1
            dfs(i)
    return count
```

재귀 대신 스택을 직접 관리하는 반복(iterative) 버전도 동치다.

```python title="DFS 반복 — 명시적 스택"
def count_components_iterative(adj, n):
    visited = [False] * n
    count = 0
    for i in range(n):
        if not visited[i]:
            count += 1
            visited[i] = True
            stack = [i]
            while stack:
                u = stack.pop()
                for v in adj[u]:
                    if not visited[v]:
                        visited[v] = True
                        stack.append(v)
    return count
```

무작위 그래프 200개에서 두 구현이 항상 같은 개수를 내는지 확인했다.

```text
DFS 재귀 vs 반복 연결요소 개수 200회 대조 통과
```

::: danger 재귀 DFS는 체인처럼 긴 그래프에서 RecursionError 가 난다
파이썬의 재귀는 **C 함수 호출 스택**을 그대로 쓴다. 기본 재귀 한도는 1,000 근처다. 정점이 일렬로 연결된 그래프(체인)에서 DFS를 재귀로 짜면 깊이가 정점 개수만큼 나온다.

```python title="실제로 재현"
import sys

def make_chain(n):
    adj = [[] for _ in range(n)]
    for i in range(n - 1):
        adj[i].append(i + 1)
        adj[i + 1].append(i)
    return adj

def dfs_chain(adj, n, start):
    visited = [False] * n
    def dfs(u):
        visited[u] = True
        for v in adj[u]:
            if not visited[v]:
                dfs(v)
    dfs(start)

sys.setrecursionlimit(1000)   # 기본값 근처
adj = make_chain(5000)
try:
    dfs_chain(adj, 5000, 0)
except RecursionError as e:
    print("RecursionError 재현됨:", type(e).__name__)
```

```text
RecursionError 재현됨: RecursionError
```

`sys.setrecursionlimit()` 로 한도를 올릴 수는 있지만, 한도를 무한정 올리면 이번엔 C 스택 자체가 넘쳐서 인터프리터가 죽는다(세그폴트). **격자·트리·그래프 문제에서 정점 수가 수만 단위를 넘길 수 있다면 반복(스택) 버전을 쓰는 게 안전하다.** 코딩테스트에서 백준 같은 저지가 재귀 깊이 때문에 런타임 에러를 내는 건 매우 흔한 사고다. [8.1 코딩테스트의 구조와 전략](#/cote-strategy)에서 제출 전 체크리스트로 다시 언급한다.
:::

::: perf 재귀 DFS는 반복 DFS보다 실제로 느리다
함수 호출에는 스택 프레임을 만들고 해제하는 고정 비용이 있다. 체인 그래프(정점 5,000개)에서 같은 로직을 재귀와 반복으로 짜서 재 보면 차이가 그대로 드러난다.

```text
체인 n=5000  재귀 DFS=0.00064s  반복 DFS=0.00029s
```

(Python 3.14.5 / Windows 기준 실측, best-of-7. 같은 조건으로 4번 반복 측정해도 매번 2.0~2.4배 사이로 일관됐다.) 정답이 같다면 코딩테스트에서는 반복 버전을 기본으로 고려할 가치가 있다. 특히 재귀 깊이 걱정까지 같이 해결된다.
:::

## 플러드 필 — 격자를 그래프로 보기

플러드 필(flood fill)은 그림판의 "페인트 통" 기능이다. 시작 칸과 같은 색인 상하좌우 칸을 전부 새 색으로 바꾼다. 격자를 그래프로 보면 **각 칸이 정점, 인접한 칸이 간선**인 그래프의 연결 요소 탐색과 똑같다.

```python title="플러드 필 — BFS"
def flood_fill(grid, sr, sc, new_color):
    rows, cols = len(grid), len(grid[0])
    old_color = grid[sr][sc]
    if old_color == new_color:      # 색이 같으면 아무 것도 안 해야 무한 루프를 피한다
        return grid
    q = deque([(sr, sc)])
    grid[sr][sc] = new_color
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == old_color:
                grid[nr][nc] = new_color
                q.append((nr, nc))
    return grid
```

```pyrepl
>>> grid = [[1, 1, 1], [1, 1, 0], [1, 0, 1]]
>>> flood_fill(grid, 1, 1, 2)
[[2, 2, 2], [2, 2, 0], [2, 0, 1]]
```

이 출력을 "전체를 반복 스캔하며 전파"하는 느린 무식한 방법과 대조해 정확히 일치함을 확인했다.

::: warn `old_color == new_color` 를 안 챙기면 무한 루프
`grid[sr][sc]` 를 새 색으로 바꾸기 전에 `old_color` 를 저장해야 한다. 만약 새 색과 원래 색이 같은데 이 검사를 빼먹으면, `grid[nr][nc] == old_color` 조건이 계속 참이 되고 이미 처리한 칸을 색이 "그대로"라는 이유로 계속 큐에 넣는다 — 방문 마킹이 색 자체이기 때문에 색이 안 바뀌면 방문 여부를 구분할 수 없다.
:::

이 패턴은 [7.13 그래프 표현과 순회](#/graph)에서 다룬 격자 그래프 변환의 직접적인 응용이다. 백준 "미로 탐색", "섬의 개수", "토마토" 유형이 전부 이 형태다.

## 백트래킹과 DFS의 차이 — 되돌리는가, 안 되돌리는가

연결 요소나 최단 거리를 구할 때는 한 번 방문한 정점을 **영구히** 방문 처리한다. 그런데 "경로의 개수를 센다"거나 "가능한 조합을 전부 나열한다" 같은 문제는 다르다. 한 가지가 끝나면 방문 표시를 **되돌려서(un-mark)** 다른 가지가 같은 칸을 다시 쓸 수 있게 해야 한다. 이게 백트래킹이다.

```python title="격자에서 단순 경로 개수 세기 — 백트래킹"
def count_paths(grid):
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    target = (rows - 1, cols - 1)
    count = 0

    def dfs(r, c):
        nonlocal count
        if (r, c) == target:
            count += 1
            return
        visited[r][c] = True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and grid[nr][nc] == 0:
                dfs(nr, nc)
        visited[r][c] = False    # 되돌리기 — 이게 백트래킹의 정의다

    visited[0][0] = True
    dfs(0, 0)
    return count
```

`visited[r][c] = False` 를 빼면 어떻게 되는지 직접 확인해 보자. 3행 2열의 빈 격자에서 (0,0)에서 (2,1)까지 가는 단순 경로 개수를 모든 이동 시퀀스를 나열하는 완전탐색과 대조한다.

```text
격자: [[0, 0], [0, 0], [0, 0]]
백트래킹(되돌리기 O): 4
버그 버전(되돌리기 X): 2
완전탐색 대조: 4
```

되돌리기를 빼먹으면 첫 번째로 찾은 경로가 지나간 칸들이 **영구히 "방문됨"으로 남는다.** 그 뒤로 시작되는 다른 가지들은 이미 성공한 경로가 썼던 칸을 다시 쓸 수 없으니, 실제로 존재하는 경로 절반을 놓친다. 무작위로 생성한 50개 격자에서 시험해 보면 23개에서 버그 버전이 틀린 답을 냈다 — 우연히 맞는 경우가 더 드물다.

::: cote DFS(순회)와 백트래킹(탐색)을 헷갈리면 시험장에서 이렇게 걸린다
- **연결 요소 찾기, 플러드 필**: "갈 수 있는 곳을 전부 한 번씩 방문"이 목적 → 되돌리지 않는다. 방문 배열은 전역으로 한 번만 쓰고 끝난다.
- **순열/조합 생성, 경로 개수 세기, N-Queen**: "선택 하나하나의 모든 조합"이 목적 → 각 가지가 끝나면 상태를 되돌려야 형제 가지가 오염되지 않는다.

이름이 둘 다 "DFS"라서 같은 걸로 착각하기 쉽다. **"이 칸을 다른 경로에서 또 써야 하는가?"** 를 자문해 보면 구분된다. 쓸 일이 없으면(순회) 되돌릴 필요가 없고, 쓸 일이 있으면(탐색·나열) 반드시 되돌려야 한다. 백트래킹의 가지치기 기법은 [7.18 재귀와 백트래킹](#/backtracking)에서 깊게 다룬다.
:::

## 0-1 BFS — 가중치가 0 또는 1일 때

간선 가중치가 전부 0 또는 1뿐인 그래프의 최단 거리는 다익스트라([7.15 최단 경로](#/shortest-path))의 $O(E \log V)$ 를 쓸 필요 없이, **덱 하나로 $O(V+E)$ 에** 풀 수 있다. 아이디어는 간단하다. 가중치 0인 간선으로 이동하면 **거리가 그대로**이므로 그 정점을 덱의 **앞쪽**에 넣는다. 가중치 1인 간선으로 이동하면 거리가 하나 늘어나므로 **뒤쪽**에 넣는다. 이렇게 하면 덱이 항상 "거리 오름차순"으로 정렬된 상태를 유지한다 — 우선순위 큐 없이도 다익스트라의 그리디 성질이 재현된다.

```python title="0-1 BFS"
def bfs01(adj, n, start):
    # adj[u] = [(v, w), ...], w는 0 또는 1
    INF = float("inf")
    dist = [INF] * n
    dist[start] = 0
    dq = deque([start])
    while dq:
        u = dq.popleft()
        for v, w in adj[u]:
            nd = dist[u] + w
            if nd < dist[v]:
                dist[v] = nd
                if w == 0:
                    dq.appendleft(v)   # 거리 그대로 → 맨 앞
                else:
                    dq.append(v)       # 거리 +1 → 맨 뒤
    return dist
```

무작위 그래프 300개에서 힙 기반 다익스트라와 결과를 비교해 완전히 일치함을 확인했다.

```text
0-1 BFS vs 다익스트라 300회 대조 통과
```

::: note 언제 0-1 BFS가 실전에서 등장하는가
전형적인 예는 "벽을 최대 K번 부수고 최단 거리로 가라" 유형이다. 빈 칸으로 이동은 비용 0, 벽을 부수고 이동은 비용 1로 모델링하면 그대로 0-1 BFS 문제가 된다. 가중치가 세 종류 이상이면 이 트릭이 깨지고 [7.8 힙과 우선순위 큐](#/heap) 기반 다익스트라로 가야 한다.
:::

## 실전 벤치마크: $O(V+E)$ 가 실제로 선형인가

평균 차수 4로 고정하고 정점 수를 5배씩 늘려 가며 BFS 실행 시간을 쟀다.

| $n$ (정점) | 간선 수 | 실행 시간 |
| --- | --- | --- |
| 1,000 | 2,000 | 0.0002s |
| 5,000 | 10,000 | 0.0010s |
| 25,000 | 50,000 | 0.0065s |
| 125,000 | 250,000 | 0.0411s |
| 625,000 | 1,250,000 | 0.4107s |

(Python 3.14.5 / Windows 기준 실측, best-of-7.) 작은 구간(1,000~5,000)에서는 인터프리터 오버헤드와 시스템 잡음이 절대 시간 대부분을 차지해서 곡선이 매끈하지 않다. 그런데 정점이 625배(1,000→625,000) 늘어나는 동안 시간은 약 2,100배 늘었다 — $O(n^2)$ 이었다면 625배의 제곱, 즉 39만 배 가까이 늘어야 하니 그것과는 확연히 다르다. 2,100배가 625배보다 훨씬 크게 나온 이유도 짚을 필요가 있다: $n=1{,}000$ 은 그래프 크기 자체보다 함수 호출·`deque` 생성 같은 고정 오버헤드가 시간을 지배하는 구간이라 분모가 비정상적으로 작다. 그 구간을 빼고 $n=25{,}000$ 과 $n=625{,}000$ 만 비교하면(정점 25배 증가) 시간은 $0.4107 / 0.0065 \approx 63$배로, 정점 증가 배수(25배)의 약 2.5배 수준이다 — 순수 $O(n)$ 이라면 정확히 25배가 나와야 하는데, 파이썬 레벨 루프의 캐시 미스·GC 오버헤드가 $n$ 이 커질수록 조금씩 늘어나서 완전히 선형은 아니다. 그래도 $O(n^2)$ 의 방향과는 명백히 다르고, $O(V+E)$ 가 실전에서 "거의 선형"이라는 결론 자체는 유지된다.

::: cote 인접 리스트 크기가 곧 시간 제한의 실마리다
문제 제약이 $V, E \le 10^5{\sim}10^6$ 이면 $O(V+E)$ 인 BFS/DFS 는 안전하다. 그런데 인접 행렬(`n x n` 2차원 리스트)로 그래프를 표현하면 순회 자체가 $O(V^2)$ 이 되어 정점 10만 개에서 이미 100억 번 연산이 필요해진다. **정점 수가 커 보이면 인접 리스트인지부터 확인하라.** [7.13 그래프 표현과 순회](#/graph)에서 두 표현의 비용을 실측으로 비교했다.
:::

## 요약

- BFS는 큐로 "층"을 넓혀 가므로 첫 도달이 곧 최단 거리다. 가중치 없는 그래프의 최단 거리에 쓴다.
- BFS 큐는 반드시 `collections.deque` 를 쓴다. `list.pop(0)` 은 $O(n)$ 이라 큰 그래프에서 시간 초과의 원인이 된다.
- 방문 마킹은 **큐에 넣을 때** 해야 한다. 꺼낼 때 하면 정답은 맞아도 중복 push 로 느려진다.
- DFS는 연결 요소 탐색에 자연스럽다. 재귀로 짜면 정점 수가 많은 체인형 그래프에서 `RecursionError` 가 날 수 있으니 반복(스택) 버전도 준비해 둔다.
- 플러드 필은 격자를 그래프로 본 BFS/DFS다. 시작 색과 새 색이 같을 때를 처리하지 않으면 무한 루프에 빠진다.
- **DFS(순회)와 백트래킹(탐색)은 다르다.** 경로·조합을 나열할 때는 방문 표시를 되돌려야(un-mark) 한다. 안 되돌리면 조용히 답이 틀린다.
- 가중치가 0/1뿐이면 다익스트라 대신 덱 하나로 $O(V+E)$ 에 푸는 0-1 BFS를 쓴다.

::: quiz 연습문제
1. 다음 BFS 구현에서 버그를 찾아라. 어떤 입력에서 잘못된 답을 내는지 반례를 만들어라.

   ```python
   def bfs_shortest_buggy(adj, n, start, end):
       dist = [-1] * n
       q = deque([start])
       while q:
           u = q.popleft()
           dist[u] = 0 if u == start else dist[u]
           for v in adj[u]:
               if dist[v] == -1:
                   dist[v] = dist[u] + 1
                   q.append(v)
       return dist[end]
   ```

2. 격자에서 상하좌우 이동만 가능한 플러드 필을, 대각선까지 포함한 8방향으로 바꾸면 어떤 한 줄만 고치면 되는가?

3. 정점 3만 개짜리 완전 이진 트리 형태 그래프에서 재귀 DFS와 반복 DFS 중 어느 쪽이 `RecursionError` 위험이 낮은가? 체인형 그래프와 비교해 이유를 설명하라.

4. 순열을 생성하는 백트래킹 함수에서 방문 배열을 되돌리는 줄을 지우면 어떤 결과가 나오는지 직접 실행해서 확인하라. `itertools.permutations` 결과와 개수를 비교하라.

5. 어떤 미로에서 일반 칸은 비용 0, 특정 "슬로우 타일"은 비용 1이라고 하자. 0-1 BFS로 최단 비용 경로를 구하는 코드를 작성하고, 다익스트라 구현과 결과를 대조해 검증하라.
:::

**다음 절**: [7.15 최단 경로](#/shortest-path) — 가중치가 임의의 양수/음수일 때, 다익스트라·벨만-포드·플로이드-워셜 중 무엇을 골라야 하는가.
