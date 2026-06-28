"use client";

import { useState } from "react";
import useSWR from "swr";
import { admin, type AdminJob, type AutoCollectStatus } from "@/lib/api";
import Pager from "@/components/ui/Pager";
import UsersAdmin from "./UsersAdmin";
import PoolsAdmin from "./PoolsAdmin";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<AdminJob["status"], { color: string; label: string }> = {
  pending: { color: "#eab308", label: "Na fila" },
  running: { color: "#58a6ff", label: "Rodando" },
  success: { color: "#22c55e", label: "Concluído" },
  error: { color: "#ef4444", label: "Erro" },
};
const KIND_LABEL: Record<AdminJob["kind"], string> = { coleta: "Coleta", recalc: "Recálculo", "preditiva-learn": "Re-treino preditiva" };

function fmt(ts: string | null): string {
  if (!ts) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      timeZone: "America/Sao_Paulo",
    }).format(new Date(ts));
  } catch { return ts; }
}

// ── Job row (expansível) ────────────────────────────────────────────────────────

function JobRow({ job, index }: { job: AdminJob; index: number }) {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(false);
  const s = STATUS_STYLE[job.status];
  const live = job.status === "running" || job.status === "pending";
  return (
    <>
      <tr onClick={() => setOpen(o => !o)} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
        style={{ borderBottom: "1px solid var(--border)", cursor: job.log ? "pointer" : "default", background: hover ? "var(--surface2)" : "transparent", transition: "background .15s", animation: "rowIn .28s ease backwards", animationDelay: `${Math.min(index, 10) * 25}ms` }}>
        <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.82rem" }}>#{job.id}</td>
        <td style={{ padding: "10px 12px", fontWeight: 600 }}>{KIND_LABEL[job.kind] ?? job.kind}</td>
        <td style={{ padding: "10px 12px" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 10px", borderRadius: 20, fontSize: "0.74rem", fontWeight: 700, color: s.color, background: `${s.color}22`, border: `1px solid ${s.color}44` }}>
            {live && <span style={{ width: 7, height: 7, borderRadius: "50%", background: s.color, animation: "pulse 1.2s ease-in-out infinite" }} />}
            {s.label}
          </span>
        </td>
        <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.8rem" }}>{fmt(job.started_at)}</td>
        <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.8rem" }}>{fmt(job.finished_at)}</td>
        <td style={{ padding: "10px 12px", color: hover ? "var(--accent)" : "var(--text-muted)", fontSize: "0.8rem", textAlign: "right" }}>{job.log ? (open ? "▲ log" : "▼ log") : "—"}</td>
      </tr>
      {open && job.log && (
        <tr style={{ borderBottom: "1px solid var(--border)" }}>
          <td colSpan={6} style={{ padding: 0 }}>
            <pre style={{ margin: 0, padding: "14px 18px", background: "#0d1117", color: "var(--text-muted)", fontSize: "0.78rem", lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 320, overflowY: "auto" }}>{job.log}</pre>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Aba Coleta ────────────────────────────────────────────────────────────────

function ActionCard({ icon, title, desc, onClick, busy, disabled, primary }: {
  icon: string; title: string; desc: string; onClick: () => void; busy: boolean; disabled: boolean; primary?: boolean;
}) {
  const [hover, setHover] = useState(false);
  const accent = "#58a6ff";
  return (
    <button onClick={onClick} disabled={disabled} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        flex: "1 1 280px", textAlign: "left", background: "var(--surface)", border: `1px solid ${hover && !disabled ? accent : "var(--border)"}`,
        borderRadius: 12, padding: "16px 18px", cursor: disabled ? "default" : "pointer", opacity: disabled ? 0.55 : 1,
        boxShadow: hover && !disabled ? `0 8px 22px -10px ${accent}66` : "none",
        transform: hover && !disabled ? "translateY(-2px)" : "none", transition: "transform .16s, box-shadow .16s, border-color .16s",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <span style={{ width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", background: primary ? accent : "var(--surface2)", color: primary ? "#0d1117" : "var(--text)", fontWeight: 800 }}>{icon}</span>
        <span style={{ fontWeight: 800, fontSize: "1rem" }}>{busy ? "Disparando…" : title}</span>
      </div>
      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{desc}</div>
    </button>
  );
}

// ── Status da coleta automática (scheduler dirigido pelo calendário) ──────────

function AutoCollectCard() {
  const { data: st } = useSWR<AutoCollectStatus>("admin/auto-collect", () => admin.autoCollect(), {
    refreshInterval: 30000,
  });
  if (!st) return null;

  const on = st.enabled;
  const waiting = !!st.waiting_until && st.pending.length > 0;
  const accent = on ? "#22c55e" : "#8b949e";
  const label = on
    ? `Ligada · checa a cada ${st.interval_minutes ?? "?"} min (espera até ${st.grace_minutes ?? "?"} min p/ stats)`
    : "Desligada (AUTO_COLLECT_MINUTES=0)";

  const facts: [string, string][] = [
    ["Ligado desde", fmt(st.started_at)],
    ["Última checagem do calendário", fmt(st.last_check_at)],
    ["Jogos finalizados vistos", st.last_finished_count != null ? String(st.last_finished_count) : "—"],
    ["Última coleta automática", st.last_collect_at ? `${fmt(st.last_collect_at)}${st.last_collect_ok === false ? " · falhou" : ""}` : "—"],
  ];

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "14px 18px", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: on ? 12 : 0, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 800, fontSize: "0.95rem" }}>Coleta automática</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "2px 10px", borderRadius: 20, fontSize: "0.74rem", fontWeight: 700, color: accent, background: `${accent}22`, border: `1px solid ${accent}44` }}>
          {on && <span style={{ width: 7, height: 7, borderRadius: "50%", background: accent, animation: "pulse 1.6s ease-in-out infinite" }} />}
          {label}
        </span>
      </div>

      {on && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
          {facts.map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{k}</div>
              <div style={{ fontSize: "0.88rem", fontWeight: 600, marginTop: 2 }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {waiting && (
        <div style={{ marginTop: 12, padding: "9px 12px", borderRadius: 8, background: "rgba(234,179,8,0.1)", border: "1px solid rgba(234,179,8,0.35)", fontSize: "0.82rem", color: "#eab308", fontWeight: 600 }}>
          Detectou {st.pending.length} jogo(s) finalizado(s) — sondando as stats; coleta assim que publicarem.
        </div>
      )}
      {!on && (
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 8, marginBottom: 0 }}>
          Sem gatilho automático. Defina <code>AUTO_COLLECT_MINUTES</code> no <code>infra/.env</code> da VM (ex.: 15) e suba a API de novo. Enquanto isso, use “Coletar dados”.
        </p>
      )}
    </div>
  );
}

function CollectTab() {
  const [busy, setBusy] = useState<"collect" | "recalc" | "learn" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const PER = 8;
  const { data: jobs, mutate, isLoading } = useSWR<AdminJob[]>("admin/jobs", () => admin.jobs(), {
    refreshInterval: (latest) => latest?.some(j => j.status === "running" || j.status === "pending") ? 2500 : 0,
  });
  const running = jobs?.some(j => j.status === "running" || j.status === "pending") ?? false;

  async function trigger(which: "collect" | "recalc" | "learn") {
    setBusy(which); setError(null);
    try {
      await (which === "collect" ? admin.collect() : which === "recalc" ? admin.recalc() : admin.learnPredictive());
      await mutate();
    }
    catch (err) { setError(err instanceof Error ? err.message : "Falha ao disparar o job."); }
    finally { setBusy(null); }
  }

  const sorted = [...(jobs ?? [])].sort((a, b) => b.id - a.id);
  const pageJobs = sorted.slice((page - 1) * PER, page * PER);

  return (
    <div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 16 }}>
        <ActionCard icon="▶" title="Coletar dados" primary disabled={!!busy || running} busy={busy === "collect"} onClick={() => trigger("collect")}
          desc="Busca os dados oficiais da FIFA (calendário, jogos, escalações, stats) e regera scores e relatórios." />
        <ActionCard icon="↻" title="Recalcular" disabled={!!busy || running} busy={busy === "recalc"} onClick={() => trigger("recalc")}
          desc="Reprocessa os scores das seleções/jogadores e os pontos dos bolões com os dados já coletados." />
        <ActionCard icon="◎" title="Re-treinar preditiva" disabled={!!busy || running} busy={busy === "learn"} onClick={() => trigger("learn")}
          desc="Recalibra os parâmetros e pesos do modelo de previsão com os resultados reais. Pode levar alguns minutos." />
      </div>

      <AutoCollectCard />

      {running && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 16px", borderRadius: 10, background: "rgba(88,166,255,0.1)", border: "1px solid rgba(88,166,255,0.35)", marginBottom: 16, fontSize: "0.85rem", color: "#58a6ff", fontWeight: 600 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "#58a6ff", animation: "pulse 1.2s ease-in-out infinite" }} />
          Um job está em andamento — a lista atualiza sozinha.
        </div>
      )}
      {error && <p style={{ color: "#ef4444", fontSize: "0.85rem", marginBottom: 12 }}>{error}</p>}

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--surface2)" }}>
              {["ID", "Tipo", "Status", "Início", "Fim", ""].map((h, i) => (
                <th key={i} style={{ textAlign: i === 5 ? "right" : "left", padding: "9px 12px", fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Carregando…</td></tr>}
            {!isLoading && sorted.length === 0 && <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Nenhum job ainda. Use “Coletar dados” pra começar.</td></tr>}
            {pageJobs.map((j, i) => <JobRow key={j.id} job={j} index={i} />)}
          </tbody>
        </table>
      </div>
      <Pager page={page} total={sorted.length} perPage={PER} onPage={setPage} />
    </div>
  );
}

// ── Página ───────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [tab, setTab] = useState<"coleta" | "boloes" | "usuarios">("coleta");
  const TABS: [typeof tab, string][] = [["coleta", "Coleta"], ["boloes", "Bolões"], ["usuarios", "Usuários"]];

  return (
    <div style={{ maxWidth: 920, margin: "0 auto", padding: "28px 16px" }}>
      <style>{`@keyframes rowIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}@keyframes tabIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`}</style>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 800, marginBottom: 4 }}>Administração</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: 20 }}>Painel do admin — coleta de dados, bolões e usuários.</p>

      <div style={{ display: "flex", gap: 4, marginBottom: 22, borderBottom: "1px solid var(--border)" }}>
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} style={{ background: "none", border: "none", borderBottom: tab === k ? "2px solid var(--accent)" : "2px solid transparent", padding: "10px 16px", fontSize: "0.9rem", fontWeight: tab === k ? 700 : 500, color: tab === k ? "var(--accent)" : "var(--text-muted)", cursor: "pointer", marginBottom: -1 }}>{label}</button>
        ))}
      </div>

      <div key={tab} style={{ animation: "tabIn .25s ease both" }}>
        {tab === "coleta" && <CollectTab />}
        {tab === "boloes" && <PoolsAdmin />}
        {tab === "usuarios" && <UsersAdmin />}
      </div>
    </div>
  );
}
