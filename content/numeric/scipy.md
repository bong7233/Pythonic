# 9.8 SciPy

::: lead
NumPy는 배열을 빠르게 다루는 법을 가르쳐 준다. 그런데 "이 함수의 최솟값은 어디인가", "이 점들 사이는 어떤 값일까", "이 신호에서 잡음만 걷어내려면" 같은 질문에는 NumPy가 답을 주지 않는다. 이런 질문에 답하는 검증된 수치 알고리즘 모음이 SciPy다. NumPy가 데이터를 담는 그릇이라면, SciPy는 그 그릇에 담긴 데이터로 실제 계산을 해내는 도구 상자다.
:::

## SciPy는 왜 NumPy 위에 있는가

역할을 먼저 정확히 나눠야 한다. **NumPy는 자료구조와 기본 연산**을 담당한다. `ndarray`, 브로드캐스팅, 사칙연산, 기본적인 선형대수(`np.linalg`)까지가 NumPy의 영역이다. [9.1 NumPy: ndarray의 모든 것](#/numpy-basics)에서 본 그 배열이다.

**SciPy는 그 배열을 입력받아 더 복잡한 수치 알고리즘을 수행**한다. 최적화, 보간, 신호 처리, 통계 분포, 희소 행렬, 고급 선형대수, 상미분방정식 등이다. SciPy는 NumPy를 대체하지 않는다. NumPy의 `ndarray` 위에서 동작하는 상위 레이어다.

```pyrepl
>>> import scipy
>>> import numpy as np
>>> scipy.__version__
'1.18.0'
>>> np.__version__
'2.5.1'
```

왜 이렇게 나뉘어 있는가. NumPy는 **범용 배열 컨테이너**로 설계됐다. 어떤 도메인에도 치우치지 않는 최소한의 연산만 제공한다. 반면 SciPy는 각 하위 모듈(`optimize`, `interpolate`, `signal`, `sparse`, `stats`, `linalg`, `spatial`, `ndimage`...)이 특정 수치해석 분야 전체를 다룬다. 각 모듈 뒤에는 수십 년간 검증된 Fortran/C 라이브러리(LAPACK, ARPACK, FITPACK 등)가 있다. **직접 짜면 버그가 나기 쉬운 알고리즘을, 이미 검증된 구현으로 가져다 쓰는 것**이 SciPy를 쓰는 이유다.

::: note 모듈은 따로 임포트한다
`import scipy` 만으로는 하위 모듈이 로드되지 않는다. `scipy.optimize`, `scipy.interpolate` 처럼 필요한 서브패키지를 직접 임포트해야 한다. 이건 우연이 아니라 설계다 — 각 서브패키지가 무겁고 독립적인 의존성(예: 선형대수 라이브러리)을 가질 수 있어서, 쓰지 않는 모듈까지 매번 로드하지 않게 만든 것이다.
:::

이 절에서는 SciPy의 방대한 영역 중 실무에서 가장 자주 마주치는 네 갈래 — 최적화, 보간, 신호 처리, 희소 행렬 — 를 직접 실행하며 훑는다.

## 최적화: scipy.optimize

"어떤 함수의 최솟값을 찾아라"는 ML에서 손실 함수를 최소화하는 것부터 로봇의 역기구학을 푸는 것까지, 모든 곳에 등장하는 문제다.

문제부터 보자. 다음 함수의 최솟값을 직접 찾는다고 하면 어떻게 할까.

```python title="찾을 함수: (x-3)^2 + (y+1)^2 + 5, 최솟값은 (3, -1)에서 5"
def f(x):
    return (x[0] - 3) ** 2 + (x[1] + 1) ** 2 + 5
```

가장 무식한 방법은 격자를 촘촘히 훑어보는 것이다.

```python title="격자 탐색 — 순수 NumPy"
import numpy as np

def grid_search():
    best, best_val = None, float("inf")
    for a in np.linspace(-10, 10, 200):
        for b in np.linspace(-10, 10, 200):
            val = f([a, b])
            if val < best_val:
                best_val, best = val, (a, b)
    return best, best_val
```

이걸 `scipy.optimize.minimize` 와 비교해서 실제로 돌려 본다.

```pyrepl
>>> import timeit
>>> from scipy import optimize
>>> t_grid = timeit.timeit(grid_search, number=1)
>>> t_min = timeit.timeit(lambda: optimize.minimize(f, x0=[0, 0]), number=1)
>>> grid_search()
((2.9648241206030157, -0.9547738693467327), 5.003282745385218)
>>> res = optimize.minimize(f, x0=[0, 0])
>>> res.x, res.fun, res.nfev
(array([ 3.00000027, -0.99999984]), 5.000000000000099, 9)
>>> t_grid, t_min
(0.011931600000025355, 0.0007411000001411594)
```

(Python 3.14 / scipy 1.18.0 실측. `timeit`은 실행할 때마다 값이 흔들리는데, 이 환경에서 여러 번 다시 재봐도 대략 16~22배 사이에서 왔다 갔다 했다 — "약 20배"라고 뭉뚱그리는 게 정직하다.) 격자 탐색은 $200 \times 200 = 40{,}000$ 번 함수를 평가해서 소수점 두 자리 정밀도밖에 못 얻는다. `minimize` 는 **9번** 평가로 소수점 일곱 자리까지 정확한 답을 낸다. 약 20배 더 빠르면서 정밀도는 비교가 안 될 정도로 높다.

이 차이가 나는 이유는 알고리즘 자체가 다르기 때문이다. 격자 탐색은 함수의 모양에 대해 아무것도 가정하지 않고 무작정 다 찍어 본다. `minimize` 의 기본 방법(BFGS)은 **그래디언트**(기울기) 정보를 이용해서 "내리막 방향"을 계산하고, 그 방향으로만 이동한다. `res.jac` 를 보면 이 방법이 그래디언트를 근사로 계산했다는 걸 알 수 있다.

```pyrepl
>>> res.jac
array([5.36441803e-07, 3.57627869e-07])
```

거의 0에 가깝다. 최솟값에서는 그래디언트가 0이라는 미적분의 기본 사실을 그대로 이용한 것이다.

::: note 여러 알고리즘 중에서 고른다
`method` 인자로 알고리즘을 바꿀 수 있다. 매끄러운 함수는 `"BFGS"`(기본값), 제약 조건이 있으면 `"SLSQP"` 나 `"trust-constr"`, 그래디언트를 계산하기 힘들면 `"Nelder-Mead"`(그래디언트 없이 심플렉스로 탐색). 어떤 문제냐에 따라 적절한 방법이 다르다는 게 SciPy가 "하나의 만능 함수"가 아니라 **알고리즘 라이브러리**인 이유다.
:::

::: cote 코딩테스트에서의 쓸모
매개변수 탐색(파라메트릭 서치) 문제에서 목적함수가 볼록(convex)하고 미분 가능하다면 `scipy.optimize.minimize_scalar` 나 `brentq` 로 이분 탐색보다 빠르게 답을 낼 수 있다. 다만 코딩테스트 환경에 SciPy가 없는 경우가 많으니 [7.5 이분 탐색](#/binary-search)의 직접 구현이 여전히 기본기다.
:::

## 보간: scipy.interpolate

**보간**(interpolation)은 알고 있는 점들 사이의 값을 추정하는 것이다. 센서에서 10Hz로 값을 받았는데 그 사이 시점의 값이 필요하다거나, 실험 데이터가 듬성듬성해서 매끄러운 곡선이 필요할 때 쓴다.

```pyrepl
>>> import numpy as np
>>> from scipy import interpolate
>>> x = np.linspace(0, 10, 11)
>>> y = np.sin(x)
>>> f_linear = interpolate.interp1d(x, y)
>>> f_cubic = interpolate.interp1d(x, y, kind="cubic")
>>> xnew = np.array([2.5, 5.5, 8.5])
>>> np.sin(xnew)                     # 진짜 값
array([ 0.59847214, -0.70554033,  0.79848711])
>>> f_linear(xnew)                   # 직선으로 이은 근사
array([ 0.52520872, -0.61916989,  0.70073837])
>>> f_cubic(xnew)                    # 3차 곡선으로 이은 근사
array([ 0.59820591, -0.70317713,  0.7927072 ])
```

선형 보간은 오차가 크다(0.598 대신 0.525). 점과 점 사이를 직선으로 잇기 때문에, `sin` 처럼 휘어진 곡선에서는 곡률을 놓친다. 3차 보간은 훨씬 정확하다(0.5982 대 실제 0.5985) — 인접한 네 점을 이용해 3차 다항식 조각을 이어 붙이면서 **1차 미분까지 연속**이 되게 만들기 때문이다.

최신 SciPy에서는 3차 보간에 `CubicSpline` 을 쓰는 걸 권장한다. 값뿐 아니라 미분까지 바로 뽑을 수 있어서 더 유용하다.

```pyrepl
>>> cs = interpolate.CubicSpline(x, y)
>>> cs(xnew)
array([ 0.59820591, -0.70317713,  0.7927072 ])
>>> cs(xnew, 1)                       # 1차 미분(도함수) 값
array([-0.80491328,  0.71035787, -0.60697733])
>>> np.cos(xnew)                      # sin의 도함수는 cos, 실제 값과 비교
array([-0.80114362,  0.70866977, -0.6020119 ])
```

`CubicSpline` 은 스플라인을 **다항식 계수 형태로 저장**하고 있어서 값뿐 아니라 임의 차수의 미분·적분까지 그 계수로부터 바로 계산해 낸다. 매번 유한차분으로 근사하는 것보다 정확하고 빠르다.

::: warn 외삽은 위험하다
보간 함수에 원래 데이터 범위(`[0, 10]`) 밖의 값을 넣으면 어떻게 될까. `interp1d` 는 기본적으로 에러를 던지고, `CubicSpline` 은 범위 밖을 다항식으로 그대로 연장해서 계산해 버린다. 둘 다 위험하다 — 데이터가 없는 구간의 곡선 모양은 순전히 추측이다. 범위를 반드시 확인하고, 필요하면 `bounds_error=False, fill_value="extrapolate"` 를 명시적으로 지정해서 그 위험을 인지한 채로 써라.
:::

## 신호 처리 맛보기: scipy.signal

`scipy.signal` 은 디지털 신호 처리 전체를 다루는 모듈이다. 그중 가장 흔히 쓰는 건 **필터링** — 신호에서 원하는 주파수 대역만 남기는 것이다.

잡음이 섞인 신호를 만들고 저역통과 필터로 걸러 본다.

```pyrepl
>>> import numpy as np
>>> from scipy import signal
>>> rng = np.random.default_rng(42)
>>> t = np.linspace(0, 1, 500)
>>> clean = np.sin(2 * np.pi * 5 * t)          # 5Hz 순수 신호
>>> noisy = clean + rng.normal(0, 0.5, size=t.shape)
>>> sos = signal.butter(4, 15, fs=500, btype="low", output="sos")
>>> filtered = signal.sosfilt(sos, noisy)
```

`butter(4, 15, fs=500, btype="low")` 는 **4차 버터워스 저역통과 필터**를 설계한다. 샘플링 주파수 500Hz 기준으로 15Hz 위쪽은 걸러내겠다는 뜻이다. `sos`(second-order sections) 형식으로 계수를 받는 게 요즘 권장되는 방식이다 — 옛날 방식인 `(b, a)` 계수는 필터 차수가 높아지면 부동소수점 오차로 수치적으로 불안정해질 수 있어서다.

결과를 원본과 비교한다.

```pyrepl
>>> np.abs(noisy - clean).mean()      # 필터링 전 평균 오차
0.381478147021468
>>> np.abs(filtered - clean).mean()   # sosfilt 후 평균 오차
0.5486476707470734
```

필터를 걸었는데 오차가 오히려 **커졌다**. 이게 함정이다.

::: danger sosfilt는 위상을 지연시킨다
`sosfilt` 는 **인과적**(causal) 필터다. 실시간 처리에서 쓰는 방식으로, 각 출력이 그 시점까지의 입력만으로 계산된다. 그 대가로 신호에 **위상 지연**(phase delay)이 생긴다 — 필터링된 파형이 원본보다 뒤처져서 나온다. 오차를 `clean` 과 시점 단위로 비교하면, 잡음은 줄었어도 파형이 밀려서 오차가 오히려 커진 것처럼 보인다.

실시간성이 필요 없고 전체 신호를 다 가지고 있다면 `sosfiltfilt` 를 쓴다. 신호를 정방향으로 한 번, 역방향으로 한 번 걸러서 **위상 지연을 상쇄**시킨다(zero-phase filtering).

```pyrepl
>>> filtered_zp = signal.sosfiltfilt(sos, noisy)
>>> np.abs(filtered_zp - clean).mean()
0.08537172915972922
```

같은 필터인데 함수만 바꿨더니 오차가 0.548 → 0.085로, 필터링 전(0.381)보다도 훨씬 정확해졌다. **실시간 스트리밍이면 `sosfilt`, 녹화된 데이터를 나중에 분석하는 거면 `sosfiltfilt`.** 이 둘을 헷갈리는 게 신호 처리 코드에서 실제로 자주 나는 버그다.
:::

## 희소 행렬: scipy.sparse

행렬의 대부분이 0인 경우가 있다. 그래프의 인접 행렬, 추천 시스템의 사용자-아이템 평점 행렬, 유한요소법의 계수 행렬 같은 것들이다. 이런 행렬을 **모든 칸에 메모리를 할당하는 밀집 행렬**로 저장하는 건 명백한 낭비다.

직접 실측해 본다. $2000 \times 2000$ 행렬에서 0.1%만 값이 있는 경우다.

```pyrepl
>>> import numpy as np
>>> from scipy import sparse
>>> n = 2000
>>> rng = np.random.default_rng(0)
>>> dense = np.zeros((n, n))
>>> idx = int(n * n * 0.001)
>>> rows = rng.integers(0, n, size=idx)
>>> cols = rng.integers(0, n, size=idx)
>>> dense[rows, cols] = rng.random(size=idx)
>>> sp = sparse.csr_matrix(dense)
>>> dense.nbytes
32000000
>>> sp.data.nbytes + sp.indices.nbytes + sp.indptr.nbytes
55968
>>> dense.nbytes / (sp.data.nbytes + sp.indices.nbytes + sp.indptr.nbytes)
571.7552887364208
```

(Python 3.14 / scipy 1.18.0 / Windows 실측. 배율은 밀집도에 따라 달라지지만, **밀집도가 낮을수록 압축률이 커진다**는 방향은 언제나 같다.) 밀집 행렬은 30.5 MB인데 희소 행렬(CSR 형식)은 약 55KB, **571배** 작다.

이게 가능한 이유는 CSR(Compressed Sparse Row) 형식의 저장 방식 때문이다. 세 개의 1차원 배열만 저장한다.

```text nolines
data     : 값이 있는 원소들 (0이 아닌 값만, 순서대로)
indices  : 그 값들의 열 번호
indptr   : 각 행이 data/indices의 어디서 시작하는지 가리키는 인덱스
```

0인 원소는 아예 저장하지 않는다. 실제로 값이 있는 원소(`nnz`, number of non-zeros)의 개수에 비례해서만 메모리를 쓴다.

```pyrepl
>>> sp.nnz
3997
```

메모리만 아끼는 게 아니라 **연산도 빠르다.** 0과의 곱셈·덧셈을 건너뛸 수 있기 때문이다.

```pyrepl
>>> import timeit
>>> v = rng.random(n)
>>> timeit.timeit(lambda: dense @ v, number=100)
0.013263800000004267
>>> timeit.timeit(lambda: sp @ v, number=100)
0.0005595999996330647
```

(이것도 `timeit` 실측값이라 실행마다 조금씩 다르다 — 이 환경에서 다시 재보면 20~33배 사이를 오갔다.) 행렬-벡터 곱이 약 24배 빠르다. [9.2 브로드캐스팅과 벡터화](#/broadcasting)에서 봤던 벡터화 원리와 같은 방향이다 — **하지 않아도 되는 계산은 아예 안 하는 것**이 최고의 최적화다. 다만 밀집도가 높아지면(예: 30% 이상) 희소 형식의 오버헤드(인덱스 저장 비용)가 오히려 손해가 될 수 있다. 희소 행렬은 "진짜로 대부분이 0일 때"만 쓰는 도구다.

::: note CSR 말고도 여러 형식이 있다
`csr_matrix` 는 행 단위 연산(행렬-벡터 곱, 행 슬라이싱)에 강하다. 열 단위 연산이 많으면 `csc_matrix`, 행렬을 조금씩 조립하는 중이면 `lil_matrix` 나 `coo_matrix` 로 만들고 계산 전에 `.tocsr()` 로 변환하는 게 정석이다. `lil_matrix` 에 원소를 하나씩 채우는 건 되지만, `csr_matrix` 에 원소를 하나씩 추가하는 건 매번 배열을 다시 만들어야 해서 매우 느리다.
:::

## 요약

- SciPy는 NumPy의 `ndarray` 위에서 동작하는 수치 알고리즘 모음이다. NumPy가 컨테이너, SciPy가 알고리즘이라는 역할 분담을 기억하라.
- `scipy.optimize.minimize` 는 그래디언트 기반으로 격자 탐색보다 훨씬 적은 함수 평가로 훨씬 정확한 최솟값을 찾는다.
- `scipy.interpolate` 의 `CubicSpline` 은 값뿐 아니라 미분·적분까지 다항식 계수에서 바로 계산한다. 원래 데이터 범위 밖의 외삽은 항상 위험하다.
- `scipy.signal` 의 `sosfilt` 는 인과적이라 위상 지연이 생긴다. 실시간이 아니면 `sosfiltfilt` 로 위상을 상쇄시켜라.
- `scipy.sparse` 는 0이 대부분인 행렬에서 메모리와 연산 시간을 밀집도에 비례해 절약한다. 밀집도가 낮을수록 이득이 커진다.
- 어떤 서브모듈을 쓰든 원리는 같다 — **하지 않아도 될 계산을 안 하는 것**이 빠른 코드의 본질이다. [5.1 측정 없이 최적화 없다](#/profiling)의 태도가 여기서도 그대로 적용된다.

::: quiz 연습문제
1. `scipy.optimize.minimize` 에 `method="Nelder-Mead"` 를 지정해서 이 절의 예제 함수를 최소화해 보라. `nfev` 가 기본 방법(BFGS)보다 많은가 적은가? 왜 그럴지 `res.jac` 유무로 추론해 보라.
2. `interpolate.CubicSpline` 으로 만든 곡선에, 원래 데이터 범위(`[0, 10]`) 밖의 값(예: `15`)을 넣어 보라. 에러 없이 값이 나오는가? 그 값을 신뢰할 수 있는가?
3. 이 절의 신호 처리 예제에서 `signal.sosfilt` 대신 `signal.sosfiltfilt` 를 쓰면 왜 위상 지연이 사라지는지, "정방향 한 번 + 역방향 한 번"이 어떻게 지연을 상쇄하는지 설명해 보라.
4. `n=2000` 행렬에서 밀집도를 0.001(0.1%) 대신 0.3(30%)으로 바꿔서 직접 실행해 보라. 희소 행렬이 여전히 밀집 행렬보다 메모리를 적게 쓰는가? 압축률이 어떻게 변하는지 측정하라.
5. `scipy.sparse.csr_matrix` 에 원소를 하나씩 추가하는 것이 왜 느린지, [1.3 시퀀스](#/sequences)에서 배운 리스트의 증폭(over-allocation) 전략과 비교해서 설명해 보라.
:::

**다음 절**: [9.9 matplotlib과 시각화](#/matplotlib) — 지금까지 계산한 숫자들을 눈으로 확인하는 법.
