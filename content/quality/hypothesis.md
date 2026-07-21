# 6.3 속성 기반 테스트 (Hypothesis)

::: lead
[6.1 pytest](#/pytest)에서 배운 테스트는 전부 **예제 기반**이다. `assert f(3) == 9` 처럼 사람이 입력을 하나씩 고른다. 문제는 사람이 버그를 만드는 바로 그 상상력의 한계로 테스트 케이스도 고른다는 것이다. 이 절은 다른 접근을 쓴다. "이 함수가 지켜야 할 성질은 무엇인가"만 적으면, 나머지는 기계가 수천 개의 입력을 생성해서 깨뜨려 본다. 아래에서 실제로 손으로 짠 함수 두 개가 이 방법에 무너지는 것을 그대로 보여준다.
:::

## 예제 기반 테스트가 놓치는 것

런렝스 인코딩(run-length encoding)을 짜 보자. 연속된 같은 문자를 `문자+개수`로 압축한다. `"aaabbc"` 는 `"a3b2c1"` 이 된다.

```python title="rle.py"
def encode(s: str) -> str:
    if not s:
        return ""
    result = []
    prev = s[0]
    count = 1
    for c in s[1:]:
        if c == prev:
            count += 1
        else:
            result.append(prev + str(count))
            prev = c
            count = 1
    result.append(prev + str(count))
    return "".join(result)


def decode(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        char = s[i]
        j = i + 1
        num = ""
        while j < len(s) and s[j].isdigit():
            num += s[j]
            j += 1
        result.append(char * int(num))
        i = j
    return "".join(result)
```

테스트를 짠다. 흔히 쓰는 예제들로.

```python title="test_rle_examples.py"
from rle import encode, decode


def test_basic():
    assert encode("aaabbc") == "a3b2c1"
    assert decode("a3b2c1") == "aaabbc"


def test_roundtrip_examples():
    for s in ["", "a", "aaaa", "abcabc", "zzzzzzzzzz"]:
        assert decode(encode(s)) == s
```

```bash
uv run pytest test_rle_examples.py -q
```

```text nolines
..                                                                       [100%]
2 passed in 0.92s
```

통과했다. 커버리지 도구를 돌려도 `encode`, `decode` 의 모든 줄이 실행됐다고 나올 것이다. **그런데 이 코드에는 치명적인 버그가 있다.** 알파벳만 넣어 봤기 때문에 안 보였을 뿐이다. 사람이 테스트 케이스를 고를 때는 자기도 모르게 "정상적인" 입력만 상상한다. 실제 버그는 항상 상상 밖에 있다.

::: note 이게 [6.2 fixture·파라미터화](#/pytest-advanced)와 뭐가 다른가
`@pytest.mark.parametrize` 도 여러 입력을 시도한다. 하지만 **입력 목록은 여전히 사람이 적는다.** 파라미터화는 "내가 생각한 케이스들을 깔끔하게 반복하는 법"이고, 속성 기반 테스트는 "내가 생각조차 못한 케이스를 기계가 찾아내는 법"이다. 둘은 경쟁이 아니라 역할이 다르다. 회귀 테스트(과거에 실제로 터졌던 입력)는 여전히 파라미터화로 고정해 둬야 한다.
:::

## `@given`: 성질을 적으면 기계가 입력을 만든다

Hypothesis를 설치한다. [0.3 uv](#/uv)에서 배운 대로 개발 의존성으로 추가한다.

```bash
uv add --dev hypothesis
```

이제 "예제 하나"를 적는 대신 "**항상 참이어야 하는 성질**"을 적는다. 런렝스 인코딩이 지켜야 할 가장 기본적인 성질은 round-trip이다 — 인코딩했다가 디코딩하면 원본이 나와야 한다.

```python title="test_rle_hypothesis.py"
from hypothesis import given, strategies as st

from rle import encode, decode


@given(st.text())
def test_roundtrip(s):
    assert decode(encode(s)) == s
```

`st.text()` 는 **전략**(strategy)이다. "임의의 문자열을 만들어라"라는 뜻이고, 빈 문자열·한 글자·이모지·서로게이트 쌍까지 온갖 문자열을 만들어 낸다. `@given` 은 이 전략으로 만든 값을 함수에 반복해서 넣어 실행한다. 기본값은 최대 100번이다.

```bash
uv run pytest test_rle_hypothesis.py -q
```

```text nolines
F                                                                        [100%]
================================== FAILURES ===================================
_______________________________ test_roundtrip ________________________________

    @given(st.text())
>   def test_roundtrip(s):

s = '01'

    @given(st.text())
    def test_roundtrip(s):
>       assert decode(encode(s)) == s
E       AssertionError: assert '000000000000...0000000000000' == '01'
E
E         - 01
E         + 000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
E       Falsifying example: test_roundtrip(
E           s='01',
E       )

1 failed in 0.33s
```

(Python 3.14.5 / Windows, `hypothesis==6.157.2` 기준 실제 실행 결과. 무작위 탐색이라 실행마다 결과가 달라질 수 있는데, 카운트만 달라지는 게 아니다. 같은 코드를 여러 번 재현해 보면 절반가량은 위처럼 단일 `AssertionError` 하나로 끝나지만, 나머지 절반 가까이는 Hypothesis가 서로 다른 원인의 실패를 **두 가지** 찾아내 "Found 2 distinct failures"로 판단하고 `ExceptionGroup` 박스 형식(서로 다른 트레이스백 두 개, 그중 하나는 서로게이트 문자 처리 중 나는 `ValueError`)으로 보고한다. 실패의 **개수와 종류 자체**가 실행마다 바뀔 수 있다는 뜻이다. 다만 `s = '01'` 이라는 핵심 재현은 두 형태 모두에 공통으로 나온다 — 이유는 뒤에서.)

100번도 안 채우고 곧바로 실패했다. **`s = '01'`** 이라는, 사람이라면 절대 먼저 시도하지 않았을 입력이다. 무슨 일이 일어났는지 손으로 따라가 보자.

```pyrepl
>>> from rle import encode
>>> encode("01")
'0111'
```

`encode` 는 `'0'` 을 한 번, `'1'` 을 한 번 봤으니 `"0" + "1" + "1" + "1"`, 즉 `"0111"` 을 만든다. 그런데 `decode("0111")` 은 첫 글자 `'0'` 뒤에 이어지는 숫자들을 **전부** "개수"로 읽어 버린다. `'1'`, `'1'`, `'1'` 이 셋 다 숫자로 보이니 `num = "111"` 이 되고, `'0' * 111` 을 만들어 버린다.

**진짜 문제는 오타나 오프바이원이 아니다. 설계 자체가 틀렸다.** `"글자+숫자"` 형식은 원본 문자열에 숫자가 섞여 있으면 인코딩된 결과를 되돌릴 방법이 없어진다. 이건 알파벳만 테스트해서는 원리적으로 발견할 수 없는 종류의 버그였다.

::: cote 코딩테스트에서도 이 함정은 흔하다
런렝스 인코딩, 압축, 직렬화류 문제에서 "구분자로 어떤 문자를 쓸 것인가"는 항상 함정이 있다. 입력 범위에 그 구분자가 나올 수 있는지 제약 조건을 다시 확인하는 습관을 들여라. 이 절의 사고방식 자체가 그 습관을 기계로 자동화한 것이다.
:::

고치려면 애초에 **구조를 바꿔야** 한다. 문자열이 아니라 `(문자, 개수)` 쌍의 리스트로 표현하면 모호함이 사라진다.

```python title="rle_fixed.py"
def encode(s: str) -> list[tuple[str, int]]:
    if not s:
        return []
    result = []
    prev = s[0]
    count = 1
    for c in s[1:]:
        if c == prev:
            count += 1
        else:
            result.append((prev, count))
            prev = c
            count = 1
    result.append((prev, count))
    return result


def decode(pairs: list[tuple[str, int]]) -> str:
    return "".join(char * count for char, count in pairs)
```

같은 속성 테스트를 다시 돌리면 이번엔 통과한다.

```bash
uv run pytest test_rle_fixed_hypothesis.py -q
```

```text nolines
.                                                                        [100%]
1 passed in 0.92s
```

## 전략(strategies): 무엇을, 어떻게 생성할지

`st.text()` 같은 전략이 이 방식의 핵심이다. 몇 가지 기본형과 조합 방법을 실제로 확인해 보자.

| 전략 | 만드는 것 |
| --- | --- |
| `st.integers()` | 임의 정수. 경계 부근(0, -1, 최댓값 근처)을 더 자주 시도한다 |
| `st.floats()` | 부동소수. 기본적으로 `nan`, `inf` 도 포함한다 |
| `st.text()` | 유니코드 문자열. 서로게이트, 제어 문자까지 포함할 수 있다 |
| `st.lists(전략)` | 그 전략으로 만든 값들의 리스트 |
| `st.tuples(전략, ...)` | 고정 길이 튜플 |
| `st.dictionaries(키전략, 값전략)` | 딕셔너리 |
| `st.one_of(전략, ...)` | 여러 전략 중 하나 (합집합) |
| `st.sampled_from([...])` | 주어진 목록에서 고르기 |

전략은 `.map()`, `.filter()` 로 가공하고, `st.composite` 로 여러 전략을 엮어 나만의 전략을 만들 수 있다. 그리고 `assume()` 으로 특정 입력을 아예 걸러낸다.

```python title="test_strategies_demo.py"
from hypothesis import given, assume, strategies as st


@given(st.lists(st.integers()))
def test_sorted_is_ordered(xs):
    ys = sorted(xs)
    assert all(ys[i] <= ys[i + 1] for i in range(len(ys) - 1))


@given(st.integers(), st.integers())
def test_division(a, b):
    assume(b != 0)                      # b == 0 인 경우는 아예 시도하지 않는다
    assert (a // b) * b + (a % b) == a
```

```bash
uv run pytest test_strategies_demo.py -q --hypothesis-show-statistics
```

```text nolines
test_strategies_demo.py::test_sorted_is_ordered:
  - during generate phase (0.05 seconds):
    - 100 passing examples, 0 failing examples, 17 invalid examples

test_strategies_demo.py::test_division:
  - during generate phase (0.03 seconds):
    - 100 passing examples, 0 failing examples, 6 invalid examples
    - Events:
      * 5.66%, invalid because: failed to satisfy assume() in test_division (line 12)

2 passed in 0.22s
```

`test_sorted_is_ordered` 에서 "17 invalid examples"가 눈에 띈다. 이 테스트에는 `assume()` 도 `.filter()` 도 없다 — 그런데도 왜 invalid가 나올까? 확인해 보면 원인은 리스트 길이나 `range(len(ys) - 1)` 의 공집합 여부와 무관하다. `assert xs == xs` 처럼 항상 참인 자명한 어서션만 있고 `assume`·`filter`가 전혀 없는 `@given(st.lists(st.integers()))` 테스트로 똑같이 돌려 봐도 매번 10여 개의 invalid examples가 잡힌다(실제 실행 결과). 즉 이 invalid는 사용자 코드의 조건이 아니라 `st.lists` 내부 생성 엔진이 내부 버퍼를 다 써버려 예제 생성을 조기에 포기하는 경우(버퍼 오버런)에서 나오는 것이고, 사용자가 신경 쓸 지점이 아니다. 반면 `test_division` 의 6개 invalid는 정확히 `assume(b != 0)` 에 걸린 것이다 — **`assume` 을 너무 자주 걸면 유효한 입력을 찾느라 시간을 낭비한다.** 무효 비율이 높으면(대략 절반 이상) 전략 자체를 다시 설계하라는 신호다. 예를 들어 위 예제라면 `st.integers().filter(lambda b: b != 0)` 대신 `st.integers(min_value=1)` 과 `st.sampled_from([-1, 1])` 을 조합해 애초에 0을 만들지 않는 편이 낫다.

::: tip 전략도 합성 함수다
`st.lists(st.tuples(st.text(), st.integers(min_value=0)))` 처럼 전략을 겹겹이 쌓으면 "문자열과 자연수 쌍의 리스트" 같은 복잡한 입력도 한 줄로 표현된다. 도메인 객체(예: 이 책의 `dataclass`, [2.6 dataclasses](#/dataclasses))를 만들 때는 `st.builds(MyClass, 필드1=전략1, ...)` 를 쓴다.
:::

## Shrinking: 실패를 최소 재현으로 줄인다

방금 본 실패 예시가 `s = '01'` 처럼 짧았던 건 우연이 아니다. Hypothesis는 실패를 찾으면 **곧바로 보고하지 않는다.** 그 실패를 유지한 채로 입력을 계속 더 작고 단순하게 줄여 나간다. 이 과정을 **shrinking**이라 한다.

통계를 다시 보면 두 단계로 나뉘어 있다.

```bash
uv run pytest test_rle_hypothesis.py -q --hypothesis-show-statistics
```

```text nolines
test_rle_hypothesis.py::test_roundtrip:

  - during generate phase (0.18 seconds):
    - 26 passing examples, 6 failing examples, 0 invalid examples
    - Found 2 distinct errors in this phase

  - during shrink phase (0.10 seconds):
    - 14 passing examples, 15 failing examples, 0 invalid examples
    - Tried 29 shrinks of which 12 were successful

  - Stopped because nothing left to do
```

(실제 실행 결과. 무작위 생성이 개입하므로 정확한 횟수는 실행마다 달라질 수 있지만 두 단계 구조는 항상 같다.)

**generate 단계**에서 무작위 입력을 시도하다가 실패를 발견하면(위에서는 26번 성공한 뒤 실패 발견, 서로 다른 원인의 오류 2종류 — 뒤에서 설명), 곧바로 **shrink 단계**로 넘어간다. 여기서는 실패를 재현하는 더 작은 입력을 체계적으로 찾는다 — 문자열이면 글자 수를 줄여 보고, 리스트면 원소를 지워 보고, 정수면 0에 가깝게 당겨 본다. **"여전히 실패하는가?"를 계속 확인**하면서, 실패가 사라지는 순간 직전 크기에서 멈춘다. 위 결과에서는 29번 시도해서 12번이 "더 작게 줄여도 여전히 실패"였다.

::: deep 왜 최소화가 디버깅에 결정적인가
탐색 자체는 무작위이므로, 운이 나쁘면 첫 실패가 `"a3f#9你好\x00..."` 같은 뒤죽박죽 문자열일 수 있다. 이런 입력으로는 **어디가 문제인지 눈으로 읽을 수 없다.** shrinking이 그걸 `'01'` 두 글자로 줄여 주기 때문에, 실패 원인이 "문자열에 숫자가 섞이면"이라는 게 한눈에 보인다.

이건 사람이 디버깅할 때 본능적으로 하는 일 — "재현되는 최소 케이스를 찾을 때까지 입력을 지워보기" — 을 기계가 자동으로, 그리고 훨씬 체계적으로 하는 것이다. shrinking이 없는 속성 기반 테스트는 사실상 반쪽이다. QuickCheck(하스켈, 이 개념의 원조)에서 온 아이디어를 Hypothesis가 파이썬에 그대로 들여왔다.
:::

::: note 실패가 재현되는 이유 — 예제 데이터베이스
`--hypothesis-show-statistics` 를 켠 채로 같은 테스트를 캐시가 남아 있는 상태에서 한 번 더 돌리면 이렇게 나온다.

```text nolines
- during reuse phase (0.17 seconds):
  - 0 passing examples, 2 failing examples, 0 invalid examples
  - Found 2 distinct errors in this phase
```

**reuse phase**다. Hypothesis는 실패한 예시를 `.hypothesis/examples/` 밑에 캐시해 두고, 다음 실행에서 **가장 먼저** 그 예시들부터 재생한다. 방금 generate phase에서 서로 다른 원인의 실패 2가지를 찾았다면(위 실행 결과 노트 참고), 캐시에도 2개가 쌓이고 reuse phase는 그 2개를 그대로 재생해 "2 failing examples"로 보고한다 — generate phase가 단일 실패만 찾은 실행이었다면 reuse phase도 1개만 재생한다. 즉 reuse phase의 숫자는 항상 직전 generate phase에서 발견한 실패 종류의 수를 그대로 따라간다. 그래서 어제 발견한 버그가 오늘도 똑같이 재현된다 — 무작위 테스트인데 결과가 들쭉날쭉하지 않은 이유다. CI에서는 이 캐시가 매번 새 컨테이너라 사라지므로, 중요한 실패 사례는 `@example()` 로 코드에 직접 박아 둬야 한다. [6.6 CI/CD](#/ci)에서 캐시 디렉터리를 워크플로에 남기는 법을 다룬다.
:::

## 좋은 property는 어떻게 고르는가

"이 함수가 지켜야 할 성질"을 찾는 게 이 기법의 진짜 난이도다. 자주 쓰는 패턴 네 가지를 정리한다.

1. **Round-trip** — `decode(encode(x)) == x`. 인코딩/디코딩, 직렬화/역직렬화, 파싱/렌더링 쌍에 거의 항상 적용된다.
2. **불변식(invariant)** — 출력이 항상 만족해야 하는 조건. `sorted(xs)` 의 결과는 항상 정렬돼 있고, 원소 개수는 입력과 같다.
3. **오라클(oracle) 비교** — 더 느리지만 확실히 맞는 구현이 있으면, 빠른 구현과 결과를 대조한다. 직접 짠 정렬 함수를 `sorted()` 와 비교하는 것도 오라클 비교다.
4. **메타모픽(metamorphic)** — 입력을 살짝 바꿨을 때 출력이 어떻게 바뀌어야 하는지를 검증한다. 리스트에 원소를 하나 추가하면 최댓값은 절대 줄어들지 않는다, 같은 식.

```python title="my_sort.py — 직접 구현한 정렬 함수"
def bubble_sort(xs):
    xs = list(xs)
    n = len(xs)
    for i in range(n):
        for j in range(n - 1 - i):
            if xs[j] > xs[j + 1]:
                xs[j], xs[j + 1] = xs[j + 1], xs[j]
    return xs
```

```python title="test_oracle_sort.py — 오라클 비교"
from hypothesis import given, strategies as st

from my_sort import bubble_sort


@given(st.lists(st.integers()))
def test_matches_builtin_sort(xs):
    assert bubble_sort(xs) == sorted(xs)
```

```bash
uv run pytest test_oracle_sort.py -q
```

```text nolines
.                                                                        [100%]
1 passed in 0.37s
```

이 절 첫머리의 `rle` 예제는 1번(round-trip)이었다. [7.4 정렬](#/sorting)에서 직접 구현하는 정렬 함수들도 전부 3번 방식으로 검증할 수 있다 — 정답을 이미 아는데 새로 구현할 이유가 있냐고 물을 수 있지만, 목적이 정답을 얻는 게 아니라 **당신이 짠 구현이 맞는지 확인하는 것**이기 때문이다.

::: warn 성질이 "항상 통과하게" 너무 약하게 짜지 마라
`assert result is not None` 같은 성질은 거의 항상 참이라 버그를 못 잡는다. 좋은 성질은 **실패할 수 있어야** 의미가 있다. 새 property를 짤 때는 일부러 함수에 버그를 하나 심어 보고, 그 테스트가 정말 잡아내는지 확인하는 습관을 들여라 — 이걸 **뮤테이션 테스트**적 사고라고 한다.
:::

## Stateful 테스트: 순서에서만 드러나는 버그

지금까지의 property는 함수 호출 한 번에 대한 것이었다. 그런데 어떤 버그는 **호출을 여러 번, 특정 순서로** 해야만 드러난다. 최솟값을 $O(1)$에 추적하는 스택을 만들어 보자.

```python title="minstack.py"
class MinStack:
    """O(1) push/pop/get_min. 보조 스택으로 최솟값을 추적한다."""

    def __init__(self):
        self.data = []
        self.mins = []

    def push(self, x):
        self.data.append(x)
        if not self.mins or x < self.mins[-1]:
            self.mins.append(x)

    def pop(self):
        x = self.data.pop()
        if self.mins and x == self.mins[-1]:
            self.mins.pop()
        return x

    def get_min(self):
        return self.mins[-1]
```

단일 호출로는 문제가 안 보인다. `push(3); get_min()` 은 잘 동작한다. Hypothesis의 `RuleBasedStateMachine` 은 **호출 순서 자체를 생성**한다 — `push`, `pop` 을 무작위로 몇 번씩 섞어 부른 뒤, 매 단계마다 진짜로 참이어야 하는 불변식을 확인한다. 여기서는 "진짜 최솟값을 아는 단순 모델(파이썬 리스트)"과 대조한다.

```python title="test_minstack_stateful.py"
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, precondition, invariant

from minstack import MinStack


class MinStackMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut = MinStack()      # 검사 대상 (system under test)
        self.model = []            # 정답 역할을 하는 단순 모델

    @rule(x=st.integers(min_value=-5, max_value=5))
    def push(self, x):
        self.sut.push(x)
        self.model.append(x)

    @precondition(lambda self: self.model)
    @rule()
    def pop(self):
        self.sut.pop()
        self.model.pop()

    @precondition(lambda self: self.model)
    @invariant()
    def min_matches(self):
        assert self.sut.get_min() == min(self.model)


TestMinStack = MinStackMachine.TestCase
```

`@rule` 로 표시된 메서드가 "할 수 있는 행동"이고, `@precondition` 은 그 행동이 가능한 조건(빈 스택에서는 못 뺀다), `@invariant` 는 매 단계마다 지켜져야 하는 성질이다.

```bash
uv run pytest test_minstack_stateful.py -q
```

```text nolines
F                                                                        [100%]
  +-+---------------- 1 ----------------
    | AssertionError: assert 0 == -1
    |  +  where 0 = get_min()
    |  +  and   -1 = min([0, -1])
    | Falsifying example:
    | state = MinStackMachine()
    | state.push(x=0)
    | state.min_matches()
    | state.push(x=-1)
    | state.min_matches()
    | state.push(x=-1)
    | state.min_matches()
    | state.pop()
    | state.min_matches()
    | state.teardown()
    +---------------- 2 ----------------
    | IndexError: list index out of range
    | Falsifying example:
    | state = MinStackMachine()
    | state.push(x=0)
    | state.min_matches()
    | state.push(x=0)
    | state.min_matches()
    | state.pop()
    | state.min_matches()
    | state.teardown()
    +------------------------------------
1 failed in 1.95s
```

(실제 실행 결과. `hypothesis==6.157.2`.) shrinking이 여기서도 일했다 — 최소 재현이 **호출 3~4개짜리 시퀀스**로 줄어 있다. 두 번째 실패가 핵심을 정확히 짚는다: `push(0); push(0); pop()`. 같은 값을 두 번 넣고 한 번 빼는 것만으로 터진다.

원인은 `push` 의 `x < self.mins[-1]` 이다. **동률(`==`)일 때 `mins` 에 쌓지 않는다.** `0` 을 두 번 넣으면 `mins` 에는 `0` 이 딱 하나만 들어간다. `pop()` 으로 하나를 빼면, 아직 `data` 에 `0` 이 하나 남아 있는데도 `x == mins[-1]` 이 참이라 `mins` 에서 그 하나뿐인 `0` 을 지워 버린다. `data` 에는 여전히 값이 있는데 `mins` 는 텅 비어 `get_min()` 이 `IndexError` 를 던진다. 고치는 방법은 부등호 하나다.

```python title="minstack_fixed.py — < 를 <= 로"
def push(self, x):
    self.data.append(x)
    if not self.mins or x <= self.mins[-1]:  # 동률도 쌓는다
        self.mins.append(x)
```

```bash
uv run pytest test_minstack_fixed_stateful.py -q
```

```text nolines
.                                                                        [100%]
1 passed in 0.77s
```

::: cote 코딩테스트 포인트
`MinStack` 은 실제로 자주 나오는 문제(최소 스택, LeetCode 155 등)다. "중복된 최솟값"은 손으로 짤 때 가장 흔히 놓치는 경계 조건이고, 방금 본 버그가 그 정확한 예다. 스택·큐·트리처럼 **여러 연산을 순서대로 조합**하는 자료구조를 직접 구현했다면, 최소한 손으로 "같은 값 두 번 넣고 빼기" 시나리오는 항상 검산하라. [7.7 스택과 큐](#/stack-queue), [7.8 힙과 우선순위 큐](#/heap)에서 비슷한 자료구조를 더 다룬다.
:::

## 실전 설정: 얼마나 돌릴 것인가

기본 100번은 로컬 개발 중 빠른 피드백에는 맞지만, CI에서 밤새 배치로 도는 스위트라면 더 철저히 돌리고 싶을 것이다. `@settings` 로 프로파일을 나눠 관리한다.

```python title="conftest.py"
from hypothesis import settings, Verbosity

settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=1000, deadline=None)
settings.register_profile("debug", max_examples=10, verbosity=Verbosity.verbose)

# HYPOTHESIS_PROFILE 환경 변수로 선택, 기본은 dev
import os
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
```

```bash
uv run pytest                            # dev 프로파일 — 빠르게
HYPOTHESIS_PROFILE=ci uv run pytest      # CI — 훨씬 많이, 시간 제한 없이
```

::: warn deadline 을 끄는 이유
Hypothesis는 기본적으로 한 예시 실행이 너무 오래 걸리면(기본 200ms) 실패로 처리한다 — 무한 루프를 잡기 위한 안전장치다. 그런데 GitHub Actions 같은 공유 러너는 로컬보다 훨씬 느리고 성능이 들쭉날쭉해서, 진짜 버그가 아닌데 타임아웃으로 실패하는 **깜빡이는(flaky) 테스트**가 생긴다. CI 프로파일에서는 `deadline=None` 으로 꺼 두는 게 안전하다. [6.6 CI/CD](#/ci)에서 이런 flaky 테스트를 다루는 법을 더 본다.
:::

`@given` 은 일반 pytest 함수이므로 [6.2 fixture](#/pytest-advanced)의 `fixture`, `monkeypatch` 와 자유롭게 섞을 수 있다. 다만 `@given` 이 붙은 함수는 **여러 번 재실행**된다는 걸 기억해라 — 함수 스코프 fixture는 실행마다 새로 만들어지지만, 모듈/세션 스코프 fixture에 상태를 쌓는 방식으로 짜면 예시들 사이에 상태가 새어 나가 원인 추적이 꼬인다.

## 언제 쓰고, 언제 쓰지 않는가

속성 기반 테스트가 잘 맞는 곳은 뚜렷하다.

- **순수 함수**, 특히 파싱·직렬화·인코딩처럼 입력과 출력의 관계가 수학적으로 정의되는 곳.
- **자료구조**, 알고리즘 구현 — 특히 이 책 [Part VII](#/complexity)에서 직접 짜는 것들. 정답 오라클(느리지만 확실한 구현, 또는 표준 라이브러리)과 대조하기 좋다.
- **경계값을 사람이 상상하기 어려운** 곳 — 유니코드, 부동소수점, 큰 정수.

잘 안 맞는 곳도 있다.

- **UI, 엔드투엔드 테스트**처럼 "성질"을 정의하기 애매한 곳. "버튼을 누르면 팝업이 뜬다"는 예제 기반이 자연스럽다.
- 외부 API 호출처럼 **부수효과가 크고 재현이 안 되는** 것. 순수 로직만 분리해서 property로 검증하고, 나머지는 예제 기반 + mocking([6.2](#/pytest-advanced))으로 처리하는 편이 낫다.
- 실행이 느린 테스트를 수백~수천 번 반복하면 전체 스위트가 느려진다. `max_examples` 를 낮추거나 dev/ci 프로파일을 분리해서 대응한다.

**속성 기반 테스트는 예제 기반 테스트를 대체하지 않는다.** 실제로 터졌던 버그(회귀)는 여전히 고정된 예제로 박제해 둬야 재발을 확실히 막는다. Hypothesis가 찾아낸 실패 사례(`s = '01'`, `push(0); push(0); pop()`)를 `@example()` 이나 별도의 회귀 테스트로 남겨 두는 것이 실전에서 가장 안전한 조합이다.

## 요약

- 예제 기반 테스트는 **사람이 상상한 입력**만 검사한다. 진짜 버그는 상상 밖에 있다.
- `@given(전략, ...)` 은 그 전략으로 무작위 입력을 만들어 함수를 수백 번 실행한다.
- 전략(`st.text`, `st.integers`, `st.lists` ...)은 조합 가능하다. `assume()` 으로 무효한 입력을 걸러낸다.
- **shrinking**은 실패를 찾은 뒤 그 실패를 유지한 채 입력을 최소로 줄인다. 디버깅 가능한 재현을 만드는 핵심 단계다.
- 좋은 property 네 갈래: round-trip, 불변식, 오라클 비교, 메타모픽.
- `RuleBasedStateMachine` 으로 **호출 순서**에서만 드러나는 버그(스택·큐·상태 있는 객체)를 찾는다.
- CI에서는 `max_examples` 를 늘리고 `deadline=None` 으로 flaky를 줄인다. 발견한 실패 사례는 `@example` 로 고정해 회귀를 막는다.

::: quiz 연습문제
1. 이 절의 `rle.py`(고치기 전)를 직접 저장하고 `st.text(alphabet="ab")` 로 알파벳을 `a`, `b` 두 글자로 제한한 `@given` 테스트를 돌려라. 통과하는가? 왜 `st.text()`(전체 유니코드)를 썼을 때와 다른가?
2. `test_division` 예제에서 `assume(b != 0)` 대신 `st.integers(min_value=1)` 두 개를 곱해 항상 양의 나눗셈만 생성하도록 바꿔라. `--hypothesis-show-statistics` 로 invalid 비율이 어떻게 바뀌는지 확인하라.
3. `MinStack` 에 규칙을 하나 추가하라: `peek()` (스택 맨 위 값 조회, `data[-1]` 반환)를 만들고 `@invariant` 로 `sut.peek() == model[-1]` 을 검증해라. 이 버전에서도 버그가 잡히는가?
4. **깊이 생각해 볼 문제.** `assert decode(encode(s)) == s` 대신 `assert len(encode(s)) <= len(s) * 3` (인코딩 결과가 원본보다 지나치게 길어지면 안 된다) 같은 성질을 하나 더 추가한다면, 이 성질은 몇 글자 이상 반복되는 문자열에서 깨질까? 실제로 `st.text(alphabet="a", min_size=1)` 로 확인해 보라.
:::

**다음 절**: [6.4 로깅과 관측성](#/logging) — 테스트로 못 잡은 버그가 실제 운영 환경에서 터졌을 때, 무슨 일이 있었는지 알아내는 법.
