# 7.21 동적 계획법 심화

::: lead
[7.20 동적 계획법 기초](#/dp-basics)에서 점화식을 세우는 감을 잡았다면, 이 절은 그 감각을 실전 문제 유형에 그대로 적용해 본다. 배낭, LIS, LCS, 구간 DP, 비트마스크 DP, 트리 DP — 이름은 다 다르지만 하나의 질문으로 수렴한다. **"상태를 어떻게 정의할 것인가."** 상태 정의만 옳으면 전이식은 따라온다. 상태 정의가 틀리면 아무리 코드를 잘 짜도 답이 안 나온다. 이 절의 모든 코드는 브루트포스와 대조해 정답을 검증했고, 모든 복잡도 주장은 실제로 실행 시간을 재서 뒷받침한다.
:::

## 상태 정의가 전부다

DP 문제를 풀 때 초심자가 가장 먼저 하는 실수는 점화식부터 떠올리려는 것이다. 순서가 거꾸로다. 먼저 물어야 할 것은 이거다.

> **"부분 문제를 어떤 숫자(또는 튜플)로 나타낼 것인가?"**

상태를 `dp[i]` 로 잡을지 `dp[i][j]` 로 잡을지, `dp[i][j]` 가 "i번째까지 보고 j를 썼을 때"인지 "i번째부터 j번째까지"인지에 따라 전이식 자체가 완전히 달라진다. 이 절에서 다루는 6가지 유형은 사실 **상태를 잡는 방식의 6가지 패턴**이다.

| 유형 | 상태의 의미 | 상태 공간 |
| --- | --- | --- |
| 배낭 | i번째까지 고려, 무게 c 이하일 때 최대 가치 | `dp[i][c]` |
| LIS | i번째로 끝나는 증가 부분수열의 최대 길이 | `dp[i]` |
| LCS | 두 문자열의 접두사 i, j까지의 최장 공통 부분수열 | `dp[i][j]` |
| 구간 DP | 구간 `[i, j]` 를 처리하는 최적값 | `dp[i][j]` |
| 비트마스크 DP | "방문한 원소의 집합" + 현재 위치 | `dp[mask][u]` |
| 트리 DP | 서브트리 루트에서의 두 가지 선택(포함/제외) | `dp[u][0/1]` |

::: cote 상태 개수 = 시간복잡도의 절반
DP의 시간복잡도는 대략 **(상태의 개수) × (전이 하나의 비용)** 이다. 문제를 보고 "상태가 몇 개나 나올 수 있는가"를 먼저 세는 습관을 들이면, 코드를 짜기 전에 이미 시간 제한을 통과할지 가늠할 수 있다. 상태가 $2^{20}$ 개라면 그 자체로 $10^6$ 이니 전이 비용을 O(1)~O(n) 수준으로 눌러야 한다는 계산이 바로 선다. [8.4 문제 유형 분류](#/problem-signals)에서 이 역추론을 더 훈련한다.
:::

## 0/1 배낭 — 상태에 "무게 한도"를 넣는다

물건이 $n$ 개 있고, 각각 무게 $w_i$ 와 가치 $v_i$ 를 가진다. 배낭 용량 $W$ 를 넘기지 않으면서 가치의 합을 최대화하라. 각 물건은 넣거나 안 넣거나 둘 중 하나다(그래서 "0/1").

### 브루트포스가 막히는 지점

물건마다 넣는다/안 넣는다 두 선택이 있으니 전체 경우의 수는 $2^n$ 이다.

```python title="knapsack_brute.py"
def knapsack_brute(weights: list[int], values: list[int], capacity: int) -> int:
    n = len(weights)
    best = 0
    for mask in range(1 << n):        # 모든 부분집합
        w = v = 0
        for i in range(n):
            if mask & (1 << i):
                w += weights[i]
                v += values[i]
        if w <= capacity:
            best = max(best, v)
    return best
```

$n = 22$ 만 돼도 $2^{22} \approx 4.2 \times 10^6$ 개의 부분집합을 매번 안쪽 루프로 훑는다. 실측해 보자.

```text nolines
0/1 배낭 실측: 브루트포스 O(2^n) vs DP O(nW)  (capacity=1000)
     n     brute(s)        dp(s)
    10       0.0004       0.0004
    15       0.0183       0.0006
    20       0.8424       0.0008
    22       3.7306       0.0009
```

(Python 3.14.5 / Windows 기준 실측.) $n$ 이 2 늘 때마다 브루트포스 시간이 거의 4배가 된다 — $2^n$ 의 특징이다. 백준 등에서 $n \le 100$, $W \le 10^5$ 같은 제약이 나오면 $2^{100}$ 은 우주가 끝나도 못 돈다는 뜻이고, 이게 DP가 필요하다는 신호다.

### 상태 정의와 점화식

**상태**: `dp[i][c]` = "물건 0번부터 i-1번까지만 고려했을 때, 무게 한도 c 이하에서 얻을 수 있는 최대 가치".

물건 i를 넣을지 말지 두 경우 중 좋은 쪽을 고른다.

$$dp[i][c] = \max(\underbrace{dp[i-1][c]}_{\text{i번을 안 넣는다}},\ \underbrace{dp[i-1][c-w_i] + v_i}_{\text{i번을 넣는다 (}c \ge w_i\text{일 때만)}})$$

```python title="knapsack_2d.py — 2차원 그대로"
def knapsack_2d(weights: list[int], values: list[int], capacity: int) -> int:
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w, v = weights[i - 1], values[i - 1]
        for c in range(capacity + 1):
            dp[i][c] = dp[i - 1][c]              # 안 넣는다
            if c >= w:
                dp[i][c] = max(dp[i][c], dp[i - 1][c - w] + v)   # 넣는다
    return dp[n][capacity]
```

### 1차원으로 압축하기 — 역순 루프의 이유

`dp[i][c]` 는 `dp[i-1][...]` 에만 의존한다. 즉 한 줄만 있으면 충분하다. 그런데 그냥 1차원 배열로 줄이면 함정이 하나 생긴다.

```python title="knapsack_1d.py — 반드시 역순"
def knapsack_1d(weights: list[int], values: list[int], capacity: int) -> int:
    n = len(weights)
    dp = [0] * (capacity + 1)
    for i in range(n):
        w, v = weights[i], values[i]
        for c in range(capacity, w - 1, -1):      # ← 큰 c에서 작은 c로
            dp[c] = max(dp[c], dp[c - w] + v)
    return dp[capacity]
```

```python title="검증: 3가지 구현이 모두 일치하는가"
import random

random.seed(0)
for _ in range(300):
    n = random.randint(1, 12)
    weights = [random.randint(1, 15) for _ in range(n)]
    values = [random.randint(1, 20) for _ in range(n)]
    capacity = random.randint(1, 30)
    assert knapsack_brute(weights, values, capacity) == \
           knapsack_2d(weights, values, capacity) == \
           knapsack_1d(weights, values, capacity)
print("300회 무작위 대조 통과")
```

```text nolines
300회 무작위 대조 통과
```

::: danger 왜 역순이어야 하는가
`c` 를 **작은 값부터** 갱신하면, `dp[c - w]` 가 **이번 물건을 이미 반영한 값**으로 덮어써진 뒤일 수 있다. 그러면 같은 물건을 여러 번 담는 "무한 배낭(complete knapsack)"이 되어 버린다. **큰 `c` 부터 내려오면** `dp[c - w]` 는 항상 "아직 이번 물건을 반영하지 않은" 이전 줄의 값이라서 0/1 제약이 지켜진다.

역으로, **물건을 여러 번 담아도 되는 문제**(동전 교환처럼 무한 공급)라면 정순 루프를 쓴다. 이 둘을 헷갈리는 것이 배낭 문제에서 가장 흔한 실수다.
:::

::: cote 배낭 계열 변형을 알아두면 문제를 반쯤 풀고 시작한다
- **무한 배낭(complete knapsack)**: 정순 루프. 동전 교환 최소 개수, 사탕 담기처럼 "무제한 공급" 문제.
- **개수 제한 배낭(bounded knapsack)**: 물건마다 최대 개수가 정해짐 → 이진수 분해로 0/1 배낭으로 환원하거나 모노톤 큐로 최적화.
- **차원 추가**: 무게 외에 부피 등 제약이 하나 더 있으면 `dp[c][d]` 로 차원을 늘린다. 상태 개수가 곱으로 늘어나니 시간 제한을 먼저 확인하라.
:::

## LIS — 가장 긴 증가 부분수열

배열에서 (연속하지 않아도 되는) 부분수열 중, 원소가 계속 증가하면서 가장 긴 것의 길이를 구하라. 예: `[10, 9, 2, 5, 3, 7, 101, 18]` 에서 답은 `[2, 5, 7, 18]` 같은 길이 4짜리 수열이다.

### $O(n^2)$ — 상태를 "i로 끝나는 LIS"로 잡는다

**상태**: `dp[i]` = "인덱스 i의 원소로 반드시 끝나는 증가 부분수열 중 최대 길이".

```python title="lis_n2.py"
def lis_n2(arr: list[int]) -> int:
    n = len(arr)
    if n == 0:
        return 0
    dp = [1] * n                      # 자기 자신만으로 길이 1
    for i in range(n):
        for j in range(i):
            if arr[j] < arr[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)
```

앞의 모든 `j < i` 를 훑어 `arr[j] < arr[i]` 인 것 중 `dp[j]` 가 가장 큰 것에 1을 더한다. 이중 루프이므로 $O(n^2)$.

```python title="검증: 브루트포스(모든 부분집합)와 대조"
def lis_brute(arr: list[int]) -> int:
    n = len(arr)
    best = 0
    for mask in range(1 << n):
        seq = [arr[i] for i in range(n) if mask & (1 << i)]
        if all(seq[k] < seq[k + 1] for k in range(len(seq) - 1)):
            best = max(best, len(seq))
    return best

random.seed(0)
for _ in range(200):
    n = random.randint(0, 14)
    arr = [random.randint(0, 10) for _ in range(n)]
    assert lis_brute(arr) == lis_n2(arr)
print("LIS 200회 대조 통과 (n≤14, 브루트 2^n 과 비교)")
```

```text nolines
LIS 200회 대조 통과 (n≤14, 브루트 2^n 과 비교)
```

### $O(n \log n)$ — 상태를 버리고 "길이별 최소 끝값"만 남긴다

$n^2$ 로 충분할 때도 많지만, $n \le 10^5$ 이상이면 뚫린다. 핵심 아이디어를 바꿔야 한다.

> `tails[k]` = "길이 `k+1` 짜리 증가 부분수열들 중, **끝나는 값이 가장 작은 것**의 끝값".

왜 이렇게 잡는가? 길이가 같은 여러 증가 부분수열이 있다면, **끝값이 작을수록 뒤에 더 많은 원소를 이어붙일 가능성이 높다.** 그러니 길이별로 "가장 이어붙이기 좋은" 대표 하나만 남기면 된다.

```python title="lis_nlogn.py"
from bisect import bisect_left

def lis_nlogn(arr: list[int]) -> int:
    tails: list[int] = []
    for x in arr:
        pos = bisect_left(tails, x)     # tails에서 x 이상이 처음 나오는 위치
        if pos == len(tails):
            tails.append(x)             # x가 가장 크다 → 길이가 하나 늘어난다
        else:
            tails[pos] = x              # 같은 길이인데 더 작은 끝값으로 교체
    return len(tails)
```

`tails` 는 **항상 정렬된 상태로 유지된다**(새 값을 넣거나 이분 탐색으로 찾은 위치를 교체할 뿐 순서를 어지럽히지 않는다). 그래서 [7.5 이분 탐색](#/binary-search)의 `bisect_left` 를 그대로 쓸 수 있다. 원소마다 $O(\log n)$ 이므로 전체 $O(n \log n)$.

::: warn `tails` 는 정답 수열이 아니다
`tails` 의 최종 길이는 LIS의 **길이**와 같지만, `tails` 자체가 실제 LIS 원소들은 아니다. 교체가 일어날 때마다 과거 정보가 덮어써지기 때문이다. **실제 수열을 복원해야 한다면** 각 원소를 넣을 때 "이 값 앞에 무엇이 있었는지"를 별도 배열에 기록해 뒤에서부터 역추적해야 한다. 길이만 물으면 이 부분은 필요 없다.
:::

```python title="검증: 세 구현이 모두 일치하는가"
random.seed(0)
for _ in range(200):
    n = random.randint(0, 14)
    arr = [random.randint(0, 10) for _ in range(n)]
    assert lis_brute(arr) == lis_n2(arr) == lis_nlogn(arr)
print("LIS 세 구현 200회 대조 통과")

arr = [10, 9, 2, 5, 3, 7, 101, 18]
print(lis_n2(arr), lis_nlogn(arr))
```

```text nolines
LIS 세 구현 200회 대조 통과
4 4
```

시간 차이를 실측하면 이렇다.

```text nolines
LIS 실측: O(n^2) vs O(n log n)
       n    O(n^2)(s)  O(nlogn)(s)       배수
    1000       0.0238       0.0001   311.1x
    3000       0.1766       0.0002   773.4x
    6000       0.6075       0.0005  1263.6x
   10000       1.7673       0.0008  2223.2x
   20000       6.8576       0.0019  3560.3x
```

(Python 3.14.5 / Windows 기준 실측.) $n$ 이 커질수록 배수가 **계속 커진다** — $n^2$ 대 $n \log n$ 이므로 당연하다. $n = 20000$ 에서 이미 3500배 이상 차이가 난다.

::: cote LIS는 변형이 많다
- **최장 감소 부분수열**: 배열을 뒤집거나 부호를 뒤집어서 그대로 적용.
- **비내림차순(같은 값 허용)**: `bisect_left` 대신 `bisect_right` 로 바꾸면 된다.
- **박스 쌓기, 강 건너기류 문제**: 두 속성(가로·세로)이 있으면 하나를 정렬 기준으로, 나머지를 LIS 대상으로 — **차원을 하나 줄이는 전형적인 트릭**이다. 정렬 기준이 같을 때 동점 처리(오름차순/내림차순)를 반대로 둬야 하는 경우가 많으니 직접 검증해라.
:::

## LCS — 최장 공통 부분수열

두 문자열(또는 시퀀스) `a`, `b` 에서, 순서는 유지하되 연속하지 않아도 되는 공통 부분수열 중 가장 긴 것의 길이를 구한다. `"ABCBDAB"` 와 `"BDCABA"` 사이에는 `"BCBA"` 같은 길이 4짜리 공통 부분수열이 있다.

### 상태 정의

**상태**: `dp[i][j]` = "`a` 의 앞 i글자와 `b` 의 앞 j글자 사이의 LCS 길이".

$$dp[i][j] = \begin{cases} dp[i-1][j-1] + 1 & a_{i-1} = b_{j-1}\\ \max(dp[i-1][j],\ dp[i][j-1]) & a_{i-1} \ne b_{j-1} \end{cases}$$

마지막 글자가 같으면 그 글자를 결과에 포함시키고 양쪽 다 한 칸씩 줄인 상태로 넘어간다. 다르면 둘 중 하나를 포기한 결과 중 나은 쪽을 취한다 — **한쪽을 포기해도 답이 유지된다는 것**이 이 점화식이 성립하는 이유다(어느 한쪽 문자열의 마지막 글자는 최적해에 아예 안 쓰일 수도 있으니까).

```python title="lcs.py"
def lcs_length(a: str, b: str) -> int:
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]
```

$n \times m$ 개의 상태, 전이는 O(1)이므로 $O(nm)$.

```python title="검증: 브루트포스(재귀 완전탐색)와 대조"
from functools import lru_cache

def lcs_brute(a: str, b: str) -> int:
    @lru_cache(maxsize=None)
    def rec(i: int, j: int) -> int:
        if i == len(a) or j == len(b):
            return 0
        if a[i] == b[j]:
            return 1 + rec(i + 1, j + 1)
        return max(rec(i + 1, j), rec(i, j + 1))
    return rec(0, 0)

random.seed(0)
for _ in range(150):
    a = "".join(random.choice("ABC") for _ in range(random.randint(0, 8)))
    b = "".join(random.choice("ABC") for _ in range(random.randint(0, 8)))
    assert lcs_brute(a, b) == lcs_length(a, b)
print("LCS 150회 대조 통과")
print(lcs_length("ABCBDAB", "BDCABA"))
```

```text nolines
LCS 150회 대조 통과
4
```

::: note 실제 수열을 복원하려면
`dp` 표를 오른쪽 아래에서 시작해 역추적한다. `a[i-1] == b[j-1]` 이면 그 글자를 채택하고 `(i-1, j-1)` 로, 아니면 `dp[i-1][j]` 와 `dp[i][j-1]` 중 큰 쪽으로 이동한다. LIS의 길이 복원과 원리가 같다.
:::

::: cote LCS와 헷갈리기 쉬운 것들
- **최장 공통 부분문자열(substring, 연속)**: 이건 다른 문제다. `dp[i][j]` 의 의미를 "**반드시** `a[i-1]`, `b[j-1]` 로 끝나는 공통 부분문자열의 길이"로 바꾸고, 불일치 시 0으로 리셋한다.
- **편집 거리(edit distance)**: LCS와 점화식 구조는 같지만 "삽입·삭제·교체" 세 연산의 비용을 각각 반영한다. LCS는 편집 거리의 특수한 경우(교체 금지, 삽입·삭제만 허용)로 볼 수 있다.
- **두 배열이 매우 길 때 메모리**: `dp` 2차원 배열이 아니라 이전 행 하나만 유지하는 1차원 압축이 가능하다 (배낭의 1차원 압축과 같은 원리).
:::

## 구간 DP — 팰린드롬 분할

문자열 `s` 를 여러 조각으로 잘라서, **각 조각이 모두 팰린드롬(회문)이 되도록** 하고 싶다. 최소 몇 번 잘라야 하는가? (조각 수가 아니라 "자르는 횟수"를 구한다 — 조각이 1개면 0번.)

이 문제의 특징은 부분 문제가 **연속 구간** `[i, j]` 단위로 정의된다는 것이다. 배낭이나 LIS처럼 "앞에서부터 하나씩" 진행하는 게 아니라, **구간을 어떻게 쪼갤지**가 관건이다. 이런 문제를 구간 DP라고 부른다.

### 1단계: 구간이 팰린드롬인지 미리 표로 만든다

먼저 모든 구간 `[i, j]` 가 팰린드롬인지를 $O(n^2)$ 시간, $O(n^2)$ 공간에 전부 구해 둔다. 이것 자체가 작은 구간 DP다.

**상태**: `is_pal[i][j]` = "`s[i:j+1]` 이 팰린드롬인가".

$$is\_pal[i][j] = (s_i = s_j) \ \wedge\ (j - i < 2\ \lor\ is\_pal[i+1][j-1])$$

```python title="팰린드롬 표 만들기"
def build_palindrome_table(s: str) -> list[list[bool]]:
    n = len(s)
    is_pal = [[False] * n for _ in range(n)]
    for i in range(n):
        is_pal[i][i] = True
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            if s[i] == s[j] and (length == 2 or is_pal[i + 1][j - 1]):
                is_pal[i][j] = True
    return is_pal
```

**짧은 구간부터 채워야** 긴 구간이 짧은 구간의 결과를 참조할 수 있다. 구간 DP는 항상 이 순서(길이가 짧은 것부터, 또는 오른쪽 끝에서부터)로 채운다.

### 2단계: 최소 컷 수

**상태**: `dp[i]` = "`s[i:]` (i번째 글자부터 끝까지)를 전부 팰린드롬 조각으로 나누는 데 필요한 최소 컷 수".

$$dp[i] = \min_{i \le j < n,\ is\_pal[i][j]} \bigl(1 + dp[j+1]\bigr), \qquad dp[n] = -1$$

`dp[n] = -1` 로 두는 이유는, 마지막 조각까지 다 자르고 나면 "그 뒤에 자를 필요가 없다"는 뜻으로 컷 수를 하나 상쇄하기 위해서다(조각이 1개면 컷은 0번이어야 하니까).

```python title="palindrome_partition.py"
def min_palindrome_cuts(s: str) -> int:
    n = len(s)
    is_pal = build_palindrome_table(s)
    dp = [0] * (n + 1)
    dp[n] = -1
    for i in range(n - 1, -1, -1):          # 뒤에서부터 채운다
        best = float("inf")
        for j in range(i, n):
            if is_pal[i][j]:
                best = min(best, 1 + dp[j + 1])
        dp[i] = best
    return dp[0]
```

```python title="검증: 브루트포스(모든 분할)와 대조"
from functools import lru_cache

def min_cut_brute(s: str) -> int:
    n = len(s)
    @lru_cache(maxsize=None)
    def rec(i: int) -> int:
        if i == n:
            return -1
        best = float("inf")
        for j in range(i, n):
            if s[i:j + 1] == s[i:j + 1][::-1]:
                best = min(best, 1 + rec(j + 1))
        return best
    return rec(0)

random.seed(0)
for _ in range(200):
    s = "".join(random.choice("aab") for _ in range(random.randint(1, 10)))
    assert min_cut_brute(s) == min_palindrome_cuts(s)
print("팰린드롬 분할 200회 대조 통과")
print("aab ->", min_palindrome_cuts("aab"))
print("aabbc ->", min_palindrome_cuts("aabbc"))
```

```text nolines
팰린드롬 분할 200회 대조 통과
aab -> 1
aabbc -> 2
```

`"aab"` 는 `"aa" | "b"` 로 한 번만 자르면 되고(`dp[0] = 1`), `"aabbc"` 는 `"aa" | "bb" | "c"` 로 두 번 자른다.

::: cote 구간 DP를 알아보는 신호
- 문제에서 "**구간을 나눈다/합친다**"는 말이 나온다 (분할, 행렬 곱 순서, 구간 병합 비용).
- 상태가 `dp[i][j]` 형태이고, **전이가 구간 안의 어떤 분기점 `k` 를 순회**한다 ($i \le k < j$).
- 대표 문제: 팰린드롬 분할(이번 예제), 행렬 체인 곱셈, 돌 합치기(stone game), 버스트 벌룬.
- 시간복잡도는 보통 $O(n^3)$ — 구간 $O(n^2)$ 개 × 분기점 탐색 $O(n)$. $n$ 이 몇백 수준일 때만 통한다. $n$ 이 크면 다른 접근이 필요하다는 뜻이다.
:::

## 비트마스크 DP — 외판원 문제(TSP)

도시가 $n$ 개 있고 도시 사이의 이동 비용이 주어진다. 도시 0에서 출발해 **모든 도시를 정확히 한 번씩** 방문하고 다시 0으로 돌아오는 최소 비용 경로를 구하라. 이게 그 유명한 외판원 문제(Traveling Salesman Problem)다.

### 브루트포스 — 순열 전체 탐색

가능한 방문 순서는 $(n-1)!$ 가지다.

```python title="tsp_brute.py"
import itertools

def tsp_brute(dist: list[list[int]]) -> int:
    n = len(dist)
    best = float("inf")
    for perm in itertools.permutations(range(1, n)):
        cost, cur = 0, 0
        for nxt in perm:
            cost += dist[cur][nxt]
            cur = nxt
        cost += dist[cur][0]
        best = min(best, cost)
    return best
```

```text nolines
TSP 브루트포스(순열) vs 비트마스크 DP 실측
   n   brute(s)   bitmask(s)
   8     0.0009       0.0003
  10     0.0820       0.0017
  11     0.9124       0.0046
  12    10.2712       0.0097
```

(Python 3.14.5 / Windows 기준 실측.) $n$ 이 1 늘 때마다 브루트포스는 거의 $n$ 배로 느려진다($O(n!)$ 이니까). $n = 12$ 에서 이미 10초를 넘긴다. 코딩테스트에 $n \le 15 \sim 20$ 짜리 "모든 곳을 방문"하는 문제가 나오면, 그건 순열이 아니라 **비트마스크 DP**로 풀라는 신호다.

### 상태 정의 — "방문 집합"을 정수 하나로 압축한다

핵심 통찰은 이거다. 다음에 어디로 갈지 결정하는 데 필요한 정보는 **"지금까지 어느 도시들을 방문했는가(집합)"** 와 **"지금 어디에 있는가"** 뿐이다. **방문 순서 자체는 중요하지 않다.**

**상태**: `dp[mask][u]` = "`mask` 로 표현되는 도시 집합을 이미 방문했고, 지금 도시 `u` 에 있을 때, 여기까지 오는 데 든 최소 비용".

`mask` 는 정수 하나로 표현한다. `n` 개 도시가 있으면 `mask` 의 `i` 번째 비트가 1이면 "도시 `i` 를 방문했다"는 뜻이다. [7.24 비트마스크](#/bitmask)에서 이 표현법을 더 자세히 다룬다.

$$dp[mask][u] \to dp[mask\,|\,(1\!\ll\! v)][v] = \min\bigl(\cdots,\ dp[mask][u] + dist[u][v]\bigr) \quad (v \notin mask)$$

```python title="tsp_bitmask.py"
def tsp_bitmask(dist: list[list[int]]) -> int:
    n = len(dist)
    INF = float("inf")
    dp = [[INF] * n for _ in range(1 << n)]
    dp[1][0] = 0                       # 도시 0만 방문한 상태, 지금 0에 있음
    for mask in range(1 << n):
        for u in range(n):
            if dp[mask][u] == INF or not (mask & (1 << u)):
                continue
            for v in range(n):
                if mask & (1 << v):
                    continue           # 이미 방문한 도시
                nmask = mask | (1 << v)
                ncost = dp[mask][u] + dist[u][v]
                if ncost < dp[nmask][v]:
                    dp[nmask][v] = ncost
    full = (1 << n) - 1
    return min(dp[full][u] + dist[u][0] for u in range(n) if dp[full][u] < INF)
```

```python title="검증: 브루트포스와 대조"
random.seed(0)
for _ in range(50):
    n = random.randint(2, 8)
    dist = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i][j] = random.randint(1, 20)
    assert tsp_brute(dist) == tsp_bitmask(dist)
print("TSP 비트마스크 50회 대조 통과")
```

```text nolines
TSP 비트마스크 50회 대조 통과
```

상태 개수는 $2^n \times n$, 전이마다 $O(n)$ 이므로 전체 $O(2^n n^2)$ 이다. $n!$ 보다 훨씬 느리게 자라서 $n = 20$ 정도까지도 현실적으로 돈다(`2^20 * 400 ≈ 4 \times 10^8` — 언어에 따라 빠듯할 수 있어 PyPy나 C++을 쓰는 경우가 많지만, 파이썬이라도 $n \le 15$ 안팎에서는 충분히 통과권이다).

::: cote 비트마스크 DP를 알아보는 신호
- 문제 제약이 **$n \le 15 \sim 22$ 정도로 유난히 작다.** 이건 우연이 아니라 출제자가 $2^n$ 을 의도한 것이다.
- "**모든 원소를 정확히 한 번씩 사용/방문**"이라는 조건이 있다 (TSP, 최소 신장 부분집합, 조 짜기 문제).
- 상태 전이에서 "이미 쓴 것들의 집합"이 다음 선택에 영향을 준다.
- **`dp` 배열의 크기가 `2**n`** 이므로 메모리도 같이 확인하라. `n = 20` 이면 `dp[mask][u]` 가 $2^{20} \times 20 \approx 2 \times 10^7$ 칸이다.
:::

## 트리 DP — 서브트리의 두 가지 선택

트리 구조에서 각 노드에 가중치가 있다. **인접한 두 노드를 동시에 고르지 못한다**는 제약 아래, 고른 노드들의 가중치 합을 최대화하라(트리 버전의 "최대 가중치 독립 집합". 회사 조직도에서 "직속 상사와 부하를 동시에 초대하지 않기" 문제로도 잘 알려져 있다).

### 상태 정의 — 노드마다 "포함/제외" 두 값을 들고 다닌다

트리 DP의 표준 패턴은 이거다. 각 노드에서 **자식의 답을 먼저 구한 뒤(후위 순회) 부모의 답을 조립**한다.

**상태**: 노드 `u` 에 대해 두 값을 계산한다.

- `include[u]` = "`u` 를 반드시 포함할 때, `u` 의 서브트리에서 얻을 수 있는 최댓값"
- `exclude[u]` = "`u` 를 반드시 제외할 때, `u` 의 서브트리에서 얻을 수 있는 최댓값"

전이는 이렇다.

$$include[u] = weight[u] + \sum_{c \in children(u)} exclude[c]$$
$$exclude[u] = \sum_{c \in children(u)} \max(include[c],\ exclude[c])$$

`u` 를 포함하면 **자식은 반드시 제외**해야 한다(인접 조건). `u` 를 제외하면 자식은 자유롭게 고르든 말든 좋은 쪽을 택한다.

```python title="tree_dp.py"
import sys

def max_weight_independent_set(n: int, edges: list[tuple[int, int]], weight: list[int], root: int = 0) -> int:
    adj: list[list[int]] = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)

    include = [0] * n
    exclude = [0] * n

    def dfs(u: int, parent: int) -> None:
        include[u] = weight[u]
        exclude[u] = 0
        for v in adj[u]:
            if v == parent:
                continue
            dfs(v, u)
            include[u] += exclude[v]                       # u를 쓰면 자식은 제외만
            exclude[u] += max(include[v], exclude[v])       # u를 안 쓰면 자식은 자유

    dfs(root, -1)
    return max(include[root], exclude[root])
```

```python title="검증: 브루트포스(모든 부분집합 중 인접 없는 것)와 대조"
def brute(n: int, edges: list[tuple[int, int]], weight: list[int]) -> int:
    best = 0
    for mask in range(1 << n):
        valid = all(not ((mask & (1 << u)) and (mask & (1 << v))) for u, v in edges)
        if valid:
            best = max(best, sum(weight[i] for i in range(n) if mask & (1 << i)))
    return best

random.seed(0)
for _ in range(200):
    n = random.randint(1, 9)
    weight = [random.randint(1, 10) for _ in range(n)]
    edges = [(random.randint(0, i - 1), i) for i in range(1, n)]   # 무작위 트리
    assert brute(n, edges, weight) == max_weight_independent_set(n, edges, weight)
print("트리 DP 200회 대조 통과")

edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]
weight = [3, 2, 1, 10, 10, 1, 1]
print(max_weight_independent_set(7, edges, weight))
```

```text nolines
트리 DP 200회 대조 통과
25
```

노드가 7개, 뿌리 0에서 자식 1과 2가 뻗고, 1의 자식이 3·4(가중치 10, 10), 2의 자식이 5·6(가중치 1, 1)인 트리에서 답은 25다. 0은 1·2와만 인접하고 3·4·5·6과는 인접하지 않으므로, **1과 2를 포기하고 0, 3, 4, 5, 6을 모두 선택**하면 된다: $3 + 10 + 10 + 1 + 1 = 25$. 가중치가 큰 잎(3, 4)을 확보하려고 그 부모(1)를 포기하는 판단을 트리 DP가 자동으로 내려 준 것이다.

::: warn 재귀 깊이에 주의
`dfs` 는 트리 깊이만큼 재귀가 쌓인다. 노드가 $10^5$ 개인 편향 트리(사실상 연결 리스트)라면 파이썬 기본 재귀 한도($1000$)를 넘겨 `RecursionError` 가 난다. 이럴 때는 `sys.setrecursionlimit` 을 늘리거나, 스택을 직접 관리하는 반복문(명시적 스택 + 두 번 방문 트릭)으로 바꿔야 한다. 재귀 깊이 문제는 [7.13 그래프 표현과 순회](#/graph)에서 더 자세히 다룬다.
:::

::: cote 트리 DP를 알아보는 신호
- 문제가 **트리 구조**(사이클 없는 연결 그래프)를 준다.
- "인접한 것끼리는 안 된다", "부모-자식 관계에 제약이 있다"는 조건.
- 상태가 노드마다 **몇 가지 경우의 수**(포함/제외, 색칠 여부 등)로 나뉜다.
- 후위 순회(자식 → 부모) 순서로 답을 조립한다는 점이 배낭·LIS와 다른 핵심 차이다. 앞에서부터 채우는 게 아니라 **잎에서부터 뿌리로** 올라온다.
:::

## 종합: DP를 설계하는 순서

지금까지 여섯 유형을 봤다. 실전에서 DP 문제를 만나면 이 순서로 접근하면 된다.

1. **브루트포스를 먼저 떠올린다.** 대부분 재귀나 완전 탐색으로 자연스럽게 풀린다. 이게 상태 전이의 원형이 된다.
2. **브루트포스에서 중복 계산되는 부분 문제를 찾는다.** 같은 인자로 재귀 함수가 여러 번 불리는가? 그게 겹치는 부분 문제(overlapping subproblems)다.
3. **부분 문제를 숫자/튜플로 표현한다.** 이게 상태 정의다. 이 절의 표를 다시 보라 — 상태가 인덱스 하나(`dp[i]`)인지, 둘(`dp[i][j]`)인지, 집합을 포함하는지(`dp[mask]`)에 따라 문제의 성격이 갈린다.
4. **전이식을 쓴다.** "이 상태에 도달하는 직전 상태는 무엇이었나"를 역으로 물으면 나온다.
5. **채우는 순서를 정한다.** 배낭·LIS는 앞에서 뒤로, 구간 DP는 짧은 구간에서 긴 구간으로, 트리 DP는 잎에서 뿌리로.
6. **작은 예제와 브루트포스로 검증한다.** 이 절의 모든 코드가 그렇게 검증됐다. 손으로 짠 DP가 맞는지 스스로도 믿지 마라 — 코드로 확인하라.

이 여섯 단계는 [8.8 실전 풀이 III — DP](#/drill-dp)에서 실제 문제들에 반복 적용하며 몸에 붙인다.

## 요약

- DP의 본질은 **상태 정의**다. 상태를 잘못 잡으면 전이식도, 복잡도도 다 틀어진다.
- 0/1 배낭은 `dp[i][c]`, 역순 루프로 1차원 압축. 순서를 정순으로 바꾸면 무한 배낭이 된다.
- LIS는 $O(n^2)$(`dp[i]` = i로 끝나는 길이)와 $O(n \log n)$(`tails[k]` = 길이 k+1의 최소 끝값 + 이분 탐색) 둘 다 알아야 한다. 후자는 원소 복원이 따로 필요하다.
- LCS는 `dp[i][j]`, 마지막 글자가 같으면 대각선, 다르면 위/왼쪽 중 큰 값.
- 구간 DP(`dp[i][j]`)는 짧은 구간부터 채우고, 분기점 `k` 를 순회하는 전이가 특징이다. 대체로 $O(n^3)$.
- 비트마스크 DP(`dp[mask][u]`)는 "방문 집합"을 정수로 압축한다. 제약이 $n \le 20$ 안팎이면 이 유형을 의심하라.
- 트리 DP는 후위 순회로 자식의 포함/제외 값을 부모가 조립한다. 재귀 깊이 문제를 조심하라.
- 모든 DP는 **작은 입력에서 브루트포스와 대조**해서 검증할 수 있고, 반드시 그렇게 검증해야 한다.

::: quiz 연습문제
1. 배낭 문제에서 `dp` 를 1차원으로 압축할 때 왜 무게 `c` 를 **역순**으로 순회해야 하는지, 정순으로 돌리면 어떤 값이 잘못되는지 구체적인 예시(물건 1개, 무게 3, 가치 5, 용량 6)로 직접 확인하라.
2. LIS의 $O(n \log n)$ 풀이에서 `tails` 배열을 실제로 출력해 가며, 왜 이 배열 자체는 정답 수열이 아닌지 반례를 하나 만들어라.
3. 팰린드롬 분할 문제를 "최소 컷 수"가 아니라 "가능한 분할의 총 개수"를 구하는 문제로 바꿔라. 점화식이 어떻게 달라지는가?
4. TSP 비트마스크 DP에서 `dp` 배열의 메모리 크기를 $n = 18$ 일 때 계산하라. 파이썬 `float` 객체 하나가 대략 24바이트를 차지한다고 가정하면 총 메모리는 대략 몇 MB인가?
5. 트리 DP를 "인접한 두 노드를 고르지 못한다"가 아니라 "**같은 부모를 공유하는 형제끼리는 최대 2명까지만** 고를 수 있다"로 바꾸면 상태를 어떻게 확장해야 하는가?
:::

**다음 절**: [7.22 문자열 알고리즘](#/string-algo) — KMP와 라빈-카프로 문자열 검색을 $O(n)$, $O(n+m)$ 에 끝내는 법.
