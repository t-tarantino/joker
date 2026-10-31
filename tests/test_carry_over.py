"""Cards that stay out between hands (match-level zones, Engine.next_hand,
LiveSession.next_hand) — handoffs/cards-across-hands.md §3."""

import random
import unittest
from fractions import Fraction

from joker.core import Engine, FACE, StepKind
from joker.core.card import facet_dict
from joker.games.blackjack import Blackjack, BlackjackRules, shoe_counts
from joker.games.briscola import Briscola2
from joker.games.tiny import TinyCarry, TinyTricks
from joker.live import LiveSession
from joker.probability import possible_worlds
from joker.probability.oracle import oracle_worlds
from joker.strategy.blackjack import (BlackjackSolver, next_hand_value, shoe_mixture,
                                      unseen_counts)


def _normalized(items):
    items = list(items)
    total = sum(w for _, w in items)
    out: dict = {}
    for s, w in items:
        out[s] = out.get(s, Fraction(0)) + w / total
    return out


def _follow(test, session, trace, observer=0):
    """Drive the session through the observations of a simulated hand."""
    actual = session.engine.info_state(trace, observer).observations
    session.auto_advance()
    while len(session.info.observations) < len(actual):
        k = len(session.info.observations)
        options = [c.observation for c in session.pending().choices]
        test.assertIn(actual[k], options)
        session.choose(options.index(actual[k]))
    test.assertEqual(session.info.observations, actual)
    test.assertIsNone(session.pending())


class TinyCarryTest(unittest.TestCase):
    def test_two_hands_equal_the_oracle(self):
        """Live mode across two hands = brute force over the two-hand history."""
        engine = Engine(TinyCarry())
        for seed in range(12):
            rng = random.Random(seed)
            trace1 = engine.play(rng)
            trace2 = engine.play(rng, start=engine.next_hand(trace1.final))
            session = LiveSession(engine, 0)
            _follow(self, session, trace1)
            session.next_hand()
            _follow(self, session, trace2)

            first = oracle_worlds(engine, engine.info_state(trace1, 0))
            start: dict = {}
            for s, w in first.items():
                nxt = engine.next_hand(s)
                start[nxt] = start.get(nxt, Fraction(0)) + w
            second = oracle_worlds(engine, engine.info_state(trace2, 0), start=start)
            expected = _normalized((engine.canonical(s), w) for s, w in second.items())
            self.assertEqual(_normalized(session._trusted.items()), expected)
            exact, _, _ = possible_worlds(engine, session.info, start=session._start)
            self.assertEqual(_normalized(exact), expected)

    def test_undo_goes_back_to_the_end_of_the_previous_hand(self):
        engine = Engine(TinyCarry())
        session = LiveSession(engine, 0)
        _follow(self, session, engine.play(random.Random(3)))
        before = dict(session._trusted)
        session.next_hand()
        self.assertEqual(session.hand, 2)
        self.assertTrue(session.undo())
        self.assertEqual(session.hand, 1)
        self.assertEqual(session._trusted, before)
        self.assertIsNone(session.pending())


class OldBehaviorTest(unittest.TestCase):
    def test_without_match_level_zones_next_hand_is_a_new_hand(self):
        engine = Engine(Briscola2())
        final = engine.play(random.Random(0), match_state={"dealer": 1}).final
        self.assertEqual(engine.next_hand(final), engine.new_hand(engine.match_state_after(final)))

    def test_live_next_hand_equals_a_new_session(self):
        engine = Engine(TinyTricks())
        session = LiveSession(engine, 0)
        _follow(self, session, engine.play(random.Random(1)))
        session.next_hand()
        fresh = LiveSession(engine, 0)
        self.assertEqual(session._trusted, fresh._trusted)
        self.assertEqual(session.pending(), fresh.pending())


def _play_ranks(test, session, ranks, actions):
    """Live Blackjack hand: draws seen with the given ranks, choices the given actions."""
    ranks, actions = list(ranks), list(actions)
    session.auto_advance()
    while (pending := session.pending()) is not None:
        if pending.kind is StepKind.CHOICE:
            want = actions.pop(0)
            index = next(i for i, c in enumerate(pending.choices) if c.own.kind == want)
        else:                                # None: the choice where no card is seen
            want = ranks.pop(0)
            index = next(i for i, c in enumerate(pending.choices)
                         if (facet_dict(c.moves[0].attrs, FACE).get("rank") if c.moves else None) == want)
        session.choose(index)
    test.assertEqual((ranks, actions), ([], []))


class BlackjackShoeTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Blackjack(BlackjackRules(decks=1, max_hands=2)))

    def test_seen_cards_stay_out(self):
        session = LiveSession(self.engine, 0)
        # you T, up 5, you 7; stand; the dealer turns T and draws 6 (21)
        _play_ranks(self, session, ["T", "5", "7", "T", "6"], ["stand"])
        session.next_hand()
        (view, _), = session.worlds()
        expected = list(shoe_counts(1))
        for i in (9, 4, 6, 9, 5):            # T, 5, 7, T, 6
            expected[i] -= 1
        self.assertEqual(unseen_counts(view), tuple(expected))
        self.assertEqual(view.count("discard"), 5)

    def test_unseen_hole_card_after_a_peek(self):
        """Up A, the dealer peeks (no blackjack), you bust: the hole card goes to the
        discard unseen, known not to be a ten. P(next card is a ten) = 14/47, not
        14/48 as if a random unseen card had been removed."""
        session = LiveSession(self.engine, 0)
        _play_ranks(self, session, ["T", "A", "6", None, "T"], ["hit"])   # None: no blackjack
        session.next_hand()
        mixture = shoe_mixture(session.worlds())
        self.assertEqual(len(mixture), 9)    # the hole card: any rank but T
        p_ten = sum(Fraction(deck[9], sum(deck)) * Fraction(w) for deck, w in mixture)
        self.assertAlmostEqual(float(p_ten), 14 / 47, places=12)
        tens = lambda view: sum(1 for c in view.cards("shoe") if c.face["rank"] == "T")
        exact = sum(Fraction(tens(view), view.count("shoe")) * w for view, w in session.worlds())
        self.assertEqual(exact, Fraction(14, 47))

    def test_cut_card_and_reshuffle(self):
        engine, rng = self.engine, random.Random(7)
        s, reshuffles = engine.new_hand(), 0
        for _ in range(40):
            final = engine.play(rng, start=s).final
            s = engine.next_hand(final)
            engine.check_invariants(s)
            if final.zones["shoe"] and len(final.zones["shoe"]) <= 13:   # cut card at 75% of 52
                self.assertEqual(len(s.zones["shoe"]), 52)
                reshuffles += 1
            else:
                self.assertEqual(len(s.zones["discard"]), 52 - len(s.zones["shoe"]))
        self.assertGreater(reshuffles, 2)
        self.assertEqual(len(engine.next_hand(final, reshuffle=True).zones["shoe"]), 52)

    def test_no_cut_card_the_shoe_refills_from_the_discard(self):
        engine = Engine(Blackjack(BlackjackRules(decks=1, max_hands=2, penetration=None)))
        rng, s = random.Random(2), engine.new_hand()
        for _ in range(60):                  # far more cards than one deck
            s = engine.next_hand(engine.play(rng, start=s).final)
            engine.check_invariants(s)


class NextHandValueTest(unittest.TestCase):
    def test_estimate_close_to_exact_on_a_fresh_deck(self):
        rules = BlackjackRules(decks=1, max_hands=2)
        exact = next_hand_value(rules, shoe_counts(1), exact=True)
        self.assertAlmostEqual(exact, BlackjackSolver(rules).round_value(), places=12)
        self.assertLess(abs(next_hand_value(rules, shoe_counts(1)) - exact), 2e-4)


if __name__ == "__main__":
    unittest.main()
