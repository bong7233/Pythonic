# 10.2 워크스페이스, 패키지, colcon

::: lead
지금까지 이 책에서 "패키지"는 `pyproject.toml` 하나와 `import` 문 몇 개로 끝나는 개념이었다([1.19 모듈, 패키지, import 시스템](#/imports), [6.5 패키징](#/packaging)). ROS 2에서는 다르다. 로봇 하나를 움직이려면 메시지 정의 패키지, 드라이버 패키지, 인식 패키지, 실행 패키지가 서로를 참조하며 수십 개가 얽힌다. 이걸 어떤 순서로 빌드하고, 어떻게 서로 찾게 만들고, 시스템에 이미 깔린 ROS와 내 코드를 어떻게 겹쳐 쓸지 — 이 절이 그 배관을 다룬다. rclpy 코드를 한 줄도 쓰기 전에 이걸 정확히 알아야, 나중에 "왜 내 노드가 안 뜨지"를 30분 삽질하지 않는다.
:::

## 워크스페이스라는 그릇

**워크스페이스**(workspace)는 여러 ROS 2 패키지의 소스 코드를 담는 디렉터리다. 특별할 것 없다 — 그냥 `src/` 라는 하위 폴더를 가진 평범한 디렉터리다.

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/ros/ros_tutorials.git -b jazzy
```

이 안에 패키지 여러 개를 자유롭게 넣는다. 각 패키지는 자기 디렉터리 하나를 차지하고, 그 안에 `package.xml` 이 있다는 것만으로 "이건 ROS 2 패키지다"라고 인식된다. 워크스페이스 자체는 패키지가 아니다 — 그냥 여러 패키지를 한 번에 빌드하기 위한 작업 단위다.

빌드는 워크스페이스 루트에서 한다.

```bash
cd ~/ros2_ws
colcon build
```

여기서 처음 마주치는 게 4개의 디렉터리다.

```text nolines
ros2_ws/
├── src/         <- 소스 코드. 당신이 직접 채우는 유일한 폴더
├── build/       <- 빌드 중간 산출물. 패키지마다 하위 폴더 하나씩
├── install/     <- 빌드 완료된 결과물. 실행 파일과 setup.bash가 여기 있다
└── log/         <- colcon build를 돌릴 때마다 쌓이는 로그
```

- **`src/`** — 유일하게 당신이 손으로 관리하는 폴더다. 나머지 셋은 `colcon build` 가 매번 다시 만들어 낼 수 있는 파생물이다.
- **`build/`** — colcon이 각 패키지를 컴파일/처리하는 작업 공간이다. `ament_cmake` 패키지라면 CMake의 중간 오브젝트 파일이, `ament_python` 패키지라면 `setup.py` 실행 흔적이 여기 남는다.
- **`install/`** — 최종 산출물이 설치되는 곳이다. 실행 파일, 파이썬 모듈, launch 파일, 그리고 **이 워크스페이스를 쓰기 위한 `setup.bash`** 가 여기에 있다.
- **`log/`** — 빌드할 때마다 타임스탬프가 찍힌 폴더가 새로 생긴다. 빌드 실패 원인을 추적할 때 여기부터 본다.

::: tip build/install/log는 지워도 된다
이 셋은 `src/` 로부터 재생성 가능한 캐시다. 이상하게 빌드가 꼬였을 때 가장 확실한 해결책은 지우고 다시 빌드하는 것이다.

```bash
rm -rf build/ install/ log/
colcon build
```

`src/` 만은 절대 실수로 지우면 안 된다. 거기엔 당신이 짠 코드가 있다.
:::

## 패키지의 두 얼굴: ament_python과 ament_cmake

`ros2 pkg create` 로 새 패키지를 만들 때 빌드 타입을 고른다.

```bash
ros2 pkg create --build-type ament_python --license Apache-2.0 my_package
ros2 pkg create --build-type ament_cmake --license Apache-2.0 my_cpp_package
```

둘의 차이는 단순하다. **`ament_cmake`** 는 C++ 패키지용으로, 빌드 지시서가 `CMakeLists.txt` 다. **`ament_python`** 은 순수 파이썬 패키지용으로, 빌드 지시서가 `setup.py` 다 (파이썬 표준 `setuptools` 그대로 재활용한 것이다). C++과 파이썬을 한 패키지에 섞으려면 `ament_cmake_python` 이라는 세 번째 선택지가 있지만, ROS 2 공식 문서는 "웬만하면 파이썬 전용 패키지는 `ament_python` 을 쓰라"고 못박는다 — 섞는 건 진짜 필요할 때만 하는 예외적인 선택이다.

두 타입 모두 **패키지 루트에 `package.xml` 이 있어야 한다는 점은 같다.** 빌드 도구가 무엇이든, colcon이 "이 폴더가 패키지인지, 무엇에 의존하는지"를 판단하는 근거는 항상 `package.xml` 이다.

```text nolines
my_package/                    <- ament_python
├── package.xml                <- 메타데이터 + 의존성 (공통)
├── setup.py                   <- 빌드 지시서 (파이썬)
├── setup.cfg                  <- 스크립트 설치 경로 지정
├── my_package/
│   ├── __init__.py
│   └── my_node.py
└── resource/
    └── my_package             <- 빈 파일. ament 인덱스 등록용

my_cpp_package/                <- ament_cmake
├── package.xml                <- 메타데이터 + 의존성 (공통)
├── CMakeLists.txt              <- 빌드 지시서 (C++)
├── src/
│   └── my_node.cpp
└── include/
```

::: note resource/ 폴더가 왜 있나
`ament_python` 패키지에는 `resource/<패키지이름>` 이라는 빈 파일이 하나 있다. 내용은 없고, 존재 자체가 중요하다. `ament index`(ROS 2가 설치된 패키지를 등록해 두는 내부 색인)에 이 패키지가 있다는 걸 알리는 표식이다. `ros2 pkg list`, `ament_index_python` 같은 도구가 이 색인을 뒤진다.
:::

## package.xml: 의존성 선언과 빌드 순서

`package.xml` 이 하는 일은 두 가지다. 메타데이터(이름, 버전, 설명, 라이선스)를 적는 것, 그리고 **`<depend>` 태그로 의존 패키지를 선언하는 것.**

```xml title="package.xml — 최소 형태"
<?xml version="1.0"?>
<package format="3">
  <name>sensor_driver</name>
  <version>0.1.0</version>
  <description>라이다 드라이버</description>
  <maintainer email="you@example.com">you</maintainer>
  <license>Apache-2.0</license>

  <depend>rclpy</depend>
  <depend>my_msgs</depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

colcon은 워크스페이스 안의 모든 `package.xml` 을 먼저 훑어서 **의존성 그래프**를 만들고, 그 그래프를 **위상 정렬**해서 빌드 순서를 정한다. `sensor_driver` 가 `my_msgs` 를 의존한다면, `my_msgs` 가 먼저 빌드돼야 한다 — 이건 [7.17 위상 정렬과 DAG](#/topological)에서 다룬 바로 그 알고리즘이다. 실제로 colcon 내부가 이 문제를 어떻게 푸는지, 최소한의 논리만 뽑아 직접 확인해 보자.

```python title="colcon이 하는 일: package.xml 파싱 + 위상 정렬"
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

PACKAGE_XMLS = {
    "my_msgs": """<?xml version="1.0"?>
<package format="3">
  <name>my_msgs</name>
  <depend>rosidl_default_generators</depend>
</package>""",
    "sensor_driver": """<?xml version="1.0"?>
<package format="3">
  <name>sensor_driver</name>
  <depend>rclpy</depend>
  <depend>my_msgs</depend>
</package>""",
    "perception": """<?xml version="1.0"?>
<package format="3">
  <name>perception</name>
  <depend>rclpy</depend>
  <depend>sensor_driver</depend>
  <depend>my_msgs</depend>
</package>""",
    "bringup": """<?xml version="1.0"?>
<package format="3">
  <name>bringup</name>
  <depend>perception</depend>
  <depend>sensor_driver</depend>
</package>""",
}


def parse_depends(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    return root.findtext("name"), [el.text for el in root.findall("depend")]


local_packages = set(PACKAGE_XMLS)
graph = defaultdict(list)
indegree = {name: 0 for name in local_packages}

for name, xml_text in PACKAGE_XMLS.items():
    _, deps = parse_depends(xml_text)
    for dep in deps:
        if dep in local_packages:        # rclpy, rosidl_...은 언더레이에 이미 있다 → 제외
            graph[dep].append(name)
            indegree[name] += 1

queue = deque(sorted(n for n, d in indegree.items() if d == 0))
build_order = []
while queue:
    node = queue.popleft()
    build_order.append(node)
    for nxt in sorted(graph[node]):
        indegree[nxt] -= 1
        if indegree[nxt] == 0:
            queue.append(nxt)

print("colcon이 계산할 빌드 순서:", build_order)
assert len(build_order) == len(local_packages), "순환 의존성이 있다!"
```

```text nolines
colcon이 계산할 빌드 순서: ['my_msgs', 'sensor_driver', 'perception', 'bringup']
```

(직접 실행해 확인함. Python 3.14.5 기준.) `rclpy`, `rosidl_default_generators` 처럼 워크스페이스 **바깥**(언더레이)에 이미 빌드돼 있는 패키지는 그래프에서 제외했다 — colcon도 정확히 이렇게, "워크스페이스 안에서 아직 안 빌드된 것들" 사이의 순서만 계산한다.

::: cote 코딩테스트 포인트가 실전에서 이렇게 나온다
위상 정렬을 "그래프 문제집에서나 보는 것"으로 여기기 쉽지만, `colcon build` 를 칠 때마다 정확히 이 알고리즘이 워크스페이스 뒤에서 돌고 있다. 순환 의존성(A가 B를, B가 A를 요구)이 생기면 `assert` 가 터지듯 colcon도 빌드 순서를 정하지 못하고 에러를 낸다. **순환 의존성은 설계 실수의 신호다.** 보통 공통 부분을 세 번째 패키지로 뽑아내서 푼다.
:::

## setup.py와 setup.cfg: 파이썬 패키지의 진입점

`ament_python` 패키지의 `setup.py` 는 표준 `setuptools` 문법 그대로다. 다른 점은 **`entry_points` 로 노드를 실행 파일처럼 등록한다**는 것.

```python title="setup.py — 공식 튜토리얼(rclpy 퍼블리셔/구독자) 기준"
from setuptools import find_packages, setup

package_name = "py_pubsub"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="you",
    maintainer_email="you@example.com",
    description="예시 패키지",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "talker = py_pubsub.publisher_member_function:main",
            "listener = py_pubsub.subscriber_member_function:main",
        ],
    },
)
```

(공식 튜토리얼 "Writing a simple publisher and subscriber (Python)"의 `entry_points` 형식과 대조해 확인했다. docs.ros.org, Jazzy/Rolling 기준 — 배포판이 달라도 이 부분 문법은 동일하다.)

`entry_points["console_scripts"]` 의 각 줄은 `실행이름 = 모듈경로:함수` 형태다. `ros2 run py_pubsub talker` 라고 치면, ROS 2는 이 매핑을 보고 `py_pubsub.publisher_member_function` 모듈의 `main` 함수를 호출한다. **이건 파이썬 `pyproject.toml` 의 `[project.scripts]` 와 정확히 같은 메커니즘이다** — `setuptools` 가 원래 하던 일을 ROS 2가 그대로 빌려 쓴 것뿐이다. [6.5 패키징](#/packaging)에서 본 그 진입점 개념이 여기서도 나온다.

`setup.cfg` 는 짧다. 실행 파일이 설치될 위치를 지정한다.

```ini title="setup.cfg"
[develop]
script_dir=$base/lib/py_pubsub
[install]
install_scripts=$base/lib/py_pubsub
```

`ros2 run` 은 `install/<패키지>/lib/<패키지>/` 아래에서 실행 파일을 찾는다. 이 경로 규칙이 `setup.cfg` 에 박혀 있다 — 직접 건드릴 일은 거의 없지만, "왜 하필 `lib/` 밑인가"를 알아 두면 나중에 실행 파일이 안 보일 때 어디를 봐야 할지 감이 온다.

::: warn 새 노드를 추가했는데 ros2 run이 못 찾는다면
가장 흔한 원인 두 가지.

1. **`setup.py` 의 `entry_points` 에 새 노드를 안 넣었다.** 파일만 만들었다고 실행 파일이 되는 게 아니다. 이 매핑에 한 줄 추가하고 다시 빌드해야 한다.
2. **다시 빌드한 뒤 `source` 를 다시 안 했다.** 아래에서 자세히 다룬다.
:::

## colcon build가 실제로 하는 일

`colcon build` 를 그냥 치면 워크스페이스 안의 **모든** 패키지를 위상 정렬 순서대로, 가능한 만큼 **병렬로** 빌드한다. 실전에서 자주 쓰는 플래그가 몇 개 있다.

```bash
# 특정 패키지 하나와 그 의존성만 빌드 (워크스페이스 전체를 다시 돌리지 않는다)
colcon build --packages-up-to sensor_driver

# 파이썬 노드를 수정할 때마다 재빌드하지 않도록 심볼릭 링크로 설치
colcon build --symlink-install

# 빌드 중 콘솔 출력을 바로 보고 싶을 때 (기본은 log/ 에만 쌓인다)
colcon build --event-handlers console_direct+
```

::: tip --symlink-install은 왜 유용한가
`ament_python` 패키지는 순수 파이썬 파일을 `install/` 아래로 **복사**한다. `--symlink-install` 없이 노드 코드를 한 줄 고치면, `install/` 안의 복사본은 그대로라서 **`colcon build` 를 다시 돌려야 반영된다.** 심볼릭 링크로 설치하면 `install/` 의 파일이 `src/` 의 원본을 가리키는 링크가 돼서, 파이썬 코드를 고친 즉시 `ros2 run` 에 반영된다. C++ 노드는 컴파일이 필요하므로 이 옵션이 효과가 없다 — 여전히 재빌드해야 한다.

개발 중에는 거의 항상 켜 두는 게 낫다. 처음 워크스페이스를 만들 때부터 습관을 들여라.
:::

`--packages-up-to` 가 왜 워크스페이스 전체 재빌드보다 나은지도 위상 정렬 그림으로 보면 명확하다. 앞서 만든 `bringup → perception → sensor_driver → my_msgs` 의존 그래프에서, `sensor_driver` 코드만 고쳤다면 `perception` 과 `bringup` 은 다시 빌드할 이유가 없다 — 정확히는 **그 패키지에 의존하는 하류(downstream)만** 다시 봐야 하는데, `--packages-up-to` 는 반대로 **그 패키지가 필요로 하는 상류만** 빌드 대상으로 좁혀 준다. 대규모 워크스페이스(패키지 수십 개)에서 이 차이는 빌드 시간을 몇 분에서 몇 초로 줄인다.

## 오버레이와 언더레이: source가 여러 겹인 이유

여기부터가 초심자를 가장 많이 헷갈리게 하는 부분이다. ROS 2를 쓰려면 `install/setup.bash` 를 **source** 해야 한다는 건 알겠는데, 왜 매번 두 번, 세 번씩 source 하라고 하는가?

답은 ROS 2 자체가 **하나의 거대한 workspace 결과물**이라는 데 있다. `/opt/ros/jazzy` 는 ROS 2 재단이 미리 빌드해 둔 install 디렉터리다. 당신의 `~/ros2_ws` 는 그 위에 또 하나의 install 디렉터리를 얹는 것이다.

```bash
source /opt/ros/jazzy/setup.bash          # 1. 언더레이: 시스템에 깔린 ROS 2
source ~/ros2_ws/install/local_setup.bash # 2. 오버레이: 내가 만든 패키지들
```

- **언더레이**(underlay) — 먼저 source하는 기반 워크스페이스. 보통 `/opt/ros/<distro>` 다.
- **오버레이**(overlay) — 언더레이 위에 겹쳐 쓰는 워크스페이스. 당신의 `~/ros2_ws` 다.

핵심 규칙 하나: **나중에 source한 것이 검색 경로의 맨 앞에 붙고, 우선순위를 갖는다.** 언더레이에도 `my_msgs` 가 있고 오버레이에도 같은 이름의 `my_msgs` 를 다시 빌드했다면, `ros2` 도구는 오버레이 쪽을 먼저 찾아서 그걸 쓴다. `setup.bash` 가 내부적으로 하는 일의 본질은 `AMENT_PREFIX_PATH` 같은 환경 변수 **맨 앞에 새 경로를 추가**하는 것뿐이다. 그 부분만 파이썬으로 재현해 보면 원리가 뚜렷하게 보인다.

```python title="overlay가 우선순위를 갖는 이유 — PATH 앞에 붙이기"
SEP = ":"  # 리눅스 PATH 구분자


def prepend_path(env_value: str, new_front: str) -> str:
    parts = [p for p in env_value.split(SEP) if p]
    if new_front in parts:
        parts.remove(new_front)
    return SEP.join([new_front, *parts])


ament_prefix_path = ""
ament_prefix_path = prepend_path(ament_prefix_path, "/opt/ros/jazzy")
print("언더레이만 source:", ament_prefix_path)

ament_prefix_path = prepend_path(ament_prefix_path, "/home/user/ros2_ws/install/my_msgs")
ament_prefix_path = prepend_path(ament_prefix_path, "/home/user/ros2_ws/install/sensor_driver")
print("오버레이까지 source:", ament_prefix_path)

print("가장 먼저 검색되는 prefix:", ament_prefix_path.split(SEP)[0])
```

```text nolines
언더레이만 source: /opt/ros/jazzy
오버레이까지 source: /home/user/ros2_ws/install/sensor_driver:/home/user/ros2_ws/install/my_msgs:/opt/ros/jazzy
가장 먼저 검색되는 prefix: /home/user/ros2_ws/install/sensor_driver
```

(직접 실행해 확인함. 실제 `setup.bash` 는 이 외에도 `PATH`, `PYTHONPATH`, `LD_LIBRARY_PATH` 등 여러 변수를 함께 조작하고 각 패키지의 `local_setup.bash` 를 순회하는 등 훨씬 복잡하지만, **"뒤에 source한 게 앞자리를 차지한다"는 원리는 이 문자열 조작 하나로 요약된다.**)

::: danger 새 터미널을 열 때마다 source를 잊는다
가장 흔한 사고. `colcon build` 를 새 터미널에서 하고 바로 `ros2 run` 을 치면 십중팔구 "package not found" 다. **각 터미널은 독립된 프로세스라서, source는 그 터미널에만 적용된다.** 새 터미널을 열 때마다 언더레이와 오버레이를 둘 다 다시 source해야 한다.

매번 치기 귀찮다면 `~/.bashrc` 맨 아래에 넣어 두는 것도 방법이다. 다만 워크스페이스가 여러 개면 이것도 꼬임의 원인이 된다 — 어느 워크스페이스가 "현재" 오버레이인지 헷갈리기 쉽다.
:::

::: warn 오버레이 안에서 언더레이 패키지를 고쳤다면
오버레이에서 언더레이와 **같은 이름**의 패키지를 다시 빌드해 두면, 앞의 실험이 보여주듯 오버레이 버전이 이긴다. 이건 의도한 동작이지만, 자기가 뭘 실행하고 있는지 헷갈리기 쉽다. `ros2 pkg prefix <패키지이름>` 으로 지금 어느 install 경로에서 그 패키지를 찾았는지 바로 확인할 수 있다.
:::

## 흔한 빌드 실수

이 절을 마무리하며 실전에서 반복적으로 마주치는 실수를 모아 둔다.

::: warn "고쳤는데 반영이 안 된다"
1. **재빌드를 안 했다.** `ament_cmake` 패키지의 C++ 코드는 항상 재빌드가 필요하다.
2. **재빌드는 했는데 새 터미널에서 source를 안 했다.** 위에서 다룬 그 문제다.
3. **`--symlink-install` 없이 빌드해서, 파이썬 코드를 고쳤는데 `install/` 의 복사본이 옛날 그대로다.**
:::

::: warn package.xml에 의존성을 안 적었다
코드에서 `import my_msgs` 를 쓰면서 `package.xml` 에 `<depend>my_msgs</depend>` 를 빠뜨리면, 지금 당장은 두 패키지가 같은 워크스페이스에서 우연히 순서대로 빌드돼서 문제가 안 보일 수도 있다. 하지만 `--packages-select` 로 일부만 빌드하거나, 다른 사람이 이 패키지 하나만 떼어서 빌드하면 즉시 깨진다. **런타임에 동작하는 것과 의존성 그래프에 선언하는 것은 별개다.** `rosdep` 도 `package.xml` 을 근거로 시스템 패키지를 설치하므로, 여기 빠지면 다른 컴퓨터에서 아예 빌드가 안 될 수 있다.
:::

::: warn resource/ 파일이나 __init__.py를 빠뜨렸다
`ament_python` 패키지에서 `resource/<패키지이름>` 빈 파일이 없으면 `ament index` 에 등록되지 않아 `ros2 pkg list` 에도 안 뜬다. 서브 디렉터리를 새로 만들었는데 `__init__.py` 를 안 넣으면 `find_packages()` 가 그 폴더를 못 찾는다 — 파이썬 패키지 규칙([1.19 모듈, 패키지, import 시스템](#/imports))이 여기서도 그대로 적용된다.
:::

::: hist 왜 이렇게 복잡한 빌드 시스템을 만들었나
ROS 1의 `catkin` 은 워크스페이스 전체를 **하나의 CMake 프로젝트**로 묶어서 빌드했다. 패키지 하나만 따로 빌드하거나, 파이썬과 C++을 자연스럽게 섞기가 까다로웠다. ROS 2의 `ament` + `colcon` 조합은 **각 패키지를 독립적인 빌드 단위**로 취급하고, colcon이 그 위에서 의존성 순서만 조율하는 방식으로 바꿨다. 그 대가가 지금 본 것들이다 — `package.xml` 이라는 공통 계약, 그리고 언더레이/오버레이라는 겹쳐 쓰기 구조. 복잡해 보이지만, 실은 "패키지마다 독립적으로 만들고, 필요한 것만 겹쳐 쓴다"는 하나의 원칙에서 나온 결과다.
:::

## 요약

- 워크스페이스는 `src/build/install/log` 네 폴더로 이뤄진다. 손으로 관리하는 건 `src/` 뿐이다.
- `package.xml` 은 모든 패키지에 공통이다. 빌드 도구만 `ament_python`(파이썬, `setup.py`)과 `ament_cmake`(C++, `CMakeLists.txt`)로 갈린다.
- colcon은 `package.xml` 의 `<depend>` 로 의존성 그래프를 만들고 **위상 정렬**해서 빌드 순서를 정한다 ([7.17 위상 정렬](#/topological)과 같은 알고리즘).
- `setup.py` 의 `entry_points["console_scripts"]` 가 `ros2 run` 으로 실행할 노드를 등록한다. `pyproject.toml` 의 `[project.scripts]` 와 같은 메커니즘이다.
- `--symlink-install` 은 파이썬 코드 수정이 재빌드 없이 반영되게 해 준다. 개발 중엔 거의 항상 켠다.
- **언더레이**(시스템 ROS)를 먼저, **오버레이**(내 워크스페이스)를 나중에 source한다. 나중에 source한 게 검색 우선순위를 갖는다.
- 새 터미널마다 source를 다시 해야 한다는 것, `package.xml` 에 실제 의존성을 빠짐없이 적어야 한다는 것이 실전에서 가장 많이 걸리는 함정이다.

::: quiz 연습문제
1. 워크스페이스의 `build/`, `install/`, `log/` 를 전부 지우고 `colcon build` 를 다시 돌리면 무슨 일이 일어나는가? `src/` 도 함께 지우면 어떻게 다른가?
2. 패키지 A가 B를, B가 C를 의존하고, 실수로 C가 A를 의존하도록 `package.xml` 을 적었다고 하자. `colcon build` 를 돌리면 어떤 일이 벌어질지 위상 정렬의 관점에서 설명하라.
3. `ament_python` 패키지에 새 노드 파일 `my_package/tracker.py` 를 추가하고 `main()` 함수를 정의했다. `ros2 run my_package tracker` 가 동작하게 하려면 어떤 파일을 어떻게 고쳐야 하는가?
4. 터미널을 새로 열고 `source /opt/ros/jazzy/setup.bash` 만 실행한 뒤, 자신이 만든 패키지의 노드를 `ros2 run` 으로 실행하면 어떤 에러가 나겠는가? 왜인가?
5. `--symlink-install` 없이 빌드한 `ament_python` 패키지의 노드 코드를 수정했다. `colcon build` 없이 바로 `ros2 run` 하면 예전 코드가 실행되는 이유를 `install/` 디렉터리의 구조로 설명하라.
:::

**다음 절**: [10.3 rclpy 노드](#/rclpy-node) — 지금 빌드한 이 껍데기 안에, 실제로 스핀하는 노드를 만들어 넣는다.
