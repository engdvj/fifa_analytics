"use client";

import AuthGuard from "@/components/AuthGuard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <main>
      <AuthGuard adminOnly>{children}</AuthGuard>
    </main>
  );
}
