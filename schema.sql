-- Run this in your Supabase SQL editor

create table players (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  uscf_rating integer default 1806,
  lichess_username text,
  created_at timestamptz default now()
);

create table games (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references players(id) on delete cascade,
  pgn text not null,
  color text check (color in ('white','black')),
  result text check (result in ('win','loss','draw')),
  opponent_name text,
  opponent_rating integer,
  opening_eco text,
  opening_name text,
  tournament text,
  played_at date,
  created_at timestamptz default now()
);

create table analyses (
  id uuid primary key default gen_random_uuid(),
  game_id uuid references games(id) on delete cascade unique,
  verdict text,
  key_moments jsonb default '[]',
  strengths text[] default '{}',
  weaknesses text[] default '{}',
  coach_notes text,
  created_at timestamptz default now()
);

create table weakness_profile (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references players(id) on delete cascade,
  pattern_name text not null,
  occurrences integer default 1,
  severity text check (severity in ('critical','moderate','minor')) default 'moderate',
  trend text check (trend in ('improving','stable','worsening')) default 'stable',
  last_seen_at date default current_date,
  updated_at timestamptz default now(),
  unique(player_id, pattern_name)
);

-- Seed Neal as the default player
insert into players (name, uscf_rating, lichess_username)
values ('Neal Sundar', 1806, 'apolloarcher');
