"""Procedurally generated local scenes for seats without an authored one.

So that *every* castle, town, and city on the map can be entered and walked
about - not just the flagship seats - this builds a small, sensible local scene
for any holding, themed by its kind, and a bleak wilderness scene for provinces
with no seat at all. Generation is deterministic (seeded from the province and
the holding's own attributes), so the same place looks the same every session
without needing to be stored in the save. NPC ids are stable, so the memory
system can track how the locals feel about you over time.

Generated ids are namespaced ``gen:<province>:<slot>`` (locations) and
``gnpc:<province>:<slot>`` (NPCs) so the resolver in ``world.data`` can find the
province again and rebuild the scene on demand.
"""
from __future__ import annotations

import random
from functools import lru_cache
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import mapdata
from .holdings import Holding
from .models import Location, NPCDef


class Scene(NamedTuple):
    entry: str
    locations: Dict[str, Location]
    npcs: Dict[str, NPCDef]


# role name pools for generated officials and folk
_FIRST = ["Ser Alyn", "Ser Harys", "Ser Bennet", "Maester Colemon", "Old Merrek",
          "Willas", "Donnel", "Ser Kyle", "Rodrik", "Gawen", "Ser Ilyn", "Bryen",
          "Maester Ballabar", "Wendel", "Ser Ronnet", "Tom", "Ser Perwyn"]
_MERCHANT = ["Hobb", "Sella", "Pate", "Yorko", "Marya", "Dobber", "Illa", "Quill"]


def _describe(kind_label: str, place: str, holder: str, region: str) -> Dict[str, str]:
    return {
        "gate": f"The gatehouse of {place} guards the way in, its portcullis toothed with iron. "
                f"Guards in the colours of {holder} watch the road.",
        "yard": f"The outer yard of {place} rings with the everyday business of a {kind_label} - "
                "smiths, grooms, servants, and the clash of practice steel.",
        "hall": f"The great hall of {place}, seat of {holder}, hung with banners and warmed by a "
                "fire at its heart. This is where the household gathers and petitioners wait.",
        "street": f"The main street of {place} runs thick with carts, cries, and the press of a "
                  f"{region} crowd going about its day.",
        "market": f"The market of {place} is a clamour of stalls and haggling, where a traveller "
                  "can find most things, and a few they would rather not.",
        "square": f"The central square of {place}, where the folk of this {kind_label} gather to "
                  "trade news, gossip, and the odd hard word.",
        "inn": f"A low, smoky common room in {place}, smelling of ale and wet wool, where "
               "travellers loosen their tongues over a cup.",
        "keep": f"The keep of {place} rises above the rooftops, the seat of {holder} and the "
                "hard fist that keeps the peace here.",
        "camp": f"A traveller's camp in the wilds of {place}, a ring of stones and a windbreak "
                "against the open country.",
        "trail": f"A rough trail through the {region}, far from any hall, where the only law is "
                 "the speed of your horse and the edge of your blade.",
    }


# (slot, role-title) layout per holding kind; first slot is the entry
_LAYOUT: Dict[str, List[Tuple[str, str]]] = {
    "keep": [("gate", "Captain of the Guard"), ("hall", "Castellan")],
    "castle": [("gate", "Captain of the Guard"), ("yard", "Master-at-Arms"),
               ("hall", "Castellan")],
    "town": [("square", "Town Reeve"), ("market", "Market Trader"), ("inn", "Innkeep")],
    "city": [("gate", "Captain of the Watch"), ("street", "Master Armorer"),
             ("market", "Market Trader"), ("keep", "Steward")],
    "wilds": [("camp", ""), ("trail", "")],
}

# how the slots connect (label -> slot); entry is first
_LINKS: Dict[str, Dict[str, Dict[str, str]]] = {
    "keep": {"gate": {"into the hall": "hall"}, "hall": {"out to the gate": "gate"}},
    "castle": {"gate": {"into the yard": "yard"},
               "yard": {"out to the gate": "gate", "into the hall": "hall"},
               "hall": {"back to the yard": "yard"}},
    "town": {"square": {"to the market": "market", "to the inn": "inn"},
             "market": {"back to the square": "square"},
             "inn": {"back to the square": "square"}},
    "city": {"gate": {"up the main street": "street"},
             "street": {"down to the gate": "gate", "to the market": "market", "to the keep": "keep"},
             "market": {"back to the street": "street"},
             "keep": {"back to the street": "street"}},
    "wilds": {"camp": {"onto the trail": "trail"}, "trail": {"back to camp": "camp"}},
}


def _holding_signature(holding: Optional[Holding]) -> Tuple:
    if holding is None:
        return ("wilds",)
    return (holding.id, holding.kind, holding.name, holding.population,
            holding.defense, holding.holder_house)


@lru_cache(maxsize=256)
def _build(province_id: str, signature: Tuple) -> Scene:
    prov = mapdata.PROVINCES.get(province_id)
    region = prov.region if prov else "the wilds"
    is_wilds = signature == ("wilds",)
    kind = "wilds" if is_wilds else signature[1]
    place = (signature[2] if not is_wilds
             else (prov.name if prov else province_id.replace("_", " ").title()))
    holder = "no one" if is_wilds else signature[5]
    kind_label = {"keep": "holdfast", "castle": "castle", "town": "town",
                  "city": "city", "wilds": "wilderness"}[kind]

    rng = random.Random(hash((province_id, signature)) & 0xFFFFFFFF)
    descs = _describe(kind_label, place, holder, region)
    layout = _LAYOUT[kind]
    links = _LINKS[kind]

    locations: Dict[str, Location] = {}
    npcs: Dict[str, NPCDef] = {}
    entry_id = f"gen:{province_id}:{layout[0][0]}"

    for slot, role in layout:
        loc_id = f"gen:{province_id}:{slot}"
        exits = {label: f"gen:{province_id}:{dest}"
                 for label, dest in links[slot].items()}
        npc_ids: List[str] = []
        if role:
            npc_id = f"gnpc:{province_id}:{slot}"
            npc_ids.append(npc_id)
            npcs[npc_id] = _make_npc(npc_id, role, loc_id, place, holder, prov, rng)
        locations[loc_id] = Location(
            id=loc_id, name=f"{place} - {slot.title()}" if not is_wilds else _wilds_name(slot, place),
            region=region, description=descs[slot], exits=exits,
            npcs=npc_ids, travel_days=0,
        )
    return Scene(entry=entry_id, locations=locations, npcs=npcs)


def _wilds_name(slot: str, place: str) -> str:
    return {"camp": f"A Camp in {place}", "trail": f"The Trail through {place}"}[slot]


def _make_npc(npc_id: str, role: str, loc_id: str, place: str, holder: str,
              prov, rng: random.Random) -> NPCDef:
    if "Trader" in role or "Innkeep" in role or "Reeve" in role:
        name = rng.choice(_MERCHANT)
    else:
        name = rng.choice(_FIRST)
    faction = prov.faction if prov else None
    desc = (f"{name}, {role.lower()} of {place}. "
            "One of the folk who keep this place running, and worth a word to a newcomer.")
    return NPCDef(id=npc_id, name=name, title=role, home_location=loc_id,
                  faction=faction, description=desc, base_disposition=0)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def themed_holding(world, province_id: str) -> Optional[Holding]:
    """Which holding a province's generated scene is themed on.

    A player-owned holding in the province wins; otherwise the canonical seat.
    """
    own = [h for h in world.holdings.values()
           if h.province == province_id and h.owner_is_player]
    if own:
        return own[0]
    return world.holdings.get(f"seat_{province_id}")


def scene_for_province(world, province_id: str) -> Scene:
    holding = themed_holding(world, province_id)
    return _build(province_id, _holding_signature(holding))


def entry_for_province(world, province_id: str) -> str:
    return scene_for_province(world, province_id).entry
