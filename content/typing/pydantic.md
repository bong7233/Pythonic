# 2.7 attrs와 pydantic v2

::: lead
[2.6 dataclasses](#/dataclasses)에서 본 `@dataclass` 는 타입 힌트를 붙여 주지만, 그 힌트가 실제로 지켜지는지는 아무도 검사하지 않는다. 파일을 읽어 온 JSON, 사용자가 입력한 폼, 외부 API가 준 응답 — 이런 것들은 애초에 "타입이 맞는 데이터"라는 보장이 없다. 그 경계에서 필요한 건 정적 힌트가 아니라 **런타임 검증**이다. pydantic은 그 검증을 데이터가 들어오는 순간 실제로 수행하고, 필요하면 변환까지 해 주는 라이브러리다. 이 절에서는 dataclass와 pydantic이 근본적으로 다른 층위의 도구라는 것, 그리고 pydantic v2가 왜 빨라졌는지를 직접 확인한다.
:::

## dataclass와 pydantic은 다른 문제를 푼다

먼저 사실 하나를 직접 확인하자. **타입 힌트는 런타임에 아무 영향이 없다.** [1.10 함수](#/functions)에서 함수 어노테이션을 다뤘지만, 그 어노테이션이 강제되는지는 다루지 않았다. 지금 확인한다.

```python title="typehint_noop.py"
def add(a: int, b: int) -> int:
    return a + b


print(add("hello", "world"))       # 문자열을 넣어도 그냥 실행된다
print(add.__annotations__)
```

```text nolines
helloworld
{'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

에러가 안 난다. `int` 라고 써 놓은 자리에 문자열을 넣어도 파이썬 인터프리터는 신경 쓰지 않는다. 어노테이션은 `__annotations__` 딕셔너리에 저장되는 **메타데이터**일 뿐, 실행 경로에 어떤 검사 코드도 끼워 넣지 않는다. `@dataclass` 도 마찬가지다.

```python title="dataclass_noop.py"
from dataclasses import dataclass


@dataclass
class UserDC:
    name: str
    age: int


u = UserDC(name="Alice", age="twenty-five")   # age에 문자열
print(u)
print(type(u.age))
```

```text nolines
UserDC(name='Alice', age='twenty-five')
<class 'str'>
```

`age` 자리에 문자열이 그대로 들어가 앉았다. `@dataclass` 가 만들어 주는 `__init__` 은 그냥 `self.age = age` 를 실행할 뿐, 타입을 확인하는 코드는 단 한 줄도 없다. 대신 이 실수는 정적 검사기가 잡는다.

```bash
uvx pyright dataclass_noop.py
```

```text nolines
error: Argument of type "Literal['twenty-five']" cannot be assigned to
       parameter "age" of type "int" in function "__init__"
  "Literal['twenty-five']" is not assignable to "int" (reportArgumentType)
1 error, 0 warnings, 0 informations
```

이게 정확히 dataclass의 계약이다. **"당신이 이 타입으로 코드를 짰다면, 그 부분은 pyright가 검사해 준다. 하지만 그 값이 실제로 그 타입인지는 실행 시점에 아무도 보장하지 않는다."** 이 계약은 코드베이스 내부에서는 문제가 없다. 함수를 호출하는 다른 코드도 같은 pyright 검사를 통과했을 테니까. 문제는 **경계**에서 터진다. `request.json()`, `yaml.safe_load()`, `os.environ`, 외부 API 응답 — 이것들은 pyright가 본 적 없는 데이터다. 파이썬 실행기 입장에서는 그냥 `dict[str, Any]` 다.

pydantic은 바로 이 경계를 위한 도구다. **선언한 타입을 실행 시점에 실제로 검사하고, 가능하면 변환한다.**

## BaseModel — 기본 사용

```python title="basic_model.py"
from pydantic import BaseModel


class User(BaseModel):
    name: str
    age: int


u1 = User(name="Alice", age=25)
print(u1)

u2 = User(name="Bob", age="25")       # 문자열 "25"를 넣었다
print(u2)
print(type(u2.age))
```

```text nolines
name='Alice' age=25
name='Bob' age=25
<class 'int'>
```

`age="25"` 를 넣었는데 결과는 `age=25`, 타입은 `int` 다. dataclass처럼 값을 그대로 통과시킨 게 아니라, **파싱해서 변환**했다. 이걸 pydantic은 "coercion(강제 변환)"이라 부른다. 문자열 `"25"` 는 정수로 파싱 가능하니 통과시킨 것이다. 반면 파싱이 불가능한 값은 그대로 통과하지 않는다.

## ValidationError — 실제로 터뜨려 본다

```python title="validation_error.py"
from pydantic import BaseModel, ValidationError


class User(BaseModel):
    name: str
    age: int


try:
    User(name="Carol", age="twenty-five")   # 정수로 파싱 불가능
except ValidationError as e:
    print(e)
```

```text nolines
1 validation error for User
age
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='twenty-five', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/int_parsing
```

이게 dataclass와의 결정적 차이다. dataclass는 이 상황에서 **조용히 통과시키고 나중에 어딘가에서 터진다.** pydantic은 **경계에서 즉시, 명시적으로** 터뜨린다. `ValidationError` 는 예외 하나가 아니라 **에러 목록**을 들고 있다. 필드 하나가 아니라 여러 필드가 동시에 잘못됐을 때 한 번에 전부 보여 주기 위해서다.

```python title="multiple_errors.py"
try:
    User(name=123, age="twenty-five")
except ValidationError as e:
    print(f"에러 개수: {e.error_count()}")
    for err in e.errors():
        print(f" - {err['loc']}: {err['msg']}")
```

```text nolines
에러 개수: 2
 - ('name',): Input should be a valid string
 - ('age',): Input should be a valid integer, unable to parse string as an integer
```

::: note pydantic v2에서 `name=123` 도 에러다 — coercion은 방향이 있다
직접 실행해 보면 `name` 필드도 에러가 뜬다. `int` 를 넣었는데 `str` 로 자동 변환해 주지 않고 `'Input should be a valid string'` 으로 그대로 실패한다. pydantic v2의 **lax 모드**(기본값)가 허용하는 강제 변환은 방향이 정해져 있다 — `str`/`bool` → `int`, `str` → `float` 처럼 "덜 구체적인 표현을 더 구체적인 타입으로" 파싱하는 쪽은 허용하지만, 그 반대인 `int` → `str` 변환은 하지 않는다. 애초에 앞의 `age="25"` 예제가 통과한 것도 문자열 숫자를 `int` 로 파싱한 것이지, 아무 타입이나 서로 넘나든 게 아니다. 이 방향성을 뒤집어 아예 강제 변환 자체를 끄고 싶으면(문자열 필드에 숫자·불리언이 들어오는 것도 막고 싶으면) `model_config = ConfigDict(strict=True)` 또는 필드에 `Field(strict=True)` 를 쓴다. "느슨하게 받고 정확하게 변환"이 기본 철학이고, 웹 폼이나 쿼리 파라미터처럼 **모든 값이 일단 문자열로 들어오는** 환경을 염두에 둔 설계다.
:::

## 커스텀 검증자

필드 하나만으로 표현 안 되는 규칙 — "비밀번호와 확인란이 같아야 한다", "나이는 14세 이상이어야 한다" — 은 검증자 함수로 추가한다.

```python title="custom_validators.py"
from pydantic import BaseModel, ValidationError, field_validator, model_validator


class SignupForm(BaseModel):
    username: str
    password: str
    password_confirm: str
    age: int

    @field_validator("username")
    @classmethod
    def username_must_be_alnum(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("username은 영문/숫자만 허용한다")
        return v

    @field_validator("age")
    @classmethod
    def age_must_be_adult(cls, v: int) -> int:
        if v < 14:
            raise ValueError("14세 미만은 가입할 수 없다")
        return v

    @model_validator(mode="after")
    def passwords_must_match(self) -> "SignupForm":
        if self.password != self.password_confirm:
            raise ValueError("password와 password_confirm이 일치하지 않는다")
        return self


try:
    SignupForm(username="hong!!", password="abc123", password_confirm="xyz789", age=10)
except ValidationError as e:
    print(f"에러 개수: {e.error_count()}")
    for err in e.errors():
        print(f" - {err['loc']}: {err['msg']}")
```

```text nolines
에러 개수: 2
 - ('username',): Value error, username은 영문/숫자만 허용한다
 - ('age',): Value error, 14세 미만은 가입할 수 없다
```

두 가지를 눈여겨봐라. `@field_validator` 는 **필드 하나**를 검사한다 — 클래스 메서드처럼 정의하고 `@classmethod` 를 반드시 같이 붙인다 (인스턴스가 아직 완성되지 않은 시점에 호출되기 때문이다). `@model_validator(mode="after")` 는 **모든 필드가 개별 검증을 통과한 뒤** 인스턴스 전체를 받아 필드 간 관계를 검사한다. `password_confirm` 이 틀렸다는 에러는 안 뜬 걸 확인해라 — `mode="after"` 검증자는 개별 필드 검증(`username`, `age`)이 실패해도 **일단 다 시도한 뒤** 실행되지 않고, 개별 검증에 실패한 필드가 있으면 모델 검증기는 아예 건너뛴다. 여기서는 `username` 과 `age` 만 실패했으므로 정확히 그 둘만 나온 것이다.

## model_dump / model_validate — 경계를 넘나들기

pydantic 모델은 양방향으로 쓴다. 바깥 데이터를 모델로 들여오는 것(`model_validate`)과, 모델을 다시 바깥으로 내보내는 것(`model_dump`) 둘 다.

```python title="dump_and_validate.py"
from pydantic import BaseModel


class Address(BaseModel):
    city: str
    zipcode: str


class User(BaseModel):
    name: str
    age: int
    address: Address


u = User(name="Alice", age=25, address=Address(city="Seoul", zipcode="04524"))

print(u.model_dump())          # 중첩 모델까지 재귀적으로 dict로
print(u.model_dump_json())     # JSON 문자열로 직접

# 딕셔너리 → 모델
raw = {"name": "Bob", "age": "30", "address": {"city": "Busan", "zipcode": "48058"}}
u2 = User.model_validate(raw)
print(u2)

# JSON 문자열 → 모델 (파싱과 검증을 한 번에)
json_raw = '{"name": "Carol", "age": 22, "address": {"city": "Incheon", "zipcode": "21554"}}'
u3 = User.model_validate_json(json_raw)
print(u3)
```

```text nolines
{'name': 'Alice', 'age': 25, 'address': {'city': 'Seoul', 'zipcode': '04524'}}
{"name":"Alice","age":25,"address":{"city":"Seoul","zipcode":"04524"}}
name='Bob' age=30 address=Address(city='Busan', zipcode='48058')
name='Carol' age=22 address=Address(city='Incheon', zipcode='21554')
```

`model_validate_json` 이 `model_validate(json.loads(s))` 보다 그냥 편의 함수인 게 아니다. pydantic-core가 JSON 텍스트를 **직접 파싱하면서 동시에 검증**한다. 중간에 파이썬 딕셔너리를 만드는 단계가 없다. 큰 JSON 페이로드를 다루는 API 서버라면 이 차이가 실측 성능에 그대로 나타난다.

`FastAPI` 를 써 봤다면 이 패턴이 익숙할 것이다. 요청 바디를 `BaseModel` 로 선언하면 FastAPI가 내부적으로 `model_validate_json` 을 호출해 파싱·검증·에러 응답까지 자동으로 처리해 준다. pydantic이 파이썬 웹 생태계의 사실상 표준이 된 이유가 이거다.

## 왜 v2가 빨라졌는가 — pydantic-core

pydantic 1.x는 검증 로직 전체가 순수 파이썬이었다. v2는 **핵심 검증 엔진을 Rust로 새로 작성**해서 `pydantic-core` 라는 별도 패키지로 분리했다. `BaseModel` 은 이제 얇은 파이썬 래퍼고, 실제 파싱·검증·직렬화는 컴파일된 Rust 코드가 한다.

```pyrepl
>>> import pydantic, pydantic_core
>>> pydantic.VERSION
'2.13.4'
>>> pydantic_core.__version__
'2.46.4'
```

직접 재 보자. 단일 모델 생성은 차이가 크지 않다.

```python title="bench_single.py"
import timeit
from pydantic import BaseModel


class Item(BaseModel):
    id: int
    name: str
    price: float
    tags: list[str]


data = {"id": 1, "name": "widget", "price": 9.99, "tags": ["a", "b", "c"]}
t = timeit.timeit(lambda: Item(**data), number=100_000)
print(f"{t:.4f}초 / 100,000회")
```

같은 코드를 pydantic v2(2.13.4)와 v1(1.10.14) 환경 각각에서 실측하면:

```text nolines
pydantic 2.13.4: 0.0750초 / 100,000회
pydantic 1.10.14: 0.0782초 / 100,000회
```

이 수치는 `timeit` 벤치마크라 실행할 때마다 조금씩 흔들린다. 실제로 같은 코드를 이 문서를 검증하며 다시 돌려 보면 v2 0.0773~0.0775초, v1 0.0777초 정도로 나온다 — 절대값은 매번 바뀌지만 "거의 차이가 없다"는 결론 자체는 재실행해도 그대로 유지된다. 이유는 **호출 하나당 파이썬 ↔ Rust 경계를 넘는 고정 비용(FFI 오버헤드)** 때문이다. 필드 4개짜리 모델 하나를 만드는 정도로는 그 비용을 상쇄하지 못한다. **v2가 진짜로 빨라지는 지점은 검증할 데이터가 커질 때, 특히 리스트를 한 번에 검증할 때**다.

```python title="bench_batch.py"
import timeit
from pydantic import TypeAdapter


class Item(BaseModel):
    id: int
    name: str
    price: float
    tags: list[str]


batch = [{"id": 1, "name": "widget", "price": 9.99, "tags": ["a", "b", "c"]}] * 1000
adapter = TypeAdapter(list[Item])

t = timeit.timeit(lambda: adapter.validate_python(batch), number=200)
print(f"{t:.4f}초 / (1000개 x 200회 = 20만 건)")
```

```text nolines
pydantic 2.13.4: 0.0827초 / 20만 건 (list[Item] 배치 검증)
pydantic 1.10.14: 0.2750초 / 20만 건 (parse_obj_as 배치 검증)
```

약 **3.3배**. 커뮤니티에서 흔히 보는 "5~50배" 같은 수치보다는 소박하다. 다시 실행하면 절대값은 또 바뀐다 — 같은 코드를 이 문서 검증 중 재실행했을 때는 v2 0.0782초, v1 0.2833초로 약 3.6배가 나왔다. 배수 자체가 3.3배냐 3.6배냐는 실행마다 달라지지만, "단일 생성은 거의 차이가 없는데 배치 검증은 3배 이상 차이 난다"는 방향은 매번 재현된다. 이 기기, 이 모델 구조에서는 그렇다는 것이지 일반화된 상수는 아니다 — 필드가 많고 중첩이 깊을수록, 그리고 개별 호출이 아니라 배치로 검증할수록 Rust 코어의 이득이 커진다. 요지는 이거다. **"v2가 v1보다 빠르다"는 마케팅 문구를 그대로 믿지 말고, 당신의 모델·당신의 데이터 크기로 직접 재라.** [5.1 측정 없이 최적화 없다](#/profiling)의 원칙이 여기도 그대로 적용된다.

::: perf TypeAdapter — 모델이 아닌 타입도 검증한다
`BaseModel` 을 만들 만큼 구조화되지 않은 값 — `list[int]`, `dict[str, float]`, 심지어 `int | str` 같은 단순 타입 — 도 검증하고 싶을 때가 있다. `TypeAdapter` 가 그 자리를 채운다.

```pyrepl
>>> from pydantic import TypeAdapter
>>> adapter = TypeAdapter(list[int])
>>> adapter.validate_python(["1", "2", "3"])
[1, 2, 3]
```

`BaseModel` 을 굳이 만들지 않고도 pydantic-core의 검증·변환 능력만 빌리는 방법이다.
:::

## 설정 관리 — BaseSettings

애플리케이션 설정(DB 주소, 디버그 플래그, API 키)은 보통 환경변수로 주입된다. `pydantic-settings` 패키지의 `BaseSettings` 는 **환경변수를 읽어서 자동으로 파싱·검증까지 해 주는 BaseModel** 이다.

```python title="settings.py"
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_")

    debug: bool = False
    db_host: str = "localhost"
    db_port: int = 5432


print(AppSettings())       # 환경변수가 없으면 기본값

os.environ["MYAPP_DEBUG"] = "true"
os.environ["MYAPP_DB_PORT"] = "6543"
settings = AppSettings()
print(settings)
print(type(settings.debug), type(settings.db_port))
```

```text nolines
debug=False db_host='localhost' db_port=5432
debug=True db_host='localhost' db_port=6543
<class 'bool'> <class 'int'>
```

`MYAPP_DEBUG=true` 라는 **문자열**이 `bool` 타입 필드로, `MYAPP_DB_PORT=6543` 이 `int` 타입 필드로 자동 변환됐다. 환경변수는 원래 전부 문자열이라는 사실을 생각하면, 이 변환이 왜 pydantic의 핵심 가치인지 다시 보인다 — 환경변수도 결국 **바깥에서 들어온, 타입이 안 보장된 데이터**다.

::: tip .env 파일도 읽는다
`SettingsConfigDict(env_file=".env")` 를 추가하면 `.env` 파일도 같이 읽는다. 우선순위는 (일반적으로) 명시적 인자 > 환경변수 > `.env` 파일 > 기본값 순이다. 비밀번호·API 키처럼 커밋하면 안 되는 값은 `.env` 로 분리하고 `.gitignore` 에 넣는 게 관례다.
:::

## attrs — pydantic보다 가벼운 선택지

pydantic이 "검증 + 파싱 + 직렬화"까지 다 하는 무거운 도구라면, `attrs` 는 dataclass에 더 가깝다. **검증은 옵션이고, 강제 변환은 하지 않는다.**

```python title="attrs_demo.py"
import attrs


@attrs.define
class Point:
    x: int
    y: int


@attrs.define
class Positive:
    value: int = attrs.field(validator=attrs.validators.gt(0))


p = Point(1, 2)
print(p)

try:
    Positive(-1)
except ValueError as e:
    print(f"{type(e).__name__}: {e}")
```

```text nolines
Point(x=1, y=2)
ValueError: 'value' must be > 0: -1
```

사실 `dataclasses` 모듈 자체가 attrs의 아이디어를 표준 라이브러리로 가져온 것이다([2.6 dataclasses](#/dataclasses)). attrs는 `dataclass` 보다 먼저 있었고, 지금도 `dataclass` 에는 없는 것들 — 필드별 검증자, `on_setattr` 훅, 더 빠른 `__init__` 생성 — 을 제공한다. 다만 pydantic처럼 "임의의 문자열을 int로 파싱"하는 강제 변환은 기본적으로 하지 않는다. **가벼운 값 객체엔 attrs나 frozen dataclass, 외부 경계의 검증엔 pydantic** — 이게 실무에서 자리 잡은 구분이다.

## 언제 무엇을 쓰는가

| 상황 | 도구 |
| --- | --- |
| 내부 코드끼리 주고받는 구조화된 값 | `@dataclass` |
| 값 검증이 필요하지만 파싱은 필요 없는 내부 값 객체 | `attrs` |
| 외부 입력(API 요청, JSON, 폼, 환경변수) 검증 | `pydantic.BaseModel` |
| 애플리케이션 설정 로딩 | `pydantic_settings.BaseSettings` |
| 타입은 있지만 클래스로 감쌀 필요 없는 값 하나 | `pydantic.TypeAdapter` |

이 표를 가르는 기준은 결국 하나다. **그 데이터가 당신의 코드 안에서 태어났는가, 바깥에서 왔는가.** [1.15 프로토콜](#/protocols)에서 봤듯 파이썬은 "타입이 맞는 것처럼 행동하면 된다"는 덕 타이핑 위에 서 있다. 정적 타입 힌트([2.2 타입 문법의 기초](#/typing-basics))는 그 위에 얹는 **약속**이고, pydantic은 그 약속을 **경계에서 실제로 검사**해 주는 감시자다. 다음 절 [2.8 mypy와 pyright 실전](#/typecheckers)에서는 그 정적 검사기 자체를 더 깊이 다룬다.

## 요약

- 타입 힌트는 런타임에 아무 영향이 없다. `@dataclass` 도 마찬가지다 — 값 검증은 정적 검사기(`pyright`, `mypy`)의 몫이다.
- pydantic `BaseModel` 은 **선언한 타입을 실행 시점에 실제로 검증**하고, 가능하면 변환(coercion)한다.
- 검증 실패는 `ValidationError` 하나로 모인다. 필드마다의 실패를 `.errors()` 로 한 번에 볼 수 있다.
- `@field_validator` 는 필드 하나, `@model_validator(mode="after")` 는 필드 간 관계를 검사한다.
- `model_dump`/`model_validate`, `model_dump_json`/`model_validate_json` 이 경계를 넘나드는 표준 통로다.
- v2의 속도 개선은 Rust로 작성된 `pydantic-core` 덕분이다. 다만 이득은 **배치·중첩 검증**에서 크게 나타나고, 단일 호출에서는 미미할 수 있다 — 직접 재라.
- `attrs`는 pydantic보다 가벼운 선택지다. 강제 변환 없이 검증만 필요하면 이쪽을 본다.
- `pydantic_settings.BaseSettings` 는 환경변수·`.env` 파일을 자동으로 읽어 타입 변환까지 해 준다.

::: quiz 연습문제
1. 다음 dataclass가 런타임에서 아무 에러 없이 실행됨을 먼저 예측하고 실행해서 확인하라. 그다음 같은 파일에 `uvx pyright` 를 돌려서 어떤 오류가 나오는지 확인하라.

   ```python
   from dataclasses import dataclass

   @dataclass
   class Point:
       x: int
       y: int

   p = Point(x="1", y=2.5)
   print(p)
   ```

2. 아래 pydantic 모델에 `age=-5` 를 넣으면 `ValidationError` 가 나지 않는다. 왜 안 나는지 설명하고, `field_validator` 를 추가해 나이가 음수면 막도록 고쳐라.

   ```python
   from pydantic import BaseModel

   class User(BaseModel):
       name: str
       age: int
   ```

3. `User(name="a", age="1", age2="2")` 처럼 모델에 정의되지 않은 필드(`age2`)를 같이 넘기면 기본 설정에서 pydantic은 그 필드를 어떻게 처리하는가? 직접 실행해서 확인하고, 그 필드가 들어오면 아예 에러를 내도록 만드는 설정을 찾아라.

4. `model_dump()` 와 `model_dump_json()` 의 차이를 설명하고, 중첩된 `datetime` 필드가 있을 때 두 메서드의 출력이 어떻게 다른지 직접 확인하라.

5. **깊이 생각해 볼 문제.** 이 절의 배치 검증 벤치마크에서 v2가 v1보다 약 3.3배 빨랐다. 단일 모델 생성 벤치마크에서는 오히려 v1과 비슷하거나 근소하게 느렸다. 왜 이런 차이가 나는지, "파이썬-Rust 경계를 넘는 비용"이라는 개념으로 설명하라.
:::

**다음 절**: [2.8 mypy와 pyright 실전](#/typecheckers) — 지금까지 몇 번이나 등장한 `uvx pyright` 를 실제 프로젝트에 어떻게 설정하고, strict 모드는 무엇을 더 잡아내는가.
