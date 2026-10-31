# JOKER — Game Assumptions

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

> **Status:** COMPLETE for the current phase (2026-10-29). New assumptions that
> emerged from the Core Model draft are `proposed`: S5.5, S5.6, S7.8.
> The chronological history of how each decision was reached is in
> [`../DECISIONS_LOG.md`](../DECISIONS_LOG.md).

## Legend

- **Scope tags:**
  - `[Project]` — holds for the whole project, all goals.
  - `[Goal 1]` — holds for Goal 1 only; later goals may replace it.
  - `[Permanent]` — a project-wide exclusion that will never be lifted.
- **Status:** `proposed` (under discussion) · `decided` (owner-approved) ·
  `verified` (confirmed by tests — reserved for later) · `unsupported` (explicitly
  out).
- Template used where useful (from the brief): **Assumption / Justification /
  Cases where it fails / Consequence / Test / Status**.

---

# Part A — Semantics of the probability computation

## A0 — Which probabilities we compute `[Goal 1]` _(decided)_

**Belief over hidden cards only.** Examples: "P(opponent holds card X)",
"P(next draw is a trump)", "P(player 3 is my partner)", the distribution over who
holds which hidden cards.

Probability of a future event (e.g. winning a trick) is **out of Goal 1**: it would
require an assumption about how the remaining play unfolds. It may later be built
as a layer on top of A0.

## A1 — Chance outcomes are weighted by their declared probability `[Project]` _(decided)_

- **Assumption:** every combination of chance outcomes (shuffles, deals, random
  role draws, ...) consistent with what the observer has seen is weighted by its
  declared chance probability.
- **Special case:** with a uniform shuffle (S2.2 default), every consistent card
  arrangement is equally likely.
- **Test:** brute-force enumeration on tiny games must match the module's output.

## A1.1 — Goal 1 choice model: player choices add no weight `[Goal 1]` _(decided)_

"Choices add no weight" is **not** the same as "every choice is equally likely"
(a random player). They give different numbers:

> Spades led; the opponent holds 2 cards and plays 7♠. Two equally likely worlds:
> A = {7♠, 3♥} (7♠ was the only legal move), B = {7♠, K♠} (7♠ was one of two).
> - Random-player reading: A is twice as likely → P(remaining card is a spade) = 1/3.
> - **"No weight" reading (chosen):** only the facts count (had 7♠, had a spade) →
>   A and B stay equal → P(spade) = 1/2.

- **Choice fully observed** by the observer: it does not change the weight of the
  possible worlds; only the facts it reveals are used.
- **Choice not observed** (Hearts pass, Skat discard, draw-poker discard, secret
  role choice): it carries no information, so its outcome is spread **uniformly
  over its legal options**.
- Whether a choice is observed is **derived** from what the observer sees of its
  effects (S7.2), not declared.
- **Open technical point** (for the probability module design): exact weighting
  for *partially* observed choices ("discarded one card, I don't know which"),
  to be fixed and verified with brute-force tests.
- **Justification:** faithful version of "type 1 only" (A2): use rule-forced facts,
  never the *why* of a choice — not even a "random" why.
- **Cases where it fails:** real opponents' choices leak information; the true
  posterior is then different.
- **Consequence:** results are exact *under the stated model*, not the true
  posterior of a strategic game.
- This choice model is a **replaceable component**: Goal 2 swaps it for a
  realistic opponent model (which must also receive the match state, S8.1).

## A2 — Only rule-forced information (type 1), never strategic preference (type 2) `[Goal 1]` _(decided)_

- **Type 1 (used):** information the rules force, regardless of intent — e.g. a
  player who does not follow suit must be void in that suit.
- **Type 2 (ignored):** information from *why* a player chose one legal move over
  another.
- Rule-forced constraints are **never written by hand**: they emerge from
  consistency-by-replay (S7.4).

## A3 — Rule verifiability classes and trust policy `[Project]` _(decided)_

The physical model makes some things impossible (you cannot play a card you do not
hold). Every other **regulatory rule** can be broken, and is classified by when a
violation can be detected:

| Class | Example | Effect on belief | Trust toggle (default) |
|---|---|---|---|
| **(i) verifiable immediately** | drawing when you should not | none — checkable from what is seen, says nothing about hidden cards; used only to validate input | not applicable |
| **(ii) verifiable later** | following suit (a renege is exposed when the player later plays that suit) | this is what produces type-1 constraints | on/off (default: **trust**) |
| **(iii) never verifiable in the game** | a constraint on cards that are never revealed | would constrain hidden cards with no way to check | on/off (default: **do not trust**) |

- Verifiability depends on the **observer** (only the receiver can check a Hearts
  pass) and on the **time window** (whether end-of-hand inspection counts).
  Therefore the **game author declares the class of each rule**, and tests check it.
- **Detected violation:** if trusting a class-(ii) rule leaves **no** consistent
  world (a renege was exposed), the engine must report "violation detected" and
  recompute without trusting that rule for that player — never crash.
- Not trusting a rule does not mean assuming opponents cheat: it only means not
  relying on something we cannot check.

---

# Part B — Structural modeling assumptions

## S1 — Cards and zones

### S1.1 — The deck is a multiset `[Project]` _(decided)_
Cards may be duplicated (two-deck games such as Burraco/Canasta). Each physical
copy gets an internal label (7♥#1, 7♥#2). Treating copies as distinct gives
**exact** probabilities for any event defined on card attributes (every unlabeled
configuration corresponds to the same number of labeled ones). Labels only make
exact enumeration slower; multiset-aware counting is a deferred optimization.

### S1.1b — Copy labels are never observable `[Project]` _(decided)_
Observers see a card's **visible attributes** ("a 7♥"), never its internal copy
label. Otherwise labels would leak information that does not exist at the table,
and replay (S7.4) would reject worlds that differ only by which copy is where.
If copies are distinguishable at the table (e.g. two decks with different back
colors), that is expressed by a **visible attribute** (S1.6), never by the label.

### S1.2 — Cards have free-form attributes `[Project]` _(decided)_
A card is an identity plus an attribute dictionary. Suit/rank live in an optional
"classic cards" library, never in the core.

### S1.2a — Goal 1 card library `[Goal 1]` _(decided)_
Cards with **ranks, face cards, suits, and jokers**, in both the **Italian** and
the **French** families. Which cards and how many are used is defined **per game**
(Italian 40, French 52, 32/36-card subsets, jokers, multiple decks). Non-suited
decks (UNO, tarot, custom) are deferred, not excluded.

### S1.3 — Zones are generic named containers `[Project]` _(decided)_
Stock, hands, table, discard, captured piles, exposed trump, ... Each zone has an
owner (none or a player) and is **ordered** (a stack: the next draw is a position)
or **unordered** (a set: a hand).

### S1.4 — Zones are atomic `[Project]` _(decided)_
All cards in a zone share the same properties (visibility, owner, ordering). Mixed
situations use **separate zones** (Briscola's face-up trump is `stock_exposed`,
distinct from `stock_hidden`; a card shown only to player 2 moves to a zone visible
to {owner, player 2}).
- Zones are **declared in advance** in the game definition (possibly many); no
  zones are created at runtime.
- Physical relations between zones (the exposed trump is drawn last) are expressed
  by the **rules**.
- Zone visibility is about **now**; knowledge from the past lives in the
  information state (S5).

### S1.6 — Attributes are grouped into facets; zones show facets `[Project]` _(decided)_
- A card's attributes are grouped into **facets**. Default: two facets, `back`
  (back color / design) and `face` (suit, rank, figure).
- Facets are **logical, not physical**: a card physically has two sides, but a game
  may define more facets when an observer can see only part of a side (e.g. suit
  visible but rank hidden). The number of facets is open, defined per game.
- A zone's visibility is, per observer, the **set of facets** that observer sees:
  opponent's hand `{back}`, own hand `{back, face}`, face-up table `{face}` or
  `{face, back}` (declared by the game), bottom of the stock `{}` (count only).
- Zones stay atomic (S1.4): all cards in a zone show the same facets to the same
  observer. For single-deck games `back` is identical for all cards, so nothing
  changes and nothing costs extra.
- **Example (owner's):** two decks with red and blue backs. I hold the blue A♠;
  the opponent's hand shows only red backs → the opponent cannot hold an A♠. This
  emerges automatically from replay (S7.4): worlds where the opponent holds the
  other A♠ would have shown a blue back.
- **Top of the stock is a separate zone** (decided): its back reveals which deck
  the next draw comes from, so it is a 1-card zone `stock_top` `{back}` above
  `stock_rest` `{}`, refilled automatically by the framework after each draw. This
  keeps zones atomic; no per-position exceptions exist.

### S1.5 — Zone card counts `[Project]` _(decided)_
Counts drive the belief directly (opponent holds 3, stock 20 → an unseen card is in
that hand with probability 3/23). Each zone has a `count_visible_to` property
(default: everyone), separate from face visibility.
- `[Goal 1]` if an observer cannot see a zone's count → `unsupported`.
- Later: sum over possible counts with a prior derived from history and rules.

## S2 — Deck and chance

### S2.1 — Deck composition is known and finite `[Permanent]` _(decided)_
The full multiset of cards is known to everyone. **Collectible / trading card games
and private custom decklists are never handled.** Deck-builders (e.g. Dominion) fit
as long as composition stays derivable from public information.

### S2.2 — Shuffles are uniform by default `[Project]` _(decided)_
The shuffle distribution is a **parameter**, default uniform. Fails for imperfect
real shuffles or stacked decks.

### S2.3 — Draws are never independent `[Project]` _(decided)_
A model property: card identities and zones are tracked, so without-replacement
dependencies come out naturally.

### S2.4 — Generic discrete chance events `[Project]` _(decided)_
Discrete, finite, with a declared distribution: dice, random dealer, cutting the
deck, a random card turned. Shuffle, deal and draw are special cases.

### S2.5 — Mid-game reshuffles `[Project]` _(decided)_
After a reshuffle the order is uniform again, but knowledge of *which* cards are in
the new stock stays in the information state.

## S3 — Players and roles

### S3.1 — N players, fixed per game `[Project]` _(decided)_
N ≥ 1, fixed at the start. Eliminated players stay in the model as inactive.

### S3.2 — Teams are state properties, possibly hidden `[Project]` _(decided)_
A team may be hidden, derived from cards, and revealed during play (Briscola a
chiamata: the partner is whoever holds the called card).

### S3.3 — Roles are player properties `[Project]` _(decided)_
Dealer, declarer, Bridge dummy (a zone visible to everyone). Asymmetry is expressed
by zones, visibility and rules. Roles may be hidden and derived from the state.

### S3.4 — The observer is an explicit parameter `[Project]` _(decided)_
A specific player, a **public observer** (public information only), or an
**omniscient** observer (tests only). Main guard against leakage.

### S3.5 — Chance is explicit (Nature) `[Project]` _(decided)_
Every random event is an explicit choice point of the Nature actor with enumerable
outcomes and declared probabilities — never hidden randomness in game code (S7.2).

### S3.6 — Hidden variables beyond cards `[Project]` _(decided)_
Hidden state = hidden card locations **plus** other hidden variables (roles, teams).
No extra information layer is needed. Cases: (a) derived from cards; (b) assigned
by chance (a Nature outcome); (c) chosen secretly by a player (a hidden choice,
A1.1). `[Goal 1]` supports all three.

### S3.7 — Only rule-defined communication is modeled `[Project]` _(decided, for now)_
Players communicate only through choices whose effects the rules define (e.g.
Tressette "busso / striscio / volo"). Informal table talk and illegal signaling
between partners are not modeled.

## S4 — Turn structure

### S4.1 — Speed is never a game factor `[Permanent]` _(decided)_
- Acting faster never matters. Simultaneous conflicts are resolved by a **fixed
  rule** (e.g. seat priority) or an explicit **chance event**, never by reaction
  time.
- **Excluded:** Speed/Spit, Slapjack, Ligretto, Dobble/Spot It, UNO "jump-in", any
  "first to grab" mechanic → `unsupported`.

### S4.2 — The state declares who acts `[Project]` _(decided)_
One player, several players (simultaneous), Nature, or nobody (terminal). No fixed
alternation; turn order comes from the rules. "Mixed" structure = this answer
changes during the game.

### S4.3 — Simultaneous phases are atomic joint actions `[Project]` _(decided)_
Each actor chooses without seeing the others; choices are applied together; what is
visible afterwards follows from the rules and the destination zones. The physical
"face-down, then reveal" procedure is not modeled.

### S4.4 — Hidden player choices are supported `[Project]` _(decided)_
Hearts pass, Skat discard, draw-poker discard. In Goal 1 they follow A1.1.

### S4.5 — Out-of-turn actions `[Project]` _(decided)_
Interrupts (Contract Rummy "May I?") are simultaneous decision points where several
players may act or pass, resolved by rule-defined priority.

## S5 — Observation model

### S5.1 — Information state = observation history `[Project]` _(decided)_
Perfect recall by default. A "memoryless" toggle (knows only what is visible now)
is part of the design; implementation deferred.

### S5.2 — Observations are always derived `[Project]` _(decided)_
Observations are generated automatically from state changes (S7.2) and the
visibility of zones and variables — games never declare observations by hand.
When a card moves, an observer sees the attributes of the facets (S1.6) it can see
in the source or destination zone, never the copy label (S1.1b); anyone who sees
the counts sees **that** a move happened. A choice is observed only through its effects on visible state.

### S5.3 — Raw observations are the source of truth `[Project]` _(decided)_
The information state stores raw observations. Everything else (constraints, known
locations, candidate sets, per-card "seen" summaries) is a **derived view**. Rule
constraints come from replay (S7.4) under the trust policy (A3).

### S5.4 — Non-leakage is an architectural requirement `[Project]` _(decided)_
The probability module receives **only** an information state, never the physical
state. Mandatory test: two games producing the same observation sequence for an
observer must produce the identical belief.

### S5.5 — Control flow is public `[Project]` _(proposed, from the Core Model draft)_
Who acts, which phase the game is in, and pending automatic steps (e.g. queued
draws) are always observed by everyone — as at a real table. Since control flow may
depend on hidden cards (Hearts: the holder of 2♣ leads), this is information, and
replay uses it automatically.

### S5.6 — An actor always observes its own choice `[Project]` _(proposed, from the Core Model draft)_
A player knows which option it chose (as it saw it), even when the effects are
hidden from itself (e.g. picking a face-down card from an opponent's hand).

## S6 — Horizon

### S6.1 — Hierarchical structure: match → hand → phases `[Project]` _(decided)_
- The match state (scores, dealer, hand number, end condition) is part of the
  physical state, usually public, and carries over between hands.
- Hands are independent **only w.r.t. card information** (a reshuffle resets it;
  exceptions: non-uniform shuffles, explicit carry-over rules), **not** w.r.t.
  state or rules (Tressette "chiamarsi fuori" ends a hand early).
- `[Goal 1]` beliefs are computed within a hand; the match state is a public input.

### S6.2 — No finiteness assumption for beliefs `[Project]` _(decided)_
Belief is computed over a past history, which is always finite (War/Bataille can
cycle forever; "first to 21" matches are unbounded). Forward-looking goals must
**detect** cycles, never assume them away.

### S6.3 — Discounting `[Project]` _(decided)_
Not applicable while there are no utilities. Revisit with S8.

## S7 — Rule expressivity (how a game is written)

### S7.1 — Games are written in Python with framework primitives `[Project]` _(decided)_
Hybrid approach: not free-form code, not (yet) a declarative DSL.

### S7.2 — Three primitives; all state changes go through them `[Project]` _(decided)_

| | Primitive | Does |
|---|---|---|
| **M1** | Move card | from zone/position A to zone/position B |
| **M2** | Set variable | scores, roles, flags (e.g. "declared busso"), each with its own visibility |
| **B1** | Choice point | one or more actors (players or Nature) choose among options |

- Game code may only **read** state outside these primitives (legality, who acts,
  phase end) and must be **deterministic**: no `random`, no external state.
- Reveal = M1 into a visible zone; a declaration = B1 + M2 + a regulatory rule.
  Shuffle / deal = B1 (Nature) + M1. Nature vs player only changes who supplies
  the probabilities (game-declared vs the choice model).
- **Exhaustive** w.r.t. the state definition (cards in zones + variables), given
  S2.1 (no cards created/destroyed), S1.4 (zones declared in advance), S3.1 (fixed
  players). **One deliberate redundancy:** M1 is technically a special case of M2,
  kept separate because card conservation tests and the probability module rely on
  the "cards in zones" structure. **Atomic:** each does exactly one thing.
- Guarantees by construction: explicit chance, automatic event log and replay,
  automatic observations, no leakage.

### S7.3 — Physical impossibility vs regulatory rules `[Project]` _(decided)_
Physical constraints are enforced by the model and can never be violated.
Regulatory rules carry a verifiability class (A3).

### S7.4 — Consistency is defined by replay `[Project]` _(decided)_
A candidate world (a combination of chance outcomes and hidden choices) is
**possible** iff replaying the game with it produces exactly the observations the
observer actually saw, and every action respects the regulatory rules currently
trusted (A3).
- Example: spades led, player 2 plays a heart. World "player 2 held K♠": on
  replay, playing a heart was illegal → impossible (if class (ii) is trusted).
  The constraint "void in spades" is never written by anyone.
- Probability of an event = weight of possible worlds where it holds ÷ weight of
  all possible worlds (A1, A1.1).
- Replay is the **definition** of correctness and the test oracle; faster methods
  are optimizations that must agree with it.

### S7.5 — DSL deferred `[Project]` _(decided)_
No declarative Domain-Specific Language for now. The primitives are designed as its
future compilation target (and for LLM-assisted rule translation).

### S7.6 — Every choice point has finitely many options `[Project]` _(decided)_
From the brief (§2.1). Continuous quantities (e.g. poker bet sizes) must be
discretized. Options may be numerous, but always a finite, enumerable set.

### S7.7 — Rules are a fixed function of the state `[Project]` _(decided)_
The game's rules never change during play. "Rule changes" (variants switched on by
an event, a trump suit chosen mid-hand) are modeled as **state variables** (M2)
that the rules read.

### S7.8 — Options are what the actor can distinguish `[Project]` _(proposed, from the Core Model draft)_
A player's options are defined by what that player can tell apart: two physical
copies it cannot distinguish (same visible attributes, same zone) are **one**
option. Example: hand {7♥, 7♥, K♠}, hidden discard of one card → 2 options
(P(discard a 7♥) = 1/2 under A1.1), not 3 (which would give 2/3). Nature outcomes
are not affected (they use concrete copies, S1.1).

## S8 — Objectives (future goals — not used in Goal 1)

### S8.1 — The objective is defined at the match level `[Project]` _(decided)_
- The objective never changes during a hand; it is always the match-level one.
- A hand is a subgame; its value is its **effect on the match outcome**. Example:
  in Scopa to 21, an opponent scoring a point matters very differently at 20 vs 5.
- "Maximize this hand's points" is only an explicit, labeled approximation.
- Goal 2's choice model must receive the match state as input.
