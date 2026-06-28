"use client";

import React from "react";
import { PredictiveData } from "@/lib/api";
import { usePredictive, usePredictiveBacktest } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";

type Prediction = PredictiveData["matches"][number];

const num = (v: number | null | undefined, d = 2) =>
  typeof v === "number" ? v.toFixed(d).replace(".", ",") : "-";

const HOME = "#58a6ff";
const AWAY = "#f0883e";
const DRAW = "#8b949e";

export default function PreditivaView({
  snapshot,
  enabled,
}: {
  snapshot: number;
  enabled: boolean;
}) {
  const { predictive, isLoading, error } = usePredictive({ snapshot, enabled });
  // Histórico de acerto = track record COMPLETO do modelo (todos os jogos já
  // finalizados), independente da bolinha que você está olhando. Sem `end` ele
  // usa o último snapshot disponível.
  const { backtest } = usePredictiveBacktest({ start: 25, enabled });

  if (isLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  }
  if (error) {
    return <Aviso texto={`Erro ao carregar a previsão: ${String(error)}`} />;
  }
  if (!predictive?.matches?.length) {
    const minDisplay = predictive?.base?.min_display_game ?? 2;
    if (snapshot < minDisplay) {
      return <Aviso texto={`A previsão precisa de pelo menos um jogo de base — começa a partir do jogo ${minDisplay}.`} />;
    }
    return <Aviso texto={`Não há jogo para prever na posição ${snapshot}.`} />;
  }

  const lowConf = !!predictive.matches[0]?.low_confidence;
  const minPred = predictive.base?.min_prediction_game ?? 25;
  const hasTrack = !!backtest?.summary?.n;
  return (
    <div
      className={`v2-predictive-shell ${hasTrack ? "has-track" : ""}`}
      style={{
        display: "grid",
        gridTemplateColumns: hasTrack ? "minmax(0, 620px) minmax(240px, 320px)" : "minmax(0, 620px)",
        gap: 14,
        justifyContent: "center",
        alignItems: "start",
      }}
    >
      <div className="v2-predictive-main" style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
        {lowConf && (
          <div style={{ background: "rgba(245,197,66,0.1)", border: "1px solid #f5c54255", borderRadius: 8, padding: "10px 12px", fontSize: 12, color: "#f5c542", lineHeight: 1.45 }}>
            ⚠ Previsão de <b>baixa confiança</b>: poucos jogos de base até aqui (antes do jogo {minPred}). A previsão é mostrada, mas não entra na avaliação de acerto do modelo.
          </div>
        )}
        {predictive.matches.map((match) => (
          <PredictionCard key={match.match_id} match={match} />
        ))}
      </div>

      {hasTrack && <ModelTrack summary={backtest!.summary} treino={predictive.base?.treino_jogos} />}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   CARD DO JOGO
   ────────────────────────────────────────────────────────────────────────── */

function PredictionCard({ match }: { match: Prediction }) {
  const p = match.probabilities;
  const score = p.scoreline?.recommended ?? { home: p.score.home, away: p.score.away, probability: null };
  const alternatives = p.scoreline?.alternatives ?? [];
  const actual = match.actual_result;
  const evaluation = match.evaluation;

  const favSide = match.favorite_side ?? "home";
  const favColor = favSide === "home" ? HOME : favSide === "away" ? AWAY : DRAW;
  const verdict = readVerdict(match);

  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
      {/* HERO: times + placar provável */}
      <header style={{ padding: "16px 16px 14px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ display: "flex", gap: 6, justifyContent: "center", flexWrap: "wrap", marginBottom: 12 }}>
          {match.group && <Tag texto={match.group} />}
          {match.stage && <Tag texto={traduzStage(match.stage)} />}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <TeamLabel team={match.home_team} />
          <div style={{ textAlign: "center", minWidth: 96 }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>placar provável</div>
            <div style={{ fontSize: 30, fontWeight: 900, color: "var(--text)", lineHeight: 1 }}>
              {score.home}<span style={{ color: "var(--text-muted)", margin: "0 3px" }}>×</span>{score.away}
            </div>
          </div>
          <TeamLabel team={match.away_team} align="right" />
        </div>

        {/* Veredito em uma frase */}
        <div style={{ marginTop: 13, textAlign: "center" }}>
          <span style={{ fontSize: 15, fontWeight: 800, color: favColor }}>{verdict.title}</span>
          <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4 }}>{verdict.subtitle}</div>
        </div>

        {/* Confiança em linguagem simples */}
        <div style={{ display: "flex", gap: 6, justifyContent: "center", flexWrap: "wrap", marginTop: 11 }}>
          <ConfidenceChip match={match} />
          {match.frozen_at && <Badge texto="palpite oficial" tone="neutral" />}
          {actual && (
            <Badge
              texto={evaluation?.winner_hit ? "acertou o vencedor" : "errou o vencedor"}
              tone={evaluation?.winner_hit ? "good" : "warn"}
            />
          )}
        </div>
      </header>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 18 }}>
        {/* CHANCES DE CADA RESULTADO */}
        <Block title="Chances de cada resultado">
          <ProbBar
            home={{ team: match.home_team, pct: p.home_win }}
            draw={p.draw}
            away={{ team: match.away_team, pct: p.away_win }}
          />
        </Block>

        {/* PREVISÃO vs REALIDADE (lado a lado) quando finalizado; senão só a previsão */}
        {actual && evaluation ? (
          <Block title="Previsão × Realidade">
            <PredictionVsReality match={match} score={score} actual={actual} evaluation={evaluation} />
          </Block>
        ) : (
          <Block title="Como deve ser o jogo" hint="“Chances de gol” = qualidade das oportunidades esperadas (xG).">
            <div className="v2-predictive-stat-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
              <Stat label={`Chances de gol · ${match.home_team}`} value={num(match.expected_goals.home)} color={HOME} />
              <Stat label={`Chances de gol · ${match.away_team}`} value={num(match.expected_goals.away)} color={AWAY} />
              <Stat label="Tom do jogo" value={gameTone(match)} color="var(--text)" />
            </div>
          </Block>
        )}

        {/* PLACARES POSSÍVEIS */}
        {alternatives.length > 0 && (
          <Block title="Placares mais prováveis">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {alternatives.map((alt) => (
                <ScoreChip
                  key={`${alt.home}-${alt.away}-${alt.result}`}
                  alt={alt}
                  recommended={alt.home === score.home && alt.away === score.away}
                />
              ))}
            </div>
          </Block>
        )}

        {/* POR QUE — fatores */}
        <Block title="Por que — quem leva vantagem em cada quesito">
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {match.factors.map((factor) => (
              <FactorRow key={factor.label} factor={factor} home={match.home_team} away={match.away_team} />
            ))}
          </div>
        </Block>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   VEREDITO / TOM (linguagem simples)
   ────────────────────────────────────────────────────────────────────────── */

function readVerdict(match: Prediction): { title: string; subtitle: string } {
  const p = match.probabilities;
  const side = match.favorite_side ?? "home";
  if (side === "draw") {
    return {
      title: "Jogo equilibrado",
      subtitle: `Sem favorito claro — empate é o cenário mais provável (${p.draw}%).`,
    };
  }
  const fav = match.favorite;
  const favPct = side === "home" ? p.home_win : p.away_win;
  const margem =
    favPct >= 60 ? "favorito claro" : favPct >= 45 ? "leve favorito" : "favorito por pouco";
  return {
    title: `${fav} é ${margem}`,
    subtitle: `${favPct}% de chance de vencer.`,
  };
}

function gameTone(match: Prediction): string {
  const total = match.summary?.total_xg ?? 0;
  if (total >= 3) return "aberto";
  if (total >= 2.3) return "equilibrado";
  return "truncado";
}

function ConfidenceChip({ match }: { match: Prediction }) {
  // Une consenso + amostra numa só leitura de confiança.
  const consensus = match.consensus;
  const conf = match.confidence?.nivel;
  let texto = "confiança média";
  let tone: "good" | "warn" | "neutral" = "neutral";
  if (consensus === "forte" && conf === "alta") {
    texto = "previsão confiável";
    tone = "good";
  } else if (consensus === "baixa" || conf === "baixa") {
    texto = "previsão incerta";
    tone = "warn";
  }
  return <Badge texto={texto} tone={tone} />;
}

/* ──────────────────────────────────────────────────────────────────────────
   BLOCOS VISUAIS
   ────────────────────────────────────────────────────────────────────────── */

function Block({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 800, marginBottom: 8 }}>
        {title}
      </div>
      {children}
      {hint && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.4, opacity: 0.85 }}>{hint}</div>}
    </div>
  );
}

function ProbBar({
  home,
  draw,
  away,
}: {
  home: { team: string; pct: number };
  draw: number;
  away: { team: string; pct: number };
}) {
  return (
    <div>
      {/* rótulos casa / empate / fora; as porcentagens ficam DENTRO da barra */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 6 }}>
        <span style={{ color: "var(--text-muted)" }}>{home.team}</span>
        <span style={{ color: "var(--text-muted)" }}>empate</span>
        <span style={{ color: "var(--text-muted)" }}>{away.team}</span>
      </div>
      <div style={{ display: "flex", height: 20, borderRadius: 8, overflow: "hidden", background: "var(--surface2)" }}>
        <BarSeg pct={home.pct} color={HOME} />
        <BarSeg pct={draw} color={DRAW} />
        <BarSeg pct={away.pct} color={AWAY} />
      </div>
    </div>
  );
}

function BarSeg({ pct, color }: { pct: number; color: string }) {
  // Mostra a % dentro do segmento; some quando o segmento é estreito demais.
  return (
    <div style={{ position: "relative", width: `${pct}%`, background: color, minWidth: 0 }}>
      {pct >= 9 && (
        <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: "#0d1117", whiteSpace: "nowrap" }}>
          {pct}%
        </span>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "9px 10px", minWidth: 0 }}>
      <div style={{ fontSize: 10.5, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
      <div style={{ marginTop: 3, color, fontWeight: 850, fontSize: 16, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}

function ScoreChip({
  alt,
  recommended,
}: {
  alt: NonNullable<Prediction["probabilities"]["scoreline"]>["alternatives"][number];
  recommended?: boolean;
}) {
  const color = alt.result === "home" ? HOME : alt.result === "away" ? AWAY : DRAW;
  return (
    <span
      style={{
        fontSize: 12,
        color: "var(--text)",
        background: recommended ? color + "22" : "var(--surface)",
        border: `1px solid ${color}`,
        borderRadius: 6,
        padding: "4px 9px",
        fontWeight: 750,
      }}
    >
      {alt.home}-{alt.away} <span style={{ color: "var(--text-muted)", fontWeight: 550 }}>{num(alt.probability, 1)}%</span>
    </span>
  );
}

function FactorRow({ factor, home, away }: { factor: Prediction["factors"][number]; home: string; away: string }) {
  const edge = factor.edge === "home" ? home : factor.edge === "away" ? away : "equilíbrio";
  const edgeColor = factor.edge === "home" ? HOME : factor.edge === "away" ? AWAY : "var(--text-muted)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto 96px", gap: 8, alignItems: "center", fontSize: 12.5 }}>
      <span style={{ color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{traduzFactor(factor.label)}</span>
      <span style={{ color: edgeColor, fontWeight: 750, textAlign: "right", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{edge}</span>
      <span style={{ color: "var(--text-muted)", fontWeight: 500, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {num(factor.home, 1)} × {num(factor.away, 1)}
      </span>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   PREVISÃO × REALIDADE (lado a lado, jogo finalizado)
   ────────────────────────────────────────────────────────────────────────── */

function PredictionVsReality({
  match,
  score,
  actual,
  evaluation,
}: {
  match: Prediction;
  score: { home: number; away: number; probability: number | null };
  actual: NonNullable<Prediction["actual_result"]>;
  evaluation: NonNullable<Prediction["evaluation"]>;
}) {
  const hit = evaluation.winner_hit;
  const tone = hit ? "#3fb950" : "#d29922";
  const name = (o: "home" | "draw" | "away") =>
    o === "home" ? match.home_team : o === "away" ? match.away_team : "Empate";
  const predictedOutcome = evaluation.predicted_outcome;

  return (
    <div>
      <div className="v2-predictive-reality-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <ComparePane title="Previsão" accent="var(--text-muted)">
          <BigScore value={`${score.home}×${score.away}`} color="var(--text)" />
          <CompareLine label="vencedor" value={name(predictedOutcome)} />
          <CompareLine label="chance" value={evaluation.actual_probability != null ? `${num(evaluation.actual_probability, 0)}%` : "-"} />
        </ComparePane>
        <ComparePane title="Realidade" accent={tone}>
          <BigScore value={`${actual.home}×${actual.away}`} color={tone} />
          <CompareLine label="vencedor" value={name(actual.outcome)} />
          <CompareLine label="placar exato" value={evaluation.exact_score ? "sim ✓" : "não"} color={evaluation.exact_score ? "#3fb950" : undefined} />
        </ComparePane>
      </div>
      <div style={{ display: "flex", justifyContent: "center", marginTop: 10 }}>
        <Badge texto={hit ? "✓ acertou o vencedor" : "✗ errou o vencedor"} tone={hit ? "good" : "warn"} />
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 8, lineHeight: 1.45, textAlign: "center" }}>
        O modelo dava <b style={{ color: "var(--text)" }}>{evaluation.actual_probability != null ? `${num(evaluation.actual_probability, 0)}%` : "-"}</b> para o que aconteceu ·
        errou o placar por <b style={{ color: "var(--text)" }}>{evaluation.goal_error_total}</b> {evaluation.goal_error_total === 1 ? "gol" : "gols"}.
      </div>
    </div>
  );
}

function ComparePane({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "var(--surface)", border: `1px solid ${accent === "var(--text-muted)" ? "var(--surface2)" : accent + "55"}`, borderRadius: 8, padding: 12, textAlign: "center" }}>
      <div style={{ fontSize: 10.5, color: accent, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 800, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function BigScore({ value, color }: { value: string; color: string }) {
  return <div style={{ fontSize: 26, fontWeight: 900, color, lineHeight: 1, marginBottom: 8 }}>{value}</div>;
}

function CompareLine({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "3px 0" }}>
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span style={{ color: color ?? "var(--text)", fontWeight: 700, textAlign: "right", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 }}>{value}</span>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   SIDEBAR: COMO O MODELO TEM ACERTADO + re-treinar
   ────────────────────────────────────────────────────────────────────────── */

function ModelTrack({
  summary,
  treino,
}: {
  summary: NonNullable<ReturnType<typeof usePredictiveBacktest>["backtest"]>["summary"];
  treino?: number;
}) {
  const acc = summary.accuracy != null ? Math.round(summary.accuracy * 100) : null;
  const recent = summary.evolution?.recent?.accuracy;
  const recentPct = recent != null ? Math.round(recent * 100) : null;

  return (
    <aside className="v2-predictive-track" style={{ display: "flex", flexDirection: "column", gap: 12, position: "sticky", top: 12 }}>
      <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "12px 14px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 800 }}>
            Como o modelo tem acertado
          </div>
          <div style={{ fontSize: 12.5, color: "var(--text)", marginTop: 4, lineHeight: 1.4, fontWeight: 650 }}>
            Vencedor certo em <b style={{ color: HOME }}>{acc != null ? `${acc}%` : "-"}</b> de {summary.n} jogos.
          </div>
        </div>
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
          <Stat label="Jogos avaliados" value={String(summary.n ?? 0)} color="var(--text)" />
          <Stat label="Acerto do vencedor" value={acc != null ? `${acc}%` : "-"} color={HOME} />
          <Stat label="Acerto recente" value={recentPct != null ? `${recentPct}%` : "-"} color="#3fb950" />
          <Stat label="Erro médio de gols" value={summary.goal_mae != null ? num(summary.goal_mae, 2) : "-"} color="var(--text)" />
          <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, margin: "2px 0 0" }}>
            Avaliação “à prova de futuro”: cada jogo só usou dados anteriores a ele
            {typeof treino === "number" ? ` (treino com ${treino} jogos)` : ""}. “Erro médio de gols” é a
            diferença média entre placar previsto e real — quanto menor, melhor.
          </p>
          <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, margin: "2px 0 0" }}>
            Para recalibrar o modelo com os resultados mais recentes, use “Re-treinar preditiva” no painel de Administração.
          </p>
        </div>
      </section>
    </aside>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   PRIMITIVOS
   ────────────────────────────────────────────────────────────────────────── */

function TeamLabel({ team, align = "left" }: { team: string; align?: "left" | "right" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: align === "right" ? "flex-end" : "flex-start", flex: 1, minWidth: 0 }}>
      {align === "left" && <Flag team={team} height={22} />}
      <span style={{ fontSize: 15, fontWeight: 800, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{team}</span>
      {align === "right" && <Flag team={team} height={22} />}
    </div>
  );
}

function Tag({ texto }: { texto: string }) {
  return (
    <span style={{ fontSize: 10.5, color: "var(--text-muted)", background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 5, padding: "2px 8px", fontWeight: 700 }}>
      {texto}
    </span>
  );
}

function Badge({ texto, tone = "neutral" }: { texto: string; tone?: "neutral" | "good" | "warn" }) {
  const color = tone === "good" ? "#3fb950" : tone === "warn" ? "#d29922" : "var(--text-muted)";
  const border = tone === "good" ? "#3fb950" : tone === "warn" ? "#d29922" : "var(--surface2)";
  return (
    <span style={{ fontSize: 11, color, background: "var(--background)", border: `1px solid ${border}`, borderRadius: 5, padding: "3px 9px", fontWeight: 700 }}>
      {texto}
    </span>
  );
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "32px 16px", textAlign: "center", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5, maxWidth: 520, margin: "0 auto" }}>{texto}</div>;
}

/* ──────────────────────────────────────────────────────────────────────────
   TRADUÇÕES
   ────────────────────────────────────────────────────────────────────────── */

function traduzStage(stage: string): string {
  const map: Record<string, string> = {
    "First Stage": "Fase de grupos",
    "Round of 32": "16-avos",
    "Round of 16": "Oitavas",
    "Quarter-final": "Quartas",
    "Quarter-finals": "Quartas",
    "Semi-final": "Semifinal",
    "Semi-finals": "Semifinal",
    "Final": "Final",
    "Play-off for third place": "Disputa de 3º",
  };
  return map[stage] ?? stage;
}

function traduzFactor(label: string): string {
  const map: Record<string, string> = {
    "Score geral": "Força geral",
    "Elo": "Ranking (Elo)",
    "xG criado/jogo": "Chances criadas",
    "xG sofrido/jogo": "Solidez defensiva",
    "Controle": "Controle de jogo",
    "Eficiencia": "Eficiência",
  };
  return map[label] ?? label;
}
