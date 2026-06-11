"""
game_logic.py — 우주 조종 게임 로직

왼손 악력 → 왼쪽 이동
오른손 악력 → 오른쪽 이동
두 손의 힘 차이로 우주선을 조종해 터널을 통과한다.

60초 생존, 목숨 3개 (벽 충돌 시 -1)
터널은 시간이 지날수록 좁아진다.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional

SCREEN_W = 800
SCREEN_H = 600

TUNNEL_SPEED  = 200.0   # px/s 터널 스크롤 속도
PLAYER_SPEED  = 40.0   # px/s per kg 차이 (낮을수록 둔감)
CENTER_SPEED  = 160.0   # px/s — 입력 없을 때 중앙 복귀 속도
GAME_DURATION = 60.0    # 초
SEGMENT_H     = 25      # 터널 체크포인트 간격 (px)

INIT_HALF_W = 175       # 초기 터널 반폭 (전체 폭 350px)
MIN_HALF_W  = 65        # 최소 터널 반폭 (전체 폭 130px)

PLAYER_W = 36
PLAYER_H = 48
PLAYER_Y = int(SCREEN_H * 0.72)    # 플레이어 고정 y 위치

THRESHOLD_KG = 8.0      # 더블 펌프 종료 감지 임계값


@dataclass
class TunnelPoint:
    y:      float
    cx:     float   # 터널 중심 x
    half_w: float   # 터널 반폭


@dataclass
class GameState:
    player_x:  float = SCREEN_W / 2.0
    score:     float = 0.0
    time_left: float = GAME_DURATION
    lives:     int   = 3
    running:   bool  = False
    finished:  bool  = False
    grace_t:   float = 0.0  # 충돌 후 무적 시간
    tunnel:    list  = field(default_factory=list)  # TunnelPoint 리스트, y 오름차순


class SteeringGame:
    def __init__(self):
        self._gen_cx     = SCREEN_W / 2.0
        self._gen_vel    = 0.0
        self._cur_half_w = INIT_HALF_W
        self.state       = GameState()
        self._fill_tunnel()

    def start(self):
        self._gen_cx     = SCREEN_W / 2.0
        self._gen_vel    = 0.0
        self._cur_half_w = INIT_HALF_W
        self.state       = GameState(running=True, grace_t=2.0)
        self._fill_tunnel()

    # ── 공개 API ────────────────────────────────────────────────────────────

    def update(self, dt: float, left_kg: float, right_kg: float) -> list:
        """매 프레임 호출. 이벤트 문자열 리스트 반환."""
        s = self.state
        events = []
        if not s.running or s.finished:
            return events

        # 타이머
        s.time_left = max(0.0, s.time_left - dt)
        if s.time_left == 0.0:
            s.running = False
            s.finished = True
            events.append("game_over")
            return events

        # 터널 폭 업데이트 (새 포인트 생성 전에 먼저)
        progress = 1.0 - s.time_left / GAME_DURATION
        self._cur_half_w = INIT_HALF_W - (INIT_HALF_W - MIN_HALF_W) * min(progress * 1.2, 1.0)

        # 플레이어 이동: net force = 오른손 - 왼손
        net = right_kg - left_kg
        if abs(net) > 0.5:
            s.player_x += net * PLAYER_SPEED * dt
        else:
            # 거의 같은 힘 → 중앙 복귀
            diff = SCREEN_W / 2.0 - s.player_x
            move = min(abs(diff), CENTER_SPEED * dt)
            s.player_x += math.copysign(move, diff) if diff != 0 else 0
        s.player_x = max(PLAYER_W / 2, min(SCREEN_W - PLAYER_W / 2, s.player_x))

        # 터널 스크롤
        for pt in s.tunnel:
            pt.y += TUNNEL_SPEED * dt
        s.tunnel = [pt for pt in s.tunnel if pt.y <= SCREEN_H + SEGMENT_H * 2]
        self._ensure_top()

        # 점수
        s.score += dt * 10.0

        # 충돌 판정
        if s.grace_t > 0:
            s.grace_t = max(0.0, s.grace_t - dt)
        else:
            pt = self._at(PLAYER_Y)
            if pt is not None:
                lw = pt.cx - pt.half_w
                rw = pt.cx + pt.half_w
                if s.player_x - PLAYER_W / 2 < lw or s.player_x + PLAYER_W / 2 > rw:
                    s.lives -= 1
                    s.grace_t = 1.2
                    events.append(f"hit:{s.lives}")
                    if s.lives <= 0:
                        s.running  = False
                        s.finished = True
                        events.append("game_over")

        return events

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _gen_one(self, y: float) -> TunnelPoint:
        """다음 터널 포인트 생성 (생성기 상태 갱신)."""
        self._gen_vel += random.uniform(-7.0, 7.0)
        self._gen_vel *= 0.80
        margin = self._cur_half_w + 55
        self._gen_cx = max(margin, min(SCREEN_W - margin, self._gen_cx + self._gen_vel))
        return TunnelPoint(y=y, cx=self._gen_cx, half_w=self._cur_half_w)

    def _fill_tunnel(self):
        """초기 터널 생성: 화면 위에서 아래까지 채움."""
        s = self.state
        s.tunnel = []
        ys = list(range(-SEGMENT_H * 5, int(SCREEN_H) + SEGMENT_H * 3, SEGMENT_H))
        # 아래→위 순서로 생성해야 생성기 상태가 최상단 포인트에 맞음
        pts = [self._gen_one(float(y)) for y in reversed(ys)]
        s.tunnel = list(reversed(pts))  # y 오름차순 (위→아래)

    def _ensure_top(self):
        """터널 최상단이 부족하면 위쪽으로 포인트 추가."""
        s = self.state
        while not s.tunnel or s.tunnel[0].y > SEGMENT_H:
            new_y = (s.tunnel[0].y - SEGMENT_H) if s.tunnel else float(-SEGMENT_H)
            s.tunnel.insert(0, self._gen_one(new_y))

    def _at(self, y: float) -> Optional[TunnelPoint]:
        """주어진 y에서 터널 상태를 보간하여 반환."""
        pts = self.state.tunnel
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if a.y <= y <= b.y:
                t = (y - a.y) / max(b.y - a.y, 0.001)
                return TunnelPoint(
                    y=y,
                    cx=a.cx + (b.cx - a.cx) * t,
                    half_w=a.half_w + (b.half_w - a.half_w) * t,
                )
        return None
