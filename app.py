import streamlit as st
import anthropic
import json
import requests
from datetime import datetime
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Football Chat ⚽",
    page_icon="⚽",
    layout="wide",
)

st.markdown("""
<style>
  .stApp { background: #0d1117; color: #e6edf3; }
  section[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
  section[data-testid="stSidebar"] * { color: #e6edf3 !important; }
  .stChatMessage { background: #161b22; border-radius: 12px; border: 1px solid #21262d; margin-bottom: .5rem; }
  .stChatMessage[data-testid="stChatMessage-user"] { background: #1c2d3f; border-color: #1f6feb; }
  .stChatInput textarea { background: #161b22 !important; color: #e6edf3 !important; border: 1px solid #30363d !important; border-radius: 8px !important; }
  .stChatInput > div { background: #161b22 !important; border: 1px solid #30363d !important; border-radius: 10px !important; }
  .source-pill-sofa  { display:inline-block; background:#0d2137; color:#58a6ff; border:1px solid #1f6feb; border-radius:20px; padding:2px 10px; font-size:.72rem; margin:1px; }
  .source-pill-data  { display:inline-block; background:#1a1f0d; color:#7ee787; border:1px solid #3fb950; border-radius:20px; padding:2px 10px; font-size:.72rem; margin:1px; }
  .source-pill-other { display:inline-block; background:#2d1f0d; color:#f0883e; border:1px solid #d29922; border-radius:20px; padding:2px 10px; font-size:.72rem; margin:1px; }
  h1,h2,h3 { color: #58a6ff !important; }
  .stButton>button { background:#21262d; color:#e6edf3; border:1px solid #30363d; border-radius:6px; font-size:.8rem; padding:4px 10px; }
  .stButton>button:hover { background:#30363d; border-color:#58a6ff; }
  .stTextInput input { background:#161b22 !important; color:#e6edf3 !important; border:1px solid #30363d !important; }
  div[data-testid="stMarkdownContainer"] p { line-height: 1.7; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SOFASCORE API
# ══════════════════════════════════════════════════════════════════════════════
SS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
SS_BASE = "https://api.sofascore.com/api/v1"

def ss_get(path):
    r = requests.get(f"{SS_BASE}{path}", headers=SS_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def ss_match_data(match_id):
    try:
        ev = ss_get(f"/event/{match_id}").get("event", {})
        return {
            "home_team": ev.get("homeTeam", {}).get("name"),
            "away_team": ev.get("awayTeam", {}).get("name"),
            "home_score": ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("awayScore", {}).get("current"),
            "status": ev.get("status", {}).get("description"),
            "tournament": ev.get("tournament", {}).get("name"),
            "country": ev.get("tournament", {}).get("category", {}).get("name"),
            "start_time": datetime.utcfromtimestamp(ev["startTimestamp"]).strftime("%Y-%m-%d %H:%M UTC") if ev.get("startTimestamp") else None,
            "winner_code": ev.get("winnerCode"),
            "venue": ev.get("venue", {}).get("name") if ev.get("venue") else None,
        }
    except Exception as e:
        return {"error": str(e)}

def ss_match_shotmap(match_id):
    try:
        shots = ss_get(f"/event/{match_id}/shotmap").get("shotmap", [])
        rows = [{
            "player": s.get("player", {}).get("name"),
            "team": "home" if s.get("isHome") else "away",
            "minute": s.get("time"),
            "added_time": s.get("addedTime"),
            "shot_type": s.get("shotType"),
            "situation": s.get("situation"),
            "goal_mouth": s.get("goalMouthLocation"),
            "xG": round(s.get("xg", 0), 3) if s.get("xg") else None,
            "on_target": s.get("isOnTarget"),
            "blocked": s.get("isBlocked"),
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
    except Exception as e:
        return {"error": str(e)}

def ss_match_lineups(match_id):
    try:
        data = ss_get(f"/event/{match_id}/lineups")
        result = {}
        for side in ("home", "away"):
            td = data.get(side, {})
            result[side] = {
                "formation": td.get("formation"),
                "players": [{
                    "name": p.get("player", {}).get("name"),
                    "position": p.get("position"),
                    "shirt": p.get("shirtNumber"),
                    "substitute": p.get("substitute", False),
                    "rating": p.get("statistics", {}).get("rating"),
                    "goals": p.get("statistics", {}).get("goals"),
                    "assists": p.get("statistics", {}).get("goalAssist"),
                    "yellow_cards": p.get("statistics", {}).get("yellowCards"),
                    "red_cards": p.get("statistics", {}).get("redCards"),
                } for p in td.get("players", [])],
            }
        return result
    except Exception as e:
        return {"error": str(e)}

def ss_match_statistics(match_id):
    try:
        groups = ss_get(f"/event/{match_id}/statistics").get("statistics", [])
        rows = []
        for g in groups:
            for item in g.get("groups", []):
                for s in item.get("statisticsItems", []):
                    rows.append({"stat": s.get("name"), "home": s.get("home"), "away": s.get("away")})
        return {"statistics": rows}
    except Exception as e:
        return {"error": str(e)}

def ss_search_team(team_name):
    try:
        results = ss_get(f"/search/all?q={requests.utils.quote(team_name)}&type=team").get("results", [])
        return {"teams": [{
            "id": r["entity"].get("id"),
            "name": r["entity"].get("name"),
            "country": r["entity"].get("country", {}).get("name"),
            "sport": r["entity"].get("sport", {}).get("name"),
        } for r in results[:6] if r.get("type") == "team"]}
    except Exception as e:
        return {"error": str(e)}

def ss_team_recent(team_id):
    try:
        events = ss_get(f"/team/{team_id}/events/last/0").get("events", [])[-10:]
        return {"matches": [{
            "id": ev.get("id"),
            "home": ev.get("homeTeam", {}).get("name"),
            "away": ev.get("awayTeam", {}).get("name"),
            "home_score": ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("awayScore", {}).get("current"),
            "status": ev.get("status", {}).get("description"),
            "tournament": ev.get("tournament", {}).get("name"),
            "date": datetime.utcfromtimestamp(ev["startTimestamp"]).strftime("%Y-%m-%d") if ev.get("startTimestamp") else None,
        } for ev in events]}
    except Exception as e:
        return {"error": str(e)}

def ss_team_next(team_id):
    try:
        events = ss_get(f"/team/{team_id}/events/next/0").get("events", [])[:5]
        return {"next_matches": [{
            "id": ev.get("id"),
            "home": ev.get("homeTeam", {}).get("name"),
            "away": ev.get("awayTeam", {}).get("name"),
            "tournament": ev.get("tournament", {}).get("name"),
            "date": datetime.utcfromtimestamp(ev["startTimestamp"]).strftime("%Y-%m-%d %H:%M UTC") if ev.get("startTimestamp") else None,
        } for ev in events]}
    except Exception as e:
        return {"error": str(e)}

def ss_search_player(player_name):
    try:
        results = ss_get(f"/search/all?q={requests.utils.quote(player_name)}&type=player").get("results", [])
        return {"players": [{
            "id": r["entity"].get("id"),
            "name": r["entity"].get("name"),
            "team": r["entity"].get("team", {}).get("name") if r["entity"].get("team") else None,
            "position": r["entity"].get("position"),
            "nationality": r["entity"].get("country", {}).get("name"),
        } for r in results[:5] if r.get("type") == "player"]}
    except Exception as e:
        return {"error": str(e)}

def ss_live_matches(sport="football"):
    try:
        events = ss_get(f"/sport/{sport}/events/live").get("events", [])[:25]
        return {"live_matches": [{
            "id": ev.get("id"),
            "home": ev.get("homeTeam", {}).get("name"),
            "away": ev.get("awayTeam", {}).get("name"),
            "home_score": ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("awayScore", {}).get("current"),
            "minute": ev.get("time", {}).get("played"),
            "status": ev.get("status", {}).get("description"),
            "tournament": ev.get("tournament", {}).get("name"),
            "country": ev.get("tournament", {}).get("category", {}).get("name"),
        } for ev in events], "count": len(events)}
    except Exception as e:
        return {"error": str(e)}

def ss_match_momentum(match_id):
    try:
        points = ss_get(f"/event/{match_id}/graph").get("graphPoints", [])
        if not points:
            return {"error": "No hay datos de momentum para este partido"}
        home_dom = len([p for p in points if p.get("value", 0) > 0])
        away_dom = len([p for p in points if p.get("value", 0) < 0])
        return {"total_points": len(points), "home_dominant_periods": home_dom, "away_dominant_periods": away_dom, "momentum_timeline": points[:30]}
    except Exception as e:
        return {"error": str(e)}

def ss_player_match_heatmap(match_id, player_name):
    try:
        lineup_data = ss_get(f"/event/{match_id}/lineups")
        player_id = None
        for side in ("home", "away"):
            for p in lineup_data.get(side, {}).get("players", []):
                name = p.get("player", {}).get("name", "")
                if player_name.lower() in name.lower():
                    player_id = p.get("player", {}).get("id")
                    break
            if player_id:
                break
        if not player_id:
            return {"error": f"Jugador '{player_name}' no encontrado en las alineaciones del partido {match_id}"}
        heatmap = ss_get(f"/event/{match_id}/player/{player_id}/heatmap").get("heatmap", [])
        return {"player": player_name, "player_id": player_id, "total_heat_points": len(heatmap), "sample_coordinates": heatmap[:20]}
    except Exception as e:
        return {"error": str(e)}

def ss_search_tournament(tournament_name):
    try:
        results = ss_get(f"/search/all?q={requests.utils.quote(tournament_name)}&type=uniqueTournament").get("results", [])
        tournaments = []
        for r in results[:5]:
            if r.get("type") == "uniqueTournament":
                e = r.get("entity", {})
                tid = e.get("id")
                season_info = {}
                try:
                    seasons = ss_get(f"/unique-tournament/{tid}/seasons")
                    current = seasons.get("seasons", [{}])[0]
                    season_info = {"season_id": current.get("id"), "season_name": current.get("name")}
                except Exception:
                    pass
                tournaments.append({"id": tid, "name": e.get("name"), "country": e.get("category", {}).get("name"), **season_info})
        return {"tournaments": tournaments}
    except Exception as e:
        return {"error": str(e)}

def ss_team_standings(tournament_id, season_id):
    try:
        data = ss_get(f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total")
        rows_raw = data.get("standings", [{}])[0].get("rows", [])
        return {"standings": [{
            "position": r.get("position"),
            "team": r.get("team", {}).get("name"),
            "played": r.get("matches"),
            "wins": r.get("wins"),
            "draws": r.get("draws"),
            "losses": r.get("losses"),
            "goals_for": r.get("scoresFor"),
            "goals_against": r.get("scoresAgainst"),
            "points": r.get("points"),
        } for r in rows_raw]}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# DATAFACTORY API
# ══════════════════════════════════════════════════════════════════════════════
DF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://panorama.datafactory.la/",
}

DF_LEAGUES = {
    "Liga Profesional Argentina":       "torneo-betsson-2024",
    "Copa de la Liga Argentina":        "copa-de-la-liga-profesional-2024",
    "Primera Nacional Argentina":       "primera-nacional-2024",
    "Copa Argentina":                   "copa-argentina-2024",
    "Primera División Uruguay":         "campeonato-uruguayo-2024",
    "Primera División Chile":           "primera-division-2024",
    "División Profesional Paraguay":    "division-profesional-2024",
    "División Profesional Bolivia":     "division-profesional-boliviana-2024",
    "Liga BetPlay Colombia":            "liga-betplay-dimayor-2024",
    "LigaPro Ecuador":                  "ligapro-serie-a-2024",
    "Liga 1 Perú":                      "liga-1-2024",
    "Liga FUTVE Venezuela":             "liga-futve-2024",
    "Copa Libertadores":                "copa-libertadores-2024",
    "Copa Sudamericana":                "copa-sudamericana-2024",
}

DF_INCIDENCES = [
    "goals", "substitutions", "clearances", "cornerKicks",
    "correctPasses", "fouls", "incorrectPasses", "offsides",
    "redCards", "shots", "stealings", "yellowCards",
    "throwIn", "goalkick", "penaltyShootout", "var",
]

def df_get(league_slug, match_id):
    url = (f"https://panorama.datafactory.la/html/v3/htmlCenter/data/"
           f"deportes/futbol/{league_slug}/events/{match_id}.json?t=172730124")
    r = requests.get(url, headers=DF_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def _df_get_name(players, pid):
    pid = str(int(pid)) if pid else None
    if not pid:
        return None
    n = players.get(pid, {}).get("name", {})
    return f"{n.get('first','')} {n.get('last','')}".strip() or pid

def df_available_leagues():
    return {"available_leagues": list(DF_LEAGUES.keys()),
            "note": "Para consultar un partido necesitás su ID de DataFactory (distinto al de SofaScore)."}

def df_match_summary(league, match_id):
    if league not in DF_LEAGUES:
        return {"error": f"Liga '{league}' no disponible.", "available_leagues": list(DF_LEAGUES.keys())}
    try:
        data = df_get(DF_LEAGUES[league], match_id)
        mi = data.get("match", {})
        home = mi.get("homeTeamName", "Local")
        away = mi.get("awayTeamName", "Visitante")
        home_id = mi.get("homeTeamId")
        players = data.get("players", {})
        incidences = data.get("incidences", {})

        def parse_events(inc_type):
            evs = incidences.get(inc_type, {})
            rows = []
            for _, ev in evs.items():
                t = ev.get("t", {})
                rows.append({
                    "type": inc_type,
                    "team": home if ev.get("team") == home_id else away,
                    "minute": t.get("m"), "half": t.get("half"),
                    "player": _df_get_name(players, ev.get("plyrId")),
                    "player2": _df_get_name(players, ev.get("recvId")) if ev.get("recvId") else None,
                })
            return sorted(rows, key=lambda r: (r.get("half") or 0, r.get("minute") or 0))

        return {
            "league": league, "match_id": match_id,
            "home_team": home, "away_team": away,
            "home_score": mi.get("homeTeamScore"),
            "away_score": mi.get("awayTeamScore"),
            "status": mi.get("status"),
            "goals": parse_events("goals"),
            "yellow_cards": parse_events("yellowCards"),
            "red_cards": parse_events("redCards"),
            "substitutions": parse_events("substitutions"),
            "var_reviews": parse_events("var"),
        }
    except requests.HTTPError as e:
        return {"error": f"Partido no encontrado en DataFactory ({e}). Verificá el ID y la liga."}
    except Exception as e:
        return {"error": str(e)}

def df_match_events(league, match_id, incidence):
    if league not in DF_LEAGUES:
        return {"error": f"Liga '{league}' no disponible.", "available_leagues": list(DF_LEAGUES.keys())}
    if incidence not in DF_INCIDENCES:
        return {"error": f"Incidencia '{incidence}' no válida.", "valid_options": DF_INCIDENCES}
    try:
        data = df_get(DF_LEAGUES[league], match_id)
        mi = data.get("match", {})
        home = mi.get("homeTeamName", "Local")
        away = mi.get("awayTeamName", "Visitante")
        home_id = mi.get("homeTeamId")
        players = data.get("players", {})
        rows = []
        for _, ev in data.get("incidences", {}).get(incidence, {}).items():
            t = ev.get("t", {})
            row = {
                "team": home if ev.get("team") == home_id else away,
                "side": "home" if ev.get("team") == home_id else "away",
                "half": t.get("half"), "minute": t.get("m"), "second": t.get("s"),
                "player": _df_get_name(players, ev.get("plyrId")),
                "player_recv": _df_get_name(players, ev.get("recvId")) if ev.get("recvId") else None,
            }
            coord = ev.get("coord", {})
            if coord:
                c1 = coord.get("1", {}); c2 = coord.get("2", {})
                if c1:
                    row["x"] = round((c1.get("x", 0) + 1) * 50, 1)
                    row["y"] = round((c1.get("y", 0) + 1) * 50, 1)
                if c2:
                    row["end_x"] = round((c2.get("x", 0) + 1) * 50, 1)
                    row["end_y"] = round((c2.get("y", 0) + 1) * 50, 1)
            rows.append(row)
        rows.sort(key=lambda r: (r.get("half") or 0, r.get("minute") or 0, r.get("second") or 0))
        return {"league": league, "home_team": home, "away_team": away,
                "incidence": incidence, "total_events": len(rows), "events": rows}
    except requests.HTTPError as e:
        return {"error": f"Partido no encontrado ({e}). Verificá el ID y la liga."}
    except Exception as e:
        return {"error": str(e)}

def df_match_passes(league, match_id, only_completed=True):
    if league not in DF_LEAGUES:
        return {"error": f"Liga '{league}' no disponible.", "available_leagues": list(DF_LEAGUES.keys())}
    try:
        data = df_get(DF_LEAGUES[league], match_id)
        mi = data.get("match", {})
        home = mi.get("homeTeamName", "Local")
        away = mi.get("awayTeamName", "Visitante")
        home_id = mi.get("homeTeamId")
        players = data.get("players", {})
        keys = ["correctPasses"] if only_completed else ["correctPasses", "incorrectPasses"]
        rows = []
        for key in keys:
            for _, ev in data.get("incidences", {}).get(key, {}).items():
                t = ev.get("t", {})
                rows.append({
                    "completed": key == "correctPasses",
                    "team": home if ev.get("team") == home_id else away,
                    "minute": t.get("m"), "half": t.get("half"),
                    "passer": _df_get_name(players, ev.get("plyrId")),
                    "receiver": _df_get_name(players, ev.get("recvId")) if ev.get("recvId") else None,
                })
        home_p = [r for r in rows if r["team"] == home]
        away_p = [r for r in rows if r["team"] == away]
        return {
            "league": league, "home_team": home, "away_team": away,
            "total_passes": len(rows), "home_passes": len(home_p), "away_passes": len(away_p),
            "passes": rows[:100],
        }
    except requests.HTTPError as e:
        return {"error": f"Partido no encontrado ({e})."}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    # SofaScore
    {"name": "ss_live_matches", "description": "SofaScore: Partidos en vivo ahora mismo con resultado, minuto y torneo.",
     "input_schema": {"type": "object", "properties": {"sport": {"type": "string", "description": "Deporte: 'football', 'basketball', 'tennis', etc.", "default": "football"}}, "required": []}},
    {"name": "ss_search_team", "description": "SofaScore: Buscar equipo por nombre para obtener su ID. Usá PRIMERO antes de pedir partidos.",
     "input_schema": {"type": "object", "properties": {"team_name": {"type": "string"}}, "required": ["team_name"]}},
    {"name": "ss_team_recent", "description": "SofaScore: Últimos 10 partidos de un equipo (resultados, fechas, torneos).",
     "input_schema": {"type": "object", "properties": {"team_id": {"type": "string"}}, "required": ["team_id"]}},
    {"name": "ss_team_next", "description": "SofaScore: Próximos 5 partidos programados de un equipo.",
     "input_schema": {"type": "object", "properties": {"team_id": {"type": "string"}}, "required": ["team_id"]}},
    {"name": "ss_match_data", "description": "SofaScore: Datos generales de un partido: equipos, resultado, estado, torneo, sede.",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string", "description": "Número al final de la URL de SofaScore"}}, "required": ["match_id"]}},
    {"name": "ss_match_statistics", "description": "SofaScore: Estadísticas del partido: posesión, tiros, córners, faltas, tarjetas.",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string"}}, "required": ["match_id"]}},
    {"name": "ss_match_lineups", "description": "SofaScore: Alineaciones, formaciones, números y calificaciones.",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string"}}, "required": ["match_id"]}},
    {"name": "ss_match_shotmap", "description": "SofaScore: Mapa de disparos con xG, minuto, jugador y tipo de tiro.",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string"}}, "required": ["match_id"]}},
    {"name": "ss_match_momentum", "description": "SofaScore: Momentum del partido (dominio local vs visitante en el tiempo).",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string"}}, "required": ["match_id"]}},
    {"name": "ss_search_player", "description": "SofaScore: Buscar jugador por nombre. Devuelve ID, equipo, posición y nacionalidad.",
     "input_schema": {"type": "object", "properties": {"player_name": {"type": "string"}}, "required": ["player_name"]}},
    {"name": "ss_player_match_heatmap", "description": "SofaScore: Heatmap de un jugador en un partido específico.",
     "input_schema": {"type": "object", "properties": {"match_id": {"type": "string"}, "player_name": {"type": "string"}}, "required": ["match_id", "player_name"]}},
    {"name": "ss_search_tournament", "description": "SofaScore: Buscar torneo/liga por nombre para obtener su ID y el de la temporada actual. Necesario para tabla de posiciones.",
     "input_schema": {"type": "object", "properties": {"tournament_name": {"type": "string"}}, "required": ["tournament_name"]}},
    {"name": "ss_team_standings", "description": "SofaScore: Tabla de posiciones de un torneo. Primero usá ss_search_tournament para obtener los IDs.",
     "input_schema": {"type": "object", "properties": {"tournament_id": {"type": "string"}, "season_id": {"type": "string"}}, "required": ["tournament_id", "season_id"]}},
    # DataFactory
    {"name": "df_available_leagues", "description": "DataFactory: Lista todas las ligas LATAM disponibles con nombres exactos para usar en otras tools df_.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "df_match_summary", "description": "DataFactory: Resumen de partido LATAM: goles, tarjetas, sustituciones y VAR con minutos y jugadores. El match_id es el ID de DataFactory (distinto al de SofaScore).",
     "input_schema": {"type": "object", "properties": {"league": {"type": "string", "description": "Nombre exacto de la liga (usar df_available_leagues para ver opciones)"}, "match_id": {"type": "string"}}, "required": ["league", "match_id"]}},
    {"name": "df_match_events", "description": "DataFactory: Eventos específicos de un partido LATAM con coordenadas (tiros, pases, faltas, córners, etc.).",
     "input_schema": {"type": "object", "properties": {
         "league": {"type": "string"},
         "match_id": {"type": "string"},
         "incidence": {"type": "string", "enum": DF_INCIDENCES},
     }, "required": ["league", "match_id", "incidence"]}},
    {"name": "df_match_passes", "description": "DataFactory: Pases de un partido LATAM con pasador, receptor, minuto y equipo.",
     "input_schema": {"type": "object", "properties": {
         "league": {"type": "string"},
         "match_id": {"type": "string"},
         "only_completed": {"type": "boolean", "default": True},
     }, "required": ["league", "match_id"]}},
]

TOOL_FNS = {
    "ss_live_matches":         lambda i: ss_live_matches(**i),
    "ss_search_team":          lambda i: ss_search_team(**i),
    "ss_team_recent":          lambda i: ss_team_recent(**i),
    "ss_team_next":            lambda i: ss_team_next(**i),
    "ss_match_data":           lambda i: ss_match_data(**i),
    "ss_match_statistics":     lambda i: ss_match_statistics(**i),
    "ss_match_lineups":        lambda i: ss_match_lineups(**i),
    "ss_match_shotmap":        lambda i: ss_match_shotmap(**i),
    "ss_match_momentum":       lambda i: ss_match_momentum(**i),
    "ss_search_player":        lambda i: ss_search_player(**i),
    "ss_player_match_heatmap": lambda i: ss_player_match_heatmap(**i),
    "ss_search_tournament":    lambda i: ss_search_tournament(**i),
    "ss_team_standings":       lambda i: ss_team_standings(**i),
    "df_available_leagues":    lambda i: df_available_leagues(),
    "df_match_summary":        lambda i: df_match_summary(**i),
    "df_match_events":         lambda i: df_match_events(**i),
    "df_match_passes":         lambda i: df_match_passes(**i),
}

TOOL_META = {
    "ss_live_matches":         ("sofa", "🔴 Partidos en vivo"),
    "ss_search_team":          ("sofa", "🔍 Buscando equipo"),
    "ss_team_recent":          ("sofa", "📅 Últimos partidos"),
    "ss_team_next":            ("sofa", "📅 Próximos partidos"),
    "ss_match_data":           ("sofa", "📋 Datos del partido"),
    "ss_match_statistics":     ("sofa", "📊 Estadísticas"),
    "ss_match_lineups":        ("sofa", "👥 Alineaciones"),
    "ss_match_shotmap":        ("sofa", "🎯 Mapa de disparos"),
    "ss_match_momentum":       ("sofa", "📈 Momentum"),
    "ss_search_player":        ("sofa", "🔍 Buscando jugador"),
    "ss_player_match_heatmap": ("sofa", "🔥 Heatmap del jugador"),
    "ss_search_tournament":    ("sofa", "🏆 Buscando torneo"),
    "ss_team_standings":       ("sofa", "🏆 Tabla de posiciones"),
    "df_available_leagues":    ("data", "📋 Ligas disponibles"),
    "df_match_summary":        ("data", "📋 Resumen del partido"),
    "df_match_events":         ("data", "⚡ Eventos con coordenadas"),
    "df_match_passes":         ("data", "🔄 Pases del partido"),
}


# ══════════════════════════════════════════════════════════════════════════════
# AGENTIC LOOP
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Sos un asistente experto en fútbol y estadísticas deportivas con acceso a dos fuentes de datos:

**SofaScore** (tools con prefijo ss_): cobertura global, partidos en vivo, estadísticas, alineaciones, tabla de posiciones, heatmaps, xG.
**DataFactory** (tools con prefijo df_): ligas latinoamericanas, eventos detallados con coordenadas (tiros, pases, faltas, córners, VAR, etc.).

## Estrategia

### SofaScore:
- Para equipos o jugadores → buscá el ID con ss_search_team / ss_search_player primero, luego usás ese ID.
- Para tabla de posiciones → ss_search_tournament primero (obtenés tournament_id + season_id), luego ss_team_standings.
- El match_id de SofaScore = número al final de la URL: `.../partido/river-boca/12345678` → `"12345678"`.

### DataFactory:
- Siempre llamá df_available_leagues si el usuario no especificó la liga con nombre exacto.
- El match_id de DataFactory es **distinto** al de SofaScore. Si el usuario no lo sabe, pedíselo.
- Usá DataFactory para análisis profundos de partidos LATAM: eventos por jugador, coordenadas, pases, etc.
- Cuando el usuario quiere analizar un partido LATAM, podés combinar SofaScore (estadísticas generales) + DataFactory (eventos detallados) para dar una respuesta completa.

## Presentación
- Respondé siempre en español, con tono claro y amigable.
- Usá tablas markdown para datos tabulares (tabla de posiciones, alineaciones, estadísticas, tiros).
- Indicá siempre la fuente (📘 SofaScore / 📗 DataFactory) al presentar datos.
- Si una tool falla, explicá el motivo y sugerí alternativas.
- Si el usuario pregunta algo fuera del alcance disponible, decíselo con claridad."""

def run_agent(client, messages):
    tool_calls_made = []
    for _ in range(12):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        assistant_text = ""
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                assistant_text += block.text
            elif block.type == "tool_use":
                tool_uses.append(block)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn" or not tool_uses:
            return assistant_text, tool_calls_made

        tool_results = []
        for tu in tool_uses:
            tool_calls_made.append(tu.name)
            try:
                result = TOOL_FNS[tu.name](tu.input)
            except Exception as e:
                result = {"error": str(e)}
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(result, ensure_ascii=False)})
        messages.append({"role": "user", "content": tool_results})

    return "Alcancé el límite de iteraciones. Intentá reformular la pregunta.", tool_calls_made


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚽ Football Chat")
    st.markdown("<small style='color:#8b949e'>SofaScore · DataFactory · Claude AI</small>", unsafe_allow_html=True)
    st.divider()

    api_key = st.text_input("🔑 API Key de Anthropic", type="password", placeholder="sk-ant-...")

    st.divider()
    st.markdown("### 💡 Ejemplos de consultas")

    EXAMPLES = {
        "🔴 En vivo": [
            "¿Qué partidos hay en vivo?",
            "Partidos en vivo de basketball",
        ],
        "🏆 Equipos y torneos": [
            "Últimos partidos de River Plate",
            "Próximos partidos de Boca Juniors",
            "Tabla de la Liga Profesional Argentina",
            "Tabla de la Premier League",
        ],
        "⚽ Partidos (SofaScore ID)": [
            "Estadísticas del partido 12345678",
            "Alineaciones del partido 12345678",
            "Disparos y xG del partido 12345678",
            "Momentum del partido 12345678",
        ],
        "📊 DataFactory (LATAM)": [
            "¿Qué ligas tiene DataFactory?",
            "Resumen del partido 98765 de Copa Libertadores",
            "Goles del partido 98765 de Liga Profesional Argentina",
            "Tiros del partido 98765 de Liga BetPlay Colombia",
        ],
        "👤 Jugadores": [
            "Buscame info sobre Messi",
            "Heatmap de Álvarez en el partido 12345678",
        ],
    }

    for section, examples in EXAMPLES.items():
        with st.expander(section, expanded=False):
            for ex in examples:
                if st.button(ex, key=ex, use_container_width=True):
                    st.session_state.pending_example = ex

    st.divider()
    st.markdown("""<small>
<b>Fuentes:</b><br>
<span class='source-pill-sofa'>SofaScore</span> cobertura global<br>
<span class='source-pill-data'>DataFactory</span> ligas LATAM<br><br>
<b>IDs de SofaScore:</b> número al final de la URL del partido.<br>
<b>IDs de DataFactory:</b> sistema separado — pedíselo al usuario si no lo sabe.
</small>""", unsafe_allow_html=True)
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
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("# ⚽ Football Chat")
    st.markdown("<span style='color:#8b949e'>Resultados · Estadísticas · Eventos · Tabla de posiciones · Ligas LATAM</span>", unsafe_allow_html=True)
with col2:
    st.markdown("""<div style='text-align:right;margin-top:14px'>
<span class='source-pill-sofa'>📘 SofaScore</span><br>
<span class='source-pill-data'>📗 DataFactory</span>
</div>""", unsafe_allow_html=True)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════
def render_tool_pills(tools_used):
    if not tools_used:
        return
    pills = []
    for t in tools_used:
        source, label = TOOL_META.get(t, ("other", t))
        pills.append(f'<span class="source-pill-{source}">{label}</span>')
    st.markdown(" ".join(pills), unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("tools_used"):
            render_tool_pills(msg["tools_used"])
        st.markdown(msg["content"])

# handle example button
prompt = None
if "pending_example" in st.session_state:
    prompt = st.session_state.pop("pending_example")

user_input = st.chat_input("Preguntá sobre partidos, equipos, estadísticas, ligas LATAM…")
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
        with st.spinner("Consultando…"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                api_msgs = list(st.session_state.api_messages)
                answer, tools_used = run_agent(client, api_msgs)
                st.session_state.api_messages = api_msgs

                render_tool_pills(tools_used)
                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant", "content": answer, "tools_used": tools_used,
                })
            except anthropic.AuthenticationError:
                st.error("❌ API Key inválida. Verificá que sea correcta.")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")
