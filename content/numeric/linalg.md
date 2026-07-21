# 9.4 선형대수

::: lead
`@` 연산자 하나로 행렬을 곱할 수 있다는 건 안다. 그런데 그 뒤에서 무슨 계산이 일어나는지, 왜 `np.linalg.inv` 로 역행렬을 구해서 곱하면 안 되는지, LU·QR·SVD가 실제로 무엇을 분해하는지는 대부분 건너뛴다. 이 절은 그 밑바닥을 코드로 직접 확인한다. 최소자승 피팅, 고윳값 분해 같은 ML의 기초 연산도 여기서 손으로 굴려 본다. 이 파트 전체가 그렇듯, **말로 설명하지 않고 실행해서 보여준다.**
:::

## `@` 는 행렬곱이다, `*` 가 아니다

[9.2 브로드캐스팅](#/broadcasting)에서 `*` 는 원소별(element-wise) 곱셈이라고 배웠다. 선형대수의 "행렬곱"은 다른 연산이다. 파이썬 3.5부터 생긴 `@` 연산자가 그 자리를 담당한다.

```python title="matmul_vs_elementwise.py"
import numpy as np

A = np.array([[2.0, 1.0], [1.0, 3.0]])
B = np.array([[1.0, 0.0], [0.0, 1.0]])

print(A @ B)          # 행렬곱
print(np.dot(A, B))   # 같은 결과 — @ 는 __matmul__, np.dot 의 문법 설탕이다
print(A * B)          # 원소별 곱셈 — 완전히 다른 연산
```

```text nolines
A @ B =
[[2. 1.]
 [1. 3.]]

A * B =
[[2. 0.]
 [0. 3.]]
```

2차원 배열에서는 `@` 와 `np.dot` 이 정확히 같은 결과를 낸다. 차이는 고차원에서 갈린다. `np.dot` 은 3차원 이상에서 마지막 축과 뒤에서 두 번째 축을 곱하는 규칙이 직관과 어긋나는 경우가 많고, `@` 는 배치 행렬곱(batched matmul)을 표준적으로 처리하도록 설계됐다. 딥러닝 프레임워크가 배치 단위로 텐서를 곱할 때 `@` 문법을 따르는 이유가 이거다. **2차원 이상을 다룰 땐 `@` 를 기본으로 쓰고, `np.dot` 은 레거시 코드에서 만나는 것으로 취급해라.**

### 벡터화가 빠른 진짜 이유 — 다시 한번 실측

[1.1 객체·이름·참조](#/objects-names)와 [5.1 프로파일링](#/profiling)에서 반복해 온 얘기를 행렬곱으로 마지막으로 확인하자. $80 \times 80$ 행렬을 파이썬 3중 루프로 곱한 것과 `@` 를 비교한다.

```python title="naive_matmul_vs_blas.py"
import time
import numpy as np

n = 80
rng = np.random.default_rng(0)
A = rng.random((n, n))
B = rng.random((n, n))

def naive_matmul(A, B):
    n, m = A.shape
    _, p = B.shape
    C = np.zeros((n, p))
    for i in range(n):
        for j in range(p):
            s = 0.0
            for k in range(m):
                s += A[i, k] * B[k, j]
            C[i, j] = s
    return C

t0 = time.perf_counter(); C1 = naive_matmul(A, B); t1 = time.perf_counter()
print("순수 파이썬 3중 루프:", t1 - t0, "초")

t0 = time.perf_counter(); C2 = A @ B; t1 = time.perf_counter()
print("A @ B (BLAS):", t1 - t0, "초")

print(np.allclose(C1, C2))
```

```text nolines
순수 파이썬 3중 루프: 0.0747 초
A @ B (BLAS): 0.0000516 초
True
```

(Python 3.14 / numpy 2.5.1 / Windows 기준 실측. 약 **1,450배** 차이다.) 80×80이면 원소 51만 2천 번의 곱셈-덧셈뿐인데도 이 차이가 난다. `A[i, k]` 같은 인덱싱마다 파이썬 객체를 만들고 버리는 비용, 그리고 반복문 자체의 바이트코드 디스패치 비용이 누적된 결과다. `@` 는 내부적으로 BLAS(Basic Linear Algebra Subprograms) 라이브러리를 호출한다. C로 짜여 있고, CPU 캐시 구조에 맞춰 블록 단위로 계산하며, 경우에 따라 SIMD 명령과 멀티스레드까지 쓴다. **이 파트에서 "왜 반복문이 느린가"를 계속 강조하는 이유가 여기서 가장 극적으로 드러난다.**

## 역행렬의 함정 — `inv` 대신 `solve`

선형 연립방정식 $Ax = b$ 를 풀 때, 수학 시간에 배운 방법을 그대로 코드로 옮기고 싶어진다.

```python
x = np.linalg.inv(A) @ b     # ❌ 동작은 하지만 나쁜 습관
```

이게 왜 나쁜지 두 가지 각도에서 보자.

### 각도 1 — 낭비되는 계산

$Ax = b$ 를 풀기 위해 필요한 건 $b$ **하나**에 대한 답이다. 그런데 `inv(A)` 는 $A^{-1}$ 전체, 즉 $n$개의 열 전부를 계산한다. 이는 $n$개의 서로 다른 우변에 대해 연립방정식을 $n$번 푸는 것과 맞먹는 일이다. 그러고 나서 그 결과를 다시 $b$ 와 곱한다. **`solve`는 필요한 계산만 한다.**

```python title="inv_vs_solve_time.py"
import time
import numpy as np

n = 500
rng = np.random.default_rng(0)
M = rng.random((n, n))
b = rng.random(n)

t0 = time.perf_counter()
for _ in range(50):
    np.linalg.inv(M) @ b
t1 = time.perf_counter()
print("inv 방식 평균:", (t1 - t0) / 50, "초")

t0 = time.perf_counter()
for _ in range(50):
    np.linalg.solve(M, b)
t1 = time.perf_counter()
print("solve 방식 평균:", (t1 - t0) / 50, "초")
```

```text nolines
inv 방식 평균: 0.0372 초
solve 방식 평균: 0.0328 초
```

(numpy 2.5.1 / Windows 기준 실측. 이 실행에서는 `solve`가 약 12% 빠르다. **단, 이 수치 자체를 외우지는 마라** — 같은 코드를 그대로 여러 번 돌려보면 5%에서 30% 이상까지 격차가 들쭉날쭉하고, 시스템 부하가 낀 순간에는 `inv`가 순간적으로 더 빠르게 나온 적도 있다(측정 노이즈다). $n=500$, 반복 50회짜리 이 정도 규모의 벤치마크는 스레드 스케줄링이나 캐시 상태 같은 외부 요인에 크게 흔들린다는 뜻이다. **재현되는 건 방향성이다** — 반복해서 여러 번 측정하면 `solve`가 `inv`보다 느린 경우는 거의 없다. $n$ 이 커질수록 이 격차는 더 벌어지는 경향이 있다 — 역행렬 계산 자체가 $O(n^3)$ 이고 상수항이 `solve`보다 크기 때문이다. 정확한 배율을 알고 싶다면 직접 여러 번 실행해서 중앙값을 보는 게 안전하다.)

### 각도 2 — 수치 안정성

이게 진짜 이유다. `inv` 로 만든 역행렬은 부동소수점 오차가 누적된 근사치이고, 그걸 다시 곱하면 오차가 한 번 더 증폭된다. **행렬의 조건수(condition number)가 클수록** 이 차이가 폭발적으로 커진다.

힐베르트 행렬(Hilbert matrix)은 악명 높게 조건이 나쁜 행렬이다. 이걸로 실측해 보자.

```python title="hilbert_ill_conditioned.py"
import numpy as np
from scipy.linalg import hilbert

n = 12
H = hilbert(n)
x_true = np.ones(n)
b = H @ x_true                      # 정답을 알고 있는 문제를 역으로 만든다

x_inv = np.linalg.inv(H) @ b
x_solve = np.linalg.solve(H, b)

print("조건수:", np.linalg.cond(H))
print("inv 오차:", np.linalg.norm(x_inv - x_true))
print("solve 오차:", np.linalg.norm(x_solve - x_true))
```

```text nolines
조건수: 1.6198146845303300e+16
inv 오차: 9.441581303123591
solve 오차: 0.4466671116940329
```

정답은 전부 1인데, `inv` 로는 오차가 9.4나 나고 `solve` 로도 0.45나 난다. 조건수 $10^{16}$ 짜리 행렬은 애초에 어느 방법으로도 정확히 풀 수 없다는 뜻이다(배정밀도 부동소수점의 유효자리가 약 16자리이기 때문이다. [1.2 숫자와 수치 연산](#/numbers)에서 다룬 부동소수점 오차의 확장판이다). 하지만 **같은 조건에서 `solve`가 항상 덜 틀린다.** 이게 핵심이다.

::: warn 역행렬이 필요해 보여도 대부분은 아니다
"역행렬을 구해서 곱한다"는 사고방식 자체가 함정이다. $Ax=b$ 를 풀고 싶으면 `solve(A, b)`. 여러 개의 우변 $b_1, b_2, \dots$ 를 한꺼번에 풀고 싶으면 `solve(A, np.column_stack([b1, b2, ...]))` — 이것도 `inv(A)` 보다 낫다. **`inv`가 정말 필요한 경우는 역행렬 자체가 결과물일 때뿐이다**(공분산 행렬의 역행렬을 통계량으로 쓰는 경우 등).
:::

## LU, QR, SVD — 행렬을 뜯어보기

행렬 분해(decomposition)는 하나의 행렬을 다루기 쉬운 여러 행렬의 곱으로 쪼개는 것이다. `solve`, `lstsq`, `eig` 같은 고수준 함수들이 내부적으로 쓰는 재료이기도 하다. 세 가지를 직접 분해하고, **분해한 걸 다시 곱해서 원본이 나오는지 검증**하는 것으로 이해한다.

```python title="decompositions.py"
import numpy as np
from scipy.linalg import lu

rng = np.random.default_rng(42)
A = rng.integers(1, 10, size=(4, 4)).astype(float)
```

### LU 분해 — 가우스 소거법을 행렬로

`solve`가 내부적으로 하는 일이 정확히 이거다. $A = PLU$ 로 쪼갠다. $P$는 행을 바꾸는 순열 행렬(피벗팅), $L$은 대각이 1인 하삼각행렬, $U$는 상삼각행렬이다.

```python
P, L, U = lu(A)
print(P @ L @ U)
print("복원 오차:", np.linalg.norm(A - P @ L @ U))
```

```text nolines
[[1. 7. 6. 4.]
 [4. 8. 1. 7.]
 [2. 1. 5. 9.]
 [7. 7. 7. 8.]]
복원 오차: 0.0
```

$A = PLU$ 로 쪼개고 나면 $Ax=b$ 는 $PLUx=b$ 가 되고, 이걸 삼각행렬 두 번의 대입 계산(전진 대입, 후진 대입)으로 풀 수 있다. 삼각행렬은 소거 없이 한 줄씩 순서대로 풀리므로 $O(n^2)$ 이면 끝난다. **역행렬을 구하지 않고도 방정식을 풀 수 있는 이유**가 바로 이 분해다.

### QR 분해 — 직교 기저로 바꾸기

$A = QR$. $Q$는 직교행렬(열벡터가 서로 수직이고 크기가 1), $R$은 상삼각행렬이다.

```python
Q, R = np.linalg.qr(A)
print("복원 오차:", np.linalg.norm(A - Q @ R))
print("Q.T @ Q (직교성):\n", Q.T @ Q)
```

```text nolines
복원 오차: 4.362484308104375e-15
Q.T @ Q (직교성):
[[ 1.00000000e+00  1.50687112e-16  4.79992960e-17 -5.39493880e-17]
 [ 1.50687112e-16  1.00000000e+00  6.12531457e-17 -9.58642049e-17]
 [ 4.79992960e-17  6.12531457e-17  1.00000000e+00 -1.56023601e-16]
 [-5.39493880e-17 -9.58642049e-17 -1.56023601e-16  1.00000000e+00]]
```

대각 원소는 정확히 1이고, 나머지는 죄다 `1e-16` ~ `1e-17` 수준이다 — 딱 배정밀도 부동소수점의 머신 엡실론 자리다. 즉 이건 완벽한 항등행렬은 아니지만 **수치적으로 항등행렬과 구분이 안 되는** 결과다(`np.allclose(Q.T @ Q, np.eye(4))` 로 확인하면 `True`). `Q.T @ Q` 가 (수치적으로) 단위행렬이라는 게 "직교행렬"의 정의를 그대로 확인해 준다. 직교행렬은 곱해도 벡터의 길이와 각도를 바꾸지 않는다(회전·반사만 한다) — 그래서 수치적으로 아주 안정적이다. QR 분해는 최소자승법을 안정적으로 푸는 핵심 도구다. 바로 아래에서 쓴다.

### SVD — 가장 일반적인 분해

특이값 분해(Singular Value Decomposition)는 **정사각이 아니어도, 역행렬이 없어도** 항상 존재하는 분해다. $A = U \Sigma V^T$ — $U$, $V$는 직교행렬, $\Sigma$ 는 대각선에 음이 아닌 특이값이 큰 순서로 놓인 행렬이다.

```python
U, S, Vt = np.linalg.svd(A)
Sigma = np.zeros_like(A)
np.fill_diagonal(Sigma, S)
print("복원 오차:", np.linalg.norm(A - U @ Sigma @ Vt))
print("특이값:", S)
```

```text nolines
복원 오차: 7.738182802630888e-15
특이값: [22.0169  6.1627  4.5739  3.2178]
```

::: note 세 분해를 언제 쓰는가
- **LU** — 정사각 행렬에서 $Ax=b$ 를 여러 번(다른 $b$로) 풀 때. 분해를 한 번만 해 두고 재사용한다.
- **QR** — 최소자승 피팅, 직교화(그람-슈미트의 안정된 버전), $QR$ 알고리즘 기반 고윳값 계산.
- **SVD** — 정사각이 아닌 행렬, 랭크가 부족한 행렬, 주성분분석(PCA), 유사역행렬(pseudo-inverse) 계산. 가장 느리지만 가장 안정적이고 가장 많은 정보를 준다.
:::

::: deep 왜 복원 오차가 정확히 0이 아닌가
LU는 `0.0`이 나왔는데 QR과 SVD는 `1e-15` 수준의 아주 작은 값이 나왔다. 둘 다 부동소수점 연산이 누적된 결과이지만, LU는 이 예제의 정수 입력과 피벗팅 조합이 우연히 딱 떨어졌을 뿐이다. `1e-15`는 배정밀도 부동소수점의 최소 유효자리(약 $2.2 \times 10^{-16}$, [1.2 숫자와 수치 연산](#/numbers)의 머신 엡실론)와 같은 자릿수다. **이 정도는 "완전히 같다"로 취급해도 된다.** `np.allclose(A, U @ Sigma @ Vt)` 로 확인하는 게 `==` 로 정확히 비교하는 것보다 항상 옳다.
:::

## 최소자승법 — 데이터에 직선 피팅하기

방정식의 개수가 미지수보다 많으면(즉 데이터가 노이즈를 포함하면) $Ax=b$ 를 정확히 만족하는 $x$ 는 없다. 대신 $\|Ax-b\|^2$ 를 최소화하는 $x$ 를 찾는다 — 이게 최소자승법(least squares)이다. 회귀 분석의 뼈대다.

```python title="least_squares_fit.py"
import numpy as np

rng = np.random.default_rng(7)
x = np.linspace(0, 10, 50)
true_a, true_b = 2.5, -1.0
y = true_a * x + true_b + rng.normal(0, 1.5, size=x.shape)   # 노이즈 낀 관측치

A = np.column_stack([x, np.ones_like(x)])    # 설계 행렬 — 열이 [기울기 항, 절편 항]
print("A shape:", A.shape)                    # (50, 2) — 미지수보다 방정식이 많다

coef, residuals, rank, sv = np.linalg.lstsq(A, y, rcond=None)
print("lstsq 추정 (a, b):", coef)
```

```text nolines
A shape: (50, 2)
lstsq 추정 (a, b): [ 2.558  -1.7289]
```

진짜 기울기 2.5, 절편 -1.0에 노이즈가 섞여 2.558, -1.7289로 추정됐다 — 합리적인 결과다. `np.linalg.lstsq` 는 내부적으로 SVD를 쓴다. **직접 정규방정식(normal equation)** $A^TAx = A^Ty$ 을 풀어서 검산해 보자.

```python
coef_normal = np.linalg.solve(A.T @ A, A.T @ y)
print("정규방정식 결과:", coef_normal)
print("두 방법 차이:", np.linalg.norm(coef - coef_normal))

print("cond(A):", np.linalg.cond(A))
print("cond(A.T @ A):", np.linalg.cond(A.T @ A))
```

```text nolines
정규방정식 결과: [ 2.558  -1.7289]
두 방법 차이: 2.979040983896728e-15
cond(A): 11.687812992148189
cond(A.T @ A): 136.60497253942794
```

값은 사실상 같다. 하지만 조건수를 보면 `A.T @ A` 가 `A`보다 약 **12배** 나쁘다 — 우연이 아니다. 정규방정식으로 풀면 조건수가 **제곱**이 된다는 게 선형대수의 정리다($\kappa(A^TA) = \kappa(A)^2$). 이 예제는 $11.7^2 \approx 137$ 로 딱 들어맞는다.

::: perf 정규방정식보다 lstsq / QR
데이터가 적을 땐 정규방정식으로 풀어도 티가 안 난다. 하지만 조건수가 큰 데이터(강하게 상관된 특징들, [9.6 pandas 실전](#/pandas-advanced)에서 다룰 다중공선성)에서는 정규방정식이 먼저 정밀도를 잃는다. **`np.linalg.lstsq` 나 `scipy.linalg.qr` 기반 방법을 기본으로 써라.** scikit-learn의 `LinearRegression` 도 내부적으로 SVD 기반 최소자승을 쓴다. 직접 $A^TA$ 를 구성해서 푸는 코드를 보면 의심해야 한다.
:::

## 고윳값과 고유벡터

행렬 $A$ 를 곱해도 **방향은 안 바뀌고 크기만 바뀌는** 벡터가 있다면, 그게 고유벡터(eigenvector)다. 그 배율이 고윳값(eigenvalue)이다.

$$Av = \lambda v$$

```python title="eigen_verify.py"
import numpy as np

A = np.array([[4.0, 1.0], [2.0, 3.0]])
eigvals, eigvecs = np.linalg.eig(A)
print("고윳값:", eigvals)

for i in range(2):
    lam = eigvals[i]
    v = eigvecs[:, i]          # 고유벡터는 열 방향으로 저장된다
    lhs = A @ v
    rhs = lam * v
    print(f"A@v = {lhs.real}, λ·v = {rhs.real}, 차이 = {np.linalg.norm(lhs - rhs):.2e}")
```

```text nolines
고윳값: [5.+0.j 2.+0.j]
A@v = [3.5355 3.5355], λ·v = [3.5355 3.5355], 차이 = 0.00e+00
A@v = [-0.8944  1.7889], λ·v = [-0.8944  1.7889], 차이 = 2.22e-16
```

::: warn eig() 는 항상 복소수를 반환할 수 있다
`eigvals`의 dtype이 `complex128`이다. **실수 행렬이라도 고윳값이 복소수일 수 있기 때문**이다(회전 행렬이 대표적이다 — 회전은 "방향이 안 바뀌는 실수 벡터"가 없다). 이 예제는 우연히 허수부가 0이라 실수처럼 보였을 뿐이다. `eigvals.real` 로 실수부만 뽑기 전에, 정말 실수인지(`np.allclose(eigvals.imag, 0)`) 먼저 확인해라.
:::

`eigvecs[:, i]` 처럼 **열 방향**으로 읽어야 한다는 점이 실수하기 쉬운 지점이다. [9.1 NumPy: ndarray의 모든 것](#/numpy-basics)에서 다룬 행 우선(row-major) 메모리 레이아웃과는 무관하게, 이건 "고유벡터 행렬의 각 열이 하나의 고유벡터"라는 수학적 관례일 뿐이다.

### 대칭행렬은 특별하다

행렬이 대칭이면(공분산 행렬, 그람 행렬 등 ML에서 매우 흔하다) 고윳값은 항상 실수이고 고유벡터는 항상 직교한다. 전용 함수 `eigh` 가 이걸 이용해 더 빠르고 안정적으로 계산한다.

```python
S = np.array([[2.0, 1.0], [1.0, 2.0]])
w, V = np.linalg.eigh(S)
print("고윳값:", w)
print("V.T @ V (직교성):\n", V.T @ V)
```

```text nolines
고윳값: [1. 3.]
V.T @ V (직교성):
[[1.00000000e+00 2.23711432e-17]
 [2.23711432e-17 1.00000000e+00]]
```

QR 때와 같은 이야기다 — 대각은 정확히 1, 비대각은 `1e-17` 수준의 반올림 오차다. `np.allclose(V.T @ V, np.eye(2))` 로 확인하면 `True`. 완벽한 항등행렬이 아니라 "부동소수점 정밀도 안에서 항등행렬"이라는 뜻이고, 그게 바로 직교성이 실전에서 확인되는 방식이다.

::: cote 인접 행렬의 거듭제곱
그래프의 인접 행렬 $A$ 를 $k$ 번 거듭제곱하면, $A^k$ 의 $(i,j)$ 원소는 **정확히 길이 $k$ 인 경로의 개수**가 된다. `np.linalg.matrix_power(A, k)` 로 바로 계산할 수 있다. 정점 수가 적고 $k$ 가 클 때([7.13 그래프](#/graph)의 BFS로는 느린 경우) 고윳값 분해로 $A^k = V \Lambda^k V^{-1}$ 를 빠르게 구하는 트릭도 있다 — $\Lambda^k$ 는 대각 원소를 $k$ 제곱하기만 하면 되기 때문이다.
:::

### 대각화로 행렬 거듭제곱 검증

고유벡터 행렬 $V$ 와 고윳값 대각행렬 $\Lambda$ 로 $A = V\Lambda V^{-1}$ 를 복원해 보자.

```python
A2 = np.array([[2.0, 0.0], [1.0, 3.0]])
w2, V2 = np.linalg.eig(A2)
recon = V2 @ np.diag(w2) @ np.linalg.inv(V2)
print("대각화 복원 오차:", np.linalg.norm(A2 - recon))
```

```text nolines
대각화 복원 오차: 0.0
```

여기서 `np.linalg.inv(V2)` 를 쓴 것에 놀랄 수 있다 — 방금 "`inv`를 피하라"고 해 놓고서. 모순이 아니다. 이번엔 **역행렬 자체가 필요한 경우**다(대각화 공식이 그렇게 정의돼 있다). 위에서 강조한 건 "$Ax=b$ 를 풀 때 `inv`를 거치지 말라"는 것이지 "`inv`를 절대 쓰지 말라"가 아니다.

## 요약

- `@` 는 행렬곱, `*` 는 원소별 곱셈. `np.dot`은 2차원에서 `@`와 같지만 고차원에서는 `@`를 써라.
- 벡터화된 행렬곱은 순수 파이썬 3중 루프보다 이 실측에서 약 1,450배 빠르다 — BLAS가 캐시와 SIMD를 쓰기 때문이다.
- $Ax=b$ 를 풀 땐 `inv(A) @ b` 대신 `solve(A, b)`. 계산량도 적고, 조건수가 나쁜 행렬에서 오차도 덜 누적된다.
- LU는 가우스 소거의 행렬 버전, QR은 직교화, SVD는 가장 일반적인 분해 — 셋 다 "분해 후 다시 곱하면 원본"으로 검증할 수 있다.
- 최소자승법은 노이즈 낀 데이터에 방정식보다 미지수가 적은 경우를 푼다. 정규방정식은 조건수를 제곱시키므로 `lstsq`가 더 안전하다.
- 고윳값·고유벡터는 $Av=\lambda v$ 를 만족하는 짝이다. 대칭행렬이면 `eigh`를 써서 실수 고윳값과 직교 고유벡터를 보장받는다.

::: quiz 연습문제
1. $3\times 3$ 랜덤 정수 행렬 `A`를 만들고, `np.linalg.inv(A) @ np.linalg.inv(A) ** -1`과 `A`가 같은지 확인하는 건 왜 무의미한 검증인지 설명하라(힌트: `**` 연산자가 행렬에 어떻게 적용되는가).
2. 조건수가 서로 다른 두 개의 $5\times 5$ 행렬을 만들어라(하나는 `np.random.default_rng().random((5,5))`, 하나는 `scipy.linalg.hilbert(5)`). 각각에 대해 `solve`의 오차를 실측하고 비교하라.
3. `np.linalg.svd(A, full_matrices=False)`와 기본 옵션의 결과 shape이 어떻게 다른지 $A$가 $5\times 3$일 때 실행해서 확인하라.
4. 대칭이 아닌 행렬에 `eigh`를 쓰면 어떤 일이 일어나는가? 실행해서 확인하고, 왜 그런 결과가 나오는지 `eigh`의 전제 조건에서 설명하라.
5. 이 절의 최소자승 예제에서 노이즈의 표준편차를 `1.5`에서 `10`으로 올리면 추정된 `(a, b)`가 참값 `(2.5, -1.0)`에서 얼마나 더 벗어나는지 실측하라.
:::

**다음 절**: [9.5 pandas 기초](#/pandas-basics) — Series와 DataFrame, 그리고 NumPy와는 다른 인덱싱의 세계.
