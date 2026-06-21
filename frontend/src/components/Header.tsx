"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/bolao", label: "Bolão" },
];

export default function Header() {
  const path = usePathname();

  return (
    <header
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
      }}
      className="sticky top-0 z-50 flex items-center gap-6 px-6 h-14"
    >
      <Link
        href="/dashboard"
        style={{ color: "var(--text)", fontWeight: 700, fontSize: "1rem" }}
        className="no-underline tracking-tight"
      >
        Copa 2026
      </Link>

      <nav className="flex gap-1">
        {NAV.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "px-3 py-1.5 rounded text-sm font-medium transition-colors no-underline",
              path.startsWith(href)
                ? "bg-blue-500/20 text-blue-300"
                : "text-gray-400 hover:text-gray-200"
            )}
          >
            {label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
