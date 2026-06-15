"""
main.py — 악력 신디사이저

왼손 악력  → 볼륨   (0~30 kg)
오른손 악력 → 음 높이 (도레미파솔라시도)

실행:
    python3 main.py            # Mock 모드 (키보드)
    python3 main.py --arduino  # Arduino USB 시리얼

Mock 조작:
    A / S  : 왼손 악력 증가 / 감소  → 볼륨 조절
    K / L  : 오른손 악력 증가 / 감소 → 음 높이 조절
    ESC    : 종료

pip 의존성:
    pip install sounddevice numpy pygame pyserial
"""

import sys
import os
import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from common.sensor import MockGripSensor, ArduinoGripSensor

from audio_engine import AudioEngine, kg_to_freq, kg_to_volume
from renderer import SynthRenderer

SCREEN_W, SCREEN_H = 800, 600
FPS = 60

EXIT_THRESHOLD_KG = 6.0   # 양손이 이 값 이상이면 "쥔" 것으로 판정
EXIT_WINDOW_SEC   = 2.0   # 더블 펌프 인정 시간 창


def main():
    import time
    pygame.init()
    pygame.mixer.quit()   # aplay와 ALSA 디바이스 충돌 방지
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption("악력 신디사이저")
    clock = pygame.time.Clock()

    # 센서 — Arduino 자동 감지, 실패 시 Mock
    try:
        sensor = ArduinoGripSensor()
        print("[센서] Arduino 연결됨")
    except Exception as e:
        print(f"[센서] Arduino 감지 실패: {e} → Mock 모드  |  A/S = 왼손(볼륨)   K/L = 오른손(음정)")
        sensor = MockGripSensor()

    sensor.start()

    audio    = AudioEngine()
    renderer = SynthRenderer(screen)
    audio.start()

    # 종료 제스처: 양손 동시 2초 내 2번 더블 펌프
    exit_pulse_times: list = []
    prev_both_high = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif isinstance(sensor, MockGripSensor):
                    sensor.handle_keydown(event.key)
            elif event.type == pygame.KEYUP:
                if isinstance(sensor, MockGripSensor):
                    sensor.handle_keyup(event.key)

        reading = sensor.get()
        freq   = kg_to_freq(reading.right_kg)
        volume = kg_to_volume(reading.left_kg)
        audio.set(freq, volume)

        # ── 더블 펌프 종료 감지 ──────────────────────────────────────────
        both_high = (reading.left_kg >= EXIT_THRESHOLD_KG and
                     reading.right_kg >= EXIT_THRESHOLD_KG)
        if both_high and not prev_both_high:   # 상승 엣지
            now = time.time()
            exit_pulse_times = [t for t in exit_pulse_times if now - t <= EXIT_WINDOW_SEC]
            exit_pulse_times.append(now)
            if len(exit_pulse_times) >= 2:
                running = False
        prev_both_high = both_high

        renderer.draw(reading.left_kg, reading.right_kg, freq, volume, dt)
        pygame.display.flip()

    audio.stop()
    sensor.stop()
    pygame.quit()


if __name__ == '__main__':
    main()
