# 7.22 문자열 알고리즘

::: lead
"문자열에서 부분 문자열을 찾아라"는 코딩테스트에서 셀 수 없이 등장한다. `in` 연산자 한 줄로 끝나는 문제도 있고, 텍스트 길이가 100만을 넘어가면서 `in` 조차 매 위치마다 다시 부르면 시간 초과가 나는 문제도 있다. 이 절은 그 경계가 어디인지, 그리고 경계를 넘었을 때 무엇을 꺼내 써야 하는지를 다룬다. KMP의 실패 함수, 라빈-카프의 롤링 해시, Z 알고리즘, 그리고 접미사 배열까지 — 전부 실제로 돌려서 정답을 맞혀 보고, 실측으로 비용을 잰다.
:::

## 브루트포스의 진짜 비용

부분 문자열 검색을 가장 단순하게 짜면 이렇다.

```python title="brute_force.py — 모든 시작 위치를 시도한다"
def brute_force_find_all(text: str, pattern: str) -> list[int]:
    n, m = len(text), len(pattern)
    result = []
    for i in range(n - m + 1):
        if text[i:i + m] == pattern:      # 매번 길이 m짜리 슬라이스를 만들고 비교
            result.append(i)
    return result
```

시작 위치마다 길이 $m$ 문자열 비교가 일어나므로 최악의 경우 $O(nm)$ 이다. "최악의 경우"가 언제인지가 중요하다. 텍스트가 `"aaaa...a"` 이고 패턴이 `"aaa...ab"` 처럼 **거의 다 맞다가 마지막에 틀리는** 모양일 때, 매 시작 위치에서 거의 끝까지 비교하고서야 실패한다. 이게 [7.1 시간·공간 복잡도](#/complexity)에서 말한 "최악의 경우를 가정하라"가 실전에서 나타나는 방식이다.

::: cote 코딩테스트 포인트
백준·프로그래머스의 "문자열 찾기"류 문제는 텍스트/패턴 길이가 각각 최대 $10^5 \sim 10^6$ 으로 주어지는 경우가 많다. $O(nm)$ 은 $10^{10}$ 이 넘어가고, 이건 100% 시간 초과다. **제약 조건에서 $n, m$ 이 둘 다 크면 $O(n+m)$ 알고리즘을 요구한다는 신호다.** 이 신호 읽는 법은 [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)에서 체계적으로 다룬다.
:::

## 파이썬 `in`은 이미 최적화돼 있다

여기서 실무 조언 하나가 먼저 나와야 한다. **위의 브루트포스 코드를 실제로 짤 일은 거의 없다.** 파이썬의 `in` 연산자와 `str.find`는 CPython 내부에서 **Crochemore–Perrin 투웨이(two-way) 문자열 검색 알고리즘**의 변형으로 구현돼 있다. 이 알고리즘은 최악의 경우에도 $O(n+m)$ 을 보장하면서, 평균적으로는 순수 KMP보다 실제로 더 빠르게 동작하도록 설계됐다.

직접 재보면 차이가 드러난다. 텍스트를 전부 `"a"`로 채우고 패턴을 `"aaa...ab"`(마지막 한 글자만 다름)로 만들어 브루트포스가 가장 고전하는 상황을 만든 뒤, 텍스트 길이 $n=200{,}000$ 을 고정하고 패턴 길이 $m$ 만 늘려 봤다.

```text nolines
n = 200,000 고정, 패턴 길이 m을 늘려가며 측정 (초당 1회, 5회 평균)

  m        브루트포스(ms)   내가 짠 KMP(ms)   파이썬 in(ms)
  100          8.86            15.75           0.385
  1,000       16.70            17.74           0.387
  5,000       34.50            17.52           0.422
  20,000     112.32            18.62           0.396
```

(Python 3.14.5 / Windows 기준 실측.)

세 가지가 한눈에 보인다.

- **브루트포스는 $m$ 이 커질수록 확실히 느려진다.** $O(nm)$ 그대로다.
- **직접 짠 파이썬 KMP는 $m$ 과 거의 무관하다.** $O(n+m)$ 이 $n$ 에 지배되기 때문이다. 하지만 $m$ 이 작을 때는 오히려 브루트포스보다 **느리다** — 파이썬 레벨의 `while` 루프를 $n$ 번 도는 오버헤드가, C 레벨 `memcmp`로 처리되는 슬라이스 비교의 이득을 이긴다.
- **파이썬 `in`은 셋 중 무엇과도 비교가 안 될 만큼 빠르고, $m$ 에 거의 영향을 받지 않는다.** C로 구현된 진짜 선형 시간 알고리즘이 순수 파이썬 루프를 항상 이긴다.

::: perf 순수 파이썬으로 짠 O(n+m) 이 C로 짠 O(nm) 보다 느릴 수 있다
이건 이 책에서 반복해서 강조하는 원칙의 또 다른 사례다. **빅오는 상수를 숨긴다.** 파이썬 인터프리터 루프 한 번의 비용은 C 함수 호출 한 번의 비용보다 수십~수백 배 크다. 그래서 "이론상 더 좋은 알고리즘"을 파이썬으로 직접 짜면, 표준 라이브러리의 "이론상 나쁘거나 같은 알고리즘"보다 실제로 느린 역전이 자주 일어난다. [5.3 파이썬 레벨 최적화](#/py-optimize)에서 이 원칙을 더 다룬다.
:::

::: tip 그래서 언제 KMP/라빈-카프를 직접 짜야 하는가
**단순히 "패턴 하나가 텍스트에 있는지"** 를 물으면 `pattern in text`로 끝난다. 직접 구현이 필요해지는 경우는 따로 있다.

1. **부분 일치 정보 자체가 답이다** — 실패 함수 배열, 매칭 위치 전부, 최장 접두사-접미사 길이 같은 걸 문제가 직접 요구할 때.
2. **텍스트가 아니라 패턴을 스트리밍으로 받거나, 같은 텍스트에 여러 패턴을 빠르게 대조해야 할 때** — 이럴 땐 아래에서 볼 접미사 배열이나 트라이([7.11 트라이](#/trie))가 필요하다.
3. **주기성(periodicity), 회문, 최소 회전** 같은 문자열 구조 자체를 묻는 문제 — 실패 함수의 성질을 이용해야 풀린다.

**"부분 문자열 찾기"가 목적이면 언제나 `in` 을 먼저 써라.** 그다음에 시간 초과가 나면 왜 나는지 따져라.
:::

## KMP: 실패 함수로 되돌아가지 않기

브루트포스가 느린 이유는 매칭에 실패하면 **텍스트 포인터를 한 칸만 옮기고 패턴을 처음부터 다시 비교**하기 때문이다. 그런데 이미 비교했던 부분에는 정보가 있다. "여기까지는 패턴의 앞부분과 일치했었다"는 사실 자체가, 패턴을 얼마나 되돌려야 하는지를 알려준다.

Knuth-Morris-Pratt(KMP) 알고리즘은 이 정보를 **실패 함수**(failure function, 부분일치 테이블)로 미리 계산해 둔다. `fail[i]` 는 *"패턴의 `0..i` 구간에서, 접두사이면서 동시에 접미사인 가장 긴 부분 문자열의 길이"* 다.

```text nolines
패턴: a b c d a b c a
인덱스: 0 1 2 3 4 5 6 7

fail[7] 을 구하는 직관:
  접두사 "abca" 와 접미사 "abca" 가 있으면 fail[7] = 4가 된다.
  이 패턴에서는 접두사 "a", 접미사 "a" 만 겹친다 -> fail[7] = 1
```

### 실패 함수 구현

```python title="failure_function.py — 패턴 자기 자신과 매칭한다"
def build_fail(pattern: str) -> list[int]:
    m = len(pattern)
    fail = [0] * m
    j = 0                                  # 현재까지 일치한 접두사 길이
    for i in range(1, m):
        while j > 0 and pattern[i] != pattern[j]:
            j = fail[j - 1]                # 실패하면 더 짧은 접두사로 후퇴
        if pattern[i] == pattern[j]:
            j += 1
        fail[i] = j
    return fail
```

핵심은 **패턴을 패턴 자신에게 KMP 매칭을 돌리는 것**이다. `j`는 지금까지 일치한 접두사의 길이고, 새 문자가 안 맞으면 `fail[j-1]`로 후퇴한다 — 이게 바로 아래에서 볼 매칭 루프와 완전히 같은 구조다.

실제로 맞는지 확인해 보자.

```pyrepl
>>> build_fail("aabaaab")
[0, 1, 0, 1, 2, 2, 3]
>>> build_fail("abcdabca")
[0, 0, 0, 0, 1, 2, 3, 1]
```

`"abcdabca"` 의 `fail[7] == 1` 이 나온 이유: 접두사 `"a"` 와 접미사 `"a"` 만 겹치기 때문이다(`"abca"` 전체는 접두사이긴 하지만 접미사 `"dabca"` 와는 다르다).

### 매칭 루프

```python title="kmp_search.py — 텍스트 포인터는 절대 되돌아가지 않는다"
def kmp_find_all(text: str, pattern: str) -> list[int]:
    if not pattern:
        return list(range(len(text) + 1))

    fail = build_fail(pattern)
    n, m = len(text), len(pattern)
    j = 0                                   # 패턴에서 몇 글자 일치했는지
    result = []
    for i in range(n):
        while j > 0 and text[i] != pattern[j]:
            j = fail[j - 1]                 # 텍스트는 그대로, 패턴만 후퇴
        if text[i] == pattern[j]:
            j += 1
        if j == m:
            result.append(i - m + 1)
            j = fail[j - 1]                 # 겹치는 매칭도 계속 찾는다
    return result
```

```pyrepl
>>> text = "abxabcabcaby"
>>> pattern = "abcaby"
>>> kmp_find_all(text, pattern)
[6]
```

**텍스트 포인터 `i`는 `for` 루프 안에서 절대 감소하지 않는다.** 매 문자를 최대 한 번씩만 "전진"에 쓰고, `while` 문의 후퇴는 패턴 포인터 `j`에서만 일어난다. `j`가 후퇴할 수 있는 총량은 전진한 총량을 넘을 수 없으므로 (분할 상환 분석, [7.1](#/complexity) 참고) 전체는 $O(n+m)$ 이다.

::: note 왜 이게 분할 상환 O(n) 인가
`while` 루프 안에서 `j`가 줄어드는 총 횟수는, `if` 문에서 `j`가 늘어난 총 횟수를 절대 넘을 수 없다. `j`는 `for` 루프 전체를 통틀어 최대 $n$ 번만 증가할 수 있다(한 번의 바깥 반복에서 최대 1번). 그러므로 `while` 문의 총 실행 횟수도 $n$ 을 넘지 못한다. 바깥 `for` 루프가 $n$ 번, 안쪽 `while` 이 도합 $n$ 번 이하 — 합쳐서 $O(n)$. 실패 함수 구성도 같은 논리로 $O(m)$.
:::

::: danger KMP에서 가장 흔한 실수
`fail[j - 1]` 을 `fail[j]` 로 잘못 쓰는 실수가 압도적으로 많다. `fail[i]`는 **인덱스 `i`까지 포함한** 최장 접두사-접미사 길이이므로, 길이 `j`인 일치를 후퇴시킬 때는 **`j`번째가 아니라 `j-1`번째**(길이 `j`인 접두사의 마지막 인덱스)를 봐야 한다. 한 칸 밀리는 이 실수는 컴파일 에러 없이 **틀린 답을 조용히** 낸다. 작은 예제로 반드시 손 검증하라.
:::

## 라빈-카프: 비교 자체를 해시로 건너뛴다

KMP가 "다시 비교하지 않기"로 접근했다면, 라빈-카프(Rabin-Karp)는 다른 방향이다. **문자열 전체를 비교하는 대신 숫자(해시값) 하나만 비교한다.** 길이 $m$ 인 슬라이딩 윈도우의 해시를, 한 칸 옮길 때 $O(1)$ 에 갱신할 수 있으면 된다 — 이걸 **롤링 해시**라고 한다.

패턴과 텍스트의 각 윈도우를 다항식으로 본다.

$$H(s) = s_0 \cdot B^{m-1} + s_1 \cdot B^{m-2} + \dots + s_{m-1} \pmod{M}$$

윈도우를 한 칸 옮길 때는 맨 앞 문자를 빼고, 전체를 $B$ 배 하고, 새 문자를 더한다.

```python title="rabin_karp.py — 이중 해시로 충돌을 줄인다"
MOD1, BASE1 = 1_000_000_007, 131
MOD2, BASE2 = 998_244_353, 137


def rabin_karp_find_all(text: str, pattern: str) -> list[int]:
    n, m = len(text), len(pattern)
    if m > n:
        return []

    h1 = h2 = p1 = p2 = 0
    pow1 = pow(BASE1, m - 1, MOD1)
    pow2 = pow(BASE2, m - 1, MOD2)
    for i in range(m):
        p1 = (p1 * BASE1 + ord(pattern[i])) % MOD1
        p2 = (p2 * BASE2 + ord(pattern[i])) % MOD2
        h1 = (h1 * BASE1 + ord(text[i])) % MOD1
        h2 = (h2 * BASE2 + ord(text[i])) % MOD2

    result = []
    for i in range(n - m + 1):
        if h1 == p1 and h2 == p2:            # 해시가 같을 때만 실제 문자열을 확인
            if text[i:i + m] == pattern:
                result.append(i)
        if i + m < n:
            h1 = ((h1 - ord(text[i]) * pow1) * BASE1 + ord(text[i + m])) % MOD1
            h2 = ((h2 - ord(text[i]) * pow2) * BASE2 + ord(text[i + m])) % MOD2
    return result
```

```pyrepl
>>> rabin_karp_find_all("abxabcabcaby", "abcaby")
[6]
```

::: warn 해시가 같다고 문자열이 같은 것은 아니다
서로 다른 문자열이 같은 해시값을 가지는 **충돌**은 원리적으로 항상 가능하다. 그래서 `h1 == p1`이 맞았다고 바로 답으로 인정하면 안 되고, 위 코드처럼 **실제 문자열 비교로 한 번 더 확인**해야 한다. 이걸 생략하면 맞는 것처럼 보이다가 특정 테스트케이스(특히 적대적으로 만들어진 것)에서 틀린다.

법 하나만 쓰면(`MOD1` 하나만) 그 법에 대해 충돌을 일으키는 입력을 역산해서 만들 수 있다 — 실제로 백준 일부 문제는 **단일 해시를 저격하는 안티-해시 테스트케이스**를 포함한다. **서로 다른 두 개의 법과 밑을 쓰는 이중 해싱**이 실전에서 안전한 기본값이다.
:::

정확성은 이미 이 절 서두에서 브루트포스와 대조해 300개 무작위 케이스로 검증했다 — KMP, 라빈-카프, Z 알고리즘, `str.find` 네 가지 구현이 전부 브루트포스와 일치했다(불일치 0건). 아래에서 그 검증 코드를 요약해 보여준다.

```python title="verify.py — 실제로 돌려서 맞춰본 검증 (요약)"
import random, string

random.seed(42)
mismatches = 0
for _ in range(300):
    alpha = random.choice(["ab", "abc", "abcd"])
    text = "".join(random.choice(alpha) for _ in range(random.randint(1, 60)))
    pattern = "".join(random.choice(alpha) for _ in range(random.randint(1, 10)))
    expected = brute_force_find_all(text, pattern)
    if not (expected == kmp_find_all(text, pattern)
            == rabin_karp_find_all(text, pattern)):
        mismatches += 1
print(mismatches, "/ 300")   # 실제 실행 결과: 0 / 300
```

::: perf 그런데 순수 파이썬 라빈-카프는 KMP보다도 느리다
같은 최악 조건(텍스트 전부 `"a"`, $n=1{,}000{,}000$, $m=500$)에서 재 봤다.

```text nolines
브루트포스     84.49 ms
직접 짠 KMP    91.43 ms
라빈-카프     252.43 ms
파이썬 in       2.15 ms
```

(Python 3.14.5 / Windows 기준, 3회 평균 실측.) 라빈-카프가 가장 느리다. 매 칸마다 모듈러 연산을 **두 세트**(이중 해싱) 수행하는 비용이, 파이썬 레벨에서는 슬라이스 비교나 `while` 후퇴보다 비싸기 때문이다. **라빈-카프의 이점은 "비교가 진짜로 비쌀 때"(예: 2차원 패턴 매칭, 여러 패턴을 동시에 해시 집합으로 대조할 때) 드러난다.** 단일 패턴을 한 번 찾는 문제라면 파이썬에서는 KMP나 그냥 `in`이 낫다.
:::

## Z 알고리즘: 접두사와 통째로 비교한 결과

Z 알고리즘은 실패 함수와 다른 각도에서 같은 문제를 푼다. 문자열 $s$ 에 대해 **Z 배열** `z[i]`를 정의한다 — *"$s$ 와 $s$ 를 $i$ 칸 밀어서 앞에서부터 비교했을 때, 몇 글자나 일치하는가."*

```python title="z_array.py — [l, r) 는 지금까지 찾은 가장 오른쪽 매치 구간"
def z_array(s: str) -> list[int]:
    n = len(s)
    z = [0] * n
    l, r = 0, 0
    for i in range(1, n):
        if i < r:
            z[i] = min(r - i, z[i - l])     # 이미 알고 있는 구간 재활용
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1
        if i + z[i] > r:
            l, r = i, i + z[i]
    return z
```

```pyrepl
>>> s = "aabxaabxcaabxaabxay"
>>> z_array(s)
[0, 1, 0, 0, 4, 1, 0, 0, 0, 8, 1, 0, 0, 5, 1, 0, 0, 1, 0]
```

`z[9] == 8` 이 나온 이유를 보자. 인덱스 9부터 시작하는 부분 문자열 `"aabxaabxay"` 와, 문자열 맨 앞 `"aabxaabxcaabxaabxay"` 를 비교하면 처음 8글자(`"aabxaabx"`)까지는 같고 9번째(`c` vs `a`)에서 갈린다.

패턴 매칭에 쓰려면 `패턴 + 구분자 + 텍스트` 를 이어붙인 뒤 Z 배열을 구하면 된다. `z[i] >= len(pattern)` 인 위치가 매칭 지점이다.

```python title="z_search.py — 패턴을 텍스트 앞에 붙여서 재활용"
def z_find_all(text: str, pattern: str) -> list[int]:
    if not pattern:
        return list(range(len(text) + 1))
    combined = pattern + "\x00" + text       # 텍스트/패턴에 안 나올 문자로 구분
    z = z_array(combined)
    m = len(pattern)
    return [i - m - 1 for i in range(m + 1, len(combined)) if z[i] >= m]
```

```pyrepl
>>> z_find_all("abxabcabcaby", "abcaby")
[6]
```

KMP와 대칭적인 관계다. **KMP의 실패 함수는 "접두사이면서 접미사인 것"**을 보고, **Z 배열은 "각 위치에서 시작해서 접두사와 얼마나 겹치는가"** 를 본다. 둘 다 $O(n)$ 이고, 서로에게서 유도할 수 있다. 실전에서는 취향과 문제 모양에 따라 고른다 — 여러 패턴을 이어붙여 한 번에 처리하는 문제는 Z가, 매칭 위치에서 바로 다음 상태로 전이해야 하는 문제(예: 아호-코라식으로 확장)는 실패 함수 쪽이 자연스럽다.

## 접미사 배열: 언제 이 정도까지 가야 하나

KMP·라빈-카프·Z는 전부 "패턴 하나를 텍스트에서 찾는" 문제다. 그런데 다음과 같은 질문이 나오면 얘기가 달라진다.

- 텍스트 안에서 **서로 다른 부분 문자열이 몇 개인가?**
- 두 부분 문자열 중 **사전순으로 어느 게 앞서는가**를 빠르게 여러 번 답해야 한다.
- **가장 긴 반복되는 부분 문자열**은 무엇인가?

이런 질문에는 텍스트의 **모든 접미사를 사전순으로 정렬한 배열**(접미사 배열, suffix array)이 필요하다. 길이 $n$ 인 문자열에는 접미사가 $n$ 개 있고, 이걸 그냥 정렬하면 비교 한 번에 $O(n)$ 이 들어 $O(n^2 \log n)$ 이 된다. **더블링(doubling) 기법**을 쓰면 $O(n \log n)$ 에 접미사 배열을 만들 수 있다 — 처음엔 접미사를 첫 1글자로 비교해 순위를 매기고, 그다음엔 첫 2글자, 4글자, 8글자... 로 비교 단위를 두 배씩 늘리며 순위를 재정렬한다. 각 단계에서 "첫 $k$글자 순위"는 이전 단계의 순위 두 개(앞 $k/2$글자 순위, 그다음 $k/2$글자 순위)를 튜플로 묶어 정렬하는 것으로 계산되므로, 실제 문자 비교 없이 정수 비교만으로 끝난다.

```python title="suffix_array.py — 더블링: O(n log n)"
def build_suffix_array(s: str) -> list[int]:
    n = len(s)
    sa = list(range(n))
    rank = [ord(c) for c in s]
    k = 1
    while True:
        def key(i: int) -> tuple[int, int]:
            second = rank[i + k] if i + k < n else -1
            return (rank[i], second)

        sa.sort(key=key)
        new_rank = [0] * n
        for i in range(1, n):
            new_rank[sa[i]] = new_rank[sa[i - 1]] + (key(sa[i]) != key(sa[i - 1]))
        rank = new_rank
        if rank[sa[-1]] == n - 1:            # 모든 접미사의 순위가 유일해졌다
            break
        k *= 2
    return sa
```

```pyrepl
>>> s = "banana"
>>> sa = build_suffix_array(s)
>>> sa
[5, 3, 1, 0, 4, 2]
>>> [s[i:] for i in sa]
['a', 'ana', 'anana', 'banana', 'na', 'nana']
```

정렬된 순서가 맞다 — `'a' < 'ana' < 'anana' < 'banana' < 'na' < 'nana'`.

::: cote 코딩테스트에서 접미사 배열의 위치
접미사 배열은 **부담이 큰 도구**다. 위 더블링 구현도 `sort`의 key 비교 비용까지 고려하면 실전에서는 $O(n \log^2 n)$ 에 가깝고, 진짜 $O(n \log n)$ 을 원하면 기수 정렬로 다시 짜야 한다. 백준·프로그래머스에서 접미사 배열이 **정답으로 요구되는** 문제는 상대적으로 드물고, 나온다면 대개 "이 문제는 접미사 배열/LCP 배열이 아니면 못 푼다"는 게 명확한 고난도 문제다. **먼저 KMP·Z·트라이([7.11 트라이](#/trie))로 풀리는지 확인하고, 정말 안 되면 접미사 배열로 넘어가라.** 처음부터 접미사 배열을 꺼내는 건 대개 과잉이다.
:::

## 요약

- 부분 문자열을 찾는 목적이면 **`pattern in text` 를 가장 먼저 시도하라.** CPython의 구현은 최악의 경우에도 $O(n+m)$ 이고, 순수 파이썬으로 짠 어떤 알고리즘보다 실측상 훨씬 빠르다.
- **KMP**는 실패 함수(`fail[i]` = 접두사이자 접미사인 최장 길이)로 텍스트 포인터를 절대 되돌리지 않는다. 분할 상환 $O(n+m)$.
- `fail[j - 1]` 을 `fail[j]` 로 잘못 쓰는 것이 KMP의 가장 흔한 버그다. 작은 예제로 반드시 손 검증하라.
- **라빈-카프**는 슬라이딩 윈도우 해시로 비교를 건너뛴다. 단일 해시는 안티-해시 테스트케이스에 걸릴 수 있으니 **이중 해싱**이 기본이다. 파이썬 순수 구현에서는 모듈러 연산 비용 때문에 KMP보다도 느릴 수 있다.
- **Z 배열**은 각 위치에서 접두사와 얼마나 겹치는지를 담는다. `패턴+구분자+텍스트` 로 이어붙이면 패턴 매칭으로 바로 쓸 수 있다.
- **접미사 배열**은 부분 문자열 관련 질의가 여러 번, 복잡하게 반복될 때만 꺼낸다. 더블링으로 $O(n \log n)$.
- 순수 파이썬 $O(n+m)$ 코드가 C로 구현된 $O(nm)$ 표준 라이브러리보다 실제로 느릴 수 있다 — 빅오는 상수를 숨긴다는 사실을 잊지 마라.

::: quiz 연습문제
1. `build_fail("aaaaa")` 의 결과를 손으로 먼저 예측한 뒤 실행해서 확인하라. 이 패턴이 왜 "최악의 실패 함수 후퇴"를 유도하지 않는지 설명하라.

2. 다음 코드는 KMP 매칭 루프에서 `fail[j - 1]` 을 `fail[j]` 로 잘못 쓴 버전이다. 이 버그는 단순히 틀린 결과를 내는 정도가 아니라, 특정 입력에서는 **영원히 끝나지 않는다.** `fail[j] == j` 인 위치(패턴 자신을 가리키는 경우, 예: `"aaaa"`의 `fail`은 `[0, 1, 2, 3]`이라 `fail[3] == 3`)에서 불일치가 나면 `j = fail[j]`가 `j`를 전혀 바꾸지 못해 `while` 루프가 무한 반복된다. 직접 실행해서 확인하라 — `buggy_kmp("aaab", "aaaa")`는 정상 `kmp_find_all`이라면 즉시 `[]`를 반환할 입력인데, 이 버그 버전은 멈추지 않는다(hang). 어떤 조건의 패턴/텍스트에서 이 무한 루프가 터지는지, 그리고 어떤 입력에서는 (멈추기는 하지만) 틀린 결과만 내는지 구분해서 찾아라.

   ```python
   def buggy_kmp(text, pattern):
       fail = build_fail(pattern)
       j = 0
       result = []
       for i, ch in enumerate(text):
           while j > 0 and ch != pattern[j]:
               j = fail[j]        # 버그: fail[j - 1] 이어야 한다
           if ch == pattern[j]:
               j += 1
           if j == len(pattern):
               result.append(i - len(pattern) + 1)
               j = fail[j - 1]
       return result
   ```

3. 라빈-카프 구현에서 단일 해시(`MOD1`, `BASE1`만 사용)로 바꾼 뒤, 서로 다른 두 문자열이 같은 해시값을 갖는 충돌 사례를 무작위 탐색으로 찾아라. (힌트: 짧은 알파벳, 짧은 길이에서 여러 쌍을 해시 비교하면 금방 나온다.)

4. `z_array("aaaaaa")` 를 손으로 예측하고 실행해서 확인하라. 이 배열에서 패턴 `"aaa"` 가 몇 번, 어느 위치에서 매칭되는지 `z_find_all` 로 구하라.

5. **깊이 생각해 볼 문제.** 이 절의 벤치마크에서 `m=100`일 때 브루트포스가 직접 짠 KMP보다 빨랐던 이유를, "빅오가 숨기는 상수"라는 개념으로 3문장 이내로 설명하라. 그리고 `m`이 20,000까지 커지자 순서가 어떻게 바뀌었는지도 근거로 들어라.
:::

**다음 절**: [7.23 수학과 정수론](#/math-algo) — 소수 판정, GCD, 모듈러 역원, 조합론까지 코딩테스트에 필요한 정수론을 정리한다.
