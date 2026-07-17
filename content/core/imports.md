# 1.19 모듈, 패키지, import 시스템

::: lead
`import` 한 줄은 당신이 생각하는 것보다 훨씬 많은 일을 한다. 파일을 찾고, 컴파일하고, 실행하고, 캐시에 등록하는 네 단계짜리 파이프라인이다. 이걸 모르면 순환 import 에러를 만났을 때 코드를 이리저리 옮기며 운에 맡기게 되고, `python foo.py` 와 `python -m foo` 가 왜 다른 결과를 내는지 설명하지 못한다. 이 절은 그 파이프라인을 열어서 보여준다.
:::

## import 는 캐시 조회다

`import json` 을 두 번 실행하면 무슨 일이 일어날까. 실측해 보자.

```python title="import_cache.py"
import time
import sys

t0 = time.perf_counter()
import json
t1 = time.perf_counter()
import json as json2
t2 = time.perf_counter()

print("첫 import:", round((t1 - t0) * 1000, 4), "ms")
print("두번째 import:", round((t2 - t1) * 1000, 4), "ms")
print("같은 객체인가:", json is json2)
```

```text nolines
첫 import: 12.2727 ms
두번째 import: 0.0005 ms
같은 객체인가: True
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 **약 24000배** 차이나는 자릿수는 재현된다.)

첫 번째 `import json` 은 파일을 찾고, 파싱하고, 바이트코드로 컴파일하고, 그 모듈의 최상위 코드를 실제로 실행한다. 두 번째 `import json` 은 이 전부를 건너뛴다. **`import` 문은 "실행해라"가 아니라 "이 모듈이 필요하다"는 요청이고, 인터프리터는 `sys.modules` 라는 딕셔너리부터 확인한다.** 이미 있으면 그 객체를 그대로 이름에 묶는다.

```pyrepl
>>> import sys
>>> "json" in sys.modules
True
>>> sys.modules["json"] is json
True
```

`import` 가 실제로 하는 일을 순서대로 풀면 이렇다.

```text nolines
import json 실행

1. sys.modules 에 "json" 이 있나?
      Yes ──▶ 그 객체를 그대로 쓴다. 끝.
      No  ──▶ 2번으로
2. sys.meta_path 에 있는 파인더(finder)들에게 순서대로 물어본다.
      "json" 을 로드할 수 있는 로더(loader)를 아는 파인더가 있나?
3. 찾은 로더로 모듈 객체를 만들고, 먼저 sys.modules["json"] 에 등록한다.
      (실행 전에 등록! 이게 순환 import 를 이해하는 열쇠다)
4. 그 모듈 객체의 __dict__ 를 전역 네임스페이스로 삼아 소스 코드를 실행한다.
5. 실행이 끝난 모듈 객체를 호출한 쪽 이름에 묶는다.
```

::: deep 파인더와 로더 — sys.meta_path
"어디서 찾을지"와 "어떻게 로드할지"는 분리된 책임이다. **파인더**(finder)는 이름에 해당하는 모듈의 위치를 찾고, **로더**(loader)는 그 위치에서 실제로 코드를 읽어 실행한다.

```pyrepl
>>> import sys
>>> for f in sys.meta_path:
...     print(f)
...
<class '_frozen_importlib.BuiltinImporter'>
<class '_frozen_importlib.FrozenImporter'>
<class '_frozen_importlib_external.PathFinder'>
```

(3.14.5 기준 실측. 순서가 곧 탐색 순서다.)

- `BuiltinImporter` — `sys`, `builtins` 처럼 C로 구현되어 인터프리터에 내장된 모듈.
- `FrozenImporter` — 바이트코드 형태로 인터프리터 안에 냉동(freeze)되어 있는 모듈. `importlib._bootstrap` 자신이 그 예다.
- `PathFinder` — 우리가 아는 보통의 `.py` 파일. `sys.path` 를 순서대로 뒤진다.

**`sys.path` 를 아무리 조작해도 내장 모듈보다 먼저 검색되지 않는다.** 앞의 둘이 먼저 물어보기 때문이다. `sys.meta_path` 에 파인더를 추가하면 `import` 문을 가로챌 수 있다 — 네트워크에서 모듈을 받아오거나, zip 안의 모듈을 로드하는 등의 확장이 전부 이 지점에 훅을 건다.
:::

## sys.path — 검색 순서는 우연이 아니다

`PathFinder` 가 뒤지는 `sys.path` 는 특정 순서로 조립된다. 순서가 왜 중요한가? **먼저 발견되는 것이 이긴다.** 프로젝트 폴더에 실수로 `random.py` 를 만들면 표준 라이브러리의 `random` 대신 그 파일이 임포트된다 — 실제로 자주 일어나는 사고다.

```pyrepl
>>> import sys
>>> for p in sys.path:
...     print(p)
'C:\\...\\importlab'
'C:\\...\\pythoncore-3.14-64\\python314.zip'
'C:\\...\\pythoncore-3.14-64\\DLLs'
'C:\\...\\pythoncore-3.14-64\\Lib'
'C:\\...\\pythoncore-3.14-64'
'C:\\...\\pythoncore-3.14-64\\Lib\\site-packages'
```

(경로는 실행 환경마다 다르다. 중요한 건 **순서의 종류**다.)

조립 순서는 이렇다.

```text nolines
sys.path[0]                <- 실행 방식에 따라 결정 (아래에서 자세히)
PYTHONPATH 환경변수의 각 경로   <- 설정했을 때만
표준 라이브러리 경로들
site-packages               <- pip/uv로 설치한 서드파티 패키지
.pth 파일이 추가한 경로들      <- site-packages 안의 특수 파일
```

`sys.path[0]` 이 정해지는 규칙이 실전에서 가장 자주 혼란을 준다. 세 가지 실행 방식을 직접 비교한다.

```pyrepl
>>> import sys
>>> sys.path[0]        # python -c "..." 로 실행했을 때
''
```

빈 문자열 `''` 는 **"현재 작업 디렉터리"** 를 뜻한다. `-c` 옵션과 REPL은 이렇게 동작한다.

```python title="pathcheck.py"
import sys
print(repr(sys.path[0]))
```

```bash
python pathcheck.py
```

```text nolines
'C:\...\importlab'    <- pathcheck.py 가 들어 있는 디렉터리 (절대경로)
```

**스크립트로 직접 실행하면 `sys.path[0]` 은 그 스크립트 파일이 들어 있는 디렉터리다.** 현재 작업 디렉터리가 아니다. 이 둘이 다른 폴더면 헷갈리기 쉽다.

```bash
python -m pathcheck
```

```text nolines
'C:\...\scratchpad\importlab'   <- 스크립트 위치가 아니라, -m 을 실행한 현재 디렉터리
```

`-m` 으로 실행하면 `sys.path[0]` 은 **명령을 실행한 현재 작업 디렉터리**다. `pathcheck.py` 가 하위 폴더 `sub/` 에 있고 `python -m sub.pathcheck` 로 실행해도 마찬가지로, `sys.path[0]` 은 `sub/` 가 아니라 그 상위인 실행 위치 그대로다. `-m` 은 파일 경로가 아니라 **점(`.`)으로 구분된 모듈 이름**을 받아서, `sys.path` 위를 이름으로 검색하기 때문이다.

::: cote 코딩테스트에서 이게 왜 중요한가
여러 파일로 나뉜 프로젝트를 로컬에서 테스트할 때 `ModuleNotFoundError` 가 나면, 거의 항상 `sys.path[0]` 이 기대와 다른 경우다. **`python 폴더/파일.py` 로 실행하면서 그 폴더 안에서 상위 패키지를 상대 import 하려 하면 실패한다.** 다음 절의 `__main__` 이야기가 바로 이 문제를 설명한다.
:::

## 절대 import 와 상대 import

패키지 안에서 형제 모듈을 부르는 두 가지 방법이 있다.

```python title="pkg/main.py — 절대 import"
import pkg.helper
from pkg import helper
```

```python title="pkg/main.py — 상대 import"
from . import helper       # 같은 패키지
from .. import sibling     # 부모 패키지
from .sub import thing     # 하위 패키지
```

절대 import 는 `sys.path` 를 기준으로 전체 경로를 명시한다. 상대 import 는 **현재 모듈의 `__name__`(정확히는 `__package__`)을 기준으로 상대 위치를 계산한다.** 이게 핵심이다 — 상대 import 가 동작하려면 그 모듈이 **패키지의 일부로서 import 되어 있어야** 한다. 파일로 직접 실행된 모듈은 패키지 소속이 없다.

## `__main__` 과 `-m` — 가장 흔한 혼란

다음 셋은 각각 결과가 다르다. 직접 확인해 보자.

```python title="pkg/__init__.py (내용 없음)"
```

```python title="pkg/helper.py"
def greet():
    return "hello from helper"
```

```python title="pkg/main.py"
from . import helper

if __name__ == "__main__":
    print(helper.greet())
```

```bash
python pkg/main.py
```

```text nolines
Traceback (most recent call last):
  ...
    from . import helper
ImportError: attempted relative import with no known parent package
```

```bash
python -m pkg.main
```

```text nolines
hello from helper
```

(3.14.5 실측. 두 명령의 유일한 차이가 결과를 갈랐다.)

**왜 이렇게 갈리는가.** 인터프리터가 실행하는 파일이 무엇이든, 그 모듈의 이름은 항상 `__main__` 으로 등록된다 — 원래 이름이 무엇이었는지는 버려진다.

- `python pkg/main.py`: `main.py` 를 파일 경로로 직접 열어 실행한다. 이 모듈의 `__name__` 은 `"__main__"` 이고, `__package__` 는 `None` 이다. 자신이 `pkg` 패키지에 속한다는 정보 자체가 없다. `from . import helper` 는 "현재 패키지의 형제"를 찾으려 하는데 **현재 패키지가 없으므로** 실패한다.
- `python -m pkg.main`: 인터프리터가 먼저 `pkg.main` 을 **정상적인 모듈 이름으로 검색해서 import** 한다. 이 과정에서 `pkg` 패키지가 먼저 import 되고 `pkg.main` 의 `__package__` 가 `"pkg"` 로 설정된다. 그런 다음에야 그 모듈을 `__main__` 으로 실행한다. 상대 import 가 가리킬 "현재 패키지"가 존재하므로 동작한다.

::: warn __main__ 으로 실행된 모듈은 두 번째 이름을 가질 수 있다
더 미묘한 함정이 있다. 스크립트를 직접 실행하는 중에, **그 스크립트가 자기 자신을 이름으로 다시 import 하면 완전히 별개의 모듈 객체가 하나 더 생긴다.**

```python title="check_double.py"
import sys

print("이 모듈의 __name__:", __name__)

if __name__ == "__main__":
    import check_double as m
    print("id 비교 (같은 모듈인가):", m.__dict__ is sys.modules["__main__"].__dict__)
```

```bash
python check_double.py
```

```text nolines
이 모듈의 __name__: __main__
이 모듈의 __name__: check_double
id 비교 (같은 모듈인가): False
```

(3.14.5 실측.)

**`이 모듈의 __name__:` 이 두 번 찍힌다는 점 자체가 증거다.** `False` 가 나오는 이유는 `sys.modules` 가 **이름으로** 캐시하기 때문이다. `python check_double.py` 로 실행할 때 이 모듈은 `sys.modules["__main__"]` 에만 등록되고, `sys.modules["check_double"]` 에는 아무것도 없다. 그래서 스크립트 안에서 `import check_double` 을 하면 캐시 조회가 실패하고, **완전히 새로 파일을 읽어 처음부터 실행한다.** 그 재실행 과정에서 모듈 최상위의 `print("이 모듈의 __name__:", __name__)` 줄이 다시 돌아가고, 이번엔 `__name__` 이 `"check_double"` 이므로 두 번째 줄이 그렇게 찍힌다. 결과: 모듈 최상위 코드가 두 번 실행되고, 전역 변수도 두 벌이 생긴다. 클래스 정의도 두 번 일어나서 `isinstance` 비교가 예상치 못하게 실패하는 사고로 이어질 수 있다.

**교훈**: 직접 실행할 스크립트와, 다른 곳에서 import 될 모듈을 같은 파일로 만들지 마라. 실행 진입점은 얇게 두고(`if __name__ == "__main__": main()`), 로직은 별도 모듈에 둔 뒤 그걸 import 해서 쓴다.
:::

## `__init__.py` 와 네임스페이스 패키지

`__init__.py` 가 있는 디렉터리는 **일반 패키지**(regular package)다. 이 파일은 패키지가 import 될 때 실행되고, 그 안에서 하위 모듈을 미리 import 해 두면 사용자가 더 짧은 경로로 접근할 수 있게 만들 수 있다.

```python title="mypkg/__init__.py"
from .core import main_function   # mypkg.main_function 으로 바로 접근 가능
```

3.3부터는 `__init__.py` 가 **없어도** 디렉터리를 패키지로 취급한다 — **네임스페이스 패키지**(namespace package, PEP 420)다.

```pyrepl
>>> import nspkg          # nspkg/ 안에 __init__.py 없음, mod.py만 있음
>>> nspkg
<module 'nspkg' (namespace) from ['C:\\...\\importlab\\nspkg']>
>>> nspkg.__file__ is None
True
>>> type(nspkg.__path__)
<class '_frozen_importlib_external._NamespacePath'>
```

(3.14.5 실측.)

일반 패키지와 다른 점이 눈에 띈다. **`__file__` 이 없다**(대응하는 소스 파일이 없으니까). `__path__` 도 보통의 리스트가 아니라 `_NamespacePath` 객체다 — `sys.path` 가 바뀌면 다시 계산되도록 동적으로 동작한다.

::: deep 네임스페이스 패키지가 존재하는 이유
같은 이름의 패키지를 **여러 디렉터리에 나눠서** 배포하고 싶은 경우가 있다. 회사 하나가 `company.web`, `company.db` 를 별도 배포판으로 나눠 배포하되, 사용자 입장에서는 둘 다 `company` 라는 하나의 네임스페이스 아래 있는 것처럼 보이게 하고 싶을 때다. `__init__.py` 가 있는 일반 패키지는 정의상 **디렉터리 하나에만** 묶이므로 이게 불가능했다. PEP 420은 `__init__.py` 없는 디렉터리들을 **같은 이름이면 하나의 논리적 패키지로 합쳐서** 이 문제를 풀었다.

대가도 있다. `__init__.py` 가 없으면 "여기서 초기화 코드를 실행한다"는 지점이 없고, 실수로 만든 빈 폴더가 조용히 패키지처럼 동작해 버그를 감출 수 있다. **일반적인 프로젝트에서는 여전히 `__init__.py` 를 명시적으로 두는 편이 낫다.** 네임스페이스 패키지는 정말로 배포 단위를 쪼개야 하는 라이브러리 설계에서 쓰는 도구다.
:::

## 순환 import — 왜 나고 어떻게 푸는가

두 모듈이 서로를 import 하면 무슨 일이 벌어지는지 직접 만들어서 본다.

```python title="circ_a.py"
print("circ_a: 시작")
import circ_b
print("circ_a: circ_b 임포트 끝, circ_b.X =", circ_b.X)

X = "A"
print("circ_a: 끝")
```

```python title="circ_b.py"
print("circ_b: 시작")
import circ_a
print("circ_b: circ_a 모듈 객체 =", circ_a)

X = "B"
print("circ_b: 끝")
```

```bash
python circ_a.py
```

```text nolines
circ_a: 시작
circ_b: 시작
circ_a: 시작
Traceback (most recent call last):
  ...
    print("circ_a: circ_b 임포트 끝, circ_b.X =", circ_b.X)
                                                  ^^^^^^^^
AttributeError: module 'circ_b' has no attribute 'X' (consider renaming 'C:\...\circ_b.py' if it has the same name as a library you intended to import)
```

(3.14.5 실측. `circ_a: 시작` 이 두 번 찍히는 건 앞서 본 `__main__` 이중 등록과 같은 이유다 — 여기서는 본질과 무관하니 무시하고 아래 논리에 집중해라. 괄호 안의 "consider renaming ..." 제안 문구는 3.10 무렵부터 `AttributeError` 에 붙기 시작한 힌트로, "혹시 이 이름이 표준 라이브러리/서드파티 패키지와 겹치는 로컬 파일이 아니냐"고 묻는 것이다 — 지금 이 상황은 진짜 순환 import 문제이지 이름 충돌이 아니므로 이 제안은 무시하면 된다. 핵심 메시지는 앞부분 `has no attribute 'X'` 다.)

여기서 벌어진 일을 **3단계 캐시 등록** 규칙으로 다시 읽어보자.

```text nolines
1. circ_a 실행 시작. sys.modules["circ_a"] 에 "실행 중"인 빈 모듈 객체가 먼저 등록된다.
2. circ_a 의 2번째 줄에서 import circ_b.
3. circ_b 가 sys.modules 에 없으므로 새로 실행 시작.
      sys.modules["circ_b"] 에 등록 (아직 텅 빈 상태).
4. circ_b 의 2번째 줄에서 import circ_a.
      sys.modules 를 보니 "circ_a" 가 이미 있다!
      ──▶ 그 모듈 객체를 그대로 가져온다. (아직 X = "A" 줄까지 실행 안 된 상태)
5. circ_b 는 이 "미완성 circ_a" 를 circ_a 라는 이름에 묶고 계속 진행한다.
      circ_b 는 문제없이 끝까지 실행된다 (circ_a 의 속성을 안 건드렸으니까).
6. 제어가 circ_a 로 돌아온다. circ_b.X 에 접근하려 한다.
      circ_b 는 이미 완전히 실행됐으므로 X = "B" 가 있다 → 성공.
```

이 예제에서 실제로 깨진 지점은 반대쪽이다. `circ_a` 의 3번째 줄이 `circ_b.X` 를 참조하는 시점에 `circ_b` 는 이미 끝까지 실행된 뒤라 `X = "B"` 가 있어야 정상이다. 그런데 트레이스백은 `circ_b` 에 `X` 가 없다고 말한다 — 왜인가. **`circ_b` 가 실행되는 도중 `import circ_a` 를 만났을 때, 그 시점의 `circ_a` 는 아직 `X = "A"` 줄에 도달하지 못한 미완성 모듈이었다.** 이 예제 구조상 두 모듈이 정확히 대칭이라, 실제로 실행해 보면 어느 파일을 먼저 실행하느냐에 따라 어느 쪽의 `X` 가 없다고 나올지 갈린다 — **핵심은 어느 쪽이 실패하느냐가 아니라, "아직 만들어지지 않은 이름"을 참조하는 순간 반드시 터진다는 것**이다.

**핵심 원칙**: 순환 import 자체는 에러가 아니다. `sys.modules` 캐시 덕분에 무한 루프에 빠지지는 않는다. 문제는 **A가 B를 import 하는 시점에, B가 아직 정의하지 않은 이름에 접근하려는 것**이다. 모듈 최상위(전역 스코프)에서 상대방의 이름을 즉시 쓰려고 하면 거의 항상 이 문제에 걸린다.

### 순환 import를 푸는 세 가지 방법

```python title="방법 1 — 함수 안으로 옮긴다 (지연 바인딩)"
# circ_b.py
import circ_a

def use_a():
    return circ_a.X    # 호출되는 시점에는 circ_a 가 완주해 있다
```

모듈이 로드되는 시점에는 `circ_a.X` 에 접근하지 않고, 함수가 **나중에 호출될 때** 접근한다. 그때는 두 모듈 다 완전히 로드된 뒤이므로 안전하다. 가장 흔하고 가장 권장되는 해법이다.

```python title="방법 2 — import 자체를 함수 안으로 옮긴다 (지연 import)"
# circ_b.py
def use_a():
    import circ_a       # 호출될 때 비로소 import
    return circ_a.X
```

두 모듈이 최상위에서 서로를 아예 몰라도 되게 만든다. 순환 구조 자체를 깨는 대신 숨기는 방식이라, 남용하면 의존 관계가 코드를 다 읽어야만 보이게 된다.

```python title="방법 3 — 공통 의존성을 제3의 모듈로 뽑는다 (구조 개선)"
# 진짜 원인은 보통 설계다: A와 B가 서로를 알아야 하는 게 아니라,
# 둘 다 공유하는 개념(타입, 상수)이 있는데 그걸 어느 한쪽에 억지로 넣은 것이다.
# common.py 로 그 개념을 뽑아내면 A, B 모두 common만 import 하면 된다.
```

::: hist 왜 파이썬은 순환 import를 아예 막지 않았나
컴파일 언어라면 링크 단계에서 전체 의존 그래프를 미리 알 수 있어 순환을 사전에 차단하기 쉽다. 파이썬은 **모듈을 위에서 아래로 한 줄씩 즉시 실행하는 인터프리터**다. import 시점에 "이 모듈이 최종적으로 어떤 이름들을 갖게 될지"를 미리 알 방법이 없다 — 실행해봐야 안다. 그래서 파이썬은 순환 자체를 막는 대신, **부분적으로 실행된 모듈이라도 캐시에 걸어 두고 그대로 진행**하는 실용적인 타협을 택했다. 대부분의 경우 이 타협은 아무 문제도 안 만든다 — 함수 본문 안에서만 상대방을 쓰면, 그 함수가 호출되는 시점엔 이미 양쪽 다 완성돼 있기 때문이다.
:::

## 지연 import — 순환 회피를 넘어선 이유

지연 import(lazy import)는 순환을 피하는 용도 외에, **비용을 미룬다**는 독립적인 이유로도 쓴다.

```python title="무거운 의존성을 정말 쓸 때만 로드"
def convert_to_dataframe(rows):
    import pandas as pd     # 이 함수가 실제로 호출될 때만 로드
    return pd.DataFrame(rows)
```

`pandas`, `torch`, `matplotlib` 같은 무거운 패키지를 모듈 최상위에서 import 하면, **그 기능을 한 번도 안 쓰는 실행 경로에서도 로드 비용을 무조건 낸다.** CLI 도구가 서브커맨드 10개 중 하나만 pandas를 쓴다면, 나머지 9개 커맨드를 실행할 때도 매번 pandas 로딩 시간을 물어야 한다. 함수 안으로 옮기면 그 서브커맨드가 실제로 선택됐을 때만 비용을 낸다.

::: warn 지연 import 를 습관으로 삼지 마라
함수 본문의 지연 import 는 **가독성 비용**을 낸다. 이 모듈이 무엇에 의존하는지 파일 맨 위만 봐서는 알 수 없어진다. 순환 import 회피나, 무거운 선택적 의존성(옵션 기능) 같은 **구체적인 이유가 있을 때만** 쓰고, 이유를 주석으로 남겨라. 이 함정은 [1.10 함수](#/functions)의 클로저·스코프 논의와도 이어진다 — 지연 import 로 만든 이름도 결국 지역 스코프의 이름 바인딩일 뿐이다.
:::

## `importlib` — import 시스템을 코드로 다루기

`import` 문은 컴파일 타임에 이름이 고정된다. 모듈 이름을 **런타임에 문자열로** 정해야 하면 `importlib` 을 쓴다.

```pyrepl
>>> import importlib
>>> mod = importlib.import_module("json")
>>> mod is __import__("json")
True
```

`import` 문 자체도 내부적으로는 `__import__` 라는 내장 함수 호출로 컴파일된다. `importlib.import_module` 은 그 위에 상대 import(`package=` 인자)까지 지원하는 사용하기 쉬운 래퍼다.

가장 실전적으로 쓰이는 건 `importlib.reload` 다.

```pyrepl
>>> import importlib
>>> import reload_test
>>> reload_test.VALUE
1
```

파일을 고쳐서 `VALUE = 2` 로 바꾼 뒤:

```pyrepl
>>> import reload_test        # 그냥 다시 import — 캐시라서 안 바뀐다
>>> reload_test.VALUE
1
>>> importlib.reload(reload_test)   # 강제로 다시 실행
<module 'reload_test' from 'C:\\...\\reload_test.py'>
>>> reload_test.VALUE
2
```

(3.14.5 실측.)

**`reload(...)` 줄 바로 다음에 찍힌 `<module 'reload_test' ...>` 를 놓치지 마라.** `import reload_test` 문(statement)은 REPL에 아무것도 에코하지 않지만, `importlib.reload(reload_test)` 는 **표현식(expression)으로서 호출**되었고 `reload()` 는 non-None 값 — 다시 실행된 그 모듈 객체 자신 — 을 반환한다. REPL은 bare expression의 반환값이 `None` 이 아니면 항상 그 `repr()` 을 자동으로 에코한다(위 `sys.path[0]`, `nspkg` 예제에서 본 것과 같은 규칙이다). `import` 문과 `reload()` 호출이 결과적으로 비슷한 일을 하는 것처럼 보여도, 전자는 문이라 값이 없고 후자는 함수 호출식이라 값이 있다는 차이가 REPL 출력에 그대로 드러난다.

`reload` 는 **같은 모듈 객체를 재사용하면서 그 안의 소스를 다시 실행**한다. 새 모듈 객체를 만드는 게 아니라서, 다른 곳에서 이미 `from reload_test import VALUE` 로 값을 복사해 간 코드는 갱신되지 않는다 — 이름 바인딩은 그 시점의 객체를 가리켰을 뿐이니까([1.1 객체, 이름, 참조](#/objects-names)). Jupyter의 `autoreload` 확장이나 웹 프레임워크의 개발 서버가 하는 일이 바로 이 `reload` 호출이고, 위와 같은 한계 때문에 프로덕션에서는 절대 쓰지 않는다 — 재시작이 유일하게 안전한 방법이다.

## 모듈 레벨 `__getattr__` (PEP 562)

클래스에 `__getattr__` 이 있으면 속성이 없을 때 호출된다는 건 [1.14 특수 메서드](#/dunder)에서 다룬다. **모듈에도 같은 훅을 쓸 수 있다.** 3.7부터다.

```python title="lazy_mod.py"
print("lazy_mod: 모듈 본문 실행 (여기가 import 시점)")

def __getattr__(name):
    if name == "EXPENSIVE":
        print("lazy_mod: EXPENSIVE 처음 접근 -> 지금 계산한다")
        value = sum(range(1000))
        globals()[name] = value   # 캐싱: 다음부터는 __getattr__ 를 안 거친다
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

```pyrepl
>>> import lazy_mod
lazy_mod: 모듈 본문 실행 (여기가 import 시점)
>>> lazy_mod.EXPENSIVE
lazy_mod: EXPENSIVE 처음 접근 -> 지금 계산한다
499500
>>> lazy_mod.EXPENSIVE
499500
```

(3.14.5 실측. 두 번째 접근에서는 "처음 접근" 메시지가 **안 찍힌다** — `globals()[name] = value` 가 모듈의 실제 속성으로 값을 박아 넣어서, 다음부터는 평범한 속성 조회로 끝나고 `__getattr__` 까지 가지도 않는다.)

이 패턴이 실전에서 쓰이는 곳은 크다.

- **선택적 의존성 지연**: 패키지의 서브모듈 중 무거운 것(예: 시각화 전용 서브모듈)을 최상위 `__init__.py` 에서 바로 import 하지 않고, 실제로 접근될 때만 로드한다.
- **Deprecation 경고**: 옛 이름으로 접근하면 경고를 띄우고 새 이름으로 안내한 뒤 실제 값을 돌려준다.
- **`__dir__` 과 짝을 이룬다**: 모듈 레벨 `__dir__` 을 같이 정의하면 `dir(module)` 이나 자동완성에도 지연 속성을 노출할 수 있다.

::: deep PEP 562 이전에는 어떻게 했나
모듈은 하나의 객체이므로, 원래는 그 객체의 클래스를 바꿔야 `__getattr__` 을 걸 수 있었다 — `sys.modules[__name__] = SomeModuleSubclass(...)` 같은 트릭이다. `types.ModuleType` 을 상속한 가짜 클래스를 만들어 `sys.modules` 에 있는 자기 자신을 그 인스턴스로 바꿔치기하는, 읽기 괴로운 코드였다. PEP 562는 모듈 안에 그냥 함수 `__getattr__` 을 정의하면 인터프리터가 자동으로 그걸 속성 조회 실패 시 호출해 주도록 **언어 차원에서 지원**했다. 같은 메타프로그래밍을 [3.5 `__getattr__` 계열과 동적 속성](#/dynamic-attrs)에서 클래스 레벨까지 확장해서 다룬다.
:::

## 종합: `sys.path`, 캐시, `__main__` 을 한 번에

지금까지 조각을 하나의 실행 흐름으로 합쳐 보자. 흔한 프로젝트 구조를 생각한다.

```text nolines
project/
├── pyproject.toml
└── src/
    └── mypkg/
        ├── __init__.py
        ├── core.py
        └── cli.py         <- if __name__ == "__main__" 진입점
```

`python src/mypkg/cli.py` 로 실행하면: `sys.path[0]` 은 `src/mypkg/` 가 되고, `cli` 모듈은 `__main__` 으로 등록되며 `__package__` 는 `None` 이다. `cli.py` 안에서 `from . import core` 를 쓰면 즉시 `ImportError` 다 — 앞서 본 것과 정확히 같은 이유다.

`python -m mypkg.cli` 를 `src/` 디렉터리에서 실행하면(또는 `pyproject.toml` 로 패키지를 설치해 `sys.path` 에 `src` 를 넣으면): `mypkg` 가 먼저 정상 패키지로 import 되고, `mypkg.cli` 의 `__package__` 는 `"mypkg"` 로 설정된다. 상대 import 가 정상 동작한다.

**실무 규칙**: 패키지 안에서 상대 import 를 쓸 계획이라면, 그 패키지의 진입점은 항상 `-m` 으로 실행하거나, `pyproject.toml` 의 `[project.scripts]` 로 설치해서 진짜 콘솔 스크립트로 실행해라. 파일 경로로 직접 실행하는 건 최상위 스크립트(패키지 바깥의, 아무도 import 하지 않을 파일)에만 써라.

## 요약

- `import` 는 매번 실행하는 게 아니라 **`sys.modules` 캐시를 먼저 확인**한다. 캐시 히트는 사실상 공짜다(위 실측에서 약 24000배 차이).
- `sys.meta_path` 의 파인더들(`BuiltinImporter` → `FrozenImporter` → `PathFinder`)이 순서대로 모듈을 찾는다. `sys.path` 는 그중 `PathFinder` 가 쓰는 목록이다.
- `sys.path[0]` 은 실행 방식에 따라 다르다 — `-c`/REPL은 `''`(cwd), 파일 직접 실행은 그 파일의 디렉터리, `-m` 은 현재 작업 디렉터리.
- 상대 import 는 `__package__` 가 있어야 동작한다. 파일로 직접 실행된 모듈(`__main__`)은 `__package__` 가 없어서 실패한다 — 이게 `python foo.py` vs `python -m foo` 혼란의 정체다.
- 순환 import 는 캐시 덕분에 무한 루프에 빠지지 않지만, **아직 정의되지 않은 이름을 모듈 최상위에서 참조하면** 터진다. 함수 본문으로 참조를 미루면 대부분 풀린다.
- 지연 import 는 순환 회피뿐 아니라 무거운 의존성의 로딩 비용을 실제로 쓸 때까지 미루는 데도 쓴다. 다만 남용하면 의존 관계가 안 보인다.
- 모듈 레벨 `__getattr__`(PEP 562)로 속성 접근을 가로채 지연 로딩·deprecation 경고를 구현할 수 있다.
- `importlib.import_module` 로 문자열 이름의 모듈을 동적으로 로드하고, `importlib.reload` 로 같은 모듈 객체를 재실행할 수 있다 — 단, 이미 복사돼 나간 이름은 갱신되지 않는다.

::: quiz 연습문제
1. 프로젝트 루트에 `email.py` 라는 파일을 실수로 만들었다고 하자. 같은 폴더에서 `python -c "import email"` 을 실행하면 표준 라이브러리 `email` 대신 이 파일이 import 되는가? 왜 그런지 `sys.path` 조립 순서로 설명하라.

2. 다음 두 모듈이 있다.

   ```python title="a.py"
   import b
   def get_b_value():
       return b.VALUE
   VALUE = "A"
   ```

   ```python title="b.py"
   import a
   VALUE = "B"
   print(a.VALUE)
   ```

   `python a.py` 를 실행하면 어떤 에러가 나는가? 어느 줄에서 실패하는지 위의 "3단계 캐시 등록" 규칙으로 짚어라. 그리고 `b.py` 의 `print(a.VALUE)` 를 `def show(): print(a.VALUE)` 로 바꾸고 아무 데서도 호출하지 않으면 왜 에러가 사라지는지 설명하라.

3. `python mypkg/cli.py` 는 상대 import 에서 실패하는데 `python -m mypkg.cli` 는 성공한다. 이 차이를 `__package__` 속성 하나로 설명하라. 두 경우 각각 `cli` 모듈의 `__package__` 값이 무엇일지 예측하고 `print(__package__)` 로 확인하라.

4. `__init__.py` 가 있는 패키지와 없는 네임스페이스 패키지를 각각 만들고, `pkg.__file__` 과 `pkg.__path__` 의 타입을 비교하라. 네임스페이스 패키지 쪽에서 `__file__` 에 접근하면 무엇이 나오는가?

5. 모듈 레벨 `__getattr__` 을 이용해서, `numpy` 를 실제로 접근할 때만 import 하는 모듈을 만들어라. `import` 시점과 `모듈.numpy_thing` 접근 시점에 각각 다른 메시지를 출력해서, 로딩이 실제로 지연되는지 확인하라.
:::

**다음 절**: [2.1 왜 타입 힌트인가](#/why-typing) — 동적 타이핑 위에 정적 안전망을 얹는 이유와, 그게 실제로 잡아주는 버그의 종류.
