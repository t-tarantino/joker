# JOKER — Live Status Dashboard

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

This is the owner's control surface. **Keep it updated after every meaningful
change.** It always reflects the present, not history (history lives in
[`DECISIONS_LOG.md`](DECISIONS_LOG.md)).

**Current goal:** Goal 2 — strategy, through the ladder of games in
[`ROADMAP.md`](ROADMAP.md). **Rung 1 (Blackjack) solved**; next rung: Texas Hold'em.
Goal 1 (card probabilities) meets its "done when" criterion; formal closure is
the owner's call. See [`GOALS.md`](GOALS.md).

_Last updated: 2026-10-31_

**North star:** a general system; target = beat an average human player.
Big picture and roadmap: [`architecture/strategy.md`](architecture/strategy.md).

---

## Done
- Goal 1 scope agreed (belief over hidden cards; no classifier, no game theory).
- Core language: Python. Build-vs-reuse stance agreed.
- Game assumptions consolidated → [`architecture/assumptions.md`](architecture/assumptions.md).
- Core Model first draft → [`architecture/core-contracts.md`](architecture/core-contracts.md),
  [`architecture/probability.md`](architecture/probability.md),
  [`architecture/examples/mini-briscola.md`](architecture/examples/mini-briscola.md).
- **Milestone 1 code: Goal 1 walking skeleton** → [`IMPLEMENTATION.md`](IMPLEMENTATION.md).
- **Live mode** (DR-8): follow a real hand from what you see (`joker/live.py`).
- **Local GUI, Briscola, "Split Jester" style**: `python -m joker.gui`.
  Style chosen from four directions on the design canvas
  https://claude.ai/artifact/FQUmtRvxTMRArm8sfHJgvC.
- **Scopone scientifico in the GUI** (2026-10-30), with a new exact combinatorial
  method for exchangeable games (`joker/probability/exchangeable.py`).
- **GUI polish** (2026-10-30): yellow logo in the header, softer colors, standard
  suit symbols, suit → rank card picker.
- **Rung 1 — Blackjack solved** (2026-10-31) → [`rungs/rung-1-blackjack.md`](rungs/rung-1-blackjack.md):
  game in the engine; generic expectimax over information states (exact
  fractions, caching); fast blackjack solver; arena (Monte Carlo with margin of
  error). Published values matched to 6 decimals; infinite-deck house edge
  −0.511734% matched; basic strategy charts matched.
- **Blackjack in the GUI** (2026-10-31), with advice on every move (exact
  expected value). **One generic presentation for all three games**
  (`CircleProfile`, [`architecture/gui.md`](architecture/gui.md) §8); live mode now
  merges interchangeable copies of a card (needed for a 6-deck shoe).
- 53 tests passing (2 slow tests opt-in, also passing) + a GUI page test.

## In progress — awaiting owner review
- **Cards carrying over between hands (card counting)** — core change, to be done
  in another session: spec in [`handoffs/cards-across-hands.md`](handoffs/cards-across-hands.md).
  Today every hand restarts from a full deck (S6.1, `Engine.new_hand`); the GUI
  part follows once the core supports it.
- **Blackjack modeling choices** (rung report §2): ranks only, hole card hidden
  only when the dealer must peek, auto-stand on 21, peek always on.
- **Open point:** Nairn 2019's single-deck game totals are ≈0.044% below ours
  while every per-hand value matches (rung report §6).
- The GUI, on a real game.
- **Generic GUI principles** (brainstorm) → [`architecture/gui.md`](architecture/gui.md):
  circle of avatars, numbers instead of card backs, density by space, selection
  (focused player / focused card / lenses). Open questions in §6.
  **All three games use it with the same code**; provisional answers to §6 in use.
  **To review:** how the 6 incompatibilities met with Blackjack were solved (gui.md §8).
- Decisions DR-1…DR-7 (core-contracts §10) and assumptions S5.5 / S5.6 / S7.8 —
  already implemented with the recommended defaults.

## Next (proposed)
1. Owner tries the GUI on a real hand; collect feedback (flow, wording, missing
   questions).
2. Speed: early-hand clicks take ~1–2 s; optimize the enumeration.
3. More games in the GUI (game picker), starting with one with follow-suit
   (Tressette) to exercise rule trust and violation warnings.
4. Monte Carlo + AUTO method selection, for games too large for exact enumeration.
5. Fix the logo tagline typo ("inteligence" → "intelligence") in the source image
   (the GUI header uses only the icon, so it is not affected).

**Goal 2 ladder** ([`ROADMAP.md`](ROADMAP.md)): ~~rung 1 Blackjack~~ ✅ → **rung 2
Texas Hold'em** (cards, pot, players still in) → Briscola → Briscola reading the
opponent → Scopone. Blackjack leftovers (optional): finite-deck resplitting,
surrender, card counting.

## Open questions
- `strategy.md` §12: flagship and control game; solitaire as first step; source
  of recorded human games; compiled language (not urgent); close Goal 1 now or
  after Tressette.
- Version control: the project is not a git repository yet (ROADMAP "before
  rung 1"; waiting for the owner's go-ahead).
