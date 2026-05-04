"""
sensor.py — 두더지 잡기 악력 센서

MockGripSensor    : 키보드 시뮬레이션
    왼손  A(9kg) / S(15kg) — 키 누르는 동안 유지, 떼면 즉시 0
    오른손 K(9kg) / L(15kg)

RealGripSensor    : Arduino "L:x.xx,R:x.xx" 포맷 (Arduino가 kg로 변환해서 전송)
ArduinoGripSensor : Arduino "raw1,raw2" 포맷 — 자동 영점 + 스케일 캘리브레이션
"""

import threading
import time
from abc import ABC, abstractmethod

import pygame


class GripSensor(ABC):
    @abstractmethod
    def get_grip(self) -> tuple[float, float]: ...
    def close(self): pass


# ── Mock (키보드) ──────────────────────────────────────────────────────────────

class MockGripSensor(GripSensor):
    LIGHT  = 9.0    # A / K  — 임계값(6kg) 이상, 가볍게 잡기
    HEAVY  = 15.0   # S / L  — 세게 잡기 (콤보 획득에 유리)

    def __init__(self):
        self._left  = 0.0
        self._right = 0.0

    def update(self, keys):
        self._left  = self.HEAVY if keys[pygame.K_s] else (self.LIGHT if keys[pygame.K_a] else 0.0)
        self._right = self.HEAVY if keys[pygame.K_l] else (self.LIGHT if keys[pygame.K_k] else 0.0)

    def get_grip(self) -> tuple[float, float]:
        return self._left, self._right


# ── Real: Arduino → kg 변환 완료된 포맷 ───────────────────────────────────────

class RealGripSensor(GripSensor):
    """Arduino가 'L:12.34,R:8.56\\n' 포맷으로 전송하는 경우."""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        import serial
        self._ser     = serial.Serial(port, baudrate, timeout=1)
        self._left    = 0.0
        self._right   = 0.0
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("L:"):
                    parts        = line.split(",")
                    self._left   = max(0.0, float(parts[0][2:]))
                    self._right  = max(0.0, float(parts[1][2:]))
            except Exception:
                time.sleep(0.01)

    def get_grip(self) -> tuple[float, float]:
        return self._left, self._right

    def close(self):
        self._running = False
        self._ser.close()


# ── Arduino: raw ADC 포맷 — 자동 영점 + 최대악력 스케일 ──────────────────────

def _find_arduino_port() -> str:
    try:
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            if any(k in port.description.lower()
                   for k in ['arduino', 'usbmodem', 'usbserial', 'ch340', 'cp210']):
                return port.device
    except ImportError:
        raise RuntimeError("pyserial 없음. pip install pyserial")
    raise RuntimeError("아두이노를 찾을 수 없습니다. USB 연결을 확인하세요.")


class ArduinoGripSensor(GripSensor):
    """
    Arduino가 115200 baud로 'raw1,raw2\\n' 형식의 정수값을 전송해야 합니다.

    시작 시:
        1. 3초 영점(tare) — 아무것도 올리지 마세요
        2. 5초 최대악력 측정 — 최대한 세게 쥐어주세요 (자동 스케일)
    """
    BAUD       = 115200
    TARE_SECS  = 3
    CALIB_SECS = 5
    MAX_KG     = 30.0   # 스케일 기준 최대값 (kg)

    def __init__(self):
        self._port    = _find_arduino_port()
        self._left    = 0.0
        self._right   = 0.0
        self._tare_l  = 0.0
        self._tare_r  = 0.0
        self._scale_l = 1.0
        self._scale_r = 1.0
        self._running = False
        self._lock    = threading.Lock()
        self._thread: threading.Thread | None = None
        print(f"[Arduino] 감지됨: {self._port}")

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _read_raw(self, ser):
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if "," in line:
                parts = line.split(",")
                return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    def _do_tare(self, ser):
        print(f"[Arduino] 영점 조절 중 ({self.TARE_SECS}초)... 손 떼주세요!")
        buf_l, buf_r = [], []
        deadline = time.time() + self.TARE_SECS
        while time.time() < deadline:
            if ser.in_waiting:
                pair = self._read_raw(ser)
                if pair:
                    buf_l.append(pair[0]); buf_r.append(pair[1])
        self._tare_l = sum(buf_l) / len(buf_l) if buf_l else 0.0
        self._tare_r = sum(buf_r) / len(buf_r) if buf_r else 0.0
        print(f"[Arduino] 영점 완료: L={self._tare_l:.0f}  R={self._tare_r:.0f}")

    def _do_scale(self, ser):
        print(f"[Arduino] 최대악력 측정 ({self.CALIB_SECS}초)... 최대한 세게 쥐어주세요!")
        max_l = max_r = 0.0
        deadline = time.time() + self.CALIB_SECS
        while time.time() < deadline:
            if ser.in_waiting:
                pair = self._read_raw(ser)
                if pair:
                    max_l = max(max_l, abs(pair[0] - self._tare_l))
                    max_r = max(max_r, abs(pair[1] - self._tare_r))
        self._scale_l = max(max_l, 1.0) / self.MAX_KG
        self._scale_r = max(max_r, 1.0) / self.MAX_KG
        print(f"[Arduino] 스케일: L={self._scale_l:.2f}  R={self._scale_r:.2f}")

    def _loop(self):
        try:
            import serial
        except ImportError:
            print("[ERROR] pyserial 없음. pip install pyserial")
            return
        try:
            ser = serial.Serial(self._port, self.BAUD, timeout=1)
            time.sleep(2)
            self._do_tare(ser)
            self._do_scale(ser)
            print("[Arduino] 게임 시작!")
            while self._running:
                if ser.in_waiting:
                    pair = self._read_raw(ser)
                    if pair:
                        l = max(0.0, (pair[0] - self._tare_l) / self._scale_l)
                        r = max(0.0, (pair[1] - self._tare_r) / self._scale_r)
                        with self._lock:
                            self._left, self._right = l, r
                else:
                    time.sleep(0.005)
        except Exception as e:
            print(f"[ERROR] Arduino 오류: {e}")
        finally:
            try: ser.close()
            except Exception: pass

    def get_grip(self) -> tuple[float, float]:
        with self._lock:
            return self._left, self._right

    def close(self):
        self._running = False
