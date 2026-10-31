# JOKER — Strategy: the Big Picture

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

How JOKER goes from "probabilities on the cards" (Goal 1) to **playing well**.
This page records the big-picture discussion of 2026-10-30/31 so it is not lost.
It is a direction agreed with the owner, not a frozen design: the open decisions
are listed in §12.

Writing rule for this page: every technical term is explained the first time it
appears; acronyms are avoided or spelled out (glossary in §13).

---

## 1. North star

- **A general system**, able to play many card games with little code per game.
  Not one bot per game, and not "the strongest program in the world" at any game.
- **Target strength: beat an average human player.** Measured as a win rate over
  many hands, with its margin of error (§9.1).
- **Objective inside a game: maximize the probability of winning the match**
  (assumption S8.1), not the points of the current hand. "Most points this hand"
  is only a labeled approximation.

**Is the target realistic?** Yes, with good margin. Reasons:
- An average human forgets cards and miscounts; JOKER counts exactly.
- In trick-taking games, programs built on the "sample possible worlds, solve
  each one" idea (§6, Category 4) have reached strong amateur to expert level
  (bridge card play, Skat).
- Caveat: in team games a bot partnered with a human must understand the human
  partner's conventions (signals, habits). Playing *against* humans is easier
  than playing *with* them.

---

## 2. Basic concepts

- **State:** the full snapshot of a moment (where every card is, whose turn,
  scores). What an all-seeing referee would see.
- **Move:** a legal choice of a player.
- **Chance:** what nobody chooses (shuffle, draws). Modeled as an extra player,
  "Nature", choosing with known probabilities.
- **Game tree:** from the start, every possible move branches out, then every
  answer, down to every possible end. A played hand is one path in the tree.
- **Hidden information:** a player does not see the true state, only part of it.
  Several true states are then **indistinguishable** to them. That set of
  indistinguishable states is an **information set**. In card games you never
  decide "in state X", you decide "in one of the situations that could be true,
  given what I know".
- **Possible world:** one true state consistent with what you have seen.
- **Belief:** a probability for each possible world. Card questions ("chance the
  opponent holds the trump ace") are read from it.
- **Strategy (policy):** a rule saying what to do in every situation. *Pure*:
  always the same move; *mixed*: moves chosen with probabilities (e.g. 70% / 30%).
  Mixed strategies are essential with hidden information: a predictable player
  can be exploited.
- **Expected value:** the average of the possible results, each weighted by its
  probability. Win 10 points with 30% chance, else 0 → expected value 3 points.

---

## 3. The tool hierarchy

Each level uses the ones below it.

```
 L6  ADAPTATION to the real opponent      "this person bluffs too much"    [future]
 L5  MOVE CHOICE (strategy)               "which card do I play?"          [one-player games: rung 1]
 L4  EXPECTED VALUE                       "how much is playing the 7 worth?" [one-player games: rung 1]
 L3  MODEL OF OTHER PLAYERS' CHOICES      "how does the opponent play?"    [only 'uniform']
 L2  BELIEF / CARD PROBABILITIES          "P(holds the ace) = 1/12"        [DONE, Goal 1]
 L1  COUNTING THE POSSIBLE WORLDS         "7140 consistent worlds"         [DONE, Goal 1]
 L0  RULES / ENGINE                       "what is legal, what happens"    [DONE]
```

- **L0 Rules.** Given a state and a move, says what happens. The engine.
- **L1 Counting worlds.** Lists (enumeration) or counts with formulas
  (combinatorics) the worlds consistent with what was seen. Done, two methods.
- **L2 Belief.** Gives each world a weight and derives card probabilities. Done,
  **but under assumption A1.1** (other players' choices add no information).
- **L3 Choice model.** For a player's situation, the probability of each of
  their moves. Today: "uniform". The hook already exists: the weighting formula
  of decision DR-6 contains the probability of the observed choice.
- **L4 Expected value.** How much a move is worth on average, over all possible
  worlds and the whole future of the match. Needs L2 (weights of the worlds) and
  a forecast of future moves (L3 and L5).
- **L5 Move choice.** Pick the move with the best expected value. All the
  difficulty is inside L4.
- **L6 Adaptation.** Learn how *this* person plays and exploit their weaknesses.

---

## 4. A1.1 is temporary — and removing it couples L2 with L5

A1.1 was a **Goal 1 simplification only**. Other players' moves carry a lot of
information (an opponent who could have taken 10 points and did not, probably
could not), so A1.1 must go.

Consequence: **a correct belief cannot be computed "first" and on its own.** To
learn something from an opponent's move, we must know how they would have played
with each possible hand, i.e. we need a model of their play (L3). A good model
of their play is a strategy (L5). Removing A1.1 means **belief and strategy must
be computed together** (§5).

Practical path:
1. Build L4/L5 with the current belief, only to *have* a strategy.
2. Plug that strategy into L3: the belief now "reads" the opponents' moves.
3. Recompute the strategy with the better belief; repeat.

Technical consequence: the exact combinatorial method for exchangeable games
(Scopone, `joker/probability/exchangeable.py`) works only because today all
consistent worlds weigh the same. When moves carry weight, worlds are no longer
equivalent and that shortcut breaks. We will need **weighted sampling**: draw
possible worlds, give each a weight = how plausible the observed moves are in
that world, and average. (This is the "Monte Carlo" item that was already in the
backlog, now with a precise reason.)

The hard constraints never become approximate: a world that contradicts what was
seen still has weight exactly zero.

---

## 5. The vicious circle, and how it closes

The circle:
1. To compute L4 (what my move is worth) I must forecast the others' moves (L3).
2. If they play well, they choose by computing *their* L4, which depends on what
   they forecast I will do (my L5).
3. And L2 depends on L3 (what their moves reveal depends on how they play).

**It is not broken; we look for the point where it is consistent with itself.**
Rock-paper-scissors: if you always play rock I play paper; then you switch to
scissors, I switch to rock... round and round. But "one third each, at random"
stops the loop: against it nobody can do better by changing. A situation where
**nobody has a reason to change their strategy** is an **equilibrium** (Nash
equilibrium): my strategy is the best answer to yours, yours to mine, and the
beliefs are computed with exactly those strategies.

**"Converging to the equilibrium"**: going round the circle many times, each
round a bit closer. On rock-paper-scissors: assume the opponent always plays
rock → best answer paper → they answer scissors → ... Look not at the last
answer but at the **average frequency** of all answers so far: it approaches
1/3, 1/3, 1/3.

**Measuring the distance from equilibrium — exploitability:** imagine a perfect
opponent who knows your strategy and plays the best answer to it. How much do
they beat you on average? 0 at equilibrium; maximal for "always rock". This is
the yardstick that says whether an algorithm works.

**Why equilibrium is valuable:** in games with **two sides** (§7), the
equilibrium strategy guarantees a minimum average result *whatever the opponent
does*. It does not exploit a weak opponent's mistakes; that is L6.

**Four practical options, from crude to serious:**
1. **Ignore the circle:** assume opponents choose at random (Goal 1 today).
2. **Fix a simple model:** assume a fixed rule ("always takes when there are
   points"). The circle stops because their play no longer depends on mine.
3. **A few rounds by hand ("levels"):** level 0 random; level 1 best answer to
   level 0; level 2 best answer to level 1; stop when it stops improving.
4. **True equilibrium:** iterate until convergence, with algorithms that
   guarantee getting there.

---

## 6. Classifying games, and which method for which class

### 6.1 Five questions

- **A. What is hidden?**
  A1 nothing hidden, no chance (rare in cards) ·
  A2 chance but nothing hidden from anyone ·
  A3 hidden information (almost every real card game).
  In A1/A2 there is **no circle**: reason backward from the end (the last move
  is obvious, so the second-to-last can be decided, and so on). In A3 there is.
- **B. Who plays against whom?**
  B1 solitaire (you vs the deck: **no circle**, the deck does not think) ·
  B2 two players, one side's gain is the other's loss ·
  B3 two teams (teammates do not see each other's cards and cannot talk) ·
  B4 three or more independent sides.
- **C. How big is it?** See §6.2.
- **D. Do the others' moves reveal much?** If little, a uniform choice model is
  almost exact; if a lot, the circle weighs more.
- **E. Single hand or match?** Same computation, different objective (S8.1).

### 6.2 What "small" means

There is no "small" in absolute terms: **a game is small *for a method* if that
method can visit everything it needs to visit in reasonable time.** Two sizes
matter, and they are very different:

- **C1 — number of possible worlds:** what L1/L2 (belief) must handle.
  Briscola after the deal: 7,140. Scopone after the deal: ~5.5·10¹².
- **C2 — size of the game tree / number of information sets:** what L4/L5
  (strategy) must handle. Almost always **vastly larger** than C1, because it
  includes every sequence of future moves.

Reference points for C2:

| Game | Information sets | Exact equilibrium? |
|---|---|---|
| Kuhn poker (toy poker, 3 cards) | 12 | yes, instantly |
| Leduc poker (toy poker, 6 cards) | ~900 | yes, seconds |
| Two-player limit hold'em poker | ~10¹⁴ | solved in 2015 with thousands of processors for ~2 months |
| Briscola, Scopone, Tressette (full games) | far beyond | **no** — approximate methods needed |

Rule of thumb (to be measured): our Python engine handles a few thousand worlds
per second (Briscola: 7,140 worlds in ~1.7 s). A compiled engine would be ×100 to
×10,000 faster.

### 6.3 Categories and methods

**Category 1 — nothing hidden, no chance, two players (A1+B2).**
- Small: **full backward search** ("minimax"): at my nodes take the maximum, at
  the opponent's the minimum (they want the opposite). Exact.
- Large: look ahead a few moves, then estimate the position (by a formula or by
  simulations).

**Category 2 — chance but nothing hidden, or solitaire (A2, or B1).**
- Small: as above, but at chance nodes take the probability-weighted average
  ("expectimax"). No circle.
- Large: **Monte Carlo** = simulate many random cases and average, instead of
  computing them all. More simulations, more precision, with a computable margin
  of error.
- 👉 **Solitaires with a face-down deck are a natural first step**: they use the
  Goal 1 belief and add only expected value, with no opponent and no circle.

**Category 3 — hidden information, two sides, small (A3+B2/B3, small).**
- **Exact equilibrium** by iteration. The standard algorithm is
  **counterfactual regret minimization**: the bot plays itself many times; after
  each game, in every situation, it asks "how much more would I have won by
  always playing that other move?" (its **regret**) and next time plays more
  often the moves it regrets most. The *average* of its strategies provably
  converges to equilibrium.
- Exact, verifiable, measurable with exploitability. **The test bench**: toy
  games with known solutions (Kuhn, Leduc, reduced versions of our games).

**Category 4 — hidden information, two players, large (Briscola).** Four
families of approximation:
1. **Determinization** ("perfect-information Monte Carlo"): sample e.g. 100
   possible worlds from the belief; in each, pretend all cards are face up and
   solve by backward search; play the move that is best on average. **The direct
   next step after Goal 1** (the belief becomes the world generator). Known
   flaws: in each world the bot "knows" the cards, so it assumes it will always
   guess right later (it overrates itself); it cannot hide information or play a
   move just to discover something (no bluffing, no probing).
2. **Tree search over information sets** ("information-set Monte Carlo tree
   search"): a tree whose nodes are "what I know", not single worlds; the most
   promising moves are explored and evaluated by simulating the rest of the
   game. Partly fixes flaw 1.
3. **Equilibrium with abstraction:** group similar situations ("I hold a high
   trump", without saying which) until the game is small enough for Category 3,
   then use that solution in the real game. As good as the grouping.
4. **Learning with neural networks:** the bot plays copies of itself millions of
   times and a network learns how good a situation is. State of the art on big
   games; costly, slow to train, hard to explain.

**Category 5 — teams (B3: Scopone, Tressette).** Same menu as Category 4;
determinization and learning adapt well; exact team equilibrium is much harder
(teammates must coordinate without talking).

**Category 6 — three or more independent sides (B4).** Same techniques, no
guarantees, much more weight on opponent models (L3, L6).

---

## 7. "Zero-sum": what it means and why it matters

"Zero-sum" does not mean points cancel out: it means **what one side gains, the
other loses**. If the objective is winning the match and there is one winning
side and one losing side, the game is zero-sum **even with teams**. Briscola
points always total 120: each point of mine is one taken from you.

- **Zero-sum (two sides):** two-player Briscola and Scopa, Scopone, Tressette in
  pairs, four-player Briscola in pairs, Bridge, Burraco in pairs — most Italian
  classics.
- **Not zero-sum:** three or more independent sides (multi-way poker, Hearts,
  four-player Uno). In between: *Briscola a chiamata* (teams change every hand
  and are hidden).

It matters because **the equilibrium guarantees hold only with two sides.** The
real difficulties are teams (coordination without communication) and three or
more sides (no "safe" strategy exists).

---

## 8. Generality vs performance

### 8.1 Where a specialized program gains

Specialization does not make an exact computation *more exact*: exact is exact.
It changes *which* games can be solved exactly in the time available, and how
good an approximation is for a given time. Sources of gain (orders of
magnitude, **estimates to be measured**, §8.4):

| Source | Typical gain | Needs per-game code? |
|---|---|---|
| **A. Language and data representation** (Python objects today; compiled code, cards as bits of an integer tomorrow) | ×100 – ×1000 | **No** — a well-written generic engine gets most of it |
| **B. Hand-tuning on one game** (rule shortcuts, memory layout) | ×2 – ×10 over a fast generic engine | Yes |
| **C. Structural properties** (interchangeable suits, cards that became equivalent, exchangeability as in Scopone) | ×10 up to "impossible → exact" | **No** — they belong to *families* of games |
| **D. Game knowledge** (expert heuristics and evaluations) | large, on quality for a given time | Yes — or **learned** (generic algorithm, per-game training) |

Conclusions:
- The biggest jump (A) does not depend on specialization: today's slowness comes
  from Python and from an engine written for correctness.
- C is "general but fast", and we already did it once (the exchangeable method is
  code for "games whose unseen cards are interchangeable", not code for Scopone).
  This is the concrete role of the **classifier** of the original brief:
  recognize a game's properties and switch on the fast methods they allow.
- Estimated price of a well-built generic architecture: **×2 – ×10** against a
  program hand-written for one game.

### 8.2 The layered plan

1. **Generic reference solver in Python.** Simple, readable, exact `Fraction`s.
   Slow is fine. It is the **oracle** for everything else.
2. **Generic fast solver in a compiled language** (C, C++ or Rust — to choose),
   checked against the Python oracle.
3. **Accelerators per class of games**, switched on by declared or detected
   properties (exchangeability, suit symmetry, equivalent cards...), each checked
   against the oracle.
4. **Game-specific tuning** (strategies, heuristics, speed tricks) only for the
   games we care most about. Allowed, never required.

### 8.3 How we gain confidence that the reference is right

Absolute certainty does not exist; we stack independent evidence:
- **Brute-force oracles** on tiny cases (done in Goal 1).
- **Two different methods agree** (enumeration vs combinatorics: done for the
  exchangeable method).
- **Known published values** (Kuhn poker: first player's value is −1/18) and an
  external, widely validated library (OpenSpiel) as a second oracle.
- **Invariants:** probabilities sum to 1, cards are conserved, swapping two
  equivalent suits gives the same results, a best answer cannot improve an
  equilibrium, exploitability goes to 0.
- **Rules are the biggest risk**, more than the algorithms: rule tests written
  from the rulebook's examples, owner review, real hands played in the GUI.
- **Simplicity over speed** in the reference code; exact fractions, no rounding.

The fast version is then checked by **differential testing**: generate many
random positions, ask both versions, require identical answers.

### 8.4 Measure the price of generality

At some point we write by hand a specialized version of the flagship game and
compare it with the generic one. That turns the estimates of §8.1 into a real
number.

---

## 9. Evaluation and learning

### 9.1 Arena and reference bots

- **Arena:** a program that makes two bots play thousands of hands and reports
  the win rate with its margin of error. Needed because over a few hands luck
  hides who is actually better.
- **Baseline:** a deliberately simple bot. A "smart" method that does not clearly
  beat it is useless.
- **Greedy bot:** picks the move that pays most *right now*, without looking
  ahead.
- **Sparring partners:** the reference bots (random, greedy, rule-based, later a
  "human-like" model) that our methods play against to measure their strength.
- **Human-like model:** a model of how an *average human* plays (§9.3). Since the
  target is the average human, this is the most relevant opponent to measure
  against.

### 9.2 Where to use neural networks (or other learned models)

Question discussed: train a network on beliefs only, since "with the belief,
everything else is probability and combinatorics"?

**Not quite.** The belief says *where the cards are now*. Choosing a move needs
L4: the value of a move over the **whole future**, i.e. everyone's future play.
That forward look is the expensive part, not the belief. (Today the belief is
cheap: Briscola ~2 s in Python, milliseconds compiled; Scopone exact and
instant. It becomes expensive only once A1.1 is removed, because it then
contains the opponent model.)

The links worth approximating with a learned model:
1. **The move model (L3): "given what this player knows, how likely is each
   move?"** It is the right thing to learn instead of the belief, because the
   belief is then computed **exactly from it**: weight every possible world by
   how likely the observed moves are in that world (Bayes' rule). Constraints stay
   exact ("cards don't lie": an impossible world keeps weight zero), while only
   the human/strategic part is learned. The same model also serves as a sparring
   partner and as the fast policy for simulating the rest of a game.
2. **The value of a situation (L4): "how likely am I to win from here?"** It
   lets the search stop after a few moves instead of simulating to the end.
   This is where the big time savings come from.
3. A network that predicts the belief directly is useful at most as a **fast
   proposal**: it suggests worlds to sample, and the exact weights correct it.
   Never as the final answer.

**Hybrid beats pure network** for our goals: search + exact probabilities +
learned models is stronger for a given computing budget (the AlphaZero family
and the poker programs all combine search with learned values), keeps the hard
constraints exact, and stays explainable.

**Game-specific?** The trained weights are per game; the code can stay generic if
the input is described generically (cards by facets, zones, public history).
Transfer between similar games (same deck, similar rules) is possible in
principle but is research, not a promise.

### 9.3 Where the move model comes from

- **Expert rules:** cheap and immediate, but game-specific. A middle way: a small
  library of **generic** heuristics expressed in generic terms ("plays the lowest
  card that wins the trick", "keeps high trumps"), tuned per game by parameters.
- **Statistics over many recorded games:**
  - **human games:** model the real average human, which is exactly our target.
    Needs data (source to find);
  - **self-play games:** unlimited data, but they model the bot, not humans.
- **Simple statistical models before deep networks.** A deep network is also a
  statistical model, not inherently less precise; the real differences are data
  needed and interpretability. Progression:
  1. generic features ("can win the trick", "points on the table", "rank
     relative to the cards still out") + a simple weighted model (e.g. logistic
     regression: one weight per feature, readable);
  2. a neural network only if it predicts clearly better.
- **The test for any move model:** how well it predicts the moves actually played
  in games **not used to build it**.

Expert research on Skat (University of Alberta) used exactly this scheme — a
model of human play learned from game records, used to weight the sampled worlds
in determinization — and it improved playing strength.

---

## 10. Optimization: when

Correct and slow first; then measure where time goes; then a fast version
checked against the slow one (the same oracle → fast method pattern as Goal 1).
Known in advance: determinization, search and equilibrium need millions of
simulations, so the Python engine will become the bottleneck early. It stays the
reference; the compiled engine (§8.2 step 2) comes when the measurements say so.

---

## 11. Proposed roadmap

**Superseded in detail by [`../ROADMAP.md`](../ROADMAP.md)** (2026-10-31): a ladder
of famous games, each forcing one new verified technology. The steps below are
the same ideas in their original order.

Principle: **generality in the architecture, focus in practice** — one
**flagship game** to measure everything on and reach "beats an average human",
plus one **control game**, very different, where every addition must also work
(otherwise it was not generic).

1. **Arena + reference bots** (random, greedy, rule-based).
2. **L4/L5 on small games with known answers:** a face-down solitaire (expected
   value, no circle); toy two-player games with known equilibria (Kuhn, Leduc,
   reduced versions of our games), checked against published values / OpenSpiel.
3. **Determinization on the flagship game** with the current belief.
4. **Remove A1.1:** opponent move model in the belief, weighted sampling; iterate
   strategy ↔ belief (levels, §5).
5. **Compiled generic engine**, checked against the Python oracle by
   differential testing — when measurements require it.
6. **Accelerators per class of games** (the classifier's real job).
7. **Learned models:** move model (from human or self-play games) and situation
   value.
8. **Game-specific tuning** for the games we care most about.

---

## 12. Open decisions

1. Flagship game (proposal: two-player Briscola, then Scopone) and control game.
2. Solitaire as the very first step of L4/L5: yes or no.
3. Source of recorded human games (online platforms? our own GUI?).
4. Compiled language for the fast engine (C, C++, Rust) — not urgent.
5. Whether to formally close Goal 1 now (its "done when" criterion is met) or
   after the Tressette / constrained-counting work.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| **A1.1, S8.1, S5.5…** | numbered assumptions in [`assumptions.md`](assumptions.md) |
| **DR-1…DR-8** | "decisions for review" in [`core-contracts.md`](core-contracts.md) §10 |
| **Minimax** | backward search: I take the maximum, the opponent the minimum |
| **Expectimax** | minimax plus probability-weighted averages at chance nodes |
| **Monte Carlo** | estimating by simulating many random cases instead of computing all |
| **Monte Carlo tree search (MCTS)** | tree search that decides where to look deeper based on random simulations |
| **Information-set MCTS (ISMCTS)** | the same, with nodes = "what I know" instead of single worlds |
| **Determinization / Perfect-Information Monte Carlo (PIMC)** | sample worlds, solve each with all cards face up, average |
| **Counterfactual regret minimization (CFR)** | iterative algorithm converging to equilibrium by reducing regret |
| **Nash equilibrium** | strategies where nobody has a reason to change theirs |
| **Exploitability** | how much a perfect opponent who knows your strategy beats you on average; 0 = equilibrium |
| **Team-maxmin equilibrium** | the version of equilibrium for teams |
| **Reinforcement learning (RL)** | learning by playing and receiving rewards / penalties |
| **Self-play** | the bot plays copies of itself |
| **Rollout** | simulating the rest of a game with a fast strategy to estimate a situation |
| **Oracle** | a slow computation that is certainly right, used to check fast ones |
| **Differential testing** | asking two implementations the same many questions and requiring equal answers |
| **Logistic regression** | a simple statistical model: one readable weight per feature |
| **Kuhn / Leduc poker** | toy pokers with exact known solutions, used in research |
| **OpenSpiel** | public, widely validated library of games and algorithms (Google DeepMind) |
| **AlphaZero, Student of Games, ReBeL** | research programs combining search with neural networks |
| **DouZero, Suphx** | neural-network programs for Dou Dizhu (a Chinese card game) and Mahjong |
