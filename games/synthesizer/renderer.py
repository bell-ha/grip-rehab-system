"""
renderer.py — 악력 신디사이저 시각화 (2옥타브 + 검은건반)
"""

import pygame
import math

from audio_engine import (
    NOTE_KR, NOTE_LIST, FREQS, IS_BLACK,
    freq_to_name, freq_to_index,
    MIN_KG, MAX_KG, N_NOTES,
)

W, H = 800, 600

BG       = (8,   8,  18)
C_LEFT   = (70, 140, 255)    # 왼손 - 파랑 (볼륨)
C_RIGHT  = (255, 100,  50)   # 오른손 - 주황 (음정)
C_NOTE   = (255, 215,   0)   # 현재 음 - 금색
C_WAVE   = (0,  230, 160)    # 파형 - 민트
DIM      = (50,  50,  70)
DARK     = (18,  18,  32)
WHITE    = (220, 220, 230)
BLACK_K  = (20,  20,  30)    # 검은건반 색

WAVE_CY = 78
WAVE_H  = 58

# 피아노 흰건반 순서 및 검은건반 위치
# octave semitone → 흰건반 index: C=0,D=1,E=2,F=3,G=4,A=5,B=6
_SEMITONE_TO_WHITE = {0:0,2:1,4:2,5:3,7:4,9:5,11:6}
# 검은건반은 왼쪽 흰건반 오른쪽에 위치 (semitone → 앞 흰건반 index)
_BLACK_AFTER_WHITE = {1:0, 3:1, 6:3, 8:4, 10:5}


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ['AppleGothic', 'Malgun Gothic', 'NanumGothic', '나눔고딕', None]:
        try:
            if name:
                f = pygame.font.SysFont(name, size, bold=bold)
            else:
                f = pygame.font.Font(None, size)
            f.render('가', True, (255, 255, 255))   # 한글 렌더 테스트
            return f
        except Exception:
            continue
    return pygame.font.Font(None, size)


class SynthRenderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._t = 0.0

        self.font_huge  = _load_font(96, bold=True)
        self.font_large = _load_font(36)
        self.font_mid   = _load_font(24)
        self.font_small = _load_font(18)

        # 피아노 레이아웃 미리 계산
        self._piano_rects = self._build_piano_rects()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def draw(self, left_kg: float, right_kg: float,
             freq: float, volume: float, dt: float):
        self._t += dt
        self.screen.fill(BG)

        self._draw_waveform(freq, volume)
        self._draw_volume_bar(left_kg, volume)
        self._draw_note_indicator(right_kg)
        self._draw_center(freq)
        self._draw_piano(freq)

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
        for lbl_txt, col in [(f'{left_kg:.1f} kg', WHITE),
                              (f'{int(volume * 100)}%', C_LEFT)]:
            s = self.font_small.render(lbl_txt, True, col)
            self.screen.blit(s, (cx - s.get_width() // 2, y + bh + 10 + (WHITE == col and 0 or 22)))

    # ── 음정 인디케이터 (오른쪽) ──────────────────────────────────────────────

    def _draw_note_indicator(self, right_kg: float):
        """세로 슬라이더로 현재 음 위치 + 음이름 목록 표시."""
        x, y, bw, bh = W - 120, 180, 90, 260

        lbl = self.font_mid.render('음정', True, C_RIGHT)
        self.screen.blit(lbl, (x + bw // 2 - lbl.get_width() // 2, y - 36))

        # 배경 트랙
        pygame.draw.rect(self.screen, DARK, (x + bw // 2 - 8, y, 16, bh), border_radius=4)

        # 현재 위치 점
        if right_kg >= MIN_KG:
            ratio = (right_kg - MIN_KG) / (MAX_KG - MIN_KG)
            dot_y = y + int(bh * (1.0 - ratio))
            pygame.draw.circle(self.screen, C_RIGHT, (x + bw // 2, dot_y), 10)
            pygame.draw.circle(self.screen, WHITE,   (x + bw // 2, dot_y), 10, 2)

            # 현재 음 인덱스
            idx = min(int(ratio * N_NOTES), N_NOTES - 1)
            note_kr, note_en = NOTE_KR[idx], NOTE_LIST[idx]
            is_blk = IS_BLACK[idx]

            kr_s  = self.font_mid.render(note_kr, True, C_NOTE if not is_blk else (200, 180, 255))
            en_s  = self.font_small.render(note_en, True, DIM)
            self.screen.blit(kr_s, (x + bw // 2 - kr_s.get_width() // 2, y + bh + 12))
            self.screen.blit(en_s, (x + bw // 2 - en_s.get_width() // 2, y + bh + 34))
        else:
            sil = self.font_small.render('무음', True, DIM)
            self.screen.blit(sil, (x + bw // 2 - sil.get_width() // 2, y + bh + 12))

        kg_s = self.font_small.render(f'{right_kg:.1f} kg', True, WHITE)
        self.screen.blit(kg_s, (x + bw // 2 - kg_s.get_width() // 2, y + bh + 56))

    # ── 중앙 음이름 ───────────────────────────────────────────────────────────

    def _draw_center(self, freq: float):
        cx = W // 2
        kr_name, en_name = freq_to_name(freq)
        idx = freq_to_index(freq)
        is_blk = IS_BLACK[idx] if idx >= 0 else False

        col = (200, 180, 255) if is_blk else (C_NOTE if freq > 0 else DIM)
        note_s = self.font_huge.render(kr_name, True, col)
        self.screen.blit(note_s, (cx - note_s.get_width() // 2, 188))

        en_s = self.font_large.render(en_name if freq > 0 else '—', True,
                                      WHITE if freq > 0 else DIM)
        self.screen.blit(en_s, (cx - en_s.get_width() // 2, 310))

        if freq > 0:
            hz_s = self.font_mid.render(f'{freq:.2f} Hz', True, DIM)
            self.screen.blit(hz_s, (cx - hz_s.get_width() // 2, 355))

    # ── 피아노 (2옥타브 + 검은건반) ───────────────────────────────────────────

    def _build_piano_rects(self):
        """각 음의 pygame.Rect 미리 계산."""
        piano_y    = H - 118
        white_h    = 108
        black_h    = 66
        start_x    = 20
        total_w    = W - 40

        # 흰건반 15개 (C4~B5 = 14, + C6 = 15)
        n_white = 15
        wk_w    = total_w // n_white

        # FREQS 인덱스 → Rect 매핑
        rects = {}

        # 흰건반 먼저
        white_idx = 0
        for i, (freq, black) in enumerate(zip(FREQS, IS_BLACK)):
            if not black:
                rx = start_x + white_idx * wk_w
                rects[i] = pygame.Rect(rx + 1, piano_y, wk_w - 2, white_h)
                white_idx += 1

        # 검은건반 (각 옥타브 내 위치로 계산)
        # FREQS 인덱스 기준으로 검은건반 위치 찾기
        white_idx = 0
        prev_white_x = start_x
        for i, (freq, black) in enumerate(zip(FREQS, IS_BLACK)):
            if not black:
                prev_white_x = start_x + white_idx * wk_w
                white_idx += 1
            else:
                # 바로 앞 흰건반 오른쪽에 붙임
                bx = prev_white_x + wk_w - (wk_w * 3 // 8)
                bw = wk_w * 3 // 4
                rects[i] = pygame.Rect(bx, piano_y, bw, black_h)

        return rects

    def _draw_piano(self, freq: float):
        active_idx = freq_to_index(freq)
        piano_rects = self._piano_rects

        # 흰건반 먼저
        for i, (is_blk, rect) in enumerate(
                zip(IS_BLACK, [piano_rects.get(j) for j in range(N_NOTES)])):
            if is_blk or rect is None:
                continue
            active = (i == active_idx)
            if active:
                pygame.draw.rect(self.screen, C_NOTE, rect, border_radius=5)
            else:
                pygame.draw.rect(self.screen, (200, 200, 215), rect, border_radius=5)
                pygame.draw.rect(self.screen, DIM, rect, 1, border_radius=5)

            lbl = self.font_small.render(NOTE_KR[i], True,
                                         (20, 20, 20) if active else (100, 100, 120))
            self.screen.blit(lbl, (rect.x + rect.w // 2 - lbl.get_width() // 2,
                                   rect.bottom - lbl.get_height() - 5))

        # 검은건반 위에 그리기
        for i, (is_blk, rect) in enumerate(
                zip(IS_BLACK, [piano_rects.get(j) for j in range(N_NOTES)])):
            if not is_blk or rect is None:
                continue
            active = (i == active_idx)
            col = (180, 140, 255) if active else BLACK_K
            pygame.draw.rect(self.screen, col, rect, border_radius=3)
            if active:
                pygame.draw.rect(self.screen, WHITE, rect, 1, border_radius=3)

            lbl = self.font_small.render(NOTE_KR[i], True,
                                         (20, 20, 20) if active else (80, 80, 100))
            if lbl.get_width() < rect.w:
                self.screen.blit(lbl, (rect.x + rect.w // 2 - lbl.get_width() // 2,
                                       rect.bottom - lbl.get_height() - 3))
