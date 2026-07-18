# 7.2 파이썬 자료구조의 실제 비용

::: lead
[7.1절](#/complexity)에서 빅오가 무엇인지, 상수가 왜 중요한지를 봤다. 이제 그 지식을 파이썬의 구체적인 자료구조에 꽂아 넣을 차례다. 코딩테스트에서 시간 초과를 받는 사람 대다수는 알고리즘을 몰라서가 아니라 **자료구조를 잘못 골라서** 떨어진다. `list.pop(0)` 하나, `in` 연산 하나가 정답과 시간 초과를 가른다. 이 절이 끝나면 어떤 연산이 왜 느린지 몸으로 알게 된다.
:::

## 리스트에 당하는 흔한 사고

큐를 흉내 내려고 이렇게 쓴 코드를 본 적이 있을 것이다.

```python
# ❌ 앞에서 계속 뺀다
queue = list(range(100000))
while queue:
    x = queue.pop(0)
    # ... x로 뭔가 처리
```

이 코드는 백준이나 프로그래머스에서 **BFS 큐**를 구현할 때 정말 자주 나온다. 그리고 정말 자주 시간 초과를 받는다. 이유를 실측으로 보자.

```python title="bench_pop.py"
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

for n in [1000, 5000, 10000, 20000, 40000, 80000]:
    t_list = bench_list_pop0(n)
    t_deque = bench_deque_popleft(n)
    print(f"n={n:>7} list.pop(0)={t_list:.5f}s deque.popleft()={t_deque:.5f}s  ratio={t_list/t_deque:.1f}x")
```

```text
n=   1000 list.pop(0)=0.00004s deque.popleft()=0.00001s  ratio=2.9x
n=   5000 list.pop(0)=0.00045s deque.popleft()=0.00007s  ratio=6.3x
n=  10000 list.pop(0)=0.00213s deque.popleft()=0.00014s  ratio=14.9x
n=  20000 list.pop(0)=0.00990s deque.popleft()=0.00028s  ratio=35.3x
n=  40000 list.pop(0)=0.03666s deque.popleft()=0.00059s  ratio=62.6x
n=  80000 list.pop(0)=0.14611s deque.popleft()=0.00120s  ratio=121.8x
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

숫자를 읽어라. $n$ 이 두 배가 될 때마다 `list.pop(0)` 은 시간이 **약 4배**가 된다 — 전형적인 $O(n^2)$ 곡선이다. `deque.popleft()` 는 시간이 **약 2배**로 늘어난다 — $O(n)$, 즉 원소 하나당 비용은 그대로다. $n=80000$ 에서는 이미 120배 차이가 나고, 백준 시간 제한(보통 1~2초) 기준으로는 이 지점에서 `list` 버전이 확실히 죽는다.

::: deep 왜 list.pop(0) 은 O(n) 인가
`list` 는 CPython 내부에서 **연속된 메모리 블록에 포인터를 나란히 저장하는 동적 배열**이다 ([1.3 시퀀스](#/sequences)). 인덱스로 원소를 꺼내는 `lst[i]` 는 주소 계산 한 번으로 끝나 $O(1)$ 이다. 문제는 **맨 앞을 뺀 다음**이다.

배열이 연속이어야 한다는 제약 때문에, 앞의 원소 하나가 사라지면 **뒤에 남은 원소 전부를 한 칸씩 왼쪽으로 밀어야** 한다. 원소가 $n$ 개 남아 있으면 $n-1$ 번의 포인터 이동이 일어난다. 그래서 `pop(0)` 은 $O(n)$ 이고, 이걸 $n$ 번 반복하면 $O(n^2)$ 이 된다.

반대로 `lst.pop()` (인자 없이, 맨 뒤를 뺀다)은 밀 것이 없다. $O(1)$ 이다. **리스트는 뒤쪽에서 넣고 빼는 것만 싸다.**
:::

`deque` (double-ended queue)는 CPython에서 **양방향 연결 리스트로 이어진 고정 크기 블록들의 집합**으로 구현된다. 양쪽 끝에 여유 공간을 늘 남겨 두기 때문에 앞/뒤 어느 쪽에서 넣고 빼도 $O(1)$ 이다. 대신 대가가 있다.

```python title="bench_deque_index.py"
import time
from collections import deque

def bench_middle_index(container, n, repeats):
    mid = n // 2
    start = time.perf_counter()
    for _ in range(repeats):
        _ = container[mid]
    return time.perf_counter() - start

for n in [10000, 100000, 1000000]:
    lst = list(range(n))
    dq = deque(range(n))
    t_list = bench_middle_index(lst, n, 200000)
    t_deque = bench_middle_index(dq, n, 200000)
    print(f"n={n:>8}  list[mid] x200000={t_list:.5f}s  deque[mid] x200000={t_deque:.5f}s  ratio={t_deque/t_list:.1f}x")
```

```text
n=   10000  list[mid] x200000=0.00227s  deque[mid] x200000=0.01626s  ratio=7.2x
n=  100000  list[mid] x200000=0.00190s  deque[mid] x200000=0.33557s  ratio=177.0x
n= 1000000  list[mid] x200000=0.00196s  deque[mid] x200000=4.17037s  ratio=2129.3x
```

`list` 의 인덱싱은 $n$ 이 커져도 시간이 그대로다. `deque` 의 중간 인덱싱은 $n$ 에 비례해 느려진다 — 블록들을 따라가야 찾을 수 있기 때문이다. **`deque` 는 양 끝 전용이다. 중간을 자주 들여다봐야 하면 `list` 를 써라.**

::: cote deque 는 언제 쓰는가
BFS 큐, 슬라이딩 윈도우의 양 끝 관리, 최근 $k$ 개만 유지하는 버퍼(`maxlen`) — 전부 양 끝만 건드리는 패턴이다. 인덱싱이나 중간 삽입이 필요하면 애초에 `deque` 를 고르지 않는다. [7.7 스택과 큐](#/stack-queue)에서 BFS 템플릿으로 다시 쓴다.
:::

## 연산별 복잡도 표

코테에서 실전 판단에 쓸 표를 정리한다. $n$ 은 컨테이너의 현재 원소 수다.

### list

| 연산 | 복잡도 | 비고 |
| --- | --- | --- |
| `lst[i]` 인덱싱 | $O(1)$ | 주소 계산 한 번 |
| `lst[i] = x` | $O(1)$ | |
| `lst.append(x)` | $O(1)$ 분할상환 | 가끔 재할당, [7.1절](#/complexity) 참고 |
| `lst.pop()` | $O(1)$ | 맨 뒤 |
| `lst.pop(0)` / `lst.pop(i)` | $O(n)$ | 뒤 원소 전부 이동 |
| `lst.insert(0, x)` / `lst.insert(i, x)` | $O(n)$ | 뒤로 밀어야 함 |
| `x in lst` | $O(n)$ | 순차 탐색 |
| `lst.index(x)` | $O(n)$ | |
| `lst[a:b]` 슬라이싱 | $O(b-a)$ | 새 리스트 생성 |
| `len(lst)` | $O(1)$ | 카운터를 따로 들고 있음 |
| `lst.sort()` | $O(n \log n)$ | [7.4 정렬](#/sorting) |

### dict / set

| 연산 | 평균 | 최악 | 비고 |
| --- | --- | --- | --- |
| `d[k]` 조회/대입 | $O(1)$ | $O(n)$ | 해시 충돌이 심하면 최악 |
| `k in d` / `k in s` | $O(1)$ | $O(n)$ | |
| `del d[k]` | $O(1)$ | $O(n)$ | |
| `d.get(k, default)` | $O(1)$ | $O(n)$ | |
| `dict(a, b, c, ...)` 생성 | $O(n)$ | | 원소 수만큼 |
| `set1 & set2` 교집합 | $O(\min(|s_1|,|s_2|))$ | | 작은 쪽 기준 순회 |
| `set1 \| set2` 합집합 | $O(|s_1|+|s_2|)$ | | |
| 순회 `for k in d` | $O(n)$ | | 삽입 순서 보장 (3.7+) |

최악의 경우는 사실상 걱정할 필요가 없다. 해시 함수가 골고루 흩뿌려 주는 한 평균이 곧 실전이다. 자세한 내부 구조는 [1.6 dict](#/dict), [7.6 해시](#/hashing)에서 다룬다.

### deque

| 연산 | 복잡도 | 비고 |
| --- | --- | --- |
| `dq.append(x)` / `dq.appendleft(x)` | $O(1)$ | 양 끝 전용 |
| `dq.pop()` / `dq.popleft()` | $O(1)$ | |
| `dq[i]` 인덱싱 | $O(n)$ | 중간은 느리다 |
| `dq.insert(i, x)` (양 끝이 아닌 곳) | $O(n)$ | |
| `x in dq` | $O(n)$ | |
| `dq.rotate(k)` | $O(k)$ | |

### heapq (list 위에 구현된 이진 힙)

| 연산 | 복잡도 | 비고 |
| --- | --- | --- |
| `heapq.heappush(h, x)` | $O(\log n)$ | |
| `heapq.heappop(h)` | $O(\log n)$ | |
| `h[0]` (최솟값 확인) | $O(1)$ | 힙 속성상 루트가 최소 |
| `heapq.heapify(lst)` | $O(n)$ | 리스트 전체를 한 번에 힙으로 |
| `heapq.nsmallest(k, lst)` | $O(n \log k)$ | 내부적으로 크기 $k$ 힙 유지 |

```pyrepl
>>> import heapq
>>> h = []
>>> for x in [5, 1, 8, 2, 9, 3]:
...     heapq.heappush(h, x)
>>> h
[1, 2, 3, 5, 9, 8]
>>> heapq.heappop(h)
1
>>> h
[2, 5, 3, 8, 9]
```

`heapq` 는 `list` 를 이진 힙 규칙에 맞게 관리하는 **함수 모음**일 뿐 별도 타입이 아니다. 그래서 `h[0]` 로 최솟값을 훔쳐볼 수 있고, `heapq.heapify` 는 이미 만들어진 리스트를 제자리에서 $O(n)$ 에 힙으로 바꾼다 (원소 하나씩 push하면 $O(n \log n)$ 이니 더 느리다). $k$번째 최솟값·최댓값, 다익스트라의 우선순위 큐가 이 자료구조의 주 무대다. [7.8 힙과 우선순위 큐](#/heap)에서 이어진다.

::: cote in 연산의 비용을 반드시 외워라
표에서 가장 중요한 한 줄만 고르라면 이거다.

> **`x in list` 는 $O(n)$, `x in set`/`x in dict` 는 평균 $O(1)$.**

코테 문제 중 절반은 "이미 나온 값인지 확인해야 한다"는 형태를 띤다. 이 확인을 `list` 로 하면 시간 초과, `set`/`dict` 로 하면 통과다. 다음 절에서 이걸 직접 재본다.
:::

## "in" 하나가 시간 초과를 가른다

이론만으로는 감이 안 온다. 직접 재보자. $n$ 개의 정수를 넣어 두고, 그 안에 있을 수도 없을 수도 있는 값 2000개를 검색한다.

```python title="bench_in.py"
import time
import random

def bench_in(container, queries):
    start = time.perf_counter()
    hits = 0
    for q in queries:
        if q in container:
            hits += 1
    return time.perf_counter() - start

random.seed(0)

for n in [1000, 10000, 100000, 1000000]:
    data = list(range(n))
    lst, st, dct = data, set(data), dict.fromkeys(data)
    queries = [random.randrange(-n, n) for _ in range(2000)]

    t_list = bench_in(lst, queries)
    t_set = bench_in(st, queries)
    t_dict = bench_in(dct, queries)
    print(f"n={n:>8}  list={t_list:.5f}s  set={t_set:.6f}s  dict={t_dict:.6f}s  list/set={t_list/t_set:.0f}x")
```

```text
n=    1000  list=0.00504s  set=0.000047s  dict=0.000055s  list/set=108x
n=   10000  list=0.05062s  set=0.000065s  dict=0.000081s  list/set=779x
n=  100000  list=0.51885s  set=0.000138s  dict=0.000196s  list/set=3752x
n= 1000000  list=5.32405s  set=0.000200s  dict=0.000273s  list/set=26580x
```

`list` 는 $n$ 이 커질수록 검색 2000번의 시간이 **선형으로** 늘어난다 (원소당 탐색 비용이 그대로 $O(n)$ 이니까). `set` 과 `dict` 는 $n$ 이 1000배(1000 → 1,000,000) 늘어도 검색 시간이 거의 그대로다 — $O(1)$ 이 실제로 $O(1)$ 로 나타나는 그림이다. $n=1{,}000{,}000$ 에서는 **26580배** 차이가 났다.

### 실전 사례: 두 수의 합

이 차이가 실제 문제에서 어떻게 작동하는지 보자. 배열에서 합이 `target` 인 두 수의 인덱스를 찾는, 코테의 "Hello World" 같은 문제다.

```python title="brute vs hash — 정답 검증 포함"
def two_sum_brute(nums, target):
    # ❌ O(n^2) — 모든 쌍을 확인한다
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                return i, j
    return None


def two_sum_hash(nums, target):
    # ✅ O(n) — "짝이 이미 나왔는가"를 dict로 O(1) 확인
    seen = {}
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:
            return seen[need], i
        seen[x] = i
    return None


# 두 구현이 같은 답을 내는지 먼저 확인한다
assert two_sum_brute([2, 7, 11, 15], 9) == two_sum_hash([2, 7, 11, 15], 9) == (0, 1)
assert two_sum_brute([3, 2, 4], 6) == two_sum_hash([3, 2, 4], 6) == (1, 2)
```

정답 검증부터 하는 이유는 최적화 코드일수록 실수하기 쉽기 때문이다. `two_sum_hash` 는 **뒤 원소를 만나기 전에 앞 원소를 `seen` 에 넣는 순서**가 핵심이다. 자기 자신을 짝으로 잡는 사고를 막는다.

이제 정답이 없는(끝까지 뒤져야 하는) 최악의 경우로 실측한다.

```text
n=  1000  brute(O(n^2))=0.01063s  hash(O(n))=0.000079s  ratio=134x
n=  2000  brute(O(n^2))=0.04125s  hash(O(n))=0.000156s  ratio=265x
n=  4000  brute(O(n^2))=0.16412s  hash(O(n))=0.000348s  ratio=471x
n=  8000  brute(O(n^2))=0.68536s  hash(O(n))=0.000752s  ratio=911x
```

$n$ 이 두 배가 될 때마다 브루트포스는 4배, 해시 버전은 2배로 늘어난다. 정확히 $O(n^2)$ 대 $O(n)$ 의 모양이다. 문제의 제약 조건이 $n \le 100{,}000$ 이라면 브루트포스는 확정 시간 초과, 해시 버전은 여유 있게 통과한다. 이 판단을 제약 조건만 보고 즉시 내리는 훈련은 [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 한다.

::: warn set/dict가 항상 빠른 건 아니다
$O(1)$ 은 **평균**이다. 원소가 몇 개 안 되면(예: 10개 미만) 해시 계산 자체의 상수 비용이 리스트 순차 탐색보다 오히려 클 수 있다. 그리고 **해시 가능한(hashable) 값만** 넣을 수 있다 — `list`, `dict` 처럼 가변 객체는 `set`/`dict`의 키가 될 수 없다.

```pyrepl
>>> s = {[1, 2]}
Traceback (most recent call last):
  ...
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
```

리스트를 키로 쓰고 싶으면 `tuple` 로 바꿔라. [1.7 set과 frozenset](#/sets)에서 해시 가능성의 조건을 정리한다.
:::

## collections 모듈: 코테에서 바로 쓰는 도구

표준 라이브러리 `collections` 는 `dict`/`list`를 조금씩 변형해 코테에서 반복적으로 나오는 패턴을 짧게 만들어 준다.

### Counter — 빈도수 세기

"뭐가 몇 번 나왔는가"는 문제 절반에 등장한다.

```pyrepl
>>> from collections import Counter
>>> words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
>>> c = Counter(words)
>>> c
Counter({'apple': 3, 'banana': 2, 'cherry': 1})
>>> c.most_common(2)
[('apple', 3), ('banana', 2)]
```

`Counter` 는 `dict` 의 서브클래스다. 그래서 `c["없는키"]` 가 `KeyError` 대신 **0을 반환**한다 — 카운팅에 딱 맞는 기본값이다.

```pyrepl
>>> c["durian"]
0
```

`most_common(k)` 는 내부적으로 `heapq.nlargest` 를 쓴다. 상위 $k$ 개만 필요하면 전체를 정렬(`O(n \log n)`)하는 것보다 `most_common(k)` (`O(n \log k)`)가 낫다.

### defaultdict — "키가 없으면 만든다"를 없앤다

그래프의 인접 리스트, 그룹핑에서 매번 나오는 방어 코드를 지운다.

```python
# ❌ 매번 확인해야 한다
graph = {}
edges = [("a", "b"), ("a", "c"), ("b", "c")]
for u, v in edges:
    if u not in graph:
        graph[u] = []
    graph[u].append(v)

# ✅ defaultdict가 없는 키를 자동으로 만든다
from collections import defaultdict

graph = defaultdict(list)
for u, v in edges:
    graph[u].append(v)
```

```pyrepl
>>> dd = defaultdict(list)
>>> for k, v in [("a", 1), ("b", 2), ("a", 3)]:
...     dd[k].append(v)
>>> dict(dd)
{'a': [1, 3], 'b': [2]}
```

`defaultdict(list)`, `defaultdict(int)`, `defaultdict(set)` 세 가지가 코테의 90%를 커버한다. `defaultdict(int)` 는 `Counter` 와 겹치지만, 값에 리스트나 집합을 넣어 **그룹핑**할 때는 `Counter` 로는 못 하고 `defaultdict` 가 필요하다.

::: warn defaultdict는 조회만 해도 키를 만든다
```pyrepl
>>> dd = defaultdict(list)
>>> "x" in dd
False
>>> dd["x"]          # 조회했을 뿐인데
[]
>>> "x" in dd         # 키가 생겨 버렸다
True
```
`dd[k]` 로 존재 여부를 확인하지 마라. 없는 키를 조용히 만든다. 존재 확인은 `"x" in dd` 로, 값 없이 읽고 싶으면 `dd.get("x")` 로 한다.
:::

### deque — 양 끝 큐, 그리고 고정 크기 윈도우

이미 위에서 봤다. 추가로 `maxlen` 이 코테에서 유용하다.

```pyrepl
>>> from collections import deque
>>> recent = deque(maxlen=3)
>>> for i in range(5):
...     recent.append(i)
>>> recent
deque([2, 3, 4], maxlen=3)
```

`maxlen` 을 넘어서면 **반대쪽 끝이 자동으로 밀려난다.** "최근 $k$개만 유지" 하는 슬라이딩 윈도우를 손으로 구현할 필요가 없다. [7.3 배열, 투 포인터, 슬라이딩 윈도우](#/two-pointers)에서 이 패턴을 확장한다.

### OrderedDict — 3.7 이후엔 대부분 필요 없다

::: hist 왜 아직도 OrderedDict가 있는가
파이썬 3.7부터 일반 `dict` 도 **삽입 순서를 보장**한다. 그래서 "순서가 유지되는 dict"가 필요해서 `OrderedDict` 를 쓸 이유는 대부분 사라졌다.

`OrderedDict` 가 여전히 유리한 지점은 딱 하나, **순서 자체를 적극적으로 조작**할 때다. `move_to_end(key, last=True/False)` 로 특정 키를 맨 끝이나 맨 앞으로 옮길 수 있다. 일반 `dict` 에는 이 메서드가 없다.
:::

```pyrepl
>>> from collections import OrderedDict
>>> od = OrderedDict()
>>> od["x"], od["y"], od["z"] = 1, 2, 3
>>> od.move_to_end("x")
>>> od
OrderedDict({'y': 2, 'z': 3, 'x': 1})
>>> od.move_to_end("z", last=False)
>>> od
OrderedDict({'z': 3, 'y': 2, 'x': 1})
```

::: cote LRU 캐시를 직접 구현해야 할 때
"최근에 안 쓴 것부터 버려라"는 LRU(Least Recently Used) 문제가 `OrderedDict` 의 정석 활용처다. 접근할 때마다 `move_to_end` 로 맨 뒤로 보내고, 용량을 넘으면 `popitem(last=False)` 로 맨 앞(가장 오래된 것)을 버린다. $O(1)$ 에 끝난다 — `functools.lru_cache` 가 내부에서 하는 일과 같은 아이디어다 ([3.1 functools](#/functools)).
:::

## 메모리도 비용이다

시간만 재고 끝내면 절반이다. 컨테이너 자체가 차지하는 메모리도 실제 비용이다.

```pyrepl
>>> import sys
>>> from collections import deque
>>> lst = list(range(1000))
>>> dq = deque(range(1000))
>>> sys.getsizeof(lst)
8056
>>> sys.getsizeof(dq)
8680
```

원소 1000개 기준으로 `list` 가 `deque` 보다 오히려 살짝 작다. `deque` 는 블록 단위로 관리하느라 각 블록에 여유 공간과 이전/다음 블록을 가리키는 포인터가 추가로 붙는다. **`deque` 가 이기는 건 시간이지, 메모리가 아니다.** 양 끝을 자주 쓸 때만 `deque` 를 골라라. 순수하게 저장만 하고 인덱싱 위주라면 `list` 가 더 가볍고 빠르다.

메모리 문제가 실제로 코테 등수를 가르는 지점은 [5.2 메모리 모델](#/memory)에서 더 깊이 다룬다. 시간 최적화의 나머지 관용구는 [8.3 시간 초과를 피하는 관용구](#/tle)로 이어진다.

이 절에서 본 표는 암기용이 아니다. 문제를 읽으면서 "이 연산을 몇 번 반복하는가"와 "그 연산의 자료구조별 비용이 얼마인가"를 곱해 보는 습관이 실전 감각이다. 그 감각을 제출 전 체크리스트로 다듬는 법은 [8.1 코딩테스트의 구조와 전략](#/cote-strategy)에서 잇는다.

## 요약

- `list` 는 뒤쪽(끝)에서 넣고 빼는 것만 $O(1)$ 이다. 앞에서 `pop(0)`/`insert(0, x)` 하면 $O(n)$ — 큐로 쓰지 마라.
- `deque` 는 양 끝 모두 $O(1)$ 이지만 중간 인덱싱은 $O(n)$ 이다. BFS 큐·슬라이딩 윈도우 전용이다.
- `x in list` 는 $O(n)$, `x in set`/`x in dict` 는 평균 $O(1)$. 이 한 줄이 시간 초과 여부를 가장 자주 가른다.
- `heapq` 는 `list` 위의 이진 힙이다. push/pop이 $O(\log n)$, `heapify` 는 $O(n)$.
- `Counter` 는 빈도수, `defaultdict` 는 그룹핑, `deque(maxlen=k)` 는 고정 크기 윈도우, `OrderedDict.move_to_end` 는 LRU에 쓴다.
- $O(1)$/$O(\log n)$ 이라는 말에 속지 마라. 실제로 걸리는 시간은 입력 크기를 키워 가며 직접 재서 확인하는 습관을 들여라.

::: quiz 연습문제
1. 다음 코드는 왜 큰 입력에서 시간 초과가 나는가? `deque` 로 고쳐라.

   ```python
   def process_queue(items):
       queue = list(items)
       result = []
       while queue:
           result.append(queue.pop(0))
       return result
   ```

2. `set` 대신 `list` 로 방문 여부를 확인하는 BFS 코드가 있다고 하자. 노드 수가 $10^5$ 개일 때 왜 시간 초과가 나는지, `in` 연산의 복잡도로 설명하라.

3. 다음 두 코드 중 어느 쪽이 상위 3개 빈도를 구하는 데 더 유리한가? 원소 수 $n$ 이 매우 크고 $k=3$ 으로 고정일 때를 기준으로 답하라.

   ```python
   # A
   sorted(Counter(data).items(), key=lambda kv: -kv[1])[:3]

   # B
   Counter(data).most_common(3)
   ```

4. `defaultdict(list)` 로 그래프의 인접 리스트를 만든 뒤, 존재하지 않는 노드를 `in` 으로 확인하는 코드를 짜 보고, 그 확인이 부작용으로 빈 리스트 키를 만들어 내는지 직접 실행해서 확인하라.

5. `list`, `deque`, `set`, `dict` 각각에 원소 100,000개를 넣고 `sys.getsizeof` 로 크기를 재 보라. 예상과 얼마나 다른가?
:::

**다음 절**: [7.3 배열, 투 포인터, 슬라이딩 윈도우](#/two-pointers) — 자료구조 선택을 끝냈으니, 이제 배열을 한 번만 훑고도 답을 내는 패턴으로 간다.
