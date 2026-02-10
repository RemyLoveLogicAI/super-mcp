"""AI-Driven D&D Quest — full campaign engine.

The AI acts as Dungeon Master. Rule-bounded world with
deterministic combat, character sheets, quest logs, and NPC registries.
Everything is logged and checkpointable.
"""

from __future__ import annotations

import random
from typing import Any

from src.games.engine.runner import GameInterface, GameOutput
from src.games.engine.state import GameAction, GamePhase, GameState

# --- D&D Rules and Data ---

RACES = {
    "human": {"str_mod": 1, "dex_mod": 1, "con_mod": 1, "int_mod": 1, "wis_mod": 1, "cha_mod": 1,
              "desc": "Versatile and ambitious. +1 to all ability scores."},
    "elf": {"str_mod": 0, "dex_mod": 2, "con_mod": 0, "int_mod": 1, "wis_mod": 0, "cha_mod": 0,
            "desc": "Graceful and perceptive. +2 DEX, +1 INT. Darkvision."},
    "dwarf": {"str_mod": 2, "dex_mod": 0, "con_mod": 2, "int_mod": 0, "wis_mod": 1, "cha_mod": 0,
              "desc": "Sturdy and resilient. +2 STR, +2 CON, +1 WIS. Poison resistance."},
    "halfling": {"str_mod": 0, "dex_mod": 2, "con_mod": 1, "int_mod": 0, "wis_mod": 0, "cha_mod": 1,
                 "desc": "Lucky and brave. +2 DEX, +1 CON, +1 CHA. Reroll natural 1s."},
    "tiefling": {"str_mod": 0, "dex_mod": 0, "con_mod": 0, "int_mod": 1, "wis_mod": 0, "cha_mod": 2,
                 "desc": "Infernal heritage. +1 INT, +2 CHA. Fire resistance."},
}

CLASSES = {
    "warrior": {"hit_die": 10, "primary": "str", "save": ["str", "con"],
                "desc": "Master of martial combat. Heavy armor. d10 hit die."},
    "mage": {"hit_die": 6, "primary": "int", "save": ["int", "wis"],
             "desc": "Wielder of arcane magic. Spellcasting. d6 hit die."},
    "rogue": {"hit_die": 8, "primary": "dex", "save": ["dex", "int"],
              "desc": "Cunning and stealthy. Sneak attack. d8 hit die."},
    "cleric": {"hit_die": 8, "primary": "wis", "save": ["wis", "cha"],
               "desc": "Divine spellcaster. Healing. d8 hit die."},
    "ranger": {"hit_die": 10, "primary": "dex", "save": ["str", "dex"],
               "desc": "Wilderness expert. Dual wielding. d10 hit die."},
}

STARTER_QUEST = {
    "name": "The Darkened Hollow",
    "description": "A shadow has fallen over the village of Thornfield. Livestock vanish by night, and strange marks appear on the standing stones at the forest edge. The village elder begs for aid.",
    "objectives": [
        "Investigate the standing stones at the forest edge",
        "Find the source of the shadow plaguing Thornfield",
        "Defeat or banish the threat",
    ],
    "reward": "200 gold, Amulet of Minor Warding",
}

ROOMS = {
    "village_square": {
        "name": "Thornfield Village Square",
        "desc": "A modest square surrounded by thatched-roof cottages. A well stands at the center. The village elder waits near the notice board. The forest looms to the north.",
        "exits": {"north": "forest_edge", "east": "tavern", "west": "blacksmith"},
        "npcs": ["elder_maren"],
        "items": [],
    },
    "tavern": {
        "name": "The Rusty Flagon",
        "desc": "A warm tavern with a crackling hearth. A few villagers nurse their ales. The barkeep polishes a glass, eyeing you warily.",
        "exits": {"west": "village_square"},
        "npcs": ["barkeep_dorn"],
        "items": ["healing_potion"],
    },
    "blacksmith": {
        "name": "Ironheart Forge",
        "desc": "The heat of the forge washes over you. Weapons and armor line the walls. The blacksmith hammers away at a blade.",
        "exits": {"east": "village_square"},
        "npcs": ["smith_kael"],
        "items": ["iron_shield"],
    },
    "forest_edge": {
        "name": "Forest Edge — Standing Stones",
        "desc": "Ancient stones rise from the earth in a rough circle. Strange runes glow faintly in the moonlight. A path leads deeper into the Darkened Hollow.",
        "exits": {"south": "village_square", "north": "dark_hollow_entrance"},
        "npcs": [],
        "items": ["rune_fragment"],
    },
    "dark_hollow_entrance": {
        "name": "The Darkened Hollow — Entrance",
        "desc": "The trees close overhead, blocking the sky. The air grows cold. You can hear dripping water and something else... a low, rhythmic chanting from deeper within.",
        "exits": {"south": "forest_edge", "north": "hollow_depths"},
        "npcs": ["shadow_wisp"],
        "items": [],
    },
    "hollow_depths": {
        "name": "The Darkened Hollow — Depths",
        "desc": "A vast underground chamber lit by sickly green fungus. At its center, a corrupted altar pulses with dark energy. A hooded figure stands before it, channeling shadow magic.",
        "exits": {"south": "dark_hollow_entrance"},
        "npcs": ["shadow_priest"],
        "items": ["shadow_orb"],
    },
}

NPCS = {
    "elder_maren": {
        "name": "Elder Maren",
        "role": "Quest Giver",
        "dialogue": {
            "greet": "Thank the gods you've come! Our village is cursed. Shadows move at night, and our livestock... please, investigate the standing stones north of here.",
            "quest": "The standing stones were once a place of protection. Now something dark corrupts them. I fear an ancient evil stirs in the Hollow beyond.",
            "farewell": "Be careful, adventurer. The Hollow has swallowed many brave souls.",
        },
        "hostile": False,
        "hp": 8,
        "ac": 10,
    },
    "barkeep_dorn": {
        "name": "Dorn the Barkeep",
        "role": "Merchant",
        "dialogue": {
            "greet": "What'll it be? We've got ale and rumors. Both are cheap.",
            "rumor": "I heard the smith found strange metal near the stones. Glowed like embers, he said. Wouldn't touch it myself.",
            "farewell": "Watch yourself out there.",
        },
        "hostile": False,
        "hp": 12,
        "ac": 11,
    },
    "smith_kael": {
        "name": "Kael the Blacksmith",
        "role": "Merchant",
        "dialogue": {
            "greet": "Adventurer, eh? I've got steel if you've got coin.",
            "rumor": "Found a shard of black iron near the stones. Never seen anything like it. It whispers if you hold it too long.",
            "farewell": "Swing true.",
        },
        "hostile": False,
        "hp": 15,
        "ac": 13,
    },
    "shadow_wisp": {
        "name": "Shadow Wisp",
        "role": "Monster",
        "hostile": True,
        "hp": 15,
        "ac": 13,
        "attack": 4,
        "damage": "1d6",
        "xp": 50,
    },
    "shadow_priest": {
        "name": "Shadow Priest Vordak",
        "role": "Boss",
        "hostile": True,
        "hp": 35,
        "ac": 15,
        "attack": 6,
        "damage": "2d6",
        "xp": 200,
        "dialogue": {
            "greet": "You dare interrupt the ritual? The shadow will consume this land, and you with it!",
        },
    },
}


def roll_dice(sides: int, count: int = 1) -> tuple[list[int], int]:
    """Roll dice deterministically (seeded from game state for replay)."""
    rolls = [random.randint(1, sides) for _ in range(count)]
    return rolls, sum(rolls)


def roll_ability_scores() -> dict[str, int]:
    """4d6 drop lowest for each ability."""
    abilities = {}
    for stat in ["str", "dex", "con", "int", "wis", "cha"]:
        rolls = sorted([random.randint(1, 6) for _ in range(4)])
        abilities[stat] = sum(rolls[1:])  # drop lowest
    return abilities


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


class DnDGame(GameInterface):
    """Full D&D quest engine."""

    def game_type(self) -> str:
        return "dnd"

    async def initialize(self, state: GameState) -> GameOutput:
        state.phase = GamePhase.CHARACTER_CREATION
        state.world = {
            "rooms": {k: dict(v) for k, v in ROOMS.items()},
            "current_room": "village_square",
        }
        state.npcs = {k: dict(v) for k, v in NPCS.items()}
        state.quest_log = [dict(STARTER_QUEST)]
        state.metadata["seed"] = random.randint(0, 2**32)

        race_list = "\n".join(
            f"  [{r}] {data['desc']}" for r, data in RACES.items()
        )
        class_list = "\n".join(
            f"  [{c}] {data['desc']}" for c, data in CLASSES.items()
        )

        narrative = f"""
╔══════════════════════════════════════════════════════════════╗
║               THE DARKENED HOLLOW                           ║
║           An AI-Driven D&D Quest                            ║
╚══════════════════════════════════════════════════════════════╝

A shadow has fallen over the village of Thornfield...

═══ CHARACTER CREATION ═══

Choose your race:
{race_list}

Choose your class:
{class_list}

Enter your character as: <name> <race> <class>
Example: Thorin dwarf warrior
"""
        return GameOutput(
            narrative=narrative.strip(),
            prompt="Create your character> ",
            options=list(RACES.keys()),
        )

    async def process_input(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]:
        # Character creation
        if state.phase == GamePhase.CHARACTER_CREATION:
            return await self._create_character(user_input, state)

        # Combat
        if state.phase == GamePhase.COMBAT:
            return await self._combat_turn(user_input, state)

        # Exploration
        return await self._exploration_turn(user_input, state)

    async def _create_character(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]:
        parts = user_input.strip().split()
        if len(parts) < 3:
            return (
                GameOutput(narrative="Format: <name> <race> <class>", prompt="Create your character> "),
                GameAction(actor="player", action_type="invalid", description=user_input, valid=False),
            )

        name = parts[0].capitalize()
        race = parts[1].lower()
        char_class = parts[2].lower()

        if race not in RACES:
            return (
                GameOutput(narrative=f"Unknown race: {race}. Choose from: {', '.join(RACES.keys())}"),
                GameAction(actor="player", action_type="invalid", valid=False),
            )
        if char_class not in CLASSES:
            return (
                GameOutput(narrative=f"Unknown class: {char_class}. Choose from: {', '.join(CLASSES.keys())}"),
                GameAction(actor="player", action_type="invalid", valid=False),
            )

        # Roll stats
        random.seed(state.metadata.get("seed", 42))
        abilities = roll_ability_scores()
        race_mods = RACES[race]
        for stat in abilities:
            abilities[stat] += race_mods.get(f"{stat}_mod", 0)

        class_data = CLASSES[char_class]
        hp = class_data["hit_die"] + ability_modifier(abilities["con"])

        state.player = {
            "name": name,
            "race": race,
            "class": char_class,
            "level": 1,
            "xp": 0,
            "hp": hp,
            "max_hp": hp,
            "ac": 10 + ability_modifier(abilities["dex"]),
            "abilities": abilities,
            "gold": 50,
        }
        state.inventory = ["torch", "rope", "rations"]
        state.phase = GamePhase.PLAYING

        sheet = self._format_character_sheet(state)
        room = self._describe_room(state)

        action = GameAction(
            actor="player",
            action_type="create_character",
            description=f"Created {name} the {race} {char_class}",
            result="Character created",
            action_data={"name": name, "race": race, "class": char_class},
        )

        return (
            GameOutput(
                narrative=f"═══ CHARACTER CREATED ═══\n\n{sheet}\n\n{'═' * 40}\n\n{room}",
                prompt=f"[{name}]> ",
            ),
            action,
        )

    async def _exploration_turn(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]:
        cmd = user_input.strip().lower()
        parts = cmd.split(maxsplit=1)
        verb = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""

        current_room_id = state.world.get("current_room", "village_square")
        room = state.world["rooms"].get(current_room_id, ROOMS["village_square"])

        # Movement
        if verb in ("go", "move", "walk", "north", "south", "east", "west"):
            direction = target if verb in ("go", "move", "walk") else verb
            exits = room.get("exits", {})
            if direction in exits:
                new_room_id = exits[direction]
                state.world["current_room"] = new_room_id
                new_room = state.world["rooms"].get(new_room_id, ROOMS.get(new_room_id, {}))

                # Check for hostile NPCs
                hostile_npcs = [
                    npc_id for npc_id in new_room.get("npcs", [])
                    if state.npcs.get(npc_id, {}).get("hostile", False)
                    and state.npcs.get(npc_id, {}).get("hp", 0) > 0
                ]

                narrative = self._describe_room(state)

                if hostile_npcs:
                    state.phase = GamePhase.COMBAT
                    state.metadata["combat_target"] = hostile_npcs[0]
                    npc = state.npcs[hostile_npcs[0]]
                    narrative += f"\n\n⚔️  COMBAT! {npc['name']} attacks!\n"
                    narrative += f"Enemy HP: {npc['hp']} | AC: {npc['ac']}\n"
                    narrative += "Commands: attack, defend, flee, use <item>"

                return (
                    GameOutput(narrative=narrative, prompt=self._prompt(state)),
                    GameAction(actor="player", action_type="move", description=f"Moved {direction}",
                              action_data={"direction": direction, "room": new_room_id}),
                )
            else:
                available = ", ".join(exits.keys())
                return (
                    GameOutput(narrative=f"You can't go {direction}. Exits: {available}"),
                    GameAction(actor="player", action_type="move", valid=False),
                )

        # Look
        if verb in ("look", "examine", "inspect"):
            desc = self._describe_room(state, verbose=True)
            return (
                GameOutput(narrative=desc),
                GameAction(actor="player", action_type="look", description=f"Examined {target or 'surroundings'}"),
            )

        # Talk
        if verb in ("talk", "speak", "ask"):
            npc_ids = room.get("npcs", [])
            if not npc_ids:
                return (GameOutput(narrative="There's no one here to talk to."),
                        GameAction(actor="player", action_type="talk", valid=False))

            matching = [n for n in npc_ids if target in state.npcs.get(n, {}).get("name", "").lower()]
            npc_id = matching[0] if matching else npc_ids[0]
            npc = state.npcs.get(npc_id, {})
            dialogue = npc.get("dialogue", {})
            response = dialogue.get("greet", "...")

            return (
                GameOutput(narrative=f'**{npc.get("name", "NPC")}**: "{response}"'),
                GameAction(actor="player", action_type="talk", description=f"Talked to {npc.get('name')}",
                          action_data={"npc": npc_id}),
            )

        # Take
        if verb in ("take", "pick", "grab", "get"):
            items = room.get("items", [])
            if not items:
                return (GameOutput(narrative="Nothing to pick up here."),
                        GameAction(actor="player", action_type="take", valid=False))

            matching = [i for i in items if target in i.lower()]
            item = matching[0] if matching else items[0]

            state.inventory.append(item)
            room["items"].remove(item)

            return (
                GameOutput(narrative=f"Picked up: {item.replace('_', ' ').title()}"),
                GameAction(actor="player", action_type="take", description=f"Took {item}",
                          action_data={"item": item}),
            )

        # Inventory
        if verb in ("inventory", "inv", "i", "bag"):
            inv = ", ".join(i.replace("_", " ").title() for i in state.inventory) or "Empty"
            gold = state.player.get("gold", 0)
            return (
                GameOutput(narrative=f"═══ INVENTORY ═══\n{inv}\nGold: {gold}"),
                GameAction(actor="player", action_type="inventory"),
            )

        # Character sheet
        if verb in ("character", "char", "sheet", "stats"):
            return (
                GameOutput(narrative=self._format_character_sheet(state)),
                GameAction(actor="player", action_type="character"),
            )

        return (
            GameOutput(narrative="Unknown command. Try: go/look/talk/take/inventory/character"),
            GameAction(actor="player", action_type="unknown", description=user_input, valid=False),
        )

    async def _combat_turn(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]:
        cmd = user_input.strip().lower()
        target_id = state.metadata.get("combat_target")
        if not target_id:
            state.phase = GamePhase.PLAYING
            return (GameOutput(narrative="Combat ended."), GameAction(actor="system", action_type="combat_end"))

        npc = state.npcs.get(target_id, {})
        player = state.player

        if cmd in ("attack", "hit", "strike"):
            # Player attack
            _, player_roll = roll_dice(20)
            atk_mod = ability_modifier(player["abilities"][CLASSES[player["class"]]["primary"]])
            total_atk = player_roll + atk_mod

            narrative = f"You roll to attack: {player_roll} + {atk_mod} = {total_atk}"

            if total_atk >= npc.get("ac", 10):
                _, damage = roll_dice(CLASSES[player["class"]]["hit_die"])
                npc["hp"] = npc.get("hp", 0) - damage
                narrative += f"\n  HIT! You deal {damage} damage."
                narrative += f"\n  {npc['name']} HP: {npc['hp']}/{npc.get('max_hp', npc.get('hp', 0) + damage)}"

                if npc.get("hp", 0) <= 0:
                    xp = npc.get("xp", 50)
                    player["xp"] = player.get("xp", 0) + xp
                    state.phase = GamePhase.PLAYING
                    state.metadata.pop("combat_target", None)
                    narrative += f"\n\n  ✨ {npc['name']} is defeated! +{xp} XP"

                    # Check quest progress
                    if target_id == "shadow_priest":
                        state.flags["boss_defeated"] = True
                        narrative += "\n\n═══ QUEST COMPLETE: The Darkened Hollow ═══"
                        narrative += "\nThe shadow dissipates. Thornfield is saved!"
                        narrative += f"\nReward: {STARTER_QUEST['reward']}"
                        player["gold"] = player.get("gold", 0) + 200
            else:
                narrative += "\n  MISS!"

            # Enemy counter-attack (if alive)
            if npc.get("hp", 0) > 0:
                _, enemy_roll = roll_dice(20)
                enemy_atk = enemy_roll + npc.get("attack", 3)
                narrative += f"\n\n{npc['name']} attacks: {enemy_roll} + {npc.get('attack', 3)} = {enemy_atk}"

                if enemy_atk >= player.get("ac", 10):
                    dmg_sides = int(npc.get("damage", "1d6").split("d")[1])
                    dmg_count = int(npc.get("damage", "1d6").split("d")[0])
                    _, enemy_damage = roll_dice(dmg_sides, dmg_count)
                    player["hp"] -= enemy_damage
                    narrative += f"\n  HIT! Takes {enemy_damage} damage."
                    narrative += f"\n  Your HP: {player['hp']}/{player['max_hp']}"

                    if player["hp"] <= 0:
                        state.phase = GamePhase.GAME_OVER
                        narrative += "\n\n💀 You have fallen in battle. GAME OVER."
                        return (
                            GameOutput(narrative=narrative, game_over=True),
                            GameAction(actor="system", action_type="game_over"),
                        )
                else:
                    narrative += "\n  MISS!"

            return (
                GameOutput(narrative=narrative, prompt=self._prompt(state)),
                GameAction(actor="player", action_type="attack", description=f"Attacked {npc['name']}"),
            )

        if cmd in ("flee", "run", "escape"):
            _, roll = roll_dice(20)
            dex_mod = ability_modifier(player["abilities"]["dex"])
            if roll + dex_mod >= 12:
                state.phase = GamePhase.PLAYING
                state.metadata.pop("combat_target", None)
                # Move back
                current = state.world.get("current_room", "")
                exits = ROOMS.get(current, {}).get("exits", {})
                if exits:
                    first_exit = list(exits.values())[0]
                    state.world["current_room"] = first_exit
                return (
                    GameOutput(narrative=f"You flee! (Roll: {roll}+{dex_mod}={roll+dex_mod} vs DC 12)\n\n{self._describe_room(state)}"),
                    GameAction(actor="player", action_type="flee"),
                )
            else:
                return (
                    GameOutput(narrative=f"Failed to flee! (Roll: {roll}+{dex_mod}={roll+dex_mod} vs DC 12)"),
                    GameAction(actor="player", action_type="flee", valid=False),
                )

        if cmd.startswith("use "):
            item = cmd[4:].strip().replace(" ", "_")
            if item == "healing_potion" and "healing_potion" in state.inventory:
                _, heal = roll_dice(8)
                heal += 2
                player["hp"] = min(player["hp"] + heal, player["max_hp"])
                state.inventory.remove("healing_potion")
                return (
                    GameOutput(narrative=f"You drink the healing potion. Restored {heal} HP. (HP: {player['hp']}/{player['max_hp']})"),
                    GameAction(actor="player", action_type="use_item", action_data={"item": item}),
                )
            return (GameOutput(narrative=f"Can't use {item} here."),
                    GameAction(actor="player", action_type="use_item", valid=False))

        return (
            GameOutput(narrative="Combat commands: attack, flee, use <item>"),
            GameAction(actor="player", action_type="unknown", valid=False),
        )

    def validate_input(self, user_input: str, state: GameState) -> tuple[bool, str]:
        if not user_input.strip():
            return False, "Enter a command. Type /help for help."
        return True, ""

    async def get_help(self) -> str:
        return """
═══ D&D QUEST COMMANDS ═══

EXPLORATION:
  go <direction>    Move (north/south/east/west)
  look              Examine surroundings
  talk [npc]        Speak with NPC
  take [item]       Pick up item
  inventory         Show inventory
  character         Show character sheet

COMBAT:
  attack            Attack the enemy
  flee              Attempt to escape
  use <item>        Use an item

META:
  /save             Save game
  /load             Load a save
  /undo             Undo last action
  /redo             Redo action
  /status           Game status
  /replay           View action history
  /help             This help
  /quit             End game
"""

    async def generate_summary(self, state: GameState) -> str:
        p = state.player
        if not p:
            return "No active character."
        return (
            f"═══ SESSION SUMMARY ═══\n"
            f"Character: {p.get('name', '?')} the {p.get('race', '?')} {p.get('class', '?')}\n"
            f"Level: {p.get('level', 1)} | XP: {p.get('xp', 0)}\n"
            f"HP: {p.get('hp', 0)}/{p.get('max_hp', 0)}\n"
            f"Gold: {p.get('gold', 0)}\n"
            f"Turns played: {state.turn_number}\n"
            f"Items: {', '.join(state.inventory) or 'None'}\n"
            f"Quests: {len(state.quest_log)}\n"
            f"Boss defeated: {'Yes' if state.flags.get('boss_defeated') else 'No'}"
        )

    def _prompt(self, state: GameState) -> str:
        name = state.player.get("name", "Hero")
        if state.phase == GamePhase.COMBAT:
            return f"[{name} ⚔️ ]> "
        return f"[{name}]> "

    def _describe_room(self, state: GameState, verbose: bool = False) -> str:
        room_id = state.world.get("current_room", "village_square")
        room = state.world["rooms"].get(room_id, ROOMS.get(room_id, {}))

        lines = [f"📍 **{room.get('name', room_id)}**"]
        lines.append(room.get("desc", ""))

        npcs = room.get("npcs", [])
        alive_npcs = [
            n for n in npcs
            if state.npcs.get(n, {}).get("hp", 1) > 0
        ]
        if alive_npcs:
            npc_names = [state.npcs.get(n, {}).get("name", n) for n in alive_npcs]
            lines.append(f"\nPresent: {', '.join(npc_names)}")

        items = room.get("items", [])
        if items:
            item_names = [i.replace("_", " ").title() for i in items]
            lines.append(f"Items: {', '.join(item_names)}")

        exits = room.get("exits", {})
        if exits:
            lines.append(f"Exits: {', '.join(exits.keys())}")

        return "\n".join(lines)

    def _format_character_sheet(self, state: GameState) -> str:
        p = state.player
        if not p:
            return "No character."
        abilities = p.get("abilities", {})
        return (
            f"═══ CHARACTER SHEET ═══\n"
            f"  Name:  {p.get('name', '?')}\n"
            f"  Race:  {p.get('race', '?').title()}\n"
            f"  Class: {p.get('class', '?').title()}\n"
            f"  Level: {p.get('level', 1)}\n"
            f"  XP:    {p.get('xp', 0)}\n"
            f"  HP:    {p.get('hp', 0)}/{p.get('max_hp', 0)}\n"
            f"  AC:    {p.get('ac', 10)}\n"
            f"  Gold:  {p.get('gold', 0)}\n"
            f"  ─────────────────\n"
            f"  STR: {abilities.get('str', 10)} ({ability_modifier(abilities.get('str', 10)):+d})\n"
            f"  DEX: {abilities.get('dex', 10)} ({ability_modifier(abilities.get('dex', 10)):+d})\n"
            f"  CON: {abilities.get('con', 10)} ({ability_modifier(abilities.get('con', 10)):+d})\n"
            f"  INT: {abilities.get('int', 10)} ({ability_modifier(abilities.get('int', 10)):+d})\n"
            f"  WIS: {abilities.get('wis', 10)} ({ability_modifier(abilities.get('wis', 10)):+d})\n"
            f"  CHA: {abilities.get('cha', 10)} ({ability_modifier(abilities.get('cha', 10)):+d})"
        )
