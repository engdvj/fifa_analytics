"use client";

import DashboardV2Page from "./v2/page";

// Cutover: /dashboard serve o dashboard React. Navegação (Bolão/Admin/Perfil)
// fica na barra global fixa do app (components/Header.tsx).
export default function DashboardPage() {
  return <DashboardV2Page />;
}
