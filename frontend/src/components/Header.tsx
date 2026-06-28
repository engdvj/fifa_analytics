"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV = [
  { href: "/dashboard", label: "Analytics" },
  { href: "/bolao", label: "Bolão" },
  { href: "/definicoes", label: "Definições" },
];

export default function Header() {
  const path = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, logout, isAuthenticated } = useAuth();

  // No popup do glossário (?popup=1) não mostramos a barra global.
  const isPopup = searchParams.get("popup") === "1";

  function handleLogout() {
    logout();
    router.push("/login");
  }

  // Barra global: só aparece logado (some no login/registro e no popup).
  if (!isAuthenticated || isPopup) return null;

  return (
    <header
      className="app-header"
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
        width: "100%",
        maxWidth: "100vw",
        overflow: "hidden",
      }}
    >
      <Link
        className="app-header-brand"
        href="/dashboard"
        style={{ color: "var(--text)", fontWeight: 700, fontSize: "0.95rem", textDecoration: "none", marginRight: 8, flexShrink: 0 }}
      >
        Copa 2026
      </Link>

      <nav className="app-header-nav" style={{ display: "flex", gap: 2, flex: "1 1 auto", minWidth: 0, overflowX: "auto", scrollbarWidth: "thin" }}>
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
                flex: "0 0 auto",
              }}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {isAuthenticated && user && (
        <div className="app-header-actions" style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, minWidth: 0 }}>
          <Link
            className="app-header-profile"
            href="/perfil"
            title="Meu perfil"
            style={{
              display: "inline-flex", alignItems: "center", gap: 8, textDecoration: "none",
              color: path.startsWith("/perfil") ? "var(--accent)" : "var(--text)",
              background: path.startsWith("/perfil") ? "rgba(88,166,255,0.1)" : "transparent",
              border: "1px solid var(--border)", borderRadius: 20, padding: "3px 10px 3px 3px",
              minWidth: 0,
            }}
          >
            <span style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 26, height: 26, borderRadius: "50%", background: "linear-gradient(135deg,#2ea043,#3fb950)",
              color: "#04130a", fontWeight: 800, fontSize: "0.8rem",
            }}>{(user.name || user.username || "?").charAt(0).toUpperCase()}</span>
            <span className="app-header-name" style={{ fontSize: "0.82rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.name}</span>
          </Link>
          <button
            className="app-header-logout"
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
