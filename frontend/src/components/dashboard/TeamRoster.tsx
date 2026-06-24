"use client";

import React from "react";
import { PlayerSnapshot } from "@/lib/api";
import { KitColors } from "@/lib/teamUtils";
import { DefinitionBubble } from "@/components/DefinitionLink";

// Chave de stat do jogador → id de definição (só as que têm conceito).
const STAT_DEF_ID: Record<string, string> = {
  expected_goals: "xg",
  score_geral: "powerranking", // exibido como "PR FIFA" (Power Ranking oficial)
};

interface Props {
  players: PlayerSnapshot[];
  loading: boolean;
  kit: KitColors;
}

function num(p: PlayerSnapshot, key: string): number {
  const v = p[key];
  return typeof v === "number" ? v : 0;
}

// Líderes — só métricas que a FIFA fornece por jogador (sem xA/xGP).
const LEADERS: { key: string; label: string; dec?: number }[] = [
  { key: "goals", label: "Gols" },
  { key: "expected_goals", label: "xG", dec: 2 },
  { key: "key_passes", label: "Passes-chave" },
  { key: "tackles_won", label: "Desarmes" },
  { key: "saves", label: "Defesas" },
  { key: "score_geral", label: "PR FIFA", dec: 1 },
];

const PERFIL_ORDER: { key: string; label: string }[] = [
  { key: "goleiro", label: "Goleiros" },
  { key: "defensor", label: "Defensores" },
  { key: "meio", label: "Meias" },
  { key: "atacante", label: "Atacantes" },
];

// Stats mostradas no card de detalhe (todas FIFA-disponíveis).
const DETAIL_STATS: { key: string; label: string; dec?: number }[] = [
  { key: "goals", label: "Gols" },
  { key: "assists", label: "Assist." },
  { key: "expected_goals", label: "xG", dec: 2 },
  { key: "key_passes", label: "Passes-chave" },
  { key: "dribbles_won", label: "Dribles" },
  { key: "tackles_won", label: "Desarmes" },
  { key: "interceptions", label: "Intercept." },
  { key: "ball_recovery", label: "Recuperações" },
  { key: "duels_won", label: "Duelos" },
  { key: "saves", label: "Defesas" },
  { key: "fouls_committed", label: "Faltas" },
  { key: "yellow_cards", label: "Amarelos" },
];

// Camisa (SVG): silhueta em `border` (mangas + gola contrastantes) e o torso em
// `main`. Usa só as 2 cores que o kit já tem — sem assets, mas com cara de
// uniforme (corpo + mangas de cores diferentes). Não é o kit oficial 2026.
function Jersey({ number, kit, size = 58 }: { number: number | string; kit: KitColors; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ display: "block" }} aria-hidden>
      {/* silhueta inteira (vira as mangas + a gola, na cor de contraste) */}
      <path
        d="M20 6 L28 9 Q32 13 36 9 L44 6 L58 16 L49 28 L46 23 L46 58 L18 58 L18 23 L15 28 L6 16 Z"
        fill={kit.border}
        strokeLinejoin="round"
      />
      {/* torso (corpo da camisa, na cor principal — deixa as mangas aparecerem) */}
      <path
        d="M21 8 L28 11 Q32 14.5 36 11 L43 8 L46 19 L46 57 L18 57 L18 19 Z"
        fill={kit.main}
      />
      <text x="32" y="44" textAnchor="middle" fill={kit.text} fontSize="19" fontWeight="800">
        {number}
      </text>
    </svg>
  );
}

export default function TeamRoster({ players, loading, kit }: Props) {
  // vários cards abertos ao mesmo tempo (toggle por jogador), como no campo
  const [openIds, setOpenIds] = React.useState<string[]>([]);
  const toggle = (id: string) => setOpenIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  if (loading) return <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Carregando elenco…</p>;
  if (!players || players.length === 0) {
    return <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Sem dados de elenco neste momento (a seleção ainda não jogou).</p>;
  }

  const leaders = LEADERS.map((l) => {
    let best: PlayerSnapshot | null = null;
    for (const p of players) if (num(p, l.key) > (best ? num(best, l.key) : 0)) best = p;
    return { ...l, best, value: best ? num(best, l.key) : 0 };
  }).filter((l) => l.best && l.value > 0);

  const byPerfil = PERFIL_ORDER.map((g) => ({
    ...g,
    list: players
      .filter((p) => (p.perfil ?? "").toLowerCase() === g.key)
      .sort((a, b) => (b.score_geral ?? 0) - (a.score_geral ?? 0)),
  })).filter((g) => g.list.length > 0);

  return (
    <div>
      {/* Líderes de estatística */}
      {leaders.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginBottom: 18 }}>
          {leaders.map((l) => (
            <div key={l.key} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px" }}>
              <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", display: "inline-flex", alignItems: "center" }}>
                {l.label}
                {STAT_DEF_ID[l.key] && <DefinitionBubble id={STAT_DEF_ID[l.key]} size={13} />}
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 3 }}>
                <span style={{ fontSize: 18, fontWeight: 800, color: "var(--accent)" }}>
                  {l.dec ? l.value.toFixed(l.dec) : Math.round(l.value)}
                </span>
                <span style={{ fontSize: 11, color: "var(--text)" }}>
                  {l.best?.player_name}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Jogadores por posição — tiles em formato de camisa */}
      {byPerfil.map((g) => (
        <div key={g.key} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            {g.label} · {g.list.length}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(116px, 1fr))", gap: 10 }}>
            {g.list.map((p) => {
              const id = p.player_slug ?? p.id_player;
              const open = openIds.includes(id);
              const baseBorder = open ? kit.main + "cc" : "var(--border)";
              const primary = g.key === "goleiro" ? num(p, "saves") : g.key === "atacante" ? num(p, "goals") : num(p, "tackles_won");
              const primaryLabel = g.key === "goleiro" ? "def." : g.key === "atacante" ? "gols" : "desarmes";
              return (
                <button
                  key={id}
                  onClick={() => toggle(id)}
                  title={`Ver detalhes de ${p.player_name}`}
                  style={{
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 5,
                    padding: "10px 6px 9px", background: open ? "var(--surface)" : "var(--surface2)", border: `1px solid ${baseBorder}`,
                    borderRadius: 10, cursor: "pointer", fontFamily: "inherit", transition: "border-color 0.15s, background 0.15s",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = kit.main + "88"; e.currentTarget.style.background = "var(--surface)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = baseBorder; e.currentTarget.style.background = open ? "var(--surface)" : "var(--surface2)"; }}
                >
                  <div style={{ position: "relative" }}>
                    <Jersey number={p.shirt_number ?? "?"} kit={kit} size={58} />
                    {p.score_geral != null && (
                      <span style={{ position: "absolute", top: -3, right: -7, background: "var(--accent)", color: "#fff", fontSize: 10, fontWeight: 800, borderRadius: 9, padding: "1px 5px", boxShadow: "0 1px 4px rgba(0,0,0,0.4)" }}>
                        {p.score_geral.toFixed(0)}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", textAlign: "center", lineHeight: 1.2 }}>{p.player_name}</span>
                  <span style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{Math.round(primary)} {primaryLabel}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {openIds.map((id, i) => {
        const p = players.find((pl) => (pl.player_slug ?? pl.id_player) === id);
        if (!p) return null;
        return <PlayerCard key={id} player={p} kit={kit} index={i} onClose={() => toggle(id)} />;
      })}
    </div>
  );
}

// Card flutuante de detalhe — arrastável e múltiplo (vários abertos), igual ao
// card do jogador no campo. position:fixed + header que arrasta; sem backdrop.
function PlayerCard({ player, kit, index, onClose }: { player: PlayerSnapshot; kit: KitColors; index: number; onClose: () => void }) {
  const perfil = (player.perfil ?? "").toString();
  const [pos, setPos] = React.useState({ x: 120 + index * 28, y: 120 + index * 28 });
  const drag = React.useRef<{ px: number; py: number; x: number; y: number } | null>(null);
  return (
    <div style={{ position: "fixed", left: pos.x, top: pos.y, width: 360, maxWidth: "92vw", maxHeight: "82vh", overflowY: "auto", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, boxShadow: "0 22px 64px rgba(0,0,0,0.62)", zIndex: 300 + index }}>
      {/* Header arrastável: camisa + nome + PR FIFA + fechar */}
      <div
        onPointerDown={(e) => { drag.current = { px: e.clientX, py: e.clientY, x: pos.x, y: pos.y }; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => { if (drag.current) setPos({ x: drag.current.x + (e.clientX - drag.current.px), y: drag.current.y + (e.clientY - drag.current.py) }); }}
        onPointerUp={() => { drag.current = null; }}
        style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderBottom: "1px solid var(--border)", cursor: "grab", touchAction: "none", position: "sticky", top: 0, background: "var(--surface)" }}
      >
        <Jersey number={player.shirt_number ?? "?"} kit={kit} size={42} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>{player.player_name}</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "capitalize" }}>{perfil}</div>
        </div>
        {player.score_geral != null && (
          <div style={{ textAlign: "center", flexShrink: 0 }} title="Power Ranking FIFA (oficial · parcial)">
            <div style={{ fontSize: 17, fontWeight: 800, color: "var(--accent)", lineHeight: 1 }}>{player.score_geral.toFixed(1)}</div>
            <div style={{ fontSize: 8, color: "var(--text-muted)", display: "inline-flex", alignItems: "center" }}>PR FIFA<DefinitionBubble id="powerranking" size={11} /></div>
          </div>
        )}
        <button onClick={onClose} onPointerDown={(e) => e.stopPropagation()} style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: 19, cursor: "pointer", lineHeight: 1, padding: 0, flexShrink: 0 }}>×</button>
      </div>
      {/* Grid de stats */}
      <div style={{ padding: "13px 15px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "11px 8px" }}>
        <Stat label="Jogos" value={Math.round(num(player, "jogos"))} />
        {DETAIL_STATS.map((s) => {
          const v = num(player, s.key);
          if (v === 0 && !["goals", "assists"].includes(s.key)) return null;
          return <Stat key={s.key} label={s.label} value={s.dec ? v.toFixed(s.dec) : Math.round(v)} defId={STAT_DEF_ID[s.key]} />;
        })}
      </div>
    </div>
  );
}

function Stat({ label, value, defId }: { label: string; value: number | string; defId?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>{value}</div>
      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
        {label}
        {defId && <DefinitionBubble id={defId} size={12} />}
      </div>
    </div>
  );
}
