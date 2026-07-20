# 3.2 itertools 완전 정복

::: lead
[1.18 이터레이터](#/iterators)에서 이터레이터 프로토콜을 봤다. `__iter__`, `__next__`, `StopIteration` — 이 세 가지만 있으면 게으른 시퀀스를 만들 수 있다는 것도 배웠다. `itertools` 는 그 프로토콜 위에 지은 **표준 부품 창고**다. 전부 C로 구현돼 있고, 전부 게으르고, 조합하면 왠만한 반복문을 대체한다. 그런데 부품이 많으면 잘못 쓰기도 쉽다. 이 절은 각 부품이 정확히 무엇을 계산하는지, 어디서 틀리는지, 손으로 만들면 왜 느린지를 실행으로 증명한다.
:::

## 무한 이터레이터 — count, cycle, repeat

세 함수 모두 **끝이 없다.** `list()` 로 감싸면 프로그램이 멈추는 게 아니라 **메모리가 터질 때까지 안 멈춘다.** 그래서 항상 `islice` 나 `break` 와 짝지어 쓴다.

```pyrepl
>>> import itertools
>>> list(itertools.islice(itertools.count(10, 5), 4))     # 10부터 5씩
[10, 15, 20, 25]
>>> list(itertools.islice(itertools.cycle("abc"), 7))     # 무한 반복
['a', 'b', 'c', 'a', 'b', 'c', 'a']
>>> list(itertools.repeat("x", 3))                        # 3번만
['x', 'x', 'x']
```

`repeat` 은 두 얼굴을 가진다. **횟수를 주면 유한**, 안 주면 무한이다.

```pyrepl
>>> list(itertools.repeat("x", 3))
['x', 'x', 'x']
>>> r = itertools.repeat("x")
>>> next(r), next(r), next(r)
('x', 'x', 'x')
```

무한이라고 해서 메모리를 많이 쓰는 게 아니다. 오히려 정반대다.

```pyrepl
>>> import sys
>>> sys.getsizeof(itertools.count())
56
>>> sys.getsizeof(itertools.cycle([1, 2, 3]))
64
>>> sys.getsizeof(itertools.repeat(1))
48
```

**무한 수열이 56바이트, 64바이트다.** [1.18 이터레이터](#/iterators)에서 `range` 가 48바이트였던 것과 같은 이유다 — 값을 저장하는 게 아니라 *"다음 값을 어떻게 계산하는지"* 만 들고 있다.

::: deep cycle 은 사실 저장을 한다 — 원본이 이터레이터일 때
`cycle` 의 초기 크기가 `count`/`repeat` 보다 큰 이유가 있다. **첫 바퀴를 도는 동안 값을 내부 버퍼에 저장해 두고, 두 바퀴째부터는 그 버퍼를 재생한다.**

```pyrepl
>>> import itertools
>>> def source():
...     print("소스에서 값 생성")
...     yield 1
...     yield 2
...
>>> c = itertools.cycle(source())
>>> [next(c) for _ in range(5)]
소스에서 값 생성
[1, 2, 1, 2, 1]
```

`소스에서 값 생성` 이 **딱 한 번만** 찍힌다. `print` 는 `source()` 함수 본문 맨 위, 첫 `yield` 이전에 딱 한 줄 있을 뿐이다. 첫 `next(c)` 호출이 그 `print` 를 실행하고 `yield 1` 에서 멈추고, 두 번째 `next(c)` 는 실행을 재개해 `yield 2` 로 갈 뿐이라 이 경로에는 `print` 가 없다. 세 번째 `next(c)` 가 원본을 끝까지 소진시켜 `StopIteration` 을 일으키고, 그 순간 `cycle` 이 버퍼 재생 모드로 전환된다. 그다음부터는 원본을 다시 부르지 않고 **저장해 둔 값을 그대로 돌려준다.** 원본이 무한이 아니라 유한한 제너레이터여도 `cycle` 이 동작하는 이유가 이거다 — 원본을 한 번 다 읽고 나면, 그다음부터는 버퍼만 순회한다.

그래서 원본이 크면 `cycle` 도 그만큼의 메모리를 먹는다. **"무한"이 "공짜"는 아니다.**
:::

::: danger 무한 이터레이터를 그냥 순회하면 멈추지 않는다
```python
for x in itertools.count():     # ❌ 프로그램이 안 끝난다
    print(x)
```

`islice`, `takewhile`, 또는 명시적 `break` 없이 무한 이터레이터를 `for`나 `list()`에 넣지 마라. 코딩테스트에서 흔한 실수는 종료 조건 없는 `count()` 를 인덱스 생성기로 쓰다가 시간 초과가 아니라 **무한 루프로 채점 자체가 안 끝나는** 경우다.

```python
for i, x in zip(itertools.count(), data):     # ✅ zip이 짧은 쪽에서 끝난다
    ...
```
:::

## chain, islice, tee — 이어붙이기·자르기·복제

### chain — 여러 이터러블을 하나처럼

```pyrepl
>>> list(itertools.chain([1, 2], [3], (4, 5)))
[1, 2, 3, 4, 5]
>>> list(itertools.chain.from_iterable([[1, 2], [3], [4, 5]]))     # 리스트의 리스트
[1, 2, 3, 4, 5]
```

`chain` 은 **새 리스트를 만들지 않는다.** 각 이터러블을 순서대로 훑을 뿐이다. 리스트를 `+` 로 이어 붙이는 것과 비교하면 차이가 분명해진다.

::: perf `+` 이어붙이기 vs chain — 81배
길이 1000짜리 리스트 1000개를 이어 붙였다.

```python title="concat_bench.py"
import itertools, timeit

lists = [list(range(1000)) for _ in range(1000)]

def via_plus():
    out = []
    for lst in lists:
        out = out + lst          # 매번 새 리스트를 통째로 복사
    return out

def via_chain():
    return list(itertools.chain.from_iterable(lists))

t1 = timeit.timeit(via_plus, number=5)
t2 = timeit.timeit(via_chain, number=5)
print(f"'+' concat: {t1:.4f}s  chain: {t2:.4f}s  ratio: {t1/t2:.1f}x")
```

```text nolines
'+' concat: 3.9475s  chain: 0.0486s  ratio: 81.2x
```

(Python 3.14.5 / Windows 기준 실측)

`out = out + lst` 는 [1.1 객체, 이름, 참조](#/objects-names)에서 본 **불변 시퀀스의 재할당**과 똑같은 함정이다. 매번 지금까지 쌓인 전체를 새로 복사한다. 1000번 반복하면 $O(n^2)$ 로 터진다. `chain` 은 각 조각을 그 자리에서 읽기만 하니 $O(n)$ 이다.
:::

### islice — 슬라이싱을 이터레이터에

`lst[2:8:2]` 는 리스트에서만 된다. 이터레이터에는 `[]` 슬라이싱이 없다. `islice` 가 그 자리를 채운다.

```pyrepl
>>> list(itertools.islice(range(10), 2, 8, 2))
[2, 4, 6]
>>> list(itertools.islice(range(10), 5))          # 시작 생략 = 처음부터
[0, 1, 2, 3, 4]
```

::: warn islice 는 음수 인덱스를 못 받는다
`lst[-3:]` 같은 건 `islice` 로 안 된다. **한 방향으로만, 앞에서부터** 셀 수 있다. 이터레이터는 뒤에서 몇 번째인지 미리 알 방법이 없기 때문이다 — 끝까지 가 봐야 안다. 뒤쪽 몇 개가 필요하면 `collections.deque(it, maxlen=n)` 으로 구체화하는 게 맞다.
:::

### tee — 복제는 공짜가 아니다

`itertools.tee(it, n)` 은 이터레이터 하나를 `n` 개로 나눠 준다. 이름과 달리 **원본을 실제로 복사하지 않는다.** 대신 내부에 버퍼를 두고, 느린 쪽이 아직 안 읽은 값을 쌓아 둔다. 손으로 만들면 이 구조가 보인다.

```python title="tee 의 핵심 아이디어를 그대로 재현"
from collections import deque

def tee_simple(iterable, n=2):
    it = iter(iterable)
    queues = [deque() for _ in range(n)]

    def gen(q):
        while True:
            if not q:                     # 내 버퍼가 비었으면
                try:
                    val = next(it)          # 원본에서 하나 꺼내
                except StopIteration:
                    return                  # 원본이 끝났으면 나도 끝낸다
                for other in queues:
                    other.append(val)      # 모두의 버퍼에 나눠준다
            yield q.popleft()

    return tuple(gen(q) for q in queues)


a, b = tee_simple([1, 2, 3, 4, 5])
print(next(a), next(a), next(a))    # 1 2 3  — a가 먼저 치고 나간다
print(list(b))                      # [1, 2, 3, 4, 5]  — b는 버퍼에서 그대로 다 받는다
```

```text nolines
1 2 3
[1, 2, 3, 4, 5]
```

`except StopIteration: return` 이 빠지면 안 된다. 원본이 소진된 뒤 `next(it)` 이 던지는 `StopIteration` 을 잡지 않고 그대로 두면, 그 예외가 제너레이터 `gen` 밖으로 새어 나가는 순간 [PEP 479](https://peps.python.org/pep-0479/)에 의해 `RuntimeError: generator raised StopIteration` 으로 바뀌어 프로그램이 죽는다 — `list(b)` 가 조용히 값을 다 내주는 게 아니라 그 자리에서 크래시가 난다. 원본이 끝났다는 신호를 `try/except` 로 받아 `return` 으로 바꿔 줘야 제너레이터가 정상적으로 끝난다. 이 처리를 넣은 뒤에야 진짜 `itertools.tee` 로 똑같은 코드를 돌린 것과 **한 글자도 다르지 않은 결과**가 나온다. `a` 가 앞서 나가는 동안 `a` 가 이미 읽은 값들이 `b` 의 버퍼에 쌓여 있다가, `b` 가 나중에 그 버퍼에서 꺼내 가는 것이다.

이 구조를 알면 [1.18 이터레이터](#/iterators)에서 실측했던 사실이 당연해진다. **한쪽만 끝까지 읽고 다른 쪽을 안 읽으면, 버퍼가 원본 전체 크기만큼 쌓인다.** `tee` 는 *"두 갈래가 비슷한 속도로 나란히 전진할 때"* 만 이득이다. 한쪽을 몰아서 다 쓸 거면 차라리 `list(it)` 을 한 번 만들고 그 리스트를 두 번 순회하는 게 낫다.

## groupby의 함정 — 정렬 안 된 입력에서 실제로 틀린다

`groupby` 는 *"키가 바뀌는 지점마다 새 그룹을 시작한다."* **정렬해서 같은 키를 모아 주는 게 아니다.** 이 오해가 실무에서 가장 흔한 버그를 만든다. 직접 확인해 보자.

```pyrepl
>>> import itertools
>>> data = [("a", 1), ("b", 2), ("a", 3)]
>>> [(k, list(g)) for k, g in itertools.groupby(data, key=lambda x: x[0])]
[('a', [('a', 1)]), ('b', [('b', 2)]), ('a', [('a', 3)])]
```

**`"a"` 그룹이 두 개 나왔다.** `[('a', 1), ('a', 3)]` 하나로 합쳐질 거라 기대했다면 틀렸다. `groupby` 는 리스트 전체를 보고 같은 키를 찾아 모으는 게 아니라, **바로 직전 원소의 키와만 비교**하며 지나간다. 정렬해서 넣으면 원하는 결과가 나온다.

```pyrepl
>>> data_sorted = sorted(data, key=lambda x: x[0])
>>> [(k, list(g)) for k, g in itertools.groupby(data_sorted, key=lambda x: x[0])]
[('a', [('a', 1), ('a', 3)]), ('b', [('b', 2)])]
```

말로만 하지 말고 `groupby` 를 직접 만들어서, 이게 정말 *"직전 키와만 비교"* 하는 알고리즘인지 증명해 보자.

```python title="groupby_simple.py — 표준 라이브러리와 동일하게 동작함을 증명"
def groupby_simple(iterable, key=None):
    key = key or (lambda x: x)
    it = iter(iterable)
    try:
        current_value = next(it)
    except StopIteration:
        return
    current_key = key(current_value)
    current_group = [current_value]
    for value in it:
        k = key(value)
        if k == current_key:               # 직전 키와 같으면 같은 그룹
            current_group.append(value)
        else:                               # 다르면 지금까지 그룹을 내보내고 새로 시작
            yield current_key, current_group
            current_key = k
            current_group = [value]
    yield current_key, current_group


import itertools

real = [(k, list(g)) for k, g in itertools.groupby("aabbba")]
mine = list(groupby_simple("aabbba"))
print(real)
print(mine)
print(real == mine)
```

```text nolines
[('a', ['a', 'a']), ('b', ['b', 'b', 'b']), ('a', ['a'])]
[('a', ['a', 'a']), ('b', ['b', 'b', 'b']), ('a', ['a'])]
True
```

10줄짜리 순수 파이썬 코드가 C 구현과 **한 글자도 다르지 않은 출력**을 낸다. `groupby` 에는 정렬 기능도, 되돌아보는 기능도 없다. 지금 보고 있는 원소와 바로 전 원소의 키만 비교하는 **단순 순차 스캔**이다.

::: cote 코딩테스트 포인트
`groupby` 를 쓸 거면 **먼저 정렬하라.** 대부분의 코테 문제에서 "같은 값끼리 묶기"를 원한다면 이게 필수 순서다.

```python
# ❌ 원본 순서 그대로 groupby — 같은 키가 흩어져 있으면 여러 그룹으로 쪼개진다
groups = itertools.groupby(records, key=lambda r: r.category)

# ✅ 키 기준으로 정렬한 뒤 groupby
records.sort(key=lambda r: r.category)
groups = itertools.groupby(records, key=lambda r: r.category)
```

이미 정렬돼 있다고 확신할 수 있는 입력(연속된 로그, 이미 그룹 단위로 온 데이터)이 아니라면 **정렬을 생략하지 마라.** 대신 이미 정렬돼 있다는 게 보장된 상황(예: 문자열의 연속 문자 압축, `run-length encoding`)에서는 `groupby` 가 정확히 맞는 도구다.
:::

::: danger groupby 의 그룹은 오래 들고 있으면 안 된다
`groupby` 가 반환하는 각 그룹은 **자기 자신만의 독립된 리스트가 아니라, 원본 이터레이터를 공유하는 부분 뷰**다. 바깥 이터레이터를 먼저 앞으로 돌리면, 이전 그룹은 **조용히 비어 버린다.**

```pyrepl
>>> g = itertools.groupby("aaabbbccc")
>>> first_key, first_group = next(g)
>>> second_key, second_group = next(g)      # 바깥을 한 번 더 진행시켰다
>>> first_key, list(first_group)            # first_group 은 이미 죽었다
('a', [])
```

`first_group` 을 `list()` 로 감싸도 **빈 리스트**만 나온다. `second_key` 를 꺼내는 순간 `groupby` 내부가 `"a"` 그룹을 버리고 `"b"` 로 넘어갔기 때문이다.

**규칙**: 그룹을 즉시 `list()` 로 소비하거나, 다음 그룹으로 넘어가기 전에 지금 그룹을 다 써라.

```python
# ✅ 각 그룹을 즉시 리스트로 굳힌다
result = [(k, list(g)) for k, g in itertools.groupby(data)]
```
:::

## 조합론 4형제: product, permutations, combinations, combinations_with_replacement

네 함수는 전부 *"원소들을 어떻게 뽑아 배열하는가"* 를 다루는데, **순서를 따지는지, 중복을 허용하는지**로 갈린다.

| 함수 | 순서 따짐? | 중복(자기 자신 재선택) 허용? | 개수 공식 |
| --- | --- | --- | --- |
| `product(items, repeat=r)` | O | O | $n^r$ |
| `permutations(items, r)` | O | X | $\dfrac{n!}{(n-r)!}$ |
| `combinations(items, r)` | X | X | $\dbinom{n}{r} = \dfrac{n!}{r!(n-r)!}$ |
| `combinations_with_replacement(items, r)` | X | O | $\dbinom{n+r-1}{r}$ |

`n=3, r=2` 로 넷을 나란히 찍어서 눈으로 차이를 확인하자.

```pyrepl
>>> items = ["a", "b", "c"]
>>> list(itertools.product(items, repeat=2))
[('a', 'a'), ('a', 'b'), ('a', 'c'), ('b', 'a'), ('b', 'b'), ('b', 'c'), ('c', 'a'), ('c', 'b'), ('c', 'c')]
>>> list(itertools.permutations(items, 2))
[('a', 'b'), ('a', 'c'), ('b', 'a'), ('b', 'c'), ('c', 'a'), ('c', 'b')]
>>> list(itertools.combinations(items, 2))
[('a', 'b'), ('a', 'c'), ('b', 'c')]
>>> list(itertools.combinations_with_replacement(items, 2))
[('a', 'a'), ('a', 'b'), ('a', 'c'), ('b', 'b'), ('b', 'c'), ('c', 'c')]
```

개수는 각각 9, 6, 3, 6개다. 공식으로도 확인된다.

```pyrepl
>>> import math
>>> math.perm(3, 2)              # permutations 개수
6
>>> math.comb(3, 2)              # combinations 개수
3
>>> math.comb(3 + 2 - 1, 2)      # combinations_with_replacement 개수
6
>>> 3 ** 2                       # product 개수
9
```

차이를 결과로 구분하는 법: `("a","b")` 와 `("b","a")` 가 **둘 다 나오면 순서를 따진다**(product, permutations). `("a","a")` 처럼 **같은 원소가 반복되면 중복을 허용한다**(product, combinations_with_replacement).

::: cote 조합론적 폭발을 얕보지 마라
```pyrepl
>>> import math
>>> math.factorial(10)
3628800
>>> len(list(itertools.permutations(range(10))))
3628800
```

$n=10$ 짜리 순열이 벌써 362만 개다. $n=12$ 면 4억7900만 개를 넘는다. `permutations`/`product` 를 코딩테스트에 쓸 때는 **먼저 $n$ 과 $r$ 을 보고 몇 개가 나올지 계산해라.** 계산 없이 돌리면 메모리와 시간 둘 다 터진다.

가지치기가 필요한 진짜 조합 탐색 문제는 여기 대신 [7.18 재귀와 백트래킹](#/backtracking)의 도구를 써야 한다 — 조건을 만족 못 하는 가지를 **만들기 전에 잘라내는** 것과, `itertools` 로 **다 만들고 나서 거르는** 것은 완전히 다른 시간 복잡도다. 순수 조합론 계산(조합의 개수, 모듈러 이항계수 등)은 [7.23 수학과 정수론](#/math-algo)에서 다룬다.
:::

## accumulate — 누적은 덧셈만이 아니다

`accumulate` 의 기본값은 누적합이다. 그런데 두 번째 인자로 **어떤 이항 함수든** 줄 수 있다.

```pyrepl
>>> list(itertools.accumulate([1, 2, 3, 4]))                 # 누적합
[1, 3, 6, 10]
>>> import operator
>>> list(itertools.accumulate([1, 2, 3, 4], operator.mul))   # 누적곱
[1, 2, 6, 24]
>>> list(itertools.accumulate([3, 1, 4, 1, 5, 9, 2, 6], max)) # 지금까지의 최댓값
[3, 3, 4, 4, 5, 9, 9, 9]
```

`initial` 매개변수(3.8+)는 시작값을 앞에 붙인다.

```pyrepl
>>> list(itertools.accumulate([1, 2, 3, 4], initial=100))
[100, 101, 103, 106, 110]
```

`initial` 이 있으면 출력 길이가 입력보다 **하나 많다.** 입력이 빈 경우에도 `initial` 하나는 나온다는 뜻이라, 빈 시퀀스에서 예외 없이 안전하게 시작값을 다루고 싶을 때 쓴다.

::: perf accumulate vs 손으로 쓴 루프 — 1.4배
```python title="accumulate_bench.py"
import itertools, timeit

big = list(range(1, 200_001))

def manual_accum(seq):
    total = 0
    out = []
    for x in seq:
        total += x
        out.append(total)
    return out

t1 = timeit.timeit(lambda: list(itertools.accumulate(big)), number=20)
t2 = timeit.timeit(lambda: manual_accum(big), number=20)
print(f"accumulate: {t1:.4f}s  manual: {t2:.4f}s  ratio: {t2/t1:.2f}x")
```

```text nolines
accumulate: 0.0989s  manual: 0.1376s  ratio: 1.39x
```

(Python 3.14.5 / Windows 기준 실측)

`permutations` 의 24배(뒤에서 본다)에 비하면 **소박한 차이다.** 손으로 쓴 루프도 이미 단순한 `+=` 와 `append` 뿐이라 C 구현이 이길 여지가 크지 않다. **`itertools` 가 항상 극적으로 빠른 건 아니다.** 반복 로직 자체가 복잡할수록(순열 생성처럼 상태 추적이 많을수록) C 구현의 이득이 커진다.
:::

## itertools 레시피: pairwise와 batched

공식 문서의 "Itertools Recipes" 절에는 **표준 라이브러리에 없던 시절 사람들이 직접 조립해 쓰던 코드**가 있다. 그중 둘은 나중에 정식으로 채택됐다.

### pairwise (3.10+)

```pyrepl
>>> list(itertools.pairwise([1, 2, 3, 4]))
[(1, 2), (2, 3), (3, 4)]
```

3.10 이전에는 이렇게 조립했다. `tee` 로 둘로 나누고, 한쪽만 하나 앞서가게 만든 뒤 `zip` 으로 묶는다.

```python title="pairwise 레시피 — 3.10 이전 관용구"
def pairwise_recipe(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)          # b만 한 칸 앞으로
    return zip(a, b)


print(list(pairwise_recipe([1, 2, 3, 4])) == list(itertools.pairwise([1, 2, 3, 4])))
```

```text nolines
True
```

### batched (3.12+)

```pyrepl
>>> list(itertools.batched("abcdefg", 3))
[('a', 'b', 'c'), ('d', 'e', 'f'), ('g',)]
```

이건 [1.18 이터레이터](#/iterators)에서 본 `zip(it, it, it)` 관용구를 대체하려고 만든 함수다. 원리는 단순하다. `islice` 로 `n` 개씩 떼어 오다가, 뗄 게 없으면 멈춘다.

```python title="batched 레시피 — 3.12 이전 관용구"
def batched_recipe(iterable, n):
    if n < 1:
        raise ValueError("n must be >= 1")
    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch


print(list(batched_recipe("abcdefg", 3)) == list(itertools.batched("abcdefg", 3)))
```

```text nolines
True
```

`walrus`(`:=`) 로 *"다음 n개를 떼어 오고, 그게 비었으면 멈춘다"* 를 한 줄로 표현한다. 마지막 조각이 `n` 보다 짧을 수 있다는 게 기본 동작인데, 이게 싫으면 `strict=True` 를 준다.

```pyrepl
>>> list(itertools.batched("abcdefg", 3, strict=True))
Traceback (most recent call last):
  ...
ValueError: batched(): incomplete batch
```

`strict=True` 는 **입력 길이가 배치 크기의 배수라고 확신할 때**만 켜라. 배치 처리 파이프라인에서 마지막 조각이 잘려 나가면 안 되는 경우(예: 고정 길이 레코드 파싱) 조용히 짧은 배치를 받는 것보다 예외로 즉시 아는 게 낫다.

## 왜 itertools가 빠른가 — 실측

`itertools` 를 쓰는 이유가 항상 "메모리 절약"인 건 아니다. **같은 알고리즘을 순수 파이썬으로 짜는 것보다 빠르기도 하다.** `permutations` 로 확인해 보자. CPython의 `permutations` 는 Heap's algorithm 계열의 인덱스 순환 방식을 C로 구현한다. 같은 알고리즘을 파이썬으로 그대로 옮겨서 비교했다.

```python title="permutations_bench.py"
import itertools, timeit

def perm_py(pool, r=None):
    pool = list(pool)
    n = len(pool)
    r = n if r is None else r
    if r > n:
        return
    indices = list(range(n))
    cycles = list(range(n, n - r, -1))
    yield tuple(pool[i] for i in indices[:r])
    while n:
        for i in reversed(range(r)):
            cycles[i] -= 1
            if cycles[i] == 0:
                indices[i:] = indices[i + 1:] + indices[i:i + 1]
                cycles[i] = n - i
            else:
                j = cycles[i]
                indices[i], indices[-j] = indices[-j], indices[i]
                yield tuple(pool[i] for i in indices[:r])
                break
        else:
            return


data = list(range(8))
t1 = timeit.timeit(lambda: list(itertools.permutations(data)), number=20)
t2 = timeit.timeit(lambda: list(perm_py(data)), number=20)
print(f"itertools: {t1:.4f}s  pure-python: {t2:.4f}s  ratio: {t2/t1:.1f}x")
```

```text nolines
itertools: 0.0267s  pure-python: 0.6617s  ratio: 24.8x
```

(Python 3.14.5 / Windows 기준 실측. 같은 알고리즘, 같은 출력. 차이는 순전히 **C 함수 호출 대 파이썬 바이트코드 실행**이다. 같은 스크립트를 이 환경에서 3회 재실행하면 24.5x, 22.9x, 23.8x 처럼 매번 조금씩 다른 값이 나온다 — `timeit` 은 벽시계 기준이라 OS 스케줄링·캐시 상태에 따라 흔들리기 때문이다. **"약 20~25배"라는 정성적 결론은 재현되지만, 소수점 첫째 자리까지 똑같은 값이 매번 나온다는 뜻은 아니다.**)

**알고리즘이 같은데도 20배 넘게 차이가 난다.** 파이썬 루프 한 바퀴마다 인터프리터가 바이트코드를 하나씩 해석하는 반면, C 구현은 컴파일된 기계어로 같은 일을 한다. `itertools` 의 각 함수는 반복문의 **몸통**을 C로 옮겨 둔 것이라고 생각하면 된다.

## 언제 쓰지 말아야 하는가

`itertools` 는 강력한 만큼 오남용하기도 쉽다.

- **체이닝을 과하게 하지 마라.** `chain(islice(filter(...), ...), map(...))` 처럼 서너 겹 겹치면, 디버거로 중간값을 찍어 볼 수도 없고 읽는 사람이 순서를 손으로 추적해야 한다. 이해하기 쉬운 `for` 문 하나가 "똑똑해 보이는" 체인보다 낫다.
- **groupby는 정렬을 대신해 주지 않는다.** 앞에서 실측했듯 입력이 정렬돼 있다는 확신 없이 쓰면 **조용히 틀린 결과**가 나온다. 예외도 경고도 없다.
- **조합론 함수는 개수를 먼저 계산하고 써라.** `permutations(range(15))` 를 실수로 돌리면 프로그램이 죽는 게 아니라 **몇 분간 응답 없이 멈춘 것처럼 보인다.**
- **tee는 두 갈래의 속도가 비슷할 때만 쓴다.** 한쪽만 몰아 쓸 계획이면 `list()` 로 한 번 구체화하고 그 리스트를 재사용하는 게 메모리도 코드도 더 낫다.
- **무한 이터레이터는 항상 종료 조건과 함께.** `count`/`cycle`/`repeat(x)`(횟수 없이) 를 `islice`, `zip`, `takewhile` 없이 그냥 `for` 에 넣지 마라.

`itertools` 는 **반복 로직을 표현하는 어휘**이지, 무조건 써야 하는 도구가 아니다. 평범한 `for` 문이 더 명확하면 그걸 써라. 이 판단 기준은 이 파트의 다른 도구들 — [3.3 디스크립터](#/descriptors), [3.4 메타클래스](#/metaclass) — 에도 똑같이 적용된다. **강력함과 명확함을 저울질하고, 애매하면 명확함을 택한다.**

## 요약

- `count`/`cycle`/`repeat` 는 무한할 수 있지만 메모리는 크기와 무관하게 작다. 종료 조건 없이 순회하지 마라.
- `cycle` 은 첫 바퀴 동안 값을 버퍼에 저장한다 — "무한"이 "저장 안 함"은 아니다.
- `chain` 은 `+` 이어붙이기보다 훨씬 빠르다(실측 81배) — 매번 전체를 복사하지 않기 때문이다.
- `tee` 는 복제가 아니라 버퍼링이다. 두 갈래 속도가 비슷할 때만 쓴다.
- `groupby` 는 **바로 직전 키와만 비교**한다. 정렬 없이 쓰면 같은 키가 여러 그룹으로 쪼개진다. 그룹은 즉시 소비하라.
- `product`/`permutations`/`combinations`/`combinations_with_replacement` 는 순서·중복 허용 여부로 갈리고, 개수는 각각 $n^r$, $\frac{n!}{(n-r)!}$, $\binom{n}{r}$, $\binom{n+r-1}{r}$ 이다.
- `accumulate` 는 어떤 이항 함수든 받는다. 기본은 합, `max`/`operator.mul` 등도 가능하고 `initial` 로 시작값을 지정한다.
- `pairwise`(3.10+), `batched`(3.12+)는 예전에 `tee`/`islice` 로 손수 조립하던 레시피가 정식 채택된 것이다.
- 같은 알고리즘이라도 C 구현이 순수 파이썬보다 훨씬 빠르다(실측 25배) — 이게 `itertools` 를 쓰는 진짜 이유 중 하나다.

::: quiz 연습문제
1. 다음 코드의 출력을 예측한 뒤 실행해서 확인하라. 왜 그런 결과가 나오는지 `groupby` 의 동작 방식으로 설명하라.

   ```python
   import itertools
   logs = [("2024-01-01", "A"), ("2024-01-02", "B"), ("2024-01-03", "A")]
   grouped = {k: list(g) for k, g in itertools.groupby(logs, key=lambda x: x[1])}
   print(grouped)
   ```

2. `n=5` 인 원소 집합에서 `r=3` 을 뽑을 때 `product`, `permutations`, `combinations`, `combinations_with_replacement` 각각 몇 개가 나오는지 공식으로 먼저 계산하고, 실제로 `len(list(...))` 로 확인하라.

3. 아래 코드는 왜 위험한가? 실행하지 말고 이유를 설명한 뒤, `islice` 를 써서 안전하게 고쳐라.

   ```python
   import itertools
   evens = (x for x in itertools.count(0, 2) if x % 3 == 0)
   result = list(evens)     # 어떻게 될까?
   ```

4. `itertools.tee(it, 2)` 로 만든 두 이터레이터 중 하나만 끝까지 다 읽고 다른 하나는 전혀 안 읽는다면, 내부 버퍼에는 몇 개의 값이 쌓이는가? 이 절의 `tee_simple` 구현을 참고해 설명하라.

5. **깊이 생각해 볼 문제.** `itertools.accumulate(data, func)` 를 `itertools` 없이 제너레이터로 직접 구현하라. `initial` 매개변수까지 지원해야 한다. 구현한 뒤 다양한 입력에 대해 `itertools.accumulate` 와 결과가 같은지 확인하라.
:::

**다음 절**: [3.3 디스크립터](#/descriptors) — `property`, `classmethod`, `staticmethod` 가 실제로 어떻게 만들어지는지, `__get__`/`__set__` 을 직접 구현해서 증명한다.
