# Handoff — Cards that carry over between hands (card counting)

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

_2026-10-31. Written for the Claude session that will change the core. Status:
**open**, owner's request. The GUI side will be done after this lands._

## 1. The problem

At the end of a hand everything resets: every card goes back to the deck. In a
real blackjack shoe the cards already played **stay out** until the shuffle, and
knowing which ones left is card counting — the most valuable piece of blackjack
strategy, and it costs nothing (we already record every card).

This is **not a GUI problem**. It comes from three places:

| Where | What it does today |
|---|---|
| `docs/architecture/assumptions.md` **S6.1** | "Hands are independent **only w.r.t. card information** (a reshuffle resets it)"; "[Goal 1] beliefs are computed within a hand". |
| `joker/core/engine.py` `Engine.new_hand` | puts **all** cards in `game.deck_zone`; only **match variables** carry over (`match_state` = variables only). |
| `joker/games/blackjack.py` | models every hand "off the top" of a fresh shoe (rung-1 report §2). |

Live mode (`joker/live.py`) and the belief (`joker/probability/belief.py`) both
start from `engine.new_hand(match_state)`, so they inherit the reset.

## 2. What is needed

### 2.1 Core: zones that live at match level
- A zone can be declared **match-level** (like `match_vars` for variables): its
  content carries over from one hand to the next. Blackjack: `shoe` and a new
  `discard` tray.
- `Engine` gets a way to go from the end of a hand to the start of the next one
  **from a state**, not from scratch: run `Game.end_hand` (which may move cards,
  e.g. hands → discard, and decide a reshuffle), keep match-level zones and
  variables, reset the rest. Suggested name: `Engine.next_hand(s) -> State`.
  `new_hand(match_state)` stays for the first hand.
- A **reshuffle** is an ordinary event of the game (discard → shoe), so S2.2
  (uniform shuffle) applies to it unchanged.
- Update **S6.1**: hands are independent w.r.t. card information *only when the
  game reshuffles*; match-level zones carry card information.

### 2.2 Belief and live mode: information spans the match
- The information state must be able to span several hands (the observations of
  hand 1, then hand 2, …), or equivalently the possible worlds at the end of hand
  k, with their weights, are the starting worlds of hand k+1.
- Recommended for live mode: `LiveSession.next_hand()` applies `engine.next_hand`
  to **every world of the frontier**, keeping the weights. This is exact also for
  cards that left **unseen**. Example: the dealer peeked with an Ace showing
  (so the hole card is known not to be a ten), then the player busted and the hole
  card went to the discard without being turned. The worlds keep it, so the
  remaining shoe is correctly a little richer in tens.
- `Engine.canonical` (copy merging) already keeps the frontier small: only cards
  that left unseen create worlds (at most one per hand in blackjack).
- `ExchangeableSession` (Scopone) needs the same `next_hand` only if a game with
  carry-over is also exchangeable; not needed now.

### 2.3 Blackjack game
- `shoe` and `discard` match-level; at the end of a hand all cards on the table go
  to `discard`.
- **Reshuffle rule:** the dealer reshuffles when the cut card is reached (a fixed
  penetration, e.g. 75% of the shoe), between hands. In live mode the person must
  also be able to say "the dealer reshuffled now" (the cut card position is
  physical and random): a match-level option or a NATURE outcome is fine.
- Optional, worth asking the owner: the **burn card** (first card after a shuffle,
  discarded unseen) and **other players' cards** at the table (seen, so they count:
  modeled as cards dealt face up to an extra zone, without modeling those players'
  decisions).

### 2.4 Solver (advice)
- `BlackjackSolver` already accepts any shoe composition. With several worlds
  (cards gone unseen), the value of a move is the **weighted average over worlds**
  of the solver's value for that world's shoe: exact, since expected values are
  linear in the worlds.
- New, for counting: the **value of the next hand before it is dealt** for the
  current shoe (`round_value` on the remaining composition) → "bet more / bet the
  minimum". Today `round_value` takes ~3 s on one deck: check the time on a
  6-deck shoe; caching or a faster path may be needed.

## 3. Acceptance tests (suggested)

1. **Two hands = one long history:** on a tiny game with carry-over, the possible
   worlds after hand 2 equal the brute-force oracle over the full 2-hand history
   (extend `joker/probability/oracle.py` across hands).
2. **Blackjack composition:** after a hand where everything was seen, the shoe in
   every world = previous shoe − cards seen; after a reshuffle = full shoe.
3. **Unseen hole card:** dealer shows A, peeks, no blackjack, player busts, hole
   card not shown → the next hand's P(next card is a ten) is slightly higher than
   with the hole card removed uniformly (exact value from the mixture).
4. **Old behavior unchanged** for games without match-level zones (Briscola,
   Scopone): all current tests pass.

## 4. After it lands (GUI, done in the GUI session)

- At the end of a hand: **"Next hand (same shoe)"** and **"New shoe"** instead of
  only "New hand"; a "Dealer reshuffled" button.
- Show cards played / left per rank, and the advised bet from the value of the
  next hand.
- Report to the owner and update `STATUS.md` / `DECISIONS_LOG.md`.
