"""
renderer.py — 두더지 잡기 Pygame 렌더러

화면 레이아웃 (800 × 600):
  ┌─────────────────────────────────┐
  │  HUD (점수 / 시간 / 콤보)        │  y 0~80
  ├─────────────────────────────────┤
  │  구멍 3개 (왼쪽 / 가운데 / 오른쪽) │  y 80~420
  ├─────────────────────────────────┤
  │  악력 게이지 2개                  │  y 440~560
  └─────────────────────────────────┘
"""

import math
import time
import sys
import os
import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.fonts import get_korean_font

from game_logic import MoleStatus, WhackAMoleLogic, THRESHOLD_KG


# ── 팔레트 ────────────────────────────────────

BG_DARK    = (18,  38,  18)
BG_MID     = (28,  56,  28)
HOLE_BG    = (12,  22,  12)
HOLE_EDGE  = (42,  72,  42)
GREEN_HI   = (80, 220, 120)
BLUE_HI    = (80, 140, 255)
PURPLE_HI  = (180, 100, 255)
YELLOW_HI  = (255, 230, 60)
RED_HI     = (255,  70,  70)
WHITE      = (230, 255, 230)
MUTED      = (100, 140, 100)
HIT_FLASH  = (255, 240, 80)
MISS_FLASH = (255,  60,  60)

KIND_COLOR = {'left': BLUE_HI, 'both': PURPLE_HI, 'right': GREEN_HI}
KIND_LABEL = {'left': '왼손', 'both': '양손', 'right': '오른손'}

W, H = 800, 600

HOLE_CENTERS = [(167, 240), (400, 240), (633, 240)]
HOLE_R = 100  # 구멍 반지름


# ── 파티클 ────────────────────────────────────

class Particle:
    def __init__(self, x, y, color):
        import random
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(60, 180)
        self.x, self.y = float(x), float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 80
        self.color = color
        self.life  = 1.0
        self.r     = random.randint(4, 8)

    def update(self, dt):
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += 300 * dt   # 중력
        self.life -= dt * 2.5

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf):
        alpha = max(0, int(self.life * 255))
        col   = (*self.color, alpha)
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (self.r, self.r), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))


# ── 플래시 이펙트 ─────────────────────────────

class HoleFlash:
    def __init__(self, color, duration=0.35):
        self.color    = color
        self.life     = duration
        self.max_life = duration

    def update(self, dt):
        self.life -= dt

    @property
    def alive(self):
        return self.life > 0

    @property
    def alpha(self):
        return int((self.life / self.max_life) * 180)


# ── 팝업 텍스트 ───────────────────────────────

class PopText:
    def __init__(self, text, x, y, color, size=28):
        self.text  = text
        self.x, self.y = float(x), float(y)
        self.color = color
        self.life  = 1.0
        self.size  = size

    def update(self, dt):
        self.y  -= 60 * dt
        self.life -= dt * 1.8

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surf, font):
        alpha = max(0, int(self.life * 255))
        col   = (*self.color, alpha)
        s     = font.render(self.text, True, self.color)
        s.set_alpha(alpha)
        surf.blit(s, (int(self.x) - s.get_width() // 2, int(self.y)))


# ── 메인 렌더러 ───────────────────────────────

class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()

        self.font_lg  = get_korean_font(40)
        self.font_md  = get_korean_font(26)
        self.font_sm  = get_korean_font(18)
        self.font_xs  = get_korean_font(14)
        self.font_hud = get_korean_font(32)

        self.particles: list[Particle]  = []
        self.pop_texts: list[PopText]   = []
        self.hole_flash: list           = [None, None, None]
        self.hit_anim:   list[float]    = [0.0, 0.0, 0.0]  # 0~1 (scale flash)

    # ── 이벤트 소비 ──────────────────────────

    def handle_event(self, event_str: str):
        if event_str.startswith("hit:"):
            i = int(event_str.split(":")[1])
            cx, cy = HOLE_CENTERS[i]
            self.hole_flash[i] = HoleFlash(HIT_FLASH)
            self.hit_anim[i]   = 1.0
            for _ in range(20):
                self.particles.append(Particle(cx, cy - 60, YELLOW_HI))
            self.pop_texts.append(PopText("+10", cx, cy - 80, YELLOW_HI, 30))

        elif event_str.startswith("missed:"):
            i = int(event_str.split(":")[1])
            self.hole_flash[i] = HoleFlash(MISS_FLASH, 0.4)

        elif event_str.startswith("combo:"):
            c  = event_str.split(":")[1]
            cx = W // 2
            self.pop_texts.append(PopText(f"{c} COMBO!", cx, 100, YELLOW_HI, 36))

    # ── 메인 draw ────────────────────────────

    def draw(self, logic: WhackAMoleLogic, left_kg: float, right_kg: float, dt: float):
        s  = logic.state
        sc = self.screen

        # 배경
        sc.fill(BG_DARK)
        pygame.draw.rect(sc, BG_MID, (0, 0, W, 80))
        pygame.draw.line(sc, HOLE_EDGE, (0, 80), (W, 80), 1)

        self._draw_hud(s)
        self._draw_holes(s, dt)
        self._draw_grip_bars(left_kg, right_kg)
        self._draw_particles(dt)
        self._draw_pop_texts(dt)

        if s.finished:
            self._draw_game_over(s)
        elif not s.running:
            self._draw_start_screen()

    # ── HUD ──────────────────────────────────

    def _draw_hud(self, s):
        sc = self.screen

        # 점수
        self._draw_hud_box(sc, 20, 8, 140, 64, "점수", str(s.score), WHITE)

        # 타이머
        tl = int(s.time_left)
        col = RED_HI if tl <= 10 else (255, 160, 60) if tl <= 20 else WHITE
        self._draw_hud_box(sc, W - 160, 8, 140, 64, "남은 시간", str(tl), col)

        # 콤보
        if s.combo >= 3:
            txt = self.font_md.render(f"🔥 {s.combo} COMBO", True, YELLOW_HI)
            sc.blit(txt, (W // 2 - txt.get_width() // 2, 24))

    def _draw_hud_box(self, sc, x, y, w, h, label, value, col):
        pygame.draw.rect(sc, (0, 0, 0, 100), (x, y, w, h), border_radius=8)
        pygame.draw.rect(sc, HOLE_EDGE, (x, y, w, h), 1, border_radius=8)
        lb = self.font_xs.render(label, True, MUTED)
        sc.blit(lb, (x + w // 2 - lb.get_width() // 2, y + 6))
        vb = self.font_hud.render(value, True, col)
        sc.blit(vb, (x + w // 2 - vb.get_width() // 2, y + 28))

    # ── 구멍 + 두더지 ─────────────────────────

    def _draw_holes(self, s, dt):
        sc = self.screen
        labels = ['왼쪽 (왼손)', '가운데 (양손)', '오른쪽 (오른손)']
        label_cols = [BLUE_HI, PURPLE_HI, GREEN_HI]

        for i, (cx, cy) in enumerate(HOLE_CENTERS):
            mole  = s.moles[i]
            flash = self.hole_flash[i]

            # 히트 애니메이션 감쇠
            if self.hit_anim[i] > 0:
                self.hit_anim[i] = max(0.0, self.hit_anim[i] - dt * 5)

            # 구멍 그리기
            edge_col = HOLE_EDGE
            if mole and mole.status == MoleStatus.UP:
                edge_col = KIND_COLOR[mole.kind]
            pygame.draw.ellipse(sc, HOLE_BG,
                (cx - HOLE_R, cy - HOLE_R // 2, HOLE_R * 2, HOLE_R), )
            pygame.draw.ellipse(sc, edge_col,
                (cx - HOLE_R, cy - HOLE_R // 2, HOLE_R * 2, HOLE_R), 3)

            # 플래시
            if flash:
                flash.update(dt)
                if flash.alive:
                    overlay = pygame.Surface((HOLE_R * 2, HOLE_R), pygame.SRCALPHA)
                    overlay.fill((*flash.color, flash.alpha))
                    sc.blit(overlay, (cx - HOLE_R, cy - HOLE_R // 2))
                else:
                    self.hole_flash[i] = None

            # 두더지
            if mole and mole.status in (MoleStatus.UP, MoleStatus.HIT):
                self._draw_mole(sc, cx, cy, mole, dt)

            # 타이머 바
            if mole and mole.status == MoleStatus.UP:
                self._draw_timer_bar(sc, cx, cy, mole)

            # 구멍 라벨
            lb = self.font_xs.render(labels[i], True, label_cols[i])
            sc.blit(lb, (cx - lb.get_width() // 2, cy + HOLE_R // 2 + 8))

    def _draw_mole(self, sc, cx, cy, mole, dt):
        scale = 1.0 + self.hit_anim[int(mole.hole)] * 0.25
        emoji = "🐹"
        size  = int(64 * scale)
        # pygame 기본 폰트로 이모지 → 폴백으로 원 + 눈으로 그리기
        # (Linux 환경에서 컬러 이모지 렌더링이 안 될 수 있으므로 직접 그림)
        col = KIND_COLOR[mole.kind] if mole.status == MoleStatus.UP else HIT_FLASH
        pygame.draw.circle(sc, col, (cx, cy - 30), size // 2)
        pygame.draw.circle(sc, BG_DARK, (cx, cy - 30), size // 2, 2)
        # 눈
        ew = size // 8
        pygame.draw.circle(sc, BG_DARK, (cx - ew * 2, cy - 34), ew)
        pygame.draw.circle(sc, BG_DARK, (cx + ew * 2, cy - 34), ew)
        # 코
        pygame.draw.circle(sc, (200, 80, 80), (cx, cy - 26), ew)
        # 수염
        for dx, sign in [(-1, -1), (1, 1)]:
            pygame.draw.line(sc, BG_DARK,
                (cx + sign * 6, cy - 27),
                (cx + sign * 20, cy - 24), 1)

        # 종류 배지
        badge_col = KIND_COLOR[mole.kind]
        badge_txt = self.font_xs.render(KIND_LABEL[mole.kind], True, BG_DARK)
        bw = badge_txt.get_width() + 10
        bh = 18
        bx = cx - bw // 2
        by = cy - 30 - size // 2 - 22
        pygame.draw.rect(sc, badge_col, (bx, by, bw, bh), border_radius=6)
        sc.blit(badge_txt, (bx + 5, by + 2))

    def _draw_timer_bar(self, sc, cx, cy, mole):
        bw, bh = 120, 6
        bx = cx - bw // 2
        by = cy + HOLE_R // 2 - 4
        pygame.draw.rect(sc, (40, 60, 40), (bx, by, bw, bh), border_radius=3)
        fill_w = int(bw * mole.time_ratio)
        if fill_w > 0:
            col = KIND_COLOR[mole.kind]
            if mole.time_ratio < 0.3:
                col = RED_HI
            pygame.draw.rect(sc, col, (bx, by, fill_w, bh), border_radius=3)

    # ── 악력 게이지 ───────────────────────────

    def _draw_grip_bars(self, left_kg: float, right_kg: float):
        sc   = self.screen
        by0  = 450
        bh   = 28
        bpad = 60
        bw   = (W - bpad * 2 - 20) // 2
        max_kg = 20.0

        for i, (kg, label, col, bx) in enumerate([
            (left_kg,  "왼손  (A:약 / S:강)", BLUE_HI,  bpad),
            (right_kg, "오른손 (K:약 / L:강)", GREEN_HI, bpad + bw + 20),
        ]):
            # 라벨
            lb = self.font_sm.render(label, True, MUTED)
            sc.blit(lb, (bx, by0 - 22))

            # 배경 바
            pygame.draw.rect(sc, (20, 40, 20), (bx, by0, bw, bh), border_radius=6)
            pygame.draw.rect(sc, HOLE_EDGE, (bx, by0, bw, bh), 1, border_radius=6)

            # 채우기
            fill_w = int(bw * min(1.0, kg / max_kg))
            if fill_w > 0:
                fill_col = YELLOW_HI if kg >= THRESHOLD_KG else col
                pygame.draw.rect(sc, fill_col, (bx, by0, fill_w, bh), border_radius=6)

            # 임계값 선
            tx = bx + int(bw * THRESHOLD_KG / max_kg)
            pygame.draw.line(sc, WHITE, (tx, by0 - 4), (tx, by0 + bh + 4), 2)

            # 수치
            val = self.font_sm.render(f"{kg:.1f} kg", True, WHITE)
            sc.blit(val, (bx + bw - val.get_width() - 4, by0 + 5))

    # ── 파티클 / 팝업 ─────────────────────────

    def _draw_particles(self, dt):
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update(dt)
            p.draw(self.screen)

    def _draw_pop_texts(self, dt):
        self.pop_texts = [t for t in self.pop_texts if t.alive]
        for t in self.pop_texts:
            t.update(dt)
            t.draw(self.screen, self.font_md)

    # ── 오버레이 ─────────────────────────────

    def _draw_start_screen(self):
        self._draw_overlay("두더지 잡기\n악력 재활 게임",
                           "Space 키를 눌러 시작!")

    def _draw_game_over(self, s):
        sc = self.screen
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        sc.blit(overlay, (0, 0))

        title = self.font_lg.render("게임 종료!", True, GREEN_HI)
        sc.blit(title, (W // 2 - title.get_width() // 2, 120))

        total = s.hits + s.misses
        acc   = int(s.hits / total * 100) if total else 0

        stats = [
            ("점수",    str(s.score)),
            ("잡은 수", str(s.hits)),
            ("정확도",  f"{acc}%"),
            ("최대콤보", str(s.max_combo)),
        ]
        for j, (lbl, val) in enumerate(stats):
            x = 120 + j * 150
            pygame.draw.rect(sc, (20, 50, 20), (x, 200, 130, 80), border_radius=10)
            pygame.draw.rect(sc, HOLE_EDGE,    (x, 200, 130, 80), 1, border_radius=10)
            lb = self.font_xs.render(lbl, True, MUTED)
            vb = self.font_md.render(val, True, WHITE)
            sc.blit(lb, (x + 65 - lb.get_width() // 2, 210))
            sc.blit(vb, (x + 65 - vb.get_width() // 2, 236))

        hint = self.font_sm.render("R 키: 다시 하기   /   Q 키: 종료", True, MUTED)
        sc.blit(hint, (W // 2 - hint.get_width() // 2, 320))

    def _draw_overlay(self, title_text, hint_text):
        sc = self.screen
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        sc.blit(overlay, (0, 0))

        for j, line in enumerate(title_text.split("\n")):
            t = self.font_lg.render(line, True, GREEN_HI)
            sc.blit(t, (W // 2 - t.get_width() // 2, 180 + j * 52))

        hint = self.font_md.render(hint_text, True, MUTED)
        sc.blit(hint, (W // 2 - hint.get_width() // 2, 310))

        legend = [
            ("왼쪽 구멍 = 왼손", BLUE_HI),
            ("가운데 구멍 = 양손", PURPLE_HI),
            ("오른쪽 구멍 = 오른손", GREEN_HI),
        ]
        for j, (txt, col) in enumerate(legend):
            lb = self.font_sm.render(txt, True, col)
            sc.blit(lb, (W // 2 - lb.get_width() // 2, 370 + j * 28))
