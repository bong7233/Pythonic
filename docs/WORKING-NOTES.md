# 작업 노트 — 이 책을 어떻게 만들어 왔는가

이 문서는 **어느 세션에서 이어받든 같은 품질을 유지하기 위한** 누적 기록이다.
집필 규범 자체는 [STYLE.md](STYLE.md)에 있다. 이 문서는 그 규범을 **어떤 절차와 도구로**
지켜 왔는지를 다룬다. 새 파트를 쓰기 전에 STYLE.md와 이 문서를 모두 읽어라.

---

## 1. 집필 절차 — 3단계 파이프라인

절 하나마다 다음 세 단계를 거친다. 병렬로 여러 절을 동시에 돌린다.

```text nolines
[Write]  절 하나 = 에이전트 하나. STYLE.md + 기준 샘플을 읽고 집필.
   |     반환할 때 "재검증이 필요한 사실 주장" 목록을 함께 신고한다.
   v
[Verify] 신고된 주장 + 파일 전체를 실제로 실행해서 대조.
   |     추측 금지. 실행한 것만 보고. 파일은 고치지 않고 보고만 한다.
   v
[Fix]    검증자가 찾은 문제만 수정. 틀린 주장은 지우지 말고 올바른 것으로 교체.
```

**이 파이프라인이 실제로 잡아낸 오류가 200건이 넘는다.** 생략하지 마라.

### Write 단계에서 반드시 읽힐 것

1. `docs/STYLE.md` — 절대 규범
2. `content/core/objects-names.md` — 밀도·말투·구조의 기준 샘플
3. `content/toc.json` — 링크에 쓸 id는 여기 있는 것만

### Verify 단계의 판정 기준

| 판정 | 의미 |
| --- | --- |
| `wrong` | 실행 결과가 문서와 다르다. 코드가 에러 난다. 없는 id를 링크했다. 다이어그램이 깨졌다 |
| `imprecise` | 결과는 맞지만 조건(버전·환경·시드)이 빠졌다 |
| `style` | 사실은 맞지만 STYLE.md 규범 위반 |

---

## 2. 가장 많이 틀리는 것 — 실측 없는 수치

집필 중 발생한 오류의 **절반 이상**이 "추정해서 쓴 숫자"였다. 반복해서 확인된 패턴:

- **벤치마크 배수를 한 번 측정하고 단정한다.** 실제로는 재실행마다 크게 흔들린다.
  → 여러 번 돌려서 **범위**로 쓰고, 방향성(어느 쪽이 빠른가)만 단정해라.
- **REPL 출력을 그럴듯하게 지어낸다.** 특히 `is` 비교, `id()`, `getsizeof`, dict/set 순서.
- **`is` 비교는 REPL과 파일 실행 결과가 다르다.** 같은 코드 객체 안의 동일 상수는
  컴파일러가 합치기 때문(상수 폴딩). REPL을 정확히 재현하려면
  `compile(line, "<stdin>", "single")` 로 줄마다 컴파일해서 exec 해라.
- **부동소수점 결과를 깔끔하게 반올림해서 쓴다.** 실제로는 `1e-16` 수준 잡음이 남는다.

> **실측 표기 관용구** — 수치를 쓸 때는 측정 환경을 밝힌다.
> `(Python 3.14 / Windows 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)`

---

## 3. 실행 검증이 불가능한 주제 — 문서 대조로 대체

대상 런타임을 이 환경에 설치할 수 없는 경우가 있다(대표적으로 ROS 2/rclpy —
PyPI에 없고 전용 리눅스 환경이 필요하다).

이럴 때의 규칙:

1. **실행한 척 로그를 지어내지 마라.** 이게 최우선이다.
2. 공식 저장소의 **실제 소스 코드**를 WebFetch로 가져와 대조한다.
   (`docs.ros.org` 는 봇 차단이 걸릴 수 있으니 GitHub 원본을 직접 본다.)
3. 대상 라이브러리와 **무관한 순수 파이썬 로직은 최대한 뽑아내서** 실제로 실행 검증한다.
   ROS 파트에서는 쿼터니언 변환, YAML 병합 순서, enum 값 등이 이 방식으로 검증됐다.

이 방식으로 실제 오류를 여러 건 잡았다(메시지 스펙의 enum 정수값 반전, 예제 코드가
공식 튜토리얼 원본과 다르게 지어내진 것 등).

---

## 4. 검증 도구

```bash
python build.py              # content/ -> assets/bundle.js, 자산 URL에 해시 도장
python tools/check_diagrams.py   # 아스키 다이어그램 정렬 검사
```

`check_diagrams.py` 는 **한글이 고정폭 글꼴에서 두 칸을 차지해 선이 밀리는 것**을 잡는다.
원본 텍스트에서는 줄이 맞아 보여 눈으로는 못 잡는 종류의 버그다.
규칙: **선 문자(`│ ─ ┌ └ ▶`)보다 왼쪽에 한글을 두지 마라.** 선 오른쪽 꼬리 주석은 괜찮다.

### 링크 무결성 검사 (커밋 전 필수)

```bash
python -c "
import json, re, pathlib
toc = json.loads(pathlib.Path('content/toc.json').read_text(encoding='utf-8'))
ids = {ch['id'] for p in toc['parts'] for ch in p['chapters']}
bad = 0
for f in sorted(pathlib.Path('content').rglob('*.md')):
    for l in re.findall(r'\(#/([a-z0-9-]+)(?:#[^)]*)?\)', f.read_text(encoding='utf-8')):
        if l not in ids:
            print(f'{f}: dangling -> #/{l}'); bad += 1
print(f'{bad} dangling' if bad else 'all links valid')
"
```

### 절 구조 점검

각 절은 `::: lead` 로 시작하고 `## 요약`, `::: quiz`, 마지막 줄 **다음 절** 링크로 끝난다.

```bash
for f in content/<part>/*.md; do
  echo "$(basename $f .md) | lead=$(grep -c '^::: lead' $f) summary=$(grep -c '^## 요약' $f) quiz=$(grep -c '^::: quiz' $f)"
done
```

---

## 5. 워크플로 운영 — 중단은 정상이다

대형 병렬 작업은 **거의 항상 중간에 끊긴다.** 관측된 실패 유형 세 가지:

| 실패 | 대응 |
| --- | --- |
| 사용량 한도 도달 | 한도 회복 후 재개 |
| 서버 측 rate limit | 잠시 후 재개 |
| 안전 분류기 일시 오류 | 즉시 재개하면 대개 성공 |

**전부 재개로 해결된다.** 처음부터 다시 돌리지 마라 — 이미 성공한 절까지 다시 쓰게 된다.

```text nolines
Workflow({scriptPath: "<기록해 둔 경로>", resumeFromRunId: "<기록해 둔 runId>"})
```

파트 하나(10~26절)를 끝내는 데 재개가 **2~4회** 필요한 것이 정상 패턴이었다.
작업 시작 시 반환되는 `scriptPath` 와 `Run ID` 를 반드시 기록해 둬라.

재개 후 일부 절이 처음부터 다시 집필될 수 있다. 내용이 짧아져도 곧바로 문제로 보지 말고,
파일을 직접 읽어 구조 점검표로 품질을 확인해라.

---

## 6. 서브에이전트 주의사항

반복해서 발생한 문제들이다. 프롬프트에 명시적으로 금지해야 재발하지 않는다.

- **프로세스 종료는 반드시 정확한 PID로.** 이름 기준 시스템 전역 종료
  (`taskkill /IM python.exe` 등)는 무관한 프로세스까지 죽인다. 실제로 한 번 발생했다.
- **임시 파일은 프로젝트 폴더 밖에.** `scratchpad/`, `nul`, `out.txt` 같은 잔여물이
  저장소에 섞여 들어온 적이 여러 번 있다. **매 파트 완료 후 `git status` 로
  낯선 untracked 파일이 없는지 확인하고 정리해라.**
- `> nul` 은 Windows용 리다이렉트다. git-bash에서 쓰면 `nul` 이라는 **파일이 생긴다.**
  POSIX 셸에서는 `/dev/null`, PowerShell에서는 `$null`.

---

## 7. 이 환경에서 확인된 도구 가용성

| 도구 | 상태 |
| --- | --- |
| Python 3.14.5 (일반 빌드) | `python` |
| free-threaded 빌드 | `uv python install 3.14t` 후 `uv run --python 3.14t python` (수 초) |
| 대부분의 서드파티 | `uvx --with <pkg> python ...` 로 즉시 사용 |
| pyright / mypy | `uvx pyright`, `uvx mypy` |
| C 컴파일러 (Cython, mypyc) | MSVC 설치돼 있음 — `vcvars64.bat` 활성화 후 빌드 |
| Rust (PyO3, maturin) | `winget install Rustlang.Rustup` 로 설치 가능 |
| ROS 2 / rclpy / colcon | **설치 불가** — 문서 대조로 검증 (3절 참고) |
| Docker | **없음** — Dockerfile은 문법만 검증, 빌드 결과를 지어내지 마라 |

---

## 8. git 운영

- 커밋 단위는 **파트 하나**. 커밋 메시지에는 무엇을 검증했고 **어떤 오류를 잡았는지** 남긴다.
- 커밋 이메일은 `<username>@users.noreply.github.com` 을 쓴다.
  실제 이메일로 push 하면 GitHub 이메일 공개 방지 정책(`GH007`)에 막힌다.
- `assets/bundle.js` 는 빌드 산출물이지만 **일부러 커밋한다** — 휴대폰에서는 `build.py` 를
  돌릴 수 없어서, 레포를 받으면 바로 열려야 하기 때문이다.
- **이 저장소는 공개(public)다.** 회사·채용 절차·비공개 문제 등 외부에 유출하면 안 되는
  내용은 어떤 파일에도 기록하지 마라. 일반화된 형태로만 다룬다.
