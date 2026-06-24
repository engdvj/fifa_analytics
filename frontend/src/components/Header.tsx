"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

const NAV = [
  { href: "/dashboard", label: "Analytics" },
  { href: "/bolao", label: "Bolão" },
  { href: "/definicoes", label: "Definições" },
];

export default function Header() {
  const path = usePathname();
  const router = useRouter();
  const { user, logout, isAuthenticated } = useAuth();

  // No popup do glossário (?popup=1) não mostramos a barra global.
  const [isPopup, setIsPopup] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsPopup(new URLSearchParams(window.location.search).get("popup") === "1");
    }
  }, [path]);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  // Barra global: só aparece logado (some no login/registro e no popup).
  if (!isAuthenticated || isPopup) return null;

  return (
    <header
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        height: 52,
        gap: 8,
        flexShrink: 0,
      }}
    >
      <Link
        href="/dashboard"
        style={{ color: "var(--text)", fontWeight: 700, fontSize: "0.95rem", textDecoration: "none", marginRight: 8 }}
      >
        Copa 2026
      </Link>

      <nav style={{ display: "flex", gap: 2, flex: 1 }}>
        {[...NAV, ...(user?.is_admin ? [{ href: "/admin", label: "Admin" }] : [])].map(({ href, label }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              style={{
                padding: "5px 12px",
                borderRadius: 6,
                fontSize: "0.85rem",
                fontWeight: active ? 600 : 400,
                textDecoration: "none",
                color: active ? "var(--accent)" : "var(--text-muted)",
                background: active ? "rgba(88,166,255,0.1)" : "transparent",
                transition: "color 0.12s, background 0.12s",
              }}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {isAuthenticated && user && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link
            href="/perfil"
            title="Meu perfil"
            style={{
              display: "inline-flex", alignItems: "center", gap: 8, textDecoration: "none",
              color: path.startsWith("/perfil") ? "var(--accent)" : "var(--text)",
              background: path.startsWith("/perfil") ? "rgba(88,166,255,0.1)" : "transparent",
              border: "1px solid var(--border)", borderRadius: 20, padding: "3px 10px 3px 3px",
            }}
          >
            <span style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 26, height: 26, borderRadius: "50%", background: "linear-gradient(135deg,#2ea043,#3fb950)",
              color: "#04130a", fontWeight: 800, fontSize: "0.8rem",
            }}>{(user.name || user.username || "?").charAt(0).toUpperCase()}</span>
            <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>{user.name}</span>
          </Link>
          <button
            onClick={handleLogout}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "5px 10px",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Sair
          </button>
        </div>
      )}

      {!isAuthenticated && (
        <Link
          href="/login"
          style={{
            background: "var(--accent)",
            color: "#0d1117",
            borderRadius: 6,
            padding: "5px 14px",
            fontSize: "0.82rem",
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          Entrar
        </Link>
      )}
    </header>
  );
}
