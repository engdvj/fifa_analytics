"use client";

import React from "react";
import { Match, PredictiveData, TeamSnapshot } from "@/lib/api";
import { usePredictive, useTeamSnapshots } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import { STYLE_COLOR, styleName } from "@/lib/styleMeta";

type Prediction = PredictiveData["matches"][number];
type RiskTone = "transition" | "box" | "setpiece" | "discipline" | "gameState";
type Level = "alto" | "medio" | "baixo";

interface Risk {
  tone: RiskTone;
  title: string;
  scenario: string;
  avoid: string;
  earlyWarning: string;
  evidence: string;
  likelihood: Level;
  impact: Level;
}

interface Props {
  snapshot: number;
  enabled: boolean;
  matches: Match[];
  selectedTeams: string[];
}

const TONE: Record<RiskTone, { label: string; color: string }> = {
  transition: { label: "Transição", color: "#f85149" },
  box: { label: "Área", color: "#d29922" },
  setpiece: { label: "Bola parada", color: "#f0883e" },
  discipline: { label: "Disciplina", color: "#a371f7" },
  gameState: { label: "Estado do jogo", color: "#58a6ff" },
};

export default function PreventivaView({ snapshot, enabled, matches, selectedTeams }: Props) {
  const { snapshots: rows, isLoading, error } = useTeamSnapshots(snapshot);
  const { predictive, isLoading: predictiveLoading } = usePredictive({ snapshot, enabled });
  const prediction = predictive?.matches?.[0] ?? null;
  const rowByTeam = React.useMemo(() => new Map(rows.map((row) => [row.team, row])), [rows]);
  const focusRows = selectedTeams
    .map((team) => rowByTeam.get(team))
    .filter((row): row is TeamSnapshot => !!row);
  const currentMatch = React.useMemo(() => matchForSnapshot(matches, snapshot), [matches, snapshot]);

  if (isLoading || predictiveLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  }
  if (error) {
    return <Aviso texto={`Erro ao carregar preventiva: ${String(error)}`} />;
  }
  if (!focusRows.length) {
    return <Aviso texto="Escolha uma ou duas seleções para montar o mapa de riscos." />;
  }

  const opponentOf = (team: string) => {
    if (prediction && (prediction.home_team === team || prediction.away_team === team)) {
      const opponent = prediction.home_team === team ? prediction.away_team : prediction.home_team;
      return rowByTeam.get(opponent) ?? null;
    }
    if (focusRows.length === 2) {
      return focusRows.find((row) => row.team !== team) ?? null;
    }
    if (currentMatch && (currentMatch.home_team === team || currentMatch.away_team === team)) {
      const opponent = currentMatch.home_team === team ? currentMatch.away_team : currentMatch.home_team;
      return rowByTeam.get(opponent ?? "") ?? null;
    }
    return null;
  };

  return (
    <div className="v2-advice-shell">
      <ContextPanel prediction={prediction} match={currentMatch} snapshot={snapshot} />
      <div className="v2-advice-grid">
        {focusRows.map((row) => {
          const opponent = opponentOf(row.team);
          const risks = buildRisks(row, opponent, rows, prediction).slice(0, 5);
          return <RiskPanel key={row.team} row={row} opponent={opponent} risks={risks} />;
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
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ padding: "13px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ color: "var(--text-muted)", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: 0.5 }}>Mapa preventivo</div>
        <div style={{ marginTop: 5, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <b style={{ fontSize: 15 }}>{title}</b>
          {prediction && <span style={{ color: "var(--text-muted)", fontSize: 12 }}>riscos priorizados pelo cenário da preditiva</span>}
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4, lineHeight: 1.45 }}>
          Prevenção aqui significa identificar o erro provável antes dele aparecer no placar.
        </div>
      </div>
    </section>
  );
}

function RiskPanel({ row, opponent, risks }: { row: TeamSnapshot; opponent: TeamSnapshot | null; risks: Risk[] }) {
  const style = typeof row.estilo_jogo === "string" ? row.estilo_jogo : null;
  const color = STYLE_COLOR[style ?? ""] ?? "var(--accent)";
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      <header style={{ padding: "13px 15px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <Flag team={row.team} height={18} />
          <b style={{ fontSize: 15, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.team}</b>
          <span style={{ color, fontWeight: 850, fontSize: 12 }}>{styleName(style)}</span>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 11.5, marginTop: 5 }}>
          {opponent ? `Riscos contra ${opponent.team}` : "Riscos do recorte atual"}
        </div>
      </header>

      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        <RiskStrip row={row} opponent={opponent} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {risks.map((risk, index) => <RiskCard key={`${risk.title}-${index}`} risk={risk} />)}
        </div>
      </div>
    </section>
  );
}

function RiskStrip({ row, opponent }: { row: TeamSnapshot; opponent: TeamSnapshot | null }) {
  const items = [
    ["xGA/j", num(metric(row, "xg_sofrido_pj")), opponent ? `opp xG ${num(metric(opponent, "xg_pj"))}` : "sem opp"],
    ["Chutes alvo", num(metric(row, "chutes_sofridos_no_alvo_pj")), "sofridos/j"],
    ["Amarelos", num(metric(row, "amarelos_pj")), "por jogo"],
    ["Bola parada", num(metric(opponent ?? row, "fase_bola_parada"), 1), opponent ? "ameaça opp" : "perfil"],
  ];
  return (
    <div className="v2-advice-strip">
      {items.map(([label, value, note]) => (
        <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "8px 7px", minWidth: 0 }}>
          <div style={{ color: "var(--text-muted)", fontSize: 10.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
          <div style={{ color: "var(--text)", fontWeight: 900, fontSize: 16, marginTop: 2 }}>{value}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 10.5, marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{note}</div>
        </div>
      ))}
    </div>
  );
}

function RiskCard({ risk }: { risk: Risk }) {
  const tone = TONE[risk.tone];
  return (
    <article style={{ background: "var(--surface)", border: `1px solid ${tone.color}55`, borderLeft: `3px solid ${tone.color}`, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ color: tone.color, fontSize: 10.5, fontWeight: 900, textTransform: "uppercase", letterSpacing: 0.5 }}>{tone.label}</span>
        <span style={{ display: "flex", gap: 6, color: "var(--text-muted)", fontSize: 10.5, fontWeight: 800 }}>
          <LevelPill label="prob" level={risk.likelihood} />
          <LevelPill label="impacto" level={risk.impact} />
        </span>
      </div>
      <h3 style={{ margin: "5px 0 0", fontSize: 14, lineHeight: 1.25 }}>{risk.title}</h3>
      <p style={{ margin: "5px 0 0", color: "var(--text-muted)", fontSize: 12.2, lineHeight: 1.45 }}>{risk.scenario}</p>
      <p style={{ margin: "7px 0 0", color: "var(--text)", fontSize: 12.5, lineHeight: 1.45, fontWeight: 650 }}>{risk.avoid}</p>
      <div style={{ marginTop: 7, display: "grid", gridTemplateColumns: "1fr", gap: 4 }}>
        <span style={{ color: "#d29922", fontSize: 11.2, lineHeight: 1.35 }}>Sinal: {risk.earlyWarning}</span>
        <span style={{ color: "var(--text-muted)", fontSize: 10.8 }}>{risk.evidence}</span>
      </div>
    </article>
  );
}

function LevelPill({ label, level }: { label: string; level: Level }) {
  const color = level === "alto" ? "#f85149" : level === "medio" ? "#d29922" : "#8b949e";
  return <span style={{ color }}>{label} {level}</span>;
}

function buildRisks(team: TeamSnapshot, opponent: TeamSnapshot | null, field: TeamSnapshot[], prediction: Prediction | null): Risk[] {
  const risks: Risk[] = [];
  const avg = (key: string) => average(field.map((row) => toNum(row[key])));
  const xgAgainst = metric(team, "xg_sofrido_pj");
  const shotsTargetAgainst = metric(team, "chutes_sofridos_no_alvo_pj");
  const oppXg = opponent ? metric(opponent, "xg_pj") : null;
  const oppTransition = opponent ? Math.max(metric(opponent, "fase_contra_ataque") ?? 0, metric(opponent, "estilo_verticalidade") ?? 0) : 0;
  const oppSetPiece = opponent ? metric(opponent, "fase_bola_parada") : null;
  const oppCorners = opponent ? metric(opponent, "escanteios_pj") : null;
  const yellows = metric(team, "amarelos_pj");
  const fouls = metric(team, "faltas_cometidas_pj");
  const passPct = metric(team, "precisao_passes");
  const control = metric(team, "final_third_control");
  const predSide = predictionSideFor(prediction, team.team);

  if ((oppTransition >= avg("fase_contra_ataque") + 4 && (control ?? 0) >= avg("final_third_control")) || predSide?.risk === "favorite") {
    risks.push({
      tone: "transition",
      likelihood: oppTransition >= avg("fase_contra_ataque") + 8 ? "alto" : "medio",
      impact: "alto",
      title: "Contra-ataque nas costas do domínio",
      scenario: opponent
        ? `${opponent.team} tem sinal de transição/verticalidade para punir perda com time aberto.`
        : "O risco principal é perder a bola com muita gente à frente.",
      avoid: "Evite ataque com os dois laterais altos ao mesmo tempo. Mantenha cobertura central pronta antes da bola entrar no terço final.",
      earlyWarning: "duas perdas seguidas por dentro ou zagueiro defendendo campo grande.",
      evidence: `transição/verticalidade opp ${num(oppTransition, 1)} · controle ${num(control, 0)}`,
    });
  }

  if ((xgAgainst != null && xgAgainst >= avg("xg_sofrido_pj") + 0.2) || (oppXg != null && oppXg >= avg("xg_pj") + 0.2)) {
    risks.push({
      tone: "box",
      likelihood: xgAgainst != null && xgAgainst >= avg("xg_sofrido_pj") + 0.45 ? "alto" : "medio",
      impact: "alto",
      title: "Ceder chance limpa cedo demais",
      scenario: opponent
        ? `O encontro soma xG sofrido relevante (${num(xgAgainst)}) com ataque adversário perigoso (${num(oppXg)}).`
        : `O time vem permitindo ${num(xgAgainst)} xG por jogo.`,
      avoid: "Não aceite perseguições longas dos volantes para fora do centro. A prioridade é fechar passe frontal e segunda bola na meia-lua.",
      earlyWarning: "adversário recebendo entrelinhas de frente para a área.",
      evidence: `xG sofrido/jogo ${num(xgAgainst)} · chutes no alvo sofridos ${num(shotsTargetAgainst)}`,
    });
  }

  if ((oppSetPiece != null && oppSetPiece >= avg("fase_bola_parada") + 4) || (oppCorners != null && oppCorners >= avg("escanteios_pj") + 1)) {
    risks.push({
      tone: "setpiece",
      likelihood: oppSetPiece != null && oppSetPiece >= avg("fase_bola_parada") + 8 ? "alto" : "medio",
      impact: "medio",
      title: "Jogo destravar em bola parada",
      scenario: opponent
        ? `${opponent.team} tem bola parada acima da média do recorte.`
        : "O risco de bola parada cresce se o jogo ficar travado.",
      avoid: "Evite faltas laterais baratas e escanteios cedidos sem pressão. Marcação híbrida precisa proteger primeira e segunda trave.",
      earlyWarning: "sequência de escanteios ou faltas laterais nos primeiros 20 minutos.",
      evidence: `bola parada opp ${num(oppSetPiece, 1)} · escanteios opp ${num(oppCorners)}`,
    });
  }

  if ((yellows != null && yellows >= avg("amarelos_pj") + 0.4) || (fouls != null && fouls >= avg("faltas_cometidas_pj") + 2)) {
    risks.push({
      tone: "discipline",
      likelihood: yellows != null && yellows >= avg("amarelos_pj") + 0.8 ? "alto" : "medio",
      impact: "medio",
      title: "Cartão mudar a forma de defender",
      scenario: "O perfil disciplinar aumenta o risco de perder agressividade ou ficar exposto a expulsão.",
      avoid: "Troque o marcador amarelado de zona ou reduza duelo isolado no corredor. Falta tática só longe da área.",
      earlyWarning: "primeiro cartão em defensor/meio antes dos 35 minutos.",
      evidence: `amarelos/jogo ${num(yellows)} · faltas/jogo ${num(fouls)}`,
    });
  }

  if ((passPct != null && passPct < avg("precisao_passes") - 0.04) || predSide?.risk === "underdog") {
    risks.push({
      tone: "gameState",
      likelihood: predSide?.risk === "underdog" ? "alto" : "medio",
      impact: predSide?.risk === "underdog" ? "alto" : "medio",
      title: "Entrar em jogo emocional",
      scenario: predSide?.risk === "underdog"
        ? "A projeção coloca o time atrás; gol sofrido cedo pode quebrar o plano."
        : "Baixa segurança de passe pode transformar pressão adversária em caos.",
      avoid: "Nos primeiros minutos após sofrer pressão, reduza ambição do passe e reorganize a posse com apoio curto.",
      earlyWarning: "três ataques seguidos terminando em perda antes de cruzar o meio.",
      evidence: `precisão passe ${numPct(passPct)}${predSide ? ` · chance vitória ${predSide.winPct}%` : ""}`,
    });
  }

  if (!risks.length) {
    risks.push({
      tone: "gameState",
      likelihood: "baixo",
      impact: "medio",
      title: "Risco baixo, mas não invisível",
      scenario: "O recorte não aponta uma fragilidade dominante contra o adversário ou snapshot atual.",
      avoid: "Mantenha atenção nos cinco minutos após gols, substituições e intervalo; são janelas comuns de desorganização.",
      earlyWarning: "linha defensiva e meio-campo ficando separados após a primeira troca de ritmo.",
      evidence: `score geral ${num(team.score_geral, 0)} · estilo ${styleName(typeof team.estilo_jogo === "string" ? team.estilo_jogo : null)}`,
    });
  }

  return sortRisks(risks);
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

function sortRisks(risks: Risk[]) {
  const weight = { alto: 3, medio: 2, baixo: 1 };
  return [...risks].sort((a, b) => (weight[b.likelihood] + weight[b.impact]) - (weight[a.likelihood] + weight[a.impact]));
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
  return toNum(row[`${key}_pj`]);
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
