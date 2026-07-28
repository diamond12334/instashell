# Iron & Ash

A persistent, single-player **text RPG set in the world of A Song of Ice and Fire**,
played in your terminal. This is a personal, non-commercial transformative fan
project — all narrative prose is original; the names, houses, and geography echo
George R. R. Martin's books without quoting them.

The design goal is a world that **remembers everything you do, forever**, built on
three first-class systems: deep character customization, an infinite tiered
memory system, and robust save/load.

## Quick start

```bash
cd iron_and_ash
python -m pip install -r requirements.txt   # rich + pydantic (see note below)
python -m iron_and_ash
```

> **No dependencies? It still runs.** The game uses `rich` for colour and layout
> but falls back to plain `print`/`input` if it is missing. `pydantic` is used
> for the data models and is the one hard dependency.

Run the tests:

```bash
python -m pytest
```

## The three pillars

### 1. Deep character customization
Character creation offers a one-key **quick start** or a full **custom** path:

- **Origin** — a Great House (Stark, Lannister, Targaryen loyalist, Baratheon,
  Tyrell, Martell, Greyjoy, Tully, Arryn) or a humbler start (smallfolk, highborn
  bastard, sellsword, maester's apprentice, Night's Watch recruit, Free City exile).
- **Region of birth**, **religion**, and **background** (knight, spy, healer,
  smuggler, scholar, hunter) — each shaping starting skills, gear, gold, and standing.
- **Attributes** via point-buy (Might, Agility, Cunning, Presence, Will, Lore).
- **Traits & flaws** (Silver Tongue, Warg-touched, Craven, Kinslayer's Guilt, …)
  that change skill checks and how the world treats you.
- **Identity** — name, gender (free text, described respectfully), appearance, motto.

### 2. Infinite, tiered memory system
The backbone. Everything meaningful becomes an append-only **event** in SQLite that
is *never* truncated — the raw record is always there. On top of the permanent log:

- **Long-term store** — the full `events` table, the canonical history.
- **Working memory** — a cheap query surfacing what matters now (recent events plus
  high-importance landmarks from all of history) for the journal and NPC dialogue.
- **Semantic summarization** — old events are periodically folded into narrative
  "chronicle" digests so the game can recall their *meaning* cheaply, while the raw
  events remain untouched.
- **NPC memory** — every NPC tracks a per-individual disposition and the specific
  events that shaped it, and will quote that history back at you in conversation.
- **World reactivity** — consequences ripple: help or wrong someone and, days later,
  aid arrives or a reprisal finds you. Time passes and the world turns between and
  within sessions.

The memory API is deliberately clean so a future version could plug in an LLM for
dynamic narration — but the base game is fully deterministic and offline.

### 3. Save / load
- **One SQLite database per save slot** holding the entire game — character, world
  state, and the complete memory log — under `~/.iron_and_ash/saves/<slot>.db`
  (override with `$IRON_AND_ASH_HOME`).
- **Crash-safe by construction:** each save is a single transactional `COMMIT`;
  a failure rolls back rather than corrupting the file, and a `.bak` snapshot is
  taken before every save.
- **Named slots**, **autosave** (on travel, key interactions, and exit), and a
  **"Continue"** option for the most recent tale.
- **Versioned schema with forward migrations**, so old saves keep loading after updates.
- The load menu shows a summary card per save: character, house, in-game day, and a
  notable recent event.

## Project layout

```
iron_and_ash/
├── iron_and_ash/
│   ├── __main__.py         # `python -m iron_and_ash`
│   ├── app.py              # main menu / orchestration
│   ├── ui/console.py       # terminal rendering (rich, with plain fallback)
│   ├── character/          # models, lore data, creation flow
│   ├── memory/             # events + tiered SQLite memory store
│   ├── persistence/        # save/load, slots, atomicity, migration
│   ├── world/              # geography, factions, NPCs, reactivity
│   ├── narrative/          # memory-aware NPC dialogue
│   └── engine/             # game loop, mechanics (skill checks, combat), codex
└── tests/                  # memory, save/load, and character-creation tests
```

## Current content (vertical slice)

A playable slice of **the North around Winterfell**: six connected locations, three
factions (Northern Lords, Free Folk, Night's Watch), and six NPCs with distinct,
memory-aware conversations, skill checks, quest hooks, and rippling consequences.
The systems are built to be extended — regions, NPCs, houses, quests, and traits are
all data-driven.

## Roadmap

- More regions of Westeros and Essos on the same location/faction/NPC data model.
- A main-quest arc layered over the emergent side content.
- Deeper tactical combat and an economy/holdings layer (land, titles, armies).
- Optional LLM narration layer over the existing memory API.

## Legal

A non-commercial fan work. A Song of Ice and Fire and its world are the creation of
George R. R. Martin. No book text is reproduced; all prose here is original.
