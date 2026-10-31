"""Blackjack (ROADMAP rung 1): rules, exact values against published tables, the
generic solver against the fast one, and the arena against exact values.

References (numbers copied from the sources):
- [W-inf] Wizard of Odds, "Blackjack expected return, infinite deck":
  https://wizardofodds.com/games/blackjack/expected-return-infinite-deck/
  infinite deck, S17, DAS, split to 4 hands except aces, one card on split aces;
  values conditional on no dealer blackjack; overall -0.511734%.
- [W-1d] Wizard of Odds, appendix 9, one deck, S17 (composition dependent):
  https://wizardofodds.com/games/blackjack/appendix/9/1ds17r4/
- [N] J. A. Nairn, "Exact Calculation of Expected Values for Splitting Pairs in
  Blackjack", arXiv:1909.13710 (2019), Tables 1-2 first rows (no resplitting).
"""

import os
import random
import unittest
from fractions import Fraction

from joker.arena import play_solo
from joker.core import Engine, StepKind, option
from joker.games.blackjack import RANKS, Blackjack, BlackjackRules, situation_of
from joker.strategy import SoloExpectimax
from joker.strategy.blackjack import (BlackjackSolver, basic_strategy_chart, engine_policy,
                                      solver_policy)
from joker.strategy.blackjack_reference import chart_policy, nairn_single_deck_s17

UPS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "A")
INFINITE = BlackjackRules(decks=None, hit_soft_17=False, double_after_split=True, max_hands=4)


def row(values: str) -> list[float]:
    return [float(v) for v in values.split()]


# --- rules through the engine ---------------------------------------------------------------

def deal(engine, ranks, actions=()):
    """Drive a hand: draws take the given ranks in order, choices the given actions.
    Returns the final state (or the state where the script runs out)."""
    s = engine.new_hand()
    ranks, actions = list(ranks), list(actions)
    while True:
        step = engine.next_step(s)
        if step.kind is StepKind.END:
            return s
        if step.kind is StepKind.AUTO:
            outcome = None
        elif step.kind is StepKind.NATURE:
            if not ranks:
                return s
            rank = ranks.pop(0)
            outcome = next(cid for cid, _ in step.outcomes if engine.cards[cid].face["rank"] == rank)
        else:
            if not actions:
                return s
            outcome = {0: option(actions.pop(0))}
        s, _ = engine.apply(s, outcome)


class BlackjackRulesTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Blackjack(BlackjackRules(decks=1, max_hands=4)))

    def net(self, s):
        return self.engine.view(s).net

    def test_random_hands_conserve_cards(self):
        for seed in range(300):
            trace = self.engine.play(random.Random(seed))
            for s in trace.states:
                self.engine.check_invariants(s)

    def test_dealer_blackjack_ends_the_hand_before_any_choice(self):
        s = deal(self.engine, ["9", "A", "8", "T"])           # player 9, up A, player 8, hole T
        self.assertEqual(self.engine.next_step(s).kind, StepKind.END)
        self.assertEqual(self.net(s), -1)

    def test_blackjack_pays_three_to_two_and_pushes_with_dealer(self):
        self.assertEqual(self.net(deal(self.engine, ["A", "9", "T"])), Fraction(3, 2))
        self.assertEqual(self.net(deal(self.engine, ["A", "T", "T", "A"])), 0)

    def test_hole_card_is_hidden_and_peek_is_public(self):
        s = deal(self.engine, ["9", "T", "8", "5"])           # up T, hole 5: no blackjack
        self.assertEqual(self.engine.next_step(s).kind, StepKind.CHOICE)
        self.assertEqual(situation_of(self.engine.view(s)), (("8", "9"), "T", 1, False))

    def test_split_double_and_settle(self):
        # 8,8 vs 6: split; hand 0 gets 3 -> double, gets T (21); hand 1 gets T (18) stand;
        # dealer 6 + hole T + 7 = 23 bust. Result: +2 +1.
        s = deal(self.engine, ["8", "6", "8", "3", "T", "T", "T", "7"], ["split", "double", "stand"])
        self.assertEqual(self.engine.next_step(s).kind, StepKind.END)
        self.assertEqual(self.engine.view(s).bets[:2], (2, 1))
        self.assertEqual(self.net(s), 3)

    def test_split_aces_get_one_card(self):
        s = deal(self.engine, ["A", "7", "A", "5", "9"], ["split"])   # A+5, then A+9 at its turn
        self.assertEqual(self.engine.next_step(s).kind, StepKind.NATURE)   # dealer's hole card
        v = self.engine.view(s)
        self.assertEqual((v.n_hands, v.split_aces), (2, True))

    def test_twenty_one_after_split_is_not_a_blackjack(self):
        # T,T vs 7: split; T + A = 21 (pays 1), T + 9 stand; dealer 7 + T = 17
        s = deal(self.engine, ["T", "7", "T", "A", "9", "T"], ["split", "stand"])
        self.assertEqual(self.net(s), 2)


# --- infinite deck: [W-inf] --------------------------------------------------------------------

class InfiniteDeckTest(unittest.TestCase):
    """Every value must agree with the published table to the printed 6 decimals."""

    @classmethod
    def setUpClass(cls):
        cls.solver = BlackjackSolver(INFINITE)
        cls.always = BlackjackSolver(INFINITE, always_resplit=True)

    def check(self, solver, hand, action, published):
        for up, expected in zip(UPS, row(published)):
            with self.subTest(hand=hand, action=action, up=up):
                self.assertAlmostEqual(solver.action_values(hand[0], hand[1], up)[action], expected, delta=6e-7)

    def test_stand(self):
        self.check(self.solver, "T6", "stand", "-0.292784 -0.252250 -0.211063 -0.167193 -0.153699 -0.475375 -0.510518 -0.543150 -0.540430 -0.666951")
        self.check(self.solver, "T7", "stand", "-0.152975 -0.117216 -0.080573 -0.044941 0.011739 -0.106809 -0.381951 -0.423154 -0.419721 -0.478033")
        self.check(self.solver, "T8", "stand", "0.121742 0.148300 0.175854 0.199561 0.283444 0.399554 0.105951 -0.183163 -0.178301 -0.100199")
        self.check(self.solver, "T9", "stand", "0.386305 0.404363 0.423179 0.439512 0.495977 0.615976 0.593854 0.287597 0.063118 0.277636")
        self.check(self.solver, "TT", "stand", "0.639987 0.650272 0.661050 0.670360 0.703959 0.773227 0.791815 0.758357 0.554538 0.655470")

    def test_hit(self):
        self.check(self.solver, "T6", "hit", "-0.470995 -0.463768 -0.456286 -0.449520 -0.430927 -0.414779 -0.458440 -0.509322 -0.539826 -0.517149")
        self.check(self.solver, "T2", "hit", "-0.253390 -0.233691 -0.213537 -0.193271 -0.170526 -0.212848 -0.271575 -0.340013 -0.381043 -0.350540")
        self.check(self.solver, "92", "hit", "0.238351 0.260325 0.283020 0.307350 0.333690 0.292147 0.229982 0.158257 0.119482 0.143001")
        self.check(self.solver, "54", "hit", "0.074446 0.101265 0.128981 0.158032 0.196019 0.171868 0.098376 -0.052178 -0.152953 -0.065681")
        self.check(self.solver, "22", "hit", "-0.114913 -0.082613 -0.049367 -0.012380 0.011130 -0.088279 -0.159334 -0.240666 -0.289198 -0.253077")
        self.check(self.solver, "A2", "hit", "0.046636 0.074119 0.102477 0.133363 0.161693 0.122386 0.054057 -0.037695 -0.104851 -0.057308")
        self.check(self.solver, "A4", "hit", "-0.000121 0.029160 0.059285 0.091960 0.118246 0.037028 -0.027055 -0.112189 -0.173704 -0.130027")
        self.check(self.solver, "A7", "hit", "0.062905 0.090248 0.118502 0.147613 0.190753 0.170676 0.039677 -0.100744 -0.143808 -0.092935")

    def test_double(self):
        self.check(self.solver, "92", "double", "0.470641 0.517795 0.566041 0.614699 0.667380 0.462889 0.350693 0.227783 0.179689 0.109061")
        self.check(self.solver, "73", "double", "0.358939 0.409321 0.460940 0.512517 0.575590 0.392412 0.286636 0.144328 -0.008659 -0.014042")
        self.check(self.solver, "54", "double", "0.061119 0.120816 0.181949 0.243057 0.317055 0.104250 -0.026442 -0.300996 -0.466707 -0.432911")
        self.check(self.solver, "A2", "double", "-0.071570 -0.007228 0.058427 0.125954 0.179748 -0.183866 -0.314441 -0.456367 -0.514028 -0.624391")
        self.check(self.solver, "A7", "double", "0.119750 0.177641 0.237004 0.295225 0.381506 0.219948 -0.029917 -0.290219 -0.346892 -0.362813")

    def test_split_with_resplits(self):
        # Published split values resplit whenever allowed; where splitting is right
        # they equal the optimal values.
        self.check(self.always, "AA", "split", "0.470641 0.517795 0.566041 0.614699 0.667380 0.462889 0.350693 0.227783 0.179689 0.109061")
        self.check(self.always, "88", "split", "0.073852 0.146187 0.220849 0.297475 0.409329 0.321042 -0.022736 -0.387228 -0.480686 -0.372535")
        self.check(self.always, "99", "split", "0.195625 0.258548 0.323474 0.391987 0.471339 0.364837 0.234447 -0.078010 -0.317336 -0.136810")
        self.check(self.always, "77", "split", "-0.131478 -0.043733 0.049255 0.146678 0.247385 -0.050148 -0.391981 -0.577584 -0.657268 -0.651641")
        self.check(self.always, "66", "split", "-0.212560 -0.119715 -0.021320 0.080912 0.153668 -0.264427 -0.425122 -0.610576 -0.716103 -0.653362")
        self.check(self.always, "44", "split", "-0.192325 -0.108712 -0.020395 0.081913 0.151377 -0.166452 -0.326068 -0.511152 -0.625044 -0.560206")
        self.check(self.always, "33", "split", "-0.137710 -0.056273 0.029932 0.126284 0.201318 -0.053043 -0.231843 -0.436607 -0.553507 -0.482405")
        self.check(self.always, "22", "split", "-0.084336 -0.015650 0.059088 0.151665 0.226890 0.006743 -0.176693 -0.386883 -0.507175 -0.433570")

    def test_house_edge(self):
        self.assertAlmostEqual(self.solver.round_value() * 100, -0.511734, delta=6e-7)

    def test_basic_strategy_chart(self):
        # The usual multi-deck S17/DAS chart, except A2 vs 5 and A4 vs 4: hit, not
        # double, with an infinite deck ([W-inf]: hit 0.133363 > double 0.125954;
        # hit 0.059285 > double 0.058427).
        expected = """
            hard 5   H H H H H H H H H H
            hard 8   H H H H H H H H H H
            hard 9   H D D D D H H H H H
            hard 10  D D D D D D D D H H
            hard 11  D D D D D D D D D H
            hard 12  H H S S S H H H H H
            hard 13  S S S S S H H H H H
            hard 16  S S S S S H H H H H
            hard 17  S S S S S S S S S S
            soft A2  H H H H D H H H H H
            soft A3  H H H D D H H H H H
            soft A4  H H H D D H H H H H
            soft A5  H H D D D H H H H H
            soft A6  H D D D D H H H H H
            soft A7  S Ds Ds Ds Ds S S H H H
            soft A8  S S S S S S S S S S
            pair 22  P P P P P P H H H H
            pair 33  P P P P P P H H H H
            pair 44  H H H P P H H H H H
            pair 55  D D D D D D D D H H
            pair 66  P P P P P H H H H H
            pair 77  P P P P P P H H H H
            pair 88  P P P P P P P P P P
            pair 99  P P P P P S P P S S
            pair TT  S S S S S S S S S S
            pair AA  P P P P P P P P P P"""
        chart = basic_strategy_chart(self.solver)
        for line in expected.strip().splitlines():
            kind, label, *cells = line.split()
            with self.subTest(row=f"{kind} {label}"):
                self.assertEqual(chart[f"{kind} {label}"], cells)


# --- single deck: [W-1d] and [N] --------------------------------------------------------------

class SingleDeckTest(unittest.TestCase):
    """Composition-dependent values; the dealer has peeked (Griffin's conditioning)."""

    @classmethod
    def setUpClass(cls):
        cls.solver = BlackjackSolver(BlackjackRules(decks=1, max_hands=2))

    def check(self, solver, hand, action, published, delta=1.5e-6):
        for up, expected in zip(UPS, row(published)):
            with self.subTest(hand=hand, action=action, up=up):
                self.assertAlmostEqual(solver.action_values(hand[0], hand[1], up)[action], expected, delta=delta)

    def test_wizard_one_deck(self):
        s = self.solver
        self.check(s, "T6", "stand", "-0.297664 -0.249876 -0.193442 -0.141194 -0.179023 -0.483324 -0.527007 -0.539232 -0.542952 -0.652909")
        self.check(s, "97", "stand", "-0.276548 -0.249700 -0.194143 -0.163593 -0.179634 -0.507327 -0.525806 -0.539836 -0.518034 -0.643247")
        self.check(s, "TT", "stand", "0.627226 0.636134 0.644848 0.673675 0.697403 0.764677 0.783251 0.743970 0.583154 0.650097")
        self.check(s, "9A", "stand", "0.655985 0.644126 0.653883 0.682074 0.694187 0.773194 0.784814 0.765635 0.554551 0.680745")
        self.check(s, "T6", "hit", "-0.465396 -0.461402 -0.454566 -0.444223 -0.396278 -0.376194 -0.424823 -0.479306 -0.506929 -0.508750")
        self.check(s, "92", "hit", "0.263585 0.269339 0.300049 0.339824 0.345816 0.288889 0.215256 0.142601 0.103847 0.169644")
        self.check(s, "65", "hit", "0.284031 0.314733 0.351969 0.393653 0.380696 0.297369 0.229714 0.151960 0.113832 0.172946")
        self.check(s, "92", "double", "0.524828 0.538044 0.600097 0.679649 0.691631 0.455401 0.327731 0.213840 0.142776 0.188935")
        self.check(s, "64", "double", "0.432187 0.500878 0.585523 0.677649 0.663295 0.475371 0.317153 0.164633 0.011219 0.048615")

    def test_nairn_split_once(self):
        """Splitting once, each hand played by Nairn's basic strategy (his Appendix A).
        Ours uses Griffin's approximation, exact within ~3e-6 per Nairn."""
        published = {  # (pair, up): (no double after split, double any two after split)
            ("A", "2"): (0.565702, 0.565702), ("8", "2"): (0.0167248, 0.0890850),
            ("8", "6"): (0.233716, 0.340370), ("T", "6"): (0.525105, 0.525105),
            ("2", "2"): (-0.128397, -0.0393101), ("9", "T"): (-0.265721, -0.260551),
            ("A", "T"): (0.194252, 0.194252), ("4", "5"): (0.0947167, 0.256441),
        }
        for das, column in ((False, 0), (True, 1)):
            solver = BlackjackSolver(BlackjackRules(decks=1, max_hands=2, double_after_split=das),
                                     policy=nairn_single_deck_s17, split_choice="best")
            for (pair, up), values in published.items():
                with self.subTest(pair=pair, up=up, das=das):
                    self.assertAlmostEqual(solver.action_values(pair, pair, up)["split"], values[column], delta=5e-6)


# --- generic solver (engine, Fractions) vs fast solver ------------------------------------------

def first_decision(x: SoloExpectimax, hand: tuple[str, str], up: str):
    """The player's first information state with this deal."""
    _, firsts = x.root()
    for _, belief in firsts:
        cards, seen_up, _, _ = situation_of(x.view(belief))
        if cards == tuple(sorted(hand)) and seen_up == up:
            return belief
    raise LookupError((hand, up))


class _Compare:
    """The generic solver plays the engine's rules with exact fractions, including
    the hidden hole card; the fast solver uses rank counts and Griffin's formula.
    Same rules, so the same numbers (to float precision) when no split is involved."""

    def compare(self, rules, shoe, deals):
        x = SoloExpectimax(Engine(Blackjack(rules, shoe=shoe)))
        fast = BlackjackSolver(rules, shoe=shoe)
        for hand, up in deals:
            belief = first_decision(x, hand, up)
            exact = {o.kind: v for o, v in x.option_values(belief).items()}
            approx = fast.action_values(hand[0], hand[1], up)
            for action in exact:
                with self.subTest(hand=hand, up=up, action=action):
                    self.assertAlmostEqual(float(exact[action]), approx[action], delta=1e-12)


class GenericVsFastTest(_Compare, unittest.TestCase):
    def test_small_shoe(self):
        shoe = (2, 1, 2, 1, 2, 1, 2, 1, 2, 6)
        self.compare(BlackjackRules(decks=1, max_hands=1), shoe,
                     [(("T", "6"), "T"), (("9", "2"), "A"), (("A", "7"), "9"), (("5", "3"), "6"), (("3", "2"), "A")])

    def test_whole_game_small_shoe(self):
        shoe = (1, 1, 1, 1, 1, 1, 1, 1, 1, 4)
        rules = BlackjackRules(decks=1, max_hands=1)
        exact = SoloExpectimax(Engine(Blackjack(rules, shoe=shoe))).game_value()
        self.assertAlmostEqual(float(exact), BlackjackSolver(rules, shoe=shoe).round_value(), delta=1e-12)


@unittest.skipUnless(os.environ.get("JOKER_SLOW"), "set JOKER_SLOW=1 to run")
class GenericVsFastSingleDeckTest(_Compare, unittest.TestCase):
    def test_single_deck(self):
        self.compare(BlackjackRules(decks=1, max_hands=1), None,
                     [(("T", "6"), "T"), (("9", "2"), "A"), (("A", "7"), "9"), (("8", "8"), "7")])


# --- arena: Monte Carlo through the engine vs exact values ------------------------------------

class ArenaTest(unittest.TestCase):
    def test_monte_carlo_agrees_with_exact_value(self):
        rules = BlackjackRules(decks=1, max_hands=1)
        for name, policy in (("Nairn", nairn_single_deck_s17), ("solver", None)):
            solver = BlackjackSolver(rules, policy=policy)
            exact = solver.round_value()
            play = engine_policy(policy or solver_policy(solver))
            result = play_solo(Engine(Blackjack(rules)), play, 20_000, seed=7)
            with self.subTest(policy=name):
                self.assertLess(abs(result.mean - exact), 1.5 * result.margin)

    def test_chart_policy_plays_the_chart(self):
        rules = BlackjackRules(decks=1, max_hands=1)
        chart = basic_strategy_chart(BlackjackSolver(rules))
        exact = BlackjackSolver(rules, policy=chart_policy(chart)).round_value()
        optimal = BlackjackSolver(rules).round_value()
        self.assertLessEqual(exact, optimal)
        self.assertGreater(exact, optimal - 0.001)         # a total-based chart loses little


if __name__ == "__main__":
    unittest.main()
