# 3.6 AST와 코드 생성

::: lead
지금까지 데코레이터, 디스크립터, 메타클래스로 파이썬 객체를 조작했다. 이 절은 한 단계 더 내려간다. **객체가 아니라 코드 자체를 조작하는 법**이다. 소스 코드는 실행되기 전에 트리 구조를 거친다. 그 트리를 들여다보고, 고치고, 다시 실행 가능한 형태로 되돌리는 것이 파이썬의 `ast` 모듈이다. 린터, 포매터, 일부 DSL, `pytest` 의 `assert` 재작성까지 — 전부 이 위에서 돌아간다. 동시에 이 절은 **가장 위험한 도구**를 다룬다. 코드를 코드로 실행하는 능력은 오남용되면 그대로 보안 사고가 된다.
:::

## 문자열 조작으로는 안 되는 이유

코드를 변형하고 싶다고 하자. 예를 들어 "이 함수 안의 모든 `print` 호출 앞에 로그를 남겨라" 같은 작업이다. 가장 먼저 떠오르는 방법은 정규식으로 소스 텍스트를 뒤지는 것이다.

```python
import re

src = "print('hello')  # print('상수 문자열 안')"
re.sub(r"print\(", "log(", src)
```

이 코드는 문자열 리터럴 안에 있는 `print`, 주석 안에 있는 `print`, 심지어 변수 이름의 일부인 `myprint(` 까지 전부 건드릴 위험이 있다. **텍스트는 코드의 구조를 모른다.** 어디까지가 문자열이고, 어디부터가 주석이고, 어디가 실제 호출식인지 구분하려면 결국 파이썬 문법을 다시 파싱해야 한다.

파이썬 인터프리터는 이 문제를 이미 풀어 놨다. 소스 코드를 실행하기 전에 반드시 **추상 구문 트리**(Abstract Syntax Tree, AST)로 바꾼다. `ast` 모듈은 이 내부 단계를 그대로 꺼내 쓰게 해 준다.

```text nolines
source ──▶ tokenize ──▶ ast ──▶ compile ──▶ VM
```

소스 텍스트가 먼저 토큰으로 쪼개지고(`tokenize`), 그 토큰들이 트리로 조립되고(`ast`), 트리가 바이트코드로 컴파일되고(`compile`), 마지막으로 CPython 가상 머신이 그 바이트코드를 실행한다. 바이트코드 단계는 [3.7 바이트코드와 dis](#/bytecode)에서 다룬다. 이 절은 그 앞 단계, **AST를 직접 만들고 읽고 고치는 법**이다.

## `ast.parse` — 소스를 트리로

`ast.parse(source)` 는 소스 코드 문자열을 받아 트리의 뿌리 노드를 돌려준다.

```python title="parse_basic.py"
import ast

src = "x = 1 + 2 * 3"
tree = ast.parse(src)
print(ast.dump(tree, indent=2))
```

```text nolines
Module(
  body=[
    Assign(
      targets=[
        Name(id='x', ctx=Store())],
      value=BinOp(
        left=Constant(value=1),
        op=Add(),
        right=BinOp(
          left=Constant(value=2),
          op=Mult(),
          right=Constant(value=3))))])
```

실제로 실행해서 나온 출력이다. 구조를 읽어 보자.

- 최상위는 항상 `Module` 이다. 파일 하나가 통째로 이 노드다.
- `body` 는 문장(statement)의 리스트다. `x = 1 + 2 * 3` 은 문장 하나니까 `Assign` 노드 하나가 들어 있다.
- `Assign` 은 `targets`(대입 대상, 리스트인 이유는 `a = b = 1` 처럼 다중 대입이 가능해서다)와 `value`(오른쪽 값)를 가진다.
- 연산자 우선순위(`*` 가 `+` 보다 먼저)가 트리의 **깊이**로 표현된다. `2 * 3` 이 `BinOp` 로 먼저 묶이고, 그 결과가 `1 + (...)` 의 오른쪽에 들어간다.

`Name` 노드의 `ctx` 필드를 주목하라. 같은 이름 `x` 라도 **왼쪽에 있으면 `Store()`, 오른쪽에 있으면 `Load()`** 다. 이건 [1.1 객체·이름·참조](#/objects-names)에서 다룬 이야기와 정확히 이어진다 — `x = 5` 는 "상자에 값을 넣는" 연산이 아니라 "이름표를 붙이는" 연산이라고 했다. AST 레벨에서 그 비유가 문자 그대로 드러난다. `Store` 는 이름표를 붙이는 동작이고, `Load` 는 이미 붙어 있는 이름표를 따라가 객체를 읽는 동작이다.

::: note 문장(statement) vs 표현식(expression)
`ast.parse` 의 기본 모드는 `mode="exec"` 다. 파일 전체, 즉 문장들의 나열을 기대한다. 표현식 하나만 파싱하고 싶으면 `mode="eval"` 을 쓴다. 결과 루트 노드도 달라진다.

```pyrepl
>>> import ast
>>> ast.parse("x + 1", mode="eval")
<ast.Expression object at 0x...>
>>> ast.dump(ast.parse("x + 1", mode="eval"))
"Expression(body=BinOp(left=Name(id='x', ctx=Load()), op=Add(), right=Constant(value=1)))"
```

`Module` 은 `body` 가 문장의 **리스트**이고, `Expression` 은 `body` 가 표현식 **하나**다. 이 차이가 뒤에서 `eval` 과 `exec` 의 차이로 그대로 이어진다.
:::

::: deep 노드에는 위치 정보도 들어 있다
`ast.dump` 는 기본적으로 줄 번호를 숨긴다. `include_attributes=True` 를 주면 보인다.

```pyrepl
>>> ast.dump(ast.parse("x = 1"), include_attributes=True, indent=2)
```

```text nolines
Module(
  body=[
    Assign(
      targets=[
        Name(
          id='x',
          ctx=Store(),
          lineno=1,
          col_offset=0,
          end_lineno=1,
          end_col_offset=1)],
      value=Constant(
        value=1,
        lineno=1,
        col_offset=4,
        end_lineno=1,
        end_col_offset=5),
      lineno=1,
      col_offset=0,
      end_lineno=1,
      end_col_offset=5)])
```

`lineno`/`col_offset`/`end_lineno`/`end_col_offset` 는 에러 메시지가 소스의 정확한 위치를 가리킬 때, 그리고 린터가 "몇 번째 줄, 몇 번째 칸"을 보고할 때 쓰인다. 3.8부터 `end_lineno`/`end_col_offset` 이 추가되어 **노드가 끝나는 위치**까지 알 수 있게 됐다 — 여러 줄에 걸친 표현식을 정확히 잘라내는 도구(자동 리팩터링, 코드 포매터)에 필수적이다.
:::

## 트리를 순회한다: `NodeVisitor`

트리가 있으면 그 안에서 특정 패턴을 찾고 싶어진다. "이 함수에 가변 기본값이 있는가?", "이 모듈이 `eval` 을 쓰는가?" 같은 질문이다. 매번 재귀 함수를 손으로 짜는 대신 `ast.NodeVisitor` 를 상속한다.

```python title="visitor_basic.py"
import ast


class CallCounter(ast.NodeVisitor):
    def __init__(self):
        self.calls = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        self.generic_visit(node)  # 자식 노드도 계속 순회한다


src = "print(len([1, 2, 3])); sorted(range(5))"
tree = ast.parse(src)
counter = CallCounter()
counter.visit(tree)
print(counter.calls)
```

```pyrepl
>>> exec(open("visitor_basic.py").read())
['print', 'len', 'sorted', 'range']
```

`visit_Call` 처럼 **`visit_노드타입`** 이름의 메서드를 정의하면, `.visit()` 이 트리를 훑다가 해당 타입을 만날 때마다 그 메서드를 호출한다. 이건 방문자 패턴(visitor pattern)이고, `dict` 나 `list` 를 순회할 때 쓰는 [1.18 이터레이터](#/iterators)의 아이디어와 본질이 같다 — **순회 로직과 처리 로직을 분리**한다. 다른 점은 `NodeVisitor` 가 순회하는 대상이 트리이므로 재귀가 필요하고, `generic_visit(node)` 를 호출해야 자식으로 내려간다는 것뿐이다. `generic_visit` 을 빼먹으면 최상위 레벨만 보고 멈춘다 — 흔한 실수다.

`ast.walk(tree)` 를 쓰면 클래스를 안 만들어도 트리의 모든 노드를 순서 상관없이 순회하는 제너레이터를 얻는다. 빠르게 뭔가 찾을 때 편하다.

```pyrepl
>>> [type(n).__name__ for n in ast.walk(ast.parse("x = 1 + 2"))]
['Module', 'Assign', 'Name', 'BinOp', 'Store', 'Constant', 'Add', 'Constant']
```

`ast.walk` 는 내부적으로 `deque` 에 자식 노드를 쌓아 가며 도는 너비 우선(BFS) 순회다. `Assign` 의 자식은 `targets`(먼저 나오는 `Name`)와 `value`(그다음 `BinOp`) 순서로 큐에 들어가고, 그 각각의 자식이 다시 큐 뒤에 쌓인다 — 그래서 `Name` 이 `BinOp` 보다 먼저, `Name` 의 `Store` 가 `BinOp` 의 자식들보다 먼저 나온다. 순서 자체에 의미를 두지 마라. **집합으로서 어떤 노드 타입이 있는지**를 볼 때나 쓰는 도구다.

## 트리를 바꾼다: `NodeTransformer`

읽기만 하는 게 아니라 **고치고** 싶으면 `ast.NodeTransformer` 를 쓴다. 각 `visit_*` 메서드가 **원래 노드 대신 반환하는 노드**로 트리를 대체한다.

```python title="transform.py"
import ast


class DoubleConstants(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            new_node = ast.Constant(value=node.value * 2)
            return ast.copy_location(new_node, node)
        return node


src = """
def total(a, b):
    return a + b + 10

print(total(1, 2))
"""

tree = ast.parse(src)
new_tree = DoubleConstants().visit(tree)
ast.fix_missing_locations(new_tree)

print(ast.unparse(new_tree))
```

실제 실행 결과다.

```text nolines
def total(a, b):
    return a + b + 20
print(total(2, 4))
```

모든 숫자 리터럴이 두 배가 됐다. 여기서 두 가지를 짚어야 한다.

**`ast.copy_location`.** 새로 만든 노드는 위치 정보(`lineno` 등)가 없다. 원래 노드의 위치를 복사해 줘야 나중에 에러가 나도 정확한 줄을 가리킨다.

**`ast.fix_missing_locations`.** 트리 전체를 훑으면서 위치 정보가 빠진 노드에 부모의 위치를 채워 넣는다. `copy_location` 을 노드마다 일일이 챙기지 못했을 때의 안전망이다. **이걸 빼먹으면 `compile()` 단계에서 `ValueError: ... has no lineno attribute` 로 죽는다.**

`ast.unparse(tree)` 는 3.9에서 추가됐다. 트리를 다시 파이썬 소스 문자열로 되돌린다. 변환 결과를 사람이 읽을 수 있게 확인할 때, 또는 코드 생성 도구의 최종 산출물을 만들 때 쓴다.

## `compile()` 과 `exec()` — 트리를 다시 실행 가능하게

트리를 고쳤으면 실행해야 의미가 있다. `compile()` 은 AST(또는 소스 문자열)를 **코드 객체**(code object)로 바꾼다.

```python
code = compile(new_tree, filename="<transformed>", mode="exec")
namespace = {}
exec(code, namespace)
```

```text nolines
26
```

`total(2, 4)` — 두 배가 된 인자와 상수로 계산한 값이다 (`2 + 4 + 20`). `compile()` 의 세 인자를 눈여겨봐라.

- **소스**: AST 노드거나 소스 코드 문자열이거나 상관없다. 둘 다 받는다.
- **`filename`**: 실제 파일이 아니어도 된다. 관례적으로 `<string>` 이나 `<transformed>` 처럼 꺾쇠로 감싼 이름을 쓴다. 에러 트레이스백에 이 이름이 그대로 찍힌다.
- **`mode`**: `"exec"`(문장들), `"eval"`(표현식 하나), `"single"`(REPL 한 줄, 결과를 자동 출력) 중 하나. 소스와 이 모드가 안 맞으면 `SyntaxError` 다.

`filename` 이 왜 중요한지는 실제 에러로 보면 바로 느껴진다.

```pyrepl
>>> code = compile("1 / 0", "<my_dsl_script>", "exec")
>>> exec(code)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    exec(code)
    ~~~~^^^^^^
  File "<my_dsl_script>", line 1, in <module>
ZeroDivisionError: division by zero
```

`<my_dsl_script>` 가 트레이스백에 그대로 나온다. `File "<stdin>", line 1` 아래 붙은 `exec(code)` 소스 라인과 캐럿(`^`) 강조는 3.11부터 들어온 PEP 657 세밀한 에러 위치 표시 기능이다 — `exec` 를 호출한 바깥쪽 프레임에는 붙지만, `<my_dsl_script>` 프레임에는 붙지 않는다. 코드를 생성해서 실행하는 도구(템플릿 엔진, DSL 인터프리터)를 만든다면, 이 인자에 의미 있는 이름을 넣어 두는 것만으로 사용자에게 훨씬 나은 에러 메시지를 줄 수 있다.

::: deep import 시스템도 이 파이프라인을 그대로 쓴다
`import` 문이 `.py` 파일을 실행 가능한 모듈로 바꾸는 과정도 정확히 이 세 단계를 거친다 — 소스를 읽고, `ast.parse` 로 트리를 만들고, `compile()` 로 코드 객체를 만들고, 모듈의 이름 공간에서 `exec` 한다. `.pyc` 캐시는 이 중 **컴파일된 코드 객체를 저장**해서 다음 실행 때 파싱·컴파일 단계를 건너뛰게 해 주는 것이다. [1.19 모듈, 패키지, import 시스템](#/imports)에서 다룬 `sys.path` 탐색이 끝나면, 그다음이 바로 이 절에서 본 과정이다.
:::

## `eval` 과 `exec` 는 다른 질문에 답한다

이 둘을 헷갈리는 사람이 많다. 질문 자체가 다르다.

| | `eval` | `exec` |
| --- | --- | --- |
| 입력 | **표현식 하나** | **문장들의 나열** |
| 반환값 | 표현식의 값 | 항상 `None` |
| 대입문 (`x = 1`) | 불가능 (`SyntaxError`) | 가능 |
| `def`, `for`, `import` | 불가능 | 가능 |
| 결과 확인 방법 | 반환값 | 넘겨준 네임스페이스 딕셔너리 |

실제로 확인해 보자.

```pyrepl
>>> eval("1 + 2")
3
>>> eval("x = 1")
Traceback (most recent call last):
  ...
SyntaxError: invalid syntax
>>> ns = {}
>>> exec("x = 1 + 2", ns)
>>> ns["x"]
3
```

`eval("x = 1")` 이 문법 에러가 나는 이유는 `x = 1` 이 **문장**이지 **표현식**이 아니기 때문이다. `eval` 은 내부적으로 `ast.parse(source, mode="eval")` 과 똑같은 제약을 받는다. `exec` 는 반환값이 없는 대신, 넘겨준 딕셔너리(네임스페이스)를 직접 수정한다 — 그래서 결과를 보려면 그 딕셔너리를 들여다봐야 한다.

::: warn eval/exec에 넘기는 globals/locals 딕셔너리
`eval(src, globals_dict, locals_dict)` 형태로 네임스페이스를 직접 지정할 수 있다. 지정하지 않으면 **호출하는 곳의 실제 전역/지역 네임스페이스**를 그대로 쓴다 — 즉 그 함수가 보는 모든 이름과 모든 임포트된 모듈에 접근할 수 있다는 뜻이다. 신뢰 못 하는 문자열을 `eval` 에 넘길 때 네임스페이스를 제한하지 않는 건 문을 활짝 열어 두는 것과 같다. 다음 절에서 이게 왜 충분한 방어가 아닌지도 본다.
:::

## 신뢰할 수 없는 코드를 실행한다는 것

`eval`/`exec`/`compile` 은 **임의의 파이썬 코드를 실행하는 능력**이다. 이 능력에는 신뢰 경계라는 개념이 따라붙는다. 웹 요청, 설정 파일, 사용자 입력처럼 **당신이 통제하지 않는 곳에서 온 문자열을 절대 `eval`/`exec` 에 넘기지 마라.** 그 문자열을 만든 사람이 당신의 프로세스 전체를 가져갈 수 있다.

"`__builtins__` 를 비우면 안전하지 않나?" — 흔한 오해다. 직접 확인해 보자.

```pyrepl
>>> payload = "().__class__.__base__.__subclasses__()"
>>> result = eval(payload, {"__builtins__": {}})
>>> len(result)
174
>>> result[:3]
[<class 'type'>, <class 'async_generator'>, <class 'bytearray_iterator'>]
```

`__builtins__` 를 빈 딕셔너리로 막아도 뚫렸다. **모든 객체는 `__class__` 를 가지고, 모든 클래스는 `object` 로 이어지는 `__base__` 사슬을 가지며, `object` 는 현재 로드된 **모든 서브클래스**를 알고 있다.** 저 리스트 174개 안에는 파일을 열거나 서브프로세스를 띄울 수 있는 클래스가 섞여 있을 수 있다. `__builtins__` 를 비우는 건 **정문**을 잠그는 것이고, 이건 담을 넘는 경로다. 순수 파이썬으로 이 경로를 완벽히 막는 건 사실상 불가능하다고 알려져 있다.

::: danger 신뢰 못 하는 코드를 실행하지 마라
이 절에서 가장 중요한 문장이다.

- **사용자 입력, 네트워크에서 받은 문자열, 신뢰할 수 없는 설정 파일을 `eval`/`exec`/`compile` 에 절대 넘기지 마라.**
- `globals`/`locals` 를 제한하는 것은 **방어가 아니라 완화**다. 위에서 봤듯 뚫린다.
- 정말로 샌드박스가 필요하면 파이썬 프로세스 자체를 격리하라 (컨테이너, 별도 프로세스, OS 레벨 권한 제한). 언어 레벨 트릭으로 해결하려 하지 마라.
- **숫자·문자열·리스트 같은 리터럴 값만 안전하게 읽고 싶다면 `ast.literal_eval` 을 써라.** 이건 코드를 실행하지 않고 리터럴만 파싱한다.

```pyrepl
>>> ast.literal_eval("[1, 2, {'a': 3}]")
[1, 2, {'a': 3}]
>>> ast.literal_eval("1 + 2")
Traceback (most recent call last):
  ...
ValueError: malformed node or string ...
```

`literal_eval` 은 연산조차 허용하지 않는다. 안전을 위해 일부러 그렇게 만들었다. 산술 연산까지 허용하는 "안전한 계산기"가 필요하면 아래처럼 **직접 AST를 화이트리스트로 검증**해야 한다.
:::

## 실전: 안전한 표현식 DSL

`literal_eval` 은 연산을 못 하고, `eval` 은 뭐든 다 한다. 그 중간이 필요할 때가 있다 — 예를 들어 설정 파일에 `"width * 2 + margin"` 같은 수식을 허용하고 싶지만, 임포트나 함수 호출은 막고 싶은 경우다. `ast` 를 쓰면 **허용할 노드 타입만 화이트리스트**로 정해서 이걸 만들 수 있다.

```python title="safe_eval.py"
import ast
import operator

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
UNARY_OPS = {ast.USub: operator.neg}


def safe_eval(expr: str):
    node = ast.parse(expr, mode="eval").body
    return _eval(node)


def _eval(node):
    match node:
        case ast.Constant(value=v) if isinstance(v, (int, float)):
            return v
        case ast.BinOp(left=left, op=op, right=right) if type(op) in BIN_OPS:
            return BIN_OPS[type(op)](_eval(left), _eval(right))
        case ast.UnaryOp(op=op, operand=operand) if type(op) in UNARY_OPS:
            return UNARY_OPS[type(op)](_eval(operand))
        case _:
            raise ValueError(f"허용하지 않는 문법: {ast.dump(node)}")
```

실행 결과다.

```pyrepl
>>> safe_eval("1 + 2 * 3")
7
>>> safe_eval("(1 + 2) * -3")
-9
>>> safe_eval("__import__('os').system('echo pwned')")
Traceback (most recent call last):
  ...
ValueError: 허용하지 않는 문법: Call(func=Attribute(value=Call(func=Name(id='__import__', ...
>>> safe_eval("[x for x in range(3)]")
Traceback (most recent call last):
  ...
ValueError: 허용하지 않는 문법: ListComp(...)
```

핵심은 **`Call`, `ListComp`, `Attribute` 같은 노드 타입 자체를 `_eval` 이 인식하지 못한다**는 것이다. `match` 문의 `case _` 가 화이트리스트에 없는 모든 걸 예외로 떨어뜨린다. 이건 [1.8 제어 흐름과 match 문](#/control-flow)에서 본 구조적 패턴 매칭이 AST 노드를 다룰 때 얼마나 잘 맞는지 보여주는 예이기도 하다 — 노드 타입과 필드를 동시에 매치하고 조건(`if type(op) in BIN_OPS`)까지 건다.

`BinOp` 노드가 파이썬을 실행할 때는 `left.__add__(right)` 호출로 이어진다는 것도 짚어 둘 만하다. `+` 연산자가 실제로 무엇을 호출하는지는 [1.14 특수 메서드 총정리](#/dunder)에서 다뤘다. 여기서는 그 호출을 직접 흉내 내는 대신 `operator.add` 로 대체했을 뿐, 개념은 같다.

::: cote 코딩테스트 포인트
코딩테스트에서 `eval` 을 쓰고 싶은 유혹이 자주 생긴다 — 특히 수식 문자열을 파싱해서 계산하는 문제(계산기, 후위 표기법 변환)에서다. **`eval` 은 문제에서 주어진 입력이 항상 신뢰할 수 있는 상황**이라 실전에서는 크게 위험하지 않지만, 습관은 위험하다. 실무 코드에 그 습관이 그대로 옮겨가면 사고가 난다. 연습 삼아 위의 `safe_eval` 패턴으로 직접 계산기를 짜 보는 걸 권한다 — 어차피 스택 기반 계산기보다 코드가 짧고, AST가 우선순위와 결합성을 이미 다 처리해 준다.
:::

## 실전: 미니 린터 만들기

`ast` 의 가장 실용적인 용도는 코드를 **실행하지 않고** 검사하는 것이다. [1.1 객체·이름·참조](#/objects-names)에서 본 "가변 기본값" 함정을 기억할 것이다. `ruff` 의 `B006` 규칙이 바로 이걸 잡는다고 했다. 그 규칙을 흉내 낸 미니 린터를 40줄 안에 만들 수 있다.

```python title="mini_linter.py"
import ast

MUTABLE_LITERALS = (ast.List, ast.Dict, ast.Set)


class MutableDefaultChecker(ast.NodeVisitor):
    def __init__(self):
        self.problems = []

    def visit_FunctionDef(self, node):
        for default in node.args.defaults:
            if isinstance(default, MUTABLE_LITERALS):
                self.problems.append(
                    f"{node.name}() 줄 {default.lineno}: 가변 기본값 사용"
                )
        self.generic_visit(node)


src = '''
def add_item(item, bucket=[]):
    bucket.append(item)
    return bucket


def safe_add(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
'''

tree = ast.parse(src)
checker = MutableDefaultChecker()
checker.visit(tree)
for p in checker.problems:
    print(p)
```

실행 결과다.

```text nolines
add_item() 줄 2: 가변 기본값 사용
```

`safe_add` 는 걸리지 않는다. 기본값이 `None` 이라 `ast.List`/`ast.Dict`/`ast.Set` 타입이 아니기 때문이다. 여기서 **린터가 코드를 실행하지 않는다**는 점이 중요하다. `add_item` 을 한 번도 호출하지 않고도 문제를 찾아냈다. 실제 `ruff`, `pylint`, `flake8` 은 이 접근을 훨씬 정교하게 확장한 것이다 — 데이터 흐름 분석, 스코프 추적, 수백 개의 규칙이 추가될 뿐 **원리는 여기서 만든 것과 같다.** ([0.4 린터·포매터·타입체커 세팅](#/tooling))

`args.defaults` 가 함수의 **뒤쪽** 매개변수부터 채워진다는 점도 실전에서 주의할 부분이다. `def f(a, b=1, c=2)` 라면 `defaults` 는 `[1, 2]` 두 개뿐이고 `a` 에는 대응하는 기본값이 없다. 정확한 린터를 만들려면 `node.args.args` 의 길이와 `defaults` 의 길이 차이를 계산해서 매칭해야 한다 — 이 절에서는 생략했지만, 실전 도구를 만든다면 반드시 처리해야 하는 부분이다.

## 언제 쓰지 말아야 하는가

AST 조작은 이 파트에서 다룬 메타클래스([3.4 메타클래스와 __init_subclass__](#/metaclass))만큼이나 강력하고, 그만큼 오남용하기 쉽다.

**정적 분석·코드 생성 도구를 만들 때만 써라.** 런타임에 일반적인 애플리케이션 로직으로 `ast`/`compile`/`exec` 를 쓰는 경우는 거의 없어야 한다. "설정값에 따라 다른 함수를 실행하고 싶다"는 요구는 대부분 `dict` 로 이름과 함수를 매핑하거나(`{"add": add_fn, "sub": sub_fn}`), [3.1 일급 함수와 functools](#/functools)의 `partial`/`singledispatch` 로 풀린다. 코드를 **생성**하는 것보다 코드를 **선택**하는 것이 거의 항상 더 안전하고, 더 빠르고, 디버깅하기 쉽다.

**디버깅이 지옥이 된다.** 동적으로 생성된 코드는 트레이스백에 `<string>` 이나 `<transformed>` 같은 가짜 파일명이 찍힌다. 브레이크포인트를 걸 실제 소스 줄도 없다. `filename` 인자에 신경 써도 한계가 있다.

**신뢰 경계를 넘는 입력에는 절대 쓰지 마라.** 위에서 봤듯 `__builtins__` 를 비우는 정도의 방어는 뚫린다.

**"그냥 함수로 짜면 되는 걸" AST로 짜고 있지 않은지 항상 의심하라.** 진짜로 AST가 필요한 경우는 명확하다 — 정적 분석 도구를 만들거나, 소스 코드 자체를 변환하는 빌드 도구를 만들거나(예: `pytest` 가 `assert` 문을 재작성해서 실패 시 좌우 값을 자동으로 보여주는 것), 사용자가 정의하는 제한된 DSL을 안전하게 해석해야 할 때다. 이 셋에 해당하지 않는다면, 다른 도구가 이미 있다.

## 요약

- 소스 코드는 실행 전에 **AST**를 거친다. `ast.parse` 로 이 트리를 직접 볼 수 있다.
- `Module` 은 문장들의 나열(`mode="exec"`), `Expression` 은 표현식 하나(`mode="eval"`)다. `ast.parse` 와 `eval`/`exec`/`compile` 은 이 모드를 정확히 공유한다.
- `NodeVisitor` 는 트리를 읽기만, `NodeTransformer` 는 노드를 반환값으로 대체해 트리를 바꾼다. 새 노드에는 `ast.copy_location`/`ast.fix_missing_locations` 로 위치 정보를 채워야 `compile()` 이 받아들인다.
- `compile()` 은 AST(또는 소스)를 코드 객체로 바꾸고, `exec`/`eval` 이 그것을 실행한다. `eval` 은 표현식 하나의 **값**을, `exec` 는 네임스페이스의 **부수효과**를 남긴다.
- `eval`/`exec` 로 신뢰 못 하는 문자열을 실행하지 마라. `globals`/`locals` 제한은 방어가 아니라 완화다. 리터럴만 필요하면 `ast.literal_eval`, 제한된 산술이 필요하면 화이트리스트 방식의 AST 인터프리터를 직접 짜라.
- 실전 용도는 정적 분석(린터)과 코드 생성(빌드 도구, DSL)이다. 일반 애플리케이션 로직에 끌어들이지 마라.

::: quiz 연습문제
1. `ast.parse("a and b or c")` 를 실행하고 `ast.dump` 로 구조를 확인하라. `BoolOp` 노드가 어떤 필드를 가지는지, `and`/`or` 가 이항 연산자로 표현되지 않는 이유를 설명하라.
2. 이 절의 `MutableDefaultChecker` 를 확장해서, 매개변수 이름과 기본값의 대응을 정확히 맞춰라 (`args.args` 길이와 `args.defaults` 길이가 다르다는 점을 반영). 키워드 전용 인자(`node.args.kwonlyargs`)의 기본값도 검사하도록 만들어라.
3. `safe_eval` 에 `%`(나머지 연산)와 비교 연산자(`<`, `>`)를 추가하라. 비교 연산자는 `ast.Compare` 노드로 표현되는데, `ast.dump(ast.parse("1 < 2", mode="eval"))` 를 먼저 실행해서 구조를 확인한 뒤 구현하라.
4. 다음 코드가 왜 `SyntaxError` 를 내는지 설명하라. `eval` 대신 무엇을 써야 하는가?

   ```python
   eval("for i in range(3): print(i)")
   ```

5. **깊이 생각해 볼 문제.** `ast.literal_eval` 은 왜 `1 + 2` 같은 산술조차 거부하도록 설계됐을까? `eval` 이 있는데 왜 굳이 훨씬 제한적인 함수를 따로 만들었는지, 이 절에서 본 보안 논의와 연결해 설명하라.
:::

**다음 절**: [3.7 바이트코드와 dis](#/bytecode) — AST 다음 단계, 인터프리터가 실제로 실행하는 명령어를 직접 들여다본다.
