"""
Neal's Chess Improvement App — FastAPI backend
Run with: uvicorn main:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers import games, analysis, dashboard, profile

app = FastAPI(title="Neal's Chess Coach", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Routers
app.include_router(games.router,     prefix="/games",    tags=["games"])
app.include_router(analysis.router,  prefix="/analysis", tags=["analysis"])
app.include_router(dashboard.router, prefix="/dashboard",tags=["dashboard"])
app.include_router(profile.router,   prefix="/profile",  tags=["profile"])

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
