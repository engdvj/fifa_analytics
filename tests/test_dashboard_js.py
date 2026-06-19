import re
import json
import shutil
import subprocess

import pytest


def test_dashboard_embedded_javascript_node_check_and_stub_dom(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node nao esta disponivel")

    html_path = "reports/tournament/ranking_race.html"
    try:
        html = open(html_path, encoding="utf-8").read()
    except FileNotFoundError:
        pytest.skip("dashboard ainda nao foi gerado")

    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "dashboard sem bloco <script>"

    stub = r"""
function makeEl() {
  const el = {
    style: {}, dataset: {}, children: [], className: "", id: "",
    value: "", checked: false, disabled: false, innerHTML: "", textContent: "",
    clientWidth: 800, clientHeight: 600, offsetWidth: 800, offsetHeight: 40,
    scrollLeft: 0,
    classList: { add(){}, remove(){}, toggle(){ return false; }, contains(){ return false; } },
    appendChild(c){ this.children.push(c); return c; },
    prepend(c){ this.children.unshift(c); return c; },
    removeChild(c){ this.children = this.children.filter(x => x !== c); return c; },
    replaceChildren(...cs){ this.children = cs; },
    insertBefore(c){ this.children.push(c); return c; },
    addEventListener(){}, removeEventListener(){},
    setAttribute(k, v){ this[k] = v; }, getAttribute(k){ return this[k] || null; },
    removeAttribute(k){ delete this[k]; },
    querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    closest(){ return null; }, focus(){}, blur(){}, click(){}, scrollIntoView(){},
    getBoundingClientRect(){ return {left: 0, top: 0, width: 800, height: 40, right: 800, bottom: 40}; },
  };
  return new Proxy(el, {
    get(t, p) {
      if (p in t) return t[p];
      if (p === "options") return [];
      if (p === "parentElement" || p === "parentNode") return makeEl();
      if (typeof p === "symbol") return undefined;
      return undefined;
    },
    set(t, p, v) { t[p] = v; return true; },
  });
}
const nodes = {};
global.document = {
  body: makeEl(), documentElement: makeEl(),
  getElementById(id){ return nodes[id] ||= makeEl(); },
  createElement(){ return makeEl(); },
  createTextNode(t){ const e = makeEl(); e.textContent = t; return e; },
  querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
  addEventListener(){}, removeEventListener(){},
};
global.window = {
  innerWidth: 1280, innerHeight: 720, location: {hash: ""},
  addEventListener(){}, removeEventListener(){}, getComputedStyle(){ return {}; },
  requestAnimationFrame(fn){ return setTimeout(fn, 0); },
  cancelAnimationFrame(id){ clearTimeout(id); },
};
global.requestAnimationFrame = window.requestAnimationFrame;
global.cancelAnimationFrame = window.cancelAnimationFrame;
global.localStorage = { getItem(){ return null; }, setItem(){}, removeItem(){} };
global.navigator = {userAgent: "node"};
global.ResizeObserver = class { observe(){} unobserve(){} disconnect(){} };
global.IntersectionObserver = class { observe(){} unobserve(){} disconnect(){} };
"""
    assertions = r"""
const assert = require("assert");
trajectoryAxis = "team";
currentJogo = 9;
const alignedAtGermanyDebut = trajectorySeriesByTeam(["Alemanha", "Tchéquia"], "score_geral", "desc");
const germanyTeamSeries = alignedAtGermanyDebut["Alemanha"];
const czechTeamSeries = alignedAtGermanyDebut["Tchéquia"];
assert.strictEqual(germanyTeamSeries.length, 1);
assert.strictEqual(czechTeamSeries.length, 1);
assert.strictEqual(germanyTeamSeries[0].teamOrder, 1);
assert.strictEqual(czechTeamSeries[0].teamOrder, 1);
assert.strictEqual(germanyTeamSeries[0].jogo, 9);
assert.strictEqual(czechTeamSeries[0].jogo, 9);

currentJogo = lastJogo();
const czechSoloTeamSeries = trajectorySeries("Tchéquia", "score_geral", "desc");
assert.strictEqual(czechSoloTeamSeries.length, 2);
assert.strictEqual(czechSoloTeamSeries[0].teamOrder, 1);
assert.strictEqual(czechSoloTeamSeries[0].jogo, 2);
assert.strictEqual(czechSoloTeamSeries[1].teamOrder, 2);
assert.strictEqual(czechSoloTeamSeries[1].jogo, 25);
assert.strictEqual(czechSoloTeamSeries[0].total, 4);
assert.strictEqual(czechSoloTeamSeries[1].total, 48);

const southAfricaSoloSeries = trajectorySeries("África do Sul", "score_geral", "desc");
assert.strictEqual(southAfricaSoloSeries.length, 2);
assert.strictEqual(southAfricaSoloSeries[0].teamOrder, 1);
assert.strictEqual(southAfricaSoloSeries[1].teamOrder, 2);

currentJogo = 24;
const comparedTeams = ["Alemanha", "Tchéquia", "África do Sul", "Haiti"];
let comparedSeries = trajectorySeriesByTeam(comparedTeams, "score_geral", "desc");
comparedTeams.forEach(team => {
  assert.strictEqual(comparedSeries[team][0].teamOrder, 1);
  assert.strictEqual(comparedSeries[team][0].jogo, 9);
  assert.strictEqual(comparedSeries[team][0].total, 18);
});

currentJogo = lastJogo();
const comparedLatest = trajectorySeriesByTeam(["África do Sul", "Alemanha"], "score_geral", "desc");
assert.strictEqual(comparedLatest["África do Sul"].length, 1);
assert.strictEqual(comparedLatest["Alemanha"].length, 1);
assert.strictEqual(comparedLatest["África do Sul"][0].jogo, 9);

currentJogo = 27;
const swissCanada = trajectorySeriesByTeam(["Suíça", "Canadá"], "score_geral", "desc");
assert.deepStrictEqual(swissCanada["Suíça"].map(p => p.teamOrder), [1, 2]);
assert.deepStrictEqual(swissCanada["Canadá"].map(p => p.teamOrder), [1, 2]);
assert.strictEqual(swissCanada["Suíça"][1].jogo, 27);
assert.strictEqual(swissCanada["Canadá"][1].jogo, 27);

activeTab = "players";
currentJogo = lastJogo();
document.getElementById("teamSearch").value = "";
selectedTeam = "Noruega";
renderPlayersGrid();
assert(nodes.playersGrid.innerHTML.includes("Erling Haaland"));
assert(!nodes.playersGrid.innerHTML.includes("Lionel Messi"));
assert(nodes.teamsCount.textContent.includes("Noruega"));

trajectoryTeams = ["Noruega", "Alemanha"];
selectedTeam = "Alemanha";
renderPlayersGrid();
assert(nodes.playersGrid.innerHTML.includes("Erling Haaland"));
assert(nodes.playersGrid.innerHTML.includes("Kai Havertz"));
assert(!nodes.playersGrid.innerHTML.includes("Lionel Messi"));
assert(nodes.teamsCount.textContent.includes("2 seleções"));

activeTab = "teams";
renderTeamsGrid();
assert(nodes.teamsGrid.innerHTML.includes("Noruega"));
assert(nodes.teamsGrid.innerHTML.includes("Alemanha"));
assert(!nodes.teamsGrid.innerHTML.includes("Argentina"));

const australiaGame = TEAMS_DETAIL["Austrália"].jogos.find(g => g.match_id === "copa_2026_jogo_006");
const aiden = australiaGame.pitch.find(p => p.name === "Aiden O'Neill");
const aidenCard = _playerCardHtml(aiden);
assert(aidenCard.includes("Criação"));
assert(aidenCard.includes("xA"));
assert(aidenCard.includes("Passes para chute"));
assert(aidenCard.includes("Controle"));
assert(aidenCard.includes("Desarmes"));
assert(aidenCard.includes("Finalização"));
assert(aidenCard.includes("Disciplina"));

const germanyGame = TEAMS_DETAIL["Alemanha"].jogos.find(g => (g.pitch || []).some(p => p.name === "Manuel Neuer"));
assert(germanyGame);
const neuer = germanyGame.pitch.find(p => p.name === "Manuel Neuer");
const neuerCard = _playerCardHtml(neuer);
assert(neuerCard.includes("Ações do goleiro"));
assert(neuerCard.includes("xGP"));
assert(neuerCard.includes("Pênaltis defendidos"));
assert(neuerCard.includes("Bolas altas seguradas"));
assert(neuerCard.includes("Bolas socadas"));
assert(neuerCard.includes("Disciplina"));
assert(!neuerCard.includes("Ataque"));
assert(!neuerCard.includes("Criação"));

const vozinhaRoster = TEAMS_DETAIL["Cabo Verde"].players.find(p => p.name === "Vozinha");
assert(vozinhaRoster);
const vozinhaRosterCard = _rosterPlayerCardHtml(vozinhaRoster);
assert(vozinhaRosterCard.includes("Ações do goleiro"));
assert(vozinhaRosterCard.includes("xGP"));
assert(vozinhaRosterCard.includes("Bolas altas seguradas"));
assert(vozinhaRosterCard.includes("Bolas socadas"));
assert(vozinhaRosterCard.includes("Disciplina"));
assert(!vozinhaRosterCard.includes("Ataque"));
assert(!vozinhaRosterCard.includes("Avançadas"));

const richieRoster = TEAMS_DETAIL["Canadá"].players.find(p => p.name === "Richie Laryea");
assert(richieRoster);
const richieRosterCard = _rosterPlayerCardHtml(richieRoster);
assert(richieRosterCard.includes("Defesa"));
assert(richieRosterCard.includes("Cobertura"));
assert(richieRosterCard.includes("Disciplina"));
"""
    js_path = tmp_path / "dashboard.js"
    js_path.write_text(stub + "\n" + match.group(1) + "\n" + assertions, encoding="utf-8")

    subprocess.run([node, "--check", str(js_path)], check=True)
    subprocess.run([node, str(js_path)], check=True)


def test_dashboard_team_player_counts_follow_canonical_roster():
    html_path = "reports/tournament/ranking_race.html"
    try:
        html = open(html_path, encoding="utf-8").read()
    except FileNotFoundError:
        pytest.skip("dashboard ainda nao foi gerado")

    teams_match = re.search(r"const TEAMS_DETAIL = (.*?);\n", html)
    players_match = re.search(r"const PLAYER_DATA = (.*?);\n", html)
    assert teams_match, "dashboard sem TEAMS_DETAIL"
    assert players_match, "dashboard sem PLAYER_DATA"

    teams_detail = json.loads(teams_match.group(1))
    player_data = json.loads(players_match.group(1))
    latest_snapshot = str(max(map(int, player_data)))

    for team, detail in teams_detail.items():
        roster_count = detail.get("roster_count") or 0
        detail_players = [p for p in detail.get("players", []) if p.get("in_roster") is not False]
        snapshot_players = [p for p in player_data[latest_snapshot] if p["team"] == team]

        assert len(detail_players) == roster_count, team
        assert len(snapshot_players) == roster_count, team
