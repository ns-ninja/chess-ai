"""Analysis router — runs Claude on a game and updates weakness profile."""
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_supabase, get_anthropic, COACH_SYSTEM_PROMPT

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Weakness pattern keywords Claude uses → canonical pattern name
PATTERN_MAP = {
    "king safety":       ("King safety / unsafe castling", "critical"),
    "castling":          ("King safety / unsafe castling", "critical"),
    "queenside castle":  ("King safety / unsafe castling", "critical"),
    "draws":             ("Taking draws too early as White", "moderate"),
    "active piece":      ("Trading active pieces", "moderate"),
    "passive rook":      ("Passive rook in endgames", "moderate"),
    "queen sortie":      ("Early queen sorties", "minor"),
    "queen too early":   ("Early queen sorties", "minor"),
    "pawn grab":         ("Material greed under pressure", "moderate"),
}


def extract_patterns(weaknesses: list[str]) -> list[tuple[str, str]]:
    """Map raw weakness strings to canonical (name, severity) pairs."""
    found = set()
    for w in weaknesses:
        wl = w.lower()
        for keyword, (name, severity) in PATTERN_MAP.items():
            if keyword in wl:
                found.add((name, severity))
    return list(found)


def update_weakness_profile(player_id: str, weaknesses: list[str], strengths: list[str]):
    sb = get_supabase()
    patterns = extract_patterns(weaknesses)
    for name, severity in patterns:
        existing = (sb.table("weakness_profile")
                      .select("*")
                      .eq("player_id", player_id)
                      .eq("pattern_name", name)
                      .execute().data)
        if existing:
            row = existing[0]
            new_count = row["occurrences"] + 1
            # Simple trend: if seen in 3+ consecutive games → worsening
            trend = "worsening" if new_count >= 3 else "stable"
            sb.table("weakness_profile").update({
                "occurrences":   new_count,
                "severity":      severity,
                "trend":         trend,
                "last_seen_at":  "now()",
                "updated_at":    "now()",
            }).eq("id", row["id"]).execute()
        else:
            sb.table("weakness_profile").insert({
                "player_id":    player_id,
                "pattern_name": name,
                "severity":     severity,
                "occurrences":  1,
                "trend":        "stable",
            }).execute()

    # Mark strengths as improving if they match known weaknesses
    for s in strengths:
        sl = s.lower()
        for keyword, (name, _) in PATTERN_MAP.items():
            if keyword in sl:
                sb.table("weakness_profile").update({
                    "trend": "improving"
                }).eq("player_id", player_id).eq("pattern_name", name).execute()


@router.get("/{game_id}/run")
async def run_analysis(game_id: str):
    """Trigger Claude analysis for a game. Called automatically after upload."""
    sb = get_supabase()
    ai = get_anthropic()

    game = sb.table("games").select("*, players(*)").eq("id", game_id).single().execute().data
    if not game:
        raise HTTPException(404, "Game not found")

    # Check for existing analysis
    existing = sb.table("analyses").select("id").eq("game_id", game_id).execute().data
    if existing:
        return RedirectResponse(f"/games/{game_id}", status_code=303)

    player  = game["players"]
    color   = game["color"].capitalize()
    result  = game["result"].upper()
    opp     = game.get("opponent_name", "opponent")
    opp_r   = game.get("opponent_rating", "?")
    opening = game.get("opening_name", "")
    tourn   = game.get("tournament", "")

    # Fetch previous weaknesses for cross-game context
    profile = (sb.table("weakness_profile")
                 .select("pattern_name, occurrences, trend, severity")
                 .eq("player_id", player["id"])
                 .order("occurrences", desc=True)
                 .execute().data)
    profile_text = "\n".join(
        f"- {p['pattern_name']}: seen {p['occurrences']} times, trend={p['trend']}"
        for p in profile
    ) or "No previous pattern data yet."

    prompt = f"""Analyze this chess game for Neal Sundar ({player['uscf_rating']} USCF).

GAME INFO:
- Neal played: {color}
- Result: {result}
- Opponent: {opp} (rated {opp_r})
- Opening: {opening}
- Tournament: {tourn}

EXISTING WEAKNESS PROFILE (from previous games):
{profile_text}

PGN:
{game['pgn']}

Provide your analysis as a JSON object following the format in your instructions.
Cross-reference any patterns with the existing weakness profile above.
If king safety or queenside castling is an issue, flag it as CRITICAL — this is a known recurring pattern.
"""
    response = ai.messages.create(
        model="claude-sonnet-4-5-20251001",
        max_tokens=2000,
        system=COACH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        data = {
            "verdict": raw[:500],
            "key_moments": [],
            "strengths": [],
            "weaknesses": [],
            "cross_game_patterns": [],
            "study_recommendation": ""
        }

    # Save analysis
    sb.table("analyses").insert({
        "game_id":     game_id,
        "verdict":     data.get("verdict", ""),
        "key_moments": data.get("key_moments", []),
        "strengths":   data.get("strengths", []),
        "weaknesses":  data.get("weaknesses", []),
        "coach_notes": data.get("study_recommendation", ""),
    }).execute()

    # Update weakness profile
    update_weakness_profile(
        player["id"],
        data.get("weaknesses", []),
        data.get("strengths", [])
    )

    return RedirectResponse(f"/games/{game_id}", status_code=303)


@router.get("/{game_id}/chat", response_class=HTMLResponse)
async def chat_page(request: Request, game_id: str):
    sb = get_supabase()
    game = sb.table("games").select("*, analyses(*)").eq("id", game_id).single().execute().data
    return templates.TemplateResponse("analysis/chat.html",
                                      {"request": request, "game": game})


@router.post("/{game_id}/chat/message")
async def chat_message(game_id: str, request: Request):
    """Stream a coach response for a specific game."""
    body = await request.json()
    user_msg = body.get("message", "")
    history  = body.get("history", [])

    sb = get_supabase()
    ai = get_anthropic()

    game = (sb.table("games")
              .select("*, analyses(*), players(*)")
              .eq("id", game_id).single().execute().data)

    analysis = game.get("analyses") or {}
    game_context = f"""Game: {game['color']} vs {game['opponent_name']} ({game['opponent_rating']})
Result: {game['result']} | Opening: {game['opening_name']}
PGN: {game['pgn']}
Coach verdict: {analysis.get('verdict','')}
Key weaknesses found: {', '.join(analysis.get('weaknesses',[]))}"""

    messages = [
        *history,
        {"role": "user", "content": f"[Game context: {game_context}]\n\n{user_msg}"}
    ]

    response = ai.messages.create(
        model="claude-sonnet-4-5-20251001",
        max_tokens=800,
        system=COACH_SYSTEM_PROMPT,
        messages=messages
    )
    return {"reply": response.content[0].text}
