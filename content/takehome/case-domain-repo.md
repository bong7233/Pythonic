# 12.10 완결 예제 II — 도메인과 저장소 분리

::: lead
[12.9](#/case-state-system)에서는 상태가 규칙의 중심이었다. 이번 과제의 중심은 **데이터가 어디에 남는가**다. "대출 이력은 프로그램을 껐다 켜도 남아야 한다"는 한 문장이 요구사항에 들어오는 순간, 초보자의 코드에는 `json.load` 가 비즈니스 규칙 한복판에 박힌다. 그러면 규칙을 읽으려면 파일 포맷을 읽어야 하고, 규칙 하나를 고치려면 저장 코드를 다시 만져야 한다. 이 절은 도서 대출 과제 하나를 처음부터 끝까지 짜면서 **규칙과 저장을 갈라놓는다.** 인메모리 저장소와 파일 저장소가 같은 `Protocol` 뒤에서 자리를 바꾸고, **한 벌의 테스트가 두 구현을 모두 검증한다.** 그리고 그 분리가 실제로 얼마를 벌어 주고 얼마를 치르게 하는지를 측정한 숫자로 확인한다.
:::

## 요구사항 한 장

과제 지문은 이렇게 왔다. 이번에도 [12.2](#/requirements-to-model)의 절차대로 명사와 동사를 뽑을 것이다. 다만 이 절이 겨누는 문장은 마지막 줄이다.

> **도서 대출 관리**
>
> 1. 회원은 책을 빌리고 반납한다. 책은 사본 단위로 구분되고, 한 사본은 동시에 한 명만 빌릴 수 있다.
> 2. 한 회원이 동시에 빌릴 수 있는 책은 **3권**까지다.
> 3. 대출 기간은 **14일**이다. 기한을 넘겨 반납하면 하루당 **100원**의 연체료를 받는다.
> 4. 연체 중인 대출이 하나라도 있는 회원은 새로 빌릴 수 없다.
> 5. **대출 이력은 프로그램을 다시 켜도 남아 있어야 한다.**
> 6. 저장 방식은 자유롭게 고르되, 그 선택의 이유를 적어라.

5번이 저장소를 만들 이유다. **"나중에 DB로 바꿀지도 모르니까"가 아니다.** [12.4](#/boundaries-di)에서 못 박았듯 그건 경계를 긋는 이유가 아니라 경계를 긋고 싶은 기분이다. 여기서는 요구사항이 명시적으로 영속성을 요구했고, 6번이 대놓고 "설계 결정을 적어라"라고 말한다. 즉 이 과제는 **저장 방식을 어떻게 골랐는지를 채점하겠다**고 예고하고 있다.

## 1차 시도 — 규칙과 저장이 한 몸일 때

대부분의 제출물이 이렇게 생겼다. 그리고 **이 코드는 동작한다.**

```python title="library_v0.py — 1차 시도"
import json
from datetime import date, timedelta
from pathlib import Path

DB = Path("loans.json")
MAX_ACTIVE = 3
LOAN_DAYS = 14
FINE_PER_DAY = 100


def borrow(member_id, book_id, on):
    rows = json.loads(DB.read_text()) if DB.exists() else []
    active = [r for r in rows if r["returned_on"] is None]
    mine = [r for r in active if r["member_id"] == member_id]
    if any(date.fromisoformat(r["due_on"]) < on for r in mine):
        raise ValueError("연체 중")
    if len(mine) >= MAX_ACTIVE:
        raise ValueError("한도 초과")
    if any(r["book_id"] == book_id for r in active):
        raise ValueError("이미 대출됨")
    row = {
        "loan_id": f"L{len(rows) + 1:04d}",
        "member_id": member_id,
        "book_id": book_id,
        "loaned_on": on.isoformat(),
        "due_on": (on + timedelta(days=LOAN_DAYS)).isoformat(),
        "returned_on": None,
    }
    rows.append(row)
    DB.write_text(json.dumps(rows))
    return row
```

테스트도 쓸 수 있다. 실제로 통과한다.

```python title="test_v0.py"
from datetime import date

import pytest

import library_v0


def test_같은_책은_두_번_못_빌린다(tmp_path, monkeypatch):
    monkeypatch.setattr(library_v0, "DB", tmp_path / "loans.json")
    library_v0.borrow("M-01", "B-100", date(2025, 3, 2))
    with pytest.raises(ValueError):
        library_v0.borrow("M-02", "B-100", date(2025, 3, 2))
```

```text nolines
.                                                                        [100%]
1 passed in 0.01s
```

동작하고, 테스트도 있다. 그런데 평가자는 여기서 감점한다. 이유가 넷이다.

1. **규칙을 읽으려면 파일 포맷을 읽어야 한다.** "3권 제한"이라는 규칙은 `len(mine) >= MAX_ACTIVE` 한 줄인데, 그 `mine` 에 도달하기까지 `json.loads`, `r["returned_on"] is None`, `date.fromisoformat(r["due_on"])` 을 통과해야 한다. **규칙과 직렬화가 같은 함수에 섞여 있다.**
2. **모든 규칙 테스트가 파일을 만든다.** 위 테스트는 `tmp_path` 와 `monkeypatch` 를 쓴다. 규칙이 스무 개면 스무 번 디스크를 친다. 그리고 `monkeypatch.setattr` 로 **모듈 전역을 바꾸는** 테스트는 [12.4](#/boundaries-di)에서 본 그 함정 위에 서 있다.
3. **저장 방식을 바꾸면 규칙을 다시 읽어야 한다.** JSON을 SQLite로 바꾸는 순간 `borrow` 본문 전체를 다시 쓴다. 규칙은 하나도 안 바뀌었는데.
4. **`dict` 는 오타를 안 잡는다.** `r["returnd_on"]` 이라고 쓰면 `KeyError` 지만, `r.get("returnd_on")` 으로 바꾼 순간 조용히 `None` 이 되어 모든 대출이 반납된 것으로 처리된다.

::: warn "함수 하나짜리인데 클래스가 필요한가"
필요 없다. [12.2](#/requirements-to-model)에서 다뤘듯 상태 없는 계산은 함수로 충분하다. 지금 문제는 클래스냐 함수냐가 아니라 **한 함수가 두 가지 일을 하고 있다**는 것이다. 아래에서 하는 일은 클래스를 도입하는 것이 아니라 `json` 을 다른 파일로 밀어내는 것이다. 클래스는 그 결과로 생긴다.
:::

## 무엇을 끊는가 — 저장소 하나면 충분하다

[12.4](#/boundaries-di)의 세 질문을 이 과제에 그대로 돌린다.

| 후보 | Q1 프로세스 밖? | Q2 결정적? | Q3 실패를 만들 수 있나? | 결론 |
| --- | --- | --- | --- | --- |
| `loans.json` | yes | no | no | **끊는다** |
| `date.today()` | yes | no | — | 인자로 민다 |
| 연체료 계산 | no | — | — | 그냥 함수 |
| `Loan` 자료구조 | no | — | — | 그냥 `dataclass` |

끊을 것은 **저장소 하나**다. 현재 시각도 Q1에 걸리지만, 여기서는 포트를 만들지 않고 **메서드 인자로 밀어냈다**(`borrow(..., on: date)`). 부르는 쪽이 날짜를 주면 도메인은 시계를 몰라도 되고, 포트가 하나 줄어든다.

::: tip 경계를 하나 줄이는 가장 싼 방법은 인자다
`Clock` 프로토콜을 만들고, `SystemClock` 과 `FixedClock` 을 만들고, 생성자에 주입하는 것 — 전부 합쳐 20줄이다. 그 20줄이 사는 값은 `on: date` 인자 하나와 정확히 같다. **주입은 "그 객체가 상태를 갖거나 여러 메서드를 제공할 때"만 값을 한다.** 값 하나를 받는 데 프로토콜을 만들면 [12.1](#/takehome-eval)이 말한 오버엔지니어링 감점 구간에 들어간다.

반대로 시간이 **여러 군데에서 여러 형태로** 필요해지면(대출 시각, 만료 배치, 로그 타임스탬프) 그때 포트로 승격시켜라.
:::

## 저장소 인터페이스를 얼마나 크게 만들 것인가

경계를 정했으면 다음 질문은 **그 경계에 메서드를 몇 개 뚫을 것인가**다. 여기서 설계가 갈린다.

**안 A — 컬렉션처럼 다룬다.** 저장소는 넣고 꺼내는 일만 한다. 거르는 일은 도메인이 한다.

```python
class LoanRepository(Protocol):
    def save(self, loan: Loan) -> None: ...
    def all(self) -> list[Loan]: ...
```

**안 B — 질의를 저장소가 맡는다.** 규칙이 필요로 하는 조회를 그대로 메서드로 뚫는다.

```python
class LoanRepository(Protocol):
    def save(self, loan: Loan) -> None: ...
    def active_by_member(self, member_id: str) -> list[Loan]: ...
    def active_by_book(self, book_id: str) -> Loan | None: ...
    def overdue_before(self, on: date) -> list[Loan]: ...
    def count(self) -> int: ...
```

둘 다 동작한다. 갈리는 지점은 이렇다.

| | 안 A: `save` + `all` | 안 B: 질의 메서드 |
| --- | --- | --- |
| 포트 메서드 수 | 2개 | 5개 |
| 인메모리 구현(빈 줄 제외) | **7줄** | **17줄** |
| 규칙이 사는 곳 | 전부 도메인 | **일부가 저장소로 샌다** |
| 요구사항이 하나 늘면 | 도메인만 고친다 | **모든 구현을 고친다** |
| 큰 데이터 | 매번 전체를 읽는다 | 인덱스·`WHERE` 를 쓸 수 있다 |
| 저장소를 잘못 구현했을 때 | 계약 테스트 5개로 잡힌다 | 메서드 수만큼 테스트가 필요하다 |

::: perf 안 A의 전체 스캔은 언제 무너지는가
`borrow()` 한 번은 저장된 대출 전체를 훑는다. 인메모리 저장소에 대출 n건을 넣어 두고 `borrow()` 1회에 걸린 시간:

| n | `borrow()` 1회 |
| --- | --- |
| 100 | 0.008 ~ 0.023 ms |
| 10,000 | 0.398 ~ 0.613 ms |
| 100,000 | 4.63 ~ 11.7 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

깨끗하게 선형이다. **10만 건에서도 한 번에 5~12 ms**라, 과제형 채점에 쓰이는 수십~수백 건 규모에서는 측정 자체가 무의미하다. 안 A를 고르는 근거는 "빨라서"가 아니라 **느려지는 지점이 요구사항보다 훨씬 뒤에 있어서**다.
:::

**과제형에서는 안 A다.** 데이터가 수백 건이고, 평가자가 보는 것은 처리량이 아니라 규칙의 위치다. 안 B가 이기는 조건은 분명하다 — **저장소가 전부를 돌려줄 수 없을 때.** 데이터가 메모리에 안 들어가거나, 진짜 DB가 있어서 인덱스를 태울 수 있을 때다. 그 조건이 요구사항에 없으면 안 B는 그냥 손이 두 배 반 더 가는 설계다.

::: danger 안 B로 갈 때 조용히 새는 것
`overdue_before(on)` 를 저장소 메서드로 만들면, **"연체란 무엇인가"라는 도메인 규칙이 SQL 안으로 들어간다.** 나중에 "공휴일은 연체일에서 뺀다"는 요구사항이 붙으면 그 규칙을 고칠 자리가 `service.py` 가 아니라 SQL 문자열 안이 된다. 그리고 인메모리 구현과 SQLite 구현에 **각각 따로** 고쳐야 한다. 두 벌이 어긋나는 순간, 테스트는 통과하는데 운영에서만 틀린다.

질의를 저장소로 내릴 때는 **"이 조건문이 도메인 규칙인가, 단순한 필터인가"** 를 먼저 물어라. `member_id == x` 는 필터다. `연체 중이다` 는 규칙이다.
:::

## 도메인 — 저장을 모르는 코드

안 A로 간다. 파일 네 개가 도메인이고, 넷 중 어디에도 `json` 이 없다.

```python title="library/models.py"
"""순수 데이터. 저장 방식도, 규칙도 모른다."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Loan:
    loan_id: str
    member_id: str
    book_id: str
    loaned_on: date
    due_on: date
    returned_on: date | None = None

    @property
    def is_active(self) -> bool:
        return self.returned_on is None

    def overdue_days(self, on: date) -> int:
        """on 시점 기준 연체 일수. 기한 내면 0."""
        return max(0, (on - self.due_on).days)
```

`frozen=True` 가 이 절 전체에서 가장 중요한 한 줄이다. **이유는 아래 "인메모리가 통과시키는 거짓말"에서 실행 결과로 본다.** `dataclass` 문법 자체는 [2.6](#/dataclasses)에 있다.

```python title="library/errors.py"
"""이 프로그램이 정의하는 실패. 호출자는 이 뿌리 하나만 알면 된다."""


class LoanError(Exception):
    """대출 규칙 위반의 뿌리."""


class TooManyLoans(LoanError):
    """동시 대출 한도를 넘었다."""


class BookAlreadyLoaned(LoanError):
    """다른 사람이 이미 빌려 간 책이다."""


class HasOverdueLoan(LoanError):
    """연체 중인 대출이 있어 새로 빌릴 수 없다."""


class NotLoaned(LoanError):
    """대출 중이 아닌 책을 반납하려 했다."""
```

뿌리 하나에 잎 넷. 왜 이 모양인지는 [12.5](#/error-design)에 있으니 반복하지 않는다. 1차 시도의 `raise ValueError("연체 중")` 과 비교하면 차이는 하나다 — **호출자가 문자열을 읽지 않고도 어떤 실패인지 구분할 수 있다.**

```python title="library/ports.py"
"""도메인이 바깥에 요구하는 것. 구현은 여기 없다."""
from typing import Protocol

from .models import Loan


class LoanRepository(Protocol):
    def save(self, loan: Loan) -> None:
        """새로 넣거나, 같은 loan_id 가 있으면 덮어쓴다."""
        ...

    def all(self) -> list[Loan]:
        """저장된 모든 대출. 순서는 보장하지 않는다."""
        ...
```

메서드는 둘, docstring은 셋째 줄까지다. 그런데 저 docstring이 곧 **계약**이다. "같은 `loan_id` 면 덮어쓴다", "순서는 보장하지 않는다" — 이 두 문장이 아래에서 그대로 테스트가 된다. `Protocol` 의 타입 이론은 [2.4](#/protocol-typing)와 [1.15](#/protocols)에 있다.

```python title="library/service.py"
"""대출 규칙. 이 파일에는 json, sqlite3, open 이 한 번도 나오지 않는다."""
from dataclasses import replace
from datetime import date, timedelta

from .errors import BookAlreadyLoaned, HasOverdueLoan, NotLoaned, TooManyLoans
from .models import Loan
from .ports import LoanRepository

MAX_ACTIVE = 3
LOAN_DAYS = 14
FINE_PER_DAY = 100


class LoanService:
    def __init__(self, loans: LoanRepository) -> None:
        self._loans = loans

    def borrow(self, member_id: str, book_id: str, on: date) -> Loan:
        rows = self._loans.all()
        active = [ln for ln in rows if ln.is_active]
        mine = [ln for ln in active if ln.member_id == member_id]

        if any(ln.overdue_days(on) > 0 for ln in mine):
            raise HasOverdueLoan(member_id)
        if len(mine) >= MAX_ACTIVE:
            raise TooManyLoans(f"{member_id}: {len(mine)}/{MAX_ACTIVE}")
        if any(ln.book_id == book_id for ln in active):
            raise BookAlreadyLoaned(book_id)

        loan = Loan(
            loan_id=f"L{len(rows) + 1:04d}",
            member_id=member_id,
            book_id=book_id,
            loaned_on=on,
            due_on=on + timedelta(days=LOAN_DAYS),
        )
        self._loans.save(loan)
        return loan

    def give_back(self, book_id: str, on: date) -> int:
        """반납하고 연체료(원)를 돌려준다."""
        for loan in self._loans.all():
            if loan.is_active and loan.book_id == book_id:
                self._loans.save(replace(loan, returned_on=on))
                return loan.overdue_days(on) * FINE_PER_DAY
        raise NotLoaned(book_id)

    def overdue(self, on: date) -> list[Loan]:
        """on 시점에 연체 중인 대출. 오래 밀린 것부터."""
        late = [ln for ln in self._loans.all() if ln.is_active and ln.overdue_days(on) > 0]
        return sorted(late, key=lambda ln: (ln.due_on, ln.loan_id))
```

`borrow` 본문의 규칙 세 줄을 1차 시도와 나란히 놓고 봐라. 조건식이 `any(ln.overdue_days(on) > 0 for ln in mine)` 이 됐다. **`date.fromisoformat` 이 사라졌다.** 사라진 것이 아니라 저장소로 옮겨 갔을 뿐인데, 그 결과 이 함수는 요구사항 문장과 거의 한 줄씩 대응한다.

::: note `loan_id` 를 `len(rows) + 1` 로 만든 것은 의도적인 타협이다
`uuid4()` 를 쓰면 충돌 걱정이 없지만 테스트에서 id를 못 적는다. 이 과제에는 삭제 요구사항도 동시 실행 요구사항도 없고, 저장소는 오직 `save` 로만 자란다. **그 조건에서만** 순번은 유일하다.

전제가 무너지는 조건은 명확하다 — 대출 기록을 지우는 기능이 생기거나, 프로세스가 둘 이상 같은 파일을 쓰면 그날로 깨진다. 이런 판단은 머릿속에만 두지 말고 README의 "알려진 한계"에 적어라([12.8](#/readme-submit)). **한계를 아는 사람과 모르는 사람은 이 한 줄로 갈린다.**
:::

## 저장소 두 개

이제 규칙이 아니라 저장만 하는 파일이다. 여기에만 `json` 이 있다.

```python title="library/repos.py"
"""LoanRepository 의 구현들. 규칙은 한 줄도 없다."""
import json
import os
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .models import Loan


def _to_row(loan: Loan) -> dict:
    row = asdict(loan)
    for k in ("loaned_on", "due_on", "returned_on"):
        row[k] = row[k].isoformat() if row[k] else None
    return row


def _from_row(row: dict) -> Loan:
    return Loan(
        loan_id=row["loan_id"],
        member_id=row["member_id"],
        book_id=row["book_id"],
        loaned_on=date.fromisoformat(row["loaned_on"]),
        due_on=date.fromisoformat(row["due_on"]),
        returned_on=date.fromisoformat(row["returned_on"]) if row["returned_on"] else None,
    )


class InMemoryLoanRepo:
    """테스트와 시연용. 프로세스가 죽으면 같이 사라진다."""

    def __init__(self) -> None:
        self._rows: dict[str, Loan] = {}

    def save(self, loan: Loan) -> None:
        self._rows[loan.loan_id] = loan

    def all(self) -> list[Loan]:
        return list(self._rows.values())


class JsonFileLoanRepo:
    """요구사항이 요구하는 진짜 저장소. 파일 하나에 전부 넣는다."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _read(self) -> dict[str, Loan]:
        if not self._path.exists():
            return {}
        rows = json.loads(self._path.read_text(encoding="utf-8"))
        return {r["loan_id"]: _from_row(r) for r in rows}

    def _write(self, rows: dict[str, Loan]) -> None:
        # 쓰는 도중에 죽어도 반쪽짜리 JSON 이 남지 않도록 임시 파일에 쓰고 바꿔치기한다.
        tmp = self._path.with_suffix(".tmp")
        payload = [_to_row(ln) for ln in rows.values()]
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def save(self, loan: Loan) -> None:
        rows = self._read()
        rows[loan.loan_id] = loan
        self._write(rows)

    def all(self) -> list[Loan]:
        return list(self._read().values())
```

`_write` 의 임시 파일 + `os.replace` 는 세 줄짜리 투자다. `os.replace` 는 같은 파일 시스템 안에서 원자적이라, **쓰다가 죽어도 이전 파일이 그대로 남는다.** 직접 `self._path.write_text(...)` 로 덮으면 중간에 죽었을 때 잘린 JSON이 남고, 다음 실행은 `JSONDecodeError` 로 시작하지 못한다. "이력이 남아야 한다"는 5번 요구사항을 진지하게 읽으면 이 세 줄이 나온다.

조립은 한 군데서만 한다.

```python title="library/main.py"
"""조립하는 유일한 곳. 진짜 저장소가 여기서만 도메인과 만난다."""
from datetime import date
from pathlib import Path

from .repos import JsonFileLoanRepo
from .service import LoanService


def build(db: Path) -> LoanService:
    return LoanService(JsonFileLoanRepo(db))
```

저장소만 갈아 끼우고 같은 시나리오를 두 번 돌려 본다.

```python title="demo.py"
def scenario(repo, label):
    svc = LoanService(repo)
    print(f"[{label}]")
    loan = svc.borrow("M-01", "B-100", date(2025, 3, 2))
    print(f"  대출 {loan.loan_id} 기한 {loan.due_on}")
    try:
        svc.borrow("M-02", "B-100", date(2025, 3, 3))
    except LoanError as exc:
        print(f"  거절 {type(exc).__name__}: {exc}")
    svc.borrow("M-02", "B-200", date(2025, 3, 2))
    print(f"  연체 {[ln.book_id for ln in svc.overdue(date(2025, 3, 20))]}")
    print(f"  반납 연체료 {svc.give_back('B-100', date(2025, 3, 20))}원")


scenario(InMemoryLoanRepo(), "메모리")
db = Path(tempfile.mkdtemp()) / "loans.json"
scenario(JsonFileLoanRepo(db), "파일")
print(db.read_text(encoding="utf-8")[:230] + " ...")
```

```text nolines
[메모리]
  대출 L0001 기한 2025-03-16
  거절 BookAlreadyLoaned: B-100
  연체 ['B-100', 'B-200']
  반납 연체료 400원
[파일]
  대출 L0001 기한 2025-03-16
  거절 BookAlreadyLoaned: B-100
  연체 ['B-100', 'B-200']
  반납 연체료 400원
[
  {
    "loan_id": "L0001",
    "member_id": "M-01",
    "book_id": "B-100",
    "loaned_on": "2025-03-02",
    "due_on": "2025-03-16",
    "returned_on": "2025-03-20"
  },
  {
    "loan_id": "L0002",
    "member_id": "M-02",
   ...
```

**출력이 한 글자도 다르지 않다.** 그리고 `LoanService` 는 자기가 무엇과 이야기하는지 모른다.

## 인메모리가 통과시키는 거짓말

여기가 이 절에서 가장 값어치 있는 함정이다. 그리고 **초록불 테스트가 지켜 주지 못하는 종류**다.

`Loan` 에서 `frozen=True` 를 떼고, `give_back` 을 이렇게 짰다고 하자. 자연스러워 보인다.

```python
    def give_back(self, book_id: str, on: date) -> int:
        for loan in self._loans.all():
            if loan.is_active and loan.book_id == book_id:
                loan.returned_on = on          # ❌ save() 를 부르지 않았다
                return loan.overdue_days(on) * FINE_PER_DAY
        raise NotLoaned(book_id)
```

인메모리 저장소로 테스트하면 **통과한다.** 왜인지는 REPL에서 바로 드러난다.

```pyrepl
>>> import tempfile
>>> from datetime import date
>>> from pathlib import Path
>>> from library.models import Loan
>>> from library.repos import InMemoryLoanRepo, JsonFileLoanRepo
>>> L1 = Loan("L0001", "M-01", "B-100", date(2025, 3, 2), date(2025, 3, 16))
>>> mem = InMemoryLoanRepo()
>>> mem.save(L1)
>>> mem.all()[0] is L1
True
>>> disk = JsonFileLoanRepo(Path(tempfile.mkdtemp()) / "loans.json")
>>> disk.save(L1)
>>> disk.all()[0] is L1
False
>>> disk.all()[0] == L1
True
```

인메모리 저장소의 `all()` 은 **저장한 그 객체 자체**를 돌려준다([1.1](#/objects-names)). 그러니 꺼내서 고치면 저장소 안의 것도 같이 고쳐진다. 파일 저장소는 매번 새로 만들어 돌려주므로 `is` 는 `False`, `==` 는 `True` 다. **같은 값, 다른 객체.** 이 차이 위에 버그가 앉는다.

::: danger 저장소를 바꾸는 순간 터지는 버그, 인메모리로는 못 잡는다
이 테스트를 두 저장소에 대해 한 번씩 돌렸다. 아래 출력은 그 시점의 저장소 테스트 파일 전체(테스트 4개 × 구현 2개 = 8케이스)를 돌린 결과다.

```python
def test_반납하면_다른_사람이_빌릴_수_있다(repo):
    svc = LoanService(repo)
    svc.borrow("M-01", "B-100", date(2025, 3, 2))
    svc.give_back("B-100", date(2025, 3, 10))
    assert svc.borrow("M-02", "B-100", date(2025, 3, 11)).is_active
```

```text nolines
.......F                                                                 [100%]
=========================== short test summary info ============================
FAILED tests/test_repos.py::test_반납하면_다른_사람이_빌릴_수_있다[jsonfile]
1 failed, 7 passed in 0.03s
```

```text nolines
        if any(ln.book_id == book_id for ln in active):
>           raise BookAlreadyLoaned(book_id)
E           library.errors.BookAlreadyLoaned: B-100
```

**`[memory]` 는 통과하고 `[jsonfile]` 만 깨졌다.** 반납이 파일에 반영되지 않아, 반납한 책을 다른 회원이 빌리려 하자 "이미 대출됨"이 나온 것이다.

인메모리 저장소만으로 테스트하고 제출했다면 이 버그는 **평가자가 실제로 프로그램을 두 번 실행할 때** 처음 드러난다. 이건 인메모리 가짜의 결함이 아니라 **가짜와 진짜의 의미론이 다른 지점을 테스트가 덮지 않은** 것이다.
:::

처방은 두 갈래다.

| | 처방 A: `frozen=True` | 처방 B: 인메모리가 복사본을 준다 |
| --- | --- | --- |
| 어떻게 | 도메인 객체를 불변으로. 바꾸려면 `replace()` 후 `save()` | `all()` 에서 `copy.deepcopy` 로 떠서 반환 |
| 잘못된 코드가 | **작성 시점에 막힌다**(`FrozenInstanceError`) | 실행해 보면 반영이 안 되는 걸로 드러난다 |
| 비용 | 갱신할 때마다 새 객체 | 꺼낼 때마다 깊은 복사 |
| 부작용 | `dict`/`set` 키로 쓸 수 있게 된다 | 진짜 저장소의 느린 점만 흉내 낸다 |

**A를 골라라.** B는 가짜를 진짜에 맞춰 나쁘게 만드는 방향이고, A는 **애초에 그 실수를 쓸 수 없게** 만드는 방향이다. `frozen=True` 를 붙이면 위의 `loan.returned_on = on` 은 `dataclasses.FrozenInstanceError: cannot assign to field 'returned_on'` 으로 그 자리에서 죽는다. 그래서 `service.py` 가 `replace(loan, returned_on=on)` 다음에 `save()` 를 부를 수밖에 없다.

::: note 그래도 계약 테스트는 A와 함께 둬야 한다
`frozen=True` 는 **내 도메인 객체**를 지킨다. 저장소 구현이 리스트를 공유하거나 캐시를 잘못 다는 실수는 여전히 가능하다. 그래서 아래 계약 테스트에 이 한 개가 들어간다.

```python
def test_돌려받은_객체를_고쳐도_저장소는_안_변한다(repo):
    repo.save(L1)
    got = repo.all()[0]
    with pytest.raises(FrozenInstanceError):
        got.returned_on = date(2025, 3, 10)
    assert repo.all()[0].returned_on is None
```

테스트 이름이 곧 계약 문장이다([12.6](#/test-strategy)).
:::

## 계약 테스트 — 한 벌로 두 구현을

`Protocol` 은 **모양**만 검사한다. `save` 라는 이름의 메서드가 있는지는 보지만, 그 메서드가 진짜로 저장하는지는 아무도 안 본다. 그 간극을 메우는 것이 **계약 테스트**다. 테스트를 구현별로 쓰지 말고, **한 벌을 쓰고 구현을 파라미터로 돌려라.**

```python title="tests/test_repos.py"
"""저장소 계약. 같은 테스트를 구현마다 한 번씩 돌린다."""
from dataclasses import FrozenInstanceError, replace
from datetime import date

import pytest

from library.models import Loan
from library.repos import InMemoryLoanRepo, JsonFileLoanRepo
from library.service import LoanService

L1 = Loan("L0001", "M-01", "B-100", date(2025, 3, 2), date(2025, 3, 16))


@pytest.fixture(params=["memory", "jsonfile"])
def repo(request, tmp_path):
    if request.param == "memory":
        return InMemoryLoanRepo()
    return JsonFileLoanRepo(tmp_path / "loans.json")


def test_빈_저장소는_빈_목록을_돌려준다(repo):
    assert repo.all() == []


def test_저장한_것을_그대로_돌려준다(repo):
    repo.save(L1)
    assert repo.all() == [L1]


def test_같은_id_로_저장하면_덮어쓴다(repo):
    repo.save(L1)
    repo.save(replace(L1, returned_on=date(2025, 3, 10)))
    assert len(repo.all()) == 1
    assert repo.all()[0].returned_on == date(2025, 3, 10)


def test_돌려받은_객체를_고쳐도_저장소는_안_변한다(repo):
    repo.save(L1)
    got = repo.all()[0]
    with pytest.raises(FrozenInstanceError):
        got.returned_on = date(2025, 3, 10)
    assert repo.all()[0].returned_on is None


def test_서비스가_어느_저장소에서든_같게_동작한다(repo):
    svc = LoanService(repo)
    svc.borrow("M-01", "B-100", date(2025, 3, 2))
    assert svc.give_back("B-100", date(2025, 3, 20)) == 400
```

```text nolines
tests/test_repos.py::test_빈_저장소는_빈_목록을_돌려준다[memory] PASSED  [ 10%]
tests/test_repos.py::test_빈_저장소는_빈_목록을_돌려준다[jsonfile] PASSED [ 20%]
tests/test_repos.py::test_저장한_것을_그대로_돌려준다[memory] PASSED     [ 30%]
tests/test_repos.py::test_저장한_것을_그대로_돌려준다[jsonfile] PASSED   [ 40%]
tests/test_repos.py::test_같은_id_로_저장하면_덮어쓴다[memory] PASSED    [ 50%]
tests/test_repos.py::test_같은_id_로_저장하면_덮어쓴다[jsonfile] PASSED  [ 60%]
tests/test_repos.py::test_돌려받은_객체를_고쳐도_저장소는_안_변한다[memory] PASSED [ 70%]
tests/test_repos.py::test_돌려받은_객체를_고쳐도_저장소는_안_변한다[jsonfile] PASSED [ 80%]
tests/test_repos.py::test_서비스가_어느_저장소에서든_같게_동작한다[memory] PASSED [ 90%]
tests/test_repos.py::test_서비스가_어느_저장소에서든_같게_동작한다[jsonfile] PASSED [100%]

============================== 10 passed in 0.04s ==============================
```

테스트 함수는 다섯 개인데 케이스는 열 개다. **저장소를 하나 더 만들면 자동으로 열다섯 개가 된다.** `fixture` 파라미터화 문법은 [6.2](#/pytest-advanced)에 있다.

::: tip 테스트를 어디에 나눌 것인가
| 파일 | 무엇을 검증하는가 | 어떤 저장소로 |
| --- | --- | --- |
| `tests/test_rules.py` | 3권 제한, 연체료, 중복 대출 금지 | **인메모리 하나**로 충분 |
| `tests/test_repos.py` | 저장소가 계약을 지키는가 | **전 구현**을 돌린다 |

규칙 테스트를 파일 저장소로 돌리지 마라. 느려지기만 하고 검증하는 것은 같다. 반대로 저장소 계약 테스트를 인메모리로만 돌리면 위의 함정에 그대로 걸린다. **무엇을 테스트하는지가 어떤 저장소를 쓸지를 정한다.**
:::

전체를 돌리면 이렇다.

```bash
uv run --python 3.14 --with pytest pytest -q
```

```text nolines
...................                                                      [100%]
19 passed in 0.05s
```

::: warn Protocol 은 검사기를 돌려야 검사한다
`JsonFileLoanRepo.all` 의 이름을 실수로 `find_all` 로 바꿔도 파이썬은 아무 말이 없다. 조립 지점(`main.py`)에서 mypy 를 돌려야 잡힌다.

```text nolines
library/main.py:10: error: Argument 1 to "LoanService" has incompatible type "JsonFileLoanRepo"; expected "LoanRepository"  [arg-type]
library/main.py:10: note: "JsonFileLoanRepo" is missing following "LoanRepository" protocol member:
library/main.py:10: note:     all
Found 1 error in 1 file (checked 7 source files)
```

(mypy 1.19.1 실측.) `Protocol` 을 쓰기로 했으면 검사기를 실제로 돌려라([2.8](#/typecheckers)). 이 이야기는 [12.4](#/boundaries-di)에서 이미 다뤘고, 여기서 달라지는 건 하나다 — **계약 테스트가 있으면 검사기를 못 돌리는 환경에서도 이 실수가 잡힌다.** 정적 검사와 계약 테스트는 서로 다른 종류의 실수를 잡는다.
:::

## 무엇이 나중에 이득이 되는가

여기까지가 분리의 비용이다. 파일 두 개(`ports.py`, `repos.py`)와 생성자 인자 하나. 이제 그 값을 회수하는 장면을 본다.

**① 요구사항이 하나 늘었다 — "연체 목록을 뽑아 달라."**

`service.py` 에 메서드 하나가 붙는다. 저장소는 **한 글자도 안 바뀐다.**

```python
    def overdue(self, on: date) -> list[Loan]:
        late = [ln for ln in self._loans.all() if ln.is_active and ln.overdue_days(on) > 0]
        return sorted(late, key=lambda ln: (ln.due_on, ln.loan_id))
```

안 B(질의 메서드형)를 골랐다면 여기서 `overdue_before` 를 **모든 저장소 구현에** 추가해야 했다. 그것이 위 표의 "요구사항이 하나 늘면" 칸이 말하던 것이다.

**② 저장 방식이 바뀌었다 — "JSON 대신 SQLite로."**

`repos.py` 에 클래스 하나가 붙는다.

```python title="library/repos.py 에 추가"
class SqliteLoanRepo:
    """3주 차에 추가된 세 번째 구현. 도메인은 한 글자도 안 바뀌었다."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS loans ("
            " loan_id TEXT PRIMARY KEY, member_id TEXT, book_id TEXT,"
            " loaned_on TEXT, due_on TEXT, returned_on TEXT)"
        )

    def save(self, loan: Loan) -> None:
        row = _to_row(loan)
        self._conn.execute(
            "INSERT INTO loans VALUES (:loan_id, :member_id, :book_id,"
            " :loaned_on, :due_on, :returned_on)"
            " ON CONFLICT(loan_id) DO UPDATE SET returned_on = :returned_on",
            row,
        )
        self._conn.commit()

    def all(self) -> list[Loan]:
        cur = self._conn.execute(
            "SELECT loan_id, member_id, book_id, loaned_on, due_on, returned_on FROM loans"
        )
        keys = [d[0] for d in cur.description]
        return [_from_row(dict(zip(keys, r))) for r in cur.fetchall()]
```

계약 테스트에는 파라미터 하나와 분기 두 줄이 붙는다.

```python
@pytest.fixture(params=["memory", "jsonfile", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        return InMemoryLoanRepo()
    if request.param == "jsonfile":
        return JsonFileLoanRepo(tmp_path / "loans.json")
    return SqliteLoanRepo(sqlite3.connect(tmp_path / "loans.db"))
```

```text nolines
........................                                                 [100%]
24 passed in 0.13s
```

**바뀐 파일은 둘뿐이다.** `repos.py` 에 29줄이 붙었고 `tests/test_repos.py` 가 +6/−3 이다. `models.py`, `errors.py`, `ports.py`, `service.py` — **도메인 네 파일은 0줄.** 그리고 새 구현은 처음 돌리는 순간부터 다섯 개의 계약 테스트를 통과해야 했다. 실제로 통과했다는 사실 자체가 `Protocol` 의 두 줄짜리 docstring이 진짜 계약이었다는 증거다.

::: danger 그런데 이걸 미리 만들면 감점이다
위 SQLite 구현은 **요구사항이 실제로 바뀐 다음에** 붙인 것이다. 요구사항이 "저장 방식은 자유"일 때 세 개를 다 넣어 제출하면 평가자가 읽는 것은 이렇다.

> 이 지원자는 요구사항이 시키지 않은 저장소 구현을 하나 더 만들었다. 프로그램은 그걸 쓰지 않는다.

과제형 제출물의 정답 구성은 **진짜 구현 하나 + 테스트용 가짜 하나**다. 세 번째부터는 요구사항이 시켜야 만든다. [12.1](#/takehome-eval)의 "확장 가능한가 — 그리고 그 함정"이 정확히 이 이야기다.

**분리의 가치는 "구현이 여러 개인 것"이 아니라 "하나를 바꿀 때 도메인을 안 여는 것"이다.** 구현이 하나여도 이득은 이미 다 받았다.
:::

## 값을 치른 곳 — 파일 저장소는 느리다

정직하게 비용도 재자. `JsonFileLoanRepo.save` 는 **저장할 때마다 파일 전체를 읽고 전체를 다시 쓴다.** n건을 순서대로 저장하면 $O(n^2)$ 이다.

::: perf 대출 n건을 하나씩 저장하는 데 걸린 시간
| n | `InMemoryLoanRepo` | `JsonFileLoanRepo` |
| --- | --- | --- |
| 100 | 0.012 ~ 0.015 ms | 86.4 ~ 89.3 ms |
| 300 | 0.032 ~ 0.050 ms | 620 ~ 639 ms |
| 1,000 | 0.098 ~ 0.140 ms | 6,718 ~ 6,752 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**n이 10배가 되자 시간은 76~78배가 됐다.** 정확히 이차식이 하는 일이다. 1,000건을 넣는 데 6.7초라면, 1만 건은 분 단위다.
:::

그런데 **어디가 느린지**를 재 보면 예상과 다르다. 1,000건이 든 파일(166 KB)에 `save()` 한 번을 나눠 재면 이렇다.

::: perf 느린 것은 디스크가 아니다
| 구간 | 시간 |
| --- | --- |
| `save()` 1회 | 12.3 ~ 60.7 ms |
| ├ `_read()` | 2.91 ~ 4.93 ms |
| │ └ `json.loads` | 1.28 ~ 1.42 ms |
| ├ `_write()` | 9.70 ~ 19.3 ms |
| │ ├ `_to_row` × 1000 | 7.90 ~ 9.49 ms |
| │ ├ `json.dumps` | 1.10 ~ 1.49 ms |
| │ └ `write` + `os.replace` | 0.20 ~ 0.53 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**실제 디스크 쓰기는 전체의 5%도 안 된다.** 시간의 대부분은 `_to_row` 안의 `dataclasses.asdict` 가 먹는다. `asdict` 는 필드를 재귀적으로 훑으면서 dataclass가 아닌 값에 `copy.deepcopy` 를 건다. 손으로 `dict` 를 짜면 이렇게 갈린다.

| 1,000개 변환 | 시간 |
| --- | --- |
| `asdict(ln)` | 6.46 ~ 13.4 ms |
| 필드를 직접 나열 | 0.92 ~ 1.85 ms |

**7배다.** 직렬화가 병목인 코드에서 `asdict` 는 첫 번째 용의자다([2.6](#/dataclasses)).
:::

::: warn 그러니 지금 고치라는 말이 아니다
과제 데이터가 수백 건이면 `save()` 한 번은 밀리초 단위다. 여기서 `asdict` 를 손으로 푼 `dict` 로 바꾸면 코드가 여섯 줄 길어지고 필드를 추가할 때 고칠 자리가 하나 늘어난다. **읽기 쉬운 쪽을 남기고 한계를 적는 것이 옳은 판단이다.**

README에는 이렇게 한 줄이면 된다.

> `JsonFileLoanRepo` 는 저장할 때마다 파일 전체를 다시 쓴다. 대출 1,000건 기준 저장 1회 약 12 ms 이며 건수의 제곱에 비례한다. 수천 건 이상이 필요하면 `SqliteLoanRepo` 를 추가하면 되고, 도메인 코드는 바뀌지 않는다.

**측정하지 않고 "느릴 수 있습니다"라고 쓰면 아무 값이 없다. 측정하고 숫자와 한계선을 적으면 그 자체가 평가 항목이다**([12.8](#/readme-submit)).
:::

## 과하게 설계하지 않는 선

저장소 패턴은 오버엔지니어링이 가장 잘 자라는 밭이다. 실제 제출물에서 반복해서 보이는 것들이다.

```python
# ❌ 타입 하나뿐인데 제네릭 저장소를 만든다
class Repository[T](Protocol):
    def save(self, entity: T) -> None: ...
    def get(self, key: str) -> T | None: ...
    def all(self) -> list[T]: ...

class LoanRepository(Repository[Loan], Protocol): ...

# ✅ 엔티티가 하나면 제네릭은 이름만 늘린다
class LoanRepository(Protocol):
    def save(self, loan: Loan) -> None: ...
    def all(self) -> list[Loan]: ...
```

```python
# ❌ 트랜잭션 요구사항이 없는데 UnitOfWork 를 만든다
with UnitOfWork(repo) as uow:
    uow.loans.save(loan)
    uow.commit()

# ✅ 저장은 한 번, 실패하면 예외
repo.save(loan)
```

```python
# ❌ 저장소 위에 캐시를 얹는다
class CachedLoanRepo:
    def __init__(self, inner, ttl=60): ...

# ✅ 성능 요구사항이 나오면 그때. 지금은 캐시 무효화 버그만 산다
```

::: danger 저장소를 아예 만들지 말아야 할 때도 있다
요구사항 5번이 **없었다면** 이 절의 설계 절반은 감점 요인이다. 프로그램이 도는 동안만 데이터가 살아 있으면 되는 과제라면, `LoanService` 가 `dict` 하나를 들고 있는 것이 정답이다. `Protocol` 도 `repos.py` 도 필요 없다.

판단 기준은 딱 하나다. **"요구사항에 저장이 있는가."** 있으면 끊고, 없으면 만들지 마라. [12.4](#/boundaries-di)의 Q1~Q3에 "나중에"라는 항목이 없는 이유가 이것이다.
:::

::: tip 반대로 이 정도는 과하지 않다
- 도메인 예외 계층 다섯 개 — 실패 종류가 실제로 다섯 가지다.
- `frozen=True` — 값을 사지 않고 버그 한 종류를 통째로 없앤다.
- 계약 테스트 다섯 개 — 구현이 늘 때마다 공짜로 재사용된다.
- `os.replace` 원자적 쓰기 — 세 줄이고, 요구사항 5번이 시켰다.

**과한 설계와 필요한 설계를 가르는 것은 줄 수가 아니라 "요구사항 문장을 짚을 수 있는가"다.** 짚을 수 있으면 남기고, 못 짚으면 지워라.
:::

## 최종 구조

```text nolines
   loan-task/
   ├── README.md
   ├── conftest.py           <- 빈 파일. pytest 가 루트를 sys.path 에 넣게 한다
   ├── library/
   │   ├── __init__.py
   │   ├── models.py         <- Loan. 순수 데이터
   │   ├── errors.py         <- 도메인 예외
   │   ├── ports.py          <- LoanRepository (Protocol)
   │   ├── service.py        <- 규칙. 저장 방법을 모른다
   │   ├── repos.py          <- InMemory / JsonFile 구현
   │   └── main.py           <- 조립 지점
   └── tests/
       ├── test_rules.py     <- 규칙. 인메모리 하나로
       └── test_repos.py     <- 저장소 계약. 구현마다 반복
```

의존 방향은 한쪽으로만 흐른다.

```text nolines
   service.py ──▶ ports.py ◀── repos.py
       │                          │
       └──────▶ models.py ◀───────┘

   main.py ──▶ service.py + repos.py      (조립은 여기서만)
```

`repos.py` 는 `service.py` 를 모르고, `service.py` 는 `repos.py` 를 모른다. **둘은 `ports.py` 에서만 만난다.** 이 그림을 README에 그대로 넣어라 — 평가자가 5분 안에 구조를 이해하는 가장 싼 방법이다. 구조를 왜 이렇게 나누는지는 [12.7](#/project-structure), README에 무엇을 적는지는 [12.8](#/readme-submit)에 있다.

::: note 파일이 일곱 개면 많은 것 아닌가
`library/` 일곱 파일이 197줄, `tests/` 두 파일이 117줄, 합쳐 314줄이다. 파일 수가 아니라 **파일당 책임 수**를 봐라. `models.py` 21줄, `ports.py` 14줄, `service.py` 51줄, `repos.py` 67줄. 각 파일을 열었을 때 "이 파일은 무엇을 하는가"에 한 문장으로 답할 수 있으면 충분하다.

반대로 이 규모의 과제에 `domain/`, `application/`, `infrastructure/` 세 겹 디렉터리를 파면 그건 다른 이야기다. **디렉터리는 파일이 열 개를 넘을 때 만든다.**
:::

## 요약

- 저장소를 끊는 이유는 "나중에 DB를 바꿀지 몰라서"가 아니라 **요구사항이 영속성을 요구했기 때문**이다. 요구사항 문장을 짚을 수 없으면 만들지 마라.
- 저장소 인터페이스는 **작을수록 이긴다.** `save` + `all` 두 개면 규칙이 전부 도메인에 남는다. 질의 메서드를 늘리면 도메인 규칙이 저장소 구현마다 복제된다.
- 안 A(전체 스캔)가 무너지는 지점은 **10만 건 근처**다(`borrow()` 1회 5~12 ms). 과제 규모보다 세 자릿수 뒤에 있다.
- **인메모리 가짜는 진짜와 의미론이 다르다.** `all()` 이 같은 객체를 돌려주기 때문에, `save()` 를 빠뜨린 코드가 인메모리에서만 통과한다. `frozen=True` 가 그 실수를 작성 시점에 막는다.
- **계약 테스트 한 벌을 파라미터화해서 모든 구현에 돌려라.** 테스트 5개가 구현 2개에서 케이스 10개, 구현 3개에서 15개가 된다. `Protocol` 은 모양만 보고, 계약 테스트가 의미를 본다.
- 분리의 대가는 파일 두 개와 생성자 인자 하나다. 회수는 **저장소를 갈아 끼울 때 도메인 0줄**로 돌아온다.
- 파일 저장소가 느린 이유는 디스크가 아니라 `dataclasses.asdict` 다 — 저장 시간의 절반 이상을 먹고, 실제 디스크 쓰기는 5%도 안 된다. **그래도 지금 고치지 마라. 측정하고 README에 한계를 적어라.**

::: quiz 과제 — 읽지 말고 고쳐라
이 절의 프로젝트를 그대로 옮겨 놓고 시작한다. 전부 **실제로 실행하고 `pytest` 를 통과시켜야** 한다.

**1. 계약을 깨뜨려 보고 계약 테스트가 잡는지 확인해라.**
`InMemoryLoanRepo.save` 를 `self._rows[loan.loan_id] = loan` 대신 `self._rows.setdefault(loan.loan_id, loan)` 으로 바꿔라. 다섯 개 테스트 중 몇 개가, 어느 파라미터에서 깨지는가? 깨진 테스트 이름이 **무엇이 위반됐는지를 문장으로 말해 주는지** 확인해라. 말해 주지 않는다면 테스트 이름을 고쳐라.

**2. CSV 저장소를 추가해라.**
`csv` 표준 라이브러리로 `CsvLoanRepo` 를 구현하고 계약 테스트 파라미터에 추가해서 **15개를 통과**시켜라. 도메인 파일 네 개(`models`/`errors`/`ports`/`service`)를 한 줄이라도 고쳤다면, 무엇 때문에 고쳐야 했는지 적어라 — 그것이 이 설계의 진짜 구멍이다.

**3. 삭제 요구사항을 받아라.**
"회원 탈퇴 시 그 회원의 대출 기록을 지운다"가 추가됐다. `LoanRepository` 에 `delete(loan_id)` 를 넣고 구현해라. 그러고 나서 **`loan_id = f"L{len(rows) + 1:04d}"` 가 무너지는 시나리오를 테스트로 재현**하고, 고쳐라. 고칠 때 선택지가 둘 이상이다(최대 순번 추적 / UUID / 저장소가 id를 발급). **셋을 나란히 적고 하나를 고른 이유를 세 줄로 쓴다.**

**4. 안 B로 리팩터링하고 비용을 세어라.**
`active_by_member`, `active_by_book`, `overdue_before` 를 저장소 메서드로 옮겨라. 두 구현과 테스트를 모두 고친 뒤 **바뀐 총 줄 수를 세어라.** 그리고 "공휴일은 연체일에서 제외한다"는 요구사항을 추가로 넣어 보고, 안 A일 때와 안 B일 때 **고쳐야 하는 파일 수**를 비교해라.

**5. 성능 요구사항이 붙었다면.**
"대출 기록 5만 건에서도 대출 처리가 100 ms 안에 끝나야 한다"가 요구사항에 있다고 하자. `JsonFileLoanRepo` 로는 불가능하다. **가장 먼저 무엇을 바꿀 것인가**를 정하고, 바꾸기 전과 후를 직접 측정해서 표로 만들어라. 추정치를 쓰지 마라.

**6. 과한 설계를 골라내라.**
아래 다섯 중 이 요구사항에서 **삭제해야 하는 것**을 고르고, 각각 한 줄로 이유를 써라.

| | 후보 | 무엇인가 |
| --- | --- | --- |
| (a) | `LoanRepository(Protocol)` | 저장소 포트 |
| (b) | `Repository[T](Protocol)` | 엔티티 타입으로 매개변수화한 공통 저장소 |
| (c) | `CachedLoanRepo` | 저장소를 감싸는 TTL 캐시 |
| (d) | `Loan` 에 붙은 `frozen=True` | 도메인 객체 불변화 |
| (e) | `LoanEventPublisher(Protocol)` | 대출/반납 이벤트 발행 포트 |

정답 개수를 세는 문제가 아니다. **각 항목에 대해 "요구사항 몇 번이 이걸 시켰는가"에 답할 수 있는지**가 전부다. 답할 수 없으면 그건 지울 것이다.
:::

**다음 절**: [12.11 제출 전 자기 코드 리뷰](#/self-review) — 다 짰다. 이제 평가자의 눈으로 내 코드를 한 번 더 읽는다.
