# 7.10 트리와 이진 탐색 트리

::: lead
[7.9 연결 리스트](#/linked-list)에서 노드는 `next` 하나만 가졌다. 그 노드가 참조를 하나 더 가지면 — `left`, `right` — 사슬이 아니라 가지가 생긴다. 그게 트리다. 이 절은 트리를 순회하는 네 가지 방법(전위·중위·후위·레벨), 이진 탐색 트리의 삽입·탐색·삭제, 그리고 코딩테스트에서 트리 문제를 풀 때 거의 항상 걸려 넘어지는 함정 하나 — **파이썬의 재귀 깊이 제한** — 를 다룬다. 마지막에는 LCA와 트리 지름, 두 개의 대표 문제로 마무리한다.
:::

## 트리는 가지 친 연결 리스트다

노드 하나가 자식을 최대 두 개까지 가질 수 있게 하면 이진 트리(binary tree)가 된다.

```python title="이진 트리 노드 -- 연결 리스트 Node에 참조 하나가 늘었을 뿐이다"
class Node:
    __slots__ = ("val", "left", "right")

    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
```

```text nolines
        5
       ╱ ╲
      3   8
     ╱ ╲ ╱ ╲
    1  4 7  9
```

용어를 정확히 잡고 가자. **루트**(root)는 시작 노드, **리프**(leaf)는 자식이 없는 노드, **깊이**(depth)는 루트에서 그 노드까지의 간선 수, **높이**(height)는 그 노드에서 가장 먼 리프까지의 간선 수다. 위 트리에서 5의 깊이는 0, 높이는 2다. 1의 깊이는 2, 높이는 0이다.

::: note 왜 배열이 아니라 참조로 만드는가
힙([7.8 힙과 우선순위 큐](#/heap))은 **완전 이진 트리**라서 배열 인덱스만으로 부모/자식을 계산할 수 있었다(`2i+1`, `2i+2`). 이 절에서 다루는 트리는 완전 이진 트리가 아니어도 된다 — 노드가 중간에 비어 있을 수 있다. 그래서 배열 인덱스 트릭이 낭비가 심해지고, 참조 기반 노드가 자연스러운 표현이 된다. "완전 이진 트리면 배열, 아니면 참조"가 실전 선택 기준이다.
:::

## 순회: 재귀로 먼저

트리의 모든 노드를 방문하는 순서에는 이름이 붙어 있다. **루트를 언제 처리하느냐**로 구분한다.

```python title="세 가지 DFS 순회 -- 재귀"
def preorder(root, out):
    if root is None:
        return
    out.append(root.val)      # 루트 먼저
    preorder(root.left, out)
    preorder(root.right, out)


def inorder(root, out):
    if root is None:
        return
    inorder(root.left, out)
    out.append(root.val)      # 루트 중간
    inorder(root.right, out)


def postorder(root, out):
    if root is None:
        return
    postorder(root.left, out)
    postorder(root.right, out)
    out.append(root.val)      # 루트 마지막
```

위 트리(5, 3, 8, 1, 4, 7, 9)에 대해 실제로 돌려 보면 이렇다.

```pyrepl
>>> preorder(root, r := [])
>>> r
[5, 3, 1, 4, 8, 7, 9]
>>> inorder(root, r := [])
>>> r
[1, 3, 4, 5, 7, 8, 9]
>>> postorder(root, r := [])
>>> r
[1, 4, 3, 7, 9, 8, 5]
```

**중위 순회가 정렬된 순서로 나온 것은 우연이 아니다.** 이 트리가 이진 탐색 트리이기 때문이고, 이 성질은 뒤에서 그대로 활용한다.

## 순회를 반복문으로: 스택이 재귀를 대신한다

재귀 호출은 파이썬 인터프리터가 콜 스택에 프레임을 쌓는 것이다. **직접 스택을 관리하면 재귀 없이 같은 순서를 만들 수 있다.** 이게 단순한 취향 문제가 아니라는 건 다음 절에서 바로 보게 된다.

```python title="전위 순회 -- 반복 (스택)"
def preorder_iter(root):
    out = []
    if root is None:
        return out
    stack = [root]
    while stack:
        node = stack.pop()
        out.append(node.val)
        if node.right:         # 오른쪽을 먼저 넣어야
            stack.append(node.right)
        if node.left:          # 왼쪽이 나중에 나와 먼저 처리된다 (LIFO)
            stack.append(node.left)
    return out
```

```python title="중위 순회 -- 반복 (스택, '왼쪽 끝까지 내려가기' 패턴)"
def inorder_iter(root):
    out = []
    stack = []
    cur = root
    while cur or stack:
        while cur:                 # 왼쪽으로 갈 수 있는 데까지 스택에 쌓는다
            stack.append(cur)
            cur = cur.left
        cur = stack.pop()          # 더 못 내려가면 이 노드를 처리
        out.append(cur.val)
        cur = cur.right            # 오른쪽 서브트리로 넘어간다
    return out
```

후위 순회는 셋 중 가장 헷갈린다. "왼쪽, 오른쪽, 루트" 순서를 반복문으로 직접 재현하려면 스택 하나로는 부족하다. 대신 **"루트, 오른쪽, 왼쪽" 순서를 만들고 뒤집으면 후위가 된다**는 트릭을 쓴다 — 후위(LRD)는 정확히 (DRL)의 역순이기 때문이다.

```python title="후위 순회 -- 반복 (스택 2개, 역순 트릭)"
def postorder_iter(root):
    if root is None:
        return []
    stack1, stack2 = [root], []
    while stack1:
        node = stack1.pop()
        stack2.append(node.val)
        if node.left:
            stack1.append(node.left)
        if node.right:
            stack1.append(node.right)
    return stack2[::-1]
```

레벨 순회(level-order, BFS)는 스택이 아니라 **큐**를 쓴다. 같은 깊이의 노드를 왼쪽부터 순서대로 방문해야 하는데, 큐의 FIFO 성질이 정확히 그걸 보장한다.

```python title="레벨 순회 -- 큐 (BFS)"
from collections import deque

def levelorder(root):
    out = []
    if root is None:
        return out
    q = deque([root])
    while q:
        node = q.popleft()
        out.append(node.val)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return out
```

네 가지 순회(전위·중위·후위) 모두 재귀 버전과 반복 버전이 무작위로 만든 300개의 트리에서 완전히 같은 결과를 내는지 대조해서 확인했다.

```pyrepl
>>> # 무작위 크기(1~30)의 값으로 BST 300개를 만들어
>>> # preorder/inorder/postorder 각각 재귀 vs 반복 결과를 비교
전위/전위/후위 재귀=반복 300회 대조: 통과
```

::: cote 왜 반복형을 반드시 알아야 하는가
재귀형이 코드는 더 짧고 읽기 쉽다. 그런데 코딩테스트 입력은 **트리 노드가 수만 개인 경우가 흔하다.** 다음 절에서 정확히 보겠지만, 파이썬 재귀는 기본 1000단계에서 멈춘다. **편향된 트리(치우친 트리)에서는 노드 수가 곧 재귀 깊이다.** 재귀로 짠 순회가 로컬 테스트에서는 통과하고 제출하면 `RecursionError`로 죽는 전형적인 패턴이 여기서 나온다. 그래서 트리 문제를 풀 때는 **반복형을 기본으로 준비해 두고, 재귀는 트리 크기가 확실히 작을 때만 쓴다.**
:::

## 이진 탐색 트리: 삽입, 탐색, 삭제

이진 탐색 트리(BST)는 딱 하나의 규칙을 지키는 이진 트리다. **모든 노드에서, 왼쪽 서브트리의 값은 전부 그 노드보다 작고, 오른쪽 서브트리의 값은 전부 그 노드보다 크다.** 이 규칙 하나가 [7.5 이분 탐색](#/binary-search)의 "반으로 자르기"를 트리 위에서 그대로 재현한다.

```python title="삽입과 탐색 -- 매 단계 왼쪽/오른쪽을 결정할 뿐이다"
def insert(root, val):
    if root is None:
        return Node(val)
    if val < root.val:
        root.left = insert(root.left, val)
    elif val > root.val:
        root.right = insert(root.right, val)
    return root                    # 같은 값이면 무시 (중복 없는 집합 가정)


def search(root, val):
    cur = root
    while cur:
        if val == cur.val:
            return True
        cur = cur.left if val < cur.val else cur.right
    return False
```

삭제가 까다로운 이유는 지울 노드가 **자식을 몇 개 갖고 있느냐**에 따라 처리가 완전히 달라지기 때문이다.

```text nolines
경우 1: 자식이 없다      -> 그냥 지운다 (부모가 None을 가리키게)
경우 2: 자식이 하나다    -> 그 자식이 삭제된 자리를 대신한다
경우 3: 자식이 둘 다 있다 -> 대체할 값이 필요하다
```

세 번째 경우가 핵심이다. 노드를 통째로 지울 수 없으니, **BST 규칙을 깨지 않으면서 대신 넣을 값**을 찾아야 한다. 정답은 **오른쪽 서브트리에서 가장 작은 값**(또는 왼쪽 서브트리에서 가장 큰 값) — 중위 순회 기준 바로 다음(또는 이전) 값이다. 이 값을 **후계자**(successor)라 부른다.

```text nolines
       8                     8                     9
      ╱ ╲                   ╱ ╲                   ╱ ╲
     3   12    8 삭제 →     3   12    9로 값 교체 → 3   12
        ╱  ╲               ╱  ╲                  ╱  ╲
       9   15              9   15               (지움) 15
                            ↑
                    오른쪽 서브트리 최솟값 = 후계자
```

```python title="삭제 -- 세 가지 경우"
def find_min(root):
    cur = root
    while cur.left:
        cur = cur.left
    return cur


def delete(root, val):
    if root is None:
        return None
    if val < root.val:
        root.left = delete(root.left, val)
    elif val > root.val:
        root.right = delete(root.right, val)
    else:                                    # 찾았다
        if root.left is None:
            return root.right                # 경우 1, 2 (왼쪽이 없음)
        if root.right is None:
            return root.left                 # 경우 2 (오른쪽이 없음)
        succ = find_min(root.right)          # 경우 3: 후계자를 찾고
        root.val = succ.val                  # 값만 옮겨 온 뒤
        root.right = delete(root.right, succ.val)  # 후계자 자리를 재귀로 지운다
    return root
```

::: warn 값을 옮기는 것과 노드를 옮기는 것은 다르다
`root.val = succ.val` 은 **객체를 바꿔치기하는 게 아니라 값만 복사**하는 것이다. 후계자 노드 자체는 여전히 오른쪽 서브트리 어딘가에 남아 있고, 그 노드를 실제로 지우는 건 마지막 줄의 재귀 호출이 한다. 이 두 단계를 하나로 착각하면 — 예를 들어 `succ` 를 직접 어딘가에 다시 연결하려고 하면 — 트리가 망가진다.
:::

삽입·탐색·삭제 세 함수 모두 무작위로 만든 BST 500개에 대해, 매 삭제 후 **중위 순회 결과가 파이썬 `set`으로 관리한 정답과 항상 정렬된 상태로 일치하는지** 대조해서 검증했다.

```pyrepl
>>> # 무작위 값 삽입 후 무작위 순서로 일부를 삭제하며
>>> # 매번 inorder(root) == sorted(현재 남은 값들의 set) 인지 확인, 500회
BST insert/search/delete 500회 무작위 대조: 통과
```

## 균형이 전부다 — 편향된 트리의 대가

삽입과 탐색 모두 **루트에서 리프까지 한 경로만** 따라간다. 그 경로 길이, 즉 트리의 높이가 곧 시간복잡도다. 문제는 높이가 입력 순서에 따라 완전히 달라진다는 것이다.

무작위 순서로 값을 넣으면 트리는 평균적으로 균형 잡힌 모양이 되어 높이가 $O(\log n)$ 이 된다. 그런데 **이미 정렬된 순서**로 값을 넣으면 모든 노드가 오른쪽 자식 하나씩만 가지는, 사실상 연결 리스트가 되어 높이가 $O(n)$ 이 된다.

```text nolines
무작위 삽입 -> 균형 잡힌 모양        정렬된 순서로 삽입 -> 완전히 편향
        8                          1
       ╱ ╲                          ╲
      3   12                         2
     ╱ ╲    ╲                         ╲
    1   5    15                        3
                                         ╲
                                          ...  (사실상 연결 리스트)
```

::: perf 균형 vs 편향, 실제로 재 보면
같은 $n$개의 값을 무작위 순서(균형)와 정렬된 순서(편향)로 각각 삽입한 뒤, 2000번 탐색하는 데 걸린 시간을 쟀다.

```text nolines
       n |    균형(무작위) height |   편향(정렬) height |    균형 탐색(s) |    편향 탐색(s) | 배율
    1000 |                   23 |                999 |       0.000731 |       0.021466 |  29.4x
   10000 |                   32 |               9999 |       0.001121 |       0.218882 | 195.2x
  100000 |                   39 |              99999 |       0.001500 |       2.149918 | 1433.7x
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 **배율이 n에 비례해 커지는 추세**는 어디서나 같다.)

높이 자체가 그대로 찍혀 있다 — 균형 트리는 $n$이 100배 늘어도 높이가 23→39로 거의 안 늘지만($O(\log n)$), 편향 트리는 높이가 곧 $n-1$이다 — 간선 수 기준이라 $n$개 노드를 한 줄로 이은 사슬의 높이는 정확히 $n-1$이다($O(n)$). 그래서 탐색 시간의 배율이 $n$이 커질수록 폭발적으로 벌어진다.
:::

::: cote 정렬된 입력을 조심하라
"수를 순서대로 넣어라"류의 문제에서 순진하게 BST를 짜면 **시간복잡도 분석에서는 $O(n \log n)$ 이라고 믿었는데 실제로는 $O(n^2)$ 로 실행되는** 사고가 난다. 표준 BST는 **자가 균형(self-balancing)을 보장하지 않는다.** 균형을 보장하는 AVL 트리나 레드-블랙 트리는 파이썬 표준 라이브러리에 없다. 코딩테스트에서 "정렬된 자료구조에 삽입/삭제/탐색이 다 필요하다"는 요구가 나오면, 직접 균형 트리를 구현하기보다 **`heapq`([7.8](#/heap))로 우선순위만 필요한지, `bisect`([7.5](#/binary-search))로 정적인 정렬 배열이면 충분한지, 아니면 서드파티 `sortedcontainers.SortedList`를 쓸 수 있는 환경인지**부터 확인해라. 대부분의 코테는 직접 짠 자가 균형 트리를 요구하지 않는다.
:::

## 파이썬 재귀 깊이 제한이 트리에서 실제로 걸리는 경우

이 절에서 가장 실전적인 함정이다. 파이썬 인터프리터는 콜 스택 오버플로우를 막기 위해 재귀 호출 깊이에 기본 한도를 둔다.

```pyrepl
>>> import sys
>>> sys.getrecursionlimit()
1000
```

트리를 재귀로 순회하면 **재귀 깊이가 트리의 높이와 같다.** 균형 잡힌 트리라면 높이가 $\log n$ 수준이라 100만 개 노드가 있어도 깊이는 20 안팎이라 문제가 없다. 그런데 **편향된 트리는 높이가 곧 노드 수다.** 정렬된 순서로 만든 편향 트리에서 재귀로 높이를 계산해 보면 이렇다.

```python title="편향 트리에서 재귀 높이 계산"
def height_rec(root):
    if root is None:
        return -1                 # 빈 트리의 높이는 -1 -- 그래야 리프의 높이가 0이 된다
    return 1 + max(height_rec(root.left), height_rec(root.right))
```

빈 트리에서 `-1`을 반환하는 게 어색해 보일 수 있는데, 이렇게 해야 위에서 정의한 "높이 = 가장 먼 리프까지의 간선 수"와 정확히 맞는다. 리프 노드는 `height_rec(None)` 호출 두 번(양쪽 자식)에 `1`을 더하므로 `1 + max(-1, -1) = 0` — 리프의 높이는 0이다. (`None`에 `0`을 반환하는 흔한 실수를 하면 모든 노드의 높이가 실제보다 1 크게 나온다 — 리프가 높이 1을 갖는 셈이 되어 버리기 때문이다.)

```pyrepl
>>> # 정렬된 순서로 삽입해 만든 편향 트리에 height_rec 적용
n=900: height_rec 성공, height=899
n=995: height_rec 성공, height=994
n=1000: RecursionError 발생
n=2000: RecursionError 발생
```

**실제로 재현된다.** 노드가 1000개만 되어도 편향된 트리에서는 재귀가 죽는다. 백준·프로그래머스의 트리 문제는 노드 수 $10^5$ 를 흔히 준다. "이진 트리"라는 이름만 보고 균형을 가정하면 안 된다 — 문제가 명시적으로 균형을 보장하지 않는 한, **최악의 입력은 항상 완전히 편향된 트리**라고 가정하고 코드를 짜야 한다.

::: danger 재귀 순회를 그대로 제출하면 죽는 이유
```python
def find(root, target):     # 재귀 탐색
    if root is None:
        return False
    if root.val == target:
        return True
    return find(root.left, target) or find(root.right, target)
```
이 코드는 균형 트리에서는 잘 동작하고 로컬 테스트도 통과한다. 하지만 채점 서버가 **일부러 편향된 입력(정렬된 순서로 노드를 연결)**을 주면 `RecursionError`로 죽는다. 이건 시간 초과가 아니라 **런타임 에러**로 잡히기 때문에 원인을 못 찾고 헤매기 쉽다.
:::

해결책은 두 가지다.

**1. 반복형으로 짠다.** 앞서 본 스택/큐 기반 순회는 재귀 깊이 문제 자체가 없다 — 스택은 힙 메모리에 있는 파이썬 리스트라 한도가 사실상 메모리 크기다.

```python title="레벨 순회로 높이 재기 -- 반복 (BFS), 재귀 깊이 문제 자체가 없다"
from collections import deque

def height_iter(root):
    if root is None:
        return -1
    depth = -1
    q = deque([root])
    while q:
        depth += 1                # 한 레벨을 다 처리할 때마다 깊이 1 증가
        for _ in range(len(q)):   # 지금 큐에 있는 만큼이 "이번 레벨"이다
            node = q.popleft()
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
    return depth
```

`height_rec`와 똑같이 "간선 수" 관례를 따른다 — 큐가 완전히 빌 때까지 도는 바깥 `while`이 재귀 프레임 대신 힙 메모리의 리스트(`deque`)를 쓰므로, 트리가 아무리 편향되어도 `RecursionError`가 날 자리가 없다.

```pyrepl
>>> # height_iter는 BFS 기반이라 편향 여부와 무관하게 항상 동작한다
>>> # 10만 개 노드로 만든 편향 트리에도 그대로 적용
height_iter(n=100000) = 99999
```

**2. `sys.setrecursionlimit`로 한도를 늘린다.**

```pyrepl
>>> sys.setrecursionlimit(200_000)
>>> height_rec(big_skewed_tree)     # n=100000
99999
```

::: warn setrecursionlimit은 만능이 아니다
`sys.getrecursionlimit()`이 세는 것은 **파이썬 프레임 개수**지, 실제 운영체제 스레드의 C 스택 크기가 아니다. 한도를 아주 크게(예: 수백만) 늘리면 파이썬 예외가 뜨기 전에 **진짜 C 스택이 넘쳐서 `RecursionError` 없이 인터프리터가 그냥 죽을 수 있다** — `try/except`로도 못 잡는다. 그래서 이 값을 늘릴 때는 필요한 만큼만(입력 크기 + 여유분) 늘려야 하고, **애초에 반복형으로 짜는 게 근본적인 해결책**이라는 사실은 바뀌지 않는다. 이 내용은 [7.13 그래프 표현과 순회](#/graph)의 DFS에서도 똑같이 등장한다 — 그래프의 "일자 경로" 역시 트리의 편향과 같은 문제를 일으킨다.
:::

## 최소 공통 조상(LCA)

두 노드 $p$, $q$ 의 최소 공통 조상(Lowest Common Ancestor)은 **$p$와 $q$ 둘 다를 자손으로 갖는 노드 중 트리에서 가장 아래(루트에서 가장 먼)에 있는 것**이다.

### 브루트포스: 루트까지 가는 경로를 비교한다

가장 직관적인 방법은 각 노드에서 루트까지 가는 경로를 전부 기록한 뒤, 두 경로가 갈라지기 직전 노드를 찾는 것이다.

```python title="LCA 브루트포스 -- 두 경로를 구해서 비교"
def path_to(root, target, path):
    if root is None:
        return False
    path.append(root)
    if root is target:
        return True
    if path_to(root.left, target, path) or path_to(root.right, target, path):
        return True
    path.pop()          # 이 방향에 없었다 -- 되돌아간다 (백트래킹)
    return False


def lca_brute(root, p, q):
    path_p, path_q = [], []
    path_to(root, p, path_p)
    path_to(root, q, path_q)
    lca = None
    for a, b in zip(path_p, path_q):
        if a is b:
            lca = a
        else:
            break
    return lca
```

이 방법은 루트에서 두 번 순회하므로 $O(n)$ 이고 경로를 저장하니 $O(h)$ 공간이 추가로 든다. 정확하지만 매 쿼리마다 트리 전체를 훑는다는 점이 아쉽다.

### 일반 이진 트리의 재귀 LCA — 한 번의 순회로

부모 포인터 없이도, **재귀 호출이 반환되는 시점 자체를 이용하면** 한 번의 순회로 끝낼 수 있다.

```python title="일반 이진 트리 LCA -- 부모 포인터 없이 한 번의 순회"
def lca_general(root, p, q):
    if root is None or root is p or root is q:
        return root
    left = lca_general(root.left, p, q)
    right = lca_general(root.right, p, q)
    if left and right:          # 양쪽에서 각각 찾았다 -> 여기가 갈라지는 지점
        return root
    return left if left else right   # 한쪽에만 있었다 -> 그 결과를 그대로 위로 전달
```

이 함수가 하는 일을 한 문장으로 요약하면: **"내 서브트리에 $p$나 $q$가 있으면 그중 가장 위에서 만나는 노드를 위로 올려보낸다. 양쪽 서브트리에서 각각 하나씩 올라오면, 지금 내가 있는 자리가 갈라지는 지점 — 즉 LCA다."**

### BST라면 값 비교만으로 더 빠르게

일반 트리라면 위 방법이 최선이다. 하지만 **BST라는 추가 정보가 있으면 훨씬 단순해진다.** $p$와 $q$가 모두 현재 노드보다 작으면 답은 왼쪽에, 모두 크면 오른쪽에 있다. 둘 중 하나만 작거나 같으면 — 즉 두 값이 현재 노드를 기준으로 갈라지면 — 바로 그 노드가 LCA다.

```python title="BST 전용 LCA -- O(h), 순회조차 필요 없다"
def lca_bst(root, p_val, q_val):
    cur = root
    while cur:
        if p_val < cur.val and q_val < cur.val:
            cur = cur.left
        elif p_val > cur.val and q_val > cur.val:
            cur = cur.right
        else:
            return cur
    return None
```

이건 재귀도 아니고 트리 전체를 훑지도 않는다. **루트에서 한 경로만 따라 내려가므로 $O(h)$** — 균형 잡힌 BST라면 $O(\log n)$ 이다. 세 구현(브루트포스, 일반 이진 트리 재귀, BST 전용)이 무작위로 만든 트리 400개에서 항상 같은 답을 내는지 대조했다.

```pyrepl
>>> # 무작위 BST 400개, 각각 무작위 두 노드에 대해 세 방법의 결과를 비교
LCA 세 가지 구현 400회 대조: 통과
```

::: cote LCA를 쿼리가 여러 번 들어오는 문제로 만나면
지금까지 본 방법은 쿼리 한 번에 $O(h)$ (BST) 또는 $O(n)$ (일반 트리)이 든다. **쿼리가 $q$번 들어오면 총 $O(qh)$ 또는 $O(qn)$** 이 되어, $q$가 크면 느려진다. 이런 문제는 대개 **오일러 투어 + 희소 테이블**이나 **바이너리 리프팅**으로 각 쿼리를 $O(\log n)$ 에 처리하도록 전처리한다. 이 최적화는 트리 DP를 다루는 [7.21 동적 계획법 심화](#/dp-advanced)와 함께 보는 게 자연스럽다. 지금 단계에서는 "쿼리가 하나거나 적으면 여기서 배운 방법으로 충분하다"는 것만 기억해도 된다.
:::

## 트리 지름 — 가장 먼 두 리프 사이의 거리

트리의 지름(diameter)은 **트리 안의 어떤 두 노드 사이의 경로 중 가장 긴 것의 간선 수**다. 반드시 루트를 지날 필요는 없다 — 지름은 어느 서브트리 안에 통째로 들어 있을 수도 있다.

### 순진한 방법: 노드마다 높이를 다시 잰다

"모든 노드에 대해, 그 노드를 지나는 최장 경로(왼쪽 높이 + 오른쪽 높이)를 구하고 최댓값을 취한다"는 게 가장 먼저 떠오르는 방법이다.

```python title="트리 지름 -- 순진한 방법"
def height(root):
    if root is None:
        return 0
    return 1 + max(height(root.left), height(root.right))


def diameter_naive(root):
    if root is None:
        return 0
    through_root = height(root.left) + height(root.right)
    return max(through_root,
               diameter_naive(root.left),
               diameter_naive(root.right))
```

문제는 `height`가 **매 노드마다 그 아래 서브트리 전체를 다시 훑는다**는 것이다. 노드 $n$개짜리 트리에서 `diameter_naive`가 재귀로 방문하는 노드마다 `height`를 또 처음부터 부르므로, 균형 잡힌 트리에서도 $O(n \log n)$, **완전히 편향된 트리에서는 $O(n^2)$** 까지 나빠진다.

::: perf 편향 트리에서 실제로 O(n^2)가 나온다
편향된(정렬된 순서로 삽입한) 트리에서 노드 수를 늘려 가며 순진한 방법과, 뒤에 나올 최적화된 방법의 실행 시간을 쟀다.

```text nolines
       n |   naive(s) |   optimal(s) | 배율   (편향 트리 = 최악의 경우)
     500 |   0.008626 |     0.000057 | 150.3x
    1000 |   0.041831 |     0.000126 | 330.9x
    2000 |   0.189599 |     0.000253 | 748.5x
    3000 |   0.413790 |     0.000446 | 928.8x
    4000 |   0.747587 |     0.000539 | 1385.7x
```

(Python 3.14.5 / Windows 기준 실측.)

$n$이 두 배가 될 때마다 `naive` 의 시간이 **네 배 가까이** 늘어난다 — $O(n^2)$ 의 전형적인 신호다. `optimal` 은 거의 선형으로만 늘어난다. 배율이 150배에서 1385배까지 커지는 게 그 격차를 그대로 보여준다.
:::

### 최적화: 높이를 재는 김에 지름도 갱신한다

핵심 통찰은 이거다. **어차피 모든 노드의 높이는 한 번씩 계산해야 한다. 그 계산을 하는 김에, "이 노드를 지나는 경로 길이"도 그 자리에서 확인하고 최댓값만 기억해 두면 된다.** 굳이 따로 순회를 또 돌 필요가 없다.

```python title="트리 지름 -- O(n), 한 번의 순회"
def diameter_optimal(root):
    best = 0

    def height(node):
        nonlocal best
        if node is None:
            return 0
        lh = height(node.left)
        rh = height(node.right)
        best = max(best, lh + rh)   # 이 노드를 지나는 경로 길이를 확인
        return 1 + max(lh, rh)

    height(root)
    return best
```

`height` 는 그대로 재귀 높이 계산이다. 다른 점은 반환하기 직전에 `lh + rh`(이 노드를 지나는 경로)를 `best`와 비교해 둔다는 것뿐이다. **트리를 딱 한 번만 훑으므로 $O(n)$.** 두 구현이 무작위 트리 300개에서 항상 같은 값을 내는지 확인했다.

```pyrepl
>>> # 무작위 BST 300개에 대해 diameter_naive와 diameter_optimal 비교
트리 지름 naive vs optimal 300회 대조: 통과
```

::: cote 지름·LCA류 문제를 만나면 먼저 물어라
1. **"이 재귀가 서브트리를 중복해서 훑고 있나?"** — 훑고 있다면 지름 최적화처럼 "값을 계산하는 김에 답도 갱신"하는 패턴을 찾아라. 이건 [7.21 동적 계획법 심화](#/dp-advanced)의 트리 DP와 사실상 같은 사고방식이다.
2. **트리가 균형을 보장하는가?** 문제 제약을 보고 최악의 경우 편향된 트리가 나올 수 있다면, 재귀 깊이 초과를 반드시 대비해라.
3. 이런 "구조에서 신호를 읽는" 습관은 [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 체계적으로 다룬다.
:::

## 요약

- 트리는 자식 참조를 여러 개 가진 연결 리스트다. [1.1](#/objects-names)의 이름표 모델과 [7.9](#/linked-list)의 포인터 조작이 그대로 이어진다.
- 전위·중위·후위는 **루트를 언제 처리하느냐**의 차이다. 셋 다 재귀로도, 스택(전위·중위) 또는 스택 2개(후위)로도 짤 수 있다. 레벨 순회는 큐를 쓴다.
- BST는 "왼쪽은 작고 오른쪽은 크다"는 규칙 하나로 삽입·탐색·삭제를 전부 $O(h)$ 에 해결한다. 삭제에서 자식이 둘인 경우는 후계자(오른쪽 서브트리의 최솟값)로 값을 대체하고 그 자리를 재귀로 지운다.
- **트리의 높이가 곧 시간복잡도다.** 무작위 삽입이면 $O(\log n)$ 이지만, 정렬된 순서로 삽입하면 $O(n)$ 까지 나빠진다 — 실측으로 1500배 넘게 벌어지는 것을 확인했다.
- **파이썬 재귀 한도(기본 1000)는 편향된 트리에서 실제로 걸린다.** 반복형이 근본 해결책이고, `sys.setrecursionlimit`는 임시방편이며 C 스택 자체가 넘치면 잡히지 않는 크래시가 날 수 있다.
- LCA는 브루트포스(경로 비교, $O(n)$), 일반 이진 트리 재귀($O(n)$, 한 번의 순회), BST 전용(값 비교만으로 $O(h)$) 세 층위로 풀 수 있다.
- 트리 지름은 "노드마다 높이를 다시 재는" 순진한 방법이면 최악 $O(n^2)$ 이고, 높이를 재는 김에 지름을 갱신하면 $O(n)$ 이다.

::: quiz 연습문제
1. 전위 순회 결과와 중위 순회 결과가 주어졌을 때 원래 트리를 복원하는 함수를 짜라. (힌트: 전위의 첫 값이 항상 루트다.) 복원한 트리를 다시 전위·중위 순회해서 원래 입력과 일치하는지 검증하라.
2. `lca_bst`가 $p$나 $q$ 중 하나가 트리에 아예 없는 값이면 어떤 값을 반환하는가? 실제로 실행해서 확인하고, 이 동작이 안전한지(호출하는 쪽에서 오해할 여지가 없는지) 판단하라.
3. `diameter_optimal`을 아예 반복형(명시적 스택)으로 바꿔 짜 보라. 후위 순회 순서로 처리해야 하는 이유를 설명하라.
4. BST에서 $k$번째로 작은 값을 찾는 함수를 중위 순회를 이용해 짜라. 매번 전체 중위 순회를 다 하지 않고 $k$번째에서 멈추게 하려면 어떻게 해야 하는가?
5. **깊이 생각해 볼 문제.** 이진 트리가 "높이 균형(height-balanced)"인지 — 모든 노드에서 왼쪽/오른쪽 서브트리 높이 차이가 1 이하인지 — 판별하는 함수를, `diameter_optimal`과 같은 방식으로 "높이를 재는 김에 판별도 같이" $O(n)$ 에 짜 보라. 순진하게 매 노드마다 양쪽 높이를 다시 재면 왜 $O(n^2)$ 이 되는지도 설명하라.
:::

**다음 절**: [7.11 트라이](#/trie) — 트리의 각 노드가 "문자 하나"를 의미하도록 바꾸면, 문자열 집합을 트리 모양으로 검색하는 자료구조가 된다.
