"""Tests for the save / load system: round-trips, slots, atomicity, migration."""
from __future__ import annotations

from iron_and_ash.character.models import Attributes, Character
from iron_and_ash.memory import Event, EventType
from iron_and_ash.persistence.saves import SCHEMA_VERSION, SaveManager
from iron_and_ash.world import data as wdata


def _make_character(name="Test Stark"):
    return Character(
        name=name, house="House Stark", origin="stark", region="north",
        religion="old_gods", background="knight",
        attributes=Attributes(might=7, agility=5, cunning=4, presence=4, will=5, lore=3),
        location=wdata.STARTING_LOCATION, gold=120,
    )


def test_new_game_and_load_roundtrip(save_home):
    mgr = SaveManager()
    char = _make_character()
    world = wdata.new_world_state()
    gs = mgr.new_game("slot1", char, world)
    gs.memory.record(Event(game_day=0, type=EventType.MILESTONE,
                           summary="Began the tale", importance=4))
    gs.world.day = 12
    gs.world.adjust_reputation("north_lords", 25)
    mgr.save_game(gs)

    loaded = mgr.load_game("slot1")
    assert loaded.character.name == "Test Stark"
    assert loaded.character.attributes.might == 7
    assert loaded.world.day == 12
    assert loaded.world.reputation("north_lords") == 25
    # the memory log persisted with the save
    assert loaded.memory.event_count() == 1
    assert loaded.memory.all_events()[0].summary == "Began the tale"


def test_full_memory_log_survives_save_load(save_home):
    mgr = SaveManager()
    gs = mgr.new_game("epic", _make_character(), wdata.new_world_state())
    for i in range(100):
        gs.memory.record(Event(game_day=i, type=EventType.WORLD,
                               summary=f"day {i}", importance=1))
    mgr.save_game(gs)
    loaded = mgr.load_game("epic")
    assert loaded.memory.event_count() == 100  # nothing lost


def test_multiple_named_slots_are_independent(save_home):
    mgr = SaveManager()
    mgr.new_game("north", _make_character("Ned"), wdata.new_world_state())
    mgr.new_game("south", _make_character("Tyrion"), wdata.new_world_state())
    names = {i.character_name for i in mgr.list_saves()}
    assert names == {"Ned", "Tyrion"}


def test_list_saves_reports_summary_card(save_home):
    mgr = SaveManager()
    gs = mgr.new_game("card", _make_character("Jon"), wdata.new_world_state())
    gs.world.day = 7
    gs.memory.record(Event(game_day=7, type=EventType.OATH,
                           summary="Swore a mighty oath", importance=4))
    mgr.save_game(gs)
    info = next(i for i in mgr.list_saves() if i.slot == "card")
    assert info.character_name == "Jon"
    assert info.in_game_day == 7
    assert "oath" in info.notable_event.lower()


def test_delete_save_removes_slot(save_home):
    mgr = SaveManager()
    mgr.new_game("temp", _make_character(), wdata.new_world_state())
    assert mgr.exists("temp")
    assert mgr.delete_save("temp") is True
    assert not mgr.exists("temp")


def test_last_slot_tracks_most_recent(save_home):
    mgr = SaveManager()
    mgr.new_game("first", _make_character("A"), wdata.new_world_state())
    gs = mgr.new_game("second", _make_character("B"), wdata.new_world_state())
    mgr.save_game(gs)  # second is most recently played
    assert mgr.last_slot() == "second"


def test_schema_version_recorded_and_backup_made(save_home):
    mgr = SaveManager()
    gs = mgr.new_game("v", _make_character(), wdata.new_world_state())
    mgr.save_game(gs)
    # schema version stored in meta
    row = gs.memory.conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert int(row["value"]) == SCHEMA_VERSION
    # an atomic backup exists after a save
    assert (mgr.root / "v.db.bak").exists()


def test_slot_name_is_sanitised(save_home):
    mgr = SaveManager()
    mgr.new_game("../evil name!!", _make_character(), wdata.new_world_state())
    # the dangerous characters are stripped; a normal file is created safely
    files = list(mgr.root.glob("*.db"))
    assert len(files) == 1
    assert ".." not in files[0].name
