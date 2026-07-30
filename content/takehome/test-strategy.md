# 12.6 테스트 전략 — 무엇을 얼마나

::: lead
과제형 제출물에서 테스트는 **있냐 없냐**로 갈리지 않는다. 요즘은 거의 다 있다. 갈리는 건 **무엇을 테스트했는가**다. 어떤 사람은 47개를 내고 커버리지 100%를 찍고도 "이 사람은 자기 코드가 무슨 규칙을 지켜야 하는지 모른다"는 평가를 받는다. 어떤 사람은 20개로 명세 전체를 못 박는다. 이 절은 그 차이를 만드는 판단을 다룬다. pytest 사용법 자체는 [6.1 pytest](#/pytest)와 [6.2 fixture, 파라미터화, mocking](#/pytest-advanced)에 있다. 여기서는 문법을 한 줄도 새로 가르치지 않는다. **무엇을 쓸지, 그리고 무엇을 쓰지 않을지**만 정한다.
:::

## 47개가 20개보다 낮게 평가되는 이유

이 절 내내 쓸 과제다. [12.4](#/boundaries-di)에서 시계 이야기를 하며 잠깐 나왔던 그 소재다.

> **[과제] 상가 주차장 정산기**
>
> 1. 차량이 입차하면 번호판과 입차 시각을 기록한다. 주차면은 N면이고, **만차면 입차를 거부한다.**
> 2. **30분 이하는 무료.** 초과하면 최초 1시간까지 1,000원, 그 뒤로는 **10분마다 500원**(10분 미만은 올림).
> 3. **하루(24시간) 요금은 15,000원을 넘지 않는다.**
> 4. 제휴 상점 도장 1개당 **30분이 할인**되고, 도장은 **최대 2개**까지 인정한다.
> 5. **정산한 차량만 출차할 수 있다.** 정산 후 15분이 지나면 다시 정산해야 한다.
> 6. 같은 번호판이 이미 주차 중이면 입차를 거부한다. 주차 기록이 없는 번호판은 정산도 출차도 거부한다.

두 사람이 제출했다.

**A.** 테스트 47개. `pytest --cov` 가 100%를 찍는다. 열어 보면 `Ticket` 의 각 필드를 하나씩 읽는 테스트, 생성자에 넣은 값이 그대로 들어갔는지 확인하는 테스트, `fee()` 가 `int` 를 반환하는지 보는 테스트가 20개 가까이 된다. 요구사항 2번의 요금 구간은 `fee(100) == 3000` 하나로 끝났다. 요구사항 5번의 "정산 후 15분"은 테스트가 없다.

**B.** 테스트 20개. 커버리지는 재지도 않았다. 요구사항 여섯 문장이 테스트 이름 목록에 그대로 보인다. 30분·60분·70분 같은 **경계**가 케이스로 나열돼 있고, 거부되는 경우마다 **거부된 뒤 상태가 멀쩡한지**까지 확인한다.

평가자는 B를 고른다. A의 47개 중 절반은 **깨질 수가 없는 테스트**이기 때문이다. 깨질 수 없는 테스트는 정보를 주지 않는다. 정보를 주지 않는 코드가 수백 줄 있으면 읽는 사람의 시간만 쓴다.

그래서 이 절은 **더할 것이 아니라 뺄 것부터** 정한다.

## 먼저 지운다 — 테스트하지 않을 것

아래 넷은 실제로 통과한다. 그리고 넷 다 지워야 한다.

```python title="junk/test_useless.py — 전부 통과하고, 전부 무의미하다"
from parking.fees import fee
from parking.lot import ParkingLot, Ticket


def test_ticket_equality():
    assert Ticket("11A1111", 0) == Ticket("11A1111", 0)


def test_ticket_stores_what_it_was_given():
    t = Ticket("11A1111", 10)
    assert t.plate == "11A1111"
    assert t.entered_at == 10
    assert t.stamps == 0


def test_fee_returns_int():
    assert isinstance(fee(100), int)


def test_new_lot_is_empty():
    assert ParkingLot(capacity=5).free_spaces == 5
```

```text nolines
$ pytest -q
....                                                                     [100%]
4 passed in 0.01s
```

하나씩 무엇을 검증하고 있는지 보자.

| 테스트 | 실제로 검증하는 것 | 누가 이미 보장하나 |
| --- | --- | --- |
| `test_ticket_equality` | `@dataclass` 가 `__eq__` 를 만든다 | CPython과 표준 라이브러리 ([2.6](#/dataclasses)) |
| `test_ticket_stores_what_it_was_given` | 대입문이 동작한다 | 언어 |
| `test_fee_returns_int` | `int` 끼리 더하면 `int` 다 | 언어 |
| `test_new_lot_is_empty` | 뺄셈이 동작한다 | 언어 |

**요구사항 문장 중 하나라도 이 테스트들과 연결되는 것이 있는가.** 없다. 여섯 문장 어디에도 "티켓 두 개가 같으면 같아야 한다"는 말이 없다.

::: danger 무의미한 테스트가 커버리지를 만든다
이 네 개만 돌려서 커버리지를 재 봤다.

```text nolines
$ pytest -q junk --cov=parking --cov-branch
....                                                                     [100%]
================================ tests coverage ================================
_____________ coverage: platform linux, python 3.14.0-candidate-2 ______________

Name                  Stmts   Miss Branch BrPart  Cover
-------------------------------------------------------
parking/__init__.py       0      0      0      0   100%
parking/errors.py         5      0      0      0   100%
parking/fees.py          19      3      6      3    76%
parking/lot.py           46     23      8      0    43%
-------------------------------------------------------
TOTAL                    70     26     14      3    56%
4 passed in 0.05s
```

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**규칙을 하나도 검증하지 않은 네 개의 테스트가 56%를 만든다.** 커버리지를 목표로 삼으면 사람은 정확히 이런 테스트를 쓰게 된다. 규칙을 파고드는 것보다 훨씬 쉽고 숫자는 더 빨리 오르기 때문이다.
:::

::: tip 지울지 남길지 가르는 한 문장
**"이 assert 가 깨지려면 무엇이 잘못돼야 하는가?"** 에 답해 봐라.

- "내가 `fee()` 의 구간 조건을 잘못 쓰면" → 남긴다.
- "파이썬이 고장 나면", "`@dataclass` 가 고장 나면" → 지운다.

답이 **당신이 작성한 규칙**이면 남기고, **언어·표준 라이브러리·서드파티**면 지운다. 남의 코드를 테스트하는 것은 당신의 일이 아니다.
:::

## 요구사항 문장이 테스트 목록이다

지웠으면 이제 채운다. 채우는 순서는 요구사항 문장 순서다. **문장 하나에 최소 테스트 하나.** 이게 전부다.

문장을 읽고 세 갈래로 나눈다.

```text nolines
  requirement sentence
        |
        +-- 값을 계산하는가?   ->  boundary table + parametrize
        +-- 상태를 바꾸는가?   ->  allowed transition 1 + forbidden transition 1
        +-- 무언가를 막는가?   ->  raises + state after the failure
        +-- none of the above  ->  do not write a test
```

주차장 과제의 여섯 문장을 이 표로 옮기면 이렇게 된다. 실제로 제출한 20개다.

| 요구사항 | 갈래 | 테스트 | 수 |
| --- | --- | --- | --- |
| 1. 만차 거부 | 막는다 | `test_full_lot_rejects_entry` | 1 |
| 2. 요금 구간 | 계산 | `test_fee_at_each_rate_boundary` (7 케이스) | 7 |
| 3. 일 상한 | 계산 | `test_fee_stops_growing_at_the_daily_cap`, `test_second_day_starts_a_new_cap`, `test_free_grace_applies_again_on_the_second_day` | 3 |
| 4. 도장 할인 | 계산 | `test_a_stamp_discounts_thirty_minutes`, `test_stamps_are_capped_at_two` | 2 |
| 5. 정산·출차 | 상태 | `test_leaving_returns_the_space_and_the_ticket`, `test_leaving_without_settling_is_rejected_and_keeps_the_ticket`, `test_settlement_expires_after_the_exit_window`, `test_leaving_one_minute_past_the_window_requires_re_settlement` | 4 |
| 6. 중복·미등록 | 막는다 | `test_same_plate_cannot_enter_twice`, `test_unknown_plate_is_rejected_everywhere` | 2 |
| (방어) 음수 시간 | 막는다 | `test_negative_duration_is_rejected` | 1 |

**요구사항 칸이 비어 있는 테스트는 없다.** 반대로 테스트 칸이 비어 있는 요구사항도 없다. 이 표를 README에 그대로 붙이면([12.8](#/readme-submit)) 평가자는 명세 충족 여부를 코드를 읽기 전에 확인한다.

::: note 이 표를 진짜로 그려야 하나
과제형에서는 **머릿속으로 그려도 된다.** 다만 마지막 30분에 요구사항 문장을 하나씩 짚으며 "이 문장의 테스트가 어느 것인가"를 소리 내어 확인해라. 여기서 빠진 문장이 나오는 일이 굉장히 흔하다. 특히 **요구사항 문장 안에 조건절로 숨어 있는 규칙**(3번의 "24시간", 5번의 "15분")이 잘 빠진다.
:::

## 테스트 이름이 명세다

같은 검증을 이름만 바꿔 보자.

```python
# ❌ 무엇을 보장하는지 알 수 없다
def test_leave1(): ...
def test_leave2(): ...
def test_edge_case(): ...
def test_bug_fix_2(): ...

# ✅ 이름만 읽어도 규칙이 보인다
def test_leaving_returns_the_space_and_the_ticket(): ...
def test_leaving_without_settling_is_rejected_and_keeps_the_ticket(): ...
def test_settlement_expires_after_the_exit_window(): ...
def test_leaving_one_minute_past_the_window_requires_re_settlement(): ...
```

이름을 이렇게 지으면 부수 효과가 하나 생긴다. **테스트 목록이 그대로 명세서가 된다.**

```text nolines
$ pytest -q --collect-only tests/test_lot.py
tests/test_lot.py::test_leaving_returns_the_space_and_the_ticket
tests/test_lot.py::test_full_lot_rejects_entry
tests/test_lot.py::test_same_plate_cannot_enter_twice
tests/test_lot.py::test_leaving_without_settling_is_rejected_and_keeps_the_ticket
tests/test_lot.py::test_settlement_expires_after_the_exit_window
tests/test_lot.py::test_leaving_one_minute_past_the_window_requires_re_settlement
tests/test_lot.py::test_a_stamp_discounts_thirty_minutes
tests/test_lot.py::test_stamps_are_capped_at_two
tests/test_lot.py::test_unknown_plate_is_rejected_everywhere

9 tests collected in 0.01s
```

평가자가 이 아홉 줄을 보고 나면 `lot.py` 를 읽는 속도가 달라진다. 무엇을 찾을지 알고 읽기 때문이다.

::: tip 이름 짓는 틀
`test_<주어>_<동사>_<조건>` 이다. **주어는 시스템, 동사는 시스템이 하는 일, 조건은 언제.**

- `test_full_lot_rejects_entry` — 주어 `full lot`, 동사 `rejects`, 대상 `entry`.
- `test_stamps_are_capped_at_two` — 주어 `stamps`, 동사 `are capped`, 조건 `at two`.

이름이 30자를 넘어도 괜찮다. **테스트 이름은 호출되지 않는다.** 짧게 줄여서 얻는 것이 없다. 반대로 이름이 `and` 로 두 번 이상 이어지면 테스트가 두 개여야 한다는 신호다.
:::

### given-when-then은 빈 줄 두 개다

프레임워크가 필요한 이야기가 아니다. **본문을 빈 줄로 세 덩이로 나누면 끝난다.**

```python title="tests/test_lot.py"
def test_leaving_returns_the_space_and_the_ticket():
    lot = ParkingLot(capacity=2)                # given
    lot.enter("11A1111", at=0)
    lot.settle("11A1111", at=100)

    lot.leave("11A1111", at=105)                # when

    assert lot.free_spaces == 2                 # then: 자리가 돌아왔고
    with pytest.raises(NotParked):              # 티켓은 사라졌고
        lot.settle("11A1111", at=110)
    lot.enter("11A1111", at=200)                # 같은 차가 다시 들어올 수 있다
```

가운데 덩이가 **한 줄**인 것이 핵심이다. `when` 이 세 줄이면 무엇이 결과를 만들었는지 특정할 수 없다. 위 예제에서 실제로 `# given` `# when` 주석은 없어도 된다 — 빈 줄만으로 이미 읽힌다.

::: note AAA와 given-when-then은 같은 것이다
Arrange–Act–Assert 라고도 부른다. 이름만 다르다. 굳이 주석으로 `# Arrange` 를 세 줄 박아 넣지 마라. 과제형 평가자는 **구조가 보이는지**를 보지, 유행어를 아는지를 보지 않는다.
:::

## `assert` 를 여러 개 쓰는 이유

"테스트 하나에 `assert` 하나"라는 말을 어디선가 들었을 것이다. 그 규칙의 원문은 **개념 하나**(one concept per test)지 `assert` 하나가 아니다. 그리고 이 둘은 다르다.

`leave()` 는 **한 번의 호출로 세 가지를 바꾼다.** 자리를 돌려주고, 티켓을 지우고, 그 번호판을 다시 받을 수 있게 만든다. 셋 중 하나만 확인하면 나머지 둘은 안 해도 통과한다. 그래서 위 테스트의 `assert` 는 세 개다. **개념은 여전히 하나 — "출차가 끝났다"이다.**

반대로 이렇게 묶으면 안 된다.

```python title="demo/test_lumped.py — 관계없는 규칙 세 개를 한 테스트에"
def test_parking_lot():
    lot = ParkingLot(capacity=1)
    lot.enter("11A1111", at=0)
    assert lot.free_spaces == 0

    with pytest.raises(LotFull):
        lot.enter("22B2222", at=1)

    lot.settle("11A1111", at=100)
    lot.leave("11A1111", at=105)
    assert lot.free_spaces == 1
```

버그가 **두 개**(만차 판정과 출차 처리) 심어진 구현으로 돌려 봤다.

```text nolines
$ pytest -q --tb=no test_lumped.py
F                                                                        [100%]
=========================== short test summary info ============================
FAILED test_lumped.py::test_parking_lot - Failed: DID NOT RAISE LotFull
1 failed in 0.01s
```

**보고된 버그는 하나다.** 만차 판정에서 멈췄으니 출차 쪽은 실행조차 안 됐다. 고치고 다시 돌려야 두 번째 버그를 알게 된다.

같은 구현, 같은 검증을 세 개로 쪼개면 이렇게 나온다.

```text nolines
$ pytest -q --tb=no test_split.py
.FF                                                                      [100%]
=========================== short test summary info ============================
FAILED test_split.py::test_full_lot_rejects_entry - Failed: DID NOT RAISE Lot...
FAILED test_split.py::test_leaving_returns_the_space - assert 0 == 1
2 failed, 1 passed in 0.01s
```

**한 번 돌려서 두 개를 다 안다.** 그리고 이름만 읽어도 어느 규칙이 깨졌는지 안다.

::: warn 판단 기준 한 줄
**같은 `when` 의 결과면 `assert` 를 붙이고, `when` 이 달라지면 테스트를 쪼개라.**

`when` 이 두 개인데 한 테스트에 있다는 것은, 첫 번째가 실패하면 두 번째 규칙에 대해 **아무 정보도 얻지 못한다**는 뜻이다. 테스트를 돌리는 이유가 정보를 얻는 것이므로, 이건 손해다.
:::

## 경계값 — 요금표는 경계의 목록이다

요구사항 2번을 다시 읽어라. *"30분 이하는 무료. 초과하면 최초 1시간까지 1,000원, 그 뒤로는 10분마다 500원."*

이 한 문장에 **구간 경계가 두 개**(30분, 60분)와 **올림 규칙 하나**가 들어 있다. 셋 다 부등호로 구현된다. 그리고 과제형 제출물에서 실제로 깨지는 곳은 언제나 부등호다. 구간 안쪽 값(`fee(45)`)은 웬만하면 맞는다. 틀리는 건 `fee(30)` 과 `fee(31)` 이다.

경계를 뽑는 절차는 기계적이다. **구간마다 마지막 값과 다음 구간의 첫 값을 적는다.**

```pyrepl
>>> from parking.fees import fee
>>> [fee(m) for m in (29, 30, 31)]
[0, 0, 1000]
>>> [fee(m) for m in (60, 61, 70, 71)]
[1000, 1500, 1500, 2000]
>>> fee(330), fee(331), fee(400)
(14500, 15000, 15000)
>>> fee(1440), fee(1441), fee(1471)
(15000, 15000, 16000)
```

`fee(61)` 이 1,500원인 것을 보라. 1분을 초과했는데 한 단위(500원)를 다 낸다. **"10분 미만은 올림"이 여기서 처음 눈에 보인다.** 이런 건 코드를 아무리 들여다봐도 안 보이고, 값을 찍어 봐야 보인다.

이제 이걸 테스트로 옮긴다.

```python title="tests/test_fees.py"
@pytest.mark.parametrize(
    "minutes, expected",
    [
        (0, 0),
        (30, 0),          # 무료 구간의 마지막 분
        (31, 1_000),      # 유료가 시작되는 첫 분
        (60, 1_000),      # 기본요금의 마지막 분
        (61, 1_500),      # 10분 단위가 시작되는 첫 분 (1분도 한 단위)
        (70, 1_500),      # 첫 단위의 마지막 분
        (71, 2_000),      # 두 번째 단위
    ],
)
def test_fee_at_each_rate_boundary(minutes, expected):
    assert fee(minutes) == expected


def test_fee_stops_growing_at_the_daily_cap():
    assert fee(330) == 14_500
    assert fee(331) == 15_000
    assert fee(400) == 15_000
    assert fee(1_439) == 15_000
```

::: warn 두 안이 갈리는 지점 — parametrize 인가, 개별 테스트인가
위 파일에는 두 방식이 나란히 있다. 일부러 그랬다. 부등호를 두 군데 망가뜨린 구현으로 돌려 보면 차이가 드러난다.

```text nolines
$ pytest -q tests/test_fees.py --tb=no
.F..F.FF...                                                              [100%]
=========================== short test summary info ============================
FAILED tests/test_fees.py::test_fee_at_each_rate_boundary[30-0] - assert 1000...
FAILED tests/test_fees.py::test_fee_at_each_rate_boundary[61-1500] - assert 1...
FAILED tests/test_fees.py::test_fee_at_each_rate_boundary[71-2000] - assert 1...
FAILED tests/test_fees.py::test_fee_stops_growing_at_the_daily_cap - assert 1...
4 failed, 7 passed in 0.02s
```

파라미터화한 쪽은 **깨진 경계 세 개를 각각 이름으로 보고한다.** `[30-0]` 은 "30분일 때 0원이어야 하는데 아니다"라고 읽힌다. 상한 테스트는 `fee(331)` 에서 멈춰서 `fee(400)`, `fee(1439)` 는 확인조차 안 됐다.

| | `parametrize` | 개별 `assert` 나열 |
| --- | --- | --- |
| 실패 보고 | 케이스마다 따로, ID로 식별 | 첫 실패에서 멈춤 |
| 케이스 추가 | 튜플 한 줄 | 줄 한 개 |
| 케이스에 이유 달기 | 주석 또는 `pytest.param(id=...)` | 주석 |
| 읽기 | 표로 보인다 | 흐름으로 보인다 |

**값이 표로 주어진 규칙(요금표, 등급표, 환율)은 `parametrize` 가 낫다.** 표를 코드로 옮긴 모양이 그대로 보이기 때문이다. **한 규칙이 여러 값에서 "같은 방향으로" 성립함을 보이는 경우**(상한은 그 뒤로 계속 15,000원이다)는 나열이 낫다. 케이스마다 이름을 붙일 것이 없기 때문이다.

케이스가 3개 이하면 `parametrize` 로 얻는 게 없다. 그냥 나열해라.
:::

::: cote 경계값 감각은 코딩테스트에서 더 자주 쓰인다
`<` 와 `<=`, `n` 과 `n-1` 은 알고리즘 문제에서 틀리는 1순위다([11.14](#/exam-debug)). 다른 점은 코딩테스트에서는 채점 서버가 대신 잡아 준다는 것뿐이고, 과제형에서는 **당신이 그 채점 서버를 직접 짜야 한다.** 경계값 목록을 만드는 습관은 두 곳 다에서 같은 값을 한다.
:::

## 실패 경로에서 갈린다

성공 경로만 있는 테스트 스위트는 **절반짜리 명세**다. 요구사항 1·5·6번은 전부 "거부한다"는 문장이고, 거부되는 것은 성공 경로를 아무리 돌려도 확인되지 않는다.

그런데 여기서 한 단계가 더 있다. 대부분의 지원자는 여기까지 쓴다.

```python
def test_leaving_without_settling_is_rejected():        # 절반
    lot = ParkingLot(capacity=1)
    lot.enter("11A1111", at=0)
    with pytest.raises(NotSettled):
        lot.leave("11A1111", at=40)
```

예외가 났다는 것만 확인했다. **예외가 난 뒤 시스템이 어떤 상태인지는 아무도 안 물어봤다.** 실제로 여기서 사고가 난다 — 자리를 먼저 비우고 검사를 나중에 하는 구현이면, 이 테스트는 통과하는데 주차면 하나가 영원히 사라진다.

```python title="tests/test_lot.py — 실패 뒤의 상태까지 본다"
def test_leaving_without_settling_is_rejected_and_keeps_the_ticket():
    lot = ParkingLot(capacity=1)
    lot.enter("11A1111", at=0)

    with pytest.raises(NotSettled):
        lot.leave("11A1111", at=40)

    assert lot.free_spaces == 0                 # 자리가 반납되지 않았다
    lot.settle("11A1111", at=40)                # 정산하면 여전히 나갈 수 있다
    lot.leave("11A1111", at=41)
    assert lot.free_spaces == 1
```

::: danger 실패 테스트에서 반드시 확인할 세 가지
1. **예외 타입** — `pytest.raises(NotSettled)`. `Exception` 으로 잡으면 오타로 난 `NameError` 까지 통과한다.
2. **거부된 부작용** — 막기로 한 일이 진짜로 안 일어났는가. 자리가 그대로인가, 알림이 안 나갔는가.
3. **복구 가능성** — 실패 뒤에 정상 경로로 돌아갈 수 있는가. 위 테스트의 마지막 세 줄이 그것이다.

2번과 3번이 있는 제출물은 드물다. **드물기 때문에 눈에 띈다.** 예외 계층을 어떻게 설계하는지는 [12.5 예외와 오류 설계](#/error-design)와 [1.16 예외](#/exceptions)에 있다.
:::

### 명세가 안 정한 곳은 테스트로 못 박는다

요구사항 3번은 "하루 15,000원"이라고만 했다. 그럼 **24시간 1분을 주차하면 둘째 날에도 무료 30분을 다시 주는가?** 명세에 없다. 물어볼 사람도 없다.

이럴 때 하는 일은 셋 중 하나다. 아무거나 정하고 넘어가기, README에 질문으로 적기, 그리고 **테스트로 못 박기**. 셋째가 가장 강하다.

```python title="tests/test_fees.py"
def test_free_grace_applies_again_on_the_second_day():
    # 명세가 정하지 않은 부분. 이 구현은 하루 단위로 무료 30분을 다시 준다.
    assert fee(1_441) == 15_000
```

이 테스트가 하는 일은 검증이 아니라 **선언**이다. "나는 이렇게 해석했고, 다르게 바꾸려면 이 테스트를 고치면 된다"고 코드로 적어 둔 것이다. 평가자가 다르게 생각했더라도 감점하지 않는다 — **모호함을 발견했다는 사실 자체가 점수**이기 때문이다.

## 커버리지 숫자에 속지 않기

여기, 요구사항 2번을 구현한 함수가 있다. 부등호 하나가 틀렸다.

```python title="fees.py — 30분 '이하' 무료인데 < 를 썼다"
GRACE_MINUTES = 30
BASE_FEE = 1_000
UNIT_MINUTES = 10
UNIT_FEE = 500


def fee(minutes: int) -> int:
    if minutes < GRACE_MINUTES:          # 버그
        return 0
    if minutes <= 60:
        return BASE_FEE
    over = minutes - 60
    units = -(-over // UNIT_MINUTES)
    return BASE_FEE + units * UNIT_FEE
```

그리고 이 세 개의 테스트가 있다.

```python title="test_fees.py"
def test_short_stay_is_free():
    assert fee(10) == 0


def test_under_an_hour_costs_the_base_fee():
    assert fee(45) == 1_000


def test_over_an_hour_adds_ten_minute_units():
    assert fee(100) == 3_000
```

```text nolines
$ pytest -q --cov=fees --cov-branch
...                                                                      [100%]
================================ tests coverage ================================
_____________ coverage: platform linux, python 3.14.0-candidate-2 ______________

Name      Stmts   Miss Branch BrPart  Cover
-------------------------------------------
fees.py      12      0      4      0   100%
-------------------------------------------
TOTAL        12      0      4      0   100%
3 passed in 0.02s
```

**문장 커버리지 100%, 분기 커버리지도 100%.** 그런데 요구사항 2번이 틀렸다. 30분 주차한 차에게 1,000원을 받는다.

경계 케이스 하나를 추가하면 바로 드러난다. 그리고 **커버리지 숫자는 1%도 안 움직인다.**

```python title="test_boundary.py — 위 셋에 이 하나를 더했다"
def test_thirty_minutes_exactly_is_still_free():
    assert fee(30) == 0
```

```text nolines
$ pytest -q --tb=no --cov=fees --cov-branch
...F                                                                     [100%]
================================ tests coverage ================================
_____________ coverage: platform linux, python 3.14.0-candidate-2 ______________

Name      Stmts   Miss Branch BrPart  Cover
-------------------------------------------
fees.py      12      0      4      0   100%
-------------------------------------------
TOTAL        12      0      4      0   100%
=========================== short test summary info ============================
FAILED test_boundary.py::test_thirty_minutes_exactly_is_still_free - assert 1...
1 failed, 3 passed in 0.03s
```

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

커버리지가 답하는 질문은 딱 하나다 — **"이 줄이 한 번이라도 실행됐는가."** 그 줄이 **옳은 값을 냈는가**는 묻지 않는다. 부등호 버그, off-by-one, 잘못된 상수는 커버리지가 원리적으로 못 잡는다.

::: tip 커버리지의 올바른 사용법
**목표 숫자가 아니라 지도로 써라.** 보고서를 열어서 퍼센트가 아니라 **빨간 줄**을 봐라.

- 빨간 줄이 예외 처리부라면 → 실패 경로 테스트가 없다는 뜻이다. 채워라.
- 빨간 줄이 `if` 의 한쪽 가지라면 → 그 조건이 참인 경우를 아무도 안 만들어 봤다는 뜻이다.
- 빨간 줄이 "쓰지도 않는 기능"이라면 → 테스트가 아니라 **그 코드를 지워야 한다**([12.2](#/requirements-to-model)의 YAGNI).

과제형 README에 `커버리지 100%` 라고 적는 것은 권하지 않는다. 위 예시를 아는 평가자에게는 오히려 **숫자로 실력을 증명하려 했다**는 신호로 읽힌다. 대신 요구사항–테스트 대응표를 적어라.
:::

::: danger 테스트가 계산식을 베끼면 아무것도 검증하지 않는다
커버리지보다 더 조용히 망가지는 것이 이것이다.

```python title="test_mirror.py"
from fees import BASE_FEE, UNIT_FEE, UNIT_MINUTES, fee


def test_fee_matches_the_formula():          # 계산식을 테스트가 그대로 베꼈다
    minutes = 100
    expected = BASE_FEE + -(-(minutes - 60) // UNIT_MINUTES) * UNIT_FEE
    assert fee(minutes) == expected


def test_fee_at_the_first_unit():            # 명세에서 직접 계산한 값
    assert fee(70) == 1_500
```

단가를 500원이 아니라 **600원**으로 잘못 넣은 구현으로 돌렸다.

```text nolines
$ pytest -q --tb=no
.F                                                                       [100%]
=========================== short test summary info ============================
FAILED test_mirror.py::test_fee_at_the_first_unit - assert 1600 == 1500
1 failed, 1 passed in 0.01s
```

**첫 번째 테스트는 통과한다.** 구현과 테스트가 같은 상수, 같은 식을 쓰기 때문에 둘 다 틀려도 서로 같다. 이런 테스트는 리팩터링 방지턱 역할만 하고 **명세는 하나도 지키지 않는다.**

기대값은 **명세에서 사람이 손으로 계산해 하드코딩해라.** 테스트에서 구현 모듈의 상수를 import 하고 있다면 그때가 의심할 순간이다.
:::

## 얼마나 — 4시간짜리 과제에서의 배분

숫자로 못 박는다. 요구사항이 6~8문장인 전형적인 과제 기준이다.

| 대상 | 테스트 수 | 이유 |
| --- | --- | --- |
| 순수 계산 함수(요금, 점수, 변환) | 경계 개수만큼 | 가장 싸고 가장 많이 깨진다 |
| 상태 전이 | 규칙당 성공 1 + 금지 1 | 금지 전이가 진짜 규칙이다 |
| 거부 규칙 | 규칙당 1 (상태 검증 포함) | 요구사항 문장이 곧 테스트 |
| 전체 흐름(입차→정산→출차) | **1개** | 조립이 되는지만 본다 |
| getter, `__init__`, 프로퍼티 | **0개** | 위에서 지웠다 |

합치면 요구사항 문장 하나당 1~3개, 총 15~25개다. 그 위로 올라가기 시작하면 "지금 추가하려는 이 테스트가 어느 요구사항 문장인가"를 물어라. 답이 없으면 안 쓴다.

시간은 이렇게 쓴다.

| 구간 | 하는 일 |
| --- | --- |
| 처음 | 요구사항 문장에 번호를 매기고 갈래(계산·상태·거부)를 표시한다 |
| 다음 | **순수 계산부터** 짠다. 경계 목록을 먼저 적고 `parametrize` 로 테스트를 짠 뒤 구현한다 |
| 다음 | 상태·거부 규칙을 구현하고 규칙마다 테스트를 붙인다 |
| 마지막 | 전체 흐름 테스트 1개, 요구사항–테스트 대응 점검, README |

**순수 계산을 먼저 짜는 이유**는 그것이 의존성이 없어서 테스트가 가장 싸고, 요금 규칙처럼 **명세에서 가장 오해하기 쉬운 부분**이 거기 있기 때문이다. 외부 경계를 끊는 일은 [12.4](#/boundaries-di)에서 이미 했다고 가정한다 — 안 끊었다면 테스트를 짜기 전에 그것부터 해라.

::: perf 테스트가 느리면 안 돌리게 된다
위 20개 스위트를 반복 실행하고 pytest가 보고한 시간의 최소~최대를 적었다.

| 실행 | 시간 | 반복 |
| --- | --- | --- |
| `pytest -q` | 0.02 ~ 0.03 s | 5회 |
| `pytest -q --cov=parking --cov-branch` | 0.05 ~ 0.06 s | 3회 |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

이 스위트에는 `sleep` 도, 파일 I/O도, 네트워크도 없다. 시각은 전부 `at=100` 같은 **정수 인자**로 밀어 넣었다([12.4](#/boundaries-di)). 그래서 코드를 한 줄 고칠 때마다 전체를 돌릴 수 있다.

`time.sleep(1)` 이 다섯 개만 들어가도 스위트는 5초가 되고, 5초가 되면 사람은 저장할 때마다 돌리지 않는다. **안 돌리는 테스트는 없는 테스트다.** 시간 관련 규칙을 `sleep` 으로 테스트하고 있다면 그건 테스트 문제가 아니라 **설계 문제**다.
:::

::: danger 테스트에서의 오버엔지니어링 — 감점 목록
과제형에서 아래를 보면 평가자는 "이 사람은 도구를 쓰고 싶어 한다"고 읽는다.

1. **`conftest.py` 에 fixture 열두 개.** 테스트를 읽으려면 다른 파일을 열어야 한다. 주차장 테스트에서 `ParkingLot(capacity=1)` 은 **한 줄**이다. fixture로 뽑을 이유가 없다. 상태를 가진 객체를 fixture로 공유하면 테스트 간 격리가 깨지는 사고까지 딸려 온다.
2. **테스트 데이터 팩토리·빌더 클래스.** `TicketBuilder().with_plate("11A1111").with_entry(0).build()` 는 `Ticket("11A1111", 0)` 보다 길고 읽기 어렵다. 필드가 열 개를 넘고 대부분이 기본값일 때만 값이 있다.
3. **`unittest.mock` 남용.** 이미 [12.4](#/boundaries-di)에서 다뤘다. 도메인 객체를 mock 으로 감싸면 진짜 규칙을 하나도 안 보게 된다.
4. **테스트를 위해 도메인에 뚫은 구멍.** `lot._tickets` 를 테스트가 직접 들여다보는 순간, 내부 자료구조를 바꿀 때마다 테스트가 깨진다. 위 테스트들은 `free_spaces` 와 공개 메서드만 쓴다.
5. **속성 기반 테스트를 습관적으로 붙이기.** [6.3 Hypothesis](#/hypothesis)는 강력하지만, 4시간 과제에서 명세 테스트가 비어 있는데 property 테스트만 있으면 역효과다. 규칙 테스트를 다 채운 **뒤에** 붙이는 보너스다.
6. **CI 파이프라인 구축.** [6.6 CI/CD](#/ci)는 실무의 것이다. 과제형에서는 `pytest` 한 줄이 도는 것이 훨씬 중요하다.

공통점은 하나다. **읽는 사람이 코드보다 먼저 당신의 도구를 이해해야 한다.** 그 순간 손해다.
:::

## 요약

- 과제형 테스트는 개수가 아니라 **요구사항 문장과의 대응**으로 평가된다. 문장 하나에 최소 하나, 문장에 없는 테스트는 쓰지 않는다.
- **먼저 지운다.** 언어·표준 라이브러리·프레임워크가 이미 보장하는 것은 테스트하지 않는다. 판단 기준은 *"이 assert 가 깨지려면 무엇이 잘못돼야 하는가"* 다. 답이 "파이썬이 고장 나면"이면 지운다.
- **테스트 이름이 명세다.** `test_<주어>_<동사>_<조건>` 으로 짓고 `pytest --collect-only` 출력이 명세 목록으로 읽히게 만들어라. 이름에 `and` 가 두 번 나오면 테스트를 쪼개라.
- **`assert` 는 여러 개 써도 된다.** 기준은 개수가 아니라 `when` 이다. 같은 동작의 여러 흔적이면 붙이고, 동작이 달라지면 쪼갠다. 관계없는 규칙을 묶으면 첫 실패에서 멈춰 나머지 정보를 잃는다.
- **틀리는 곳은 언제나 부등호다.** 구간마다 마지막 값과 다음 구간 첫 값을 적어 경계 목록을 만들어라. 표로 주어진 규칙은 `parametrize`, "그 뒤로 계속 같다"는 나열이 낫다.
- **실패 경로에서 갈린다.** 예외 타입만 보면 절반이다. **거부된 부작용이 진짜 안 일어났는지**와 **실패 뒤 복구가 되는지**까지 확인해라. 명세가 안 정한 지점은 테스트로 선언해 두면 감점이 아니라 가점이다.
- **커버리지 100%는 버그가 없다는 뜻이 아니다.** 분기 커버리지 100%에서도 부등호 버그는 살아남는다. 커버리지는 점수가 아니라 **안 밟은 줄을 찾는 지도**다.
- **테스트에도 오버엔지니어링이 있다.** fixture 계층, 빌더, mock, 테스트용 구멍, CI. 읽는 사람이 코드보다 먼저 당신의 도구를 이해해야 한다면 그건 감점이다.

::: quiz 설계 과제 — 고르지 말고 판단하고 짜라
전부 **코드를 짜거나 판단을 문장으로 적는** 과제다. 정답은 없다. 근거 없는 선택만 틀린 것이다.

**1. 지우기 (10분, 코드 없음)**
어떤 지원자가 주차장 과제에 아래 테스트를 냈다. **남길 것과 지울 것을 나누고, 지우는 것마다 "이게 깨지려면 무엇이 잘못돼야 하는가"를 한 줄로 적어라.**

- `test_ticket_repr_is_not_empty`
- `test_fee_is_never_negative`
- `test_capacity_is_stored`
- `test_settle_returns_a_number`
- `test_two_cars_can_park_at_the_same_time`
- `test_enter_raises_on_none_plate`

**2. 경계 목록 (15분, 코드)**
아래 규칙의 경계값 목록을 먼저 **표로** 만들고, 그 표를 `pytest.mark.parametrize` 로 옮겨라. 각 케이스마다 왜 그 값인지 주석을 달아라. 그 다음 규칙을 구현하고 `pytest` 로 통과시켜라.

> 전기 요금: 200 kWh까지는 kWh당 100원. 200 초과 400까지는 초과분에 kWh당 200원. 400 초과분은 kWh당 300원. 총액이 1,000원 미만이면 최소요금 1,000원을 받는다.

최소요금 규칙 때문에 **경계가 하나 더 생긴다.** 그것이 몇 kWh인지 계산해서 케이스에 넣어라.

**3. 쪼개기 (10분, 코드)**
아래 테스트를 쪼개라. 몇 개가 되는지, 각각 어떤 이름인지 적고 실제로 짜라.

```python title="조각"
def test_stamp():
    lot = ParkingLot(capacity=1)
    lot.enter("11A1111", at=0)
    assert lot.stamp("11A1111") == 1
    assert lot.stamp("11A1111", count=3) == 2
    assert lot.settle("11A1111", at=150) == 2_500
    lot.leave("11A1111", at=155)
    assert lot.free_spaces == 1
```

**4. 실패 경로 보강 (20분, 코드)**
아래 테스트는 "예외가 났다"까지만 확인한다. **거부된 부작용**과 **복구 가능성**을 검증하는 `assert` 를 추가하고, 그 `assert` 들이 실제로 무언가를 잡을 수 있음을 보여라 — 즉 **일부러 그 규칙을 어기는 구현을 만들어 테스트가 빨간불이 되는 것을 확인**해라.

```python title="조각"
def test_full_lot_rejects_entry():
    lot = ParkingLot(capacity=1)
    lot.enter("11A1111", at=0)
    with pytest.raises(LotFull):
        lot.enter("22B2222", at=1)
```

**5. 커버리지 함정 만들기 (15분, 코드)**
**분기 커버리지 100%인데 명세를 어기는** 함수와 테스트 쌍을 직접 만들어라. 조건은 둘이다. ① 함수가 `if` 를 두 개 이상 가질 것 ② 버그가 부등호가 아닐 것(상수, 순서, 반올림 중 하나). 그리고 그 버그를 잡는 테스트를 한 개 추가했을 때 **커버리지 숫자가 그대로임**을 출력으로 보여라.

**6. 얼마나 (10분, 문장)**
2번의 전기 요금 규칙에 다음이 추가됐다고 하자. *"고객 등급이 A면 총액의 10%를 할인한다. 할인 후에도 최소요금은 적용된다."*

**테스트를 몇 개 더 쓸 것인가.** 개수와 각 테스트 이름을 적고, **쓰지 않기로 한 테스트도 하나 이상 적고 왜 안 쓰는지** 밝혀라.
:::

**다음 절**: [12.7 프로젝트 구조 만들기](#/project-structure) — 이 테스트들을 어디에 두고, 과제 규모에 맞는 최소 폴더 구조는 무엇인가.
