"""Bandeiras (emoji) por seleção — pt-BR. Cobre os 48 times da Copa 2026.

Fonte única para o watcher; espelha (e amplia) o dict FLAGS do bar_chart_race.py.
"""

from __future__ import annotations

FLAGS: dict[str, str] = {
    "Alemanha": "🇩🇪",
    "Argentina": "🇦🇷",
    "Argélia": "🇩🇿",
    "Arábia Saudita": "🇸🇦",
    "Austrália": "🇦🇺",
    "Brasil": "🇧🇷",
    "Bélgica": "🇧🇪",
    "Bósnia e Herzegovina": "🇧🇦",
    "Cabo Verde": "🇨🇻",
    "Canadá": "🇨🇦",
    "Catar": "🇶🇦",
    "Colômbia": "🇨🇴",
    "Coreia do Sul": "🇰🇷",
    "Costa do Marfim": "🇨🇮",
    "Croácia": "🇭🇷",
    "Curaçao": "🇨🇼",
    "Egito": "🇪🇬",
    "Equador": "🇪🇨",
    "Escócia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Espanha": "🇪🇸",
    "Estados Unidos": "🇺🇸",
    "França": "🇫🇷",
    "Gana": "🇬🇭",
    "Haiti": "🇭🇹",
    "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Iraque": "🇮🇶",
    "Irã": "🇮🇷",
    "Japão": "🇯🇵",
    "Jordânia": "🇯🇴",
    "Marrocos": "🇲🇦",
    "México": "🇲🇽",
    "Noruega": "🇳🇴",
    "Nova Zelândia": "🇳🇿",
    "Panamá": "🇵🇦",
    "Paraguai": "🇵🇾",
    "Países Baixos": "🇳🇱",
    "Portugal": "🇵🇹",
    "RD Congo": "🇨🇩",
    "Senegal": "🇸🇳",
    "Suécia": "🇸🇪",
    "Suíça": "🇨🇭",
    "Tchéquia": "🇨🇿",
    "Tunísia": "🇹🇳",
    "Turquia": "🇹🇷",
    "Uruguai": "🇺🇾",
    "Uzbequistão": "🇺🇿",
    "África do Sul": "🇿🇦",
    "Áustria": "🇦🇹",
}


def flag(team: str) -> str:
    return FLAGS.get(team, "🏳️")
