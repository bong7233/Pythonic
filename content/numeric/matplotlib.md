# 9.9 matplotlib과 시각화

::: lead
[9.1](#/numpy-basics)부터 [9.8](#/scipy)까지 배열을 만들고, 깎고, 분석했다. 그런데 숫자 배열은 눈으로 보기 전까지는 믿을 수 없다. 벡터화가 틀렸는지, 이상치가 있는지, 분포가 정규분포를 닮았는지는 표를 스크롤해서는 안 보이고 그려야 보인다. matplotlib은 이 책에서 다루는 시각화의 밑바닥이다 — pandas의 `.plot()`도, seaborn도, 결국 이 위에서 돈다. 이 절은 두 가지만 확실히 박는다. **상태 기반 API를 버리고 객체지향 API를 써야 하는 이유**, 그리고 **화면에 안 보여도 파일로 저장해서 검증하는 습관**이다.
:::

## 상태 기반 API의 함정

`matplotlib.pyplot`을 이렇게 배운 사람이 많다.

```python title="익숙한 방식"
import matplotlib.pyplot as plt

plt.plot([1, 2, 3], [1, 4, 9])
plt.title("제곱")
plt.xlabel("x")
plt.savefig("quick.png")
```

간단해서 튜토리얼마다 이렇게 시작한다. 문제는 `plt.plot`, `plt.title`, `plt.xlabel`이 모두 **"현재 활성화된 figure와 axes"** 라는 전역 상태를 몰래 참조한다는 점이다. `pyplot` 모듈 내부에는 지금까지 만든 모든 figure의 스택이 있고, `plt.title(...)`은 사실 `plt.gcf().gca().set_title(...)`(get current figure → get current axes)을 줄인 것이다.

이게 왜 문제인지 직접 만들어 보자.

```python title="상태 기반 API가 헷갈리는 순간"
import matplotlib.pyplot as plt

fig1 = plt.figure()
plt.plot([1, 2, 3])          # fig1 위에 그린다

fig2 = plt.figure()
plt.plot([3, 2, 1])          # fig2가 새로 "현재"가 됐다

plt.title("current active")  # 어느 figure에 붙을까?

print(plt.gcf() is fig2)     # True
```

```pyrepl
>>> plt.gcf() is fig2
True
```

`plt.title(...)`은 `fig1`이 아니라 방금 만든 `fig2`에 붙는다. 함수 하나로 여러 figure를 다루면, 어느 순간 "지금 내가 그리고 있는 게 어느 figure인지" 코드만 봐서는 알 수 없어진다. 함수를 리팩터링해서 그래프 생성을 분리하면 이 문제는 훨씬 심해진다 — 호출 순서에 따라 결과가 달라지는, 전형적인 **암묵적 전역 상태**다.

이 감각이 낯설지 않을 것이다. [1.1 객체, 이름, 참조](#/objects-names)에서 본 것과 정확히 같은 종류의 함정이다. 그때는 "이름표가 어떤 객체를 가리키는가"가 코드만 봐서 불분명했다. 여기서는 "`plt`의 함수 호출이 어떤 figure/axes를 조작하는가"가 코드 순서에 숨어 있다. `pyplot`은 사실상 **모듈 수준의 전역 변수 하나(현재 axes에 대한 참조)를 계속 재할당하면서 그 위에 메서드를 호출하는 구조**다. 이름은 안 보이지만 동작 방식은 똑같다.

::: warn 왜 노트북에서는 안 드러나는가
주피터 노트북 셀 하나에 그림 하나만 그리는 습관 때문에 이 문제가 잘 안 보인다. 셀이 끝나면 그림이 그려지고 다음 셀은 새 상태에서 시작하는 것처럼 느껴진다. 하지만 함수로 그림 그리기 로직을 분리하는 순간, 또는 반복문 안에서 여러 figure를 만드는 순간 바로 터진다.
:::

## 객체지향 API: fig와 ax를 직접 쥔다

해법은 간단하다. **전역 상태에 의존하지 말고, figure와 axes 객체를 변수에 직접 담아서 그 객체의 메서드를 호출한다.**

```python title="객체지향 API"
import matplotlib.pyplot as plt

fig, ax = plt.subplots()      # Figure 객체와 Axes 객체를 각각 이름표로 받는다
ax.plot([1, 2, 3], [1, 4, 9])
ax.set_title("제곱")           # plt.title이 아니라 ax.set_title
ax.set_xlabel("x")
fig.savefig("quick_oo.png")
```

방금의 함정을 이 스타일로 다시 쓰면 애초에 헷갈릴 수가 없다.

```python title="같은 상황, 객체지향으로"
fig1, ax1 = plt.subplots()
ax1.plot([1, 2, 3])

fig2, ax2 = plt.subplots()
ax2.plot([3, 2, 1])

ax1.set_title("first")        # ax1은 언제나 ax1이다. 순서와 무관하다
ax2.set_title("second")
```

명명 규칙이 있다. `plt.무엇` 형태의 상태 기반 함수는 대체로 `ax.set_무엇` 이라는 객체지향 메서드로 대응된다.

| pyplot 함수 (상태 기반) | Axes 메서드 (객체지향) |
| --- | --- |
| `plt.plot(...)` | `ax.plot(...)` |
| `plt.title(...)` | `ax.set_title(...)` |
| `plt.xlabel(...)` / `plt.ylabel(...)` | `ax.set_xlabel(...)` / `ax.set_ylabel(...)` |
| `plt.xlim(...)` / `plt.ylim(...)` | `ax.set_xlim(...)` / `ax.set_ylim(...)` |
| `plt.legend(...)` | `ax.legend(...)` |
| `plt.savefig(...)` | `fig.savefig(...)` |

::: tip 그럼 pyplot을 완전히 버려야 하나
아니다. `plt.subplots()`로 figure를 **만드는 것** 자체는 여전히 `pyplot`을 쓴다. 버릴 것은 "만든 뒤 그 위에 그리는 모든 조작"이다. 원칙은 하나다. **`fig`, `ax`를 변수로 받은 순간부터는 `plt.`가 아니라 `fig.`/`ax.`를 쓴다.** 스크립트나 함수 안에서 여러 그림을 다루면 이 습관이 버그를 원천 차단한다.
:::

::: hist 왜 pyplot은 애초에 이렇게 설계됐나
matplotlib은 MATLAB의 플로팅 스타일을 흉내 내려고 만들어졌다. MATLAB은 `plot(x, y); title('...')` 식으로 "현재 그림"에 계속 명령을 쌓는 방식이다. `pyplot`은 그 스타일을 그대로 파이썬으로 옮긴 **호환성 계층**이다. 아래에는 항상 진짜 객체지향 구조(Figure, Axes, Artist 계층)가 있고, `pyplot`은 그 위에 얹은 "현재 상태를 기억하는" 편의 함수 모음일 뿐이다. 한 줄짜리 빠른 확인용 그림에는 `pyplot`이 여전히 편하다. 재사용 가능한 코드, 함수, 여러 그림에는 객체지향이 맞다.
:::

## 여러 서브플롯 배치

`plt.subplots(nrows, ncols)`는 격자 모양의 Axes 배열을 한 번에 만든다. 반환된 `axes`는 NumPy 배열이므로 [9.1 NumPy](#/numpy-basics)에서 배운 인덱싱이 그대로 통한다.

```python title="2x2 격자"
import matplotlib.pyplot as plt
import numpy as np

rng = np.random.default_rng(42)
x = np.linspace(0, 10, 200)

fig, axes = plt.subplots(2, 2, figsize=(8, 6), constrained_layout=True)

axes[0, 0].plot(x, np.sin(x))
axes[0, 0].set_title("line")

axes[0, 1].scatter(rng.normal(size=100), rng.normal(size=100), s=10, alpha=0.6)
axes[0, 1].set_title("scatter")

axes[1, 0].bar(["a", "b", "c", "d"], [3, 7, 2, 5])
axes[1, 0].set_title("bar")

axes[1, 1].hist(rng.normal(size=1000), bins=30)
axes[1, 1].set_title("hist")

fig.savefig("grid.png", dpi=150)
```

실제로 실행하면 `grid.png`가 만들어진다 — matplotlib 3.11.1 기준 크기는 약 59.5 KB였다(내용에 따라 달라진다). `constrained_layout=True`를 빼면 제목과 라벨이 옆 서브플롯과 겹치는 경우가 많다. 옛 코드에서 보이는 `fig.tight_layout()` 호출도 같은 문제를 풀지만, `constrained_layout`(또는 3.6+의 `layout="constrained"`)이 더 안정적이다.

행과 열의 크기가 다른 비정형 배치가 필요하면 `subplot_mosaic`가 편하다. 문자열 이름으로 영역을 지정하면 딕셔너리로 axes를 돌려준다.

```python title="비정형 배치"
fig, axd = plt.subplot_mosaic(
    [["left", "right_top"],
     ["left", "right_bottom"]],
    figsize=(6, 4),
)
axd["left"].plot(x, np.sin(x))
axd["right_top"].plot(x, np.cos(x))
axd["right_bottom"].bar(["a", "b"], [1, 2])
fig.savefig("mosaic.png")
```

실제로 실행하면 `mosaic.png`가 만들어진다 — matplotlib 3.11.1 기준 크기는 30,902바이트였다.

같은 x축을 공유하되 y축 단위가 다른 두 데이터를 겹쳐 보고 싶을 때는 `ax.twinx()`로 같은 x축을 쓰는 두 번째 y축을 만든다.

```python title="두 개의 y축"
fig, ax1 = plt.subplots()
ax1.plot(x, np.sin(x), color="C0")
ax2 = ax1.twinx()
ax2.plot(x, np.exp(x * 0.1) * 100, color="C1")
fig.savefig("twinx.png")
```

::: note sharex, sharey
`plt.subplots(2, 2, sharex=True, sharey=True)`로 만들면 모든 서브플롯이 같은 축 범위를 공유한다. 여러 그림을 나란히 비교할 때 눈금이 어긋나지 않아 비교가 정확해진다.
:::

## 그려서 저장하고, 저장됐는지 실제로 확인한다

이 환경은 화면에 그림을 띄울 수 없다. 그래도 `fig.savefig(path)`로 파일을 만들고 **그 파일이 실제로 생겼는지, 크기가 0이 아닌지**를 확인하면 코드가 제대로 동작했다는 증거가 된다.

```python title="저장 후 검증"
import os

fig, ax = plt.subplots()
ax.plot(x, np.sin(x))
fig.savefig("check.png")
plt.close(fig)          # figure를 메모리에서 해제한다 — 반복 호출 시 필수

print(os.path.exists("check.png"), os.path.getsize("check.png"))
```

```pyrepl
>>> os.path.exists("check.png"), os.path.getsize("check.png")
(True, 24873)
```

::: perf plt.close를 잊으면 메모리가 샌다
`plt.subplots()`로 만든 Figure는 `plt.close(fig)`를 호출하기 전까지 `pyplot`이 내부적으로 참조를 들고 있다. [1.1](#/objects-names)에서 배웠듯, 참조가 남아 있으면 참조 카운트가 0이 되지 않고 객체는 죽지 않는다. 반복문 안에서 그림을 수백 개 만들고 닫지 않으면 메모리가 계속 쌓인다. `for` 루프로 그림을 여러 장 저장하는 코드에는 반드시 `plt.close(fig)`를 넣어라.
:::

저장 포맷과 해상도는 별개의 축이다. `figsize`는 인치 단위의 그림 크기, `dpi`는 인치당 픽셀 수다. 최종 픽셀 크기는 이 둘의 곱이다.

```python title="figsize와 dpi의 관계"
fig, ax = plt.subplots(figsize=(4, 3))
ax.plot(x, np.sin(x))
fig.savefig("dpi72.png", dpi=72)
fig.savefig("dpi300.png", dpi=300)
```

```pyrepl
>>> from PIL import Image
>>> Image.open("dpi72.png").size
(288, 216)
>>> Image.open("dpi300.png").size
(1200, 900)
```

$4 \times 72 = 288$, $4 \times 300 = 1200$ — 정확히 맞아떨어진다. 논문이나 인쇄용은 최소 `dpi=300`을 쓴다. 웹이나 슬라이드는 `dpi=100~150`이면 충분하고, 파일이 쓸데없이 커지지 않는다.

포맷 선택도 용도에 따라 갈린다.

| 포맷 | 특징 | 언제 |
| --- | --- | --- |
| `.png` | 래스터, 압축, 투명 배경 지원 | 슬라이드, 웹, 빠른 확인 |
| `.pdf` | 벡터, 무한 확대해도 안 깨짐 | 논문 제출(대부분 요구) |
| `.svg` | 벡터, 텍스트가 텍스트로 남음 | 후편집(Illustrator 등)이 필요할 때 |
| `.jpg` | 손실 압축, 투명 불가 | 사진 위주 이미지 |

```python title="벡터 포맷으로 저장"
fig.savefig("figure.pdf")
fig.savefig("figure.svg")
```

실측으로 `.pdf`는 7,658바이트, `.svg`는 14,337바이트가 나왔다(같은 단순한 선 그래프 기준). 벡터 포맷은 도형의 개수에 비례해 커지므로, 점이 수만 개인 산점도를 그대로 PDF로 저장하면 파일이 수십 MB로 불어날 수 있다. 이런 경우는 `rasterized=True` 옵션으로 해당 요소만 래스터화한다.

## 논문·발표용 품질 만들기

기본 설정 그대로 저장한 그림은 발표 자료로 쓰기엔 부족하다. 세 가지 축으로 손본다.

**1. 스타일 시트.** `plt.style.use(...)`로 색·격자·폰트를 한 번에 바꾼다.

```pyrepl
>>> plt.style.available[:5]
['Solarize_Light2', 'bmh', 'classic', 'dark_background', 'fast']
>>> len(plt.style.available)
28
```

```python title="스타일을 국소적으로만 적용"
with plt.style.context("seaborn-v0_8-whitegrid"):
    fig, ax = plt.subplots()
    ax.plot(np.arange(10), np.arange(10) ** 2)
    fig.savefig("styled.png")
```

`plt.style.use(...)`는 전역으로 남지만, `with plt.style.context(...)`는 `with` 블록 안에서만 적용되고 끝나면 원래대로 돌아온다. [1.17 컨텍스트 매니저](#/context-managers)에서 본 그 패턴이다 — 전역 설정을 임시로 바꾸고 반드시 되돌린다.

**2. rcParams로 세밀 조정.** 폰트, 글자 크기, 기본 DPI를 코드 맨 앞에서 한 번에 지정해 두면 이후 모든 그림에 일관되게 적용된다.

```python title="발표/논문용 기본값"
plt.rcParams.update({
    "font.size": 11,
    "font.family": "serif",
    "axes.titlesize": 13,
    "figure.dpi": 100,       # 화면/노트북 표시용
    "savefig.dpi": 300,      # 저장할 때는 고해상도
})
```

```pyrepl
>>> plt.rcParams["savefig.dpi"]
300.0
```

**3. 잘림 방지.** 라벨이나 범례가 그림 가장자리에서 잘리는 문제는 `savefig`에 `bbox_inches="tight"`를 주면 대부분 해결된다.

```python title="여백 자동 조정"
fig.savefig("tight.png", bbox_inches="tight")
```

::: cote 코딩테스트/보고서 제출용 그림 체크리스트
과제나 보고서에 그림을 넣을 때 최소한 이건 지켜라. (1) 축 라벨과 단위를 반드시 적는다. (2) 여러 선을 그렸으면 범례를 넣는다. (3) `dpi`를 150 이상으로 저장한다. (4) 파일 크기가 0바이트가 아닌지, 즉 코드가 예외 없이 끝까지 돌았는지 저장 직후 `os.path.getsize`로 확인한다.
:::

## 자주 쓰는 그래프 타입

데이터의 성격에 맞는 그래프 타입을 고르는 게 절반이다. 아래는 Axes 객체의 메서드 기준으로 정리한 표다.

| 메서드 | 용도 | 데이터 형태 |
| --- | --- | --- |
| `ax.plot(x, y)` | 연속적인 추세, 시계열 | 정렬된 x, y |
| `ax.scatter(x, y)` | 두 변수의 관계, 군집 | 대응하는 x, y 쌍 |
| `ax.bar(labels, values)` | 범주별 비교 | 이산 범주 |
| `ax.hist(data, bins=...)` | 분포 확인 | 1차원 표본 |
| `ax.boxplot(datasets)` | 여러 그룹의 분포·이상치 비교 | 그룹별 표본 |
| `ax.errorbar(x, y, yerr=...)` | 측정값과 오차/신뢰구간 | 값 + 오차 |
| `ax.imshow(matrix)` | 2차원 배열을 색으로(히트맵, 이미지) | 2차원 배열 |

히트맵은 [9.1 NumPy](#/numpy-basics)에서 만든 2차원 배열을 그대로 넣으면 된다.

```python title="히트맵"
data = rng.normal(size=(20, 20))
fig, ax = plt.subplots()
im = ax.imshow(data, cmap="viridis")
fig.colorbar(im, ax=ax)   # 색 스케일을 보여주는 막대
fig.savefig("heatmap.png")
```

오차 막대는 실험값 비교에서 자주 빠뜨리는 요소다.

```python title="오차 막대"
x = np.arange(5)
y = rng.normal(size=5) + 5
yerr = rng.uniform(0.2, 0.6, size=5)

fig, ax = plt.subplots()
ax.errorbar(x, y, yerr=yerr, fmt="o-", capsize=4)
fig.savefig("errorbar.png")
```

::: deep 색은 왜 "C0", "C1"인가
`color="C0"`처럼 쓴 코드를 자주 본다. matplotlib은 `axes.prop_cycle`이라는 rcParams 항목에 기본 색 순환 목록을 갖고 있고, `C0`부터 `C9`까지는 그 목록의 색을 직접 가리키는 표기다. `ax.plot`을 색 지정 없이 여러 번 호출하면 이 순환을 따라 자동으로 다른 색이 배정된다. 방금 twinx 예제에서 두 선이 자동으로 다른 색이 된 것도 이 순환 때문이다.
:::

## 요약

- **pyplot 상태 기반 API(`plt.plot`, `plt.title`)는 "현재 활성 figure/axes"라는 전역 상태를 몰래 참조한다.** 함수를 나누거나 여러 figure를 다루면 순서에 따라 결과가 달라지는 함정에 빠진다.
- **객체지향 API(`fig, ax = plt.subplots()`)는 figure와 axes를 변수로 직접 쥐고 그 메서드를 호출한다.** 어느 코드가 어느 그림에 그리는지 코드만 보고 알 수 있다. 재사용 가능한 코드, 함수 안의 그리기 로직에는 항상 이쪽을 써라.
- `plt.subplots(nrows, ncols)`로 격자를, `subplot_mosaic`로 비정형 배치를, `ax.twinx()`로 이중 y축을 만든다.
- 화면이 없어도 `fig.savefig(path)`로 저장하고 `os.path.getsize`로 검증할 수 있다. **`plt.close(fig)`를 잊으면 반복 호출 시 메모리가 계속 쌓인다.**
- 저장 픽셀 크기는 `figsize × dpi`다. 인쇄/논문용은 `dpi=300` 이상, 벡터가 필요하면 `.pdf`/`.svg`를 쓴다.
- `plt.style.context(...)`, `rcParams`, `bbox_inches="tight"`로 발표/논문 품질을 만든다.
- 데이터 형태에 맞는 그래프 타입을 고른다 — 추세는 line, 관계는 scatter, 분포는 hist/boxplot, 2차원 배열은 imshow.

::: quiz 연습문제
1. 다음 코드를 실행하면 두 번째 `plt.title(...)`이 어느 figure에 붙는지 예측하고, 실제로 실행해서 확인하라. 왜 그런 결과가 나오는지 이 절의 개념으로 설명하라.

   ```python
   fig_a = plt.figure()
   plt.plot([1, 2, 3])
   fig_b = plt.figure()
   plt.plot([3, 2, 1])
   plt.title("어디에 붙을까")
   ```

2. `plt.subplots(figsize=(5, 4))`로 만든 그림을 `dpi=100`과 `dpi=250`으로 각각 저장하라. 두 PNG 파일의 픽셀 크기를 `PIL.Image.open(...).size`로 확인하고, `figsize × dpi` 공식과 일치하는지 검증하라.

3. 반복문으로 그림 20개를 만들어 각각 `savefig`로 저장하되, 한 번은 `plt.close(fig)`를 호출하지 않고, 한 번은 호출하면서 실행하라. `len(plt.get_fignums())`로 살아있는 figure 개수를 비교하라.

4. 표준정규분포 표본 1000개를 만들어 히스토그램으로 그리고, 같은 데이터를 boxplot으로도 그려라. 두 그래프가 각각 어떤 정보를 더 잘 보여주는지 비교하라.

5. `ax.plot`을 색 지정 없이 5번 연속 호출한 뒤 각 선의 색을 확인하라. `axes.prop_cycle`의 몇 번째 색까지 쓰였는지 `ax.lines[i].get_color()`로 확인하라.
:::

**다음 절**: [10.1 ML 문제 정의와 워크플로](#/ml-workflow) — 데이터를 눈으로 확인했다면, 이제 그 데이터로 무엇을 예측할지 정할 차례다.
