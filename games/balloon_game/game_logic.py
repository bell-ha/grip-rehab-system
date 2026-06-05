"""
game_logic.py
풍선 키우기 게임 로직 — 상태 머신 + 점수 관리
Pygame 렌더링과 완전히 분리되어 있습니다.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum, auto


# ── 게임 설정 ─────────────────────────────────────────────────────────────────

@dataclass
class GameConfig:
    target_kg:    float = 15.0   # 목표 악력
    pop_kg:       float = 22.0   # 펑 임계값
    tolerance_kg: float = 1.5    # 목표 ± 허용 범위
    success_sec:  float = 3.0    # 성공 인정 유지 시간
    rounds:       int   = 5      # 라운드 수
    pop_reset_sec: float = 1.5   # 펑 후 리셋 대기 시간


# ── 핸드 상태 ─────────────────────────────────────────────────────────────────

class HandState(Enum):
    IDLE    = auto()   # 대기
    FILLING = auto()   # 목표 미달 (올라가는 중)
    ON_TARGET = auto() # 목표 범위 유지 중
    OVER    = auto()   # 목표 초과 (위험)
    POPPED  = auto()   # 펑!


@dataclass
class HandData:
    state:      HandState = HandState.IDLE
    grip_kg:    float     = 0.0
    hold_start: float | None = None  # ON_TARGET 진입 시각
    hold_sec:   float     = 0.0      # 현재 유지 시간
    success_count: int    = 0
    pop_count:     int    = 0
    pop_time:      float | None = None  # 펑 발생 시각

    @property
    def hold_ratio(self) -> float:
        """0.0 ~ 1.0, 성공까지 진행률"""
        return min(self.hold_sec / 3.0, 1.0)  # config.success_sec 기준


# ── 게임 상태 ─────────────────────────────────────────────────────────────────

class GameState(Enum):
    TUTORIAL  = auto()   # 풍선 키우기 (지금 구현)
    RESULT    = auto()   # 결과 화면


# ── 메인 게임 로직 ────────────────────────────────────────────────────────────

class BalloonGame:

    def __init__(self, config: GameConfig | None = None):
        self.cfg   = config or GameConfig()
        self.left  = HandData()
        self.right = HandData()
        self.game_state = GameState.TUTORIAL
        self.session_start = time.time()

    # ── 매 프레임 호출 ──────────────────────────────────────────────────────

    def update(self, left_kg: float, right_kg: float):
        now = time.time()
        self._update_hand(self.left,  left_kg,  now)
        self._update_hand(self.right, right_kg, now)

    def _update_hand(self, hand: HandData, kg: float, now: float):
        hand.grip_kg = kg

        # 펑 후 대기
        if hand.state == HandState.POPPED:
            if hand.pop_time and (now - hand.pop_time) >= self.cfg.pop_reset_sec:
                self._reset_hand(hand)
            return

        # 펑 판정
        if kg >= self.cfg.pop_kg:
            hand.state     = HandState.POPPED
            hand.pop_count += 1
            hand.pop_time  = now
            hand.hold_start = None
            hand.hold_sec   = 0.0
            return

        # 목표 범위 판정
        lo = self.cfg.target_kg - self.cfg.tolerance_kg
        hi = self.cfg.pop_kg

        if kg < 0.5:
            hand.state      = HandState.IDLE
            hand.hold_start = None
            hand.hold_sec   = 0.0

        elif kg < lo:
            hand.state      = HandState.FILLING
            hand.hold_start = None
            hand.hold_sec   = 0.0

        elif lo <= kg < hi:
            if hand.state != HandState.ON_TARGET:
                hand.state      = HandState.ON_TARGET
                hand.hold_start = now
                hand.hold_sec   = 0.0
            else:
                hand.hold_sec = now - hand.hold_start
                if hand.hold_sec >= self.cfg.success_sec:
                    hand.success_count += 1
                    hand.hold_start     = now   # 연속 카운트
                    hand.hold_sec       = 0.0

        else:  # hi <= kg < pop_kg  (OVER zone)
            hand.state      = HandState.OVER
            hand.hold_start = None
            hand.hold_sec   = 0.0

    def _reset_hand(self, hand: HandData):
        hand.state      = HandState.IDLE
        hand.grip_kg    = 0.0
        hand.hold_start = None
        hand.hold_sec   = 0.0
        hand.pop_time   = None

    # ── 렌더링용 계산값 ─────────────────────────────────────────────────────

    def balloon_scale(self, kg: float) -> float:
        """kg → 0.0(최소) ~ 1.0(펑 크기) 정규화"""
        return min(max(kg, 0.0), self.cfg.pop_kg) / self.cfg.pop_kg

    @property
    def total_success(self) -> int:
        return self.left.success_count + self.right.success_count

    @property
    def total_pop(self) -> int:
        return self.left.pop_count + self.right.pop_count
