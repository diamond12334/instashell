"""Tests for the strategic map: geography, holdings, military sim, campaign."""
from __future__ import annotations

import json
import random
import sqlite3

import pytest

from iron_and_ash.memory.store import MemoryStore
from iron_and_ash.world import campaign, geography, holdings, mapdata, military
from iron_and_ash.world.models import WorldState


@pytest.fixture
def memory():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return MemoryStore(conn)


# -- geography ----------------------------------------------------------------
def test_adjacency_is_symmetric():
    for pid, nbrs in mapdata.ADJACENCY.items():
        for n in nbrs:
            assert pid in mapdata.ADJACENCY[n], f"{pid}->{n} not mirrored"


def test_every_province_is_reachable_from_winterfell():
    for pid in mapdata.PROVINCES:
        assert geography.distance("winterfell", pid) >= 0, f"{pid} unreachable"


def test_step_toward_advances_along_path():
    path = geography.bfs_path("winterfell", "kings_landing")
    assert path[0] == "winterfell" and path[-1] == "kings_landing"
    step = geography.step_toward("winterfell", "kings_landing")
    assert step == path[1]


# -- holdings -----------------------------------------------------------------
def test_generate_holding_is_deterministic_with_seed():
    a = holdings.generate_holding("h1", "winterfell", "House Test",
                                  kind="castle", rng=random.Random(1))
    b = holdings.generate_holding("h1", "winterfell", "House Test",
                                  kind="castle", rng=random.Random(1))
    assert a.model_dump() == b.model_dump()


def test_holding_stats_scale_with_kind():
    rng = random.Random(5)
    keep = holdings.generate_holding("k", "winterfell", "H", kind="keep", rng=rng)
    city = holdings.generate_holding("c", "white_harbor", "H", kind="city", rng=rng)
    assert city.population > keep.population
    assert city.levy_potential() > keep.levy_potential()


def test_holding_has_economy_and_defenses():
    h = holdings.generate_holding("h", "winterfell", "H", kind="castle",
                                  rng=random.Random(3))
    assert h.buildings and h.defense_works
    assert h.income > 0 and h.garrison > 0
    assert h.defense >= holdings.KIND_PROFILE["castle"]["defense"]


def test_generated_names_are_nonempty():
    rng = random.Random(9)
    assert holdings.generate_house_name(rng).startswith("House ")
    assert holdings.generate_holding_name("city", rng)


# -- military: composition & derived stats ------------------------------------
def _test_army(**over):
    base = dict(id="a1", name="Test Host", kind="host", allegiance="north_lords",
                province="winterfell", home_province="winterfell",
                composition={"levies": 500, "archers": 200, "knights": 100},
                morale=60, coffers=100000)
    base.update(over)
    army = military.Army(**base)
    if "supplies" not in over:
        # a full baggage train: ~40 days of rations for this host
        army.supplies = army.daily_rations() * 40
    return army


def test_army_derived_quantities():
    army = _test_army()
    assert army.strength() == 800
    assert army.combat_power() > 0
    assert army.daily_pay() > 0
    assert army.daily_rations() > 0


def test_well_supplied_paid_army_holds_together():
    army = _test_army()
    before = army.strength()
    for _ in range(10):
        military.tick_army(None_world(), army, 1, random.Random(2))
    # small attrition only; no collapse
    assert army.strength() >= before * 0.8
    assert not army.disbanded


def test_starving_unpaid_army_bleeds_and_deserts():
    army = _test_army(supplies=0.0, coffers=0)
    before = army.strength()
    for _ in range(8):
        military.tick_army(None_world(), army, 1, random.Random(2))
    assert army.strength() < before          # men desert
    assert army.days_unfed > 0 or army.days_unpaid > 0


def test_unpaid_free_company_can_turn_outlaw():
    army = _test_army(kind="free_company", allegiance="lannister", coffers=0,
                      composition={"mercenaries": 400, "archers": 100})
    turned = False
    for _ in range(20):
        events = military.tick_army(None_world(), army, 1, random.Random(7))
        if army.kind == "outlaws":
            turned = True
            break
    assert turned, "an unpaid sellsword company should eventually turn outlaw"


def test_resolve_battle_produces_winner_and_casualties():
    big = _test_army(id="big", composition={"levies": 2000, "knights": 300})
    small = _test_army(id="small", allegiance="lannister",
                       composition={"levies": 400}, province="winterfell")
    b0, s0 = big.strength(), small.strength()
    winner_id, lines = military.resolve_battle(None_world(), big, small, random.Random(1))
    assert winner_id == "big"
    assert small.strength() < s0            # loser bleeds most
    assert big.strength() <= b0             # winner still pays a price
    assert big.morale >= 60                 # victor's morale rises
    assert lines


def test_spawn_helpers_make_valid_bands():
    w = None_world()
    band = military.form_bandits(w, "harrenhal", intensity=50, rng=random.Random(1))
    assert band.kind == "bandits" and band.strength() > 0
    outlaws = military.form_outlaws(w, "harrenhal", rng=random.Random(1))
    assert outlaws.kind == "outlaws" and outlaws.strength() > 0
    company = military.hire_free_company(w, "lannister", "casterly_rock", rng=random.Random(1))
    assert company.kind == "free_company" and company.allegiance == "lannister"


# -- campaign -----------------------------------------------------------------
def test_ensure_map_seeds_holdings_control_and_fog(memory):
    w = WorldState()
    campaign.ensure_map(w, "winterfell")
    assert w.map_ready
    # every province with a seat got a holding
    seats = [p for p in mapdata.PROVINCES.values() if p.seat]
    assert len(w.holdings) == len(seats)
    assert w.control_of("winterfell") == "north_lords"
    # fog of war: you know where you stand and its neighbours, not the whole map
    assert w.is_discovered("winterfell")
    assert not w.is_discovered("volantis")


def test_declare_war_musters_hosts_on_both_sides(memory):
    w = WorldState()
    campaign.ensure_map(w, "winterfell")
    campaign.declare_war(w, memory, "lannister", "riverlands_lords",
                         "a broken oath", random.Random(1))
    allegiances = {a.allegiance for a in w.living_armies()}
    assert "lannister" in allegiances and "riverlands_lords" in allegiances
    assert w.war_intensity > 0
    assert any(w2["attacker"] == "lannister" for w2 in w.wars)


def test_strategic_tick_is_bounded_and_serialisable(memory):
    w = WorldState()
    campaign.ensure_map(w, "winterfell")
    rng = random.Random(3)
    campaign.declare_war(w, memory, "lannister", "riverlands_lords", "war", rng)
    for _ in range(40):
        campaign.strategic_tick(w, memory, 3)
    assert len(w.armies) <= campaign.MAX_ARMIES
    # the whole world state still round-trips through JSON (i.e. saves/loads)
    blob = json.dumps(w.model_dump())
    w2 = WorldState.model_validate(json.loads(blob))
    assert w2.map_ready
    assert set(w2.holdings) == set(w.holdings)


def test_muster_player_levies_from_a_holding(memory):
    w = WorldState()
    campaign.ensure_map(w, "winterfell")
    h = holdings.generate_holding("mine", "winterfell", "House Player", kind="castle",
                                  owner_is_player=True, rng=random.Random(1))
    w.holdings["mine"] = h

    class _Ch:
        name = "Aemon"
        house = "House Player"
        gold = 500
        class attributes:  # noqa
            @staticmethod
            def modifier(_a):
                return 1
    army = campaign.muster_player_levies(w, _Ch())
    assert army is not None and army.allegiance == "player"
    assert army.strength() > 0


# a bare object standing in for WorldState where the sim only needs its map fields
class _NoneWorld:
    def __init__(self):
        self.province_control = {}
        self.devastation = {}
        self.flags = {}
        self.next_entity_seq = 0


def None_world():
    return _NoneWorld()
