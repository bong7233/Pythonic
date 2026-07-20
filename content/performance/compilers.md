# 5.5 Cython, Numba, mypyc

::: lead
[5.1 측정 없이 최적화 없다](#/profiling)에서 병목을 찾았고, [5.3 파이썬 레벨 최적화](#/py-optimize)로 짤 수 있는 만큼 짰다. 그런데도 느리다면 남은 선택지는 하나다. **그 함수를 파이썬 바깥에서 실행되게 만드는 것.** 이 절은 그 일을 하는 세 가지 도구 — Cython, Numba, mypyc — 를 실제로 컴파일하고 실측해서 비교한다. 셋은 이름이 비슷해 보이지만 겨냥하는 지점이 완전히 다르다. 그 차이를 모르고 고르면 엉뚱한 도구에 시간을 버린다.
:::

## 세 도구는 같은 문제를 풀지 않는다

"파이썬을 컴파일해서 빠르게 만든다"는 한 문장으로 셋을 뭉뚱그리면 안 된다. 실제로는 서로 다른 지점을 공략한다.

```text nolines
   순수 파이썬 함수
        │
        ├── Cython ──▶ C에 가까운 "별도 언어"로 다시 쓴다
        │              (cdef 타입, 포인터, malloc까지 손이 닿는다)
        │
        ├── Numba ───▶ 데코레이터 하나로 LLVM이 그 자리에서 기계어를 만든다
        │              (수치 반복문 전용, 넘파이 배열이 주 무대)
        │
        └── mypyc ───▶ 이미 있는 타입 힌트를 그대로 읽어 컴파일한다
                       (코드를 고치지 않는다, 파이썬 의미론을 그대로 유지한다)
```

| | Cython | Numba | mypyc |
| --- | --- | --- | --- |
| 정체 | C의 상위집합인 **별도 언어** | 함수 단위 **JIT 컴파일러** | **AOT 컴파일러** (mypy 기반) |
| 입력 | `.pyx` 파일 (파이썬 문법 + `cdef`) | 데코레이터 붙은 일반 파이썬 함수 | 타입 힌트가 있는 일반 `.py` |
| 코드 수정 | 많이 필요 (타입 선언을 추가해야 효과가 크다) | 거의 없음 (데코레이터 한 줄) | 없음 (타입 힌트만 있으면 됨) |
| 잘하는 일 | 수치 루프, C 라이브러리 래핑, 세밀한 메모리 제어 | 수치 루프, 넘파이 배열 연산 | 객체·문자열이 섞인 일반 코드 전체 |
| 컴파일 시점 | 빌드 시 (C 컴파일러 필요) | **런타임 첫 호출 시** (또는 `cache=True`로 캐싱) | 빌드 시 (C 컴파일러 필요) |
| 파이썬 객체 다루기 | 가능 (느림, `cdef` 안 쓴 부분은 그대로 파이썬) | 제한적 (지원 안 되는 연산은 예외) | 완전 지원 (파이썬 의미론 그대로) |

이 표의 각 줄을 실측으로 확인한다.

## 측정 대상: 왜 이 함수가 느린가

세 도구를 공정하게 비교하려면 같은 함수를 써야 한다. 소수 판별 함수를 쓴다 — 순수한 수치 반복문이라 세 도구 모두의 강점이 드러난다.

```python title="pure.py — 기준선"
def count_primes(n: int) -> int:
    count = 0
    for i in range(2, n):
        is_prime = True
        j = 2
        while j * j <= i:
            if i % j == 0:
                is_prime = False
                break
            j += 1
        if is_prime:
            count += 1
    return count
```

이 함수가 왜 느린지는 이미 알고 있는 지식으로 설명된다. [3.7 바이트코드](#/bytecode)에서 본 대로 직접 들여다보자.

```pyrepl
>>> import dis
>>> dis.dis(count_primes)
  6   L2:     LOAD_FAST_BORROW_LOAD_FAST_BORROW 68 (j, j)
              BINARY_OP                5 (*)
              LOAD_FAST_BORROW         2 (i)
              COMPARE_OP              58 (bool(<=))
              POP_JUMP_IF_FALSE       28 (to L4)
              NOT_TAKEN

  7           LOAD_FAST_BORROW_LOAD_FAST_BORROW 36 (i, j)
              BINARY_OP                6 (%)
              LOAD_SMALL_INT           0
              COMPARE_OP              88 (bool(==))
```

(Python 3.14.5 실측. 3.11+ 특수화 인터프리터가 `BINARY_OP` 를 캐싱해 int 전용 빠른 경로로 재작성하지만, 여전히 **매 연산마다 타입을 확인하고 분기**한다.)

`j * j` 한 번을 계산하려고 C라면 기계어 `imul` 명령 하나로 끝날 일을, 파이썬은 `j` 가 정말 int인지 확인하고, `int.__mul__` 을 찾고, 결과로 새 int 객체를 힙에 만들고([1.2 숫자](#/numbers) — 파이썬 int는 임의 정밀도라 C의 `long` 과 표현 자체가 다르다), 참조 카운트를 조정한다([1.1 객체와 참조](#/objects-names)). 이 오버헤드가 반복문 안에서 수백만 번 반복된다. 세 도구가 없애려는 게 정확히 이 오버헤드다.

## Cython — 파이썬 문법을 한 C 언어

Cython은 `.pyx` 파일을 C 코드로 변환한 뒤, 그 C 코드를 **일반 C 컴파일러로 컴파일**해서 파이썬이 import할 수 있는 확장 모듈(`.pyd`/`.so`)을 만든다. 핵심 기능은 `cdef` — 변수에 **C 타입**을 선언하는 것이다.

```python title="cy_prime.pyx — 두 버전"
# 버전 1: 타입 선언 없음 (그냥 .pyx로 옮겨 컴파일만 함)
def count_primes_cy_untyped(n):
    count = 0
    for i in range(2, n):
        is_prime = True
        j = 2
        while j * j <= i:
            if i % j == 0:
                is_prime = False
                break
            j += 1
        if is_prime:
            count += 1
    return count


# 버전 2: cdef로 C 타입 선언
def count_primes_cy_typed(long n):
    cdef long count = 0
    cdef long i, j
    cdef bint is_prime
    for i in range(2, n):
        is_prime = True
        j = 2
        while j * j <= i:
            if i % j == 0:
                is_prime = False
                break
            j += 1
        if is_prime:
            count += 1
    return count
```

빌드는 `setup.py` 로 한다.

```python title="setup.py"
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("cy_prime.pyx", compiler_directives={"language_level": "3"}),
)
```

```bash
python setup.py build_ext --inplace
```

(Windows에서는 MSVC 빌드 도구 환경(`vcvars64.bat`)을 먼저 활성화해야 `cl.exe` 를 찾는다. Linux/Mac은 `gcc`/`clang` 이 있으면 바로 된다.)

::: perf 실측 — 타입 선언의 유무가 전부를 가른다
$n = 200{,}000$ 이하 소수 개수를 세는 벤치마크. `timeit.repeat(number=1, repeat=5)` 의 최솟값을 썼다.

| 버전 | 시간 | 배수 |
| --- | --- | --- |
| pure python | 208.808 ms | ×1.00 |
| Cython (타입 선언 없음) | 123.545 ms | ×1.69 |
| Cython (`cdef long`) | 9.148 ms | ×22.83 |

(Python 3.14.5 / Windows, MSVC 빌드. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다. 208.808 ms는 `repeat=5` 배치를 여러 번 돌려서 나온 최솟값이다 — 배치 한 번만 돌리면 백그라운드 스케줄링 잡음 때문에 209~222 ms 사이를 오갈 수 있으니, 진짜 최소치를 보려면 배치를 여러 번 반복하고 그 전체의 최솟값을 취해라.)

**타입을 선언하지 않은 Cython은 겨우 1.7배다.** `.pyx` 로 옮겨 컴파일만 해도 함수 호출 오버헤드 일부는 줄어들지만, 내부 연산은 여전히 파이썬 객체(`PyLongObject`)를 만들고 `PyNumber_Multiply` 같은 C API를 거친다. **`cdef long` 로 타입을 선언한 순간** `j * j` 는 진짜 C의 `long` 곱셈이 되고, 이때 22배가 나온다. Cython의 속도는 코드를 옮긴 데서 오는 게 아니라 **타입을 선언한 데서** 온다.
:::

::: tip 컴파일된 C 코드를 직접 봐라
`cython -a cy_prime.pyx` 를 실행하면 HTML 어노테이션이 나온다. 노란 줄일수록 파이썬 C API 호출이 많이 남아 있다는 뜻이다. `cdef` 를 하나씩 추가하면서 노란 줄이 흰 줄로 바뀌는 걸 눈으로 확인하는 게 Cython 최적화의 실전 워크플로다.
:::

## Numba — 데코레이터가 곧 컴파일러

Numba는 코드를 다시 쓸 필요가 없다. `@njit` 데코레이터를 붙이면, **함수가 처음 호출되는 순간** 인자의 타입을 보고 LLVM으로 기계어를 생성한다.

```python title="numba_prime.py"
from numba import njit


@njit(cache=True)
def count_primes_nb(n):
    count = 0
    for i in range(2, n):
        is_prime = True
        j = 2
        while j * j <= i:
            if i % j == 0:
                is_prime = False
                break
            j += 1
        if is_prime:
            count += 1
    return count
```

C 컴파일러가 필요 없다 — Numba는 LLVM을 라이브러리로 내장하고 있다. 그래서 설치만 하면 바로 동작한다.

::: perf 실측 — 첫 호출은 느리다, 그다음은 빠르다
같은 $n=200{,}000$ 기준.

```pyrepl
>>> count_primes_nb(200_000)   # 첫 호출: 컴파일 포함
197.2 ms
>>> count_primes_nb(200_000)   # 두 번째부터: 캐시된 기계어 실행
8.7 ms
```

(Python 3.14.5, `uvx --with numba` 환경 실측. `timeit.repeat(number=1, repeat=5)` 최솟값.)

| 버전 | 시간 | 배수 (pure python 대비) |
| --- | --- | --- |
| Numba 첫 호출 (컴파일 포함) | 197.206 ms | ×1.06 |
| Numba (워밍업 후) | 8.726 ms | ×23.93 |

**컴파일된 뒤의 속도는 Cython의 `cdef` 버전과 거의 같다** — 둘 다 결국 LLVM/C 컴파일러가 만든 기계어이기 때문이다. 하지만 **첫 호출 비용을 무시하면 안 된다.** 짧게 한 번 실행하고 끝나는 스크립트나, 매번 새 프로세스로 뜨는 서버리스 함수에서는 이 197ms가 실제 체감 성능이다. `cache=True` 를 주면 컴파일 결과를 디스크에 캐싱해서 다음 프로세스 실행부터는 이 비용을 건너뛴다.
:::

::: warn Numba는 아무 파이썬 코드나 받지 않는다
Numba의 nopython 모드(`@njit`)는 지원하는 타입과 연산의 부분집합 안에서만 동작한다. 정수·실수·넘파이 배열·간단한 반복문은 잘 되지만, 딕셔너리에 임의 객체를 넣거나, 문자열을 복잡하게 조작하거나, 서드파티 클래스를 쓰면 컴파일이 실패하거나 `object mode`(느린 대체 경로)로 떨어진다. **Numba는 수치 계산 전용 도구다.** 일반 애플리케이션 코드에는 맞지 않는다.
:::

## mypyc — 있던 타입 힌트를 그대로 쓴다

mypyc는 접근이 다르다. **파이썬 코드를 고치지 않는다.** [Part II 타입 시스템](#/why-typing)에서 이미 붙여 둔 타입 힌트를 mypy가 읽고, 그 정보를 이용해 C 코드를 생성한다.

```python title="mypyc_prime.py — 일반 타입 힌트 파이썬"
def count_primes_mypyc(n: int) -> int:
    count: int = 0
    for i in range(2, n):
        is_prime: bool = True
        j: int = 2
        while j * j <= i:
            if i % j == 0:
                is_prime = False
                break
            j += 1
        if is_prime:
            count += 1
    return count
```

이건 Cython 코드가 아니다. **평범한 파이썬 문법**이다. 타입 힌트를 지우고 그냥 실행해도 똑같이 동작한다. 컴파일만 다르게 한다.

```bash
mypyc mypyc_prime.py
```

::: perf 실측 — Cython/Numba보다 조금 느리지만 코드 변경이 0이다
| 버전 | 시간 | 배수 |
| --- | --- | --- |
| pure python | 208.808 ms | ×1.00 |
| mypyc | 11.481 ms | ×18.19 |

(Python 3.14.5 / Windows, MSVC 빌드. `timeit.repeat(number=1, repeat=5)` 최솟값.)

Cython의 `cdef long` 버전(×22.83)이나 Numba(×23.93)보다는 느리다. 이유는 mypyc가 **파이썬 의미론을 100% 지키기 때문이다.** `n: int` 는 여전히 임의 정밀도 파이썬 int일 수 있으므로(작은 값은 내부적으로 unboxed C 정수로 최적화하지만, 오버플로 가능성을 늘 확인해야 한다), Cython의 `cdef long` 처럼 오버플로를 무시하고 진짜 C `long` 으로만 다루는 것보다는 확인 비용이 남는다. 그래도 **코드를 한 글자도 안 고치고 18배**를 얻었다는 게 mypyc의 존재 이유다.
:::

::: note mypyc는 이미 mypy strict 모드를 통과한 코드에 가장 잘 듣는다
타입 힌트가 허술하면(`Any` 투성이) mypyc가 만드는 코드도 파이썬 객체를 그대로 다루는 느린 경로로 떨어진다. mypyc의 속도는 **타입 힌트의 정확도에 비례한다.** [2.8 mypy와 pyright 실전](#/typecheckers)에서 strict 모드를 켜 둔 코드베이스일수록 mypyc 도입 비용이 낮다.
:::

## 세 도구를 한 표에

지금까지의 실측을 모으면 이렇다.

| 도구 | 워밍업 후 배수 | 코드 수정량 | 컴파일 시점 |
| --- | --- | --- | --- |
| Cython (`cdef` 없이) | ×1.69 | 거의 없음 | 빌드 시 |
| mypyc | ×18.19 | 없음 (기존 타입 힌트) | 빌드 시 |
| Numba (`@njit`) | ×23.93 | 데코레이터 한 줄 | 첫 호출 시 |
| Cython (`cdef` 사용) | ×22.83 | 많음 (타입 선언) | 빌드 시 |

**끝점의 속도는 셋이 비슷하다.** 결국 다 기계어로 내려가기 때문이다. 차이는 **거기 도달하는 데 얼마나 코드를 고쳐야 하는가**, 그리고 **어떤 종류의 코드에 적용할 수 있는가**다.

## 언제 무엇을 쓰는가

::: cote 판단 기준표
| 상황 | 선택 |
| --- | --- |
| 넘파이 배열 위에서 순수 수치 반복문 (물리 시뮬레이션, 이미지 필터, 거리 계산) | **Numba** — 데코레이터 한 줄, 프로토타이핑이 가장 빠르다 |
| C/C++ 라이브러리를 파이썬에서 감싸야 함 | **Cython** — C API를 직접 호출할 수 있는 유일한 선택지 |
| 배열 크기가 매번 바뀌거나, 서버리스처럼 프로세스가 짧게 사는 환경 | **Cython** 또는 **mypyc** — 빌드 시 컴파일이라 첫 호출 지연이 없다 |
| 이미 타입 힌트가 잘 된 큰 코드베이스 전체를 조금씩 빠르게 하고 싶다 | **mypyc** — 코드를 고치지 않고 빌드 스텝만 추가한다 |
| 문자열·딕셔너리·클래스가 뒤섞인 일반 애플리케이션 로직 | **mypyc** — Numba는 애초에 지원하지 않는다 |
| 세밀한 메모리 레이아웃 제어, `nogil` 로 GIL을 실제로 놓아야 함 | **Cython** — `with nogil:` 블록을 직접 쓸 수 있다. [4.3 GIL](#/gil) |
:::

::: hist 왜 셋 다 살아남았는가
세 도구는 경쟁 관계가 아니라 **다른 문제를 풀도록 태어났다.** Cython(2007년, Pyrex의 후속)은 애초에 "C 확장을 파이썬 문법으로 쉽게 쓰자"는 목표였고, 지금도 CPython 자체나 여러 과학 계산 라이브러리의 C 바인딩 레이어로 쓰인다. Numba(2012년)는 NumPy 생태계에서 "루프를 벡터화하기 번거로운 계산을 그냥 루프로 짜고 빠르게 만들자"는 요구에서 나왔다 — LLVM이 성숙해지면서 가능해진 접근이다. mypyc(2019년, mypy 프로젝트의 부산물)는 애초에 **mypy 자신을 빠르게 만들려고** 만들어졌다. mypy 컴파일러 자체가 mypyc로 컴파일된다. 세 도구가 겨냥한 문제가 다르다 보니 지금도 각자의 자리에서 쓰인다.
:::

## 공통된 트레이드오프: 복잡도는 공짜가 아니다

셋 다 속도를 얻는 대신 뭔가를 지불한다.

- **배포가 복잡해진다.** 순수 파이썬은 `.py` 파일만 옮기면 어디서나 돈다. Cython과 mypyc는 **플랫폼별로 컴파일된 바이너리**(`.pyd`/`.so`)가 필요하다. Linux에서 빌드한 `.so` 는 Windows에서 못 쓴다. CI에서 각 플랫폼용 wheel을 따로 빌드해야 한다. [6.5 패키징](#/packaging)에서 이 문제를 자세히 다룬다.
- **의존성이 늘어난다.** Cython/mypyc는 빌드 시점에 C 컴파일러(MSVC, gcc, clang)가 있어야 한다. Numba는 LLVM을 통째로 끌고 들어온다 — `pip install numba` 한 번에 수십 MB가 딸려 온다.
- **디버깅이 어려워진다.** 파이썬 트레이스백은 이제 C 프레임과 섞인다. Cython은 `# distutils: language=c` 같은 지시어와 `.pyx` 소스가 최종 에러 메시지 사이에 한 겹 더 낀다. `pdb` 로 한 줄씩 따라가던 습관이 통하지 않는다.
- **빌드 스텝이 하나 늘어난다.** `pip install` 만으로 끝나던 것이 `setup.py build_ext` 나 `mypyc` 커맨드를 CI 파이프라인에 넣어야 하는 일이 된다.

::: danger 마이크로 최적화에 낚이지 마라
이 절에서 본 20배는 인상적이다. 하지만 **20배 빨라진 함수가 전체 프로그램 실행 시간의 3%를 차지한다면, 체감 개선은 3% 근처다.** [5.1 측정 없이 최적화 없다](#/profiling)에서 프로파일러로 실제 병목을 찾지 않고 "여기가 느릴 것 같다"는 감으로 아무 함수나 Cython으로 옮기는 건 시간 낭비다. 게다가 컴파일된 코드는 배포·디버깅 비용이 늘어난다는 걸 방금 봤다. **먼저 측정해서 진짜 병목을 찾고, 그 병목이 이 절에서 다룬 순수 수치 반복문 형태일 때만** 이 도구들을 꺼내라. 대부분의 파이썬 프로그램은 I/O를 기다리거나(→ [Part IV 동시성](#/concurrency-map)) 이미 C로 구현된 라이브러리 호출(NumPy, pandas)에 시간을 쓴다. 그런 코드는 Cython으로 옮겨도 안 빨라진다 — 애초에 병목이 파이썬 인터프리터가 아니기 때문이다.
:::

## 요약

- Cython, Numba, mypyc는 경쟁 도구가 아니라 **서로 다른 문제를 겨냥한다.**
- **Cython**은 C에 가까운 별도 언어다. `cdef` 로 타입을 선언해야 진짜 속도(실측 ×22.83)가 나온다. 타입 선언 없이 옮기기만 하면 겨우 ×1.69다.
- **Numba**는 `@njit` 데코레이터 하나로 수치 반복문을 LLVM 기계어로 만든다(실측 워밍업 후 ×23.93). 첫 호출은 컴파일 때문에 오히려 느리다(실측 197ms). 파이썬 객체 전반을 지원하지 않는다 — 수치 계산 전용.
- **mypyc**는 이미 있는 타입 힌트로, 코드를 한 글자도 안 고치고 컴파일한다(실측 ×18.19). 파이썬 의미론을 그대로 지키느라 끝점 속도는 조금 낮지만, 도입 비용이 가장 낮다.
- 셋 다 컴파일된 뒤의 최고 속도는 비슷하다 — 결국 기계어로 내려가기 때문이다. 차이는 **어떤 코드에 적용 가능한가**와 **얼마나 고쳐야 하는가**다.
- 셋 다 배포·의존성·디버깅 복잡도를 늘린다. **공짜 점심은 없다.**
- 컴파일 도구를 꺼내기 전에 반드시 프로파일러로 진짜 병목인지 확인하라. 아니면 시간 낭비다.

::: quiz 연습문제
1. 이 절의 `count_primes` 함수를 Cython으로 옮기되, `j`, `i` 는 `cdef long` 으로 선언하고 `count` 는 선언하지 않은 채로 컴파일해서 실행해 보라. `count` 하나만 타입을 빼먹어도 속도가 크게 떨어지는지 확인하라.

2. `@njit` 을 붙인 Numba 함수에 파이썬 리스트(`list[int]`)를 인자로 넘기면 어떻게 되는가? 넘파이 배열을 넘겼을 때와 비교해 보라. (직접 실행해서 확인하라.)

3. mypyc로 컴파일한 함수에서 타입 힌트를 일부러 `Any` 로 바꾸고 다시 컴파일하면 속도가 어떻게 바뀌는가? 예측한 뒤 실측하라.

4. 다음 셋 중 Numba를 쓰기에 가장 부적합한 것은? 이유를 설명하라.
   - (a) 100만 개의 좌표 쌍 사이 유클리드 거리를 모두 계산하는 함수
   - (b) 딕셔너리에 담긴 사용자 레코드를 파싱해 문자열 필드를 정규화하는 함수
   - (c) 몬테카를로 방식으로 원주율을 추정하는 반복문

5. 어떤 함수가 프로파일러 결과 전체 실행 시간의 1%를 차지한다. 이 함수를 Cython으로 컴파일해 20배 빠르게 만들면 전체 프로그램은 몇 % 빨라지는가? 이 계산이 왜 "측정 없이 최적화하지 마라"의 핵심 근거인지 설명하라.
:::

**다음 절**: [5.6 Rust 확장 (PyO3) 맛보기](#/pyo3) — maturin으로 만드는 고성능 모듈, 그리고 이 환경에서 실제로 무엇이 되고 무엇이 안 됐는지.
