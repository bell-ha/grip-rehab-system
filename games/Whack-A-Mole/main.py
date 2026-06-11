"""
main.py — 두더지 잡기 메인 루프

사용법:
    python3 main.py                          # 키보드 Mock 모드
    python3 main.py --arduino                # Arduino USB 자동 감지
    python3 main.py --real                   # Raspberry Pi HX711 직결
    python3 main.py --arduino --port COM3    # 포트 직접 지정
"""

import sys
import os
import time
import threading
import argparse
import pygame

# 공통 센서 모듈 import (프로젝트 루트 추가)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.sensor import MockGripSensor, RealGripSensor, ArduinoGripSensor

from game_logic import WhackAMoleLogic
from renderer   import Renderer, W, H

FPS = 60


def main():
    parser = argparse.ArgumentParser(description="두더지 잡기 악력 재활 게임")
    parser.add_argument("--arduino", action="store_true", help="Arduino USB (raw ADC 포맷)")
    parser.add_argument("--real",    action="store_true", help="Raspberry Pi HX711 직결")
    parser.add_argument("--port",    default=None, help="시리얼 포트 (Arduino 모드)")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("두더지 잡기 — 악력 재활 게임")
    clock  = pygame.time.Clock()

    # ── 센서 선택 ──────────────────────────────────────────────────────────
    if args.real:
        print("[센서] Raspberry Pi HX711 직결 모드")
        try:
            sensor = RealGripSensor()
        except Exception as e:
            print(f"[센서] 연결 실패: {e} → Mock 모드")
            sensor = MockGripSensor()
    else:
        try:
            sensor = ArduinoGripSensor(port=args.port)
            print("[센서] Arduino 연결됨")
        except Exception as e:
            print(f"[센서] Arduino 감지 실패: {e} → Mock 모드  |  A/S = 왼손   K/L = 오른손")
            sensor = MockGripSensor()

    sensor.start()

    logic    = WhackAMoleLogic()
    renderer = Renderer(screen)
    running  = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── 이벤트 처리 ──────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not logic.state.running:
                        logic.start()
                elif event.key == pygame.K_r:
                    logic.start()
                elif isinstance(sensor, MockGripSensor):
                    sensor.handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                if isinstance(sensor, MockGripSensor):
                    sensor.handle_keyup(event.key)

        # ── 센서 읽기 ────────────────────────────────────────────────────
        reading = sensor.get()
        left_kg, right_kg = reading.left_kg, reading.right_kg

        # ── 게임 로직 ────────────────────────────────────────────────────
        events = logic.update(dt, left_kg, right_kg)

        # 두더지 정리 (딜레이 후 슬롯 비우기) + 진동 피드백
        for ev in events:
            if ev.startswith("hit:"):
                i = int(ev.split(":")[1])
                mole = logic.state.moles[i]
                if mole is not None:
                    sensor.vibrate_pulse(
                        left   = mole.kind in ('left',  'both'),
                        right  = mole.kind in ('right', 'both'),
                        duration = 0.2,
                    )
                threading.Thread(
                    target=lambda idx=i: (time.sleep(0.28), logic.clear_mole(idx)),
                    daemon=True,
                ).start()
            elif ev.startswith("missed:"):
                i = int(ev.split(":")[1])
                threading.Thread(
                    target=lambda idx=i: (time.sleep(0.35), logic.clear_mole(idx)),
                    daemon=True,
                ).start()

        # ── 렌더링 ──────────────────────────────────────────────────────
        for ev in events:
            renderer.handle_event(ev)

        renderer.draw(logic, left_kg, right_kg, dt)
        pygame.display.flip()

    sensor.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
