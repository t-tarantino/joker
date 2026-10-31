"""Briscola sanity checks ("cards don't lie")."""

import os
import random
import time
import unittest
from fractions import Fraction

from joker.core import Engine, StepKind
from joker.games.briscola import Briscola2
from joker.probability import Marginals, P, belief


def _first_choice(trace):
    return next(i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE)


class BriscolaAfterDealTest(unittest.TestCase):
    def test_trump_ace_is_three_in_thirty_six(self):
        engine = Engine(Briscola2())
        for seed in range(3):
            trace = engine.play(random.Random(seed))
            k = _first_choice(trace)
            state = trace.states[k]
            trump = state.vars["trump_suit"]
            info = engine.info_state(trace, observer=0, upto=k)
            started = time.perf_counter()
            result = belief(engine, info, P(lambda w: w.holds("hand1", suit=trump, rank="A")))
            elapsed = time.perf_counter() - started
            ace_seen = engine.view(state).holds("hand0", suit=trump, rank="A") or \
                engine.view(state).holds("trump_card", suit=trump, rank="A")
            self.assertEqual(result.value, Fraction(0) if ace_seen else Fraction(3, 36))
            self.assertTrue(result.exact)
            print(f"\n  seed={seed}: P(opponent holds trump A) = {result.value} "
                  f"over {result.support} worlds in {elapsed:.2f}s")

    def test_marginals_after_first_trick(self):
        engine = Engine(Briscola2())
        trace = engine.play(random.Random(11))
        choices = [i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE]
        k = choices[2]                                   # after the first trick + draws
        info = engine.info_state(trace, observer=0, upto=k)
        marg = belief(engine, info, Marginals("hand1")).value
        self.assertEqual(sum(marg.values()), 3)          # opponent holds exactly 3 cards
        state = trace.states[k]
        seen = {tuple(sorted(engine.cards[i].face.items()))
                for zone in ("hand0", "trump_card", "won0", "won1") for i in state.zones[zone]}
        for face in seen:                                # cards player 0 has seen elsewhere
            self.assertEqual(marg.get(face, 0), 0)


@unittest.skipUnless(os.environ.get("JOKER_SLOW"), "set JOKER_SLOW=1 to run")
class BriscolaFullHandTest(unittest.TestCase):
    def test_loser_taking_the_trump_card_is_known(self):
        engine = Engine(Briscola2())
        for seed in range(20):
            trace = engine.play(random.Random(seed))
            k = next((i for i, e in enumerate(trace.events)
                      if any(getattr(p, "src", None) == "trump_card" and p.dst == "hand1"
                             for p in e.primitives)), None)
            if k is None:
                continue
            card = engine.cards[trace.events[k].primitives[-1].card]
            info = engine.info_state(trace, observer=0, upto=k + 1)
            result = belief(engine, info, P(lambda w: w.holds("hand1", **card.face)))
            self.assertEqual(result.value, 1)
            return
        self.skipTest("no seed where player 1 took the trump card")


if __name__ == "__main__":
    unittest.main()
