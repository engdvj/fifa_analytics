"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthShell, authInput, authButton, AuthError } from "@/components/AuthShell";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await auth.login(username.trim(), password);
      if (!res.access_token) { setError("Usuário ou senha incorretos."); return; }
      const u = await login(res.access_token);
      router.push(u.is_admin ? "/admin" : "/bolao");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Bem-vindo de volta" subtitle="Entre pra fazer seus palpites e subir no ranking">
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <label style={lbl}>Usuário
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus
            placeholder="seu_usuario" style={authInput} autoComplete="username" />
        </label>
        <label style={lbl}>Senha
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            placeholder="••••••••" style={authInput} autoComplete="current-password" />
        </label>
        <AuthError msg={error} />
        <button type="submit" disabled={loading} style={authButton(loading)}>
          {loading ? "Entrando…" : "Entrar em campo ⚽"}
        </button>
      </form>
      <p style={{ marginTop: 18, textAlign: "center", fontSize: "0.85rem", color: "#8b949e" }}>
        Ainda não tem conta?{" "}
        <Link href="/register" style={{ color: "#58a6ff", fontWeight: 700, textDecoration: "none" }}>Criar conta</Link>
      </p>
    </AuthShell>
  );
}

const lbl: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 6, fontSize: "0.82rem", color: "#9fb0c3", fontWeight: 600 };
