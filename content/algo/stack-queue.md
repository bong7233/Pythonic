# 7.7 스택과 큐

::: lead
스택과 큐는 자료구조 중 가장 단순하다. 그런데 코딩테스트에서 가장 많이 사고를 내는 것도 이 둘이다. 원인은 하나다 — 파이썬의 `list` 하나로 둘 다 만들 수 있다고 착각하기 때문이다. 스택은 `list`로 충분하지만 큐는 아니다. 이 절은 그 이유를 실측으로 보여주고, 스택이 만드는 대표 패턴인 **괄호 매칭**과 **단조 스택**을 다룬다. [7.1 복잡도](#/complexity)에서 상수의 무게를 얘기했는데, 여기서 그 상수가 실제로 몇 배 차이를 내는지 눈으로 본다.
:::

## 스택: `list` 하나로 충분하다

스택은 **LIFO**(Last In, First Out) — 마지막에 넣은 게 먼저 나온다. 함수 호출, 되돌리기(undo), 괄호 짝, [7.14 BFS/DFS](#/bfs-dfs)의 DFS 반복 구현까지 전부 스택이다.

파이썬에서 스택은 그냥 `list`다. `append`로 넣고 `pop()`(인자 없이, 즉 맨 뒤)으로 꺼낸다.

```python title="스택 기본 연산"
stack = []
stack.append(1)
stack.append(2)
stack.append(3)
stack.pop()          # 3 — 마지막에 넣은 게 먼저 나온다
stack.pop()          # 2
stack               # [1]
```

왜 `list`의 끝(오른쪽)을 쓰는지가 중요하다. CPython의 `list`는 내부적으로 포인터 배열이고, 끝에 여유 공간을 남겨 두는 방식으로 증폭한다([7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 다룬다). **끝에서 넣고 빼는 것은 배열을 밀 필요가 없어 상수 시간**이다.

```text nolines
push(4)                     pop()
   ┌───┬───┬───┬───┐           ┌───┬───┬───┐
   │ 1 │ 2 │ 3 │ 4 │  ──────▶  │ 1 │ 2 │ 3 │   4가 빠진다
   └───┴───┴───┴───┘           └───┴───┴───┘
                 ▲                         ▲
              top (끝)                  top (끝)
```

::: perf append/pop 이 진짜로 리스트 크기와 무관한가
직접 재 봐야 믿을 수 있다. 리스트 크기를 1천에서 100만까지 늘려 가며 `append` + `pop` 을 10만 번씩 반복했다.

```python title="stack_bench.py"
import timeit

for n in [1_000, 10_000, 100_000, 1_000_000]:
    setup = f"lst = list(range({n}))"
    t = timeit.timeit("lst.append(1); lst.pop()", setup=setup, number=100_000)
    print(f"n={n:8d}  1회당 {t / 100_000 * 1e9:.1f}ns")
```

```text nolines
n=    1000  1회당 19.8ns
n=   10000  1회당 18.5ns
n=  100000  1회당 18.4ns
n= 1000000  1회당 31.7ns
```

(Python 3.14.5 / Windows 기준 실측.) 리스트가 1천 개든 100만 개든 한 번의 `append`+`pop` 은 20ns 근방에서 거의 그대로다. **크기가 늘어도 시간이 늘지 않는다 — 이게 $O(1)$ 의 의미다.** 아주 가끔(용량이 꽉 찼을 때) 배열 전체를 재할당하는 비용이 들지만, 그 비용을 여러 번의 호출에 나눠 갚는다고 보면 평균은 상수다. 이걸 **분할 상환**(amortized) $O(1)$ 이라 부른다.
:::

여기까지는 스택이 착하다. 문제는 **끝이 아니라 앞**에서 넣고 빼려고 할 때 생긴다 — 그게 큐다.

## 큐: 왜 `list`로 만들면 안 되는가

큐는 **FIFO**(First In, First Out) — 먼저 넣은 게 먼저 나온다. BFS([7.14](#/bfs-dfs))의 핵심 자료구조가 바로 큐다.

`list`로 큐를 흉내 내려는 사람은 보통 이렇게 쓴다.

```python
# ❌ 큐를 리스트로 만들면
queue = [1, 2, 3]
queue.append(4)        # 뒤에 넣기 — 괜찮다
queue.pop(0)            # 앞에서 빼기 — 문제는 여기
```

`pop(0)` 은 **첫 번째 원소를 지운 뒤, 나머지 원소를 전부 한 칸씩 왼쪽으로 당긴다.** 배열 기반 자료구조에서 앞쪽 삭제는 반드시 이 대가를 치른다.

```text nolines
pop(0)
   ┌───┬───┬───┬───┐        ┌───┬───┬───┐
   │ 1 │ 2 │ 3 │ 4 │ ─────▶ │ 2 │ 3 │ 4 │    2,3,4가 전부 한 칸씩 이동
   └───┴───┴───┴───┘        └───┴───┴───┘
```

원소가 $n$ 개면 매번 최대 $n-1$ 번의 이동이 필요하다. 큐 연산을 $n$ 번 반복하면 $O(n^2)$ 이 된다.

::: perf list.pop(0) vs deque.popleft() 실측
큐 하나에 원소 $n$개를 넣고 전부 빼는 데 걸리는 시간을 쟀다.

```python title="bench_queue.py"
import time
from collections import deque

def bench_list_pop0(n):
    lst = list(range(n))
    start = time.perf_counter()
    while lst:
        lst.pop(0)
    return time.perf_counter() - start

def bench_deque_popleft(n):
    dq = deque(range(n))
    start = time.perf_counter()
    while dq:
        dq.popleft()
    return time.perf_counter() - start
```

```text nolines
n= 10000  list.pop(0)=0.00213s  deque.popleft()=0.00014s  ratio=15.2x
n= 20000  list.pop(0)=0.00893s  deque.popleft()=0.00029s  ratio=30.8x
n= 40000  list.pop(0)=0.03660s  deque.popleft()=0.00058s  ratio=62.9x
n= 80000  list.pop(0)=0.14303s  deque.popleft()=0.00122s  ratio=116.8x
```

(Python 3.14.5 / Windows 기준 실측.) $n$ 이 두 배가 될 때 `list.pop(0)` 시간은 대략 **네 배**로 늘어난다 — $O(n^2)$ 의 전형적인 지문이다. `deque.popleft()` 는 대략 **두 배**로 늘어난다 — $O(n)$, 즉 원소 하나당 상수 시간이라는 뜻이다. $n=80000$ 에서 이미 100배 넘게 차이가 난다. 백준·프로그래머스에서 $n$ 이 10만을 넘는 BFS 문제에 `list.pop(0)` 을 쓰면 십중팔구 시간 초과다.
:::

### `deque` 는 왜 양쪽 다 빠른가

`collections.deque` 는 **양방향 고정 크기 블록들을 이어 붙인 이중 연결 리스트**다. 각 블록은 보통 64개 원소를 담는 작은 배열이고, 블록끼리는 포인터로 연결된다.

```text nolines
   ┌────────────┐   ┌────────────┐   ┌────────────┐
◀──┤ block(64)  │◀──┤ block(64)  │◀──┤ block(64)  ├──▶
   └────────────┘   └────────────┘   └────────────┘
      leftmost                          rightmost
```

앞이나 뒤에 원소를 넣고 뺄 때는 **해당 끝 블록 안의 포인터만 움직이면 된다.** 블록이 꽉 차면 새 블록을 하나 이어 붙일 뿐, 기존 원소를 옮기지 않는다. 그래서 `appendleft` / `popleft` / `append` / `pop` 넷 다 $O(1)$ 이다.

대신 대가가 있다. **가운데 원소에 접근하려면 블록을 하나씩 따라가야 한다.** `list`의 인덱싱은 주소 계산 한 번으로 끝나지만, `deque`는 블록을 순회해야 한다.

::: perf deque 인덱싱은 O(n) 이다
```python
import timeit
from collections import deque

for n in [10_000, 100_000, 1_000_000]:
    t_list = timeit.timeit(f"lst[{n}//2]", setup=f"lst=list(range({n}))", number=100_000)
    t_deque = timeit.timeit(f"dq[{n}//2]", setup=f"from collections import deque; dq=deque(range({n}))", number=100_000)
    print(f"n={n:8d}  list={t_list:.5f}s  deque={t_deque:.5f}s  ratio={t_deque/t_list:.1f}x")
```

```text nolines
n=   10000  list=0.00086s  deque=0.00707s  ratio=8.2x
n=  100000  list=0.00095s  deque=0.16241s  ratio=170.4x
n= 1000000  list=0.00089s  deque=2.11438s  ratio=2383.7x
```

`list[n//2]` 는 $n$ 이 100배 커져도 시간이 그대로다 — $O(1)$. `dq[n//2]` 는 $n$ 에 거의 비례해서 늘어난다 — $O(n)$. **`deque`는 양 끝 전용 자료구조다.** 가운데를 자주 들여다봐야 한다면 `list`를 써야 한다.
:::

::: cote deque로 큐 구현
```python title="deque 큐"
from collections import deque

q = deque()
q.append(1)          # 뒤로 넣기 — enqueue
q.append(2)
q.popleft()           # 앞에서 빼기 — dequeue, O(1)
```

BFS 템플릿은 거의 항상 이 모양이다.

```python title="BFS 뼈대"
from collections import deque

def bfs(start, graph):
    visited = {start}
    q = deque([start])
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in graph[node]:
            if nxt not in visited:
                visited.add(nxt)
                q.append(nxt)
    return order
```

`deque(maxlen=k)` 로 만들면 **크기 $k$짜리 슬라이딩 윈도우**가 된다. 꽉 찬 상태에서 반대쪽에 넣으면 오래된 원소가 자동으로 밀려난다. [7.3 투 포인터·슬라이딩 윈도우](#/two-pointers)와 조합하면 최근 $k$개 최댓값 같은 문제에 바로 쓴다.
:::

## 괄호 매칭 — 스택의 원형 문제

"올바른 괄호인가?"는 스택이 왜 존재하는지를 가장 압축해서 보여주는 문제다. `(`, `)`, `[`, `]`, `{`, `}` 로만 이뤄진 문자열이 올바르게 짝지어졌는지 판정한다.

여는 괄호를 만나면 **나중에 어떤 닫는 괄호가 와야 하는지 기억해 둬야** 하고, 그 기억은 **가장 최근 것부터 확인**해야 한다 — 전형적인 LIFO다.

```python title="괄호 검증 — 스택"
def is_valid(s: str) -> bool:
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        elif ch in ')]}':
            if not stack or stack.pop() != pairs[ch]:
                return False   # 닫을 게 없거나 짝이 안 맞는다
    return not stack           # 남은 여는 괄호가 없어야 한다
```

**두 가지를 놓치기 쉽다.** 첫째, `stack.pop() != pairs[ch]` 전에 `not stack` 을 먼저 확인해야 한다 — 빈 스택에서 `pop()` 은 `IndexError`다. 둘째, 마지막에 `return not stack` 이 필요하다. `"((("` 처럼 닫는 괄호가 하나도 없으면 루프 안에서는 아무 문제도 안 걸리기 때문이다.

::: cote 괄호 문제에서 자주 나오는 함정
- **여는 괄호만 있고 안 닫힌 경우**: 루프가 끝난 뒤 `stack`이 비어 있는지 반드시 확인한다.
- **닫는 괄호가 먼저 나오는 경우**(`")("`): `not stack` 체크가 없으면 `IndexError`로 죽는다.
- 문제에 따라 괄호 외의 문자가 섞여 있을 수 있다 — 그 문자는 무시하고 지나가야 하는지 확인하라.
- "괄호의 최대 깊이"를 물으면 스택 대신 **카운터 하나**로 충분하다. 짝의 종류를 구분할 필요가 없으면 스택 자체가 과하다.
:::

::: perf 스택 없이 짝을 지우는 방법은 왜 느린가
"`()`, `[]`, `{}` 를 문자열에서 안 나올 때까지 반복해서 지운다"는 접근도 정답은 맞힌다. 그런데 `str.replace`는 매번 **문자열 전체를 새로 훑고 새로 만든다**([1.1 객체·이름·참조](#/objects-names)에서 본 것처럼 `str`은 불변이다). 괄호가 바깥쪽부터 안쪽으로 중첩된 경우, 한 겹을 지우는 데 한 번의 전체 스캔이 필요하고 이런 겹이 $n/2$개까지 있을 수 있다 — $O(n^2)$.

```python title="parens_bench.py"
def is_valid_naive(s: str) -> bool:
    prev_len = -1
    while len(s) != prev_len:
        prev_len = len(s)
        s = s.replace("()", "").replace("[]", "").replace("{}", "")
    return s == ""
```

`"(" * n + ")" * n` (괄호 $n$쌍이 완전히 중첩된 최악의 경우)으로 실측했다.

```text nolines
n=  2000  naive=0.00482s  stack=0.000119s  ratio=40.6x
n=  4000  naive=0.01802s  stack=0.000228s  ratio=78.9x
n=  8000  naive=0.06145s  stack=0.000451s  ratio=136.3x
n= 16000  naive=0.25589s  stack=0.000867s  ratio=295.0x
n= 32000  naive=0.98726s  stack=0.001734s  ratio=569.2x
```

$n$이 두 배가 될 때마다 `naive`는 시간이 대략 네 배로 늘고(=$O(n^2)$), 스택 방식은 대략 두 배로 는다(=$O(n)$). $n=32000$에서 이미 500배 넘게 차이 난다. **"정답은 맞는데 시간 초과"의 전형이다.** [8.3 시간 초과를 피하는 관용구](#/tle)에서 이런 패턴을 더 다룬다.
:::

## 단조 스택: 무식하게 풀면 $O(n^2)$인 문제를 $O(n)$으로

이제 이 절에서 가장 중요한 패턴이다. 문제를 먼저 보자.

> 배열이 주어질 때, 각 원소에 대해 **자신보다 오른쪽에 있으면서 자신보다 큰 첫 번째 원소**(다음 더 큰 원소, next greater element)를 찾아라. 없으면 -1.

### 무식한 방법부터

가장 먼저 떠오르는 풀이는 각 원소마다 오른쪽을 전부 훑는 것이다.

```python title="브루트포스 — O(n²)"
def next_greater_brute(nums):
    n = len(nums)
    result = [-1] * n
    for i in range(n):
        for j in range(i + 1, n):
            if nums[j] > nums[i]:
                result[i] = nums[j]
                break
    return result
```

이중 반복문이 눈에 보인다. $n$이 커지면 반드시 문제가 생긴다.

### 왜 안쪽 반복문이 낭비인가

`nums[i]` 를 처리할 때 이미 스캔한 `nums[i+1], ..., ` 중에서 **아직 자기보다 큰 걸 못 찾은 원소들**을 생각해 보자. 그 원소들은 전부 **아직 다음 더 큰 원소를 기다리는 중**이다. 그리고 그 원소들끼리는 **왼쪽에서 오른쪽으로 갈수록 값이 감소**한다 — 만약 증가했다면 더 왼쪽 것이 이미 답을 찾았을 것이기 때문이다.

이 "기다리는 중이고, 감소하는 순서로 쌓여 있는" 목록이 바로 **단조 스택**(monotonic stack)이다. 새 원소가 들어올 때 스택 꼭대기보다 크면, 꼭대기는 **드디어 답을 찾은 것**이므로 꺼내서 답을 채우고, 새 원소는 계속 그 자리를 이어받아 비교한다.

```python title="단조 스택 — O(n)"
def next_greater_stack(nums):
    n = len(nums)
    result = [-1] * n
    stack = []  # 인덱스를 쌓는다. nums[stack] 은 항상 감소하는 순서다.
    for i, x in enumerate(nums):
        while stack and nums[stack[-1]] < x:
            result[stack.pop()] = x
        stack.append(i)
    return result
```

```text nolines
nums = [2, 1, 2, 4, 3]

i=0(2): stack=[]        -> push        stack=[0]
i=1(1): 1<2, 못 이김      -> push        stack=[0,1]
i=2(2): 2>nums[1]=1     -> pop 1, result[1]=2
        2==nums[0]=2, 못 이김 (더 크지 않음) -> push  stack=[0,2]
i=3(4): 4>nums[2]=2     -> pop 2, result[2]=4
        4>nums[0]=2     -> pop 0, result[0]=4
        stack=[]        -> push        stack=[3]
i=4(3): 3<4, 못 이김      -> push        stack=[3,4]

result = [4, 2, 4, -1, -1]
```

**핵심은 각 인덱스가 스택에 최대 한 번 들어가고 최대 한 번 나온다는 것이다.** `while` 안의 `pop()`이 전체 실행 동안 몇 번 일어나는지 다 더해도 $n$번을 넘을 수 없다. 겉보기엔 이중 반복문이지만 실제 총 작업량은 $O(n)$이다. **분할 상환 분석**의 대표 사례다.

::: cote 답이 정말 맞는지 브루트포스와 대조하라
단조 스택 코드는 겉보기엔 간단한데 인덱스 vs 값, `<` vs `<=` 를 헷갈리면 조용히 틀린다. **제출하기 전에 무식한 풀이와 무작위 입력으로 맞대봐라.**

```python title="검증 코드"
import random

random.seed(0)
for _ in range(1000):
    n = random.randint(0, 20)
    nums = [random.randint(0, 10) for _ in range(n)]
    assert next_greater_brute(nums) == next_greater_stack(nums), nums
print("무작위 1000회 검증 통과")
```

실행하면 `무작위 1000회 검증 통과` 가 나온다. 이렇게 작은 입력에서 브루트포스와 대조하는 습관 하나가, 큰 입력에서 시간 초과 대신 틀린 답을 받는 사고를 막아 준다.
:::

::: perf 실제로 얼마나 차이 나는가
가장 나쁜 경우 — **완전히 감소하는 수열**(`[n, n-1, ..., 1]`)은 다음 더 큰 원소가 아예 없어서, 브루트포스의 안쪽 반복문이 매번 끝까지 스캔한다. 진짜 $O(n^2)$ 최악의 경우다.

```text nolines
n=  1000  brute=0.00826s  stack=0.000050s  ratio=165.6x
n=  2000  brute=0.03269s  stack=0.000085s  ratio=385.4x
n=  4000  brute=0.12936s  stack=0.000162s  ratio=799.5x
n=  8000  brute=0.52517s  stack=0.000354s  ratio=1485.6x
n= 16000  brute=2.14719s  stack=0.000645s  ratio=3326.4x
```

(Python 3.14.5 / Windows 기준 실측.) 브루트포스는 $n$이 두 배 될 때마다 대략 **네 배**씩 느려진다(2000→4000: 3.96배, 8000→16000: 4.09배) — $O(n^2)$. 단조 스택은 대략 **두 배**씩만 늘어난다 — $O(n)$.

이 배율 자체를 외울 필요는 없다. `stack` 쪽 실행 시간이 1밀리초도 안 되는 구간이라 **재실행할 때마다 배율이 크게 흔들린다** — 같은 코드를 다섯 번 더 돌려 보면 $n=16000$에서 3031배, 3262배, 3269배, 3271배, 3427배가 나왔고, 다른 환경에서는 2742배, 2896배까지 낮게 나온 적도 있다. 대략 **수천 배(3000배 안팎)** 수준이라고만 기억하면 된다 — 중요한 건 정확한 배율이 아니라 **한쪽은 $n$의 제곱으로, 한쪽은 $n$에 비례해서 늘어난다는 성장 패턴** 그 자체다. 실제 코딩테스트의 $n \le 10^5$ 규모라면 브루트포스는 확정적으로 시간 초과, 단조 스택은 수십 밀리초 안에 끝난다.
:::

### 단조 스택이 쓰이는 곳

"다음 더 큰 원소"는 단조 스택의 가장 단순한 형태고, 같은 뼈대가 여러 문제로 변형된다.

- **일일 온도**(daily temperatures): 값 대신 **거리**(며칠 뒤인지)를 구하는 버전. `result[stack.pop()] = i - stack.pop_index` 식으로 인덱스 차이를 쓴다.
- **히스토그램에서 가장 큰 직사각형**: 각 막대가 "왼쪽/오른쪽으로 얼마나 넓힐 수 있는지"를 단조 증가 스택으로 구한다. 이건 [7.21 동적 계획법 심화](#/dp-advanced) 근처에서 다시 만난다.
- **최소 스택**(min stack): 스택에 넣을 때마다 "지금까지의 최솟값"도 같이 저장해서, 언제 `pop`해도 O(1)에 최솟값을 안다.

패턴을 알아보는 신호는 이거다 — **"각 원소에 대해 자신보다 왼쪽/오른쪽에서 처음 더 크거나 작은 것을 찾아라"** 라는 문장이 보이면 이중 반복문부터 쓰지 말고 단조 스택을 의심하라. [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 이런 신호들을 더 모아 놓았다.

## 요약

- 스택은 `list`의 `append`/`pop()`(끝 쪽)으로 만든다. 분할 상환 $O(1)$이다.
- 큐를 `list`로 만들면 `pop(0)`이 매번 나머지를 한 칸씩 밀어 $O(n)$이 되고, 전체로는 $O(n^2)$가 된다. 실측 결과 $n=80000$에서 100배 넘게 차이 났다.
- `collections.deque`는 고정 크기 블록의 이중 연결 리스트다. 양 끝은 $O(1)$이지만 가운데 인덱싱은 $O(n)$이다 — 용도가 다른 자료구조다.
- 괄호 매칭은 "가장 최근 걸 먼저 확인해야 한다"는 요구가 스택과 정확히 대응하는 전형적 문제다. 빈 스택 `pop`과 "다 끝난 뒤 스택이 비었는지" 확인을 놓치지 마라.
- 단조 스택은 "다음 더 큰/작은 원소" 류 문제를 이중 반복문 $O(n^2)$에서 $O(n)$으로 낮춘다. 각 인덱스가 스택에 최대 한 번 들어가고 나온다는 게 분할 상환 $O(n)$의 근거다.
- 알고리즘을 구현했으면 브루트포스와 무작위 입력으로 먼저 맞대보고, 그다음에 실제로 시간을 재라. "이론상 O(n)"이 아니라 실측 곡선으로 확인하는 습관이 [Part VIII 코딩테스트 실전](#/cote-strategy)에서 그대로 쓰인다.

::: quiz 연습문제
1. `deque`로 스택을 구현하면(`append`/`pop`) `list`로 구현한 것과 성능이 어떻게 다를까? 위의 벤치마크 방식을 참고해서 직접 재 보고, 이유를 설명하라.
2. 다음 함수가 왜 틀렸는지 찾아라. 반례를 하나 만들어라.

   ```python
   def is_valid_buggy(s: str) -> bool:
       stack = []
       pairs = {'(': ')', '[': ']', '{': '}'}
       for ch in s:
           if ch in pairs:
               stack.append(ch)
           else:
               if stack.pop() != pairs.get(stack[-1] if stack else None):
                   return False
       return True
   ```

3. "다음 더 작은 원소"(next smaller element)를 구하려면 `next_greater_stack` 코드에서 무엇을 바꿔야 하는가? 직접 고치고, 브루트포스와 대조해서 검증하라.
4. 정수 배열에서 "각 원소보다 왼쪽에 있으면서 자신보다 작은 것 중 가장 가까운 것의 인덱스"를 구하는 함수를 단조 스택으로 작성하라. 스택에 무엇을(값인가 인덱스인가) 넣을지부터 결정하라.
5. `[[0] * 3] * 3` 이 왜 위험한지는 [1.1 객체·이름·참조](#/objects-names)에서 다뤘다. 단조 스택 코드에서 `result = [-1] * n` 은 왜 안전한가? 원소가 가변 객체였다면 문제가 생겼을지 생각해 보라.
:::

**다음 절**: [7.8 힙과 우선순위 큐](#/heap) — `heapq`로 최솟값을 $O(\log n)$에 유지하는 법과, 최대 힙이 없는 파이썬에서 최대 힙을 흉내 내는 트릭.
