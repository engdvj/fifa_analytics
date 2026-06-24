"use client";

// CRUD de regras de pontuação (compartilhado entre o "Novo bolão" e a página
// de bolões). Regras "padrão" (owner_id null) são só leitura; as do usuário
// podem ser editadas/excluídas (o backend bloqueia excluir regra em uso).

import { useEffect, useState } from "react";
import Modal from "@/components/ui/Modal";
import { scoring, type ScoringRule, type ScoringCriterion } from "@/lib/api";

const input: React.CSSProperties = { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 12px", color: "var(--text)", fontSize: "0.9rem", outline: "none", boxSizing: "border-box", width: "100%" };
const card: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 };
const primary: React.CSSProperties = { border: "none", borderRadius: 6, padding: "9px 16px", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", background: "var(--accent)", color: "#0d1117" };
const cancel: React.CSSProperties = { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 16px", fontSize: "0.85rem", cursor: "pointer" };
const small: React.CSSProperties = { background: "none", border: "1px solid var(--border)", borderRadius: 5, padding: "4px 10px", fontSize: "0.76rem", color: "var(--text-muted)", cursor: "pointer", whiteSpace: "nowrap" };
const errStyle: React.CSSProperties = { color: "#ef4444", fontSize: "0.82rem", margin: 0 };
const muted: React.CSSProperties = { color: "var(--text-muted)", fontSize: "0.85rem" };

const MODE_LABELS: Record<string, string> = { max: "Vale o maior", sum: "Soma todos" };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 6 }}><label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{label}</label>{children}</div>;
}

export default function RulesModal({ criteria, modes, isAdmin, onClose, onChanged }: {
  criteria: ScoringCriterion[]; modes: string[]; isAdmin?: boolean; onClose: () => void; onChanged?: () => void;
}) {
  const [list, setList] = useState<ScoringRule[] | null>(null);
  const [view, setView] = useState<"list" | "edit">("list");
  const [editId, setEditId] = useState<number | null>(null); // null = nova
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [points, setPoints] = useState<Record<string, number>>({});
  const [mode, setMode] = useState("max");
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { scoring.rules().then(setList).catch(() => setList([])); }, []);

  async function refresh() { setList(await scoring.rules()); onChanged?.(); }

  function newRule() {
    setEditId(null); setName(""); setDesc("");
    setPoints({ exact_score: 5, correct_winner: 3 }); setMode("max"); setError(""); setView("edit");
  }
  function editRule(r: ScoringRule) {
    setEditId(r.id); setName(r.name); setDesc(r.description ?? "");
    const p: Record<string, number> = {};
    Object.entries(r.spec).forEach(([k, v]) => { if (!k.startsWith("_")) p[k] = Number(v); });
    setPoints(p); setMode(String(r.spec._mode ?? "max")); setError(""); setView("edit");
  }

  async function save() {
    if (!name.trim()) { setError("Dê um nome à regra."); return; }
    const spec: Record<string, number | string> = {};
    Object.entries(points).forEach(([k, v]) => { if (Number(v) > 0) spec[k] = Number(v); });
    if (Object.keys(spec).length === 0) { setError("Defina ao menos um critério com pontos."); return; }
    spec._mode = mode;
    setBusy(true); setError("");
    try {
      if (editId === null) await scoring.createRule({ name: name.trim(), description: desc.trim() || undefined, spec });
      else await scoring.updateRule(editId, { name: name.trim(), description: desc.trim() || undefined, spec });
      await refresh(); setView("list");
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setBusy(false); }
  }

  async function remove(id: number) {
    setBusy(true); setError("");
    try { await scoring.deleteRule(id); setConfirmId(null); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao excluir."); }
    finally { setBusy(false); }
  }

  function summary(r: ScoringRule): string {
    const parts = Object.entries(r.spec).filter(([k]) => !k.startsWith("_"))
      .map(([k, v]) => `${criteria.find(c => c.key === k)?.label ?? k}: ${v}`);
    return `${parts.join(" · ")} · ${MODE_LABELS[String(r.spec._mode ?? "max")] ?? "Vale o maior"}`;
  }

  const title = view === "list" ? "Regras de pontuação" : (editId === null ? "Nova regra" : "Editar regra");

  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title={title} size="md">
      {view === "list" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {error && <p style={errStyle}>{error}</p>}
          <button onClick={newRule} style={primary}>+ Nova regra</button>
          {list === null ? <p style={muted}>Carregando…</p>
            : <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 360, overflowY: "auto" }}>
              {list.map(r => {
                const builtin = r.owner_id === null;
                return (
                  <div key={r.id} style={{ ...card, padding: "10px 12px", display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>
                        {r.name}{builtin && <span style={{ marginLeft: 6, fontSize: "0.68rem", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>padrão</span>}
                      </div>
                      <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 2 }}>{summary(r)}</div>
                    </div>
                    {(builtin && !isAdmin) ? null
                      : confirmId === r.id ? (
                        <>
                          <button onClick={() => remove(r.id)} disabled={busy} style={{ ...small, background: "#ef4444", color: "#fff", border: "none" }}>Excluir</button>
                          <button onClick={() => setConfirmId(null)} style={small}>Não</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => editRule(r)} style={small}>Editar</button>
                          <button onClick={() => { setConfirmId(r.id); setError(""); }} style={{ ...small, color: "#ef4444" }}>Excluir</button>
                        </>
                      )}
                  </div>
                );
              })}
            </div>}
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button onClick={onClose} style={cancel}>Fechar</button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Nome"><input value={name} onChange={e => setName(e.target.value)} style={input} placeholder="Ex.: Minha regra" /></Field>
          <Field label="Descrição (opcional)"><input value={desc} onChange={e => setDesc(e.target.value)} style={input} /></Field>
          <div style={{ ...card, padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
            {criteria.map(c => (
              <div key={c.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{c.label}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", lineHeight: 1.3 }}>{c.description}</div>
                </div>
                <input type="number" min={0} max={99} value={points[c.key] ?? 0} onChange={e => setPoints(p => ({ ...p, [c.key]: Number(e.target.value) }))} style={{ ...input, width: 60, textAlign: "center", padding: "7px 6px", fontWeight: 700 }} />
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>pts</span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", gap: 10, borderTop: "1px solid var(--border)", paddingTop: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Acertando vários critérios:</span>
              <select value={mode} onChange={e => setMode(e.target.value)} style={{ ...input, width: "auto", minWidth: 140, cursor: "pointer" }}>
                {(modes.length ? modes : ["max", "sum"]).map(m => <option key={m} value={m}>{MODE_LABELS[m] ?? m}</option>)}
              </select>
            </div>
          </div>
          {error && <p style={errStyle}>{error}</p>}
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button onClick={() => { setView("list"); setError(""); }} disabled={busy} style={cancel}>Voltar</button>
            <button onClick={save} disabled={busy} style={{ ...primary, opacity: busy ? 0.7 : 1 }}>{busy ? "Salvando…" : "Salvar"}</button>
          </div>
        </div>
      )}
    </Modal>
  );
}
