"""Live mode: driving a session with the observations of a simulated hand must
always offer the real observation, and end in the same worlds as the exact method."""

import random
import unittest

from joker.core import Engine, StepKind
from joker.games.briscola import Briscola2
from joker.games.tiny import TinyTricks
from joker.live import LiveSession
from joker.probability import possible_worlds


def _normalized(worlds):
    total = sum(w for _, w in worlds)
    return {s: w / total for s, w in worlds}


def drive(test, engine, trace, observer, until=None):
    actual = engine.info_state(trace, observer).observations
    target = len(actual) if until is None else until
    session = LiveSession(engine, observer, trace.match_state)
    session.auto_advance()
    while len(session.info.observations) < target:
        k = len(session.info.observations)
        options = [c.observation for c in session.pending().choices]
        test.assertIn(actual[k], options)
        session.choose(options.index(actual[k]))
        done = len(session.info.observations)
        test.assertEqual(session.info.observations, actual[:done])
    return session


class LiveDrivingTest(unittest.TestCase):
    def test_tiny_tricks_full_hand(self):
        engine = Engine(TinyTricks())
        for seed in range(4):
            trace = engine.play(random.Random(seed))
            for observer in (0, 1):
                session = drive(self, engine, trace, observer)
                self.assertIsNone(session.pending())
                exact, _, _ = possible_worlds(engine, session.info)
                self.assertEqual(_normalized(list(session._trusted.items())), _normalized(exact))

    def test_briscola_first_trick(self):
        engine = Engine(Briscola2())
        trace = engine.play(random.Random(4))
        choices = [i for i, e in enumerate(trace.events) if e.kind is StepKind.CHOICE]
        session = drive(self, engine, trace, 0, until=choices[2])
        exact, _, _ = possible_worlds(engine, session.info)
        self.assertEqual(_normalized(list(session._trusted.items())), _normalized(exact))

    def test_undo_returns_to_previous_choice(self):
        engine = Engine(TinyTricks())
        session = LiveSession(engine, 0)
        session.auto_advance()
        before = session.info
        pending = session.pending()
        session.choose(0, label="first")
        self.assertEqual(session.labels, ["first"])
        self.assertTrue(session.undo())
        self.assertEqual(session.info, before)
        self.assertEqual(session.pending(), pending)
        self.assertEqual(session.labels, [])


class LiveViolationTest(unittest.TestCase):
    def test_a_renege_can_be_recorded_and_is_reported(self):
        engine = Engine(TinyTricks())

        def cheater(view, p, options, rng):
            if p == 1:
                legal = engine.legal_options(view.raw, p)
                illegal = [o for o in options if o not in legal]
                if illegal:
                    return illegal[0]
            return rng.choice(options)

        for seed in range(30):
            trace = engine.play(random.Random(seed), policy=cheater, enforce_rules=False)
            session = drive(self, engine, trace, 0)          # never gets stuck
            if session.warnings:
                self.assertEqual(session.warnings[0].player, 1)
                return
        self.fail("no seed exposed a renege")


if __name__ == "__main__":
    unittest.main()
