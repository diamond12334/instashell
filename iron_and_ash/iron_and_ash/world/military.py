"""Military and outlaw entities, and the simulation that keeps them honest.

An :class:`Army` is any body of armed men on the strategic map: a lord's host, a
sellsword free company, a bandit band, an outlaw gang, or a holding's garrison.
The daily :func:`tick_army` models the four things the brief asks for -

* **Troop composition** - a dict of :data:`TROOP_TYPES`, each with its own combat
  power, pay, and rations. What an army is made of drives everything else.
* **Logistics** - it eats every day (rations scaled by size); it forages from the
  land it stands on (terrain- and control-dependent); when the food runs out,
  men go hungry, then desert. Harsh terrain and time bleed it through attrition.
* **Finances** - it must be paid; pay is drawn from its coffers each day; unpaid
  men - sellswords first - lose heart and slip away, and unpaid free companies
  turn outlaw.
* **Morale** - risen by victory, pay, and food; sunk by defeat, hunger, arrears,
  and distance from home. Low morale means desertion and a weaker line of battle.

Armies move along the map toward their orders, fight when they meet an enemy, and
disband when they starve, rout, or melt away. All of it is deterministic given an
RNG, so it is testable.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from . import geography, mapdata


class TroopType(BaseModel):
    id: str
    name: str
    power: float        # combat weight per soldier
    pay: float          # coin per soldier per day
    rations: float      # supply units per soldier per day
    speed: float        # march speed multiplier (cavalry faster)
    category: str       # infantry / ranged / cavalry / specialist


TROOP_TYPES: Dict[str, TroopType] = {
    t.id: t for t in [
        TroopType(id="levies", name="Levies", power=1.0, pay=0.02, rations=0.03, speed=1.0, category="infantry"),
        TroopType(id="light_infantry", name="Light Infantry", power=1.4, pay=0.04, rations=0.03, speed=1.1, category="infantry"),
        TroopType(id="archers", name="Archers", power=1.7, pay=0.05, rations=0.03, speed=1.0, category="ranged"),
        TroopType(id="men_at_arms", name="Men-at-Arms", power=2.6, pay=0.10, rations=0.05, speed=0.9, category="infantry"),
        TroopType(id="light_horse", name="Light Horse", power=2.2, pay=0.12, rations=0.09, speed=1.6, category="cavalry"),
        TroopType(id="knights", name="Knights", power=4.2, pay=0.28, rations=0.12, speed=1.5, category="cavalry"),
        TroopType(id="mercenaries", name="Sellswords", power=2.8, pay=0.22, rations=0.05, speed=1.1, category="infantry"),
        TroopType(id="specialists", name="Siege Engineers", power=1.5, pay=0.09, rations=0.05, speed=0.7, category="specialist"),
    ]
}

# baseline morale each kind drifts toward when fed and paid
_BASELINE = {"host": 60, "garrison": 65, "free_company": 55,
             "bandits": 45, "outlaws": 40}


class Army(BaseModel):
    """A body of armed men on the strategic map."""

    id: str
    name: str
    kind: str                       # host / garrison / free_company / bandits / outlaws
    allegiance: str                 # faction id, or "player"
    commander: str = ""
    leadership: int = 2             # 0-5, multiplies effective power
    province: str = ""
    home_province: str = ""
    composition: Dict[str, int] = Field(default_factory=dict)
    morale: int = 60
    supplies: float = 0.0           # ration-units of food in the baggage train
    coffers: int = 0                # coin on hand for pay
    loot: int = 0
    orders_target: Optional[str] = None
    orders_intent: str = "hold"     # hold / march / raid / besiege / return
    days_unpaid: int = 0
    days_unfed: int = 0
    hidden: bool = False            # bandits/outlaws lie low until they strike
    disbanded: bool = False

    # -- derived quantities ---------------------------------------------------
    def strength(self) -> int:
        return sum(self.composition.values())

    def combat_power(self) -> float:
        raw = sum(TROOP_TYPES[t].power * n
                  for t, n in self.composition.items() if t in TROOP_TYPES)
        morale_factor = 0.5 + (self.morale / 100.0)     # 0.5 .. 1.5
        leader_factor = 0.8 + 0.1 * self.leadership     # 0.8 .. 1.3
        return raw * morale_factor * leader_factor

    def daily_pay(self) -> float:
        return sum(TROOP_TYPES[t].pay * n
                   for t, n in self.composition.items() if t in TROOP_TYPES)

    def daily_rations(self) -> float:
        return sum(TROOP_TYPES[t].rations * n
                   for t, n in self.composition.items() if t in TROOP_TYPES)

    def march_speed(self) -> float:
        if not self.strength():
            return 1.0
        # an army marches at the pace of its slowest meaningful contingent,
        # weighted by numbers, so a baggage-heavy host crawls
        total = sum(TROOP_TYPES[t].speed * n
                    for t, n in self.composition.items() if t in TROOP_TYPES)
        return total / self.strength()

    def is_hostile_to(self, faction: str) -> bool:
        if self.kind in ("bandits", "outlaws"):
            return True  # prey on everyone
        return self.allegiance != faction

    def composition_line(self) -> str:
        parts = [f"{n} {TROOP_TYPES[t].name.lower()}"
                 for t, n in sorted(self.composition.items(), key=lambda kv: -kv[1])
                 if t in TROOP_TYPES and n > 0]
        return ", ".join(parts) if parts else "no men left"

    def supply_status(self) -> str:
        if self.days_unfed > 0:
            return "starving"
        if self.supplies < self.daily_rations() * 5:
            return "short on food"
        return "well supplied"

    def morale_word(self) -> str:
        if self.morale >= 75:
            return "eager"
        if self.morale >= 55:
            return "steady"
        if self.morale >= 35:
            return "wavering"
        if self.morale >= 15:
            return "fraying"
        return "broken"


def baseline_morale(kind: str) -> int:
    return _BASELINE.get(kind, 50)


def _provision(army: "Army", rng: random.Random, lo_days: int, hi_days: int) -> None:
    """Fill an army's baggage train with a plausible number of days of rations.

    Supplies are ration-units (a day's food for the whole host), so a bigger army
    needs proportionally more to march the same distance - the crux of logistics.
    """
    army.supplies = army.daily_rations() * rng.randint(lo_days, hi_days)


# ---------------------------------------------------------------------------
# spawning
# ---------------------------------------------------------------------------
def _next_id(world: Any, prefix: str) -> str:
    world.next_entity_seq = getattr(world, "next_entity_seq", 0) + 1
    return f"{prefix}_{world.next_entity_seq}"


def muster_host(world: Any, faction: str, home_province: str, *,
                name: str, commander: str = "", leadership: int = 2,
                strength_hint: int = 2000, coffers: int = 0,
                rng: Optional[random.Random] = None) -> Army:
    """Raise a lord's host: a composition weighted toward levies and foot, with
    a leaven of men-at-arms, archers, and horse. Size roughly ``strength_hint``.
    """
    rng = rng or random
    s = max(200, int(strength_hint * rng.uniform(0.7, 1.3)))
    comp = {
        "levies": int(s * 0.45),
        "light_infantry": int(s * 0.15),
        "archers": int(s * 0.15),
        "men_at_arms": int(s * 0.12),
        "light_horse": int(s * 0.08),
        "knights": int(s * 0.05),
    }
    army = Army(
        id=_next_id(world, "host"), name=name, kind="host", allegiance=faction,
        commander=commander, leadership=leadership, province=home_province,
        home_province=home_province, composition=comp,
        morale=baseline_morale("host"),
        coffers=coffers or s * rng.randint(1, 3),
    )
    _provision(army, rng, 15, 30)
    return army


def form_bandits(world: Any, province: str, *, intensity: int = 30,
                 rng: Optional[random.Random] = None) -> Army:
    """A bandit band coalesces in a lawless or devastated province."""
    rng = rng or random
    s = max(15, int(rng.randint(20, 80) * (1 + intensity / 100)))
    comp = {"levies": int(s * 0.7), "light_infantry": int(s * 0.2),
            "archers": int(s * 0.1)}
    army = Army(
        id=_next_id(world, "band"), name=_bandit_name(rng), kind="bandits",
        allegiance="bandit", commander=_captain_name(rng), leadership=rng.randint(0, 2),
        province=province, home_province=province, composition=comp,
        morale=baseline_morale("bandits"), coffers=rng.randint(0, 50),
        hidden=True, orders_intent="raid",
    )
    _provision(army, rng, 5, 12)
    return army


def form_outlaws(world: Any, province: str, source_army: Optional[Army] = None,
                 rng: Optional[random.Random] = None) -> Army:
    """Outlaws form when soldiers desert - often the unpaid remnant of a host."""
    rng = rng or random
    if source_army is not None and source_army.strength() > 0:
        # a slice of the parent army breaks away
        comp = {t: max(1, n // 3) for t, n in source_army.composition.items() if n >= 3}
        province = source_army.province
    else:
        s = rng.randint(15, 60)
        comp = {"light_infantry": int(s * 0.6), "archers": int(s * 0.2),
                "men_at_arms": int(s * 0.2)}
    army = Army(
        id=_next_id(world, "outlaw"), name=_outlaw_name(rng), kind="outlaws",
        allegiance="outlaw", commander=_captain_name(rng), leadership=rng.randint(1, 3),
        province=province, home_province=province, composition=comp,
        morale=baseline_morale("outlaws"), coffers=rng.randint(0, 30),
        hidden=True, orders_intent="raid",
    )
    _provision(army, rng, 4, 10)
    return army


def hire_free_company(world: Any, employer: str, province: str, *,
                      strength_hint: int = 800, coffers: int = 0,
                      rng: Optional[random.Random] = None) -> Army:
    rng = rng or random
    s = max(100, int(strength_hint * rng.uniform(0.7, 1.3)))
    comp = {"mercenaries": int(s * 0.5), "archers": int(s * 0.2),
            "men_at_arms": int(s * 0.2), "light_horse": int(s * 0.1)}
    army = Army(
        id=_next_id(world, "company"), name=_company_name(rng), kind="free_company",
        allegiance=employer, commander=_captain_name(rng), leadership=rng.randint(2, 4),
        province=province, home_province=province, composition=comp,
        morale=baseline_morale("free_company"),
        coffers=coffers or s * rng.randint(2, 4),
    )
    _provision(army, rng, 12, 25)
    return army


# ---------------------------------------------------------------------------
# the daily simulation
# ---------------------------------------------------------------------------
def tick_army(world: Any, army: Army, days: int,
              rng: Optional[random.Random] = None) -> List[str]:
    """Advance one army by ``days``. Returns human-readable notable events.

    Order of operations each tick: forage, eat, pay, attrition, morale, move.
    """
    rng = rng or random
    events: List[str] = []
    if army.disbanded or army.strength() <= 0:
        army.disbanded = True
        return events

    prov = mapdata.PROVINCES.get(army.province)
    terrain = mapdata.TERRAIN[prov.terrain] if prov else mapdata.TERRAIN["plains"]
    per_thousand = army.strength() / 1000.0

    # -- logistics: forage from the land ------------------------------------
    control = _province_control(world, army.province)
    friendly = (control == army.allegiance)
    forage_rate = terrain.forage * (1.3 if friendly else 0.8)
    army.supplies += forage_rate * per_thousand * days

    # -- logistics: eat ------------------------------------------------------
    need = army.daily_rations() * days
    if army.supplies >= need:
        army.supplies -= need
        army.days_unfed = 0
    else:
        army.supplies = 0.0
        army.days_unfed += days
        army.morale -= 4 * days
        events += _desert(army, rng, rate=0.04 * days, reason="hunger")

    # -- attrition from terrain and season ----------------------------------
    attrition = terrain.attrition * per_thousand * days
    if _is_winter(world):
        attrition *= 1.5
    lost = int(attrition)
    if lost > 0:
        _remove_troops(army, lost, rng)

    # -- finances: pay the men ----------------------------------------------
    cost = int(army.daily_pay() * days)
    if army.coffers >= cost:
        army.coffers -= cost
        army.days_unpaid = 0
    elif cost > 0:
        army.coffers = 0
        army.days_unpaid += days
        # sellswords and free companies are quickest to walk when coin runs dry
        merc_heavy = army.kind == "free_company" or army.composition.get("mercenaries", 0) > army.strength() * 0.3
        # an unpaid free company turns its coat and goes outlaw before it dissolves
        if merc_heavy and army.kind == "free_company" and army.days_unpaid >= 5 \
                and rng.random() < 0.4 * days:
            army.kind = "outlaws"
            army.allegiance = "outlaw"
            army.orders_intent = "raid"
            army.morale = max(army.morale, baseline_morale("outlaws"))
            events.append(f"{army.name}, unpaid too long, has turned outlaw.")
        else:
            rate = (0.06 if merc_heavy else 0.03) * days
            army.morale -= (3 if merc_heavy else 2) * days
            events += _desert(army, rng, rate=rate, reason="arrears")

    # -- morale drift --------------------------------------------------------
    _drift_morale(world, army)

    # rout / collapse
    if army.morale <= 0 or army.strength() <= 0:
        army.disbanded = True
        events.append(f"{army.name} has melted away to nothing.")
        return events

    # -- movement toward orders ---------------------------------------------
    events += _move_army(world, army, days, rng)
    return events


def _desert(army: Army, rng: random.Random, rate: float, reason: str) -> List[str]:
    before = army.strength()
    if before <= 0:
        return []
    losses = 0
    for t in list(army.composition):
        n = army.composition[t]
        # men-at-arms and knights hold better than levies and sellswords
        loyalty = 0.5 if t in ("men_at_arms", "knights") else 1.0
        gone = int(n * rate * loyalty * rng.uniform(0.6, 1.4))
        if gone > 0:
            army.composition[t] = max(0, n - gone)
            losses += gone
    if losses > 0:
        return [f"{losses} men slip away from {army.name} ({reason})."]
    return []


def _remove_troops(army: Army, count: int, rng: random.Random) -> None:
    """Remove ``count`` men spread across contingents (used for attrition/casualties)."""
    remaining = count
    types = [t for t in army.composition if army.composition[t] > 0]
    rng.shuffle(types)
    while remaining > 0 and types:
        for t in list(types):
            if remaining <= 0:
                break
            take = min(army.composition[t], max(1, remaining // max(1, len(types))))
            army.composition[t] -= take
            remaining -= take
            if army.composition[t] <= 0:
                types.remove(t)


def _drift_morale(world: Any, army: Army) -> None:
    base = baseline_morale(army.kind)
    # distance from home wears on a host
    dist = geography.distance(army.province, army.home_province)
    if dist > 0:
        base -= min(20, dist * 3)
    if army.days_unfed == 0 and army.days_unpaid == 0:
        # recover toward baseline when fed and paid
        if army.morale < base:
            army.morale = min(base, army.morale + 3)
        elif army.morale > base:
            army.morale = max(base, army.morale - 1)
    army.morale = max(0, min(100, army.morale))


def _move_army(world: Any, army: Army, days: int, rng: random.Random) -> List[str]:
    events: List[str] = []
    if army.orders_intent in ("hold", "besiege") or not army.orders_target:
        # bandits and outlaws wander to a neighbouring province to raid
        if army.kind in ("bandits", "outlaws") and rng.random() < 0.4 * days:
            nbrs = geography.neighbors(army.province)
            if nbrs:
                army.province = rng.choice(nbrs)
        return events
    if army.province == army.orders_target:
        if army.orders_intent == "return":
            army.orders_intent = "hold"
            army.orders_target = None
        return events
    # progress toward the target; faster armies cover ground in fewer days
    step = geography.step_toward(army.province, army.orders_target)
    if step is None:
        army.orders_target = None
        return events
    dest = mapdata.PROVINCES.get(step)
    cost = mapdata.TERRAIN[dest.terrain].move_days if dest else 4
    effective = days * army.march_speed()
    if effective >= cost * rng.uniform(0.7, 1.0):
        army.province = step
        if step == army.orders_target:
            events.append(f"{army.name} has reached {dest.name}.")
    return events


# ---------------------------------------------------------------------------
# battle
# ---------------------------------------------------------------------------
def resolve_battle(world: Any, attacker: Army, defender: Army,
                   rng: Optional[random.Random] = None) -> Tuple[str, List[str]]:
    """Resolve a field battle. Returns (winner_id, narrative lines).

    Casualties scale with the power ratio; the loser routs (morale collapses,
    heavy losses) and, if not shattered, is ordered home. Terrain aids the
    defender.
    """
    rng = rng or random
    prov = mapdata.PROVINCES.get(defender.province)
    terrain = mapdata.TERRAIN[prov.terrain] if prov else mapdata.TERRAIN["plains"]

    atk_power = attacker.combat_power() * rng.uniform(0.85, 1.15)
    def_power = defender.combat_power() * (1 + terrain.defense_bonus / 100.0) * rng.uniform(0.85, 1.15)

    lines = [f"{attacker.name} ({attacker.strength()}) meets "
             f"{defender.name} ({defender.strength()}) in {prov.name if prov else 'the field'}."]

    if atk_power >= def_power:
        winner, loser = attacker, defender
        ratio = atk_power / max(1.0, def_power)
    else:
        winner, loser = defender, attacker
        ratio = def_power / max(1.0, atk_power)

    # loser takes the worse of it; winner still bleeds
    loser_loss = min(0.9, 0.30 + 0.15 * (ratio - 1))
    winner_loss = max(0.05, 0.18 / ratio)
    l_before, w_before = loser.strength(), winner.strength()
    _remove_troops(loser, int(l_before * loser_loss), rng)
    _remove_troops(winner, int(w_before * winner_loss), rng)

    winner.morale = min(100, winner.morale + 12)
    loser.morale = max(0, loser.morale - 30)
    winner.loot += loser.coffers // 2
    loser.coffers //= 2

    lines.append(f"{winner.name} carries the field. "
                 f"{loser.name} loses {l_before - loser.strength()} men and breaks; "
                 f"{winner.name} loses {w_before - winner.strength()}.")

    if loser.strength() <= 0 or loser.morale <= 0:
        loser.disbanded = True
        lines.append(f"{loser.name} is destroyed.")
    else:
        loser.orders_target = loser.home_province
        loser.orders_intent = "return"
    return winner.id, lines


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _province_control(world: Any, province: str) -> Optional[str]:
    control = getattr(world, "province_control", {}) or {}
    if province in control:
        return control[province]
    prov = mapdata.PROVINCES.get(province)
    return prov.faction if prov else None


def _is_winter(world: Any) -> bool:
    return getattr(world, "flags", {}).get("season") == "winter"


# name generators ------------------------------------------------------------
_BAND_A = ["Broken", "Bloody", "Ragged", "Grey", "Kingswood", "Ironwood",
           "Night", "Hollow", "Red", "Weeping", "Rusty", "Black"]
_BAND_B = ["Men", "Brotherhood", "Wolves", "Blades", "Dogs", "Boys", "Band",
           "Reavers", "Riders", "Crows"]
_COMPANY_A = ["Golden", "Iron", "Long", "Bright", "Second", "Windblown",
              "Stormcrow", "Ragged", "Free", "Bloody"]
_COMPANY_B = ["Company", "Lances", "Sons", "Swords", "Spears", "Banners"]
_CAPTAINS = ["Rorge", "Gorne", "Ulf", "Harwin", "Black Jack", "Timeon",
             "Shagwell", "Merrett", "Long Tom", "Old Ben", "Red Rolfe",
             "Utt", "Grazdan", "Salladhor", "Denys", "Ser Amory"]


def _bandit_name(rng: random.Random) -> str:
    return f"The {rng.choice(_BAND_A)} {rng.choice(_BAND_B)}"


def _outlaw_name(rng: random.Random) -> str:
    return f"The {rng.choice(_BAND_A)} {rng.choice(_BAND_B)}"


def _company_name(rng: random.Random) -> str:
    return f"The {rng.choice(_COMPANY_A)} {rng.choice(_COMPANY_B)}"


def _captain_name(rng: random.Random) -> str:
    return rng.choice(_CAPTAINS)
