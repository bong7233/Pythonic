# 1.13 상속, MRO, 컴포지션

::: lead
상속은 배우기 쉽고 쓰기 어렵다. `class Dog(Animal)` 은 5분이면 이해하지만, 클래스 네 개가 다이아몬드를 이루는 순간 "이 메서드는 대체 어디서 오는가"가 미스터리가 된다. 이 절은 그 미스터리를 없앤다. 파이썬이 메서드를 찾는 순서는 **C3 선형화**라는 결정론적 알고리즘이 정하고, `super()` 는 당신이 배운 것과 달리 **부모를 부르지 않는다.** 그리고 마지막에는 더 불편한 질문에 답한다 — 애초에 상속을 써야 하는가.
:::

## 문제부터: 이 코드는 무엇을 출력하는가

```python title="예측해 보라"
class A:
    def who(self): return "A"

class B(A):
    pass

class C(A):
    def who(self): return "C"

class D(B, C):
    pass

print(D().who())
```

`D` 는 `B` 를 먼저 상속했다. `B` 를 따라 올라가면 `A` 가 있고, `A.who` 는 `"A"` 를 반환한다. 그러니 답은 `"A"` 일 것 같다.

```pyrepl
>>> D().who()
'C'
```

`"C"` 다. `D` 의 상속 목록에서 `C` 는 **두 번째**인데도 이겼다. 왜인지 설명할 수 있어야 이 절을 넘어갈 수 있다.

## 다이아몬드

`D` 의 상속 그래프를 그리면 이렇게 생겼다.

```text nolines
        ┌───┐
        │ A │           <- 공통 조상
        └───┘
         ▲ ▲
   ┌─────┘ └─────┐
   │             │
 ┌───┐         ┌───┐
 │ B │         │ C │
 └───┘         └───┘
   ▲             ▲
   └─────┐ ┌─────┘
         │ │
        ┌───┐
        │ D │
        └───┘
```

마름모다. 그래서 **다이아몬드 문제**(diamond problem)라고 부른다. 문제는 이것이다. `D` 에서 `who` 를 찾을 때 **`A` 를 언제 방문하는가?**

두 가지 후보가 있다.

- **깊이 우선**: `D → B → A → C`. `B` 를 끝까지 파고든 뒤 `C` 로 간다. → 답은 `"A"`.
- **너비 우선**: `D → B → C → A`. 직접 부모를 모두 본 뒤 조상으로 올라간다. → 답은 `"C"`.

파이썬은 후자에 가깝다. 하지만 "너비 우선"이라고 외우면 틀린다.

::: hist 파이썬은 이 답을 두 번 바꿨다
2.2 이전의 고전 클래스(classic class)는 **순수 깊이 우선**이라 위 코드가 `"A"` 를 반환했다. `C` 는 `A.who` 를 고치려고 오버라이드했는데 `D` 에서는 그 오버라이드가 무시되고 원본이 불린 것이다 — 자식이 부모에게 진 셈이라 상속의 의미를 배반한다. 2.2에서 새 스타일 클래스로 고쳤지만 결함이 남아, **2.3에서 C3 선형화**(Dylan 언어에서 가져온 알고리즘)로 갈아엎었다. 3.x는 그대로 쓴다.
:::

## MRO — 상속 그래프를 한 줄로 편다

파이썬은 다이아몬드 그래프를 매번 탐색하지 않는다. **클래스를 만드는 순간, 그래프를 평평한 리스트 하나로 미리 펴 둔다.** 이 리스트가 **MRO**(Method Resolution Order)다.

```pyrepl
>>> D.__mro__
(<class '__main__.D'>, <class '__main__.B'>, <class '__main__.C'>, <class '__main__.A'>, <class 'object'>)
>>> [c.__name__ for c in D.__mro__]
['D', 'B', 'C', 'A', 'object']
```

여기 답이 있다. `D` 의 MRO에서 `C` 는 `A` 보다 **앞**이다. 속성 탐색은 이 리스트를 **왼쪽부터 순서대로** 훑어 **처음 발견한 것**을 쓴다. `who` 를 찾으면 `D`(없음) → `B`(없음) → `C`(있음!) 에서 멈춰 `"C"` 다.

**이게 전부다.** 상속에서 벌어지는 모든 일은 "MRO 리스트를 왼쪽부터 훑는다"로 설명된다. 그래프도 부모도 재귀도 없다. **리스트 하나와 순차 탐색**뿐이다.

## C3 선형화 — MRO는 어떻게 계산되는가

MRO는 아무렇게나 정해지지 않는다. **C3 선형화**라는 알고리즘이 만든다. 규칙은 셋이다.

1. **자기 자신이 맨 앞이다.** 자식은 항상 부모보다 앞선다(지역 우선 순위).
2. **선언 순서를 지킨다.** `class D(B, C)` 라면 MRO에서 `B` 가 `C` 보다 앞이다.
3. **단조성**(monotonicity). `B` 의 MRO에서 `X` 가 `Y` 보다 앞이었다면, `B` 를 상속한 모든 클래스의 MRO에서도 그 순서가 유지된다.

세 규칙을 **동시에** 만족하는 순서를 찾는 게 C3다. 정의는 재귀적이다.

$$L[C] = C + \operatorname{merge}(L[B_1],\; \dots,\; L[B_n],\; [B_1, \dots, B_n])$$

$L[C]$ 는 `C` 의 MRO다. 자기 자신을 맨 앞에 놓고 **모든 부모의 MRO**와 **부모 목록 자체**를 `merge` 한다 — 마지막 `[B1, ..., Bn]` 이 규칙 2를 강제하는 장치다.

### merge — 진짜 알고리즘

`merge` 는 이렇게 동작한다. 리스트 여러 개를 받아 하나로 합친다.

```text nolines
1. 각 리스트의 head (첫 원소) 를 왼쪽 리스트부터 차례로 본다.
2. 그 head 가 다른 어떤 리스트의 tail (첫 원소를 뺀 나머지) 에도
   나타나지 않으면 -> 채택. 결과에 붙이고 모든 리스트에서 제거한다.
3. tail 에 나타나면 -> 기각. 다음 리스트의 head 로 넘어간다.
4. 모든 리스트가 빌 때까지 반복. 채택할 head 가 하나도 없으면 -> 에러.
```

2번이 핵심이다. **어떤 리스트의 tail에 있다는 것은, 그 앞에 먼저 나와야 할 클래스가 아직 남았다는 뜻**이다. 지금 채택하면 순서가 깨진다. 직접 구현해서 CPython과 대조해 보자.

```python title="c3.py — 20줄짜리 C3"
def merge(seqs):
    result = []
    seqs = [list(s) for s in seqs]
    while True:
        seqs = [s for s in seqs if s]          # 빈 리스트 제거
        if not seqs:
            return result
        for seq in seqs:                        # 왼쪽 리스트부터
            head = seq[0]
            if not any(head in s[1:] for s in seqs):   # 어떤 tail 에도 없다
                break                                   # -> 채택
        else:
            raise TypeError("Cannot create a consistent MRO")
        result.append(head)
        for s in seqs:
            if s[0] == head:
                del s[0]


def c3(cls):
    if cls is object:
        return [object]
    return merge([[cls]] + [c3(b) for b in cls.__bases__] + [list(cls.__bases__)])
```

```pyrepl
>>> [c.__name__ for c in c3(D)]
['D', 'B', 'C', 'A', 'object']
>>> c3(D) == list(D.__mro__)
True
```

::: deep 손으로 따라가 보기 — D(B, C)
```text nolines
L[A] = [A, object]
L[B] = [B, A, object]
L[C] = [C, A, object]

L[D] = D + merge( [B, A, object],
                  [C, A, object],
                  [B, C] )

step 1: head = B.  다른 리스트의 tail 에 B 가 있나?
        [C, A, object] 의 tail -> 없음.  [B, C] 의 tail 은 [C] -> 없음.
        -> B 채택.
        남은 것: merge([A, object], [C, A, object], [C])

step 2: head = A.  [C, A, object] 의 tail 은 [A, object] -> A 가 있다!
        -> A 기각.  다음 리스트로.
        head = C.  [A, object] 의 tail -> 없음.  [C] 의 tail 은 [] -> 없음.
        -> C 채택.
        남은 것: merge([A, object], [A, object])

step 3: head = A.  tail 에 없음 -> 채택.
step 4: object 채택.

L[D] = [D, B, C, A, object]
```

step 2가 이 절 첫 문제의 답이다. **`A` 를 채택하려 했지만 기각당했다** — `C` 가 아직 `A` 앞에 나올 권리(자식이 부모보다 먼저)를 갖고 있었기 때문이다. 그래서 `A.who` 가 아니라 `C.who` 가 이긴다. **다이아몬드의 공통 조상은 항상 맨 뒤로 밀린다.**
:::

### C3가 실패할 때

세 규칙을 동시에 만족하는 순서가 **존재하지 않을 수 있다.** 그때 파이썬은 클래스 생성 자체를 거부한다.

```pyrepl
>>> class X: pass
>>> class Y: pass
>>> class K1(X, Y): pass
>>> class K2(Y, X): pass
>>> class Z(K1, K2): pass
Traceback (most recent call last):
  ...
TypeError: Cannot create a consistent method resolution order (MRO) for bases X, Y
```

`K1` 은 "`X` 가 `Y` 보다 앞"이라 하고, `K2` 는 "`Y` 가 `X` 보다 앞"이라 한다. 단조성을 지키려면 둘 다 만족해야 하는데 모순이다.

::: warn 이 에러는 실행 중이 아니라 import 중에 터진다
`TypeError: Cannot create a consistent MRO` 는 `class` 문이 실행되는, 즉 **모듈을 import하는 순간** 발생한다. 테스트를 돌려 보기도 전에 알 수 있다는 뜻이라 오히려 다행이다. 흔한 원인은 **부모를 자식보다 왼쪽에 쓰는 것**이다. `class Weird(Animal, Dog)` 처럼 조상을 자손보다 앞에 나열하면 규칙 1(자식 우선)과 규칙 2(선언 순서)가 정면으로 충돌한다. 대개 베이스 순서를 뒤집으면(`class Weird(Dog, Animal)`) 해결된다 — 어차피 `Animal` 은 `Dog` 를 통해 이미 상속되므로 명시적으로 적을 이유도 없다.
:::

## `super()` 는 부모를 부르지 않는다

이제 이 절에서 가장 중요한 문장이다.

> **`super()` 는 "부모 클래스"가 아니라 "MRO상 나의 다음"을 가리킨다.**

대부분의 튜토리얼이 `super()` 를 "부모 클래스를 호출하는 방법"이라고 가르친다. 단일 상속에서는 그 설명이 우연히 맞는다. 다중 상속에서는 **틀린다.**

증거를 보자.

```python title="super_is_not_parent.py"
class Base:
    def go(self): print("Base.go")

class L(Base):
    def go(self):
        print("L.go -> super")
        super().go()

class R(Base):
    def go(self):
        print("R.go")

class Both(L, R):
    pass

Both().go()
```

`L` 의 부모는 누가 봐도 `Base` 다. `L.__bases__` 가 그렇게 말한다.

```pyrepl
>>> L.__bases__
(<class '__main__.Base'>,)
```

그러니 `L.go` 안의 `super().go()` 는 `Base.go` 를 부를 것 같다. 실행하면:

```text nolines
L.go -> super
R.go
```

**`R.go` 가 불렸다.** `Base.go` 는 아예 실행되지 않았다. `R` 은 `L` 의 형제이지 부모가 아니다. `L` 을 정의할 때 `R` 은 존재하지도 않았을 수 있다. 이유는 MRO다.

```pyrepl
>>> [c.__name__ for c in Both.__mro__]
['Both', 'L', 'R', 'Base', 'object']
```

`super()` 는 이렇게 동작한다. **"인스턴스의 MRO에서 지금 이 메서드가 정의된 클래스를 찾고, 그 바로 다음 칸부터 탐색한다."**

```text nolines
Both.__mro__ :  [ Both,  L,  R,  Base,  object ]
                         ^
                         │  현재 실행 중인 L.go
                         │
                         └──▶ super() 는 여기 다음부터 찾는다
                                  │
                                  ▼
                              [ R, Base, object ]  <- R.go 발견. 끝.
```

**결정적인 점: 그 MRO는 `L` 의 MRO가 아니라 `type(self)` 의 MRO다.** `L` 은 자기가 어떤 클래스에 섞일지 모른 채 작성됐다. 그런데 런타임에 `self` 가 `Both` 의 인스턴스라서, `L` 의 `super()` 가 `R` 로 간다.

::: danger super() 를 "부모 호출"로 이해하면 반드시 사고가 난다
당신이 `L.go` 를 작성하며 "super()로 `Base.go` 를 부르니까 안전해"라고 생각한다. 6개월 뒤 다른 사람이 `class Both(L, R)` 를 만든다. **당신 코드는 한 글자도 안 바뀌었는데 동작이 바뀐다.** 다중 상속을 쓰는 코드에서 `super()` 의 계약은 "나는 내 다음이 누구인지 모른다, 그저 다음에게 넘긴다"는 것뿐이다. 이 계약을 받아들일 준비가 안 됐다면 다중 상속을 쓰지 마라.
:::

진짜 부모를 부르고 싶으면 `Base.go(self)` 라고 클래스를 명시한다. 이건 MRO를 무시하고 정확히 그 클래스의 메서드를 부른다. 단, 다중 상속에서 이걸 쓰면 **협력 체인이 끊긴다.** 뒤에서 볼 이중 호출 버그의 원인이 바로 이거다. 단일 상속이 확실한 곳에서만 써라.

## `super()` 의 정체

`super()` 는 함수가 아니다. **클래스**다. `super()` 를 호출하면 인스턴스가 만들어진다.

```pyrepl
>>> class P:
...     def m(self): return "P.m"
...
>>> class Q(P):
...     def m(self):
...         s = super()
...         print(type(s), s)
...         return s.m()
...
>>> Q().m()
<class 'super'> <super: <class 'Q'>, <Q object>>
'P.m'
```

`super` 객체는 **프록시**다. `__thisclass__`(지금 어느 클래스의 메서드 안에 있는가 — MRO 시작점)와 `__self_class__`(실제 인스턴스의 타입 — 어느 MRO를 쓸지)를 들고 있다.

```pyrepl
>>> b = Both()
>>> s = super(L, b)
>>> s.__thisclass__
<class '__main__.L'>
>>> s.__self_class__
<class '__main__.Both'>
```

`super(L, b)` 는 "`Both` 의 MRO에서 `L` 다음부터 찾아라"라는 뜻이다. `super` 객체의 속성 접근은 **디스크립터 프로토콜을 정상적으로 탄다** — `s.m` 은 이미 `self` 가 묶인 바운드 메서드다. 이 원리는 [3.3 디스크립터](#/descriptors)에서 파헤친다.

### 인자 없는 `super()` 는 컴파일러의 마법이다

파이썬 3의 `super()` 는 인자가 없다. 그런데 방금 봤듯 `super` 는 두 인자가 있어야 동작한다. `self` 는 쉽다 — 첫 지역 변수다. 문제는 `__thisclass__` 다. 메서드 안에서 "내가 정의된 클래스"를 알아낼 방법이 원래 없다 — `type(self)` 는 `Both` 지 `L` 이 아니다.

그래서 CPython은 **메서드 본문에 `super` 나 `__class__` 라는 이름이 나타나면, 컴파일러가 그 메서드에 `__class__` 라는 클로저 셀을 몰래 추가한다.**

```pyrepl
>>> class A:
...     def m(self):
...         super()
...         return __class__
...     def n(self):
...         return 1
...
>>> A.m.__code__.co_freevars
('__class__',)
>>> A.n.__code__.co_freevars
()
>>> A().m()
<class '__main__.A'>
```

`m` 에는 자유 변수 `__class__` 가 생겼고 `n` 에는 없다. `super` 를 언급했다는 이유만으로 함수의 **바이트코드 구조가 달라진 것이다.** 클래스 본문 실행이 끝나면 `type.__new__` 가 이 셀에 완성된 클래스 객체를 채워 넣는다([1.10 함수](#/functions)의 클로저와 같은 메커니즘). 대가도 있다. **클래스 본문 밖에서 정의한 함수에서는 인자 없는 `super()` 가 죽는다.**

```pyrepl
>>> def outside(self):
...     return super().m()
...
>>> A.outside = outside          # 나중에 클래스에 붙였다
>>> A().outside()
Traceback (most recent call last):
  ...
RuntimeError: super(): __class__ cell not found
```

컴파일 시점에 `class A:` 블록 안이 아니었으니 셀이 만들어지지 않았다. 이럴 때는 `super(A, self)` 라고 명시적으로 써야 한다.

## 협력적 다중 상속

`super()` 가 "MRO상 다음"이라는 사실을 받아들이면, 다중 상속을 안전하게 쓰는 유일한 방법이 나온다. **모든 클래스가 `super()` 로 다음에게 넘긴다.** 이것을 **협력적 다중 상속**(cooperative multiple inheritance)이라 한다.

먼저 협력하지 **않는** 코드가 어떻게 망가지는지 보자. 흔한 착각은 "부모를 하나씩 명시적으로 부르면 되지"다.

```python title="broken.py — 명시 호출의 함정"
class A2:
    def __init__(self):
        print("A2.__init__")
        super().__init__()

class B2:
    def __init__(self):
        print("B2.__init__")
        super().__init__()

class C2(A2, B2):
    def __init__(self):
        A2.__init__(self)     # 부모를 하나씩 부른다
        B2.__init__(self)
```

```pyrepl
>>> [c.__name__ for c in C2.__mro__]
['C2', 'A2', 'B2', 'object']
>>> c = C2()
A2.__init__
B2.__init__
B2.__init__
```

**`B2.__init__` 이 두 번 불렸다.** `A2.__init__(self)` 안의 `super().__init__()` 이 `type(self)` = `C2` 의 MRO를 따라 이미 `B2` 를 불렀는데, `C2` 가 또 불렀다. `__init__` 이 카운터를 올리거나 리스트에 항목을 넣는다면 값이 조용히 두 배가 된다. **이게 다중 상속에서 가장 자주 나는 버그다.** 올바른 방식은 전부 `super()` 를 쓰고, **인자를 `**kwargs` 로 흘려보내는 것**이다.

```python title="cooperative.py"
class Base:
    def __init__(self, **kw):
        if kw:
            raise TypeError(f"알 수 없는 인자: {sorted(kw)}")
        super().__init__()          # object.__init__() 은 인자 없이

class A(Base):
    def __init__(self, a=None, **kw):
        self.a = a
        super().__init__(**kw)      # 내 것만 빼고 나머지는 다음에게

class B(Base):
    def __init__(self, b=None, **kw):
        self.b = b
        super().__init__(**kw)

class C(A, B):
    pass
```

```pyrepl
>>> c = C(a=1, b=2)
>>> c.a, c.b
(1, 2)
>>> C(a=1, typo=9)
Traceback (most recent call last):
  ...
TypeError: 알 수 없는 인자: ['typo']
```

각 클래스는 **자기가 아는 키워드만 꺼내 쓰고 나머지를 다음에게 넘긴다.** `A` 는 `B` 의 존재를 모른다. 그래도 `b=2` 가 `B` 에게 도착한다. MRO가 배달해 준다.

협력적 다중 상속의 계약은 넷이다. **모든 클래스가 `super().__init__()` 을 부른다**(하나라도 빠지면 체인이 끊긴다). **키워드 인자만 쓴다**(위치 인자는 MRO 순서에 따라 의미가 달라져 협력이 불가능하다). **모르는 인자는 그대로 넘긴다**(`**kw` 를 삼키지 마라). 그리고 **체인의 끝을 직접 만든다** — 다음 항목을 보라.

::: danger object.__init__() 은 kwargs 를 받지 않는다
체인의 마지막은 항상 `object` 다. 그런데 `object.__init__` 은 인자를 거부한다.

```pyrepl
>>> class Root:
...     def __init__(self, **kw):
...         super().__init__(**kw)      # object 에게 kw 를 넘긴다
...
>>> class A(Root):
...     def __init__(self, a=None, **kw):
...         super().__init__(**kw)
...
>>> A(a=1, typo=2)
Traceback (most recent call last):
  ...
TypeError: object.__init__() takes exactly one argument (the instance to initialize)
```

에러 메시지가 최악이다. **진짜 문제는 `typo=2` 라는 오타인데, `object.__init__` 을 탓한다.** 원인이 어디인지 전혀 알려주지 않는다.

그래서 협력 체인의 **바닥에 자기 클래스를 하나 두고**, 거기서 남은 kwargs를 직접 검사해 사람이 읽을 수 있는 에러를 내야 한다. 위 `cooperative.py` 의 `Base` 가 그 역할이다. 이건 선택이 아니라 필수다.
:::

## 믹스인

믹스인(mixin)은 **단독으로 인스턴스화할 수 없고, 다른 클래스에 기능을 얹기 위해서만 존재하는 클래스**다. 문법이 따로 있는 게 아니라 **관례**다.

```python title="mixin.py"
class Doc:
    def render(self):
        return "hello"

class Tagged:                       # 믹스인
    def render(self):
        return "tag:" + super().render()

class Loud:                         # 믹스인
    def render(self):
        return super().render().upper()

class M1(Tagged, Loud, Doc): pass
class M2(Loud, Tagged, Doc): pass
```

```pyrepl
>>> M1().render()
'tag:HELLO'
>>> M2().render()
'TAG:HELLO'
```

**순서가 결과를 바꾼다.** `M1` 은 `Tagged` 가 먼저라 `"tag:"` 를 나중에 붙이고(대문자화 이후), `M2` 는 `Loud` 가 먼저라 태그까지 대문자가 됐다.

MRO를 보면 자명하다.

```pyrepl
>>> [c.__name__ for c in M1.__mro__]
['M1', 'Tagged', 'Loud', 'Doc', 'object']
>>> [c.__name__ for c in M2.__mro__]
['M2', 'Loud', 'Tagged', 'Doc', 'object']
```

믹스인은 **파이프라인의 한 단**이다. 각 단이 `super()` 로 다음 단을 부르고, 결과를 가공한다. 데코레이터([1.11](#/decorators))와 구조가 같다 — 다만 조립 지점이 함수가 아니라 클래스 정의라는 것뿐이다.

```text nolines
M1().render()
    │
    ├─ Tagged.render     "tag:" + ...          <- 4. 태그를 붙여 반환
    │      │
    │      └─ super() ──▶ Loud.render          <- 3. 대문자로 만들어 반환
    │                        │
    │                        └─ super() ──▶ Doc.render
    │                                          <- 1. "hello" 를 만든다
    ▼
'tag:HELLO'
```

### 믹스인 작성 규칙

1. **믹스인은 MRO 왼쪽에 둔다.** `class M(Mixin1, Mixin2, Base)`. 오른쪽에 두면 실체 클래스가 먼저 응답해 믹스인이 무시된다.
2. **믹스인은 `__init__` 을 최소화한다.** 꼭 필요하면 협력 규약(`**kwargs` + `super()`)을 지킨다.
3. **믹스인은 상태를 거의 갖지 않는다.** 상태를 가지면 이름 충돌이 나고, 충돌은 조용히 서로를 덮어쓴다.
4. **믹스인은 자기가 무엇에 섞일지 문서화한다.** 믹스인은 혼자서는 못 돈다.

```pyrepl
>>> Tagged().render()
Traceback (most recent call last):
  ...
AttributeError: 'super' object has no attribute 'render'
```

`Tagged` 는 `render` 를 제공하는 무언가와 섞여야만 동작한다. 이 의존은 **코드 어디에도 안 적혀 있다.** 그래서 문서화가 규칙에 들어간다. 정적으로 이 의존을 표현하고 싶다면 [2.4 Protocol](#/protocol-typing)을 본다.

::: tip 이름 충돌은 믹스인의 진짜 위험이다
믹스인 두 개가 둘 다 `self.cache` 를 쓰면 예외도 경고도 없이 서로의 데이터를 덮어쓴다. 방어책은 **이름 맹글링**이다. 믹스인 안에서 `self.__cache`(밑줄 두 개)로 쓰면 `self._Tagged__cache` 로 변환돼 충돌하지 않는다. 맹글링이 존재하는 이유가 정확히 이것이다 — 프라이버시가 아니라 **다중 상속에서의 이름 충돌 방지**다. ([1.12 클래스](#/classes))
:::

## 상속은 캡슐화를 깬다

여기서 방향을 튼다. 지금까지 상속을 **어떻게** 하는지 봤다. 이제 **해야 하는가**를 묻는다.

상속의 근본 문제는 **자식이 부모의 구현 세부사항에 의존한다**는 것이다. 부모가 자기 메서드를 내부에서 어떻게 부르는지까지 알아야 하는데, 그건 공개 계약이 아니다. 파이썬에서 이걸 가장 잔인하게 보여주는 예가 `dict` 서브클래싱이다.

```python title="logging_dict.py — 되는 것 같지만 안 된다"
class LoggingDict(dict):
    def __setitem__(self, k, v):
        print(f"set {k}={v}")
        super().__setitem__(k, v)
```

```pyrepl
>>> d = LoggingDict()
>>> d["a"] = 1
set a=1
>>> d.update(b=2)          # 로그가 안 찍힌다?!
>>> d2 = LoggingDict(c=3)  # 여기도 안 찍힌다
>>> dict(d), dict(d2)
({'a': 1, 'b': 2}, {'c': 3})
```

**`update()` 와 `__init__` 이 `__setitem__` 을 부르지 않는다.** 값은 멀쩡히 들어갔지만 오버라이드만 건너뛰었다. `list.extend`/`__iadd__` 도 같은 이유로 `append` 를 건너뛴다.

::: deep 왜 그런가 — C 레벨 슬롯은 파이썬 레벨을 안 본다
`dict.update` 는 C로 구현돼 있고, 내부에서 `PyDict_SetItem()` 이라는 **C 함수를 직접 호출한다.** 파이썬 레벨의 `type(self).__setitem__` 을 조회하지 않는다 — 매번 조회하면 `dict` 자체가 느려지기 때문이다. CPython의 버그가 아니라 **속도를 위해 의도적으로 만든 지름길**이며, `str`, `list`, `set`, `int` 모두 같다.

해법은 `collections` 의 `UserDict`/`UserList`/`UserString` 이다. 실제 데이터를 `self.data` 라는 평범한 `dict` 에 **컴포지션으로** 들고 있는 얇은 래퍼라서, 모든 경로가 `__setitem__` 을 지난다.

```pyrepl
>>> from collections import UserDict
>>> class LoggingUserDict(UserDict):
...     def __setitem__(self, k, v):
...         print(f"set {k}={v}")
...         super().__setitem__(k, v)
...
>>> u = LoggingUserDict()
>>> u.update(b=2)
set b=2
>>> u2 = LoggingUserDict(c=3)
set c=3
```

동작한다. **표준 라이브러리조차 "내장 타입 상속"을 포기하고 컴포지션으로 갔다는 게 이 이야기의 핵심이다.**

```pyrepl
>>> [c.__name__ for c in UserDict.__mro__]
['UserDict', 'MutableMapping', 'Mapping', 'Collection', 'Sized', 'Iterable', 'Container', 'object']
```

`dict` 가 MRO에 없다. `UserDict` 는 `dict` 가 **아니다.** 매핑 프로토콜을 구현할 뿐이다. ([1.15 프로토콜](#/protocols))
:::

::: warn 내장 타입 상속은 대개 나쁜 선택이다
`dict` 를 상속해서 뭔가 하고 싶다면 멈춰라. 선택지는 이렇다.

- 기본값이 필요하다 → `collections.defaultdict`
- 개수를 센다 → `collections.Counter`
- 여러 dict를 겹친다 → `collections.ChainMap`
- 동작을 바꾼다 → `collections.UserDict` 또는 `collections.abc.MutableMapping` 구현
- 필드가 정해져 있다 → `@dataclass` ([2.6](#/dataclasses))

`dict` 직접 상속은 **성능이 정말 중요하고 오버라이드는 안 할 때**만 의미가 있다.
:::

## 컴포지션

**컴포지션**(composition)은 상속 대신 **다른 객체를 속성으로 갖고 필요한 것만 위임**하는 것이다.

```python title="inherit vs compose"
class Engine:
    def start(self): return "vroom"


# 상속: Car 는 Engine 이다 (?)
class CarInherit(Engine):
    pass

# 컴포지션: Car 는 Engine 을 갖는다
class CarCompose:
    def __init__(self):
        self._engine = Engine()

    def start(self):
        return self._engine.start()
```

상속판은 `Engine` 의 **모든** 공개 메서드를 `Car` 의 API에 노출한다. `Engine` 에 나중에 `explode()` 가 추가되면 `Car` 도 폭발할 수 있게 된다 — 당신은 아무것도 안 했는데. 컴포지션판은 `start()` 만 노출한다. **명시적으로 허락한 것만 나간다.**

### 무엇을 언제 쓰는가

| 상속을 써도 되는 조건 | 확인 방법 |
| --- | --- |
| **is-a 가 진짜 성립한다** | 자식 인스턴스를 부모 자리에 넣어도 프로그램이 옳게 동작하는가 (리스코프 치환) |
| **부모의 모든 공개 API가 자식에게도 말이 된다** | 자식에서 "이 메서드는 지원 안 함"으로 막아야 하는 게 있는가 → 있으면 실패 |
| **부모가 상속을 위해 설계됐다** | 확장 지점이 문서화돼 있는가, 아니면 그냥 상속 가능한가 |
| **관계가 영원하다** | 런타임에 부모를 바꾸고 싶어질 일이 없는가 |

하나라도 걸리면 컴포지션이다.

::: tip 정사각형은 직사각형이 아니다
`class Square(Rectangle)` 는 고전적인 함정이다. `width`/`height` 를 따로 설정하는 API가 있다면 `sq.width = 10` 은 `height` 도 같이 바꿔야 하는데, 그러면 `Rectangle` 을 기대한 코드가 깨진다. **is-a 는 "수학적으로 참인 문장"이 아니라 "계약을 지킬 수 있는가"로 판단한다.**
:::

::: perf 위임에는 값이 있다
컴포지션은 호출을 한 단 더 거친다.

```python title="delegation_cost.py"
import timeit

class Engine:
    def start(self): return "vroom"

class CarInherit(Engine):
    pass

class CarCompose:
    def __init__(self): self._engine = Engine()
    def start(self): return self._engine.start()

class CarProxy:
    def __init__(self): self._engine = Engine()
    def __getattr__(self, name):
        return getattr(self._engine, name)

def best(fn):
    return min(timeit.repeat(fn, number=500_000, repeat=9))

ci, cc, cp = CarInherit(), CarCompose(), CarProxy()
print("inherit          : %.4f" % best(lambda: ci.start()))
print("explicit forward : %.4f" % best(lambda: cc.start()))
print("__getattr__ proxy: %.4f" % best(lambda: cp.start()))
```

```text nolines
inherit          : 0.0129
explicit forward : 0.0203      -> 1.57x
__getattr__ proxy: 0.0446      -> 3.46x
```

(Python 3.14.5 / Windows, 50만 회 best-of-9 실측.)

명시적 위임은 **약 1.6배**, `__getattr__` 프록시는 **약 3.5배** 느리다 — `__getattr__` 은 **정상 탐색이 실패한 뒤에야 불리는 폴백**이라 `AttributeError` 경로를 한 번 타고 다시 조회하기 때문이다. ([3.5 동적 속성](#/dynamic-attrs)) 50만 번에 0.03초 차이라 **대부분은 신경 쓸 필요 없다.** 초당 수십만 번 도는 루프에서만 명시적 위임을 쓰고 프록시는 피하라.
:::

## `isinstance` vs `type`

마지막 질문. 타입을 검사할 때 무엇을 쓰는가.

```python
if type(x) is Sub:          # 정확히 Sub 인가
if isinstance(x, Sub):      # Sub 이거나 Sub 의 자식인가
```

**둘은 다른 질문이다.** `isinstance` 는 MRO를 본다. `type(x) is C` 는 안 본다.

```pyrepl
>>> class Base: pass
>>> class Sub(Base): pass
>>> s = Sub()
>>> isinstance(s, Base)
True
>>> type(s) is Base
False
```

**기본은 `isinstance` 다.** 리스코프 치환 때문이다. `Sub` 은 `Base` 로서 동작할 수 있어야 하는데 `type(x) is Base` 는 그 대체를 거부한다 — 상속을 만들어 놓고 부정하는 코드다. 가장 유명한 사례가 `bool` 이다.

```pyrepl
>>> bool.__mro__
(<class 'bool'>, <class 'int'>, <class 'object'>)
>>> isinstance(True, int)
True
>>> type(True) is int
False
>>> True + True
2
```

`bool` 은 `int` 의 서브클래스다. `True` 는 진짜로 정수 1이다. `type(x) is int` 로 검사하는 코드는 `True` 를 정수로 인정하지 않는다 — 산술에서는 멀쩡히 정수로 동작하는데도.

::: perf 속도는 이유가 되지 못한다
"`type(x) is C` 가 빠르니까"는 흔한 변명이다. 실제로 측정해서 확인해보자.

```python title="bench.py"
import timeit

class Base: pass
class Sub(Base): pass
s = Sub()

N = 2_000_000
print("isinstance:", min(timeit.repeat(lambda: isinstance(s, Sub), number=N, repeat=9)))
print("type() is :", min(timeit.repeat(lambda: type(s) is Sub, number=N, repeat=9)))
```

같은 스크립트를 8번 반복 실행한 결과다 (Python 3.14.5 / Windows, 200만 회 best-of-9):

```text nolines
isinstance: 0.0406   type() is: 0.0415
isinstance: 0.0403   type() is: 0.0439
isinstance: 0.0401   type() is: 0.0417
isinstance: 0.0403   type() is: 0.0413
isinstance: 0.0408   type() is: 0.0414
isinstance: 0.0402   type() is: 0.0418
isinstance: 0.0409   type() is: 0.0438
isinstance: 0.0414   type() is: 0.0437
```

`isinstance` 가 매번 근소하게 빠르다 — 그런데 **먼저 실행한 쪽이 매번 더 빠르다는 게 함정이다.** 두 줄의 순서를 바꿔서 `type() is` 를 먼저 재는 스크립트로 같은 걸 8번 더 돌리면:

```text nolines
type() is: 0.0411   isinstance: 0.0411
type() is: 0.0407   isinstance: 0.0408
type() is: 0.0413   isinstance: 0.0409
type() is: 0.0417   isinstance: 0.0408
type() is: 0.0406   isinstance: 0.0407
type() is: 0.0406   isinstance: 0.0406
type() is: 0.0409   isinstance: 0.0408
type() is: 0.0452   isinstance: 0.0451
```

이번엔 거의 동률이거나 **먼저 잰 `type() is` 가 오히려 앞선다.** 즉 위 첫 번째 표에서 본 "`isinstance` 가 빠르다"는 결과는 `isinstance` 를 항상 먼저 측정한 스크립트 순서 때문에 생긴 착시였다 — CPU 캐시·분기 예측기가 먼저 도는 코드에 불리하게 워밍업되는 흔한 벤치마크 함정이다. **결론: 이 정도 크기(수백만 회, 수 ms 차이)의 마이크로벤치마크에서는 방향조차 안정적으로 재현되지 않는다.** 두 연산 모두 C 레벨 단일 스텝이라 실질 차이가 없다고 보는 게 맞다. **속도는 어느 쪽으로도 근거가 못 된다.** `type() is` 를 쓰겠다면 정확성 문제 — 서브클래스 배제가 의도인지 — 로만 판단하라.
:::

### `type(x) is C` 가 옳은 때

드물지만 있다. **서브클래스를 명시적으로 배제해야 할 때**다 — 직렬화기가 "정확히 `dict` 면 빠른 경로, 아니면 일반 경로"로 분기하는 식이다.

```pyrepl
>>> from collections import OrderedDict
>>> od = OrderedDict(a=1)
>>> isinstance(od, dict)
True
>>> type(od) is dict          # OrderedDict, Counter 는 여기서 제외된다
False
```

이때는 서브클래스 배제가 **의도**다. 의도가 아니라면 쓰지 마라.

::: deep isinstance 는 거짓말을 할 수 있다
`isinstance` 는 MRO를 직접 보지 않는다. **메타클래스의 `__instancecheck__` 를 부른다.** 그래서 오버라이드할 수 있고, 상속 관계가 전혀 없어도 `True` 를 반환하게 만들 수 있다. 이게 장난이 아니라 표준 기능이라는 증거가 **ABC의 가상 서브클래스**다.

```pyrepl
>>> from abc import ABC
>>> class Drawable(ABC): pass
>>> class Circle: pass
>>> Drawable.register(Circle)
<class '__main__.Circle'>
>>> isinstance(Circle(), Drawable)
True
>>> issubclass(Circle, Drawable)
True
>>> [c.__name__ for c in Circle.__mro__]
['Circle', 'object']
```

`Drawable` 이 `Circle` 의 MRO에 **없는데도** `isinstance` 가 `True` 다 — `register()` 가 ABC의 내부 등록부에 넣었고 `ABCMeta.__instancecheck__` 가 그걸 본다. **결론: `isinstance` 는 "상속했는가"가 아니라 "이 타입으로 취급해도 되는가"를 묻는다.** `type() is` 로는 이런 확장이 원천적으로 불가능하다. [1.15 프로토콜, ABC, 덕 타이핑](#/protocols)에서 이어진다.
:::

::: cote 코딩테스트에서의 상속
코딩테스트에서 다중 상속을 쓸 일은 거의 없다. `bool` 이 `int` 라는 사실만 활용해도 카운팅이 짧아진다.

```python
count = sum(x > 0 for x in arr)        # True 가 1로 더해진다
```

그리고 `class MyStack(list)` 처럼 자료구조를 상속으로 감싸지 마라. 인스턴스 생성과 메서드 조회 비용만 늘린다. 시험장에서는 `list` 나 `deque` 를 직접 쓰는 게 항상 빠르다.
:::

## 요약

> 파이썬의 상속은 **MRO라는 평평한 리스트 하나**로 환원된다. 이 리스트는 클래스 생성 시 **C3 선형화**가 계산하며, 자식 우선·선언 순서 유지·단조성 세 규칙을 동시에 만족한다. 만족할 수 없으면 클래스 생성이 `TypeError` 로 실패한다. `super()` 는 부모가 아니라 **`type(self)` 의 MRO에서 나의 다음**을 가리키므로, 다중 상속에서는 작성 시점에 알 수 없는 형제 클래스로 흐를 수 있다. 이걸 안전하게 쓰려면 **모두가 `super()` 로 협력**해야 한다. 그리고 대부분의 경우, 답은 상속이 아니라 **컴포지션**이다.

- [ ] MRO는 `D.__mro__` 로 **직접 확인한다.** 추측하지 마라.
- [ ] C3의 규칙 셋: 자식 우선, 선언 순서, 단조성. 셋이 모순이면 클래스가 안 만들어진다.
- [ ] `super()` 는 **부모가 아니라 MRO상 다음**이다. 이게 이 절의 한 문장이다.
- [ ] 다중 상속에서 부모를 하나씩 명시 호출하면 **이중 호출 버그**가 난다. 전부 `super()` + `**kwargs`.
- [ ] `dict`/`list` 상속은 `update`/`extend` 가 오버라이드를 무시한다. `UserDict` 나 컴포지션을 써라.
- [ ] 타입 검사는 `isinstance`. `type() is` 는 서브클래스 배제가 **의도일 때만**.

::: quiz 연습문제

1. 다음 클래스들의 MRO를 **손으로 C3를 돌려서** 구한 뒤, `__mro__` 로 확인하라.

   ```python
   class A: pass
   class B(A): pass
   class C(A): pass
   class D(B, C): pass
   class E(C, B): pass
   ```

   그리고 `class F(D, E)` 는 왜 실패하는가?

2. 다음 코드의 출력을 예측하라. `Mid.__bases__` 는 `(Base,)` 인데도 예측이 맞는가?

   ```python
   class Base:
       def f(self): print("Base")
   class Mid(Base):
       def f(self): print("Mid"); super().f()
   class Side(Base):
       def f(self): print("Side")
   class Final(Mid, Side): pass

   Final().f()
   Mid().f()          # 이건?
   ```

   같은 `Mid.f` 가 두 경우에 다르게 동작한다. 무엇이 그 차이를 만드는가?

3. 아래 코드는 `count` 가 3이 되기를 기대했는데 4가 된다. 원인을 설명하고 고쳐라.

   ```python
   class Counter1:
       def __init__(self):
           self.count = getattr(self, "count", 0) + 1
           super().__init__()

   class Counter2:
       def __init__(self):
           self.count = getattr(self, "count", 0) + 1
           super().__init__()

   class Both(Counter1, Counter2):
       def __init__(self):
           Counter1.__init__(self)
           Counter2.__init__(self)
           self.count += 1
   ```

4. 다음 두 함수의 차이를 `bool` 을 인자로 넣어 확인하라. 어느 쪽이 옳은가? 그리고 "옳다"를 판단한 기준은 무엇인가?

   ```python
   def f(x):
       return type(x) is int
   def g(x):
       return isinstance(x, int)
   ```

5. **깊이 생각해 볼 문제.** 다음 믹스인은 왜 위험한가? 두 가지 문제가 있다.

   ```python
   class CacheMixin:
       def __init__(self):
           self.cache = {}
           super().__init__()

       def get(self, k):
           if k not in self.cache:
               self.cache[k] = super().get(k)
           return self.cache[k]
   ```
:::

**다음 절**: [1.14 특수 메서드 총정리](#/dunder) — `super()` 가 MRO를 타는 것처럼, `a + b` 도 `__add__` 를 타고 `__radd__` 로 넘어간다. 파이썬 문법 뒤의 프로토콜을 전부 연다.
