"""Tests for character creation and the character model."""
from __future__ import annotations

from iron_and_ash.character import data as cdata
from iron_and_ash.character.creation import (
    POINT_BUY_POOL, _apply_background, _quick_start, _random_attributes,
)
from iron_and_ash.character.models import Attributes, Character
from tests.conftest import ScriptedUI


# -- model behaviour ----------------------------------------------------------
def test_attribute_modifier_and_total():
    attr = Attributes(might=8, agility=4, cunning=4, presence=4, will=4, lore=4)
    assert attr.modifier("might") == 4
    assert attr.modifier("agility") == 0
    assert attr.total() == 28


def test_check_bonus_combines_attribute_and_skill():
    c = Character(name="X", origin="stark", region="north", religion="old_gods",
                  background="knight", attributes=Attributes(might=7))
    c.skills["swordsmanship"] = 3
    assert c.check_bonus("might", "swordsmanship") == (7 - 4) + 3


def test_grant_xp_levels_up_and_heals():
    c = Character(name="X", origin="stark", region="north", religion="old_gods",
                  background="knight")
    start_hp = c.max_health
    messages = c.grant_xp(250)  # enough for at least one level
    assert c.level >= 2
    assert c.max_health > start_hp
    assert c.health == c.max_health
    assert messages  # at least one level-up message


def test_character_death_flag():
    c = Character(name="X", origin="stark", region="north", religion="old_gods",
                  background="knight")
    c.health = 0
    assert c.is_alive() is False


# -- creation building blocks -------------------------------------------------
def test_random_attributes_spends_exact_pool():
    attr = _random_attributes()
    assert attr.total() == 24 + POINT_BUY_POOL  # baseline 4*6 plus the pool
    for a in ("might", "agility", "cunning", "presence", "will", "lore"):
        assert getattr(attr, a) <= 10


def test_apply_background_grants_skills_and_items():
    c = Character(name="X", origin="stark", region="north", religion="old_gods",
                  background="knight")
    _apply_background(c, "knight")
    assert c.skill("swordsmanship") == cdata.BACKGROUNDS["knight"].skill_bonuses["swordsmanship"]
    assert "longsword" in c.inventory


def test_quick_start_produces_valid_character():
    ui = ScriptedUI(ask=["Alaric Snow"])
    char = _quick_start(ui)
    assert char.name == "Alaric Snow"
    assert char.background == "knight"
    assert char.skill("swordsmanship") > 0
    assert char.gold > 0


def test_data_integrity_backgrounds_reference_real_skills():
    for bg in cdata.BACKGROUNDS.values():
        for skill in bg.skill_bonuses:
            assert skill in cdata.SKILLS, f"{bg.id} references unknown skill {skill}"


def test_data_integrity_houses_reference_real_regions_and_faiths():
    for house in cdata.GREAT_HOUSES.values():
        assert house.region in cdata.REGIONS
        assert house.religion in cdata.RELIGIONS
