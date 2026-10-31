"""Strategy (levels L4/L5 of docs/architecture/strategy.md): expected values and
move choice. `expectimax` is generic; `blackjack` is a fast game-specific solver
checked against it."""

from .expectimax import SoloExpectimax
