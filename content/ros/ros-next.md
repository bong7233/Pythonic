# 10.16 다음 단계: C++(rclcpp)로

::: lead
지금까지 이 책은 파이썬으로 로봇을 움직였다. 노드를 만들고, 토픽을 주고받고, TF2로 좌표를 변환하고, Nav2로 자율주행까지 붙였다. 그런데 실제 로봇 회사의 채용 공고를 보면 "rclcpp 경험 우대"라는 문구가 훨씬 자주 보인다. 이 절은 그 간극을 메운다. rclpy와 rclcpp가 실제로 어떻게 다른지, 왜 실전 프로젝트는 C++을 주력으로 놓는지, 그리고 이 책에서 배운 것 중 무엇이 언어를 넘어 그대로 남고 무엇을 새로 배워야 하는지를 정리한다. 이 책의 마지막 절이다.
:::

## rclpy로 다 되는데 왜 C++을 묻는가

여기까지 온 당신은 이미 rclpy로 노드([10.3](#/rclpy-node))를 만들고, 토픽·서비스·액션([10.4](#/topics), [10.5](#/services), [10.6](#/actions))을 실행해 봤다. 다 동작한다. 그런데 질문 자체가 잘못됐다. "rclpy로 안 되는 게 있나?"가 아니라 "이 콜백이 **몇 밀리초 안에** 반드시 끝나야 하는가?"가 진짜 질문이다.

바퀴 달린 로봇의 균형 제어 루프, 매니퓰레이터의 관절 서보 루프, 자율주행차의 긴급 제동 판단은 100Hz~1kHz로 돈다. 한 주기가 1~10ms다. 이 구간에서 **가끔 20ms가 걸리는 것**이 평균 5ms보다 더 큰 문제가 된다. 가끔 튀는 지연(latency spike)이 로봇을 넘어뜨리거나 충돌을 만든다. rclpy가 "느려서"가 아니라 **얼마나 걸릴지 보장할 수 없어서** 문제가 되는 구간이다.

## 같은 뿌리, 다른 줄기: rcl 아키텍처

rclpy와 rclcpp는 경쟁 관계가 아니다. 둘 다 **같은 C 코어를 감싸는 언어별 껍질**이다.

```text nolines
        ┌─────────────┐   ┌─────────────┐
        │   rclpy     │   │   rclcpp    │   <- 언어별 클라이언트 라이브러리
        └──────┬──────┘   └──────┬──────┘
               │                 │
               └────────┬────────┘
                        │
                  ┌─────▼─────┐
                  │    rcl    │             <- C로 짠 공통 코어: 노드·토픽·서비스 로직
                  └─────┬─────┘
                        │
                  ┌─────▼─────┐
                  │    rmw    │             <- DDS 미들웨어 추상화 계층
                  └─────┬─────┘
                        │
                   DDS 구현체 (Fast DDS, Cyclone DDS, ...)
```

노드를 만들고, 발행자를 등록하고, QoS를 협상하는 실질적인 로직은 `rcl` 안에 있다. rclpy와 rclcpp는 그 위에 각 언어의 관용구(파이썬 클래스, C++ 템플릿)를 씌운 얇은 바인딩이다. 그래서 두 라이브러리로 만든 노드는 **DDS 수준에서 완전히 같은 프로토콜로 통신한다.** rclpy로 만든 발행자와 rclcpp로 만든 구독자가 아무 문제 없이 대화한다 — 실제로 대규모 로봇 시스템은 두 언어를 섞어 쓴다.

::: note 그럼 차이는 어디서 나는가
`rcl`은 같지만, 그 위에 얹은 **실행 모델(executor)**과 **런타임**이 다르다. 파이썬은 인터프리터 위에서 돌고, GIL이 있고, 참조 카운팅 GC가 있다. C++은 컴파일된 네이티브 코드고, 스마트 포인터로 결정적인 소멸 시점을 갖는다. 차이는 API가 아니라 **그 위에 얹힌 언어 런타임**에서 온다.
:::

## 성능의 실체: 인터프리터 오버헤드는 숫자로 보인다

"파이썬이 느리다"는 말은 너무 막연하다. 실제로 무엇이 느린지 재보자. 파이썬의 모든 연산은 바이트코드 하나하나를 인터프리터가 해석해서 실행한다 ([3.7 바이트코드](#/bytecode)). 그 해석 자체에 고정 비용이 붙는다.

```python title="interpreter_overhead.py"
import timeit


def pure_python_loop(n):
    total = 0.0
    for i in range(n):
        total += i * 0.5 - 0.25
    return total


def noop():
    pass


n = 1_000_000
t_loop = timeit.timeit(lambda: pure_python_loop(n), number=5) / 5
t_call = timeit.timeit(noop, number=1_000_000)

print(f"루프 1회 반복당: {t_loop / n * 1e9:.1f} ns")
print(f"함수 호출 1회당: {t_call / 1_000_000 * 1e9:.1f} ns")
```

```text nolines
루프 1회 반복당: 22.7 ns
함수 호출 1회당: 12.6 ns
```

(Python 3.14.5 / Windows 기준 실측. 절대값은 기기마다 다르지만 자릿수는 어디서나 비슷하다.)

::: perf 이 숫자가 제어 루프에서 뜻하는 것
곱셈 한 번, 뺄셈 한 번짜리 연산 하나에 22.7ns가 든다. 별거 아닌 것 같지만, 실제 제어 콜백은 이런 연산을 수백~수천 번 반복한다. 여기에 파이썬 함수 호출 하나당 12.6ns의 고정 비용이 매번 얹힌다. 콜백 안에서 NumPy 벡터 연산으로 우회하면([9.2 브로드캐스팅](#/broadcasting)) 이 오버헤드를 크게 줄일 수 있지만, **NumPy 호출 자체의 진입 비용**은 여전히 남는다. 컴파일된 C++ 코드는 이런 인터프리터 디스패치 단계가 아예 없다 — 기계어가 CPU에서 곧바로 실행된다. "몇 배 빠르다"는 식의 수치는 벤치마크마다 다르므로 여기서 단정하지 않는다. 다만 **인터프리터 해석 단계 자체가 사라진다는 구조적 차이**는 어떤 벤치마크에서도 변하지 않는다.
:::

## 실시간성: 예측 가능함이 진짜 자산이다

로봇 제어에서 원하는 것은 "빠름"이 아니라 **"매번 비슷하게 걸림"**이다. 이걸 지터(jitter)라고 부른다. rclpy가 실시간 제어에 잘 쓰이지 않는 이유는 두 가지 구조적 원인 때문이다.

**첫째, GC 정지 시간이 예측 불가능하다.** 파이썬은 참조 카운팅으로 대부분의 객체를 즉시 회수하지만, 순환 참조는 세대별 GC가 주기적으로 훑는다 ([5.2 메모리 모델](#/memory)). 이 훑는 시점과 소요 시간은 코드가 만들어내는 객체 그래프에 따라 달라진다. 제어 루프 콜백이 실행되는 정확히 그 순간에 GC가 끼어들면, 그 주기만 유독 길어진다.

**둘째, GIL이 병렬 실행을 막는다.** `MultiThreadedExecutor`로 콜백 그룹을 여러 스레드에 분산해도, CPU 바운드 파이썬 코드는 GIL 때문에 결국 한 번에 하나만 실행된다 ([4.3 GIL](#/gil), [4.2 threading](#/threading)). 3.13+의 free-threaded 빌드가 이 제약을 풀어 주는 실험적 옵션이지만, 2026년 기준으로 ROS 2 생태계 대부분이 표준 GIL 빌드를 전제로 배포된다. C++은 애초에 이런 제약이 없다 — 스레드가 진짜로 동시에 돈다.

::: warn 그렇다고 rclcpp가 저절로 실시간을 보장하진 않는다
표준 `rclcpp::executors::SingleThreadedExecutor` / `MultiThreadedExecutor`도 스케줄링 방식(타이머 우선, 비선점 라운드로빈) 때문에 엄밀한 실시간 마감시한 보장은 어렵다고 알려져 있다. 진짜 하드 리얼타임이 필요하면 `rclcpp`만으로 부족하고, PREEMPT_RT 커널 패치나 전용 실행기 설계까지 내려가야 한다. C++로 옮기는 것은 **실시간성의 필요조건이지 충분조건이 아니다.**
:::

## 개념은 그대로, 이름만 다르다

이게 이 절에서 가장 중요한 사실이다. 당신이 rclpy로 배운 **개념**(노드, 토픽, 서비스, 액션, QoS, TF2, launch)은 rclcpp에서 구조가 거의 그대로다. 바뀌는 건 문법이다.

| 개념 | rclpy (파이썬) | rclcpp (C++) |
| --- | --- | --- |
| 노드 정의 | `class MyNode(Node):` `super().__init__("name")` | `class MyNode : public rclcpp::Node` `Node("name")` |
| 발행자 생성 | `self.create_publisher(String, "topic", 10)` | `this->create_publisher<std_msgs::msg::String>("topic", 10)` |
| 구독자 생성 | `self.create_subscription(String, "topic", cb, 10)` | `this->create_subscription<std_msgs::msg::String>("topic", 10, cb)` |
| 타이머 | `self.create_timer(0.5, cb)` | `this->create_wall_timer(500ms, cb)` |
| 실행 진입점 | `rclpy.init(); rclpy.spin(node); rclpy.shutdown()` | `rclcpp::init(argc, argv); rclcpp::spin(node); rclcpp::shutdown()` |
| 서비스 서버 | `self.create_service(AddTwoInts, "add", cb)` | `this->create_service<AddTwoInts>("add", cb)` |
| 서비스 클라이언트 | `self.create_client(...)` + `call_async` | `this->create_client<...>(...)` + `async_send_request` |
| 액션 서버 | `rclpy.action.ActionServer(node, Fibonacci, "fib", execute_cb)` | `rclcpp_action::create_server<Fibonacci>(node, ...)` |
| 액션 목표 핸들 | `goal_handle.succeed()` | `goal_handle->succeed()` |
| QoS 설정 | `rclpy.qos.QoSProfile(...)` | `rclcpp::QoS(...)` |
| TF2 리스너 | `tf2_ros.TransformListener(buffer, self)` | `tf2_ros::TransformListener(buffer, this)` |
| launch 파일 | 파이썬(또는 XML/YAML)으로 작성 | **동일하다** — 파이썬(또는 XML/YAML)으로 작성, 노드가 rclpy든 rclcpp든 무관 |
| 빌드 시스템 | `ament_python` + `setup.py` | `ament_cmake` + `CMakeLists.txt` |

::: note 두 언어의 예제 코드 대조 출처
위 표의 rclcpp 문법은 ROS 2 Jazzy용 공식 예제 저장소(`ros2/examples`, jazzy 브랜치)의 `rclcpp/topics/minimal_publisher`, `minimal_subscriber` 소스와 액션 서버 예제(`rclcpp/actions/minimal_action_server`)를 직접 대조해서 확인했다. `rclcpp::Node`, `create_publisher`, `create_wall_timer`, `RCLCPP_INFO`, `rclcpp_action::create_server`, `ServerGoalHandle::succeed` 등 클래스·메서드명이 실제 예제와 일치한다.
:::

TF2 프레임 트리 개념 ([10.9](#/tf2)) — 부모-자식 관계, 시간 보간, `lookup_transform`의 좌표 변환 수학 — 은 언어와 무관하다. QoS 정책(신뢰성, 내구성, 이력)의 의미 ([10.8](#/qos))도 그대로다. 액션의 목표-피드백-결과 3단 구조 ([10.6](#/actions))도 그대로다. **당신이 이 책 10부에서 익힌 것의 8할은 개념이었고, 개념은 언어를 넘어 살아남는다.**

launch 파일도 같은 이야기다. 공식 문서(`docs.ros.org`의 "Using XML, YAML, and Python for ROS 2 Launch Files" 가이드, Humble/Iron/Jazzy/Kilted 공통)에 따르면 launch 파일은 파이썬·XML·YAML 셋 중 아무 형식으로나 쓸 수 있고, 어느 형식을 고르든 **노드가 rclpy로 짰든 rclcpp로 짰든 상관없다** — launch는 결국 실행 파일을 OS 프로세스로 띄우고 인자를 넘기는 역할이라 노드의 구현 언어를 몰라도 된다. `ros2/launch`와 `ros2/launch_ros` 자체는 파이썬으로 구현돼 있지만, 이는 launch 시스템의 내부 구현 언어일 뿐 launch 파일 작성자가 파이썬을 강제로 써야 한다는 뜻은 아니다. 이 책은 파이썬 launch 파일만 다뤘지만, C++ 노드를 섞은 워크스페이스에서도 그 파이썬 launch 파일을 그대로 쓸 수 있다.

## 순수 파이썬 로직으로 확인하는 것

TF2의 좌표 변환 수학처럼 rclpy와 무관한 순수 계산 로직은 두 언어 어느 쪽으로 옮겨도 **수학 자체는 바뀌지 않는다.** 쿼터니언 곱셈을 예로 확인해 보자 — 이 계산은 파이썬으로 짜든 C++로 짜든 같은 결과를 내야 한다.

```python title="quaternion_check.py — TF2가 내부에서 하는 계산과 같은 종류"
def quat_mul(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


identity = (1.0, 0.0, 0.0, 0.0)
q = (0.7071067811865476, 0.7071067811865476, 0.0, 0.0)  # x축 90도 회전

result = quat_mul(q, identity)
print(result)
print(all(abs(a - b) < 1e-9 for a, b in zip(result, q)))
```

```text nolines
(0.7071067811865476, 0.7071067811865476, 0.0, 0.0)
True
```

항등 쿼터니언을 곱해도 원래 값이 그대로 나온다 — 항등원 검증이 통과했다. 이런 순수 수학 로직은 언어를 바꿔도 **알고리즘 자체를 새로 배울 필요가 없다.** C++로 옮길 때 그대로 포팅하면 된다. 새로 배워야 하는 것은 이 함수를 감싸는 껍질(문법, 빌드, 메모리)이지 이 함수 자체가 아니다.

## 무엇을 새로 배워야 하는가

개념은 남지만 다음 네 가지는 확실히 새로 배워야 한다.

**문법.** C++은 정적 타입이고 컴파일 단계가 있다. 템플릿(`create_publisher<MsgType>`)이 파이썬의 덕 타이핑을 대신한다.

**빌드 시스템.** `ament_python`의 `setup.py`/`entry_points`는 `ament_cmake`의 `CMakeLists.txt`/`find_package`/`ament_target_dependencies`로 바뀐다 ([10.2 워크스페이스](#/ros-workspace)). colcon 자체는 그대로 쓴다 — 빌드 시스템의 **뒷단**만 바뀐다.

```text nolines
CMakeLists.txt 핵심 골격
  find_package(rclcpp REQUIRED)
  find_package(std_msgs REQUIRED)
  add_executable(talker src/publisher_member_function.cpp)
  ament_target_dependencies(talker rclcpp std_msgs)
  install(TARGETS talker DESTINATION lib/${PROJECT_NAME})
```

**메모리 관리.** 파이썬은 참조 카운팅 + GC가 자동으로 처리한다 ([1.1 객체, 이름, 참조](#/objects-names)). C++은 스마트 포인터(`std::shared_ptr`, `std::unique_ptr`)로 직접 소유권을 표현해야 한다. rclcpp의 노드, 퍼블리셔, 타이머는 전부 `SharedPtr` 타입으로 반환된다 — **참조 카운팅이라는 개념 자체는 1.1절에서 이미 배웠다.** `shared_ptr`은 그 개념을 언어 차원에서 명시적으로 드러낸 것뿐이다. 다른 점은, 파이썬은 순환 참조를 GC가 알아서 청소해 주지만 `shared_ptr` 순환은 `weak_ptr`로 직접 끊어야 한다는 것이다.

**콜백 실행 모델의 디테일.** `rclcpp::spin`은 싱글 스레드가 기본이고, 콜백 그룹과 실행기(executor) 선택이 rclpy보다 더 명시적으로 드러난다. 어떤 콜백이 어떤 스레드에서 도는지 코드만 보고 바로 알 수 있어야 한다는 압박이 rclpy보다 세다.

## 마이그레이션 전략: 전부 바꾸지 마라

실전에서 가장 흔한 실수는 "이제 진짜 로봇이니 전부 C++로 다시 짜자"는 결정이다. 대부분 불필요하다. ROS 2 워크스페이스는 **패키지 단위로 언어를 섞을 수 있게** 설계돼 있다.

```text nolines
my_robot_ws/
└── src/
    ├── my_robot_msgs/         <- 메시지 정의: 언어 무관, 공통 패키지
    ├── perception_py/         <- rclpy: 오프라인 후처리, 느슨한 주기, 빠른 실험
    │   └── setup.py
    ├── mission_py/            <- rclpy: 상태 머신, 사람이 읽을 로직, 자주 바뀜
    │   └── setup.py
    └── control_cpp/           <- rclcpp: 100Hz 제어 루프, 하드 마감시한
        └── CMakeLists.txt
```

권장하는 순서는 이렇다.

1. **먼저 rclpy로 전체 시스템을 프로토타입한다.** 이 책 10부에서 배운 전부가 여기서 쓰인다.
2. **프로파일링으로 실제 병목을 찾는다** ([5.1 측정 없이 최적화 없다](#/profiling), [10.15 rosbag/디버깅/성능](#/ros-debug)). "느릴 것 같다"가 아니라 **측정된 지연**이 기준이다.
3. **레이턴시가 실제로 문제인 노드만** rclcpp로 다시 짠다. 보통 저수준 제어 루프, 센서 드라이버, 고빈도 필터가 대상이다.
4. 나머지(상태 머신, 미션 로직, 오프라인 분석, 시각화)는 rclpy로 남긴다. 사람이 자주 고치는 코드는 컴파일 시간이 없는 파이썬이 개발 속도에서 이긴다.

::: tip C++ 대신 먼저 시도할 것들
C++로 옮기기 전에 확인할 것: (1) 콜백이 NumPy 벡터화로 대체 가능한가 ([9.2 브로드캐스팅](#/broadcasting)), (2) `cProfile`로 봤을 때 병목이 정말 파이썬 오버헤드인지 아니면 I/O나 알고리즘 자체의 문제인지 ([5.1 profiling](#/profiling)), (3) Cython/Numba로 그 함수만 컴파일할 수 있는지 ([5.5 컴파일러](#/compilers)). rclcpp 전체 재작성보다 훨씬 싸게 먹힐 때가 많다.
:::

## 실전 감각: 무엇이 자주 틀리고 왜 디버깅이 어려운가

rclpy에서 rclcpp로 넘어간 사람들이 겪는 흔한 함정을 미리 알아 두면 시간을 아낀다.

- **`ament_target_dependencies`를 빠뜨린다.** 컴파일은 되는데 링크 단계에서 심볼을 못 찾는 에러가 난다. 파이썬은 `import`만 하면 됐지만 C++은 빌드 시스템에 의존성을 명시적으로 등록해야 한다.
- **콜백 안에서 `shared_ptr`을 캡처하다 순환을 만든다.** 노드가 자기 자신을 가리키는 콜백을 람다로 캡처하면 참조 순환이 생겨 노드가 절대 소멸하지 않는다. `weak_ptr`로 캡처해야 한다 — 파이썬에서는 GC가 이런 순환을 알아서 치웠지만([1.1 객체, 이름, 참조](#/objects-names)의 순환 참조 GC), C++ `shared_ptr`에는 그런 안전망이 없다.
- **콜백 그룹을 안 나눠서 서비스 호출이 데드락난다.** 노드 자신의 콜백 안에서 자기 서비스 클라이언트를 동기 호출하면 같은 실행기가 자기 자신의 응답 콜백을 기다리며 멈춘다. rclpy에서도 나는 문제지만, 멀티스레드 실행기와 콜백 그룹 조합이 C++ 쪽에서 더 자주 명시적으로 요구된다.
- **디버깅 난이도 자체가 오른다.** 파이썬은 스택 트레이스에 파이썬 코드가 그대로 찍힌다. C++은 세그폴트가 나면 코어 덤프와 `gdb`가 필요하고, 템플릿 에러 메시지는 몇 줄이 아니라 몇 백 줄이 나올 때도 있다. 이건 능력 부족이 아니라 **언어가 원래 그렇다.**

## 이 책을 다 읽은 사람에게

이 책은 언어 코어([Part I](#/objects-names))에서 시작해서 타입([Part II](#/why-typing)), 메타프로그래밍([Part III](#/functools)), 동시성([Part IV](#/concurrency-map)), 성능([Part V](#/profiling)), 품질([Part VI](#/pytest)), 알고리즘([Part VII](#/complexity)), 코딩테스트([Part VIII](#/cote-strategy)), 수치 계산([Part IX](#/numpy-basics)), 그리고 ROS 2까지 왔다. 다음 단계로 실전에서 도움이 되는 순서를 제안한다.

1. **작은 실물 로봇이나 시뮬레이션(Gazebo, [10.11](#/gazebo))으로 이 책의 코드를 직접 돌려 봐라.** 문서로 읽은 QoS 불일치, TF 타이밍 문제는 직접 겪어야 몸에 붙는다.
2. **하나의 노드만 골라서 rclcpp로 다시 짜 봐라.** 전체 시스템이 아니라 퍼블리셔 하나로 충분하다. 표에 있는 대응이 실제로 손에 익는 게 목적이다.
3. **C++ 기초가 약하다면 이 책의 1부(객체와 이름, 함수, 클래스)를 다시 펼쳐 놓고 대응 개념을 찾아가며 C++을 배워라.** 참조 카운팅을 이미 아는 사람에게 `shared_ptr`은 새 개념이 아니라 **이미 아는 개념의 다른 표기법**이다.
4. **ROS 2 공식 문서(docs.ros.org)의 배포판을 항상 확인해라.** API는 배포판마다 조금씩 바뀐다. 이 절의 예시는 Jazzy 기준이다.

## 요약

- rclpy와 rclcpp는 같은 `rcl` 코어를 감싼 두 언어 바인딩이다. DDS 수준에서 완전히 호환된다.
- 실전에서 C++을 쓰는 이유는 "빠름"보다 **예측 가능함(낮은 지터)**이다. GC 정지 시간과 GIL이 rclpy의 실시간성을 어렵게 만든다.
- 노드/토픽/서비스/액션/QoS/TF2/launch의 **개념**은 그대로 대응한다. 바뀌는 건 문법·빌드·메모리 관리다.
- `shared_ptr`은 새 개념이 아니라 1.1절에서 배운 참조 카운팅을 언어가 명시적으로 드러낸 것이다.
- 전체를 C++로 다시 짜지 마라. 프로파일링으로 확인된 병목 노드만 옮기고 나머지는 rclpy에 둬라.
- ROS 2 워크스페이스는 패키지 단위로 파이썬과 C++을 섞어 쓸 수 있게 설계됐다.

::: quiz 연습문제
1. rclpy로 만든 발행자 노드와 rclcpp로 만든 구독자 노드가 같은 워크스페이스에서 통신할 수 있는 이유를 아키텍처 그림을 근거로 설명하라.
2. 제어 루프 콜백에서 "가끔 20ms가 걸리는 것"이 "항상 평균 5ms인 것"보다 왜 더 위험한지, 실제 로봇 동작(균형 제어, 관절 서보)을 예로 들어 설명하라.
3. `shared_ptr` 순환 참조가 파이썬의 순환 참조와 다른 점은 무엇인가? 1.1절의 참조 카운팅 GC 내용을 근거로 답하라.
4. 다음 상황에서 rclpy로 남길지 rclcpp로 옮길지 판단하고 이유를 써라: (a) 라이다 포인트클라우드를 20Hz로 필터링하는 노드, (b) 미션 상태를 관리하는 상태 머신 노드, (c) 매니퓰레이터 관절을 1kHz로 서보 제어하는 노드.
5. 이 책 5부(성능)에서 배운 프로파일링 도구 중, C++로 옮기기 전에 "정말 파이썬 오버헤드가 병목인지" 확인하는 데 가장 먼저 써야 할 도구는 무엇이고 왜인가?
:::

---

여기서 책을 마친다. 1부에서 "변수는 상자가 아니라 이름표"라는 문장으로 시작해서, 그 이름표 하나(참조 카운팅)가 결국 10부 끝에서 `shared_ptr`이라는 다른 언어의 문법으로 다시 나타나는 것을 봤다. 동시성 파트에서 배운 GIL은 왜 rclpy 제어 루프가 지터에 취약한지를 설명하는 근거가 됐고, 성능 파트에서 배운 프로파일링은 "느낄 것 같다"가 아니라 "측정된 병목"으로 판단하라는 원칙으로 이 절에 다시 나왔다. 알고리즘과 코딩테스트 파트에서 훈련한 복잡도 감각은 로봇 노드 하나하나의 설계에도 그대로 적용된다. 언어는 도구다. 이 책이 진짜로 가르치려 한 것은 특정 문법이 아니라, **왜 그렇게 동작하는지 묻는 습관**이었다. 그 습관을 가지고 있다면, rclpy든 rclcpp든, 다음에 나올 어떤 언어든 큰 문제가 되지 않는다.
