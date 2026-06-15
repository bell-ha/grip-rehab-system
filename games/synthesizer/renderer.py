"""
renderer.py — 악력 신디사이저 시각화 (연속 주파수)
"""

import pygame
import math
import os

from audio_engine import (
    MIN_KG, MAX_KG, MIN_FREQ, MAX_FREQ,
    kg_to_freq,
)

W, H = 800, 600

BG     = (8,   8,  18)
C_LEFT = (70, 140, 255)   # 왼손 - 파랑 (볼륨)
C_RIGHT= (255, 100,  50)  # 오른손 - 주황 (주파수)
C_NOTE = (255, 215,   0)  # 주파수 숫자 - 금색
C_WAVE = (0,  230, 160)   # 파형 - 민트
DIM    = (50,  50,  70)
DARK   = (18,  18,  32)
WHITE  = (220, 220, 230)

WAVE_CY = 78
WAVE_H  = 58


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    candidates = []
    if bold:
        candidates = [
            '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
            '/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf',
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        ]
    else:
        candidates = [
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        ]
    for path in candidates:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


class SynthRenderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._t = 0.0

        self.font_huge  = _load_font(96, bold=True)
        self.font_large = _load_font(36)
        self.font_mid   = _load_font(24)
        self.font_small = _load_font(18)

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def draw(self, left_kg: float, right_kg: float,
             freq: float, volume: float, dt: float):
        self._t += dt
        self.screen.fill(BG)

        self._draw_waveform(freq, volume)
        self._draw_volume_bar(left_kg, volume)
        self._draw_freq_bar(right_kg, freq)
        self._draw_center(freq)

    # ── 파형 ─────────────────────────────────────────────────────────────────

    def _draw_waveform(self, freq: float, volume: float):
        pygame.draw.line(self.screen, DIM, (0, 155), (W, 155), 1)

        if freq <= 0 or volume < 0.01:
            pygame.draw.line(self.screen, DIM, (0, WAVE_CY), (W, WAVE_CY), 1)
            return

        cycles = max(2.0, min(6.0, freq / 120.0))
        amp = int(WAVE_H * volume)
        pts = []
        for x in range(W):
            phase = self._t * 2 * math.pi * freq * 0.4 + x / W * cycles * 2 * math.pi
            pts.append((x, WAVE_CY - int(amp * math.sin(phase))))

        glow = tuple(int(c * 0.22) for c in C_WAVE)
        pygame.draw.lines(self.screen, glow,   False, pts, 7)
        pygame.draw.lines(self.screen, C_WAVE, False, pts, 2)

    # ── 볼륨 바 (왼쪽) ───────────────────────────────────────────────────────

    def _draw_volume_bar(self, left_kg: float, volume: float):
        x, y, bw, bh = 30, 180, 72, 260

        lbl = self.font_mid.render('볼륨', True, C_LEFT)
        self.screen.blit(lbl, (x + bw // 2 - lbl.get_width() // 2, y - 36))

        pygame.draw.rect(self.screen, DARK, (x, y, bw, bh), border_radius=8)
        fill_h = int(bh * volume)
        if fill_h > 0:
            pygame.draw.rect(self.screen, C_LEFT,
                             (x, y + bh - fill_h, bw, fill_h), border_radius=8)
        pygame.draw.rect(self.screen, C_LEFT, (x, y, bw, bh), 2, border_radius=8)

        cx = x + bw // 2
        for txt, col in [(f'{left_kg:.1f} kg', WHITE), (f'{int(volume * 100)}%', C_LEFT)]:
            s = self.font_small.render(txt, True, col)
            self.screen.blit(s, (cx - s.get_width() // 2,
                                 y + bh + 10 + (0 if col == WHITE else 22)))

    # ── 주파수 바 (오른쪽) ──────────────────────────────────────────────────

    def _draw_freq_bar(self, right_kg: float, freq: float):
        x, y, bw, bh = W - 120, 180, 90, 260

        lbl = self.font_mid.render('주파수', True, C_RIGHT)
        self.screen.blit(lbl, (x + bw // 2 - lbl.get_width() // 2, y - 36))

        pygame.draw.rect(self.screen, DARK, (x, y, bw, bh), border_radius=8)

        if right_kg >= MIN_KG:
            ratio = min(1.0, (right_kg - MIN_KG) / (MAX_KG - MIN_KG))
            fill_h = int(bh * ratio)
            if fill_h > 0:
                pygame.draw.rect(self.screen, C_RIGHT,
                                 (x, y + bh - fill_h, bw, fill_h), border_radius=8)

        pygame.draw.rect(self.screen, C_RIGHT, (x, y, bw, bh), 2, border_radius=8)

        cx = x + bw // 2
        for txt, col in [(f'{right_kg:.1f} kg', WHITE),
                         (f'{freq:.0f} Hz' if freq > 0 else '무음', C_RIGHT)]:
            s = self.font_small.render(txt, True, col)
            self.screen.blit(s, (cx - s.get_width() // 2,
                                 y + bh + 10 + (0 if col == WHITE else 22)))

    # ── 중앙 주파수 표시 ─────────────────────────────────────────────────────

    def _draw_center(self, freq: float):
        cx = W // 2
        if freq > 0:
            num_s = self.font_huge.render(f'{freq:.0f}', True, C_NOTE)
            hz_s  = self.font_large.render('Hz', True, WHITE)
            self.screen.blit(num_s, (cx - num_s.get_width() // 2, 188))
            self.screen.blit(hz_s,  (cx - hz_s.get_width()  // 2, 310))
        else:
            sil = self.font_large.render('무음', True, DIM)
            self.screen.blit(sil, (cx - sil.get_width() // 2, 240))
