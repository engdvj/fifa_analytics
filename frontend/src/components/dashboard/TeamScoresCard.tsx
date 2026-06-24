"use client";

import React from "react";
import { TeamSnapshot } from "@/lib/api";
import { METRIC_OPTIONS } from "@/lib/metrics";
import Flag from "@/components/ui/Flag";
import { DefinitionBubble } from "@/components/DefinitionLink";

// chave do card (legacy) → id de conceito da Central de Definições. Só mapeia
// quando existe uma definição correspondente; chaves sem id ficam de fora.
const DEF_ID: Record<string, string> = {
  score_geral: "score_geral", score_resultado: "score_resultado", score_ataque: "score_ataque",
  score_defesa: "score_defesa", score_eficiencia: "score_eficiencia", score_controle: "score_controle",
  score_forca_relativa: "score_forca_relativa", score_disciplina: "score_disciplina",
  pontos: "pontos", aproveitamento: "aproveitamento", saldo_gols: "saldo_gols",
  elo_rating: "elo", clean_sheet: "clean_sheet",
  xg_pj: "xg",
  chutes_no_alvo_pj: "chutes_no_alvo", threat_pj: "threat", escanteios_pj: "escanteios",
  impedimentos_pj: "impedimentos",
  chutes_sof_alvo_pj: "chutes_no_alvo", save_pct_goleiro: "save_pct", turnovers_forcados_pj: "turnovers_forcados",
  pressoes_def_pj: "pressao_defensiva",
  posse: "posse", pitch_control: "pitch_control", final_third_control: "final_third_control",
  precisao_passes: "precisao_passes", progressoes_pj: "progressoes_bola", linebreaks_pj: "linebreaks",
  sprints_pj: "sprints", distancia_km_pj: "distancia_percorrida",
};
function defIdFor(key: string): string | null {
  const id = DEF_ID[key];
  return id && id.length > 0 ? id : null;
}

const METRIC_LABEL: Record<string, string> = {};
for (const g of METRIC_OPTIONS) for (const [k, l] of g.items) METRIC_LABEL[k] = l;

// ── Grupos de métricas do card (EXATO do legacy: rótulo, classe, métricas) ──
type Metric = [key: string, label: string];
type Group = [title: string, cls: string, metrics: Metric[]];
const METRIC_GROUPS: Group[] = [
  ["Scores", "scores", [
    ["score_geral", "Geral"], ["score_resultado", "Resultado"], ["score_ataque", "Ataque"],
    ["score_defesa", "Defesa"], ["score_eficiencia", "Eficiência"], ["score_controle", "Controle"],
    ["score_forca_relativa", "Força Relativa"], ["score_disciplina", "Disciplina"],
  ]],
  ["Campanha · Totais", "campanha", [
    ["pontos", "Pontos"], ["aproveitamento", "Aproveitamento %"], ["saldo_gols", "Saldo de Gols"],
    ["gols_pro", "Gols Marcados"], ["gols_contra", "Gols Sofridos"], ["elo_rating", "Rating Elo"],
    ["clean_sheet", "Jogos Sem Sofrer Gol"],
  ]],
  ["Ataque · Média/jogo", "ataque", [
    ["gols_pj", "Gols"], ["xg_pj", "xG (Esperados)"], ["chutes_pj", "Chutes"], ["chutes_no_alvo_pj", "No Alvo"],
    ["precisao_chutes", "Precisão de Chute %"], ["threat_pj", "Ameaça (Threat)"], ["escanteios_pj", "Escanteios"],
    ["impedimentos_pj", "Impedimentos"],
  ]],
  ["Defesa · Média/jogo", "defesa", [
    ["gols_contra_pj", "Gols Sofridos"], ["chutes_sofridos_pj", "Chutes Sofridos"],
    ["chutes_sof_alvo_pj", "Chutes no Alvo Sofridos"], ["defesas_goleiro_pj", "Defesas do Goleiro"],
    ["save_pct_goleiro", "Save % Goleiro"], ["turnovers_forcados_pj", "Turnovers Forçados"],
    ["pressoes_def_pj", "Pressões Defensivas"],
  ]],
  ["Controle · Média/jogo", "controle", [
    ["posse", "Posse %"], ["pitch_control", "Pitch Control %"], ["final_third_control", "Controle 3º Final %"],
    ["passes_pj", "Passes"], ["precisao_passes", "Precisão de Passes %"], ["progressoes_pj", "Progressões"],
    ["linebreaks_pj", "Linebreaks"], ["dribles_pj", "Dribles"],
  ]],
  ["Disciplina · Média/jogo", "disciplina", [
    ["faltas_pj", "Faltas"], ["amarelos_pj", "Amarelos"], ["vermelhos_pj", "Vermelhos"],
  ]],
];

// chave do card (legacy) → campo real do snapshot
const KEY_MAP: Record<string, string> = {
  pontos: "points", gols_pro: "gols", chutes_sof_alvo_pj: "chutes_sofridos_no_alvo_pj",
  progressoes_pj: "progressoes_bola_pj", dribles_pj: "dribles_certos_pj",
  distancia_km_pj: "distancia_total_km_pj", corridas_av_pj: "corridas_alta_vel_pj",
  pressoes_def_pj: "pressoes_defensivas_pj", faltas_pj: "faltas_cometidas_pj",
};
// métrica selecionada (snapshot) → chave do card (p/ relações/active) — inverso do KEY_MAP
const REVERSE: Record<string, string> = Object.fromEntries(Object.entries(KEY_MAP).map(([legacy, snap]) => [snap, legacy]));

const SCORE_INPUT = new Set([
  "score_resultado", "score_ataque", "score_defesa", "score_eficiencia", "score_controle", "score_forca_relativa",
  "pontos", "aproveitamento", "saldo_gols", "elo_rating",
  "gols_pj", "xg_pj", "chutes_no_alvo_pj", "precisao_chutes", "threat_pj",
  "gols_contra_pj", "chutes_sofridos_pj", "save_pct_goleiro", "turnovers_forcados_pj",
  "posse", "pitch_control", "final_third_control", "passes_pj", "precisao_passes", "progressoes_pj",
]);
const PERCENT_FRAC = new Set(["posse", "aproveitamento", "precisao_chutes", "precisao_passes", "save_pct_goleiro"]);
const PERCENT_DIRECT = new Set(["pitch_control", "final_third_control"]);

// card-key (por jogo) → campo TOTAL no snapshot. Só métricas de CONTAGEM têm
// total acumulado; taxas (%, razões) não entram aqui e ficam IGUAIS nos dois
// modos. Usado pelo toggle "Por jogo ⇄ Total".
const TOTAL_FIELD: Record<string, string> = {
  gols_pj: "gols", xg_pj: "xg", chutes_pj: "chutes", chutes_no_alvo_pj: "chutes_no_alvo",
  threat_pj: "threat", escanteios_pj: "escanteios", impedimentos_pj: "impedimentos",
  gols_contra_pj: "gols_contra", chutes_sofridos_pj: "chutes_sofridos",
  chutes_sof_alvo_pj: "chutes_sofridos_no_alvo", defesas_goleiro_pj: "defesas_goleiro",
  turnovers_forcados_pj: "turnovers_forcados", pressoes_def_pj: "pressoes_defensivas",
  passes_pj: "passes", progressoes_pj: "progressoes_bola", linebreaks_pj: "linebreaks",
  dribles_pj: "dribles_certos", faltas_pj: "faltas_cometidas", amarelos_pj: "amarelos",
  vermelhos_pj: "vermelhos",
};
type ValueMode = "pj" | "total";
// só estes grupos alternam total/por-jogo (Scores e Campanha são fixos)
const MODE_GROUPS = new Set(["ataque", "defesa", "controle", "disciplina"]);

const RELATIONS: Record<string, string[]> = {
  score_resultado: ["aproveitamento", "pontos", "saldo_gols", "gols_pro", "gols_contra", "score_geral"],
  aproveitamento: ["pontos", "saldo_gols", "score_resultado"],
  pontos: ["aproveitamento", "saldo_gols", "score_resultado"],
  saldo_gols: ["gols_pro", "gols_contra", "aproveitamento", "score_resultado"],
  gols_pro: ["saldo_gols", "gols_pj", "score_resultado", "score_ataque"],
  gols_contra: ["saldo_gols", "gols_contra_pj", "clean_sheet", "score_resultado", "score_defesa"],
  score_ataque: ["xg_pj", "gols_pj", "chutes_no_alvo_pj", "threat_pj", "score_eficiencia"],
  gols_pj: ["gols_pro", "xg_pj", "chutes_no_alvo_pj", "score_ataque", "score_eficiencia"],
  xg_pj: ["gols_pj", "chutes_no_alvo_pj", "threat_pj", "score_ataque", "score_eficiencia"],
  chutes_no_alvo_pj: ["chutes_pj", "precisao_chutes", "gols_pj", "score_ataque"],
  chutes_pj: ["chutes_no_alvo_pj", "precisao_chutes", "escanteios_pj"],
  threat_pj: ["xg_pj", "gols_pj", "score_ataque"],
  escanteios_pj: ["chutes_pj", "chutes_no_alvo_pj"],
  impedimentos_pj: ["chutes_no_alvo_pj", "score_ataque"],
  score_eficiencia: ["precisao_chutes", "xg_pj", "gols_pj", "progressoes_pj", "score_ataque"],
  precisao_chutes: ["chutes_pj", "chutes_no_alvo_pj", "gols_pj", "score_eficiencia"],
  progressoes_pj: ["passes_pj", "linebreaks_pj", "score_eficiencia", "score_controle"],
  score_defesa: ["gols_contra_pj", "gols_contra", "chutes_sofridos_pj", "save_pct_goleiro", "turnovers_forcados_pj"],
  gols_contra_pj: ["gols_contra", "chutes_sofridos_pj", "clean_sheet", "score_defesa"],
  chutes_sofridos_pj: ["gols_contra_pj", "score_defesa", "chutes_sof_alvo_pj"],
  chutes_sof_alvo_pj: ["chutes_sofridos_pj", "defesas_goleiro_pj", "score_defesa"],
  defesas_goleiro_pj: ["chutes_sof_alvo_pj", "gols_contra_pj", "save_pct_goleiro"],
  save_pct_goleiro: ["defesas_goleiro_pj", "chutes_sof_alvo_pj", "score_defesa"],
  turnovers_forcados_pj: ["score_defesa"],
  clean_sheet: ["gols_contra_pj", "gols_contra"],
  score_controle: ["posse", "pitch_control", "final_third_control", "passes_pj", "precisao_passes"],
  posse: ["passes_pj", "precisao_passes", "pitch_control", "score_controle", "estilo_posse"],
  pitch_control: ["posse", "final_third_control", "score_controle"],
  final_third_control: ["pitch_control", "posse", "score_controle"],
  passes_pj: ["posse", "precisao_passes", "progressoes_pj", "score_controle"],
  precisao_passes: ["passes_pj", "posse", "score_controle"],
  linebreaks_pj: ["progressoes_pj", "passes_pj", "score_controle"],
  dribles_pj: ["posse", "score_controle"],
  distancia_km_pj: ["sprints_pj", "corridas_av_pj"],
  sprints_pj: ["distancia_km_pj", "corridas_av_pj", "pressoes_def_pj"],
  corridas_av_pj: ["sprints_pj", "distancia_km_pj"],
  pressoes_def_pj: ["turnovers_forcados_pj", "sprints_pj"],
  score_disciplina: ["faltas_pj", "amarelos_pj", "vermelhos_pj"],
  faltas_pj: ["amarelos_pj", "vermelhos_pj", "score_disciplina"],
  amarelos_pj: ["faltas_pj", "vermelhos_pj", "score_disciplina"],
  vermelhos_pj: ["amarelos_pj", "faltas_pj", "score_disciplina"],
  score_forca_relativa: ["elo_rating", "aproveitamento", "pontos"],
  elo_rating: ["score_forca_relativa", "aproveitamento", "pontos"],
  score_geral: ["score_resultado", "score_ataque", "score_defesa", "score_eficiencia", "score_controle", "score_forca_relativa"],
};
const INDIRECT: Record<string, string[]> = {
  score_ataque: ["chutes_pj", "escanteios_pj", "impedimentos_pj"],
  chutes_no_alvo_pj: ["escanteios_pj", "chutes_pj"],
  gols_pj: ["chutes_pj", "escanteios_pj"],
  gols_pro: ["chutes_no_alvo_pj", "precisao_chutes"],
  score_eficiencia: ["chutes_pj", "escanteios_pj", "linebreaks_pj"],
  precisao_chutes: ["escanteios_pj", "threat_pj"],
  score_defesa: ["clean_sheet", "defesas_goleiro_pj", "faltas_pj"],
  gols_contra_pj: ["faltas_pj", "clean_sheet"],
  gols_contra: ["chutes_sofridos_pj", "faltas_pj"],
  score_controle: ["escanteios_pj", "dribles_pj", "linebreaks_pj"],
  posse: ["dribles_pj", "progressoes_pj"],
  passes_pj: ["escanteios_pj", "dribles_pj"],
  score_resultado: ["elo_rating", "score_forca_relativa"],
  aproveitamento: ["elo_rating"],
  saldo_gols: ["gols_pj", "gols_contra_pj"],
  score_forca_relativa: ["score_resultado", "aproveitamento"],
  elo_rating: ["score_resultado", "saldo_gols"],
  faltas_pj: ["escanteios_pj"],
  amarelos_pj: ["escanteios_pj", "faltas_pj"],
  escanteios_pj: ["score_ataque", "gols_pj", "chutes_pj"],
  chutes_pj: ["score_ataque", "gols_pj"],
  distancia_km_pj: ["score_defesa"],
  sprints_pj: ["score_ataque"],
  pressoes_def_pj: ["turnovers_forcados_pj"],
};

// campo do snapshot a ler para uma card-key, respeitando o modo. Em "total",
// métricas de contagem leem o acumulado; taxas e métricas sem total ignoram.
function snapField(key: string, mode: ValueMode): string {
  if (mode === "total" && TOTAL_FIELD[key]) return TOTAL_FIELD[key];
  return KEY_MAP[key] ?? key;
}
function snapVal(row: TeamSnapshot, key: string, mode: ValueMode = "pj"): number | null {
  const v = row[snapField(key, mode)];
  return typeof v === "number" ? v : null;
}
function formatVal(v: number | null, key: string): string {
  if (v === null) return "—";
  if (v === 0) return "0";
  if (PERCENT_FRAC.has(key)) return `${(v * 100).toFixed(0)}%`;
  if (PERCENT_DIRECT.has(key)) return `${v.toFixed(1)}%`;
  if (Number.isInteger(v) || Math.abs(v - Math.round(v)) < 0.005) return String(Math.round(v));
  return v.toFixed(1);
}

interface Props {
  team: string;
  rows: TeamSnapshot[];
  metric: string;
  color?: string | null;
  index?: number;
  onSelectMetric?: (metric: string) => void;
  syncArea?: boolean;
  sharedArea?: number;
  onAreaChange?: (area: number) => void;
  sharedMode?: ValueMode;
  onModeChange?: (m: ValueMode) => void;
  onToggleSync?: (on: boolean, area: number, mode: ValueMode) => void;
  onClose: () => void;
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export default function TeamScoresCard({ team, rows, metric, color, index = 0, onSelectMetric, syncArea = false, sharedArea, onAreaChange, sharedMode, onModeChange, onToggleSync, onClose }: Props) {
  const curKey = REVERSE[metric] ?? metric;
  const defaultArea = Math.max(0, METRIC_GROUPS.findIndex(([, , ms]) => ms.some(([k]) => k === curKey)));
  const [localArea, setLocalArea] = React.useState(defaultArea);
  const [mode, setMode] = React.useState<ValueMode>("pj");
  // com Sync ligado, o modo (por jogo/total) também vem do estado compartilhado
  const activeMode: ValueMode = syncArea && sharedMode != null ? sharedMode : mode;
  const setModeH = (m: ValueMode) => { if (syncArea) onModeChange?.(m); else setMode(m); };
  const [pos, setPos] = React.useState({ x: 80 + index * 34, y: 64 + index * 34 });
  const [size, setSize] = React.useState<{ w: number; h: number | null }>({ w: 600, h: null });
  const drag = React.useRef<{ dx: number; dy: number } | null>(null);
  const onDown = (e: React.PointerEvent) => { drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y }; (e.target as HTMLElement).setPointerCapture(e.pointerId); };
  const onMove = (e: React.PointerEvent) => { if (drag.current) setPos({ x: e.clientX - drag.current.dx, y: e.clientY - drag.current.dy }); };
  const onUp = () => { drag.current = null; };
  const rz = React.useRef<{ x: number; y: number; w: number; h: number } | null>(null);
  const onRzDown = (e: React.PointerEvent) => { e.stopPropagation(); rz.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h ?? (e.currentTarget.parentElement?.offsetHeight ?? 460) }; (e.target as HTMLElement).setPointerCapture(e.pointerId); };
  const onRzMove = (e: React.PointerEvent) => { if (!rz.current) return; setSize({ w: clamp(rz.current.w + (e.clientX - rz.current.x), 380, 1100), h: clamp(rz.current.h + (e.clientY - rz.current.y), 240, window.innerHeight * 0.92) }); };
  const onRzUp = () => { rz.current = null; };

  const row = rows.find((r) => r.team === team);
  // rank na MESMA direção da barra (desc: maior = 1º), com empate "="
  const rankOf = React.useCallback((key: string): { rank: number; tied: boolean } | null => {
    if (!row) return null;
    const me = snapVal(row, key, activeMode);
    if (me === null) return null;
    const vals = rows.map((r) => snapVal(r, key, activeMode)).filter((v): v is number => v !== null);
    const ahead = vals.filter((v) => v > me).length;
    const tied = vals.filter((v) => v === me).length > 1;
    return { rank: ahead + 1, tied };
  }, [rows, row, activeMode]);

  if (!row) return null;
  const related = new Set(RELATIONS[curKey] ?? []);
  const indirect = new Set(INDIRECT[curKey] ?? []);
  const hasRelated = related.size > 0, hasIndirect = indirect.size > 0;
  const geral = rankOf("score_geral");
  const jogos = typeof row.jogos === "number" ? row.jogos : 0;
  const accent = color ?? "#58a6ff";
  const total = METRIC_GROUPS.length;
  const activeArea = syncArea && sharedArea != null ? sharedArea : localArea;
  const safeArea = ((activeArea % total) + total) % total;
  const setAreaH = (i: number) => {
    const n = ((i % total) + total) % total;
    if (syncArea) onAreaChange?.(n); else setLocalArea(n);
  };
  const [areaTitle, areaCls, areaMetrics] = METRIC_GROUPS[safeArea];
  // sempre mostra todas as métricas do grupo (consistente entre seleções)
  const metrics = areaMetrics;
  // título reflete o modo só nos grupos alternáveis; Scores/Campanha ficam fixos
  const areaToggleable = MODE_GROUPS.has(areaCls);
  const displayTitle = areaToggleable
    ? `${areaTitle.split(" · ")[0]} · ${activeMode === "total" ? "Totais" : "Média/jogo"}`
    : areaTitle;

  return (
    <div style={{ position: "fixed", left: pos.x, top: pos.y, zIndex: 80, width: size.w, height: size.h ?? undefined, maxWidth: "96vw" }}>
      <div style={{ background: "#010409", border: "1px solid #30363d", borderRadius: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.55)", overflow: "hidden", height: "100%", display: "flex", flexDirection: "column", position: "relative" }}>
        {/* faixa de cor da seleção (distingue cards no multi-país) */}
        <div style={{ height: 3, background: accent, flexShrink: 0 }} />
        {/* cabeçalho (arrasta) */}
        <div onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
          style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: "#0d1117", borderBottom: "1px solid #21262d", cursor: "grab", touchAction: "none" }}>
          <Flag team={team} height={22} style={{ borderRadius: 3 }} />
          <span style={{ fontSize: 16, fontWeight: 800, color: "#f0f6fc" }}>{team}</span>
          <span style={{ fontSize: 12, color: "#8b949e" }}>
            {geral ? `#${geral.rank}${geral.tied ? "=" : ""} no ranking` : ""} · {jogos} {jogos === 1 ? "jogo" : "jogos"}
            <span style={{ marginLeft: 8, display: "inline-flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 9, height: 9, borderRadius: 2, background: accent }} />
              {METRIC_LABEL[metric] ?? "Score Geral"}
            </span>
          </span>
          <button
            onClick={() => onToggleSync?.(!syncArea, safeArea, activeMode)}
            onPointerDown={(e) => e.stopPropagation()}
            title={syncArea ? "Sync de área ligado — escolher área muda em todos os cards" : "Sync de área desligado"}
            style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, background: syncArea ? "#1f6feb24" : "transparent", border: `1px solid ${syncArea ? "#1f6feb88" : "#30363d"}`, color: syncArea ? "#79c0ff" : "#8b949e", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
          >
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: syncArea ? "#4ade80" : "#56606b" }} />
            Sync
          </button>
          <button onClick={onClose} onPointerDown={(e) => e.stopPropagation()} style={{ background: "none", border: "none", color: "#8b949e", fontSize: 20, cursor: "pointer", padding: 2, lineHeight: 1 }}>×</button>
        </div>

        {/* seletor de área: ‹ chips › */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "9px 10px 7px", borderBottom: "1px solid #161b22", flexShrink: 0 }}>
          <ArrowBtn dir="‹" onClick={() => setAreaH(safeArea - 1)} />
          <div style={{ display: "flex", gap: 4, overflowX: "auto", flex: 1, scrollbarWidth: "none" }}>
            {METRIC_GROUPS.map(([title], i) => {
              const short = title.split(" · ")[0];
              const on = i === safeArea;
              const relHere = METRIC_GROUPS[i][2].some(([k]) => related.has(k) || k === curKey);
              return (
                <button key={title} onClick={() => setAreaH(i)} title={title} style={{
                  border: 0, borderRadius: 6, padding: "4px 9px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap",
                  color: on ? "#fff" : "#8b949e", background: on ? accent : "#11161d",
                  boxShadow: on ? "none" : "inset 0 0 0 1px #21262d",
                  display: "inline-flex", alignItems: "center", gap: 5,
                }}>
                  {relHere && !on && <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#4ade80" }} />}
                  {short}
                </button>
              );
            })}
          </div>
          <ArrowBtn dir="›" onClick={() => setAreaH(safeArea + 1)} />
        </div>

        {/* área selecionada (um grupo, coluna única) */}
        <div style={{ padding: "8px 12px 10px", flex: 1, minHeight: 0, maxHeight: size.h == null ? "70vh" : undefined, overflowY: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4, minHeight: 22 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", color: accent }}>{displayTitle}</span>
            {areaToggleable && <ModeToggle mode={activeMode} onChange={setModeH} accent={accent} />}
          </div>
          {metrics.map(([key, label]) => {
            const v = snapVal(row, key, areaToggleable ? activeMode : "pj");
            const isActive = key === curKey;
            const isRel = !isActive && related.has(key);
            const isInd = !isActive && !isRel && indirect.has(key);
            const rk = rankOf(key);
            const medal = rk && !rk.tied ? (rk.rank === 1 ? "rk1" : rk.rank === 2 ? "rk2" : rk.rank === 3 ? "rk3" : "") : "";
            const isNeg = v !== null && v < 0;
            const rowBg = isActive ? "#1a2d50" : isRel ? "#1f2d1a" : isInd ? "#2a2510" : "transparent";
            const labelColor = isActive ? "#c8d3e0" : isRel ? "#86c98a" : isInd ? "#c9a84c" : "#9aa4af";
            const valColor = isActive ? "#58a6ff" : isRel ? "#4ade80" : isInd ? "#f0c040" : isNeg ? "#f85149" : "#e6edf3";
            // respeita o modo: em "Total" seleciona o campo acumulado (ex.: gols,
            // chutes), senão a média por jogo. Assim o card muda a Ranking Race.
            const snapKey = snapField(key, areaToggleable ? activeMode : "pj");
            const clickable = !!onSelectMetric && v !== null;
            return (
              <MetricRow
                key={key}
                label={label}
                defId={defIdFor(key)}
                isInput={SCORE_INPUT.has(key)}
                valueText={formatVal(v, key)}
                labelColor={labelColor}
                valColor={valColor}
                valWeight={isRel ? 600 : 700}
                tinted={isActive || isRel || isInd}
                rowBg={rowBg}
                rk={rk}
                medal={medal}
                clickable={clickable}
                onClick={clickable ? () => onSelectMetric!(snapKey) : undefined}
              />
            );
          })}
        </div>

        {/* legenda */}
        <div style={{ display: "flex", gap: 14, padding: "7px 12px 8px", borderTop: "1px solid #21262d", fontSize: 10, color: "#8b949e", flexWrap: "wrap", alignItems: "center", flexShrink: 0 }}>
          <span style={{ display: "flex", alignItems: "center" }}><span style={{ color: "#4a86d8", fontSize: 10, marginRight: 5 }}>▪</span>base do score geral</span>
          {hasRelated && <span style={{ display: "flex", alignItems: "center" }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "#4ade80", marginRight: 5 }} />relação direta com a métrica atual</span>}
          {hasIndirect && <span style={{ display: "flex", alignItems: "center" }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "#f0c040", marginRight: 5 }} />contexto/correlação</span>}
          <span style={{ marginLeft: "auto", color: "#56606b" }}>arraste o canto p/ redimensionar</span>
        </div>

        {/* alça de resize (canto inferior direito) */}
        <div
          onPointerDown={onRzDown} onPointerMove={onRzMove} onPointerUp={onRzUp}
          title="Arraste para redimensionar"
          style={{ position: "absolute", right: 2, bottom: 2, width: 16, height: 16, cursor: "nwse-resize", touchAction: "none", color: "#56606b", display: "flex", alignItems: "flex-end", justifyContent: "flex-end", fontSize: 12, lineHeight: 1, userSelect: "none" }}
        >◢</div>
      </div>
    </div>
  );
}

function MetricRow({ label, defId, isInput, valueText, labelColor, valColor, valWeight, tinted, rowBg, rk, medal, clickable, onClick }: {
  label: string; defId: string | null; isInput: boolean; valueText: string; labelColor: string; valColor: string; valWeight: number;
  tinted: boolean; rowBg: string; rk: { rank: number; tied: boolean } | null; medal: string; clickable: boolean; onClick?: () => void;
}) {
  const [hover, setHover] = React.useState(false);
  const bg = hover && clickable && !tinted ? "#161b22" : rowBg;
  return (
    <div
      role={clickable ? "button" : undefined}
      title={clickable ? `Ordenar a Ranking Race por ${label}` : undefined}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ display: "flex", justifyContent: "space-between", alignItems: "center", minHeight: 30, padding: "5px 8px", gap: 10, background: bg, borderRadius: 5, cursor: clickable ? "pointer" : "default", boxShadow: hover && clickable ? "inset 0 0 0 1px #30363d" : "none" }}
    >
      <span style={{ fontSize: 12.5, lineHeight: 1.18, color: labelColor, flex: 1, minWidth: 0 }}>
        {isInput && <span style={{ color: "#4a86d8", fontSize: 9, marginRight: 5, opacity: 0.85 }}>▪</span>}
        {label}
        {defId && <DefinitionBubble id={defId} size={13} />}
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 7, whiteSpace: "nowrap" }}>
        <span style={{ fontSize: 13, fontWeight: valWeight, color: valColor }}>{valueText}</span>
        {rk && <RankBadge rank={rk.rank} tied={rk.tied} medal={medal} />}
      </span>
    </div>
  );
}

function ModeToggle({ mode, onChange, accent }: { mode: ValueMode; onChange: (m: ValueMode) => void; accent: string }) {
  const opt = (m: ValueMode, label: string) => {
    const on = mode === m;
    return (
      <button onClick={() => onChange(m)} style={{
        border: 0, borderRadius: 5, padding: "2px 8px", fontSize: 10.5, fontWeight: 700, cursor: "pointer",
        fontFamily: "inherit", whiteSpace: "nowrap", lineHeight: 1.5,
        color: on ? "#fff" : "#8b949e", background: on ? accent : "transparent",
      }}>{label}</button>
    );
  };
  return (
    <div title="Taxas (%, razões) não mudam entre os modos" style={{ display: "inline-flex", gap: 2, background: "#11161d", border: "1px solid #21262d", borderRadius: 7, padding: 2, flexShrink: 0 }}>
      {opt("pj", "Por jogo")}
      {opt("total", "Total")}
    </div>
  );
}

function ArrowBtn({ dir, onClick }: { dir: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ flexShrink: 0, width: 24, height: 24, borderRadius: 6, border: "1px solid #21262d", background: "#11161d", color: "#8b949e", cursor: "pointer", fontSize: 15, lineHeight: 1, fontFamily: "inherit", display: "flex", alignItems: "center", justifyContent: "center" }}>{dir}</button>
  );
}

function RankBadge({ rank, tied, medal }: { rank: number; tied: boolean; medal: string }) {
  const base: React.CSSProperties = { fontSize: 9.5, fontWeight: 800, color: "#8b949e", background: "#21262d", border: "1px solid #30363d", borderRadius: 4, padding: "0 4px", minWidth: 22, textAlign: "center" };
  if (medal === "rk1") Object.assign(base, { color: "#1b1b1b", background: "#f5c542", borderColor: "#f5c542" });
  else if (medal === "rk2") Object.assign(base, { color: "#1b1b1b", background: "#c0c0c0", borderColor: "#c0c0c0" });
  else if (medal === "rk3") Object.assign(base, { color: "#1b1b1b", background: "#cd7f32", borderColor: "#cd7f32" });
  return <span style={base}>{rank}º{tied ? "=" : ""}</span>;
}
