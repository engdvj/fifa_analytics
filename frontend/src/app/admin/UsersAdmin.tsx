"use client";

// Gestão de usuários (admin): CRUD completo com modais.
// Backend: GET/POST/PATCH/DELETE /users (editar/excluir exige admin ou o próprio).

import { useEffect, useState } from "react";
import Modal from "@/components/ui/Modal";
import Pager from "@/components/ui/Pager";
import { users, type AppUser } from "@/lib/api";

const PER_PAGE = 10;

function UserRow({ u, index, onEdit, onDelete }: { u: AppUser; index: number; onEdit: () => void; onDelete: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <tr onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ borderBottom: "1px solid var(--border)", background: hover ? "var(--surface2)" : "transparent", transition: "background .15s", animation: "rowIn .28s ease backwards", animationDelay: `${Math.min(index, 10) * 22}ms` }}>
      <td style={{ padding: "10px 12px", fontWeight: 600 }}>{u.name}</td>
      <td style={{ padding: "10px 12px", color: "var(--text-muted)", fontSize: "0.84rem" }}>@{u.username}</td>
      <td style={{ padding: "10px 12px" }}>
        <span style={{ fontSize: "0.72rem", fontWeight: 700, padding: "2px 8px", borderRadius: 20, color: u.is_admin ? "#58a6ff" : "var(--text-muted)", background: u.is_admin ? "rgba(88,166,255,0.12)" : "var(--surface2)" }}>{u.is_admin ? "Admin" : "Comum"}</span>
      </td>
      <td style={{ padding: "10px 12px", textAlign: "right", whiteSpace: "nowrap" }}>
        <button onClick={onEdit} style={small}>Editar</button>{" "}
        <button onClick={onDelete} style={{ ...small, color: "#ef4444" }}>Excluir</button>
      </td>
    </tr>
  );
}

const input: React.CSSProperties = { width: "100%", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 6, padding: "9px 12px", color: "var(--text)", fontSize: "0.9rem", outline: "none", boxSizing: "border-box" };
const primary: React.CSSProperties = { border: "none", borderRadius: 6, padding: "9px 16px", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", background: "var(--accent)", color: "#0d1117" };
const cancel: React.CSSProperties = { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 16px", fontSize: "0.85rem", cursor: "pointer" };
const small: React.CSSProperties = { background: "none", border: "1px solid var(--border)", borderRadius: 5, padding: "4px 11px", fontSize: "0.78rem", color: "var(--text-muted)", cursor: "pointer", whiteSpace: "nowrap" };
const errStyle: React.CSSProperties = { color: "#ef4444", fontSize: "0.82rem", margin: 0 };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 6 }}><label style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{label}</label>{children}</div>;
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

function AdminToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: "0.86rem", cursor: "pointer", color: "var(--text)" }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      Administrador <span style={{ color: "var(--text-muted)", fontSize: "0.76rem" }}>(acesso ao painel de admin)</span>
    </label>
  );
}

function CreateUserModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    if (!name.trim()) { setError("Informe o nome."); return; }
    if (!login.trim()) { setError("Informe o nome de usuário (login)."); return; }
    if (!password) { setError("Informe a senha."); return; }
    setBusy(true); setError("");
    try {
      await users.create({ username: login.trim(), name: name.trim(), password, is_admin: isAdmin });
      onDone(); onClose();
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao criar."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title="Novo usuário" size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nome"><input autoFocus value={name} onChange={e => setName(e.target.value)} style={input} placeholder="Ex.: João Silva" /></Field>
        <Field label="Nome de usuário (login)"><input value={login} onChange={e => setLogin(e.target.value)} style={input} placeholder="ex.: joao" /></Field>
        <Field label="Senha"><input type="password" value={password} onChange={e => setPassword(e.target.value)} style={input} placeholder="••••••" /></Field>
        <AdminToggle checked={isAdmin} onChange={setIsAdmin} />
        {error && <p style={errStyle}>{error}</p>}
        <Footer onClose={onClose} onSave={save} busy={busy} confirmText="Criar" />
      </div>
    </Modal>
  );
}

function EditUserModal({ user, onClose, onDone }: { user: AppUser; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(user.name);
  const [isAdmin, setIsAdmin] = useState(!!user.is_admin);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    if (!name.trim()) { setError("O nome não pode ficar vazio."); return; }
    setBusy(true); setError("");
    try {
      await users.update(user.id, { name: name.trim(), is_admin: isAdmin });
      onDone(); onClose();
    } catch (e) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title={`Editar ${user.name}`} size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nome"><input autoFocus value={name} onChange={e => setName(e.target.value)} style={input} /></Field>
        <AdminToggle checked={isAdmin} onChange={setIsAdmin} />
        <p style={{ fontSize: "0.74rem", color: "var(--text-muted)", margin: 0 }}>Login: <strong>@{user.username}</strong> (não editável)</p>
        {error && <p style={errStyle}>{error}</p>}
        <Footer onClose={onClose} onSave={save} busy={busy} confirmText="Salvar" />
      </div>
    </Modal>
  );
}

function DeleteUserModal({ user, onClose, onDone }: { user: AppUser; onClose: () => void; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function confirm() {
    setBusy(true); setError("");
    try { await users.remove(user.id); onDone(); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro ao excluir."); }
    finally { setBusy(false); }
  }
  return (
    <Modal open onClose={() => { if (!busy) onClose(); }} title="Excluir usuário" size="sm">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0, lineHeight: 1.55 }}>
          Excluir <strong style={{ color: "var(--text)" }}>{user.name}</strong>? Isso apaga os palpites e participações dele em todos os bolões — não dá pra desfazer. (Se for dono de algum bolão, a exclusão é bloqueada.)
        </p>
        {error && <p style={errStyle}>{error}</p>}
        <Footer onClose={onClose} onSave={confirm} busy={busy} confirmText="Excluir" danger />
      </div>
    </Modal>
  );
}

type ModalState = null | { kind: "create" } | { kind: "edit"; user: AppUser } | { kind: "delete"; user: AppUser };

type SortKey = "name" | "username" | "is_admin";

export default function UsersAdmin() {
  const [list, setList] = useState<AppUser[] | null>(null);
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState<ModalState>(null);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  async function refresh() { setList(await users.list()); }
  useEffect(() => { users.list().then(setList).catch(() => setList([])); }, []);

  function sortBy(k: SortKey) {
    if (k === sortKey) setSortDir(d => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir("asc"); }
  }

  const filtered = (list ?? []).filter(u =>
    !search.trim() || u.name.toLowerCase().includes(search.toLowerCase()) || u.username.toLowerCase().includes(search.toLowerCase()));

  const sorted = [...filtered].sort((a, b) => {
    let cmp: number;
    if (sortKey === "is_admin") cmp = Number(!!a.is_admin) - Number(!!b.is_admin);
    else {
      const va = sortKey === "username" ? a.username : a.name;
      const vb = sortKey === "username" ? b.username : b.name;
      cmp = va.localeCompare(vb, "pt-BR");
    }
    if (cmp === 0) cmp = a.name.localeCompare(b.name, "pt-BR");
    return sortDir === "asc" ? cmp : -cmp;
  });

  const curPage = Math.min(page, Math.max(1, Math.ceil(sorted.length / PER_PAGE)));
  const paged = sorted.slice((curPage - 1) * PER_PAGE, curPage * PER_PAGE);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>Usuários</h2>
        <span style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{list ? `${list.length} no total` : ""}</span>
        <div style={{ flex: 1 }} />
        {(list?.length ?? 0) > 6 && <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Buscar…" style={{ ...input, width: 180 }} />}
        <button onClick={() => setModal({ kind: "create" })} style={primary}>+ Novo usuário</button>
      </div>

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--surface2)" }}>
              {([["name", "Nome"], ["username", "Login"], ["is_admin", "Tipo"]] as [SortKey, string][]).map(([k, label]) => {
                const active = sortKey === k;
                return (
                  <th key={k} onClick={() => sortBy(k)} style={{ textAlign: "left", padding: "9px 12px", fontSize: "0.72rem", color: active ? "var(--text)" : "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer", userSelect: "none" }}>
                    {label} <span style={{ fontSize: "0.85em", opacity: active ? 1 : 0.35 }}>{active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}</span>
                  </th>
                );
              })}
              <th style={{ padding: "9px 12px" }} />
            </tr>
          </thead>
          <tbody>
            {list === null && <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Carregando…</td></tr>}
            {list !== null && sorted.length === 0 && <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>Nenhum usuário.</td></tr>}
            {paged.map((u, i) => (
              <UserRow key={u.id} u={u} index={i}
                onEdit={() => setModal({ kind: "edit", user: u })}
                onDelete={() => setModal({ kind: "delete", user: u })} />
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={curPage} total={sorted.length} perPage={PER_PAGE} onPage={setPage} />

      {modal?.kind === "create" && <CreateUserModal onClose={() => setModal(null)} onDone={refresh} />}
      {modal?.kind === "edit" && <EditUserModal user={modal.user} onClose={() => setModal(null)} onDone={refresh} />}
      {modal?.kind === "delete" && <DeleteUserModal user={modal.user} onClose={() => setModal(null)} onDone={refresh} />}
    </div>
  );
}
