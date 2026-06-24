"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthShell, authInput, authButton, AuthError } from "@/components/AuthShell";

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await auth.register({ username: username.trim(), name: name.trim() || undefined, password });
      if (!res.access_token) { setError("Não foi possível criar a conta."); return; }
      await login(res.access_token);
      router.push("/bolao");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Crie sua conta" subtitle="Monte bolões, palpite nos 104 jogos e dispute o ranking">
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <label style={lbl}>Usuário
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus
            placeholder="ex: craque10" style={authInput} autoComplete="username" />
        </label>
        <label style={lbl}>Nome de exibição <span style={{ color: "#586374", fontWeight: 400 }}>(opcional)</span>
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Como aparece no ranking" style={authInput} />
        </label>
        <label style={lbl}>Senha
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            placeholder="••••••••" style={authInput} autoComplete="new-password" />
        </label>
        <AuthError msg={error} />
        <button type="submit" disabled={loading} style={authButton(loading)}>
          {loading ? "Criando…" : "Entrar pra disputa 🏆"}
        </button>
      </form>
      <p style={{ marginTop: 18, textAlign: "center", fontSize: "0.85rem", color: "#8b949e" }}>
        Já tem conta?{" "}
        <Link href="/login" style={{ color: "#58a6ff", fontWeight: 700, textDecoration: "none" }}>Entrar</Link>
      </p>
    </AuthShell>
  );
}

const lbl: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 6, fontSize: "0.82rem", color: "#9fb0c3", fontWeight: 600 };
