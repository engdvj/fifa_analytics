"use client";

import React from "react";
import { Match, DescriptiveDigest, TeamSnapshot } from "@/lib/api";
import { useDescriptive, useTeamSnapshots, useExploratory } from "@/lib/hooks";
import Flag from "@/components/ui/Flag";
import Spinner from "@/components/ui/Spinner";
import ExploratoriaView from "@/components/dashboard/ExploratoriaView";
import TeamProfile from "@/components/dashboard/TeamProfile";
import JogoView from "@/components/dashboard/JogoView";

// Três abas em fluxo temporal: torneio (passado agregado) → times/confrontos →
// o jogo (passado OU futuro de UMA partida, com plano). As antigas 6 camadas
// foram consolidadas: Descritiva→Panorama; Exploratória→Seleções & Confrontos;
// Diagnóstica+Preditiva+Prescritiva+Preventiva→O Jogo.
const TIPOS: { id: string; label: string; pronto: boolean; hint: string }[] = [
  { id: "panorama", label: "Panorama", pronto: true, hint: "Como está o torneio" },
  { id: "selecoes", label: "Seleções & Confrontos", pronto: true, hint: "Como é cada time e como se comparam" },
  { id: "jogo", label: "O Jogo", pronto: true, hint: "O que aconteceu / o que vem em uma partida" },
];

interface Props {
  matches: Match[];
  activeSnapshot: number;
  isAdmin: boolean;
  selectedTeams: string[];
  onToggleTeam: (team: string) => void;
  onClearTeams: () => void;
  onFocusTeams?: (teams: string[]) => void;
  onSnapshotChange?: (snap: number) => void;
  onPredictiveActive?: (active: boolean) => void;
}

export default function AnaliseTab({
  matches,
  activeSnapshot,
  isAdmin,
  selectedTeams,
  onToggleTeam,
  onClearTeams,
  onFocusTeams,
  onSnapshotChange,
  onPredictiveActive,
}: Props) {
  const [tipo, setTipo] = React.useState("jogo");
  const [teamFocusTouched, setTeamFocusTouched] = React.useState(false);
  const isPanorama = tipo === "panorama";
  const isSelecoes = tipo === "selecoes";
  const isJogo = tipo === "jogo";

  // Na aba "O Jogo" a Preditiva está ativa → colore as bolinhas pelo acerto.
  React.useEffect(() => {
    onPredictiveActive?.(isJogo && isAdmin);
    return () => onPredictiveActive?.(false);
  }, [isJogo, isAdmin, onPredictiveActive]);

  const allTeams = React.useMemo(() => {
    const set = new Set<string>();
    for (const m of matches) { if (m.home_team) set.add(m.home_team); if (m.away_team) set.add(m.away_team); }
    return Array.from(set).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [matches]);

  // snapshot (índice cronológico) de cada jogo finalizado
  const matchSnapshot = React.useMemo(() => {
    const fin = matches.filter((m) => m.status === "finalizado")
      .sort((a, b) => String(a.date_utc).localeCompare(String(b.date_utc)));
    const map = new Map<string, number>();
    fin.forEach((m, i) => map.set(m.match_id, i + 1));
    return map;
  }, [matches]);

  const snapshotTeams = React.useMemo(() => {
    const match = matches.find((m) => matchSnapshot.get(m.match_id) === activeSnapshot);
    return uniqueTeams([match?.home_team, match?.away_team]);
  }, [matches, matchSnapshot, activeSnapshot]);
  const shouldUseSnapshotFocus = selectedTeams.length === 0 && !teamFocusTouched && (isSelecoes || isJogo) && snapshotTeams.length > 0;
  const focusedTeams = shouldUseSnapshotFocus ? snapshotTeams : selectedTeams;

  const toggleTeam = React.useCallback((t: string) => {
    setTeamFocusTouched(true);
    if (shouldUseSnapshotFocus) {
      const next = snapshotTeams.includes(t) ? snapshotTeams.filter((team) => team !== t) : [...snapshotTeams, t];
      for (const team of next) onToggleTeam(team);
      return;
    }
    onToggleTeam(t);
  }, [onToggleTeam, shouldUseSnapshotFocus, snapshotTeams]);

  const clearTeamFocus = React.useCallback(() => {
    setTeamFocusTouched(true);
    onClearTeams();
  }, [onClearTeams]);

  // Panorama (Descritiva) e perfis das seleções em foco.
  const { digest, isLoading: digestLoading } = useDescriptive(activeSnapshot, isAdmin && isPanorama);
  // "O que decide os jogos" (correlações de torneio) vem da camada exploratória.
  const { explore } = useExploratory(activeSnapshot, isAdmin && isPanorama);
  const { snapshots: teamSnaps } = useTeamSnapshots(activeSnapshot);
  const selectedRows = React.useMemo(
    () => teamSnaps.filter((s: TeamSnapshot) => focusedTeams.includes(s.team)),
    [teamSnaps, focusedTeams],
  );

  if (!isAdmin) return <Aviso texto="Acesso restrito a administradores." />;

  return (
    <div className="v2-analytics-shell">
      <nav className="v2-analytics-tabs">
        {TIPOS.map((t) => (
          <button
            key={t.id}
            onClick={() => t.pronto && setTipo(t.id)}
            disabled={!t.pronto}
            title={t.pronto ? t.hint : `${t.hint} · em breve`}
            style={{ ...subTabStyle(t.id === tipo), opacity: t.pronto ? 1 : 0.45, cursor: t.pronto ? "pointer" : "not-allowed" }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <TeamFocusBar teams={allTeams} selected={focusedTeams} onToggle={toggleTeam} onClear={clearTeamFocus} />

      {isSelecoes ? (
        <ExploratoriaView snapshot={activeSnapshot} enabled={isAdmin && isSelecoes} matches={matches} selectedTeams={focusedTeams} onToggleTeam={toggleTeam} onFocusTeams={(teams) => { setTeamFocusTouched(true); onFocusTeams?.(teams); }} />
      ) : isJogo ? (
        <JogoView
          matches={matches}
          activeSnapshot={activeSnapshot}
          isAdmin={isAdmin}
          selectedTeams={focusedTeams}
          onSnapshotChange={onSnapshotChange}
        />
      ) : (
        digestLoading
          ? <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}><Spinner /></div>
          : <DigestView digest={digest} decide={explore?.decide ?? []} selectedTeams={focusedTeams} selectedRows={selectedRows} />
      )}
    </div>
  );
}

function DigestView({ digest, decide = [], selectedTeams = [], selectedRows = [] }: { digest?: DescriptiveDigest; decide?: { metric: string; label: string; corr: number; n?: number }[]; selectedTeams?: string[]; selectedRows?: TeamSnapshot[] }) {
  // Com seleção(ões) marcada(s), o panorama vira o das seleções (troca no lugar).
  if (selectedRows.length > 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {selectedRows.map((r) => <TeamProfile key={r.team} snapshot={r} variant="full" />)}
      </div>
    );
  }
  if (!digest || !digest.totais) {
    return <Aviso texto="Sem panorama disponível ainda — rode uma coleta." />;
  }
  const t = digest.totais;
  const num = (v: number) => v.toFixed(2).replace(".", ",");
  const goalGap = t.xg_por_jogo != null ? t.gols_por_jogo - t.xg_por_jogo : null;
  const essentialLeaders = digest.lideres.filter((l) =>
    ["Melhor ataque", "Melhor defesa", "Mais eficiente (gols − xG)", "Mais com a bola"].includes(l.categoria)
  ).slice(0, 4);
  const cards: { label: string; value: string | number; note: string; color?: string }[] = [
    { label: "Jogos", value: t.jogos, note: "amostra do recorte" },
    { label: "Gols", value: t.gols, note: `${num(t.gols_por_jogo)} por jogo`, color: "var(--green)" },
    { label: "xG/jogo", value: t.xg_por_jogo != null ? num(t.xg_por_jogo) : "—", note: goalGapText(goalGap) },
    { label: "Com vencedor", value: `${t.pct_decisivos}%`, note: `${t.decisivos} de ${t.jogos} jogos`, color: "var(--accent)" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        {cards.map((card) => (
          <SummaryCard key={card.label} {...card} />
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 14, alignItems: "start" }}>
        {digest.tendencia.length > 0 && <TendenciaTable rows={digest.tendencia} />}
        <ListPanel titulo="Referências do torneio">
          {essentialLeaders.length ? essentialLeaders.map((l, i) => {
            const on = selectedTeams.includes(l.team);
            return <LeaderRow key={i} item={l} active={on} />;
          }) : <EmptyRow texto="Sem referências calculadas ainda." />}
        </ListPanel>
      </div>

      {decide.length > 0 && <DecidePanel decide={decide} />}
    </div>
  );
}

// O que mais separa quem vence de quem perde no torneio (correlação com o
// resultado). Insight de torneio — vive no Panorama, não no perfil de um time.
function DecidePanel({ decide }: { decide: { metric: string; label: string; corr: number; n?: number }[] }) {
  const rows = decide.filter((d) => typeof d.corr === "number").slice(0, 8);
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((d) => Math.abs(d.corr)), 0.01);
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        O que decide os jogos
      </div>
      <div style={{ padding: "10px 16px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.4, marginBottom: 2 }}>
          O quanto cada fator anda junto com vencer (correlação). Mais alto = mais associado ao resultado.
        </div>
        {rows.map((d) => {
          const pct = (Math.abs(d.corr) / max) * 100;
          const pos = d.corr >= 0;
          return (
            <div key={d.metric} style={{ display: "grid", gridTemplateColumns: "150px 1fr 44px", gap: 8, alignItems: "center", fontSize: 12 }}>
              <span style={{ color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{d.label}</span>
              <div style={{ height: 8, background: "var(--surface2)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: pos ? "#3fb950" : "#f85149" }} />
              </div>
              <span style={{ textAlign: "right", fontWeight: 700, color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>{d.corr.toFixed(2).replace(".", ",")}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function goalGapText(gap: number | null) {
  if (gap == null) return "sem xG no recorte";
  const abs = Math.abs(gap).toFixed(2).replace(".", ",");
  if (gap >= 0.15) return `+${abs} gols vs xG`;
  if (gap <= -0.15) return `-${abs} gols vs xG`;
  return "em linha com os gols";
}

function uniqueTeams(teams: Array<string | null | undefined>): string[] {
  return Array.from(new Set(teams.filter((team): team is string => !!team)));
}

function SummaryCard({ label, value, note, color = "var(--accent)" }: { label: string; value: string | number; note: string; color?: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--surface2)", borderRadius: 8, padding: "12px 14px", minHeight: 86 }}>
      <div style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</div>
      <div style={{ fontSize: 23, fontWeight: 850, color, marginTop: 5, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 7, lineHeight: 1.35 }}>{note}</div>
    </div>
  );
}

function LeaderRow({ item, active }: { item: DescriptiveDigest["lideres"][number]; active: boolean }) {
  return (
    <li style={{ ...rowStyle, background: active ? "#10213a" : undefined }}>
      <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{item.categoria}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 650, textAlign: "right", color: active ? "var(--accent)" : "var(--text)" }}>
        <Flag team={item.team} height={13} />{item.team}
        <span style={{ color: "var(--accent)", fontWeight: 800, fontSize: 11.5 }}>{item.valor}</span>
      </span>
    </li>
  );
}

function EmptyRow({ texto }: { texto: string }) {
  return <li style={{ padding: "14px 16px", color: "var(--text-muted)", fontSize: 12.5 }}>{texto}</li>;
}


function TendenciaTable({ rows }: { rows: DescriptiveDigest["tendencia"] }) {
  const cols: [string, (r: DescriptiveDigest["tendencia"][0]) => string | number][] = [
    ["Jogos", (r) => r.jogos],
    ["Gols/jogo", (r) => r.gols_por_jogo.toFixed(2).replace(".", ",")],
    ["xG médio", (r) => (r.xg_medio != null ? r.xg_medio.toFixed(2).replace(".", ",") : "—")],
  ];
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        Tendência por rodada
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ ...thStyle, textAlign: "left" }}>Rodada</th>
              {cols.map(([h]) => <th key={h} style={thStyle}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.rodada}>
                <td style={{ ...tdStyle, textAlign: "left", fontWeight: 600 }}>{r.rodada}</td>
                {cols.map(([h, f]) => <td key={h} style={tdStyle}>{f(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const thStyle: React.CSSProperties = { padding: "8px 12px", textAlign: "center", fontSize: 11, color: "var(--text-muted)", fontWeight: 600, borderBottom: "1px solid var(--surface)" };
const tdStyle: React.CSSProperties = { padding: "9px 12px", textAlign: "center", color: "var(--text)", borderBottom: "1px solid var(--surface)" };

const rowStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "9px 16px", borderTop: "1px solid var(--surface)", fontSize: 13,
};

function ListPanel({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section style={{ background: "var(--background)", border: "1px solid var(--surface2)", borderRadius: 12, overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, background: "var(--surface)", borderBottom: "1px solid var(--surface2)" }}>
        {titulo}
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{children}</ul>
    </section>
  );
}

function Aviso({ texto, cor = "var(--text-muted)" }: { texto: string; cor?: string }) {
  return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: cor }}>{texto}</div>;
}

// Barra de foco — chips das seleções em foco + popover de busca pra adicionar.
function TeamFocusBar({ teams, selected, onToggle, onClear }: { teams: string[]; selected: string[]; onToggle: (t: string) => void; onClear: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const filtered = q ? teams.filter((t) => norm(t).includes(norm(q))) : teams;
  return (
    <div className="v2-team-focus-bar">
      <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--text-muted)", fontWeight: 700, flexShrink: 0 }}>Em foco</span>
      {selected.length === 0 && <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>nenhuma — mostrando o panorama geral</span>}
      {selected.map((t) => (
        <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, background: "#10213a", border: "1px solid var(--accent)", borderRadius: 16, padding: "3px 5px 3px 10px", color: "var(--text)" }}>
          <Flag team={t} height={12} />{t}
          <button onClick={() => onToggle(t)} title="Remover" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14, lineHeight: 1, padding: "0 3px" }}>×</button>
        </span>
      ))}
      <div ref={ref} className="v2-team-focus-picker">
        <button onClick={() => setOpen((o) => !o)}
          style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, background: open ? "#1a2233" : "var(--surface)", border: `1px solid ${open ? "var(--accent)" : "var(--surface2)"}`, color: "var(--text)", borderRadius: 16, padding: "4px 12px", cursor: "pointer", fontFamily: "inherit" }}>
          ＋ seleção
        </button>
        {open && (
          <div className="v2-team-focus-popover">
            <div style={{ padding: 8, borderBottom: "1px solid var(--surface2)" }}>
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar seleção..."
                style={{ width: "100%", background: "var(--background)", color: "var(--text)", border: "1px solid var(--surface2)", borderRadius: 6, padding: "6px 9px", fontSize: 12.5, outline: "none", fontFamily: "inherit" }} />
            </div>
            <div className="v2-team-focus-options">
              {filtered.map((t) => {
                const on = selected.includes(t);
                return (
                  <button key={t} onClick={() => onToggle(t)} title={t}
                    style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", textAlign: "left", padding: "5px 8px", borderRadius: 6, fontSize: 12, cursor: "pointer", fontFamily: "inherit", background: on ? "#10213a" : "transparent", border: `1px solid ${on ? "var(--accent)" : "transparent"}`, color: on ? "var(--text)" : "var(--text-muted)" }}>
                    <Flag team={t} height={11} />
                    <span style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t}</span>
                    {on && <span style={{ color: "var(--accent)", fontSize: 10, flexShrink: 0 }}>✓</span>}
                  </button>
                );
              })}
              {filtered.length === 0 && <div style={{ gridColumn: "1 / -1", fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: 8 }}>nenhuma</div>}
            </div>
          </div>
        )}
      </div>
      {selected.length > 0 && (
        <button onClick={onClear} style={{ fontSize: 11.5, color: "var(--accent)", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}>limpar ({selected.length})</button>
      )}
    </div>
  );
}


// Mesmo visual das abas do dashboard (v2/page.tsx → tabStyle).
function subTabStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? "#1a2233" : "#161b22",
    border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
    color: active ? "#e6edf3" : "#8b949e",
    borderRadius: 6,
    padding: "5px 12px",
    fontSize: 13,
    fontFamily: "inherit",
  };
}
