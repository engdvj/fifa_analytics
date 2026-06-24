"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import AuthGuard from "@/components/AuthGuard";

function ProfileInner() {
  const { user, refresh, logout } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(user?.name ?? "");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (password && password !== password2) { setMsg({ kind: "err", text: "As senhas não conferem." }); return; }
    setBusy(true);
    try {
      await auth.updateMe({ name: name.trim() || undefined, password: password || undefined });
      await refresh();
      setPassword(""); setPassword2("");
      setMsg({ kind: "ok", text: "Perfil atualizado!" });
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof Error ? err.message : "Erro ao salvar." });
    } finally { setBusy(false); }
  }

  function handleLogout() { logout(); router.push("/login"); }

  if (!user) return null;
  const initial = (user.name || user.username || "?").charAt(0).toUpperCase();

  return (
    <div className="perfil" style={{ maxWidth: 560, margin: "32px auto", padding: "0 16px" }}>
      <style>{`
        @keyframes perfilIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
        .perfil input { transition: border-color .15s, box-shadow .15s; }
        .perfil input:not([disabled]):focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(88,166,255,0.16); }
        .perfil button[type=submit] { transition: transform .15s, box-shadow .15s, filter .15s; }
        .perfil button[type=submit]:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.06); box-shadow: 0 10px 26px rgba(88,166,255,0.4); }
      `}</style>
      {/* cabeçalho do perfil */}
      <div style={{ ...card, padding: "22px 24px", display: "flex", alignItems: "center", gap: 16, marginBottom: 16, boxShadow: "0 10px 30px -16px rgba(0,0,0,0.5)", animation: "perfilIn .3s ease both" }}>
        <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 56, height: 56, borderRadius: "50%", background: "linear-gradient(135deg,#4493e6,#58a6ff)", color: "#06182e", fontWeight: 800, fontSize: "1.6rem", flexShrink: 0, boxShadow: "0 6px 16px -4px rgba(88,166,255,0.5)" }}>{initial}</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--text)" }}>{user.name}</div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>@{user.username}</div>
          {user.is_admin && (
            <Link href="/admin" style={{ display: "inline-block", marginTop: 6, fontSize: "0.72rem", fontWeight: 700, color: "#f5c542", background: "rgba(245,197,66,0.12)", border: "1px solid rgba(245,197,66,0.3)", borderRadius: 6, padding: "2px 8px", textDecoration: "none" }}>⭐ ADMIN · abrir painel</Link>
          )}
        </div>
      </div>

      {/* edição */}
      <form onSubmit={save} style={{ ...card, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16, boxShadow: "0 10px 30px -16px rgba(0,0,0,0.5)", animation: "perfilIn .3s ease .06s both" }}>
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text)" }}>Editar perfil</h2>

        <Field label="Usuário (não editável)">
          <input value={user.username} disabled style={{ ...inp, color: "var(--text-muted)", cursor: "not-allowed" }} />
        </Field>
        <Field label="Nome de exibição">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Como aparece no ranking" style={inp} />
        </Field>

        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>Trocar senha <span style={{ color: "#586374" }}>(opcional)</span></span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Nova senha" style={inp} autoComplete="new-password" />
          <input type="password" value={password2} onChange={(e) => setPassword2(e.target.value)} placeholder="Confirmar nova senha" style={inp} autoComplete="new-password" />
        </div>

        {msg && <p style={{ margin: 0, fontSize: "0.84rem", color: msg.kind === "ok" ? "#22c55e" : "#ff7b72" }}>{msg.text}</p>}

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button type="submit" disabled={busy} style={{ background: "linear-gradient(135deg,#4493e6,#58a6ff)", color: "#06182e", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 800, fontSize: "0.9rem", cursor: busy ? "default" : "pointer", opacity: busy ? 0.7 : 1 }}>{busy ? "Salvando…" : "Salvar alterações"}</button>
          <Link href="/bolao" style={{ fontSize: "0.85rem", color: "var(--text-muted)", textDecoration: "none" }}>Voltar ao bolão</Link>
          <div style={{ flex: 1 }} />
          <button type="button" onClick={handleLogout} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 8, padding: "9px 14px", fontSize: "0.85rem", color: "var(--text-muted)", cursor: "pointer" }}>Sair</button>
        </div>
      </form>
    </div>
  );
}

export default function PerfilPage() {
  return <AuthGuard><ProfileInner /></AuthGuard>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: "0.82rem", color: "var(--text-muted)" }}>
      {label}
      {children}
    </label>
  );
}

const card: React.CSSProperties = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12 };
const inp: React.CSSProperties = { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.92rem", outline: "none", width: "100%", boxSizing: "border-box" };
