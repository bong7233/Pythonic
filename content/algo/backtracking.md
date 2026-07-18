# 7.18 재귀와 백트래킹

::: lead
순열, 조합, 부분집합 — 코딩테스트에 나오는 "가능한 모든 경우를 살펴봐라"는 문제는 결국 재귀로 만든 탐색 트리를 훑는 일이다. 그런데 그 트리를 끝까지 다 훑으면 지수 시간이 나오고, 대부분은 시간 초과다. 백트래킹은 재귀에 딱 한 가지를 더한다 — **가망 없는 가지를 끝까지 가보기 전에 잘라낸다.** 이 절은 `itertools`로 순열을 뽑는 것과 직접 재귀를 짜는 것의 차이부터 시작해서, 그 차이가 왜 가지치기 때문에 생기는지, 그리고 N-Queen과 부분집합 합으로 그걸 실제로 체감하는 데까지 간다.
:::

## itertools로 되는 것과 안 되는 것

파이썬에서 순열과 조합은 이미 만들어져 있다.

```python title="itertools 기본"
from itertools import permutations, combinations

list(permutations([1, 2, 3]))
# [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]

list(combinations([1, 2, 3, 4], 2))
# [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]
```

이걸 직접 재귀로 짜면 다음과 같다. 결과가 실제로 같은지 먼저 검증한다.

```python title="직접 구현 vs itertools — 결과 대조"
import itertools

def perms_manual(arr):
    result = []
    path = []
    used = [False] * len(arr)

    def dfs():
        if len(path) == len(arr):
            result.append(tuple(path))  # 완성됐을 때만 저장
            return
        for i in range(len(arr)):
            if used[i]:
                continue
            used[i] = True
            path.append(arr[i])          # 선택
            dfs()                        # 탐색
            path.pop()                   # 되돌리기
            used[i] = False

    dfs()
    return result

arr = [1, 2, 3, 4]
a = sorted(perms_manual(arr))
b = sorted(itertools.permutations(arr))
print(a == b, len(a))
```

```pyrepl
>>> a == b, len(a)
(True, 24)
```

combinations도 마찬가지로 대조하면 일치한다(직접 실행해 확인했다 — `combs match: True 10 10`). 두 구현이 같은 답을 낸다면, **그럼 왜 굳이 직접 짜야 하는가?**

답은 하나다. **`itertools.permutations` 는 순열을 끝까지 다 만든 다음에야 넘겨준다. 만드는 도중에 "이 앞부분은 이미 틀렸다"고 중간에 그만둘 수 없다.** 길이 8짜리 순열을 만드는데 앞의 3개만 봐도 이미 조건 위반이 확정이라면, `itertools`는 그걸 몰라주고 나머지 5자리를 다 채워서 하나의 순열을 완성한 뒤에야 당신에게 넘긴다. 직접 재귀를 짜면 그 3개 시점에서 바로 포기하고 다음 가지로 넘어갈 수 있다. **이게 가지치기(pruning)이고, 가지치기가 필요한 순간이 바로 직접 구현해야 하는 순간이다.**

::: cote itertools를 써도 되는 경우 vs 안 되는 경우
- **모든 순열/조합을 어차피 다 만들어서 검사해야 한다** → `itertools`가 낫다. C로 구현되어 있어서 같은 로직을 파이썬 재귀로 짜는 것보다 빠르다.
- **완성되기 전에 가지를 쳐낼 수 있다** (지금까지 고른 것만 봐도 조건 위반이 확정된다) → 직접 재귀로 짜야 한다. 이 절 나머지가 전부 이 경우다.
- 판단 기준: 원소 개수가 10을 넘어가면 $10! = 3{,}628{,}800$, $12! \approx 4.8$억. `itertools`로 다 만들고 필터링하는 방식은 이 지점에서 죽는다. [7.1 복잡도](#/complexity)에서 본 "1초에 1억 번" 기준으로 감을 잡아라.
:::

## 백트래킹 템플릿: 선택 — 탐색 — 되돌리기

방금 짠 `perms_manual`이 이미 백트래킹의 뼈대를 담고 있다. 모든 백트래킹 코드는 이 세 동작의 반복이다.

```text nolines
dfs(상태)
├─ 종료 조건이면 답을 기록하고 return
└─ 각 선택지 c 에 대해:
    ├─ 1. 선택한다      (상태에 c 를 더한다)
    ├─ 2. 가지치기      (지금 상태로 답이 될 가능성이 있는가? 없으면 즉시 되돌리고 다음 c로)
    ├─ 3. 탐색한다      (dfs(다음 상태) 를 재귀 호출한다)
    └─ 4. 되돌린다      (상태에서 c 를 뺀다 — 다음 선택지를 시도하기 전에 원상복구)
```

```python title="백트래킹 표준 템플릿"
def backtrack(state):
    if is_goal(state):
        record(state)
        return
    for choice in candidates(state):
        if not is_valid(state, choice):   # 가지치기: 여기서 대부분 걸러진다
            continue
        apply(state, choice)              # 선택
        backtrack(state)                  # 탐색
        undo(state, choice)               # 되돌리기
```

`apply`와 `undo`가 항상 짝을 이뤄야 한다는 게 핵심이다. 리스트라면 `append`/`pop`, 집합이라면 `add`/`discard`, 카운터라면 `+= 1`/`-= 1`. 짝이 어긋나면 다음 가지를 탐색할 때 이전 선택의 흔적이 남아서 완전히 틀린 답을 낸다. 이건 디버깅하기 지독하게 어렵다 — 결과가 "가끔" 틀리기 때문이다.

::: danger 결과를 저장할 때 `path`를 그대로 넣으면 안 된다
[1.1 객체·이름·참조](#/objects-names)에서 배운 별칭(aliasing) 문제가 백트래킹에서 가장 흔하게 터지는 곳이다.

```python
# ❌ 흔한 실수
result = []
path = []

def dfs(...):
    if 종료:
        result.append(path)   # path 를 가리키는 이름표를 하나 더 추가했을 뿐
        return
    ...
    path.append(x)
    dfs(...)
    path.pop()
```

`result.append(path)`는 `path`의 **사본**을 넣는 게 아니라 **같은 리스트 객체에 이름표를 하나 더 붙이는 것**이다. 이후 `path.pop()`이나 `path.append()`가 실행되면 `result` 안에 저장해 둔 "그 답"도 같이 바뀐다. 재귀가 다 끝나고 나면 `result`에는 **똑같은 빈 리스트(혹은 마지막 상태)가 여러 개** 들어 있게 된다.

```python
# ✅ 스냅샷을 떠서 저장한다
result.append(path[:])       # 또는 list(path), path.copy()
```

튜플로 변환해서 저장해도 된다(`tuple(path)`) — 튜플은 불변이라 이후 `path`가 바뀌어도 영향받지 않는다. 위 `perms_manual`이 `result.append(tuple(path))`를 쓴 이유가 이거다.
:::

## 가지치기로 지수 시간을 실전에서 줄이는 법

가지치기가 없으면 백트래킹은 그냥 느린 완전 탐색이다. 가지치기가 있으면 같은 코드가 **탐색 트리의 대부분을 아예 만들지 않고 건너뛴다.** 부분집합 합 문제로 확인해 보자.

> 문제: 양의 정수 배열에서 합이 정확히 `target`이 되는 부분집합을 모두 찾아라.

가장 단순한 방법은 $2^n$개의 부분집합을 전부 만들어 합을 확인하는 것이다.

```python title="브루트포스 — 모든 부분집합 (2^n)"
def subset_sum_bruteforce(nums, target):
    n = len(nums)
    results = []
    for mask in range(1 << n):
        chosen = [nums[i] for i in range(n) if mask & (1 << i)]
        if sum(chosen) == target:
            results.append(chosen)
    return results
```

백트래킹 버전은 **정렬해 두고, 지금까지 고른 합이 이미 target을 넘으면 그 자리에서 포기한다.**

```python title="백트래킹 + 가지치기"
def subset_sum_backtrack(nums, target):
    nums = sorted(nums)
    results = []
    path = []

    def dfs(start, remain):
        if remain == 0:
            results.append(path[:])      # 스냅샷 — 위 danger 박스 참고
            return
        if remain < 0:
            return
        for i in range(start, len(nums)):
            if nums[i] > remain:
                break   # 정렬돼 있으므로 이 뒤는 전부 더 크다 → 더 볼 필요 없다
            if i > start and nums[i] == nums[i - 1]:
                continue  # 같은 깊이에서 중복값 건너뛰기 (중복 답 방지)
            path.append(nums[i])
            dfs(i + 1, remain - nums[i])
            path.pop()

    dfs(0, target)
    return results
```

두 함수가 같은 답을 내는지 먼저 확인했다.

```pyrepl
>>> nums = [2, 3, 6, 7, 1, 5, 4]
>>> subset_sum_match_result   # 두 함수의 결과를 정렬해서 비교
True
```

이제 정답이 같다는 걸 확인했으니 시간을 재보자. $n$을 늘려 가며 **서로 다른 값으로만 이루어진** 무작위 배열(`random.sample`로 뽑아 중복을 배제했다 — 이유는 바로 아래 danger 박스에)에 대해 `target = sum(nums) // 3`으로 실행했다.

```text nolines
n=16  brute= 0.0666s  backtrack=0.0023s   (약 29배)   count=12==12
n=18  brute= 0.2110s  backtrack=0.0063s   (약 33배)   count=38==38
n=20  brute= 1.0174s  backtrack=0.0274s   (약 37배)   count=146==146
n=22  brute= 4.6125s  backtrack=0.0928s   (약 50배)   count=399==399
n=24  brute=22.4369s  backtrack=0.3436s   (약 65배)   count=1718==1718
```

브루트포스는 $n$이 2 늘 때마다 시간이 대략 4배가 된다($2^n$이니까 당연하다). 백트래킹도 이론적 최악은 여전히 지수지만, **가지치기 조건(`nums[i] > remain`)이 실제 입력에서 탐색 트리의 대부분을 잘라낸다.** 배속이 $n$이 커질수록 계속 벌어지는 것도 같은 이유다. $n=30$이면 backtrack만으로 1초 안에 답이 나온다(브루트포스라면 $2^{30} \approx 10.7$억 번 — 어림도 없다. 바로 다음 절에서 실측한다).

::: perf 실측 (Python 3.14.5 / Windows). 절대 시간은 기기마다 다르지만 브루트포스와 백트래킹의 격차가 $n$에 따라 계속 벌어지는 추세는 어디서나 같다.
:::

::: danger 입력에 중복값이 섞이면 두 함수의 "카운트"가 서로 달라진다
위 표에서 `random.sample`로 서로 다른 값만 뽑은 이유가 있다. 만약 `random.randint(1, 30)`처럼 중복을 허용하는 방식으로 뽑으면(원소 30개 미만인데 값의 범위가 1~30이면 거의 확실히 중복이 낀다) 두 함수가 **더 이상 같은 개수를 세지 않는다.** 실제로 `random.seed(0)`에 `random.randint(1, 30)`을 $n$개씩 뽑아 실행하면:

```text nolines
n=16  brute_count=374    backtrack_count=209
n=18  brute_count=1117   backtrack_count=366
n=20  brute_count=4552   backtrack_count=1997
n=22  brute_count=13616  backtrack_count=3508
n=24  brute_count=57653  backtrack_count=4313
```

시간이 아니라 **답의 개수 자체가 다르다.** 원인은 `subset_sum_backtrack`의 `if i > start and nums[i] == nums[i - 1]: continue` 줄이다. 이 줄은 "같은 깊이에서 값이 같은 원소는 하나만 시도한다"는 뜻이라 **값 기준으로 같은 조합을 하나로 묶어 버린다.** 반면 `subset_sum_bruteforce`는 `mask`의 비트, 즉 **인덱스 기준**으로 부분집합을 센다 — 값이 같아도 인덱스가 다르면 다른 부분집합으로 취급한다. 예를 들어 `nums = [3, 3, 5]`에서 `target = 3`이면 brute는 `{nums[0]}`과 `{nums[1]}`을 별개로 세어 2를 반환하지만, backtrack은 dedup 로직 때문에 값 `3`을 딱 한 번만 시도해서 1을 반환한다.

즉 `subset_sum_backtrack`은 "**서로 다른 값의 조합**"을 세는 함수고, `subset_sum_bruteforce`는 "**서로 다른 인덱스의 조합**"을 세는 함수다 — 입력에 중복값이 없으면 둘은 같은 답을 내지만, 중복값이 있으면 다른 문제를 푸는 셈이 된다. 코딩테스트에서 "부분집합의 개수"를 물을 때 이게 인덱스 기준인지 값(멀티셋) 기준인지 문제를 꼼꼼히 읽어야 하는 이유가 이거다. 값 기준으로 세고 싶다면 지금의 dedup 로직이 맞고, 인덱스 기준(원소가 몇 번째인지까지 구별)으로 세고 싶다면 dedup 줄을 빼야 한다.
:::

::: warn 가지치기는 "정답이 이미 확정적으로 틀렸다"를 빨리 아는 것이다
`nums[i] > remain: break`가 되려면 **정렬이 먼저 되어 있어야 한다.** 정렬 안 된 배열에서 같은 조건을 넣으면 큰 수 하나가 앞에 있다는 이유만으로 뒤의 작은 수까지 못 보고 넘어가는 버그가 난다. 가지치기 조건 하나를 넣을 때마다 "이 조건이 성립하지 않는 입력이 있는가"를 늘 의심해라.
:::

## N-Queen — 가지치기의 정석 예제

$n \times n$ 체스판에 퀸 $n$개를 서로 공격하지 못하게 놓는 모든 방법을 찾는다. 브루트포스로 접근하면 이렇게 된다 — 각 행에 퀸을 하나씩 놓아야 하니, 열 배치는 $0 \ldots n-1$의 순열 하나에 대응한다. **모든 순열을 만들고, 그중 대각선이 겹치지 않는 것만 센다.**

```python title="브루트포스 — 순열을 전부 만들고 검사"
from itertools import permutations

def solve_nqueens_bruteforce(n):
    count = 0
    for perm in permutations(range(n)):     # perm[r] = r행 퀸의 열
        ok = True
        for r1 in range(n):
            for r2 in range(r1 + 1, n):
                if abs(perm[r1] - perm[r2]) == r2 - r1:   # 대각선 충돌
                    ok = False
                    break
            if not ok:
                break
        if ok:
            count += 1
    return count
```

이 코드는 순열을 $n!$개 다 만들고, 각각을 $O(n^2)$에 검사한다. 열 충돌은 순열 자체가 이미 막아 주지만, **대각선 충돌은 순열을 다 채운 뒤에야 확인할 수 있다.** 앞의 두 개만 놓아도 이미 대각선이 겹친 게 확정인데, 그 사실을 모르고 나머지 $n-2$자리를 계속 채운다 — 이게 딱 위에서 말한 "가지치기를 못 하는 상황"이다.

백트래킹은 **한 행씩 놓으면서, 그 즉시 열·대각선 충돌을 확인한다.** 충돌이면 그 자리에서 다음 열로 넘어가고, 아예 다음 행으로 내려가지 않는다.

```python title="백트래킹 N-Queen"
def solve_nqueens(n):
    count = 0
    cols = set()
    diag1 = set()   # 우상향 대각선: r - c 가 같으면 같은 대각선
    diag2 = set()   # 좌상향 대각선: r + c 가 같으면 같은 대각선

    def dfs(r):
        nonlocal count
        if r == n:
            count += 1
            return
        for c in range(n):
            if c in cols or (r - c) in diag1 or (r + c) in diag2:
                continue                    # 가지치기: 이 열에는 못 놓는다
            cols.add(c)
            diag1.add(r - c)
            diag2.add(r + c)
            dfs(r + 1)
            cols.discard(c)                 # 되돌리기
            diag1.discard(r - c)
            diag2.discard(r + c)

    dfs(0)
    return count
```

::: deep 왜 `r - c`와 `r + c`가 대각선을 나타내는가
체스판에서 같은 우상향 대각선(`↗`) 위의 칸들은 행이 늘어날 때 열도 똑같이 늘어난다 — 즉 `r - c`가 일정하다. 같은 좌상향 대각선(`↖`)은 행이 늘 때 열이 똑같이 줄어든다 — `r + c`가 일정하다. 그래서 이 두 값을 집합에 넣어 두면 $O(1)$ 만에 "이 칸이 기존 퀸과 같은 대각선인가"를 확인할 수 있다. 2차원 좌표 문제에서 대각선 판정이 필요할 때 자주 쓰는 관용구니 기억해 둬라.
:::

$n=4$일 때 첫 해를 그려 보면 이렇다 (실제로 코드를 돌려 얻은 결과다).

```text nolines
. Q . .
. . . Q
Q . . .
. . Q .
```

정답 개수가 맞는지 알려진 값과 대조했다.

```text nolines
n= 4: 백트래킹=2    (알려진 값 2)   일치
n= 8: 백트래킹=92   (알려진 값 92)  일치
n=10: 백트래킹=724  (알려진 값 724) 일치
```

그리고 브루트포스(순열 전수조사)와 백트래킹의 결과·시간을 직접 대조했다.

```text nolines
n= 6  brute=0.0002s  backtrack=0.0001s  speedup=  2.6x  count 4==4
n= 7  brute=0.0018s  backtrack=0.0003s  speedup=  6.1x  count 40==40
n= 8  brute=0.0144s  backtrack=0.0012s  speedup= 12.4x  count 92==92
n= 9  brute=0.1501s  backtrack=0.0047s  speedup= 31.8x  count 352==352
n=10  brute=1.5426s  backtrack=0.0219s  speedup= 70.3x  count 724==724
```

배속(speedup)이 $n$이 늘어날수록 **계속 커진다.** 브루트포스는 $n!$을 다 도니 $n=10 \to 11$이면 시간이 약 11배가 되지만, 백트래킹은 애초에 유효하지 않은 가지의 대부분을 만들지도 않으므로 훨씬 완만하게 증가한다. 실제로 $n=11$은 백트래킹으로 0.11초, $n=12$는 0.58초에 끝난다 — 브루트포스로 $n=12$를 하려면 $12! \approx 4.79$억 개의 순열을 만들어야 하니 애초에 시도할 게 못 된다.

::: cote 백준·프로그래머스에서 N-Queen류 문제의 신호
- 제약이 "$N \le 12$ 안팎"이면 백트래킹으로 충분하다는 신호다. $N \le 20$ 근처면서 "부분집합/조합을 고른다"는 형태면 이 절의 가지치기 패턴(정렬 후 break, 집합으로 O(1) 충돌 확인)을 의심해라.
- **행마다 하나씩 놓는다는 제약 자체가 이미 가지치기다.** "전체 좌표 중 $k$개를 고른다"보다 "각 행에 하나씩 고른다"로 문제를 재구성할 수 있으면 탐색 공간이 $\binom{n^2}{n}$에서 $n^n$, 다시 열·대각선 조건으로 $n!$대까지 줄어든다. 문제를 어떻게 모델링하느냐가 가지치기의 절반이다.
:::

## 부분집합 합, 다시 — 백트래킹이 안 통하는 지점

앞서 본 부분집합 합은 가지치기가 잘 먹혔다. 그런데 **가지치기를 아무리 잘해도 지수 시간을 벗어나지 못하는 경우가 있다.** 배열 원소가 100개, 200개로 늘어나면 얘기가 달라진다.

```pyrepl
>>> # n=30, nums = [random.randint(1, 30) for _ in range(30)], target = sum // 3
>>> # backtrack만 실행: 0.96초, 답 100,509개
>>> # n=40, nums = [random.randint(1, 30) for _ in range(40)], target = sum // 6
>>> # backtrack만 실행: 0.63초, 답 122,173개
```

$n=40$이 $n=30$보다 시간이 짧게 나온 게 이상해 보이겠지만, `target = sum // 6`으로 목표를 더 작게 잡았기 때문이다 — 탐색 트리 깊이(고를 수 있는 원소 수)와 남은 target의 크기가 같이 줄어서 가지치기가 더 일찍 걸린다. **가지치기가 있어도 답의 개수 자체는 여전히 십만~수십만 단위로 크다.** 답을 전부 나열해야 하는 문제라면 이건 어쩔 수 없다 — 답이 백만 개면 출력만 해도 시간이 걸린다. 하지만 "부분집합이 존재하는가"나 "몇 개인가"만 물어보는 문제라면, **경로 자체를 저장할 필요가 없다.** 그러면 `(인덱스, 남은 target)` 조합마다 답이 하나로 정해지므로 같은 부분 문제를 반복해서 풀 이유가 없어진다 — 이게 바로 메모이제이션이고, 백트래킹에 그걸 더하면 동적계획법이 된다. [7.20 동적계획법 기초](#/dp-basics)에서 바로 이 문제를 이어서 최적화한다.

::: tip 백트래킹과 DP를 가르는 기준
- **모든 경우를 나열해야 한다** (순열 자체, N-Queen의 각 배치, 존재하는 모든 부분집합) → 백트래킹. 답의 개수만큼 시간이 드는 건 피할 수 없다.
- **개수·최적값만 필요하고, 부분 문제가 겹친다** (부분집합의 개수, 최소 비용) → 메모이제이션/DP로 지수 시간을 다항 시간으로 낮출 수 있다.
- 같은 재귀 구조라도 "뭘 묻는가"에 따라 갈 길이 갈린다는 걸 기억해라.
:::

## 재귀 깊이라는 숨은 제약

백트래킹은 재귀다. 파이썬은 재귀 깊이에 기본 한도가 있다.

```pyrepl
>>> import sys
>>> sys.getrecursionlimit()
1000
```

$n=1000$짜리 배열을 원소마다 하나씩 재귀로 파고드는 백트래킹(예: 각 원소를 넣을지 말지 결정하며 내려가는 형태)을 짜면 재귀 깊이가 $n$에 비례한다. $n$이 커지면 이 한도에 걸린다.

::: danger RecursionError를 만나는 흔한 패턴
```python
def dfs(i, path):
    if i == len(nums):        # 매 원소마다 재귀 한 단계
        ...
        return
    dfs(i + 1, path + [nums[i]])
    dfs(i + 1, path)

dfs(0, [])   # len(nums) 가 1000을 넘으면 RecursionError
```

이런 "포함/제외를 각 원소마다 결정"하는 형태는 재귀 깊이가 원소 개수만큼 쌓인다. `sys.setrecursionlimit(...)`로 한도를 올릴 수는 있지만 **근본 해법이 아니다.** 스택 프레임 자체가 파이썬에서 가볍지 않고(각 프레임에 지역 변수, 반환 주소 등이 쌓인다), 한도를 무작정 올리면 실제 C 스택이 넘쳐 인터프리터가 죽는다(`Segmentation fault`) — 파이썬 예외로도 못 잡는다. 깊이가 입력 크기에 비례하는 백트래킹을 큰 입력에 그대로 쓰기 전에, 반복문으로 바꾸거나(명시적 스택) 문제 자체를 가지치기로 얕게 만들 수 있는지부터 봐라. [8.3 시간 초과를 피하는 관용구](#/tle)에서 재귀를 반복문으로 바꾸는 패턴을 더 다룬다.
:::

## 종합: 코딩테스트에서 백트래킹을 알아보는 법

지금까지의 내용을 실전 판단 순서로 정리하면 이렇다.

1. "모든 경우의 수를 나열/세라"는 문제인가? → 순열/조합/부분집합 후보.
2. 원소 개수가 10~12개를 넘고 완전 탐색이 그대로는 안 될 것 같은가? → 가지치기가 필요하다는 신호. `itertools`로 끝까지 만들고 거르는 방식은 늦다.
3. 지금까지 고른 것만 보고 "이미 틀렸다"를 판단할 수 있는 조건이 있는가? (정렬 후 초과, 집합으로 O(1) 충돌 확인 등) → 그게 이 문제의 가지치기 조건이다.
4. 답의 개수 자체가 아니라 "존재하는가/최적값은?"만 묻는가? → 메모이제이션으로 DP화할 수 있는지 의심해라.

이 판단 순서는 [8.4 문제 유형 분류와 신호 읽기](#/problem-signals)와 [8.1 코딩테스트의 구조와 전략](#/cote-strategy)에서 제약 조건만 보고 알고리즘을 역추론하는 훈련으로 이어진다.

## 요약

- `itertools.permutations`/`combinations`는 결과를 끝까지 만든 뒤에야 넘겨준다. **완성 전에 가지를 쳐낼 수 있으면 직접 재귀로 짜야 한다.**
- 백트래킹의 뼈대는 **선택 → 탐색 → 되돌리기**다. `apply`와 `undo`는 항상 짝을 맞춘다.
- 결과를 저장할 때 `path`를 그대로 넣으면 안 된다. **`path[:]`나 `tuple(path)`로 스냅샷을 떠서 저장해라** — 안 그러면 별칭 문제로 저장된 답이 나중에 같이 바뀐다.
- 가지치기는 "지금까지 고른 것만 봐도 이미 답이 될 수 없다"를 빨리 판단하는 조건이다. 정렬 후 초과분 자르기, 집합으로 O(1) 충돌 확인이 대표적이다.
- 실측으로 확인했듯, 가지치기가 있는 백트래킹은 브루트포스보다 격차가 입력이 커질수록 계속 벌어진다. 하지만 최악의 경우 여전히 지수 시간이다 — 답의 개수 자체가 많으면 어쩔 수 없다.
- 답의 개수가 아니라 존재 여부·최적값만 필요하면 메모이제이션으로 DP화해서 지수 시간을 다항 시간으로 낮출 수 있다.
- 재귀 깊이가 입력 크기에 비례하는 백트래킹은 큰 입력에서 `RecursionError`나 스택 오버플로를 만난다.

::: quiz 연습문제
1. 아래 코드는 순열을 만들어 `results`에 저장하려 한다. 실행하면 왜 빈 리스트들만 잔뜩 쌓이는가? 고쳐라.

   ```python
   def perms(arr):
       results = []
       path = []
       used = [False] * len(arr)

       def dfs():
           if len(path) == len(arr):
               results.append(path)
               return
           for i in range(len(arr)):
               if used[i]:
                   continue
               used[i] = True
               path.append(arr[i])
               dfs()
               path.pop()
               used[i] = False

       dfs()
       return results
   ```

2. `subset_sum_backtrack`에서 `if nums[i] > remain: break`를 `if nums[i] > remain: continue`로 바꾸면 정답이 여전히 맞는가, 틀린가? 왜 `break`가 `continue`보다 나은가?

3. N-Queen 코드에서 `diag1 = set()`(r - c) 대신 `diag1 = []`(리스트)를 쓰고 `in` 연산자로 확인하면 정답은 똑같이 나온다. 그런데 왜 큰 $n$에서 느려지는가? [7.6 해시](#/hashing)를 참고해서 설명하라.

4. 부분집합 합 문제를 "포함/제외 방식"(각 원소마다 넣을지 말지 재귀로 결정)으로 다시 짜 보고, 정렬 후 `break`로 가지치기하는 버전과 실행 시간을 실제로 비교하라. 어느 쪽이 더 가지치기하기 쉬운가?

5. $n=8$ N-Queen에서 백트래킹이 실제로 만드는 탐색 트리의 노드 수를 `dfs` 안에 카운터를 추가해서 세어 보라. $8! = 40320$과 비교하면 몇 퍼센트나 가지치기로 건너뛰었는가?
:::

**다음 절**: [7.19 그리디](#/greedy) — 모든 경우를 보지 않고도 최적해를 보장할 수 있는 건 언제인가.
