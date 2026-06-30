"use client";

import React from "react";
import { Insight, Match, MatchComparison } from "@/lib/api";
import { useMatchComparison, useEliminations } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import { getKit, eliminatedStyle, ELIMINATED_BADGE } from "@/lib/teamUtils";

/**
 * Diagnóstico de UM jogo finalizado: placar + veredito, a história do jogo
 * (narrativa), destaques/problemas por seleção e o head-to-head de números.
 * Extraído da AnaliseTab para ser reusado pela aba "O Jogo" (JogoView).
 */

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

export default function GameReport({ match, matchId, items, narrative, tipoLabel, enabled }: {
  match?: Match; matchId: string; items: Insight[]; narrative: string[]; tipoLabel: string; enabled: boolean;
}) {
  const { comparison } = useMatchComparison(matchId, enabled);
  const { isEliminated } = useEliminations();

  const home = match?.home_team ?? "—";
  const away = match?.away_team ?? "—";
  const contraXg = items.find((i) => i.achado_key === "resultado_vs_xg");
  const prestigio = items.find((i) => i.achado_key === "vitoria_prestigio");

  const perTeam = (team: string, dir: Insight["direcao"]) =>
    items.filter((i) => i.team === team && i.direcao === dir && i.categoria !== "Veredito" && i.categoria !== "Contexto");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18, maxWidth: 1000, margin: "0 auto", width: "100%" }}>
      <header style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 14, padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, justifyContent: "center" }}>
          <TeamSide team={home} align="right" eliminated={isEliminated(home)} />
          <div style={{ textAlign: "center", minWidth: 96 }}>
            <div style={{ fontSize: 30, fontWeight: 800, color: "var(--text)", lineHeight: 1 }}>
              {match?.home_score ?? "-"} <span style={{ color: "var(--text-muted)" }}>–</span> {match?.away_score ?? "-"}
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 8 }}>
              {match?.group && <Badge texto={match.group} />}
              {match?.stage && <Badge texto={match.stage} />}
            </div>
          </div>
          <TeamSide team={away} align="left" eliminated={isEliminated(away)} />
        </div>

        {(contraXg || prestigio) && (
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginTop: 10 }}>
            {prestigio && <Callout cor="var(--green)" texto={prestigio.detalhe} />}
            {contraXg && <Callout cor="var(--red)" texto={contraXg.detalhe} />}
          </div>
        )}
      </header>

      {narrative.length > 0 && (
        <section style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderLeft: "3px solid var(--accent)", borderRadius: 12, padding: "16px 20px" }}>
          <SectionLabel texto="A história do jogo" cor="var(--accent)" />
          {narrative.map((p, i) => (
            <p key={i} style={{ margin: i === 0 ? "8px 0 0" : "10px 0 0", fontSize: 13.5, lineHeight: 1.65, color: "var(--text)" }}>{p}</p>
          ))}
        </section>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
        <TeamColumn team={home} match={match} destaques={perTeam(home, "positivo")} fracos={perTeam(home, "negativo")} />
        <TeamColumn team={away} match={match} destaques={perTeam(away, "positivo")} fracos={perTeam(away, "negativo")} />
      </div>

      {comparison && <ComparisonPanel comparison={comparison} home={home} away={away} />}

      <p style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center", margin: "2px 0 0", opacity: 0.7 }}>
        Análise {tipoLabel} · gerada dos dados oficiais da FIFA (xG, controle, finalização, goleiro, disciplina, físico).
      </p>
    </div>
  );
}

function TeamSide({ team, align, eliminated }: { team: string; align: "left" | "right"; eliminated?: boolean }) {
  const out = !!eliminated;
  const name = (
    <span style={{ fontWeight: 700, fontSize: 16, textAlign: align === "right" ? "right" : "left" }} title={out ? "Eliminada" : undefined}>
      {out && align === "left" && <span style={{ marginRight: 5 }}>{ELIMINATED_BADGE}</span>}
      {team}
      {out && align === "right" && <span style={{ marginLeft: 5 }}>{ELIMINATED_BADGE}</span>}
    </span>
  );
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, justifyContent: align === "right" ? "flex-end" : "flex-start", ...eliminatedStyle(out) }}>
      {align === "right" && name}
      <Flag team={team} height={26} />
      {align === "left" && name}
    </div>
  );
}

function TeamColumn({ team, match, destaques, fracos }: { team: string; match?: Match; destaques: Insight[]; fracos: Insight[] }) {
  const cleaned = cleanTeamFindings(team, match, destaques, fracos);
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <Flag team={team} height={16} />
        <span style={{ fontWeight: 700, fontSize: 14 }}>{team}</span>
      </header>
      <FindingGroup titulo="Funcionou" cor="var(--green)" simbolo="▲" items={cleaned.positivos} />
      <FindingGroup titulo="Problemas" cor="var(--red)" simbolo="▼" items={cleaned.negativos} />
      {cleaned.positivos.length === 0 && cleaned.negativos.length === 0 && (
        <div style={{ padding: "16px", fontSize: 12.5, color: "var(--text-muted)", textAlign: "center" }}>
          Atuação sem sinais fortes nos dados.
        </div>
      )}
    </section>
  );
}

function cleanTeamFindings(team: string, match: Match | undefined, positivos: Insight[], negativos: Insight[]) {
  const ctx = teamMatchContext(team, match);
  const lost = ctx != null && ctx.golsPro < ctx.golsContra;
  const heavyLoss = ctx != null && ctx.golsContra - ctx.golsPro >= 2;
  const concededMultiple = ctx != null && ctx.golsContra >= 2;
  const blockedPositive = (item: Insight) => {
    if (item.categoria === "Goleiro" && lost) return true;
    if (item.categoria === "Defesa" && (lost || concededMultiple)) return true;
    if (item.achado_key === "eficiente_sem_bola" && heavyLoss) return true;
    return false;
  };
  return {
    positivos: positivos.filter((item) => !blockedPositive(item)),
    negativos,
  };
}

function teamMatchContext(team: string, match?: Match) {
  if (!match || match.home_score == null || match.away_score == null) return null;
  if (match.home_team === team) return { golsPro: match.home_score, golsContra: match.away_score };
  if (match.away_team === team) return { golsPro: match.away_score, golsContra: match.home_score };
  return null;
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
