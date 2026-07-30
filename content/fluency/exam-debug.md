# 11.14 시험장 디버깅과 제출 전 점검

::: lead
채점 결과는 다섯 글자다. **틀렸습니다.** 줄 번호도, 어느 입력에서 틀렸는지도 없다. 여기서 실력이 갈린다. 한쪽은 코드를 처음부터 다시 읽으면서 20분을 태우고, 다른 쪽은 3분 만에 "이 줄이다"까지 온다. 차이는 눈썰미가 아니라 **절차**다. 이 절은 디버거 없이, 실패 입력조차 모르는 상태에서 원인을 좁히는 절차를 다룬다. 그리고 그 절차가 반복해서 잡아내는 실수 패턴과, 제출 버튼 앞에서 도는 마지막 점검을 다룬다.
:::

## 채점 결과에는 줄 번호가 없다

문제부터 보자. 소재는 새로 만든 것이다.

```text nolines
도서관 연체료 정산

첫 줄에 기록 수 N (1 <= N <= 200000).
이어지는 N 줄은 "회원이름 연체일수" 형식이다. 연체일수는 0 이상 정수.

연체료는 하루 단위로 붙는다. 1~7일째는 하루 100원, 8일째부터는 하루 200원.
단 30일을 넘긴 뒤로는 더 붙지 않는다(상한 5300원).

회원별 총 연체료가 가장 큰 회원의 이름과 금액을 공백으로 구분해 출력한다.
동점이면 이름이 사전순으로 앞선 회원을 출력한다.

예제 입력          예제 출력
5                  kim 5600
kim 3
lee 0
kim 40
park 31
lee 7
```

30분 안에 짠 코드는 대개 이렇게 생긴다. 문제 문장이 그대로 코드 문장이 됐다.

```python title="overdue_bug.py — 예제는 통과한다"
import sys


def fee(days):
    if days <= 7:
        return days * 100
    if days <= 30:
        return 700 + (days - 8) * 200      # 8일째부터 200원이니까 -8
    return 5300


def solve(text):
    lines = text.split("\n")
    n = int(lines[0])
    total = {}
    for line in lines[1:n + 1]:
        name, days = line.split()
        total[name] = total.get(name, 0) + fee(int(days))
    best = max(total, key=total.get)
    return f"{best} {total[best]}"


print(solve(sys.stdin.read()))
```

예제를 넣으면 `kim 5600`. 정답이다. 제출하면 **틀렸습니다**.

이 코드에는 버그가 **두 개** 있다. 그리고 둘 다 예제로는 절대 드러나지 않는다. 예제 데이터에 8~30일 구간의 연체일이 하나도 없고, 동점도 없기 때문이다. 이게 실전에서 가장 흔한 실패 모양이다 — **예제는 알고리즘을 확인해 주지만 경계는 확인해 주지 않는다.**

::: warn 예제 통과는 정보가 거의 없다
예제는 문제 작성자가 **설명을 위해** 고른 데이터다. 반례를 찾기 위해 고른 데이터가 아니다. 그래서 예제가 덮는 것은 대개 "정상 경로 한 줄기"뿐이다.

당신이 물어야 할 질문은 "예제가 통과했는가"가 아니라 **"예제가 안 덮은 입력 공간이 어디인가"** 다. 위 문제라면 넷이다. ① 8~30일 구간 ② 동점 ③ `N`이 1 ④ 연체일 0만 있는 입력. 예제를 통과한 직후 이 목록을 만드는 것이 디버깅의 시작이다.
:::

### 다섯 단계

무작정 코드를 다시 읽는 것은 절차가 아니다. 절차는 이렇게 생겼다.

```text nolines
  ┌──────────────────┐
  │ 1. REPRODUCE     │  같은 입력에서 같은 오답이 다시 나오는가
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │ 2. SPLIT         │  어느 단계에서 값이 처음 틀어지는가
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │ 3. SHRINK        │  그 단계를 깨는 가장 작은 입력은 무엇인가
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │ 4. EXPLAIN       │  왜 틀리는지 한 문장으로 말할 수 있는가
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │ 5. FIX           │  그 한 문장이 가리키는 곳만 고친다
  └──────────────────┘
```

순서를 지키는 것이 전부다. 대부분의 시간 낭비는 2번을 건너뛰고 5번으로 뛰는 데서 나온다.

::: danger 설명 없이 고치면 버그가 자리를 옮긴다
`days - 8` 을 `days - 7` 로 바꿨더니 통과했다고 하자. 왜 통과했는지 말할 수 없다면 **당신은 아무것도 고치지 않았다.** 부등호를 뒤집고 인덱스를 ±1 하며 통과를 기다리는 방식은 두 가지 대가를 청구한다. 첫째, 한 경계를 고치고 다른 경계를 깨뜨려 채점 데이터의 절반만 통과하는 상태에서 멈춘다. 둘째, **다음 문제에서 같은 실수를 또 한다** — 원인을 언어화하지 않으면 학습이 일어나지 않는다([11.1](#/fluency-gap)).

**4단계를 못 하면 5단계를 하지 마라.** "8일째 요금이 한 칸 밀렸다"까지 말할 수 있어야 손을 댄다.
:::

## 증상이 원인을 가리킨다

앞 절들이 "이 문제를 보면 → 이 도구"였다면 디버깅은 **역방향**이다. **이 증상을 보면 → 여기를 먼저 본다.** 코드 전체를 훑지 말고 이 표로 후보를 좁혀라.

| 증상 | 가장 먼저 의심할 것 |
| --- | --- |
| 예제는 맞고 채점만 틀림 | 예제가 안 덮는 구간 — 경계값, 동점, 최솟값·최댓값 |
| 첫 케이스는 맞고 두 번째부터 틀림 | 함수 밖에 사는 상태 — 가변 기본값, 전역, 캐시([11.8](#/function-completion)) |
| 실행할 때마다 답이 다름 | `set`/`dict` 순회 순서에 의존([11.2](#/stdlib-arsenal)) |
| 입력 줄 순서를 바꾸면 답이 바뀜 | 동점 규칙이 없다, 또는 그리디가 순서를 가정한다 |
| 답이 항상 1 크거나 1 작음 | off-by-one — `range` 끝, 누적합 인덱스, 양끝 포함 여부 |
| 답이 항상 0 또는 빈 리스트 | 조건이 한 번도 참이 안 됨, 또는 초기값 |
| 한 칸을 고쳤는데 여러 칸이 바뀜 | 얕은 복사 — `[[0] * m] * n`, `list(2차원)` |
| 작은 입력은 맞고 큰 입력에서만 `IndexError` | 음수 인덱스가 조용히 통과하다 결국 범위를 넘음 |
| `TypeError: list indices must be ... not float` | `/` 를 썼다. 인덱스·개수에는 `//`([1.2](#/numbers)) |
| `RecursionError` | 깊이. 반복문으로 바꾸는 쪽을 먼저([7.18](#/backtracking)) |
| 작은 입력은 맞고 큰 입력에서 시간 초과 | 복잡도를 추측하지 말고 **기울기를 재라**(이 절 뒤에서) |
| 로컬은 맞는데 채점기만 런타임 에러 | 메모리, 재귀 한도, 출력량, 남겨 둔 디버그 출력 |

이 표의 값어치는 항목 수가 아니라 **한 줄에 후보를 하나씩만 뒀다는 것**이다. 그 하나를 확인하고 아니면 다음으로 넘어가라.

::: note `breakpoint()` 는 왜 시험장에서 안 쓰이는가
pdb 는 좋은 도구다([0.5](#/repl-debug)). 그런데 자동 채점 환경에서는 표준 입력이 문제 데이터로 채워져 있어서 pdb 가 명령을 받을 수 없고, 웹 에디터는 대개 대화형 세션을 주지 않으며, 결정적으로 **느리다.** 한 스텝씩 밟아서 20만 줄짜리 루프의 어디가 틀렸는지 찾을 수는 없다.

시험장 디버깅은 대화형 관찰이 아니라 **비대화형 좁히기**다. 그래서 이 절의 도구는 pdb 가 아니라 `print`, `assert`, 그리고 대조군이다.
:::

## print 는 세 자리에만 찍는다

`print` 를 뿌리는 것 자체는 문제가 아니다. 문제는 **어디에** 찍느냐다. 루프 안에 하나 넣으면 20만 줄이 쏟아지고, 20만 줄은 읽히지 않는다. 읽히지 않는 출력은 정보가 아니다.

자리는 셋뿐이다.

1. **파싱 직후** — 입력이 내가 생각한 모양으로 들어왔는가. 행 수, 앞 세 행, 타입.
2. **단계 사이** — 각 단계의 출력이 다음 단계에 넘어가기 직전. 크기와 합계 같은 **요약 한 줄**.
3. **반환 직전** — 최종 답과 함께 **답을 고른 근거**. 동점 목록, 선택된 인덱스.

세 자리에 요약만 찍는다. 그러면 아무리 큰 입력에서도 출력은 세 줄이다.

```python title="dbg.py — 스위치 하나로 켜고 끈다"
import sys

DEBUG = True
_LEFT = 20                    # 출력 할당량. 루프 안에서 실수로 불러도 터지지 않는다


def dbg(*args):
    global _LEFT
    if DEBUG and _LEFT > 0:
        _LEFT -= 1
        print(*args, file=sys.stderr)      # 채점 대상은 stdout 이다


def fee(days):                    # 요금 버그는 이미 고쳤다고 하자
    if days <= 7:
        return days * 100
    if days <= 30:
        return 700 + (days - 7) * 200
    return 5300


def solve(text):
    lines = text.splitlines()
    n = int(lines[0])
    rows = [(nm, int(d)) for nm, d in (l.split() for l in lines[1:n + 1])]
    dbg(f"① 파싱  {len(rows)}행 (선언 {n}) 앞 3행={rows[:3]}")

    total = {}
    for nm, d in rows:
        total[nm] = total.get(nm, 0) + fee(d)
    dbg(f"② 집계  {len(total)}명 총합={sum(total.values())}")

    best = max(total, key=total.get)
    top = total[best]
    dbg(f"③ 선택  {best=} {top=} 동점={sorted(k for k, v in total.items() if v == top)}")
    return f"{best} {top}"


print(solve("3\npark 7\nkim 7\nlee 3\n"))
```

```text nolines
① 파싱  3행 (선언 3) 앞 3행=[('park', 7), ('kim', 7), ('lee', 3)]
② 집계  3명 총합=1700
③ 선택  best='park' top=700 동점=['kim', 'park']
park 700
```

위 세 줄은 `stderr` 고, 마지막 `park 700` 한 줄만 `stdout` 이다. 터미널에서는 네 줄이 섞여 보이지만 채점기가 읽는 것은 마지막 줄뿐이다. `2>/dev/null` 로 돌려 보면 정말 한 줄만 남는다.

**③ 이 두 번째 버그를 그대로 보여 준다.** `동점=['kim', 'park']` 인데 `best='park'` 다. 사전순이면 `kim` 이어야 한다. "답을 고른 근거를 함께 찍는다"는 규칙 하나가 코드를 다시 읽는 일을 대신했다.

여기 쓰인 도구 세 개를 눈여겨봐라.

- **`file=sys.stderr`** — 채점기는 `stdout` 만 본다. `stderr` 로 찍으면 디버그 출력이 답을 오염시키지 않는다. 지우는 것을 잊어도 오답이 되지 않는다.
- **f-string 의 `=`** — `f"{best=}"` 는 `best='park'` 로 펼쳐진다. 이름을 따로 쓸 필요가 없으니 오타로 엉뚱한 변수를 찍는 사고가 사라진다.
- **출력 할당량** — 루프 안에서 실수로 `dbg` 를 불러도 20줄에서 멈춘다.

```pyrepl
>>> lo, hi, mid = 3, 9, 6
>>> print(f"{lo=} {hi=} {mid=}")
lo=3 hi=9 mid=6
>>> seats = [1, 2, 3, 4]
>>> k = 2
>>> print(f"{seats[:k]=} {len(seats)=}")
seats[:k]=[1, 2] len(seats)=4
```

::: perf 루프마다 `print` 를 찍으면 시간 초과의 원인이 `print` 가 된다
20만 번 도는 루프에서 `s += i` 만 하는 경우와, 그 안에 `print(f"i={i} s={s}", file=sys.stderr)` 를 하나 넣은 경우다. `stderr` 는 `/dev/null` 로 버렸다.

| | 20만 회 루프 1회 |
| --- | --- |
| `print` 없음 | 7.0 ~ 9.4 ms |
| 루프마다 `print` | 281 ~ 303 ms |

(Python 3.14.0rc2 / Linux 기준 실측. `timeit.repeat(number=1, repeat=5)` 를 네 번 돌린 최솟값과 최댓값. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**30배 이상 느려졌다.** 배수를 소수점까지 외울 필요는 없다 — 재실행마다 30배에서 40배 사이를 오간다. 외울 것은 **자릿수가 하나 바뀐다**는 사실이다. 그리고 채점기는 출력을 파일이나 파이프로 받으니 `/dev/null` 보다 더 느릴 수 있다. 알고리즘을 고치려고 30분을 쓴 다음에야 남겨 둔 `print` 가 원인이었다는 것을 발견하는 일이 실제로 일어난다. 출력이 많은 문제에서 `print` 자체가 얼마나 비싼가는 [8.2](#/io-optimize)에 있다.
:::

## 단계 사이에 불변식을 박는다

`print` 는 당신이 봐야 한다. `assert` 는 **당신이 안 봐도 터진다.** 좁히기의 2단계(SPLIT)를 자동화하는 것이 이쪽이다.

요령은 하나다. 코드를 단계로 쪼개고, **각 단계의 출력이 반드시 만족해야 하는 성질**을 그 단계 끝에 적는다.

```text nolines
  text
    │
    ▼  parse()        assert len(rows) == n
  rows
    │
    ▼  aggregate()    assert sum(total.values()) == sum(fee(d) for _, d in rows)
  total
    │
    ▼  pick()         assert total[best] == max(total.values())
  answer
```

세 불변식의 성격이 서로 다르다는 점이 중요하다.

- `len(rows) == n` — **입력과 파싱 결과의 대조.** 지문이 준 숫자를 실제로 써먹는다.
- 합계 보존 — **집계 단계는 정보를 잃지도 만들지도 않는다.** 누락과 이중 계산을 동시에 잡는다.
- 최댓값 확인 — **선택 단계는 선택만 한다.**

```python title="overdue.py — 단계와 불변식"
CAP_FEE = 5300


def parse(text):
    lines = text.splitlines()          # split("\n") 과 달리 마지막 빈 줄이 없다
    n = int(lines[0])
    rows = [(nm, int(d)) for nm, d in (l.split() for l in lines[1:n + 1])]
    assert len(rows) == n, f"줄 수 {len(rows)} != 선언 {n}"
    return rows


def fee(days):
    if days <= 7:
        return days * 100
    if days <= 30:
        return 700 + (days - 7) * 200
    return CAP_FEE


def aggregate(rows):
    total = {}
    for name, days in rows:
        total[name] = total.get(name, 0) + fee(days)
    assert sum(total.values()) == sum(fee(d) for _, d in rows), "집계에서 합이 새 나갔다"
    return total


def pick(total):
    return min(total, key=lambda nm: (-total[nm], nm))    # 값 내림차순, 이름 오름차순


def solve(text):
    total = aggregate(parse(text))
    best = pick(total)
    return f"{best} {total[best]}"
```

`parse` 의 불변식은 실제로 자주 터진다. 입력이 잘려 들어오거나 `N` 을 잘못 읽었을 때다.

```pyrepl
>>> parse("2\nkim 3\nlee 5\n")
[('kim', 3), ('lee', 5)]
>>> parse("5\nkim 3\n")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    parse("5\nkim 3\n")
    ~~~~~^^^^^^^^^^^^^^
  File "<stdin>", line 5, in parse
    assert len(rows) == n, f"줄 수 {len(rows)} != 선언 {n}"
           ^^^^^^^^^^^^^^
AssertionError: 줄 수 1 != 선언 5
```

이 한 줄이 없으면 같은 상황에서 답이 그냥 `kim 300` 으로 나온다. **예외 없이 틀린 답**이 가장 비싼 종류의 버그다.

### 함수 하나를 전 구간으로 훑어라

불변식은 파이프라인 사이에만 박는 게 아니다. **작은 함수 하나에도 성질이 있다.** `fee` 는 30일까지 엄격히 증가하고 그 뒤로는 고정이다. 이걸 그대로 적으면 첫 번째 버그가 즉시 잡힌다.

```python title="요금 함수의 성질을 그대로 옮긴다"
# fee 와 CAP_FEE 는 위 overdue.py 에서 가져온다. 이 네 줄만 이어 붙이면 된다.
slipped = [d for d in range(30) if not fee(d) < fee(d + 1)]
assert not slipped, f"요금 계단이 밀렸다: d={slipped}"
assert {fee(d) for d in range(30, 100)} == {CAP_FEE}, "상한이 고정되지 않았다"
assert fee(0) == 0
```

버그 버전(`days - 8`)에 걸면 `AssertionError: 요금 계단이 밀렸다: d=[7]` 이다. 눈으로 보고 싶으면 구간을 그냥 다 찍어라. 이게 시험장에서 가장 값싼 검사다.

```python title="경계 앞뒤를 통째로 찍는다"
def fee_bug(d):
    return d * 100 if d <= 7 else (700 + (d - 8) * 200 if d <= 30 else 5300)


def fee_ok(d):
    return d * 100 if d <= 7 else (700 + (d - 7) * 200 if d <= 30 else 5300)


print("버그:", [fee_bug(d) for d in range(12)])
print("정상:", [fee_ok(d) for d in range(12)])
print("상한:", sorted({fee_bug(d) for d in range(30, 100)}),
      sorted({fee_ok(d) for d in range(30, 100)}))
```

```text nolines
버그: [0, 100, 200, 300, 400, 500, 600, 700, 700, 900, 1100, 1300]
정상: [0, 100, 200, 300, 400, 500, 600, 700, 900, 1100, 1300, 1500]
상한: [5100, 5300] [5300]
```

**`700` 이 두 번 나왔다.** 단조 증가해야 하는 수열에서 같은 값이 이어지면 계단이 한 칸 밀린 것이다. 상한 검사도 같은 버그를 잡는다 — 버그 버전의 30일 이후 요금이 값 두 개다. `fee_bug(30)` 이 `5100` 인데 `fee_bug(31)` 부터는 `5300` 이라서 그렇다.

::: tip 구간 공식 대신 하루씩 더하는 함수를 하나 더 짜라
경계를 틀리는 이유는 구간 공식을 쓰기 때문이다. 하루씩 더하는 루프는 느리지만 **경계를 틀릴 수가 없다.**

```python
# CAP_FEE 는 위 overdue.py 에서 가져온다.
def fee_slow(days):
    total = 0
    for i in range(1, min(days, 30) + 1):
        total += 100 if i <= 7 else 200      # 규칙을 그대로 옮겼을 뿐이다
    return min(total, CAP_FEE)
```

0~199 전 범위에서 `fee` 와 `fee_slow` 가 일치하는 것을 확인했다. 이 함수는 세 가지로 쓰인다. **① 경계 검증의 정답지 ② 잠시 뒤에 볼 반례 축소의 대조군 ③ 시간이 없을 때 그냥 제출할 답.** 규칙 그대로 옮긴 느린 함수를 지우지 않는 습관이 여기서 이자를 낸다([11.7](#/blank-page-routine)).
:::

::: warn 불변식 `assert` 는 제출 전에 비용을 확인해라
`assert` 자체는 싸다. 단순 비교를 20만 회 하는 루프에서 `assert 0 <= x < 200_000` 를 넣으면 6.2 ~ 9.0 ms 가 10.5 ~ 12.3 ms 로 늘어난다. 수 밀리초다.

문제는 **$O(n)$ 검사를 루프 안에 넣는 것**이다. 위 `aggregate` 의 합계 검사를 루프 밖이 아니라 안에 두면 이렇게 된다. 단 `sum(fee(d) for _, d in rows)` 를 그대로 안으로 넣으면 부분합과 전체합이 달라 **첫 반복에서 터진다.** 루프 안에 두려면 오른쪽을 러닝합으로 바꿔야 한다. 그래도 왼쪽 `sum(total.values())` 가 매 반복 $O(n)$ 이다.

```python title="bench_assert.py — 합계 검사를 루프 안에 둔다"
# fee 는 고친 버전(days - 7)이다. 위 overdue.py 에서 가져온다.


def aggregate_checked(rows):
    total = {}
    running = 0                                   # 오른쪽은 O(1) 러닝합
    for name, days in rows:
        f = fee(days)
        total[name] = total.get(name, 0) + f
        running += f
        assert sum(total.values()) == running, "집계에서 합이 새 나갔다"   # 여기가 O(n)
    return total


def aggregate_plain(rows):
    total = {}
    for name, days in rows:
        total[name] = total.get(name, 0) + fee(days)
    return total
```

데이터는 `(이름, 연체일)` 튜플 n개이고 이름은 전부 서로 다르다(`[(f"m{i:06d}", 0~40 난수) for i in range(n)]`).

| n | 루프 안 `assert` | 없음 |
| --- | --- | --- |
| 2,500 | 31.6 ~ 35.8 ms | 0.41 ~ 0.48 ms |
| 5,000 | 127 ~ 132 ms | 0.89 ~ 1.07 ms |
| 10,000 | 507 ~ 558 ms | 1.91 ~ 2.18 ms |
| 20,000 | 2,041 ~ 2,078 ms | 4.20 ~ 4.54 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

$O(n)$ 짜리 루프가 $O(n^2)$ 이 됐다. **불변식은 단계 경계에, 즉 루프 밖에 둬라.** 그리고 `python -O` 로 돌리면 모든 `assert` 가 사라진다는 것도 알아 둬라 — 그런 채점기는 드물지만, 그래서 `assert` 에 **프로그램 동작을 넣으면 안 된다.** `assert` 는 검사만 한다.
:::

## 반례를 최소로 줄인다

여기가 이 절의 핵심 기법이다. 대부분의 사람은 "반례를 찾았다"에서 멈춘다. 그런데 **여섯 줄짜리 반례는 여전히 읽어야 하고, 한 줄짜리 반례는 원인을 그대로 가리킨다.**

절차는 둘이다. **① 무작위 입력으로 반례를 찾는다 ② 반례를 더 이상 줄어들지 않을 때까지 줄인다.** 두 번째를 축소(shrinking)라고 부른다.

대조군은 `fee_slow` 다. 규칙을 그대로 옮긴 함수와 답이 갈리면, 갈린 쪽이 틀린 것이다.

```python title="shrink.py — 반례를 찾고 줄인다"
import random

# fee 는 버그 버전(days - 8), fee_slow 는 규칙을 그대로 옮긴 함수다. 위 두 블록에서 가져온다.


def answer(rows, f):
    total = {}
    for name, days in rows:
        total[name] = total.get(name, 0) + f(days)
    best = min(total, key=lambda nm: (-total[nm], nm))
    return best, total[best]


def fails(rows):
    """이 입력이 버그를 드러내는가."""
    return bool(rows) and answer(rows, fee) != answer(rows, fee_slow)


def shrink(rows):
    """fails(rows) 를 유지하면서 더 이상 줄어들지 않을 때까지 줄인다."""
    moved = True
    while moved:
        moved = False
        for i in range(len(rows)):                       # 개수를 줄인다: 줄 삭제
            if fails(cand := rows[:i] + rows[i + 1:]):
                rows, moved = cand, True
                break
        if moved:
            continue
        for i, (name, days) in enumerate(rows):          # 크기를 줄인다: 값 축소
            for smaller in (0, days // 2, days - 1):
                if 0 <= smaller < days and fails(
                        cand := rows[:i] + [(name, smaller)] + rows[i + 1:]):
                    rows, moved = cand, True
                    break
            if moved:
                break
    return rows


random.seed(7)
for attempt in range(1, 10001):
    rows = [(random.choice("abc"), random.randint(0, 40))
            for _ in range(random.randint(1, 8))]
    if fails(rows):
        break
else:
    raise SystemExit("반례를 못 찾았다")

print(f"{attempt}번째 시도에서 반례 발견 ({len(rows)}행)")
print("  입력:", rows)
print("  내 답:", answer(rows, fee), " 대조군:", answer(rows, fee_slow))

small = shrink(list(rows))
print(f"축소 후 {len(small)}행")
print("  입력:", small)
print("  내 답:", answer(small, fee), " 대조군:", answer(small, fee_slow))
```

```text nolines
1번째 시도에서 반례 발견 (6행)
  입력: [('a', 25), ('c', 3), ('a', 34), ('a', 23), ('c', 3), ('c', 13)]
  내 답: ('a', 13100)  대조군: ('a', 13500)
축소 후 1행
  입력: [('c', 8)]
  내 답: ('c', 700)  대조군: ('c', 900)
```

**여섯 줄이 한 줄이 됐고, 그 한 줄은 `('c', 8)` 이다.** 8일. 요금 규칙이 바뀌는 바로 그 지점이다. 원본 반례에서는 `13100` 과 `13500` 이라는 큰 수만 보였고 어느 줄이 문제인지 알 수 없었다. 축소된 반례는 4단계(EXPLAIN)를 대신 해 준다.

`fails` 를 갈아 끼우면 같은 축소기로 다른 버그도 잡는다. 요금을 고친 뒤 이번에는 `max(total, key=total.get)` 과 사전순 규칙을 대조하면 두 번째 버그가 나온다.

```text nolines
184번째 시도에서 반례 발견: [('c', 39), ('b', 40)]
  내 답: ('c', 5300)  대조군: ('b', 5300)
축소 후: [('c', 30), ('b', 30)]
  내 답: ('c', 5300)  대조군: ('b', 5300)
```

두 회원의 금액이 같고, 내 코드는 먼저 들어온 `c` 를 골랐다. `max` 는 동점일 때 **먼저 만난 원소**를 돌려준다. 지문은 사전순을 요구했다.

::: note 축소기는 국소 최소에서 멈춘다
`[('c', 30), ('b', 30)]` 이 더 안 줄어든 것을 보라. 30을 15로 줄이면 두 사람의 금액이 달라져서 동점이 사라지고, 그러면 `fails` 가 거짓이 되어 축소가 거부된다. **한 줄만 바꾸는 이동으로는 여기서 나갈 수 없다.**

축소기가 도달하는 최소 크기는 **이동 집합이 결정한다.** "모든 줄을 같은 값으로 동시에 낮추기"를 이동에 추가하면 `[('c', 0), ('b', 0)]` 까지 내려간다(실행 확인). 시험장에서는 여기까지 정교하게 만들 필요가 없다. **줄 삭제와 값 반감, 이 둘만으로 대개 열 줄이 두세 줄이 된다.** 그거면 원인을 읽을 수 있다.
:::

### 대조군이 없을 때 — 오라클 없는 검사

축소는 대조군을 요구한다. 그런데 문제 자체가 어려워서 대조군을 짤 수 없을 때도 있다. 그때 쓰는 것이 **입력을 변형해도 답이 변하지 않아야 한다**는 성질이다. 정답을 몰라도 쓸 수 있다.

가장 값싸고 가장 잘 걸리는 것이 **순서 뒤집기**다.

```python title="order_check.py — 정답을 몰라도 버그를 잡는다"
import random

# fee 는 고친 버전(days - 7)이다. 위 overdue.py 에서 가져온다.


def mine(rows):                               # 검증 대상. 요금은 이미 맞다
    total = {}
    for name, days in rows:
        total[name] = total.get(name, 0) + fee(days)
    best = max(total, key=total.get)          # 여기에 동점 규칙이 없다
    return best, total[best]


random.seed(3)
broken = []
for _ in range(2000):
    rows = [(random.choice("abc"), random.randint(0, 40))
            for _ in range(random.randint(1, 6))]
    if mine(rows) != mine(rows[::-1]):        # 순서만 뒤집었다
        broken.append(rows)

print(f"2,000건 중 {len(broken)}건이 입력 순서에 따라 답이 달라진다")
first = broken[0]
print("  ", first, "->", mine(first))
print("  ", first[::-1], "->", mine(first[::-1]))
```

```text nolines
2,000건 중 47건이 입력 순서에 따라 답이 달라진다
   [('a', 34), ('b', 26), ('c', 37)] -> ('a', 5300)
   [('c', 37), ('b', 26), ('a', 34)] -> ('c', 5300)
```

지문에 "입력 순서에 따라 답이 달라진다"는 말이 없었다면 **이 검사만으로 버그가 확정된다.** 2,000건 중 47건, 2%가 걸렸다.

::: tip 오라클이 없어도 쓸 수 있는 성질 네 개
1. **순서 불변** — 입력 순서를 뒤집거나 섞어도 답이 같아야 한다. 동점 규칙 누락과 순서 가정을 잡는다.
2. **멱등** — 같은 함수를 두 번 적용해도 결과가 같아야 하는 종류의 연산(정규화, 중복 제거, 정렬)에서.
3. **역연산 왕복** — 압축과 해제, 인코딩과 디코딩. `decode(encode(s)) == s` 는 정답표 없이 성립한다.
4. **분할 일관성** — 입력을 둘로 쪼개 각각 처리하고 합친 결과가 통째로 처리한 결과와 같아야 하는 집계·누적 문제에서.

전부 **정답을 모르는 상태에서** 쓸 수 있다. 시험장에서 대조군을 짤 시간이 없을 때 이 넷 중 하나는 대개 쓸 수 있다. 속성 기반 테스트라는 이름으로 정식화된 방법이고, 도구까지 쓰려면 [6.3](#/hypothesis)에 있다.
:::

## 반복되는 실수 다섯 가지

같은 사람이 같은 실수를 한다. 아래 다섯 개가 이 파트의 드릴 절들에서 반복해 나온 것들이다. 각각을 **증상 → 5초 확인법**으로 외워라.

### off-by-one — 답이 정확히 1 또는 한 칸 어긋난다

증상: 답이 항상 1 크거나 작다. 첫 원소나 마지막 원소만 빠진다. 길이 1 입력에서만 틀린다.

5초 확인법: **길이 1과 길이 2를 넣어라.** 구간 문제라면 **한 칸짜리 구간**을 넣어라. 누적합에서 `area(r, c, r, c) == grid[r][c]` 가 성립하는지 보는 것이 정확히 이 검사다([11.10](#/drill-grid)).

경계가 있는 함수라면 위의 `fee` 처럼 **경계 앞뒤를 다 찍어라.** 단조성이 깨지는 자리가 밀린 자리다.

### 음수 인덱스 — 예외 없이 뒤에서 원소를 꺼내 온다

증상: 작은 입력은 맞고 특정 입력만 조용히 틀린다. 더 큰 입력에서는 `IndexError` 로 터진다.

5초 확인법: **`range` 나 슬라이스에 들어가는 식에 `- k` 나 `- 1` 이 있으면 `max(0, ...)` 로 감싸져 있는지 본다.** 파이썬에서 `a[-1]` 은 유효 문법이라 경계 검사가 무력화된다. 격자·구간 문제에서 가장 많이 나오는 버그다([11.8](#/function-completion), [11.12](#/drill-mixed)).

### 얕은 복사 — 한 칸을 고쳤는데 여러 칸이 바뀐다

증상: 한 행만 수정했는데 모든 행이 같이 바뀐다. 백업해 둔 값이 원본과 함께 변한다.

```pyrepl
>>> board = [["."] * 3] * 3
>>> board[0][0] = "X"
>>> board
[['X', '.', '.'], ['X', '.', '.'], ['X', '.', '.']]
>>> saved = list(board)
>>> saved[1][1] = "O"
>>> board[1][1]
'O'
```

두 번째가 더 잡기 어렵다. `list(board)` 는 **바깥 리스트만** 새로 만든다. 안쪽 행은 원본과 같은 객체다. 시뮬레이션 문제에서 "이전 상태를 저장해 두고 비교"할 때 정확히 여기서 무너진다.

5초 확인법: **바꾸기 전과 후를 둘 다 찍어 봐라.** 하나를 바꿨는데 둘이 바뀌면 확정이다. 2차원은 `[[0] * m for _ in range(n)]`, 복사는 `[row[:] for row in board]` 다. 왜 그런가는 [1.1](#/objects-names)과 [11.4](#/array-grid)에 있다.

### 케이스 사이 상태 누출 — 두 번째 호출부터 틀린다

증상: 첫 케이스는 맞고 두 번째부터 틀린다. 혼자 돌리면 맞는데 채점기에서만 틀린다.

5초 확인법: **같은 입력을 두 번 연달아 호출해서 같은 답이 나오는지 본다.**

```python
assert solve(EX) == solve(EX)      # 이 한 줄이 이 범주 전체를 잡는다
```

원인은 함수 밖에 사는 가변 객체다. 가변 기본값, 모듈 수준 리스트·`Counter`, 전역을 읽는 `@cache`. 각각이 어떻게 새는지는 [11.8](#/function-completion)에서 실제 코드로 다뤘다.

### 입력 파싱 — 애초에 문제를 안 읽고 시작했다

증상: 첫 줄이나 마지막 줄에서만 터진다. `ValueError`. 문자열 비교가 이유 없이 실패한다.

파싱 사고는 종류가 적고 반복된다.

```pyrepl
>>> raw = "3\nkim 5\nlee 2\n"
>>> raw.split("\n")
['3', 'kim 5', 'lee 2', '']
>>> raw.splitlines()
['3', 'kim 5', 'lee 2']
>>> raw.split()
['3', 'kim', '5', 'lee', '2']
```

`split("\n")` 은 **마지막 개행 뒤의 빈 문자열을 남긴다.** 그 줄을 `line.split()` 하면 빈 리스트가 되고 언패킹이 터진다.

```pyrepl
>>> for line in "3\nkim 5\nlee 2\n".split("\n")[1:]:
...     name, days = line.split()
... 
Traceback (most recent call last):
  File "<stdin>", line 2, in <module>
        name, days = line.split()
ValueError: not enough values to unpack (expected 2, got 0)
```

::: warn `split()` 과 `split(" ")` 은 다른 함수다
인자가 없는 `split()` 은 **연속된 공백을 하나로 보고 양끝을 다듬고 개행까지 먹는다.** 인자를 주면 그 문자만 정확히 자른다.

```pyrepl
>>> "kim 12\n".split()
['kim', '12']
>>> "kim 12\n".split(" ")
['kim', '12\n']
>>> int("12\n")
12
>>> "12\n" == "12"
False
```

세 번째 줄이 함정이다. `int("12\n")` 은 **성공한다.** 그래서 숫자만 다루는 문제에서는 개행이 남아 있어도 아무 일이 없다. 그런데 문자열을 비교하는 순간 조용히 전부 `False` 가 된다. 명령어나 상태 문자열을 파싱하는 문제에서 여기서 무너진다([11.3](#/string-toolkit)).

**공백으로 나눌 때는 항상 인자 없는 `split()`, 줄로 나눌 때는 `splitlines()`.**
:::

이터레이터를 두 번 쓰는 것도 파싱 자리에서 자주 나온다.

```pyrepl
>>> nums = map(int, "4 7 2".split())
>>> sum(nums)
13
>>> max(nums)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    max(nums)
ValueError: max() iterable argument is empty
```

`map` 은 한 번 소진되면 비어 있다. 두 번 볼 값이면 `list(map(...))` 로 받아라([1.18](#/iterators)).

## 시간 초과는 기울기로 진단한다

`틀렸습니다` 와 `시간 초과` 는 다른 신호다. 시간 초과는 **어느 줄이 틀렸는가**가 아니라 **어느 줄이 비싼가**를 묻는다. 그리고 이건 눈으로 읽어서 알아내는 게 아니라 재서 알아내는 것이다.

시험장에서는 프로파일러를 붙일 여유가 없다([5.1](#/profiling)). 대신 **입력을 두 배씩 늘려 시간의 배수를 본다.** 복잡도를 추측하는 대신 관측한다.

```python title="slope.py — 시험장에서 쓰는 12줄"
import time


def slope(fn, make, sizes):
    prev = None
    for n in sizes:
        data = make(n)
        t = time.perf_counter()
        fn(data)
        dt = time.perf_counter() - t
        print(f"  n={n:6d}  {dt * 1000:8.1f} ms"
              + ("" if prev is None else f"   x{dt / prev:.1f}"))
        prev = dt
```

회원별 집계를 두 방식으로 짜서 재 본다. 하나는 이름 목록을 리스트에 담고 `in` 과 `.index()` 로 찾는다. 하나는 딕셔너리를 쓴다. 답은 같다.

```python title="slope.py 에 이어 붙인다 — 두 집계와 데이터 생성기"
import random

# fee 는 고친 버전(days - 7)이다. 위 overdue.py 에서 가져온다.


def make(n, pool=None):
    """(이름, 연체일) n행. 이름 후보는 pool 개, 기본은 n개다."""
    rnd = random.Random(0)
    pool = n if pool is None else pool
    return [(f"m{rnd.randrange(pool):06d}", rnd.randint(0, 40)) for _ in range(n)]


def by_list(rows):
    names, sums = [], []
    for name, days in rows:
        if name in names:                            # O(len(names))
            sums[names.index(name)] += fee(days)     # 한 번 더 O(len(names))
        else:
            names.append(name)
            sums.append(fee(days))
    return dict(zip(names, sums))


def by_dict(rows):
    total = {}
    for name, days in rows:
        total[name] = total.get(name, 0) + fee(days)
    return total


assert by_list(make(2000)) == by_dict(make(2000))    # 답이 같은 것부터 확인한다
print("리스트로 찾기")
slope(by_list, make, [2500, 5000, 10000, 20000])
print("딕셔너리로 찾기")
slope(by_dict, make, [2500, 5000, 10000, 20000, 40000, 80000])
```

```text nolines
리스트로 찾기
  n=  2500      39.2 ms
  n=  5000     155.8 ms   x4.0
  n= 10000     621.5 ms   x4.0
  n= 20000    2501.1 ms   x4.0
딕셔너리로 찾기
  n=  2500       0.5 ms
  n=  5000       1.1 ms   x2.1
  n= 10000       2.1 ms   x2.0
  n= 20000       5.0 ms   x2.4
  n= 40000      11.2 ms   x2.2
  n= 80000      29.7 ms   x2.7
```

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**배수만 보면 된다.** 4에 붙어 있으면 이차, 2에 붙어 있으면 선형에 가깝다. 리스트 버전은 $n$ 을 10배 늘리면 100배가 되고, 제한이 $2 \times 10^5$ 이면 절대 통과하지 못한다. 위 표에서 이미 $n = 20{,}000$ 에 2.5초다.

이 방법의 진짜 값어치는 **최대 크기까지 안 가도 판정된다**는 것이다. 20만 개로 돌려서 4분을 기다릴 필요가 없다 — 실제로 끝까지 재 보면 리스트 버전은 $n = 80{,}000$ 에 41 ~ 43초(x4.1)고, 이차니까 20만은 그 6.25배인 260초쯤이다. 2,500에서 20,000까지 네 번 재는 데는 3.4초가 들고, 결론은 똑같다.

::: perf 배수를 어디까지 신뢰할 수 있는가
같은 `make`, 같은 두 함수를 `timeit` 으로 다시 잡은 것이다. 이름 후보가 n개라 서로 다른 이름은 n의 63% 남짓 나온다(n=20,000 에서 12,668개).

| n | 리스트로 찾기 | 배수 | 딕셔너리로 찾기 | 배수 |
| --- | --- | --- | --- | --- |
| 2,500 | 38.3 ~ 42.1 ms | | 0.43 ~ 0.52 ms | |
| 5,000 | 153 ~ 163 ms | 4.0 | 0.93 ~ 1.06 ms | 2.1 |
| 10,000 | 624 ~ 643 ms | 4.1 | 1.91 ~ 2.26 ms | 2.1 |
| 20,000 | 2,487 ~ 2,531 ms | 4.0 | 4.24 ~ 4.58 ms | 2.2 |

(Python 3.14.0rc2 / Linux 기준 실측. `timeit.repeat(number=1, repeat=5)` / `repeat=9` 의 최솟값과 최댓값이고, 배수는 최솟값끼리의 비율. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

배수를 읽는 기준은 이렇다.

| 관측 배수 | 판단 |
| --- | --- |
| 1.9 ~ 2.8 | 선형에 가깝다. 이 크기에서는 문제없다 |
| 3.5 ~ 4.5 | 이차. n을 10배 늘리면 100배 |
| 7 이상 | 삼차 이상이거나 지수 |

**$O(n)$ 과 $O(n \log n)$ 은 이 방법으로 구별되지 않는다.** 난수 float 리스트를 `sorted` 하는 시간은 $n$ 을 100,000 → 200,000 → 400,000 → 800,000 으로 두 배씩 늘릴 때 2.1 ~ 2.5배가 되는데(같은 조건으로 세 번 측정한 범위), 위 딕셔너리 집계의 2.1 ~ 2.2와 그대로 겹친다. 그런데 시험장에서 그 구분은 필요 없다. **가려야 하는 것은 2 근처와 4 근처다**([7.1](#/complexity)).
:::

::: danger 데이터의 중복도가 기울기를 바꾼다
위 리스트 버전에서 이름이 서로 다를수록 `names` 가 길어지고 `in` 이 비싸진다. 그래서 **같은 코드가 데이터에 따라 기울기를 바꾼다.** `make(n, pool=100)` 으로 이름 후보를 100개로 고정하면 이렇게 된다.

| n | 이름 후보 n개 | 이름 후보 100개 |
| --- | --- | --- |
| 2,500 | 38.3 ~ 42.1 ms | 4.7 ~ 4.9 ms |
| 5,000 | 153 ~ 163 ms | 9.5 ~ 9.7 ms |
| 10,000 | 624 ~ 643 ms | 19.3 ~ 19.9 ms |
| 20,000 | 2,487 ~ 2,531 ms | 39.5 ~ 40.9 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 두 열 모두 위 표와 같은 실행에서 `timeit.repeat(number=1, repeat=5)` 로 나온 값이다.)

오른쪽 열은 **2배씩 늘어난다.** 이름이 100개뿐이면 `names` 가 100에서 멈추므로 사실상 선형이다. 예제와 비슷한 데이터로만 재면 이 코드는 무죄로 나온다. **기울기를 잴 때는 최악 모양을 만들어야 한다** — 여기서는 "값이 전부 서로 다른" 입력이다([8.3](#/tle)).
:::

## 제출 전 90초 점검

[11.8](#/function-completion)의 검증 루틴은 **함수 완성형의 반환값**을 겨눈다. 이 목록은 다르다. **디버깅하다가 만들어 놓은 것들이 제출물에 남아 있는지**를 본다. 채점 직전 90초에 이것만 본다.

::: cote 제출 전 90초 — 여섯 줄
```text nolines
  1. 디버그 출력    dbg / print 가 stdout 으로 나가지 않는가. DEBUG = False 인가
  2. 무거운 assert  루프 안에 O(n) 검사가 남아 있지 않은가
  3. 하드코딩       고치면서 박아 둔 상수, 축소 반례가 코드에 남아 있지 않은가
  4. 두 번 호출     solve(EX) 를 두 번 불러 같은 답이 나오는가
  5. 퇴화 입력      N=1, 전부 같은 값, 최솟값만 있는 입력을 돌렸는가
  6. 출력 형식      공백·개행·정렬 순서가 지문과 같은가
```

1~3번은 **디버깅이 만든 부채**다. 이 절의 도구를 쓸수록 이 세 줄이 중요해진다. `stderr` 로 찍는 습관과 `DEBUG` 스위치가 1번을 거의 공짜로 만든다. 4번은 한 줄이면서 상태 누출 전체를 덮고, 6번은 [8.2](#/io-optimize)의 영역이다.

시간이 정말 없으면 순서는 **1 → 4 → 6** 이다. 남겨 둔 출력과 형식 오류는 알고리즘이 맞아도 0점을 만든다.
:::

::: tip 고친 뒤에 반드시 하는 한 가지
버그를 고쳤으면 원래 반례를 다시 돌리고, **예제도 다시 돌려라.** 두 번째를 빼먹는 사람이 많다. 경계를 고치면서 정상 경로를 깨뜨리는 일이 흔하다.

축소된 반례는 지우지 말고 검증 목록에 넣어라. 시험장에서 만든 반례 목록이 그 문제의 테스트 스위트다. 과제형에서는 이 목록이 그대로 `tests/` 가 된다([12.6](#/test-strategy)).
:::

## 요약

- **채점 결과에는 줄 번호가 없다.** 필요한 것은 눈썰미가 아니라 절차다. **재현 → 분리 → 축소 → 설명 → 수정.** 4단계를 못 하면 5단계를 하지 마라 — 설명 없는 수정은 버그를 옮길 뿐이다.
- **예제 통과는 정보가 거의 없다.** 예제는 정상 경로 한 줄기만 덮는다. 통과한 직후 물어야 할 것은 "예제가 안 덮은 입력 공간이 어디인가"다.
- 디버깅은 앞 절들의 **역방향**이다. 증상이 후보를 가리킨다. 두 번째 케이스부터 틀리면 함수 밖의 상태, 실행마다 답이 다르면 `set`/`dict` 순서, 입력 순서에 답이 흔들리면 동점 규칙 누락이다.
- `print` 는 **파싱 직후 / 단계 사이 / 반환 직전** 세 자리에만, 요약 한 줄씩. **`file=sys.stderr` 로 찍고 답을 고른 근거를 함께 찍어라.** 루프마다 찍으면 20만 회에서 8 ms 가 300 ms 가 된다(실측).
- `assert` 로 단계 경계에 불변식을 박아라. **파싱 결과의 개수, 집계의 합계 보존, 선택의 최댓값.** 단 $O(n)$ 검사를 루프 안에 두면 $O(n)$ 이 $O(n^2)$ 이 된다 — 20,000개에서 4.2 ms 가 2.0초였다.
- **반례를 찾는 것으로 끝내지 말고 줄여라.** 줄 삭제와 값 반감, 두 이동만으로 여섯 줄 반례가 `[('c', 8)]` 한 줄이 됐다. 대조군을 못 짜겠으면 **정답을 모르고도 쓸 수 있는 성질**을 써라 — 순서 뒤집기 하나가 무작위 2,000건 중 47건에서 버그를 드러냈다.
- 시간 초과는 읽지 말고 **재라.** 입력을 두 배씩 늘려 배수를 본다. **2 근처면 선형, 4 근처면 이차.** 기울기는 데이터 모양에 따라 바뀌니 최악 모양으로 재야 한다. 그리고 제출 전 90초는 **디버깅이 만든 부채**를 본다 — 남은 디버그 출력, 무거운 `assert`, 하드코딩.

::: quiz 코드 과제 — 도구를 만들어서 손에 붙여라
전부 실제로 짜서 돌려라. 읽고 넘기면 이 절은 아무 일도 하지 않는다.

**1. 축소기를 문자열 입력용으로 다시 짜라 (15분)**

좌석 예약 로그를 처리하는 문제다. 입력은 한 줄에 하나씩 `"B 좌석번호"`(예약) 또는 `"C 좌석번호"`(취소)이고, 이미 예약된 좌석을 다시 예약하거나 비어 있는 좌석을 취소하는 요청은 **무시**한다. 마지막에 예약된 좌석 번호를 오름차순으로 출력한다.

일부러 버그가 있는 구현과 규칙 그대로 옮긴 느린 구현을 둘 다 짜고, 무작위 로그로 반례를 찾은 뒤 축소해라. 이동 집합은 **① 줄 삭제 ② 좌석 번호를 더 작은 수로** 두 개다. 축소 전과 후의 줄 수를 함께 출력해라.

**2. 오라클 없는 검사를 한 함수로 (15분)**

`solve(rows)` 를 받아 다음을 검사하는 `sanity(solve, gen, trials=2000)` 를 짜라.

```text nolines
(a) 순서 불변    solve(rows) == solve(shuffled(rows))
(b) 두 번 호출    solve(rows) == solve(rows)
(c) 재현성       같은 입력에 대해 프로세스를 다시 띄워도 같은 답
```

(c)는 한 프로세스 안에서 확인할 수 없다. **왜 그런지 적고**, 대신 무엇을 검사하면 근사할 수 있는지 정해서 구현해라. 그리고 1번의 버그 구현을 `sanity` 에 통과시켜 몇 건이 걸리는지 세라.

**3. 기울기 측정기 (10분)**

본문의 `slope` 를 짜고, 다음 세 함수로 검증해라. 각각의 배수가 무엇에 수렴하는지 표로 적어라.

```text nolines
(a) sum(data)                              기대: 2 근처
(b) sorted(data)                           기대: 2 근처 (선형과 구별 안 된다)
(c) [x for x in data if data.count(x) > 1]  기대: 4 근처
```

(b)와 (a)의 배수가 겹치는 것을 **직접 확인하고**, 그럼에도 이 도구가 쓸 만한 이유를 한 문장으로 적어라.

**4. 파싱 함정 재현 (10분)**

다음 다섯 가지를 각각 재현하고 **정확한 예외 메시지 또는 잘못된 결과값을 기록**해라.

```text nolines
(a) split("\n") 의 마지막 빈 줄로 언패킹이 터진다
(b) split(" ") 이 개행을 남겨서 문자열 비교가 False 가 된다
(c) map 을 두 번 순회한다
(d) 첫 줄의 N 을 무시하고 전부 순회해서 뒤에 붙은 잉여 줄까지 먹는다
(e) 한 줄에 세 값이 오는데 둘로 언패킹한다
```

그다음 이 다섯 개를 **모두 막는 `parse` 함수 하나**를 짜라. 막는 방법은 `assert` 여야 한다 — `try/except` 로 숨기지 마라. 왜 여기서 예외를 삼키면 안 되는지 한 문장으로 적어라([12.5](#/error-design)).

**5. 잔여물 검출기 (15분)**

제출 직전 1번 항목을 자동화해라. `check_clean(solve, sample_input, expected_lines)` 는 `contextlib.redirect_stdout` 으로 `stdout` 을 잡아서 **줄 수가 `expected_lines` 와 다르면 무엇이 더 나왔는지 보고**한다.

일부러 `print("여기 도달")` 을 남긴 `solve` 로 검출되는 것을 확인하고, `stderr` 로 바꾸면 검출되지 않는 것도 확인해라. 그다음 `DEBUG = False` 로 껐을 때 성능이 실제로 돌아오는지 `slope` 로 재라.

**6. 확장 과제 — 두 버그를 한 번에**

본문의 `overdue_bug.py` 를 그대로 옮겨 적고, **버그 두 개를 한 번의 실행으로 모두 찾아내는 검증 스크립트**를 짜라. 요구사항은 셋이다.

```text nolines
(a) fee 의 경계를 0~100 전 구간에서 fee_slow 와 대조한다
(b) 순서 뒤집기로 동점 버그를 잡는다
(c) 두 버그를 각각 최소 반례까지 축소해서 출력한다
```

그리고 이 스크립트를 짜는 데 걸린 시간을 재라. **두 번째 문제에서 이 시간이 절반 이하가 되어야 한다.** 검증 스크립트는 문제마다 새로 짜는 것이 아니라 갈아 끼우는 것이다.
:::

**다음 절**: [12.1 과제형 문제가 진짜 평가하는 것](#/takehome-eval) — 정답이 하나가 아닌 문제에서, 채점자가 첫 5분에 실제로 보는 것.
