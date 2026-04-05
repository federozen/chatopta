import streamlit as st
import anthropic
import json
import requests
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Football Chat ⚽", page_icon="⚽", layout="wide")

st.markdown("""
<style>
  /* ── base ── */
  .stApp { background:#f6f8fa; color:#1f2328; }

  /* ── sidebar ── */
  section[data-testid="stSidebar"] {
    background:#ffffff;
    border-right:1px solid #d1d9e0;
  }
  section[data-testid="stSidebar"] * { color:#1f2328 !important; }
  section[data-testid="stSidebar"] .stButton>button {
    background:#f6f8fa; color:#1f2328;
    border:1px solid #d1d9e0; border-radius:6px;
    font-size:.8rem; text-align:left; padding:5px 10px;
    width:100%;
  }
  section[data-testid="stSidebar"] .stButton>button:hover {
    background:#eaeef2; border-color:#0969da; color:#0969da !important;
  }

  /* ── chat messages ── */
  .stChatMessage {
    background:#ffffff;
    border:1px solid #d1d9e0;
    border-radius:12px;
    margin-bottom:.5rem;
  }
  .stChatMessage[data-testid="stChatMessage-user"] {
    background:#dbeafe;
    border-color:#93c5fd;
  }

  /* ── chat input ── */
  .stChatInput textarea {
    background:#ffffff !important;
    color:#1f2328 !important;
    border:1px solid #d1d9e0 !important;
    border-radius:8px !important;
  }
  .stChatInput > div {
    background:#ffffff !important;
    border:1px solid #d1d9e0 !important;
    border-radius:10px !important;
  }

  /* ── tool pills ── */
  .pill {
    display:inline-block;
    background:#dbeafe; color:#1d4ed8;
    border:1px solid #93c5fd;
    border-radius:20px;
    padding:2px 10px; font-size:.72rem;
    margin:2px; font-weight:600;
  }

  /* ── typography ── */
  h1 { color:#0969da !important; }
  h2, h3 { color:#1f2328 !important; }
  hr { border-color:#d1d9e0; }

  /* ── expander ── */
  details summary { color:#1f2328 !important; font-weight:600; }

  /* ── api key input ── */
  .stTextInput input {
    background:#ffffff !important;
    color:#1f2328 !important;
    border:1px solid #d1d9e0 !important;
  }

  /* ── misc ── */
  .stSpinner > div { color:#0969da !important; }
  code { background:#eaeef2; color:#1f2328; padding:1px 5px; border-radius:4px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
_SS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
SS_BASE = "https://api.sofascore.com/api/v1"

def _ss(path: str) -> dict:
    r = requests.get(f"{SS_BASE}{path}", headers=_SS_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def _fmt_dt(ts) -> str | None:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC") if ts else None

def _fmt_date(ts) -> str | None:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else None

def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════════════════
# SOFASCORE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def ss_live(sport: str = "football") -> dict:
    """Partidos en vivo ahora mismo."""
    try:
        evs = _ss(f"/sport/{sport}/events/live").get("events", [])[:25]
        return {
            "fetched_at_utc": _today_utc(),
            "count": len(evs),
            "live": [{
                "id": e.get("id"),
                "home": e.get("homeTeam", {}).get("name"),
                "away": e.get("awayTeam", {}).get("name"),
                "home_score": e.get("homeScore", {}).get("current"),
                "away_score": e.get("awayScore", {}).get("current"),
                "minute": e.get("time", {}).get("played"),
                "status": e.get("status", {}).get("description"),
                "tournament": e.get("tournament", {}).get("name"),
                "country": e.get("tournament", {}).get("category", {}).get("name"),
            } for e in evs],
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_search_team(name: str) -> dict:
    """Busca un equipo por nombre y devuelve su ID de SofaScore."""
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=team").get("results", [])
        return {"teams": [{
            "id": r["entity"].get("id"),
            "name": r["entity"].get("name"),
            "country": r["entity"].get("country", {}).get("name"),
            "sport": r["entity"].get("sport", {}).get("name"),
        } for r in rs[:6] if r.get("type") == "team"]}
    except Exception as ex:
        return {"error": str(ex)}


def ss_team_recent(team_id: str) -> dict:
    """Últimos 10 partidos jugados por un equipo."""
    try:
        evs = _ss(f"/team/{team_id}/events/last/0").get("events", [])[-10:]
        return {
            "today_utc": _today_utc(),
            "matches": [{
                "id": e.get("id"),
                "home": e.get("homeTeam", {}).get("name"),
                "away": e.get("awayTeam", {}).get("name"),
                "home_score": e.get("homeScore", {}).get("current"),
                "away_score": e.get("awayScore", {}).get("current"),
                "status": e.get("status", {}).get("description"),
                "tournament": e.get("tournament", {}).get("name"),
                "date": _fmt_date(e.get("startTimestamp")),
            } for e in evs],
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_team_next(team_id: str) -> dict:
    """Próximos partidos programados de un equipo. Incluye fecha y hora en UTC."""
    try:
        evs = _ss(f"/team/{team_id}/events/next/0").get("events", [])[:7]
        return {
            "today_utc": _today_utc(),
            "next_matches": [{
                "id": e.get("id"),
                "home": e.get("homeTeam", {}).get("name"),
                "away": e.get("awayTeam", {}).get("name"),
                "tournament": e.get("tournament", {}).get("name"),
                "datetime_utc": _fmt_dt(e.get("startTimestamp")),
                "date": _fmt_date(e.get("startTimestamp")),
            } for e in evs],
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_match_data(match_id: str) -> dict:
    """Datos generales de un partido: equipos, resultado, estado, torneo, sede."""
    try:
        ev = _ss(f"/event/{match_id}").get("event", {})
        return {
            "home": ev.get("homeTeam", {}).get("name"),
            "away": ev.get("awayTeam", {}).get("name"),
            "home_score": ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("awayScore", {}).get("current"),
            "status": ev.get("status", {}).get("description"),
            "tournament": ev.get("tournament", {}).get("name"),
            "country": ev.get("tournament", {}).get("category", {}).get("name"),
            "datetime_utc": _fmt_dt(ev.get("startTimestamp")),
            "venue": ev.get("venue", {}).get("name") if ev.get("venue") else None,
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_match_stats(match_id: str) -> dict:
    """Estadísticas del partido: posesión, tiros, córners, faltas, etc."""
    try:
        gs = _ss(f"/event/{match_id}/statistics").get("statistics", [])
        rows = []
        for g in gs:
            for item in g.get("groups", []):
                for s in item.get("statisticsItems", []):
                    rows.append({
                        "stat": s.get("name"),
                        "home": s.get("home"),
                        "away": s.get("away"),
                    })
        return {"statistics": rows}
    except Exception as ex:
        return {"error": str(ex)}


def ss_match_lineups(match_id: str) -> dict:
    """Alineaciones, formaciones, números de camiseta y calificaciones."""
    try:
        data = _ss(f"/event/{match_id}/lineups")
        out = {}
        for side in ("home", "away"):
            td = data.get(side, {})
            out[side] = {
                "formation": td.get("formation"),
                "players": [{
                    "name": p.get("player", {}).get("name"),
                    "position": p.get("position"),
                    "shirt": p.get("shirtNumber"),
                    "sub": p.get("substitute", False),
                    "rating": p.get("statistics", {}).get("rating"),
                    "goals": p.get("statistics", {}).get("goals"),
                    "assists": p.get("statistics", {}).get("goalAssist"),
                    "yellow": p.get("statistics", {}).get("yellowCards"),
                    "red": p.get("statistics", {}).get("redCards"),
                } for p in td.get("players", [])],
            }
        return out
    except Exception as ex:
        return {"error": str(ex)}


def ss_match_shotmap(match_id: str) -> dict:
    """Mapa de disparos con xG, minuto, jugador y tipo de tiro."""
    try:
        shots = _ss(f"/event/{match_id}/shotmap").get("shotmap", [])
        rows = [{
            "player": s.get("player", {}).get("name"),
            "team": "home" if s.get("isHome") else "away",
            "minute": s.get("time"),
            "shot_type": s.get("shotType"),
            "situation": s.get("situation"),
            "xG": round(s.get("xg", 0), 3) if s.get("xg") else None,
            "on_target": s.get("isOnTarget"),
        } for s in shots]
        home = [r for r in rows if r["team"] == "home"]
        away = [r for r in rows if r["team"] == "away"]
        return {
            "total": len(rows),
            "home_shots": len(home), "away_shots": len(away),
            "home_xG": round(sum(r["xG"] or 0 for r in home), 2),
            "away_xG": round(sum(r["xG"] or 0 for r in away), 2),
            "shots": rows,
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_match_momentum(match_id: str) -> dict:
    """Momentum del partido (dominio local vs visitante en el tiempo)."""
    try:
        pts = _ss(f"/event/{match_id}/graph").get("graphPoints", [])
        if not pts:
            return {"error": "Sin datos de momentum para este partido."}
        return {
            "total_points": len(pts),
            "home_dominant": len([p for p in pts if p.get("value", 0) > 0]),
            "away_dominant": len([p for p in pts if p.get("value", 0) < 0]),
            "timeline": pts[:40],
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_search_player(name: str) -> dict:
    """Busca un jugador por nombre. Devuelve ID, equipo, posición y nacionalidad."""
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=player").get("results", [])
        return {"players": [{
            "id": r["entity"].get("id"),
            "name": r["entity"].get("name"),
            "team": r["entity"].get("team", {}).get("name") if r["entity"].get("team") else None,
            "position": r["entity"].get("position"),
            "nationality": r["entity"].get("country", {}).get("name"),
        } for r in rs[:5] if r.get("type") == "player"]}
    except Exception as ex:
        return {"error": str(ex)}


def ss_search_tournament(name: str) -> dict:
    """Busca un torneo/liga por nombre. Devuelve ID y season_id de la temporada actual."""
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=uniqueTournament").get("results", [])
        out = []
        for r in rs[:5]:
            if r.get("type") == "uniqueTournament":
                e = r["entity"]
                tid = e.get("id")
                si = {}
                try:
                    s = _ss(f"/unique-tournament/{tid}/seasons").get("seasons", [{}])[0]
                    si = {"season_id": s.get("id"), "season_name": s.get("name")}
                except Exception:
                    pass
                out.append({
                    "id": tid,
                    "name": e.get("name"),
                    "country": e.get("category", {}).get("name"),
                    **si,
                })
        return {"tournaments": out}
    except Exception as ex:
        return {"error": str(ex)}


def ss_standings(tournament_id: str, season_id: str) -> dict:
    """Tabla de posiciones de un torneo."""
    try:
        rows = (_ss(f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total")
                .get("standings", [{}])[0].get("rows", []))
        return {
            "today_utc": _today_utc(),
            "standings": [{
                "pos": r.get("position"),
                "team": r.get("team", {}).get("name"),
                "pj": r.get("matches"),
                "g": r.get("wins"),
                "e": r.get("draws"),
                "p": r.get("losses"),
                "gf": r.get("scoresFor"),
                "gc": r.get("scoresAgainst"),
                "pts": r.get("points"),
            } for r in rows],
        }
    except Exception as ex:
        return {"error": str(ex)}


def ss_player_match_stats(match_id: str, player_name: str) -> dict:
    """Estadísticas individuales de un jugador en un partido específico."""
    try:
        data = _ss(f"/event/{match_id}/lineups")
        for side in ("home", "away"):
            for p in data.get(side, {}).get("players", []):
                pname = p.get("player", {}).get("name", "")
                if player_name.lower() in pname.lower():
                    stats = p.get("statistics", {})
                    return {
                        "player": pname,
                        "team_side": side,
                        "position": p.get("position"),
                        "shirt": p.get("shirtNumber"),
                        "rating": stats.get("rating"),
                        "minutes_played": stats.get("minutesPlayed"),
                        "goals": stats.get("goals"),
                        "assists": stats.get("goalAssist"),
                        "shots": stats.get("totalShot"),
                        "shots_on_target": stats.get("onTargetScoringAttempt"),
                        "key_passes": stats.get("keyPass"),
                        "accurate_passes": stats.get("accuratePass"),
                        "total_passes": stats.get("totalPass"),
                        "dribbles_succeeded": stats.get("successfulDribble"),
                        "tackles": stats.get("totalTackle"),
                        "interceptions": stats.get("interceptionWon"),
                        "yellow_cards": stats.get("yellowCard"),
                        "red_cards": stats.get("redCard"),
                    }
        return {"error": f"Jugador '{player_name}' no encontrado en las alineaciones del partido {match_id}."}
    except Exception as ex:
        return {"error": str(ex)}


def ss_matches_by_date(date_str: str, sport: str = "football") -> dict:
    """
    Partidos de un día específico. date_str formato YYYY-MM-DD.
    Ideal para 'partidos de hoy', 'partidos de mañana', 'partidos del fin de semana'.
    """
    try:
        # SofaScore usa formato YYYY-MM-DD en este endpoint
        evs = _ss(f"/sport/{sport}/scheduled-events/{date_str}").get("events", [])
        return {
            "date_requested": date_str,
            "today_utc": _today_utc(),
            "total": len(evs),
            "matches": [{
                "id": e.get("id"),
                "home": e.get("homeTeam", {}).get("name"),
                "away": e.get("awayTeam", {}).get("name"),
                "home_score": e.get("homeScore", {}).get("current"),
                "away_score": e.get("awayScore", {}).get("current"),
                "status": e.get("status", {}).get("description"),
                "tournament": e.get("tournament", {}).get("name"),
                "country": e.get("tournament", {}).get("category", {}).get("name"),
                "time_utc": _fmt_dt(e.get("startTimestamp")),
            } for e in evs[:60]],
        }
    except Exception as ex:
        return {"error": str(ex)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    {
        "name": "ss_live",
        "description": "Partidos en vivo ahora mismo. Devuelve resultado actual, minuto y torneo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sport": {"type": "string", "description": "Deporte: 'football', 'basketball', 'tennis'. Default: football", "default": "football"}
            },
            "required": [],
        },
    },
    {
        "name": "ss_matches_by_date",
        "description": (
            "Partidos programados en una fecha específica. "
            "Usá esta tool para 'partidos de hoy', 'partidos de mañana', 'partidos del sábado', etc. "
            "Calculá la fecha correcta usando today_utc que ya conocés. "
            "date_str formato: YYYY-MM-DD."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"},
                "sport": {"type": "string", "description": "Deporte. Default: football", "default": "football"},
            },
            "required": ["date_str"],
        },
    },
    {
        "name": "ss_search_team",
        "description": "Buscar equipo por nombre para obtener su ID de SofaScore. Usá PRIMERO antes de pedir partidos o tabla de un equipo.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Nombre del equipo"}},
            "required": ["name"],
        },
    },
    {
        "name": "ss_team_recent",
        "description": "Últimos 10 partidos jugados por un equipo (resultados, fechas, torneos).",
        "input_schema": {
            "type": "object",
            "properties": {"team_id": {"type": "string"}},
            "required": ["team_id"],
        },
    },
    {
        "name": "ss_team_next",
        "description": (
            "Próximos partidos programados de un equipo con fecha y hora en UTC. "
            "Siempre mostrá cuántos días faltan desde hoy (today_utc que ya conocés) hasta cada partido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"team_id": {"type": "string"}},
            "required": ["team_id"],
        },
    },
    {
        "name": "ss_match_data",
        "description": "Datos generales de un partido: equipos, resultado, estado, torneo, fecha/hora, sede.",
        "input_schema": {
            "type": "object",
            "properties": {"match_id": {"type": "string", "description": "Número al final de la URL de SofaScore"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "ss_match_stats",
        "description": "Estadísticas del partido: posesión, tiros, córners, faltas, tarjetas, etc.",
        "input_schema": {
            "type": "object",
            "properties": {"match_id": {"type": "string"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "ss_match_lineups",
        "description": "Alineaciones, formaciones, números de camiseta y calificaciones de jugadores.",
        "input_schema": {
            "type": "object",
            "properties": {"match_id": {"type": "string"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "ss_match_shotmap",
        "description": "Mapa de disparos con xG, minuto, jugador y si fue al arco.",
        "input_schema": {
            "type": "object",
            "properties": {"match_id": {"type": "string"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "ss_match_momentum",
        "description": "Momentum del partido: gráfico de dominio local vs visitante a lo largo del tiempo.",
        "input_schema": {
            "type": "object",
            "properties": {"match_id": {"type": "string"}},
            "required": ["match_id"],
        },
    },
    {
        "name": "ss_player_match_stats",
        "description": "Estadísticas individuales de un jugador en un partido: pases, tiros, duelos, calificación, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string"},
                "player_name": {"type": "string", "description": "Nombre parcial o completo del jugador"},
            },
            "required": ["match_id", "player_name"],
        },
    },
    {
        "name": "ss_search_player",
        "description": "Buscar jugador por nombre. Devuelve ID, equipo actual, posición y nacionalidad.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "ss_search_tournament",
        "description": "Buscar torneo/liga por nombre para obtener su ID y el season_id actual. Necesario para tabla de posiciones.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "ss_standings",
        "description": "Tabla de posiciones de un torneo. Primero usá ss_search_tournament para obtener tournament_id y season_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tournament_id": {"type": "string"},
                "season_id": {"type": "string"},
            },
            "required": ["tournament_id", "season_id"],
        },
    },
]

TOOL_FNS = {
    "ss_live":               lambda i: ss_live(**i),
    "ss_matches_by_date":    lambda i: ss_matches_by_date(**i),
    "ss_search_team":        lambda i: ss_search_team(**i),
    "ss_team_recent":        lambda i: ss_team_recent(**i),
    "ss_team_next":          lambda i: ss_team_next(**i),
    "ss_match_data":         lambda i: ss_match_data(**i),
    "ss_match_stats":        lambda i: ss_match_stats(**i),
    "ss_match_lineups":      lambda i: ss_match_lineups(**i),
    "ss_match_shotmap":      lambda i: ss_match_shotmap(**i),
    "ss_match_momentum":     lambda i: ss_match_momentum(**i),
    "ss_player_match_stats": lambda i: ss_player_match_stats(**i),
    "ss_search_player":      lambda i: ss_search_player(**i),
    "ss_search_tournament":  lambda i: ss_search_tournament(**i),
    "ss_standings":          lambda i: ss_standings(**i),
}

TOOL_LABELS = {
    "ss_live":               "🔴 Partidos en vivo",
    "ss_matches_by_date":    "📅 Partidos por fecha",
    "ss_search_team":        "🔍 Buscando equipo",
    "ss_team_recent":        "📋 Últimos partidos",
    "ss_team_next":          "📅 Próximos partidos",
    "ss_match_data":         "📋 Datos del partido",
    "ss_match_stats":        "📊 Estadísticas",
    "ss_match_lineups":      "👥 Alineaciones",
    "ss_match_shotmap":      "🎯 Mapa de tiros",
    "ss_match_momentum":     "📈 Momentum",
    "ss_player_match_stats": "👤 Stats del jugador",
    "ss_search_player":      "🔍 Buscando jugador",
    "ss_search_tournament":  "🏆 Buscando torneo",
    "ss_standings":          "🏆 Tabla de posiciones",
}


# ══════════════════════════════════════════════════════════════════════════════
# AGENTIC LOOP
# ══════════════════════════════════════════════════════════════════════════════
def build_system_prompt() -> str:
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    weekday = now_utc.strftime("%A")           # Monday, Tuesday, etc.
    weekday_es = {
        "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles",
        "Thursday": "jueves", "Friday": "viernes",
        "Saturday": "sábado", "Sunday": "domingo",
    }.get(weekday, weekday)

    return f"""Sos un asistente experto en fútbol y estadísticas deportivas. Usás la API de SofaScore.

## 📅 FECHA DE HOY
Hoy es **{weekday_es} {today_str} (UTC)**. Usá esta fecha siempre que el usuario mencione "hoy", "mañana", "esta semana", "el fin de semana", "próximos partidos", etc.

Ejemplos de cálculo:
- "hoy" → {today_str}
- "mañana" → calculá {today_str} + 1 día
- "pasado mañana" → calculá {today_str} + 2 días
- "el sábado" → calculá el sábado más cercano desde {today_str}
- "esta semana" → los días {today_str} hasta el domingo de esta semana

Cuando el usuario pregunta por próximos partidos de un equipo (ss_team_next), **siempre calculá y mostrá cuántos días faltan** desde hoy ({today_str}) hasta cada partido.

## 🔧 Estrategia de tools

### Para equipos:
1. Llamá `ss_search_team` para obtener el ID
2. Luego `ss_team_recent` o `ss_team_next` con ese ID

### Para tabla de posiciones:
1. Llamá `ss_search_tournament` para obtener tournament_id y season_id
2. Luego `ss_standings` con esos IDs

### Para partidos por fecha:
- Usá `ss_matches_by_date` con la fecha calculada en formato YYYY-MM-DD
- Para partidos en vivo → `ss_live`

### Para partidos específicos:
- El match_id de SofaScore está al final de la URL: `.../river-boca/12345678` → `"12345678"`

## 📝 Formato de respuesta
- Respondé **siempre en español**, tono amigable y claro
- Usá **tablas markdown** para datos tabulares (tabla de posiciones, estadísticas, alineaciones)
- Para próximos partidos, mostrá: fecha, hora UTC, cuántos días faltan y el torneo
- Si una tool falla con error, explicá el motivo brevemente y sugerí alternativas
- Si el usuario necesita un ID que no tiene, explicale cómo encontrarlo en la URL"""


def run_agent(client: anthropic.Anthropic, messages: list) -> tuple[str, list]:
    tool_calls = []
    system = build_system_prompt()   # rebuilt each call → always has today's date

    for _ in range(12):
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        text = ""
        uses = []
        for b in resp.content:
            if b.type == "text":
                text += b.text
            elif b.type == "tool_use":
                uses.append(b)

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn" or not uses:
            return text, tool_calls

        results = []
        for tu in uses:
            tool_calls.append(tu.name)
            try:
                result = TOOL_FNS[tu.name](tu.input)
            except Exception as e:
                result = {"error": str(e)}
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": results})

    return "Alcancé el límite de iteraciones. Intentá reformular la pregunta.", tool_calls


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚽ Football Chat")
    st.markdown(
        "<span style='color:#57606a;font-size:.85rem'>Powered by SofaScore · Claude AI</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    api_key = st.text_input("🔑 API Key de Anthropic", type="password", placeholder="sk-ant-...")

    st.divider()
    st.markdown("### 💡 Ejemplos")

    EXAMPLES = {
        "🔴 En vivo / por fecha": [
            "¿Qué partidos hay en vivo?",
            "¿Qué partidos hay hoy?",
            "Partidos de mañana",
            "Partidos del sábado",
        ],
        "🏆 Equipos": [
            "Últimos partidos de River Plate",
            "Próximos partidos de Boca Juniors",
            "¿Cuándo juega el próximo partido Barcelona?",
            "Tabla de posiciones de la Premier League",
            "Tabla de la Liga Profesional Argentina",
        ],
        "⚽ Partidos (con ID)": [
            "Estadísticas del partido 12345678",
            "Alineaciones del partido 12345678",
            "Tiros y xG del partido 12345678",
            "Momentum del partido 12345678",
        ],
        "👤 Jugadores": [
            "Buscame info sobre Lautaro Martinez",
            "Stats de Messi en el partido 12345678",
        ],
    }

    for section, exs in EXAMPLES.items():
        with st.expander(section, expanded=False):
            for ex in exs:
                if st.button(ex, key=ex, use_container_width=True):
                    st.session_state.pending_example = ex

    st.divider()
    st.markdown(
        "<div style='font-size:.8rem;color:#57606a;line-height:1.9'>"
        "<b>Match ID de SofaScore:</b><br>"
        "sofascore.com/partido/river-boca/<b>12345678</b>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("# ⚽ Football Chat")
    st.markdown(
        "<span style='color:#57606a'>Resultados · Estadísticas · Tabla de posiciones · Próximos partidos · xG</span>",
        unsafe_allow_html=True,
    )
with c2:
    now = datetime.now(timezone.utc)
    st.markdown(
        f"<div style='text-align:right;margin-top:18px;color:#57606a;font-size:.85rem'>"
        f"📅 Hoy: <b>{now.strftime('%Y-%m-%d')}</b><br>"
        f"🕐 {now.strftime('%H:%M')} UTC</div>",
        unsafe_allow_html=True,
    )
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════
def render_pills(tools_used: list):
    if not tools_used:
        return
    pills = " ".join(
        f'<span class="pill">{TOOL_LABELS.get(t, t)}</span>'
        for t in tools_used
    )
    st.markdown(pills, unsafe_allow_html=True)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("tools_used"):
            render_pills(msg["tools_used"])
        st.markdown(msg["content"])

# handle example button click
prompt = None
if "pending_example" in st.session_state:
    prompt = st.session_state.pop("pending_example")

user_input = st.chat_input("Preguntá sobre partidos, equipos, estadísticas…")
if user_input:
    prompt = user_input

if prompt:
    if not api_key:
        st.warning("⚠️ Ingresá tu API Key de Anthropic en el panel izquierdo.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.api_messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Consultando SofaScore…"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                msgs = list(st.session_state.api_messages)
                answer, tools_used = run_agent(client, msgs)
                st.session_state.api_messages = msgs

                render_pills(tools_used)
                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "tools_used": tools_used,
                })
            except anthropic.AuthenticationError:
                st.error("❌ API Key inválida. Verificá que sea correcta.")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")
