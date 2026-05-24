# Neal's Chess Improvement App

A personalized AI chess coach built with FastAPI + Supabase + Claude.
Analyzes PGN games, tracks weakness patterns, and shows progress on an interactive chess board.

## Quick Start

### 1. Clone and install
```bash
git clone https://github.com/you/neal-chess
cd neal-chess
pip install -r requirements.txt
```

### 2. Set up Supabase (free)
1. Go to https://supabase.com and create a free project
2. Go to SQL Editor and paste + run the contents of `schema.sql`
3. Copy your project URL and anon key from Settings > API

### 3. Set up environment variables
```bash
cp .env.example .env
# Edit .env and fill in:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-anon-key
# ANTHROPIC_API_KEY=sk-ant-...
# SECRET_KEY=any-random-string
```

### 4. Run locally
```bash
uvicorn main:app --reload
# Open http://localhost:8000
```

## Deploy to Railway (free tier)
1. Push this repo to GitHub (private repo is fine)
2. Go to https://railway.app and create a new project from GitHub
3. Add the same environment variables in Railway's Variables tab
4. Railway detects FastAPI automatically and deploys

## Deploy to Render (free, but sleeps after 15min)
1. Push to GitHub
2. Create a new Web Service on https://render.com
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Features
- **PGN upload**: drag-and-drop or paste a PGN, analysis runs automatically
- **Interactive board**: click any key moment to jump to that position
- **Cross-game patterns**: weakness profile updated after every game
- **Study plan**: AI generates a personalized weekly plan from your pattern history
- **Coach chat**: ask questions about any game, move, or idea
- **Progress dashboard**: rating trajectory, opening stats, weakness trends

## The chess board
Uses `chessboard.js` (no install needed, loads from CDN). Key moments in the
analysis are linked to board positions — clicking a moment auto-jumps the board.
Arrows and square highlights are drawn on a canvas overlay.

## Adding more visual libraries (optional)
- **Stockfish evaluation bar**: add `stockfish.js` from CDN for engine eval overlay
- **Opening explorer**: link to Lichess opening explorer API for theory reference
- **Move arrows**: `chessground` (Lichess's own board) has built-in arrow support
  if you want richer visuals than chessboard.js

## Project structure
```
main.py              — FastAPI app entry point
db.py                — Supabase client + Claude coaching system prompt
schema.sql           — Run this in Supabase to create all tables
requirements.txt
routers/
  games.py           — Upload, list, view games
  analysis.py        — Claude analysis + weakness tracking
  dashboard.py       — Progress stats and charts
  profile.py         — Player profile + study plan generator
templates/
  base.html          — Navigation, chess board JS libraries loaded here
  games/
    list.html        — All games table
    detail.html      — Individual game with interactive board + chat
    upload.html      — PGN upload form
  dashboard/
    index.html       — Progress charts (Chart.js)
  profile/
    index.html       — Weakness profile
    study_plan.html  — AI-generated study plan
static/
  css/app.css        — Extra styles
  js/board.js        — Shared board helpers
```
