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
import os
import time
import pygame

# 공통 센서 모듈 import (프로젝트 루트 추가)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.sensor import MockGripSensor, RealGripSensor, ArduinoGripSensor

from game_logic import BalloonGame, GameConfig, HandState
from renderer   import GameRenderer


# ── 설정 ──────────────────────────────────────────────────────────────────────

USE_REAL_SENSOR = "--real"    in sys.argv
USE_ARDUINO     = "--arduino" in sys.argv

FPS = 60

CONFIG = GameConfig(
    target_kg    = 10.0,
    pop_kg       = 15.0,
    tolerance_kg = 3.0,
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

    clock = pygame.time.Clock()
    if USE_REAL_SENSOR:
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
    game     = BalloonGame(CONFIG)
    renderer = GameRenderer(CONFIG)

    sensor.start()

    # ── 카운트다운 ────────────────────────────────────────────────────────
    font_cd   = renderer.font_large
    font_go   = renderer.font_title
    countdown = [("3", (80, 80, 80)), ("2", (80, 80, 80)), ("1", (80, 80, 80)), ("시작!", (34, 139, 34))]
    for text, color in countdown:
        start = time.time()
        while time.time() - start < 0.8:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sensor.stop(); pygame.quit(); sys.exit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    sensor.stop(); pygame.quit(); sys.exit(0)
            renderer.draw(screen, game, 0)
            overlay = pygame.Surface((GameRenderer.SCREEN_W, GameRenderer.SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            screen.blit(overlay, (0, 0))
            f = font_go if text == "시작!" else font_cd
            txt = f.render(text, True, color)
            screen.blit(txt, (GameRenderer.SCREEN_W // 2 - txt.get_width() // 2,
                               GameRenderer.SCREEN_H // 2 - txt.get_height() // 2))
            pygame.display.flip()
            clock.tick(FPS)

    # 종료 제스처: 양손 동시 목표 구간 2회 더블 펌프 (2초 내)
    EXIT_THRESHOLD  = CONFIG.target_kg - CONFIG.tolerance_kg
    EXIT_WINDOW_SEC = 2.0
    exit_pulse_times: list[float] = []
    prev_both_high  = False

    # 상태 전환 추적용
    prev_l_popped    = False
    prev_r_popped    = False
    prev_l_on_target = False
    prev_r_on_target = False
    prev_l_success   = 0
    prev_r_success   = 0

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
                elif isinstance(sensor, MockGripSensor):
                    sensor.handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                if isinstance(sensor, MockGripSensor):
                    sensor.handle_keyup(event.key)

        # ── 센서 읽기 + 게임 업데이트 ────────────────────────────────────
        reading = sensor.get()
        game.update(reading.left_kg, reading.right_kg, dt)

        if game.is_over:
            running = False

        # ── 종료 제스처: 양손 더블 펌프 ──────────────────────────────────
        both_high = (reading.left_kg  >= EXIT_THRESHOLD and
                     reading.right_kg >= EXIT_THRESHOLD)
        if both_high and not prev_both_high:          # 상승 엣지
            now = time.time()
            exit_pulse_times = [t for t in exit_pulse_times
                                 if now - t <= EXIT_WINDOW_SEC]
            exit_pulse_times.append(now)
            if len(exit_pulse_times) >= 2:
                running = False
        prev_both_high = both_high

        # 상태 전환 감지
        l_popped    = game.left.state  == HandState.POPPED
        r_popped    = game.right.state == HandState.POPPED
        l_on_target = game.left.state  == HandState.ON_TARGET
        r_on_target = game.right.state == HandState.ON_TARGET

        # 펑 발생 → 파티클 스폰 + 진동
        if l_popped and not prev_l_popped:
            lx = renderer.L_PANEL_X + GameRenderer.BALLOON_CX
            ly = renderer.PANEL_Y   + GameRenderer.BALLOON_CY
            renderer.spawn_pop(lx, ly, is_left=True)
            sensor.vibrate_pulse(left=True, right=False, duration=0.4)

        if r_popped and not prev_r_popped:
            rx = renderer.R_PANEL_X + GameRenderer.BALLOON_CX
            ry = renderer.PANEL_Y   + GameRenderer.BALLOON_CY
            renderer.spawn_pop(rx, ry, is_left=False)
            sensor.vibrate_pulse(left=False, right=True, duration=0.4)

        # 목표 압력 진입 → 짧은 진동 (잘 쥐고 있다는 피드백)
        if l_on_target and not prev_l_on_target:
            sensor.vibrate_pulse(left=True, right=False, duration=0.15)
        if r_on_target and not prev_r_on_target:
            sensor.vibrate_pulse(left=False, right=True, duration=0.15)

        # 유지 성공 → 양손 진동 (성취감 피드백)
        if game.left.success_count  > prev_l_success:
            sensor.vibrate_pulse(left=True, right=False, duration=0.6)
        if game.right.success_count > prev_r_success:
            sensor.vibrate_pulse(left=False, right=True, duration=0.6)

        prev_l_popped    = l_popped
        prev_r_popped    = r_popped
        prev_l_on_target = l_on_target
        prev_r_on_target = r_on_target
        prev_l_success   = game.left.success_count
        prev_r_success   = game.right.success_count

        # ── 렌더링 ────────────────────────────────────────────────────────
        renderer.draw(screen, game, dt)
        pygame.display.flip()

    sensor.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
