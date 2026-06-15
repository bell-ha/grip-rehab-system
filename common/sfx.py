"""
common/sfx.py — 절차적 효과음 생성·재생

pygame.init() 이후에 sfx.init()을 한 번 호출하면 모든 효과음이 준비됩니다.
이후 sfx.play("이름") 으로 재생합니다.

효과음 목록:
    click       - UI 커서 이동 (짧은 틱)
    select      - UI 선택 확정 (올라가는 두 음)
    on_target   - 풍선: 목표 범위 진입 (부드러운 차임)
    success     - 풍선: 유지 성공 (밝은 딩!)
    pop         - 풍선: 펑 (노이즈 버스트)
    hit         - 두더지: 잡기 성공 (핑)
    miss        - 두더지: 놓침 (내려가는 음)
    appear      - 두더지: 등장 (chirp)
    combo       - 두더지: 콤보 (아르페지오)
    collision   - 우주선: 벽 충돌 (낮은 충격음)
    game_over   - 게임 오버 (내려가는 멜로디)
"""

import numpy as np
import pygame

_SR = 44100
_sounds: dict = {}


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(_SR * dur), endpoint=False)


def _exp_env(dur: float, tau: float = 10.0) -> np.ndarray:
    return np.exp(-tau * _t(dur))


def _sweep(f0: float, f1: float, dur: float) -> np.ndarray:
    """주파수가 f0→f1로 선형 변화하는 사인파"""
    t = _t(dur)
    freq = f0 + (f1 - f0) * t / dur
    phase = 2 * np.pi * np.cumsum(freq) / _SR
    return np.sin(phase)


def _to_sound(wave: np.ndarray) -> pygame.mixer.Sound:
    """float64 [-1, 1] 1D → pygame.mixer.Sound (스테레오 자동 대응)"""
    s16 = (np.clip(wave, -1.0, 1.0) * 32767).astype(np.int16)
    info = pygame.mixer.get_init()
    if info and info[2] == 2:          # 스테레오 믹서
        s16 = np.column_stack([s16, s16])
    return pygame.sndarray.make_sound(s16)


# ── 효과음 정의 ───────────────────────────────────────────────────────────────

def _click():
    """UI 커서 이동 - 매우 짧은 틱"""
    dur = 0.025
    return _sweep(1400, 1000, dur) * _exp_env(dur, 120) * 0.25


def _select():
    """UI 선택 확정 - 올라가는 두 음 (C5 → G5)"""
    w1 = np.sin(2 * np.pi * 523 * _t(0.14)) * _exp_env(0.14, 9) * 0.45
    w2 = np.sin(2 * np.pi * 784 * _t(0.22)) * _exp_env(0.22, 6) * 0.45
    return np.concatenate([w1, w2])


def _on_target():
    """풍선 목표 범위 진입 - 부드러운 차임"""
    dur = 0.20
    t = _t(dur)
    wave = (
        0.6 * np.sin(2 * np.pi * 660 * t) +
        0.4 * np.sin(2 * np.pi * 990 * t)
    ) * _exp_env(dur, 10)
    return wave * 0.35


def _success():
    """풍선 유지 성공 - 밝고 명쾌한 딩"""
    dur = 0.35
    t = _t(dur)
    wave = (
        0.5 * np.sin(2 * np.pi * 880 * t) +
        0.3 * np.sin(2 * np.pi * 1320 * t) +
        0.2 * np.sin(2 * np.pi * 1760 * t)
    ) * _exp_env(dur, 7)
    return wave * 0.5


def _pop():
    """풍선 펑 - 노이즈 버스트 + 저주파 충격"""
    dur = 0.30
    t = _t(dur)
    rng = np.random.default_rng(seed=1)
    noise = rng.uniform(-1.0, 1.0, len(t))
    low   = np.sin(2 * np.pi * 70 * t)
    wave  = (noise * 0.65 + low * 0.35) * np.exp(-t * 22)
    return wave * 0.75


def _hit():
    """두더지 잡기 성공 - 상승 스윕 핑"""
    dur = 0.18
    wave = _sweep(700, 1400, dur) * _exp_env(dur, 18)
    return wave * 0.5


def _miss():
    """두더지 놓침 - 내려가는 슬픈 두 음"""
    w1 = np.sin(2 * np.pi * 350 * _t(0.15)) * _exp_env(0.15, 10) * 0.4
    w2 = np.sin(2 * np.pi * 220 * _t(0.25)) * _exp_env(0.25,  6) * 0.4
    return np.concatenate([w1, w2])


def _appear():
    """두더지 등장 - 짧고 경쾌한 chirp"""
    dur = 0.09
    wave = _sweep(350, 700, dur) * _exp_env(dur, 30)
    return wave * 0.30


def _combo():
    """콤보 - 올라가는 아르페지오 (C5 E5 G5 C6)"""
    notes = [523, 659, 784, 1047]
    segs = []
    for i, f in enumerate(notes):
        d = 0.07
        seg = np.sin(2 * np.pi * f * _t(d)) * _exp_env(d, 30) * (0.3 + i * 0.05)
        segs.append(seg)
    return np.concatenate(segs)


def _collision():
    """우주선 벽 충돌 - 낮은 둔탁한 충격음"""
    dur = 0.40
    t = _t(dur)
    rng = np.random.default_rng(seed=2)
    noise = rng.uniform(-1.0, 1.0, len(t))
    low   = np.sin(2 * np.pi * 55 * t) + np.sin(2 * np.pi * 80 * t)
    wave  = (noise * 0.45 + low * 0.55) * np.exp(-t * 14)
    return wave * 0.65


def _game_over():
    """게임 오버 - 내려가는 멜로디 (C5 A4 F4 C4)"""
    notes = [523, 440, 349, 262]
    durs  = [0.18, 0.18, 0.18, 0.45]
    segs = []
    for f, d in zip(notes, durs):
        t = _t(d)
        seg = np.sin(2 * np.pi * f * t) * np.exp(-t * 5) * 0.4
        segs.append(seg)
    return np.concatenate(segs)


# ── 공개 API ─────────────────────────────────────────────────────────────────

_BUILDERS = {
    'click':     _click,
    'select':    _select,
    'on_target': _on_target,
    'success':   _success,
    'pop':       _pop,
    'hit':       _hit,
    'miss':      _miss,
    'appear':    _appear,
    'combo':     _combo,
    'collision': _collision,
    'game_over': _game_over,
}


def init():
    """pygame.init() 이후 한 번 호출. 모든 효과음을 미리 빌드합니다."""
    global _sounds
    if _sounds:
        return
    cur = pygame.mixer.get_init()
    if not cur or cur[0] != _SR:
        # pygame.init()이 기본값(22050Hz)으로 초기화했을 경우 재초기화
        if cur:
            pygame.mixer.quit()
        pygame.mixer.init(frequency=_SR, size=-16, channels=2, buffer=2048)
    for name, builder in _BUILDERS.items():
        try:
            _sounds[name] = _to_sound(builder())
        except Exception as e:
            print(f"[sfx] '{name}' 빌드 실패: {e}")


def play(name: str, volume: float = 1.0):
    """효과음 재생. init()가 먼저 호출되어 있어야 합니다."""
    sound = _sounds.get(name)
    if sound:
        sound.stop()   # 이전 인스턴스 종료 — 채널 누적으로 인한 클리핑 방지
        sound.set_volume(min(1.0, max(0.0, volume)))
        sound.play()
