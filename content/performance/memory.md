# 5.2 메모리 모델과 측정

::: lead
[1.1 객체와 이름](#/objects-names)에서 참조 카운트가 0이 되면 객체가 죽는다고 배웠다. 이론은 안다. 그런데 지금 이 프로그램이 실제로 메모리를 얼마나 쓰고 있는지, 어디서 새고 있는지는 어떻게 아는가? "느낌"으로는 못 잡는다. 이 절은 `tracemalloc`, `gc`, `sys.getsizeof` 로 메모리를 실제로 들여다보는 법을 다룬다. 누수를 직접 만들고, 직접 잡는다.
:::

## 복습: 참조 카운트만으로는 안 보이는 것

[1.1절](#/objects-names)의 결론을 한 줄로 다시 쓰면 이렇다.

> 객체는 참조 카운트가 0이 되는 순간 죽는다. 순환 참조는 별도의 GC가 처리한다.

이 문장은 맞지만, **"메모리가 얼마나 쓰이고 있는가"**에는 아무 답도 주지 않는다. 참조 카운트는 객체 하나의 생사만 결정할 뿐, 프로그램 전체의 메모리 그림은 그려 주지 않는다. 다음 코드를 보자.

```python
data = [str(i) * 10 for i in range(100_000)]
```

이 한 줄이 메모리를 얼마나 먹었는가? `sys.getsizeof(data)` 로는 안 나온다 — 리스트 컨테이너 크기만 알려 주지, 그 안의 10만 개 문자열은 세지 않는다. 이걸 실제로 측정하는 도구가 `tracemalloc` 이다.

## tracemalloc으로 스냅샷 비교하기

`tracemalloc` 은 파이썬이 `malloc` 을 호출할 때마다 **어느 줄에서 호출됐는지**를 같이 기록하는 표준 라이브러리다. `cProfile` 이 "시간을 어디서 썼는가"를 보여준다면, `tracemalloc` 은 "메모리를 어디서 썼는가"를 보여준다. 사용법의 핵심은 **스냅샷을 두 번 찍고 차이를 비교하는 것**이다.

```python title="basic_tracemalloc.py"
import tracemalloc

tracemalloc.start()

snap1 = tracemalloc.take_snapshot()

data = [str(i) * 10 for i in range(100_000)]

snap2 = tracemalloc.take_snapshot()

top_stats = snap2.compare_to(snap1, "lineno")

print("[ Top 3 differences ]")
for stat in top_stats[:3]:
    print(stat)

current, peak = tracemalloc.get_traced_memory()
print(f"current={current}, peak={peak}")
```

```text nolines
[ Top 3 differences ]
basic_tracemalloc.py:7: size=9561 KiB (+9561 KiB), count=100002 (+100002), average=98 B
tracemalloc.py:560: size=328 B (+328 B), count=1 (+1), average=328 B
tracemalloc.py:423: size=328 B (+328 B), count=1 (+1), average=328 B

current=9793058, peak=9793257
```

(Python 3.14.5 / Windows 기준 실측. 절대 수치는 기기·버전마다 다르지만 **7번째 줄이 범인으로 지목되는 구조**는 어디서나 같다.)

`snap2.compare_to(snap1, "lineno")` 가 핵심이다. 두 스냅샷의 차이를 **줄 단위로** 정렬해서 보여준다. 리스트 컴프리헨션이 있는 7번째 줄이 압도적으로 많은 메모리(9.3 MiB)를 새로 할당했다는 게 바로 드러난다. `sys.getsizeof(data)` 하나만 봤다면 얻지 못했을 그림이다.

::: note `compare_to` 의 그룹 기준
`"lineno"` 대신 `"filename"` 을 쓰면 파일 단위로, `"traceback"` 을 쓰면 호출 스택 전체를 기준으로 묶는다. 문제를 좁혀 갈수록 더 세밀한 기준으로 바꿔라. 처음엔 파일 단위로 어느 모듈이 범인인지 찾고, 그다음 줄 단위로 좁힌다.
:::

## 메모리 누수를 직접 만들고 잡는다

"누수"라는 말은 C에서 온 말이라 파이썬에서는 안 맞는 것처럼 느껴질 수 있다. 파이썬에는 `free()` 를 깜빡하는 버그가 없다. 하지만 파이썬에서도 누수는 일어난다. **아무도 지우지 않는 곳에 계속 참조를 쌓아 두면**, 참조 카운트가 절대 0이 되지 않으므로 객체가 영원히 죽지 않는다. GC가 잡을 수 있는 것은 순환 참조뿐이고, 이런 캐시는 순환도 아니다.

실제로 자주 나오는 패턴을 재현해 본다. 사용자 프로필을 캐싱하는 함수인데, **캐시를 절대 비우지 않는다.**

```python title="leak_hunt.py"
import tracemalloc
import random

_cache = {}  # 여기가 범인이다 — 한 번 넣으면 절대 지우지 않는다


def get_user_profile(user_id):
    if user_id not in _cache:
        _cache[user_id] = {"id": user_id, "history": [f"event-{i}" for i in range(50)]}
    return _cache[user_id]


def handle_request(user_id):
    profile = get_user_profile(user_id)
    return len(profile["history"])


tracemalloc.start()
snap_start = tracemalloc.take_snapshot()

for round_no in range(5):
    # 매 라운드 새로운 방문자 10,000명이 들어온다고 가정
    for _ in range(10_000):
        uid = random.randint(round_no * 100_000, round_no * 100_000 + 99_999)
        handle_request(uid)

    snap = tracemalloc.take_snapshot()
    top = snap.compare_to(snap_start, "lineno")[:1]
    current, _ = tracemalloc.get_traced_memory()
    print(f"round {round_no} 이후 (current={current / 1024:.1f} KiB)")
    for stat in top:
        print(" ", stat)
```

```text nolines
round 0 이후 (current=29442.5 KiB)
  leak_hunt.py:9: size=28.5 MiB (+28.5 MiB), count=515361 (+515361), average=58 B
round 1 이후 (current=58857.8 KiB)
  leak_hunt.py:9: size=56.9 MiB (+56.9 MiB), count=1030198 (+1030198), average=58 B
round 2 이후 (current=88621.9 KiB)
  leak_hunt.py:9: size=85.7 MiB (+85.7 MiB), count=1543954 (+1543954), average=58 B
round 3 이후 (current=117718.6 KiB)
  leak_hunt.py:9: size=114 MiB (+114 MiB), count=2058356 (+2058356), average=58 B
round 4 이후 (current=148235.8 KiB)
  leak_hunt.py:9: size=143 MiB (+143 MiB), count=2575243 (+2575243), average=58 B
```

(Python 3.14.5 / Windows 기준 실측. 라운드마다 약 29 MiB씩 **선형으로** 늘어난다. 실제 서비스라면 이 프로세스는 언젠가 메모리 부족으로 죽는다.)

증거는 명확하다. `current` 가 라운드마다 거의 정확히 같은 양만큼 늘고, 매번 9번째 줄(`_cache[user_id] = ...`)이 범인으로 지목된다. 방문자가 늘어날수록 캐시도 무한정 늘어난다 — 이게 실무에서 가장 흔한 누수 형태다. 새로운 버그를 만드는 게 아니라, **캐시에 유효기간이나 크기 제한을 깜빡한 것**이다.

::: tip 실전에서는 이렇게 고친다
- `functools.lru_cache(maxsize=...)` 로 크기 상한을 둔다.
- `cachetools.TTLCache` 로 유효기간을 둔다.
- 정말 무제한으로 쌓아야 한다면, 그게 의도인지 확인하고 디스크나 별도 저장소로 옮긴다.

**증상은 항상 같다.** `tracemalloc` 으로 시간 경과에 따라 `current` 를 찍었을 때 우상향 직선이 나오면 누수다. 한 번 반짝 올랐다가 평평해지면 정상이다(캐시가 다 채워진 것뿐).
:::

## 순환 참조 + `__del__`: GC는 언제 끼어드는가

[1.1절](#/objects-names)에서 순환 참조는 참조 카운팅으로 못 잡고 별도의 GC가 처리한다고 배웠다. 그런데 **그 회수가 정확히 언제 일어나는지**는 다루지 않았다. `__del__` 을 이용해서 직접 관찰해 보자.

```python title="cycle_del.py"
import gc


class Node:
    def __init__(self, name):
        self.name = name
        self.other = None

    def __del__(self):
        print(f"{self.name} 소멸")


gc.disable()  # 자동 GC를 끄고 순환 참조가 쌓이는 걸 관찰한다


def make_cycle(name):
    a = Node(name + "-A")
    b = Node(name + "-B")
    a.other = b
    b.other = a
    # 함수가 끝나면 a, b라는 지역 이름표는 사라지지만
    # a와 b가 서로를 참조하므로 참조 카운트는 0이 되지 않는다


for i in range(3):
    make_cycle(f"cycle{i}")

print("루프 종료 직후, __del__ 이 하나도 안 찍혔다")
print("gc가 추적 중인 객체 수:", len(gc.get_objects()))

n = gc.collect()
print(f"gc.collect() 가 회수한 객체 수: {n}")
```

```text nolines
루프 종료 직후, __del__ 이 하나도 안 찍혔다
gc가 추적 중인 객체 수: 5518
cycle0-A 소멸
cycle0-B 소멸
cycle1-A 소멸
cycle1-B 소멸
cycle2-A 소멸
cycle2-B 소멸
gc.collect() 가 회수한 객체 수: 6
```

(Python 3.14.5 기준 실측.)

여기서 확인할 두 가지가 있다. 첫째, `Node` 객체 6개는 루프가 끝난 뒤에도 **한동안 죽지 않는다.** 참조 카운트가 0이 안 됐기 때문이다. 둘째, `gc.collect()` 를 부르는 순간에야 비로소 `__del__` 이 전부 호출되며 회수된다.

::: hist 왜 예전에는 이게 더 심각한 문제였나
파이썬 3.4 이전에는 `__del__` 을 정의한 객체가 순환에 끼면 **GC가 아예 포기했다.** 어느 걸 먼저 죽여야 할지(순서 의존성이 있는 소멸자) 정할 방법이 없었기 때문이다. 그런 객체들은 `gc.garbage` 리스트에 쌓인 채 프로그램이 끝날 때까지 살아남았다 — 사실상의 확정 누수였다.

[PEP 442](https://peps.python.org/pep-0442/)(3.4)가 이걸 고쳤다. `__del__` 을 호출하는 순서를 안전하게 정의해서, 순환 참조 안의 객체도 정상적으로 finalize된다. 위 실험에서 순환이 결국 회수된 게 그 덕분이다.
:::

::: warn 그래도 순환 참조는 피하는 게 낫다
지금은 순환이 "영원한 누수"는 아니다. 하지만 **참조 카운팅처럼 즉시 죽지도 않는다.** GC의 세대별 임계값에 도달할 때까지, 또는 누군가 `gc.collect()` 를 부를 때까지 그 객체가 잡고 있는 파일 핸들, 소켓, 락이 그대로 열려 있다. 이게 왜 위험한지는 [1.17 컨텍스트 매니저](#/context-managers)에서 이미 다뤘다 — 자원 해제는 `__del__` 이 아니라 `with` 로 결정론적으로 해야 한다.

순환 참조 자체를 피하고 싶다면 `weakref` 를 쓴다. 부모→자식은 보통 참조, 자식→부모는 약한 참조로 두면 순환이 애초에 생기지 않아서 참조 카운팅만으로 즉시 회수된다.
:::

## 세대별 GC 관찰하기

CPython의 순환 참조 검출기는 모든 객체를 매번 훑지 않는다. **세대별**(generational)로 나눠서, 새로 만들어진 객체(0세대)를 자주 검사하고 오래 살아남은 객체(1, 2세대)는 드물게 검사한다. "오래 산 객체는 앞으로도 오래 산다"는 경험적 가설에 기반한 최적화다.

```python title="gc_gen.py"
import gc
import pprint

gc.collect()  # 기준선을 맞춘다
print("시작 시 gc.get_count():", gc.get_count())
print("gc.get_threshold():", gc.get_threshold())


class Cyclic:
    def __init__(self):
        self.self_ref = self


garbage = [Cyclic() for _ in range(1000)]
del garbage

print("순환 참조 1,000개 생성 후:", gc.get_count())

collected = gc.collect(0)
print(f"gc.collect(0) 회수 개수: {collected}")
print("회수 후:", gc.get_count())

print("gc.get_stats():")
pprint.pprint(gc.get_stats())
```

```text nolines
시작 시 gc.get_count(): (0, 0, 0)
gc.get_threshold(): (2000, 10, 10)

순환 참조 1,000개 생성 후: (1017, 0, 0)

gc.collect(0) 회수 개수: 1000
회수 후: (0, 1, 0)

gc.get_stats():
[{'collected': 1023, 'collections': 4, 'uncollectable': 0},
 {'collected': 0, 'collections': 0, 'uncollectable': 0},
 {'collected': 79, 'collections': 1, 'uncollectable': 0}]
```

(Python 3.14.5 기준 실측. `gc.get_count()` 절댓값은 인터프리터가 이미 만든 객체 수에 따라 달라진다.)

`gc.get_threshold()` 가 `(2000, 10, 10)` 이라는 건, 0세대에 추적 객체가 2,000개 늘어날 때마다(정확히는 할당-해제 수 차이가 임계값을 넘을 때마다) 0세대 검사가 자동으로 돈다는 뜻이다. 1세대 검사가 10번 돌 때마다 2세대 검사가 한 번, 2세대 검사가 10번 돌 때마다도 마찬가지다. 위 실험에서 `Cyclic` 객체 1,000개를 만들었더니 0세대 카운트가 1,017로 뛰었고, `gc.collect(0)` 을 명시적으로 부르니 그 1,000개가 바로 회수됐다.

`gc.get_stats()` 는 세대별 누적 통계를 보여준다. `collected`(회수된 객체 수), `collections`(그 세대의 검사 실행 횟수), `uncollectable`(회수 불가능해서 포기한 객체 수 — 정상 프로그램이면 항상 0이어야 한다)을 담고 있다.

::: perf GC를 끄면 빨라지는가
자동 GC가 순환 검사를 위해 주기적으로 전체 객체를 훑는 건 공짜가 아니다. 순환 참조를 아예 안 만드는 프로그램(예: 대부분의 짧은 스크립트, 배치 작업)이라면 `gc.disable()` 로 끄고 스크립트 끝에서 `gc.collect()` 한 번만 불러도 안전하다. 단, 장기 실행 서버 프로세스에서 끄는 건 위험하다 — 순환 참조가 어딘가에서 생기면 그대로 누적된다. **끄기 전에 반드시 프로파일링으로 GC가 실제 병목인지 확인하라.** [5.1 측정 없이 최적화 없다](#/profiling)의 원칙이 여기도 그대로 적용된다.
:::

## `sys.getsizeof` 의 한계

`sys.getsizeof` 는 객체 **하나**의 크기만 알려준다. 그 객체가 다른 객체를 참조하고 있어도, 참조되는 객체의 크기는 절대 포함하지 않는다.

```pyrepl
>>> import sys
>>> nested = [str(i) * 100 for i in range(1000)]
>>> sys.getsizeof(nested)
8856
```

8,856바이트? 문자열 1,000개(각각 100자 이상)가 들어 있는데 9 KB가 안 된다고? 당연히 틀렸다. `sys.getsizeof(nested)` 는 **리스트가 문자열 객체들을 가리키는 포인터 배열의 크기**만 잰다. 포인터가 가리키는 문자열 본체는 세지 않는다.

이 문제는 [7.11 트라이](#/trie)에서 이미 만났다 — 트라이 노드의 실제 메모리를 재려면 중첩된 자식 노드까지 재귀적으로 더해야 했다. 같은 기법을 여기서 범용으로 다시 쓴다.

```python title="deep_getsizeof.py"
import sys


def deep_getsizeof(obj, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen:          # 이미 잰 객체는 다시 재지 않는다 (순환 방지, 이중 계산 방지)
        return 0
    seen.add(id(obj))

    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += deep_getsizeof(k, seen)
            size += deep_getsizeof(v, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            size += deep_getsizeof(item, seen)
    return size


nested = [str(i) * 100 for i in range(1000)]
print("sys.getsizeof(nested):", sys.getsizeof(nested), "bytes")
print("deep_getsizeof(nested):", deep_getsizeof(nested), "bytes")
```

```text nolines
sys.getsizeof(nested): 8856 bytes
deep_getsizeof(nested): 338856 bytes
```

(Python 3.14.5 기준 실측. 실제 크기는 얕은 측정치의 **38배**다.)

`seen` 집합이 하는 일이 두 가지다. 같은 객체를 두 번 세지 않는 것(중복 계산 방지), 그리고 순환 참조가 있어도 무한 재귀에 안 빠지는 것. [1.1절](#/objects-names)에서 `id()` 가 "지금 이 순간의 정체성"을 잰다고 했는데, 바로 그 성질을 여기서 이용한다.

::: warn deep_getsizeof도 완벽하지 않다
공유된 객체를 다시 세지 않는 건 정확하지만, 그 말은 **여러 컨테이너가 같은 객체를 나눠 가지면 "전체 메모리"와 "이 컨테이너만 지웠을 때 줄어드는 메모리"가 다르다**는 뜻이다. `deep_getsizeof(a) + deep_getsizeof(b)` 가 `deep_getsizeof([a, b])` 보다 클 수 있다 — `a` 와 `b` 가 뭔가를 공유하면. 정확한 참조 그래프 분석이 필요하면 `sys.getsizeof` 로 직접 짜는 것보다 `pympler` 나 `objgraph` 같은 서드파티 도구를 쓰는 게 낫다.
:::

## 객체 개수 폭증 디버깅

메모리가 새는 걸 알아도, "어떤 종류의 객체가 쌓이고 있는가"를 모르면 고칠 수 없다. `gc.get_objects()` 는 GC가 추적 중인 **모든 객체**를 리스트로 반환한다. 타입별로 세면 무엇이 폭증했는지 바로 보인다.

```python title="object_explosion.py"
import gc
from collections import Counter


def type_histogram(top_n=5):
    counter = Counter(type(o).__name__ for o in gc.get_objects())
    return counter.most_common(top_n)


print("평상시:")
for name, count in type_histogram():
    print(f"  {name}: {count}")


class Event:
    def __init__(self, payload):
        self.payload = payload


subscribers = []  # 구독 해지를 깜빡한 리스너를 흉내낸다


def on_event(payload):
    subscribers.append(Event(payload))


for i in range(50_000):
    on_event(f"event-{i}")

print()
print("이벤트 5만 개 처리 후:")
for name, count in type_histogram():
    print(f"  {name}: {count}")
```

```text nolines
평상시:
  wrapper_descriptor: 1128
  tuple: 849
  method_descriptor: 812
  function: 808
  builtin_function_or_method: 706

이벤트 5만 개 처리 후:
  Event: 50000
  wrapper_descriptor: 1128
  method_descriptor: 812
  function: 781
  builtin_function_or_method: 719
```

(Python 3.14.5 기준 실측. `wrapper_descriptor` 등은 인터프리터가 늘 들고 있는 배경 객체들이다.)

`Event` 가 순위표 맨 위로 뛰어오른 게 한눈에 보인다. 실전에서는 이런 식으로 쓴다 — 서버가 오래 돌수록 메모리가 계속 느는데 원인을 모를 때, 운영 중인 프로세스에 훅을 걸어 주기적으로 `type_histogram()` 을 찍어 본다. 특정 타입이 시간에 비례해서 계속 늘면, 그 타입을 어디서 만들고 어디서 안 지우는지를 좇아가면 된다.

::: cote 코딩테스트에서는 이게 왜 중요한가
코딩테스트에서 메모리 제한(보통 128~512 MB)에 걸리는 경우, 원인은 대부분 **불필요하게 큰 중간 자료구조**다. 예를 들어 DFS/BFS에서 방문 배열을 매 재귀 호출마다 복사하거나([7.14 BFS/DFS](#/bfs-dfs)), 메모이제이션 테이블을 실제 상태 공간보다 훨씬 크게 잡는 경우([7.20 DP 기초](#/dp-basics)). `sys.getsizeof` 로 자료구조 하나의 크기를 어림잡아 보는 습관을 들이면, 제출 전에 "이거 메모리 초과 나겠다"를 미리 감지할 수 있다.
:::

## 정리: 이 도구들을 실제로 언제 쓰는가

지금까지 다룬 도구를 정리하면 이렇다.

| 도구 | 무엇을 알려주는가 | 언제 쓰는가 |
| --- | --- | --- |
| `tracemalloc` | 어느 줄이 얼마나 할당했는가 | 메모리가 는다는 걸 이미 알 때, 범인을 찾을 때 |
| `gc.collect()` / `get_stats()` | 순환 참조가 언제·얼마나 회수되는가 | GC 자체가 병목인지, 순환이 안 잡히는지 의심될 때 |
| `sys.getsizeof` / `deep_getsizeof` | 객체 하나(또는 그 트리)가 얼마나 무거운가 | 자료구조 선택을 저울질할 때 |
| `gc.get_objects()` | 어떤 타입이 몇 개나 살아 있는가 | "뭔가 계속 쌓인다"는 증상만 있고 원인을 모를 때 |

::: danger 마이크로 최적화에 시간을 낭비하지 마라
이 절의 도구들은 **"메모리가 문제가 되고 있다"는 증거가 있을 때** 쓰는 것이다. 프로파일링도 안 해 보고 "이 딕셔너리를 튜플로 바꾸면 몇 바이트 아낄 텐데" 하는 식으로 자료구조를 미세 조정하는 데 시간을 쓰지 마라. 대부분의 프로그램에서 메모리 문제는 알고리즘이나 자료구조 선택 자체(예: 전체 데이터를 한 번에 메모리에 올림)에서 오지, 객체 하나의 오버헤드 몇십 바이트에서 오지 않는다. [5.1 측정 없이 최적화 없다](#/profiling)에서 다룰 원칙이 여기서도 똑같다 — **먼저 재고, 그다음 고쳐라.**
:::

## 요약

- `sys.getsizeof` 는 객체 하나만 잰다. 중첩된 참조는 못 잡는다 — `deep_getsizeof` 로 재귀적으로 더해야 한다.
- `tracemalloc` 은 스냅샷 두 개를 비교해서 "어느 줄이 메모리를 새로 잡아먹었는가"를 알려준다. 누수 추적의 기본 도구다.
- 파이썬의 "누수"는 대부분 free를 안 부르는 문제가 아니라 **아무도 지우지 않는 캐시나 리스트에 계속 참조를 쌓는 문제**다.
- 순환 참조 + `__del__` 은 3.4(PEP 442) 이후로는 영원히 새지 않지만, 참조 카운팅처럼 즉시 회수되지도 않는다. `gc.collect()` 가 돌아야 회수된다.
- GC는 세대별로 동작한다. `gc.get_count()`, `gc.get_threshold()`, `gc.get_stats()` 로 각 세대의 상태를 직접 볼 수 있다.
- `gc.get_objects()` 를 타입별로 세면 "무엇이 쌓이고 있는가"를 정확히 짚어낼 수 있다.
- 증거 없이 메모리를 미세 조정하지 마라. 먼저 측정해서 진짜 문제를 찾아라.

::: quiz 연습문제
1. `tracemalloc.take_snapshot()` 을 반복 호출로 여러 번 찍어서, 리스트에 원소를 계속 추가하는 루프의 메모리 증가 추세를 직접 그려 보라. 몇 번째 스냅샷부터 증가가 멈추는지 확인하라(멈추지 않으면 그 자체가 누수다).

2. 다음 코드가 `__del__` 을 언제 호출하는지 예측한 뒤 실행해서 확인하라. `gc.disable()` 를 걸었을 때와 안 걸었을 때가 다른가?

   ```python
   class A:
       def __del__(self):
           print("A 소멸")

   class B:
       def __del__(self):
           print("B 소멸")

   a = A()
   b = B()
   a.ref = b
   b.ref = a
   del a
   del b
   print("여기까지 왔다")
   ```

3. `sys.getsizeof({})` 와 `sys.getsizeof({"a": 1, "b": 2, "c": 3})` 을 비교하라. 왜 원소가 3개 늘었는데 크기 차이가 원소 하나당 일정하지 않은가? [1.6 dict](#/dict)의 내부 구조를 다시 참고하라.

4. `gc.get_objects()` 로 현재 인터프리터가 추적 중인 객체 중 `list` 타입만 몇 개인지 세어 보라. 그다음 크기 100짜리 리스트를 1,000개 만들고 다시 세어서, 몇 개가 늘었는지 확인하라.

5. **깊이 생각해 볼 문제.** `deep_getsizeof` 로 재귀적으로 크기를 잴 때, `seen` 집합에 `id(obj)` 를 저장하는 이유가 두 가지다. 하나는 본문에 나왔다(순환 방지). 나머지 하나는 무엇인가? 힌트: 작은 정수 캐싱과 문자열 인터닝([1.1절](#/objects-names))이 있는 상태에서 리스트 `[1, 1, 1]` 의 `deep_getsizeof` 를 재는 상황을 생각해 보라.
:::

**다음 절**: [5.3 파이썬 레벨 최적화](#/py-optimize) — 지역 변수, 내장 함수, 자료구조 선택만으로 얼마나 빨라지는지.
