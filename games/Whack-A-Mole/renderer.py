"""
renderer.py — 두더지 잡기 Pygame 렌더러

화면 (800 × 620):
  ┌─────────────────────────┐
  │  HUD 점수 / 타이머 / 콤보  │  0 ~ 85
  ├─────────────────────────┤
  │  구멍 3개 + 두더지        │  85 ~ 440
  ├─────────────────────────┤
  │  악력 게이지              │  450 ~ 560
  └─────────────────────────┘
"""

import math
import os
import random
import time
import pygame

from game_logic import MoleStatus, WhackAMoleLogic, THRESHOLD_KG


# ── 색상 ──────────────────────────────────────────────────────────────────────

BG_DARK    = ( 15,  32,  15)
BG_MID     = ( 25,  50,  25)
GRASS      = ( 38,  90,  38)
SOIL       = ( 80,  55,  30)
HOLE_BG    = (  8,  15,   8)
HOLE_EDGE  = ( 50,  85,  50)
GREEN_HI   = ( 80, 220, 120)
BLUE_HI    = ( 80, 150, 255)
PURPLE_HI  = (180, 100, 255)
YELLOW_HI  = (255, 225,  50)
ORANGE_HI  = (255, 155,  40)
RED_HI     = (255,  70,  70)
WHITE      = (235, 255, 235)
MUTED      = ( 95, 135,  95)
HIT_FLASH  = (255, 240,  80)
MISS_COLOR = (255,  70,  70)

KIND_COLOR = {'left': BLUE_HI, 'both': PURPLE_HI, 'right': GREEN_HI}
KIND_LABEL = {'left': '왼손', 'both': '양손', 'right': '오른손'}

W, H = 800, 620

HOLE_CENTERS = [(155, 260), (400, 260), (645, 260)]
HOLE_RX, HOLE_RY = 95, 48   # 구멍 타원 반지름


# ── 폰트 ──────────────────────────────────────────────────────────────────────

def _load_font(size: int) -> pygame.font.Font:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    for name in ["applegothic", "nanumgothic", "malgun gothic", "gulim"]:
        try:
            f = pygame.font.SysFont(name, size)
            if f: return f
        except Exception:
            continue
    return pygame.font.SysFont(None, size)


# ── 파티클 ────────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y, color):
        a = random.uniform(0, math.tau)
        v = random.uniform(70, 200)
        self.x, self.y = float(x), float(y)
        self.vx = math.cos(a) * v
        self.vy = math.sin(a) * v - 60
        self.color = color
        self.life  = 1.0
        self.r     = random.randint(3, 8)

    def update(self, dt):
        self.x   += self.vx * dt
        self.y   += self.vy * dt
        self.vy  += 280 * dt
        self.life -= dt * 2.2

    @property
    def alive(self): return self.life > 0

    def draw(self, surf):
        if not self.alive: return
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, int(self.life * 255)), (self.r, self.r), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))


# ── 플래시 이펙트 ─────────────────────────────────────────────────────────────

class HoleFlash:
    def __init__(self, color, duration=0.3):
        self.color = color; self.life = duration; self.max_life = duration
    def update(self, dt): self.life -= dt
    @property
    def alive(self): return self.life > 0
    @property
    def alpha(self): return int((self.life / self.max_life) * 160)


# ── 팝업 텍스트 ───────────────────────────────────────────────────────────────

class PopText:
    def __init__(self, text, x, y, color, size=26):
        self.text = text
        self.x, self.y = float(x), float(y)
        self.color = color
        self.life  = 1.0
        self.size  = size

    def update(self, dt):
        self.y    -= 55 * dt
        self.life -= dt * 1.6

    @property
    def alive(self): return self.life > 0

    def draw(self, surf, font):
        if not self.alive: return
        rendered = font.render(self.text, True, self.color)
        rendered.set_alpha(max(0, int(self.life * 255)))
        surf.blit(rendered, (int(self.x) - rendered.get_width() // 2, int(self.y)))


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()

        self.font_lg  = _load_font(42)
        self.font_md  = _load_font(26)
        self.font_sm  = _load_font(18)
        self.font_xs  = _load_font(14)
        self.font_hud = _load_font(34)
        self.font_pop = _load_font(28)

        self.particles:  list[Particle] = []
        self.pop_texts:  list[PopText]  = []
        self.hole_flash: list           = [None, None, None]
        self.hit_anim:   list[float]    = [0.0, 0.0, 0.0]
        self.miss_anim:  list[float]    = [0.0, 0.0, 0.0]  # 놓친 두더지 X 표시
        self._start_t   = time.time()

    # ── 이벤트 처리 ────────────────────────────────────────────────────────

    def handle_event(self, ev: str):
        if ev.startswith("hit:"):
            parts  = ev.split(":")
            i      = int(parts[1])
            pts    = int(parts[2]) if len(parts) > 2 else 10
            cx, cy = HOLE_CENTERS[i]
            self.hole_flash[i] = HoleFlash(HIT_FLASH)
            self.hit_anim[i]   = 1.0
            col = KIND_COLOR.get('both', YELLOW_HI)  # 파티클 색은 노랑 계열
            for _ in range(22):
                self.particles.append(Particle(cx, cy - 80, YELLOW_HI))
            label = f"+{pts}" if pts == 10 else f"+{pts} ★"
            self.pop_texts.append(PopText(label, cx, cy - 110, YELLOW_HI, 30))

        elif ev.startswith("missed:"):
            i = int(ev.split(":")[1])
            self.hole_flash[i] = HoleFlash(MISS_COLOR, 0.5)
            self.miss_anim[i]  = 1.0
            cx, cy = HOLE_CENTERS[i]
            self.pop_texts.append(PopText("놓쳤다!", cx, cy - 110, MISS_COLOR, 22))

        elif ev.startswith("combo:"):
            c  = ev.split(":")[1]
            cx = W // 2
            self.pop_texts.append(PopText(f"{c} COMBO!", cx, 95, YELLOW_HI, 36))

    # ── 메인 draw ──────────────────────────────────────────────────────────

    def draw(self, logic: WhackAMoleLogic, left_kg: float, right_kg: float, dt: float):
        s  = logic.state
        sc = self.screen

        # 배경
        sc.fill(BG_DARK)
        # 잔디 라인
        pygame.draw.rect(sc, GRASS,  (0, 320, W, 12))
        pygame.draw.rect(sc, SOIL,   (0, 332, W, 80))
        pygame.draw.rect(sc, BG_MID, (0,  0,  W, 86))
        pygame.draw.line(sc, HOLE_EDGE, (0, 86), (W, 86), 1)

        self._draw_hud(s)
        self._draw_holes(s, dt)
        self._draw_grip_bars(left_kg, right_kg)
        self._draw_particles(dt)
        self._draw_pop_texts(dt)

        if s.finished:
            self._draw_game_over(s)
        elif not s.running:
            self._draw_start_screen()

    # ── HUD ────────────────────────────────────────────────────────────────

    def _draw_hud(self, s):
        sc = self.screen
        self._hud_box(sc, 18,  8, 140, 68, "점수", str(s.score),    WHITE)
        tl  = int(s.time_left)
        col = RED_HI if tl <= 10 else (ORANGE_HI if tl <= 20 else WHITE)
        self._hud_box(sc, W - 158, 8, 140, 68, "남은 시간", f"{tl}초", col)

        if s.combo >= 3:
            fire = "🔥" * min(s.combo // 3, 3)
            t = self.font_md.render(f"{fire} {s.combo} COMBO! {fire}", True, YELLOW_HI)
            sc.blit(t, (W // 2 - t.get_width() // 2, 28))

    def _hud_box(self, sc, x, y, w, h, label, value, col):
        pygame.draw.rect(sc, (0, 0, 0), (x, y, w, h), border_radius=10)
        pygame.draw.rect(sc, HOLE_EDGE, (x, y, w, h), 1, border_radius=10)
        lb = self.font_xs.render(label, True, MUTED)
        sc.blit(lb, (x + w // 2 - lb.get_width() // 2, y + 7))
        vb = self.font_hud.render(value, True, col)
        sc.blit(vb, (x + w // 2 - vb.get_width() // 2, y + 30))

    # ── 구멍 + 두더지 ──────────────────────────────────────────────────────

    def _draw_holes(self, s, dt):
        sc = self.screen
        labels    = ['왼쪽 구멍\n(왼손)', '가운데 구멍\n(양손)', '오른쪽 구멍\n(오른손)']
        lbl_colors = [BLUE_HI, PURPLE_HI, GREEN_HI]

        for i, (cx, cy) in enumerate(HOLE_CENTERS):
            mole  = s.moles[i]
            flash = self.hole_flash[i]

            # hit/miss 애니메이션 감쇠
            self.hit_anim[i]  = max(0.0, self.hit_anim[i]  - dt * 6)
            self.miss_anim[i] = max(0.0, self.miss_anim[i] - dt * 2)

            # 구멍 테두리 색상
            edge_col = HOLE_EDGE
            if mole and mole.status == MoleStatus.UP:
                edge_col = KIND_COLOR[mole.kind]

            # 구멍 타원 (깊이감)
            pygame.draw.ellipse(sc, (5, 10, 5),
                (cx - HOLE_RX - 2, cy - HOLE_RY + 6, (HOLE_RX + 2) * 2, HOLE_RY * 2 + 4))
            pygame.draw.ellipse(sc, HOLE_BG,
                (cx - HOLE_RX, cy - HOLE_RY, HOLE_RX * 2, HOLE_RY * 2))
            pygame.draw.ellipse(sc, edge_col,
                (cx - HOLE_RX, cy - HOLE_RY, HOLE_RX * 2, HOLE_RY * 2), 3)

            # 플래시
            if flash:
                flash.update(dt)
                if flash.alive:
                    ov = pygame.Surface((HOLE_RX * 2, HOLE_RY * 2), pygame.SRCALPHA)
                    ov.fill((*flash.color, flash.alpha))
                    sc.blit(ov, (cx - HOLE_RX, cy - HOLE_RY))
                else:
                    self.hole_flash[i] = None

            # 두더지
            if mole and mole.status in (MoleStatus.UP, MoleStatus.HIT):
                self._draw_mole(sc, cx, cy, mole, i)

            # 놓친 두더지 X 표시
            if self.miss_anim[i] > 0:
                self._draw_miss_x(sc, cx, cy - 60, self.miss_anim[i])

            # 타이머 바
            if mole and mole.status == MoleStatus.UP:
                self._draw_timer_bar(sc, cx, cy, mole)

            # 구멍 라벨 (두 줄)
            for j, line in enumerate(labels[i].split('\n')):
                lb = self.font_xs.render(line, True, lbl_colors[i])
                sc.blit(lb, (cx - lb.get_width() // 2, cy + HOLE_RY + 8 + j * 18))

    def _draw_mole(self, sc, cx, cy, mole, hole_idx):
        anim  = self.hit_anim[hole_idx]
        scale = 1.0 + anim * 0.22
        body_r = int(42 * scale)

        is_hit = mole.status == MoleStatus.HIT
        col    = HIT_FLASH if is_hit else KIND_COLOR[mole.kind]

        head_y = cy - 55

        # 귀 (몸체보다 먼저 그림)
        ear_r = body_r // 3
        ear_col = tuple(max(0, c - 40) for c in col)
        pygame.draw.circle(sc, ear_col, (cx - body_r // 2, head_y - body_r + ear_r // 2), ear_r)
        pygame.draw.circle(sc, ear_col, (cx + body_r // 2, head_y - body_r + ear_r // 2), ear_r)
        # 귀 안쪽 (밝은 색)
        inner = tuple(min(255, c + 40) for c in col)
        pygame.draw.circle(sc, inner, (cx - body_r // 2, head_y - body_r + ear_r // 2), ear_r // 2)
        pygame.draw.circle(sc, inner, (cx + body_r // 2, head_y - body_r + ear_r // 2), ear_r // 2)

        # 몸통 (타원)
        body_rect = pygame.Rect(cx - body_r, head_y - body_r, body_r * 2, int(body_r * 2.1))
        pygame.draw.ellipse(sc, col, body_rect)
        pygame.draw.ellipse(sc, tuple(max(0, c - 50) for c in col), body_rect, 2)

        # 배 (밝은 타원)
        belly_col = tuple(min(255, c + 60) for c in col)
        belly_r   = body_r // 2
        pygame.draw.ellipse(sc, belly_col,
            (cx - belly_r, head_y - belly_r + 10, belly_r * 2, int(belly_r * 1.4)))

        # 눈
        ew   = max(4, body_r // 7)
        ey   = head_y - body_r // 2
        if is_hit:
            # 히트 시 X 눈
            for dx in (-ew * 2, ew * 2):
                ex = cx + dx
                pygame.draw.line(sc, BG_DARK, (ex - ew, ey - ew), (ex + ew, ey + ew), 2)
                pygame.draw.line(sc, BG_DARK, (ex - ew, ey + ew), (ex + ew, ey - ew), 2)
        else:
            pygame.draw.circle(sc, BG_DARK,   (cx - ew * 2, ey), ew)
            pygame.draw.circle(sc, BG_DARK,   (cx + ew * 2, ey), ew)
            pygame.draw.circle(sc, WHITE,     (cx - ew * 2 - 1, ey - 1), ew // 3)
            pygame.draw.circle(sc, WHITE,     (cx + ew * 2 - 1, ey - 1), ew // 3)

        # 코
        nose_y = head_y
        pygame.draw.ellipse(sc, (210, 90, 90), (cx - ew, nose_y - ew // 2, ew * 2, ew))

        # 수염
        for sign, dx in [(1, 14), (1, 18), (-1, 14), (-1, 18)]:
            sx = cx + sign * ew
            pygame.draw.line(sc, tuple(max(0, c - 60) for c in col),
                (sx, nose_y),
                (sx + sign * dx, nose_y - 3 if dx == 14 else nose_y + 1), 1)

        # 종류 배지
        badge_col = KIND_COLOR[mole.kind]
        badge_txt = self.font_xs.render(KIND_LABEL[mole.kind], True, BG_DARK)
        bw = badge_txt.get_width() + 12
        bh = 20
        bx = cx - bw // 2
        by = head_y - body_r - ear_r - bh - 4
        pygame.draw.rect(sc, badge_col, (bx, by, bw, bh), border_radius=7)
        sc.blit(badge_txt, (bx + 6, by + 3))

    def _draw_miss_x(self, sc, cx, cy, ratio):
        alpha = int(ratio * 200)
        size  = int(28 * ratio)
        if size < 2: return
        s = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
        r = (255, 70, 70, alpha)
        pygame.draw.line(s, r, (2, 2), (size * 2, size * 2), 4)
        pygame.draw.line(s, r, (size * 2, 2), (2, size * 2), 4)
        sc.blit(s, (cx - size, cy - size))

    def _draw_timer_bar(self, sc, cx, cy, mole):
        bw, bh = 130, 7
        bx = cx - bw // 2
        by = cy + HOLE_RY + 2
        pygame.draw.rect(sc, (30, 55, 30), (bx, by, bw, bh), border_radius=4)
        fw = int(bw * mole.time_ratio)
        if fw > 0:
            col = RED_HI if mole.time_ratio < 0.25 else (ORANGE_HI if mole.time_ratio < 0.5 else KIND_COLOR[mole.kind])
            pygame.draw.rect(sc, col, (bx, by, fw, bh), border_radius=4)

    # ── 악력 게이지 ────────────────────────────────────────────────────────

    def _draw_grip_bars(self, left_kg: float, right_kg: float):
        sc   = self.screen
        by0  = 465
        bh   = 32
        bpad = 55
        bw   = (W - bpad * 2 - 24) // 2
        max_kg = 20.0

        infos = [
            (left_kg,  "왼손  [ A: 쥐기 / S: 강하게 ]",  BLUE_HI,  bpad),
            (right_kg, "오른손 [ K: 쥐기 / L: 강하게 ]", GREEN_HI, bpad + bw + 24),
        ]
        for kg, label, col, bx in infos:
            lb = self.font_xs.render(label, True, MUTED)
            sc.blit(lb, (bx, by0 - 20))

            pygame.draw.rect(sc, (15, 35, 15), (bx, by0, bw, bh), border_radius=8)
            pygame.draw.rect(sc, HOLE_EDGE,    (bx, by0, bw, bh), 1, border_radius=8)

            fw = int(bw * min(1.0, kg / max_kg))
            if fw > 0:
                c = YELLOW_HI if kg >= THRESHOLD_KG else col
                pygame.draw.rect(sc, c, (bx, by0, fw, bh), border_radius=8)

            # 임계값 선 + 라벨
            tx = bx + int(bw * THRESHOLD_KG / max_kg)
            pygame.draw.line(sc, WHITE, (tx, by0 - 6), (tx, by0 + bh + 6), 2)
            tl = self.font_xs.render(f"{THRESHOLD_KG:.0f}kg", True, WHITE)
            sc.blit(tl, (tx - tl.get_width() // 2, by0 + bh + 7))

            val = self.font_sm.render(f"{kg:.1f} kg", True, WHITE)
            sc.blit(val, (bx + bw - val.get_width() - 6, by0 + (bh - val.get_height()) // 2))

    # ── 파티클 / 팝업 ──────────────────────────────────────────────────────

    def _draw_particles(self, dt):
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update(dt)
            p.draw(self.screen)

    def _draw_pop_texts(self, dt):
        self.pop_texts = [t for t in self.pop_texts if t.alive]
        for t in self.pop_texts:
            t.update(dt)
            t.draw(self.screen, self.font_pop)

    # ── 오버레이 ───────────────────────────────────────────────────────────

    def _draw_start_screen(self):
        sc = self.screen
        ov = pygame.Surface((W, H))
        ov.fill(BG_DARK)
        ov.set_alpha(210)
        sc.blit(ov, (0, 0))

        title = self.font_lg.render("두더지 잡기", True, GREEN_HI)
        sub   = self.font_md.render("악력 재활 게임", True, MUTED)
        sc.blit(title, (W // 2 - title.get_width() // 2, 140))
        sc.blit(sub,   (W // 2 - sub.get_width() // 2,   192))

        # 조작 설명
        controls = [
            (BLUE_HI,   "왼손  → A 키(쥐기)  /  S 키(강하게)"),
            (GREEN_HI,  "오른손 → K 키(쥐기)  /  L 키(강하게)"),
            (PURPLE_HI, "가운데 구멍은 양손 동시에!"),
        ]
        for j, (col, txt) in enumerate(controls):
            t = self.font_sm.render(txt, True, col)
            sc.blit(t, (W // 2 - t.get_width() // 2, 260 + j * 34))

        # 구멍 색상 범례
        legend = [
            (BLUE_HI,   "● 왼쪽 = 왼손"),
            (PURPLE_HI, "● 가운데 = 양손"),
            (GREEN_HI,  "● 오른쪽 = 오른손"),
        ]
        for j, (col, txt) in enumerate(legend):
            t = self.font_xs.render(txt, True, col)
            sc.blit(t, (W // 2 - t.get_width() // 2, 380 + j * 24))

        hint = self.font_md.render("[ Space ] 키를 눌러 시작!", True, YELLOW_HI)
        sc.blit(hint, (W // 2 - hint.get_width() // 2, 460))

    def _draw_game_over(self, s):
        sc  = self.screen
        ov  = pygame.Surface((W, H))
        ov.fill(BG_DARK)
        ov.set_alpha(200)
        sc.blit(ov, (0, 0))

        title = self.font_lg.render("게임 종료!", True, GREEN_HI)
        sc.blit(title, (W // 2 - title.get_width() // 2, 100))

        total = s.hits + s.misses
        acc   = int(s.hits / total * 100) if total else 0
        grade, gcol = self._grade(acc, s.score)

        gtext = self.font_lg.render(grade, True, gcol)
        sc.blit(gtext, (W // 2 - gtext.get_width() // 2, 155))

        stats = [
            ("점수",    str(s.score),        WHITE),
            ("잡은 수", str(s.hits),          GREEN_HI),
            ("놓친 수", str(s.misses),        MISS_COLOR),
            ("정확도",  f"{acc}%",            YELLOW_HI),
            ("최대 콤보", str(s.max_combo),   ORANGE_HI),
        ]
        box_w, box_h = 120, 82
        total_w = len(stats) * (box_w + 12) - 12
        sx = W // 2 - total_w // 2
        for j, (lbl, val, col) in enumerate(stats):
            bx = sx + j * (box_w + 12)
            by = 230
            pygame.draw.rect(sc, (20, 45, 20), (bx, by, box_w, box_h), border_radius=10)
            pygame.draw.rect(sc, HOLE_EDGE,    (bx, by, box_w, box_h), 1, border_radius=10)
            lt = self.font_xs.render(lbl, True, MUTED)
            vt = self.font_md.render(val, True, col)
            sc.blit(lt, (bx + box_w // 2 - lt.get_width() // 2, by + 10))
            sc.blit(vt, (bx + box_w // 2 - vt.get_width() // 2, by + 38))

        hint = self.font_sm.render("[ R ] 다시 하기     [ Q ] 종료", True, MUTED)
        sc.blit(hint, (W // 2 - hint.get_width() // 2, 348))

    def _grade(self, acc: int, score: int):
        if acc >= 90 and score >= 150: return "S 등급 🏆", YELLOW_HI
        if acc >= 75 and score >= 100: return "A 등급 ★",  GREEN_HI
        if acc >= 55:                  return "B 등급",     BLUE_HI
        if acc >= 35:                  return "C 등급",     MUTED
        return "D 등급",                                     MISS_COLOR
