# 1.8 제어 흐름과 match 문

::: lead
이 절은 두 가지를 한다. 하나는 당신이 매일 쓰는 `if`, `and`, `for`가 실제로는 당신이 생각하는 것과 다르게 동작한다는 걸 보여주는 것이다. `and` 는 불리언을 반환하지 않고, `for-else` 의 `else` 는 이름이 틀렸으며, `if x:` 는 `__bool__` 이 아니라 `__len__` 을 부를 수도 있다. 다른 하나는 3.10에 들어온 `match` 문이다. 이건 switch가 아니다. **switch라고 생각하고 쓰면 느리고, 조용히 틀린다.**
:::

## 문제부터

다음 세 코드의 출력을 예측해 보라.

```python
# ①
print(True and [] or "기본값")

# ②
RED = 1
def color_name(c):
    match c:
        case RED:
            return "빨강"
print(color_name(999), RED)

# ③
for i in []:
    pass
else:
    print("else 실행됨")
```

답은 순서대로 `"기본값"`, `("빨강", 1)`, 그리고 `"else 실행됨"` 이다. 세 개 다 예측했다면 이 절은 복습이다. 하나라도 틀렸다면 읽어라. ②는 실제 프로덕션 코드에서 나오는 버그다.

## 진리값 — 파이썬은 무엇을 참으로 보는가

`if x:` 를 쓸 때 파이썬은 `x` 를 불리언으로 바꾼다. 이 변환에는 정해진 순서가 있다.

```text nolines
bool(x)
   │
   ├─ 1. has type(x).__bool__ ?  ──yes──▶ 호출. 반환값이 곧 답이다.
   │                                      bool 이 아니면 TypeError
   ├─ 2. has type(x).__len__  ?  ──yes──▶ 호출. 0이면 False, 아니면 True
   │
   └─ 3. neither                 ──────▶ 무조건 True
```

세 번째 줄이 중요하다. **아무것도 정의하지 않은 객체는 항상 참이다.** 그래서 사용자 정의 클래스의 인스턴스는 기본적으로 truthy다.

```pyrepl
>>> class Plain: pass
...
>>> bool(Plain())
True
```

`__bool__` 이 `__len__` 보다 우선한다. 둘 다 있으면 `__len__` 은 아예 호출되지 않는다.

```pyrepl
>>> class Both:
...     def __bool__(self):
...         print("__bool__ 호출"); return True
...     def __len__(self):
...         print("__len__ 호출"); return 0
...
>>> bool(Both())
__bool__ 호출
True
```

::: deep 프로토콜의 계약은 생각보다 빡빡하다
`__bool__` 과 `__len__` 은 아무 값이나 반환할 수 없다. CPython이 실제로 검사한다.

```pyrepl
>>> class BadBool:
...     def __bool__(self): return 1
...
>>> bool(BadBool())
TypeError: __bool__ should return bool, returned int
```

`1` 은 truthy인데도 거부된다. `__bool__` 은 **정확히 `bool` 타입**을 반환해야 한다.

`__len__` 은 더 재밌다.

```pyrepl
>>> class BadLen:
...     def __len__(self): return -1
...
>>> bool(BadLen())
ValueError: __len__() should return >= 0

>>> class BigLen:
...     def __len__(self): return 2**63
...
>>> bool(BigLen())
OverflowError: cannot fit 'int' into an index-sized integer
```

`__len__` 의 반환값은 C 레벨에서 `Py_ssize_t` 에 담긴다. 그래서 음수도, 플랫폼 워드 크기를 넘는 수도 안 된다. 길이가 $2^{63}$ 을 넘는 지연 컬렉션을 만들고 싶다면 `__len__` 대신 `__bool__` 을 직접 정의하거나 `__length_hint__` 를 써야 한다. ([1.14 특수 메서드](#/dunder))
:::

### 무엇이 거짓인가

파이썬의 falsy 값은 다음이 전부다.

| 분류 | 값 |
| --- | --- |
| 상수 | `None`, `False` |
| 0 | `0`, `0.0`, `0j`, `Decimal(0)`, `Fraction(0, 1)` |
| 빈 시퀀스 | `''`, `()`, `[]`, `b''`, `bytearray()`, `range(0)` |
| 빈 컬렉션 | `{}`, `set()`, `frozenset()` |

나머지는 전부 참이다. 헷갈리는 것들을 직접 확인해 보자.

```pyrepl
>>> bool(float('nan'))
True
>>> bool('0')
True
>>> bool('False')
True
>>> bool([0])
True
>>> bool((0,))
True
>>> bool(Decimal('-0.0'))
False
```

`nan` 이 참이라는 게 처음엔 이상하다. 하지만 `nan` 은 "0이 아닌 float"이고, `__bool__` 은 `x != 0` 을 볼 뿐이다. `nan != 0` 은 참이다. ([1.2 숫자](#/numbers))

::: danger 진리값 검사가 예외를 던지는 객체가 있다
NumPy 배열은 `__bool__` 이 **예외를 던진다.**

```pyrepl
>>> import numpy as np
>>> a = np.array([1, 2, 3])
>>> if a:
...     pass
ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()
```

빈 배열도 마찬가지다.

```pyrepl
>>> bool(np.array([]))
ValueError: The truth value of an empty array is ambiguous. Use `array.size > 0` to check that an array is not empty.
```

이유는 설계 철학이다. `a` 가 배열일 때 "참인가?"는 질문 자체가 모호하다 — 전부 참인가? 하나라도 참인가? NumPy는 답을 추측하지 않고 거부한다.

그래서 **함수 인자가 배열일 수 있는 코드에서 `if arr:` 를 쓰면 안 된다.** `if arr is not None:` 이나 `if len(arr):` 를 써라. 이건 [9.1 NumPy](#/numpy-basics)에서 다시 만난다. pandas의 `Series`/`DataFrame` 도 같다.
:::

::: perf if x: 가 if len(x) > 0: 보다 빠르다
```python title="측정"
import timeit
setup = "x = [1, 2, 3]"
timeit.repeat("if x: pass",           setup, number=1_000_000)   # 5.4 ns/회
timeit.repeat("if len(x): pass",      setup, number=1_000_000)   # 9.9 ns/회
timeit.repeat("if len(x) > 0: pass",  setup, number=1_000_000)   # 13.7 ns/회
timeit.repeat("if x != []: pass",     setup, number=1_000_000)   # 16.3 ns/회
```

(Python 3.14.5 / Windows 실측. 절대값은 기기마다 다르지만 순서와 배수는 어디서나 같다.)

**약 2.5배 차이다.** 이유는 바이트코드를 보면 명확하다.

```pyrepl
>>> import dis
>>> dis.dis(compile("if x: pass", "<s>", "exec"))
  LOAD_NAME                0 (x)
  TO_BOOL
  POP_JUMP_IF_FALSE        3 (to L1)
```

`if x:` 는 `TO_BOOL` 하나다. `if len(x) > 0:` 은 `LOAD_NAME(len)` + `PUSH_NULL` + `CALL` + `LOAD_SMALL_INT` + `COMPARE_OP` — 전역 이름 조회와 함수 호출이 추가된다.

여기서 한 층 더 내려가면 진짜 이유가 나온다. **`TO_BOOL` 은 적응형 특수화(adaptive specialization) 대상이다.** 같은 타입이 반복해서 들어오면 인터프리터가 명령어 자체를 바꿔 치운다.

```pyrepl
>>> def f(x):
...     if x: return 1
...     return 0
...
>>> for _ in range(200): f([1])
...
>>> dis.dis(f, adaptive=True)
  LOAD_FAST_BORROW         0 (x)
  TO_BOOL_LIST                       # ← TO_BOOL 이 아니다!
  POP_JUMP_IF_FALSE        3 (to L1)
```

`TO_BOOL_LIST` 는 타입 확인 한 번 + `ob_size != 0` 검사가 전부다. `__bool__`/`__len__` 탐색을 통째로 건너뛴다. `TO_BOOL_INT`, `TO_BOOL_STR`, `TO_BOOL_NONE`, `TO_BOOL_BOOL` 도 있다. 3.11에서 도입된 이 특수화 인터프리터 이야기는 [3.7 바이트코드](#/bytecode)에서 본격적으로 다룬다.

`len(x) > 0` 은 이 최적화를 통째로 놓친다. **관용구를 쓰는 게 빠른 게 아니라, 관용구가 최적화 대상이라서 빠른 거다.**
:::

## `and` / `or` 는 불리언을 반환하지 않는다

이걸 모르는 사람이 많다.

```pyrepl
>>> 1 and 2
2
>>> 0 or [] or "x" or None
'x'
>>> repr(0 or "")
"''"
```

정확한 규칙은 이렇다.

- `a and b` — `a` 가 거짓이면 **`a` 를** 반환. 아니면 `b` 를 평가해서 반환.
- `a or b` — `a` 가 참이면 **`a` 를** 반환. 아니면 `b` 를 평가해서 반환.

**반환되는 건 항상 피연산자 중 하나다.** `True`/`False` 가 아니다. 그리고 두 번째 피연산자는 **필요할 때만 평가된다** — 이게 단축 평가(short-circuit)다.

```pyrepl
>>> [] and 1/0        # 1/0 이 아예 평가되지 않는다
[]
>>> "a" or 1/0
'a'
```

바이트코드가 이 사실을 그대로 보여준다.

```pyrepl
>>> dis.dis("x = a and b")
  LOAD_NAME                0 (a)
  COPY                     1          # a 를 복제해 둔다
  TO_BOOL
  POP_JUMP_IF_FALSE        3 (to L1)  # 거짓이면 복제해 둔 a 를 남기고 점프
  NOT_TAKEN
  POP_TOP                             # 참이면 a 를 버리고
  LOAD_NAME                1 (b)      # b 를 올린다
L1:
  STORE_NAME               2 (x)
```

`COPY 1` 로 `a` 를 복제해 두고, `TO_BOOL` 로 진리값만 판정한 뒤, 스택에 남는 건 **원래 `a` 객체**다. 진리값 판정과 반환값이 분리돼 있다.

::: danger and/or 로 삼항 연산자를 흉내내지 마라
C의 `cond ? x : y` 를 흉내내려고 `cond and x or y` 를 쓰는 관용구가 있다. **`x` 가 falsy면 조용히 틀린다.**

```pyrepl
>>> v = 0
>>> True and v or "기본값"      # ❌ v를 원했는데
'기본값'
>>> v if True else "기본값"     # ✅
0
```

이건 파이썬 2.5 이전, 조건 표현식이 없던 시절의 유물이다. 지금 쓰면 버그다.

같은 병이 `or` 로 기본값을 채울 때도 나온다.

```python
name = user_input or "익명"        # 빈 문자열도 "익명"이 된다
port = config.get("port") or 8080  # ❌ port=0 을 설정하면 8080이 된다
port = config.get("port", 8080)    # ✅ 키가 없을 때만 8080
```

`or` 기본값은 **"falsy면 전부 기본값"** 이라는 뜻이다. `0`, `""`, `[]`, `False` 가 유효한 값일 수 있는 자리에서는 쓰면 안 된다. "값이 없을 때"를 뜻하려면 `is None` 을 명시해라.

```python
port = config["port"] if config.get("port") is not None else 8080
```
:::

### 연쇄 비교

`a < b < c` 는 `(a < b) and (b < c)` 로 펼쳐진다. 그런데 **`b` 는 한 번만 평가된다.**

```pyrepl
>>> def f():
...     print("f() 평가")
...     return 5
...
>>> 1 < f() < 10
f() 평가
True
```

`(1 < f()) and (f() < 10)` 이었다면 `f()` 가 두 번 불렸을 것이다. 컴파일러가 중간값을 스택에 복제해 둔다. 그래서 **부작용이 있는 함수도 연쇄 비교에서는 안전하다.**

이 규칙 때문에 생기는 함정도 있다.

```pyrepl
>>> False == False in [False]      # (False == False) and (False in [False])
True
>>> x = 1
>>> x is not None == True          # (x is not None) and (None == True)
False
```

두 번째가 무섭다. `x is not None == True` 는 사람이 읽으면 `(x is not None) == True` 같지만, 실제로는 `(x is not None) and (None == True)` 다. `None == True` 는 거짓이므로 결과는 항상 `False`. **`is`, `in`, `==`, `<` 는 전부 같은 우선순위의 비교 연산자라 서로 연쇄된다.**

## 조건 표현식

```python
value = x if cond else y
```

`cond` 가 먼저 평가된다. 그 다음 `x` 나 `y` 중 **하나만** 평가된다.

읽는 순서가 뒤죽박죽인 건 사실이다(가운데 → 왼쪽 → 오른쪽). 이 문법은 파이썬 2.5에서 도입될 때 격렬한 논쟁 끝에 정해졌고, 최종 결정은 귀도가 직접 했다.

::: warn 조건 표현식은 우선순위가 거의 최하위다
`lambda` 를 빼면 가장 낮다. 그래서 이렇게 된다.

```pyrepl
>>> x = 5
>>> 1 + 1 if x > 3 else 100
2
```

`1 + (1 if x > 3 else 100)` 이 아니라 `(1 + 1) if x > 3 else 100` 이다. 결과가 `2` 인 게 우연히 같아 보이지만, `x = 1` 이면 `100` 이 나온다.

**콤마보다도 낮다는 게 진짜 함정이다.**

```pyrepl
>>> [1 if True else 2, 3]
[1, 3]
```

`[(1 if True else 2), 3]` 으로 파싱된다. 리스트 원소가 2개다. 의도가 다르면 괄호를 쳐라. **조건 표현식은 항상 괄호로 감싸는 습관이 안전하다.**
:::

중첩은 왼쪽부터 읽는다. `if-elif-else` 와 순서가 같다.

```python
grade = "A" if s >= 90 else "B" if s >= 80 else "C"
```

두 단계까지가 한계다. 세 단계부터는 `if` 문이나 `match` 를 써라.

## `for-else` 와 `while-else` — 이름이 잘못됐다

파이썬에서 가장 널리 오해받는 문법이다. 절반의 사람이 "루프가 한 번도 안 돌면 `else`" 라고 잘못 안다.

```pyrepl
>>> for i in []:
...     pass
... else:
...     print("else 실행됨")
...
else 실행됨
```

빈 시퀀스에서도 `else` 가 실행된다. 정확한 규칙은 하나뿐이다.

> **`break` 없이 루프가 끝나면 `else` 가 실행된다.**

`else` 가 아니라 `nobreak` 였어야 한다. 귀도 본인도 이걸 후회한다고 밝힌 적이 있다.

```text nolines
   for ... :               while cond :
       body                    body
   else:                   else:
       run                     run
   ^^^^                    ^^^^
    └── break 로 빠져나오지 않았을 때만 실행된다
```

::: hist 왜 else 라는 단어를 골랐나
`try/except/else` 의 `else` 와 같은 뜻으로 고른 것이다 — "예외적인 탈출 경로를 타지 않았다면". `try` 에서는 `except` 가, 루프에서는 `break` 가 그 탈출 경로다.

그런데 사람들의 머릿속에는 `if/else` 가 먼저 박혀 있다. 그래서 `for` 옆의 `else` 를 보면 반사적으로 `if/else` 로 읽는다. **비유가 틀리면 잘못된 모델이 심긴다.** 이게 그 교과서적 사례다.
:::

`break` 만이 `else` 를 막는다. `continue` 는 막지 못한다. `return` 과 예외는 애초에 루프 밖으로 나가므로 `else` 를 실행할 기회 자체가 없다.

```pyrepl
>>> for i in [1, 2]:
...     continue
... else:
...     print("continue 후에도 else 실행")
...
continue 후에도 else 실행
```

```pyrepl
>>> n = 0
>>> while n < 3:
...     n += 1
... else:
...     print("while-else 실행, n =", n)
...
while-else 실행, n = 3
```

### 그럼 언제 쓰나

**"찾았는가?"를 표현할 때다.** 이게 사실상 유일한 정당한 용도다.

```python title="플래그 변수를 지우는 패턴"
# ❌ 플래그
found = False
for item in items:
    if item.id == target:
        found = True
        break
if not found:
    raise KeyError(target)

# ✅ for-else
for item in items:
    if item.id == target:
        break
else:
    raise KeyError(target)
```

::: cote 코딩테스트 포인트
백트래킹과 소수 판정에서 `for-else` 가 코드를 줄여 준다.

```python title="약수 탐색"
def is_prime(n):
    if n < 2:
        return False
    for d in range(2, int(n**0.5) + 1):
        if n % d == 0:
            return False          # 여기선 return 이 더 명확하다
    return True
```

`return` 을 쓸 수 있으면 `return` 이 낫다. `for-else` 가 진짜로 이기는 건 **함수 안이 아니라 루프 안에서, 중첩 루프의 안쪽을 다 돌았는지 판정할 때**다.

```python title="N-Queen 류: 안쪽 루프가 전부 통과했을 때만 배치"
for col in range(n):
    for r, c in placed:
        if conflicts(row, col, r, c):
            break
    else:
        placed.append((row, col))    # 충돌이 하나도 없었다
        ...
```

플래그 변수 하나가 사라진다. [7.18 백트래킹](#/backtracking)에서 이 패턴을 다시 쓴다.

**단, 팀 코드에서는 신중해라.** `for-else` 는 읽는 사람의 절반이 오해한다. 시험장 코드는 괜찮고, 리뷰 받는 코드에서는 주석을 달아라.
:::

::: warn 루프 변수는 루프가 끝나도 남는다
```pyrepl
>>> for k in range(3):
...     pass
...
>>> k
2
```

파이썬의 `for` 는 새 스코프를 만들지 않는다. 루프 변수는 **바깥 스코프에 그대로 남는다.** C++/Java 를 하다 오면 걸린다.

빈 시퀀스면 아예 정의되지 않는다는 것도 함정이다.

```python
for k in []:
    pass
print(k)          # NameError (앞에 k가 없었다면)
```

**루프 변수를 루프 밖에서 쓰는 코드는 이 두 함정 사이에 낀다.** 컴프리헨션은 이 문제가 없다 — 자기만의 스코프를 만든다. ([1.9 컴프리헨션](#/comprehensions))
:::

## 대입 표현식 (walrus)

`:=` 는 **값을 반환하는 대입**이다. 3.8에서 PEP 572로 들어왔고, 그 논쟁 때문에 귀도가 BDFL에서 물러났다.

쓸 자리는 사실상 세 개다.

```python title="① 조건에서 쓰고 바로 재사용"
if (m := re.match(r"\d+", s)):
    print(m.group())          # m 을 다시 계산하지 않는다
```

```python title="② while 루프의 읽기 패턴"
while (chunk := f.read(8192)):
    process(chunk)

# 이게 없던 시절:
while True:
    chunk = f.read(8192)
    if not chunk:
        break
    process(chunk)
```

```python title="③ 컴프리헨션의 중복 계산 제거"
# ❌ cost() 를 두 번 호출한다
result = [cost(x) for x in data if cost(x) > 100]

# ✅ 한 번만
result = [y for x in data if (y := cost(x)) > 100]
```

::: perf ③의 실제 이득
```python title="측정"
data = list(range(1000))
def cost(v): return v*v + 1

timeit.repeat("[cost(x) for x in data if cost(x) > 100]",       number=2000)  # 59.0 us
timeit.repeat("[y for x in data if (y := cost(x)) > 100]",      number=2000)  # 39.6 us
```

**약 1.5배.** `cost` 가 비쌀수록 2배에 가까워진다 — 호출 횟수가 절반이 되니까. 반대로 `cost` 가 싸면 walrus 자체 오버헤드로 이득이 줄어든다. 여기서 얻는 교훈은 "walrus 를 쓰면 빨라진다"가 아니라 **"중복 계산이 있는지 보라"** 다. ([5.1 프로파일링](#/profiling))
:::

::: deep 컴프리헨션 안의 walrus 는 바깥 스코프에 바인딩된다
컴프리헨션은 자기만의 스코프를 갖는다. 그런데 **walrus 만은 예외적으로 바깥에 쓴다.** PEP 572가 명시적으로 그렇게 정했다.

```pyrepl
>>> data = [1, 2, 3]
>>> res = [y for x in data if (y := x * 2) > 2]
>>> res
[4, 6]
>>> y
6                     # 바깥에 남았다 (마지막 값)
>>> x
NameError: name 'x' is not defined      # for 타깃은 안 남는다
```

같은 자리에서 `y` 는 새고 `x` 는 안 샌다. 일관성이 없어 보이지만 의도된 설계다. `any(...)`/`all(...)` 에서 "성공시킨 원소"를 꺼내 오라는 것이다.

```python
if any((match := p).matches(s) for p in patterns):
    print(match)      # 성공시킨 패턴을 꺼낼 수 있다
```

**대신 문법이 몇 가지를 금지한다.** 애매한 코드를 컴파일 단계에서 막는다.

```pyrepl
>>> [(i := i + 1) for i in range(3)]
SyntaxError: assignment expression cannot rebind comprehension iteration variable 'i'

>>> class C:
...     vals = [1, 2]
...     r = [(t := v) for v in vals]
SyntaxError: assignment expression within a comprehension cannot be used in a class body
```

두 번째는 클래스 바디가 이미 특수한 스코프라서, "바깥에 쓴다"의 바깥이 어디인지 정의할 수 없기 때문이다.
:::

마지막으로, `:=` 는 문장 자리에 올 수 없다.

```pyrepl
>>> x := 1
SyntaxError: invalid syntax
```

일부러 막았다. `=` 와 `:=` 가 같은 자리에서 경쟁하면 `==` 를 `=` 로 잘못 쓴 C의 고전적 버그가 파이썬에 들어온다. **`:=` 는 표현식이 오는 자리에만 쓸 수 있다.** 굳이 쓰려면 괄호를 쳐야 한다: `(x := 1)`.

## `match` 는 switch가 아니다

이제 이 절의 본론이다. `match` 는 3.10에 PEP 634/635/636으로 들어왔다. **switch를 늦게 추가한 게 아니다.** 파이썬은 switch를 20년 넘게 거부했고 (PEP 275, PEP 3103 모두 기각), 지금도 switch는 없다.

들어온 건 **구조적 패턴 매칭**(structural pattern matching)이다. 하스켈/러스트/스칼라 계열의 그것이다. 값을 비교하는 게 아니라 **구조를 분해한다.**

이 차이를 먼저 몸으로 느껴야 한다.

```python title="switch 로 쓸 수 없는 것"
def handle(msg):
    match msg:
        case {"type": "move", "pos": [float(x), float(y)]}:
            return f"이동 ({x}, {y})"
        case {"type": "say", "text": str(t)} if len(t) < 10:
            return f"말: {t}"
        case {"type": "batch", "items": [*items]}:
            return [handle(i) for i in items]
        case {"type": str(t)}:
            return f"모르는 타입 {t}"
        case _:
            return "형식 오류"
```

```pyrepl
>>> handle({"type": "move", "pos": [1.0, 2.0]})
'이동 (1.0, 2.0)'
>>> handle({"type": "batch", "items": [{"type": "say", "text": "a"}, {"type": "nope"}]})
['말: a', '모르는 타입 nope']
>>> handle([1, 2])
'형식 오류'
```

한 줄에 **타입 검사 + 구조 분해 + 변수 바인딩 + 조건**이 다 들어 있다. 이걸 `if` 로 쓰면 열 배 길어진다.

### 패턴의 전체 목록

| 패턴 | 예 | 하는 일 |
| --- | --- | --- |
| 리터럴 | `case 42:` `case "a":` | `==` 로 비교 (단, `None`/`True`/`False` 는 `is`) |
| 캡처 | `case n:` | **항상 매치**하고 이름에 바인딩 |
| 와일드카드 | `case _:` | 항상 매치, 바인딩 안 함 |
| 값 | `case Color.RED:` | **점이 있어야 한다.** `==` 로 비교 |
| 시퀀스 | `case [a, b, *rest]:` | 길이 확인 + 원소 분해 |
| 매핑 | `case {"k": v, **rest}:` | **부분 매치** + 키 조회 |
| 클래스 | `case Point(x, y=0):` | `isinstance` + 속성 분해 |
| Or | `case 1 \| 2 \| 3:` | 왼쪽부터, 첫 성공 |
| As | `case [x] as whole:` | 하위 패턴 결과를 통째로 바인딩 |
| 가드 | `case n if n > 0:` | 매치 **성공 후** 조건 검사 |

### 함정 1 — 이름은 비교가 아니라 캡처다

이게 `match` 최대의 함정이다. 절 첫머리 문제 ②의 답이다.

```pyrepl
>>> RED = 1
>>> def color_name(c):
...     match c:
...         case RED:
...             return f"빨강 (RED={RED})"
...
>>> color_name(999)
'빨강 (RED=999)'
```

`case RED:` 는 "`c` 가 전역 `RED` 와 같은가?"가 **아니다.** "`c` 를 `RED` 라는 이름에 바인딩하라"다. 그래서 무조건 매치하고, `RED` 는 함수 지역 변수가 되어 `999` 를 담는다.

여기서 `case RED:` 뒤에 `case _:` 를 하나 더 붙이고 싶어질 텐데, **그렇게 하면 아예 실행이 안 된다.**

```pyrepl
>>> RED = 1
>>> def color_name(c):
...     match c:
...         case RED:
...             return f"빨강 (RED={RED})"
...         case _:
...             return "모름"
...
  File "<stdin>", line 5
SyntaxError: name capture 'RED' makes remaining patterns unreachable
```

(Python 3.14.5 실측. `compile(..., "single")` 로 REPL 입력을 그대로 재현해도 결과는 같다.) `case RED:` 는 이미 무조건 매치하는 캡처이므로, 그 뒤에 오는 `case _:` 는 **정적으로 도달 불가능**하다. CPython 컴파일러가 이걸 바로 잡아낸다 — `def` 문 자체가 성립하지 않으니 함수를 호출해 보기도 전에 죽는다. 즉 위쪽의 `color_name(999)` 예제가 실제로 값을 돌려주는 건 **`case RED:` 가 유일한(그리고 마지막) case 일 때뿐이다.** 뒤에 다른 분기가 하나라도 있으면 조용한 버그 대신 시끄러운 `SyntaxError` 로 바뀐다 — 아래에서 더 자세히 본다.

::: danger 캡처 패턴이 마지막 case 로 숨어 있으면 조용히 항상 매치된다
캡처 패턴 두 개를 나란히 두면 파이썬이 바로 잡아낸다. `def` 를 쓰는 순간 죽는다 — 함수를 호출해 보기도 전이다.

```pyrepl
>>> STATUS_OK = 200
>>> STATUS_ERR = 500
>>> def f(code):
...     match code:
...         case STATUS_OK:  return "ok"
...         case STATUS_ERR: return "err"
...
  File "<stdin>", line 4
SyntaxError: name capture 'STATUS_OK' makes remaining patterns unreachable
```

(Python 3.14.5 실측.) `STATUS_OK` 자체가 이미 무조건 매치하는 캡처라서, 뒤따르는 `STATUS_ERR` 케이스는 컴파일 단계에서 곧바로 걸린다. **함수 정의조차 성립하지 않는다.** `f` 라는 이름도 만들어지지 않으니 나중에 `f(999)` 를 불러도 그냥 `NameError` 다.

진짜 위험은 캡처가 **맨 뒤에 숨어 있을 때**다. 이때는 파이썬이 막을 방법이 없다.

```python
def f(code):
    match code:
        case 200:       return "explicit ok"
        case STATUS_ERR: return f"기타: {STATUS_ERR}"   # ❌ 값 비교가 아니라 무조건 매치
```

```pyrepl
>>> f(999)
'기타: 999'
>>> f(200)
'explicit ok'
```

(Python 3.14.5 실측.) `case STATUS_ERR:` 은 다른 어떤 case 뒤에도 마지막에 오는 순간 `case _:` 와 똑같이 동작한다 — `500` 과 비교하는 게 아니라 무조건 매치하고 `code` 값을 지역 변수 `STATUS_ERR` 에 담는다. **예외도, 경고도 없다.** `f(999)` 가 `500` 과 아무 상관 없는데도 그 분기로 빠진다. 이게 이 함정의 진짜 얼굴이다 — 앞쪽 예제처럼 나란히 두면 컴파일러가 잡아 주지만, 마지막 자리에 숨겨 두면 아무도 안 잡아 준다.

고치는 법은 **점을 찍는 것**이다. 점이 하나라도 있으면 캡처가 아니라 **값 패턴**이 된다.

```python
class Status:
    OK = 200
    ERR = 500

def f(code):
    match code:
        case Status.OK:  return "ok"      # ✅ Status.OK 와 == 비교
        case Status.ERR: return "err"
```

`Enum` 을 쓰면 자연히 이렇게 된다. **`match` 를 쓸 거면 상수는 `Enum` 이나 클래스 속성으로 묶어라.** 이게 사실상 강제 규칙이다.

```pyrepl
>>> import dis
>>> dis.dis(compile("match x:\n case Color.RED: pass", "<s>", "exec"))
  LOAD_NAME                1 (Color)
  LOAD_ATTR                4 (RED)
  COMPARE_OP              88 (bool(==))     # 값 패턴 = == 비교
```

바이트코드가 증명한다. 점이 있으면 `COMPARE_OP`, 없으면 `STORE_NAME`.
:::

다행히 파이썬은 **캡처 패턴 뒤에 다른 case 를 두는 것**은 막는다.

```pyrepl
>>> compile("match x:\n case a: pass\n case 1: pass", "<s>", "exec")
SyntaxError: name capture 'a' makes remaining patterns unreachable
```

즉 `case RED:` 를 **마지막 case 로 썼을 때만** 조용히 통과한다. `case _:` 를 항상 마지막에 두는 습관이 이 함정을 덤으로 막아 준다.

### 함정 2 — 리터럴 패턴의 `==` / `is` 비대칭

`None`, `True`, `False` 만 `is` 로 비교하고, 나머지 리터럴은 `==` 다. 여기서 비대칭이 나온다.

```pyrepl
>>> match True:
...     case 1: print("매치")
...     case _: print("미매치")
...
매치                       # True == 1 이므로

>>> match 1:
...     case True: print("매치")
...     case _: print("미매치")
...
미매치                     # 1 is True 는 False 이므로
```

**`match A: case B` 와 `match B: case A` 의 결과가 다르다.** `1.0` 도 `case 1:` 에 매치된다 — `1.0 == 1` 이니까.

`case True:` 가 `IS_OP` 로 컴파일되는 걸 직접 볼 수 있다.

```pyrepl
>>> dis.dis(compile("match x:\n case True: pass", "<s>", "exec"))
  LOAD_NAME                0 (x)
  LOAD_CONST               0 (True)
  IS_OP                    0 (is)
```

리터럴 패턴이 `==` 라는 건 **`__eq__` 를 오버라이드한 객체가 아무 리터럴에나 매치될 수 있다**는 뜻이기도 하다.

```pyrepl
>>> class Weird:
...     def __eq__(self, other): return True
...
>>> match Weird():
...     case 1: print("1에 매치됐다")
...
1에 매치됐다
```

### 함정 3 — 시퀀스 패턴은 str 을 시퀀스로 보지 않는다

```pyrepl
>>> def s(x):
...     match x:
...         case [a, b]: return f"2-시퀀스: {a}, {b}"
...         case _: return "미매치"
...
>>> s([1, 2])
'2-시퀀스: 1, 2'
>>> s((1, 2))
'2-시퀀스: 1, 2'
>>> s("ab")
'미매치'
>>> s(b"ab")
'미매치'
>>> s({1, 2})
'미매치'
>>> s(range(2))
'2-시퀀스: 0, 1'
```

`str`, `bytes`, `bytearray` 는 **일부러 제외됐다.** 문자열을 문자 시퀀스로 분해하는 건 거의 항상 실수이기 때문이다. `set` 도 제외된다 — 순서가 없으니 위치 분해가 말이 안 된다.

::: deep 무엇이 시퀀스인지는 tp_flags 비트가 결정한다
`match` 는 덕 타이핑을 하지 않는다. `__len__` 과 `__getitem__` 을 정의해도 시퀀스 패턴에 매치되지 않는다.

```pyrepl
>>> class MySeq:
...     def __init__(self, d): self.d = d
...     def __len__(self): return len(self.d)
...     def __getitem__(self, i): return self.d[i]
...
>>> match MySeq([1, 2]):
...     case [a, b]: print("매치")
...     case _: print("미매치")
...
미매치
```

CPython은 타입 객체의 `tp_flags` 에 있는 `Py_TPFLAGS_SEQUENCE`(1 << 5) 비트만 본다. `MATCH_SEQUENCE` 라는 전용 바이트코드가 이 비트 하나를 검사한다. 그래서 O(1)이고, 덕 타이핑보다 훨씬 빠르다.

이 비트를 켜는 방법은 **`collections.abc.Sequence` 와 엮이는 것**뿐이다. 상속해도 되고, `register()` 해도 된다.

```pyrepl
>>> from collections.abc import Sequence
>>> Sequence.register(MySeq)
>>> match MySeq([1, 2]):
...     case [a, b]: print("매치", a, b)
...
매치 1 2
```

`register()` 로도 되는 게 놀랍다. 비밀은 `_collections_abc.py` 에 있다.

```python
class Sequence(Reversible, Collection):
    __abc_tpflags__ = 1 << 5      # Py_TPFLAGS_SEQUENCE

class Mapping(Collection):
    __abc_tpflags__ = 1 << 6      # Py_TPFLAGS_MAPPING
```

C로 구현된 `_abc_register` 가 이 `__abc_tpflags__` 를 읽어 **등록되는 클래스의 tp_flags 에 직접 OR 해 넣는다.** 가상 서브클래스 등록이 C 레벨 비트를 바꾼다. ABC의 일반 규칙에서 벗어난 특수 케이스다. ([1.15 프로토콜과 ABC](#/protocols))

`memoryview` 가 매치되고 `str` 이 안 되는 것도 결국 이 비트로 설명된다.

```pyrepl
>>> s(memoryview(b"ab"))
'2-시퀀스: 97, 98'
```
:::

시퀀스 패턴은 **길이가 정확히 맞아야 한다.** `*rest` 가 있을 때만 유연해진다.

```pyrepl
>>> match [1, 2, 3]:
...     case [1, 2]: print("매치")
...     case _: print("길이가 달라 미매치")
...
길이가 달라 미매치
```

### 함정 4 — 매핑 패턴은 부분 매치이고 `.get()` 을 부른다

시퀀스와 정반대다. **매핑 패턴은 나머지 키를 신경 쓰지 않는다.**

```pyrepl
>>> d = {"name": "kim", "age": 30, "extra": 1}
>>> match d:
...     case {"name": n, "age": a}: print("매치:", n, a)
...
매치: kim 30
```

`extra` 가 있어도 매치된다. **"이 키들만 있는 딕셔너리"를 표현하는 문법은 없다.** 필요하면 가드로 `if len(d) == 2` 를 붙여야 한다.

그리고 키 조회에 `__getitem__` 이 아니라 **`.get()` 을 쓴다.**

```pyrepl
>>> class Spy(dict):
...     def __getitem__(self, k):
...         print("__getitem__", k); return super().__getitem__(k)
...     def get(self, k, d=None):
...         print("get", k); return super().get(k, d)
...
>>> match Spy(a=1, b=2):
...     case {"a": x}: print("x =", x)
...
get a
x = 1
```

이건 의도된 설계다. `.get()` 을 쓰면 **`defaultdict` 가 키를 자동 생성하지 않는다.** 패턴 매칭이 부작용을 일으키면 안 되니까.

```pyrepl
>>> from collections import defaultdict
>>> d = defaultdict(list)
>>> match d:
...     case {"a": v}: print("매치")
...     case _: print("미매치")
...
미매치
>>> len(d)
0                       # 키가 생기지 않았다
```

`d["a"]` 였다면 빈 리스트가 생겼을 것이다. **`match` 는 조회 대상을 수정하지 않는다** — 이 원칙이 설계 전반에 깔려 있다.

::: perf **rest 는 딕셔너리를 통째로 복사한다
```pyrepl
>>> dis.dis(compile('match x:\n case {"a": v, **r}: pass', "<s>", "exec"))
  ...
  BUILD_MAP                0
  SWAP                     3
  DICT_UPDATE              2       # 원본 전체를 복사
  ...
  DELETE_SUBSCR                    # 매치된 키를 하나씩 삭제
```

`**rest` 는 원본을 복사한 뒤 매치된 키를 지운다. 원본을 건드리지 않으려면 이 방법밖에 없다. 비용이 나온다.

```python title="키 20개짜리 dict, 200,000회"
case {"k0": v}:            #  90.6 ns/회
case {"k0": v, **rest}:    # 204.3 ns/회   → 2.3배
```

**`rest` 를 실제로 안 쓸 거면 넣지 마라.** 딕셔너리가 클수록 격차가 벌어진다. 매핑 패턴은 어차피 부분 매치라 `**rest` 없이도 잘 동작한다.
:::

### 클래스 패턴과 `__match_args__`

`case Point(1, 2)` 는 `Point` 를 호출하는 게 아니다. 문법이 생성자와 같아 보일 뿐이다.

```python title="위치 인자를 쓰려면 __match_args__ 가 필요하다"
class Point:
    __match_args__ = ("x", "y")
    def __init__(self, x, y):
        self.x, self.y = x, y
```

```pyrepl
>>> match Point(3, 0):
...     case Point(0, 0): print("원점")
...     case Point(x, 0): print("x축 위:", x)
...     case Point(x=a, y=b): print("일반:", a, b)
...
x축 위: 3
```

`case Point(x, 0)` 은 이렇게 풀린다.

```text nolines
   case Point(x, 0):
        │      │  └── __match_args__[1] = "y"  ->  subject.y == 0 ?
        │      └───── __match_args__[0] = "x"  ->  subject.x -> x 에 바인딩
        └──────────── isinstance(subject, Point) ?
```

`__match_args__` 가 없으면 **위치 인자를 쓸 수 없다.** 키워드는 언제나 된다.

```pyrepl
>>> class Bare:
...     def __init__(self, x): self.x = x
...
>>> match Bare(1):
...     case Bare(v): print(v)
...
TypeError: Bare() accepts 0 positional sub-patterns (1 given)

>>> match Bare(1):
...     case Bare(x=v): print("키워드는 된다:", v)
...
키워드는 된다: 1

>>> match Bare(1):
...     case Bare(): print("인자가 없으면 isinstance 검사만")
...
인자가 없으면 isinstance 검사만
```

`dataclass` 와 `NamedTuple` 은 `__match_args__` 를 자동으로 만들어 준다. **이게 `match` 와 `dataclass` 를 짝지어 쓰는 이유다.**

```pyrepl
>>> from dataclasses import dataclass
>>> @dataclass
... class P:
...     x: int
...     y: int
...
>>> P.__match_args__
('x', 'y')
```

([2.6 dataclasses](#/dataclasses), [2.5 NamedTuple](#/typed-containers))

::: deep 내장 타입은 __match_args__ 없이 특수 처리된다
```pyrepl
>>> int.__match_args__
AttributeError: type object 'int' has no attribute '__match_args__'
>>> match "hello":
...     case str(s): print(s)
...
hello
```

`str` 에는 `__match_args__` 가 없는데 `str(s)` 가 동작한다. **컴파일러가 하드코딩된 목록을 특수 처리하기 때문이다.**

`bool`, `bytearray`, `bytes`, `dict`, `float`, `frozenset`, `int`, `list`, `set`, `str`, `tuple` — 이 11개는 위치 인자가 **정확히 하나**일 때 "주어(subject) 전체"를 뜻한다. `str(s)` 는 `isinstance(subject, str)` 검사 후 `subject` 를 `s` 에 바인딩한다.

이게 있어서 `case {"pos": [float(x), float(y)]}` 같은 **타입 검사 겸 바인딩**이 가능하다. `match` 코드에서 가장 자주 쓰는 관용구다.

`object` 는 이 목록에 없다.

```pyrepl
>>> match 5:
...     case object(v): pass
...
TypeError: object() accepts 0 positional sub-patterns (1 given)
```
:::

::: danger 클래스 패턴이 AttributeError 를 삼킨다
속성 접근 중 `AttributeError` 가 나면 **매치 실패로 처리된다.** 예외가 안 보인다.

```pyrepl
>>> class A:
...     @property
...     def x(self): raise AttributeError("설정 안 됨")
...
>>> match A():
...     case A(x=v): print("매치", v)
...     case _: print("미매치로 처리됨")
...
미매치로 처리됨
```

프로퍼티 안의 버그가 `AttributeError` 로 새면 **조용히 잘못된 분기로 간다.** 다른 예외는 정상적으로 전파된다.

```pyrepl
>>> class B:
...     @property
...     def x(self): raise RuntimeError("펑")
...
>>> match B():
...     case B(x=v): pass
...     case _: pass
...
RuntimeError: 펑
```

**계산이 들어가는 프로퍼티를 클래스 패턴에 노출하지 마라.** `__match_args__` 에는 순수한 데이터 속성만 넣어라.
:::

### 가드, Or, As

```pyrepl
>>> match 1:
...     case 1 | 2 as v: print("as v =", v)
...
as v = 1
```

Or 패턴은 **모든 대안이 같은 이름을 바인딩해야 한다.** 아니면 컴파일 에러다.

```pyrepl
>>> compile("match x:\n case [a] | [a, b]: pass", "<s>", "exec")
SyntaxError: alternative patterns bind different names
```

`_` 는 예외다. 바인딩을 안 하니까.

```pyrepl
>>> match [1]:
...     case [a] | [a, _]: print("ok", a)
...
ok 1
```

가드는 **패턴이 성공한 뒤에** 평가된다. 그래서 가드 안에서 바인딩된 이름을 쓸 수 있다.

```python
case [n] if n > 10:
    ...
```

::: danger 가드가 실패해도 바인딩은 남는다
가드가 거짓이면 그 case 는 실패하고 다음으로 넘어간다. **그런데 이미 바인딩된 이름은 되돌려지지 않는다.**

```pyrepl
>>> def h(x):
...     match x:
...         case [1, y] if y > 100: return "big"
...         case _: pass
...     return locals()
...
>>> h([1, 2])
{'x': [1, 2], 'y': 2}
```

`y` 가 남아 있다. 매치되지 않은 case 의 부산물이다.

패턴이 중간에 실패해도 마찬가지다. `case [1, 2, z]` 를 시도하다 세 번째 원소에서 깨져도, 그 전에 성공한 바인딩은 남는다. **`match` 는 트랜잭션이 아니다.**

실전에서 이게 물어뜯는 지점: `case _:` 블록에서 앞선 case 의 변수를 실수로 참조하면 **`NameError` 가 안 나고 이전 값이 쓰인다.** 리팩터링할 때 특히 위험하다.

가드의 부작용도 그대로 실행된다.

```pyrepl
>>> calls = []
>>> def check(v): calls.append(v); return False
>>> match [1, 2]:
...     case [a, b] if check((a, b)): pass
...     case _: pass
...
>>> calls
[(1, 2)]
```

**가드에는 순수 함수만 넣어라.**
:::

### 왜 switch가 아닌가 — 성능

여기가 이 절에서 가장 중요한 실측이다. C의 `switch` 는 **점프 테이블**로 컴파일된다 — case 개수와 무관하게 O(1)이다. `match` 는 아니다.

```pyrepl
>>> dis.dis(compile("def f(x):\n match x:\n  case 1: return 'a'\n  case 2: return 'b'\n  case 3: return 'c'", "<s>", "exec").co_consts[0])
  LOAD_FAST                0 (x)
  COPY                     1
  LOAD_SMALL_INT           1
  COMPARE_OP              88 (bool(==))     # x == 1 ?
  POP_JUMP_IF_FALSE ...
  ...
  LOAD_SMALL_INT           2
  COMPARE_OP              88 (bool(==))     # x == 2 ?
  POP_JUMP_IF_FALSE ...
  ...
```

**`if-elif-elif` 와 똑같은 선형 비교 사슬이다.** 점프 테이블은 어디에도 없다.

::: perf match 는 case 개수에 비례해 느려진다
case 64개짜리 `match` 와 `dict.get()` 을 비교했다.

```python title="측정 — 200,000회 반복"
def m(x):
    match x:
        case 0: return 0
        case 1: return 1
        ...          # case 63 까지
        case _: return -1

table = {i: i for i in range(64)}
def d(x): return table.get(x, -1)
```

| 인자 | `match` | `dict.get` | 비 |
| --- | --- | --- | --- |
| 첫 번째 case (`0`) | 0.030 us | 0.038 us | 0.8x |
| 마지막 case (`63`) | **0.438 us** | 0.038 us | 11.6x |
| 매치 실패 (`999`) | **0.443 us** | 0.037 us | 11.9x |

(Python 3.14.5 / Windows 실측.)

**같은 `match` 문 안에서 첫 case 와 마지막 case 가 14.6배 차이 난다.** `dict` 는 해시 테이블이라 위치와 무관하게 일정하다. ([1.6 dict](#/dict))

클래스 패턴도 `isinstance` 사슬보다 느리다.

```python title="dataclass 3종 디스패치 — 300,000회"
match Circle(1)  → 109.2 ns      isinstance 사슬 →  53.7 ns
match Tri(2, 3)  → 154.8 ns      isinstance 사슬 →  81.4 ns
```

약 2배. `MATCH_CLASS` 가 `__match_args__` 조회와 튜플 구성을 하기 때문이다.

**결론**: 값 하나로 분기하는 뜨거운 루프에서는 `match` 를 쓰지 마라. `dict` 디스패치가 정답이다. `match` 의 값어치는 **구조를 분해할 때** 나온다.
:::

::: cote 코딩테스트에서 match 는 대체로 손해다
1. **느리다.** 위 표대로다. 값 분기는 `dict` 나 `if-elif` 가 낫다.
2. **타이핑이 길다.** `case` 가 `elif` 보다 길고, 들여쓰기가 한 단계 더 들어간다.
3. **바인딩 함정**(`case RED:`)이 시험장의 압박 속에서 잡기 어려운 버그를 만든다.

값으로 분기할 거면 이렇게 써라.

```python
# ✅ 값 디스패치는 dict
DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
dr, dc = DIRS[cmd]

# ✅ 구간 분기는 if-elif (dict 로 못 한다)
if score >= 90: grade = "A"
elif score >= 80: grade = "B"
else: grade = "C"
```

`match` 가 실제로 이기는 코테 문제는 **명령어 파싱이 복잡한 삼성형 시뮬레이션** 정도다. 입력이 `["move", 3, 4]` / `["turn", "L"]` 처럼 이형(heterogeneous) 시퀀스로 들어올 때, 시퀀스 패턴이 코드를 확실히 줄인다.

```python
for cmd in commands:
    match cmd:
        case ["move", int(dr), int(dc)]:
            r, c = r + dr, c + dc
        case ["turn", "L" | "R" as d]:
            facing = rotate(facing, d)
        case ["repeat", int(n), *rest]:
            ...
```

[8.6 구현/시뮬레이션](#/drill-impl)에서 다시 본다. 그 외에는 쓰지 마라.
:::

::: hist 파이썬은 switch 를 두 번 거부했다
- **PEP 275** (2001) — `switch` 문 제안. 기각.
- **PEP 3103** (2006) — 귀도가 직접 쓴 switch 제안. **자기가 기각했다.** 파이콘 설문에서 어떤 문법안도 과반을 못 얻었다.

이유는 일관됐다. **`dict` 가 이미 있다.** 파이썬에서 값 디스패치는 `dict` 로 하고, 그게 점프 테이블보다 더 유연하고 이미 O(1)이다. switch 는 순수한 중복이었다.

그럼 2020년에 PEP 634가 통과된 이유는? **switch 가 아니었기 때문이다.** 구조적 패턴 매칭은 `dict` 로 대체할 수 없다. 딕셔너리 안의 리스트 안의 float 를 검사하면서 동시에 이름에 바인딩하는 일을 `dict` 는 못 한다.

`match` 를 switch 로 쓰는 건 20년의 논쟁을 무시하는 짓이다. 도구를 목적대로 써라.
:::

::: note match 와 case 는 예약어가 아니다
```pyrepl
>>> match = 1
>>> case = 2
>>> print(match, case)
1 2
```

**소프트 키워드**(soft keyword)다. 파서가 문맥으로 구분한다. 3.10 이전에 `match` 를 변수명으로 쓰던 수많은 코드(`re.match` 결과를 `match` 에 담는 게 관용구였다)를 깨지 않기 위해서다.

파서가 PEG로 바뀐 덕분에 가능해졌다. LL(1) 파서로는 못 한다. `type` (3.12), `_` 도 소프트 키워드다.
:::

### 컴파일러가 막아 주는 것들

`match` 는 정적으로 잡을 수 있는 실수를 꽤 잡아 준다.

```pyrepl
>>> compile("match x:\n case _: pass\n case 1: pass", "<s>", "exec")
SyntaxError: wildcard makes remaining patterns unreachable

>>> compile("match x:\n case [x, x]: pass", "<s>", "exec")
SyntaxError: multiple assignments to name 'x' in pattern

>>> compile('match x:\n case {"a": 1, "a": 2}: pass', "<s>", "exec")
SyntaxError: mapping pattern checks duplicate key ('a')

>>> compile("match x:\n case [*a, *b]: pass", "<s>", "exec")
SyntaxError: multiple starred names in sequence pattern

>>> compile("match x:\n case 1 + 2: pass", "<s>", "exec")
SyntaxError: imaginary number required in complex literal
```

마지막이 재밌다. 리터럴 패턴에서 `+`/`-` 는 **복소수 리터럴을 쓸 때만** 허용된다. `case 1 + 2j:` 는 되고 `case 1 + 2:` 는 안 된다. 패턴 안에서 산술을 하는 걸 막으면서도 복소수는 표현해야 했던 문법 설계의 흔적이다.

`_` 가 진짜로 바인딩하지 않는 것도 확인할 수 있다.

```pyrepl
>>> _ = "원래값"
>>> match 99:
...     case _: pass
...
>>> _
'원래값'
```

REPL에서 `_` 는 마지막 결과를 담는 변수인데, `match` 의 `_` 는 그걸 건드리지 않는다.

## `match` 를 쓸 자리 / 쓰지 말 자리

| 쓴다 | 쓰지 않는다 |
| --- | --- |
| 중첩된 JSON/메시지 파싱 | 값 하나로 분기 (`dict` 를 써라) |
| AST 순회 ([3.6 AST](#/ast)) | 뜨거운 루프 안의 분기 |
| 대수적 데이터 타입 디스패치 | 구간 조건 (`if-elif` 를 써라) |
| ROS 메시지 타입별 처리 | case 가 2개뿐일 때 |
| 명령어 인터프리터 | 이미 다형성으로 풀리는 것 |

마지막 줄이 중요하다. **클래스마다 메서드를 오버라이드해서 풀 수 있는 문제를 `match` 로 풀지 마라.** 그건 객체지향의 후퇴다. `match` 가 맞는 건 **타입을 내가 소유하지 않았거나**(외부 JSON), **분기 로직을 타입 밖에 두어야 할 때**(방문자 패턴)다.

## 요약

- **`bool(x)` 는 `__bool__` → `__len__` → `True` 순서로 결정된다.** 아무것도 없으면 참이다. `__bool__` 은 정확히 `bool` 을, `__len__` 은 0 이상 `Py_ssize_t` 범위의 정수를 반환해야 한다.
- **`if x:` 를 써라.** `len(x) > 0` 보다 2.5배 빠르다 — `TO_BOOL` 이 특수화 대상이기 때문이다. 단 NumPy 배열에는 절대 쓰지 마라.
- **`and`/`or` 는 불리언이 아니라 피연산자를 반환한다.** `cond and x or y` 는 `x` 가 falsy면 틀린다. `or` 기본값은 `0`/`""` 를 삼킨다.
- **`for-else` 의 `else` 는 `nobreak` 다.** 빈 시퀀스에서도 실행된다. `break` 만이 막는다.
- **`match` 는 switch 가 아니다.** 선형 `==` 사슬로 컴파일되고, 마지막 case 는 첫 case 보다 14.6배 느리다. 값 분기는 `dict` 로 해라.
- **`case NAME:` 은 비교가 아니라 캡처다.** 상수를 쓰려면 `Enum` 이나 `Class.ATTR` 처럼 **점을 찍어라.**
- **시퀀스 패턴은 `str`/`bytes`/`set` 을 거부하고, 매핑 패턴은 부분 매치이며 `.get()` 을 쓴다.** 클래스 패턴은 `AttributeError` 를 삼킨다.
- **`match` 의 값어치는 구조 분해에 있다.** `dataclass` 와 짝지어 써라.

::: quiz 연습문제

1. 다음 각각을 **먼저 예측한 뒤** 실행하라.

   ```python
   print(bool(float('nan')), bool(Decimal('-0.0')), bool([0]))

   class A:
       def __len__(self): return 0
       def __bool__(self): return True
   print(bool(A()), len(A()))
   ```

   `A()` 를 `if` 에 넣으면 참인데 `len` 은 0이다. 이런 클래스를 만드는 게 정당한 경우가 있는가?

2. 다음이 왜 항상 `False` 인지 설명하라. 그리고 의도한 대로 고쳐라.

   ```python
   x = 1
   print(x is not None == True)
   ```

3. 아래 `match` 는 어떤 입력이 와도 `"작음"` 을 반환한다. 왜인가? 세 가지 방법으로 고쳐라(가드 / Enum / 리터럴).

   ```python
   THRESHOLD = 100

   def f(n):
       match n:
           case THRESHOLD:
               return "작음"
           case _:
               return "큼"
   ```

4. 다음의 출력을 예측하라. 예측이 틀렸다면 어느 규칙 때문인가?

   ```python
   def s(x):
       match x:
           case [a, b]: return f"seq {a}{b}"
           case {"k": v}: return f"map {v}"
           case _: return "no"

   print(s("ab"), s([1, 2]), s({"k": 1, "z": 2}), s(range(2)))
   ```

5. 아래 코드는 `y` 를 출력한다. `case [1, y]` 는 매치되지 않았는데 왜 `y` 가 존재하는가? 이 성질이 실제 버그를 만드는 시나리오를 하나 써 보라.

   ```python
   def h(x):
       match x:
           case [1, y] if y > 100:
               return "big"
           case _:
               return f"y = {y}"
   print(h([1, 2]))
   ```

6. **깊이 생각해 볼 문제.** 다음 두 클래스 중 하나만 시퀀스 패턴에 매치된다. 어느 쪽이고, 왜인가? `tp_flags` 라는 단어를 써서 설명하라.

   ```python
   from collections.abc import Sequence

   class P:
       def __len__(self): return 2
       def __getitem__(self, i): return i

   class Q:
       def __len__(self): return 2
       def __getitem__(self, i): return i
   Sequence.register(Q)
   ```
:::

**다음 절**: [1.9 컴프리헨션과 제너레이터 표현식](#/comprehensions) — 컴프리헨션은 왜 `for` 문보다 빠른가, 그리고 언제 쓰지 말아야 하는가.
