# JOKER — Decisions Log

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

Chronological, append-only log of decisions. Newest at the top. Each entry:
what was decided, and why.

---

## 2026-10-31

- **Card counting needs cards to carry over between hands** (owner: "the game
  resets after every hand, we lose the most important part of the strategy").
  Diagnosis: not a GUI problem — assumption S6.1 (hands independent w.r.t. card
  information), `Engine.new_hand` (all cards back to the deck, only variables
  carry over) and the blackjack model ("off the top" every hand). Owner will have
  the core changed in another session; spec: `handoffs/cards-across-hands.md`
  (match-level zones, `next_hand` from a state, beliefs spanning hands, reshuffle
  as an event, solver averaged over worlds, value of the next hand for betting).

- **Blackjack in the GUI, with ONE generic presentation for every game** (owner:
  "the same code must work for Blackjack too; if not, let's discuss").
  `CircleProfile` (`joker/gui/profiles.py`) does all the work; a game only gives
  hints (seats and their zones, piles, labels, prompts) and optional hooks (game
  questions, notes, advice on your moves, final result, header text). Briscola
  moved to the circle layout too; its old hand-made layout was removed.
  Incompatibilities met and how they were solved (provisional, owner to review;
  details in `architecture/gui.md` §8):
  1. cards without a suit → picker shows ranks only, the grid has one row;
  2. a participant who never decides (the dealer) → a seat with no player;
  3. the lazily drawn hole card (DR-2) is not in any zone, but it is on the table →
     the Blackjack profile shows it face down; its odds are those of the next card;
  4. decisions that are actions, not cards (stand, hit…) → buttons, generic rule:
     an option is "play a card" only if a card is among its arguments;
  5. many copies per card (6 decks) → the grid shows "unseen of copies" and
     P(at least one) / P(next card);
  6. strategy (Goal 2) → an `advice` hook: the expected value of each of your
     moves is printed on its button, the best one marked.
- **Copy-symmetry merging moved into the core** (`Engine.canonical`) and now also
  used by live mode and by exact enumeration: worlds that differ only by which copy
  of a card is where are merged (S1.1, S1.1b). Without it, every seen card of a
  6-deck shoe multiplied the worlds by its number of copies (a Blackjack hand never
  finished); with it, < 0.1 s per step. The brute-force oracle stays unmerged; the
  test compares the two after grouping equivalent worlds.
- **Blackjack rules in the GUI:** 1 or 6 decks, S17, double any two, DAS, **split
  once** (finite-deck resplitting is not solved yet), 3:2, dealer peeks.

- **Rung 1 (Blackjack) started and solved** (owner: "let's do the first step,
  let's solve blackjack"). Report: `rungs/rung-1-blackjack.md`. Decisions taken
  while building it (all reviewable):
  - **`Game.utility(view, player)`** added to the core: what a finished hand is
    worth. Blackjack: money, in original bets. Hands are independent, so one hand
    is the whole "match" (S8.1 holds trivially).
  - **Ranks-only deck** for blackjack (A, 2…9, T with 16 tens per deck): suits and
    10/J/Q/K never matter in the rules; probabilities unchanged.
  - **Hole card:** dealt face down at the start only when the dealer must peek
    (up card A or T); otherwise drawn lazily at reveal (DR-2, exchangeable).
    Peek always on (US rules); no-hole-card rule deferred. Auto-stand on 21.
  - **Generic solver = expectimax over the player's information states**, not over
    physical states: the hidden hole card is averaged, never seen. Worlds are
    grouped by the player's observations (replay, S7.4). Exact Fractions; it is the
    oracle. Copy-symmetry merging (S1.1: interchangeable copies) and caching by
    state and by belief.
  - **Layered plan applied (strategy.md §8.2):** a fast blackjack-specific solver
    (rank counts, floats) is checked against the generic one by differential
    tests, and both against published tables.
  - **Published-table conventions adopted:** per-hand values conditional on no
    dealer blackjack; Griffin's peek-conditioned draw probabilities (we derived
    the same formula from the hidden-card model); published split values assume
    "always resplit" (`always_resplit=True` reproduces them; default is optimal).
  - **Finite-deck splits:** split once via Griffin's approximation (error ~3e-6);
    finite resplitting deferred. Infinite deck: exact with resplits.
  - **Arena skeleton** (ROADMAP "before rung 1") built: N hands through the
    engine, mean ± 95% margin, parallel over processes.
  - Git (the other "before rung 1" item) **not** done: waiting for the owner.

- **Big picture for strategy recorded** in `architecture/strategy.md` (owner:
  "write it down so we don't lose it").
- **North star:** a general system, not the strongest bot at one game. **Target:
  beat an average human player.** Judged feasible.
- **A1.1 is temporary** (owner): opponents' moves carry a lot of information.
  Removing it couples belief and strategy; the exchangeable shortcut will not
  survive weighted moves → weighted sampling needed.
- **Layered plan for generality vs performance** (owner agreed): generic Python
  reference (oracle) → generic compiled engine checked against it → accelerators
  per class of games → game-specific tuning only for selected games. Estimated
  price of generality ×2–×10, to be measured on the flagship game.
- **Learned models:** learn the move model and the situation value, not the
  belief directly; the belief stays computed exactly from the move model
  (constraints exact). Hybrid (search + exact probability + learned parts)
  preferred over a pure network. Simple statistical models before deep networks.
- **Goals reordered (proposal):** strategy → opponent-aware beliefs → fast
  engine → class accelerators (classifier) → learned models. Classifier and
  selector moved later: they need several methods to choose among.
- **Communication rule:** explain concepts in plain words, no unexplained
  acronyms.
- **Roadmap as a ladder of famous games** (`ROADMAP.md`, owner's idea): every
  rung is a game that forces one new verified technology. Proposed order:
  Blackjack → Klondike → Kuhn/Leduc poker → Briscola → Briscola reading the
  opponent → Scopone → Tressette → Hearts → Bridge card play → heads-up limit
  Hold'em. Blackjack is first because the dealer follows a fixed procedure (no
  circle), but it already needs expected value over future draws, which Goal 1
  does not provide.
- **Roadmap revised (owner):** ladder stops at Scopone; Goal 1 row removed;
  Klondike dropped (Briscola already teaches determinization). Small pokers
  replaced, on the owner's proposal, by **full 2-player Texas Hold'em with fixed
  bet sizes against a known opponent model** (proposal pending confirmation):
  2a without reading the opponent, 2b reading it with the known model — the
  first, fully checkable removal of A1.1. Equilibrium checked later on reduced
  Briscola (Kuhn poker only as a one-off test). Final ladder: Blackjack →
  Hold'em → Briscola → Briscola reading the opponent → Scopone.
- **Hold'em rung refined (owner):** 2a decides only on cards, pot and **number
  of players still in the hand** (owner's correction: it is fundamental), with
  uniform hidden hands and no bluffing; equity against all remaining players,
  pot odds, bet threshold 1/(K+1) under "everyone still in calls"; any number of
  players from the start; fixed bet sizes. 2b adds reading the bets with a known
  model.

## 2026-10-29

- **Project working rules.**
  - All project content is written in English (code, docs, comments, commits).
  - `.md` files are a *living control surface*: produced and kept updated so the
    owner has full visibility at all times.

- **Build vs reuse.** Prefer building from scratch, *unless* the specific
  mechanism is already solid and validated by many people. Rationale: control and
  avoiding inherited hidden assumptions matter more than assembly speed.

- **Core language: Python.** Rationale: direct interop with OpenSpiel/RLCard for
  test oracles, fast prototyping, easy numeric/combinatorial work.

- **Equilibrium solvers: reuse first (OpenSpiel), maybe from-scratch later.**
  Rationale: these are mathematically subtle and fail *silently*; a validated
  reference prevents silent incorrectness. Keep OpenSpiel + known game values as
  test oracles regardless. (Applies to later goals, not Goal 1.)

- **Goal 1 defined.** Model an arbitrary card game and compute probabilities based
  only on the cards — no game theory, no opponent modeling. Chosen for simplicity
  and verifiability ("cards don't lie").

- **Classifier / analyzer / solver selector: deferred.** Not needed for Goal 1
  (nothing to select without game-theory solvers).

- **Uniform-over-consistent-deals is a deliberate Goal 1 assumption**, to be
  documented explicitly, not treated as a true posterior.

- **Approach: document skeleton first, scoped to Goal 1**, then discuss game
  assumptions, then do the first Core Model abstraction.

- **A0 — probability type for Goal 1: (a) belief over hidden cards only.**
  Pure combinatorics, no assumption about how people play. Future-event
  probability (b) deferred, possibly layered on top of (a) later.

- **A2 — condition on rule-forced reveals (type 1) only, never on strategic
  preference (type 2).** Plus a **control toggle** to enable/disable rule-forced
  deductions, because real players may not respect forced rules.

- **Clarified meaning of "assumptions":** the owner means *structural modeling
  assumptions* (players, turn structure, card states/zones, observations, ...).
  These are the next topic, discussed one group at a time.

- **S1 Cards and zones (S1.1–S1.4).** Deck is a multiset; cards have free-form
  attributes; zones are generic named containers, ordered or unordered; **zones
  are atomic** (owner's proposal): mixed visibility is modeled with separate zones
  rather than per-card overrides. Knowledge from the past lives in the information
  state, not in zones.

- **S1.5 Zone counts.** Each zone has a `count_visible_to` property (default:
  everyone). In Goal 1 a hidden count makes the engine return `unsupported`.

- **S4.1 Speed is never a game factor.** Real-time / reaction-speed games are out
  of scope. Simultaneous conflicts are resolved by a fixed rule or a chance event.

- **S2 Deck and chance (complete).** Known finite composition — **project-wide,
  permanent**: collectible/trading card games are never handled. Uniform shuffle
  as a parameterized default; draws never independent; generic discrete chance
  events; mid-game reshuffles supported.

- **Added a "Permanent project-wide exclusions" section to `GOALS.md`**
  (collectible card games, speed games).

- **Correction to S1.1.** Treating duplicate copies as distinct labeled cards is
  *correct* for attribute-defined events; multiset-aware counting is only a
  deferred efficiency optimization.

- **Non-standard decks — decided (S1.2a).** Analysis: a generic card core costs
  ~nothing in model/engine/solvers; duplicates cost only efficiency; GUI cost is
  assets (generic fallback renderer + deck skins), not architecture. Decision:
  core stays generic; the **Goal 1 library** covers suited cards (ranks, face
  cards, suits) + jokers, Italian and French families. Which cards and how many
  are used is defined per game. Non-suited decks (UNO, tarot, custom) deferred.

- **S3 Players and roles (complete).** S3.1 N fixed per game; S3.2 teams as
  possibly-hidden state properties (e.g. Briscola a chiamata); S3.3 roles as
  player properties; S3.4 explicit observer (player / public / omniscient); S3.5
  chance is explicit (Nature); S3.6 hidden variables beyond cards — Goal 1
  supports card-derived roles (a) and chance-assigned roles (b); secret player
  choices (c) are `unsupported`.

- **A1 generalized.** Consistent chance-outcome combinations are weighted by their
  declared probability; player choices add no weight. Reduces to "equally likely"
  under a uniform shuffle. Fixes an inconsistency with S2.2 and S3.6(b).

- **Probability module foundation:** built over unobserved chance outcomes in
  general, not over card-to-zone assignments specifically.

- **S4 Turn structure — partial.** Decided: S4.2 (state declares current actors),
  S4.3 (simultaneous phases are atomic joint actions; the physical face-down /
  reveal procedure is not modeled — owner's correction), S4.5 (out-of-turn actions
  resolved by fixed priority).

- **A1.1 — "choices add no weight" (not "random player").** Public choices only
  contribute the facts they reveal; hidden choices are spread uniformly over
  their legal options. Faithful to "type 1 only". This Goal 1 *choice model* is a
  replaceable component — the hook for Goal 2.

- **S4.4 hidden choices supported** in Goal 1 via A1.1. **S3.6(c)** (secret role
  choice) changed from `unsupported` to supported for the same reason.
  S4 turn structure complete.

- **S5 Observation model (complete).** Information state = observation history,
  perfect recall by default ("memoryless" toggle designed, implementation
  deferred); observations generated by events + atomic zones; raw observations
  are the source of truth, constraints derived (respecting A2.1); non-leakage is
  an architectural requirement with a mandatory indistinguishability test.

- **State vs knowledge (decided, in `core-contracts.md`).** Knowledge is never
  stored in the physical state; the owner's per-card "never seen / seen before /
  visible now" idea becomes a derived view of the information state.

- **S6 Horizon (complete) — revised after owner's Scopa-to-21 scenario.**
  Hierarchical model match → hand → phases from the start; match state is part of
  the physical state and carries over; hands are independent only w.r.t. card
  information, not state or rules (e.g. Tressette "chiamarsi fuori"). Goal 1 takes
  the match state as a public input to the hand. No finiteness assumption for
  Goal 1; cycles must be detected in forward-looking goals. Discounting n/a.

- **S8.1 Objective at match level (recorded early for future goals).** The
  objective never changes mid-hand; a hand's value is its effect on the match
  outcome. "Maximize hand points" is only a labeled approximation. Goal 2's
  choice model must take the match state as input.

- **S7.1 decided:** games are written in Python using framework primitives
  (hybrid approach), not free-form code and not a declarative DSL (yet).

- **S7 decided.** (a) Owner's rule-verifiability classes — verifiable
  immediately / later / never — replace the single A2.1 toggle with a per-class
  trust policy (now **A3**; defaults: n/a / trust / do not trust; class declared
  by the game author, checked by tests; a detected violation triggers recompute,
  never a crash). (b) Primitive set reduced to M1 move card, M2 set variable,
  B1 choice point (players or Nature); observations always derived;
  reveal/declaration/public-vs-hidden choice turned out redundant. (c) Consistency
  defined by replay (S7.4): rule-forced constraints are never written by hand.
  (d) DSL deferred (S7.5).

- **`assumptions.md` consolidated.** Rewritten to remove contradictions between
  early text and later decisions (A2 "accumulate constraints" → replay; A2.1
  toggle → A3 trust policy; S1.4 dynamic zones → zones declared in advance; S5.2
  explicit observations → always derived). Added scope tags `[Project]`,
  `[Goal 1]`, `[Permanent]`.

- **Four gap items decided:** S1.1b copy labels never observable; S3.7 only
  rule-defined communication (for now); S7.6 finitely many options per choice
  point; S7.7 rules are a fixed function of the state.

- **Partial card information (owner's back-color example) — S1.6 proposed.** The
  model could not express "I see the back but not the face". Proposal: attributes
  grouped into facets (`back`, `face`, ...); zone visibility per observer becomes a
  set of facets. Back-color inferences then emerge from replay. Open: top-of-stock
  back visibility — (A) 1-card `stock_top` zone, auto-refilled (recommended) vs
  (B) per-position exception for ordered zones.

- **S1.6 decided.** Two facets by default (`back`, `face`), but facets are logical
  and their number is open per game (e.g. suit visible, rank hidden). Top of the
  stock is a separate 1-card zone `stock_top`, auto-refilled (option A).

- **Assumptions phase complete.** Next: first abstraction of the Core Model.

- **Core Model first draft written (for owner review, nothing approved yet).**
  `core-contracts.md` rewritten (game definition, state, engine API, observations,
  information state, live vs simulation mode, tests, decisions for review DR-1…8);
  `probability.md` rewritten (weighting formula, queries, result format,
  methods); worked example `examples/mini-briscola.md`. New proposed assumptions
  that emerged: S5.5 control flow is public, S5.6 an actor observes its own
  choice, S7.8 options are what the actor can distinguish. Proposed resolution of
  the A1.1 open point (DR-6): `w = π(chosen) / Σ_{o∈C} π(o)`, so a choice never
  re-weights the past.

- **Milestone 1 implemented (Goal 1 walking skeleton).** Owner asked to start
  coding. Python package `joker/` (core, probability, cards, games) + 21 tests,
  standard library only. DR-1…DR-6 implemented with the recommended defaults,
  still subject to review. Exact `Fraction` probabilities. Key results: exact
  method matches the brute-force oracle; A1.1 example gives 1/2; S7.8 gives 5/12;
  Briscola after the deal gives exactly 1/12 over C(36,3) = 7140 worlds. Small
  doc fix: `Var.level` removed (level given by `match_vars` / `hand_vars`).
  Details: `docs/IMPLEMENTATION.md`.

- **GUI style: "Split Jester" chosen** (direction C of four, from the final logo's
  palette: navy text, bright red / bright blue split like the hat band; Fraunces
  900 for display, Nunito for text). Note: the final logo image misspells the
  tagline ("inteligence") — to fix before real use.

- **Local GUI = a small local web app.** Python standard-library server bound to
  127.0.0.1 + plain HTML/CSS/JS page (no build step), talking through a JSON API,
  so it can later become a real web app by moving the server.

- **Live mode implemented (DR-8 resolved).** Generic, no game-specific input code:
  at each step the session lists the observations still possible across all
  possible worlds; one → applied automatically, several → the person picks. A
  PHYSICAL frontier (no rule trusted) lists what may happen, so rule breaking can
  still be recorded; the TRUSTED frontier gives the belief, with violation
  recompute (A3).

## 2026-10-30

- **GUI game switched to Scopone scientifico** (owner's request); Briscola kept
  as a second choice on the start screen.
- **New exact method for exchangeable games.** Scopone has ~5.5·10¹² possible
  worlds after the deal, so enumeration is impossible. Because every play and
  capture is public, unseen cards are exchangeable: one representative world +
  pinned (seen) cards gives exact hypergeometric probabilities. A game must
  declare `exchangeable = True`; verified against enumeration on a mini Scopone.
  `ExchangeableSession` gives live mode with the same API as `LiveSession`.
- **Common belief reading API** (`joker/probability/views.py`): the GUI reads
  `WorldsBelief` and `ExchangeableBelief` the same way.
- **GUI polish (owner's feedback).**
  - Header: the "JO | KER" text is replaced by the logo (hat + brain + suit marks,
    no wordmark) as a flat yellow stencil on the red/blue split. Generated from the
    final logo by `tools/make_gui_logo.py` (dev-only, needs Pillow).
  - Softer palette: warm paper background instead of pure white, muted red and
    blue, softer navy (the old colors felt too heavy).
  - Standard suit symbols ♦ ♥ ♠ ♣ instead of custom drawings; Italian suits use the
    usual equivalents (coins ♦, cups ♥, swords ♠, clubs ♣).
  - Card input: a suit menu, then a rank menu (fixed positions, impossible ones
    disabled); a third "how" menu appears only when one card can be played in
    several ways (different captures). One possible way → recorded at once.
- **Generic GUI direction (owner's brainstorm, in `architecture/gui.md`).**
  Players in a circle as avatars (blue teammates, red opponents, plus a shape
  cue); hidden cards as numbers, never as rows of backs; less detail as players
  grow, click a seat to enlarge it; **selection** as the core interaction (odds
  of one focused player at a time, default = whose turn it is).
- **Scopone moved to the circle layout** (owner: "start with Scopone"). Open
  questions answered provisionally: horns / halo; default focus = player to play,
  or the next one on your turn; focus follows the turn until you pick a player.
  API: every call carries the selected view, the server computes only that.
- **Rank 9 of the 40-card deck is the Queen, code `Q`** (was `N`, "knight").
  Owner's correction; applies to the whole project (deck, Scopone, Briscola, GUI).
