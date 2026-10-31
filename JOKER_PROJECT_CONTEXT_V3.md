# JOKER — Universal Game Intelligence Framework

> **Status:** architectural research brief and implementation context, version 3 (2026-10-29). Not an approved architecture. Sources are linked at the bottom. **Do not equate the card-game pilot with the product architecture.**

## 1. Mission and non-goals

JOKER is a modular system that accepts a formal description of a game, identifies its mathematical and computational structure, selects compatible solution methods, estimates feasibility and resources, then computes, evaluates and explains strategies under explicit assumptions. Target initially traditional card games, but **game-model and engine interfaces must be general enough to express other discrete games**.

JOKER is *not* a single LLM, not a giant universal trained policy, not a Scopa bot, and not just a collection of hand-coded game agents. AI/LLMs may help translate natural-language rules into candidate formal definitions, classify unclear mechanics, write adapters and summarize results; **never accept an LLM's interpretation as proof that the implementation of the game or solution is correct**.

Deliverables must distinguish: (A) the formal game's semantics, (B) a correct executable engine, (C) a game-characteristics analyzer, (D) an algorithm applicability checker, (E) a budgeted solver selector, (F) verifiable outputs, (G) UI and APIs.

## 2. Scope and assumptions: explicit design decisions

### 2.1 Provisional v1 scope, NOT mathematical necessities

- Discrete decisions and finite actions per decision; finite game components when possible.
- Machine-executable game rules; ability to simulate from an authoritative state.
- Finite or bounded-horizon episodes in first implementation; detect cyclic/unbounded games rather than silently treating them as finite.
- Games may have 1 to N players, chance and hidden information. Some advanced classes can be recognized but initially unsupported by solvers.
- Information available to a solver must be precisely specified; omniscient engine state must never leak to player agents.
- Exact rules, probabilistic models and payout rules are either supplied or marked uncertain.

### 2.2 Properties NEVER assume globally

- Not always 2 players; not always competitive or zero-sum.
- Not always sequential/alternating; simultaneous actions and automatic transitions may exist.
- Not always deterministic: deals, shuffled decks, draws, dice and random events.
- Not always perfect information; knowledge may depend on public history and own observations.
- Not always a uniform prior for hidden states; chance distributions and conditional correlations matter.
- Not always perfect recall; model the distinction rather than inadvertently claiming equilibrium guarantees.
- Not always independent card draws / replacement; decks usually induce dependencies without replacement.
- Not always fixed scoring, zero-sum utilities or identical player objectives.
- Not always known opponent strategy; distinguish optimal play against an equilibrium, a model, or a population.
- Not always computationally feasible to compute exact optimum; distinguish exact, bounded and heuristic results.
- Not every game can be represented as a spatial board or a flat list of legal moves without extra state.
- A game's name or genre does NOT determine the valid solver.

### 2.3 Open questions to formalize in ADRs

What constitutes a game definition? What level of rule expressivity is supported (programmatic rules, declarative DSL, or both)? How do we guarantee reproducible simulations? Are repeated games and long-term learning part of v1? Is strategy optimality defined as max expected reward, robust worst case, Nash/exploitability, team reward, risk-sensitive reward, or something else? How do we handle imperfect recall and coalition formation? Which parts of hidden information are observable to the engine vs an agent? Do we support dynamically changing rules, trading-card-game effects, continuous stakes, auction/bidding phases, communication and partner inference? What performance/latency budget is acceptable?

Document each with **Assumption / Justification / Cases where it fails / Consequence / Test / Decision status**.

## 3. Formal mathematical foundation

Canonical model: a stochastic multi-agent extensive-form system, with state set S, players P, active-player/turn control C(s), each player's action set A_i(s), chance transitions T(s'|s,a), observations O_i(s,h) where history h may matter, initial-state distribution mu, terminal predicate, utility vector u_i(h_terminal) and game horizon/discounting when applicable. For simultaneous decisions, actions are joint actions. For information-imperfect games, observation and information-state histories should induce information sets; observation alone may be insufficient. Explicitly distinguish perfect information, imperfect information, unknown payoff rules, and uncertainty about opponents' strategies. Do not assume Markov observations.

Three separate layers: **physical hidden state** (what is actually in the deck/hands), **information state** (what an individual player can infer from history), **belief** (probability distribution over hidden states conditional on observation/history and modeling assumptions). Bayesian updates must condition on prior and all observed actions; player-action likelihoods may depend on opponent policies. A uniform sample of consistent deals is not automatically a correct posterior.

Use reproducible RNG and chance-event logs. Model exhaustive history if needed, then optimize with sufficient statistics and provable equivalence. Define invariants and reachability checks.

## 4. Architecture: independent contracts

```
Game specification (DSL / API / imported models)
    -> Validation + semantic compilation
    -> Core Model (states, rules, action, observation, utilities)
    -> Core Engine (initialise, legal actions, step, chance, replay, simulate)
    -> Analyzer (properties, complexity estimates, empirical profiles)
    -> Applicability checker (theoretical preconditions per algorithm)
    -> Solver selector (cost / budget / accuracy / certificate)
    -> Solver registry + adapters to external libraries
    -> Evaluation (exact checks, exploitability if defined, baselines, CIs)
    -> API / CLI / UI (definition, debugging, strategy explanation)
```

Do not merge the *analyzer* with the *selector*: a game can have many applicable solvers and resource constraints select between them. Do not merge model with specific backend representations. Game semantics must remain independent from the solver and UI.

### 4.1 Core Model

Interfaces/types: `GameDefinition`, `Player`, `State`, `History`, `Action`, `JointAction`, `ChanceEvent`, `Observation`, `InformationState`, `Utility`, `GamePhase`, `TurnController`, `Rule`, `OutcomeDistribution`, `Capabilities`. Card specific features belong in an **optional card-domain library**: `Deck`, `Card`, `CardSet`, `Hand`, `Zone`, `Deal`, `Draw`, `Trick`, `Capture`, `Trump`, `Contract`, `Discard`, `Reveal`. These are compositional primitives, not the canonical state type.

### 4.2 Core Engine

Core operations: `new_game(seed)`, `current_actors(state)`, `legal_actions(state, player)`, `transition(state, joint_action, chance_event?)`, `chance_outcomes(state)`, `observe(state, player)`, `information_state(history, player)`, `is_terminal(state)`, `returns(state)`, `clone/serialize/state_hash`, `replay(events)`, `sample_hidden_state(info_state, prior, opponent_model?)` with sampling metadata. For external game engines provide adapters; never leak hidden state into `observe()` or agent view. Specify deterministic transition contract given random event and logged seed.

Test: legal move completeness, conservation of cards/components, no duplication/loss, valid transitions, terminal scoring, invariance under equivalent encodings, determinism under replay, observation non-leakage, probability normalisation, performance profiles.

### 4.3 Interface design

Provide (1) a machine API, (2) a CLI for tests/simulation/benchmarks, (3) an exploratory UI to view game specs, state transitions, visible vs hidden information, legal actions, solver feasibility, algorithm choice, policy/value/exploitability/confidence, and compare candidate solvers. Consider a rule editor later, **not before semantic validation and backend contracts**. GUI should be decoupled from engines.

## 5. Game feature taxonomy, measurable instead of labels

For every candidate game, infer or request:

- Number of players, teams, coalitions, symmetric/asymmetric roles.
- Sequential / simultaneous / mixed actions; chance placement and conditional probabilities.
- Perfect vs imperfect information; private/public history; perfect recall conditions.
- Deterministic/stochastic transitions; finite/infinite/unknown horizon; cycles.
- Zero-sum, constant-sum, general-sum, cooperative or mixed utility.
- Objective: optimal response, equilibrium policy, best action from observation, robust strategy, opponent exploitation, planning vs learning.
- Branching factor, state count, info-set count, chance branching, game length; both analytic bounds and empirically estimated values.
- Hidden-information combinatorics, number of feasible determinizations, known vs inferred deck distributions.
- Availability of generative simulator vs explicit transition probabilities; differentiable/non-differentiable models; full/partial access.
- Perfect recall; observability of others' actions; binding contracts, bidding, communication; history-dependent constraints.
- Resource constraints: memory, CPU/GPU, allowed simulation count, latency, target accuracy, certificates.

Store feature values with status `proven | declared | measured | estimated | unknown`, evidence, confidence and caveats. An unchecked genre label must not trigger a solver.

## 6. Solver eligibility: theory before heuristics

Registry entries must declare theoretical requirements, computational requirements, guarantees, failure modes and supported output. Examples:

| Family | Typical applicability | Key limitations / required care |
|---|---|---|
| Backward induction / exhaustive dynamic programming | tractable finite, fully specified perfect-information trees | state-space explosion; chance expectation; utility assumptions |
| Minimax / alpha-beta | typically 2-player zero-sum deterministic perfect information | invalid as universal solution to multiplayer, hidden-information or general-sum games |
| Expectimax / expectiminimax | explicit chance probabilities, tractable tree, appropriate opponent model | opponent strategy assumptions; explosion |
| MDP planning / value iteration | fully observable controlled stochastic process | opponent dynamics cannot be ignored unless modeled |
| POMDP / belief-space planning | partially observable decision problems with modeled dynamics | opponent policies, belief approximation, high dimensionality |
| Nash / extensive-form equilibrium methods, CFR variants | specified imperfect-information multiagent games, notably 2p zero-sum with perfect recall for familiar guarantees | non-zero-sum/multiplayer guarantees differ; abstraction error; convergence not instantaneous |
| Sequence-form LP and game-theoretic solvers | small suitable extensive-form games | may require perfect recall, 2p zero-sum or specific formulations |
| MCTS / UCT | simulator, manageable sample cost | empirical, asymptotic and domain-dependent; not automatically equilibrium |
| ISMCTS / PIMC/determinization | hidden-information simulation | strategy fusion, nonlocality, inconsistent beliefs; no general optimality guarantee |
| CFR+ / MCCFR / outcome sampling | game structure and regret updates accessible | memory and convergence considerations |
| Self-play RL, deep RL, population methods | large games with simulators and training budget | no universal optimality or transfer guarantee |
| Robust/Bayesian opponent modeling | uncertain opponent policy and explicit objective | prior/model dependence; sensitivity analyses necessary |

The selector must return: chosen algorithm(s), rejected candidates with reasons, input assumptions, confidence/quality indicators, estimated cost, requested metric, termination criteria, fallback and references. For unsupported classes, respond `unsupported` rather than inventing guarantees.

Proposed pipeline: static checks -> eligibility graph -> estimated complexity -> cost-based shortlist -> trial benchmark on representative states -> actual selection/ensemble -> ongoing diagnostic checks. Algorithm meta-selection may eventually be learned, **after** collecting a cross-game empirical dataset.

## 7. Research and reuse: mandatory comparison BEFORE implementing large components

**A. Ludii** — https://ludii.games/ ; https://github.com/Ludeme/Ludii ; tutorial https://github.com/Ludeme/LudiiTutorials . General Game System with a compositional, ludeme-based Game Description Language and GUI; strong reference for reusable rules, semantic model and automated simulation. Verify API, extensibility, performance, hidden-information support and source LICENSE before adopting.

**B. Alexandre Verlaine (2025), _Introducing Card Games in Ludii_** — thesis PDF https://perso.uclouvain.be/eric.piette/master/2025%20-%20Introducing%20Card%20Games%20in%20Ludii.pdf ; publication https://research.dial.uclouvain.be/entities/publication/fa99648e-8f43-4542-b822-a7ec500174ea ; implementation fork https://github.com/ALverlaine/Ludii . **Highest-priority source for reusable card mechanics**. Thesis examines and extends language for deck, hands, deal, card operations; example implementations include simplified UNO, Bataille, The Game, 5 Alive, Briscola. Crucial caveat from Chapter 5: tests focus on deterministic perfect-information cases; sophisticated hidden-information modeling is *unfinished*, with a high-level visibility construct proposed as future work. Do not claim this fork solves all card games, epistemic logic or equilibrium selection.

**C. OpenSpiel** — https://github.com/google-deepmind/open_spiel ; https://openspiel.readthedocs.io/en/latest/intro.html ; algorithm catalogue https://openspiel.readthedocs.io/en/latest/algorithms.html . High-priority for extensive-form API, observations/information states, chance, sequential/simultaneous turns, varied utility, implementation and evaluation of CFR, exploitability etc. Compare whether to use as solver backend via adapters or rely on OpenSpiel model directly. No claim that it automatically selects best solver.

**D. TAG (Tabletop Games Framework)** — https://github.com/GAIGResearch/TabletopGames ; https://tabletopgames.ai/ . Java tabletop forward models, game components, GUI, analytics (branching, hidden information); evaluate code and benchmarks. May overlap heavily with engine, especially for modern games. Check actual game coverage and license.

**E. RLCard** — https://github.com/datamllab/rlcard ; https://rlcard.org/ . RL environment collection and benchmarks for multiple card games; useful as reference and baselines, less suited as universal declarative-rule model.

**F. GDL / GDL-II** — Stanford GDL overview https://logic.stanford.edu/ggp/overview/game_description.html ; Thielscher 2010 https://ojs.aaai.org/index.php/AAAI/article/view/7647 ; Stanford GDL-II explanation https://logic.stanford.edu/ggp/chapters/chapter_17.html . Formal language tradition; GDL-II explicitly models chance and incomplete information. Important theoretical comparison to ludemes and programmatic game definitions.

**G. Related modeling research** — _Game design patterns in digital card games: a browser engine to an abstract card game model_ https://repositum.tuwien.at/handle/20.500.12708/2993 (card-game taxonomy and abstract model). _Cardiverse_ https://danruili.github.io/Cardiverse/ (LLM-assisted card-game prototyping, separate from verified strategic solution). _Realizzazione di un gioco a informazione incompleta sulla piattaforma Ludii_ https://amslaurea.unibo.it/id/eprint/29788/ (observability case study). Additional candidate: PettingZoo https://github.com/Farama-Foundation/PettingZoo for a standardized multiagent environment API, not a full general rules compiler.

### 7.1 Due diligence for EVERY candidate

Record: core purpose; what is implemented versus described as future work; current repo state and release activity; actual license and redistribution restrictions; language, installation and dependencies; game modeling expressivity; APIs/adapters; exact/imperfect info support; chance support; dynamic rules; scaling; test quality; extensibility; integration friction; available solvers; reproducibility; GUI; and known limitations. Provide sourced evidence and hands-on toy-game tests. **Open source visibility does not automatically imply unrestricted licensing.**

### 7.2 Decision matrix (qualitative hypotheses, not benchmark claims)

| Project | Primary potential value for JOKER | Main validation risk |
|---|---|---|
| Ludii | rule DSL, core game system, large game corpus, GUI | integration/hidden info/expressivity constraints |
| Verlaine Ludii fork | reusable card-domain grammar and implementation | hidden info gaps, merge/maintenance status |
| OpenSpiel | general game API, solution algorithms, evaluation tools | declarative game-authoring not its primary strength |
| TAG | component engine, forward model, analyses, GUI | more code-driven than universal grammar |
| RLCard | card-game agents/environments, benchmarks | coverage and rule reusability |
| GDL-II | formal expressive reference for chance/observations | practical runtime/integration costs |

**Architecture options** (do not choose until a spike): (1) JOKER DSL -> Ludii backend + OpenSpiel adapter, (2) JOKER semantic IR -> multiple backends (Ludii, OpenSpiel, TAG) with common invariants, (3) OpenSpiel as canonical game API + domain-level authoring compiler, (4) narrow independent core + optional backends. Analyze semantic equivalence, not just ease of calling a library. Prefer a modular IR/adapters **as a hypothesis** where mapping fidelity is demonstrated.

## 8. Validation and cross-game benchmark suite

Testing must cover *distinct mathematical classes*: Kuhn Poker (tiny stochastic hidden-info, solved reference); Leduc Poker (larger hidden-info); simple chance/decision toy MDP; perfect-information 2-player zero-sum; multiplayer general-sum; cooperative team game; simultaneous-move matrix game; trick-taking; capturing game (Scopa); bidding/contract game; variable-hand-length and reshuffle games. These are test targets, not proof that all can be expressed today.

For each: test fidelity to rules; run exhaustive micro-state tests; measure states/second, branch factors, memory and information-set leakage; compare baseline policies; convergence and confidence; exploitability only where correctly defined; reproducibility; behavior under time limits. Vary hidden-info priors and opponent models as sensitivity tests. Record when a solver provides *no* formal guarantee.

## 9. Implementation order and acceptance gates

**Phase 0: Research and architecture.** Analyze Ludii + Verlaine thesis/fork deeply, OpenSpiel, TAG, RLCard, GDL-II and licensing. Write `docs/research/landscape.md`, `docs/architecture/assumptions.md`, `docs/architecture/adr/`, comparison matrices, dependency policy. No game-specific code yet.

**Phase 1: Semantic prototypes.** Model *at least three distinct small games* in candidate backends (perfect-info, hidden-info stochastic, multiplayer/general-sum). Define invariants, observation contract and adapter fidelity. Decide canonical semantics with evidence.

**Phase 2: Core interfaces + tests.** Implement APIs and adapters, game capability descriptors, deterministic replay and validated chance/observation semantics. Avoid premature GUI work.

**Phase 3: Analyzer + registry.** Output structured game characteristics, evidence sources, solver preconditions, complexity estimation, and machine-readable rejections.

**Phase 4: Solver integration.** First use proven existing algorithms; compare against exact tiny game solutions and run resource-limited benchmarks.

**Phase 5: Interface.** Build developer CLI and lightweight GUI to inspect game state, player view, moves, diagnostics and strategies.

**Phase 6: Broader card-game pilots.** Implement Scopa, Briscola, trick-taking, Poker/variants etc. after core contracts stabilize. Track exceptions: every game-specific hack requires architecture review.

### Acceptance criteria for beginning production implementation

- Documented assumptions and non-assumptions; each assumption has a falsifying example.
- Research matrix includes Ludii, Verlaine, OpenSpiel, TAG, RLCard and GDL-II with exact source links and license review.
- At least two alternative semantic architectures tested on three structurally different toy games.
- Model/engine interfaces clearly distinguish true state, observation, information state and belief.
- Algorithm eligibility contracts demonstrably reject invalid combinations.
- A plan for verifiable optimality or quality metrics by problem class.

## 10. Instructions for VS Code AI coding agent

1. Read this entire file before changing the project architecture. Treat all architecture choices as provisional until ADR approval.
2. Prioritize research of **Verlaine's fork and thesis**, Ludii internals, OpenSpiel abstractions and TAG over writing bespoke infrastructure.
3. Do NOT start by coding Scopa. Do NOT establish card-specific schemas as the universal internal game representation.
4. When citing a framework's capability, link source code/docs and distinguish tested support from stated goals/future work. Never infer capabilities from abstracts only.
5. First task: produce `docs/research/landscape.md` with side-by-side comparison and specific reusable modules/classes; `docs/architecture/assumptions.md`; `docs/architecture/core-contracts.md`; `docs/architecture/solver-eligibility.md`; and 2–4 competing ADRs. Do not make unreviewed architectural commitments.
6. Propose minimum experiment implementations and how to verify semantic equivalence across engines.
7. Separate rule inference from rule verification, and theoretical solver applicability from performance selection.
8. Maintain a clear `verified / tentative / proposed / unsupported` evidence label for major claims.
9. Never claim mathematically optimal actions from heuristic policies without applicable proof/certificate.

## 11. What this context does NOT establish

This document is a sourced research-oriented design brief, not a demonstration that the listed tools can be combined without friction. Neither the optimum number of solver families nor universal automatic algorithm selection has been proven. The exact licenses, current maintenance, implementation status of the Verlaine branch, and whether each game/algorithm pair compiles correctly need repo inspection and runnable experiments. The project should explicitly measure such gaps and avoid 'universal' marketing claims beyond demonstrated coverage.
