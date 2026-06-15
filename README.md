# 악력 재활 시스템 (Grip Rehabilitation System)

HX711 로드셀 + Arduino를 활용한 **양손 악력 측정 및 재활 훈련 시스템**입니다.
실시간 신호 처리 파이프라인과 4가지 악력 기반 게임 및 신디사이저를 제공합니다.

---

## 주요 특징

| 분류 | 내용 |
|------|------|
| 신호 처리 | 스파이크 필터 → 중간값 필터 → 이동평균 필터 → 데드존 |
| 센서 캘리브레이션 | 영점(Tare) 측정 + 스케일 팩터 자동 계산 (`calibration.json`) |
| 통신 | UART 직렬 통신 115200 baud, Arduino 포트 자동 감지 |
| 진동 피드백 | Arduino 진동 액츄에이터 (L1/L0/R1/R0 명령 프로토콜) |
| 게임 루프 | 60 Hz 고정 dt, 멀티스레딩 Producer-Consumer |
| 오디오 피드백 | 절차적 효과음(numpy 합성) + 실시간 신디사이저(aplay 스트리밍) |

---

## 프로젝트 구조

```
grip-rehab-system/
├── sketch_jun11a.ino        # Arduino 펌웨어 (HX711 읽기 + 진동 제어)
├── common/
│   ├── sensor.py            # 센서 인터페이스 (Mock / Arduino / RealGrip)
│   ├── sfx.py               # 절차적 효과음 생성·재생
│   └── fonts.py             # 공통 폰트 로더
├── games/
│   ├── launcher.py          # 게임 선택 런처 (메인 진입점)
│   ├── balloon_game/        # 풍선 키우기 — 목표 악력 유지
│   │   ├── main.py
│   │   ├── game_logic.py
│   │   ├── renderer.py
│   │   └── calibrate.py     # HX711 캘리브레이션 도구
│   ├── Whack-A-Mole/        # 두더지 잡기 — 반응속도 훈련
│   │   ├── main.py
│   │   ├── game_logic.py
│   │   └── renderer.py
│   ├── steering_game/       # 우주 조종 — 양손 힘 차이로 방향 제어
│   │   ├── main.py
│   │   ├── game_logic.py
│   │   └── renderer.py
│   └── synthesizer/         # 악력 신디사이저 — 악력으로 음악 연주
│       ├── main.py
│       ├── audio_engine.py  # aplay 실시간 PCM 스트리밍
│       └── renderer.py
├── measure/
│   └── main.py              # 시리얼 모니터 + 진동 수동 제어 (디버그용)
├── models/
│   ├── Base_1.stl           # 센서 고정 베이스 3D 모델
│   └── HX711_Load_Cell--Foot.stl
└── requirements.txt
```

---

## 환경 설정

Python 3.10 이상 필요.

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Raspberry Pi에서 HX711 직결 사용 시 추가 설치:

```bash
sudo apt-get install python3-dev alsa-utils
pip install hx711
```

---

## 하드웨어 연결

### 시스템 구성도

```
[로드셀 ×2]
    │
[HX711 ADC ×2]
    │ (Digital I/O)
[Arduino Uno]
    │ (USB UART 115200 baud)
[Raspberry Pi / PC — Python 게임]
```

### Arduino 핀 배선

| 신호 | 왼손 | 오른손 |
|------|------|--------|
| HX711 DOUT | D2 | D4 |
| HX711 SCK  | D3 | D5 |
| 진동 액츄에이터 | D9 (PWM) | D10 (PWM) |

### Arduino ↔ PC 시리얼 프로토콜

**Arduino → PC** (10ms 주기):
```
left_raw,right_raw\n
```
예) `285400,291820`

**PC → Arduino** (진동 명령):
```
L1\n  왼쪽 진동 ON
L0\n  왼쪽 진동 OFF
R1\n  오른쪽 진동 ON
R0\n  오른쪽 진동 OFF
```

### Raspberry Pi HX711 직결 배선 (BCM 핀)

| 신호 | 왼손 | 오른손 |
|------|------|--------|
| DOUT | GPIO 5  | GPIO 13 |
| SCK  | GPIO 6  | GPIO 19 |

---

## 실행 방법

### 런처 (Raspberry Pi 권장)

4가지 게임을 악력으로 선택·실행하는 메인 화면입니다.

```bash
cd games
DISPLAY=:0 python3 launcher.py --arduino   # Arduino USB
DISPLAY=:0 python3 launcher.py --real      # Pi HX711 직결
```

**조작법**

| 입력 | 동작 |
|------|------|
| 왼손 0.3초 유지 | 커서 왼쪽 이동 |
| 오른손 0.3초 유지 | 커서 오른쪽 이동 |
| 양손 0.3초 유지 | 선택 실행 |

---

### 게임별 직접 실행

모든 게임은 아래 세 가지 모드로 실행할 수 있습니다.

```bash
python3 main.py            # Mock 모드 (키보드, 센서 없이 테스트)
python3 main.py --arduino  # Arduino USB 자동 감지
python3 main.py --real     # Raspberry Pi HX711 직결
```

**공통 종료 제스처**: 양손을 동시에 2초 이내 2번 힘껏 쥐면 (더블 펌프) 게임을 종료하고 런처로 돌아갑니다.

**Mock 모드 키보드 조작**

| 키 | 동작 |
|----|------|
| A | 왼손 악력 증가 |
| S | 왼손 악력 감소 (손 뗌) |
| K | 오른손 악력 증가 |
| L | 오른손 악력 감소 (손 뗌) |
| R | 게임 재시작 |
| ESC / Q | 종료 |

---

### 1. 풍선 키우기 (`games/balloon_game/`)

목표 악력을 일정 시간 유지해 풍선을 최대한 키우는 게임입니다.

```bash
cd games/balloon_game && python3 main.py --arduino
```

- 점선 풍선(목표 약 15 kg)에 맞게 힘을 조절하세요.
- 목표 범위를 3초 유지하면 성공, 22 kg 이상이면 풍선이 터집니다.

---

### 2. 두더지 잡기 (`games/Whack-A-Mole/`)

두더지가 나타나면 해당 손으로 악력을 가해 잡는 반응속도 훈련 게임입니다.

```bash
cd games/Whack-A-Mole && python3 main.py --arduino
```

- 왼쪽 두더지 → 왼손, 오른쪽 두더지 → 오른손으로 잡으세요.
- 잡으면 진동 피드백이 옵니다.
- 콤보를 이어가면 보너스 점수를 얻습니다.

---

### 3. 우주 조종 (`games/steering_game/`)

두 손의 악력 **차이**로 우주선을 조종해 터널을 통과하는 게임입니다.

```bash
cd games/steering_game && python3 main.py --arduino
```

- 오른손 세게 → 오른쪽 이동, 왼손 세게 → 왼쪽 이동.
- 시간이 지날수록 터널이 좁아집니다. 60초 생존이 목표.
- 목숨 3개, 벽 충돌 시 진동 피드백.

---

### 4. 악력 신디사이저 (`games/synthesizer/`)

두 손의 악력으로 실시간 음악을 연주합니다.

```bash
cd games/synthesizer && python3 main.py --arduino
```

| 손 | 역할 | 범위 |
|----|------|------|
| 왼손 | 볼륨 | 0.5 ~ 15 kg |
| 오른손 | 주파수 (로그 스케일) | 2.3 kg → 220 Hz ~ 10 kg → 600 Hz |

- 기본파 + 2배음 + 3배음 합성으로 오르간 느낌의 소리를 냅니다.
- Linux(Raspberry Pi)에서는 `aplay`로 끊김 없는 PCM 스트리밍.

---

## 센서 캘리브레이션

### Arduino (USB) — 자동 캘리브레이션

`ArduinoGripSensor` 초기 실행 시 자동으로 진행됩니다.

1. **영점 조절 (3초)** — 센서에서 손을 떼세요.
2. **최대 악력 측정 (5초)** — 최대한 세게 쥐어주세요.
3. 결과가 `common/calibration.json`에 저장됩니다. 다음 실행부터는 이 파일을 사용합니다.

### Raspberry Pi (HX711 직결) — 수동 캘리브레이션

```bash
cd games/balloon_game
python3 calibrate.py
```

1. 로드셀을 비운 상태에서 Enter → 영점(Tare) 측정.
2. 알고 있는 무게(kg)를 입력 후 Enter.
3. 해당 무게를 올리고 Enter → 스케일 팩터 계산.
4. `calibration.json` 자동 생성.

---

## 3D 모델 (`models/`)

| 파일 | 설명 |
|------|------|
| `Base_1.stl` | 센서 고정 베이스 |
| `HX711_Load_Cell--Foot.stl` | 로드셀 발판 |

FDM 프린터로 출력 후 로드셀과 조립하세요.

---

## 디버그 도구

### 시리얼 모니터 (`measure/main.py`)

Arduino 연결 상태를 확인하고 진동 모터를 수동으로 제어합니다.

```bash
python3 measure/main.py
```

실행 후 터미널에서:
- `1` / `2` : 왼쪽 진동 ON / OFF
- `3` / `4` : 오른쪽 진동 ON / OFF
- `q` : 종료

> 포트가 `/dev/cu.usbmodem141011`로 하드코딩되어 있으니 필요 시 수정하세요.

---

## Raspberry Pi 배포

로컬 코드를 Pi로 전송:

```bash
scp -r /Users/jongha/Desktop/GitHub/grip-rehab-system doori@192.168.0.206:~/
```

Pi에서 런처 실행:

```bash
export DISPLAY=:0
cd ~/grip-rehab-system/games
python3 launcher.py --arduino
```

---

## 문제 해결

**포트를 찾을 수 없을 때**

| OS | 포트 확인 |
|----|-----------|
| macOS | `ls /dev/cu.*` |
| Linux | `ls /dev/ttyUSB*` 또는 `ls /dev/ttyACM*` |
| Windows | 장치 관리자 → 포트(COM & LPT) |

- Arduino IDE 시리얼 모니터가 열려 있으면 반드시 닫으세요. (포트 충돌)

**오른손 신호가 안 들어올 때**

1. 진동 모터를 분리한 상태에서 테스트 — 모터가 전원을 과소비하는 경우.
2. Arduino IDE 시리얼 모니터로 `left_raw,right_raw` 출력 확인.
3. 진동 모터는 GPIO 핀에 직결하지 말고 NPN 트랜지스터(2N2222)를 통해 구동하세요.

**신디사이저 소리가 안 날 때**

```bash
# Linux — aplay 설치 확인
aplay --version
sudo apt-get install alsa-utils
```

**Windows에서 `python3`가 없을 때**

```bat
python main.py --arduino
```
