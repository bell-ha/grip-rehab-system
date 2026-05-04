"""
main.py
풍선 키우기 — 메인 게임 루프

실행:
    python main.py             # Mock 모드 (PC 개발용)
    python main.py --arduino   # Arduino USB 시리얼 센서 사용
    python main.py --real      # Raspberry Pi HX711 센서 사용

Mock 조작:
    A / S  : 왼손 악력 증가 / 감소
    K / L  : 오른손 악력 증가 / 감소
    R      : 게임 리셋
    ESC    : 종료
"""

import sys
import time
import pygame

from sensor     import MockGripSensor, RealGripSensor, ArduinoGripSensor
from game_logic import BalloonGame, GameConfig, HandState
from renderer   import GameRenderer


# ── 설정 ──────────────────────────────────────────────────────────────────────

USE_REAL_SENSOR = "--real"    in sys.argv
USE_ARDUINO     = "--arduino" in sys.argv

FPS = 60

CONFIG = GameConfig(
    target_kg    = 15.0,
    pop_kg       = 22.0,
    tolerance_kg = 5.0,
    success_sec  = 3.0,
    pop_reset_sec= 1.5,
)


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    pygame.display.set_caption("풍선 키우기 — 악력 재활 게임")

    screen = pygame.display.set_mode(
        (GameRenderer.SCREEN_W, GameRenderer.SCREEN_H),
        pygame.NOFRAME if USE_REAL_SENSOR else 0,   # Pi에선 전체화면 테두리 없이
    )

    clock    = pygame.time.Clock()
    if USE_ARDUINO:
        sensor = ArduinoGripSensor()
    elif USE_REAL_SENSOR:
        sensor = RealGripSensor()
    else:
        sensor = MockGripSensor()
    game     = BalloonGame(CONFIG)
    renderer = GameRenderer(CONFIG)

    sensor.start()

    # 펑 이벤트 → 파티클 스폰 추적용
    prev_l_popped = False
    prev_r_popped = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0   # 초 단위

        # ── 이벤트 처리 ───────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game = BalloonGame(CONFIG)
                elif not USE_REAL_SENSOR and not USE_ARDUINO:
                    sensor.handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                if not USE_REAL_SENSOR and not USE_ARDUINO:
                    sensor.handle_keyup(event.key)

        # ── 센서 읽기 + 게임 업데이트 ────────────────────────────────────
        reading = sensor.get()
        game.update(reading.left_kg, reading.right_kg)

        # 펑 발생 감지 → 파티클 스폰
        if game.left.state == HandState.POPPED and not prev_l_popped:
            lx = renderer.L_PANEL_X + GameRenderer.BALLOON_CX
            ly = renderer.PANEL_Y   + GameRenderer.BALLOON_CY
            renderer.spawn_pop(lx, ly, is_left=True)

        if game.right.state == HandState.POPPED and not prev_r_popped:
            rx = renderer.R_PANEL_X + GameRenderer.BALLOON_CX
            ry = renderer.PANEL_Y   + GameRenderer.BALLOON_CY
            renderer.spawn_pop(rx, ry, is_left=False)

        prev_l_popped = (game.left.state  == HandState.POPPED)
        prev_r_popped = (game.right.state == HandState.POPPED)

        # ── 렌더링 ────────────────────────────────────────────────────────
        renderer.draw(screen, game, dt)
        pygame.display.flip()

    sensor.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
