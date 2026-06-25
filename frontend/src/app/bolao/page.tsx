"use client";

import { useState, useEffect, useCallback, Fragment } from "react";
import {
  bolao, scoring, users, analytics,
  type Pool, type PoolMatch, type ScoringRule, type PoolGrid,
  type ScoringCriterion, type PoolRanking, type PoolScope, type AppUser, type Match,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { FLAGS } from "@/lib/teamUtils";
import { STAGE_ORDER, stageLabel } from "@/lib/stages";
import Modal from "@/components/ui/Modal";
import RulesModal from "./RulesModal";

// Diálogo in-app (substitui prompt/confirm/alert nativos).
type DialogState = {
  title: string;
  message?: string;
  input?: { label: string; placeholder?: string };
  confirmText: string;
  danger?: boolean;
  onConfirm: (value: string) => Promise<void>;
};

// ── Helpers ─────────────────────────────────────────────────────────────────
const card: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 };
const inputStyle: React.CSSProperties = { width: "100%", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 12px", color: "var(--text)", fontSize: "0.9rem", outline: "none", boxSizing: "border-box" };
const btn: React.CSSProperties = { background: "var(--accent)", color: "#0d1117", border: "none", borderRadius: 6, padding: "10px", fontWeight: 700, fontSize: "0.9rem", cursor: "pointer" };
const primaryBtn: React.CSSProperties = { border: "none", borderRadius: 6, padding: "8px 18px", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", background: "var(--accent)", color: "#0d1117" };
const cancelBtn: React.CSSProperties = { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 16px", fontSize: "0.85rem", cursor: "pointer" };

function flatten(pools: Pool[], depth = 0): { pool: Pool; depth: number }[] {
  const out: { pool: Pool; depth: number }[] = [];
  for (const p of pools) {
    out.push({ pool: p, depth });
    if (p.children?.length) out.push(...flatten(p.children, depth + 1));
  }
  return out;
}
function findPool(pools: Pool[], id: number): Pool | null {
  for (const p of pools) {
    if (p.id === id) return p;
    const c = p.children ? findPool(p.children, id) : null;
    if (c) return c;
  }
  return null;
}
function scopeLabel(s: PoolScope): string {
  if (s.type === "all") return "Todos os jogos";
  if (s.type === "stage") return (s.stages ?? []).map(stageLabel).join(", ") || "Por fase";
  return `${(s.match_ids ?? []).length} jogos escolhidos`;
}

const TZ = "America/Sao_Paulo";
function dayKey(iso: string | null): string {
  if (!iso) return "0000";
  try { return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso)); }
  catch { return "0000"; }
}
function dayLabel(iso: string | null): string {
  if (!iso) return "Sem data";
  try {
    const s = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, weekday: "short", day: "2-digit", month: "short" }).format(new Date(iso));
    return s.charAt(0).toUpperCase() + s.slice(1).replace(/\.$/, "");
  } catch { return "Sem data"; }
}
function timeLabel(iso: string | null): string {
  if (!iso) return "";
  try { return new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(new Date(iso)); }
  catch { return ""; }
}

// ── Match card (palpite) ─────────────────────────────────────────────────────
type Outcome = "exact" | "partial" | "miss" | "nopred" | "pending";
const OUTCOME_COLOR: Record<Outcome, string> = {
  exact: "#22c55e", partial: "#eab308", miss: "#ef4444", nopred: "#6b7280", pending: "#58a6ff",
};

function MatchCard({ m, onSave, saving, index }: { m: PoolMatch; onSave: (id: string, h: number, a: number) => Promise<void>; saving: boolean; index: number }) {
  const [home, setHome] = useState(m.prediction ? String(m.prediction.home_score) : "");
  const [away, setAway] = useState(m.prediction ? String(m.prediction.away_score) : "");
  const [dirty, setDirty] = useState(false);
  const [hover, setHover] = useState(false);
  const finished = m.status === "finalizado";
  const live = m.status === "em_andamento";
  const playable = m.status === "agendado";
  const hasResult = m.home_score != null && m.away_score != null;
  const hasPred = m.prediction != null;
  const pts = m.prediction?.points ?? null;
  const exact = finished && hasResult && hasPred
    && m.prediction!.home_score === m.home_score && m.prediction!.away_score === m.away_score;
  const outcome: Outcome = !finished || !hasResult ? "pending"
    : !hasPred ? "nopred" : exact ? "exact" : (pts ?? 0) > 0 ? "partial" : "miss";
  const accent = OUTCOME_COLOR[outcome];
  // Palpite salvo é definitivo: só o admin pode alterar depois.
  const { user } = useAuth();
  const locked = playable && hasPred && !user?.is_admin;

  async function handleSave() {
    const h = parseInt(home), a = parseInt(away);
    if (isNaN(h) || isNaN(a) || h < 0 || a < 0) return;
    await onSave(m.match_id, h, a);
    setDirty(false);
  }
  const inp: React.CSSProperties = { width: 40, textAlign: "center", background: "var(--surface2)", border: `1px solid ${dirty ? "var(--accent)" : "var(--border)"}`, borderRadius: 6, padding: "6px 4px", color: "var(--text)", fontSize: "1rem", fontWeight: 700, outline: "none", transition: "border-color .15s" };
  const flagStyle: React.CSSProperties = { fontSize: "1.3rem", transition: "transform .16s", transform: hover ? "scale(1.12)" : "none" };

  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        ...card, position: "relative", padding: "9px 14px 9px 18px", display: "flex", alignItems: "center", gap: 10,
        overflow: "hidden", borderColor: hover ? accent : "var(--border)", opacity: finished ? 0.93 : 1,
        boxShadow: hover ? `0 6px 20px -8px ${accent}66` : "none",
        transform: hover ? "translateY(-2px)" : "none",
        transition: "transform .16s ease, box-shadow .16s ease, border-color .16s ease, opacity .16s",
        animation: "matchIn .3s ease backwards", animationDelay: `${Math.min(index, 14) * 25}ms`,
      }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: playable ? "transparent" : accent }} />
      <div style={{ width: 56, flexShrink: 0, lineHeight: 1.3 }}>
        <div style={{ fontSize: "0.66rem", color: "var(--text-muted)" }}>#{String(m.match_number).padStart(3, "0")}</div>
        <div style={{ fontSize: "0.72rem", fontWeight: live ? 800 : 400, color: live ? "#ef4444" : "var(--text-muted)" }}>{live ? "● AO VIVO" : finished ? "Encerrado" : timeLabel(m.date_utc)}</div>
      </div>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 7, minWidth: 0 }}>
          <span style={{ fontSize: "0.86rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.home_team ?? "A definir"}</span>
          <span style={flagStyle}>{FLAGS[m.home_team ?? ""] ?? "🏳️"}</span>
        </div>
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", minWidth: 78 }}>
          {playable ? (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <input type="number" min={0} max={99} value={home} disabled={locked} title={locked ? "Palpite já salvo — só o admin altera" : undefined} onChange={e => { setHome(e.target.value); setDirty(true); }} style={{ ...inp, opacity: locked ? 0.65 : 1, cursor: locked ? "not-allowed" : "text" }} />
              <span style={{ color: "var(--text-muted)", fontWeight: 700 }}>×</span>
              <input type="number" min={0} max={99} value={away} disabled={locked} title={locked ? "Palpite já salvo — só o admin altera" : undefined} onChange={e => { setAway(e.target.value); setDirty(true); }} style={{ ...inp, opacity: locked ? 0.65 : 1, cursor: locked ? "not-allowed" : "text" }} />
            </div>
          ) : (
            <span style={{ fontSize: "1.15rem", fontWeight: 800, color: "var(--text)", whiteSpace: "nowrap" }}>{hasResult ? `${m.home_score} – ${m.away_score}` : "—"}</span>
          )}
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
          <span style={flagStyle}>{FLAGS[m.away_team ?? ""] ?? "🏳️"}</span>
          <span style={{ fontSize: "0.86rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.away_team ?? "A definir"}</span>
        </div>
      </div>
      <div style={{ width: 118, flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
        {playable ? (
          <button disabled={saving || locked || (!dirty && hasPred)} onClick={handleSave} style={{ ...btn, padding: "6px 14px", fontSize: "0.78rem", background: !locked && (dirty || !hasPred) ? "var(--accent)" : "var(--surface2)", color: !locked && (dirty || !hasPred) ? "#0d1117" : "var(--text-muted)", cursor: saving || locked || (!dirty && hasPred) ? "default" : "pointer", opacity: saving ? 0.6 : 1, transition: "background .15s" }}>
            {saving ? "…" : locked ? "Salvo 🔒" : hasPred && !dirty ? "Salvo ✓" : hasPred ? "Atualizar" : "Salvar"}
          </button>
        ) : finished ? (
          hasPred ? (
            <>
              <span style={{ fontSize: "0.74rem", fontWeight: 800, padding: "3px 10px", borderRadius: 20, color: accent, background: `${accent}22`, border: `1px solid ${accent}55`, whiteSpace: "nowrap" }}>
                {exact ? `🎯 +${pts}` : (pts ?? 0) > 0 ? `+${pts} pts` : "0 pts"}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>palpite {m.prediction!.home_score}–{m.prediction!.away_score}</span>
            </>
          ) : (
            <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)" }}>sem palpite</span>
          )
        ) : (
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>{hasPred ? `palpite ${m.prediction!.home_score}–${m.prediction!.away_score}` : "sem palpite"}</span>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{label}</label>
      {children}
    </div>
  );
}
function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} style={{ border: "1px solid " + (on ? "var(--accent)" : "var(--border)"), background: on ? "rgba(88,166,255,0.12)" : "none", color: on ? "var(--accent)" : "var(--text-muted)", borderRadius: 6, padding: "5px 10px", fontSize: "0.78rem", fontWeight: 600, cursor: "pointer" }}>{children}</button>;
}

function PoolStat({ label, value, big, first }: { label: string; value: React.ReactNode; big?: boolean; first?: boolean }) {
  return (
    <div style={{ flex: 1, minWidth: 0, padding: "9px 8px", textAlign: "center", borderLeft: first ? "none" : "1px solid var(--border)" }}>
      <div style={{ fontWeight: 800, fontSize: big ? "1.1rem" : "0.82rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginTop: 3 }}>{label}</div>
    </div>
  );
}

const STATUS_META: Record<string, { label: string; color: string }> = {
  a_iniciar: { label: "A iniciar", color: "#8b949e" },
  em_andamento: { label: "Em andamento", color: "#d29922" },
  finalizado: { label: "Finalizado", color: "#3fb950" },
};

function StatusBadge({ status }: { status?: string }) {
  const m = STATUS_META[status ?? "a_iniciar"] ?? STATUS_META.a_iniciar;
  return (
    <span style={{
      fontSize: "0.58rem", fontWeight: 700, color: m.color, border: `1px solid ${m.color}66`,
      background: `${m.color}1a`, borderRadius: 4, padding: "1px 6px", flexShrink: 0,
      whiteSpace: "nowrap", textTransform: "uppercase", letterSpacing: "0.03em",
    }}>{m.label}</span>
  );
}

function PoolListCard({ pool, onOpen, index }: { pool: Pool; onOpen: () => void; index: number }) {
  const [hover, setHover] = useState(false);
  const accent = "#58a6ff";
  return (
    <button onClick={onOpen} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        ...card, position: "relative", overflow: "hidden", padding: 0, textAlign: "left", cursor: "pointer",
        color: "var(--text)", display: "flex", flexDirection: "column",
        borderColor: hover ? accent : "var(--border)",
        boxShadow: hover ? `0 12px 28px -12px ${accent}80` : "none",
        transform: hover ? "translateY(-3px)" : "none",
        transition: "transform .16s ease, box-shadow .16s ease, border-color .16s ease",
        animation: "poolIn .3s ease backwards", animationDelay: `${Math.min(index, 12) * 35}ms`,
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", background: `linear-gradient(135deg, ${accent}14, transparent 62%)` }}>
        <div style={{ width: 42, height: 42, borderRadius: 11, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface2)", fontSize: "1.3rem", transition: "transform .16s", transform: hover ? "scale(1.08)" : "none" }}>{pool.is_group ? "🗂️" : "🎯"}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: "0.98rem", display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pool.name}</span>
            {pool.is_group && <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px", flexShrink: 0 }}>grupo</span>}
            <StatusBadge status={pool.status} />
          </div>
          {pool.status === "finalizado" && (pool.winners?.length ?? 0) > 0 ? (
            <div style={{ fontSize: "0.78rem", color: "#f5c542", fontWeight: 700, marginTop: 3, display: "flex", alignItems: "center", gap: 5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              <span>🏆</span>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{pool.winners!.join(", ")}</span>
            </div>
          ) : (
            <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {pool.is_group ? `${pool.children?.length ?? 0} ${(pool.children?.length ?? 0) === 1 ? "bolão" : "bolões"}` : scopeLabel(pool.scope)}
            </div>
          )}
        </div>
        <span style={{ color: accent, fontSize: "0.82rem", fontWeight: 700, flexShrink: 0, transform: hover ? "translateX(3px)" : "none", transition: "transform .16s" }}>Abrir →</span>
      </div>
      <div style={{ display: "flex", borderTop: "1px solid var(--border)", background: "var(--surface)" }}>
        <PoolStat first label="Participantes" value={pool.n_members ?? 0} big />
        <PoolStat label={pool.is_group ? "Bolões" : "Jogos"} value={pool.is_group ? (pool.children?.length ?? 0) : (pool.n_matches ?? 0)} big />
        <PoolStat label="Regra" value={pool.rule_name ?? pool.rule?.name ?? "—"} />
      </div>
    </button>
  );
}

// ── Comemoração do vencedor (confete + parabéns) ─────────────────────────────
const CONFETTI_COLORS = ["#f5c542", "#58a6ff", "#3fb950", "#db61a2", "#f0883e", "#bc8cff", "#79c0ff"];

function WinnerCelebration({ poolName, onDone }: { poolName: string; onDone: () => void }) {
  const [pieces] = useState(() =>
    Array.from({ length: 110 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 1.2,
      dur: 2.6 + Math.random() * 2.2,
      color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
      w: 6 + Math.random() * 6,
      h: 9 + Math.random() * 8,
      rot: Math.random() * 360,
    })),
  );
  useEffect(() => {
    const t = setTimeout(onDone, 6500);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, pointerEvents: "none", overflow: "hidden" }}>
      <style>{`
        @keyframes confettiFall { 0% { transform: translateY(-15vh) rotate(0deg); opacity: 1; } 100% { transform: translateY(110vh) rotate(740deg); opacity: .85; } }
        @keyframes celebPop { 0% { transform: translateX(-50%) scale(.7); opacity: 0; } 55% { transform: translateX(-50%) scale(1.06); } 100% { transform: translateX(-50%) scale(1); opacity: 1; } }
        @keyframes trophyBob { 0%,100% { transform: translateY(0) rotate(-6deg); } 50% { transform: translateY(-8px) rotate(6deg); } }
      `}</style>
      {pieces.map((p) => (
        <span key={p.id} style={{
          position: "absolute", top: 0, left: `${p.left}%`, width: p.w, height: p.h,
          background: p.color, borderRadius: 1, transform: `rotate(${p.rot}deg)`,
          animation: `confettiFall ${p.dur}s linear ${p.delay}s forwards`,
        }} />
      ))}
      <div style={{ position: "fixed", top: "26%", left: "50%", pointerEvents: "auto", textAlign: "center", animation: "celebPop .55s ease both" }}>
        <div style={{ fontSize: "3.4rem", animation: "trophyBob 1.1s ease-in-out infinite", display: "inline-block" }}>🏆</div>
        <div style={{ position: "relative", background: "var(--surface)", border: "1px solid var(--accent)", borderRadius: 14, padding: "22px 34px 18px", boxShadow: "0 18px 56px -14px rgba(0,0,0,.65)", marginTop: 6 }}>
          <button onClick={onDone} title="Fechar" aria-label="Fechar"
            style={{ position: "absolute", top: 8, right: 8, width: 24, height: 24, borderRadius: 6, background: "rgba(248,81,73,0.12)", border: "1px solid #f85149", color: "#f85149", cursor: "pointer", fontSize: "0.95rem", fontWeight: 800, lineHeight: 1, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>×</button>
          <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text)" }}>Parabéns! 🥳</div>
          <div style={{ fontSize: "0.96rem", color: "var(--text-muted)", marginTop: 7 }}>
            Você venceu o bolão <strong style={{ color: "#f5c542" }}>{poolName}</strong>!
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Palpites ─────────────────────────────────────────────────────────────────
function PredictionsTab({ pool, onPickChild }: { pool: Pool; onPickChild: (id: number) => void }) {
  const [matches, setMatches] = useState<PoolMatch[]>([]);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"todos" | "a_jogar" | "jogados">("todos");

  const load = useCallback(async () => {
    if (pool.is_group) { setLoading(false); return; }
    setLoading(true);
    try { setMatches(await bolao.poolMatches(pool.id)); } finally { setLoading(false); }
  }, [pool.id, pool.is_group]);
  useEffect(() => { load(); }, [load]);

  async function save(id: string, h: number, a: number) {
    setSavingId(id);
    try { await bolao.predict(pool.id, { match_id: id, home_score: h, away_score: a }); await load(); }
    finally { setSavingId(null); }
  }

  if (pool.is_group) {
    return (
      <div style={{ maxWidth: 600, margin: "0 auto", padding: "28px 16px" }}>
        <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>Este é um bolão por fases — escolha uma fase para palpitar:</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {(pool.children ?? []).map(c => (
            <button key={c.id} onClick={() => onPickChild(c.id)} style={{ ...card, padding: "14px 18px", textAlign: "left", cursor: "pointer", color: "var(--text)", fontSize: "0.9rem", fontWeight: 600 }}>
              {c.name} <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.8rem" }}>· {scopeLabel(c.scope)}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (loading) return <div style={{ padding: 32, color: "var(--text-muted)" }}>Carregando jogos…</div>;
  if (matches.length === 0) return <div style={{ padding: 32, color: "var(--text-muted)", textAlign: "center" }}>Nenhum jogo neste escopo ainda.</div>;

  const predicted = matches.filter(m => m.prediction).length;
  const totalPts = matches.reduce((sum, m) => sum + (m.prediction?.points ?? 0), 0);
  const exactCount = matches.filter(m =>
    m.status === "finalizado" && m.prediction && m.home_score != null && m.away_score != null
    && m.prediction.home_score === m.home_score && m.prediction.away_score === m.away_score).length;
  const aJogar = matches.filter(m => m.status !== "finalizado").length;
  const jogados = matches.length - aJogar;

  const visible = matches.filter(m =>
    filter === "todos" ? true : filter === "jogados" ? m.status === "finalizado" : m.status !== "finalizado");

  // agrupa por dia (cronológico)
  const ordered = [...visible].sort((a, b) =>
    (a.date_utc ?? "").localeCompare(b.date_utc ?? "") || a.match_number - b.match_number);
  const days: { key: string; label: string; list: PoolMatch[] }[] = [];
  for (const m of ordered) {
    const k = dayKey(m.date_utc);
    const grp = days.find(d => d.key === k);
    if (grp) grp.list.push(m);
    else days.push({ key: k, label: dayLabel(m.date_utc), list: [m] });
  }

  const FILTERS: [typeof filter, string, number][] = [
    ["todos", "Todos", matches.length],
    ["a_jogar", "A jogar", aJogar],
    ["jogados", "Já jogados", jogados],
  ];

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "20px 16px" }}>
      <style>{`@keyframes matchIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      <div style={{ ...card, padding: "14px 20px", marginBottom: 16, display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
        <Stat label="Palpites" value={`${predicted}/${matches.length}`} />
        <Stat label="Pontos" value={totalPts} color="var(--accent)" big />
        <Stat label="Cravados" value={exactCount} color="#22c55e" />
        <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginLeft: "auto" }}>Código <strong style={{ color: "var(--text)" }}>#{pool.id}</strong> · compartilhe pra outros entrarem</div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {FILTERS.map(([k, label, n]) => (
          <Chip key={k} on={filter === k} onClick={() => setFilter(k)}>{label} <span style={{ opacity: 0.7 }}>({n})</span></Chip>
        ))}
      </div>

      {days.length === 0 && <div style={{ padding: 28, color: "var(--text-muted)", textAlign: "center" }}>Nenhum jogo neste filtro.</div>}
      {days.map(({ key, label, list }) => {
        const allDone = list.every(m => m.status === "finalizado");
        const dayPred = list.filter(m => m.prediction).length;
        return (
          <div key={key} style={{ marginBottom: 22 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 9 }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 800, color: allDone ? "var(--text-muted)" : "var(--accent)", letterSpacing: "0.02em" }}>{label}</span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", padding: "1px 8px", borderRadius: 20, border: "1px solid var(--border)" }}>{allDone ? "encerrados" : `${dayPred}/${list.length} palpitados`}</span>
              <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {list.map((m, i) => <MatchCard key={m.match_id} m={m} onSave={save} saving={savingId === m.match_id} index={i} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Stat({ label, value, color, big }: { label: string; value: React.ReactNode; color?: string; big?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontWeight: 800, fontSize: big ? "1.45rem" : "1.05rem", color: color ?? "var(--text)", lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

// ── Ranking ──────────────────────────────────────────────────────────────────
const MEDAL = ["#f5c542", "#c0c0c0", "#cd7f32"];

function RankTable({ rows }: { rows: PoolRanking["ranking"] }) {
  if (rows.length === 0) return <div style={{ ...card, padding: 28, color: "var(--text-muted)", textAlign: "center", fontSize: "0.9rem" }}>Ninguém pontuou ainda — os pontos aparecem quando os jogos forem acontecendo.</div>;
  // ranking de competição: empate divide a mesma posição
  const positions: number[] = [];
  rows.forEach((r, i) => positions.push(i > 0 && rows[i - 1].total_points === r.total_points ? positions[i - 1] : i + 1));
  const max = Math.max(...rows.map(r => r.total_points), 1);
  const th: React.CSSProperties = { padding: "10px 16px", fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" };
  const td: React.CSSProperties = { padding: "11px 16px", fontSize: "0.92rem", color: "var(--text)", verticalAlign: "middle" };
  return (
    <div style={{ ...card, overflow: "hidden" }}>
      <style>{`.bolao-rank tbody tr:hover { background: var(--surface2); }`}</style>
      <table className="bolao-rank" style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
        <thead>
          <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
            <th style={{ ...th, textAlign: "center", width: 56 }}>#</th>
            <th style={{ ...th, textAlign: "left", width: 240 }}>Participante</th>
            <th style={{ ...th, textAlign: "left" }}>Pontuação</th>
            <th style={{ ...th, textAlign: "right", width: 120 }}>Palpites</th>
            <th style={{ ...th, textAlign: "right", width: 120 }}>Pontos</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const pos = positions[i];
            const medal = pos <= 3 ? MEDAL[pos - 1] : null;
            const top = pos === 1;
            const pct = max > 0 ? Math.max(3, (r.total_points / max) * 100) : 0;
            const barColor = medal ?? "var(--accent)";
            return (
              <tr key={r.user_id} style={{ borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : "none", background: top ? "rgba(245,197,66,0.06)" : "transparent", transition: "background .12s" }}>
                <td style={{ ...td, textAlign: "center", fontWeight: 800, color: medal ?? "var(--text-muted)" }}>{pos}º</td>
                <td style={td}>
                  <span style={{ display: "flex", alignItems: "center", gap: 11 }}>
                    <span style={{ width: 30, height: 30, borderRadius: "50%", background: top ? "linear-gradient(135deg,#e3a008,#f5c542)" : "linear-gradient(135deg,#2ea043,#3fb950)", color: "#04130a", fontWeight: 800, fontSize: "0.82rem", display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{(r.name || "?").charAt(0).toUpperCase()}</span>
                    <span style={{ fontWeight: top ? 800 : 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.name}</span>
                  </span>
                </td>
                <td style={{ ...td, paddingRight: 28 }}>
                  <div style={{ height: 9, borderRadius: 6, background: "var(--surface2)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 6, transition: "width .5s ease" }} />
                  </div>
                </td>
                <td style={{ ...td, textAlign: "right", color: "var(--text-muted)", fontSize: "0.85rem" }}>{r.predictions}</td>
                <td style={{ ...td, textAlign: "right", fontWeight: 800, fontSize: "1.1rem", color: medal ?? "var(--accent)" }}>{r.total_points}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
// ── Gerenciar palpites de todos (dono/admin) ──────────────────────────────────
const gth: React.CSSProperties = { textAlign: "center", padding: "8px 10px", fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", borderBottom: "1px solid var(--border)", fontWeight: 700, whiteSpace: "nowrap" };
const gtd: React.CSSProperties = { textAlign: "center", padding: "6px 10px" };
const gInput: React.CSSProperties = { width: 32, textAlign: "center", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 5, padding: "5px 3px", color: "var(--text)", fontSize: "0.85rem", fontWeight: 700, outline: "none" };

function ManageGrid({ pool }: { pool: Pool }) {
  const [grid, setGrid] = useState<PoolGrid | null>(null);
  const [cells, setCells] = useState<Record<string, { home: string; away: string }>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const applyGrid = useCallback((g: PoolGrid) => {
    const c: Record<string, { home: string; away: string }> = {};
    for (const p of g.predictions) c[`${p.match_id}|${p.user_id}`] = { home: String(p.home_score), away: String(p.away_score) };
    setCells(c);
    setGrid(g);
  }, []);
  useEffect(() => { bolao.poolGrid(pool.id).then(applyGrid).catch(() => {}); }, [pool.id, applyGrid]);

  function setCell(mid: string, uid: number, side: "home" | "away", v: string) {
    const k = `${mid}|${uid}`;
    setCells(prev => ({ ...prev, [k]: { ...(prev[k] ?? { home: "", away: "" }), [side]: v.replace(/[^0-9]/g, "").slice(0, 2) } }));
  }

  async function save() {
    if (!grid) return;
    const items: { user_id: number; match_id: string; home_score: number; away_score: number }[] = [];
    for (const m of grid.matches) for (const u of grid.participants) {
      const c = cells[`${m.match_id}|${u.user_id}`];
      if (!c || c.home === "" || c.away === "") continue;
      items.push({ user_id: u.user_id, match_id: m.match_id, home_score: Number(c.home), away_score: Number(c.away) });
    }
    if (items.length === 0) { setError("Preencha ao menos um palpite."); return; }
    setBusy(true); setError(""); setOkMsg("");
    try { const res = await bolao.registro(pool.id, items); setOkMsg(`Salvo — ${res.scored} já pontuados.`); applyGrid(await bolao.poolGrid(pool.id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setBusy(false); }
  }

  if (!grid) return <div style={{ padding: 32, color: "var(--text-muted)", textAlign: "center" }}>Carregando palpites…</div>;
  if (grid.participants.length === 0) return <div style={{ maxWidth: 600, margin: "0 auto", padding: "32px 16px", color: "var(--text-muted)", textAlign: "center" }}>Nenhum participante ainda. Adicione palpites por aqui (digite e salve) ou pelo fluxo de criação.</div>;

  const ordered = [...grid.matches].sort((a, b) => (a.date_utc ?? "").localeCompare(b.date_utc ?? "") || a.match_number - b.match_number);
  const days: { key: string; label: string; list: PoolMatch[] }[] = [];
  for (const m of ordered) { const k = dayKey(m.date_utc); const g = days.find(d => d.key === k); if (g) g.list.push(m); else days.push({ key: k, label: dayLabel(m.date_utc), list: [m] }); }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "20px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 800 }}>Palpites de todos</h2>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{grid.participants.length} participantes · {grid.matches.length} jogos</span>
        <div style={{ flex: 1 }} />
        {error && <span style={{ color: "#ef4444", fontSize: "0.82rem" }}>{error}</span>}
        {okMsg && <span style={{ color: "#22c55e", fontSize: "0.82rem" }}>{okMsg}</span>}
        <button onClick={save} disabled={busy} style={{ ...btn, padding: "8px 16px", opacity: busy ? 0.7 : 1 }}>{busy ? "Salvando…" : "Salvar alterações"}</button>
      </div>
      <p style={{ fontSize: "0.76rem", color: "var(--text-muted)", margin: "0 0 12px" }}>Edite o palpite de cada participante. Jogos já realizados pontuam na hora ao salvar.</p>
      <div style={{ overflowX: "auto", ...card }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.82rem", minWidth: "100%" }}>
          <thead>
            <tr style={{ background: "var(--surface2)" }}>
              <th style={{ ...gth, textAlign: "left", position: "sticky", left: 0, background: "var(--surface2)", zIndex: 2 }}>Jogo</th>
              <th style={gth}>Resultado</th>
              {grid.participants.map(u => <th key={u.user_id} style={{ ...gth, minWidth: 92 }}>{u.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {days.map(({ key, label, list }) => (
              <Fragment key={key}>
                <tr><td colSpan={grid.participants.length + 2} style={{ padding: "10px 10px 4px", fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--accent)", position: "sticky", left: 0 }}>{label}</td></tr>
                {list.map(m => {
                  const hasResult = m.status === "finalizado" && m.home_score != null;
                  return (
                    <tr key={m.match_id} style={{ borderTop: "1px solid var(--border)" }}>
                      <td style={{ ...gtd, textAlign: "left", whiteSpace: "nowrap", position: "sticky", left: 0, background: "var(--surface)" }}>
                        <span style={{ marginRight: 5 }}>{FLAGS[m.home_team ?? ""] ?? "🏳️"}</span>{m.home_team ?? "?"}<span style={{ color: "var(--text-muted)" }}> × </span>{m.away_team ?? "?"}<span style={{ marginLeft: 5 }}>{FLAGS[m.away_team ?? ""] ?? "🏳️"}</span>
                      </td>
                      <td style={{ ...gtd, whiteSpace: "nowrap" }}>{hasResult ? <span style={{ color: "#22c55e", fontWeight: 700 }}>{m.home_score}–{m.away_score}</span> : <span style={{ fontSize: "0.64rem", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>A JOGAR</span>}</td>
                      {grid.participants.map(u => {
                        const c = cells[`${m.match_id}|${u.user_id}`] ?? { home: "", away: "" };
                        return (
                          <td key={u.user_id} style={gtd}>
                            <div style={{ display: "flex", gap: 3, justifyContent: "center", alignItems: "center" }}>
                              <input value={c.home} onChange={e => setCell(m.match_id, u.user_id, "home", e.target.value)} style={gInput} inputMode="numeric" />
                              <span style={{ color: "var(--text-muted)" }}>×</span>
                              <input value={c.away} onChange={e => setCell(m.match_id, u.user_id, "away", e.target.value)} style={gInput} inputMode="numeric" />
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RankingTab({ pool }: { pool: Pool }) {
  const [data, setData] = useState<PoolRanking | null>(null);
  const [sub, setSub] = useState<"geral" | number>("geral");
  useEffect(() => { bolao.ranking(pool.id).then(setData).catch(() => setData({ ranking: [], children: [] })); }, [pool.id]);
  if (!data) return <div style={{ padding: 32, color: "var(--text-muted)" }}>Carregando ranking…</div>;
  const hasChildren = data.children.length > 0;
  return (
    <div style={{ padding: "20px" }}>
      {hasChildren && (
        <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
          <Chip on={sub === "geral"} onClick={() => setSub("geral")}>Geral</Chip>
          {data.children.map(c => <Chip key={c.child_id} on={sub === c.child_id} onClick={() => setSub(c.child_id)}>{c.child_name}</Chip>)}
        </div>
      )}
      {sub === "geral"
        ? <RankTable rows={data.ranking} />
        : <RankTable rows={data.children.find(c => c.child_id === sub)?.ranking ?? []} />}
    </div>
  );
}

// ── Editar bolão (nome + regra + escopo) ──────────────────────────────────────
function EditPoolModal({ pool, rules: initialRules, onClose, onSaved }: {
  pool: Pool; rules: ScoringRule[]; onClose: () => void; onSaved: () => Promise<void>;
}) {
  // Busca as regras frescas ao abrir (não depende do estado da página, que pode
  // estar defasado) — garante que a regra do próprio bolão sempre apareça.
  const [rules, setRules] = useState<ScoringRule[]>(initialRules);
  useEffect(() => { bolao.rules().then(setRules).catch(() => {}); }, []);
  const [name, setName] = useState(pool.name);
  const [ruleId, setRuleId] = useState<number>(pool.rule_id ?? initialRules[0]?.id ?? 0);
  const [scopeChoice, setScopeChoice] = useState<"all" | "stage" | "keep">(
    pool.scope?.type === "stage" ? "stage" : pool.scope?.type === "matches" ? "keep" : "all"
  );
  const [stages, setStages] = useState<string[]>(pool.scope?.stages ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    if (!name.trim()) { setError("O nome não pode ficar vazio."); return; }
    if (scopeChoice === "stage" && stages.length === 0) { setError("Escolha ao menos uma fase."); return; }
    setBusy(true); setError("");
    const body: { name?: string; rule_id?: number; scope?: PoolScope } = { name: name.trim(), rule_id: ruleId };
    if (scopeChoice === "all") body.scope = { type: "all" };
    else if (scopeChoice === "stage") body.scope = { type: "stage", stages };
    // scopeChoice === "keep" → não envia scope (preserva os jogos escolhidos)
    try { await bolao.updatePool(pool.id, body); await onSaved(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Não foi possível salvar (só o dono pode)."); }
    finally { setBusy(false); }
  }

  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title="Editar bolão" size="md">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field label="Nome"><input value={name} onChange={e => setName(e.target.value)} style={inputStyle} /></Field>
        <Field label="Regra de pontuação">
          <select value={ruleId} onChange={e => setRuleId(Number(e.target.value))} style={{ ...inputStyle, cursor: "pointer" }}>
            {rules.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </Field>
        {!pool.is_group && (
          <Field label="Jogos">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {pool.scope?.type === "matches" && <Chip on={scopeChoice === "keep"} onClick={() => setScopeChoice("keep")}>Manter jogos escolhidos ({pool.scope.match_ids?.length ?? 0})</Chip>}
              <Chip on={scopeChoice === "all"} onClick={() => setScopeChoice("all")}>Todos os jogos</Chip>
              <Chip on={scopeChoice === "stage"} onClick={() => setScopeChoice("stage")}>Por fase</Chip>
            </div>
            {scopeChoice === "stage" && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                {STAGE_ORDER.map(s => <Chip key={s} on={stages.includes(s)} onClick={() => setStages(p => p.includes(s) ? p.filter(x => x !== s) : [...p, s])}>{stageLabel(s)}</Chip>)}
              </div>
            )}
            <p style={{ fontSize: "0.74rem", color: "var(--text-muted)", margin: "6px 0 0" }}>Mudar regra ou escopo recalcula os pontos dos palpites.</p>
          </Field>
        )}
        {error && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} disabled={busy} style={cancelBtn}>Cancelar</button>
          <button onClick={save} disabled={busy} style={{ ...primaryBtn, opacity: busy ? 0.7 : 1 }}>{busy ? "Salvando…" : "Salvar"}</button>
        </div>
      </div>
    </Modal>
  );
}

// ── Sala (liga): grupo com participantes + regra padrão ──────────────────────
function CreateSalaModal({ rules, onClose, onCreated }: {
  rules: ScoringRule[]; onClose: () => void; onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [allUsers, setAllUsers] = useState<AppUser[]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const [ruleId, setRuleId] = useState<number>(rules[0]?.id ?? 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { users.list().then(setAllUsers).catch(() => {}); }, []);
  const toggle = (id: number) => setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  async function create() {
    if (!name.trim()) { setError("Dê um nome à sala."); return; }
    if (!ruleId) { setError("Escolha a regra padrão."); return; }
    setBusy(true); setError("");
    try { await bolao.createSala({ name: name.trim(), member_ids: picked, rule_id: ruleId }); await onCreated(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar sala."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title="Nova sala" size="md">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
          Uma sala agrupa vários bolões com os mesmos participantes e a mesma regra. Cada bolão criado dentro já vem pronto — você só escolhe os jogos.
        </p>
        <Field label="Nome da sala"><input value={name} onChange={e => setName(e.target.value)} placeholder="Ex.: Fifa Maroto" style={inputStyle} /></Field>
        <Field label="Regra padrão">
          <select value={ruleId} onChange={e => setRuleId(Number(e.target.value))} style={{ ...inputStyle, cursor: "pointer" }}>
            {rules.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </Field>
        <Field label={`Participantes (${picked.length})`}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", maxHeight: 200, overflow: "auto" }}>
            {allUsers.map(u => <Chip key={u.id} on={picked.includes(u.id)} onClick={() => toggle(u.id)}>{u.name || u.username}</Chip>)}
            {allUsers.length === 0 && <span style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Nenhum usuário cadastrado.</span>}
          </div>
        </Field>
        {error && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} disabled={busy} style={cancelBtn}>Cancelar</button>
          <button onClick={create} disabled={busy} style={{ ...primaryBtn, opacity: busy ? 0.7 : 1 }}>{busy ? "Criando…" : "Criar sala"}</button>
        </div>
      </div>
    </Modal>
  );
}

function CreateSubBolaoModal({ sala, onClose, onCreated }: {
  sala: Pool; onClose: () => void; onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [scopeType, setScopeType] = useState<"all" | "stage" | "matches">("all");
  const [stages, setStages] = useState<string[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [stageFilter, setStageFilter] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (scopeType === "matches" && matches.length === 0) analytics.matches().then(setMatches).catch(() => {});
  }, [scopeType, matches.length]);

  const toggleMatch = (id: string) => setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  // Fase de grupos = jogos 1–72, em 3 rodadas (≤24, ≤48, resto). Mata-mata = >72.
  const groupRound = (m: Match) => (m.match_number <= 24 ? 1 : m.match_number <= 48 ? 2 : 3);
  const matchStageLabel = (m: Match) => (m.match_number <= 72 ? `Grupos · Rod. ${groupRound(m)}` : stageLabel(m.stage));
  const stageOptions: { value: string; label: string }[] = [{ value: "", label: "Todas as etapas" }];
  if (matches.some(m => m.match_number <= 72)) {
    stageOptions.push(
      { value: "grupos-1", label: "Grupos · Rodada 1" },
      { value: "grupos-2", label: "Grupos · Rodada 2" },
      { value: "grupos-3", label: "Grupos · Rodada 3" },
    );
  }
  for (const s of Array.from(new Set(matches.filter(m => m.match_number > 72 && m.stage).map(m => m.stage as string)))) {
    stageOptions.push({ value: s, label: stageLabel(s) });
  }
  const visibleMatches = matches.filter(m => {
    if (!stageFilter) return true;
    if (stageFilter.startsWith("grupos-")) return m.match_number <= 72 && groupRound(m) === Number(stageFilter.slice(7));
    return m.stage === stageFilter;
  });
  const allVisiblePicked = visibleMatches.length > 0 && visibleMatches.every(m => picked.includes(m.match_id));
  const toggleAllVisible = () => {
    const ids = visibleMatches.map(m => m.match_id);
    setPicked(p => allVisiblePicked ? p.filter(id => !ids.includes(id)) : Array.from(new Set([...p, ...ids])));
  };

  async function create() {
    if (!name.trim()) { setError("Dê um nome ao bolão."); return; }
    if (scopeType === "stage" && stages.length === 0) { setError("Escolha ao menos uma fase."); return; }
    if (scopeType === "matches" && picked.length === 0) { setError("Escolha ao menos um jogo."); return; }
    setBusy(true); setError("");
    const scope: PoolScope =
      scopeType === "all" ? { type: "all" }
      : scopeType === "stage" ? { type: "stage", stages }
      : { type: "matches", match_ids: picked };
    try {
      // sem rule_id → herda a regra da sala; participantes herdados no backend.
      await bolao.createPool({ name: name.trim(), parent_id: sala.id, scope });
      await onCreated(); onClose();
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar bolão."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title={`Novo bolão em ${sala.name}`} size="md">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field label="Nome do bolão"><input value={name} onChange={e => setName(e.target.value)} placeholder="Ex.: Oitavas de final" style={inputStyle} /></Field>
        <Field label="Jogos">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Chip on={scopeType === "all"} onClick={() => setScopeType("all")}>Todos os jogos</Chip>
            <Chip on={scopeType === "stage"} onClick={() => setScopeType("stage")}>Por fase</Chip>
            <Chip on={scopeType === "matches"} onClick={() => setScopeType("matches")}>Jogos específicos</Chip>
          </div>
          {scopeType === "stage" && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {STAGE_ORDER.map(s => <Chip key={s} on={stages.includes(s)} onClick={() => setStages(p => p.includes(s) ? p.filter(x => x !== s) : [...p, s])}>{stageLabel(s)}</Chip>)}
            </div>
          )}
          {scopeType === "matches" && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                <select value={stageFilter} onChange={e => setStageFilter(e.target.value)} style={{ ...inputStyle, width: "auto", cursor: "pointer", padding: "6px 10px" }}>
                  {stageOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                {visibleMatches.length > 0 && (
                  <button type="button" onClick={toggleAllVisible}
                    style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 11px", fontSize: "0.76rem", color: "var(--text)", cursor: "pointer", whiteSpace: "nowrap" }}>
                    {allVisiblePicked ? "Limpar etapa" : "Marcar todos"}
                  </button>
                )}
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{picked.length} selecionado(s)</span>
              </div>
              <div style={{ maxHeight: 240, overflow: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
                {visibleMatches.map(m => {
                  const on = picked.includes(m.match_id);
                  return (
                    <button key={m.match_id} type="button" onClick={() => toggleMatch(m.match_id)} style={{
                      width: "100%", textAlign: "left", display: "flex", alignItems: "center", gap: 10,
                      padding: "8px 12px", background: on ? "rgba(88,166,255,0.1)" : "none", border: "none",
                      borderBottom: "1px solid var(--border)", color: "var(--text)", cursor: "pointer", fontSize: "0.82rem",
                    }}>
                      <span style={{ width: 15, height: 15, borderRadius: 4, border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`, background: on ? "var(--accent)" : "transparent", flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#0d1117", fontWeight: 800 }}>{on ? "✓" : ""}</span>
                      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.home_team ?? "?"} × {m.away_team ?? "?"}</span>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", flexShrink: 0 }}>{matchStageLabel(m)}</span>
                    </button>
                  );
                })}
                {visibleMatches.length === 0 && <div style={{ padding: 16, color: "var(--text-muted)", fontSize: "0.82rem", textAlign: "center" }}>Carregando jogos…</div>}
              </div>
            </div>
          )}
          <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", margin: "6px 0 0" }}>Participantes e regra herdados da sala{sala.rule_name ? ` (regra: ${sala.rule_name})` : ""}.</p>
        </Field>
        {error && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} disabled={busy} style={cancelBtn}>Cancelar</button>
          <button onClick={create} disabled={busy} style={{ ...primaryBtn, opacity: busy ? 0.7 : 1 }}>{busy ? "Criando…" : "Criar bolão"}</button>
        </div>
      </div>
    </Modal>
  );
}

function SalaView({ sala, canManage, onOpenChild, onReload }: {
  sala: Pool; canManage: boolean; onOpenChild: (id: number) => void; onReload: () => Promise<void>;
}) {
  const [creating, setCreating] = useState(false);
  const children = sala.children ?? [];
  return (
    <div style={{ padding: 20 }}>
      <style>{`@keyframes poolIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 800, color: "var(--text)" }}>Bolões da sala <span style={{ color: "var(--text-muted)", fontWeight: 600 }}>({children.length})</span></h3>
        {canManage && <button onClick={() => setCreating(true)} style={primaryBtn}>+ Novo bolão</button>}
      </div>
      {children.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: "0.88rem" }}>Nenhum bolão ainda. Crie o primeiro — ele já vem com os participantes e a regra da sala.</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 14 }}>
          {children.map((c, i) => <PoolListCard key={c.id} pool={c} index={i} onOpen={() => onOpenChild(c.id)} />)}
        </div>
      )}
      {creating && <CreateSubBolaoModal sala={sala} onClose={() => setCreating(false)} onCreated={async () => { setCreating(false); await onReload(); }} />}
    </div>
  );
}

function PoolParticipants({ pool, parent, canManage, onReload }: {
  pool: Pool; parent?: Pool | null; canManage: boolean; onReload: () => Promise<void>;
}) {
  const [members, setMembers] = useState<{ user_id: number; name: string }[]>([]);
  const [candidates, setCandidates] = useState<{ id: number; name: string }[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const isBolao = !!parent;
  const loadMembers = useCallback(async () => {
    try { const d = await bolao.pool(pool.id); setMembers(d.members ?? []); } catch { /* ignore */ }
  }, [pool.id]);
  useEffect(() => { loadMembers(); }, [loadMembers]);
  useEffect(() => {
    if (!addOpen) return;
    if (parent) {
      // bolão: candidatos = participantes da sala (que ainda não estão no bolão).
      bolao.pool(parent.id).then(p => setCandidates((p.members ?? []).map(m => ({ id: m.user_id, name: m.name })))).catch(() => {});
    } else {
      // sala: candidatos = todos os usuários.
      users.list().then(us => setCandidates(us.map(u => ({ id: u.id, name: u.name || u.username })))).catch(() => {});
    }
  }, [addOpen, parent]);
  const memberIds = new Set(members.map(m => m.user_id));
  async function add(uid: number) { await bolao.addMember(pool.id, uid); await loadMembers(); await onReload(); }
  async function remove(uid: number) { await bolao.removeMember(pool.id, uid); await loadMembers(); await onReload(); }
  return (
    <div style={{ padding: "20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 800, color: "var(--text)" }}>Participantes <span style={{ color: "var(--text-muted)", fontWeight: 600 }}>({members.length})</span></h3>
        {canManage && <button onClick={() => setAddOpen(o => !o)} style={cancelBtn}>{addOpen ? "Fechar" : "+ Adicionar"}</button>}
      </div>
      <p style={{ margin: "0 0 14px", fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
        {isBolao
          ? "Quem participa deste bolão. Por padrão herda os participantes da sala — remova quem não vai participar dele."
          : "Participantes da sala — valem para todos os bolões dela. Adicionar ou remover propaga aos bolões."}
      </p>
      {members.length === 0 ? (
        <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Nenhum participante ainda.</span>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 10 }}>
          {members.map((m, i) => (
            <div key={m.user_id} style={{ ...card, display: "flex", alignItems: "center", gap: 11, padding: "10px 12px" }}>
              <span style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#2ea043,#3fb950)", color: "#04130a", fontWeight: 800, fontSize: "0.85rem", display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{(m.name || "?").charAt(0).toUpperCase()}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontWeight: 600 }}>#{i + 1}</div>
                <div style={{ fontSize: "0.92rem", color: "var(--text)", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.name}</div>
              </div>
              {canManage && (
                <button onClick={() => remove(m.user_id)} title="Remover participante"
                  style={{ flexShrink: 0, width: 26, height: 26, borderRadius: 6, background: "none", border: "1px solid var(--border)", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.95rem", lineHeight: 1, display: "inline-flex", alignItems: "center", justifyContent: "center" }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#f85149"; e.currentTarget.style.color = "#f85149"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
                >✕</button>
              )}
            </div>
          ))}
        </div>
      )}
      {addOpen && canManage && (
        <div style={{ ...card, marginTop: 12, padding: 12, display: "flex", gap: 6, flexWrap: "wrap" }}>
          {candidates.filter(c => !memberIds.has(c.id)).map(c => <Chip key={c.id} on={false} onClick={() => add(c.id)}>+ {c.name}</Chip>)}
          {candidates.length > 0 && candidates.filter(c => !memberIds.has(c.id)).length === 0 && (
            <span style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{isBolao ? "Todos os participantes da sala já estão neste bolão." : "Todos já estão na sala."}</span>
          )}
        </div>
      )}
    </div>
  );
}

function MovePoolModal({ pool, salas, onClose, onMoved }: {
  pool: Pool; salas: Pool[]; onClose: () => void; onMoved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function move(parentId: number | null) {
    setBusy(true); setError("");
    try { await bolao.movePool(pool.id, parentId); await onMoved(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao mover."); }
    finally { setBusy(false); }
  }
  const options = salas.filter(s => s.id !== pool.id && s.id !== pool.parent_id);
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title={`Mover “${pool.name}”`} size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
          Escolha a sala de destino. Palpites e pontos são preservados.
        </p>
        {options.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>Nenhuma sala disponível — crie uma sala primeiro.</p>}
        {options.map(s => (
          <button key={s.id} disabled={busy} onClick={() => move(s.id)}
            style={{ ...cancelBtn, textAlign: "left", display: "flex", alignItems: "center", gap: 8, padding: "10px 14px" }}>
            🗂️ {s.name}
          </button>
        ))}
        {pool.parent_id != null && (
          <button disabled={busy} onClick={() => move(null)}
            style={{ ...cancelBtn, textAlign: "left", color: "var(--text-muted)", padding: "10px 14px" }}>
            ↥ Tirar da sala (deixar avulso)
          </button>
        )}
        {error && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
      </div>
    </Modal>
  );
}

// ── Página ───────────────────────────────────────────────────────────────────
export default function BolaoPage() {
  const { token, user } = useAuth();
  const [pools, setPools] = useState<Pool[] | null>(null);
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [criteria, setCriteria] = useState<ScoringCriterion[]>([]);
  const [modes, setModes] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tab, setTab] = useState<"palpites" | "gerenciar" | "ranking" | "sala" | "participantes">("palpites");
  const [showCreateSala, setShowCreateSala] = useState(false);
  const [moving, setMoving] = useState<Pool | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [dialogInput, setDialogInput] = useState("");
  const [dialogBusy, setDialogBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");
  const [editing, setEditing] = useState<Pool | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [poolSearch, setPoolSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "a_iniciar" | "em_andamento" | "finalizado">("all");
  const [celebrate, setCelebrate] = useState(false);

  const reload = useCallback(async () => {
    const ps = await bolao.pools();
    setPools(ps);
    // Mantém o bolão aberto só se ainda existir; senão volta pra lista (null).
    setActiveId(prev => (prev && findPool(ps, prev) ? prev : null));
  }, []);

  useEffect(() => {
    if (!token) return;
    // Não seleciona nenhum bolão automaticamente — começa na LISTA.
    Promise.all([bolao.pools(), bolao.rules(), scoring.criteria()])
      .then(([ps, rs, cr]) => {
        setPools(ps); setRules(rs); setCriteria(cr.criteria); setModes(cr.modes);
      })
      .finally(() => setLoading(false));
  }, [token]);

  // Comemoração: ao abrir um bolão finalizado em que o usuário é vencedor.
  useEffect(() => {
    const a = activeId && pools ? findPool(pools, activeId) : null;
    const won = !!a && !a.is_group && a.status === "finalizado" && !!user?.name && (a.winners ?? []).includes(user.name);
    setCelebrate(won);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  if (!token) return null;
  if (loading || pools === null) return <div style={{ padding: 48, color: "var(--text-muted)", textAlign: "center" }}>Carregando…</div>;

  if (pools.length === 0) {
    return (
      <>
        <div style={{ maxWidth: 460, margin: "60px auto", padding: "0 16px", textAlign: "center" }}>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 800, marginBottom: 8 }}>Nenhuma sala ainda</h1>
          <p style={{ color: "var(--text-muted)", marginBottom: 20, fontSize: "0.9rem" }}>
            Crie uma sala (liga) para reunir os participantes e a regra — depois é só criar os bolões dentro dela.
          </p>
          <button onClick={() => setShowCreateSala(true)} style={{ ...btn, padding: "10px 22px" }}>+ Criar sala</button>
        </div>
        {showCreateSala && <CreateSalaModal rules={rules} onClose={() => setShowCreateSala(false)} onCreated={reload} />}
      </>
    );
  }

  const active = activeId ? findPool(pools, activeId) : null;
  // Topo da lista = raízes (salas + bolões avulsos). Os sub-bolões ficam dentro da sala.
  const flat = pools.map(p => ({ pool: p, depth: 0 }));
  const poolVisible = (entry: { pool: Pool }) =>
    (!poolSearch.trim() || entry.pool.name.toLowerCase().includes(poolSearch.toLowerCase())) &&
    (statusFilter === "all" || (entry.pool.status ?? "a_iniciar") === statusFilter);
  const isAdmin = !!user?.is_admin;
  const canManage = isAdmin || (!!active && active.owner_id === user?.id);
  const TAB_LABEL: Record<"palpites" | "gerenciar" | "ranking" | "sala" | "participantes", string> = { palpites: "Palpites", gerenciar: "Palpites de todos", ranking: "Ranking", sala: "Bolões da sala", participantes: "Participantes" };
  const poolTabs: ("palpites" | "gerenciar" | "ranking" | "sala" | "participantes")[] = active?.is_group
    ? ["sala", "participantes", "ranking"]
    : isAdmin ? ["gerenciar", "participantes", "ranking"]
    : canManage ? ["palpites", "gerenciar", "participantes", "ranking"]
    : ["palpites", "participantes", "ranking"];
  const headerBarStyle: React.CSSProperties = { borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex", alignItems: "center", padding: "0 20px", gap: 10, flexWrap: "wrap" };
  const topBtn: React.CSSProperties = { background: "none", border: "1px solid var(--border)", borderRadius: 6, padding: "5px 10px", fontSize: "0.78rem", color: "var(--text-muted)", cursor: "pointer" };
  const topActions = (
    <>
      <button onClick={join} style={topBtn}>Entrar com código</button>
      <button onClick={() => setRulesOpen(true)} style={topBtn}>Regras</button>
      <button onClick={() => setShowCreateSala(true)} style={{ background: "var(--accent)", color: "#0d1117", border: "none", borderRadius: 6, padding: "5px 12px", fontSize: "0.78rem", fontWeight: 700, cursor: "pointer" }}>+ Nova sala</button>
    </>
  );

  function openDialog(d: DialogState, initial = "") {
    setDialogInput(initial);
    setDialogError("");
    setDialog(d);
  }

  async function submitDialog() {
    if (!dialog) return;
    setDialogBusy(true);
    setDialogError("");
    try {
      await dialog.onConfirm(dialogInput.trim());
      setDialog(null);
    } catch (e) {
      setDialogError(e instanceof Error ? e.message : "Algo deu errado.");
    } finally {
      setDialogBusy(false);
    }
  }

  function join() {
    openDialog({
      title: "Entrar com código",
      input: { label: "Código do bolão", placeholder: "número, ex.: 12" },
      confirmText: "Entrar",
      onConfirm: async (v) => {
        const id = Number(v);
        if (!v || Number.isNaN(id)) throw new Error("Informe um número válido.");
        try { await bolao.join(id); }
        catch { throw new Error("Bolão não encontrado."); }
        await reload();
        setActiveId(id);
      },
    });
  }

  function del() {
    if (!active) return;
    const pool = active;
    openDialog({
      title: pool.is_group ? "Excluir grupo" : "Excluir bolão",
      message: pool.is_group
        ? `Excluir a sala “${pool.name}” e todos os bolões dela? Os palpites serão apagados — não dá pra desfazer.`
        : `Excluir o bolão “${pool.name}”? Os palpites serão apagados — não dá pra desfazer.`,
      confirmText: "Excluir",
      danger: true,
      onConfirm: async () => {
        await bolao.deletePool(pool.id);
        await reload();
        setTab("palpites");
      },
    });
  }

  return (
    <div>
      {active == null ? (
        <>
          <div style={headerBarStyle}>
            <span style={{ fontWeight: 700, fontSize: "0.95rem", margin: "12px 0" }}>Meus bolões</span>
            <input value={poolSearch} onChange={e => setPoolSearch(e.target.value)} placeholder="Buscar bolão…"
              style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "5px 10px", fontSize: "0.78rem", background: "none", color: "var(--text)", outline: "none", width: 180 }} />
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {([["all", "Todos"], ["a_iniciar", "A iniciar"], ["em_andamento", "Em andamento"], ["finalizado", "Finalizado"]] as const).map(([val, label]) => {
                const n = val === "all" ? flat.length : flat.filter(e => (e.pool.status ?? "a_iniciar") === val).length;
                return (
                  <Chip key={val} on={statusFilter === val} onClick={() => setStatusFilter(val)}>
                    {label} <span style={{ opacity: 0.7 }}>({n})</span>
                  </Chip>
                );
              })}
            </div>
            <div style={{ flex: 1 }} />
            {topActions}
          </div>
          <div style={{ padding: "24px 20px" }}>
            <style>{`@keyframes poolIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }`}</style>
            {(() => {
              const vis = flat.filter(poolVisible);
              if (vis.length === 0) return <div style={{ padding: 28, color: "var(--text-muted)", textAlign: "center" }}>Nenhum bolão encontrado.</div>;
              return (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 16 }}>
                  {vis.map(({ pool }, i) => (
                    <PoolListCard key={pool.id} pool={pool} index={i}
                      onOpen={() => { setActiveId(pool.id); setTab(pool.is_group ? "sala" : isAdmin ? "gerenciar" : "palpites"); }} />
                  ))}
                </div>
              );
            })()}
          </div>
        </>
      ) : (
        <>
          {celebrate && active && <WinnerCelebration poolName={active.name} onDone={() => setCelebrate(false)} />}
          <div style={headerBarStyle}>
            <button onClick={() => { if (active.parent_id != null) { setActiveId(active.parent_id); setTab("sala"); } else setActiveId(null); }} style={{ ...topBtn, margin: "8px 0" }}>{active.parent_id != null ? "← Sala" : "← Bolões"}</button>
            <span style={{ fontWeight: 700, fontSize: "0.9rem", marginLeft: 2 }}>{active.name}</span>
            {poolTabs.map(t => (
              <button key={t} onClick={() => setTab(t)} style={{ background: "none", border: "none", borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent", padding: "12px 14px", fontSize: "0.85rem", fontWeight: tab === t ? 600 : 400, color: tab === t ? "var(--accent)" : "var(--text-muted)", cursor: "pointer", marginBottom: -1, whiteSpace: "nowrap" }}>{TAB_LABEL[t]}</button>
            ))}
            <div style={{ flex: 1 }} />
            {!active.is_group && canManage && <button onClick={() => setMoving(active)} title="Mover para uma sala" style={topBtn}>Mover</button>}
            {canManage && <button onClick={() => setEditing(active)} title="Editar este bolão" style={topBtn}>Editar</button>}
            {canManage && <button onClick={del} title="Excluir este bolão" style={{ ...topBtn, color: "#ef4444" }}>Excluir</button>}
          </div>

          {active.scope && !active.is_group && <div style={{ padding: "8px 20px", fontSize: "0.78rem", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
            Escopo: {scopeLabel(active.scope)}{active.rule ? ` · Regra: ${active.rule.name}` : ""}
          </div>}

          {active.is_group && tab === "sala"
            ? <SalaView sala={active} canManage={canManage} onReload={reload}
                onOpenChild={id => { setActiveId(id); setTab(isAdmin ? "gerenciar" : "palpites"); }} />
            : tab === "participantes"
              ? <PoolParticipants pool={active} parent={active.parent_id != null ? findPool(pools, active.parent_id) : null} canManage={canManage} onReload={reload} />
              : tab === "gerenciar" && canManage && !active.is_group
                ? <ManageGrid pool={active} />
                : !isAdmin && tab === "palpites"
                  ? <PredictionsTab pool={active} onPickChild={id => { setActiveId(id); }} />
                  : <RankingTab pool={active} />}
        </>
      )}

      <Modal open={!!dialog} onClose={() => { if (!dialogBusy) setDialog(null); }} title={dialog?.title} size="sm">
        {dialog && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {dialog.message && <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0, lineHeight: 1.55 }}>{dialog.message}</p>}
            {dialog.input && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{dialog.input.label}</label>
                <input autoFocus value={dialogInput} placeholder={dialog.input.placeholder}
                  onChange={e => setDialogInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") submitDialog(); }}
                  style={inputStyle} />
              </div>
            )}
            {dialogError && <p style={{ color: "#ef4444", fontSize: "0.82rem", margin: 0 }}>{dialogError}</p>}
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 2 }}>
              <button onClick={() => setDialog(null)} disabled={dialogBusy}
                style={{ background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 16px", fontSize: "0.85rem", cursor: "pointer" }}>Cancelar</button>
              <button onClick={submitDialog} disabled={dialogBusy}
                style={{ border: "none", borderRadius: 6, padding: "8px 18px", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", background: dialog.danger ? "#ef4444" : "var(--accent)", color: dialog.danger ? "#fff" : "#0d1117", opacity: dialogBusy ? 0.7 : 1 }}>
                {dialogBusy ? "Aguarde…" : dialog.confirmText}
              </button>
            </div>
          </div>
        )}
      </Modal>

      {showCreateSala && <CreateSalaModal rules={rules} onClose={() => setShowCreateSala(false)} onCreated={reload} />}
      {moving && <MovePoolModal pool={moving} salas={pools.filter(p => p.is_group)} onClose={() => setMoving(null)} onMoved={reload} />}
      {editing && <EditPoolModal pool={editing} rules={rules} onClose={() => setEditing(null)} onSaved={reload} />}
      {rulesOpen && <RulesModal criteria={criteria} modes={modes} isAdmin={isAdmin} onClose={() => setRulesOpen(false)} onChanged={() => { bolao.rules().then(setRules); }} />}
    </div>
  );
}
