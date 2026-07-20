# 5.1 측정 없이 최적화 없다

::: lead
지금부터 이 책은 "고쳐라"보다 "재라"를 먼저 말한다. 코드를 보고 "여기가 느릴 것 같다"고 짐작하는 순간 이미 틀릴 확률이 절반이다. 이 절은 그 짐작을 실제 숫자로 바꾸는 도구 — `timeit`, `cProfile`, `line_profiler`, `py-spy` — 를 하나씩 손으로 돌려 보여준다. Part V 전체, 그리고 [5.2](#/memory)부터 [5.6](#/pyo3)까지 나올 모든 최적화 기법은 이 절의 도구로 "진짜 병목"을 먼저 찾았다는 전제 위에 서 있다.
:::

## 감으로 최적화하면 안 되는 이유

다음 파이프라인을 보자. 로그 15만 줄을 만들고, 각 줄에서 상태 코드를 뽑아내고, 정렬해서 상위 10개를 돌려준다.

```python title="pipeline.py"
import re
import random

random.seed(42)
N = 150_000


def generate_lines(n):
    return [
        f"2026-01-{(i % 28) + 1:02d} ERROR user={i} code={random.randint(400, 599)} msg=timeout"
        for i in range(n)
    ]


def clean_line(line):
    pattern = re.compile(r"code=(\d+)")   # 나중에 다시 보자
    m = pattern.search(line)
    return int(m.group(1)) if m else 0


def parse_all(lines):
    return [clean_line(line) for line in lines]


def aggregate(codes):
    return sorted(codes, reverse=True)      # 15만 개 정렬 — $O(n \log n)$


def main():
    lines = generate_lines(N)
    codes = parse_all(lines)
    return aggregate(codes)[:10]
```

세 단계 중 어디가 가장 오래 걸릴 것 같은가? 대부분은 `aggregate` 라고 답한다. $O(n \log n)$ 정렬이 유일하게 이름 붙은 "알고리즘"이고, 나머지 둘은 그냥 반복문처럼 보이기 때문이다. 실제로 `cProfile` 로 재 보자.

```bash
python -m cProfile -s cumulative pipeline.py
```

```text nolines
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.393    0.393 pipeline.py:32(main)
        1    0.019    0.019    0.194    0.194 pipeline.py:23(parse_all)
        1    0.062    0.062    0.187    0.187 pipeline.py:9(generate_lines)
   150000    0.062    0.000    0.174    0.000 pipeline.py:16(clean_line)
   150000    0.050    0.000    0.125    0.000 random.py:335(randint)
   150000    0.020    0.000    0.068    0.000 __init__.py:287(compile)
        1    0.000    0.000    0.010    0.010 pipeline.py:27(aggregate)
        1    0.010    0.010    0.010    0.010 {built-in method builtins.sorted}
```

(Python 3.14.5 / Windows 기준 실측. 여러 번 반복 실행하면 총 실행 시간은 0.39~0.43초 사이에서 흔들린다 — 절대값은 기기와 실행마다 다르지만, 아래에서 볼 각 함수의 상대 비율은 반복 실행해도 거의 그대로 재현된다.)

`aggregate` 는 전체 0.393초 중 **0.010초, 2.5%다.** 짐작이 완전히 틀렸다. 진짜 시간은 `generate_lines`(난수 생성, 0.187초)와 `parse_all`(정규식 매칭, 0.194초)에 있다. 그리고 `parse_all` 안을 보면 `clean_line` 이 매 반복마다 `re.compile` 을 새로 호출한다 — 컴파일된 패턴을 캐싱하지 않은 버그다.

::: perf 정렬이 아니라 상수가 문제였다
$O(n \log n)$ 이라는 이름이 주는 위압감과 실제 비용은 다른 문제다. 15만 개 정수 비교는 Timsort([7.4 정렬](#/sorting))가 C로 구현된 비교 루프를 돌기 때문에 상수가 극히 작다. 반면 `clean_line` 은 파이썬 레벨 함수 호출 15만 번 + 정규식 엔진 진입을 15만 번 반복한다. **"이름이 무서운 연산"이 아니라 "파이썬 인터프리터 오버헤드가 15만 번 곱해지는 연산"이 실제 병목이다.** 이건 감으로는 절대 못 잡는다.
:::

`clean_line` 을 고쳐서 컴파일을 루프 밖으로 빼면 어떻게 될까? 감으로는 "정규식 컴파일은 무거우니 수십~수백 배 빨라지겠지"라고 기대하기 쉽다. 실제로 재 보자.

```python title="컴파일 위치만 다른 두 버전"
def parse_slow(lines):
    out = []
    for line in lines:
        pattern = re.compile(r"code=(\d+)")   # 매 반복마다 컴파일
        out.append(int(pattern.search(line).group(1)))
    return out


def parse_fast(lines):
    pattern = re.compile(r"code=(\d+)")       # 한 번만 컴파일
    out = []
    for line in lines:
        out.append(int(pattern.search(line).group(1)))
    return out
```

```pyrepl
>>> import time
>>> t0 = time.perf_counter(); parse_slow(lines); t1 = time.perf_counter()
>>> parse_fast(lines); t2 = time.perf_counter()
>>> t1 - t0, t2 - t1
(0.062, 0.027)          # 약 2.3배
```

(3회 반복 실측 범위: `parse_slow` 0.060~0.062초, `parse_fast` 0.027~0.028초, 배율 2.25~2.35배.)

2.3배는 개선이지만 기대했던 "수백 배"에는 한참 못 미친다. 이유는 `re` 모듈이 이미 컴파일된 패턴을 내부적으로 캐싱하기 때문이다.

::: deep re.compile은 이미 캐시된다
```pyrepl
>>> import re
>>> re._MAXCACHE
512
```
`re.compile(pattern)` 을 같은 문자열로 반복 호출하면, 실제 정규식 컴파일(NFA 구성)은 처음 한 번만 일어나고 이후엔 내부 딕셔너리에서 이미 만들어진 `Pattern` 객체를 찾아 반환한다. 그래서 "루프 안에서 compile 하면 안 된다"는 직관은 방향은 맞지만 **크기를 과대평가하기 쉽다.** 실제 비용은 컴파일이 아니라 매번 함수 호출 + 딕셔너리 조회를 반복하는 오버헤드다. 서로 다른 패턴을 512개 넘게 쓰는 코드라면 캐시가 밀려나면서 얘기가 완전히 달라진다.

**여기서 얻어야 할 교훈은 방향이 아니라 크기다.** "루프 밖으로 빼면 빨라진다"는 맞았지만 "얼마나"는 재 보기 전엔 아무도 모른다.
:::

이 절 전체의 원칙은 하나다. **어디가 느린지는 프로파일러가 말해 준다. 얼마나 빨라지는지는 `timeit`이 말해 준다. 둘 다 안 재고 고치는 건 도박이다.**

## timeit — 정확한 사용법과 함정

`timeit` 은 짧은 코드 조각의 실행 시간을 잰다. 반복 실행해서 노이즈를 줄이고, 기본적으로 **가비지 컬렉션을 꺼서** GC 개입으로 인한 흔들림을 없앤다.

```pyrepl
>>> import timeit
>>> timeit.timeit("sum(range(100))", number=100_000)
0.4213...
```

### 전역 vs 지역 — 첫 번째 함정

`timeit.timeit` 에 넘기는 문자열은 **완전히 새로운 이름공간**에서 실행된다. 지금 스코프의 이름은 안 보인다.

```python title="이름공간 함정"
data = list(range(50_000))

def sum_local():
    total = 0
    for x in data:
        total += x
    return total

timeit.timeit("sum_local()", number=200)
```

```pyrepl
NameError: name 'sum_local' is not defined
```

`sum_local` 이 분명히 같은 파일에 있는데도 못 찾는다. 두 가지 해법이 있다.

```python title="고친 두 가지 방법"
# 1) 지금 이름공간을 명시적으로 넘긴다
timeit.timeit("sum_local()", globals=globals(), number=200)

# 2) 호출 가능한 객체를 문자열 대신 직접 넘긴다 (더 간단하다)
timeit.timeit(sum_local, number=200)
```

::: warn 명령줄 timeit은 다르게 동작한다
`python -m timeit -s "import mymodule" "mymodule.f()"` 처럼 CLI로 쓸 때는 `-s`(setup)로 임포트를 미리 해 두면 된다. 이때는 스크립트 실행 시점의 `__main__` 네임스페이스를 그대로 쓰기 때문에 API로 쓸 때와 규칙이 살짝 다르다. **어느 쪽을 쓰든 "이 변수가 지금 어느 네임스페이스에 있는가"를 항상 의식하라.**
:::

### 전역 변수 접근과 지역 변수 접근 — 바이트코드는 다르지만 재 보면 확인해야 한다

[1.10 함수](#/functions)와 [3.7 바이트코드](#/bytecode)에서 봤듯, 함수 안의 지역 변수는 `LOAD_FAST` 로 배열 인덱싱하듯 접근하지만 모듈 전역 변수는 `LOAD_GLOBAL` 로 딕셔너리 조회를 거친다 — **바이트코드 명령어 자체는 다르다.** 그런데 "명령어가 다르니 실행 시간도 눈에 띄게 차이 날 것이다"는 짐작일 뿐이다. `timeit` 으로 직접 재 보자.

```pyrepl
>>> data = list(range(50_000))
>>> def local_version():
...     x = 0
...     for i in data:      # data는 전역, i·x는 지역
...         x = x + i
...     return x
>>> timeit.timeit("x=0\nfor i in data: x = x + i", globals=globals(), number=200)
0.113...
>>> timeit.timeit(local_version, number=200)
0.113...
```

이 절을 쓰면서 처음엔 "전역 루프 0.159초 vs 지역 함수 0.114초, 약 1.4배 차이"라는 수치를 실었다. 그런데 같은 코드를 Python 3.14.5 / Windows에서 반복 재현(단발 실행, `timeit.repeat(min, repeat=7~9)`, `number` 를 10배로 늘린 재확인까지 총 7회)해 보니 **매번 비율이 0.99~1.04배 사이였다 — 1.4배에 근접한 값은 한 번도 나오지 않았다.** 즉 최초 수치는 재현되지 않는 잘못된 실측이었다. **이 지식(LOAD_FAST vs LOAD_GLOBAL의 바이트코드 구조 차이)은 사실이지만, 지금 이 환경/버전에서는 그 차이가 눈에 보이는 벽시계 시간으로 거의 나타나지 않는다.** 원인은 정확히 확인하지 못했지만, CPython 3.11+ 의 적응형 인터프리터(PEP 659)가 `LOAD_GLOBAL` 을 캐싱해 딕셔너리 조회 비용을 크게 줄였을 가능성이 높다(이건 추측이지 실행으로 확인한 사실은 아니다).

**이 절 전체가 말하려는 원칙이 바로 이 실패 사례에서 다시 확인된다.** "구조상 이래야 한다"는 이론과 "실제로 이렇게 나온다"는 실측은 다른 질문이고, CPython 버전이 바뀌면 답도 바뀔 수 있다. 전역/지역 접근 자체를 핫 루프 최적화의 근거로 삼기 전에, 반드시 **당신의 인터프리터 버전에서 직접 재라.** [5.3 파이썬 레벨 최적화](#/py-optimize)에서 "핫 루프는 함수로 감싸라"는 조언을 다시 다루는데, 그 이유는 전역/지역 접근 속도 차이보다는 함수 호출 자체가 만드는 다른 최적화 여지(지역 변수 캐싱, 인터프리터 디스패치 감소) 쪽에 더 무게가 실린다는 점을 함께 봐라.

::: deep timeit이 내부적으로 하는 일
- 지정한 코드를 `number` 번 반복하는 루프를 **컴파일된 함수**로 만들어 실행한다. 인터프리터 파싱 오버헤드가 반복마다 들어가지 않게 하기 위해서다.
- 기본적으로 `gc.disable()` 을 호출한다. GC가 중간에 끼어들어 한 번만 유독 느린 샘플을 만드는 걸 막기 위해서다.
- 여러 번 돌려서 **평균이 아니라 최솟값**을 대표값으로 쓰는 게 관례다(`timeit.repeat`). 노이즈는 항상 위로만 튄다 — 다른 프로세스가 끼어들거나 캐시가 밀리면 느려지기만 하지, 원래보다 더 빨라질 일은 없다. 그래서 여러 번 잰 것 중 최솟값이 "코드 자체의 진짜 비용"에 가장 가깝다.

```pyrepl
>>> min(timeit.repeat(sum_local, number=200, repeat=5))
```
:::

## cProfile — 함수 단위로 병목을 찾는다

`timeit` 은 "이 코드 조각이 얼마나 걸리는가"를 잰다. 하지만 프로그램 전체에서 **어느 함수가** 시간을 먹는지는 알려주지 않는다. 그게 `cProfile` 의 역할이다. 위 파이프라인 예제에서 이미 한 번 봤다. 이번엔 컬럼을 정확히 읽어 보자.

```bash
python -m cProfile -s tottime pipeline.py
```

```text nolines
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   150000    0.063    0.000    0.176    0.000 pipeline.py:16(clean_line)
        1    0.060    0.060    0.182    0.182 pipeline.py:9(generate_lines)
   150000    0.049    0.000    0.122    0.000 random.py:335(randint)
   150000    0.036    0.000    0.058    0.000 random.py:245(_randbelow_with_getrandbits)
   150000    0.033    0.000    0.048    0.000 re/__init__.py:330(_compile)
```

- **`ncalls`** — 호출 횟수. `3/1` 처럼 분수로 나오면 재귀 호출이다(분모는 원시 호출, 분자는 총 호출).
- **`tottime`** — 그 함수 **자체 코드**에서만 쓴 시간. 하위 함수 호출 시간은 뺀다.
- **`cumtime`** — 그 함수와 **그 함수가 부른 모든 것**을 합친 시간.
- **`percall`** — 각각을 `ncalls` 로 나눈 값. 두 개(tottime 기준, cumtime 기준)가 있다.

`-s cumulative` 로 정렬하면 "이 함수 밑에서 전체적으로 얼마나 시간을 썼는가" 순으로, `-s tottime` 으로 정렬하면 "정확히 이 줄들 자체가 얼마나 무거운가" 순으로 본다. 재귀 함수나 깊은 호출 스택에서는 `tottime` 이 더 정직하다 — `cumtime` 은 하위 호출 전체를 끌어안기 때문에 얕은 래퍼 함수가 항상 상위권에 뜬다.

::: deep cProfile은 결정론적(deterministic) 프로파일러다
`cProfile` 은 CPython의 `sys.setprofile` 후킹 지점을 C 레벨로 구현한 것이다. **모든** 함수 호출(`CALL`)과 반환(`RETURN_VALUE`, [3.7 바이트코드](#/bytecode)에서 본 그 명령어들)마다 타이머를 찍는다. 그래서 숫자가 정확하고 재현 가능하다 — 같은 입력이면 같은 `ncalls` 가 나온다.

대가는 오버헤드다. 함수 호출 하나하나에 후킹 비용이 붙으므로, **함수 호출이 잦을수록** (재귀, 작은 헬퍼 함수 남발) 오버헤드가 커진다. 뒤에서 이 오버헤드를 직접 잰다.
:::

## pstats로 결과 다루기, snakeviz로 보기

터미널에 쏟아지는 출력을 그때그때 읽는 대신, 결과를 파일로 저장해서 코드로 다루면 편하다.

```python title="pstats로 상위 항목만 뽑기"
import cProfile
import pstats
from pipeline import main

pr = cProfile.Profile()
pr.enable()
main()
pr.disable()

pr.dump_stats("pipeline.prof")

stats = pstats.Stats("pipeline.prof")
stats.sort_stats("tottime")
stats.print_stats(5)
```

```text nolines
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   150000    0.063    0.000    0.176    0.000 pipeline.py:16(clean_line)
        1    0.060    0.060    0.182    0.182 pipeline.py:9(generate_lines)
   150000    0.049    0.000    0.122    0.000 random.py:335(randint)
   150000    0.036    0.000    0.058    0.000 random.py:245(_randbelow_with_getrandbits)
   150000    0.033    0.000    0.048    0.000 re/__init__.py:330(_compile)
```

`.prof` 파일은 텍스트가 아니라 마샬링된 통계 덩어리다. 함수 100개가 넘는 실전 프로그램에서는 이걸 텍스트로 읽는 것 자체가 고역이 된다. 그럴 때 `snakeviz` 를 쓴다.

```bash
uvx snakeviz pipeline.prof
```

브라우저가 열리고 함수별 시간을 **원형(icicle/sunburst) 다이어그램**으로 보여준다. 가운데(또는 왼쪽)가 `main`이고, 바깥으로 갈수록 하위 호출이며, **조각의 넓이가 곧 `cumtime` 비율**이다. 텍스트 표에서는 안 보이던 "이 함수가 전체의 몇 %인지"가 한눈에 들어온다. 이 문서는 브라우저 캡처를 실을 수 없어 화면을 보여주지 못한다 — 위 명령을 직접 돌려서 확인하라.

::: tip 언제 pstats/snakeviz까지 가는가
함수가 10개 안팎이면 터미널 출력으로 충분하다. 함수가 수십~수백 개거나 호출 그래프가 깊으면(프레임워크, ORM 등을 감싸는 코드) `snakeviz` 의 시각적 비율이 훨씬 빨리 눈에 들어온다. **처음부터 snakeviz로 시작하지 마라.** 터미널 출력으로 상위 5개만 봐도 병목이 바로 보이는 경우가 대부분이다.
:::

## line_profiler — 함수 안, 줄 단위로

`cProfile` 은 "`clean_line` 이 느리다"까지는 알려준다. 그런데 `clean_line` 은 세 줄이다. **그 세 줄 중 어디가 문제인가?** 이건 함수 단위 프로파일러가 답할 수 없는 질문이다. `line_profiler` 가 필요하다.

```bash
uv venv .venv --with line_profiler
uvx --with line_profiler python -m kernprof -l -v line_demo.py
```

대상 함수에 `@profile` 데코레이터를 붙인다.

```python title="line_demo.py"
@profile          # noqa: F821 — kernprof가 실행 시점에 주입한다
def clean_line(line):
    pattern = re.compile(r"code=(\d+)")
    m = pattern.search(line)
    return int(m.group(1)) if m else 0
```

실제로 5만 번 호출해서 나온 결과다.

```text nolines
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
     5     50000      71771.0      1.4     68.7      pattern = re.compile(r"code=(\d+)")
     6     50000      18102.2      0.4     17.3      m = pattern.search(line)
     7     50000      14555.9      0.3     13.9      return int(m.group(1)) if m else 0
```

세 줄 중 `compile` 호출 한 줄이 전체 시간의 **68.7%다.** `cProfile` 로는 "clean_line이 느리다"만 나오고 이 세부 배분은 안 보인다. 이게 line_profiler의 존재 이유다.

::: warn @profile은 평소엔 존재하지 않는 이름이다
`kernprof` 없이 그냥 `python line_demo.py` 로 실행하면 `NameError: name 'profile' is not defined` 로 죽는다. `kernprof -l` 이 실행 시점에 `profile` 이라는 이름을 전역에 주입해서 데코레이터로 쓸 수 있게 만드는 것뿐이다. 그래서 실전 코드에 `@profile` 을 박아 둔 채로 커밋하면 안 된다 — 다른 사람이 그냥 실행하면 즉시 터진다. 프로파일링이 끝나면 반드시 지워라.
:::

## py-spy — 이미 돌고 있는 프로세스를 밖에서 들여다보기

`cProfile` 과 `line_profiler` 는 둘 다 **코드 안에 들어가서** 잰다. 실행을 새로 시작해야 하고, 코드를 건드려야 한다(데코레이터, `enable()`/`disable()`). 그런데 이미 배포된 서버가 가끔 느려질 때, 재시작 없이 지금 이 순간 뭘 하고 있는지 보고 싶다면? `py-spy` 는 **외부에서 프로세스 메모리를 읽어** 파이썬 콜스택을 샘플링한다. 대상 프로세스의 코드는 한 줄도 안 건드린다.

먼저 오래 도는 프로세스를 하나 띄운다.

```python title="long_running.py"
def busy_loop(seconds):
    end = time.perf_counter() + seconds
    lines = [f"code={i}" for i in range(2000)]
    total = 0
    while time.perf_counter() < end:
        for line in lines:
            total += clean_line(line)
    return total
```

다른 터미널에서 PID를 찾아 붙는다.

```bash
uvx py-spy dump --pid 6112
```

```text nolines
Thread 14172 (active+gil)
    clean_line (long_running.py:7)
    busy_loop (long_running.py:17)
    <module> (long_running.py:23)
```

**한 번 스냅샷을 뜬 것**이다. 지금 이 순간 인터프리터가 어디에 있는지 정확히 보여준다. `(active+gil)` 표시를 눈여겨보라 — 지금 [GIL](#/gil)을 쥐고 실제로 바이트코드를 실행 중인 스레드라는 뜻이다. 스레드가 여럿인 프로그램에서 GIL을 누가 들고 있는지 바로 이렇게 확인한다.

한 번이 아니라 일정 시간 동안 계속 샘플링해서 어디에 시간이 몰리는지 보려면 `record` 를 쓴다.

```bash
uvx py-spy record --pid 6112 --duration 5 --output profile.svg
```

```text nolines
py-spy> Sampling process 100 times a second for 5 seconds.
py-spy> Wrote flamegraph data to 'profile.svg'. Samples: 499 Errors: 0
```

5초 동안 초당 100번, 총 499번 스택을 캡처해 SVG 불꽃그래프(flamegraph)로 저장한다. 폭이 넓은 막대일수록 그 함수가 샘플에 자주 잡혔다는 뜻 — 즉 시간을 많이 쓰고 있다는 뜻이다.

::: deep py-spy는 어떻게 프로세스 코드를 안 건드리고 스택을 읽는가
운영체제가 제공하는 프로세스 메모리 읽기 기능(Windows의 `ReadProcessMemory`, Linux의 `ptrace` 계열)으로 **대상 프로세스의 메모리를 밖에서 그대로 들여다본다.** CPython 인터프리터의 프레임 스택 구조를 알고 있으므로, 그 메모리 레이아웃을 해석해서 지금 실행 중인 파이썬 함수 이름들을 재구성한다. 대상 프로세스는 이 사실을 전혀 모른다 — 아무 훅도 안 걸리고, 코드 실행 흐름도 안 바뀐다. 그래서 프로덕션 서버에 **재시작 없이** 붙일 수 있는 것이다.
:::

## 프로파일러 자체의 비용

측정 도구도 공짜가 아니다. `cProfile` 은 모든 호출/반환마다 후킹하므로, 켜 두면 프로그램이 느려진다. 얼마나 느려지는지 직접 재 보자.

```pyrepl
>>> import time, cProfile
>>> from pipeline import main
>>> t0 = time.perf_counter(); main(); t1 = time.perf_counter()
>>> t1 - t0
0.1305...
>>> pr = cProfile.Profile()
>>> t0 = time.perf_counter(); pr.enable(); main(); pr.disable(); t1 = time.perf_counter()
>>> t1 - t0
0.3900...
```

같은 프로그램인데 `cProfile` 을 켰더니 **약 3배** 느려졌다. 함수 호출이 극단적으로 많은 코드에서는 더 심하다.

```pyrepl
>>> def fib(n):
...     return n if n < 2 else fib(n - 1) + fib(n - 2)
>>> t0 = time.perf_counter(); fib(30); t1 = time.perf_counter()
>>> raw = t1 - t0
>>> pr = cProfile.Profile()
>>> t0 = time.perf_counter(); pr.enable(); fib(30); pr.disable(); t1 = time.perf_counter()
>>> (t1 - t0) / raw
5.74...
```

재귀 호출 270만 번짜리 `fib(30)` 은 **5.7배 안팎**(재실행하면 5.6~5.9배 사이에서 흔들린다 — 둘 다 단발 측정값이라는 한계는 있다)으로, `pipeline.py` 사례(약 3배)보다 훨씬 크게 느려졌다. 오버헤드는 실행한 코드의 CPU 무게가 아니라 **함수 호출 횟수**에 비례한다 — 후킹 지점이 호출마다 하나씩 박히기 때문이다([3.7 바이트코드](#/bytecode)의 `CALL`/`RETURN_VALUE` 명령어를 떠올려라).

::: perf 세 도구의 오버헤드는 성격이 다르다 — 직접 잰 수치로 비교한다
- **`cProfile`** — 결정론적. 모든 호출을 후킹하므로 정확하지만, 호출 밀도가 높은 코드에서 3~6배(위 실측: pipeline.py 약 3배, fib(30) 약 5.7배) 느려질 수 있다. 절대 실행 시간을 그대로 믿지 마라. **상대 비율**(어느 함수가 몇 %인가)만 믿어라.
- **`line_profiler`** — `cProfile` 보다 오버헤드가 한 자릿수가 아니라 **거의 두 자릿수 배** 더 크다. 줄 단위로 후킹하기 때문이다. 실측: 5만 줄짜리 `clean_line` 루프를 그냥 돌리면 약 0.022초, `kernprof -l` 로 줄 단위 프로파일링을 켜고 돌리면 약 2.4초 — **약 110배 느려졌다.** 이 정도면 프로그램 전체에 걸어 두는 건 사실상 불가능하고, 그래서 프로그램 전체가 아니라 **의심 가는 함수 하나에만** `@profile` 을 붙이는 게 관례다.
- **`py-spy`** — 프로세스 안에서 아무것도 실행하지 않고 밖에서 스냅샷만 뜬다. 실측: `busy_loop`를 6초간 그냥 돌리면 약 2,960만 번 반복하고, 같은 프로세스에 `py-spy record --duration 5 --rate 100`을 붙여 놓고 돌려도 약 2,982만 번으로 **차이가 오차범위(1% 미만) 안이었다** — 대상 프로세스의 실행 속도에 측정 가능한 영향이 없다는 뜻이다. 그 대신 **정확도는 확률적이다** — 초당 100번만 찍으므로, 아주 짧게 실행되고 끝나는 함수는 놓칠 수 있다.

**정확도가 필요하면 `cProfile`, 어느 줄인지까지 봐야 하는데 전체를 걸면 너무 느려지니 의심 함수 하나만 골라서 `line_profiler`, 실행 흐름을 건드리면 안 되면(프로덕션) `py-spy`.** 이 트레이드오프를 이해하고 골라야 한다.
:::

## 마이크로 최적화에 시간 쓰지 마라

여기까지 읽고 "모든 함수를 다 프로파일링해서 1% 하나까지 쥐어짜야겠다"고 생각했다면 방향이 틀렸다. 위 파이프라인에서 `aggregate`(정렬)는 전체의 2.5%였다. **설령 그 함수를 마법처럼 무한히 빠르게 만들어도 전체 프로그램은 2.5%밖에 안 빨라진다.** 반면 `clean_line` 은 전체의 44%를 넘게 차지했다 — 여기를 고치는 게 시간 대비 효과가 훨씬 크다.

::: warn 프로파일러 없이 "느려 보이는 곳"부터 고치지 마라
실무에서 가장 흔한 시간 낭비 패턴은 이렇다. 리뷰어가 코드를 보다가 "이 리스트 컴프리헨션을 제너레이터로 바꾸면 빠를 것 같은데요"라고 말하고, 그 함수는 애초에 전체 실행 시간의 0.3%였다. **프로파일링 결과 없이 나온 최적화 제안은 전부 의심하라.** 이 절의 도구로 5분만 재 보면 어디를 고쳐야 할지, 그리고 고쳐서 얼마나 이득인지가 바로 숫자로 나온다. [5.2 메모리 모델](#/memory), [5.4 C 확장](#/c-ext), [5.5 Cython/Numba/mypyc](#/compilers) 로 넘어가기 전에 반드시 이 순서를 지켜라 — **측정 → 병목 확인 → 그 병목에만 도구 적용.**
:::

## 요약

- 감으로 짚은 병목은 자주 틀린다. `cProfile` 로 실제 `tottime`/`cumtime` 비율을 봐야 한다.
- `timeit` 문자열은 별도 네임스페이스에서 실행된다. `globals=globals()` 를 넘기거나 호출 가능한 객체를 직접 넘겨라.
- `cProfile` 은 함수 단위, `line_profiler` 는 줄 단위. 함수 하나가 의심스러운데 어느 줄인지 모를 때 `line_profiler` 로 내려간다.
- `py-spy` 는 코드를 건드리지 않고 실행 중인 프로세스에 외부에서 붙는다. 재시작할 수 없는 프로덕션 진단에 쓴다.
- 프로파일러 자체가 프로그램을 느리게 만든다(`cProfile`: 실측 3~6배). 절대 시간이 아니라 **상대 비율**을 봐라.
- 어떤 함수를 최적화해서 얻는 이득의 상한은 **그 함수가 전체에서 차지하는 비율**이다. 2%짜리 함수를 10배 빠르게 만들어도 전체는 1.8%만 빨라진다.

::: quiz 연습문제
1. 이 절의 `pipeline.py` 를 그대로 실행하고 `cProfile` 로 프로파일링하라. 당신 기기에서 `clean_line`, `generate_lines`, `aggregate` 각각이 전체의 몇 %인지 계산하라.
2. `timeit.timeit("f()")` 를 실행했을 때 `NameError` 가 나는 이유를 한 문장으로 설명하라. 그리고 두 가지 해법을 써 보라.
3. `re.compile` 을 루프 안에서 호출하는 것이 "생각보다 덜 느린" 이유는 무엇인가? `re._MAXCACHE` 를 확인하고 답하라.
4. `cProfile` 로 잰 실행 시간과 `time.perf_counter()` 로 잰 순수 실행 시간을 비교해서, 당신의 컴퓨터에서 어떤 함수의 오버헤드 배율이 얼마나 되는지 직접 재라. 함수 호출 횟수를 늘리면(예: 재귀 깊이를 늘리면) 배율이 어떻게 변하는지도 확인하라.
5. 어떤 함수가 프로그램 전체 실행 시간의 4%를 차지한다. 그 함수를 완벽하게 최적화해서 실행 시간을 0으로 만들었다고 하자. 프로그램 전체는 몇 % 빨라지는가? 이 계산이 왜 "무엇을 먼저 최적화할지" 결정하는 데 중요한지 설명하라.
:::

**다음 절**: [5.2 메모리 모델과 측정](#/memory) — 참조 카운팅과 GC를 `tracemalloc`으로 직접 들여다보고, 메모리 누수를 실제로 잡는다.
