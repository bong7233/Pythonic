# 9.7 polars와 Apache Arrow

::: lead
[9.6 pandas 실전](#/pandas-advanced)까지 왔다면 pandas의 한계도 함께 느꼈을 것이다. `df.apply(lambda ...)` 는 왜 이렇게 느린가. 코어가 16개인 컴퓨터에서 왜 CPU 사용률은 계속 6%인가. 이 절은 그 답을 pandas 바깥에서 찾는다. **Arrow** 라는 컬럼 포맷과, 그 위에서 동작하는 **polars** 라는 엔진이다. pandas와 같은 일을 시켜서 실제로 몇 배 차이 나는지 이 절에서 직접 잰다.
:::

## pandas가 느려지는 지점

pandas 자체는 느리지 않다. `df["a"] + df["b"]` 처럼 NumPy 벡터화 연산으로 떨어지는 코드는 이미 빠르다. 문제는 그 바깥이다.

- **`apply(lambda ...)` 는 파이썬 반복문이다.** [1.3 시퀀스](#/sequences)에서 본 "파이썬 반복문이 느린 이유"가 여기서도 그대로 적용된다. 매 행마다 파이썬 함수 호출과 객체 생성이 일어난다.
- **pandas 연산 대부분은 싱글 스레드다.** 코어가 16개든 64개든 기본 연산 파이프라인은 하나만 쓴다.
- **연쇄된 연산마다 중간 결과를 전부 메모리에 만든다.** `df.filter(...).groupby(...).agg(...)` 를 쓰면 `filter` 결과 전체가 먼저 새 DataFrame으로 만들어지고, 그다음에야 `groupby` 가 시작된다. 최종적으로 필요 없는 계산도 일단 다 한다.

이 세 가지를 각각 겨냥해서 만들어진 게 Arrow와 polars다. 실측으로 먼저 감을 잡자.

```python title="apply 대 벡터화 대 polars"
import pandas as pd
import polars as pl
import time

pdf = pd.read_csv("bench_data.csv")     # 300만 행, qty·value·category·id 4열
pldf = pl.read_csv("bench_data.csv")

def pandas_apply():
    return pdf["qty"].apply(lambda x: "high" if x > 50 else "low")

def pandas_np_where():
    import numpy as np
    return np.where(pdf["qty"] > 50, "high", "low")

def polars_expr():
    return pldf.select(
        pl.when(pl.col("qty") > 50).then(pl.lit("high")).otherwise(pl.lit("low"))
    )
```

```pyrepl
>>> timeit(pandas_apply)          # 최소 실행 시간, 3회 반복
0.1921
>>> timeit(pandas_np_where)
0.0117
>>> timeit(polars_expr)
0.0017
```

(Python 3.14 / pandas 3.0.3 / polars 1.43.0 / Windows, 300만 행 CSV 기준 실측. 절대값과 정확한 배수는 CPU·메모리·당시 부하에 따라 달라진다 — 다른 컴퓨터에서 재현하면 배수가 달라질 수 있지만, "느림 순서"와 "자릿수 차이"는 그대로 재현된다.) `apply` 에서 NumPy 벡터화로만 바꿔도 **16배** 가까이, polars의 표현식 API로 가면 **100배** 넘게 빨라진다. 이 절의 목표는 이 격차가 어디서 나오는지 설명하는 것이다.

## Apache Arrow: 컬럼 포맷이라는 공통 언어

먼저 pandas가 데이터를 어떻게 들고 있는지부터 봐야 한다.

### pandas의 BlockManager

pandas DataFrame은 내부적으로 **BlockManager** 라는 구조로 열들을 관리한다. 같은 dtype인 열들을 묶어서 하나의 2차원 NumPy 배열(**Block**)로 저장한다.

```python title="BlockManager 들여다보기"
import pandas as pd

df = pd.DataFrame({
    "a": [1, 2, 3],       # int64
    "b": [1.0, 2.0, 3.0], # float64
    "c": ["x", "y", "z"], # str
    "d": [4, 5, 6],       # int64
})
print(df._mgr)
```

```text
BlockManager
Items: Index(['a', 'b', 'c', 'd'], dtype='str')
Axis 1: RangeIndex(start=0, stop=3, step=1)
ExtensionBlock: slice(2, 3, 1), 1 x 3, dtype: str
NumpyBlock: slice(1, 2, 1), 1 x 3, dtype: float64
NumpyBlock: slice(0, 6, 3), 2 x 3, dtype: int64
```

`a` 와 `d` 는 둘 다 int64라서 **한 블록에 합쳐졌다.** 문자열 열 `c` 는 pandas 3.0부터 기본 dtype이 `object` 가 아니라 **`str`** 로 바뀌었고, Arrow 기반의 `ExtensionBlock` 으로 저장된다. `df.dtypes` 를 찍어 보면 확인된다.

```pyrepl
>>> df.dtypes
a      int64
b    float64
c        str
d      int64
dtype: object
```

::: note pandas 3.0의 큰 변화: 문자열도 Arrow로
pandas 2.x까지는 문자열 열이 파이썬 `str` 객체를 가리키는 포인터 배열(`object` dtype)이었다. 문자열 하나하나가 별도의 파이썬 객체라 메모리도 많이 쓰고 캐시 지역성도 나빴다. pandas 3.0은 기본적으로 **PyArrow 기반 문자열 타입**을 쓴다. Arrow가 이제 옵션이 아니라 pandas 내부로 들어오고 있다는 뜻이다.
:::

BlockManager 방식의 문제는 **"열끼리 묶는 방법"이 pandas만의 내부 규약**이라는 점이다. 이 DataFrame을 다른 언어나 다른 도구(Rust, Java, Spark, DuckDB)로 넘기려면 pandas의 내부 구조를 이해하는 변환 코드가 따로 필요하다.

### Arrow: 언어 중립적인 컬럼 메모리 레이아웃

**Apache Arrow** 는 이 문제를 "다들 이 메모리 레이아웃 하나로 통일하자"는 규격으로 푼다. 열 하나는 다음 세 가지로 이뤄진다.

```text nolines
Arrow column (dtype: int64, 값 하나당 null 여부 비트 하나)
┌───────────────────────────────┐
│ validity bitmap               │  <- null 여부만 담는 비트맵
├───────────────────────────────┤
│ data buffer                   │  <- 실제 값이 연속으로 붙은 배열
│ [1, 2, 3, 4, 5, ...]           │
└───────────────────────────────┘
```

핵심은 **연속된 메모리에 같은 타입 값이 쭉 붙어 있다**는 것이다. 이건 NumPy 배열과 본질적으로 같은 아이디어이지만, Arrow는 이 레이아웃을 **언어와 프로세스 경계를 넘어 공유할 수 있는 표준 규격**으로 못 박았다. 그래서 다음이 가능해진다.

- **제로카피 교환.** 같은 메모리를 파이썬(polars, pandas), Rust, Java, C++가 복사 없이 그대로 읽는다.
- **null을 값과 분리해서 표현.** NumPy는 정수 배열에 결측치를 못 담아서 `float64` 로 승격시키는 편법을 쓴다([9.1 ndarray](#/numpy-basics)에서 다룬 dtype 문제). Arrow는 별도의 validity bitmap으로 null을 표시하므로 **정수 열도 결측치를 가질 수 있다.**
- **SIMD 친화적.** 같은 타입이 메모리에 쭉 이어져 있으니 CPU가 한 번에 여러 값을 처리하는 벡터 명령을 그대로 적용할 수 있다. [1.1 객체·이름·참조](#/objects-names)에서 본 "파이썬 리스트는 객체를 가리키는 포인터의 배열"이라는 사실과 정반대 극단에 있는 구조다.

```python title="polars DataFrame을 Arrow로, 복사 없이"
import polars as pl

pldf = pl.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]})
tbl = pldf.to_arrow()
print(tbl)
```

```text
pyarrow.Table
a: int64
b: double
----
a: [[1,2,3]]
b: [[1,2,3]]
```

polars는 **Arrow를 그대로 자신의 내부 메모리 포맷으로 쓴다.** pandas처럼 "가끔 Arrow를 경유하는" 게 아니라, polars 안의 모든 열이 처음부터 Arrow 배열이다. `to_arrow()` 가 사실상 뷰 변환에 가까운 이유가 이것이다 — [1.1절](#/objects-names)에서 본 "복사냐 참조냐"의 질문을 여기서도 그대로 물을 수 있다.

## 즉시 실행: DataFrame

polars의 `DataFrame` 은 pandas의 DataFrame과 감각적으로 비슷하다. **연산을 호출하는 즉시 실행**된다.

```python title="polars DataFrame 기초"
import polars as pl

df = pl.DataFrame({
    "category": ["A", "B", "A", "C"],
    "value": [10.5, 20.1, 30.0, 15.3],
    "qty": [3, 7, 2, 9],
})
print(df.schema)
```

```text
Schema({'category': String, 'value': Float64, 'qty': Int64})
```

인덱스가 없다는 점이 pandas와 다르다. pandas의 `Index` 는 강력하지만 [9.5 pandas 기초](#/pandas-basics)에서 봤듯 정렬·조인에서 은근한 함정이 되기도 한다. polars는 애초에 인덱스 개념을 없애고 열은 그냥 열, 순서는 그냥 행 순서로만 다룬다.

## 지연 실행: LazyFrame

polars의 진짜 무기는 `DataFrame` 이 아니라 **`LazyFrame`** 이다. 여기서 사고방식이 SQL 쿼리 플래너에 가까워진다.

```python title="즉시 실행 vs 지연 실행"
# 즉시 실행: read_csv 하는 순간 3,000,000행을 전부 메모리에 올린다
df = pl.read_csv("bench_data.csv")
result = df.filter(pl.col("qty") > 50).group_by("category").agg(pl.col("value").mean())

# 지연 실행: scan_csv는 아직 아무것도 읽지 않는다. "계획"만 세운다
lf = pl.scan_csv("bench_data.csv")
query = lf.filter(pl.col("qty") > 50).group_by("category").agg(pl.col("value").mean())
result = query.collect()   # 여기서 비로소 실행된다
```

`scan_csv` 는 파일을 열어 스키마만 확인하고 즉시 `LazyFrame` 을 돌려준다. `.filter()`, `.group_by()`, `.agg()` 를 아무리 이어 붙여도 **실제 계산은 `.collect()` 를 호출하는 순간까지 일어나지 않는다.** 그 사이에 polars는 전체 쿼리를 하나의 **실행 계획**으로 보고 최적화한다.

### `.explain()` 으로 최적화를 직접 본다

```python title="쿼리 계획 확인"
query = (
    pl.scan_csv("bench_data.csv")
    .filter(pl.col("qty") > 50)
    .group_by("category")
    .agg(pl.col("value").mean().alias("avg_value"))
    .sort("category")
)
print(query.explain(optimized=False))
print("---")
print(query.explain())   # optimized=True (기본값)
```

```text
SORT BY [col("category")]
  AGGREGATE[maintain_order: false]
    [col("value").mean().alias("avg_value")] BY [col("category")]
    FROM
    FILTER col("qty") > 50
    FROM
      Csv SCAN [bench_data.csv]
      PROJECT */4 COLUMNS
      ESTIMATED ROWS: 3704765
---
SORT BY [col("category")]
  AGGREGATE[maintain_order: false]
    [col("value").mean().alias("avg_value")] BY [col("category")]
    FROM
    simple π 2/2 ["category", "value"]
      Csv SCAN [bench_data.csv]
      PROJECT 3/4 COLUMNS
      SELECTION: col("qty") > 50
      ESTIMATED ROWS: 3704765
```

두 계획을 비교하면 optimizer가 한 일이 보인다.

- **projection pushdown** — 원래 코드는 `category`, `value`, `qty` 를 쓰지만 최종 결과에는 `id` 열이 필요 없다. optimizer는 이걸 알아채고 **CSV를 읽는 단계에서부터** `PROJECT 3/4 COLUMNS` 로 필요한 열만 골라 읽는다.
- **predicate pushdown** — `filter` 가 원래는 그룹화 *이전*에 별도 단계였는데, 최적화된 계획에서는 `SELECTION` 이 스캔 바로 다음, 즉 **가능한 한 이른 시점**으로 끌어올려졌다. 걸러질 행을 뒤에서 버리는 게 아니라 애초에 읽지 않는다.

### 컬럼 pruning의 위력: Parquet에서 확실히 보인다

pushdown 효과는 컬럼이 많고 컬럼 지향 파일 포맷(Parquet)일 때 극적으로 드러난다. 20개 열, 500만 행짜리 Parquet 파일에서 열 하나의 평균만 구해 보자.

```python title="eager 대 lazy — 열이 많은 Parquet"
def eager_full_then_select():
    df = pl.read_parquet("wide.parquet")           # 20개 열을 전부 읽는다
    return df.select(pl.col("col0").mean())

def lazy_scan_then_select():
    return pl.scan_parquet("wide.parquet").select(pl.col("col0").mean()).collect()
```

```pyrepl
>>> timeit(eager_full_then_select)
0.0860
>>> timeit(lazy_scan_then_select)
0.0057
```

(500만 행 × 20열 float64 Parquet, 약 768MB 기준 실측.) **15배** 차이가 난다. Parquet은 Arrow와 같은 철학의 컬럼 지향 파일 포맷이라, `scan_parquet` + `select` 조합에서는 필요한 열의 바이트만 디스크에서 읽어 온다. `read_parquet` 로 먼저 다 읽어버리면 이 이점이 사라진다.

::: tip 지연 실행이 이기는 상황
LazyFrame의 이득은 아래 세 조건이 겹칠 때 커진다.

1. **원본이 실제로 필요한 것보다 크다** — 열이 많거나(와이드 테이블), 필터로 걸러질 행이 많을 때.
2. **파일 포맷이 컬럼 지향이다** — Parquet, Arrow IPC. CSV는 행 지향이라 컬럼 pruning의 이득이 상대적으로 작다(그래도 predicate pushdown은 여전히 유효하다).
3. **파이프라인이 여러 단계다** — 중간 결과를 매번 완성된 DataFrame으로 만들지 않고 통째로 최적화하고 한 번에 실행(**query fusion**)하기 때문에, 단계가 많을수록 아낄 게 많아진다.

작은 CSV 하나를 그냥 한 번 읽고 끝내는 스크립트라면 `read_csv` 로 즉시 실행해도 차이는 미미하다.
:::

## 표현식 API: `pl.col` 의 사고방식

polars 코드가 pandas와 가장 다르게 느껴지는 지점이 표현식(**expression**)이다. `pl.col("qty")` 는 값이 아니라 **"qty 열에 대해 이런 계산을 하라"는 계획 조각**이다.

```python title="표현식은 조합된다"
result = df.select(
    pl.col("value").mean().alias("value_mean"),
    pl.col("value").std().alias("value_std"),
    (pl.col("qty") * pl.col("value")).sum().alias("total"),
    pl.when(pl.col("qty") > 50)
      .then(pl.lit("high"))
      .otherwise(pl.lit("low"))
      .alias("bucket"),
)
```

이 방식의 장점은 세 가지다.

1. **여러 계산을 한 번에 표현한다.** `select` 안의 표현식들은 서로 독립이라 polars가 **병렬로** 계산한다. pandas에서 `df["a"].mean()`, `df["a"].std()` 를 따로 호출하면 각각 별개의 파이썬 문장이고 순서대로 실행된다.
2. **행 단위 분기에 파이썬 함수가 필요 없다.** `pl.when/then/otherwise` 는 `apply(lambda x: ...)` 가 하던 일을 표현식으로 대체한다. 앞서 측정한 100배 넘는 차이가 여기서 나온다 — 파이썬 인터프리터가 300만 번 호출되는 대신, Rust로 짜인 벡터 연산 한 번으로 끝난다.
3. **최적화 대상이 된다.** `LazyFrame` 위에서 표현식을 쓰면 방금 본 pushdown 최적화가 표현식 단위로 적용된다. 표현식은 데이터가 아니라 **데이터에 대한 서술**이기 때문에 optimizer가 재배치할 수 있다.

::: cote 코딩테스트/데이터 처리 공통 원칙
`apply(lambda row: ...)` 를 보면 반사적으로 의심하라. pandas든 polars든 **행 단위로 파이썬 콜백을 부르는 순간 벡터화의 이점이 전부 사라진다.** 조건 분기는 `np.where`/`np.select`(pandas) 또는 `pl.when/then/otherwise`(polars)로, 집계는 내장 메서드로 표현할 수 있는지 먼저 찾아라. 정말 방법이 없을 때만 `apply` 로 물러난다.
:::

## 실측: 같은 작업, pandas와 polars

CSV 300만 행(약 92MB, `id`/`category`/`value`/`qty` 4열)에서 "수량이 50 초과인 행만 걸러 카테고리별 평균"을 구하는, 실무에서 흔한 파이프라인으로 정리해 비교한다.

```python title="파일 읽기부터 집계까지 전체 파이프라인"
def pandas_task():
    df = pd.read_csv("bench_data.csv")
    return df[df["qty"] > 50].groupby("category")["value"].mean()

def polars_eager_task():
    df = pl.read_csv("bench_data.csv")
    return df.filter(pl.col("qty") > 50).group_by("category").agg(pl.col("value").mean())

def polars_lazy_task():
    return (
        pl.scan_csv("bench_data.csv")
        .filter(pl.col("qty") > 50)
        .group_by("category")
        .agg(pl.col("value").mean())
        .collect()
    )
```

```pyrepl
>>> timeit(pandas_task)
0.5797
>>> timeit(polars_eager_task)
0.0369
>>> timeit(polars_lazy_task)
0.0461
```

(Windows / Python 3.14 / pandas 3.0.3 / polars 1.43.0, CSV 300만 행 실측. 절대값은 기기마다 다르지만 **자릿수 차이**는 재현된다.) polars가 **13~16배** 빠르다. 이미 메모리에 올라온 DataFrame에서 필터+집계 연산만 따로 떼어 재보면 격차가 좁아진다.

```pyrepl
>>> timeit(pandas_op_only, n=10)     # 이미 로드된 DataFrame에서 연산만
0.0616
>>> timeit(polars_op_only, n=10)
0.0070
>>> 0.0616 / 0.0070
8.8
```

**즉 격차는 두 군데서 온다.** (1) polars의 CSV 파서 자체가 훨씬 빠르고(Rust로 구현, 자동 스레드 병렬화), (2) 순수 연산 단계에서도 **표현식이 멀티스레드로 실행**되기 때문에 8~9배가 남는다. (이 두 숫자도 하드웨어와 그때그때 부하에 따라 흔들린다 — 다시 재보면 6배가 나올 수도, 13배가 나올 수도 있다. 그래도 "CSV 파싱 배수보다는 작지만 여전히 여러 배"라는 순서는 유지된다.)

```pyrepl
>>> pl.thread_pool_size()
16
```

이 컴퓨터의 논리 코어 수(16개)와 일치한다. pandas는 `groupby`/`agg` 같은 연산 대부분을 싱글 스레드로 처리하는 반면, polars는 별도 설정 없이 **가용 코어를 전부 쓴다.** [4장 동시성](#/concurrency-map)에서 다룰 GIL 이야기와 이어지는 지점이다 — polars의 실제 연산은 Rust로 구현되어 파이썬 GIL 바깥에서 돈다.

## 언제 pandas, 언제 polars

polars가 항상 정답은 아니다. 실무 판단 기준을 정리한다.

| 상황 | 선택 |
| --- | --- |
| 데이터가 수천~수만 행, 한 번 훑고 끝 | pandas로 충분. 생태계(플로팅, `scikit-learn` 입력 등)가 훨씬 넓다 |
| 수백만 행 이상, 파이프라인이 여러 단계 | polars — 특히 `LazyFrame` |
| 결과를 matplotlib/seaborn에 바로 넘겨야 함 | pandas가 여전히 편하다. 필요하면 polars 결과를 `.to_pandas()` 로 변환 |
| 파일이 메모리보다 큼 | polars의 스트리밍 엔진(`collect(engine="streaming")`) — pandas는 청크 읽기를 직접 짜야 한다 |
| 팀 전체가 pandas API에 익숙 | 급하게 바꾸지 마라. 병목이 실제로 측정됐을 때 바꿔라([5.1 프로파일링](#/profiling)) |

**polars와 pandas는 적이 아니다.** 둘 다 Arrow를 점점 더 깊이 받아들이고 있고(`pd.read_parquet` 도 내부적으로 Arrow를 거친다), `.to_pandas()`/`pl.from_pandas()` 로 거의 제로카피에 가깝게 오갈 수 있다. 무거운 전처리는 polars로 빠르게 끝내고, 마지막 시각화나 팀 관례에 맞춘 API가 필요할 때만 pandas로 바꾸는 조합이 실전에서 흔하다.

## 요약

- pandas의 BlockManager는 같은 dtype 열을 묶어 저장한다. 열끼리 다른 라이브러리와 데이터를 주고받으려면 변환이 필요했다.
- **Apache Arrow** 는 언어 중립적인 컬럼 메모리 레이아웃 규격이다. 같은 타입 값이 연속으로 붙어 있고, null은 별도 비트맵으로 표현해 SIMD·제로카피 교환에 유리하다. pandas 3.0의 문자열 dtype도 이제 Arrow 기반이다.
- polars는 처음부터 Arrow를 내부 포맷으로 쓴다. `DataFrame` 은 pandas처럼 **즉시 실행**되고, `LazyFrame` 은 `scan_*` + `.collect()` 로 **지연 실행**되며 그 사이에 predicate/projection pushdown 같은 쿼리 최적화가 일어난다.
- `pl.col(...)` 표현식은 값이 아니라 계산 계획이다. 여러 표현식이 병렬로 계산되고, `when/then/otherwise` 가 행 단위 파이썬 콜백(`apply`)을 대체한다.
- 실측: 필터+그룹화 파이프라인에서 polars가 pandas보다 13~16배 빨랐다(측정 환경에 따라 더 벌어질 수도 있다). 그중 상당 부분은 빠른 CSV 파서에서, 나머지는 멀티스레드 표현식 실행(코어 수만큼)에서 나온다.
- 작은 데이터·플로팅 중심 워크플로는 pandas, 대용량·다단계 파이프라인은 polars. 병목이 실측되기 전에는 바꾸지 마라.

::: quiz 연습문제
1. `pl.scan_csv("data.csv").select(pl.col("a").mean()).collect()` 와 `pl.read_csv("data.csv").select(pl.col("a").mean())` 의 실행 결과는 같다. 그런데도 지연 버전을 권장하는 이유를 `.explain()` 출력을 근거로 설명하라.
2. pandas의 `df["x"].apply(lambda v: v * 2 if v > 0 else 0)` 을 (a) `np.where`, (b) polars `pl.when/then/otherwise` 두 가지로 각각 다시 써라. 실제로 실행 시간을 재서 몇 배 차이인지 확인하라.
3. Arrow의 validity bitmap이 없다면 정수 열에 결측치를 넣을 때 어떤 문제가 생기는가? [9.1 NumPy](#/numpy-basics)에서 다룬 dtype 승격 규칙과 연결해 설명하라.
4. 다음 코드에서 `t1` 과 `t2` 중 어느 쪽이 더 빠를지 예측하고, 20개 열짜리 Parquet 파일로 실제로 확인하라. 왜 그런 차이가 나는지 `PROJECT n/20 COLUMNS` 표기로 설명하라.

   ```python
   t1 = pl.read_parquet("wide.parquet").select(pl.col("col5").sum())
   t2 = pl.scan_parquet("wide.parquet").select(pl.col("col5").sum()).collect()
   ```
:::

**다음 절**: [9.8 SciPy](#/scipy) — 최적화, 보간, 신호 처리, 희소 행렬까지 NumPy 위에 쌓인 과학 계산 도구.
