# 풍선 키우기 — 악력 재활 게임

## 파일 구조

```
balloon_game/
├── main.py          # 진입점 — 게임 루프
├── sensor.py        # GripSensor 인터페이스 + Mock/Real 구현
├── game_logic.py    # 상태 머신 + 게임 규칙
├── renderer.py      # Pygame 렌더링 (게임 로직과 분리)
├── calibrate.py     # HX711 캘리브레이션 도구 (Pi 전용)
└── calibration.json # 캘리브레이션 결과 (calibrate.py 실행 후 생성)
```

## PC 개발 환경 실행

```bash
pip install pygame
python main.py
```

### 키보드 조작 (Mock 모드)

| 키 | 동작 |
|----|------|
| A  | 왼손 악력 증가 (+1 kg) |
| S  | 왼손 악력 감소 (-1 kg) |
| K  | 오른손 악력 증가 (+1 kg) |
| L  | 오른손 악력 감소 (-1 kg) |
| R  | 게임 리셋 |
| ESC | 종료 |

> A / K 를 누르고 있으면 유지, 손을 떼면 자연 감소합니다.

## Raspberry Pi 실행

### 1. 의존성 설치

```bash
pip install pygame hx711
```

### 2. 캘리브레이션

```bash
python calibrate.py
```

절차:
1. 아무것도 올리지 않은 상태 → Enter (영점)
2. 알고 있는 무게 입력 (예: 2.0)
3. 해당 무게를 로드셀에 올리고 Enter

`calibration.json` 이 생성됩니다.

### 3. 게임 실행

```bash
python main.py --real
```

## GPIO 핀 배선 (BCM 기준)

| 신호 | 왼손 | 오른손 |
|------|------|--------|
| DOUT | GPIO 5  | GPIO 13 |
| SCK  | GPIO 6  | GPIO 19 |
| VCC  | 3.3V    | 3.3V    |
| GND  | GND     | GND     |

## 게임 설정 변경

`main.py` 상단의 `CONFIG` 를 수정하세요:

```python
CONFIG = GameConfig(
    target_kg    = 15.0,   # 목표 악력 (kg)
    pop_kg       = 22.0,   # 펑 임계값 (kg)
    tolerance_kg = 1.5,    # 목표 ± 허용 범위
    success_sec  = 3.0,    # 성공 인정 유지 시간 (초)
    pop_reset_sec= 1.5,    # 펑 후 리셋 대기 (초)
)
```

## systemd 자동 실행 (Pi 부팅 시 자동 시작)

`/etc/systemd/system/balloon-game.service` 생성:

```ini
[Unit]
Description=Balloon Grip Game
After=graphical.target

[Service]
User=pi
Environment=DISPLAY=:0
WorkingDirectory=/home/pi/balloon_game
ExecStart=/usr/bin/python3 /home/pi/balloon_game/main.py --real
Restart=on-failure

[Install]
WantedBy=graphical.target
```

```bash
sudo systemctl enable balloon-game
sudo systemctl start balloon-game
```
