// JOKER local table — talks to the Python server (joker/gui/server.py).
// ONE renderer for every game (docs/architecture/gui.md): seats on a circle, piles
// in the middle, the question + card picker, your cards, and the odds of one
// selected player or pile. Everything game-specific comes from the server.
"use strict";

const RED_SUITS = new Set(["coins", "cups", "hearts", "diamonds"]);
const SUIT_LABEL = { coins: "Coins", cups: "Cups", swords: "Swords", clubs: "Clubs",
  hearts: "Hearts", diamonds: "Diamonds", spades: "Spades" };
const RANK_LABEL = { A: "Ace", J: "Jack", Q: "Queen", K: "King", T: "10" };
const RANK_SHOW = { T: "10" };

// Standard suit symbols; Italian suits use the usual French equivalents
// (coins = diamonds, cups = hearts, swords = spades, clubs = clubs).
// U+FE0E asks for the text glyph, not an emoji.
const SUIT_SYMBOL = {
  coins: "♦︎", cups: "♥︎", swords: "♠︎", clubs: "♣︎",
  diamonds: "♦︎", hearts: "♥︎", spades: "♠︎",
};

let state = null;
let busy = false;
// card picker selection; the suit is kept between questions when still available
const pick = { suit: null, rank: null };
// what the person selected (gui.md G6). focus: a seat or pile key, or null = follow
// the turn; card: "suit/rank" whose holders are shown on the circle; lens: the odds view.
const view = { focus: null, card: null, lens: "cards" };

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x) => `${x.toFixed(1)}%`;
const pctShort = (x) => (x >= 99.95 ? "100%" : x < 0.05 ? "0%" : x >= 10 ? `${x.toFixed(0)}%` : `${x.toFixed(1)}%`);
const suitKey = (suit) => suit ?? "";
const rankShow = (rank) => RANK_SHOW[rank] || rank;
const suitColor = (suit) => (!suit ? "plain" : RED_SUITS.has(suit) ? "red" : "blue");
const symbol = (suit) => (suit ? SUIT_SYMBOL[suit] || "" : "");

function cardName(face) {
  const rank = RANK_LABEL[face.rank] || face.rank;
  return face.suit ? `${rank} of ${SUIT_LABEL[face.suit] || face.suit}` : rank;
}

const shortCard = (face) => `<span class="${suitColor(face.suit)}">${esc(rankShow(face.rank))}${symbol(face.suit)}</span>`;

function cardHTML(card, opts = {}) {
  const face = card.face;
  const trump = state && state.trump && face.suit === state.trump ? " trump" : "";
  const cls = `card ${suitColor(face.suit)}${trump}${opts.sm ? " sm" : ""}${opts.xs ? " xs" : ""}`;
  return `<div class="${cls}" role="img" aria-label="${esc(cardName(face))}"><span class="rank">${esc(rankShow(face.rank))}</span>` +
    `<span class="suit" aria-hidden="true">${symbol(face.suit)}</span></div>`;
}

// every call carries the view, so the server computes only what is shown
async function api(path, body) {
  if (busy) return;
  busy = true;
  document.body.classList.add("busy");
  const sel = { focus: view.focus, card: view.card };
  try {
    const res = body === undefined
      ? await fetch(`${path}?${new URLSearchParams({ focus: sel.focus ?? "", card: sel.card ?? "" })}`)
      : await fetch(path, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, view: sel }),
      });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    state = data;
    pick.rank = null;
    render();
  } finally {
    busy = false;
    document.body.classList.remove("busy");
  }
}

function setBand(left, right) {
  document.getElementById("score-opp").textContent = left;
  document.getElementById("score-me").textContent = right;
}

// ---------- the question ----------

function askHTML() {
  const p = state.pending;
  if (!p) return finalHTML();
  const body = p.choices.every((c) => c.card && !c.action) ? pickerHTML(p.choices) : buttonsHTML(p.choices);
  return `<section class="ask ${p.who}" aria-label="What happened"><h2>${esc(p.question)}</h2>${body}</section>`;
}

const ev = (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;

// choices that are not just a card: actions (stand, hit...) or events; with the
// expected value of each of your options when the game gives advice (Goal 2)
function buttonsHTML(choices) {
  const advised = choices.some((c) => c.value !== undefined);
  const buttons = choices.map((c) => `<button type="button" class="key option${c.best ? " best" : ""}" data-choice="${c.index}">
      <span class="otext">${esc(c.text)}${c.card && c.action ? " " + shortCard(c.card.face) : ""}</span>
      ${c.value !== undefined ? `<span class="oval" title="expected result per original bet">${ev(c.value)}</span>` : ""}
      ${c.best ? '<span class="tag best-tag">best</span>' : ""}</button>`).join("");
  const note = advised ? `<p class="panel-sub" style="margin:0">Expected result of each move per original bet, exact for the cards seen, then playing on perfectly.</p>` : "";
  return `<div class="pick-row">${buttons}</div>${note}`;
}

// the choices available for a given suit / rank
const choicesFor = (choices, suit, rank) =>
  choices.filter((c) => suitKey(c.card.face.suit) === suit && (rank === undefined || c.card.face.rank === rank));

// Suit menu, then rank menu, then — only when one card can be played in several
// ways (different captures) — the ways. Suits and ranks keep a fixed position
// (deck order); the ones not possible now are disabled. No suits: ranks only.
function pickerHTML(choices) {
  const deck = state.deck.map((d) => ({ ...d, key: suitKey(d.suit) }));
  const open = deck.filter((d) => choicesFor(choices, d.key).length);
  if (!open.some((d) => d.key === pick.suit)) pick.suit = open.length === 1 ? open[0].key : null;

  let out = "";
  if (deck.length > 1) {
    const suits = deck.map((d) => {
      const n = choicesFor(choices, d.key).length;
      return `<button type="button" class="key ${suitColor(d.suit)}" data-suit="${esc(d.key)}"
        aria-pressed="${d.key === pick.suit}" ${n ? "" : "disabled"}>
        <span class="suit" aria-hidden="true">${symbol(d.suit)}</span>${esc(SUIT_LABEL[d.suit] || d.suit)}</button>`;
    }).join("");
    out += `<span class="pick-label">Suit</span><div class="pick-row" role="group" aria-label="Suit">${suits}</div>`;
  }
  if (pick.suit === null) return out;

  const row = deck.find((d) => d.key === pick.suit);
  const ranks = row.ranks.map((rank) => {
    const n = choicesFor(choices, pick.suit, rank).length;
    const name = cardName({ rank, suit: row.suit });
    return `<button type="button" class="key ${suitColor(row.suit)}" data-rank="${esc(rank)}" aria-label="${esc(name)}"
      aria-pressed="${rank === pick.rank}" ${n ? "" : "disabled"}><span class="rank">${esc(rankShow(rank))}</span></button>`;
  }).join("");
  out += `<span class="pick-label">Card</span><div class="pick-row" role="group" aria-label="Card">${ranks}</div>`;
  if (!pick.rank) return out;

  const ways = choicesFor(choices, pick.suit, pick.rank).map((c) => {
    const caps = c.captures || [];
    const text = caps.length ? `Takes ${caps.map((x) => esc(rankShow(x.face.rank)) + symbol(x.face.suit)).join(" + ")}`
      : "Lays it on the table";
    return `<button type="button" class="key option" data-choice="${c.index}">
      <span>${text}${c.scopa ? `<span class="tag">SCOPA</span>` : ""}</span></button>`;
  }).join("");
  return out + `<span class="pick-label">How</span><div class="pick-row" role="group" aria-label="How">${ways}</div>`;
}

function finalHTML() {
  const f = state.table.final;
  let body = "";
  if (f && f.rows.length) {
    body = `<table class="final"><thead><tr>${f.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>
      ${f.rows.map((r) => `<tr><th scope="row">${esc(r[0])}</th>${r.slice(1).map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}
      </tbody></table>`;
  }
  return `<section class="ask" aria-label="Hand over"><h2>${esc(f ? f.summary : "Hand over")}</h2>${body}
    <div class="actions"><button type="button" class="pill ghost" data-restart>New hand</button></div></section>`;
}

function actionsHTML() {
  return `<div class="actions">
    <button type="button" class="pill ghost" data-undo ${state.history.length ? "" : "disabled"}>Undo</button>
    <button type="button" class="pill ghost" data-restart>New hand</button></div>`;
}

// ---------- the circle (gui.md) ----------

// User icon: blue = you and teammates, red = opponents, plus a shape cue that does
// not depend on color: a halo for teammates, horns for opponents.
function avatarSVG(team) {
  const ornament = team === "opp"
    ? '<path d="M21 17 L16 3 L28 13 Z M43 17 L48 3 L36 13 Z" class="horns"/>'
    : team === "ally" ? '<ellipse cx="32" cy="7" rx="12" ry="3.6" class="halo"/>' : "";
  return `<svg viewBox="0 0 64 64" aria-hidden="true" class="avatar ${team}">${ornament}
    <circle cx="32" cy="24" r="11" class="body"/><path d="M11 61 C11 45 21 39 32 39 C43 39 53 45 53 61 Z" class="body"/></svg>`;
}

const pileIcon = () => `<svg viewBox="0 0 64 64" aria-hidden="true" class="avatar pileicon">
  <rect x="14" y="10" width="30" height="42" rx="5" class="p1"/><rect x="20" y="14" width="30" height="42" rx="5" class="p2"/></svg>`;

// Seats on an ellipse: you at the bottom, the others in order of play
// (counterclockwise: the next player sits on your right).
function seatPosition(k, n) {
  const angle = (Math.PI / 2) - (2 * Math.PI * k) / n;
  return { x: 50 + 41 * Math.cos(angle), y: 50 + 39 * Math.sin(angle) };
}

// face-up cards and notes of a seat, compact: "A♦ 7♠ · soft 17", "Taken 12"
function seatLinesHTML(seat) {
  return seat.zones.map((z) => {
    if (z.show === "count") return z.count ? `<span class="line">${esc(z.label)} ${z.count}</span>` : "";
    const cards = z.known.map((c) => shortCard(c.face)).join(" ");
    if (!cards && !z.note) return "";
    return `<span class="line">${cards}${z.note ? ` <span class="note">${esc(z.note)}</span>` : ""}</span>`;
  }).join("");
}

function seatHTML(seat, k, n, compact) {
  const t = state.table;
  const pos = seatPosition(k, n);
  const focused = t.focus && seat.key === t.focus.key;
  const cls = `seat2 ${seat.team}${seat.turn ? " turn" : ""}${focused ? " focused" : ""}${compact && !focused ? " compact" : ""}`;
  const label = `${seat.name}${seat.hidden ? `: ${seat.hidden} face-down card${seat.hidden === 1 ? "" : "s"}` : ""}${seat.turn ? ", to play" : ""}${seat.dealer ? ", dealer" : ""}`;
  const lines = seat.team !== "me" && !(compact && !focused) ? seatLinesHTML(seat) : "";
  const hold = seat.hold ? `<span class="hold" title="exactly ${esc(seat.hold.fraction)}">${pctShort(seat.hold.percent)}</span>` : "";
  const inner = `<span class="disc">${avatarSVG(seat.team)}${seat.hidden ? `<span class="count">${seat.hidden}</span>` : ""}${
    seat.dealer ? '<span class="dealer" title="Dealer">D</span>' : ""}</span>
    <span class="name">${esc(seat.name)}${seat.turn ? ' <span class="to-play">to play</span>' : ""}</span>${lines}${hold}`;
  const style = `left:${pos.x.toFixed(2)}%;top:${pos.y.toFixed(2)}%`;
  return seat.target
    ? `<button type="button" class="${cls}" style="${style}" data-focus="${esc(seat.key)}" aria-pressed="${!!focused}"
        aria-label="${esc(label)} — show the odds">${inner}</button>`
    : `<div class="${cls}" style="${style}" role="img" aria-label="${esc(label)}">${inner}</div>`;
}

function pileHTML(pile) {
  const t = state.table;
  const focused = t.focus && pile.zone === t.focus.key;
  const content = pile.show === "count"
    ? `<span class="stack-count">${pile.count}</span>`
    : pile.known.length ? `<div class="row felt-cards">${pile.known.map((c) => cardHTML(c, { xs: true })).join("")}</div>`
      : `<span class="felt-empty">empty</span>`;
  const inner = `<span class="pile-label">${esc(pile.label)}</span>${content}`;
  return pile.target
    ? `<button type="button" class="pile${focused ? " focused" : ""}" data-focus="${esc(pile.zone)}" aria-pressed="${!!focused}"
        aria-label="${esc(pile.label)}: ${pile.count} cards — show the odds">${inner}</button>`
    : `<div class="pile">${inner}</div>`;
}

function centerHTML() {
  const t = state.table;
  let probe = "";
  if (t.card) {
    const f = t.card.face;
    probe = `<div class="probe"><span>Where is the <b>${shortCard(f)}</b>? ${t.card.where ? esc(t.card.where) : "% on each player"}</span>
      <button type="button" class="x" data-clear-card aria-label="Stop showing this card">✕</button></div>`;
  }
  return `<div class="felt2">${probe}<div class="piles">${t.piles.map(pileHTML).join("")}</div></div>`;
}

function circleHTML() {
  const seats = state.table.seats;
  const n = seats.length < 3 ? 4 : seats.length;  // 2 seats: face to face, room on the sides
  const step = seats.length === 2 ? 2 : 1;
  const compact = seats.length > 6;                // many players: only the focused seat shows details
  return `<section class="ring" aria-label="Table">${centerHTML()}${
    seats.map((s, k) => seatHTML(s, k * step, n, compact)).join("")}</section>`;
}

// your own seat, readable: cards drawn, one row per zone, with notes
function mineHTML() {
  const me = state.table.seats.find((s) => s.team === "me");
  const shown = me.zones.filter((z) => z.show === "cards" && (z.count || z.zone === me.zones[0].zone));
  const rows = shown.map((z) => `
    <div class="mine-row"><div class="row hand">${z.known.map((c) => cardHTML(c, { sm: true })).join("") || '<div class="empty"></div>'}</div>
      <span class="mine-label">${shown.length > 1 ? esc(z.label) : "Your hand"}${z.note ? ` <b>${esc(z.note)}</b>` : ""}</span></div>`).join("");
  const counts = me.zones.filter((z) => z.show === "count").map((z) => `<span class="chip">${esc(z.label)}: ${z.count}</span>`).join("");
  return `<section class="panel panel-me mine" aria-label="Your cards">${rows}${counts ? `<div class="chips">${counts}</div>` : ""}</section>`;
}

// ---------- the odds of the focused player / pile ----------

function focusHTML() {
  const t = state.table;
  const f = t.focus;
  if (!f) return `<h2>The odds</h2><p class="panel-sub">Nothing hidden right now.</p>${lensHTML()}`;
  const switcher = t.targets.length > 1 ? `<div class="who-row" role="group" aria-label="Show the odds of">${
    t.targets.map((x) => `<button type="button" class="who ${x.team}" data-focus="${esc(x.key)}"
      aria-pressed="${x.key === f.key}">${x.team === "pile" ? pileIcon() : avatarSVG(x.team)}<span>${esc(x.short)}</span></button>`).join("")}</div>` : "";
  const follow = f.auto ? `<span class="chip">follows the turn</span>`
    : `<button type="button" class="pill ghost small" data-follow>Follow the turn</button>`;
  const questions = f.questions.length ? `<div class="qs">${f.questions.map((q) => `<div class="qrow" title="exactly ${esc(q.fraction)}">
      <span class="ql">${esc(q.label)}</span><span class="qv">${pct(q.percent)}</span>
      <div class="qbar"><span style="width:${Math.min(100, q.percent).toFixed(2)}%"></span></div></div>`).join("")}</div>` : "";
  const lenses = [["cards", "Every card"], ...(f.ranks.length ? [["ranks", "By rank"]] : []), ["history", "History"]];
  if (!lenses.some(([id]) => id === view.lens)) view.lens = "cards";
  const tabs = lenses.map(([id, label]) =>
    `<button type="button" role="tab" class="lens" data-lens="${id}" aria-selected="${view.lens === id}">${label}</button>`).join("");
  return `<div class="focus-head"><h2>Odds for ${esc(f.name)}</h2>${follow}</div>${switcher}${questions}
    <div class="lenses" role="tablist">${tabs}</div><div class="lens-body">${lensHTML()}</div>`;
}

function lensHTML() {
  const f = state.table.focus;
  if (!f || view.lens === "history") {
    return `<ol class="history">${state.history.slice().reverse().map((h) => `<li>${esc(h)}</li>`).join("")}</ol>`;
  }
  const what = f.reading === "next" ? "the next card" : `${f.name} holds it`;
  if (view.lens === "ranks") {
    return `<div class="ranks" role="table" aria-label="By rank">
      <div class="rrow r4 head" role="row"><span role="columnheader">Rank</span><span role="columnheader">Unseen</span>
        <span role="columnheader">${f.reading === "next" ? "Next card" : "At least one"}</span><span role="columnheader">Expected</span></div>
      ${f.ranks.map((r) => `<div class="rrow r4" role="row"><b role="cell">${esc(rankShow(r.rank))}</b><span role="cell">${r.unseen}</span>
        <span role="cell" class="pf">${r.unseen ? pct(r.percent) : "—"}</span><span role="cell">${r.unseen ? r.expected.toFixed(2) : "—"}</span></div>`).join("")}
    </div><p class="panel-sub" style="margin:0">Exact over ${esc(f.worlds)} possible world${f.worlds === "1" ? "" : "s"}</p>`;
  }
  const cols = Math.max(...f.cards.map((r) => r.cells.length));
  const rows = f.cards.map((r) => `<div class="trow" style="grid-template-columns:${r.suit ? "80px " : ""}repeat(${cols}, minmax(30px, 1fr))">${
    r.suit ? `<span class="s ${suitColor(r.suit)}">${symbol(r.suit)} ${esc(SUIT_LABEL[r.suit] || r.suit)}</span>` : ""}${
    r.cells.map((c) => {
      const key = `${suitKey(r.suit)}/${c.rank}`;
      const name = cardName({ rank: c.rank, suit: r.suit });
      const many = c.copies > 1 ? ` · ${c.unseen} of ${c.copies} unseen` : "";
      const title = `${name}: ${c.status ? c.status : `P = ${c.fraction}`}${many} — click to see it on every player`;
      return `<button type="button" class="cell ${c.kind ? "k-" + c.kind : ""}" data-card="${esc(key)}" aria-pressed="${view.card === key}"
        title="${esc(title)}"><b>${esc(rankShow(c.rank))}</b><span>${c.status ? esc(c.status) : pctShort(c.p)}</span>${
        c.copies > 1 ? `<i>×${c.unseen}</i>` : ""}</button>`;
    }).join("")}</div>`).join("");
  return `<p class="panel-sub" style="margin:0">% = chance ${esc(what)} · exact over ${esc(f.worlds)} possible world${f.worlds === "1" ? "" : "s"} · click a card to see it on every player</p>
    <div class="tracker">${rows}</div>`;
}

// ---------- pages ----------

function renderTable() {
  const t = state.table;
  setBand(t.band[0], t.band[1]);
  return `<main class="main">${circleHTML()}${askHTML()}${mineHTML()}${actionsHTML()}</main>
    <aside class="side" aria-label="Odds">${focusHTML()}</aside>`;
}

function renderStart() {
  setBand("Them", "Us");
  const games = state.games.map((g) => `<div class="game">
      <h2>${esc(g.title)}</h2><p>${esc(g.question)}</p>
      <div class="actions">${g.setups.map((s) => `<button type="button" class="pill ${s.color}" data-game="${esc(g.id)}" data-setup="${s.value}">${esc(s.label)}</button>`).join("")}</div>
    </div>`).join("");
  return `<section class="start"><h1>New hand</h1>
    <p>Play a real game and record what you see. JOKER tells you, exactly, what the cards still allow.</p>
    <div class="games">${games}</div></section>`;
}

function render() {
  const app = document.getElementById("app");
  state.trump = state.session ? state.table.highlight_suit : null;
  app.innerHTML = state.session ? renderTable() : renderStart();
  app.classList.toggle("wide-side", Boolean(state.session));
  const warn = document.getElementById("warnings");
  const warnings = state.warnings || [];
  warn.hidden = warnings.length === 0;
  warn.textContent = warnings.join(" · ");
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("button");
  if (!el || el.disabled) return;
  if (el.dataset.choice !== undefined) api("/api/choose", { index: Number(el.dataset.choice) });
  else if (el.dataset.suit !== undefined) { pick.suit = el.dataset.suit; pick.rank = null; render(); }
  else if (el.dataset.rank !== undefined) {
    const ways = choicesFor(state.pending.choices, pick.suit, el.dataset.rank);
    if (ways.length === 1) api("/api/choose", { index: ways[0].index });
    else { pick.rank = el.dataset.rank; render(); }
  }
  else if (el.dataset.focus !== undefined) { view.focus = el.dataset.focus; api("/api/view", {}); }
  else if (el.dataset.follow !== undefined) { view.focus = null; api("/api/view", {}); }
  else if (el.dataset.card !== undefined) { view.card = view.card === el.dataset.card ? null : el.dataset.card; api("/api/view", {}); }
  else if (el.dataset.clearCard !== undefined) { view.card = null; api("/api/view", {}); }
  else if (el.dataset.lens !== undefined) { view.lens = el.dataset.lens; render(); }
  else if (el.dataset.game !== undefined) {
    view.focus = view.card = null; pick.suit = null;
    api("/api/new", { game: el.dataset.game, setup: Number(el.dataset.setup) });
  }
  else if (el.dataset.undo !== undefined) api("/api/undo", {});
  else if (el.dataset.restart !== undefined) { state = { session: false, games: state.games }; render(); }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && view.card && state && state.session) { view.card = null; api("/api/view", {}); }
});

api("/api/state");
