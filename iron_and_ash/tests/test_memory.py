"""Tests for the persistent, tiered memory system."""
from __future__ import annotations

import sqlite3

import pytest

from iron_and_ash.memory import Event, EventType, MemoryStore


@pytest.fixture
def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return MemoryStore(conn)


def _ev(day, etype, summary, actors=None, importance=2):
    return Event(game_day=day, type=etype, summary=summary,
                 actors=actors or [], importance=importance)


def test_events_are_appended_and_counted(store):
    store.record(_ev(0, EventType.MILESTONE, "A tale begins"))
    store.record(_ev(1, EventType.TRAVEL, "Went to Winterfell"))
    assert store.event_count() == 2
    ids = [e.id for e in store.all_events()]
    assert ids == sorted(ids) and all(i is not None for i in ids)


def test_log_is_append_only_and_never_truncates(store):
    for i in range(50):
        store.record(_ev(i, EventType.WORLD, f"beat {i}", importance=1))
    # summarising must not delete anything from the raw log
    store.summarize_period("Chronicle", up_to_day=40, importance_floor=1)
    assert store.event_count() == 50


def test_recent_events_returns_tail_in_order(store):
    for i in range(10):
        store.record(_ev(i, EventType.WORLD, f"beat {i}"))
    recent = store.recent_events(3)
    assert [e.summary for e in recent] == ["beat 7", "beat 8", "beat 9"]


def test_favor_and_betrayal_move_npc_disposition(store):
    store.record(_ev(1, EventType.FAVOR, "Helped Tobbot", actors=["merchant"]))
    assert store.npc_disposition("merchant") > 0
    store.record(_ev(2, EventType.BETRAYAL, "Betrayed Tobbot", actors=["merchant"]))
    assert store.npc_disposition("merchant") < 0


def test_disposition_is_clamped(store):
    for i in range(20):
        store.record(_ev(i, EventType.BETRAYAL, "again", actors=["foe"]))
    assert store.npc_disposition("foe") >= -100


def test_events_with_actor_filters_correctly(store):
    store.record(_ev(1, EventType.DIALOGUE, "spoke to A", actors=["npc_a"]))
    store.record(_ev(2, EventType.DIALOGUE, "spoke to B", actors=["npc_b"]))
    store.record(_ev(3, EventType.FAVOR, "helped A", actors=["npc_a"]))
    a_events = store.events_with_actor("npc_a")
    assert {e.summary for e in a_events} == {"spoke to A", "helped A"}


def test_working_memory_tiers(store):
    store.record(_ev(1, EventType.OATH, "Swore a great oath", importance=5))
    for i in range(10):
        store.record(_ev(2 + i, EventType.WORLD, f"trivia {i}", importance=1))
    wm = store.working_memory(recent=3)
    assert len(wm["recent"]) == 3
    # the high-importance oath surfaces as a landmark even though it is old
    assert any("great oath" in e.summary for e in wm["landmarks"])


def test_summarize_period_creates_digest_over_floor(store):
    store.record(_ev(1, EventType.OATH, "Swore fealty", importance=4))
    store.record(_ev(2, EventType.WORLD, "a dull day", importance=1))
    summary = store.summarize_period("The First Chronicle", up_to_day=5, importance_floor=3)
    assert summary is not None
    assert "fealty" in summary["text"]
    assert "dull day" not in summary["text"]  # below the importance floor
    assert store.summaries()[0]["title"] == "The First Chronicle"


def test_summarize_period_returns_none_when_nothing_qualifies(store):
    store.record(_ev(1, EventType.WORLD, "trivia", importance=1))
    assert store.summarize_period("Empty", up_to_day=5, importance_floor=4) is None
