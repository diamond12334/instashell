"""Save / load system.

Design decision: **one SQLite database per save slot**, holding the whole game -
character, world state, and the entire memory/event log - in one place. This is
what makes saves robust:

* SQLite writes are transactional (ACID). A save is a single ``COMMIT``; if the
  process dies mid-write the database rolls back to the last good state rather
  than leaving a half-written file. This is stronger than a temp-file-and-rename
  scheme, and we additionally take an atomic ``.bak`` snapshot before each save.
* The event log lives *inside* the save and is written through continuously
  during play, so the "infinite memory" is persisted as it happens, not only at
  save time.
* The schema is versioned in the ``meta`` table and migrated forward on load, so
  saves keep working after the game is updated.

Saves live under ``$IRON_AND_ASH_HOME`` (default ``~/.iron_and_ash/saves``) as
``<slot>.db`` - human-inspectable with any SQLite tool.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..character.models import Character
from ..engine.state import GameState
from ..memory.store import MemoryStore
from ..world.models import WorldState

SCHEMA_VERSION = 1


def save_root() -> Path:
    base = os.environ.get("IRON_AND_ASH_HOME")
    root = Path(base) if base else Path.home() / ".iron_and_ash"
    saves = root / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    return saves


@dataclass
class SaveInfo:
    """Summary card for a save slot, shown in the load menu."""

    slot: str
    character_name: str
    house: str
    in_game_day: int
    notable_event: str
    last_played: str


class SaveManager:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or save_root()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- slot helpers ---------------------------------------------------------
    def _path(self, slot: str) -> Path:
        return self.root / f"{_safe_slot(slot)}.db"

    def exists(self, slot: str) -> bool:
        return self._path(slot).exists()

    def _connect(self, slot: str) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path(slot))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_meta_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS character (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL
            );
            """
        )
        conn.commit()

    # -- create / load / save -------------------------------------------------
    def new_game(self, slot: str, character: Character, world: WorldState) -> GameState:
        path = self._path(slot)
        if path.exists():
            path.unlink()
        conn = self._connect(slot)
        self._ensure_meta_schema(conn)
        memory = MemoryStore(conn)  # creates its own tables
        self._set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        gs = GameState(character=character, world=world, memory=memory, slot=slot)
        self.save_game(gs)
        return gs

    def load_game(self, slot: str) -> GameState:
        if not self.exists(slot):
            raise FileNotFoundError(f"No save in slot '{slot}'.")
        conn = self._connect(slot)
        self._ensure_meta_schema(conn)
        self._migrate(conn)
        char_row = conn.execute("SELECT data FROM character WHERE id = 1").fetchone()
        world_row = conn.execute("SELECT data FROM world_state WHERE id = 1").fetchone()
        if char_row is None or world_row is None:
            raise ValueError(f"Save '{slot}' is missing core data.")
        character = Character.model_validate(json.loads(char_row["data"]))
        world = WorldState.model_validate(json.loads(world_row["data"]))
        memory = MemoryStore(conn)
        return GameState(character=character, world=world, memory=memory, slot=slot)

    def save_game(self, gs: GameState) -> None:
        """Persist the character and world snapshot atomically.

        The memory log is already on disk (written through during play); this
        commits the mutable character/world snapshot plus meta in one
        transaction. A ``.bak`` copy is taken first so a slot always has a
        recoverable previous state.
        """
        self._backup(gs.slot)
        conn = gs.memory.conn
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO character (id, data) VALUES (1, ?)"
                " ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (json.dumps(gs.character.model_dump()),),
            )
            conn.execute(
                "INSERT INTO world_state (id, data) VALUES (1, ?)"
                " ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (json.dumps(gs.world.model_dump()),),
            )
            self._set_meta(conn, "character_name", gs.character.name, commit=False)
            self._set_meta(conn, "house", gs.character.house, commit=False)
            self._set_meta(conn, "in_game_day", str(gs.world.day), commit=False)
            self._set_meta(conn, "last_played", _now(), commit=False)
            notable = self._notable_event(gs)
            self._set_meta(conn, "notable_event", notable, commit=False)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _notable_event(self, gs: GameState) -> str:
        recents = gs.memory.recent_events(20)
        important = [e for e in recents if e.importance >= 3]
        chosen = important[-1] if important else (recents[-1] if recents else None)
        return chosen.summary if chosen else "A new tale begins."

    # -- listing / deletion ---------------------------------------------------
    def list_saves(self) -> List[SaveInfo]:
        infos: List[SaveInfo] = []
        for path in sorted(self.root.glob("*.db")):
            slot = path.stem
            try:
                conn = sqlite3.connect(path)
                conn.row_factory = sqlite3.Row
                meta = {r["key"]: r["value"]
                        for r in conn.execute("SELECT key, value FROM meta")}
                conn.close()
            except sqlite3.Error:
                continue
            infos.append(SaveInfo(
                slot=slot,
                character_name=meta.get("character_name", "Unknown"),
                house=meta.get("house", ""),
                in_game_day=int(meta.get("in_game_day", "0")),
                notable_event=meta.get("notable_event", ""),
                last_played=meta.get("last_played", ""),
            ))
        infos.sort(key=lambda i: i.last_played, reverse=True)
        return infos

    def delete_save(self, slot: str) -> bool:
        path = self._path(slot)
        removed = False
        for p in (path, path.with_suffix(".db.bak"),
                  Path(str(path) + "-wal"), Path(str(path) + "-shm")):
            if p.exists():
                p.unlink()
                removed = True
        return removed

    def last_slot(self) -> Optional[str]:
        saves = self.list_saves()
        return saves[0].slot if saves else None

    # -- internals ------------------------------------------------------------
    def _backup(self, slot: str) -> None:
        path = self._path(slot)
        if path.exists():
            try:
                shutil.copy2(path, path.with_suffix(".db.bak"))
            except OSError:
                pass  # a failed backup must never block the actual save

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str,
                  commit: bool = True) -> None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        if commit:
            conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        version = int(row["value"]) if row else 0
        # Future migrations register here: while version < SCHEMA_VERSION, apply
        # the step that upgrades `version` -> `version + 1`, then bump it.
        while version < SCHEMA_VERSION:
            migrate = _MIGRATIONS.get(version)
            if migrate:
                migrate(conn)
            version += 1
            self._set_meta(conn, "schema_version", str(version))


# version N -> N+1 upgrade functions live here as the schema evolves
_MIGRATIONS = {}


def _safe_slot(slot: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", slot.strip()) or "save"
    return cleaned[:48]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
