"""
audio_engine.py — 실시간 사인파 합성기

오른손 악력 → 음 높이 (C4~C6, 검은건반 포함 25음)
왼손 악력   → 볼륨
"""

import numpy as np
import threading

SAMPLE_RATE = 44100
MIN_KG = 1.0
MAX_KG = 30.0

# C4 ~ C6 반음 25개
NOTE_LIST = [
    'C4','C#4','D4','D#4','E4','F4','F#4','G4','G#4','A4','A#4','B4',
    'C5','C#5','D5','D#5','E5','F5','F#5','G5','G#5','A5','A#5','B5',
    'C6',
]
NOTE_KR = [
    '도','도#','레','레#','미','파','파#','솔','솔#','라','라#','시',
    '도','도#','레','레#','미','파','파#','솔','솔#','라','라#','시',
    '도',
]
FREQS = [
    261.63, 277.18, 293.66, 311.13, 329.63,
    349.23, 369.99, 392.00, 415.30, 440.00, 466.16, 493.88,
    523.25, 554.37, 587.33, 622.25, 659.25,
    698.46, 739.99, 783.99, 830.61, 880.00, 932.33, 987.77,
    1046.50,
]
# True = 검은건반
IS_BLACK = [
    False, True, False, True, False, False, True, False, True, False, True, False,
    False, True, False, True, False, False, True, False, True, False, True, False,
    False,
]
N_NOTES = len(FREQS)

assert len(NOTE_LIST) == len(FREQS) == len(IS_BLACK) == len(NOTE_KR) == 25


def kg_to_freq(kg: float) -> float:
    """오른손 악력 → 주파수. 데드존 이하 0."""
    if kg < MIN_KG:
        return 0.0
    idx = int((kg - MIN_KG) / (MAX_KG - MIN_KG) * N_NOTES)
    return FREQS[min(idx, N_NOTES - 1)]


def kg_to_volume(kg: float) -> float:
    """왼손 악력 → 볼륨 (0.0~1.0)."""
    if kg < MIN_KG:
        return 0.0
    return min(1.0, (kg - MIN_KG) / (MAX_KG - MIN_KG))


def freq_to_index(freq: float) -> int:
    """주파수 → FREQS 인덱스. 없으면 -1."""
    try:
        return FREQS.index(freq)
    except ValueError:
        return -1


def freq_to_name(freq: float) -> tuple[str, str]:
    """주파수 → (한글이름, 영문이름). 예: ('파#', 'F#4')"""
    idx = freq_to_index(freq)
    if idx < 0:
        return '—', '—'
    return NOTE_KR[idx], NOTE_LIST[idx]


class AudioEngine:
    def __init__(self):
        self._freq   = 0.0
        self._volume = 0.0
        self._phase  = 0.0
        self._lock   = threading.Lock()
        self._stream = None

    def start(self):
        try:
            import sounddevice as sd
            self._stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocksize=512,
                callback=self._callback,
            )
            self._stream.start()
            print("[오디오] 초기화 완료")
        except Exception as e:
            print(f"[오디오] sounddevice 오류: {e} — 소리 없이 진행")

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    def set(self, freq: float, volume: float):
        with self._lock:
            self._freq   = freq
            self._volume = max(0.0, min(1.0, volume))

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            freq   = self._freq
            volume = self._volume

        if freq <= 0 or volume < 0.001:
            outdata[:] = 0
            self._phase = 0.0
            return

        phase_inc = 2.0 * np.pi * freq / SAMPLE_RATE
        phases = self._phase + np.arange(frames, dtype=np.float64) * phase_inc

        # 기본파 + 2배음 + 3배음 — 오르간 느낌
        wave = volume * (
            0.60 * np.sin(phases) +
            0.25 * np.sin(2.0 * phases) +
            0.15 * np.sin(3.0 * phases)
        )
        outdata[:, 0] = wave.astype(np.float32)
        self._phase = (self._phase + frames * phase_inc) % (2.0 * np.pi)
