"""Scopone scientifico: rules, and the exact combinatorial (exchangeable) method
checked against full enumeration on a miniature Scopone."""

import random
import unittest
from fractions import Fraction

from joker.core import Engine, StepKind
from joker.core.card import CardType
from joker.games.scopone import VALUES, capture_sets, hand_score, make_scopone
from joker.live import ExchangeableSession
from joker.probability import possible_worlds
from joker.probability.views import WorldsBelief
from joker.core.state import View


def _card(suit, rank):
    return CardType.of(back={"color": "blue"}, face={"suit": suit, "rank": rank})


def drive(test, engine, trace, observer, check=None):
    """Feed a simulated hand to an ExchangeableSession, observation by observation."""
    actual = engine.info_state(trace, observer).observations
    session = ExchangeableSession(engine, observer, trace.match_state)
    session.auto_advance()
    while len(session.info.observations) < len(actual):
        k = len(session.info.observations)
        options = [c.observation for c in session.pending().choices]
        test.assertIn(actual[k], options)
        session.choose(options.index(actual[k]))
        test.assertEqual(session.info.observations, actual[:len(session.info.observations)])
        if check:
            check(session)
    test.assertIsNone(session.pending())
    return session


class CaptureRulesTest(unittest.TestCase):
    def test_same_rank_has_priority_over_sums(self):
        table = [_card("cups", "3"), _card("coins", "4"), _card("swords", "A")]
        self.assertEqual(capture_sets(4, table), [(table[1],)])           # not 3 + A

    def test_sum_captures_and_choices(self):
        table = [_card("cups", "3"), _card("coins", "2"), _card("swords", "A"), _card("clubs", "4")]
        sets = capture_sets(VALUES["5"], table)
        self.assertIn((table[0], table[1]), sets)
        self.assertIn((table[2], table[3]), sets)
        self.assertEqual(capture_sets(10, [_card("cups", "A")]), [])

    def test_hand_score(self):
        team0 = [{"suit": "coins", "rank": "7"}, {"suit": "coins", "rank": "6"}]
        score = hand_score({0: team0, 1: []}, {0: 2, 1: 0})
        self.assertEqual(score[0]["settebello"], 1)
        self.assertEqual(score[0]["scope"], 2)


class ScoponeEngineTest(unittest.TestCase):
    def test_full_hands_conserve_cards_and_end(self):
        engine = Engine(make_scopone())
        for seed in range(3):
            trace = engine.play(random.Random(seed))
            for s in trace.states:
                engine.check_invariants(s)
            final = trace.final
            self.assertIs(engine.next_step(final).kind, StepKind.END)
            self.assertEqual(len(final.zones["taken0"]) + len(final.zones["taken1"]), 40)

    def test_last_card_is_never_a_scopa(self):
        engine = Engine(make_scopone())
        for seed in range(10):
            trace = engine.play(random.Random(seed))
            last_play = max(i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE)
            names = [p.name for p in trace.events[last_play].primitives if hasattr(p, "name")]
            self.assertFalse(any(n.startswith("scope") for n in names))


class ExchangeableAgainstEnumerationTest(unittest.TestCase):
    """On a miniature Scopone (8 cards, 2 each) every number of the combinatorial
    method must equal the exact enumeration, at every step, for every observer."""

    def test_mini_scopone(self):
        engine = Engine(make_scopone(suits=("coins", "cups"), ranks=("A", "2", "3", "4"), hand_size=2))
        types = sorted({c.type for c in engine.cards}, key=str)
        is_coin = lambda t: t.face["suit"] == "coins"
        is_ace = lambda t: t.face["rank"] == "A"

        def check(session):
            fast = session.belief()
            exact_worlds, _, _ = possible_worlds(engine, session.info)
            total = sum(w for _, w in exact_worlds)
            slow = WorldsBelief(engine, [(View(engine, s), w / total) for s, w in exact_worlds])
            self.assertEqual(fast.support, slow.support)
            for zone in engine.zones:
                self.assertEqual(fast.zone_count(zone), slow.zone_count(zone))
                for t in types:
                    self.assertEqual(fast.expected(zone, t), slow.expected(zone, t), (zone, str(t)))
                    self.assertEqual(fast.certain(zone, t), slow.certain(zone, t), (zone, str(t)))
                for match in (is_coin, is_ace):
                    for k in (1, 2):
                        self.assertEqual(fast.prob_at_least(zone, k, match),
                                         slow.prob_at_least(zone, k, match))

        for seed in range(4):
            trace = engine.play(random.Random(seed))
            for observer in range(4):
                drive(self, engine, trace, observer, check)


class FullScoponeTest(unittest.TestCase):
    def test_settebello_after_the_deal(self):
        engine = Engine(make_scopone())
        trace = engine.play(random.Random(2))
        first_play = next(i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE)
        session = ExchangeableSession(engine, 0, trace.match_state)
        actual = engine.info_state(trace, 0).observations
        session.auto_advance()
        while len(session.info.observations) < first_play:
            options = [c.observation for c in session.pending().choices]
            session.choose(options.index(actual[len(session.info.observations)]))
        belief = session.belief()
        settebello = next(c.type for c in engine.cards if c.face == {"suit": "coins", "rank": "7"})
        mine = belief.certain("hand0", settebello) == 1
        expected = Fraction(0) if mine else Fraction(1, 3)
        self.assertEqual(belief.expected("hand2", settebello), expected)     # partner
        if not mine:
            self.assertEqual(belief.support, 5550996791340)                   # 30! / (10!)^3

    def test_whole_hand_can_be_followed(self):
        engine = Engine(make_scopone())
        for seed in range(2):
            trace = engine.play(random.Random(seed))
            session = drive(self, engine, trace, 0)
            belief = session.belief()
            self.assertEqual(belief.zone_count("taken0") + belief.zone_count("taken1"), 40)


if __name__ == "__main__":
    unittest.main()
