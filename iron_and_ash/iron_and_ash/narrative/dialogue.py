"""NPC conversations.

Each NPC has a handler that runs a small dialogue loop. Conversations are
memory-aware in two directions: the greeting reflects the NPC's current
disposition and recalls specific past events with the player, and the player's
choices *record* new events (favours, slights, oaths, discoveries) that the NPC -
and the world - will remember afterwards.
"""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional

from ..engine import codex
from ..engine.mechanics import skill_check
from ..engine.state import GameState
from ..memory import Event, EventType
from ..ui.console import UI
from ..world import data as world_data
from ..world import lore
from ..world import reactivity


def talk_to(ui: UI, gs: GameState, npc_id: str) -> None:
    npc = world_data.get_npc(npc_id, gs.world)
    if npc is None:
        ui.print("There is no one here by that name.")
        return
    _greet(ui, gs, npc_id)
    handler = _HANDLERS.get(npc_id, _generic_conversation)
    handler(ui, gs, npc_id)


def _greet(ui: UI, gs: GameState, npc_id: str) -> None:
    npc = world_data.get_npc(npc_id, gs.world)
    disposition = gs.memory.npc_disposition(npc_id) + npc.base_disposition
    past = gs.memory.events_with_actor(npc_id, count=3)
    ui.heading(f"{npc.name}, {npc.title}")
    ui.narrate(npc.description)
    if disposition >= 25:
        mood = f"{npc.name} greets you warmly, as a trusted friend."
    elif disposition <= -25:
        mood = f"{npc.name} regards you with open hostility."
    elif disposition <= -10:
        mood = f"{npc.name} eyes you with cool suspicion."
    else:
        mood = f"{npc.name} gives you a measured, neutral look."
    ui.print(mood)
    # recall a specific shared memory, the heart of "the world remembers you"
    meaningful = [e for e in past if e.type != EventType.DIALOGUE]
    if meaningful:
        recalled = meaningful[-1]
        days_ago = gs.world.day - recalled.game_day
        when = "earlier today" if days_ago <= 0 else f"{days_ago} day(s) past"
        ui.print(f"[dim]\"I've not forgotten,\" they say. \"{recalled.summary}\" ({when}.)[/dim]")


def _record_dialogue(gs: GameState, npc_id: str, note: str, importance: int = 1) -> None:
    gs.memory.record(Event(
        game_day=gs.world.day, type=EventType.DIALOGUE, summary=note,
        actors=[npc_id], location=gs.character.location, importance=importance,
    ))


def _teach_lore(ui: UI, gs: GameState, npc_id: str, categories: list,
                teacher_line: str, xp: int = 15) -> bool:
    """An NPC teaches the player a lore entry they have not yet studied.

    The entry is shown in full, marked as studied in the codex, and recorded as
    a DISCOVERY event so the memory system knows what the character has learned
    and from whom. Returns False when the teacher has nothing new left.
    """
    entry = lore.random_entry(exclude_ids=codex.studied_ids(gs.world),
                              categories=categories)
    if entry is None:
        return False
    ui.narrate(teacher_line)
    codex.show_entry(ui, entry)
    codex.mark_studied(gs.world, entry.id)
    gs.memory.record(Event(
        game_day=gs.world.day, type=EventType.DISCOVERY,
        summary=f"You learned the lore of '{entry.name}' from {world_data.NPCS[npc_id].name}.",
        actors=[npc_id], location=gs.character.location, importance=2,
        data={"lore_id": entry.id},
    ))
    for m in gs.character.grant_xp(xp):
        ui.print(f"[green]{m}[/green]")
    ui.print(f"[dim]'{entry.name}' is now marked in your codex under "
             f"{lore.CATEGORIES[entry.category]}.[/dim]")
    return True


# -- specific NPC handlers ----------------------------------------------------
def _master_at_arms(ui: UI, gs: GameState, npc_id: str) -> None:
    while True:
        choice = ui.menu(
            "Ser Ormund Cassel",
            ["Ask to prove yourself in the training yard",
             "Ask about the state of the North",
             "Swear your sword to Winterfell"],
            allow_back=True,
        )
        if choice == -1:
            _record_dialogue(gs, npc_id, "You spoke with Ser Ormund in the yard.")
            return
        if choice == 0:
            ui.narrate("\"Steel doesn't lie,\" Ormund grunts. \"Show me, then.\"")
            result = skill_check(gs.character, "might", "swordsmanship", "moderate")
            ui.print(result.describe())
            if result.success:
                ui.narrate("You give a good account of yourself; the old knight nods, grudging respect in his eyes.")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary="You impressed Ser Ormund with your skill at arms.",
                    actors=[npc_id], location=gs.character.location, importance=2,
                ))
                for m in gs.character.grant_xp(30):
                    ui.print(f"[green]{m}[/green]")
            else:
                ui.narrate("He knocks you flat twice before you find your feet. \"More work needed.\"")
                gs.character.skills["swordsmanship"] = gs.character.skill("swordsmanship") + 1
                ui.print("[dim]You learned something from the bruising. (Swordsmanship +1)[/dim]")
        elif choice == 1:
            ui.narrate("\"The North remembers, and the North endures. But the winds "
                       "from the south smell of trouble, and those from the north of worse.\"")
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.DISCOVERY,
                summary="Ser Ormund warned you of troubles brewing north and south.",
                actors=[npc_id], importance=2,
            ))
        elif choice == 2:
            if ui.confirm("Swear your sword to Winterfell? This is an oath the North will hold you to.", default=False):
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.OATH,
                    summary="You swore your sword to Winterfell before Ser Ormund.",
                    actors=[npc_id], location=gs.character.location, importance=4,
                ))
                gs.world.adjust_reputation("north_lords", 15)
                gs.character.titles.append("Sworn Sword of Winterfell")
                ui.narrate("Ormund clasps your forearm. \"Then you are one of us. Don't make me regret it.\"")
                reactivity.schedule_ripple(
                    gs.world, delay_days=8, kind="aid", faction="north_lords", npc=npc_id,
                    text="A rider from Winterfell finds you with coin and word that your oath is remembered.",
                )
            else:
                ui.narrate("\"Wise to think on it. An oath is not a thing to spend lightly.\"")


def _maester(ui: UI, gs: GameState, npc_id: str) -> None:
    while True:
        choice = ui.menu(
            "Maester Wyllis",
            ["Ask him to teach you (test of wits)",
             "Ask after news from the ravens",
             "Ask about the old histories of the North"],
            allow_back=True,
        )
        if choice == -1:
            _record_dialogue(gs, npc_id, "You conferred with Maester Wyllis.")
            return
        if choice == 0:
            result = skill_check(gs.character, "lore", "lore_skill", "moderate")
            ui.print(result.describe())
            if result.success:
                ui.narrate("You follow his reasoning and even best him on a point of history. He is pleased.")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary="You showed sharp wits to Maester Wyllis.",
                    actors=[npc_id], importance=2))
                for m in gs.character.grant_xp(25):
                    ui.print(f"[green]{m}[/green]")
            else:
                ui.narrate("The lesson goes over your head, but the maester is patient.")
        elif choice == 1:
            ui.narrate("\"A raven came at dawn - the seal was one I did not know. Curious times.\"")
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.DISCOVERY,
                summary="Maester Wyllis spoke of a raven bearing an unknown seal.",
                actors=[npc_id], importance=3,
                data={"quest_hook": "unknown_raven"}))
            gs.world.quests["unknown_raven"] = "heard"
        elif choice == 2:
            taught = _teach_lore(
                ui, gs, npc_id,
                categories=["history", "houses", "orders", "places"],
                teacher_line="Wyllis's eyes brighten. \"Ah - sit, sit. Few enough "
                             "care for the old accounts. Attend, now...\"",
                xp=20,
            )
            if not taught:
                ui.narrate("\"I have taught you all the histories I keep, I think. "
                           "You begin to sound like a maester yourself.\"")


def _woodswitch(ui: UI, gs: GameState, npc_id: str) -> None:
    while True:
        choice = ui.menu(
            "Old Nan of the Wood",
            ["Pray before the weirwood",
             "Ask her to read your fate",
             "Ask about the free folk beyond the Wall",
             "Ask for one of her old tales"],
            allow_back=True,
        )
        if choice == -1:
            return
        if choice == 0:
            ui.narrate("You kneel in the red-leaved quiet. Something old and patient seems to listen.")
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.DISCOVERY,
                summary="You prayed before the heart tree of Winterfell.",
                actors=[npc_id], importance=2))
            if "warg_touched" in gs.character.traits:
                ui.narrate("For a heartbeat you see the godswood through a raven's eyes. The old blood stirs.")
        elif choice == 1:
            result = skill_check(gs.character, "will", None, "hard")
            ui.print(result.describe())
            if result.success:
                ui.narrate("\"You'll be tested by cold and by kin,\" she rasps. \"Trust the wolf, not the lion.\"")
            else:
                ui.narrate("She peers at you, then shakes her head. \"The threads are tangled. Come again.\"")
        elif choice == 2:
            ui.narrate("\"Free folk, wildlings, the men beyond the Wall - call them what you like. "
                       "They run from something, child. Something that doesn't tire and doesn't warm.\"")
            gs.world.quests.setdefault("the_cold", "heard")
        elif choice == 3:
            taught = _teach_lore(
                ui, gs, npc_id,
                categories=["legends", "religions", "customs"],
                teacher_line="She settles onto a root of the heart tree, and her voice "
                             "goes soft and far away. \"Now this is a true tale, mind...\"",
                xp=15,
            )
            if not taught:
                ui.narrate("\"You've had all my tales, child. Now you carry them - "
                           "see you tell them true.\"")


def _merchant(ui: UI, gs: GameState, npc_id: str) -> None:
    wares = [("healer's satchel", 15), ("warm furs", 10), ("good steel dagger", 25)]
    while True:
        labels = [f"Buy {name} ({price} silver)" for name, price in wares]
        labels.append("Haggle over prices (Presence)")
        labels.append("Ask what news the roads bring")
        choice = ui.menu(f"Tobbot Flint - you have {gs.character.gold} silver", labels, allow_back=True)
        if choice == -1:
            return
        if choice < len(wares):
            name, price = wares[choice]
            if gs.character.gold >= price:
                gs.character.gold -= price
                gs.character.inventory.append(name)
                ui.print(f"[green]You bought {name}.[/green]")
                _record_dialogue(gs, npc_id, f"You traded with Tobbot for {name}.")
            else:
                ui.print("[red]You cannot afford that.[/red]")
        elif choice == len(wares):
            result = skill_check(gs.character, "presence", "intrigue", "moderate")
            ui.print(result.describe())
            if result.success:
                discount = random.randint(3, 8)
                gs.character.gold += discount
                ui.narrate(f"Tobbot laughs and presses {discount} silver back into your palm. \"A shrewd one!\"")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary="You won Tobbot's respect with sharp bargaining.",
                    actors=[npc_id], importance=1))
            else:
                ui.narrate("\"Prices are prices, friend.\" He is unmoved.")
        else:
            ui.narrate("\"Bandits on the kingsroad, and worse tales from up north. "
                       "Coin's the only thing that travels safe these days.\"")


def _ranger(ui: UI, gs: GameState, npc_id: str) -> None:
    while True:
        choice = ui.menu(
            "Qorin the Black",
            ["Buy him a drink and listen",
             "Offer to carry word to the Wall",
             "Ask why a ranger is so far from his post"],
            allow_back=True,
        )
        if choice == -1:
            return
        if choice == 0:
            if gs.character.gold >= 2:
                gs.character.gold -= 2
                ui.narrate("He drinks, and for a while the black brother talks - of the Wall, the cold, "
                           "and rangers who ride out and don't ride back.")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary="You shared a drink and an ear with Qorin the ranger.",
                    actors=[npc_id], importance=2))
            else:
                ui.print("[red]You haven't the coin for a drink.[/red]")
        elif choice == 1:
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.OATH,
                summary="You promised Qorin to carry word north to the Wall.",
                actors=[npc_id], location=gs.character.location, importance=3,
                data={"quest": "word_to_the_wall"}))
            gs.world.quests["word_to_the_wall"] = "accepted"
            gs.world.adjust_reputation("nights_watch", 8)
            ui.narrate("\"Then the Watch is in your debt. See that it reaches Castle Black.\"")
        elif choice == 2:
            ui.narrate("\"That,\" he says, draining his cup, \"is Watch business. But if the dead ever walk again, "
                       "you'll wish more men wore the black.\"")
            gs.world.quests.setdefault("the_cold", "heard")


def _wildling(ui: UI, gs: GameState, npc_id: str) -> None:
    disposition = gs.memory.npc_disposition(npc_id) + world_data.NPCS[npc_id].base_disposition
    while True:
        options = ["Speak to her plainly, kneeler to free folk",
                   "Threaten her to move off the kingsroad",
                   "Offer food and safe passage"]
        choice = ui.menu("Ygga Snowhair", options, allow_back=True)
        if choice == -1:
            return
        if choice == 0:
            result = skill_check(gs.character, "presence", "intrigue", "hard")
            ui.print(result.describe())
            if result.success:
                ui.narrate("\"Huh. You talk straight, for a kneeler.\" Some of the wariness leaves her eyes.")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary="You earned a measure of trust from Ygga the free folk raider.",
                    actors=[npc_id], importance=2))
                gs.world.adjust_reputation("free_folk", 6)
            else:
                ui.narrate("She spits at your feet. \"Pretty words. Kneelers are all the same.\"")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.SLIGHT,
                    summary="You gave offence to Ygga with clumsy words.",
                    actors=[npc_id], importance=1))
        elif choice == 1:
            ui.narrate("She bares her teeth and levels her spear. \"Try it, kneeler.\"")
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.SLIGHT,
                summary="You threatened Ygga on the Wolfswood road.",
                actors=[npc_id], importance=3))
            gs.world.adjust_reputation("free_folk", -12)
            reactivity.schedule_ripple(
                gs.world, delay_days=6, kind="reprisal", faction="free_folk", npc=npc_id,
                text="Free folk raiders waylay a road you often travel - Ygga has not forgotten your threat.")
        elif choice == 2:
            if "warm furs" in gs.character.inventory or "healer's satchel" in gs.character.inventory or gs.character.gold >= 5:
                if gs.character.gold >= 5:
                    gs.character.gold -= 5
                ui.narrate("She takes the offering warily, then inclines her head. \"The free folk pay their debts.\"")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.ALLIANCE,
                    summary="You showed kindness to Ygga; the free folk remember a debt owed.",
                    actors=[npc_id], location=gs.character.location, importance=3))
                gs.world.adjust_reputation("free_folk", 15)
                reactivity.schedule_ripple(
                    gs.world, delay_days=10, kind="aid", faction="free_folk", npc=npc_id,
                    text="A free folk runner leaves a fine bone-and-iron knife where you'll find it - Ygga repays her debt.")
            else:
                ui.print("[red]You have nothing to offer her.[/red]")


def _generic_conversation(ui: UI, gs: GameState, npc_id: str) -> None:
    """A flexible conversation for authored seat NPCs and generated locals.

    The options offered depend on the NPC's role (read from their title), so a
    trader will barter, a steward will grant or deny an audience, and anyone will
    trade rumor for a moment of your time.
    """
    npc = world_data.get_npc(npc_id, gs.world)
    title = (npc.title or "").lower()
    trader = any(w in title for w in ("trader", "merchant", "innkeep", "reeve", "armorer", "smith"))
    official = any(w in title for w in ("castellan", "steward", "seneschal", "captain",
                                        "officer", "master", "knight", "maester"))
    while True:
        options = ["Ask after news and rumor"]
        handlers = ["news"]
        if trader:
            options.append("Trade and barter"); handlers.append("trade")
        if official:
            options.append("Seek their favour"); handlers.append("favour")
        options.append("Take your leave"); handlers.append("leave")
        idx = ui.menu(f"{npc.name}, {npc.title}", options, allow_back=True)
        if idx in (-1, len(options) - 1):
            _record_dialogue(gs, npc_id, f"You spoke with {npc.name} at {_place(gs)}.")
            return
        choice = handlers[idx]
        if choice == "news":
            ui.narrate(f"{npc.name} shares what the day has brought - the price of grain, "
                       "the doings of lords, and who was seen where they ought not to be.")
            gs.memory.record(Event(
                game_day=gs.world.day, type=EventType.DISCOVERY,
                summary=f"{npc.name} told you the local news.", actors=[npc_id], importance=1))
        elif choice == "trade":
            ui.narrate(f"{npc.name} lays out their wares and haggles with the ease of long practice.")
            _record_dialogue(gs, npc_id, f"You traded with {npc.name}.")
        elif choice == "favour":
            check = skill_check(gs.character, "presence", "intrigue", "moderate")
            ui.print(check.describe())
            if check.success:
                ui.narrate(f"{npc.name} warms to you, and marks you as someone worth knowing.")
                gs.memory.record(Event(
                    game_day=gs.world.day, type=EventType.FAVOR,
                    summary=f"You won the goodwill of {npc.name}.", actors=[npc_id], importance=2))
            else:
                ui.narrate(f"{npc.name} hears you out, but gives you nothing for your trouble.")


def _place(gs: GameState) -> str:
    loc = world_data.get_location(gs.character.location, gs.world)
    return loc.name if loc else "this place"


_HANDLERS: Dict[str, Callable[[UI, GameState, str], None]] = {
    "master_at_arms": _master_at_arms,
    "maester": _maester,
    "septa_or_woodswitch": _woodswitch,
    "merchant": _merchant,
    "ranger": _ranger,
    "wildling": _wildling,
}
