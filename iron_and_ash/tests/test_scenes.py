"""Tests for local scenes: authored seats, the generator, resolver, and starts."""
from __future__ import annotations

from iron_and_ash.character.models import Character
from iron_and_ash.engine import startloc
from iron_and_ash.world import campaign, data as wdata, localgen, mapdata, seatscenes
from tests.conftest import ScriptedUI


def _fresh_world():
    world = wdata.new_world_state()
    campaign.ensure_map(world, "winterfell")
    return world


def _character():
    return Character(name="Aemon", house="House Frostwood", origin="bastard",
                     region="north", religion="old_gods", background="knight", gold=500)


# -- authored seat scenes -----------------------------------------------------
def test_authored_seats_loaded_with_entry_and_npcs():
    for pid in ("kings_landing", "casterly_rock", "the_eyrie", "storms_end",
                "highgarden", "sunspear"):
        assert pid in seatscenes.PROVINCE_ENTRY
        entry = seatscenes.PROVINCE_ENTRY[pid]
        assert entry in seatscenes.SCENE_LOCATIONS


def test_authored_scene_locations_interconnect():
    for loc in seatscenes.SCENE_LOCATIONS.values():
        for dest in loc.exits.values():
            assert dest in seatscenes.SCENE_LOCATIONS, f"{loc.id} -> {dest} dangles"


def test_authored_npcs_placed_in_new_world():
    world = wdata.new_world_state()
    # a King's Landing NPC exists and stands in its scene from the start
    assert "kl_goldcloak" in world.npcs
    assert world.npcs["kl_goldcloak"].location == "kl_gate"


def test_authored_scenes_merged_into_lookup():
    assert wdata.get_location("kl_keep") is not None
    assert wdata.get_npc("ss_steward") is not None
    assert wdata.province_of_location("cr_hall") == "casterly_rock"


# -- the generator ------------------------------------------------------------
def test_generator_is_deterministic():
    world = _fresh_world()
    a = localgen.scene_for_province(world, "riverrun")
    b = localgen.scene_for_province(world, "riverrun")
    assert a.entry == b.entry
    assert set(a.locations) == set(b.locations)


def test_generated_castle_scene_structure():
    world = _fresh_world()
    scene = localgen.scene_for_province(world, "riverrun")  # a castle seat
    assert scene.entry == "gen:riverrun:gate"
    assert set(scene.locations) == {"gen:riverrun:gate", "gen:riverrun:yard", "gen:riverrun:hall"}
    for loc in scene.locations.values():
        for dest in loc.exits.values():
            assert dest in scene.locations


def test_generated_wilds_for_seatless_province():
    world = _fresh_world()
    scene = localgen.scene_for_province(world, "beyond_wall")  # no seat
    assert scene.entry == "gen:beyond_wall:camp"


def test_generated_scene_themes_to_player_holding():
    from iron_and_ash.world import holdings
    world = _fresh_world()
    world.holdings["player_seat"] = holdings.generate_holding(
        "player_seat", "harrenhal", "House Mine", kind="castle",
        name="Mycastle", owner_is_player=True)
    themed = localgen.themed_holding(world, "harrenhal")
    assert themed.owner_is_player


# -- resolver -----------------------------------------------------------------
def test_entry_for_province_authored_vs_generated():
    world = _fresh_world()
    assert wdata.entry_for_province(world, "kings_landing") == "kl_gate"
    assert wdata.entry_for_province(world, "winterfell") == wdata.STARTING_LOCATION
    assert wdata.entry_for_province(world, "riverrun").startswith("gen:riverrun:")


def test_ensure_local_places_generated_npcs():
    world = _fresh_world()
    entry = wdata.entry_for_province(world, "pyke")
    assert entry.startswith("gen:pyke:")
    # before entering, the generated NPCs are not yet in the world
    assert not any(n.startswith("gnpc:pyke") for n in world.npcs)
    wdata.ensure_local(world, entry)
    placed = [n for n in world.npcs if n.startswith("gnpc:pyke")]
    assert placed
    # and they resolve to real definitions
    assert wdata.get_npc(placed[0], world) is not None


def test_get_location_resolves_generated():
    world = _fresh_world()
    loc = wdata.get_location("gen:riverrun:hall", world)
    assert loc is not None and "Hall" in loc.name


def test_province_of_generated_location():
    assert wdata.province_of_location("gen:pyke:gate") == "pyke"


# -- start selection ----------------------------------------------------------
def test_start_at_winterfell():
    world = wdata.new_world_state()
    char = _character()
    startloc.choose_start(ScriptedUI(menu=[0]), char, world)
    assert char.location == wdata.STARTING_LOCATION
    assert world.player_province == "winterfell"


def test_start_at_famous_seat():
    world = wdata.new_world_state()
    char = _character()
    seats = startloc._seat_provinces()
    ki = next(i for i, p in enumerate(seats) if p.id == "kings_landing")
    startloc.choose_start(ScriptedUI(menu=[1, ki]), char, world)
    assert char.location == "kl_gate"
    assert world.player_province == "kings_landing"


def test_found_custom_holding_with_chosen_stats():
    world = wdata.new_world_state()
    char = _character()
    provinces = [p for p in mapdata.PROVINCES.values()
                 if p.id not in seatscenes.PROVINCE_ENTRY and p.id != "winterfell"]
    pi = next(i for i, p in enumerate(provinces) if p.id == "riverrun")
    ui = ScriptedUI(menu=[2, pi, 1, 1, 1, 1], ask=["Ravenhold"], confirm=[False])
    startloc.choose_start(ui, char, world)

    h = world.holdings["player_seat"]
    assert h.owner_is_player and h.name == "Ravenhold"
    assert h.population == startloc._SIZE[1][2]
    assert h.defense == startloc._DEFENSE[1][1]
    assert h.income == startloc._PROSPERITY[1][1]
    assert h.levy_potential() == startloc._LEVY[1][1]
    assert "Lord of Ravenhold" in char.titles
    assert world.player_province == "riverrun"
    assert char.location.startswith("gen:riverrun:")
    # the seat's own folk have been placed
    assert any(n.startswith("gnpc:riverrun") for n in world.npcs)
