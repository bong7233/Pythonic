# 6.5 패키징: pyproject.toml부터 배포까지

::: lead
[0.3 uv](#/uv)에서 `pyproject.toml` 을 봤다. 그때는 "의존성을 적어 두는 파일" 정도로만 다뤘다. 이 절에서는 그 파일을 **실제로 설치 가능한 wheel**로 바꾸는 전 과정을 다룬다. 빌드 백엔드가 뭘 하는지, `src` 레이아웃이 왜 사고를 막아 주는지, 버전을 어디에 한 번만 적어야 하는지, 그리고 PyPI에 올리는 절차가 실제로 어떤 명령들로 이뤄지는지 — 전부 직접 빌드해서 결과물을 열어 보며 확인한다.
:::

## 스크립트와 패키지의 경계

지금까지 쓴 `.py` 파일은 전부 **스크립트**였다. 실행하면 끝이다. 패키지는 다르다. **남이 `pip install`(또는 `uv add`)로 설치해서 `import` 할 수 있는 것**이다. 이 차이 하나가 요구하는 게 많다.

- 어디에 뭐가 있는지 알려주는 **메타데이터**(이름, 버전, 의존성)가 있어야 한다.
- 소스 코드를 **하나의 아카이브**(wheel, sdist)로 묶을 수 있어야 한다.
- 설치했을 때 `sys.path` 어디에 뭐가 깔릴지가 **결정적**이어야 한다.

이 세 가지를 책임지는 것이 **빌드 백엔드**(build backend)다.

## 빌드 백엔드: pyproject.toml 뒤에서 실제로 도는 것

`uv build` 나 `pip install .` 을 실행하면, 그 명령이 직접 파일을 압축하지 않는다. **`pyproject.toml` 의 `[build-system]` 테이블에 적힌 다른 도구를 호출**한다.

```toml title="pyproject.toml"
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

::: hist 왜 이렇게 나눠져 있는가 — PEP 517/518
2017년 이전에는 `setup.py` 가 유일한 방법이었다. 문제는 `setup.py` 가 **임의의 파이썬 코드**라는 것이다. 패키지를 빌드하려면 그 코드를 일단 실행해야 하는데, 실행하기 전에는 **무엇이 필요한지조차 알 수 없었다**(`setup.py` 안에서 import 하는 걸 보기 전까지는).

PEP 518(2016)이 `[build-system] requires` 를 만들어 "빌드에 뭐가 필요한지"를 **정적으로** 선언하게 했다. PEP 517(2017)은 한 걸음 더 나가 "빌드 백엔드가 구현해야 할 표준 함수들"(`build_wheel`, `build_sdist` 등)을 정의해서, **setuptools가 아닌 다른 도구도 빌드 백엔드가 될 수 있게** 열었다. hatchling, flit-core, pdm-backend, uv_build가 전부 이 표준을 구현한 서로 다른 백엔드다.

그래서 `uv build` 는 사실 자기가 직접 빌드하는 게 아니라, `[build-system]` 이 지정한 도구를 **격리된 환경에 설치해서 대신 실행**한다. 어떤 프로젝트든 백엔드만 다를 뿐 같은 명령으로 빌드되는 이유다.
:::

지금 실무에서 고를 만한 선택지는 셋이다.

| 백엔드 | 특징 | 쓰는 때 |
| --- | --- | --- |
| `uv_build` | uv가 만든 신생 백엔드. `uv init` 기본값 | 순수 파이썬, 별 요구사항 없을 때 |
| `hatchling` | 설정이 유연하고 플러그인 생태계가 크다 | 동적 버전, 빌드 훅이 필요할 때 |
| `setuptools` | 가장 오래됨, C 확장 빌드 관례가 많다 | 레거시 프로젝트, C 확장 |

`uv init --lib` 으로 라이브러리 프로젝트를 만들면 실제로 이렇게 나온다.

```toml title="uv init --lib --name greetkit 으로 생성됨"
[project]
name = "greetkit"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
authors = [
    { name = "bong7233", email = "batmantwo7233@gmail.com" }
]
requires-python = ">=3.14"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.14,<0.12.0"]
build-backend = "uv_build"
```

(`authors` 안의 이름·이메일은 `git config` 에서 읽어 온 값이라 환경마다 다르게 채워진다. `requires-python`, `[build-system]` 은 어느 환경에서든 이 값 그대로 나온다.)

`[build-system]` 만 `hatchling`/`hatchling.build` 로 바꿔도 **똑같은 소스에서 똑같은 wheel이 나온다** — 파일 구성만 보면 그렇다. 직접 바꿔서 두 백엔드로 각각 빌드해 wheel 내용물을 열어 비교해 보면 `greetkit/__init__.py`, `greetkit/py.typed`, `*.dist-info/{METADATA,WHEEL,RECORD}` 다섯 개 파일 구성은 동일하다. 다만 zip 내부 엔트리까지 완전히 같지는 않다 — `uv_build` 로 만든 wheel은 `greetkit/`, `greetkit-0.1.0.dist-info/` 라는 **디렉터리 엔트리 두 개가 별도로** 들어 있는데, `hatchling` 으로 만든 wheel에는 이 디렉터리 엔트리가 없고 파일 5개뿐이다. 파일 목록이라는 관점에서는 "똑같은 wheel"이 맞고, zip 구조까지 따지면 완전히 동일하지는 않다. **백엔드는 구현일 뿐, `pyproject.toml` 의 `[project]` 테이블이 진짜 계약**이라는 뜻이다. 그래서 백엔드를 바꿔도 사용자 쪽 `uv add greetkit` 은 아무것도 몰라도 된다.

## src 레이아웃 vs flat 레이아웃

패키지 소스를 어디에 둘지는 두 갈래다.

```text nolines
flat 레이아웃                    src 레이아웃
greetkit/                        greetkit/
├── greetkit/                    ├── src/
│   └── __init__.py              │   └── greetkit/
├── tests/                       │       └── __init__.py
│   └── test_hello.py            ├── tests/
└── pyproject.toml                │   └── test_hello.py
                                  └── pyproject.toml
```

둘 다 wheel은 만들어진다. 차이는 **설치 안 하고도 import가 되느냐**다. 직접 확인해 보자. flat 레이아웃 루트에서, 패키지를 설치하지 않은 상태로 이렇게 해 본다.

```pyrepl
>>> import greetkit
>>> greetkit.hello()
'Hello from greetkit (flat)!'
```

**설치를 한 적이 없는데 동작한다.** 이유는 파이썬이 `sys.path` 맨 앞에 **현재 실행하는 스크립트/REPL의 디렉터리**를 넣기 때문이다. `greetkit/` 이 마침 현재 디렉터리 바로 밑에 있으니 우연히 보인 것이다.

src 레이아웃에서 같은 걸 해 보면 다르다.

```pyrepl
>>> import greetkit
Traceback (most recent call last):
    ...
ModuleNotFoundError: No module named 'greetkit'
```

**이게 실은 src 레이아웃의 장점이다.** `src/greetkit` 은 `sys.path` 우연히 걸리는 위치가 아니라서, **정말로 설치해야만** import된다. `uv sync`/`uv pip install -e .` 를 실제로 실행해야 `import greetkit` 이 통과한다.

::: danger flat 레이아웃이 숨기는 사고
flat 레이아웃에서 테스트를 돌리면, **CI에서 wheel을 못 만드는 배포 버그**가 로컬에서는 안 잡힌다. 로컬 pytest는 우연히 cwd에 있는 소스를 바로 읽어서 통과하는데, 실제로 `pip install` 된 패키지에는 파일 하나가 빠져 있을 수도 있다 — `MANIFEST.in` 이나 백엔드 설정 실수로. **"내 컴퓨터에선 테스트가 통과하는데 설치하면 깨진다"** 는 flat 레이아웃에서 실제로 반복되는 사고 패턴이다. src 레이아웃은 이 우연을 원천적으로 차단한다. 그래서 hatchling·uv_build 문서 모두 src 레이아웃을 권장한다.
:::

레이아웃이 하나만 있을 때는 백엔드가 자동으로 패키지를 찾아 준다(hatchling, uv_build 둘 다). 문제는 flat 레이아웃에 **패키지처럼 보이는 디렉터리가 여러 개** 있을 때다. `tests/` 안에 `__init__.py` 를 넣어 두면(과거 관례) setuptools는 실제로 이렇게 멈춘다.

```text nolines
error: Multiple top-level packages discovered in a flat-layout: ['helpers', 'greetkit'].

To avoid accidental inclusion of unwanted files or directories,
setuptools will not proceed with this build.
```

(setuptools로 직접 재현한 실제 에러 메시지다. `tests/` 라는 이름은 setuptools의 기본 제외 목록에 걸려 이 에러가 안 나지만, `helpers/` 처럼 목록에 없는 이름으로 바꾸면 바로 재현된다.) 이게 setuptools가 src 레이아웃을 사실상 강하게 권하는 이유다 — **소스 루트 밑에 패키지가 정확히 하나만 있다는 걸 보장**하기 때문에 이런 모호함 자체가 생기지 않는다.

## 실제로 빌드하기: uv build

이론은 이만하면 됐다. 직접 빌드해서 안을 열어 보자.

```bash
uv init --lib --python 3.14 --name greetkit .
uv build
```

```text nolines
Building source distribution (uv build backend)...
Building wheel from source distribution (uv build backend)...
Successfully built dist\greetkit-0.1.0.tar.gz
Successfully built dist\greetkit-0.1.0-py3-none-any.whl
```

`dist/` 에 **두 종류**가 생긴다. 이름이 비슷해서 헷갈리기 쉽지만 용도가 다르다.

| 파일 | 확장자 | 내용물 | 설치 시 |
| --- | --- | --- | --- |
| sdist (source distribution) | `.tar.gz` | 소스 코드 + `pyproject.toml` 원본 | 설치하는 쪽에서 빌드 백엔드를 다시 돌린다 |
| wheel | `.whl` | **이미 빌드가 끝난** 파일들 | 그냥 압축 풀어서 배치. 빌드 단계 없음 |

wheel은 사실 **이름 규칙이 있는 zip 파일**이다. 직접 열어 보면 이렇다.

```python title="wheel 내부 확인"
import zipfile
z = zipfile.ZipFile("dist/greetkit-0.1.0-py3-none-any.whl")
for n in z.namelist():
    print(n)
```

```text nolines
greetkit/
greetkit/__init__.py
greetkit/py.typed
greetkit-0.1.0.dist-info/
greetkit-0.1.0.dist-info/WHEEL
greetkit-0.1.0.dist-info/METADATA
greetkit-0.1.0.dist-info/RECORD
```

`greetkit/`, `greetkit-0.1.0.dist-info/` 처럼 슬래시로 끝나는 두 줄은 **디렉터리 자체를 가리키는 엔트리**다(uv_build가 zip에 디렉터리 엔트리를 명시적으로 넣기 때문 — hatchling 백엔드는 이 두 줄 없이 파일만 넣는다, 위 절 참고). `src/greetkit/...` 이 아니라 `greetkit/...` 로 들어 있는 것도 눈여겨봐라. **`src/` 는 순전히 소스 트리 상의 관례일 뿐, wheel 안에는 흔적도 남지 않는다.** `METADATA` 파일이 사람이 읽는 패키지 정보(`PKG-INFO` 형식)이고, `RECORD` 는 설치될 각 파일의 경로와 해시 목록 — `pip uninstall` 이 정확히 뭘 지워야 하는지 여기서 안다. (`WHEEL` 이 `METADATA` 보다 먼저 나오는 순서도 실제 출력 그대로다 — zip 안 엔트리 순서는 스펙으로 고정된 게 아니라 백엔드가 파일을 쓰는 순서를 따른다.)

wheel 파일명 자체도 정보다. `greetkit-0.1.0-py3-none-any.whl` 을 나눠 보면:

```text nolines
{이름}-{버전}-{파이썬 태그}-{ABI 태그}-{플랫폼 태그}.whl
greetkit - 0.1.0 - py3 - none - any    .whl
```

`py3-none-any` 는 *"순수 파이썬이라 아무 파이썬 3, 아무 ABI, 아무 플랫폼에서나 동작한다"* 는 뜻이다. C 확장이 있는 패키지(NumPy 등)는 여기가 `cp314-cp314-win_amd64` 처럼 구체적으로 박힌다 — 그 조합에서만 동작한다는 뜻이고, 그래서 플랫폼마다 wheel을 따로 빌드해 올린다.

## 엔트리 포인트: 설치하면 생기는 명령어

라이브러리가 아니라 커맨드라인 도구를 배포하고 싶다면 `[project.scripts]` 를 쓴다.

```toml title="pyproject.toml"
[project.scripts]
greet = "greetkit:main"
```

빌드해서 wheel을 열어 보면 `dist-info/entry_points.txt` 에 이렇게 기록된다.

```text nolines
[console_scripts]
greet = greetkit:main
```

이 wheel을 새 가상환경에 실제로 설치해 실행해 보면.

```bash
uv venv .testenv
uv pip install --python .testenv dist/greetkit-0.2.0-py3-none-any.whl
.testenv/Scripts/greet
```

```text nolines
Hello from greetkit!
```

`.testenv/Scripts/greet.exe` 라는 실행 파일이 설치 시점에 **자동으로 생성**된다. 이 실행 파일이 하는 일은 딱 하나, `greetkit` 모듈을 import해서 `main()` 을 호출하는 것뿐이다. `uv tool install`, `uvx` 로 배포되는 CLI 도구([0.3 uv](#/uv))들이 전부 이 메커니즘 위에 서 있다.

## 버전 관리: 진실은 한 곳에만

`pyproject.toml` 의 `version = "0.1.0"` 은 **정적**이다. 릴리스할 때마다 사람이 손으로 고쳐야 한다. 그런데 코드 안에도 `__version__` 을 두고 싶을 때가 많다. 문제는 **두 곳에 버전을 적으면 반드시 어긋난다.** 하나 고치고 하나 까먹는 게 시간문제다.

해법은 **한쪽을 진실의 원천으로 두고 다른 쪽이 거기서 읽게** 하는 것이다. hatchling으로 실제로 해 보면:

```toml title="pyproject.toml"
[project]
name = "greetkit"
dynamic = ["version"]      # 정적 version 필드를 없애고

[tool.hatch.version]
path = "src/greetkit/_version.py"   # 여기서 읽는다
```

```python title="src/greetkit/_version.py"
__version__ = "0.2.0"
```

이 상태로 `uv build` 하면 실제로 `greetkit-0.2.0-py3-none-any.whl` 이 나오고, `METADATA` 안의 `Version:` 필드도 정확히 `0.2.0` 이다. **파일 하나만 고치면 wheel 이름과 메타데이터가 전부 따라간다.**

더 널리 쓰이는 방식은 **git 태그에서 버전을 뽑는 것**이다(`hatch-vcs`, `setuptools-scm`). `git tag v1.2.0` 을 찍으면 그 자체가 버전의 원천이 되고, 빌드 시점에 `git describe` 결과로부터 버전 문자열을 만든다. 커밋마다 버전을 손으로 바꿀 필요가 없고, **태그와 배포판이 항상 일치**한다는 장점이 크다.

::: note SemVer는 강제되지 않는다
`MAJOR.MINOR.PATCH` (시맨틱 버저닝) 관례 — 호환 깨지는 변경은 MAJOR, 기능 추가는 MINOR, 버그 수정은 PATCH — 는 **파이썬이 강제하지 않는 사회적 약속**이다. `pyproject.toml` 의 `dependencies = ["requests>=2.30,<3"]` 같은 버전 제약이 의미를 가지려면, 그 패키지가 실제로 SemVer를 지킨다는 신뢰가 전제다. 지키지 않는 패키지의 버전 제약은 **거짓 안전망**이다.
:::

## PyPI에 올리기

빌드된 wheel/sdist를 실제로 세상에 내놓는 절차다. **이 환경에서 실제 업로드는 하지 않는다** — 계정과 토큰이 필요하고, 한 번 올리면 같은 버전 번호로 되돌릴 수 없기 때문이다. 대신 업로드 **전** 단계까지는 전부 실행해서 확인했다.

### 1. 로컬 검증: twine check

```bash
uv build
uvx twine check dist/*
```

```text nolines
Checking dist/greetkit-0.2.0-py3-none-any.whl: PASSED with warnings
WARNING  `long_description_content_type` missing. defaulting to `text/x-rst`.
WARNING  `long_description` missing.
Checking dist/greetkit-0.2.0.tar.gz: PASSED with warnings
WARNING  `long_description_content_type` missing. defaulting to `text/x-rst`.
WARNING  `long_description` missing.
```

**실제로 나온 경고**다. 두 줄이 항상 짝으로 뜬다 — hatchling으로 빌드한 METADATA에는 `Description-Content-Type` 헤더 자체가 없어서(위 버전 관리 절부터 hatchling 백엔드로 바꿔 놨다) twine이 먼저 "content-type이 없으니 `text/x-rst` 로 간주한다"고 경고하고, 그다음 `README.md` 를 빈 파일로 뒀으니 `long_description` 자체가 비어 있다고 또 경고한다. (uv_build 백엔드로 그대로 두면 `readme = "README.md"` 확장자를 보고 `Description-Content-Type: text/markdown` 을 자동으로 채워 넣어서, 첫 번째 경고 없이 `long_description` 경고 한 줄만 뜬다 — 백엔드마다 검사 결과가 달라진다는 것도 실제로 확인했다.) `twine check` 는 업로드하지 않고 **메타데이터만 검사**하므로, CI에서 매번 돌려도 안전하다.

### 2. TestPyPI에서 먼저 연습

진짜 PyPI에 올리기 전에 [test.pypi.org](https://test.pypi.org)라는 별도의 연습용 인덱스가 있다. 여기는 아무 때나 지우고 다시 올려도 된다.

```bash
uv publish --index testpypi --token <TestPyPI 토큰>
```

### 3. 실제 배포

```bash
uv publish --token <PyPI API 토큰>
# 또는
uvx twine upload dist/*
```

`uv publish` 와 `twine upload` 는 하는 일이 같다(`dist/` 의 파일들을 업로드). uv 생태계 안에 있다면 `uv publish` 가 별도 설치 없이 바로 되니 더 간단하다.

::: warn 비밀번호를 직접 치지 마라
계정 비밀번호로 업로드하던 시절은 끝났다. 지금은 두 가지 중 하나를 쓴다.

1. **API 토큰**: PyPI 계정 설정에서 발급받은, 그 프로젝트에만 쓸 수 있는 토큰. `UV_PUBLISH_TOKEN` 환경변수나 `--token` 옵션으로 넘긴다. 절대 코드나 커밋에 넣지 않는다.
2. **Trusted Publishing**: GitHub Actions 같은 CI에서, **토큰을 아예 저장하지 않고** OIDC로 그 순간에만 발급받는 방식. `uv publish --trusted-publishing automatic` 이 이걸 자동 처리한다. 가능하면 이쪽을 써라 — 유출될 비밀 자체가 없다.

이 절차는 [6.6 CI/CD](#/ci)에서 GitHub Actions 워크플로로 자동화하는 법과 이어진다.
:::

::: cote 코딩테스트 포인트
패키징은 코딩테스트에 직접 나오지 않는다. 다만 **여러 문제를 풀며 쌓은 유틸 함수를 재사용**하고 싶을 때, 매번 복붙하는 대신 개인용 패키지 하나로 묶어 `uv add --dev` 로 로컬에 설치해 두면 편하다. `uv init --lib` 으로 만들고 `uv pip install -e .` 로 연습 환경에 넣어 두는 정도면 충분하다.
:::

## 요약

- 빌드 백엔드(`hatchling`, `setuptools`, `uv_build`)는 `[build-system]` 이 지정하고, `uv build`/`pip install` 은 그 백엔드를 호출할 뿐이다. **계약은 `[project]` 테이블**이라 백엔드를 바꿔도 결과 wheel은 동일하다.
- **src 레이아웃**은 설치 안 된 패키지를 우연히 import하는 사고를 막는다. flat 레이아웃은 이름이 겹치는 여러 최상위 디렉터리가 있으면 `Multiple top-level packages discovered` 에러로 멈춘다.
- wheel은 이미 빌드가 끝난 zip, sdist는 설치 시점에 다시 빌드해야 하는 소스 아카이브다. 파일명의 `py3-none-any` 태그가 호환 범위를 말해 준다.
- 버전은 **한 곳에서만** 관리한다 — `pyproject.toml` 에 정적으로 두거나, `dynamic = ["version"]` 으로 코드나 git 태그에서 읽어온다.
- `[project.scripts]` 는 설치 시점에 실행 파일을 만들어 준다. `uv tool install`/`uvx` 가 이 위에서 동작한다.
- PyPI 배포는 `twine check` → (선택)TestPyPI → `uv publish`/`twine upload` 순서다. 비밀번호 대신 API 토큰이나 Trusted Publishing을 쓴다.

::: quiz 연습문제
1. `uv init --lib --name mytool .` 로 프로젝트를 만들고 `uv build` 해서 `dist/` 에 생긴 두 파일의 확장자와 크기를 확인하라. wheel을 `zipfile` 로 열어 `dist-info/RECORD` 의 내용을 출력해 보라.
2. flat 레이아웃 프로젝트에서 `tests/` 디렉터리에 `__init__.py` 를 추가하면 어떤 이름의 디렉터리까지는 setuptools가 자동으로 제외해 주는지, 문서를 찾아 확인하라. (힌트: `test*`, `example*` 같은 패턴이다.)
3. `[project.scripts]` 에 두 번째 명령을 추가해 보라. wheel의 `entry_points.txt` 에 몇 줄이 추가되는지 확인하라.
4. `dynamic = ["version"]` 과 `[tool.hatch.version] path = "..."` 를 설정한 뒤, 그 파일의 `__version__` 을 바꾸고 다시 빌드해 wheel 파일명이 정확히 그 버전으로 바뀌는지 확인하라.
5. **생각해 볼 문제.** sdist(`*.tar.gz`)만 있고 wheel이 없는 패키지를 설치하면 설치 시간이 왜 더 오래 걸리는가? C 확장이 있는 패키지라면 어떤 문제가 추가로 생기는가?
:::

**다음 절**: [6.6 CI/CD와 pre-commit](#/ci) — 이 절의 빌드·검증 과정을 커밋마다 자동으로 돌리는 법.
