import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import SWRProvider from "@/components/SWRProvider";
import { AuthProvider } from "@/lib/auth-context";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "Copa 2026 — Analytics & Bolão",
  description: "Dashboard de analytics e bolão oficial da Copa do Mundo 2026",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className="h-full">
      <body className="min-h-full flex flex-col">
        <SWRProvider>
          <AuthProvider>
            {/* Barra global fixa — só aparece logado (some no login/registro) */}
            <Suspense fallback={null}>
              <Header />
            </Suspense>
            {children}
          </AuthProvider>
        </SWRProvider>
      </body>
    </html>
  );
}
