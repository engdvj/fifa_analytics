"use client";

import React from "react";
import { Match, TeamSnapshot } from "@/lib/api";
import { deriveTeams, TeamSummary, getKit, selectionColor } from "@/lib/teamUtils";
import Flag from "@/components/ui/Flag";
import TeamModal from "./TeamModal";
import { METRIC_OPTIONS } from "@/lib/metrics";
import { DefinitionBubble } from "@/components/DefinitionLink";

const PAGE_SIZE = 24;

// métrica do snapshot (chave de ordenação) → id de conceito. Só mapeia as que
// têm definição; demais ficam sem bolinha.
const METRIC_DEF_ID: Record<string, string> = {
  score_geral: "score_geral", score_resultado: "score_resultado", score_ataque: "score_ataque",
  score_defesa: "score_defesa", score_eficiencia: "score_eficiencia", score_controle: "score_controle",
  score_forca_relativa: "score_forca_relativa", score_disciplina: "score_disciplina",
  pontos: "pontos", aproveitamento: "aproveitamento", saldo_gols: "saldo_gols", elo_rating: "elo",
  gols_pj: "", xg_pj: "xg", chutes_no_alvo_pj: "chutes_no_alvo", threat_pj: "threat",
  posse: "posse", pitch_control: "pitch_control", final_third_control: "final_third_control",
  precisao_passes: "precisao_passes",
};
function metricDefId(metric: string): string | null {
  const id = METRIC_DEF_ID[metric];
  return id && id.length > 0 ? id : null;
}

const METRIC_LABEL: Record<string, string> = {};
for (const g of METRIC_OPTIONS) for (const [k, l] of g.items) METRIC_LABEL[k] = l;
const PCT_FRAC = new Set(["posse", "aproveitamento"]);
const LOWER_BETTER = new Set(["gols_contra", "gols_contra_pj"]);
function fmtMetric(v: number, metric: string): string {
  if (PCT_FRAC.has(metric)) return `${Math.round(v <= 1 ? v * 100 : v)}%`;
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(metric.startsWith("score") || metric === "elo_rating" ? 1 : 2);
}

interface Props {
  matches: Match[];
  snapshots: TeamSnapshot[];
  activeSnapshot: number;
  matchSnapshot: Map<string, number>;
  passesFilters: (team: string) => boolean;
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  metric: string;
  sortDir?: "desc" | "asc";
  search?: string;
}

interface Card {
  team: TeamSummary;
  value: number | null;     // valor da métrica escolhida
  label: string;            // rótulo da métrica
  metric: string;
  rank: number | null;      // posição na ordenação por métrica
  active: boolean;
}

function statsFromGames(name: string, games: Match[]) {
  let wins = 0, draws = 0, losses = 0, gf = 0, ga = 0, points = 0;
  for (const m of games) {
    const home = m.home_team === name;
    const f = home ? (m.home_score ?? 0) : (m.away_score ?? 0);
    const a = home ? (m.away_score ?? 0) : (m.home_score ?? 0);
    gf += f; ga += a;
    if (f > a) { wins++; points += 3; } else if (f === a) { draws++; points++; } else losses++;
  }
  return { wins, draws, losses, gf, ga, points, played: games.length };
}

export default function SelecoesTab({ matches, snapshots, activeSnapshot, matchSnapshot, passesFilters, selectedTeams, onToggleTeam, metric, sortDir = "desc", search = "" }: Props) {
  const [page, setPage] = React.useState(0);
  React.useEffect(() => { setPage(0); }, [search]);
  const [detail, setDetail] = React.useState<TeamSummary | null>(null);
  const metricLabel = METRIC_LABEL[metric] ?? "Score Geral";

  const rowByTeam = React.useMemo(() => {
    const m = new Map<string, TeamSnapshot>();
    for (const s of snapshots) {
      if (s.snapshot_jogo !== activeSnapshot) continue;
      m.set(s.team, s);
    }
    return m;
  }, [snapshots, activeSnapshot]);

  const playedUpTo = React.useCallback(
    (m: Match) => {
      const sn = matchSnapshot.get(m.match_id);
      return sn !== undefined && sn <= activeSnapshot && m.status === "finalizado";
    },
    [matchSnapshot, activeSnapshot]
  );

  const cards = React.useMemo<Card[]>(() => {
    const q = search.trim().toLowerCase();
    const asc = LOWER_BETTER.has(metric) !== (sortDir === "asc");
    const built = deriveTeams(matches)
      .filter((t) => passesFilters(t.name))
      .filter((t) => !q || t.name.toLowerCase().includes(q))
      .map((base) => {
        const gamesUpTo = base.games.filter(playedUpTo);
        const s = statsFromGames(base.name, gamesUpTo);
        const row = rowByTeam.get(base.name);
        const raw = row ? row[metric] : null;
        const value = typeof raw === "number" ? raw : null;
        const team: TeamSummary = { ...base, ...s, games: gamesUpTo };
        return { team, value, label: metricLabel, metric, rank: null as number | null, active: gamesUpTo.length > 0 && value != null };
      })
      .sort((a, b) => {
        if (a.active !== b.active) return a.active ? -1 : 1;
        if (a.active) return asc ? (a.value! - b.value!) : (b.value! - a.value!);
        return a.team.name.localeCompare(b.team.name, "pt-BR");
      });
    // posição (rank) na ordenação pela métrica, só p/ as ativas
    let r = 0;
    for (const c of built) if (c.active) c.rank = ++r;
    return built;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matches, search, rowByTeam, passesFilters, playedUpTo, metric, metricLabel, sortDir]);

  const pageCount = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageCards = cards.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        {selectedTeams.length > 0 && (
          <span style={{ color: "#8b949e", fontSize: 12 }}>{selectedTeams.length} selecionada(s) · clique pra comparar na Ranking Race</span>
        )}
        <span style={{ color: "#8b949e", fontSize: 12, marginLeft: "auto" }}>
          {cards.length} seleções · página {safePage + 1}/{pageCount}
        </span>
      </div>

      {cards.length === 0 ? (
        <p style={{ color: "#8b949e", fontSize: 13 }}>Nenhuma seleção encontrada com esses filtros.</p>
      ) : (
        // 6 por linha (24/página = 4 linhas). paddingBottom reserva espaço p/ a barra fixa.
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gap: 12, paddingBottom: 56 }}>
          {pageCards.map((c) => (
            <TeamCard
              key={c.team.name}
              card={c}
              selColor={selectionColor(c.team.name, selectedTeams)}
              onToggle={() => onToggleTeam(c.team.name)}
              onDetails={() => setDetail(c.team)}
            />
          ))}
        </div>
      )}

      {/* Barra de paginação FIXA embaixo */}
      {pageCount > 1 && (
        <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 40, background: "#0d1117ee", borderTop: "1px solid #21262d", backdropFilter: "blur(6px)", padding: "9px 16px", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <PageBtn disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>← Anterior</PageBtn>
          {Array.from({ length: pageCount }).map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i)}
              style={{ minWidth: 30, height: 30, padding: "0 6px", borderRadius: 6, fontSize: 12, cursor: "pointer", fontFamily: "inherit",
                background: i === safePage ? "#1f6feb" : "#161b22", color: i === safePage ? "#fff" : "#8b949e",
                border: `1px solid ${i === safePage ? "#1f6feb" : "#30363d"}` }}
            >{i + 1}</button>
          ))}
          <PageBtn disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>Próxima →</PageBtn>
          <span style={{ marginLeft: 12, color: "#8b949e", fontSize: 12 }}>{cards.length} seleções · pág. {safePage + 1}/{pageCount}</span>
        </div>
      )}

      {detail && <TeamModal team={detail} snapshot={activeSnapshot} onClose={() => setDetail(null)} />}
    </div>
  );
}

function PageBtn({ children, disabled, onClick }: { children: React.ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, color: disabled ? "#484f58" : "#e6edf3", padding: "6px 12px", fontSize: 12, cursor: disabled ? "default" : "pointer", fontFamily: "inherit" }}>{children}</button>
  );
}

function TeamCard({ card, selColor, onToggle, onDetails }: { card: Card; selColor: string | null; onToggle: () => void; onDetails: () => void }) {
  const { team, value, label, metric, rank, active } = card;
  const [hover, setHover] = React.useState(false);
  const kit = getKit(team.name);
  const gd = team.gf - team.ga;
  const selected = selColor != null;
  const DASH = "—";

  return (
    <div
      onClick={onToggle}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title="Clique para selecionar (comparar na Ranking Race)"
      style={{
        position: "relative",
        background: "#0d1117",
        border: `2px solid ${selected ? selColor! : hover ? kit.main + "88" : "#21262d"}`,
        borderRadius: 13, cursor: "pointer", overflow: "hidden",
        transition: "border-color 0.15s, box-shadow 0.15s, opacity 0.15s",
        boxShadow: selected ? `0 0 0 1px ${selColor!}, 0 8px 26px ${selColor!}33` : hover ? `0 8px 26px ${kit.main}22` : "none",
        opacity: active ? 1 : 0.55,
      }}
    >
      {/* topo: bandeira + nome + botão Detalhes em destaque */}
      <div style={{ background: active ? `linear-gradient(135deg, ${kit.main}33, ${kit.main}11)` : "#11151c", borderBottom: `1px solid ${active ? kit.main + "33" : "#21262d"}`, padding: "13px 15px", display: "flex", alignItems: "center", gap: 12 }}>
        <Flag team={team.name} height={30} style={{ filter: active ? "none" : "grayscale(0.5)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ color: "#e6edf3", fontWeight: 700, fontSize: 15.5, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{team.name}</p>
          <p style={{ color: "#8b949e", fontSize: 11.5, margin: "3px 0 0" }}>{team.confederation}{team.group ? ` · ${team.group}` : ""}</p>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDetails(); }}
          title="Ver detalhes da seleção"
          style={{ flexShrink: 0, display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 11px", borderRadius: 7, background: "#10213a", border: "1px solid #1f6feb", color: "#79c0ff", cursor: "pointer", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#16335c"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "#10213a"; }}
        >Detalhes ⤢</button>
      </div>

      {/* nota da métrica escolhida */}
      <div style={{ padding: "11px 15px", borderBottom: "1px solid #21262d", display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 26, fontWeight: 800, color: active ? "#58a6ff" : "#56606b", lineHeight: 1 }}>{active && value != null ? fmtMetric(value, metric) : DASH}</span>
        <span style={{ fontSize: 11, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.03em", display: "inline-flex", alignItems: "center", gap: 3 }} title={label}>
          {active && rank != null ? `#${rank} · ` : ""}{label}
          {metricDefId(metric) && <DefinitionBubble id={metricDefId(metric)!} size={11} />}
        </span>
      </div>

      {/* corpo */}
      <div style={{ padding: "12px 15px" }}>
        {active ? (
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            {([["V", team.wins, "#3fb950"], ["E", team.draws, "#d29922"], ["D", team.losses, "#f85149"]] as const).map(([l, v, c]) => (
              <div key={l} style={{ textAlign: "center", flex: 1 }}>
                <div style={{ fontSize: 17, fontWeight: 700, color: c }}>{v}</div>
                <div style={{ fontSize: 10.5, color: "#8b949e" }}>{l}</div>
              </div>
            ))}
            <div style={{ width: 1, background: "#21262d", alignSelf: "stretch", margin: "2px 0" }} />
            <div style={{ textAlign: "center", flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#e6edf3" }}>{team.gf}:{team.ga}</div>
              <div style={{ fontSize: 10.5, color: "#8b949e" }}>Gols</div>
            </div>
            <div style={{ textAlign: "center", flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: gd > 0 ? "#3fb950" : gd < 0 ? "#f85149" : "#8b949e" }}>{gd > 0 ? `+${gd}` : gd}</div>
              <div style={{ fontSize: 10.5, color: "#8b949e" }}>Saldo<DefinitionBubble id="saldo_gols" size={11} /></div>
            </div>
          </div>
        ) : (
          <p style={{ color: "#56606b", fontSize: 12.5, textAlign: "center", padding: "8px 0" }}>Ainda não jogou {DASH} sem dados neste momento</p>
        )}
      </div>

      {/* faixa de seleção (cor) */}
      {selected && <div style={{ height: 4, background: selColor! }} />}
    </div>
  );
}
