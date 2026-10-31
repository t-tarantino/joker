# JOKER — Goals and Roadmap

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

This file keeps the *big picture* visible while we work on one goal at a time.
We design each goal so the system stays **ready to host the next goals** without
rewrites.

---

## Permanent project-wide exclusions

These are never in scope, for any goal (details in
[`architecture/assumptions.md`](architecture/assumptions.md)):

- **Collectible / trading card games** and games with private custom decklists —
  deck composition must always be known (S2.1).
- **Speed / real-time games** — acting faster must never matter (S4.1).

---

## Goal 1 — Card-based probabilities for arbitrary card games

_Status 2026-10-31: the "done when" criterion is met; formal closure (now or after
Tressette) is still the owner's decision. Active work has moved to Goal 2._

**Statement:** build all the structure needed to model an *arbitrary* card game
and compute its **probabilities based only on the cards** — no game theory, no
opponent modeling ("only the cards, not the people").

**Why this goal first:**
- It removes the hardest, most subjective part (strategic reasoning about people).
- It is **easily verifiable**: cards don't lie — given the rules, the probabilities
  are a matter of fact we can check by brute force on small cases.

**In scope:**
- Core Model: how we represent an arbitrary card game.
- Engine: enumerate / sample the card configurations consistent with observations.
- Probability module: compute probabilities over those configurations.

**Out of scope (deferred, NOT part of Goal 1):**
- Classifier / game-characteristics analyzer.
- Algorithm applicability checker and solver selector.
- Equilibrium / game-theory solvers (minimax, CFR, MCTS, ...).
- Opponent modeling and strategic belief updates.

**Deliberate assumption (documented, not a bug):** chance outcomes consistent
with what we observe are weighted by their chance probability (with a uniform
shuffle: every consistent card arrangement is equally likely). Player choices add
**no** weight: we use only the facts they reveal, and a hidden choice is spread
uniformly over its legal options. This throws away the information that
opponents' choices would leak. The brief (§3) notes this is *not* a true posterior
— which is acceptable for Goal 1, by design. See A1 / A1.1 in
[`architecture/assumptions.md`](architecture/assumptions.md).

**Probability type (decided 2026-10-29): (a) belief over hidden cards only** —
pure combinatorics, no people-assumption. Future-event probability (b) is
deferred and may later be layered on top of (a).

**Done when:** we can define a non-trivial card game, ask a card-probability
question, and the answer matches an independent brute-force check.

---

## North star (agreed 2026-10-31)

- A **general** system that plays many card games with little code per game —
  not one bot per game, not the strongest program in the world.
- **Target strength: beat an average human player.**
- Full reasoning, tool hierarchy L0–L6 and roadmap:
  [`architecture/strategy.md`](architecture/strategy.md).

## Future goals — big picture, NOT being worked on yet

Reordered 2026-10-31 (proposal). Each goal is reached through famous games, one
new technology per game: see the ladder in [`ROADMAP.md`](ROADMAP.md).
No commitment to details.

- **Goal 2 — ACTIVE (started 2026-10-31) — Strategy (expected value + move
  choice, levels L4/L5)**, with an arena and reference bots: Blackjack ✅ (rung 1
  solved), Texas Hold'em (cards, pot, players still in), Briscola.
- **Goal 3 — Opponent-aware beliefs:** remove A1.1 (it was a Goal 1
  simplification only). Plug a move model into the choice model, weighted
  sampling, iterate strategy ↔ belief.
- **Goal 4 — Fast generic engine** in a compiled language, verified against the
  Python reference by differential testing.
- **Goal 5 — Accelerators per class of games** — the concrete role of the
  analyzer / "classifier": detect properties, switch on the fast methods they
  allow. The budgeted solver selector belongs here, once several methods exist.
- **Goal 6 — Learned models** (move model, situation value) and game-specific
  tuning for the games we care most about.

Interfaces (GUI) grow alongside every goal.

The authoritative long-term vision remains
[`../JOKER_PROJECT_CONTEXT_V3.md`](../JOKER_PROJECT_CONTEXT_V3.md).
