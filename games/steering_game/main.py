"""
main.py — 우주 조종 게임 메인 루프

실행:
    python3 main.py             # Mock 모드 (PC 개발용)
    python3 main.py --arduino   # Arduino USB 시리얼
    python3 main.py --real      # Raspberry Pi HX711

Mock 조작:
    A / S  : 왼손 악력 증가 / 감소   →  왼쪽 이동
    K / L  : 오른손 악력 증가 / 감소  →  오른쪽 이동
    R      : 재시작
    ESC    : 종료

종료 제스처: 양손 동시로 2초 안에 2번 (더블 펌프)
"""

import sys
import os
import time
import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.sensor import MockGripSensor, RealGripSensor, ArduinoGripSensor

from game_logic import SteeringGame, THRESHOLD_KG, SCREEN_W, SCREEN_H
from renderer   import SteeringRenderer

FPS = 60


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("우주 조종 — 악력 재활 게임")
    clock = pygame.time.Clock()

    # ── 센서 선택 ────────────────────────────────────────────────────────
    if "--real" in sys.argv:
        try:
            sensor = RealGripSensor()
            print("[센서] Raspberry Pi HX711 연결됨")
        except Exception as e:
            print(f"[센서] 연결 실패: {e} → Mock 모드")
            sensor = MockGripSensor()
    else:
        try:
            sensor = ArduinoGripSensor()
            print("[센서] Arduino 연결됨")
        except Exception as e:
            print(f"[센서] Arduino 감지 실패: {e} → Mock 모드  |  A/S = 왼손   K/L = 오른손")
            sensor = MockGripSensor()

    sensor.start()

    game     = SteeringGame()
    renderer = SteeringRenderer(screen)

    # ── 카운트다운 ────────────────────────────────────────────────────────
    countdown = [("3", (80, 80, 80)), ("2", (80, 80, 80)),
                 ("1", (80, 80, 80)), ("시작!", (34, 139, 34))]
    for text, color in countdown:
        t0 = time.time()
        while time.time() - t0 < 0.8:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sensor.stop(); pygame.quit(); sys.exit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    sensor.stop(); pygame.quit(); sys.exit(0)
            renderer.draw(game, 0.0, 0.0, 0.0)
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            screen.blit(ov, (0, 0))
            f   = renderer.font_title if text == "시작!" else renderer.font_large
            txt = f.render(text, True, color)
            screen.blit(txt, (SCREEN_W // 2 - txt.get_width()  // 2,
                               SCREEN_H // 2 - txt.get_height() // 2))
            pygame.display.flip()
            clock.tick(FPS)

    game.start()

    # ── 종료 제스처: 양손 더블 펌프 ──────────────────────────────────────
    EXIT_WINDOW    = 2.0
    exit_times: list = []
    prev_both_high = False

    game_over_at: float = 0.0   # 0 = 아직 게임 오버 아님

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── 이벤트 ───────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_r:
                    game.start()
                    game_over_at = 0.0
                elif isinstance(sensor, MockGripSensor):
                    sensor.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                if isinstance(sensor, MockGripSensor):
                    sensor.handle_keyup(event.key)

        # ── 센서 읽기 ────────────────────────────────────────────────────
        reading  = sensor.get()
        left_kg  = reading.left_kg
        right_kg = reading.right_kg

        # ── 더블 펌프 종료 ────────────────────────────────────────────────
        both_high = left_kg >= THRESHOLD_KG and right_kg >= THRESHOLD_KG
        if both_high and not prev_both_high:
            now = time.time()
            exit_times = [t for t in exit_times if now - t <= EXIT_WINDOW]
            exit_times.append(now)
            if len(exit_times) >= 2:
                running = False
        prev_both_high = both_high

        # ── 게임 로직 ────────────────────────────────────────────────────
        events = game.update(dt, left_kg, right_kg)

        for ev in events:
            if ev.startswith("hit:"):
                sensor.vibrate_pulse(left=True, right=True, duration=0.3)
            elif ev == "game_over":
                game_over_at = time.time()

        # 게임 오버 후 2.5초 표시 후 종료
        if game_over_at > 0 and time.time() - game_over_at > 2.5:
            running = False

        # ── 렌더링 ───────────────────────────────────────────────────────
        renderer.draw(game, left_kg, right_kg, dt)
        pygame.display.flip()

    sensor.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
