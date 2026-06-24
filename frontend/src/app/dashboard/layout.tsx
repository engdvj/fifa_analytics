"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// Plataforma de membros: o dashboard exige login. Sem sessão → /login.
// O dashboard React tem header/layout próprios, então aqui só gating (sem
// duplicar o header global do app).
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0d1117", color: "#8b949e", fontSize: "0.9rem" }}>
        Carregando…
      </div>
    );
  }

  return <>{children}</>;
}
