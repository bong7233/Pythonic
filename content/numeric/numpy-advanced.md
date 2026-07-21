# 9.3 NumPy 고급

::: lead
[9.1 ndarray](#/numpy-basics)에서 배열이 "뷰냐 복사냐"를 배웠다. 그런데 뷰가 어떻게 같은 메모리를 다른 모양으로 보여주는지, 그 아래에는 무엇이 있을까. 답은 **스트라이드**(strides)다. 이 절은 스트라이드를 직접 조작해서 뷰의 정체를 드러내고, 벡터화 연산의 실체인 **ufunc**이 왜 빠른지, `einsum` 이 왜 "항상" 빠르지는 않은지, 메모리를 어떤 순서로 늘어놓느냐가 왜 성능을 가르는지를 전부 실측으로 확인한다.
:::

## 스트라이드 — ndarray가 메모리를 읽는 규칙

`ndarray` 는 실제로는 아주 단순한 구조다. **연속된 메모리 덩어리 하나**와, 그것을 몇 차원으로 얼마나 건너뛰며 읽을지 정하는 **정수 몇 개**가 전부다. 그 정수들이 `strides` 다.

```pyrepl
>>> import numpy as np
>>> a = np.arange(12, dtype=np.int64)
>>> a.strides
(8,)
>>> b = a.reshape(3, 4)
>>> b.strides
(32, 8)
```

`int64` 원소 하나가 8바이트다. `b.strides == (32, 8)` 은 *"다음 행으로 가려면 32바이트(원소 4개), 다음 열로 가려면 8바이트(원소 1개) 건너뛰라"* 는 뜻이다. `b[i, j]` 를 읽는 계산은 사실 이거다.

```text nolines
주소 = data 시작 주소 + i * strides[0] + j * strides[1]
     = data 시작 주소 + i * 32       + j * 8
```

`reshape` 가 데이터를 옮기지 않고 뷰를 반환할 수 있는 이유가 여기 있다. `(12,)` 를 `(3, 4)` 로 바꾸는 건 데이터를 재배열하는 게 아니라, **이 스트라이드 규칙을 바꾸는 것**뿐이다. 메모리 덩어리는 그대로다.

### `as_strided` — 규칙을 손으로 조작한다

`numpy.lib.stride_tricks.as_strided` 는 `shape` 와 `strides` 를 직접 지정해서 뷰를 만드는 저수준 도구다. 흔한 용도는 슬라이딩 윈도우다.

```python title="슬라이딩 윈도우를 스트라이드로 만들기"
from numpy.lib.stride_tricks import as_strided

a = np.arange(12)
window = 3
n = a.size - window + 1
sw = as_strided(a, shape=(n, window), strides=(a.strides[0], a.strides[0]))
print(sw)
```

```text nolines
[[ 0  1  2]
 [ 1  2  3]
 [ 2  3  4]
 [ 3  4  5]
 ...
 [ 9 10 11]]
```

핵심은 **새 배열이 하나도 만들어지지 않았다**는 것이다. `sw` 는 `a` 의 12개 원소를 겹쳐서 10번 재사용하는 뷰다. 원소를 복사했다면 $O(n \times \text{window})$ 만큼 메모리가 들었겠지만, 이건 $O(n)$ 원본 그대로에 스트라이드 트릭만 얹은 것이다.

::: danger as_strided는 경계를 검사하지 않는다
`as_strided` 는 `shape` 와 `strides` 가 실제 메모리 범위 안에 있는지 **전혀 확인하지 않는다.** 잘못 지정하면 남의 메모리를 읽는다.

```python
a = np.arange(12)
danger = as_strided(a, shape=(20, 3), strides=(a.strides[0], a.strides[0]))
print(danger[15])
```

```text nolines
[-9223366536609934183 140734435588825 1397241784391696384]
```

`a` 는 원소 12개뿐인데 `shape=(20, 3)` 을 요구했다. 15번째 행부터는 `a` 의 메모리 뒤에 있는 **완전히 무관한 프로세스 메모리**를 정수로 읽어 온 것이다. 크래시가 안 나고 조용히 쓰레기 값을 돌려준다는 게 더 무섭다 — 인덱스 에러였다면 바로 알아챘을 텐데, 이건 "그럴듯한 숫자"를 내놓는다.

쓰기는 더 위험하다. 슬라이딩 윈도우처럼 **겹치는 뷰**에 값을 쓰면 여러 논리적 위치가 동시에 바뀐다.

```pyrepl
>>> a = np.arange(12)
>>> sw = as_strided(a, shape=(10, 3), strides=(a.strides[0], a.strides[0]))
>>> sw.flags.writeable
True                        # 기본값이 쓰기 가능!
>>> sw[0, 0] = 111
>>> a
[111   1   2   3   4   5   6   7   8   9  10  11]
```

`sw[0,0]` 하나만 바꾼 것 같지만, 그 메모리 위치는 `sw[1]`, `sw[2]` ... 여러 윈도우와 겹친다. 의도치 않게 여러 논리적 값을 동시에 건드리는 버그를 만들기 아주 쉽다.

**실전에서는 `as_strided` 를 직접 쓰지 마라.** 슬라이딩 윈도우가 필요하면 검사와 안전장치가 들어간 공식 API를 써라.

```pyrepl
>>> from numpy.lib.stride_tricks import sliding_window_view
>>> sw2 = sliding_window_view(a, 3)
>>> sw2.flags.writeable
False                       # 기본이 읽기 전용 — 겹침 문제를 원천 차단
```

`as_strided` 는 NumPy 내부 구현자나 정말 그 위험을 이해하고 감수하는 사람을 위한 도구다. 당신이 지금 이걸 쓰고 싶다면, 십중팔구 `sliding_window_view`, `broadcast_to`, 아니면 그냥 [9.2 브로드캐스팅](#/broadcasting) 이 필요한 상황이다.
:::

## C-연속 vs F-연속 — 메모리 순서의 두 가지 관습

다차원 배열을 1차원 메모리에 늘어놓는 방법은 두 가지뿐이다.

- **C 순서**(row-major): 마지막 축이 먼저 움직인다. `[[0,1],[2,3]]` → 메모리에 `0,1,2,3`.
- **F 순서**(column-major, Fortran 순서): 첫 축이 먼저 움직인다. 같은 배열이 메모리에 `0,2,1,3`.

NumPy는 기본이 C 순서다. `flags` 로 확인할 수 있다.

```pyrepl
>>> a = np.arange(12).reshape(3, 4)
>>> a.strides
(32, 8)
>>> a.flags['C_CONTIGUOUS'], a.flags['F_CONTIGUOUS']
(True, False)
```

### 전치는 왜 복사가 안 일어나는가

`a.T` 를 하면 셋이 동시에 바뀐다. **shape 이 뒤집히고, strides 도 뒤집히고, 연속성 플래그도 뒤집힌다.** 데이터는 한 바이트도 움직이지 않는다.

```pyrepl
>>> at = a.T
>>> at.strides
(8, 32)
>>> at.flags['C_CONTIGUOUS'], at.flags['F_CONTIGUOUS']
(False, True)
>>> np.shares_memory(a, at)
True
```

직접 증명해 보자. 뷰를 고치면 원본이 바뀐다.

```pyrepl
>>> at[0, 0] = 999
>>> a[0, 0]
999
```

`a.T` 는 *"같은 메모리를 strides 만 바꿔서 읽어라"* 는 지시일 뿐이다. `(3, 4)` 짜리 C-연속 배열을 전치하면 `(4, 3)` 짜리 F-연속 배열이 되는데, 둘 다 **같은 24개의 숫자를 서로 다른 순서로 훑는 것**뿐이다. 그래서 전치는 배열 크기와 무관하게 $O(1)$ 이다. 이게 [1.1 객체·이름·참조](#/objects-names)에서 본 "얕은 복사"의 NumPy 버전이다 — 컨테이너(shape/strides 메타데이터)만 새로 만들고 내용물(데이터 버퍼)은 공유한다.

::: warn `.base` 를 뷰 확인에 쓰지 마라
직관적으로 `at.base is a` 를 기대하겠지만, 실제로는 이렇다.

```pyrepl
>>> root = np.arange(12)
>>> a = root.reshape(3, 4)
>>> at = a.T
>>> at.base is a
False
>>> at.base is root
True
```

NumPy는 뷰의 뷰를 만들 때 `.base` 체인을 평탄화해서 **항상 최초의 소유자**를 가리키게 한다. `a` 도 사실 `root` 의 뷰였기 때문에, `a.T` 의 `.base` 는 `a` 를 건너뛰고 곧장 `root` 를 가리킨다. "이 배열이 저 배열과 메모리를 공유하는가"를 확인하고 싶으면 `.base` 를 비교하지 말고 **`np.shares_memory(x, y)`** 를 써라. 이게 유일하게 믿을 수 있는 방법이다.
:::

### `ascontiguousarray` 가 필요한 순간

뷰가 항상 공짜인 건 아니다. **레이아웃을 강제로 요구하는 코드**를 만나면 복사가 필요해진다.

```pyrepl
>>> at = a.T                          # F-연속 뷰
>>> b = np.ascontiguousarray(at)      # C-연속으로 강제 변환
>>> np.shares_memory(b, a)
False                                 # 이번엔 진짜 복사됐다
>>> b.flags['C_CONTIGUOUS']
True
```

언제 필요한가.

- **C 확장이나 다른 라이브러리(OpenCV, 일부 SciPy 루틴, ctypes로 넘기는 raw 버퍼)가 C-연속 메모리를 가정할 때.** 비연속 배열을 그대로 넘기면 잘못된 순서로 읽거나, 라이브러리가 알아서 몰래 복사해서 넘겨준 값을 못 믿게 된다.
- **`.tobytes()` / `.tofile()` 로 바이트를 그대로 내보낼 때.** 전치 뷰의 바이트 순서는 원본과 다르므로, 특정 순서를 기대하는 파일 포맷에 쓰려면 먼저 연속 메모리로 만들어야 한다.
- **반복적으로 스캔하는 핫 루프에서, 뷰가 비연속이라 캐시 미스가 잦을 때.** 한 번 복사해서 연속으로 만들어 두고 여러 번 재사용하면 이득이다.

::: perf 연속성이 항상 속도를 가르지는 않는다 — 실측해라
"C-연속이 항상 빠르다"는 것도 검증 없이 믿으면 안 되는 통념이다. 실측해 보면 미묘하다.

```python title="전치 뷰로 행렬곱을 해도 BLAS 성능은 거의 그대로"
import timeit
A = np.random.default_rng(0).random((1000, 1000))
At = A.T                       # F-연속 뷰, 복사 없음
B = np.random.default_rng(1).random((1000, 1000))

timeit.timeit(lambda: A @ B, number=30)    # 3.115 ms
timeit.timeit(lambda: At @ B, number=30)   # 3.060 ms  — 거의 차이 없다
```

BLAS는 C/F 연속 배열 양쪽을 다 직접 처리하도록 설계돼 있다. 반면 축 방향 리덕션은 다른 이야기다.

```python title="합계 방향에 따른 속도 — 직관과 반대로 나온다"
M = np.random.default_rng(0).random((3000, 3000))   # C-연속

timeit.timeit(lambda: M.sum(axis=1), number=20)   # 2.769 ms  (행 방향 합)
timeit.timeit(lambda: M.sum(axis=0), number=20)   # 0.881 ms  (열 방향 합)
```

(NumPy 2.5.1 / Windows 기준 실측. 여러 번 반복해도 이 순서는 안정적으로 재현됐다.)

"메모리에서 연속인 축(axis=1, 행 내부)을 따라 줄이는 게 캐시에 유리하니 더 빠를 것"이라는 예상과 **실제 결과가 반대**다. NumPy의 리덕션 구현은 축 순서에 따라 다른 커널을 타고, `axis=0` 방향은 행 전체를 한 번에 읽어 누산 배열에 SIMD로 더하는 방식이 유리하게 작동한다. **결론은 "이래서 axis=0이 빠르다"를 암기하는 게 아니라, 속도가 걸린 코드라면 직감 대신 반드시 [5.1 측정 없이 최적화 없다](#/profiling)의 도구로 재보라는 것**이다. 배열 크기, dtype, NumPy 버전이 바뀌면 이 순서도 바뀔 수 있다.
:::

## ufunc — 벡터화의 진짜 정체

`a + b`, `np.sqrt(a)`, `np.maximum(a, b)` 가 빠른 이유는 이것들이 전부 **ufunc**(universal function)이기 때문이다. ufunc은 파이썬 루프 없이 **C로 짜인 반복문 하나**가 배열 전체를 훑으면서 원소마다 같은 스칼라 연산을 적용하는 객체다.

```pyrepl
>>> type(np.add)
<class 'numpy.ufunc'>
>>> np.add.nin, np.add.nout
(2, 1)
>>> np.add.types[:5]
['??->?', 'bb->b', 'BB->B', 'hh->h', 'HH->H']
```

`np.add` 는 단순한 함수가 아니라 **타입별로 미리 컴파일된 커널의 묶음**이다. `types` 목록의 각 문자열은 "이 입력 dtype 조합에는 이 C 커널을 써라"는 디스패치 표다. 그래서 `int32 + int32` 와 `float64 + float64` 는 서로 다른 커널을 타면서도 같은 `np.add` 라는 이름 뒤에 숨어 있다. 브로드캐스팅([9.2 브로드캐스팅](#/broadcasting))도 ufunc의 내장 기능이다 — 파이썬 레벨에서 모양을 맞추는 코드가 전혀 없다.

### 내 함수를 ufunc처럼 만들기 — 그런데 빠르지는 않다

`np.vectorize` 와 `np.frompyfunc` 는 임의의 파이썬 함수를 배열에 적용할 수 있게 감싸 준다. 이름 때문에 "이러면 진짜 ufunc처럼 빨라지겠지"라고 오해하기 쉽다. **틀렸다.** 실측해 보자.

```python title="real_ufunc.py — 네 가지 방식 비교"
import numpy as np
import timeit

n = 200_000
a = np.random.rand(n)
b = np.random.rand(n)

def custom_scalar(x, y):
    return x + y if x > y else x * y

def py_loop():
    out = [0.0] * n
    for i in range(n):
        out[i] = custom_scalar(a[i], b[i])
    return out

vec = np.vectorize(custom_scalar)
fpy = np.frompyfunc(custom_scalar, 2, 1)
real_ufunc = lambda: np.where(a > b, a + b, a * b)   # 진짜 ufunc 조합

for name, fn in [("python 루프", py_loop), ("np.vectorize", lambda: vec(a, b)),
                 ("np.frompyfunc", lambda: fpy(a, b)), ("진짜 ufunc", real_ufunc)]:
    t = timeit.timeit(fn, number=5) / 5 * 1000
    print(f"{name:15s}: {t:7.3f} ms")
```

```text nolines
python 루프    :  37.147 ms
np.vectorize   :  19.290 ms
np.frompyfunc  :  16.050 ms
진짜 ufunc     :   0.611 ms
```

(NumPy 2.5.1 / Windows 기준 실측.) 진짜 ufunc이 파이썬 루프보다 **약 61배**, `np.vectorize` 보다도 **약 32배** 빠르다. 이유는 단순하다. `vectorize` 와 `frompyfunc` 는 내부적으로 **원소마다 여전히 파이썬 함수 `custom_scalar` 를 호출한다.** C 루프 안에서 스칼라 연산을 한 게 아니라, C 루프가 파이썬 콜백을 매번 부르는 것뿐이다. 배열 모양을 다루는 편의만 얻었지, 파이썬 함수 호출 오버헤드는 그대로 남는다.

::: note frompyfunc과 vectorize의 차이
`frompyfunc` 은 **항상 `dtype=object`** 배열을 반환한다. 결과가 숫자여도 파이썬 객체로 boxing된 채 나온다.

```pyrepl
>>> fpy(a[:3], b[:3])
array([2.0, 6.0, 9.0], dtype=object)
```

`np.vectorize` 는 `frompyfunc` 위에 얇은 래퍼를 씌워서 결과를 적절한 숫자 dtype으로 캐스팅해 준다(`otypes` 로 직접 지정할 수도 있다). 그래서 겉보기엔 더 "진짜 ufunc" 같지만, 속도 면에서는 근본적으로 같은 처지다.
:::

**진짜로 빠른 커스텀 ufunc이 필요하면** `vectorize`/`frompyfunc` 가 아니라 [5.5 Cython, Numba, mypyc](#/compilers)로 가야 한다. Numba의 `@vectorize` 데코레이터는 이름은 비슷해도 실제로 C 수준 커널을 컴파일해서 만들기 때문에 이 벤치마크의 "진짜 ufunc" 줄에 가까운 성능을 낸다.

## einsum — 텐서 축약을 표현하는 언어, 그러나 만능은 아니다

`np.einsum` 은 아인슈타인 표기법으로 행렬곱, 전치, 대각합, 배치 연산을 **하나의 통일된 문법**으로 표현한다.

```pyrepl
>>> A = np.arange(6).reshape(2, 3)
>>> B = np.arange(12).reshape(3, 4)
>>> np.einsum('ij,jk->ik', A, B)          # 행렬곱 = A @ B
>>> np.einsum('ii->', np.eye(3) * 5)      # 대각합 = np.trace(...)
15.0
>>> np.einsum('bij,bjk->bik', Ab, Bb)     # 배치 행렬곱 = np.matmul(Ab, Bb)
```

반복되는 인덱스(`j`)는 그 축을 따라 합산되고, 출력에 없는 인덱스는 사라진다. 코드가 어떤 연산인지 **수식 그대로 읽히는** 게 장점이다.

### 실측: einsum이 항상 빠른 건 아니다

```python title="einsum_bench.py — 일반 행렬곱과 비교"
import numpy as np, timeit

rng = np.random.default_rng(0)
A = rng.random((500, 500))
B = rng.random((500, 500))

t_matmul = timeit.timeit(lambda: A @ B, number=20) / 20 * 1000
t_ein_default = timeit.timeit(lambda: np.einsum('ij,jk->ik', A, B), number=20) / 20 * 1000
t_ein_opt = timeit.timeit(lambda: np.einsum('ij,jk->ik', A, B, optimize=True), number=20) / 20 * 1000
print(f"A @ B                : {t_matmul:.3f} ms")
print(f"einsum (기본값)       : {t_ein_default:.3f} ms")
print(f"einsum(optimize=True): {t_ein_opt:.3f} ms")
```

```text nolines
A @ B                : 0.713 ms
einsum (기본값)       : 17.645 ms
einsum(optimize=True): 0.722 ms
```

(NumPy 2.5.1 / Windows 기준 실측.) **기본 설정의 `einsum` 은 BLAS로 가는 `@` 보다 24배 느리다.** `einsum` 은 기본적으로 자기 자신의 범용 축약 루프를 쓰지, BLAS 같은 최적화된 행렬곱 루틴을 자동으로 타지 않기 때문이다. `optimize=True` 를 주면 NumPy가 가능한 경우 BLAS 경로로 우회하도록 계획을 세워서 `@` 와 거의 같은 속도가 나온다 — **하지만 그건 여전히 `@` 보다 빠르지 않고, 딱 같아진다.**

배치 행렬곱에서는 격차가 더 뚜렷하다.

```pyrepl
>>> Ab = rng.random((64, 64, 64)); Bb = rng.random((64, 64, 64))
>>> timeit.timeit(lambda: np.matmul(Ab, Bb), number=50) / 50 * 1000
0.397   # ms
>>> timeit.timeit(lambda: np.einsum('bij,bjk->bik', Ab, Bb), number=50) / 50 * 1000
3.083   # ms
```

**결론: 단순한 행렬곱·배치 행렬곱이라면 `@` 나 `np.matmul` 을 써라.** `einsum` 은 그 경우에 더 빠를 이유가 없다.

### einsum이 진짜로 이기는 경우 — 축약 순서 최적화

`einsum` 의 진짜 무기는 **여러 텐서를 한 번에 축약할 때 계산 순서를 자동으로 골라 준다**는 것이다. 파이썬에서 `@` 를 체이닝하면 항상 **왼쪽부터** 계산되는데, 이 순서가 최악일 수 있다.

```python title="chain_order.py — 순서가 성능을 좌우하는 경우"
import numpy as np, timeit

rng = np.random.default_rng(0)
M1 = rng.random((2000, 2))
M2 = rng.random((2, 2000))
M3 = rng.random((2000, 2))

def naive_chain():
    return M1 @ M2 @ M3        # 왼쪽부터: (2000,2)@(2,2000) → (2000,2000) 거대 중간행렬!

def einsum_opt():
    return np.einsum('ij,jk,kl->il', M1, M2, M3, optimize=True)

t_naive = timeit.timeit(naive_chain, number=20) / 20 * 1000
t_opt = timeit.timeit(einsum_opt, number=20) / 20 * 1000
print(f"naive @ 체이닝        : {t_naive:.3f} ms")
print(f"einsum(optimize=True): {t_opt:.3f} ms")
```

```text nolines
naive @ 체이닝        : 2.699 ms
einsum(optimize=True): 0.032 ms
```

(NumPy 2.5.1 / Windows 기준 실측.) **약 84배 차이.** `M1 @ M2` 를 먼저 계산하면 $(2000, 2000)$ 짜리 중간 행렬이 생겨서 $O(2000^2 \times 2)$ 만큼 낭비된다. 반면 `M2 @ M3` 를 먼저 계산하면 $(2, 2)$ 짜리 작은 행렬만 생긴다. `einsum(optimize=True)` 는 `np.einsum_path` 로 이 계획을 자동으로 세운다.

```pyrepl
>>> print(np.einsum_path('ij,jk,kl->il', M1, M2, M3, optimize=True)[1])
  Complete contraction:  ij,jk,kl->il
         Naive scaling:  4
     Optimized scaling:  3
      Naive FLOP count:  4.800e+07
  Optimized FLOP count:  3.200e+04
  Theoretical speedup:  1499.953
  Largest intermediate:  4.000e+03 elements
...
```

이게 `einsum` 을 쓰는 정당한 이유다 — **연산 자체를 빠르게 하는 게 아니라, 계산 순서를 실수하지 않게 대신 계획해 주는 것.** 두세 개짜리 단순 텐서 곱에는 과하고, 네 개 이상의 텐서를 다양한 축으로 축약해야 하는 상황(텐서 네트워크, 어텐션 계산의 일부)에서 진가를 발휘한다.

::: cote 코딩테스트 포인트
코딩테스트에서 `einsum` 을 쓸 일은 거의 없다. 다만 **행렬 체이닝의 계산 순서가 전체 복잡도를 바꾼다**는 원리 자체는 "행렬 체인 곱셈"(matrix chain multiplication) DP 문제로 그대로 나온다. [7.21 동적 계획법 심화](#/dp-advanced)에서 다시 만난다 — 여기서는 NumPy가 그 최적화를 `optimize=True` 한 줄로 대신해 준다는 차이뿐이다.
:::

## 종합: 왜 이게 ML/DL/비전의 기반인가

이 절에서 본 세 가지 — 스트라이드, ufunc, einsum — 는 전부 같은 질문에 대한 답이다. **"파이썬 반복문을 어떻게 없애는가."** 딥러닝 프레임워크(PyTorch, [11.2 PyTorch 텐서](#/torch-tensor))의 텐서도 내부적으로 스트라이드를 그대로 쓰고, `view()`/`permute()` 가 복사 없이 동작하는 것도 똑같은 원리다. 어텐션 연산의 실제 구현도 `einsum` 이거나 그와 동등한 축약이다. 여기서 "뷰가 왜 공짜인지", "ufunc이 왜 빠른지", "축약 순서가 왜 중요한지"를 체감해 두면, 뒤에서 그 지식을 다시 설명받을 필요가 없다 — 이름만 바뀌어서 나타날 뿐이다.

## 요약

- 배열은 **연속 메모리 + strides** 다. reshape/transpose가 공짜인 이유가 여기 있다.
- `as_strided` 는 경계 검사가 없다. 잘못 쓰면 남의 메모리를 읽거나(조용히 쓰레기 값), 겹치는 뷰에 쓰기를 해서 값을 오염시킨다. 슬라이딩 윈도우는 `sliding_window_view` 를 써라.
- **C-연속과 F-연속은 같은 데이터를 다른 순서로 읽는 관습**일 뿐이다. 전치는 strides만 바꾸는 $O(1)$ 연산이라 복사가 없다 — `np.shares_memory` 로 확인해라. `.base` 는 최초 소유자를 가리키므로 뷰 확인 용도로 믿지 마라.
- 레이아웃을 강제로 요구하는 코드(C 확장, 파일 I/O)를 만나면 `np.ascontiguousarray` 로 복사해라. 어떤 축으로 줄이는 게 빠른지는 직관이 아니라 **실측**으로 정해라.
- `np.vectorize`/`np.frompyfunc` 는 배열 인터페이스를 주지만 내부적으로 여전히 파이썬 함수를 호출한다 — 진짜 ufunc보다 실측 30~60배 느리다. 진짜 속도가 필요하면 Numba/Cython으로 가라.
- `einsum` 은 기본 설정으로는 BLAS 행렬곱보다 느리다. `optimize=True` 로 BLAS 경로를 타게 하거나, 여러 텐서를 축약할 때 최적 순서를 자동으로 찾게 하는 게 진짜 용도다.

::: quiz 연습문제
1. `a = np.arange(24).reshape(2, 3, 4)` 의 `strides` 를 손으로 계산해서 예측한 뒤 `a.strides` 로 확인하라.
2. `as_strided` 로 `a = np.arange(6)` 에서 겹치는 윈도우(윈도우 크기 2)를 만들고, 그중 하나를 수정했을 때 원본 `a` 가 어떻게 바뀌는지 예측하고 확인하라.
3. `b = np.arange(6).reshape(2, 3)` 과 `c = b.T` 에 대해 `np.shares_memory(b, c)` 와 `c.base is b` 를 각각 예측하고 실행해서 왜 다른지 설명하라.
4. `np.frompyfunc(lambda x, y: x + y, 2, 1)` 로 만든 함수를 두 개의 `float64` 배열에 적용한 결과의 `dtype` 을 예측하고 확인하라. 왜 그런 dtype이 나오는가?
5. 세 행렬 `X:(1000, 3)`, `Y:(3, 1000)`, `Z:(1000, 3)` 에 대해 `X @ Y @ Z` 와 `np.einsum('ij,jk,kl->il', X, Y, Z, optimize=True)` 의 실행 시간을 직접 측정해서 비교하라. `np.einsum_path` 로 어떤 순서를 골랐는지도 확인하라.
:::

**다음 절**: [9.4 선형대수](#/linalg) — 행렬 분해, 최소자승, 고윳값을 코드로 직접 확인한다.
