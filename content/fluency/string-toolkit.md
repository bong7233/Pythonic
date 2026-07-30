# 11.3 문자열 다루기 완전 정복

::: lead
코딩테스트에서 가장 많이 나오는 자료형은 트리도 그래프도 아니라 `str` 이다. 그런데 백지 앞에서 손이 멈추는 지점도 여기다. "숫자로만 이뤄졌는지 확인"에서 3분을 쓰고, `split` 이 왜 빈 문자열을 하나 뱉는지 몰라 답이 틀린다. 이 절은 `str` 메서드 설명서가 아니다. **문제 문장의 어떤 표현이 어떤 메서드를 가리키는지**, 그리고 그 메서드가 언제 배신하는지를 다룬다. 문자열의 내부(유니코드, 메모리, f-string 문법)는 [1.4 문자열과 유니코드](#/strings)에 있다. 여기는 손이다.
:::

## 문제 문장이 메서드를 가리킨다

[11.1](#/fluency-gap)에서 봤듯 막히는 첫 지점은 **번역**이다. 문제 문장을 읽고 도구가 안 떠오른다. 문자열 문제에서는 이 대응이 거의 고정돼 있다.

| 문제 문장에 이런 말이 나오면 | 꺼낼 것 |
| --- | --- |
| "쉼표로 구분된", "공백으로 나뉜" | `split` |
| "앞뒤 공백을 무시한다", "개행 포함" | `strip` / `rstrip` |
| "~로 시작하는", "~로 끝나는" | `startswith` / `endswith` (튜플 인자!) |
| "포함되어 있으면", "몇 번 나오는가" | `in` / `count` / `find` |
| "숫자로만", "영문자로만" | `isdecimal` / `isalpha` / `isalnum` |
| "대소문자를 구분하지 않는다" | `lower()` 로 먼저 정규화 |
| "확장자를 뗀다", "접두사를 뗀다" | `removesuffix` / `removeprefix` |
| "여러 글자를 한꺼번에 바꾼다·지운다" | `str.maketrans` + `translate` |
| "자리수를 맞춰 0을 채운다" | `zfill` |
| "뒤집는다", "거꾸로" | `s[::-1]` |
| "조각들을 이어 붙인다" | `"".join(...)` |
| "규칙을 전부 만족", "하나라도 있으면" | `all(...)` / `any(...)` |

이 표를 외우라는 게 아니다. **문장을 읽는 즉시 오른쪽 칸이 떠오르는 상태**를 만들라는 것이다. 지금 안 떠오르는 행이 당신이 다음 30분에 손으로 쳐 볼 것이다.

::: tip 메서드 이름이 기억 안 날 때
`dir(str)` 을 REPL에서 치면 전부 나온다. 이름이 반쯤 기억나면 `[m for m in dir(str) if "part" in m]` 처럼 걸러라. 검색창을 여는 것보다 빠르고 오프라인 환경에서도 된다.
:::

## 자르기 — `split` 하나로 다 되지 않는다

`split` 은 **인자를 주느냐 안 주느냐로 완전히 다른 함수**가 된다. 이 차이를 모르면 공백이 여러 개인 입력에서 조용히 틀린다.

```pyrepl
>>> "  A12  B7  ".split()
['A12', 'B7']
>>> "  A12  B7  ".split(" ")
['', '', 'A12', '', 'B7', '', '']
```

인자가 없으면 **연속된 공백을 하나로 보고 양끝을 버린다.** 인자를 주면 **구분자 하나하나가 경계**라 빈 조각이 그대로 남는다. 표준 입력을 다룰 때는 거의 항상 인자 없는 `split()` 이 맞다.

빈 문자열에서도 둘이 갈린다.

```pyrepl
>>> "".split()
[]
>>> "".split(",")
['']
```

`"".split(",")` 가 `['']` 인 것은 버그가 아니다. "구분자가 0개면 조각은 1개"라는 규칙이 일관되게 적용된 결과다. 하지만 `for x in "".split(","):` 를 도는 코드는 **빈 입력에서 한 번 돈다.** 빈 줄 처리를 잊으면 여기서 터진다.

자르는 도구는 네 개고 목적이 다르다.

```text nolines
"2024-03-15T09:30:00"

  .split("T")       ──▶  ['2024-03-15', '09:30:00']        전부 자른다
  .split("-", 1)    ──▶  ['2024', '03-15T09:30:00']        앞에서 한 번만
  .rsplit("-", 1)   ──▶  ['2024-03', '15T09:30:00']        뒤에서 한 번만
  .partition("T")   ──▶  ('2024-03-15', 'T', '09:30:00')   구분자를 남긴다
  .split()          ──▶  ['2024-03-15T09:30:00']           공백이 없어 안 잘린다
```

`maxsplit` 은 **뒤쪽에 구분자가 또 들어 있어도 되는** 경우에 쓴다. `key=value` 에서 값에 `=` 가 들어갈 수 있는 상황이 대표적이다.

```pyrepl
>>> "note=a=b=c".partition("=")
('note', '=', 'a=b=c')
>>> "flagonly".partition("=")
('flagonly', '', '')
>>> "flagonly".rpartition("=")
('', '', 'flagonly')
```

`partition` 이 `split` 보다 나은 이유는 **결과 길이가 항상 3**이라는 것이다. 구분자가 없어도 언패킹이 실패하지 않는다. 그래서 `sep` 이 빈 문자열인지만 보면 "구분자가 있었는가"를 알 수 있다. `split("=", 1)` 은 길이가 1일 수도 2일 수도 있어서 매번 `len` 을 재야 한다.

::: warn `splitlines()` 와 `split("\n")` 은 다르다
```pyrepl
>>> "a\nb\n".split("\n")
['a', 'b', '']
>>> "a\nb\n".splitlines()
['a', 'b']
>>> "a\r\nb".splitlines()
['a', 'b']
```
파일이나 여러 줄 입력은 대개 마지막에 개행이 붙는다. `split("\n")` 은 그 자리에 **빈 문자열을 하나 만든다.** 그리고 윈도우에서 만든 입력의 `\r` 도 `split("\n")` 은 못 없앤다 — 각 줄 끝에 `\r` 이 남는다. 이 둘이 각각 다른 방식으로 배신한다.

```pyrepl
>>> "12\r\n7\r\n".split("\n")
['12\r', '7\r', '']
>>> int("12\r")
12
>>> "A3\r" == "A3"
False
>>> int("")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: invalid literal for int() with base 10: ''
```

남은 `\r` 로는 `int()` 가 죽지 않는다. `int()` 는 앞뒤 공백류를 전부 무시하고, `\r` 도 공백류다. 그래서 숫자 입력에서는 조용히 통과한다. 대신 **문자열 비교와 딕셔너리 조회가 조용히 실패한다** — `slot == "A3"` 이 `False` 가 되고 `counts["A3\r"]` 가 따로 하나 더 생긴다. 실제로 예외를 던지는 쪽은 오히려 마지막 빈 조각이다. `int("")` 는 `ValueError` 다. 여러 줄을 쪼갤 때는 `splitlines()` 를 기본값으로 삼아라.
:::

::: cote 시험장 입력 파싱의 기본형
```python title="조각 — 표준 입력이 있을 때만 돈다"
n = int(input())
nums = list(map(int, input().split()))          # 공백 개수를 신경 쓸 필요가 없다
name, score = input().split()                   # 개수가 정확할 때만 언패킹
```
`sys.stdin.readline()` 을 쓰면 **개행이 붙어 온다.** 숫자면 `int()` 가 알아서 무시하지만 문자열이면 `.rstrip()` 이 필수다. 입출력 속도 자체는 [8.2 입출력 최적화](#/io-optimize)에서 다룬다.
:::

## 다듬기 — `strip` 은 접두사 제거가 아니다

이건 실무와 시험장 양쪽에서 반복해서 사고를 낸다.

::: danger `strip(".py")` 는 `.py` 를 떼지 않는다
`strip` 의 인자는 **문자열이 아니라 문자 집합**이다. "양끝에서 이 집합에 속한 문자가 안 나올 때까지 계속 벗겨라"라는 뜻이다.

```pyrepl
>>> "puppy.py".strip(".py")
'u'
>>> "puppy.py".removesuffix(".py")
'puppy'
>>> "commerce.com".strip(".com")
'erce'
```
`"puppy.py".strip(".py")` 는 `{'.', 'p', 'y'}` 를 양끝에서 계속 벗겨 `'u'` 하나만 남긴다. 테스트 데이터가 `"main.py"` 뿐이면 통과하고, `"puppy.py"` 가 들어오는 순간 틀린다. **접두사·접미사를 뗄 때는 `removeprefix` / `removesuffix` 를 써라.** 둘 다 없으면 원본을 그대로 돌려주므로 `if` 로 감쌀 필요도 없다.

```pyrepl
>>> "no-prefix".removeprefix("SKU-")
'no-prefix'
>>> "SKU-A-SKU".removeprefix("SKU-")
'A-SKU'
```
`replace("SKU-", "", 1)` 로도 같은 결과를 얻지만, 그건 **문자열 어디에 있든** 첫 등장을 지운다. "맨 앞에 있을 때만"이라는 의도를 코드가 말해 주지 않는다.
:::

인자 없는 `strip()` 은 안전하다. 공백·탭·개행 전부를 양끝에서 없앤다. 입력 한 줄을 받으면 **가장 먼저 `strip()`** 이 습관이 돼야 한다.

## 검증 — 규칙 여러 개를 어떻게 배치하는가

문자열 문제의 절반은 "이 문자열이 규칙을 만족하는가"다. 규칙이 서너 개를 넘어가면 코드 모양을 정해야 한다. 선택지는 둘이다.

- **조기 반환** — `if not 조건: return False` 를 규칙마다 하나씩. 참/거짓만 필요할 때.
- **규칙 테이블** — `(이름, 검사함수)` 목록을 만들고 `all` 로 돌린다. **어느 규칙이 깨졌는지**를 알려야 할 때.

조기 반환은 [11.1](#/fluency-gap)에서 봤다. 여기서는 두 번째를 만든다. 소재는 창고 재고 코드다.

> 재고 코드는 `창고-품목-등급` 형식이다. 창고는 `SEO`, `BSN`, `ICN` 중 하나, 품목은 숫자 5자리(앞자리 0 허용), 등급은 `A`~`E` 한 글자다.

```python title="sku.py"
WAREHOUSES = {"SEO", "BSN", "ICN"}
GRADES = "ABCDE"

RULES = [
    ("칸 수", lambda s: s.count("-") == 2),
    ("창고", lambda s: s.split("-")[0] in WAREHOUSES),
    ("품목", lambda s: len(s.split("-")[1]) == 5 and s.split("-")[1].isdecimal()),
    ("등급", lambda s: s.split("-")[2] in GRADES),
]


def is_valid(code):
    return all(check(code) for _name, check in RULES)


def first_broken(code):
    # 첫 번째로 깨진 규칙 이름. 다 통과하면 None.
    return next((name for name, check in RULES if not check(code)), None)


for code in ["SEO-04821-A", "BSN-4821-A", "PUS-04821-A",
             "SEO-0482X-A", "SEO-04821-Z", "SEO-04821", ""]:
    print(f"{code!r:16} {is_valid(code)!s:6} {first_broken(code)}")
```

```text nolines
'SEO-04821-A'    True   None
'BSN-4821-A'     False  품목
'PUS-04821-A'    False  창고
'SEO-0482X-A'    False  품목
'SEO-04821-Z'    False  등급
'SEO-04821'      False  칸 수
''               False  칸 수
```

규칙 하나가 늘어도 `RULES` 에 한 줄이 늘 뿐이다. 검증 함수는 손대지 않는다. 그리고 오류 메시지가 공짜로 따라온다 — 과제형([12.5 예외와 오류 설계](#/error-design))에서 특히 값이 나가는 성질이다.

### 단락 평가가 뒤 규칙의 전제를 보장한다

위 코드에서 `"SEO-04821"` 은 `split("-")[2]` 가 없다. 그런데도 `IndexError` 가 안 난다. **`all()` 이 `False` 를 만나는 순간 멈추기 때문이다.** 첫 규칙("칸 수")이 이미 실패했으므로 뒤 세 개는 아예 호출되지 않는다.

이건 우연이 아니라 설계다. **규칙의 순서가 곧 전제 조건의 순서**다. 구조를 확인하는 규칙을 앞에, 내용을 확인하는 규칙을 뒤에 둔다.

::: danger 대괄호 하나 때문에 터진다
`all(...)` 안의 제너레이터 표현식을 리스트 컴프리헨션으로 바꾸면 단락 평가가 사라진다.

```python title="조각 — 위 sku.py 안에서 비교"
all(check(code) for _name, check in RULES)     # ✅ 하나 실패하면 즉시 멈춘다
all([check(code) for _name, check in RULES])   # ❌ 전부 먼저 계산한다
```
아래 줄에 `"SEO-04821"` 을 넣으면 이렇게 된다.

```text nolines
IndexError: list index out of range
```
리스트를 먼저 **완성한 뒤** `all` 에 넘기므로, 실패한 규칙 뒤의 규칙까지 전부 실행된다. `any`/`all` 에 컴프리헨션을 넘길 때 대괄호를 쓰지 마라. 느린 것보다 **터지는 것**이 진짜 문제다. 제너레이터 표현식 자체는 [1.9](#/comprehensions)에 있다.
:::

::: warn 빈 것에 대한 `all` 과 `any`
```pyrepl
>>> all([])
True
>>> any([])
False
```
`all([])` 이 `True` 인 것은 "반례가 없다"는 뜻이라 논리적으로 맞다. 그런데 실전에서는 **"규칙 목록이 비어 있으면 뭐든 통과"** 라는 뜻이 되어 검증이 통째로 무력화된다. 필터링 결과를 `all` 에 넣을 때는 "이 목록이 빌 수 있는가"를 먼저 물어라.
:::

### `str.isX()` 와 `all(...)` 은 빈 문자열에서 갈린다

"영숫자로만 이뤄졌는가"를 두 가지로 쓸 수 있다. 결과가 다르다.

```pyrepl
>>> "".isalnum()
False
>>> all(c.isalnum() for c in "")
True
```

**글자의 종류를 검사하는 `isX()` 는 빈 문자열에 대해 모두 `False`** 다 — `isalnum`, `isalpha`, `isdecimal`, `isdigit`, `isnumeric`, `islower`, `isupper`, `isspace`, `istitle`, `isidentifier` 전부. "그런 글자가 최소 하나는 있어야 한다"는 조건이 이름 안에 들어 있기 때문이다. 반면 `all(...)` 은 `True` 다. 빈 입력을 별도로 막지 않을 거라면 `isalnum()` 쪽이 안전하다. 반대로 "빈 문자열은 허용"이 요구사항이면 `all` 이 맞다. **둘 중 하나를 우연히 고르지 마라.**

예외가 둘 있다. `isascii()` 와 `isprintable()` 은 빈 문자열에서 `True` 다.

```pyrepl
>>> "".isascii(), "".isprintable()
(True, True)
```

이 둘은 "이런 글자가 있는가"가 아니라 **"금지된 글자가 없는가"** 를 묻는다. 없는 것을 묻는 조건은 빈 입력에서 자동으로 만족된다 — `all([])` 이 `True` 인 것과 같은 논리다. `dir(str)` 의 `is*` 12개 중 이 둘만 그렇다.

`any` 는 "적어도 하나"를 그대로 옮긴다.

```pyrepl
>>> any(c.isdecimal() for c in "abc1")
True
>>> any(c.isdecimal() for c in "abc")
False
```

"숫자인가"를 물을 때 `isdigit()` 이 아니라 `isdecimal()` 을 쓰는 이유는 [11.1](#/fluency-gap)에서 이미 한 번 당했다. 기준은 하나다 — **`int()` 가 받는가**. 그래서 전각 숫자처럼 낯선 입력에서도 둘의 답이 일치한다.

```pyrepl
>>> "２４".isdecimal()
True
>>> int("２４")
24
```

## 찾기 — `find` / `index` / `in` / `count`

넷은 답하는 질문이 다르다.

| 도구 | 질문 | 없을 때 |
| --- | --- | --- |
| `sub in s` | 있는가 | `False` |
| `s.find(sub)` | 어디에 있는가 | `-1` |
| `s.index(sub)` | 어디에 있는가 | `ValueError` |
| `s.count(sub)` | 몇 번 나오는가 | `0` |

```pyrepl
>>> "A-12".find("=")
-1
>>> "A-12".index("=")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: substring not found
```

`find` 가 `-1` 을 준다는 것이 함정의 근원이다. `-1` 은 파이썬에서 **유효한 인덱스**다. `s[s.find(x)]` 는 못 찾았을 때 조용히 마지막 글자를 준다. 존재 여부만 궁금하면 `in` 을 쓰고, `find` 를 썼으면 **반드시 `!= -1` 로 검사해라.**

::: danger `count` 는 겹치는 것을 안 센다
```pyrepl
>>> "aaaa".count("aa")
2
>>> "ababa".count("aba")
1
```
`count` 는 찾은 자리 **뒤부터** 다시 찾는다. 겹치는 등장까지 세야 하면 `find` 를 한 칸씩 밀며 직접 돌아야 한다.

```python title="겹치는 등장 세기"
def count_overlapping(s, sub):
    n, i = 0, s.find(sub)
    while i != -1:
        n += 1
        i = s.find(sub, i + 1)      # 찾은 자리 다음 칸부터 다시
    return n


print("aaaa".count("aa"), count_overlapping("aaaa", "aa"))
print("ababa".count("aba"), count_overlapping("ababa", "aba"))
```

```text nolines
2 3
1 2
```
문제 문장이 "겹쳐도 센다"인지 아닌지를 먼저 확인해라. 이 한 단어 때문에 채점이 갈린다. 입력이 아주 커서 이 루프로도 느리면 그때가 [7.22 문자열 알고리즘](#/string-algo)이 필요한 순간이다. 그 전에는 아니다.
:::

::: tip `startswith` 는 튜플을 받는다
```pyrepl
>>> name = "report_2024_final.csv"
>>> name.endswith((".csv", ".tsv"))
True
>>> name.startswith(("report_", "log_"))
True
```
`or` 로 늘어놓지 마라. 후보가 늘어나도 튜플만 늘리면 된다. `in` 은 이렇게 못 한다 — `any(name.endswith(e) for e in exts)` 로 써야 한다.
:::

## 파싱 — 값을 꺼내 타입을 확정한다

파싱은 절차가 정해져 있다. 매번 이 순서다.

```text nolines
raw line
   │
   ├── .strip()                     앞뒤 공백과 개행을 없앤다
   ├── skip empty / comment         빈 줄과 주석을 여기서 버린다
   ├── .split(sep)                  필드로 자른다
   ├── len(fields) check            칸 수가 맞는지 본다
   ├── int(...) / .isdecimal()      타입을 확정한다
   ▼
record tuple
```

자판기 판매 로그를 예로 든다. 형식은 `시각|슬롯|상품|단가|수량` 이고, 주석 줄과 빈 줄이 섞여 있다.

```python title="vending.py"
RAW = """\
# time|slot|item|price|qty
09:12|A3|cola|1500|2

09:15|B1|water|900|1
09:41|A3|cola|1500|3
"""


def parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None                      # 건너뛸 줄은 None 하나로 통일한다
    time, slot, item, price, qty = line.split("|")
    return time, slot, item, int(price), int(qty)


rows = [r for line in RAW.splitlines() if (r := parse_line(line)) is not None]
for r in rows:
    print(r)
print("매출", sum(price * qty for *_rest, price, qty in rows))
```

```text nolines
('09:12', 'A3', 'cola', 1500, 2)
('09:15', 'B1', 'water', 900, 1)
('09:41', 'A3', 'cola', 1500, 3)
매출 8400
```

여기서 배울 것은 세 가지다.

1. **건너뛸 줄은 `None` 하나로 표현한다.** 함수 하나가 "한 줄 → 레코드 또는 없음"만 책임진다.
2. **언패킹이 곧 검증이다.** 칸 수가 다르면 `ValueError` 로 즉시 죽는다. 조용히 틀리는 것보다 훨씬 낫다. 죽지 말아야 하는 상황이면 `len(fields)` 를 먼저 재라.
3. **`int()` 는 파싱 단계에서 끝낸다.** 문자열 숫자를 뒤까지 들고 가면 비교와 정렬에서 반드시 사고가 난다(`"9" > "10"` 은 `True` 다).

구분자가 아예 없는 형식도 있다. 자릿수가 고정돼 있으면 자르는 게 아니라 **슬라이스로 떠낸다.**

```pyrepl
>>> rec = "SEO0482100025A"
>>> rec[:3], rec[3:8], int(rec[8:13]), rec[13]
('SEO', '04821', 25, 'A')
```

경계 숫자를 코드 여기저기 흩어 놓지 마라. `FIELDS = [("wh", 0, 3), ("item", 3, 8), ...]` 처럼 표로 만들면 형식이 바뀌어도 표만 고친다. 규칙 테이블과 같은 발상이다.

## 슬라이싱 — 뒤집기와 부분 추출

슬라이스는 **범위를 벗어나도 죽지 않는다.** 인덱싱은 죽는다. 이 비대칭이 실전에서 꽤 쓸모 있다.

```pyrepl
>>> code = "SEO-04821-A"
>>> code[100:200]
''
>>> code[100]
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
IndexError: string index out of range
```

그래서 `s[:1]` 은 빈 문자열에서도 안전하고 `s[0]` 은 아니다. "첫 글자가 대문자인가"를 빈 입력까지 포함해 물어야 하면 `s[:1].isupper()` 가 분기 없이 끝난다.

뒤집기는 `s[::-1]` 이 표준이다. 회문 판정은 정규화 한 줄과 뒤집기 한 줄로 끝난다.

```pyrepl
>>> s = "다시 합창합시다"
>>> t = "".join(c for c in s if not c.isspace())
>>> t == t[::-1]
True
>>> u = "".join(c.lower() for c in "Was it a car or a cat I saw?" if c.isalnum())
>>> u == u[::-1]
True
```

`isalnum()` 은 한글에도 `True` 를 준다. 유니코드 기준이라 영문 전용이 아니다.

::: perf `s[::-1]` 과 `"".join(reversed(s))` 는 자릿수가 다르다
길이 100,000 문자열, 각 방식 여러 번 반복 측정.

```text nolines
s[::-1]                  61 ~   64 us
"".join(reversed(s))   1540 ~ 1600 us
```
(Python 3.14.0rc2 / Linux 기준 실측. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

약 25배 차이다. 원인은 흔한 오해와 다르다. `[::-1]` 은 결과 길이를 먼저 알기 때문에 버퍼를 한 번 잡고, **C 루프가 코드포인트를 뒤에서 앞으로 읽어 그 버퍼에 채운다.** 파이썬 바이트코드는 한 번도 돌지 않는다. `join(reversed(s))` 는 **글자 하나마다 파이썬 수준 이터레이션을 한 바퀴 돌고**, `join` 은 총 길이를 미리 알아야 하니 그 이터레이터를 다시 리스트로 펼친 뒤 순회한다. 즉 10만 번의 이터레이터 호출과 10만 칸 리스트가 추가로 생긴다.

"`reversed` 는 글자마다 새 문자열 객체를 만들어서 느리다"는 설명을 자주 보는데, ASCII 문자열에서는 틀렸다. 1글자 latin-1 문자열 256개는 CPython이 미리 만들어 두고 계속 재사용한다.

```pyrepl
>>> [c is chr(ord(c)) for c in reversed("abcABC")]
[True, True, True, True, True, True]
>>> [c is chr(ord(c)) for c in reversed("가나다")]
[False, False, False]
```

ASCII 쪽은 전부 같은 객체다. 새로 만드는 게 아니라 그 싱글턴을 가리키기만 한다(3.12부터 이 싱글턴들은 불멸 객체라 참조 카운트조차 건드리지 않는다). 그러니 위 25배의 원인은 객체 생성이 아니다. `join` 을 떼고 `list(reversed(s))` 만 재면 약 930 us — 전체 1,560 us 의 60%가 **순회 그 자체**다.

한글은 이야기가 다르다. 캐시에 없으니 정말로 글자마다 새 객체가 만들어진다. 같은 길이 100,000의 한글 문자열로 재면 `list(reversed(s))` 가 6,700~7,000 us 로 7배 넘게 뛴다. 반면 `s[::-1]` 은 63 us → 275 us 로 4배 남짓이다 — 객체를 하나도 안 만드는 쪽은 문자 폭이 넓어져도 버퍼에 쓰는 비용만 늘어난다. **"파이썬 객체를 만든다"는 설명은 비ASCII에서만 맞고, ASCII에서 25배가 나는 이유는 순회다.**

읽기 좋으라고 `join(reversed(...))` 를 쓸 이유가 없다 — `[::-1]` 이 더 짧기도 하다.
:::

일정 길이로 토막 내는 것도 슬라이스다. 이 관용구는 격자 문제([11.4](#/array-grid))에서도 그대로 쓴다.

```pyrepl
>>> digits = "0482100025"
>>> [digits[i:i + 2] for i in range(0, len(digits), 2)]
['04', '82', '10', '00', '25']
```

::: warn `capitalize()` 와 `title()` 은 생각보다 공격적이다
```pyrepl
>>> "iPhone 15".capitalize()
'Iphone 15'
>>> "it's a test".title()
"It'S A Test"
```
`capitalize()` 는 첫 글자를 올리는 김에 **나머지를 전부 내린다.** `title()` 은 알파벳이 아닌 문자 뒤를 전부 단어 시작으로 본다 — 아포스트로피 뒤까지. 첫 글자만 올리고 싶으면 `s[:1].upper() + s[1:]` 를 써라. 길고 못생겼지만 하는 일이 정확히 그것뿐이다.
:::

## 만들기 — `join`, `translate`, 폭 맞추기

조각을 이어 붙일 때는 `join` 이다. `+=` 를 반복하지 않는 이유는 [1.4](#/strings)에 있다. 여기서는 `join` 자체의 함정만 본다.

```pyrepl
>>> "-".join(["A", 1, "B"])
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: sequence item 1: expected str instance, int found
>>> "-".join(str(x) for x in ["A", 1, "B"])
'A-1-B'
```

`join` 은 자동 변환을 안 한다. 숫자가 섞이면 `str` 로 바꾸는 것은 당신 몫이다.

::: perf `join` 에는 무엇을 넘기는 게 빠른가
`PARTS` 는 **길이 8인 문자열 100,000개의 리스트**(합치면 80만 자)다. 세 가지를 여러 번 반복 측정했다.

```text nolines
"".join(PARTS)                  0.73 ~ 0.84 ms      이미 리스트다
"".join([p for p in PARTS])     2.76 ~ 3.31 ms      리스트 컴프리헨션
"".join(p for p in PARTS)       4.13 ~ 4.90 ms      제너레이터 표현식
```
(Python 3.14.0rc2 / Linux 기준 실측. 조각의 개수와 길이를 바꾸면 절대값은 2배까지 움직인다. 고정되는 것은 순서다 — 리스트가 가장 빠르고 제너레이터가 가장 느리다.)

`join` 은 총 길이를 미리 알아야 버퍼를 한 번에 잡는다. 제너레이터를 받으면 **내부에서 먼저 리스트로 펼친 뒤** 다시 순회한다. 그래서 제너레이터가 오히려 느리다. 여기는 `any`/`all` 과 정반대다 — **`any`/`all` 에는 제너레이터, `join` 에는 리스트**로 기억해라. 다만 이 차이는 조각이 수만 개일 때 이야기고, 그 아래에서는 읽기 좋은 쪽을 골라라.
:::

여러 글자를 한꺼번에 바꾸거나 지울 때는 `translate` 다. 변환표를 `str.maketrans` 로 만든다. 세 번째 인자는 **삭제할 문자들**이다.

```pyrepl
>>> table = str.maketrans("OIl", "011")
>>> "SEO-O482I-A".translate(table)
'SE0-04821-A'
>>> "1,234,567".translate(str.maketrans("", "", ","))
'1234567'
```

첫 줄은 스캐너가 `0` 을 `O` 로, `1` 을 `I`/`l` 로 잘못 읽는 것을 보정하는 실전 패턴이다. 그런데 결과를 자세히 봐라. 창고 코드 `SEO` 가 `SE0` 이 됐다. **변환표는 어디에 적용하는지를 가리지 않는다.** 보정이 필요한 자리에만 적용하려면 먼저 자르고 나서 `translate` 해야 한다. 이건 아래 연습문제 1번이다.

`replace` 를 세 번 이어 부르는 것과 결과가 같아 보여도, `replace` 체인은 **앞 단계가 만든 글자를 뒤 단계가 다시 바꿀 수 있다.** `translate` 는 원본을 한 번만 훑으므로 그런 연쇄가 없다.

::: perf 문자 여러 종을 지우는 세 가지
원본은 **길이 100,000, 그중 10%가 제거 대상**이다. 제거 대상은 `string.punctuation` 의 앞 10종(`!"#$%&'()*`), 나머지는 영문자와 공백이다. 여러 번 반복 측정.

```text nolines
s.translate(table)                     0.29 ~ 0.30 ms
replace 10번 체인                       0.91 ~ 0.96 ms
"".join(c for c in s if c not in set)  4.8  ~ 5.3  ms
```
(Python 3.14.0rc2 / Linux 기준 실측. 앞의 두 값은 제거 대상이 원본에 얼마나 자주 나오는지에 따라 움직인다 — 비율을 0%에서 30%로 올리면 `translate` 는 0.20 → 0.51 ms, `replace` 체인은 0.62 → 1.39 ms 다. 순서와 자릿수 차이는 어디서나 같다.)

세 결과가 같은 문자열인지 확인하고 잰 값이다. `join`+제너레이터는 글자마다 파이썬 루프를 도니 자릿수가 다르다. 반면 `translate` 와 `replace` 는 원본 구성이 바뀌어도 서로의 자리를 바꾸지 않는다.

지울 문자 종류만 바꿔 가며(`string.punctuation` 의 앞 3종·10종·21종, 제거 대상 비율은 10%로 고정) `replace` 체인과 `translate` 의 비를 재면 이렇다. 3종 1.6배, 10종 3.2배, 21종 5.6배. 종류가 늘면 비가 거의 선형으로 커진다. **`replace` 는 문자 종류만큼 원본을 다시 훑고, `translate` 는 몇 종이든 한 번만 훑는다.** 실제로 `translate` 쪽 절대값은 3종이든 21종이든 0.29~0.30 ms 에서 움직이지 않는다. 구두점 제거처럼 지울 문자가 고정돼 있으면 변환표를 모듈 상수로 한 번만 만들어라.
:::

숫자를 자리수에 맞춰 채울 때 `zfill` 과 `rjust("0")` 은 다르다.

```pyrepl
>>> "-42".zfill(6)
'-00042'
>>> "-42".rjust(6, "0")
'000-42'
```

`zfill` 은 **부호를 알고 있다.** 부호를 앞에 두고 그 뒤를 채운다. 음수가 나올 수 있으면 `zfill` 이나 `f"{n:06d}"` 를 써라.

::: warn 한글은 `ljust` 로 정렬되지 않는다
`ljust`/`rjust`/`center` 는 **코드포인트 개수**로 센다. 한글은 고정폭 글꼴에서 두 칸을 차지하므로 표가 어긋난다.

```python title="가운데 줄만 밀린다"
for name, price in [("cola", 3000), ("생수", 900), ("energy", 2300)]:
    print(name.ljust(10) + str(price).rjust(6))
```

```text nolines
cola        3000
생수           900
energy      2300
```

표시 폭으로 채우려면 직접 세야 한다.

```python title="표시 폭 기준으로 채우기"
import unicodedata


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * (n - width(s))


for name, price in [("cola", 3000), ("생수", 900), ("energy", 2300)]:
    print(pad(name, 10) + str(price).rjust(6))
```

```text nolines
cola        3000
생수         900
energy      2300
```

`len("생수")` 는 2, 표시 폭은 4다. 이 구분이 왜 필요한지는 [1.4](#/strings)에 있다. 이 책의 아스키 다이어그램 검사기도 정확히 같은 이유로 존재한다.
:::

## 언제 `str` 을 벗어나는가

문자열 도구를 고집하면 오히려 손해인 지점이 셋 있다.

**하나. 글자를 하나씩 바꿔야 할 때.** `str` 은 불변이라 제자리 수정이 없다. `s[:i] + c + s[i+1:]` 를 반복하면 매번 전체를 복사한다.

```pyrepl
>>> "SEO-04821-A"[4] = "9"
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: 'str' object does not support item assignment
>>> chars = list("SEO-04821-A")
>>> chars[4] = "9"
>>> "".join(chars)
'SEO-94821-A'
```

::: perf 리스트로 바꿔서 고치고 다시 합쳐라
길이 20,000 문자열에서 10,000개 위치를 수정, 여러 번 반복 측정.

```text nolines
s = s[:i] + "b" + s[i+1:]   반복       16.4 ~ 17.6 ms
list -> 수정 -> "".join                 0.32 ~ 0.35 ms
```
(Python 3.14.0rc2 / Linux 기준 실측. 수정할 위치를 앞쪽에 몰아도, 뒤쪽에 몰아도, 무작위로 흩어도 앞 줄은 15 ms 아래로 내려가지 않는다. 절대값은 기기마다 다르지만 자릿수 차이는 어디서나 같다.)

약 50배 차이다. 슬라이스 재조립은 수정 한 번마다 $O(n)$ 을 쓰므로 전체가 $O(n^2)$ 이 된다. **문자 단위 수정이 두 번 이상 나오면 `list(s)` 로 바꿔라.** 자료구조별 실제 비용은 [7.2](#/py-ds-cost)에 있다.
:::

**둘. 패턴이 규칙적이지만 경우의 수가 많을 때.** 구분자가 여러 종류거나 선택적인 부분이 있으면 `split` 을 겹겹이 쌓는 대신 표준 라이브러리 `re` 를 꺼내라. 다만 코딩테스트에서는 대개 입력 형식이 고정이다. `re` 를 먼저 떠올렸다면 형식을 다시 읽어라 — 열에 아홉은 `split` 로 끝난다.

**셋. 빈도·그룹·정렬이 나오는 순간.** "가장 많이 나온 글자", "애너그램끼리 묶기" 같은 문제는 `str` 메서드가 아니라 `Counter` 와 `sorted` 의 영역이다. [11.2 표준 라이브러리 무기고](#/stdlib-arsenal)와 [11.5 딕셔너리와 집합](#/dict-set-patterns)으로 넘어가라. 문자열은 그 도구의 **입력을 만드는 단계**일 뿐이다.

## 요약

- `split()` 과 `split(sep)` 은 다른 함수다. 인자가 없으면 연속 공백을 하나로 보고 양끝을 버리고, 있으면 빈 조각이 남는다. `"".split(",")` 는 `['']` 이다. 여러 줄은 `splitlines()` 로 쪼갠다.
- `strip(".py")` 는 접미사를 떼지 않는다. **문자 집합**을 벗긴다. 접두사·접미사는 `removeprefix`/`removesuffix`.
- 규칙이 서너 개를 넘으면 `(이름, 검사함수)` 표를 만들고 `all(제너레이터)` 로 돌려라. 대괄호를 넣는 순간 단락 평가가 사라져 뒤 규칙이 터진다.
- 글자 종류를 검사하는 `str.isX()`(`isalnum`, `isdecimal`, `isspace` 등)는 빈 문자열에서 `False`, 같은 조건을 `all(...)` 로 쓰면 `True` 다. 어느 쪽이 요구사항인지 정하고 골라라. `isascii`/`isprintable` 은 "금지된 글자가 없는가"를 묻는 것이라 빈 문자열에서 `True` 다.
- `find` 는 없을 때 `-1` 을 준다. `-1` 은 유효한 인덱스라 조용히 틀린다. 존재 여부만 궁금하면 `in` 을 써라. `count` 는 겹치는 등장을 세지 않는다.
- 파싱은 `strip` → 건너뛸 줄 거르기 → `split` → 칸 수 확인 → `int()` 순서다. 숫자는 파싱 단계에서 확정해라.
- 뒤집기는 `s[::-1]`(`join(reversed(s))` 보다 약 25배 빠르다 — 글자마다 파이썬 순회를 도는 값이다). 여러 글자 치환·삭제는 `translate`. 문자 단위 수정이 반복되면 `list(s)`.

::: quiz 연습문제 — 전부 코드를 짜는 과제다
읽고 넘기지 마라. 편집기를 열고 실행해서 예시 출력이 그대로 나오는지 확인해라. 다섯 문제 합쳐 40분이 목표다.

1. **`normalize_sku(raw) -> str | None`** 을 쓰라. 입력은 사람이 손으로 옮겨 적은 재고 코드다. 앞뒤 공백과 **내부 공백**을 없애고, 대문자로 올리고, 품목 자리에 한해 스캐너 오독(`O`→`0`, `I`→`1`, `l`→`1`)을 보정한 뒤, 본문의 세 규칙(창고·품목 5자리 숫자·등급)을 만족하면 `창고-품목-등급` 형식 문자열을, 아니면 `None` 을 반환한다.
   - `"  seo-O482I-a "` → `'SEO-04821-A'`
   - `"ICN - 00007 - E"` → `'ICN-00007-E'`
   - `"seo-0482l-a"` → `'SEO-04821-A'`
   - `"PUS-04821-A"` → `None`, `"SEO-482-A"` → `None`, `"SEO04821A"` → `None`
   **`translate` 를 코드 전체가 아니라 품목 자리에만 적용해야 한다.** 전체에 걸면 창고 `SEO` 의 `O` 가 `0` 으로 바뀌어 창고 검사가 통째로 실패한다.
   그리고 **위에 적은 순서를 그대로 따르면 세 번째 예시가 `None` 이 된다.** `upper()` 가 소문자 `l` 을 `L` 로 바꿔 버려서 `str.maketrans("OIl", "011")` 의 `l` 항목이 영원히 걸리지 않는다. 보정을 대문자화보다 **앞에** 두든, 변환표를 `str.maketrans("OIL", "011")` 로 바꾸든 하나를 골라라. 이렇게 **한 단계가 뒤 단계의 전제를 조용히 무너뜨리는 것**이 파싱 코드에서 가장 흔한 사고다.

2. **`parse_log(text) -> tuple[list, list[int]]`** 를 쓰라. 본문의 자판기 로그를 받되, 칸 수가 5개가 아니거나 단가·수량이 숫자가 아닌 줄은 **버리고 그 줄 번호(1부터)를 따로 모아** 반환한다. 주석·빈 줄은 줄 번호를 세되 오류로 치지 않는다.
   아래 입력에서 정상 레코드 2개, 오류 줄 번호 `[3, 4]`, 매출 합계 `7500` 이 나와야 한다.
   ```text nolines
   1: # time|slot|item|price|qty
   2: 09:12|A3|cola|1500|2
   3: 09:15|B1|water|900
   4: 09:20|B1|water|900|x
   5: 09:41|A3|cola|1500|3
   ```
   **언패킹으로 죽게 두지 말고 `len` 을 먼저 재야 한다.** 여기가 이 문제의 전부다.

3. **`broken_rules(code) -> list[str]`** 을 쓰라. 본문의 `first_broken` 과 달리 **깨진 규칙을 전부** 돌려준다. 단락 평가가 사라지므로 `IndexError` 를 직접 막아야 한다.
   - `"SEO-04821-A"` → `[]`
   - `"PUS-482-Z"` → `['창고', '품목', '등급']`
   - `"SEO-04821"` → `['칸 수', '등급']`
   마지막 줄이 왜 `['칸 수', '품목', '등급']` 이 아닌지 설명할 수 있어야 한다. 설명 못 하면 아직 안 푼 것이다.

4. **`is_palindrome(s) -> bool`** 을 쓰라. 영문 대소문자와 공백·구두점을 무시한다. 한글도 지원해야 한다.
   - `"다시 합창합시다"` → `True`, `"소주 만 병만 주소"` → `True`
   - `"Was it a car or a cat I saw?"` → `True`, `"재고 관리"` → `False`
   그다음 **슬라이스를 쓰지 않는 버전**(양끝에서 좁혀 오는 두 인덱스)을 하나 더 짜고, 무작위 문자열 1000개에 대해 두 결과가 항상 같은지 `assert` 로 대조하라. 두 번째 버전은 [11.4](#/array-grid)의 투 포인터 관용구와 같은 모양이 된다.

5. **`render(rows) -> str`** 을 쓰라. `(코드, 상품명, 단가, 수량)` 목록을 받아 열이 정렬된 표 문자열을 만든다. 상품명에는 **한글이 섞여 있다.** 본문의 `width`/`pad` 를 써서 표시 폭 기준으로 맞추고, 단가·수량은 오른쪽 정렬, 마지막 줄에 합계를 넣어라. 출력을 터미널에 찍어 **눈으로 열이 맞는지 확인**해라. `ljust` 만 쓴 버전과 나란히 찍어 보면 차이가 바로 보인다.
:::

**다음 절**: [11.4 리스트·배열·격자 다루기](#/array-grid) — 문자열에서 쓴 슬라이스와 순회 관용구가 2차원으로 올라가면 무엇이 달라지는지, 그리고 2차원 리스트를 만들 때 절반이 빠지는 함정을 다룬다.
