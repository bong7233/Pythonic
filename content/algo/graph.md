# 7.13 그래프 표현과 순회

::: lead
[7.12 유니온 파인드](#/union-find)에서는 "누가 누구와 연결되어 있는가"만 답했다. 이제 **그 연결 자체를 어떻게 메모리에 담을 것인가**를 다룬다. 정점 10만 개짜리 문제에서 인접 행렬을 그대로 짰다가 메모리 초과로 죽는 것은 코딩테스트 초심자의 통과의례에 가깝다. 이 절에서는 인접 리스트와 인접 행렬의 실제 비용을 실측으로 비교하고, 재귀 DFS가 왜 큰 그래프에서 `RecursionError`를 내는지 직접 터뜨려서 확인한 뒤, 반복문으로 바꾸는 법을 정리한다. 여기서 만드는 그래프 표현은 [7.14 BFS/DFS 응용](#/bfs-dfs)부터 [7.17 위상 정렬](#/topological)까지 이 파트 전체의 기반이 된다.
:::

## 인접 행렬로 짰다가 죽는 사례

그래프를 표현하는 가장 직관적인 방법은 $n \times n$ 표를 만들고 `mat[a][b]`에 간선 유무를 적는 것이다.

```python title="matrix_naive.py"
n = 100_000
mat = [[0] * n for _ in range(n)]   # 정점 10만 개
```

이 한 줄이 문제다. $n=100{,}000$이면 칸 수는 $100{,}000^2 = 10^{10}$개다. 정수 하나가 파이썬에서 최소 28바이트를 차지한다고만 쳐도 수백 기가바이트다. 실행해 보면 `MemoryError`조차 안 나고 그냥 멈춰 버리거나, 운영체제가 스와핑을 시작해 화면이 멎는다. 백준·프로그래머스에서 $n \le 10^5$이라는 제약이 보이는 순간 인접 행렬은 후보에서 빠져야 한다.

::: cote 신호: 정점 수 제약을 보고 표현 방식을 정하라
문제의 제약 조건에서 바로 판단할 수 있다.

- $n \le 1{,}000$ 안팎이고 간선이 촘촘하다(밀집 그래프) → 인접 행렬도 괜찮다. 특히 플로이드-워셜([7.15 최단 경로](#/shortest-path))처럼 애초에 모든 쌍의 거리를 표로 관리해야 하는 알고리즘은 행렬이 자연스럽다.
- $n$이 $10^4$ 이상이거나 "간선이 최대 $m$개"라는 조건이 따로 주어진다(그래프가 성기다, sparse) → 인접 리스트가 사실상 유일한 선택지다.

대부분의 코딩테스트 그래프 문제는 후자다. **인접 리스트를 기본값으로 삼고, 정말 필요할 때만 행렬을 꺼내라.**
:::

## 인접 리스트: `defaultdict(list)`로 표현하기

인접 리스트는 정점마다 "내가 연결된 이웃들"만 저장한다. 존재하는 간선만큼만 메모리를 쓴다.

```python title="adjlist.py"
from collections import defaultdict

def build_graph(n, edges, directed=False):
    g = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
        if not directed:
            g[b].append(a)
    return g

edges = [(0, 1), (0, 2), (1, 2), (2, 3)]
g = build_graph(4, edges)
print(dict(g))
```

```pyrepl
>>> from collections import defaultdict
>>> g = defaultdict(list)
>>> g[0].append(1)
>>> g[0].append(2)
>>> dict(g)
{0: [1, 2]}
```

`defaultdict(list)`를 쓰는 이유는 [7.6 해시](#/hashing)에서 이미 다룬 그 이유 그대로다. 정점 `a`가 처음 등장할 때 `g[a]`에 접근하면 빈 리스트가 자동으로 생기니 `if a not in g: g[a] = []`를 매번 쓸 필요가 없다. `g = [[] for _ in range(n)]`처럼 리스트로 미리 크기를 잡아도 되지만, **정점 번호가 정수가 아니거나(문자열 좌표 등) 범위가 애매하면** `defaultdict`가 더 안전하다.

::: warn `defaultdict`를 그냥 출력하거나 `in`으로 조회하지 마라
`defaultdict`는 **존재하지 않는 키에 접근만 해도 그 키를 만들어 버린다.** 그래프를 다 만든 뒤 방문 여부를 확인한다고 `if v in g`처럼 실수로 `g[v]`를 먼저 찍어 보면, 간선이 하나도 없던 정점이 빈 리스트를 가진 채로 슬쩍 생겨난다. 정점 개수를 세는 로직(`len(g)`)이 있다면 이 부작용으로 답이 틀릴 수 있다. 순회만 할 거면 일반 `dict`로 변환해서(`dict(g)`) 넘기거나, 애초에 `for v in range(n)`처럼 정점 범위를 별도로 관리하라.
:::

## 실측: 리스트 vs 행렬 — 메모리와 순회 속도

말로 하는 트레이드오프 주장은 숫자로 뒷받침해야 한다. 평균 차수 4인 성긴 무작위 그래프를 만들어 두 표현의 메모리와 BFS 순회 시간을 재 보자.

```python title="graph_mem.py — 메모리 실측"
import sys
from collections import defaultdict

def make_adj_list(edges):
    g = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
        g[b].append(a)
    return g

def make_adj_matrix(n, edges):
    mat = [[0] * n for _ in range(n)]
    for a, b in edges:
        mat[a][b] = 1
        mat[b][a] = 1
    return mat

def total_size(container):
    size = sys.getsizeof(container)
    for item in container.values() if isinstance(container, dict) else container:
        size += sys.getsizeof(item)
    return size
```

| n (정점) | 간선 수 | 인접 리스트 (바이트) | 인접 행렬 (바이트) | 배수 |
| --- | --- | --- | --- | --- |
| 100 | 197 | 14,552 | 86,520 | 5.9x |
| 1,000 | 2,000 | 135,424 | 8,064,856 | 59.6x |
| 5,000 | 9,997 | 641,600 | 200,321,880 | 312.2x |

(Python 3.14.5 / Windows 기준 실측, 평균 차수 4인 무작위 그래프. `sys.getsizeof`로 컨테이너 자체와 그 안의 리스트/행 객체 크기만 합산했다 — 정수 객체 자체는 작은 정수 캐싱으로 공유되므로 제외했다. [1.1 객체·이름·참조](#/objects-names)의 캐싱 논의를 떠올려라.)

$n$이 늘수록 배수가 폭발적으로 커진다. **인접 리스트는 $O(V+E)$, 인접 행렬은 $O(V^2)$** 이기 때문이다. 정점이 50배(100→5,000) 늘 때 리스트는 약 44배, 행렬은 약 2,300배 커졌다 — 정확히 제곱 스케일링이다.

순회 속도도 같은 이야기를 한다.

```python title="graph_bench_traverse.py — BFS로 두 표현 비교"
from collections import deque

def bfs_list(g, n, start=0):
    visited = [False] * n
    visited[start] = True
    q = deque([start])
    while q:
        u = q.popleft()
        for v in g[u]:
            if not visited[v]:
                visited[v] = True
                q.append(v)

def bfs_matrix(mat, n, start=0):
    visited = [False] * n
    visited[start] = True
    q = deque([start])
    while q:
        u = q.popleft()
        row = mat[u]
        for v in range(n):          # 모든 열을 다 훑어야 한다
            if row[v] and not visited[v]:
                visited[v] = True
                q.append(v)
```

| n | 리스트 생성 | 행렬 생성 | 배수 | BFS(리스트) | BFS(행렬) | 배수 |
| --- | --- | --- | --- | --- | --- | --- |
| 500 | 0.00016초 | 0.00052초 | 3.3x | 0.00010초 | 0.00275초 | 27.0x |
| 1,000 | 0.00025초 | 0.00440초 | 17.8x | 0.00020초 | 0.01285초 | 63.3x |
| 2,000 | 0.00059초 | 0.01435초 | 24.4x | 0.00036초 | 0.05796초 | 159.7x |
| 4,000 | 0.00124초 | 0.04779초 | 38.6x | 0.00129초 | 0.25777초 | 200.4x |

(Python 3.14.5 / Windows 기준 실측. 두 BFS의 방문 순서가 같은 정점 집합을 만드는지 `assert`로 대조해 정합성을 확인했다. 생성·순회 시간 모두 마이크로초 단위라 노이즈에 민감하다 — 여러 차례 재실행하면 개별 값은 수십 % 흔들리지만, $n$이 커질수록 배수가 커지는 추세 자체는 매번 재현된다.)

$n=4{,}000$에서 행렬 생성은 리스트보다 약 39배, BFS는 약 200배 느리다. 원인은 명확하다. **인접 리스트의 BFS는 정점 `u`의 실제 이웃 수(차수)만큼만 훑지만, 인접 행렬의 BFS는 이웃이 있든 없든 $n$개 열을 전부 훑는다.** 성긴 그래프일수록 이 낭비가 커진다. 생성 시간의 배수가 BFS 시간의 배수보다 작은 것도 같은 논리다 — 행렬 생성은 간선 개수(`m`)에 비례해 채워 넣지만 $n \times n$ 칸을 `0`으로 초기화하는 비용이 이미 $O(n^2)$이라 격차가 서서히 벌어지고, BFS는 매 정점마다 $n$개 열을 훑어야 하니 격차가 훨씬 빨리 벌어진다.

::: perf 인접 행렬이 유리해지는 경우
그래프가 조밀해서 간선이 $O(n^2)$에 가깝다면 얘기가 달라진다. 이때는 인접 리스트도 결국 $O(n^2)$짜리 데이터를 담아야 하므로 메모리 이득이 사라지고, 대신 행렬은 **"a와 b 사이에 간선이 있는가"를 `mat[a][b]`로 $O(1)$에 확인**할 수 있다는 강점이 남는다. 인접 리스트로 같은 질문에 답하려면 `b in g[a]`로 리스트를 훑어야 하므로 최악 $O(\deg(a))$다. 플로이드-워셜처럼 애초에 모든 쌍의 관계를 다뤄야 하는 알고리즘이 행렬을 쓰는 이유가 이것이다. [7.15 최단 경로](#/shortest-path)에서 다시 나온다.
:::

## 방향, 무방향, 가중치

지금까지의 `build_graph`는 무방향 그래프였다. 세 변형을 정리하면 이렇다.

```python title="graph_variants.py"
from collections import defaultdict

# 무방향 — 양쪽에 다 추가
def undirected(edges):
    g = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
        g[b].append(a)
    return g

# 방향 — 한쪽에만 추가
def directed(edges):
    g = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
    return g

# 가중치 — 이웃을 (정점, 가중치) 튜플로
def weighted(edges):
    g = defaultdict(list)
    for a, b, w in edges:
        g[a].append((b, w))
        g[b].append((a, w))
    return g
```

가중치 그래프를 순회할 때는 `for v in g[u]`가 아니라 `for v, w in g[u]`로 풀어야 한다는 것만 기억하면 된다. 다익스트라([7.15 최단 경로](#/shortest-path))는 정확히 이 `weighted` 형태의 인접 리스트 위에서 동작한다.

::: cote 인접 행렬로 가중치를 표현할 때
행렬을 쓴다면 간선이 없는 칸을 `0`이 아니라 **"무한대"**로 채워야 한다. `0`은 "가중치 0인 간선이 있다"와 "간선이 없다"를 구분하지 못한다.

```python
INF = float("inf")
mat = [[INF] * n for _ in range(n)]
for i in range(n):
    mat[i][i] = 0          # 자기 자신까지 거리는 0
for a, b, w in edges:
    mat[a][b] = w
```

플로이드-워셜 구현에서 이 초기화를 빼먹는 것이 가장 흔한 실수다.
:::

## 재귀 DFS가 실제로 터지는 지점

DFS를 재귀로 짜는 것이 자연스럽다. 문제는 파이썬 함수 호출 하나하나가 콜 스택 프레임을 하나씩 먹는다는 것이고, 파이썬은 기본적으로 **재귀 깊이 1,000**에서 멈춘다.

```python title="dfs_recursive.py"
from collections import defaultdict

def dfs_recursive(g, start, visited=None):
    if visited is None:
        visited = set()
    visited.add(start)
    for nxt in g[start]:
        if nxt not in visited:
            dfs_recursive(g, nxt, visited)
    return visited
```

그래프가 트리 모양의 넓은 트리라면 재귀 깊이는 트리의 높이 정도라 문제가 안 된다. 그런데 그래프가 **사슬**(체인)이면 얘기가 다르다. 백준 문제에서 "정점을 일렬로 잇는 간선"이 주어지는 경우(예: 트리가 사실상 리스트인 최악의 입력)가 이런 모양이다.

```python title="graph_recursion.py — 실제로 터뜨려 본다"
import sys

def build_chain(n):
    g = defaultdict(list)
    for i in range(n - 1):
        g[i].append(i + 1)
        g[i + 1].append(i)
    return g

print(sys.getrecursionlimit())     # 1000

for n in (999, 1000):
    g = build_chain(n)
    try:
        dfs_recursive(g, 0)
        print(f"n={n}: 통과")
    except RecursionError:
        print(f"n={n}: RecursionError")
```

```text nolines
1000
n=999: 통과
n=1000: RecursionError
```

(Python 3.14.5 실측. 사슬 길이 999는 통과하고 1,000부터 `RecursionError`가 난다 — 기본 재귀 한도 1,000에 `dfs_recursive` 자체와 모듈 최상위 실행 프레임 등의 오버헤드가 얹혀서 실제 여유 깊이가 999 근처로 줄어든다.)

::: danger 재귀 DFS는 "트리 문제라서 괜찮다"고 방심하기 쉽다
트리 자료구조 문제([7.10 트리](#/tree))에서 재귀 DFS/순회는 흔히 잘 동작한다. 트리가 균형 잡혀 있으면 높이가 $\log n$이라 재귀 깊이가 얕기 때문이다. **문제는 트리가 편향될 때다.** 연결 리스트처럼 한쪽으로만 뻗은 트리, 혹은 애초에 트리가 아니라 그래프인데 DFS가 최악의 경로를 따라가는 경우, 재귀 깊이는 정점 수 $n$에 비례한다. $n=10^5$짜리 문제라면 재귀 DFS는 **거의 확실히 `RecursionError`로 죽는다.** 코딩테스트에서 "왜 로컬에서는 됐는데 채점 서버에서 런타임 에러가 나지?"의 흔한 원인이 이것이다.
:::

## 반복(스택)으로 바꾸기

해법은 **명시적 스택**으로 재귀 호출을 흉내 내는 것이다. 함수 호출 스택 대신 파이썬 리스트를 스택으로 쓴다.

```python title="dfs_iterative.py"
def dfs_iterative(g, start):
    visited = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in g[u]:
            if v not in visited:
                visited.add(v)
                stack.append(v)
    return visited
```

이 코드는 재귀 깊이 제한과 완전히 무관하다. 스택은 힙 메모리에 있는 리스트일 뿐이라, 파이썬 프로세스가 쓸 수 있는 메모리가 허락하는 한 얼마든지 커질 수 있다. `RecursionError`를 낸 사슬 그래프(n=1,000)를 그대로 넣어도 문제없이 끝난다.

::: note 방문 순서는 재귀와 다를 수 있다
재귀 DFS는 `g[u]`의 첫 번째 이웃부터 깊이 파고들지만, 스택 버전은 **`g[u]`의 이웃을 스택에 순서대로 넣고 마지막에 넣은 것부터 꺼내므로** 방문 순서가 뒤집힌다. "도달 가능한 정점의 집합"을 구하는 문제라면 상관없지만, "방문 순서 그 자체"가 답에 영향을 주는 문제(예: 사전순으로 가장 먼저 나오는 경로)라면 `for v in reversed(g[u])`로 뒤집어 넣어야 재귀와 같은 순서가 나온다.
:::

정답 검증은 말로 하지 말고 실제로 대조한다.

```python title="graph_verify_dfs.py — 재귀 vs 반복 대조"
import random

def build_random_graph(n, m, seed):
    random.seed(seed)
    g = defaultdict(list)
    for _ in range(m):
        a, b = random.randint(0, n - 1), random.randint(0, n - 1)
        if a != b:
            g[a].append(b)
            g[b].append(a)
    return g

for trial in range(20):
    n = random.randint(5, 60)
    m = random.randint(5, 150)
    g = build_random_graph(n, m, seed=trial)
    assert dfs_recursive(g, 0) == dfs_iterative(g, 0)

print("20회 무작위 그래프 전부 일치")
```

20회 무작위 시행 전부 방문 집합이 일치했다. 두 구현이 **도달 가능한 정점의 집합**에 대해서는 동치임을 확인한 것이다.

::: cote BFS는 애초에 재귀로 안 짠다
DFS는 재귀로 짜는 습관이 있어서 이 함정에 잘 걸리지만, **BFS는 처음부터 `deque`로 반복문을 쓰는 게 관용구**라 이 문제 자체가 잘 안 생긴다. "재귀 깊이가 걱정되면 BFS로 풀 수 없는지부터 확인하라"는 것도 실전에서 쓸 만한 판단 기준이다. `deque`의 비용은 [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 이미 봤다.
:::

## `sys.setrecursionlimit`은 근본 해결책이 아니다

한도를 올리면 당장의 `RecursionError`는 사라진다.

```python
import sys
sys.setrecursionlimit(1_000_000)
```

실제로 확인해 보자. Python 3.14에서 위 사슬(n=1,000)에 이 설정을 추가하면 통과한다. 그런데 "한도를 사슬 길이와 똑같이 맞추면 되겠지"라는 생각은 함정이다. 앞서 999/1000 사례에서 본 것과 똑같은 이유로, `dfs_recursive` 자신의 프레임과 모듈 최상위 실행 프레임 오버헤드가 한도를 조금 갉아먹기 때문이다.

```python title="setrecursionlimit_trap.py — 한도=사슬 길이로 맞춰도 죽는다"
import sys

sys.setrecursionlimit(2_000_000)
g = build_chain(2_000_000)
dfs_recursive(g, 0)     # 아래 에러가 난다
```

```text nolines
RecursionError: maximum recursion depth exceeded
```

(Python 3.14.5 / Windows 기준 실측. 재현성 있게 항상 실패한다. 한도를 2,100,000으로 여유 있게 잡아야 통과한다 — `len(dfs_recursive(g, 0)) == 2_000_000`. 즉 "한도=사슬 길이"라는 계산은 틀렸고, 오버헤드만큼 여유를 더 얹어야 한다.) CPython 3.11 이후 파이썬 함수 호출이 예전만큼 C 콜 스택을 깊게 먹지 않도록 인터프리터가 바뀐 덕에 수백만 단위까지 한도를 올릴 수 있게 된 것 자체는 맞다. 하지만 **모든 재귀가 이렇게 안전해진 것은 아니다.** 순수 파이썬 함수 호출이 아니라 C로 구현된 함수가 내부적으로 재귀하는 경우(`repr()`, 깊이 중첩된 자료구조의 비교, 일부 표준 라이브러리 함수)는 여전히 진짜 C 스택을 소비한다.

```python title="repr_stack.py — C 스택을 실제로 태우는 경우"
import sys
sys.setrecursionlimit(2_000_000)

lst = []
cur = lst
for _ in range(1_500_000):
    cur.append([])
    cur = cur[0]

repr(lst)     # 아래 에러가 난다
```

```text nolines
RecursionError: Stack overflow (used 2912 kB) while getting the repr of an object
```

(Python 3.14.5 / Windows 기준 실측. 재귀 한도를 200만으로 올렸는데도 `repr()`은 실제 C 스택 크기를 넘어서면 이렇게 잡아 준다.)

다행히 최신 CPython은 이 경우도 무작정 죽지 않고 `RecursionError`로 잡아내도록 스택 사용량을 자체적으로 점검한다. 하지만 이건 **CPython 구현이 친절해진 것**이지, `setrecursionlimit`을 올리는 행위 자체가 안전해졌다는 뜻은 아니다.

::: danger setrecursionlimit을 올리는 것이 여전히 위험한 이유
1. **플랫폼과 버전에 의존한다.** 여기서 측정한 결과는 Python 3.14 / Windows 기준이다. 다른 운영체제, 다른 스레드(특히 별도 스레드는 기본 스택 크기가 더 작다), 다른 파이썬 버전에서는 진짜 세그멘테이션 폴트로 인터프리터 전체가 죽을 수 있다. **`RecursionError`는 잡을 수 있지만 세그폴트는 잡을 수 없다** — `try/except`가 무력하다.
2. **채점 서버 환경을 통제할 수 없다.** 코딩테스트에서 "내 컴퓨터에서는 됐다"가 통하지 않는다. 채점 서버의 파이썬 버전, 스택 크기 한도(`ulimit -s`)는 응시자가 모른다.
3. **근본 문제를 안 고친다.** 재귀 깊이가 $n$에 비례한다는 것은 애초에 알고리즘이 스택 공간을 $O(n)$ 쓴다는 뜻이다. 한도를 올리는 것은 증상만 지우는 것이고, 메모리 사용량과 함수 호출 오버헤드는 그대로 남는다.

**결론: 재귀 깊이가 입력 크기에 비례할 수 있는 그래프/트리 문제에서는 처음부터 반복(스택) 버전으로 짜라.** `setrecursionlimit`은 "이 재귀는 절대 깊어질 수 없다는 걸 알지만 기본값 1,000이 우연히 부족한" 아주 좁은 경우에만 임시방편으로 쓴다.
:::

## 요약

- **인접 리스트**는 $O(V+E)$ 메모리, **인접 행렬**은 $O(V^2)$ 메모리다. 성긴 그래프(대부분의 코테 문제)에서는 리스트가 압도적으로 유리하다 — 실측으로 정점 5,000개에서 300배 이상 차이가 났다.
- `defaultdict(list)`로 인접 리스트를 만들면 정점 초기화를 신경 쓸 필요가 없지만, **존재 확인에 `in`이나 출력에 접근하면 키가 생겨 버리는 부작용**을 조심하라.
- 방향 그래프는 한쪽에만, 가중치 그래프는 `(정점, 가중치)` 튜플로 이웃을 저장한다. 행렬로 가중치를 표현할 때는 빈 칸을 `0`이 아니라 무한대로 채운다.
- 재귀 DFS는 그래프가 사슬처럼 편향되면 재귀 깊이가 $n$에 비례해 **기본 한도 1,000에서 `RecursionError`가 난다** — 실측으로 n=1,000에서 정확히 재현했다.
- **반복(스택) DFS**는 재귀 깊이 제한과 무관하며, 재귀 버전과 도달 가능 집합이 동일함을 무작위 대조로 확인했다. 방문 **순서**는 다를 수 있다.
- `sys.setrecursionlimit`은 근본 해결책이 아니다. 순수 파이썬 재귀는 최신 CPython에서 예전보다 훨씬 깊이 들어가지만, C 레벨 재귀(`repr()` 등)는 여전히 진짜 스택 한계에 부딪히고 플랫폼에 따라 세그폴트로 죽을 수도 있다. **입력 크기에 비례하는 재귀는 처음부터 반복문으로 짜라.**

이 절에서 만든 인접 리스트와 반복 DFS는 [7.14 BFS/DFS 응용](#/bfs-dfs)에서 최단 거리, 연결 요소, 플러드 필로 바로 이어진다. 코딩테스트 시험장 전략은 [8.1 코딩테스트의 구조와 전략](#/cote-strategy)에서 다시 짚는다.

::: quiz 연습문제
1. 정점 6개, 간선 `[(0,1),(1,2),(2,3),(3,4),(4,5)]`인 무방향 그래프를 `defaultdict(list)`로 만들고, 재귀 DFS와 반복 DFS 각각으로 정점 0에서 도달 가능한 집합을 구해 두 결과가 같은지 확인하라.

2. 이 절의 `dfs_recursive`를 `sys.setrecursionlimit` 없이 사슬 길이 2,000짜리 그래프에 돌리면 어떤 예외가 나는가? 예외 메시지를 직접 확인하고, 사슬 길이를 조금씩 줄여 가며 몇 번째부터 통과하는지 찾아라.

3. 인접 행렬로 가중치 그래프를 표현할 때 빈 칸을 `0`으로 채우면 어떤 알고리즘에서 어떤 틀린 결과가 나오는지 구체적인 예를 만들어 보여라. (힌트: 최단 거리 계산)

4. `dfs_iterative`에서 `for v in g[u]:`를 `for v in reversed(g[u]):`로 바꾸면 방문 순서가 재귀 버전과 정확히 같아지는 이유를 스택의 LIFO 동작으로 설명하라.

5. **깊이 생각해 볼 문제.** 이 절에서는 무작위 성긴 그래프(평균 차수 4)로 인접 리스트와 인접 행렬을 비교했다. 만약 그래프가 거의 완전 그래프(모든 정점 쌍이 간선으로 연결)라면, 두 표현의 메모리와 순회 속도 우열이 어떻게 바뀔지 예측하고 직접 벤치마크로 확인하라.
:::

**다음 절**: [7.14 BFS/DFS 응용](#/bfs-dfs) — 이 절에서 만든 인접 리스트로 최단 거리, 연결 요소, 플러드 필, 0-1 BFS까지 실전 문제를 푼다.
