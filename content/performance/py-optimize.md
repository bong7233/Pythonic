# 5.3 파이썬 레벨 최적화

::: lead
프로파일러가 병목을 가리켰다. 이제 무엇을 어떻게 고칠 차례다. 이 절은 C 확장도, 컴파일러도 쓰지 않고 **순수 파이썬 코드만 바꿔서** 낼 수 있는 이득의 목록이다. 지역 변수, 내장 함수, 자료구조 선택, 캐싱 — 넷 다 "그렇다고 들었다" 수준으로 알고 있을 가능성이 높다. 여기서는 넷을 전부 실제로 재서, 어느 게 진짜 이득이고 어느 게 옛날 이야기인지 가른다. 결론부터 말하면 **넷의 이득 규모는 자릿수가 다르다.** 그 차이를 모르면 아무 데나 시간을 쓴다.
:::

## 지역 변수가 전역보다 빠른 이유

[3.7 바이트코드](#/bytecode)에서 CPython이 스택 기반 가상머신이고, 이름 조회마다 서로 다른 명령이 쓰인다는 걸 봤다. 지역 변수와 전역 변수를 읽는 명령은 이름만 비슷하지 실제로 하는 일이 다르다.

```pyrepl
>>> import dis
>>> G = 1
>>> def f(a):
...     return a + G
...
>>> dis.dis(f)
  1           RESUME                   0
  2           LOAD_FAST_BORROW         0 (a)
              LOAD_GLOBAL              0 (G)
              BINARY_OP                0 (+)
              RETURN_VALUE
```

`LOAD_FAST`(및 참조 카운트를 아끼는 변형 `LOAD_FAST_BORROW`, [3.7](#/bytecode) 참고)는 함수 프레임 안의 **고정 크기 배열**(`co_varnames` 에 대응하는 슬롯)을 인덱스로 바로 읽는다. 배열 인덱싱 한 번이다. `LOAD_GLOBAL` 은 그 함수가 정의된 **모듈의 `__dict__`** 에서 이름을 찾고, 없으면 `builtins` 모듈의 `__dict__` 까지 확인해야 한다. 딕셔너리 조회가 배열 인덱싱보다 원천적으로 더 하는 일이 많다.

::: deep 왜 굳이 이렇게 나눠 놨나
함수 안의 지역 변수는 **컴파일 시점에 개수와 이름이 확정**된다. 그래서 컴파일러가 각 지역 변수에 슬롯 번호를 미리 배정해 둘 수 있고, 실행 중에는 그 번호로 배열만 인덱싱하면 끝난다. 반면 전역 변수는 **모듈이 실행되는 동안 언제든 늘어날 수 있는 딕셔너리**에 담겨 있다. 게다가 전역과 내장(`builtins`)이라는 두 단계를 뒤져야 한다는 점도 근본적으로 다르다. 이 구조적 차이가 두 명령의 비용 차이의 뿌리다.
:::

실측해 보자. 같은 값을 5번 참조하는 루프를 전역 변수로 한 번, 지역 변수로 한 번 백만 번 돌린다.

```python title="bench_local_global.py"
import timeit

STEP = 1

def sum_global():
    total = 0
    for i in range(1_000_000):
        total = total + STEP + STEP + STEP + STEP + STEP
    return total

def sum_local():
    step = STEP
    total = 0
    for i in range(1_000_000):
        total = total + step + step + step + step + step
    return total

t_global = min(timeit.repeat(sum_global, number=1, repeat=7))
t_local = min(timeit.repeat(sum_local, number=1, repeat=7))
print(f"global: {t_global:.4f}s  local: {t_local:.4f}s  비율: {t_global/t_local:.2f}x")
```

```text
global: 0.0372s  local: 0.0318s  비율: 1.17x
```

(Python 3.14.5 / Windows 기준 실측.) 방향은 예상대로 지역이 빠르다. 그런데 **1.17배다.** "지역 변수가 전역보다 몇 배는 빠르다"는 오래된 통념을 기대했다면 실망스러운 숫자다.

::: perf 메서드 참조를 미리 캐싱하는 건 이제 거의 무의미하다
한때 표준 관용구였던 "반복문 밖에서 메서드를 지역 변수로 꺼내 두기"도 재보자.

```python title="bench_method_cache.py"
def build_plain():
    out = []
    for i in range(500_000):
        out.append(i)
    return out

def build_cached():
    out = []
    append = out.append      # 반복문 밖으로 조회를 끌어냈다
    for i in range(500_000):
        append(i)
    return out
```

```text
매번 out.append: 0.0132s
append 캐싱:     0.0136s
비율: 0.97x
```

캐싱한 쪽이 오히려 근소하게 **더 느렸다.** 3.11 이후 특수화 인터프리터가 `LOAD_ATTR`/`LOAD_GLOBAL` 자체를 실행 중 관찰된 대상에 맞춰 캐싱하기 때문이다([3.7 바이트코드](#/bytecode)의 `LOAD_ATTR_INSTANCE_VALUE` 이야기와 같은 메커니즘). 컴파일러와 인터프리터가 이미 하고 있는 일을 손으로 다시 하려 한 것뿐이라 이득이 사라졌다.
:::

**결론**: 지역 변수가 전역보다 빠른 것은 여전히 사실이지만, 3.11+ 의 적응형 특수화가 그 격차를 실무에서 신경 쓸 수준 밑으로 눌러 놨다. 코드 가독성을 희생하면서까지 전역을 지역으로 끌어내리는 리팩터링은 지금은 시간 낭비다.

## 내장 함수가 파이썬 반복문보다 빠른 이유

`sum`, `map`, `sorted` 같은 내장 함수는 파이썬 바이트코드가 아니라 **CPython의 C 구현**으로 돌아간다. 파이썬 `for` 루프는 매 반복마다 `FOR_ITER` → 조건 분기 → 원소 언패킹 → 사용자 바이트코드 실행이라는 사이클을 인터프리터 루프 안에서 밟는다. 내장 함수는 이 사이클 전체를 C 레벨의 단일 루프 하나로 눌러 담아, 매 원소마다 파이썬 바이트코드 디스패치를 하지 않는다.

```python title="bench_builtins.py"
data = list(range(1_000_000))

def sum_manual():
    total = 0
    for x in data:
        total += x
    return total

def sum_builtin():
    return sum(data)
```

```text
수동 for 누적:  0.0151s
sum() 내장:     0.0020s
비율: 7.36x
```

(Python 3.14.5 / Windows 기준.) 7배대는 진짜 이득이다. 그런데 `map` 은 조건부다.

```python title="bench_map.py"
def str_comp():
    return [str(x) for x in data]

def str_map_builtin():
    return list(map(str, data))

def str_map_lambda():
    return list(map(lambda x: str(x), data))
```

```text
수동 for+append:      0.0530s
리스트 컴프리헨션:      0.0507s
map(str, data):        0.0484s  비율(수동/map내장)=1.10x
map(lambda x: str(x)): 0.0664s  비율(수동/map람다)=0.80x
```

`map(str, data)` 처럼 **C로 구현된 함수를 그대로 넘기면** 파이썬 함수 호출 자체가 생략되어 약간 빨라진다. 하지만 `map(lambda x: str(x), data)` 는 매 원소마다 여전히 **파이썬 함수(람다) 호출**을 거친다 — 수동 반복문과 근본적으로 같은 비용에, `map` 객체를 만들고 순회하는 오버헤드까지 얹힌다. 그래서 오히려 더 느리다.

::: warn map + 람다는 최적화가 아니다
"`map` 이 반복문보다 빠르다"는 말은 **넘기는 콜러블이 C 함수일 때만** 맞는다. 파이썬 함수(특히 `lambda`)를 넘기는 순간 그 이점은 사라지고, 가독성만 잃는다. 리스트 컴프리헨션이 거의 항상 `map`+`lambda` 보다 낫다 — 읽기도 쉽고 속도도 밀리지 않는다. [7.2](#/py-ds-cost)와 [1.9 컴프리헨션](#/comprehensions)에서 컴프리헨션을 기본값으로 권하는 이유가 여기서도 반복된다.
:::

`sorted()` 는 더 극단적이다. 다만 이번엔 재는 방법 자체가 문제다 — `sorted(data)` 한 번의 실행 시간이 마이크로초 단위라 `timeit.repeat(..., number=1)` 로 한 번씩만 재면 타이머 자체의 호출 오버헤드가 섞여 값이 들쭉날쭉해진다. `number=1000` 처럼 여러 번을 한 묶음으로 재고 평균을 내서 오버헤드를 amortize해야 안정된 값이 나온다.

```python title="bench_sorted.py"
import timeit, random

random.seed(0)
data = [random.randint(0, 1_000_000) for _ in range(2000)]

def bubble_sort():
    arr = data[:]
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def sorted_builtin():
    return sorted(data)

t_bubble = min(timeit.repeat(bubble_sort, number=1, repeat=7))
t_sorted = min(timeit.repeat(sorted_builtin, number=1000, repeat=5)) / 1000
```

```text
수동 버블 정렬(2000개): 0.0756s
sorted() 내장(1000회 배치 평균): 0.0000361s
비율: 2095x
```

(Python 3.14.5 / Windows 기준 실측. `number=1`로 단발 측정하면 타이머 오버헤드 때문에 매 실행마다 1100~2400x 사이에서 값이 흔들린다 — 배치 평균이 재현 가능한 값이다.)

::: danger 이 숫자를 "내장 함수가 2000배 빠르다"로 오해하지 마라
2095배 차이의 대부분은 **알고리즘 복잡도 차이**에서 온다. 버블 정렬은 $O(n^2)$, `sorted()` 가 쓰는 Timsort는 $O(n \log n)$ 이다([7.4 정렬](#/sorting)). C 구현이라는 것과 더 나은 알고리즘이라는 것, 두 가지 다른 이유가 섞여 있는 숫자를 "내장 함수 효과"로만 읽으면 잘못 배운다. `sum`/`map`/`str` 처럼 **같은 알고리즘, 다른 구현**을 비교한 앞의 수치(7배, 1.1배)가 순수한 "내장 함수 효과"에 가깝다.
:::

## 자료구조 선택이 성능을 좌우하는 사례

[7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 이미 이 표를 자세히 다뤘다. `x in list` 는 $O(n)$, `x in set`/`x in dict` 는 평균 $O(1)$ — 그 절에서 $n=1{,}000{,}000$ 기준으로 **26580배** 차이를 실측했다. 여기서는 그 지식을 "최적화 작업"의 맥락에 놓고 한 번 더 확인한다.

```python title="bench_dedup.py"
import random

random.seed(0)
items = [random.randint(0, 100_000) for _ in range(50_000)]  # 약 39,332개가 서로 다른 값

def dedup_list(items):
    seen = []
    out = []
    for x in items:
        if x not in seen:        # O(n) 확인을 n번 반복
            seen.append(x)
            out.append(x)
    return out

def dedup_set(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:        # 평균 O(1) 확인을 n번 반복
            seen.add(x)
            out.append(x)
    return out
```

$n=50{,}000$ 개, `random.seed(0)` 으로 고정한 뒤 `random.randint(0, 100_000)` 으로 뽑은 무작위 정수(약 39,332개가 서로 다른 값)를 넣고 재면 이렇다.

```text
list 기반 dedup: 3.2291s
set  기반 dedup: 0.0023s
비율: 1405x
```

(Python 3.14.5 / Windows 기준 실측.) 1405배. 지금까지 본 어떤 "코드 레벨" 최적화보다 크다. 이유는 단순하다 — 이건 코드를 다듬은 게 아니라 **알고리즘의 복잡도 자체를 $O(n^2)$ 에서 $O(n)$ 으로 바꾼 것**이기 때문이다. 참고로 이 비율은 `randint`의 상한(정수 범위)에 따라 크게 흔들린다 — 상한이 좁아 중복이 많이 나올수록(예: `randint(0, 10_000)`) `seen` 리스트가 짧게 유지돼 비율이 약 770배대로 낮아지고, 상한을 넓혀 중복이 드물어질수록(예: `randint(0, 1_000_000)`) `seen` 리스트가 거의 끝까지 자라 비율이 1700배대까지 커진다. 그래서 이런 벤치마크를 인용할 때는 **정수의 범위(상한)까지 정확히 밝혀야** 재현할 수 있다.

::: cote 최적화 순서의 힌트
자료구조 선택이 여기서 항상 가장 큰 숫자로 나오는 이유가 곧 최적화 우선순위의 힌트다. **코드를 어떻게 더 빠르게 쓸지 고민하기 전에, 자료구조부터 맞는지 확인해라.** `in` 하나를 `list` 에서 `set` 으로 바꾸는 것이 다른 어떤 미세 조정보다 이득이 크다. [8.3 시간 초과를 피하는 관용구](#/tle)에서 이 순서를 실전 체크리스트로 다듬는다.
:::

## lru_cache로 메모이제이션

[3.1 functools](#/functools)에서 `lru_cache` 가 인자를 키로 결과를 딕셔너리에 저장해 뒀다가 같은 인자가 다시 들어오면 재계산을 건너뛴다고 했다. 겹치는 부분 문제가 있는 재귀에서 특히 강력하다. 2×n 보드를 도미노로 타일링하는 경우의 수 — 점화식이 피보나치와 같은 전형적인 지수 재귀 사례로 확인해 보자([7.20 동적 계획법 기초](#/dp-basics)에서 이 관계를 자세히 다룬다).

```python title="bench_lru.py"
import functools

def tiling_plain(n):
    if n <= 2:
        return n
    return tiling_plain(n - 1) + tiling_plain(n - 2)

@functools.lru_cache(maxsize=None)
def tiling_cached(n):
    if n <= 2:
        return n
    return tiling_cached(n - 1) + tiling_cached(n - 2)
```

```text
n=32
메모이제이션 없음: 0.1028s
lru_cache 적용:    0.000036s
비율: 2872x
CacheInfo(hits=29, misses=32, maxsize=None, currsize=32)
```

(Python 3.14.5 / Windows 기준 실측.) `misses=32` 는 $n=0$ 부터 $32$ 까지 각 부분 문제를 딱 한 번씩만 계산했다는 뜻이다 — $O(2^n)$ 이 $O(n)$ 으로 떨어졌다. `hits=29` 는 재귀 중 이미 계산된 값을 그만큼 재사용했다는 뜻이다. 이건 자료구조 선택과 마찬가지로 **복잡도 자체를 바꾸는 최적화**라 이득이 크다.

::: warn 캐싱은 공짜가 아니다
`lru_cache` 가 이득을 내려면 **같은 인자로 여러 번 불려야 한다.** 매번 다른 인자가 들어오면 캐시 히트가 하나도 없이 조회·저장 오버헤드만 쌓인다.

```python title="bench_lru_overhead.py"
@functools.lru_cache(maxsize=None)
def square_cached(x):
    return x * x

def square_plain(x):
    return x * x

# 0부터 2,000,000까지 매번 다른 인자로 호출
```

```text
캐시 없음: 0.0746s
캐시 있음: 0.1769s  (오버헤드만 추가됨)
비율(캐시있음/없음): 2.37x
CacheInfo(hits=0, misses=2000000, maxsize=None, currsize=2000000)
```

히트가 0인데 오히려 **2.37배 느려졌다.** 매 호출마다 인자를 해시하고 내부 딕셔너리에 조회·삽입하는 비용이 추가로 붙기 때문이다. `maxsize=None` 은 이 경우 캐시 항목이 200만 개까지 쌓여 메모리도 그만큼 차지한다 — [5.2 메모리 모델](#/memory)에서 다룬 참조 유지 문제와 같은 맥락이다. **호출 인자의 종류가 유한하고 반복적으로 재사용될 때만** `lru_cache` 를 붙여라. 무작위 인자, 매번 새로운 요청 페이로드 같은 곳에는 붙이지 마라.
:::

## 문자열 join

[1.1 객체·이름·참조](#/objects-names)에서 문자열이 불변이라 `+=` 누적이 이론적으로 $O(n^2)$ 이라고 했고, [1.4 문자열](#/strings)에서 CPython이 참조 카운트 1일 때 제자리 확장을 시도해 실제로는 조건부로 $O(n)$ 에 가깝게 동작하는 구현 세부사항까지 다뤘다. 여기서는 그 지식을 "최적화 체크리스트의 한 항목"으로 다시 확인만 한다.

```python title="bench_join.py"
words = [f"word{i}" for i in range(200_000)]

def concat_plus():
    result = ""
    for w in words:
        result += w
    return result

def concat_join():
    return "".join(words)
```

```text
n=200000
+= 누적:  0.0444s
join():   0.0007s
비율: 64.5x
```

(Python 3.14.5 / Windows 기준 실측.) 이 벤치마크는 `result` 를 다른 이름이 붙잡지 않는 **가장 유리한 조건**에서 돌렸다 — CPython의 제자리 확장 최적화가 최선으로 작동하는 상황이다. 그런데도 `join` 이 64배 더 빠르다. 조건이 조금만 나빠지면([1.4](#/strings)에서 본 별칭이 낀 경우) 이 격차는 더 벌어진다. **`+=` 누적이 최적화될 수도 있다는 사실에 기대지 말고, 항상 `join` 을 써라**는 결론은 변하지 않는다.

## 이득의 규모를 정리한 표

지금까지 실측한 숫자를 한자리에 모은다. **모두 이 문서에서 실제로 실행해 얻은 값**이고, 절대값은 기기마다 다르지만 자릿수의 순서는 재현된다.

| 기법 | 실측 배수 | 이득의 성격 | 우선순위 |
| --- | --- | --- | --- |
| 자료구조 선택 (`list`→`set`의 `in`) | 1405x (n=50,000) | 복잡도 $O(n^2)$→$O(n)$ | **최우선** |
| 메모이제이션 (`lru_cache`, 겹치는 부분 문제) | 2872x (n=32) | 복잡도 $O(2^n)$→$O(n)$ | **최우선** |
| 문자열 `join` vs `+=` | 64.5x (n=200,000) | 상수 인자 축소, n이 클수록 격차 확대 | 높음 |
| 내장 함수 `sum()` vs 수동 루프 | 7.4x | 인터프리터 디스패치 생략 | 중간 |
| `map(builtin, ...)` vs 컴프리헨션 | 1.1x | 미미, 가독성이 우선 | 낮음 (권장 안 함) |
| `map(lambda, ...)` vs 컴프리헨션 | 0.8x (오히려 손해) | 함수 호출 오버헤드 그대로 | 하지 마라 |
| 지역 변수 캐싱 (전역→지역) | 1.17x | 3.11+ 특수화로 격차 축소 | 낮음 |
| 메서드 참조 사전 캐싱 (`append = out.append`) | 0.97x (차이 없음) | 인터프리터가 이미 대신 해 줌 | 하지 마라 |
| `lru_cache` — 인자가 항상 새 값일 때 | 2.37x **손해** | 히트 없이 오버헤드만 | 쓰지 마라 |

표를 읽는 법은 하나다. **위쪽 두 줄(자료구조, 메모이제이션)이 나머지 전부를 합친 것보다 크다.** 둘 다 알고리즘의 복잡도 등급 자체를 바꾸기 때문이다. 반대로 아래쪽 세 줄은 격차가 아예 없거나 마이너스다.

::: danger 마이크로 최적화에 시간을 쓰지 마라
"지역 변수로 캐싱하면 빠르다", "메서드 참조를 미리 꺼내 두면 빠르다" 같은 조언은 3.10 이전 CPython에서는 지금보다 더 유효했다. 3.11+ 의 적응형 특수화 인터프리터([3.7 바이트코드](#/bytecode))가 그 격차의 상당 부분을 이미 인터프리터 내부에서 흡수해 버렸다. 이런 것들에 시간을 쓰기 전에 먼저 물어라 — **자료구조가 맞는가? 알고리즘의 복잡도 등급이 최선인가?** 이 두 질문에 대한 답이 "아니오"라면, 다른 어떤 미세 조정도 그 답을 바꾸지 못한다. 측정([5.1 측정 없이 최적화 없다](#/profiling))으로 병목을 먼저 찾고, 그 병목이 알고리즘/자료구조 층에 있는지부터 확인해라. 대부분 거기 있다.
:::

## 요약

- `LOAD_FAST` 는 지역 변수 슬롯을 배열 인덱싱으로 읽고, `LOAD_GLOBAL` 은 모듈·내장 딕셔너리를 조회한다. 방향은 지역이 빠르지만 3.11+ 특수화 덕에 실측 격차는 1.2배 안팎으로 작다.
- 내장 함수는 C 레벨 루프로 파이썬 바이트코드 디스패치를 생략한다. `sum()` 처럼 **순수 C 구현**을 쓸 때만 의미 있는 이득(7배대)이 나온다. `map`+람다처럼 파이썬 콜백을 다시 부르면 이득이 사라지거나 손해다.
- 자료구조 선택은 이 절에서 가장 큰 숫자를 냈다(1405배). `in` 연산 하나를 `list`→`set` 으로 바꾸는 것이 알고리즘의 복잡도 등급을 바꾸기 때문이다. 단, 이 배수는 무작위 정수의 범위(중복 발생 빈도)에 따라 크게 흔들리므로 인용할 때는 범위까지 명시해야 재현 가능하다.
- `lru_cache` 메모이제이션은 겹치는 부분 문제가 있을 때 압도적이다(2872배). 대신 인자가 항상 새로운 값이면 히트 없이 오버헤드만 남아 오히려 느려진다(2.37배 손해).
- 문자열 `join` 은 CPython의 제자리 확장 최적화가 최선으로 작동하는 조건에서도 `+=` 보다 64배 빠르다.
- 마이크로 최적화(지역 변수 캐싱, 메서드 참조 사전 조회)에 시간을 쓰지 마라. 이득이 거의 없거나 인터프리터가 이미 대신 하고 있다. 시간은 자료구조와 알고리즘 선택에 써라.

::: quiz 연습문제
1. 이 절의 `dedup_list`/`dedup_set` 벤치마크를 $n=5{,}000$ 과 $n=500{,}000$ 으로 바꿔 다시 재 보라. 비율이 어떻게 변하는가? $O(n^2)$ 대 $O(n)$ 이라는 설명과 맞는가?
2. `map(len, ["a", "bb", "ccc"])` 처럼 인자를 하나만 받는 C 내장 함수를 다른 것으로 바꿔 가며 컴프리헨션과 비교해 보라. 항상 컴프리헨션과 비슷하거나 약간 빠른가?
3. `tiling_cached(32)` 를 호출하기 **전에** `tiling_cached.cache_info()` 를 확인하고, 호출한 뒤 다시 확인하라. `hits`, `misses`, `currsize` 가 예상과 맞는지 설명하라.
4. `lru_cache` 의 `maxsize` 를 `None` 대신 `128` 로 바꾸고, 이 절의 "인자가 항상 새 값일 때" 벤치마크를 다시 돌려라. 캐시가 꽉 찬 뒤에는 무슨 일이 일어나는가? `cache_info()` 로 확인하라.
5. `"".join()` 대신 `io.StringIO` 에 `write` 를 반복해서 문자열을 만드는 방법도 있다. 이 절의 `words` 리스트로 `io.StringIO` 버전을 직접 만들어 `join()` 과 비교해 보라. 어느 쪽이 빠른가?
:::

**다음 절**: [5.4 C 확장, ctypes, cffi](#/c-ext) — 파이썬 코드로 짜낼 수 있는 이득의 한계에 도달했을 때, 네이티브 코드를 직접 호출하는 법.
