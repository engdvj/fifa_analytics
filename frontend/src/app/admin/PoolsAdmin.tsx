"use client";

// Gestão de bolões (admin): lista todos, transfere posse, exclui.
// Admin só administra — não joga. Transferir passa a posse (e a participação) a outro.

import { useEffect, useState } from "react";
import Modal from "@/components/ui/Modal";
import Pager from "@/components/ui/Pager";
import { bolao, users as usersApi, type AdminPool, type AppUser, type PoolScope } from "@/lib/api";
import { stageLabel } from "@/lib/stages";

const PER_PAGE = 10;

const input: React.CSSProperties = { width: "100%", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 12px", color: "var(--text)", fontSize: "0.9rem", outline: "none", boxSizing: "border-box" };
const primary: React.CSSProperties = { border: "none", borderRadius: 6, padding: "9px 16px", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", background: "var(--accent)", color: "#0d1117" };
const cancel: React.CSSProperties = { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 16px", fontSize: "0.85rem", cursor: "pointer" };
const small: React.CSSProperties = { background: "none", border: "1px solid var(--border)", borderRadius: 5, padding: "4px 11px", fontSize: "0.78rem", color: "var(--text-muted)", cursor: "pointer", whiteSpace: "nowrap" };
const errStyle: React.CSSProperties = { color: "#ef4444", fontSize: "0.82rem", margin: 0 };

function scopeLabel(s: PoolScope | null): string {
  if (!s || s.type === "all") return "Todos os jogos";
  if (s.type === "stage") return (s.stages ?? []).map(stageLabel).join(", ") || "Por fase";
  return `${(s.match_ids ?? []).length} jogos`;
}

function PoolRow({ p, index, onTransfer, onDelete }: { p: AdminPool; index: number; onTransfer: () => void; onDelete: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <tr onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ borderBottom: "1px solid var(--border)", background: hover ? "var(--surface2)" : "transparent", transition: "background .15s", animation: "rowIn .28s ease backwards", animationDelay: `${Math.min(index, 10) * 22}ms` }}>
      <td style={{ padding: "10px 12px", fontWeight: 600 }}>
        {p.parent_id != null && <span style={{ color: "var(--text-muted)", marginRight: 4 }}>↳</span>}
        {p.name}
        {p.is_group && <span style={{ marginLeft: 6, fontSize: "0.66rem", color: "var(--text-muted)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>grupo</span>}
        {p.rule_name && <span style={{ marginLeft: 8, fontSize: "0.72rem", color: "var(--text-muted)" }}>· {p.rule_name}</span>}
      </td>
      <td style={{ padding: "10px 12px", fontSize: "0.86rem" }}>{p.owner_name}</td>
      <td style={{ padding: "10px 12px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.86rem" }}>{p.members}</td>
      <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.82rem" }}>{scopeLabel(p.scope)}</td>
      <td style={{ padding: "10px 12px", textAlign: "right", whiteSpace: "nowrap" }}>
        <button onClick={onTransfer} style={small}>Transferir</button>{" "}
        <button onClick={onDelete} style={{ ...small, color: "#ef4444" }}>Excluir</button>
      </td>
    </tr>
  );
}

function Footer({ onClose, onSave, busy, confirmText, danger }: { onClose: () => void; onSave: () => void; busy: boolean; confirmText: string; danger?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
      <button onClick={onClose} disabled={busy} style={cancel}>Cancelar</button>
      <button onClick={onSave} disabled={busy} style={{ ...primary, background: danger ? "#ef4444" : "var(--accent)", color: danger ? "#fff" : "#0d1117", opacity: busy ? 0.7 : 1 }}>
        {busy ? "Aguarde…" : confirmText}
      </button>
    </div>
  );
}

function TransferModal({ pool, allUsers, onClose, onDone }: { pool: AdminPool; allUsers: AppUser[]; onClose: () => void; onDone: () => void }) {
  const [userId, setUserId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const candidates = allUsers.filter(u => u.id !== pool.owner_id);
  async function save() {
    if (!userId) { setError("Escolha o novo dono."); return; }
    setBusy(true); setError("");
    try { await bolao.transferPool(pool.id, Number(userId)); onDone(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao transferir."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title={`Transferir “${pool.name}”`} size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>Dono atual: <strong style={{ color: "var(--text)" }}>{pool.owner_name}</strong></p>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>Novo dono</label>
          <select autoFocus value={userId} onChange={e => setUserId(e.target.value ? Number(e.target.value) : "")} style={{ ...input, cursor: "pointer" }}>
            <option value="">Selecione…</option>
            {candidates.map(u => <option key={u.id} value={u.id}>{u.name} (@{u.username}){u.is_admin ? " — admin" : ""}</option>)}
          </select>
        </div>
        <p style={{ fontSize: "0.74rem", color: "var(--text-muted)", margin: 0 }}>O novo dono passa a poder editar o bolão e entra como jogador (a não ser que seja admin — admin só administra).</p>
        {error && <p style={errStyle}>{error}</p>}
        <Footer onClose={onClose} onSave={save} busy={busy} confirmText="Transferir" />
      </div>
    </Modal>
  );
}

function DeleteModal({ pool, onClose, onDone }: { pool: AdminPool; onClose: () => void; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function confirm() {
    setBusy(true); setError("");
    try { await bolao.deletePool(pool.id); onDone(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao excluir."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title="Excluir bolão" size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0, lineHeight: 1.55 }}>
          Excluir <strong style={{ color: "var(--text)" }}>{pool.name}</strong>{pool.is_group ? " e seus sub-bolões" : ""}? Apaga os palpites — não dá pra desfazer.
        </p>
        {error && <p style={errStyle}>{error}</p>}
        <Footer onClose={onClose} onSave={confirm} busy={busy} confirmText="Excluir" danger />
      </div>
    </Modal>
  );
}

type SortKey = "name" | "owner_name" | "members";
type ModalState = null | { kind: "transfer"; pool: AdminPool } | { kind: "delete"; pool: AdminPool };

export default function PoolsAdmin() {
  const [pools, setPools] = useState<AdminPool[] | null>(null);
  const [allUsers, setAllUsers] = useState<AppUser[]>([]);
  const [modal, setModal] = useState<ModalState>(null);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  async function refresh() { setPools(await bolao.adminPools()); }
  useEffect(() => {
    bolao.adminPools().then(setPools).catch(() => setPools([]));
    usersApi.list().then(setAllUsers).catch(() => {});
  }, []);

  function sortBy(k: SortKey) {
    if (k === sortKey) setSortDir(d => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir("asc"); }
  }

  const sorted = [...(pools ?? [])].sort((a, b) => {
    let cmp: number;
    if (sortKey === "members") cmp = a.members - b.members;
    else cmp = (a[sortKey] ?? "").localeCompare(b[sortKey] ?? "", "pt-BR");
    if (cmp === 0) cmp = a.name.localeCompare(b.name, "pt-BR");
    return sortDir === "asc" ? cmp : -cmp;
  });
  const curPage = Math.min(page, Math.max(1, Math.ceil(sorted.length / PER_PAGE)));
  const paged = sorted.slice((curPage - 1) * PER_PAGE, curPage * PER_PAGE);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>Bolões</h2>
        <span style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{pools ? `${pools.length} no total` : ""}</span>
      </div>

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--surface2)" }}>
              {([["name", "Bolão"], ["owner_name", "Dono"], ["members", "Jogadores"]] as [SortKey, string][]).map(([k, label]) => {
                const active = sortKey === k;
                return (
                  <th key={k} onClick={() => sortBy(k)} style={{ textAlign: k === "members" ? "center" : "left", padding: "9px 12px", fontSize: "0.72rem", color: active ? "var(--text)" : "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer", userSelect: "none" }}>
                    {label} <span style={{ fontSize: "0.85em", opacity: active ? 1 : 0.35 }}>{active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}</span>
                  </th>
                );
              })}
              <th style={{ textAlign: "left", padding: "9px 12px", fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Escopo</th>
              <th style={{ padding: "9px 12px" }} />
            </tr>
          </thead>
          <tbody>
            {pools === null && <tr><td colSpan={5} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Carregando…</td></tr>}
            {pools !== null && sorted.length === 0 && <tr><td colSpan={5} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Nenhum bolão.</td></tr>}
            {paged.map((p, i) => (
              <PoolRow key={p.id} p={p} index={i}
                onTransfer={() => setModal({ kind: "transfer", pool: p })}
                onDelete={() => setModal({ kind: "delete", pool: p })} />
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={curPage} total={sorted.length} perPage={PER_PAGE} onPage={setPage} />

      {modal?.kind === "transfer" && <TransferModal pool={modal.pool} allUsers={allUsers} onClose={() => setModal(null)} onDone={refresh} />}
      {modal?.kind === "delete" && <DeleteModal pool={modal.pool} onClose={() => setModal(null)} onDone={refresh} />}
    </div>
  );
}
