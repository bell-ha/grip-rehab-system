"""
game_logic.py — 두더지 잡기 게임 로직 (상태 머신)

구멍 3개:  0=왼쪽  1=가운데(양손)  2=오른쪽

두더지 상태:
    HIDDEN  → RISING → UP → (HIT | MISSED)

타입:
    'left'  : 왼손 단독
    'right' : 오른손 단독
    'both'  : 양손 동시
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto


THRESHOLD_KG   = 8.0    # 잡기 성공에 필요한 최소 악력
GAME_DURATION  = 60.0   # 초


class MoleStatus(Enum):
    HIDDEN = auto()
    UP     = auto()
    HIT    = auto()
    MISSED = auto()


@dataclass
class Mole:
    hole: int               # 0, 1, 2
    kind: str               # 'left' | 'right' | 'both'
    status: MoleStatus = MoleStatus.HIDDEN
    appear_at: float = 0.0  # time.monotonic()
    duration: float = 2.0   # 화면에 머무는 시간 (초)

    @property
    def time_ratio(self) -> float:
        """남은 시간 비율 1.0 → 0.0 (타이머 바용)"""
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
    """
    매 프레임 update(dt, left_kg, right_kg) 호출.
    이벤트 리스트를 반환 → renderer가 소비.
    """

    # 구멍별 허용 두더지 종류
    _HOLE_KINDS = {
        0: ['left'],
        1: ['both'],
        2: ['right'],
    }

    def __init__(self):
        self.state = GameState()
        self._spawn_cooldown = 0.0   # 다음 스폰까지 대기 시간
        self._spawn_timer    = 0.0

    # ── 공개 API ──────────────────────────────

    def start(self):
        self.state = GameState(running=True, time_left=GAME_DURATION)
        self._spawn_timer    = 0.0
        self._spawn_cooldown = 0.8   # 첫 등장까지 여유

    def update(self, dt: float, left_kg: float, right_kg: float) -> list[str]:
        """
        dt       : 프레임 델타 (초)
        left_kg  : 왼손 악력
        right_kg : 오른손 악력
        반환 : 이벤트 문자열 리스트 ['hit:0', 'missed:2', 'combo:5', ...]
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
            # 게임 진행할수록 빠르게
            progress = 1.0 - s.time_left / GAME_DURATION
            self._spawn_cooldown = max(0.6, 1.8 - progress * 1.0)

        # 두더지 상태 처리
        for i, mole in enumerate(s.moles):
            if mole is None or mole.status != MoleStatus.UP:
                continue

            # 잡기 판정
            triggered = False
            if mole.kind == 'left'  and left_kg  >= THRESHOLD_KG:
                triggered = True
            if mole.kind == 'right' and right_kg >= THRESHOLD_KG:
                triggered = True
            if mole.kind == 'both'  and left_kg  >= THRESHOLD_KG \
                                     and right_kg >= THRESHOLD_KG:
                triggered = True

            if triggered:
                mole.status = MoleStatus.HIT
                s.hits  += 1
                s.combo += 1
                s.max_combo = max(s.max_combo, s.combo)
                bonus = max(0, s.combo - 3) * 5
                s.score += 10 + bonus
                events.append(f"hit:{i}")
                if s.combo >= 3:
                    events.append(f"combo:{s.combo}")

            elif mole.expired:
                mole.status = MoleStatus.MISSED
                s.misses += 1
                s.combo   = 0
                events.append(f"missed:{i}")

        return events

    def clear_mole(self, hole: int):
        """renderer가 애니메이션 완료 후 호출"""
        self.state.moles[hole] = None

    # ── 내부 ──────────────────────────────────

    def _try_spawn(self):
        s = self.state
        empty = [i for i, m in enumerate(s.moles) if m is None]
        if not empty:
            return
        hole = random.choice(empty)
        kind = random.choice(self._HOLE_KINDS[hole])

        progress  = 1.0 - s.time_left / GAME_DURATION
        duration  = max(1.0, 2.5 - progress * 1.2)
        duration += random.uniform(-0.2, 0.2)

        mole = Mole(
            hole=hole,
            kind=kind,
            status=MoleStatus.UP,
            appear_at=time.monotonic(),
            duration=duration,
        )
        s.moles[hole] = mole
