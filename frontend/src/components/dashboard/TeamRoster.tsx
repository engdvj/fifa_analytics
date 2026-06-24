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

// Stats mostradas no detalhe ao clicar (todas FIFA-disponíveis).
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

export default function TeamRoster({ players, loading, kit }: Props) {
  const [openId, setOpenId] = React.useState<string | null>(null);

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
                <span style={{ fontSize: 11, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {l.best?.player_name}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Jogadores por posição */}
      {byPerfil.map((g) => (
        <div key={g.key} style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
            {g.label} · {g.list.length}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 6 }}>
            {g.list.map((p) => {
              const id = p.player_slug ?? p.id_player;
              const open = openId === id;
              const primary = g.key === "goleiro" ? num(p, "saves") : g.key === "atacante" ? num(p, "goals") : num(p, "tackles_won");
              const primaryLabel = g.key === "goleiro" ? "def." : g.key === "atacante" ? "gols" : "desarmes";
              return (
                <div key={id} style={{ background: "var(--surface2)", border: `1px solid ${open ? kit.main + "88" : "var(--border)"}`, borderRadius: 8, overflow: "hidden" }}>
                  <button
                    onClick={() => setOpenId(open ? null : id)}
                    style={{ width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", background: "none", border: "none", cursor: "pointer", textAlign: "left", fontFamily: "inherit" }}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 22, height: 22, borderRadius: 4, background: kit.main, color: kit.text, fontSize: 10, fontWeight: 700, border: `1px solid ${kit.border}`, flexShrink: 0 }}>
                      {p.shirt_number ?? "?"}
                    </span>
                    <span style={{ flex: 1, minWidth: 0, fontSize: 13, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.player_name}</span>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{Math.round(primary)} {primaryLabel}</span>
                    {p.score_geral != null && (
                      <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)", minWidth: 30, textAlign: "right" }}>{p.score_geral.toFixed(0)}</span>
                    )}
                  </button>
                  {open && (
                    <div style={{ padding: "8px 10px 10px", borderTop: "1px solid var(--border)", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
                      <Stat label="Jogos" value={Math.round(num(p, "jogos"))} />
                      {DETAIL_STATS.map((s) => {
                        const v = num(p, s.key);
                        if (v === 0 && !["goals", "assists"].includes(s.key)) return null;
                        return <Stat key={s.key} label={s.label} value={s.dec ? v.toFixed(s.dec) : Math.round(v)} defId={STAT_DEF_ID[s.key]} />;
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, defId }: { label: string; value: number | string; defId?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{value}</div>
      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
        {label}
        {defId && <DefinitionBubble id={defId} size={12} />}
      </div>
    </div>
  );
}
