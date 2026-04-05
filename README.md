# ⚽ SofaScore Chat

Chat de consulta de resultados y partidos usando la API pública de SofaScore + Claude (Anthropic).

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

Luego ingresá tu API Key de Anthropic en el panel lateral izquierdo y empezá a consultar.

## Herramientas disponibles

| Tool | Descripción |
|------|-------------|
| `get_live_matches` | Partidos en vivo ahora mismo |
| `search_team` | Buscar un equipo por nombre |
| `get_team_recent_matches` | Últimos 10 partidos de un equipo |
| `get_team_next_matches` | Próximos 5 partidos de un equipo |
| `search_player` | Buscar un jugador por nombre |
| `get_match_data` | Datos generales de un partido (score, estado) |
| `get_match_lineups` | Alineaciones y formaciones |
| `get_match_statistics` | Estadísticas del partido (posesión, tiros, etc.) |
| `get_match_shotmap` | Mapa de disparos con xG |

## Ejemplos de consultas

- "¿Qué partidos hay en vivo ahora?"
- "Últimos partidos de River Plate"
- "¿Cuándo juega el próximo partido el Barcelona?"
- "Dame las estadísticas del partido 11398400"
- "Buscame info sobre Lionel Messi"
- "¿Cuál fue la alineación en el partido con ID 12345678?"

## Nota

Usa la API pública de SofaScore (sin Selenium) a través de `api.sofascore.com`.
Los IDs de partidos los encontrás en las URLs de SofaScore: el número al final.
