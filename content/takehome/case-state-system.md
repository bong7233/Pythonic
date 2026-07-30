# 12.9 완결 예제 I — 상태 머신 시스템

::: lead
지금까지 여덟 절에 걸쳐 조각을 하나씩 봤다. 요구사항에서 모델을 뽑고([12.2](#/requirements-to-model)), 상태를 `Enum` 과 전이표로 못 박고([12.3](#/state-machine)), 외부 시스템을 `Protocol` 뒤로 밀어내고([12.4](#/boundaries-di)), 실패를 설계하고([12.5](#/error-design)), 테스트를 고르고([12.6](#/test-strategy)), 구조를 잡고([12.7](#/project-structure)), README를 썼다([12.8](#/readme-submit)). 이 절은 그 여덟 개를 **하나의 제출물 안에서 순서대로** 굴린다. 소재는 음료 자판기다. 요구사항 여덟 문장에서 시작해 소스 515줄, 테스트 271줄, 29개 테스트가 통과하는 저장소까지 간다. 코드보다 중요한 것은 **각 갈림길에서 무엇을 왜 골랐는가**다. 정답을 외우지 말고 판단 근거를 봐라.
:::

## 과제 지시문

이런 문서 한 장을 받았다고 하자. 실제 과제형 지시문의 분량이 대개 이 정도다.

> **음료 자판기 컨트롤러 (제한 4시간)**
>
> 1. 자판기에는 슬롯이 있다. 슬롯마다 상품명, 가격, 남은 수량이 있다. 가격은 100원 단위다.
> 2. 손님은 100원·500원 동전과 1000원 지폐를 여러 번 넣을 수 있다. 그 외의 화폐는 받지 않는다.
> 3. 투입 금액이 가격 이상이고 재고가 있는 슬롯만 고를 수 있다.
> 4. 상품을 내보내고 남은 금액을 거스름돈으로 반환한다. **거스름돈은 동전으로만 낸다**(지폐는 나가지 않는다).
> 5. 거스름돈을 만들 수 없으면 **판매하지 않는다.**
> 6. 손님은 반환 레버로 투입 금액 전액을 언제든 돌려받는다.
> 7. 상품 배출과 동전 반환은 하드웨어가 한다. **하드웨어 없이 테스트할 수 있어야 한다.**
> 8. 관리자는 점검 모드로 바꿔 재고와 동전을 보충하고 금고를 회수한다. 점검 모드에서는 판매하지 않는다.
>
> 제출: 실행 방법과 설계 결정을 담은 README, 테스트 포함.

여덟 문장이다. 여기서 곧바로 클래스를 그리기 시작하면 대개 두 시간쯤 뒤에 지운다. 먼저 할 일이 있다.

## 첫 20분 — 손을 대기 전에

### 명세의 구멍을 먼저 찾는다

지시문은 반드시 불완전하다. **구멍을 못 본 채로 코드를 짜면 나중에 그 구멍이 설계를 뒤집는다.** 위 여덟 문장을 세 번 읽고 나온 것들이다.

| 안 적힌 것 | 왜 문제인가 | 정한 것 |
| --- | --- | --- |
| 손님이 방금 넣은 동전을 거스름돈 재원으로 쓰는가 | 안 쓰면 5번 거절이 훨씬 자주 난다 | **쓴다.** 테스트로 고정 |
| 손님 돈이 들어 있는데 관리자가 점검 모드로 들어가면 | 손님 돈이 금고로 딸려 들어간다 | **금지한다** |
| 거스름돈을 못 만들었을 때 손님 돈은 | 5번은 "판매하지 않는다"까지만 말한다 | **그대로 둔다.** 반환 레버는 여전히 동작 |
| 판매 도중 하드웨어가 실패하면 | 재고와 금고가 어긋난다 | 배출 실패 시 **아무것도 안 바뀐다** |
| 1000원 지폐가 여러 장 들어오면 거스름돈이 | 4번 때문에 동전만 나간다 | 못 만들면 5번에 걸린다 |

다섯 개 전부를 **README의 설계 결정 칸에 적을 것**이다. [12.2](#/requirements-to-model)에서 말한 대로, 구멍을 메운 것 자체보다 **메웠다고 밝히는 것**이 평가된다. 조용히 정하면 평가자는 그것을 "결정"이 아니라 "누락"으로 읽는다.

::: tip 구멍을 찾는 세 가지 질문
① **"~할 수 없다"의 반대는 무엇인가.** "재고보다 많이 못 판다"면 시도했을 때 무슨 일이 일어나는가. ② **두 요구사항이 동시에 걸리면 무엇이 이기는가.** 3번(잔액 충분)과 5번(거스름돈 불가)이 부딪히면. ③ **가장 나쁜 타이밍에 실패하면.** 상품이 나간 직후에 전원이 나가면.
:::

### 만드는 순서 — 안쪽부터

과제형에서 순서를 잘못 잡으면 마지막 30분에 아무것도 못 돌린다. 규칙은 하나다.

> **가장 안쪽 값부터 만들고, 각 단계가 끝날 때마다 테스트가 통과한 상태로 다음으로 넘어간다.**

```text nolines
  coins/states/errors  ->  machine  ->  ports/fakes  ->  cli  ->  README
  (값과 규칙)              (도메인)     (경계)          (입출력)   (설명)
       |                     |            |               |
     빠르다               제일 오래       짧다           짧다
     테스트 쉽다          여기가 본론    가짜부터        수동 확인
```

바깥(CLI)부터 만들면 안쪽이 정해지지 않아 계속 고치게 되고, 중간에 시간이 끊기면 **동작하는 것이 하나도 없다.** 안쪽부터 만들면 언제 끊기든 그 시점까지는 테스트가 통과한다.

실제로 쓴 4시간이다.

| 시각 | 한 일 |
| --- | --- |
| 0:00~0:20 | 지시문 세 번 읽기. 구멍 표 작성. 상태·사건 이름 종이에 |
| 0:20~0:50 | `states.py`, `errors.py`, `coins.py` + `test_coins.py` (8개) |
| 0:50~1:50 | `machine.py` 판매 경로 + `test_machine.py` (21개) |
| 1:50~2:20 | `ports.py`, `fakes.py`, `hardware.py` + 실패 경로 테스트 |
| 2:20~2:50 | `cli.py`, `__main__.py`. 손으로 한 번 굴려 보기 |
| 2:50~3:20 | README |
| 3:20~3:50 | 깨끗한 복제본에서 리허설, 잔여물 정리 |

**README에 30분을 배정한 것**이 이 표에서 가장 중요하다. 마지막에 남는 시간으로 쓰겠다고 하면 안 쓰게 된다.

## 상태를 먼저 못 박는다

명사와 동사를 뽑는 절차는 [12.2](#/requirements-to-model)에 있으니 결과만 쓴다. 이 과제의 **상태**는 셋이다.

```python title="vending/states.py"
from enum import Enum, auto


class MachineState(Enum):
    """자판기가 있을 수 있는 자리."""

    IDLE = auto()         # 투입 금액 0. 손님을 기다린다
    ACCEPTING = auto()    # 투입 금액 > 0. 손님 돈을 들고 있다
    MAINTENANCE = auto()  # 점검 중. 판매하지 않는다


class MachineEvent(Enum):
    """자판기에 일어나는 일."""

    INSERT = auto()
    SELECT = auto()
    REFUND = auto()
    SERVICE_START = auto()
    SERVICE_END = auto()
    RESTOCK = auto()
    COLLECT = auto()


S, E = MachineState, MachineEvent

# (현재 상태, 사건) -> 다음 상태. 여기 없는 조합은 전부 금지다.
TRANSITIONS: dict[tuple[MachineState, MachineEvent], MachineState] = {
    (S.IDLE, E.INSERT): S.ACCEPTING,
    (S.ACCEPTING, E.INSERT): S.ACCEPTING,
    (S.ACCEPTING, E.SELECT): S.IDLE,
    (S.ACCEPTING, E.REFUND): S.IDLE,
    (S.IDLE, E.SERVICE_START): S.MAINTENANCE,
    (S.MAINTENANCE, E.SERVICE_END): S.IDLE,
    (S.MAINTENANCE, E.RESTOCK): S.MAINTENANCE,
    (S.MAINTENANCE, E.COLLECT): S.MAINTENANCE,
}
```

`Enum` / `auto()` 의 문법과 `IntEnum`·`StrEnum`·`Flag` 의 차이는 [12.3](#/state-machine)에 있다. 여기서 볼 것은 다른 것이다.

**상태 3 × 사건 7 = 21가지 중 8가지만 허용된다.** 나머지 13가지는 표에 없다는 사실만으로 전부 막힌다. 요구사항 8("점검 모드에서는 판매하지 않는다")을 위해 따로 `if` 를 쓴 곳이 한 군데도 없다는 것을 확인해라. `(MAINTENANCE, SELECT)` 가 표에 없다 — 그게 전부다.

```text nolines
  IDLE        --insert--------> ACCEPTING
  ACCEPTING   --insert--------> ACCEPTING     (self)
  ACCEPTING   --select--------> IDLE          (도메인 규칙을 통과했을 때만)
  ACCEPTING   --refund--------> IDLE
  IDLE        --service_start-> MAINTENANCE
  MAINTENANCE --restock-------> MAINTENANCE   (self)
  MAINTENANCE --collect-------> MAINTENANCE   (self)
  MAINTENANCE --service_end---> IDLE
```

::: note 12.3의 발주서와 정반대인 지점 — 종료 상태가 없다
발주서는 `RECEIVED`·`CANCELLED` 같은 종료 상태가 있었다. 자판기는 **하나도 없다.**

```pyrepl
>>> from vending.states import TRANSITIONS, MachineState
>>> {s for s in MachineState if not any(src is s for src, _ in TRANSITIONS)}
set()
```

이 기계는 순환한다. 그래서 [12.3](#/state-machine)에서 쓴 `FINAL_STATES` 를 여기서는 **만들지 않는다.** 항상 빈 집합인 상수를 두는 것은 코드가 아니라 장식이다. 같은 도메인 개념이라도 요구사항이 요구하지 않으면 빼라 — 상태 머신을 한 번 배우고 나면 이걸 습관적으로 복사해 넣게 된다.
:::

### 전이 검증과 상태 커밋을 분리한다

[12.3](#/state-machine)의 발주서는 전이가 확인되면 곧바로 상태를 바꿨다. 여기서는 그러면 안 된다. `select` 는 전이가 **가능하더라도** 재고·잔액·거스름돈 때문에 실패할 수 있기 때문이다.

```python title="vending/machine.py (발췌)"
def _target(self, event: MachineEvent) -> MachineState:
    """이 사건이 지금 가능한지만 본다. 상태를 바꾸지는 않는다."""
    try:
        return TRANSITIONS[(self._state, event)]
    except KeyError:
        raise InvalidTransition(self._state, event) from None
```

`_target` 은 **다음 상태를 계산해서 돌려줄 뿐 대입하지 않는다.** 호출하는 쪽은 이렇게 생겼다.

```python
def insert(self, coin: Coin) -> None:
    if not isinstance(coin, Coin):
        raise UnsupportedCoin(coin)
    target = self._target(MachineEvent.INSERT)   # ① 가능한가
    self._escrow.add(coin)                       # ② 실제 변경
    self._state = target                         # ③ 커밋
```

세 줄이 항상 이 순서다. **중간에서 예외가 나면 `_state` 는 손대지 않은 채로 남는다.** 상태 머신을 쓰면서 가장 자주 나는 사고가 "전이는 했는데 본체 작업이 실패해서 상태만 앞서가는 것"이다. 검증과 커밋을 분리하면 그 사고가 구조적으로 불가능해진다.

::: warn 상태 머신이 모든 규칙을 담지는 않는다
과제형에서 상태 머신을 처음 써 본 사람이 가장 자주 하는 실수는 **모든 조건을 전이표에 밀어 넣으려는 것**이다. "재고 있음", "잔액 충분", "거스름돈 가능"을 상태로 만들기 시작하면 상태가 금세 스무 개가 된다.

경계선은 이렇다.

- **전이표가 답하는 질문**: *지금 이 조작을 시도할 수 있는가.* 오직 현재 상태만 보면 답이 나온다.
- **도메인 규칙이 답하는 질문**: *시도했을 때 성공하는가.* 재고·잔액·금고를 봐야 답이 나온다.

`select` 는 `ACCEPTING` 에서만 **시도할 수 있고**, 시도한 뒤에 네 개의 규칙을 더 통과해야 **성공한다**. 둘을 섞으면 표가 폭발하거나 규칙이 표 밖으로 새 나간다.
:::

### 왜 여기서는 `IntEnum` 을 쓰는가

[12.3](#/state-machine)은 `IntEnum` 을 조심하라고 했다. 그런데 화폐는 `IntEnum` 으로 만들었다.

```python title="vending/coins.py (발췌)"
class Coin(IntEnum):
    """받는 화폐. 값이 곧 금액이라서 IntEnum 이다."""

    W100 = 100
    W500 = 500
    W1000 = 1000
```

기준은 하나다. **값이 도메인에서 의미를 갖고 산술에 쓰이는가.** 발주서 상태의 `1, 2, 3` 은 아무 의미가 없어서 `auto()` 였다. 화폐의 `100` 은 **금액 그 자체**고, `coin * n` 으로 곱해야 하고, 정렬하면 액면 순서가 나온다. 그래서 `IntEnum` 이 맞다.

대가는 그대로 따라온다.

```pyrepl
>>> from collections import Counter
>>> from vending.coins import Coin
>>> Coin.W100
<Coin.W100: 100>
>>> Coin.W100 == 100
True
>>> Coin(100)
<Coin.W100: 100>
>>> box = Counter({Coin.W100: 3})
>>> box[100]
3
>>> Coin(300)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: 300 is not a valid Coin
```

`box[100]` 이 통과한다. `Coin.W100` 과 정수 `100` 은 해시도 같고 `==` 도 참이라 **딕셔너리 키로 구분되지 않는다.** 내부 자료구조가 맨 정수를 조용히 받아들인다는 뜻이다.

그래서 **경계에서 한 번 막는다.**

```pyrepl
>>> from vending.cli import build
>>> from vending.errors import UnsupportedCoin
>>> m = build(None)
>>> try:
...     m.insert(100)
... except UnsupportedCoin as exc:
...     print(exc)
...
받지 않는 화폐: 100
```

`Coin.W100 == 100` 은 `True` 인데 `m.insert(100)` 은 거부됐다. `isinstance(100, Coin)` 이 `False` 이기 때문이다. **`IntEnum` 은 `==` 에서는 정수와 섞이지만 `isinstance` 로는 걸러진다.** 이 성질이 "바깥에서 들어오는 값은 문 앞에서 한 번 검사하고, 안쪽에서는 신뢰한다"는 설계를 가능하게 한다. 문을 하나로 좁혀 놓지 않으면 이 검사가 코드 열 군데에 흩어진다.

## 돈을 세는 자리

### CoinBox — 개수가 음수가 되지 않는 유일한 이유

```python title="vending/coins.py (발췌)"
class CoinBox:
    """동전 다발. 개수가 음수가 되는 일이 없도록 여기서만 뺀다."""

    def __init__(self, counts: Mapping[Coin, int] | None = None) -> None:
        self._counts: Counter[Coin] = Counter(counts or {})

    def count(self, coin: Coin) -> int:
        return self._counts[coin]

    def total(self) -> int:
        return sum(coin * n for coin, n in self._counts.items())

    def add(self, coin: Coin, n: int = 1) -> None:
        if n < 0:
            raise ValueError(f"음수는 넣을 수 없다: {n}")
        self._counts[coin] += n

    def merge(self, other: "CoinBox") -> None:
        self._counts.update(other._counts)

    def take(self, plan: Mapping[Coin, int]) -> None:
        """계획한 만큼 뺀다. 하나라도 모자라면 아무것도 바꾸지 않는다."""
        short = [c for c, n in plan.items() if self._counts[c] < n]
        if short:
            raise ValueError(f"동전이 모자란다: {short}")
        for coin, n in plan.items():
            self._counts[coin] -= n

    def drain(self) -> dict[Coin, int]:
        """전부 꺼내고 비운다. 실제로 나가는 동전만 담는다."""
        out = {coin: n for coin, n in sorted(self._counts.items()) if n > 0}
        self._counts.clear()
        return out

    def snapshot(self) -> dict[Coin, int]:
        """0개인 화폐도 빠뜨리지 않는다 — 보고용."""
        return {coin: self._counts[coin] for coin in Coin}
```

`Counter` 를 그냥 쓰지 않고 이 껍데기를 씌운 이유가 셋이다.

1. **`take` 가 먼저 전부 검사한다.** 반쯤 빼다가 실패하면 금고가 깨진다. 검사와 변경을 나눈 것은 앞의 `_target` 과 같은 발상이다.
2. **`Counter` 뺄셈을 쓰지 않는다.** `-` 는 0 이하가 된 키를 조용히 지운다([11.2](#/stdlib-arsenal)). 금고에서 "100원 0개"라는 정보가 사라지면 거스름돈 계산이 그 화폐를 아예 못 보게 된다.
3. **`drain` 과 `snapshot` 이 다르다.** 나가는 동전 목록에 `{W500: 0}` 이 섞이면 하드웨어에 "500원 0개를 내보내라"를 보내게 된다. 반대로 보고용 스냅숏에서 0을 빼면 "100원이 없다"는 사실이 화면에서 사라진다. **같은 자료의 두 용도를 두 메서드로 나눈 것**이고, 두 메서드가 다르다는 사실 자체가 테스트로 고정돼 있다.

::: danger 껍데기가 `_counts` 를 그대로 내주면 전부 무의미해진다
`CoinBox` 가 지키는 불변식은 "개수가 음수가 아니다" 하나다. 그런데 `def counts(self): return self._counts` 같은 게터를 하나 열어 두면 호출자가 `box.counts()[Coin.W100] -= 5` 를 할 수 있고, 위의 세 가지 보호가 전부 무너진다. `snapshot()` 이 **새 `dict` 를 만들어 돌려주는 것**이 그래서 중요하다. 캡슐화는 `_` 를 붙이는 것이 아니라 **밖으로 나가는 객체가 안쪽과 이어져 있지 않게 하는 것**이다. 같은 실수를 `list` 로 하면 더 흔하다 — `return self._items` 는 호출자에게 `append` 권한을 준 것과 같다.
:::

### 거스름돈 — 계획만 세우고 아무것도 바꾸지 않는다

```python title="vending/coins.py (발췌)"
# 거스름돈으로 나가는 것. 1000원은 지폐라서 나가지 않는다(요구사항 4).
CHANGE_DENOMS: tuple[Coin, ...] = (Coin.W500, Coin.W100)


def plan_change(amount: int, available: CoinBox) -> dict[Coin, int]:
    """거스름돈 구성을 정한다. 만들 수 없으면 CannotMakeChange.

    이 함수는 아무것도 바꾸지 않는다. 계획만 돌려준다.
    500 이 100 의 배수라서 큰 것부터 집는 방법이 최적이자 완전하다.
    """
    if amount < 0:
        raise ValueError(f"음수 거스름돈: {amount}")
    plan: dict[Coin, int] = {}
    rest = amount
    for coin in CHANGE_DENOMS:
        n = min(rest // coin, available.count(coin))
        if n:
            plan[coin] = n
            rest -= coin * n
    if rest:
        raise CannotMakeChange(amount, rest)
    return plan
```

이 함수가 **계획만 돌려주고 금고를 건드리지 않는 것**이 판매 전체 설계의 뿌리다. 요구사항 5("만들 수 없으면 팔지 않는다")를 지키려면 배출 전에 거스름돈이 가능한지 알아야 하고, 알아보는 행위 자체가 금고를 줄이면 안 된다. **질문과 실행을 분리하면 "미리 물어볼 수 있는" 코드가 된다.**

요구사항 4의 "동전으로만"은 `CHANGE_DENOMS` 한 줄이다. 받는 화폐(`Coin` 전체)와 내주는 화폐(`CHANGE_DENOMS`)를 **다른 이름으로 분리한 것**이 요구사항을 코드에 옮긴 자리다. 하나로 뒀으면 이 규칙이 `if coin != Coin.W1000` 같은 조건으로 흩어졌을 것이다.

::: danger 큰 것부터 집는 방법이 맞는 이유는 이 화폐에서만이다
그리디는 **일반적으로 틀린다.** 화폐 단위가 1·3·4이고 4가 하나, 3이 둘 있을 때 6을 만들어 보자.

```pyrepl
>>> def greedy(amount, have):
...     plan = {}
...     for coin in sorted(have, reverse=True):
...         n = min(amount // coin, have[coin])
...         if n:
...             plan[coin] = n
...             amount -= coin * n
...     return plan if amount == 0 else None
...
>>> greedy(6, {4: 1, 3: 2, 1: 0}) is None
True
>>> greedy(6, {4: 0, 3: 2, 1: 0})
{3: 2}
```

**답이 있는데 그리디는 못 찾았다.** 4를 집는 순간 남은 2를 만들 방법이 없어진다. 4를 포기하면 3+3으로 끝난다.

이 프로그램에서 그리디가 안전한 이유는 딱 하나다. **거스름돈 화폐가 500과 100뿐이고 100이 500을 나눈다.** 500을 하나 덜 집으면 100이 다섯 개 더 필요해지므로, 큰 것부터 집는 것이 100의 소요량을 최소로 만든다. 만들 수 있는 조합이 있으면 그리디가 반드시 찾는다.

**요구사항이 50원을 추가하면 이 논증을 다시 해야 한다.** 50·100·500도 나눗셈 사슬이라 여전히 성립하지만, 문제는 "성립한다"가 아니라 **성립하는지 확인했는가**다. `plan_change` 의 독스트링에 그 이유를 한 줄로 적어 둔 것이 이 확인의 흔적이다. 주석이 없으면 다음 사람은 화폐를 추가하면서 이 함수를 쳐다보지도 않는다. 일반 화폐라면 DP가 필요하고, 그건 [7.20](#/dp-basics)의 동전 교환 문제다.
:::

## 손님 돈은 아직 자판기 것이 아니다

요구사항 6(반환 레버)이 자료구조 하나를 강제한다. 갈림길이 여기에 있다.

| | **안 A — 투입 즉시 금고로** | **안 B — 에스크로에 따로** |
| --- | --- | --- |
| 반환 레버 | 금고에서 투입 금액만큼 **다시 만들어** 내준다 | 에스크로를 그대로 비운다 |
| 반환이 실패할 수 있는가 | **있다.** 1000원 넣고 반환하면 동전으로 바꿔 줘야 한다 | 없다. 넣은 그대로 나간다 |
| 금고 잔고 | 반환 계산이 틀리면 금고가 어긋난다 | 반환은 금고를 건드리지 않는다 |
| 거스름돈 재원 | 그냥 금고를 본다 | **금고 + 에스크로를 합쳐야 한다** |
| 코드 | 상태가 하나 적다 | `CoinBox` 가 둘이다 |

**안 B를 골랐다.** 근거는 요구사항 6의 "전액"이다. 안 A에서 1000원 지폐를 넣고 반환 레버를 누르면 자판기는 1000원을 동전으로 바꿔 줘야 하고, 동전이 모자라면 **반환이 실패한다.** 손님 돈을 못 돌려주는 상태는 어떤 이유로도 만들면 안 된다. 안 B에서는 반환이 실패할 수 없다 — 넣은 물리적 화폐를 그대로 내보내면 되기 때문이다.

대가는 정직하게 하나다. 거스름돈 재원을 계산할 때 두 곳을 합쳐야 한다.

```python title="vending/machine.py (발췌)"
payable = CoinBox(self._vault.snapshot())
payable.merge(self._escrow)          # 방금 받은 동전도 거스름돈 재원이다
plan = plan_change(change_due, payable)
```

그리고 이 두 줄이 명세의 구멍 하나(방금 넣은 동전을 재원으로 쓰는가)에 대한 답이다. 테스트가 그 답을 못 박는다.

```python title="tests/test_machine.py (발췌)"
def test_방금_넣은_동전도_거스름돈_재원이_된다():
    # 금고에는 100원이 하나뿐. 손님이 넣은 100원 두 개가 없으면 300원을 못 만든다.
    m = machine(vault={Coin.W100: 1})
    for coin in (Coin.W1000, Coin.W100, Coin.W100):
        m.insert(coin)
    assert m.select("A1") == {Coin.W100: 3}
```

**주석이 테스트 데이터의 의도를 설명하고 있다.** 금고에 100원을 하나만 둔 것은 우연이 아니라 이 규칙이 없으면 실패하도록 고른 값이다. 그 설명이 없으면 다음 사람이 `vault={Coin.W100: 1}` 을 무심코 넉넉하게 고쳐서 테스트를 무력화한다.

## 하드웨어를 끊는다

요구사항 7이다. `Protocol` 로 경계를 정의하고 생성자로 주입하는 방법 자체는 [12.4](#/boundaries-di)에 있으니 여기서는 **이 과제에서 경계를 몇 개 그었고 왜 거기서 멈췄는가**만 본다.

```python title="vending/ports.py"
"""이 프로그램이 하드웨어에 요구하는 것. 구현은 여기 없다(요구사항 7)."""

from collections.abc import Mapping
from typing import Protocol

from .coins import Coin


class Dispenser(Protocol):
    def dispense(self, code: str) -> None:
        """슬롯 code 의 상품을 하나 내보낸다. 실패하면 DispenseFailed."""
        ...

    def return_coins(self, coins: Mapping[Coin, int]) -> None:
        """지정한 구성대로 동전을 반환구로 내보낸다. 실패하면 ChangeReturnFailed."""
        ...
```

**포트가 하나고 메서드가 둘이다.** 상품 배출기와 동전 호퍼를 별도 포트로 나눌 수도 있었다. 나누지 않은 이유는 요구사항에 "배출기만 교체한다"는 말이 없고, 실제 자판기에서 둘은 같은 제어 보드에 물려 있기 때문이다. **포트를 나누는 기준은 개념의 우아함이 아니라 "따로 갈아 끼울 일이 있는가"다.** 갈아 끼울 일이 없으면 파일 하나와 조립 코드 몇 줄만 늘어난다.

진짜와 가짜는 나란히 둔다.

```python title="vending/hardware.py — 진짜"
class SerialDispenser:
    """제어 보드에 한 줄짜리 명령을 써 보낸다.

    실제 자판기에서는 port 가 /dev/ttyUSB0 같은 시리얼 장치다.
    """

    def __init__(self, port: Path) -> None:
        self._port = port

    def _send(self, line: str) -> None:
        with self._port.open("a", encoding="ascii") as dev:
            dev.write(line + "\n")

    def dispense(self, code: str) -> None:
        try:
            self._send(f"MOTOR {code}")
        except OSError as exc:
            raise DispenseFailed(code, str(exc)) from exc

    def return_coins(self, coins: Mapping[Coin, int]) -> None:
        try:
            for coin, n in sorted(coins.items(), reverse=True):
                self._send(f"HOPPER {int(coin)} {n}")
        except OSError as exc:
            raise ChangeReturnFailed(dict(coins), str(exc)) from exc
```

```python title="vending/fakes.py — 가짜"
class FakeDispenser:
    """무엇이 나갔는지 기억한다. 테스트는 이것만 본다."""

    def __init__(self) -> None:
        self.dispensed: list[str] = []
        self.returned: list[dict[Coin, int]] = []

    def dispense(self, code: str) -> None:
        self.dispensed.append(code)

    def return_coins(self, coins: Mapping[Coin, int]) -> None:
        self.returned.append(dict(coins))


class JammedDispenser(FakeDispenser):
    """모터가 걸린 자판기. 상품이 안 나간다."""

    def dispense(self, code: str) -> None:
        raise DispenseFailed(code, "motor jam")


class EmptyHopper(FakeDispenser):
    """상품은 나가지만 동전 반환구가 죽었다."""

    def return_coins(self, coins: Mapping[Coin, int]) -> None:
        raise ChangeReturnFailed(dict(coins), "hopper stuck")
```

가짜가 셋인 것이 이 과제의 핵심이다. **`FakeDispenser` 하나만 있으면 성공 경로밖에 못 짠다.** 요구사항 7이 진짜로 요구하는 것은 "하드웨어 없이 돌아간다"가 아니라 **"하드웨어가 고장 났을 때를 하드웨어 없이 재현할 수 있다"**다. 실물 자판기의 모터를 일부러 걸리게 만들 수는 없다. 그런데 `JammedDispenser` 는 세 줄이다.

`SerialDispenser` 가 `Path` 를 받는 것도 의도적이다. 실제 장치 파일이든 로그 파일이든 **여는 대상만 바뀐다.** 임시 파일을 주고 그대로 실행해 보면 이렇게 나간다.

```text nolines
MOTOR A1
HOPPER 500 2
HOPPER 100 1
```

::: perf 가짜가 빠른 것은 부수 효과다
같은 판매 1,000회를, 가짜 배출기로 한 번과 `SerialDispenser` 로 로컬 파일에 쓰면서 한 번 돌렸다.

| 배출기 | 판매 1,000회 |
| --- | --- |
| `FakeDispenser` | 8.0 ~ 8.9 ms |
| `SerialDispenser` (로컬 파일) | 37 ~ 50 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

4~6배다. 그리고 이건 로컬 파일이라 OS 캐시에 얹혀 있다. 진짜 시리얼 포트가 얼마나 걸리는지는 **여기서 측정하지 않았으니 숫자를 말하지 않겠다.**

중요한 건 이 표가 경계를 정당화하지 않는다는 것이다. **속도는 부수 효과고, 진짜 이유는 재현성이다.** 모터 걸림·호퍼 고장·전원 순단을 테스트에서 원하는 순간에 정확히 일으킬 수 있는가 — 그게 요구사항 7이 묻는 것이다. 이 저장소의 테스트 29개가 0.03초에 끝나는 것은 좋은 일이지만, 그것 때문에 경계를 그은 것은 아니다.
:::

## 판매 한 번 — 순서가 곧 설계다

이 절 전체에서 가장 중요한 코드다.

```python title="vending/machine.py (발췌)" {5,15,17,18}
def select(self, code: str) -> dict[Coin, int]:
    """상품을 판다. 돌려주는 것은 실제로 나간 거스름돈 구성이다."""
    target = self._target(MachineEvent.SELECT)

    # ① 되돌릴 수 없는 일을 하기 전에 전부 검사한다.
    slot = self.slot(code)
    if slot.stock <= 0:
        raise SoldOut(code)
    if self.balance < slot.price:
        raise InsufficientFunds(code, slot.price, self.balance)

    change_due = self.balance - slot.price
    payable = CoinBox(self._vault.snapshot())
    payable.merge(self._escrow)          # 방금 받은 동전도 거스름돈 재원이다
    plan = plan_change(change_due, payable)   # 못 만들면 여기서 끝난다

    # ② 여기부터가 되돌릴 수 없는 구간이다.
    self._dispenser.dispense(code)

    slot.stock -= 1
    self._vault.merge(self._escrow)
    self._escrow = CoinBox()
    self._vault.take(plan)
    self._sales += slot.price
    self._state = target

    self._dispenser.return_coins(plan)
    return plan
```

주석 두 줄이 이 함수의 설계 전부다. **①은 전부 질문이고 ②는 전부 실행이다.** 질문 구간에서는 어떤 상태도 바뀌지 않으므로, 어느 줄에서 예외가 나든 자판기는 손님이 조작하기 전과 똑같다.

순서를 뒤집은 안과 나란히 놓아 본다.

| | **안 A — 검증 먼저 (골랐다)** | **안 B — 상태 갱신 먼저** |
| --- | --- | --- |
| 거스름돈 불가 | 배출도 안 하고 상태도 그대로 | 재고를 줄였다가 되돌려야 한다 |
| 모터 걸림 | 아무것도 안 바뀜 | 재고·금고를 되돌리는 코드가 필요 |
| 되돌리기 코드 | **없다** | 실행 경로마다 있어야 한다 |
| 요구사항 5 | 자연히 지켜진다 | 되돌리기가 완벽해야 지켜진다 |

되돌리기 코드는 **테스트하기 가장 어렵고 가장 안 짜지는 코드**다. 안 A는 그 코드를 아예 존재하지 않게 만든다. 원칙 한 줄로 줄이면 이렇다.

> **바깥 세상을 건드리는 호출은 함수의 가능한 한 뒤로 몰아라. 그 앞은 전부 되돌릴 필요가 없는 코드가 된다.**

실제로 그렇게 동작하는지 확인한다.

```pyrepl
>>> from vending.coins import Coin, CoinBox
>>> from vending.machine import Slot, VendingMachine
>>> from vending.fakes import FakeDispenser
>>> from vending.errors import CannotMakeChange
>>> hw = FakeDispenser()
>>> m = VendingMachine([Slot("A1", "Cola", 900, 2)], CoinBox(), hw)
>>> m.insert(Coin.W1000)
>>> try:
...     m.select("A1")
... except CannotMakeChange as exc:
...     print(exc)
...
거스름돈 100원 중 100원을 만들 수 없다
>>> hw.dispensed
[]
>>> m.slot("A1").stock
2
>>> m.balance
1000
>>> m.refund()
{<Coin.W1000: 1000>: 1}
```

금고가 빈 자판기에 1000원을 넣고 900원짜리를 골랐다. **상품은 안 나갔고, 재고는 2 그대로고, 잔액도 1000원 그대로다.** 그리고 반환 레버는 여전히 동작해서 넣은 지폐를 그대로 돌려준다. 명세의 구멍 하나("못 팔았을 때 손님 돈은")가 코드 한 줄 없이 해결된 것은, 애초에 손님 돈을 건드리지 않았기 때문이다.

::: danger 그래도 남는 구멍이 하나 있다 — 그걸 숨기지 마라
`dispense` 는 성공했는데 `return_coins` 가 실패하면 어떻게 되는가. 상품은 이미 나갔다. 되돌릴 방법이 없다.

이 코드는 **판매를 확정하고 예외를 위로 올린다.** 그래서 `_state` 는 `IDLE` 이고 재고는 줄어 있다. 손님은 상품을 받았고 거스름돈을 못 받았다.

```python title="tests/test_machine.py (발췌)"
def test_거스름돈_반환이_실패해도_판매는_되돌리지_않는다():
    m = machine(EmptyHopper())
    m.insert(Coin.W1000)
    with pytest.raises(ChangeReturnFailed) as exc:
        m.select("A1")
    assert exc.value.amount == 100
    assert m.slot("A1").stock == 1      # 상품은 이미 나갔다
    assert m.sales == 900
    assert m.state is MachineState.IDLE
```

**이 동작이 옳아서 테스트한 것이 아니다. 이렇게 동작한다는 사실을 못 박으려고 테스트한 것이다.** 반대로 판매를 취소하면 상품은 나갔는데 재고는 그대로가 되어 더 나쁘다. 진짜 해결책은 못 준 금액을 비휘발성 저장소에 남기고 관리자에게 알리는 것인데, 그건 요구사항에 없는 영속화 계층이 필요하다.

그래서 한 것: **예외에 금액을 실어 보내고(`exc.value.amount == 100`), README의 "알려진 한계" 맨 위에 적었다.** 4시간짜리 과제에서 이런 구멍을 만나면 선택지는 셋이다 — 모르는 척한다, 요구사항 밖의 계층을 만든다, **드러내고 적는다.** 세 번째가 [12.1](#/takehome-eval)에서 말한 "정직한 TODO"다. 첫 번째는 발견되면 치명적이고, 두 번째는 오버엔지니어링으로 읽힌다.
:::

## 테스트를 어디에 놓았는가

29개다. 무엇을 테스트하고 무엇을 안 하는가의 기준은 [12.6](#/test-strategy)에 있으니, 여기서는 **이 과제의 29개가 어디에 붙었는지**만 본다.

| 파일 | 개수 | 무엇을 |
| --- | --- | --- |
| `test_coins.py` | 8 | 거스름돈 구성, 지폐 제외, 금고 인출의 원자성 |
| `test_machine.py` 상태 전이 | 7 | 허용된 전이가 되는가, 금지된 네 조합이 막히는가 |
| `test_machine.py` 판매 | 6 | 정확한 금액, 거스름돈 구성, 방금 넣은 동전, 잔액 부족, 품절, 없는 슬롯 |
| `test_machine.py` 거스름돈 불가 | 2 | 팔지 않는가, 그 뒤에도 반환되는가 |
| `test_machine.py` 하드웨어 실패 | 2 | 배출 실패, 반환 실패 |
| `test_machine.py` 반환·관리자 | 4 | 레버, 금고 불변, 보충·회수, 매출 누적 |

요구사항 여덟 문장이 전부 최소 하나의 테스트로 이어진다. 역추적 표는 README에 있다.

```python title="tests/test_machine.py (발췌)"
def machine(dispenser=None, *, vault=None, stock=2):
    return VendingMachine(
        [Slot("A1", "Cola", 900, stock), Slot("A2", "Water", 600, 0)],
        CoinBox(vault if vault is not None else {Coin.W500: 2, Coin.W100: 5}),
        dispenser or FakeDispenser(),
    )


def test_손님_돈이_들어_있으면_점검_모드로_못_바꾼다():
    m = machine()
    m.insert(Coin.W100)
    with pytest.raises(InvalidTransition):
        m.start_service()
    assert m.state is MachineState.ACCEPTING


def test_배출에_실패하면_아무것도_바뀌지_않는다():
    m = machine(JammedDispenser())
    m.insert(Coin.W1000)
    with pytest.raises(DispenseFailed):
        m.select("A1")
    assert m.slot("A1").stock == 2
    assert m.balance == 1000
    assert m.sales == 0
    assert m.state is MachineState.ACCEPTING
```

세 가지를 짚는다.

1. **`machine()` 헬퍼 하나가 fixture 를 대신한다.** `A2` 의 재고를 처음부터 0으로 둔 것은 품절 테스트를 위해서다. pytest fixture 를 쓸 수도 있지만([6.2](#/pytest-advanced)), 인자 세 개짜리 함수 하나로 끝나는 것을 `conftest.py` 로 옮기면 테스트를 읽는 사람이 파일을 하나 더 열어야 한다.
2. **두 번째 테스트의 `assert` 가 네 개다.** [12.6](#/test-strategy)에서 말한 대로 이건 "한 테스트에 한 단언" 규칙 위반이 아니다. **"아무것도 바뀌지 않는다"는 명제 자체가 네 개의 관찰로 이루어져 있다.** 하나만 검사하면 나머지 셋이 조용히 깨진다.
3. **이름이 요구사항 문장이다.** `test_배출에_실패하면_아무것도_바뀌지_않는다` 는 지시문에 없는 문장인데, 명세의 구멍 표에서 정한 것이다. 테스트 이름이 곧 그 결정의 기록이다.

::: warn 21가지 조합을 전부 테스트하고 싶어지는 순간
상태 3 × 사건 7 = 21이고 금지된 것이 13가지다. 반복문 하나로 13가지를 전부 도는 테스트를 짜고 싶어진다. 짜지 마라.

```python
# ❌ 전이표를 전이표로 검증한다. 항상 통과한다.
@pytest.mark.parametrize("state,event", BANNED_COMBOS)
def test_금지된_전이는_예외(state, event): ...
```

`BANNED_COMBOS` 를 `TRANSITIONS` 에서 계산해 만들면 **이 테스트는 표가 무엇이든 통과한다.** 표에서 `(IDLE, SELECT)` 를 실수로 허용해도 그 조합이 금지 목록에서 빠질 뿐이라 테스트는 여전히 초록색이다. 구현으로 구현을 검사하는 전형적인 함정이다.

의미 있는 것은 **요구사항이 지목한 몇 개를 손으로 적는 것**이다. 이 저장소가 손으로 적은 것은 네 개다 — "돈 안 넣고 못 고른다", "손님 돈 있으면 점검 못 들어간다", "점검 중엔 동전 안 받는다", "판매 모드에선 보충 못 한다". 나머지 아홉 개는 표를 눈으로 읽으면 되고, 표가 한 화면인 이유가 그것이다.
:::

실제 실행 결과다.

```bash
uv run --python 3.14 --with pytest pytest -q
```

```text nolines
.............................                                            [100%]
29 passed in 0.03s
```

## 실행되는 자리

도메인이 다 됐으면 CLI는 짧다. 여기에 규칙을 넣지 않는 것이 요점이다.

```python title="vending/cli.py (발췌)"
def build(port: str | None) -> VendingMachine:
    """조립 지점. 진짜 하드웨어가 도메인과 만나는 유일한 곳."""
    dispenser: Dispenser = SerialDispenser(Path(port)) if port else FakeDispenser()
    vault = CoinBox({Coin.W500: 2, Coin.W100: 3})
    return VendingMachine(initial_slots(), vault, dispenser)


def handle(m: VendingMachine, cmd: str, args: list[str]) -> str:
    match cmd, args:
        case "coin", [value]:
            m.insert(Coin(int(value)))
            return f"투입 {m.balance}원"
        case "select", [code]:
            change = m.select(code)
            paid = sum(c * n for c, n in change.items())
            return f"{m.slot(code).name} 배출, 거스름돈 {paid}원 {_fmt(change)}"
        case "refund", []:
            coins = m.refund()
            return f"반환 {sum(c * n for c, n in coins.items())}원"
        # service / restock / collect / end / report 도 같은 모양이다
        case _:
            return f"모르는 명령: {cmd}"
```

`match` 문으로 명령을 가르는 것은 [1.8](#/control-flow)의 시퀀스 패턴이다. `case "coin", [value]` 는 **명령 이름과 인자 개수를 동시에** 검사한다. `if/elif` 로 쓰면 `len(args) != 1` 검사가 가지마다 붙는다.

`handle` 이 `print` 하지 않고 **문자열을 돌려주는 것**도 의도적이다. 출력은 `run` 한 곳에서만 한다. 그래서 나중에 결과를 파일로 보내라거나 JSON으로 내라는 요구가 붙어도 `handle` 은 안 바뀐다.

```bash
python -m vending < demo.txt
```

```text nolines
> coin 1000
  투입 1000원
> select A1
  Cola 배출, 거스름돈 100원 {100x1}
> coin 500
  투입 500원
> select A1
  거부: A1: 900원인데 500원 들어 있다
> coin 500
  투입 1000원
> refund
  반환 1000원
> service
  점검 모드
> restock B1 2
  B1 재고 2
> collect
  회수 2200원 {100x2, 500x2, 1000x1}
> end
  판매 모드
> report
  IDLE 잔액=0 매출=900 A1=1 A2=1 B1=2
```

**데모 입력에 실패 사례를 일부러 넣었다.** 네 번째 명령의 `거부:` 가 없으면 이 출력은 "잘 되는 경우만 보여 준" 것이 된다. README에 붙일 출력에는 반드시 거부 한 줄이 들어가야 한다([12.8](#/readme-submit)).

::: note `initial_slots()` 가 함수인 이유
```python
def initial_slots() -> list[Slot]:
    """호출할 때마다 새 Slot 을 만든다. Slot 은 가변이라 공유하면 안 된다."""
    return [Slot("A1", "Cola", 900, 2), ...]
```

모듈 상수 `SLOTS = [Slot(...), ...]` 로 두고 `list(SLOTS)` 를 넘기면 **리스트만 복사되고 `Slot` 객체는 공유된다.** 자판기를 두 개 만들면 한쪽에서 판 상품이 다른 쪽 재고에서도 줄어든다. 테스트가 하나만 돌 때는 절대 안 드러나고, 테스트를 두 개째 짜는 순간 앞 테스트의 결과가 뒤에 새어 든다.

이름과 참조의 문제([1.1](#/objects-names))가 과제형에서 나타나는 가장 흔한 형태다. **가변 객체를 담은 모듈 레벨 상수는 상수가 아니다.**
:::

## 안 만든 것들

여기까지 만든 것을 세어 보면 소스 515줄, 테스트 271줄, 패키지 파일 10개다. 과제형에서 **감점의 절반은 여기서 더 만들어서** 난다. 이 저장소가 의도적으로 만들지 않은 것들과 그 판단 근거다.

| 안 만든 것 | 만들면 언제 이득인가 |
| --- | --- |
| 상태별 클래스(State 패턴) | 상태마다 **데이터가 다르거나** 같은 동작이 다르게 작동할 때. 여기선 둘 다 아니다([12.3](#/state-machine)) |
| `Money` 값 객체 | 통화가 둘 이상이거나 소수점 반올림 규칙이 있을 때. 여기선 100원 단위 정수다 |
| 저장소(영속화) 계층 | 요구사항에 저장이 있을 때. 지금 만들면 구현이 하나뿐인 인터페이스가 생긴다([12.10](#/case-domain-repo)) |
| 시계 주입 | 시각을 **기록하거나 판단에 쓸 때.** 이 명세에는 시각이 한 번도 안 나온다 |
| 이벤트 로그 / 이력 | "지나온 상태를 조회하라"가 요구사항일 때. 여기엔 없다 |
| 설정 파일 · 환경변수 | 설정할 것이 슬롯 구성 하나뿐이면 코드가 설정이다 |
| 상태 머신 라이브러리 | 전이표가 8줄이다. 의존성 하나가 평가자의 실행을 막을 위험이 더 크다 |
| `async` | 하드웨어 호출이 밀리초 단위 동기 명령이다. 동시 손님이 없다 |

::: danger 확장 포인트를 미리 뚫는 것이 가장 흔한 감점이다
"나중에 카드 결제가 붙을 수 있으니까" `PaymentMethod` 추상을 만들고, "나중에 커피 자판기도 되니까" `Product` 계층을 만든다. 요구사항에 없는 두 번째 구현을 위해 만든 인터페이스는 **거의 항상 틀린 모양으로 만들어진다.** 두 번째 구현을 실제로 써 보기 전에는 무엇이 공통인지 알 수 없기 때문이다.

평가자가 읽는 방식은 이렇다. **요구사항 8문장 → 개념 20개**를 보면 "요구사항을 이해 못 했거나, 이해했는데 자기 취향을 얹었다"로 읽힌다. 둘 다 같이 일하기 어려운 신호다.

반대 방향은 훨씬 싸다. 이 저장소에 카드 결제를 붙이려면 `Dispenser` 옆에 포트를 하나 더 만들고 `select` 를 고치면 된다. **필요해졌을 때 만드는 비용은 미리 만들어 놓고 틀린 것을 고치는 비용보다 항상 작다.** 그리고 지금 안 만든 이유를 README에 한 줄 적어 두면, 평가자는 그것을 "생각을 안 했다"가 아니라 "생각하고 안 했다"로 읽는다.
:::

## 제출물

```text nolines
vending-task/
├── README.md
├── conftest.py                  비어 있음. tests 에서 vending 을 import 하게 한다
├── demo.txt                     README 에 붙인 출력을 재현하는 입력
├── pyproject.toml
├── vending/
│   ├── __init__.py
│   ├── __main__.py              python -m vending 의 진입점
│   ├── cli.py                   명령 해석, 조립, 출력
│   ├── coins.py                 화폐와 금고. 자판기를 모른다
│   ├── errors.py                도메인 예외
│   ├── fakes.py                 가짜 배출기 셋
│   ├── hardware.py              진짜 배출기. 장치가 여기에만
│   ├── machine.py               판매 규칙. ports 만 안다
│   ├── ports.py                 Protocol 로 정의한 경계
│   └── states.py                상태·사건·전이표
└── tests/
    ├── test_coins.py
    └── test_machine.py
```

디렉터리는 둘이다. [12.7](#/project-structure)의 규모 C에 해당하고, 파일이 열 개로 늘었을 뿐 깊이는 그대로다. 빈 `conftest.py` 가 푸는 문제는 [12.1](#/takehome-eval)에 있다.

README 전문의 형식은 [12.8](#/readme-submit)에 있으니 반복하지 않는다. 이 과제에서 **가장 값어치 있는 칸**만 옮긴다.

````text nolines
## 5. 설계 결정

**① 투입 동전을 금고에 바로 넣지 않고 에스크로에 둔다.**
요구사항 6이 "투입 금액 전액 반환"이라서, 판매가 확정되기 전까지 손님 돈과
자판기 돈을 섞지 않는 쪽을 골랐다. 반환 레버는 에스크로를 그대로 비우면 끝이고,
금고를 건드리지 않으므로 반환이 금고 잔고를 틀리게 만들 수 없다.
대가는 select 에서 거스름돈 재원을 계산할 때 금고와 에스크로를 합쳐야 한다는 것이다.

**② 거스름돈 재원에 방금 넣은 동전을 포함한다.**
명세에 없어서 정했다. 실제 자판기가 그렇게 동작하고, 포함하지 않으면 "1000원 넣고
900원짜리를 사려는데 금고에 100원이 없어서 거절"이 훨씬 자주 난다.
test_방금_넣은_동전도_거스름돈_재원이_된다 가 이 결정을 고정한다.

**③ 검증을 전부 끝낸 뒤에 하드웨어를 부른다.**
select 는 슬롯·재고·잔액·거스름돈 구성까지 확인한 다음에야 dispense 를 호출한다.
그래서 거스름돈을 못 만들거나 잔액이 모자라면 상품도 안 나가고 상태도 안 바뀐다.
반대 순서(배출 먼저)로 짜면 되돌릴 방법이 없다.

**④ 상태 전이를 딕셔너리 표 8줄로 적었다.**
상태 3 × 사건 7 = 21가지 중 8가지만 허용된다. 표에 없으면 InvalidTransition 이다.
상태별 클래스를 만들면 클래스 3개와 메서드 자리 21개가 이 8줄을 대신하는데,
상태마다 다른 데이터도 다른 동작도 없어서 이득이 없다.

**⑤ 저장·시계·설정 계층을 만들지 않았다.**
명세에 영속화도, 시각 기록도, 설정 파일도 없다. 판매 시각을 남겨야 하면
VendingMachine 생성자에 시계를 주입하고 select 끝에서 기록한다 — machine.py 한 파일만 바뀐다.

## 6. 알려진 한계

- **상품이 나간 뒤 동전 반환이 실패하면 손님이 거스름돈을 못 받는다.** 이때
  ChangeReturnFailed 에 못 준 금액이 실려 올라오지만, 자판기가 그 빚을 기억하지는 않는다.
  실제 기기라면 이 자리에 비휘발성 로그와 관리자 알림이 필요하다.
- 동시에 두 사람이 조작하는 상황을 가정하지 않았다. 락이 없다.
- 금고 동전 개수의 상한(호퍼 용량)을 모델링하지 않았다.
- 전원이 꺼지면 에스크로에 있던 손님 돈이 사라진다. 영속화가 없다.
- 가격은 100원 단위만 가정한다. 50원 단위가 들어오면 CHANGE_DENOMS 와 요금 검증을 같이 고쳐야 한다.
````

다섯 개의 결정이 전부 **"대안이 있었고 이걸 골랐다"** 형태다. 그리고 ⑤는 **안 만든 것**에 대한 결정이다. 안 만든 것을 적는 칸이 있어야 오버엔지니어링을 피한 판단이 평가자에게 도달한다. 적지 않으면 그건 그냥 빈자리다.

### 제출 직전 3분

깨끗한 복제본에서 이 네 줄을 순서대로 친다.

```bash
python -c "import vending; print(vending.__file__)"   # None 이면 __init__.py 가 없다
python -m vending < demo.txt                          # README 의 출력과 같은가
python -m pytest -q                                   # 평가자가 실제로 치는 명령
git status --porcelain                                # 잔여물이 없는가
```

두 번째 줄이 특히 중요하다. **README에 붙인 출력과 지금 나오는 출력이 한 글자라도 다르면 그 README는 거짓말이다.** 코드를 고치고 README를 안 고친 흔적은 평가자가 가장 빨리 찾아내는 것 중 하나다. `demo.txt` 를 저장소에 넣어 둔 이유가 이 확인을 3초로 만들기 위해서다.

## 요약

- 과제형의 완결 예제는 **안쪽부터 만든다.** 값 → 규칙 → 경계 → 입출력 → README. 어느 시점에 끊겨도 그때까지는 테스트가 통과한 상태여야 한다.
- **명세의 구멍을 먼저 목록으로 만들어라.** 메운 것보다 메웠다고 밝힌 것이 평가된다. 이 과제에서는 다섯 개였고 전부 README에 들어갔다.
- 전이표는 **"시도할 수 있는가"만** 답한다. "성공하는가"는 도메인 규칙이다. 둘을 섞으면 상태가 폭발한다.
- **검증과 커밋을 분리하고, 바깥 세상을 건드리는 호출을 함수의 끝으로 몰아라.** 그러면 되돌리기 코드가 존재할 필요가 없어진다 — 과제형에서 가장 안 짜지는 코드가 그것이다.
- `IntEnum` 은 **값이 산술에 쓰일 때만.** 그리고 정수와 섞이는 대가는 경계에서 `isinstance` 로 한 번 막아 치른다.
- 가짜 구현이 **셋**인 이유는 속도가 아니다. 성공 경로만 있는 가짜는 요구사항 7("하드웨어 없이 테스트")의 절반만 만족시킨다.
- **되돌릴 수 없는 구멍은 반드시 남는다.** 숨기지 말고, 예외에 정보를 실어 올리고, README 맨 위에 적어라.
- 감점의 절반은 **더 만들어서** 난다. 안 만든 것과 그 이유를 적는 칸이 README에 있어야 한다.

::: quiz 과제 — 이 저장소를 직접 고쳐라
전부 **코드를 짜거나 설계 판단을 문장으로 적는** 과제다. 1·2·4는 테스트를 먼저 쓰고 시작해라.

**1. 거스름돈 부족 램프 (30분)**
요구사항이 하나 추가됐다. *"각 슬롯을 지금 살 수 있는지 램프로 표시한다."* `VendingMachine.can_serve(code) -> bool` 을 구현해라. 참이 되는 조건은 셋이다 — 재고가 있고, 현재 투입 금액이 가격 이상이고, 그 차액을 거스름돈으로 만들 수 있다.
- `select` 와 로직이 중복되지 않게 해라. 어디를 공통 함수로 뽑을 것인지가 이 과제의 본론이다.
- `can_serve` 가 금고를 바꾸지 않는다는 것을 테스트로 못 박아라.

**2. 50원 동전 (40분)**
`Coin.W50 = 50` 을 추가하고 가격을 50원 단위까지 허용해라.
- `plan_change` 의 그리디가 여전히 옳은가. **옳다면 왜인지 두 문장으로 적고, 아니라면 반례를 만들어라.**
- 고쳐야 하는 파일이 몇 개인가. 세 개를 넘으면 원래 설계에 문제가 있었다는 뜻이다 — 어디였는지 적어라.

**3. 잘못된 설계 고르기 (설계 판단만, 15분)**
어떤 제출물이 요구사항 8을 이렇게 구현했다.

```python
class VendingMachine:
    def __init__(self, ...):
        self.is_maintenance = False
        self.has_money = False
        self.is_selling = False
```

이 설계로 표현 가능한 조합은 8가지고 실제로 존재할 수 있는 상태는 3가지다. **존재할 수 없는 조합 다섯 개를 전부 적고**, 그중 어느 것이 실제 버그로 나타날지 하나 골라 시나리오를 세 문장으로 써라.

**4. 반환 실패를 기억하는 자판기 (60분)**
README의 첫 번째 알려진 한계를 실제로 메워라. `ChangeReturnFailed` 가 났을 때 못 준 금액을 남기고, 다음 점검 모드에서 관리자가 조회할 수 있어야 한다.
- **먼저 판단하고 시작해라.** 이걸 `machine.py` 안의 리스트로 둘 것인가, 새 포트를 만들 것인가. 두 안의 트레이드오프를 세 줄로 적은 뒤 하나를 골라라.
- 요구사항에 없는 이 기능을 실제 4시간 과제에서 구현하는 것이 옳은 판단인가. 답을 한 문장으로 적어라.

**5. 확장 과제 — 반대 방향으로 (30분)**
이 저장소에서 `TRANSITIONS` 와 `MachineEvent` 를 지우고(`MachineState` 는 남긴다), 같은 규칙을 각 메서드 안의 `if` 문으로 다시 써라. 그리고 다음 셋을 비교해서 적어라.
- 전체 규칙을 파악하는 데 봐야 하는 줄 수
- "점검 중에는 동전을 안 받는다"를 추가할 때 고치는 자리의 개수
- 29개 테스트 중 몇 개가 그대로 통과하는가

**세 번째가 핵심이다.** 테스트가 구현이 아니라 동작에 붙어 있으면 구조를 통째로 바꿔도 대부분 그대로 통과해야 한다. 통과하지 않는 것이 있다면 그 테스트는 무엇을 검사하고 있었던 것인가.
:::

**다음 절**: [12.10 완결 예제 II — 도메인과 저장소 분리](#/case-domain-repo) — 이번엔 규칙을 저장 방식에서 떼어 내고, 메모리와 파일 저장소를 같은 `Protocol` 로 갈아 끼운다.
