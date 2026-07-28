"""Tests for the structured lore library and codex study tracking."""
from __future__ import annotations

import random

from iron_and_ash.engine import codex
from iron_and_ash.world import lore
from iron_and_ash.world.models import WorldState


# -- data integrity -----------------------------------------------------------
def test_lore_loads_and_is_substantial():
    entries = lore.load_lore()
    assert len(entries) >= 50, "the lore library should be genuinely in-depth"


def test_every_category_is_populated():
    for category in lore.CATEGORIES:
        assert len(lore.entries_in(category)) >= 5, f"category '{category}' is thin"


def test_entries_have_required_fields():
    for entry in lore.load_lore().values():
        assert entry.id and entry.name and entry.summary
        assert entry.body and all(p.strip() for p in entry.body)
        assert entry.category in lore.CATEGORIES


def test_entry_ids_are_unique_and_lookup_works():
    entries = lore.load_lore()
    assert len({e.id for e in entries.values()}) == len(entries)
    assert lore.get("house_stark") is not None
    assert lore.get("no_such_entry") is None


def test_full_text_joins_paragraphs():
    entry = lore.get("house_stark")
    assert entry.full_text().count("\n\n") == len(entry.body) - 1


# -- search -------------------------------------------------------------------
def test_search_is_case_insensitive_and_finds_names():
    results = lore.search("WINTERFELL")
    assert any(e.id == "place_winterfell" for e in results)


def test_search_ranks_name_hits_before_body_hits():
    results = lore.search("dragon")
    assert results, "search for 'dragon' should hit"
    # the dragons legend entry names the term outright and should outrank
    # entries that only mention dragons in passing prose
    name_hits = [e for e in results if "dragon" in e.name.lower()]
    assert results.index(name_hits[0]) < len(results) - 1 or len(results) == len(name_hits)
    assert results[0].id in {e.id for e in name_hits}


def test_search_empty_query_returns_nothing():
    assert lore.search("") == []
    assert lore.search("   ") == []


def test_search_reaches_body_text():
    # "Nissa Nissa" appears only inside the Azor Ahai body prose
    results = lore.search("Nissa Nissa")
    assert any(e.id == "legend_azor_ahai" for e in results)


# -- random teaching ----------------------------------------------------------
def test_random_entry_respects_exclusions_and_categories():
    rng = random.Random(7)
    history_ids = {e.id for e in lore.entries_in("history")}
    picked = lore.random_entry(categories=["history"], rng=rng)
    assert picked.id in history_ids
    # excluding everything yields None
    assert lore.random_entry(exclude_ids=set(lore.load_lore())) is None


# -- codex study tracking -----------------------------------------------------
def test_studied_ids_roundtrip_through_world_flags():
    world = WorldState()
    assert codex.studied_ids(world) == set()
    codex.mark_studied(world, "house_stark")
    codex.mark_studied(world, "long_night")
    codex.mark_studied(world, "house_stark")  # idempotent
    assert codex.studied_ids(world) == {"house_stark", "long_night"}
    # flags store plain JSON, so it serialises with the save
    assert isinstance(world.flags[codex.STUDIED_FLAG], str)


def test_studied_ids_tolerates_missing_or_bad_flag():
    world = WorldState()
    assert codex.studied_ids(None) == set()
    world.flags[codex.STUDIED_FLAG] = "not json"
    assert codex.studied_ids(world) == set()
