# 12.2 요구사항에서 모델로

::: lead
과제형 문제의 요구사항은 대개 A4 한 장이다. 그런데 그 한 장을 읽고 나면 제출물이 두 갈래로 갈린다. 클래스를 하나도 안 만들고 전역 딕셔너리와 함수 열 개로 밀어붙이거나, `Manager`·`Service`·`Handler` 를 다섯 개 만들어 놓고 정작 요구사항의 절반을 빠뜨린다. 이 절은 그 사이를 잇는 **기계적인 절차**를 다룬다. 요구사항 문장에서 명사와 동사를 뽑아 모델로 옮기는 순서, 그리고 그보다 중요한 것 — 무엇을 만들지 **않을지** 정하는 기준이다. 설계에 정답은 없다. 그러나 **근거 없는 선택은 리뷰어에게 바로 보인다.**
:::

## 요구사항 한 장, 그리고 흔한 두 개의 오답

이 절 내내 쓸 요구사항이다. 소리 내어 두 번 읽어라.

> **[과제] 사내 비품 재고 관리**
>
> 사무실 비품 재고를 관리하는 프로그램을 작성하라. 외부 시스템 연동은 없고, 데이터는 프로그램이 도는 동안만 유지되면 된다.
>
> 1. 비품은 **품목 코드**, **이름**, **현재 수량**, **최소 보유 수량**을 가진다.
> 2. 담당자는 비품을 **입고**(수량 증가)하고 **출고**(수량 감소)할 수 있다.
> 3. **현재 수량보다 많은 수량은 출고할 수 없다.**
> 4. 현재 수량이 최소 보유 수량 미만인 품목은 **보충 대상**으로 보고된다.
> 5. 모든 입출고는 **기록**으로 남고, **품목별 입출고 이력**을 조회할 수 있다.

다섯 문장이다. 여기서 실제로 나오는 오답 두 가지를 먼저 보자. 둘 다 동작은 한다.

**오답 1 — 전역 상태와 함수 뭉치.**

```python title="bad_flat.py (조각)"
STOCK = {}          # 코드 -> 수량
MIN = {}            # 코드 -> 최소 보유 수량
LOG = []            # (코드, 종류, 수량)


def register(code, name, qty, min_qty):
    STOCK[code] = qty
    MIN[code] = min_qty          # name 은 받아 놓고 버린다


def issue(code, amount):
    if STOCK[code] < amount:
        return False             # 실패를 False 로 알린다
    STOCK[code] -= amount
    LOG.append((code, "OUT", amount))
    return True
```

딕셔너리 둘과 리스트 하나가 **같은 코드 키로 따로 산다.** `STOCK` 과 `MIN` 은 코드로 찾고, `LOG` 는 튜플 안에 코드를 끼워 넣어 나중에 훑는다. 셋을 묶어 주는 것이 아무것도 없다. 하나만 갱신하고 나머지를 잊는 순간 조용히 깨진다. `name` 은 인자로 받고 저장하지 않는다 — 요구사항 1번이 이미 빠졌다. 그리고 실패가 `False` 로 돌아오므로, 호출자가 반환값을 안 보면 **재고가 안 줄었는데도 성공한 것처럼 흘러간다**([12.5](#/error-design)).

**오답 2 — 미리 만든 층.**

```python title="bad_layers.py (조각 — 구조만 본다)"
class InventoryManager: ...
class InventoryService: ...
class InventoryRepository: ...
class ItemFactory: ...
class ItemValidator: ...
class EventBus: ...
```

요구사항에 저장소는 없다. 팩토리로 만들 것도 하나뿐이다. 이벤트를 구독하는 쪽은 존재하지 않는다. **여섯 개 중 요구사항 문장이 부르는 것은 하나도 없다.** 이건 실력의 과시가 아니라 요구사항을 안 읽었다는 증거로 읽힌다.

두 오답의 뿌리는 같다. **요구사항 문장과 코드 사이에 절차가 없다.** 절차를 넣자.

```text nolines
  [1] 명사에 밑줄을 긋는다        -> 후보 목록
  [2] 명사를 거른다               -> 엔티티 / 값 객체 / 속성 / 버릴 것
  [3] 동사를 배치한다             -> 누가 그 규칙을 아는가
  [4] 요구사항 문장을 테스트 이름으로 다시 쓴다
```

## 1단계 — 명사에 밑줄을 긋는다

기계적으로 한다. 판단하지 말고 **전부** 적어라. 거르는 건 다음 단계다.

> 비품, 품목 코드, 이름, 현재 수량, 최소 보유 수량, 담당자, 입고, 출고, 보충 대상, 기록, 입출고 이력, 프로그램, 사무실

13개다. 여기서 클래스가 13개 나오면 오답 2가 된다. 이 목록은 **후보**일 뿐이고, 대부분은 탈락한다.

::: tip 밑줄은 진짜로 그어라
머릿속으로 하지 마라. 요구사항을 텍스트 파일에 복사해 놓고 명사에 `**` 를, 동사에 `_` 를 붙여라. 5분 걸린다. 이 5분이 제출 후에 "아, 이력 조회를 안 만들었네"를 막는다. 과제형에서 가장 흔한 감점은 설계 실패가 아니라 **요구사항 누락**이다([12.1](#/takehome-eval)).
:::

## 2단계 — 명사를 거른다

명사는 넷 중 하나로 간다. 순서대로 세 질문을 던진다.

```text nolines
  Q1. 이 명사가 시간이 지나면서 변하는가?
      no   ->  Q2
      yes  ->  Q3

  Q2. 값이 같으면 같은 것으로 봐도 되는가?
      yes  ->  값 객체(frozen dataclass) 또는 그냥 필드
      no   ->  Q3

  Q3. 이 명사만의 규칙이 요구사항에 적혀 있는가?
      yes  ->  엔티티 — 클래스로 만든다
      no   ->  다른 것의 필드로 흡수한다
              (흡수할 곳조차 없으면 그 명사는 버린다)
```

Q3이 핵심이다. **규칙이 없는 명사는 클래스가 될 이유가 없다.** 앞의 13개를 통과시키면 이렇게 된다.

| 명사 | 판정 | 근거 |
| --- | --- | --- |
| 비품 | **엔티티** `Item` | 코드로 식별되고 수량이 변한다. 규칙 3·4를 자기가 안다 |
| 품목 코드 | `Item` 의 필드 | 변하지 않고, 자기 규칙이 없다 |
| 이름, 현재 수량, 최소 보유 수량 | `Item` 의 필드 | 같음 |
| 기록 / 입출고 이력 | **값 객체** `Movement` | 한번 일어나면 변하지 않는다. 내용이 같으면 같은 기록이다 |
| 보충 대상 | `Item` 의 **파생 속성** | 저장할 상태가 아니라 수량에서 계산되는 값이다 |
| 입고, 출고 | 명사가 아니다 | 동사가 명사로 위장한 것. 3단계에서 다룬다 |
| 담당자 | **버린다** | 요구사항 어디에도 담당자를 **구분**하는 규칙이 없다 |
| 프로그램, 사무실 | **버린다** | 배경 설명이다 |

::: warn "담당자"를 클래스로 만들고 싶어질 때
요구사항 2번은 "담당자는 입고하고 출고할 수 있다"이다. 사람이 등장하니 `User` 를 만들고 싶어진다. 하지만 요구사항 전체를 뒤져도 **담당자를 서로 구별해야 하는 문장이 하나도 없다.** 누가 출고했는지 기록하라는 말도, 권한을 나누라는 말도 없다.

판정 기준은 하나다. **그 명사를 둘 이상 만들었을 때 서로 다르게 행동하는가.** 아니라면 그건 문장의 주어일 뿐 모델이 아니다. 나중에 "누가 출고했는가"가 요구사항에 추가되면 그때 `Movement` 에 필드 하나를 더한다. 그게 훨씬 싸다.
:::

그래서 남은 명사는 **`Item`, `Movement`, 그리고 이들을 담을 무언가** 셋뿐이다. 13개에서 셋이 됐다.

::: note 값 객체와 엔티티를 나누는 실용적인 기준
"두 개가 있는데 내용이 완전히 같다. 이걸 하나로 합쳐도 되는가?"

- 된다 → **값 객체.** 3월 1일에 A-1을 5개 입고한 기록이 두 개 있으면, 그건 두 번 입고한 것이고 둘은 서로 대체 가능하다. `@dataclass(frozen=True)` 로 만든다.
- 안 된다 → **엔티티.** 이름과 수량이 같아도 코드가 다르면 다른 비품이다. 식별자를 갖는다.

이 구분은 나중에 **저장소를 분리할 때** 다시 크게 쓰인다([12.10](#/case-domain-repo)).
:::

## 3단계 — 동사를 배치한다

동사에도 밑줄을 긋는다.

> 가진다, 입고한다, 출고한다, **출고할 수 없다**, 보고된다, 기록으로 남는다, 조회할 수 있다

이제 각 동사를 2단계에서 남긴 것 위에 올린다. 배치 기준은 **하나의 질문**이다.

> **이 규칙을 지키는 데 필요한 데이터가 어디에 있는가.**

"현재 수량보다 많이 출고할 수 없다"를 검사하려면 `quantity` 하나면 된다. 그건 `Item` 안에 있다 → `Item` 에 붙인다. "품목별 이력을 조회한다"는 전체 기록 목록이 필요하다. 그건 `Item` 하나가 못 본다 → 담는 쪽에 붙인다.

| 동사 | 붙는 곳 | 왜 |
| --- | --- | --- |
| 가진다 | `Item` 의 필드 선언 | 2단계에서 이미 흡수됐다. 메서드가 되지 않는 유일한 동사다 |
| 입고한다 / 출고한다 | `Item.receive` / `Item.issue` | 규칙에 필요한 데이터가 자기 안에 다 있다 |
| 출고할 수 없다 | `Item.issue` 안의 검사 | 같음 |
| 보충 대상이다 | `Item.needs_restock` | 자기 두 필드의 비교다 |
| 기록으로 남는다 | `Inventory` | 한 품목이 아니라 전체의 기록이다 |
| 이력을 조회한다 | `Inventory.history` | 같음 |
| *(품목을 등록한다)* | `Inventory.register` | **요구사항 문장에 없는 동사다.** 뒤에서 다룬다 |

마지막 행에 괄호가 붙은 이유를 짚고 가자. 위 여섯 행은 밑줄 그은 동사 일곱 개가 그대로 앉은 것이다. 마지막 행만 다르다 — **"등록한다"는 밑줄 목록에도, 요구사항 다섯 문장에도 없다.** 요구사항은 비품이 **이미 있다고 전제**하고 입출고만 말하기 때문이다. 그런데 `Inventory` 에 품목을 넣는 동작이 없으면 프로그램이 시작조차 못 한다. 이건 요구사항에서 뽑은 동사가 아니라 **모델을 세우다가 새로 필요해진 동사**다.

이런 동사는 반드시 표시해 둬라. 요구사항에 근거가 없다는 것은 **그 동작의 규칙도 요구사항에 없다**는 뜻이고, 그게 곧 결정할 거리가 된다 — 같은 코드로 두 번 등록하면? 뒤의 「요구사항의 구멍은 메우고, 반드시 적어라」에서 이 질문에 답한다.

여기서 **이름이 하나 새로 필요해졌다.** 품목들과 기록을 담는 그릇이다. `InventoryManager` 라고 부르고 싶은 충동을 참아라. 그것이 하는 일은 "재고를 담고 있는 것"이고, 그 이름은 `Inventory` 다.

::: danger `~Manager`, `~Handler`, `~Processor`, `~Util` 은 생각을 멈춘 자리다
이 접미사들은 **책임을 정하지 못했다는 신호**다. `Manager` 는 무엇이든 넣어도 이름이 안 틀린다. 그래서 무엇이든 들어간다.

이름이 안 떠오르면 클래스를 만들 준비가 안 된 것이다. 그럴 땐 **그 클래스가 지키는 규칙을 한 문장으로 써 봐라.** "품목을 코드로 찾고, 일어난 입출고를 기록한다" — 그러면 이름은 `Inventory` 로 정해진다. 한 문장이 안 나오면 그 클래스는 없어도 된다.
:::

### 두 안 — 규칙을 `Item` 에 둘 것인가 `Inventory` 에 둘 것인가

여기가 실제로 갈리는 지점이다. **둘 다 정상적인 설계다.**

```python title="안 A — 규칙이 Inventory 에 (Item 은 데이터만, 발췌)"
@dataclass
class Item:
    code: str
    name: str
    quantity: int = 0
    min_quantity: int = 0


class Inventory:
    def issue(self, code: str, amount: int) -> None:
        item = self._items[code]
        if amount <= 0:                            # 규칙 1
            raise ValueError(amount)
        if amount > item.quantity:                 # 규칙 2
            raise NotEnoughStock(code)
        item.quantity -= amount
        self._log.append(Movement(code, "OUT", amount))
```

```python title="안 B — 규칙이 Item 에 (발췌)"
@dataclass
class Item:
    code: str
    name: str
    quantity: int = 0
    min_quantity: int = 0

    def issue(self, amount: int) -> None:
        _check_positive(amount)
        if amount > self.quantity:
            raise NotEnoughStock(self.code, amount, self.quantity)
        self.quantity -= amount


class Inventory:
    def issue(self, code: str, amount: int) -> None:
        self._find(code).issue(amount)             # 규칙 위반이면 여기서 예외
        self._log.append(Movement(code, "OUT", amount))
```

| | 안 A | 안 B |
| --- | --- | --- |
| 코드 총량 | 조금 짧다 | 위임 한 줄이 더 생긴다 |
| 규칙 하나 추가 | `Inventory` 메서드가 길어진다 | `Item` 만 고친다 |
| 품목 종류가 늘 때 | `Inventory` 안에 `if` 사다리가 생긴다 | 필드/서브클래스로 흡수된다 |
| 단위 테스트 | `Inventory` 를 세워야 규칙을 테스트한다 | `Item` 하나만 만들면 된다 |
| 처음 읽는 사람 | 규칙이 한곳에 모여 있어 훑기 쉽다 | 규칙을 보려면 두 파일을 연다 |

**판단 기준은 이것이다.**

> **규칙이 한 개체 안에서 완결되면 그 개체에, 여러 개체를 봐야 하면 컬렉션에 둔다.**

"재고보다 많이 출고할 수 없다"는 `Item` 하나 안에서 끝난다 → 안 B. 반대로 "전체 품목 수는 100개를 넘을 수 없다"가 요구사항이라면 그건 `Item` 이 알 수 없다 → `Inventory` 에 둔다. 이 절은 안 B로 간다. 요구사항 3·4가 **둘 다 한 품목 안에서 완결**되기 때문이다.

::: perf "클래스를 나누면 느려진다"는 변명은 과제형에서 성립하지 않는다
출고 10만 번을 돌렸다. 품목 200개를 순회하며 1개씩 출고한다. **안 A와 안 B는 위에 실린 코드 그대로다** — 성공한 출고마다 `self._log.append(Movement(code, "OUT", amount))` 까지 한다. 그래서 기준선도 두 줄로 나눠 뒀다.

| 방식 | 10만 회 |
| --- | --- |
| `dict[code] -= 1` (규칙 없음, 기록 없음) | 3.9 ~ 4.3 ms |
| `dict[code] -= 1` + `Movement` 기록 | 31 ~ 35 ms |
| 안 A (`Inventory` 가 검사) | 35 ~ 40 ms |
| 안 B (`Item.issue` 호출) | 41 ~ 45 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

첫 줄과 마지막 줄만 보면 **10배**다. 여기서 "클래스로 나눴더니 10배 느려졌다"고 읽으면 정확히 틀린 결론을 얻는다. 두 번째 줄이 그 이유다. **딕셔너리 한 줄짜리 코드에 기록 한 줄만 붙여도 4 ms 가 33 ms 가 된다.** 설계와 아무 상관 없는 이 한 줄이 전체 격차 약 40 ms 중 30 ms 가까이를 먹는다.

설계가 실제로 만든 차이는 나머지다. **같은 일을 하는 것끼리 비교해야 보인다.**

- 안 A는 `dict` + 기록보다 2~5 ms 느리다. 규칙 검사 두 줄과 메서드 호출 한 번의 값이다.
- 안 B는 안 A보다 5~8 ms 느리다. `Item.issue` 로 한 번 더 위임하는 값이다. 10만 번에 그 정도면 **출고 한 번에 60 나노초 수준이다.**

과제형 데이터가 수백~수천 건이면 두 안의 차이는 통째로 마이크로초 단위이고, 사람이 인지할 수 없다. 자릿수가 갈리지 않는 차이를 설계 근거로 쓰지 마라. 진짜 병목은 이런 데서 안 나온다([5.1](#/profiling)).

그 30 ms 는 어디서 나오나. `Movement` 는 `@dataclass(frozen=True)` 다. `frozen=True` 는 `__setattr__` 를 막으므로 생성된 `__init__` 이 필드마다 평범한 대입 대신 `object.__setattr__(self, ...)` 를 부른다. 10만 개를 만드는 데만 28~31 ms 다. 같은 필드를 일반 `dataclass` 로 만들면 11.5~12.4 ms, 튜플이면 5.5~5.7 ms — **불변성의 값은 여기서 치른다.** 그래도 이것이 `Movement` 를 값 객체로 판정한 것을 뒤집지는 않는다. 과제형이 만드는 기록은 10만 개가 아니라 수십 개고, 30 ms 를 아끼려고 `==` 비교가 그대로 명세가 되는 성질을 버릴 이유가 없다.

같은 논리가 반대 방향으로도 성립한다. **성능이 이유가 안 되므로, 안 B를 고르는 근거도 "빠르다"가 아니라 "규칙이 데이터 옆에 있어서 고칠 때 한 곳만 본다"여야 한다.**
:::

### 요구사항이 하나 늘면 어떻게 되는가

리뷰어가 실제로 궁금해하는 건 "지금 동작하는가"보다 "다음 요구사항이 왔을 때 어디를 고치는가"다. 가상의 추가 요구사항을 넣어 보자.

> 6. 냉장 비품은 **최대 보유 수량**이 있고, 이를 초과하는 입고는 거부한다.

안 B에서는 `Item` 만 열면 된다.

```python title="delta_full.py — 추가된 것은 필드 하나와 검사 두 줄"
from dataclasses import dataclass

from inventory.errors import InventoryError, NotEnoughStock


class OverCapacity(InventoryError):
    pass


@dataclass
class Item:                                          # 안 B 의 Item 에서 달라진 곳만 표시
    code: str
    name: str
    quantity: int = 0
    min_quantity: int = 0
    max_quantity: int | None = None                  # (1) 추가된 필드

    def receive(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError(amount)
        if self.max_quantity is not None and self.quantity + amount > self.max_quantity:
            raise OverCapacity(self.code)            # (2) 추가된 규칙 — Item 안에서 끝난다
        self.quantity += amount

    def issue(self, amount: int) -> None:            # 그대로
        if amount <= 0:
            raise ValueError(amount)
        if amount > self.quantity:
            raise NotEnoughStock(self.code, amount, self.quantity)
        self.quantity -= amount


fridge = Item("C-9", "우유", quantity=8, max_quantity=10)
try:
    fridge.receive(5)
except OverCapacity as e:
    print("거부:", type(e).__name__, e)
fridge.receive(2)
print("현재 수량:", fridge.quantity)
```

```text nolines
거부: OverCapacity C-9
현재 수량: 10
```

`Inventory` 는 **한 글자도 안 바뀐다.** 안 A였다면 `Inventory.receive` 가 길어지고, 그 메서드를 테스트하려면 매번 `Inventory` 를 세워야 한다. 이 차이가 규칙 두세 개에서는 안 보이다가 열 개쯤에서 갈린다.

## 클래스가 아니라 함수로 충분할 때

모델링을 배운 직후에 가장 자주 하는 실수는 **함수로 끝날 것을 클래스로 만드는 것**이다. 아래가 그 전형이다.

```python
# ❌ 상태가 없다. __init__ 이 인자를 저장만 하고, 메서드가 하나뿐이다.
class ReorderCalculator:
    def __init__(self, item):
        self.item = item

    def calculate(self):
        return max(0, self.item.min_quantity * 2 - self.item.quantity)

need = ReorderCalculator(item).calculate()

# ✅ 이건 그냥 함수다
def reorder_amount(item: Item) -> int:
    return max(0, item.min_quantity * 2 - item.quantity)

need = reorder_amount(item)
```

판정표다.

| 신호 | 정답 |
| --- | --- |
| `__init__` 이 인자를 저장만 하고 공개 메서드가 하나 | **함수** |
| 인스턴스가 프로그램 전체에 하나뿐이고 필드가 없다 | **함수** (또는 모듈) |
| 입력이 들어가면 출력이 나오고 그사이 상태가 없다 | **함수** |
| 필드가 있고, 그 필드가 호출 사이에 변한다 | 클래스 |
| 같은 데이터에 붙는 규칙이 셋 이상이다 | 클래스 |
| 같은 모양의 데이터를 여러 개 만든다 | `dataclass` |

::: tip `dataclass` 가 클래스와 함수 사이의 정확한 중간이다
필드 네 개를 묶고 싶은데 규칙은 아직 없다면 `@dataclass` 로 시작해라. 나중에 규칙이 생기면 **그 자리에 메서드를 추가하면 된다.** 처음부터 완성된 클래스를 설계하려고 하지 마라. `dataclass` 의 옵션과 함정은 [2.6](#/dataclasses)에 있다.

반대로 **필드가 두 개 이하이고 규칙이 없으면** `NamedTuple` 이나 그냥 튜플이 낫다([2.5](#/typed-containers)).
:::

::: danger dataclass 의 기본 `__eq__` 는 엔티티에 틀린 의미를 준다
`@dataclass` 는 **모든 필드를 비교하는** `__eq__` 를 만든다. 그건 값 객체의 의미론이다. 엔티티에 그대로 쓰면 이렇게 된다.

```pyrepl
>>> from dataclasses import dataclass
>>> @dataclass
... class Item:
...     code: str
...     name: str
...     quantity: int
...
>>> Item("A-1", "A4 용지", 5) == Item("A-1", "A4 용지", 3)
False
>>> shelf = [Item("A-1", "A4 용지", 5)]
>>> Item("A-1", "A4 용지", 5) in shelf
True
```

**같은 비품인데 수량이 달라졌다고 다른 것이 됐다.** `list.remove()` 나 `in` 으로 품목을 찾는 코드는 재고가 바뀌는 순간 못 찾는다. 게다가 가변 `dataclass` 는 해시가 없다.

```pyrepl
>>> {Item("A-1", "A4 용지", 5)}
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    {Item("A-1", "A4 용지", 5)}
TypeError: cannot use 'Item' as a set element (unhashable type: 'Item')
```

해결책은 `__eq__` 를 손보는 게 **아니다.** 그건 증상 치료다. **엔티티는 리스트가 아니라 `dict[식별자, 엔티티]` 로 담아라.** 그러면 조회가 $O(1)$ 이 되고([1.6](#/dict)) 동등성 비교가 아예 필요 없어진다. 정말 리스트에 담아야 한다면 그때 `field(compare=False)` 로 변하는 필드를 비교에서 빼라.
:::

## 하나의 클래스가 너무 많은 걸 안다는 신호

"책임을 나눠라"는 조언은 실행 가능하지 않다. **관찰 가능한 신호**로 바꾼다.

```python title="이 클래스는 무엇을 하는 클래스인가 (조각 — 구조만 본다)"
class InventoryManager:
    def register_item_and_log(self, code, name, qty): ...
    def issue_and_notify(self, code, amount): ...
    def load_from_csv(self, path): ...
    def save_to_csv(self, path): ...
    def print_restock_report(self): ...
    def calculate_reorder_amount(self, code): ...
    def validate_code_format(self, code): ...
```

여기에 신호가 다섯 개 들어 있다.

1. **메서드 이름에 `and` 가 있다.** `register_item_and_log` 는 두 가지를 한다고 이름이 자백한다.
2. **입출력이 계산과 섞여 있다.** `print_restock_report` 는 보충 목록 계산과 출력 형식을 동시에 갖는다. 그래서 이 로직은 **표준 출력을 가로채지 않으면 테스트할 수 없다.**
3. **저장 방식이 도메인에 박혀 있다.** `load_from_csv` 때문에 이 클래스를 테스트하려면 CSV 파일이 필요하다. 경계를 끊는 법은 [12.4](#/boundaries-di)에서 다룬다.
4. **필드를 쓰는 무리가 갈린다.** `validate_code_format` 은 인스턴스 필드를 하나도 안 쓴다. 그건 이 클래스에 있을 이유가 없는 함수다.
5. **서로 무관한 이유로 같은 파일을 고치게 된다.** 출력 형식이 바뀌어도, 저장 형식이 바뀌어도, 재고 규칙이 바뀌어도 전부 이 클래스다.

::: tip 가장 빨리 감지되는 신호는 테스트 준비 코드다
"출고하면 수량이 준다"를 테스트하는데 CSV 임시 파일을 만들고 출력을 가로채야 한다면, **그 클래스가 너무 많은 걸 알고 있다.** 테스트의 준비(given) 부분이 검증하려는 것과 무관한 세팅으로 길어지는 것 — 이게 설계 문제를 가장 먼저, 가장 정직하게 알려주는 신호다([12.6](#/test-strategy)).
:::

## 요구사항에 없는 것은 만들지 마라

과제형에서 오버엔지니어링은 **가산점이 아니라 감점**이다. 이유는 감정적인 게 아니다.

- 요구사항에 없는 코드도 **읽히고 평가된다.** 리뷰어는 그 앞에서 "왜 있지?"를 묻는다.
- 그 코드도 테스트가 없으면 감점 대상이 된다. 있으면 있는 대로 시간을 먹는다.
- README에 설명해야 한다. 설명 못 하면 "안 쓰는 코드를 남긴 사람"이 된다.
- 무엇보다, 그 시간에 **요구사항 5번을 마저 만들 수 있었다.**

이번 과제에서 만들지 말아야 할 목록이다. 전부 실제로 자주 등장한다.

| 만들고 싶어지는 것 | 요구사항의 근거 | 판정 |
| --- | --- | --- |
| `Repository` 추상화 | 저장 요구 자체가 없다 | ❌ |
| CSV·JSON 저장 | "실행 중에만 유지되면 된다" | ❌ |
| `User` / 권한 | 담당자를 구분하는 규칙이 없다 | ❌ |
| 이벤트 버스, 옵저버 | 알림 요구가 없다 | ❌ |
| 설정 파일, 로깅 프레임워크 | 언급 없음 | ❌ |
| `ItemFactory` | 만드는 방법이 하나뿐이다 | ❌ |
| 예외 계층 (`InventoryError` 뿌리) | 요구사항 3이 실패를 요구한다 | ✅ 얕게 |
| 이력 조회 | 요구사항 5 | ✅ |

::: warn "확장 가능하게 설계하라"는 문장은 지금 만들라는 뜻이 아니다
요구사항에 이 문장이 있으면 대부분 층을 쌓기 시작한다. 그건 오독이다. 미리 만든 확장점이 왜 감점으로 읽히는지는 [12.1](#/takehome-eval)에서 다뤘다. 여기서는 **그 대신 무엇을 하는가**만 본다. 셋이다.

1. **바뀔 지점에 이름이 붙어 있는가.** 나중에 저장소가 생긴다면, 지금 `Inventory` 가 그 자리를 이미 차지하고 있으면 된다. 인터페이스는 필요해질 때 뽑는다.
2. **바뀔 것과 안 바뀔 것이 섞여 있지 않은가.** 요금 계산과 출력 형식이 한 함수에 있으면 안 된다.
3. **그 판단을 README에 적었는가.** "지금은 메모리 저장만 필요해서 `Inventory` 하나로 두었다. 영속화가 필요하면 `Inventory` 를 Protocol로 뽑고 구현을 갈아 끼운다" — **이 한 문장이 추상 클래스 다섯 개보다 높게 평가된다**([12.8](#/readme-submit)).

Protocol을 실제로 뽑는 시점과 방법은 [12.4](#/boundaries-di), 저장소를 갈아 끼우는 완결 예제는 [12.10](#/case-domain-repo)에 있다.
:::

::: note YAGNI 는 게으름이 아니다
"You Aren't Gonna Need It." 이 원칙이 말하는 것은 "설계하지 마라"가 아니라 **"추측으로 만든 유연성은 대개 틀린 방향이다"** 이다. 실제로 요구사항이 추가될 때, 미리 만들어 둔 확장점이 정확히 그 자리인 경우는 드물다. 대신 안 맞는 확장점을 **걷어내는 비용**이 추가된다. 앞의 `max_quantity` 예시를 보라 — 미리 아무것도 안 만들어 뒀는데 필드 하나와 두 줄로 끝났다.
:::

## 요구사항의 구멍은 메우고, 반드시 적어라

다섯 문장짜리 요구사항에는 반드시 구멍이 있다. **이번 요구사항에서 답이 안 적힌 것들이다.**

- 출고 수량으로 `0` 이나 음수가 들어오면?
- 같은 품목 코드로 두 번 등록하면?
- 없는 품목 코드로 출고하면?
- 최소 보유 수량과 **정확히 같을** 때 보충 대상인가? (요구사항은 "미만"이라고 했다 → 아니다)
- 거부된 출고도 이력에 남는가?

여기서 하지 말아야 할 두 가지가 있다. **하나, 질문을 못 봤다고 넘어가는 것. 둘, 요구사항에 없는 정교한 정책을 발명하는 것.** 할 일은 [12.1](#/takehome-eval)에서 원칙으로 말한 그것이다.

> **가장 단순한 쪽으로 결정하고, 결정했다는 사실을 코드와 README에 남긴다.**

문제는 그 원칙을 아는 것이 아니라 **구멍을 발견하는 것**이다. 2·3단계가 그 도구다. 명사와 동사를 표로 옮기고 나면, 표의 빈칸이 곧 결정할 것이 된다. 이번 요구사항의 결정은 다음과 같다.

| 구멍 | 결정 | 근거 |
| --- | --- | --- |
| 0 이하 수량 | `ValueError` | 도메인 규칙 위반이 아니라 호출자의 잘못이다 |
| 코드 중복 등록 | `ValueError` | 조용히 덮어쓰면 재고가 사라진다 |
| 없는 코드 | `ItemNotFound` | 도메인 예외. 호출자가 구분해서 잡을 수 있다 |
| 최소 수량과 같을 때 | 보충 대상 **아님** | 요구사항이 "미만"이라고 썼다 |
| 거부된 출고 | 이력에 **안 남김** | 일어나지 않은 일이다 |

::: tip 마지막 줄이 실제로 점수를 만든다
"거부된 출고는 이력에 남기지 않는다"는 요구사항에 없다. 그래서 **테스트로 남겨야 한다.** 그 테스트 하나가 리뷰어에게 "이 사람은 요구사항의 빈틈을 인지하고 결정했다"를 증명한다. 결정 자체가 반대여도 상관없다. **인지하지 못한 것과 결정한 것의 차이가 평가받는다.**
:::

## 모델이 요구사항을 담았는지 확인하는 법

절차의 마지막 단계다. **요구사항 문장을 그대로 테스트 이름으로 옮긴다.** 옮겨지지 않는 문장이 있으면 모델이 그 요구사항을 표현하지 못한 것이다.

여기까지 나온 최종 구조다. 과제 규모에 맞는 최소 형태다([12.7](#/project-structure)).

```text nolines
inventory-task/
├── inventory/
│   ├── __init__.py
│   ├── errors.py       예외 계층
│   ├── models.py       Item, Movement
│   └── store.py        Inventory
├── tests/
│   ├── test_item.py
│   └── test_inventory.py
├── pyproject.toml      pythonpath = ["."] — tests 에서 inventory 를 import 할 수 있게 한다
└── README.md
```

```toml title="pyproject.toml — 지금 필요한 것은 이 세 줄뿐이다"
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`pythonpath` 한 줄이 왜 필요한지, 그리고 같은 일을 하는 **빈 `conftest.py`** 대신 왜 이쪽인지는 [12.1](#/takehome-eval)에서 실측과 함께 정했다 — 요약하면 평가자가 파일 하나를 열어 실행 방법을 알 수 있기 때문이다. 구조를 고르는 기준 전체는 [12.7](#/project-structure)에 있다. 여기서는 **명사와 동사가 파일 위에 어떻게 앉는지**만 본다 — `models.py` 는 2단계의 산출물이고, `store.py` 는 3단계에서 새로 필요해진 그릇이다.

```python title="inventory/errors.py"
class InventoryError(Exception):
    """이 도메인이 거부한 요청. 호출자가 잡을 하나의 뿌리."""


class ItemNotFound(InventoryError):
    pass


class NotEnoughStock(InventoryError):
    def __init__(self, code: str, requested: int, available: int) -> None:
        super().__init__(f"{code}: {requested}개 요청, 재고 {available}개")
        self.code = code
        self.requested = requested
        self.available = available
```

```python title="inventory/models.py"
from dataclasses import dataclass

from .errors import NotEnoughStock


@dataclass
class Item:
    """비품 하나. code 로 식별되고 quantity 가 변한다 — 엔티티."""

    code: str
    name: str
    quantity: int = 0
    min_quantity: int = 0

    def receive(self, amount: int) -> None:
        _check_positive(amount)
        self.quantity += amount

    def issue(self, amount: int) -> None:
        _check_positive(amount)
        if amount > self.quantity:
            raise NotEnoughStock(self.code, amount, self.quantity)
        self.quantity -= amount

    @property
    def needs_restock(self) -> bool:
        return self.quantity < self.min_quantity


@dataclass(frozen=True)
class Movement:
    """일어난 사건의 기록. 값 객체 — 내용이 같으면 같은 기록이다."""

    code: str
    kind: str          # "IN" | "OUT" — 12.3에서 Enum 으로 바꾼다
    amount: int


def _check_positive(amount: int) -> None:
    if amount <= 0:
        raise ValueError(f"수량은 1 이상이어야 한다: {amount}")
```

```python title="inventory/store.py"
from .errors import ItemNotFound
from .models import Item, Movement


class Inventory:
    """품목을 코드로 찾고, 일어난 입출고를 기록한다."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}
        self._log: list[Movement] = []

    def register(self, item: Item) -> None:
        if item.code in self._items:
            raise ValueError(f"이미 등록된 코드: {item.code}")
        self._items[item.code] = item

    def receive(self, code: str, amount: int) -> None:
        self._find(code).receive(amount)
        self._log.append(Movement(code, "IN", amount))

    def issue(self, code: str, amount: int) -> None:
        self._find(code).issue(amount)          # 규칙 위반이면 여기서 예외
        self._log.append(Movement(code, "OUT", amount))

    def restock_list(self) -> list[Item]:
        return [it for it in self._items.values() if it.needs_restock]

    def history(self, code: str) -> list[Movement]:
        self._find(code)                        # 없는 코드는 빈 리스트가 아니라 예외
        return [m for m in self._log if m.code == code]

    def _find(self, code: str) -> Item:
        try:
            return self._items[code]
        except KeyError:
            raise ItemNotFound(code) from None
```

`kind` 가 `"IN"` / `"OUT"` 문자열인 것이 눈에 걸릴 것이다. 맞다. 오타가 나도 안 잡힌다. 이건 [12.3](#/state-machine)에서 `enum` 으로 바꾼다. **지금 단계에서 중요한 건 명사와 동사가 제자리에 있는가이고, 표현 수단은 그다음이다.**

### 요구사항 → 테스트 이름

이제 요구사항 문장을 테스트 이름으로 옮긴다. 이 매핑이 안 되는 문장은 모델의 구멍이다.

```python title="tests/test_item.py"
import pytest

from inventory.errors import NotEnoughStock
from inventory.models import Item


def make_item(quantity=10, min_quantity=3):
    return Item("A-1", "A4 용지", quantity, min_quantity)


def test_출고하면_재고가_그만큼_줄어든다():
    item = make_item(quantity=10)
    item.issue(4)
    assert item.quantity == 6


def test_재고보다_많이_출고하면_거부한다():
    item = make_item(quantity=10)
    with pytest.raises(NotEnoughStock):
        item.issue(11)
    assert item.quantity == 10          # 거부됐으면 상태도 그대로여야 한다


def test_재고와_같은_수량은_출고할_수_있다():
    item = make_item(quantity=10)
    item.issue(10)
    assert item.quantity == 0


def test_최소_보유_수량_미만이면_보충_대상이다():
    item = make_item(quantity=10, min_quantity=3)
    assert not item.needs_restock
    item.issue(8)
    assert item.needs_restock


def test_최소_보유_수량과_같으면_보충_대상이_아니다():
    item = make_item(quantity=10, min_quantity=3)
    item.issue(7)
    assert item.quantity == 3
    assert not item.needs_restock


@pytest.mark.parametrize("amount", [0, -1])
def test_0_이하의_수량은_받지_않는다(amount):
    item = make_item()
    with pytest.raises(ValueError):
        item.issue(amount)
    with pytest.raises(ValueError):
        item.receive(amount)
```

```python title="tests/test_inventory.py"
import pytest

from inventory.errors import ItemNotFound, NotEnoughStock
from inventory.models import Item, Movement
from inventory.store import Inventory


@pytest.fixture
def inv():
    inv = Inventory()
    inv.register(Item("A-1", "A4 용지", quantity=10, min_quantity=3))
    inv.register(Item("B-2", "볼펜", quantity=2, min_quantity=5))
    return inv


def test_입출고는_이력으로_남는다(inv):
    inv.receive("A-1", 5)
    inv.issue("A-1", 3)
    assert inv.history("A-1") == [
        Movement("A-1", "IN", 5),
        Movement("A-1", "OUT", 3),
    ]


def test_이력은_품목별로_분리된다(inv):
    inv.issue("A-1", 1)
    inv.receive("B-2", 7)
    assert inv.history("B-2") == [Movement("B-2", "IN", 7)]


def test_거부된_요청은_이력에_남지_않는다(inv):
    with pytest.raises(NotEnoughStock):
        inv.issue("A-1", 999)
    assert inv.history("A-1") == []


def test_보충_대상은_최소_보유_수량_미만인_품목뿐이다(inv):
    assert [it.code for it in inv.restock_list()] == ["B-2"]
    inv.receive("B-2", 3)
    assert inv.restock_list() == []


def test_없는_코드는_예외로_알린다(inv):
    with pytest.raises(ItemNotFound):
        inv.issue("Z-9", 1)
    with pytest.raises(ItemNotFound):
        inv.history("Z-9")


def test_같은_코드를_두_번_등록할_수_없다(inv):
    with pytest.raises(ValueError):
        inv.register(Item("A-1", "다른 이름"))
```

```bash
pytest -q
```

```text nolines
.............                                                            [100%]
13 passed in 0.02s
```

이 테스트 목록을 이름만 읽으면 요구사항이 재구성된다. 요구사항 2~5가 전부 들어 있고, 앞에서 결정한 구멍 다섯 개도 들어 있다. **모델이 요구사항을 담았다는 증거는 클래스 다이어그램이 아니라 이 목록이다.**

빠진 것이 하나 있다. **요구사항 1번에 대응하는 테스트 이름이 없다.** 앞에서 "옮겨지지 않는 문장이 있으면 모델이 그 요구사항을 표현하지 못한 것"이라고 했으니 여기서 걸려야 맞다. 걸리지 않는 이유는 요구사항 1이 **동작이 아니라 데이터 모양**이기 때문이다. "비품은 코드·이름·수량·최소 수량을 가진다"는 `Item` 의 `dataclass` 선언 다섯 줄이 그대로 명세다. 필드가 있는지 확인하는 테스트는 도메인 규칙이 아니라 `dataclass` 라는 언어 기능을 테스트하는 것이라 쓰지 않는다([12.6](#/test-strategy)).

즉 판정 기준은 이렇게 읽어야 정확하다. **동작을 말하는 문장은 테스트 이름이 되고, 데이터 모양을 말하는 문장은 타입 선언이 된다. 둘 중 어디에도 안 앉는 문장이 있으면 그때가 모델의 구멍이다.** 앞의 오답 1이 걸린 것도 이 기준이다 — 거기서는 `name` 이 필드 선언에조차 없었다. 무엇을 테스트하고 무엇을 안 할지의 기준은 [12.6](#/test-strategy)에서 본격적으로 다룬다. pytest 자체의 사용법은 [6.1](#/pytest)에 있다.

::: note `Movement` 를 `frozen=True` 로 만든 것이 여기서 값을 한다
`test_입출고는_이력으로_남는다` 는 `Movement` 두 개를 리스트째로 `==` 비교한다. `frozen=True` 인 `dataclass` 는 `__eq__` 를 필드 전체로 만들어 주므로 **이 한 줄이 그대로 명세가 된다.** 값 객체로 판정한 것이 테스트를 짧게 만든 것이다. 반대로 `Item` 은 엔티티라 `==` 로 비교하지 않고 `it.code` 를 뽑아 비교했다.
:::

## 요약

- 요구사항과 코드 사이에 **절차**를 넣어라. ① 명사에 밑줄 ② 명사를 거른다 ③ 동사를 배치한다 ④ 요구사항을 테스트 이름으로 옮긴다.
- 명사를 거르는 질문은 **"이 명사만의 규칙이 요구사항에 적혀 있는가"** 다. 없으면 클래스가 아니라 남의 필드다. 후보 13개가 셋으로 줄었다.
- **엔티티는 식별자로 같고 다름을 따지고, 값 객체는 내용으로 따진다.** `@dataclass` 의 기본 `__eq__` 는 값 객체 의미론이라 엔티티에 쓰면 조용히 틀린다. 엔티티는 `dict[식별자, 엔티티]` 로 담아라.
- 동사의 배치 기준은 하나다. **규칙이 한 개체 안에서 완결되면 그 개체에, 여러 개체를 봐야 하면 컬렉션에.**
- **함수로 끝날 것을 클래스로 만들지 마라.** `__init__` 이 저장만 하고 공개 메서드가 하나면 그건 함수다.
- 클래스가 너무 많은 걸 안다는 신호는 관찰 가능하다 — 메서드 이름의 `and`, 계산과 출력의 혼재, 필드를 안 쓰는 메서드, 그리고 **테스트 준비 코드의 길이.**
- **요구사항에 없는 것을 만들지 마라.** "확장 가능하게"는 지금 층을 쌓으라는 뜻이 아니라, 바뀔 지점에 이름을 붙이고 그 판단을 README에 적으라는 뜻이다.
- 요구사항의 구멍은 반드시 있다. **가장 단순한 쪽으로 결정하고, 결정했다는 사실을 테스트와 README에 남겨라.** 인지하지 못한 것과 결정한 것의 차이가 평가받는다.

::: quiz 설계 과제 — 읽지 말고 결정해라

**1. 명사 거르기 (코드 없음, 10분)**

아래 요구사항에서 명사를 전부 뽑고, 2단계의 세 질문으로 **엔티티 / 값 객체 / 필드 / 버릴 것**으로 분류해라. 각 판정에 근거를 한 줄씩 붙여라. 클래스가 세 개를 넘으면 다시 걸러라.

> **[과제] 회의실 예약**
>
> 사내 회의실 예약 시스템을 만들어라. 회의실은 이름과 수용 인원을 가진다. 사용자는 회의실을 특정 시간대(시작·종료)로 예약할 수 있다. 같은 회의실의 시간대가 겹치는 예약은 거부한다. 참석 인원이 수용 인원을 넘는 예약도 거부한다. 예약은 취소할 수 있고, 취소된 예약의 시간대는 다시 예약 가능하다. 회의실별 예약 목록을 조회할 수 있다.

**2. 동사 배치 (설계 판단, 10분)**

1번의 모델에서 **"시간대가 겹치는 예약은 거부한다"** 는 규칙을 어디에 둘 것인가. 3단계의 기준("규칙이 한 개체 안에서 완결되는가")을 적용해 답하고, **왜 다른 쪽이 아닌지**를 한 문장으로 적어라. 그다음 **"참석 인원이 수용 인원을 넘으면 거부"** 는 어디에 두는지도 답해라. 둘의 답이 다르면 왜 다른지 설명해라.

**3. 구현과 테스트 (코드, 40분)**

1·2번의 결정대로 실제로 구현하고, **요구사항 문장을 그대로 테스트 이름으로 옮겨** `pytest` 로 통과시켜라. 시간대는 `datetime` 대신 정수 시각(0~23)으로 단순화해도 된다. 최소한 다음이 테스트로 있어야 한다.

- 겹치지 않는 두 예약은 둘 다 성공한다
- 완전히 겹치는 예약은 거부된다
- **끝나는 시각과 시작 시각이 같은 예약은 겹치지 않는다** (요구사항에 없다 — 결정하고 이유를 적어라)
- 수용 인원 초과 예약은 거부된다
- 취소한 시간대는 다시 예약된다
- 거부된 예약은 목록에 남지 않는다

**4. 함수인가 클래스인가 (판단, 5분)**

3번을 다 짠 뒤, 아래 각각을 **함수로 둘지 클래스의 메서드로 둘지** 결정하고 근거를 한 줄씩 적어라.

- 두 시간대가 겹치는지 판정하는 것
- 회의실 이름 형식(`"A-101"`)이 올바른지 검사하는 것
- 특정 날짜의 전체 예약률(예약된 시간 / 전체 시간)을 계산하는 것

**5. 만들지 않은 것 적기 (5분)**

3번을 제출한다고 치고, README에 들어갈 **"만들지 않은 것과 그 이유"** 를 세 줄로 써라. 최소 하나는 "지금은 만들지 않았지만 필요해지면 여기를 이렇게 고친다"의 형태여야 한다. 이 세 줄이 12.8에서 그대로 쓰인다.

**6. 요구사항이 하나 늘었다 (설계, 10분)**

> 7. 회의실은 **점검 중** 상태가 될 수 있고, 점검 중인 회의실은 예약할 수 없다.

당신의 모델에서 **어느 파일을 몇 줄 고치는지** 세어라. 세 파일 이상을 고쳐야 한다면, 3단계의 배치 기준을 다시 적용해 어디가 틀렸는지 찾아라. 그리고 이 요구사항이 왜 [12.3](#/state-machine)의 주제인지 생각해 봐라 — `"점검 중"` 을 `bool` 필드로 둘 것인가, 상태 값으로 둘 것인가.
:::

**다음 절**: [12.3 상태와 상태 머신](#/state-machine) — `kind = "IN"` 같은 문자열 상태가 왜 위험한지, `Enum` 과 전이 규칙으로 그것을 어떻게 못 박는지 다룬다.
