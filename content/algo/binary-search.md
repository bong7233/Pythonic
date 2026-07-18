# 7.5 이분 탐색

::: lead
정렬된 배열에서 값을 찾는 데 왜 반복문을 돌리면 안 되는가. 답은 간단하다 — 정렬돼 있다는 정보를 버리기 때문이다. 이분 탐색은 그 정보를 써서 $O(n)$을 $O(\log n)$으로 줄인다. 이 절의 진짜 핵심은 탐색 자체가 아니라 **불변식(invariant)을 정확히 세우는 법**이다. 코딩테스트에서 이분 탐색 코드를 짜다가 무한 루프에 빠지거나 결과가 하나씩 어긋나는 사고는 전부 불변식을 대충 세워서 생긴다. 그리고 이 절의 후반부, **매개변수 탐색**은 "값 찾기"를 넘어 "정답 자체를 이분 탐색으로 찾는" 기법이다. 코딩테스트에서 이분 탐색이 실제로 쓰이는 자리는 대부분 여기다.
:::

## 정렬돼 있다는 걸 알면서 왜 처음부터 훑는가

[7.1 시간·공간 복잡도](#/complexity)에서 봤듯, `x in a` 나 `for` 로 값을 찾는 건 정렬 여부와 무관하게 $O(n)$이다. 리스트가 정렬돼 있다는 사실을 전혀 활용하지 않기 때문이다.

정렬된 배열이 있다면 중간값 하나만 봐도 절반을 통째로 버릴 수 있다. 중간값이 찾는 값보다 크면 오른쪽 절반은 볼 필요가 없고, 작으면 왼쪽 절반은 볼 필요가 없다. 매번 절반을 버리므로 최악의 경우도 $\log_2 n$번이면 끝난다.

숫자로 느껴보자. $n$이 100만이면 $\log_2 n \approx 20$이다. 선형 탐색이 최악의 경우 100만 번 비교할 때, 이분 탐색은 20번이면 충분하다. 실제로 측정한 값이다.

```python title="linear_vs_bisect.py — 100만 원소, 맨 끝 값을 찾는 최악의 경우"
import bisect
import timeit

n = 1_000_000
a = list(range(n))
target = n - 1

t_lin = timeit.timeit(lambda: target in a, number=200)
t_bin = timeit.timeit(lambda: bisect.bisect_left(a, target), number=200)
print(f"linear={t_lin:.5f}s  bisect={t_bin:.6f}s  배수={t_lin / t_bin:.1f}x")
```

```text nolines
linear=0.72196s  bisect=0.000030s  배수=23748.6x
```

(Python 3.14.5 / Windows 기준 실측.) 배수가 2만 배가 넘는다. 크기별로 찍어 보면 로그 성장이 더 분명히 보인다.

| n | 선형 탐색 | `bisect_left` | 배수 |
| --- | --- | --- | --- |
| 1,000 | 0.00069s | 0.000022s | 31배 |
| 10,000 | 0.00666s | 0.000025s | 268배 |
| 100,000 | 0.06768s | 0.000027s | 2,488배 |
| 1,000,000 | 0.72196s | 0.000030s | 23,749배 |

선형 탐색 시간은 $n$에 정비례해서 늘어나는데(10배 커질 때마다 시간도 약 10배), `bisect_left` 시간은 100만에서도 여전히 0.00003초 근처에 머무른다. $\log_2(1{,}000{,}000) \approx 20$, $\log_2(1{,}000) \approx 10$이니 두 배 늘어나야 정상인데 실측값은 그보다도 덜 늘었다 — 그만큼 로그 함수는 완만하다. 이게 "정렬해 두면 이후 탐색이 사실상 공짜"라는 말의 실체다.

::: cote 코딩테스트 신호
문제에 "정렬된 배열에서", "N번 쿼리로 조회", 또는 제약 조건에 $N \le 10^6$ 같은 큰 수와 함께 "찾기/조회"가 섞여 있으면 이분 탐색 후보다. 정렬이 안 돼 있어도 **한 번만 정렬**($O(n \log n)$)하고 나머지 쿼리를 전부 이분 탐색($O(\log n)$)으로 처리하면 전체가 $O((n+q)\log n)$이 된다. [8.3 시간 초과를 피하는 관용구](#/tle)에서 이 패턴을 더 다룬다.
:::

## 불변식을 세우는 법 — off-by-one을 피하는 유일한 방법

이분 탐색은 짧은 코드지만 변형이 무수히 많고, 그만큼 틀리기 쉽다. 원인은 거의 항상 하나다. **탐색 구간이 무엇을 의미하는지 정하지 않고 코드부터 짠다.**

이 절에서는 반열린 구간 `[lo, hi)` 를 쓴다. 즉 `lo`는 포함, `hi`는 제외다. 그리고 탐색 내내 다음 불변식을 지킨다.

> `a[i] < target` 인 `i` 는 전부 `lo` 왼쪽에 있고, `a[i] >= target` 인 `i` 는 전부 `hi`(제외) 오른쪽 경계까지 남아 있다.

이 불변식만 지키면 "몇 번째 인덱스에서 멈추는가"를 고민할 필요가 없다. `lo == hi`가 되는 순간 그게 곧 답이다.

```python title="lower_bound.py — bisect_left와 동치인 구현"
def lower_bound(a, target):
    """a[i] >= target 을 만족하는 최소 i."""
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < target:
            lo = mid + 1      # mid는 target보다 작다 -> 확실히 답이 아니다
        else:
            hi = mid          # mid가 답일 수도 있다 -> 버리지 않는다
    return lo
```

`mid = (lo + hi) // 2` 는 항상 `lo` 이상, `hi` 미만이다. 매 반복마다 `lo`와 `hi`의 간격이 최소 절반으로 줄어든다는 것도 이 불변식에서 바로 나온다.

::: danger 흔한 off-by-one: hi를 mid-1이 아니라 mid로 잘못 줄이는 경우
반열린 구간 `[lo, hi)`을 쓰면서 실수로 닫힌 구간 스타일 코드를 섞으면 무한 루프가 난다.

```python
# ❌ 반열린 구간인데 hi = mid - 1 을 섞어 썼다
lo, hi = 0, len(a)
while lo < hi:
    mid = (lo + hi) // 2
    if a[mid] < target:
        lo = mid + 1
    else:
        hi = mid - 1        # mid도 답일 수 있는데 통째로 버린다 -> 답을 잃어버린다
```

반대로 **닫힌 구간** `[lo, hi]` 스타일(`hi = len(a) - 1`로 시작)을 쓸 거면 끝까지 그 스타일을 유지해야 한다. 두 스타일을 한 함수 안에서 섞는 순간 경계 조건이 깨진다. **하나를 정해서 항상 그것만 써라.** 이 책은 반열린 구간으로 통일한다.
:::

`lower_bound`가 맞는지는 눈으로 확인하는 게 아니라 실행해서 확인해야 한다. 표준 라이브러리 `bisect.bisect_left`와 무작위로 대조해 보자.

```python title="검증: 2000회 무작위 대조"
import random
import bisect

random.seed(0)
for _ in range(2000):
    n = random.randint(0, 30)
    a = sorted(random.randint(0, 10) for _ in range(n))
    target = random.randint(-2, 12)
    assert lower_bound(a, target) == bisect.bisect_left(a, target)
```

```text nolines
(assert 에러 없이 종료 — 2000회 전부 bisect_left와 일치)
```

## `bisect_left` 와 `bisect_right`, 실측으로 확인하는 차이

파이썬 표준 라이브러리 `bisect` 모듈이 이걸 이미 구현해 준다. 그런데 `bisect_left`와 `bisect_right`의 차이를 "왼쪽/오른쪽"이라는 이름만으로 짐작하면 반드시 헷갈린다. 직접 찍어서 확인하자.

```pyrepl
>>> import bisect
>>> a = [1, 3, 3, 3, 5, 7, 9]
>>> bisect.bisect_left(a, 3)
1
>>> bisect.bisect_right(a, 3)
4
>>> bisect.bisect_left(a, 4)
4
>>> bisect.bisect_right(a, 4)
4
```

값이 배열에 없을 때(`4`)는 `bisect_left`와 `bisect_right`가 같은 위치를 가리킨다 — 삽입할 자리가 하나뿐이기 때문이다. 값이 여러 개 있을 때(`3`)는 갈린다.

- **`bisect_left(a, x)`**: `x`를 넣어도 정렬이 깨지지 않는 **가장 왼쪽** 위치. 즉 "`a[i] >= x`인 최소 `i`" — `lower_bound`.
- **`bisect_right(a, x)`**: `x`를 넣어도 정렬이 깨지지 않는 **가장 오른쪽** 위치. 즉 "`a[i] > x`인 최소 `i`" — `upper_bound`.

두 값의 차이가 곧 배열 안에 있는 `x`의 개수다.

```pyrepl
>>> bisect.bisect_right(a, 3) - bisect.bisect_left(a, 3)
3
```

::: cote `in` 대신 개수를 세야 하는 문제
"몇 개 있는가", "이 범위에 몇 개인가" 류의 문제에서 정렬된 배열 + `bisect_right - bisect_left`는 $O(\log n)$에 답이 나온다. 반면 `list.count(x)`는 내부적으로 전체를 훑는 $O(n)$이다. 배열이 이미 정렬돼 있다면(혹은 한 번 정렬해 둘 수 있다면) 절대 `count`를 쓰지 마라.
:::

값을 정렬된 자리에 끼워 넣는 `insort_left` / `insort_right`도 같은 원리다.

```pyrepl
>>> b = [1, 3, 5, 7]
>>> bisect.insort_left(b, 4)
>>> b
[1, 3, 4, 5, 7]
```

::: perf insort는 탐색은 로그, 삽입은 선형이다
`insort`가 끼울 위치를 찾는 건 $O(\log n)$이지만, 리스트 중간에 원소를 끼워 넣는 것 자체가 뒤쪽 원소를 전부 한 칸씩 밀어야 하는 $O(n)$ 연산이다. [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 본 `list.insert`와 같은 비용이다. **정렬된 상태를 유지하면서 삽입을 자주 해야 한다면 `bisect`가 아니라 힙이나 균형 트리 계열 구조를 고려하라.** 이건 [7.8 힙과 우선순위 큐](#/heap)에서 이어진다.
:::

3.10부터는 `key` 매개변수로 튜플이나 객체의 특정 필드를 기준으로 이분 탐색할 수 있다. 배열 자체를 변형하지 않아도 된다는 뜻이다.

```pyrepl
>>> people = [("alice", 20), ("bob", 25), ("carol", 25), ("dave", 30)]
>>> bisect.bisect_left(people, 25, key=lambda p: p[1])
1
>>> people[1]
('bob', 25)
>>> bisect.bisect_right(people, 25, key=lambda p: p[1])
3
```

::: danger bisect는 정렬 여부를 확인하지 않는다
`bisect` 계열 함수는 배열이 정렬돼 있다고 **가정**할 뿐, 검사하지 않는다. 정렬이 안 된 배열에 쓰면 에러 없이 **조용히 틀린 값**을 반환한다.

```pyrepl
>>> a = [5, 1, 9, 3, 7]      # 정렬 안 됨
>>> bisect.bisect_left(a, 3)
2
>>> a[2]
9                              # 3이 아니다!
>>> 3 in a
True                           # 실제로는 배열에 있는데도 못 찾은 셈
```

에러가 나면 차라리 낫다. **틀린 답이 조용히 나오는 게 이분 탐색 버그의 가장 위험한 형태다.** 입력이 정렬돼 있다는 전제를 코드에서든 주석에서든 항상 명시하라.
:::

## 직접 구현 vs `bisect` 모듈, 언제 무엇을

`bisect`가 있는데 왜 직접 구현을 배우는가. 두 가지 이유다.

1. **`lower_bound`/`upper_bound`가 아닌 조건**으로 이분 탐색해야 할 때가 많다. 곧 볼 매개변수 탐색이 그렇다 — 배열에서 값을 찾는 게 아니라 "어떤 조건을 만족하는 최대/최소 정수"를 찾는다. 이건 `bisect` 모듈로 표현이 안 된다. 직접 짜야 한다.
2. **성능 자체도 무시할 수 없다.** `bisect`는 C로 구현돼 있고, 직접 짠 파이썬 루프보다 빠르다.

```python title="같은 로직, 파이썬 루프 vs C 구현"
import bisect, timeit

n = 1_000_000
a = list(range(n))
target = n - 1

t_manual = timeit.timeit(lambda: lower_bound(a, target), number=2000)
t_bisect = timeit.timeit(lambda: bisect.bisect_left(a, target), number=2000)
print(f"manual={t_manual:.5f}s  bisect={t_bisect:.5f}s  배수={t_manual / t_bisect:.1f}x")
```

```text nolines
manual=0.00157s  bisect=0.00020s  배수=7.7x
```

(Python 3.14.5 / Windows 기준 실측.) 둘 다 $O(\log n)$이라 이 배수는 $n$이 커져도 거의 그대로다. 즉 **알고리즘 등급은 같지만 상수가 다르다.** [7.1 시간·공간 복잡도](#/complexity)에서 말한 "상수의 무게"가 여기서도 나타난다. **배열에서 값이나 삽입 위치를 찾는 표준적인 경우라면 `bisect`를 써라.** 조건이 배열 인덱싱을 벗어나면 직접 짠다.

## 매개변수 탐색: 정답 자체를 이분 탐색으로 찾는다

여기부터가 코딩테스트에서 이분 탐색이 진짜로 쓰이는 자리다. **매개변수 탐색**(parametric search)은 "이 배열에서 값 X를 찾아라"가 아니라, **"조건 P(x)를 만족하는 최댓값(또는 최솟값) x를 찾아라"** 형태의 문제를 이분 탐색으로 푸는 기법이다.

핵심 전제는 하나다. **P(x)가 단조(monotonic)여야 한다.** 즉 어떤 경계값을 기준으로, 그 이하(또는 이상)에서는 전부 참이고 반대쪽은 전부 거짓이어야 한다. 이 성질이 없으면 이분 탐색으로 정답을 찾을 수 없다 — 절반을 버리는 근거 자체가 사라지기 때문이다.

::: cote 매개변수 탐색을 알아보는 신호
문제에 "최대 ~를 구하시오", "~를 최소화하는 값을 구하시오" 같은 표현이 있고, **후보가 되는 값을 하나 정했을 때 "이 값이 가능한가"를 판정하는 함수를 빠르게 만들 수 있다면** 매개변수 탐색을 의심하라. 정답 자체를 순회하며 매번 확인하면 느리지만($O(정답 범위 \times 판정 비용)$), 정답 범위를 이분 탐색하면 $O(\log(정답 범위) \times 판정 비용)$으로 줄어든다.
:::

백준 2805(나무 자르기) 스타일의 문제로 확인해 보자. 나무 여러 그루의 높이가 주어지고, 절단기 높이 `h`로 자르면 `h`보다 높은 부분만 잘려서 모인다. 필요한 나무 양 이상을 확보하는 **최대 `h`**를 구하라.

브루트포스는 `h`를 0부터 최댓값까지 하나씩 올려보며 확인한다. `h` 후보가 $10^9$까지 갈 수 있는 문제라면 이건 그대로 시간 초과다. 반면 "이 `h`로 자르면 충분한가?"는 배열을 한 번 훑으면($O(n)$) 판정되고, **`h`가 클수록 모이는 양은 단조 감소**한다 — 그래서 이분 탐색이 통한다.

```python title="parametric_search.py"
def wood_collected(heights, h):
    return sum(x - h for x in heights if x > h)


def max_cut_height(heights, need):
    lo, hi = 0, max(heights)
    ans = 0
    while lo <= hi:                       # 여기는 닫힌 구간 [lo, hi] 스타일
        mid = (lo + hi) // 2
        if wood_collected(heights, mid) >= need:
            ans = mid                     # mid는 가능하다 -> 기록해 두고
            lo = mid + 1                  # 더 큰 값도 가능한지 본다
        else:
            hi = mid - 1
    return ans
```

이 함수는 반열린 구간이 아니라 **닫힌 구간** `[lo, hi]`을 쓴다. "정답일 수도 있는 mid를 즉시 채택하되, 더 나은 답이 있는지 계속 찾는다"는 패턴은 닫힌 구간 + 별도의 `ans` 변수로 표현하는 편이 자연스럽다. 반열린 구간의 `lower_bound`와 코드 모양이 다른 건 실수가 아니라 **문제 종류가 다르기 때문**이다 — 배열 인덱스를 찾는 게 아니라 정수 하나를 찾는 것이라 구간의 의미 자체가 다르다.

```python
heights = [20, 15, 10, 17]
need = 7
print(max_cut_height(heights, need))   # 15
```

```text nolines
15
```

검산: `h=15`일 때 `20-15=5`, `17-15=2`, 합이 `7` — 정확히 필요량과 같다. `h=16`이면 `20-16=4`, `17-16=1`, 합이 `5`로 부족하다. 그러니 `15`가 맞다. 브루트포스와도 대조해 확인했다.

```python title="검증: 3000회 무작위 대조"
import random

def max_cut_height_brute(heights, need):
    best = -1
    for h in range(max(heights) + 1):
        if wood_collected(heights, h) >= need:
            best = h
    return best

random.seed(2)
for _ in range(3000):
    n = random.randint(1, 8)
    heights = [random.randint(1, 30) for _ in range(n)]
    need = random.randint(0, sum(heights))
    assert max_cut_height(heights, need) == max_cut_height_brute(heights, need)
```

```text nolines
(assert 에러 없이 종료 — 3000회 전부 브루트포스와 일치)
```

::: tip 매개변수 탐색 템플릿
1. 정답이 될 수 있는 값의 **범위**를 정한다 (`lo`, `hi`).
2. "값 `x`가 조건을 만족하는가?"를 판정하는 함수 `ok(x)`를 만든다. 이게 단조인지 먼저 확인한다.
3. 이분 탐색하면서, `ok(mid)`가 참이면 정답 후보로 기록하고 탐색 범위를 정답이 더 좋은 쪽으로 좁힌다.
4. 거짓이면 반대쪽으로 좁힌다.

`ok` 함수를 만드는 것과 그게 단조인지 증명하는 것, 이 두 가지가 실제 어려움이다. 이분 탐색 코드 자체는 거의 항상 같은 모양이다. [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 이 판단을 더 훈련한다.
:::

## 회전 정렬 배열에서 탐색

정렬된 배열을 통째로 회전시킨 배열(예: `[15, 17, 20, 1, 3, 10]`)에서도 이분 탐색이 된다. 배열 전체는 정렬돼 있지 않지만, **중간을 기준으로 자르면 둘 중 한쪽은 반드시 정렬돼 있다.** 그 정렬된 쪽을 기준으로 목표가 그 안에 있는지 판단해서 방향을 정하면 된다.

```python title="rotated_search.py"
def search_rotated(a, target):
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == target:
            return mid
        if a[lo] <= a[mid]:               # 왼쪽 절반이 정렬돼 있다
            if a[lo] <= target < a[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:                              # 오른쪽 절반이 정렬돼 있다
            if a[mid] < target <= a[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1
```

`a[lo] <= a[mid]`로 어느 쪽이 정렬됐는지 먼저 판정하는 게 이 알고리즘의 전부다. 정렬된 쪽이 정해지면 그 쪽 범위 안에 `target`이 있는지는 일반 비교로 바로 알 수 있다. 무작위 회전 배열 5000개로 대조했다.

```python title="검증: 5000회 무작위 대조 (브루트포스는 in 연산)"
import random

random.seed(1)
mismatches = 0
for _ in range(5000):
    n = random.randint(1, 12)
    base = sorted(random.sample(range(50), n))
    k = random.randint(0, n - 1)
    rotated = base[k:] + base[:k]
    target = random.choice(rotated) if rotated and random.random() < 0.7 else random.randint(-5, 55)
    got = search_rotated(rotated, target)
    if (target in rotated) != (got != -1 and rotated[got] == target):
        mismatches += 1
print(mismatches)
```

```text nolines
0
```

::: warn 회전 배열에서 흔한 실수
`a[lo] <= a[mid]`를 `<`로 쓰면 `lo == mid`인 길이 1~2짜리 구간에서 왼쪽 정렬 여부 판정이 틀린다. 경계에 원소가 하나뿐일 때를 항상 손으로 그려서 확인하라. 이런 경계 케이스가 바로 이분 탐색 버그의 8할이다.
:::

## 요약

- 정렬된 배열에서 값을 찾을 땐 선형 탐색을 쓰지 마라. `bisect`는 100만 원소에서도 수십 마이크로초다.
- `bisect_left`는 "이 값 이상이 시작하는 자리", `bisect_right`는 "이 값을 넘는 자리"다. 값이 배열에 없으면 둘은 같다.
- 이분 탐색은 **탐색 구간이 무엇을 의미하는지**(반열린 `[lo, hi)`인지 닫힌 `[lo, hi]`인지) 먼저 정하고, 한 함수 안에서 한 스타일만 써라. 섞으면 무한 루프나 답 누락으로 이어진다.
- 표준적인 삽입 위치 탐색은 `bisect` 모듈을 써라. 조건이 배열 인덱싱을 벗어나면(매개변수 탐색 등) 직접 구현해야 한다.
- 매개변수 탐색은 "답이 될 값의 범위"를 이분 탐색한다. 전제 조건은 판정 함수의 **단조성**이다.
- 회전 정렬 배열은 중간을 기준으로 항상 한쪽은 정렬돼 있다는 사실을 이용한다.
- `bisect`는 정렬 여부를 검사하지 않는다. 정렬 안 된 배열에 쓰면 조용히 틀린다.

::: quiz 연습문제
1. `bisect.bisect_left([1, 2, 2, 2, 5], 2)`와 `bisect.bisect_right([1, 2, 2, 2, 5], 2)`의 값을 먼저 예측하고 실행해서 확인하라.
2. 정렬된 배열 `a`에서 값 `x`가 **정확히 몇 개** 들어 있는지 `bisect`만으로 $O(\log n)$에 세는 코드를 써라.
3. 다음 코드는 왜 무한 루프에 빠지는가? 반열린 구간의 불변식 관점에서 설명하고 고쳐라.

   ```python
   def buggy_lower_bound(a, target):
       lo, hi = 0, len(a)
       while lo < hi:
           mid = (lo + hi) // 2
           if a[mid] < target:
               lo = mid
           else:
               hi = mid
       return lo
   ```

4. 오름차순으로 정렬된 두 정수 배열이 주어졌을 때, 두 배열을 합친 것의 중앙값을 $O(\log(\min(m, n)))$에 구하는 방법을 매개변수 탐색 관점에서 설계해 보라. (힌트: "왼쪽에 몇 개를 가져올 것인가"를 이분 탐색한다.)
5. 회전 정렬 배열 탐색 코드에서 `a[lo] <= a[mid]` 대신 `a[lo] < a[mid]`로 바꾸면 어떤 입력에서 틀리는지 반례를 하나 만들어 실행으로 확인하라.
:::

**다음 절**: [7.6 해시](#/hashing) — dict와 set이 이분 탐색보다도 빠른 $O(1)$ 조회를 어떻게 해내는가.
