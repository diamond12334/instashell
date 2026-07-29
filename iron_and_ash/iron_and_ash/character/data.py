"""Lore-grounded content for character creation.

Everything here is data, not logic, so the roster of houses, backgrounds, traits
and religions can grow without touching the creation flow. All prose is written
originally for this fan project.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple


class House(NamedTuple):
    id: str
    name: str
    words: str
    sigil: str
    region: str          # id into REGIONS
    religion: str        # default religion id
    starting_gold: int
    prestige: int        # baseline standing with the realm's lords
    blurb: str


class Region(NamedTuple):
    id: str
    name: str
    culture: str
    default_religion: str
    blurb: str


class Background(NamedTuple):
    id: str
    name: str
    skill_bonuses: Dict[str, int]
    starting_items: List[str]
    blurb: str


class Trait(NamedTuple):
    id: str
    name: str
    kind: str            # "perk" or "flaw"
    blurb: str


# -- regions -----------------------------------------------------------------
REGIONS: Dict[str, Region] = {
    r.id: r for r in [
        Region("north", "The North", "hardy and plainspoken", "old_gods",
               "A vast, cold land of pine and snow that remembers the First Men."),
        Region("riverlands", "The Riverlands", "weary of war", "faith",
               "Fertile, contested country where the great rivers meet - and armies march."),
        Region("vale", "The Vale of Arryn", "proud and knightly", "faith",
               "Mountain-walled and aloof, guarded by the Bloody Gate and the Eyrie."),
        Region("westerlands", "The Westerlands", "rich and prideful", "faith",
               "Golden hills honeycombed with mines; the seat of Lannister power."),
        Region("reach", "The Reach", "courtly and chivalrous", "faith",
               "The realm's breadbasket, land of knights, tourneys, and roses."),
        Region("stormlands", "The Stormlands", "stubborn and fierce", "faith",
               "Storm-lashed coasts and deep forests under ancient Storm's End."),
        Region("dorne", "Dorne", "passionate and unbowed", "faith",
               "Sun, sand, and spears; a people who bow to no throne unwilling."),
        Region("iron_islands", "The Iron Islands", "raiding and iron-willed", "drowned_god",
               "Bleak salt-rock isles whose folk pay the iron price."),
        Region("crownlands", "The Crownlands", "cosmopolitan and scheming", "faith",
               "The lands about King's Landing, thick with courtiers and gold cloaks."),
        Region("beyond_wall", "Beyond the Wall", "free and unforgiving", "old_gods",
               "The haunted forest and frozen wastes where free folk and worse things roam."),
        Region("essos", "Essos (Free Cities)", "worldly and mercantile", "many_faced",
               "Braavos and the Free Cities across the narrow sea, rich and treacherous."),
    ]
}

RELIGIONS: Dict[str, str] = {
    "old_gods": "The Old Gods of the Forest",
    "faith": "The Faith of the Seven",
    "drowned_god": "The Drowned God",
    "rhllor": "R'hllor, the Lord of Light",
    "many_faced": "The Many-Faced God",
}


# -- houses & origins --------------------------------------------------------
GREAT_HOUSES: Dict[str, House] = {
    h.id: h for h in [
        House("stark", "House Stark", "Winter is Coming", "a grey direwolf on ice-white",
              "north", "old_gods", 120, 60,
              "Lords of Winterfell and Wardens of the North, blood of the First Men."),
        House("lannister", "House Lannister", "Hear Me Roar", "a golden lion on crimson",
              "westerlands", "faith", 400, 55,
              "The richest house in the realm - gold, ambition, and long memory."),
        House("targaryen", "House Targaryen (loyalist)", "Fire and Blood",
              "a red three-headed dragon on black", "crownlands", "faith", 200, 20,
              "Dragonless exiles and loyalists who still dream of the Iron Throne."),
        House("baratheon", "House Baratheon", "Ours is the Fury", "a black stag on gold",
              "stormlands", "faith", 220, 55,
              "Storm-born and strong, kin to the crowned stag of Storm's End."),
        House("tyrell", "House Tyrell", "Growing Strong", "a golden rose on green",
              "reach", "faith", 300, 50,
              "Wardens of the South, masters of the Reach's wealth and knights."),
        House("martell", "House Martell", "Unbowed, Unbent, Unbroken",
              "a red sun pierced by a golden spear", "dorne", "faith", 200, 45,
              "Princes of Dorne who never truly knelt to dragon or throne."),
        House("greyjoy", "House Greyjoy", "We Do Not Sow", "a golden kraken on black",
              "iron_islands", "drowned_god", 90, 35,
              "Reavers of Pyke who take with sword and pay the iron price."),
        House("tully", "House Tully", "Family, Duty, Honor", "a silver trout on red and blue",
              "riverlands", "faith", 150, 45,
              "Lords of Riverrun, guardians of the contested river country."),
        House("arryn", "House Arryn", "As High as Honor", "a white falcon and moon on sky-blue",
              "vale", "faith", 180, 50,
              "Ancient and proud, enthroned in the impregnable Eyrie."),
    ]
}

# Lowborn / unaffiliated origins. ``region`` here is a *suggested* default; the
# player still picks their region of birth explicitly during creation.
COMMON_ORIGINS: Dict[str, House] = {
    o.id: o for o in [
        House("peasant", "Smallfolk", "", "", "riverlands", "faith", 5, 5,
              "Born to the fields, owning little but your own two hands."),
        House("bastard", "Highborn Bastard", "", "", "north", "old_gods", 30, 20,
              "Noble blood, base-born name - trusted by neither high nor low."),
        House("sellsword", "Sellsword", "", "", "essos", "many_faced", 40, 10,
              "A blade for hire who has fought under a dozen banners for coin."),
        House("maester", "Maester's Apprentice", "", "", "reach", "faith", 25, 25,
              "Trained at the Citadel in letters, medicine, and quiet counsel."),
        House("watch", "Night's Watch Recruit", "", "", "north", "old_gods", 10, 15,
              "Sworn (or soon to be) to the black, guarding the realms of men."),
        House("exile", "Free City Exile", "", "", "essos", "many_faced", 60, 15,
              "A stranger far from home, carrying secrets across the narrow sea."),
    ]
}


BACKGROUNDS: Dict[str, Background] = {
    b.id: b for b in [
        Background("knight", "Knight", {"swordsmanship": 3, "riding": 2},
                   ["longsword", "destrier", "suit of mail"],
                   "Anointed and armoured, raised to the code of chivalry."),
        Background("spy", "Spy", {"intrigue": 3, "stealth": 2},
                   ["hidden dagger", "coded ledger"],
                   "You trade in whispers, and know the price of every secret."),
        Background("healer", "Healer", {"healing": 3, "lore_skill": 2},
                   ["healer's satchel", "milk of the poppy"],
                   "Trained in wounds and fevers; welcome in any camp."),
        Background("smuggler", "Smuggler", {"stealth": 2, "intrigue": 2, "riding": 1},
                   ["fast skiff", "purse of foreign coin"],
                   "You move goods past those who would tax or hang you for it."),
        Background("scholar", "Scholar", {"lore_skill": 3, "old_tongue": 1},
                   ["heavy tome", "writing kit"],
                   "A rare literate soul, versed in histories and old tongues."),
        Background("hunter", "Hunter", {"archery": 3, "stealth": 1, "riding": 1},
                   ["longbow", "quiver of arrows", "skinning knife"],
                   "The wild is your larder; few can track or shoot as you do."),
    ]
}

# The full skill roster (used for display and for validating background bonuses).
SKILLS: Dict[str, str] = {
    "swordsmanship": "Swordsmanship",
    "archery": "Archery",
    "riding": "Riding",
    "intrigue": "Intrigue",
    "stewardship": "Stewardship",
    "healing": "Healing",
    "stealth": "Stealth",
    "warging": "Warging",
    "old_tongue": "Old Tongue",
    "high_valyrian": "High Valyrian",
    "lore_skill": "Lore & Letters",
}


TRAITS: Dict[str, Trait] = {
    t.id: t for t in [
        Trait("silver_tongue", "Silver Tongue", "perk",
              "Your words open doors and loosen purses; a bonus to persuasion."),
        Trait("tourney_champion", "Tourney Champion", "perk",
              "Renowned in the lists; lords and ladies know your name."),
        Trait("warg_touched", "Warg-touched", "perk",
              "The old blood runs strong; you sometimes slip into the skins of beasts."),
        Trait("iron_stomach", "Iron Constitution", "perk",
              "Poison and hardship trouble you less than most - extra vigour."),
        Trait("craven", "Craven", "flaw",
              "Fear grips you in a fight; foes read it, and courage fails you."),
        Trait("kinslayer_guilt", "Kinslayer's Guilt", "flaw",
              "A blood-crime shadows you; the gods and men look on you askance."),
        Trait("proud", "Prideful", "flaw",
              "You cannot let a slight pass, which makes enemies you need not have."),
        Trait("marked", "Marked by the Faith", "flaw",
              "The septons name you sinner; the pious withhold their trust."),
    ]
}
