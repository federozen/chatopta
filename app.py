import streamlit as st
import anthropic
import json
import time
import re
import subprocess
import sys
from datetime import datetime
import pandas as pd

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SofaScore Chat",
    page_icon="⚽",
    layout="wide",
)

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* overall background */
  .stApp { background: #0d1117; color: #e6edf3; }

  /* sidebar */
  section[data-testid="stSidebar"] { background: #161b22; }
  section[data-testid="stSidebar"] * { color: #e6edf3 !important; }

  /* chat messages */
  .stChatMessage { background: #161b22; border-radius: 12px;
                   border: 1px solid #30363d; margin-bottom: .6rem; }

  /* user bubble */
  .stChatMessage[data-testid="stChatMessage-user"] {
    background: #1c3052; border-color: #264f78;
  }

  /* chat input */
  .stChatInput textarea { background: #161b22 !important;
    color: #e6edf3 !important; border: 1px solid #30363d !important; }

  /* tool-use pill */
  .tool-pill {
    display:inline-block; background:#1f2f1f; color:#56d364;
    border:1px solid #2ea043; border-radius:20px;
    padding:2px 12px; font-size:.75rem; margin-bottom:.5rem;
  }

  /* dataframe */
  .stDataFrame { border: 1px solid #30363d; border-radius:8px; }

  /* headings */
  h1,h2,h3 { color: #58a6ff !important; }

  /* buttons */
  .stButton>button { background:#238636; color:#fff;
    border:none; border-radius:6px; }
  .stButton>button:hover { background:#2ea043; }
</style>
""", unsafe_allow_html=True)

# ── SofaScore API helpers (simplified – no Selenium, pure requests) ───────────
import requests

SOFASCORE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
BASE = "https://api.sofascore.com/api/v1"

def _get(path: str) -> dict:
    """Raw GET to SofaScore public API."""
    url = f"{BASE}{path}"
    resp = requests.get(url, headers=SOFASCORE_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()

# ── Tool implementations ──────────────────────────────────────────────────────

def get_match_data(match_id: str) -> dict:
    """General data for a match (teams, score, status, etc.)."""
    try:
        data = _get(f"/event/{match_id}")
        ev = data.get("event", {})
        return {
            "home_team": ev.get("homeTeam", {}).get("name"),
            "away_team": ev.get("awayTeam", {}).get("name"),
            "home_score": ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("awayScore", {}).get("current"),
            "status": ev.get("status", {}).get("description"),
            "tournament": ev.get("tournament", {}).get("name"),
            "start_time": datetime.utcfromtimestamp(
                ev.get("startTimestamp", 0)
            ).strftime("%Y-%m-%d %H:%M UTC") if ev.get("startTimestamp") else None,
            "winner_code": ev.get("winnerCode"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_match_shotmap(match_id: str) -> dict:
    """Shotmap for a match."""
    try:
        data = _get(f"/event/{match_id}/shotmap")
        shots = data.get("shotmap", [])
        rows = []
        for s in shots:
            player = s.get("player", {})
            rows.append({
                "player": player.get("name"),
                "team": "home" if s.get("isHome") else "away",
                "minute": s.get("time"),
                "shot_type": s.get("shotType"),
                "situation": s.get("situation"),
                "goal_mouth_location": s.get("goalMouthLocation"),
                "xG": round(s.get("xg", 0), 3) if s.get("xg") else None,
                "on_target": s.get("isOnTarget"),
            })
        return {"total_shots": len(rows), "shots": rows}
    except Exception as e:
        return {"error": str(e)}


def get_match_lineups(match_id: str) -> dict:
    """Starting lineups for a match."""
    try:
        data = _get(f"/event/{match_id}/lineups")
        result = {}
        for side in ("home", "away"):
            team_data = data.get(side, {})
            players = team_data.get("players", [])
            result[side] = {
                "formation": team_data.get("formation"),
                "players": [
                    {
                        "name": p.get("player", {}).get("name"),
                        "position": p.get("position"),
                        "shirt_number": p.get("shirtNumber"),
                        "substitute": p.get("substitute", False),
                        "rating": p.get("statistics", {}).get("rating"),
                    }
                    for p in players
                ],
            }
        return result
    except Exception as e:
        return {"error": str(e)}


def get_match_statistics(match_id: str) -> dict:
    """Match statistics (possession, shots, etc.)."""
    try:
        data = _get(f"/event/{match_id}/statistics")
        groups = data.get("statistics", [])
        rows = []
        for g in groups:
            for item in g.get("groups", []):
                for stat in item.get("statisticsItems", []):
                    rows.append({
                        "name": stat.get("name"),
                        "home": stat.get("home"),
                        "away": stat.get("away"),
                    })
        return {"statistics": rows}
    except Exception as e:
        return {"error": str(e)}


def search_team(team_name: str) -> dict:
    """Search for a team by name."""
    try:
        data = _get(f"/search/all?q={requests.utils.quote(team_name)}&type=team")
        results = data.get("results", [])
        teams = []
        for r in results[:5]:
            e = r.get("entity", {})
            if r.get("type") == "team":
                teams.append({
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "country": e.get("country", {}).get("name"),
                    "sport": e.get("sport", {}).get("name"),
                })
        return {"teams": teams}
    except Exception as e:
        return {"error": str(e)}


def get_team_recent_matches(team_id: str) -> dict:
    """Last 10 matches for a team."""
    try:
        data = _get(f"/team/{team_id}/events/last/0")
        events = data.get("events", [])[-10:]
        matches = []
        for ev in events:
            matches.append({
                "id": ev.get("id"),
                "home": ev.get("homeTeam", {}).get("name"),
                "away": ev.get("awayTeam", {}).get("name"),
                "home_score": ev.get("homeScore", {}).get("current"),
                "away_score": ev.get("awayScore", {}).get("current"),
                "status": ev.get("status", {}).get("description"),
                "tournament": ev.get("tournament", {}).get("name"),
                "date": datetime.utcfromtimestamp(
                    ev.get("startTimestamp", 0)
                ).strftime("%Y-%m-%d") if ev.get("startTimestamp") else None,
            })
        return {"matches": matches}
    except Exception as e:
        return {"error": str(e)}


def get_team_next_matches(team_id: str) -> dict:
    """Next 5 scheduled matches for a team."""
    try:
        data = _get(f"/team/{team_id}/events/next/0")
        events = data.get("events", [])[:5]
        matches = []
        for ev in events:
            matches.append({
                "id": ev.get("id"),
                "home": ev.get("homeTeam", {}).get("name"),
                "away": ev.get("awayTeam", {}).get("name"),
                "tournament": ev.get("tournament", {}).get("name"),
                "date": datetime.utcfromtimestamp(
                    ev.get("startTimestamp", 0)
                ).strftime("%Y-%m-%d %H:%M UTC") if ev.get("startTimestamp") else None,
            })
        return {"next_matches": matches}
    except Exception as e:
        return {"error": str(e)}


def search_player(player_name: str) -> dict:
    """Search for a player by name."""
    try:
        data = _get(f"/search/all?q={requests.utils.quote(player_name)}&type=player")
        results = data.get("results", [])
        players = []
        for r in results[:5]:
            if r.get("type") == "player":
                e = r.get("entity", {})
                players.append({
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "team": e.get("team", {}).get("name") if e.get("team") else None,
                    "position": e.get("position"),
                    "nationality": e.get("country", {}).get("name"),
                })
        return {"players": players}
    except Exception as e:
        return {"error": str(e)}


def get_live_matches(sport: str = "football") -> dict:
    """Get currently live matches for a sport."""
    try:
        data = _get(f"/sport/{sport}/events/live")
        events = data.get("events", [])[:20]
        matches = []
        for ev in events:
            matches.append({
                "id": ev.get("id"),
                "home": ev.get("homeTeam", {}).get("name"),
                "away": ev.get("awayTeam", {}).get("name"),
                "home_score": ev.get("homeScore", {}).get("current"),
                "away_score": ev.get("awayScore", {}).get("current"),
                "minute": ev.get("time", {}).get("played"),
                "status": ev.get("status", {}).get("description"),
                "tournament": ev.get("tournament", {}).get("name"),
            })
        return {"live_matches": matches, "count": len(matches)}
    except Exception as e:
        return {"error": str(e)}


# ── Tool definitions for Claude ───────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_match_data",
        "description": "Get general data for a match: teams, score, status, tournament, start time. Use when the user asks about a specific match result or info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "SofaScore match/event ID (numeric string)."}
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "get_match_shotmap",
        "description": "Get all shots for a match including player, xG, minute, shot type, and whether it was on target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "SofaScore match/event ID."}
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "get_match_lineups",
        "description": "Get starting lineups, formations, shirt numbers and ratings for both teams in a match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "SofaScore match/event ID."}
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "get_match_statistics",
        "description": "Get match statistics like possession, shots on target, corners, fouls, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "SofaScore match/event ID."}
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "search_team",
        "description": "Search for a team by name to get its SofaScore ID. Use this first before fetching team matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_name": {"type": "string", "description": "Team name to search for (e.g. 'River Plate', 'Barcelona')."}
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_team_recent_matches",
        "description": "Get last 10 matches (results) for a team using its SofaScore team ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "SofaScore team ID (numeric string)."}
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "get_team_next_matches",
        "description": "Get next 5 upcoming scheduled matches for a team using its SofaScore team ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "SofaScore team ID (numeric string)."}
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "search_player",
        "description": "Search for a player by name to get their SofaScore ID, team, position and nationality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string", "description": "Player name to search for."}
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "get_live_matches",
        "description": "Get all currently live matches for a sport (default: football). Shows score, minute, tournament.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sport": {
                    "type": "string",
                    "description": "Sport slug: 'football', 'basketball', 'tennis', etc.",
                    "default": "football",
                }
            },
            "required": [],
        },
    },
]

# ── Tool dispatcher ───────────────────────────────────────────────────────────
TOOL_FNS = {
    "get_match_data": lambda inp: get_match_data(**inp),
    "get_match_shotmap": lambda inp: get_match_shotmap(**inp),
    "get_match_lineups": lambda inp: get_match_lineups(**inp),
    "get_match_statistics": lambda inp: get_match_statistics(**inp),
    "search_team": lambda inp: search_team(**inp),
    "get_team_recent_matches": lambda inp: get_team_recent_matches(**inp),
    "get_team_next_matches": lambda inp: get_team_next_matches(**inp),
    "search_player": lambda inp: search_player(**inp),
    "get_live_matches": lambda inp: get_live_matches(**inp),
}

TOOL_LABELS = {
    "get_match_data": "📋 Buscando datos del partido…",
    "get_match_shotmap": "🎯 Obteniendo mapa de disparos…",
    "get_match_lineups": "👥 Cargando alineaciones…",
    "get_match_statistics": "📊 Cargando estadísticas…",
    "search_team": "🔍 Buscando equipo…",
    "get_team_recent_matches": "🏆 Últimos partidos del equipo…",
    "get_team_next_matches": "📅 Próximos partidos…",
    "search_player": "🔍 Buscando jugador…",
    "get_live_matches": "🔴 Partidos en vivo…",
}

# ── Agentic loop ──────────────────────────────────────────────────────────────
def run_agent(client: anthropic.Anthropic, messages: list) -> tuple[str, list]:
    """Run the agentic loop. Returns final text and tool_calls list for display."""
    system = """Sos un asistente experto en fútbol y estadísticas deportivas que usa la API de SofaScore.

Cuando el usuario pregunte sobre equipos, partidos o jugadores:
1. Primero buscá el ID usando search_team o search_player si no lo tenés.
2. Luego usá ese ID para obtener la info pedida.
3. Presentá la información de forma clara, ordenada y en español.
4. Si el usuario da una URL de SofaScore, extraé el ID del final (ej. .../12345678 → match_id="12345678").
5. Para partidos en vivo, usá get_live_matches.
6. Siempre informá el torneo/competición cuando sea relevante.

Respondé siempre en español y de forma amigable."""

    tool_calls_made = []

    for _ in range(10):  # max 10 iterations
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # collect text blocks
        assistant_text = ""
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                assistant_text += block.text
            elif block.type == "tool_use":
                tool_uses.append(block)

        # add assistant turn to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn" or not tool_uses:
            return assistant_text, tool_calls_made

        # execute tools
        tool_results = []
        for tu in tool_uses:
            tool_calls_made.append(tu.name)
            try:
                result = TOOL_FNS[tu.name](tu.input)
            except Exception as e:
                result = {"error": str(e)}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        messages.append({"role": "user", "content": tool_results})

    return "No pude completar la consulta en el número máximo de iteraciones.", tool_calls_made


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ SofaScore Chat")
    st.markdown("---")

    api_key = st.text_input(
        "API Key de Anthropic",
        type="password",
        placeholder="sk-ant-...",
        help="Ingresá tu API key de Anthropic",
    )

    st.markdown("---")
    st.markdown("### 💡 Ejemplos de consultas")
    examples = [
        "¿Qué partidos hay en vivo ahora?",
        "Buscame los últimos partidos de River Plate",
        "¿Cuál es la alineación del partido con ID 12345678?",
        "Buscame estadísticas del partido 11398400",
        "¿Cuándo juega el próximo partido el Barcelona?",
        "Buscame info sobre el jugador Lionel Messi",
        "Dame el mapa de disparos del partido 12345678",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.pending_example = ex

    st.markdown("---")
    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<small style='color:#8b949e'>Datos: SofaScore API pública<br>"
        "IA: Claude claude-sonnet-4-20250514<br>"
        "Herramientas: 9 endpoints</small>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []  # display messages
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []  # API history

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ⚽ SofaScore Chat")
st.markdown(
    "<span style='color:#8b949e'>Consultá resultados, estadísticas y datos "
    "de partidos usando IA + SofaScore</span>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # tool pills
        if msg.get("tools_used"):
            for t in msg["tools_used"]:
                label = TOOL_LABELS.get(t, t)
                st.markdown(f'<span class="tool-pill">🔧 {label.split("…")[0]}</span>', unsafe_allow_html=True)
        st.markdown(msg["content"])

# ── Handle example button click ───────────────────────────────────────────────
if "pending_example" in st.session_state:
    prompt = st.session_state.pop("pending_example")
else:
    prompt = None

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Preguntá sobre partidos, equipos, estadísticas…")
if user_input:
    prompt = user_input

if prompt:
    if not api_key:
        st.warning("⚠️ Ingresá tu API Key de Anthropic en el panel izquierdo para continuar.")
        st.stop()

    # show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # add to API history
    st.session_state.api_messages.append({"role": "user", "content": prompt})

    # run agent
    with st.chat_message("assistant"):
        with st.spinner("Consultando SofaScore…"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                # pass a copy so we can update session state after
                api_msgs_copy = [m for m in st.session_state.api_messages]
                answer, tools_used = run_agent(client, api_msgs_copy)
                # update session api_messages with the full agentic loop
                st.session_state.api_messages = api_msgs_copy

                # show tool pills
                for t in tools_used:
                    label = TOOL_LABELS.get(t, t)
                    st.markdown(f'<span class="tool-pill">🔧 {label.split("…")[0]}</span>', unsafe_allow_html=True)

                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "tools_used": tools_used,
                })
            except anthropic.AuthenticationError:
                st.error("❌ API Key inválida. Verificá que sea correcta.")
            except Exception as e:
                st.error(f"❌ Error: {e}")
