"""Games router — upload PGN, list games, view a game."""
import json, chess.pgn, io
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_supabase

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def parse_pgn(pgn_text: str) -> dict:
    """Extract metadata from a PGN string using python-chess."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return {}
    h = game.headers
    result_map = {"1-0": "win", "0-1": "loss", "1/2-1/2": "draw", "*": "unknown"}
    return {
        "white":        h.get("White", ""),
        "black":        h.get("Black", ""),
        "result_raw":   h.get("Result", "*"),
        "result":       result_map.get(h.get("Result","*"), "unknown"),
        "eco":          h.get("ECO", ""),
        "opening":      h.get("Opening", ""),
        "date":         h.get("Date", "")[:10] if h.get("Date") else None,
        "event":        h.get("Event", ""),
        "white_elo":    int(h.get("WhiteElo", 0) or 0),
        "black_elo":    int(h.get("BlackElo", 0) or 0),
    }


@router.get("/", response_class=HTMLResponse)
async def list_games(request: Request):
    sb = get_supabase()
    player = sb.table("players").select("*").limit(1).execute().data[0]
    games = (sb.table("games")
               .select("*, analyses(id, verdict)")
               .eq("player_id", player["id"])
               .order("played_at", desc=True)
               .execute().data)
    return templates.TemplateResponse("games/list.html",
                                      {"request": request, "games": games, "player": player})


@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("games/upload.html", {"request": request})


@router.post("/upload")
async def upload_game(
    request: Request,
    pgn_file: UploadFile = File(None),
    pgn_text: str = Form(""),
    player_color: str = Form("white"),
    tournament: str = Form(""),
):
    sb = get_supabase()
    player = sb.table("players").select("*").limit(1).execute().data[0]

    # Get PGN content from file or textarea
    raw_pgn = pgn_text.strip()
    if pgn_file and pgn_file.filename:
        raw_pgn = (await pgn_file.read()).decode("utf-8").strip()
    if not raw_pgn:
        raise HTTPException(400, "Please provide a PGN file or paste PGN text.")

    meta = parse_pgn(raw_pgn)
    if not meta:
        raise HTTPException(400, "Could not parse PGN. Please check the format.")

    # Determine opponent info based on color
    if player_color == "white":
        opponent_name   = meta["black"]
        opponent_rating = meta["black_elo"]
    else:
        opponent_name   = meta["white"]
        opponent_rating = meta["white_elo"]

    # Map result to Neal's perspective
    result = meta["result"]
    if player_color == "black":
        result = {"win": "loss", "loss": "win", "draw": "draw"}.get(result, result)

    game = sb.table("games").insert({
        "player_id":       player["id"],
        "pgn":             raw_pgn,
        "color":           player_color,
        "result":          result,
        "opponent_name":   opponent_name,
        "opponent_rating": opponent_rating or None,
        "opening_eco":     meta["eco"],
        "opening_name":    meta["opening"],
        "tournament":      tournament or meta["event"],
        "played_at":       meta["date"],
    }).execute().data[0]

    # Auto-trigger analysis
    return RedirectResponse(f"/analysis/{game['id']}/run", status_code=303)


@router.get("/{game_id}", response_class=HTMLResponse)
async def view_game(request: Request, game_id: str):
    sb = get_supabase()
    game = sb.table("games").select("*, analyses(*)").eq("id", game_id).single().execute().data
    if not game:
        raise HTTPException(404, "Game not found")
    return templates.TemplateResponse("games/detail.html",
                                      {"request": request, "game": game})
