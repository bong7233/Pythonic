# 6.7 도커와 재현 가능한 환경

::: lead
[0.3 uv](#/uv)에서 `uv.lock` 이 "사실"이라고 했다. 정확한 버전을 고정하니 팀원 누구나 같은 패키지를 받는다. 그런데 그 문장에는 조용히 생략된 단서가 있었다. **파이썬 패키지가 같다고 실행 환경까지 같은 건 아니다.** OS가 다르고, 시스템 라이브러리가 다르고, GPU 드라이버가 다르면 `uv sync` 를 아무리 정확히 해도 "내 컴퓨터에선 되는데요"가 돌아온다. 이 절은 그 마지막 틈을 도커로 메우는 법을 다룬다. 그리고 이 환경에는 도커 데몬이 없다는 사실도 먼저 밝혀 둔다 — 뭘 실제로 확인했고 뭘 못 했는지 절 안에서 계속 구분해서 쓴다.
:::

## uv.lock으로 충분하지 않은 지점

[0.3 uv](#/uv)의 재현성 표를 다시 보자.

| 파일 | 보장하는 것 |
| --- | --- |
| `uv.lock` | 파이썬 패키지의 정확한 버전 |
| — | OS, 시스템 라이브러리, GPU 드라이버 |

`uv.lock` 은 "numpy는 정확히 2.2.4다"까지는 보장한다. 하지만 numpy의 wheel이 링크하는 **OpenBLAS의 실제 동작**, PyTorch가 요구하는 **CUDA 드라이버 버전**, OpenCV가 필요로 하는 `libGL.so`, 심지어 **파이썬 인터프리터 자체가 어떤 OS 위에서 컴파일됐는가**는 잠금 파일의 관할 밖이다.

구체적으로 세 가지 축에서 깨진다.

**OS와 시스템 라이브러리.** `opencv-python` 은 wheel 안에 필요한 공유 라이브러리를 대부분 정적으로 담아 배포하지만, 리눅스 배포판에 따라 `libgthread`, `libSM` 같은 것이 아예 없으면 임포트 시점에 죽는다. Windows에서 잘 되던 코드가 우분투 CI에서 `ImportError: libGL.so.1: cannot open shared object file` 로 죽는 건 이 때문이다. 잠금 파일에는 이 의존성이 전혀 기록되지 않는다.

**CPU 아키텍처.** `uv.lock` 에는 플랫폼별 wheel 선택 규칙이 들어 있어서 x86-64와 arm64에서 각각 다른 바이너리를 받아 오긴 한다. 하지만 그건 "같은 논리적 버전의 다른 빌드"를 고르는 것이지, **컴파일된 확장 모듈이 실제로 그 CPU의 명령어 집합(AVX-512 유무 등)을 어떻게 쓰는지**까지 통제하진 않는다.

**GPU 드라이버.** 이게 가장 크다. PyTorch의 `torch==2.7.0+cu126` 이라는 wheel은 "CUDA 12.6 런타임과 함께 컴파일됐다"는 뜻이다. 그런데 이 wheel이 실제로 동작하려면 **머신에 설치된 NVIDIA 드라이버가 그 CUDA 버전과 호환**돼야 한다. 드라이버는 `uv`가 건드릴 수 있는 대상이 아니다. 운영체제 레벨에 설치되는, 커널 모듈이 딸린 시스템 소프트웨어이기 때문이다.

::: note 왜 이게 uv의 결함이 아닌가
`uv.lock` 은 애초에 **"파이썬 패키지 의존성 해결"**이라는 문제만 풀도록 설계됐다. OS 패키지 관리, 드라이버 설치는 완전히 다른 층위의 문제다. pip, poetry, conda(부분적으로는 예외) 전부 마찬가지다. 이 경계를 인정하고 **다음 층위의 도구로 넘기는 것**이 올바른 설계다. 그 다음 층위가 도커다.
:::

::: cote 코딩테스트 포인트
이 절 전체가 코딩테스트와는 무관하다. 채점 서버는 이미 고정된 환경을 주고, 당신은 컨테이너를 만들 필요가 없다. 하지만 실무에서 ML/DL 모델을 배포하거나 인턴/신입으로 "재현 가능한 개발 환경 만들기" 과제를 받으면 이 절 전체가 그대로 요구사항이 된다.
:::

## 도커의 최소 모델: 이미지, 컨테이너, 레이어

도커를 마법처럼 생각하면 Dockerfile을 읽어도 뭘 하는지 감이 안 온다. 최소한의 모델은 이렇다.

```text nolines
Dockerfile ─build─▶ image ─run─▶ container
   |                  |               |
 레시피         읽기 전용 스냅샷    실행 중인 인스턴스
```

**이미지**는 파일시스템 스냅샷이다. `FROM`, `RUN`, `COPY` 같은 명령 한 줄마다 **레이어(layer)** 하나가 쌓인다. 각 레이어는 그 직전 상태와의 차이(diff)만 저장한다.

```text nolines
Layer 4: COPY . /app              <- 소스 코드 추가
Layer 3: RUN uv sync              <- 패키지 설치 결과
Layer 2: COPY pyproject.toml .    <- 의존성 정의 파일
Layer 1: FROM python:3.14-slim    <- 베이스 이미지
```

**컨테이너**는 이 읽기 전용 이미지 위에 쓰기 가능한 얇은 레이어 하나를 얹어 실행한 것이다. 컨테이너를 지워도 이미지는 그대로 남는다.

이 레이어 구조에서 핵심 성질 하나가 나온다. **도커는 레이어를 캐시한다.** Dockerfile의 한 줄이 이전 빌드와 똑같고, 그 줄이 참조하는 파일(있다면)도 안 바뀌었으면, 도커는 그 줄을 다시 실행하지 않고 캐시된 레이어를 재사용한다. 그리고 **어떤 레이어 하나가 캐시 미스가 나면, 그 아래로 이어지는 모든 레이어가 다시 빌드된다.** 이게 다음 절에서 다룰 "COPY 순서"가 왜 그렇게 중요한지의 전부다.

::: warn 이 절의 Dockerfile은 이 환경에서 빌드해 검증하지 못했다
이 환경에는 도커 데몬이 없다(`docker: command not found`). 아래 모든 Dockerfile은 **문법과 구조를 신중하게 검토**했고 uv 공식 문서가 권장하는 패턴을 따랐지만, "실제로 빌드해서 몇 초 걸렸다", "이미지 크기가 몇 MB로 줄었다" 같은 **실행 기반 수치는 이 절 어디에도 쓰지 않는다.** 실제로 검증한 것은 `.dockerignore` 의 패턴 매칭 로직(아래에서 직접 스크립트로 확인한다)과 Dockerfile의 문법적 정합성뿐이다. 직접 도커가 설치된 환경에서 `docker build .` 를 돌려 보길 권한다.
:::

## uv를 도커 안에서 쓰는 올바른 패턴

가장 순진한 Dockerfile부터 보고, 왜 나쁜지 확인한 뒤 고친다.

```dockerfile title="Dockerfile — ❌ 캐싱을 스스로 걷어차는 버전"
FROM python:3.14-slim
WORKDIR /app
COPY . /app
RUN pip install uv && uv sync --locked
CMD ["uv", "run", "python", "main.py"]
```

문제는 `COPY . /app` 한 줄이다. 소스 코드 파일 하나(`README.md` 오타 수정, 로그 메시지 변경 등)만 바뀌어도 이 레이어는 캐시 미스가 나고, **그 아래에 있는 `uv sync` 레이어까지 통째로 다시 실행된다.** 의존성은 하나도 안 바뀌었는데 무거운 패키지 설치를 매번 처음부터 다시 하는 것이다.

핵심 원칙은 하나다. **자주 안 바뀌는 것을 먼저 COPY하고, 자주 바뀌는 것을 나중에 COPY한다.** 의존성 정의(`pyproject.toml`, `uv.lock`)는 하루에도 여러 번 바뀌는 소스 코드보다 훨씬 덜 바뀐다.

```dockerfile title="Dockerfile — ✅ 레이어 캐싱을 살리는 버전"
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 1단계: 의존성 정의만 먼저 복사한다. 소스 코드가 바뀌어도 이 레이어는 캐시된다.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# 2단계: 그 다음에야 소스 코드를 복사한다.
COPY . .
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "main.py"]
```

한 줄씩 뜯어보자.

`COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/` — uv 자체를 `pip install uv` 로 설치하지 않는다. Astral이 공식으로 배포하는 **uv 바이너리가 든 이미지에서 실행 파일만 복사**해 온다. `pip`도 필요 없이 바이너리 하나 복사로 끝난다. 훨씬 가볍고 빠르다.

`--no-install-project` — 이 시점에는 아직 소스 코드(`src/`)가 없다. 프로젝트 자체는 설치하지 말고 **의존성만** 먼저 설치해 두라는 뜻이다. 이렇게 하면 "의존성 설치"와 "내 프로젝트 설치"가 서로 다른 레이어로 분리되어, 소스만 바뀌었을 때 의존성 레이어가 그대로 캐시된다.

`--locked` — `uv.lock` 과 `pyproject.toml` 이 어긋나 있으면(누군가 `pyproject.toml` 만 고치고 lock을 안 갱신했으면) **에러를 내고 멈춘다.** 이미지 안에서 조용히 다른 버전이 깔리는 사고를 막는다. [0.3 uv](#/uv)에서 본 "선언과 잠금은 다르다"는 원칙이 여기서 강제된다.

`--no-dev` — `pytest`, `ruff` 같은 개발 전용 의존성([0.4 도구 세팅](#/tooling)에서 `--dev`로 넣은 것들)은 런타임 이미지에 필요 없다. 이미지만 무거워진다.

`UV_LINK_MODE=copy` — uv는 기본적으로 캐시에서 site-packages로 **하드링크**를 건다(디스크 공간 절약). 그런데 도커의 레이어 시스템은 하드링크가 레이어 경계를 넘나드는 걸 항상 깔끔하게 처리하지 못한다. 컨테이너 안에서는 **파일을 실제로 복사**하도록 강제하는 게 안전하다.

::: deep BuildKit 캐시 마운트 — 한 단계 더
위 버전도 실전에서 쓸 만하지만, uv 공식 문서는 한 걸음 더 나아가 **BuildKit의 캐시 마운트**를 함께 쓰라고 권한다.

```dockerfile title="Dockerfile — BuildKit 캐시 마운트 버전"
# syntax=docker/dockerfile:1
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "main.py"]
```

`--mount=type=cache,target=/root/.cache/uv` 는 uv의 다운로드·빌드 캐시를 **이미지 레이어가 아니라 별도의 영속 캐시 볼륨**에 둔다. 이러면 두 가지가 동시에 좋아진다. 최종 이미지에는 캐시가 안 남아서 가볍고, 그런데도 빌드할 때마다 캐시가 재사용돼 빠르다.

`--mount=type=bind,source=...,target=...` 는 그 두 파일을 이 `RUN` 명령이 실행되는 동안만 임시로 마운트한다. `COPY` 로 레이어에 영구히 새기지 않으므로, 이 파일들이 나중에 다시 바뀌어도 **이 레이어 자체는 다시 캐시 무효화되지 않는다** — 대신 마운트 내용이 바뀌었는지를 uv가 직접 확인해 필요할 때만 재설치한다.

**주의**: `--mount` 문법을 쓰려면 Dockerfile 맨 위에 `# syntax=docker/dockerfile:1` 을 반드시 적어야 한다. 이게 없으면 구파서 문법으로 해석되어 에러가 난다.
:::

## 멀티스테이지 빌드: 왜, 그리고 어떻게

지금까지의 Dockerfile은 최종 이미지 안에 **uv 바이너리, 컴파일 도구, pip 캐시** 같은 빌드 전용 부산물이 그대로 남는다. numpy나 scipy처럼 네이티브 확장을 컴파일해야 하는 패키지가 있으면 `gcc`, `build-essential` 같은 컴파일 도구 체인까지 이미지에 눌러앉는다. 이건 런타임에 전혀 필요 없는 무게다.

**멀티스테이지 빌드**는 `FROM` 을 여러 번 써서 Dockerfile 안에 여러 "단계"를 만들고, 마지막 단계에서 **필요한 결과물만** 이전 단계에서 뽑아 오는 방식이다.

```dockerfile title="Dockerfile — 멀티스테이지"
# ---- 빌드 스테이지 ----
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . .
RUN uv sync --locked --no-dev

# ---- 런타임 스테이지 ----
FROM python:3.14-slim AS runtime

# builder 스테이지에서 결과물(가상환경 + 소스)만 가져온다.
# uv 바이너리도, apt 캐시도, 빌드 도구도 여기엔 없다.
COPY --from=builder /app /app

WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

# 컨테이너 안에서도 불필요한 권한은 갖지 않는다.
RUN useradd --create-home appuser
USER appuser

CMD ["python", "main.py"]
```

`AS builder`, `AS runtime` 으로 각 스테이지에 이름을 붙인다. `COPY --from=builder /app /app` 은 **builder 스테이지가 만든 최종 파일시스템 상태에서 `/app` 디렉터리 하나만** 새 스테이지로 복사해 온다. builder 스테이지에서 실행됐던 `RUN uv sync`, apt 설치, 임시 빌드 산출물은 전부 **최종 이미지에 흔적을 남기지 않는다.**

::: perf 크기가 왜 줄어드는지는 원리로 설명할 수 있다
정확한 MB 수치는 이 환경에서 직접 빌드해 측정하지 못했으므로 지어내지 않는다. 대신 **왜** 줄어드는지는 레이어 모델만으로 설명된다.

빌드 스테이지의 레이어에는 다음이 누적된다.

- uv 실행 파일 자체
- `pip`/`uv` 의 다운로드·빌드 캐시(마운트 캐시를 안 썼다면)
- numpy·scipy 등을 네이티브로 빌드할 때 필요한 `gcc`, 헤더 파일들
- 소스 코드의 중간 산출물

런타임 스테이지는 `COPY --from=builder /app /app` **단 한 줄**로 시작한다. 이전 스테이지의 다른 레이어는 최종 이미지의 레이어 스택에 아예 포함되지 않는다 — 도커가 "잘라내는" 게 아니라, 애초에 최종 이미지가 그 레이어들을 참조하지 않는다. 컴파일 도구 체인 하나만 놓고 봐도 수백 MB 단위인 경우가 흔하므로, 이 원리만으로도 이미지 크기 차이가 왜 나는지는 확신을 갖고 말할 수 있다.
:::

::: tip 스테이지가 셋 이상이어도 된다
"의존성만 설치하는 스테이지"와 "소스까지 설치하는 스테이지"를 나누고, 테스트 전용 스테이지(`pytest` 포함)를 따로 두어 CI에서만 그 스테이지를 타겟으로 빌드하는 것도 흔한 패턴이다.

```bash
docker build --target test -t myapp:test .
docker build --target runtime -t myapp:prod .
```

`--target` 으로 어느 스테이지까지만 빌드할지 고를 수 있다. [6.6 CI/CD](#/ci)에서 이 패턴이 그대로 쓰인다.
:::

## .dockerignore: 빌드 컨텍스트부터 줄인다

`docker build .` 를 실행하면, 도커는 그 명령을 실행하기 전에 **현재 디렉터리 전체를 "빌드 컨텍스트"로 도커 데몬에 보낸다.** `.venv`, `.git`, 데이터셋 폴더까지 딸려 있으면 이 전송 자체가 느려지고, `COPY . .` 를 쓰면 그것들이 그대로 이미지 안에 들어가 버린다.

`.dockerignore` 는 `.gitignore` 와 같은 자리에서 같은 문법으로 동작한다. 프로젝트 루트에 두면 나열된 패턴에 맞는 파일은 빌드 컨텍스트에서 아예 제외된다.

```text title=".dockerignore"
.venv
.git
__pycache__
*.pyc
.pytest_cache
.ruff_cache
.mypy_cache
.env
data/
*.ipynb_checkpoints
```

이 로직이 실제로 어떻게 걸러내는지, 도커 없이도 확인할 수 있다. 다음 파일 트리를 만들었다.

```text nolines
demo/
├── .dockerignore
├── .git/HEAD
├── .venv/pyvenv.cfg
├── __pycache__/mod.cpython-314.pyc
├── data/huge_dataset.csv
├── src/main.py
├── pyproject.toml
├── uv.lock
└── README.md
```

패턴별로 파일 경로 각 부분을 매칭시키는 간단한 파이썬 스크립트로 걸러 봤다(`fnmatch` 기반 — 도커 엔진의 정확한 매처는 아니지만 디렉터리·파일명 패턴 매칭이라는 핵심 개념은 동일하다).

```pyrepl
빌드 컨텍스트로 전송될 파일:
  README.md
  pyproject.toml
  src/main.py
  uv.lock
제외된 파일:
  .git/HEAD
  .venv/pyvenv.cfg
  __pycache__/mod.cpython-314.pyc
  data/huge_dataset.csv
```

의도한 대로 `.venv`, `.git`, 컴파일된 바이트코드, 대용량 데이터는 제외되고 실제로 이미지에 필요한 것만 남는다. (Python 3.14.5 / Windows, `fnmatch` 기반 간이 시뮬레이션으로 실측 — 실제 도커 엔진의 패턴 매칭 세부 규칙과 100% 동일하다고 보장하지는 않는다. 부정 패턴(`!`)이나 앵커링된 경로처럼 미묘한 차이가 있을 수 있으니 실제 프로젝트에서는 `docker build --no-cache . 2>&1 | grep "transferring context"` 로 컨텍스트 크기를 직접 확인하는 걸 권한다.)

::: warn .dockerignore가 없으면 COPY . . 가 캐시까지 오염시킨다
`.dockerignore` 없이 `COPY . .` 를 쓰면, `.venv` 안의 내용(수십~수백 MB)까지 매번 빌드 컨텍스트에 포함된다. 게다가 `.venv` 안의 타임스탬프가 조금만 바뀌어도 **그 COPY 레이어 전체가 캐시 미스**가 난다 — 소스 코드는 하나도 안 바뀌었는데도. 레이어 캐싱 전략을 아무리 잘 짜도 `.dockerignore` 를 빼먹으면 전부 무효화된다.
:::

## GPU 이미지: nvidia/cuda와 PyTorch

지금까지는 CPU 전용 이미지였다. 딥러닝 워크로드는 GPU가 필요하고, 여기서부터 [0.3 uv](#/uv)에서 말한 "드라이버는 uv의 영역이 아니다"가 실제로 부딪히는 지점이다.

::: deep 왜 nvidia/cuda 베이스 이미지를 직접 쌓는 게 위험한가
가장 직관적인 접근은 이렇다.

```dockerfile title="❌ 손으로 쌓으면 버전 지옥"
FROM nvidia/cuda:12.6.0-runtime-ubuntu24.04
RUN apt-get update && apt-get install -y python3.14 python3-pip
RUN pip install torch --index-url https://download.pytorch.org/whl/cu126
```

문제는 **세 가지 버전이 서로 정확히 맞아야 한다**는 점이다.

1. 컨테이너를 실행하는 **호스트 머신의 NVIDIA 드라이버** 버전
2. `nvidia/cuda` 베이스 이미지의 **CUDA 런타임** 버전
3. PyTorch wheel이 컴파일된 **CUDA 버전**(`cu126` 같은 접미사)

이 셋 중 하나라도 어긋나면 `torch.cuda.is_available()` 이 조용히 `False` 를 반환하거나, 더 나쁘게는 `CUDA error: no kernel image is available for execution on the device` 처럼 원인을 짐작하기 어려운 에러가 난다. 호스트 드라이버는 컨테이너 밖에 있는 시스템 자원이라 Dockerfile로 통제할 수 없다는 점이 특히 까다롭다 — nvidia-container-toolkit이 드라이버를 컨테이너 안으로 노출해 주는 방식이라, **드라이버 자체는 이미지 버전과 별개로 호스트에 이미 설치돼 있어야 한다.**
:::

실무에서 권장되는 접근은 **PyTorch가 공식으로 배포하는, CUDA·cuDNN·PyTorch 버전이 이미 서로 맞춰진 이미지를 그대로 베이스로 쓰는 것**이다.

```dockerfile title="Dockerfile — GPU 런타임 (베이스만 예시)"
FROM pytorch/pytorch:2.7.0-cuda12.6-cudnn9-runtime AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 이 베이스 이미지는 이미 torch가 설치돼 있으니,
# pyproject.toml에서 torch는 빼고 나머지 의존성만 uv로 관리한다.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY . .
RUN uv sync --locked --no-dev

FROM pytorch/pytorch:2.7.0-cuda12.6-cudnn9-runtime AS runtime
COPY --from=builder /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"
CMD ["python", "main.py"]
```

**핵심 판단**: CUDA 버전 조합을 직접 관리하려 들지 마라. PyTorch 팀이 이미 검증해서 배포하는 조합(`cuda12.6-cudnn9` 같은 태그)을 그대로 베이스로 삼고, 그 위에 uv로 **나머지 파이썬 의존성만** 얹는다. `torch` 자체는 `pyproject.toml` 의 의존성에서 빼두거나, 베이스 이미지에 이미 설치된 버전과 정확히 일치하는 버전으로 고정해야 한다 — 안 그러면 `uv sync` 가 다른 버전의 torch를 새로 깔아 버려서 애써 맞춘 CUDA 조합이 깨진다.

::: note 실행 시점: --gpus 플래그
이미지가 GPU를 지원하도록 빌드됐다고 해서 컨테이너가 자동으로 GPU를 보는 건 아니다. 호스트에 `nvidia-container-toolkit` 이 설치돼 있어야 하고, 실행할 때 명시적으로 알려 줘야 한다.

```bash
docker run --gpus all myimage:latest
```

이 부분은 호스트 OS의 드라이버·툴킷 설치에 의존하므로, 이 환경(도커 데몬 자체가 없는 환경)에서는 실행해 확인할 수 없다. 직접 GPU가 달린 리눅스 머신에서 `nvidia-container-toolkit` 을 설치한 뒤 검증하라.
:::

## 도커 컴포즈: 로컬 재현의 마지막 조각

애플리케이션이 데이터베이스나 캐시 서버와 함께 동작한다면, `docker run` 을 여러 번 손으로 치는 대신 **compose.yaml** 하나로 전체 스택을 정의한다.

```yaml title="compose.yaml"
services:
  app:
    build:
      context: .
      target: runtime
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/app

  db:
    image: postgres:17
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
```

`build.target: runtime` 은 방금 만든 멀티스테이지 Dockerfile의 `runtime` 스테이지를 지정한다. `docker compose up` 한 줄로 앱과 DB가 함께 뜬다. 이 파일 역시 이 환경에서 `docker compose up` 을 실행해 검증하지는 못했다 — 문법만 YAML 파서로 확인 가능하고 실제 기동 여부는 도커가 있는 환경에서 확인해야 한다.

## 요약

- **`uv.lock` 은 파이썬 패키지 버전까지만 재현한다.** OS, 시스템 라이브러리, GPU 드라이버는 그 밖의 문제이고, 도커가 그 층위를 담당한다.
- 도커 이미지는 **레이어의 스택**이고, 레이어 하나가 캐시 미스면 그 아래 전부가 다시 빌드된다. 그래서 **자주 안 바뀌는 것(의존성 정의)을 먼저 COPY하고, 자주 바뀌는 것(소스 코드)을 나중에 COPY한다.**
- uv를 도커에서 쓸 땐 `pip install uv` 대신 **공식 uv 이미지에서 바이너리만 복사**하고, `--no-install-project` 로 의존성 설치와 소스 설치를 분리하며, `--locked` 로 잠금 파일과의 불일치를 빌드 시점에 잡는다.
- **멀티스테이지 빌드**는 빌드 도구·캐시가 든 스테이지와, 결과물만 남긴 런타임 스테이지를 분리한다. `COPY --from=<스테이지> ...` 로 필요한 것만 가져온다.
- **`.dockerignore`** 는 `.gitignore` 와 같은 문법으로 빌드 컨텍스트 자체를 줄인다. 없으면 `.venv`, `.git`, 데이터셋까지 매번 전송되고 캐시도 오염된다.
- GPU 이미지는 `nvidia/cuda` 베이스를 손으로 쌓기보다, **PyTorch가 CUDA·cuDNN 버전을 맞춰 배포하는 공식 이미지**를 베이스로 쓰는 게 안전하다.
- 이 절의 Dockerfile들은 문법과 구조를 검토했을 뿐, **이 환경에서 실제로 빌드·실행해 검증하지는 못했다.** 이미지 크기·빌드 시간 수치는 의도적으로 싣지 않았다. `.dockerignore` 매칭 로직만 파이썬 시뮬레이션으로 직접 확인했다.

::: quiz 연습문제
1. `COPY . . RUN uv sync` 순서로만 이루어진 Dockerfile과, 이 절에서 만든 "의존성 먼저 COPY" 버전이 있다. 소스 코드 파일 하나(의존성과 무관한)만 수정한 뒤 다시 빌드한다면, 각각 어느 레이어부터 다시 빌드되는가?
2. 멀티스테이지 빌드에서 `COPY --from=builder /app /app` 한 줄이 최종 이미지에 **가져오지 않는** 것 세 가지를 이 절의 예시에서 찾아 써라.
3. `.dockerignore` 에 `.venv` 를 빠뜨렸다고 하자. `COPY . .` 를 쓰는 Dockerfile에서 어떤 문제가 두 가지 생기는가? (전송량과 캐시 무효화, 두 각도에서 생각하라.)
4. `nvidia/cuda` 베이스 이미지에 파이썬과 PyTorch를 손으로 설치하는 대신 `pytorch/pytorch:*-cuda*-cudnn*-runtime` 이미지를 베이스로 쓰라고 한 이유를 세 가지 버전(드라이버/CUDA/PyTorch)의 관계로 설명하라.
5. 이 절에서 "실제로 확인했다"고 명시한 것과 "확인하지 못했다"고 명시한 것을 각각 최소 두 가지씩 나열하라.
:::

**다음 절**: [7.1 시간·공간 복잡도](#/complexity) — 여기까지가 "코드를 신뢰할 수 있게 만드는 법"이었다면, 이제부터는 "그 코드가 왜 그 속도로 도는가"를 본다.
