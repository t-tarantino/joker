# Rung 1 — Blackjack: report

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

_2026-10-31. Rung definition: [`../ROADMAP.md`](../ROADMAP.md) §"Rung 1"._

**Result: solved.** Our expected values match the published reference tables to the
last printed digit (6 decimals) and our basic strategy matches the published
charts. The verification table is in §4. One open point remains in §6:
a published single-deck *game total* that we do not reproduce.

---

## 1. What blackjack forced us to build

| New piece | Where | In plain words |
|---|---|---|
| **Utility of a hand** | `Game.utility` (`joker/core/spec.py`) | What a finished hand is worth to a player: here, money won or lost, in original bets. |
| **Generic expectimax over information states** | `joker/strategy/expectimax.py` | Value of every choice = best over my options, probability-weighted average over chance. It works on *what the player knows*, not on the true state: the dealer's hidden card is averaged over, never peeked at. Works for any one-player game written for the engine. |
| **Caching of identical situations** | same file | Two situations with the same remaining cards and the same hands are computed once. Identical copies of a card (the four 7s) are interchangeable, so a draw branches once per *rank*, not once per physical card. |
| **Fast blackjack solver** | `joker/strategy/blackjack.py` | Same rules, written directly on "how many cards of each rank are left", in floating point. The whole single-deck game in ~3 s, where the generic solver needs ~4 s for one decision. Checked against the generic one. |
| **Arena (Monte Carlo)** | `joker/arena.py` | Plays N hands through the engine and reports the average with its margin of error (95%). |
| **Reference strategies** | `joker/strategy/blackjack_reference.py` | A published basic strategy (Nairn 2019) and "play a chart by totals". |

The game itself is `joker/games/blackjack.py`, written with the same engine
primitives as Briscola and Scopone.

## 2. Rules and modeling choices

Configurable (`BlackjackRules`): number of decks (or infinite), dealer hits or
stands on soft 17, doubling (any two cards / 9-11 / 10-11 / none), doubling after a
split, maximum number of hands from splitting, resplitting aces, hitting split
aces, blackjack payout. Always: the dealer **peeks** for blackjack when showing an
Ace or a ten (US rules), and loses only the original bet to a dealer blackjack.

Modeling choices, all exact for these rules:
- **Ranks only.** Suits never matter and 10/J/Q/K behave the same, so the deck
  lists A, 2…9, T (16 tens per deck). Every probability is unchanged.
- **The hole card is a real hidden card** when the dealer must peek (up card A or
  T): the player's decisions are taken *without* knowing it, and "the dealer
  peeked and has no blackjack" is public information. With other up cards it is
  drawn when revealed (lazy draw, DR-2): unseen, it is interchangeable with the
  shoe, so nothing the player sees changes.
- A hand totalling 21 stands automatically (hitting it never helps).
- After a split, each new hand gets its second card when its turn comes.
- Each hand starts from a full, freshly shuffled shoe ("off the top").

Not modeled yet: surrender, the no-hole-card (European) rule, side bets.

## 3. How the values are computed

Everything is the **expected result per original bet**. Values of single hands
are **conditional on the dealer not having blackjack** (the dealer has already
peeked), as in every published table.

**Peeking is information.** If the dealer shows an Ace and has no blackjack, the
hole card is not a ten, so a ten is slightly *more* likely to be the player's next
card. Exactly (Griffin, *The Theory of Blackjack*): with n unseen cards, n_k of the
blackjack-making rank k,
P(next = k) = n_k / (n − 1) and P(next = i ≠ k) = n_i / (n − 1) · (n − n_k − 1)/(n − n_k).
The generic solver never uses this formula: it finds the same numbers by itself,
by averaging over the possible hidden hole cards. Their agreement (§4) is a strong
check of both.

**Splitting** is famously hard to compute exactly with a finite deck, because the
hands share the deck. Status:
- **Infinite deck:** exact, with resplits to any number of hands (hands are then
  independent of each other).
- **Finite deck, split once:** Griffin's approximation (each split hand valued with
  both pair cards removed), within ~3·10⁻⁶ of the exact value per Nairn 2019; our
  numbers reproduce Nairn's exact table to 6 decimals.
- **Finite deck with resplits:** not implemented yet (§7).

Strategy after splitting, in the fast solver: each hand is played knowing its own
cards and the pair card, not the other hands' cards. The generic solver, used on a
split, would use everything seen.

## 4. Verification

| Check | Reference | Result |
|---|---|---|
| Infinite deck, 260 published values (26 rows × 10 up cards): stand, hit, double, split (S17, DAS, split to 4) | Wizard of Odds, infinite-deck table ([link](https://wizardofodds.com/games/blackjack/expected-return-infinite-deck/)) | **all equal to 6 decimals** |
| Infinite deck, whole game | same: −0.511734% | **−0.5117336%** |
| Infinite deck basic strategy chart | the standard S17/DAS chart; two cells (A,2 v 5 and A,4 v 4: hit) differ from the *multi-deck* chart and are confirmed by the published values | equal |
| 6-deck basic strategy chart (S17, DAS) | the standard published 4–8 deck S17/DAS chart | equal (hard 12 v 4 depends on the two cards) |
| Single deck, 90 published composition-dependent cells (stand, hit, double) | Wizard of Odds, 1 deck S17 ([link](https://wizardofodds.com/games/blackjack/appendix/9/1ds17r4/)) | **all equal to 6 decimals** |
| Single deck, split once, with and without doubling after split, played by Nairn's strategy | Nairn 2019 Tables 1–2 ([arXiv:1909.13710](https://arxiv.org/abs/1909.13710)) | equal within 3·10⁻⁶ (the size of Griffin's approximation) |
| Fast solver vs generic solver (engine rules, exact fractions, hidden hole card) | — | equal to 10⁻¹² on decisions in a small shoe and in a full deck, and on the **whole game** in a small shoe |
| Arena vs exact value, 10 million hands each | exact value of the same strategy | **within the margin** (0.4 and 1.0 standard errors, §5) |
| Rules through the engine | hand-made scenarios (dealer blackjack, 3:2, split + double, split aces, 21 after split ≠ blackjack) | pass |

## 5. Results

Player expected value per hand (negative = house edge), optimal play deciding on
the exact cards seen:

| Rules | Expected value |
|---|---|
| infinite deck, S17, DAS, split to 4 | −0.5117% |
| infinite deck, H17, DAS, split to 4 | −0.7311% |
| 6 decks, S17, DAS, split once | −0.4569% |
| 1 deck, S17, no splitting | −0.3335% |
| 1 deck, S17, no DAS, split once | +0.0248% |
| 1 deck, S17, DAS, split once | +0.1541% |

**Monte Carlo through the engine** (10 million hands per row, `tools/blackjack_report.py`):

| Rules | Simulated (95% margin) | Exact | Gap |
|---|---|---|---|
| 1 deck, S17, no splitting | −0.319% ± 0.070% | −0.3335% | +0.40 standard errors |
| 6 decks, S17, DAS, split once | −0.494% ± 0.071% | −0.4569% | −1.02 standard errors |

Both inside the margin: the rules in the engine, the strategy played through the
engine and the exact solver tell the same story. (6-deck run: 37 min on 18 cores;
in its split hands the player ignores the other hand's cards, a difference far
below the margin.)

Charts: `python -m tools.blackjack_report` prints the infinite-deck and 6-deck
charts (H hit, S stand, D double else hit, Ds double else stand, P split).

## 6. Open point: Nairn's single-deck game totals

Nairn's Table 4 gives game totals for his single-deck strategy: −0.0283% (no double
after split, split once) and +0.1007% (double after split). Playing exactly his
strategy, we get **+0.0155%** and **+0.1445%**, about **0.044% higher** in both.
The per-hand values agree with his tables to 6 decimals, which rules out his
strategy and the split values as the cause. Our game total is
independently confirmed by the generic solver and by Monte Carlo, and our
single-deck results are in line with the Wizard of Odds' single-deck total
(+0.18% with resplitting). Most likely the paper totals the game under a convention we
cannot see (e.g. blackjack bookkeeping). Not blocking; worth a look if a second
finite-deck total turns up.

## 7. What is next

- Finite-deck **resplitting** (Nairn's approximation, accurate to ±0.001 per
  value), then the Wizard of Odds single-deck and 6-deck totals as references.
- Surrender, no-hole-card rule.
- **Card counting** (strategy depending on the cards already played from a shoe):
  the solver already takes any shoe composition as input.
- Blackjack in the GUI (not done): record a real hand, see the value of each option.

**Limits of the generic tools, to lift in the next rungs:**
1. `SoloExpectimax` handles one deciding player. Next: opponents with a known
   way of playing, treated as chance (rung 2b).
2. It visits everything: fine for blackjack, impossible for a full Briscola or
   Scopone hand. Next: determinization (rung 3).
3. Its caches grow without limit (a whole-game run on a small shoe reached
   12.8 GB). Needs bounded caches.
4. It builds its belief by playing forward from the start of the hand; it is not
   yet connected to the Goal 1 belief computed from what was actually seen (needed
   for live advice in the GUI and for card counting).
5. The arena is one-player only; Hold'em needs several seats and per-seat results.
- Speed of the generic solver: ~4 s per decision on a full deck. Fine as an oracle.
