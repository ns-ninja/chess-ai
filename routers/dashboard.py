"""Dashboard router — progress charts and overview."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db import get_supabase

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    sb  = get_supabase()
    player = sb.table("players").select("*").limit(1).execute().data[0]

    games = (sb.table("games")
               .select("*, analyses(strengths, weaknesses, verdict)")
               .eq("player_id", player["id"])
               .order("played_at", desc=True)
               .execute().data)

    weakness_profile = (sb.table("weakness_profile")
                          .select("*")
                          .eq("player_id", player["id"])
                          .order("occurrences", desc=True)
                          .execute().data)

    # Compute stats
    total  = len(games)
    wins   = sum(1 for g in games if g["result"] == "win")
    losses = sum(1 for g in games if g["result"] == "loss")
    draws  = sum(1 for g in games if g["result"] == "draw")

    white_games = [g for g in games if g["color"] == "white"]
    black_games = [g for g in games if g["color"] == "black"]

    stats = {
        "total":        total,
        "wins":         wins,
        "losses":       losses,
        "draws":        draws,
        "win_rate":     round(wins / total * 100) if total else 0,
        "white_score":  sum({"win":1,"draw":0.5,"loss":0}.get(g["result"],0) for g in white_games),
        "white_total":  len(white_games),
        "black_score":  sum({"win":1,"draw":0.5,"loss":0}.get(g["result"],0) for g in black_games),
        "black_total":  len(black_games),
    }

    # Opening breakdown
    opening_stats = {}
    for g in games:
        eco  = g.get("opening_eco","?") or "?"
        name = (g.get("opening_name","Unknown") or "Unknown")[:30]
        key  = f"{eco} — {name}"
        if key not in opening_stats:
            opening_stats[key] = {"eco":eco,"name":name,"games":0,"score":0}
        opening_stats[key]["games"] += 1
        opening_stats[key]["score"] += {"win":1,"draw":0.5,"loss":0}.get(g["result"],0)
    openings = sorted(opening_stats.values(), key=lambda x: -x["games"])[:8]

    return templates.TemplateResponse("dashboard/index.html", {
        "request":          request,
        "player":           player,
        "games":            games,
        "stats":            stats,
        "weakness_profile": weakness_profile,
        "openings":         openings,
    })
