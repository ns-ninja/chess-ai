"""Profile router — view and update player profile."""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_supabase, get_anthropic, COACH_SYSTEM_PROMPT

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def profile(request: Request):
    sb = get_supabase()
    player = sb.table("players").select("*").limit(1).execute().data[0]
    weakness_profile = (sb.table("weakness_profile")
                          .select("*")
                          .eq("player_id", player["id"])
                          .order("occurrences", desc=True)
                          .execute().data)
    games_count = (sb.table("games")
                     .select("id", count="exact")
                     .eq("player_id", player["id"])
                     .execute().count)
    return templates.TemplateResponse("profile/index.html", {
        "request": request,
        "player": player,
        "weakness_profile": weakness_profile,
        "games_count": games_count or 0,
    })


@router.post("/update-rating")
async def update_rating(rating: int = Form(...)):
    sb = get_supabase()
    player = sb.table("players").select("*").limit(1).execute().data[0]
    sb.table("players").update({"uscf_rating": rating}).eq("id", player["id"]).execute()
    return RedirectResponse("/profile/", status_code=303)


@router.get("/study-plan", response_class=HTMLResponse)
async def study_plan(request: Request):
    """Generate a personalized study plan from Claude based on current weakness profile."""
    sb = get_supabase()
    ai = get_anthropic()

    player = sb.table("players").select("*").limit(1).execute().data[0]
    profile = (sb.table("weakness_profile")
                 .select("*")
                 .eq("player_id", player["id"])
                 .order("occurrences", desc=True)
                 .execute().data)

    games_count = (sb.table("games")
                     .select("id", count="exact")
                     .eq("player_id", player["id"])
                     .execute().count) or 0

    profile_text = "\n".join(
        f"- {p['pattern_name']}: {p['occurrences']} occurrences, "
        f"severity={p['severity']}, trend={p['trend']}"
        for p in profile
    ) or "No patterns recorded yet — upload some games first."

    prompt = f"""Based on Neal's current weakness profile from {games_count} analyzed games,
create a personalized 4-week study plan.

WEAKNESS PROFILE:
{profile_text}

Format as JSON:
{{
  "weekly_plans": [
    {{
      "week": 1,
      "focus": "main topic",
      "daily_tasks": ["task 1 (15 min)", "task 2 (20 min)"],
      "resources": ["resource 1", "resource 2"],
      "goal": "what success looks like"
    }}
  ],
  "immediate_priority": "the single most important thing to do this week",
  "motivational_note": "encouraging note about Neal's progress and potential"
}}"""

    response = ai.messages.create(
        model="claude-sonnet-4-5-20251001",
        max_tokens=1500,
        system=COACH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    import json
    try:
        plan = json.loads(raw.strip())
    except Exception:
        plan = {"weekly_plans": [], "immediate_priority": raw[:300], "motivational_note": ""}

    return templates.TemplateResponse("profile/study_plan.html", {
        "request": request,
        "player": player,
        "plan": plan,
        "profile": profile,
    })
