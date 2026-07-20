# 2.8 mypy와 pyright 실전

::: lead
[2.1 왜 타입 힌트인가](#/why-typing)에서 타입 힌트가 "점진적"이라고 했다. 점진적이라는 말은 좋게 들리지만, 실무에서는 질문 하나로 바뀐다. **타입을 다 적었는데, 그래서 누가 검사하나?** 답은 파이썬 인터프리터가 아니다. 인터프리터는 타입 힌트를 거의 완전히 무시한다. 검사는 별도의 프로그램 — mypy나 pyright — 이 파일을 읽고 사람이 손으로 하던 추론을 대신 해 주는 것이다. 이 절은 그 둘을 실제로 돌려서 뭐가 나오는지 보고, `strict` 모드가 정확히 뭘 켜는지, 기존 코드베이스에 어떻게 스며들게 하는지를 다룬다.
:::

## 타입 힌트는 런타임에 아무것도 하지 않는다

먼저 이 사실을 몸으로 확인하고 넘어가야 한다. 아니면 이 절 전체가 안 믿긴다.

```python title="no_runtime_effect.py"
def add(a: int, b: int) -> int:
    return a + b


print(add("hello", " world"))
print(add.__annotations__)
```

이 함수는 `int` 를 받겠다고 선언해 놓고 문자열을 받는다. 실행해 보자.

```bash
$ python no_runtime_effect.py
```

```text nolines
hello world
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

**아무 일도 안 일어난다.** 에러도, 경고도 없다. `a + b` 는 파이썬 입장에서 그냥 `__add__` 호출이고, 문자열은 `__add__` 를 구현하니 잘 붙는다. 함수의 `__annotations__` 딕셔너리에 타입 정보가 저장되긴 하지만 ([2.9 런타임 타입 정보](#/runtime-typing)에서 다룬다), 그걸 검사에 쓰는 코드는 어디에도 없다. `int` 라는 어노테이션은 **주석보다 조금 더 구조화된 문서**일 뿐, 실행에는 [1.10 함수](#/functions)에서 본 매개변수 바인딩 규칙 외에 아무 영향도 주지 않는다.

이제 같은 파일에 pyright를 돌려 보자.

```bash
$ uvx pyright no_runtime_effect.py
```

```text nolines
no_runtime_effect.py:5:11 - error: Argument of type "Literal['hello']" cannot be
  assigned to parameter "a" of type "int" in function "add"
    "Literal['hello']" is not assignable to "int" (reportArgumentType)
no_runtime_effect.py:5:20 - error: Argument of type "Literal[' world']" cannot be
  assigned to parameter "b" of type "int" in function "add"
    "Literal[' world']" is not assignable to "int" (reportArgumentType)
2 errors, 0 warnings, 0 informations
```

mypy도 똑같은 것을 다른 말투로 잡는다.

```bash
$ uvx mypy no_runtime_effect.py
```

```text nolines
no_runtime_effect.py:5: error: Argument 1 to "add" has incompatible type "str";
  expected "int"  [arg-type]
no_runtime_effect.py:5: error: Argument 2 to "add" has incompatible type "str";
  expected "int"  [arg-type]
Found 2 errors in 1 file (checked 1 source file)
```

여기서 이 절의 핵심 그림이 나온다. **파이썬 코드는 두 개의 완전히 분리된 프로그램이 읽는다.** 하나는 CPython — 타입 힌트를 무시하고 그냥 실행한다. 하나는 정적 검사기 — 실행은 안 하고 코드를 읽기만 하면서 타입이 앞뒤가 맞는지 추론한다. `python no_runtime_effect.py` 를 돌리면 "hello world"가 찍히고, `pyright no_runtime_effect.py` 를 돌리면 에러 2개가 나온다. **둘 다 맞다.** 서로 다른 질문에 답하고 있을 뿐이다.

::: warn 타입체커가 통과했다고 버그가 없는 게 아니다
정적 검사기는 **당신이 선언한 타입들이 서로 모순되지 않는지**만 본다. 로직이 맞는지는 안 본다. `def divide(a: int, b: int) -> int: return a // b` 는 `b=0` 이면 여전히 런타임에 터진다. 타입체커는 이걸 잡을 수 없다. 타입체커와 [6.1 pytest](#/pytest) 는 서로 다른 종류의 버그를 잡는, 상호 보완적인 도구다.
:::

## strict 모드가 실제로 켜는 것

지금까지 본 예제는 명백한 타입 불일치라서 **기본 모드**에서도 잡혔다. 하지만 대부분의 기존 코드는 이렇게 명백하지 않다. 다음 파일을 보자.

```python title="strict_demo.py — 얼핏 문제없어 보인다"
def parse(raw):
    data = raw.strip()
    return data.split(",")


def total(items):
    result = 0
    for item in items:
        result += item
    return result


values = parse("1,2,3")
print(total(values))
```

이 코드는 실제로 버그다. `parse` 는 문자열의 **리스트**를 반환하는데, `total` 은 그 원소들을 정수처럼 `+=` 로 더한다. 실행하면 어떻게 될까.

```pyrepl
>>> values = parse("1,2,3")
>>> total(values)
Traceback (most recent call last):
  ...
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

런타임에 바로 터진다. 그런데 기본 모드 pyright는 이 파일에 대해 뭐라고 할까.

```bash
$ uvx pyright strict_demo.py
```

```text nolines
0 errors, 0 warnings, 0 informations
```

**아무것도 못 잡는다.** 이유는 단순하다. `parse` 와 `total` 의 매개변수에 타입 어노테이션이 없다. 어노테이션이 없으면 pyright는 그 값의 타입을 암묵적으로 `Unknown` 취급하고, 기본 모드는 `Unknown` 이 섞인 코드에 대해 대부분의 검사를 건너뛴다. **타입 힌트가 없는 코드는 정적 검사기에게 투명 인간이다.** 안 보이니 검사할 게 없다.

이제 파일 맨 위에 한 줄만 추가해서 같은 파일을 strict 모드로 돌려 보자. pyright는 파일 단위 강제를 `# pyright: strict` 인라인 주석으로 켤 수 있다.

```python title="strict_demo.py — 맨 위에 한 줄 추가"
# pyright: strict
def parse(raw):
    ...
```

```bash
$ uvx pyright strict_demo.py
```

```text nolines
strict_demo.py:2:5 - error: Return type is unknown (reportUnknownParameterType)
strict_demo.py:2:11 - error: Type of parameter "raw" is unknown (reportUnknownParameterType)
strict_demo.py:2:11 - error: Type annotation is missing for parameter "raw" (reportMissingParameterType)
strict_demo.py:3:5 - error: Type of "data" is unknown (reportUnknownVariableType)
strict_demo.py:3:12 - error: Type of "strip" is unknown (reportUnknownMemberType)
strict_demo.py:4:12 - error: Type of "split" is unknown (reportUnknownMemberType)
strict_demo.py:4:12 - error: Return type is unknown (reportUnknownVariableType)
strict_demo.py:7:5 - error: Return type, "Unknown | Literal[0]", is partially unknown (reportUnknownParameterType)
strict_demo.py:7:11 - error: Type of parameter "items" is unknown (reportUnknownParameterType)
strict_demo.py:7:11 - error: Type annotation is missing for parameter "items" (reportMissingParameterType)
strict_demo.py:9:9 - error: Type of "item" is unknown (reportUnknownVariableType)
strict_demo.py:10:9 - error: Type of "result" is unknown (reportUnknownVariableType)
strict_demo.py:11:12 - error: Return type, "Unknown | Literal[0]", is partially unknown (reportUnknownVariableType)
13 errors, 0 warnings, 0 informations
```

에러 13개가 쏟아진다. **정작 진짜 버그(`str` 에 `+=` 로 정수를 더하려는 것)는 아직 하나도 안 나왔다.** strict 모드가 지금 잡은 건 전부 "타입을 안 적었다"는 지적이다. `reportUnknownParameterType`, `reportMissingParameterType`, `reportUnknownVariableType` — 이름을 보면 알겠지만 전부 **"모르겠다"**는 에러다. strict 모드의 정체가 여기서 드러난다.

::: deep strict 모드는 새로운 검사가 아니라 기준선을 바꾸는 것이다
기본 모드와 strict 모드는 서로 다른 검사 로직을 쓰지 않는다. **똑같은 추론 엔진**이 돈다. 차이는 "모르겠다"를 만났을 때의 태도다.

- 기본 모드: 타입을 모르면 조용히 `Any` 취급하고 넘어간다. `Any` 는 뭐든 될 수 있으니 아무 검사도 실패하지 않는다.
- strict 모드: 타입을 모르면 **그 자체를 에러로 보고한다.** 그리고 일단 모든 어노테이션이 갖춰지고 나면, 이번엔 그 타입들 사이의 불일치를 훨씬 깐깐하게 잡는다.

그래서 strict 모드로 가는 진짜 경로는 "에러 13개를 하나씩 지우는" 게 아니라, **먼저 어노테이션을 다 채우는 것**이다. 어노테이션이 갖춰지면 `Unknown` 계열 에러가 사라지고, 그제서야 진짜 로직 버그(`total` 이 문자열에 `+=` 를 시도하는 것)가 `reportOperatorIssue` 같은 이름으로 드러난다. 강제로 이 코드를 고쳐 보자.
:::

```python title="strict_demo.py — 어노테이션을 채운 버전"
def parse(raw: str) -> list[str]:
    data = raw.strip()
    return data.split(",")


def total(items: list[str]) -> int:
    result = 0
    for item in items:
        result += item  # 여기가 진짜 버그다
    return result
```

```bash
$ uvx pyright strict_demo.py
```

```text nolines
strict_demo.py:9:9 - error: Operator "+=" not supported for types "Literal[0]" and "str"
  Operator "+" not supported for types "Literal[0]" and "str" (reportOperatorIssue)
1 error, 0 warnings, 0 informations
```

이제서야 진짜 버그 하나가 정확히 짚힌다. **어노테이션이 없으면 진짜 버그가 `Unknown` 무더기에 파묻혀서 안 보인다.** 이게 strict 모드를 켜는 이유다 — 타입체커에게 검사할 재료를 주는 것이다.

mypy도 같은 이야기를 자기 방식대로 한다. 어노테이션 없는 첫 버전을 mypy 기본 모드로 돌리면.

```bash
$ uvx mypy strict_demo.py   # 어노테이션 없는 버전
```

```text nolines
Success: no issues found in 1 source file
```

mypy 기본 모드는 pyright 기본 모드보다도 관대하다. `--strict` 를 켜면.

```bash
$ uvx mypy --strict strict_demo.py   # 어노테이션 없는 버전
```

```text nolines
strict_demo.py:1: error: Function is missing a type annotation  [no-untyped-def]
strict_demo.py:6: error: Function is missing a type annotation  [no-untyped-def]
strict_demo.py:13: error: Call to untyped function "parse" in typed context  [no-untyped-call]
strict_demo.py:14: error: Call to untyped function "total" in typed context  [no-untyped-call]
Found 4 errors in 1 file (checked 1 source file)
```

똑같은 지적이다. mypy는 이걸 `no-untyped-def` 라는 하나의 에러 코드로 부르고, pyright는 몇 가지 리포트로 나눠 부른다. **이름은 다르지만 둘 다 "타입 정보가 없어서 검사를 못 한다"는 같은 사실을 말하고 있다.**

::: note mypy `--strict` 가 켜는 개별 플래그
`mypy --strict` 는 사실 `--disallow-untyped-defs`, `--disallow-any-generics`, `--warn-return-any`, `--no-implicit-optional` 등 십여 개 플래그를 한꺼번에 켜는 단축키다. `mypy -h` 실행 결과의 "strict mode" 절에 전체 목록이 나온다. pyright의 `# pyright: strict` 역시 `reportUnknownParameterType`, `reportMissingTypeArgument` 같은 개별 리포트 규칙들을 `error` 로 올리는 것에 불과하다 — [1.15 프로토콜](#/protocols)에서 본 "프로토콜은 새 기능이 아니라 기존 구조에 이름을 붙인 것"이라는 이야기와 비슷하게, strict 모드도 새 검사가 아니라 **기존 검사의 임계값**을 올리는 것이다.
:::

## 왜 두 검사기가 다른 말을 하나

`no-any-return` 이라는 에러 하나를 더 보자. `dict` 를 반환한다고 선언했는데 실제로는 `Any` 를 반환하는 흔한 상황이다.

```python title="check1.py"
import json


def load_config(path: str) -> dict[str, object]:
    with open(path) as f:
        return json.load(f)
```

```bash
$ uvx mypy check1.py            # 기본 모드
```

```text nolines
Success: no issues found in 1 source file
```

```bash
$ uvx mypy --strict check1.py
```

```text nolines
check1.py:6: error: Returning Any from function declared to return "dict[str, object]"
  [no-any-return]
Found 1 error in 1 file (checked 1 source file)
```

`json.load` 의 반환 타입은 표준 라이브러리 타입 스텁에 `Any` 로 정의돼 있다. 그 값을 그대로 `dict[str, object]` 라고 선언한 함수에서 반환하면, strict 모드는 **"당신이 그 값이 정말 dict인지 검증한 적이 없다"** 는 사실을 지적한다. `json.load` 가 실제로 리스트를 반환해도 코드는 이 시점까지 아무 저항 없이 통과했을 거란 뜻이다. 이런 종류의 에러는 pyright와 mypy가 **같은 파이썬 타입 시스템 명세**(PEP 484 계열)를 구현하지만 세부 추론 알고리즘과 표준 라이브러리 스텁 소스가 달라서, 잡아내는 순서나 메시지 문구가 달라진다. 어느 쪽이 "더 정확하다"는 절대적 기준은 없다 — 프로젝트 하나에는 **하나만** 골라 쓰는 게 맞다. 둘을 동시에 CI에 넣고 둘 다 통과시키려 하면, 한쪽만 아는 특이 케이스 때문에 영원히 끝나지 않는 술래잡기를 하게 된다.

::: tip 실무에서 어느 걸 고를까
- **pyright**: 추론이 더 적극적이고 속도가 빠르다(Node.js 기반, 증분 분석). VS Code의 Pylance가 이걸 그대로 쓴다. 에디터에서 실시간 피드백을 우선한다면 자연스러운 선택이다.
- **mypy**: 파이썬으로 작성됐고 커뮤니티 플러그인 생태계가 크다(Django, SQLAlchemy 전용 플러그인 등). 원조 격이라 PEP 논의와 가장 가깝게 맞물린다.
- 신규 프로젝트라면 pyright로 시작해서 에디터 경험을 먼저 얻고, CI에서는 pyright든 mypy든 **하나를 고정**해라. 이미 mypy 플러그인(예: `pydantic.mypy`)에 의존하는 프로젝트라면 mypy를 유지하는 게 낫다.
:::

## 기존 코드베이스에 점진적으로 도입하기

신규 프로젝트라면 처음부터 strict를 켜면 그만이다. 문제는 **이미 수만 줄이 있는 코드베이스**다. 어느 날 갑자기 strict를 켜면 에러가 수천 개 쏟아지고, 팀은 타입체커를 그냥 꺼 버린다. 그러면 도입은 실패한다. 점진적 도입의 핵심은 **"전부 다 아니면 전부 안 함"을 피하는 것**이다. 두 가지 축으로 나눠 생각한다.

### 축 1 — 디렉터리별 strictness

새 코드는 strict로, 기존 코드는 느슨하게 둔다. mypy는 `mypy.ini`(또는 `pyproject.toml`의 `[tool.mypy]`)에서 모듈 패턴별로 다른 설정을 줄 수 있다.

```ini title="mypy.ini"
[mypy]
warn_unused_ignores = True

[mypy-legacy.*]
ignore_errors = True

[mypy-new.*]
strict = True
```

`legacy/` 와 `new/` 각각에 파일을 하나씩 두고 확인해 보자.

```python title="legacy/legacy_mod.py — 타입 없는 옛날 코드"
def old_func(x):
    return x + 1
```

```python title="new/new_mod.py — 어노테이션 하나가 빠졌다"
def new_func(x: int) -> int:
    return x + 1


def other(y):
    return y
```

```bash
$ uvx mypy legacy new --config-file mypy.ini
```

```text nolines
new\new_mod.py:5: error: Function is missing a type annotation  [no-untyped-def]
Found 1 error in 1 file (checked 4 source files)
```

정확히 의도한 대로다. `legacy/` 안의 어노테이션 없는 함수는 `ignore_errors = True` 덕분에 완전히 무시되고, `new/` 안의 같은 실수는 strict 설정 때문에 바로 걸린다. **"이 디렉터리는 아직 옛날 코드다. 새로 짜는 코드만 엄격하게 본다"** 는 규칙을 설정 파일 몇 줄로 강제한 것이다. pyright는 같은 것을 `pyrightconfig.json` 의 `"executionEnvironments"` 로 표현한다 — 경로별로 `root` 와 `typeCheckingMode` 를 따로 지정할 수 있다.

### 축 2 — 파일별 무시

디렉터리 단위로도 안 되는 애매한 경계 파일이 있다. 그럴 땐 파일 맨 위에 한 줄을 넣는다.

```python title="mypy — 파일 전체 무시"
# mypy: ignore-errors
```

```python title="pyright — 파일 전체 무시"
# pyright: basic
```

또는 mypy `exclude` 옵션에 정규식 경로 목록을 올려서 특정 파일(자동 생성 코드, 서드파티 vendored 코드)을 아예 분석 대상에서 뺄 수도 있다.

```toml title="pyproject.toml"
[tool.mypy]
exclude = ["^migrations/", "^vendor/"]
```

::: cote 점진적 도입은 "게이트를 고정하는 것"이다
실전에서 잘 되는 방식은 이렇다. 오늘 시점의 에러 개수를 **베이스라인으로 고정**하고("현재 342개"), CI에서는 "베이스라인보다 늘어나면 실패"만 강제한다. mypy는 `--baseline` 을 직접 지원하지 않지만, pyright는 `--outputjson` 결과를 스크립트로 diff해서 같은 효과를 낼 수 있고, 서드파티 도구(`mypy-baseline` 등)도 있다. 핵심은 **"기존 부채는 당장 안 갚아도 되지만, 새 부채는 못 만들게 막는다"** 는 규칙이다. 리팩터링 문제에서 자주 나오는 "레거시 코드를 건드리지 않고 새 기능만 안전하게 추가하라"는 요구와 정확히 같은 모양이다.
:::

## `# type: ignore` 를 올바르게 쓰는 법

타입체커가 틀렸거나(서드파티 라이브러리의 스텁이 부정확한 경우), 지금 당장 고칠 여유가 없는 경우가 있다. 이럴 때 `# type: ignore` 로 그 줄만 넘어가게 할 수 있다. 그런데 이 주석을 아무렇게나 쓰면 **타입체커를 있으나 마나 하게 만든다.**

```python title="ignore_demo.py"
import json


def load_config(path: str) -> dict[str, object]:
    with open(path) as f:
        return json.load(f)  # type: ignore[no-any-return]  # json.load 는 Any를 반환한다


x: int = 5
y: int = 5  # type: ignore[assignment]  # 불필요한 ignore — 실제로는 오류가 없다
```

이 파일을 앞서 확인한 에러 코드까지 지정한 `--strict` 모드로, `--warn-unused-ignores` 를 붙여 돌려 보자.

```bash
$ uvx mypy --strict --warn-unused-ignores ignore_demo.py
```

```text nolines
ignore_demo.py:10: error: Unused "type: ignore" comment  [unused-ignore]
Found 1 error in 1 file (checked 1 source file)
```

6번째 줄의 ignore는 조용히 넘어갔다 — 실제로 `no-any-return` 에러가 있었고, 정확히 그 코드를 지정해서 억제했기 때문이다(이 줄의 ignore를 지우면 `Returning Any from function declared to return "dict[str, object]"` 에러가 실제로 뜬다는 걸 앞 절에서 확인했다). 반면 10번째 줄은 애초에 에러가 없는데 ignore를 붙였다. mypy는 이걸 **"불필요한 억제"** 로 잡아 준다.

이 결과에서 규칙 세 가지가 나온다.

1. **에러 코드를 명시해라.** `# type: ignore` 는 그 줄의 **모든** 에러를 삼킨다. `# type: ignore[no-any-return]` 처럼 구체적 코드를 쓰면, 나중에 코드가 바뀌어 **다른** 에러가 생겼을 때도 여전히 잡아낸다. 맨 처음 발견했던 에러만 정확히 봐준다.
2. **이유를 주석으로 남겨라.** "왜 이 타입 불일치가 안전한지"는 6개월 뒤의 당신도, 리뷰어도 모른다. `# json.load 는 Any를 반환한다` 처럼 한 줄이면 충분하다.
3. **`--warn-unused-ignores` (mypy) / `reportUnnecessaryTypeIgnoreComment`(pyright)를 CI에 켜 둬라.** 코드가 리팩터링되면서 억제하던 에러 자체가 사라지는 일이 흔하다. 그러면 그 ignore는 죽은 주석이 되고, 다음 사람이 "여기 뭔가 위험한 게 있나 보다"하고 잘못된 인상을 받는다. 이 검사가 그런 유령 주석을 걷어내 준다.

::: danger 벌거벗은 `# type: ignore` 를 습관으로 쓰지 마라
```python
result = risky_call()  # type: ignore
```

이건 "이 줄에서 나는 어떤 에러가 나든 상관 안 한다"는 뜻이다. `risky_call` 의 시그니처가 나중에 완전히 달라져서 전혀 다른 종류의 버그가 생겨도, 이 주석은 계속 침묵을 지킨다. 타입체커를 도입하는 의미 자체가 사라진다.
:::

## CI에 넣기 전에

이 절에서 로컬로 돌린 명령들 — `uvx pyright`, `uvx mypy --strict` — 은 그대로 CI 파이프라인의 한 단계가 된다. 로컬에서 통과한 코드가 CI에서도 통과해야 팀 전체가 같은 기준으로 일한다. **CI에 타입체크를 넣을 때 주의할 점 하나만 미리 말해 둔다.** 로컬 실행 환경(당신의 파이썬 버전, 설치된 패키지)과 CI 실행 환경이 다르면 같은 코드에도 다른 결과가 나올 수 있다. 그래서 `pythonVersion`, 의존성 버전을 pyright/mypy 설정 파일에 명시적으로 고정해야 한다. 구체적인 워크플로 작성과 매트릭스 테스트는 [6.6 CI/CD](#/ci)에서 다룬다.

## 요약

- 타입 힌트는 CPython 실행에 **아무 영향도 주지 않는다.** 검사는 pyright나 mypy 같은 별도 프로그램이 한다.
- 기본 모드는 어노테이션 없는 코드를 조용히 `Any`/`Unknown` 취급하고 넘어간다. **strict 모드는 그 "모르겠다"를 에러로 승격시킨다.**
- strict 모드가 처음 잡는 에러 대부분은 "타입을 안 적었다"는 지적이다. 어노테이션을 채운 뒤에야 진짜 로직 버그가 드러난다.
- pyright와 mypy는 같은 명세를 서로 다르게 구현한다. 프로젝트마다 **하나만** 골라 CI에 고정해라.
- 기존 코드베이스는 디렉터리별(`mypy-legacy.*` 패턴, pyright `executionEnvironments`) 또는 파일별 무시로 점진적으로 조인다.
- `# type: ignore` 는 반드시 **에러 코드를 명시**하고 **이유를 주석**으로 남긴다. `--warn-unused-ignores` 로 죽은 ignore를 걷어내라.

::: quiz 연습문제
1. 다음 함수에 pyright 기본 모드를 돌리면 에러가 몇 개 나올지 예측하고, 실제로 `uvx pyright` 로 확인하라. 그다음 `# pyright: strict` 를 추가하고 다시 돌려서 차이를 설명하라.

   ```python
   def build_url(host, port, path):
       return f"{host}:{port}{path}"
   ```

2. 아래 코드는 strict 모드에서 `reportOperatorIssue` 류의 에러를 낸다. 어떤 줄에서 무슨 에러가 날지 예측한 뒤 `uvx pyright --outputjson` 으로 실제 확인하라.

   ```python
   def average(nums: list[int]) -> float:
       return sum(nums) / len(nums)

   print(average([1, 2, "3"]))
   ```

3. 팀에 20,000줄짜리 타입 없는 코드베이스가 있다. 이번 스프린트에 새로 짜는 `billing/` 디렉터리만 strict로 강제하고 싶다. `mypy.ini` 설정을 작성하라. (힌트: 이 절의 `mypy.ini` 예제를 변형하면 된다.)

4. `# type: ignore` 와 `# type: ignore[에러코드]` 의 차이를 `--warn-unused-ignores` 관점에서 설명하라. 둘 중 어느 쪽이 코드가 바뀐 뒤 "죽은 ignore"를 더 잘 잡아내는가?

5. **깊이 생각해 볼 문제.** 타입체커가 통과해도 런타임 버그가 날 수 있는 이유를 [1.1 객체·이름·참조](#/objects-names)의 가변/불변 개념과 연결해서 설명하라. 힌트: 타입체커는 "이 값이 `list[int]` 라는 것"은 알아도, 그 리스트가 함수 실행 도중 **다른 코드에 의해 변경**될 수 있다는 것까지는 추적하지 못한다.
:::

**다음 절**: [2.9 런타임 타입 정보와 리플렉션](#/runtime-typing) — `get_type_hints`, `Annotated`, 그리고 어노테이션이 지연 평가되는 이유.
