# 12.4 경계 설계 — 외부 시스템 끊어내기

::: lead
과제 명세 맨 아래에는 거의 항상 이런 문장이 하나 붙어 있다. *"실제 결제 단말과 장치 없이 전체 흐름을 테스트할 수 있어야 한다."* 많은 지원자가 이걸 **편의 요청**으로 읽고 넘어간다. 아니다. 이건 그 과제에서 가장 무거운 **설계 요구사항**이고, 평가자가 코드를 열어 5분 안에 확인하는 항목이다. 이 절은 그 한 줄이 실제로 무엇을 요구하는지, 경계를 어디에 긋고 어떻게 끊는지, 그리고 **어디서 멈춰야 하는지**를 다룬다. `Protocol` 문법은 [2.4 Protocol과 구조적 서브타이핑](#/protocol-typing)에, pytest 사용법은 [6.1 pytest](#/pytest)에 있다. 여기서는 문법이 아니라 **판단**만 한다.
:::

## 그 한 줄이 실제로 요구하는 것

이 절 내내 쓸 과제다. [12.1](#/takehome-eval)의 엘리베이터, [12.2](#/requirements-to-model)의 비품 재고와는 다른 소재를 쓴다.

> **[과제] 전기차 충전 스탠드 컨트롤러**
>
> 1. 카드를 대면 세션이 시작된다. 시작 전에 결제사에 **사전 승인**을 요청하고, **거절되면 충전을 시작하지 않는다.**
> 2. 충전 중에는 커넥터를 잠그고, 종료하면 해제한다.
> 3. 요금은 `기본요금 + 사용량 × 단가` 이고, **심야(23:00~07:00)는 단가가 다르다.**
> 4. 종료 시 **실제 사용량으로 승인 금액을 확정**한다. 확정에 실패하면 세션은 미정산으로 남고 보고된다.
> 5. **결제 단말과 충전기 하드웨어 없이 전체 흐름을 테스트할 수 있어야 한다.**

5번을 만족한다는 건 이 셋을 전부 만족한다는 뜻이다.

| 요구 | 구체적으로 |
| --- | --- |
| **결정성** | 결제사 서버가 죽어 있어도, 심야든 낮이든, 실행 결과가 항상 같다 |
| **속도** | 테스트 전체가 1초 안에 끝난다. 느린 테스트는 안 돌리게 되고, 안 돌리는 테스트는 없는 테스트다 |
| **실패 재현** | "승인 거절"과 "확정 실패"를 **내가 원할 때 만들 수 있다** |

세 번째가 가장 중요하다. 요구사항 1번과 4번은 **실패 경로가 곧 규칙**이다. 실제 결제사를 붙여 놓고는 그 두 규칙을 테스트할 방법이 없다. 카드를 일부러 거절당하게 만들 수 없기 때문이다. **끊지 않으면 요구사항의 절반을 검증할 수 없다.**

## 끊지 않은 코드는 무엇을 막는가

말로 하면 안 와닿는다. 실제로 짜서 돌려 보자. 흔히 나오는 첫 버전이다.

```python title="charger/gateway.py — 흔한 첫 버전"
import socket

PG_HOST = ("127.0.0.1", 9)          # 결제사 승인 서버
_CONN = socket.create_connection(PG_HOST, timeout=0.5)   # 모듈 최상단


def authorize(card_id, amount):
    _CONN.sendall(f"AUTH {card_id} {amount}\n".encode())
    return _CONN.recv(64).decode().strip()
```

```python title="charger/station.py"
from datetime import datetime

from charger import gateway          # 이 줄에서 이미 접속이 일어난다

LOCKED = {}                          # 커넥터 상태를 모듈 전역에 둔다


def start(card_id, connector_id):
    hour = datetime.now().hour                     # 심야 여부를 여기서 본다
    unit = 180 if 7 <= hour < 23 else 120
    if gateway.authorize(card_id, 30000) != "OK":
        return None
    LOCKED[connector_id] = card_id
    return {"card": card_id, "unit": unit}
```

테스트를 한 개 짜고 `pytest` 를 돌린다.

```python title="tests/test_station.py"
from charger.station import start


def test_start_locks_connector():
    session = start("CARD-1", "A")
    assert session is not None
```

```text nolines
==================================== ERRORS ====================================
____________________ ERROR collecting tests/test_station.py ____________________
tests/test_station.py:1: in <module>
    from charger.station import start
charger/station.py:3: in <module>
    from charger import gateway          # 이 줄에서 이미 접속이 일어난다
charger/gateway.py:5: in <module>
    _CONN = socket.create_connection(PG_HOST, timeout=0.5)   # 모듈 최상단
E   ConnectionRefusedError: [Errno 111] Connection refused
=========================== short test summary info ============================
ERROR tests/test_station.py - ConnectionRefusedError: [Errno 111] Connection ...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.13s
```

**테스트가 한 개도 실행되지 않았다.** 실패한 게 아니라 수집 단계에서 끝났다. 평가자 머신에서 `pytest` 를 쳤을 때 이 화면이 나오면 그 제출물은 [12.1](#/takehome-eval)의 관문 1에서 걸린다.

::: danger import 시점에 부작용을 두지 마라
`_CONN = socket.create_connection(...)` 을 모듈 최상단에 둔 순간, **그 모듈을 import 하는 모든 코드가 네트워크를 요구하게 된다.** import 는 값을 가져오는 행위여야지 접속·파일 열기·환경변수 읽기를 하는 자리가 아니다.

이건 테스트만의 문제가 아니다. `import charger.station` 한 줄 때문에 문서 생성 도구, 린터, IDE의 자동완성까지 결제사 접속을 시도한다. import 시스템이 모듈 본문을 언제 실행하는지는 [1.19 모듈과 import](#/imports)에 있다.

**규칙: 모듈 최상단에는 상수, 함수·클래스 정의, import 만 둔다.** 연결이 필요하면 함수 안이나 `__init__` 안으로 미뤄라.
:::

접속을 함수 안으로 옮기면 수집은 통과한다. 심야 요금 테스트를 하나 더 붙여 보자.

```python title="tests/test_station.py"
def test_night_rate_is_cheaper():
    session = start("CARD-2", "B")
    assert session["unit"] == 120        # 심야에만 참이다
```

이번엔 테스트가 **실패**한다.

```text nolines
FAILED tests/test_station.py::test_start_locks_connector - ConnectionRefusedE...
FAILED tests/test_station.py::test_night_rate_is_cheaper - ConnectionRefusedE...
2 failed in 0.07s
```

여기서 두 번째 벽이 나온다. **`test_night_rate_is_cheaper` 는 결제사를 띄워 줘도 통과하지 못한다.** `datetime.now()` 가 실제 시각을 읽으므로, 이 테스트는 **밤 11시부터 아침 7시 사이에만** 통과한다. 아무도 그런 테스트를 CI에 올릴 수 없다.

세 번째 벽은 전역 상태다. `LOCKED` 는 모듈 전역이라 테스트 사이에 남는다.

```python title="tests/test_global.py — 승인은 가짜로 갈아 끼운 뒤"
def test_charging_locks_the_connector():
    station.start("CARD-1", "A", hour=12)
    assert station.LOCKED == {"A": "CARD-1"}


def test_fresh_station_has_no_locked_connector():
    assert station.LOCKED == {}
```

두 번째 테스트만 따로 돌리면 통과한다.

```text nolines
$ pytest -q tests/test_global.py::test_fresh_station_has_no_locked_connector
.                                                                        [100%]
1 passed in 0.01s
```

파일째 돌리면 실패한다.

```text nolines
$ pytest -q tests/test_global.py
    def test_fresh_station_has_no_locked_connector():
>       assert station.LOCKED == {}
E       AssertionError: assert {'A': 'CARD-1'} == {}
E
E         Left contains 1 more item:
E         {'A': 'CARD-1'}
tests/test_global.py:19: AssertionError
1 failed, 1 passed in 0.02s
```

**같은 코드, 같은 테스트인데 순서에 따라 결과가 갈린다.** 전역 변수는 곧 "테스트끼리 공유하는 숨은 인자"다. 이름은 상자가 아니라 객체에 붙은 이름표라는 [1.1](#/objects-names)의 이야기가, 모듈 수준에서 그대로 사고로 이어진 것이다.

정리하면 끊지 않은 코드가 막는 것은 넷이다.

| 막는 것 | 원인 | 증상 |
| --- | --- | --- |
| 실행 자체 | import 시점 부작용 | 테스트 수집 단계에서 죽는다 |
| 실패 경로 검증 | 진짜 서버가 거절해 주지 않는다 | 요구사항 1·4를 테스트할 수 없다 |
| 재현성 | `datetime.now()` 같은 숨은 입력 | 밤에만 통과하는 테스트 |
| 격리 | 모듈 전역 상태 | 순서에 따라 결과가 바뀐다 |

## 경계를 어디에 긋는가

"전부 추상화하라"가 답이면 그건 [12.1](#/takehome-eval)의 오답 A로 가는 길이다. 대상을 고르는 기준이 필요하다. 질문 셋이면 끝난다.

```text nolines
  Q1. 이 프로세스 밖의 무언가에 말을 거는가?
      no   ->  경계가 아니다. 그냥 함수로 둬라
      yes  ->  Q2

  Q2. 같은 입력에 항상 같은 결과가 나오는가?
      no   ->  끊어라
      yes  ->  Q3

  Q3. 그것이 실패하는 상황을 내가 만들 수 있는가?
      no   ->  끊어라
      yes  ->  안 끊어도 된다
```

이 셋을 통과시키면 목록이 이렇게 갈린다.

| 끊는다 | 안 끊는다 |
| --- | --- |
| 네트워크(결제사, 외부 API) | 순수 계산 함수 |
| 하드웨어·장치 파일 | `list`, `dict`, `dataclass` |
| 데이터베이스, 파일 저장 | `json`, `re`, `math` 같은 순수 표준 라이브러리 |
| 현재 시각, 난수 | 내가 방금 만든 도메인 클래스 |
| 표준 입출력, 환경변수 | 예외 클래스 |

::: warn "언젠가 바뀔지도 모르니까"는 기준이 아니다
Q1~Q3 어디에도 "나중에 구현이 바뀔 수 있으니까"는 없다. 그건 경계를 긋는 이유가 아니라 **경계를 긋고 싶은 기분**이다.

`dict` 를 나중에 Redis로 바꿀지 몰라서 `Storage` 인터페이스를 만드는 것, 요금 계산이 나중에 복잡해질까 봐 `PricingStrategy` 를 만드는 것 — 둘 다 요구사항에 없다. 요구사항에 없는 것을 만들지 마라는 YAGNI는 [12.2](#/requirements-to-model)에서 이미 다뤘다. 여기서도 같다.

**끊는 이유는 하나뿐이다. 안 끊으면 요구사항을 검증할 수 없기 때문이다.**
:::

이 과제에서 Q1~Q3에 걸리는 것은 딱 셋이다. **결제사, 커넥터 하드웨어, 현재 시각.** 셋이면 충분하고, 셋보다 많으면 과하다.

## 패치로 때울 것인가, 주입할 것인가

경계를 정했다. 이제 갈림길이다. 두 안이 실제로 다 동작한다.

**안 A — 테스트에서 패치한다.** 코드 구조는 그대로 두고 `monkeypatch` 로 갈아 끼운다([6.2](#/pytest-advanced)). 비교를 결제사 하나로 좁히려고 시각은 이미 `hour` 인자로 밀어냈다고 하자.

```python title="tests/test_station.py — 안 A"
from unittest.mock import MagicMock

from charger import station


def test_start_locks_connector(monkeypatch):
    monkeypatch.setattr(station.gateway, "authorize", MagicMock(return_value="OK"))
    assert station.start("CARD-1", "A", hour=12) is not None


def test_declined_card_does_not_lock(monkeypatch):
    monkeypatch.setattr(station.gateway, "authorize", MagicMock(return_value="NO"))
    station.LOCKED.clear()
    assert station.start("CARD-2", "B", hour=12) is None
    assert station.LOCKED == {}
```

```text nolines
..                                                                       [100%]
2 passed in 0.05s
```

**동작한다.** 승인 거절 경로까지 테스트했다. 그런데 여기에 조용한 함정이 있다.

::: danger 패치한 테스트는 진짜 코드가 깨져도 계속 통과한다
결제사가 API를 바꿔서 단말 번호가 필수가 됐다고 하자. `gateway.authorize` 에 인자를 하나 추가한다. **호출하는 쪽(`station.start`)은 고치는 것을 잊었다.**

```python title="charger/gateway.py"
def authorize(card_id, amount, terminal_id):        # 인자가 하나 늘었다
    ...
```

`station.start` 는 여전히 `gateway.authorize(card_id, 30000)` 를 부른다. 실제로 돌리면 `TypeError` 다. 그런데 테스트를 돌리면?

```text nolines
..                                                                       [100%]
2 passed in 0.01s
```

**초록불이다.** `MagicMock` 은 어떤 인자로 불려도 받아 주기 때문이다. 테스트 스위트가 전부 통과하는데 프로그램은 첫 요청에서 죽는다.

이건 `MagicMock` 의 버그가 아니라 **가짜의 모양을 아무도 검사하지 않는다**는 구조적 문제다. `autospec=True` 로 완화할 수 있지만, 패치 지점이 늘어나면 그것도 관리 대상이 된다.
:::

**안 B — 생성자로 주입한다.** 코드가 필요한 것을 밖에서 받는다.

```python
class ChargingStation:
    def __init__(self, gateway, connector):
        self._gateway = gateway
        self._connector = connector
```

테스트는 진짜 대신 가짜를 넘긴다. 패치도, `import` 경로 문자열도 없다.

| | 안 A: 패치 | 안 B: 생성자 주입 |
| --- | --- | --- |
| 프로덕션 코드 변경 | 없음 | 있음(생성자에 인자 추가) |
| 테스트가 아는 것 | **모듈 경로 문자열** | 객체 하나 |
| 리팩터링에 견디는가 | import 방식만 바꿔도 깨진다 | 안 깨진다 |
| 가짜의 모양 검증 | 안 됨(또는 `autospec` 수동) | **타입 검사기가 한다** |
| 병렬 테스트 | 전역을 건드리므로 위험 | 서로 독립 |
| 도입 비용 | 0 | 인자 두 개와 조립 코드 |

::: tip 그래서 언제 무엇을 쓰는가
**안 A가 맞는 자리** — 내가 소유하지 않은 서드파티 라이브러리의 깊은 안쪽(`requests.get`, `boto3` 클라이언트), 그리고 이미 남이 짜 놓은 레거시에 테스트를 뒤늦게 붙일 때. 코드를 못 고치면 패치가 유일한 수단이다.

**안 B가 맞는 자리** — 내가 처음부터 짜는 코드 전부. 과제형이 여기다. **백지에서 시작하면서 패치에 의존하는 설계를 고르는 것은, 평가자에게 "경계를 설계할 줄 모른다"고 말하는 것과 같다.**

그리고 하나 더. 안 B로 짜 두면 안 A도 여전히 쓸 수 있다. 반대는 성립하지 않는다.
:::

## Protocol로 경계를 쓴다

주입하기로 했다. 그럼 `ChargingStation` 이 받는 그 객체는 **무엇이어야 하는가?** 그 답을 적어 두는 자리가 `ports.py` 다.

```python title="charger/ports.py"
"""이 프로그램이 바깥세상에 요구하는 것. 구현은 여기 없다."""
from typing import Protocol


class PaymentGateway(Protocol):
    def hold(self, card_id: str, amount: int) -> str:
        """사전 승인. 승인 번호를 돌려준다. 거절되면 PaymentDeclined 를 던진다."""
        ...

    def capture(self, hold_id: str, amount: int) -> None:
        """실제 사용액으로 확정한다."""
        ...


class Connector(Protocol):
    def lock(self) -> None: ...
    def unlock(self) -> None: ...

    def meter_wh(self) -> int:
        """적산 전력계 값(Wh). 단조 증가한다."""
        ...
```

이 파일을 쓸 때 지킬 규칙은 셋이다.

1. **내가 실제로 부르는 메서드만 적는다.** 진짜 결제사 API에는 취소·조회·부분환불이 있겠지만 이 과제는 `hold` 와 `capture` 만 쓴다. 안 쓰는 메서드를 넣으면 가짜도 그만큼 구현해야 하고, 그건 순수한 낭비다.
2. **이름을 도메인 언어로 쓴다.** `send_http_request` 가 아니라 `hold` 다. 포트는 **내 프로그램이 요구하는 것**을 적는 자리지, 상대방 프로토콜을 옮겨 적는 자리가 아니다.
3. **도메인 쪽에 둔다.** `ports.py` 는 `charger/` 안에 있고 `adapters.py` 를 import 하지 않는다. 화살표 방향이 이렇게 된다.

```text nolines
   station.py  ──▶  ports.py  ◀──  adapters.py   (진짜)
                              ◀──  fakes.py      (가짜)
```

도메인은 포트만 안다. 진짜 구현이 무엇인지 **모른다.** 그래서 `socket` 이 통째로 사라져도 `station.py` 는 한 글자도 안 바뀐다.

::: note ABC가 아니라 Protocol을 쓰는 이유
[1.15 프로토콜과 ABC](#/protocols)와 [2.4](#/protocol-typing)에 문법과 원리가 있으니 반복하지 않는다. 경계 설계 관점에서 실무적인 차이는 하나다.

**ABC를 쓰면 구현 클래스가 도메인을 상속하거나 `register()` 로 등록해야 한다.** 어느 쪽이든 어댑터가 도메인 패키지를 알아야 하고, 서드파티 객체(예: 이미 존재하는 SDK 클라이언트)는 그대로 넘길 수 없다. `Protocol` 은 구조적이라 **아무 선언 없이** 모양만 맞으면 된다. 어댑터가 도메인을 몰라도 되는 이 성질이 경계에서는 그대로 이득이 된다.

반대로 **런타임 강제가 필요하면 ABC가 낫다.** 플러그인을 외부에서 받아 로드하는 프로그램이라면, 잘못 만든 구현이 로드 시점에 `TypeError` 로 죽는 편이 안전하다. 과제형에서는 구현이 내 손 안에 둘(진짜·가짜)뿐이라 그 강제가 필요 없다.
:::

::: danger Protocol 상속은 런타임에 아무것도 막지 않는다
`class TcpGateway(PaymentGateway):` 라고 명시적으로 상속하면 ABC처럼 지켜 줄 것 같다. 아니다.

```pyrepl
>>> from typing import Protocol
>>> class Gateway(Protocol):
...     def hold(self, card_id: str, amount: int) -> str: ...
...
>>> class TcpGateway(Gateway):
...     def authorize(self, card_id, amount):     # 이름을 잘못 썼다
...         return "OK H-1"
...
>>> g = TcpGateway()
>>> print(g.hold("CARD-1", 30000))
None
```

`hold` 를 구현하지 않았는데 **인스턴스가 만들어지고, 호출되고, `None` 을 돌려준다.** 프로토콜 본문의 `...` 가 진짜 함수 본문이라 그대로 상속된 것이다. 같은 실수를 `ABC` 로 하면 런타임이 막아 준다.

```pyrepl
>>> from abc import ABC, abstractmethod
>>> class Gateway(ABC):
...     @abstractmethod
...     def hold(self, card_id: str, amount: int) -> str: ...
...
>>> class TcpGateway(Gateway):
...     def authorize(self, card_id, amount):
...         return "OK H-1"
...
>>> TcpGateway()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: Can't instantiate abstract class TcpGateway without an implementation for abstract method 'hold'
```

`@runtime_checkable` 을 붙여도 부족하다. `isinstance` 는 **메서드 이름만** 본다.

```pyrepl
>>> from typing import Protocol, runtime_checkable
>>> @runtime_checkable
... class Gateway(Protocol):
...     def hold(self, card_id: str, amount: int) -> str: ...
...
>>> class Wrong:
...     def hold(self):          # 인자가 하나도 안 맞는다
...         return 42
...
>>> isinstance(Wrong(), Gateway)
True
```

**결론은 "Protocol이 나쁘다"가 아니다.** mypy 는 상속하든 안 하든 이 실수를 잡는다(1.19.1 실측 — 상속하면 인스턴스를 만드는 자리에서 `Cannot instantiate abstract class`, 상속하지 않으면 아래의 조립 지점에서 `missing following protocol member`). 잡히려면 **검사기를 실제로 돌려야 한다**는 것이 요점이다.

`Protocol` 을 쓰기로 했다면 둘 중 하나는 반드시 해라. **① 타입 검사기를 CI에 넣는다**([2.8](#/typecheckers), [6.6 CI/CD](#/ci)) **② 진짜 어댑터를 한 번이라도 실제로 호출하는 테스트를 둔다.** 둘 다 안 하면 `Protocol` 은 주석이나 다름없다. 그리고 굳이 상속할 이유는 없다 — 상속하면 어댑터가 도메인 패키지를 import 하게 되어 방금 그린 화살표 방향이 되돌아간다.
:::

### 조립은 한 군데서

주입을 하면 "누가 진짜를 만들어 넣는가"라는 질문이 남는다. 답은 **프로그램의 가장 바깥, 한 군데**다. 그 한 군데를 조립 지점(composition root)이라고 부른다.

```python title="charger/main.py"
"""조립하는 유일한 곳. 진짜 구현이 여기서만 도메인과 만난다."""
import os
from pathlib import Path

from .adapters import SysfsConnector, TcpGateway
from .station import ChargingStation


def build_station() -> ChargingStation:
    return ChargingStation(
        TcpGateway(os.environ["PG_HOST"], int(os.environ["PG_PORT"])),
        SysfsConnector(Path("/sys/class/evse/relay"), Path("/sys/class/evse/meter")),
    )
```

이 파일이 존재하는 것만으로 공짜 이득이 하나 붙는다. **타입 검사기가 어댑터의 이탈을 잡아 준다.** 위의 `TcpGateway` 에서 `hold` 를 실수로 `authorize` 로 바꿔 보면 이렇게 나온다.

```text nolines
charger/main.py:11: error: Argument 1 to "ChargingStation" has incompatible type "TcpGateway"; expected "PaymentGateway"  [arg-type]
charger/main.py:11: note: "TcpGateway" is missing following "PaymentGateway" protocol member:
charger/main.py:11: note:     hold
Found 1 error in 1 file (checked 10 source files)
```

앞의 `MagicMock` 이 조용히 통과시켰던 그 사고를, 여기서는 검사기가 문장으로 알려 준다. **가짜와 진짜가 같은 `Protocol` 을 향하고 있고 조립 지점이 한 군데면, 어긋남은 정적으로 드러난다.** mypy/pyright 설정은 [2.8](#/typecheckers)에 있다.

## 진짜 구현과 가짜 구현

이제 포트 하나에 구현 둘을 나란히 놓는다.

```python title="charger/adapters.py — 진짜"
"""진짜 구현. 이 파일에만 socket 과 장치 파일이 등장한다."""
import socket
from pathlib import Path

from .errors import CaptureFailed, PaymentDeclined


class TcpGateway:
    """결제사 승인 서버에 한 줄씩 말을 건다."""

    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self._addr = (host, port)
        self._timeout = timeout

    def _call(self, line: str) -> str:
        with socket.create_connection(self._addr, timeout=self._timeout) as conn:
            conn.sendall(line.encode() + b"\n")
            return conn.recv(64).decode().strip()

    def hold(self, card_id: str, amount: int) -> str:
        reply = self._call(f"HOLD {card_id} {amount}")
        if not reply.startswith("OK "):
            raise PaymentDeclined(reply)
        return reply.removeprefix("OK ")

    def capture(self, hold_id: str, amount: int) -> None:
        reply = self._call(f"CAPTURE {hold_id} {amount}")
        if reply != "OK":
            raise CaptureFailed(reply)


class SysfsConnector:
    """릴레이와 전력계가 sysfs 파일로 노출돼 있다고 가정한다."""

    def __init__(self, relay: Path, meter: Path) -> None:
        self._relay = relay
        self._meter = meter

    def lock(self) -> None:
        self._relay.write_text("1")

    def unlock(self) -> None:
        self._relay.write_text("0")

    def meter_wh(self) -> int:
        return int(self._meter.read_text().strip())
```

어댑터의 책임은 **번역뿐**이다. 프로토콜 문자열을 도메인 예외로 바꾸는 것 말고는 아무 규칙도 없다. 요금 계산이나 상태 판단이 이 파일에 들어가는 순간 경계가 새는 것이다.

```python title="charger/fakes.py — 가짜"
"""테스트와 데모용 가짜 구현. socket 도 장치 파일도 쓰지 않는다."""
from .errors import CaptureFailed, PaymentDeclined


class FakeGateway:
    def __init__(self, *, decline: bool = False, capture_fails: bool = False) -> None:
        self.decline = decline
        self.capture_fails = capture_fails
        self.holds: list[tuple[str, int]] = []      # 무엇을 요청받았는지 남긴다
        self.captures: list[tuple[str, int]] = []

    def hold(self, card_id: str, amount: int) -> str:
        if self.decline:
            raise PaymentDeclined(card_id)
        self.holds.append((card_id, amount))
        return f"HOLD-{len(self.holds)}"

    def capture(self, hold_id: str, amount: int) -> None:
        if self.capture_fails:
            raise CaptureFailed(hold_id)
        self.captures.append((hold_id, amount))


class FakeConnector:
    def __init__(self, meter: int = 0) -> None:
        self.meter = meter
        self.locked = False
        self.lock_calls = 0

    def lock(self) -> None:
        self.locked = True
        self.lock_calls += 1

    def unlock(self) -> None:
        self.locked = False

    def meter_wh(self) -> int:
        return self.meter

    def charge(self, wh: int) -> None:
        """테스트가 '충전이 일어났다'고 말하는 방법."""
        self.meter += wh
```

가짜가 하는 일은 셋뿐이다. **① 규약대로 답한다 ② 무엇을 요청받았는지 기록한다 ③ 실패를 주문받는다.** `decline=True` 한 글자가 요구사항 1번의 실패 경로를, `capture_fails=True` 가 요구사항 4번의 실패 경로를 만든다. 진짜 결제사로는 불가능한 일이다.

`charge()` 처럼 **진짜에는 없는 메서드**를 가짜에 두는 것은 정상이다. 이건 테스트가 세상을 조작하는 손잡이지 포트의 일부가 아니다. 포트에 넣지만 않으면 된다.

::: warn 가짜를 진짜처럼 만들지 마라
가짜를 짜다 보면 자꾸 커진다. 승인 한도를 검사하고, 중복 승인을 막고, 만료된 hold를 정리하고… **가짜에 규칙이 생기는 순간 가짜 자체가 테스트가 필요한 코드가 된다.** 그리고 그 규칙은 진짜와 달라지고, 테스트는 존재하지 않는 세상을 검증하기 시작한다.

기준: **가짜의 코드 줄 수가 도메인 클래스보다 많아지면 잘못 가고 있다.** 위의 `FakeGateway` 는 조건문이 두 개고 둘 다 테스트가 직접 켠 것뿐이다. 그게 상한이다.
:::

::: note Fake / Stub / Mock — 세 단어를 언제 쓰는가
| | 하는 일 | 이 과제에서 |
| --- | --- | --- |
| **Stub** | 정해진 값을 돌려준다. 그뿐 | 승인만 통과시키면 될 때 |
| **Fake** | 동작하는 간이 구현. 상태를 가진다 | `FakeConnector` — 전력계 값이 누적된다 |
| **Mock** | **어떻게 불렸는지**를 검증한다 | `FakeGateway.holds` 로 확인하는 부분 |

이름은 중요하지 않다. 중요한 판단은 하나다. **"무엇을 호출했는가"를 검증할 것인가, "결과가 무엇인가"를 검증할 것인가.** 전자에 기대면 테스트가 구현 세부에 묶여서 리팩터링마다 깨진다. **원칙은 결과 검증이고, 호출 검증은 결과에 드러나지 않는 것에만 쓴다** — 예를 들어 "거절된 카드로는 커넥터를 잠그지 않았다"는 결과에 안 드러나므로 `lock_calls` 로 본다. 이 판단은 [12.6 테스트 전략](#/test-strategy)에서 더 깊게 다룬다.
:::

## 테스트가 어떻게 달라지는가

도메인은 이렇게 생겼다. 요구사항 3의 심야 판정은 순수 함수로 따로 뺐다.

```python title="charger/pricing.py"
"""요금 계산. 아무것도 import 하지 않는다 — 여기엔 경계가 없다."""

BASE_FEE = 1_000          # 원
DAY_RATE = 180            # 원/kWh
NIGHT_RATE = 120
NIGHT_START, NIGHT_END = 23, 7


def unit_rate(hour: int) -> int:
    """23시부터 07시 직전까지가 심야다."""
    return NIGHT_RATE if hour >= NIGHT_START or hour < NIGHT_END else DAY_RATE


def fee(watt_hours: int, hour: int) -> int:
    """돈은 정수로만 다룬다. Wh 정수를 받아 원 단위 정수를 낸다."""
    return BASE_FEE + watt_hours * unit_rate(hour) // 1000
```

```python title="charger/station.py"
from dataclasses import dataclass

from .errors import CaptureFailed, WrongState
from .ports import Connector, PaymentGateway
from .pricing import fee

HOLD_AMOUNT = 30_000


@dataclass(frozen=True)
class Receipt:
    card_id: str
    watt_hours: int
    amount: int
    settled: bool


@dataclass
class _Session:
    card_id: str
    hold_id: str
    start_wh: int
    hour: int


class ChargingStation:
    def __init__(self, gateway: PaymentGateway, connector: Connector) -> None:
        self._gateway = gateway
        self._connector = connector
        self._session: _Session | None = None
        self.unsettled: list[Receipt] = []

    def start(self, card_id: str, hour: int) -> None:
        if self._session is not None:
            raise WrongState(f"이미 {self._session.card_id} 세션이 진행 중이다")
        hold_id = self._gateway.hold(card_id, HOLD_AMOUNT)   # 거절이면 여기서 예외
        self._connector.lock()
        self._session = _Session(card_id, hold_id, self._connector.meter_wh(), hour)

    def stop(self) -> Receipt:
        if self._session is None:
            raise WrongState("진행 중인 세션이 없다")
        s, self._session = self._session, None
        self._connector.unlock()                              # 하드웨어부터 푼다
        wh = self._connector.meter_wh() - s.start_wh
        amount = fee(wh, s.hour)
        try:
            self._gateway.capture(s.hold_id, amount)
        except CaptureFailed:
            receipt = Receipt(s.card_id, wh, amount, settled=False)
            self.unsettled.append(receipt)
            return receipt
        return Receipt(s.card_id, wh, amount, settled=True)
```

`socket` 도 `datetime` 도 없다. 전역도 없다. **`ChargingStation` 을 두 개 만들면 서로 완전히 독립이다.**

`WrongState` 로 막은 두 전이(세션 중 재시작, 세션 없이 종료)는 상태 머신의 일이다. 전이 규칙을 명시적으로 표현하는 방법은 [12.3 상태와 상태 머신](#/state-machine)에 있고, 저장소까지 같은 방식으로 갈아 끼우는 완결 예제는 [12.10](#/case-domain-repo)에 있다.

이제 테스트가 요구사항 문장을 그대로 옮긴 모양이 된다.

```python title="tests/test_station.py"
import pytest

from charger.errors import PaymentDeclined, WrongState
from charger.fakes import FakeConnector, FakeGateway
from charger.station import HOLD_AMOUNT, ChargingStation


def make(**kw):
    gateway = FakeGateway(**kw)
    connector = FakeConnector(meter=5_000)      # 이전 사용량이 남아 있는 상태
    return ChargingStation(gateway, connector), gateway, connector


def test_start_holds_then_locks():
    station, gateway, connector = make()
    station.start("CARD-1", hour=12)
    assert gateway.holds == [("CARD-1", HOLD_AMOUNT)]
    assert connector.locked is True


def test_declined_card_never_locks_the_connector():
    station, gateway, connector = make(decline=True)
    with pytest.raises(PaymentDeclined):
        station.start("CARD-X", hour=12)
    assert connector.locked is False
    assert connector.lock_calls == 0


def test_full_session_captures_actual_usage():
    station, gateway, connector = make()
    station.start("CARD-1", hour=12)
    connector.charge(12_000)                    # 12 kWh 충전됐다
    receipt = station.stop()
    assert receipt.watt_hours == 12_000
    assert receipt.amount == 1_000 + 12 * 180
    assert receipt.settled is True
    assert gateway.captures == [("HOLD-1", receipt.amount)]
    assert connector.locked is False


def test_night_session_is_billed_at_night_rate():
    station, _, connector = make()
    station.start("CARD-1", hour=23)
    connector.charge(12_000)
    assert station.stop().amount == 1_000 + 12 * 120


def test_capture_failure_leaves_session_unsettled_but_unlocks():
    station, _, connector = make(capture_fails=True)
    station.start("CARD-1", hour=12)
    connector.charge(3_000)
    receipt = station.stop()
    assert receipt.settled is False
    assert station.unsettled == [receipt]
    assert connector.locked is False            # 손님을 가둬 두지 않는다


def test_second_start_without_stop_is_rejected():
    station, _, _ = make()
    station.start("CARD-1", hour=12)
    with pytest.raises(WrongState):
        station.start("CARD-2", hour=12)


def test_stop_without_start_is_rejected():
    station, _, _ = make()
    with pytest.raises(WrongState):
        station.stop()
```

```text nolines
$ pytest -q
..............                                                           [100%]
14 passed in 0.02s
```

`test_declined_card_never_locks_the_connector` 와 `test_capture_failure_leaves_session_unsettled_but_unlocks` 를 보라. **끊기 전에는 이 두 개를 아예 짤 수 없었다.** 요구사항 1번과 4번은 이 두 테스트로 증명된다. 경계를 끊는다는 것은 결국 이것이다 — **명세의 실패 경로를 코드로 쓸 수 있게 만드는 일.**

::: perf 가짜가 빠른 것은 부수 효과가 아니라 요구사항이다
같은 시나리오(승인 → 잠금 → 12 kWh → 해제 → 확정)를 진짜 어댑터와 가짜로 각각 실행했다. 100회씩 5묶음을 돌려 **묶음 평균의 최소~최대**를 적었다. 진짜 쪽 승인 서버는 **같은 머신의 루프백**에 띄웠다. 즉 네트워크 지연이 0인, 진짜에 가장 유리한 조건이다.

| 구현 | 세션 1회 |
| --- | --- |
| `TcpGateway` + `SysfsConnector`(파일) | 1.26 ~ 1.54 ms |
| `FakeGateway` + `FakeConnector` | 2.3 ~ 5.1 µs |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**세 자릿수 차이다.** 그리고 이건 하한이다. 실제 결제사는 다른 네트워크 너머에 있고, 그 왕복 시간이 여기 그대로 더해진다. 테스트 스무 개가 1초를 넘기기 시작하면 사람은 `pytest` 를 안 치게 된다. 속도는 편의가 아니라 **테스트가 실제로 돌아가느냐**의 문제다.
:::

## 시계와 난수 — 눈에 안 보이는 경계

`socket` 은 눈에 띈다. `datetime.now()` 는 안 띈다. 그런데 성질은 같다. **함수 시그니처에 안 적혀 있는 입력**이고, 값을 내가 못 정한다.

여기서도 두 안이 갈린다.

**안 A — 인자로 밀어낸다.** 위 코드가 택한 방식이다. `start(card_id, hour)` 로 시각을 밖에서 받는다.

**안 B — `Clock` 포트를 만든다.**

```python title="clock.py — 안 B"
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now()


class FrozenClock:
    def __init__(self, t: datetime) -> None:
        self._t = t

    def now(self) -> datetime:
        return self._t
```

```pyrepl
>>> from datetime import datetime
>>> from clock import FrozenClock
>>> def greeting(clock):
...     return "심야 요금" if clock.now().hour >= 23 else "주간 요금"
...
>>> greeting(FrozenClock(datetime(2025, 3, 1, 23, 30)))
'심야 요금'
>>> greeting(FrozenClock(datetime(2025, 3, 1, 9, 0)))
'주간 요금'
```

| | 안 A: 인자로 밀어내기 | 안 B: Clock 포트 |
| --- | --- | --- |
| 코드량 | 0 | 클래스 3개 + 주입 |
| 시각을 몇 번 읽는가 | **한 번뿐일 때 적합** | 여러 번, 여러 지점 |
| 시간이 흐르는 것 자체가 규칙일 때 | 인자가 계속 늘어난다 | 자연스럽다 |
| 읽는 사람의 부담 | 없다 | 포트 하나를 더 이해해야 한다 |

**이 과제에서는 안 A가 낫다.** 시각이 필요한 지점이 "세션 시작 시 단가 결정" 하나뿐이기 때문이다. 포트를 하나 더 만들 이유가 없다.

**주차장 정산처럼 "입차 시각과 출차 시각의 차이"가 규칙의 중심이면 안 B가 낫다.** 시각이 여러 지점에서 여러 번 필요하고, "10분 후" 같은 시간 이동을 테스트가 직접 조작해야 하기 때문이다.

::: tip 판단 기준 한 줄
**시각을 읽는 지점이 하나면 인자로 밀어내고, 둘 이상이면 포트로 뽑아라.** 난수(`random`), UUID 생성, 프로세스 ID도 정확히 같은 기준으로 판단한다.

인자로 밀어내는 쪽이 언제나 시작점이어야 한다. 밀어낼 수 없을 만큼 인자가 지저분해졌을 때가 포트를 만들 때다. **반대 순서로 가면 거의 항상 과해진다.**
:::

## 어디까지 끊을 것인가

이 절의 도구를 배운 직후가 가장 위험하다. 모든 것에 `Protocol` 을 씌우고 싶어진다. 과제형에서 **오버엔지니어링은 실력의 증거가 아니라 감점 요인**이다([12.1](#/takehome-eval)).

멈춰야 하는 지점 넷을 못으로 박아 둔다.

**① 구현이 하나뿐이고 앞으로도 하나면 포트를 만들지 마라.** 요금 계산은 함수 두 개다. `PricingPolicy` 프로토콜과 `DefaultPricingPolicy` 구현을 만들면, 파일 하나와 간접 참조 하나가 늘어나는 대신 얻는 것이 없다. **"나중에 요금제가 늘어나면 `fee` 를 주입받게 바꾼다"는 문장을 README에 한 줄 적는 것이 훨씬 높게 평가된다**([12.8](#/readme-submit)).

**② 메서드가 하나면 `Protocol` 대신 `Callable` 이다.**

```python title="notify.py"
from collections.abc import Callable


class Station:
    def __init__(self, notify: Callable[[str], None]) -> None:
        self._notify = notify

    def report_unsettled(self, card_id: str) -> None:
        self._notify(f"미정산: {card_id}")
```

```pyrepl
>>> from notify import Station
>>> sent = []
>>> Station(sent.append).report_unsettled("CARD-9")
>>> sent
['미정산: CARD-9']
```

가짜가 **`sent.append` 한 줄**이다. 클래스도 파일도 필요 없다.

**③ DI 컨테이너·프레임워크를 쓰지 마라.** 주입할 것이 둘이다. 생성자에 두 줄 쓰면 끝난다. 컨테이너 설정 파일과 라이브러리 의존성을 추가하는 순간, 평가자는 코드를 읽기 전에 그 라이브러리 문서를 읽어야 한다. **읽는 사람의 시간을 쓰게 만드는 설계는 과제형에서 손해다.**

**④ 계층을 이름으로 늘리지 마라.** `Service` → `Manager` → `Handler` → `Repository` 를 한 줄로 통과하는 호출은 경계가 아니라 미로다. 이 과제의 최종 구조는 이게 전부다.

```text nolines
charging-station/
├── README.md
├── pyproject.toml
├── charger/
│   ├── __init__.py
│   ├── pricing.py        <- 순수 계산. import 가 하나도 없다
│   ├── ports.py          <- 바깥세상에 요구하는 것 (Protocol)
│   ├── errors.py         <- 도메인 예외
│   ├── station.py        <- 규칙. ports 만 안다
│   ├── adapters.py       <- 진짜 구현. socket 과 장치 파일이 여기에만
│   ├── fakes.py          <- 가짜 구현
│   └── main.py           <- 조립하는 유일한 곳
└── tests/
    ├── test_pricing.py
    └── test_station.py
```

파일 여덟 개다. 구조 자체는 [12.7](#/project-structure)에서 따로 다룬다.

::: note fakes.py 를 패키지 안에 둘 것인가, tests/ 에 둘 것인가
두 안 다 흔하다.

- **`charger/fakes.py`** — `main.py` 에 가짜로 조립하는 함수를 하나 더 두면 하드웨어 없이 데모가 돈다. 평가자가 장치 없이 프로그램을 **실행해 볼 수 있다**는 것은 관문 1에서 큰 이득이다. 대신 배포물에 테스트용 코드가 섞인다.
- **`tests/fakes.py`** — 배포물이 깨끗하다. 대신 데모 모드를 만들려면 가짜를 또 만들어야 한다.

**과제형에서는 전자를 권한다.** 평가자가 실행해 볼 수 있는 것이 배포 순수성보다 가치가 크다. 어느 쪽을 골랐든 **README에 이유를 한 줄 적어라.** 판단 근거가 적힌 선택은 틀려도 감점되지 않는다.
:::

::: danger 끊었다고 착각하기 쉬운 세 가지
1. **포트를 만들었는데 도메인이 어댑터를 import 한다.** 그러면 경계는 이름뿐이다. `station.py` 에서 `import socket` 이나 `from .adapters import ...` 가 보이면 실패다.
2. **생성자로 받아 놓고 안에서 기본값으로 진짜를 만든다.** `def __init__(self, gateway=TcpGateway("prod", 443))` — 기본 인자는 정의 시점에 한 번 평가된다([1.1](#/objects-names)). 테스트가 아무것도 안 넘기면 진짜에 붙는다. 기본값은 `None` 으로 두고 조립 지점에서 넣어라.
3. **가짜를 썼는데 전역이 남아 있다.** 앞에서 본 `LOCKED` 다. 주입은 했는데 상태를 모듈 전역에 두면 테스트 격리는 여전히 깨진다.

셋 다 "pytest 는 통과하는데 설계는 안 끊긴" 상태다. 확인법은 간단하다. **`charger/station.py` 와 `charger/pricing.py` 의 import 목록을 보라.** 표준 라이브러리의 순수한 것과 같은 패키지의 도메인 모듈만 있으면 성공이다.
:::

::: cote 이 감각이 코딩테스트 밖에서 쓰이는 곳
로봇 코드에서 센서와 액추에이터는 정확히 이 문제다. 실제 하드웨어 없이 노드 로직을 테스트하려면 `read_scan()` 을 포트로 뽑고 시뮬레이터·녹화 데이터·가짜를 갈아 끼운다([10.12 센서 데이터 처리](#/sensors), [10.15 rosbag과 디버깅](#/ros-debug)). ML 파이프라인에서 데이터 로더를 인자로 받는 것도, 로깅 핸들러를 주입하는 것도([6.4 로깅](#/logging)) 같은 형태다.

**"프로세스 밖의 것을 이름 있는 경계 뒤로 밀어낸다"** 는 한 가지 동작을, 도메인만 바꿔 평생 반복하게 된다.
:::

## 요약

- **"장치 없이 테스트하라"는 편의 요청이 아니라 설계 요구사항이다.** 결정성·속도·**실패 재현** 셋을 요구하고, 셋째가 가장 무겁다. 끊지 않으면 명세의 실패 경로를 검증할 수 없다.
- 끊지 않은 코드가 막는 것은 넷이다. **import 시점 부작용**(수집 단계에서 죽는다), **실패 경로 검증 불가**, **숨은 입력**(`datetime.now()`), **전역 상태**(순서에 따라 결과가 바뀐다).
- 경계 대상은 세 질문으로 고른다. **① 프로세스 밖에 말을 거는가 ② 같은 입력에 같은 결과인가 ③ 실패를 내가 만들 수 있는가.** "언젠가 바뀔지도 모르니까"는 기준이 아니다.
- **패치보다 생성자 주입이다.** `MagicMock` 은 진짜 시그니처가 바뀌어도 **초록불을 유지한다.** 주입 + `Protocol` + 조립 지점 한 군데면 그 어긋남을 타입 검사기가 잡는다.
- **`Protocol` 은 런타임에 아무것도 보장하지 않는다.** 상속해도 빠뜨린 메서드가 조용히 `None` 을 반환하고(`ABC` 였다면 `TypeError`), `@runtime_checkable` 의 `isinstance` 는 이름만 본다. **타입 검사기를 실제로 돌리든지, 진짜 어댑터를 부르는 테스트를 두든지 둘 중 하나는 해라.**
- 가짜가 하는 일은 셋뿐이다. **규약대로 답하고, 요청받은 것을 기록하고, 실패를 주문받는다.** 가짜가 도메인보다 커지면 잘못 가고 있다.
- **멈추는 법을 아는 것이 끊는 법을 아는 것보다 어렵다.** 구현이 하나면 포트를 만들지 말고, 메서드가 하나면 `Callable` 을 쓰고, DI 컨테이너는 쓰지 마라. 안 만든 이유는 **코드가 아니라 README에** 적는다.

::: quiz 설계 과제 — 읽지 말고 결정하고 짜라
답을 고르는 문제가 아니다. 전부 **코드를 짜거나 판단을 문장으로 적는** 과제다.

**1. 경계 선별 (10분, 코드 없음)**
아래 요구사항에서 Q1~Q3을 적용해 **끊을 것과 끊지 않을 것**을 표로 나눠라. 각 항목마다 어느 질문에서 걸렸는지 적어라.

> 사내 회의실 예약기. ① 사번으로 예약한다. ② 예약 시각이 근무시간(09~18시) 밖이면 거부한다. ③ 예약이 확정되면 사내 메신저 API로 알림을 보낸다. ④ 예약 내역은 JSON 파일로 남는다. ⑤ 예약 번호는 무작위 8자리다. ⑥ 같은 회의실 같은 시간대는 중복 예약할 수 없다.

**2. 포트와 가짜 (30분, 코드)**
1번의 결과대로 `ports.py`, `fakes.py`, 도메인 클래스를 짜라. 그리고 다음 세 개를 **반드시 포함한** 테스트를 `pytest` 로 통과시켜라.

- 근무시간 밖 예약이 거부되고, **그때 알림이 나가지 않았다**
- 메신저 API가 실패해도 **예약 자체는 남는다**
- 예약 번호가 무작위인데도 테스트가 **매번 같은 값**을 본다

**3. 시계 판단 (10분, 문장)**
1번의 회의실 예약기에서 "현재 시각"을 **인자로 밀어낼 것인가, `Clock` 포트로 뽑을 것인가.** 결정하고 근거를 세 문장으로 적어라. 그 다음, 요구사항에 *"예약 시작 10분 전에 리마인더를 보낸다"* 가 추가됐다고 가정하고 **판단이 바뀌는지** 다시 적어라.

**4. 과한 설계 잡아내기 (10분, 문장)**
어떤 지원자가 회의실 예약기를 이렇게 제출했다. `RoomRepository`, `ReservationRepository`, `NotificationPort`, `ClockPort`, `IdGeneratorPort`, `ReservationPolicy`, `ReservationService`, `ReservationFacade`. 전부 인터페이스와 구현이 한 쌍씩이다.

**남길 것과 지울 것을 고르고, 지우는 것마다 한 줄 근거를 써라.** 그리고 지운 것들에 대해 README에 넣을 문장을 세 줄로 작성하라.

**5. 함정 찾기 (10분, 코드)**
아래 코드는 경계를 끊은 것처럼 보이지만 셋 다 안 끊겼다. 각각 무엇이 문제이고, 어떤 테스트를 짜면 그 문제가 드러나는지 코드로 보여라.

```python title="조각 — 이 상태로는 실행되지 않는다"
class Booking:
    def __init__(self, notifier=SlackNotifier("https://hooks.example/xxx")):
        self._notifier = notifier

    def reserve(self, emp_id, at):
        from .storage import save          # 함수 안에서 import 했으니 괜찮다?
        code = f"R{random.randint(0, 10**8 - 1):08d}"
        save(code, emp_id, at)
        self._notifier.send(f"{emp_id} 예약 완료")
        return code
```
:::

**다음 절**: [12.5 예외와 오류 설계](#/error-design) — 이 절에서 `PaymentDeclined` 와 `CaptureFailed` 를 그냥 썼다. 실패를 예외로 표현할지 반환값으로 표현할지, 그 경계를 정하는 절이다.
