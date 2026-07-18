# 7.6 해시

::: lead
[7.1 복잡도](#/complexity)에서 본 것처럼 알고리즘 문제의 절반은 "어떻게 $O(n^2)$ 를 $O(n)$ 으로 줄이는가"로 귀결된다. 그리고 그 절반의 절반은 답이 해시맵이다. 이 절은 [1.6 dict](#/dict)와 [1.7 set](#/sets)에서 배운 내부 구조를 실전 패턴으로 바꾼다. 두 수의 합, 아나그램 그룹, 빈도수 세기, 그래프 인접 리스트 — 코딩테스트에서 가장 자주 나오는 네 가지 해시맵 패턴을 브루트포스와 직접 대조하며 익힌다. 그리고 마지막에는 해시맵의 가장 흔한 함정, "이 키가 왜 해시 가능하지 않은가"를 파헤친다.
:::

## 왜 브루트포스는 시간 초과가 나는가

문제를 하나 보자. 정수 배열에서 합이 `target` 이 되는 두 수의 인덱스를 찾아라. 이른바 "두 수의 합"이다.

가장 먼저 떠오르는 풀이는 이중 반복문이다.

```python title="two_sum_brute.py"
def two_sum_brute(nums, target):
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                return (i, j)
    return None
```

모든 쌍을 검사하니 정답을 반드시 찾는다. 문제는 속도다. 쌍의 개수는 $\binom{n}{2} \approx n^2/2$ 개다. 실제로 입력 크기를 키우면서 재 보자.

```python title="bench_two_sum.py"
import timeit, random

def two_sum_brute(nums, target):
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                return (i, j)
    return None

def two_sum_hash(nums, target):
    seen = {}                      # 값 -> 인덱스
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:
            return (seen[need], i)
        seen[x] = i
    return None

random.seed(0)
target = 10**9                     # 일부러 매치가 안 나는 값 → 최악의 경우 측정
for n in (1000, 2000, 4000, 8000):
    nums = random.sample(range(n * 10), n)
    t_brute = timeit.timeit(lambda: two_sum_brute(nums, target), number=3) / 3
    t_hash = timeit.timeit(lambda: two_sum_hash(nums, target), number=50) / 50
    print(f"n={n:6d}  brute={t_brute*1000:8.2f} ms  hash={t_hash*1000:7.4f} ms  ratio={t_brute/t_hash:7.1f}")
```

```text nolines
n=  1000  brute=   10.45 ms  hash= 0.0790 ms  ratio=  132.3
n=  2000  brute=   46.70 ms  hash= 0.1257 ms  ratio=  371.5
n=  4000  brute=  169.70 ms  hash= 0.3115 ms  ratio=  544.9
n=  8000  brute=  712.09 ms  hash= 0.7181 ms  ratio=  991.6
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 곡선의 모양은 어디서나 같다.)

$n$ 이 두 배가 될 때마다 `brute` 는 대략 **네 배**로 늘어난다($O(n^2)$ 의 정의 그대로다). `hash` 는 대략 **두 배**로 늘어난다($O(n)$). $n=1000$ 에서 132배였던 격차가 $n=8000$ 에서 991배가 됐다. 코딩테스트의 제약 조건이 흔히 $n \le 10^5$ 또는 $10^6$ 인 이유가 여기 있다 — $n^2$ 짜리 풀이는 그 크기에서 초 단위가 아니라 **시간 단위**가 걸린다.

::: cote 왜 하필 이 문제가 코테의 "관문"인가
"두 수의 합"이 유명한 이유는 **가장 단순한 형태로 브루트포스의 함정을 보여주기** 때문이다. 백준·프로그래머스의 많은 문제가 겉모습만 다를 뿐 본질은 이거다. *"짝을 지어야 하는데, 이중 반복문을 쓰면 시간 초과, 한 번의 반복 + 해시맵 조회면 통과."* 문제를 읽자마자 "정렬된 배열에서 짝을 찾는다" → 이중 반복문이 보이면, 반사적으로 "해시맵으로 하나를 줄일 수 있는가"를 물어라.
:::

## 해시맵이 반복문을 지우는 원리

`two_sum_hash` 가 하는 일은 간단하다. 배열을 **한 번만** 훑으면서, 지금까지 본 값을 딕셔너리에 쌓아 둔다. 각 원소 `x` 에서 필요한 짝은 `target - x` 인데, 이 값이 **이미 쌓아 둔 딕셔너리에 있는지**를 확인한다.

```text nolines
nums = [2, 7, 11, 15],  target = 9

i=0  x=2   need=7   seen={}          -> 7 not in seen  -> seen={2:0}
i=1  x=7   need=2   seen={2:0}       -> 2 in seen!     -> return (0, 1)
```

핵심은 "짝이 있는지 찾는다"를 **뒤에서부터 다시 훑는 대신, 이미 지나온 것들의 사전에서 조회한다**로 바꾼 것이다. `x in dict` 는 [1.6 dict](#/dict)에서 봤듯 평균 $O(1)$ 이다. 그래서 전체가 $O(n)$ 이 된다. **이중 반복문의 안쪽 루프를 통째로 딕셔너리 조회 한 번으로 대체했다** — 이게 이 절에서 반복해서 나올 패턴의 원형이다.

::: cote 변형 문제들
- **정확히 하나의 쌍만 존재**: 위 코드 그대로.
- **모든 쌍을 다 찾아야 한다**: `seen` 을 `dict[값, 인덱스 리스트]` 로 바꾸거나, 값 하나당 등장 횟수를 센 뒤 조합 개수를 계산한다.
- **배열이 정렬돼 있다**: 이때는 해시맵보다 **투 포인터**가 메모리도 적게 쓰고 더 빠르다. [7.3 투 포인터](#/two-pointers) 참고. *"정렬 여부"* 는 해시맵과 투 포인터 중 뭘 쓸지 가르는 첫 질문이다.
- **`target` 이 세 수의 합(3Sum)**: 하나를 고정하고 나머지 둘에 대해 두 수의 합을 반복 — $O(n^2)$ 이 최선이다. [7.21 DP 심화](#/dp-advanced) 이전에 자주 등장하는 다음 단계다.
:::

## 아나그램 그룹 — 키를 어떻게 설계하는가

두 번째 패턴은 "같은 부류를 묶어라"다. 예를 들어 문자열 목록에서 서로 철자 구성이 같은 것(아나그램)끼리 묶는다.

브루트포스는 모든 쌍을 비교한다 — $O(n^2 \cdot k)$ ($k$ 는 문자열 길이). 해시맵을 쓰려면 **"같은 그룹이면 반드시 같은 키가 나오는 함수"** 를 설계해야 한다.

```python title="group_anagrams.py"
from collections import defaultdict

def group_anagrams(words: list[str]) -> list[list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for w in words:
        key = "".join(sorted(w))     # 철자를 정렬하면 아나그램끼리 키가 같아진다
        groups[key].append(w)
    return list(groups.values())


words = ["eat", "tea", "tan", "ate", "nat", "bat"]
print(group_anagrams(words))
```

```pyrepl
>>> group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"])
[['eat', 'tea', 'ate'], ['tan', 'nat'], ['bat']]
```

`sorted(w)` 로 정규화한 값을 키로 쓰면, **원래 값이 달라도 같은 그룹이면 같은 키가 나온다.** 이게 "그룹핑을 위한 해시 키 설계"의 본질이다. 문자열 정렬은 $O(k \log k)$ 이므로 전체는 $O(n \cdot k \log k)$ — 원래의 $O(n^2 k)$ 에서 $n$ 자리 하나를 지운 것이다.

::: tip 정규화 키를 만드는 다른 방법
`sorted(w)` 대신 `Counter(w)` 를 `frozenset(Counter(w).items())` 로 감싸도 된다. 문자열이 아주 길 때는 정렬($O(k \log k)$)보다 글자 개수 세기($O(k)$)가 더 빠르다. 다만 `Counter` 객체 자체는 가변이라 키로 못 쓴다 — 아래 "해시 가능성" 절에서 이유가 나온다.
:::

## 빈도수 세기 — `Counter`

"각 원소가 몇 번 나오는가"는 그 자체로 흔한 요구이자, 다른 패턴의 부품이다. `dict.get` 으로 직접 세도 되지만 `collections.Counter` 가 이 작업을 위해 만들어진 타입이다.

```pyrepl
>>> from collections import Counter
>>> c = Counter("mississippi")
>>> c
Counter({'i': 4, 's': 4, 'p': 2, 'm': 1})
>>> c.most_common(3)
[('i', 4), ('s', 4), ('p', 2)]
```

`Counter` 는 `dict` 의 서브클래스다. **딕셔너리가 하는 모든 것(조회, 순회, `in`)을 그대로 하면서, 몇 가지가 더 붙어 있다.**

- `most_common(n)` — 빈도 내림차순 상위 $n$ 개. 힙을 직접 짤 필요가 없다. 내부적으로 $n$ 이 전체보다 작을 때 `heapq.nlargest` 를 쓴다 — [7.8 힙](#/heap)에서 그 원리를 본다.
- **없는 키를 조회해도 `KeyError` 가 안 난다.** `Counter()["없는키"]` 는 `0` 을 반환한다. 그냥 `dict` 였다면 `KeyError` 다.
- 산술 연산자가 통째로 오버로딩돼 있다.

```pyrepl
>>> c1 = Counter(a=3, b=1)
>>> c2 = Counter(a=1, b=2, c=3)
>>> c1 + c2
Counter({'a': 4, 'b': 3, 'c': 3})
>>> c1 - c2
Counter({'a': 2})
>>> c1 & c2
Counter({'a': 1, 'b': 1})
>>> c1 | c2
Counter({'a': 3, 'c': 3, 'b': 2})
```

`+` 는 항목별 합, `-` 는 **음수와 0을 버리는** 뺄셈(수학적 뺄셈이 아니다), `&` 는 항목별 최솟값(교집합), `|` 는 항목별 최댓값(합집합)이다. 단항 `+c` 는 0 이하인 항목을 걸러내는 관용구로 자주 쓰인다.

```pyrepl
>>> c3 = Counter(a=3, b=0, c=-1)
>>> +c3
Counter({'a': 3})
```

::: cote `Counter` 가 정답을 앞당기는 문제들
- **아나그램 판별**(그룹이 아니라 두 문자열이 아나그램인지만): `Counter(s) == Counter(t)`. 정렬($O(k \log k)$)보다 빠르고($O(k)$) 무엇보다 **읽기 쉽다.**
- **다수결 원소(과반수 투표, Boyer-Moore로도 풀리는 문제)**: `Counter(nums).most_common(1)[0][0]`. 다만 이건 $O(n)$ **추가 공간**을 쓴다. 공간 제약이 빡빡하면 [7.19 그리디](#/greedy)의 보이어-무어 다수결 투표 알고리즘이 공간 $O(1)$ 로 이긴다 — 시간이 같다고 공간까지 같은 게 아니다.
- **두 배열이 같은 멀티셋인지**: `Counter(a) == Counter(b)`.
:::

## `defaultdict` 로 그래프 인접 리스트 만들기

그래프 문제([7.13 그래프](#/graph), [7.14 BFS/DFS](#/bfs-dfs))의 첫 단계는 거의 항상 "간선 목록을 인접 리스트로 바꾸는" 일이다. 평범한 `dict` 로 하면 매번 키 존재 여부를 확인해야 한다.

```python title="adjacency_naive.py"
edges = [(1, 2), (1, 3), (2, 3), (3, 4)]

# ❌ 매번 방어 코드가 필요하다
graph = {}
for a, b in edges:
    if a not in graph:
        graph[a] = []
    graph[a].append(b)
    if b not in graph:
        graph[b] = []
    graph[b].append(a)
```

`defaultdict` 는 이 방어 코드를 지운다.

```python title="adjacency_defaultdict.py"
from collections import defaultdict

edges = [(1, 2), (1, 3), (2, 3), (3, 4)]

graph: dict[int, list[int]] = defaultdict(list)
for a, b in edges:
    graph[a].append(b)     # 키가 없으면 list() 를 자동으로 만들고 append
    graph[b].append(a)

print(dict(graph))
```

```pyrepl
>>> dict(graph)
{1: [2, 3], 2: [1, 3], 3: [1, 2, 4], 4: [3]}
```

::: deep `defaultdict` 는 무엇을 저장하는가 — 값이 아니라 함수
`defaultdict(list)` 에서 `list` 는 **호출된 결과가 아니라 팩토리 함수 그 자체**다. 없는 키를 조회할 때마다 `__missing__` 훅이 그 팩토리를 **호출**해서 새 값을 만들고, 그 값을 키에 저장한 뒤 반환한다. 그래서 `defaultdict(list)`, `defaultdict(int)`, `defaultdict(set)` 모두 되지만 `defaultdict([])` 는 안 된다 — `[]` 는 이미 만들어진 리스트지, 호출 가능한 팩토리가 아니다.

```pyrepl
>>> from collections import defaultdict
>>> d = defaultdict(list)
>>> d["없는키"]          # 조회만 했는데
[]
>>> "없는키" in d         # 키가 생겨 있다!
True
```

**이게 함정이 될 수 있다.** 딕셔너리에 키가 있는지만 확인하려던 `if key in d` 대신 `if d[key]:` 를 썼다면, 조회하는 순간 없던 키가 조용히 생겨 버린다. 단순 존재 확인은 `in` 을 쓰고, `defaultdict` 의 자동 생성은 "값을 채워 넣을 것"이 확실할 때만 믿어라.
:::

::: cote `defaultdict(int)` 로 세는 관용구
`Counter` 를 쓰지 않고 직접 빈도를 셀 때 가장 흔한 패턴이다.

```python
from collections import defaultdict

count = defaultdict(int)
for x in nums:
    count[x] += 1     # 없으면 0에서 시작 -> +1
```

`Counter(nums)` 한 줄로 대체 가능하지만, **여러 종류의 값을 동시에 누적**할 때(예: 좌표별로 방문 횟수 하나, 최소 비용 하나를 같이 관리)는 `defaultdict` 가 더 유연하다.
:::

## 해시 가능성 — 튜플은 되고 리스트는 안 되는 이유

여기까지 나온 모든 패턴은 딕셔너리·집합의 키에 의존한다. 그런데 아무 값이나 키로 쓸 수 있는 게 아니다.

```pyrepl
>>> d = {}
>>> d[[1, 2]] = "x"
Traceback (most recent call last):
  ...
TypeError: cannot use 'list' as a dict key (unhashable type: 'list')
>>> d[(1, 2)] = "ok"     # 튜플은 된다
>>> d
{(1, 2): 'ok'}
```

이유는 [1.6 dict](#/dict)에서 본 해시 테이블의 구조 그 자체에 있다. 딕셔너리는 **키를 넣을 때 `hash(key)` 를 계산해서 그 값으로 슬롯을 정한다.** 만약 키가 들어간 뒤에 값이 바뀌면 — 리스트라면 `append` 한 번으로 — **해시값도 바뀌어야 하는데, 이미 계산해서 특정 슬롯에 넣어 버린 뒤다.** 슬롯을 다시 계산할 방법이 없으니 그 항목은 영원히 미아가 된다. 그래서 파이썬은 아예 **가변 타입에는 `__hash__` 를 주지 않는다.**

```pyrepl
>>> hash((1, 2))
-3550055125485641917
>>> hash([1, 2])
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'list'
```

**튜플이라고 무조건 안전한 건 아니다.** 튜플 자체는 불변이지만, **안에 가변 객체가 들어 있으면 그 튜플도 해시 불가능**하다.

```pyrepl
>>> hash((1, [2, 3]))
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'list'
```

`hash()` 가 컨테이너를 만들 때 **내용물의 해시값까지 재귀적으로 합성**하기 때문이다. 원소 중 하나라도 해시 불가능하면 전체가 해시 불가능해진다.

::: warn `__eq__` 를 정의하면 `__hash__` 가 사라진다
사용자 정의 클래스에서 자주 걸리는 함정이다. 기본적으로 모든 객체는 정체성(`id`) 기반 해시를 갖고 있어서 해시 가능하다. 그런데 **`__eq__` 를 직접 정의하면, 파이썬이 `__hash__` 를 자동으로 `None` 으로 지워 버린다.**

```pyrepl
>>> class Point:
...     def __init__(self, x, y):
...         self.x, self.y = x, y
...     def __eq__(self, other):
...         return (self.x, self.y) == (other.x, other.y)
...
>>> hash(Point(1, 2))
Traceback (most recent call last):
  ...
TypeError: unhashable type: 'Point'
```

값이 같으면 같다고 판단하도록 `__eq__` 를 새로 정의했는데, **그 값이 나중에 바뀔 수도 있는 객체**라면 해시 가능하게 두는 게 위험하다는 게 파이썬의 판단이다. 값으로 비교하면서도 딕셔너리 키·집합 원소로 쓰고 싶다면 `__hash__` 를 명시적으로 함께 정의해야 한다(그리고 그 객체가 실제로는 안 바뀐다는 걸 당신이 보장해야 한다). `@dataclass(frozen=True)` 를 쓰면 이 둘을 자동으로 일관되게 만들어 준다 — [2.6 dataclasses](#/dataclasses), 자세한 원리는 [1.14 특수 메서드](#/dunder)에서.
:::

::: cote 실전에서 이 함정에 걸리는 자리
- **2차원 방문 배열 대신 좌표를 집합의 키로 쓸 때**: `visited = set(); visited.add((r, c))` 는 되지만, 좌표를 리스트 `[r, c]` 로 관리하던 코드를 그대로 넣으면 즉시 `TypeError` 다. BFS/DFS에서 좌표를 `visited` 에 넣기 직전에 `tuple(...)` 로 바꾸는 습관을 들여라.
- **부분집합·상태를 키로 쓸 때(비트마스크 DP, 방문 상태 캐시)**: 순서가 안 중요한 상태는 `frozenset`, 순서가 중요하면 `tuple` 을 쓴다. `set` 자체는 가변이라 `set` 을 원소로 갖는 `set` 은 못 만든다.

  ```pyrepl
  >>> visited_states = set()
  >>> visited_states.add(frozenset({1, 2, 3}))   # OK
  >>> visited_states.add({1, 2, 3})              # ❌
  Traceback (most recent call last):
    ...
  TypeError: cannot use 'set' as a set element (unhashable type: 'set')
  ```

- **메모이제이션 캐시의 키**: `@lru_cache` ([3.1 functools](#/functools))로 재귀 함수를 캐싱할 때, 인자에 리스트를 그대로 넘기면 `TypeError` 로 즉시 터진다. 재귀 함수의 인자는 항상 튜플·정수·문자열 같은 불변으로 설계하라.
:::

## 종합: 해시맵 패턴을 고르는 순서

지금까지 본 네 패턴은 겉보기엔 달라도 같은 질문에서 나온다. **"지금 보고 있는 것과 짝이 맞는 무언가가 이미 나왔는가?"** 를 다시 훑지 않고 즉시 답하려면 해시맵에 저장해 둬야 한다.

```text nolines
문제에서 이런 말이 보이면          -> 이 패턴
"두 원소의 합/차/짝"                -> 값 -> 인덱스 dict (two sum)
"같은 부류로 묶어라"                -> 정규화 키 -> defaultdict(list) (그룹핑)
"몇 번 나왔는지/가장 많이 나온 것"   -> Counter
"A에서 B로 연결" (그래프 간선)      -> defaultdict(list) 인접 리스트
"이미 방문/사용했는지"              -> set, 원소는 반드시 해시 가능해야
```

::: cote [8.1 코딩테스트 전략](#/cote-strategy)과 연결
문제를 읽고 "이중 반복문이 보이는데 시간 제약이 촉박하다"는 신호를 느끼는 순간, 가장 먼저 물어야 할 질문이 "이 중 하나의 루프를 해시맵 조회로 바꿀 수 있는가"다. 이 반사 신경이 코딩테스트에서 가장 값싸게 시간을 버는 방법이다. [8.3 시간 초과를 피하는 관용구](#/tle)에서 이 판단을 더 체계적으로 다룬다.
:::

## 요약

- 이중 반복문으로 "짝을 찾는" 문제는 거의 항상 해시맵으로 한 겹을 줄일 수 있다. $O(n^2) \to O(n)$.
- 두 수의 합: 가는 길에 본 값을 딕셔너리에 쌓아 두고, 필요한 짝이 이미 쌓였는지 조회한다.
- 그룹핑은 **"같은 그룹이면 같은 값이 나오는 정규화 함수"** 를 키로 쓰는 문제다.
- `Counter` 는 `dict` 의 서브클래스다. `most_common`, `elements`, `+ - & |` 연산자가 덧붙는다.
- `defaultdict(팩토리)` 는 없는 키를 조회하는 순간 팩토리를 호출해 채운다 — 그래프 인접 리스트를 만들 때 방어 코드가 사라진다. 단, 단순 존재 확인에 쓰면 없던 키가 조용히 생기는 부작용이 있다.
- 해시 가능하려면 **불변이어야 한다.** 리스트·집합은 안 되고, 튜플·`frozenset`은 되지만 안에 가변 원소가 있으면 튜플도 해시 불가능해진다.
- 사용자 정의 클래스는 `__eq__` 를 정의하는 순간 `__hash__` 가 사라진다. 값 기반 비교와 해시 가능성을 같이 원하면 둘 다 명시하거나 `frozen=True` dataclass를 써라.

::: quiz 연습문제
1. 정수 배열과 정수 `k` 가 주어질 때, `nums[i] - nums[j] == k` (`i != j`) 인 쌍이 존재하는지 확인하는 함수를 해시맵으로 $O(n)$ 에 작성하라. 브루트포스 $O(n^2)$ 버전도 같이 짜서 무작위 배열 100개에 대해 결과가 일치하는지 검증하라.
2. 문자열 리스트를 받아 "서로 아나그램인 것끼리" 그룹을 만들되, **이번엔 `sorted` 대신 `Counter` 를 정규화 키로 쓰려고 한다.** `Counter` 객체를 직접 딕셔너리 키로 쓰면 무슨 일이 나는가? 실행해서 확인하고, 해시 가능한 형태로 바꿔 고쳐라.
3. 다음 코드는 왜 의도한 대로 동작하지 않는가? 실행해서 확인하고 원인을 설명하라.

   ```python
   from collections import defaultdict

   log = defaultdict(list)
   if log["오류"]:          # "오류" 키가 있는지 확인하려는 의도
       print("이미 기록됨")
   print("오류" in log)     # 예상과 같은가?
   ```

4. 정수 배열에서 **과반수(절반 초과)를 차지하는 원소**를 `Counter.most_common(1)` 로 구하는 함수와, 보이어-무어 다수결 투표로 구하는 함수를 각각 작성해 같은 결과가 나오는지 확인하라. 두 방법의 공간 복잡도 차이를 설명하라.
5. `visited: set[tuple[int, int]]` 로 좌표를 관리하는 BFS 코드가 있다고 하자. 어떤 개발자가 실수로 좌표를 `[r, c]` (리스트)로 만들어 `visited.add([r, c])` 를 호출했다. 무슨 에러가 나는지 예측하고, 실제로 실행해 확인하라.
:::

**다음 절**: [7.7 스택과 큐](#/stack-queue) — `deque`로 양쪽 끝을 $O(1)$에 다루는 법과 괄호 문제의 단조 스택.
