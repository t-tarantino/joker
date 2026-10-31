# JOKER — Implementation Status

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

What exists in code, how to run it, and how it maps to the design docs.
_Last updated: 2026-10-31 — milestone 1 (Goal 1 walking skeleton) + Scopone GUI +
rung 1 (Blackjack)._

## How to run

Python 3.12, **no external dependencies** (standard library only).

```
python -m unittest discover -s tests -t . -v          # ~75 s
$env:JOKER_SLOW = "1"; python -m unittest tests.test_briscola   # + full-hand Briscola test (~7 s)
$env:JOKER_SLOW = "1"; python -m unittest tests.test_blackjack  # + generic solver on a full deck (~17 s)
```

### Blackjack (rung 1)

```
python -m tools.blackjack_report                               # house edges + basic strategy charts (~1 min)
python -m tools.blackjack_report --hands 10000000 --workers 18 # + Monte Carlo check (~45 min on 18 cores)
```

Full report: [`rungs/rung-1-blackjack.md`](rungs/rung-1-blackjack.md).

### Local GUI (play a real hand, record what you see)

```
python -m joker.gui            # opens http://127.0.0.1:8765/ in the browser
python -m joker.gui --port 9000 --no-browser
```

Games: **Scopone scientifico** (4 players, you + partner vs two opponents; exact
combinatorial method), 2-player **Briscola** (exact enumeration) and **Blackjack**
(1 or 6 decks; exact enumeration + the exact blackjack solver for advice). You
are always player 0. Style: "Split Jester". Every number shown is an aggregate
over possible worlds (never one world). After changing Python code, restart the
server; changes to the page (`static/`) only need a browser reload.

Recording a card: pick the suit, then the rank (impossible ones are disabled); if
the card can be played in several ways (different captures), pick which one.
Cards without a suit (Blackjack): rank only. Actions (stand, hit…): buttons, with
the expected value of each move when the game gives advice.

All games use the same generic **circle layout** ([`architecture/gui.md`](architecture/gui.md)
§8): players as avatars around the table, piles in the middle, odds for one
selected player or pile at a time, click a card in the grid to see on every
avatar the chance they hold it.

## Package layout

| Module | Contents | Design reference |
|---|---|---|
| `joker/core/card.py` | `CardType` (facets), `Card` (internal copy id), `build_cards` | S1.1, S1.1b, S1.2, S1.6 |
| `joker/core/spec.py` | observers, selectors, `Zone`, `Var`, `CardRef`, `Option`, `Rule` + classes, `TrustPolicy`, phase base classes, `Game` | core-contracts §3, A3 |
| `joker/core/state.py` | `State` (physical, hashable), `View` (read-only API for game code) | core-contracts §4 |
| `joker/core/events.py` | primitives `Move` (M1), `SetVar` (M2), `DrawTask`, `Step`, `Event` | S7.2 |
| `joker/core/engine.py` | `Engine` (referee: steps, legality, violations, simulation, replay, invariants, `canonical`: merge states that differ only by which copy of a card is where), `Ctx` (the only door to M1/M2/draws) | core-contracts §5, S1.1 |
| `joker/core/observation.py` | derived observations, `InformationState` | S5, core-contracts §6 |
| `joker/probability/belief.py` | exact incremental enumeration with state merging, DR-6 weighting, violation detection | probability.md §2–§3, §6.2, §7 |
| `joker/probability/oracle.py` | brute-force oracle (tests only) | probability.md §6.1 |
| `joker/probability/queries.py` | `P`, `Distribution`, `Marginals`, `NextDraw` | probability.md §4 |
| `joker/cards/classic.py` | Italian 40, French 52 (+ jokers), `subset`, `union` | S1.2a |
| `joker/games/briscola.py` | 2-player Briscola | examples/mini-briscola.md |
| `joker/games/tiny.py` | tiny test games (TinyTricks, TinyDiscard, TinyDupDiscard, TinyFollow) | — |
| `joker/live.py` | `LiveSession` (explicit worlds) and `ExchangeableSession` (representative world + pinned cards): follow a real hand, undo | DR-8 |
| `joker/probability/exchangeable.py` | exact combinatorial belief for exchangeable games | probability.md §6.5 |
| `joker/probability/views.py` | common belief reading API (`WorldsBelief`) | — |
| `joker/games/scopone.py` | Scopone scientifico (+ smaller variants for tests), hand scoring | — |
| `joker/gui/server.py` | local JSON API + static file server (127.0.0.1 only); every call carries the selected view | gui.md §4 |
| `joker/gui/profiles.py` | `CircleProfile`: generic presentation for every game (seats, piles, prompts, labels, card grid, focus, advice); `ScoponeProfile`, `BriscolaProfile`, `BlackjackProfile`: hints + hooks only | gui.md §8 |
| `joker/gui/static/` | the page: `index.html`, `style.css` (Split Jester, softened palette), `app.js` (one renderer for every game; suit → rank card picker; move buttons with values), `logo.png` (header logo) | gui.md |
| `tools/make_gui_logo.py` | rebuilds `logo.png` from the final logo (dev-only, needs Pillow) | — |
| `joker/games/blackjack.py` | Blackjack vs the dealer: `BlackjackRules` (decks, S17/H17, doubling, DAS, splits, payout), hidden hole card + peek, money in variable `net` | rung 1 |
| `joker/strategy/expectimax.py` | `SoloExpectimax`: generic exact expected value / best option for one-player games, over the player's information states (Fractions); copy-symmetry merging and caching | strategy.md L4/L5 |
| `joker/strategy/blackjack.py` | `BlackjackSolver`: fast exact blackjack values (infinite or finite shoe, optimal or a given policy), Griffin's peek conditioning, splits; basic strategy charts; policies for the engine | rung 1 |
| `joker/strategy/blackjack_reference.py` | published strategies: Nairn 2019 single deck; play-a-chart policy | rung 1 |
| `joker/arena.py` | `play_solo` / `play_solo_parallel`: N hands through the engine, mean ± 95% margin | ROADMAP "before rung 1" |
| `tools/blackjack_report.py` | house edges, charts, Monte Carlo check | rung 1 |
| `Game.utility` (in `core/spec.py`) | what a finished hand is worth to a player (S8); used by solvers and the arena | S8 |

## Implemented with the recommended defaults (pending owner review)

DR-1 explicit state machine · DR-2 lazy draws · DR-3 task queue in `State` ·
DR-4 option canonicalization (S7.8) · DR-5 public control flow + own option
(S5.5, S5.6) · DR-6 weighting `w = 1/|C|`. Probabilities are exact `Fraction`s.

## What the tests verify

| Test | Result |
|---|---|
| Card conservation, hands end, replay determinism (TinyTricks, Briscola) | pass |
| Opponent draws show only the back; unordered zones never reveal positions; only the actor sees its own option | pass |
| Identical copies give one option (S7.8) | pass |
| **Exact method = brute-force oracle**, every prefix of several hands, both observers (TinyTricks, TinyDiscard, TinyDupDiscard) | pass |
| **A1.1 example (7♠): P = 1/2** | pass |
| **S7.8: P(discard is a 1) = 5/12** | pass |
| Partial observation: discarded back color always respected (S1.6) | pass |
| Violations: reported only when a player really reneged, as `ViolationDetected(1, "follow_suit")` | pass |
| **Briscola after the deal: P(opponent holds trump A) = 1/12 exactly, over 7140 = C(36,3) worlds, ~1.8 s** | pass |
| Briscola marginals after a trick: sum to 3, zero on seen cards | pass |
| Briscola full hand: loser taking the face-up trump card is known with P = 1 (slow) | pass |
| Live mode: driven by a simulated hand, always offers the real observation and ends in exactly the exact method's worlds (TinyTricks full hands both observers, Briscola first trick) | pass |
| Live mode: undo returns to before the last choice; a renege can be recorded and is reported | pass |
| Scopone rules: same-rank priority, sum captures, last card never a scopa, conservation | pass |
| **Exchangeable method = full enumeration** on a mini Scopone (8 cards), every step, all 4 observers (expected counts, certain counts, P(≥k), number of worlds) | pass |
| Scopone after the deal: P(partner holds settebello) = 1/3 over 5 550 996 791 340 worlds | pass |
| GUI page test (manual script, drives `app.js` clicks against the server): full hands of Scopone, Briscola and 24 Blackjack hands (1 and 6 decks), focus / card / lens switching; advice present at all 363 decisions of 300 random Blackjack hands; slowest Blackjack step ~0.8 s (6 decks, first solver call), Scopone ~0.02 s | pass |
| Live mode on Blackjack, 6 decks, with copy merging: < 0.1 s per step (without merging: never finished) | pass |
| **Blackjack rules** through the engine: conservation, dealer blackjack ends the hand, 3:2 and push, hidden hole card, split + double, split aces, 21 after split | pass |
| **Blackjack infinite deck = Wizard of Odds table**, 260 values to 6 decimals; house edge −0.511734%; basic strategy chart | pass |
| **Blackjack single deck = Wizard of Odds composition table** (90 values) and **Nairn 2019 split values** | pass |
| **Generic expectimax = fast solver** to 1e-12: decisions in a small shoe, the whole game in a small shoe, (slow) decisions with a full deck | pass |
| **Arena = exact value** within the margin of error (20 000 hands; 10 million in the report tool) | pass |

## Not implemented yet

- Monte Carlo (sequential importance sampling) and the AUTO method selector.
- GUI: Briscola takes ~1–2 s per click early in a hand (pure-Python enumeration
  over up to ~10 000 worlds). Seats are still declared per game, not derived from
  the zones. Blackjack in the GUI: split once only.
- The "memoryless" observer toggle (S5.1), NEVER-class rules in a real game,
  `NaturePhase` used by a real game (only queued draws are exercised).
- Performance work: Python-level enumeration, a few seconds per Briscola belief.
- Blackjack: finite-deck resplitting, surrender, no-hole-card rule, card counting.
- `SoloExpectimax` only handles one deciding player; ~4 s per blackjack decision
  on a full deck.
