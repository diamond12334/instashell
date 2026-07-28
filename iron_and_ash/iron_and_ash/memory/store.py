"""SQLite-backed memory store - the persistent, tiered memory system.

Design
------
Each save slot is a single SQLite database. The memory store owns three of its
tables and exposes the tiered model described in the brief:

* **Long-term store** - the ``events`` table. Append-only, never truncated. This
  is the canonical, "infinite" record of everything that has happened.
* **Working / active memory** - :meth:`working_memory`, a cheap query that
  surfaces what is currently relevant (recent + high-importance events, plus the
  running summaries) so the game can remind the player and NPCs what matters now.
* **Semantic summarisation** - :meth:`summarize_period`, which folds a span of
  old events into a single narrative summary row. The raw events remain; the
  summary just gives a cheap way to recall their *meaning*.

NPC memory lives in ``npc_memory``: a per-individual disposition plus the ids of
the events that shaped it, so an NPC can reference specific history in dialogue.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional

from .events import Event, EventType


class MemoryStore:
    """Owns the memory tables inside a save database.

    The store does not open or close the connection itself; it is handed a live
    :class:`sqlite3.Connection` so that the whole save (character, world, memory)
    shares one transactional database and one atomic commit.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                game_day   INTEGER NOT NULL,
                type       TEXT    NOT NULL,
                summary    TEXT    NOT NULL,
                actors     TEXT    NOT NULL DEFAULT '[]',
                location   TEXT,
                importance INTEGER NOT NULL DEFAULT 2,
                data       TEXT    NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_events_day ON events(game_day);
            CREATE INDEX IF NOT EXISTS idx_events_importance ON events(importance);

            CREATE TABLE IF NOT EXISTS summaries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                title          TEXT NOT NULL,
                text           TEXT NOT NULL,
                span_start_day INTEGER NOT NULL,
                span_end_day   INTEGER NOT NULL,
                event_count    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS npc_memory (
                npc_id        TEXT PRIMARY KEY,
                disposition   INTEGER NOT NULL DEFAULT 0,
                last_seen_day INTEGER,
                notes         TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        self.conn.commit()

    # -- writing --------------------------------------------------------------
    def record(self, event: Event) -> Event:
        """Append an event to the permanent log. Returns it with its ``id`` set.

        Also nudges the disposition of any NPC actors when the event type carries
        an obvious valence, so being helped or wronged is remembered per person.
        """
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO events (game_day, type, summary, actors, location, importance, data)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.game_day,
                event.type.value,
                event.summary,
                json.dumps(event.actors),
                event.location,
                event.importance,
                json.dumps(event.data),
            ),
        )
        event.id = cur.lastrowid
        delta = _DISPOSITION_DELTA.get(event.type, 0)
        for actor in event.actors:
            self.remember_about_npc(actor, event, disposition_delta=delta)
        self.conn.commit()
        return event

    def remember_about_npc(self, npc_id: str, event: Event,
                           disposition_delta: int = 0) -> None:
        """Attach an event to an NPC's memory and shift their disposition.

        Disposition is clamped to [-100, 100]. The ``notes`` list keeps the ids
        and one-line summaries of the events that shaped this NPC's view, so
        dialogue can quote specific history back at the player.
        """
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT disposition, notes FROM npc_memory WHERE npc_id = ?", (npc_id,)
        ).fetchone()
        if row is None:
            disposition, notes = 0, []
        else:
            disposition, notes = row[0], json.loads(row[1])
        disposition = max(-100, min(100, disposition + disposition_delta))
        if event.id is not None:
            notes.append({"event_id": event.id, "day": event.game_day, "summary": event.summary})
            notes = notes[-50:]  # keep the memory bounded per-NPC; raw log is intact
        cur.execute(
            "INSERT INTO npc_memory (npc_id, disposition, last_seen_day, notes)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(npc_id) DO UPDATE SET"
            " disposition=excluded.disposition,"
            " last_seen_day=excluded.last_seen_day,"
            " notes=excluded.notes",
            (npc_id, disposition, event.game_day, json.dumps(notes)),
        )
        self.conn.commit()

    # -- reading --------------------------------------------------------------
    def all_events(self, limit: Optional[int] = None) -> List[Event]:
        q = "SELECT * FROM events ORDER BY id"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [self._row_to_event(r) for r in self.conn.execute(q)]

    def recent_events(self, count: int = 10) -> List[Event]:
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (count,)
        ).fetchall()
        return [self._row_to_event(r) for r in reversed(rows)]

    def events_with_actor(self, npc_id: str, count: int = 20) -> List[Event]:
        """Every remembered happening involving a given NPC/faction."""
        rows = self.conn.execute(
            "SELECT * FROM events WHERE actors LIKE ? ORDER BY id DESC LIMIT ?",
            (f'%"{npc_id}"%', count),
        ).fetchall()
        return [self._row_to_event(r) for r in reversed(rows)]

    def event_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def npc_disposition(self, npc_id: str) -> int:
        row = self.conn.execute(
            "SELECT disposition FROM npc_memory WHERE npc_id = ?", (npc_id,)
        ).fetchone()
        return row[0] if row else 0

    def working_memory(self, recent: int = 8, importance_floor: int = 4) -> Dict[str, list]:
        """The active-memory tier: what is relevant right now.

        Combines the most recent events with any high-importance events from the
        whole history, plus the running narrative summaries. This is what the
        game surfaces in the journal and hands to any narration layer.
        """
        recents = self.recent_events(recent)
        recent_ids = {e.id for e in recents}
        landmark_rows = self.conn.execute(
            "SELECT * FROM events WHERE importance >= ? ORDER BY id DESC LIMIT 12",
            (importance_floor,),
        ).fetchall()
        landmarks = [self._row_to_event(r) for r in landmark_rows if r["id"] not in recent_ids]
        return {
            "recent": recents,
            "landmarks": list(reversed(landmarks)),
            "summaries": self.summaries(),
        }

    def summaries(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM summaries ORDER BY span_start_day"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- summarisation --------------------------------------------------------
    def summarize_period(self, title: str, up_to_day: int,
                         importance_floor: int = 3) -> Optional[dict]:
        """Fold events up to ``up_to_day`` into one narrative summary row.

        The raw events are left untouched (the log never truncates); this only
        adds a cheap, human-readable digest of what those days meant. Only events
        at or above ``importance_floor`` shape the digest so trivia is skipped.
        Returns the created summary, or ``None`` if there was nothing worth
        summarising.
        """
        rows = self.conn.execute(
            "SELECT * FROM events WHERE game_day <= ? AND importance >= ? ORDER BY id",
            (up_to_day, importance_floor),
        ).fetchall()
        if not rows:
            return None
        events = [self._row_to_event(r) for r in rows]
        start = min(e.game_day for e in events)
        highlights = [e.summary for e in sorted(events, key=lambda e: -e.importance)][:6]
        text = "; ".join(highlights) + "."
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO summaries (title, text, span_start_day, span_end_day, event_count)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, text, start, up_to_day, len(events)),
        )
        self.conn.commit()
        return {
            "id": cur.lastrowid, "title": title, "text": text,
            "span_start_day": start, "span_end_day": up_to_day, "event_count": len(events),
        }

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            game_day=row["game_day"],
            type=EventType(row["type"]),
            summary=row["summary"],
            actors=json.loads(row["actors"]),
            location=row["location"],
            importance=row["importance"],
            data=json.loads(row["data"]),
        )


# How much each event type shifts an involved NPC's disposition toward the player.
_DISPOSITION_DELTA: Dict[EventType, int] = {
    EventType.FAVOR: 12,
    EventType.SLIGHT: -12,
    EventType.OATH: 8,
    EventType.OATH_BROKEN: -25,
    EventType.ALLIANCE: 15,
    EventType.BETRAYAL: -40,
    EventType.MARRIAGE: 20,
}
