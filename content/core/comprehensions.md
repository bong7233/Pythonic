# 1.9 컴프리헨션과 제너레이터 표현식

::: lead
컴프리헨션은 파이썬에서 가장 먼저 배우고 가장 많이 오용되는 문법이다. "for문을 한 줄로 줄이는 문법"이라고 이해하면 절반은 맞고 절반은 위험하다. 이 절은 컴프리헨션이 **무엇으로 컴파일되는지**, 왜 3.12에서 이게 통째로 바뀌었는지, 그리고 대괄호 하나를 괄호로 바꾸는 것만으로 왜 메모리가 38MB에서 480바이트로 줄어드는지를 다룬다. 마지막에는 반대로 **컴프리헨션을 쓰면 안 되는 자리**를 정리한다. 그게 이 절에서 제일 중요하다.
:::

## 문제부터: 같은 일을 하는 네 가지 코드

제곱수 리스트를 만든다. 방법이 여러 개다.

```python title="넷 다 같은 답을 낸다"
data = list(range(1000))

# ① 손으로 쓴 루프
out = []
for x in data:
    out.append(x * x)

# ② 리스트 컴프리헨션
out = [x * x for x in data]

# ③ map + lambda
out = list(map(lambda x: x * x, data))

# ④ 제너레이터 표현식을 list() 로 소비
out = list(x * x for x in data)
```

답이 같으니 취향 문제처럼 보인다. 아니다. 넷은 **서로 다른 바이트코드로 컴파일되고, 비용이 다르다.**

```python title="bench_four.py"
import timeit

setup = "data = list(range(1000))"
for stmt in ("[x*x for x in data]",
             "list(map(lambda x: x*x, data))",
             "list(x*x for x in data)"):
    print(f"{stmt:35s} {timeit.timeit(stmt, setup, number=10000):.4f}")

print(f"{'for + append':35s} "
      f"{timeit.timeit('''
out = []
for x in data:
    out.append(x*x)
''', setup, number=10000):.4f}")
```

```text nolines
[x*x for x in data]                 0.1682
list(map(lambda x: x*x, data))      0.3279     <- 1.95x
list(x*x for x in data)             0.2624     <- 1.56x
for + append                        0.2106     <- 1.25x
```

(Python 3.14.5 / Windows 기준 실측. 여러 번 재측정하면 map 쪽 비율은 1.9~2.0x, for+append 쪽은 1.2~1.3x 사이에서 흔들린다. 절대값은 기기마다 다르지만 순서와 자릿수는 어디서나 같다.)

컴프리헨션이 이긴다. 이유는 세 가지고, 셋 다 이 절에서 하나씩 밝힌다.

1. `LIST_APPEND` 라는 **전용 바이트코드**가 있다. `out.append` 를 이름으로 찾아 호출하는 과정이 통째로 없다.
2. 3.12부터 컴프리헨션은 **함수 프레임을 만들지 않는다** (PEP 709).
3. `map(lambda ...)` 는 원소마다 **파이썬 함수 호출**을 한다. 이게 제일 비싸다.

### map 이 항상 지는 건 아니다

`lambda` 를 끼우면 진다. 하지만 **이미 있는 C 함수**를 그대로 넘기면 map 이 이긴다. 호출 자체가 C 레벨에서 끝나기 때문이다.

```python title="bench_map.py"
import timeit
setup = "data = [str(i) for i in range(1000)]"
print(timeit.timeit("[int(x) for x in data]", setup, number=5000))   # 0.1387
print(timeit.timeit("list(map(int, data))",   setup, number=5000))   # 0.1101
```

약 1.2~1.3배(6회 재측정 범위 1.17~1.34배, 방향은 항상 map이 이김). 이 정도 차이로 가독성을 팔지 마라. `map(int, ...)` 처럼 **이름 하나만 넘기는 경우**에만 쓰고, `lambda` 가 등장하는 순간 컴프리헨션으로 돌아와라.

## 네 가지 형태, 그리고 없는 한 가지

괄호가 바꾸는 것은 **결과 타입**이다.

| 문법 | 결과 | 즉시 평가? |
| --- | --- | --- |
| `[f(x) for x in it]` | `list` | 예 |
| `{f(x) for x in it}` | `set` | 예 |
| `{k(x): v(x) for x in it}` | `dict` | 예 |
| `(f(x) for x in it)` | **`generator`** | 아니오 |

마지막 줄이 함정이다. 소괄호는 튜플이 아니다.

```pyrepl
>>> type((x for x in range(3)))
<class 'generator'>
>>> tuple(x for x in range(3))       # 튜플이 필요하면 이렇게
(0, 1, 2)
```

**튜플 컴프리헨션은 문법에 없다.** 소괄호를 이미 제너레이터 표현식이 가져갔기 때문이다. 이건 설계 사고가 아니라 의도된 선택이다 — 튜플은 "고정 길이 레코드"고, 컴프리헨션은 "길이를 모르는 반복"이다. 둘은 애초에 짝이 아니다. ([1.3 시퀀스](#/sequences))

### dict 컴프리헨션의 중복 키

```pyrepl
>>> {k: v for k, v in [("a", 1), ("b", 2), ("a", 3)]}
{'a': 3, 'b': 2}
```

**나중 것이 이긴다.** 그런데 순서는 `'a'` 가 앞이다. dict는 **처음 삽입된 자리**를 유지하고 값만 덮어쓴다. 이 동작의 근거는 [1.6 dict](#/dict)의 compact dict 구조에 있다.

::: tip 컴프리헨션이 필요 없는 경우가 있다
`{k: v for k, v in pairs}` 는 그냥 `dict(pairs)` 다. 마찬가지로:

```python title="bench_shortcuts.py"
import timeit
from itertools import chain

setup1 = "ks = list(range(1000)); vs = list(range(1000))"
a = timeit.timeit("{k: v for k, v in zip(ks, vs)}", setup1, number=5000)
b = timeit.timeit("dict(zip(ks, vs))", setup1, number=5000)
print("dict:", a, b, a / b)

setup2 = "from itertools import chain; m = [list(range(10)) for _ in range(200)]"
c = timeit.timeit("[x for row in m for x in row]", setup2, number=5000)
d = timeit.timeit("list(chain.from_iterable(m))", setup2, number=5000)
print("chain:", c, d, c / d)
```

```text nolines
dict:  0.1128  0.0704   <- 1.60x
chain: 0.0961  0.0437   <- 2.20x
```

(길이 1000 dict, 200×10 리스트 기준. 재측정하면 dict 쪽은 1.5~1.6x, chain 쪽은 2.0~2.2x 사이에서 흔들린다. 방향은 항상 같다.)

| 컴프리헨션 | 더 나은 것 | 실측 (위 코드 기준) |
| --- | --- | --- |
| `{k: v for k, v in zip(ks, vs)}` | `dict(zip(ks, vs))` | 약 1.6배 느림 |
| `[c for row in m for c in row]` | `list(chain.from_iterable(m))` | 약 2.2배 느림 |
| `[x for x in data]` | `list(data)` | 아래 참조 |

**항등 컴프리헨션**(`[x for x in data]`)은 특히 나쁘다. 느릴 뿐 아니라 메모리도 더 쓴다.

```pyrepl
>>> import sys
>>> sys.getsizeof([x for x in range(1000)])
8856
>>> sys.getsizeof(list(range(1000)))
8056
```

800바이트 차이는 **과할당**이다. `list(range(1000))` 은 `range` 가 길이를 알려 주므로(`__length_hint__`) 딱 1000칸을 한 번에 잡는다. 컴프리헨션은 `LIST_APPEND` 로 한 칸씩 밀어 넣으므로 리스트가 성장하면서 여유분을 남긴다 — 1100칸이 잡혔다. `chain` 은 [3.2 itertools](#/itertools)에서.
:::

## 중첩: 순서가 헷갈리는 진짜 이유

이게 컴프리헨션에서 가장 많이 틀리는 지점이다. 외우려 하지 마라. **기계적 번역 규칙 하나면 끝난다.**

> `for` 절과 `if` 절은 **쓴 순서 그대로 위에서 아래로** 중첩된다. 결과 표현식은 **맨 안쪽**으로 간다.

```text nolines
[ EXPR for A in IT1 if C1 for B in IT2 ]

   |
   v   (기계적으로 이렇게 펼친다)

result = []
for A in IT1:
    if C1:
        for B in IT2:
            result.append(EXPR)
```

이 규칙만 있으면 전부 읽힌다.

```pyrepl
>>> matrix = [[1, 2, 3], [4, 5, 6]]
>>> [c for row in matrix for c in row]
[1, 2, 3, 4, 5, 6]
```

`for row in matrix` 가 먼저 쓰였으니 바깥 루프. `for c in row` 가 안쪽 루프. **읽는 순서와 실행 순서가 같다.**

그런데도 헷갈리는 이유는 하나다. **결과 표현식이 맨 앞에 있기 때문이다.** `[c for row in matrix for c in row]` 에서 `c` 는 맨 앞에 쓰였지만 맨 마지막에 정의된다. 사람 눈은 왼쪽부터 읽으므로 "c가 뭐지?" 하는 순간 뇌가 멈춘다.

그래서 순서를 뒤집고 싶은 충동이 생긴다. 해 보면 바로 걸린다.

```pyrepl
>>> [c for c in row for row in matrix]
Traceback (most recent call last):
  ...
NameError: name 'row' is not defined
```

`for c in row` 를 먼저 썼으니 `row` 는 아직 존재하지 않는다. **컴프리헨션은 왼쪽부터 오른쪽으로 이름을 만든다.**

### 전치(transpose)가 특히 헷갈리는 이유

```pyrepl
>>> matrix = [[1, 2, 3], [4, 5, 6]]
>>> [[row[i] for row in matrix] for i in range(3)]
[[1, 4], [2, 5], [3, 6]]
```

이건 앞의 예와 **구조가 다르다.** 위의 평탄화는 `for` 두 개가 **한 컴프리헨션 안에** 나란히 있었다. 이건 컴프리헨션이 **두 개 겹쳐 있다.**

```text nolines
flatten     [ c        for row in matrix for c in row ]
                       ^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^
                       for 두 개, 컴프리헨션은 하나

transpose   [ [row[i] for row in matrix]   for i in range(3) ]
              ^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^
              안쪽 컴프리헨션 (통째로 EXPR)  바깥 루프
```

바깥이 **오른쪽**에 있다. `flatten` 과 정반대다. 이 둘을 나란히 놓고 보지 않으면 평생 헷갈린다.

::: tip 전치는 손으로 쓰지 마라
```pyrepl
>>> matrix = [[1, 2, 3], [4, 5, 6]]
>>> list(zip(*matrix))
[(1, 4), (2, 5), (3, 6)]
```

`zip(*matrix)` 가 정답이다. 튜플이 싫으면 `[list(t) for t in zip(*matrix)]`. NumPy가 있으면 `arr.T` 고, 이건 **복사조차 안 한다** ([9.3 NumPy 고급](#/numpy-advanced)의 스트라이드).
:::

### 뒤쪽 iterable 은 앞쪽 변수를 본다

이게 중첩 컴프리헨션의 힘이다. 안쪽 iterable이 바깥 변수에 의존할 수 있다.

```pyrepl
>>> [(i, j) for i in range(4) for j in range(i)]
[(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2)]
```

`range(i)` 가 `i` 마다 다시 평가된다. 상삼각 순회, 조합 생성의 기본형이다.

`if` 절을 어디에 놓느냐도 의미가 다르다.

```pyrepl
>>> [(a, b) for a in range(3) if a % 2 == 0 for b in range(2)]
[(0, 0), (0, 1), (2, 0), (2, 1)]
```

`if` 가 바깥 루프 직후에 있으므로 **`a` 가 홀수면 안쪽 루프 자체를 건너뛴다.** 맨 뒤로 옮기면 안쪽 루프를 다 돌고 나서 버린다 — 결과는 같고 비용은 다르다. 필터는 **가능한 한 왼쪽으로**.

## 제너레이터 표현식: 대괄호 하나의 값

여기서 이 절의 가장 중요한 실측이 나온다.

```pyrepl
>>> import sys
>>> sys.getsizeof([x * x for x in range(1000)])
8856
>>> sys.getsizeof((x * x for x in range(1000)))
208
```

208바이트. 그런데 이 숫자가 진짜 말하는 건 이거다.

```pyrepl
>>> sys.getsizeof([x * x for x in range(1_000_000)])
8448728
>>> sys.getsizeof((x * x for x in range(1_000_000)))
208
```

**원소가 1000개든 100만 개든 제너레이터는 208바이트다.** 제너레이터 객체는 값을 담고 있지 않기 때문이다. 그것이 담고 있는 건 "다음에 무엇을 할지"뿐이다 — 중단된 프레임과 명령 포인터. ([1.18 이터레이터와 제너레이터](#/iterators))

::: perf sum([...]) 과 sum(...) — 84,000배
`getsizeof` 는 컨테이너 껍데기만 잰다. 진짜 비용은 **원소 객체까지** 포함해야 보인다. `tracemalloc` 으로 최고점을 재자.

```python title="mem_sum.py"
import tracemalloc

def peak_of(fn):
    tracemalloc.start()
    result = fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak

t1, p1 = peak_of(lambda: sum([x * x for x in range(1_000_000)]))
t2, p2 = peak_of(lambda: sum(x * x for x in range(1_000_000)))
print(f"sum([...]) peak: {p1:>10,} bytes")
print(f"sum(...)   peak: {p2:>10,} bytes")
print("같은 답:", t1 == t2, "/ 배수:", round(p1 / p2))
```

```text nolines
sum([...]) peak: 40,447,720 bytes
sum(...)   peak:        480 bytes
같은 답: True / 배수: 84266
```

38.6MB vs 480바이트. 답은 똑같다. **대괄호 두 개를 지웠을 뿐이다.**

40MB 중 8.4MB만 리스트 껍데기고, 나머지 32MB는 백만 개의 `int` 객체다. 제너레이터 쪽은 `int` 를 하나 만들어 `sum` 에 넘기고, `sum` 이 더한 뒤 그 `int` 는 즉시 참조 카운트가 0이 되어 죽는다 ([1.1 객체, 이름, 참조](#/objects-names)). 살아 있는 원소가 **항상 하나뿐**이다.
:::

### 파이프라인은 공짜로 이어진다

제너레이터의 진짜 값은 단독 사용이 아니라 **연결**에 있다.

```python title="pipeline.py"
import tracemalloc

tracemalloc.start()
nums  = (i for i in range(1_000_000))
sq    = (n * n for n in nums)          # 아직 아무것도 안 일어났다
evens = (s for s in sq if s % 2 == 0)  # 여전히 아무것도 안 일어났다
total = sum(evens)                     # 여기서 비로소 흐른다
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(total, peak)                     # 166666166667000000 / 1624
```

리스트로 같은 3단계를 하면 어떨까.

```python title="pipeline_list.py"
import tracemalloc

tracemalloc.start()
nums  = [i for i in range(1_000_000)]
sq    = [n * n for n in nums]
evens = [s for s in sq if s % 2 == 0]
total = sum(evens)
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(total, peak)                     # 166666166667000000 / 85055800
```

**85,055,800바이트 (81.1MB)** 가 최고점이다. 제너레이터 파이프라인은 **1,624바이트**. 5만 배다.

중간 단계마다 백만 개짜리 리스트가 생기지 않기 때문이다. 원소 하나가 `range` → 제곱 → 필터 → `sum` 을 **끝까지 통과한 뒤에야** 다음 원소가 출발한다.

```text nolines
  list  :  [1M] ──▶ [1M] ──▶ [500K] ──▶ sum        (81.1 MB)
                     ^^^ 3개가 동시에 메모리에 산다

  genexpr:   1  ──▶   1  ──▶    1   ──▶ sum        (1.6 KB)
                     ^^^ 언제나 원소 하나
```

::: danger any / all 에 대괄호를 넣으면 조기 종료가 죽는다
이건 실제 장애로 이어지는 실수다.

```python title="bench_any.py"
import timeit
setup = "data = list(range(1_000_000))"
a = timeit.timeit("any(x > 5 for x in data)",   setup, number=100) / 100
b = timeit.timeit("any([x > 5 for x in data])", setup, number=100) / 100
print(f"genexpr: {a * 1e6:10.2f} us")   #      0.25 us
print(f"list   : {b * 1e6:10.2f} us")   #  19298.08 us
```

**약 8만 배.** `any` 는 첫 참을 만나면 즉시 멈춘다. 위 데이터에서는 7번째 원소에서 끝난다.

그런데 `any([...])` 는 **대괄호 안이 먼저 전부 평가된다.** `any` 가 호출되기도 전에 백만 개를 다 계산해 리스트로 만든다. 조기 종료할 게 남아 있지 않다.

같은 이유로 이 관용구들이 중요하다.

```python
next((x for x in data if cond(x)), None)   # ✅ 첫 원소를 찾으면 즉시 멈춤
[x for x in data if cond(x)][0]            # ❌ 전부 훑고 나서 앞의 하나만
```

`any`, `all`, `next`, `min`/`max` 의 첫 결정, 그리고 `in` — **조기 종료하는 소비자에게는 절대 리스트를 만들어 주지 마라.**
:::

### 괄호 규칙

제너레이터 표현식이 **유일한 인자일 때만** 함수 호출의 겉괄호를 빌려 쓸 수 있다.

```pyrepl
>>> sum(x for x in range(5))                # 괄호 한 겹으로 충분
10
>>> min((x for x in range(5)), default=0)   # 인자가 둘이면 괄호 필수
0
```

`min(x for x in range(5), default=0)` 은 `SyntaxError` 다.

### 제너레이터의 대가

공짜는 아니다. 세 가지를 내준다.

**① 한 번만 흐른다.**

```pyrepl
>>> g = (x for x in range(3))
>>> list(g)
[0, 1, 2]
>>> list(g)
[]
```

두 번째는 조용히 빈 리스트다. **예외도 안 난다.** 함수가 제너레이터를 반환하는데 호출자가 두 번 순회하면 이 버그가 난다.

**② 길이를 모른다.** `len(g)` 는 `TypeError`. 인덱싱도 슬라이싱도 없다.

**③ 원소당 오버헤드가 있다.** 매 원소마다 제너레이터 프레임을 재개하고 중단한다.

```text nolines
len(data)   [x for x in data]   list(x for x in data)   ratio
    0            0.0025                0.0170           6.73x
    3            0.0045                0.0297           6.64x
  100            0.1049                0.2146           2.05x
 1000            0.9021                1.8442           2.04x
```

(number=100000 기준 실측. `timeit` 은 원소가 적을수록 노이즈에 취약해서, `len(data)==3` 자리는 재측정할 때마다 4배대~6배대로 크게 흔들린다. 그래도 방향과 자릿수 — **작을수록 격차가 크고, 커질수록 2배 근처로 수렴한다** — 는 항상 같다.)

**어차피 전부 리스트로 만들 거라면 제너레이터를 경유하지 마라. 최소 2배 손해다.** `list(x for x in it)` 는 순수한 낭비다. 항상 `[x for x in it]` 이 낫다.

### 판단 기준은 하나다

> **소비자가 전부 다 필요로 하는가?**
>
> - 그렇다 (`list`, `sorted`, `len`, 인덱싱, 두 번 순회) → **컴프리헨션**
> - 아니다 (`sum`, `any`, `all`, `next`, `for`, `min`, 파일 스트리밍) → **제너레이터 표현식**

그래서 `sorted(x for x in data)` 는 의미가 없다. `sorted` 는 어차피 내부에서 리스트를 만든다. 그냥 `sorted(data)` 다.

## 스코프: 컴프리헨션은 왜 변수를 유출하지 않는가

```pyrepl
>>> x = "원래값"
>>> [x for x in range(3)]
[0, 1, 2]
>>> x
'원래값'
```

`for` 문이었다면 `x` 는 `2` 가 됐을 것이다. 컴프리헨션은 **바깥 `x` 를 건드리지 않는다.**

::: hist 파이썬 2에서는 샜다
파이썬 2.x에서 리스트 컴프리헨션은 **변수를 유출했다.** `[x for x in range(3)]` 다음에 `x` 는 `2` 였다. 그런데 같은 2.x의 제너레이터 표현식과 셋/딕트 컴프리헨션은 유출하지 않았다 — 이들은 나중에(2.4/2.7) 추가되면서 처음부터 함수 스코프를 가졌기 때문이다.

**같은 언어 안에 규칙이 두 개 있었다.** 파이썬 3은 리스트 컴프리헨션을 나머지 셋에 맞춰 통일했다. 하위 호환을 깬 몇 안 되는 결정 중 하나고, 옳은 결정이었다.
:::

방식은 단순했다. **컴프리헨션을 익명 함수로 컴파일한 뒤 즉시 호출한다.** 함수 스코프가 생기니 변수가 갇힌다. 3.11까지 파이썬은 이걸 문자 그대로 했다 — `<listcomp>` 라는 이름의 코드 객체가 실제로 만들어졌고, 실행할 때마다 함수 객체와 프레임이 생겼다.

::: danger 클래스 본문 안의 컴프리헨션 — 예고 없이 NameError
그 익명 함수 때문에 이런 일이 생긴다.

```python title="class_scope.py"
class Config:
    limit = 10
    values = [1, 2, 3, 20]

    ok = [v for v in values]                   # ✅ 동작한다
    bad = [v for v in values if v < limit]     # ❌ NameError: name 'limit' is not defined
```

**`values` 는 보이는데 `limit` 은 안 보인다.** 이유:

> 첫 번째 `for` 절의 iterable만 **바깥 스코프에서 평가되어 인자로 전달**된다. 나머지 전부(조건절, 결과 표현식, 두 번째 이후 iterable)는 **안쪽 스코프에서 평가된다.**

그리고 **클래스 본문은 클로저를 만들지 않는다.** 함수 안에서라면 `limit` 은 자유 변수로 잡혔겠지만, 클래스 본문의 이름은 클로저 대상이 아니다. 안쪽에서 `limit` 을 찾으면 지역 → 전역 → 빌트인 순으로 뒤지다 실패한다.

**피하는 법**: 클래스 본문에서는 컴프리헨션에 클래스 변수를 참조하지 마라. 인자로 밀어 넣거나, 클래스 밖으로 빼라.

```python
_LIMIT = 10

class Config:
    values = [1, 2, 3, 20]
    good = [v for v in values if v < _LIMIT]    # ✅ 전역이라 보인다
```

같은 함정이 [1.10 함수](#/functions)의 LEGB 규칙, [1.12 클래스](#/classes)의 클래스 본문 실행 모델과 이어진다.
:::

## PEP 709: 3.12에서 프레임이 사라졌다

익명 함수를 만들어 호출하는 방식에는 대가가 있었다. **컴프리헨션 하나마다 함수 객체 생성 + 프레임 푸시/팝이 붙는다.** 원소가 3개짜리 컴프리헨션에서 이 고정 비용은 실제 작업보다 크다.

3.12의 [PEP 709](#/bytecode)는 이걸 없앴다. **리스트·딕트·셋 컴프리헨션은 이제 감싸는 함수 안으로 인라인된다.** 직접 확인할 수 있다.

```python title="inline_proof.py"
import dis

def f(data):
    return [x * x for x in data]

print(f.__code__.co_consts)     # (None,)      <- <listcomp> 코드 객체가 없다!
print(f.__code__.co_varnames)   # ('data', 'x') <- x 가 f 의 지역 변수가 됐다
dis.dis(f)
```

```text nolines
LOAD_FAST_BORROW         0 (data)
GET_ITER
LOAD_FAST_AND_CLEAR      1 (x)      <- 기존 x 값을 스택에 밀어두고 비운다
SWAP                     2
BUILD_LIST               0
SWAP                     2
FOR_ITER                11
STORE_FAST_LOAD_FAST    17 (x, x)
LOAD_FAST_BORROW         1 (x)
BINARY_OP                5 (*)
LIST_APPEND              2
JUMP_BACKWARD           13
END_FOR
POP_ITER
SWAP                     2
STORE_FAST               1 (x)      <- 밀어뒀던 값을 되돌린다
RETURN_VALUE
```

`CALL` 이 없다. 함수 호출이 아니라 **평범한 루프**다. 격리는 `LOAD_FAST_AND_CLEAR` / `STORE_FAST` 한 쌍이 만든다 — 컴프리헨션 변수와 이름이 같은 지역 변수가 있으면 그 값을 스택에 잠깐 치워 뒀다가, 끝나면 되돌려 놓는다.

```pyrepl
>>> def f():
...     x = "함수의 x"
...     r = [x for x in range(3)]
...     return x, r
...
>>> f()
('함수의 x', [0, 1, 2])
```

예외가 나도 복원된다. 위 `dis` 출력 아래에 붙는 `ExceptionTable: L1 to L4 -> L5` 가 그 보장이다.

::: deep 인라이닝이 새 나오는 지점 세 개
설계 목표는 "성능은 올리되 관찰 가능한 동작은 그대로"였다. 완벽하진 않다. 세 군데서 티가 난다.

**① 트레이스백에서 `<listcomp>` 프레임이 사라졌다.**

```python title="tb.py"
def boom_listcomp(): return [1 / x for x in [1, 0]]
def boom_genexpr():  return list(1 / x for x in [1, 0])
```

```text nolines
  File "tb.py", line 1, in boom_listcomp
    def boom_listcomp(): return [1 / x for x in [1, 0]]
                                 ~~^~~
ZeroDivisionError: division by zero
```

프레임이 하나다. 반면 제너레이터 표현식은 여전히 `<genexpr>` 프레임을 남긴다.

```text nolines
  File "tb.py", line 2, in boom_genexpr
    def boom_genexpr():  return list(1 / x for x in [1, 0])
  File "tb.py", line 2, in <genexpr>
    def boom_genexpr():  return list(1 / x for x in [1, 0])
                                     ~~^~~
ZeroDivisionError: division by zero
```

**② `sys._getframe()` 이 거짓말을 하지 않게 됐다.**

```python title="frame.py"
import sys, inspect

def outer():
    return [sys._getframe().f_code.co_name for _ in range(1)]

def outer_g():
    return list(sys._getframe().f_code.co_name for _ in range(1))

print(outer())     # ['outer']       <- 3.11 이었다면 ['<listcomp>']
print(outer_g())   # ['<genexpr>']
```

프레임을 세는 코드(로깅 라이브러리의 호출자 추적, 프로파일러)가 3.12에서 결과가 달라지는 이유가 여기 있다.

**③ 예외 종류가 바뀌었다.** 이게 제일 미묘하다.

```python title="err.py"
def k():
    r = [w for w in range(3)]
    return w             # 컴프리헨션 변수를 밖에서 읽으면?
```

3.11에서 `w` 는 `k` 의 지역 변수가 **아니었으므로** 전역/빌트인을 뒤지다 `NameError`. 3.12+에서 `w` 는 인라이닝 때문에 `k.__code__.co_varnames` 에 **들어 있다.** 보통 값 없는 지역 변수를 읽으면 `UnboundLocalError` 다. 그런데:

```pyrepl
>>> k.__code__.co_varnames
('w', 'r')
>>> k()
Traceback (most recent call last):
  ...
NameError: name 'w' is not defined
```

`UnboundLocalError` 가 아니라 `NameError` 다. 컴파일러가 이 자리에 `LOAD_FAST_CHECK` 대신 `NameError` 를 던지는 경로를 넣어서 **3.11과 같은 예외를 흉내 낸다.** 호환성을 위해 일부러 넣은 거짓말이다.

```pyrepl
>>> try:
...     k()
... except NameError as e:
...     print(type(e).__name__, isinstance(e, UnboundLocalError))
...
NameError False
```

일반 지역 변수와 비교하면 차이가 선명하다.

```pyrepl
>>> def m():
...     return v
...     v = 1
...
>>> m()
Traceback (most recent call last):
  ...
UnboundLocalError: cannot access local variable 'v' where it is not associated with a value
```

`v` 와 `w` 는 **둘 다 `co_varnames` 에 있고 둘 다 값이 없다.** 그런데 예외가 다르다. 그 차이가 곧 인라이닝의 지문이다.
:::

::: perf 인라이닝이 실제로 얼마를 아꼈나
PEP 709 문서가 보고한 값은 **작은 컴프리헨션에서 최대 2배, 종합 벤치마크에서 약 11%** 다. 3.11이 손에 없으니 그 수치를 재현할 수는 없다. 대신 **3.11이 하던 일을 손으로 재현**해서 고정 비용만 재 보자.

```python title="frame_cost.py"
import timeit

src = """
def inlined(data):
    return [x for x in data]

def _lc(it):                 # 3.11 이 몰래 만들던 <listcomp>
    return [x for x in it]

def framed(data):
    return _lc(data)
"""
setup = src + "\ndata = []"       # 빈 입력 = 고정 비용만 남는다
a = min(timeit.repeat("inlined(data)", setup, number=500_000, repeat=5))
b = min(timeit.repeat("framed(data)",  setup, number=500_000, repeat=5))
print(f"inlined {a / 5e5 * 1e9:.1f} ns  framed {b / 5e5 * 1e9:.1f} ns  "
      f"delta {(b - a) / 5e5 * 1e9:.1f} ns")
```

```text nolines
inlined 35.9 ns  framed 50.6 ns  delta 14.7 ns
```

(3회 반복 실행하면 델타는 14.7~15.4ns 사이. **컴프리헨션 하나당 약 15ns.** 이게 3.12가 없애 준 값이다.)

작아 보이지만 방향을 뒤집어 읽어라. **한 번 도는 데 15ns라면, 컴프리헨션이 루프 안에 있고 그 루프가 백만 번 돌면 15ms다.** 그리고 실무 코드에서 컴프리헨션은 대부분 원소 3~10개짜리로 **자주** 실행된다. PEP 709가 노린 건 정확히 그 패턴이다.
:::

::: warn 제너레이터 표현식은 인라인되지 않는다
PEP 709는 **리스트·딕트·셋 컴프리헨션만** 다룬다. 제너레이터 표현식은 지금도 별도 코드 객체와 프레임을 만든다. 만들 수밖에 없다 — **중단했다가 재개해야 하니 프레임이 살아 있어야 한다.** 그게 제너레이터의 존재 이유다.

```pyrepl
>>> def g(data): return (x * x for x in data)
...
>>> g.__code__.co_consts
(<code object <genexpr> at 0x..., line 1>,)
```

앞의 표에서 `list(genexpr)` 가 컴프리헨션보다 (n=1000 기준) 약 2배 느렸던 이유의 절반이 여기 있다. 3.12 이후 둘의 격차는 **더 벌어졌다.**
:::

::: deep 인라이닝이 포기되는 조건
컴프리헨션 변수가 **클로저에 잡히면** 이야기가 달라진다. 함정 하나가 여기 숨어 있다.

```pyrepl
>>> fs = [lambda: i for i in range(3)]
>>> [f() for f in fs]
[2, 2, 2]
```

전부 `2` 다. **늦은 바인딩**(late binding)이다. 세 람다가 `i` 라는 **같은 셀 객체**를 공유하고, 컴프리헨션이 끝난 시점의 `i` 는 `2` 다.

인라이닝은 여전히 일어난다. 다만 `i` 가 셀 변수로 승격된다.

```pyrepl
>>> def makes_lambda(): return [lambda: i for i in range(3)]
...
>>> makes_lambda.__code__.co_consts       # <listcomp> 없음 = 인라인됨
(3, <code object <lambda> at 0x..., line 1>)
>>> makes_lambda.__code__.co_cellvars     # i 가 셀로 올라갔다
('i',)
```

3.11에서도 결과는 `[2, 2, 2]` 였다 — 그때는 `<listcomp>` 프레임 안의 셀이었을 뿐이다. **동작은 안 바뀌었고 그게 PEP 709의 목표였다.**

고치는 법은 [1.10 함수](#/functions)의 기본 인자 트릭이다.

```pyrepl
>>> fs = [lambda i=i: i for i in range(3)]
>>> [f() for f in fs]
[0, 1, 2]
```

셀 변수와 `co_cellvars` 의 정체는 [1.10 함수](#/functions)에서, 바이트코드 읽는 법은 [3.7 바이트코드](#/bytecode)에서 제대로 다룬다.
:::

## walrus 조합: 두 번 계산하지 않기

컴프리헨션의 구조적 약점 하나. **조건절에서 쓴 값을 결과 표현식에서 다시 쓸 수 없다.**

```python
import math

nums = [1, 4, 9, 16, 25, 30]

# ❌ isqrt 를 원소마다 두 번 호출한다
roots = [math.isqrt(n) for n in nums if math.isqrt(n) ** 2 == n]
```

3.8의 walrus 연산자(`:=`, [PEP 572](#/control-flow))가 이 자리를 위해 있다.

```python
# ✅ 한 번만 호출하고 이름을 붙여 재사용
roots = [r for n in nums if (r := math.isqrt(n)) ** 2 == n]
```

```pyrepl
>>> [r for n in [1, 4, 9, 16, 25, 30] if (r := math.isqrt(n)) ** 2 == n]
[1, 2, 3, 4, 5]
```

**평가 순서가 이걸 가능하게 한다.** `if` 절이 결과 표현식보다 먼저 실행되므로, 조건절에서 만든 이름을 결과 표현식이 쓸 수 있다. 반대는 안 된다.

::: warn walrus 는 스코프를 뚫고 나온다 — 의도된 설계다
```pyrepl
>>> result = [q for w in [1, 2, 3] if (q := w * w) > 2]
>>> result
[4, 9]
>>> q
9
```

`q` 가 밖에 남았다. 컴프리헨션 변수 `w` 는 안 새는데 `q` 는 샌다.

**버그가 아니다.** PEP 572가 명시적으로 정한 규칙이다 — 컴프리헨션 안의 `:=` 는 **컴프리헨션을 감싸는 스코프**에 바인딩한다. 근거는 이 관용구를 살리기 위해서였다.

```python
if any((match := pattern.search(line)) for line in lines):
    print(match.group())     # 밖으로 새기 때문에 쓸 수 있다
```

그래도 **의도적으로 회수할 때만 이걸 쓰고, 나머지는 이름 충돌을 조심하라.** 컴프리헨션 위쪽에서 쓰던 이름을 walrus로 덮어쓰면 조용히 망가진다.

그리고 `for` 절의 대상 변수는 walrus로 못 쓴다. `[i := x for x in data]` 는 괜찮지만 `[x for (x := i) in data]` 는 `SyntaxError` 다.
:::

## 언제 for문이 더 나은가

이 절에서 제일 중요한 부분이다. 컴프리헨션이 빠르다는 걸 배운 사람은 **모든 걸 컴프리헨션으로 쓰려 한다.** 그게 다음 함정이다.

### ① 부수 효과가 목적이면 절대 쓰지 마라

```python
# ❌ 백만 개짜리 None 리스트를 만들어서 즉시 버린다
[print(x) for x in data]
[cursor.execute(sql, row) for row in rows]

# ✅
for x in data:
    print(x)
```

컴프리헨션은 **리스트를 만드는 문법**이다. 리스트가 필요 없는데 쓰면 메모리를 쓰고 버린다. 그리고 읽는 사람에게 "이 리스트는 어디에 쓰이지?" 하는 질문을 남긴다. 답은 "안 쓰인다"다.

::: cote 코딩테스트 포인트
`[input() for _ in range(n)]` 은 괜찮지만 `[print(x) for x in ans]` 는 아니다. 백만 줄 출력에서 이 리스트 하나가 메모리 한도를 넘긴다.

```python
# ❌
[print(x) for x in ans]
# ✅ 출력은 한 번에 모아서
sys.stdout.write("\n".join(map(str, ans)))
```

입출력 최적화는 [8.2 입출력 최적화](#/io-optimize)에서 따로 다룬다.
:::

### ② `break` 가 필요하면 못 쓴다

컴프리헨션에는 `break` 도 `continue` 도 없다. `if` 절이 `continue` 를 대신할 뿐이다.

```python
# 조기 종료가 필요하면 → 제너레이터 + next / itertools
first = next((x for x in data if is_valid(x)), None)

from itertools import takewhile
prefix = list(takewhile(lambda x: x < limit, data))
```

`itertools.takewhile` / `islice` 로 커버되는 범위를 넘어가면 그냥 `for` 문을 써라.

### ③ 상태를 누적하면 못 쓴다

```python
# ❌ walrus 로 억지로 되긴 한다. 읽지 마라.
total = 0
running = [total := total + x for x in data]

# ✅ 표준 라이브러리에 이미 있다
from itertools import accumulate
running = list(accumulate(data))
```

**walrus로 할 수 있다고 해서 해도 된다는 뜻은 아니다.** 누적합은 [3.2 itertools](#/itertools)의 `accumulate`, 누적 카운트는 [7.6 해시](#/hashing)의 `Counter` 가 이미 있다.

### ④ 예외 처리가 필요하면 못 쓴다

`try/except` 는 문(statement)이다. 컴프리헨션 안에는 식(expression)만 들어간다.

```python
# ❌ 문법적으로 불가능
values = [int(s) for s in raw]      # 하나만 이상해도 전체가 터진다

# ✅ 헬퍼로 뺀다
def to_int(s, default=0):
    try:
        return int(s)
    except ValueError:
        return default

values = [to_int(s) for s in raw]
```

이 제약은 실은 **선물**이다. 컴프리헨션 안에서 예외가 나면 원인 지점이 명확하다. `for` 문이었다면 `try` 를 어디에 걸지가 설계 문제가 된다.

### ⑤ 세 줄이 넘어가면 지는 거다

```python
# ❌ 읽을 수 있는가?
result = [transform(x, y) for x in xs if pred(x)
          for y in ys if x != y and check(x, y)
          if transform(x, y) is not None]
```

경험칙 두 개다.

> **`for` 절이 두 개를 넘으면 for문으로 풀어라.**
> **컴프리헨션이 한 화면에 안 들어오면 for문으로 풀어라.**

컴프리헨션의 장점은 속도가 아니라 **"이건 변환이지 절차가 아니다"라는 신호**다. 그 신호가 안 읽히면 장점이 사라진다. 15%의 속도를 위해 동료(6개월 뒤의 당신 포함)의 30초를 팔지 마라. 진짜로 그 15%가 필요한 지점은 [5.1 프로파일링](#/profiling)으로 찾아야 한다.

::: cote 코딩테스트 포인트
컴프리헨션이 제값을 하는 자리는 시험장에서 거의 정해져 있다.

```python
import sys
input = sys.stdin.readline

n, m = map(int, input().split())

# ① 격자 입력 — 이건 컴프리헨션이 정답이다
board = [list(map(int, input().split())) for _ in range(n)]

# ② 방문 배열 — [[False] * m] * n 은 같은 행 n개다! (1.1절)
visited = [[False] * m for _ in range(n)]

# ③ 3차원 DP
dp = [[[0] * m for _ in range(n)] for _ in range(k)]

# ④ 조건 검사는 제너레이터로 — 조기 종료가 살아 있다
if any(board[i][j] == 0 for i in range(n) for j in range(m)):
    ...
```

②의 `[[False] * m for _ in range(n)]` 가 왜 필수인지는 [1.1 객체, 이름, 참조](#/objects-names)에서 이미 봤다. `*` 는 객체를 복사하지 않고 참조를 늘린다.

그리고 **반례**: 아래 코드는 시험장에서 시간 초과를 낸다.

```python
# ❌ n이 10만이면 매 i마다 리스트를 새로 만든다 → O(n²)
for i in range(n):
    if target in [a[j] for j in range(i)]:
        ...
```

컴프리헨션이 느린 게 아니라 **필요 없는 리스트를 반복 생성**하는 게 느리다. `in` 은 조기 종료하는 연산이니 리스트를 만들 이유가 없다. 더 좋은 건 `set` 하나를 밖에 두고 갱신하는 것이다 ([7.6 해시](#/hashing)).

전반적인 시간 초과 회피는 [8.3 시간 초과를 피하는 관용구](#/tle)에서.
:::

::: tip NumPy가 있으면 컴프리헨션을 지워라
숫자 배열이라면 이 절의 모든 논의가 무의미해진다.

```python
# ❌ 파이썬 루프. 원소마다 int 객체 하나씩.
result = [x * 2 + 1 for x in data]

# ✅ C 루프. 객체 없음.
result = arr * 2 + 1
```

컴프리헨션은 아무리 빨라도 **원소마다 파이썬 객체를 만든다.** NumPy는 안 만든다. 자릿수가 다른 이야기다. 이 사고 전환이 [9.2 브로드캐스팅과 벡터화](#/broadcasting)의 주제다.
:::

## 요약

- 컴프리헨션은 for문의 축약이 아니라 **다른 바이트코드**다. `LIST_APPEND` 전용 명령 덕에 `for` + `append` 보다 약 1.2~1.3배 빠르다.
- `[]` `{}` `{k: v}` 는 **즉시** 전부 만든다. `()` 는 **제너레이터**를 만들고 아무것도 안 만든다. 튜플 컴프리헨션은 없다.
- 제너레이터 표현식의 크기는 **원소 수와 무관하게 208바이트**. `sum([...])` 38.6MB vs `sum(...)` 480바이트, 84,000배.
- **`any`/`all`/`next` 에 대괄호를 넣으면 조기 종료가 죽는다.** 실측 약 8만 배.
- 반대로 **어차피 리스트가 될 거면 제너레이터를 경유하지 마라.** `list(genexpr)` 는 컴프리헨션의 2배 느리다.
- 중첩은 **쓴 순서대로 위에서 아래로** 펼친다. 결과 표현식은 맨 안쪽. 전치처럼 컴프리헨션이 **겹친** 경우와 헷갈리지 마라.
- 컴프리헨션 변수는 안 샌다. **`:=` 로 만든 이름은 샌다** — PEP 572가 그렇게 정했다.
- 3.12+ 는 리스트·딕트·셋 컴프리헨션을 **인라인**한다(PEP 709). 프레임이 없고, 트레이스백에 `<listcomp>` 가 안 나오고, 컴프리헨션 하나당 약 15ns를 아낀다. **제너레이터 표현식은 해당 없다.**
- **클래스 본문 안 컴프리헨션은 조건절에서 클래스 변수를 못 본다.** 첫 iterable만 바깥에서 평가된다.
- 부수 효과, `break`, 상태 누적, `try/except` 중 하나라도 필요하면 **for문을 써라.** `for` 절이 두 개를 넘어도 마찬가지다.

::: quiz 연습문제
1. 다음 넷의 출력을 **먼저 예측한 뒤** 실행하라. 틀린 것이 있다면 왜인가?

   ```python
   matrix = [[1, 2], [3, 4]]
   print([c for row in matrix for c in row])
   print([[c for c in row] for row in matrix])
   print([[row[i] for row in matrix] for i in range(2)])
   print([c for c in row for row in matrix])
   ```

2. 아래 함수는 100만 줄짜리 로그에서 메모리 초과를 낸다. 답을 바꾸지 않고 상수 메모리로 고쳐라.

   ```python
   def error_count(path):
       lines = [ln for ln in open(path)]
       errors = [ln for ln in lines if "ERROR" in ln]
       return len(errors)
   ```

3. 다음 클래스는 `NameError` 를 낸다. **어느 줄이고, 왜인가?** 그리고 `threshold` 를 `for` 절의 iterable 자리로 옮기면(`for v in values if v > threshold` → `for v in above(values, threshold)`) 왜 해결되는가?

   ```python
   class Filter:
       threshold = 5
       values = [1, 6, 3, 9]
       passed = [v for v in values if v > threshold]
   ```

4. `sys.getsizeof` 로 확인하라. `[x for x in range(1000)]` 과 `list(range(1000))` 은 원소가 같은데 크기가 800바이트 다르다. 왜인가? 그리고 `list(x for x in range(1000))` 은 둘 중 어느 쪽 크기가 나올지 예측한 뒤 확인하라.

5. 다음 두 줄의 차이를 설명하라. 그리고 두 번째가 `[2, 2, 2]` 가 되는 이유를 `co_cellvars` 로 증명하라.

   ```python
   print([f() for f in [lambda i=i: i for i in range(3)]])
   print([f() for f in [lambda: i for i in range(3)]])
   ```

6. **깊이 생각해 볼 문제.** 다음은 3.12에서 동작이 바뀐 코드다. 무엇이 바뀌었고, 왜 그런가? `dis` 로 확인하라.

   ```python
   import sys

   def who_called_me():
       return [sys._getframe(1).f_code.co_name for _ in range(1)]

   def caller():
       return who_called_me()

   print(caller())
   ```
:::

**다음 절**: [1.10 함수: 인자, 스코프, 클로저](#/functions) — 이 절에서 계속 튀어나온 "셀 변수"와 LEGB의 정체를 밝힌다. 그리고 `def f(x=[])` 가 왜 파이썬 최악의 함정인지도.
