# 7.25 세그먼트 트리와 펜윅 트리

::: lead
"배열의 구간 합(또는 최솟값)을 구하라. 그런데 중간에 값이 계속 바뀐다." 이 한 문장이 코딩테스트에서 세그먼트 트리를 불러내는 신호다. 누적합은 값이 안 바뀔 때만 강하고, 매번 처음부터 훑는 방식은 갱신이 잦으면 반드시 시간 초과가 난다. 세그먼트 트리는 배열을 이진 트리로 접어서 "갱신도 빠르고 질의도 빠른" 절충점을 만든다. 이 절에서는 그 트리를 직접 구현해 정답을 검증하고, 합만 필요하다면 훨씬 짧은 코드인 펜윅 트리(BIT)로 충분하다는 것까지 실측으로 확인한다. 마지막에는 "구간에 값을 통째로 더한다"는 요구가 왜 또 다른 트릭(레이지 프로퍼게이션)을 부르는지 본다.
:::

## 브루트포스가 막히는 지점

다음 상황을 생각해 보자. 길이 $n$의 배열이 있고, 이런 질의가 총 $q$번 섞여서 들어온다.

- `update(i, v)`: `arr[i]`를 `v`로 바꾼다.
- `query(l, r)`: 구간 `[l, r]`의 합(또는 최솟값)을 구한다.

백준 2042(구간 합 구하기), 10868(최솟값), 11505(구간 곱 구하기)가 정확히 이 모양이다.

가장 직관적인 풀이는 `update`는 배열 한 칸을 그냥 바꾸고, `query`는 `sum(arr[l:r+1])`로 매번 다시 더하는 것이다. `update`는 $O(1)$이지만 `query`가 $O(n)$이다. $n, q$가 각각 $10^5$면 최악의 경우 $10^{10}$번의 덧셈 — 확실한 시간 초과다.

실제로 재 보자. `update`와 `query`를 절반씩 섞어 2,000번 실행한다.

```python title="naive_bench.py — 매번 sum()으로 구간 합을 구하는 버전"
import random, time

def bench_naive(n, n_ops):
    arr = [random.randint(1, 100) for _ in range(n)]
    ops = []
    for _ in range(n_ops):
        if random.random() < 0.5:
            ops.append(("update", random.randrange(n), random.randint(1, 100)))
        else:
            l = random.randrange(n)
            ops.append(("query", l, random.randrange(l, n)))

    start = time.perf_counter()
    for kind, a, b in ops:
        if kind == "update":
            arr[a] = b
        else:
            sum(arr[a:b + 1])
    return time.perf_counter() - start
```

| n | naive (초) |
| --- | --- |
| 1,000 | 0.0010 |
| 5,000 | 0.0045 |
| 10,000 | 0.0084 |
| 50,000 | 0.0462 |

(Python 3.14.5 / Windows 기준 실측, 연산 2,000회 고정.)

`update` 횟수는 그대로인데 `n`이 늘수록 전체 시간이 거의 비례해서 는다. `query`마다 구간 전체를 훑기 때문이다. [7.1 시간·공간 복잡도](#/complexity)에서 본 "$n=10^5$면 $O(n)$짜리 연산을 $10^5$번 반복하지 마라"가 그대로 적용되는 상황이다.

## 왜 누적합만으로는 부족한가

"구간 합이면 누적합 아닌가?"라는 반응이 자연스럽다. 맞다 — 값이 **절대 안 바뀐다면** 누적합 배열을 한 번 만들어 두고 질의마다 뺄셈 두 번이면 끝난다. $O(n)$ 전처리, $O(1)$ 질의. 이보다 좋을 수 없다.

문제는 `update`다. 누적합 배열에서 한 칸을 고치면, 그 뒤 모든 칸의 누적값이 전부 어긋난다. 다시 만들려면 $O(n)$이다. 즉 누적합은 "갱신은 없고 질의만 많다"는 극단에서만 이긴다.

::: cote 정적 배열이면 세그먼트 트리는 과하다
값이 안 바뀌는 문제에 세그먼트 트리를 짜고 있다면 멈춰라. 구간 합이면 누적합, 구간 최솟값/최댓값이면 **스파스 테이블**(sparse table, $O(n \log n)$ 전처리 + $O(1)$ 질의)이 코드도 짧고 더 빠르다. 세그먼트 트리는 **갱신이 실제로 있을 때만** 값어치를 한다. 이 판단은 이 절 끝의 체크리스트에서 다시 정리한다.
:::

`update`도 자주 있고 `query`도 자주 있다면, 두 연산을 모두 $O(\log n)$ 정도로 눌러야 한다. 그게 세그먼트 트리의 존재 이유다.

## 세그먼트 트리의 구조

세그먼트 트리는 배열의 각 구간을 **이진 트리의 노드**로 나타낸다. 루트는 전체 구간 `[0, n-1]`을 담당하고, 왼쪽/오른쪽 자식은 그 구간을 반씩 나눠 담당한다. 잎(leaf)까지 내려가면 원소 하나짜리 구간이 된다.

```text nolines
arr = [2, 4, 5, 7, 8, 9]  (인덱스 0~5)

                [0,5]=35
               /         \
         [0,2]=11        [3,5]=24
         /     \          /      \
     [0,1]=6  [2,2]=5  [3,4]=15  [5,5]=9
      /   \
   [0,0]=2 [1,1]=4
```

각 노드는 자기 구간의 "합쳐진 값"(여기서는 합)을 들고 있다. 노드 개수는 대략 $2n$개지만, 트리가 완전히 균형 잡히지 않을 수 있어 배열로 표현할 때는 여유 있게 **`4n`** 칸을 잡는 것이 관례다. 인덱스 `node`의 자식은 `2*node`, `2*node+1`이다 — 힙(heap)에서 쓰던 것과 같은 트릭이다.

`query(l, r)`은 루트에서 시작해서, 현재 노드의 구간이 **질의 구간에 완전히 포함되면** 그 노드 값을 그대로 쓰고, **전혀 안 겹치면** 무시하고, **일부만 겹치면** 양쪽 자식으로 내려간다. 겹치는 노드 수가 트리 높이($O(\log n)$)에 비례해서 제한되므로 전체가 $O(\log n)$이다.

## 구현: 구간 합 세그먼트 트리

```python title="segtree.py — 구간 합, 재귀 구현"
class SegTreeSum:
    def __init__(self, arr):
        self.n = len(arr)
        self.tree = [0] * (4 * self.n)
        self._build(arr, 1, 0, self.n - 1)

    def _build(self, arr, node, l, r):
        if l == r:
            self.tree[node] = arr[l]
            return
        mid = (l + r) // 2
        self._build(arr, node * 2, l, mid)
        self._build(arr, node * 2 + 1, mid + 1, r)
        self.tree[node] = self.tree[node * 2] + self.tree[node * 2 + 1]

    def update(self, idx, value):
        self._update(1, 0, self.n - 1, idx, value)

    def _update(self, node, l, r, idx, value):
        if l == r:
            self.tree[node] = value
            return
        mid = (l + r) // 2
        if idx <= mid:
            self._update(node * 2, l, mid, idx, value)
        else:
            self._update(node * 2 + 1, mid + 1, r, idx, value)
        self.tree[node] = self.tree[node * 2] + self.tree[node * 2 + 1]

    def query(self, ql, qr):
        return self._query(1, 0, self.n - 1, ql, qr)

    def _query(self, node, l, r, ql, qr):
        if qr < l or r < ql:          # 전혀 안 겹침
            return 0
        if ql <= l and r <= qr:       # 완전히 포함됨
            return self.tree[node]
        mid = (l + r) // 2            # 일부만 겹침 -> 양쪽 다 본다
        return self._query(node * 2, l, mid, ql, qr) + \
               self._query(node * 2 + 1, mid + 1, r, ql, qr)
```

`_build`, `_update`, `_query` 셋 다 트리 높이만큼만 재귀하므로 각각 $O(\log n)$이다(`_build`만 전체 $O(n)$).

### 정답 검증: 브루트포스와 대조

손으로 훑어서는 확신할 수 없다. **매번 `sum(arr[l:r+1])`을 다시 계산하는 정답이 뻔한 코드**와 무작위로 대조한다.

```python title="segtree_verify.py"
import random

def verify_sum(trials=20):
    random.seed(1)
    for t in range(trials):
        n = random.randint(1, 50)
        arr = [random.randint(-50, 50) for _ in range(n)]
        st = SegTreeSum(arr)
        ref = arr[:]                      # 브루트포스용 원본
        for _ in range(100):
            if random.random() < 0.5:
                idx = random.randrange(n)
                v = random.randint(-50, 50)
                st.update(idx, v)
                ref[idx] = v
            else:
                l = random.randrange(n)
                r = random.randrange(l, n)
                assert st.query(l, r) == sum(ref[l:r + 1])
    print("SegTreeSum: all", trials, "trials OK")
```

실행 결과:

```text nolines
SegTreeSum: all 20 trials OK
```

20번의 시행, 시행마다 최대 100번의 무작위 `update`/`query`를 섞었는데 전부 일치했다. 이 패턴 — 느리지만 명백히 맞는 코드와 대조 — 은 [7.12 유니온 파인드](#/union-find)에서도 쓴 검증법이고, 이 책의 알고리즘 절 전반에서 반복된다.

## 다른 연산으로 확장: 최솟값 세그먼트 트리

세그먼트 트리의 핵심은 "자식 두 값을 하나로 합치는 함수"뿐이다. 그 함수를 `+` 대신 `min`으로 바꾸면 **구간 최솟값** 트리가 된다. 항등원만 바뀐다 — 합에서는 `0`, 최솟값에서는 `+inf`.

```python title="segtree_min.py — 병합 함수만 바꾼 버전"
class SegTreeMin:
    def __init__(self, arr):
        self.n = len(arr)
        self.tree = [float("inf")] * (4 * self.n)
        self._build(arr, 1, 0, self.n - 1)

    def _build(self, arr, node, l, r):
        if l == r:
            self.tree[node] = arr[l]
            return
        mid = (l + r) // 2
        self._build(arr, node * 2, l, mid)
        self._build(arr, node * 2 + 1, mid + 1, r)
        self.tree[node] = min(self.tree[node * 2], self.tree[node * 2 + 1])

    def update(self, idx, value):
        self._update(1, 0, self.n - 1, idx, value)

    def _update(self, node, l, r, idx, value):
        if l == r:
            self.tree[node] = value
            return
        mid = (l + r) // 2
        if idx <= mid:
            self._update(node * 2, l, mid, idx, value)
        else:
            self._update(node * 2 + 1, mid + 1, r, idx, value)
        self.tree[node] = min(self.tree[node * 2], self.tree[node * 2 + 1])

    def query(self, ql, qr):
        return self._query(1, 0, self.n - 1, ql, qr)

    def _query(self, node, l, r, ql, qr):
        if qr < l or r < ql:
            return float("inf")
        if ql <= l and r <= qr:
            return self.tree[node]
        mid = (l + r) // 2
        return min(self._query(node * 2, l, mid, ql, qr),
                   self._query(node * 2 + 1, mid + 1, r, ql, qr))
```

같은 방식으로 무작위 20회 검증하면(`min(ref[l:r+1])`과 대조) **전부 일치**한다. 최댓값, GCD, XOR, 곱셈(모듈러) 모두 "결합법칙이 성립하는 이항 연산"이기만 하면 똑같은 틀에 넣을 수 있다.

::: note 결합법칙이 핵심이다
세그먼트 트리에 올릴 수 있는 연산의 조건은 **결합법칙**(associativity)이 성립하는 것뿐이다. 교환법칙까지는 필요 없다(예: 행렬 곱). 반대로 뺄셈이나 나눗셈처럼 결합법칙이 안 되는 연산은 이 틀에 그대로 못 올린다.
:::

## 펜윅 트리(BIT) — 더 간단하게 구간 합 구하기

구간 합·구간 XOR처럼 **역연산이 존재하는 연산**(더한 것을 뺄셈으로 되돌릴 수 있는 연산)이라면, 세그먼트 트리보다 훨씬 짧은 자료구조로 같은 일을 할 수 있다. 그게 **펜윅 트리**(Fenwick tree), 다른 이름으로 **BIT**(Binary Indexed Tree)다.

아이디어는 "각 인덱스가 몇 개의 원소를 대표하는가"를 **인덱스의 최하위 비트**(lowest set bit)로 정하는 것이다. 1-based 인덱스 `i`에서 `i & (-i)`가 그 최하위 비트 값이다.

```pyrepl
>>> for i in range(1, 9):
...     print(i, bin(i), i & (-i))
1 0b1 1
2 0b10 2
3 0b11 1
4 0b100 4
5 0b101 1
6 0b110 2
7 0b111 1
8 0b1000 8
```

`tree[i]`는 `arr[i - (i & -i) + 1 : i]`(1-based, `i`를 포함) 구간의 합을 저장한다. 갱신은 `i`에 `i & -i`를 더하며 위로, 접두사 합 질의는 `i`에서 `i & -i`를 빼며 아래로 내려간다. 두 연산 모두 이진수 자릿수만큼, 즉 $O(\log n)$번만 움직인다.

```python title="fenwick.py — 점 갱신 + 구간 합"
class Fenwick:
    def __init__(self, n):
        self.n = n
        self.tree = [0] * (n + 1)     # 1-based

    def add(self, idx, delta):        # idx: 0-based, 값에 delta를 더한다
        i = idx + 1
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)

    def prefix_sum(self, idx):        # [0, idx] 합, 0-based
        i = idx + 1
        s = 0
        while i > 0:
            s += self.tree[i]
            i -= i & (-i)
        return s

    def range_sum(self, l, r):        # [l, r] 합, 0-based
        if l == 0:
            return self.prefix_sum(r)
        return self.prefix_sum(r) - self.prefix_sum(l - 1)
```

세그먼트 트리와 다른 점 하나. `update(idx, value)`처럼 "값을 대입"하는 인터페이스가 없다. `add`는 **델타(변화량)를 더하는** 인터페이스라서, 값을 통째로 바꾸려면 `add(idx, 새값 - 현재값)`으로 변환해야 한다.

### 정답 검증

세그먼트 트리와 똑같은 방식으로, 이번엔 `add`로 값을 바꿀 때마다 델타를 계산해서 넘긴다.

```python title="fenwick_verify.py"
def verify_fenwick(trials=20):
    random.seed(3)
    for t in range(trials):
        n = random.randint(1, 50)
        arr = [random.randint(-50, 50) for _ in range(n)]
        fw = Fenwick(n)
        for i, v in enumerate(arr):
            fw.add(i, v)
        ref = arr[:]
        for _ in range(100):
            if random.random() < 0.5:
                idx = random.randrange(n)
                v = random.randint(-50, 50)
                fw.add(idx, v - ref[idx])     # 대입 -> 델타로 변환
                ref[idx] = v
            else:
                l = random.randrange(n)
                r = random.randrange(l, n)
                assert fw.range_sum(l, r) == sum(ref[l:r + 1])
    print("Fenwick: all", trials, "trials OK")
```

```text nolines
Fenwick: all 20 trials OK
```

::: warn 최솟값·최댓값에는 이 트릭이 안 통한다
펜윅 트리가 짧은 이유는 "구간 합에서 일부를 빼면 나머지 구간의 합이 나온다"는 **뺄셈으로 되돌릴 수 있는 성질** 덕분이다. 최솟값은 이게 안 된다 — 최솟값 10개 중 하나를 빼도 나머지 최솟값을 $O(1)$에 알 수 없다. 그래서 **구간 최솟값/최댓값은 펜윅 트리로 못 만들고 세그먼트 트리가 필요하다.** 합·곱(0이 없을 때)·XOR처럼 역원이 존재하는 연산만 펜윅 트리 후보다.
:::

## 실측 비교: naive vs 세그먼트 트리 vs 펜윅 트리

`update`/`query`를 절반씩 섞어 3,000번 실행해서 세 구현을 나란히 잰다.

| n | naive (초) | 세그먼트 트리 (초) | 펜윅 트리 (초) |
| --- | --- | --- | --- |
| 1,000 | 0.0024 | 0.0079 | 0.0013 |
| 5,000 | 0.0054 | 0.0069 | 0.0018 |
| 10,000 | 0.0107 | 0.0066 | 0.0016 |
| 50,000 | 0.0519 | 0.0088 | 0.0025 |
| 100,000 | 0.1260 | 0.0090 | 0.0021 |

(Python 3.14.5 / Windows 기준 실측, 연산 3,000회 고정.)

$n=100{,}000$에서 naive는 0.1260초, 세그먼트 트리는 0.0090초(**약 14배**), 펜윅 트리는 0.0021초(**약 60배**)다. 세그먼트 트리와 펜윅 트리를 비교하면 펜윅 트리가 **약 4.3배** 더 빠르다 — 둘 다 $O(\log n)$이지만 펜윅 트리는 재귀도, 자식 노드 계산도 없이 정수 비트 연산만 반복하기 때문에 상수가 훨씬 작다. $n$이 1,000일 때는 오히려 세그먼트 트리(재귀 호출 오버헤드가 상대적으로 크다)가 naive보다 느린 것도 눈에 띈다 — **$n$이 작으면 정교한 자료구조가 오히려 손해**라는 걸 실측이 보여 준다.

## 세그먼트 트리 vs 펜윅 트리 — 언제 무엇을

| | 세그먼트 트리 | 펜윅 트리(BIT) |
| --- | --- | --- |
| 코드 길이 | 길다 (재귀 3개) | 짧다 (반복문 2개) |
| 상수 | 크다 | 작다 (약 4~5배 빠름, 실측) |
| 가능한 연산 | 결합법칙만 되면 뭐든(합, 최솟값, 최댓값, GCD, ...) | 역원이 있는 연산만(합, XOR, 곱 등) |
| 구간 갱신 + 구간 질의 | 레이지 프로퍼게이션으로 확장 | 두 개의 BIT로 확장 가능(트릭, 아래 참고) |
| 암기 난이도 | 상대적으로 어렵다 | 쉽다 |

::: tip 합만 필요하면 펜윅 트리부터 떠올려라
코딩테스트에서 "점 갱신 + 구간 합" 패턴을 보면 **펜윅 트리를 먼저 시도하라.** 코드가 15줄 안팎이고 버그 낼 자리가 적다. 세그먼트 트리는 **최솟값/최댓값처럼 역연산이 없는 경우**, 또는 **구간 갱신 + 구간 질의**처럼 더 복잡한 요구가 있을 때 꺼내는 무거운 도구다. [8.10 실전 템플릿 모음](#/templates)에 두 템플릿이 나란히 정리된다.
:::

## 레이지 프로퍼게이션 — 구간을 통째로 갱신하기

지금까지는 `update`가 **원소 하나**만 바꿨다. 그런데 "구간 `[l, r]`에 있는 모든 원소에 $v$를 더하라"는 요구가 나오면 얘기가 달라진다. 순진하게 구현하면 그 구간의 모든 잎을 하나씩 갱신해야 하고, 구간 길이가 $n$이면 $O(n \log n)$이 든다 — 여러 번 반복되면 다시 시간 초과다.

**레이지 프로퍼게이션**(lazy propagation)은 "지금 당장 필요하지 않은 갱신은 미뤄 둔다"는 아이디어다. 구간 `[l, r]`이 어떤 노드의 구간을 완전히 덮으면, 그 노드 아래로 내려가 잎까지 갱신하는 대신 **그 노드에 "나중에 자식에게 전달할 값"만 적어 두고 멈춘다.** 나중에 그 자식을 실제로 들여다볼 일이 생기면(다른 질의가 그 자식까지 파고들 때) 그때 미뤄 둔 값을 자식에게 밀어 내린다(`push_down`).

```text nolines
구간 [0,5]에 +10을 한다고 하자. 트리 전체가 그 구간에 덮이면:

          [0,5], lazy=10          <- 여기서 멈춘다. 자식은 아직 안 건드림.
         /              \
   [0,2] (아직 반영 안 됨)   [3,5] (아직 반영 안 됨)

나중에 query(0, 2)가 들어오면, 그때 lazy=10을 자식에게 내려보낸 뒤 계속 내려간다.
```

```python title="lazy_segtree.py — 구간에 값 더하기 + 구간 합 질의"
class LazySegTreeRangeAddSum:
    def __init__(self, arr):
        self.n = len(arr)
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self._build(arr, 1, 0, self.n - 1)

    def _build(self, arr, node, l, r):
        if l == r:
            self.tree[node] = arr[l]
            return
        mid = (l + r) // 2
        self._build(arr, node * 2, l, mid)
        self._build(arr, node * 2 + 1, mid + 1, r)
        self.tree[node] = self.tree[node * 2] + self.tree[node * 2 + 1]

    def _push_down(self, node, l, r):
        if self.lazy[node] == 0:
            return
        mid = (l + r) // 2
        for child, cl, cr in ((node * 2, l, mid), (node * 2 + 1, mid + 1, r)):
            self.lazy[child] += self.lazy[node]
            self.tree[child] += self.lazy[node] * (cr - cl + 1)
        self.lazy[node] = 0

    def range_add(self, ql, qr, delta):
        self._range_add(1, 0, self.n - 1, ql, qr, delta)

    def _range_add(self, node, l, r, ql, qr, delta):
        if qr < l or r < ql:
            return
        if ql <= l and r <= qr:
            self.tree[node] += delta * (r - l + 1)
            self.lazy[node] += delta       # 자식에게는 미룬다
            return
        self._push_down(node, l, r)
        mid = (l + r) // 2
        self._range_add(node * 2, l, mid, ql, qr, delta)
        self._range_add(node * 2 + 1, mid + 1, r, ql, qr, delta)
        self.tree[node] = self.tree[node * 2] + self.tree[node * 2 + 1]

    def range_query(self, ql, qr):
        return self._range_query(1, 0, self.n - 1, ql, qr)

    def _range_query(self, node, l, r, ql, qr):
        if qr < l or r < ql:
            return 0
        if ql <= l and r <= qr:
            return self.tree[node]
        self._push_down(node, l, r)
        mid = (l + r) // 2
        return self._range_query(node * 2, l, mid, ql, qr) + \
               self._range_query(node * 2 + 1, mid + 1, r, ql, qr)
```

`tree[node]`는 항상 그 노드가 **자기 자신 기준으로는 최신값**을 들고 있다는 점이 핵심이다(`range_add`가 완전 포함 구간에서 `tree[node]`를 즉시 갱신한다). 다만 자식에게 아직 안 알린 몫이 `lazy[node]`에 쌓여 있을 뿐이다. `push_down`은 그 몫을 자식에게 넘기고 자신은 0으로 비운다.

### 정답 검증

이번엔 브루트포스가 "구간 전체를 for문으로 돌며 실제로 더하는" 코드다.

```python title="lazy_verify.py"
def verify_lazy(trials=20):
    random.seed(4)
    for t in range(trials):
        n = random.randint(1, 50)
        arr = [random.randint(-50, 50) for _ in range(n)]
        st = LazySegTreeRangeAddSum(arr)
        ref = arr[:]
        for _ in range(100):
            l = random.randrange(n)
            r = random.randrange(l, n)
            if random.random() < 0.5:
                delta = random.randint(-50, 50)
                st.range_add(l, r, delta)
                for i in range(l, r + 1):
                    ref[i] += delta
            else:
                assert st.range_query(l, r) == sum(ref[l:r + 1])
    print("LazySegTree: all", trials, "trials OK")
```

```text nolines
LazySegTree(range-add/range-sum): all 20 trials OK
```

### 실측: 레이지 프로퍼게이션이 실제로 이기는 지점

"구간에 통째로 더하기"를 순진하게(for문으로) 처리한 것과 비교한다.

| n | naive 구간 갱신 (초) | 레이지 세그먼트 트리 (초) | 배수 |
| --- | --- | --- | --- |
| 1,000 | 0.0062 | 0.0100 | 0.62x |
| 5,000 | 0.0297 | 0.0148 | 2.01x |
| 10,000 | 0.0571 | 0.0162 | 3.52x |
| 50,000 | 0.3048 | 0.0209 | 14.58x |
| 100,000 | 0.5892 | 0.0224 | 26.30x |

(Python 3.14.5 / Windows 기준 실측, 연산 2,000회 고정.)

$n=1{,}000$에서는 naive가 오히려 더 빠르다(재귀와 레이지 배열 관리의 오버헤드가 이득보다 크다). 하지만 $n$이 커질수록 격차가 급격히 벌어져서 $n=100{,}000$에서는 **26배** 차이가 난다. **레이지 프로퍼게이션의 값어치는 $n$과 구간 갱신 횟수가 둘 다 클 때 나온다** — 이게 바로 코딩테스트의 전형적인 제약 조건이다.

::: perf push_down을 빼먹으면 답이 조용히 틀린다
레이지 프로퍼게이션에서 가장 흔한 실수는 **`_range_query`나 자식으로 내려가는 모든 지점에서 `push_down`을 잊는 것**이다. `push_down` 없이 자식으로 내려가면, 미뤄 둔 갱신이 반영되지 않은 오래된 값을 그대로 읽거나 덮어써서 **예외 없이 조용히 틀린 답**이 나온다. 이 절의 `verify_lazy`처럼 브루트포스와 대조하는 습관이 없으면 이 버그는 알아채기 어렵다 — 로직상 크래시가 안 나기 때문이다.
:::

## 실전 판단 기준: 정말 세그먼트 트리가 필요한가

세그먼트 트리는 코드가 길고 버그 낼 자리가 많다. 시험장에서는 **가장 간단한 도구부터** 확인하는 게 맞다.

::: cote 도구 선택 순서
1. **값이 아예 안 바뀐다** → 누적합(합), 스파스 테이블(최솟값/최댓값). 세그먼트 트리 불필요.
2. **점 갱신 + 구간 합/XOR** → 펜윅 트리. 코드가 짧고 빠르다.
3. **점 갱신 + 구간 최솟값/최댓값/GCD** → 세그먼트 트리(펜윅 트리는 못 쓴다).
4. **구간 갱신 + 점 질의**(구간 전체에 더하고 한 지점 값만 물어봄) → 펜윅 트리에 **차분 배열**을 얹으면 충분하다. 레이지 프로퍼게이션까지 필요 없다.
5. **구간 갱신 + 구간 질의** → 레이지 프로퍼게이션 세그먼트 트리, 또는 (합에 한해) 두 개의 펜윅 트리를 쓰는 트릭.
6. **갱신이 아주 드물고 질의만 압도적으로 많다** → 스파스 테이블이나 sqrt 분할이 세그먼트 트리보다 간단할 때가 있다.

**"구간"이라는 단어가 문제에 보인다고 바로 세그먼트 트리부터 짜지 마라.** 위 순서대로 "이것보다 간단한 방법으로 안 되는가"를 먼저 자문하는 습관이 시간을 아낀다. [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 제약 조건만 보고 이 판단을 빠르게 내리는 훈련을 더 다룬다.
:::

::: note 4번의 "펜윅 트리 + 차분 배열" 감 잡기
구간 `[l, r]`에 $v$를 더하는 걸 **차분 배열**(difference array) `d`로 표현하면 `d[l] += v; d[r+1] -= v` 두 번의 점 갱신으로 끝난다. 어떤 지점 `i`의 실제 값은 `d`의 접두사 합 `d[0] + d[1] + ... + d[i]`다. 즉 "구간 갱신, 점 질의"는 "**점 갱신**, **접두사 합 질의**"로 뒤집을 수 있고, 이건 펜윅 트리가 정확히 잘하는 일이다. 레이지 프로퍼게이션은 여기에 "구간 질의"까지 필요할 때 꺼내는 다음 단계다.
:::

## 요약

- 값이 계속 바뀌는 배열에서 구간 합/최솟값/최댓값을 반복 질의하면, 매번 다시 훑는 방식은 $O(n)$/질의라 반드시 느려진다 — 실측으로 확인했다.
- 누적합은 갱신이 없을 때만 강하다. 갱신이 있으면 세그먼트 트리나 펜윅 트리가 필요하다.
- **세그먼트 트리**: 결합법칙이 성립하는 어떤 이항 연산이든(합, 최솟값, 최댓값, GCD, ...) $O(\log n)$의 갱신·질의로 처리한다.
- **펜윅 트리(BIT)**: 역원이 있는 연산(합, XOR 등)이면 훨씬 짧은 코드로 같은 일을 한다. 실측으로 세그먼트 트리보다 약 4~5배 빠르다.
- 구간을 통째로 갱신하고 구간을 통째로 질의해야 하면 **레이지 프로퍼게이션**으로 갱신을 미뤄서 $O(n \log n)$을 $O(\log n)$으로 낮춘다.
- 세그먼트 트리는 코드가 길고 버그가 잘 숨는다 — 항상 브루트포스와 대조해서 검증하고, 문제가 더 간단한 도구(누적합, 스파스 테이블, 차분 배열)로 풀리지 않는지 먼저 확인하라.

::: quiz 연습문제
1. 이 절의 `SegTreeSum`을 이용해 백준 2042(구간 합 구하기)를 직접 풀어라. 입력이 1-based인 점에 주의하라.

2. `SegTreeMin`을 참고해서 **구간 최댓값** 세그먼트 트리를 직접 만들고, `max(ref[l:r+1])`과 대조해 20회 무작위 검증을 통과시켜라.

3. 펜윅 트리로 "구간 XOR"을 구하는 자료구조를 만들어라. XOR은 자기 자신의 역원이라는 점(`a ^ a = 0`)을 이용하면 `Fenwick`의 `+`를 `^`로 바꾸는 것만으로 충분하다는 걸 확인하라.

4. 이 절의 마지막 노트에서 설명한 "차분 배열 + 펜윅 트리로 구간 갱신, 점 질의" 방식을 직접 구현하고, `for i in range(l, r+1): arr[i] += v`로 구간을 직접 갱신하는 브루트포스와 대조해 검증하라.

5. **깊이 생각해 볼 문제.** `LazySegTreeRangeAddSum`에서 `_push_down`을 `_range_query` 안에서 빼먹으면(즉, 완전히 포함되지 않는 경우 바로 자식으로 내려가면서 `lazy` 반영을 생략하면) 어떤 입력에서 답이 틀리는지 직접 만들어 보여라. 힌트: `range_add`로 한 번 미뤄 둔 뒤, 그 하위 구간을 파고드는 `range_query`를 바로 연결해야 재현된다.
:::

**다음 절**: [7.26 기하 알고리즘](#/geometry) — CCW 판정 하나로 선분 교차와 볼록 껍질까지 풀어내는 법.
