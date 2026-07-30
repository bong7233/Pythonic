# 11.8 함수 완성형 테스트 대응

::: lead
해외 플랫폼 문제는 백지로 시작하지 않는다. 화면에는 이미 `def solve(nums, k):` 가 적혀 있고 지문은 영문이다. 입력 파싱도 출력 형식도 없다. 그래서 쉬워 보이는데, 실제로 떨어지는 지점은 알고리즘이 아니다. **반환 타입 하나, 부등호 한 글자, 지문의 대괄호 하나**다. 이 절은 알고리즘을 다루지 않는다. 영문 지문에서 밑줄 칠 자리, 시그니처가 강제하는 계약, 반드시 만들어야 하는 엣지케이스, 그리고 제출 버튼을 누르기 전 6분 동안 돌리는 자체 검증 루틴을 다룬다.
:::

## 예시는 다 통과했는데 오답이다

문제부터 보자. 지문은 이렇게 생겼다. 실제 함수 완성형 문제의 어투를 그대로 따랐다.

```text nolines
A parking garage records how many cars entered during each hour of operation.

You are given a 0-indexed integer array `counts`, where `counts[i]` is the number of
cars that entered during hour `i`, and an integer `k`.

An hour `i` is a *local peak* if `counts[i]` is strictly greater than `counts[j]` for
every index `j` in the range `[i - k, i + k]` such that `j != i` and `j` is a valid
index of `counts`.

Return an array containing the indices of all local peaks in increasing order.
If there are no local peaks, return an empty array.

Example 1:
  counts = [3, 1, 4, 7, 5, 9, 2, 6], k = 2   ->   [5]
Example 2:
  counts = [2, 8, 1], k = 1                  ->   [1]

Constraints:
  1 <= len(counts) <= 10**5
  0 <= k <= 10**5
  0 <= counts[i] <= 10**9
  All values in counts are distinct.
```

지문을 곧이곧대로 옮기면 이런 코드가 나온다. 문장 구조가 그대로 코드 구조가 됐다.

```python title="첫 시도 — 지문을 그대로 옮겼다"
def local_peaks(counts, k):
    n = len(counts)
    out = []
    for i in range(n):
        if all(counts[i] > counts[j] for j in range(i - k, i + k + 1)
               if j != i and j < n):          # "j 가 유효한 인덱스일 때"
            out.append(i)
    return out
```

예시 두 개를 돌린다.

```text nolines
local_peaks([3, 1, 4, 7, 5, 9, 2, 6], 2)  ->  [5]      기대 [5]
local_peaks([2, 8, 1], 1)                 ->  [1]      기대 [1]
```

둘 다 맞다. 제출하면 **오답**이다.

원인은 `j < n` 이다. 이 조건은 위쪽 경계만 막는다. 아래쪽에서 `j` 가 음수가 되면 파이썬은 예외를 내지 않고 **배열 뒤쪽에서 원소를 꺼내 온다.**

```text nolines
  i = 0, k = 2   ─▶  range(-2, 3) = -2  -1  0  1  2
                                    │   │
                                    │   └──▶ counts[-1]        <- 맨 뒤 원소!
                                    └──────▶ counts[-2]        <- 뒤에서 두 번째!
```

배열의 맨 앞 시간대를 판정할 때 **맨 뒤 시간대와 비교하고 있다.** `counts = [5, 1, 2, 9]`, `k = 2` 로 확인된다.

```pyrepl
>>> counts = [5, 1, 2, 9]
>>> counts[-2], counts[-1]
(2, 9)
>>> all(counts[0] > counts[j] for j in range(-2, 3) if j != 0 and j < 4)
False
```

`5` 는 왼쪽에 아무것도 없으므로 `k=2` 에서 local peak인데(오른쪽의 `1`, `2` 보다 크다) `counts[-1]` 이 `9` 라서 탈락했다. 정답은 `[0, 3]`, 이 코드는 `[3]` 을 낸다.

::: danger 음수 인덱스는 k 가 작을 때 조용히 틀리고 k 가 클 때 터진다
같은 버그가 두 얼굴을 갖는다. `k` 가 배열 길이보다 작으면 위처럼 **예외 없이 틀린 답**이 나온다. `k` 가 배열 길이를 넘으면 `j` 가 `-n` 보다 더 작아져 그때는 예외가 난다.

```pyrepl
>>> counts = [7]
>>> [counts[j] for j in range(-5, 6) if j != 0 and j < 1]
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
IndexError: list index out of range
```

인덱스 범위를 만들 때는 **`range` 에 넣기 전에 양쪽을 자른다.** `range(max(0, i - k), min(n - 1, i + k) + 1)` 이다. `if j < n` 처럼 루프 안에서 걸러내는 방식은 아래쪽을 잊게 만든다. 파이썬의 음수 인덱스는 편리한 기능이지만 격자·구간 문제에서는 **경계 검사를 무력화하는 함정**이다([11.4](#/array-grid)).
:::

이 절의 나머지는 전부 하나의 질문에 대한 답이다. **예시를 통과한 코드가 왜 틀렸는지, 제출하기 전에 어떻게 알아내는가.**

## 함수 완성형이 표준 입력형과 다른 네 가지

차이를 정확히 알아야 어디를 방어할지 정해진다.

| | 표준 입력형 | 함수 완성형 |
| --- | --- | --- |
| 입력 | `input()` 으로 직접 파싱 | 인자로 들어온다. 파싱 없음 |
| 출력 | `print` 로 형식 맞춰 출력 | `return`. **타입이 곧 형식** |
| 지문 | 대개 한국어 | 대개 영문 |
| 호출 | 프로세스당 한 번 | 한 프로세스에서 케이스마다 **여러 번** |

첫 두 줄은 좋은 소식이다. 입출력 형식 실수가 사라진다([8.2](#/io-optimize)). 나머지 두 줄이 이 절이 존재하는 이유다.

**네 번째 줄이 특히 중요하다.** 대부분의 채점기는 한 프로세스에서 케이스를 연달아 호출한다. 그렇지 않은 채점기도 있지만, **그렇다고 가정하는 편이 언제나 안전하다.** 이 가정 하나가 전역 변수와 가변 기본값을 버그로 바꾼다.

## 영문 지문 — 밑줄 칠 자리는 여섯 곳이다

영어를 잘하는 것과 문제를 정확히 읽는 것은 다르다. 함수 완성형 지문은 형식이 굳어 있어서 **틀리는 자리도 굳어 있다.** 지문을 처음 훑을 때 이 여섯 곳만 찾아라.

1. **반환 문장** — 무엇을, 어떤 타입으로, 어떤 순서로. 대개 `Return ...` 한 문장이다.
2. **부등호 단어** — `strictly`, `at most`, `at least`, `non-decreasing`.
3. **구간의 대괄호** — `[a, b]` 는 양 끝 포함이다. 파이썬 `range` 는 아니다.
4. **없을 때** — `If there are no ..., return ...`. `-1` 인가 `[]` 인가.
5. **Constraints 의 상한** — 최악 크기. 알고리즘 선택이 여기서 정해진다.
6. **`guaranteed` / `distinct` 문장** — 검사하지 않아도 되는 것들.

### 표현 → 코드 변환표

왼쪽 표현을 보면 오른쪽이 즉시 나와야 한다. **뜻을 아는 것으로는 부족하다. 코드의 어느 글자가 되는지를 알아야 한다.**

| 영문 표현 | 코드에서 무엇이 되는가 |
| --- | --- |
| `0-indexed` | 그대로. `1-indexed` 면 모든 인덱스에 `-1` 보정 |
| `in the range [i - k, i + k]` | `range(max(0, i - k), min(n - 1, i + k) + 1)` — **`+1` 을 잊는 자리, 그리고 양쪽을 클램프하는 자리** |
| `strictly greater` | `>`. `>=` 로 쓰면 동점에서 갈린다 |
| `non-decreasing` | `a[i] <= a[i + 1]`. "증가"가 아니라 **"감소하지 않음"** |
| `at most k` / `at least k` | `<= k` / `>= k` |
| `subarray` / `substring` | **연속**이다. 슬라이스 |
| `subsequence` | 건너뛸 수 있다. 조합·DP |
| `distinct` | 동점 처리 코드를 **짜지 마라** |
| `in-place` | `nums[:] = ...`. 새 리스트를 반환하면 오답 |
| `return an empty array` | `[]`. `None` 이 아니다 |
| `modulo 10**9 + 7` | 반환 직전 `% (10**9 + 7)`. 파이썬은 안 넘쳐서 잊는다 |
| `indices outside the array are ignored` | **잘라낸다.** 순환이 아니다 |
| `It is guaranteed that ...` | 검증 코드를 짜지 마라 |

::: warn `non-decreasing` 과 `increasing` 은 다른 조건이다
`increasing` 은 `a[i] < a[i+1]`, `non-decreasing` 은 `a[i] <= a[i+1]` 이다. 등호 하나 차이지만 `[1, 1, 2]` 에서 답이 갈린다. 영문 지문은 이 구분을 **엄격하게 지켜서** 쓴다. 한국어로 옮기면서 "정렬된"으로 뭉개는 순간 정보가 사라진다.

같은 계열로 `positive`(> 0)와 `non-negative`(>= 0)가 있다. Constraints 에 `0 <= counts[i]` 가 적혀 있으면 **0이 들어온다는 뜻**이다. 초기값을 `0` 으로 잡은 코드가 여기서 무너진다.
:::

::: note Constraints 를 읽으면 코드가 짧아진다
위 문제의 `All values in counts are distinct.` 는 선물이다. 동점 처리를 아예 지울 수 있다. 그리고 "창의 최댓값과 같으면 local peak"이라는 훨씬 간단한 판정이 성립한다 — 값이 서로 다르니 최댓값은 하나뿐이다.

`1 <= len(counts)` 도 읽어라. **빈 배열은 들어오지 않는다.** 빈 입력 방어 코드를 짜는 5분이 절약되고, 더 중요하게는 빈 입력용 특수 분기가 만들 버그가 사라진다.

이 지문에는 재미있는 것이 하나 더 있다. `If there are no local peaks, return an empty array.` 는 **도달할 수 없는 문장**이다. 배열 전체의 최댓값은 자기 창 안에서 항상 최대이므로 언제나 local peak이다. 길이 1~10, `k` 0~12 범위에서 무작위 20만 건을 돌려도 빈 결과는 한 번도 나오지 않는다. 이런 문장을 발견하는 것 자체가 지문을 정확히 읽었다는 신호다. 다만 **그렇다고 `[]` 반환 경로를 지우지는 마라.** 판단이 틀렸을 때의 비용이 아낀 두 줄보다 크다.
:::

## 반환 타입 하나가 0점을 만든다

여기가 함수 완성형 특유의 실패 지점이다. 표준 입력형에서는 `print` 가 타입을 문자열로 눌러 버리니 이 문제가 없다. 함수 완성형은 **반환한 객체를 채점기가 직접 비교**한다.

그리고 파이썬은 이 실수를 **당신 대신 감춰 준다.** 직접 `assert` 로 확인해도 통과하기 때문이다.

```pyrepl
>>> True == 1
True
>>> [3, True] == [3, 1]
True
>>> {"ok": True} == {"ok": 1}
True
>>> 10 / 2
5.0
>>> [10 / 2] == [5]
True
```

`bool` 은 `int` 의 하위 클래스라 `True == 1` 이다. `/` 는 항상 `float` 를 낸다. 그래서 **로컬에서는 전부 통과하고, 타입을 엄격하게 보는 채점기에서만 떨어진다.** 개수를 세는 함수에서 `/` 를 한 번 쓰면 반환값이 `5.0` 이 되고, 그 함수의 `assert` 는 여전히 초록불이다.

::: danger 타입이 달라도 `==` 가 통과하는 자리와, 눈으로 못 보는 자리
다섯 가지를 한 표에 놓되 **두 부류를 구분해서** 봐라. 위의 둘은 `==` 자체가 통과시킨다. 아래 셋은 `==` 가 잡을 수 있는데도 테스트를 그렇게 안 짜서 못 잡는다.

| 실제로 반환한 것 | 기대한 것 | 어떻게 빠져나가는가 |
| --- | --- | --- |
| `5.0` | `5` | **`==` 가 통과시킨다.** `5.0 == 5` 가 `True` |
| `True` | `1` | **`==` 가 통과시킨다.** `bool` 은 `int` 의 하위 클래스 |
| `(0, 3)` | `[0, 3]` | `==` 는 잡는다(`False`). 기대값을 `(0, 3)` 으로 적으면 못 잡는다 |
| `"True"` | `"true"` | `==` 는 잡는다(`'True' != 'true'`). 눈으로 훑으면 대소문자가 안 보인다 |
| `None` | `[]` | `==` 는 잡는다(`False`). 답이 없는 케이스를 안 돌려 봐서 못 잡는다 |

특히 네 번째가 함정이다. 영문 플랫폼이 문자열 `"true"` 를 요구할 때 `str(True)` 를 쓰면 `'True'` 가 나온다.

```pyrepl
>>> str(True)
'True'
>>> str(True).lower()
'true'
>>> import json
>>> json.dumps({"found": True})
'{"found": true}'
```

세 번째 줄이 힌트다. **채점기가 값을 JSON으로 직렬화해서 비교한다면 소문자 `true` 가 된다.** 그래서 불리언을 반환해야 하는 문제에서 문자열을 반환하면 절대 안 맞는다. 지문이 `Return true if ...` 라고 쓰여 있어도 반환할 것은 **파이썬 `bool`** 이다. 시그니처의 `-> bool` 이 사양이다.
:::

### 값과 타입을 함께 보는 비교 함수

`assert got == want` 는 위의 다섯 가지 중 `5.0` 과 `True` 를 놓친다. 나머지 셋은 기대값을 제대로 적었다면 `==` 로도 잡히지만, 기대값을 튜플로 적거나 답이 없는 케이스를 아예 만들지 않아서 실제로는 통과해 버린다. **놓치는 이유가 둘로 갈리니 방어도 둘이다** — 타입을 직접 보게 만들고, 기대값을 사람이 손으로 적지 않게 만든다. 앞쪽을 맡는 비교 함수를 하나 만들어 두고 문제마다 재사용한다. **이게 이 절에서 가져갈 도구 하나다.**

```python title="strict_eq — 타입까지 재귀적으로 대조한다"
def strict_eq(got, want, path="result"):
    """값과 타입이 모두 같으면 None, 다르면 어디가 다른지 문자열로."""
    if type(got) is not type(want):
        return f"{path}: 타입 {type(got).__name__} (기대 {type(want).__name__})"
    if isinstance(want, (list, tuple)):
        if len(got) != len(want):
            return f"{path}: 길이 {len(got)} (기대 {len(want)})"
        for i, (g, w) in enumerate(zip(got, want)):
            if msg := strict_eq(g, w, f"{path}[{i}]"):
                return msg
        return None
    return None if got == want else f"{path}: 값 {got!r} (기대 {want!r})"
```

`type(got) is not type(want)` 가 핵심이다. `isinstance` 를 쓰면 `bool` 이 `int` 를 통과한다. 원소 하나까지 내려가므로 리스트 안에 섞인 `True` 도 잡힌다.

```text nolines
[1, 2, 3]    vs [1, 2, 3]  -> OK
(0, 3)       vs [0, 3]     -> result: 타입 tuple (기대 list)
[0, True]    vs [0, 1]     -> result[1]: 타입 bool (기대 int)
5.0          vs 5          -> result: 타입 float (기대 int)
None         vs []         -> result: 타입 NoneType (기대 list)
true         vs True       -> result: 타입 str (기대 bool)
[0, 3, 5]    vs [0, 3]     -> result: 길이 3 (기대 2)
[0, 5, 3]    vs [0, 3, 5]  -> result[1]: 값 5 (기대 3)
```

마지막 줄을 보라. **순서가 틀린 것도 잡는다.** `in increasing order` 를 놓치고 `set` 을 리스트로 바꿔 반환하면 여기서 걸린다.

::: warn 정수 나눗셈과 반올림은 언어마다 규칙이 다르다
함수 완성형 문제의 모범 답안은 대개 C++이나 자바 기준으로 만들어진다. 두 언어의 정수 나눗셈은 **0 쪽으로 자르고**, 파이썬 `//` 는 **아래로 내린다.** 음수에서 갈린다.

```pyrepl
>>> -7 // 2
-4
>>> int(-7 / 2)
-3
>>> -7 % 3
2
```

`-7 % 3` 이 `2` 인 것도 같은 이유다(C에서는 `-1`). 그리고 파이썬 `round` 는 **은행가 반올림**이라 `.5` 를 짝수 쪽으로 보낸다.

```pyrepl
>>> round(2.5), round(3.5), round(-2.5)
(2, 4, -2)
>>> from decimal import Decimal, ROUND_HALF_UP
>>> int(Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP))
3
```

지문에 `rounded half up` 이나 `truncated toward zero` 라고 쓰여 있으면 **파이썬 기본 연산자를 쓰면 안 된다.** 수치 연산의 규칙 자체는 [1.2](#/numbers)에 있다.
:::

## 주어진 시그니처는 계약이다

시그니처는 예시 코드가 아니라 **채점기와의 인터페이스**다. 임의로 고치면 알고리즘이 맞아도 0점이다.

### 인자 이름을 바꾸지 마라

채점기가 키워드 인자로 호출할 수 있다. 그러면 이름 변경이 즉시 `TypeError` 가 된다.

```pyrepl
>>> def local_peaks(arr, dist):
...     return []
...
>>> local_peaks(counts=[3, 1, 4], k=1)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: local_peaks() got an unexpected keyword argument 'counts'
```

`arr`, `dist` 가 `counts`, `k` 보다 나은 이름이라 해도 바꾸지 마라. 순서를 바꾸는 것은 더 위험하다 — 위치 인자로 호출하면 **예외 없이** 인자가 뒤바뀐 채 실행된다.

::: tip 보조 인자가 필요하면 내부 함수로 내려라
재귀 보조 인자나 메모 딕셔너리가 필요할 때 시그니처에 인자를 추가하고 싶어진다. 기본값을 주면 채점기의 2-인자 호출이 깨지지는 않는다. 그래도 하지 마라.

```python
# ❌ 동작은 하지만 계약을 늘렸다. 인자 개수·순서를 다시 확인해야 한다
def local_peaks(counts, k, memo=None, depth=0): ...

# ✅ 시그니처를 아예 건드리지 않는다
def local_peaks(counts, k):
    def walk(i, depth): ...
    return [i for i in range(len(counts)) if walk(i, 0)]
```

내부 함수는 `counts` 와 `k` 를 클로저로 그냥 읽는다([1.10](#/functions)). 인자를 넘기지 않으니 순서를 틀릴 일도 없고, 바로 뒤에서 볼 **상태 누출**도 구조적으로 막힌다.
:::

### `in-place` 는 대입이 아니라 변경이다

지문이 `Modify nums in-place` 라고 쓰면 **호출한 쪽의 리스트가 바뀌어야 한다.** 이름에 새 리스트를 대입하는 것은 아무것도 바꾸지 않는다([1.1](#/objects-names)).

```pyrepl
>>> def compact(nums):
...     nums = [x for x in nums if x != 0]
...
>>> data = [1, 0, 2, 0, 3]
>>> compact(data)
>>> data
[1, 0, 2, 0, 3]
>>> def compact(nums):
...     nums[:] = [x for x in nums if x != 0]
...
>>> data = [1, 0, 2, 0, 3]
>>> compact(data)
>>> data
[1, 2, 3]
```

`nums[:] = ...` 가 슬라이스 대입이고, 이것만이 원본을 바꾼다. `nums.sort()` 는 제자리, `sorted(nums)` 는 새 리스트라는 구분도 같은 이야기다([11.6](#/sorting-as-tool)).

### 케이스 사이로 상태가 새어 나간다

채점기가 같은 프로세스에서 여러 번 부른다는 사실이 여기서 청구서로 돌아온다. **함수 밖에 사는 것은 전부 케이스 사이에 살아남는다.**

가변 기본값이 대표적이다.

```pyrepl
>>> def uniq(rows, out=[]):
...     for r in rows:
...         if r not in out:
...             out.append(r)
...     return out
...
>>> uniq(["A3", "B1"])
['A3', 'B1']
>>> uniq(["C7"])
['A3', 'B1', 'C7']
```

두 번째 호출이 첫 번째 호출의 결과를 끌고 왔다. **한 번만 테스트하면 절대 안 걸린다.** 기본값은 함수 정의 시점에 딱 한 번 만들어지기 때문이다([1.10](#/functions)).

::: danger 전역 상태에 얹은 `@cache` 는 두 번째 케이스부터 거짓말을 한다
더 잡기 어려운 형태다. 격자 문제를 이렇게 짰다고 하자. 흔한 모양이다.

```python title="paths_bug.py — 두 번째 호출부터 틀린다"
from functools import cache

GRID = []

@cache
def _paths(r, c):
    if GRID[r][c] == "#":
        return 0
    if r == 0 and c == 0:
        return 1
    total = 0
    if r:
        total += _paths(r - 1, c)
    if c:
        total += _paths(r, c - 1)
    return total


def count_paths(grid):
    global GRID
    GRID = grid
    return _paths(len(grid) - 1, len(grid[0]) - 1)


print(count_paths(["..", ".."]))     # 2
print(count_paths([".#", ".."]))     # 1 이어야 한다
print(count_paths(["..", ".."]))     # 2
```

```text nolines
2
2
2
```

두 번째 격자는 답이 `1` 인데 `2` 가 나왔다. 캐시 키는 `(r, c)` 뿐이고 **`GRID` 는 키에 없다.** 첫 케이스의 답이 두 번째 케이스에 그대로 재사용된다.

고치는 방법은 캐시를 **함수 안으로 넣는 것**이다. 호출마다 새 캐시가 생긴다.

```python title="paths.py"
from functools import cache


def count_paths(grid):
    @cache                                   # 호출마다 새로 만들어진다
    def paths(r, c):
        if grid[r][c] == "#":
            return 0
        if r == 0 and c == 0:
            return 1
        return (paths(r - 1, c) if r else 0) + (paths(r, c - 1) if c else 0)
    return paths(len(grid) - 1, len(grid[0]) - 1)


print(count_paths(["..", ".."]))
print(count_paths([".#", ".."]))
print(count_paths(["..", ".."]))
print(count_paths(["...", "...", "..."]))
```

```text nolines
2
1
2
6
```

`_paths.cache_clear()` 를 매 호출 앞에 부르는 방법도 있지만 **잊기 쉽고, 잊었을 때 조용히 틀린다.** 캐시의 수명을 호출의 수명과 묶어 두는 쪽이 구조적으로 안전하다. `@cache` 자체는 [3.1](#/functools), 쓰지 말아야 할 자리는 [11.2](#/stdlib-arsenal)에 있다.
:::

::: warn 함수 밖에 두면 안 되는 것 목록
- 가변 기본값(`out=[]`, `memo={}`)
- 모듈 수준 리스트·딕셔너리·`Counter`
- 전역 상태를 읽는 `@cache` / `@lru_cache` 함수
- 모듈 수준에서 하는 모든 상태 초기화 (`sys.setrecursionlimit` 만 예외다)

반대로 **함수 밖에 둬도 되는 것**은 상수뿐이다. 방향 벡터 `DIRS = [(0,1),(1,0),(0,-1),(-1,0)]`, 소수 목록 같은 순수한 읽기 전용 값이다. 이 구분 하나만 지키면 이 범주의 버그는 사라진다.
:::

## 엣지케이스 체크리스트

"엣지케이스를 확인하라"는 조언은 아무 도움이 안 된다. 무엇을 만들지 알려주지 않기 때문이다. **입력의 모양이 만들 케이스를 결정한다.** 아래 표를 인자 타입별로 훑어라.

| 인자 모양 | 반드시 만들 케이스 | 이게 잡는 버그 |
| --- | --- | --- |
| 배열 | 길이 1 | `i - 1` / `i + 1` 을 무조건 참조하는 코드 |
| 배열 | 길이 2 | 양 끝만 있는 상황, 홀짝 분기 |
| 배열 | 전부 같은 값 | `>` 와 `>=` 혼동, 중복 제거로 답이 사라짐 |
| 배열 | 이미 정렬 / 완전 역순 | 정렬 가정, **브루트포스의 최악 시간** |
| 배열 | 값의 하한·상한 (`0`, `10**9`, 음수) | 초기값을 `0` 이나 `-1` 로 잡은 코드 |
| 배열 | 제약이 허용하는 **최대 길이** | 시간 초과, 재귀 한도, 메모리 |
| 문자열 | 한 글자, 전부 같은 글자 | 슬라이딩 윈도우 초기화 |
| 정수 `k` | `k = 0`, `k = 1`, `k >= n` | 창 크기 계산, `range` 경계 |
| 격자 | 1×1, 1×n, n×1 | 행과 열을 뒤바꾼 코드 |
| 반환 | 답이 **없는** 입력 | `None` / `[]` / `-1` 혼동 |

빈 입력은 이 표에 없다. **제약이 `1 <= n` 이면 만들지 마라.** 무엇을 만들지 정하는 것만큼 무엇을 만들지 않을지 정하는 것도 이 표의 일이다.

::: tip 기대값은 손으로 계산하지 말고 무식한 구현에게 물어라
엣지케이스를 만들 때 가장 지치는 일은 **정답을 직접 계산하는 것**이다. 그럴 필요가 없다. 무식한 구현을 하나 짜 두면 그것이 기대값 생성기가 된다([11.7](#/blank-page-routine)).

단, 무식한 구현도 틀릴 수 있다. 그래서 **예시 케이스만은 지문에 적힌 값과 대조**한다. 예시로 검증된 브루트포스가 나머지 전부의 기준이 된다.
:::

앞의 문제에 이 표를 적용하면 열한 개가 나온다. 그리고 그중 **네 개가 처음 시도한 코드를 잡는다.**

```text nolines
[7]              k=5        IndexError    (기대 [0])
[2, 1]           k=5        IndexError    (기대 [0])
[5, 1, 2, 9]     k=2        [3]           (기대 [0, 3])
list(range(10))  k=100000   IndexError    (기대 [9])
```

`k >= n` 세 개는 예외로 즉시 드러나고, `[5, 1, 2, 9]` 하나는 조용히 틀린다. **표의 `k = 0`, `k >= n` 줄을 지키기만 해도 이 버그는 제출 전에 잡힌다.**

## 최대 크기로 돌려라 — 그런데 어떤 데이터로

Constraints 의 상한을 읽었으면 **그 크기로 실제로 돌려 봐야** 한다. 여기에 함정이 하나 더 있다. **어떤 데이터로 돌리는가가 결과를 바꾼다.**

앞 문제의 브루트포스는 `all(...)` 이 단락 평가된다. 난수 데이터에서는 대부분의 `i` 가 첫 비교에서 탈락하므로 창을 다 훑지 않는다. 그런데 입력이 단조 증가면 각 `i` 는 자기 왼쪽 창 전체를 훑고 나서야 오른쪽에서 탈락한다.

::: perf 같은 코드, 같은 크기, 데이터 모양만 다르다
`local_peaks` 브루트포스에 `k = n` 을 준 실행 시간이다. 입력은 **모두 서로 다른 값**이고, `random.seed(11)` 아래에서 "난수"는 `random.sample(range(10**9), n)`, "증가"는 `list(range(n))` 이다.

| n | 난수 | 증가 |
| --- | --- | --- |
| 1,000 | 0.7 ~ 0.9 ms | 32 ~ 37 ms |
| 2,000 | 1.8 ~ 3.2 ms | 130 ~ 145 ms |
| 4,000 | 3.9 ~ 4.1 ms | 520 ~ 650 ms |
| 8,000 | 7.6 ~ 12 ms | 2.1 ~ 2.5 s |
| 16,000 | 측정 안 함 | 8.6 ~ 9.1 s |
| 100,000 | 110 ~ 120 ms | 측정 중단 |

(Python 3.14.0rc2 / Linux 기준 실측. `timeit.repeat(number=1, repeat=5)` 의 최솟값과 최댓값을 **세 세션에 걸쳐** 모은 폭이다. 마지막 두 줄만 `repeat=3`. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**폭을 넓게 잡은 것은 실수가 아니다.** 한 세션 안에서는 값이 몇 퍼센트 안에서 모이지만, 세션을 바꿔 다시 재면 같은 셀이 2배 가까이 벌어지기도 한다(공유 컨테이너에서 재면 특히 그렇다). 그러니 **셀의 소수점이 아니라 열끼리의 자릿수 차이를 봐라.** 벤치마크 수치를 소수 두 자리로 적는 순간 재현되지 않는 약속을 하게 된다.

**난수 열은 n이 2배가 될 때 2배**, **증가 열은 n이 2배가 될 때 4배**가 된다. 같은 코드가 데이터 모양에 따라 $O(n)$ 처럼도 $O(n^2)$ 처럼도 보인다.

제한은 $10^5$ 이다. 난수 $10^5$ 개로는 브루트포스가 **100밀리초대로 통과한다.** 그런데 증가 열은 16,000 개에서 이미 9초다. **난수로만 스모크 테스트하면 통과하고, 채점 데이터가 정렬돼 있으면 시간 초과다.** 최대 크기 테스트에 정렬·역순 데이터를 반드시 섞어라([8.3](#/tle)).
:::

같은 문제를 창의 최댓값으로 푸는 구현은 `k` 와 무관하게 선형이다. 뒤에 나올 `submit_check.py` 의 `local_peaks` 가 그것이다. 덱에는 **값이 감소하는 순서로 인덱스만** 담고, 오른쪽 끝 `right` 는 절대 되돌아가지 않는다. 그래서 인덱스 하나는 평생 `append` 한 번, `pop` 또는 `popleft` 한 번을 겪고 끝난다. 안쪽에 `while` 이 두 개나 있어도 전체 덱 연산 횟수는 $2n$ 을 넘지 않고, 그래서 `k` 가 커져도 시간이 늘지 않는다. 덱의 양 끝이 $O(1)$ 이라는 근거는 [7.2](#/py-ds-cost)에, 언제 `deque` 를 집고 언제 안 집는지는 [11.2](#/stdlib-arsenal)에 있다. 결과는 `n = k = 100,000` 에서 난수·증가·감소 세 모양 모두 **32 ~ 45 ms** 로 데이터 모양에 흔들리지 않는다(같은 조건 실측).

::: cote 재귀로 짜면 최대 크기에서 터진다
해외 플랫폼 문제는 트리·그래프를 다룰 때 재귀 DFS를 자연스럽게 유도한다. 그런데 파이썬의 기본 재귀 한도는 1,000이다.

```pyrepl
>>> import sys
>>> sys.getrecursionlimit()
1000
```

모듈 최상위에서 단순 재귀 함수를 부르면 이 환경에서는 깊이 **998** 까지 성공하고 그다음 `RecursionError` 다. 연결 리스트나 한 줄로 늘어진 트리가 $10^5$ 개면 그대로 실패한다. 한 줄로 막는다.

```python
import sys
sys.setrecursionlimit(300_000)
```

최근 CPython은 파이썬 함수가 파이썬 함수를 부를 때 C 스택을 쓰지 않으므로, 3.14에서는 이 한 줄이면 **깊이 200,000이 실제로 통과한다**(실측). 하지만 **C를 거쳐 다시 파이썬으로 들어오는 재귀**는 여전히 실제 스택 한도에 걸린다. 예컨대 재귀적인 `__repr__` 은 깊이 5,000은 되지만 50,000에서 이렇게 끝난다.

```text nolines
RecursionError: Stack overflow (used 8152 kB) while getting the repr of an object
```

괄호 안의 kB 는 **스레드 스택 크기에 달려 있어서 기기마다 다르고, 같은 기기에서도 실행마다 흔들린다.** 이 환경에서만도 `8148 kB` 와 `8152 kB` 가 번갈아 나왔다. 다른 숫자가 보인다고 당신이 뭘 잘못한 것이 아니다. 봐야 할 것은 `while getting the repr of an object` 쪽이다 — **재귀 한도가 아니라 진짜 C 스택이 찼다**는 뜻이기 때문이다.

`setrecursionlimit` 은 파이썬 프레임 개수의 상한만 올린다. **한도를 올려도 안전해지지 않는 재귀가 있다는 것**을 기억하고, 깊이가 $10^5$ 급이면 반복문으로 바꾸는 쪽을 먼저 생각해라([7.18](#/backtracking)).
:::

## 제출 전 6분 — 자체 검증 루틴

지금까지의 방어책을 하나의 파일로 묶는다. **문제가 바뀌어도 구조는 그대로**여서, 이걸 손에 붙이면 매번 6분이면 끝난다.

```text nolines
  ┌────────────────────────┐
  │ (1) EXAMPLES           │  strict_eq. 지문의 예시. 타입까지
  └────────────┬───────────┘
               ▼
  ┌────────────────────────┐
  │ (2) EDGE               │  체크리스트 표대로. 기대값은 brute 가 만든다
  └────────────┬───────────┘
               ▼
  ┌────────────────────────┐
  │ (3) RANDOM             │  brute 와 무작위 대조. 작은 입력으로 많이
  └────────────┬───────────┘
               ▼
  ┌────────────────────────┐
  │ (4) MAX SIZE           │  제약의 상한. 난수 + 정렬 + 역순
  └────────────────────────┘
```

```python title="submit_check.py — 문제만 갈아 끼워 재사용한다"
import random
import time
from collections import deque


# ── 제출할 함수 ───────────────────────────────────────────────
def local_peaks(counts: list[int], k: int) -> list[int]:
    n = len(counts)
    dq = deque()                      # counts 가 감소하도록 유지되는 인덱스들
    right = 0                         # 아직 창에 넣지 않은 첫 인덱스
    out = []
    for i in range(n):
        hi = min(n - 1, i + k)        # clamp. 음수/초과 인덱스를 만들지 않는다
        while right <= hi:
            while dq and counts[dq[-1]] <= counts[right]:
                dq.pop()
            dq.append(right)
            right += 1
        lo = max(0, i - k)
        while dq[0] < lo:
            dq.popleft()
        if dq[0] == i:                # 값이 서로 다르니 창의 최댓값 == 자기 자신
            out.append(i)
    return out


# ── 대조용 무식한 구현 ────────────────────────────────────────
def brute(counts, k):
    n = len(counts)
    out = []
    for i in range(n):
        lo, hi = max(0, i - k), min(n - 1, i + k)
        if all(counts[i] > counts[j] for j in range(lo, hi + 1) if j != i):
            out.append(i)
    return out


def strict_eq(got, want, path="result"):
    if type(got) is not type(want):
        return f"{path}: 타입 {type(got).__name__} (기대 {type(want).__name__})"
    if isinstance(want, (list, tuple)):
        if len(got) != len(want):
            return f"{path}: 길이 {len(got)} (기대 {len(want)})"
        for i, (g, w) in enumerate(zip(got, want)):
            if msg := strict_eq(g, w, f"{path}[{i}]"):
                return msg
        return None
    return None if got == want else f"{path}: 값 {got!r} (기대 {want!r})"


# ── ① 지문의 예시. 기대값은 지문에서 그대로 가져온다 ──────────
EXAMPLES = [
    (([3, 1, 4, 7, 5, 9, 2, 6], 2), [5]),
    (([2, 8, 1], 1), [1]),
]
for args, want in EXAMPLES:
    msg = strict_eq(local_peaks(*args), want)
    assert msg is None, f"예시 실패 {args} -> {msg}"
print("① 예시 2건 통과 (타입 포함)")

# ── ② 엣지 배터리. 기대값은 brute 가 만든다 ───────────────────
EDGE = [
    ([7], 0), ([7], 5),                            # 원소 한 개
    ([1, 2], 0), ([1, 2], 1), ([2, 1], 5),         # 원소 두 개
    ([5, 1, 2, 9], 2),                             # 왼쪽 경계가 음수로 넘어간다
    ([1, 2, 3, 4, 5], 1), ([5, 4, 3, 2, 1], 1),    # 단조 증가 / 감소
    (list(range(10)), 0),                          # k = 0
    (list(range(10)), 10 ** 5),                    # k 가 n 보다 크다
    ([0, 10 ** 9], 1),                             # 값의 하한과 상한
]
for counts, k in EDGE:
    msg = strict_eq(local_peaks(counts, k), brute(counts, k))
    assert msg is None, f"엣지 실패 {counts} k={k} -> {msg}"
print(f"② 엣지 {len(EDGE)}건 통과")

# ── ③ 무작위 교차 대조 ────────────────────────────────────────
random.seed(11)
for _ in range(20_000):
    n = random.randint(1, 12)
    counts = random.sample(range(100), n)
    k = random.randint(0, 14)
    assert local_peaks(counts, k) == brute(counts, k), (counts, k)
print("③ 무작위 20,000건 일치")

# ── ④ 최대 크기 스모크. 모양을 바꿔 가며 ──────────────────────
N = 100_000
for name, data in (("난수", random.sample(range(10 ** 9), N)),
                   ("증가", list(range(N))),
                   ("감소", list(range(N, 0, -1)))):
    t = time.perf_counter()
    got = local_peaks(data, N)
    print(f"④ n={N} k={N} {name}: {(time.perf_counter() - t) * 1000:6.1f} ms, "
          f"결과 {len(got)}개")
```

```text nolines
① 예시 2건 통과 (타입 포함)
② 엣지 11건 통과
③ 무작위 20,000건 일치
④ n=100000 k=100000 난수:   37.9 ms, 결과 1개
④ n=100000 k=100000 증가:   34.4 ms, 결과 1개
④ n=100000 k=100000 감소:   33.2 ms, 결과 1개
```

④ 의 밀리초 값은 실행마다 흔들린다. 봐야 할 것은 **자릿수**다. 제한 시간이 보통 몇 초니까 수십 밀리초는 안전하다. 그리고 `결과 1개` 도 정보다 — `k = n` 이면 전체 최댓값 하나만 남는 것이 맞다. **출력에 검산 가능한 숫자를 하나 넣어 두면 스모크 테스트가 정확성 테스트도 된다.**

::: cote 시험장 시간 배분 — 6분을 어디에 쓰는가
```text nolines
(1) EXAMPLES    1분   지문 예시를 strict_eq 로. 복사만 하면 된다
(2) EDGE        2분   체크리스트 표를 훑으며 인자별로 케이스를 적는다
(3) RANDOM      1분   brute 가 이미 있으면 3줄
(4) MAX SIZE    2분   난수 + 정렬 + 역순. 시간을 눈으로 본다
```

브루트포스를 먼저 짰다면 ②③은 거의 공짜다. 그래서 **무식한 구현을 지우지 않는 습관**이 여기서 이자를 낸다([11.7](#/blank-page-routine)).

시간이 정말 없으면 순서는 **④ → ② → ③** 이다. 시간 초과는 부분 점수도 못 받고, 엣지케이스는 케이스 단위로 깎이고, 무작위 대조는 남은 시간에 하는 보험이다.
:::

::: tip 제출 버튼 앞에서 마지막 30초
- 반환 타입이 시그니처의 힌트와 같은가. `int` 자리에 `float` 가 없는가
- 답이 없는 케이스를 실제로 돌려 봤는가. `None` 이 새어 나가지 않는가
- 함수 밖에 가변 객체가 있는가
- `print` 로 디버그 출력을 남겨 두지 않았는가 — 채점기가 느려지거나 형식이 깨진다
- `in increasing order` 같은 순서 요구를 지켰는가

다섯 줄이 전부다. 종이에 적어 두고 매번 봐라. 항목을 외우려 하면 급할 때 빠뜨린다([11.14](#/exam-debug)).
:::

## 요약

- 함수 완성형에서 떨어지는 이유는 대개 알고리즘이 아니다. **반환 타입, 시그니처, 지문의 부등호와 대괄호**다. 입력 파싱이 사라진 만큼 실패 지점이 이쪽으로 옮겨 왔다.
- 영문 지문에서 밑줄 칠 자리는 여섯 곳이다. **반환 문장 / 부등호 단어 / 구간의 대괄호 / 없을 때 / Constraints 상한 / `guaranteed` 문장.** `[a, b]` 는 양 끝 포함이고 `range` 는 아니다. 그리고 Constraints 는 제약이 아니라 **선물**이다 — `distinct` 는 동점 처리를, `1 <= n` 은 빈 입력 방어를 지워 준다.
- 타입 불일치가 새어 나가는 길은 둘이다. `True == 1`, `5.0 == 5` 는 **`==` 자체가 통과시킨다.** 반면 `(0, 3)` vs `[0, 3]`, `'True'` vs `'true'`, `None` vs `[]` 는 `==` 가 잡을 수 있는데 기대값을 튜플로 적거나 그 케이스를 안 만들어서 못 잡는다. 앞쪽은 `type(got) is type(want)` 까지 보는 비교 함수로, 뒤쪽은 기대값을 무식한 구현에게 시키는 것으로 막는다.
- 시그니처는 계약이다. **인자 이름·순서를 바꾸지 마라.** 보조 인자가 필요하면 내부 함수와 클로저로 해결한다. `in-place` 는 `nums[:] = ...` 이지 재대입이 아니다.
- 채점기는 한 프로세스에서 케이스를 **여러 번** 부른다. 가변 기본값, 모듈 수준 컨테이너, 전역을 읽는 `@cache` 는 전부 케이스 사이로 새어 나간다. 캐시는 **함수 안에** 둬라.
- 엣지케이스는 감이 아니라 표다. **길이 1 / 길이 2 / 전부 같음 / 정렬·역순 / 값의 상하한 / 최대 크기 / `k = 0` / `k >= n`.** 기대값은 손으로 계산하지 말고 무식한 구현에게 물어라.
- 제출 전 루틴은 넷이다. **예시(타입까지) → 엣지 배터리 → 무작위 대조 → 최대 크기 스모크.** 그리고 최대 크기 테스트는 **데이터 모양까지 바꿔야** 한다 — 같은 브루트포스가 난수 $10^5$ 개는 100밀리초대, 증가 16,000개는 9초였다(실측). 난수로만 재면 통과해 버린다. 시간이 없으면 최대 크기부터.

::: quiz 코드 과제 — 전부 `submit_check.py` 구조로 검증까지 짜라
각 문제마다 **함수 + 무식한 구현 + `strict_eq` + 네 단계 검증**을 한 파일에 담아라. 검증 출력이 없는 답은 이 절의 과제를 안 한 것이다.

**1. 지문을 정확히 읽었는지 확인하라 (10분)**

```text nolines
You are given a 0-indexed integer array `waits` and an integer `limit`.

A pair `(i, j)` with `i < j` is *within budget* if `waits[i] + waits[j]` is at most
`limit` and `j - i` is at least 2.

Return the number of pairs that are within budget. If there are none, return 0.

Constraints:
  1 <= len(waits) <= 2000
  0 <= waits[i] <= 10**9
  0 <= limit <= 10**9
```

`count_within_budget(waits, limit) -> int` 를 완성해라. 먼저 **`at most` 와 `at least` 를 각각 어떤 부등호로 옮겼는지 주석으로 적고** 코드를 써라. 다음 세 케이스가 정답을 갈라 놓는다. 왜 그런지도 적어라.

```python
count_within_budget([1, 2, 3, 4], 5)      # 2
count_within_budget([0, 0, 0], 0)         # 1
count_within_budget([10 ** 9], 10 ** 9)   # 0
```

**2. 반환 타입 함정을 직접 만들어라 (10분)**

`is_balanced(entries: list[int]) -> bool` — `entries` 의 합이 0이면 `True`, 아니면 `False`. 단순하다. 그런데 **아래 네 가지 구현을 모두 짜고**, 각각에 대해 합이 0인 입력(`[0, 0]`)과 0이 아닌 입력(`[1, 2]`)을 **둘 다** 넣어 `strict_eq(got, True)` / `strict_eq(got, False)` 에 걸어 보고 어떤 메시지가 나오는지 기록해라.

```text nolines
(a) "true" / "false" 문자열을 반환한다
(b) 1 / 0 을 반환한다
(c) sum(entries) == 0.0 처럼 float 와 비교한 결과를 반환한다
(d) 합이 0이 아닐 때 아무것도 반환하지 않는다 (None 이 새어 나간다)
```

합이 0인 입력만 넣어 보면 네 개 중 **`assert got == True` 로 걸러지는 것은 (a) 하나뿐**이다. (b)는 `1 == True` 라서 그냥 통과하고, 여기서 `strict_eq` 가 타입으로 잡아 준다. (c)는 **`strict_eq` 조차 통과한다** — 비교식의 결과라 반환 타입이 실제로 `bool` 이기 때문이다. (d)도 합이 0인 케이스만 돌리면 `True` 를 정상으로 반환해 통과하고, **합이 0이 아닌 케이스를 넣어야** `None` 이 드러난다.

여기서 답해야 할 것이 둘이다. 첫째, (c)는 사실 **언제나 올바른 `bool` 을 반환한다** — 그런데도 이 목록에 들어 있는 이유를 한 문장으로 적어라(힌트: `0.0` 은 이 코드에서 어디로 사라지는가, 그리고 `sum` 자리에 `/` 가 하나 들어오면 어떻게 되는가). 둘째, (d)를 잡으려면 검증 코드에 무엇이 더 있어야 했는지 적어라.

**3. 상태 누출을 재현하고 고쳐라 (15분)**

`longest_run(flags: list[str]) -> int` — 같은 값이 연속으로 이어진 가장 긴 길이. 여기에 **일부러 상태 누출을 심어라.** 모듈 수준 `BEST = 0` 을 두고 갱신하는 방식이다. 그리고 다음 호출 순서로 버그를 드러내라.

```python
longest_run(["ON", "ON", "OFF"])          # 2
longest_run(["OFF"])                      # 1 이어야 한다
longest_run(["ON", "OFF", "ON", "OFF"])   # 1 이어야 한다
```

세 호출을 **한 프로세스에서 연달아** 실행했을 때 실제로 무엇이 나오는지 적고, 지역 변수로 고친 뒤 다시 실행해 대조해라. 그다음 `@cache` 를 붙인 버전으로 같은 실험을 하라 — 인자가 리스트라 캐시가 아예 붙지 않는다. **그 예외 메시지도 기록해라.**

**4. 최악 모양 데이터를 찾아라 (15분)**

`has_close_pair(values: list[int], gap: int) -> bool` — 차이가 `gap` 이하인 두 값이 있으면 `True`. 이중 루프 브루트포스와, 정렬 후 인접만 보는 구현을 둘 다 짜라. 그리고 **브루트포스가 가장 느려지는 입력 모양을 직접 찾아라.** 힌트: 답이 `True` 면 조기 반환이 걸린다.

`n = 3,000` 에서 세 가지 모양(난수 / 전부 서로 멀리 떨어진 값 / 답이 맨 앞에 있는 입력)의 실행 시간을 **범위로** 측정해 표로 적고, 어느 모양이 최악인지와 그 이유를 쓰라.

**5. `in-place` 문제 (10분)**

```text nolines
Modify `slots` in-place so that all occupied slots ("X") come before all free
slots ("."), preserving the relative order within each group. Return None.
```

`arrange(slots: list[str]) -> None` 을 완성해라. **반환값이 `None` 인 것까지** `strict_eq(arrange(data), None)` 으로 검증하고, 호출 후 `data` 가 실제로 바뀌었는지도 검증해라. `slots = sorted(...)` 로 쓰면 왜 아무 일도 일어나지 않는지 한 문장으로 적어라.

**6. 확장 과제.** 1~5번의 `strict_eq` 를 **딕셔너리와 집합까지** 대조하도록 확장하라. 딕셔너리는 키 집합과 각 값의 타입을, 집합은 원소의 타입을 봐야 한다. 확장한 뒤 `strict_eq({"a": 1}, {"a": True})` 와 `strict_eq({1, 2}, {True, 2})` 가 무엇을 보고하는지 확인해라. 두 번째는 **파이썬이 `1` 과 `True` 를 같은 키로 취급**하기 때문에 생각보다 까다롭다. 어디까지 잡을 수 있고 어디부터는 못 잡는지 경계를 적어라.
:::

**다음 절**: [11.9 드릴 I — 문자열·검증](#/drill-string) — 여기까지의 루틴을 문자열·검증 문제 여덟 개에 실제로 적용한다. 이제부터는 읽는 절이 아니라 멈춰서 푸는 절이다.
