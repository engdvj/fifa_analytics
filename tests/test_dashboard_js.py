import re
import json
import shutil
import subprocess

import pytest


def test_dashboard_embedded_javascript_node_check_and_stub_dom(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node nao esta disponivel")

    for html_path in ("frontend/public/ranking_race.html", "reports/tournament/ranking_race.html"):
        try:
            html = open(html_path, encoding="utf-8").read()
            break
        except FileNotFoundError:
            continue
    else:
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
// ambas já disputaram 2 jogos → série alinhada tem um ponto por ordem de jogo (1 e 2)
assert.strictEqual(comparedLatest["África do Sul"].length, 2);
assert.strictEqual(comparedLatest["Alemanha"].length, 2);
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

// Card do jogador no CAMPO (_playerCardHtml): seleciona por papel da posição
// dinamicamente (sem nomes fixos, que variam conforme os jogos processados).
let anyMid = null, anyGk = null;
for (const team of Object.keys(TEAMS_DETAIL)) {
  for (const g of (TEAMS_DETAIL[team].jogos || [])) {
    for (const p of (g.pitch || [])) {
      const role = _playerRoleFromPos(p.pos_code || p.pos);
      if (!anyMid && role === "meio" && p.stats) anyMid = p;
      if (!anyGk && role === "goleiro" && p.stats) anyGk = p;
    }
  }
}
assert(anyMid, "esperava um meio com stats no campo");
const midCard = _playerCardHtml(anyMid);
assert(midCard.includes("Criação"));
assert(midCard.includes("xA"));
assert(midCard.includes("Passes p/ chute"));
assert(midCard.includes("Controle"));
assert(midCard.includes("Desarmes"));
assert(midCard.includes("Finalização"));
assert(midCard.includes("Disciplina"));

assert(anyGk, "esperava um goleiro com stats no campo");
const gkCard = _playerCardHtml(anyGk);
assert(gkCard.includes("Ações do goleiro"));
assert(gkCard.includes("xGP"));
assert(gkCard.includes("Pênaltis def."));
assert(gkCard.includes("Bolas altas"));
assert(gkCard.includes("Socos"));
assert(gkCard.includes("Disciplina"));
assert(!gkCard.includes("Finalização"));
assert(!gkCard.includes("Criação"));

// Card do jogador no ELENCO (_rosterPlayerCardHtml): goleiro e defensor por grupo.
function _findRoster(group) {
  for (const team of Object.keys(TEAMS_DETAIL)) {
    const pl = (TEAMS_DETAIL[team].players || []).find(p => p.pos_group === group);
    if (pl) { modalTeam = team; return pl; }
  }
  return null;
}
const gkRoster = _findRoster("Goleiros");
assert(gkRoster, "esperava um goleiro no elenco");
const gkRosterCard = _rosterPlayerCardHtml(gkRoster);
assert(gkRosterCard.includes("Ações do goleiro"));
assert(gkRosterCard.includes("xGP"));
assert(gkRosterCard.includes("Bolas altas"));
assert(gkRosterCard.includes("Socos"));
assert(gkRosterCard.includes("Disciplina"));
assert(!gkRosterCard.includes("Finalização"));

const defRoster = _findRoster("Defensores");
assert(defRoster, "esperava um defensor no elenco");
const defRosterCard = _rosterPlayerCardHtml(defRoster);
assert(defRosterCard.includes("Defesa"));
assert(defRosterCard.includes("Cobertura"));
assert(defRosterCard.includes("Disciplina"));
"""
    js_path = tmp_path / "dashboard.js"
    js_path.write_text(stub + "\n" + match.group(1) + "\n" + assertions, encoding="utf-8")

    subprocess.run([node, "--check", str(js_path)], check=True)
    subprocess.run([node, str(js_path)], check=True)


def test_dashboard_team_player_counts_follow_canonical_roster():
    for html_path in ("frontend/public/ranking_race.html", "reports/tournament/ranking_race.html"):
        try:
            html = open(html_path, encoding="utf-8").read()
            break
        except FileNotFoundError:
            continue
    else:
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
