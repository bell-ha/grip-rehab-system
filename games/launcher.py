"""
launcher.py
게임 선택 메뉴 — 악력으로 조작

조작법:
    왼손 2초 유지  → 커서 왼쪽 이동
    오른손 2초 유지 → 커서 오른쪽 이동
    양손 동시 2초  → 선택 실행

버튼: 풍선 키우기 / 두더지 잡기 / 나가기

실행:
    python launcher.py           # Mock 모드
    python launcher.py --arduino # Arduino 센서
    python launcher.py --real    # Raspberry Pi HX711
"""

import sys
import os
import math
import time
import subprocess
import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from common.sensor import MockGripSensor, RealGripSensor, ArduinoGripSensor

# ── 설정 ──────────────────────────────────────────────────────────────────────

W, H         = 800, 480
FPS          = 60
HOLD_SEC     = 0.3
THRESHOLD_KG = 6.0

GAMES = [
    {
        "label":  "풍선 키우기",
        "desc":   "목표 악력을 유지해서\n풍선을 키워요",
        "emoji":  "🎈",
        "path":   "balloon_game/main.py",
        "color":  (255, 153,  51),
        "border": (200,  64,   0),
    },
    {
        "label":  "두더지 잡기",
        "desc":   "두더지가 나타나면\n해당 손으로 잡아요",
        "emoji":  "🐭",
        "path":   "Whack-A-Mole/main.py",
        "color":  ( 68, 153, 255),
        "border": ( 20,  80, 200),
    },
    {
        "label":  "나가기",
        "desc":   "게임을 종료합니다",
        "emoji":  "👋",
        "path":   None,
        "color":  (160, 160, 170),
        "border": (100, 100, 115),
    },
]

# ── 색상 ──────────────────────────────────────────────────────────────────────

SKY_TOP  = (140, 200, 255)
SKY_MID  = (200, 235, 255)
GRASS_HI = (122, 204,  68)
GRASS_LO = ( 90, 170,  40)
SOIL_COL = (160, 113,  42)
CLOUD_C  = (230, 248, 255)

TEXT_MAIN = ( 30,  30,  28)
TEXT_SUB  = (100,  98,  90)
TEXT_DARK = ( 20,  70,  10)
WHITE     = (255, 255, 255)
MUTED     = ( 60, 120,  30)

BAR_L    = ( 68, 153, 255)
BAR_R    = ( 68, 200,  80)
BAR_BOTH = (255, 210,  60)
BAR_BG_C = (200, 230, 160)

# ── 폰트 ──────────────────────────────────────────────────────────────────────

def _load_font(size):
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
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


# ── 배경 ──────────────────────────────────────────────────────────────────────

def _draw_bg(surface):
    horizon = 170
    for y in range(horizon):
        t = y / horizon
        c = tuple(int(SKY_TOP[i] + (SKY_MID[i] - SKY_TOP[i]) * t) for i in range(3))
        pygame.draw.line(surface, c, (0, y), (W, y))
    pygame.draw.rect(surface, GRASS_HI, (0, horizon,      W, 50))
    pygame.draw.rect(surface, GRASS_LO, (0, horizon + 50, W, 30))
    pygame.draw.rect(surface, SOIL_COL, (0, horizon + 80, W, H - horizon - 80))


def _draw_clouds(surface):
    clouds = [
        [(105, 43, 32, 19), (128, 34, 30, 17), (152, 41, 27, 16), (123, 50, 36, 18)],
        [(590, 37, 30, 18), (613, 27, 32, 18), (635, 35, 28, 16), (605, 44, 34, 17)],
        [(368, 22, 28, 16), (392, 15, 30, 17), (415, 21, 26, 15), (388, 30, 32, 16)],
    ]
    for cloud in clouds:
        for cx, cy, rx, ry in cloud:
            pygame.draw.ellipse(surface, CLOUD_C, (cx - rx, cy - ry, rx * 2, ry * 2))


# ── 메인 런처 ─────────────────────────────────────────────────────────────────

class Launcher:

    CARD_W   = 215
    CARD_H   = 228
    CARD_GAP = 14
    CARD_Y   = 68

    def __init__(self, screen, sensor):
        self.screen  = screen
        self.sensor  = sensor
        self.cursor  = 0
        self.n       = len(GAMES)

        self.left_held_t  = 0.0
        self.right_held_t = 0.0
        self.both_held_t  = 0.0
        self._moved = False

        pygame.font.init()
        self.fn_title = _load_font(34)
        self.fn_sub   = _load_font(16)
        self.fn_label = _load_font(27)
        self.fn_desc  = _load_font(17)
        self.fn_hint  = _load_font(15)
        self.fn_emoji = _load_font(46)
        self.fn_val   = _load_font(19)

        total = self.n * self.CARD_W + (self.n - 1) * self.CARD_GAP
        sx = W // 2 - total // 2
        self.card_xs = [sx + i * (self.CARD_W + self.CARD_GAP) for i in range(self.n)]

    def run(self):
        clock   = pygame.time.Clock()
        running = True
        result  = None

        while running:
            dt = clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if isinstance(self.sensor, MockGripSensor):
                        self.sensor.handle_keydown(event.key)
                    if event.key == pygame.K_ESCAPE:
                        return None
                    if event.key == pygame.K_LEFT:
                        self.cursor = (self.cursor - 1) % self.n
                    if event.key == pygame.K_RIGHT:
                        self.cursor = (self.cursor + 1) % self.n
                    if event.key == pygame.K_RETURN:
                        return self.cursor
                if event.type == pygame.KEYUP:
                    if isinstance(self.sensor, MockGripSensor):
                        self.sensor.handle_keyup(event.key)

            reading = self.sensor.get()
            left_kg, right_kg = reading.left_kg, reading.right_kg

            both       = left_kg >= THRESHOLD_KG and right_kg >= THRESHOLD_KG
            left_only  = left_kg  >= THRESHOLD_KG and not both
            right_only = right_kg >= THRESHOLD_KG and not both

            if both:
                self.both_held_t  += dt
                self.left_held_t   = 0.0
                self.right_held_t  = 0.0
                self._moved        = False
            elif left_only:
                self.left_held_t  += dt
                self.right_held_t  = 0.0
                self.both_held_t   = 0.0
            elif right_only:
                self.right_held_t += dt
                self.left_held_t   = 0.0
                self.both_held_t   = 0.0
            else:
                self.left_held_t   = 0.0
                self.right_held_t  = 0.0
                self.both_held_t   = 0.0
                self._moved        = False

            if self.both_held_t >= HOLD_SEC:
                result  = self.cursor
                running = False
            elif self.left_held_t >= HOLD_SEC and not self._moved:
                self.cursor      = (self.cursor - 1) % self.n
                self.left_held_t = 0.0
                self._moved      = True
            elif self.right_held_t >= HOLD_SEC and not self._moved:
                self.cursor       = (self.cursor + 1) % self.n
                self.right_held_t = 0.0
                self._moved       = True

            self._draw(left_kg, right_kg, left_only, right_only, both)
            pygame.display.flip()

        return result

    def _draw(self, left_kg, right_kg, left_only, right_only, both):
        sc = self.screen
        _draw_bg(sc)
        _draw_clouds(sc)

        # 제목 밴드 (반투명 흰색)
        band = pygame.Surface((W, 58), pygame.SRCALPHA)
        band.fill((255, 255, 255, 190))
        sc.blit(band, (0, 0))
        title = self.fn_title.render("악력 재활 게임", True, TEXT_MAIN)
        sc.blit(title, (W // 2 - title.get_width() // 2, 8))
        sub = self.fn_sub.render("손을 쥐어 게임을 선택하세요", True, TEXT_SUB)
        sc.blit(sub, (W // 2 - sub.get_width() // 2, 40))

        # 카드
        for i, game in enumerate(GAMES):
            self._draw_card(i, game)

        # 악력 게이지 패널
        self._draw_grip_bars(sc, left_kg, right_kg, left_only, right_only, both)

        # 힌트 밴드 (하단)
        hint_band = pygame.Surface((W, 36), pygame.SRCALPHA)
        hint_band.fill((255, 255, 255, 160))
        sc.blit(hint_band, (0, H - 36))
        hint = self.fn_hint.render(
            "왼손 2초 → 왼쪽 이동   │   오른손 2초 → 오른쪽 이동   │   양손 2초 → 선택",
            True, MUTED,
        )
        sc.blit(hint, (W // 2 - hint.get_width() // 2, H - 24))

    def _draw_card(self, i, game):
        sc  = self.screen
        sel = (i == self.cursor)
        x   = self.card_xs[i]
        y   = self.CARD_Y
        w   = self.CARD_W
        h   = self.CARD_H
        r   = 18

        # 카드 배경 (frosted glass)
        card_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        alpha = 215 if sel else 155
        pygame.draw.rect(card_surf, (255, 255, 255, alpha), (0, 0, w, h), border_radius=r)

        if sel:
            tint = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(tint, (*game["color"], 35), (0, 0, w, h), border_radius=r)
            card_surf.blit(tint, (0, 0))

        border_col = (*game["border"], 255) if sel else (180, 220, 140, 200)
        border_w   = 3 if sel else 1
        pygame.draw.rect(card_surf, border_col, (0, 0, w, h), border_w, border_radius=r)
        sc.blit(card_surf, (x, y))

        # 이모지
        em = self.fn_emoji.render(game["emoji"], True, TEXT_MAIN)
        sc.blit(em, (x + w // 2 - em.get_width() // 2, y + 16))

        # 라벨
        label_col = game["border"] if sel else TEXT_MAIN
        lb = self.fn_label.render(game["label"], True, label_col)
        sc.blit(lb, (x + w // 2 - lb.get_width() // 2, y + 78))

        # 설명
        desc_col = TEXT_SUB if sel else (140, 140, 130)
        for j, line in enumerate(game["desc"].split("\n")):
            d = self.fn_desc.render(line, True, desc_col)
            sc.blit(d, (x + w // 2 - d.get_width() // 2, y + 118 + j * 24))

        # 양손 유지 진행 바 (선택된 카드)
        if sel and self.both_held_t > 0:
            ratio = min(self.both_held_t / HOLD_SEC, 1.0)
            bx    = x + 14
            bw2   = w - 28
            by2   = y + h - 18
            pbg   = pygame.Surface((bw2, 8), pygame.SRCALPHA)
            pygame.draw.rect(pbg, (200, 230, 160, 180), (0, 0, bw2, 8), border_radius=4)
            sc.blit(pbg, (bx, by2))
            fw = int(bw2 * ratio)
            if fw > 0:
                pygame.draw.rect(sc, BAR_BOTH, (bx, by2, fw, 8), border_radius=4)

    def _draw_grip_bars(self, sc, left_kg, right_kg, left_only, right_only, both):
        # 반투명 패널 배경
        panel = pygame.Surface((W - 60, 86), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 130))
        sc.blit(panel, (30, 308))

        by0 = 336
        bh  = 26
        bw  = 285
        pad = 52

        ratio_l = min(self.left_held_t / HOLD_SEC, 1.0) if left_only else 0.0
        self._bar(sc, pad, by0, bw, bh, left_kg, BAR_L, ratio_l, "왼손")

        ratio_r = min(self.right_held_t / HOLD_SEC, 1.0) if right_only else 0.0
        self._bar(sc, W - pad - bw, by0, bw, bh, right_kg, BAR_R, ratio_r, "오른손")

    def _bar(self, sc, x, y, w, h, kg, color, hold_ratio, label):
        MAX_KG = 20.0

        lb = self.fn_hint.render(label, True, TEXT_DARK)
        sc.blit(lb, (x, y - 22))

        # 반투명 배경 바
        bar_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*BAR_BG_C, 180), (0, 0, w, h), border_radius=6)
        sc.blit(bar_surf, (x, y))

        # 채우기
        fw = int(w * min(kg / MAX_KG, 1.0))
        if fw > 0:
            c = BAR_BOTH if kg >= THRESHOLD_KG else color
            pygame.draw.rect(sc, c, (x, y, fw, h), border_radius=6)

        # 테두리
        bdr = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bdr, (255, 255, 255, 160), (0, 0, w, h), 1, border_radius=6)
        sc.blit(bdr, (x, y))

        # 임계값 선
        tx = x + int(w * THRESHOLD_KG / MAX_KG)
        pygame.draw.line(sc, WHITE, (tx, y - 3), (tx, y + h + 3), 2)

        # 유지 진행 바
        if hold_ratio > 0:
            py = y + h + 5
            hold_surf = pygame.Surface((w, 6), pygame.SRCALPHA)
            pygame.draw.rect(hold_surf, (*BAR_BG_C, 180), (0, 0, w, 6), border_radius=3)
            sc.blit(hold_surf, (x, py))
            fw2 = int(w * hold_ratio)
            if fw2 > 0:
                pygame.draw.rect(sc, BAR_BOTH, (x, py, fw2, 6), border_radius=3)

        # 수치
        val = self.fn_val.render(f"{kg:.1f} kg", True, TEXT_DARK)
        sc.blit(val, (x + w - val.get_width() - 6, y + (h - val.get_height()) // 2))


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    USE_ARDUINO = "--arduino" in sys.argv
    USE_REAL    = "--real"    in sys.argv

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("악력 재활 게임")

    if USE_REAL:
        try:
            sensor = RealGripSensor()
        except Exception as e:
            print(f"[센서] 연결 실패: {e} → Mock 모드")
            sensor = MockGripSensor()
    else:
        try:
            sensor = ArduinoGripSensor()
        except Exception as e:
            print(f"[센서] Arduino 감지 실패: {e} → Mock 모드")
            sensor = MockGripSensor()

    sensor.start()

    while True:
        launcher = Launcher(screen, sensor)
        choice   = launcher.run()

        if choice is None or GAMES[choice]["path"] is None:
            break

        game_path = os.path.join(os.path.dirname(__file__), GAMES[choice]["path"])
        arg = "--real" if USE_REAL else "--arduino"
        cmd = [sys.executable, game_path, arg]
        sensor.stop()          # 포트 해제
        subprocess.run(cmd)
        sensor.start()         # 포트 재점유

    sensor.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
