# JOKER — Probability Module (Goal 1 heart)

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

> **Status:** FIRST DRAFT (2026-10-29) — for owner review. §1–§2 are `decided`
> (they restate assumptions); §3–§6 are `proposed`.

## 1. Purpose `[Goal 1]` _(decided)_

Given an **information state** (never a physical state — S5.4), compute
probabilities about the hidden part of the game: belief over hidden cards and other
hidden variables (A0), under explicit assumptions (A1, A1.1, A3), with no game
theory.

## 2. Foundation _(decided)_

- A **world** is a complete history: every Nature outcome and every player option
  from the start of the hand until now.
- A world is **possible** iff replaying it reproduces the observer's actual
  observations and every player option respects the rules currently trusted
  (S7.4, A3).
- Probability of an event = weight of possible worlds where it holds ÷ weight of
  all possible worlds.
- Card arrangements, random role draws, secret choices are all parts of worlds;
  card-specific combinatorics are only optimizations.

## 3. Weighting of worlds (DR-6) `[Project]` _(proposed — resolves the A1.1 open point)_

```
weight(world) = Π over Nature steps:  P(outcome)                       (A1)
              × Π over player steps:  w(step)
```

Let, at a player step: `π` = the choice model's distribution over the actor's
allowed options (allowed = physically possible and passing the trusted rules), and
`C` = the allowed options that would have produced **the same observation** for
the observer at that step (computed by applying each option and deriving the
observation).

- **Goal 1 — "no information" mode (A1.1):** `w = π(chosen) / Σ_{o∈C} π(o)`,
  with `π` uniform, i.e. `w = 1 / |C|`.
  - Fully observed choice: `C = {chosen}` → `w = 1` (no weight, only facts).
  - Fully hidden choice: `C` = all allowed options → `w = 1 / |allowed|`.
  - Partially observed ("discarded one red-backed card"): `w = 1 / |C|`.
  - **Defining property:** for each predecessor world, the weights of its
    continuations within `C` sum to 1, so **a choice never re-weights the past**;
    it can only rule worlds out (when `C` is empty). This is exactly "choices add
    no information".
  - Check against A1.1's example (7♠): both worlds have `C = {7♠}` → `w = 1` →
    P(spade) = 1/2 ✓.
- **Goal 2 — "Bayesian" mode:** `w = π(chosen)` with `π` a real opponent model.
  The past *is* re-weighted by how likely the observed behavior was. Same
  interface, different mode: nothing else in the module changes.
- If the observer is the actor, it saw its own option (S5.6) → `C = {chosen}` →
  `w = 1`.
- Simultaneous steps use joint options; `π` is the product of the actors' `π`.

## 4. Queries _(proposed)_

Queries are written on **attributes and derived functions**, never on `CardId`s
(S1.1b):

| Query | Example |
|---|---|
| `P(predicate)` | P(player 1 holds the A of coins); P(player 1 has ≥ 2 trumps) |
| Location marginals | for every card type: probability / expected count per zone |
| Hidden variable / derived function | P(partner == player 3) (Briscola a chiamata) |
| Next chance step | distribution of the next card drawn from the stock |

"Next chance step" is allowed in Goal 1 only when **no player choice** can happen
before it (pure Nature lookahead — consistent with A0).

## 5. Result format _(proposed)_

```python
@dataclass(frozen=True)
class BeliefResult:
    value: float | Distribution
    exact: bool                      # exact enumeration vs estimate
    ci: tuple[float, float] | None   # confidence interval when estimated
    support: int | None              # number of worlds (exact) or effective sample size (MC)
    trust_policy: TrustPolicy        # what was trusted
    choice_model: str                # e.g. "UniformNoInformation"
    assumptions: tuple[str, ...]     # e.g. ("A1", "A1.1", "A3", "S2.2:uniform")
    warnings: tuple[Warning, ...]    # e.g. ViolationDetected(rule="follow_suit", player=2)
```

Every number states how it was obtained and under which assumptions (brief: never
present an estimate as exact).

## 6. Methods _(proposed)_

1. **Brute-force oracle** (tests only): enumerate every full history from the start
   of the hand, replay each, keep those matching the observations. Exponential;
   used only on tiny games as the reference all other methods must match.
2. **Exact incremental enumeration** (default for small/medium cases): walk the
   observation sequence step by step; at each step branch only over the hidden
   outcomes that reproduce the current observation, accumulating weights (§3).
   Impossible branches are pruned immediately instead of being replayed to the end.
   **Merge branches that reach the same state hash** (their futures are identical
   because the whole control state lives in `State` — DR-1): e.g. the order in
   which the opponent drew two cards stops mattering. _Goal 2 caveat:_ with a real
   opponent model, merging also requires the actors' information states to match.
   **Also merge branches that differ only by which copy of a card is where**
   (`Engine.canonical`, S1.1/S1.1b — implemented 2026-10-31): with multi-copy decks
   (a 6-deck blackjack shoe) every seen card would otherwise multiply the worlds
   by its number of copies.
3. **Monte Carlo — sequential importance sampling** (large cases): sample one
   hidden outcome per step among those consistent with the current observation,
   proportionally to its weight, and carry the importance weight. Report effective
   sample size and confidence intervals; resample when weights degenerate.
5. **Exact combinatorial method for exchangeable games** _(implemented
   2026-10-30, `joker/probability/exchangeable.py`)_: when a game declares
   `exchangeable = True` (unseen cards can be swapped with each other without
   changing anything the observer saw; no regulatory rule constrains unseen cards;
   every choice is fully observed), the belief is one representative world + the
   set of cards the observer has fully seen. Probabilities are exact
   (hypergeometric, Fractions) without enumerating worlds — e.g. Scopone right after
   the deal has 30!/(10!)³ ≈ 5.5·10¹² worlds. Checked against full enumeration on a
   miniature Scopone at every step for every observer; refuses (`Unsupported`) when
   a seen card moves unseen among look-alike cards.
4. **AUTO:** estimate the size of the exact frontier; use exact enumeration within
   the budget, otherwise Monte Carlo — and say so in the result.

## 7. Detected violations _(decided, A3)_

If no world is possible under the current trust policy, return a
`ViolationDetected` warning naming the rule and player whose distrust restores
consistency, and the recomputed result. Never crash, never return an empty
distribution silently.

## 8. Correctness

Every method must agree with the brute-force oracle on small games — the
verifiability that motivated Goal 1 ("cards don't lie").
