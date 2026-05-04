"""
main.py — 두더지 잡기 메인 루프

사용법:
    python3 main.py                          # 키보드 Mock 모드
    python3 main.py --arduino                # Arduino USB 자동 감지
    python3 main.py --real                   # Arduino (L:x.xx,R:x.xx 포맷)
    python3 main.py --real --port COM3       # 포트 직접 지정 (Windows)
    python3 main.py --real --port /dev/cu.usbmodem141011  # macOS
"""

import sys
import time
import threading
import argparse
import pygame

from sensor     import MockGripSensor, RealGripSensor, ArduinoGripSensor
from game_logic import WhackAMoleLogic
from renderer   import Renderer, W, H

FPS = 60


def main():
    parser = argparse.ArgumentParser(description="두더지 잡기 악력 재활 게임")
    parser.add_argument("--arduino", action="store_true", help="Arduino USB 자동 감지 (raw ADC 포맷)")
    parser.add_argument("--real",    action="store_true", help="Arduino (L:x,R:x kg 포맷)")
    parser.add_argument("--port",    default="/dev/ttyUSB0", help="시리얼 포트")
    parser.add_argument("--baud",    type=int, default=115200, help="보드레이트")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("두더지 잡기 — 악력 재활 게임")
    clock  = pygame.time.Clock()

    # ── 센서 선택 ──────────────────────────────────────────────────────────
    if args.arduino:
        print("[센서] Arduino 자동 감지 모드 (raw ADC + 자동 캘리브레이션)")
        try:
            sensor = ArduinoGripSensor()
            sensor.start()          # 별도 스레드에서 tare + 스케일 측정
        except Exception as e:
            print(f"[센서] Arduino 연결 실패: {e}")
            print("[센서] Mock 모드로 전환합니다.")
            sensor = MockGripSensor()

    elif args.real:
        print(f"[센서] 실제 센서 연결 중 ({args.port}, {args.baud}bps)...")
        try:
            sensor = RealGripSensor(args.port, args.baud)
            print("[센서] 연결 성공!")
        except Exception as e:
            print(f"[센서] 연결 실패: {e}")
            print("[센서] Mock 모드로 전환합니다.")
            sensor = MockGripSensor()

    else:
        print("[센서] Mock 모드  |  A/S = 왼손   K/L = 오른손")
        sensor = MockGripSensor()

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

        # ── 센서 읽기 ────────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        if isinstance(sensor, MockGripSensor):
            sensor.update(keys)
        left_kg, right_kg = sensor.get_grip()

        # ── 게임 로직 ────────────────────────────────────────────────────
        events = logic.update(dt, left_kg, right_kg)

        # 두더지 정리 (딜레이 후 슬롯 비우기)
        for ev in events:
            if ev.startswith("hit:"):
                i = int(ev.split(":")[1])
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

    sensor.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
