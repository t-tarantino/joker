"""Published blackjack strategies, used as references (tests, arena opponents).

- `nairn_single_deck_s17`: the single-deck basic strategy written out in
  J. A. Nairn, "Exact Calculation of Expected Values for Splitting Pairs in
  Blackjack" (arXiv:1909.13710, 2019), Appendix A, dealer stands on soft 17.
  Its Table 4 gives the exact total expected value of this strategy.
- `chart_policy`: plays any first-decision chart (e.g. one printed by
  `blackjack.basic_strategy_chart`) by hand totals, as a person would.
"""

from __future__ import annotations

from ..games.blackjack import hand_value
from .blackjack import CHART_UPS, Situation


def nairn_single_deck_s17(sit: Situation) -> str:
    """Nairn's Appendix A (S17), hitting and doubling. Splits are decided by value
    (evaluate with split_choice="best"), as in the paper."""
    total, soft = hand_value(sit.cards)
    two = sit.cards if len(sit.cards) == 2 else None
    up = sit.up
    if "double" in sit.options and _nairn_doubles(total, soft, two, up):
        return "double"
    if "hit" not in sit.options:
        return "stand"
    return "hit" if _nairn_hits(total, soft, two, len(sit.cards), up) else "stand"


def _nairn_doubles(total: int, soft: bool, two, up: str) -> bool:
    if soft:
        other = two[0] if two[1] == "A" else two[1]         # (A, x)
        return ((up == "2" and other == "6") or (up == "3" and other in "67")
                or (up in "45" and other in "234567") or (up == "6" and other in "2345678"))
    if up in "234":
        return 9 <= total <= 11
    if up in "56":
        return 8 <= total <= 11 and two != ("2", "6")       # hit (6,2) vs 5 (S17) and vs 6
    if up in "789":
        return total in (10, 11)
    return total == 11                                      # vs T and A


def _nairn_hits(total: int, soft: bool, two, n_cards: int, up: str) -> bool:
    if soft:
        if up in "2345678":
            return total <= 17
        return total <= 18 and not (up == "A" and total == 18)
    if up == "2":
        return total <= 12 or two == ("3", "T")
    if up == "3":
        return total <= 12 and two not in (("4", "8"), ("5", "7"), ("6", "6"))
    if up in "456":
        return total <= 11 or (two == ("2", "T") and up in "46")
    if up == "T" and (two == ("7", "7") or (total == 16 and n_cards >= 3)):
        return False
    return total <= 16


def chart_policy(chart: dict[str, list[str]]):
    """Play a first-decision chart by totals: pairs by the pair row when a split is
    allowed, then soft / hard rows; D = double else hit, Ds = double else stand.
    Cells marked '*' (composition dependent) use their most common code."""
    def play(sit: Situation) -> str:
        col = CHART_UPS.index(sit.up)
        total, soft = hand_value(sit.cards)
        code = None
        if "split" in sit.options:
            code = chart[f"pair {sit.cards[0]}{sit.cards[1]}"][col].rstrip("*")
            if code == "P":
                return "split"
        others = [c for c in sit.cards if c != "A"]
        if soft and len(sit.cards) == 2 and len(others) == 1 and others[0] != "T":
            code = chart[f"soft A{others[0]}"][col].rstrip("*")
        elif sit.cards == ("A", "A"):
            code = "H"
        elif soft:
            code = "S" if total >= 19 or (total == 18 and up_stands_soft18(chart, col)) else "H"
        elif code is None or code == "P":
            code = "H" if total <= 4 else "S" if total >= 20 else chart[f"hard {max(total, 5)}"][col].rstrip("*")
        if code.startswith("D"):
            if "double" in sit.options:
                return "double"
            code = "S" if code == "Ds" else "H"
        if code == "H" and "hit" in sit.options:
            return "hit"
        return "stand"
    return play


def up_stands_soft18(chart: dict[str, list[str]], col: int) -> bool:
    """Multi-card soft 18: stand where the chart stands (or doubles-else-stands) on A7."""
    return chart["soft A7"][col] in ("S", "Ds")
