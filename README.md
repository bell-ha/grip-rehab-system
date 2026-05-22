# 악력 재활 시스템 (Grip Rehabilitation System)

HX711 로드셀 + Arduino를 활용한 양손 악력 측정 및 재활 훈련 시스템입니다.
실시간 신호 처리 파이프라인과 유한 상태 머신(FSM) 기반 게임 두 가지를 제공합니다.

---

## 주요 알고리즘

| 분류 | 내용 |
|------|------|
| 신호 처리 | 스파이크 필터 → 중간값 필터 → 이동평균 필터 → 데드존 |
| 상태 제어 | 유한 상태 머신 (IDLE / FILLING / ON_TARGET / OVER / POPPED) |
| 센서 캘리브레이션 | 영점(Tare) 측정 + 스케일 팩터 계산 |
| 통신 | UART 직렬 통신 (115200 baud), 포트 자동 감지 |
| 실시간 루프 | 60 Hz 고정 dt 게임 루프, 멀티스레딩 Producer-Consumer |

---

## 프로젝트 구조

```
grip-rehab-system/
├── measure/
│   └── main.py              # 로드셀 실시간 그래프 (matplotlib)
├── games/
│   ├── balloon_game/        # 풍선 키우기 — 목표 악력 유지 게임
│   │   ├── main.py          # 게임 루프 진입점
│   │   ├── sensor.py        # 신호 처리 파이프라인 + 센서 인터페이스
│   │   ├── game_logic.py    # FSM 기반 게임 상태 관리
│   │   ├── renderer.py      # Pygame 렌더링
│   │   └── calibrate.py     # HX711 캘리브레이션 도구 (Raspberry Pi 전용)
│   └── Whack-A-Mole/        # 두더지 잡기 — 반응속도 훈련 게임
│       ├── main.py
│       ├── sensor.py
│       ├── game_logic.py
│       └── renderer.py
├── models/
│   ├── Base_1.stl           # 센서 고정 베이스 3D 모델
│   └── HX711_Load_Cell--Foot.stl
└── requirements.txt
```

---

## 환경 설정

Python 3.10 이상이 설치되어 있어야 합니다.

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> 이후 실행할 때마다 가상환경 활성화 명령(`source venv/bin/activate` 또는 `venv\Scripts\activate`)을 먼저 실행하세요.

---

## 실행 방법

### 1. 실시간 로드셀 그래프 (`measure/`)

Arduino를 USB로 연결한 상태에서 실행합니다.

```bash
# macOS / Linux
cd measure && python3 main.py

# Windows
cd measure && python main.py
```

- 아두이노 포트를 자동 감지합니다.
- 5초간 영점 조절 후 실시간 그래프가 표시됩니다.
- **Arduino IDE 시리얼 모니터는 반드시 닫아야 합니다.** (포트 충돌)

---

### 2. 풍선 키우기 (`games/balloon_game/`)

목표 악력을 일정 시간 유지하는 재활 훈련 게임입니다.

```bash
cd games/balloon_game

# 키보드 시뮬레이션 (센서 없이 PC에서 테스트)
python3 main.py          # macOS / Linux
python  main.py          # Windows

# Arduino USB 센서 사용
python3 main.py --arduino

# Raspberry Pi HX711 센서 사용
python3 main.py --real
```

**키보드 조작 (Mock 모드)**

| 키 | 동작 |
|----|------|
| A | 왼손 악력 증가 |
| S | 왼손 악력 감소 |
| K | 오른손 악력 증가 |
| L | 오른손 악력 감소 |
| R | 게임 리셋 |
| ESC | 종료 |

**게임 규칙**
- 점선 풍선(목표 15 kg) 크기에 맞게 힘을 조절하세요.
- 목표 범위를 3초 유지하면 성공입니다.
- 22 kg 이상이면 풍선이 터집니다.
- 화면 하단 바에서 현재 힘의 위치를 실시간으로 확인할 수 있습니다.

---

### 3. 두더지 잡기 (`games/Whack-A-Mole/`)

두더지가 나타나면 해당 손으로 악력을 가해 잡는 반응속도 훈련 게임입니다.

```bash
cd games/Whack-A-Mole

# 키보드 시뮬레이션
python3 main.py          # macOS / Linux
python  main.py          # Windows

# Arduino USB 센서 사용
python3 main.py --real

# 포트 직접 지정
python3 main.py --real --port COM3          # Windows
python3 main.py --real --port /dev/cu.usbmodem141011  # macOS
```

**키보드 조작 (Mock 모드)**

| 키 | 동작 |
|----|------|
| A | 왼손 약한 악력 |
| S | 왼손 강한 악력 |
| K | 오른손 약한 악력 |
| L | 오른손 강한 악력 |
| SPACE | 게임 시작 |
| R | 재시작 |
| ESC / Q | 종료 |

---

## 하드웨어 연결

### 시스템 구성도

```
[로드셀 ×2]
    │
[HX711 ADC ×2]
    │ (GPIO)
[Arduino / Raspberry Pi]
    │ (USB UART 115200 baud)
[PC — Python 게임]
```

### Arduino → PC 시리얼 포맷

Arduino가 115200 baud로 아래 형식을 전송해야 합니다.

```
raw1,raw2\n
```

예) `12345,11890`

### Raspberry Pi HX711 배선 (BCM 핀 번호)

| 신호 | 왼손 | 오른손 |
|------|------|--------|
| DOUT | GPIO 5  | GPIO 13 |
| SCK  | GPIO 6  | GPIO 19 |
| VCC  | 3.3V    | 3.3V    |
| GND  | GND     | GND     |

---

## 센서 캘리브레이션 (Raspberry Pi)

```bash
cd games/balloon_game
python3 calibrate.py
```

1. 로드셀을 비운 상태에서 Enter → 영점(Tare) 측정
2. 알고 있는 무게(kg) 입력 후 Enter
3. 해당 무게를 올리고 Enter → 스케일 팩터 계산

`calibration.json`이 자동 생성됩니다.

---

## 3D 모델 (`models/`)

| 파일 | 설명 |
|------|------|
| `Base_1.stl` | 센서 고정 베이스 |
| `HX711_Load_Cell--Foot.stl` | 로드셀 발판 |

FDM 프린터로 출력 후 로드셀과 조립하세요.

---

## 문제 해결

**포트를 찾을 수 없을 때**

| OS | 포트 확인 방법 |
|----|----------------|
| Windows | 장치 관리자 → 포트(COM & LPT) 에서 `COM*` 번호 확인 |
| macOS | `ls /dev/cu.*` |
| Linux | `ls /dev/ttyUSB*` 또는 `ls /dev/ttyACM*` |

- 포트 확인 후 `--port` 옵션으로 직접 지정하세요.
- **Arduino IDE 시리얼 모니터가 열려 있으면 반드시 닫으세요.** (포트 충돌)

**Windows에서 `python3` 명령이 없을 때**

Windows는 `python3` 대신 `python`을 사용하세요.

```bat
python main.py --arduino
```

**pip install 오류 (macOS Homebrew Python)**

시스템 Python에 직접 설치하지 말고 반드시 가상환경을 사용하세요.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```






# 라즈베리 파이로 깃허브 파일 보내는 방법
```bash
scp -r /Users/jongha/Desktop/GitHub/grip-rehab-system doori@192.168.0.206:~/
```

# 라즈베리파이에서 파일 실행
```bash
export DISPLAY=:0
cd ~/grip-rehab-system/games/balloon_game
python3 main.py --arduino
```