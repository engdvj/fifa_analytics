"use client";

import React from "react";
import { LineupPlayer, MatchEvent } from "@/lib/api";

interface Props {
  events: MatchEvent[];
  homePlayers: LineupPlayer[];
  awayPlayers: LineupPlayer[];
  homeTeam: string;
  awayTeam: string;
  homeIdTeam: string;
}

function minuteNum(m: string | null): number {
  if (!m) return 999;
  // "45'+5'" → 45.5 ; "73'" → 73
  const base = parseFloat(m.replace(/'/g, "").replace(/\+.*/, "")) || 0;
  const extra = m.includes("+") ? (parseFloat(m.split("+")[1].replace(/'/g, "")) || 0) / 10 : 0;
  return base + extra;
}

function eventMeta(e: MatchEvent): { icon: string; kind: string } {
  if (e.event_type === "goal") return { icon: "⚽", kind: "goal" };
  if (e.event_type === "substitution") return { icon: "🔄", kind: "sub" };
  const d = (e.detail ?? "").toLowerCase();
  if (d.includes("red") || d.includes("vermelho")) return { icon: "🟥", kind: "red" };
  return { icon: "🟨", kind: "yellow" };
}

function StatRow({ label, h, a, homeColor, awayColor }: { label: string; h: number; a: number; homeColor: string; awayColor: string }) {
  const total = h + a;
  const empty = total === 0;
  const hp = total > 0 ? (h / total) * 100 : 0;
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12.5, marginBottom: 4 }}>
        <span style={{ fontWeight: 800, color: !empty && h >= a ? "var(--text)" : "var(--text-muted)" }}>{h}</span>
        <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{label}</span>
        <span style={{ fontWeight: 800, color: !empty && a >= h ? "var(--text)" : "var(--text-muted)" }}>{a}</span>
      </div>
      {empty ? (
        <div style={{ height: 6, borderRadius: 3, background: "var(--surface2)" }} />
      ) : (
        <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "var(--surface2)" }}>
          <div style={{ width: `${hp}%`, background: homeColor }} />
          <div style={{ width: `${100 - hp}%`, background: awayColor }} />
        </div>
      )}
    </div>
  );
}

export default function MatchTimeline({ events, homePlayers, awayPlayers, homeTeam, awayTeam, homeIdTeam }: Props) {
  // Cores fixas casa/fora (claras e distintas) — as cores de kit ficavam lavadas.
  const homeColor = "#58a6ff";
  const awayColor = "#f0883e";

  const nameById = new Map<string, string>();
  for (const p of [...homePlayers, ...awayPlayers]) if (p.player_name) nameById.set(p.id_player, p.player_name);
  const resolve = (id: string | null, fb: string | null) => fb || (id ? nameById.get(id) : null) || "?";

  const sorted = [...events].sort((a, b) => minuteNum(a.minute) - minuteNum(b.minute));

  // resumo (gráfico de barras: gols/cartões/subs por time)
  const summary = { home: { goal: 0, card: 0, sub: 0 }, away: { goal: 0, card: 0, sub: 0 } };
  for (const e of sorted) {
    const side = e.id_team === homeIdTeam ? "home" : "away";
    const { kind } = eventMeta(e);
    if (kind === "goal") summary[side].goal++;
    else if (kind === "sub") summary[side].sub++;
    else summary[side].card++;
  }

  // placar progressivo
  let hs = 0, as = 0;
  const rows = sorted.map((e, i) => {
    const isHome = e.id_team === homeIdTeam;
    const { icon, kind } = eventMeta(e);
    if (kind === "goal") { if (isHome) hs++; else as++; }
    return { e, i, isHome, icon, kind, score: kind === "goal" ? `${hs}–${as}` : null };
  });

  if (sorted.length === 0) {
    return <p style={{ fontSize: 13, color: "var(--text-muted)" }}>Sem eventos registrados neste jogo.</p>;
  }

  return (
    <div className="v2-match-timeline">
      {/* Resumo (gráfico) */}
      <div className="v2-match-timeline-summary" style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 16px", marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: homeColor }}>{homeTeam}</span>
          <span style={{ color: "var(--text)", fontSize: 18 }}>{hs} – {as}</span>
          <span style={{ color: awayColor }}>{awayTeam}</span>
        </div>
        <StatRow label="Gols" h={summary.home.goal} a={summary.away.goal} homeColor={homeColor} awayColor={awayColor} />
        <StatRow label="Cartões" h={summary.home.card} a={summary.away.card} homeColor={homeColor} awayColor={awayColor} />
        <StatRow label="Substituições" h={summary.home.sub} a={summary.away.sub} homeColor={homeColor} awayColor={awayColor} />
      </div>

      {/* Eixo vertical de eventos */}
      <div className="v2-match-timeline-axis" style={{ position: "relative", padding: "4px 0" }}>
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 2, background: "var(--border)", transform: "translateX(-50%)" }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {rows.map(({ e, i, isHome, icon, kind, score }) => {
            const kit = { main: isHome ? homeColor : awayColor };
            const label = kind === "sub"
              ? <span><span style={{ color: "var(--green)" }}>{resolve(e.id_player2, e.player2_name)}</span><span style={{ color: "var(--text-muted)" }}> ↔ </span><span style={{ color: "var(--red)" }}>{resolve(e.id_player, e.player_name)}</span></span>
              : <span style={{ fontWeight: kind === "goal" ? 700 : 500, color: "var(--text)" }}>{resolve(e.id_player, e.player_name)}</span>;
            return (
              <div className="v2-match-event-row" key={i} style={{ display: "grid", gridTemplateColumns: "1fr 64px 1fr", alignItems: "center", gap: 6 }}>
                <div style={{ textAlign: "right", fontSize: 12 }}>{isHome ? <Card kit={kit} align="right">{label}{score && <Score>{score}</Score>}</Card> : null}</div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, zIndex: 1 }}>
                  <span style={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: 10, padding: "0 6px", fontSize: 10, color: "var(--text-muted)" }}>{e.minute}</span>
                  <span style={{ fontSize: 14 }}>{icon}</span>
                </div>
                <div style={{ textAlign: "left", fontSize: 12 }}>{!isHome ? <Card kit={kit} align="left">{score && <Score>{score}</Score>}{label}</Card> : null}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Card({ children, kit, align }: { children: React.ReactNode; kit: { main: string }; align: "left" | "right" }) {
  return (
    <span className="v2-match-event-card" style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "var(--surface2)", border: "1px solid var(--border)", borderLeft: align === "left" ? `3px solid ${kit.main}` : "1px solid var(--border)", borderRight: align === "right" ? `3px solid ${kit.main}` : "1px solid var(--border)", borderRadius: 6, padding: "4px 9px", maxWidth: "100%" }}>
      {children}
    </span>
  );
}

function Score({ children }: { children: React.ReactNode }) {
  return <span style={{ fontWeight: 800, color: "var(--accent)", fontSize: 12 }}>{children}</span>;
}
