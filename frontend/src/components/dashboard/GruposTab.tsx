"use client";

import React from "react";
import { Match, TeamSnapshot } from "@/lib/api";
import Flag from "@/components/ui/Flag";
import { METRIC_OPTIONS } from "@/lib/metrics";
import { DefinitionBubble } from "@/components/DefinitionLink";
import FixedPager from "./FixedPager";

// Copa 2026: 12 grupos, avançam os 2 primeiros + os 8 melhores terceiros (32 no
// mata-mata). Cores da classificação espelham isso.
const QUALIFY_DIRECT = 2; // top 2 por grupo
const BEST_THIRDS = 8;

const METRIC_LABEL: Record<string, string> = {};
for (const g of METRIC_OPTIONS) for (const [k, l] of g.items) METRIC_LABEL[k] = l;

const METRIC_DEF_ID: Record<string, string> = {
  score_geral: "score_geral", score_resultado: "score_resultado", score_ataque: "score_ataque",
  score_defesa: "score_defesa", score_eficiencia: "score_eficiencia", score_controle: "score_controle",
  score_forca_relativa: "score_forca_relativa", score_disciplina: "score_disciplina",
  pontos: "pontos", aproveitamento: "aproveitamento", saldo_gols: "saldo_gols", elo_rating: "elo",
  xg_pj: "xg", chutes_no_alvo_pj: "chutes_no_alvo", threat_pj: "threat",
  posse: "posse", pitch_control: "pitch_control", final_third_control: "final_third_control",
  precisao_passes: "precisao_passes",
};
const PCT_FRAC = new Set(["posse", "aproveitamento"]);
function fmtMetric(v: number | null, metric: string): string {
  if (v == null) return "—";
  if (PCT_FRAC.has(metric)) return `${Math.round(v <= 1 ? v * 100 : v)}%`;
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(metric.startsWith("score") || metric === "elo_rating" ? 1 : 2);
}

function compactMetricLabel(label: string): string {
  return label
    .replace(/^Score\s+/i, "")
    .replace(/^Ranking\s+/i, "Rank ")
    .replace(/^Aproveitamento$/i, "Aprov.")
    .replace(/^Saldo de gols$/i, "Saldo");
}

type Form = "V" | "E" | "D";
interface Row {
  team: string;
  played: number; won: number; drawn: number; lost: number;
  gf: number; ga: number; gd: number; points: number;
  form: Form[];
  metricValue: number | null;
}
interface GroupTable {
  group: string;       // "Group A"
  label: string;       // "Grupo A"
  rows: Row[];         // já ordenado
  maxPlayed: number;   // jogos da rodada mais avançada (nº de slots da forma)
}

function groupLabel(g: string): string {
  return g.replace(/^Group\s+/i, "Grupo ");
}

interface Props {
  matches: Match[];
  snapshots: TeamSnapshot[];
  activeSnapshot: number;
  matchSnapshot: Map<string, number>;
  filters: { group: string; confed: string; stage: string };
  passesFilters: (team: string) => boolean;
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  metric: string;
  search?: string;
}

export default function GruposTab({
  matches, snapshots, activeSnapshot, matchSnapshot, filters, passesFilters,
  selectedTeams, onToggleTeam, metric, search = "",
}: Props) {
  const metricByTeam = React.useMemo(() => {
    const m = new Map<string, number | null>();
    for (const s of snapshots) {
      if (s.snapshot_jogo !== activeSnapshot) continue;
      const v = s[metric];
      m.set(s.team, typeof v === "number" ? v : null);
    }
    return m;
  }, [snapshots, activeSnapshot, metric]);

  const tables = React.useMemo<GroupTable[]>(() => {
    // jogos da fase de grupos com placar, ATÉ o snapshot selecionado (a tabela
    // "viaja no tempo" junto com o slider — só conta o que já tinha acontecido).
    const groupGames = matches.filter(
      (g) => g.group && g.status === "finalizado" && g.home_score != null && g.away_score != null
        && (matchSnapshot.get(g.match_id) ?? Infinity) <= activeSnapshot
    );
    const byGroup = new Map<string, Match[]>();
    for (const g of groupGames) {
      const arr = byGroup.get(g.group!) ?? [];
      arr.push(g);
      byGroup.set(g.group!, arr);
    }

    const out: GroupTable[] = [];
    for (const [group, games] of byGroup) {
      const teams = new Set<string>();
      games.forEach((g) => { if (g.home_team) teams.add(g.home_team); if (g.away_team) teams.add(g.away_team); });
      const rows: Row[] = [...teams].map((team) => {
        const ordered = games
          .filter((g) => g.home_team === team || g.away_team === team)
          .sort((a, b) => (a.date_utc ?? "").localeCompare(b.date_utc ?? ""));
        let won = 0, drawn = 0, lost = 0, gf = 0, ga = 0, points = 0;
        const form: Form[] = [];
        for (const g of ordered) {
          const home = g.home_team === team;
          const f = (home ? g.home_score : g.away_score) ?? 0;
          const a = (home ? g.away_score : g.home_score) ?? 0;
          gf += f; ga += a;
          if (f > a) { won++; points += 3; form.push("V"); }
          else if (f === a) { drawn++; points++; form.push("E"); }
          else { lost++; form.push("D"); }
        }
        return {
          team, played: ordered.length, won, drawn, lost, gf, ga,
          gd: gf - ga, points, form, metricValue: metricByTeam.get(team) ?? null,
        };
      });
      rows.sort((a, b) =>
        b.points - a.points || b.gd - a.gd || b.gf - a.gf || a.team.localeCompare(b.team, "pt-BR")
      );
      const maxPlayed = rows.reduce((mx, r) => Math.max(mx, r.played), 0);
      out.push({ group, label: groupLabel(group), rows, maxPlayed });
    }
    out.sort((a, b) => a.group.localeCompare(b.group));
    return out;
  }, [matches, metricByTeam, matchSnapshot, activeSnapshot]);

  // 8 melhores terceiros (entre todos os grupos)
  const bestThirds = React.useMemo(() => {
    const thirds = tables
      .map((t) => t.rows[2])
      .filter(Boolean)
      .sort((a, b) => b!.points - a!.points || b!.gd - a!.gd || b!.gf - a!.gf);
    return new Set(thirds.slice(0, BEST_THIRDS).map((r) => r!.team));
  }, [tables]);

  const all = filters.group ? tables.filter((t) => t.group === filters.group) : tables;
  const q = search.trim().toLowerCase();
  const metricLabel = METRIC_LABEL[metric] ?? metric;
  const metricDef = METRIC_DEF_ID[metric];

  // 12 grupos → 6 por página (3×2), 2 páginas. Com filtro de grupo, vira página única.
  const PER_PAGE = 6;
  const [page, setPage] = React.useState(0);
  const pageCount = Math.max(1, Math.ceil(all.length / PER_PAGE));
  const safePage = Math.min(page, pageCount - 1);
  const shown = all.slice(safePage * PER_PAGE, safePage * PER_PAGE + PER_PAGE);

  if (all.length === 0) {
    return <p style={{ color: "#8b949e", fontSize: 13 }}>Sem jogos de fase de grupos com esse filtro.</p>;
  }

  return (
    <div className="v2-groups-table-tab" style={{ paddingBottom: pageCount > 1 ? 56 : 0 }}>
      <Legend />
      <div className="v2-groups-grid">
        {shown.map((t) => (
          <section key={t.group} className="v2-group-card">
            <header style={{ padding: "11px 16px", borderBottom: "1px solid #21262d", fontSize: 14, fontWeight: 800, color: "#f0f6fc" }}>
              {t.label}
            </header>
            <div className="v2-group-table-wrap">
            <table className="v2-group-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr style={{ color: "#8b949e", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.03em" }}>
                  <Th w={26} align="center">#</Th>
                  <Th w={9999}>Seleção</Th>
                  <Th w={26} align="right" title="Jogos">J</Th>
                  <Th w={24} align="right" title="Vitórias">V</Th>
                  <Th w={24} align="right" title="Empates">E</Th>
                  <Th w={24} align="right" title="Derrotas">D</Th>
                  <Th w={28} align="right" title="Gols marcados">GM</Th>
                  <Th w={28} align="right" title="Gols sofridos">GS</Th>
                  <Th w={28} align="right" title="Saldo de gols">SG</Th>
                  <Th w={30} align="right" title="Pontos">Pts</Th>
                  <Th align="right" metric title={metricLabel}><span title={metricLabel}>{compactMetricLabel(metricLabel)}</span>{metricDef && <DefinitionBubble id={metricDef} size={11} />}</Th>
                  <Th w={62} align="center" title="Últimos resultados">Forma</Th>
                </tr>
              </thead>
              <tbody>
                {t.rows.map((r, i) => {
                  const pos = i + 1;
                  const qual = pos <= QUALIFY_DIRECT ? "direct" : pos === 3 && bestThirds.has(r.team) ? "third" : pos === 3 ? "third-maybe" : "out";
                  const selected = selectedTeams.includes(r.team);
                  const dim = !passesFilters(r.team) || (q && !r.team.toLowerCase().includes(q));
                  const bar = qual === "direct" ? "#2ea043" : qual === "third" ? "#3fb950" : qual === "third-maybe" ? "#d29922" : "transparent";
                  return (
                    <tr
                      key={r.team}
                      onClick={() => onToggleTeam(r.team)}
                      style={{
                        cursor: "pointer", borderTop: "1px solid #161b22",
                        background: selected ? "linear-gradient(90deg, rgba(88,166,255,0.14), transparent)" : "transparent",
                        opacity: dim ? 0.32 : 1,
                      }}
                    >
                      <Td align="center" style={{ position: "relative", color: "#8b949e", fontWeight: 700 }}>
                        <span style={{ position: "absolute", left: 0, top: 4, bottom: 4, width: 3, borderRadius: 2, background: bar }} />
                        {pos}
                      </Td>
                      <Td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, color: selected ? "#58a6ff" : "#e6edf3", fontWeight: selected ? 700 : 600 }}>
                          <Flag team={r.team} height={12} />
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.team}</span>
                        </span>
                      </Td>
                      <Td align="right" dim>{r.played}</Td>
                      <Td align="right">{r.won}</Td>
                      <Td align="right">{r.drawn}</Td>
                      <Td align="right">{r.lost}</Td>
                      <Td align="right" dim>{r.gf}</Td>
                      <Td align="right" dim>{r.ga}</Td>
                      <Td align="right" style={{ color: r.gd > 0 ? "#3fb950" : r.gd < 0 ? "#f85149" : "#8b949e" }}>
                        {r.gd > 0 ? `+${r.gd}` : r.gd}
                      </Td>
                      <Td align="right" style={{ fontWeight: 800, color: "#f0f6fc" }}>{r.points}</Td>
                      <Td align="right" metric style={{ fontWeight: 700, color: "#79c0ff" }}>{fmtMetric(r.metricValue, metric)}</Td>
                      <Td align="center"><FormDots form={r.form} slots={Math.max(1, t.maxPlayed)} /></Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </section>
        ))}
      </div>

      <FixedPager page={safePage} pageCount={pageCount} onPage={setPage} total={all.length} unit="grupos" />
    </div>
  );
}

function FormDots({ form, slots }: { form: Form[]; slots: number }) {
  const color: Record<Form, string> = { V: "#3fb950", E: "#8b949e", D: "#f85149" };
  return (
    <span style={{ display: "inline-flex", gap: 3, justifyContent: "center" }}>
      {Array.from({ length: slots }).map((_, i) => {
        const r = form[i];
        return r ? (
          <span key={i} title={r === "V" ? "Vitória" : r === "E" ? "Empate" : "Derrota"}
            style={{ width: 8, height: 8, borderRadius: "50%", background: color[r] }} />
        ) : (
          <span key={i} style={{ width: 8, height: 2, alignSelf: "center", background: "#30363d", borderRadius: 1 }} />
        );
      })}
    </span>
  );
}

function Legend() {
  const items: [string, string][] = [
    ["#2ea043", "Classificado (1º/2º)"],
    ["#3fb950", "Melhor 3º (classifica)"],
    ["#d29922", "3º em disputa"],
  ];
  return (
    <div className="v2-groups-legend">
      {items.map(([c, l]) => (
        <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: c }} /> {l}
        </span>
      ))}
      <span style={{ marginLeft: "auto" }}>Clique numa seleção para fixá-la nas outras abas.</span>
    </div>
  );
}

const thBase: React.CSSProperties = { padding: "7px 8px", borderBottom: "1px solid #21262d", fontWeight: 700, whiteSpace: "nowrap" };
function Th({ children, align = "left", w, metric, title }: { children?: React.ReactNode; align?: "left" | "right" | "center"; w?: number; metric?: boolean; title?: string }) {
  return <th className={metric ? "v2-group-table-metric" : undefined} title={title} style={{ ...thBase, textAlign: align, width: w, background: metric ? "#1f6feb12" : undefined, color: metric ? "#58a6ff" : undefined }}>{children}</th>;
}
function Td({ children, align = "left", dim, metric, style }: { children?: React.ReactNode; align?: "left" | "right" | "center"; dim?: boolean; metric?: boolean; style?: React.CSSProperties }) {
  return <td className={metric ? "v2-group-table-metric" : undefined} style={{ padding: "8px 8px", textAlign: align, whiteSpace: "nowrap", color: dim ? "#8b949e" : "#e6edf3", background: metric ? "#1f6feb0a" : undefined, ...style }}>{children}</td>;
}
