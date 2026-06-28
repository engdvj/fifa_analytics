"use client";

import React from "react";
import { TeamSnapshot } from "@/lib/api";
import Flag from "@/components/ui/Flag";
import { styleName } from "@/lib/styleMeta";

/**
 * Perfil de seleção UNIFICADO — antes duplicado entre a Descritiva (card completo,
 * baseado em TeamSnapshot) e a Exploratória (card resumido, baseado em
 * TeamStyleDetail). Agora há um só componente com `variant`:
 *
 *   - "full"    → manchete (tiles) + componentes do score + números avançados.
 *   - "compact" → estilo + cartel (V/E/D) + 3 métricas-chave (para grids de comparação).
 *
 * A fonte canônica é o TeamSnapshot. Quem tiver dados de estilo/cartel (vindos do
 * TeamStyleDetail) passa o overlay opcional `style`/`record`.
 */

export interface TeamProfileOverlay {
  arquetipo?: string | null;     // estilo de jogo (sobrepõe estilo_jogo do snapshot)
  vitorias?: number | null;
  empates?: number | null;
  derrotas?: number | null;
  pts_jogo?: number | null;
  saldo_pj?: number | null;
  aproveitamento_pct?: number | null; // já em 0-100 (TeamStyleDetail), se houver
}

const SCORE_COMPS: { key: keyof TeamSnapshot | string; label: string; color: string }[] = [
  { key: "score_resultado", label: "Resultado", color: "#58a6ff" },
  { key: "score_ataque", label: "Ataque", color: "#f0883e" },
  { key: "score_defesa", label: "Defesa", color: "#3fb950" },
  { key: "score_eficiencia", label: "Eficiência", color: "#d29922" },
  { key: "score_controle", label: "Controle", color: "#a371f7" },
  { key: "score_forca_relativa", label: "Força rel.", color: "#f85149" },
];

const nv = (v: unknown, d = 2) => (typeof v === "number" ? v.toFixed(d).replace(".", ",") : "—");

function aproveitamentoPct(r: TeamSnapshot, overlay?: TeamProfileOverlay): string {
  if (overlay?.aproveitamento_pct != null) return `${Math.round(overlay.aproveitamento_pct)}%`;
  if (typeof r.aproveitamento === "number") return `${Math.round(r.aproveitamento * 100)}%`;
  return "—";
}

function styleOf(r: TeamSnapshot, overlay?: TeamProfileOverlay): string | null {
  const s = overlay?.arquetipo ?? r.estilo_jogo;
  return typeof s === "string" && s ? s : null;
}

export default function TeamProfile({
  snapshot,
  overlay,
  variant = "full",
  title,
}: {
  snapshot: TeamSnapshot;
  overlay?: TeamProfileOverlay;
  variant?: "full" | "compact";
  title?: string;
}) {
  if (variant === "compact") return <CompactProfile snapshot={snapshot} overlay={overlay} title={title} />;
  return <FullProfile snapshot={snapshot} overlay={overlay} />;
}

function CompactProfile({ snapshot: r, overlay, title }: { snapshot: TeamSnapshot; overlay?: TeamProfileOverlay; title?: string }) {
  const style = styleOf(r, overlay);
  const accent = "var(--accent)";
  const record =
    overlay && (overlay.vitorias != null || overlay.empates != null || overlay.derrotas != null)
      ? `${overlay.vitorias ?? 0}V ${overlay.empates ?? 0}E ${overlay.derrotas ?? 0}D`
      : `${r.jogos ?? 0} jogos`;
  const ptsJogo = overlay?.pts_jogo ?? (typeof r.points === "number" && r.jogos ? r.points / r.jogos : null);
  const saldoPj = overlay?.saldo_pj ?? (typeof r.saldo_gols === "number" && r.jogos ? r.saldo_gols / r.jogos : null);
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 13px", minWidth: 0 }}>
      {title && <div style={{ color: "var(--text-muted)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 800 }}>{title}</div>}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: title ? 8 : 0 }}>
        <Flag team={r.team} height={15} />
        <b style={{ color: "var(--text)", fontSize: 15 }}>{r.team}</b>
      </div>
      {style && <div style={{ color: accent, fontSize: 18, lineHeight: 1.1, fontWeight: 900, marginTop: 8 }}>{styleName(style)}</div>}
      <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 4 }}>{record}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, marginTop: 10 }}>
        <SmallMetric label="Pts/jogo" value={nv(ptsJogo)} color={accent} />
        <SmallMetric label="Aproveit." value={aproveitamentoPct(r, overlay)} color={accent} />
        <SmallMetric label="Saldo/jogo" value={nv(saldoPj)} color={accent} />
      </div>
    </div>
  );
}

function FullProfile({ snapshot: r, overlay }: { snapshot: TeamSnapshot; overlay?: TeamProfileOverlay }) {
  const style = styleOf(r, overlay);
  const tiles: [string | number, string][] = [
    [r.jogos ?? "—", "Jogos"],
    [r.gols ?? "—", "Gols"],
    [r.gols_contra ?? "—", "Gols sofridos"],
    [r.saldo_gols ?? "—", "Saldo"],
    [aproveitamentoPct(r, overlay), "Aproveitamento"],
    [nv(r.score_geral, 1), "Score geral"],
  ];
  const stats: [string, string][] = [
    [String(r.points ?? "—"), "Pontos"],
    [nv(r["xg_pj"]), "xG / jogo"],
    [nv(r["xg_sofrido_pj"]), "xG sofrido / jogo"],
    [r.elo_rating != null ? String(Math.round(r.elo_rating)) : "—", "Elo"],
  ];
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "13px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <Flag team={r.team} height={22} />
        <span style={{ fontWeight: 700, fontSize: 16, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.team}</span>
        {r.ranking_score_geral != null && (
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)", background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 6, padding: "3px 9px" }}>{r.ranking_score_geral}º no geral</span>
        )}
        {style && (
          <span style={{ fontSize: 11, color: "var(--text-muted)", border: "1px solid var(--surface2)", borderRadius: 6, padding: "3px 9px" }}>{styleName(style)}</span>
        )}
      </header>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10 }}>
          {tiles.map(([v, l]) => (
            <div key={l} style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 10, padding: "12px 6px", textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--accent)" }}>{v}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{l}</div>
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div>
            <SectionLabel texto="Componentes do score" />
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              {SCORE_COMPS.map((c) => {
                const v = r[c.key as string];
                const val = typeof v === "number" ? v : null;
                return (
                  <div key={c.key as string} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                    <span style={{ width: 76, color: "var(--text-muted)", flexShrink: 0 }}>{c.label}</span>
                    <div style={{ flex: 1, height: 7, background: "var(--surface2)", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ width: `${val ?? 0}%`, height: "100%", background: c.color }} />
                    </div>
                    <span style={{ width: 26, textAlign: "right", fontWeight: 700, color: "var(--text)", flexShrink: 0 }}>{val != null ? Math.round(val) : "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <SectionLabel texto="Números" />
            <div style={{ marginTop: 8 }}>
              {stats.map(([v, l]) => (
                <div key={l} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, borderTop: "1px solid var(--surface)", padding: "7px 0" }}>
                  <span style={{ color: "var(--text-muted)" }}>{l}</span>
                  <span style={{ fontWeight: 700 }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SmallMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ color: "var(--text-muted)", fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
      <div style={{ color, fontSize: 14, fontWeight: 850, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function SectionLabel({ texto }: { texto: string }) {
  return <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700 }}>{texto}</div>;
}
