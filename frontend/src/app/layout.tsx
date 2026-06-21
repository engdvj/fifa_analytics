import type { Metadata } from "next";
import "./globals.css";
import SWRProvider from "@/components/SWRProvider";

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
        <SWRProvider>{children}</SWRProvider>
      </body>
    </html>
  );
}
