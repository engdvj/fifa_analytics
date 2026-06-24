"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// Envolve qualquer página/área que exija usuário autenticado.
// Redireciona para /login enquanto não houver sessão. Quando adminOnly,
// usuários sem is_admin veem uma mensagem amigável em vez de conteúdo.
export default function AuthGuard({
  children,
  adminOnly = false,
}: {
  children: React.ReactNode;
  adminOnly?: boolean;
}) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: "60vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: "0.9rem",
        }}
      >
        Carregando…
      </div>
    );
  }

  if (!isAuthenticated) return null;

  if (adminOnly && !user?.is_admin) {
    return (
      <div
        style={{
          maxWidth: 440,
          margin: "80px auto",
          padding: "32px",
          textAlign: "center",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
        }}
      >
        <div style={{ fontSize: "2rem", marginBottom: 8 }}>🔒</div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: 8, color: "var(--text)" }}>
          Acesso restrito
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0 }}>
          Esta área é exclusiva para administradores. Fale com quem cuida da
          plataforma se você precisa de acesso.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
