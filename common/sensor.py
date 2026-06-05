"""
sensor.py
GripSensor 추상 인터페이스 + MockGripSensor / RealGripSensor / ArduinoGripSensor 구현

MockGripSensor    : PC 개발용 — 키보드(A/S 왼손, K/L 오른손)로 악력 시뮬레이션
RealGripSensor    : Raspberry Pi 실제 하드웨어용 (HX711 + 로드셀 GPIO)
ArduinoGripSensor : Arduino USB 시리얼용 — "raw1,raw2" 포맷 수신
"""

from __future__ import annotations
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field


# ── 설정 상수 ────────────────────────────────────────────────────────────────

SAMPLE_RATE_HZ   = 80      # HX711 80Hz 모드
DEADZONE_KG      = 1.0     # 1 kg 이하는 0으로 처리
SPIKE_THRESHOLD  = 8.0     # 이전 값 대비 8 kg 이상 급변 → 스파이크
MEDIAN_N         = 3       # 중간값 필터 윈도우
MOVING_AVG_N     = 5       # 이동평균 필터 윈도우
MOCK_STEP_KG     = 1.0     # Mock에서 키 1회 = 1 kg 변화량
MOCK_DECAY_HZ    = 8       # Mock에서 손 떼면 초당 감소량 (kg/s)


# ── 데이터 클래스 ─────────────────────────────────────────────────────────────

@dataclass
class GripReading:
    left_kg:  float = 0.0
    right_kg: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ── 필터 파이프라인 ───────────────────────────────────────────────────────────

class GripFilter:
    """스파이크 → 중간값 → 이동평균 → 데드존 파이프라인"""

    def __init__(self):
        self._raw_buf:  deque[float] = deque(maxlen=MEDIAN_N)
        self._avg_buf:  deque[float] = deque(maxlen=MOVING_AVG_N)
        self._prev: float = 0.0

    def process(self, raw: float) -> float:
        # 1. 스파이크 필터 — 급격한 상승만 차단 (하강은 정상 이완이므로 허용)
        if raw - self._prev > SPIKE_THRESHOLD:
            raw = self._prev
        self._prev = raw

        # 2. 중간값 필터
        self._raw_buf.append(raw)
        median = sorted(self._raw_buf)[len(self._raw_buf) // 2]

        # 3. 이동평균 필터
        self._avg_buf.append(median)
        avg = sum(self._avg_buf) / len(self._avg_buf)

        # 4. 데드존
        return 0.0 if avg < DEADZONE_KG else round(avg, 2)

    def reset(self):
        self._raw_buf.clear()
        self._avg_buf.clear()
        self._prev = 0.0


# ── 추상 인터페이스 ───────────────────────────────────────────────────────────

class GripSensor(ABC):

    def __init__(self):
        self._lock    = threading.Lock()
        self._reading = GripReading()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def get(self) -> GripReading:
        with self._lock:
            r = self._reading
        return GripReading(r.left_kg, r.right_kg, r.timestamp)

    def _set(self, left: float, right: float):
        with self._lock:
            self._reading = GripReading(left, right)

    @abstractmethod
    def _loop(self): ...


# ── Mock 구현 (PC 개발용) ─────────────────────────────────────────────────────

class MockGripSensor(GripSensor):
    """
    키보드 입력으로 악력 시뮬레이션.
    Pygame 이벤트 루프에서 handle_keydown / handle_keyup 을 호출하세요.

    왼손:  A 누르면 증가 / S 누르면 감소  (또는 A 누르고 있으면 유지)
    오른손: K 누르면 증가 / L 누르면 감소
    """

    def __init__(self):
        super().__init__()
        self._left_target:  float = 0.0
        self._right_target: float = 0.0
        self._left_held:    bool  = False
        self._right_held:   bool  = False
        self._filter_l = GripFilter()
        self._filter_r = GripFilter()

    # Pygame 이벤트에서 호출
    def handle_keydown(self, key: int):
        import pygame
        if key == pygame.K_a:
            self._left_target  = min(30.0, self._left_target  + MOCK_STEP_KG)
            self._left_held    = True
        elif key == pygame.K_s:
            self._left_target  = max(0.0,  self._left_target  - MOCK_STEP_KG)
        elif key == pygame.K_k:
            self._right_target = min(30.0, self._right_target + MOCK_STEP_KG)
            self._right_held   = True
        elif key == pygame.K_l:
            self._right_target = max(0.0,  self._right_target - MOCK_STEP_KG)

    def handle_keyup(self, key: int):
        import pygame
        if key == pygame.K_a:
            self._left_held  = False
        elif key == pygame.K_k:
            self._right_held = False

    def set_grip(self, left_kg: float, right_kg: float):
        """슬라이더 등 외부 입력으로 직접 지정할 때 사용"""
        self._left_target  = max(0.0, min(30.0, left_kg))
        self._right_target = max(0.0, min(30.0, right_kg))

    def _loop(self):
        interval = 1.0 / SAMPLE_RATE_HZ
        decay    = MOCK_DECAY_HZ / SAMPLE_RATE_HZ  # 한 틱당 감소량

        while self._running:
            # 손 떼면 자연 감소
            if not self._left_held:
                self._left_target  = max(0.0, self._left_target  - decay)
            if not self._right_held:
                self._right_target = max(0.0, self._right_target - decay)

            lf = self._filter_l.process(self._left_target)
            rf = self._filter_r.process(self._right_target)
            self._set(lf, rf)
            time.sleep(interval)


# ── Real 구현 (Raspberry Pi + HX711) ─────────────────────────────────────────

class RealGripSensor(GripSensor):
    """
    실제 하드웨어 구현.
    calibration.json 에서 scale_factor / tare_offset 을 읽어옵니다.

    calibration.json 예시:
    {
        "left":  {"scale_factor": 420.5, "tare_offset": -12300},
        "right": {"scale_factor": 415.2, "tare_offset": -11900}
    }
    """

    # GPIO 핀 번호 (BCM 기준)
    LEFT_DOUT  = 5;  LEFT_SCK  = 6
    RIGHT_DOUT = 13; RIGHT_SCK = 19

    def __init__(self, calib_path: str = "calibration.json"):
        super().__init__()
        self._calib_path = calib_path
        self._filter_l   = GripFilter()
        self._filter_r   = GripFilter()
        self._scale_l    = 1.0
        self._tare_l     = 0
        self._scale_r    = 1.0
        self._tare_r     = 0
        self._load_calibration()

    def _load_calibration(self):
        import json, os
        if not os.path.exists(self._calib_path):
            print(f"[WARN] {self._calib_path} 없음 — 캘리브레이션 필요")
            return
        with open(self._calib_path) as f:
            data = json.load(f)
        self._scale_l = data["left"]["scale_factor"]
        self._tare_l  = data["left"]["tare_offset"]
        self._scale_r = data["right"]["scale_factor"]
        self._tare_r  = data["right"]["tare_offset"]
        print("[INFO] 캘리브레이션 로드 완료")

    def _loop(self):
        try:
            from hx711 import HX711  # pip install hx711
        except ImportError:
            print("[ERROR] hx711 라이브러리 없음. pip install hx711")
            return

        hx_l = HX711(dout_pin=self.LEFT_DOUT,  pd_sck_pin=self.LEFT_SCK)
        hx_r = HX711(dout_pin=self.RIGHT_DOUT, pd_sck_pin=self.RIGHT_SCK)

        # 80Hz 모드 설정 (RATE 핀 HIGH)
        for hx in (hx_l, hx_r):
            hx.set_reading_format("MSB", "MSB")
            hx.set_reference_unit(1)
            hx.reset()
            hx.tare()

        interval = 1.0 / SAMPLE_RATE_HZ

        while self._running:
            try:
                raw_l = (hx_l.get_raw_data_mean(times=1) - self._tare_l) / self._scale_l
                raw_r = (hx_r.get_raw_data_mean(times=1) - self._tare_r) / self._scale_r
                lf = self._filter_l.process(max(0.0, raw_l))
                rf = self._filter_r.process(max(0.0, raw_r))
                self._set(lf, rf)
            except Exception as e:
                print(f"[WARN] 센서 읽기 오류: {e}")
            time.sleep(interval)


# ── Arduino 구현 (USB 시리얼) ──────────────────────────────────────────────────

def _find_arduino_port() -> str:
    """USB에서 아두이노 포트 자동 감지"""
    try:
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            if any(k in port.description.lower() for k in
                   ['arduino', 'usbmodem', 'usbserial', 'ch340', 'cp210']):
                return port.device
    except ImportError:
        raise RuntimeError("pyserial 없음. pip install pyserial")
    raise RuntimeError("아두이노를 찾을 수 없습니다. USB 연결을 확인하세요.")


class ArduinoGripSensor(GripSensor):
    """
    Arduino USB 시리얼 센서.
    아두이노가 115200 baud로 "raw1,raw2\\n" 형식의 정수값을 전송해야 합니다.

    시작 시 동작:
        1. 3초 영점(tare) 측정 — 아무것도 올려놓지 마세요
        2. 5초 최대악력 측정 — 최대한 세게 쥐어주세요 (자동 스케일)
    """

    BAUD_RATE  = 115200
    TARE_SECS  = 3
    CALIB_SECS = 5

    def __init__(self, port: str | None = None):
        super().__init__()
        self._filter_l   = GripFilter()
        self._filter_r   = GripFilter()
        self._tare_l     = 0.0
        self._tare_r     = 0.0
        self._scale_l    = 1.0
        self._scale_r    = 1.0
        self._calibrated = False
        self._port       = port or _find_arduino_port()
        print(f"[INFO] 아두이노 감지: {self._port}")
        self._load_calibration()

    def _load_calibration(self):
        import json, os
        calib_path = os.path.join(os.path.dirname(__file__), 'calibration.json')
        if not os.path.exists(calib_path):
            return
        with open(calib_path) as f:
            data = json.load(f)
        self._tare_l     = data['tare_l']
        self._tare_r     = data['tare_r']
        self._scale_l    = data['scale_l']
        self._scale_r    = data['scale_r']
        self._calibrated = True
        print(f"[INFO] 캘리브레이션 로드: L={self._tare_l:.0f}/{self._scale_l:.1f}  R={self._tare_r:.0f}/{self._scale_r:.1f}")

    def _read_raw(self, ser) -> tuple[int, int] | None:
        """시리얼에서 한 줄 읽어 (raw1, raw2) 반환. 실패 시 None."""
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if ',' in line:
                parts = line.split(',')
                return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    def _do_tare(self, ser):
        print(f"[INFO] 영점 조절 중 ({self.TARE_SECS}초)... 센서에서 손 떼주세요!")
        buf_l, buf_r = [], []
        deadline = time.time() + self.TARE_SECS
        while time.time() < deadline:
            if ser.in_waiting:
                pair = self._read_raw(ser)
                if pair:
                    buf_l.append(pair[0])
                    buf_r.append(pair[1])
        self._tare_l = sum(buf_l) / len(buf_l) if buf_l else 0.0
        self._tare_r = sum(buf_r) / len(buf_r) if buf_r else 0.0
        print(f"[INFO] 영점 완료: L={self._tare_l:.0f}  R={self._tare_r:.0f}")

    def _do_scale_calib(self, ser, pop_kg: float):
        print(f"[INFO] 최대악력 측정 ({self.CALIB_SECS}초)... 최대한 세게 쥐어주세요!")
        max_l, max_r = 0.0, 0.0
        deadline = time.time() + self.CALIB_SECS
        while time.time() < deadline:
            if ser.in_waiting:
                pair = self._read_raw(ser)
                if pair:
                    max_l = max(max_l, abs(pair[0] - self._tare_l))
                    max_r = max(max_r, abs(pair[1] - self._tare_r))
        # 최대값이 pop_kg에 대응하도록 스케일 설정
        self._scale_l = max(max_l, 1.0) / pop_kg
        self._scale_r = max(max_r, 1.0) / pop_kg
        print(f"[INFO] 스케일 설정: L={self._scale_l:.1f}  R={self._scale_r:.1f}")

    def _loop(self):
        try:
            import serial
        except ImportError:
            print("[ERROR] pyserial 없음. pip install pyserial")
            return

        try:
            ser = serial.Serial(self._port, self.BAUD_RATE, timeout=1)
            time.sleep(2)           # 아두이노 부팅 대기
            if self._calibrated:
                print("[INFO] 저장된 캘리브레이션 사용 — 초기화 단계 건너뜀")
            else:
                self._do_tare(ser)
                self._do_scale_calib(ser, pop_kg=22.0)
            print("[INFO] 게임 시작!")

            interval = 1.0 / SAMPLE_RATE_HZ
            while self._running:
                if ser.in_waiting:
                    pair = self._read_raw(ser)
                    if pair:
                        raw_l = (pair[0] - self._tare_l) / self._scale_l
                        raw_r = (pair[1] - self._tare_r) / self._scale_r
                        lf = self._filter_l.process(max(0.0, raw_l))
                        rf = self._filter_r.process(max(0.0, raw_r))
                        self._set(lf, rf)
                else:
                    time.sleep(interval)
        except Exception as e:
            print(f"[ERROR] 아두이노 오류: {e}")
        finally:
            try:
                ser.close()
            except Exception:
                pass
