"use client";

import React from "react";
import { Match, PredictiveData, TeamSnapshot } from "@/lib/api";
import { usePredictive, useTeamSnapshots } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import { STYLE_COLOR, styleName } from "@/lib/styleMeta";

type Prediction = PredictiveData["matches"][number];
type ActionTone = "attack" | "defense" | "control" | "setpiece" | "risk";

interface Action {
  tone: ActionTone;
  title: string;
  why: string;
  doThis: string;
  metric: string;
  urgency: "alta" | "media" | "baixa";
}

interface Props {
  snapshot: number;
  enabled: boolean;
  matches: Match[];
  selectedTeams: string[];
}

const TONE: Record<ActionTone, { label: string; color: string }> = {
  attack: { label: "Atacar", color: "#58a6ff" },
  defense: { label: "Proteger", color: "#3fb950" },
  control: { label: "Controlar", color: "#a371f7" },
  setpiece: { label: "Bola parada", color: "#f0883e" },
  risk: { label: "Risco", color: "#d29922" },
};

export default function PrescritivaView({ snapshot, enabled, matches, selectedTeams }: Props) {
  const { snapshots: rows, isLoading: snapshotsLoading, error: snapshotsError } = useTeamSnapshots(snapshot);
  const { predictive, isLoading: predictiveLoading } = usePredictive({ snapshot, enabled });
  const prediction = predictive?.matches?.[0] ?? null;
  const rowByTeam = React.useMemo(() => new Map(rows.map((row) => [row.team, row])), [rows]);
  const focusRows = selectedTeams
    .map((team) => rowByTeam.get(team))
    .filter((row): row is TeamSnapshot => !!row);
  const currentMatch = React.useMemo(() => matchForSnapshot(matches, snapshot), [matches, snapshot]);

  if (snapshotsLoading || predictiveLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  }
  if (snapshotsError) {
    return <Aviso texto={`Erro ao carregar prescrições: ${String(snapshotsError)}`} />;
  }
  if (!focusRows.length) {
    return <Aviso texto="Escolha uma ou duas seleções para montar o plano de ação." />;
  }

  const opponentOf = (team: string) => {
    if (prediction && (prediction.home_team === team || prediction.away_team === team)) {
      const opp = prediction.home_team === team ? prediction.away_team : prediction.home_team;
      return rowByTeam.get(opp) ?? null;
    }
    if (focusRows.length === 2) {
      return focusRows.find((row) => row.team !== team) ?? null;
    }
    if (currentMatch && (currentMatch.home_team === team || currentMatch.away_team === team)) {
      const opp = currentMatch.home_team === team ? currentMatch.away_team : currentMatch.home_team;
      return rowByTeam.get(opp ?? "") ?? null;
    }
    return null;
  };

  return (
    <div className="v2-advice-shell">
      <ContextPanel prediction={prediction} match={currentMatch} snapshot={snapshot} />

      <div className="v2-advice-grid">
        {focusRows.map((row) => {
          const opponent = opponentOf(row.team);
          const actions = buildActions(row, opponent, rows, prediction).slice(0, 4);
          return <TeamPlan key={row.team} row={row} opponent={opponent} actions={actions} />;
        })}
      </div>
    </div>
  );
}

function ContextPanel({ prediction, match, snapshot }: { prediction: Prediction | null; match: Match | null; snapshot: number }) {
  const title = prediction
    ? `${prediction.home_team} x ${prediction.away_team}`
    : match
      ? `${match.home_team} x ${match.away_team}`
      : `Snapshot ${snapshot}`;
  const subtitle = prediction
    ? `Plano orientado pela preditiva: ${prediction.favorite} entra como referência de vantagem.`
    : "Plano baseado no raio-x acumulado do snapshot atual.";
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ padding: "13px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 0.5 }}>Plano prescritivo</div>
        <div style={{ marginTop: 5, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <b style={{ fontSize: 15 }}>{title}</b>
          {prediction?.probabilities && (
            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
              {prediction.probabilities.home_win}% casa · {prediction.probabilities.draw}% empate · {prediction.probabilities.away_win}% fora
            </span>
          )}
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4, lineHeight: 1.45 }}>{subtitle}</div>
      </div>
    </section>
  );
}

function TeamPlan({ row, opponent, actions }: { row: TeamSnapshot; opponent: TeamSnapshot | null; actions: Action[] }) {
  const style = typeof row.estilo_jogo === "string" ? row.estilo_jogo : null;
  const color = STYLE_COLOR[style ?? ""] ?? "var(--accent)";
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      <header style={{ padding: "13px 15px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Flag team={row.team} height={18} />
          <b style={{ fontSize: 15 }}>{row.team}</b>
          <span style={{ color, fontWeight: 850, fontSize: 12 }}>{styleName(style)}</span>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 11.5, marginTop: 5 }}>
          {opponent ? `Plano contra ${opponent.team}` : "Plano de ajuste para o próximo recorte"}
        </div>
      </header>

      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        <ScoreStrip row={row} opponent={opponent} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {actions.map((action, index) => <ActionCard key={`${action.title}-${index}`} action={action} />)}
        </div>
      </div>
    </section>
  );
}

function ScoreStrip({ row, opponent }: { row: TeamSnapshot; opponent: TeamSnapshot | null }) {
  const items = [
    ["Ataque", num(row.score_ataque, 0), diff(row.score_ataque, opponent?.score_ataque)],
    ["Defesa", num(row.score_defesa, 0), diff(row.score_defesa, opponent?.score_defesa)],
    ["Controle", num(row.score_controle, 0), diff(row.score_controle, opponent?.score_controle)],
    ["Eficiência", num(row.score_eficiencia, 0), diff(row.score_eficiencia, opponent?.score_eficiencia)],
  ];
  return (
    <div className="v2-advice-strip">
      {items.map(([label, value, delta]) => (
        <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "8px 7px", minWidth: 0 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 10.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
          <div style={{ color: "var(--text)", fontWeight: 900, fontSize: 16, marginTop: 2 }}>{value}</div>
          <div style={{ color: delta.startsWith("+") ? "#3fb950" : delta.startsWith("-") ? "#d29922" : "var(--text-muted)", fontSize: 10.5, marginTop: 1 }}>{delta}</div>
        </div>
      ))}
    </div>
  );
}

function ActionCard({ action }: { action: Action }) {
  const tone = TONE[action.tone];
  return (
    <article style={{ background: "var(--surface)", border: `1px solid ${tone.color}55`, borderLeft: `3px solid ${tone.color}`, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ color: tone.color, fontSize: 10.5, fontWeight: 900, textTransform: "uppercase", letterSpacing: 0.5 }}>{tone.label}</span>
        <span style={{ color: action.urgency === "alta" ? "#f85149" : action.urgency === "media" ? "#d29922" : "var(--text-muted)", fontSize: 10.5, fontWeight: 800 }}>{action.urgency}</span>
      </div>
      <h3 style={{ margin: "5px 0 0", fontSize: 14, lineHeight: 1.25 }}>{action.title}</h3>
      <p style={{ margin: "5px 0 0", color: "var(--text-muted)", fontSize: 12.2, lineHeight: 1.45 }}>{action.why}</p>
      <p style={{ margin: "7px 0 0", color: "var(--text)", fontSize: 12.5, lineHeight: 1.45, fontWeight: 650 }}>{action.doThis}</p>
      <div style={{ marginTop: 7, color: "var(--text-muted)", fontSize: 10.8 }}>{action.metric}</div>
    </article>
  );
}

function buildActions(team: TeamSnapshot, opponent: TeamSnapshot | null, field: TeamSnapshot[], prediction: Prediction | null): Action[] {
  const actions: Action[] = [];
  const avg = (key: string) => average(field.map((row) => toNum(row[key])));
  const attackGap = gap(team.score_ataque, opponent?.score_defesa);
  const defenseGap = gap(team.score_defesa, opponent?.score_ataque);
  const xg = metric(team, "xg_pj");
  const xgAgainst = metric(team, "xg_sofrido_pj");
  const oppXg = opponent ? metric(opponent, "xg_pj") : null;
  const control = metric(team, "final_third_control");
  const setPieces = metric(team, "fase_bola_parada");
  const corners = metric(team, "escanteios_pj");
  const style = typeof team.estilo_jogo === "string" ? team.estilo_jogo : "";

  if (attackGap < -8 || (xg != null && xg < avg("xg_pj") - 0.15)) {
    actions.push({
      tone: "attack",
      urgency: attackGap < -14 ? "alta" : "media",
      title: "Aumentar qualidade da última ação",
      why: opponent
        ? `O ataque está abaixo da defesa adversária (${num(team.score_ataque, 0)} vs ${num(opponent.score_defesa, 0)}).`
        : `A criação está abaixo da média do recorte (${num(xg)} xG/jogo).`,
      doThis: "Priorize entradas na área e passes de ruptura antes de aumentar volume de chute. Menos finalização forçada, mais chance limpa.",
      metric: `xG/jogo ${num(xg)} · chutes na área ${num(metric(team, "chutes_dentro_area_pj"))}`,
    });
  }

  if (defenseGap < -8 || (xgAgainst != null && oppXg != null && xgAgainst > oppXg + 0.25)) {
    actions.push({
      tone: "defense",
      urgency: defenseGap < -14 ? "alta" : "media",
      title: "Proteger a zona de maior perigo",
      why: opponent
        ? `A defesa encontra um ataque mais forte (${num(team.score_defesa, 0)} defesa vs ${num(opponent.score_ataque, 0)} ataque).`
        : `O time vem cedendo ${num(xgAgainst)} xG por jogo.`,
      doThis: "Baixe o risco nas perdas pelo centro e force o adversário para corredores laterais. O objetivo é trocar chance central por cruzamento contestado.",
      metric: `xG sofrido/jogo ${num(xgAgainst)} · chutes no alvo sofridos ${num(metric(team, "chutes_sofridos_no_alvo_pj"))}`,
    });
  }

  if (control != null && control < avg("final_third_control") - 4) {
    actions.push({
      tone: "control",
      urgency: "media",
      title: "Ganhar presença no terço final",
      why: `O controle territorial está baixo para sustentar pressão (${num(control, 0)}).`,
      doThis: "Suba apoio por trás da bola e use inversões curtas para manter ataques vivos. Sem presença, a equipe fica refém de transição.",
      metric: `controle terço final ${num(control, 0)} · precisão passe ${numPct(metric(team, "precisao_passes"))}`,
    });
  }

  if ((setPieces != null && setPieces >= avg("fase_bola_parada") + 4) || (corners != null && corners >= avg("escanteios_pj") + 1)) {
    actions.push({
      tone: "setpiece",
      urgency: "baixa",
      title: "Transformar bola parada em plano A situacional",
      why: `A bola parada já aparece como alavanca forte no perfil ${styleName(style)}.`,
      doThis: "Ataque a primeira trave para gerar segunda bola e mantenha dois jogadores fora da área para rebote/contra-pressão.",
      metric: `bola parada ${num(setPieces, 1)} · escanteios/jogo ${num(corners)}`,
    });
  }

  const predSide = predictionSideFor(prediction, team.team);
  if (predSide?.risk === "underdog") {
    actions.push({
      tone: "risk",
      urgency: "alta",
      title: "Reduzir variância nos primeiros 25 minutos",
      why: `A preditiva coloca ${team.team} atrás no cenário-base.`,
      doThis: "Comece com bloco mais compacto, faltas táticas longe da área e transição com poucos passes. O primeiro objetivo é não abrir o jogo cedo.",
      metric: `chance estimada de vitória ${predSide.winPct}%`,
    });
  } else if (predSide?.risk === "favorite") {
    actions.push({
      tone: "control",
      urgency: "baixa",
      title: "Não acelerar o jogo sem necessidade",
      why: `${team.team} entra com vantagem na projeção; o risco é transformar controle em troca franca.`,
      doThis: "Use posse para escolher o lado fraco e evite ataques partidos após vantagem territorial. Favoritismo pede paciência.",
      metric: `chance estimada de vitória ${predSide.winPct}%`,
    });
  }

  if (actions.length === 0) {
    actions.push({
      tone: "control",
      urgency: "baixa",
      title: "Manter identidade e ajustar detalhes",
      why: "O perfil atual não mostra um buraco gritante contra o recorte comparado.",
      doThis: "Preserve o padrão dominante e mexa só no gatilho de pressão após perda e na ocupação da área em ataques longos.",
      metric: `score geral ${num(team.score_geral, 0)} · estilo ${styleName(style)}`,
    });
  }

  return sortActions(actions);
}

function predictionSideFor(prediction: Prediction | null, team: string) {
  if (!prediction) return null;
  const isHome = prediction.home_team === team;
  const isAway = prediction.away_team === team;
  if (!isHome && !isAway) return null;
  const winPct = isHome ? prediction.probabilities.home_win : prediction.probabilities.away_win;
  const oppPct = isHome ? prediction.probabilities.away_win : prediction.probabilities.home_win;
  const risk = winPct + 8 < oppPct ? "underdog" : winPct >= oppPct + 8 ? "favorite" : "balanced";
  return { winPct, risk };
}

function sortActions(actions: Action[]) {
  const weight = { alta: 3, media: 2, baixa: 1 };
  return [...actions].sort((a, b) => weight[b.urgency] - weight[a.urgency]);
}

function matchForSnapshot(matches: Match[], snapshot: number) {
  return matches
    .filter((match) => match.status === "finalizado")
    .sort((a, b) => String(a.date_utc ?? "").localeCompare(String(b.date_utc ?? "")))
    [snapshot - 1] ?? null;
}

function metric(row: TeamSnapshot, key: string) {
  const direct = toNum(row[key]);
  if (direct != null) return direct;
  const perGame = toNum(row[`${key}_pj`]);
  return perGame;
}

function gap(a: number | null | undefined, b: number | null | undefined) {
  const av = toNum(a);
  const bv = toNum(b);
  return av != null && bv != null ? av - bv : 0;
}

function diff(a: number | null | undefined, b: number | null | undefined) {
  const delta = gap(a, b);
  if (!b || Math.abs(delta) < 0.5) return "vs opp -";
  return `${delta >= 0 ? "+" : ""}${Math.round(delta)} vs opp`;
}

function average(values: Array<number | null>) {
  const valid = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return valid.length ? valid.reduce((acc, value) => acc + value, 0) / valid.length : 0;
}

function toNum(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function num(value: unknown, decimals = 2) {
  const parsed = toNum(value);
  return parsed == null ? "-" : parsed.toFixed(decimals).replace(".", ",");
}

function numPct(value: unknown) {
  const parsed = toNum(value);
  if (parsed == null) return "-";
  const pct = parsed <= 1 ? parsed * 100 : parsed;
  return `${Math.round(pct)}%`;
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "32px 16px", textAlign: "center", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5, maxWidth: 560, margin: "0 auto" }}>{texto}</div>;
}
