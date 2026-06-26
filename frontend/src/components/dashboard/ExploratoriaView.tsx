"use client";

import React from "react";
import {
  CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { ExploratoryData } from "@/lib/api";
import { useExploratory } from "@/lib/hooks";
import Spinner from "@/components/ui/Spinner";

// Cores por arquétipo de estilo (mapa de estilos).
const ARQ_COLOR: Record<string, string> = {
  "Posse": "#58a6ff", "Pressão Alta": "#f85149", "Contra-ataque": "#3fb950",
  "Retranca": "#d29922", "Jogo Direto": "#a371f7", "Bola Parada": "#79c0ff",
};

export default function ExploratoriaView({ snapshot, enabled }: { snapshot: number; enabled: boolean }) {
  const { explore, isLoading } = useExploratory(snapshot, enabled);

  if (isLoading) return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  if (!explore || !explore.decisao) {
    return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: "var(--text-muted)" }}>
      Amostra ainda insuficiente para padrões — avance no tempo ou rode uma coleta.
    </div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: 0, lineHeight: 1.55, textAlign: "center" }}>
        <b style={{ color: "var(--text)" }}>Padrões da competição</b> — relações que atravessam os {explore.amostra / 2} jogos analisados; cresce conforme o torneio avança.
      </p>

      <Decisao rows={explore.decisao} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 14 }}>
        <Eficiencia rows={explore.eficiencia ?? []} />
        <MapaEstilos rows={explore.estilos ?? []} />
      </div>

      <Correlacoes rows={explore.correlacoes ?? []} />
    </div>
  );
}

// ── 1. O que decide os jogos ──────────────────────────────────────────────────
function Decisao({ rows }: { rows: NonNullable<ExploratoryData["decisao"]> }) {
  return (
    <Panel titulo="O que decide os jogos" sub="Correlação entre o diferencial da métrica (time − adversário) e o saldo de gols. Quanto mais forte, mais aquilo pesa no resultado.">
      <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
        {rows.map((r) => {
          const pos = r.corr >= 0;
          const cor = pos ? "var(--green)" : "var(--red)";
          return (
            <div key={r.metric} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
              <span style={{ width: 160, color: "var(--text-muted)", textAlign: "right", flexShrink: 0 }}>{r.label}</span>
              {/* eixo central em 0; barra cresce p/ direita (positivo) ou esquerda (negativo) */}
              <div style={{ flex: 1, display: "flex", alignItems: "center", height: 16 }}>
                <div style={{ flex: 1, display: "flex", justifyContent: "flex-end" }}>
                  {!pos && <div style={{ width: `${Math.abs(r.corr) * 100}%`, height: 12, background: cor, borderRadius: "3px 0 0 3px", opacity: 0.85 }} />}
                </div>
                <div style={{ width: 1, height: 16, background: "var(--surface2)" }} />
                <div style={{ flex: 1, display: "flex", justifyContent: "flex-start" }}>
                  {pos && <div style={{ width: `${Math.abs(r.corr) * 100}%`, height: 12, background: cor, borderRadius: "0 3px 3px 0", opacity: 0.85 }} />}
                </div>
              </div>
              <span style={{ width: 40, fontWeight: 700, color: cor, textAlign: pos ? "left" : "right", flexShrink: 0 }}>
                {r.corr > 0 ? "+" : ""}{r.corr.toFixed(2).replace(".", ",")}
              </span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── 2. Paisagem de eficiência (xG × gols/jogo) ───────────────────────────────
function Eficiencia({ rows }: { rows: NonNullable<ExploratoryData["eficiencia"]> }) {
  const max = Math.ceil(Math.max(1, ...rows.flatMap((r) => [r.xg, r.gols]))) ;
  return (
    <Panel titulo="Paisagem de eficiência" sub="xG × gols por jogo. Acima da linha: rende acima do esperado (clínico/sorte). Abaixo: desperdiça.">
      <div style={{ padding: "8px 8px 4px", height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
            <CartesianGrid stroke="#21262d" />
            <XAxis type="number" dataKey="xg" name="xG/jogo" domain={[0, max]} tick={{ fontSize: 10, fill: "#8b949e" }} stroke="#30363d"
              label={{ value: "xG/jogo", position: "insideBottom", offset: -6, fontSize: 11, fill: "#8b949e" }} />
            <YAxis type="number" dataKey="gols" name="Gols/jogo" domain={[0, max]} tick={{ fontSize: 10, fill: "#8b949e" }} stroke="#30363d"
              label={{ value: "Gols/jogo", angle: -90, position: "insideLeft", offset: 16, fontSize: 11, fill: "#8b949e" }} />
            <ZAxis range={[55, 55]} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="#6e7681" strokeDasharray="4 4" />
            <Tooltip content={<PointTip fields={[["gols", "gols/jogo"], ["xg", "xG/jogo"]]} />} />
            <Scatter data={rows} fill="#58a6ff" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

// ── 3. Mapa de estilos ────────────────────────────────────────────────────────
function MapaEstilos({ rows }: { rows: NonNullable<ExploratoryData["estilos"]> }) {
  const grupos = React.useMemo(() => {
    const m = new Map<string, typeof rows>();
    for (const p of rows) {
      const k = p.arquetipo ?? "—";
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(p);
    }
    return Array.from(m.entries());
  }, [rows]);
  return (
    <Panel titulo="Mapa de estilos" sub="Cada seleção por posse × verticalidade, colorida pelo arquétipo de jogo. Mostra quem joga parecido e os outliers.">
      <div style={{ padding: "8px 8px 4px", height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
            <CartesianGrid stroke="#21262d" />
            <XAxis type="number" dataKey="posse" name="Posse" domain={[0, 100]} tick={{ fontSize: 10, fill: "#8b949e" }} stroke="#30363d"
              label={{ value: "← retranca · posse →", position: "insideBottom", offset: -6, fontSize: 10, fill: "#8b949e" }} />
            <YAxis type="number" dataKey="verticalidade" name="Verticalidade" domain={[0, 100]} tick={{ fontSize: 10, fill: "#8b949e" }} stroke="#30363d"
              label={{ value: "vertical →", angle: -90, position: "insideLeft", offset: 16, fontSize: 10, fill: "#8b949e" }} />
            <ZAxis range={[50, 50]} />
            <Tooltip content={<PointTip fields={[["posse", "posse"], ["verticalidade", "vertical."]]} />} />
            {grupos.map(([arq, pts]) => (
              <Scatter key={arq} name={arq} data={pts} fill={ARQ_COLOR[arq] ?? "#8b949e"} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "0 16px 12px" }}>
        {grupos.map(([arq]) => (
          <span key={arq} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-muted)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: ARQ_COLOR[arq] ?? "#8b949e" }} />{arq}
          </span>
        ))}
      </div>
    </Panel>
  );
}

// ── 4. Correlações entre métricas ─────────────────────────────────────────────
function Correlacoes({ rows }: { rows: NonNullable<ExploratoryData["correlacoes"]> }) {
  if (rows.length === 0) return null;
  return (
    <Panel titulo="O que anda junto" sub="Pares de métricas mais correlacionados — sinalizam redundância (medem quase a mesma coisa) ou oposição.">
      <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
        {rows.map((c, i) => {
          const cor = c.corr >= 0 ? "var(--accent)" : "var(--red)";
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
              <span style={{ flex: 1, color: "var(--text)" }}>{c.label_a} <span style={{ color: "var(--text-muted)" }}>~</span> {c.label_b}</span>
              <div style={{ width: 120, height: 8, background: "var(--surface2)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${Math.abs(c.corr) * 100}%`, height: "100%", background: cor }} />
              </div>
              <span style={{ width: 40, fontWeight: 700, color: cor, textAlign: "right" }}>{c.corr > 0 ? "+" : ""}{c.corr.toFixed(2).replace(".", ",")}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────
function PointTip({ active, payload, fields }: { active?: boolean; payload?: { payload: Record<string, unknown> }[]; fields: [string, string][] }) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0].payload;
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 6, padding: "6px 10px", fontSize: 12 }}>
      <div style={{ fontWeight: 700, color: "var(--text)", marginBottom: 2 }}>{String(p.team)}</div>
      {fields.map(([k, lbl]) => (
        <div key={k} style={{ color: "var(--text-muted)" }}>{lbl}: <b style={{ color: "var(--text)" }}>{Number(p[k]).toFixed(2).replace(".", ",")}</b></div>
      ))}
    </div>
  );
}

function Panel({ titulo, sub, children }: { titulo: string; sub?: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700 }}>{titulo}</div>
        {sub && <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4, textTransform: "none", letterSpacing: 0, fontWeight: 400 }}>{sub}</div>}
      </div>
      {children}
    </section>
  );
}
