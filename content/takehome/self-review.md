# 12.11 제출 전 자기 코드 리뷰

::: lead
코드를 다 짰고 테스트가 통과한다. 남은 시간은 한 시간. 여기서 대부분의 사람이 **기능을 하나 더 넣는다.** 그게 가장 흔한 실수다. 제출물의 점수를 마지막 한 시간에 가장 크게 올리는 일은 새 코드가 아니라 **이미 쓴 코드를 남의 것처럼 다시 읽는 것**이다. 문제는 그게 안 된다는 데 있다 — 세 시간 전의 내가 쓴 코드는 눈에 너무 익어서 안 읽힌다. 이 절은 **자기 코드를 억지로 낯설게 만드는 절차**와, 그렇게 찾아낸 것 중 **무엇을 고치고 무엇을 그냥 적어 두고 낼 것인가**의 판단을 다룬다.
:::

## 세 시간 전의 내가 쓴 코드는 안 읽힌다

자기 코드를 읽을 때 당신은 코드를 읽는 게 아니다. **기억을 재생한다.** `process(user, s, d, True)` 를 보면 눈이 글자를 훑기 전에 머리가 "아 취소하는 거"라고 답을 채워 넣는다. 평가자에게는 그 자동 완성이 없다. 그 사람은 `True` 가 무엇인지 알아내려고 함수 정의로 올라가야 하고, **올라가야 한다는 사실 자체가 감점**이다.

그래서 자기 리뷰는 의지의 문제가 아니라 **절차의 문제**다. 기억이 개입하지 못하게 만드는 조작이 필요하다. 이 절에서 쓰는 조작은 셋이다.

1. **읽는 순서를 작성 순서와 다르게 만든다.** 위에서 아래로 읽으면 짤 때와 같은 길을 지나므로 같은 착각을 그대로 반복한다.
2. **본문을 가리고 이름만 본다.** 이름이 혼자서 말을 하는지 확인하는 유일한 방법이다.
3. **기계에게 먼저 읽힌다.** 사람 눈이 확실히 놓치는 종류가 있고, 그건 1초 만에 끝난다.

### 리뷰 대상 — 스터디룸 좌석 예약

이 절 내내 쓸 제출물이다. 요구사항은 다섯 줄이다.

> **스터디룸 좌석 예약 모듈**
>
> 1. 좌석은 행 문자(`A` 부터)와 열 번호(`1` 부터)로 식별한다. 예: `A1`, `C12`.
> 2. 이미 예약된 좌석은 다른 사람이 예약할 수 없다.
> 3. 한 사람이 동시에 가질 수 있는 좌석은 최대 2석이다.
> 4. 취소는 본인이 예약한 좌석만 가능하다.
> 5. 전체 예약 좌석 목록과 특정 사용자의 좌석 목록을 조회할 수 있다.

세 시간 만에 짰고, 테스트 다섯 개가 통과한다. 지금 상태는 이렇다.

```python title="seatmap.py — 제출 한 시간 전, 아직 아무도 안 읽은 코드"
from datetime import date


class SeatManager:
    """좌석 예약을 관리하는 클래스"""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.data = {}          # 좌석 -> (사용자, 날짜)
        self.cnt = 0

    def check(self, s):
        # 좌석 문자열이 올바른지 확인한다
        if len(s) < 2:
            return False
        if not ("A" <= s[0] < chr(ord("A") + self.rows)):
            return False
        if not s[1:].isdigit():
            return False
        return 1 <= int(s[1:]) <= self.cols

    def process(self, user, s, d, cancel=False):
        if not self.check(s):
            return False
        if cancel:
            if s in self.data and self.data[s][0] == user:
                del self.data[s]
                self.cnt -= 1
                return True
            return False
        if s in self.data:
            return False
        if len([1 for u, _ in self.data.values() if u == user]) >= 2:
            return False
        self.data[s] = (user, d)
        self.cnt += 1
        return True

    def get(self, user=None):
        if user is None:
            return sorted(self.data.keys())
        return sorted(k for k, v in self.data.items() if v[0] == user)
```

```bash
$ pytest -q
.....                                                                    [100%]
5 passed in 0.02s
```

배치는 모듈이 저장소 루트의 `seatmap.py`, 테스트가 `tests/test_seatmap.py` 다. **이 절의 모든 `pytest` 출력은 루트에 이 설정이 있다고 가정한다.**

```toml title="pyproject.toml"
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`pythonpath` 한 줄이 없으면 `pytest` 는 `tests/` 만 `sys.path` 에 넣고 그 위의 루트는 넣지 않아서, 첫 줄의 `from seatmap import SeatManager` 가 `ModuleNotFoundError: No module named 'seatmap'` 로 **수집 단계에서 죽는다.** 테스트가 하나도 안 돌므로 아래의 `5 passed` 도 `17 passed` 도 재현되지 않는다. 같은 일을 하는 **빈 `conftest.py`** 를 대신 써도 되지만, 그 경우 파일 안에 왜 있는지 한 줄을 남겨야 한다 — 두 안의 차이와 왜 과제 제출에는 `pythonpath` 쪽인지는 [12.1](#/takehome-eval)에서 실측과 함께 정했다.

**요구사항 다섯 개가 다 구현돼 있고 테스트가 전부 통과한다.** 그런데 이 코드에는 **요구사항 2를 정면으로 위반하는 버그가 하나 들어 있다.** 뒤에서 찾는다. 지금 눈으로 찾아보려고 애쓰지 마라 — 못 찾는 게 정상이고, 그게 이 절이 존재하는 이유다.

## 리뷰는 밖에서 안으로 — 네 번의 패스

한 번에 다 보려고 하면 아무것도 못 본다. 패스마다 **한 가지만** 본다.

```text nolines
  pass 1  outside    clean 복제본에서 README 대로 실행 -> pytest -> ruff  5min
  pass 2  names      본문을 가리고 공개 이름만 뽑아서 읽는다              5min
  pass 3  bodies     함수 하나씩. 다섯 가지 질문만 던진다                 15min
  pass 4  tests      테스트 이름만 이어 읽고 요구사항이 복원되는지 본다   5min
  -----------------------------------------------------------------------------
  decide             찾은 것 중 무엇을 고칠지 정한다. 전부 고치지 않는다  5min
```

30분이다. 남은 30분이 실제 수정 시간이다. 순서가 이런 이유는 **바깥 패스에서 걸리면 안쪽이 의미가 없기 때문**이다. 실행이 안 되는 코드의 변수명을 다듬는 건 아무 값이 없다([12.1](#/takehome-eval)의 관문 순서와 같은 논리다).

::: note 이 절이 다른 절과 겹치지 않는 지점
"무엇을 테스트할 것인가"는 [12.6](#/test-strategy), "README에 무엇을 적을 것인가"는 [12.8](#/readme-submit), "제출물이 실행되는가"는 [12.1](#/takehome-eval)에 있다. 이 절은 그 셋을 다시 설명하지 않는다. **이미 다 만들어 놓은 것을 마지막에 어떤 눈으로 다시 보는가**만 다룬다. 절차가 겹치는 곳에서는 링크만 걸고 넘어간다.

실패를 예외로 표현할지 반환값으로 표현할지는 [12.5](#/error-design)다. 거기도 좌석 예약을 소재로 쓰지만 **별개의 과제다** — 좌석 코드 형식부터 다르고(거기는 `A-1`, 여기는 `A1`), 거기는 실패 표현을 처음부터 고르는 훈련이다. 여기서는 그 설계를 **지금 도입할지 말지의 판단**만 다룬다. 아래 "고치지 말아야 할 것"의 안 B가 정확히 12.5의 결론인데, 이 절의 답은 "옳지만 지금은 아니다"다. **두 절을 이어서 읽되 코드를 섞지 마라.**
:::

## 패스 1 — 기계에게 먼저 읽힌다

clean 복제본에서 README의 명령을 그대로 복사해 붙이는 리허설은 [12.8](#/readme-submit)에 있다. 여기서는 그다음, **린터를 돌리는 5초**를 말한다.

```bash
$ ruff check .
F401 [*] `datetime.date` imported but unused
 --> seatmap.py:1:22
  |
1 | from datetime import date
  |                      ^^^^
  |
help: Remove unused import: `datetime.date`

Found 1 error.
[*] 1 fixable with the `--fix` option.
```

(ruff 0.15.8 기준 실측. 진단 표시가 **0.12.9에서 바뀌었다** — 그 이전 버전은 `seatmap.py:1:22: F401 [*] ...` 처럼 파일·행·열이 코드 앞에 오고 `help:` 도 `= help:` 로 찍는다. 같은 진단이므로 읽는 데는 지장이 없다.)

`date` 를 타입 힌트로 쓰려다 말았고 그 흔적이 남았다. 한 줄짜리 문제지만 **평가자가 파일을 열자마자 첫 줄에서 보게 되는 것**이다. 첫 줄에 쓰지 않는 import가 있으면 나머지 코드도 정리되지 않았을 거라는 인상이 먼저 만들어진다.

린터가 잡는 것은 대체로 이 종류다. 쓰지 않는 import와 변수, 도달 불가능한 코드, 섀도잉된 이름, 비어 있는 `except`. **전부 사람 눈이 확실히 놓치는 것들**이고, 전부 "정리를 안 했다"는 신호로 읽힌다. 설정은 [0.4 린터·포매터·타입체커 세팅](#/tooling)에 있다.

::: tip 리뷰 루프는 1초 안에 끝난다 — 그러니 이름 하나 고칠 때마다 돌려라
좌석 예약 모듈(소스 60줄, 테스트 17개)에서 각 도구의 실행 시간이다.

| 명령 | 7회 실행 |
| --- | --- |
| `ruff check .` | 0.008 ~ 0.013 s |
| `pytest -q` | 0.294 ~ 0.785 s |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

`pytest` 쪽 시간의 거의 전부가 인터프리터와 플러그인 로딩이다. 테스트 17개를 실제로 도는 데는 0.03초가 걸린다. **한 바퀴가 1초면 "이름 하나 바꾸고 돌려 본다"가 가능해진다.** 마지막 30분에 리팩터링을 해도 되는지를 가르는 것이 사실 이 숫자다.
:::

## 패스 2 — 본문을 가리고 이름만 읽는다

가장 값싸고 가장 잔인한 패스다. **소스에서 공개 이름만 뽑아서 그것만 읽는다.** 사람이 자기 코드에 대해 갖고 있는 배경 지식을 최대한 무력화하는 방법이다.

```python title="tools/surface.py — 공개 이름만 뽑아 출력한다"
"""소스 파일에서 공개 이름만 뽑아 출력한다. 본문은 읽지 않는다."""
import ast
import sys

for path in sys.argv[1:]:
    print(f"# {path}")
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        if isinstance(node, ast.ClassDef):
            print(f"class {node.name}")
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and not sub.name.startswith("_"):
                    print(f"    .{sub.name}({', '.join(a.arg for a in sub.args.args[1:])})")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            print(f"{node.name}({', '.join(a.arg for a in node.args.args)})")
```

`ast` 는 [3.6 AST와 코드 생성](#/ast)에서 다뤘다. 여기서는 **파일 하나를 파싱해서 이름만 찍는 열두 줄**로 쓴다. 돌려 보면 이렇다.

```bash
$ python tools/surface.py seatmap.py
# seatmap.py
class SeatManager
    .check(s)
    .process(user, s, d, cancel)
    .get(user)
```

이 네 줄을 아무 배경 없이 읽어 보라. **무엇을 하는 프로그램인지 하나도 알 수 없다.** `check` 는 무엇을 확인하는가. `process` 는 무엇을 처리하는가. `get` 은 무엇을 가져오는가. `s` 와 `d` 는 무엇인가. 좌석이라는 단어가 클래스 이름 말고는 어디에도 없다.

이름만 읽을 때 던지는 질문은 넷이다.

| 질문 | 걸리면 |
| --- | --- |
| 동사가 **무엇을** 하는지 말하는가 | `process`, `handle`, `do`, `run` |
| 반환값이 이름에서 예측되는가 | `get` 이 리스트인지 하나인지 모른다 |
| 인자 이름이 정체나 단위를 말하는가 | `s`, `d`, `t`, `n` |
| 불리언 인자가 있는가 | 함수 하나에 함수 두 개가 들어 있다 |

::: danger 불리언 플래그 인자는 함수 두 개를 한 이름에 숨긴 것이다
```python
# ❌ 호출부만 보면 True 가 무엇인지 알 수 없다
manager.process("kim", "A1", today, True)

# ✅ 이름이 곧 동작이다
seat_map.cancel("kim", "A1")
```

플래그 인자를 알아보는 기준은 하나다. **본문이 그 인자 하나로 두 덩이로 갈라지고, 두 덩이가 다시 만나지 않으면 그건 두 개의 함수다.** `process` 는 검증 한 줄(`if not self.check(s)`)을 지나자마자 `if cancel:` 로 갈라져서, 예약 경로와 취소 경로가 끝까지 만나지 않는다. 공유하는 것은 그 좌석 유효성 검사 한 줄뿐이고, 그건 함수를 따로 부르면 된다.

기준을 "첫 줄"이 아니라 "두 덩이"로 잡는 이유가 여기 있다. 분기 위에 **양쪽이 공유하는 전처리**가 몇 줄 있는 것은 흔하고, 그 줄 수는 판단과 아무 상관이 없다. 봐야 하는 것은 **갈라진 뒤 두 경로가 다시 합류하는가**다. 합류한다면 그건 진짜 옵션이고, 안 한다면 함수 두 개다.

쪼개면 부수적으로 인자도 줄어든다. **취소에는 날짜가 필요 없다.** `process(user, s, d, cancel=True)` 는 쓰지도 않는 `d` 를 호출자에게 요구하고 있었다. 쓰지 않는 인자는 "이 값이 결과에 영향을 준다"는 거짓말이다.
:::

이름을 고친 결과는 이렇다. **왼쪽을 오른쪽으로 바꾸는 데 든 시간이 4분**이다.

| 지금 | 고친 뒤 | 근거 |
| --- | --- | --- |
| `SeatManager` | `SeatMap` | `~Manager` 는 책임을 안 정했다는 표시다([12.2](#/requirements-to-model)) |
| `.data` | `._reservations` | 무엇이 들었는지 이름이 말한다. 게다가 내부 상태다 |
| `.cnt` | (삭제) | 뒤에서 다룬다. 아무도 읽지 않는다 |
| `.check(s)` | `.is_valid_seat(seat)` | 불리언을 반환한다는 것이 이름에 있다 |
| `.process(...)` | `.reserve(...)` / `.cancel(...)` | 함수 두 개를 분리한다 |
| `.get(user=None)` | `.reserved_seats()` / `.seats_of(user)` | 인자에 따라 의미가 바뀌는 함수를 나눈다 |

::: warn 여기서 멈춰야 하는 지점 — 값 객체로 승격할 것인가
`is_valid_seat` 를 보다 보면 자연스럽게 다음 생각이 든다. "좌석 문자열을 여기저기서 파싱하고 있으니 `Seat` 클래스를 만들자."

| | 문자열 그대로 + 검증 함수 | `Seat` 값 객체 (`frozen=True`) |
| --- | --- | --- |
| 코드량 | 검증 함수 하나 | 클래스 + 파싱 + `__str__` + 테스트 |
| 잘못된 좌석의 존재 | 검증을 안 부르면 통과한다 | 만들어질 수 없다 |
| 경계 | 입력·출력이 그냥 문자열 | 경계마다 변환 코드가 붙는다 |
| 이득이 나는 조건 | 좌석에 붙는 규칙이 **검증 하나** | 좌석에 붙는 규칙이 **여럿**(인접, 통로, 등급) |

이 과제에서 좌석에 붙는 규칙은 검증 하나다. **그러면 값 객체는 이름만 늘린다.** 반대로 "통로 좌석은 예약 불가", "같은 행 인접석만 2석 허용" 같은 요구사항이 하나라도 있으면 그때는 값 객체가 이긴다. 지금 없는 요구사항을 위해 만들면 [12.2](#/requirements-to-model)가 말한 YAGNI 위반이고, 과제형에서는 **가점이 아니라 감점**이다.
:::

## 패스 3 — 함수 하나씩, 다섯 가지 질문

여기서 진짜 결함이 나온다. 함수를 하나씩 보되 **질문을 다섯 개로 고정한다.** 고정하지 않으면 "좀 이상한데"에서 끝나고 아무것도 안 고친다.

### ① 이 함수의 이름에 "그리고"가 들어가는가

`process` 는 "예약하고 **그리고** 취소한다"였다. 패스 2에서 이미 잡혔다. 이 질문은 대개 패스 2와 중복으로 잡히는데, **본문을 보면 더 확실하게 잡힌다.** 본문의 `if` 하나가 함수 전체를 두 덩이로 가르고 있으면 그건 두 함수다.

### ② 이 함수가 아직 받아 본 적 없는 입력은 무엇인가

가장 많이 건지는 질문이다. 테스트에 쓴 입력만 머릿속에 남아 있으니, **의도적으로 안 써 본 것을 나열해야** 한다. `is_valid_seat` 이 받는 것은 문자열이다. 테스트에 쓴 것은 `"A1"`, `"Z9"`, `"A99"` 뿐이다. 안 써 본 것은?

```pyrepl
>>> from seatmap import SeatManager
>>> from datetime import date
>>> m = SeatManager(5, 10)
>>> m.process("kim", "A1", date(2025, 3, 1))
True
>>> m.process("lee", "A01", date(2025, 3, 1))
True
>>> m.get()
['A01', 'A1']
```

**한 자리가 두 사람에게 팔렸다.** `"A01"` 과 `"A1"` 은 같은 좌석인데 `check` 가 둘 다 통과시키고, 딕셔너리 키로는 서로 다르다. 요구사항 2가 정면으로 깨진다. 테스트 다섯 개는 전부 통과한 채로.

원인은 `int(s[1:])` 한 줄이다. **검증할 때는 정수로 바꿔서 보고, 저장할 때는 문자열 그대로 쓴다.** 같은 것을 두 가지 표현으로 다루는 순간 이런 균열이 생긴다.

::: danger `isdigit()` 은 당신이 생각하는 것보다 넓다
같은 줄에 함정이 하나 더 있다.

```pyrepl
>>> "1²".isdigit()
True
>>> int("1²")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    int("1²")
ValueError: invalid literal for int() with base 10: '1²'
>>> "１".isdigit()
True
>>> int("１")
1
```

위첨자 `²` 는 `isdigit()` 을 통과하고 `int()` 에서 **예외로 터진다.** 전각 숫자 `１` 은 둘 다 통과해서 `"A１"` 이라는 **또 하나의 유령 좌석**을 만든다. 검증 함수가 `False` 를 반환하는 대신 `ValueError` 를 던지면, 그건 더 이상 검증 함수가 아니다.

고치는 것은 조건 하나다. `number.isascii() and number.isdigit()`. 문자열의 유니코드 동작은 [1.4 문자열과 유니코드](#/strings)에 있다. **여기서 중요한 건 지식이 아니라 절차다** — "이 함수가 받아 본 적 없는 입력"을 묻지 않았으면 셋 다 못 찾는다.
:::

### ③ 이 필드를 누가 읽는가

`self.cnt` 를 찾아보면 **쓰는 곳은 세 군데인데 읽는 곳이 하나도 없다.** 소스에도, 테스트에도, 어디에도 없다.

```python
self.cnt = 0        # 초기화
self.cnt -= 1       # 취소할 때
self.cnt += 1       # 예약할 때
```

죽은 상태다. 게다가 살아 있었더라도 문제였다. `cnt` 는 항상 `len(self.data)` 와 같아야 하는 **파생 상태**이고, 갱신 지점이 두 군데라 언젠가 어긋난다. **파생 상태는 저장하지 말고 계산해라.** 성능 때문에 저장해야 할 정도의 규모라면 그때는 요구사항에 그렇게 적혀 있을 것이다.

읽는 곳이 없는 필드, 호출하는 곳이 없는 메서드, 쓰지 않는 인자는 전부 같은 신호를 준다 — **만들다 만 것이 남아 있다.** 지워라. 지우면 테스트가 알려 준다.

### ④ 출력이 사람이 기대하는 모양인가

```pyrepl
>>> from seatmap import SeatManager
>>> from datetime import date
>>> m = SeatManager(5, 12)
>>> for user, seat in [("kim", "A2"), ("lee", "A10"), ("park", "A1")]:
...     m.process(user, seat, date(2025, 3, 1))
...
True
True
True
>>> m.get()
['A1', 'A10', 'A2']
```

`sorted()` 를 썼으니 정렬은 됐다. **문자열 정렬이라 `A10` 이 `A2` 앞에 온다.** 요구사항 어디에도 "번호 순으로 정렬하라"는 문장이 없으니 이건 오답이 아니다. 그러나 평가자가 이 출력을 보면 **"12석 이상인 방을 한 번도 안 돌려 봤구나"** 로 읽는다. 요구사항 위반보다 이쪽이 더 아프다. 테스트가 `cols=10` 으로만 돌았다는 사실까지 같이 드러나기 때문이다.

고치는 것은 `key` 하나다([11.6](#/sorting-as-tool)).

```python
def _seat_order(seat: str) -> tuple[str, int]:
    """정렬용 키. 문자열 정렬은 A10 을 A2 보다 앞에 놓는다."""
    return seat[0], int(seat[1:])
```

### ⑤ 이 리터럴은 왜 이 값인가

```python
if len([1 for u, _ in self.data.values() if u == user]) >= 2:
```

`2` 가 요구사항 3의 "최대 2석"이라는 것을 아는 사람은 지금 이 코드를 쓴 사람뿐이다. 상수로 올리면 **요구사항 번호가 코드에 박힌다.**

```python
MAX_SEATS_PER_USER = 2
```

이름을 붙이는 것이 목적이지 설정 가능하게 만드는 것이 목적이 아니다. **생성자 인자로 빼서 주입하지 마라.** 요구사항에 "정원은 설정 가능해야 한다"가 없으면 그건 확장점을 미리 뚫는 것이고, [12.1](#/takehome-eval)이 감점 항목으로 지목한 그것이다.

::: perf 그 다음 줄에 대한 지적은 하지 마라 — n을 먼저 봐라
같은 줄을 보고 "리스트를 만들 필요가 없으니 `sum(1 for ...)` 로 바꿔라"라고 말하고 싶어진다. 실제로 재 봤다.

| n(전체 예약 수) | `len([1 for ...])` | `sum(1 for ...)` |
| --- | --- | --- |
| 60 | 1.79 ~ 1.82 µs | 1.99 ~ 2.00 µs |
| 100,000 | 3.12 ~ 3.24 ms | 3.10 ~ 3.35 ms |

(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

**작은 n에서는 리스트 쪽이 오히려 빠르고, 큰 n에서는 차이가 측정 잡음에 묻힌다.** 제너레이터는 프레임을 만들고 재개하는 비용이 있어서, 원소가 적으면 리스트 컴프리헨션을 이기지 못한다. 즉 **`sum` 으로 바꿀 이유는 속도가 아니다.** "개수만 필요하다"는 의도가 코드에 드러난다는 것뿐이고, 그건 그것대로 충분한 이유다. 다만 **리뷰에서 그것을 성능 문제로 말하면 틀린 말이 된다.**

그리고 이 과제의 실제 규모는 `rows × cols` = 60석이다. 60석을 전부 예약하는 전체 시나리오가 **0.161 ~ 0.169 ms** 다. 여기서 성능을 논하는 것 자체가 시간 낭비다. **자기 리뷰에서 성능 항목은 맨 마지막이고, 대개 "해당 없음"이 정답이다.**
:::

## 주석 — 코드가 못 하는 말만 남긴다

패스 3에서 주석도 같이 본다. 주석은 세 종류이고, 처리 방법이 각각 다르다.

```python
# ① 번역 주석 — 코드를 한국어로 옮겨 적었다. 지운다.
def check(self, s):
    # 좌석 문자열이 올바른지 확인한다
    ...

# ② 보상 주석 — 이름이 나빠서 주석으로 때웠다. 주석이 아니라 이름을 고친다.
self.data = {}          # 좌석 -> (사용자, 날짜)

# ③ 근거 주석 — 코드가 절대 말할 수 없는 것을 말한다. 남긴다.
if number != str(int(number)):
    # 'A01' 을 거부한다. 허용하면 'A1' 과 다른 키가 되어 같은 좌석이 두 번 팔린다.
```

②가 특히 중요하다. `self.data = {}  # 좌석 -> (사용자, 날짜)` 는 주석이 성실해 보이지만, **주석이 필요했다는 사실 자체가 이름과 타입이 부족하다는 증거**다. 고치면 주석이 사라진다.

```python
self._reservations: dict[str, Reservation] = {}
```

**주석을 지우려고 이름을 고쳐라.** 반대로 하지 마라.

::: warn 코드를 고칠 때 주석을 안 고치면 주석이 거짓말이 된다
거짓말하는 주석은 없는 주석보다 훨씬 나쁘다. 평가자는 주석을 읽고 코드를 믿는데, 둘이 다르면 **어느 쪽이 의도인지 알 수 없어져서** 그 파일 전체를 못 믿게 된다.

자기 리뷰에서 가장 확실한 검사는 이것이다. **주석이 붙은 줄을 고쳤으면 그 주석을 소리 내어 읽어라.** 특히 숫자가 들어간 주석(`# 30분 단위로 올림`), 예시가 들어간 주석(`# 예: A1`), 그리고 `# TODO` 를 조심해라. `# TODO` 는 세 시간 전의 계획이지 지금의 계획이 아니다. 이미 한 일이면 지우고, 안 할 일이면 README의 "알려진 한계"로 옮겨라([12.8](#/readme-submit)).
:::

## 패스 4 — 테스트를 명세로 읽는다

무엇을 테스트할지는 [12.6](#/test-strategy)에서 다뤘다. 여기서는 **이미 쓴 테스트를 마지막에 어떻게 검사하는가**만 본다. 방법은 하나다. **본문을 보지 말고 이름만 이어서 읽어라.**

```bash
$ pytest -q --collect-only
tests/test_seatmap.py::test_1
tests/test_seatmap.py::test_2
tests/test_seatmap.py::test_3
tests/test_seatmap.py::test_4
tests/test_seatmap.py::test_5

5 tests collected in 0.01s
```

이 다섯 줄에서 복원되는 요구사항은 **없다.** 테스트가 다섯 개 있다는 사실만 알 수 있고, 그건 평가자가 이미 아는 것이다. 이름을 고치고 나면 같은 명령이 이렇게 나온다.

```bash
$ pytest -q --collect-only
tests/test_seatmap.py::test_예약하면_전체_목록에_나온다
tests/test_seatmap.py::test_이미_예약된_좌석은_다른_사람이_못_잡는다
tests/test_seatmap.py::test_한_사람은_최대_2석까지만_잡는다
tests/test_seatmap.py::test_취소하면_그_자리를_다시_잡을_수_있다
tests/test_seatmap.py::test_남의_예약은_취소하지_못한다
tests/test_seatmap.py::test_빈_좌석_취소는_실패한다
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[A0]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[A13]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[F1]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[1A]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[A]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[]
tests/test_seatmap.py::test_범위를_벗어난_좌석은_예약되지_않는다[A 1]
tests/test_seatmap.py::test_같은_좌석의_다른_표기는_거부한다[A01]
tests/test_seatmap.py::test_같은_좌석의_다른_표기는_거부한다[A\uff11]
tests/test_seatmap.py::test_같은_좌석의_다른_표기는_거부한다[A1\xb2]
tests/test_seatmap.py::test_좌석_목록은_번호_순서로_나온다

17 tests collected in 0.01s
```

**요구사항 다섯 개가 이 목록에서 전부 복원된다.** 그리고 요구사항에 없던 것 두 개(표기 정규화, 정렬 순서)가 추가로 보인다. 이 출력은 그대로 README에 붙일 수 있다 — 테스트 목록이 명세 목록이 되면, 평가자는 "이 사람은 요구사항을 항목으로 관리했다"고 읽는다.

::: tip 새로 찾은 버그는 코드보다 테스트를 먼저 쓴다
패스 3에서 `A01` 버그를 찾았다. 바로 고치고 싶겠지만 **먼저 실패하는 테스트를 쓴다.**

```bash
$ pytest -q
.....F                                                                   [100%]
=================================== FAILURES ===================================
___________________________ test_같은_좌석의_다른_표기는_거부한다 ____________________________

    def test_같은_좌석의_다른_표기는_거부한다():
        m = SeatManager(5, 10)
        m.process("kim", "A1", D)

>       assert m.process("lee", "A01", D) is False
E       AssertionError: assert True is False
E        +  where True = process('lee', 'A01', datetime.date(2025, 3, 1))
E        +    where process = <seatmap.SeatManager object at 0x7fdf8de69a30>.process

tests/test_seatmap.py:44: AssertionError
=========================== short test summary info ============================
FAILED tests/test_seatmap.py::test_같은_좌석의_다른_표기는_거부한다 - Asserti...
1 failed, 5 passed in 0.03s
```

`E +  where` 두 줄은 pytest의 단언 재작성이 붙여 주는 것이다. **단언식을 조각내서 각 조각이 실제로 무엇이었는지 되짚어 준다** — 여기서는 `True` 가 어디서 나왔는지가 인자까지 그대로 찍힌다(객체 주소는 실행할 때마다 다르다). 이 두 줄이 있어서 `print` 를 넣어 볼 필요가 없다.

이유는 둘이다. 첫째, **버그를 정확히 이해했는지 확인된다.** 실패하는 테스트를 못 쓰면 아직 원인을 모르는 것이다. 둘째, 남은 시간이 부족해서 못 고치더라도 **`@pytest.mark.xfail` 을 붙여 두면 "알고 있다"는 증거가 남는다.** 조용히 통과하는 제출물과 "여기가 깨진다는 걸 안다"고 말하는 제출물은 완전히 다르게 평가된다([12.1](#/takehome-eval)).
:::

## 고친 결과

네 패스에서 나온 것을 반영한 최종본이다. **새 기능은 하나도 없다.** 요구사항은 그대로 다섯 개다.

```python title="seatmap.py — 리뷰 후"
from dataclasses import dataclass
from datetime import date

MAX_SEATS_PER_USER = 2


@dataclass(frozen=True)
class Reservation:
    user: str
    day: date


def _seat_order(seat: str) -> tuple[str, int]:
    """정렬용 키. 문자열 정렬은 A10 을 A2 보다 앞에 놓는다."""
    return seat[0], int(seat[1:])


class SeatMap:
    """행 문자(A~) + 열 번호(1~cols)로 식별되는 좌석의 예약 상태."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self._reservations: dict[str, Reservation] = {}

    def is_valid_seat(self, seat: str) -> bool:
        row, number = seat[:1], seat[1:]
        if not ("A" <= row < chr(ord("A") + self.rows)):
            return False
        # isdigit() 만으로는 전각 숫자와 위첨자가 통과한다. isascii() 가 그걸 막는다.
        if not (number.isascii() and number.isdigit()):
            return False
        # 'A01' 을 거부한다. 허용하면 'A1' 과 다른 키가 되어 같은 좌석이 두 번 팔린다.
        if number != str(int(number)):
            return False
        return 1 <= int(number) <= self.cols

    def reserve(self, user: str, seat: str, day: date) -> bool:
        if not self.is_valid_seat(seat):
            return False
        if seat in self._reservations:
            return False
        if len(self.seats_of(user)) >= MAX_SEATS_PER_USER:
            return False
        self._reservations[seat] = Reservation(user, day)
        return True

    def cancel(self, user: str, seat: str) -> bool:
        held = self._reservations.get(seat)
        if held is None or held.user != user:
            return False
        del self._reservations[seat]
        return True

    def reserved_seats(self) -> list[str]:
        return sorted(self._reservations, key=_seat_order)

    def seats_of(self, user: str) -> list[str]:
        seats = [s for s, r in self._reservations.items() if r.user == user]
        return sorted(seats, key=_seat_order)
```

```bash
$ python tools/surface.py seatmap.py
# seatmap.py
class Reservation
class SeatMap
    .is_valid_seat(seat)
    .reserve(user, seat, day)
    .cancel(user, seat)
    .reserved_seats()
    .seats_of(user)

$ ruff check .
All checks passed!

$ pytest -q
.................                                                        [100%]
17 passed in 0.03s
```

이제 **이름 목록만 읽어도 무슨 모듈인지 안다.** 43줄이 60줄이 됐는데, 늘어난 17줄은 상수 하나, `Reservation` 데이터클래스([2.6](#/dataclasses)), 정렬 키 함수, 근거 주석 두 줄, 타입 힌트다. **전부 읽는 사람을 위한 줄이고, 그게 이 파트가 채점되는 항목이다.**

::: note `reserve` 안에서 `seats_of` 를 부르는 것은 의도된 타협이다
`len(self.seats_of(user))` 는 개수만 필요한데 리스트를 만들고 **정렬까지 한다.** 그냥 세는 것보다 확실히 낭비다. 그런데도 이렇게 둔 이유는 **"이 사람의 좌석"이라는 개념의 정의가 한 군데에만 있게 하려고**다. 나중에 "취소된 좌석은 제외" 같은 규칙이 붙으면 고칠 곳이 하나다.

이 타협의 값은 이미 위에서 쟀다. 60석짜리 방 전체를 예약하는 데 0.161 ~ 0.169 ms. **낭비의 절대량이 이 정도면 개념의 단일성이 이긴다.** 규모가 달랐다면 반대로 판단했을 것이고, 그 판단의 근거는 취향이 아니라 숫자다.
:::

## 고치지 말아야 할 것 — 남은 시간의 계산

리뷰를 하면 항상 발견이 고칠 시간보다 많다. **여기서 판단이 갈린다.**

패스 3에서 하나 더 나온 것이 있다. `reserve` 와 `cancel` 이 실패를 전부 `False` 로 뭉갠다. 좌석 형식이 틀린 것, 이미 팔린 것, 2석 초과인 것이 호출자에게 구별되지 않는다. [12.5](#/error-design)의 기준으로는 **도메인 예외로 바꾸는 것이 맞다.**

```python title="안 B — 예외로 바꾼 버전(발췌)"
class SeatError(Exception):
    """이 모듈이 정의하는 모든 실패의 뿌리."""


class InvalidSeat(SeatError):
    pass


class SeatTaken(SeatError):
    pass


class SeatLimitExceeded(SeatError):
    pass


class NotYourReservation(SeatError):
    pass


    def reserve(self, user: str, seat: str, day: date) -> None:
        if not self.is_valid_seat(seat):
            raise InvalidSeat(seat)
        if seat in self._reservations:
            raise SeatTaken(seat)
        if len(self.seats_of(user)) >= MAX_SEATS_PER_USER:
            raise SeatLimitExceeded(user)
        self._reservations[seat] = Reservation(user, day)
```

더 나은 설계다. 그런데 **지금 할 일인지는 별개의 질문**이다. 실제로 두 버전을 다 만들어서 변경량을 재 봤다.

| | 안 A — 이름·분리·버그 수정 | 안 B — 예외 도입 |
| --- | --- | --- |
| 모듈 변경 | 이름 치환 + 조건 3줄 | 24줄 |
| 테스트 변경 | 이름만, 단언은 그대로 | 9개 중 **8개**, +26 / −13줄 |
| 테스트가 지켜 주는가 | 그렇다. 단언이 그대로라 회귀가 잡힌다 | **아니다.** 테스트를 같이 고치므로 둘 다 틀릴 수 있다 |
| 중간에 시간이 끊기면 | 남은 이름만 안 바뀐 상태 = 동작함 | **절반은 예외, 절반은 불리언 = 최악** |
| 되돌리기 | 쉽다 | 어렵다 |

**남은 시간이 30분이면 안 A만 한다.** 안 B는 되돌릴 수 없는 변경이고, 테스트를 같이 고쳐야 하므로 안전망이 사라지는 유일한 종류의 리팩터링이다. 남은 시간이 두 시간이고 테스트가 통과 중이면 그때는 해도 된다.

::: danger 마지막 30분에 절대 하면 안 되는 세 가지
1. **테스트가 없는 곳을 고치는 것.** 리뷰에서 "여긴 좀 이상한데"를 발견했는데 그 경로를 덮는 테스트가 없다면, 지금 할 일은 고치는 게 아니라 **테스트를 쓰는 것**이다. 시간이 없으면 README에 한 줄 적고 그대로 낸다.
2. **테스트와 구현을 같은 커밋에서 함께 고치는 것.** 둘 다 바꾸면 무엇이 무엇을 검증하는지 아무도 모른다. 순서는 항상 **테스트 먼저 통과 확인 → 구현 변경 → 다시 통과 확인**이다.
3. **되돌릴 수 없는 상태로 제출 시각을 맞는 것.** 커밋을 안 하고 리팩터링을 시작하지 마라. 리뷰를 시작하기 전에 **동작하는 상태를 반드시 커밋해 두는 것**이 이 절 전체에서 가장 값싼 보험이다.
:::

::: tip 남은 시간별로 무엇을 하는가
| 남은 시간 | 한다 | 안 한다 |
| --- | --- | --- |
| 2시간 | 패스 1~4 전부. 안 B 같은 구조 변경도 가능 | 새 기능 |
| 1시간 | 패스 1~4 + 안 A 수준의 수정 | 구조 변경, 새 추상화 |
| 30분 | 패스 1·2·4 + 이름 고치기 + README | 함수 본문 수정 |
| 10분 | 패스 1(실행 확인) + README의 "알려진 한계" | 코드를 여는 것 자체 |

**10분 남았을 때 코드를 여는 것이 가장 위험하다.** 그 시간에 할 수 있는 가장 가치 있는 일은 clean 복제본에서 한 번 더 실행해 보는 것과, 못 고친 것을 정직하게 적는 것이다.
:::

못 고친 것은 반드시 적는다. 이런 세 줄이 남는다([12.8](#/readme-submit)의 "알려진 한계").

```markdown
- 실패를 모두 `False` 로 반환한다. 좌석 형식 오류·중복 예약·한도 초과가 호출자에게
  구별되지 않는다. `SeatError` 하위 예외로 바꾸는 것이 맞다고 보지만, 남은 시간에
  테스트 8개를 함께 고치는 변경은 안전하지 않다고 판단해 남겨 뒀다.
```

**이 세 줄은 안 B를 절반만 하다 만 코드보다 높게 평가된다.** 문제를 알아봤고, 대안을 알고 있고, 왜 지금 안 했는지를 설명할 수 있다는 것이 전부 드러나기 때문이다.

## 흔한 감점 요인 — 리뷰에서 실제로 나오는 것들

위 예제에서 나온 것 외에, 자기 리뷰에서 자주 걸리는 항목이다. 대부분 **1분 안에 고칠 수 있고, 안 고치면 확실히 눈에 띈다.**

| 항목 | 어떻게 찾는가 | 왜 감점인가 |
| --- | --- | --- |
| 디버깅용 `print` 잔여물 | `grep -rn "print(" src/` | 제출 전에 안 읽어 봤다는 증거 |
| 주석 처리된 코드 덩어리 | 기본 설정의 린터는 못 잡는다. `ruff check --select ERA` ([0.4](#/tooling)) | git이 있는데 왜 남겼는지 설명이 안 된다 |
| 쓰지 않는 import·변수 | `ruff check .` | 첫 줄부터 보인다 |
| `__pycache__`, `.venv`, `.idea` 커밋 | `git status`, 트리 훑기 | `.gitignore` 를 안 썼다 |
| 커밋 안 된 파일 | `git status` | **제출물에 아예 없는 파일이 생긴다** |
| 요구사항 하나가 조용히 빠짐 | 요구사항 ↔ 테스트 이름 대조(패스 4) | 문제를 안 읽은 사람이 된다 |
| README와 실제 명령 불일치 | clean 복제본에서 복사·붙여넣기 | 실행이 안 되면 나머지는 안 읽힌다 |
| 죽은 필드·메서드 | 패스 3의 질문 ③ | 만들다 만 것이 남아 있다 |
| 클래스 하나에 파일 하나씩 쪼갠 트리 | 트리를 그려 본다 | 과제 규모에 안 맞는다([12.7](#/project-structure)) |

표의 두 번째 항목에 한 마디 더 붙인다. 주석 처리된 코드를 못 잡는 것은 린터의 한계가 아니라 **기본 규칙 집합의 선택**이다. ruff의 기본값은 `E4,E7,E9,F` 이고 거기에 `ERA001` 이 안 들어 있을 뿐이다.

```bash
$ ruff check commented.py
All checks passed!

$ ruff check --select ERA commented.py
ERA001 Found commented-out code
 --> commented.py:2:1
  |
1 | x = 1
2 | # y = 2
  | ^^^^^^^
  |
help: Remove commented-out code

Found 1 error.
```

`ERA001` 은 기본에서 빠져 있는 이유가 있다 — **주석과 코드를 구별하는 휴리스틱이라 오탐이 난다.** 그래서 자동 수정도 안 붙는다(`[*]` 표시가 없다). 그래도 제출 직전에 `--select ERA` 로 한 번 훑는 것은 값이 있다. 오탐이 몇 개 나와도 눈으로 거르면 되고, **진짜 잔여물을 놓치는 것보다 낫다.**

::: warn 리뷰에서 나온 지적을 전부 반영하지 마라
자기 리뷰를 처음 해 보면 발견이 스무 개쯤 나온다. 전부 고치려 들면 **제출 직전에 동작하지 않는 코드가 남는다.** 실제로 이게 마지막 한 시간에 제출물이 망가지는 가장 흔한 경로다.

우선순위는 언제나 이 순서다.

1. **틀린 동작** (요구사항 위반, 조용히 나오는 오답)
2. **읽는 사람이 멈추는 것** (이름, 플래그 인자, 거짓 주석)
3. **지저분한 것** (죽은 코드, import, 잔여물)
4. 나머지는 README로 보낸다

3번까지 못 가면 그냥 안 하는 것이지, 급하게 반쯤 하는 것이 아니다. **일관되게 나쁜 코드가 절반만 고쳐진 코드보다 읽기 쉽다.**
:::

::: cote 알고리즘 코딩테스트에서 이 절이 남기는 것
채점이 자동인 시험에서는 이 절의 대부분이 필요 없다. 이름이 `dp` 든 `memo` 든 아무도 안 본다. 그러나 **딱 두 가지는 그대로 살아남는다.**

**하나, "이 함수가 받아 본 적 없는 입력은 무엇인가."** 패스 3의 질문 ②는 시험장에서 그대로 엣지케이스 점검이 된다. 빈 입력, 원소 하나, 전부 같은 값, 최댓값. `A01` 버그를 찾아낸 것과 정확히 같은 종류의 질문이다([11.14](#/exam-debug)).

**둘, 제출 전에 예제를 다시 한 번 돌리는 것.** 고치고 나서 안 돌려 보고 내는 것이 두 시험 모두에서 가장 아까운 실점이다.
:::

## 15분 자기 리뷰 체크리스트

시간이 정말 없을 때 이 순서로만 훑어도 대부분이 걸린다.

```text nolines
  run     clean 복제본에서 README 명령을 복사해서 실행         -> 되는가
  lint    ruff check .                                         -> 0건인가
  test    pytest -q --collect-only                             -> 이름만 읽어 요구사항이 복원되는가
  names   surface.py 로 공개 이름만 출력                       -> 무슨 모듈인지 알 수 있는가
  flags   불리언 인자를 받는 함수가 있는가                     -> 있으면 쪼갠다
  dead    읽는 곳이 없는 필드/메서드/인자가 있는가             -> 지운다
  input   각 검증 함수가 받아 본 적 없는 입력을 세 개 대 본다  -> 돌려 본다
  numbers 코드에 박힌 숫자마다 이름이 있는가                   -> 상수로 올린다
  doc     주석과 README가 지금 코드와 일치하는가               -> 아니면 코드가 아니라 문서를 고친다
  git     git status 가 깨끗한가                               -> 커밋 안 된 파일이 없어야 한다
```

## 요약

- 자기 코드는 안 읽힌다. **읽는 게 아니라 기억을 재생하기 때문이다.** 리뷰는 의지가 아니라 **낯설게 만드는 절차**로 한다.
- 패스를 나눠라. **밖에서 안으로** — 실행·린터 → 이름만 → 함수 본문 → 테스트 이름. 한 패스에 한 가지만 본다.
- **공개 이름만 뽑아 읽는 것**이 가장 값싸고 잔인한 검사다. `check(s)` / `process(user, s, d, cancel)` / `get(user)` 네 줄로 무슨 모듈인지 알 수 없으면 이름이 실패한 것이다.
- 함수마다 다섯 가지만 묻는다. **이름에 "그리고"가 있는가 / 받아 본 적 없는 입력은 무엇인가 / 이 필드를 누가 읽는가 / 출력이 기대한 모양인가 / 이 숫자는 왜 이 값인가.** `A01` 이중 예약은 두 번째 질문에서만 나온다.
- 주석은 세 종류다. **번역 주석은 지우고, 보상 주석은 이름을 고쳐 없애고, 근거 주석만 남긴다.** 코드를 고쳤으면 주석을 소리 내어 읽어라.
- **발견을 전부 고치지 마라.** 되돌릴 수 없고 테스트를 함께 고쳐야 하는 변경(예외 도입 등)은 남은 시간이 30분이면 하지 않는다. 대신 **왜 안 했는지를 README에 적는다.** 그 세 줄이 절반만 한 리팩터링보다 높게 평가된다.
- 리뷰를 시작하기 전에 **동작하는 상태를 커밋해라.** 이 절 전체에서 가장 값싼 보험이다.

::: quiz 과제 — 읽지 말고 당신 코드에 돌려라
**1. 이름만으로 설명되는가 (10분)**
이 절의 `surface.py` 를 당신이 최근에 쓴 파이썬 파일에 돌려라. 출력만 다른 사람에게 보여 주고 **무슨 프로그램인지 맞히게** 해라. 못 맞히면 이름 세 개를 고치고 다시 돌려라. 본문은 한 줄도 고치지 마라.

**2. 패스 3을 이 코드에 적용하라 (25분)**
주차 정산 모듈이다. 요구사항은 이렇다. ① 입차 시각과 출차 시각(분 단위 정수)을 받는다. ② 주차 시간은 30분 단위로 올려서 과금한다(1~30분 = 1단위, 31~60분 = 2단위). ③ 0분은 0원이다. ④ 입차 기록이 없는 차의 출차는 오류다. ⑤ 현재 주차 중인 차량 목록을 조회할 수 있다.

```python title="parking.py — 리뷰 대상"
class Parking:
    def __init__(self, rate):
        self.rate = rate
        self.log = {}
        self.total = 0

    def do(self, car, t, out=False):
        if out:
            if car not in self.log:
                return -1
            m = t - self.log[car]
            del self.log[car]
            f = self.rate * (m // 30 + 1)
            self.total += f
            return f
        self.log[car] = t
        return 0

    def get(self):
        return list(self.log.keys())
```

패스 3의 다섯 가지 질문을 순서대로 던져서 **결함을 네 개 이상** 찾아라. 각각에 대해 (a) 어느 질문에서 걸렸는지, (b) 요구사항 위반인지 읽기 문제인지, (c) 실패하는 테스트를 먼저 쓴 뒤 고쳐라. 최소한 다음은 나와야 한다 — **정확히 30분을 주차한 차의 요금**과 **0분 주차의 요금**을 손으로 계산한 값과 코드가 내놓는 값을 비교해 봐라.

**3. 이름만 읽어 요구사항을 복원하라 (10분)**
2번에서 고친 코드의 테스트를 `pytest -q --collect-only` 로 출력해라. 그 목록만 옆 사람에게 주고 **위 요구사항 다섯 개를 복원**하게 해라. 복원되지 않는 요구사항이 있으면 테스트 이름을 고치거나 빠진 테스트를 추가해라.

**4. 고칠 것과 적을 것을 나눠라 (10분)**
2번의 리뷰에서 이런 발견이 나왔다고 하자.

- (가) 30분 경계에서 요금이 한 단위 더 나온다.
- (나) `do(car, t, out=True)` 의 플래그 인자.
- (다) 실패를 `-1` 로 표현한다. 요금 −1원과 구별되지 않는다.
- (라) `self.total` 이 파생 상태다.
- (마) 요금 계산을 `Fee` 전략 클래스로 빼면 요금 정책을 갈아 끼울 수 있다.

**남은 시간이 25분**이라고 가정하고 다섯 개를 각각 (1) 지금 고친다 (2) README의 "알려진 한계"에 적는다 (3) 아무것도 하지 않는다 로 분류해라. **각각에 대해 한 문장으로 근거를 써라.** 이 문제에 정답은 하나가 아니지만, (마)를 "지금 고친다"로 분류했다면 [12.1](#/takehome-eval)과 [12.2](#/requirements-to-model)를 다시 읽어라.

**5. 실제 값을 재라 (15분)**
2번에서 고친 코드에 대해 `ruff check .` 과 `pytest -q` 를 각각 일곱 번 실행하고 소요 시간을 재라. 한 바퀴가 몇 초인가? 그 숫자를 보고 **"이름 하나 바꿀 때마다 돌리는 것"이 당신의 프로젝트에서 현실적인지** 판단해라. 1초를 넘어가면 왜 그런지 찾아라 — 대개 테스트가 파일이나 네트워크를 만지고 있고, 그건 [12.4](#/boundaries-di)의 문제다.
:::

---

여기서 이 책을 마친다.

[1.1](#/objects-names)에서 "변수는 상자가 아니라 이름표"라는 한 문장으로 시작했다. 그 이름표는 5부에서 메모리 측정의 근거가 됐고, [10.16](#/ros-next) 끝에서는 다른 언어의 `shared_ptr` 로 다시 나타났다. 방금 이 절에서는 **"이 필드를 누가 읽는가"** 라는 질문으로 한 번 더 나왔다 — 이름과 그 이름이 가리키는 것을 분리해서 볼 줄 아는 능력이, 결국 자기 코드를 남의 눈으로 읽는 능력이었다.

이 책이 실제로 가르치려 한 것은 문법이 아니었다. 파이썬은 문법이 작은 언어라서, 문법만 필요했다면 이 책은 지금의 십분의 일이면 됐다. 대신 세 가지를 반복했다.

**첫째, 한 층 아래를 본다.** `dict` 가 빠르다에서 멈추지 않고 해시 충돌이 어떻게 처리되는지까지 갔다. 그 습관은 라이브러리를 고를 때, 병목을 찾을 때, 남이 쓴 코드를 읽을 때 전부 같은 방식으로 쓰인다.

**둘째, 추정하지 않고 잰다.** 이 책에 나온 모든 수치는 실제로 돌려서 나온 것이고, 그중 여러 개는 처음 예상과 반대였다. 방금 이 절에서도 `sum` 이 리스트 컴프리헨션보다 느렸다. **"~일 것 같다"를 믿지 않는 습관**이 5부와 7부와 11부를 관통한 유일한 원칙이다.

**셋째, 읽는 사람을 생각한다.** 11부는 빈 화면 앞에서 손이 움직이게 만드는 훈련이었고, 12부는 그렇게 짠 코드를 남이 읽을 수 있게 만드는 훈련이었다. 시험은 끝나지만 두 번째 능력은 끝나지 않는다. 실무에서 당신이 쓴 코드는 당신이 여덟 번 더 읽고 다른 사람이 그보다 더 많이 읽는다.

이 책은 처음부터 끝까지 한 번 읽고 덮는 책이 아니다. 코드를 짜다가 막히는 지점이 생기면 그 지점의 절로 돌아와라. 두 번째로 읽을 때 보이는 것이 첫 번째와 다르다 — 그때는 당신이 그 문제를 실제로 겪어 봤기 때문이다.

**책의 끝**: [0.1 이 책을 읽는 법](#/how-to-read) — 이제 학습 경로를 다시 펴고, 당신이 실제로 쓸 파트부터 두 번째로 읽어라.
