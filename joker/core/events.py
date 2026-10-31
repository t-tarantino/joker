"""Primitives, queued tasks and events (core-contracts.md §3.7, §5)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class Move:
    """M1: a card moved. Positions are None for unordered zones."""

    card: int
    src: str
    dst: str
    src_pos: int | None
    dst_pos: int | None


@dataclass(frozen=True)
class SetVar:
    """M2: a variable changed."""

    name: str
    value: Any


Primitive = Move | SetVar


@dataclass(frozen=True)
class DrawTask:
    """A queued Nature step: draw a uniformly random card of `src` into `dst` (DR-2)."""

    src: str
    dst: str


class StepKind(Enum):
    AUTO = "auto"        # an AutoPhase runs, no decision
    NATURE = "nature"    # a chance event (queued draw or NaturePhase)
    CHOICE = "choice"    # one or more players choose
    END = "end"          # the hand is over


@dataclass(frozen=True)
class Step:
    """What happens next in a state. Control flow is public (S5.5)."""

    kind: StepKind
    actors: tuple
    options: dict | None = None      # CHOICE: player -> physically possible options
    outcomes: tuple | None = None    # NATURE: ((outcome, probability), ...)


@dataclass(frozen=True)
class Event:
    """One step of the history, as the referee saw it."""

    step: int
    kind: StepKind
    actors: tuple
    outcome: Any                     # None (AUTO), a Nature outcome, or {player: Option}
    primitives: tuple
