# 6.2 fixture, 파라미터화, mocking

::: lead
[6.1 pytest](#/pytest)에서 `assert` 하나로 시작하는 테스트를 봤다. 실전 테스트는 그렇게 단순하지 않다. DB 연결을 흉내 내야 하고, 환경변수에 따라 동작이 갈리고, 같은 로직을 다른 입력 100개로 돌려야 한다. 이걸 전부 `if`와 반복문으로 손으로 짜면 테스트 코드가 본체 코드보다 커진다. pytest의 fixture와 `unittest.mock`은 이 문제를 구조적으로 푼다. 다만 도구가 강력할수록 잘못 쓰기도 쉽다 — 이 절 후반부는 그 함정을 다룬다.
:::

## setUp/tearDown이 아니라 함수 인자로

`unittest` 스타일에 익숙하다면 이런 코드를 봤을 것이다.

```python title="xUnit 스타일 — pytest에서는 안 쓴다"
import unittest


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_connection()

    def tearDown(self):
        self.conn.close()

    def test_insert(self):
        self.conn.insert({"id": 1})
        assert self.conn.count() == 1
```

문제는 `self.conn`이 **암묵적**이라는 것이다. 테스트 본문만 보면 `conn`이 어디서 왔는지 알 수 없다. 클래스 전체를 훑어야 한다. 그리고 테스트마다 다른 조합의 자원이 필요하면(어떤 테스트는 DB만, 어떤 테스트는 DB+캐시) `setUp`이 점점 비대해진다.

pytest는 이걸 **함수 시그니처에 선언**하는 방식으로 바꾼다.

```python title="test_db.py"
import pytest


@pytest.fixture
def conn():
    connection = create_test_connection()
    yield connection
    connection.close()


def test_insert(conn):          # 필요한 것을 인자로 요청한다
    conn.insert({"id": 1})
    assert conn.count() == 1


def test_empty_by_default(conn):
    assert conn.count() == 0
```

`test_insert(conn)`을 읽는 순간 이 테스트가 DB 연결을 쓴다는 걸 안다. pytest는 매개변수 이름이 `conn`인 걸 보고 **같은 이름의 fixture 함수를 찾아 실행한 뒤 반환값을 넣어준다.** 이게 fixture의 전부다 — 값을 만들어 주는 함수를, 이름으로 주입받는 것.

::: note 의존성 주입이라는 이름
이 패턴에 익숙한 이름이 있다면 **의존성 주입**(dependency injection)이다. 테스트가 자기 의존성을 스스로 만들지 않고, 외부(pytest)가 만들어서 넣어준다. 그래서 실제 DB 대신 테스트용 가짜 DB를 넣는 게 자연스러워진다 — 테스트 코드를 고칠 필요 없이 fixture 함수만 바꾸면 된다.
:::

## 스코프: 언제 다시 만들고 언제 재사용하는가

fixture는 매 테스트마다 새로 실행되는 게 기본이다. 하지만 비싼 자원(DB 스키마 생성, 대용량 파일 로드)을 테스트마다 새로 만들면 느리다. `scope` 인자로 **얼마나 오래 재사용할지**를 정한다.

| scope | 새로 만드는 시점 |
| --- | --- |
| `function` (기본값) | 테스트 함수마다 |
| `class` | 클래스당 한 번 |
| `module` | 파일당 한 번 |
| `session` | 전체 테스트 실행에 딱 한 번 |

말로만 하면 안 믿길 테니 실제로 확인한다. 네 가지 스코프의 fixture를 각각 만들고 카운터를 증가시키게 한 뒤, 클래스 두 개(`TestA`, `TestB`)에서 각각 테스트 두 개씩 돌린다.

```python title="test_scope.py"
import pytest

counters = {"function": 0, "class": 0, "module": 0, "session": 0}


@pytest.fixture(scope="function")
def f_fixture():
    counters["function"] += 1
    print(f"\n[function fixture 생성] 누적 {counters['function']}회")
    yield


@pytest.fixture(scope="class")
def c_fixture():
    counters["class"] += 1
    print(f"\n[class fixture 생성] 누적 {counters['class']}회")
    yield


@pytest.fixture(scope="module")
def m_fixture():
    counters["module"] += 1
    print(f"\n[module fixture 생성] 누적 {counters['module']}회")
    yield


@pytest.fixture(scope="session")
def s_fixture():
    counters["session"] += 1
    print(f"\n[session fixture 생성] 누적 {counters['session']}회")
    yield


class TestA:
    def test_a1(self, f_fixture, c_fixture, m_fixture, s_fixture): pass
    def test_a2(self, f_fixture, c_fixture, m_fixture, s_fixture): pass


class TestB:
    def test_b1(self, f_fixture, c_fixture, m_fixture, s_fixture): pass
    def test_b2(self, f_fixture, c_fixture, m_fixture, s_fixture): pass
```

실제로 돌린 결과다 (`pytest -v -s`, Python 3.14.5 / pytest 9.1.1 / Windows 실측).

```text nolines
test_scope.py::TestA::test_a1
[session fixture 생성] 누적 1회
[module fixture 생성] 누적 1회
[class fixture 생성] 누적 1회
[function fixture 생성] 누적 1회
PASSED
test_scope.py::TestA::test_a2
[function fixture 생성] 누적 2회
PASSED
test_scope.py::TestB::test_b1
[class fixture 생성] 누적 2회
[function fixture 생성] 누적 3회
PASSED
test_scope.py::TestB::test_b2
[function fixture 생성] 누적 4회
PASSED

4 passed in 0.03s
```

숫자를 읽으면 규칙이 그대로 보인다. `function`은 매번(4회), `class`는 클래스가 바뀔 때만(2회, `TestA`에서 1번·`TestB`에서 1번), `module`과 `session`은 전체를 통틀어 딱 1회다. `test_a2`에서는 `function` 것만 다시 생성되고 나머지는 첫 실행 때 만든 걸 그대로 재사용한다.

::: tip 스코프 선택 기준
- **비싼데 상태가 없는 것**(설정 로드, 컴파일된 정규식) → `session`이나 `module`
- **테스트마다 깨끗해야 하는 것**(DB 트랜잭션, 임시 리스트) → `function`
- 애매하면 `function`으로 시작해라. **격리가 깨져서 생기는 버그가 속도보다 훨씬 비싸다.** 어떤 테스트가 session fixture의 상태를 몰래 바꿔놓으면, 그 뒤에 도는 무관한 테스트가 실행 순서에 따라 실패하거나 통과한다 — 디버깅이 지옥이다.
:::

::: warn 가변 상태를 넓은 스코프에 두면
`session`/`module` fixture가 리스트나 딕셔너리 같은 **가변 객체**를 반환하면, 한 테스트가 거기에 `append`하면 다른 모든 테스트가 그 변경을 본다. [1.1 객체, 이름, 참조](#/objects-names)에서 다룬 별칭 문제가 테스트 사이에서 벌어지는 것이다. 넓은 스코프의 fixture는 **읽기 전용으로만** 쓰거나, 매번 복사본을 내주게 설계하라.
:::

## yield fixture: setup과 teardown을 한 함수에

지금까지 본 fixture는 전부 `yield`를 썼다. `return` 대신 `yield`를 쓰면 **`yield` 앞은 setup, 뒤는 teardown**이 된다.

```python title="test_yield.py"
import pytest


@pytest.fixture
def tmp_resource():
    print("\n[setup] 자원 연다")
    resource = {"open": True}
    yield resource
    print("\n[teardown] 자원 닫는다")
    resource["open"] = False


def test_use_resource(tmp_resource):
    print("[test] 자원 사용 중:", tmp_resource["open"])
    assert tmp_resource["open"] is True


def test_fails_but_teardown_still_runs(tmp_resource):
    print("[test] 일부러 실패시킨다")
    assert tmp_resource["open"] is False  # 일부러 틀리게
```

두 번째 테스트를 **일부러 실패**하게 만들었다. teardown이 실행되는지 확인하기 위해서다.

```text nolines
test_yield.py::test_use_resource
[setup] 자원 연다
[test] 자원 사용 중: True
PASSED
[teardown] 자원 닫는다

test_yield.py::test_fails_but_teardown_still_runs
[setup] 자원 연다
[test] 일부러 실패시킨다
FAILED
[teardown] 자원 닫는다

1 failed, 1 passed in 0.16s
```

**테스트가 실패해도 teardown은 실행됐다.** 이게 `yield` fixture를 쓰는 이유다. `try/finally`와 똑같이 동작한다 — pytest는 실제로 fixture 함수를 제너레이터로 실행하고, 테스트가 끝나면(성공이든 실패든 예외든) `next()`를 한 번 더 호출해서 나머지를 마저 돈다. DB 연결, 임시 파일, 락 — 반드시 정리돼야 하는 자원은 예외 없이 이 패턴을 써라. `with` 문의 원리와 정확히 같다. ([1.17 컨텍스트 매니저](#/context-managers))

## parametrize: 테스트 하나로 입력 여러 개

같은 함수를 여러 입력으로 검증하고 싶을 때, 테스트를 복사-붙여넣기 하지 마라. `@pytest.mark.parametrize`가 이 문제를 정확히 위해 있다.

```python title="test_param.py"
def is_palindrome(s: str) -> bool:
    s = s.lower().replace(" ", "")
    return s == s[::-1]


import pytest


@pytest.mark.parametrize(
    "text, expected",
    [
        ("level", True),
        ("Level", True),
        ("hello", False),
        ("A man a plan a canal Panama", True),
        ("", True),
    ],
)
def test_is_palindrome(text, expected):
    assert is_palindrome(text) == expected
```

```text nolines
test_param.py::test_is_palindrome[level-True] PASSED
test_param.py::test_is_palindrome[Level-True] PASSED
test_param.py::test_is_palindrome[hello-False] PASSED
test_param.py::test_is_palindrome[A man a plan a canal Panama-True] PASSED
test_param.py::test_is_palindrome[-True] PASSED
```

함수 하나가 **다섯 개의 독립된 테스트**로 실행됐다. 각각 통과·실패가 따로 표시되고, 하나가 실패해도 나머지는 계속 돈다 — `for` 반복문 안에서 `assert`를 여러 번 하는 것과 결정적으로 다른 점이다. `for` 루프였다면 첫 번째 실패에서 전체가 멈추고, 그 뒤 입력이 맞는지는 영영 모른다.

데코레이터를 여러 개 쌓으면 **모든 조합**이 만들어진다.

```python
@pytest.mark.parametrize("a", [1, 2])
@pytest.mark.parametrize("b", [10, 20])
def test_stacked(a, b):
    assert a < b
```

실제로 4개(2×2)가 생성된다.

```text nolines
test_param.py::test_stacked[10-1] PASSED
test_param.py::test_stacked[10-2] PASSED
test_param.py::test_stacked[20-1] PASSED
test_param.py::test_stacked[20-2] PASSED
```

::: cote 코딩테스트 포인트
직접 짠 알고리즘 함수를 채점 사이트에 내기 전에, `parametrize`로 **엣지 케이스 목록**을 한 번에 돌려 보는 습관을 들여라. 빈 입력, 원소 1개, 전부 같은 값, 최댓값 경계 — 이런 것들을 매번 손으로 실행하는 대신 리스트 하나로 관리하면 실수로 빠뜨리는 일이 줄어든다.
:::

## monkeypatch: 환경을 통째로 갈아 끼운다

테스트가 진짜 환경변수나 진짜 시간에 의존하면 테스트가 불안정해진다(오늘은 통과, 자정 넘으면 실패 같은). `monkeypatch`는 pytest가 기본 제공하는 fixture로, **실행 중에 뭔가를 바꿔치기했다가 테스트가 끝나면 원래대로 되돌린다.**

```python title="app.py"
import os
import time


def get_api_key() -> str:
    key = os.environ.get("API_KEY")
    if key is None:
        raise RuntimeError("API_KEY 환경변수가 없다")
    return key


def timestamp_message(msg: str) -> str:
    return f"[{time.time()}] {msg}"
```

```python title="test_monkeypatch.py"
import pytest
import app


def test_get_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test-123")
    assert app.get_api_key() == "sk-test-123"


def test_get_api_key_missing(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        app.get_api_key()


def test_timestamp_message_is_deterministic(monkeypatch):
    monkeypatch.setattr(app.time, "time", lambda: 1_700_000_000.0)
    assert app.timestamp_message("hi") == "[1700000000.0] hi"


def test_env_leak_check():
    import os
    # 앞선 테스트의 setenv가 여기까지 새어 나오지 않는지 확인한다.
    assert os.environ.get("API_KEY") is None
```

```text nolines
test_monkeypatch.py::test_get_api_key PASSED
test_monkeypatch.py::test_get_api_key_missing PASSED
test_monkeypatch.py::test_timestamp_message_is_deterministic PASSED
test_monkeypatch.py::test_env_leak_check PASSED

4 passed in 0.03s
```

마지막 테스트 `test_env_leak_check`가 핵심이다. 앞의 테스트가 `API_KEY`를 설정했는데도, 뒤 테스트에서는 **다시 없는 상태**로 보인다. `monkeypatch`는 `function` 스코프 fixture이고, 테스트가 끝나면 자신이 바꾼 모든 것(환경변수, 속성, 딕셔너리 항목)을 **자동으로 원상 복구**한다. 직접 `os.environ["API_KEY"] = ...`로 설정했다면 이 복구를 手동으로 해야 하고, 잊으면 다음 테스트가 오염된다.

`setattr`도 마찬가지로 원상 복구된다 — `time.time`을 고정값으로 바꿔서 시간 의존적인 함수를 **결정적으로** 테스트할 수 있게 한 뒤, 테스트가 끝나면 진짜 `time.time`으로 돌아온다.

::: warn setenv/delenv가 monkeypatch.setattr보다 나은 이유
`os.environ["KEY"] = "val"` 대신 `monkeypatch.setenv("KEY", "val")`을 써라. 전자는 테스트가 끝나도 프로세스 전역 상태(`os.environ`)에 남아서 다음 테스트, 심지어 다음 테스트 파일까지 오염시킬 수 있다. `monkeypatch`를 거치면 되돌리기를 pytest가 보장해 준다.
:::

## unittest.mock: 진짜 객체 대신 가짜를 세운다

`monkeypatch`가 "값을 바꿔치기"라면, `unittest.mock`은 "객체 자체를 관찰 가능한 가짜로 바꾼다"에 가깝다.

### Mock — 무엇이든 받아주는 객체

```python title="Mock의 기본 동작"
from unittest.mock import Mock

fake = Mock()
fake.save(42, tag="important")

fake.save.assert_called_once_with(42, tag="important")  # 통과
```

`Mock()`은 **어떤 속성에 접근해도, 어떤 메서드를 호출해도** 에러 없이 받아준다. 존재하지 않는 메서드를 불러도 새로운 `Mock` 객체를 만들어 돌려줄 뿐이다.

```python
result = fake.whatever_method_i_want(1, 2, 3)
assert isinstance(result, Mock)   # 실제로 True
```

이게 편리하면서 동시에 위험하다. **오타를 내도 아무 말 안 한다.**

```python
fake.sav(1)          # save의 오타인데도 그냥 통과한다
assert fake.sav.called   # 참이다 — Mock은 이게 오타인지 모른다
```

이 위험을 없애는 게 `spec`이다. 실제 클래스를 지정하면, **그 클래스에 없는 메서드를 부르면 즉시 `AttributeError`**가 난다.

```python title="spec으로 오타를 잡는다"
class Downloader:
    def fetch(self, url: str) -> str: ...


fake = Mock(spec=Downloader)
fake.feetch("http://example.com")   # AttributeError: Mock object has no attribute 'feetch'
```

실제로 실행하면 정확히 `AttributeError`가 발생한다. **`Mock`을 쓸 때는 거의 항상 `spec`을 지정해라.** 이게 없으면 mock이 실제 인터페이스와 어긋나도 테스트가 아무것도 알려주지 않는다.

### MagicMock — 특수 메서드까지 지원

일반 `Mock`은 `__len__`, `__iter__` 같은 던더 메서드를 지원하지 않는다. 그런 게 필요하면 `MagicMock`을 쓴다.

```python
from unittest.mock import MagicMock

fake = MagicMock()
fake.__len__.return_value = 5
assert len(fake) == 5    # 일반 Mock이었다면 TypeError
```

### patch — 실제 위치의 객체를 잠깐 바꿔치기

`patch`는 "이 이름이 가리키는 것"을 테스트가 도는 동안만 바꾼다. 데코레이터로도, `with`로도 쓸 수 있다.

```python
from unittest.mock import patch

@patch("app.time.time")
def test_patch_as_decorator(mock_time):
    mock_time.return_value = 1_700_000_000.0
    assert app.timestamp_message("x") == "[1700000000.0] x"


def test_patch_as_context_manager():
    with patch("app.os.environ.get", return_value="patched-key"):
        assert app.get_api_key() == "patched-key"
```

둘 다 실제로 통과한다. 그런데 `patch("app.time.time")`처럼 문자열로 경로를 적는 방식에는 **반드시 알아야 하는 함정**이 있다.

::: danger patch는 "정의된 곳"이 아니라 "쓰이는 곳"을 바꿔야 한다
`app_from_import.py`가 이렇게 돼 있다고 하자.

```python title="app_from_import.py"
from time import time    # 함수 자체를 이름으로 가져왔다


def timestamp_message(msg: str) -> str:
    return f"[{time()}] {msg}"
```

`from time import time`을 실행하는 순간, `app_from_import` 모듈 안에 **`time`이라는 새 이름**이 생긴다. 이건 `time` 모듈과는 별개의 참조다. 그래서 `patch("time.time", ...)`으로 원본 `time` 모듈의 `time`을 바꿔도, `app_from_import.time`은 이미 예전 함수를 가리키는 채로 그대로 남는다.

실제로 확인해 보면 이렇다.

```text nolines
time.time patch (틀림) -> [1784607156.496699] x
app_from_import.time patch (맞음) -> [0.0] x
```

첫 번째는 patch가 **조용히 아무 효과도 내지 못했다** — 에러도 안 나고, 그냥 진짜 시각이 찍혔다. 두 번째, `patch("app_from_import.time", ...)`처럼 **그 이름을 실제로 쓰는 모듈의 네임스페이스**를 지정하니 제대로 먹혔다.

규칙은 하나다. **"정의된 곳"이 아니라 "그 이름을 찾아 쓰는 곳"을 patch하라.** `import time`으로 모듈 전체를 가져와 `time.time()`으로 쓰는 코드라면(이 절 앞의 `app.py`처럼) `patch("app.time.time")`이 맞고, `from time import time`으로 함수를 직접 가져온 코드라면 `patch("모듈이름.time")`이 맞다. 어느 쪽인지는 대상 파일의 import 문을 봐야 알 수 있다.
:::

## 테스트 더블의 용어: dummy, stub, spy, mock

"mock"이라는 단어를 모든 가짜 객체에 뭉뚱그려 쓰지만, 원래는 역할에 따라 이름이 다르다.

| 이름 | 하는 일 | 예 |
| --- | --- | --- |
| **dummy** | 그냥 자리만 채운다. 실제로 쓰이지 않는다 | `def f(logger=None)`에 아무 객체나 넘기기 |
| **stub** | 정해진 값을 그대로 돌려준다 | `Mock(return_value=42)` |
| **spy** | 진짜 객체를 그대로 두고 **호출 여부만 기록**한다 | `mocker.spy(obj, "method")` |
| **mock** | 호출 여부와 인자를 **검증**하는 것까지가 목적 | `fake.save.assert_called_once_with(...)` |

`unittest.mock`이라는 라이브러리 이름 때문에 전부 "mock"이라 부르지만, 실제로 많이 쓰는 건 stub(값만 바꿔치기)이다. **호출 자체를 검증**할 필요가 없다면 굳이 `assert_called_with`류를 쓰지 마라 — 검증이 늘어날수록 리팩터링에 깨지기 쉬운 테스트가 된다.

::: note spy는 진짜 로직을 지우지 않는다
`Mock`/`stub`은 원래 로직을 완전히 대체한다. `spy`는 **원래 함수를 그대로 실행시키면서 호출 기록만 곁에서 남긴다.** `unittest.mock`에는 spy 전용 헬퍼가 따로 없어서 보통 `wraps` 인자로 흉내 낸다.

```python
from unittest.mock import Mock

real_list = [1, 2, 3]
spy = Mock(wraps=real_list.append)
spy(4)
assert real_list == [1, 2, 3, 4]   # 진짜 append가 실행됐다
spy.assert_called_once_with(4)      # 그리고 호출도 기록됐다
```
:::

## 과도한 mocking의 위험: 가짜가 진짜 버그를 가린다

여기까지는 mock을 쓰는 법이었다. 이제 **왜 아껴 써야 하는지**를 실제 버그로 보여준다.

```python title="pricing.py — 버그가 있다"
def round_price(x: float) -> float:
    # 버그: 소수점을 아예 버린다. 원래 의도는 round(x, 2) 였다.
    return round(x)


def apply_discount(price: float, rate: float) -> float:
    discounted = price * (1 - rate)
    return round_price(discounted)
```

`round_price`에 버그가 있다. 소수점 둘째 자리까지 반올림해야 하는데 정수로 뭉개 버린다. 이제 두 가지 방식으로 `apply_discount`를 테스트한다.

```python title="test_overmock_danger.py"
from unittest.mock import patch
import pricing


def test_apply_discount_with_overmocking():
    # round_price를 통째로 mock으로 바꿔치기
    with patch("pricing.round_price", return_value=90.0) as mock_round:
        result = pricing.apply_discount(100.0, 0.1)
        mock_round.assert_called_once()
        assert result == 90.0


def test_apply_discount_without_mocking():
    # 실제 round_price를 그대로 통과시킨다
    result = pricing.apply_discount(100.0, 0.001)
    # 100 * 0.999 = 99.9 -> 올바른 반올림이면 99.9, 버그가 있으면 100
    assert result == 99.9
```

실제로 돌린 결과다.

```text nolines
test_overmock_danger.py::test_apply_discount_with_overmocking PASSED
test_overmock_danger.py::test_apply_discount_without_mocking FAILED

FAILED test_overmock_danger.py::test_apply_discount_without_mocking
  assert 100 == 99.9

1 failed, 1 passed in 0.14s
```

**첫 번째 테스트는 통과했다.** `round_price`를 통째로 mock으로 바꿔치기했기 때문에, 진짜 `round_price` 안의 버그와는 완전히 무관하게 돈다. `mock_round.assert_called_once()`가 통과해도 그건 "함수가 호출됐다"만 확인할 뿐, **그 함수가 옳은 일을 했는지는 전혀 확인하지 않는다.** 두 번째 테스트는 진짜 `round_price`를 그대로 통과시켰고, 버그가 정직하게 드러나서 실패했다.

이 두 테스트를 나란히 놓고 보면 결론은 명확하다. **의존하는 대상을 mock으로 바꿀 때마다, 그 mock 뒤에 숨은 실제 코드는 테스트 범위에서 빠진다.** mock이 늘어날수록 "테스트가 통과한다"는 사실이 보장하는 범위는 좁아진다. 극단적으로 모든 걸 mock하면, 남는 건 "내가 짠 순서대로 함수가 호출됐다"는 것뿐이고 — 그건 애초에 코드를 다시 베껴 쓴 것과 다르지 않다.

::: tip mock을 어디에 써야 하는가
- **경계에서만 mock하라.** 네트워크 호출, 파일 시스템, 시간, 랜덤 — **내가 통제할 수 없는 외부**만 가짜로 바꾼다.
- **내 코드끼리의 협업은 되도록 진짜로 돌려라.** `apply_discount`와 `round_price`는 둘 다 내가 짠 순수 함수다. 이런 건 mock 없이 실제로 실행해서 **통합된 결과**를 확인하는 게 버그를 잡는다.
- **테스트가 구현 세부사항과 결합되면 신호다.** `assert_called_once_with(정확히 이 인자로)`가 많아질수록, 내부 구현을 리팩터링할 때마다 테스트가 깨진다. 그건 "동작"이 아니라 "구현"을 테스트하고 있다는 뜻이다.
- 항상 **mock 없이 도는 테스트를 최소 하나는 남겨라.** 이번 예제의 `test_apply_discount_without_mocking`처럼, 진짜 함수들이 실제로 맞물려 돌아가는지 확인하는 테스트가 없으면 이런 종류의 버그는 영원히 안 잡힌다.
:::

## 요약

- fixture는 `setUp`/`tearDown`을 함수 인자로 명시적으로 선언하는 방식이다. pytest가 이름으로 찾아 주입한다.
- 스코프(`function`/`class`/`module`/`session`)는 fixture를 얼마나 자주 새로 만들지 정한다. 실측으로 확인했듯, 넓은 스코프는 빠르지만 상태 오염 위험이 있다.
- `yield` fixture는 `try/finally`처럼 동작한다. 테스트가 실패해도 teardown은 반드시 실행된다.
- `parametrize`는 같은 테스트를 여러 입력으로 돌리되, **각 입력을 독립된 테스트**로 취급한다. 하나 실패해도 나머지는 계속 돈다.
- `monkeypatch`는 환경변수·속성을 바꿔치기하고 테스트가 끝나면 자동으로 되돌린다. `os.environ` 직접 조작보다 항상 안전하다.
- `Mock`/`MagicMock`/`patch`는 강력하지만, `spec` 없이 쓰면 오타를 잡아주지 못한다. `patch`는 **정의된 곳이 아니라 쓰이는 곳**을 지정해야 한다.
- dummy/stub/spy/mock은 서로 다른 역할이다. 대부분의 경우 필요한 건 stub이지, 호출을 검증하는 진짜 mock이 아니다.
- **mock을 많이 쓸수록 테스트가 보장하는 범위는 좁아진다.** 경계(외부 자원)에서만 mock하고, 내 코드끼리는 실제로 돌려라.

::: quiz 연습문제
1. `scope="module"`인 fixture와 `scope="function"`인 fixture를 하나씩 만들고, 같은 파일에 테스트 3개를 넣어 `pytest -v -s`로 돌려라. 이 절의 표와 실측 결과를 보지 않고 각 fixture가 몇 번 생성될지 먼저 예측한 뒤 맞춰봐라.
2. 다음 fixture는 왜 위험한가? 실행해서 확인하고, `function` 스코프로 바꿔서 다시 확인하라.

   ```python
   @pytest.fixture(scope="session")
   def shared_list():
       return []


   def test_one(shared_list):
       shared_list.append(1)
       assert shared_list == [1]


   def test_two(shared_list):
       assert shared_list == []   # 통과할까?
   ```

3. `Mock(spec=SomeClass)`와 그냥 `Mock()`의 차이를 오타 하나로 직접 만들어 확인하라. `spec` 없이는 오타가 어떻게 조용히 통과하는지, `spec`을 걸면 어떤 예외가 나는지 실행해서 보여라.
4. 이 절의 `pricing.py` 버그를 실제로 고쳐라(`round(x)`를 `round(x, 2)`로). 두 테스트(`with_overmocking`, `without_mocking`)를 다시 돌리면 어떻게 되는가? 결과를 예측하고 확인하라.
5. `patch("모듈.이름")`이 왜 "정의된 곳"이 아니라 "쓰이는 곳"을 가리켜야 하는지, 이 절의 `app.py`(`import time`)와 `app_from_import.py`(`from time import time`) 차이로 설명하라. 어느 쪽이든 상관없이 통하는 patch 대상이 있다면 무엇인가?
:::

**다음 절**: [6.3 속성 기반 테스트 (Hypothesis)](#/hypothesis) — 예제를 일일이 나열하는 대신, 항상 성립해야 하는 성질을 코드로 표현하고 반례를 자동으로 찾게 한다.
