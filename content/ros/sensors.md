# 10.12 센서 데이터 처리

::: lead
로봇은 숫자로만 세상을 본다. 카메라는 초당 30장의 이미지를, LiDAR는 초당 10바퀴의 거리 스캔을, IMU는 초당 200번의 가속도·각속도를 쏟아낸다. 이 셋은 속도도 다르고 타입도 다르고 심지어 "지금"이 언제인지에 대한 생각도 다르다. 이 절은 그 이질적인 데이터를 하나의 파이썬 배열로 모으고, 서로 다른 시각에 찍힌 값들을 "같은 순간"으로 묶는 문제를 다룬다. [1.5 bytes, bytearray, memoryview](#/bytes)에서 예고했던 그 지점 — `cv_bridge`가 이미지를 복사 없이 NumPy 배열로 바꾸는 이유 — 을 여기서 마침내 확인한다. 이 파트에서 유일하게 **실제로 실행해서 검증할 수 있는 부분**은 rclpy 없이 돌아가는 순수 배열·알고리즘 로직이고, 이 절은 그 부분을 최대한 끄집어낸다.
:::

## 센서 데이터가 유독 까다로운 이유

지금까지 이 책에서 다룬 데이터는 대체로 "한 번 들어오면 끝"이었다. 파일을 읽거나, API를 호출하거나, DB에서 쿼리하면 그 순간의 완결된 값을 받았다. 센서는 다르다. **끝나지 않는 스트림**이고, 게다가 셋 이상의 스트림이 서로 다른 속도로 동시에 흐른다.

```text nolines
camera  30Hz   ──●─────●─────●─────●─────●──▶ t
lidar   10Hz   ────────●───────────●────────▶ t
imu    200Hz   ●●●●●●●●●●●●●●●●●●●●●●●●●●●●●▶ t
```

"장애물까지 거리 1.2m, 그 순간 카메라에 뭐가 찍혔지?"라는 흔한 질문에 답하려면 세 스트림에서 **같은 순간에 가장 가까운 값**을 골라야 한다. 그런데 "같은 순간"이라는 게 정확히 무슨 뜻인지부터 애매하다. 카메라 30Hz와 LiDAR 10Hz는 애초에 서로 정확히 겹치는 순간이 거의 없다.

이 절이 다루는 문제는 정확히 세 가지다.

1. **표현** — 카메라 프레임, LiDAR 포인트클라우드, IMU 값을 어떤 자료구조로 받는가.
2. **변환** — 그 자료구조를 파이썬에서 실제로 계산 가능한 형태(NumPy 배열)로 바꾸는 비용.
3. **정렬** — 서로 다른 주기로 도착하는 여러 스트림을 "같은 순간"으로 묶는 알고리즘.

## 센서 메시지의 구조

ROS 2는 각 센서 종류마다 표준 메시지 타입을 정의해 뒀다(`sensor_msgs` 패키지). 값 자체는 결국 숫자 배열이지만, 그 배열을 **어떻게 해석해야 하는지**를 알려주는 메타데이터가 항상 같이 붙는다. 이 메타데이터를 무시하고 숫자만 보면 반드시 사고가 난다.

### Image — 카메라 프레임

```text nolines
sensor_msgs/msg/Image
├── header            Header        타임스탬프 + frame_id
├── height             uint32        세로 픽셀 수
├── width              uint32        가로 픽셀 수
├── encoding           string        "rgb8", "bgr8", "mono8", "16UC1" ...
├── is_bigendian       uint8         바이트 순서
├── step               uint32        한 행(row)의 바이트 수
└── data               uint8[]       실제 픽셀, 길이 = step * height
```

`step`이 왜 따로 있는지가 첫 함정이다. **`step`은 `width * 채널 수 * 픽셀당 바이트`와 같지 않을 수 있다.** 일부 카메라 드라이버나 압축 포맷은 각 행 끝에 정렬용 패딩을 붙인다. `data`를 `width`만 보고 잘라내면 이 패딩 때문에 이미지가 한 줄씩 밀려 보이는 버그가 난다. 뒤에서 이걸 코드로 직접 확인한다.

### PointCloud2 — LiDAR·깊이 카메라의 포인트클라우드

```text nolines
sensor_msgs/msg/PointCloud2
├── header             Header
├── height             uint32        정렬된(organized) 클라우드면 2D, 아니면 1
├── width              uint32        포인트 개수(height=1일 때) 또는 열 개수
├── fields             PointField[]  각 포인트 안의 필드 배치
├── is_bigendian       bool          바이트 순서
├── point_step         uint32        포인트 하나의 바이트 수
├── row_step           uint32        한 행의 바이트 수
├── data               uint8[]       실제 포인트 데이터
└── is_dense           bool          NaN/Inf 없는 유효 포인트만 있는가
```

여기서 헷갈리기 쉬운 점 하나. `Image.msg`의 `is_bigendian`은 `uint8`인데 `PointCloud2.msg`의 `is_bigendian`은 `bool`이다 — 같은 이름의 필드라도 메시지 타입마다 실제 타입이 다르다. `ros2/common_interfaces` 저장소의 `sensor_msgs/msg/Image.msg`와 `sensor_msgs/msg/PointCloud2.msg` 원본을 직접 대조하면 확인된다.

`fields`는 `PointField`의 배열이고, 각 원소가 "이 포인트 구조체 안에서 `x`가 몇 바이트째부터 시작하는지"를 알려준다.

```text nolines
sensor_msgs/msg/PointField
├── name       string   "x", "y", "z", "intensity", "rgb" ...
├── offset     uint32   포인트 시작점에서 이 필드까지의 바이트 오프셋
├── datatype   uint8    INT8=1 UINT8=2 INT16=3 UINT16=4
│                        INT32=5 UINT32=6 FLOAT32=7 FLOAT64=8
└── count      uint32   이 필드에 원소가 몇 개인가(보통 1)
```

이 구조가 낯설지 않을 것이다. **`point_step`은 NumPy 구조화 배열(structured array)의 `itemsize`고, `offset`은 그 안의 필드 오프셋이다.** 다음 절에서 그대로 재현한다.

### LaserScan — 2D LiDAR

```text nolines
sensor_msgs/msg/LaserScan
├── header             Header
├── angle_min          float32   시작 각도(rad)
├── angle_max          float32   끝 각도(rad)
├── angle_increment    float32   측정 사이 각도 간격(rad)
├── time_increment     float32   측정 사이 시간 간격(초)
├── scan_time          float32   한 바퀴 스캔에 걸린 시간(초)
├── range_min          float32   유효 최소 거리(m)
├── range_max          float32   유효 최대 거리(m)
├── ranges             float32[]  거리 값들(m)
└── intensities        float32[]  반사 강도(장비마다 단위 다름, 없으면 빈 배열)
```

`ranges[i]`에 대응하는 각도는 `angle_min + i * angle_increment`로 직접 계산해야 한다 — 메시지 어디에도 각도 배열 자체는 들어 있지 않다. 그리고 **`range_min`/`range_max` 밖의 값은 버려야 한다**는 게 스펙에 명시돼 있다. 필터링을 빼먹으면 벽 반사나 센서 노이즈로 인한 0.0이나 `inf`가 "진짜 장애물"로 둔갑한다.

### Imu — 관성 측정 장치

```text nolines
sensor_msgs/msg/Imu
├── header                            Header
├── orientation                       Quaternion   x,y,z,w
├── orientation_covariance            float64[9]   3x3 행렬(행 우선)
├── angular_velocity                  Vector3      rad/s
├── angular_velocity_covariance       float64[9]
├── linear_acceleration               Vector3      m/s^2
└── linear_acceleration_covariance    float64[9]
```

여기 숨어 있는 함정 하나. **공분산 행렬의 첫 원소가 `-1`이면, 그 필드 전체를 신뢰하지 말라는 뜻이다.** 저가 IMU는 방향(orientation) 추정을 자체적으로 못 해서 `orientation_covariance[0] = -1`을 채워 넣고 `orientation`은 0으로 둔 채 보낸다. 이 규약을 모르고 `orientation`을 그대로 갖다 쓰면, 항상 단위 쿼터니언(회전 없음)을 "정상적으로 측정된 방향"이라고 착각하게 된다.

## cv_bridge와 버퍼 프로토콜 — 이미지가 복사 없이 넘어오는 이유

`Image` 메시지의 `data`는 그냥 `uint8` 바이트 배열이다. 이걸 OpenCV로 처리하려면 `(height, width, channels)` 모양의 NumPy 배열이 필요하다. 이 변환을 해 주는 게 `cv_bridge` 패키지의 `CvBridge` 클래스다.

```python title="cv_bridge 사용 예 — 실제 문서 시그니처 확인 완료"
from cv_bridge import CvBridge

bridge = CvBridge()

# ROS Image 메시지 -> OpenCV/NumPy 배열
cv_image = bridge.imgmsg_to_cv2(img_msg, desired_encoding='passthrough')

# OpenCV/NumPy 배열 -> ROS Image 메시지
out_msg = bridge.cv2_to_imgmsg(cv_image, encoding='passthrough')
```

`imgmsg_to_cv2(img_msg, desired_encoding='passthrough')`와 `cv2_to_imgmsg(cvim, encoding='passthrough', header=None)`이 실제 시그니처다(ros-perception/vision_opencv, `cv_bridge/python/cv_bridge/core.py`, rolling 기준). `desired_encoding='passthrough'`는 "원본 인코딩 그대로 두고 아무 색공간 변환도 하지 마라"는 뜻이다.

여기서 [1.5 bytes](#/bytes) 마지막에 예고했던 것이 나온다. **`imgmsg_to_cv2`는 `msg.data`를 복사해서 새 배열을 만드는 게 아니다.** 내부적으로 `np.ndarray(shape=..., dtype=..., buffer=img_msg.data)`를 쓴다 — [1.5절](#/bytes)의 `memoryview`, [9.1 NumPy](#/numpy-basics)의 `ndarray`가 여기서 만나는 지점이다. `buffer=` 인자는 **버퍼 프로토콜을 구현한 아무 객체나 받아서, 그 메모리를 그대로 배열의 뼈대로 쓴다.** 새로 메모리를 할당하지 않는다.

이 핵심부만 rclpy 없이 그대로 재현하고 검증할 수 있다.

```python title="imgmsg_zerocopy.py — cv_bridge 핵심부 재현"
import numpy as np


def imgmsg_to_ndarray(height, width, step, channels, dtype, data):
    """cv_bridge.imgmsg_to_cv2 의 핵심부 축약.
    step(행 바이트 수)이 width*channels*itemsize 보다 크면(정렬 패딩)
    그 초과분을 잘라내야 하므로 그 경우에만 슬라이싱이 들어간다."""
    cols = step // dtype.itemsize // channels
    arr = np.ndarray(shape=(height, cols, channels), dtype=dtype, buffer=data)
    if cols == width:
        return arr                     # 슬라이싱 없이 원본 버퍼를 그대로 본다
    return arr[:, :width, :]           # 패딩이 있으면 뷰를 한 겹 더 씌운다


h, w, c = 2, 3, 3
data = bytearray(h * w * c)            # 패딩 없는 경우: step == w*c
img = imgmsg_to_ndarray(h, w, w * c, c, np.dtype(np.uint8), data)

img[0, 0] = [10, 20, 30]               # 배열에 쓴 값이 원본 bytearray에 그대로 반영되는가?
print(list(data[:9]))
print(img.base is data)
```

```pyrepl
[10, 20, 30, 0, 0, 0, 0, 0, 0]
True
```

(Python 3.14.5 기준 실측.) `img.base is data`가 `True`다 — 배열은 `data` bytearray의 **메모리를 그대로 빌린 창**일 뿐, 자기 데이터를 갖고 있지 않다. `img[0, 0] = [...]`로 쓴 값이 원본 `bytearray`에 그대로 나타난다.

::: perf 왜 복사 없음이 이 파이프라인에서 결정적인가
1920x1080 BGR 프레임은 프레임당 6,220,800바이트다. 30fps 카메라라면 초당 186MB가 흐른다. `imgmsg_to_cv2` 호출마다 이걸 복사한다면, 추론이나 필터링 이전에 이미 CPU가 메모리 복사만으로 상당한 시간을 쓴다. 반대로 뷰로만 넘기면 그 비용이 사실상 0이다. [1.5절의 실측](#/bytes)에서 본 "10MB vs 496바이트" 차이가 여기서 초당 수백 MB 규모로 반복된다.
:::

::: warn desired_encoding을 빼먹지 마라
`desired_encoding='passthrough'`는 원본 인코딩을 그대로 믿는다는 뜻이다. 카메라가 `bgr8`로 보내는데 OpenCV로 `rgb8`인 것처럼 처리하면(또는 그 반대), **에러 없이 빨강과 파랑 채널이 뒤바뀐 이미지**가 나온다. 색이 이상하다고 느껴지면 제일 먼저 `img_msg.encoding`을 실제로 찍어서 확인하라. 이건 실행이 되고 예외도 안 나기 때문에 오래 방치되는 버그 유형이다.
:::

## LiDAR 포인트클라우드를 NumPy로 다루기

`PointCloud2`의 `fields`(이름 + `offset` + `datatype`)와 `point_step`(포인트 하나의 바이트 수)을 알면, `data` 전체를 **NumPy 구조화 배열 하나로 통째로 해석**할 수 있다. 포인트 하나씩 파이썬 루프로 파싱하는 것과는 비교가 안 되게 빠르다.

`sensor_msgs_py.point_cloud2` 모듈의 `read_points(cloud, field_names=None, skip_nans=False, ...)`가 이 일을 대신해 주지만(ros2/common_interfaces, rolling 기준 시그니처), 내부에서 하는 일은 아래와 완전히 같다. `PointField.datatype`은 `INT8=1 UINT8=2 INT16=3 UINT16=4 INT32=5 UINT32=6 FLOAT32=7 FLOAT64=8`로 정의돼 있고, 이걸 NumPy dtype으로 그대로 옮기면 된다.

```python title="pointcloud_view.py — rclpy 없이 순수 배열 처리만"
import numpy as np

point_step = 16          # x, y, z, intensity 각 4바이트 float32
n_points = 3

# PointField[x(offset=0), y(offset=4), z(offset=8), intensity(offset=12)]
# 을 그대로 NumPy 구조화 dtype으로 옮긴 것
dtype = np.dtype({
    "names": ["x", "y", "z", "intensity"],
    "formats": [np.float32, np.float32, np.float32, np.float32],
    "offsets": [0, 4, 8, 12],
    "itemsize": point_step,
})

# 실제로는 msg.data(bytes/bytearray)가 이 자리에 들어온다
raw = bytearray(point_step * n_points)
src = np.zeros(n_points, dtype=dtype)
src["x"], src["y"], src["z"], src["intensity"] = (
    [1.0, 2.0, 3.0], [0.5, 0.5, 0.5], [0.0, 0.0, 0.0], [10.0, 20.0, 30.0],
)
raw[:] = src.tobytes()

cloud = np.frombuffer(raw, dtype=dtype)      # data 를 복사 없이 구조화 배열로
print(cloud)
print(cloud["x"])

raw[0:4] = np.float32(99.0).tobytes()        # 원본 버퍼를 직접 고쳐 본다
print(cloud["x"])                            # 뷰이므로 그대로 반영돼야 한다
```

```pyrepl
[(1., 0.5, 0., 10.) (2., 0.5, 0., 20.) (3., 0.5, 0., 30.)]
[1. 2. 3.]
[99.  2.  3.]
```

(Python 3.14.5 기준 실측.) `np.frombuffer`는 [1.5절 bytes-NumPy 연결](#/bytes)에서 본 그대로 **복사하지 않는다.** `raw`를 직접 고쳤더니 `cloud["x"]`가 즉시 바뀐 게 그 증거다. `x`, `y`, `z`만 뽑아 좌표 배열로 합치고 싶으면 `np.column_stack([cloud["x"], cloud["y"], cloud["z"]])`을 쓰면 되는데, 이건 세 개의 뷰를 하나로 합치는 연산이라 여기서는 새 메모리가 할당된다 — 뷰가 항상 공짜는 아니라는 걸 기억해 둬라. [9.3 NumPy 고급](#/numpy-advanced)에서 스트라이드와 함께 이 경계를 더 파고든다.

::: note height/width로 정렬 여부를 판단하라
`is_dense`가 `False`거나 `height > 1`이면 조직화된(organized) 클라우드다. 깊이 카메라가 흔히 이 형태로 보낸다 — 픽셀 위치와 3D 점이 1대1로 대응해서, 이미지 처리와 포인트클라우드 처리를 같은 인덱스로 오갈 수 있다. 반대로 회전형 LiDAR는 보통 `height=1`인 비정렬(unorganized) 리스트로 보낸다.
:::

## 여러 센서의 시간 동기화 — message_filters

카메라와 LiDAR를 동시에 구독해서 "이 프레임을 찍었을 때 저 거리 스캔이 뭐였나"를 알고 싶다면, 두 콜백이 각각 다른 시각에 따로 불린다는 문제부터 풀어야 한다. `message_filters` 패키지가 이 조합을 표준화해 준다.

```python title="sync_node.py — message_filters 로 카메라 + LiDAR 동기화"
import rclpy
from rclpy.node import Node
from message_filters import Subscriber, ApproximateTimeSynchronizer
from sensor_msgs.msg import Image, LaserScan


class SensorFusionNode(Node):
    def __init__(self):
        super().__init__('sensor_fusion')

        image_sub = Subscriber(self, Image, '/camera/image_raw')
        scan_sub = Subscriber(self, LaserScan, '/scan')

        self.sync = ApproximateTimeSynchronizer(
            [image_sub, scan_sub],
            queue_size=10,
            slop=0.05,          # 최대 50ms 어긋난 메시지끼리도 짝짓는다
        )
        self.sync.registerCallback(self.on_synced)

    def on_synced(self, image_msg, scan_msg):
        self.get_logger().info(
            f'동기화됨: image stamp={image_msg.header.stamp.sec}, '
            f'scan stamp={scan_msg.header.stamp.sec}'
        )
```

`Subscriber(node, msg_type, topic, qos_profile=...)`, `ApproximateTimeSynchronizer(fs, queue_size, slop, ...)`, 그리고 결과를 받는 `registerCallback(cb)`가 실제 시그니처다(ros2/message_filters, `src/message_filters/__init__.py`, rolling 기준). `TimeSynchronizer(fs, queue_size)`는 `slop` 없이 **타임스탬프가 정확히 일치**해야 짝짓는 엄격한 버전이고, 실전에서는 정확히 일치하는 경우가 거의 없어 `ApproximateTimeSynchronizer`를 훨씬 자주 쓴다.

::: danger 콜백이 한 번도 안 불린다면 QoS부터 의심하라
`message_filters.Subscriber`는 내부적으로 일반 `create_subscription`을 감싼 것뿐이다. 그래서 [10.8 QoS](#/qos)에서 배운 규칙이 그대로 적용된다. **발행자와 구독자의 QoS 프로파일(특히 신뢰성)이 호환되지 않으면, 어느 쪽도 에러를 내지 않고 그냥 아무것도 매칭되지 않는다.** 두 토픽 각각은 `ros2 topic echo`로 잘 나오는데 동기화 콜백만 침묵한다면, 코드 로직이 아니라 QoS 불일치일 확률이 높다.
:::

## 근사 시간 동기화 알고리즘을 직접 구현하고 검증한다

`ApproximateTimeSynchronizer`가 내부에서 하는 일은 rclpy 문서 수준에서는 "타임스탬프가 `slop` 이내로 가까운 메시지들을 짝짓는다"로만 설명된다. 그 알고리즘의 핵심 — **여러 개의 정렬된 타임스탬프 스트림에서, 서로 `slop` 이내로 가까운 조합을 그리디하게 찾아나가는 것** — 은 rclpy와 무관한 순수 파이썬 로직이고, 그대로 실행해서 검증할 수 있다. [7.3 투 포인터](#/two-pointers)에서 배운 "여러 포인터를 각자의 배열에서 전진시키며 조건을 맞추는" 패턴 그 자체다.

```python title="approx_sync.py — ApproximateTimeSynchronizer 핵심 로직 재현"
def approx_sync(streams, slop):
    """streams: {이름: [타임스탬프...]} (각 리스트는 오름차순 정렬됨)
    모든 스트림에서 하나씩 골라 (최댓값 - 최솟값) <= slop 인 조합을 그리디하게 찾는다."""
    names = list(streams.keys())
    idx = {name: 0 for name in names}
    matches = []

    def peek(name):
        i = idx[name]
        seq = streams[name]
        return seq[i] if i < len(seq) else None

    while all(peek(name) is not None for name in names):
        candidate = {name: peek(name) for name in names}
        lo, hi = min(candidate.values()), max(candidate.values())
        if hi - lo <= slop:
            matches.append(dict(candidate))
            for name in names:
                idx[name] += 1
        else:
            oldest = min(candidate, key=candidate.get)   # 가장 뒤처진 스트림만 전진
            idx[oldest] += 1

    return matches


camera = [0.000, 0.100, 0.200, 0.300, 0.400]
lidar = [0.012, 0.098, 0.205, 0.410]
imu = [0.003, 0.101, 0.198, 0.301, 0.399]

for m in approx_sync({"camera": camera, "lidar": lidar, "imu": imu}, slop=0.02):
    print(m)
```

```pyrepl
{'camera': 0.0, 'lidar': 0.012, 'imu': 0.003}
{'camera': 0.1, 'lidar': 0.098, 'imu': 0.101}
{'camera': 0.2, 'lidar': 0.205, 'imu': 0.198}
{'camera': 0.4, 'lidar': 0.41, 'imu': 0.399}
```

(Python 3.14.5 기준 실측.) 눈여겨볼 것은 **`camera=0.300`이 결과에 없다는 점**이다. 그 시각에 `slop=0.02` 이내로 가까운 `lidar`도 `imu`도 없었기 때문에 조용히 버려졌다. 실제 `ApproximateTimeSynchronizer`도 마찬가지다 — 짝을 못 찾은 메시지는 에러 없이 그냥 사라진다. "이미지는 매 프레임 잘 들어오는데 동기화 콜백은 가끔 안 불린다"는 현상은 버그가 아니라 **설계된 동작**이다. `slop`을 너무 좁게 잡으면 이런 드롭이 잦아지고, 너무 넓게 잡으면 실제로는 다른 순간의 데이터를 "같은 순간"이라고 우기게 된다.

::: cote 정렬된 여러 배열에서 근접 조합 찾기
이 문제는 "정렬된 배열 $k$개에서, 각 배열에서 하나씩 골라 그 최댓값과 최솟값의 차이를 최소화하는 조합을 찾아라"라는 코딩테스트 단골 유형과 뼈대가 같다. 흔히 최소 힙으로 "지금 가장 작은 원소가 있는 배열의 포인터만 전진시킨다"는 그리디로 푼다. 여기서는 스트림이 3~4개뿐이라 `min()`으로 충분하지만, 스트림이 많아지면 [7.8 힙](#/heap)으로 바꿔야 매 단계 $O(k)$가 $O(\log k)$로 줄어든다.
:::

::: deep 왜 그리디가 최적을 보장하는가
"가장 뒤처진 스트림만 전진시킨다"는 규칙이 왜 맞는가? 어떤 조합이 `slop`을 만족하지 못했다면, 그 원인은 항상 **가장 작은(가장 오래된) 값**이다 — 그 값이 나머지를 따라잡지 못해서 범위가 벌어진 것이기 때문이다. 그 값을 그대로 두고 다른 스트림을 전진시켜 봐야 범위는 더 벌어지거나 그대로다. 그러니 뒤처진 것만 미는 게 유일하게 범위를 줄일 수 있는 수다. 이건 `slop`을 만족하는 조합이 존재한다면 반드시 찾아낸다는 뜻이지, 전역적으로 "가장 좋은" 매칭(예: 오차 총합 최소화)을 보장하지는 않는다 — `ApproximateTimeSynchronizer`도 마찬가지로 그리디이지 최적화기가 아니다.
:::

## 실전 감각: 센서 파이프라인 디버깅이 어려운 이유

지금까지 배운 것을 실전 버그 세 가지로 정리한다. 전부 **예외 없이 조용히 틀린 값을 만든다**는 공통점이 있다.

1. **인코딩 불일치.** `bgr8`을 `rgb8`로 착각하면 색이 뒤집힌다. `imgmsg_to_cv2`는 `desired_encoding`을 신뢰할 뿐, 실제 카메라 인코딩과 다른지 검증해 주지 않는다.
2. **동기화 드롭.** 위에서 본 대로, `ApproximateTimeSynchronizer`의 `slop`을 못 맞추면 콜백이 조용히 덜 불린다. "가끔 융합 결과가 안 나온다"를 로직 버그로 오해하고 며칠을 낭비하기 쉽다. `ros2 topic hz`([10.15 rosbag, 디버깅, 성능](#/ros-debug))로 각 토픽의 실제 발행 주기부터 확인하고, 그 다음에 `slop`을 조정하라.
3. **공분산 -1 규약을 놓침.** IMU의 `orientation_covariance[0] == -1`을 확인하지 않고 `orientation`을 그대로 쓰면, 방향 추정이 아예 없는 센서에서 "항상 회전 없음"이라는 값을 실제 측정치처럼 다루게 된다.

세 경우 모두 코드는 정상 실행되고 에러 로그도 없다. **센서 데이터 버그의 대부분은 예외가 아니라 스펙을 안 읽어서 생긴다.** 이 절 앞부분의 메시지 필드 표를 다시 훑어보는 게, 어떤 디버거보다 빠른 해결책일 때가 많다.

## 요약

- `Image`/`PointCloud2`/`LaserScan`/`Imu`는 전부 "숫자 배열 + 그걸 해석하는 메타데이터"라는 같은 뼈대를 공유한다. 메타데이터를 무시하면 반드시 사고가 난다.
- `cv_bridge`의 `imgmsg_to_cv2`/`cv2_to_imgmsg`는 [버퍼 프로토콜](#/bytes) 위에서 동작한다. `np.ndarray(buffer=msg.data)`는 복사하지 않고, 이게 초당 수백 MB의 이미지 스트림을 감당하는 이유다.
- `PointCloud2`의 `point_step`/`offset`은 NumPy 구조화 배열의 `itemsize`/`offsets`와 정확히 대응한다. `np.frombuffer`로 포인트클라우드 전체를 한 번에 구조화 배열로 본다.
- `message_filters`의 `Subscriber` + `ApproximateTimeSynchronizer` + `registerCallback`이 여러 토픽을 시간으로 묶는 표준 도구다. QoS 불일치는 조용히 콜백을 죽인다.
- 근사 시간 동기화는 결국 [투 포인터](#/two-pointers) 그리디다 — "가장 뒤처진 스트림만 전진시킨다"는 단순한 규칙으로 $O(n)$에 짝을 찾고, 짝 없는 메시지는 조용히 버려진다.
- 센서 파이프라인 버그는 대부분 예외를 던지지 않는다. 인코딩, 동기화 드롭, 공분산 규약을 먼저 의심하라.

::: quiz 연습문제
1. `Image` 메시지의 `step`이 `width * 3`(bgr8 기준)보다 8바이트 크다. 이 절의 `imgmsg_to_ndarray` 함수를 그대로 써서 이런 패딩이 있는 경우를 처리하려면 어떤 분기를 타는지 설명하고, 실제로 패딩이 있는 예제 데이터를 만들어 실행해 확인하라.
2. `PointCloud2`의 `fields`에 `rgb`(FLOAT32, offset=12)가 추가로 있다고 하자. 이 절의 구조화 dtype 예제를 고쳐서 `rgb` 필드까지 읽어내는 코드를 작성하고 실행하라.
3. 이 절의 `approx_sync` 함수에서 `slop`을 0.005로 줄이면 몇 개의 조합이 살아남는지 예측한 뒤 실행해서 확인하라. 왜 그렇게 되는지 스트림별 타임스탬프로 설명하라.
4. `ApproximateTimeSynchronizer(fs, queue_size, slop)` 대신 `TimeSynchronizer(fs, queue_size)`를 썼다면, 카메라(30Hz)와 LiDAR(10Hz)를 동기화할 때 콜백이 몇 번이나 불릴지 이 절의 지식을 근거로 답하라.
5. IMU의 `orientation_covariance[0] == -1`인 상황에서, `orientation`을 그대로 TF에 발행하면 어떤 문제가 생기는지 설명하라. [10.9 TF2](#/tf2)의 프레임 트리 개념과 연결해서 답하라.
:::

**다음 절**: [10.13 Nav2 자율주행](#/nav2) — 이 절에서 다룬 센서 스트림이 SLAM과 코스트맵으로 들어가 실제 주행 경로가 되는 과정.
