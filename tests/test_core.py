"""Core model tests: cards, visibility, canonical options, conservation,
determinism, observation leakage (core-contracts.md §8)."""

import random
import unittest

from joker.core import (ALL, BACK, FACE, OMNISCIENT, OTHERS, OWNER, PUBLIC, CardType, Engine,
                        MoveSeen, StepKind, Zone)
from joker.core.card import build_cards
from joker.games.briscola import Briscola2
from joker.games.tiny import TinyDupDiscard, TinyTricks


class CardsTest(unittest.TestCase):
    def test_duplicate_copies_get_distinct_ids(self):
        seven = CardType.of(back={"color": "blue"}, face={"suit": "hearts", "rank": "7"})
        cards = build_cards([(seven, 2)])
        self.assertEqual([c.id for c in cards], [0, 1])
        self.assertEqual(cards[0].type, cards[1].type)

    def test_restrict_keeps_only_visible_facets(self):
        card = CardType.of(back={"color": "red"}, face={"suit": "spades", "rank": "A"})
        self.assertEqual(card.restrict(frozenset({BACK})), (("back", (("color", "red"),)),))


class ZoneVisibilityTest(unittest.TestCase):
    def test_selectors(self):
        all_facets = frozenset({BACK, FACE})
        hand = Zone("hand1", owner=1, facets={OWNER: {BACK, FACE}, OTHERS: {BACK}})
        self.assertEqual(hand.visible_facets(1, all_facets), {BACK, FACE})
        self.assertEqual(hand.visible_facets(0, all_facets), {BACK})
        self.assertEqual(hand.visible_facets(PUBLIC, all_facets), {BACK})
        self.assertEqual(hand.visible_facets(OMNISCIENT, all_facets), all_facets)
        stock = Zone("stock", facets={ALL: set()})
        self.assertEqual(stock.visible_facets(0, all_facets), frozenset())
        self.assertTrue(stock.count_seen(0))


class CanonicalOptionsTest(unittest.TestCase):
    def test_identical_copies_are_one_option(self):
        engine = Engine(TinyDupDiscard())
        s = engine.new_hand()
        s, _ = engine.apply(s)                       # deal: queues 3 draws into hand1
        for cid in (0, 1, 2):                        # the two 1s and the 2
            s, _ = engine.apply(s, cid)
        options = engine.legal_options(s, 1)
        self.assertEqual(sorted(o.card.face["rank"] for o in options), [1, 2])


class EngineInvariantsTest(unittest.TestCase):
    GAMES = (TinyTricks, Briscola2)

    def test_conservation_and_hand_ends(self):
        for game in self.GAMES:
            engine = Engine(game())
            for seed in range(5):
                trace = engine.play(random.Random(seed))
                for s in trace.states:
                    engine.check_invariants(s)
                self.assertIs(engine.next_step(trace.final).kind, StepKind.END)

    def test_replay_is_deterministic(self):
        for game in self.GAMES:
            engine = Engine(game())
            trace = engine.play(random.Random(42))
            again = engine.replay(trace.match_state, trace.outcomes)
            self.assertEqual(trace.states, again.states)
            self.assertEqual(trace.events, again.events)

    def test_briscola_deals_all_40_cards(self):
        engine = Engine(Briscola2())
        trace = engine.play(random.Random(7))
        won = trace.final.zones["won0"] + trace.final.zones["won1"]
        self.assertEqual(len(won), 40)


class ObservationLeakTest(unittest.TestCase):
    def test_opponent_draws_show_only_the_back(self):
        engine = Engine(Briscola2())
        trace = engine.play(random.Random(3))
        info = engine.info_state(trace, observer=0)
        for obs in info.observations:
            for seen in obs.perceived:
                if isinstance(seen, MoveSeen) and seen.dst == "hand1" and seen.src == "stock":
                    self.assertEqual({facet for facet, _ in seen.attrs}, {BACK})

    def test_unordered_zones_never_reveal_positions(self):
        engine = Engine(Briscola2())
        trace = engine.play(random.Random(5))
        for obs in engine.info_state(trace, observer=PUBLIC).observations:
            for seen in obs.perceived:
                if isinstance(seen, MoveSeen):
                    if not engine.zones[seen.src].ordered:
                        self.assertIsNone(seen.src_pos)
                    if not engine.zones[seen.dst].ordered:
                        self.assertIsNone(seen.dst_pos)

    def test_actor_sees_own_option_others_do_not(self):
        engine = Engine(TinyTricks())
        trace = engine.play(random.Random(1))
        choice = next(i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE)
        actor = trace.events[choice].actors[0]
        mine = engine.info_state(trace, actor).observations[choice]
        theirs = engine.info_state(trace, 1 - actor).observations[choice]
        self.assertIsNotNone(mine.own)
        self.assertIsNone(theirs.own)


if __name__ == "__main__":
    unittest.main()
