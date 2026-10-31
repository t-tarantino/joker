# JOKER — Universal Game Intelligence Framework

> **Language rule — read first:** All content in this project (code, docs,
> comments, filenames, commit messages) is written in **English**.
> Only the live conversation with the project owner may be in another language.
> This rule is repeated in every `.md` file on purpose, because it is easy to forget.

JOKER is a modular system that takes a formal description of a game and reasons
about it. The long-term vision is in [`JOKER_PROJECT_CONTEXT_V3.md`](JOKER_PROJECT_CONTEXT_V3.md)
(the research brief). That brief is the *big picture*, **not** the current plan.

## Where we are right now

Goal 1 (card probabilities) is built. We are now on **Goal 2 — strategy**, climbing
the ladder of games in [`docs/ROADMAP.md`](docs/ROADMAP.md): rung 1, Blackjack, is
solved ([report](docs/rungs/rung-1-blackjack.md)). Live status: [`docs/STATUS.md`](docs/STATUS.md).
The Goal 1 description below is kept for context.

> **Goal 1:** model an *arbitrary card game* and compute its **probabilities based
> only on the cards** — no game theory, no opponent modeling ("only the cards, not
> the people"). It is deliberately simpler and easy to verify.

Game-theory components (classifier / analyzer / solver selector / equilibrium
solvers) are **out of scope for Goal 1** and intentionally deferred.

## Running the code

Python 3.12, standard library only:

```
python -m unittest discover -s tests -t . -v
```

Play a real hand of Briscola in the local GUI and see the odds:

```
python -m joker.gui
```

What exists in code and what the tests verify: [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md).

## How to navigate the docs

| File | Purpose |
|---|---|
| [`docs/GOALS.md`](docs/GOALS.md) | The roadmap: current goal + future goals (big picture) |
| [`docs/STATUS.md`](docs/STATUS.md) | **Live control dashboard**: done / in progress / next |
| [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) | What exists in code, how to run it, test results |
| [`docs/DECISIONS_LOG.md`](docs/DECISIONS_LOG.md) | Chronological log of every decision made |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | The ladder of games (Goal 2 onward) |
| [`docs/rungs/`](docs/rungs/) | One report per rung: what was built, verification, results |
| [`docs/architecture/assumptions.md`](docs/architecture/assumptions.md) | Explicit game assumptions + falsifying examples |
| [`docs/architecture/core-contracts.md`](docs/architecture/core-contracts.md) | Core Model + Engine interfaces |
| [`docs/architecture/probability.md`](docs/architecture/probability.md) | The probability module (Goal 1 heart) |
| [`docs/architecture/examples/`](docs/architecture/examples/) | Worked examples of games written against the Core Model |

## Key decisions so far (full log in `docs/DECISIONS_LOG.md`)

- **Core language: Python.**
- **Build mostly from scratch**, reusing a mechanism only when it is already solid
  and widely validated.
- **Equilibrium solvers:** reuse (OpenSpiel) when the time comes; keep OpenSpiel +
  known game values as **test oracles** regardless. (Relevant only to later goals.)
