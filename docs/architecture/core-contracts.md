# JOKER — Core Model & Engine Contracts

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

> **Status:** FIRST DRAFT (2026-10-29) — written for owner review, not approved.
> Everything here is `proposed` unless marked `decided`. Open design decisions are
> collected in §10 ("Decisions for review").
> Assumptions referenced as A*/S* live in [`assumptions.md`](assumptions.md).
> A complete worked example: [`examples/mini-briscola.md`](examples/mini-briscola.md).
> All code below is **pseudo-code** illustrating contracts, not implementation.

---

## 1. Principles carried in (all `decided`)

- **Three layers, never mixed:** physical state (referee's truth) / information
  state (one per observer: raw observation history) / belief (distribution over
  physical worlds). Knowledge is never stored in the physical state.
- **Three primitives** change state: **M1** move card, **M2** set variable,
  **B1** choice point. Game code otherwise only reads state and is deterministic.
- **Observations are derived**, never declared (S5.2).
- **Consistency = replay** (S7.4). Rule-forced constraints are never hand-written.
- **Replaceable choice model** (A1.1) — the Goal 2 hook.

---

## 2. Overview

```
GameDefinition (written by the game author, Python + framework primitives)
   │  cards & facets · deck · zones · variables · phases · rules · derived functions
   ▼
Engine ──────────────► State (physical, omniscient)      ◄── invariants checked
   │  advance / choice_point / apply / replay
   ▼
Event log (one Event per step: actors, outcome, primitives applied)
   │  observe(event, observer)      ← derived, facet-filtered
   ▼
InformationState (per observer: observations only)        ◄── live input also lands here
   │
   ▼
Probability module: belief(info_state, query, trust_policy, choice_model)
   (never sees State — S5.4)
```

---

## 3. Game definition — what the author writes

### 3.1 Cards, facets, deck

```python
Facet = str                         # default facets: "back", "face" (S1.6)

@dataclass(frozen=True)
class CardType:                     # what a card *is* (S1.2): attributes grouped by facet
    attrs: dict[Facet, dict[str, Any]]    # {"back": {"color": "blue"},
                                          #  "face": {"suit": "coins", "rank": 3}}

DeckSpec = dict[CardType, int]      # multiset: type -> number of copies (S1.1)
```

- The engine assigns each physical copy an internal `CardId` (e.g. `7♥#2`). A
  `CardId` is **never observable** (S1.1b).
- The classic library (S1.2a) provides helpers, e.g. `italian_40(back_color=...)`,
  `french_52(jokers=0, back_color=...)`, plus subset filters (32/36-card decks) and
  deck union (two decks with different back colors).

### 3.2 Players and observers

```python
Player   = int                      # 0 .. N-1, N fixed per game (S3.1)
Observer = Player | PUBLIC | OMNISCIENT   # S3.4
Actor    = Player | NATURE                # S3.5
```

### 3.3 Zones

```python
@dataclass(frozen=True)
class Zone:
    name: str
    owner: Player | None = None
    ordered: bool = False           # stack vs set (S1.3)
    facets: dict[Selector, set[Facet]]   # per-observer visible facets (S1.6)
    count_visible: Selector = ALL        # S1.5
    refill_from: str | None = None       # auto-refill (e.g. stock_top), §3.7

Selector = OWNER | OTHERS | ALL | set[Player]   # OTHERS includes PUBLIC
```

- Zones are declared **in advance** (S1.4); helper `per_player(fn)` declares one
  zone per player (`hand0`, `hand1`, ...).
- `OMNISCIENT` always sees every facet.
- **Atomic:** all cards in a zone show the same facets to the same observer.

### 3.4 Variables

```python
@dataclass(frozen=True)
class Var:
    name: str
    initial: Any
    visible: Selector = ALL         # who observes its value (M2)
    per_player: bool = False        # declares name[0..N-1]
```

Match- or hand-level is given by the list a variable is declared in
(`Game.match_vars` carry over between hands, S6.1; `Game.hand_vars` reset).

Scores, dealer, leader, trump suit, roles, flags ("declared busso"), hidden roles
(S3.6) are all variables.

### 3.5 Derived functions

Pure functions of the physical state, usable by rules and by queries. Example:
`partner(s)` in Briscola a chiamata = holder of the called card (S3.6a). They are
evaluated on each candidate world, so queries like P(partner == 3) come for free.

### 3.6 Structure: match → hand → phases (S6.1)

The control flow is an **explicit state machine** whose state lives entirely in the
physical state (current phase + pending tasks). See DR-1 for why.

```python
class AutoPhase:                    # no decision: runs primitives, then moves on
    def run(self, s: View, ctx: Ctx) -> PhaseId | END_HAND: ...

class ChoicePhase:                  # a B1 choice point for players
    def actors(self, s: View) -> list[Player]               # S4.2 (>1 = simultaneous)
    def options(self, s: View, p: Player) -> list[Option]   # PHYSICALLY possible only (S7.3)
    rules: list[Rule]                                       # regulatory rules (A3)
    def apply(self, s: View, joint: dict[Player, Option], ctx: Ctx) -> PhaseId | END_HAND

class NaturePhase:                  # an explicit chance event (S2.4)
    def distribution(self, s: View) -> Distribution         # finite, declared probabilities
    def apply(self, s: View, outcome, ctx: Ctx) -> PhaseId | END_HAND

class Game:
    name: str
    players: int | range
    deck: DeckSpec
    zones: list[Zone]
    match_vars: list[Var]
    hand_vars: list[Var]
    phases: dict[PhaseId, AutoPhase | ChoicePhase | NaturePhase]
    initial_phase: PhaseId
    def end_hand(self, s: View, ctx: Ctx) -> None           # updates match vars
    def match_over(self, s: View) -> bool
```

- A **match** is a loop of hands; the match state (match vars) carries over.
- `[Goal 1]` the engine can start a single hand from a given match state (S6.1).

### 3.7 The mutation context `Ctx` — the only door to M1 / M2 / B1

```python
class Ctx:
    state: View                                      # live view, updated after each primitive
    def move(self, card: CardId | CardRef, to: str, position: int | TOP | BOTTOM = TOP)  # M1
    def set(self, var: str, value) -> None                                              # M2
    def draw_random(self, src: str, dst: str, n: int = 1) -> None   # queues n Nature B1 + M1
```

- `draw_random` is the default **lazy chance** idiom (DR-2): each draw is a Nature
  choice point "which card of `src`", uniform over the cards there, followed by an
  M1. Queued draws are stored in the state (`pending`), so the state stays complete.
- `refill_from` on a zone (e.g. `stock_top`) makes the engine queue a `draw_random`
  automatically whenever that zone becomes empty (S1.6).
- There is no other way to change state. Game code calling `random` or keeping
  external state is a contract violation (S7.2); determinism is tested.

### 3.8 Options and card references

```python
@dataclass(frozen=True)
class Option:                       # one decision of one actor, e.g. PlayCard(ref)
    kind: str
    args: tuple

@dataclass(frozen=True)
class CardRef:                      # a card *as the actor sees it*
    zone: str
    visible_attrs: frozendict       # attributes of the facets the actor sees there
```

- **Canonicalization (S7.8, proposed):** player options are expressed with
  `CardRef`s, so two physical copies the actor cannot tell apart give **one**
  option, not two. When applied, the engine resolves a `CardRef` to the lowest
  matching `CardId` (any fixed rule works, by copy symmetry, S1.1).
- Nature outcomes use concrete `CardId`s (proper probabilities, S1.1).

### 3.9 Regulatory rules and trust policy (A3)

```python
class Rule:
    name: str
    klass: IMMEDIATE | LATER | NEVER          # verifiability class, declared by author
    def allowed(self, s: View, p: Player, opt: Option) -> bool

@dataclass
class TrustPolicy:
    later: bool = True                         # default: trust class (ii)
    never: bool = False                        # default: do not trust class (iii)
    overrides: dict[tuple[Player, str], bool] = {}   # per player/rule (e.g. after a detected violation)
```

- **Live play / input validation:** all rules are checked; an illegal input is
  flagged (class (i) violations are visible by definition).
- **Belief replay:** class (i) rules are ignored (they carry no hidden-card
  information); classes (ii)/(iii) are checked if trusted.
- **Automatic class check (test):** a class (i) rule's verdict must be identical
  on every world consistent with the observation; sampling worlds detects a
  mis-declared class.

---

## 4. Physical state

```python
@dataclass(frozen=True)
class State:
    zones: Mapping[str, tuple[CardId, ...] | frozenset[CardId]]   # ordered / unordered
    vars: Mapping[str, Any]                # match + hand variables
    phase: PhaseId                         # control state
    pending: tuple[Task, ...]              # queued automatic steps (draw_random, refills)
    # derived caches (not part of identity): card -> zone index
```

- Plain data → `clone`, `serialize`, `state_hash` are trivial (needed by future
  solvers too).
- **Invariant:** every `CardId` is in exactly one zone, always (conservation).
- Mutable-with-undo vs immutable states is a performance choice, deferred (DR-7).

---

## 5. Engine API

```python
class Engine:
    def __init__(self, game: Game, n_players: int): ...
    def new_hand(self, match_state: Mapping[str, Any]) -> State
    def advance(self, s: State) -> tuple[State, list[Event]]        # runs AutoPhases until a choice point
    def choice_point(self, s: State) -> ChoicePoint | None          # None = hand over
    def legal_options(self, s, p, trust: TrustPolicy | None = None) -> list[Option]
    def apply(self, s: State, outcome: Outcome) -> tuple[State, Event]
    def sample_nature(self, s: State, rng) -> Outcome               # simulation only
    def observe(self, event: Event, observer: Observer) -> Observation
    def replay(self, match_state, outcomes: list[Outcome]) -> Trace # deterministic
    def info_state(self, trace: Trace, observer: Observer) -> InformationState
    def check_invariants(self, s: State) -> None

@dataclass(frozen=True)
class ChoicePoint:
    actors: tuple[Actor, ...]
    options: Mapping[Actor, tuple[Option, ...]]      # players: physically possible
    distribution: Distribution | None                # Nature only

@dataclass(frozen=True)
class Event:                                         # one step of the history
    step: int
    actors: tuple[Actor, ...]                        # empty for AutoPhase steps
    outcome: Outcome | None
    primitives: tuple[Primitive, ...]                # M1 / M2 applied, in order
```

- The engine is the **referee**: it always holds a complete physical state.
- Randomness exists only in `sample_nature` (simulation); outcomes are logged, so
  `replay` needs no RNG.

---

## 6. Observations and information state

### 6.1 Observation of one event, for one observer

```python
@dataclass(frozen=True)
class Observation:
    step: int
    actors: tuple[Actor, ...]           # always public (S5.5, proposed)
    own_option: Option | None           # if the observer was an actor (S5.6, proposed)
    perceived: tuple[Perceived, ...]

Perceived = MoveSeen | VarSeen
MoveSeen(src, dst, src_pos, dst_pos, attrs: dict[Facet, dict])   # attrs: facets visible in src ∪ dst
VarSeen(var, value)
```

Derivation rules (S5.2):
- **M1** of card c from `Z1` to `Z2`: if the observer sees the count of `Z1` or
  `Z2`, it perceives the move; it receives the attributes of every facet it can see
  in `Z1` or in `Z2`; positions only for ordered zones. Never the `CardId`.
- **M2** of variable v: perceived (with value) iff the observer is in `v.visible`.
- **Control flow** (phase, actors, pending automatic steps) is public (S5.5).
  This is information too: e.g. in Hearts "the holder of 2♣ leads" — who leads
  reveals who held 2♣, and replay exploits it automatically.

### 6.2 Information state

```python
@dataclass(frozen=True)
class InformationState:
    game: GameRef
    n_players: int
    observer: Observer
    initial_public: Mapping[str, Any]     # public match state at hand start
    observations: tuple[Observation, ...] # S5.1: perfect recall = keep all
```

- **Derived views** (computed on demand, never stored as truth): known cards and
  known locations, per-card "never seen / seen before / visible now", candidate
  sets, rule-forced constraints under a trust policy.
- The "memoryless" toggle (S5.1, deferred) would be a view that keeps only what is
  visible now.

### 6.3 Two ways to build an information state

1. **Simulation mode:** the engine plays a full game (tests, demos, benchmarks)
   and `info_state(trace, observer)` filters the event log.
2. **Live mode (the real Goal 1 use case):** a person playing a real game enters
   what they see ("opponent played 5♥", "I drew 7♣", "opponent drew a card"). These
   entries are Observations; there is **no physical state**. The probability module
   works identically, because it only ever needs the information state. Input
   helpers and validation (at least one consistent world must exist) are designed
   later (DR-8).

---

## 7. Interface to the probability module

```python
def belief(info: InformationState,
           query: Query,
           trust: TrustPolicy = TrustPolicy(),
           choice_model: ChoiceModel = UniformNoInformation(),   # Goal 1 (A1.1)
           method: EXACT | MONTE_CARLO | AUTO = AUTO,
           budget: Budget | None = None) -> BeliefResult
```

Queries are expressed on **attributes and derived functions**, never on `CardId`s.
Details, weighting and methods: [`probability.md`](probability.md).

---

## 8. Invariants and mandatory tests

| Test | What it guarantees |
|---|---|
| Card conservation after every primitive | no duplicated / lost cards |
| Determinism: same outcomes → same state hashes | replay is valid |
| Replay equality: `replay(log)` reproduces the live trace | event log is complete |
| Non-leakage (S5.4): same observation sequence → identical belief | no hidden info used |
| Facet leakage: observations never contain invisible facets or `CardId`s | S1.1b, S1.6 |
| Class (i) rule check: verdict constant across consistent worlds | rule classes declared correctly |
| Omniscient observer → all probabilities 0 or 1 | sanity |
| Normalization: probabilities sum to 1 | sanity |
| Brute-force oracle agreement on tiny games | correctness of every method |
| Detected violation is reported, never a crash | A3 |

---

## 9. What this draft deliberately does not cover

Utilities and scoring beyond `end_hand` bookkeeping (S8), solvers, the analyzer,
GUI, the DSL (S7.5), concrete performance optimizations.

---

## 10. Decisions for review (all `proposed`)

| ID | Decision | Recommendation | Why |
|---|---|---|---|
| **DR-1** | Control flow: explicit state machine vs Python generator scripts | **State machine** | A generator's program counter is hidden state outside `State`: it cannot be cloned, hashed or serialized, which breaks efficient replay/enumeration now and solvers later. Cost: a bit more verbose to author. |
| **DR-2** | Default chance idiom: lazy draws vs explicit shuffle of an ordered stock | **Lazy draws** (`draw_random`) | Same distribution as a uniform shuffle (S2.2), but each chance step has ≤ #cards outcomes instead of 40! permutations — far better for enumeration. Ordered stock + explicit shuffle remains available for non-uniform shuffles. |
| **DR-3** | Framework task queue (`pending`) for automatic steps (queued draws, refills) | **Yes**, stored in `State` | Keeps authoring short while the state stays complete. |
| **DR-4** | Option canonicalization by what the actor can distinguish (S7.8) | **Yes** | Two identical copies are one decision, not two; otherwise hidden-choice weights double-count duplicates. |
| **DR-5** | Control flow and actors always public (S5.5); an actor observes its own option (S5.6) | **Yes** | Matches the table; makes "who leads" information usable. |
| **DR-6** | Weighting of choices (resolves the A1.1 open point) | see [`probability.md`](probability.md) §3 | One formula covering observed, hidden and partially observed choices. |
| **DR-7** | Immutable states vs mutable + undo | **Defer** | Pure performance question; contracts are the same. |
| **DR-8** | Live-mode input format and helpers | **Resolved** (`joker/live.py`): the person picks among the observations still possible; single possibilities are applied automatically | Generic for every game; impossible input cannot be entered; rule breaking can still be recorded (physical frontier). |
