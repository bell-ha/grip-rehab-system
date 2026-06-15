"""
audio_engine.py — 실시간 사인파 합성기

오른손 악력 → 주파수 (220~600 Hz, 로그 스케일 연속)
왼손 악력   → 볼륨

오디오 백엔드: aplay 스트리밍 (끊김 없는 연속 PCM 출력)
"""

import numpy as np
import subprocess
import threading

SAMPLE_RATE = 44100
CHUNK = 1024  # 약 23ms — Raspberry Pi에서 안정적인 스트리밍

# 볼륨 (왼손) 범위
VOL_MIN_KG = 0.5
VOL_MAX_KG = 15.0

# 주파수 (오른손) 범위 — 2.3 kg ≈ 220 Hz, 10 kg ≈ 600 Hz
FREQ_MIN_KG = 2.3
FREQ_MAX_KG = 10.0
MIN_FREQ = 220.0
MAX_FREQ = 600.0

# 하위 호환용 alias (renderer에서 사용)
MIN_KG = FREQ_MIN_KG
MAX_KG = FREQ_MAX_KG


def kg_to_freq(kg: float) -> float:
    """오른손 악력 → 주파수 (로그 스케일). 데드존 이하 0."""
    if kg < FREQ_MIN_KG:
        return 0.0
    ratio = min(1.0, (kg - FREQ_MIN_KG) / (FREQ_MAX_KG - FREQ_MIN_KG))
    return MIN_FREQ * (MAX_FREQ / MIN_FREQ) ** ratio


def kg_to_volume(kg: float) -> float:
    """왼손 악력 → 볼륨 (0.0~1.0)."""
    if kg < VOL_MIN_KG:
        return 0.0
    return min(1.0, (kg - VOL_MIN_KG) / (VOL_MAX_KG - VOL_MIN_KG))


class AudioEngine:
    """
    aplay에 S16_LE PCM을 파이프로 스트리밍.
    주파수/볼륨이 바뀌어도 스트림은 끊기지 않고 그냥 다음 청크부터 새 값 적용.
    """

    def __init__(self):
        self._freq    = 0.0
        self._volume  = 0.0
        self._lock    = threading.Lock()
        self._process = None
        self._running = False
        self._thread  = None

    def start(self):
        try:
            self._process = subprocess.Popen(
                ['aplay', '-r', str(SAMPLE_RATE), '-f', 'S16_LE', '-c', '1', '-'],
                stdin=subprocess.PIPE,
                bufsize=0,           # Python 버퍼링 없이 바로 커널 파이프로
                stderr=subprocess.DEVNULL,
            )
            self._running = True
            self._thread = threading.Thread(target=self._audio_loop, daemon=True)
            self._thread.start()
            print("[오디오] aplay 스트리밍 시작")
        except Exception as e:
            print(f"[오디오] 오류: {e} — 소리 없이 진행")

    def stop(self):
        self._running = False
        if self._process:
            try:
                self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=1.0)
            except Exception:
                pass

    def set(self, freq: float, volume: float):
        with self._lock:
            self._freq   = freq
            self._volume = max(0.0, min(1.0, volume))

    def _audio_loop(self):
        """끊김 없는 PCM 스트림 생성. 주파수/볼륨 변화도 위상을 유지한 채 적용."""
        import time
        phase = 0.0
        t_arr = np.arange(CHUNK, dtype=np.float64)
        chunk_dur = CHUNK / SAMPLE_RATE   # ≈ 5.8ms

        # 파이프 버퍼 누적 방지를 위한 타이밍 기준점
        next_write = time.monotonic()

        while self._running:
            with self._lock:
                freq   = self._freq
                volume = self._volume

            if freq <= 0 or volume < 0.001:
                data = bytes(CHUNK * 2)  # 무음: numpy 없이 빠르게
                phase = 0.0
            else:
                phase_inc = 2.0 * np.pi * freq / SAMPLE_RATE
                phases = phase + t_arr * phase_inc
                # 기본파 + 2배음 + 3배음 — 오르간 느낌
                wave = volume * (
                    0.60 * np.sin(phases) +
                    0.25 * np.sin(2.0 * phases) +
                    0.15 * np.sin(3.0 * phases)
                )
                data = (wave * 32767).astype(np.int16).tobytes()
                # 위상 누적 (2π 주기로 감싸 오버플로 방지)
                phase = (phase + CHUNK * phase_inc) % (2.0 * np.pi)

            try:
                self._process.stdin.write(data)
            except Exception:
                break

            # 청크 하나 재생 시간만큼 기다려서 파이프를 거의 비워둠
            # → 파이프 지연 ≈ 0, 총 지연 = ALSA 하드웨어 버퍼(~20ms)만 남음
            next_write += chunk_dur
            gap = next_write - time.monotonic()
            if gap > 0.001:
                time.sleep(gap)
            elif gap < -chunk_dur * 4:
                # 연산이 너무 느려 많이 뒤처진 경우 기준점 리셋
                next_write = time.monotonic()
