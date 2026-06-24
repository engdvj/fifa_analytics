"use client";

import { useState, useRef } from "react";
import { LineupPlayer, MatchEvent } from "@/lib/api";
import { getKit, KitColors } from "@/lib/teamUtils";
import { DefinitionBubble } from "@/components/DefinitionLink";

// Chave de stat FIFA (linha de seção) → id de definição. Só as que têm conceito.
const STAT_DEF_ID: Record<string, string> = {
  XG: "xg",
  Threat: "threat",
  Sprints: "sprints",
  ForcedTurnovers: "turnovers_forcados",
  DefensivePressuresApplied: "pressao_defensiva",
  CompletedBallProgressions: "progressoes_bola",
};

const W = 820;
const H = 520;
const PAD = 30;
// largura máxima de exibição (compacta o campo dentro do modal; os dots escalam junto)
const DISPLAY_MAX = 700;

// Layout por formação quando a FIFA não manda coordenadas (lineup_x/y nulos):
// agrupa por linha (G/D/M/F) e distribui cada linha uniformemente, sem sobrepor.
// dx = espalhamento lateral (0-100), dy = profundidade (0=gol → 100=meio).
function computeLayout(starters: LineupPlayer[]): Map<string, [number, number]> {
  const lines: Record<string, LineupPlayer[]> = { G: [], D: [], M: [], F: [] };
  for (const p of starters) {
    const c = (p.position ?? "M").toUpperCase()[0];
    (lines[c] ?? lines.M).push(p);
  }
  const depth: Record<string, number> = { G: 8, D: 28, M: 52, F: 78 };
  const out = new Map<string, [number, number]>();
  (["G", "D", "M", "F"] as const).forEach((key) => {
    const arr = lines[key];
    const n = arr.length;
    // ordena por camisa pra dar uma ordem estável esquerda→direita
    arr.sort((a, b) => (a.shirt_number ?? 99) - (b.shirt_number ?? 99));
    arr.forEach((p, i) => {
      // margens iguais nas laterais (estilo legacy): 100/(n+1) por jogador
      const dx = n === 1 ? 50 : (100 / (n + 1)) * (i + 1);
      out.set(p.id_player, [dx, depth[key]]);
    });
  });
  return out;
}

function toSVG(
  lx: number | null,
  ly: number | null,
  fallback: [number, number],
  side: "home" | "away"
): [number, number] {
  const [dx, dy] = lx != null && ly != null ? [lx, ly] : fallback;

  const svgY = PAD + (dx / 100) * (H - PAD * 2);

  if (side === "home") {
    const svgX = PAD + (dy / 100) * (W / 2 - PAD);
    return [svgX, svgY];
  }
  const svgX = W - PAD - (dy / 100) * (W / 2 - PAD);
  return [svgX, svgY];
}

// Formação a partir dos titulares (ex.: 4 D + 3 M + 3 F → "4-3-3").
function formationOf(starters: LineupPlayer[]): string {
  let d = 0, m = 0, f = 0;
  for (const p of starters) {
    const pos = (p.position ?? "").toUpperCase();
    if (pos.startsWith("G")) continue;
    if (pos.startsWith("D")) d++;
    else if (pos.startsWith("F")) f++;
    else m++;
  }
  return d + m + f === 10 ? `${d}-${m}-${f}` : "";
}

interface PitchViewProps {
  homePlayers: LineupPlayer[];
  awayPlayers: LineupPlayer[];
  homeTeam: string;
  awayTeam: string;
  events: MatchEvent[];
  homeIdTeam: string;
  playerStats?: Map<string, Record<string, number>>;
  playerScores?: Map<string, number>;
}

// Seções do card por POSIÇÃO (só métricas FIFA-disponíveis por jogador).
type Section = { title: string; rows: [string, string, number?][] };
const DISC: Section = { title: "Disciplina", rows: [["FoulsAgainst", "Faltas"], ["FoulsFor", "Sofridas"], ["YellowCards", "Amarelos"], ["RedCards", "Vermelhos"]] };
const SECTIONS_BY_POS: Record<string, Section[]> = {
  G: [
    { title: "Ações do goleiro", rows: [["GoalkeeperSaves", "Defesas"], ["GoalsConceded", "Gols sofridos"], ["DefensivePressuresApplied", "Pressões"], ["Sprints", "Sprints"]] },
    { title: "Distribuição", rows: [["Passes", "Passes"], ["PassesCompleted", "Certos"], ["NumberOfShotEndingSequences", "p/ chute"], ["CompletedBallProgressions", "Progressões"]] },
    DISC,
  ],
  D: [
    { title: "Defesa", rows: [["ForcedTurnovers", "Desarmes"], ["DefensivePressuresApplied", "Pressões"], ["TakeOnsCompleted", "Dribles"], ["Crosses", "Cruzamentos"]] },
    { title: "Construção", rows: [["Passes", "Passes"], ["PassesCompleted", "Certos"], ["CompletedBallProgressions", "Progressões"]] },
    { title: "Ataque / Físico", rows: [["Goals", "Gols"], ["AttemptAtGoal", "Finalizações"], ["Sprints", "Sprints"]] },
    DISC,
  ],
  M: [
    { title: "Criação", rows: [["Assists", "Assistências"], ["NumberOfShotEndingSequences", "Passes p/ chute"], ["TakeOnsCompleted", "Dribles"], ["Crosses", "Cruzamentos"]] },
    { title: "Controle", rows: [["Passes", "Passes"], ["PassesCompleted", "Certos"], ["CompletedBallProgressions", "Progressões"]] },
    { title: "Defesa / Físico", rows: [["ForcedTurnovers", "Desarmes"], ["DefensivePressuresApplied", "Pressões"], ["Sprints", "Sprints"]] },
    { title: "Finalização", rows: [["Goals", "Gols"], ["XG", "xG", 2], ["AttemptAtGoalOnTarget", "No alvo"]] },
    DISC,
  ],
  F: [
    { title: "Finalização", rows: [["Goals", "Gols"], ["AttemptAtGoal", "Finalizações"], ["AttemptAtGoalOnTarget", "No alvo"], ["XG", "xG", 2], ["Threat", "Ameaça", 2]] },
    { title: "Criação", rows: [["Assists", "Assistências"], ["NumberOfShotEndingSequences", "Passes p/ chute"], ["TakeOnsCompleted", "Dribles"]] },
    { title: "Físico / Defesa", rows: [["Sprints", "Sprints"], ["ForcedTurnovers", "Desarmes"], ["DefensivePressuresApplied", "Pressões"]] },
    DISC,
  ],
};

const POS_LABEL: Record<string, string> = { G: "Goleiro", D: "Defensor", M: "Meia", F: "Atacante" };

export default function PitchView({
  homePlayers,
  awayPlayers,
  homeTeam,
  awayTeam,
  events,
  playerStats,
  playerScores,
}: PitchViewProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  // Toggle: clicar abre; clicar de novo no mesmo jogador fecha o card.
  const togglePlayer = (id: string) => setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const homeKit = getKit(homeTeam);
  const awayKit = getKit(awayTeam);

  const isCard = (e: MatchEvent, kind: "yellow" | "red") => {
    if (e.event_type !== "card") return false;
    const d = (e.detail ?? "").toLowerCase();
    return kind === "yellow" ? (d.includes("yellow") || d.includes("amarelo")) : (d.includes("red") || d.includes("vermelho"));
  };
  const goalPlayers = new Set(events.filter(e => e.event_type === "goal").map(e => e.id_player));
  const yellowCards = new Set(events.filter(e => isCard(e, "yellow")).map(e => e.id_player));
  const redCards = new Set(events.filter(e => isCard(e, "red")).map(e => e.id_player));

  // Substituições: quem SAIU (id_player) ↔ quem ENTROU (id_player2), com minuto.
  const subInMinute = new Map<string, string>();
  const subOut = new Map<string, { min: string; inId: string | null }>();
  const subPair = new Map<string, { partnerId: string; min: string; dir: "in" | "out" }>();
  for (const e of events) {
    if (e.event_type === "substitution") {
      if (e.id_player2) subInMinute.set(e.id_player2, e.minute ?? "?");
      if (e.id_player) subOut.set(e.id_player, { min: e.minute ?? "?", inId: e.id_player2 ?? null });
      if (e.id_player && e.id_player2) {
        subPair.set(e.id_player, { partnerId: e.id_player2, min: e.minute ?? "?", dir: "out" });
        subPair.set(e.id_player2, { partnerId: e.id_player, min: e.minute ?? "?", dir: "in" });
      }
    }
  }
  const nameById = new Map<string, string>();
  for (const p of [...homePlayers, ...awayPlayers]) if (p.player_name) nameById.set(p.id_player, p.player_name);

  const starters = {
    home: homePlayers.filter(p => p.is_starter),
    away: awayPlayers.filter(p => p.is_starter),
  };
  const subs = {
    home: homePlayers.filter(p => !p.is_starter),
    away: awayPlayers.filter(p => !p.is_starter),
  };
  const homeFormation = formationOf(starters.home);
  const awayFormation = formationOf(starters.away);
  const homeLayout = computeLayout(starters.home);
  const awayLayout = computeLayout(starters.away);

  function renderPlayer(p: LineupPlayer, side: "home" | "away") {
    const layout = side === "home" ? homeLayout : awayLayout;
    const fallback = layout.get(p.id_player) ?? [50, 50];
    const [cx, cy] = toSVG(p.lineup_x, p.lineup_y, fallback, side);
    const isHovered = hovered === p.id_player;
    const isSelected = selectedIds.includes(p.id_player);
    const dimmed = selectedIds.length > 0 && !isSelected;
    const kit = side === "home" ? homeKit : awayKit;
    const r = isHovered || isSelected ? 17 : 14;

    return (
      <g
        key={p.id_player}
        onMouseEnter={() => setHovered(p.id_player)}
        onMouseLeave={() => setHovered(null)}
        onClick={() => togglePlayer(p.id_player)}
        style={{ cursor: "pointer", opacity: dimmed ? 0.35 : 1, transition: "opacity 0.2s" }}
      >
        {/* halo de destaque do jogador selecionado */}
        {isSelected && (
          <>
            <circle cx={cx} cy={cy} r={r + 8} fill="#f5c54222" />
            <circle cx={cx} cy={cy} r={r + 3} fill="none" stroke="#f5c542" strokeWidth={3} />
          </>
        )}
        <circle
          cx={cx} cy={cy} r={r}
          fill={kit.main}
          stroke={isSelected ? "#f5c542" : isHovered ? "#58a6ff" : kit.border}
          strokeWidth={isSelected ? 3 : isHovered ? 2.5 : 2}
          style={{ transition: "r 0.12s, stroke 0.12s" }}
        />
        <text x={cx} y={cy + 4} textAnchor="middle" fill={kit.text} fontSize={11} fontWeight="800">
          {p.shirt_number ?? "?"}
        </text>
        {/* Nome em pílula escura — legível sobre o gramado */}
        {(() => {
          const parts = (p.player_name ?? "").trim().split(" ");
          const first = parts.length > 1 ? parts[0] : "";
          const last = (parts[parts.length - 1] ?? "").slice(0, 16);
          const fs = 10;
          const maxChars = Math.max(first.length, last.length);
          const pillW = Math.max(maxChars * fs * 0.56 + 10, 30);
          const pillH = (first ? 2 * fs + 7 : fs + 7);
          const top = cy + r + 3;
          return (
            <g>
              <rect x={cx - pillW / 2} y={top} width={pillW} height={pillH} rx={4} fill="rgba(8,16,12,0.82)" />
              {first && (
                <text x={cx} y={top + fs} textAnchor="middle" fill="#aeb9c7" fontSize={fs - 2.5}>{first}</text>
              )}
              <text x={cx} y={top + (first ? 2 * fs + 1 : fs + 2)} textAnchor="middle" fill="#ffffff" fontSize={fs} fontWeight="700">{last}</text>
            </g>
          );
        })()}
        {p.captain && (
          <text x={cx + r - 2} y={cy - r + 8} fontSize={11} fill="#fbbf24" fontWeight="700">©</text>
        )}
        {goalPlayers.has(p.id_player) && (
          <text x={cx + r - 1} y={cy - r + 7} fontSize={13}>⚽</text>
        )}
        {yellowCards.has(p.id_player) && !redCards.has(p.id_player) && (
          <text x={cx + r - 1} y={cy + 5} fontSize={13}>🟨</text>
        )}
        {redCards.has(p.id_player) && (
          <text x={cx + r - 1} y={cy + 5} fontSize={13}>🟥</text>
        )}
        {/* Substituído: 🔄 + minuto. Clicar abre quem ENTROU. */}
        {subOut.has(p.id_player) && (() => {
          const sub = subOut.get(p.id_player)!;
          return (
            <g onClick={(e) => { e.stopPropagation(); if (sub.inId) togglePlayer(sub.inId); }} style={{ cursor: sub.inId ? "pointer" : "default" }}>
              <circle cx={cx - r + 1} cy={cy - r + 3} r={9} fill="#0b1f12cc" stroke="#3b82f6" strokeWidth={1.5} />
              <text x={cx - r + 1} y={cy - r + 7} fontSize={11} textAnchor="middle">🔄</text>
              <text x={cx - r - 1} y={cy + r + 1} fontSize={9} textAnchor="end" fill="#fca5a5" stroke="#0b1f12" strokeWidth={1.8} style={{ paintOrder: "stroke" }} fontWeight="700">{sub.min}</text>
            </g>
          );
        })()}
        {isHovered && (
          <g>
            <rect x={cx - 58} y={cy - 48} width={116} height={20} rx={4}
              fill="#21262d" stroke="#30363d" strokeWidth={1} />
            <text x={cx} y={cy - 34} textAnchor="middle" fill="#e6edf3" fontSize={10}>
              {p.player_name ?? "?"} {p.captain ? "©" : ""}
            </text>
          </g>
        )}
      </g>
    );
  }

  const allPlayers = [...homePlayers, ...awayPlayers];

  return (
    <div>
      <div style={{ position: "relative", maxWidth: DISPLAY_MAX, margin: "0 auto" }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", maxWidth: DISPLAY_MAX, display: "block", margin: "0 auto", borderRadius: 8 }}
      >
        <defs>
          <pattern id="pitch-stripes" patternUnits="userSpaceOnUse" width="100%" height={H / 9}>
            <rect width="100%" height={H / 9} fill="#166534" />
            <rect y={H / 18} width="100%" height={H / 18} fill="#14532d" />
          </pattern>
        </defs>

        {/* Grass with stripes */}
        <rect width={W} height={H} fill="url(#pitch-stripes)" rx={8} />
        {/* Escurece o campo quando há jogador selecionado (foco no destaque) */}
        {selectedIds.length > 0 && (
          <rect width={W} height={H} fill="rgba(0,0,0,0.5)" rx={8} style={{ transition: "opacity 0.2s" }} />
        )}

        {/* Pitch lines */}
        <rect x={PAD} y={PAD} width={W - PAD * 2} height={H - PAD * 2}
          fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD}
          stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <circle cx={W / 2} cy={H / 2} r={H * 0.13}
          fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
        <circle cx={W / 2} cy={H / 2} r={4} fill="rgba(255,255,255,0.4)" />

        {/* Penalty areas */}
        <rect x={PAD} y={H / 2 - H * 0.17} width={W * 0.13} height={H * 0.34}
          fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth={1} />
        <rect x={W - PAD - W * 0.13} y={H / 2 - H * 0.17} width={W * 0.13} height={H * 0.34}
          fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth={1} />
        {/* Goals */}
        <rect x={PAD - 14} y={H / 2 - H * 0.075} width={14} height={H * 0.15}
          fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth={1.5} />
        <rect x={W - PAD} y={H / 2 - H * 0.075} width={14} height={H * 0.15}
          fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth={1.5} />

        {/* Team labels + formação */}
        <text x={PAD + 10} y={PAD + 16} fill="rgba(255,255,255,0.6)" fontSize={10} fontWeight="700">
          {homeTeam}{homeFormation ? `  ${homeFormation}` : ""}
        </text>
        <text x={W - PAD - 10} y={PAD + 16} textAnchor="end" fill="rgba(255,255,255,0.6)" fontSize={10} fontWeight="700">
          {awayFormation ? `${awayFormation}  ` : ""}{awayTeam}
        </text>

        {/* Players */}
        {starters.home.map((p) => renderPlayer(p, "home"))}
        {starters.away.map((p) => renderPlayer(p, "away"))}
      </svg>

      {/* Cards de detalhe do jogador (clique no campo) — vários, arrastáveis */}
      {selectedIds.map((id, i) => {
        const p = allPlayers.find(x => x.id_player === id);
        if (!p) return null;
        const pair = subPair.get(id);
        const subInfo = pair ? { dir: pair.dir, min: pair.min, partnerName: nameById.get(pair.partnerId) ?? "?", onGo: () => togglePlayer(pair.partnerId) } : null;
        // lado pela LISTA em que o jogador está (homePlayers = esquerda), não pelo
        // team_side original — os lados podem estar invertidos p/ o time do modal.
        const isHomeSide = homePlayers.some(x => x.id_player === id);
        return (
          <PlayerDetailCard
            key={id}
            player={p}
            stats={playerStats?.get(id) ?? {}}
            score={playerScores?.get(id) ?? null}
            kit={getKit(isHomeSide ? homeTeam : awayTeam)}
            index={i}
            sub={subInfo}
            onClose={() => setSelectedIds(prev => prev.filter(x => x !== id))}
          />
        );
      })}
      </div>

      {/* Reservas dos dois times (a linha do tempo virou sub-aba própria) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 16, alignItems: "start", maxWidth: DISPLAY_MAX, marginLeft: "auto", marginRight: "auto" }}>
        <ReservesCol title={homeTeam} subs={subs.home} subInMinute={subInMinute} align="left" onSelect={togglePlayer} goalPlayers={goalPlayers} yellowCards={yellowCards} redCards={redCards} />
        <ReservesCol title={awayTeam} subs={subs.away} subInMinute={subInMinute} align="right" onSelect={togglePlayer} goalPlayers={goalPlayers} yellowCards={yellowCards} redCards={redCards} />
      </div>
    </div>
  );
}

function ReservesCol({ title, subs, subInMinute, align, onSelect, goalPlayers, yellowCards, redCards }: { title: string; subs: LineupPlayer[]; subInMinute: Map<string, string>; align: "left" | "right"; onSelect: (id: string) => void; goalPlayers: Set<string>; yellowCards: Set<string>; redCards: Set<string> }) {
  return (
    <div>
      <p style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8, textAlign: align }}>
        Reservas · {title}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {subs.length === 0 && <span style={{ fontSize: 11, color: "var(--text-muted)", textAlign: align }}>—</span>}
        {subs.map(p => {
          const minute = subInMinute.get(p.id_player);
          return (
            <button
              key={p.id_player}
              onClick={() => onSelect(p.id_player)}
              title="Ver detalhes do jogador"
              style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: align === "right" ? "flex-end" : "flex-start", fontSize: 11, color: minute ? "var(--green)" : "var(--text-muted)", background: "none", border: "none", cursor: "pointer", padding: "1px 3px", borderRadius: 4, fontFamily: "inherit", textAlign: align }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface2)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              {align === "left" && <span style={{ opacity: 0.7, minWidth: 16 }}>{p.shirt_number ?? ""}</span>}
              <span style={{ color: "var(--text)" }}>{p.player_name}</span>
              {(goalPlayers.has(p.id_player) || yellowCards.has(p.id_player) || redCards.has(p.id_player)) && (
                <span style={{ fontSize: 10, display: "inline-flex", gap: 2 }}>
                  {goalPlayers.has(p.id_player) && <span>⚽</span>}
                  {redCards.has(p.id_player) ? <span>🟥</span> : yellowCards.has(p.id_player) ? <span>🟨</span> : null}
                </span>
              )}
              {minute && <span>↑{minute}</span>}
              {align === "right" && <span style={{ opacity: 0.7, minWidth: 16, textAlign: "right" }}>{p.shirt_number ?? ""}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PlayerDetailCard({ player, stats, score, kit, index, sub, onClose }: { player: LineupPlayer; stats: Record<string, number>; score: number | null; kit: KitColors; index: number; sub: { dir: "in" | "out"; min: string; partnerName: string; onGo: () => void } | null; onClose: () => void }) {
  const posKey = (player.position ?? "M").toUpperCase()[0];
  const posLabel = POS_LABEL[posKey] ?? player.position ?? "";
  const sections = SECTIONS_BY_POS[posKey] ?? SECTIONS_BY_POS.M;
  const num = (k: string) => stats[k] ?? 0;
  const isGK = posKey === "G";
  const pr = score != null ? score.toFixed(1) : "—"; // Power Ranking FIFA (oficial, parcial)
  // position: fixed (relativo à viewport) → não é cortado pelo overflow do modal
  // e pode ser arrastado pra fora da área.
  const [pos, setPos] = useState({ x: 90 + index * 30, y: 96 + index * 30 });
  const drag = useRef<{ px: number; py: number; x: number; y: number } | null>(null);

  return (
    <div style={{ position: "fixed", left: pos.x, top: pos.y, width: 340, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, boxShadow: "0 16px 48px rgba(0,0,0,0.65)", zIndex: 200 + index }}>
      {/* Header (arrastável) */}
      <div
        onPointerDown={(e) => { drag.current = { px: e.clientX, py: e.clientY, x: pos.x, y: pos.y }; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => { if (drag.current) setPos({ x: drag.current.x + (e.clientX - drag.current.px), y: drag.current.y + (e.clientY - drag.current.py) }); }}
        onPointerUp={() => { drag.current = null; }}
        style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 11px", borderBottom: "1px solid var(--border)", cursor: "grab", touchAction: "none" }}
      >
        <span style={{ width: 26, height: 26, borderRadius: 6, background: kit.main, color: kit.text, border: `2px solid ${kit.border}`, display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, flexShrink: 0 }}>{player.shirt_number ?? "?"}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{player.player_name}{player.captain ? " ©" : ""}</div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{posLabel}{player.is_starter === false ? " · reserva" : ""}</div>
        </div>
        {/* Power Ranking FIFA (oficial, só ~244 jogadores) */}
        <div style={{ textAlign: "center", flexShrink: 0, marginRight: 2 }} title="Power Ranking FIFA (oficial · parcial)">
          <div style={{ fontSize: 16, fontWeight: 800, color: "var(--accent)", lineHeight: 1 }}>{pr}</div>
          <div style={{ fontSize: 8, color: "var(--text-muted)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
            PR FIFA
            <DefinitionBubble id="powerranking" size={11} />
          </div>
        </div>
        <button onClick={onClose} onPointerDown={(e) => e.stopPropagation()} style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: 17, cursor: "pointer", lineHeight: 1, padding: 0 }}>×</button>
      </div>
      {/* Link da substituição — pula pro jogador da troca */}
      {sub && (
        <button
          onClick={sub.onGo}
          style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "7px 12px", background: "#161b22", border: "none", borderBottom: "1px solid var(--border)", cursor: "pointer", fontFamily: "inherit", fontSize: 12, color: "var(--text-muted)", textAlign: "left" }}
        >
          <span>🔄</span>
          <span>{sub.dir === "out" ? "Saiu" : "Entrou"} aos {sub.min} ·</span>
          <span style={{ color: "var(--accent)", fontWeight: 700 }}>ver {sub.partnerName}</span>
          <span style={{ marginLeft: "auto", color: "var(--accent)" }}>›</span>
        </button>
      )}
      <div style={{ padding: "10px 13px" }}>
        {sections.map(sec => (
          <div key={sec.title} style={{ marginBottom: 9 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 5 }}>{sec.title}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 16px" }}>
              {sec.rows.map(([k, label, dec]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
                  <span style={{ color: "var(--text-muted)", display: "inline-flex", alignItems: "center" }}>
                    {label}
                    {STAT_DEF_ID[k] && <DefinitionBubble id={STAT_DEF_ID[k]} size={12} />}
                  </span>
                  <span style={{ color: "var(--text)", fontWeight: 600 }}>{dec ? num(k).toFixed(dec) : Math.round(num(k))}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
