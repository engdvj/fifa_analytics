"use client";

import React from "react";
import { ExploratoryData } from "@/lib/api";
import { useExploratory } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import QuadranteMapa from "@/components/dashboard/QuadranteMapa";

const PERFIL_COLOR: Record<string, string> = {
  "Elite": "#3fb950", "Oportunistas": "#58a6ff", "Frustrados": "#d29922", "Em apuros": "#f85149", "Neutro": "#8b949e",
};
const PERFIL_DESC: Record<string, string> = {
  "Elite": "cria muito e converte",
  "Oportunistas": "cria pouco, mas mata",
  "Frustrados": "cria muito e desperdiça",
  "Em apuros": "cria pouco e não converte",
  "Neutro": "no meio — sem perfil claro",
};
const num = (v: number) => v.toFixed(2).replace(".", ",");

export default function ExploratoriaView({ snapshot, enabled, selectedTeams = [], onToggleTeam }: {
  snapshot: number; enabled: boolean; selectedTeams?: string[]; onToggleTeam?: (t: string) => void;
}) {
  const { explore, isLoading } = useExploratory(snapshot, enabled);
  if (isLoading) return <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>;
  if (!explore || !explore.decide) {
    return <Aviso texto="Amostra ainda insuficiente para padrões — avance no tempo ou rode uma coleta." />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Foco: onde as seleções marcadas se encaixam nos padrões */}
      {selectedTeams.length > 0 && (
        <FocusContext teams={selectedTeams} quadrante={explore.quadrante} estilos={explore.estilos_mapa ?? []} eficiencia={explore.eficiencia ?? []} />
      )}
      {/* Herói: o quadrante (gráfico grande + cards) */}
      <Quadrante data={explore.quadrante} selected={selectedTeams} onToggle={onToggleTeam ?? (() => {})} />
      <EficienciaDestaques rows={explore.eficiencia ?? []} />
      {/* Segundo insight forte: o que decide os jogos */}
      <Decide rows={explore.decide} />
      {/* Apoio: estilo, fases e defesa em fileira */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14, alignItems: "start" }}>
        <EstiloResultado rows={explore.estilo_resultado ?? []} />
        <Fases rows={explore.fases ?? []} />
        <Defesa rows={explore.defesa ?? []} />
      </div>
    </div>
  );
}

// Onde as seleções em foco se encaixam nos padrões (perfil, estilo, eficiência).
function FocusContext({ teams, quadrante, estilos, eficiencia }: {
  teams: string[]; quadrante?: ExploratoryData["quadrante"];
  estilos: NonNullable<ExploratoryData["estilos_mapa"]>; eficiencia: NonNullable<ExploratoryData["eficiencia"]>;
}) {
  const pontos = quadrante?.pontos ?? [];
  return (
    <Panel titulo="Seleções em foco no mapa" sub="Onde a(s) seleção(ões) marcada(s) se encaixa(m) nos padrões da Copa.">
      <div style={{ padding: "10px 16px 14px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
        {teams.map((t) => {
          const q = pontos.find((p) => p.team === t);
          const e = estilos.find((s) => s.team === t);
          const ef = eficiencia.find((x) => x.team === t);
          return (
            <div key={t} style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, fontWeight: 700, fontSize: 13.5, marginBottom: 7 }}><Flag team={t} height={14} />{t}</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {q?.perfil && <Tag texto={q.perfil} cor={PERFIL_COLOR[q.perfil]} />}
                {e?.arquetipo && <Tag texto={e.arquetipo} />}
                {ef && <Tag texto={`${ef.overperf >= 0 ? "+" : ""}${num(ef.overperf)} gols vs xG`} cor={ef.overperf >= 0 ? "var(--green)" : "var(--red)"} />}
                {q && <Tag texto={`cria ${num(q.cria)} xG/jogo`} />}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function Tag({ texto, cor }: { texto: string; cor?: string }) {
  return (
    <span style={{ fontSize: 11, color: cor ?? "var(--text-muted)", border: `1px solid ${cor ? `color-mix(in srgb, ${cor} 40%, transparent)` : "var(--surface2)"}`, borderRadius: 5, padding: "2px 8px" }}>{texto}</span>
  );
}

// Destaque enxuto de eficiência (substitui o painel — é o eixo Y do quadrante).
function EficienciaDestaques({ rows }: { rows: NonNullable<ExploratoryData["eficiencia"]> }) {
  if (rows.length < 2) return null;
  const over = rows.slice(0, 2);
  const under = rows.slice(-2).reverse();
  const chip = (r: typeof rows[0], cor: string) => (
    <span key={r.team} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <Flag team={r.team} height={11} />{r.team} <b style={{ color: cor }}>{r.overperf >= 0 ? "+" : ""}{num(r.overperf)}</b>
    </span>
  );
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "4px 16px", fontSize: 12, color: "var(--text-muted)", padding: "0 4px" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><b style={{ color: "var(--green)" }}>Rendem além do xG:</b> {over.map((r) => chip(r, "var(--green)"))}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><b style={{ color: "var(--red)" }}>Rendem aquém:</b> {under.map((r) => chip(r, "var(--red)"))}</span>
    </div>
  );
}

// ── 1. O que ganha jogos ──────────────────────────────────────────────────────
function Decide({ rows }: { rows: NonNullable<ExploratoryData["decide"]> }) {
  const top = rows[0];
  const neg = rows.filter((r) => r.corr < 0.15);
  const leitura = top
    ? `${top.label.split(" (")[0]} é o que mais decide (correlação +${num(top.corr)} com o saldo de gols)` +
      (neg.length ? `. Já ${neg.map((n) => n.label.split(" (")[0].toLowerCase()).join(", ")} pouco ou nada explicam — e pressionar muito na defesa anda com a derrota.` : ".")
    : "";
  return (
    <Panel titulo="O que ganha jogos" leitura={leitura}
      sub="Correlação entre o diferencial da métrica (time − adversário) e o saldo. +1 = ter vantagem nisso quase sempre vence; 0 = não tem relação; negativo = anda com a derrota.">
      <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map((r) => {
          const pos = r.corr >= 0;
          const cor = pos ? "var(--green)" : "var(--red)";
          return (
            <div key={r.metric} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
              <span style={{ width: 150, color: "var(--text-muted)", textAlign: "right", flexShrink: 0 }}>{r.label.split(" (")[0]}</span>
              <div style={{ flex: 1, display: "flex", alignItems: "center", height: 14 }}>
                <div style={{ flex: 1, display: "flex", justifyContent: "flex-end" }}>
                  {!pos && <div style={{ width: `${Math.abs(r.corr) * 100}%`, height: 11, background: cor, borderRadius: "3px 0 0 3px", opacity: 0.85 }} />}
                </div>
                <div style={{ width: 1, height: 14, background: "var(--surface2)" }} />
                <div style={{ flex: 1, display: "flex", justifyContent: "flex-start" }}>
                  {pos && <div style={{ width: `${Math.abs(r.corr) * 100}%`, height: 11, background: cor, borderRadius: "0 3px 3px 0", opacity: 0.85 }} />}
                </div>
              </div>
              <span style={{ width: 38, fontWeight: 700, color: cor, textAlign: pos ? "left" : "right", flexShrink: 0 }}>
                {r.corr > 0 ? "+" : ""}{num(r.corr)}
              </span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── 2. Quem cria × quem converte (quadrante interativo, multi-seleção) ───────
const QUAD_ORDER = ["Oportunistas", "Elite", "Em apuros", "Frustrados", "Neutro"];
const CARD_ORDER = ["Elite", "Frustrados", "Oportunistas", "Em apuros", "Neutro"];

function Quadrante({ data, selected, onToggle }: { data?: ExploratoryData["quadrante"]; selected: string[]; onToggle: (t: string) => void }) {
  if (!data || !data.pontos.length) return null;
  const pontos = data.pontos;
  const grupos = new Map<string, typeof pontos>();
  for (const p of pontos) {
    if (!grupos.has(p.perfil)) grupos.set(p.perfil, []);
    grupos.get(p.perfil)!.push(p);
  }
  const selSet = new Set(selected);
  const hasSel = selected.length > 0;

  const toggleTeam = (t?: string) => { if (t) onToggle(t); };
  const togglePerfil = (perfil: string) => {
    const teams = (grupos.get(perfil) ?? []).map((p) => p.team);
    const all = teams.length > 0 && teams.every((t) => selSet.has(t));
    teams.forEach((t) => { if (all ? selSet.has(t) : !selSet.has(t)) onToggle(t); });
  };

  return (
    <Panel titulo="Quem cria e quem converte"
      leitura="Cada seleção em perigo criado (xG) × eficiência (gols − xG). Os perfis classificam quem domina, desperdiça ou é cirúrgico — quem fica na zona neutra do meio tem números próximos demais para cravar."
      sub="Clique em seleções (ou num perfil) para selecionar várias e comparar no gráfico.">
      <div style={{ display: "flex", justifyContent: "flex-end", padding: "6px 16px 0" }}>
        {hasSel && (
          <button onClick={() => selected.forEach(onToggle)}
            style={{ fontSize: 11, color: "var(--accent)", background: "none", border: "1px solid var(--surface2)", borderRadius: 6, padding: "3px 10px", cursor: "pointer", fontFamily: "inherit" }}>
            ✕ limpar seleção ({selected.length})
          </button>
        )}
      </div>
      <div style={{ padding: "4px 8px 8px" }}>
        <QuadranteMapa data={data} selected={selected} onToggle={onToggle} />
      </div>
      {/* Cards clicáveis: selecionar grupo inteiro; chips selecionam país a país */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8, padding: "4px 16px 14px" }}>
        {CARD_ORDER.map((perfil) => {
          const pts = grupos.get(perfil) ?? [];
          if (pts.length === 0) return null;
          const nSel = pts.filter((p) => selSet.has(p.team)).length;
          return (
            <div key={perfil} style={{ borderLeft: `3px solid ${PERFIL_COLOR[perfil]}`, paddingLeft: 10 }}>
              <div onClick={() => togglePerfil(perfil)} title="Selecionar o grupo todo"
                style={{ fontSize: 12, fontWeight: 700, color: PERFIL_COLOR[perfil], cursor: "pointer" }}>
                {perfil} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>({pts.length})</span>
                {nSel > 0 && <span style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 400 }}> · {nSel} selec.</span>}
              </div>
              <div style={{ fontSize: 10.5, color: "var(--text-muted)", marginBottom: 5 }}>{PERFIL_DESC[perfil]}</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {pts.map((p) => {
                  const on = selSet.has(p.team);
                  return (
                    <span key={p.team} onClick={() => toggleTeam(p.team)} title="Comparar no gráfico"
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, cursor: "pointer",
                        color: on ? "#fff" : "var(--text)", background: on ? PERFIL_COLOR[perfil] : "transparent",
                        border: `1px solid ${on ? PERFIL_COLOR[perfil] : "var(--surface2)"}`, borderRadius: 5, padding: "1px 6px",
                      }}>
                      <Flag team={p.team} height={11} />{p.team}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── 4. Qual estilo está rendendo ─────────────────────────────────────────────
function EstiloResultado({ rows }: { rows: NonNullable<ExploratoryData["estilo_resultado"]> }) {
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((r) => r.pts_jogo), 3);
  const leitura = `${rows[0].arquetipo} é o estilo que mais rende (${num(rows[0].pts_jogo)} pts/jogo); ${rows[rows.length - 1].arquetipo}, o que menos.`;
  return (
    <Panel titulo="Qual estilo está rendendo" leitura={leitura}
      sub="Pontos por jogo das seleções de cada arquétipo de jogo. O que está funcionando nesta Copa.">
      <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
        {rows.map((r) => (
          <div key={r.arquetipo} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
            <span style={{ width: 110, textAlign: "right", color: "var(--text)", flexShrink: 0 }}>{r.arquetipo} <span style={{ color: "var(--text-muted)", fontSize: 10.5 }}>({r.n})</span></span>
            <div style={{ flex: 1, height: 14, background: "var(--surface2)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${r.pts_jogo / max * 100}%`, height: "100%", background: "var(--accent)" }} />
            </div>
            <span style={{ width: 72, fontWeight: 700, color: "var(--accent)", flexShrink: 0 }}>{num(r.pts_jogo)} <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: 10.5 }}>pts/jogo</span></span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── 5. De onde vem o perigo ───────────────────────────────────────────────────
function Fases({ rows }: { rows: NonNullable<ExploratoryData["fases"]> }) {
  if (rows.length === 0) return null;
  return (
    <Panel titulo="De onde vem o perigo" sub="A seleção que mais se apoia em cada fase de jogo — quem vive de bola parada, de transição, de ataque posicional…">
      <ul style={{ listStyle: "none", margin: 0, padding: "4px 0" }}>
        {rows.map((f) => (
          <li key={f.fase} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 16px", borderTop: "1px solid var(--surface)", fontSize: 13 }}>
            <span style={{ color: "var(--text-muted)" }}>{f.fase}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}><Flag team={f.team} height={12} />{f.team}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── 6. Defesa: o que segura ───────────────────────────────────────────────────
function Defesa({ rows }: { rows: NonNullable<ExploratoryData["defesa"]> }) {
  if (rows.length === 0) return null;
  return (
    <Panel titulo="O que segura atrás" sub="As defesas que menos cederam perigo (xG sofrido por jogo) e o estilo de cada uma.">
      <ul style={{ listStyle: "none", margin: 0, padding: "4px 0" }}>
        {rows.map((d) => (
          <li key={d.team} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 16px", borderTop: "1px solid var(--surface)", fontSize: 13 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
              <Flag team={d.team} height={12} />{d.team}
              {d.estilo && <span style={{ fontSize: 10.5, color: "var(--text-muted)", fontWeight: 400 }}>· {d.estilo}</span>}
            </span>
            <span style={{ color: "var(--accent)", fontWeight: 700 }}>{num(d.xg_sofrido)} <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: 10.5 }}>xG sofrido/jogo</span></span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}


function Panel({ titulo, leitura, sub, children }: { titulo: string; leitura?: string; sub?: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700 }}>{titulo}</div>
        {leitura && <div style={{ fontSize: 13, color: "var(--text)", marginTop: 4, lineHeight: 1.45, fontWeight: 600 }}>{leitura}</div>}
        {sub && <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 3, lineHeight: 1.4 }}>{sub}</div>}
      </div>
      {children}
    </section>
  );
}

function Aviso({ texto }: { texto: string }) {
  return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: "var(--text-muted)" }}>{texto}</div>;
}
