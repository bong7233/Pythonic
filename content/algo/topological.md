# 7.17 위상 정렬과 DAG

::: lead
"수강 신청을 하려면 선수 과목을 먼저 들어야 한다." "빌드 시스템은 의존하는 모듈부터 컴파일해야 한다." "엑셀 수식은 참조하는 셀이 먼저 계산돼야 한다." 이 세 문장은 전부 같은 문제다. **선후 관계가 있는 일들을, 그 관계를 어기지 않는 순서로 나열하라.** 이 절은 그 문제를 푸는 알고리즘, 왜 사이클이 있으면 풀 수 없는지, 그리고 이 구조 위에서 최장·최단 경로를 구하는 법을 다룬다. [7.13 그래프 표현](#/graph)과 [7.14 BFS/DFS](#/bfs-dfs)를 이미 안다고 가정한다.
:::

## 순서를 브루트포스로 찾으면 왜 안 되는가

문제를 하나 정의하자. 과목이 $n$ 개 있고, `(a, b)` 형태의 선수 관계 쌍이 주어진다. `b` 를 들으려면 `a` 를 먼저 들어야 한다. 모든 과목을 들을 수 있는 순서를 하나 찾아라. 불가능하면 그렇게 답하라.

가장 순진한 접근은 **모든 순서를 다 시도해 보는 것**이다. 과목이 $n$ 개면 순서는 $n!$ 가지다.

```pyrepl
>>> import math
>>> math.factorial(10)
3628800
>>> math.factorial(20)
2432902008176640000
```

과목이 10개면 순열이 360만 개, 20개면 24경 개다. 코딩테스트에서 과목 수는 보통 $10^4$~$10^5$ 단위로 나온다. 순열을 다 돌리는 건 애초에 후보에서 제외해야 하는 접근이다. [7.1 복잡도](#/complexity)에서 봤듯, 필요한 건 "가능한 것 중 하나"를 $O(V+E)$ 에 직접 만들어내는 알고리즘이다.

::: cote 순열은 코테에서 언제나 위험 신호다
"조건을 만족하는 순서 하나를 찾아라"라는 문제에서 순열(`itertools.permutations`)이 먼저 떠오른다면, 그건 대부분 **제약 조건($n \le 10$ 안팎)이 순열을 허용하는 특수 케이스**이거나 문제를 잘못 읽은 것이다. $n$ 이 100을 넘어가면 순열은 무조건 시간 초과다. 이 절에서 볼 두 알고리즘은 순열 없이 $O(V+E)$ 에 답을 만든다.
:::

## 위상 정렬의 정의와 전제 조건

**위상 정렬**(topological sort)은 방향 그래프의 정점들을, 모든 간선 `u → v` 에 대해 `u` 가 `v` 보다 앞에 오도록 나열하는 것이다.

이게 가능하려면 그래프에 **사이클이 없어야 한다.** 사이클이 있으면 "A가 B보다 먼저"이면서 동시에 "B가 A보다 먼저"인 모순이 생기기 때문이다. 사이클이 없는 방향 그래프를 **DAG**(Directed Acyclic Graph)라고 부른다. 위상 정렬은 정확히 DAG에서만 정의된다.

중요한 사실 하나: **위상 정렬의 결과는 대개 유일하지 않다.** 간선으로 직접 연결되지 않은 두 정점은 어느 쪽이 먼저 와도 상관없다. 이 절 뒤에서 이게 코딩테스트에서 왜 문제가 되는지 다룬다.

## Kahn 알고리즘 — 진입차수를 깎아 나간다

아이디어는 단순하다. **아무 선수 과목도 없는 과목부터 듣는다.** 그 과목을 듣고 나면, 그 과목을 선수로 요구하던 과목들의 조건이 하나씩 풀린다. 조건이 다 풀린 과목은 다음 차례에 듣는다.

정점마다 **진입차수**(indegree, 자신을 향하는 간선의 수)를 세어 두고, 진입차수가 0인 정점부터 큐에 넣어 처리한다.

```python title="topo_kahn.py — Kahn 알고리즘"
from collections import deque


def topo_kahn(n: int, edges: list[tuple[int, int]]) -> list[int] | None:
    graph = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:
        graph[u].append(v)
        indeg[v] += 1

    q = deque(i for i in range(n) if indeg[i] == 0)
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    return order if len(order) == n else None   # n개를 못 채우면 사이클
```

`order` 에 담긴 개수가 `n` 보다 적다는 것은, **더 이상 진입차수 0인 정점이 없는데 아직 처리 못한 정점이 남았다**는 뜻이다. 남은 정점들은 서로 순환 참조하는 사이클 안에 갇혀 있다. 이게 Kahn 알고리즘이 사이클을 검출하는 방법이다.

### 검증: brute force와 대조

작은 무작위 DAG 200개를 만들어서, `topo_kahn` 의 결과가 "모든 순열 중 조건을 만족하는 것들의 집합"(brute force로 전부 나열)에 실제로 속하는지 확인했다.

```python title="brute force와 대조 검증"
from itertools import permutations


def is_valid_topo_order(n, edges, order):
    if order is None or len(order) != n:
        return False
    pos = [0] * n
    for i, node in enumerate(order):
        pos[node] = i
    return all(pos[u] < pos[v] for u, v in edges)


def brute_force_all_valid_orders(n, edges):
    valid = []
    for perm in permutations(range(n)):
        pos = [0] * n
        for i, node in enumerate(perm):
            pos[node] = i
        if all(pos[u] < pos[v] for u, v in edges):
            valid.append(perm)
    return valid

# 무작위 DAG 200개에 대해:
# assert tuple(topo_kahn(n, edges)) in brute_force_all_valid_orders(n, edges)
```

200개의 무작위 DAG(정점 2~7개)에 대해 전부 통과했다. Kahn 알고리즘이 항상 **유효한** 위상 순서를 만든다는 뜻이다 — brute force가 인정하는 정답 집합에 속한다.

::: perf 실측: $O(V+E)$ 는 정말 선형으로 늘어나는가
각 정점이 평균 3개의 뒤쪽 정점으로 간선을 뻗는 무작위 DAG를 만들어 `topo_kahn` 을 돌렸다.

| $n$ (정점) | 간선 수 | 실행 시간 |
| --- | --- | --- |
| 1,000 | 2,994 | 0.0004초 |
| 10,000 | 29,994 | 0.0038초 |
| 100,000 | 299,994 | 0.0407초 |

(Python 3.14.5 / Windows 기준 실측.) 정점이 10배 늘 때마다 간선 수도 10배 늘고, 시간도 대략 10배씩 늘어난다. $O(V+E)$ 라는 이론이 실측 곡선으로 그대로 확인된다. `deque.popleft()` 가 $O(1)$ 이 아니라 리스트로 큐를 흉내 내서 `list.pop(0)` 을 썼다면 이 곡선은 $O(V \times E)$ 가 되어 완전히 다르게 나왔을 것이다. [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 `deque` 가 왜 필요한지 다시 보라.
:::

## DFS 기반 위상 정렬 — 끝나는 순서의 역순

두 번째 구현은 DFS를 이용한다. 아이디어는 이렇다. **정점 `u` 에서 갈 수 있는 모든 정점을 다 방문하고 나서야 `u` 의 방문이 끝난다.** 그러니 "방문이 끝난 순서"를 뒤집으면, `u` 에서 갈 수 있는 정점들이 항상 `u` 보다 앞에 오게 된다 — 이게 바로 위상 순서다.

```python title="topo_dfs.py — DFS 기반, 재귀 버전"
def topo_dfs(n: int, edges: list[tuple[int, int]]) -> list[int] | None:
    graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append(v)

    WHITE, GRAY, BLACK = 0, 1, 2   # 미방문 / 방문 중 / 방문 완료
    color = [WHITE] * n
    order = []
    has_cycle = False

    def dfs(u):
        nonlocal has_cycle
        color[u] = GRAY
        for v in graph[u]:
            if color[v] == WHITE:
                dfs(v)
                if has_cycle:
                    return
            elif color[v] == GRAY:      # 지금 스택에 있는 조상을 다시 만남 = 사이클
                has_cycle = True
                return
        color[u] = BLACK
        order.append(u)                 # "끝난 순서"에 추가

    for i in range(n):
        if color[i] == WHITE:
            dfs(i)
            if has_cycle:
                return None

    order.reverse()
    return order
```

**3색(white/gray/black) 표시**가 핵심이다. `WHITE` 는 아직 안 가본 정점, `GRAY` 는 지금 DFS 스택 위에 있는(재귀 호출 체인 안에 있는) 정점, `BLACK` 은 완전히 끝난 정점이다. 어떤 정점에서 `GRAY` 인 정점으로 다시 갈 수 있다면, 그건 **지금 내려가고 있는 경로가 자기 자신에게 돌아왔다**는 뜻 — 사이클이다.

이 구현도 같은 방식으로 검증했다: 무작위 DAG 200개에서 결과가 brute force 정답 집합에 매번 속했고, 사이클이 있는 그래프(`(0,1),(1,2),(2,0)`)와 self-loop(`(1,1)`)에서 둘 다 정확히 `None` 을 반환했다.

::: danger 재귀 DFS는 큰 입력에서 죽는다
파이썬의 기본 재귀 한도는 1,000이다.

```pyrepl
>>> import sys
>>> sys.getrecursionlimit()
1000
```

정점 3,000개짜리 **체인** 그래프(`0→1→2→...→2999`, 최악의 경우 — 그래프가 한 줄로 이어진 형태)에 위 재귀 `topo_dfs` 를 돌리면 이렇게 된다.

```pyrepl
>>> topo_dfs(3000, [(i, i + 1) for i in range(2999)])
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

실제로 이 값으로 재현했다. `sys.setrecursionlimit(10**6)` 으로 늘리는 건 임시방편이고, 진짜 문제(C 스택 오버플로 → 인터프리터 크래시)를 미룰 뿐이다. **코딩테스트에서 그래프 DFS를 재귀로 짜면 정점 수가 몇천만 넘어도 런타임 에러가 난다.** 안전한 선택은 둘 중 하나다.

1. **반복문 기반 DFS**로 바꾼다 (스택을 직접 관리).
2. 위상 정렬이 목적이라면 **Kahn 알고리즘을 쓴다.** 애초에 재귀가 없다.
:::

```python title="topo_dfs_iterative.py — 명시적 스택으로 재귀 제거"
def topo_dfs_iterative(n: int, edges: list[tuple[int, int]]) -> list[int] | None:
    graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append(v)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n
    order = []

    for start in range(n):
        if color[start] != WHITE:
            continue
        stack = [(start, iter(graph[start]))]
        color[start] = GRAY
        while stack:
            u, it = stack[-1]
            advanced = False
            for v in it:                 # 이터레이터를 이어서 소비 — 다음 루프에서 이어짐
                if color[v] == WHITE:
                    color[v] = GRAY
                    stack.append((v, iter(graph[v])))
                    advanced = True
                    break
                elif color[v] == GRAY:
                    return None
            if not advanced:
                color[u] = BLACK
                order.append(u)
                stack.pop()

    order.reverse()
    return order
```

`stack[-1]` 에서 꺼낸 이터레이터 `it` 을 **for로 다시 돌리다가 `break` 로 빠져나오는** 게 이 구현의 핵심이다. 다음번에 같은 정점이 스택 맨 위에 오면 `it` 은 멈췄던 자리부터 이어서 소비된다 — 재귀 호출 하나하나를 스택 프레임 하나로 손수 흉내 낸 것이다. 이 버전은 체인 정점 100,000개에서도 `RecursionError` 없이 끝난다. 검증했다.

## 사이클 검출: 두 알고리즘이 보는 방식의 차이

같은 문제(사이클이 있으면 위상 정렬 불가능)를 두 알고리즘은 다른 신호로 잡아낸다.

| | 신호 |
| --- | --- |
| **Kahn** | 큐가 비었는데 아직 처리 못 한 정점이 남아 있다 (`len(order) < n`) |
| **DFS** | 지금 재귀/스택 경로 위에 있는(`GRAY`) 정점을 다시 방문한다 |

DFS에서 **`BLACK`(완료) 정점을 다시 만나는 것은 사이클이 아니다.** 그건 그냥 두 정점이 같은 목적지를 공유하는, 흔한 정상적인 상황이다. 초심자가 자주 헷갈리는 지점이다 — "이미 방문했다"와 "지금 내 조상이다"는 다른 조건이다.

```text nolines
   0 ──▶ 1 ──▶ 2
   0 ──────────▶ 2      <- 0->2 직접 간선도 있다.
                          2를 두 번 방문하지만 사이클이 아니다.
                          (2는 두 번째 방문 시점에 BLACK이지 GRAY가 아니다)
```

## 결과가 유일하지 않다 — 그리고 코테에서의 함정

같은 DAG라도 위상 정렬 결과가 여러 개일 수 있다. Kahn 알고리즘에서 `deque` 대신 `heapq` 를 쓰면 **매 순간 고를 수 있는 정점 중 번호가 가장 작은 것**을 고르게 만들 수 있다.

```python title="사전순으로 가장 작은 위상 순서"
import heapq


def topo_kahn_lexmin(n, edges):
    graph = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:
        graph[u].append(v)
        indeg[v] += 1
    heap = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)
    return order if len(order) == n else None
```

같은 간선 `[(2, 1), (3, 0)]` 에 두 방식을 돌려 보면 차이가 바로 드러난다.

```pyrepl
>>> edges = [(2, 1), (3, 0)]
>>> topo_kahn(4, edges)             # deque, FIFO
[2, 3, 1, 0]
>>> topo_kahn_lexmin(4, edges)      # heapq, 항상 최솟값 우선
[2, 1, 3, 0]
```

둘 다 **유효한** 위상 순서다(`1` 은 `2` 다음, `0` 은 `3` 다음이라는 조건을 둘 다 지킨다). 하지만 값은 다르다.

::: cote 백준 1766 "문제집" 같은 문제를 놓치는 이유
문제가 "가능한 순서 중 아무거나"를 요구하면 `deque` 로 짠 Kahn이든 DFS든 다 정답이다. 하지만 **"사전순으로 가장 앞서는 답을 출력하라"** 는 조건이 붙으면 얘기가 다르다 — `deque` 로 짜면 은근슬쩍 틀린다. 반드시 `heapq` 로 "지금 고를 수 있는 것 중 최솟값"을 고르도록 짜야 한다. 문제 지문에서 "우선순위", "사전순", "번호가 작은 것부터"라는 표현을 보면 반사적으로 `heapq` 를 떠올려라. 반대로 그런 조건이 없는데 `heapq` 를 쓰면 $O(\log V)$ 를 매 단계 더 무는 손해만 본다 — `deque` 로 충분하다.
:::

## DAG 위의 최장 경로 — 위상 순서가 있으면 DP가 된다

일반 그래프에서 최장 경로를 구하는 건 NP-hard다(모든 경우를 다 봐야 한다). 그런데 **DAG에서는 다항 시간에 풀린다.** 위상 순서대로 정점을 처리하면, 어떤 정점을 처리할 때 그 정점으로 들어오는 모든 경로가 **이미 확정돼 있기** 때문이다. 이게 [7.20 DP 기초](#/dp-basics)에서 말하는 "부분 문제가 먼저 끝나 있어야 한다"는 조건을 위상 순서가 정확히 보장해 준다는 뜻이다.

```python title="DAG 최장 경로"
def dag_longest_path(n, edges, weight):
    graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append((v, weight[(u, v)]))

    order = topo_kahn(n, edges)
    if order is None:
        return None                       # 사이클 → 경로 길이가 무한정 늘어날 수 있어 정의 불가

    dist = [0] * n                        # dist[v] = v에서 끝나는 경로 중 최댓값
    for u in order:                       # 위상 순서대로 처리 → u는 이미 확정된 상태
        for v, w in graph[u]:
            if dist[u] + w > dist[v]:
                dist[v] = dist[u] + w
    return dist
```

`dist[u]` 가 확정된 뒤에야 `u` 를 처리하므로, `dist[u] + w` 로 `dist[v]` 를 갱신하는 시점에 `dist[u]` 는 절대 다시 바뀌지 않는다. 이게 DP의 "한 번 계산하면 끝"이라는 성질을 그대로 만족시킨다.

무작위 DAG 200개(가중치 포함)에서 이 DP 결과를, "각 정점으로 들어오는 경로를 재귀 + 메모이제이션으로 직접 계산"하는 brute force와 대조했다. 전부 일치했다. 최단 경로가 필요하면 `dist` 를 $+\infty$ 로 초기화하고 `min` 으로 갱신하면 된다 — 로직은 동일하다.

::: cote DAG 최장 경로 문제를 알아보는 법
"$N$ 개의 작업이 있고 일부는 다른 작업이 끝나야 시작할 수 있다. 모든 작업을 끝내는 데 걸리는 최소 시간은?" — 이런 문제는 위상 정렬 + DP다. 각 작업을 정점으로, 선후 관계를 간선으로, 소요 시간을 가중치로 놓고 `dist[v] = max(dist[v], dist[u] + w)` 를 위상 순서대로 돌리면 끝난다. 백준 "줄 세우기(1766)", "문제집", ACM 크래프트류 문제가 전형적으로 이 패턴이다. [7.21 DP 심화](#/dp-advanced)의 문제들과 뼈대가 같다는 걸 눈치채면, 그래프 문제인지 DP 문제인지로 나눠 생각할 필요가 없어진다.
:::

## 대표 문제: 강의 수강 순서 (Course Schedule)

지금까지 다룬 걸 그대로 조립하면 전형적인 코딩테스트 문제가 풀린다. "`numCourses` 개의 강의가 있고, `prerequisites[i] = [a, b]` 는 `b` 를 먼저 들어야 `a` 를 들을 수 있다는 뜻이다. 모든 강의를 들을 수 있는 순서를 구하라. 불가능하면 빈 리스트를 반환하라." (LeetCode 210과 동일한 구조.)

```python title="course_schedule.py"
from collections import deque


def find_order(num_courses: int, prerequisites: list[list[int]]) -> list[int]:
    graph = [[] for _ in range(num_courses)]
    indeg = [0] * num_courses
    for a, b in prerequisites:      # b -> a : b를 먼저 들어야 a를 들을 수 있다
        graph[b].append(a)
        indeg[a] += 1

    q = deque(i for i in range(num_courses) if indeg[i] == 0)
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    return order if len(order) == num_courses else []
```

```pyrepl
>>> find_order(4, [[1, 0], [2, 0], [3, 1], [3, 2]])
[0, 1, 2, 3]
>>> find_order(2, [[1, 0], [0, 1]])   # 서로가 서로의 선수 과목 -> 불가능
[]
```

첫 번째는 0을 듣고 나면 1, 2가 풀리고, 그 둘을 듣고 나면 3이 풀리는 다이아몬드 모양 DAG다. 두 번째는 `0 → 1 → 0` 사이클이라 `[]` 를 반환한다 — 두 결과 다 실제로 실행해 확인했다.

::: warn 방향을 반대로 짜기 쉽다
`prerequisites[i] = [a, b]` 를 `graph[a].append(b)` 로 짜면(반대로) 완전히 다른 그래프가 된다. "`b` 를 먼저 들어야 `a` 를 들을 수 있다"는 **`b → a` 간선**이다. 어느 쪽이 화살표의 시작이고 어느 쪽이 끝인지, 코드를 짜기 전에 손으로 한 번 그려서 확인해라. 이 문제는 방향을 거꾸로 짜도 컴파일은 되고 실행도 되지만 답이 조용히 틀린다 — 가장 고치기 어려운 종류의 버그다.
:::

이 문제는 사실 [8.4 문제 유형 분류](#/problem-signals)에서 다루는 신호 읽기의 좋은 예다. "A가 B보다 먼저", "A를 하려면 B가 필요하다"는 표현이 지문에 있으면 위상 정렬을 의심하고, 시작한다. 실전에서 시간 배분과 검산 절차는 [8.1 코딩테스트의 구조와 전략](#/cote-strategy)에서 다룬다.

## 요약

- 위상 정렬은 **DAG**(사이클 없는 방향 그래프)에서만 정의된다.
- **Kahn 알고리즘**은 진입차수가 0인 정점부터 큐에 넣어 처리한다. 처리한 개수가 정점 수보다 적으면 사이클이 있다는 뜻이다.
- **DFS 기반**은 방문이 끝난 순서의 역순이 위상 순서다. `WHITE`/`GRAY`/`BLACK` 3색으로 "지금 내 조상인가"를 구분해 사이클을 잡는다.
- 재귀 DFS는 정점 수가 수천을 넘는 체인형 그래프에서 `RecursionError` 로 죽는다. 반복문 기반으로 짜거나 Kahn을 써라.
- 위상 정렬 결과는 대개 **유일하지 않다.** "사전순 최소" 같은 추가 조건이 있으면 `deque` 대신 `heapq` 를 쓴다.
- DAG 위에서는 **최장/최단 경로가 다항 시간 DP**로 풀린다. 위상 순서가 DP의 "부분 문제 먼저 끝남" 조건을 보장해 주기 때문이다.
- "A가 B보다 먼저", "A를 하려면 B가 필요하다"는 지문은 위상 정렬 신호다.

::: quiz 연습문제
1. 정점 5개, 간선이 `(0,1), (0,2), (1,3), (2,3), (3,4)` 인 DAG의 위상 정렬 결과를 손으로 구하라. 가능한 순서가 몇 가지인지도 세어 보라.
2. `topo_kahn` 함수에서 `order` 를 만들지 않고 `indeg` 배열만 보고 사이클 유무만 빠르게 판정하려면 어떻게 바꿔야 하는가?
3. DFS 기반 위상 정렬에서 `BLACK` 정점을 다시 방문하는 것이 왜 사이클이 아닌지, 그리고 `GRAY` 정점을 다시 방문하는 것이 왜 사이클인지 각각 그림을 그려 설명하라.
4. 다음 코드는 무엇이 잘못됐는가? (힌트: 화살표 방향)

   ```python
   def find_order(n, prereq):
       graph = [[] for _ in range(n)]
       indeg = [0] * n
       for a, b in prereq:        # b를 먼저 들어야 a를 들을 수 있음
           graph[a].append(b)     # <- 여기
           indeg[b] += 1          # <- 그리고 여기
       ...
   ```

5. 어떤 작업 목록에서 각 작업 $i$ 는 소요 시간 $t_i$ 를 가지고, 일부 작업은 다른 작업이 끝나야 시작할 수 있다. **모든 작업을 마치는 데 걸리는 최소 시간**을 구하는 알고리즘을 설계하라. (힌트: `dag_longest_path` 를 거의 그대로 쓸 수 있다.)
:::

**다음 절**: [7.18 재귀와 백트래킹](#/backtracking) — 가능한 경우를 전부 만들어야 할 때, 가지치기로 그 폭발을 줄이는 법.
