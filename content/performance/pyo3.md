# 5.6 Rust 확장 (PyO3) 맛보기

::: lead
[5.5 Cython, Numba, mypyc](#/compilers)까지 왔다면 이런 질문이 남는다. "그런데 왜 굳이 Rust까지 가야 하나?" 답은 대부분의 경우 **갈 필요 없다**는 것이다. 하지만 복잡한 자료구조를 다루면서 세그멘테이션 폴트 없이 짜야 하거나, GIL을 놓고 진짜 병렬 계산을 시키면서도 메모리 안전성을 포기하고 싶지 않을 때는 이야기가 다르다. 이 절은 PyO3와 maturin으로 파이썬에서 부르는 Rust 함수를 실제로 만들고, 컴파일하고, 측정한다.
:::

## 이 환경에서 실제로 한 것

먼저 정직하게 밝힌다. 이 절의 모든 코드는 **실제로 컴파일하고 실행해서** 나온 결과다. `winget install Rustlang.Rustup` 으로 Rust 툴체인을 설치하는 데 성공했고([0.3 uv](#/uv)와 비슷하게, 새 도구를 설치하는 것도 결국 패키지 관리다), `rustc 1.97.1` / `cargo 1.97.1` / MSVC 백엔드(`x86_64-pc-windows-msvc`) 조합으로 실제 `.pyd` 파일까지 빌드했다. 아래 벤치마크 수치는 전부 그렇게 만든 확장 모듈을 직접 호출해서 잰 것이다(Windows / Python 3.14.5 / pyo3 0.29.0 / maturin 1.14.1 기준. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 비슷하다).

## 최소 예제 만들기

`maturin new -b pyo3` 는 이런 뼈대를 만든다.

```toml title="Cargo.toml"
[package]
name = "rustdemo"
version = "0.1.0"
edition = "2024"

[lib]
name = "rustdemo"
crate-type = ["cdylib"]

[dependencies]
pyo3 = "0.29.0"
```

`crate-type = ["cdylib"]` 이 핵심이다. 일반 Rust 라이브러리(`rlib`)가 아니라 **C 호환 동적 라이브러리**를 만들라는 뜻이다. [5.4 C 확장](#/c-ext)에서 본 `.pyd`/`.so` 와 정확히 같은 종류의 산출물이다 — CPython이 `import` 할 때 여는 것은 결국 이 파일이다.

```rust title="src/lib.rs — 소수 개수를 세는 함수"
use pyo3::prelude::*;

#[pymodule]
mod rustdemo {
    use pyo3::prelude::*;

    /// n 이하의 소수 개수를 센다 (에라토스테네스의 체).
    #[pyfunction]
    fn count_primes(n: usize) -> usize {
        if n < 2 {
            return 0;
        }
        let mut sieve = vec![true; n + 1];
        sieve[0] = false;
        sieve[1] = false;
        let mut i = 2;
        while i * i <= n {
            if sieve[i] {
                let mut j = i * i;
                while j <= n {
                    sieve[j] = false;
                    j += i;
                }
            }
            i += 1;
        }
        sieve.iter().filter(|&&is_prime| is_prime).count()
    }
}
```

`#[pymodule]` 는 이 모듈 전체를 파이썬 확장 모듈로 등록하고, `#[pyfunction]` 은 함수 하나를 파이썬에서 부를 수 있게 만든다. 타입은 자동 변환된다 — `usize` 는 파이썬 `int` 와, 반환값도 마찬가지로 서로 오간다. 이 변환 코드를 매크로가 생성해 준다는 게 Cython의 `cpdef` 와 개념적으로 같은 자리다. 다만 Cython은 파이썬 문법의 확장이고, PyO3는 **순수 Rust 코드에 매크로만 붙인 것**이라는 차이가 있다.

::: note pyo3 버전에 따라 문법이 바뀐다
0.29 기준으로 `#[pymodule]` 를 함수가 아니라 **모듈**(`mod rustdemo { ... }`)에 붙이는 새 문법이 기본이다. 예전 자료에는 `#[pymodule] fn rustdemo(_py: Python, m: &PyModule) -> PyResult<()> { ... }` 형태가 많이 나온다. 둘 다 동작하지만, PyO3는 마이너 버전 사이에도 API가 꽤 바뀌는 편이니 **공식 문서의 버전을 항상 확인하라.**
:::

## maturin develop 워크플로

`maturin` 은 Rust 크레이트를 파이썬 배포 가능한 wheel로 만들어 주는 빌드 백엔드다. `pyproject.toml` 에 이렇게 선언한다.

```toml title="pyproject.toml"
[build-system]
requires = ["maturin>=1.14,<2.0"]
build-backend = "maturin"
```

개발 중에는 매번 wheel을 만들고 설치하는 대신 이걸 쓴다.

```bash
uv venv .venv
uv pip install --python .venv maturin
maturin develop --release
```

`maturin develop` 이 하는 일은 세 단계다. (1) `cargo build --release` 로 네이티브 라이브러리를 컴파일하고, (2) 그 산출물의 이름을 `rustdemo.cp314-win_amd64.pyd` 형태로 바꿔서, (3) 지금 활성화된 가상환경의 `site-packages` 에 **직접 복사**한다(편집 가능 설치이므로 다시 빌드할 때마다 이 파일만 갱신된다). 실제로 이 환경에서 설치된 결과를 확인하면 이렇다.

```text nolines
.venv/Lib/site-packages/rustdemo/
├── __init__.py                    <- 115바이트, `from .rustdemo import *` 한 줄짜리 래퍼
├── rustdemo.cp314-win_amd64.pyd   <- 약 186.5 KB(190,976바이트), 실제 네이티브 코드
└── rustdemo.pdb
```

`__init__.py` 는 maturin이 `module-name` 설정에 맞춰 자동으로 만들어 주는 얇은 파이썬 래퍼다 — 실제 임포트되는 건 여전히 `.pyd` 안의 네이티브 심볼이고, 이 파일은 그걸 패키지처럼 보이게 다시 내보내는(re-export) 역할만 한다.

`import rustdemo` 는 이 `.pyd` 를 여는 것뿐이다. 파이썬 인터프리터 입장에서는 [5.4 C 확장](#/c-ext)에서 본 `ctypes`/C 확장과 구분이 안 된다 — CPython의 C API를 만족하는 동적 라이브러리이기만 하면 된다.

빌드 시간도 재봤다. `cargo` 빌드 로그를 그대로 옮기면 이렇다. 의존성 크레이트 13개(`target-lexicon`, `proc-macro2`, `unicode-ident`, `quote`, `libc`, `heck`, `once_cell`, `pyo3-build-config`, `syn`, `pyo3-ffi`, `pyo3`, `pyo3-macros-backend`, `pyo3-macros`)를 전부 새로 받아 컴파일한 뒤 `rustdemo` 자신을 컴파일하는 **최초 빌드는 8.79초**였고, 코드 한 줄만 고친 뒤의 **증분 빌드는 0.4초 이하**였다. Cython의 `setup.py build_ext` 보다 초기 비용은 크지만(의존성 컴파일이 있으니까), 이후로는 비슷한 속도다.

::: cote 실전에서 이걸 코딩테스트에 쓸 일은 거의 없다
이 절의 내용은 코딩테스트보다는 **실무에서 진짜 성능이 필요한 라이브러리를 만들 때**를 겨냥한다. 시험장에서 Rust 툴체인을 설치할 시간은 없다. [8장](#/cote-strategy)에서 쓰는 최적화는 여전히 [7.2 자료구조 비용](#/py-ds-cost)과 알고리즘 선택이다.
:::

## 실측: 얼마나 빨라지는가

에라토스테네스의 체로 200만 이하의 소수 개수를 세는 순수 파이썬 함수와 위 Rust 함수를 그대로 비교했다.

```python title="bench.py"
import timeit
import rustdemo


def count_primes_py(n):
    if n < 2:
        return 0
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    i = 2
    while i * i <= n:
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
        i += 1
    return sum(sieve)


N = 2_000_000
t_py = timeit.timeit(lambda: count_primes_py(N), number=5) / 5
t_rs = timeit.timeit(lambda: rustdemo.count_primes(N), number=5) / 5
print(f"pure python: {t_py:.4f}s, pyo3: {t_rs:.4f}s, 배율: {t_py/t_rs:.1f}배")
```

```text nolines
pure python : 0.0499s
pyo3(rust)  : 0.0015s
배율        : 32.5배
```

32.5배는 [5.5 Cython/Numba](#/compilers)에서 나온 배율과 같은 자릿수다. 당연하다 — 병목의 정체가 같기 때문이다. 순수 파이썬 루프의 매 반복마다 [1.1 객체 모델](#/objects-names)에서 다룬 **박싱된 `PyObject`** 를 만들고 참조 카운트를 건드리고 [3.7 바이트코드](#/bytecode)의 인터프리터 디스패치 루프를 도는 비용이 든다. Rust는 이 전부를 건너뛰고 스택에 놓인 네이티브 `bool` 배열을 직접 만진다. **Rust 자체가 Cython/Numba보다 유의미하게 더 빠른 게 아니다.** 셋 다 "파이썬 인터프리터 오버헤드를 없앤다"는 같은 트릭을 쓸 뿐이다.

::: perf 이 32.5배가 실제로 의미 있으려면
이 함수 하나를 초당 수백만 번 호출하는 게 아니라면, 200만 소수 세기가 0.05초 걸리는 것과 0.0015초 걸리는 것의 차이는 **체감되지 않는다.** 마이크로 최적화에 매달리기 전에 먼저 [5.1 프로파일링](#/profiling)으로 이 함수가 실제 병목인지부터 확인하라. 프로그램 전체 시간의 1%를 차지하는 함수를 32배 빠르게 만들어 봐야 전체는 0.99배가 될 뿐이다.
:::

## GIL을 놓는다는 것 — `Python::detach`

여기서부터가 Cython/Numba의 `nogil` 과 개념적으로 이어지는 지점이다. [4.3 GIL](#/gil)에서 봤듯, 순수 파이썬 스레드는 CPU 바운드 작업에서 서로를 기다리기만 한다. PyO3는 파이썬 객체를 건드리지 않는 구간에서 명시적으로 GIL을 놓을 수 있게 해 준다.

```rust title="GIL을 놓고 실행하는 함수"
#[pyfunction]
fn count_primes_nogil(py: Python<'_>, n: usize) -> usize {
    py.detach(|| {
        // 이 클로저 안에서는 GIL이 없다.
        // 파이썬 객체를 만들거나 만지면 안 된다 — 컴파일러가 대부분 막아 준다.
        if n < 2 {
            return 0;
        }
        let mut sieve = vec![true; n + 1];
        sieve[0] = false;
        sieve[1] = false;
        let mut i = 2;
        while i * i <= n {
            if sieve[i] {
                let mut j = i * i;
                while j <= n {
                    sieve[j] = false;
                    j += i;
                }
            }
            i += 1;
        }
        sieve.iter().filter(|&&is_prime| is_prime).count()
    })
}
```

::: note 이름이 바뀌었다
PyO3 문서와 대부분의 예제 코드에는 이 메서드가 `Python::allow_threads` 로 나온다. 이 절에서 실제로 컴파일에 쓴 **pyo3 0.29.0에서는 `Python::detach` 로 이름이 바뀌었다**(`allow_threads` 로 쓰면 컴파일 에러가 난다 — 실제로 겪었다). 의미는 같다. "GIL을 놓고 클로저를 실행한 뒤 돌려받는다."
:::

이제 스레드 4개로 같은 함수를 동시에 부르면 어떻게 될까? 직관적으로는 "GIL을 놓았으니 코어 4개를 다 쓰겠지"라고 기대하기 쉽다. **실제로 재 보면 그렇지 않았다.**

```python title="스레드 4개로 count_primes_nogil 호출 (N = 6천만)"
# 단일 호출: 0.0912초
# 스레드 1개: 0.0915초
# 스레드 2개: 0.1645초
# 스레드 4개: 0.3783초
# 스레드 8개: 0.9076초
```

이건 완전한 실패다 — 스레드가 늘수록 시간이 **정확히 스레드 개수만큼 비례해서 늘어난다.** 원인은 GIL이 아니다. `vec![true; n + 1]` 에서 `n = 60,000,000` 이면 스레드마다 매번 **60MB짜리 배열을 새로 할당하고 0으로 채운다.** 4개 스레드가 동시에 이걸 하면 힙 할당자와 메모리 대역폭에서 경합이 생겨 사실상 직렬화된다. **GIL을 놓았다고 병렬성이 저절로 생기지 않는다.** 다른 병목(이 경우 메모리 할당)이 기다리고 있었을 뿐이다.

이걸 확인하려고 할당이 없는 버전을 따로 만들었다.

```rust title="할당 없이 순수 연산만 하는 버전"
#[pyfunction]
fn collatz_sum_nogil(py: Python<'_>, limit: u64) -> u64 {
    py.detach(|| {
        let mut total: u64 = 0;
        for start in 1..=limit {
            let mut n = start;
            while n != 1 {
                n = if n % 2 == 0 { n / 2 } else { 3 * n + 1 };
                total += 1;
            }
        }
        total
    })
}
```

```text nolines
콜라츠 수열 총 길이 합 (limit = 3,000,000), 힙 할당 없음
스레드 1개: 0.2640초
스레드 2개: 0.2620초
스레드 4개: 0.2712초
스레드 8개: 0.2792초
```

이번엔 스레드가 몇 개든 **벽시계 시간이 거의 그대로다.** 8개 스레드가 각자 독립된 코어에서 진짜로 동시에 도는 것이다(이 기기는 논리 코어 16개). 두 결과를 나란히 놓으면 결론이 분명해진다. **GIL을 놓는 것은 병렬성의 필요조건이지 충분조건이 아니다.** 공유 자원(힙 할당자, 캐시, 메모리 대역폭, 락)이 남아 있으면 그게 새 병목이 된다. [4.4 multiprocessing](#/multiprocessing)에서 프로세스 간 통신 비용을 다루는 것과 같은 종류의 교훈이다 — 병렬화는 공짜가 아니라 병목을 옮기는 작업이다.

::: danger 참고: 파이썬 스레드는 원래 이 작업에서 이득이 없다
같은 소수 세기를 순수 파이썬 함수로, 스레드 4개로 돌리면 벽시계 시간이 **단일 스레드의 정확히 4배**가 나온다(실측: 단일 0.0396초, 4스레드 0.1570초). GIL이 스레드를 정직하게 순서대로 돌리기 때문이다. `count_primes` 를 GIL을 놓지 않은 채로 스레드 4개로 부르면 이것과 똑같이 동작한다 — Rust로 짰다고 자동으로 병렬이 되는 게 아니라, **명시적으로 GIL을 놓아야만** 병렬화의 가능성이 열린다.
:::

## 패닉은 파이썬 예외가 된다

Rust 코드가 `unsafe` 없이 짜여 있어도 배열 범위를 벗어나면 **패닉**(panic)이 난다. C였다면 이 자리에서 미정의 동작이나 세그폴트가 났을 것이다. PyO3는 FFI 경계에서 패닉을 가로채 파이썬 예외로 바꿔 준다. 직접 확인했다.

```rust title="일부러 패닉을 내는 함수"
#[pyfunction]
fn boom(idx: usize) -> i64 {
    let v = vec![1, 2, 3];
    v[idx] // idx >= 3 이면 범위 초과
}
```

```pyrepl
>>> import rustdemo
>>> rustdemo.boom(10)
Traceback (most recent call last):
  ...
pyo3_runtime.PanicException: index out of bounds: the len is 3 but the index is 10
```

프로세스가 죽지 않고 **`pyo3_runtime.PanicException`** 이라는 평범한 파이썬 예외로 잡힌다. 이게 "Rust는 메모리 안전성이 중요할 때 쓴다"는 말의 실제 의미다. C 확장이었다면 같은 실수가 세그폴트나 힙 손상으로 이어져 파이썬 프로세스 전체가 죽었을 것이다. Rust는 `unsafe` 를 쓰지 않는 한 배열 범위·널 포인터·해제 후 사용(use-after-free) 같은 클래스의 버그를 **컴파일 타임이나 런타임 패닉**으로 바꿔 준다. 죽더라도 "예외" 로 죽지 "프로세스 전체 다운"으로 죽지 않는다는 게 차이다.

## 언제 여기까지 와야 하는가

[5.5 Cython/Numba](#/compilers)로 충분한 경우가 압도적으로 많다. Rust/PyO3를 진지하게 고려할 신호는 이렇다.

- **복잡하고 소유권이 얽힌 자료구조를 다룬다.** 그래프, 트리, 링크드 리스트처럼 포인터가 서로를 참조하는 구조를 C 스타일로 짜면 버그가 나기 쉽다. Rust의 borrow checker는 이런 구조에서 흔한 실수(댕글링 포인터, 이중 해제)를 컴파일 타임에 잡아낸다. Cython은 결국 C 수준의 메모리 관리로 내려가므로 이런 안전성이 없다.
- **GIL을 놓고 병렬로 돌리면서도 데이터 경쟁을 컴파일러가 막아 주길 원한다.** 위에서 봤듯 GIL을 놓는 것 자체는 Cython(`nogil` 블록)도 할 수 있다. 차이는 Rust는 **여러 스레드가 같은 데이터를 안전하지 않게 공유하면 애초에 컴파일이 안 된다**(`Send`/`Sync` 트레잇 검사). Cython/C는 그 책임을 온전히 개발자에게 맡긴다.
- **파이썬 바깥에서도 재사용할 라이브러리를 만든다.** Rust 크레이트는 그 자체로 독립된 라이브러리라서, PyO3 바인딩을 걷어내면 다른 언어에서도 그대로 쓸 수 있다. Cython 코드는 파이썬 생태계에 묶인다.
- **팀에 이미 Rust 역량이 있거나, 장기적으로 유지보수할 네이티브 코드베이스를 만든다.** 러닝 커브가 있는 도구는 그걸 계속 쓸 사람이 있을 때 정당화된다.

반대로 **과한 경우**는 이렇다.

- 벡터화 가능한 수치 계산이면 NumPy나 Numba로 끝난다. 굳이 소유권 문제를 겪을 이유가 없다.
- 파이썬 코드에 타입만 붙이면 되는 정도의 최적화면 Cython이 학습 비용도 낮고 빌드도 단순하다.
- 팀에 Rust를 아는 사람이 없는데 이 코드를 유지보수해야 한다면, 성능 이득보다 유지보수 비용이 커질 수 있다.
- 애초에 [5.1 프로파일링](#/profiling)으로 병목을 확인하지 않은 상태에서 시작하는 모든 경우. 측정 없이 골라잡은 최적화 대상은 대개 틀린 곳이다.

::: hist 왜 Rust가 이 자리에 왔는가
2015년 전후로 파이썬 확장을 만드는 표준 경로는 CPython C API를 직접 쓰거나 Cython을 쓰는 것뿐이었다. 둘 다 메모리 관리 실수가 세그폴트로 직행했다. PyO3(2017년경 시작)는 "네이티브 속도는 그대로 가져가되, 메모리 안전성은 컴파일러가 보장하게 하자"는 제안이었다. maturin이 여기에 "빌드와 배포까지 표준 파이썬 패키징 도구(`pip install`, wheel)로 통합하자"를 더했다. NumPy, cryptography 같은 핵심 라이브러리들이 점점 C 확장을 Rust로 옮기는 것도 같은 이유다 — 성능은 유지하면서 버그 클래스 하나를 통째로 없앤다.
:::

## 요약

- PyO3 + maturin은 Rust로 짠 함수를 파이썬에서 그대로 부를 수 있게 해 준다. `#[pymodule]`/`#[pyfunction]` 매크로가 타입 변환 코드를 생성한다.
- `crate-type = ["cdylib"]` 로 만든 산출물은 [5.4 C 확장](#/c-ext)에서 본 `.pyd`/`.so` 와 같은 종류다. `maturin develop` 은 그걸 컴파일해서 가상환경 `site-packages` 에 바로 넣어 준다.
- 순수 파이썬 대비 속도 차이는 [5.5 Cython/Numba](#/compilers)와 같은 자릿수다(이 환경 실측 32.5배) — 셋 다 인터프리터 오버헤드를 없애는 같은 트릭이다. Rust 자체가 더 빠른 게 아니다.
- `Python::detach`(구 `allow_threads`)로 GIL을 놓을 수 있다. 단, **GIL을 놓는 것과 실제로 병렬 속도가 나는 것은 다른 문제다** — 이 환경에서 메모리 할당이 있는 함수는 스레드를 늘려도 전혀 빨라지지 않았고, 할당 없는 순수 연산 함수만 진짜 선형에 가깝게 병렬화됐다.
- Rust 패닉은 프로세스를 죽이지 않고 `pyo3_runtime.PanicException` 으로 파이썬에 전달된다.
- 복잡한 소유권 구조나 안전한 병렬성이 필요할 때만 여기까지 오라. 대부분의 성능 문제는 [5.1](#/profiling)–[5.5](#/compilers)에서 끝난다.

::: quiz 연습문제
1. `count_primes_nogil` 이 스레드 수에 비례해서 느려진 이유를 한 문장으로 설명하라. 이걸 고치려면(할당 횟수를 줄이려면) 함수 시그니처를 어떻게 바꿔야 할까?
2. `Python::detach` 클로저 안에서 파이썬 객체(`PyList` 등)를 만들려고 하면 왜 위험한가? PyO3가 이걸 컴파일 타임에 막아 주는 이유는 무엇인가?
3. 이 절의 `boom` 함수처럼 배열 범위를 넘는 인덱싱을 C 확장(`ctypes`)으로 했다면 어떤 일이 벌어질지 [5.4 C 확장](#/c-ext)의 내용을 바탕으로 설명하라.
4. 당신의 프로젝트에서 "Cython으로 충분한 문제"와 "Rust까지 가야 하는 문제"를 하나씩 예로 들어 보라. 판단 기준은 무엇이었나?
:::

**다음 절**: [6.1 pytest 완전 정복](#/pytest) — 측정하고 최적화한 코드가 계속 옳은지는 테스트가 보장한다.
