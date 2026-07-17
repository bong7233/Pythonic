# 1.7 set과 frozenset

::: lead
`set` 을 "중복 없는 리스트" 정도로 알고 있으면 절반만 아는 것이다. `set` 은 **값 없는 dict가 아니라 별개의 자료구조**고, 그래서 dict가 지키는 순서 보장을 지키지 않는다. `in` 이 $O(1)$ 이라는 말도 조건부다. 이 절은 `set` 의 내부를 열어 보고, 그 구조에서 어떤 성능과 어떤 함정이 나오는지 본다. 그리고 `frozenset` 이 왜 존재하는지 — 해시 가능성이라는 하나의 이유로 — 설명한다.
:::

## 문제부터: 중복 제거를 $O(n^2)$ 로 하고 있다

리스트에서 중복을 없애라고 하면 많은 사람이 이렇게 쓴다.

```python title="dedup.py"
def dedup(data):
    out = []
    for x in data:
        if x not in out:      # ❌ 여기가 문제다
            out.append(x)
    return out
```

읽기 쉽고, 순서도 지키고, 잘 동작한다. 그리고 **느리다.**

```python title="측정 — 20,000개"
timeit.timeit(lambda: dedup(data), number=1)          # 0.400초
timeit.timeit(lambda: list(set(data)), number=1)      # 0.00059초  → 약 680배
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

원소 2만 개에 680배다. 20만 개면 격차가 다시 10배로 벌어진다. `x not in out` 이 리스트를 **매번 처음부터 훑기** 때문이다. `set` 은 이 비교 자체를 없앤다. 어떻게 없애는지가 이 절의 내용이다.

## set은 값 없는 dict가 아니다

가장 흔한 오해부터 부순다.

> "dict는 해시 테이블이고, set은 값을 안 쓰는 dict겠지."

**아니다.** CPython 소스에서 dict는 `Objects/dictobject.c`, set은 `Objects/setobject.c` 다. 완전히 다른 파일, 완전히 다른 구현이다. 둘 다 해시 테이블이지만 **설계 목표가 다르다.**

[1.6 dict](#/dict)에서 봤듯 3.6 이후의 dict는 **compact dict** 다. 인덱스 배열과 엔트리 배열을 분리해 **삽입 순서를 보존**한다. 공짜가 아니다 — 간접 참조가 한 단계 더 생긴다. set은 그 대가를 낼 이유가 없다. 집합은 **순서 없는 모음**이고, 순서를 보존해 봐야 쓸 곳이 없다. 대신 그 예산을 **집합 연산**에 쓴다. 그래서 set은 **compact 하지 않은, 고전적인 open addressing 해시 테이블**을 유지한다.

### 구조를 그림으로

```text nolines
dict  (compact, 3.6+)

  indices: [ -1 ][  0 ][ -1 ][  1 ][ -1 ][ -1 ][ -1 ][  2 ]
                    │           │                       │
                    ▼           ▼                       ▼
  entries: [ (hash, key, value), (hash, key, value), ... ]
             ^^^^^^^^^^^^^^^^^^ 24 bytes, packed in insert order


set  (open addressing)

  table:   [     ][ h,k ][     ][ h,k ][     ][     ][     ][ h,k ]
                    ^^^^^ 16 bytes, sits where the hash put it
                    no separate index array, no insert order
```

dict는 두 층이다. `indices` 가 슬롯이고, 실제 데이터는 `entries` 에 **삽입 순서대로** 빽빽이 쌓인다. set은 한 층이다. `(hash, key)` 쌍 16바이트가 **해시가 지정한 슬롯에 그대로 앉는다.** 삽입 순서를 기록하는 곳이 어디에도 없다. **이 그림 하나에서 이 절의 나머지가 전부 따라 나온다.**

### 증거 1: 빈 컨테이너의 크기

```pyrepl
>>> import sys
>>> sys.getsizeof(set())
216
>>> sys.getsizeof({})
64
>>> sys.getsizeof(frozenset())
216
```

빈 set이 빈 dict보다 **3배 이상 크다.** 빈 dict는 `indices` 를 **아예 할당하지 않는다** — 모든 빈 dict가 공유하는 전역 "empty keys" 객체를 가리킬 뿐이다. 반면 `PySetObject` 구조체는 **8칸짜리 `smalltable` 을 자기 몸 안에 박아 두고 있다.** 8 × 16 = 128바이트가 객체에 포함된다. **작은 set이 압도적으로 많아서** 힙 할당을 한 번 더 하지 않으려는 것이다.

```pyrepl
>>> sys.getsizeof({1, 2, 3, 4})     # 아직 smalltable 안이다
216
>>> sys.getsizeof({1, 2, 3, 4, 5})  # 5번째에서 힙으로 나간다
472
```

::: deep 472? 조금 전 성장 표에는 728이라고 나와 있었는데
바로 다음 절의 성장 패턴 표는 `set(range(5))` 로 쟀고 거기서는 728이 나온다. 그런데 `{1, 2, 3, 4, 5}` 리터럴은 472다. **같은 다섯 개의 정수인데 만드는 방법에 따라 크기가 다르다.** 원인은 바이트코드에 있다.

```pyrepl
>>> import dis
>>> dis.dis(compile("{1, 2, 3, 4, 5}", "<m>", "eval"))
  0           RESUME                   0
  1           BUILD_SET                0
              LOAD_CONST               1 (frozenset({1, 2, 3, 4, 5}))
              SET_UPDATE               1
              RETURN_VALUE
```

컴파일러는 원소가 전부 상수인 set 리터럴을 **컴파일 타임에 frozenset 상수로 미리 만들어 두고**, 실행 시점에는 빈 set을 하나 만든 뒤(`BUILD_SET`) 그 frozenset을 통째로 부어 넣는다(`SET_UPDATE`). 반면 `set(range(5))` 나 `.add()` 루프는 원소를 **하나씩** 넣는다.

이 두 경로가 테이블 크기를 계산하는 공식이 다르다. `setobject.c` 에서 원소를 하나씩 추가하다 적재율(3/5)을 넘겨 리사이즈할 때는 `used * 4` 로 새 크기를 잡는다 — 5개째에서 `fill=5, mask=7`(테이블 8칸)일 때 $5\times5=25 \ge 7\times3=21$ 이라 리사이즈, 새 크기는 $5\times4=20$ 보다 큰 2의 거듭제곱인 **32**. $216 + 32\times16 = 728$.

반면 `SET_UPDATE`(그리고 다른 set/frozenset을 통째로 병합하는 `set_merge`)는 **미리 최종 개수를 알고 있어서** 한 번에 크기를 정한다. 이때 쓰는 배수는 `used * 2` 다 — $5\times2=10$ 보다 큰 2의 거듭제곱인 **16**. $216 + 16\times16 = 472$.

**같은 다섯 개의 정수, 다른 만드는 경로, 다른 최종 크기.** `set(frozenset(range(5)))` 로 확인해도 472가 나온다 — 이미 있는 set/frozenset을 통째로 옮기면 항상 이 저렴한 경로를 탄다. 요점은 숫자 자체가 아니라 **"같은 값의 set이라도 만든 방법에 따라 메모리 크기가 달라질 수 있다"** 는 것 — set의 크기는 값만으로 결정되지 않는다.
:::

### 증거 2: 성장 패턴이 dict와 다르다

`sys.getsizeof(set(range(n)))` 이 뛰는 지점을 찍으면 이렇다.

```text nolines
n=  0  size=216
n=  5  size=728
n= 19  size=2264
n= 77  size=8408
n=307  size=32984
```

같은 실험을 dict로 하면 임계점이 `1, 6, 11, 22, 43, 86, 171, 342` 다. **완전히 다르다.**

::: deep 3/5 vs 2/3 — 적재율의 차이
set의 리사이즈 조건은 `setobject.c` 에 이렇게 박혀 있다.

```c
if ((size_t)so->fill*5 < mask*3)
    return 0;                       /* 아직 여유 있음 */
return set_table_resize(so, so->used > 50000 ? so->used*2 : so->used*4);
```

**적재율 3/5(60%)** 를 넘으면 리사이즈하고, 새 크기는 `used * 4` — **4배씩 뛴다**(5만 개를 넘으면 `used * 2` 로 완화). dict는 적재율 **2/3(66.7%)** 다. set이 더 헐렁하게 산다.

위 실측이 정확히 이 공식이다. 원소 19개일 때 테이블 크기는 32(mask=31)고, $19 \times 5 = 95 \ge 31 \times 3 = 93$ 이므로 리사이즈. 새 크기는 $19 \times 4 = 76$ 보다 큰 최소 2의 거듭제곱, 즉 **128**. 실측 2264 = 216 + 128×16. 맞는다.

**왜 set이 더 헐렁한가?** set의 존재 이유가 `in` 이기 때문이다. 적재율이 낮을수록 충돌이 줄고 조회가 빨라진다. dict는 값까지 저장해 메모리 부담이 커서 더 빡빡하게 채운다. **같은 트레이드오프를 두 자료구조가 다르게 잡은 것**이다.
:::

### 증거 3: 백만 원소에서의 실제 크기

```python title="1,000,000개 저장 비용"
sys.getsizeof(set(range(n)))            # 33,554,648  (32 MB)
sys.getsizeof(dict.fromkeys(range(n)))  # 41,943,128  (40 MB)
sys.getsizeof(list(range(n)))           #  8,000,056  ( 7.6 MB)
```

(`getsizeof` 는 **컨테이너 자체**만 센다. 안에 든 정수 100만 개는 별도다. 전체를 재려면 [5.2 메모리 모델](#/memory)의 `tracemalloc` 을 쓴다.)

리스트가 4배 작다. **중복 없는 컬렉션이 필요하지 않다면 set을 쓰지 마라.** set은 `in` 을 위해 메모리를 4배 지불하는 거래다.

### 그리고 가장 중요한 차이: 순서

dict는 삽입 순서를 보장한다. **set은 아무것도 보장하지 않는다.** 명세에 그렇게 쓰여 있고, 이 사실이 실제로 물린다.

```pyrepl
>>> s = set()
>>> for x in [1, 9, 17]:
...     s.add(x)
...
>>> t = set()
>>> for x in [17, 9, 1]:
...     t.add(x)
...
>>> s == t
True
>>> list(s)
[1, 9, 17]
>>> list(t)
[17, 9, 1]
>>> list(s) == list(t)
False
```

**같은 집합인데 순회 순서가 다르다.** 왜 이렇게 되는지가 set 내부의 핵심이다.

::: deep 선형 프로빙 — set이 dict와 결정적으로 다른 지점
세 원소의 해시는 자기 자신이다(작은 정수의 `hash(n) == n`). 테이블 크기 8, 마스크 7이므로:

```text nolines
hash(1)  & 7 == 1
hash(9)  & 7 == 1        <- collision
hash(17) & 7 == 1        <- collision
```

셋 다 슬롯 1을 원한다. 충돌이 나면 CPython set은 **바로 옆 슬롯부터 순서대로 훑는다**(linear probing). `setobject.c` 의 `LINEAR_PROBES` 가 9다 — 아홉 칸까지 이웃을 선형 탐색한 뒤에야 `perturb` 기반 점프로 넘어간다.

```text nolines
insert 1, 9, 17                 insert 17, 9, 1

  slot 0 : ....                   slot 0 : ....
  slot 1 : 1                      slot 1 : 17
  slot 2 : 9                      slot 2 : 9
  slot 3 : 17                     slot 3 : 1
  slot 4 : ....                   slot 4 : ....

  iterate -> 1, 9, 17             iterate -> 17, 9, 1
```

순회는 슬롯 0번부터 끝까지 훑는 것뿐이다. **먼저 넣은 원소가 좋은 자리를 차지한다.** 그래서 삽입 순서가 순회 순서에 **영향을 준다** — 보존하는 게 아니라, 예측 불가능하게. 이게 최악이다. 보존이면 의존할 수 있고 완전 무작위면 아무도 의존하지 않는다. 어중간해서 사람이 속는다.

**왜 선형 프로빙인가?** 캐시 때문이다. 슬롯 하나가 16바이트, 캐시 라인은 보통 64바이트. 이웃 슬롯 네 개는 **이미 캐시에 올라와 있다.** 멀리 점프하면 캐시 미스지만 옆칸은 공짜다. dict는 엔트리가 별도 배열에 있어 이 이점을 못 살린다. **set만 할 수 있는 최적화다.**
:::

## `in` 이 $O(1)$ 이라는 말의 진짜 의미

이제 첫 문제로 돌아간다. 크기를 바꿔 가며 **마지막 원소를 찾는** 최악의 경우를 쟀다.

| 원소 수 | `t in lst` | `t in st` | 배수 |
| --- | --- | --- | --- |
| 100 | 0.34 μs | 19.2 ns | 18× |
| 1,000 | 3.28 μs | 23.4 ns | 140× |
| 10,000 | 34.4 μs | 23.4 ns | 1,472× |
| 100,000 | 337 μs | 23.3 ns | 14,481× |
| 1,000,000 | 3,665 μs | 23.3 ns | 157,278× |

리스트는 $n$ 에 정비례해 늘어난다. **set은 23ns 근처에서 꿈쩍도 안 한다.** 이게 $O(1)$ 이다.

숫자를 하나 기억해라. **set 조회는 약 20~25나노초다.** 이 상수를 알면 예산 계산이 된다. 100만 번 조회하면 20ms 남짓, 1000만 번이면 200ms 남짓이다. 코딩테스트의 1~2초 제한에서 무시 가능한 비용이다.

(Python 3.14.5 / Windows 기준 실측. `timeit.repeat` 로 5회 반복해 최솟값을 취했다. 절대 나노초 값은 기기·파이썬 빌드마다 다르지만, **set이 원소 수와 무관하게 평평하고 리스트는 선형으로 늘어난다는 패턴**은 어디서나 같다.)

::: cote 제약 조건에서 set을 읽어내라
문제에 이런 문장이 있으면 거의 항상 set(또는 dict)이다.

- "이미 방문한 지점인지 확인" → `visited = set()`
- "$A$ 에는 있고 $B$ 에는 없는 것" → `set(A) - set(B)`
- "두 리스트의 공통 원소" → `set(A) & set(B)`
- "중복을 제외한 개수" → `len(set(A))`
- "$N \le 10^5$, 각 원소마다 존재 여부 확인" → 리스트면 $10^{10}$, set이면 $10^5$

가장 흔한 시간 초과 패턴은 이거다.

```python
# ❌ O(n*m) — 제출하면 TLE
for x in queries:
    if x in data_list:
        ...

# ✅ O(n+m) — set 만드는 비용은 한 번뿐
data = set(data_list)
for x in queries:
    if x in data:
        ...
```

`set(data_list)` 를 만드는 데 $O(m)$ 이 든다. **한 번이라도 재사용할 거면 무조건 이득이다.** 딱 한 번 조회할 거라면 만들지 마라 — 그때는 리스트 순회가 더 싸다.
:::

### 단, 해시가 나쁘면 $O(n)$ 이다

$O(1)$ 은 **해시가 원소를 골고루 흩뿌릴 때**의 이야기다. 모두 같은 슬롯으로 몰리면 set은 그냥 리스트가 된다.

```python title="같은 해시를 반환하는 클래스"
class Good:
    __slots__ = ("v",)
    def __init__(self, v): self.v = v
    def __hash__(self): return hash(self.v)
    def __eq__(self, o): return self.v == o.v


class Evil:
    __slots__ = ("v",)
    def __init__(self, v): self.v = v
    def __hash__(self): return 1          # 전원 슬롯 1로 집합
    def __eq__(self, o): return self.v == o.v
```

원소 2,000개로 재면:

| 클래스 | set 생성 | `in` 1회 |
| --- | --- | --- |
| `Good` | 0.23 ms | 135 ns |
| `Evil` | 71.2 ms | 75,055 ns |

**조회가 556배 느려진다.** 생성은 316배다. `Evil` 의 `in` 은 평균 수백 번의 `__eq__` 호출이다. $O(1)$ 이 $O(n)$ 으로 무너진 것이다.

::: hist 해시 충돌 DoS와 해시 랜덤화
`Evil` 은 인위적이지만 **공격자는 이걸 의도적으로 만든다.** 2011년, 웹 서버가 POST 파라미터를 dict에 넣는다는 점을 이용해 **같은 해시를 갖는 문자열 수만 개**를 보내는 공격이 발표됐다(oCERT-2011-003). 서버는 $O(n^2)$ 에 빠져 CPU를 태웠다. 파이썬만이 아니라 PHP, Java, Ruby가 전부 당했다.

파이썬의 답이 **해시 랜덤화**다. 3.3부터 문자열과 bytes의 해시는 **프로세스마다 다른 무작위 시드**로 계산된다.

```pyrepl
>>> hash("spam")     # 첫 번째 실행
-3069898548465985079
>>> hash("spam")     # 인터프리터를 다시 띄우면
3219969064690369949
```

시드를 모르면 충돌 문자열을 미리 만들 수 없다. 알고리즘은 SipHash-1-3(`sys.hash_info.algorithm` 이 `'siphash13'`, `seed_bits` 는 128).

**정수는 랜덤화되지 않는다.** `hash(42) == 42` 는 어느 프로세스에서나 같다. 정수 해시가 항등 함수인 건 의도된 설계다 — 연속된 정수가 연속된 슬롯에 들어가 캐시 지역성이 좋아진다. 재현이 필요하면 `PYTHONHASHSEED=0` 으로 끌 수 있다. **테스트 환경에서만.**
:::

## 집합 연산

수학의 집합 연산이 그대로 있다. 이게 set을 쓰는 두 번째 이유다.

| 연산 | 연산자 | 메서드 | 결과 |
| --- | --- | --- | --- |
| 합집합 | `a \| b` | `a.union(b)` | 둘 중 하나에라도 있는 것 |
| 교집합 | `a & b` | `a.intersection(b)` | 둘 다 있는 것 |
| 차집합 | `a - b` | `a.difference(b)` | a에만 있는 것 |
| 대칭차 | `a ^ b` | `a.symmetric_difference(b)` | 한쪽에만 있는 것 |
| 부분집합 | `a <= b` | `a.issubset(b)` | a의 모든 원소가 b에 있나 |
| 진부분집합 | `a < b` | (없음) | 부분집합이면서 같지 않나 |
| 서로소 | (없음) | `a.isdisjoint(b)` | 공통 원소가 없나 |

제자리 수정판도 있다: `|=` / `update`, `&=` / `intersection_update`, `-=` / `difference_update`, `^=` / `symmetric_difference_update`.

### 연산자와 메서드는 같지 않다

표만 보면 둘이 동의어 같다. **아니다.** 이게 set에서 가장 실용적인 지식이다.

```pyrepl
>>> a = {1, 2, 3}
>>> a | [3, 4]
Traceback (most recent call last):
  ...
TypeError: unsupported operand type(s) for |: 'set' and 'list'
>>> a.union([3, 4])
{1, 2, 3, 4}
```

**연산자는 양쪽 다 set(또는 frozenset)이어야 한다. 메서드는 아무 이터러블이나 받는다.**

메서드는 인자를 여러 개 받는 것까지 된다.

```pyrepl
>>> {1, 2, 3}.union("ab", (7,), {8: 0})
{1, 2, 3, 'b', 'a', 7, 8}
>>> {1, 2, 3}.difference([1], [2])
{3}
```

dict를 넘기면 키만 쓴다. 비교 연산자도 같은 규칙이다.

```pyrepl
>>> {1, 2}.issubset([1, 2, 3])
True
>>> {1, 2} <= [1, 2, 3]
Traceback (most recent call last):
  ...
TypeError: '<=' not supported between instances of 'set' and 'list'
```

::: hist 왜 일부러 다르게 만들었나
우연이 아니다. 파이썬 문서가 이 차이를 명시적으로 문서화하고 있다. 이유는 **연산자의 대칭성**이다. `a | b` 는 `b | a` 와 같아야 한다. 그런데 리스트를 허용하면 `[1,2] | {3}` 은 `set.__ror__` 로 넘어가 동작해 버리고, 결과 타입이 뭔지도 애매해진다.

그래서 **연산자는 엄격하게, 메서드는 관대하게** 나눴다. 연산자는 "집합 대수를 쓰고 있다"는 신호고, 메서드는 "이터러블에서 집합 연산을 끌어낸다"는 도구다.

실전 규칙은 간단하다. **양쪽이 이미 set이면 연산자를 써라. 한쪽이 리스트/제너레이터면 메서드를 써라** — 불필요한 `set()` 변환을 아낄 수 있다.

```python
# ❌ 임시 set을 만들고 버린다
result = big_set & set(some_list)

# ✅ 임시 객체 없이 직접
result = big_set.intersection(some_list)
```
:::

한 가지 더. **반환 타입은 왼쪽 피연산자를 따른다.**

```pyrepl
>>> type({1, 2} | frozenset([3]))
<class 'set'>
>>> type(frozenset([3]) | {1, 2})
<class 'frozenset'>
```

섞어 쓰면 **결과 타입이 순서에 달렸다.** frozenset을 유지하려면 왼쪽에 두거나 결과를 `frozenset(...)` 으로 감싸라. 이건 잠시 뒤 메모이제이션에서 실제로 물린다.

::: danger 부분집합 비교는 전순서가 아니다
`<`, `<=` 가 있으니 숫자처럼 정렬되는 것 같다. 아니다.

```pyrepl
>>> a, b = {1, 2}, {2, 3}
>>> a < b, a > b, a <= b, a >= b
(False, False, False, False)
```

**넷 다 False다.** 두 집합은 서로 부분집합이 아니다 — **비교 불가능**한 것이다. 이게 부분 순서(partial order)다.

그래서 숫자에서 성립하는 `not (a < b) == (a >= b)` 가 **집합에서는 깨진다.** `not (a < b)` 에는 "둘이 아예 무관한 경우"가 포함된다. 숫자 감각으로 집합 비교를 쓰면 조용히 틀린다.
:::

### CPython이 알아서 하는 최적화 두 가지

::: perf 교집합은 작은 쪽을 순회한다
$|A| = 10^6$, $|B| = 10$ 일 때 `A & B` 는 몇 번의 조회일까? 순진하게 구현하면 A를 100만 번 훑는다. CPython은 그렇게 안 한다.

```python title="측정"
import timeit

setup = "big = set(range(1_000_000)); small = set(range(10))"

timeit.timeit("small & big", setup, number=1000)   # 0.000121초
timeit.timeit("big & small", setup, number=1000)   # 0.000110초
```

(Python 3.14.5 / Windows 기준 실측.)

**완전히 같다.** `set_intersection` 이 두 집합의 크기를 비교해서 **작은 쪽을 순회하고 큰 쪽에서 조회한다.** 그래서 교집합은 $O(\min(|A|, |B|))$ 다.

이 최적화 때문에 다음이 성립한다.

```python
# ❌ 큰 집합을 강제로 순회한다 — 최적화가 안 먹는다
{x for x in big if x in small}

# ✅ CPython이 알아서 뒤집는다
big & small
```

같은 결과인데 후자가 압도적으로 빠르다. **직접 루프를 도는 순간 이 최적화를 잃는다.**
:::

::: perf isdisjoint 는 조기 종료한다
"공통 원소가 있나?"를 확인할 때 `a & b` 를 만들어서 비어 있는지 보면, **필요 없는 교집합 객체를 통째로 만든다.**

```python title="측정 — 백만 원소 두 개"
setup = "a = set(range(1_000_000)); b = set(range(1_000_000, 2_000_000))"
timeit.timeit("a.isdisjoint(b)", setup, number=10) / 10   # 3.79 ms/회
timeit.timeit("not (a & b)", setup, number=10) / 10       # 3.69 ms/회

# 첫 원소부터 겹치는 경우
setup2 = "a = set(range(1_000_000)); b = {0} | set(range(1_000_000, 2_000_000))"
timeit.timeit("a.isdisjoint(b)", setup2, number=10) / 10  # 1.19 μs/회
```

(Python 3.14.5 / Windows 기준 실측.) 전부 서로소일 때는 큰 차이가 없다. 어차피 다 훑어야 하니까. **겹치는 원소가 있으면 `isdisjoint` 는 그 순간 멈춘다** — 4ms 남짓이 1μs로 떨어진다. **3,000배** 이상이다.

교집합의 내용이 필요 없고 "겹치나?"만 궁금하면 **항상 `isdisjoint`** 다. 메모리도 안 쓴다.
:::

## 해시 가능성 — set에 들어갈 자격

set은 원소의 해시로 슬롯을 정한다. 그래서 **해시를 계산할 수 없는 객체는 들어갈 수 없다.**

```pyrepl
>>> {[1, 2]}
Traceback (most recent call last):
  ...
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
>>> {{1, 2}}
Traceback (most recent call last):
  ...
TypeError: cannot use 'set' as a set element (unhashable type: 'set')
```

`set` 자기 자신도 못 들어간다. **여기서 frozenset이 필요해진다.** 그 전에 규칙을 정확히 하자.

### 규칙: 해시는 변하면 안 된다

해시 가능의 조건은 두 가지다. (1) 생애 동안 `hash(x)` 가 **변하지 않는다.** (2) `a == b` 이면 `hash(a) == hash(b)` 다.

1번이 왜 필요한지는 명확하다. 해시가 슬롯을 정하는데 해시가 변하면 **객체가 자기 자리를 잃는다.** 그래서 가변 객체는 원칙적으로 해시 불가다.

::: danger 해시가 변하면 원소가 미아가 된다
직접 만들어 볼 수 있다. 이건 파이썬이 막지 않는다.

```python title="orphan.py — 절대 따라 하지 마라"
class Bad:
    def __init__(self, x): self.x = x
    def __hash__(self): return hash(self.x)
    def __eq__(self, o): return self.x == o.x
    def __repr__(self): return f"Bad({self.x})"


b = Bad(1)
s = {b}
print(b in s)        # True   — 정상

b.x = 99             # 해시가 바뀌었다
print(b in s)        # False  — 자기 자신이 자기가 든 집합에 없다
print(s)             # {Bad(99)}  — 그런데 보인다!
print(Bad(99) in s)  # False
print(Bad(1) in s)   # False
```

`s` 를 출력하면 `Bad(99)` 가 **분명히 들어 있다.** 그런데 `b in s` 는 `False` — `hash(b)` 가 이제 `hash(99)` 슬롯을 가리키는데 거기엔 아무것도 없다. `Bad(1) in s` 도 `False` — 슬롯 `hash(1)` 에 객체는 있지만 `__eq__` 에서 `1 != 99` 라 탈락한다.

**어떤 키로도 꺼낼 수 없는 원소가 집합 안에 영원히 남았다.** 순회로만 볼 수 있고 `remove` 도 안 된다.

이게 파이썬이 `list` 를 해시 불가로 만든 이유다. **막을 수 있는 건 막고, 못 막는 것(사용자 클래스)은 당신 책임이다.** `__hash__` 를 직접 구현할 거면 **불변 속성만 써라.** 자세한 건 [1.14 특수 메서드](#/dunder)에서.
:::

### 불변 ≠ 해시 가능

흔한 오해다. 튜플은 불변이지만 **항상 해시 가능한 건 아니다.**

```pyrepl
>>> {(1, [2])}
Traceback (most recent call last):
  ...
TypeError: cannot use 'tuple' as a set element (unhashable type: 'list')
```

튜플의 해시는 **원소들의 해시로 계산된다.** 원소 중 하나라도 해시 불가면 튜플도 해시 불가다. 튜플이 불변인 건 "어떤 객체를 가리키는지"이지 "그 객체의 값"이 아니다. [1.1 객체, 이름, 참조](#/objects-names)에서 본 그대로다.

### `__eq__` 를 정의하면 `__hash__` 가 사라진다

이건 반드시 물린다. 아무것도 정의하지 않은 클래스는 기본 `__hash__`(정체성 기반)를 쓰므로 `len({Q(1), Q(1)})` 이 `2` 다. **여기서 "값이 같으면 같은 걸로 치자"고 `__eq__` 를 추가하면**:

```pyrepl
>>> class P:
...     def __init__(self, x): self.x = x
...     def __eq__(self, o): return self.x == o.x
...
>>> {P(1)}
Traceback (most recent call last):
  ...
TypeError: cannot use 'P' as a set element (unhashable type: 'P')
```

**`__eq__` 를 정의한 클래스는 자동으로 `__hash__ = None` 이 된다.** 해시 불가가 된다.

::: deep 왜 파이썬이 마음대로 해시를 없애는가
"$a == b$ 이면 $hash(a) == hash(b)$" 라는 계약 때문이다.

`__eq__` 를 재정의했다는 건 **동등성의 의미를 바꿨다**는 뜻이다. 기본 `__hash__` 는 정체성(`id`) 기반이므로, 값이 같은 두 객체가 **다른 해시**를 갖게 된다. 계약 위반이고, `P(1) in {P(1)}` 이 `False` 가 되는 조용한 버그가 생긴다.

파이썬은 이걸 **시끄러운 에러로 바꾼다.** 조용히 틀리느니 지금 터지는 게 낫다는 판단이다. 고치는 법은 두 가지다.

```python
# 방법 1: __hash__ 도 같이 정의한다. __eq__ 가 쓰는 필드로.
class P:
    def __init__(self, x): self.x = x
    def __eq__(self, o): return isinstance(o, P) and self.x == o.x
    def __hash__(self): return hash(self.x)

# 방법 2: 애초에 불변으로 설계한다 — 훨씬 낫다
from dataclasses import dataclass

@dataclass(frozen=True)
class P:
    x: int          # __eq__ 와 __hash__ 를 둘 다 만들어 준다
```

`@dataclass(frozen=True)` 가 정답인 경우가 대부분이다. [2.6 dataclasses](#/dataclasses)에서 다룬다.
:::

### `1 == 1.0 == True` 함정

해시 계약의 반대 방향도 물린다. 파이썬에서 이 셋은 **같은 값**이고(`1 == 1.0 == True`), 따라서 해시도 같다. 그래서 set은 셋을 **하나로 본다.**

```pyrepl
>>> {1, 1.0, True}
{1}
>>> {True, 1, 1.0}
{True}
>>> {0, False, 0.0}
{0}
```

**먼저 들어간 것이 살아남는다.** 나중 것은 "이미 있음"으로 판정돼 버려진다. 그래서 쓴 순서에 따라 `{1}` 이 되기도 `{True}` 가 되기도 한다. dict도 똑같다.

```pyrepl
>>> d = {}
>>> d[1] = "int"
>>> d[1.0] = "float"
>>> d[True] = "bool"
>>> d
{1: 'bool'}
```

**키는 `1` 로 남고 값만 세 번 덮였다.** 키는 갱신하지 않고 값만 갱신하기 때문이다.

실전에서는 JSON을 파싱했더니 `{"count": 1}` 과 `{"count": true}` 가 섞여 있는 식으로 터진다. 둘을 set에 넣어 종류를 세면 **1개로 나온다.** 굳이 구분해야 하면 타입을 원소에 섞어라.

```pyrepl
>>> {(type(x).__name__, x) for x in (1, 1.0, True)}
{('bool', True), ('float', 1.0), ('int', 1)}
```

## frozenset — 존재 이유는 딱 하나다

`frozenset` 은 불변 set이다. `add`, `remove`, `update` 가 없다. 그게 전부다. 그리고 그 대가로 **해시 가능**해진다.

```pyrepl
>>> fs = frozenset([1, 2])
>>> {fs: "ok"}
{frozenset({1, 2}): 'ok'}
>>> {frozenset([1, 2]), frozenset([2, 1])}
{frozenset({1, 2})}
```

두 번째 예가 중요하다. 원소 순서가 달라도 **같은 frozenset**이다. 해시가 원소들의 해시를 **순서 무관하게** 조합하기 때문이다.

```pyrepl
>>> hash(frozenset([1, 2])) == hash(frozenset([2, 1]))
True
```

이것이 frozenset의 킬러 기능이다. **"순서 상관없는 원소들의 모음"을 키로 쓸 수 있다.**

```pyrepl
>>> groups = [{"a", "b"}, {"b", "a"}, {"c"}]
>>> set(map(frozenset, groups))
{frozenset({'a', 'b'}), frozenset({'c'})}
```

문자열 원소라 이 출력도 **해시 시드에 따라 바깥 set의 순서도, `frozenset({'a', 'b'})` 안의 표시 순서도 실행마다 달라진다** — 위는 그중 한 번의 스냅샷이다. 값(원소 두 개짜리 frozenset 하나와 원소 한 개짜리 frozenset 하나)은 항상 같다. `{"a","b"}` 와 `{"b","a"}` 가 하나로 합쳐졌다는 사실만 확실히 챙기면 된다. 튜플로는 안 된다 — `("a","b") != ("b","a")` 니까. 정렬한 튜플로 흉내낼 수는 있지만 그러려면 원소가 **정렬 가능**해야 한다. frozenset은 해시만 되면 된다.

::: perf frozenset의 해시는 한 번만 계산된다
`frozenset` 이 불변이라는 사실을 CPython이 활용한다. **해시를 계산한 뒤 객체에 캐싱한다.**

```python title="백만 원소 frozenset"
import time

fs = frozenset(range(1_000_000))

t0 = time.perf_counter(); hash(fs); t1 = time.perf_counter()   # 첫 번째
hash(fs)
t2 = time.perf_counter(); hash(fs); t3 = time.perf_counter()   # 두 번째
print((t1 - t0) * 1e6, (t3 - t2) * 1e6)
# 첫 번째 hash(): 약 1000 μs   ← 테이블 전체를 훑는다 O(n)
# 두 번째 hash(): 약 0.2~0.3 μs ← 캐시된 값 반환 O(1)
```

(Python 3.14.5 / Windows 기준 실측, 3회 반복. 절대값은 흔들리지만 매번 **수천 배** 차이가 난다.) 그래서 frozenset을 dict 키로 반복 사용하는 것은 처음 한 번만 비싸고 그 뒤로는 사실상 공짜다.

`set` 은 이걸 못 한다. 언제든 원소가 바뀔 수 있으니 캐시가 무효화될 수 있고, 애초에 해시 자체가 금지다.

같은 이유로 복사도 공짜다.

```pyrepl
>>> fs = frozenset([1, 2])
>>> fs.copy() is fs
True
>>> frozenset(fs) is fs
True
>>> {1, 2}.copy() is {1, 2}
False
```

**불변이니 복사할 이유가 없다.** 자기 자신을 반환한다. `tuple` 과 같은 전략이다.

단, 빈 튜플과 달리 **빈 frozenset은 캐시되지 않는다.** `frozenset() is frozenset()` 은 `False` 다. [1.1](#/objects-names)의 교훈대로 `is` 로 비교하지 마라.
:::

### frozenset이 진짜 필요해지는 자리: 메모이제이션

`lru_cache` 는 인자를 **dict 키로 쓴다.** 그래서 set을 인자로 받는 함수는 캐시가 안 된다. frozenset이면 된다.

```python title="집합 상태 DP"
from functools import lru_cache


@lru_cache(maxsize=None)
def solve(remaining: frozenset) -> int:
    if not remaining:
        return 0
    return 1 + min(solve(remaining - {x}) for x in remaining)


solve(frozenset([1, 2, 3]))     # 3
solve.cache_info()              # CacheInfo(hits=5, misses=8, maxsize=None, currsize=8)
```

`remaining - {x}` 의 결과 타입에 주목하라. 왼쪽이 frozenset이므로 **결과도 frozenset**이다. 재귀가 그대로 돈다. 왼쪽에 set을 뒀으면 두 번째 호출에서 `TypeError` 다.

`hits=5` 가 캐시가 실제로 먹었다는 증거다. 같은 부분집합에 서로 다른 경로로 도달했고, 두 번째부터는 계산을 건너뛰었다.

다만 코딩테스트에서 이 패턴을 그대로 쓰지는 마라. **집합 상태 DP는 비트마스크가 거의 항상 빠르다.** frozenset 하나가 216바이트인데 `int` 비트마스크는 28바이트고, `remaining - {x}` 대신 `mask & ~(1 << x)` 하나면 된다. frozenset이 필요한 건 **원소가 정수로 매핑되지 않을 때**다 — 문자열·좌표·객체 집합. [7.24 비트마스크](#/bitmask)에서 다룬다.

## 순서 없음의 함정

이 절의 마지막이자 가장 실전적인 부분이다. **set의 순서에 절대 의존하지 마라.** 문제는 순서가 *무작위처럼 보이지 않는다*는 것이다.

```pyrepl
>>> {1, 2, 3, 4, 5, 6, 7}
{1, 2, 3, 4, 5, 6, 7}
```

정렬돼 보인다. 하지만 이건 **작은 정수의 해시가 자기 자신이고, 슬롯이 우연히 순서대로 잡혔을 뿐**이다. 조금만 건드리면 무너진다.

```pyrepl
>>> {8, 16, 24, 32}
{8, 16, 32, 24}
>>> set('python')      # 실행할 때마다 순서가 다르다 — 아래 참고
{'y', 'p', 'o', 't', 'h', 'n'}
>>> list({-1, -2, -3})
[-3, -1, -2]
```

`{8, 16, 24, 32}` 는 전부 `& 7 == 0` 이라 슬롯 0에 몰렸고, 선형 프로빙 순서가 그대로 드러난 것이다. **"정수 set은 정렬돼 나온다"는 미신을 만들기에 딱 좋은 그림이다.**

`set('python')` 은 한술 더 뜬다. **정수와 달리 문자열의 해시는 프로세스마다 무작위 시드가 걸린다**(앞서 본 해시 랜덤화 이야기 그대로다). 그래서 이 한 줄은 인터프리터를 새로 띄울 때마다 다른 순서를 낸다 — 실제로 3번 다시 실행하면 `{'y', 'p', 'o', 't', 'h', 'n'}`, `{'y', 'h', 'o', 'p', 'n', 't'}`, `{'p', 'n', 'h', 'y', 'o', 't'}` 식으로 매번 바뀐다. 위에 적은 결과는 그중 한 번의 스냅샷일 뿐, **이 코드를 그대로 쳐서 같은 출력이 나오리라고 기대하면 안 된다.** 바로 다음 문단이 이 현상을 자세히 다룬다.

문자열은 더하다. **실행할 때마다 다르다.**

```bash
$ python -c "print({'apple', 'banana', 'cherry'})"
{'cherry', 'banana', 'apple'}
$ python -c "print({'apple', 'banana', 'cherry'})"
{'cherry', 'banana', 'apple'}
$ python -c "print({'apple', 'banana', 'cherry'})"
{'banana', 'cherry', 'apple'}
```

::: danger 두 번은 맞고 세 번째에 틀리는 코드
```python
# ❌ 문자열 set을 그대로 출력한다
print(' '.join(set(words)))
```

로컬에서 테스트하면 통과한다. 다시 해도 통과한다. **제출하면 틀린다.** 해시 시드가 다른 프로세스에서는 순서가 달라지기 때문이다.

이건 코딩테스트뿐 아니라 실무에서도 터진다. set 순서에 의존한 출력을 스냅샷 테스트에 넣으면, **CI에서 무작위로 깨지는 테스트**가 된다. 원인을 찾는 데 며칠이 걸린다.

**출력에 순서가 필요하면 `sorted()` 를 붙여라. 예외 없이.**

```python
# ✅
print(' '.join(sorted(set(words))))
```
:::

### 순서를 흔드는 것은 해시 시드만이 아니다

`list.pop()` 은 마지막 원소지만 **`set.pop()` 은 명세상 "임의의 원소"** 다. `{10, 20, 30}.pop()` 이 `10` 을 준다고 해서 최소값을 꺼내는 데 쓰면 안 된다. 그건 [7.8 힙](#/heap)의 일이다.

**삭제 후 재삽입도 순서를 바꾼다.** 삭제가 남긴 더미(dummy) 슬롯이 재삽입 경로를 틀어 놓기 때문이다. `set(range(20))` 에서 0~9를 지웠다 다시 넣으면 앞부분이 `[0,1,2,...]` 에서 `[4,3,2,1,0,10,...]` 으로 뒤집힌다. **같은 원소, 같은 집합, 다른 순서다.**

### 순회 중 수정은 즉시 터진다

```pyrepl
>>> s = {1, 2, 3}
>>> for x in s:
...     s.add(x + 10)
...
Traceback (most recent call last):
  ...
RuntimeError: Set changed size during iteration
```

이건 오히려 다행이다. **크기가 변하면 잡힌다.** 리사이즈가 일어나면 이터레이터가 보던 테이블 자체가 사라지므로, 검사하지 않으면 세그폴트다. 수정해야 하면 사본을 순회해라.

```python
for x in set(s):     # ✅ 사본을 순회
    s.add(x + 10)
```

::: deep 리터럴은 컴파일 타임에 frozenset이 된다 — 그리고 순서를 오염시킨다
이건 [1.1](#/objects-names)의 상수 폴딩이 set에서 다시 나타나는 자리다. 그리고 훨씬 더 교묘하다.

```python title="같은 파일 안의 두 리터럴"
a = {1, 9, 17}
b = {17, 9, 1}
print(list(a), list(b))     # [1, 9, 17] [1, 9, 17]  — 같다?!
```

앞에서 `.add()` 로 만들었을 때는 `[1, 9, 17]` 과 `[17, 9, 1]` 로 **달랐다.** 리터럴로 쓰니 같아졌다. 바이트코드를 보면 이유가 나온다.

```pyrepl
>>> code = compile("a = {1, 9, 17}\nb = {17, 9, 1}", "<m>", "exec")
>>> code.co_consts
(1, None, frozenset({1, 9, 17}))
```

**frozenset 상수가 하나뿐이다.** 컴파일러는 (1) 원소가 전부 상수인 set 리터럴을 `frozenset` 상수로 접고, (2) `co_consts` 안의 **같은 값 상수를 하나로 합친다.** 둘이 병합됐으므로 `a` 와 `b` 는 **같은 frozenset 상수를 펼쳐서 만들어진다** — 순서가 같을 수밖에 없다. 파일을 나누면 다시 갈라진다.

```bash
$ python -c "print(list({17, 9, 1}))"
[17, 9, 1]
$ python -c "print(list({1, 9, 17}))"
[1, 9, 17]
```

**같은 리터럴이 같은 파일에 있느냐 없느냐로 순회 순서가 바뀐다.** 함수를 다른 모듈로 옮기는 것만으로 순서가 달라질 수 있다는 뜻이다.
:::

::: cote `x in {...}` 은 set을 만들지 않는다
방금 본 상수 폴딩에는 좋은 면도 있다.

```pyrepl
>>> import dis
>>> def g(x): return x in {1, 2, 3}
>>> dis.dis(g)
  RESUME                   0
  LOAD_FAST_BORROW         0 (x)
  LOAD_CONST               1 (frozenset({1, 2, 3}))
  CONTAINS_OP              0 (in)
  RETURN_VALUE
```

`BUILD_SET` 이 **없다.** 컴파일 시점에 만들어진 frozenset 상수를 그냥 올린다. **런타임 비용이 0이다.** 리스트로 쓰면 튜플 상수(`(1, 2, 3)`)가 되어 선형 탐색이 된다.

```python
if ch in {'(', '[', '{', '<'}:      # ✅ 상수 frozenset — 할당 없음
if ch in ['(', '[', '{', '<']:      # ❌ 튜플 상수 — 선형 탐색
```

원소가 서너 개면 차이가 미미하지만 열 개를 넘어가면 벌어진다. 공짜니까 습관을 들여라.

**단, 원소가 상수일 때만이다.** `x in {a, b, c}` 처럼 변수가 섞이면 매번 `BUILD_SET` 이 돌아 실제로 set을 만든다. 그런 코드가 루프 안에 있으면 루프 밖으로 빼라.
:::

## set comprehension

문법은 리스트 컴프리헨션과 같고 괄호만 다르다.

```pyrepl
>>> {x * x for x in range(-3, 4)}
{0, 9, 4, 1}
>>> {len(w) for w in ["hi", "yo", "python"]}
{2, 6}
```

정수는 해시 랜덤화 대상이 아니므로(`hash(n) == n`) 이 출력은 **재실행해도 항상 `{0, 9, 4, 1}`** 로 결정적이다 — 다만 값이 커진 순서(`0, 1, 4, 9`)와는 다르다. 순서는 슬롯 배치(선형 프로빙)가 정할 뿐 크기순이 아니라는 걸 다시 확인해 두자. **중복 제거가 공짜로 따라온다.** `{x*x for x in range(-3,4)}` 에서 $(-3)^2$ 과 $3^2$ 이 하나로 합쳐진 것에 주목하라. 이게 리스트 컴프리헨션에 `set()` 을 씌운 것과 다른 점이다 — 중간 리스트를 만들지 않는다.

```python
# ❌ 리스트 100만 개를 만들었다가 버린다
unique = set([expensive(x) for x in data])

# ✅ 처음부터 set에 넣는다
unique = {expensive(x) for x in data}
```

그리고 **빈 set 리터럴은 없다.** `{}` 는 빈 dict다 — dict가 먼저 있었고 set은 2.4에 뒤늦게 들어와서 `{}` 를 못 가져갔다. 빈 set은 `set()` 뿐이다. 컴프리헨션에서는 콜론 유무로 갈린다: `{x for x in "ab"}` 는 set, `{x: 0 for x in "ab"}` 는 dict.

### 중복 제거의 세 가지 방법 — 무엇을 언제

```python title="200,000개 / 고유값 약 20,000개"
list(set(data))                 # 0.00276초 — 순서 잃음
list(dict.fromkeys(data))       # 0.00333초 — 순서 보존, 약 1.2배
dedup_set(data)                 # 0.00458초 — 순서 보존, seen=set() 수동 루프, 약 1.7배
```

(Python 3.14.5 / Windows 기준 실측, `timeit` 20회 평균.) **순서가 필요 없으면 `set()`. 필요하면 `dict.fromkeys()`.** 후자가 약 20% 느리지만 순서를 보존하고 **한 줄이다.** 손수 루프는 그보다 훨씬 더 느리다 — 쓸 이유가 없다.

::: cote 방문 체크: set of tuple vs 2차원 배열
격자 문제에서 `visited` 를 어떻게 잡을지는 매번 나오는 선택이다.

```python
visited = set()                              # (r, c) 튜플을 넣는다
visited = [[False] * N for _ in range(N)]    # 2차원 리스트
```

1000×1000 격자, 20만 번 접근으로 재면 **속도는 set이 2배 남짓 느리다**(튜플 해싱 비용 때문이다). 하지만 진짜로 갈리는 건 메모리다. 전부 방문한 경우 set은 **테이블 32MB + 튜플 100만 개 × 64B = 약 93MB**, 2차원 리스트는 **약 8MB**. **12배 가까이 차이 난다.**

- **격자 크기를 알고 대부분을 방문할 것 같으면** → 2차원 리스트. 메모리도 적고 인덱싱이 빠르다.
- **좌표 범위가 넓거나 음수이거나, 방문 칸이 희소하면** → set. $10^9 \times 10^9$ 격자를 리스트로 잡을 수는 없다.
- **좌표가 아니라 상태(문자열·튜플·조합)면** → set 말고 선택지가 없다.

set 하나로 다 하려다 메모리 초과가 나는 게 흔한 실패다. **격자면 배열을 먼저 생각해라.**
:::

## 요약

- **set은 값 없는 dict가 아니다.** `setobject.c` 의 별도 구현이고, compact 구조가 아니며, **삽입 순서를 전혀 보존하지 않는다.** 그 대가로 **선형 프로빙**(캐시 친화적)과 **낮은 적재율 3/5**(dict는 2/3)를 얻어 조회에 최적화됐다.
- **`in` 은 약 20~25ns 고정.** 100개든 100만 개든 같다. 리스트 대비 백만 개에서 **157,278배**. 코딩테스트에서 리스트 `in` 은 TLE의 1순위 원인이다.
- 단 **$O(1)$ 은 해시가 고르게 흩어질 때만.** 해시가 뭉치면 조회가 556배 느려진다.
- **연산자는 set끼리만, 메서드는 아무 이터러블이나.** 의도된 설계다. `big & set(lst)` 대신 `big.intersection(lst)`.
- 교집합은 CPython이 **작은 쪽을 순회**한다. "겹치나?"만 궁금하면 **`isdisjoint`** — 조기 종료로 3,000배 이상 빠르다.
- **`__eq__` 를 정의하면 `__hash__` 가 사라진다.** 해시가 변하면 원소가 미아가 된다. `@dataclass(frozen=True)` 가 대체로 정답이다.
- **frozenset의 존재 이유는 해시 가능성 하나.** 순서 무관한 모음을 dict 키/set 원소/`lru_cache` 인자로 쓸 수 있다. 해시는 캐싱된다(약 1000μs → 약 0.2~0.3μs).
- **순서에 의존하지 마라.** 출력에는 예외 없이 `sorted()`.

::: quiz 연습문제
1. 다음 각각의 출력을 **먼저 예측한 뒤** 실행하라. 틀린 것이 있으면 이유를 설명하라.

   ```python
   print({1, True, 1.0, 0, False, 0.0})
   print(len({(1, 2), (1, 2)}))
   print({1, 2} | {2, 3} ^ {3, 4})
   print(type(frozenset([1]) | {2}), type({2} | frozenset([1])))
   ```

2. 아래 코드는 로컬에서 항상 통과한다. 채점 서버에서는 가끔 틀린다. 왜인가?

   ```python
   words = input().split()
   print(*set(words))
   ```

3. `sys.getsizeof(set(range(n)))` 이 `n = 307` 에서 8408 → 32984로 뛴다. 이 두 숫자와 307이라는 임계점을 **적재율 3/5, 성장 배수 4, 엔트리 16바이트, 헤더 216바이트**만 써서 유도하라. (힌트: 216은 8칸짜리 smalltable을 포함한다.)

4. **깊이 생각해 볼 문제.** 다음에서 `a` 와 `b` 는 같은 파일에 있을 때와 다른 파일에 있을 때 결과가 다르다. 각각 무엇이며 왜인가? 그리고 이 사실이 "set 순서에 의존하지 마라"는 규칙을 왜 강화하는가?

   ```python
   a = {1, 9, 17}
   b = {17, 9, 1}
   print(list(a) == list(b))
   ```

5. **설계 문제.** 좌표 `(r, c)` 를 원소로 갖는 set에 `Point` 클래스를 쓰고 싶다. 아래 코드의 문제 두 가지를 찾고, 두 가지 방법으로 각각 고쳐라.

   ```python
   class Point:
       def __init__(self, r, c):
           self.r, self.c = r, c
       def __eq__(self, o):
           return (self.r, self.c) == (o.r, o.c)

   visited = {Point(0, 0)}
   print(Point(0, 0) in visited)
   ```
:::

**다음 절**: [1.8 제어 흐름과 match 문](#/control-flow) — `for`/`while` 의 `else` 절은 왜 존재하고, 구조적 패턴 매칭은 `if` 사슬과 무엇이 다른가.
