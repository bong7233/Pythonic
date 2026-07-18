# 7.20 동적 계획법 기초

::: lead
계단을 한 번에 1칸 또는 2칸씩 오른다. n칸짜리 계단을 오르는 방법은 몇 가지인가? 재귀로 짜면 세 줄이면 끝난다. 그런데 그 세 줄짜리 코드를 백준에 그대로 내면 $n=40$ 근처에서부터 시간 초과를 받는다. 정답은 맞는데 느리다 — 이 절 전체가 그 이유와 해법을 다룬다. 동적 계획법(dynamic programming, DP)은 새로운 알고리즘이 아니다. **같은 부분 문제를 두 번 풀지 않는다**는 원칙 하나를 재귀에 적용한 것뿐이다. 그 원칙을 [7.18 재귀와 백트래킹](#/backtracking)의 완전탐색과 나란히 놓고 보면, DP가 왜 "가지치기의 특수한 형태"인지 보인다.
:::

## 왜 느린가 — 재귀 트리를 직접 그려 본다

계단 오르기 문제를 가장 순진하게 풀면 이렇다.

```python title="climb_brute — 완전탐색"
def climb_brute(n):
    if n <= 2:
        return n
    return climb_brute(n - 1) + climb_brute(n - 2)
```

`climb_brute(5)` 를 호출하면 내부에서 무슨 일이 벌어지는지 호출 트리로 펼쳐 보자.

```text nolines
climb_brute(5)
|-- climb_brute(4)
|     |-- climb_brute(3)
|     |     |-- climb_brute(2)
|     |     `-- climb_brute(1)
|     `-- climb_brute(2)
`-- climb_brute(3)         <- 이 서브트리, 위에서 이미 계산했다!
      |-- climb_brute(2)
      `-- climb_brute(1)
```

`climb_brute(3)` 이 통째로 **두 번** 계산된다. $n$ 이 커질수록 이 중복은 기하급수적으로 불어난다. 직접 실측해 보자.

```pyrepl
>>> import time
>>> for n in [20, 25, 30, 34]:
...     start = time.perf_counter()
...     climb_brute(n)
...     print(n, f"{(time.perf_counter()-start)*1000:.2f} ms")
20 0.32 ms
25 3.58 ms
30 39.66 ms
34 276.29 ms
```

(Python 3.14.5 / Windows 기준 실측.) $n$ 이 4~5 늘 때마다 시간이 대략 **10배**씩 뛴다. `climb_brute(n)` 의 호출 횟수는 피보나치 수 자체와 같은 속도로, 즉 $O(\varphi^n)$ ($\varphi \approx 1.618$)으로 커진다. $n=40$ 이면 호출 횟수가 억 단위를 넘는다. [7.1 시간·공간 복잡도](#/complexity)에서 본 "파이썬은 초당 수천만 번" 감각을 대입하면, 이 코드는 $n=40$ 근처에서 이미 수십 초짜리 코드다.

::: cote 지수 시간 재귀는 신호다
문제에 "몇 가지 방법이 있는가", "최댓값/최솟값을 구하라" 같은 문구가 있고, 순진한 재귀를 짜면 겹치는 부분 문제가 보인다면 — 그건 브루트포스로 풀 문제가 아니라 DP로 풀라는 신호다. 반대로 부분 문제가 하나도 겹치지 않는다면(예: 순열 생성) DP가 아니라 그냥 완전탐색이 맞다. 이 구분은 [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 더 다룬다.
:::

## 점화식을 세우는 사고 과정

DP를 어렵게 느끼는 이유는 대개 "점화식을 어떻게 세우는지" 순서가 안 잡혀서다. 순서는 항상 같다.

1. **답이 무엇인지 정의한다.** "$n$ 칸을 오르는 방법의 수"처럼, 구하려는 것을 함수 하나로 못 박는다. 이걸 $f(n)$ 이라 부르자.
2. **마지막 선택으로 문제를 쪼갠다.** 정답으로 가는 마지막 한 걸음에서 무엇을 고를 수 있는가? 계단 문제라면, $n$ 번째 칸에 도달하는 **마지막 걸음**은 두 가지뿐이다 — $(n-1)$ 에서 1칸을 오르거나, $(n-2)$ 에서 2칸을 오르거나.
3. **그 선택들을 더 작은 같은 문제로 표현한다.** $n$ 에 도달하는 방법의 수는, $(n-1)$ 에 도달하는 방법의 수 더하기 $(n-2)$ 에 도달하는 방법의 수다. 왜냐하면 두 경로가 절대 겹치지 않기 때문이다(마지막 걸음이 다르므로).
4. **기저 조건을 정한다.** 더 쪼갤 수 없는 가장 작은 경우를 직접 정의한다. $f(1) = 1$, $f(2) = 2$.

이 네 단계를 거치면 나오는 게 점화식이다.

$$f(n) = f(n-1) + f(n-2), \quad f(1) = 1,\ f(2) = 2$$

**핵심은 2번 단계다.** "마지막 선택이 무엇인가"라는 질문이 문제를 부분 문제로 쪼개는 유일한 도구다. 뒤에서 다룰 최대 부분합도, [7.21 배낭·LIS·LCS](#/dp-advanced)의 모든 문제도 전부 이 질문에서 시작한다. "지금 위치에 마지막으로 도달하는 방법이 몇 가지 있고, 각각에서 남은 문제는 무엇인가"를 답할 수 있으면 점화식은 거의 다 세운 것이다.

`climb_brute` 가 느린 진짜 이유는 이제 명확하다. **점화식 자체는 옳다.** 문제는 구현이 $f(n-2)$ 를 구할 때 필요한 계산을 매번 처음부터 다시 하는 것이다. 값을 한 번 구하면 저장해 두고 재사용하면 된다 — 이게 DP의 전부다.

## 메모이제이션: 재귀에 캐시를 얹는다

가장 적은 코드 수정으로 겹치는 계산을 없애는 방법이 **메모이제이션**(memoization)이다. 파이썬에서는 `functools.lru_cache` 데코레이터 하나로 끝난다 ([3.1 functools](#/functools)에서 이 데코레이터의 내부를 다룬다).

```python title="climb_memo — 메모이제이션"
from functools import lru_cache

@lru_cache(maxsize=None)
def climb_memo(n):
    if n <= 2:
        return n
    return climb_memo(n - 1) + climb_memo(n - 2)
```

코드는 딱 데코레이터 한 줄만 늘었다. 재귀 구조, 점화식, 기저 조건 전부 그대로다. `lru_cache` 가 하는 일은 단순하다 — **인자를 키로 삼아 반환값을 딕셔너리에 저장**하고, 같은 인자로 다시 불리면 저장된 값을 즉시 돌려준다. 그래서 `climb_memo(3)` 은 평생 딱 한 번만 실제로 계산된다.

정답이 같은지부터 확인하고 넘어가자.

```python title="정답 대조"
def climb_tab(n):
    if n <= 2:
        return n
    dp = [0] * (n + 1)
    dp[1], dp[2] = 1, 2
    for i in range(3, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]

for n in range(1, 26):
    assert climb_brute(n) == climb_memo(n) == climb_tab(n)
print("계단 오르기: 3가지 구현 정답 대조 통과 (n=1..25)")
```

```text
계단 오르기: 3가지 구현 정답 대조 통과 (n=1..25)
```

이제 속도를 실측한다.

```pyrepl
>>> climb_memo.cache_clear()
>>> start = time.perf_counter()
>>> climb_memo(900)
>>> print(f"{(time.perf_counter()-start)*1000:.3f} ms")
1.089 ms
```

`climb_brute(34)` 는 276 ms 걸렸는데 `climb_memo(900)` 은 **1 ms** 가 안 걸린다. 지수 시간이 선형 시간으로 떨어진 결과다. 메모이제이션 후 시간복잡도는 "서로 다른 인자의 개수 $\times$ 인자 하나당 일" — 여기서는 $O(n)$ 개의 서로 다른 호출이 각각 $O(1)$ 의 일을 하니 전체 $O(n)$ 이다.

::: warn lru_cache는 인자를 해시할 수 있어야 한다
```python
@lru_cache(maxsize=None)
def f(arr, i):
    return arr[i]

f([1, 2, 3], 0)
```

```text
TypeError: unhashable type: 'list'
```

`lru_cache` 는 인자를 딕셔너리 키로 쓰기 때문에 **해시 가능해야 한다** ([1.7 set과 frozenset](#/sets)에서 해시 가능성의 조건을 다룬다). 리스트를 인자로 넘기는 DP 함수를 짜고 싶다면 튜플로 바꾸거나(`tuple(arr)`), 배열 자체는 클로저나 전역으로 캡처하고 인덱스만 인자로 넘겨라. 코딩테스트에서 재귀 DP 함수에 리스트를 그대로 넘겨서 이 에러를 만나는 일이 실제로 잦다.
:::

## 재귀+메모 vs 반복(타뷸레이션) — 진짜 트레이드오프

메모이제이션은 **위에서 아래로**(top-down) 간다 — `climb_memo(900)` 을 물으면 그게 `climb_memo(899)` 와 `climb_memo(898)` 을 묻고, 그게 다시 더 작은 값을 묻는 식으로 기저 조건까지 내려갔다가 값을 채우며 올라온다.

**타뷸레이션**(tabulation)은 반대로 **아래에서 위로**(bottom-up) 간다. 기저 조건부터 시작해서 반복문으로 순서대로 채운다.

```python title="climb_tab_o1 — 반복, 공간까지 O(1)로"
def climb_tab_o1(n):
    if n <= 2:
        return n
    a, b = 1, 2                 # f(1), f(2)
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
```

두 방식은 **같은 값을 계산하지만 공학적으로는 다른 선택**이다. 실측으로 차이를 짚어 보자.

### 재귀 깊이 — 여기가 진짜 차이다

메모이제이션은 여전히 **재귀**다. `climb_memo(n)` 은 파이썬 호출 스택에 깊이 $n$ 짜리 프레임을 쌓는다. [7.1 시간·공간 복잡도](#/complexity)에서 본 재귀 깊이 한계가 그대로 발목을 잡는다.

```pyrepl
>>> import sys
>>> print(sys.getrecursionlimit())
1000
>>> climb_memo.cache_clear()
>>> climb_memo(2000)
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

`sys.setrecursionlimit()` 로 한도를 올리면 해결될 것 같지만, 실제로 해 보면 다르다.

```pyrepl
>>> sys.setrecursionlimit(100_000)
>>> for n in [1000, 1100, 1500, 2000]:
...     climb_memo.cache_clear()
...     try:
...         climb_memo(n)
...         print(n, "성공")
...     except RecursionError as e:
...         print(n, "실패:", e)
1000 성공
1100 실패: Stack overflow (used 2913 kB)
1500 실패: Stack overflow (used 2913 kB)
2000 실패: Stack overflow (used 2913 kB)
```

(Python 3.14.5 / Windows 기준 실측. 정확한 경계값은 스레드 스택 크기에 따라 기기마다 다르다.)

`setrecursionlimit` 을 10만으로 올려도 깊이 1000~1100 근처에서 여전히 막힌다. **파이썬의 논리적 한도가 아니라 운영체제가 스레드에 준 진짜 C 스택이 먼저 바닥나기 때문이다.** 다행히 최신 CPython은 이 상황을 감지해서 `RecursionError` 로 곱게 던진다 — 예전 같으면 인터프리터가 그냥 죽었을 상황이다. [7.1절](#/complexity)의 경고를 여기서 실제로 확인한 셈이다.

`climb_tab_o1` 은 이 문제 자체가 없다. 재귀가 아니라 `for` 문이므로 스택이 늘지 않는다.

```pyrepl
>>> start = time.perf_counter()
>>> climb_tab_o1(32_000)
>>> print(f"{(time.perf_counter()-start)*1000:.3f} ms")
7.477 ms
```

$n=32{,}000$ 은 재귀+메모로는 애초에 시도할 수도 없는 크기다. 타뷸레이션은 아무렇지 않게 처리한다.

::: cote 재귀 DP를 쓸 거면 깊이부터 따져라
문제의 제약 조건에 $n \le 10^5$, $n \le 10^6$ 같은 큰 수가 나오고 DP의 상태가 "$n$ 자체"에 선형으로 의존한다면, **재귀+메모는 위험하다.** 깊이가 그대로 $n$ 이 되기 때문이다. 이럴 때는 처음부터 타뷸레이션으로 짜라. 반대로 $n$ 이 작거나(수백 이하) 상태 공간이 복잡해서 점화식을 반복문 순서로 짜기 번거로우면(트리 DP, 상태가 여러 개인 DP) 재귀+메모가 코드를 훨씬 짧고 정확하게 만든다. [7.21 동적 계획법 심화](#/dp-advanced)의 트리 DP·비트마스크 DP에서 재귀+메모가 압도적으로 편한 경우를 본다.
:::

### 공간 — 타뷸레이션은 압축할 수 있다

`climb_tab` 은 `dp` 배열 전체($O(n)$ 공간)를 들고 있지만, 점화식이 "바로 이전 두 값만" 참조한다는 걸 알면 `climb_tab_o1` 처럼 변수 두 개로 줄일 수 있다. **재귀+메모는 이 압축이 안 된다** — `lru_cache` 가 모든 호출 결과를 다 들고 있어야 하고, 그걸 임의로 지울 방법이 마땅치 않다. 배열을 직접 다루는 타뷸레이션이라야 "지금 필요한 것만 남기고 버리는" 최적화가 가능하다. 이 기법은 [7.21절](#/dp-advanced)의 배낭 문제에서 2차원 DP를 1차원으로 압축할 때 다시 쓴다.

정리하면 이렇다.

| | 재귀 + 메모이제이션 | 반복 (타뷸레이션) |
| --- | --- | --- |
| 방향 | top-down (필요한 것만 계산) | bottom-up (전부 순서대로 계산) |
| 코드 형태 | 점화식을 거의 그대로 옮겨 적는다 | 계산 순서를 직접 설계해야 한다 |
| 재귀 깊이 | $O(n)$ — 큰 $n$ 에서 위험 | 없음 |
| 공간 압축 | 어렵다 | 쉽다 (필요한 이전 상태만 유지) |
| 상태가 일부만 필요할 때 | 유리 (안 쓰는 상태는 계산 안 함) | 불리 (보통 전부 계산) |

## 1차원 DP: 최대 부분합

계단 오르기 말고 1차원 DP의 또 다른 전형을 보자. **연속한 부분 배열 중 합이 최대인 것을 찾아라**(최대 부분합, maximum subarray). 코딩테스트에 정말 자주 나온다.

브루트포스는 모든 구간의 합을 다 구한다.

```python title="max_subarray_brute — O(n^2)"
def max_subarray_brute(arr):
    n = len(arr)
    best = arr[0]
    for i in range(n):
        s = 0
        for j in range(i, n):
            s += arr[j]
            best = max(best, s)
    return best
```

이제 점화식 세우기 4단계를 그대로 적용해 보자.

1. **답의 정의**: $f(i)$ = "인덱스 $i$ 에서 **반드시 끝나는** 부분 배열의 최댓값". (전체 답이 아니라 "$i$에서 끝난다"는 조건을 붙인 게 핵심이다.)
2. **마지막 선택**: $i$ 에서 끝나는 최적의 부분 배열은 둘 중 하나다 — `arr[i]` 하나만 쓰거나, $f(i-1)$ 이 만든 부분 배열 뒤에 `arr[i]` 를 이어 붙이거나.
3. **부분 문제로 표현**: $f(i-1)$ 이 양수로 도움이 되면 이어 붙이고, 오히려 깎아 먹으면($f(i-1) < 0$) 버리고 `arr[i]` 부터 새로 시작한다. 즉 $f(i) = \max(\text{arr}[i],\ f(i-1) + \text{arr}[i])$.
4. **기저 조건**: $f(0) = \text{arr}[0]$.

전체 답은 $\max_i f(i)$ 다. 이게 **카데인 알고리즘**(Kadane's algorithm)이고, DP 배열을 통째로 들고 있을 필요 없이 "직전 값 하나"만 기억하면 되므로 $O(1)$ 공간, $O(n)$ 시간으로 짤 수 있다.

```python title="max_subarray_kadane — O(n)"
def max_subarray_kadane(arr):
    best = cur = arr[0]
    for x in arr[1:]:
        cur = max(x, cur + x)   # f(i) = max(arr[i], f(i-1)+arr[i])
        best = max(best, cur)
    return best
```

정답 대조부터 한다.

```python title="정답 대조 — 무작위 300케이스"
import random

random.seed(0)
for _ in range(300):
    n = random.randint(1, 40)
    arr = [random.randint(-20, 20) for _ in range(n)]
    assert max_subarray_brute(arr) == max_subarray_kadane(arr)
print("최대 부분합: brute force vs kadane 정답 대조 통과 (300케이스)")
```

```text
최대 부분합: brute force vs kadane 정답 대조 통과 (300케이스)
```

시간을 재 보자.

```pyrepl
>>> import timeit, random
>>> for n in [500, 1000, 2000, 4000]:
...     arr = [random.randint(-100, 100) for _ in range(n)]
...     t = timeit.timeit(lambda: max_subarray_brute(arr), number=3) / 3
...     print("brute", n, f"{t*1000:.2f} ms")
brute 500 4.45 ms
brute 1000 20.16 ms
brute 2000 76.11 ms
brute 4000 305.23 ms
>>> for n in [10_000, 100_000, 1_000_000, 5_000_000]:
...     arr = [random.randint(-100, 100) for _ in range(n)]
...     t = timeit.timeit(lambda: max_subarray_kadane(arr), number=3) / 3
...     print("kadane", n, f"{t*1000:.3f} ms")
kadane 10000 0.490 ms
kadane 100000 5.074 ms
kadane 1000000 54.784 ms
kadane 5000000 264.098 ms
```

(Python 3.14.5 / Windows 기준 실측.) brute force는 $n$ 이 두 배 될 때마다 시간이 네 배($O(n^2)$)로 뛴다. kadane은 $n$ 이 열 배 될 때 시간도 열 배 근처로만 는다($O(n)$) — $n = 4{,}000$ 에서 brute force가 이미 305 ms 인데, kadane은 그보다 1250배 더 큰 $n = 5{,}000{,}000$ 을 264 ms 에 처리한다.

::: cote 최대 부분합의 함정
1. **전부 음수인 배열.** `best = 0` 으로 초기화하고 시작하면 "부분 배열은 최소 1개는 골라야 한다"는 조건을 깨고 빈 배열(합 0)을 답으로 낼 수 있다. 위 구현처럼 `best = cur = arr[0]` 으로 **첫 원소로 초기화**해야 안전하다.
2. **"부분 배열의 시작·끝 인덱스도 같이 구하라"** 는 변형이 잦다. `cur` 이 `arr[i]` 로 리셋되는 순간의 인덱스를 별도 변수로 추적하면 된다.
3. **원형 배열(circular array) 버전.** "배열이 원형으로 이어진다"는 변형은 "전체 합 − 최소 부분합"으로 바꿔 푸는 트릭이 있다. 카데인 알고리즘 하나로 최대·최소를 모두 구하면 된다.
:::

## 요약

- DP는 새 알고리즘이 아니라 **"같은 부분 문제를 두 번 풀지 않는다"**는 원칙이다. 점화식이 옳아도 겹치는 계산을 방치하면 지수 시간이 된다.
- 점화식은 항상 같은 순서로 세운다 — **답을 정의 → 마지막 선택으로 쪼갠다 → 부분 문제로 표현 → 기저 조건.**
- `functools.lru_cache` 로 재귀에 메모이제이션을 얹으면 코드를 거의 그대로 두고 지수 시간을 선형/다항 시간으로 바꿀 수 있다. 단, 인자는 해시 가능해야 한다.
- 재귀+메모는 **재귀 깊이가 곧 $n$** 이다. 실측으로 확인했듯 `setrecursionlimit` 을 올려도 진짜 C 스택 앞에서는 무력하다. $n$ 이 크면 처음부터 타뷸레이션(반복문)으로 짜라.
- 타뷸레이션은 재귀 깊이 걱정이 없고, 점화식이 "직전 몇 개만 참조"하면 배열 전체를 O(n) → O(1) 공간으로 압축할 수 있다.
- 계단 오르기와 최대 부분합 둘 다 "1차원 상태, 이전 한두 값만 참조"라는 같은 뼈대를 공유한다. 이 뼈대가 [7.21 동적 계획법 심화](#/dp-advanced)에서 2차원(배낭), 문자열 두 개(LCS)로 확장된다.

::: quiz 연습문제
1. `climb_brute(n)` 의 호출 횟수를 실제로 세어 보라(전역 카운터를 두거나 데코레이터를 씌워서). $n=10, 20, 30$ 에서 세어 본 값이 피보나치 수와 어떤 관계인지 설명하라.

2. 계단을 1칸, 2칸, **3칸**까지 오를 수 있다면 점화식은 어떻게 바뀌는가? 4단계 사고 과정을 그대로 적용해 새 점화식을 세우고, `climb_tab_o1` 을 수정한 `climb3_tab` 을 작성해 무작위 브루트포스와 대조하라.

3. 다음 코드가 `TypeError` 를 내는 이유와 고치는 두 가지 방법을 설명하라.

   ```python
   from functools import lru_cache

   @lru_cache(maxsize=None)
   def solve(nums, i):
       if i >= len(nums):
           return 0
       return max(nums[i], solve(nums, i + 1))
   ```

4. `max_subarray_kadane` 에서 `best = cur = 0` 으로 초기화하면 어떤 입력에서 틀린 답을 내는가? 반례를 하나 만들고 왜 틀리는지 설명하라.

5. **깊이 생각해 볼 문제.** 재귀+메모와 타뷸레이션은 항상 같은 값을 계산하는데, 왜 하나는 재귀 깊이 문제가 있고 하나는 없는가? "호출 스택"과 "명시적 배열"의 차이로 설명하라. 그리고 이 차이가 [8.3 시간 초과를 피하는 관용구](#/tle)에서 왜 실전적으로 중요한지 한 문장을 덧붙여라.
:::

**다음 절**: [7.21 동적 계획법 심화](#/dp-advanced) — 배낭 문제, LIS, LCS, 구간 DP, 비트마스크 DP, 트리 DP로 상태를 2차원 이상으로 확장한다.
