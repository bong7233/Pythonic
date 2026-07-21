# 1.5 bytes, bytearray, memoryview

::: lead
파일을 열고, 소켓에서 읽고, 이미지를 디코딩하고, 카메라 프레임을 ROS 토픽으로 보내는 순간 당신은 문자열이 아니라 **바이트**를 다루고 있다. 파이썬은 이 둘을 완전히 갈라 놨고, 그 국경에 세관이 하나 있다 — **인코딩**이다. 이 절은 그 국경에서 벌어지는 일과, 바이트를 **복사하지 않고** 다루는 법을 다룬다. 뒤에 나올 NumPy·이미지·텐서가 전부 여기 위에 서 있다.
:::

## 문제부터

이 코드는 당신 컴퓨터에서 터진다.

```python title="write_read.py"
open("memo.txt", "w", encoding="utf-8").write("한글")
print(open("memo.txt").read())
```

```text nolines
UnicodeDecodeError: 'cp949' codec can't decode byte 0xed in position 0:
illegal multibyte sequence
```

같은 파일을, 같은 파이썬으로, 방금 쓰고 바로 읽었는데 실패했다. 쓸 때는 `encoding="utf-8"` 을 줬고 읽을 때는 안 줬을 뿐이다.

한국어 윈도우에서 `open()` 의 기본 인코딩은 UTF-8이 **아니다**.

```pyrepl
>>> import locale
>>> locale.getencoding()
'cp949'
```

디스크에 있는 것은 `b'\xed\x95\x9c\xea\xb8\x80'` 이라는 **6개의 바이트**다. 이 바이트가 "한글"인지 아닌지는 바이트 자신이 모른다. **읽는 사람이 어떤 표로 해석하느냐**가 정할 뿐이다. cp949 표에는 `0xED 0x95` 로 시작하는 유효한 글자가 없다. 그래서 터졌다.

이게 이 절 전체를 관통하는 한 문장이다.

> **디스크에도, 네트워크에도, 메모리에도 "문자열"은 없다. 바이트만 있다. 문자열은 바이트를 해석해서 만들어 내는 것이다.**

## bytes는 문자열이 아니다 — 정수의 시퀀스다

`b'abc'` 가 문자처럼 생겨서 착각하기 쉽지만, `bytes` 는 **0~255 정수의 불변 시퀀스**다.

```pyrepl
>>> b = b'abc'
>>> b[0]
97
>>> type(b[0])
<class 'int'>
>>> list(b)
[97, 98, 99]
>>> 97 in b
True
```

`b[0]` 이 `b'a'` 가 아니라 `97` 이다. 이건 파이썬 3에서 가장 많이 걸려 넘어지는 지점 중 하나다.

::: warn 인덱싱과 슬라이싱이 비대칭이다
```pyrepl
>>> b'abc'[0]
97
>>> b'abc'[0:1]
b'a'
```

**인덱싱하면 `int`, 슬라이싱하면 `bytes`.** `str` 은 이 둘이 대칭이라(`'abc'[0]` 도 `'abc'[0:1]` 도 `'a'`) 습관이 그대로 넘어오면 조용히 틀린다.

```python
# ❌ header가 b'\x89' 인지 보고 싶었는데 int와 bytes를 비교했다 → 항상 False
if data[0] == b'\x89':
    ...

# ✅ 둘 중 하나
if data[0] == 0x89:
    ...
if data[0:1] == b'\x89':
    ...
```

반복문도 마찬가지다. `for ch in b'abc'` 는 `int` 를 준다. 1바이트짜리 `bytes` 를 원하면 `for ch in [b[i:i+1] for i in range(len(b))]` 같이 명시해야 한다. 이 비대칭은 실수가 아니라 **의도**다 — 바이트를 문자처럼 다루던 파이썬 2의 습관을 못 쓰게 만들려는 것이다.
:::

::: danger bytes와 str 비교는 예외가 아니라 False다
```pyrepl
>>> b'abc' == 'abc'
False
```

**예외가 안 난다.** 그냥 조용히 `False` 다. 소켓에서 읽은 `b'OK'` 를 `'OK'` 와 비교하는 코드는 영원히 안 맞으면서 아무 말도 안 한다. `dict` 키도 마찬가지다 — `d[b'k']` 와 `d['k']` 는 다른 키다.

파이썬은 이 사고를 잡아 주는 스위치를 준다. `-b` 는 경고, `-bb` 는 에러다. 경고가 아니라 **예외**로 승격되므로, 스크립트로 실행하면 여느 예외처럼 전체 트레이스백이 딸려 나온다.

```bash
python -bb script.py
```

```text nolines
Traceback (most recent call last):
  File "script.py", line 1, in <module>
    b'a' == 'a'
BytesWarning: Comparison between bytes and string
```

`str(b'abc')` 도 똑같이 잡힌다 — 이쪽은 표현식 위치 때문에 캐럿(`^`)까지 붙는다.

```text nolines
Traceback (most recent call last):
  File "script.py", line 1, in <module>
    str(b'abc')
    ~~~^^^^^^^^
BytesWarning: str() on a bytes instance
```

`str(b'abc')` 는 기본적으로 `"b'abc'"` 라는 문자열을 만든다. 디코딩이 아니라 **repr을 뜬 것**이다. 로그에 `b'...'` 가 찍혀 있다면 십중팔구 이 실수다. 테스트 CI에서 `-bb` 를 켜 둬라. (Python 3.14.5 / Windows 기준 실측 — `python -bb`로 실행한 스크립트의 실제 출력이다.)
:::

::: deep bytes 객체의 실제 모양
`sys.getsizeof` 로 재 보면 규칙이 보인다.

```pyrepl
>>> import sys
>>> sys.getsizeof(b'')
33
>>> sys.getsizeof(b'a')
34
>>> sys.getsizeof(b'abc')
36
```

빈 바이트열이 33바이트다. 1바이트 늘 때마다 정확히 1씩 는다. 33은 이렇게 나온다.

```text nolines
   offset  size  field
   ------  ----  ----------------------------------
      0      8   ob_refcnt      <- 참조 카운트
      8      8   ob_type        <- 타입 포인터
     16      8   ob_size        <- 길이
     24      8   ob_shash       <- 해시 캐시
     32      n   ob_sval[n+1]   <- 실제 바이트 + 널 종결자 1
```

헤더 32 + 널 종결자 1 = 33. 헤더를 직접 들여다볼 수도 있다.

```pyrepl
>>> import ctypes
>>> b = b'hello'
>>> fields = (ctypes.c_ssize_t * 4).from_address(id(b))
>>> fields[2]                      # ob_size
5
>>> fields[3] == hash(b)           # ob_shash
True
>>> ctypes.string_at(id(b) + 32, 5)
b'hello'
```

여기서 두 가지가 나온다.

1. **`ob_shash` — 해시는 한 번만 계산되고 캐시된다.** `bytes` 를 `dict` 키로 반복해서 써도 해시 비용은 처음 한 번뿐이다. `str` 도 같은 구조다.
2. **널 종결자 1바이트** — C 라이브러리에 `char*` 로 그대로 넘길 수 있게 하려는 배려다. `bytes` 가 불변인 실용적 이유이기도 하다.
:::

### 작은 정수 캐싱의 바이트 버전

[1.1 객체, 이름, 참조](#/objects-names)에서 `-5..256` 정수가 캐시된다고 했다. `bytes` 에도 같은 게 있다. CPython은 **길이 0인 bytes 하나**와 **길이 1인 bytes 256개**를 미리 만들어 둔다.

```pyrepl
>>> bytes([65]) is bytes([65])
True
>>> b'abc'[1:2] is b'abc'[1:2]
True
>>> b''.join([]) is b''
True
```

`b'abc'[1:2]` 는 슬라이싱인데도 같은 객체다. 길이 1이라 캐시에서 꺼냈기 때문이다. 바이트 단위 파싱은 1바이트 조각을 미친 듯이 많이 만들어 내는 작업이라 이 캐시가 실제로 효과가 있다.

**이 동작에 의존하지 마라.** 앞 절과 같은 이유다. 알아 두는 이유는 `is` 로 잘못 비교한 코드가 왜 어쩌다 통과하는지 설명하기 위해서다. 3.8+에서는 경고도 나온다.

```pyrepl
>>> x = bytes([65])
>>> x is b'A'
<stdin-2>:1: SyntaxWarning: "is" with 'bytes' literal. Did you mean "=="?
True
```

파일 위치 표기가 눈에 익지 않을 수 있다. **대화형 REPL에서는 `<stdin>` 이 아니라 `<stdin-N>` 이다** — N은 그 세션에서 지금까지 실행한 문장 번호다. 위 예시는 두 번째로 실행한 문장(`x = bytes([65])` 가 1번, `x is b'A'` 가 2번)이라 `<stdin-2>` 로 찍힌다. `python -c "..."` 로 실행하면 또 다르게 `<string>` 으로 나오고, 스크립트 파일로 실행하면 실제 파일명이 나온다 — 세 경로가 각각 다른 표기를 쓴다는 걸 기억해 둬라. (Python 3.14.5 실측.)

## 국경: encode와 decode


방향을 헷갈리면 아무것도 안 된다. 외우는 대신 그림으로 잡아라.

```text nolines
                    .encode(enc)
       ┌────────┐  ───────────────▶  ┌─────────┐
       │  str   │                    │  bytes  │
       │ (text) │  ◀───────────────  │ (data)  │
       └────────┘   .decode(enc)     └─────────┘

       code points                    0..255
       "what it means"                "what it is"
```

- `str.encode(enc)` — 의미를 바이트로 **내보낸다**(밖으로: 파일, 소켓, 디스크).
- `bytes.decode(enc)` — 바이트를 의미로 **들여온다**(안으로: 프로그램 내부).

방향을 절대 안 헷갈리는 법이 있다. **`str` 에는 `decode` 가 없고 `bytes` 에는 `encode` 가 없다.** 각 타입에 메서드가 하나씩만 있으니 헷갈릴 여지 자체가 없다. 파이썬 3가 파이썬 2에서 고친 것 중 가장 큰 하나다. 파이썬 2는 `str.decode()` 가 있어서 암묵적 인코딩·디코딩이 사방에서 일어났고, 그게 그 유명한 파이썬 2 유니코드 지옥이었다.

또 하나: 파이썬은 `bytes` 와 `str` 을 **절대 암묵적으로 섞지 않는다.**

```pyrepl
>>> b'a' + 'b'
Traceback (most recent call last):
  ...
TypeError: can't concat str to bytes
>>> bytes('가')
Traceback (most recent call last):
  ...
TypeError: string argument without an encoding
```

`bytes(문자열)` 은 인코딩을 안 주면 거부한다. 파이썬이 마음대로 UTF-8을 고르지 않는다는 뜻이다. **인코딩은 항상 당신이 정한다.**

### UTF-8이 표준이 된 이유

인코딩은 수십 개가 있는데 왜 결국 UTF-8인가. 취향이 아니라 **설계 속성** 때문이다.

```pyrepl
>>> '한글abc'.encode('utf-8')
b'\xed\x95\x9c\xea\xb8\x80abc'
>>> '한글abc'.encode('utf-16')
b'\xff\xfe\\\xd5\x00\xaea\x00b\x00c\x00'
>>> '한글abc'.encode('cp949')
b'\xc7\xd1\xb1\xdbabc'
```

UTF-8 결과를 잘 봐라. 뒤쪽 `abc` 가 **그대로 `abc`** 다. UTF-16에서는 `a\x00b\x00c\x00` 이 됐다.

::: hist UTF-8의 네 가지 설계 속성
1. **ASCII 상위 호환.** 0~127은 1바이트로, ASCII와 완전히 같은 바이트가 된다. 즉 **순수 ASCII 텍스트는 UTF-8 텍스트이기도 하다.** 30년 된 C 코드, `strlen`, 유닉스 도구 전부가 UTF-8 파일을 그냥 다룰 수 있다. UTF-16은 `\x00` 이 섞여 들어가서 `char*` 기반 도구를 전부 깨뜨린다. 이게 결정타였다.

2. **바이트 순서가 없다.** 1바이트 단위로 정의돼서 빅엔디안/리틀엔디안 구분이 없다. UTF-16은 BOM(`\xff\xfe`)이 필요하다. 위 출력에서 `utf-16` 앞에 붙은 `\xff\xfe` 가 그거다.

3. **자기 동기화(self-synchronizing).** 선두 바이트와 후속 바이트가 비트 패턴으로 구별된다.

   ```pyrepl
   >>> for x in '가나다'.encode('utf-8'):
   ...     print(format(x, '08b'))
   11101010
   10110000
   10000000
   11101011
   10000010
   10011000
   11101011
   10001011
   10100100
   ```

   후속 바이트는 **무조건 `10` 으로 시작한다.** 그래서 스트림 중간 아무 데나 떨어져도 앞으로 조금만 훑으면 글자 경계를 찾을 수 있다. 바이트 하나가 깨져도 그 글자만 잃고 복구된다. cp949는 이게 안 된다 — 한 바이트가 밀리면 그 뒤 전체가 쓰레기가 된다.

4. **부분 문자열 안전.** ASCII 문자의 바이트가 다른 글자의 중간에 절대 나타나지 않는다. 그래서 UTF-8 바이트열에서 `b'\n'` 이나 `b','` 를 그냥 `split` 해도 안전하다. cp949는 후속 바이트가 ASCII 범위와 겹쳐서 이게 깨진다.

파이썬 자신도 이 방향으로 움직였다. 3.15부터 `open()` 의 기본 인코딩이 **UTF-8로 바뀐다**(PEP 686). 지금 당장 그 미래를 켜 볼 수 있다.

```bash
python -X utf8 myscript.py       # 또는 PYTHONUTF8=1
```

```pyrepl
>>> import locale, sys
>>> sys.flags.utf8_mode
1
>>> locale.getpreferredencoding(False)
'utf-8'
```
:::

::: danger open()에 encoding을 안 쓰면 당신 코드는 이식되지 않는다
이건 한국 개발자가 가장 많이 당하는 사고다. 리눅스 CI에서는 통과하고 팀원 윈도우에서만 터진다.

```python
# ❌ 로케일에 따라 utf-8일 수도, cp949일 수도, cp1252일 수도 있다
open("data.csv")

# ✅ 텍스트를 읽는다면 언제나 명시
open("data.csv", encoding="utf-8")

# ✅ 바이너리는 애초에 인코딩이 없다
open("model.pt", "rb")
```

파이썬이 이걸 잡아 주는 스위치를 준다(PEP 597).

```bash
python -X warn_default_encoding -W error::EncodingWarning myscript.py
```

```text nolines
EncodingWarning: 'encoding' argument not specified
```

`subprocess`, `pathlib.Path.read_text()`, `json.load()` 로 감싼 파일 객체, `csv` — 텍스트를 여는 모든 곳이 같은 문제를 가진다. **`encoding=` 없는 텍스트 열기는 전부 버그로 취급하라.**
:::

### errors= — 국경에서 문제가 생겼을 때

`encode`/`decode` 는 둘 다 `errors=` 를 받는다. 기본은 `strict` — 예외를 던진다.

```pyrepl
>>> b'\xed\x95\x9c\xff'.decode('utf-8')
Traceback (most recent call last):
  ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 3: invalid start byte
```

`UnicodeDecodeError` 는 정보를 담고 있다. `except` 로 잡아서 꺼내 봐라.

```pyrepl
>>> try:
...     b'\xed\x95\x9c\xff\xfe'.decode('utf-8')
... except UnicodeDecodeError as e:
...     print(e.encoding, e.start, e.end, e.reason)
...
utf-8 3 4 invalid start byte
```

**어느 바이트에서 깨졌는지 정확히 알려준다.** 로그에 `e` 만 찍지 말고 `e.object[max(0, e.start-8):e.end+8]` 을 같이 찍어라. 실제 데이터를 봐야 원인이 보인다.

디코딩에서 쓸 수 있는 핸들러:

| `errors=` | 동작 | 왕복 복원 |
| --- | --- | --- |
| `strict` (기본) | `UnicodeDecodeError` | — |
| `ignore` | 깨진 바이트를 **버린다** | ❌ 영구 손실 |
| `replace` | 대체 문자 `�`(U+FFFD)로 바꾼다 | ❌ 영구 손실 |
| `backslashreplace` | `\xed` 같은 문자열로 바꾼다 | ❌ (수동으로만) |
| `surrogateescape` | `\udc80`~`\udcff` 로 **숨긴다** | ✅ 완전 복원 |

```pyrepl
>>> raw = b'\xed\x95\x9c\xff\xfe'
>>> raw.decode('utf-8', errors='ignore')
'한'
>>> raw.decode('utf-8', errors='replace')
'한��'
>>> raw.decode('utf-8', errors='surrogateescape')
'한\udcff\udcfe'
```

인코딩 쪽은 핸들러가 다르다.

```pyrepl
>>> '한글'.encode('ascii', errors='replace')
b'??'
>>> '한글'.encode('ascii', errors='xmlcharrefreplace')
b'&#54620;&#44544;'
>>> '한글'.encode('ascii', errors='backslashreplace')
b'\\ud55c\\uae00'
>>> '한글'.encode('ascii', errors='namereplace')
b'\\N{HANGUL SYLLABLE HAN}\\N{HANGUL SYLLABLE GEUL}'
```

::: danger errors='ignore' 는 데이터를 조용히 지운다
가장 흔한 안티패턴이 이거다.

```python
text = raw.decode('utf-8', errors='ignore')      # ❌ "일단 돌아가게" 하려고
```

이건 문제를 해결한 게 아니라 **증거를 인멸한 것**이다. 로그에 아무것도 안 남고, 데이터는 조용히 손상된 채로 DB에 들어가고, 3개월 뒤에 "왜 이 레코드만 이상하죠?"가 된다.

정직한 선택지는 셋 중 하나다.

1. **터지게 둬라.** 인코딩이 틀렸다는 건 진짜 버그다. 지금 알아야 한다.
2. `errors='replace'` 를 쓰고 **`�` 개수를 로그에 남겨라.** 손실이 있었다는 사실이 관측 가능해진다.
3. 왕복이 필요하면 `surrogateescape`.
:::

::: deep surrogateescape — 파이썬이 깨진 바이트를 다루는 방법
`surrogateescape`(PEP 383)는 트릭이다. 디코딩할 수 없는 바이트 `0xNN` 을 **U+DCNN 이라는 서로게이트 코드포인트**로 바꿔 넣는다. 이 영역은 유효한 문자에 절대 안 쓰이는 구멍이라 충돌이 없다. 그리고 같은 핸들러로 인코딩하면 정확히 원래 바이트가 돌아온다.

```pyrepl
>>> raw = b'\xed\x95\x9c\xff\xfe'
>>> s = raw.decode('utf-8', errors='surrogateescape')
>>> s
'한\udcff\udcfe'
>>> s.encode('utf-8', errors='surrogateescape') == raw
True
```

**완전 무손실이다.** 이건 장난이 아니라 파이썬이 실제로 쓰는 메커니즘이다. 파일 시스템 경로가 그렇다.

```pyrepl
>>> import sys
>>> sys.getfilesystemencoding()
'utf-8'
>>> sys.getfilesystemencodeerrors()      # 리눅스에서는 'surrogateescape'
```

리눅스 파일 이름은 그냥 바이트다. UTF-8이 아닌 이름의 파일이 실제로 존재한다. `os.listdir()` 이 `strict` 로 디코딩했다면 그런 디렉터리를 여는 순간 파이썬이 터졌을 것이다. `surrogateescape` 덕분에 **읽고 → 그 이름 그대로 다시 열 수** 있다.

**단, 이 문자열을 밖으로 내보내면 안 된다.** `strict` 로 인코딩하면 확실히 터진다.

```pyrepl
>>> '한\udcff'.encode('utf-8')
Traceback (most recent call last):
  ...
UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' in position 1: surrogates not allowed
```

**JSON은 다르다 — 터지지 않는다.** `json.dumps` 는 문자열을 UTF-8 바이트로 인코딩하는 게 아니라 코드포인트 하나하나를 `\uXXXX` 이스케이프로 바꿔 쓴다. 서로게이트 코드포인트도 그냥 숫자라서 이 변환은 예외 없이 통과한다.

```pyrepl
>>> import json
>>> s = b'\xed\x95\x9c\xff\xfe'.decode('utf-8', errors='surrogateescape')
>>> json.dumps(s)
'"\\ud55c\\udcff\\udcfe"'
>>> json.dumps(s, ensure_ascii=False)
'"한\\udcff\\udcfe"'
```

**이게 더 위험하다.** 예외가 안 나니까 손상 사실이 아무 데도 안 남는다. 서로게이트가 섞인 `\udcff` 조각이 그대로 JSON 문자열에 박혀서 API 응답이나 로그로 나가고, 그걸 받은 쪽이 `json.loads()` 로 다시 읽으면 **다시 서로게이트가 있는 파이썬 문자열**이 돌아온다 — 그 문자열을 또 `encode('utf-8')` 하거나 다른 언어의 JSON 파서(자바스크립트 등, 서로게이트를 그대로 못 받는 경우가 많다)에 넘기는 순간에야 터진다. 원인이 몇 단계 떨어진 곳에서 드러나니 디버깅이 훨씬 고약하다.

**`surrogateescape` 는 "파이썬 안에서만 돌고 원래 자리로 돌아갈 데이터"에만 쓴다.** JSON에 넣기 전에는 반드시 `errors='strict'` 로 `encode`/`decode` 왕복이 되는지 검증하거나, 최소한 `ensure_ascii=True`(기본값)로 나온 결과에 `\ud8`~`\udf` 로 시작하는 이스케이프가 없는지 확인하라.
:::

::: warn BOM: utf-8과 utf-8-sig
윈도우 메모장이나 엑셀이 저장한 UTF-8 파일에는 `\xef\xbb\xbf` 라는 3바이트가 앞에 붙는다.

```pyrepl
>>> '가'.encode('utf-8-sig')
b'\xef\xbb\xbf\xea\xb0\x80'
>>> '가'.encode('utf-8-sig').decode('utf-8')
'﻿가'
```

`utf-8` 로 읽으면 **보이지 않는 `﻿` 가 앞에 하나 붙는다.** CSV 첫 컬럼 이름이 `"﻿id"` 가 돼서 `row["id"]` 가 `KeyError` 를 내는 그 사고다. 눈으로는 절대 안 보인다.

읽을 때 `utf-8-sig` 를 쓰면 BOM이 있으면 벗기고 없으면 그냥 둔다.

```pyrepl
>>> '가'.encode('utf-8-sig').decode('utf-8-sig')
'가'
>>> '가'.encode('utf-8').decode('utf-8-sig')      # BOM이 없어도 괜찮다
'가'
```

**남이 준 CSV/텍스트를 읽을 때는 `encoding="utf-8-sig"`, 내가 쓸 때는 `encoding="utf-8"`.** BOM을 새로 만들어 내지는 마라.
:::

::: perf 인코딩은 공짜가 아니다
100만 글자 문자열 기준 실측이다.

```python title="encode/decode 비용"
import timeit
s_ascii, s_kor = 'a' * 1_000_000, '한' * 1_000_000
b_ascii, b_kor = s_ascii.encode(), s_kor.encode()

timeit.timeit(lambda: s_ascii.encode('utf-8'), number=100) / 100   # 0.152 ms
timeit.timeit(lambda: s_kor.encode('utf-8'), number=100) / 100     # 1.044 ms
timeit.timeit(lambda: b_ascii.decode('utf-8'), number=100) / 100   # 0.039 ms
timeit.timeit(lambda: b_kor.decode('utf-8'), number=100) / 100     # 1.219 ms
```

(Python 3.14.5 / Windows 기준 실측.)

ASCII 디코딩이 0.039ms — 1MB를 그냥 `memcpy` 한 수준이다. **UTF-8의 ASCII 상위 호환성이 성능으로도 돌아온다.** CPython은 바이트가 전부 0x80 미만이면 검증만 하고 바로 복사한다.

한글은 30배 가까이 느리다. 3바이트 → 2바이트 변환을 코드포인트마다 해야 하기 때문이다. 크기도 다르다.

```pyrepl
>>> import sys
>>> sys.getsizeof('한' * 1_000_000)          # str: UCS-2, 2바이트/글자
2000058
>>> len(('한' * 1_000_000).encode('utf-8'))  # utf-8: 3바이트/글자
3000000
```

**한글은 UTF-8에서 UTF-16보다 1.5배 크다.** UTF-8이 이겼지만 한글에는 손해다. 그럼에도 위의 네 가지 속성이 압도한다. 자세한 건 [1.4 문자열과 유니코드](#/strings)에서.
:::

::: cote 코딩테스트 포인트
`sys.stdin.buffer` 는 디코딩을 건너뛴다. `bytes` 도 `split()` 을 지원하고 `int()` 는 `bytes` 를 바로 받는다.

```python
import sys

data = sys.stdin.buffer.read().split()      # 디코딩 없이 바로 토큰화
nums = list(map(int, data))                 # int(b'123') 은 동작한다
```

50만 개 정수 토큰 기준 실측이다.

```text nolines
   raw.split() -> map(int)              0.0293 s
   txt.split() -> map(int)              0.0318 s
   raw.decode().split() -> map(int)     0.0316 s
```

**약 10% 차이다.** 큰 게 아니다. 진짜 이득은 다른 데 있다 — `sys.stdin.buffer.read()` 는 **입력 전체를 한 번의 시스템 콜로 가져오고**, `input()` 은 한 줄마다 한 번씩 부른다. 그 차이가 10~100배다. 자세한 건 [8.2 파이썬 입출력 최적화](#/io-optimize).

`bytes` 가 확실히 유리한 자리는 따로 있다. **격자를 문자로 받는 문제**에서는 `bytes` 행이 인덱싱만으로 `int` 를 주므로 비교가 정수 비교가 된다.

```python
grid = [line.strip() for line in sys.stdin.buffer]   # 각 행이 bytes
if grid[r][c] == ord('#'):                            # int 비교
    ...
```
:::

## bytearray — 가변 바이트

`bytes` 는 불변이다. 그래서 `str` 과 똑같은 함정을 가진다.

```python title="bytes 누적은 O(n²)"
buf = b''
for chunk in chunks:
    buf += chunk        # ❌ 매번 전체를 새로 복사한다
```

실제로 재 보면 이차식이 그대로 보인다.

```python title="bytes vs bytearray 누적"
import timeit

def bytes_append(n):
    b = b''
    for _ in range(n):
        b += b'x'
    return b

def ba_append(n):
    b = bytearray()
    for _ in range(n):
        b += b'x'
    return b
```

::: perf 누적 비용 실측
```text nolines
   n          bytes +=     bytearray +=
   -------    ---------    ------------
   100,000     0.0503 s        0.0019 s
   200,000     0.1785 s        0.0039 s
   400,000     0.6357 s        0.0077 s
   800,000     3.6045 s        0.0158 s
```

(Python 3.14.5 / Windows 기준 실측.)

`bytes` 는 n이 2배가 되면 시간이 **4배**가 된다 — 교과서적인 $O(n^2)$ 다. `bytearray` 는 정확히 2배 — $O(n)$ 이다. 80만 번에서 이미 **228배** 차이다.

[1.1절](#/objects-names)에서 문자열 누적에 `"".join()` 을 쓰라고 했던 것과 같은 이야기다. 바이트에서는 선택지가 하나 더 있다: `b"".join(chunks)` 도 되고, 스트리밍이라 미리 모을 수 없으면 `bytearray` 다.
:::

`bytearray` 는 리스트처럼 동작한다. 오히려 `list` 보다 낫다 — 원소가 1바이트로 꽉 채워져 있으니 포인터 배열이 아니다.

```pyrepl
>>> ba = bytearray(b'abcdef')
>>> ba[0] = 65              # int를 대입한다 (bytes 아님!)
>>> ba
bytearray(b'Abcdef')
>>> ba.append(0x21)
>>> ba[2:4] = b'XY'
>>> ba
bytearray(b'AbXYef!')
>>> bytearray(4)            # 0으로 채운 4바이트 버퍼
bytearray(b'\x00\x00\x00\x00')
```

::: deep bytearray의 증폭 패턴은 9/8 이다
`bytes` 는 크기가 정확히 `33 + n` 이었다. `bytearray` 는 다르다 — 여유분을 미리 잡는다.

```pyrepl
>>> import sys
>>> ba = bytearray()
>>> sys.getsizeof(ba)
56
>>> sys.getsizeof(bytearray(b'abc'))
60
```

한 바이트씩 붙이면서 크기가 바뀌는 순간만 찍어 보면 이렇다.

```text nolines
   len      getsizeof   alloc(=size-56)   ratio
   ------   ---------   ---------------   -----
        0          56                 0     -
        1          58                 2     -
        2          61                 5   2.50
        5          64                 8   1.60
        8          68                12   1.50
       12          75                19   1.58
       19          83                27   1.42
       27          92                36   1.33
      ...
   105992      119303            119247   1.125
   119247      134214            134158   1.125
   134158      150989            150933   1.125
```

**커지면 정확히 1.125배 = 9/8 로 수렴한다.** CPython의 `bytearray` 는 재할당할 때 `size + (size >> 3)` 만큼을 잡는다. 그래서 `append` 한 번의 **분할 상환** 비용이 $O(1)$ 이다.

[1.3 시퀀스](#/sequences)의 `list` 도 같은 아이디어인데 증폭률이 다르다. 헤더 56바이트도 뜯어 보면 이유가 있다.

```text nolines
   ob_refcnt(8) + ob_type(8) + ob_size(8)      <- PyObject_VAR_HEAD = 24
   ob_alloc(8)                                 <- 잡아 둔 크기
   ob_bytes(8)                                 <- 버퍼 시작
   ob_start(8)                                 <- 논리적 시작  (!)
   ob_exports(4) + padding(4)                  <- 내보낸 뷰 개수 (!)
   ------------------------------------------
   56
```

마지막 두 필드가 이 절의 나머지를 설명한다.
:::

::: perf ob_start — 앞에서 잘라내기가 O(1)인 이유
`bytes` 로 스트림을 앞에서부터 소비하면 지옥이다. 10MB를 1000바이트씩 잘라먹는 코드다.

```python title="앞에서 소비하기 — 세 가지 방법"
N = 10_000_000

def consume_bytes(chunk=1000):          # ❌
    buf = bytes(N)
    total = 0
    while buf:
        total += buf[0]
        buf = buf[chunk:]               # 남은 전체를 매번 복사한다
    return total

def consume_bytearray(chunk=1000):      # ✅
    buf = bytearray(N)
    total = 0
    while buf:
        total += buf[0]
        del buf[:chunk]                 # ob_start 를 앞으로 민다
    return total
```

```text nolines
   consume_bytes        4.6724 s
   consume_bytearray    0.0024 s        <- 약 1900배
```

(Python 3.14.5 / Windows 기준 실측.)

`consume_bytes` 가 복사하는 총 바이트는 $\frac{N^2}{2 \times 1000}$ = 약 **50GB** 다. 10MB짜리 데이터를 읽으려고 50GB를 옮긴 셈이다.

`del buf[:chunk]` 는 왜 싼가. `ob_start` 를 chunk만큼 **앞으로 밀기만 한다.** 실제 데이터는 안 움직인다. 그래서 `bytearray` 는 앞에서 소비하는 프로토콜 버퍼로 쓰기 좋다 — 소켓에서 받아 쌓고 앞에서 프레임 단위로 떼어내는 코드가 이 패턴이다.

**단, 뒤에서 앞으로 삽입(`buf[0:0] = data`)은 여전히 전체 이동이다.** `ob_start` 는 앞쪽 여유가 있을 때만 도와준다.
:::

## memoryview — 복사하지 않는다

여기서 진짜가 나온다. 위 `consume_bytes` 를 `bytes` 그대로 두고 고칠 수 있다.

```python title="memoryview 로 고치기"
def consume_mv(chunk=1000):
    mv = memoryview(bytes(N))
    total = 0
    while mv:
        total += mv[0]
        mv = mv[chunk:]                 # 복사가 아니다. 창을 옮긴다.
    return total
```

::: perf 제로카피 실측
```text nolines
   consume_bytes      4.612 s   4.536 s   4.575 s
   consume_mv        0.0005 s  0.0005 s  0.0005 s
                     ------------------------------
   ratio               8396x     8286x     8470x
```

(Python 3.14.5 / Windows 기준 실측. 3회 반복.)

**8000배가 넘는다.** 알고리즘이 $O(n^2)$ 에서 $O(n)$ 으로 바뀌었기 때문이다. 상수 튜닝으로는 절대 못 얻는 종류의 차이다.

메모리도 재 볼 수 있다.

```python title="10MB에서 1000바이트 뒤를 슬라이싱"
import tracemalloc

data = bytes(10_000_000)

tracemalloc.start()
b = data[1000:]
print(tracemalloc.get_traced_memory()[1])       # 9999033
tracemalloc.stop()

tracemalloc.start()
m = memoryview(data)[1000:]
print(tracemalloc.get_traced_memory()[1])       # 496
tracemalloc.stop()
```

**10MB vs 496바이트.** `memoryview` 슬라이싱은 데이터 크기와 무관하게 상수다. 496바이트는 뷰 객체 자체(`getsizeof` 로는 184바이트)와 추적 오버헤드다.
:::

`memoryview` 는 **다른 객체의 메모리를 들여다보는 창**이다. 자기 데이터가 없다.

```text nolines
   data = bytes(10_000_000)

   ┌───────────────────────────────────────────────┐
   │  10,000,000 bytes                             │   <- the only real buffer
   └───────────────────────────────────────────────┘
     ▲              ▲
     │              │
   ┌─┴──────────┐ ┌─┴──────────┐
   │ memoryview │ │ memoryview │                       <- 184 bytes each
   │ off=0      │ │ off=1000   │
   │ len=10M    │ │ len=9.99M  │
   └────────────┘ └────────────┘
```

```pyrepl
>>> mv = memoryview(b'abcdef')
>>> mv.format, mv.itemsize, mv.nbytes, mv.readonly, mv.ndim
('B', 1, 6, True, 1)
>>> mv.shape, mv.strides, mv.c_contiguous
((6,), (1,), True)
>>> mv[1:3]
<memory at 0x000001B3233B6B00>
>>> bytes(mv[1:3])                    # 여기서 처음으로 복사가 일어난다
b'bc'
```

`repr` 이 내용을 안 보여준다. 이건 불편이 아니라 **경고**다 — 내용을 보려면 `bytes(mv)` 나 `mv.tobytes()` 로 **복사해야** 하고, 그 순간 제로카피의 이점이 사라진다는 걸 알려 주는 것이다.

::: warn tobytes() 를 습관적으로 부르면 memoryview를 쓸 이유가 사라진다
```python
# ❌ 뷰를 만들자마자 복사하면 그냥 슬라이싱과 같다
header = mv[:8].tobytes()

# ✅ 비교/파싱은 뷰 상태로 그대로 된다
if mv[:8] == b'\x89PNG\r\n\x1a\n':
    ...
```

`memoryview` 는 `bytes` 와 **직접 비교되고 해시도 같다.**

```pyrepl
>>> memoryview(b'abc') == b'abc'
True
>>> hash(memoryview(b'abc')) == hash(b'abc')
True
>>> d = {b'k': 1}
>>> d[memoryview(b'k')]
1
```

읽기 전용 뷰만 해시할 수 있다. 당연하다 — 내용이 바뀔 수 있으면 해시가 거짓말이 된다.

```pyrepl
>>> hash(memoryview(bytearray(b'abc')))
Traceback (most recent call last):
  ...
ValueError: cannot hash writable memoryview object
```

이건 `list` 가 해시 불가능한 것과 완전히 같은 논리다. [1.7 set과 frozenset](#/sets)에서 다시 나온다.
:::

### 쓰기 가능한 뷰

`bytearray` 위의 뷰는 쓸 수 있다. **뷰를 통해 쓰면 원본이 바뀐다.**

```pyrepl
>>> ba = bytearray(b'abcdef')
>>> mv = memoryview(ba)
>>> mv.readonly
False
>>> mv[0] = 65
>>> ba
bytearray(b'Abcdef')
>>> mv[2:5] = b'XYZ'
>>> ba
bytearray(b'AbXYZf')
```

슬라이스 대입은 **길이가 정확히 같아야 한다.** 뷰는 크기를 바꿀 권한이 없다.

```pyrepl
>>> mv[2:5] = b'ab'
Traceback (most recent call last):
  ...
ValueError: memoryview assignment: lvalue and rvalue have different structures
```

이게 제약이 아니라 계약이다. **뷰는 남의 메모리를 빌려 쓸 뿐 재할당할 수 없다.** 그래서 `memoryview` 슬라이스 대입은 순수한 `memcpy` 다.

```pyrepl
>>> memoryview(b'abc')[0:1] = b'x'
Traceback (most recent call last):
  ...
TypeError: cannot modify read-only memory
```

그 계약이 성능으로도 돌아온다. 8MB를 채우는 두 방법을 재 보면 이렇다.

```python title="8MB 채우기 — 실측 0.843ms vs 1.625ms"
import timeit

n = 8_000_000
src = bytes(n)

def via_slice():
    ba = bytearray(n)
    ba[:] = src                     # 1.625 ms
    return ba

def via_mv():
    ba = bytearray(n)
    memoryview(ba)[:] = src         # 0.843 ms
    return ba
```

(Python 3.14.5 / Windows 기준 실측.)

**약 2배다.** `ba[:] = src` 는 크기가 달라질 수 있으므로 `bytearray` 가 리사이즈 경로를 탄다. `memoryview` 슬라이스 대입은 크기가 같음을 이미 검증했으니 바로 `memcpy` 한다. 큰 차이는 아니지만, 8MB짜리 프레임을 초당 30번 복사하는 비전 파이프라인에서는 의미가 있다.

### 뷰는 원본을 붙잡는다

여기가 `memoryview` 의 유일한 진짜 함정이다.

```pyrepl
>>> ba = bytearray(b'abcdef')
>>> mv = memoryview(ba)
>>> ba.append(1)
Traceback (most recent call last):
  ...
BufferError: Existing exports of data: object cannot be re-sized
```

**뷰가 살아 있는 동안 원본은 크기를 못 바꾼다.** 아까 헤더에서 본 `ob_exports` 가 이 카운터다. 뷰가 하나라도 남아 있으면 `bytearray` 는 리사이즈를 거부한다.

당연한 안전장치다. 리사이즈는 버퍼를 다른 주소로 옮길 수 있고, 그러면 뷰는 해제된 메모리를 가리키게 된다. C였다면 use-after-free다. 파이썬은 **`BufferError` 로 바꿔 놓았다.**

```pyrepl
>>> mv.release()
>>> ba.append(1)
>>> ba
bytearray(b'abcdef\x01')
```

::: tip memoryview 는 with 로 써라
`release()` 를 손으로 부르지 마라. `memoryview` 는 컨텍스트 매니저다.

```python
with memoryview(buf) as mv:
    parse(mv)
# 여기서 자동으로 release() 된다
```

특히 **긴 수명 객체의 속성으로 뷰를 저장하지 마라.** GC가 언제 돌지 모르니 원본이 언제까지 잠기는지 예측할 수 없어진다. `BufferError` 는 전혀 상관없어 보이는 다른 함수에서 튀어나온다.

읽기 전용으로 남에게 넘길 때는 `toreadonly()` 로 못을 박아라.

```pyrepl
>>> m = memoryview(bytearray(b'abcdef'))
>>> m.toreadonly().readonly
True
```

[1.17 컨텍스트 매니저](#/context-managers)에서 이 패턴을 일반화한다.
:::

### cast — 같은 바이트를 다른 눈으로

`memoryview.cast()` 는 **복사 없이 원소 타입을 바꾼다.**

```pyrepl
>>> ba = bytearray(b'Abcdef')
>>> m = memoryview(ba)
>>> m.format, m.itemsize, m.shape
('B', 1, (6,))
>>> m2 = m.cast('h')                  # 부호 있는 16비트 정수로 본다
>>> m2.format, m2.itemsize, m2.shape
('h', 2, (3,))
>>> m2.tolist()
[25153, 25699, 26213]
```

`25153` 은 `0x6241` 이다. `b'Ab'` 를 리틀엔디안 16비트로 읽은 값이다. **바이트는 하나도 안 움직였다. 해석만 바뀌었다.**

::: warn cast 는 C 연속 뷰에서만 된다
```pyrepl
>>> memoryview(b'abcdef')[::2].cast('h')
Traceback (most recent call last):
  ...
TypeError: memoryview: casts are restricted to C-contiguous views
```

`[::2]` 는 건너뛰며 보는 뷰라 메모리가 연속이 아니다. 연속이 아닌 것을 다른 크기의 원소로 다시 나눌 방법이 없다.

`cast` 는 **네이티브 바이트 순서**를 쓴다. 네트워크에서 온 빅엔디안 데이터에 `cast('h')` 를 하면 x86에서 조용히 틀린 값이 나온다. 엔디안이 다르면 `cast` 가 아니라 `struct` 를 써라.
:::

## 버퍼 프로토콜 — 이게 전부를 잇는다

`memoryview` 는 특별한 타입이 아니다. **버퍼 프로토콜**(PEP 3118)이라는 C 레벨 규약의 파이썬 쪽 얼굴일 뿐이다.

규약은 단순하다. *"내 메모리는 여기 있고, 이렇게 생겼고, 쓸 수 있는지 없는지는 이렇다"* 를 C 구조체 하나로 알려준다. 이걸 구현한 객체끼리는 **파이썬을 거치지 않고 메모리를 직접 주고받는다.**

```text nolines
                    buffer protocol (PEP 3118)
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  bytes   │  │bytearray │  │  array   │  │  mmap    │
   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
        └─────────────┴──────┬──────┴─────────────┘
                             │
                    ┌────────▼────────┐
                    │   memoryview    │
                    └────────▲────────┘
                             │
        ┌─────────────┬──────┴──────┬─────────────┐
   ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐
   │  NumPy   │  │  Pillow  │  │  OpenCV  │  │ PyTorch  │
   │ ndarray  │  │  Image   │  │   Mat    │  │  Tensor  │
   └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

3.12부터는 이 규약이 파이썬 레벨에도 노출된다(PEP 688).

```pyrepl
>>> from collections.abc import Buffer
>>> isinstance(b'x', Buffer), isinstance(bytearray(), Buffer)
(True, True)
>>> isinstance('x', Buffer)
False
>>> import numpy as np
>>> isinstance(np.zeros(3), Buffer)
True
```

`str` 이 `Buffer` 가 아니라는 게 핵심이다. **문자열은 메모리를 남에게 빌려주지 않는다.** 내부 표현(latin-1/UCS-2/UCS-4 중 하나)이 구현 세부사항이기 때문이다.

::: deep 순수 파이썬으로 버퍼 프로토콜 구현하기
PEP 688이 `__buffer__` 를 파이썬 레벨로 끌어냈다. 이제 C 확장 없이도 버퍼 제공자를 만들 수 있다.

```pyrepl
>>> class MyBuf:
...     def __buffer__(self, flags):
...         return memoryview(b'hi')
...
>>> from collections.abc import Buffer
>>> isinstance(MyBuf(), Buffer)
True
>>> bytes(memoryview(MyBuf()))
b'hi'
```

`isinstance` 가 `True` 인 이유는 `Buffer` ABC가 `__buffer__` 의 존재만 보는 구조적 검사이기 때문이다. [1.15 프로토콜, ABC, 덕 타이핑](#/protocols)에서 이 메커니즘을 다룬다.

타입 힌트에서도 쓴다. "바이트 비슷한 것 아무거나"를 `bytes | bytearray | memoryview` 로 나열하던 걸 `Buffer` 하나로 줄인다.

```python
from collections.abc import Buffer

def checksum(data: Buffer) -> int:
    ...
```
:::

### NumPy와 이어지는 지점

이제 이 절이 왜 [Part IX 수치 계산과 데이터](#/numpy-basics) 앞에 있는지가 보인다.

```pyrepl
>>> import numpy as np
>>> ba = bytearray(b'\x01\x00\x02\x00\x03\x00')
>>> arr = np.frombuffer(ba, dtype=np.int16)
>>> arr
array([1, 2, 3], dtype=int16)
>>> arr[0] = 999
>>> ba
bytearray(b'\xe7\x03\x02\x00\x03\x00')
```

**`np.frombuffer` 는 복사하지 않는다.** NumPy 배열에 쓴 값이 `bytearray` 에 그대로 나타난다. 두 객체가 같은 6바이트를 공유한다.

반대 방향도 된다.

```pyrepl
>>> mv = memoryview(np.arange(6, dtype=np.int32).reshape(2, 3))
>>> mv.ndim, mv.shape, mv.strides
(2, (2, 3), (12, 4))
>>> mv.c_contiguous
True
```

`memoryview` 는 **다차원**을 안다. `strides` 가 `(12, 4)` 라는 건 "다음 행으로 가려면 12바이트, 다음 열로 가려면 4바이트 이동"이라는 뜻이다. 이게 NumPy의 스트라이드 그 자체다. 전치하면 바로 드러난다.

```pyrepl
>>> t = memoryview(np.arange(6, dtype=np.int32).reshape(2, 3).T)
>>> t.shape, t.strides
((3, 2), (4, 12))
>>> t.c_contiguous, t.f_contiguous
(False, True)
```

**전치는 데이터를 안 옮긴다. `strides` 를 바꿀 뿐이다.** `.T` 가 왜 공짜인지, 왜 전치 후 `reshape` 이 갑자기 복사를 유발하는지가 여기서 설명된다. [9.3 NumPy 고급](#/numpy-advanced)에서 이걸 파고든다.

::: perf 이미지가 실제로 흐르는 경로
`cv2.imread()` 가 반환하는 `(H, W, 3)` `uint8` 배열은 이 절에서 본 것 그대로다.

```pyrepl
>>> import numpy as np
>>> buf = bytearray(2 * 3 * 3)                       # 2x3 RGB 이미지
>>> img = np.frombuffer(buf, dtype=np.uint8).reshape(2, 3, 3)
>>> img[0, 0] = [255, 0, 0]
>>> buf[:6]
bytearray(b'\xff\x00\x00\x00\x00\x00')
>>> mv = memoryview(img)
>>> mv.shape, mv.strides, mv.format, mv.nbytes
((2, 3, 3), (9, 3, 1), 'B', 18)
```

1920x1080 RGB 프레임은 6,220,800바이트다. 30fps면 초당 186MB다. **이 경로에서 `.tobytes()` 를 한 번 더 부르면 초당 186MB를 추가로 복사한다.** 카메라 → 전처리 → 추론 → ROS 토픽으로 가는 파이프라인에서 단계마다 복사하면 CPU가 그것만 한다.

그래서 NumPy·OpenCV·ROS 2가 전부 이 프로토콜 위에서 논다. `cv_bridge` 가 이미지 메시지를 NumPy 배열로 바꿀 때 복사 없이 즉시 끝나는 이유가 바로 이것이다. [10.12 센서 데이터 처리](#/sensors)에서 다시 만난다.
:::

::: danger np.frombuffer 는 원본의 가변성을 물려받는다
```pyrepl
>>> np.frombuffer(bytearray(b'\x01\x00'), dtype=np.int16).flags['WRITEABLE']
True
>>> np.frombuffer(b'\x01\x00', dtype=np.int16).flags['WRITEABLE']
False
```

**`bytes` 에서 만든 배열은 읽기 전용이다.** `bytes` 는 불변이니 당연하다. 그런데 에러 메시지가 `ValueError: assignment destination is read-only` 라서 원인이 한참 위의 `np.frombuffer(b'...')` 라는 걸 알아채기 어렵다.

쓸 배열이 필요하면 `np.frombuffer(bytearray(data), ...)` 로 **의도적으로** 복사하거나, 아예 `np.array(...)` 를 써라.
:::

::: tip 다른 것들도 전부 버퍼다
```pyrepl
>>> from array import array
>>> a = array('i', [1, 2, 3])
>>> m = memoryview(a)
>>> m.format, m.itemsize, m.readonly
('i', 4, False)
>>> m[0] = 99
>>> a
array('i', [99, 2, 3])
```

`mmap` 도 마찬가지다. 이건 진짜로 강력하다 — **파일을 메모리에 안 읽고 수정할 수 있다.**

```python title="mmap + memoryview: 파일을 읽지 않고 고치기"
import mmap

with open("data.bin", "r+b") as f:
    with mmap.mmap(f.fileno(), 0) as mm:
        mv = memoryview(mm)
        mv[0:1] = b'H'          # 디스크 페이지를 직접 건드린다
        mv.release()
```

10GB 파일의 첫 바이트를 바꾸려고 10GB를 읽을 이유가 없다. OS가 필요한 페이지만 올린다.

`socket.recv_into(buf)`, `file.readinto(buf)`, `zlib.decompress` 도 전부 버퍼를 받는다. **`recv()` 대신 `recv_into()` 를 쓰면 수신 버퍼를 재사용해서 할당을 없앤다.**
:::

## struct — 바이트를 구조체로

`memoryview` 는 바이트를 **가리키는** 법이었다. `struct` 는 바이트를 **읽는** 법이다.

```pyrepl
>>> import struct
>>> struct.pack('>I', 1234)
b'\x00\x00\x04\xd2'
>>> struct.pack('<I', 1234)
b'\xd2\x04\x00\x00'
>>> struct.unpack('>HHI', struct.pack('>HHI', 1, 2, 3))
(1, 2, 3)
```

`unpack` 은 **항상 튜플**을 반환한다. 값이 하나여도 그렇다. `(x,) = struct.unpack(...)` 으로 받아라.

### 첫 글자가 전부를 바꾼다

포맷 문자열 맨 앞 한 글자가 **바이트 순서와 정렬**을 정한다. 이걸 생략하는 게 `struct` 최대의 함정이다.

| 첫 글자 | 바이트 순서 | 크기 | 정렬(padding) |
| --- | --- | --- | --- |
| (없음) 또는 `@` | 네이티브 | 네이티브 | **있음** |
| `=` | 네이티브 | 표준 | 없음 |
| `<` | 리틀엔디안 | 표준 | 없음 |
| `>` , `!` | 빅엔디안 | 표준 | 없음 |

::: danger 첫 글자를 생략하면 크기가 달라진다
```pyrepl
>>> import struct
>>> struct.calcsize('ci')
8
>>> struct.calcsize('<ci')
5
```

`c`(1바이트) + `i`(4바이트)는 5바이트여야 하는데 기본 모드에서는 **8바이트**다. C 컴파일러가 `int` 를 4바이트 경계에 맞추려고 `char` 뒤에 **3바이트 패딩**을 넣기 때문이다.

```text nolines
   '<ci'  ->  [c][i][i][i][i]                       5 bytes
   'ci'   ->  [c][ ][ ][ ][i][i][i][i]              8 bytes
                  ^^^^^^^^^
                  padding inserted by alignment
```

필드 순서만 바꿔도 크기가 바뀐다.

```pyrepl
>>> struct.calcsize('ic')
5
```

`int` 먼저면 패딩이 없다. **이건 C 구조체 레이아웃 규칙 그대로다.**

규칙은 하나다.

- **파일 포맷이나 네트워크 프로토콜을 다룬다면 반드시 `<` 또는 `>` 로 시작하라.** 그 포맷의 스펙에 패딩은 없다.
- **C 확장이나 `ctypes` 로 진짜 C 구조체를 주고받을 때만** 기본 모드를 쓴다. 그럴 때는 패딩이 있어야 맞다.

`!` 는 `>` 와 완전히 같다. "network byte order"라는 뜻이라 프로토콜 코드에서 의도가 드러난다.

**크기까지 달라진다.** `l`(long)은 리눅스 64비트에서 8바이트, 윈도우 64비트에서 4바이트다. `P`(void*)는 이 기계에서 8바이트지만 32비트에서는 4바이트다.

```pyrepl
>>> struct.calcsize('P')
8
```

**네이티브 모드로 저장한 파일은 다른 기계에서 안 열린다.** `<`/`>` 를 쓰면 `i` 는 어디서나 4바이트로 고정된다.

앞의 `cast()` 도 같은 문제를 가진다. `memoryview.cast('h')` 는 네이티브 엔디안이다. **엔디안이 중요하면 `struct`, 성능이 중요하고 엔디안이 네이티브면 `cast`.**
:::

### 실전: PNG 헤더 파싱

`struct` + `memoryview` 를 합치면 실제 바이너리 포맷을 복사 없이 읽을 수 있다. PNG는 `[길이 4바이트 빅엔디안][태그 4바이트][데이터][CRC 4바이트]` 청크의 나열이다.

```python title="png_parse.py — 실행된다"
import struct
import zlib

# 2x2 빨간 PNG를 직접 만든다 (struct의 pack 쪽 예시)
def chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data)))

w = h = 2
raw = b''.join(b'\x00' + bytes([255, 0, 0] * w) for _ in range(h))
png = (b'\x89PNG\r\n\x1a\n'
       + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
       + chunk(b'IDAT', zlib.compress(raw))
       + chunk(b'IEND', b''))

# 이제 복사 없이 다시 읽는다 (unpack_from 쪽 예시)
mv = memoryview(png)
assert mv[:8] == b'\x89PNG\r\n\x1a\n'          # 뷰와 bytes 직접 비교

off = 8
while off < len(mv):
    (length,) = struct.unpack_from('>I', mv, off)     # 슬라이스 복사 없음
    tag = bytes(mv[off + 4:off + 8])
    print(tag, length)
    if tag == b'IHDR':
        width, height, depth, color, *_ = struct.unpack_from('>IIBBBBB', mv, off + 8)
        print(f"  {width}x{height} depth={depth} color={color}")
    off += 12 + length
```

```text nolines
b'IHDR' 13
  2x2 depth=8 color=2
b'IDAT' 19
b'IEND' 0
```

여기서 `unpack_from(fmt, buffer, offset)` 이 핵심이다. **`struct.unpack(fmt, data[off:off+4])` 은 슬라이스 복사를 만든다.** `unpack_from` 은 오프셋을 직접 받아서 복사가 없다. 그리고 `memoryview` 를 그대로 먹는다 — 버퍼 프로토콜을 받으니까.

::: perf Struct 객체를 미리 만들고 iter_unpack 을 써라
같은 레코드 10만 개를 파싱하는 세 가지 방법이다.

```python title="struct 파싱 3종"
import struct, timeit

n = 100_000
data = struct.pack('<' + 'ihf' * n, *([1, 2, 3.0] * n))
s = struct.Struct('<ihf')        # 포맷을 미리 컴파일

def loop_slice():                # ❌
    return [struct.unpack('<ihf', data[i:i + 10])
            for i in range(0, len(data), 10)]

def loop_from():                 # 낫다
    return [s.unpack_from(data, i)
            for i in range(0, len(data), 10)]

def it():                        # ✅
    return list(s.iter_unpack(data))
```

```text nolines
   loop_slice   0.0120 s
   loop_from    0.0083 s        <- 슬라이스 복사 제거
   it           0.0047 s        <- 루프까지 C 레벨로
```

(Python 3.14.5 / Windows 기준 실측.)

**2.5배다.** 셋 다 $O(n)$ 인데 상수가 다르다. 어디서 왔나.

1. `data[i:i+10]` 이 10만 개의 임시 `bytes` 를 만든다 → `unpack_from` 이 제거.
2. `struct.unpack('<ihf', ...)` 은 매번 포맷 문자열을 파싱한다. 모듈 레벨 함수는 캐시가 있지만 그 조회 비용도 공짜가 아니다 → `Struct` 객체가 제거.
3. 파이썬 `for` 루프 자체 → `iter_unpack` 이 C로 내린다.

**포맷이 고정이면 `Struct` 객체를 모듈 레벨에 한 번 만들어 재사용하라.** 이건 반복문마다 인터프리터를 도는 대신 C에 일을 넘기는 [5.3 파이썬 레벨 최적화](#/py-optimize)의 전형적인 패턴이다.
:::

::: tip int.from_bytes 로 충분할 때가 많다
필드가 하나면 `struct` 를 꺼낼 필요가 없다.

```pyrepl
>>> (1234).to_bytes(4, 'big')
b'\x00\x00\x04\xd2'
>>> int.from_bytes(b'\x04\xd2', 'big')
1234
>>> int.from_bytes(b'\xff', 'big', signed=True)
-1
>>> int.from_bytes(b'\x01\x02')          # 3.11+ 부터 기본값이 'big'
258
```

`struct` 와 달리 **크기 제한이 없다.** 임의 정밀도 정수를 그대로 다룬다.

```pyrepl
>>> (2 ** 100).to_bytes(13, 'big').hex()
'10000000000000000000000000'
```

암호학 코드에서 이 조합을 자주 쓴다. [1.2 숫자와 수치 연산](#/numbers)에서 파이썬 정수의 내부를 본다.
:::

## 스트림을 다룰 때의 마지막 함정

바이트를 청크로 읽어서 디코딩하는 코드는 반드시 이 버그를 만난다.

```pyrepl
>>> data = '한글'.encode('utf-8')
>>> data
b'\xed\x95\x9c\xea\xb8\x80'
>>> chunk1, chunk2 = data[:4], data[4:]      # 하필 글자 중간에서 끊겼다
>>> chunk1.decode('utf-8')
Traceback (most recent call last):
  ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xea in position 3: unexpected end of data
```

**멀쩡한 데이터인데 터진다.** 4096바이트씩 읽는 코드는 언젠가 글자 중간에서 끊긴다. ASCII로 테스트하면 절대 안 나오고, 한글 데이터를 넣는 순간 나온다.

`codecs` 의 증분 디코더가 답이다. 걸친 바이트를 내부에 들고 있다가 다음 청크와 이어 붙인다.

```pyrepl
>>> import codecs
>>> d = codecs.getincrementaldecoder('utf-8')()
>>> d.decode(chunk1)
'한'
>>> d.decode(chunk2, True)                   # True = 마지막 청크
'글'
```

::: tip 대부분의 경우 io 가 이미 해 준다
`open(..., encoding="utf-8")` 이 반환하는 `TextIOWrapper` 는 내부에서 증분 디코더를 쓴다. **텍스트 모드로 열었으면 이 문제는 없다.**

직접 증분 디코더가 필요한 자리는 파일이 아닌 스트림이다.

- `socket.recv()` 로 받은 청크
- `subprocess` 의 파이프를 직접 읽을 때
- HTTP 청크 전송 인코딩
- ROS 토픽으로 오는 조각난 페이로드

또는 `io.TextIOWrapper` 로 바이너리 스트림을 감싸면 된다.

```python
import io

text_stream = io.TextIOWrapper(binary_stream, encoding="utf-8")
```
:::

## 요약

- **디스크에도 네트워크에도 문자열은 없다. 바이트뿐이다.** `str` 은 바이트를 해석해서 만드는 것이고, 해석표가 인코딩이다.
- `bytes` 는 **0~255 정수의 불변 시퀀스**다. `b[0]` 은 `int`, `b[0:1]` 은 `bytes` — 이 비대칭이 최대 함정이다.
- **`b'a' == 'a'` 는 예외가 아니라 조용한 `False`.** CI에서 `-bb` 를 켜라.
- **`open()` 에 `encoding=` 을 항상 명시하라.** 한국어 윈도우 기본값은 cp949다. 3.15부터 UTF-8이 되지만 그때까지는 당신 책임이다.
- UTF-8이 이긴 이유는 **ASCII 상위 호환, 바이트 순서 없음, 자기 동기화, 부분 문자열 안전** — 네 가지 설계 속성이다.
- **`errors='ignore'` 는 문제를 지우는 게 아니라 증거를 지운다.** 터지게 두거나, `replace` + 로깅이거나, 왕복이 필요하면 `surrogateescape`.
- `bytes +=` 는 $O(n^2)$, `bytearray +=` 는 $O(n)$. 80만 번에서 228배.
- **`memoryview` 는 복사하지 않는다.** 앞에서 소비하는 코드에서 8000배, 슬라이스 메모리는 10MB → 496바이트. 대신 원본을 잠근다(`BufferError`) — `with` 로 써라.
- **버퍼 프로토콜이 파이썬과 NumPy·OpenCV·PyTorch·ROS를 잇는 지점이다.** `np.frombuffer` 도 `torch.from_numpy` 도 복사가 없다.
- `struct` 포맷은 **반드시 `<`/`>` 로 시작하라.** 생략하면 C 정렬 패딩이 끼어들어 `'ci'` 가 5가 아니라 8이 된다.

::: quiz 연습문제
1. 다음 각각의 출력을 **먼저 예측한 뒤** 실행해서 확인하라.

   ```python
   data = b'\x89PNG'
   print(data[0] == 0x89)
   print(data[0] == b'\x89')
   print(data[0:1] == b'\x89')
   print(data == '\x89PNG')
   print(list(data)[:2])
   ```

2. `struct.calcsize` 로 다음 넷을 예측한 뒤 확인하라. 왜 다른가?

   ```python
   struct.calcsize('<hi')
   struct.calcsize('hi')
   struct.calcsize('<ih')
   struct.calcsize('ih')
   ```

3. 아래 코드는 왜 `BufferError` 를 내는가? 두 가지 방법으로 고쳐라 — 하나는 `with`, 하나는 뷰의 생명 주기를 바꾸는 방법으로.

   ```python
   buf = bytearray(1024)
   view = memoryview(buf)
   header = view[:4]
   buf.extend(b'more data')
   ```

4. 다음 함수는 100MB 파일에서 사실상 멈춘다. 이유를 설명하고, `memoryview` 로 고쳐라. 고치기 전후에 복사되는 총 바이트 수를 각각 계산하라.

   ```python
   def parse_records(data: bytes, record_size: int = 64):
       out = []
       while data:
           out.append(data[:record_size])
           data = data[record_size:]
       return out
   ```

5. **깊이 생각해 볼 문제.** 다음이 왜 `True` 인지 설명하라. 그리고 `str` 에는 왜 이런 게 없는지도 설명하라.

   ```python
   import numpy as np
   ba = bytearray(4)
   arr = np.frombuffer(ba, dtype=np.uint8)
   mv = memoryview(ba)
   arr[0] = 7
   print(mv[0] == 7 and ba[0] == 7)
   ```

6. **손으로 푸는 문제.** `'가'.encode('utf-8')` 은 `b'\xea\xb0\x80'` 이다. `'가'` 의 코드포인트는 U+AC00이다. UTF-8 3바이트 인코딩 규칙(`1110xxxx 10xxxxxx 10xxxxxx`)을 써서 U+AC00에서 이 세 바이트가 나오는 과정을 계산으로 보여라.
:::

**다음 절**: [1.6 dict — 해시 테이블의 내부](#/dict) — `bytes` 의 `ob_shash` 가 왜 거기 있었는지, 그리고 파이썬이 어떻게 딕셔너리를 그렇게 빠르고 그렇게 작게 만드는지.
