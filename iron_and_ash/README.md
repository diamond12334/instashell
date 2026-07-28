# Iron & Ash

A persistent, single-player **text RPG set in the world of A Song of Ice and Fire**,
played in your terminal. This is a personal, non-commercial transformative fan
project — all narrative prose is original; the names, houses, and geography echo
George R. R. Martin's books without quoting them.

The design goal is a world that **remembers everything you do, forever**, built on
three first-class systems: deep character customization, an infinite tiered
memory system, and robust save/load.

## Playing on PC

Three ways to play, easiest first:

### 1. One-click launchers (recommended)

- **Windows** — double-click **`play.bat`**. On first run it finds your Python,
  sets up a private environment, and starts the game; after that it just plays.
  If Python isn't installed, it tells you exactly what to grab
  (python.org → tick *"Add python.exe to PATH"*).
- **Linux / macOS** — run **`./play.sh`**. Same deal: automatic first-run setup,
  then straight into the game.

Your saves live in your home folder (`~/.iron_and_ash/saves/`), so updating or
moving the game folder never touches them.

### 2. Standalone executable (no Python needed)

Build a single self-contained file — `iron-and-ash.exe` on Windows:

```bash
cd iron_and_ash
python -m pip install pyinstaller
python packaging/build_exe.py     # result appears in dist/
```

Build on the OS you want to play on (PyInstaller doesn't cross-compile). The
repository also ships a GitHub Actions workflow that builds Windows, macOS, and
Linux executables automatically on every push — grab them from the workflow run's
artifacts on GitHub.

### 3. Plain Python

```bash
cd iron_and_ash
python -m pip install -r requirements.txt   # rich + pydantic (see note below)
python -m iron_and_ash                      # or: python run_game.py
```

> **No dependencies? It still runs.** The game uses `rich` for colour and layout
> but falls back to plain `print`/`input` if it is missing. `pydantic` is used
> for the data models and is the one hard dependency.

Run the tests:

```bash
python -m pytest
```

> **No dependencies required.** The game runs on the Python standard library
> alone — `rich` and `pydantic` are optional (each has an automatic fallback).
> That's what lets it also run on a phone and in a browser.

## Play in the browser (desktop or iPhone — no install)

The quickest way to play, on any device, is the **self-contained web version** in
[`web/index.html`](web/index.html). It's a single HTML file — pure JavaScript, no
dependencies, no server, no download — that runs the game right in the browser and
saves your progress to the browser's storage.

- **Just open it.** Double-click `web/index.html`, or visit the GitHub Pages URL
  once it's deployed (below). On **iPhone/iPad**, open that URL in Safari and use
  **Share → Add to Home Screen** for a full-screen app icon.
- Works offline after first load; each browser keeps its own saved tales.
- Touch-friendly: everything is tappable buttons — no typing except names.

This browser edition is a streamlined port of the game: deep character creation,
the memory-driven journal, save/load with named slots, a lore codex, a realm map
with your position, and NPCs who remember how you treat them. The *complete*
engine — the 27-province strategic map, the army/war simulation, and every seat's
local scenes — lives in the Python version (see **Playing on PC**), and is also
available in the browser as an **experimental Pyodide build** at `pyodide.html`
that runs the actual Python code (~10 MB one-time download).

**Deploying to GitHub Pages (one-time, by the repo owner):** the included
`.github/workflows/pages.yml` publishes `web/` automatically. Enable it at
**Settings → Pages → Source: GitHub Actions**; the next push publishes it, and the
workflow summary shows the live URL (e.g. `https://<user>.github.io/<repo>/`).

## Playing on iPhone with the full Python engine (a-Shell — free)

Prefer a proper terminal? Install a free Python app from the App Store and run
the game directly (it needs no compiled packages):

1. Install **a-Shell** (free) from the App Store.
2. In a-Shell, download and enter the game:
   ```
   curl -L https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip -o iaa.zip
   unzip iaa.zip
   cd <repo>-<branch>/iron_and_ash      # tab-completion helps here
   ```
3. Play:
   ```
   python -m iron_and_ash
   ```
   (Optionally `pip install rich` first for colour — it's pure-Python and
   installs fine in a-Shell. The game works without it.)

Pyto and Pythonista work the same way. Tapping numbers on the keyboard drives
the menus.

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

## Where your tale begins, and the places you can walk

Local play is no longer confined to Winterfell. **Every** seat on the map can be
walked about, and you choose where to start:

- **Any famous seat.** Six great seats have **hand-authored** local scenes -
  King's Landing (the Mud Gate, the Street of Steel, the Red Keep, Flea Bottom),
  Casterly Rock, the Eyrie (the sky cells and the Moon Door), Storm's End,
  Highgarden, and Sunspear - each with its own locations and characters, on top
  of Winterfell.
- **Every other castle, town, and city.** A deterministic generator builds a
  sensible local scene for every remaining seat (a gatehouse, yard, hall, market,
  keep - scaled to whether it's a holdfast, castle, town, or city), populated with
  its own castellans, guards, traders, and townsfolk who remember how you treat
  them. Seatless wilds get a camp-and-trail scene. Generation is seeded and stored
  nowhere - the same place looks the same every session.
- **A seat of your own.** Choose *"Found your own seat, built to your design"* at
  character creation to raise a custom holding: pick the land, name it, choose its
  kind, and tune its **size, defenses, levy strength, and prosperity** yourself.
  It's attached to your house, grants you a title, and its levies are yours to
  call. (You can also found holdings mid-game from the map.)

Travelling the realm on the strategic map drops you straight into the local scene
of wherever you arrive, so the overworld and the ground-level game are one world.

## The strategic map & the wars of the realm

Beyond the streets of Winterfell lies the whole of Westeros and the nearer Free
Cities, reached from the in-game menu via **"The realm (map, travel & war)."**

- **An ASCII map with a live position tracker.** 27 provinces from Beyond the
  Wall to Volantis, drawn as a map with your position marked `@`, holdings `#`,
  and armed forces `x`/`!`. You travel province to province along authored roads
  and sea-lanes; time passes and the world turns while you march.
- **Fog of war.** You see only provinces you have discovered, plus what a distant
  observer could tell of the forces in them - an exact muster only for the men
  standing in your own province; a vaguer "a great host, bearing no banner you
  know" for everyone else.
- **Procedural holdings.** Every seat (Winterfell, the Eyrie, Casterly Rock...) is
  generated with a size, population, garrison, fortifications, and economy
  buildings that set its income and the levies it can raise. The *same* generator
  founds **your own** keep, castle, or town when you claim one - attached to your
  house, sworn or independent, granting you a title and levies of your own.
- **Reactive meetings.** Share a province with a lord in his hall or an army in
  the field and you can hail, parley, trade, negotiate, hire, recruit, bribe,
  duel, or give battle - the options and outcomes weigh your standing, your
  history together (from the memory system), the troop-strength disparity, and
  local custom (guest right binds a lord's hall). Inside Winterfell, NPCs already
  react to who you are to them the moment you enter a room.
- **A living military simulation.** Wars break out (and can be ended by exhaustion);
  hosts are mustered, free companies hired, and - in devastated, lawless country -
  bandit bands and outlaw gangs boil up. Every armed body is modelled with:
  - **troop composition** - levies, light foot, archers, men-at-arms, light horse,
    knights, sellswords, and siege specialists, each with its own combat weight,
    pay, and rations;
  - **logistics** - a baggage train measured in rations that empties as the army
    marches, refilled by foraging (better on friendly ground, worse in the waste),
    with attrition from terrain and winter;
  - **finances** - daily pay drawn from the war-chest; when the coin runs dry the
    men desert, and an unpaid free company will turn its coat and go outlaw;
  - **morale** - risen by victory, pay, and food; sunk by defeat, hunger, arrears,
    and distance from home; low morale means a weaker line and men slipping away in
    the night.

  Armies march toward their orders, fight when they meet an enemy (terrain aids the
  defender), and can seize provinces they conquer. You can call your own banners
  from your holdings, order your host to march, and lead it into battle.

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
│   ├── world/              # local world, plus the strategic map:
│   │                       #   mapdata/geography (provinces, terrain, roads),
│   │                       #   holdings (generator), military + campaign (war sim)
│   ├── narrative/          # memory-aware NPC dialogue and reaction logic
│   └── engine/             # game loop, mechanics, codex, and the map UI (mapview)
└── tests/                  # memory, save/load, and character-creation tests
```

## Current content (vertical slice)

A playable slice of **the North around Winterfell**: six connected locations, three
factions (Northern Lords, Free Folk, Night's Watch), and six NPCs with distinct,
memory-aware conversations, skill checks, quest hooks, and rippling consequences.
The systems are built to be extended — regions, NPCs, houses, quests, and traits are
all data-driven.

### The lore library

An in-depth, structured lore codex lives in `iron_and_ash/data/lore/` as JSON —
**70+ original-prose entries** across seven categories:

- **Houses** — the nine great houses plus notable minor houses (Bolton, Frey,
  Mormont, Reed, Umber, Manderly), each with words, sigil, seat, and a full history.
- **History** — a timeline from the Dawn Age through the Long Night, the Andal
  invasion, Valyria and its Doom, Aegon's Conquest, the Dance of the Dragons, the
  Blackfyre Rebellions, and Robert's Rebellion.
- **Faiths** — the old gods, the Seven, the Drowned God, R'hllor, and the
  Many-Faced God, each in depth.
- **Places** — Winterfell, the Wall, King's Landing, Harrenhal, the Citadel,
  Braavos, the ruins of Valyria, and more.
- **Legends & creatures** — the Others, dragons, direwolves, wargs and greenseers,
  Azor Ahai, the Night's King, the Rat Cook, the Horn of Winter.
- **Orders** — the Night's Watch, Kingsguard, maesters, Faceless Men, the
  Alchemists' Guild, the Golden Company.
- **Customs** — guest right, trial by combat, knighthood, fostering, tourneys,
  the iron price, and the wild seasons.

The in-game **codex** browses and full-text-searches all of it, and lore is woven
into play: Maester Wyllis teaches histories and the woods witch tells legends —
each lesson is marked in your codex, recorded as a `DISCOVERY` in the memory
system, and grants XP. Your "studies" progress persists in the save. Adding lore
means adding JSON entries — no code changes.

## Roadmap

- More regions of Westeros and Essos on the same location/faction/NPC data model.
- A main-quest arc layered over the emergent side content.
- Deeper tactical combat and an economy/holdings layer (land, titles, armies).
- Optional LLM narration layer over the existing memory API.

## Legal

A non-commercial fan work. A Song of Ice and Fire and its world are the creation of
George R. R. Martin. No book text is reproduced; all prose here is original.
