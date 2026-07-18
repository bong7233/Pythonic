# 7.11 트라이

::: lead
"사전에 있는 단어 중 `car` 로 시작하는 걸 전부 찾아라." 이런 요구가 나오면 `set` 은 무너진다. `set` 은 "이 단어가 있는가"에는 $O(1)$ 로 답하지만 "이걸로 *시작하는* 단어가 뭐가 있는가"에는 전체를 훑는 것 말고 답이 없다. 트라이(trie)는 문자열을 글자 단위로 쪼개 트리에 묻어서, 접두사 질의를 **찾는 문자열 길이만큼의 시간**으로 끝낸다. 이 절에서는 파이썬다운 트라이 구현(중첩 `defaultdict` 트릭)부터 자동완성, 그리고 실측으로 뒷받침한 시간·공간 트레이드오프까지 다룬다.
:::

## `set` 이 접두사 앞에서 무너지는 지점

[7.6 해시](#/hashing)에서 본 것처럼 `set`/`dict` 는 **정확히 같은 값**을 찾는 데는 최강이다. 해시값 하나 계산해서 버킷 하나 보면 끝난다. 그런데 접두사 검색은 질문 자체가 다르다. "이 값과 같은가"가 아니라 "이 값으로 *시작하는* 것들이 뭔가"를 묻는다. 해시는 값 전체를 뭉개서 숫자 하나로 만드는 함수라서, 접두사가 같다고 해시가 비슷하게 나온다는 보장이 전혀 없다.

```pyrepl
>>> hash("car")
-2453418534198919429
>>> hash("card")
7897834412519231067
```

접두사가 같아도 해시는 완전히 무관하다. 그래서 `set` 으로 접두사를 찾으려면 결국 **모든 단어를 순회하며 `str.startswith` 를 호출**하는 수밖에 없다.

```python title="brute_prefix.py — set/list 기반 접두사 검색"
def brute_prefix_search(words: set[str], prefix: str) -> list[str]:
    return [w for w in words if w.startswith(prefix)]
```

단어가 $n$ 개, 접두사 길이가 $L$ 이면 이건 $O(n \cdot L)$ 이다. 사전 단어 10만 개짜리 자동완성 기능에서 글자를 한 번 칠 때마다 10만 개를 전부 훑는다는 뜻이다.

::: cote 이 유형을 알아채는 신호
"자동완성", "접두사로 시작하는", "사전 검색", "문자열 집합에서 특정 패턴으로 시작하는 것 찾기" — 이런 문구가 나오면 `set` 만으로는 부족하다는 신호다. 프로그래머스의 "가사 검색", 백준의 문자열 자동완성류 문제가 이 패턴이다. 제약 조건에 "질의 개수 $q$, 단어 수 $n$, 단어 길이 $L$" 이 각각 크게 주어져 있고 $O(q \cdot n \cdot L)$ 이 시간 초과 각이면 트라이를 의심하라. 문제 유형을 제약 조건에서 역추론하는 훈련은 [8.4 문제 유형 분류](#/problem-signals)에서 더 다룬다.
:::

## dict 기반 트라이: 중첩 `defaultdict` 트릭

트라이의 아이디어는 단순하다. **공통 접두사를 가진 단어들이 트리에서 경로를 공유하게 만든다.** `car`, `card`, `care`, `cat` 을 넣으면 이런 모양이 나온다.

```text nolines
root
 └── c
      └── a
           ├── r ──(end)── car
           │    ├── d ──(end)── card
           │    └── e ──(end)── care
           └── t ──(end)── cat
```

`c`, `a` 는 네 단어 모두가 공유하는 경로다. `r` 에서 `t` 로 갈라지면서 `car` 계열과 `cat` 이 나뉜다. 노드 하나는 "다음 글자 → 다음 노드"로 가는 딕셔너리이므로, 파이썬에서는 **딕셔너리를 담는 딕셔너리**로 그대로 표현된다.

문제는 "지금 없는 키에 접근하면 자동으로 새 노드를 만들어라"를 어떻게 표현하느냐다. 이걸 위해 `defaultdict` 를 **재귀적으로** 정의하는 관용구가 있다.

```python title="trie_core.py — 중첩 defaultdict 트릭"
from collections import defaultdict

def make_trie():
    return defaultdict(make_trie)   # 자기 자신을 팩토리로 참조한다

END = "#"   # 단어가 여기서 끝난다는 표시. 어떤 실제 글자와도 겹치지 않는 키
```

`defaultdict(make_trie)` 는 *"없는 키에 접근하면 `make_trie()` 를 호출해서 채워 넣어라"* 는 뜻이고, `make_trie()` 가 반환하는 것도 똑같은 `defaultdict(make_trie)` 다. 그래서 `node[ch]` 를 몇 번을 연달아 파고들어도 매번 알아서 새 노드가 생긴다.

```pyrepl
>>> root = make_trie()
>>> root["c"]["a"]["r"]["#"] = True
>>> dict(root)
{'c': defaultdict(<function make_trie at 0x...>, {'a': defaultdict(<function make_trie at 0x...>, {'r': defaultdict(<function make_trie at 0x...>, {'#': True})})})}
```

::: note 왜 END 에 별도 키를 쓰는가
`car` 를 넣고 나면 `car` 가 끝나는 지점의 노드는 **`card`, `care` 로 가는 길목이기도 하다.** 그 노드 자체가 "여기서 단어가 끝난다"는 정보와 "여기서 계속 이어질 수도 있다"는 정보를 동시에 가져야 한다. `END` 키 하나를 얹어 두면 그 노드가 `dict` 이기 때문에 두 정보가 자연스럽게 공존한다. `END` 로 실제 글자와 겹치지 않는 문자(`"#"`, `None`, 빈 문자열 등)를 쓰면 된다.
:::

### 삽입, 검색, 접두사 검색

```python title="trie_ops.py — 삽입/검색/접두사"
def insert(root, word: str) -> None:
    node = root
    for ch in word:
        node = node[ch]      # 없으면 defaultdict가 알아서 만든다
    node[END] = True

def search(root, word: str) -> bool:
    node = root
    for ch in word:
        if ch not in node:    # in 체크는 새 노드를 만들지 않는다
            return False
        node = node[ch]
    return END in node

def starts_with(root, prefix: str) -> bool:
    node = root
    for ch in prefix:
        if ch not in node:
            return False
        node = node[ch]
    return True
```

::: danger `in` 없이 그냥 인덱싱하면 트라이가 오염된다
`search` 에서 `if ch not in node` 검사를 빼고 `node = node[ch]` 만 쓰면, **존재하지 않는 글자를 조회하는 것만으로 새 노드가 생겨 버린다.** `defaultdict` 는 조회와 생성을 구분하지 않는다. 검색 연산이 트라이 구조 자체를 바꾸는 부작용을 만드는 셈이다.

```python
node = root
node["z"]          # ❌ "z" 라는 키가 없는데 조회만 해도 새 defaultdict가 생성된다
print("z" in root)  # True — 방금 존재하게 만들어 버렸다
```

읽기 전용 연산(`search`, `starts_with`)에서는 반드시 `in` 으로 먼저 확인하라. `insert` 처럼 실제로 만들어야 할 때만 직접 인덱싱한다.
:::

이 코드가 맞는지 손으로 확인해 보자.

```pyrepl
>>> root = make_trie()
>>> for w in ["car", "card", "care", "careful", "cat", "cats"]:
...     insert(root, w)
>>> search(root, "car")
True
>>> search(root, "ca")       # 넣은 적 없다 — 경로는 있지만 END가 없다
False
>>> starts_with(root, "ca")
True
>>> starts_with(root, "xa")
False
```

`search("ca")` 가 `False` 인 이유가 핵심이다. `ca` 로 가는 경로는 있지만(`card`, `care` 를 위해 공유됨) 그 노드에 `END` 표시가 없다. **경로가 있다는 것과 그 자리에서 단어가 끝난다는 것은 다른 이야기다.**

## 자동완성: 접두사 아래를 전부 훑는다

접두사에 해당하는 노드까지 내려간 다음, 그 아래 서브트리를 DFS로 훑으면서 `END` 를 만날 때마다 지금까지의 경로를 기록하면 자동완성이 된다.

```python title="autocomplete.py"
def autocomplete(root, prefix: str, limit: int | None = None) -> list[str]:
    node = root
    for ch in prefix:
        if ch not in node:
            return []
    results: list[str] = []

    def dfs(n, path: str) -> None:
        if limit is not None and len(results) >= limit:
            return
        if END in n:
            results.append(prefix + path)
        for ch, child in n.items():
            if ch == END:
                continue
            dfs(child, path + ch)

    node = root
    for ch in prefix:
        node = node[ch]
    dfs(node, "")
    return results
```

```pyrepl
>>> sorted(autocomplete(root, "car"))
['car', 'card', 'care', 'careful']
>>> sorted(autocomplete(root, "ca"))
['car', 'card', 'care', 'careful', 'cat', 'cats']
>>> autocomplete(root, "zz")
[]
```

### 무식한 방법과 대조 검증

직접 짠 트라이가 맞는지 확인하는 가장 믿을 만한 방법은 **브루트포스와 결과를 비교**하는 것이다. 알파벳 3글자로 만들 수 있는 랜덤 문자열 200개를 넣고, 500번의 무작위 접두사 질의에 대해 트라이 결과와 `str.startswith` 브루트포스 결과가 항상 같은지 확인했다.

```python title="verify_trie.py — 무식한 방법과 대조"
import random

random.seed(0)
alphabet = "abc"

def rand_word():
    return "".join(random.choice(alphabet) for _ in range(random.randint(1, 5)))

wordset = list({rand_word() for _ in range(200)})
root2 = make_trie()
for w in wordset:
    insert(root2, w)

def brute_prefix_search(words, prefix):
    return sorted(w for w in words if w.startswith(prefix))

mismatches = 0
for _ in range(500):
    p = rand_word()[:random.randint(1, 3)]
    if sorted(autocomplete(root2, p)) != brute_prefix_search(wordset, p):
        mismatches += 1
print("mismatches:", mismatches, "/ 500")
```

```text nolines
mismatches: 0 / 500
```

(실제로 실행해서 확인한 결과다. 이런 대조 테스트는 시험장에서도 유효하다 — 손으로 짠 최적화 풀이가 맞는지 브루트포스와 대조하는 습관을 들여라. [8.1 코딩테스트 전략](#/cote-strategy)에서 검증 습관을 더 다룬다.)

## 시간복잡도: 실측으로 확인한다

이론상 삽입·검색·`starts_with` 는 전부 $O(L)$ 이다($L$ = 문자열 길이, 단어 수 $n$ 과 무관). 자동완성은 $O(L + k)$ 다($k$ = 결과에 담기는 전체 글자 수). 반면 `set` 기반 브루트포스 접두사 검색은 $O(n \cdot L)$ 이다. 단어 수 $n$ 을 1,000 → 10,000 → 100,000 으로 키워 가며 실제로 재 보면 이 차이가 그대로 드러난다.

```python title="bench_prefix.py"
import random, string, timeit

for n in (1000, 10000, 100000):
    random.seed(42)
    ws = set()
    while len(ws) < n:
        length = random.randint(3, 12)
        ws.add("".join(random.choice(string.ascii_lowercase) for _ in range(length)))
    ws = list(ws)
    r = make_trie()
    for w in ws:
        insert(r, w)
    prefix = ws[0][:3]

    t_brute = timeit.timeit(lambda: [w for w in ws if w.startswith(prefix)], number=200)
    t_trie = timeit.timeit(lambda: autocomplete(r, prefix), number=200)
    print(f"n={n:>7}: brute={t_brute:.4f}s  trie={t_trie:.4f}s  배수={t_brute/t_trie:.1f}x")
```

```text nolines
n=   1000: brute=0.0034s  trie=0.0003s  배수=12.5x
n=  10000: brute=0.0328s  trie=0.0005s  배수=66.6x
n= 100000: brute=0.4457s  trie=0.0012s  배수=372.2x
```

::: perf n이 커질수록 격차가 벌어진다 — 이게 핵심이다
(Python 3.14.5 / Windows 기준 실측. 절대 시간은 기기마다 다르지만 **배수가 $n$ 에 비례해서 커진다는 경향**은 어디서나 같다.)

배수가 12.5배 → 66.6배 → 372.2배로 **거의 선형으로 커진다.** 브루트포스가 $O(n \cdot L)$ 이고 트라이가 $O(L)$ 이니 당연한 결과다. $n$ 이 10배가 되면 브루트포스는 10배 느려지지만 트라이는 그대로다. 코딩테스트에서 "질의 개수도 많고 단어 수도 많다"는 조건이 걸리면 이 배수는 더 벌어진다 — 질의당 브루트포스 비용은 그대로 $O(n \cdot L)$ 인데 그게 $q$ 번 반복되기 때문이다. [7.1 복잡도](#/complexity)에서 다룬 "상수보다 차수가 이긴다"의 실물 증거다.

단, 삽입은 반대 방향이다. 트라이 구축은 매 글자마다 딕셔너리 노드를 만들어야 해서 `set` 에 담는 것보다 20~30배 느리다(직접 측정: n=100,000에서 `set` 구축 0.024초, 트라이 구축 0.58초). **트라이는 "한 번 구축해 놓고 질의를 많이 받는" 상황에 유리하지, 한 번 쓰고 버리는 데이터에는 오히려 손해다.**
:::

## 공간 비용: 트라이는 공짜가 아니다

트라이가 빠른 이유는 접두사를 공유해서 **경로**를 재사용하기 때문이지만, 그 경로 자체가 파이썬 객체다. 빈 `dict` 하나도 공짜가 아니다.

```pyrepl
>>> import sys
>>> from collections import defaultdict
>>> sys.getsizeof({})
64
>>> sys.getsizeof(defaultdict(int))
72
```

노드 하나(`defaultdict`)를 만드는 순간 **최소 72바이트**가 든다. 실제 글자 하나 값도 아직 저장 안 한 빈 껍데기 값이다. 소문자 알파벳으로 만든 3~10글자 랜덤 단어 20,000개를 트라이에 넣고 실제 노드 수와 메모리를 측정했다.

```python title="space_cost.py"
def count_nodes(root):
    n = 1
    stack = [root]
    while stack:
        node = stack.pop()
        for k, v in node.items():
            if k == END:
                continue
            n += 1
            stack.append(v)
    return n

def deep_getsizeof(node, seen=None):
    seen = seen or set()
    if id(node) in seen:
        return 0
    seen.add(id(node))
    size = sys.getsizeof(node)
    for k, v in node.items():
        if k != END:
            size += deep_getsizeof(v, seen)
    return size
```

```text nolines
단어 수: 20000
트라이 노드 수: 83823
트라이 총 메모리(dict 컨테이너만): 16,313,992 bytes  (약 15.6 MiB)
set 총 메모리(문자열 포함): 3,048,800 bytes         (약 2.9 MiB)
트라이/set 비율: 5.35배
```

노드 하나당 평균 약 195바이트가 든다(83,823개 노드에 16.3 MB — 실제로 계산하면 194.6바이트). **같은 20,000개 단어를 `set` 에 문자열 그대로 담는 것보다 트라이가 5배 넘게 무겁다.** 단어들이 공통 접두사를 많이 공유할수록(사전 단어처럼) 이 비율은 좋아지고, 랜덤 문자열처럼 공유가 적으면 이 절 실측치처럼 나쁘게 나온다.

::: deep 왜 이렇게까지 무거운가
`defaultdict` 노드 하나는 그 자체로 해시 테이블이다. 파이썬의 컴팩트 dict 구현([1.6 dict](#/dict) 참고)이 작은 딕셔너리에서도 최소 크기의 해시 테이블과 엔트리 배열을 할당한다. 게다가 `defaultdict` 는 팩토리 함수 참조까지 들고 있어서 일반 `dict` 보다 8바이트 더 크다. 자식이 하나뿐인 노드(사슬처럼 이어지는 구간)에서도 이 오버헤드가 그대로 붙는다.

실무·코테에서 메모리가 빠듯하면 **압축 트라이(radix trie / PATRICIA trie)**를 쓴다. 자식이 하나뿐인 경로를 하나의 노드로 뭉쳐서 노드 수 자체를 줄이는 방식이다. 이 책에서는 다루지 않지만, 접두사가 매우 길고 겹치는 부분이 적은 데이터(URL, 파일 경로)를 다룰 때는 알아 둘 가치가 있다.
:::

## 언제 그냥 `set` 을 쓰는 게 나은가

지금까지의 실측을 종합하면 판단 기준이 명확해진다.

| 상황 | 나은 선택 | 이유 |
| --- | --- | --- |
| **정확히 일치**하는지만 확인 | `set` | $O(1)$ 평균, 메모리도 훨씬 적다. 접두사 공유의 이점을 전혀 못 쓴다 |
| **접두사로 시작하는 것 찾기** (자동완성) | 트라이 | `set` 은 $O(n \cdot L)$, 트라이는 $O(L + k)$ |
| **접두사로 시작하는 개수만** 세기 | 트라이 (노드에 카운트 필드 추가) | 아래 참고. 결과를 다 모으지 않아도 된다 |
| 질의가 **1~2번뿐** | `set`/`list` + `startswith` | 트라이 구축 비용(느리다, 위 실측 참고)을 회수 못 한다 |
| 질의가 **아주 많다** (자동완성 서비스, 반복 질의) | 트라이 | 구축은 한 번, 질의는 수천 번 — 구축 비용이 상쇄된다 |
| 접두사가 아니라 **정렬된 범위** 질의 (`"car" ≤ w < "cas"`) | 정렬된 `list` + `bisect` | [7.5 이분 탐색](#/binary-search)의 `bisect_left`/`bisect_right` 로 충분하고 메모리도 가볍다 |
| 메모리가 빠듯한데 데이터가 크다 | `set` 또는 정렬 리스트 우선 고려 | 트라이는 이 절 실측처럼 5배 이상 더 먹을 수 있다 |

::: cote 코테에서 자주 나오는 변형: "접두사 개수 세기"
자동완성처럼 결과를 다 모을 필요 없이 **"이 접두사로 시작하는 단어가 몇 개인가"** 만 물으면, 각 노드에 지나간 단어 수를 카운트로 얹어 두는 편이 DFS로 다 모으는 것보다 낫다.

```python title="trie_count.py — 접두사 카운트 트릭"
COUNT = "*cnt"

def insert_with_count(root, word: str) -> None:
    node = root
    node[COUNT] = node.get(COUNT, 0) + 1
    for ch in word:
        node = node[ch]
        node[COUNT] = node.get(COUNT, 0) + 1
    node[END] = True

def count_prefix(root, prefix: str) -> int:
    node = root
    for ch in prefix:
        if ch not in node:
            return 0
        node = node[ch]
    return node.get(COUNT, 0)
```

```pyrepl
>>> root3 = make_trie()
>>> for w in ["car", "card", "care", "careful", "cat", "cats"]:
...     insert_with_count(root3, w)
>>> count_prefix(root3, "car")
4
>>> count_prefix(root3, "ca")
6
>>> count_prefix(root3, "cat")
2
>>> count_prefix(root3, "z")
0
```

프로그래머스 "가사 검색" 유형(접두사 또는 접미사로 그룹핑해서 세기)이 정확히 이 패턴이다. 접미사 검색이 필요하면 단어를 뒤집어서 넣으면 된다 — 트라이 구조 자체는 그대로다.
:::

## 종합 판단 흐름

```text nolines
what are you asking about the string set?
  |
  |-- exact match?              --> set / dict            O(1) average
  |
  |-- starts with this value?   --> trie                  O(L)
  |      (autocomplete, prefix count)
  |
  `-- in sorted-order range?    --> sorted list + bisect   O(log n)
       ("car" <= w < "cas")
```

정확히 같은 값인지, 이 값으로 시작하는지(자동완성·접두사 개수), 정렬 순서상 범위에 있는지("car" 이상 "cas" 미만 같은 질의)에 따라 각각 set/dict, 트라이, sorted list + bisect 를 고른다.

이 표의 셋 다 파이썬 표준 라이브러리 안에서 해결된다는 점을 눈여겨봐라. 트라이만 유일하게 표준 자료구조가 아니라 **직접 조립해야 하는 구조**다. 그만큼 "정말 접두사 질의가 반복적으로 필요한가"를 먼저 확인하고 도입하라. 문제를 잘못 읽고 트라이부터 짜기 시작하면 시험 시간을 갉아먹는다.

## 요약

- `set`/`dict` 는 정확히 같은 값 찾기에는 최강이지만 접두사 검색에는 $O(n \cdot L)$ 브루트포스로 떨어진다.
- 트라이는 공통 접두사를 트리 경로로 공유해서 삽입·검색·`starts_with` 를 $O(L)$ 에 끝낸다.
- 파이썬에서는 `defaultdict(make_trie)` 재귀 트릭으로 "없으면 자동 생성"을 한 줄로 구현한다. 단, 읽기 전용 연산에서 `in` 체크 없이 인덱싱하면 조회만으로 트라이가 오염된다.
- 자동완성은 접두사 노드까지 내려간 뒤 DFS로 서브트리를 훑으면 된다. 개수만 필요하면 노드에 카운트 필드를 얹는 게 더 낫다.
- 실측 결과 접두사 검색은 $n$ 이 커질수록 트라이가 브루트포스보다 압도적으로 유리해지지만(1,000개에서 12.5배 → 100,000개에서 372배), 트라이 구축 자체는 `set` 에 담는 것보다 20~30배 느리고 메모리도 5배 이상 더 든다.
- 질의가 적거나 정확히 일치하는지만 물으면 `set` 이 낫다. 정렬 범위 질의는 `bisect` 가 낫다. 트라이는 "구축은 한 번, 접두사 질의는 반복"일 때만 이긴다.

::: quiz 연습문제
1. `search` 함수에서 `if ch not in node` 검사를 지우고 바로 `node = node[ch]` 로만 구현하면 어떤 문제가 생기는지, 코드를 실행해서 확인하라. `search(root, "zzz")` 를 한 번 호출한 뒤 `"z" in root` 를 확인해 보라.

2. 다음 단어들을 트라이에 넣었을 때 총 노드 수(root 제외)를 손으로 세어 보고, `count_nodes` 로 확인하라: `"to"`, `"tea"`, `"ted"`, `"ten"`, `"inn"`.

3. `starts_with(root, "")` (빈 문자열)는 무엇을 반환해야 맞는가? 코드를 실행해서 실제로 확인하고, 그 이유를 설명하라.

4. 접두사가 아니라 **접미사**로 끝나는 단어를 찾는 자동완성을 만들려면 위 코드를 어떻게 바꿔야 하는가? 코드로 구현하고 검증하라. (힌트: 넣을 때 단어를 어떻게 가공하면 되는가.)

5. 단어 100개짜리 사전과 단어 100,000개짜리 사전 각각에 대해 같은 접두사로 자동완성을 수행하는 시간을 직접 측정하라. 단어 수가 1,000배가 되어도 트라이의 자동완성 시간이 거의 그대로인 이유를 이 절의 복잡도 분석과 연결해서 설명하라.
:::

**다음 절**: [7.12 유니온 파인드](#/union-find) — 집합을 트리로 표현해서 "같은 그룹인가"를 거의 $O(1)$ 에 답하는 또 다른 트릭.
