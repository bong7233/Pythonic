# 3.7 바이트코드와 dis

::: lead
`property`, `classmethod`, 메타클래스는 파이썬 코드로 구현돼 있으니 소스를 읽으면 끝까지 이해할 수 있다. 그런데 그 파이썬 코드 자체는 어떻게 실행될까? 인터프리터가 함수 하나를 부를 때 실제로 일어나는 일을 한 층 더 내려가서 보자. 이 절을 넘기면 "파이썬은 느리다"는 말이 훨씬 구체적으로 들리고, 3.11 이후 파이썬이 왜 갑자기 빨라졌는지도 숫자로 설명할 수 있게 된다.
:::

## 소스에서 실행까지

[3.6 AST](#/ast)에서 소스 코드가 파싱되어 트리가 되는 과정을 봤다. 그 트리는 실행되지 않는다. 트리는 다시 **바이트코드**(bytecode)로 컴파일되고, 그 바이트코드를 CPython의 `ceval.c` 안에 있는 거대한 반복문 — 흔히 **평가 루프**(evaluation loop)라고 부르는 것 — 이 하나씩 읽어서 실행한다.

```text nolines
소스 코드 (.py)
   │  tokenize + parse
   ▼
AST                    <- 3.6절에서 본 트리
   │  compile
   ▼
코드 객체 (code object) <- co_consts, co_varnames, co_code ...
   │  실행할 때마다
   ▼
바이트코드 실행 (ceval 루프)
```

함수를 정의하는 순간 이미 컴파일까지 끝나 있다. 함수 객체의 `__code__` 속성이 이 코드 객체다.

```pyrepl
>>> def add(a, b):
...     return a + b
...
>>> add.__code__
<code object add at 0x000002...>
>>> add.__code__.co_code
b'\x80\x00W\x01,\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00#\x00'
>>> len(add.__code__.co_code)
18
```

`co_code` 가 실제로 실행되는 원시 바이트열이다. 사람이 저 바이트열을 직접 읽는 건 고문이다. `dis` 모듈이 이걸 사람이 읽을 수 있는 니모닉으로 바꿔 준다.

```pyrepl
>>> import dis
>>> dis.dis(add)
  1           RESUME                   0
  2           LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (a, b)
              BINARY_OP                0 (+)
              RETURN_VALUE
```

이게 이 절에서 계속 쓸 도구다. (Python 3.14.5 기준 실측. `dis` 출력 형식은 버전마다 바뀐다 — 이 절의 모든 출력도 3.14 전용이다.)

## 스택 기반 가상머신

바이트코드를 읽으려면 CPython이 어떤 실행 모델을 쓰는지부터 알아야 한다. CPython은 **스택 기반 가상머신**(stack-based VM)이다. 레지스터가 없다. 모든 연산은 값을 스택에 밀어 넣고(push), 필요한 만큼 꺼내서(pop) 계산한 뒤, 결과를 다시 스택에 넣는 식으로 진행된다.

지역 변수가 아닌 전역 변수를 하나 섞은 함수로 이 흐름을 정확히 보자. (지역 변수 두 개를 연달아 읽으면 다음 절에서 볼 컴파일러 최적화가 끼어들어 그림이 복잡해진다.)

```python title="stack_demo.py"
G = 10

def calc(a):
    return a + G * a
```

```pyrepl
>>> dis.dis(calc, show_offsets=True)
  4          0       RESUME                   0
  5          2       LOAD_FAST_BORROW         0 (a)
             4       LOAD_GLOBAL              0 (G)
            14       LOAD_FAST_BORROW         0 (a)
            16       BINARY_OP                5 (*)
            28       BINARY_OP                0 (+)
            40       RETURN_VALUE
```

`show_offsets=True` 는 각 명령의 바이트 오프셋을 보여 준다. (기본값은 `False` 다 — 3.14에서도 그렇다. 3.10 이전에는 항상 표시됐다.) 이 흐름을 손으로 따라가면 스택이 이렇게 움직인다.

```text nolines
LOAD_FAST_BORROW a     스택: [a]
LOAD_GLOBAL G          스택: [a, G]
LOAD_FAST_BORROW a     스택: [a, G, a]
BINARY_OP *            G와 a를 꺼내 곱한 뒤 다시 넣는다 -> 스택: [a, G*a]
BINARY_OP +            a와 G*a를 꺼내 더한 뒤 다시 넣는다 -> 스택: [a+G*a]
RETURN_VALUE           스택에서 꺼내 반환한다
```

`RESUME` 은 모든 함수 바이트코드의 첫 명령이다. 시그널 처리나 추적(트레이싱) 도구가 이 함수에 개입할 준비가 됐는지 확인하는 진입점 역할을 한다. 신경 쓸 필요는 없지만, dis 출력에서 항상 보게 될 것이므로 정체는 알아 두자.

::: note LOAD_FAST_BORROW — 참조 카운트를 아끼는 컴파일러 최적화
바로 앞의 `add(a, b)` 예제에서 `LOAD_FAST_BORROW_LOAD_FAST_BORROW` 라는 낯선 이름을 봤을 것이다. 이건 3.13에서 들어온 컴파일 타임 최적화다. 원래 지역 변수를 읽는 명령은 `LOAD_FAST` 로, 참조 카운트를 하나 올린 사본을 스택에 놓는다. 그런데 그 변수가 함수 안에서 마지막으로 쓰이는 자리라면 참조 카운트를 올릴 필요가 없다 — 프레임이 어차피 곧 사라지며 그 이름표를 뗄 것이기 때문이다. 컴파일러가 이걸 정적으로 판단해서 더 싼 `LOAD_FAST_BORROW` 를 대신 넣는다.

거기다 두 개의 연속된 `LOAD_FAST_BORROW` 가 인접하면 **하나의 명령으로 합쳐진다** — `LOAD_FAST_BORROW_LOAD_FAST_BORROW`. 명령 하나를 디코드하고 분기하는 비용을 한 번만 치르고 두 값을 다 올린다. 이건 실행 중 관찰로 결정되는 다음 절의 적응형 특수화와는 다르다. **컴파일 시점에 정적으로 결정되는 고정된 최적화**다.
:::

## 코드 객체 안을 열어 보기

`dis.dis` 는 결국 코드 객체가 들고 있는 데이터를 읽어서 조립한 결과다. 코드 객체 자체를 직접 봐도 된다.

```pyrepl
>>> calc.__code__.co_consts
(None,)
>>> calc.__code__.co_varnames
('a',)
>>> calc.__code__.co_names
('G',)
```

`co_consts` 는 리터럴 상수 테이블, `co_varnames` 는 지역 변수 이름, `co_names` 는 전역/속성처럼 이름으로 조회하는 대상의 이름 테이블이다. `BINARY_OP 5 (*)` 의 `5` 는 어떤 연산인지를 가리키는 인자이고, `LOAD_GLOBAL 0 (G)` 의 `0` 은 `co_names` 의 인덱스다. [1.1 객체·이름·참조](#/objects-names)에서 REPL과 파일의 `is` 결과가 다르다고 했던 것도 결국 이 `co_consts` 가 **코드 객체 단위**로 만들어지기 때문이었다. 그 절의 마지막 퀴즈("`f.__code__.co_consts is g.__code__.co_consts` 가 왜 `True` 인가")도 여기서 다시 만난다 — 인자 없는 두 함수는 상수 테이블이 똑같이 `(None,)` 이라, 컴파일러가 같은 튜플 객체를 재사용하기도 한다.

## 3.11+ 적응형 특수화 인터프리터

여기부터가 이 절의 핵심이다. 3.11 이전까지 `BINARY_OP` 는 항상 같은 코드를 실행했다 — 피연산자가 `int` 든 `str` 이든 사용자 정의 클래스든, `__add__` 를 찾아 호출하는 일반적인 경로를 매번 탔다. 그런데 실제 코드에서 같은 줄은 거의 항상 같은 타입을 다룬다. 반복문 안의 `total += 1` 은 십만 번을 돌아도 `int` 만 만난다. **일반적인 경로를 매번 타는 건 낭비다.**

PEP 659(Specializing Adaptive Interpreter)가 3.11에서 이 낭비를 없앴다. 아이디어는 이렇다.

1. 처음 몇 번은 일반적인(generic) 바이트코드로 실행하면서 **어떤 타입이 나타나는지 관찰**한다.
2. 패턴이 안정적이면(예: 항상 `int + int`), 그 자리의 명령을 **더 빠른 특수화 버전**으로 몰래 바꿔치기한다.
3. 이후 그 타입 가정이 깨지면(다른 타입이 나타나면) 다시 일반 버전으로 되돌린다(deopt).

이 과정을 직접 관찰해 보자.

```python title="specialize_demo.py"
def add(a, b):
    return a + b
```

```pyrepl
>>> dis.dis(add, adaptive=True)      # 아직 한 번도 실행 전
  1           RESUME                   0
  2           LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (a, b)
              BINARY_OP                0 (+)
              RETURN_VALUE
>>> for _ in range(2000):
...     add(1, 2)
...
>>> dis.dis(add, adaptive=True)      # int로 2000번 실행한 뒤
  1           RESUME_CHECK             0
  2           LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (a, b)
              BINARY_OP_ADD_INT        0 (+)
              RETURN_VALUE
```

**같은 함수, 같은 소스인데 바이트코드 자체가 바뀌었다.** `RESUME` 이 `RESUME_CHECK` 로, `BINARY_OP` 이 `BINARY_OP_ADD_INT` 로 조용히 교체됐다. `adaptive=True` 를 주지 않으면 `dis.dis` 는 이 특수화를 숨기고 원래의 일반 형태만 보여준다 — 기본 출력이 실제 실행 중인 코드와 다를 수 있다는 뜻이다.

타입이 바뀌면 어떻게 될까.

```pyrepl
>>> for _ in range(2000):
...     add("x", "y")
...
>>> dis.dis(add, adaptive=True)
  1           RESUME_CHECK             0
  2           LOAD_FAST_BORROW_LOAD_FAST_BORROW 1 (a, b)
              BINARY_OP_ADD_UNICODE    0 (+)
              RETURN_VALUE
```

`BINARY_OP_ADD_INT` 가 `BINARY_OP_ADD_UNICODE` 로 바뀌었다. **같은 자리가 지금 관찰되는 타입에 맞춰 계속 재특수화된다.** 이게 "적응형"(adaptive)이라는 이름의 의미다. 한 번 섞어 부르면 즉시 되돌아가지는 않는다 — 특수화 가드가 실패해야 다시 관찰 모드로 내려가고, 새 패턴이 안정되면 다시 특수화된다. 이 안정화에는 약간의 호출 횟수가 필요하다.

::: deep 특수화는 어디에나 있다 — `opcode._specializations`
`BINARY_OP` 말고도 특수화되는 명령이 여럿이다. `opcode` 모듈이 그 대응표를 들고 있다.

```pyrepl
>>> import opcode
>>> len(opcode._specializations)
17
>>> opcode._specializations["LOAD_ATTR"]
['LOAD_ATTR_INSTANCE_VALUE', 'LOAD_ATTR_MODULE', 'LOAD_ATTR_WITH_HINT',
 'LOAD_ATTR_SLOT', 'LOAD_ATTR_CLASS', ...]
>>> opcode._specializations["FOR_ITER"]
['FOR_ITER_LIST', 'FOR_ITER_TUPLE', 'FOR_ITER_RANGE', 'FOR_ITER_GEN']
```

`FOR_ITER` 가 리스트를 도는지, `range` 를 도는지, 제너레이터를 도는지에 따라 다른 코드로 특수화된다는 뜻이다. `LOAD_ATTR` 은 더 흥미롭다. `p.x` 라는 같은 문법이 `p` 의 타입에 따라 완전히 다른 경로를 특수화해서 탄다.
:::

`LOAD_ATTR` 특수화는 [3.3 디스크립터](#/descriptors)와 직접 이어진다. 인스턴스 속성 접근은 원래 MRO를 훑고 디스크립터 프로토콜을 확인하는 일반적인 절차를 거친다. 하지만 클래스에 `__slots__`도, `property`도, 커스텀 `__getattr__`도 없는 평범한 인스턴스라면 그 절차는 매번 같은 결론(`인스턴스 딕셔너리에서 바로 찾는다`)에 도달한다.

```python title="attr_demo.py"
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def get_x(p):
    return p.x
```

```pyrepl
>>> p = Point(1, 2)
>>> dis.dis(get_x, adaptive=True)
  1           RESUME                   0
  2           LOAD_FAST_BORROW         0 (p)
              LOAD_ATTR                0 (x)
              RETURN_VALUE
>>> for _ in range(2000):
...     get_x(p)
...
>>> dis.dis(get_x, adaptive=True)
  1           RESUME_CHECK             0
  2           LOAD_FAST_BORROW         0 (p)
              LOAD_ATTR_INSTANCE_VALUE 0 (x)
              RETURN_VALUE
```

`LOAD_ATTR_INSTANCE_VALUE` 는 "MRO도, 디스크립터 검사도 다 건너뛰고 인스턴스 딕셔너리의 이 슬롯을 바로 읽어라"는 지름길이다. 만약 `Point.x` 가 [3.3 디스크립터](#/descriptors)에서 만든 `property` 였다면, 특수화는 `LOAD_ATTR_PROPERTY` 로 갈라진다 — 여전히 특수화는 되지만 지름길의 목적지가 다르다.

::: perf 실측: 모노모픽 vs 폴리모픽
특수화가 실제로 얼마나 이득인지 재 보자. 같은 `add(a, b)` 함수를 (1) 항상 `int` 로만 부르는 경우와 (2) `int`/`float` 를 번갈아 섞어 부르는 경우로 비교한다. 후자는 특수화가 안정되지 못하고 계속 흔들린다.

```python title="mono_vs_poly.py"
import timeit

def add(a, b):
    return a + b

mono = timeit.timeit(lambda: add(1, 2), number=2_000_000)

vals = [(1, 2), (1.0, 2.0)] * 1_000_000
it = iter(vals)
poly = timeit.timeit(lambda: add(*next(it)), number=2_000_000)

print(f"모노모픽: {mono/2e6*1e9:.1f} ns/call")
print(f"폴리모픽: {poly/2e6*1e9:.1f} ns/call")
```

```text nolines
모노모픽: 27.2 ns/call
폴리모픽: 47.5 ns/call
```

(Python 3.14.5 / Windows 기준 실측. 같은 스크립트를 같은 기기에서 반복 실행해도 모노모픽은 26~28 ns, 폴리모픽은 47~48 ns 사이에서 흔들린다 — 절대값은 실행마다, 그리고 기기마다 다르다. 하지만 **모노모픽이 폴리모픽보다 확연히 빠르다**는 방향과 약 1.7배 안팎이라는 격차의 크기는 반복 실행에서도, 다른 기기에서도 안정적으로 재현된다.) 폴리모픽 호출은 매번 타입 가드가 실패해서 특수화된 지름길을 못 쓰고 일반 경로로 되돌아가기 때문이다. 측정 방법론 자체는 [5.1 측정 없이 최적화 없다](#/profiling)에서 더 다룬다.
:::

::: hist 왜 3.11에 와서야 이런 걸 했나
CPython은 오랫동안 "정확성 먼저, 속도는 나중"이라는 원칙으로 발전했다. 타입을 추측해서 지름길을 타는 방식은 자칫 잘못 구현하면 **미묘하게 틀린 결과**를 낼 위험이 있다 — 이건 JIT을 쓰는 언어들이 늘 씨름하는 문제다. PEP 659는 이 위험을 **가드(guard) 검사**로 막는다. 특수화된 명령은 실행 전에 항상 "가정이 여전히 맞는가"를 확인하고, 틀리면 즉시 일반 경로로 물러난다. 그래서 특수화는 순수한 성능 최적화이고, 어떤 파이썬 코드도 그 결과가 달라지지 않는다. 3.11의 "Faster CPython" 프로젝트가 이 설계를 실용적인 수준까지 끌어올렸다.
:::

## PEP 709: 컴프리헨션 인라인을 바이트코드로 확인

[1.9 컴프리헨션](#/comprehensions)에서 3.12부터 리스트·딕트·셋 컴프리헨션이 **별도의 함수 프레임을 만들지 않는다**고 배웠다. 그 절에서 약속한 대로, 여기서 바이트코드로 직접 확인한다.

```python title="inline_check.py"
def inlined(data):
    return [x * 2 for x in data]
```

```pyrepl
>>> inlined.__code__.co_consts
(2,)
```

`co_consts` 에 `<listcomp>` 라는 이름의 코드 객체가 **없다.** 상수 `2` 하나뿐이다. 컴프리헨션이 독립된 코드 객체로 컴파일되지 않고, 감싸는 함수의 바이트코드 안에 **그대로 풀어져 들어갔다**는 뜻이다. 실제로 확인해 보자.

```pyrepl
>>> dis.dis(inlined)
  1           RESUME                   0
  2           LOAD_FAST_BORROW         0 (data)
              GET_ITER
              LOAD_FAST_AND_CLEAR      1 (x)
              SWAP                     2
      L1:     BUILD_LIST               0
              SWAP                     2
      L2:     FOR_ITER                11 (to L3)
              STORE_FAST_LOAD_FAST    17 (x, x)
              LOAD_SMALL_INT           2
              BINARY_OP                5 (*)
              LIST_APPEND              2
              JUMP_BACKWARD           13 (to L2)
      L3:     END_FOR
              ...
```

`BUILD_LIST`, `FOR_ITER`, `LIST_APPEND` 가 **`inlined` 함수 자신의 바이트코드 안에** 그대로 나열돼 있다. `<listcomp>` 를 호출하는 `CALL` 명령이 없다. 비교를 위해, 3.11 이전이 실제로 하던 일 — 컴프리헨션을 별도 함수로 만들어 즉시 호출하는 것 — 을 손으로 재현해 보자.

```python title="framed_equivalent.py"
def framed(data):
    def _listcomp(it):
        result = []
        for x in it:
            result.append(x * 2)
        return result
    return _listcomp(data)
```

```pyrepl
>>> framed.__code__.co_consts
(<code object _listcomp at 0x...>,)
```

`framed` 의 `co_consts` 에는 **코드 객체가 들어 있다.** 호출할 때마다 이 코드 객체로 새 함수 객체를 만들고(`MAKE_FUNCTION`), 새 프레임을 열어 호출하고(`CALL`), 닫는다. `inlined` 는 이 과정 전체를 생략한다. [1.9 컴프리헨션](#/comprehensions)에서 실측한 "컴프리헨션 한 번당 약 15ns 절약"이 바로 이 프레임 생략에서 나온다 — 이 절이 다루는 게 정확히 그 프레임의 정체다.

::: warn 제너레이터 표현식은 예외다
같은 이유로 제너레이터 표현식(`(x for x in data)`)은 인라인되지 **않는다.** `dis.dis` 로 직접 확인하면 여전히 `<genexpr>` 코드 객체가 `co_consts` 에 남아 있다. 제너레이터는 `yield` 로 멈췄다가 나중에 재개해야 하므로, 그 상태를 담을 자기만의 프레임이 반드시 있어야 한다. [1.18 이터레이터](#/iterators)에서 본 제너레이터의 정체 — 멈출 수 있는 함수 — 가 여기서 프레임을 놓지 못하는 이유이기도 하다.
:::

## 언제 dis를 열어 봐야 하고, 언제 손대지 말아야 하는가

`dis` 는 진단 도구지 설계 도구가 아니다. 쓸 자리와 쓰지 말아야 할 자리를 분명히 구분해야 한다.

**쓸 자리:**

- 왜 이 코드가 예상보다 느린지 감이 안 잡힐 때, 실제로 어떤 연산이 반복되는지 확인한다.
- `+=` 가 왜 어떤 타입에선 제자리 수정이고 어떤 타입에선 새 객체를 만드는지 — [1.1 객체·이름·참조](#/objects-names)의 `__iadd__` 이야기를 바이트코드 수준(`BINARY_OP` vs 없음, `STORE_FAST` 유무)으로 다시 확인할 때.
- 라이브러리나 컴파일러 최적화(예: PEP 709)가 실제로 적용됐는지 검증할 때.
- `dis.dis` 에 함수를 넣었는데 예상한 명령이 하나도 없다면, 애초에 그 코드가 실행되는 경로가 아니라는 뜻이다 — 이건 죽은 코드를 찾는 의외로 쓸모 있는 방법이다.

::: danger 하지 말아야 할 것
1. **바이트코드 명령 개수를 세서 "이 코드가 더 빠르다"고 결론 내리지 마라.** 명령 하나의 비용은 종류마다 천차만별이고, 적응형 특수화 때문에 "지금 이 순간의 바이트코드"는 다음 호출에서 또 바뀐다. 실제 속도는 반드시 `timeit` 으로 측정해야 한다. [5.1 측정 없이 최적화 없다](#/profiling).
2. **`opcode._specializations` 나 `LOAD_ATTR_INSTANCE_VALUE` 같은 내부 이름에 코드가 의존하게 만들지 마라.** 이건 공개 API가 아니다. 이름과 존재 여부가 마이너 버전 사이에서도 바뀐다. 이 절의 모든 출력이 "3.14.5 기준"이라고 못 박은 이유다.
3. **"바이트코드를 줄이려고" 코드를 억지로 비틀지 마라.** 가독성을 버리고 얻는 이득은 대개 노이즈 수준이다. 진짜 병목은 알고리즘의 복잡도이거나 자료구조 선택인 경우가 압도적으로 많다. [7.2 파이썬 자료구조의 실제 비용](#/py-ds-cost)에서 다루는 것들이 여기서 아무리 바이트코드를 들여다봐도 안 보이는 진짜 비용이다.
4. **디버깅 중 호기심으로 여는 건 얼마든지 좋다.** 문제는 그 결과를 근거로 프로덕션 코드의 구조를 바꾸는 것이다.
:::

::: tip AST/바이트코드/특수화를 헷갈리지 않는 법
세 도구는 층이 다르다. **`ast`**([3.6](#/ast))는 문법 구조를 본다 — 코드가 실행되기 *전에* 무엇을 하려는지. **`dis`** 는 그 구조가 컴파일된 뒤의 실행 단위를 본다 — 실제로 어떤 순서로 스택을 조작하는지. **적응형 특수화**는 그 실행 단위가 *런타임에 관찰한 타입에 맞춰* 어떻게 바뀌는지를 본다. 디버깅할 때 "왜 이렇게 동작하지?"는 대개 AST나 dis 층에서 풀리고, "왜 이렇게 느리지?"는 대개 특수화 층이나 그 바깥의 알고리즘 층에서 풀린다.
:::

## 요약

- 파이썬 소스는 AST([3.6](#/ast))를 거쳐 **바이트코드**로 컴파일되고, `ceval` 평가 루프가 그것을 하나씩 실행한다.
- CPython은 **스택 기반 가상머신**이다. 대부분의 명령은 스택에서 값을 꺼내 계산하고 결과를 다시 스택에 올린다.
- `dis.dis(func, show_offsets=True)` 로 바이트코드를, `func.__code__.co_consts/co_varnames/co_names` 로 그 재료를 직접 볼 수 있다.
- 3.11+ 는 **적응형 특수화 인터프리터**(PEP 659)를 쓴다. 같은 함수가 몇 번 실행된 뒤 관찰된 타입에 맞춰 `BINARY_OP` → `BINARY_OP_ADD_INT`, `LOAD_ATTR` → `LOAD_ATTR_INSTANCE_VALUE` 같은 더 빠른 버전으로 **조용히 교체**된다. `dis.dis(..., adaptive=True)` 로 이 교체를 직접 볼 수 있다.
- 타입이 안정적이면(모노모픽) 빠르고, 계속 바뀌면(폴리모픽) 특수화가 무력화된다. 실측 약 1.7배 차이.
- 3.12의 PEP 709(컴프리헨션 인라인, [1.9](#/comprehensions))는 `co_consts` 에서 `<listcomp>` 코드 객체가 사라진 것으로 바이트코드 수준에서 직접 확인된다.
- `dis` 는 진단 도구다. 이 도구가 보여 주는 내부 이름에 코드가 의존하게 만들지 마라 — 마이너 버전마다 바뀐다.

::: quiz 연습문제
1. 다음 함수를 `dis.dis(f, adaptive=True)` 로 실행 전/후 비교하라. 2000번 호출한 뒤 어떤 명령이 어떤 특수화 명령으로 바뀌는지 직접 확인하라.

   ```python
   def double(n):
       return n * 2
   ```

2. `sub(a, b): return a - b` 를 만들고, 처음 2000번은 `int` 로, 다음 2000번은 `str` 이 아니라 **커스텀 `__sub__` 를 정의한 클래스**로 호출하라. 두 번째 구간에서 `BINARY_OP` 가 특수화되지 않고 일반 형태로 남는 이유를 `opcode._specializations["BINARY_OP"]` 목록을 보고 설명하라.
3. `[i for i in range(5)]` 를 담은 함수와 `(i for i in range(5))` 를 담은 함수 각각의 `__code__.co_consts` 를 비교하라. 어느 쪽에 코드 객체가 남아 있고, 왜인지 이 절의 내용으로 설명하라.
4. [1.1 객체·이름·참조](#/objects-names)에서 본 `t[0] += [9]` (튜플 안의 리스트) 예제를 `dis.dis` 로 열어 보라. `BINARY_OP`(또는 이에 해당하는 제자리 연산 명령) 다음에 나오는 `STORE_SUBSCR` 류 명령이 왜 `TypeError` 를 내는지, 그런데도 리스트는 왜 이미 바뀌어 있는지를 바이트코드 순서로 설명하라.
5. `LOAD_ATTR_INSTANCE_VALUE` 로 특수화된 함수에, 도중에 [3.3 디스크립터](#/descriptors)의 `property` 를 가진 다른 클래스의 인스턴스를 넣어 호출하면 어떤 일이 벌어질지 예측하고 실행해서 확인하라.
:::

**다음 절**: [4.1 동시성 모델 지도](#/concurrency-map) — GIL 아래에서 스레드가 실제로 무엇을 하고 있었는지, 그리고 free-threaded 파이썬이 무엇을 바꾸는지.
