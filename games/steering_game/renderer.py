"""
renderer.py — 우주 조종 게임 렌더러

어두운 우주 배경 + 파란 터널 + 흰 우주선
"""

import os
import pygame
import math
import random

from game_logic import (
    SteeringGame, GameState,
    SCREEN_W, SCREEN_H, PLAYER_Y, PLAYER_W, PLAYER_H,
    GAME_DURATION,
)


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    candidates = (
        ['/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
         '/usr/share/fonts/truetype/nanum/NanumGothic.ttf']
        if bold else
        ['/usr/share/fonts/truetype/nanum/NanumGothic.ttf']
    ) + [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/System/Library/Fonts/AppleSDGothicNeo.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)

_BG     = (10,  10,  30)
_TUNNEL = (22,  52,  92)
_WALL   = (60, 120, 210)
_WALL2  = (35,  75, 145)
_SHIP   = (220, 230, 255)
_THRUST = (255, 120,  30)
_HUD    = (185, 200, 225)
_WARN   = (220,  55,  55)
_LIFE   = (255,  75,  75)
_GREEN  = (34,  139,  34)

# 고정 별 배치 (한 번만 계산)
_rng   = random.Random(42)
_STARS = [(_rng.randint(0, SCREEN_W - 1),
           _rng.randint(0, SCREEN_H - 1),
           _rng.randint(1, 2),
           _rng.randint(90, 210)) for _ in range(80)]


class SteeringRenderer:
    def __init__(self, screen: pygame.Surface):
        self.screen  = screen
        self._anim_t = 0.0

        self._font_hud   = _load_font(26, bold=True)
        self._font_large = _load_font(72, bold=True)
        self._font_title = _load_font(42, bold=True)
        self._font_small = _load_font(20)

    # countdown에서 접근하는 프로퍼티
    @property
    def font_large(self):
        return self._font_large

    @property
    def font_title(self):
        return self._font_title

    # ── 메인 드로우 ────────────────────────────────────────────────────────

    def draw(self, game: SteeringGame, left_kg: float, right_kg: float, dt: float):
        s = game.state
        self._anim_t += dt
        sc = self.screen

        sc.fill(_BG)
        self._draw_stars(sc)
        self._draw_tunnel(sc, s)
        self._draw_player(sc, s, left_kg, right_kg)
        self._draw_hud(sc, s, left_kg, right_kg)

        # 충돌 후 빨간 플래시
        if s.grace_t > 0 and int(s.grace_t * 8) % 2 == 0:
            fl = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            fl.fill((255, 40, 40, 55))
            sc.blit(fl, (0, 0))

        if s.finished:
            self._draw_game_over(sc, s)

    # ── 내부 드로우 ────────────────────────────────────────────────────────

    def _draw_stars(self, sc):
        for x, y, r, b in _STARS:
            pygame.draw.circle(sc, (b, b, b), (x, y), r)

    def _draw_tunnel(self, sc, s: GameState):
        # 화면 근처 포인트만 사용
        pts = [p for p in s.tunnel if -80 <= p.y <= SCREEN_H + 80]
        if len(pts) < 2:
            return

        lpts = [(int(p.cx - p.half_w), int(p.y)) for p in pts]
        rpts = [(int(p.cx + p.half_w), int(p.y)) for p in pts]

        # 터널 내부 채우기
        poly = lpts + list(reversed(rpts))
        if len(poly) >= 3:
            try:
                pygame.draw.polygon(sc, _TUNNEL, poly)
            except Exception:
                pass

        # 벽 라인 (두 겹으로 glow 효과)
        if len(lpts) >= 2:
            pygame.draw.lines(sc, _WALL2, False, lpts, 6)
            pygame.draw.lines(sc, _WALL2, False, rpts, 6)
            pygame.draw.lines(sc, _WALL,  False, lpts, 2)
            pygame.draw.lines(sc, _WALL,  False, rpts, 2)

    def _draw_player(self, sc, s: GameState, left_kg: float, right_kg: float):
        x, y = int(s.player_x), PLAYER_Y

        # 추진 불꽃
        avg = (left_kg + right_kg) / 2.0
        if avg > 0.3:
            fl_h = int(8 + avg * 2.5 + math.sin(self._anim_t * 25) * 4)
            fl_w = PLAYER_W // 4 + 2
            col  = _THRUST if avg > 3.0 else (200, 80, 20)
            for ox in (-PLAYER_W // 4, PLAYER_W // 4):
                pygame.draw.ellipse(sc, col,
                    (x + ox - fl_w // 2, y + PLAYER_H // 2 - 3, fl_w, fl_h))

        # 우주선 몸체 (삼각형)
        blink = s.grace_t > 0 and int(s.grace_t * 8) % 2 == 0
        col   = (255, 255, 100) if blink else _SHIP
        tri   = [(x,              y - PLAYER_H // 2),
                 (x - PLAYER_W // 2, y + PLAYER_H // 2),
                 (x + PLAYER_W // 2, y + PLAYER_H // 2)]
        pygame.draw.polygon(sc, col, tri)

        # 중심선
        pygame.draw.line(sc, (100, 140, 220),
            (x, y - PLAYER_H // 2 + 4), (x, y + PLAYER_H // 2 - 4), 2)

    def _draw_hud(self, sc, s: GameState, left_kg: float, right_kg: float):
        # 왼손 / 오른손 힘 바 (넓게)
        self._draw_bar(sc, 14, 55, 28, 165, left_kg, "왼손")
        self._draw_bar(sc, SCREEN_W - 42, 55, 28, 165, right_kg, "오른손")

        # 타이머 (상단 중앙, 크게)
        secs  = int(math.ceil(s.time_left))
        tcol  = _WARN if secs <= 10 else _HUD
        t_txt = self._font_hud.render(str(secs), True, tcol)
        sc.blit(t_txt, (SCREEN_W // 2 - t_txt.get_width() // 2, 8))

        # 점수
        sc_txt = self._font_small.render(f"점수  {int(s.score)}", True, _HUD)
        sc.blit(sc_txt, (SCREEN_W // 2 - sc_txt.get_width() // 2, 42))

        # 목숨 (우주선 아이콘)
        for i in range(s.lives):
            bx = 14 + i * 30
            by = 240
            pygame.draw.polygon(sc, _LIFE, [
                (bx + 9, by), (bx, by + 16), (bx + 18, by + 16)
            ])

        # 조작 안내 (하단)
        net = right_kg - left_kg
        if net > 1.0:
            arrow, hint_col = "오른손 →", (120, 220, 120)
        elif net < -1.0:
            arrow, hint_col = "← 왼손", (120, 220, 120)
        else:
            arrow, hint_col = "← 왼손   오른손 →", (110, 135, 165)
        h_surf = self._font_small.render(arrow, True, hint_col)
        sc.blit(h_surf, (SCREEN_W // 2 - h_surf.get_width() // 2, SCREEN_H - 32))

    def _draw_bar(self, sc, x, y, w, h, kg: float, label: str):
        MAX_KG = 20.0
        r = min(1.0, kg / MAX_KG)
        pygame.draw.rect(sc, (38, 44, 65), (x, y, w, h), border_radius=5)
        fh = int(h * r)
        if fh > 0:
            fc = (75, 195, 85) if r < 0.65 else (220, 140, 40)
            pygame.draw.rect(sc, fc, (x, y + h - fh, w, fh), border_radius=5)
        pygame.draw.rect(sc, (95, 135, 200), (x, y, w, h), 2, border_radius=5)
        lb = self._font_small.render(label, True, _HUD)
        sc.blit(lb, (x + w // 2 - lb.get_width() // 2, y + h + 5))

    def _draw_game_over(self, sc, s: GameState):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        sc.blit(ov, (0, 0))

        msg   = "시간 초과!" if s.lives > 0 else "게임 오버!"
        col   = (255, 200, 80) if s.lives > 0 else (255, 80, 80)
        t1    = self._font_title.render(msg, True, col)
        t2    = self._font_hud.render(f"최종 점수:  {int(s.score)}", True, _HUD)
        sc.blit(t1, (SCREEN_W // 2 - t1.get_width() // 2, SCREEN_H // 2 - 55))
        sc.blit(t2, (SCREEN_W // 2 - t2.get_width() // 2, SCREEN_H // 2 + 15))
