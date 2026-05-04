"""
renderer.py
Pygame 렌더링 — 게임 로직과 완전히 분리
"""

from __future__ import annotations
import math
import os
import time
import random
import pygame
from game_logic import BalloonGame, HandData, HandState, GameConfig


# ── 색상 팔레트 ───────────────────────────────────────────────────────────────

class C:
    BG           = (245, 243, 238)
    PANEL_BG     = (255, 255, 255)
    PANEL_BORDER = (220, 217, 210)

    L_FILL   = (181, 212, 244)
    L_STROKE = (55,  138, 221)
    L_TARGET = (24,   95, 165)

    R_FILL   = (245, 196, 179)
    R_STROKE = (216,  90,  48)
    R_TARGET = (153,  60,  29)

    POP_FILL   = (247, 193, 193)
    POP_RING   = (220,  60,  60)
    GOOD_BG    = (230, 245, 215)
    GOOD_FG    = ( 52,  96,  14)
    WARN_BG    = (255, 243, 220)
    WARN_FG    = (140,  82,  10)
    OVER_BG    = (255, 228, 220)
    OVER_FG    = (180,  45,  20)
    IDLE_BG    = (240, 240, 240)
    IDLE_FG    = (130, 128, 120)
    REL_BG     = (220, 235, 255)
    REL_FG     = ( 40,  80, 170)

    TEXT_PRI = ( 28,  28,  26)
    TEXT_SEC = (110, 108, 100)
    WHITE    = (255, 255, 255)

    # 그립 바 구간 색상
    BAR_BG     = (220, 218, 212)
    BAR_FILL   = ( 80, 160,  80)    # 목표 구간 녹색
    BAR_OVER   = (230, 120,  40)    # 초과 구간 주황
    BAR_POP    = (210,  50,  50)    # 펑 구간 빨강
    BAR_CURSOR = ( 30,  30,  30)    # 현재 위치 커서


# ── 폰트 유틸 ─────────────────────────────────────────────────────────────────

def _load_font(size: int) -> pygame.font.Font:
    """한글 지원 폰트를 시스템에서 찾아 로드. 없으면 기본 폰트."""
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    for name in ["applegothic", "nanumgothic", "malgun gothic", "gulim", "dotum"]:
        try:
            f = pygame.font.SysFont(name, size)
            if f:
                return f
        except Exception:
            continue
    return pygame.font.SysFont(None, size)


# ── 도형 유틸 ─────────────────────────────────────────────────────────────────

def lerp(a, b, t):
    return a + (b - a) * t

def draw_rrect(surface, color, rect, r=10, border=0, bc=None):
    pygame.draw.rect(surface, color, rect, border_radius=r)
    if border > 0 and bc:
        pygame.draw.rect(surface, bc, rect, border, border_radius=r)

def draw_dashed_ellipse(surface, color, rect, width=2, dash=9, gap=6):
    cx, cy = rect.centerx, rect.centery
    rx, ry = rect.width // 2, rect.height // 2
    circ   = 2 * math.pi * math.sqrt((rx**2 + ry**2) / 2)
    total  = dash + gap
    steps  = max(int(circ / total * 20), 60)
    drawing, acc = True, 0.0
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        x = int(cx + rx * math.cos(angle))
        y = int(cy + ry * math.sin(angle))
        acc += circ / steps
        if acc >= total:
            acc -= total
            drawing = not drawing
        if drawing:
            pygame.draw.circle(surface, color, (x, y), max(1, width // 2))


# ── 풍선 렌더러 ───────────────────────────────────────────────────────────────

class BalloonRenderer:

    def __init__(self, cx, cy, max_rx, max_ry, fill, stroke, target):
        self.cx, self.cy     = cx, cy
        self.max_rx, self.max_ry = max_rx, max_ry
        self.min_rx = max_rx // 6
        self.min_ry = max_ry // 6
        self.fill, self.stroke, self.target = fill, stroke, target

    def _rx_ry(self, scale):
        rx = int(lerp(self.min_rx, self.max_rx, scale))
        ry = int(lerp(self.min_ry, self.max_ry, scale))
        return max(rx, 2), max(ry, 2)

    def draw_guides(self, surface, target_scale, font_small, target_kg):
        """목표 크기 점선 + 펑 한계 링"""
        # 펑 한계 (바깥 링)
        pr_rect = pygame.Rect(self.cx - self.max_rx, self.cy - self.max_ry,
                              self.max_rx * 2, self.max_ry * 2)
        draw_dashed_ellipse(surface, (*C.BAR_POP, 70), pr_rect, width=1, dash=5, gap=5)

        # 목표 점선 타원
        trx, try_ = self._rx_ry(target_scale)
        tr = pygame.Rect(self.cx - trx, self.cy - try_, trx * 2, try_ * 2)
        tgt_s = pygame.Surface((trx * 2, try_ * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(tgt_s, (*self.fill, 35), tgt_s.get_rect())
        surface.blit(tgt_s, tr.topleft)
        draw_dashed_ellipse(surface, (*self.target, 180), tr, width=2, dash=9, gap=6)

        # kg 라벨
        lbl = font_small.render(f"목표 {target_kg:.0f}kg", True, self.target)
        surface.blit(lbl, (self.cx - lbl.get_width() // 2, self.cy - try_ - 22))

    def draw(self, surface, scale, hand: HandData, t: float):
        """실제 풍선. POPPED / RELEASE 상태에는 그리지 않음."""
        if hand.state in (HandState.POPPED, HandState.RELEASE):
            return

        rx, ry = self._rx_ry(scale)

        # OVER 상태: 빨갛게 + 살짝 진동
        if hand.state == HandState.OVER:
            pulse = int(4 * abs(math.sin(t * 8)))
            rx += pulse; ry += pulse
            fill   = C.POP_FILL
            stroke = C.POP_RING
        else:
            fill   = self.fill
            stroke = self.stroke

        rect = pygame.Rect(self.cx - rx, self.cy - ry, rx * 2, ry * 2)
        pygame.draw.ellipse(surface, fill,   rect)
        pygame.draw.ellipse(surface, stroke, rect, 2)

        # 광택
        srx = max(rx // 4, 3); sry = max(ry // 6, 2)
        ss = pygame.Surface((srx * 2, sry * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ss, (255, 255, 255, 100), ss.get_rect())
        surface.blit(ss, (self.cx - rx // 3 - srx, self.cy - ry // 2 - sry))

        # 매듭 + 실
        ky = self.cy + ry
        pygame.draw.arc(surface, stroke, pygame.Rect(self.cx - 5, ky - 2, 10, 7),
                        0, math.pi, 2)
        pygame.draw.line(surface, C.PANEL_BORDER, (self.cx, ky + 4), (self.cx, ky + 18), 1)

        # 성공 진행 호
        if hand.state == HandState.ON_TARGET and hand.hold_ratio > 0:
            self._draw_arc(surface, rx + 7, ry + 7, hand.hold_ratio, stroke)

    def _draw_arc(self, surface, rx, ry, ratio, color):
        sa = -math.pi / 2
        ea = sa + 2 * math.pi * ratio
        steps = max(int(60 * ratio), 2)
        prev = None
        for i in range(steps + 1):
            a = lerp(sa, ea, i / steps)
            pt = (int(self.cx + rx * math.cos(a)), int(self.cy + ry * math.sin(a)))
            if prev:
                pygame.draw.line(surface, color, prev, pt, 3)
            prev = pt


# ── 파티클 ────────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = float(x), float(y)
        a = random.uniform(0, math.tau)
        v = random.uniform(90, 200)
        self.vx, self.vy = math.cos(a) * v, math.sin(a) * v
        self.color = color
        self.life  = 1.0
        self.r     = random.randint(3, 7)

    def update(self, dt):
        self.x   += self.vx * dt
        self.y   += self.vy * dt
        self.vy  += 220 * dt
        self.life -= dt * 1.6

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = int(255 * self.life)
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x) - self.r, int(self.y) - self.r))


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────

class GameRenderer:

    SCREEN_W  = 800
    SCREEN_H  = 560
    PANEL_W   = 340
    PANEL_H   = 420
    PANEL_Y   = 55
    L_PANEL_X = 28
    R_PANEL_X = SCREEN_W - PANEL_W - 28

    BALLOON_CX = PANEL_W // 2
    BALLOON_CY = 148
    MAX_RX, MAX_RY = 88, 108

    # 그립 바 (패널 내부 좌표)
    BAR_X = 18
    BAR_Y = 330
    BAR_W = PANEL_W - 36
    BAR_H = 22

    def __init__(self, config: GameConfig):
        self.cfg      = config
        self.particles: list[Particle] = []
        self._start_t = time.time()
        pygame.font.init()

        self.fn_large  = _load_font(28)
        self.fn_title  = _load_font(22)
        self.fn_body   = _load_font(16)
        self.fn_small  = _load_font(13)
        self.fn_tip    = _load_font(12)

        kw = dict(fill=C.L_FILL, stroke=C.L_STROKE, target=C.L_TARGET)
        self.bal_l = BalloonRenderer(self.BALLOON_CX, self.BALLOON_CY,
                                     self.MAX_RX, self.MAX_RY, **kw)
        kw = dict(fill=C.R_FILL, stroke=C.R_STROKE, target=C.R_TARGET)
        self.bal_r = BalloonRenderer(self.BALLOON_CX, self.BALLOON_CY,
                                     self.MAX_RX, self.MAX_RY, **kw)

    # ── 파티클 API ─────────────────────────────────────────────────────────

    def spawn_pop(self, cx_screen, cy_screen, is_left: bool):
        colors = ([C.L_STROKE, C.L_FILL, C.L_TARGET] if is_left
                  else [C.R_STROKE, C.R_FILL, C.R_TARGET])
        for _ in range(18):
            self.particles.append(Particle(cx_screen, cy_screen, random.choice(colors)))

    # ── 메인 draw ──────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, game: BalloonGame, dt: float):
        surface.fill(C.BG)

        # 파티클 갱신
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update(dt)

        t = time.time() - self._start_t

        self._draw_header(surface)

        l_surf = self._draw_panel(game, game.left,
                                  game.balloon_scale(game.left.grip_kg),
                                  is_left=True, t=t)
        surface.blit(l_surf, (self.L_PANEL_X, self.PANEL_Y))

        r_surf = self._draw_panel(game, game.right,
                                  game.balloon_scale(game.right.grip_kg),
                                  is_left=False, t=t)
        surface.blit(r_surf, (self.R_PANEL_X, self.PANEL_Y))

        for p in self.particles:
            p.draw(surface)

        self._draw_score(surface, game)

        # 시작 후 5초간 안내 오버레이
        if t < 5.0:
            self._draw_intro(surface, t)

    # ── 헤더 ───────────────────────────────────────────────────────────────

    def _draw_header(self, surface):
        title = self.fn_title.render("풍선 키우기 — 악력 재활 게임", True, C.TEXT_PRI)
        surface.blit(title, (self.SCREEN_W // 2 - title.get_width() // 2, 14))
        sub = self.fn_small.render(
            f"목표 {self.cfg.target_kg:.0f}kg  ±{self.cfg.tolerance_kg:.0f}kg 범위를  "
            f"{self.cfg.success_sec:.0f}초 유지하면 성공!   |   "
            f"{self.cfg.pop_kg:.0f}kg 이상이면 펑!",
            True, C.TEXT_SEC,
        )
        surface.blit(sub, (self.SCREEN_W // 2 - sub.get_width() // 2, 38))

    # ── 패널 ───────────────────────────────────────────────────────────────

    def _draw_panel(self, game: BalloonGame, hand: HandData,
                    scale: float, *, is_left: bool, t: float) -> pygame.Surface:
        surf = pygame.Surface((self.PANEL_W, self.PANEL_H), pygame.SRCALPHA)
        draw_rrect(surf, C.PANEL_BG,
                   pygame.Rect(0, 0, self.PANEL_W, self.PANEL_H),
                   r=16, border=1, bc=C.PANEL_BORDER)

        br = self.bal_l if is_left else self.bal_r
        target_scale = game.balloon_scale(self.cfg.target_kg)

        # 가이드 점선 + 실제 풍선
        br.draw_guides(surf, target_scale, self.fn_small, self.cfg.target_kg)
        br.draw(surf, scale, hand, t)

        # POPPED / RELEASE 텍스트
        if hand.state == HandState.POPPED:
            txt = self.fn_large.render("펑! 💥", True, C.OVER_FG)
            surf.blit(txt, (self.PANEL_W // 2 - txt.get_width() // 2,
                            self.BALLOON_CY - 16))
        elif hand.state == HandState.RELEASE:
            txt = self.fn_body.render("손 놓아주세요", True, C.REL_FG)
            surf.blit(txt, (self.PANEL_W // 2 - txt.get_width() // 2,
                            self.BALLOON_CY - 10))

        # 손 라벨
        label = "왼손" if is_left else "오른손"
        lbl = self.fn_body.render(label, True, C.TEXT_SEC)
        surf.blit(lbl, (self.PANEL_W // 2 - lbl.get_width() // 2, 10))

        # 현재 kg
        kg_txt = self.fn_large.render(f"{hand.grip_kg:.1f} kg", True, C.TEXT_PRI)
        surf.blit(kg_txt, (self.PANEL_W // 2 - kg_txt.get_width() // 2,
                           self.BALLOON_CY + self.MAX_RY + 14))

        # 그립 구간 바
        self._draw_grip_bar(surf, hand)

        # 상태 뱃지
        self._draw_badge(surf, hand,
                         self.PANEL_W // 2, self.BAR_Y + self.BAR_H + 12)

        # 유지 진행 바 (ON_TARGET)
        if hand.state == HandState.ON_TARGET and hand.hold_ratio > 0:
            self._draw_hold_bar(surf, hand.hold_ratio,
                                self.BAR_X, self.PANEL_H - 22,
                                self.BAR_W, 8)

        # 성공 카운트
        if hand.success_count > 0:
            cnt = self.fn_small.render(f"성공 {hand.success_count}회", True, C.GOOD_FG)
            surf.blit(cnt, (self.PANEL_W // 2 - cnt.get_width() // 2, self.PANEL_H - 18))

        return surf

    # ── 그립 구간 바 ────────────────────────────────────────────────────────

    def _draw_grip_bar(self, surf, hand: HandData):
        """
        0 ────[filling]──[  TARGET ZONE  ]──[OVER]──[POP] ────
                                  ▲ 현재 위치
        """
        x, y, w, h = self.BAR_X, self.BAR_Y, self.BAR_W, self.BAR_H
        pop_kg = self.cfg.pop_kg
        lo = self.cfg.target_kg - self.cfg.tolerance_kg
        hi = self.cfg.target_kg + self.cfg.tolerance_kg

        def px(kg):
            return x + int(w * min(kg, pop_kg) / pop_kg)

        # 배경
        draw_rrect(surf, C.BAR_BG, pygame.Rect(x, y, w, h), r=5)

        # 채우기 구간: 0 ~ lo (연한 파랑/주황)
        fill_color = (180, 210, 245) if hand.state != HandState.POPPED else C.BAR_BG
        fend = px(lo)
        draw_rrect(surf, fill_color, pygame.Rect(x, y, fend - x, h), r=5)

        # 목표 구간: lo ~ hi (녹색)
        t_x = px(lo); t_w = px(hi) - px(lo)
        pygame.draw.rect(surf, C.BAR_FILL, pygame.Rect(t_x, y, t_w, h))

        # 초과 구간: hi ~ pop_kg (주황)
        o_x = px(hi); o_w = px(pop_kg) - px(hi)
        pygame.draw.rect(surf, C.BAR_OVER, pygame.Rect(o_x, y, o_w, h))

        # 펑 마커 (바 오른쪽 끝에 빨간 세로선)
        pop_x = px(pop_kg)
        pygame.draw.rect(surf, C.BAR_POP, pygame.Rect(pop_x - 3, y - 2, 6, h + 4),
                         border_radius=2)

        # 구간 라벨
        lbl_lo = self.fn_tip.render(f"{lo:.0f}", True, C.TEXT_SEC)
        lbl_hi = self.fn_tip.render(f"{hi:.0f}", True, C.TEXT_SEC)
        lbl_pk = self.fn_tip.render("펑", True, C.BAR_POP)
        surf.blit(lbl_lo, (px(lo) - lbl_lo.get_width() // 2, y + h + 2))
        surf.blit(lbl_hi, (px(hi) - lbl_hi.get_width() // 2, y + h + 2))
        surf.blit(lbl_pk, (pop_x - lbl_pk.get_width() // 2, y - lbl_pk.get_height() - 2))

        # 현재 위치 커서 (삼각형)
        kg = min(hand.grip_kg, pop_kg)
        cur_x = x + int(w * kg / pop_kg)
        tri = [(cur_x, y - 2), (cur_x - 5, y - 10), (cur_x + 5, y - 10)]
        pygame.draw.polygon(surf, C.BAR_CURSOR, tri)

        # 바 테두리
        pygame.draw.rect(surf, C.PANEL_BORDER, pygame.Rect(x, y, w, h), 1, border_radius=5)

    # ── 상태 뱃지 ──────────────────────────────────────────────────────────

    def _draw_badge(self, surf, hand: HandData, cx, y):
        STATE_INFO = {
            HandState.IDLE:      ("악력을 가해주세요",         C.IDLE_BG, C.IDLE_FG),
            HandState.FILLING:   ("더 세게 쥐어주세요! →",     C.WARN_BG, C.WARN_FG),
            HandState.ON_TARGET: ("딱 좋아요! 유지하세요 ✓",   C.GOOD_BG, C.GOOD_FG),
            HandState.OVER:      ("너무 세요! 살짝 풀어주세요", C.OVER_BG, C.OVER_FG),
            HandState.POPPED:    ("펑! 잠시 기다리세요...",     C.OVER_BG, C.OVER_FG),
            HandState.RELEASE:   ("손을 완전히 놓아주세요",     C.REL_BG,  C.REL_FG),
        }
        text, bg, fg = STATE_INFO.get(hand.state, ("", C.IDLE_BG, C.IDLE_FG))
        txt = self.fn_small.render(text, True, fg)
        bw, bh = txt.get_width() + 24, 26
        rect = pygame.Rect(cx - bw // 2, y, bw, bh)
        draw_rrect(surf, bg, rect, r=13)
        surf.blit(txt, (cx - txt.get_width() // 2, y + (bh - txt.get_height()) // 2))

    # ── 유지 진행 바 ────────────────────────────────────────────────────────

    def _draw_hold_bar(self, surf, ratio, x, y, w, h):
        draw_rrect(surf, C.PANEL_BORDER, pygame.Rect(x, y, w, h), r=4)
        fill_w = max(int(w * ratio), 0)
        if fill_w > 0:
            draw_rrect(surf, C.GOOD_FG, pygame.Rect(x, y, fill_w, h), r=4)

    # ── 스코어 ─────────────────────────────────────────────────────────────

    def _draw_score(self, surface, game: BalloonGame):
        y = self.PANEL_Y + self.PANEL_H + 16
        items = [
            ("총 성공", str(game.total_success)),
            ("총 펑",   str(game.total_pop)),
            ("왼손 현재", f"{game.left.grip_kg:.1f} kg"),
            ("오른손 현재", f"{game.right.grip_kg:.1f} kg"),
        ]
        tw = 680
        sx = self.SCREEN_W // 2 - tw // 2
        for i, (label, value) in enumerate(items):
            x = sx + i * (tw // len(items))
            vt = self.fn_large.render(value, True, C.TEXT_PRI)
            lt = self.fn_tip.render(label,  True, C.TEXT_SEC)
            cx = x + tw // len(items) // 2
            surface.blit(vt, (cx - vt.get_width() // 2, y))
            surface.blit(lt, (cx - lt.get_width() // 2, y + vt.get_height() + 2))

    # ── 시작 안내 오버레이 ────────────────────────────────────────────────

    def _draw_intro(self, surface, elapsed: float):
        alpha = int(215 * max(0.0, 1.0 - elapsed / 5.0))
        if alpha <= 0:
            return

        overlay = pygame.Surface((self.SCREEN_W, self.SCREEN_H))
        overlay.fill((245, 243, 238))

        lines = [
            ("악력 재활 게임",                                self.fn_large, C.TEXT_PRI),
            ("",                                              None,          None),
            ("① 손잡이를 쥐어 풍선을 키우세요",               self.fn_body,  C.TEXT_PRI),
            (f"② 점선(목표 {self.cfg.target_kg:.0f}kg) 크기에 맞추세요", self.fn_body, C.TEXT_PRI),
            (f"③ 그 크기를 {self.cfg.success_sec:.0f}초 유지하면 성공!", self.fn_body, C.GOOD_FG),
            (f"④ {self.cfg.pop_kg:.0f}kg 이상이면 풍선이 터집니다",     self.fn_body, C.OVER_FG),
            ("",                                              None,          None),
            ("하단 바에서 현재 힘의 위치를 확인하세요",        self.fn_small, C.TEXT_SEC),
        ]

        total_h = sum((f.get_height() + 6 if f else 12) for _, f, _ in lines)
        sy = self.SCREEN_H // 2 - total_h // 2

        for text, font, color in lines:
            if font is None:
                sy += 12
                continue
            rendered = font.render(text, True, color)
            overlay.blit(rendered, (self.SCREEN_W // 2 - rendered.get_width() // 2, sy))
            sy += font.get_height() + 6

        overlay.set_alpha(alpha)
        surface.blit(overlay, (0, 0))
