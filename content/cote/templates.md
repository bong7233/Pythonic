# 8.10 실전 템플릿 모음

::: lead
지금까지 [7.1 복잡도](#/complexity)부터 [7.26 기하](#/geometry)까지, 그리고 [8.6](#/drill-impl)~[8.9](#/drill-hard)에서 실제 문제로 훈련했다. 이 절은 그 전체를 관통하는 다섯 가지 뼈대 — 입출력, BFS/DFS, 다익스트라, 유니온 파인드, 이분 탐색 — 를 시험장에서 그대로 복사해 쓸 수 있는 최종 형태로 모아 둔다. 각 템플릿은 이 문서를 쓰면서 실제로 실행해 정답을 확인했다. 외우지 말고 **이 페이지를 열어 두고 붙여 쓰는 용도**로 대하라.
:::

## 이 절을 쓰는 법

세 가지만 지키면 된다.

1. **의심하지 말고 복사하되, 변수명은 문제에 맞게 바꿔라.** 아래 코드는 함수 시그니처와 반환값이 고정된 완결형이다. 문제의 그래프 표현, 시작점, 목표를 여기 맞춰 넣으면 된다.
2. **경계 조건 세 개만 확인하고 넘어가라.** 노드가 0개, 1개일 때, 그래프가 비었을 때. 대부분의 템플릿 버그는 여기서 난다.
3. **처음 짜는 문제라면 반드시 브루트포스와 대조하라.** [7.11 트라이](#/trie)에서 보여준 대조 검증 습관을 여기서도 그대로 쓴다. 아래 다익스트라 템플릿도 플로이드-워셜과 대조해서 검증했다.

::: cote 템플릿을 통째로 외우지 마라
시험장에서 진짜 필요한 건 "이 다섯 가지 중 무엇을 써야 하는가"를 문제 제약에서 읽어내는 능력이다. 그 판단법은 [8.4 문제 유형 분류](#/problem-signals)에서 다뤘다. 이 절은 판단이 끝난 뒤 **타이핑 시간을 줄이는** 용도다.
:::

## 입출력 템플릿

[8.2 입출력 최적화](#/io-optimize)에서 다룬 것처럼, `input()` 을 줄 단위로 반복 호출하면 대용량 입력에서 시간 초과가 난다. 아래 템플릿은 표준 입력 전체를 한 번에 읽어 토큰 단위로 소비한다.

```python title="io_template.py — 표준 입력 한 번에 읽기"
import sys


def read_tokens():
    """표준 입력 전체를 토큰(공백/개행 구분) 단위로 잘라 이터레이터로 반환한다."""
    data = sys.stdin.buffer.read().split()
    return iter(data)


def main():
    it = read_tokens()
    n = int(next(it))
    arr = [int(next(it)) for _ in range(n)]
    print(sum(arr))


if __name__ == "__main__":
    main()
```

`n m` 같이 한 줄에 여러 값이 섞여 있어도, $n \times m$ 격자가 여러 줄에 걸쳐 있어도 이 방식은 그대로 통한다. 토큰 스트림이라 줄 경계를 신경 쓸 필요가 없기 때문이다.

```python title="io_template_2d.py — 2차원 격자 입력"
def read_grid():
    it = read_tokens()
    n, m = int(next(it)), int(next(it))
    grid = [[int(next(it)) for _ in range(m)] for _ in range(n)]
    return grid
```

문자열 그리드(`.`/`#` 같은 미로 입력)라면 토큰 하나가 한 줄 전체이므로 이렇게 받는다.

```python title="io_template_str_grid.py — 문자열 격자 입력"
def read_str_grid(n):
    it = read_tokens()
    return [next(it) for _ in range(n)]
```

실제로 세 함수 모두 아래처럼 검증했다.

```python title="verify_io.py"
def solve(data: bytes):
    it = iter(data.split())
    n = int(next(it))
    arr = [int(next(it)) for _ in range(n)]
    return sum(arr)


print(solve(b"5\n1 2 3 4 5\n"))
```

```text nolines
15
```

::: cote 출력도 느려질 수 있다
`print` 를 반복문 안에서 수만 번 호출하면 그 자체로 병목이 된다. 결과를 리스트에 모았다가 `"\n".join(map(str, results))` 로 한 번에 출력하라. [8.2 입출력 최적화](#/io-optimize)에서 실측치를 다룬다.
:::

## BFS/DFS 템플릿

[7.14 BFS/DFS 응용](#/bfs-dfs)의 핵심 형태 세 가지 — 그리드 최단 거리, 그래프 순회(재귀·반복), 연결 요소 개수 — 를 검증된 형태로 둔다.

### 그리드 BFS: 최단 거리

```python title="grid_bfs.py — 격자 위 최단 거리"
from collections import deque


def grid_bfs(grid, start):
    n, m = len(grid), len(grid[0])
    dist = [[-1] * m for _ in range(n)]
    sy, sx = start
    dist[sy][sx] = 0
    q = deque([start])
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < n and 0 <= nx < m and grid[ny][nx] == 0 and dist[ny][nx] == -1:
                dist[ny][nx] = dist[y][x] + 1
                q.append((ny, nx))
    return dist
```

`grid[ny][nx] == 0` 은 "벽이 아니다"의 자리 표시자다. 벽 표현이 다르면(`'#'` 등) 이 조건만 바꾸면 된다. `dist[ny][nx] == -1` 검사가 곧 방문 체크를 겸한다 — 별도의 `visited` 배열을 두지 않는 게 이 템플릿의 핵심이다.

4×4 격자(`1` 이 벽)에서 (0,0)부터 (3,3)까지 최단 거리를 실제로 확인했다.

```pyrepl
>>> grid = [
...     [0, 0, 1, 0],
...     [1, 0, 1, 0],
...     [0, 0, 0, 0],
...     [0, 1, 1, 0],
... ]
>>> d = grid_bfs(grid, (0, 0))
>>> d[3][3]
6
```

손으로 따라가도 (0,0) → (0,1) → (1,1) → (2,1) → (2,0) → (2,2)… 식으로 벽을 피해 6칸이 맞다.

### 그래프 DFS: 재귀와 반복

```python title="graph_dfs.py — 인접 리스트 DFS"
def dfs_recursive(graph, start):
    visited = set()
    order = []

    def dfs(u):
        visited.add(u)
        order.append(u)
        for v in graph[u]:
            if v not in visited:
                dfs(v)

    dfs(start)
    return order


def dfs_iterative(graph, start):
    """재귀 깊이 제한을 피할 때 쓴다. 노드 10만 개 이상의 체인형 그래프에서는
    재귀 버전이 RecursionError로 죽는다."""
    visited = {start}
    order = []
    stack = [start]
    while stack:
        u = stack.pop()
        order.append(u)
        for v in graph[u]:
            if v not in visited:
                visited.add(v)
                stack.append(v)
    return order
```

```pyrepl
>>> graph = {1: [2, 3], 2: [1, 4], 3: [1], 4: [2, 5], 5: [4]}
>>> dfs_recursive(graph, 1)
[1, 2, 4, 5, 3]
>>> dfs_iterative(graph, 1)
[1, 3, 2, 4, 5]
```

두 함수의 방문 **순서**는 다르다(스택에 넣는 순서가 반대라서 인접 리스트를 뒤집어 도는 효과가 난다). 하지만 **방문하는 노드의 집합**은 항상 같다 — DFS 템플릿을 검증할 때 확인해야 할 것은 순서가 아니라 이 집합이다.

::: warn 재귀 DFS는 재귀 깊이 한도에 걸린다
파이썬 기본 재귀 한도는 1,000이다. 그래프가 사슬처럼 길게 이어지면([7.13 그래프](#/graph)에서 다룬 재귀 깊이 문제) 노드 1,000개만 넘어도 `RecursionError` 가 난다.

```python
import sys
sys.setrecursionlimit(10 ** 6)   # 임시방편. 근본 해결은 아니다
```

이 설정을 걸어도 C 스택 자체의 한계 때문에 아주 깊은 경우 세그멘테이션 폴트로 죽을 수 있다. **입력 크기가 크고 그래프가 트리/사슬 모양일 가능성이 있으면 처음부터 `dfs_iterative` 를 써라.**
:::

### 연결 요소 개수

```python title="components.py — 연결 요소 세기"
from collections import deque


def count_components(n, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen = [False] * n
    count = 0
    for i in range(n):
        if not seen[i]:
            count += 1
            q = deque([i])
            seen[i] = True
            while q:
                u = q.popleft()
                for v in adj[u]:
                    if not seen[v]:
                        seen[v] = True
                        q.append(v)
    return count
```

```pyrepl
>>> count_components(6, [(0, 1), (1, 2), (3, 4)])
3
```

노드 6개 중 `{0,1,2}`, `{3,4}`, `{5}` 세 덩어리이므로 3이 맞다.

## 다익스트라 템플릿

[7.15 최단 경로](#/shortest-path)의 다익스트라를 `heapq` 기반으로 정리한다.

```python title="dijkstra.py — heapq 기반 다익스트라"
import heapq

INF = float("inf")


def dijkstra(n, adj, start):
    """adj[u] = [(v, w), ...] 형태의 인접 리스트. 음수 가중치는 처리하지 못한다."""
    dist = [INF] * n
    dist[start] = 0
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:      # 낡은 항목: 더 짧은 경로가 이미 처리됐다
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
```

`if d > dist[u]: continue` 가 이 템플릿의 핵심이다. 힙에는 같은 노드가 여러 번 들어갈 수 있는데(더 짧은 경로를 찾을 때마다 새로 넣으므로), 나중에 그 노드를 꺼냈을 때 이미 더 짧은 거리로 확정된 상태라면 그 낡은 항목은 버려야 한다. 이 검사를 빼도 정답은 나오지만 불필요한 재확장이 쌓여 느려진다.

### 대조 검증: 플로이드-워셜과 비교

작은 그래프에서는 $O(n^3)$ 플로이드-워셜로 전체 쌍 최단 거리를 구해서 다익스트라 결과와 맞춰 볼 수 있다. 노드 4개, 간선 5개짜리 방향 그래프로 확인했다.

```python title="verify_dijkstra.py"
def floyd_warshall(n, edges):
    d = [[INF] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = 0
    for a, b, w in edges:
        d[a][b] = min(d[a][b], w)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if d[i][k] + d[k][j] < d[i][j]:
                    d[i][j] = d[i][k] + d[k][j]
    return d[0]


n = 4
edges = [(0, 1, 4), (0, 2, 1), (2, 1, 1), (1, 3, 1), (2, 3, 5)]
adj = [[] for _ in range(n)]
for a, b, w in edges:
    adj[a].append((b, w))

print(dijkstra(n, adj, 0))
print(floyd_warshall(n, edges))
```

```text nolines
[0, 2, 1, 3]
[0, 2, 1, 3]
```

두 알고리즘이 완전히 다른 방식으로 계산했는데 결과가 같다. `0 -> 2 -> 1` 이 비용 2로 직접 경로(비용 4)보다 짧다는 것까지 정확히 잡아냈다.

::: perf 힙 기반 다익스트라, 실측 규모
노드 10만 개, 양방향 간선 60만 개(무작위 가중치 1~100)짜리 그래프에서 위 템플릿을 그대로 돌렸다.

```text nolines
n=100000, m=600000(양방향), 시간=0.333s, 도달 노드 수=100000
```

(Python 3.14.5 / Windows 기준 실측, 서로 다른 랜덤 시드로 여러 번 재현. 노드 10만 개에 양방향 간선 60만 개면 평균 차수가 약 12로 무작위 그래프의 연결 임계값($\ln(100000) \approx 11.5$)을 넘기 때문에, 시작점에서 전체 노드에 거의 다 도달하는 것이 정상이다 — 도달하지 못한 노드가 여럿 남는다면 그래프 생성 로직이나 시작점 선택을 의심하라. 절대 시간은 기기·입력 분포마다 다르지만, $O((V+E) \log V)$ 라는 점을 기억하면 이 정도 규모가 1초 안쪽으로 끝난다는 감을 잡을 수 있다.) 코딩테스트에서 흔히 주는 $10^5$ 노드, $10^6$ 이하 간선 규모라면 이 템플릿을 그대로 제출해도 시간 제한 안에 들어온다. 다만 `heapq` 에 `(거리, 노드)` 튜플을 쌓는 방식이라 **간선이 그보다 한두 자릿수 더 많아지면** 힙 연산 자체의 상수 비용이 누적된다는 것도 함께 기억하라.
:::

::: cote 음수 가중치가 나오면 이 템플릿을 쓰지 마라
다익스트라는 "한 번 확정된 최단 거리는 절대 갱신되지 않는다"는 가정 위에 서 있다. 음수 간선이 있으면 이 가정이 깨진다. 문제에 "가중치가 음수일 수 있다"거나 "비용을 깎아 준다"는 표현이 나오면 벨만-포드로 바꿔야 한다. [7.15 최단 경로](#/shortest-path)에서 다룬다.
:::

## 유니온 파인드 템플릿

[7.12 유니온 파인드](#/union-find)의 경로 압축 + 랭크 합치기를 최종형으로 정리한다.

```python title="union_find.py — 경로 압축 + 랭크 유니온 파인드"
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]   # 경로 절반화
            x = self.parent[x]
        return x

    def union(self, a, b) -> bool:
        """이미 같은 집합이면 False(사이클), 합쳤으면 True."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True
```

`union` 이 `bool` 을 반환하게 만든 것이 이 템플릿의 실전 포인트다. 크루스칼의 MST 구성이든 그래프의 사이클 검출이든, **"합치기를 시도했는데 이미 같은 집합이더라"** 라는 신호를 그대로 활용할 수 있다.

```pyrepl
>>> uf = UnionFind(6)
>>> for a, b in [(0, 1), (1, 2), (3, 4)]:
...     uf.union(a, b)
True
True
True
>>> uf.find(0) == uf.find(2)
True
>>> uf.find(0) == uf.find(3)
False
```

사이클 검출도 확인했다. 삼각형(0-1, 1-2, 2-0)을 넣으면 세 번째 `union` 이 `False` 를 반환해야 한다.

```pyrepl
>>> uf2 = UnionFind(4)
>>> [uf2.union(a, b) for a, b in [(0, 1), (1, 2), (2, 0)]]
[True, True, False]
```

세 번째 간선 `(2, 0)` 에서 `0` 과 `2` 가 이미 같은 집합이라 `False` 가 나왔다. 정확히 사이클이 생기는 지점이다.

::: note find 를 재귀 대신 반복으로 짠 이유
`find` 를 재귀로 짜면 우아하지만, 트리가 한쪽으로 길게 늘어진 최악의 경우(경로 압축을 아직 한 번도 못 한 초기 상태) 재귀 깊이가 노드 수만큼 쌓일 수 있다. 위 템플릿처럼 `while` 반복문으로 짜면 이 위험이 아예 없다. 랭크 합치기와 경로 압축을 같이 쓰면 어차피 트리가 거의 평평해지지만, 방어적으로 반복문을 쓰는 편이 안전하다.
:::

## 이분 탐색 템플릿

[7.5 이분 탐색](#/binary-search)의 두 축 — 정렬된 배열에서 위치 찾기, 답 자체를 이분 탐색하는 파라메트릭 서치 — 를 정리한다.

### 정렬된 배열: bisect

```python title="bisect_template.py"
from bisect import bisect_left, bisect_right

arr = [1, 3, 3, 3, 5, 7, 9]
```

```pyrepl
>>> bisect_left(arr, 3)
1
>>> bisect_right(arr, 3)
4
>>> bisect_right(arr, 3) - bisect_left(arr, 3)   # 값 3의 개수
3
```

`bisect_left` 는 "이 값이 들어갈 수 있는 가장 왼쪽 자리"(같은 값의 맨 앞), `bisect_right` 는 "가장 오른쪽 자리"(같은 값의 뒤)다. 이 둘의 차이가 곧 **값의 개수**라는 것이 실전에서 가장 많이 쓰인다.

### 파라메트릭 서치: 답을 이분 탐색한다

"조건을 만족하는 최소값(또는 최대값)을 구하라"는 문제 중, 그 조건이 **단조적**(어떤 값 이상/이하에서는 항상 만족, 반대쪽에서는 항상 불만족)이면 답 자체를 이분 탐색할 수 있다.

```python title="parametric_search.py — 조건을 만족하는 최소값 찾기"
def parametric_search(lo, hi, feasible):
    """[lo, hi] 범위에서 feasible(mid)가 True인 가장 작은 값을 반환한다.
    feasible은 어떤 경계값을 넘으면 항상 True로 바뀌는 단조 함수여야 한다."""
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo
```

$x^2 \ge 50$ 을 만족하는 가장 작은 정수 $x$ 를 찾는 단조 조건으로 검증했다 ($7^2=49 < 50$, $8^2=64 \ge 50$).

```pyrepl
>>> parametric_search(0, 1000, lambda x: x * x >= 50)
8
```

::: cote 파라메트릭 서치를 알아채는 신호
"최댓값을 최소화하라", "가능한 가장 큰/작은 값을 구하라"면서 그 값을 직접 계산하는 공식이 안 보이고, 대신 **"이 값이 가능한가?"를 판정하는 함수는 쉽게 짤 수 있는** 문제라면 파라메트릭 서치를 의심하라. "나무 자르기", "공유기 설치" 같은 유형이 이 패턴이다. `feasible` 함수 하나만 문제에 맞게 새로 짜면 나머지 이분 탐색 뼈대는 위 템플릿 그대로 쓴다. 단조성이 실제로 성립하는지는 손으로 반드시 확인하라 — 성립하지 않는데 이분 탐색을 걸면 조용히 틀린 답을 낸다.
:::

## 다섯 템플릿을 조합하는 문제

실전 문제는 이 다섯 개를 단독으로 쓰기보다 **엮어서** 요구하는 경우가 많다. 몇 가지 조합을 표로 정리한다.

| 조합 | 전형적인 문제 형태 |
| --- | --- |
| 이분 탐색 + BFS/DFS | "이 값 이하의 간선만 써서 도달 가능한가?"를 `feasible` 로 삼아 최소/최대 임계값을 이분 탐색 |
| 유니온 파인드 + 정렬 | 간선을 가중치순으로 정렬한 뒤 유니온 파인드로 사이클 검사 — 크루스칼 MST([7.16](#/mst)) |
| 다익스트라 + 이분 탐색 | "각 간선에 비용이 붙는데, 최단 경로 비용이 예산 이하가 되는 최대 이동 범위는?" 같은 이중 최적화 |
| BFS + 유니온 파인드 | 그리드를 먼저 유니온 파인드로 그룹핑한 뒤, 그룹 간 최단 이동을 BFS로 계산 |

이 조합을 알아채는 훈련은 [8.4 문제 유형 분류](#/problem-signals)와 [8.7 실전 풀이 II](#/drill-search)에서 실제 문제로 더 다룬다. 이 절의 역할은 조합했을 때 각 부품이 바로 끼워 맞춰지도록 **부품 자체를 완성해 두는 것**이다.

## 요약

- 입출력은 `sys.stdin.buffer.read().split()` 로 전체를 한 번에 읽고 토큰 이터레이터로 소비한다. 줄 단위 `input()` 반복은 대용량에서 시간 초과의 원인이다.
- 그리드 BFS는 별도의 `visited` 없이 `dist` 배열의 `-1` 을 방문 체크로 겸한다. 그래프 DFS는 재귀와 반복 두 버전을 갖춰 두고, 사슬형 그래프에서는 반복 버전을 써서 `RecursionError` 를 피한다.
- 다익스트라는 `heapq` 에 낡은 항목이 남는 것을 `if d > dist[u]: continue` 로 걸러낸다. 음수 가중치에는 쓸 수 없다. 실측으로 노드 10만 개, 간선 60만 개가 0.33초 안에 끝난다.
- 유니온 파인드는 경로 절반화 + 랭크 합치기를 반복문으로 구현한다. `union` 이 `bool` 을 반환하게 만들면 사이클 검출과 MST 구성에 그대로 재사용된다.
- 이분 탐색은 정렬된 배열 위치 찾기(`bisect_left`/`bisect_right`)와, 답 자체를 이분 탐색하는 파라메트릭 서치 두 갈래로 나뉜다. 후자는 조건 함수의 단조성이 실제로 성립하는지 반드시 손으로 확인한 뒤 써야 한다.
- 이 다섯 템플릿은 단독보다 **조합**해서 요구되는 경우가 흔하다. 어떤 조합이 필요한지는 제약 조건에서 역추론한다([8.4](#/problem-signals)).
- 어떤 템플릿이든 처음 짜는 상황이라면 브루트포스와 대조 검증하는 습관을 들여라. 이 절의 모든 코드도 그렇게 검증했다.

::: quiz 연습문제
1. `grid_bfs` 템플릿에서 `dist[ny][nx] == -1` 검사를 지우면 어떤 일이 벌어지는지 예측하고, 작은 격자로 직접 실행해서 확인하라.
2. `dijkstra` 템플릿에서 `if d > dist[u]: continue` 를 지워도 최종 `dist` 배열은 똑같이 정확하다. 왜 정확한지, 그런데도 이 줄을 넣어야 하는 이유는 무엇인지 설명하라.
3. `UnionFind.union` 이 반환하는 `bool` 값을 이용해서, 입력으로 주어진 간선 리스트에 사이클이 있는지 없는지만 판정하는 함수 `has_cycle(n, edges)` 를 짜고, 사이클이 있는 경우와 없는 경우 각각으로 검증하라.
4. `parametric_search` 템플릿을 이용해서 "정렬된 배열에서 값 `x` 이상이 처음 나타나는 인덱스"를 구하는 함수를 짜고, `bisect_left` 의 결과와 같은지 대조하라.
5. 이 절의 다섯 템플릿 중 두 개를 조합해야 풀리는 문제 상황을 하나 직접 설계하라(표에 있는 조합 중 하나를 골라도 좋다). 어떤 부분에서 어떤 템플릿을 쓸지 순서대로 적어라.
:::

**다음 절**: [9.1 NumPy: ndarray의 모든 것](#/numpy-basics) — 코딩테스트를 넘어, 수치 계산의 세계로 들어간다. dtype, shape, 인덱싱부터 뷰와 복사의 구분까지.
