"""Probability tests: exact method vs brute-force oracle, the A1.1 example,
canonical options (S7.8), partial observations (S1.6), violations (A3)."""

import random
import unittest
from fractions import Fraction

from joker.core import Engine, StepKind, TrustPolicy
from joker.games.tiny import TinyDiscard, TinyDupDiscard, TinyFollow, TinyTricks
from joker.probability import (Distribution, P, ViolationDetected, belief, oracle_worlds,
                               possible_worlds)


def _normalized(worlds, engine):
    """Normalized weights, worlds that differ only by which copy of a card is where
    merged (the exact method merges them, Engine.canonical; the oracle does not)."""
    total = sum(w for _, w in worlds)
    out = {}
    for s, w in worlds:
        key = engine.canonical(s)
        out[key] = out.get(key, 0) + w / total
    return out


class OracleAgreementTest(unittest.TestCase):
    """The exact incremental method must match brute force exactly (Fractions)."""

    def check(self, game, seeds, observers=(0, 1)):
        engine = Engine(game())
        for seed in seeds:
            trace = engine.play(random.Random(seed))
            for observer in observers:
                for upto in range(len(trace.events) + 1):
                    info = engine.info_state(trace, observer, upto)
                    exact, _, _ = possible_worlds(engine, info)
                    oracle = oracle_worlds(engine, info)
                    self.assertEqual(_normalized(exact, engine), _normalized(list(oracle.items()), engine),
                                     f"{game.name} seed={seed} observer={observer} upto={upto}")

    def test_tiny_tricks(self):
        self.check(TinyTricks, seeds=range(3))

    def test_tiny_discard(self):
        self.check(TinyDiscard, seeds=range(4))

    def test_tiny_dup_discard(self):
        self.check(TinyDupDiscard, seeds=range(4))


class A11ExampleTest(unittest.TestCase):
    """assumptions.md A1.1: spades led, opponent plays 7♠ → P(remaining card is a
    spade) = 1/2 under 'choices add no weight' (a random-player model gives 1/3)."""

    def test_seven_of_spades(self):
        engine = Engine(TinyFollow())
        ids = {(c.face["suit"], c.face["rank"]): c.id for c in engine.cards}
        s = engine.new_hand()
        outcomes = [None, ids[("spades", "2")], ids[("spades", "7")], ids[("hearts", "3")]]
        for outcome in outcomes:
            s, _ = engine.apply(s, outcome)
        for player, card in ((0, ("spades", "2")), (1, ("spades", "7"))):
            opt = next(o for o in engine.legal_options(s, player)
                       if (o.card.face["suit"], o.card.face["rank"]) == card)
            outcomes.append({player: opt})
            s, _ = engine.apply(s, {player: opt})
        trace = engine.replay({}, outcomes)
        info = engine.info_state(trace, observer=0)
        result = belief(engine, info, P(lambda w: w.holds("hand1", suit="spades")))
        self.assertEqual(result.value, Fraction(1, 2))
        self.assertTrue(result.exact)


class CanonicalOptionsWeightTest(unittest.TestCase):
    """S7.8: hand drawn from {1, 1, 2, 3}, hidden discard → P(discard is a 1) = 5/12."""

    def test_dup_discard(self):
        engine = Engine(TinyDupDiscard())
        trace = engine.play(random.Random(0))
        info = engine.info_state(trace, observer=0)
        result = belief(engine, info, P(lambda w: w.holds("discard", rank=1)))
        self.assertEqual(result.value, Fraction(5, 12))


class PartialObservationTest(unittest.TestCase):
    """S1.6: the discarded card's back color is seen, so worlds must agree with it."""

    def test_discard_back_color_is_respected(self):
        engine = Engine(TinyDiscard())
        for seed in range(6):
            trace = engine.play(random.Random(seed))
            color = engine.cards[trace.final.zones["discard"][0]].back["color"]
            info = engine.info_state(trace, observer=0)
            dist = belief(engine, info, Distribution(lambda w: w.cards("discard")[0].back["color"]))
            self.assertEqual(dist.value, {color: Fraction(1)})


class ViolationTest(unittest.TestCase):
    """A3: a renege can make 'trust follow_suit' inconsistent; it must be reported,
    never crash, and never be reported when everybody plays by the rules."""

    def test_reported_only_when_someone_reneged(self):
        engine = Engine(TinyTricks())

        def cheater(view, p, options, rng):          # player 1 reneges whenever it can
            if p == 1:
                legal = engine.legal_options(view.raw, p)
                illegal = [o for o in options if o not in legal]
                if illegal:
                    return illegal[0]
            return rng.choice(options)

        reported = 0
        for seed in range(30):
            honest = engine.play(random.Random(seed))
            self.assertEqual(belief(engine, engine.info_state(honest, 0), P(lambda w: True)).warnings, ())

            trace = engine.play(random.Random(seed), policy=cheater, enforce_rules=False)
            reneged = any(engine.violations(s, e.outcome)
                          for s, e in zip(trace.states, trace.events) if e.kind is StepKind.CHOICE)
            result = belief(engine, engine.info_state(trace, 0), P(lambda w: True))
            if result.warnings:
                self.assertTrue(reneged)
                self.assertEqual(result.warnings, (ViolationDetected(1, "follow_suit"),))
                reported += 1
        self.assertGreater(reported, 0)

    def test_distrusting_the_rule_changes_the_belief(self):
        engine = Engine(TinyFollow())
        trace = engine.play(random.Random(0))
        info = engine.info_state(trace, observer=0)
        query = P(lambda w: True)
        trusted = belief(engine, info, query)
        relaxed = belief(engine, info, query, TrustPolicy(later=False))
        self.assertGreaterEqual(relaxed.support, trusted.support)


if __name__ == "__main__":
    unittest.main()
