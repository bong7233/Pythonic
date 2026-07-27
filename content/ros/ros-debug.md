# 10.15 rosbag, 디버깅, 성능

::: lead
지금까지 이 책은 코드를 한 번 실행하고 결과를 보는 방식으로 진행됐다. 로봇은 다르다. 센서는 매 순간 다른 값을 내놓고, 노드는 여러 개가 동시에 돌고, 버그는 로봇이 실제로 벽에 부딪힌 다음에야 드러난다. **재현할 수 없는 버그는 고칠 수 없다** — 이 절은 그 문제를 푸는 도구들이다. `ros2 bag` 으로 그 순간을 통째로 저장해서 몇 번이고 되감아 재생하고, `ros2 topic echo/hz/bw` 와 `rqt_graph` 로 지금 이 시스템이 실제로 무엇을 주고받는지 들여다보고, 로깅 레벨로 노이즈와 신호를 가른다. 그리고 [Part IV의 GIL](#/gil)과 [Part V의 프로파일러](#/profiling)가 여기서 왜 결정적으로 중요해지는지 — "실시간"이라는 말이 일반 리눅스 위의 rclpy 노드에서 실제로 무엇을 뜻하고 무엇을 뜻하지 않는지 — 를 본다.
:::

## rosbag2 — 로봇에게 되감기 버튼을 달아준다

[10.4 토픽](#/topics)에서 발행/구독을 배웠지만, 실전에서 마주치는 진짜 문제는 이거다. 필드 테스트에서 로봇이 이상한 경로로 돌았다. 그런데 그 순간의 LiDAR 스캔, IMU 값, TF, 파라미터를 지금 다시 만들어낼 방법이 없다. 로봇을 다시 그 장소에 데려가도 조명, 배터리 전압, 바닥 마찰이 그때와 같지 않다. **버그를 재현할 수 없으면 고칠 수 없다.**

`rosbag2` 는 토픽에 흐르는 메시지를 그대로 디스크에 기록했다가, 나중에 **똑같은 순서로, 똑같은 타이밍으로** 다시 발행하는 도구다. 기록된 데이터는 실제 로봇도 시뮬레이터도 필요 없다. 노드 입장에서는 진짜 센서가 발행하는 것과 구별이 안 된다 — 구독자는 토픽 이름과 타입만 본다.

### ros2 bag record

```bash
# 지정한 토픽만 기록한다
ros2 bag record /scan /odom /tf

# -o 로 출력 디렉터리 이름을 직접 지정한다
ros2 bag record -o field_test_01 /scan /odom /tf

# -a 는 지금 떠 있는 모든 토픽·서비스·액션을 기록한다 (디버깅 초기엔 이게 편하다)
ros2 bag record -a

# 토픽만 기록하고 서비스/액션은 빼고 싶으면 --all-topics (짧은 옵션은 없다)
ros2 bag record --all-topics
```

`-a`(`--all`)의 공식 help 문구는 "Record all topics, services and actions (Exclude hidden topic)"다(ros2/rosbag2 rolling 기준 `ros2bag/verb/record.py`). 즉 `-a`는 토픽뿐 아니라 서비스·액션까지 함께 기록한다 — "모든 토픽만"이 아니다. 토픽만 원하면 짧은 옵션이 없는 `--all-topics`를 써야 한다. Jazzy부터 서비스 기록 기능이 들어갔다는 정황이 있어 이 책이 기준으로 삼는 최신 LTS에서도 동일하게 동작할 가능성이 높지만, 배포판마다 `-a`의 정확한 동작이 바뀔 수 있으니 실제 사용 전엔 `ros2 bag record --help`로 그 배포판의 문구를 확인하라.

`Ctrl+C` 로 멈추면 지정한 이름(또는 타임스탬프 기반 자동 이름)의 디렉터리가 생기고, 그 안에 `metadata.yaml` 과 실제 데이터 파일(`.mcap` 파일 또는 `sqlite3` 파일)이 들어간다.

```text nolines
field_test_01/
├── metadata.yaml
└── field_test_01_0.mcap
```

::: note 저장 포맷 — mcap과 sqlite3
ROS 2 Iron부터 (그리고 이 책이 기준으로 삼는 Jazzy에서도) rosbag2의 기본 저장소는 `mcap` 이다(ROS 1의 단일 `.bag` 포맷과 달리, rosbag2는 저장소 자체가 **플러그인**이다) — Iron 이전까지 기본이던 `sqlite3` 에서 전환됐다([ROS Discourse 공지](https://discourse.openrobotics.org/t/psa-default-ros-2-bag-storage-format-is-changing-to-mcap-in-iron/28489) 및 `rosbag2_storage_default_plugins` 패키지 참고). [MCAP](https://mcap.dev)은 append-only 쓰기 방식이라 기록 도중 전원이 나가거나 레코더가 죽어도 손상되는 건 마지막 몇 메시지뿐이고, 벤치마크상 쓰기 처리량도 sqlite3보다 높다. 예전 방식대로 `sqlite3` 파일을 얻고 싶으면 `--storage sqlite3` 를 명시해야 한다 — 지금은 이쪽이 opt-in 이다.
:::

`ros2 bag info` 로 기록된 내용을 요약해서 볼 수 있다.

```bash
ros2 bag info field_test_01
```

```text nolines
Files:             field_test_01_0.mcap
Bag size:          25.7 KiB
Storage id:        mcap
Duration:          10.47s
Start:             Jul  1 2026 15:40:52.483 (1751370852.483)
End:               Jul  1 2026 15:41:02.531 (1751370862.531)
Messages:          32
Topic information: Topic: /scan | Type: sensor_msgs/msg/LaserScan | Count: 21 | Serialization Format: cdr
                    Topic: /odom | Type: nav_msgs/msg/Odometry     | Count: 11 | Serialization Format: cdr
```

(위 출력은 공식 튜토리얼에서 확인된 형식을 그대로 따른 예시다. 실제 값은 기록한 토픽과 시간에 따라 달라진다.)

::: cote 이분 탐색으로 특정 순간 찾기
`ros2 bag info` 의 `Start`/`End` 를 보면 감이 오겠지만, 실제로 rosbag2는 내부적으로 메시지를 **타임스탬프 순으로 정렬된 시퀀스**로 저장한다. "사고 발생 시각 근처의 메시지만 뽑고 싶다"는 요청은 결국 정렬된 배열에서 특정 값 이상인 첫 원소를 찾는 문제고, 이건 정확히 [7.5 이분 탐색](#/binary-search)이다. `rosbag2_py` 로 프로그래밍적으로 bag을 열면 메시지를 순서대로만 순회할 수 있는데, 수백만 개짜리 로그에서 특정 시각 부근만 보고 싶다면 타임스탬프 목록을 별도로 뽑아 `bisect` 로 위치를 찾은 뒤 그 지점부터 순회하는 식으로 $O(\log n)$ 에 도달할 수 있다. 순차 탐색이면 $O(n)$ 이다.
:::

### ros2 bag play — 재생

```bash
ros2 bag play field_test_01

# 두 배속으로 재생
ros2 bag play field_test_01 --rate 2.0

# 끝나면 처음부터 반복
ros2 bag play field_test_01 --loop

# 시뮬레이션 시간(/clock)을 함께 발행 — Nav2 등 use_sim_time 노드와 맞출 때 필수
ros2 bag play field_test_01 --clock 100
```

재생 중인 bag은 원래 발행자가 그랬던 것처럼 메시지 사이의 **시간 간격까지 재현**한다. `--rate` 는 그 간격을 통째로 스케일링하는 것이고, `--clock` 은 노드들이 벽시계 대신 bag의 시간을 `/clock` 토픽으로 구독하게 만든다.

::: warn 재생은 QoS까지 완벽하게 복제하지 않는다
[10.8 QoS](#/qos)에서 본 신뢰성·내구성 설정은 원래 발행자가 어떤 QoS로 발행했는지에 달려 있다. rosbag2는 기록 시점에 각 토픽의 QoS 프로파일을 `metadata.yaml` 에 함께 저장하고 재생 시 최대한 복원하려 하지만, **구독자 쪽 QoS와 재생기 쪽 QoS가 호환되지 않으면 여전히 메시지가 전혀 도착하지 않는다.** "bag은 재생되는데 내 노드는 아무것도 못 받는다"는 사고를 만나면 제일 먼저 QoS 호환성부터 의심하라.
:::

::: hist 왜 ROS 1의 rosbag과 다른 설계인가
ROS 1의 `rosbag` 은 자체 바이너리 포맷 하나만 지원했다. rosbag2는 저장소를 **플러그인**으로 분리해서(`rosbag2_storage_sqlite3`, `rosbag2_storage_mcap`) 새 포맷을 언제든 추가할 수 있게 설계했다. ROS 2 전체를 관통하는 철학 — DDS 벤더도, 실행기(executor)도, 미들웨어도 교체 가능한 컴포넌트로 만든다 — 이 rosbag2의 저장소 계층에도 그대로 반영된 것이다.
:::

::: tip 노드 안에서 직접 기록/재생하기
CLI 대신 코드로 기록하고 싶을 때는 `rosbag2_py` 패키지의 `SequentialWriter`/`SequentialReader` 를 쓴다. 특정 조건에서만 기록을 켜고 끄거나, 재생한 메시지를 가공해서 다시 발행하는 식의 커스텀 파이프라인을 짤 때 필요하다. 이 절에서는 CLI만 다루지만, 존재만 알아두면 나중에 검색으로 충분히 찾아 쓸 수 있다.
:::

## 실시간 진단: echo, hz, bw

bag은 **과거**를 재현하는 도구다. 지금 이 순간 시스템이 뭘 하는지 보려면 다른 도구가 필요하다.

### ros2 topic echo — 지금 흐르는 메시지 그대로 보기

```bash
ros2 topic echo /odom
```

메시지가 발행될 때마다 그 내용을 YAML 형태로 그대로 찍는다. 필드 하나만 보고 싶으면 필드 경로를 지정한다.

```bash
ros2 topic echo /odom --field pose.pose.position
```

::: warn echo 자체가 부하다
`echo` 는 구독자를 하나 만들어서 매 메시지를 파싱하고 터미널에 출력한다. 카메라 이미지나 포인트클라우드처럼 큰 메시지가 초당 30번씩 나오는 토픽에 `echo` 를 걸면, **그 출력 자체가 눈에 띄는 CPU와 대역폭을 먹는다.** 진단이 끝나면 반드시 끄고, 큰 메시지는 `--no-arr` 로 배열 필드를 생략하거나 `hz`/`bw` 로 대체하라.
:::

### ros2 topic hz — 발행 주기 확인

```bash
ros2 topic hz /scan
```

```text nolines
average rate: 10.021
        min: 0.089s max: 0.112s std dev: 0.00731s window: 65
average rate: 9.985
        min: 0.091s max: 0.108s std dev: 0.00523s window: 130
```

`average rate` 가 기대한 값(예: 10Hz LiDAR라면 10.0 근처)에서 벗어나 있거나 `std dev`(지터)가 크면, 노드가 콜백을 제때 처리하지 못하고 있다는 신호다. `window` 는 통계를 낼 때 쓴 최근 샘플 개수인데, ros2cli의 `ros2topic/verb/hz.py`를 보면 `DEFAULT_WINDOW_SIZE = 10000`이고 `--window` 옵션의 기본값도 이 상수를 그대로 쓴다 — 즉 기본 window는 100이 아니라 10000이다. 위 예시에서 `window` 값이 65, 130처럼 계속 커지는 건 아직 그 상한(10000)에 못 미쳐서 매 출력마다 지금까지 쌓인 간격 수를 그대로 보여주는 것이고, 오래 관찰할수록 window는 10000에서 멈춘다. 더 짧은 구간만 보고 싶으면 `ros2 topic hz /scan --window 50` 처럼 직접 줄여서 지정하면 된다.

### ros2 topic bw — 대역폭 확인

```bash
ros2 topic bw /camera/image_raw
```

```text nolines
Subscribed to [/camera/image_raw]
24.51 MB/s from 46 messages
        Message size mean: 245.12 KB min: 245.12 KB max: 245.12 KB
```

(ros2/ros2cli rolling 기준 `ros2topic/verb/bw.py`의 `print_bw` 포맷을 따른 예시다. 단일 토픽을 볼 때는 `average:` 라는 라벨이 따로 붙지 않고 대역폭 값 뒤에 바로 `/s`가 붙으며, `from {n} messages`로 표본 개수를 알려준다. `window` 필드는 단일 토픽 출력에는 없다 — 이건 `ros2 topic bw` 로 토픽을 여러 개 동시에 지정했을 때 나오는 표 형식에서만 컬럼으로 등장한다.)

이미지·포인트클라우드처럼 무거운 토픽에서 특히 중요하다. DDS 기본 설정에서 네트워크 대역폭을 넘어서면 메시지가 조용히 드롭되기 시작하는데, `hz` 로는 "가끔 느려지네" 정도로만 보이고 `bw` 를 봐야 원인이 대역폭 포화라는 게 드러난다.

::: deep hz/bw는 슬라이딩 윈도우 통계다
`ros2 topic hz` 는 최근 `window` 개의 타임스탬프 간격을 모아 평균·표준편차를 낸다. 뒤에서 이 로직을 파이썬으로 직접 구현해서 검증한다 — CLI 뒤에서 실제로 일어나는 계산이 생각보다 단순하다는 걸 확인할 수 있다.
:::

## rqt_graph — 지금 누가 누구와 이야기하는가

노드가 10개 넘게 뜨면 "이 토픽을 진짜 구독하고 있는 노드가 있나?", "내가 리매핑한 이름이 제대로 연결됐나?" 를 머릿속으로 추적하기 어렵다. `rqt_graph` 는 지금 실행 중인 노드와 토픽, 그 사이의 발행/구독 관계를 그래프로 그려준다.

```bash
ros2 run rqt_graph rqt_graph
```

```text nolines
[laser_node] ──/scan──▶ [filter_node] ──/scan_filtered──▶ [nav_node]
                                                              │
                                                          /cmd_vel
                                                              ▼
                                                        [motor_driver]
```

노드는 타원, 토픽은 사각형으로 그려지고 화살표가 발행/구독 방향이다. 왼쪽 위의 설정에서 "Nodes/Topics (all)"을 켜면 토픽이 별도 노드로 그려지고, 디버그용 내부 노드(`/rosout` 로거 등)를 숨기는 필터도 있다.

::: tip 연결이 안 보이면 QoS나 네임스페이스부터 의심하라
`rqt_graph` 에 화살표가 안 그려진다는 것은 발행자와 구독자가 **같은 토픽 이름으로 매칭되지 않았다**는 뜻이다. 오타, 네임스페이스 프리픽스 누락, 또는 [10.8 QoS](#/qos) 비호환이 세 가지 흔한 원인이다. `ros2 topic info /scan --verbose` 로 실제 발행자/구독자 목록과 각각의 QoS를 확인하면 그래프만 보는 것보다 빠르게 원인을 좁힐 수 있다.
:::

## 로깅: get_logger와 심각도 레벨

`print()` 로 디버깅하면 두 가지가 안 된다. 로그를 낸 노드가 어디인지 구분이 안 되고, 배포 환경에서 조용히 끌 방법이 없다. rclpy는 [6.4 로깅](#/logging)에서 배운 표준 `logging` 모듈 대신 ROS 자체 로깅 계층(`rcutils`/`rcl` 위에 얹힌 것)을 쓴다 — 여러 노드, 여러 프로세스에 흩어진 로그를 한 곳(`/rosout` 토픽, 그리고 콘솔)으로 모으기 위해서다.

```python title="노드 안에서의 로깅"
class Watchdog(Node):
    def __init__(self):
        super().__init__('watchdog')
        self.get_logger().info('워치독 시작')

    def on_scan(self, msg):
        if not msg.ranges:
            self.get_logger().warning('빈 스캔 수신')
        self.get_logger().debug(f'ranges 길이: {len(msg.ranges)}')
```

심각도는 낮은 것부터 `DEBUG`(10) `INFO`(20) `WARN`(30) `ERROR`(40) `FATAL`(50) 순이다. 숫자가 클수록 심각하고, **현재 설정된 레벨보다 낮은 로그는 아예 버려진다**(문자열 포매팅조차 하지 않는다).

기본 레벨은 `INFO`다. 특정 노드만 더 자세히 보고 싶으면 실행할 때 레벨을 올린다.

```bash
ros2 run my_pkg watchdog --ros-args --log-level watchdog:=debug
```

::: danger DEBUG를 프로덕션에 그대로 두지 마라
`DEBUG` 레벨은 콜백마다 문자열 포매팅과 I/O를 만든다. 특히 `--ros-args --log-level DEBUG` 로 **전역** 레벨을 올리면 rclpy·rcl 내부 계층까지 DEBUG 로그를 쏟아내기 시작해서, 로그 자체가 실시간성을 갉아먹는 부하가 된다. 필드에 나가는 빌드는 반드시 노드별로 필요한 로거만 `debug` 로 좁혀서 켜라.
:::

::: tip 반복되는 경고는 throttle로 눌러라
센서가 매 프레임 같은 경고를 낸다면(예: "빈 스캔 수신") 로그 창이 그 한 줄로 도배된다. `throttle_duration_sec` 을 주면 그 시간 안의 반복 호출은 무시된다.

```python
self.get_logger().warning(
    '빈 스캔 수신', throttle_duration_sec=1.0,
)
```

"1초에 한 번만 찍는다"는 이 로직 자체는 rclpy 없이도 검증할 수 있다 — 아래 순수 파이썬 절에서 직접 구현하고 실행해 확인한다.
:::

## 실시간성이라는 것 — 그리고 일반 리눅스에서의 한계

"ROS 2는 실시간을 지원한다"는 문장은 자주 오해를 낳는다. **실시간(real-time)은 "빠르다"는 뜻이 아니라 "마감 시한을 지킨다는 것을 보장할 수 있다"는 뜻이다.** 로봇 팔이 100Hz로 토크를 계산해야 한다면, 평균적으로 100Hz가 나오는 것으로는 부족하다. 단 한 번이라도 그 주기를 크게 놓치면 팔이 튀거나 진동한다.

```text nolines
soft real-time:  가끔 마감을 놓쳐도 결과 품질만 떨어진다 (센서 로깅, 화면 표시)
hard real-time:  마감을 놓치면 시스템 전체가 실패한다   (모터 제어 루프, 안전 정지)
```

일반 데스크톱/서버용 리눅스 커널의 스케줄러는 **처리량(throughput)** 을 최적화하도록 설계됐다. "이 태스크가 다음 1ms 안에 반드시 실행된다"를 보장하지 않는다. 다른 프로세스, 인터럽트, 페이지 폴트, 가비지 컬렉션이 언제든 끼어들 수 있다.

::: warn ROS 2의 "실시간 지원"이 뜻하는 것
ROS 2가 설계 단계에서 실시간을 염두에 뒀다는 말은, **DDS 미들웨어와 executor 구조가 실시간 커널 위에서 결정적으로 동작하도록 설계됐다**는 뜻이지, 일반 우분투 데스크톱 위에서 자동으로 마감 시한이 보장된다는 뜻이 아니다. 진짜 hard real-time이 필요한 제어 루프(모터 드라이버, 힘 제어)는 보통 **PREEMPT_RT 패치가 적용된 리눅스 커널** 위에서, 그것도 C++(`rclcpp`)로 작성한다. 이 책이 다루는 rclpy는 그 요구를 만족시키기 위한 도구가 아니다.
:::

::: deep 왜 rclpy는 hard real-time에 근본적으로 불리한가
세 겹의 이유가 있다.

1. **인터프리터 오버헤드 자체가 예측 불가능하다.** [1.1 객체와 참조](#/objects-names)에서 본 참조 카운팅 GC는 대체로 결정적이지만, 순환 참조를 잡는 세대별 GC([5.2 메모리 모델](#/memory))는 **언제 도는지 예측하기 어렵다.** 하필 마감 직전에 GC 사이클이 끼어들면 그 주기의 콜백은 늦는다.
2. **[GIL](#/gil)이 병렬 실행 자체를 막는다.** 멀티스레드 executor로 콜백을 여러 스레드에 분산해도, 순수 파이썬 코드는 GIL 때문에 한 번에 한 스레드만 실제로 바이트코드를 실행한다. 콜백 A가 GIL을 오래 쥐고 있으면 콜백 B는 실제로 실행할 CPU가 비어 있어도 기다려야 한다. free-threaded 빌드([4.3 GIL과 free-threaded 파이썬](#/gil))가 이 제약을 풀 여지를 주지만, 아직 rclpy 생태계 전반이 이를 전제로 검증되지는 않았다.
3. **동적 타이핑과 객체 생성 비용이 매 콜백마다 들어간다.** 메시지를 파싱해서 파이썬 객체 그래프를 만드는 과정 자체가 C++ 구조체를 그대로 쓰는 것보다 할당·해제가 훨씬 잦다.

**결론은 이렇다.** rclpy는 "1초에 여러 번 돌면 충분한" 대부분의 로봇 태스크(내비게이션 의사결정, 상태 머신, 센서 퓨전 오케스트레이션)에는 전혀 문제가 없다. 하지만 "이번 1ms를 놓치면 로봇이 넘어진다"는 수준의 제어 루프라면, 그 부분만 C++로 떼어내는 게 옳다. [10.16 다음 단계: C++로](#/ros-next)에서 이 경계를 다시 정리한다.
:::

## 5장 프로파일링을 rclpy 노드에 적용하기

[5.1 측정 없이 최적화 없다](#/profiling)의 도구들은 rclpy 노드에도 그대로 쓸 수 있다. 다만 노드는 **한 번 실행하고 끝나는 스크립트가 아니라 `spin()` 으로 영원히 도는 프로세스**라는 점이 다르다.

- **`cProfile`** — 노드를 짧게 돌리고 끝낼 수 있으면(`rclpy.spin_once` 를 정해진 횟수만 돌린 뒤 종료) 그대로 감쌀 수 있다. 하지만 실제 배포된 노드는 계속 도니까, 보통 `SIGINT` 핸들러에서 `pr.disable(); pr.dump_stats(...)` 를 호출하는 식으로 "종료될 때 통계를 저장"하게 짠다.
- **`py-spy`** — rclpy 노드 프로파일링에서 훨씬 실용적이다. 코드를 한 줄도 안 건드리고, **이미 돌고 있는 실제 노드**의 PID에 외부에서 붙어 스냅샷을 뜬다.

  ```bash
  ros2 run my_pkg watchdog &
  # 다른 터미널에서
  uvx py-spy dump --pid 48213
  ```

  멀티스레드 executor를 쓰는 노드라면 여러 스레드의 스택이 한꺼번에 보인다 — 어느 콜백 그룹이 지금 [GIL](#/gil)을 쥐고 있는지, 어느 스레드가 뮤텍스 대기 중인지가 그대로 드러난다.

- **`line_profiler`** — 특정 콜백 하나가 유독 무겁다고 의심될 때, 그 콜백 함수에만 `@profile` 을 붙여 줄 단위로 좁힌다. 이미지 콜백처럼 초당 30번 불리는 함수에 걸어 두면 오버헤드가 크므로([5.1](#/profiling)에서 실측한 대로 수십~백 배), 짧게 켰다가 반드시 끈다.

::: perf 프로파일러의 후킹 비용은 콜백 빈도에 비례한다
[5.1](#/profiling)에서 `cProfile` 은 함수 호출/반환마다 후킹하므로 **호출 밀도가 높을수록 오버헤드가 커진다**는 걸 실측했다. rclpy 노드에서 이 사실이 특히 날카로워지는 지점은 고빈도 콜백이다. 100Hz IMU 콜백에 `cProfile` 을 걸면, 그 자체가 콜백 하나하나에 몇 배의 지연을 더해서 **콜백 예산을 넘기게 만들고, 그 결과 executor 큐가 밀리는** 관측 방해(observer effect)가 생긴다. 그래서 고빈도 콜백은 `cProfile` 로 통째로 감싸기보다, 짧은 시간만 `py-spy record` 로 샘플링하거나 뒤에서 볼 콜백 시간 직접 계측 코드를 심는 쪽이 낫다.
:::

## 실행 검증 — 진단 도구의 알고리즘을 직접 확인한다

지금까지 본 도구들은 rclpy 없이는 실제로 돌려 볼 수 없다. 하지만 그 도구들이 **내부적으로 어떤 계산을 하는지**는 순수 파이썬으로 재현하고 검증할 수 있다. 세 가지를 직접 실행해서 확인한다.

### hz 계산 — 슬라이딩 윈도우 평균 주파수

`ros2 topic hz` 는 최근 `window` 개의 타임스탬프 간격을 모아 평균과 표준편차를 낸다. `deque(maxlen=...)` 로 그대로 재현할 수 있다.

```python title="hz_calc.py"
from collections import deque
import statistics


class HzTracker:
    def __init__(self, window=10):
        self.window = window
        self.timestamps = deque(maxlen=window + 1)

    def tick(self, t):
        self.timestamps.append(t)

    def report(self):
        if len(self.timestamps) < 2:
            return None
        ts = list(self.timestamps)
        intervals = [b - a for a, b in zip(ts, ts[1:])]
        rate = 1.0 / statistics.mean(intervals)
        jitter = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
        return {
            "average_rate": round(rate, 3),
            "min": round(min(intervals), 4),
            "max": round(max(intervals), 4),
            "std_dev": round(jitter, 5),
        }


tracker = HzTracker(window=8)
t = 0.0
# 10Hz로 안정적으로 발행되다가 후반부에 지터가 낀 상황
for dt in [0.100] * 6 + [0.080, 0.135, 0.095, 0.150]:
    t += dt
    tracker.tick(t)
    print(tracker.report())
```

실제로 돌려 보면 첫 호출은 타임스탬프가 하나뿐이라 `report()`가 `None`을 돌려주고, 안정 구간에서는 정확히 10Hz가 나오다가, 지터가 낀 구간부터 평균이 흔들리고 `std_dev` 가 커지는 게 그대로 보인다.

```pyrepl
None
{'average_rate': 10.0, 'min': 0.1, 'max': 0.1, 'std_dev': 0.0}
{'average_rate': 10.0, 'min': 0.1, 'max': 0.1, 'std_dev': 0.0}
{'average_rate': 10.0, 'min': 0.1, 'max': 0.1, 'std_dev': 0.0}
{'average_rate': 10.0, 'min': 0.1, 'max': 0.1, 'std_dev': 0.0}
{'average_rate': 10.0, 'min': 0.1, 'max': 0.1, 'std_dev': 0.0}
{'average_rate': 10.345, 'min': 0.08, 'max': 0.1, 'std_dev': 0.00745}
{'average_rate': 9.79, 'min': 0.08, 'max': 0.135, 'std_dev': 0.01508}
{'average_rate': 9.877, 'min': 0.08, 'max': 0.135, 'std_dev': 0.01431}
{'average_rate': 9.302, 'min': 0.08, 'max': 0.15, 'std_dev': 0.02151}
```

(Python 3.14.5 기준 실측, 총 10줄. 첫 `tick()` 직후에는 타임스탬프가 1개뿐이라 간격을 계산할 수 없어 `None`이 찍힌다. `window=8` 이므로 타임스탬프가 9개 쌓이면 그 뒤로는 간격 개수가 8개로 고정되고, 마지막 줄은 10개의 `dt` 값을 모두 처리한 뒤(`dt=0.150`까지 반영된) 최종 상태다.)

`std_dev` 가 0.00745에서 0.01508로 두 배 뛰는 지점이, 실제로 `ros2 topic hz` 화면에서 지터가 늘었다고 느끼는 바로 그 신호다.

### 콜백 예산 초과 감지

타이머 콜백이 주기보다 오래 걸리면 executor 큐가 밀린다. 이걸 직접 재는 데코레이터는 rclpy 없이도 검증 가능하다.

```python title="callback_timer.py"
import functools
import time


def warn_if_slow(budget_sec):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            if elapsed > budget_sec:
                print(
                    f"[SLOW] {fn.__name__} took {elapsed * 1000:.2f}ms "
                    f"(budget {budget_sec * 1000:.1f}ms)"
                )
            return result
        return wrapper
    return deco


@warn_if_slow(budget_sec=0.01)   # 100Hz 타이머 -> 콜백 예산 10ms
def fast_callback():
    time.sleep(0.002)


@warn_if_slow(budget_sec=0.01)
def slow_callback():
    time.sleep(0.02)             # 예산 초과


fast_callback()
slow_callback()
```

```pyrepl
[SLOW] slow_callback took 20.44ms (budget 10.0ms)
```

(Python 3.14.5 기준 실측. `time.sleep` 오차 때문에 정확히 20.00ms은 아니지만 예산 10ms를 확실히 넘겼다는 판정에는 영향이 없다.) 실전에서는 `print` 대신 `self.get_logger().warning(..., throttle_duration_sec=1.0)` 을 부르면 그대로 노드에 옮겨 쓸 수 있다.

### 로그 throttle 게이트

`throttle_duration_sec` 의 핵심 규칙은 하나다. *"마지막으로 이 로그를 찍은 시각에서 지정한 시간이 안 지났으면 건너뛴다."*

```python title="log_throttle.py"
class ThrottleGate:
    def __init__(self):
        self._last_emit = {}

    def allow(self, key, now, duration_sec):
        last = self._last_emit.get(key)
        if last is None or (now - last) >= duration_sec:
            self._last_emit[key] = now
            return True
        return False


gate = ThrottleGate()
# 0.3초 간격으로 10번 들어오는 이벤트, 1초에 한 번만 통과시키고 싶다
times = [i * 0.3 for i in range(10)]
emitted = [t for t in times if gate.allow("scan_warn", t, duration_sec=1.0)]
print(emitted)
```

```pyrepl
[0.0, 1.2, 2.4]
```

(Python 3.14.5 기준 실측.) 0.3초마다 들어오는 10개의 이벤트 중 딱 3개만 통과했다 — 1.0초 이상 벌어진 시점(`0.0`, `1.2`, `2.4`)만 남는다. 로그 창을 도배하던 반복 경고가 이 로직 하나로 억제되는 이유가 여기 있다.

## 요약

- `ros2 bag record/play` 는 센서·토픽 데이터를 통째로 저장했다 재생하는 도구다. 로봇을 다시 현장에 데려가지 않고도 버그를 재현하게 해 준다.
- `ros2 bag info` 로 기록 내용을 확인하고, `--rate`/`--loop`/`--clock` 으로 재생을 제어한다. 재생이 안 되면 QoS 호환성부터 의심하라.
- `ros2 topic echo/hz/bw` 는 지금 이 순간의 메시지 내용·주기·대역폭을 진단한다. `echo` 자체가 부하이니 무거운 토픽엔 짧게만 걸어라.
- `rqt_graph` 는 노드-토픽 연결을 시각적으로 보여준다. 화살표가 안 보이면 이름 불일치나 QoS 비호환을 의심하라.
- `get_logger()` 의 심각도 레벨(`DEBUG~FATAL`)과 `throttle_duration_sec` 으로 로그의 신호 대 잡음비를 관리한다. 전역 DEBUG는 그 자체로 부하다.
- "실시간"은 "빠르다"가 아니라 "마감 시한을 보장한다"는 뜻이다. 일반 리눅스 + rclpy는 소프트 실시간까지가 현실적 한계고, hard real-time 제어 루프는 PREEMPT_RT + `rclcpp` 로 넘어간다.
- [5장의 프로파일링 도구](#/profiling)는 rclpy 노드에도 그대로 적용된다. 다만 고빈도 콜백에 `cProfile` 을 걸면 오버헤드 자체가 executor 큐를 밀리게 만드는 관측 방해가 생긴다 — `py-spy` 로 짧게 샘플링하는 쪽이 안전할 때가 많다.

::: quiz 연습문제
1. `ros2 bag record -a` 로 전체 토픽을 기록하는 방식과 `--topics` 로 필요한 것만 지정하는 방식은 각각 언제 쓰는 게 맞는가? 대용량 카메라 토픽이 섞여 있을 때를 기준으로 답하라.
2. `ros2 topic hz /scan` 의 `average rate` 는 안정적인데 `std dev` 만 갑자기 커졌다. 이게 무엇을 의미하는지, 그리고 어느 도구로 다음 조사를 이어가야 하는지 설명하라.
3. 이 절의 `HzTracker` 코드를 고쳐서, 간격이 기대 주기의 1.5배를 넘는 순간이 발생하면 그 시점의 인덱스를 출력하도록 만들어라. 실제로 실행해서 지터 구간이 정확히 잡히는지 확인하라.
4. rclpy 노드가 `PREEMPT_RT` 커널 위에서 돈다고 해서 hard real-time이 보장되지 않는 이유 세 가지를 이 절의 내용을 근거로 설명하라.
5. 100Hz로 도는 IMU 콜백 하나가 의심스러워 `cProfile` 을 노드 전체에 걸었다. 그 결과 콜백이 더 자주 예산을 초과하는 것처럼 보였다. 왜 이런 일이 생기는지, 그리고 대신 어떤 도구를 써야 하는지 설명하라.
:::

**다음 절**: [10.16 다음 단계: C++(rclcpp)로](#/ros-next) — 언제 파이썬을 떠나 C++로 넘어가야 하는가, rclpy와 rclcpp의 실제 차이, 그리고 이 책 전체를 마무리하는 마이그레이션 전략.
