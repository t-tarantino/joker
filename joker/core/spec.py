"""What a game author writes: observers, zones, variables, options, rules,
phases and the Game base class (docs/architecture/core-contracts.md §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .card import BACK, FACE, Facet, FrozenFacets, facet_dict

if TYPE_CHECKING:
    from .engine import Ctx
    from .state import View


# --- observers, actors, selectors (S3.4, S3.5) ------------------------------------

class Special(Enum):
    PUBLIC = "public"            # sees public information only
    OMNISCIENT = "omniscient"    # sees everything (tests only)
    NATURE = "nature"            # the chance actor

    def __repr__(self) -> str:
        return self.value.upper()


PUBLIC = Special.PUBLIC
OMNISCIENT = Special.OMNISCIENT
NATURE = Special.NATURE

Observer = int | Special


class Sel(Enum):
    """Who a visibility declaration applies to."""

    ALL = "all"          # every observer
    OWNER = "owner"      # the owner of the zone / variable
    OTHERS = "others"    # everyone except the owner (includes PUBLIC)


ALL, OWNER, OTHERS = Sel.ALL, Sel.OWNER, Sel.OTHERS

Selector = Sel | frozenset  # a Sel, or an explicit frozenset of players


def _freeze_selector(sel: Any) -> Selector:
    if isinstance(sel, Sel):
        return sel
    return frozenset(sel)


def selector_matches(sel: Selector, observer: Observer, owner: int | None) -> bool:
    if observer is OMNISCIENT:
        return True
    if sel is ALL:
        return True
    if sel is OWNER:
        return owner is not None and observer == owner
    if sel is OTHERS:
        return observer != owner
    return isinstance(observer, int) and observer in sel


END_HAND = "__end_hand__"


# --- zones (S1.3, S1.4, S1.5, S1.6) -------------------------------------------------

@dataclass(frozen=True)
class Zone:
    """A named container. Atomic: all its cards show the same facets to the same observer."""

    name: str
    owner: int | None = None
    ordered: bool = False
    facets: Any = ()                 # {selector: {facet, ...}}; stored frozen
    count_visible: Any = Sel.ALL     # who sees how many cards it holds (S1.5)
    refill_from: str | None = None   # auto-refill from that zone when empty (S1.6)
    match_level: bool = False        # its cards stay from one hand to the next (S6.1)

    def __post_init__(self) -> None:
        if isinstance(self.facets, Mapping):
            frozen = tuple((_freeze_selector(s), frozenset(f)) for s, f in self.facets.items())
            object.__setattr__(self, "facets", frozen)
        object.__setattr__(self, "count_visible", _freeze_selector(self.count_visible))

    def visible_facets(self, observer: Observer, all_facets: frozenset[Facet]) -> frozenset[Facet]:
        if observer is OMNISCIENT:
            return all_facets
        seen: set[Facet] = set()
        for sel, facets in self.facets:
            if selector_matches(sel, observer, self.owner):
                seen |= facets
        return frozenset(seen)

    def count_seen(self, observer: Observer) -> bool:
        return selector_matches(self.count_visible, observer, self.owner)


@dataclass(frozen=True)
class PerPlayer:
    """Declares one item per player; expanded by the engine once N is known."""

    make: Callable[[int], Any]


def per_player(make: Callable[[int], Any]) -> PerPlayer:
    return PerPlayer(make)


# --- variables (M2) ------------------------------------------------------------------

@dataclass(frozen=True)
class Var:
    """Non-card state. Whether it is match- or hand-level depends on the list it is
    declared in (`Game.match_vars` / `Game.hand_vars`). Values must be hashable."""

    name: str
    initial: Any = None
    visible: Any = Sel.ALL
    per_player: bool = False         # declares name[0] .. name[N-1], owned by each player


@dataclass(frozen=True)
class VarInstance:
    name: str
    initial: Any
    visible: Selector
    match_level: bool
    owner: int | None


# --- options and card references (S7.8) ----------------------------------------------

@dataclass(frozen=True)
class CardRef:
    """A card *as an actor sees it*: zone + the attributes of the facets it can see.
    Two copies the actor cannot tell apart give the same CardRef (S7.8)."""

    zone: str
    seen_by: int
    attrs: FrozenFacets

    def facet(self, name: Facet) -> dict[str, Any]:
        return facet_dict(self.attrs, name)

    @property
    def face(self) -> dict[str, Any]:
        return self.facet(FACE)

    @property
    def back(self) -> dict[str, Any]:
        return self.facet(BACK)


@dataclass(frozen=True)
class Option:
    """One decision of one actor. Must be hashable and must not contain CardIds."""

    kind: str
    args: tuple = ()

    @property
    def card(self) -> CardRef:
        """Convenience for the common case Option(kind, (card_ref, ...))."""
        return self.args[0]


def option(kind: str, *args: Any) -> Option:
    return Option(kind, tuple(args))


# --- regulatory rules and trust policy (A3, S7.3) -----------------------------------

class RuleClass(Enum):
    IMMEDIATE = "verifiable immediately"   # (i)
    LATER = "verifiable later"             # (ii)
    NEVER = "never verifiable"             # (iii)


IMMEDIATE, LATER, NEVER = RuleClass.IMMEDIATE, RuleClass.LATER, RuleClass.NEVER


@dataclass(frozen=True)
class Rule:
    """A regulatory rule: can be broken, unlike physical impossibility (S7.3)."""

    name: str
    klass: RuleClass
    allowed: Callable[[View, int, Option], bool]


@dataclass(frozen=True)
class TrustPolicy:
    """Which regulatory rules the belief computation relies on (A3)."""

    later: bool = True                          # class (ii): trusted by default
    never: bool = False                         # class (iii): not trusted by default
    overrides: frozenset = frozenset()          # {(player, rule_name, trusted)}

    def trusts(self, rule: Rule, player: int) -> bool:
        for p, name, value in self.overrides:
            if p == player and name == rule.name:
                return value
        if rule.klass is IMMEDIATE:
            return False                        # carries no hidden-card information
        if rule.klass is LATER:
            return self.later
        return self.never

    def with_override(self, player: int, rule_name: str, trusted: bool) -> TrustPolicy:
        kept = frozenset(o for o in self.overrides if (o[0], o[1]) != (player, rule_name))
        return TrustPolicy(self.later, self.never, kept | {(player, rule_name, trusted)})


# --- phases and the game definition (S4, S6.1, S7.1) ---------------------------------

class AutoPhase:
    """No decision: runs primitives, returns the next phase id (or END_HAND)."""

    def run(self, s: View, ctx: Ctx) -> str:
        raise NotImplementedError


class ChoicePhase:
    """A choice point for players (B1). `options` lists PHYSICALLY possible options
    only; regulatory constraints go in `rules` (S7.3)."""

    rules: tuple[Rule, ...] = ()

    def actors(self, s: View) -> list[int]:
        raise NotImplementedError

    def options(self, s: View, p: int) -> list[Option]:
        raise NotImplementedError

    def apply(self, s: View, joint: dict[int, Option], ctx: Ctx) -> str:
        raise NotImplementedError


class NaturePhase:
    """An explicit chance event with a declared finite distribution (S2.4)."""

    def distribution(self, s: View) -> list[tuple[Any, Any]]:
        """[(outcome, probability), ...]; outcomes hashable, probabilities Fractions."""
        raise NotImplementedError

    def apply(self, s: View, outcome: Any, ctx: Ctx) -> str:
        raise NotImplementedError


class Game:
    """Base class for game definitions. Subclasses set the class attributes."""

    name: str = "game"
    players: int = 2
    deck: tuple = ()                 # DeckSpec
    deck_zone: str = "stock"         # where every card starts
    zones: tuple = ()                # Zone | PerPlayer
    match_vars: tuple = ()           # Var — carried over between hands (S6.1)
    hand_vars: tuple = ()            # Var — reset at every hand
    phases: Mapping[str, Any] = {}   # phase id -> AutoPhase | ChoicePhase | NaturePhase
    initial_phase: str = ""
    # True only if, for every observer, the cards it has not seen are exchangeable:
    # the rules never produce an observable effect that depends on an unseen card
    # except by revealing it, no regulatory rule constrains unseen cards, and every
    # player choice is fully observed. Enables the exact combinatorial method
    # (joker/probability/exchangeable.py); verified by tests against enumeration.
    exchangeable: bool = False

    def end_hand(self, s: View, ctx: Ctx) -> None:
        """Between two hands (Engine.next_hand): update match variables, and move
        cards that must stay out (e.g. table -> a match-level discard) or come
        back (a reshuffle: discard -> deck). Deterministic: no draws."""

    def utility(self, s: View, player: int) -> Any:
        """What `player` gets in a finished hand (S8), used by strategy solvers.
        Games without an objective yet leave it undefined."""
        raise NotImplementedError(f"{self.name} defines no utility")
