"""
game_logic.py — 두더지 잡기 게임 로직

구멍 3개:  0=왼쪽(왼손)  1=가운데(양손)  2=오른쪽(오른손)
두더지 상태: HIDDEN → UP → (HIT | MISSED)
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto


THRESHOLD_KG  = 6.0    # 잡기에 필요한 최소 악력 (낮출수록 쉬움)
GAME_DURATION = 60.0   # 초


class MoleStatus(Enum):
    HIDDEN = auto()
    UP     = auto()
    HIT    = auto()
    MISSED = auto()


@dataclass
class Mole:
    hole:      int
    kind:      str         # 'left' | 'right' | 'both'
    status:    MoleStatus  = MoleStatus.HIDDEN
    appear_at: float       = 0.0
    duration:  float       = 2.0

    @property
    def time_ratio(self) -> float:
        elapsed = time.monotonic() - self.appear_at
        return max(0.0, 1.0 - elapsed / self.duration)

    @property
    def expired(self) -> bool:
        return time.monotonic() - self.appear_at >= self.duration


@dataclass
class GameState:
    score:     int   = 0
    hits:      int   = 0
    misses:    int   = 0
    combo:     int   = 0
    max_combo: int   = 0
    time_left: float = GAME_DURATION
    running:   bool  = False
    finished:  bool  = False
    moles:     list  = field(default_factory=lambda: [None, None, None])


class WhackAMoleLogic:

    _HOLE_KINDS = {
        0: ['left'],
        1: ['both'],
        2: ['right'],
    }

    def __init__(self):
        self.state           = GameState()
        self._spawn_timer    = 0.0
        self._spawn_cooldown = 1.0

    def start(self):
        self.state           = GameState(running=True, time_left=GAME_DURATION)
        self._spawn_timer    = 0.0
        self._spawn_cooldown = 1.0

    def update(self, dt: float, left_kg: float, right_kg: float) -> list[str]:
        """
        반환: ['hit:0:10', 'missed:2', 'combo:5', 'game_over', ...]
        hit 이벤트에 획득 점수 포함
        """
        s = self.state
        events = []

        if not s.running or s.finished:
            return events

        # 타이머
        s.time_left = max(0.0, s.time_left - dt)
        if s.time_left == 0.0:
            s.running  = False
            s.finished = True
            events.append("game_over")
            return events

        # 스폰
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_cooldown:
            self._spawn_timer = 0.0
            self._try_spawn()
            progress = 1.0 - s.time_left / GAME_DURATION
            self._spawn_cooldown = max(0.5, 1.8 - progress * 1.0)

        # 두더지 판정
        for i, mole in enumerate(s.moles):
            if mole is None or mole.status != MoleStatus.UP:
                continue

            hit = False
            if mole.kind == 'left'  and left_kg  >= THRESHOLD_KG:
                hit = True
            if mole.kind == 'right' and right_kg >= THRESHOLD_KG:
                hit = True
            if mole.kind == 'both'  and left_kg  >= THRESHOLD_KG \
                                     and right_kg >= THRESHOLD_KG:
                hit = True

            if hit:
                mole.status  = MoleStatus.HIT
                s.hits      += 1
                s.combo     += 1
                s.max_combo  = max(s.max_combo, s.combo)
                bonus        = max(0, s.combo - 3) * 5
                points       = 10 + bonus
                s.score     += points
                events.append(f"hit:{i}:{points}")
                if s.combo >= 3:
                    events.append(f"combo:{s.combo}")

            elif mole.expired:
                mole.status  = MoleStatus.MISSED
                s.misses    += 1
                s.combo      = 0
                events.append(f"missed:{i}")

        return events

    def clear_mole(self, hole: int):
        self.state.moles[hole] = None

    def _try_spawn(self):
        s     = self.state
        empty = [i for i, m in enumerate(s.moles) if m is None]
        if not empty:
            return
        hole     = random.choice(empty)
        kind     = random.choice(self._HOLE_KINDS[hole])
        progress = 1.0 - s.time_left / GAME_DURATION
        duration = max(0.9, 2.5 - progress * 1.2) + random.uniform(-0.2, 0.2)

        s.moles[hole] = Mole(
            hole=hole, kind=kind,
            status=MoleStatus.UP,
            appear_at=time.monotonic(),
            duration=duration,
        )
