# 9.6 pandas 실전

::: lead
[9.5 pandas 기초](#/pandas-basics)에서 `Series` 와 `DataFrame` 이 무엇인지 봤다. 실전 데이터 작업은 대부분 세 가지로 요약된다. **그룹으로 나눠서 계산하고**(groupby), **여러 표를 하나로 합치고**(merge), **시간 축으로 다시 자른다**(resample). 그리고 넷째로, 이 모든 걸 파이썬 `for` 문으로 짜면 왜 망하는지 몸으로 겪어야 한다. 이 절은 각각을 실제로 실행한 결과와 함께, 반복문 버전과 벡터화 버전의 속도를 직접 재서 비교한다. 숫자를 보고 나면 "pandas에서는 반복문을 쓰지 않는다"는 규칙이 종교가 아니라 산수라는 게 이해된다.
:::

## groupby — 나눠서, 계산하고, 다시 합친다

`groupby` 가 하는 일은 정확히 세 단계다. **split**(키로 나누기) → **apply**(각 그룹에 함수 적용) → **combine**(결과를 다시 하나로 합치기). 이 이름 자체가 pandas 공식 문서의 용어(split-apply-combine)다.

```python title="예제 데이터"
import pandas as pd

df = pd.DataFrame({
    "store": ["A", "A", "B", "B", "A", "B", "A", "B"],
    "product": ["apple", "banana", "apple", "banana", "apple", "apple", "banana", "banana"],
    "qty": [3, 5, 2, 7, 1, 4, 6, 2],
    "price": [1.0, 0.5, 1.2, 0.6, 1.1, 1.3, 0.4, 0.7],
})
```

```pyrepl
>>> df.groupby("store")["qty"].sum()
store
A    15
B    15
Name: qty, dtype: int64
```

`groupby("store")` 는 그 자체로는 아무 계산도 하지 않는다. `DataFrameGroupBy` 라는 **지연 객체**를 만들 뿐이다. 실제 계산은 `.sum()`, `.mean()` 같은 집계 메서드를 붙였을 때 일어난다. 이건 [9.7 polars](#/polars)에서 보게 될 지연 실행과 결이 비슷하다 — 계산을 미뤄 두면 나중에 최적화할 여지가 생긴다.

### 한 번에 여러 집계 — `agg`

컬럼마다 다른 집계 함수를 쓰고 싶으면 `agg` 에 이름을 붙여 넘긴다.

```pyrepl
>>> df.groupby("store").agg(total_qty=("qty", "sum"), avg_price=("price", "mean"))
       total_qty  avg_price
store
A             15       0.75
B             15       0.95
```

`(컬럼명, 함수)` 튜플을 이름 있는 인자로 넘기는 이 문법을 **named aggregation**이라 부른다. 결과 컬럼 이름을 직접 정할 수 있어서 `agg({"qty": "sum", "price": "mean"})` 같은 옛 방식보다 읽기 좋다.

멀티 키로 묶는 것도 그대로 된다.

```pyrepl
>>> df.groupby(["store", "product"])["qty"].sum()
store  product
A      apple       4
       banana     11
B      apple       6
       banana      9
Name: qty, dtype: int64
```

결과 인덱스가 `(store, product)` 쌍으로 된 **MultiIndex** 라는 걸 눈여겨봐라. 나중에 `.reset_index()` 로 평평한 표로 되돌릴 수 있다.

### `apply` — 그룹마다 임의의 함수를 돌린다

내장 집계 함수로 안 되는 계산은 `apply` 로 그룹 전체를 넘겨받아 직접 짠다. 예를 들어 "매장별 매출 비중"처럼 그룹 안에서의 상대값이 필요할 때다.

```python title="그룹별 매출 비중 계산"
def revenue_share(g):
    g = g.copy()
    g["revenue"] = g["qty"] * g["price"]
    g["share"] = g["revenue"] / g["revenue"].sum()
    return g

result = df.groupby("store", group_keys=False).apply(revenue_share, include_groups=False)
```

```pyrepl
>>> result
  product  qty  price  revenue     share
0   apple    3    1.0      3.0  0.333333
1  banana    5    0.5      2.5  0.277778
2   apple    2    1.2      2.4  0.181818
3  banana    7    0.6      4.2  0.318182
4   apple    1    1.1      1.1  0.122222
5   apple    4    1.3      5.2  0.393939
6  banana    6    0.4      2.4  0.266667
7  banana    2    0.7      1.4  0.106061
```

(pandas 3.0.3 실측. `include_groups=False` 는 pandas 2.2부터 생긴 옵션으로, 그룹 키 컬럼을 함수에 다시 넘기지 않도록 명시한다 — 예전 버전은 이 인자가 없다.)

### `transform` — 그룹 통계를 원본 크기로 되돌린다

`agg` 는 그룹 하나당 한 줄로 **줄어들지만**, `transform` 은 원본과 **같은 행 개수**로 결과를 돌려준다. "각 행에 자기 그룹의 통계를 붙이고 싶을 때" 쓴다.

```pyrepl
>>> df["store_total"] = df.groupby("store")["qty"].transform("sum")
>>> df["pct_of_store"] = df["qty"] / df["store_total"]
>>> df[["store", "qty", "store_total", "pct_of_store"]]
  store  qty  store_total  pct_of_store
0     A    3           15      0.200000
1     A    5           15      0.333333
2     B    2           15      0.133333
3     B    7           15      0.466667
4     A    1           15      0.066667
5     B    4           15      0.266667
6     A    6           15      0.400000
7     B    2           15      0.133333
```

`store_total` 이 모든 행에서 15인 게 이상해 보일 수 있는데, 위쪽 `groupby("store")["qty"].sum()` 결과(L23-28)에서 이미 A=15, B=15로 우연히 같은 값이 나왔던 걸 그대로 물려받은 것뿐이다 — `transform`은 그 그룹 합계를 원본 8행 전부에 그대로 복제해 붙인다.

::: tip agg / transform / apply 고르는 법
- 그룹마다 **숫자 하나**로 요약하고 싶다 → `agg` (가장 빠르다. C로 구현된 집계 함수를 쓴다)
- 그룹 통계를 **원본 행에 다시 붙이고** 싶다 → `transform`
- 내장 함수로 표현이 안 되는 **복잡한 로직**이 필요하다 → `apply` (가장 느리다. 이 절 뒤에서 왜 그런지 잰다)

**항상 `agg`/`transform`이 되는지 먼저 확인하고, 안 될 때만 `apply` 로 내려가라.** 순서를 반대로 하면 코드는 짧아 보이는데 성능은 나락으로 간다.
:::

## merge — 두 표를 합치는 네 가지 방법

관계형 데이터베이스의 `JOIN` 을 그대로 pandas로 옮긴 게 `pd.merge` 다. **키가 한쪽에만 있을 때 그 행을 버릴지 살릴지**가 `inner`/`left`/`right`/`outer` 의 차이 전부다.

```python title="예제: 고객과 주문"
customers = pd.DataFrame({
    "cust_id": [1, 2, 3, 4],
    "name": ["Alice", "Bob", "Carol", "Dave"],
})

orders = pd.DataFrame({
    "order_id": [101, 102, 103, 104],
    "cust_id": [1, 2, 2, 5],
    "amount": [100, 50, 30, 999],
})
```

고객 3(Carol), 4(Dave)는 주문이 없고, 주문 104는 존재하지 않는 고객 5의 것이다. 이 어긋남이 네 방식의 차이를 정확히 보여준다.

```pyrepl
>>> pd.merge(customers, orders, on="cust_id", how="inner")
   cust_id   name  order_id  amount
0        1  Alice       101     100
1        2    Bob       102      50
2        2    Bob       103      30
```

**inner**는 양쪽 다 있는 키만 남긴다. Carol, Dave, 주문104가 전부 사라진다.

```pyrepl
>>> pd.merge(customers, orders, on="cust_id", how="left")
   cust_id   name  order_id  amount
0        1  Alice     101.0   100.0
1        2    Bob     102.0    50.0
2        2    Bob     103.0    30.0
3        3  Carol       NaN     NaN
4        4   Dave       NaN     NaN
```

**left**는 왼쪽(`customers`)을 전부 보존한다. Carol과 Dave는 남고 대신 `order_id`, `amount` 가 `NaN` 이 된다. 주문104는 여전히 사라진다 — 왼쪽에 없는 고객의 주문이니까.

```pyrepl
>>> pd.merge(customers, orders, on="cust_id", how="right")
   cust_id   name  order_id  amount
0        1  Alice       101     100
1        2    Bob       102      50
2        2    Bob       103      30
3        5    NaN       104     999
```

**right**는 정반대다. 오른쪽(`orders`)이 전부 남는다. 주문104가 살아남고 `name` 이 `NaN` 이 된다. Carol, Dave는 사라진다.

```pyrepl
>>> pd.merge(customers, orders, on="cust_id", how="outer")
   cust_id   name  order_id  amount
0        1  Alice     101.0   100.0
1        2    Bob     102.0    50.0
2        2    Bob     103.0    30.0
3        3  Carol       NaN     NaN
4        4   Dave       NaN     NaN
5        5    NaN     104.0   999.0
```

**outer**는 양쪽 다 보존한다. 여섯 행 전부가 살아남고, 짝이 없는 쪽은 `NaN` 으로 채워진다.

::: note NaN이 뜨면서 정수가 실수로 바뀐다
`left`/`outer` 결과에서 `order_id` 가 `101` 이 아니라 `101.0` 으로 나온 걸 봐라. **정수 컬럼에 결측치(`NaN`)가 섞이면 pandas는 그 컬럼 전체를 `float64` 로 승격시킨다.** `NaN` 자체가 IEEE 754 부동소수점 개념이라 정수 dtype에는 담을 수 없기 때문이다. `Int64` (대문자, nullable integer) dtype을 쓰면 이 승격을 피할 수 있다. `right` 결과는 `orders` 가 온전히 살아 있어서 정수 그대로 남는다 — 어느 쪽이 결측을 갖게 되느냐에 따라 dtype 변화가 갈린다.
:::

::: cote 코딩테스트 포인트
merge를 코딩테스트에서 직접 쓸 일은 적지만, **네 종류의 의미**는 그래프/집합 문제에서 그대로 재활용된다. `inner` = 교집합, `outer` = 합집합, `left`/`right` = 한쪽 기준 차집합 보정. [7.12 유니온 파인드](#/union-find)에서 집합을 다루는 감각과 통한다.
:::

## 시계열: DatetimeIndex와 resample

시계열 데이터의 핵심은 인덱스를 **날짜/시간**으로 만드는 것이다. 그러면 "월별 평균", "6시간 단위 합계" 같은 재표본화(resample)가 한 줄이 된다.

```python title="시간별 판매량 만들기"
import numpy as np

rng = np.random.default_rng(0)
idx = pd.date_range("2026-01-01", periods=24, freq="h")
s = pd.Series(rng.integers(1, 100, size=24), index=idx, name="sales")
```

```pyrepl
>>> type(s.index)
<class 'pandas.DatetimeIndex'>
>>> s.resample("6h").sum()
2026-01-01 00:00:00    263
2026-01-01 06:00:00    265
2026-01-01 12:00:00    398
2026-01-01 18:00:00    326
Freq: 6h, Name: sales, dtype: int64
>>> s.resample("1D").mean()
2026-01-01    52.166667
Freq: D, Name: sales, dtype: float64
```

(pandas 3.0.3 실측 — 시드가 고정돼 있어 위 숫자는 이 문서 어디서든 재현된다.)

`resample` 은 겉보기엔 `groupby` 와 비슷하지만 하는 일이 다르다. **`groupby` 는 값으로 나누고, `resample` 은 시간 구간으로 나눈다.** 내부적으로 `resample("6h")` 은 `DatetimeIndex` 를 6시간짜리 구간(bin)으로 자른 뒤 그 구간을 새 groupby 키로 쓴다 — 그래서 `resample(...).sum()` 처럼 뒤에 집계 함수를 반드시 붙여야 한다.

`resample` 을 **`rolling`(이동 윈도우)** 과 혼동하지 마라. `resample` 은 표본 개수를 **줄인다**(24개 시간 → 4개 6시간 구간). `rolling(3).mean()` 은 표본 개수를 그대로 두고 각 지점에서 "직전 3개의 평균"을 계산한다.

```pyrepl
>>> s.rolling(3).mean().head(4)
2026-01-01 00:00:00          NaN
2026-01-01 01:00:00          NaN
2026-01-01 02:00:00    66.666667
2026-01-01 03:00:00    47.333333
Freq: h, Name: sales, dtype: float64
```

앞의 두 값이 `NaN` 인 이유는 명확하다. 윈도우 크기가 3인데 아직 3개가 안 모였기 때문이다. 이건 결측이 아니라 **아직 계산할 수 없다는 뜻**이다 — [9.5 pandas 기초](#/pandas-basics)에서 다룬 결측치 처리와 성격이 다르니 `fillna` 로 뭉개지 마라.

## 왜 `apply()` 가 느린가 — 반복문을 지우지 못했기 때문이다

여기서부터가 이 절의 핵심이다. **`DataFrame.apply(axis=1)` 은 겉보기엔 벡터화된 pandas API처럼 보이지만, 내부적으로는 각 행마다 파이썬 함수를 호출하는 반복문이다.** [1.1 객체, 이름, 참조](#/objects-names)에서 본 것처럼 파이썬 함수 호출 자체에 고정 비용이 있고, 그 비용이 행 개수만큼 곱해진다.

```python title="10만 행에서 apply vs 벡터화 연산"
import timeit

n = 100_000
df = pd.DataFrame({
    "a": np.random.default_rng(1).integers(1, 100, n),
    "b": np.random.default_rng(2).integers(1, 100, n),
})

def with_apply():
    return df.apply(lambda row: row["a"] * row["b"] + 1, axis=1)

def with_vectorized():
    return df["a"] * df["b"] + 1

t_apply = timeit.timeit(with_apply, number=3) / 3
t_vec = timeit.timeit(with_vectorized, number=3) / 3
```

```pyrepl
>>> t_apply
0.2598  # 초
>>> t_vec
0.000440  # 초
>>> t_apply / t_vec
590.7
```

::: perf apply(axis=1)는 10만 행에서 벡터화보다 약 590배 느리다
(pandas 3.0.3 / NumPy 2.5.1 / Windows 기준 실측. 절대 시간은 기기마다 다르지만 **두 자릿수~세 자릿수 배**라는 자릿수 차이는 어디서나 재현된다.)

이유는 단순하다. `df["a"] * df["b"]` 는 NumPy의 C 레벨 루프 하나로 10만 개를 한 번에 곱한다. `df.apply(..., axis=1)` 은 10만 번 **파이썬 람다를 호출**하고, 매번 그 행을 `Series` 객체로 포장해서 넘긴다 — `Series` 하나를 만드는 것 자체가 공짜가 아니다. 계산 자체는 사소한데 그 계산을 감싸는 오버헤드가 압도적으로 크다.
:::

`apply` 가 필요할 때도 물론 있다 — 조건 분기가 복잡하거나 외부 라이브러리 함수를 호출해야 할 때다. 하지만 **"단순 산술 + 비교"라면 거의 항상 벡터화된 표현으로 다시 쓸 수 있다.** 다음 표가 자주 쓰는 치환법이다.

| apply로 짠 것 | 벡터화 대안 |
| --- | --- |
| `df.apply(lambda r: r.a + r.b, axis=1)` | `df["a"] + df["b"]` |
| `df.apply(lambda r: "H" if r.x > 0 else "L", axis=1)` | `np.where(df["x"] > 0, "H", "L")` |
| `df["x"].apply(lambda v: v ** 2)` | `df["x"] ** 2` |
| `df.apply(lambda r: max(r.a, r.b), axis=1)` | `df[["a", "b"]].max(axis=1)` |

## `iterrows()` 의 재앙 — 그리고 그보다 나은 선택지

`apply` 보다 한 단계 더 아래에 `iterrows()` 가 있다. 이건 pandas 문서 자체가 "성능이 중요하면 쓰지 마라"고 경고하는 메서드다. 직접 재 보자.

```python title="2만 행에서 iterrows vs itertuples vs 벡터화"
n = 20_000
df = pd.DataFrame({
    "price": np.random.default_rng(3).uniform(10, 1000, n),
    "qty": np.random.default_rng(4).integers(1, 20, n),
})

def with_iterrows():
    total = 0.0
    for idx, row in df.iterrows():
        total += row["price"] * row["qty"]
    return total

def with_itertuples():
    total = 0.0
    for row in df.itertuples():
        total += row.price * row.qty
    return total

def with_vectorized():
    return (df["price"] * df["qty"]).sum()
```

```pyrepl
>>> timeit.timeit(with_iterrows, number=3) / 3
0.1532  # 초
>>> timeit.timeit(with_itertuples, number=3) / 3
0.0049  # 초
>>> timeit.timeit(with_vectorized, number=3) / 3
0.000722  # 초
```

(pandas 3.0.3 / Windows 기준 실측, 2만 행. 같은 코드를 두 번 반복 돌려 보면 `iterrows`/벡터화는 210~240배, `itertuples`/벡터화는 7~9배, `iterrows`/`itertuples`는 30~32배 사이에서 흔들린다 — L263의 `apply` 벤치마크와 마찬가지로 **절대 배율은 기기마다 다르지만 "두 자릿수~세 자릿수 차이"라는 자릿수 자체는 어디서나 재현된다.**)

세 방식의 격차는 이렇게 벌어진다(위 실측 기준, 자릿수만 신뢰하고 소수점까지 믿지 마라).

- `iterrows()` 대 `.sum()` 벡터화: 약 **212배**
- `itertuples()` 대 `.sum()` 벡터화: 약 **7배**
- `iterrows()` 대 `itertuples()`: 약 **31배**

::: danger iterrows()는 매 행마다 Series를 새로 만들고, 그 과정에서 dtype까지 뭉갠다
`iterrows()` 가 느린 이유는 두 겹이다.

1. 매 행마다 파이썬 함수 호출 + `Series` 객체 생성이라는 오버헤드가 든다 (`apply` 와 같은 문제).
2. **`DataFrame` 의 컬럼마다 dtype이 다르면, 한 행을 `Series` 로 뽑는 순간 전부 하나의 공통 dtype으로 강제 변환된다.**

두 번째 문제는 눈에 잘 안 띄어서 더 위험하다. 직접 확인해 보자.

```pyrepl
>>> df2 = pd.DataFrame({"price": [10.5, 20.1], "qty": [3, 5]})
>>> df2.dtypes
price    float64
qty        int64
dtype: object
>>> for idx, row in df2.iterrows():
...     print(idx, row.dtype, row.to_dict())
0 float64 {'price': 10.5, 'qty': 3.0}
1 float64 {'price': 20.1, 'qty': 5.0}
```

원본에서 `qty` 는 정수(`int64`)인데, `row` 로 뽑히는 순간 `3` 이 `3.0` 이 된 걸 봐라. `Series` 는 dtype을 하나만 가질 수 있으므로, 정수 열과 실수 열이 섞인 행을 뽑으면 **정수가 실수로 조용히 승격**된다. 이 값으로 정수 나눗셈이나 딕셔너리 키 비교를 하면 예상과 다른 결과가 나온다.

`itertuples()` 는 `namedtuple` 을 만들기 때문에 컬럼별 dtype을 그대로 보존하고, `Series` 를 만드는 비용도 없다. **그래도 반복문은 반복문이다** — 벡터화 대비 9배는 여전히 크다. 정말 행 단위 반복이 필요하면 `iterrows()` 대신 `itertuples()` 를 써라. 하지만 최선은 애초에 반복문을 쓰지 않는 것이다.
:::

::: deep 왜 벡터화가 근본적으로 빠른가
[9.2 브로드캐스팅과 벡터화](#/broadcasting)에서 다룬 이야기가 pandas에도 그대로 적용된다. `df["a"] * df["b"]` 는 파이썬 반복문을 아예 만들지 않는다. 두 컬럼의 내부 NumPy 배열(연속된 메모리 블록)을 C 레벨 루프 하나에 넘기고, 그 루프가 CPU 캐시에 올라간 데이터를 순서대로 훑으며 곱한다. 파이썬 객체를 만들지도, 참조 카운트를 건드리지도, 타입을 매번 확인하지도 않는다.

`iterrows()`/`apply(axis=1)` 은 이 모든 이점을 포기하고 원래의 "파이썬 반복문 + 매번 타입 확인" 세계로 돌아간다. pandas를 쓰면서 반복문을 쓰는 건, 자동차를 사 놓고 걸어 다니는 것과 같다. [5.1 측정 없이 최적화 없다](#/profiling)의 원칙 그대로, **감으로 "느릴 것 같다"가 아니라 실제로 재서** 590배, 212배라는 숫자를 눈으로 봐야 이 습관이 몸에 붙는다.
:::

## 요약

- `groupby` 는 split-apply-combine이다. **단순 집계는 `agg`, 원본 크기 유지가 필요하면 `transform`, 복잡한 로직만 `apply`** 로 내려가라.
- `merge` 의 `how` 는 짝이 없는 행을 어느 쪽 기준으로 버리거나 살리는지의 차이다. `inner`(교집합) / `left`·`right`(한쪽 기준) / `outer`(합집합).
- 결측이 섞이면 정수 컬럼이 `float64` 로 승격된다. `NaN` 이 정수를 담을 수 없기 때문이다.
- `resample` 은 시간 구간으로 표본 개수를 **줄이고**, `rolling` 은 표본 개수를 유지한 채 이동 윈도우를 계산한다.
- `DataFrame.apply(axis=1)` 은 벡터화가 아니라 **파이썬 반복문 + Series 생성**이다. 실측 10만 행 기준 벡터화 대비 약 590배 느렸다.
- `iterrows()` 는 매 행마다 dtype을 공통 타입으로 강제 승격시킨다. 실측 2만 행 기준 벡터화 대비 약 212배, `itertuples()` 대비도 약 31배 느렸다(정확한 배율은 기기마다 다르지만 두 자릿수~세 자릿수 차이는 항상 재현된다).
- 정말 행 단위 반복이 필요하면 `itertuples()` 가 `iterrows()` 보다 낫지만, 최선은 벡터화된 연산으로 다시 쓰는 것이다.

::: quiz 연습문제
1. 다음 코드가 만드는 결과를 예측한 뒤 실행해서 확인하라. `how` 를 `inner`, `left`, `right`, `outer` 로 각각 바꿔 가며 행 개수가 어떻게 달라지는지 표로 정리하라.

   ```python
   left = pd.DataFrame({"key": [1, 2, 3], "v1": ["a", "b", "c"]})
   right = pd.DataFrame({"key": [2, 3, 4], "v2": ["x", "y", "z"]})
   ```

2. `df.groupby("store")["qty"].sum()` 과 `df.groupby("store")["qty"].transform("sum")` 은 반환하는 행 개수가 다르다. 각각 몇 행이 나오는지 설명하고, 언제 어느 쪽을 써야 하는지 예를 들어라.

3. 다음 두 코드가 같은 결과를 내는지 확인하고, `timeit` 으로 어느 쪽이 몇 배 빠른지 직접 측정하라.

   ```python
   df["result"] = df.apply(lambda r: r["a"] if r["a"] > r["b"] else r["b"], axis=1)
   df["result"] = df[["a", "b"]].max(axis=1)
   ```

4. 시간별 데이터 `s` (1시간 간격, 48개)에 대해 `s.resample("12h").sum()` 을 실행하면 몇 개의 값이 나오는가? `s.rolling(12).sum()` 은 몇 개가 나오는가? 두 답이 다른 이유를 한 문장으로 설명하라.

5. **깊이 생각해 볼 문제.** `int64` 와 `float64` 컬럼이 섞인 `DataFrame` 에서 `iterrows()` 로 각 행을 뽑으면 정수 컬럼이 실수로 바뀐다. 이 문제를 `itertuples()` 로 바꾸면 해결되는 이유를 `Series`(단일 dtype)와 `namedtuple`(필드별 타입 자유)의 구조 차이로 설명하라.
:::

**다음 절**: [9.7 polars와 Apache Arrow](#/polars) — pandas의 이 모든 반복문 문제를 애초에 다른 실행 모델로 우회하는 라이브러리.
