# JOKER — Roadmap: a Ladder of Games

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

Each rung is a **famous game** that forces us to build and verify **one new
piece** of technology. A rung is done only when its verification passes.
Background and vocabulary: [`architecture/strategy.md`](architecture/strategy.md).

_Created 2026-10-31; revised the same day with the owner: ladder stops at
Scopone, Klondike dropped, small pokers replaced by full Texas Hold'em decided
on cards, pot and number of players still in the hand._

Two kinds of result, never to be confused:
- **Solved** — the exact answer, checked against an independent reference.
- **Played well** — no exact answer exists; strength measured in the arena
  (thousands of hands, win rate with its margin of error) and against humans.

---

## Overview

| # | Game | Result | New technology | Main verification |
|---|---|---|---|---|
| 1 | **Blackjack** ✅ | solved | expected value over future draws, opponent with a fixed procedure, caching of identical situations | published basic-strategy tables and house edge |
| 2 | **Texas Hold'em, any number of players, fixed bet sizes** | solved parts + played well | equity against the players still in the hand, pot odds, betting threshold 1/(K+1) — only cards, pot and number of players; then **reading the bets** with a known model | published equity tables; exact decision formulas; calibration of the belief against simulated opponents |
| 3 | **Briscola (2 players)** | played well | arena + reference bots, determinization against an opponent, exact endgame | exact endgames, arena, games with the owner |
| 4 | **Briscola that reads the opponent** | played well | A1.1 removed on a big game against an *unknown* opponent: strategy ↔ belief iteration by levels, toward equilibrium | arena improvement over rung 3; reduced Briscola vs exact equilibrium |
| 5 | **Scopone scientifico** | played well | teams; compiled fast engine checked against the Python oracle | differential testing; arena |

Beyond rung 5: not planned yet (ideas parked in §"Later").

---

## Before rung 1

- Put the project under version control (git). — **not done yet** (awaiting owner).
- Arena skeleton: play N hands, report the result with its margin of error
  (for one-player games: average result per hand). — **done** (`joker/arena.py`).

---

## Rung 1 — Blackjack — **SOLVED (2026-10-31)**

Report, numbers and open points: [`rungs/rung-1-blackjack.md`](rungs/rung-1-blackjack.md).
Done: published values matched to 6 decimals (infinite deck and single deck),
house edge −0.511734% matched, basic strategy charts matched, generic solver =
fast solver, arena = exact values. Still open: finite-deck resplitting; one
published single-deck game total not reproduced (≈0.044% gap, cause unknown).

**Why first:** the dealer follows a fixed procedure (hits below 17), so there is
**no opponent who thinks and no circle**: only cards. Goal 1 alone is *not*
enough: it gives card probabilities *now*, but deciding hit / stand needs the
value of each choice over all future draws (level L4).

**New:**
- **Expected value with my choices and chance** ("expectimax": best over my
  choices, probability-weighted average over the cards).
- **Future-event probabilities** under a fixed procedure (the dealer's final
  total) — the "type (b)" probability deferred in Goal 1.
- **Objective in money** (bets, doubling), not points.
- **Caching:** two situations with the same remaining deck and the same hands are
  the same problem; compute once. First optimization lesson.
- A finite deck without replacement comes for free from our engine, so the
  strategy can depend on the cards already seen (the principle behind card
  counting).
- Monte Carlo simulation of millions of hands vs the exact value: verifies the
  arena itself.

**Verification:** published basic-strategy tables and house edge for a stated
standard rule set (number of decks, dealer on soft 17, doubling, splitting).
Splitting is famously hard to compute exactly: first without splits, then with.

**Done when:** our basic strategy matches the published table and our house edge
matches published values within the stated precision.

## Rung 2 — Texas Hold'em, any number of players, fixed bet sizes

**Why:** after Blackjack the opponents get seats and make choices, but we still
avoid the vicious circle: decisions use **only the cards, the pot and the number
of players still in the hand**, with no inference about who holds what and no
attempt to make others believe anything. No bluffing, by design.

**2a — the card-counting player (owner's formulation; A1.1 on):**
- **Belief:** every player still in the hand holds two cards drawn uniformly from
  the cards we do not see (folded cards stay simply unseen).
- **Equity:** the chance of beating **all** players still in the hand at
  showdown. It drops sharply with their number (a pair of aces wins roughly 85%
  against one random hand, roughly 56% against four).
- **Calling (pot odds):** call when equity > cost to call / (pot + cost to call).
- **Betting needs a minimal assumption** on how others answer, otherwise "should
  I bet?" has no answer. Simplest: *everyone still in calls*. Betting B against
  K callers puts (K+1)·B in the pot, so bet when equity > 1 / (K+1).
- **Fixed bet sizes ("limit")**: with free sizes the "everyone calls" assumption
  degenerates into "always all-in when ahead". Free sizes later, with a sizing
  rule.
- Known weakness, accepted: the uniform belief gets worse as the hand goes on
  and as the number of players grows, because the hands still in after bets are
  not random. Expected leak: calling too often on the last round.

**2b — reading the bets (first removal of A1.1):** same player, but each
possible hand of an opponent is weighted by how likely its observed bets are
under a fixed, known model of play (e.g. "honest player": bets strong hands,
calls medium ones, folds weak ones). This is the **weighted belief machinery**
needed in rung 4, built here where it is fully checkable: in simulation we know
the opponents' true model.

**Verification:**
- Equities match published tables, for every number of opponents.
- Pot-odds and betting decisions match the formulas above exactly.
- **Calibration of the 2b belief:** over many simulated hands against the known
  model, events predicted with probability p happen with frequency ≈ p.
- Arena: 2b beats 2a against honest players; both beat random and simple
  reference bots.

**Done when:** all four checks pass.

## Rung 3 — Briscola (2 players)

**Why:** the first real game with a thinking opponent, too big to solve.

**New:**
- **Arena and reference bots** (random, greedy, rule-based).
- **Determinization against an opponent**, using the Goal 1 belief to sample
  worlds; measure its over-optimism against a bot that sees all cards.
- **Exact endgame:** once the stock is empty, each player knows the other's cards
  by elimination: perfect information, solvable exactly by backward search.

**Verification:** endgame decisions match the exact solver; clear arena wins
over the reference bots; games against the owner.

**Done when:** it beats the rule-based bot clearly (margin of error excluded) and
gives the owner a hard time.

## Rung 4 — Briscola that reads the opponent

**Why:** remove A1.1 on a big game against an opponent whose way of playing is
**not** known in advance — the vicious circle for real.

**New:** move model plugged into the belief (machinery from rung 2b); weighted
sampling (the exchangeable shortcut no longer applies); strategy ↔ belief
iteration by levels, toward equilibrium (strategy.md §5).

**Verification:** measured arena improvement over rung 3; accuracy of the move
model on hands not used to build it; on reduced Briscola variants, comparison
with the exact equilibrium computed by regret minimization. Kuhn poker (known
value −1/18) may be used as a one-off check of the equilibrium code — a test,
not a rung.

## Rung 5 — Scopone scientifico

**Why:** teams of two; a 40-card full deal makes the volume of simulations too
big for Python.

**New:** team play (coordination without talking, information shared only
through moves); **compiled fast engine** (language to choose), verified against
the Python oracle.

**Verification:** differential testing (many random positions, identical answers
from both engines); arena.

---

## Mapping to goals (see [`GOALS.md`](GOALS.md))

- **Goal 2 — Strategy:** rungs 1–3.
- **Goal 3 — Opponent-aware beliefs:** rung 2b (known opponent), rung 4 (unknown).
- **Goal 4 — Fast engine:** rung 5 (may move earlier if measurements require).
- Goals 5–6: after the ladder, not planned yet.

## Later (parked, not planned)

Ideas from the first draft, kept only so they are not lost: Klondike solitaire
(determinization without an opponent — dropped: rung 3 covers determinization),
Kuhn/Leduc poker as rungs, Tressette (follow-suit constraints), Hearts (three or
more sides), Bridge card play (learned move models from human games), heads-up
Texas Hold'em with bluffing (equilibrium with abstraction).
