# 0.5 REPL, pdb, 주피터

::: lead
`print` 로 디버깅하는 사람과 디버거를 쓰는 사람의 생산성 차이는 몇 배다. 그런데도 대부분이 `print` 에 머무는 이유는 디버거가 어려워서가 아니라, **한 번도 제대로 배운 적이 없어서**다. 이 절은 30분 투자로 평생 쓸 도구를 손에 쥐여 준다.
:::

## 파이썬의 가장 큰 무기

파이썬으로 뭔가를 배울 때 최고의 도구는 문서가 아니라 **REPL**이다. Read-Eval-Print Loop — 읽고, 평가하고, 출력하고, 반복.

컴파일 언어에서 "이 함수가 뭘 반환하지?"를 확인하려면 프로그램을 짜고 빌드하고 실행해야 한다. 파이썬은 그냥 물어보면 된다. **이 즉시성이 학습 속도를 결정한다.**

```bash
uv run python
```

```pyrepl
>>> import sys
>>> sys.version_info.minor
14
```

### 3.13부터 REPL이 완전히 달라졌다

파이썬 3.13에서 REPL이 새로 쓰였다. 이전까지는 화살표 키가 `^[[A` 로 찍히는 환경도 있었고, 여러 줄 편집이 불가능했다. 지금은 다르다.

| 기능 | 설명 |
| --- | --- |
| 여러 줄 편집 | 위 화살표로 **블록 전체**를 불러와 수정 |
| 문법 강조 | 입력하는 동안 색이 붙는다 |
| `exit` | 이제 `exit()` 가 아니라 그냥 `exit` 로 나가진다 |
| <kbd>F2</kbd> | 히스토리 브라우징 (프롬프트 없이 코드만) |
| <kbd>F3</kbd> | **붙여넣기 모드** — 들여쓰기가 뭉개지지 않는다 |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> | 실행 중단 (프로그램 종료가 아님) |

::: tip F3 붙여넣기 모드
REPL에 들여쓴 코드를 붙여넣으면 자동 들여쓰기와 겹쳐서 계단처럼 망가지던 문제, 다들 겪어 봤을 것이다. <kbd>F3</kbd> 를 누르고 붙여넣으면 원본 그대로 들어간다. **이 책의 예제를 REPL에서 시험할 때 계속 쓰게 된다.**
:::

### REPL에서 반드시 알아야 할 세 가지

**1. `_` 는 마지막 결과다.**

```pyrepl
>>> 2 ** 10
1024
>>> _ + 1
1025
>>> x = _
>>> x
1025
```

**2. `help()` 와 `dir()` 은 검색보다 빠르다.**

```pyrepl
>>> help(str.split)
Help on method_descriptor:

split(self, /, sep=None, maxsplit=-1)
    Return a list of the substrings in the string, using sep as the separator string.
    ...

>>> dir(str)          # str이 가진 모든 이름
['__add__', '__class__', ..., 'capitalize', 'casefold', 'center', 'count', ...]

>>> [m for m in dir(str) if 'just' in m]     # 이름으로 거르기
['ljust', 'rjust']
```

::: tip dir() 을 거르는 습관
`dir()` 은 던더 메서드까지 다 쏟아내서 읽기 힘들다. 컴프리헨션으로 걸러 보는 습관을 들여라.

```pyrepl
>>> [m for m in dir(list) if not m.startswith('_')]
['append', 'clear', 'copy', 'count', 'extend', 'index', 'insert', 'pop', 'remove', 'reverse', 'sort']
```

"리스트에 뭐가 있더라?"를 검색하는 것보다 빠르다.
:::

**3. `type()` 과 `vars()` 로 정체를 캔다.**

```pyrepl
>>> from pathlib import Path
>>> p = Path("data.txt")
>>> type(p)
<class 'pathlib.PosixPath'>          # Windows면 WindowsPath
>>> p.suffix
'.txt'
>>> vars(p)                          # 인스턴스의 __dict__
```

### 스크립트를 REPL로 이어받기

이건 의외로 잘 모르는 기능인데 대단히 유용하다.

```bash
python -i script.py
```

`-i` 는 스크립트를 끝까지 실행한 뒤 **그 상태 그대로 REPL을 띄운다.** 스크립트가 만든 변수를 전부 그대로 조사할 수 있다. 예외로 죽었더라도 REPL이 뜬다.

```bash
uv run python -i train.py     # 학습 끝난 뒤 model, history 등을 바로 조사
```

## 디버거: pdb

`print` 디버깅의 문제는 셋이다. 매번 코드를 고쳐야 하고, 실행을 다시 해야 하고, **무엇을 출력할지 미리 알아야** 한다. 디버거는 셋 다 없앤다.

### 시작: breakpoint()

```python title="buggy.py" {6}
def total_price(items):
    total = 0
    for name, price, qty in items:
        total += price * qty
    return total

breakpoint()          # 여기서 멈춘다
print(total_price([("사과", 1000, 3), ("배", 2000, 2)]))
```

`breakpoint()` 는 3.7부터의 내장 함수다. 옛날에는 `import pdb; pdb.set_trace()` 라고 썼다. **`breakpoint()` 만 기억하면 된다.**

::: tip breakpoint()는 끌 수 있다
환경 변수 `PYTHONBREAKPOINT=0` 을 주면 `breakpoint()` 호출이 전부 **무시된다**. 코드를 고칠 필요가 없다.

```bash
PYTHONBREAKPOINT=0 python buggy.py      # macOS/Linux
$env:PYTHONBREAKPOINT=0; python buggy.py  # PowerShell
```

실수로 `breakpoint()` 를 커밋해서 CI가 멈추는 사고의 응급 처치로도 쓴다. (물론 ruff의 `T100` 규칙을 켜면 애초에 커밋 전에 잡힌다.)
:::

### pdb 명령어 — 이것만 알면 된다

멈추면 `(Pdb)` 프롬프트가 뜬다. 여기서 쓰는 명령은 사실상 아래가 전부다.

| 명령 | 줄임 | 하는 일 |
| --- | --- | --- |
| `next` | `n` | 다음 줄로 (함수 호출은 **건너뛴다**) |
| `step` | `s` | 다음 줄로 (함수 호출 **안으로 들어간다**) |
| `continue` | `c` | 다음 중단점까지 그냥 실행 |
| `list` | `l` | 지금 위치 주변 코드 보기 |
| `longlist` | `ll` | 현재 함수 전체 보기 |
| `print <식>` | `p` | 값 출력 |
| `pp <식>` | | 예쁘게 출력 (긴 dict/list에 유용) |
| `where` | `w` | 호출 스택 보기 |
| `up` / `down` | `u`/`d` | 스택을 위/아래로 이동 |
| `args` | `a` | 현재 함수의 인자들 |
| `until <줄번호>` | `unt` | 그 줄까지 실행 (루프 빠져나올 때 유용) |
| `return` | `r` | 현재 함수가 반환할 때까지 실행 |
| `interact` | | **완전한 REPL을 연다** |
| `quit` | `q` | 종료 |

::: warn n 과 s 의 차이가 핵심이다
`f(g(x))` 앞에서:

- `n`(next) — `f` 도 `g` 도 실행하고 **결과만** 받은 뒤 다음 줄로. "이 줄은 믿는다."
- `s`(step) — `g` 안으로 **들어간다**. "이 안이 의심스럽다."

**기본은 `n` 이다.** 남의 라이브러리까지 `s` 로 들어가면 순식간에 길을 잃는다. `s` 는 "여기가 범인이다" 싶을 때만 쓴다.
:::

::: danger p 와 변수 이름의 충돌
pdb에서 `n` 이라는 **변수**를 출력하려고 `n` 이라고 치면 `next` 명령이 실행된다. 명령어와 이름이 겹치기 때문이다.

이럴 땐 `p n` 처럼 `p` 를 붙이거나, `!n` 처럼 느낌표를 앞에 붙여 "이건 파이썬 표현식이다"라고 알린다.

```text nolines
(Pdb) p n
5
(Pdb) !n = 10      # 변수에 값을 넣는 것도 된다
```

**디버거 안에서 변수를 바꿀 수 있다**는 걸 기억해 두자. 가설을 즉석에서 시험할 수 있다.
:::

### 실전: 예외가 난 자리로 바로 가기

이게 pdb의 가장 강력한 사용법인데 잘 안 알려져 있다.

```bash
uv run python -m pdb -c continue buggy.py
```

이러면 스크립트가 그냥 실행되다가, **예외가 나는 순간 그 자리에서 디버거가 열린다.** 죽은 시점의 모든 지역 변수가 살아 있다. `where` 로 스택을 훑고, `up` 으로 올라가며 어디서 잘못됐는지 추적한다.

REPL에서 이미 예외가 났다면 사후에 열 수도 있다.

```pyrepl
>>> import pdb
>>> pdb.pm()          # post-mortem: 마지막 예외 지점으로
```

::: tip interact — pdb 안에서 진짜 REPL
pdb 프롬프트는 한 줄짜리 표현식에는 좋지만 복잡한 걸 하기엔 불편하다. `interact` 를 치면 **현재 프레임의 지역 변수를 그대로 가진 완전한 파이썬 REPL**이 열린다. 여기서 import도 하고, 함수도 정의하고, 실험을 마음껏 한 뒤 <kbd>Ctrl</kbd>+<kbd>D</kbd> 로 pdb에 돌아온다.

```text nolines
(Pdb) interact
*pdb interact start*
>>> import pandas as pd
>>> pd.DataFrame(items)          # 죽은 시점의 데이터를 자유롭게 분석
>>> ^D
*exiting pdb interact mode*
(Pdb)
```
:::

### 에디터 디버거

VS Code나 PyCharm의 GUI 디버거는 같은 일을 시각적으로 한다. **원리는 똑같다** — 중단점, 스텝, 변수 조사. GUI가 편하면 그걸 써라.

다만 pdb를 알아야 하는 이유가 있다. **원격 서버, 도커 컨테이너, GPU 클러스터, 로봇 위의 라즈베리파이** — GUI를 붙일 수 없는 곳에서도 터미널 하나만 있으면 디버깅이 된다. ROS 노드나 학습 잡을 디버깅할 때 이 차이가 크다.

## 주피터: 언제 쓰고 언제 쓰지 말아야 하나

주피터 노트북은 코드·결과·그림·설명을 한 문서에 담는다. 데이터를 **탐색**할 때는 대체재가 없다.

```bash
uv add --dev jupyterlab
uv run jupyter lab
```

::: tip 알아 두면 좋은 매직 명령
```python
%timeit sorted(data)          # 여러 번 돌려 평균 실행 시간
%%timeit                      # 셀 전체를 측정 (셀 첫 줄)
%debug                        # 방금 난 예외 지점에서 pdb 열기
%load_ext autoreload
%autoreload 2                 # 수정한 .py 모듈을 자동 재로딩
!pip list                     # 셸 명령 실행
%who                          # 정의된 변수 목록
```

`%autoreload 2` 는 특히 유용하다. 노트북에서 실험하면서 별도 `.py` 파일의 함수를 고치면 **커널 재시작 없이** 반영된다.
:::

::: danger 노트북의 진짜 위험: 실행 순서
노트북에서 셀은 **위에서 아래로 실행된다는 보장이 없다.** 셀 3을 고치고 다시 돌리고, 셀 1로 올라가 또 돌리고… 그러면 **화면에 보이는 코드와 실제 메모리 상태가 다르다.**

이것 때문에 벌어지는 일:

- 이미 지운 셀에서 만든 변수가 아직 살아 있어서, **없는 코드에 의존하는 노트북**이 만들어진다. 남에게 주면 안 돌아간다.
- 실험 결과가 재현되지 않는다. 어떤 순서로 돌렸는지 아무도 모른다.

**규칙: 결과를 남에게 보이거나 커밋하기 전에 반드시 `Kernel → Restart & Run All` 을 돌려라.** 그게 통과해야 진짜다.

그리고 노트북 `.ipynb` 는 JSON이라 **git diff가 사실상 읽을 수 없다.** 출력에 이미지가 들어가면 파일이 수 MB가 된다. `nbstripout` 이나 `jupytext` 를 쓰거나, 아예 아래 규칙을 따르는 게 낫다.
:::

::: warn 노트북과 모듈의 경계
경험칙 하나로 정리하면 이렇다.

> **탐색은 노트북에서, 자산은 `.py` 에.**

두 번 이상 쓸 함수, 테스트할 로직, 다른 데서 import할 것 — 전부 `.py` 로 옮긴다. 노트북에는 그걸 **불러 쓰는 코드와 그림**만 남긴다.

이렇게 하면: 테스트를 붙일 수 있고, 린터가 검사하고, git diff가 읽히고, 재사용된다. ML 프로젝트가 망하는 흔한 경로가 **2000줄짜리 노트북 하나**다.
:::

## 도구 선택 정리

| 상황 | 쓸 것 |
| --- | --- |
| "이 함수 뭐 반환하지?" | REPL |
| "왜 여기서 값이 이상하지?" | `breakpoint()` |
| "어디서 터졌지?" | `python -m pdb -c continue` |
| "이 데이터 어떻게 생겼지?" | 주피터 |
| "스크립트 끝난 상태를 보고 싶다" | `python -i` |
| "이게 더 빠른가?" | `%timeit` / [5.1 프로파일링](#/profiling) |

::: cote 코딩테스트 포인트
시험장에는 디버거가 없다. 대신 이 두 가지가 실전이다.

**1. 표준 에러로 디버깅한다.** 온라인 저지는 `stdout` 만 채점한다. `stderr` 에 찍으면 **정답 판정에 영향을 주지 않으면서** 로그를 볼 수 있다.

```python
import sys
print(f"{dp=}", file=sys.stderr)      # 채점에 영향 없음
```

**2. `f"{변수=}"` 문법을 익혀 둬라** (3.8+). 변수명과 값을 함께 찍어 준다.

```pyrepl
>>> n, dp = 5, [0, 1, 1, 2, 3]
>>> print(f"{n=} {dp=}")
n=5 dp=[0, 1, 1, 2, 3]
```

`print("n =", n, "dp =", dp)` 라고 칠 시간을 아껴 준다. 시험장에서 초 단위가 쌓인다.

**3. 로컬에서 입력을 파일로 만들어 두고 테스트하라.** 매번 손으로 입력을 치면 시간을 버린다. [8.2 입출력 최적화](#/io-optimize)에서 다룬다.
:::

## 요약

- **REPL은 파이썬 학습의 가속 장치**다. `help`, `dir`, `type`, `_` 만 알아도 검색보다 빠르다.
- 3.13+ REPL은 여러 줄 편집과 <kbd>F3</kbd> 붙여넣기 모드를 지원한다. 이 책의 예제 실습에 그대로 쓴다.
- **`breakpoint()`** 하나면 디버거가 열린다. `n`/`s`/`c`/`p`/`w`/`interact` 면 실전에 충분하다.
- **`python -m pdb -c continue`** 는 예외 난 자리로 바로 데려간다. `print` 를 심고 재실행하는 습관을 이걸로 바꿔라.
- 노트북은 **탐색용**이다. 재사용할 것은 `.py` 로 옮긴다. 커밋 전엔 Restart & Run All.

::: quiz 연습문제
1. 아래 코드는 틀린 답을 낸다. `breakpoint()` 를 넣고 `n`, `p`, `ll` 만 써서 원인을 찾아라. `print` 는 쓰지 마라.

   ```python
   def average(nums):
       total = 0
       for i in range(len(nums) - 1):
           total += nums[i]
       return total / len(nums)

   print(average([10, 20, 30, 40]))    # 25.0이 나와야 하는데?
   ```

2. `python -m pdb -c continue` 로 아래를 실행하고, `where` 와 `up` 을 써서 **어느 호출 단계에서** 잘못된 값이 들어갔는지 짚어라.

   ```python
   def parse(line): return int(line.strip())
   def load(lines): return [parse(l) for l in lines]
   def main(): print(sum(load(["1", "2", "세", "4"])))
   main()
   ```

3. REPL에서 `dir(dict)` 를 걸러서 언더스코어로 시작하지 않는 메서드만 출력하라. 그중 이름만 보고 뭘 하는지 모르겠는 게 있으면 `help()` 로 확인하라. ([1.6 dict](#/dict)의 예습이다.)
:::

---

**Part 0을 마쳤다.** 환경이 준비됐다. 이제 언어 자체로 들어간다.

다음 파트는 이 책에서 가장 중요하다. [Part I 언어의 코어](#/objects-names)는 "리스트 만드는 법"을 가르치지 않는다. **파이썬이 왜 그렇게 동작하는지**를 다룬다. ROS의 콜백도, PyTorch의 텐서도, 코딩테스트의 시간 초과도 전부 여기서 배우는 것 위에 얹힌다.

**다음 절**: [1.1 객체, 이름, 참조 — 실행 모델](#/objects-names)
