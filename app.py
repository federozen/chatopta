import streamlit as st
import anthropic
import json
import requests
from datetime import datetime

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
  }
  section[data-testid="stSidebar"] .stButton>button:hover {
    background:#eaeef2; border-color:#0969da;
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

  /* ── source pills ── */
  .pill-sofa {
    display:inline-block; background:#dbeafe; color:#1d4ed8;
    border:1px solid #93c5fd; border-radius:20px;
    padding:2px 10px; font-size:.72rem; margin:2px;
    font-weight:600;
  }
  .pill-fotmob {
    display:inline-block; background:#dcfce7; color:#15803d;
    border:1px solid #86efac; border-radius:20px;
    padding:2px 10px; font-size:.72rem; margin:2px;
    font-weight:600;
  }

  /* ── headings & divider ── */
  h1 { color:#0969da !important; }
  h2,h3 { color:#1f2328 !important; }
  hr { border-color:#d1d9e0; }

  /* ── expander ── */
  details summary { color:#1f2328 !important; font-weight:600; }

  /* ── tables ── */
  table { border-collapse:collapse; width:100%; font-size:.85rem; }
  th { background:#f6f8fa; color:#1f2328; padding:6px 10px; border:1px solid #d1d9e0; }
  td { padding:5px 10px; border:1px solid #d1d9e0; color:#1f2328; }
  tr:nth-child(even) td { background:#f6f8fa; }

  /* ── api key input ── */
  .stTextInput input {
    background:#ffffff !important;
    color:#1f2328 !important;
    border:1px solid #d1d9e0 !important;
  }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SOFASCORE  — api pública directa
# ══════════════════════════════════════════════════════════════════════════════
_SS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
SS = "https://api.sofascore.com/api/v1"

def _ss(path):
    r = requests.get(f"{SS}{path}", headers=_SS, timeout=15)
    r.raise_for_status()
    return r.json()

def _ts(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC") if ts else None

def _date(ts):
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else None

# ─ tools ─────────────────────────────────────────────────────────────────────

def ss_live(sport="football"):
    try:
        evs = _ss(f"/sport/{sport}/events/live").get("events", [])[:25]
        return {"live": [{
            "id": e.get("id"),
            "home": e.get("homeTeam",{}).get("name"),
            "away": e.get("awayTeam",{}).get("name"),
            "home_score": e.get("homeScore",{}).get("current"),
            "away_score": e.get("awayScore",{}).get("current"),
            "minute": e.get("time",{}).get("played"),
            "status": e.get("status",{}).get("description"),
            "tournament": e.get("tournament",{}).get("name"),
            "country": e.get("tournament",{}).get("category",{}).get("name"),
        } for e in evs], "count": len(evs)}
    except Exception as ex:
        return {"error": str(ex)}

def ss_search_team(name):
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=team").get("results",[])
        return {"teams": [{"id":r["entity"].get("id"),"name":r["entity"].get("name"),
                           "country":r["entity"].get("country",{}).get("name"),
                           "sport":r["entity"].get("sport",{}).get("name")}
                          for r in rs[:6] if r.get("type")=="team"]}
    except Exception as ex:
        return {"error": str(ex)}

def ss_team_recent(team_id):
    try:
        evs = _ss(f"/team/{team_id}/events/last/0").get("events",[])[-10:]
        return {"matches": [{"id":e.get("id"),
            "home":e.get("homeTeam",{}).get("name"),
            "away":e.get("awayTeam",{}).get("name"),
            "home_score":e.get("homeScore",{}).get("current"),
            "away_score":e.get("awayScore",{}).get("current"),
            "status":e.get("status",{}).get("description"),
            "tournament":e.get("tournament",{}).get("name"),
            "date":_date(e.get("startTimestamp"))} for e in evs]}
    except Exception as ex:
        return {"error": str(ex)}

def ss_team_next(team_id):
    try:
        evs = _ss(f"/team/{team_id}/events/next/0").get("events",[])[:5]
        return {"next": [{"id":e.get("id"),
            "home":e.get("homeTeam",{}).get("name"),
            "away":e.get("awayTeam",{}).get("name"),
            "tournament":e.get("tournament",{}).get("name"),
            "date":_ts(e.get("startTimestamp"))} for e in evs]}
    except Exception as ex:
        return {"error": str(ex)}

def ss_match_data(match_id):
    try:
        ev = _ss(f"/event/{match_id}").get("event",{})
        return {
            "home": ev.get("homeTeam",{}).get("name"),
            "away": ev.get("awayTeam",{}).get("name"),
            "home_score": ev.get("homeScore",{}).get("current"),
            "away_score": ev.get("awayScore",{}).get("current"),
            "status": ev.get("status",{}).get("description"),
            "tournament": ev.get("tournament",{}).get("name"),
            "country": ev.get("tournament",{}).get("category",{}).get("name"),
            "date": _ts(ev.get("startTimestamp")),
            "venue": ev.get("venue",{}).get("name") if ev.get("venue") else None,
        }
    except Exception as ex:
        return {"error": str(ex)}

def ss_match_stats(match_id):
    try:
        gs = _ss(f"/event/{match_id}/statistics").get("statistics",[])
        rows = []
        for g in gs:
            for item in g.get("groups",[]):
                for s in item.get("statisticsItems",[]):
                    rows.append({"stat":s.get("name"),"home":s.get("home"),"away":s.get("away")})
        return {"statistics": rows}
    except Exception as ex:
        return {"error": str(ex)}

def ss_match_lineups(match_id):
    try:
        data = _ss(f"/event/{match_id}/lineups")
        out = {}
        for side in ("home","away"):
            td = data.get(side,{})
            out[side] = {"formation": td.get("formation"),
                "players": [{"name":p.get("player",{}).get("name"),
                    "position":p.get("position"),"shirt":p.get("shirtNumber"),
                    "sub":p.get("substitute",False),
                    "rating":p.get("statistics",{}).get("rating"),
                    "goals":p.get("statistics",{}).get("goals"),
                    "assists":p.get("statistics",{}).get("goalAssist"),
                    "yellow":p.get("statistics",{}).get("yellowCards"),
                    "red":p.get("statistics",{}).get("redCards")}
                   for p in td.get("players",[])]}
        return out
    except Exception as ex:
        return {"error": str(ex)}

def ss_match_shotmap(match_id):
    try:
        shots = _ss(f"/event/{match_id}/shotmap").get("shotmap",[])
        rows = [{"player":s.get("player",{}).get("name"),
            "team":"home" if s.get("isHome") else "away",
            "minute":s.get("time"),
            "shot_type":s.get("shotType"),
            "situation":s.get("situation"),
            "xG":round(s.get("xg",0),3) if s.get("xg") else None,
            "on_target":s.get("isOnTarget")} for s in shots]
        home = [r for r in rows if r["team"]=="home"]
        away = [r for r in rows if r["team"]=="away"]
        return {"total":len(rows),
            "home_shots":len(home),"away_shots":len(away),
            "home_xG":round(sum(r["xG"] or 0 for r in home),2),
            "away_xG":round(sum(r["xG"] or 0 for r in away),2),
            "shots":rows}
    except Exception as ex:
        return {"error": str(ex)}

def ss_match_momentum(match_id):
    try:
        pts = _ss(f"/event/{match_id}/graph").get("graphPoints",[])
        if not pts:
            return {"error":"Sin datos de momentum"}
        return {"total_points":len(pts),
            "home_dominant":len([p for p in pts if p.get("value",0)>0]),
            "away_dominant":len([p for p in pts if p.get("value",0)<0]),
            "timeline":pts[:40]}
    except Exception as ex:
        return {"error": str(ex)}

def ss_search_player(name):
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=player").get("results",[])
        return {"players":[{"id":r["entity"].get("id"),
            "name":r["entity"].get("name"),
            "team":r["entity"].get("team",{}).get("name") if r["entity"].get("team") else None,
            "position":r["entity"].get("position"),
            "nationality":r["entity"].get("country",{}).get("name")}
            for r in rs[:5] if r.get("type")=="player"]}
    except Exception as ex:
        return {"error": str(ex)}

def ss_search_tournament(name):
    try:
        rs = _ss(f"/search/all?q={requests.utils.quote(name)}&type=uniqueTournament").get("results",[])
        out = []
        for r in rs[:5]:
            if r.get("type")=="uniqueTournament":
                e=r["entity"]; tid=e.get("id")
                si={}
                try:
                    s=_ss(f"/unique-tournament/{tid}/seasons").get("seasons",[{}])[0]
                    si={"season_id":s.get("id"),"season_name":s.get("name")}
                except Exception:
                    pass
                out.append({"id":tid,"name":e.get("name"),
                    "country":e.get("category",{}).get("name"),**si})
        return {"tournaments":out}
    except Exception as ex:
        return {"error": str(ex)}

def ss_standings(tournament_id, season_id):
    try:
        rows = _ss(f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
                   ).get("standings",[{}])[0].get("rows",[])
        return {"standings":[{"pos":r.get("position"),"team":r.get("team",{}).get("name"),
            "pj":r.get("matches"),"g":r.get("wins"),"e":r.get("draws"),"p":r.get("losses"),
            "gf":r.get("scoresFor"),"gc":r.get("scoresAgainst"),"pts":r.get("points")}
            for r in rows]}
    except Exception as ex:
        return {"error": str(ex)}


# ══════════════════════════════════════════════════════════════════════════════
# FOTMOB  — api pública directa
# ══════════════════════════════════════════════════════════════════════════════
_FM = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fotmob.com/",
}
FM = "https://www.fotmob.com/api/data"

def _fm(path):
    r = requests.get(f"{FM}/{path}", headers=_FM, timeout=15)
    r.raise_for_status()
    return r.json()

def fm_match_shotmap(match_id):
    """Mapa de tiros de un partido de FotMob. match_id = número al final de la URL."""
    try:
        data = _fm(f"matchDetails?matchId={match_id}")
        shots_raw = (data.get("content",{})
                        .get("shotmap",{})
                        .get("shots",[]))
        if not shots_raw:
            return {"error": "No hay shotmap para este partido en FotMob."}
        shots = []
        for s in shots_raw:
            shots.append({
                "player": s.get("playerName"),
                "team": s.get("teamColor"),
                "minute": s.get("min"),
                "shot_type": s.get("shotType"),
                "situation": s.get("situation"),
                "xG": round(s.get("expectedGoals",0),3) if s.get("expectedGoals") else None,
                "on_target": s.get("onTarget"),
                "is_goal": s.get("isGoal"),
            })
        home = [s for s in shots if s.get("team") == data.get("general",{}).get("homeTeam",{}).get("color")]
        return {
            "total_shots": len(shots),
            "shots": shots,
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_match_stats(match_id):
    """Estadísticas generales de un partido de FotMob."""
    try:
        data = _fm(f"matchDetails?matchId={match_id}")
        general = data.get("general", {})
        home_name = general.get("homeTeam", {}).get("name")
        away_name = general.get("awayTeam", {}).get("name")
        home_score = general.get("homeTeam", {}).get("score")
        away_score = general.get("awayTeam", {}).get("score")

        stats_raw = (data.get("content", {})
                        .get("stats", {})
                        .get("Periods", {})
                        .get("All", {})
                        .get("stats", []))
        rows = []
        for group in stats_raw:
            for stat in group.get("stats", []):
                rows.append({
                    "stat": stat.get("title"),
                    "home": stat.get("stats", [None, None])[0] if stat.get("stats") else None,
                    "away": stat.get("stats", [None, None])[1] if stat.get("stats") else None,
                })
        return {
            "home_team": home_name, "away_team": away_name,
            "home_score": home_score, "away_score": away_score,
            "statistics": rows,
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_match_momentum(match_id):
    """Momentum (gráfico de dominio) de un partido de FotMob."""
    try:
        data = _fm(f"matchDetails?matchId={match_id}")
        momentum = (data.get("content", {})
                       .get("momentum", {})
                       .get("items", []))
        if not momentum:
            return {"error": "Sin datos de momentum para este partido."}
        home_dom = len([m for m in momentum if m.get("value", 0) > 0])
        away_dom = len([m for m in momentum if m.get("value", 0) < 0])
        return {
            "total_points": len(momentum),
            "home_dominant_periods": home_dom,
            "away_dominant_periods": away_dom,
            "timeline": momentum[:40],
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_season_tables(league, season, table_type="all"):
    """Tabla de posiciones de FotMob. table_type: 'all', 'xg', 'form'."""
    # Mapa de ligas conocidas a sus IDs de FotMob
    LEAGUE_IDS = {
        "Premier League": 47, "La Liga": 87, "Serie A": 55, "Bundesliga": 54,
        "Ligue 1": 53, "Champions League": 42, "Europa League": 73,
        "Liga Profesional Argentina": 112, "Copa Libertadores": 480,
        "MLS": 130, "Eredivisie": 57, "Primeira Liga": 61,
        "Super Lig": 71, "Brasileirao": 325,
    }
    lid = LEAGUE_IDS.get(league)
    if not lid:
        return {"error": f"Liga '{league}' no reconocida.",
                "known_leagues": list(LEAGUE_IDS.keys())}
    try:
        data = _fm(f"table?leagueId={lid}&tableType={table_type}")
        tables = data.get("tables", [])
        if not tables:
            return {"error": "Sin datos de tabla para esta liga/temporada."}
        rows_raw = tables[0].get("table", {}).get("all", [])
        return {
            "league": league, "table_type": table_type,
            "table": [{
                "pos": r.get("idx"),
                "team": r.get("name"),
                "pj": r.get("played"),
                "g": r.get("wins"),
                "e": r.get("draws"),
                "p": r.get("losses"),
                "gf": r.get("scoresStr", "").split("-")[0] if r.get("scoresStr") else None,
                "gc": r.get("scoresStr", "").split("-")[1] if r.get("scoresStr") else None,
                "pts": r.get("pts"),
            } for r in rows_raw],
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_player_stats(league, season, stat):
    """Estadísticas de jugadores en una temporada de FotMob. Ej: stat='goals', 'assists', 'expected_goals_per_90'."""
    LEAGUE_IDS = {
        "Premier League": 47, "La Liga": 87, "Serie A": 55, "Bundesliga": 54,
        "Ligue 1": 53, "Champions League": 42, "Liga Profesional Argentina": 112,
        "Brasileirao": 325,
    }
    lid = LEAGUE_IDS.get(league)
    if not lid:
        return {"error": f"Liga '{league}' no reconocida.", "known_leagues": list(LEAGUE_IDS.keys())}
    try:
        data = _fm(f"leagueSeasonStats?id={lid}&type=players&stat={stat}")
        players_raw = data.get("topLists", [{}])[0].get("players", [])
        return {
            "league": league, "stat": stat,
            "players": [{
                "rank": i+1,
                "name": p.get("name") or p.get("playerName"),
                "team": p.get("teamName"),
                "value": p.get("statValue"),
            } for i, p in enumerate(players_raw[:20])],
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_team_stats(league, season, stat):
    """Estadísticas de equipos en una temporada de FotMob. Ej: stat='goals_scored', 'xg_for'."""
    LEAGUE_IDS = {
        "Premier League": 47, "La Liga": 87, "Serie A": 55, "Bundesliga": 54,
        "Ligue 1": 53, "Champions League": 42, "Liga Profesional Argentina": 112,
        "Brasileirao": 325,
    }
    lid = LEAGUE_IDS.get(league)
    if not lid:
        return {"error": f"Liga '{league}' no reconocida.", "known_leagues": list(LEAGUE_IDS.keys())}
    try:
        data = _fm(f"leagueSeasonStats?id={lid}&type=teams&stat={stat}")
        teams_raw = data.get("topLists", [{}])[0].get("teams", [])
        return {
            "league": league, "stat": stat,
            "teams": [{
                "rank": i+1,
                "team": t.get("name") or t.get("teamName"),
                "value": t.get("statValue"),
            } for i, t in enumerate(teams_raw[:20])],
        }
    except Exception as ex:
        return {"error": str(ex)}

def fm_player_data(player_id):
    """Toda la información disponible de un jugador en FotMob. player_id = número en la URL."""
    try:
        data = _fm(f"playerData?id={player_id}")
        general = data.get("general", {})
        career = data.get("careerStatistics", [])
        return {
            "name": general.get("name"),
            "team": general.get("teamName"),
            "position": general.get("positionType"),
            "nationality": general.get("nationality"),
            "age": general.get("age"),
            "market_value": general.get("marketValue"),
            "career_seasons": [{
                "season": s.get("seasonName"),
                "competition": s.get("competitionName"),
                "appearances": s.get("appearances"),
                "goals": s.get("goals"),
                "assists": s.get("assists"),
                "rating": s.get("rating"),
            } for s in career[:10]],
        }
    except Exception as ex:
        return {"error": str(ex)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS FOR CLAUDE
# ══════════════════════════════════════════════════════════════════════════════
TOOLS = [
    # ── SofaScore ───────────────────────────────────────────────────────────
    {"name":"ss_live","description":"SofaScore: Partidos en vivo ahora con resultado, minuto y torneo.",
     "input_schema":{"type":"object","properties":{"sport":{"type":"string","description":"Deporte: 'football', 'basketball', 'tennis'. Default: football","default":"football"}},"required":[]}},

    {"name":"ss_search_team","description":"SofaScore: Buscar equipo por nombre → obtiene su ID. Usá PRIMERO antes de pedir partidos del equipo.",
     "input_schema":{"type":"object","properties":{"name":{"type":"string","description":"Nombre del equipo"}},"required":["name"]}},

    {"name":"ss_team_recent","description":"SofaScore: Últimos 10 partidos de un equipo.",
     "input_schema":{"type":"object","properties":{"team_id":{"type":"string"}},"required":["team_id"]}},

    {"name":"ss_team_next","description":"SofaScore: Próximos 5 partidos programados de un equipo.",
     "input_schema":{"type":"object","properties":{"team_id":{"type":"string"}},"required":["team_id"]}},

    {"name":"ss_match_data","description":"SofaScore: Datos generales de un partido: equipos, resultado, torneo, sede, estado.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string","description":"Número al final de la URL de SofaScore"}},"required":["match_id"]}},

    {"name":"ss_match_stats","description":"SofaScore: Estadísticas del partido: posesión, tiros, córners, faltas, etc.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"ss_match_lineups","description":"SofaScore: Alineaciones, formaciones, números de camiseta y calificaciones.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"ss_match_shotmap","description":"SofaScore: Mapa de disparos con xG, minuto, jugador y tipo de tiro.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"ss_match_momentum","description":"SofaScore: Momentum del partido (dominio local vs visitante en el tiempo).",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"ss_search_player","description":"SofaScore: Buscar jugador por nombre → ID, equipo, posición, nacionalidad.",
     "input_schema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},

    {"name":"ss_search_tournament","description":"SofaScore: Buscar torneo/liga por nombre → ID y season_id. Necesario para tabla de posiciones.",
     "input_schema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},

    {"name":"ss_standings","description":"SofaScore: Tabla de posiciones de un torneo. Primero usá ss_search_tournament para obtener los IDs.",
     "input_schema":{"type":"object","properties":{"tournament_id":{"type":"string"},"season_id":{"type":"string"}},"required":["tournament_id","season_id"]}},

    # ── FotMob ──────────────────────────────────────────────────────────────
    {"name":"fm_match_stats","description":"FotMob: Estadísticas generales de un partido (posesión, tiros, pases, etc.). match_id = número al final de la URL de FotMob.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string","description":"Número al final de la URL de FotMob. Ej: https://www.fotmob.com/es/matches/.../2yrx85#4193851 → 4193851"}},"required":["match_id"]}},

    {"name":"fm_match_shotmap","description":"FotMob: Mapa de tiros de un partido con xG, minuto y jugador.",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"fm_match_momentum","description":"FotMob: Momentum del partido (gráfico de dominio de cada equipo en el tiempo).",
     "input_schema":{"type":"object","properties":{"match_id":{"type":"string"}},"required":["match_id"]}},

    {"name":"fm_season_tables","description":"FotMob: Tabla de posiciones de una liga. table_type puede ser 'all', 'xg' o 'form'.",
     "input_schema":{"type":"object","properties":{
         "league":{"type":"string","description":"Nombre de la liga. Ej: 'Premier League', 'La Liga', 'Liga Profesional Argentina'"},
         "season":{"type":"string","description":"Temporada. Ej: '2024/2025'"},
         "table_type":{"type":"string","description":"Tipo de tabla: 'all' (posiciones), 'xg' (por xG), 'form' (por forma reciente)","default":"all"}
     },"required":["league","season"]}},

    {"name":"fm_player_stats","description":"FotMob: Ranking de jugadores por estadística en una temporada. stat puede ser 'goals', 'assists', 'expected_goals_per_90', 'expected_assists_per_90', etc.",
     "input_schema":{"type":"object","properties":{
         "league":{"type":"string"},"season":{"type":"string"},
         "stat":{"type":"string","description":"Estadística a rankear. Ej: 'goals', 'assists', 'expected_goals_per_90'"}
     },"required":["league","season","stat"]}},

    {"name":"fm_team_stats","description":"FotMob: Ranking de equipos por estadística en una temporada. stat puede ser 'goals_scored', 'goals_conceded', 'xg_for', 'poss_won_att_3rd_team', etc.",
     "input_schema":{"type":"object","properties":{
         "league":{"type":"string"},"season":{"type":"string"},
         "stat":{"type":"string","description":"Estadística. Ej: 'goals_scored', 'xg_for', 'clean_sheet'"}
     },"required":["league","season","stat"]}},

    {"name":"fm_player_data","description":"FotMob: Toda la info disponible de un jugador: estadísticas de carrera, posición, valor de mercado. player_id = número en la URL de FotMob.",
     "input_schema":{"type":"object","properties":{
         "player_id":{"type":"string","description":"Número en la URL del jugador en FotMob. Ej: https://www.fotmob.com/es/players/1203665/alejandro-garnacho → 1203665"}
     },"required":["player_id"]}},
]

TOOL_FNS = {
    "ss_live":             lambda i: ss_live(**i),
    "ss_search_team":      lambda i: ss_search_team(**i),
    "ss_team_recent":      lambda i: ss_team_recent(**i),
    "ss_team_next":        lambda i: ss_team_next(**i),
    "ss_match_data":       lambda i: ss_match_data(**i),
    "ss_match_stats":      lambda i: ss_match_stats(**i),
    "ss_match_lineups":    lambda i: ss_match_lineups(**i),
    "ss_match_shotmap":    lambda i: ss_match_shotmap(**i),
    "ss_match_momentum":   lambda i: ss_match_momentum(**i),
    "ss_search_player":    lambda i: ss_search_player(**i),
    "ss_search_tournament":lambda i: ss_search_tournament(**i),
    "ss_standings":        lambda i: ss_standings(**i),
    "fm_match_stats":      lambda i: fm_match_stats(**i),
    "fm_match_shotmap":    lambda i: fm_match_shotmap(**i),
    "fm_match_momentum":   lambda i: fm_match_momentum(**i),
    "fm_season_tables":    lambda i: fm_season_tables(**i),
    "fm_player_stats":     lambda i: fm_player_stats(**i),
    "fm_team_stats":       lambda i: fm_team_stats(**i),
    "fm_player_data":      lambda i: fm_player_data(**i),
}

TOOL_META = {
    "ss_live":             ("sofa", "🔴 Partidos en vivo"),
    "ss_search_team":      ("sofa", "🔍 Buscando equipo"),
    "ss_team_recent":      ("sofa", "📅 Últimos partidos"),
    "ss_team_next":        ("sofa", "📅 Próximos partidos"),
    "ss_match_data":       ("sofa", "📋 Datos del partido"),
    "ss_match_stats":      ("sofa", "📊 Estadísticas"),
    "ss_match_lineups":    ("sofa", "👥 Alineaciones"),
    "ss_match_shotmap":    ("sofa", "🎯 Mapa de tiros"),
    "ss_match_momentum":   ("sofa", "📈 Momentum"),
    "ss_search_player":    ("sofa", "🔍 Buscando jugador"),
    "ss_search_tournament":("sofa", "🏆 Buscando torneo"),
    "ss_standings":        ("sofa", "🏆 Tabla de posiciones"),
    "fm_match_stats":      ("fotmob", "📊 Estadísticas FotMob"),
    "fm_match_shotmap":    ("fotmob", "🎯 Tiros FotMob"),
    "fm_match_momentum":   ("fotmob", "📈 Momentum FotMob"),
    "fm_season_tables":    ("fotmob", "🏆 Tabla FotMob"),
    "fm_player_stats":     ("fotmob", "👤 Stats jugadores"),
    "fm_team_stats":       ("fotmob", "🏟️ Stats equipos"),
    "fm_player_data":      ("fotmob", "👤 Datos del jugador"),
}


# ══════════════════════════════════════════════════════════════════════════════
# AGENTIC LOOP
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM = """Sos un asistente experto en fútbol y estadísticas deportivas con acceso a dos fuentes:

**SofaScore** (prefijo ss_): cobertura global, partidos en vivo, estadísticas, alineaciones, xG, momentum, tabla de posiciones.
**FotMob** (prefijo fm_): estadísticas de liga y temporada, ranking de jugadores/equipos, datos de carrera de jugadores, tabla con xG y forma.

## Estrategia de uso

### SofaScore:
- Para equipos → ss_search_team primero para obtener el ID, luego usás el ID.
- Para tabla de posiciones → ss_search_tournament primero (obtener tournament_id + season_id), luego ss_standings.
- El match_id de SofaScore es el número al final de la URL: `.../partido/river-boca/12345678` → `"12345678"`.

### FotMob:
- El match_id de FotMob es el número después del # en la URL: `https://fotmob.com/...#4193851` → `"4193851"`.
- El player_id de FotMob está en la URL del jugador: `https://fotmob.com/es/players/1203665/...` → `"1203665"`.
- Para rankings de jugadores/equipos en una temporada usá fm_player_stats o fm_team_stats.
- Para tabla de posiciones de ligas grandes usá fm_season_tables.
- Si el usuario no tiene el ID de FotMob, podés sugerirle que busque el partido en fotmob.com.

### Cuándo usar cada fuente:
- Partidos en vivo, alineaciones, heatmaps de jugadores → SofaScore.
- Rankings de goleadores, asistidores, xG por jugador/equipo en la temporada → FotMob.
- Datos de carrera de un jugador → FotMob (fm_player_data).
- Para un partido específico: podés combinar ambas fuentes si el usuario tiene los dos IDs.

## Formato de respuesta
- Siempre en español, tono amigable y claro.
- Usá tablas markdown para datos tabulares (tabla de posiciones, estadísticas, tiros).
- Indicá la fuente (📘 SofaScore / 📗 FotMob) al presentar datos.
- Si una tool falla, explicá el motivo y sugerí alternativas.
- Si el usuario no tiene un ID necesario, explicale cómo encontrarlo en la URL correspondiente."""

def run_agent(client, messages):
    tool_calls = []
    for _ in range(12):
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM,
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

        messages.append({"role":"assistant","content":resp.content})

        if resp.stop_reason == "end_turn" or not uses:
            return text, tool_calls

        results = []
        for tu in uses:
            tool_calls.append(tu.name)
            try:
                result = TOOL_FNS[tu.name](tu.input)
            except Exception as e:
                result = {"error": str(e)}
            results.append({"type":"tool_result","tool_use_id":tu.id,
                            "content":json.dumps(result, ensure_ascii=False)})
        messages.append({"role":"user","content":results})

    return "Alcancé el límite de iteraciones. Intentá reformular.", tool_calls


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚽ Football Chat")
    st.markdown("<span style='color:#57606a;font-size:.85rem'>SofaScore · FotMob · Claude AI</span>", unsafe_allow_html=True)
    st.divider()

    api_key = st.text_input("🔑 API Key de Anthropic", type="password", placeholder="sk-ant-...")

    st.divider()
    st.markdown("### 💡 Ejemplos")

    EXAMPLES = {
        "🔴 En vivo": [
            "¿Qué partidos hay en vivo?",
            "Partidos de basketball en vivo",
        ],
        "🏆 Equipos": [
            "Últimos partidos de River Plate",
            "Próximos partidos de Boca Juniors",
            "Tabla de posiciones de la Premier League",
        ],
        "📊 Estadísticas de temporada": [
            "Top goleadores de La Liga 2024/2025",
            "Equipos con más xG en la Premier League",
            "Tabla por xG de la Bundesliga",
        ],
        "⚽ Partidos específicos": [
            "Estadísticas del partido SS ID: 12345678",
            "Alineaciones del partido SS ID: 12345678",
            "Tiros y xG del partido FM ID: 4193851",
            "Momentum del partido FM ID: 4193851",
        ],
        "👤 Jugadores": [
            "Buscame info sobre Lautaro Martinez",
            "Datos de carrera del jugador FM ID: 1203665",
        ],
    }

    for section, exs in EXAMPLES.items():
        with st.expander(section, expanded=False):
            for ex in exs:
                if st.button(ex, key=ex, use_container_width=True):
                    st.session_state.pending_example = ex

    st.divider()
    st.markdown("""<div style='font-size:.8rem;color:#57606a;line-height:1.8'>
<b>SofaScore match ID:</b><br>
sofascore.com/partido/river-boca/<b>12345678</b><br><br>
<b>FotMob match ID:</b><br>
fotmob.com/es/matches/.../<b>#4193851</b><br><br>
<b>FotMob player ID:</b><br>
fotmob.com/es/players/<b>1203665</b>/garnacho
</div>""", unsafe_allow_html=True)
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
    st.markdown("<span style='color:#57606a'>Resultados · Estadísticas · xG · Tabla de posiciones · Datos de jugadores</span>",
                unsafe_allow_html=True)
with c2:
    st.markdown("""<div style='text-align:right;margin-top:16px'>
<span class='pill-sofa'>📘 SofaScore</span><br>
<span class='pill-fotmob'>📗 FotMob</span>
</div>""", unsafe_allow_html=True)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════════════════
def render_pills(tools_used):
    if not tools_used:
        return
    pills = []
    for t in tools_used:
        src, label = TOOL_META.get(t, ("sofa", t))
        css = "pill-fotmob" if src == "fotmob" else "pill-sofa"
        pills.append(f'<span class="{css}">{label}</span>')
    st.markdown(" ".join(pills), unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("tools_used"):
            render_pills(msg["tools_used"])
        st.markdown(msg["content"])

# example button
prompt = None
if "pending_example" in st.session_state:
    prompt = st.session_state.pop("pending_example")

user_input = st.chat_input("Preguntá sobre partidos, equipos, estadísticas, rankings de jugadores…")
if user_input:
    prompt = user_input

if prompt:
    if not api_key:
        st.warning("⚠️ Ingresá tu API Key de Anthropic en el panel izquierdo.")
        st.stop()

    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.api_messages.append({"role":"user","content":prompt})

    with st.chat_message("assistant"):
        with st.spinner("Consultando…"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                msgs = list(st.session_state.api_messages)
                answer, tools_used = run_agent(client, msgs)
                st.session_state.api_messages = msgs

                render_pills(tools_used)
                st.markdown(answer)

                st.session_state.messages.append({
                    "role":"assistant","content":answer,"tools_used":tools_used
                })
            except anthropic.AuthenticationError:
                st.error("❌ API Key inválida.")
            except Exception as e:
                st.error(f"❌ Error: {e}")
