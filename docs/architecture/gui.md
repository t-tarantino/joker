# JOKER — GUI Principles (any card game)

> **Language rule:** All project content is in **English**. (Repeated in every `.md`.)

> **Status:** principles from the owner (2026-10-30), implemented 2026-10-31 for
> **all three games — Scopone, Briscola, Blackjack — with the same code** (§7, §8).
> Open questions in §6 still have provisional answers.

## 1. Goal

One GUI that stays clear and readable for **any** game the engine can model:
2 to many players, cards in hand and on the table per player, shared areas,
hidden teams. It should be drawn **automatically** from the game definition, with
optional hints, not hand-made per game.

## 2. Principles

### G1. The GUI draws zones, not games
Every zone already declares its owner (a player or nobody), who sees what
(back / face / count), ordered or not, and its size. Rule:
- all zones owned by a player go into **that player's seat**;
- zones owned by nobody (table, stock, discard) go **in the center**.

"Each player has cards in hand and on the table" is therefore not a special case:
the seat simply has two lines.

### G2. Players sit in a circle
The circle is the most natural layout, at any player count. You sit at the
bottom; the others follow the order of play, in the direction the game declares
(Scopone and many Italian games go counterclockwise). Shared zones sit in the
middle of the circle.

### G3. A player is an avatar, not a word
Instead of the text "Opponent", each player is a user icon:
- **blue** = you and teammates, **red** = opponents;
- plus a shape cue, so the meaning never depends on color alone
  (color-blind safe). Options: horns (opponents) / halo (teammates), or a sad /
  happy face — **owner to choose**;
- hidden teams (e.g. Briscola a chiamata): neutral gray with "?", optionally
  showing the probability of being your teammate;
- small markers: whose turn (ring / glow), dealer ("D").

### G4. Numbers, not drawings
Hidden cards are a **number** on the avatar (e.g. "5"), never a fan of backs:
faster to read and more compact. Same for taken piles and the stock. Face-up
cards are shown as cards, or as short text ("7♦ Q♠") when space is tight.

### G5. Density adapts; click to expand
As the number of players grows (or the screen shrinks), seats show less:
- **full:** avatar, counts, face-up cards per zone;
- **compact:** avatar + counts; face-up cards as short text;
- **collapsed:** avatar + hand count only.

Clicking a seat **enlarges it** and shows all of that player's information. The
level is chosen from the available space, not from a fixed player count.

### G6. Selection is the core interaction
There is too much information to show at once, so the person **selects** what to
see, quickly:
- **Focused player.** The odds panel shows the odds of one player. Default: the
  player whose turn it is. Clicking an avatar focuses that player.
- **The dual: focused card.** Clicking a card (in the card grid, on the table)
  shows, **on the circle itself**, the probability that each player holds it —
  a percentage on every avatar. Select a player → see their cards; select a card
  → see its players.
- **Lenses.** The odds area has a few views to switch between: every card · ranks
  / suits summary · game questions (e.g. "can sweep") · history. Only one at a
  time.

### G7. Fixed places for the essentials
Whatever the game: the question + card picker (suit → rank → how) is always in
the same place; the odds panel in another; the circle takes the rest.

## 3. Automatic flow — three levels

1. **Pure automatic:** layout from the game definition (players, zones, owners,
   visibility, teams, direction of play). Generic prompts ("What did ⟨player⟩
   put in ⟨zone⟩?"), generic card grid and rank/suit summaries. Always correct.
2. **Optional hints in the game file** (declarative, a few lines): zone names,
   collapsed zones, groups (melds), seat names, game questions.
3. **Custom profile:** only when worth it. Goal: shrink today's
   `joker/gui/profiles.py` to level-2 hints.

## 4. Consequence for the server

Selection also saves computation: the page asks only for what is shown. The API
should move from "send everything every time" to:
- a generic **table description** (players, seats, zones, counts, known cards);
- **on-demand belief queries**: odds for player X, holders of card Y, a lens.

## 5. Stress-test games

The design is done when these three are drawn clearly with no custom code:
1. **Scopone** (4 players, hands only — exists);
2. **Scala 40 / Burraco** (cards in hand **and** melds on the table per player);
3. **Texas Hold'em, 9 players** (many players, shared board).

## 6. Open questions (for the owner)

1. Horns / halo, or sad / happy face?
2. Default focus when it is **your** turn (your own odds are trivial — you know
   your hand): the next player? The last focused one?
3. Should the focus **follow the turn** automatically (it would move at every
   play), or stay where you put it, with a "follow turn" toggle?
4. Hidden teams: gray "?", or a color blend by the probability of being a
   teammate?
5. Player names (typed at the start) instead of "Left / Right"?

Provisional answers used in the Scopone implementation (easy to change):
1 → horns / halo; 2 → the next player; 3 → follows the turn until you click an
avatar, then stays; a "Follow the turn" button goes back; 4 → not needed yet;
5 → not yet.

## 7. Implementation status (2026-10-31: Scopone, Briscola, Blackjack)

| Principle | Done |
|---|---|
| G1 zones by owner | partly: each game lists its seats and the zones they show (level-2 hints, a few lines); not yet derived from the zones automatically |
| G2 circle | yes — seats on an ellipse, you at the bottom, order of play counterclockwise |
| G3 avatars | yes — blue/red user icon, halo for the partner, horns for opponents, yellow ring + "to play" for the turn, "D" for the dealer |
| G4 numbers | yes — face-down cards as a badge on the avatar; stock / shoe as a number; taken piles as numbers |
| G5 density | basic — above 6 players only the focused seat shows details (untested, the games have 2–4 seats) |
| G6 selection | yes — focus on a seat **or a pile** (stock, shoe: "the next card"), "Follow the turn", focused card (click a card in the grid: % on every avatar, ✕ or Esc to clear), lenses: Every card · By rank (suited decks) · History |
| G7 fixed places | yes — circle, then the question, then your cards; odds on the side |
| §4 server | yes — every call carries a view `{focus, card}`; only that is computed (`POST /api/view`) |

## 8. One generic profile — what a game declares (2026-10-31)

`CircleProfile` in `joker/gui/profiles.py` draws every game. A game declares:

| Hint | Scopone | Briscola | Blackjack |
|---|---|---|---|
| seats (in order of play from you), each with its zones | You, Right, Partner, Left — one hand each | You, Opponent — hand + taken pile | You — hand + second hand (split); Dealer — up card, hole card, drawn cards |
| piles in the middle | Table | Table, Trump card, Stock | Shoe |
| zones shown as a number only | taken piles | taken piles | — |
| hooks | header, dealer, game questions (scopa, take, settebello, a 7), final score, capture-aware card choices | header, dealer, trump highlight, trump questions, final points | header, hand totals, dealer questions (bust, final total), next-card questions, **advice on your moves**, result |

Everything else is generic: the circle, avatars, badges, the card picker, the
buttons for non-card decisions, the prompts ("Which card did you get?", "What
did your partner play?"), the history lines, the card grid, the focus on a seat
or pile, the focused card, the lenses.

### Incompatibilities met with Blackjack, and how they were solved (owner to review)

1. **Cards without a suit** (ranks only): the picker skips the suit menu; the grid
   has one row.
2. **A participant who never decides** (the dealer is a fixed procedure, not a
   player): a seat may have no player.
3. **A card that is on the table but not in any zone**: the engine draws the hole
   card only when needed (lazy draw, DR-2). At the table it lies face down in
   front of the dealer, and never seen it is exactly as likely as the next card of
   the shoe. The Blackjack profile shows it (badge "1") and gives the shoe's odds
   for it (hook `unseen_on_table` + a target "the dealer's hole card"). A more
   general fix would be a game hint "this zone holds N face-down cards not drawn
   yet" — to discuss if a second game needs it.
4. **Decisions that are actions, not cards** (stand, hit, double, split): shown as
   buttons. Generic rule: an option is "play a card" only if a card is among its
   arguments (a split moves a card, but it is an action).
5. **Many copies of the same card** (6 decks): the grid shows "x of n unseen" and,
   per card, P(the seat holds at least one) or P(it is the next card).
6. **Strategy** (beyond Goal 1): the `advice` hook gives the expected value of
   each of your options; the page prints it on the move buttons and marks the
   best. Blackjack uses the exact fast solver (`BlackjackSolver`), with the exact
   unseen cards of this hand (all cards seen this hand removed, peek information
   included).
