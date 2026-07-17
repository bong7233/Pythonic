# 1.16 예외와 예외 그룹

::: lead
예외는 "에러 처리 문법"이 아니다. **반환값과 나란히 존재하는, 함수에서 빠져나오는 두 번째 경로**다. 이 경로를 정확히 이해하지 못하면 `except Exception` 하나로 모든 걸 덮고 원인을 잃어버리는 코드를 쓰게 된다. 이 절은 예외가 어떤 길로 올라가는지, 그 길이 얼마나 비싼지, 3.11에서 왜 그 비용이 0이 됐는지, 그리고 "여러 개가 동시에 터지는" 세계를 위해 파이썬이 왜 `ExceptionGroup` 이라는 새 축을 만들어야 했는지를 다룬다.
:::

## 문제부터

아래 세 코드는 전부 흔하다. 그리고 전부 틀렸다. 어디가 틀렸는지 말할 수 있나?

```python
# ①
while True:
    try:
        do_work()
    except:
        continue

# ②
def parse(s):
    try:
        return int(s)
    except Exception:
        return None

# ③
def read_config(path):
    try:
        f = open(path)
        data = f.read()
        return json.loads(data)
    finally:
        return {}
```

①은 <kbd>Ctrl</kbd>+<kbd>C</kbd>로도 멈출 수 없다. ②는 `int(s)` 안에서 난 `MemoryError` 를 "파싱 실패"로 둔갑시킨다. ③은 **모든 예외를 조용히 삼키고** 항상 빈 딕셔너리를 반환한다 — 파일이 없어도, 디스크가 죽어도.

이 절이 끝나면 셋 다 즉시 보인다.

## 계층 구조 — 잡을 것과 잡지 말 것

파이썬의 모든 예외는 `BaseException` 을 뿌리로 하는 하나의 트리다. 그런데 이 트리의 최상단은 **의도적으로 두 종류로 갈라져 있다.**

```text nolines
BaseException
├── SystemExit                 <- sys.exit() 가 던진다
├── KeyboardInterrupt          <- Ctrl+C
├── GeneratorExit              <- 제너레이터 close()
├── BaseExceptionGroup
└── Exception                  <- 여기서부터가 "프로그램의 오류"
    ├── ExceptionGroup
    ├── ArithmeticError
    │   └── ZeroDivisionError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── OSError
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   └── TimeoutError
    ├── ValueError
    │   └── UnicodeError
    ├── TypeError
    ├── AttributeError
    ├── NameError
    ├── RuntimeError
    │   └── RecursionError
    ├── StopIteration
    └── ...
```

직접 확인할 수 있다.

```pyrepl
>>> BaseException.__subclasses__()
[<class 'BaseExceptionGroup'>, <class 'Exception'>, <class 'GeneratorExit'>, <class 'KeyboardInterrupt'>, <class 'SystemExit'>]
```

`Exception` 옆에 나란히 놓인 셋은 **에러가 아니다.** 셋 다 *"지금 당장 이 스택에서 빠져나가라"* 는 **제어 신호**다. 그래서 `Exception` 의 자식이 아니다. `except Exception` 이 이들을 못 잡는 것은 **버그가 아니라 설계**다.

::: danger bare except 는 종료 신호를 삼킨다
```python
import sys

def main():
    try:
        sys.exit(1)          # SystemExit 를 raise 한다
    except:                  # ❌ BaseException 까지 전부 잡는다
        print("에러 발생, 계속 진행")
    return "정상 종료"

print(main())
```

```text nolines
에러 발생, 계속 진행
정상 종료
```

**프로그램이 종료를 거부했다.** 종료 코드 1로 죽어야 할 프로세스가 0으로 성공했다고 보고한다. CI가 초록불을 켠다.

같은 이유로 도입부의 ①은 <kbd>Ctrl</kbd>+<kbd>C</kbd>를 삼킨다. `except:` 는 `except BaseException:` 과 완전히 같다.

**규칙: `except:` 를 쓰지 마라.** `except Exception:` 을 써라. 정말 `BaseException` 을 잡아야 한다면(로깅 후 재전파 같은) **명시적으로** 쓰고 반드시 `raise` 로 다시 올려라.
:::

::: deep GeneratorExit — 잡으면 인터프리터가 화를 낸다
`GeneratorExit` 가 `Exception` 밖에 있는 이유는 더 날카롭다.

```python
def bad_gen():
    while True:
        try:
            yield 1
        except:            # ❌ GeneratorExit 까지 잡는다
            print("삼킴")

b = bad_gen()
next(b)
b.close()
```

```text nolines
삼킴
Traceback (most recent call last):
  ...
RuntimeError: generator ignored GeneratorExit
Exception ignored while closing generator <generator object bad_gen at 0x...>:
RuntimeError: generator ignored GeneratorExit
삼킴
```

`close()` 는 중단된 `yield` 지점에 `GeneratorExit` 를 던져 넣어 제너레이터를 정리한다. 그걸 잡고 다시 `yield` 하면 제너레이터가 "죽기를 거부한" 것이다. CPython은 이걸 `RuntimeError` 로 만든다 — 여기까지가 첫 번째 `삼킴` 과 `Traceback` 이다. 스크립트는 이 시점에 죽는다(처리 안 된 예외니까).

그런데 출력은 거기서 끝나지 않는다. `b` 는 아직 살아있는 제너레이터 객체고, 인터프리터가 종료되면서 이걸 GC하려고 다시 한번 `close()` 를 시도한다. 이때도 똑같이 `GeneratorExit` 를 삼키고 다시 `yield` 하려다 `RuntimeError` 가 또 난다. 다만 이번엔 `__del__` 경로라 이 예외를 던질 데가 없다 — 그래서 크래시 대신 `Exception ignored while closing generator ...: RuntimeError: ...` 로 표준에러에 찍히고 만다. 그 과정에서 `except:` 블록의 `print("삼킴")` 도 한 번 더 실행된다. **같은 버그가 두 번, 다른 얼굴로 나타나는 것이다.**

`except Exception:` 이었다면 아무 문제 없다. `GeneratorExit` 는 그대로 통과하고 `finally` 만 실행된다. 이건 [1.18 이터레이터와 제너레이터](#/iterators)에서 다시 만난다.

`asyncio.CancelledError` 도 3.8부터 같은 이유로 `BaseException` 직속으로 옮겨졌다.

```pyrepl
>>> import asyncio
>>> asyncio.CancelledError.__mro__
(<class 'asyncio.exceptions.CancelledError'>, <class 'BaseException'>, <class 'object'>)
```

`except Exception` 이 취소를 삼키면 태스크가 취소되지 않는다. [4.7 asyncio 실전](#/asyncio-advanced)의 핵심 함정이다.
:::

### 중간 계층은 장식이 아니다

`LookupError`, `ArithmeticError`, `OSError` 같은 중간 노드는 **"이 정도 추상 수준에서 묶어 잡는 게 말이 되는 지점"** 을 언어가 미리 정해 준 것이다.

```pyrepl
>>> IndexError.__mro__
(<class 'IndexError'>, <class 'LookupError'>, <class 'Exception'>, <class 'BaseException'>, <class 'object'>)
>>> UnicodeDecodeError.__mro__
(<class 'UnicodeDecodeError'>, <class 'UnicodeError'>, <class 'ValueError'>, <class 'Exception'>, <class 'BaseException'>, <class 'object'>)
```

`UnicodeDecodeError` 가 `ValueError` 의 자손인 건 우연이 아니다. "바이트를 문자열로 바꾸려는데 값이 이상하다" 는 **값의 문제**다. 그래서 `except ValueError` 로 잡힌다. 예외 계층을 설계할 때 이 감각을 빌려 써야 한다.

::: deep OSError.__new__ 는 errno 를 보고 클래스를 바꿔치기한다
3.3(PEP 3151) 전까지 파일 에러 처리는 이랬다.

```python
try:
    open(path)
except IOError as e:
    if e.errno == errno.ENOENT:      # 없는 파일
        ...
    elif e.errno == errno.EACCES:    # 권한 없음
        ...
```

`errno` 를 손으로 분기하는 C 스타일이다. 3.3은 `IOError`/`OSError`/`WindowsError`/`EnvironmentError` 를 **전부 `OSError` 하나로 합치고**, 대신 자주 쓰는 errno마다 서브클래스를 만들었다.

```pyrepl
>>> IOError is OSError, EnvironmentError is OSError
(True, True)
```

여기서 신기한 일이 벌어진다. `OSError` 는 `__new__` 에서 **첫 인자(errno)를 보고 자기 클래스를 바꾼다.**

```pyrepl
>>> type(OSError(2, "no such"))
<class 'FileNotFoundError'>
>>> type(OSError(13, "denied"))
<class 'PermissionError'>
>>> type(OSError("그냥 메시지"))
<class 'OSError'>
>>> type(OSError(9999, "unknown"))
<class 'OSError'>
```

errno가 매핑에 있으면 서브클래스로, 없거나 errno 형태가 아니면 그대로 `OSError` 로 만들어진다. 덕분에 **옛날 C 스타일 코드가 그대로 새 계층의 혜택을 받는다.**

`errno` 자체도 남아 있다.

```pyrepl
>>> try:
...     open("nope.txt")
... except OSError as e:
...     print(e.errno, e.strerror, e.filename)
...
2 No such file or directory nope.txt
```

이 트릭은 `BaseExceptionGroup` 에서 한 번 더 나온다. 기억해 둬라.
:::

## try / except / else / finally

네 절의 의미를 정확히 쓰면 이렇다.

| 절 | 실행 시점 | 존재 이유 |
| --- | --- | --- |
| `try` | 항상 | 감시 구간 |
| `except` | 매칭되는 예외가 **떴을 때** | 처리 |
| `else` | `try` 가 **예외 없이** 끝났을 때 | 감시 구간을 좁힌다 |
| `finally` | **무조건** (return/break/예외 포함) | 정리 |

`except`, `finally` 는 다들 안다. 문제는 `else` 다. 대부분 "필요 없는 문법" 이라고 생각하고 넘긴다. 아니다.

### else 가 없으면 except 가 거짓말을 한다

```python title="try 블록이 넓으면 벌어지는 일"
class Weird:
    def __getitem__(self, k):
        raise KeyError("내부 버그")


d = {"a": Weird()}

try:
    v = d["a"]
    print(v["zzz"])          # 여기서 난 KeyError 를 아래 except 가 삼킨다
except KeyError:
    print("키 없음 <- 거짓말")
```

```text nolines
키 없음 <- 거짓말
```

`d["a"]` 는 **성공했다.** 실패한 건 그 다음 줄이고, 원인은 완전히 다른 곳의 버그다. 그런데 `except KeyError` 는 둘을 구별할 방법이 없다. **`try` 블록이 넓으면 의도하지 않은 예외까지 같은 처리로 빨려 들어간다.**

`else` 가 이걸 푼다.

```python title="try 는 한 줄만 감시한다"
try:
    v = d["a"]               # 감시 대상은 이것뿐
except KeyError:
    print("키 없음")
else:
    print(v["zzz"])          # 여기서 난 KeyError 는 위로 그대로 올라간다
```

```text nolines
KeyError: '내부 버그'
```

::: tip try 블록은 예외를 낼 수 있는 최소 단위로 좁혀라
`else` 의 존재 이유는 하나다. **"성공했을 때만 하는 일"을 `try` 밖으로 빼내기 위해서.** `for/else`, `while/else` 와 달리 이건 헷갈리지도 않는다. `try: ... else:` 는 그냥 "예외 없이 끝났으면" 이다.

`with` 문이 `finally` 를 대부분 대체한 것처럼, `else` 는 `try` 를 좁히는 도구다. ([1.17 컨텍스트 매니저](#/context-managers))
:::

### except ... as e 는 블록이 끝나면 사라진다

```pyrepl
>>> try:
...     raise ValueError("x")
... except ValueError as e:
...     pass
...
>>> e
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
NameError: name 'e' is not defined
```

`Did you mean: ...` 제안이 안 붙은 걸 눈여겨봐라. `NameError` 의 오타 제안은 현재 네임스페이스에 있는 이름들과 철자 거리를 비교해서 나오는데, 방금 `del` 된 `e` 대신 내밀 만한 후보(`ne` 같은)가 애초에 이 세션 어디에도 없으면 제안 자체가 생략된다. 즉 제안이 붙고 안 붙고는 그 순간 네임스페이스에 뭐가 살아있느냐에 달렸다 — 예외 메시지 하나에도 "지금 이 스코프에 뭐가 있는지"가 새어 나온다는 뜻이다.

파이썬 3에서 `except ... as e` 의 `e` 는 **`except` 블록이 끝나는 순간 `del` 된다.** 문법이 아니라 컴파일러가 넣는 코드다. 바이트코드에 그대로 보인다.

```pyrepl
>>> import dis
>>> def f():
...     try:
...         pass
...     except ValueError as e:
...         pass
...
>>> dis.dis(f)
```

```text nolines
       ...
       STORE_FAST               0 (e)
  L2:  POP_EXCEPT
       LOAD_CONST               0 (None)
       STORE_FAST               0 (e)          <- e = None
       DELETE_FAST              0 (e)          <- del e
       ...
```

컴파일러가 `except` 블록을 이렇게 감싼 것과 같다.

```python
except ValueError as e:
    try:
        ...
    finally:
        e = None
        del e
```

::: deep 왜 지우나 — 트레이스백이 프레임을 붙잡는다
예외 객체는 `__traceback__` 을 들고 있고, 트레이스백은 **예외가 지나온 모든 프레임**을 들고 있고, 프레임은 **그 안의 모든 지역 변수**를 들고 있다. `e` 를 지역 변수로 남겨 두면 `프레임 → e → traceback → 프레임` 순환이 생긴다.

직접 보자.

```python title="예외를 except 밖으로 빼돌리면"
class Big:
    def __del__(self):
        print("  Big 소멸")


def work():
    payload = Big()          # work 프레임의 지역 변수
    raise ValueError("실패")


def handler():
    try:
        work()
    except ValueError as e:
        return e             # ❌ 예외 객체를 밖으로 반환


saved = handler()
print("  handler 는 끝났다")
print("  트레이스백이 붙잡고 있는 프레임의 지역 변수:",
      list(saved.__traceback__.tb_next.tb_frame.f_locals))
del saved
print("  del saved 이후")
```

```text nolines
  handler 는 끝났다
  트레이스백이 붙잡고 있는 프레임의 지역 변수: ['payload']
  Big 소멸
  del saved 이후
```

`handler` 가 끝난 지 한참 뒤까지 `work` 의 지역 변수 `payload` 가 **살아 있다.** `saved` 를 놓아준 순간에야 죽는다.

이게 웹 서버에서 예외 객체를 리스트에 모아 두면 메모리가 계속 늘어나는 이유다. 파이썬 2에서는 이 누수가 기본 동작이었고, 파이썬 3는 `del e` 를 자동으로 넣어 막았다.

**예외 정보를 밖으로 내보내야 한다면 예외 객체가 아니라 문자열이나 필요한 필드만 꺼내라.**

```python
except ValueError as e:
    msg = str(e)             # ✅ 프레임을 붙잡지 않는다
return msg
```
:::

## finally 의 함정

`finally` 는 "무조건 실행된다". 이 무조건이 함정이다.

::: danger finally 의 return 은 예외를 삼킨다
```python
def f():
    try:
        raise ValueError("사라진다")
    finally:
        return "정상"        # ❌

print(f())
```

```text nolines
정상
```

**예외가 증발했다.** 트레이스백도, 로그도, 아무것도 없다.

이유는 `finally` 의 정의 그 자체다. `finally` 는 "지금 진행 중인 탈출(예외 전파 / return / break)"을 잠시 멈추고 실행된다. 그 안에서 `return` 을 하면 **새로운 탈출이 기존 탈출을 덮어쓴다.** `break`, `continue` 도 똑같다.

```python
def h():
    for i in range(3):
        try:
            raise ValueError("사라짐")
        finally:
            break            # ❌ 예외 대신 루프를 빠져나간다
    return "루프 탈출"

print(h())                   # 루프 탈출
```

도입부의 ③이 정확히 이 버그다.

파이썬 3.14부터는 **컴파일 시점에 경고**한다 (PEP 765).

```text nolines
example.py:5: SyntaxWarning: 'return' in a 'finally' block
```

`break`, `continue` 도 각각 경고가 나온다. 런타임이 아니라 `compile()` 시점이므로 실행 전에 잡힌다. 3.14 미만이면 ruff의 `B012` 가 같은 일을 한다.

**규칙: `finally` 안에서는 절대 빠져나가지 마라.** 정리만 해라.
:::

::: warn finally 안에서 난 예외도 원래 예외를 가린다
```pyrepl
>>> try:
...     try:
...         raise ValueError("진짜 원인")
...     finally:
...         raise RuntimeError("정리 중 실패")
... except RuntimeError as e:
...     print(type(e).__name__, e)
...     print("  __context__:", repr(e.__context__))
...
RuntimeError 정리 중 실패
  __context__: ValueError('진짜 원인')
```

다행히 이쪽은 **완전히 사라지지는 않는다.** `__context__` 에 원래 예외가 남는다. 다음 절의 주제다.
:::

## 체이닝 — `__context__` 와 `__cause__`

예외 처리 중에 또 예외가 나면, 파이썬은 원래 예외를 **버리지 않는다.**

```pyrepl
>>> try:
...     try:
...         1 / 0
...     except ZeroDivisionError:
...         raise ValueError("bad")
... except ValueError as e:
...     print("cause:  ", e.__cause__)
...     print("context:", repr(e.__context__))
...     print("suppress:", e.__suppress_context__)
...
cause:   None
context: ZeroDivisionError('division by zero')
suppress: False
```

`__context__` 는 **자동으로** 채워진다. 아무 문법도 필요 없다. 트레이스백에는 이렇게 찍힌다.

```text nolines
During handling of the above exception, another exception occurred:
```

`raise ... from` 을 쓰면 `__cause__` 가 채워진다.

```pyrepl
>>> try:
...     try:
...         1 / 0
...     except ZeroDivisionError as e:
...         raise ValueError("bad") from e
... except ValueError as e:
...     print("cause:  ", repr(e.__cause__))
...     print("context:", repr(e.__context__))
...     print("suppress:", e.__suppress_context__)
...
cause:   ZeroDivisionError('division by zero')
context: ZeroDivisionError('division by zero')
suppress: True
```

트레이스백 문구가 바뀐다.

```text nolines
The above exception was the direct cause of the following exception:
```

**둘의 차이는 의도다.**

- `__context__` — "처리 중에 어쩌다 또 터졌다." 대개 **버그의 냄새**다.
- `__cause__` — "이것 **때문에** 저것을 던졌다." 의도적인 **번역**이다.

실전에서 `from` 은 저수준 예외를 도메인 예외로 감쌀 때 쓴다.

```python title="예외 번역"
def load(path):
    try:
        return int(open(path).read())
    except FileNotFoundError as e:
        raise ConfigError(f"설정 {path} 없음") from e
```

호출자는 `ConfigError` 만 알면 되고, 디버깅할 때는 원래 `FileNotFoundError` 가 트레이스백에 남는다. **정보를 버리지 않으면서 추상화를 유지하는 유일한 방법이다.**

::: deep raise from None 은 __context__ 를 지우지 않는다
`from None` 은 흔히 "체인을 지운다" 고 설명된다. 틀렸다.

```pyrepl
>>> try:
...     try:
...         1 / 0
...     except ZeroDivisionError:
...         raise ValueError("bad") from None
... except ValueError as e:
...     print("cause:  ", repr(e.__cause__))
...     print("context:", repr(e.__context__))
...     print("suppress:", e.__suppress_context__)
...
cause:   None
context: ZeroDivisionError('division by zero')
suppress: True
```

**`__context__` 는 그대로 있다.** `from None` 이 한 일은 `__suppress_context__ = True` 뿐이다. 즉 *"트레이스백을 출력할 때 context 를 찍지 마라"* 는 **표시일 뿐**, 정보는 객체에 남아 있다.

세 줄로 정리하면:

- `raise X` → `__context__` 자동, `__suppress_context__=False` → context 출력
- `raise X from Y` → `__cause__=Y`, `__suppress_context__=True` → cause 출력
- `raise X from None` → `__cause__=None`, `__suppress_context__=True` → 아무것도 출력 안 함

`from` 은 사실 `__cause__` 에 대입하는 것이고, `__cause__` 에 값을 넣으면 **부수 효과로** `__suppress_context__` 가 켜진다. `from None` 은 그 부수 효과만 쓰는 관용구다.

그래서 로깅 라이브러리가 `e.__context__` 를 직접 읽으면 `from None` 을 써도 원인이 로그에 나온다. **비밀을 지우는 도구가 아니다.**
:::

::: tip add_note — 예외를 다시 만들지 않고 정보를 붙인다 (3.11+)
"어느 파일 몇 번째 줄에서 실패했는지"를 붙이려고 예외를 새로 만들 필요가 없다.

```python
try:
    parse(line)
except ValueError as e:
    e.add_note(f"파일: {path}")
    e.add_note(f"줄: {lineno}")
    raise
```

```text nolines
ValueError: 파싱 실패
파일: data.csv
줄: 42
```

메시지는 원본 그대로 남고, 노트만 아래에 붙는다. `e.__notes__` 로 읽을 수 있다. 예외 타입을 바꾸지 않으니 **호출자의 `except` 절이 깨지지 않는다.** `ExceptionGroup` 안의 개별 예외에도 붙는다.
:::

## try 는 공짜다 — 3.11의 제로 코스트 예외

"try/except 는 느리니까 `if` 로 처리하라" 는 조언을 들어 봤을 것이다. **3.11부터 틀렸다.**

```python title="같은 일, try 유무만 다르다"
def plain():
    x = 1
    return x

def wrapped():
    try:
        x = 1
        return x
    except KeyError:
        return None
```

```text nolines
plain      best=0.0293s
wrapped    best=0.0297s     <- 2,000,000회. 차이가 없다.
```

::: deep 예외 테이블 — try 가 바이트코드에서 사라진 방법
3.10까지는 `try` 에 진입할 때마다 `SETUP_FINALLY` 바이트코드가 실행돼 **런타임 스택에 핸들러 블록을 밀어 넣었다.** 예외가 안 나도 비용을 냈다.

3.11은 이걸 **코드 객체 옆의 정적 테이블**로 옮겼다. `dis` 로 보면 `try` 자리에 `NOP` 하나만 남는다.

```pyrepl
>>> import dis
>>> dis.dis(wrapped)
```

```text nolines
  2           RESUME                   0
  3           NOP                                   <- try 의 흔적. 이게 전부다.
  4   L1:     LOAD_SMALL_INT           1
              STORE_FAST               0 (x)
  5           LOAD_FAST_BORROW         0 (x)
      L2:     RETURN_VALUE
 --   L3:     PUSH_EXC_INFO
  6           LOAD_GLOBAL              0 (KeyError)
              CHECK_EXC_MATCH
              ...
ExceptionTable:
  L1 to L2 -> L3 [0]                                <- 여기가 핵심
  L3 to L4 -> L6 [1] lasti
  L5 to L6 -> L6 [1] lasti
```

`ExceptionTable` 을 읽는 법: *"L1~L2 구간에서 예외가 나면 L3 으로 점프하고, 그때 값 스택 깊이는 0으로 맞춰라."*

즉 **예외가 실제로 발생했을 때만** 인터프리터가 이 테이블을 이진 탐색해서 핸들러를 찾는다. 정상 경로는 테이블을 아예 보지 않는다. 그래서 **비용이 0**이다. C++ 컴파일러가 30년 전부터 쓰던 기법(table-driven unwinding)을 CPython이 가져온 것이다.

테이블 자체는 코드 객체당 수백 바이트 수준이다. 표준 라이브러리 `argparse` 를 컴파일해 재 보면 바이트코드 45,598바이트에 예외 테이블은 514바이트 — **1%** 다.

`try` 를 아끼지 마라. **아껴야 할 것은 `raise` 다.**
:::

::: perf raise 는 비싸다
```python title="같은 제어 흐름, 전달 방식만 다르다"
class E(Exception): pass

def by_return(): return None
def by_raise():  raise E()

def caller_return():
    r = by_return()
    return r

def caller_raise():
    try:
        by_raise()
    except E:
        return None
```

```text nolines
caller_return          best=0.0276s
caller_raise           best=0.1475s     <- 약 5.3배
```

(1,000,000회 / Python 3.14.5 / Windows 실측. 절대값은 기기마다 다르지만 배수는 비슷하다.)

비용의 정체는 **예외 객체 생성 + 트레이스백 구축**이다. 그래서 스택을 깊이 통과할수록 선형으로 늘어난다.

```text nolines
depth=   1   0.21us
depth=  10   0.76us
depth=  50   3.38us
depth= 100   6.72us      <- 프레임 하나당 약 65ns 씩 누적
```

**예외를 정상 흐름의 신호로 쓰지 마라.** 100만 번 도는 루프에서 매번 예외가 나면 그게 병목이다. 반대로 100만 번 중 100번만 나면 신경 쓸 필요가 전혀 없다.
:::

## EAFP vs LBYL

파이썬 문화는 **EAFP**(Easier to Ask Forgiveness than Permission — 일단 하고 실패하면 처리)를 선호한다. C/Java 문화는 **LBYL**(Look Before You Leap — 먼저 확인)이다. 어느 쪽이 빠른가?

```text nolines
noop         12.2ns      <- 함수 호출 자체의 비용 (기준선)
lbyl_hit     29.1ns      if "key" in d: return d["key"]      키가 있을 때
eafp_hit     21.7ns      try: return d["key"] ...            키가 있을 때
lbyl_miss    22.1ns      if "zzz" in d: ...                  키가 없을 때
eafp_miss    88.1ns      try: return d["zzz"] ...            키가 없을 때
```

기준선을 빼고 보면 그림이 선명하다.

| | 성공 | 실패 |
| --- | --- | --- |
| LBYL | 16.9ns | 9.9ns |
| EAFP | **9.5ns** | 75.9ns |

- **성공할 때는 EAFP 가 빠르다.** LBYL 은 해시를 **두 번** 계산한다 (`in` 한 번, `[]` 한 번).
- **실패할 때는 LBYL 이 8배 빠르다.** 예외를 만들고 던지고 잡는 비용이 전부 붙는다.

::: tip 기준은 속도가 아니라 확률이다
> **예외적인 경우가 정말로 예외적일 때 EAFP 를 써라.**

실패율이 5%면 EAFP 가 압승이다. 실패율이 50%면 LBYL 을 써라. 실패가 정상 흐름의 절반이면 그건 "예외"가 아니다.

그리고 EAFP 를 선호하는 **더 중요한 이유는 성능이 아니다.**

```python
# ❌ LBYL — 확인과 사용 사이에 세상이 바뀔 수 있다
if os.path.exists(path):
    with open(path) as f:      # 그 사이 다른 프로세스가 지웠다면?
        ...

# ✅ EAFP — 원자적이다
try:
    with open(path) as f:
        ...
except FileNotFoundError:
    ...
```

이걸 **TOCTOU**(Time-Of-Check to Time-Of-Use) 경쟁 상태라고 한다. 파일 시스템, 네트워크, 스레드가 얽히면 LBYL 의 `if` 는 **거짓말**이 된다. 확인한 시점의 진실일 뿐이다.

같은 이유로 덕 타이핑과도 궁합이 맞는다. `hasattr(x, "read")` 로 확인하는 것보다 그냥 `x.read()` 를 호출하고 `AttributeError` 를 받는 게 더 정확하다. ([1.15 프로토콜, ABC, 덕 타이핑](#/protocols))
:::

::: perf contextlib.suppress 는 공짜가 아니다
```python
from contextlib import suppress

with suppress(KeyError):
    d["zzz"]
```

읽기는 좋다. 그런데 예외가 실제로 나면 **컨텍스트 매니저 프로토콜(`__enter__`/`__exit__` 호출)이 통째로 얹힌다.**

```text nolines
raw try/except    best=0.0432s
suppress          best=0.1148s     <- 약 2.7배
```

(500,000회 실측. 예외가 매번 발생하는 경우.)

가독성이 이기는 곳(설정 코드, 정리 루틴)에서는 써라. 뜨거운 루프에서는 쓰지 마라.
:::

## 커스텀 예외 설계

::: warn 커스텀 예외를 만드는 이유는 "이름"이 아니다
`raise Exception("사용자 없음")` 이 나쁜 이유는 못생겨서가 아니다. **호출자가 그것만 골라 잡을 수 없기 때문**이다. `except Exception` 으로 잡으면 `MemoryError` 도 같이 잡힌다.

예외 클래스는 **호출자에게 주는 API** 다. "당신이 구별해서 처리해야 할 실패는 이것들이다" 라는 선언이다.
:::

라이브러리를 만든다면 **루트 예외 하나**를 두고 그 아래로 뻗는다.

```python title="예외 계층 설계"
class MyLibError(Exception):
    """이 라이브러리가 던지는 모든 예외의 뿌리."""


class ConfigError(MyLibError):
    pass


class ConnectionFailed(MyLibError, OSError):
    """OSError 로도 잡히게 한다 — 네트워크 실패는 OS 에러이기도 하다."""
```

- 사용자가 **전부 잡고 싶으면** `except MyLibError`.
- **세밀하게 잡고 싶으면** `except ConfigError`.
- 기존 코드가 `except OSError` 로 잡고 있어도 `ConnectionFailed` 는 잡힌다.

::: danger 커스텀 예외의 __init__ 이 피클링을 깬다
이건 반드시 당한다. 그리고 원인을 찾는 데 하루가 걸린다.

```python
class BadErr(Exception):
    def __init__(self, code, msg):
        super().__init__(f"[{code}] {msg}")     # ❌ 인자를 합쳐서 넘겼다
        self.code = code
```

```pyrepl
>>> import pickle
>>> e = BadErr(404, "없음")
>>> e.args
('[404] 없음',)
>>> pickle.loads(pickle.dumps(e))
Traceback (most recent call last):
  ...
TypeError: BadErr.__init__() missing 1 required positional argument: 'msg'
```

**예외는 `args` 로 피클링된다.** `BaseException.__reduce__` 가 `(클래스, self.args)` 를 반환하고, 복원할 때 `클래스(*args)` 로 다시 만든다. `args` 가 1개인데 `__init__` 이 2개를 요구하니 깨진다.

**언제 터지나?** `multiprocessing` 이나 `concurrent.futures.ProcessPoolExecutor` 의 워커에서 이 예외가 나면, 부모 프로세스로 전달하려고 피클링하다가 **원래 예외 대신 이 `TypeError` 가 올라온다.** 원인 예외는 영원히 사라진다. ([4.4 multiprocessing](#/multiprocessing))

고치는 법은 하나다. **`super().__init__` 에 `__init__` 이 받은 인자를 그대로 넘기고, 표시는 `__str__` 에서 한다.**

```python
class GoodErr(Exception):
    def __init__(self, code, msg):
        super().__init__(code, msg)      # ✅ args = (404, "없음")
        self.code = code
        self.msg = msg

    def __str__(self):
        return f"[{self.code}] {self.msg}"
```

```pyrepl
>>> g = GoodErr(404, "없음")
>>> g.args
(404, '없음')
>>> str(g)
'[404] 없음'
>>> r = pickle.loads(pickle.dumps(g))
>>> r, r.code
([404] 없음, 404)
```

`args` 는 **재생성 레시피**이고 `__str__` 은 **표시 방법**이다. 둘을 섞지 마라.
:::

::: note KeyError 의 str 은 왜 따옴표가 붙나
```pyrepl
>>> try:
...     {}["없는 키"]
... except KeyError as e:
...     print("str: ", str(e))
...     print("args:", e.args[0])
...
str:  '없는 키'
args: 없는 키
```

`KeyError.__str__` 은 `repr(args[0])` 을 반환하도록 특별히 오버라이드돼 있다. 키가 `""` 나 `" "` 일 때 메시지가 비어 보이는 걸 막기 위해서다.

그래서 **`str(e)` 를 사용자에게 보여주면 따옴표가 딸려 나온다.** 키가 필요하면 `e.args[0]` 을 써라.
:::

## ExceptionGroup 과 `except*` (3.11+)

지금까지의 모든 이야기에는 **암묵적 전제**가 하나 있었다. *"한 번에 하나의 예외만 전파된다."*

이 전제는 40년 동안 잘 통했다. 스택은 하나였으니까. 그런데 동시성이 오면서 깨진다.

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(fetch_a())    # ValueError 로 실패
    tg.create_task(fetch_b())    # TypeError 로 실패
    tg.create_task(fetch_c())    # 성공
```

**두 개가 동시에 실패했다.** 어느 쪽을 올릴 것인가? 하나를 고르면 다른 하나는 사라진다. `__context__` 로 잇는 것도 거짓말이다 — 둘은 인과관계가 아니라 **형제**다.

`ExceptionGroup` 은 이 문제 하나를 위해 만들어졌다 (PEP 654).

```python title="여러 예외를 하나로 묶는다"
errs = []
for fn in (a, b):
    try:
        fn()
    except Exception as e:
        errs.append(e)

raise ExceptionGroup("두 작업 실패", errs)
```

트레이스백이 **트리로** 찍힌다. 각 하위 예외가 자기 트레이스백을 그대로 들고 있다.

```text nolines
  + Exception Group Traceback (most recent call last):
  |   File "run.py", line 12, in <module>
  |     raise ExceptionGroup("두 작업 실패", errs)
  | ExceptionGroup: 두 작업 실패 (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | Traceback (most recent call last):
    |   File "run.py", line 9, in <module>
    |     fn()
    |     ~~^^
    |   File "run.py", line 2, in a
    |     raise ValueError("v1")
    | ValueError: v1
    +---------------- 2 ----------------
    | Traceback (most recent call last):
    |   File "run.py", line 9, in <module>
    |     fn()
    |     ~~^^
    |   File "run.py", line 4, in b
    |     raise TypeError("t1")
    | TypeError: t1
    +------------------------------------
```

### `except*` — 절이 여러 개 실행된다

`ExceptionGroup` 은 `Exception` 의 자손이므로 `except ExceptionGroup` 으로 잡을 수는 있다. 하지만 그러면 안에서 `isinstance` 로 뒤져야 한다. `except*` 가 그 일을 해 준다.

```pyrepl
>>> eg = ExceptionGroup("작업 실패", [ValueError("v1"), TypeError("t1"), ValueError("v2")])
>>> try:
...     raise eg
... except* ValueError as e:
...     print("ValueError 그룹:", e.exceptions)
... except* TypeError as e:
...     print("TypeError 그룹:", e.exceptions)
...
ValueError 그룹: (ValueError('v1'), ValueError('v2'))
TypeError 그룹: (TypeError('t1'),)
```

**둘 다 실행됐다.** 이게 `except` 와의 결정적 차이다.

```text nolines
except   : 위에서부터 검사하다 처음 맞는 절 하나만 실행하고 끝
except*  : 모든 절을 검사한다. 그룹을 쪼개서 해당하는 조각을 각 절에 넘긴다
```

`as e` 로 받는 것은 **개별 예외가 아니라 하위 그룹**이다. 위에서 `e` 는 `ValueError` 가 아니라 `ExceptionGroup` 이다. 이름에 속지 마라.

안 잡힌 나머지는 **새 그룹으로 묶여 다시 올라간다.**

```pyrepl
>>> try:
...     try:
...         raise ExceptionGroup("g", [ValueError("v"), OSError("o")])
...     except* ValueError:
...         print("v 처리")
... except ExceptionGroup as e:
...     print("남은 것:", e.exceptions)
...
v 처리
남은 것: (OSError('o'),)
```

::: deep BaseExceptionGroup.__new__ 도 클래스를 바꿔치기한다
`OSError` 에서 봤던 그 트릭이다.

```pyrepl
>>> type(BaseExceptionGroup("x", [ValueError()]))
<class 'ExceptionGroup'>
>>> type(BaseExceptionGroup("x", [KeyboardInterrupt()]))
<class 'BaseExceptionGroup'>
```

`BaseExceptionGroup` 은 **넣은 예외가 전부 `Exception` 의 자손이면 자동으로 `ExceptionGroup` 으로 강등된다.**

왜? `except Exception` 이 제대로 동작하게 하려고. 만약 모두가 `BaseExceptionGroup` 이면 그건 `Exception` 이 아니므로 `except Exception` 에 안 잡힌다. 평범한 예외들을 묶었을 뿐인데 갑자기 `KeyboardInterrupt` 급으로 승격되는 셈이다.

반대로 `ExceptionGroup` 에 `BaseException` 을 넣으려 하면 거부한다.

```pyrepl
>>> ExceptionGroup("x", [KeyboardInterrupt()])
Traceback (most recent call last):
  ...
TypeError: Cannot nest BaseExceptions in an ExceptionGroup
```

**"타입 계층이 거짓말을 하지 않는다"** 를 지키기 위해 생성자가 일한다.
:::

### 그룹을 나눈다 — `split` 과 `subgroup`

`except*` 는 사실 `split()` 위에 얹은 문법 설탕이다. 직접 쓸 수도 있다.

```pyrepl
>>> eg = ExceptionGroup("바깥", [
...     ValueError("v1"),
...     ExceptionGroup("안쪽", [TypeError("t1"), ValueError("v2")]),
... ])
>>> match, rest = eg.split(ValueError)
>>> match
ExceptionGroup('바깥', [ValueError('v1'), ExceptionGroup('안쪽', [ValueError('v2')])])
>>> rest
ExceptionGroup('바깥', [ExceptionGroup('안쪽', [TypeError('t1')])])
```

**중첩 구조가 그대로 보존된다.** 평평하게 만들지 않는다. `ValueError('v2')` 가 원래 "바깥 → 안쪽" 경로에 있었다는 사실이 남는다.

`subgroup` 은 임의의 조건 함수를 받는다.

```pyrepl
>>> eg.subgroup(lambda e: isinstance(e, ValueError) and "2" in str(e))
ExceptionGroup('바깥', [ExceptionGroup('안쪽', [ValueError('v2')])])
```

::: warn ExceptionGroup 을 상속할 거면 __new__ 와 derive 를 둘 다 구현하라
`split` 이 새 그룹을 만들 때 `derive()` 를 호출한다. 커스텀 필드가 있으면 안 넘어간다.

```python title="올바른 ExceptionGroup 서브클래스"
class BatchError(ExceptionGroup):
    def __new__(cls, message, excs, batch_id):
        self = super().__new__(cls, message, excs)   # __new__ 가 필수다
        self.batch_id = batch_id
        return self

    def __init__(self, message, excs, batch_id):
        super().__init__(message, excs)
        self.batch_id = batch_id

    def derive(self, excs):                          # split/subgroup 이 부른다
        return BatchError(self.message, excs, self.batch_id)
```

```pyrepl
>>> eg = BatchError("배치 실패", [ValueError("v"), TypeError("t")], batch_id=7)
>>> m, r = eg.split(ValueError)
>>> type(m).__name__, m.batch_id, m.exceptions
('BatchError', 7, (ValueError('v'),))
```

`__new__` 를 빼먹으면 **생성 자체가 안 된다.** `BaseExceptionGroup.__new__` 가 인자 2개만 받기 때문이다.

```pyrepl
>>> class Bad(ExceptionGroup):
...     def __init__(self, message, excs, batch_id):
...         super().__init__(message, excs)
...         self.batch_id = batch_id
...
>>> Bad("x", [ValueError("v")], 1)
Traceback (most recent call last):
  ...
TypeError: BaseExceptionGroup.__new__() takes exactly 2 arguments (3 given)
```

`derive` 를 빼먹으면 만들어지긴 하는데 `split` 이 필드를 잃어버린다. 둘 다 해야 한다.
:::

::: warn except* 의 제약들
`except*` 는 문법 수준에서 여러 가지를 막는다. 전부 이유가 있다.

```python
try:
    ...
except ValueError:       # SyntaxError: cannot have both 'except'
    ...                  #   and 'except*' on the same 'try'
except* TypeError:
    ...
```

섞을 수 없다. 의미가 정반대(하나만 실행 vs 전부 실행)라 한 `try` 에 공존하면 읽는 사람이 반드시 틀린다.

```python
for i in range(3):
    try:
        ...
    except* ValueError:
        break            # SyntaxError: 'break', 'continue' and 'return'
                         #   cannot appear in an except* block
```

`except*` 는 **여러 절이 순차 실행**되는데, 중간에 빠져나가면 나머지 절이 실행되지 않는다. 그러면 안 잡힌 예외가 조용히 사라진다. 아예 금지했다.

```pyrepl
>>> try:
...     raise ExceptionGroup("g", [ValueError()])
... except* ExceptionGroup:
...     pass
...
Traceback (most recent call last):
  ...
TypeError: catching ExceptionGroup with except* is not allowed. Use except instead.
```

이건 런타임 에러다. 그룹으로 그룹을 잡으면 재귀 구조가 모호해진다.

그리고 하나 더 — **`except*` 는 그룹이 아닌 평범한 예외도 잡는다.** 자동으로 감싼다.

```pyrepl
>>> try:
...     raise ValueError("혼자")
... except* ValueError as e:
...     print(type(e).__name__, e.exceptions)
...
ExceptionGroup (ValueError('혼자',))
```
:::

::: hist 왜 새 문법까지 만들었나
PEP 654 논의에서 "그냥 `ExceptionGroup` 클래스만 만들고 `except` 로 잡으면 되지 않나?" 라는 반론이 있었다.

문제는 **하위 호환**이다. 기존 코드에 `except ValueError:` 가 100만 줄 있다. 어느 날 `asyncio.gather` 가 `ExceptionGroup` 을 던지기 시작하면 그 100만 줄이 전부 예외를 놓친다. `ExceptionGroup` 은 `ValueError` 가 아니니까.

그래서 두 세계를 분리했다.

- **기존 `except`** — 그룹을 **통째로만** 잡는다. 안을 들여다보지 않는다.
- **새 `except*`** — 그룹의 내용물을 본다.

이 분리 덕분에 라이브러리가 `ExceptionGroup` 을 던지기 시작해도 기존 코드가 **조용히 잘못 동작하지 않는다.** 잡히지 않고 위로 올라가서 **시끄럽게 실패**한다. 조용한 오작동보다 시끄러운 실패가 낫다는 게 파이썬의 일관된 선택이다.
:::

::: tip asyncio.TaskGroup 이 실전 진입점이다
`ExceptionGroup` 을 직접 만들 일은 드물다. 대부분 `TaskGroup` 이 만들어서 준다.

```python title="여러 태스크의 실패를 타입별로 처리"
async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom("A", ValueError))
            tg.create_task(boom("B", TypeError))
    except* ValueError as eg:
        print("ValueError:", [str(x) for x in eg.exceptions])
    except* TypeError as eg:
        print("TypeError:", [str(x) for x in eg.exceptions])

asyncio.run(main())
```

```text nolines
ValueError: ['A']
TypeError: ['B']
```

[4.7 asyncio 실전](#/asyncio-advanced)에서 본격적으로 쓴다.
:::

## 3.11+ 의 세밀한 에러 위치

3.10까지 트레이스백은 **줄 번호**만 알려 줬다. 이 줄에서 무엇이 `None` 인지는 알려 주지 않았다.

```python title="config.py"
def get(cfg):
    return cfg["a"]["b"]["c"]["d"]

get({"a": {"b": {"c": None}}})
```

3.11부터는 이렇게 나온다.

```text nolines
Traceback (most recent call last):
  File "config.py", line 4, in <module>
    get({"a": {"b": {"c": None}}})
    ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "config.py", line 2, in get
    return cfg["a"]["b"]["c"]["d"]
           ~~~~~~~~~~~~~~~~~~^^^^^
TypeError: 'NoneType' object is not subscriptable
```

`~~~` 는 **평가된 부분**, `^^^` 는 **실패한 연산**이다. `cfg["a"]["b"]["c"]` 까지는 성공했고 그 결과에 `["d"]` 를 하다 죽었다는 게 한눈에 보인다. 3.10에서는 네 개의 `[]` 중 어느 것인지 알 수 없어서 `print` 를 박아 가며 찾아야 했다.

산술식에서도 마찬가지다.

```text nolines
  File "calc.py", line 2, in calc
    return a / b + c / d
                   ~~^~~
ZeroDivisionError: division by zero
```

**`a / b` 가 아니라 `c / d` 다.** 한 줄에 나눗셈이 두 개 있어도 즉시 특정된다.

::: deep co_positions — 어디서 오는 정보인가
바이트코드 명령어마다 **(시작 줄, 끝 줄, 시작 열, 끝 열)** 4-튜플이 붙어 있다 (PEP 657).

```pyrepl
>>> def f(x):
...     return x + 1
...
>>> list(f.__code__.co_positions())
[(1, 1, 0, 0), (2, 2, 11, 12), (2, 2, 15, 16), (2, 2, 11, 16), ..., (2, 2, 4, 16)]
```

`(2, 2, 11, 12)` 는 2번 줄 11~12열 — `x`. `(2, 2, 15, 16)` 은 `1`. `(2, 2, 11, 16)` 이 `BINARY_OP`, 즉 `x + 1` 전체다. 예외가 나면 인터프리터는 **터진 명령어의 위치**를 이 표에서 읽어 캐럿을 그린다.

이 정보는 `co_linetable` 에 압축돼 들어간다. 공짜는 아니다.

```text nolines
argparse   code=45598  linetable=20799 (0.46x)  exctable=514 (0.01x)
inspect    code=54154  linetable=25185 (0.47x)  exctable=867 (0.02x)
```

`-X no_debug_ranges` 로 열 정보를 빼면 이렇게 줄어든다.

```text nolines
argparse   code=45598  linetable=14804 (0.32x)
inspect    code=54154  linetable=17580 (0.32x)
```

`argparse` 기준 약 6KB, **바이트코드 크기의 13%** 다. `.pyc` 파일이 커지고 그만큼 메모리에 올라간다.

**대신 실행 속도에는 영향이 없다.** 이 표는 예외가 났을 때만 읽힌다. 예외 테이블과 같은 원리다.

임베디드처럼 바이트가 아쉬운 환경이 아니면 **끄지 마라.** 6KB 아끼려고 디버깅 시간을 몇 시간 쓰는 건 나쁜 거래다.
:::

::: note "Did you mean" 은 어떻게 알아내나
```pyrepl
>>> import collections
>>> collections.OrderedDcit
Traceback (most recent call last):
  File "<python-input-1>", line 1, in <module>
    collections.OrderedDcit
AttributeError: module 'collections' has no attribute 'OrderedDcit'. Did you mean: 'OrderedDict'?
```

예외가 **날 때**가 아니라 **출력될 때** 계산된다. `AttributeError` 는 `name`(찾던 이름)과 `obj`(찾은 대상)를 들고 있고, 트레이스백을 찍는 순간 `dir(obj)` 를 훑어 편집 거리(Levenshtein)가 가까운 후보를 고른다.

`NameError` 도 같은 방식으로 지역/전역/내장 이름을 훑는다. 그래서 **비용이 예외 발생 경로에 없다.** 잡아서 처리하는 예외라면 이 계산은 아예 일어나지 않는다.
:::

::: cote 코딩테스트에서 실제로 만나는 예외
**1. `RecursionError` — 가장 흔한 사고.**

```pyrepl
>>> import sys
>>> sys.getrecursionlimit()
1000
>>> def f(n): return 1 if n == 0 else f(n-1) + 1
>>> f(5000)
Traceback (most recent call last):
  ...
RecursionError: maximum recursion depth exceeded
```

DFS 깊이가 10만인 그래프 문제에서 즉시 터진다. `RecursionError` 는 `RuntimeError` 의 자식이라 `except Exception` 에 잡힌다 — 그래서 **재귀 DFS를 `try/except` 로 감싸면 무한 루프에 빠질 수 있다.**

관용구는 이것이다.

```python
import sys
sys.setrecursionlimit(10**6)
```

다만 한도만 올리면 이번엔 **C 스택이 넘쳐 인터프리터가 통째로 죽는다** (파이썬 예외가 아니라 세그폴트). 깊이가 정말 깊으면 반복문 + 명시적 스택으로 바꿔라. ([7.13 그래프 표현과 순회](#/graph))

**2. 입력 끝 감지.**

```python
import sys

for line in sys.stdin:          # ✅ EOF 에서 자연스럽게 끝난다
    process(line)
```

`input()` 을 `while True` 로 돌리다 `EOFError` 로 빠져나오는 코드를 종종 보는데, 예외가 딱 한 번 나므로 성능 문제는 없다. 다만 위가 훨씬 빠르다. ([8.2 파이썬 입출력 최적화](#/io-optimize))

**3. 뜨거운 루프의 `try/except` 는 걱정하지 마라.** 앞에서 봤듯 예외가 안 나면 비용이 0이다. `dict` 조회를 `try/except KeyError` 로 감싸는 건 시간 초과의 원인이 아니다 — **예외가 매번 나는 경우만 아니라면.**
:::

## 요약

- **`BaseException` 과 `Exception` 의 경계는 "에러"와 "종료 신호"의 경계다.** `SystemExit`, `KeyboardInterrupt`, `GeneratorExit`, `asyncio.CancelledError` 는 잡으면 안 된다. `except:` 대신 **항상 `except Exception:`**.
- **`else` 는 `try` 블록을 좁히는 도구다.** `try` 가 넓으면 `except` 가 엉뚱한 예외를 자기 것으로 착각한다.
- **`finally` 안의 `return`/`break`/`continue` 는 예외를 삼킨다.** 3.14는 `SyntaxWarning` 으로 경고한다 (PEP 765).
- **`__context__` 는 자동, `__cause__` 는 의도.** `raise X from Y` 로 저수준 예외를 도메인 예외로 번역하되 원인을 남겨라. `from None` 은 `__context__` 를 **지우지 않고** 출력만 끈다.
- **3.11부터 `try` 는 공짜다** (예외 테이블). 비싼 건 `raise` 로, 반환보다 5.3배 + 프레임당 65ns. **예외가 예외적일 때 EAFP.**
- **커스텀 예외는 `super().__init__` 에 인자를 그대로 넘겨라.** `args` 가 피클링 레시피다. 어기면 `multiprocessing` 에서 원인 예외가 증발한다.
- **`ExceptionGroup`/`except*` 는 "동시에 여러 개가 실패하는" 세계를 위한 것이다.** `except*` 는 **모든 절이 실행**되고, `as e` 로 받는 건 개별 예외가 아니라 **하위 그룹**이다.

::: quiz 연습문제
1. 도입부의 세 코드 ①②③이 각각 왜 틀렸는지 한 문장씩으로 답하라. 그리고 ③을 고쳐라.

2. 다음 함수의 반환값을 **예측한 뒤** 실행하라. 그리고 3.14에서 어떤 경고가 나오는지 확인하라.

   ```python
   def f():
       try:
           return "A"
       finally:
           return "B"

   def g():
       try:
           raise ValueError("x")
       except ValueError:
           return "except"
       finally:
           return "finally"
   ```

3. 다음에서 `print` 세 줄의 출력을 예측하라. 특히 세 번째를 조심하라.

   ```python
   try:
       try:
           1 / 0
       except ZeroDivisionError:
           raise ValueError("bad") from None
   except ValueError as e:
       print(e.__cause__)
       print(e.__suppress_context__)
       print(e.__context__)
   ```

4. 아래 `except*` 는 몇 개의 절이 실행되고, 최종적으로 어떤 예외가 밖으로 나가는가? 예측한 뒤 실행하라.

   ```python
   try:
       raise ExceptionGroup("g", [
           ValueError("v1"),
           KeyError("k1"),
           ExceptionGroup("inner", [ValueError("v2"), OSError("o1")]),
       ])
   except* ValueError as e:
       print("V:", e.exceptions)
   except* LookupError as e:
       print("L:", e.exceptions)
   ```

5. **깊이 생각해 볼 문제.** 아래 예외 클래스는 단위 테스트를 전부 통과한다. 그런데 `ProcessPoolExecutor` 워커에서 이 예외가 나면 부모 프로세스는 엉뚱한 `TypeError` 를 본다. 왜인가? 그리고 테스트로 이 버그를 잡으려면 어떤 한 줄을 추가해야 하나?

   ```python
   class ValidationError(Exception):
       def __init__(self, field, value):
           super().__init__(f"{field} 의 값 {value!r} 이 올바르지 않다")
           self.field = field
           self.value = value
   ```
:::

**다음 절**: [1.17 컨텍스트 매니저](#/context-managers) — `finally` 를 손으로 쓰지 않게 해 주는 장치. `with` 는 문법 설탕이 아니라 `__enter__`/`__exit__` 프로토콜이고, `__exit__` 이 `True` 를 반환하면 예외가 사라진다.
