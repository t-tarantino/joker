# Example — Two-player Briscola written against the Core Model

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

> **Status:** PSEUDO-CODE for owner review (2026-10-29). It exists to test whether
> the abstractions in [`../core-contracts.md`](../core-contracts.md) make a real
> game natural to write. Not runnable, not final API.

## Rules being modeled (standard 2-player Briscola)

- Italian 40-card deck. Each player gets 3 cards; the next card is turned face up:
  its suit is the trump (*briscola*). It lies under the stock and is drawn last.
- A trick: the leader plays a card, the other plays any card (**no obligation to
  follow suit**). The trick goes to the highest trump, otherwise to the highest
  card of the led suit. Rank order: A, 3, King, Queen, Jack, 7, 6, 5, 4, 2.
- The trick winner draws first, then the loser; when one stock card is left, the
  winner draws it and the loser takes the face-up trump card. The winner leads next.
- Card points: A 11, 3 10, King 4, Queen 3, Jack 2 (total 120). More than 60 wins
  the hand.

## Game definition

```python
# PSEUDO-CODE
from joker.core import (Game, Zone, Var, AutoPhase, ChoicePhase, Option,
                        ALL, OWNER, OTHERS, per_player, END_HAND)
from joker.cards.classic import italian_40

BACK, FACE = "back", "face"
ORDER  = ["A", "3", "K", "Q", "J", "7", "6", "5", "4", "2"]      # strongest first
POINTS = {"A": 11, "3": 10, "K": 4, "Q": 3, "J": 2}

class Briscola2(Game):
    name = "briscola-2p"
    players = 2
    deck = italian_40(back_color="blue")     # 40 CardTypes x1: back{color}, face{suit, rank}

    zones = [
        Zone("stock",      facets={ALL: set()}),                  # unordered: lazy chance (DR-2)
        Zone("trump_card", facets={ALL: {BACK, FACE}}),            # the face-up briscola
        *per_player(lambda p: Zone(f"hand{p}", owner=p,
                                   facets={OWNER: {BACK, FACE}, OTHERS: {BACK}})),
        Zone("table", ordered=True, facets={ALL: {BACK, FACE}}),   # led card first
        *per_player(lambda p: Zone(f"won{p}", owner=p, facets={ALL: {BACK}})),
    ]                                                              # all counts visible (default)

    match_vars = [Var("dealer", initial=0, level=MATCH),
                  Var("hands_won", initial=0, level=MATCH, per_player=True)]
    hand_vars  = [Var("trump_suit", initial=None),                 # public by default
                  Var("leader", initial=None),
                  Var("to_play", initial=None)]

    initial_phase = "deal"
```

### Phases

```python
    class Deal(AutoPhase):
        def run(s, ctx):
            first = 1 - s.dealer
            for p in (first, s.dealer):
                ctx.draw_random("stock", f"hand{p}", n=3)          # 6 Nature steps
            ctx.draw_random("stock", "trump_card", n=1)            # 1 Nature step
            ctx.set("leader", first)
            return "set_trump"                                     # entered after queued draws

    class SetTrump(AutoPhase):
        def run(s, ctx):
            ctx.set("trump_suit", s.cards("trump_card")[0].face["suit"])  # stays known after
            ctx.set("to_play", s.leader)                                   # the card is drawn
            return "play"

    class Play(ChoicePhase):
        def actors(s):
            return [s.to_play]
        def options(s, p):                                         # physical possibility only
            return [Option("play", ref) for ref in s.card_refs(f"hand{p}", seen_by=p)]
        rules = []                                                 # Briscola: no follow-suit rule
        def apply(s, joint, ctx):
            (p, opt), = joint.items()
            ctx.move(opt.args[0], to="table")                      # M1, face visible to all
            if ctx.state.count("table") == 1:
                ctx.set("to_play", 1 - p)
                return "play"
            return "resolve_trick"

    class ResolveTrick(AutoPhase):
        def run(s, ctx):
            led, other = s.cards("table")
            w = s.leader if beats(led, other, s.trump_suit) else 1 - s.leader
            for c in (led, other):
                ctx.move(c, to=f"won{w}")                          # face-down pile: back only
            ctx.set("leader", w)
            ctx.set("to_play", w)
            n = s.count("stock")
            if n >= 2:
                ctx.draw_random("stock", f"hand{w}")
                ctx.draw_random("stock", f"hand{1 - w}")
            elif n == 1:
                ctx.draw_random("stock", f"hand{w}")
                ctx.move(s.cards("trump_card")[0], to=f"hand{1 - w}")
            if n == 0 and ctx.state.count(f"hand{w}") == 0:
                return END_HAND
            return "play"

    phases = {"deal": Deal(), "set_trump": SetTrump(),
              "play": Play(), "resolve_trick": ResolveTrick()}

    def end_hand(s, ctx):                                          # not used by Goal 1
        pts = [sum(POINTS.get(c.face["rank"], 0) for c in s.cards(f"won{p}")) for p in (0, 1)]
        for p in (0, 1):
            if pts[p] > 60:
                ctx.set(f"hands_won[{p}]", s.hands_won[p] + 1)
        ctx.set("dealer", 1 - s.dealer)

def beats(led, other, trump):          # pure helper: True if `led` wins the trick
    if other.face["suit"] == led.face["suit"]:
        return ORDER.index(led.face["rank"]) < ORDER.index(other.face["rank"])
    return other.face["suit"] != trump
```

## What player 0 observes (derived automatically, S5.2)

| Event | What player 0 perceives |
|---|---|
| Nature draws a card into `hand0` | `stock → hand0`, attributes `back` + `face` (own hand) |
| Nature draws a card into `hand1` | `stock → hand1`, attributes `back` only (`color: blue`) |
| Trump card turned | `stock → trump_card`, `back` + `face` (visible to all) |
| Player 1 plays | actor = 1 (public, S5.5); `hand1 → table`, `back` + `face` |
| Trick collected | `table → won1`: face seen **in the source zone**, so known |
| Loser takes the trump card | `trump_card → hand1`: face seen in the source zone → everyone knows player 1 holds it |

The last two rows show the facet rule doing real work: a card moving into a hidden
zone stays known if it was visible where it came from. Nobody wrote that rule.

## Queries player 0 can ask

```python
info = engine.info_state(trace, observer=0)            # or built from live input

belief(info, P(lambda w: w.holds(1, suit=w.trump_suit, rank="A")))
belief(info, P(lambda w: w.count(1, suit=w.trump_suit) >= 2))
belief(info, NextDraw("stock"))                        # distribution of my next card
belief(info, Marginals(zone="hand1"))                  # every card type: P(in opponent's hand)
```

**Sanity check ("cards don't lie"):** right after the deal, if player 0 does not hold
the trump Ace and it is not the turned card, then 36 cards are unseen, 3 of them
in `hand1`, so P(player 1 holds the trump Ace) = 3/36 = 1/12. The exact method must
return exactly this; the brute-force oracle must agree.

## Two snippets from other games

**A class-(ii) rule (Tressette: follow suit).** The "void in a suit" constraint is
never written; it emerges from replay when this rule is trusted (A3, S7.4):

```python
follow_suit = Rule(
    name="follow_suit",
    klass=LATER,                                   # a renege is exposed later
    allowed=lambda s, p, opt: (
        s.count("table") == 0                                       # leading: free
        or opt.args[0].face["suit"] == s.cards("table")[0].face["suit"]
        or not any(c.face["suit"] == s.cards("table")[0].face["suit"]
                   for c in s.cards(f"hand{p}"))                    # void: free
    ),
)
```

**A hidden role derived from cards (Briscola a chiamata, S3.6a).**

```python
def partner(s):                         # derived function: pure read of the state
    return s.holder_of(s.called_card)   # whoever holds the called card

belief(info, P(lambda w: partner(w) == 3))   # = P(player 3 holds the called card)
```

## What writing this example taught us

- The state machine (DR-1) is a bit more verbose than a script, but every piece of
  control state (`leader`, `to_play`, phase) is an explicit public variable, which
  is what makes cloning and replay trivial.
- Lazy chance (`draw_random`, DR-2) keeps dealing to one line per destination.
- `trump_suit` had to become a variable: once the trump card is drawn, its suit
  must still be known. M2 covered it without any special case.
- No observation, constraint or visibility logic appears in the game code at all.
