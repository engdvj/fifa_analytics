"use client";

import React from "react";
import { Insight, Match, MatchComparison, DescriptiveDigest } from "@/lib/api";
import { useInsights, useInsightNarrative, useMatchComparison, useDescriptive } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import { getKit } from "@/lib/teamUtils";

// As seis camadas de análise da plataforma. Só a Diagnóstica está implementada;
// as demais são o roteiro (cada uma vira uma sub-aba quando pronta).
// Descritiva é escopada no AGREGADO (panorama do torneio/rodada: totais, recordes,
// líderes, zebras) — não repete os números de um jogo, que a Diagnóstica já mostra.
const TIPOS: { id: string; label: string; pronto: boolean; hint: string }[] = [
  { id: "descritiva", label: "Descritiva", pronto: true, hint: "Panorama do torneio" },
  { id: "exploratoria", label: "Exploratória", pronto: false, hint: "Que padrões existem" },
  { id: "diagnostica", label: "Diagnóstica", pronto: true, hint: "Por que aconteceu" },
  { id: "preditiva", label: "Preditiva", pronto: false, hint: "O que vem" },
  { id: "prescritiva", label: "Prescritiva", pronto: false, hint: "O que fazer" },
  { id: "preventiva", label: "Preventiva", pronto: false, hint: "Que risco evitar" },
];

// Head-to-head: métricas na ordem de exibição (xG e perigo primeiro).
const METRICS: { key: string; label: string; fmt?: (v: number) => string }[] = [
  { key: "xg", label: "xG (perigo criado)", fmt: (v) => v.toFixed(2) },
  { key: "threat", label: "Ameaça (threat)", fmt: (v) => v.toFixed(2) },
  { key: "posse", label: "Posse de bola", fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "final_third_control", label: "Controle (terço final)", fmt: (v) => `${Math.round(v)}%` },
  { key: "chutes", label: "Finalizações" },
  { key: "chutes_no_alvo", label: "No alvo" },
  { key: "chutes_dentro_area", label: "Dentro da área" },
  { key: "passes", label: "Passes" },
  { key: "precisao_passes", label: "Precisão de passe", fmt: (v) => `${Math.round(v <= 1 ? v * 100 : v)}%` },
  { key: "defesas_goleiro", label: "Defesas do goleiro" },
  { key: "turnovers_forcados", label: "Roubadas de bola" },
  { key: "pressoes_defensivas", label: "Pressões defensivas" },
  { key: "faltas_cometidas", label: "Faltas" },
  { key: "amarelos", label: "Amarelos" },
  { key: "vermelhos", label: "Vermelhos" },
  { key: "escanteios", label: "Escanteios" },
  { key: "distancia_total_km", label: "Distância", fmt: (v) => `${v.toFixed(1)} km` },
  { key: "sprints", label: "Sprints" },
];

interface Props {
  matches: Match[];
  activeSnapshot: number;
  isAdmin: boolean;
}

export default function AnaliseTab({ matches, activeSnapshot, isAdmin }: Props) {
  const [tipo, setTipo] = React.useState("diagnostica");
  const isDiag = tipo === "diagnostica";
  const isDesc = tipo === "descritiva";
  const enabled = isAdmin && isDiag;
  const { insights, isLoading, error } = useInsights({ tipo, snapshot: activeSnapshot, enabled });
  const { narrative } = useInsightNarrative({ tipo, snapshot: activeSnapshot, enabled });
  const { digest, isLoading: digestLoading } = useDescriptive(activeSnapshot, isAdmin && isDesc);

  const game = React.useMemo(() => {
    const items = insights.filter((i) => i.snapshot === activeSnapshot);
    if (items.length === 0) return null;
    const matchId = items[0].match_id;
    return { matchId, match: matches.find((m) => m.match_id === matchId), items };
  }, [insights, activeSnapshot, matches]);

  if (!isAdmin) return <Aviso texto="Acesso restrito a administradores." />;

  const tipoAtual = TIPOS.find((t) => t.id === tipo);

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <nav style={{ display: "flex", gap: 4, flexWrap: "wrap", justifyContent: "center", marginBottom: 16 }}>
        {TIPOS.map((t) => (
          <button
            key={t.id}
            onClick={() => t.pronto && setTipo(t.id)}
            disabled={!t.pronto}
            title={t.pronto ? t.hint : `${t.hint} · em breve`}
            style={{ ...subTabStyle(t.id === tipo), opacity: t.pronto ? 1 : 0.45, cursor: t.pronto ? "pointer" : "not-allowed" }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {isDesc ? (
        digestLoading
          ? <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>
          : <DigestView digest={digest} />
      ) : isDiag ? (
        <>
          {error && <Aviso texto={`Erro ao carregar análise: ${String(error)}`} cor="var(--red)" />}
          {isLoading && <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>}
          {!isLoading && !error && !game && (
            <Aviso texto={`Sem análise para o snapshot ${activeSnapshot} — use o controle de tempo para escolher um jogo finalizado.`} />
          )}
          {game && (
            <GameReport
              match={game.match}
              matchId={game.matchId}
              items={game.items}
              narrative={narrative?.exists && narrative.snapshot === activeSnapshot ? narrative.paragraphs : []}
              tipoLabel={tipoAtual?.label ?? ""}
              enabled={enabled}
            />
          )}
        </>
      ) : (
        <Aviso texto="Em breve." />
      )}
    </div>
  );
}

function DigestView({ digest }: { digest?: DescriptiveDigest }) {
  if (!digest || !digest.totais) {
    return <Aviso texto="Sem panorama disponível ainda — rode uma coleta." />;
  }
  const t = digest.totais;
  const num = (v: number) => v.toFixed(2).replace(".", ",");
  const cards: [string, string | number][] = [
    ["Jogos", t.jogos],
    ["Gols", t.gols],
    ["Gols/jogo", num(t.gols_por_jogo)],
    ["xG/jogo", t.xg_por_jogo != null ? num(t.xg_por_jogo) : "—"],
    ["Decisivos", `${t.pct_decisivos}%`],
    ["Goleadas (3+)", t.goleadas],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: 0, lineHeight: 1.55, textAlign: "center" }}>
        <b style={{ color: "var(--text)" }}>Panorama — {digest.fase}</b> — o retrato da competição até aqui ({t.jogos} jogos); cresce conforme você avança no tempo.
      </p>

      {/* Manchete: cards de totais */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        {cards.map(([label, val]) => (
          <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 10, padding: "12px 14px", textAlign: "center" }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: "var(--accent)" }}>{val}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Tendência por rodada */}
      {digest.tendencia.length > 0 && <TendenciaTable rows={digest.tendencia} />}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
        <ListPanel titulo="Líderes da fase">
          {digest.lideres.map((l, i) => (
            <li key={i} style={rowStyle}>
              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{l.categoria}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, textAlign: "right" }}>
                <Flag team={l.team} height={13} />{l.team}
                <span style={{ color: "var(--accent)", fontWeight: 700, fontSize: 11.5 }}>{l.valor}</span>
              </span>
            </li>
          ))}
        </ListPanel>

        <ListPanel titulo="Atuações & recordes">
          {digest.recordes.map((r, i) => (
            <li key={i} style={{ ...rowStyle, display: "block" }}>
              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{r.label}</span>
              <div style={{ fontWeight: 600, fontSize: 13, marginTop: 2 }}>{r.valor}</div>
            </li>
          ))}
        </ListPanel>
      </div>

      {digest.zebras.length > 0 && (
        <ListPanel titulo="Surpresas — resultados contra o esperado">
          {digest.zebras.map((z, i) => (
            <li key={i} style={{ ...rowStyle, display: "block", borderLeft: "3px solid var(--red)", paddingLeft: 13 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{z.titulo}</span>
              <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}> — {z.nota}</span>
            </li>
          ))}
        </ListPanel>
      )}
    </div>
  );
}

function TendenciaTable({ rows }: { rows: DescriptiveDigest["tendencia"] }) {
  const cols: [string, (r: DescriptiveDigest["tendencia"][0]) => string | number][] = [
    ["Jogos", (r) => r.jogos],
    ["Gols/jogo", (r) => r.gols_por_jogo.toFixed(2).replace(".", ",")],
    ["xG médio", (r) => (r.xg_medio != null ? r.xg_medio.toFixed(2).replace(".", ",") : "—")],
    ["Empates", (r) => r.empates],
    ["Goleadas", (r) => r.goleadas],
  ];
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        Tendência por rodada
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ ...thStyle, textAlign: "left" }}>Rodada</th>
              {cols.map(([h]) => <th key={h} style={thStyle}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.rodada}>
                <td style={{ ...tdStyle, textAlign: "left", fontWeight: 600 }}>{r.rodada}</td>
                {cols.map(([h, f]) => <td key={h} style={tdStyle}>{f(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const thStyle: React.CSSProperties = { padding: "8px 12px", textAlign: "center", fontSize: 11, color: "var(--text-muted)", fontWeight: 600, borderBottom: "1px solid var(--surface)" };
const tdStyle: React.CSSProperties = { padding: "9px 12px", textAlign: "center", color: "var(--text)", borderBottom: "1px solid var(--surface)" };

const rowStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "9px 16px", borderTop: "1px solid var(--surface)", fontSize: 13,
};

function ListPanel({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        {titulo}
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{children}</ul>
    </section>
  );
}

function GameReport({ match, matchId, items, narrative, tipoLabel, enabled }: {
  match?: Match; matchId: string; items: Insight[]; narrative: string[]; tipoLabel: string; enabled: boolean;
}) {
  const { comparison } = useMatchComparison(matchId, enabled);

  const home = match?.home_team ?? "—";
  const away = match?.away_team ?? "—";
  const resumo = items.find((i) => i.achado_key === "resumo");
  const contraXg = items.find((i) => i.achado_key === "resultado_vs_xg");
  const prestigio = items.find((i) => i.achado_key === "vitoria_prestigio");

  const perTeam = (team: string, dir: Insight["direcao"]) =>
    items.filter((i) => i.team === team && i.direcao === dir && i.categoria !== "Veredito" && i.categoria !== "Contexto");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* ── HERO: placar + veredito ─────────────────────────────────────── */}
      <header style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 14, padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, justifyContent: "center" }}>
          <TeamSide team={home} align="right" />
          <div style={{ textAlign: "center", minWidth: 96 }}>
            <div style={{ fontSize: 30, fontWeight: 800, color: "var(--text)", lineHeight: 1 }}>
              {match?.home_score ?? "-"} <span style={{ color: "var(--text-muted)" }}>–</span> {match?.away_score ?? "-"}
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 8 }}>
              {match?.group && <Badge texto={match.group} />}
              {match?.stage && <Badge texto={match.stage} />}
            </div>
          </div>
          <TeamSide team={away} align="left" />
        </div>

        {resumo && (
          <p style={{ margin: "16px 0 0", textAlign: "center", fontSize: 14, color: "var(--text)", lineHeight: 1.5 }}>
            <b>{resumo.titulo.includes("—") ? resumo.titulo.split("—").slice(-1)[0].trim() : resumo.titulo}.</b>{" "}
            <span style={{ color: "var(--text-muted)" }}>{resumo.detalhe}</span>
          </p>
        )}
        {(contraXg || prestigio) && (
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginTop: 10 }}>
            {prestigio && <Callout cor="var(--green)" texto={prestigio.detalhe} />}
            {contraXg && <Callout cor="var(--red)" texto={contraXg.detalhe} />}
          </div>
        )}
      </header>

      {/* ── A HISTÓRIA DO JOGO (storytelling) ───────────────────────────── */}
      {narrative.length > 0 && (
        <section style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderLeft: "3px solid var(--accent)", borderRadius: 12, padding: "16px 20px" }}>
          <SectionLabel texto="A história do jogo" cor="var(--accent)" />
          {narrative.map((p, i) => (
            <p key={i} style={{ margin: i === 0 ? "8px 0 0" : "10px 0 0", fontSize: 13.5, lineHeight: 1.65, color: "var(--text)" }}>{p}</p>
          ))}
        </section>
      )}

      {/* ── POR SELEÇÃO: destaques e pontos fracos (2 colunas) ──────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
        <TeamColumn team={home} destaques={perTeam(home, "positivo")} fracos={perTeam(home, "negativo")} />
        <TeamColumn team={away} destaques={perTeam(away, "positivo")} fracos={perTeam(away, "negativo")} />
      </div>

      {/* ── NÚMEROS DO JOGO (head-to-head) ──────────────────────────────── */}
      {comparison && <ComparisonPanel comparison={comparison} home={home} away={away} />}

      <p style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center", margin: "2px 0 0", opacity: 0.7 }}>
        Análise {tipoLabel} · gerada dos dados oficiais da FIFA (xG, controle, finalização, goleiro, disciplina, físico).
      </p>
    </div>
  );
}

function TeamSide({ team, align }: { team: string; align: "left" | "right" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, justifyContent: align === "right" ? "flex-end" : "flex-start" }}>
      {align === "right" && <span style={{ fontWeight: 700, fontSize: 16, textAlign: "right" }}>{team}</span>}
      <Flag team={team} height={26} />
      {align === "left" && <span style={{ fontWeight: 700, fontSize: 16 }}>{team}</span>}
    </div>
  );
}

function TeamColumn({ team, destaques, fracos }: { team: string; destaques: Insight[]; fracos: Insight[] }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <Flag team={team} height={16} />
        <span style={{ fontWeight: 700, fontSize: 14 }}>{team}</span>
      </header>
      <FindingGroup titulo="Destaques" cor="var(--green)" simbolo="▲" items={destaques} />
      <FindingGroup titulo="Pontos fracos" cor="var(--red)" simbolo="▼" items={fracos} />
      {destaques.length === 0 && fracos.length === 0 && (
        <div style={{ padding: "16px", fontSize: 12.5, color: "var(--text-muted)", textAlign: "center" }}>
          Atuação sem destaques marcantes nos dados.
        </div>
      )}
    </section>
  );
}

function FindingGroup({ titulo, cor, simbolo, items }: { titulo: string; cor: string; simbolo: string; items: Insight[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 16px 4px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: cor }}>
        <span style={{ fontSize: 9 }}>{simbolo}</span> {titulo}
      </div>
      {items.map((i, idx) => (
        <div key={idx} style={{ padding: "6px 16px 10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <span style={{ fontSize: 9.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--text-muted)", background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 4, padding: "1px 6px" }}>
              {i.categoria}
            </span>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{i.titulo}</span>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--text-muted)", lineHeight: 1.45 }}>{i.detalhe}</div>
        </div>
      ))}
    </div>
  );
}

function ComparisonPanel({ comparison, home, away }: { comparison: MatchComparison; home: string; away: string }) {
  const rows = METRICS.filter((m) => comparison.home[m.key] != null || comparison.away[m.key] != null);
  if (rows.length === 0) return null;
  const homeColor = getKit(home).main;
  const awayColor = getKit(away).main;
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "12px 16px 4px" }}><SectionLabel texto="Números do jogo" cor="var(--text-muted)" /></div>
      {/* Cabeçalho com as cores dos times (faixa de identidade) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 16px 10px", fontSize: 13, fontWeight: 700, borderBottom: "1px solid var(--surface)" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: homeColor, border: "1px solid rgba(255,255,255,0.25)" }} />
          <Flag team={home} height={13} />{home}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
          {away}<Flag team={away} height={13} />
          <span style={{ width: 10, height: 10, borderRadius: 3, background: awayColor, border: "1px solid rgba(255,255,255,0.25)" }} />
        </span>
      </div>
      <div style={{ padding: "8px 0" }}>
        {rows.map((m) => (
          <MetricRow key={m.key} label={m.label} home={comparison.home[m.key] ?? null} away={comparison.away[m.key] ?? null}
            fmt={m.fmt} homeColor={homeColor} awayColor={awayColor} />
        ))}
      </div>
    </section>
  );
}

function MetricRow({ label, home, away, fmt, homeColor, awayColor }: {
  label: string; home: number | null; away: number | null; fmt?: (v: number) => string; homeColor: string; awayColor: string;
}) {
  const f = (v: number | null) => (v == null ? "–" : fmt ? fmt(v) : String(Math.round(v)));
  const h = home ?? 0, a = away ?? 0, total = h + a;
  const hPct = total > 0 ? (h / total) * 100 : 50;
  const homeLead = h > a, awayLead = a > h;
  return (
    <div style={{ padding: "7px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, marginBottom: 4 }}>
        <span style={{ fontWeight: homeLead ? 800 : 600, color: homeLead ? homeColor : "var(--text-muted)", minWidth: 60 }}>{f(home)}</span>
        <span style={{ color: "var(--text-muted)", fontSize: 11.5, textAlign: "center" }}>{label}</span>
        <span style={{ fontWeight: awayLead ? 800 : 600, color: awayLead ? awayColor : "var(--text-muted)", minWidth: 60, textAlign: "right" }}>{f(away)}</span>
      </div>
      {/* Barra divergente do centro: cada lado na cor do seu time */}
      <div style={{ display: "flex", alignItems: "center", height: 8, gap: 2 }}>
        <div style={{ flex: 1, display: "flex", justifyContent: "flex-end", height: "100%", background: "var(--surface2)", borderRadius: "4px 0 0 4px", overflow: "hidden" }}>
          <div style={{ width: `${hPct}%`, height: "100%", background: homeColor, opacity: homeLead ? 1 : 0.65, borderRadius: "4px 0 0 4px" }} />
        </div>
        <div style={{ flex: 1, display: "flex", justifyContent: "flex-start", height: "100%", background: "var(--surface2)", borderRadius: "0 4px 4px 0", overflow: "hidden" }}>
          <div style={{ width: `${100 - hPct}%`, height: "100%", background: awayColor, opacity: awayLead ? 1 : 0.65, borderRadius: "0 4px 4px 0" }} />
        </div>
      </div>
    </div>
  );
}

function Callout({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span style={{ fontSize: 12, color: "var(--text)", background: "var(--background)", border: `1px solid color-mix(in srgb, ${cor} 40%, var(--surface2))`, borderLeft: `3px solid ${cor}`, borderRadius: 6, padding: "5px 10px", maxWidth: 440, lineHeight: 1.4 }}>
      {texto}
    </span>
  );
}

function SectionLabel({ texto, cor }: { texto: string; cor: string }) {
  return <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: cor, fontWeight: 700 }}>{texto}</div>;
}

function Badge({ texto }: { texto: string }) {
  return (
    <span style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 5, padding: "2px 8px" }}>
      {texto}
    </span>
  );
}

function Aviso({ texto, cor = "var(--text-muted)" }: { texto: string; cor?: string }) {
  return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: cor }}>{texto}</div>;
}

// Mesmo visual das abas do dashboard (v2/page.tsx → tabStyle).
function subTabStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? "#1a2233" : "#161b22",
    border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
    color: active ? "#e6edf3" : "#8b949e",
    borderRadius: 6,
    padding: "5px 12px",
    fontSize: 13,
    fontFamily: "inherit",
  };
}
