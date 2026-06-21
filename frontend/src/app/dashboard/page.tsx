"use client";

import { useState } from "react";
import { clsx } from "clsx";
import MatchesTab from "@/components/dashboard/MatchesTab";
import TeamsTab from "@/components/dashboard/TeamsTab";
import PowerRankingTab from "@/components/dashboard/PowerRankingTab";

const TABS = [
  { id: "matches", label: "Jogos" },
  { id: "teams", label: "Seleções" },
  { id: "power-ranking", label: "Power Ranking" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabId>("matches");

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Tab bar */}
      <div
        style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)" }}
        className="flex items-center px-6 gap-1 shrink-0"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === id
                ? "border-blue-400 text-blue-300"
                : "border-transparent text-gray-400 hover:text-gray-200"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {activeTab === "matches" && <MatchesTab />}
        {activeTab === "teams" && <TeamsTab />}
        {activeTab === "power-ranking" && <PowerRankingTab />}
      </div>
    </div>
  );
}
