# 5.4 C 확장, ctypes, cffi

::: lead
파이썬으로 못 하는 계산은 거의 없다. 문제는 **속도**다. 순수 파이썬 반복문이 병목이라면, 결국 답은 "그 부분만 C로 짜서 파이썬에서 부른다"는 것으로 수렴한다. 이 절은 가장 가볍고 직접적인 방법인 `ctypes`로 시작해서, 이미 컴파일된 라이브러리(운영체제 표준 라이브러리, DLL, 서드파티 `.so`/`.dll`)를 파이썬에서 그대로 호출하는 법을 다룬다. 그리고 그 과정에서 반드시 마주치는 질문 — "C 확장이 정말 GIL을 놓아주는가?" — 을 추측이 아니라 스레드로 직접 재는 것으로 답한다.
:::

## 왜 새 언어를 안 배우고 C를 부르는가

[5.3 파이썬 레벨 최적화](#/py-optimize)에서 지역 변수, 내장 함수, 자료구조 선택으로 짜낼 수 있는 성능은 짜냈다고 하자. 그래도 안 되는 계산이 있다. 파이썬 인터프리터 자체의 오버헤드 — 바이트코드 디스패치, 객체 박싱, 참조 카운트 증감 — 는 알고리즘을 아무리 잘 짜도 사라지지 않는다. [3.7 바이트코드](#/bytecode)에서 본 것처럼 파이썬의 `+` 하나도 여러 단계의 바이트코드와 디스패치를 거친다.

이걸 벗어나는 길은 결국 하나다. **뜨거운 구간을 기계어로 실행한다.** 방법은 여러 갈래다.

- **이미 컴파일된 라이브러리를 그대로 부른다** — `ctypes`, `cffi` (이 절)
- **파이썬과 비슷한 문법으로 짜서 C로 컴파일한다** — Cython, mypyc ([5.5 Cython, Numba, mypyc](#/compilers))
- **다른 언어로 새로 짜서 파이썬 모듈로 노출한다** — C 확장 API, PyO3/Rust ([5.6 Rust 확장](#/pyo3))

이 절이 다루는 `ctypes`와 `cffi`는 셋 중 가장 가볍다. **새로 컴파일할 필요가 없다.** 이미 시스템에 있는 `.dll`이나 `.so`를 파이썬 프로세스 안으로 불러와서, 그 안의 함수를 파이썬 함수처럼 호출한다. 대신 대가가 있다 — 타입을 **당신이 직접, 정확하게** 선언해야 한다. 컴파일러가 봐주지 않는다.

## ctypes로 진짜 C 함수를 불러보기

`ctypes`는 표준 라이브러리다. 별도 설치가 필요 없다. `ctypes.CDLL()`에 라이브러리 이름을 주면 그 라이브러리가 프로세스 메모리에 로드되고, 그 안의 심볼(함수)에 파이썬 속성처럼 접근할 수 있다.

Windows에는 C 런타임이 `msvcrt`라는 이름으로 항상 있다. (POSIX 계열이면 `ctypes.CDLL("libc.so.6")`이 같은 역할을 한다.) 진짜 C 표준 라이브러리 함수를 불러보자.

```python title="msvcrt.printf를 파이썬에서 직접 호출"
import ctypes

msvcrt = ctypes.CDLL("msvcrt")
msvcrt.printf(b"hello from C: %d\n", 42)
```

```text nolines
hello from C: 42
17
```

두 번째 줄 `17`은 REPL/스크립트가 `printf`의 **반환값**(출력한 문자 수)을 그대로 찍은 것이다. 이건 파이썬 코드가 아니다. **glibc/msvcrt 안의 진짜 C 함수가 실행된 것**이고, 그 함수는 지금 이 프로세스의 stdout에 직접 쓴다.

몇 가지 더 불러보면 감이 온다.

```python title="C 표준 라이브러리 함수 여러 개"
import ctypes

msvcrt = ctypes.CDLL("msvcrt")

msvcrt.strlen.argtypes = [ctypes.c_char_p]
msvcrt.strlen.restype = ctypes.c_size_t
print(msvcrt.strlen(b"hello world"))     # 11

msvcrt.abs.argtypes = [ctypes.c_int]
msvcrt.abs.restype = ctypes.c_int
print(msvcrt.abs(-42))                   # 42

msvcrt.sqrt.argtypes = [ctypes.c_double]
msvcrt.sqrt.restype = ctypes.c_double
print(msvcrt.sqrt(2.0))                  # 1.4142135623730951
```

```text nolines
11
42
1.4142135623730951
```

(Python 3.14.5 / Windows 실측.) 세 함수 다 파이썬으로 짠 것이 아니라 C 런타임 안에 이미 컴파일되어 있던 것을 그대로 호출했다.

## `argtypes`와 `restype` — 생략하면 조용히 틀린다

방금 코드에서 매번 `argtypes`와 `restype`을 지정했다. **이걸 생략해도 일단 실행은 된다.** 문제는 실행이 되면서 **틀린 값**을 낼 수 있다는 것이다.

ctypes는 함수 시그니처를 모르면 인자를 전부 `int`로, 반환값도 `int`(C의 `int`, 즉 32비트)로 가정한다. 64비트 포인터를 반환하는 함수에서 이 가정은 바로 사고로 이어진다.

```python title="restype을 지정하지 않으면 포인터가 잘린다"
import ctypes

msvcrt = ctypes.CDLL("msvcrt")
msvcrt.malloc.argtypes = [ctypes.c_size_t]

p_wrong = msvcrt.malloc(8)          # restype 미지정 → 기본값 c_int로 해석
print(p_wrong)

msvcrt.malloc.restype = ctypes.c_void_p
p_right = msvcrt.malloc(8)          # 이번엔 올바르게 c_void_p로 해석
print(p_right)
```

```text nolines
-702587328
2318579752544
```

(Python 3.14.5 / Windows 실측. 두 호출 모두 malloc이 반환한 **같은 종류의 64비트 포인터**인데, 첫 번째는 그 값을 32비트 정수로 잘라 읽어서 완전히 다른 — 심지어 음수인 — 값이 나온다.)

이게 바로 `ctypes`를 쓸 때 컴파일러가 없어서 생기는 위험이다. C 컴파일러는 헤더 파일의 함수 선언을 보고 타입을 검사해 주지만, `ctypes`는 그런 게 없다. **당신이 선언한 타입을 그냥 믿고 메모리를 그 모양으로 읽는다.** 타입을 잘못 선언하면 컴파일 에러가 아니라 **조용히 틀린 값**, 운이 나쁘면 크래시가 나온다.

::: danger 잘못된 restype/argtypes는 컴파일 에러 없이 크래시로 이어진다
`ctypes`는 선언한 타입대로 메모리를 해석한다. 실제 함수가 8바이트를 반환하는데 `c_int`(4바이트)로 읽으면 절반만 읽고 나머지 절반은 다음 호출에 영향을 줄 수도 있다. 포인터를 정수로 착각하고 산술 연산을 하면 임의의 메모리 주소를 만들어 접근하게 되고, 최악의 경우 파이썬 프로세스 자체가 죽는다(세그폴트). **`argtypes`/`restype`을 생략하지 마라.** 특히 포인터, `size_t`, `long long`을 반환하는 함수는 반드시 지정한다.
:::

::: tip 관례
새 라이브러리를 ctypes로 감쌀 때는 함수를 쓰기 전에 항상 `argtypes`와 `restype`부터 선언하는 습관을 들여라. 매번 번거롭지만, 이 두 줄이 "타입 체크가 없는 세계"에서 유일한 안전벨트다.
:::

## 구조체 정의하기

C 함수 중에는 구조체를 인자로 받거나 반환하는 것이 많다. `ctypes.Structure`를 상속해서 `_fields_`에 필드 이름과 타입을 나열하면 C의 `struct`와 메모리 레이아웃이 완전히 같은 파이썬 클래스가 만들어진다.

```python title="C의 POINT 구조체를 파이썬에서"
import ctypes

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

pt = POINT(3, 4)
print(pt.x, pt.y)
print(ctypes.sizeof(POINT))
```

```text nolines
3 4
8
```

`c_long`이 4바이트(Windows)이므로 `x`, `y` 두 필드로 구조체 크기는 정확히 8바이트다. 이 구조체를 실제 Windows API 호출에 그대로 쓸 수 있다 — `user32.dll`의 `GetCursorPos`는 `POINT*`를 받아서 그 자리에 현재 마우스 좌표를 채워 넣는다.

```python title="진짜 Windows API 호출 — 현재 마우스 좌표 읽기"
import ctypes

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

user32 = ctypes.windll.user32
pt = POINT()
ok = user32.GetCursorPos(ctypes.byref(pt))
print(ok, pt.x, pt.y)
```

```text nolines
1 1886 589
```

(Python 3.14.5 / Windows 실측. `x`, `y` 값은 실행할 때 마우스 위치에 따라 다르다.) `ctypes.byref(pt)`는 `pt`의 주소를 넘긴다는 뜻이다 — C의 `&pt`와 같다. `GetCursorPos`는 그 주소가 가리키는 메모리에 직접 좌표를 써넣는다. 파이썬 객체 하나를 **C 함수가 직접 수정**하게 만든 것이다. [1.1 객체, 이름, 참조](#/objects-names)에서 본 "함수가 인자로 받은 가변 객체를 수정한다"는 이야기의 극단적인 버전이라고 보면 된다 — 여기서는 파이썬 GC가 관리하는 메모리를 C 코드가 통째로 건드린다.

## C 함수에 파이썬 함수를 콜백으로 넘기기

방향을 반대로 뒤집을 수도 있다. C 함수가 콜백을 요구하면, 파이썬 함수를 C 함수 포인터로 감싸서 넘긴다. C 표준 라이브러리의 `qsort`가 정확히 이런 인터페이스다 — 정렬 기준을 비교 함수 포인터로 받는다.

```python title="qsort에 파이썬 비교 함수를 콜백으로 넘기기"
import ctypes

msvcrt = ctypes.CDLL("msvcrt")

IntArray5 = ctypes.c_int * 5
arr = IntArray5(5, 2, 4, 1, 3)

CMPFUNC = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
)

def cmp_func(a, b):
    return a[0] - b[0]          # 이 함수 본문은 순수 파이썬이다

msvcrt.qsort(arr, len(arr), ctypes.sizeof(ctypes.c_int), CMPFUNC(cmp_func))
print(list(arr))
```

```text nolines
[1, 2, 3, 4, 5]
```

`qsort`의 정렬 알고리즘(퀵소트)은 C로 실행되지만, 실제 원소를 비교하는 매 순간마다 **파이썬 인터프리터로 다시 들어와서** `cmp_func`를 실행한다. 이 왕복 비용 때문에, 콜백을 파이썬으로 넘기는 패턴은 "C로 감쌌으니 빠르겠지"라는 기대를 자주 배신한다. 비교 함수 자체가 뜨거운 경로라면, 그 부분도 C 쪽에 있어야 진짜 이득이 난다.

## C 확장은 정말 GIL을 놓아주는가

[4.3 GIL](#/gil)에서 배웠듯이, 한 프로세스 안에서 파이썬 바이트코드를 실행할 수 있는 스레드는 항상 하나뿐이다. 그런데 "C 확장은 GIL을 놓아줄 수 있다"는 말을 들어봤을 것이다. 정확히 무슨 뜻일까.

C로 짠 확장 함수는 그 함수 본문 안에서 **파이썬 객체를 전혀 건드리지 않는 순수 계산 구간**이 있으면, 그 구간에서 명시적으로 GIL을 놓을 수 있다. CPython C API의 `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` 매크로가 그 경계를 표시한다.

```c title="CPython C 확장에서 GIL을 놓는 관용구 (개념 코드)"
static PyObject *
heavy_compute(PyObject *self, PyObject *args) {
    long n;
    if (!PyArg_ParseTuple(args, "l", &n))
        return NULL;

    long result;
    Py_BEGIN_ALLOW_THREADS
    /* 이 구간은 파이썬 객체를 만들거나 건드리지 않는다.
       그래서 다른 스레드가 그동안 GIL을 잡고 파이썬 바이트코드를 실행할 수 있다. */
    result = pure_c_loop(n);
    Py_END_ALLOW_THREADS

    return PyLong_FromLong(result);
}
```

이게 안전한 이유는 명확하다. GIL이 보호하는 것은 **파이썬 객체의 참조 카운트와 내부 상태**다 ([5.2 메모리 모델](#/memory)의 참조 카운팅을 떠올려라). `Py_BEGIN_ALLOW_THREADS` 구간 안에서 순수 C 데이터(정수, 배열, 구조체)만 다루고 파이썬 객체 API를 하나도 부르지 않는다면, 그 구간이 다른 스레드와 동시에 실행돼도 파이썬 쪽 상태는 전혀 위험하지 않다. NumPy의 행렬 곱셈, 압축 라이브러리의 인코딩 루프 같은 게 실제로 이 패턴을 쓴다.

### 눈으로 확인 가능한 예: `time.sleep`

이걸 추상적으로만 남겨두지 않으려면 실제로 GIL을 놓는 C 함수로 측정해야 한다. 마침 아주 좋은 예가 표준 라이브러리에 있다 — **`time.sleep`은 C로 구현되어 있고, 그 대기 구간에서 GIL을 놓는다.** 순수 파이썬으로 잠을 자는 방법은 없으니, `sleep` 중에 다른 스레드가 진짜로 실행될 수 있는지 재보면 된다.

```python title="스레드 4개가 0.5초씩 sleep — 동시에 실행되는가?"
import time
import threading

N = 4
DUR = 0.5

def worker():
    time.sleep(DUR)

# 순차 실행: 스레드 없이 그냥 4번 반복
t0 = time.perf_counter()
for _ in range(N):
    worker()
t1 = time.perf_counter()
print("순차:", t1 - t0)

# 스레드 4개를 동시에 띄움
threads = [threading.Thread(target=worker) for _ in range(N)]
t0 = time.perf_counter()
for th in threads:
    th.start()
for th in threads:
    th.join()
t1 = time.perf_counter()
print("스레드:", t1 - t0)
```

```text nolines
순차: 2.0009246999979951
스레드: 0.5014953999780118
```

(Python 3.14.5 / Windows 실측.) 순차 실행은 `0.5초 × 4 = 2.0초` — 예상대로다. 스레드 버전은 **0.5초 하나로 끝난다.** 4개의 스레드가 동시에 잠들었다가 동시에 깼다는 뜻이다. 이게 가능한 유일한 이유는 `time.sleep`의 C 구현이 대기 구간에서 GIL을 놓아서, 한 스레드가 잠들어 있는 동안 다른 스레드들도 (마찬가지로 잠들기 위해) GIL을 얻어 진행할 수 있었기 때문이다.

### 대조: 순수 파이썬 CPU 연산은 놓아주지 않는다

같은 실험을 I/O나 대기가 아니라 **순수 파이썬 계산**으로 바꾸면 정반대 결과가 나와야 한다. 파이썬 바이트코드를 실행하는 구간은 GIL을 계속 붙들고 있으니까.

```python title="같은 실험, 이번엔 CPU 바운드 파이썬 코드로"
import time
import threading

N = 4
COUNT = 20_000_000

def cpu_work(n):
    x = 0
    for i in range(n):
        x += i * i
    return x

t0 = time.perf_counter()
for _ in range(N):
    cpu_work(COUNT)
t1 = time.perf_counter()
print("순차:", t1 - t0)

threads = [threading.Thread(target=cpu_work, args=(COUNT,)) for _ in range(N)]
t0 = time.perf_counter()
for th in threads:
    th.start()
for th in threads:
    th.join()
t1 = time.perf_counter()
print("스레드:", t1 - t0)
```

```text nolines
순차: 2.2493548000056762
스레드: 2.288331099989591
```

(Python 3.14.5 / Windows 실측.) 스레드로 나눠도 **전혀 빨라지지 않는다.** 오히려 스레드 전환 오버헤드 때문에 살짝 더 걸렸다. 순수 파이썬 반복문은 매 사이클 파이썬 객체(`int`)를 만들고 참조 카운트를 만지므로 GIL을 계속 쥐고 있어야 하고, 그래서 4개 스레드가 있어도 실질적으로 한 번에 하나씩만 돈다. [4.3 GIL](#/gil)에서 다룬 "CPU 바운드 작업에 threading을 쓰면 안 되는 이유"가 바로 이 두 벤치마크의 대비다.

::: note free-threaded 빌드에서는 다르다
이 결과는 표준(GIL 있는) 빌드 기준이다. [4.3 GIL](#/gil)에서 다룬 free-threaded 빌드(`python3.14t`)에서는 GIL 자체가 없으므로 두 번째 벤치마크도 스레드 수만큼 가까이 빨라질 수 있다. 하지만 그 세계에서도 C 확장이 스레드 안전하게 짜여 있어야 한다는 전제는 그대로다.
:::

::: perf 이 지식을 언제 실전에 쓰는가
"이 라이브러리에 스레드를 여러 개 써서 병렬화할 수 있는가?"에 대한 답은 결국 "그 라이브러리의 뜨거운 구간이 GIL을 놓는가"로 귀결된다. NumPy의 많은 연산, `zlib`/`hashlib`의 압축·해시 연산, 그리고 지금 본 `time.sleep`류의 대기 함수들은 GIL을 놓는다 — 그래서 이들을 `threading`으로 병렬화하면 실제로 이득이 있다. 반대로 순수 파이썬 루프는 아무리 스레드를 늘려도 소용없다 — [4.4 multiprocessing](#/multiprocessing)이나 애초에 C/Cython으로 옮기는 것만이 답이다. 라이브러리 문서에 "releases the GIL"이라고 명시돼 있는지 확인하는 습관을 들여라.
:::

## cffi — ctypes보다 선언적인 대안

`ctypes`는 함수 하나하나를 파이썬 코드로 선언해야 한다. 함수가 몇 개 안 되면 괜찮지만, 대상 라이브러리의 헤더가 크면 지루하고 실수하기 쉽다. `cffi`(C Foreign Function Interface)는 다른 접근을 취한다 — **C 헤더 선언 문법을 그대로 문자열로 던져주면**, `cffi`가 그걸 파싱해서 함수·구조체 바인딩을 자동으로 만든다.

```python title="cffi로 같은 msvcrt 함수 호출"
from cffi import FFI

ffi = FFI()
ffi.cdef("""
    int abs(int x);
    size_t strlen(const char* s);
""")
C = ffi.dlopen("msvcrt")

print(C.abs(-99))
print(C.strlen(b"hello cffi"))
```

```text nolines
99
10
```

(우분투/윈도우 공용 `uv run --with cffi python ...`으로 실측. `cffi`는 표준 라이브러리가 아니라 별도 패키지다.) `ctypes`처럼 `argtypes`를 함수마다 따로 선언하지 않고, C 문법 그대로의 시그니처 문자열 한 번으로 여러 함수를 한꺼번에 등록했다. 이게 `cffi`의 핵심 장점이다 — **선언이 실제 C 헤더와 1:1로 대응**하므로, 기존 C 라이브러리 문서를 거의 그대로 옮겨 붙일 수 있다.

### ctypes와 cffi, 무엇이 다른가

| | ctypes | cffi |
| --- | --- | --- |
| 설치 | 표준 라이브러리 (항상 있음) | 별도 패키지 (`pip install cffi`) |
| 시그니처 선언 | 파이썬 API로 하나씩 (`argtypes`, `restype`) | C 헤더 문법 그대로 (`cdef`) |
| 모드 | 로드된 라이브러리 호출만 (ABI 방식) | **ABI 모드**(ctypes와 동일)와 **API 모드**(빌드 시점에 C 컴파일러로 진짜 확장 모듈 생성) 둘 다 지원 |
| 대량 바인딩 | 함수가 많으면 선언 코드가 길어진다 | 헤더 통째로 넣으면 끝 |
| 성능 | 호출마다 약간의 오버헤드 | API 모드가 가장 빠르다 (실측 아래 참고) |

`cffi`의 **API 모드**는 이 절에서 다룬 ABI 모드(런타임에 동적으로 라이브러리를 찾아 호출)와 다르다 — 빌드 단계에서 C 컴파일러를 돌려 진짜 파이썬 확장 모듈(`.pyd`/`.so`)을 만들어 낸다. 이론상으로는 매 호출의 타입 해석 비용이 없어져서 ABI 모드나 `ctypes`보다 빨라야 한다. 대신 컴파일러가 필요하다는 점에서 [5.5 Cython, Numba, mypyc](#/compilers)에서 다룰 빌드 파이프라인과 비슷한 처지가 된다.

이걸 말로만 남기지 않고 실제로 재보자. `msvcrt.abs`를 200만 번 호출하는 루프를 `ctypes`, `cffi` ABI 모드, `cffi` API 모드 세 방식으로 각각 짰다. API 모드는 `ffibuilder.set_source()`로 소스를 만들고 MSVC(`vcvars64.bat` 환경에서 `python build_api.py`)로 `.pyd`까지 실제로 컴파일해서 얻은 확장 모듈을 임포트해 호출했다.

```python title="ctypes vs cffi ABI vs cffi API, 200만 호출"
import time, ctypes
from cffi import FFI

N = 2_000_000
msvcrt = ctypes.CDLL("msvcrt")
msvcrt.abs.argtypes = [ctypes.c_int]
msvcrt.abs.restype = ctypes.c_int

t0 = time.perf_counter()
for i in range(N):
    msvcrt.abs(-i)
print("ctypes:", time.perf_counter() - t0)

ffi_abi = FFI()
ffi_abi.cdef("int abs(int x);")
C_abi = ffi_abi.dlopen("msvcrt")
t0 = time.perf_counter()
for i in range(N):
    C_abi.abs(-i)
print("cffi ABI:", time.perf_counter() - t0)

import _msvcrt_api  # set_source()로 빌드해 둔 API 모드 확장
C_api = _msvcrt_api.lib
t0 = time.perf_counter()
for i in range(N):
    C_api.abs(-i)
print("cffi API:", time.perf_counter() - t0)
```

```text nolines
ctypes: 0.44
cffi ABI: 0.28
cffi API: 0.21
```

(Windows / MSVC로 실제 컴파일 후 실측, 3회 반복 평균. 호출 200만 회 기준.) 순서대로 `ctypes` > `cffi` ABI > `cffi` API — 표에 적은 "API 모드가 가장 빠르다"는 주장이 이 환경에서 그대로 확인됐다. 다만 이 수치는 단순 `int` 인자 하나짜리 함수 호출 기준이고, 절대 시간도 환경(OS, 컴파일러, 파이썬 버전)마다 달라진다. 중요한 건 절대값이 아니라 **세 방식의 상대적 순서**이므로, 이 숫자를 다른 환경의 예측치로 그대로 가져다 쓰지 마라 — 성능이 중요하면 각자 환경에서 다시 재라.

## 언제 ctypes/cffi를 쓰고, 언제 다른 도구로 가는가

이 절에서 본 도구들의 위치를 분명히 하고 넘어가자.

- **이미 컴파일된 라이브러리(OS API, 서드파티 DLL/so)를 파이썬에서 그대로 부르고 싶다** → `ctypes` (간단한 몇 함수) 또는 `cffi` (헤더가 큰 라이브러리, 또는 빌드 시점 성능이 중요할 때)
- **직접 짠 계산 로직을 빠르게 만들고 싶다, 파이썬과 비슷한 문법을 유지하고 싶다** → [5.5 Cython, Numba, mypyc](#/compilers)
- **메모리 안전성이 중요한 새 네이티브 모듈을 처음부터 짜고 싶다** → [5.6 Rust 확장 (PyO3)](#/pyo3)

::: warn 마이크로 최적화에 매몰되지 마라
`ctypes`로 C 함수 하나를 감싸느라 반나절을 쓰기 전에, 그 함수가 정말 프로그램 전체 시간의 의미 있는 비율을 차지하는지 [5.1 측정 없이 최적화 없다](#/profiling)의 프로파일러로 먼저 확인하라. 흔한 실패 패턴은 이렇다 — 전체 실행 시간의 3%를 차지하는 함수를 C로 옮겨 10배 빠르게 만들었지만, 프로그램 전체는 2.9%밖에 빨라지지 않는다. 그 사이 `argtypes` 버그로 몇 시간을 날릴 위험까지 감수할 가치가 있는지 먼저 재고 나서 손대라.
:::

## 요약

- `ctypes`는 표준 라이브러리이고, `CDLL()`/`windll`로 이미 컴파일된 라이브러리를 즉시 불러와 함수를 호출할 수 있다.
- `argtypes`와 `restype`을 생략하면 컴파일 에러 없이 **조용히 틀린 값**이 나온다. 특히 포인터·`size_t` 반환값은 반드시 지정해야 한다.
- `ctypes.Structure`로 C 구조체와 동일한 메모리 레이아웃의 파이썬 클래스를 만들 수 있고, `byref()`로 그 메모리를 C 함수가 직접 수정하게 할 수 있다.
- `CFUNCTYPE`으로 파이썬 함수를 C 콜백으로 넘길 수 있지만, 매 호출마다 파이썬 인터프리터를 왕복하므로 콜백 자체가 뜨거운 경로면 이득이 크지 않다.
- C 확장은 `Py_BEGIN_ALLOW_THREADS` 구간에서 GIL을 놓을 수 있다 — 단, 그 구간이 파이썬 객체를 전혀 건드리지 않을 때만 안전하다.
- `time.sleep`으로 실측하면 GIL이 실제로 놓이는 걸 확인할 수 있다: 4개 스레드가 0.5초씩 자면 순차로는 2초, 동시로는 0.5초가 걸린다. 순수 파이썬 CPU 루프는 스레드를 늘려도 전혀 빨라지지 않는다 — GIL을 놓지 않기 때문이다.
- `cffi`는 C 헤더 문법을 그대로 받아 바인딩을 생성한다. ABI 모드는 `ctypes`와 비슷하고, API 모드는 컴파일 단계를 거쳐 더 빠른 바인딩을 만든다 — 실측으로도 `ctypes` > cffi ABI > cffi API 순으로 느려지는 걸 확인했다(200만 호출 기준 0.44s/0.28s/0.21s).
- 손대기 전에 항상 먼저 측정하라. 작은 함수 하나를 C로 옮기는 데 드는 위험과 시간이, 그게 프로그램 전체에 주는 이득보다 클 때가 많다.

::: quiz 연습문제
1. 다음 코드는 왜 위험한가? `restype`을 지정하지 않았을 때 어떤 값이 나올지 예측한 뒤, 실제로 실행해서 확인하라.

   ```python
   import ctypes
   msvcrt = ctypes.CDLL("msvcrt")
   msvcrt.malloc.argtypes = [ctypes.c_size_t]
   p = msvcrt.malloc(1024)
   print(p)
   ```

2. `time.sleep` 실험을 스레드 수를 4개에서 8개로 늘려 다시 재보라. 스레드 버전의 총 시간이 여전히 `DUR` 근처에 머무는가, 아니면 늘어나는가? 왜 그런지 설명하라.

3. `ctypes.Structure`로 3차원 벡터 `Vec3`(`x`, `y`, `z`, 모두 `c_double`)을 정의하고 `ctypes.sizeof(Vec3)`가 몇 바이트인지 예측한 뒤 확인하라.

4. `qsort` 콜백 예제에서, 비교 함수를 `a[0] - b[0]` 대신 내림차순으로 정렬하도록 바꿔라. 배열이 어떻게 바뀌는지 확인하라.

5. **생각해 볼 문제.** `Py_BEGIN_ALLOW_THREADS` 구간 안에서 실수로 파이썬 객체의 참조 카운트를 건드리는 C API 함수를 호출하면 어떤 일이 일어날 수 있을까? [5.2 메모리 모델](#/memory)의 참조 카운팅 내용을 근거로 추론해 보라.
:::

**다음 절**: [5.5 Cython, Numba, mypyc](#/compilers) — 파이썬과 비슷한 문법으로 짜서 실제로 컴파일해 본 뒤, 배수 단위 실측 비교로 언제 무엇을 쓸지 정한다.
