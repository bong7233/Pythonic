# 6.4 로깅과 관측성

::: lead
지금까지 당신은 아마 `print()` 로 디버깅해 왔을 것이다. 로컬에서 스크립트 하나 돌릴 때는 그걸로 충분하다. 하지만 서버가 여러 대이고 하루에 수백만 줄이 쏟아지며, 문제가 터진 게 3시간 전이라는 걸 방금 알았다면 `print()` 는 완전히 무너진다. 이 절은 표준 `logging` 모듈이 그 문제를 어떻게 풀도록 설계됐는지 보고, 실전에서 가장 자주 밟는 사고 — 로그가 두 번, 세 번 찍히는 것 — 을 직접 재현하고 고친다. 마지막에는 여러 서비스에 걸친 요청 하나를 추적하는 방법까지 다룬다.
:::

## `print()`가 무너지는 지점

`print()` 로 디버깅하는 코드는 보통 이렇게 생겼다.

```python
def process_order(order):
    print(f"주문 처리 시작: {order.id}")
    if order.total < 0:
        print(f"경고: 금액이 음수 {order.total}")
    print(f"주문 처리 완료: {order.id}")
```

작동은 한다. 문제는 나중에 생긴다.

- **끌 수가 없다.** 배포 후 디버그 메시지가 너무 시끄러워졌다고 느껴도, 코드를 고쳐서 다시 배포하는 것 말고는 방법이 없다.
- **급이 없다.** "이건 그냥 정보성"과 "이건 심각한 오류"가 똑같은 `print` 한 줄이다. 필터링할 방법이 없다.
- **출력지가 고정이다.** `print` 는 항상 표준 출력이다. 어떤 메시지는 화면에, 어떤 메시지는 파일에, 어떤 메시지는 모니터링 서버로 보내고 싶어도 코드를 전부 고쳐야 한다.
- **구조가 없다.** 나중에 "이 시간대에 주문 ID가 12345인 로그만 찾아줘" 같은 질의를 하려면 텍스트를 정규식으로 파싱해야 한다.

`logging` 모듈은 이 네 가지를 전부 설정으로 해결한다. 코드는 그대로 두고 **레벨, 출력지, 형식을 나중에 바꿀 수 있다.**

## logger 계층: root와 이름 있는 로거

`logging` 의 핵심 객체는 `Logger` 다. 관례적으로 모듈마다 이렇게 하나씩 가져온다.

```python
import logging

logger = logging.getLogger(__name__)
```

`__name__` 을 쓰는 이유는 로거 이름이 **점(`.`)으로 구분된 계층**을 이루기 때문이다. `myapp.db.pool` 이라는 이름의 로거는 `myapp.db` 의 자식이고, `myapp.db` 는 `myapp` 의 자식이며, 이름에 점이 없는 로거들의 공통 조상은 **root 로거**다.

```text nolines
root
 └── myapp
      └── myapp.db
           └── myapp.db.pool
```

실제로 확인해 보자.

```pyrepl
>>> import logging
>>> logger = logging.getLogger("myapp.db")
>>> logger.parent.name
'root'
>>> logger.parent is logging.root
True
```

각 로거는 자기 레벨을 가질 수도, 안 가질 수도 있다. `getLevelName(logger.getEffectiveLevel())` 은 **자기 레벨이 없으면 부모를 타고 올라가며 처음 만나는 레벨**을 반환한다.

```pyrepl
>>> child = logging.getLogger("myapp.db.pool")
>>> logging.getLevelName(child.getEffectiveLevel())
'WARNING'
```

`child` 는 레벨을 설정한 적이 없다. `myapp.db` 도 없다. `myapp` 도 없다. 결국 root까지 올라가서, **root의 기본 레벨인 WARNING** 을 물려받는다. root의 기본 레벨이 WARNING이라는 것 자체가 실전에서 자주 헷갈리는 지점이다. `logger.setLevel()` 을 한 번도 호출하지 않고 `logger.info(...)` 를 아무리 불러도 **아무것도 출력되지 않는 이유**가 이것이다.

::: deep 왜 계층 구조인가
로거 하나하나에 레벨과 핸들러를 전부 지정하는 건 현실적이지 않다. 모듈이 수백 개인 프로젝트에서 `myapp.db.*` 전체를 DEBUG로 잠깐 켜고 싶다면, `myapp.db` 로거 하나만 설정하면 그 아래 전부(`myapp.db.pool`, `myapp.db.migrations`, ...)가 따라온다. 이게 계층 구조의 존재 이유다. `__name__` 을 쓰면 이 계층이 **패키지 구조와 정확히 일치**하게 되므로 추가 설계 없이 공짜로 얻는다.
:::

## 레벨: 두 단계 필터링

표준 레벨은 다섯 개이고 숫자가 클수록 심각하다.

| 레벨 | 값 | 언제 |
| --- | --- | --- |
| `DEBUG` | 10 | 개발 중에만 필요한 세부 정보 |
| `INFO` | 20 | 정상 동작 중 알아 두면 좋은 사건 |
| `WARNING` | 30 | 비정상이지만 계속 진행 가능 |
| `ERROR` | 40 | 이번 작업은 실패했다 |
| `CRITICAL` | 50 | 프로그램 자체가 위험하다 |

메시지 하나가 실제로 출력되려면 **두 단계**를 통과해야 한다.

1. **로거의 레벨.** `logger.setLevel(...)` 보다 낮으면 여기서 버려진다. `LogRecord` 조차 만들어지지 않는다.
2. **핸들러의 레벨.** 통과한 레코드를 각 핸들러가 받는데, 핸들러도 자기 레벨보다 낮으면 무시한다.

두 단계라는 게 왜 중요한지 직접 보자. 콘솔에는 경고 이상만, 파일에는 전부 남기고 싶다고 하자.

```python title="multi_handler.py"
import logging
import sys

logger = logging.getLogger("myapp")
logger.setLevel(logging.DEBUG)  # 로거는 다 통과시킨다 — 실제 필터링은 핸들러가 한다

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.WARNING)
console.setFormatter(logging.Formatter("[콘솔] %(levelname)s %(message)s"))

file_handler = logging.FileHandler("app.log", mode="w", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

logger.addHandler(console)
logger.addHandler(file_handler)

logger.debug("연결 재시도 3회")
logger.info("연결 성공")
logger.warning("응답 지연 800ms")
logger.error("연결 끊김")
```

실행 결과다.

```text nolines
[콘솔] WARNING 응답 지연 800ms
[콘솔] ERROR 연결 끊김
```

같은 시각 `app.log` 에는 네 줄이 전부 들어 있다.

```text nolines
2026-07-21 13:11:59,964 DEBUG 연결 재시도 3회
2026-07-21 13:11:59,964 INFO 연결 성공
2026-07-21 13:11:59,964 WARNING 응답 지연 800ms
2026-07-21 13:11:59,964 ERROR 연결 끊김
```

**로거 레벨을 DEBUG로 열어 두고, 핸들러 레벨로 목적지별 필터링을 한다**는 것이 실전 패턴이다. 로거 레벨을 WARNING으로 좁혀 버리면 파일에도 DEBUG/INFO가 영영 안 남는다 — 1단계에서 이미 버려지기 때문이다.

## 핸들러와 포매터

로거가 "필터링과 라우팅 결정"을 담당한다면, **핸들러**(Handler)는 "어디로 보낼지", **포매터**(Formatter)는 "어떤 모양으로 만들지" 를 담당한다. 자주 쓰는 핸들러:

- `StreamHandler` — `sys.stdout`/`sys.stderr` 같은 스트림.
- `FileHandler` — 파일 하나.
- `RotatingFileHandler` — 크기가 차면 파일을 돌려가며 쓴다.
- `TimedRotatingFileHandler` — 시간 단위(자정마다 등)로 회전.
- `NullHandler` — 아무것도 안 한다. 라이브러리 작성자가 쓴다 (곧 나온다).

포매터는 `LogRecord` 객체를 문자열로 바꾸는 규칙이다. `%(asctime)s`, `%(levelname)s`, `%(name)s`, `%(message)s` 같은 필드를 조합한다. `LogRecord` 자체는 메시지, 시각, 호출 위치(`filename`, `lineno`, `funcName`), 예외 정보(`exc_info`) 등을 다 들고 있는 평범한 객체다 — 곧 이 객체를 직접 다뤄서 JSON을 만들 것이다.

## 흔한 함정: 로그가 중복으로 찍히는 사고

이제 실전에서 정말 자주 나는 사고를 직접 재현한다. 로거를 만드는 함수를 이렇게 짰다고 하자.

```python title="dup_bug.py"
import logging
import sys


def get_logger():
    """흔한 실수: 호출할 때마다 핸들러를 새로 붙인다."""
    logger = logging.getLogger("myapp.worker")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


log1 = get_logger()
log1.info("작업 시작")

log2 = get_logger()  # 같은 로거를 또 가져와서 또 handler를 붙인다
log2.info("작업 시작")

log3 = get_logger()
log3.info("작업 시작")

print("핸들러 개수:", len(log3.handlers))
```

실제 출력이다.

```text nolines
=== 1번째 호출 후 ===
myapp.worker - 작업 시작
=== 2번째 호출 후 (핸들러가 중복으로 붙는다) ===
myapp.worker - 작업 시작
myapp.worker - 작업 시작
=== 3번째 ===
myapp.worker - 작업 시작
myapp.worker - 작업 시작
myapp.worker - 작업 시작
핸들러 개수: 3
```

::: danger 로그 3중 출력의 정체
`logging.getLogger("myapp.worker")` 는 **같은 이름이면 항상 같은 객체**를 돌려준다(내부적으로 이름을 키로 캐시한다). 그런데 `get_logger()` 를 부를 때마다 `addHandler()` 를 새로 호출하니, **같은 로거에 핸들러가 계속 쌓인다.** 로거가 메시지 하나를 받으면 **자신에게 달린 핸들러 전부**에게 보낸다. 핸들러가 3개면 3번 출력되는 게 당연하다. `get_logger()` 가 애플리케이션 시작 시 한 번만 불리면 문제가 없어 보이지만, 웹 요청마다·재시도마다·테스트 케이스마다 이 함수가 다시 불리는 구조라면 핸들러가 무한히 늘어난다.
:::

원인이 하나 더 있다. 이번엔 **핸들러가 정확히 한 번씩만 추가돼도** 중복이 난다.

```python title="propagate_dup.py"
import logging
import sys

root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(logging.StreamHandler(sys.stdout))       # 앱 초기화 시 흔히 하는 설정

mod_logger = logging.getLogger("myapp.service")
mod_logger.addHandler(logging.StreamHandler(sys.stdout))  # "내 모듈 로그는 확실히 보이게" 하려고 추가

mod_logger.info("주문 처리 완료")
```

```text nolines
주문 처리 완료
주문 처리 완료
```

핸들러는 각자 한 번만 추가했는데도 두 번 찍힌다.

::: warn propagate — 부모에게도 올라간다
모든 로거는 `propagate` 속성을 가지고 있고 **기본값은 `True`** 다. 레코드가 자기 핸들러들에게 전달된 **다음**, 부모 로거에게도 전달되고, 부모는 다시 자기 핸들러들에게 전달한 뒤 또 그 부모에게 올려보낸다. 이 사슬은 root까지 계속된다.

위 예제에서 `mod_logger.info(...)` 는 (1) `mod_logger` 자신의 핸들러에서 한 번, (2) 부모인 `root` 의 핸들러에서 또 한 번, 총 두 번 출력된다. **핸들러를 여러 계층에 나눠 달아 두면 propagate 때문에 저절로 중복이 생긴다.**

고치는 법은 세 가지 중 하나다.

1. **말단 로거에서 `propagate = False`** 로 부모로의 전달을 끊는다.
2. **핸들러는 한 계층에만** 단다 (보통 root 하나, 또는 애플리케이션 최상위 로거 하나).
3. **라이브러리 코드는 아예 핸들러를 달지 않는다.** 이건 관례가 아니라 [공식 문서가 명시한 규칙](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library)이다. 라이브러리는 `logging.getLogger(__name__).addHandler(logging.NullHandler())` 정도만 하고, 실제 핸들러 설정은 **그 라이브러리를 사용하는 애플리케이션**의 몫으로 남긴다. 그래야 같은 라이브러리를 쓰는 서로 다른 앱이 각자 원하는 방식으로 로그를 받을 수 있다.
:::

`mod_logger.propagate = False` 를 설정하면 실제로 한 번만 찍힌다.

```pyrepl
>>> mod_logger.propagate = False
>>> mod_logger.info("주문 처리 완료")
주문 처리 완료
```

::: tip 설정은 프로그램 시작점에서 딱 한 번
가장 안전한 규칙은 **`if __name__ == "__main__":` 블록이나 앱 진입점에서 로깅 설정을 한 번만 한다**는 것이다. 함수 안에서, 모듈 임포트 시점에서, 요청 핸들러 안에서 `addHandler` 를 부르는 코드는 전부 의심하라. 멱등성이 필요하면 `if not logger.handlers:` 로 감싸거나, 아예 [dictConfig](#/logging#설정은-한-곳에서-dictconfig)로 선언적으로 관리한다.
:::

## 지연 평가: 문자열 조합은 공짜가 아니다

`logger.debug(f"결과: {expensive()}")` 와 `logger.debug("결과: %s", expensive())` 는 같아 보이지만 다르다. **인자로 넘긴 `expensive()` 자체는 어느 쪽이든 호출된다** — 파이썬은 함수를 부르기 전에 인자를 먼저 평가하기 때문이다. 차이는 그 **뒤**에 있다.

```python title="lazy_format.py — __str__ 호출 시점 추적"
class CountingArg:
    def __str__(self):
        global formats
        formats += 1
        return "결과"

def expensive():
    global calls
    calls += 1
    return CountingArg()

logger.setLevel(logging.WARNING)   # DEBUG는 걸러진다
logger.debug("계산 결과: %s", expensive())
```

```text nolines
%-style 이후: calls=1, formats=0 (걸러져서 str()이 호출 안 됨)
isEnabledFor 가드 이후: calls=1 (호출 자체가 안 일어남)
레벨을 DEBUG로 올린 뒤: calls=2, formats=1 (이번엔 str()까지 호출됨)
```

::: perf %-스타일이 아끼는 것과 못 아끼는 것 (실측)
`expensive()` 호출(`calls`)은 로그 레벨과 무관하게 **항상 일어난다** — 인자 평가는 피할 수 없다. 하지만 `"%s" % arg` 형태의 실제 문자열 조합(`str(arg)` 호출, `formats`)은 **레코드가 필터를 통과해 진짜로 나갈 때만** 일어난다. DEBUG가 걸러지는 동안엔 `formats` 가 0이었다가, 레벨을 DEBUG로 올리자 1이 됐다.

**인자 계산 자체가 무거울 때**(쿼리 실행, 직렬화 등)는 `%s` 로도 부족하다. 이때는 `if logger.isEnabledFor(logging.DEBUG):` 로 감싸서 `expensive()` 호출 자체를 건너뛴다. 위 실측에서 `isEnabledFor` 가드를 쓴 두 번째 호출은 `calls` 가 그대로였다 — 함수가 아예 불리지 않았다.

f-string으로 미리 조립한 문자열(`f"...{expensive()}"`)을 넘기면 이 최적화가 전부 무효화된다. 인자도, 포매팅도 로그 레벨과 무관하게 매번 실행된다.
:::

## 구조화 로깅: 나중에 질의 가능하게 남기기

지금까지의 로그는 사람이 눈으로 읽기 좋은 텍스트였다. 서비스가 커지면 사람이 로그를 안 읽는다 — **기계가 검색·집계·알림**을 한다. 그러려면 로그 한 줄이 파싱하기 쉬운 구조여야 한다. 가장 널리 쓰이는 형태가 **한 줄에 JSON 객체 하나**(JSON Lines)다.

핵심은 `logging.Formatter` 를 상속해서 `format()` 이 JSON 문자열을 반환하게 만드는 것뿐이다. `logging` 자체에는 JSON 지원이 없지만, `LogRecord` 의 속성을 딕셔너리로 옮기기만 하면 된다.

```python title="json_log.py"
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "user_id", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


logger.info("요청 처리", extra={"request_id": "a1b2", "user_id": 42, "duration_ms": 12.4})
```

실제 출력이다.

```text nolines
{"ts": 1784607109.562, "level": "INFO", "logger": "myapp.api", "msg": "요청 처리", "request_id": "a1b2", "user_id": 42, "duration_ms": 12.4}
```

`extra=` 로 넘긴 키들은 `LogRecord.__dict__` 에 **그대로 속성으로 얹힌다.** 그래서 커스텀 포매터가 `getattr(record, "request_id")` 로 꺼낼 수 있다. 예외를 로깅할 때는 `exc_info=True` 를 넘기면 `record.exc_info` 에 트레이스백 정보가 담기고, `self.formatException()` 으로 문자열화할 수 있다.

```text nolines
{"ts": 1784607109.562, "level": "ERROR", ..., "exc_info": "Traceback (most recent call last):\n  ...\nZeroDivisionError: division by zero"}
```

::: warn extra의 키는 LogRecord와 충돌할 수 있다
`extra` 에 `name`, `msg`, `levelname`, `args` 처럼 `LogRecord` 가 이미 쓰고 있는 속성 이름을 넣으면 예외가 난다.

```pyrepl
>>> logger.info("test", extra={"name": "collide"})
Traceback (most recent call last):
  ...
KeyError: "Attempt to overwrite 'name' in LogRecord"
```

`request_id`, `user_id`, `duration_ms` 처럼 **애플리케이션 고유의 이름**을 쓰면 문제없다. 이 충돌은 실제로 실행해 보지 않으면 예상하기 어렵다 — 개발 초기엔 안 걸리다가, 우연히 예약어와 겹치는 필드명을 쓰는 순간 프로덕션에서 로그 남기려던 코드가 예외를 던진다.
:::

실무에서는 이런 포매터를 직접 짜기보다 `python-json-logger` 같은 라이브러리를 쓰는 경우가 많지만, **원리는 지금 본 것과 똑같다** — `Formatter.format()` 을 오버라이드해서 `LogRecord` 를 원하는 문자열로 바꾸는 것뿐이다. JSON으로 남긴 로그는 Elasticsearch, Loki, Datadog 같은 시스템에 그대로 색인돼서 "지난 1시간 동안 `user_id=42` 인 ERROR 로그" 같은 질의가 텍스트 정규식 없이 바로 된다.

## 요청 전체를 하나로 묶기: contextvars와 분산 트레이싱

지금까지는 로그 한 줄 한 줄이 독립적이었다. 그런데 실제 장애 조사에서 필요한 건 "요청 하나가 시스템을 통과하는 동안 남긴 로그를 전부 모으는 것"이다. 요청마다 매번 `logger.info(..., extra={"request_id": rid})` 를 손으로 넘기는 건 함수 시그니처를 전부 오염시킨다. `contextvars`([4.6 asyncio 기초](#/asyncio-basics)에서 다시 만난다)로 이 문제를 우회할 수 있다.

```python title="contextvar_log.py"
import contextvars
import logging

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True  # False를 반환하면 이 레코드는 버려진다


handler.addFilter(RequestIdFilter())

logger.info("요청 시작 전 (기본값)")
token = request_id_var.set("req-9f3a")
logger.info("핸들러 안에서 로그를 남김")
logger.info("같은 요청 안의 다른 함수에서도 자동으로 붙는다")
request_id_var.reset(token)
logger.info("요청 끝난 뒤 (다시 기본값)")
```

```text nolines
[-] 요청 시작 전 (기본값)
[req-9f3a] 핸들러 안에서 로그를 남김
[req-9f3a] 같은 요청 안의 다른 함수에서도 자동으로 붙는다
[-] 요청 끝난 뒤 (다시 기본값)
```

`request_id_var.set()` 을 요청 진입점에서 한 번 하면, **그 요청을 처리하는 동안 호출되는 모든 함수**에서 `request_id_var.get()` 이 같은 값을 돌려준다. `Filter` 는 `Handler` 와 `Logger` 사이에서 레코드를 검사·수정·차단할 수 있는 훅이다. 여기서는 레코드마다 현재 컨텍스트의 요청 ID를 얹는 데 썼다.

::: deep 분산 트레이싱: 로그 하나로는 안 되는 이유
단일 프로세스 안에서는 `contextvars` 로 충분하다. 하지만 실제 서비스는 API 서버 → 인증 서비스 → 결제 서비스처럼 **여러 프로세스, 여러 서버**를 거친다. 각 서비스가 자기 로그만 남기면, 요청 하나의 전체 경로를 재구성하려고 여러 시스템의 로그를 시간순으로 짜맞춰야 한다 — 현실적으로 불가능에 가깝다.

**분산 트레이싱**(distributed tracing)은 이 문제를 위해 두 가지 ID를 요청과 함께 전파한다.

- **trace ID** — 요청 하나 전체(모든 서비스를 거치는 여정 전체)를 식별한다.
- **span ID** — 그 여정 안의 한 구간(한 서비스 안에서의 한 작업)을 식별한다. span은 부모-자식 관계를 가져서, 전체 호출을 트리로 재구성할 수 있다.

이 ID들은 보통 HTTP 헤더(`traceparent` 등, W3C Trace Context 표준)로 서비스 사이를 오간다. 받은 쪽은 이 ID를 이어받아 자기 로그와 함께 남기고, 다음 서비스를 호출할 때 다시 헤더로 실어 보낸다. **OpenTelemetry** 가 현재 사실상 표준 구현체다 — 언어별 SDK가 이 ID의 생성·전파·수집을 대신해 준다.

이 절에서 만든 `request_id` 패턴은 trace ID의 **아주 단순한 축소판**이다. 진짜 분산 트레이싱을 붙이기 전에도, "요청 하나의 로그를 한데 묶는다"는 개념 자체는 지금 배운 `contextvars` + `Filter` 조합으로 이미 얻을 수 있다.
:::

## 설정은 한 곳에서: dictConfig

지금까지 예제는 코드 안에서 `addHandler`, `setLevel` 을 직접 불렀다. 프로젝트가 커지면 이 호출들이 여러 파일에 흩어지고, 그게 바로 앞서 본 중복 출력 사고의 씨앗이 된다. `logging.config.dictConfig` 는 설정 전체를 딕셔너리(또는 `pyproject.toml`/`yaml`에서 읽어 온 것) 하나로 선언한다.

```python title="dictconfig_demo.py"
import logging.config

config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple", "level": "INFO"},
    },
    "loggers": {
        "myapp": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

logging.config.dictConfig(config)

logger = logging.getLogger("myapp.orders")
logger.info("dictConfig로 설정 완료")
logger.debug("로거는 DEBUG를 통과시키지만 핸들러가 INFO라 걸러진다")
```

```text nolines
INFO myapp.orders: dictConfig로 설정 완료
```

두 번째 줄이 안 보인 이유는 앞서 본 **두 단계 필터링** 그대로다 — `myapp` 로거는 DEBUG를 통과시켰지만, `console` 핸들러가 INFO 미만을 잘랐다. `disable_existing_loggers: False` 를 빼먹으면 이 설정을 적용하기 전에 만들어져 있던 다른 모듈의 로거들이 전부 비활성화된다는 점도 흔히 걸리는 함정이다.

::: note 컨테이너 환경에서는 파일보다 stdout
[6.7 도커](#/docker)에서 다루듯, 컨테이너로 배포하는 애플리케이션은 로그를 파일에 쓰지 말고 **표준 출력으로 흘리는 것**이 관례다(12-factor app 원칙). 파일 회전·보관·수집은 컨테이너 오케스트레이터나 로그 수집 에이전트(Fluentd, Vector 등)에 맡기고, 애플리케이션은 `StreamHandler` 하나로 stdout에 JSON 한 줄씩만 내보내면 된다.
:::

::: note logging은 스레드 안전하다
`Handler.emit()` 내부는 락으로 보호돼 있어서, [4.2 threading](#/threading)에서 다루는 여러 스레드가 동시에 같은 로거로 로그를 남겨도 한 줄이 다른 줄과 뒤섞이지(interleave) 않는다. 다만 `multiprocessing` 으로 프로세스를 여러 개 띄운 경우엔 각 프로세스가 독립된 핸들러를 가지므로, 같은 파일에 동시에 쓰면 파일 자체가 깨질 수 있다 — 이때는 `QueueHandler`/`QueueListener` 로 한 프로세스에 로그를 모아서 쓰는 패턴을 쓴다.
:::

## 요약

- `logging` 은 이름의 점(`.`)으로 부모-자식 계층을 이룬다. `getLogger(__name__)` 을 쓰면 이 계층이 패키지 구조와 자동으로 일치한다.
- 메시지는 **로거 레벨**과 **핸들러 레벨** 두 단계를 통과해야 실제로 출력된다. 로거는 넓게 열어 두고 핸들러로 목적지별 필터링을 하는 게 실전 패턴이다.
- **로그 중복 출력**은 (1) 같은 로거에 핸들러를 여러 번 추가하거나, (2) `propagate=True`(기본값)로 인해 부모 로거의 핸들러에서도 같은 레코드가 또 나가기 때문에 생긴다. 설정은 프로그램 진입점에서 한 번만, 라이브러리 코드는 `NullHandler` 만 단다.
- `%s` 스타일 로깅은 레코드가 실제로 나갈 때만 문자열 조합을 한다. 인자 계산 자체가 무거우면 `isEnabledFor()` 가드로 계산 자체를 건너뛴다.
- 구조화(JSON) 로깅은 커스텀 `Formatter` 로 `LogRecord` 를 딕셔너리로 바꿔서 만든다. `extra=` 로 필드를 추가할 수 있지만, `LogRecord` 의 기존 속성 이름과 겹치면 예외가 난다.
- 한 요청의 로그를 한데 묶으려면 `contextvars` + `Filter` 조합을 쓴다. 여러 서비스에 걸친 요청은 trace ID/span ID를 전파하는 분산 트레이싱(OpenTelemetry)이 필요하다.
- 설정이 흩어지는 걸 막으려면 `logging.config.dictConfig` 로 한 곳에서 선언적으로 관리한다.

::: quiz 연습문제
1. 다음 코드를 실행하면 로그가 몇 번 출력되는가? 이유를 계층·`propagate` 개념으로 설명하라.

   ```python
   import logging

   logging.basicConfig(level=logging.INFO)  # root에 핸들러 추가
   logger = logging.getLogger("myapp")
   logger.addHandler(logging.StreamHandler())
   logger.warning("점검 필요")
   ```

2. `logger.setLevel(logging.ERROR)` 로 설정된 로거에 `logger.info("%s", expensive_query())` 를 호출했다. `expensive_query()` 는 호출되는가? 문자열 조합은 일어나는가? 각각 설명하라.

3. `extra={"message": "custom"}` 을 넘기면 무슨 일이 일어나는가? 실행해서 확인하고 이유를 설명하라.

4. 웹 요청 하나를 처리하는 동안 호출되는 세 개의 함수(`handler`, `validate`, `save`)가 모두 같은 `request_id` 를 로그에 남겨야 한다. `contextvars` 를 쓰지 않고 함수 인자로만 전달한다면 어떤 코드가 늘어나는가? `contextvars` 를 쓰면 무엇이 달라지는가?

5. **깊이 생각해 볼 문제.** 라이브러리 A와 라이브러리 B가 둘 다 같은 이름 규칙(`logging.getLogger(__name__)`)을 쓰고, 둘 다 애플리케이션 코드에서 임포트된다. 두 라이브러리가 지켜야 할 규칙(`NullHandler`)을 어겼다면, 애플리케이션 개발자 입장에서 어떤 증상으로 이 문제를 알아차리게 될까?
:::

**다음 절**: [6.5 패키징](#/packaging) — `pyproject.toml` 하나로 빌드 백엔드부터 배포까지.
