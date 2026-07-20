# 2.9 런타임 타입 정보와 리플렉션

::: lead
지금까지 여덟 개 절 동안 타입 힌트를 열심히 써 왔다. 그런데 정작 "그 힌트가 실제로 어디에 저장되고, 파이썬 자신은 그걸 어떻게 다루는가"는 다루지 않았다. 이 절은 그 밑바닥을 연다. 타입 힌트가 런타임에 정말로 아무 일도 안 한다는 것을 직접 증명하고, 그럼에도 `__annotations__` 라는 딕셔너리에 저장된 그 정보를 FastAPI·pydantic 같은 라이브러리가 어떻게 훔쳐 써서 진짜 동작을 만들어내는지 본다. 그리고 [0.2절](#/install)에서 예고했던 것 — 파이썬 타입 시스템을 10년 넘게 괴롭힌 순환 참조 문제가 3.14에서 어떻게 풀렸는지 — 을 여기서 회수한다.
:::

## 증명: 타입 힌트는 런타임에 아무 일도 하지 않는다

말로만 하지 말고 직접 어겨 보자. 함수 하나를 정의하는데, 힌트를 전부 거짓말로 채운다.

```python title="wronghint.py — 힌트가 처음부터 끝까지 거짓말이다"
def add(a: int, b: int) -> int:
    return f"{a}-{b}"          # int라고 해놓고 str을 반환한다

result = add("hello", "world")  # int라고 해놓고 str을 넘긴다
print(result)
print(type(result))
```

실행하면 이렇다.

```text nolines
hello-world
<class 'str'>
```

**에러가 없다.** 경고조차 없다. `int` 라고 써 붙인 자리에 문자열이 태연히 들어가고, 함수는 끝까지 실행되고, 결과를 그대로 반환한다. 이게 파이썬 타입 힌트의 정체다. **주석이다. 조금 특별하게 저장되는 주석일 뿐, 인터프리터는 그 내용을 검사하지 않는다.**

::: warn 타입 힌트는 실행되지 않고, 강제되지도 않는다
CPython의 바이트코드 컴파일러는 어노테이션을 **평가는 하되(또는 나중에 평가하도록 미루되) 아무 곳에도 검사 코드를 심지 않는다.** `def f(x: int)` 를 컴파일한 바이트코드에는 "x가 int인지 확인하라"는 명령이 단 한 줄도 없다. 어노테이션은 그냥 어딘가에 저장됐다가, **누군가 일부러 꺼내서 검사할 때만** 의미를 갖는다.

이 절의 나머지는 전부 그 "누군가"가 어떻게 꺼내는가에 대한 이야기다.
:::

그럼 아까 [2.8 mypy와 pyright 실전](#/typecheckers)에서 봤던 그 도구들은 뭘 검사한 걸까? 같은 파일을 실제로 돌려 본다.

```bash
uvx pyright wronghint.py
```

```text nolines
c:\...\wronghint.py:2:12 - error: Type "str" is not assignable to return type "int"
    "str" is not assignable to "int" (reportReturnType)
c:\...\wronghint.py:4:14 - error: Argument of type "Literal['hello']" cannot be assigned to parameter "a" of type "int" in function "add"
    "Literal['hello']" is not assignable to "int" (reportArgumentType)
c:\...\wronghint.py:4:23 - error: Argument of type "Literal['world']" cannot be assigned to parameter "b" of type "int" in function "add"
    "Literal['world']" is not assignable to "int" (reportArgumentType)
3 errors, 0 warnings, 0 informations
```

`mypy` 도 같은 지점을 잡는다.

```bash
uvx mypy wronghint.py
```

```text nolines
wronghint.py:2: error: Incompatible return value type (got "str", expected "int")  [return-value]
wronghint.py:4: error: Argument 1 to "add" has incompatible type "str"; expected "int"  [arg-type]
wronghint.py:4: error: Argument 2 to "add" has incompatible type "str"; expected "int"  [arg-type]
Found 3 errors in 1 file (checked 1 source file)
```

**pyright와 mypy는 파이썬을 실행하지 않는다.** 소스 코드를 텍스트로 읽고, 어노테이션을 파싱해서 자기들만의 타입 추론 엔진으로 검사한 뒤 끝낸다. 실제 `python wronghint.py` 를 돌리는 인터프리터는 이 검사 결과를 전혀 모른다. 두 세계는 **완전히 분리**돼 있다. 이 분리가 이 절 전체를 관통하는 전제다.

## `__annotations__` 을 직접 열어보기

그러면 힌트는 어디로 갔을까? 사라지지 않았다. 함수 객체의 속성으로 저장된다.

```pyrepl
>>> def add(a: int, b: int) -> int:
...     return a + b
...
>>> add.__annotations__
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
>>> type(add.__annotations__)
<class 'dict'>
```

매개변수 이름을 키로, 힌트 객체를 값으로 담은 평범한 딕셔너리다. `int` 라는 문자열이 아니라 `int` **클래스 객체 자체**가 들어 있다는 걸 눈여겨봐라 — 이게 뒤에서 순환 참조 이야기와 직결된다.

클래스, 모듈 레벨 변수도 똑같이 어노테이션을 남긴다.

```pyrepl
>>> class Point:
...     x: int
...     y: int = 0
...
>>> Point.__annotations__
{'x': <class 'int'>, 'y': <class 'int'>}
```

`Point.__annotations__` 에는 `x` 도 들어 있다. `x: int` 는 값 대입이 없으니 클래스 속성으로는 존재하지 않지만, **어노테이션으로는 남는다.** 이 딕셔너리 하나가 [2.6 dataclasses](#/dataclasses)의 `@dataclass` 가 필드 목록을 알아내는 방법이고, [2.5 TypedDict](#/typed-containers)가 스키마를 구성하는 방법이다. 전부 이 딕셔너리를 읽는 것에서 시작한다.

### 3.14의 배후 사정: `__annotate__`

여기서 3.14 고유의 사실 하나. `add.__annotations__` 를 조회하면 마치 미리 계산된 딕셔너리를 꺼내오는 것처럼 보이지만, 실제로는 **그 순간에 계산된다.** 함수 객체는 진짜로는 `__annotate__` 라는 콜러블을 들고 있고, `__annotations__` 접근은 이걸 호출해서 딕셔너리를 만들어낸다.

```pyrepl
>>> add.__annotate__
<function add.__annotate__ at 0x000002D194113740>
>>> import annotationlib
>>> add.__annotate__(annotationlib.Format.VALUE)
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

`annotationlib.Format` 에는 몇 가지 모드가 있다. `VALUE` 는 실제 객체로, `STRING` 은 소스에 쓰인 그대로의 문자열로 어노테이션을 만들어낸다. 다만 `__annotate__` 를 직접 호출할 때는 `VALUE` 모드만 함수 스스로 구현하고 있고, 나머지 모드는 `annotationlib.get_annotations()` 를 거쳐야 한다.

```pyrepl
>>> annotationlib.get_annotations(add, format=annotationlib.Format.VALUE)
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
>>> annotationlib.get_annotations(add, format=annotationlib.Format.STRING)
{'a': 'int', 'b': 'int', 'return': 'int'}
```

`STRING` 모드는 **실제 이름을 평가하지 않고** 소스 텍스트만 재구성한다. 어노테이션에 아직 존재하지 않는 이름이 있어도 안전하게 조회할 수 있다는 뜻이다. IDE의 자동완성이나 문서 생성 도구가 이 모드를 쓴다.

::: deep 왜 함수 하나가 두 가지 방식으로 어노테이션을 보여주는가
과거(3.13 이하) CPython은 함수를 정의하는 순간 어노테이션 표현식을 **즉시 평가**해서 딕셔너리 하나를 만들어 `__annotations__` 에 박아 놓았다. 함수가 정의될 때 단 한 번 계산되고 끝이었다.

3.14는 다르다. 컴파일러는 어노테이션을 평가하는 코드를 **별도의 작은 함수**(`__annotate__`)로 컴파일해 두고, 함수 정의 시점에는 실행하지 않는다. 누군가 `__annotations__` 에 처음 접근하는 순간에야 그 함수가 호출되고, 결과는 캐시된다. **평가 시점이 "정의될 때"에서 "처음 조회될 때"로 미뤄진 것**이다. 이게 [1.10 함수](#/functions)에서 본 "함수 객체는 코드 객체를 감싼 껍데기"라는 그림에 어노테이션 계산용 코드 객체가 하나 더 딸려 오게 됐다는 뜻이기도 하다.

바로 이 지연(lazy) 평가가 PEP 649/749의 핵심이고, 다음 절에서 왜 이게 필요했는지 본다.
:::

## PEP 563 → 649/749: 세 번 바뀐 이유

파이썬 어노테이션의 평가 시점은 이 책이 다루는 어떤 기능보다도 파란만장한 역사를 갖고 있다. 왜 이렇게 여러 번 바뀌었는지 알아야 지금 동작을 제대로 이해할 수 있다.

```text nolines
2006  PEP 3107   함수 어노테이션 문법 도입. 의미는 정하지 않음 (그냥 표현식)
2014  PEP 484    typing 모듈. 어노테이션을 "타입 힌트"로 쓰자는 관례 확립
2017  PEP 526    변수 어노테이션 (x: int) 추가
2017  PEP 563    지연 평가 opt-in: from __future__ import annotations
2020  3.10 계획   563을 언어 기본값으로 만들 예정이었음
2021  3.10 실제   보류. 런타임에 실제 타입이 필요한 라이브러리들이 깨짐
2023  PEP 649/749  진짜 지연 평가 채택 (문자열이 아니라 콜러블로 미룬다)
2025  3.14       649/749가 새 기본 동작
```

### 왜 지연 평가가 필요했나 — 3.13 이전의 진짜 골칫거리

3.13까지는 어노테이션이 함수/클래스가 **정의되는 바로 그 줄**에서 평가됐다. 그런데 클래스 안에서 자기 자신이나 아직 정의 안 된 다른 클래스를 가리키고 싶은 경우가 흔하다.

```python title="3.13 이전이라면 NameError가 났을 코드"
class Node:
    def __init__(self, value: int, next: Node = None):  # 자기 자신을 가리킴
        self.value = value
        self.next = next
```

`class Node` 의 몸통을 실행하는 시점에는 아직 이름 `Node` 가 완성되지 않았다. 예전 파이썬은 이걸 그 자리에서 즉시 평가하려 했으므로 `NameError: name 'Node' is not defined` 가 났다. 그래서 오랫동안 관용구는 **어노테이션을 문자열로 감싸는 것**이었다.

```python
def __init__(self, value: int, next: "Node" = None):  # 따옴표로 감싼 forward reference
```

이건 동작은 하지만 볼품없고, 오타를 내도 알아채기 어렵다. PEP 563은 `from __future__ import annotations` 를 파일 맨 위에 넣으면 **파일 안의 모든 어노테이션을 컴파일 시점에 자동으로 문자열로 바꿔주는** opt-in 기능이었다. 직접 실행해서 확인해 보자.

```python title="pep563.py"
from __future__ import annotations

def add(a: int, b: int) -> int:
    return a + b

print(add.__annotations__)
print(type(list(add.__annotations__.values())[0]))
```

```text nolines
{'a': 'int', 'b': 'int', 'return': 'int'}
<class 'str'>
```

`int` 클래스가 아니라 **문자열** `'int'` 가 저장된다. 파이썬 3.14에서 이 `__future__` 임포트는 여전히 동작한다 — 하위 호환을 위해 남겨 뒀다.

이걸 파이썬의 기본 동작으로 만들려던 게 3.10 계획이었는데, **보류됐다.** 이유는 명확했다. 어노테이션을 문자열로만 저장해 버리면, **런타임에 진짜 타입 객체가 필요한 코드**(pydantic v1, 오래된 FastAPI 버전, 리플렉션 기반 ORM 등)가 전부 문자열을 다시 파싱하고 `eval` 해야 하는 처지가 됐다. 그것도 그 이름이 정의된 정확한 스코프를 재현해야 하는데, 데코레이터가 여러 겹 씌워진 함수라면 그 스코프 추적 자체가 깨지기 쉬웠다.

### PEP 649/749: 문자열이 아니라 "미룬 함수"

3.14가 채택한 해법은 다르다. 어노테이션을 **문자열로 바꾸는 대신, 평가를 함수로 감싸서 미룬다.** 방금 본 `__annotate__` 가 그 함수다. 이러면 두 마리 토끼를 다 잡는다.

- **진짜 타입 객체가 필요하면** `__annotations__` 을 조회한다 — `__annotate__` 가 그 순간 실행되어 실제 클래스를 돌려준다.
- **아직 존재하지 않는 이름을 가리켜도 괜찮다** — 함수가 정의되는 시점에는 그 안의 코드가 실행되지 않으니까.

이제 아까 봤던 순환 참조 문제로 돌아가자.

## 순환 참조가 드디어 풀리다

3.14에서는 따옴표 없이 그냥 써도 된다.

```python title="circular.py — 따옴표 없이 서로를 가리킨다"
class Node:
    def __init__(self, value: int, parent: Tree = None):   # Tree는 아직 정의 안 됨
        self.value = value
        self.parent = parent

class Tree:
    def __init__(self, root: Node):
        self.root = root

print("모듈 로드 성공 (NameError 없음)")
print(Node.__init__.__annotations__)

import typing
print(typing.get_type_hints(Node.__init__))
```

```text nolines
모듈 로드 성공 (NameError 없음)
{'value': <class 'int'>, 'parent': <class '__main__.Tree'>}
{'value': <class 'int'>, 'parent': <class '__main__.Tree'>}
```

`Node` 를 정의하는 줄에서 `Tree` 는 아직 존재하지 않는다. 그런데도 모듈은 끝까지 로드된다. 비결은 순서다. **`Node.__init__.__annotations__` 을 조회하는 시점은 모듈 맨 아래, 두 클래스가 전부 정의되고 난 뒤다.** 그때 `__annotate__` 가 처음 실행되면서 `parent` 자리의 `Tree` 를 전역 이름 공간에서 찾는데, 그 시점에는 이미 `Tree` 가 존재하므로 곧바로 **진짜 클래스 객체**로 채워진다. `get_type_hints()` 도 같은 결과를 준다 — 여기서는 애초에 문자열로 물러날 이유가 없었다.

이게 이 절에서 가장 중요한 실험이다. **"평가를 미룬다"는 게 정확히 무슨 뜻인지 완전히 없어진 이름으로 확인해 보자.**

```python title="undefined_ref.py — 아예 존재하지 않는 이름"
def f(x: DoesNotExist) -> None:
    pass

print("함수 정의 성공 - 아직 에러 없음")
print(f.__annotations__)   # 여기서 처음 평가된다
```

```text nolines
함수 정의 성공 - 아직 에러 없음
Traceback (most recent call last):
  ...
  File "undefined_ref.py", line 1, in __annotate__
    def f(x: DoesNotExist) -> None:
             ^^^^^^^^^^^^
NameError: name 'DoesNotExist' is not defined
```

**함수 정의는 성공한다.** `DoesNotExist` 라는 이름은 인터프리터가 아는 한 세상 어디에도 없는데도 그렇다. 에러는 `__annotations__` 을 **처음으로 조회하는 그 줄**에서, `__annotate__` 내부에서 터진다. 이게 "지연 평가"의 진짜 의미다. **에러가 사라진 게 아니라, 에러가 날 수 있는 시점이 뒤로 미뤄진 것.** `Node`/`Tree` 예제가 통했던 이유는, 어노테이션을 조회하는 시점(모듈이 다 로드된 뒤)에는 `Tree` 가 이미 존재했기 때문이다. 순서만 맞으면 순환은 더 이상 문제가 아니다.

::: hist 왜 굳이 이렇게까지 복잡하게 만들었나
가장 쉬운 해법은 "그냥 항상 문자열로 저장하자"(PEP 563을 기본값으로)였다. 그런데 이건 **정보를 잃는다.** 문자열 `'Tree'` 만 갖고는 그게 지금 스코프에서 어떤 `Tree` 를 가리키는지 다시 찾아야 하고, `eval()` 로 재평가하려면 그 코드가 정의됐을 때의 지역/전역 스코프를 통째로 들고 있어야 한다. 데코레이터를 씌우거나 `exec` 로 동적 생성된 코드에서는 이 스코프 복원이 종종 실패한다.

PEP 649/749의 접근은 **컴파일러가 애초에 스코프를 캡처한 함수(`__annotate__`)를 만들어 두는 것**이다. 클로저처럼, 정의 시점의 스코프를 그대로 들고 다닌다. 그래서 늦게 호출해도 정확한 이름 해석이 보장된다. 문자열로 뭉개는 것보다 훨씬 견고하지만, 그만큼 CPython 컴파일러와 함수 객체 구조에 손을 대야 했다 — 그래서 PEP 하나가 아니라 649(메커니즘)와 749(세부 보정)로 나뉘어 여러 해에 걸쳐 다듬어졌다.
:::

## `get_type_hints()`: 무엇이든 실제 타입으로

`__annotations__` 을 직접 읽는 것과 `typing.get_type_hints()` 를 쓰는 것은 다르다. 방금 순환 참조 예제에서 이미 그 차이를 봤다. 정리하면 이렇다.

| | `__annotations__` | `get_type_hints()` |
| --- | --- | --- |
| 반환 형태 | `__annotate__` 이 만든 그대로 (문자열일 수도, 클래스일 수도) | 항상 **해석된 실제 타입 객체** |
| forward reference 처리 | 안 함 | 이름 공간을 뒤져서 실제 이름을 찾아 대입 |
| `Optional[X]` 처리 | 그대로 | 동일 |
| `None` 어노테이션 | `None` | `NoneType` 으로 정규화 |
| 상속받은 메서드 | 그 함수 자체 것만 | 부모 클래스 어노테이션까지 병합 |

`get_type_hints()` 가 하는 일은 본질적으로 **"문자열이든 뭐든 갖고 와서, 그 함수/클래스가 정의된 모듈의 전역/지역 이름 공간을 기준으로 실제 객체를 찾아 대입하라"** 는 것이다. `from __future__ import annotations` 를 쓴 파일에서도 잘 동작하는 이유가 이거다 — 문자열이 되어 있어도 어차피 다시 이름 공간에서 찾아 준다.

```pyrepl
>>> from typing import Annotated, get_type_hints
>>> def get_user(user_id: Annotated[int, "primary key", "positive"]) -> None:
...     pass
...
>>> get_type_hints(get_user)
{'user_id': <class 'int'>, 'return': <class 'NoneType'>}
```

여기서 `Annotated[int, ...]` 의 메타데이터(`"primary key"`, `"positive"`)가 **사라졌다.** 기본 동작은 부가 정보를 벗겨내고 알맹이 타입만 준다. 메타데이터까지 필요하면 `include_extras=True` 를 명시해야 한다.

```pyrepl
>>> get_type_hints(get_user, include_extras=True)
{'user_id': typing.Annotated[int, 'primary key', 'positive'], 'return': <class 'NoneType'>}
```

## `Annotated`: 타입에 짐을 실어 보내기

`Annotated[X, meta1, meta2, ...]` 는 "이 값의 타입은 `X` 이고, 덤으로 이런 부가 정보도 붙어 있다"는 뜻이다. 정적 검사기는 `X` 만 보고 `meta` 들은 완전히 무시한다. 그런데 그 무시당하는 `meta` 자리가 바로 **런타임 라이브러리들이 진짜 동작을 얹는 자리**다.

FastAPI가 `Annotated[int, Query(gt=0)]` 로 "이 정수는 쿼리 파라미터이고 0보다 커야 한다"를 표현하는 방식이 정확히 이거다. pydantic v2의 `Annotated[str, Field(max_length=10)]` 도 마찬가지다. 라이브러리는 함수 시그니처를 [1.10 함수](#/functions)에서 본 `inspect` 나 `get_type_hints(include_extras=True)` 로 들여다보고, `Annotated` 의 두 번째 이후 원소들을 자기만의 규칙으로 해석해서 검증 코드를 만들어낸다.

간단한 버전을 직접 만들어서 이게 어떻게 동작하는지 보자.

```python title="Annotated 메타데이터로 런타임 검증 만들기"
from typing import Annotated, get_type_hints, get_args, get_origin
import functools

class Range:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi
    def __repr__(self):
        return f"Range({self.lo}, {self.hi})"

def validate(func):
    hints = get_type_hints(func, include_extras=True)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound = dict(zip(func.__code__.co_varnames, args))
        bound.update(kwargs)
        for name, hint in hints.items():
            if get_origin(hint) is Annotated:
                base, *metas = get_args(hint)
                for meta in metas:
                    if isinstance(meta, Range) and name in bound:
                        val = bound[name]
                        if not (meta.lo <= val <= meta.hi):
                            raise ValueError(f"{name}={val} 는 {meta} 범위를 벗어남")
        return func(*args, **kwargs)
    return wrapper

@validate
def set_volume(level: Annotated[int, Range(0, 100)]) -> None:
    print("volume set:", level)

set_volume(50)          # 통과
set_volume(150)         # ValueError
```

```text nolines
volume set: 50
Traceback (most recent call last):
  ...
ValueError: level=150 는 Range(0, 100) 범위를 벗어남
```

`get_type_hints(func, include_extras=True)` 로 `Annotated` 를 벗기지 않고 통째로 받은 뒤, `get_origin`/`get_args` 로 알맹이 타입과 메타데이터를 분리해서 `Range` 인스턴스만 골라 검사했다. FastAPI, typer, pydantic이 데코레이터·모델 생성 시점에 하는 일이 규모만 다를 뿐 원리는 이것과 같다. **타입 힌트 자리에 "타입 검사기를 위한 타입"과 "런타임 라이브러리를 위한 메타데이터"를 동시에 실어 보낼 수 있다** — 이게 `Annotated` 가 존재하는 이유다.

::: cote 코딩테스트에서는 왜 안 쓰나
경쟁 프로그래밍 코드에서 `Annotated` 나 정교한 타입 힌트를 볼 일은 거의 없다. 시간 제한 안에 정답을 내는 게 유일한 목표라 이런 인프라는 오버헤드일 뿐이다. 다만 **면접 코딩 테스트**나 **팀 과제형 문제**에서는 이야기가 다르다. 함수 시그니처만 보고도 입력 범위·불변식을 알 수 있게 `Annotated[int, "1 <= n <= 10**5"]` 처럼 주석 대신 써 두면 리뷰어에게 좋은 인상을 준다.
:::

## `dir()`과 `inspect`: 어노테이션 너머의 리플렉션

이 절의 마지막으로, 어노테이션 외에 런타임에 타입 정보를 캐낼 수 있는 다른 통로도 짚고 간다. `get_type_hints()` 는 어노테이션만 본다. 실제로 객체가 **무엇을 할 수 있는지**까지 알고 싶으면 [1.15 프로토콜](#/protocols)에서 다룬 구조적 검사나, `inspect.signature()` 로 얻는 시그니처 객체를 함께 써야 한다.

```pyrepl
>>> import inspect
>>> def greet(name: str, *, loud: bool = False) -> str:
...     return name.upper() if loud else name
...
>>> sig = inspect.signature(greet)
>>> sig.parameters['loud'].default
False
>>> sig.parameters['loud'].annotation
<class 'bool'>
```

`inspect.signature()` 는 `__annotations__` 뿐 아니라 기본값, 위치 전용/키워드 전용 구분, `*args`/`**kwargs` 까지 한 번에 담은 객체를 준다. [1.10 함수](#/functions)에서 본 다섯 구역짜리 시그니처 구조가 여기 그대로 반영돼 있다. FastAPI가 라우트 함수의 파라미터 목록을 뽑아낼 때, `functools.singledispatch`(→ [3.1 functools](#/functools))가 등록된 타입을 확인할 때 전부 이 조합을 쓴다.

## 요약

- 타입 힌트는 **런타임에 아무것도 검사하지 않는다.** 틀린 힌트를 준 함수도 그대로 실행된다 — 직접 확인했다.
- 정적 검사기(pyright, mypy)는 파이썬 인터프리터와 완전히 분리된 별도 프로그램이다. 소스를 읽고 자기 타입 추론기로 검사할 뿐, 실행 중인 파이썬은 그 결과를 모른다.
- 어노테이션은 함수·클래스 객체의 `__annotations__` 딕셔너리에 저장된다. 3.14부터는 `__annotate__` 라는 콜러블이 이 딕셔너리를 **처음 조회하는 시점에** 만들어낸다 — 지연 평가.
- PEP 563(opt-in 문자열화) → 3.10 기본값 시도 실패 → PEP 649/749(콜러블로 미루기, 3.14 기본)로 세 단계를 거쳤다. 정보를 잃지 않으면서 지연을 구현하기 위해서였다.
- 지연 평가 덕분에 아직 정의되지 않은 이름을 따옴표 없이 어노테이션에 써도 된다 — **에러가 사라진 게 아니라 조회 시점으로 미뤄진 것**이다. 순서만 맞으면 순환 참조는 더 이상 문제가 아니다.
- `typing.get_type_hints()` 는 문자열이든 뭐든 실제 이름 공간에서 찾아 진짜 타입 객체로 바꿔 준다. `include_extras=True` 없이는 `Annotated` 의 메타데이터가 벗겨진다.
- `Annotated[X, meta...]` 는 정적 검사기에는 `X` 만 보이고, 런타임 라이브러리(FastAPI, pydantic)는 `meta` 를 읽어 검증·직렬화 규칙을 만든다.

::: quiz 연습문제
1. 다음 코드는 3.13 이전이라면 `NameError` 가 났다. 3.14에서는 왜 되는지, `__annotate__` 개념을 써서 설명하라.

   ```python
   class A:
       def link(self, other: B) -> None: ...

   class B:
       pass
   ```

2. 위 코드에서 `class B` 를 **지우면** 어떤 일이 벌어지는가? 언제(어느 줄에서) 에러가 나는지 예측하고 실행해서 확인하라.

3. `get_type_hints(f)` 와 `f.__annotations__` 이 다른 값을 줄 수 있는 상황을 하나 만들어라. 힌트: `from __future__ import annotations` 또는 forward reference 문자열을 써라.

4. 다음 함수에 `Annotated` 를 이용해 "이 매개변수는 짝수여야 한다"는 제약을 표현하고, 이를 검사하는 데코레이터를 짜라.

   ```python
   def half(n: int) -> int:
       return n // 2
   ```

5. 일부러 틀린 타입 힌트를 가진 함수를 하나 짜고, `uvx pyright` 또는 `uvx mypy` 로 실제 에러 메시지를 받아 본 뒤, 그 함수가 여전히 정상 실행되는지 확인하라.
:::

**다음 절**: [3.1 일급 함수와 functools](#/functools) — 함수도 객체라는 사실이 `partial`, `reduce`, `lru_cache` 로 어떻게 이어지는가.
