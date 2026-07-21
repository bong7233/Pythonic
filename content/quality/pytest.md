# 6.1 pytest 완전 정복

::: lead
지금까지 이 책은 코드가 **왜 그렇게 동작하는지**를 다뤘다. 이 절부터는 방향이 바뀐다. 내가 짠 코드가 **정말로 맞는지 어떻게 아는가**다. `print` 로 확인하고 지우는 걸 반복하는 단계와, 자동으로 검증되는 테스트를 쌓는 단계 사이에는 큰 차이가 있다. pytest는 파이썬 테스트의 사실상 표준이고, 그 이유는 단 하나다 — **실패했을 때 왜 실패했는지를 아무 설정 없이 보여준다.** 이 절에서 그걸 표준 라이브러리 `unittest` 와 나란히 실행해서 직접 비교한다.
:::

## assert 하나로 충분한 이유

`unittest` 로 테스트를 짜 본 적이 있다면 이런 코드에 익숙할 것이다.

```python
self.assertEqual(got, want)
self.assertTrue(x in y)
self.assertIsNone(z)
self.assertAlmostEqual(a, b)
```

메서드 이름을 상황별로 골라 써야 한다. 비교 대상이 리스트인지 딕셔너리인지 근사값인지에 따라 부르는 이름이 다르다. pytest의 답은 정반대다. **전부 파이썬의 `assert` 문 하나로 쓴다.**

```python title="test_cart.py"
def total_price(items):
    return sum(items.values())


def test_total_price():
    items = {"apple": 1000, "banana": 500}
    assert total_price(items) == 2000
```

`assertEqual`, `assertIn`, `assertIsNone` 같은 이름을 외울 필요가 없다. 파이썬을 아는 사람은 이미 `assert` 를 안다. 그런데 여기서 당연한 의문이 생긴다. **평범한 `assert` 는 실패하면 `AssertionError` 하나만 던지고 아무 정보도 안 남기는데, pytest는 어떻게 저렇게 자세한 실패 메시지를 보여주는가?**

직접 실행해서 확인해 보자. 아래 네 개의 테스트는 전부 일부러 실패하게 만들었다.

```python title="test_compare.py"
def add(a, b):
    return a + b


def test_add_wrong():
    assert add(2, 3) == 6


def test_list_wrong():
    got = [1, 2, 4]
    want = [1, 2, 3]
    assert got == want


def test_dict_wrong():
    got = {"a": 1, "b": 2}
    want = {"a": 1, "b": 3}
    assert got == want


def test_string_in():
    msg = "hello world"
    assert "bye" in msg
```

```bash
uv run pytest test_compare.py -q
```

```text nolines
FFFF                                                                     [100%]
================================== FAILURES ===================================
_______________________________ test_add_wrong ________________________________

    def test_add_wrong():
>       assert add(2, 3) == 6
E       assert 5 == 6
E        +  where 5 = add(2, 3)

test_compare.py:6: AssertionError
_______________________________ test_list_wrong ________________________________

    def test_list_wrong():
        got = [1, 2, 4]
        want = [1, 2, 3]
>       assert got == want
E       assert [1, 2, 4] == [1, 2, 3]
E
E         At index 2 diff: 4 != 3
E         Use -v to get more diff

test_compare.py:12: AssertionError
_______________________________ test_dict_wrong ________________________________

    def test_dict_wrong():
        got = {"a": 1, "b": 2}
        want = {"a": 1, "b": 3}
>       assert got == want
E       AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 3}
E
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b': 2} != {'b': 3}
E         Use -v to get more diff

test_compare.py:18: AssertionError
_______________________________ test_string_in ________________________________

    def test_string_in():
        msg = "hello world"
>       assert "bye" in msg
E       AssertionError: assert 'bye' in 'hello world'

test_compare.py:23: AssertionError
=========================== short test summary info ===========================
FAILED test_compare.py::test_add_wrong - assert 5 == 6
FAILED test_compare.py::test_list_wrong - assert [1, 2, 4] == [1, 2, 3]
FAILED test_compare.py::test_dict_wrong - AssertionError: assert {'a': 1, 'b'...
FAILED test_compare.py::test_string_in - AssertionError: assert 'bye' in 'hel...
4 failed in 0.12s
```

(Python 3.14.5 / pytest 9.1.1 / Windows 기준 실측.)

`add(2, 3)` 이 실제로 무슨 값을 냈는지(`5`), 리스트의 어느 인덱스에서 어긋났는지(`인덱스 2에서 4 != 3`), 딕셔너리의 어느 키가 다른지(`'b': 2` vs `'b': 3`) — 아무것도 설정하지 않았는데 전부 나온다.

이번엔 완전히 같은 논리를 표준 라이브러리 `unittest` 로, **똑같이 그냥 `assert` 를 써서** 돌려 보자.

```python title="test_unittest_compare.py"
import unittest


def add(a, b):
    return a + b


class TestAdd(unittest.TestCase):
    def test_add_wrong(self):
        assert add(2, 3) == 6

    def test_list_wrong(self):
        got = [1, 2, 4]
        want = [1, 2, 3]
        assert got == want
```

```bash
uv run python -m unittest test_unittest_compare -v
```

```text nolines
test_add_wrong (test_unittest_compare.TestAdd.test_add_wrong) ... FAIL
test_list_wrong (test_unittest_compare.TestAdd.test_list_wrong) ... FAIL

======================================================================
FAIL: test_add_wrong (test_unittest_compare.TestAdd.test_add_wrong)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\test_unittest_compare.py", line 10, in test_add_wrong
    assert add(2, 3) == 6
           ^^^^^^^^^^^^^^
AssertionError

======================================================================
FAIL: test_list_wrong (test_unittest_compare.TestAdd.test_list_wrong)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\test_unittest_compare.py", line 15, in test_list_wrong
    assert got == want
           ^^^^^^^^^^^
AssertionError

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (failures=2)
```

**딱 `AssertionError` 뿐이다.** `add(2, 3)` 이 몇이었는지, 리스트가 어디서 어긋났는지 아무것도 없다. `unittest` 로 이 정보를 얻으려면 처음부터 `self.assertEqual(add(2, 3), 6)` 처럼 **전용 메서드로 다시 썼어야** 한다. pytest는 그럴 필요가 없다.

::: deep 어떻게 이게 가능한가 — import 시점의 재작성
비밀은 이름 그대로 **assertion rewriting**(assert 재작성)이다. pytest는 테스트 파일을 임포트하기 **전에** 소스를 파싱해서 AST([3.6 AST](#/ast))를 얻고, 그 안의 모든 `assert` 문을 찾아 **직접 만든 바이트코드로 바꿔치기한다.** 원래 `assert expr` 은 이렇게 컴파일된다.

```python
if not expr:
    raise AssertionError
```

pytest는 이걸 이렇게 바꾼다(개념적으로).

```python
_result = expr                      # 실제로는 expr을 부분식 단위로 쪼개 전부 저장한다
if not _result:
    raise AssertionError(pytest_에서_만든_설명_문자열)
```

핵심은 **`expr` 을 평가하는 과정에서 나오는 모든 중간값을 캡처해 둔다는 것**이다. `add(2, 3) == 6` 이면 좌변 `add(2, 3)` 을 계산한 값(5)을 따로 저장해 뒀다가, 실패 시 `assert 5 == 6\n +  where 5 = add(2, 3)` 처럼 조립한다. 리스트·딕셔너리 비교는 pytest가 내장한 전용 비교기(`_pytest.assertion.util`)가 인덱스별·키별로 순회하며 차이를 뽑아낸다.

이건 **런타임 트릭이 아니라 컴파일 타임 변환**이다. 그래서 딱 하나 중요한 제약이 있다. **pytest가 직접 임포트하는 테스트 파일에만 적용된다.** 테스트가 아닌 일반 모듈 안의 `assert` (예: 라이브러리 코드 내부)는 재작성되지 않는다. 재작성 대상 파일을 늘리고 싶으면 `conftest.py` 에서 `pytest.register_assert_rewrite("모듈명")` 을 부른다.
:::

::: note unittest가 나쁜 게 아니다
`unittest` 는 표준 라이브러리라 설치가 필요 없고, Java의 JUnit 계열과 구조가 비슷해서 다른 언어에서 넘어온 사람에게 익숙하다. 큰 레거시 코드베이스는 지금도 `unittest` 로 돼 있는 경우가 많다. pytest는 `unittest.TestCase` 로 짠 테스트도 그대로 실행할 수 있어서(위 예제가 그랬다), **마이그레이션 비용이 거의 0**이다. 새 프로젝트라면 pytest를 쓰지 않을 이유가 없다는 것뿐이다.
:::

## 테스트를 어떻게 찾는가 — 발견 규칙

pytest는 설정 파일에 테스트 목록을 적어 두지 않는다. **정해진 이름 규칙에 맞는 것을 자동으로 찾는다(discovery).** 규칙은 셋이다.

| 대상 | 규칙 |
| --- | --- |
| 파일 | `test_*.py` 또는 `*_test.py` |
| 클래스 | `Test` 로 시작 (단, `__init__` 이 있으면 제외) |
| 함수/메서드 | `test_` 로 시작 |

이 규칙을 벗어나면 **조용히 무시된다.** 에러도, 경고도 없다. 직접 확인해 보자.

```python title="discovery_demo/check_something.py — 파일명이 규칙을 벗어남"
def test_never_found():
    assert 1 == 2
```

```python title="discovery_demo/test_found.py"
def test_ok():
    assert 1 == 1


class NotATestClass:               # Test로 시작하지 않음
    def test_inside_wrong_class(self):
        assert False


class TestSuite:                    # Test로 시작 → 수집됨
    def test_inside_right_class(self):
        assert 1 == 1

    def helper_not_collected(self): # test_로 시작하지 않음
        assert False
```

```bash
uv run pytest discovery_demo -v
```

```text nolines
collecting ... collected 2 items

discovery_demo/test_found.py::test_ok PASSED                             [ 50%]
discovery_demo/test_found.py::TestSuite::test_inside_right_class PASSED  [100%]

============================== 2 passed in 0.01s ==============================
```

**2개만 잡혔다.** `check_something.py` 안의 `test_never_found` 는 실패하도록 일부러 만들었는데, 파일명이 `test_` 로 시작하지 않아서 **애초에 실행되지 않았다.** `NotATestClass.test_inside_wrong_class` 는 확실히 실패할 코드(`assert False`)인데도 클래스 이름이 `Test` 로 시작하지 않아 통과한 것처럼 조용히 넘어갔다. `helper_not_collected` 도 마찬가지로 무시됐다.

::: danger 발견되지 않은 테스트는 통과한 테스트보다 위험하다
CI가 초록불이라고 안심하기 쉽다. 그런데 그 초록불이 "테스트를 다 통과했다"가 아니라 **"애초에 실행 안 됐다"** 일 수 있다. 파일명 오타(`tests_login.py`, `test-login.py`) 하나로 테스트 전체가 몇 주간 아무것도 검증하지 않은 채 CI만 통과시키는 사고가 실제로 일어난다. `pytest --collect-only` 로 **몇 개가 잡혔는지 눈으로 세어 보는 습관**이 유일한 방어책이다.
:::

```bash
uv run pytest --collect-only -q
```

이 명령은 실행하지 않고 **수집된 테스트 목록만** 보여준다. 새 파일을 추가했다면 한 번 돌려서 개수가 예상과 맞는지 확인하는 습관을 들여라.

::: note testpaths 로 검색 범위를 좁힌다
프로젝트에 `scripts/`, `notebooks/` 처럼 `test_` 로 시작하는 파일이 우연히 섞여 있으면 발견 시간이 길어지고 엉뚱한 파일까지 훑는다. [0.4 도구 세팅](#/tooling)에서 본 것처럼 `pyproject.toml` 에 `[tool.pytest.ini_options] testpaths = ["tests"]` 를 지정하면 그 디렉터리만 훑는다.
:::

## 좋은 테스트의 세 가지 조건

테스트를 짤 줄 아는 것과 **좋은** 테스트를 짜는 것은 다르다. 세 가지만 지키면 나머지는 자연히 따라온다.

### 하나의 개념만 검증한다

테스트 하나가 실패했을 때, **왜 실패했는지 함수 이름만 보고 알 수 있어야 한다.** 여러 동작을 한 테스트에 몰아넣으면 실패 원인을 코드를 읽어야만 알 수 있다.

```python
# ❌ 이름은 "생성"인데 실제로는 생성+수정+삭제를 다 검증한다
def test_user():
    user = create_user("amy")
    assert user.name == "amy"
    user.rename("bob")
    assert user.name == "bob"
    delete_user(user)
    assert not user_exists("bob")


# ✅ 각 테스트가 딱 하나의 동작만 책임진다
def test_create_user_sets_name():
    user = create_user("amy")
    assert user.name == "amy"


def test_rename_changes_name():
    user = create_user("amy")
    user.rename("bob")
    assert user.name == "bob"


def test_delete_user_removes_it():
    user = create_user("amy")
    delete_user(user)
    assert not user_exists("amy")
```

쪼갠 버전은 `test_rename_changes_name` 이 실패하면 **이름 변경 로직에 문제가 있다는 것을 즉시 안다.** `test_user` 가 실패하면 생성·수정·삭제 중 어디가 문제인지 트레이스백을 읽어야 한다.

### 독립적이다 — 순서에 의존하지 않는다

테스트는 **어떤 순서로 돌려도, 몇 개만 골라 돌려도** 같은 결과를 내야 한다. 이걸 어기면 어떤 일이 생기는지 실제로 만들어서 보여준다.

```python title="test_shared_state.py — 모듈 전역 상태를 공유"
shared_cache = {}


def test_write_cache():
    shared_cache["user"] = "amy"
    assert shared_cache["user"] == "amy"


def test_cache_is_empty_at_start():
    assert shared_cache == {}
```

```bash
uv run pytest test_shared_state.py -q
```

```text nolines
.F                                                                       [100%]
================================== FAILURES ===================================
________________________ test_cache_is_empty_at_start _________________________

    def test_cache_is_empty_at_start():
>       assert shared_cache == {}
E       AssertionError: assert {'user': 'amy'} == {}
E
E         Left contains 1 more item:
E         {'user': 'amy'}
E         Use -v to get more diff

test_shared_state.py:10: AssertionError
=========================== short test summary info ===========================
FAILED test_shared_state.py::test_cache_is_empty_at_start
1 failed, 1 passed in 0.12s
```

이제 `test_cache_is_empty_at_start` **하나만** 골라서 돌려 보자.

```bash
uv run pytest test_shared_state.py -q -k test_cache_is_empty_at_start
```

```text nolines
.                                                                        [100%]
1 passed, 1 deselected in 0.01s
```

**같은 테스트, 같은 코드인데 결과가 다르다.** 전체를 돌리면 실패하고, 혼자 돌리면 통과한다. 원인은 `test_write_cache` 가 모듈 전역 `shared_cache` 를 오염시켜 놓고, 그 뒤에 도는 다른 테스트가 그 잔여물에 의존(정확히는 "없을 것이다"라고 잘못 가정)했기 때문이다. pytest는 기본적으로 파일에 적힌 순서로 실행하지만, **그 순서에 기대는 순간 테스트는 이미 버그다.** 실행 순서가 바뀌거나(플러그인, 병렬 실행), 그 테스트 하나만 재현하려고 돌리는 순간 거짓 결과를 낸다.

::: warn 상태를 공유하지 않는 방법
전역 변수, 클래스 변수, 파일, 데이터베이스 — 테스트 사이에 뭔가 남는다면 전부 이 함정의 후보다. 각 테스트가 **자기만의 데이터를 직접 만들고**, 필요하면 끝난 뒤 **직접 치운다.** [6.2 fixture, 파라미터화, mocking](#/pytest-advanced)에서 다루는 fixture의 존재 이유가 정확히 이것이다 — 매 테스트마다 깨끗한 상태를 새로 만들어 주는 장치다.
:::

### 빠르다

느린 테스트는 실행되지 않는 테스트다. 사람은 몇 초짜리 테스트는 저장할 때마다 돌리지만, 몇 분짜리는 커밋 직전에만, 그러다 결국 CI에서만 돌린다. 그러면 **버그를 코드를 짠 순간이 아니라 며칠 뒤에** 알게 된다.

::: perf 느려지는 흔한 원인
- 진짜 네트워크·DB에 접속한다 → 모킹으로 대체한다([6.2 fixture, 파라미터화, mocking](#/pytest-advanced)).
- `sleep()` 으로 타이밍을 맞춘다 → 시간을 흉내 내는 방식으로 바꾼다.
- 매 테스트가 무거운 픽스처(대용량 파일, 모델 로딩)를 처음부터 새로 만든다 → 스코프를 `session`/`module` 로 넓혀 재사용한다.

단위 테스트(unit test) 묶음 전체는 **몇 초 안에** 끝나야 한다. 몇 분이 걸리기 시작하면 이미 통합 테스트(integration test)가 섞여 있다는 신호다. 느린 것과 빠른 것을 별도 디렉터리나 마커(`@pytest.mark.slow`)로 나눠서, 평소엔 빠른 것만 돌리고 CI에서만 전체를 돌리는 구성이 실전에서 흔히 쓰인다.
:::

## 근사 비교: 부동소수점에 == 을 쓰면 안 되는 이유

[1.2 숫자와 수치 연산](#/numbers)에서 다뤘듯 부동소수점은 정확히 표현되지 않는 값이 많다. 테스트에서 이걸 무시하고 `==` 를 쓰면 어떻게 되는지 직접 실행해 보자.

```python title="test_approx.py"
import pytest


def test_float_bad():
    assert 0.1 + 0.2 == 0.3


def test_float_approx_good():
    assert 0.1 + 0.2 == pytest.approx(0.3)
```

```bash
uv run pytest test_approx.py -q
```

```text nolines
F.                                                                       [100%]
================================== FAILURES ===================================
_______________________________ test_float_bad ________________________________

    def test_float_bad():
>       assert 0.1 + 0.2 == 0.3
E       assert (0.1 + 0.2) == 0.3

test_approx.py:5: AssertionError
=========================== short test summary info ===========================
FAILED test_approx.py::test_float_bad - assert (0.1 + 0.2) == 0.3
1 failed, 1 passed in 0.13s
```

`0.1 + 0.2` 는 이진 부동소수점으로 `0.30000000000000004` 가 되므로 `0.3` 과 정확히 같지 않다. `pytest.approx(0.3)` 을 쓴 두 번째 테스트는 **상대 오차 기본값(약 $10^{-6}$) 안에 들어오면 같다고 판정**하므로 통과한다.

`approx` 가 실패했을 때는 오차까지 같이 보여준다. 이것도 확인해 보자.

```python
def test_approx_fail_shows_detail():
    result = 1.0 / 3.0 * 3
    assert result == pytest.approx(1.1)
```

```text nolines
E       assert 1.0 == 1.1 ± 1.1e-06
E
E         comparison failed
E         Obtained: 1.0
E         Expected: 1.1 ± 1.1e-06
```

기대값(`1.1`)과 실제 허용 오차 범위(`± 1.1e-06`), 그리고 실제로 얻은 값(`1.0`)이 한 줄에 다 나온다. `assertAlmostEqual(a, b, places=7)` 처럼 소수점 자릿수를 세어 지정하는 `unittest` 방식보다 **읽는 사람이 의도를 바로 이해할 수 있는 형태**다.

::: cote 코딩테스트에서 근사 비교가 필요한 순간
기하 문제(좌표 계산), 확률·통계 문제, 부동소수점 답을 요구하는 문제에서 직접 짠 함수를 검증할 때 `assert result == pytest.approx(expected, rel=1e-6)` 를 쓰면 오차 누적 때문에 생기는 미세한 차이로 테스트가 잘못 실패하는 걸 막는다. 온라인 저지 채점기는 보통 자체적으로 오차 허용 범위를 두지만, **로컬에서 직접 검증할 때는 내가 그 허용치를 정해야 한다.**
:::

::: note approx는 컨테이너도 다룬다
```python
assert [0.1 + 0.2, 1.0 / 3] == pytest.approx([0.3, 0.333333])
assert {"x": 0.1 + 0.2} == pytest.approx({"x": 0.3})
```
리스트·튜플·딕셔너리·NumPy 배열까지 원소 단위로 근사 비교한다. 하나씩 풀어서 반복문으로 비교할 필요가 없다.
:::

## conftest.py — 여러 파일이 공유하는 준비물

같은 디렉터리 안의 여러 테스트 파일이 똑같은 준비물(데이터베이스 연결, 임시 파일, 샘플 데이터)을 필요로 하는 경우가 흔하다. 매 파일마다 복사해 넣는 대신, **`conftest.py` 라는 특수한 이름의 파일에 한 번 정의해 두면 같은 디렉터리(와 하위 디렉터리)의 모든 테스트가 import 없이 바로 쓸 수 있다.**

```python title="conftest_demo/conftest.py"
import pytest


@pytest.fixture
def sample_cart():
    return {"apple": 2, "banana": 1}
```

```python title="conftest_demo/test_cart.py — sample_cart를 어디서도 import하지 않았다"
def test_total_items(sample_cart):
    assert sum(sample_cart.values()) == 3


def test_has_apple(sample_cart):
    assert "apple" in sample_cart
```

```bash
uv run pytest conftest_demo -v
```

```text nolines
conftest_demo/test_cart.py::test_total_items PASSED                      [ 50%]
conftest_demo/test_cart.py::test_has_apple PASSED                        [100%]

============================== 2 passed in 0.01s ==============================
```

`test_cart.py` 어디에도 `sample_cart` 를 정의하거나 import하는 코드가 없다. 함수 매개변수 이름이 `sample_cart` 인 것만으로 pytest가 `conftest.py` 의 픽스처를 찾아 자동으로 주입했다. 이 자동 발견이 가능한 이유는 pytest가 픽스처를 **일반 함수 호출이 아니라 이름 기반 의존성 주입(dependency injection)** 으로 다루기 때문이다.

::: note conftest.py는 import하지 않는다
`conftest.py` 는 일반 모듈처럼 `import conftest` 해서 쓰는 파일이 아니다. **파일 이름 자체가 pytest에게 미리 약속된 신호다.** pytest는 테스트를 수집하기 전에 해당 디렉터리부터 루트까지 거슬러 올라가며 모든 `conftest.py` 를 찾아 미리 읽어 들인다. 그래서 상위 디렉터리의 `conftest.py` 에 정의한 픽스처는 하위 디렉터리 전부에서 쓸 수 있고, 반대로 하위 디렉터리의 것은 그 밖에서 보이지 않는다 — **스코프가 디렉터리 트리를 따라간다.**
:::

여기서는 발견 규칙과 최소한의 사용법만 확인했다. 픽스처의 스코프(`function`/`class`/`module`/`session`), 파라미터화(`@pytest.mark.parametrize`), 진짜 외부 의존성을 가짜로 바꾸는 모킹은 분량이 커서 [6.2 fixture, 파라미터화, mocking](#/pytest-advanced)에서 통째로 다룬다.

## 요약

- pytest는 `assertEqual` 같은 전용 메서드 없이 **평범한 `assert` 하나**로 테스트를 쓴다.
- 그게 가능한 이유는 **assertion rewriting** — 임포트 시점에 AST를 고쳐서 실패 시 중간값을 자동으로 보여준다. `unittest` 의 맨 `assert` 는 `AssertionError` 하나만 던지는 것과 실측으로 비교했다.
- 테스트 발견은 **`test_*.py` 파일 + `Test*` 클래스 + `test_` 함수** 규칙을 따른다. 규칙을 벗어나면 조용히 무시된다 — `--collect-only` 로 개수를 확인하는 습관을 들여라.
- 좋은 테스트는 **하나의 개념만, 독립적으로, 빠르게** 검증한다. 전역 상태를 공유하면 실행 순서에 따라 결과가 달라지는 것을 직접 확인했다.
- 부동소수점 비교는 `==` 대신 **`pytest.approx`** 를 쓴다.
- 여러 파일이 공유하는 준비물은 **`conftest.py`** 에 픽스처로 정의한다. import 없이 이름만으로 주입된다.

::: quiz 연습문제
1. 아래 테스트가 실패하도록 만든 뒤, `unittest.TestCase.assertEqual` 로 짠 같은 테스트와 pytest의 평범한 `assert` 로 짠 테스트의 실패 메시지를 나란히 실행해서 비교하라.

   ```python
   def test_sorted_list():
       assert sorted([3, 1, 2]) == [1, 2, 3, 4]
   ```

2. 다음 파일 이름 중 pytest 기본 설정에서 **발견되지 않는** 것은? 실제로 만들어서 `--collect-only` 로 확인하라.

   - `test_login.py`
   - `login_test.py`
   - `Test_login.py`
   - `tests_login.py`

3. 아래 테스트 스위트는 두 테스트를 함께 돌리면 통과하고, `test_second` 만 단독으로 돌리면 실패한다. 원인을 설명하고 독립적으로 고쳐라.

   ```python
   counter = {"n": 0}


   def test_first():
       counter["n"] += 1
       assert counter["n"] == 1


   def test_second():
       assert counter["n"] == 1
   ```

4. `pytest.approx` 를 쓰지 않고 부동소수점을 안전하게 비교하려면 어떻게 해야 하는가? (힌트: `abs(a - b) < 1e-6` 식으로 직접 쓰는 것과 `approx` 의 차이가 무엇인지 생각하라.)

5. `conftest.py` 에 정의한 픽스처를 다른 디렉터리의 테스트에서도 쓰고 싶다. `conftest.py` 를 어디에 둬야 하는가?
:::

**다음 절**: [6.2 fixture, 파라미터화, mocking](#/pytest-advanced) — 픽스처의 스코프와 의존성 조립, 외부 세계를 가짜로 바꾸는 법.
