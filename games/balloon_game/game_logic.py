"""
game_logic.py
풍선 키우기 게임 로직 — 상태 머신 + 점수 관리
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum, auto


@dataclass
class GameConfig:
    target_kg:     float = 15.0
    pop_kg:        float = 22.0
    tolerance_kg:  float = 5.0
    success_sec:   float = 3.0
    rounds:        int   = 5
    pop_reset_sec: float = 1.5


class HandState(Enum):
    IDLE      = auto()
    FILLING   = auto()
    ON_TARGET = auto()
    OVER      = auto()
    POPPED    = auto()
    RELEASE   = auto()   # 펑 후 손 놓기 대기


@dataclass
class HandData:
    state:            HandState  = HandState.IDLE
    grip_kg:          float      = 0.0
    hold_start:       float|None = None
    hold_sec:         float      = 0.0
    hold_ratio:       float      = 0.0   # 0~1, 렌더러용
    success_count:    int        = 0
    pop_count:        int        = 0
    pop_time:         float|None = None


class BalloonGame:

    def __init__(self, config: GameConfig | None = None):
        self.cfg         = config or GameConfig()
        self.left        = HandData()
        self.right       = HandData()
        self.session_start = time.time()

    def update(self, left_kg: float, right_kg: float):
        now = time.time()
        self._update_hand(self.left,  left_kg,  now)
        self._update_hand(self.right, right_kg, now)

    def _update_hand(self, hand: HandData, kg: float, now: float):
        hand.grip_kg = kg

        # ── 펑 후 대기 ──────────────────────────────────────────
        if hand.state == HandState.POPPED:
            if hand.pop_time and (now - hand.pop_time) >= self.cfg.pop_reset_sec:
                self._reset_hand(hand)
                hand.state = HandState.RELEASE   # 손 놓기 요청
            return

        # ── 펑 후 손 놓기 대기 ───────────────────────────────────
        # 충분히 내려놓기 전까지는 새 사이클 시작 안 함
        if hand.state == HandState.RELEASE:
            if kg <= 1.5:
                hand.state = HandState.IDLE
            return

        # ── 펑 판정 ──────────────────────────────────────────────
        if kg >= self.cfg.pop_kg:
            hand.state      = HandState.POPPED
            hand.pop_count += 1
            hand.pop_time   = now
            hand.hold_start = None
            hand.hold_sec   = 0.0
            hand.hold_ratio = 0.0
            return

        lo = self.cfg.target_kg - self.cfg.tolerance_kg
        hi = self.cfg.target_kg + self.cfg.tolerance_kg

        if kg < 0.5:
            hand.state      = HandState.IDLE
            hand.hold_start = None
            hand.hold_sec   = 0.0
            hand.hold_ratio = 0.0

        elif kg < lo:
            hand.state      = HandState.FILLING
            hand.hold_start = None
            hand.hold_sec   = 0.0
            hand.hold_ratio = 0.0

        elif lo <= kg < hi:
            if hand.state != HandState.ON_TARGET:
                hand.state      = HandState.ON_TARGET
                hand.hold_start = now
                hand.hold_sec   = 0.0
                hand.hold_ratio = 0.0
            else:
                hand.hold_sec   = now - hand.hold_start
                hand.hold_ratio = min(hand.hold_sec / self.cfg.success_sec, 1.0)
                if hand.hold_sec >= self.cfg.success_sec:
                    hand.success_count += 1
                    hand.hold_start     = now
                    hand.hold_sec       = 0.0
                    hand.hold_ratio     = 0.0

        else:   # hi <= kg < pop_kg
            hand.state      = HandState.OVER
            hand.hold_start = None
            hand.hold_sec   = 0.0
            hand.hold_ratio = 0.0

    def _reset_hand(self, hand: HandData):
        hand.grip_kg    = 0.0
        hand.hold_start = None
        hand.hold_sec   = 0.0
        hand.hold_ratio = 0.0
        hand.pop_time   = None

    def balloon_scale(self, kg: float) -> float:
        """kg → 0.0~1.0 (펑 크기 기준 정규화)"""
        return min(max(kg, 0.0), self.cfg.pop_kg) / self.cfg.pop_kg

    @property
    def total_success(self) -> int:
        return self.left.success_count + self.right.success_count

    @property
    def total_pop(self) -> int:
        return self.left.pop_count + self.right.pop_count
