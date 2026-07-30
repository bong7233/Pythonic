# 11.2 표준 라이브러리 무기고

::: lead
`Counter` 가 무엇인지 아는 것과, 문제를 읽는 순간 손이 `from collections import Counter` 를 치는 것은 다른 능력이다. 이 절은 도구 목록이 아니다. **문제 문장의 어떤 표현이 어떤 도구를 부르는가**, 그리고 **그 도구를 언제 집지 말아야 하는가**를 훈련한다. 각 도구의 내부 동작과 복잡도는 이미 [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost), [3.1 functools](#/functools), [3.2 itertools](#/itertools)에서 다뤘다. 여기서는 오직 하나만 다룬다 — **빈 화면 앞에서 무엇을 집는가.**
:::

## 30초 자가 진단

아래 여섯 문장을 읽고 **각각 5초 안에** 쓸 도구를 말해라. 코드는 짜지 마라. 이름만 대면 된다.

1. 접속 로그에서 가장 많이 등장한 IP 3개를 구하라.
2. 대기열의 앞과 뒤 양쪽에서 사람이 들어오고 나간다.
3. 정렬된 점수 배열에서 "커트라인 이하가 몇 명인가" 질의가 10만 번 들어온다.
4. 작업마다 우선순위가 있고, 매번 가장 급한 것 하나를 처리한다.
5. 부품 5개 중 3개를 고르는 모든 방법을 시도한다.
6. 두 부서 명단에서 양쪽에 다 있는 사람을 찾아라.

답은 순서대로 `Counter.most_common`, `deque`, `bisect`, `heapq`, `itertools.combinations`, `set` 교집합이다.

하나라도 **"음… 뭐였더라"** 가 나왔다면 지식이 없어서가 아니다. 당신은 힙이 뭔지 안다. **문장과 도구를 잇는 회로가 없을 뿐**이다([11.1](#/fluency-gap)). 그래서 이 절은 도구를 설명하지 않는다. **회로를 깐다.**

## 도구를 고르는 세 개의 질문

무기를 외우기 전에 순서를 잡아라. 문제를 읽고 던지는 질문은 셋뿐이다.

```text nolines
  Q1. 같은 것을 몇 번이고 다시 찾아야 하는가?
      yes  ->  set / dict            해시 조회, 존재 여부와 개수
      no   ->  Q2

  Q2. 꺼내는 순서가 정해져 있는가?
      front / back  ->  deque        양 끝에서만 넣고 뺀다
      min / max     ->  heapq        매번 극값 하나
      none          ->  Q3

  Q3. 데이터가 이미 정렬돼 있고 "위치"를 묻는가?
      yes  ->  bisect                구간, 등급, 개수
      no   ->  itertools / 그냥 루프
```

이 셋에 다 걸리지 않으면 **표준 라이브러리를 뒤질 문제가 아니다.** 그냥 `for` 를 돌려라. 도구를 못 찾아서 못 푸는 문제보다, 안 써도 되는 도구를 찾느라 시간을 버리는 경우가 훨씬 많다.

## 신호 → 도구 매핑표

문제 지문에 나오는 표현과 그것이 부르는 도구다. **왼쪽 칸을 보고 오른쪽이 즉시 떠올라야 한다.**

| 지문에 나오는 말 | 집을 도구 | 왜 |
| --- | --- | --- |
| "몇 번 나오는가", "빈도", "가장 많은" | `Counter` | 세기 + 상위 K가 한 줄 |
| "~별로 묶어라", "그룹", "분류" | `defaultdict(list)` | 키 존재 확인이 사라진다 |
| "중복", "유일한", "이미 본 적 있는" | `set` | $O(1)$ 존재 확인 |
| "공통", "한쪽에만", "둘 다" | `set` 연산 | `&` `-` `^` 한 글자로 끝 |
| "앞뒤 양쪽", "회전", "최근 K개" | `deque` | 양 끝 $O(1)$, `maxlen` |
| "가장 작은 것을 계속", "상위 K개" | `heapq` | 전체 정렬 없이 극값만 |
| "정렬된 상태에서", "몇 개 이하", "등급/구간" | `bisect` | $O(\log n)$ 위치 계산 |
| "모든 조합/순서/짝", "연속으로 같은 값" | `itertools` | 이중 루프를 지운다 |
| "같은 입력이 반복된다", "재귀가 겹친다" | `functools.cache` | 한 줄 메모이제이션 |
| "누적", "구간 합" | `itertools.accumulate` | 전처리 한 줄 |

::: cote 시험장에서 이 표가 실제로 하는 일
빈 화면 앞에서 5분을 날리는 이유는 대개 "무슨 알고리즘이지?"라는 큰 질문에 갇혀서다. 그 질문을 **"이 문장이 어떤 도구를 부르는가"** 로 바꿔라. 도구를 집으면 자료구조가 정해지고, 자료구조가 정해지면 루프의 모양이 정해진다. 유형 판별 자체는 [8.4](#/problem-signals)에서 더 크게 다룬다.
:::

## 무기별 실전 카드

각 도구를 **신호 / 세 줄 / 안 집는 경우** 로 정리한다. 세 번째 칸이 가장 중요하다. 도구를 아는 사람은 많지만 **언제 안 쓰는지 아는 사람이 실력자**다.

### Counter — "몇 번"

신호: 빈도, 최빈값, 개수 비교, 애너그램, 재고 대조.

```pyrepl
>>> from collections import Counter
>>> votes = ["A", "B", "A", "C", "B", "A"]
>>> Counter(votes).most_common(1)[0]
('A', 3)
>>> Counter("aabbc") == Counter("bacab")
True
>>> [x for x, n in Counter(votes).items() if n == 1]
['C']
```

두 번째 줄이 핵심이다. **애너그램 판정을 `sorted(a) == sorted(b)` 로 쓰는 습관을 버려라.** `Counter` 비교는 정렬 없이 끝난다. 세 번째 줄은 "딱 한 번만 나온 것"으로, 실전 문제에서 놀랄 만큼 자주 나온다.

`Counter` 는 뺄셈을 안다. 이게 재고·차집합 문제에서 코드를 절반으로 줄인다.

```pyrepl
>>> from collections import Counter
>>> need = Counter("aabbc")
>>> have = Counter("abbz")
>>> need - have
Counter({'a': 1, 'c': 1})
>>> sorted((need - have).elements())
['a', 'c']
```

::: danger Counter 뺄셈은 0과 음수를 조용히 지운다
```pyrepl
>>> from collections import Counter
>>> Counter(a=5) - Counter(a=5)
Counter()
>>> Counter(a=5) - Counter(a=7)
Counter()
```

`-` 는 **다중집합 뺄셈**이라 0 이하가 된 키를 결과에서 **삭제한다.** "재고가 정확히 0인 품목"을 세야 하는 문제에서 그 품목이 통째로 사라진다. 음수 결과가 필요하면 `subtract()` 를 쓰거나 직접 계산해라.

```pyrepl
>>> from collections import Counter
>>> c = Counter(a=5)
>>> c.subtract(Counter(a=7))
>>> c
Counter({'a': -2})
```
:::

**안 집는 경우 —** 키가 두세 개로 고정돼 있고 한 번만 세면 그냥 변수를 써라. 그리고 `Counter` 는 `dict` 의 하위 클래스인데 **없는 키를 물어보면 예외 대신 0을 반환한다.**

```pyrepl
>>> from collections import Counter
>>> stock = Counter({"apple": 3})
>>> stock["aplpe"]
0
>>> stock["aplpe"] > 0
False
```

오타가 `KeyError` 로 터지지 않고 **조용히 "0개"로 통과한다.** 값을 읽기만 하는 코드에서 이건 디버깅하기 가장 힘든 종류의 버그다.

속도 걱정은 접어도 된다. 서로 다른 값이 열 개뿐인 문자열 20만 개를 세는 데 `Counter(words)` 가 10.7~11.0 ms, `d[w] = d.get(w, 0) + 1` 수동 루프가 14.7~15.2 ms 였다(Python 3.14.0rc2 / Linux 기준 실측. **자릿수가 갈리는 차이는 아니다** — 절대값과 배수는 데이터의 중복도와 기기에 따라 달라진다. 거의 전부 서로 다른 값 20만 개로 바꾸면 둘 다 2~4배 느려지고 둘의 차이는 사실상 사라진다). 다만 **`Counter` 를 쓰는 진짜 이유는 속도가 아니라 코드가 짧아지는 것**이다.

### defaultdict — "~별로 묶어라"

신호: 그룹핑, 버킷, 인접 리스트, 역인덱스.

```pyrepl
>>> from collections import defaultdict
>>> rows = [("A", 1), ("B", 2), ("A", 3)]
>>> g = defaultdict(list)
>>> for k, v in rows:
...     g[k].append(v)
...
>>> dict(g)
{'A': [1, 3], 'B': [2]}
```

`if k not in g: g[k] = []` 한 줄이 사라진다. 그게 전부다. 하지만 그 한 줄이 사라지면 **루프 본문이 한 문장이 되고, 한 문장이면 읽다가 틀리지 않는다.**

::: warn 조회만 해도 키가 생긴다
```pyrepl
>>> from collections import defaultdict
>>> g = defaultdict(list)
>>> g["A"].append("kim")
>>> "C" in g
False
>>> g["C"]
[]
>>> "C" in g
True
```

`g["C"]` 를 **읽기만 했는데 키가 만들어졌다.** 순회 중에 없는 키를 조회하면 `RuntimeError: dictionary changed size during iteration` 이 터지고, 결과를 그대로 반환하면 빈 그룹이 섞여 나간다. **반환 직전에 `dict(g)` 로 바꿔라.** 그러면 이후 조회는 정상적으로 `KeyError` 를 낸다([7.2](#/py-ds-cost)).
:::

**안 집는 경우 —** 빈도만 셀 거면 `defaultdict(int)` 대신 `Counter` 다. 기본값이 필요한 곳이 한두 군데뿐이면 `dict.setdefault` 나 `dict.get(k, 기본값)` 이 의도를 더 정확히 드러낸다. 그룹핑 패턴 자체는 [11.5](#/dict-set-patterns)에서 본격적으로 다룬다.

### deque — "양 끝", "회전", "최근 K개"

신호: 큐, BFS, 슬라이딩 윈도우, 회전, 최근 이력.

```pyrepl
>>> from collections import deque
>>> q = deque([1, 2, 3])
>>> q.appendleft(0); q.pop()
3
>>> q
deque([0, 1, 2])
>>> d = deque([1, 2, 3, 4, 5])
>>> d.rotate(2)
>>> d
deque([4, 5, 1, 2, 3])
```

`maxlen` 은 코딩테스트에서 과소평가된 기능이다. **"최근 K개"** 라는 말이 나오면 조건 검사 없이 이것으로 끝난다.

```pyrepl
>>> from collections import deque
>>> window = deque(maxlen=3)
>>> for x in [1, 2, 3, 4, 5]:
...     window.append(x)
...
>>> window
deque([3, 4, 5], maxlen=3)
```

가득 찬 상태에서 `append` 하면 **반대쪽이 알아서 밀려 나간다.** 길이 검사도 `pop` 도 필요 없다.

::: perf deque 의 중간 인덱싱은 비싸다
`deque` 는 블록 연결 리스트다. 양 끝은 $O(1)$ 이지만 **가운데 접근은 $O(n)$** 이다. 원소 10만 개에서 정확히 중앙을 20만 번 읽었을 때:

| 자료구조 | 20만 회 |
| --- | --- |
| `list[m]` | 2.2 ~ 2.5 ms |
| `deque[m]` | 534 ~ 568 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**두 자릿수 이상 차이다.** 인덱스로 훑는 코드에 `deque` 를 쓰면 $O(n)$ 짜리 루프가 조용히 $O(n^2)$ 이 된다.
:::

**안 집는 경우 —** 양 끝에서 **실제로 넣고 빼지 않으면** 쓰지 마라. 투 포인터([7.3](#/two-pointers))처럼 인덱스 두 개만 움직이면 `list` 가 정답이다. 슬라이싱도 정렬도 안 된다. BFS에서의 용례는 [7.14](#/bfs-dfs)에 있다.

### heapq — "매번 가장 작은 것 하나"

신호: 우선순위, 스케줄링, 상위 K개, 다익스트라.

```pyrepl
>>> import heapq
>>> tasks = [(3, "compile"), (1, "lint"), (2, "test")]
>>> heapq.heapify(tasks)
>>> heapq.heappop(tasks)
(1, 'lint')
>>> heapq.nlargest(2, [("kim", 88), ("lee", 95)], key=lambda r: r[1])
[('lee', 95), ('kim', 88)]
```

파이썬 힙은 **최소 힙뿐이다.** 최대 힙이 필요하면 부호를 뒤집는다. 이건 요령이 아니라 관용구니까 외워라.

```pyrepl
>>> import heapq
>>> h = []
>>> heapq.heappush(h, (-5, "a"))
>>> heapq.heappush(h, (-9, "b"))
>>> heapq.heappop(h)
(-9, 'b')
```

::: perf 상위 K개 — K가 작을 때만 힙이 이긴다
난수 20만 개에서 상위 K개를 뽑는 데 걸린 시간(1회 호출):

| K | `heapq.nlargest(K, data)` | `sorted(data, reverse=True)[:K]` |
| --- | --- | --- |
| 10 | 2.25 ~ 2.67 ms | 34.8 ~ 36.6 ms |
| 1,000 | 4.75 ~ 5.03 ms | 34.6 ~ 37.0 ms |
| 50,000 | 111 ~ 116 ms | 35.8 ~ 37.4 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**K가 수십 규모면 힙이 10배 이상, K가 1,000 규모면 7배쯤 빠르다. 그러나 K가 n의 4분의 1에 이르면 오히려 힙이 몇 배 느려진다.** `nlargest` 는 $O(n \log K)$ 라 $K$ 가 $n$ 에 가까워지면 정렬보다 손해다. **"상위 몇 개"의 몇이 상수면 힙, 비율이면 정렬**로 기억해라.
:::

::: danger 힙 원소를 직접 고치면 조용히 틀린다
`heapq` 는 우선순위 갱신(decrease-key) API가 없다. 리스트를 직접 만졌다가는 힙 불변식이 깨진다.

```pyrepl
>>> import heapq
>>> h = [(5, "a"), (7, "b")]
>>> heapq.heapify(h)
>>> h[1] = (1, "b")
>>> heapq.heappop(h)
(5, 'a')
```

**최솟값이 `(1, 'b')` 인데 `(5, 'a')` 가 나왔다.** 예외도 경고도 없다. 갱신이 필요하면 **새 항목을 그냥 `heappush` 하고, 꺼낼 때 낡은 것을 버려라**(lazy deletion). 다익스트라 구현이 그렇게 생긴 이유가 이것이다([7.8](#/heap)).
:::

**안 집는 경우 —** 최솟값이 **한 번만** 필요하면 `min()` 이다. 전체 순서가 필요하면 `sorted()` 다. 힙은 **"꺼내면서 계속 넣는다"** 는 조건이 있을 때만 이긴다. 그 조건이 없으면 코드만 복잡해진다.

### bisect — "정렬돼 있다"는 말이 나오면

신호: 정렬된 배열, 구간·등급표, "몇 개 이하", 삽입 위치 유지.

```pyrepl
>>> import bisect
>>> scores = [10, 20, 20, 30, 40]
>>> bisect.bisect_left(scores, 20)
1
>>> bisect.bisect_right(scores, 20)
3
>>> bisect.bisect_right(scores, 25)
3
```

`bisect_right(a, x)` 는 곧 **"x 이하인 원소의 개수"** 다. 이 한 문장이 `bisect` 활용의 절반이다.

나머지 절반은 **구간표 조회**다. 요금표·등급표는 전부 이 모양이다.

```pyrepl
>>> import bisect
>>> cuts = [0, 30, 60, 120]
>>> prices = [1000, 2000, 3500, 6000]
>>> prices[bisect.bisect_right(cuts, 45) - 1]
2000
>>> prices[bisect.bisect_right(cuts, 120) - 1]
6000
>>> prices[bisect.bisect_right(cuts, 0) - 1]
1000
```

`cuts` 는 각 구간의 **시작값**이고 `-1` 은 "내가 속한 구간"으로 되돌아가는 보정이다. `cuts[0]` 이 가능한 최솟값이어야 인덱스가 `-1` 로 굴러 떨어지지 않는다. `if/elif` 사다리를 이 두 줄로 바꾸는 것이 요점이다.

`insort` 는 **정렬 상태를 유지하면서 삽입**한다. 매번 `append` 후 `sort` 하는 코드를 이걸로 바꿔라.

::: perf 정렬해 두고 이분 탐색 — 격차가 자릿수로 벌어진다
정렬된 20만 개 배열에 "x 이하가 몇 개?"를 2,000번 물었을 때. 그리고 **빈 리스트에** 2만 개를 하나씩 넣으며 정렬 상태를 유지할 때:

| 방법 | 시간 |
| --- | --- |
| `bisect.bisect_right` × 2,000 | 0.88 ~ 1.2 ms |
| `sum(1 for v in data if v <= x)` × 2,000 | 15.6 ~ 18.1 s |
| `bisect.insort` × 20,000 | 22.3 ~ 23.8 ms |
| `a.append(x); a.sort()` × 20,000 | 801 ~ 825 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

"질의가 여러 번 들어온다"는 문장을 보면 정렬 비용을 한 번 치르고 `bisect` 로 가는 것이 거의 항상 이긴다([8.3 시간 초과를 피하는 관용구](#/tle)). `insort` 도 삽입 자체는 원소 이동 때문에 $O(n)$ 인데 30배 이상 빠른 이유는, 그 이동이 파이썬 바이트코드 없이 도는 **C 레벨 포인터 복사 루프**여서 원소당 상수가 극단적으로 작기 때문이다. `insort` 가 부르는 `PyList_Insert` 의 실제 이동부(`Objects/listobject.c` 의 `ins1`)는 `for (i = n; --i >= where; ) items[i+1] = items[i];` 한 줄이다 — 포인터만 밀고 객체는 건드리지 않는다. 반면 `sort()` 는 **호출마다** 런 탐색과 병합에서 객체 비교를 다시 수행한다. 파이썬에서는 복잡도만큼이나 **상수가 어디서 도는가**가 중요하다([7.1 복잡도](#/complexity)).
:::

::: danger 정렬 안 된 리스트에 bisect 를 쓰면 예외 없이 틀린 답이 나온다
```pyrepl
>>> import bisect
>>> data = [5, 1, 9, 3]
>>> bisect.bisect_left(data, 4)
2
```

`4` 는 이 리스트 어디에도 들어갈 자리가 없는데 `2` 를 반환했다. `bisect` 는 **정렬돼 있다고 가정하고 계산만 한다.** 검사하지 않는다.

시험장에서 위험한 이유는 이것이다. 예제 입력은 우연히 정렬돼 있어서 통과하고 **채점 데이터에서만 틀린다.** `bisect` 를 쓰기 전에 그 리스트가 정렬 상태로 유지되는지 눈으로 확인해라([7.5](#/binary-search)).
:::

**안 집는 경우 —** **존재 여부만** 물으면 `set` 이다. `bisect` 는 $O(\log n)$, `set` 은 $O(1)$ 이다. `bisect` 가 이기는 건 **순서가 의미를 갖는 질문**(몇 개 이하, 어느 구간, 다음으로 큰 값)뿐이다.

### itertools — 이중 루프를 지우는 자리

신호: 모든 조합/순열/곱, 연속된 같은 값, 누적, 이웃한 쌍.

```pyrepl
>>> from itertools import accumulate, combinations, groupby, pairwise
>>> list(accumulate([3, 1, 4, 1, 5]))
[3, 4, 8, 9, 14]
>>> max(b - a for a, b in pairwise([3, 1, 4, 1, 9]))
8
>>> ["".join(p) for p in combinations("ABCD", 3)]
['ABC', 'ABD', 'ACD', 'BCD']
>>> "".join(f"{c}{len(list(g))}" for c, g in groupby("aaabccd"))
'a3b1c2d1'
```

네 줄에 실전 패턴 네 개가 들어 있다. 누적합, 이웃 비교, 조합 전탐색, 런랭스 압축. 특히 마지막 줄은 **문자열 압축 유형의 표준 답안**이라 손에 붙여 둘 값어치가 있다([11.3](#/string-toolkit)).

::: warn groupby 는 "정렬"이 아니라 "연속"을 본다
```pyrepl
>>> from itertools import groupby
>>> log = [("A", 1), ("B", 2), ("A", 3)]
>>> [(k, [v for _, v in g]) for k, g in groupby(log, key=lambda r: r[0])]
[('A', [1]), ('B', [2]), ('A', [3])]
>>> [(k, [v for _, v in g]) for k, g in groupby(sorted(log), key=lambda r: r[0])]
[('A', [1, 3]), ('B', [2])]
```

`'A'` 그룹이 **두 번** 나왔다. `groupby` 는 **인접한 같은 키만** 묶으므로 전체를 그룹핑하려면 같은 key로 먼저 정렬해야 한다. 그런데 정렬까지 할 거라면 `defaultdict(list)` 가 더 짧고 $O(n)$ 이다. **`groupby` 가 진짜 이기는 자리는 "연속"이 문제의 조건일 때다** — 런랭스 압축, 연속 출석 일수, 같은 상태가 몇 번 이어졌는가.
:::

전탐색을 꺼내기 전에는 **개수를 먼저 계산해라.** `combinations(range(20), 3)` 은 1,140개지만 `permutations(range(10))` 은 3,628,800개, `permutations(range(11))` 은 39,916,800개다. `math.comb`, `math.perm`, `math.factorial` 로 1초면 확인한다. 파이썬에서 1,000만 회를 넘으면 제한 시간을 의심해야 하고, 가지치기가 필요한 지점이면 그건 `itertools` 가 아니라 백트래킹이다([7.18](#/backtracking)).

**안 집는 경우 —** `product` 로 2중 루프를 대신하는 건 취향이지만 **읽는 사람이 한 번 멈춘다면 지는 장사다.** `zip`, `enumerate`, 컴프리헨션([1.9](#/comprehensions))으로 표현되는 것을 굳이 바꾸지 마라. 전체 함수 목록은 [3.2](#/itertools)에 있다.

### functools — 같은 계산을 두 번 하지 않는다

신호: 재귀가 같은 인자로 반복 호출된다, 비교 규칙이 복잡하다.

```pyrepl
>>> from functools import cache
>>> @cache
... def ways(n):
...     return 1 if n <= 1 else ways(n - 1) + ways(n - 2)
...
>>> ways(40)
165580141
```

::: perf @cache 한 줄이 지수를 선형으로 바꾼다
`fib(30)` 을 순수 재귀로 계산할 때와 `@cache` 를 붙였을 때(캐시를 매번 비우고 측정):

| 방법 | 1회 |
| --- | --- |
| 순수 재귀 | 0.103 ~ 0.110 s |
| `@cache` | 0.000007 ~ 0.000014 s |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

$O(\varphi^n)$ 이 $O(n)$ 이 됐다. **네 자릿수 차이는 상수 최적화로 절대 못 만든다.** 재귀가 느리면 알고리즘을 바꾸기 전에 "같은 인자로 두 번 부르고 있지 않은가"를 먼저 봐라. 이게 DP의 절반이다([7.20](#/dp-basics)).
:::

::: danger cache 는 인자가 해시 가능할 때만 동작한다
```pyrepl
>>> from functools import cache
>>> @cache
... def f(xs):
...     return sum(xs)
...
>>> f([1, 2])
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    f([1, 2])
TypeError: unhashable type: 'list'
```

리스트·딕셔너리·집합을 인자로 받는 함수에는 `@cache` 를 못 붙인다. 격자 DP에서 보드를 통째로 넘기다가 여기서 막힌다. **인자를 좌표 같은 스칼라로 바꾸고 보드는 클로저나 전역으로 둬라.** 그리고 `@cache` 는 상한이 없어서 매번 새 인자로 호출하면 캐시가 무한히 자란다. 그럴 땐 `@lru_cache(maxsize=...)` 다([3.1](#/functools)).
:::

비교 규칙이 "두 값을 나란히 놓고 봐야" 정해지면 `cmp_to_key` 다. 대표적인 것이 **이어 붙여서 가장 큰 수 만들기** 유형이다.

```pyrepl
>>> from functools import cmp_to_key
>>> nums = ["10", "9", "5"]
>>> sorted(nums, key=cmp_to_key(lambda a, b: (a + b < b + a) - (a + b > b + a)))
['9', '5', '10']
```

**안 집는 경우 —** 대부분의 정렬은 `key=` 로 끝난다. `cmp_to_key` 는 파이썬 함수 호출이 $O(n \log n)$ 번 일어나 느리니, `key=` 로 표현되면 반드시 `key=` 를 써라([11.6](#/sorting-as-tool)). `reduce` 도 같다 — `sum`, `math.prod`, `max` 로 되는 것에 쓰지 말고 `reduce(math.gcd, nums)` 처럼 **대체 함수가 없을 때만** 꺼낸다.

### set — 가장 자주 잊히는 최강 무기

신호: 중복, 유일, 이미 본 것, 공통, 한쪽에만.

```pyrepl
>>> a = {"kim", "lee", "park"}
>>> b = {"lee", "choi"}
>>> sorted(a & b), sorted(a - b), sorted(a ^ b)
(['lee'], ['kim', 'park'], ['choi', 'kim', 'park'])
>>> {"lee"} <= a
True
```

`&`(공통) `-`(한쪽에만) `^`(양쪽 중 하나에만) `<=`(부분집합). **네 개의 기호가 네 개의 이중 루프를 대신한다.** 특히 `<=` 로 쓰는 부분집합 판정은 "필요한 재료를 다 갖췄는가" 류 문제의 한 줄 답안이다.

::: warn set 은 순서가 없다 — "정렬돼 보이는" 출력에 속지 마라
```pyrepl
>>> {3, 1, 2}
{1, 2, 3}
>>> {8, 1, 9}
{8, 1, 9}
```

첫 줄만 보면 정렬해 주는 것 같다. 아니다. 작은 정수는 해시가 자기 자신이라 우연히 그렇게 보일 뿐이고 두 번째 줄에서 바로 깨진다. **문자열 집합은 실행할 때마다 순서가 달라진다**(해시 시드 무작위화, [7.6](#/hashing)). 출력에 순서가 필요하면 **반드시 `sorted()` 를 거쳐라.** 로컬에서 통과하고 채점에서 떨어지는 전형적인 원인이다.
:::

**안 집는 경우 —** 원소가 해시 불가능하면 못 쓴다.

```pyrepl
>>> {[1, 2]}
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    {[1, 2]}
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
```

좌표를 담을 때 리스트 대신 **튜플**을 쓰는 이유가 이것이다. 그리고 원소가 열 개도 안 되는데 `set` 으로 바꾸는 변환 비용을 치를 필요는 없다. `set`/`frozenset` 자체는 [1.7](#/sets)에 있다.

## 신호가 겹칠 때 무엇을 집는가

실전에서 어려운 건 도구를 모르는 게 아니라 **둘 다 될 것 같을 때**다. 판단 기준을 못으로 박아 둔다.

| 상황 | 갈림길 | 기준 |
| --- | --- | --- |
| 상위 K개 | `heapq.nlargest` vs `sorted` | K가 **상수**면 힙, K가 n의 **비율**이면 정렬 |
| 있는지 확인 | `set` vs `bisect` | 존재 여부만이면 `set`, **몇 개/어느 구간**이면 `bisect` |
| 그룹으로 묶기 | `defaultdict` vs `groupby` | **연속**이 조건이면 `groupby`, 아니면 `defaultdict` |
| 개수 세기 | `Counter` vs `set` | 개수가 필요하면 `Counter`, 유일 여부만이면 `set` |
| 양 끝 처리 | `deque` vs 인덱스 두 개 | **실제로 넣고 빼면** `deque`, 읽기만 하면 인덱스 |
| 반복 계산 | `@cache` vs 직접 딕셔너리 | 인자가 해시 가능하면 `@cache`, 아니면 직접 |

## 하나의 문제, 다섯 개의 도구

실제 문제는 도구를 하나만 쓰지 않는다. **문장마다 다른 도구가 붙는다.**

> 창고 입출고 기록이 시간 순으로 들어온다. 각 줄은 `날짜,품목,IN|OUT,수량` 형식이다.
> ① 출고량 상위 2개 품목 ② 품목별 최종 재고 ③ 재고가 t 이하인 품목 수(t를 바꿔가며 여러 번) ④ 마지막 3건의 기록 ⑤ 한 번도 출고된 적 없는 품목

문장을 하나씩 도구로 번역한다.

- ①  "상위 2개" + 품목별 합계  →  `Counter` 에 누적하고 `most_common(2)`
- ②  "입고 − 출고"  →  `Counter` 뺄셈
- ③  "이하가 몇 개" + **질의 여러 번**  →  값을 한 번 정렬해 두고 `bisect`
- ④  "마지막 3건"  →  `deque(maxlen=3)`
- ⑤  "한 번도 ~ 없는"  →  `set` 차집합

```python title="warehouse.py"
from collections import Counter, deque
import bisect

LOG = [
    "20250301,SKU-A,IN,120", "20250301,SKU-B,IN,40",
    "20250302,SKU-A,OUT,30", "20250302,SKU-C,IN,15",
    "20250303,SKU-A,OUT,25", "20250303,SKU-B,OUT,10",
    "20250304,SKU-D,IN,8",   "20250304,SKU-A,OUT,15",
    "20250305,SKU-C,OUT,5",  "20250305,SKU-B,OUT,12",
]


def analyze(log, recent_n=3):
    inbound, outbound = Counter(), Counter()
    recent = deque(maxlen=recent_n)          # ④ 길이 검사가 필요 없다

    for line in log:
        day, sku, kind, qty = line.split(",")
        qty = int(qty)                       # 여기서 한 번만 변환한다
        (inbound if kind == "IN" else outbound)[sku] += qty
        recent.append((day, sku, kind, qty))

    stock = inbound - outbound               # ② 다중집합 뺄셈
    never_out = set(inbound) - set(outbound)  # ⑤ 차집합
    return outbound, stock, never_out, recent


outbound, stock, never_out, recent = analyze(LOG)
print("출고 상위 2:", outbound.most_common(2))       # ①
print("최종 재고 :", dict(stock))
print("무출고 품목:", sorted(never_out))
print("최근 3건  :", list(recent))

levels = sorted(stock.values())               # ③ 질의 전에 한 번만 정렬
for t in (10, 20, 100):
    print(f"  재고<={t:3d} : {bisect.bisect_right(levels, t)}개")
```

```text nolines
출고 상위 2: [('SKU-A', 70), ('SKU-B', 22)]
최종 재고 : {'SKU-A': 50, 'SKU-B': 18, 'SKU-C': 10, 'SKU-D': 8}
무출고 품목: ['SKU-D']
최근 3건  : [('20250304', 'SKU-A', 'OUT', 15), ('20250305', 'SKU-C', 'OUT', 5), ('20250305', 'SKU-B', 'OUT', 12)]
  재고<= 10 : 2개
  재고<= 20 : 3개
  재고<=100 : 4개
```

`analyze()` 의 본문 로직이 **10줄**이다(빈 줄 제외). 도구 없이 짜면 딕셔너리 초기화와 조건문이 붙어 두 배가 되고, 두 배가 되면 그만큼 틀린다.

::: danger 이 코드에는 이미 함정이 하나 심어져 있다
② 의 `inbound - outbound` 는 **재고가 정확히 0인 품목을 지운다.** 위 데이터에 그런 품목이 없어서 티가 안 났을 뿐이다. `"20250306,SKU-D,OUT,8"` 한 줄만 추가하면 `SKU-D` 가 최종 재고에서 **통째로 사라진다.** "재고 0인 품목을 보고하라"가 요구사항이면 그대로 오답이다.

도구가 코드를 짧게 만들어 주는 대신, 그 도구의 **기본 동작이 요구사항과 일치하는지** 확인하는 건 당신 몫이다. 짧은 코드가 맞는 코드는 아니다.
:::

## 도구를 안 쓰는 것이 정답일 때

무기고를 배운 직후에는 **모든 것에 무기를 쓰고 싶어진다.** 그게 다음 단계의 함정이다.

```python
# ❌ 원소 3개짜리에 도구를 꺼낸다
from collections import Counter
if Counter(flags)["ok"] == len(flags): ...

# ✅ 그냥 내장 함수
if all(f == "ok" for f in flags): ...
```

```python
# ❌ 최솟값 하나에 힙을 쓴다
import heapq
heapq.heapify(costs)
cheapest = heapq.heappop(costs)      # 원본까지 망가진다

# ✅
cheapest = min(costs)
```

```python
# ❌ 이중 루프를 굳이 바꾼다
from itertools import product
for i, j in product(range(n), range(m)): ...

# ✅ 읽는 사람이 멈추지 않는다
for i in range(n):
    for j in range(m): ...
```

::: tip 도구를 꺼내기 전 세 가지 자문
1. **입력 크기가 이 도구를 요구하는가.** n이 100이면 $O(n^2)$ 도 통과한다. [8.4](#/problem-signals)의 역산표로 확인해라.
2. **연산이 반복되는가.** 한 번만 하는 일에 전처리 자료구조를 만드는 건 손해다.
3. **6개월 뒤의 내가 읽고 멈추지 않는가.** 과제형 코딩테스트에서는 이게 채점 항목이다([12.1](#/takehome-eval)).

셋 다 통과하면 꺼내라. 하나라도 걸리면 `for` 가 정답이다.
:::

## 요약

- **도구를 아는 것과 손이 그 도구를 집는 것은 다른 능력이다.** 목표는 지식이 아니라 **문장 → 도구 회로**다.
- 판단은 세 질문으로 끝난다. **① 반복 조회하는가**(`set`/`dict`) **② 꺼내는 순서가 있는가**(`deque`/`heapq`) **③ 정렬된 위치를 묻는가**(`bisect`).
- 각 도구에는 **집지 말아야 할 자리**가 있다. `heapq` 는 K가 커지면 `sorted` 에 지고, `deque` 는 가운데 인덱싱에서 두 자릿수 느리고, `bisect` 는 정렬 안 된 입력에서 **예외 없이 틀린 답**을 낸다.
- **조용히 틀리는 세 가지를 외워라.** `Counter` 뺄셈이 0을 지운다, `defaultdict` 는 조회만 해도 키를 만든다, `set` 출력 순서는 보장되지 않는다.
- `@cache` 한 줄이 지수 시간을 선형으로 바꾼다. 단 **인자가 해시 가능할 때만**.
- 실제 문제는 도구 하나로 안 끝난다. **문장마다 도구를 붙여** 골격을 세우고 나서 코드를 짜라.
- **가장 흔한 실수는 도구를 모르는 게 아니라 안 써도 되는 곳에 쓰는 것이다.** 입력이 작으면 `for` 가 정답이다.

::: quiz 실습 과제 — 읽지 말고 짜라
전부 **직접 코드를 짜서 실행**해라. 제시된 입력에 제시된 출력이 나와야 한다. 과제당 10분.

**1. 좌석 배정 (heapq)**
좌석 번호는 1부터 `n` 까지다. `"A"` 는 **빈 좌석 중 가장 작은 번호**를 배정하고 그 번호를 결과에 남긴다(빈자리가 없으면 `-1`). `"Rk"` 는 좌석 `k` 를 반납한다(결과에 남기지 않는다).

```python
seats(5, ["A", "A", "A", "R3", "A", "A", "A", "A"])  # -> [1, 2, 3, 3, 4, 5, -1]
seats(2, ["A", "A", "A", "R1", "A"])                 # -> [1, 2, -1, 1]
```

**2. 상태 로그 압축 (itertools)**
센서 상태 로그를 `(상태, 연속 횟수)` 리스트로 압축하고, 가장 길게 이어진 구간을 반환해라. 길이가 같으면 먼저 나온 것을 고른다.

```python
compress(["ON", "ON", "OFF", "ON", "ON", "ON"])
# -> ([('ON', 2), ('OFF', 1), ('ON', 3)], ('ON', 3))
compress(["OFF"])
# -> ([('OFF', 1)], ('OFF', 1))
```

**3. 주차 요금 상위 결제자 (bisect + Counter)**
구간 시작값 `[0, 30, 60, 120]`, 요금 `[1000, 2000, 3500, 6000]`. 주차 시간이 속한 구간의 요금을 낸다. `(차량번호, 주차 분)` 기록에서 **차량별 총 결제액 상위 2대**를 구해라. `if/elif` 없이 `bisect` 로 풀어라.

```python
fee(0), fee(29), fee(30), fee(120), fee(500)
# -> (1000, 1000, 2000, 6000, 6000)

top_payers([("11가1111", 20), ("22나2222", 65), ("11가1111", 130),
            ("33다3333", 30), ("22나2222", 10)], k=2)
# -> [('11가1111', 7000), ('22나2222', 4500)]
```

**4. 이동평균 경보 (deque)**
값 스트림에서 **최근 `k` 개의 평균이 `limit` 을 처음 초과하는 인덱스**를 반환해라. 끝까지 없으면 `-1`. `k` 개가 모이기 전에는 판정하지 않는다.

```python
first_alert([10, 12, 11, 40, 42, 9], k=3, limit=20)  # -> 3
first_alert([1, 2, 3], k=3, limit=20)                # -> -1
first_alert([30, 30, 30], k=3, limit=20)             # -> 2
```

**5. 재고 대조 (Counter)**
장부 재고와 실사 재고를 받아 `(초과 품목, 부족 품목)` 을 각각 `(품목, 개수)` 의 정렬된 리스트로 반환해라.

```python
reconcile(book=["A", "A", "B", "C", "C", "C"],
          real=["A", "B", "B", "C", "C", "D"])
# -> ([('B', 1), ('D', 1)], [('A', 1), ('C', 1)])
```

**6. 확장 과제.** 5번을 푼 뒤, 장부와 실사가 **정확히 일치하는 품목의 목록**도 함께 반환하도록 고쳐라. `Counter` 뺄셈만으로는 안 된다는 것을 직접 확인하고, 왜 안 되는지 한 문장으로 적어라.

```python
reconcile2(book=["A", "A", "B", "C"],
           real=["A", "A", "B", "D"])
# -> ([('D', 1)], [('C', 1)], ['A', 'B'])

reconcile2(book=["A", "A", "B", "C", "C", "C"],
           real=["A", "B", "B", "C", "C", "D"])
# -> ([('B', 1), ('D', 1)], [('A', 1), ('C', 1)], [])
```

두 번째가 5번과 같은 입력이다. 세 번째 값이 `[]` 로 나오는 것이 **정답**이다 — 그 데이터에는 개수까지 일치하는 품목이 하나도 없다. 빈 리스트를 보고 "내가 틀렸나"를 의심하지 않으려면, 답을 맞히기 전에 손으로 먼저 세 봐야 한다.
:::

**다음 절**: [11.3 문자열 다루기 완전 정복](#/string-toolkit) — 여기서 고른 무기를 문자열 위에서 실제로 휘두른다.
