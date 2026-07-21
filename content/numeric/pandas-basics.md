# 9.5 pandas 기초

::: lead
NumPy 배열은 빠르지만 다루기 불편하다. 행마다 이름이 다른 데이터, 군데군데 비어 있는 값, 서로 다른 타입의 열을 한 표에 담는 일은 ndarray의 영역이 아니다. pandas는 그 위에 **라벨이 붙은 표**를 얹는다. 이 절에서는 Series와 DataFrame의 진짜 정체, `loc`와 `iloc`가 왜 다른 질문인지, 결측치를 다루는 세 가지 함수, 그리고 pandas 3.0이 Copy-on-Write를 기본으로 삼으면서 무엇이 실제로 달라졌는지를 직접 실행해서 확인한다.
:::

## Series — 값에 인덱스를 붙인 것

[9.1 NumPy](#/numpy-basics)의 ndarray를 떠올려 보자. 원소는 있지만 "몇 번째 원소인가"만 알 수 있다. Series는 여기에 **이름표**를 붙인다.

```pyrepl
>>> import pandas as pd
>>> s = pd.Series([10, 20, 30], index=["a", "b", "c"])
>>> s
a    10
b    20
c    30
dtype: int64
>>> s.index
Index(['a', 'b', 'c'], dtype='str')
>>> s["b"]
20
```

Series는 **NumPy 배열 하나 + 인덱스 배열 하나**를 감싼 것뿐이다. 실제로 `.values`로 꺼내면 진짜 ndarray가 나온다. 산술 연산, 브로드캐스팅, dtype — [9.2 브로드캐스팅](#/broadcasting)에서 본 규칙이 내부에서 그대로 작동한다. pandas가 얹은 건 인덱스로 값을 찾는 기능과, 인덱스를 기준으로 정렬해 맞추는 자동 정렬(align) 뿐이다.

## DataFrame — Series를 열로 모은 표

```pyrepl
>>> df = pd.DataFrame({
...     "name": ["철수", "영희", "민수"],
...     "age": [25, 30, 22],
...     "score": [88.5, 92.1, 79.3],
... })
>>> df
  name  age  score
0   철수   25   88.5
1   영희   30   92.1
2   민수   22   79.3
>>> df.index
RangeIndex(start=0, stop=3, step=1)
>>> df.dtypes
name         str
age        int64
score    float64
dtype: object
```

**DataFrame은 열마다 별개의 dtype을 가진 Series의 묶음**이다. 행 방향으로는 표처럼 보이지만, 실제 메모리는 열 단위로 관리된다. 그래서 "행 하나를 가져온다"는 사실 여러 dtype이 섞인 Series를 새로 조립하는 작업이고, "열 하나를 가져온다"는 그냥 이미 있는 Series를 반환하는 작업이다. 후자가 훨씬 싸다.

::: note dtype이 `str`로 나온다 — object가 아니다
pandas 2.x까지는 문자열 열의 dtype이 `object`였다. **pandas 3.0부터는 기본이 `str`이다** (실측: pandas 3.0.3). `pd.options.future.infer_string`이 3.0에서 `True`로 고정됐고, 내부적으로는 `pandas.StringDtype`이다.

```pyrepl
>>> s = pd.Series(["a", "b", "c"])
>>> s.dtype
str
>>> type(s.dtype)
<class 'pandas.StringDtype'>
```

이건 장식이 아니다. `object` dtype은 "파이썬 객체에 대한 포인터 배열"이라 문자열이든 정수든 뭐든 섞여도 받아준다. 대신 원소마다 별도의 파이썬 `str` 객체를 참조하느라 캐시 지역성이 나쁘고 메모리를 많이 먹는다. 전용 문자열 dtype은 값이 실제로 문자열이라는 보장을 얻는 대신, 향후 pandas가 더 촘촘한 내부 표현(Arrow 기반 등)으로 갈아 끼울 여지를 준다. 지금은 여전히 파이썬 문자열마다 하나씩이라 메모리 이득은 크지 않지만(뒤의 memory_usage 참고), **`object`라고 쓰지 않는 이상 뒤섞인 타입이 실수로 들어갈 일이 줄었다**는 게 실질적인 이득이다.
:::

## `loc` 대 `iloc` — 라벨이냐 위치냐

여기서 초심자가 가장 많이 헤맨다. **둘은 완전히 다른 질문에 답한다.**

- **`loc`** — "이 **라벨**(인덱스 값)을 가진 행/열은?"
- **`iloc`** — "이 **위치**(0부터 세는 정수)에 있는 행/열은?"

인덱스가 정수가 아니면 헷갈릴 일이 없다. 문제는 **인덱스 자체가 정수일 때**다.

```pyrepl
>>> df2 = pd.DataFrame({"x": [1, 2, 3]}, index=[10, 20, 30])
>>> df2
    x
10  1
20  2
30  3
>>> df2.loc[10]         # 라벨 10을 가진 행
x    1
Name: 10, dtype: int64
>>> df2.iloc[0]         # 0번째 위치의 행 — 우연히 같은 값이다
x    1
Name: 10, dtype: int64
>>> df2.iloc[10]        # 위치 10은 없다 — 행이 3개뿐
Traceback (most recent call last):
  ...
IndexError: single positional indexer is out-of-bounds
```

`df2.loc[10]`과 `df2.iloc[0]`이 우연히 같은 값을 내놓아서 둘이 같은 것처럼 보인다. **정렬하면 바로 갈라진다.**

```pyrepl
>>> df3 = df2.sort_index(ascending=False)
>>> df3
    x
30  3
20  2
10  1
>>> df3.loc[10].values          # 라벨 10을 계속 따라간다
[1]
>>> df3.iloc[0].values          # 0번째 위치는 이제 라벨 30이다
[3]
```

**`loc`는 데이터가 어떻게 재배열되든 라벨을 추적한다. `iloc`는 순서만 본다.** 정렬, 필터링, 병합을 거친 뒤에는 인덱스가 원래 순서와 어긋나 있는 경우가 흔하므로, "몇 번째 행을 원하는가"가 아니라 "무엇을 원하는가"부터 자문해야 한다.

### 슬라이싱에서도 다르다

```pyrepl
>>> df4 = pd.DataFrame({"v": range(5)}, index=list("abcde"))
>>> df4.loc["b":"d"]      # 라벨 슬라이스 — 양 끝 포함
   v
b  1
c  2
d  3
>>> df4.iloc[1:3]         # 위치 슬라이스 — 파이썬 관례대로 끝 제외
   v
b  1
c  2
```

`loc`의 슬라이스는 **양 끝을 포함**한다. 이건 파이썬 리스트나 `iloc`의 관례와 반대다. 라벨은 "값"이라서 끝 라벨도 결과에 있어야 자연스럽다는 게 pandas의 판단이다. 이 비대칭을 외워 둬라. 실전에서 자주 틀리는 지점이다.

::: cote 코딩테스트·데이터 처리에서
`df.loc[condition, "col"]`처럼 **불리언 마스크와 열 이름을 같이 쓸 때는 `loc`를 쓴다.** `iloc`는 정수 위치만 받으므로 불리언 조건이나 라벨 이름을 넣으면 에러가 나거나(구버전에서는 경고 없이 다른 값을 골랐다) 최소한 의도가 흐려진다.

```python
df.loc[df["age"] > 25, "name"]   # ✅ 조건에 맞는 행의 name 열
df.iloc[df["age"] > 25, 0]       # ❌ iloc는 불리언 Series를 못 받는다
```
:::

## 불리언 인덱싱

`df["age"] > 25`는 그 자체로 `bool` 값을 담은 Series다. 이걸 다시 `df[...]`에 넣으면 `True`인 행만 남는다.

```pyrepl
>>> df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 20, 30, 40, 50]})
>>> mask = df["a"] > 2
>>> mask
0    False
1    False
2     True
3     True
4     True
Name: a, dtype: bool
>>> df[mask]
   a   b
2  3  30
3  4  40
4  5  50
```

이 원리는 [9.1 NumPy](#/numpy-basics)의 불리언 마스킹과 정확히 같다. 여러 조건을 합칠 때는 파이썬의 `and`/`or`가 아니라 **`&`/`|`를 쓰고, 각 조건을 괄호로 감싼다.** 연산자 우선순위 때문에 괄호를 빼먹으면 엉뚱하게 파싱된다.

```python
df[(df["a"] > 2) & (df["b"] < 50)]    # ✅
df[df["a"] > 2 & df["b"] < 50]        # ❌ & 가 > 보다 먼저 묶인다
```

## 결측치 — `isna`, `fillna`, `dropna`

실제 데이터는 구멍이 있다. pandas는 `NaN`(부동소수점 전용 결측 표시)과 `None`을 모두 결측으로 취급한다.

```pyrepl
>>> import numpy as np
>>> df = pd.DataFrame({
...     "a": [1, np.nan, 3, None],
...     "b": ["x", "y", None, "w"],
... })
>>> df
     a    b
0  1.0    x
1  NaN    y
2  3.0  NaN
3  NaN    w
>>> df.isna()
       a      b
0  False  False
1   True  False
2  False   True
3   True  False
>>> df.isna().sum()
a    2
b    1
dtype: int64
```

세 함수의 역할이 갈린다.

- **`isna()`** — 어디가 비었는지 **찾는다**. 값은 안 바꾼다.
- **`dropna()`** — 결측이 있는 **행(또는 열)을 통째로 버린다**.
- **`fillna()`** — 결측을 **다른 값으로 채운다**.

```pyrepl
>>> df.dropna()                          # a나 b 중 하나라도 NaN이면 행 삭제
     a  b
0  1.0  x
>>> df.dropna(subset=["a"])              # a만 검사
     a    b
0  1.0    x
2  3.0  NaN
>>> df.fillna({"a": 0, "b": "missing"})  # 열마다 다른 값으로 채움
     a        b
0  1.0        x
1  0.0        y
2  3.0  missing
3  0.0        w
>>> df["a"].fillna(df["a"].mean())       # 평균으로 채우는 흔한 패턴
0    1.0
1    2.0
2    3.0
3    2.0
Name: a, dtype: float64
```

::: warn dropna는 기본이 "행 전체 삭제"다
`dropna()`는 기본값이 `how="any", axis=0`이다. **열 하나만 결측이어도 그 행 전체가 날아간다.** 열이 10개인데 그중 하나만 가끔 비어 있어도 그 행 전체가 사라져서, 생각보다 훨씬 많은 데이터를 잃을 수 있다. `subset`으로 검사 대상 열을 좁히거나, `how="all"`(모든 열이 비었을 때만 삭제)을 검토하라.
:::

## pandas 3.0의 Copy-on-Write — 무엇이 실제로 바뀌었나

pandas 2.x 시절, 아래 코드는 악명 높은 `SettingWithCopyWarning`을 냈다.

```python
sub = df[df["a"] > 2]
sub["b"] = 0     # 2.x: 경고. sub가 df의 뷰인지 복사본인지 불확실했다
```

문제의 근원은 **인덱싱 결과가 뷰인지 복사본인지 pandas 내부 최적화에 따라 달라졌다는 것**이다. 어떨 때는 원본이 바뀌고, 어떨 때는 안 바뀌고, 어느 쪽이든 경고만 뜨고 실행은 됐다. 재현이 안 되는 버그의 단골 원인이었다.

**pandas 3.0부터 Copy-on-Write(CoW)가 항상 켜져 있다.** 끌 수도 없다. 실제로 꺼보려 하면 경고가 뜬다.

```pyrepl
>>> pd.set_option("mode.copy_on_write", True)
<stdin>:1: Pandas4Warning: The 'mode.copy_on_write' option is deprecated.
Copy-on-Write can no longer be disabled (it is always enabled with pandas >= 3.0),
and setting the option has no impact. This option will be removed in pandas 4.0.
```

CoW의 규칙은 하나다. **인덱싱이나 슬라이싱의 결과는 항상 "지연된 복사본"으로 취급한다. 실제 메모리 복사는 그 결과에 뭔가를 쓰려는 순간에만 일어난다.** [1.1 객체·이름·참조](#/objects-names)에서 본 "대입은 이름표를 붙이는 행위"라는 원칙과 결이 같다 — 읽기만 할 때는 굳이 복사하지 않다가, 변경이 필요해지는 시점에만 값을 나눈다.

```pyrepl
>>> df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 20, 30, 40, 50]})
>>> sub = df[df["a"] > 2]
>>> sub["b"] = 0                # 경고 없음. CoW 덕분에 sub는 이미 별개다
>>> sub
   a  b
2  3  0
3  4  0
4  5  0
>>> df                          # 원본은 안전하다
   a   b
0  1  10
1  2  20
2  3  30
3  4  40
4  5  50
```

`SettingWithCopyWarning`이라는 이름 자체는 사라졌다. `sub`는 처음부터 독립된 복사본으로 취급되므로 **애매할 이유가 없어졌기 때문**이다. 하지만 진짜 위험한 패턴 하나는 여전히 남아 있고, 경고의 정체도 겉보기와 다르다.

```pyrepl
>>> df[df["a"] > 2]["b"] = 999
pd_check.py:1: ChainedAssignmentError: A value is being set on a copy of a DataFrame or Series
through chained assignment.
Such chained assignment never works to update the original DataFrame or Series,
because the intermediate object on which we are setting values always behaves
as a copy (due to Copy-on-Write).
Try using '.loc[row_indexer, col_indexer] = value' instead, ...
>>> # 위 줄이 출력된 뒤에도 프로그램은 그대로 계속 실행된다 — 예외가 아니다
```

`df[조건]["b"] = 값`처럼 **대괄호를 연달아 쓰는 연쇄 대입(chained assignment)**은 이름은 `ChainedAssignmentError`이지만 실측 결과 **예외가 아니라 경고**다. 위에 보이는 `파일이름:줄번호: ChainedAssignmentError: 메시지` 형태 자체가 파이썬 `warnings` 모듈이 찍는 표준 포맷이지 트레이스백이 아니다. `try/except Exception`으로 감싸도 아무것도 잡히지 않고 코드는 끝까지 실행되며, `df`도 (예상대로) 바뀌지 않는다 — 다만 그 이유는 "예외로 막혀서"가 아니라 "연쇄 대입이 애초에 임시 복사본에만 적용되고, pandas는 경고만 낸 뒤 넘어가기 때문"이다. `warnings.catch_warnings(record=True)`로 감싸면 실제로 `category`가 `pandas.errors.ChainedAssignmentError`인 경고 1건이 잡힌다. `pd.errors.ChainedAssignmentError.__mro__`를 찍어 보면 확실해진다.

```pyrepl
>>> pd.errors.ChainedAssignmentError.__mro__
(<class 'pandas.errors.ChainedAssignmentError'>, <class 'Warning'>,
 <class 'Exception'>, <class 'BaseException'>, <class 'object'>)
```

`ChainedAssignmentError`는 `Exception`이 아니라 **`Warning`의 서브클래스**다. pandas는 이걸 `raise`가 아니라 `warnings.warn()`으로 내보낸다. 즉 이름에 `Error`가 붙어 있어서 예외처럼 보이지만, pandas 3.0.3의 실제 동작은 "이름만 Error, 실질은 경고"다. `pandas.errors.SettingWithCopyWarning`이라는 옛 이름 자체는 없어졌다.

```pyrepl
>>> hasattr(pd.errors, "SettingWithCopyWarning")
False
>>> hasattr(pd.errors, "ChainedAssignmentError")
True
```

(pandas 3.0.3 / Windows 실측)

::: danger 연쇄 대입은 왜 애초에 안 되는가
`df[조건]["b"] = 999`는 두 단계로 쪼개진다.

1. `tmp = df[조건]` — CoW 하에서 이건 **항상 복사본**을 반환한다.
2. `tmp["b"] = 999` — 그 복사본을 수정한다. `df`에는 아무 영향이 없다.

이 순서가 파이썬 문법 자체에 박혀 있다. `a[b][c] = d`는 `a[b]`를 먼저 평가하고 그 결과에 `[c] = d`를 적용하는 것이지, `a`에게 "b, c 위치에 d를 넣어줘"라고 한 번에 요청하는 게 아니다. CoW 이전에는 1번의 결과가 운 좋게 뷰였다면 동작하는 것**처럼 보였을 뿐**이다. CoW는 그 우연을 없앴다. pandas는 "이건 절대 성공할 수 없다"는 사실을 경고로 알려주지만, 실행 자체를 멈춰 세우지는 않는다 — 그래서 이 패턴은 **코드가 에러 없이 넘어가면서도 원하는 대입은 조용히 실패하는**, 오히려 더 알아채기 힘든 함정이다. 경고를 예외로 승격시켜 확실히 잡고 싶다면 `warnings.simplefilter("error", pd.errors.ChainedAssignmentError)`를 걸어 두는 방법이 있다.

올바른 방법은 **행 조건과 열 선택을 한 번에** `loc`에 넘기는 것이다.

```python
df.loc[df["a"] > 2, "b"] = 999    # ✅ 한 단계 — 원본이 실제로 바뀐다
```
:::

전체 슬라이스도 CoW의 영향을 받는다.

```pyrepl
>>> view = df[:]
>>> view is df
False
>>> view.iloc[0, 0] = -1
>>> df                      # view를 고쳤는데 df는 그대로다
   a   b
0  1  10
...
```

`df[:]`는 겉보기엔 "전체를 그대로 가리키는 뷰"처럼 보이지만, CoW 하에서는 쓰기가 일어나는 순간 즉시 갈라진다. **"이 변수가 원본의 뷰냐 복사냐"를 추측할 필요가 없어졌다는 게 핵심이다.** 읽기만 하면 성능은 뷰와 같고(불필요한 복사를 안 한다), 쓰기를 하면 항상 안전하게 분리된다. [9.1 NumPy](#/numpy-basics)의 슬라이싱이 항상 뷰(공유)인 것과 정확히 대비된다 — NumPy는 성능을 위해 공유를 기본으로 하고 예측 가능성은 프로그래머 책임이지만, pandas 3.0은 안전을 기본으로 하고 필요할 때만 진짜 복사를 한다.

## dtype과 메모리 사용량

DataFrame의 메모리는 dtype 선택에 크게 좌우된다. `memory_usage`로 직접 확인할 수 있다.

```pyrepl
>>> df = pd.DataFrame({
...     "id": np.arange(1_000_000),
... })
>>> df.memory_usage(deep=True)
Index        132
id       8000000
dtype: int64
```

100만 행의 `int64` 열 하나가 8,000,000바이트(≈7.6MB)다 — 원소당 8바이트, 정확히 예상대로다. 값의 범위가 좁다면 더 작은 정수형으로 다운캐스트해서 줄일 수 있다.

```pyrepl
>>> df["id_small"] = df["id"].astype(np.int32)   # -21억~21억이면 충분
>>> df["id_tiny"] = (df["id"] % 100).astype(np.int8)  # 0~99
>>> df.memory_usage(deep=True)
Index           132
id          8000000
id_small    4000000
id_tiny     1000000
dtype: int64
```

`int64` → `int32`는 절반, → `int8`은 1/8로 줄었다. 이건 [9.1 NumPy](#/numpy-basics)에서 본 dtype별 고정 바이트 크기가 그대로 이어지는 것이다. pandas 열의 숫자 dtype은 결국 NumPy 배열이기 때문이다.

문자열과 카테고리 열은 이야기가 다르다.

```pyrepl
>>> df2 = pd.DataFrame({
...     "cat": np.random.choice(["A", "B", "C"], 100_000),
... })
>>> df2.memory_usage(deep=True)
Index         132
cat       5000000
dtype: int64
>>> df2["cat_cat"] = df2["cat"].astype("category")
>>> df2.memory_usage(deep=True)
Index            132
cat          5000000
cat_cat       100150
dtype: int64
```

(numpy 2.5.1 / pandas 3.0.3 실측)

`str` dtype 10만 개가 500만 바이트인데, `category`로 바꾸면 10만 배 좁아진 게 아니라 **약 50배** 줄어 10만 바이트 남짓이 된다. 이유는 명확하다. `category`는 실제 문자열을 딱 3종류(`A`, `B`, `C`)만 한 번씩 저장해 두고, 각 행은 그 3개 중 몇 번째인지를 가리키는 **작은 정수 코드**로 저장한다. 값의 종류가 적고 반복이 많은 열(성별, 지역, 등급 같은 범주형 데이터)에서 `category`는 메모리와 속도 양쪽에서 이득이다. `deep=True`를 빼면 `memory_usage`는 문자열이 실제로 차지하는 파이썬 객체 크기를 세지 않고 포인터 크기만 세서 **훨씬 작게, 그리고 틀리게** 나온다. 문자열·object 열이 섞인 DataFrame에서는 항상 `deep=True`를 써라.

::: perf memory_usage(deep=True)는 그 자체로 비용이 든다
`deep=True`는 각 파이썬 문자열 객체의 실제 크기를 `sys.getsizeof`로 하나하나 재는 것과 같다. 열이 매우 크면(수천만 행) 이 호출 자체가 수초씩 걸릴 수 있다. 습관적으로 매번 부르지 말고, 메모리 문제를 조사할 때만 써라. 자세한 프로파일링 도구는 [5.2 메모리 모델](#/memory)에서.
:::

::: hist 왜 결측 가능한 정수형(`Int64`)이 따로 있는가
NumPy의 `int64`는 결측값을 표현할 방법이 없다. `NaN`은 `float64` 전용 비트 패턴이기 때문이다. 그래서 정수 열에 결측이 하나라도 섞이면 전통적인 pandas는 열 전체를 `float64`로 **자동 승격**시켰다.

```pyrepl
>>> s = pd.Series([1, 2, None])
>>> s.dtype, s.tolist()
(dtype('float64'), [1.0, 2.0, nan])
```

`1`이 `1.0`이 되는 건 데이터 손실은 아니지만, "이 열은 정수다"라는 의도가 흐려진다. pandas는 이 문제를 풀기 위해 **결측을 지원하는 확장 정수형** `Int64`(대문자로 시작, NumPy의 소문자 `int64`와 다르다)를 도입했다. 내부적으로 값 배열과 별개의 불리언 마스크를 함께 들고 다니며, 결측은 `pd.NA`로 표시한다.

```pyrepl
>>> pd.array([1, 2, None], dtype="Int64")
<IntegerArray>
[1, 2, <NA>]
Length: 3, dtype: Int64
```

기본으로 켜져 있지 않은 이유는 성능이다. 마스크를 매 연산마다 함께 계산해야 해서 순수 NumPy `int64` 연산보다 느리다. 정수인데 결측이 있을 수 있다는 게 확실할 때만 명시적으로 `dtype="Int64"`를 선택하라.
:::

## 요약

- Series는 "값 배열 + 인덱스 배열"이고, DataFrame은 dtype이 제각각인 Series들의 묶음이다.
- **`loc`는 라벨, `iloc`는 위치.** 정수 인덱스를 쓸 때 반드시 구분해야 하고, 정렬·필터 후에는 둘의 결과가 갈린다. `loc`의 슬라이스는 끝을 포함하고 `iloc`는 포함하지 않는다.
- 불리언 인덱싱은 `&`/`|`와 괄호를 쓴다. `and`/`or`가 아니다.
- 결측 처리는 `isna`(찾기), `dropna`(버리기), `fillna`(채우기) 세 가지로 나뉜다. `dropna`는 기본이 "행 전체 삭제"라 생각보다 많이 지운다.
- **pandas 3.0부터 Copy-on-Write가 항상 켜져 있다.** `SettingWithCopyWarning`이라는 이름은 사라지고 연쇄 대입(`df[cond]["col"] = v`)은 `ChainedAssignmentError`를 낸다 — 다만 이름과 달리 실제로는 `Warning`의 서브클래스라 실행이 멈추지 않고 대입만 조용히 실패한다. 항상 `df.loc[cond, "col"] = v`로 한 단계에 쓴다.
- dtype은 메모리를 좌우한다. 정수는 범위에 맞게 다운캐스트하고, 값의 종류가 적은 문자열 열은 `category`로 바꿔라. 결측 있는 정수는 `Int64`.

::: quiz 연습문제
1. 다음 코드의 결과를 예측한 뒤 실행해서 확인하라.

   ```python
   df = pd.DataFrame({"v": [10, 20, 30]}, index=[5, 3, 1])
   print(df.loc[3])
   print(df.iloc[1])
   ```

2. `df.loc[df["score"] < 60, "grade"] = "F"`와 `df[df["score"] < 60]["grade"] = "F"`는 겉보기에 비슷하다. pandas 3.0에서 각각 실행하면 무슨 일이 일어나는지, 그리고 왜 그런지 설명하라.

3. 100만 행짜리 DataFrame에 성별 열(`"M"`/`"F"`만 있는 문자열)이 있다. `astype("category")` 전후로 `memory_usage(deep=True)`를 측정하고, 왜 그만큼 차이가 나는지 설명하라.

4. `pd.Series([1, 2, None])`의 dtype과 `pd.array([1, 2, None], dtype="Int64")`의 dtype이 다른 이유를 설명하라. 각각에서 결측값은 어떻게 표시되는가?

5. `df[df["a"] > 2]`가 CoW 하에서 반환하는 것은 뷰인가 복사본인가? 그 답이 pandas 2.x 이전과 어떻게 달랐는지, 그리고 왜 그 차이가 `SettingWithCopyWarning`을 없앨 수 있게 했는지 설명하라.
:::

**다음 절**: [9.6 pandas 실전](#/pandas-advanced) — groupby, merge, 시계열, 그리고 실무에서 자주 걸리는 성능 함정.
