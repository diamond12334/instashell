"""Holdings: seats of power, and the generator that makes them.

A :class:`Holding` is a castle, keep, town, or city on the strategic map. The
same generator builds the canonical seats (Winterfell, the Eyrie...) and any new
holding the player founds or an NPC house is given, so player content and world
content stay consistent.

Everything a holding needs to matter to the sim is here: size, defenses,
population, garrison, the economy buildings that set its income, and the levy it
can raise for war. Holdings are pydantic models so they serialise straight into
the save.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# kind -> (population range, base defense, income range, garrison range, levy %)
KIND_PROFILE: Dict[str, dict] = {
    "keep":   {"pop": (150, 800),     "defense": 2, "income": (4, 15),
               "garrison": (10, 40),   "levy_pct": 0.06, "label": "holdfast"},
    "castle": {"pop": (600, 3000),    "defense": 4, "income": (15, 50),
               "garrison": (40, 200),  "levy_pct": 0.05, "label": "castle"},
    "town":   {"pop": (2000, 8000),   "defense": 2, "income": (30, 100),
               "garrison": (20, 120),  "levy_pct": 0.04, "label": "town"},
    "city":   {"pop": (15000, 120000), "defense": 3, "income": (150, 700),
               "garrison": (200, 1500), "levy_pct": 0.03, "label": "city"},
}

# economy buildings a holding may have, and the income each adds
ECONOMY_BUILDINGS = {
    "market": 8, "granary": 4, "mill": 5, "mine": 12, "port": 15,
    "smithy": 6, "sept": 3, "vineyard": 7, "fishing wharf": 5, "tannery": 4,
    "brewery": 5, "glass gardens": 9, "counting house": 10,
}

DEFENSE_WORKS = {
    "wooden palisade": 1, "stone curtain wall": 2, "double walls": 3,
    "moat": 1, "gatehouse and portcullis": 1, "flanking towers": 1,
    "cliffside approach": 2, "great keep": 2,
}

# name fragments, kept lore-flavoured and original
_PREFIX = ["Grey", "Storm", "Rain", "Winter", "Iron", "Black", "White", "Red",
           "Wolf", "Raven", "Thorn", "Deep", "High", "Bright", "Ash", "Mist",
           "Oak", "Stone", "Frost", "Salt", "Gold", "Long", "Green", "Bitter"]
_SUFFIX = ["hall", "wood", "keep", "watch", "hold", "gate", "moor", "fell",
           "guard", "crag", "mere", "barrow", "ford", "reach", "hollow",
           "march", "rest", "helm", "point", "vale", "hearth", "run"]
_CITY_SUFFIX = ["port", "town", "harbor", "market", "gate", "haven", "landing"]

_HOUSE_ROOTS = ["Black", "Storm", "Wyl", "Marsh", "Ryder", "Frost", "Karn",
                "Oake", "Bram", "Vance", "Corbray", "Hale", "Mertyn", "Dagon",
                "Wode", "Selm", "Harl", "Toll", "Grey", "Rus", "Lang", "Ferren"]
_HOUSE_TAIL = ["wood", "s", "yn", "ell", " mont", "ar", "wyn", "hart", "ryn",
               "good", "hill", "water", "field", "stone", "ford"]


class Holding(BaseModel):
    """A seat on the strategic map."""

    id: str
    name: str
    kind: str                       # keep / castle / town / city
    province: str
    holder_house: str               # house or faction that holds it
    owner_is_player: bool = False
    independent: bool = False       # not sworn to a liege
    population: int = 0
    defense: int = 0                # fortification rating (higher = tougher)
    income: int = 0                 # coin per season
    garrison: int = 0               # standing troops
    buildings: List[str] = Field(default_factory=list)
    defense_works: List[str] = Field(default_factory=list)
    levy_override: Optional[int] = None   # set for custom-built holdings
    founded_day: int = 0
    description: str = ""

    def levy_potential(self) -> int:
        """How many levies this holding can raise for war."""
        if self.levy_override is not None:
            return self.levy_override
        pct = KIND_PROFILE.get(self.kind, KIND_PROFILE["keep"])["levy_pct"]
        return int(self.population * pct)

    def kind_label(self) -> str:
        return KIND_PROFILE.get(self.kind, {}).get("label", self.kind)


def generate_house_name(rng: Optional[random.Random] = None) -> str:
    rng = rng or random
    root = rng.choice(_HOUSE_ROOTS)
    tail = rng.choice(_HOUSE_TAIL)
    return f"House {root}{tail}".replace(" mont", "mont")


def generate_holding_name(kind: str, rng: Optional[random.Random] = None) -> str:
    rng = rng or random
    if kind == "city":
        return rng.choice(_PREFIX) + rng.choice(_CITY_SUFFIX)
    return rng.choice(_PREFIX) + rng.choice(_SUFFIX)


def generate_holding(
    holding_id: str,
    province: str,
    holder_house: str,
    *,
    kind: Optional[str] = None,
    name: Optional[str] = None,
    owner_is_player: bool = False,
    independent: bool = False,
    founded_day: int = 0,
    rng: Optional[random.Random] = None,
) -> Holding:
    """Procedurally build a holding.

    ``kind`` may be forced; otherwise it is rolled with castles most common.
    Population, defenses, economy buildings, income, and garrison are all derived
    from the kind's profile plus its buildings, so two holdings of the same kind
    still differ.
    """
    rng = rng or random
    if kind is None:
        kind = rng.choices(["keep", "castle", "town", "city"],
                           weights=[35, 40, 20, 5])[0]
    profile = KIND_PROFILE.get(kind, KIND_PROFILE["castle"])
    name = name or generate_holding_name(kind, rng)

    population = rng.randint(*profile["pop"])

    # roll a plausible set of economy buildings; cities get more
    n_buildings = {"keep": (1, 2), "castle": (2, 4),
                   "town": (3, 5), "city": (5, 8)}[kind]
    pool = list(ECONOMY_BUILDINGS)
    rng.shuffle(pool)
    buildings = pool[:rng.randint(*n_buildings)]

    # defensive works accumulate a fortification rating on top of the base
    n_works = {"keep": (1, 2), "castle": (3, 5), "town": (1, 2), "city": (2, 4)}[kind]
    works_pool = list(DEFENSE_WORKS)
    rng.shuffle(works_pool)
    works = works_pool[:rng.randint(*n_works)]
    defense = profile["defense"] + sum(DEFENSE_WORKS[w] for w in works)

    income = rng.randint(*profile["income"]) + sum(ECONOMY_BUILDINGS[b] for b in buildings)
    garrison = rng.randint(*profile["garrison"])

    return Holding(
        id=holding_id,
        name=name,
        kind=kind,
        province=province,
        holder_house=holder_house,
        owner_is_player=owner_is_player,
        independent=independent,
        population=population,
        defense=defense,
        income=income,
        garrison=garrison,
        buildings=buildings,
        defense_works=works,
        founded_day=founded_day,
        description=_describe(kind, name, holder_house, buildings, works),
    )


def _describe(kind: str, name: str, house: str, buildings: List[str],
              works: List[str]) -> str:
    label = KIND_PROFILE[kind]["label"]
    econ = ", ".join(buildings) if buildings else "little of note"
    walls = ", ".join(works) if works else "scant defenses"
    return (f"{name} is a {label} held by {house}. Its walls boast {walls}; "
            f"within and about it thrive {econ}.")
