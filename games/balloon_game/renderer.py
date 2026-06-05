"""
renderer.py
Pygame 렌더링 담당 — 게임 로직과 완전히 분리
"""

from __future__ import annotations
import math
import time
import random
import sys
import os
import pygame
from game_logic import BalloonGame, HandData, HandState, GameConfig

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.fonts import get_korean_font


# ── 색상 팔레트 ───────────────────────────────────────────────────────────────

class Color:
    # 배경
    SKY_TOP = (140, 200, 255)
    SKY_MID = (200, 235, 255)
    SKY_BOT = (180, 230, 160)
    CLOUD   = (230, 248, 255)

    # 왼손 — 주황 계열
    L_FILL   = (255, 153,  51)
    L_STROKE = (200,  64,   0)
    L_TARGET = (200,  64,   0)
    L_SHINE  = (255, 255, 255)

    # 오른손 — 핑크 계열
    R_FILL   = (255, 100, 160)
    R_STROKE = (180,   0,  80)
    R_TARGET = (180,   0,  80)
    R_SHINE  = (255, 255, 255)

    # OVER 상태
    OVER_FILL   = (255,  80,  80)
    OVER_STROKE = (180,  20,  20)

    # 펑 파티클
    POP_RING = (226,  75,  74)
    POP_FILL = (247, 193, 193)

    # 상태 배지
    GOOD_BG     = (234, 243, 222)
    GOOD_TEXT   = ( 59, 109,  17)
    WARN_BG     = (250, 238, 218)
    WARN_TEXT   = (133,  79,  11)
    DANGER_BG   = (252, 235, 235)
    DANGER_TEXT = (163,  45,  45)
    IDLE_BG     = (255, 255, 255)
    IDLE_TEXT   = (136, 135, 128)

    # 텍스트
    TEXT_PRIMARY   = ( 30,  30,  28)
    TEXT_SECONDARY = (100,  98,  90)
    WHITE = (255, 255, 255)
    BLACK = (  0,   0,   0)

    # 실/매듭용
    PANEL_BORDER = (180, 160, 140)


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def lerp(a, b, t):
    return a + (b - a) * t


def draw_ellipse_dashed(surface, color, rect, width=2, dash_len=10, gap_len=7):
    """타원을 점선으로 그리기"""
    cx, cy = rect.centerx, rect.centery
    rx, ry = rect.width // 2, rect.height // 2
    circumference = 2 * math.pi * math.sqrt((rx**2 + ry**2) / 2)
    total = dash_len + gap_len
    steps = max(int(circumference / total * 20), 60)
    drawing = True
    acc = 0.0

    for i in range(steps):
        t = i / steps
        angle = 2 * math.pi * t
        x = int(cx + rx * math.cos(angle))
        y = int(cy + ry * math.sin(angle))
        acc += circumference / steps
        if acc >= total:
            acc -= total
            drawing = not drawing
        if drawing:
            pygame.draw.circle(surface, color, (x, y), max(1, width // 2))


def draw_rounded_rect(surface, color, rect, radius=12, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border > 0 and border_color:
        pygame.draw.rect(surface, border_color, rect, border, border_radius=radius)


# ── 풍선 그리기 ───────────────────────────────────────────────────────────────

class BalloonRenderer:

    def __init__(self, cx: int, cy: int, max_rx: int, max_ry: int,
                 fill_color, stroke_color, target_color):
        self.cx, self.cy = cx, cy
        self.max_rx, self.max_ry = max_rx, max_ry
        self.min_rx = max_rx // 4   # 최소 25% 확보
        self.min_ry = max_ry // 4
        self.fill_color   = fill_color
        self.stroke_color = stroke_color
        self.target_color = target_color

    def _scale_to_r(self, scale: float):
        rx = int(lerp(self.min_rx, self.max_rx, scale))
        ry = int(lerp(self.min_ry, self.max_ry, scale))
        return max(rx, 1), max(ry, 1)

    def draw_target(self, surface, target_scale: float, pop_scale: float,
                    font_small, target_kg: float, reached: bool):
        """목표 풍선 (점선) + 펑 한계 링 그리기"""
        prx, pry = self._scale_to_r(pop_scale)
        pop_rect = pygame.Rect(self.cx - prx, self.cy - pry, prx * 2, pry * 2)
        draw_ellipse_dashed(surface, (*Color.POP_RING, 80), pop_rect, width=1, dash_len=5, gap_len=6)

        trx, try_ = self._scale_to_r(target_scale)
        target_rect = pygame.Rect(self.cx - trx, self.cy - try_, trx * 2, try_ * 2)

        tgt_surf = pygame.Surface((trx * 2, try_ * 2), pygame.SRCALPHA)
        fill_alpha = 20 if reached else 50
        pygame.draw.ellipse(tgt_surf, (*self.fill_color, fill_alpha), tgt_surf.get_rect())
        surface.blit(tgt_surf, target_rect.topleft)

        dash_alpha = 100 if reached else 200
        draw_ellipse_dashed(surface, (*self.target_color, dash_alpha),
                            target_rect, width=2, dash_len=8, gap_len=6)

        label_alpha = 100 if reached else 220
        lbl = font_small.render(f"{target_kg:.0f} kg", True, self.target_color)
        lbl.set_alpha(label_alpha)
        surface.blit(lbl, (self.cx - lbl.get_width() // 2,
                            self.cy - try_ - 22))

    def draw_balloon(self, surface, scale: float, hand: HandData, pop_particles):
        """입체감 있는 풍선 그리기 (3겹 레이어)"""
        if hand.state == HandState.POPPED:
            return

        rx, ry = self._scale_to_r(scale)

        # OVER 상태: 수직 진동
        offset_y = 0
        if hand.state == HandState.OVER:
            offset_y = int(abs(math.sin(time.time() * 8)) * 5)

        cy = self.cy + offset_y

        # 색상 결정
        if hand.state == HandState.OVER:
            fill   = Color.OVER_FILL
            stroke = Color.OVER_STROKE
        else:
            fill   = self.fill_color
            stroke = self.stroke_color

        balloon_rect = pygame.Rect(self.cx - rx, cy - ry, rx * 2, ry * 2)

        # 1. 풍선 본체
        pygame.draw.ellipse(surface, fill, balloon_rect)

        # 2. 어두운 테두리
        pygame.draw.ellipse(surface, stroke, balloon_rect, 2)

        # 3. 하이라이트 — 메인 (좌상단, alpha=140)
        h1_rx = max(int(rx * 0.30), 3)
        h1_ry = max(int(ry * 0.22), 2)
        h1_cx = self.cx - int(rx * 0.20)
        h1_cy = cy - int(ry * 0.25)
        h1_surf = pygame.Surface((h1_rx * 2, h1_ry * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(h1_surf, (255, 255, 255, 140), h1_surf.get_rect())
        surface.blit(h1_surf, (h1_cx - h1_rx, h1_cy - h1_ry))

        # 3. 하이라이트 — 서브 (더 오른쪽·위, alpha=70)
        h2_rx = max(int(rx * 0.15), 2)
        h2_ry = max(int(ry * 0.11), 2)
        h2_cx = self.cx - int(rx * 0.05)
        h2_cy = cy - int(ry * 0.38)
        h2_surf = pygame.Surface((h2_rx * 2, h2_ry * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(h2_surf, (255, 255, 255, 70), h2_surf.get_rect())
        surface.blit(h2_surf, (h2_cx - h2_rx, h2_cy - h2_ry))

        # 매듭
        knot_y = cy + ry
        pygame.draw.arc(surface, stroke,
                        pygame.Rect(self.cx - 5, knot_y - 3, 10, 8),
                        0, math.pi, 2)

        # 실
        pygame.draw.line(surface, Color.PANEL_BORDER,
                         (self.cx, knot_y + 4),
                         (self.cx, knot_y + 20), 1)

        # ON_TARGET: 진행 호 (테두리색)
        if hand.state == HandState.ON_TARGET and hand.hold_ratio > 0:
            self._draw_progress_arc(surface, rx + 6, ry + 6, hand.hold_ratio, stroke)

    def _draw_progress_arc(self, surface, rx, ry, ratio, color):
        """목표 유지 진행률 호 (풍선 바깥쪽)"""
        start_angle = -math.pi / 2
        end_angle   = start_angle + 2 * math.pi * ratio
        steps = max(int(60 * ratio), 2)
        prev_pt = None
        for i in range(steps + 1):
            t = i / steps
            angle = lerp(start_angle, end_angle, t)
            x = int(self.cx + rx * math.cos(angle))
            y = int(self.cy + ry * math.sin(angle))
            if prev_pt:
                pygame.draw.line(surface, color, prev_pt, (x, y), 3)
            prev_pt = (x, y)


# ── 파티클 (펑 효과) ──────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = float(x), float(y)
        angle = random.uniform(0, math.tau)
        speed = random.uniform(80, 180)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.life  = 1.0
        self.r     = random.randint(3, 7)

    def update(self, dt):
        self.x   += self.vx * dt
        self.y   += self.vy * dt
        self.vy  += 200 * dt
        self.life -= dt * 1.8

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = int(255 * max(self.life, 0))
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x) - self.r, int(self.y) - self.r))


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────

class GameRenderer:

    SCREEN_W  = 800
    SCREEN_H  = 520

    PANEL_W   = 340
    PANEL_H   = 380
    PANEL_Y   = 60
    L_PANEL_X = 30
    R_PANEL_X = SCREEN_W - PANEL_W - 30

    BALLOON_CX = PANEL_W // 2
    BALLOON_CY = 170
    MAX_RX, MAX_RY = 95, 115

    def __init__(self, config: GameConfig):
        self.cfg = config
        pygame.font.init()

        self.font_large = get_korean_font(42)
        self.font_title = get_korean_font(33)
        self.font_body  = get_korean_font(24)
        self.font_small = get_korean_font(20)
        self.font_tip   = get_korean_font(18)

        self.balloon_l = BalloonRenderer(
            self.BALLOON_CX, self.BALLOON_CY,
            self.MAX_RX, self.MAX_RY,
            Color.L_FILL, Color.L_STROKE, Color.L_TARGET,
        )
        self.balloon_r = BalloonRenderer(
            self.BALLOON_CX, self.BALLOON_CY,
            self.MAX_RX, self.MAX_RY,
            Color.R_FILL, Color.R_STROKE, Color.R_TARGET,
        )
        self.particles: list[Particle] = []
        self._bg_surface = self._build_bg_surface()

    # ── 배경 + 구름 (초기화 시 1회만 그림) ───────────────────────────────────

    def _build_bg_surface(self) -> pygame.Surface:
        surf = pygame.Surface((self.SCREEN_W, self.SCREEN_H))
        top_c, mid_c, bot_c = Color.SKY_TOP, Color.SKY_MID, Color.SKY_BOT
        mid_y = self.SCREEN_H // 2

        for y in range(self.SCREEN_H):
            if y <= mid_y:
                t = y / mid_y
                c0, c1 = top_c, mid_c
            else:
                t = (y - mid_y) / (self.SCREEN_H - mid_y)
                c0, c1 = mid_c, bot_c
            c = (
                int(c0[0] + (c1[0] - c0[0]) * t),
                int(c0[1] + (c1[1] - c0[1]) * t),
                int(c0[2] + (c1[2] - c0[2]) * t),
            )
            pygame.draw.line(surf, c, (0, y), (self.SCREEN_W - 1, y))

        self._draw_clouds(surf)
        return surf

    def _draw_clouds(self, surf):
        """구름 = 흰색 타원 여러 개를 겹쳐서 표현"""
        cc = Color.CLOUD
        # 각 구름: (cx, cy, rx, ry) 타원 목록
        clouds = [
            [(105, 43, 32, 19), (128, 34, 30, 17), (152, 41, 27, 16), (123, 50, 36, 18)],
            [(590, 37, 30, 18), (613, 27, 32, 18), (635, 35, 28, 16), (605, 44, 34, 17)],
            [(368, 22, 28, 16), (392, 15, 30, 17), (415, 21, 26, 15), (388, 30, 32, 16)],
            [(268, 58, 26, 15), (292, 50, 28, 16), (313, 57, 24, 14), (287, 65, 30, 15)],
        ]
        for cloud in clouds:
            for cx, cy, rx, ry in cloud:
                pygame.draw.ellipse(surf, cc, (cx - rx, cy - ry, rx * 2, ry * 2))

    # ── 공개 메서드 ───────────────────────────────────────────────────────────

    def spawn_pop(self, cx_screen, cy_screen, is_left: bool):
        colors = [Color.L_STROKE, Color.L_FILL, Color.L_TARGET] if is_left \
            else [Color.R_STROKE, Color.R_FILL, Color.R_TARGET]
        for _ in range(14):
            self.particles.append(
                Particle(cx_screen, cy_screen, random.choice(colors))
            )

    def update_particles(self, dt: float):
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update(dt)

    def draw(self, surface: pygame.Surface, game: BalloonGame, dt: float):
        surface.blit(self._bg_surface, (0, 0))
        self.update_particles(dt)

        self._draw_title(surface)

        l_surf = self._draw_panel(
            game, game.left, game.balloon_scale(game.left.grip_kg), is_left=True
        )
        surface.blit(l_surf, (self.L_PANEL_X, self.PANEL_Y))

        r_surf = self._draw_panel(
            game, game.right, game.balloon_scale(game.right.grip_kg), is_left=False
        )
        surface.blit(r_surf, (self.R_PANEL_X, self.PANEL_Y))

        for p in self.particles:
            p.draw(surface)

        self._draw_score(surface, game)

    # ── 헤더 ─────────────────────────────────────────────────────────────────

    def _draw_title(self, surface):
        # 반투명 흰색 띠 (높이 50px)
        band = pygame.Surface((self.SCREEN_W, 50), pygame.SRCALPHA)
        band.fill((255, 255, 255, 100))
        surface.blit(band, (0, 0))

        txt = self.font_title.render("풍선 키우기", True, Color.TEXT_PRIMARY)
        surface.blit(txt, (self.SCREEN_W // 2 - txt.get_width() // 2, 8))

        sub = self.font_tip.render(
            f"목표: {self.cfg.target_kg:.0f} kg 를 {self.cfg.success_sec:.0f}초 유지하면 성공!",
            True, Color.TEXT_SECONDARY,
        )
        surface.blit(sub, (self.SCREEN_W // 2 - sub.get_width() // 2, 42))

    # ── 패널 ─────────────────────────────────────────────────────────────────

    def _draw_panel(self, game: BalloonGame, hand: HandData,
                    scale: float, is_left: bool) -> pygame.Surface:
        surf = pygame.Surface((self.PANEL_W, self.PANEL_H), pygame.SRCALPHA)

        # 반투명 흰색 패널 배경
        panel_rect = pygame.Rect(0, 0, self.PANEL_W, self.PANEL_H)
        pygame.draw.rect(surf, (255, 255, 255, 150), panel_rect, border_radius=24)
        pygame.draw.rect(surf, (255, 255, 255, 220), panel_rect, 2, border_radius=24)

        br = self.balloon_l if is_left else self.balloon_r
        target_scale = game.balloon_scale(self.cfg.target_kg)
        pop_scale    = 1.0
        reached      = hand.state in (HandState.ON_TARGET,)

        br.draw_target(surf, target_scale, pop_scale,
                       self.font_small, self.cfg.target_kg, reached)
        br.draw_balloon(surf, scale, hand, self.particles)

        # 펑 텍스트
        if hand.state == HandState.POPPED:
            txt = self.font_large.render("펑! 💥", True, Color.DANGER_TEXT)
            surf.blit(txt, (self.PANEL_W // 2 - txt.get_width() // 2,
                            self.BALLOON_CY - 20))

        # 손 라벨
        label = "왼손" if is_left else "오른손"
        lbl = self.font_body.render(label, True, Color.TEXT_SECONDARY)
        surf.blit(lbl, (self.PANEL_W // 2 - lbl.get_width() // 2, 10))

        # 현재 악력 수치
        kg_txt = self.font_large.render(f"{hand.grip_kg:.1f} kg", True, Color.TEXT_PRIMARY)
        kg_y = self.BALLOON_CY + self.MAX_RY + 12
        surf.blit(kg_txt, (self.PANEL_W // 2 - kg_txt.get_width() // 2, kg_y))

        # 상태 배지 (kg 텍스트 바로 아래)
        badge_y = kg_y + self.font_large.get_height() + 4
        self._draw_status_badge(surf, hand, self.PANEL_W // 2, badge_y)

        # 유지 시간 진행바 (ON_TARGET 일 때)
        if hand.state == HandState.ON_TARGET:
            self._draw_hold_bar(surf, hand.hold_ratio,
                                20, self.PANEL_H - 28, self.PANEL_W - 40, 8)

        return surf

    def _draw_status_badge(self, surf, hand: HandData, cx, y):
        state_map = {
            HandState.IDLE:      ("  악력을 가해주세요",       Color.IDLE_BG,   Color.IDLE_TEXT),
            HandState.FILLING:   ("💪 더 세게 쥐어주세요!",    Color.WARN_BG,   Color.WARN_TEXT),
            HandState.ON_TARGET: ("✅ 딱 좋아요! 유지하세요",  Color.GOOD_BG,   Color.GOOD_TEXT),
            HandState.OVER:      ("⚠️  살짝 풀어주세요",        Color.DANGER_BG, Color.DANGER_TEXT),
            HandState.POPPED:    ("💥 펑! 잠시 기다리세요",    Color.DANGER_BG, Color.DANGER_TEXT),
        }
        text, bg, fg = state_map.get(hand.state, ("", Color.IDLE_BG, Color.IDLE_TEXT))
        txt = self.font_small.render(text, True, fg)
        w = txt.get_width() + 36   # 기존 +24에서 +12 추가
        h = 32                      # 기존 26에서 +6
        rect = pygame.Rect(cx - w // 2, y, w, h)
        draw_rounded_rect(surf, bg, rect, radius=18)
        surf.blit(txt, (cx - txt.get_width() // 2, y + (h - txt.get_height()) // 2))

    def _draw_hold_bar(self, surf, ratio, x, y, w, h):
        bg_rect   = pygame.Rect(x, y, w, h)
        fill_rect = pygame.Rect(x, y, int(w * ratio), h)
        draw_rounded_rect(surf, Color.PANEL_BORDER, bg_rect,   radius=4)
        draw_rounded_rect(surf, Color.GOOD_TEXT,    fill_rect, radius=4)

    def _draw_score(self, surface, game: BalloonGame):
        items = [
            ("성공",      str(game.total_success)),
            ("펑!",       str(game.total_pop)),
            ("왼손 최고", f"{game.left.grip_kg:.1f} kg"),
        ]
        total_w = 600
        start_x = self.SCREEN_W // 2 - total_w // 2
        y = self.PANEL_Y + self.PANEL_H + 10   # SCREEN_H=520 안에 맞게 조정

        for i, (label, value) in enumerate(items):
            x = start_x + i * (total_w // len(items))
            val_txt = self.font_large.render(value, True, Color.TEXT_PRIMARY)
            lbl_txt = self.font_small.render(label, True, Color.TEXT_SECONDARY)
            surface.blit(val_txt, (x + 60 - val_txt.get_width() // 2, y))
            surface.blit(lbl_txt, (x + 60 - lbl_txt.get_width() // 2,
                                    y + val_txt.get_height() + 4))
