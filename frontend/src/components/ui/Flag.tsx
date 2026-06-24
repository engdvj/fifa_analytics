"use client";

import React from "react";
import { flag, flagUrl } from "@/lib/teamUtils";

interface FlagProps {
  team: string | null;
  height?: number; // px
  style?: React.CSSProperties;
}

// Renderiza a bandeira como imagem (flagcdn), com fallback pro emoji caso a
// imagem não carregue ou o time não tenha código. Resolve o Windows não ter
// fonte de emoji-bandeira nativa.
export default function Flag({ team, height = 14, style }: FlagProps) {
  const [failed, setFailed] = React.useState(false);
  const url = flagUrl(team, 20);
  if (!url || failed) {
    return <span style={{ fontSize: height + 2, lineHeight: 1, ...style }}>{flag(team)}</span>;
  }
  return (
    <img
      src={url}
      alt={team ?? ""}
      height={height}
      onError={() => setFailed(true)}
      style={{ height, width: "auto", borderRadius: 2, display: "block", flexShrink: 0, ...style }}
    />
  );
}
