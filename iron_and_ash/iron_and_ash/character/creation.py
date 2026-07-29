"""Interactive character creation.

Two paths, as the brief asks for: a one-key **quick start** preset, and a full
**custom** flow that walks origin -> region -> religion -> background ->
attributes (point-buy) -> traits -> identity. Every step validates input and can
be answered with lore-aware defaults.
"""
from __future__ import annotations

import random
from typing import List, Optional

from ..ui.console import UI
from . import data
from .models import ATTRIBUTES, ATTRIBUTE_LABELS, Attributes, Character

POINT_BUY_POOL = 12  # points to distribute above the baseline of 4 per attribute
MAX_TRAITS = 3


def create_character(ui: UI) -> Character:
    ui.rule("Forging a Life in Westeros")
    mode = ui.menu(
        "How will you begin?",
        ["Quick start (a ready-made Northern sworn sword)",
         "Custom character (choose everything)"],
    )
    if mode == 0:
        return _quick_start(ui)
    return _custom_creation(ui)


# -- quick start -------------------------------------------------------------
def _quick_start(ui: UI) -> Character:
    name = ui.ask("Your name", default="Alaric Snow")
    origin = data.COMMON_ORIGINS["bastard"]
    char = Character(
        name=name,
        gender="unspecified",
        house="Snow (bastard of the North)",
        house_words="",
        sigil="",
        appearance="Lean and grey-eyed, with the look of the North about you.",
        origin="bastard",
        region="north",
        religion="old_gods",
        background="knight",
        attributes=Attributes(might=6, agility=5, cunning=4, presence=4, will=5, lore=3),
        gold=origin.starting_gold,
    )
    _apply_background(char, "knight")
    ui.panel(
        f"[bold]{char.name}[/bold], a base-born sword of the North, sworn to no lord yet.\n"
        "You begin at Winterfell with steel at your hip and a wary welcome.",
        title="Quick Start",
    )
    return char


# -- custom flow -------------------------------------------------------------
def _custom_creation(ui: UI) -> Character:
    origin_id, house_name, house_words, sigil, default_region, default_religion = _choose_origin(ui)
    region_id = _choose_region(ui, default_region)
    religion_id = _choose_religion(ui, default_religion)
    background_id = _choose_background(ui)
    attributes = _point_buy(ui)
    traits = _choose_traits(ui)
    name, gender, appearance, personal_words = _choose_identity(ui, house_words)

    origin = data.GREAT_HOUSES.get(origin_id) or data.COMMON_ORIGINS[origin_id]
    char = Character(
        name=name,
        gender=gender,
        house=house_name,
        house_words=personal_words or house_words,
        sigil=sigil,
        appearance=appearance,
        origin=origin_id,
        region=region_id,
        religion=religion_id,
        background=background_id,
        attributes=attributes,
        traits=traits,
        gold=origin.starting_gold,
    )
    _apply_background(char, background_id)
    _summarize(ui, char)
    return char


def _choose_origin(ui: UI):
    top = ui.menu("Your origin", ["Born to a Great House", "A humbler beginning"])
    if top == 0:
        houses = list(data.GREAT_HOUSES.values())
        labels = [f"{h.name} - {h.words} ({data.REGIONS[h.region].name})" for h in houses]
        idx = ui.menu("Choose your Great House", labels)
        h = houses[idx]
        ui.narrate(h.blurb)
        return h.id, h.name, h.words, h.sigil, h.region, h.religion
    origins = list(data.COMMON_ORIGINS.values())
    labels = [f"{o.name} - {o.blurb}" for o in origins]
    idx = ui.menu("Choose your station", labels)
    o = origins[idx]
    ui.narrate(o.blurb)
    house_name = o.name
    return o.id, house_name, "", "", o.region, o.religion


def _choose_region(ui: UI, default_region: str) -> str:
    regions = list(data.REGIONS.values())
    labels = [f"{r.name} - {r.blurb}" for r in regions]
    default_idx = next((i for i, r in enumerate(regions) if r.id == default_region), 0)
    ui.print(f"[dim]Suggested by your origin: {data.REGIONS[default_region].name}[/dim]")
    idx = ui.menu("Region of birth", labels)
    return regions[idx].id


def _choose_religion(ui: UI, default_religion: str) -> str:
    keys = list(data.RELIGIONS.keys())
    labels = [data.RELIGIONS[k] for k in keys]
    ui.print(f"[dim]Common where you were born: {data.RELIGIONS[default_religion]}[/dim]")
    idx = ui.menu("Faith", labels)
    return keys[idx]


def _choose_background(ui: UI) -> str:
    bgs = list(data.BACKGROUNDS.values())
    labels = []
    for b in bgs:
        bonuses = ", ".join(f"{data.SKILLS[s]} +{v}" for s, v in b.skill_bonuses.items())
        labels.append(f"{b.name} - {b.blurb} [{bonuses}]")
    idx = ui.menu("Background", labels)
    ui.narrate(bgs[idx].blurb)
    return bgs[idx].id


def _point_buy(ui: UI) -> Attributes:
    ui.heading("Distribute your attributes")
    ui.print(f"Every attribute starts at 4. You have [bold]{POINT_BUY_POOL}[/bold] points "
             "to spend, up to 10 in any single attribute.")
    if not ui.confirm("Spend points yourself? (No = roll a balanced spread)", default=True):
        return _random_attributes()
    scores = {a: 4 for a in ATTRIBUTES}
    remaining = POINT_BUY_POOL
    for a in ATTRIBUTES:
        if remaining <= 0:
            break
        ui.print(f"[dim]Points left: {remaining}[/dim]")
        spend = ui.ask_int(
            f"Add to {ATTRIBUTE_LABELS[a]} (0-{min(6, remaining)})",
            default=0, minimum=0, maximum=min(6, remaining),
        )
        scores[a] += spend
        remaining -= spend
    if remaining > 0:
        ui.print(f"[dim]{remaining} unspent points scattered evenly.[/dim]")
        i = 0
        order = [a for a in ATTRIBUTES if scores[a] < 10]
        while remaining > 0 and order:
            a = order[i % len(order)]
            if scores[a] < 10:
                scores[a] += 1
                remaining -= 1
            i += 1
            order = [a for a in ATTRIBUTES if scores[a] < 10]
    return Attributes(**scores)


def _random_attributes() -> Attributes:
    scores = {a: 4 for a in ATTRIBUTES}
    for _ in range(POINT_BUY_POOL):
        a = random.choice([a for a in ATTRIBUTES if scores[a] < 10])
        scores[a] += 1
    return Attributes(**scores)


def _choose_traits(ui: UI) -> List[str]:
    ui.heading(f"Traits (choose up to {MAX_TRAITS}; perks and flaws both shape your tale)")
    traits = list(data.TRAITS.values())
    chosen: List[str] = []
    for t in traits:
        tag = "PERK" if t.kind == "perk" else "FLAW"
        if len(chosen) >= MAX_TRAITS:
            break
        if ui.confirm(f"[{tag}] {t.name} - {t.blurb}  Take it?", default=False):
            chosen.append(t.id)
    return chosen


def _choose_identity(ui: UI, house_words: str):
    name = ui.ask("Your name")
    while not name.strip():
        name = ui.ask("Your name cannot be empty. Your name")
    gender = ui.ask("Gender (free text; how you wish to be described)", default="unspecified")
    appearance = ui.ask("Describe your appearance in a line",
                        default="Unremarkable at a glance, easy to underestimate.")
    personal_words = ""
    if not house_words:
        personal_words = ui.ask("A personal motto (optional)", default="")
    return name, gender, appearance, personal_words


def _apply_background(char: Character, background_id: str) -> None:
    bg = data.BACKGROUNDS[background_id]
    for skill, bonus in bg.skill_bonuses.items():
        char.skills[skill] = char.skills.get(skill, 0) + bonus
    char.inventory.extend(bg.starting_items)


def _summarize(ui: UI, char: Character) -> None:
    region = data.REGIONS[char.region].name
    trait_names = ", ".join(data.TRAITS[t].name for t in char.traits) or "none"
    attr_line = "  ".join(f"{ATTRIBUTE_LABELS[a]} {getattr(char.attributes, a)}" for a in ATTRIBUTES)
    skill_line = ", ".join(f"{data.SKILLS[s]} +{v}" for s, v in char.skills.items()) or "none"
    ui.panel(
        f"[bold]{char.name}[/bold] of {char.house}\n"
        f"Born in {region}, faithful to {data.RELIGIONS[char.religion]}.\n"
        f"Background: {data.BACKGROUNDS[char.background].name}\n\n"
        f"{attr_line}\n"
        f"Skills: {skill_line}\n"
        f"Traits: {trait_names}\n"
        f"Gold: {char.gold}\n"
        f"Motto: {char.house_words or '(none)'}",
        title="Your Character",
    )
