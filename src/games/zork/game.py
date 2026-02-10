"""Zork-Style Interactive Fiction — parser-based text adventure.

A modern AI-driven re-implementation inspired by Zork.
Text-only, parser-style interaction with strict command grammar,
flexible interpretation, state inspection, undo/rewind, save slots,
and session replay. Fully integrated with Super-MCP logging.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.games.engine.runner import GameInterface
from src.games.engine.state import GameStateManager
from src.kernel.types import GameType


# ── World model ──────────────────────────────────────────────────────

class Direction(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    UP = "up"
    DOWN = "down"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"


DIRECTION_ALIASES: dict[str, Direction] = {
    "n": Direction.NORTH, "north": Direction.NORTH,
    "s": Direction.SOUTH, "south": Direction.SOUTH,
    "e": Direction.EAST, "east": Direction.EAST,
    "w": Direction.WEST, "west": Direction.WEST,
    "u": Direction.UP, "up": Direction.UP,
    "d": Direction.DOWN, "down": Direction.DOWN,
    "ne": Direction.NORTHEAST, "northeast": Direction.NORTHEAST,
    "nw": Direction.NORTHWEST, "northwest": Direction.NORTHWEST,
    "se": Direction.SOUTHEAST, "southeast": Direction.SOUTHEAST,
    "sw": Direction.SOUTHWEST, "southwest": Direction.SOUTHWEST,
}


@dataclass
class Item:
    id: str
    name: str
    description: str
    takeable: bool = True
    weight: int = 1
    usable_with: list[str] = field(default_factory=list)
    examine_text: str = ""
    hidden: bool = False
    is_light_source: bool = False
    is_container: bool = False
    contains: list[str] = field(default_factory=list)
    is_weapon: bool = False
    damage: int = 0
    special_use: str | None = None  # trigger ID for scripted events


@dataclass
class NPC:
    id: str
    name: str
    description: str
    dialogue: dict[str, str] = field(default_factory=dict)  # topic → response
    hostile: bool = False
    health: int = 10
    damage: int = 2
    drops: list[str] = field(default_factory=list)
    defeat_flag: str = ""
    block_direction: Direction | None = None
    block_message: str = ""
    alive: bool = True


@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: dict[Direction, str] = field(default_factory=dict)  # direction → room_id
    items: list[str] = field(default_factory=list)  # item IDs present
    npcs: list[str] = field(default_factory=list)   # NPC IDs present
    dark: bool = False
    visited: bool = False
    on_enter: str | None = None   # trigger ID
    on_exit: str | None = None    # trigger ID
    locked_exits: dict[Direction, str] = field(default_factory=dict)  # direction → key_item_id
    description_variants: dict[str, str] = field(default_factory=dict)  # flag → alt description


# ── Parser ───────────────────────────────────────────────────────────

VERB_SYNONYMS: dict[str, str] = {
    # movement
    "go": "go", "walk": "go", "move": "go", "head": "go", "travel": "go",
    "run": "go", "enter": "go", "proceed": "go",
    # look
    "look": "look", "l": "look", "examine": "examine", "x": "examine",
    "inspect": "examine", "study": "examine", "read": "examine",
    "search": "search", "peek": "look",
    # inventory
    "take": "take", "get": "take", "grab": "take", "pick": "take",
    "collect": "take", "acquire": "take",
    "drop": "drop", "discard": "drop", "leave": "drop", "put": "drop",
    "inventory": "inventory", "i": "inventory", "inv": "inventory",
    # interaction
    "open": "open", "unlock": "open",
    "close": "close", "shut": "close",
    "use": "use", "apply": "use", "activate": "use",
    "give": "give", "offer": "give", "hand": "give",
    "talk": "talk", "speak": "talk", "ask": "talk", "chat": "talk",
    "say": "talk",
    # combat
    "attack": "attack", "hit": "attack", "strike": "attack",
    "fight": "attack", "kill": "attack", "slay": "attack",
    # misc
    "wait": "wait", "z": "wait",
    "listen": "listen", "smell": "smell",
    "push": "push", "pull": "pull",
    "climb": "climb", "jump": "jump",
    "light": "light", "ignite": "light",
    "eat": "eat", "drink": "drink",
    "wear": "wear", "equip": "wear",
    "remove": "remove", "unequip": "remove",
    "help": "help", "hint": "hint",
    "score": "score", "points": "score",
    "diagnose": "diagnose",
}


@dataclass
class ParsedCommand:
    verb: str
    noun: str = ""
    preposition: str = ""
    indirect_object: str = ""
    raw: str = ""


def parse_command(raw: str) -> ParsedCommand:
    """Parse natural-language-ish input into structured command."""
    raw = raw.strip().lower()
    if not raw:
        return ParsedCommand(verb="", raw=raw)

    # Check if it's a bare direction
    if raw in DIRECTION_ALIASES:
        return ParsedCommand(verb="go", noun=raw, raw=raw)

    words = raw.split()
    verb_word = words[0]
    verb = VERB_SYNONYMS.get(verb_word, verb_word)

    # Handle "pick up X" → take X
    if verb_word == "pick" and len(words) > 1 and words[1] == "up":
        verb = "take"
        words = [verb_word] + words[2:]

    # Handle "look at X" → examine X
    if verb == "look" and len(words) > 1 and words[1] == "at":
        verb = "examine"
        words = [verb_word] + words[2:]

    # Handle "talk to X about Y"
    prepositions = {"to", "with", "at", "on", "in", "into", "from", "about", "using"}
    noun_parts: list[str] = []
    prep = ""
    indirect_parts: list[str] = []
    in_indirect = False

    for w in words[1:]:
        if w in prepositions and not in_indirect:
            if noun_parts:
                prep = w
                in_indirect = True
            else:
                # Preposition right after verb (e.g., "look at")
                continue
        elif in_indirect:
            indirect_parts.append(w)
        else:
            noun_parts.append(w)

    noun = " ".join(noun_parts)
    indirect = " ".join(indirect_parts)

    return ParsedCommand(
        verb=verb,
        noun=noun,
        preposition=prep,
        indirect_object=indirect,
        raw=raw,
    )


# ── World definition: The Ruins of Zyl ──────────────────────────────

def build_world() -> tuple[dict[str, Room], dict[str, Item], dict[str, NPC]]:
    """Construct the game world: The Ruins of Zyl."""

    items: dict[str, Item] = {
        "brass_lantern": Item(
            id="brass_lantern",
            name="brass lantern",
            description="A sturdy brass lantern with a wick that looks ready to light.",
            examine_text="The lantern is well-crafted, with a hinged glass panel "
                         "and a small dial on the side. It smells faintly of oil.",
            is_light_source=True,
            weight=2,
        ),
        "rusty_key": Item(
            id="rusty_key",
            name="rusty key",
            description="A heavy iron key covered in orange rust.",
            examine_text="Despite the rust, the teeth of the key are still intact. "
                         "It looks like it would fit an old lock.",
            weight=1,
        ),
        "ancient_sword": Item(
            id="ancient_sword",
            name="ancient sword",
            description="A gleaming sword with elven runes along its blade.",
            examine_text="The blade is impossibly sharp despite its age. The runes "
                         "pulse with a faint blue light. The hilt is wrapped in "
                         "leather that never seems to decay.",
            is_weapon=True,
            damage=5,
            weight=3,
        ),
        "silver_amulet": Item(
            id="silver_amulet",
            name="silver amulet",
            description="A silver amulet shaped like a crescent moon.",
            examine_text="The amulet thrums with protective energy. Tiny sapphires "
                         "are set along its curved edge.",
            special_use="ward_ghost",
            weight=1,
        ),
        "dusty_tome": Item(
            id="dusty_tome",
            name="dusty tome",
            description="A leather-bound book with gilt-edged pages.",
            examine_text="The title reads: 'A History of Zyl and Its Guardians.' "
                         "Within its pages you find references to a great crystal "
                         "that powered the city, protected by three trials: "
                         "wit, courage, and mercy.",
            weight=2,
        ),
        "loaf_of_bread": Item(
            id="loaf_of_bread",
            name="loaf of bread",
            description="A surprisingly fresh loaf of dark rye bread.",
            examine_text="It's warm to the touch and smells wonderful. "
                         "Someone—or something—baked this recently.",
            weight=1,
        ),
        "iron_shield": Item(
            id="iron_shield",
            name="iron shield",
            description="A battered iron shield with a lion emblem.",
            examine_text="The shield has seen many battles. The lion emblem "
                         "is scratched but proud.",
            weight=4,
        ),
        "crystal_shard": Item(
            id="crystal_shard",
            name="crystal shard",
            description="A glowing fragment of the legendary Crystal of Zyl.",
            examine_text="The shard emits a warm, steady light and hums at a "
                         "frequency just below hearing. It feels alive.",
            takeable=True,
            weight=1,
        ),
        "golden_goblet": Item(
            id="golden_goblet",
            name="golden goblet",
            description="An ornate golden goblet encrusted with rubies.",
            examine_text="Worth a small fortune. The rubies catch the light "
                         "and scatter crimson flecks across the walls.",
            weight=2,
        ),
        "rope": Item(
            id="rope",
            name="coil of rope",
            description="A thick hemp rope, about 30 feet long.",
            examine_text="Strong braided hemp. Could support considerable weight.",
            weight=3,
        ),
        "skeleton_key": Item(
            id="skeleton_key",
            name="skeleton key",
            description="A bone-white key carved from actual bone.",
            examine_text="The key is carved from a single piece of bone, "
                         "with teeth that seem to shift when you're not looking.",
            hidden=True,
            weight=1,
        ),
        "music_box": Item(
            id="music_box",
            name="music box",
            description="A small mechanical music box with a silver crank.",
            examine_text="When wound, it plays a melancholic tune. The melody "
                         "seems to calm the very air around it.",
            special_use="calm_guardian",
            weight=1,
        ),
        "torch": Item(
            id="torch",
            name="unlit torch",
            description="A wooden torch wrapped in oil-soaked rags.",
            examine_text="Ready to be lit. The oil is fresh.",
            is_light_source=True,
            weight=2,
        ),
        "emerald_ring": Item(
            id="emerald_ring",
            name="emerald ring",
            description="A ring with a large, flawless emerald.",
            examine_text="The emerald seems to contain a miniature storm, "
                         "clouds swirling within its green depths.",
            hidden=True,
            weight=1,
        ),
    }

    npcs: dict[str, NPC] = {
        "stone_guardian": NPC(
            id="stone_guardian",
            name="Stone Guardian",
            description="A massive humanoid figure carved from living stone. "
                        "Its eyes glow with amber light, and it holds a "
                        "great stone hammer at the ready.",
            dialogue={
                "default": "The Guardian rumbles: 'NONE SHALL PASS WITHOUT THE TRIAL OF WIT.'",
                "riddle": "The Guardian speaks: 'WHAT HAS ROOTS THAT NOBODY SEES, "
                          "IS TALLER THAN TREES, UP UP IT GOES, AND YET NEVER GROWS?'",
                "mountain": "The Guardian's eyes dim. 'CORRECT. THE WAY IS OPEN.' "
                            "The great stone figure steps aside with a grinding roar.",
                "wrong": "The Guardian shakes its head. 'INCORRECT. TRY AGAIN, MORTAL.'",
            },
            hostile=False,
            health=100,
            damage=8,
            block_direction=Direction.SOUTH,
            block_message="The Stone Guardian blocks your path, "
                          "its hammer raised in warning.",
            defeat_flag="guardian_answered",
        ),
        "ghost_scholar": NPC(
            id="ghost_scholar",
            name="Ghost of the Scholar",
            description="A translucent apparition in tattered academic robes. "
                        "It drifts above the floor, muttering about lost knowledge.",
            dialogue={
                "default": "The ghost turns its hollow eyes toward you: "
                           "'Have you come to learn, or to plunder?'",
                "zyl": "'Zyl was the greatest city of the Second Age. Its crystal "
                       "powered wonders beyond imagination. But pride... pride was "
                       "our undoing.'",
                "crystal": "'The Crystal of Zyl lies in the deepest chamber. "
                           "But it is shattered now—only shards remain. "
                           "Gather them, and perhaps... perhaps it can be restored.'",
                "trials": "'Three trials guard the inner sanctum: Wit, tested by "
                          "the Guardian. Courage, tested by the Depths. And Mercy, "
                          "tested by the choice you make at the end.'",
                "amulet": "'The silver amulet of the moon priestesses. It wards "
                          "against the restless dead. If you have it, I... I must go.' "
                          "The ghost shudders and fades slightly.",
            },
            hostile=False,
            health=1,
        ),
        "cave_troll": NPC(
            id="cave_troll",
            name="Cave Troll",
            description="A hulking troll crouches in the shadows, gnawing on bones. "
                        "It hasn't noticed you yet.",
            dialogue={
                "default": "The troll grunts: 'GO AWAY. MY CAVE. MY SHINIES.'",
                "food": "The troll's eyes widen at the bread. 'FOOD? REAL FOOD? "
                        "NOT BONES?' It snatches the bread and retreats deeper "
                        "into its corner, revealing the passage behind it.",
            },
            hostile=True,
            health=20,
            damage=4,
            drops=["golden_goblet"],
            defeat_flag="troll_defeated",
            block_direction=Direction.EAST,
            block_message="The troll snarls and blocks the eastern passage.",
        ),
        "shadow_wraith": NPC(
            id="shadow_wraith",
            name="Shadow Wraith",
            description="A being of pure darkness, its form constantly shifting. "
                        "Two pinpoints of cold white light serve as eyes.",
            dialogue={
                "default": "The wraith hisses: 'Ssservice or sssubmission. Choose.'",
            },
            hostile=True,
            health=15,
            damage=5,
            drops=["crystal_shard"],
            defeat_flag="wraith_defeated",
        ),
        "imprisoned_fairy": NPC(
            id="imprisoned_fairy",
            name="Imprisoned Fairy",
            description="A tiny winged figure trapped in an iron cage. "
                        "Its wings flicker with dying light.",
            dialogue={
                "default": "'Please... the iron drains my magic. If you free me, "
                           "I can help you.'",
                "freed": "'Thank you! Thank you! The deepest chamber holds "
                         "the last crystal shard. Take this—it will protect you.' "
                         "The fairy touches your hand, and warmth spreads through you.",
            },
            hostile=False,
            health=3,
        ),
    }

    rooms: dict[str, Room] = {
        "hilltop": Room(
            id="hilltop",
            name="Hilltop Overlooking the Ruins",
            description=(
                "You stand atop a windswept hill. Below, the crumbling spires "
                "of the ancient city of Zyl pierce the mist like broken fingers. "
                "A worn stone path leads down to the north. To the east, a rocky "
                "trail skirts the hillside."
            ),
            exits={Direction.NORTH: "city_gate", Direction.EAST: "rocky_trail"},
            items=["brass_lantern"],
        ),
        "rocky_trail": Room(
            id="rocky_trail",
            name="Rocky Trail",
            description=(
                "A narrow trail carved into the hillside. Loose stones make "
                "every step treacherous. You can see a dark cave mouth to the "
                "east, and the hilltop lies to the west."
            ),
            exits={Direction.WEST: "hilltop", Direction.EAST: "troll_cave"},
            items=["rope"],
        ),
        "city_gate": Room(
            id="city_gate",
            name="The Ruined City Gate",
            description=(
                "Massive stone pillars, cracked and overgrown with ivy, "
                "frame what was once a grand entrance. The gate itself has "
                "long since crumbled. Beyond lies the main plaza to the north. "
                "A collapsed tower to the west still has an accessible ground floor."
            ),
            exits={
                Direction.SOUTH: "hilltop",
                Direction.NORTH: "main_plaza",
                Direction.WEST: "collapsed_tower",
            },
            items=["dusty_tome"],
        ),
        "collapsed_tower": Room(
            id="collapsed_tower",
            name="Collapsed Tower – Ground Floor",
            description=(
                "The interior is a mess of fallen stone and rotting timber. "
                "A spiral staircase once led upward, but it's completely "
                "destroyed. Among the rubble, you notice a glint of metal. "
                "The city gate lies to the east."
            ),
            exits={Direction.EAST: "city_gate"},
            items=["rusty_key", "iron_shield"],
        ),
        "main_plaza": Room(
            id="main_plaza",
            name="Main Plaza of Zyl",
            description=(
                "A vast open space paved with cracked marble. A dry fountain "
                "dominates the center, its stone dolphins frozen mid-leap. "
                "The city gate is to the south. Corridors lead east to the "
                "library and west to the temple. To the north, a massive "
                "archway leads deeper into the ruins, but a Stone Guardian "
                "stands watch."
            ),
            exits={
                Direction.SOUTH: "city_gate",
                Direction.EAST: "library",
                Direction.WEST: "temple",
                Direction.NORTH: "guardian_hall",
            },
            npcs=["stone_guardian"],
        ),
        "library": Room(
            id="library",
            name="The Ruined Library",
            description=(
                "Towering shelves line the walls, most books long since "
                "turned to dust. A few intact tomes sit on a reading desk. "
                "A spectral figure hovers near the back stacks. "
                "The plaza is to the west."
            ),
            exits={Direction.WEST: "main_plaza"},
            npcs=["ghost_scholar"],
            items=["music_box"],
        ),
        "temple": Room(
            id="temple",
            name="The Moon Temple",
            description=(
                "An elegant domed chamber dedicated to the moon goddess. "
                "Shafts of pale light filter through holes in the ceiling, "
                "illuminating a stone altar. Silver filigree decorates the "
                "walls. The plaza lies to the east."
            ),
            exits={Direction.EAST: "main_plaza"},
            items=["silver_amulet"],
        ),
        "guardian_hall": Room(
            id="guardian_hall",
            name="Hall of the Guardian",
            description=(
                "A long corridor of polished stone. The walls are carved "
                "with scenes of Zyl's glory days. The plaza is behind you "
                "to the north. To the south, the inner sanctum awaits."
            ),
            exits={
                Direction.NORTH: "main_plaza",
                Direction.SOUTH: "inner_sanctum",
            },
            description_variants={
                "guardian_answered": (
                    "A long corridor of polished stone. The walls are carved "
                    "with scenes of Zyl's glory days. Where the Guardian once "
                    "stood, only scuff marks remain. The way south is clear."
                ),
            },
        ),
        "troll_cave": Room(
            id="troll_cave",
            name="The Troll's Cave",
            description=(
                "A damp, stinking cave littered with bones and refuse. "
                "A large troll guards the deeper passages to the east. "
                "The rocky trail is to the west."
            ),
            exits={
                Direction.WEST: "rocky_trail",
                Direction.EAST: "underground_river",
            },
            npcs=["cave_troll"],
            dark=True,
        ),
        "underground_river": Room(
            id="underground_river",
            name="Underground River",
            description=(
                "An underground river cuts through a cavern of glistening "
                "stalactites. The water is dark and swift. A narrow ledge "
                "runs along the northern bank. To the west is the troll's "
                "cave. To the east, the ledge leads to a crystal grotto."
            ),
            exits={
                Direction.WEST: "troll_cave",
                Direction.EAST: "crystal_grotto",
            },
            dark=True,
        ),
        "crystal_grotto": Room(
            id="crystal_grotto",
            name="Crystal Grotto",
            description=(
                "The walls of this natural chamber are studded with crystals "
                "that refract what little light exists into rainbow shards. "
                "In the center, a large crystal formation pulses with "
                "inner light. A shadow wraith guards it."
            ),
            exits={Direction.WEST: "underground_river"},
            npcs=["shadow_wraith"],
            items=["crystal_shard"],
            dark=True,
        ),
        "inner_sanctum": Room(
            id="inner_sanctum",
            name="Inner Sanctum of Zyl",
            description=(
                "A vast domed chamber, the true heart of the city. "
                "The ceiling is painted with a star map. In the center "
                "stands a pedestal where the Crystal of Zyl once sat. "
                "Now only an empty socket remains. An iron cage in the "
                "corner holds a small, flickering light."
            ),
            exits={
                Direction.NORTH: "guardian_hall",
                Direction.DOWN: "deep_vault",
            },
            npcs=["imprisoned_fairy"],
            locked_exits={Direction.DOWN: "skeleton_key"},
        ),
        "deep_vault": Room(
            id="deep_vault",
            name="The Deep Vault",
            description=(
                "The final chamber. Cold air presses against you like a "
                "physical weight. Ancient machinery lines the walls—pipes "
                "and gears and conduits that once channeled the crystal's "
                "power. A socket in the center of the floor awaits the "
                "crystal shards."
            ),
            exits={Direction.UP: "inner_sanctum"},
            items=["emerald_ring"],
            dark=True,
        ),
    }

    return rooms, items, npcs


# ── Game engine ──────────────────────────────────────────────────────

MAX_INVENTORY_WEIGHT = 20
POINTS_TAKE_ITEM = 5
POINTS_DEFEAT_ENEMY = 15
POINTS_SOLVE_PUZZLE = 25
POINTS_VICTORY = 100


class ZorkGame(GameInterface):
    """Zork-style interactive fiction game."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.items: dict[str, Item] = {}
        self.npcs: dict[str, NPC] = {}
        self.state_mgr: GameStateManager | None = None

        # Player state
        self.current_room: str = "hilltop"
        self.inventory: list[str] = []
        self.score: int = 0
        self.moves: int = 0
        self.flags: dict[str, bool] = {}
        self.health: int = 25
        self.max_health: int = 25
        self.equipped_weapon: str | None = None
        self.equipped_armor: str | None = None
        self.light_active: bool = False
        self.game_over: bool = False
        self.victory: bool = False
        self.visited_rooms: set[str] = set()
        self.collected_shards: int = 0

    @property
    def game_type(self) -> GameType:
        return GameType.INTERACTIVE_FICTION

    def _get_state(self) -> dict[str, Any]:
        """Snapshot all mutable state."""
        return {
            "current_room": self.current_room,
            "inventory": list(self.inventory),
            "score": self.score,
            "moves": self.moves,
            "flags": dict(self.flags),
            "health": self.health,
            "equipped_weapon": self.equipped_weapon,
            "equipped_armor": self.equipped_armor,
            "light_active": self.light_active,
            "game_over": self.game_over,
            "victory": self.victory,
            "visited_rooms": list(self.visited_rooms),
            "collected_shards": self.collected_shards,
            "room_items": {rid: list(r.items) for rid, r in self.rooms.items()},
            "room_npcs": {rid: list(r.npcs) for rid, r in self.rooms.items()},
            "npc_alive": {nid: n.alive for nid, n in self.npcs.items()},
            "npc_health": {nid: n.health for nid, n in self.npcs.items()},
            "item_hidden": {iid: i.hidden for iid, i in self.items.items()},
        }

    def _restore_state(self, state: dict[str, Any]) -> None:
        """Restore from snapshot."""
        self.current_room = state["current_room"]
        self.inventory = list(state["inventory"])
        self.score = state["score"]
        self.moves = state["moves"]
        self.flags = dict(state["flags"])
        self.health = state["health"]
        self.equipped_weapon = state["equipped_weapon"]
        self.equipped_armor = state["equipped_armor"]
        self.light_active = state["light_active"]
        self.game_over = state["game_over"]
        self.victory = state["victory"]
        self.visited_rooms = set(state["visited_rooms"])
        self.collected_shards = state["collected_shards"]
        for rid, item_list in state.get("room_items", {}).items():
            if rid in self.rooms:
                self.rooms[rid].items = list(item_list)
        for rid, npc_list in state.get("room_npcs", {}).items():
            if rid in self.rooms:
                self.rooms[rid].npcs = list(npc_list)
        for nid, alive in state.get("npc_alive", {}).items():
            if nid in self.npcs:
                self.npcs[nid].alive = alive
        for nid, hp in state.get("npc_health", {}).items():
            if nid in self.npcs:
                self.npcs[nid].health = hp
        for iid, hidden in state.get("item_hidden", {}).items():
            if iid in self.items:
                self.items[iid].hidden = hidden

    async def initialize(self, config: dict[str, Any] | None = None) -> str:
        """Set up the game world."""
        self.rooms, self.items, self.npcs = build_world()
        self.current_room = "hilltop"
        self.inventory = []
        self.score = 0
        self.moves = 0
        self.flags = {}
        self.health = 25
        self.max_health = 25
        self.equipped_weapon = None
        self.equipped_armor = None
        self.light_active = False
        self.game_over = False
        self.victory = False
        self.visited_rooms = {"hilltop"}
        self.collected_shards = 0

        return (
            "═══════════════════════════════════════════════════\n"
            "        THE RUINS OF ZYL\n"
            "   An Interactive Fiction Adventure\n"
            "═══════════════════════════════════════════════════\n"
            "\n"
            "The wind carries whispers of a forgotten age as you\n"
            "stand atop the hill overlooking the ruins of Zyl,\n"
            "once the greatest city of the Second Age. Legends\n"
            "speak of the Crystal of Zyl — a source of immense\n"
            "power, now shattered and scattered through the\n"
            "ruins. You have come to find its shards.\n"
            "\n"
            "Type 'help' for a list of commands.\n"
            "\n"
            + self._describe_room()
        )

    def _describe_room(self) -> str:
        """Full room description."""
        room = self.rooms[self.current_room]

        # Dark room check
        if room.dark and not self._has_light():
            return (
                f"\n── {room.name} ──\n"
                "It is pitch dark. You are likely to be eaten by a grue.\n"
                "(You need a light source to see anything here.)"
            )

        # Check for variant descriptions
        desc = room.description
        for flag_name, variant in room.description_variants.items():
            if self.flags.get(flag_name):
                desc = variant
                break

        lines = [f"\n── {room.name} ──", desc]

        # Visible items
        visible_items = [
            self.items[iid] for iid in room.items
            if iid in self.items and not self.items[iid].hidden
        ]
        if visible_items:
            lines.append("")
            for item in visible_items:
                lines.append(f"  You can see: {item.description}")

        # NPCs
        for npc_id in room.npcs:
            npc = self.npcs.get(npc_id)
            if npc and npc.alive:
                lines.append(f"\n  {npc.description}")

        # Exits
        exit_names = []
        for d, rid in room.exits.items():
            locked = d in room.locked_exits
            lock_note = " [locked]" if locked else ""
            exit_names.append(f"{d.value}{lock_note}")
        if exit_names:
            lines.append(f"\nExits: {', '.join(exit_names)}")

        return "\n".join(lines)

    def _has_light(self) -> bool:
        """Check if player has an active light source."""
        if self.light_active:
            return True
        for iid in self.inventory:
            item = self.items.get(iid)
            if item and item.is_light_source:
                return True
        return False

    def _find_item_by_name(self, name: str, search_inventory: bool = True,
                           search_room: bool = True) -> Item | None:
        """Fuzzy match item by name fragment."""
        name = name.lower().strip()
        candidates: list[Item] = []

        if search_inventory:
            for iid in self.inventory:
                if iid in self.items:
                    candidates.append(self.items[iid])

        if search_room:
            room = self.rooms[self.current_room]
            for iid in room.items:
                if iid in self.items and not self.items[iid].hidden:
                    candidates.append(self.items[iid])

        # Exact ID match
        for item in candidates:
            if item.id == name.replace(" ", "_"):
                return item

        # Name contains
        for item in candidates:
            if name in item.name.lower():
                return item

        # Partial match on any word
        for item in candidates:
            if any(name in word for word in item.name.lower().split()):
                return item

        return None

    def _find_npc_by_name(self, name: str) -> NPC | None:
        """Fuzzy match NPC in current room."""
        name = name.lower().strip()
        room = self.rooms[self.current_room]
        for npc_id in room.npcs:
            npc = self.npcs.get(npc_id)
            if not npc or not npc.alive:
                continue
            if name in npc.name.lower() or name in npc.id:
                return npc
        return None

    def _inventory_weight(self) -> int:
        return sum(self.items[iid].weight for iid in self.inventory if iid in self.items)

    async def process_input(self, user_input: str) -> str:
        """Main game loop — parse and dispatch."""
        if self.game_over:
            return "The game is over. Type /restart to play again, or /quit to exit."

        cmd = parse_command(user_input)
        if not cmd.verb:
            return "I beg your pardon?"

        self.moves += 1

        # Dispatch to verb handlers
        handlers: dict[str, Any] = {
            "go": self._handle_go,
            "look": self._handle_look,
            "examine": self._handle_examine,
            "take": self._handle_take,
            "drop": self._handle_drop,
            "inventory": self._handle_inventory,
            "use": self._handle_use,
            "open": self._handle_open,
            "attack": self._handle_attack,
            "talk": self._handle_talk,
            "give": self._handle_give,
            "eat": self._handle_eat,
            "drink": self._handle_drink,
            "light": self._handle_light,
            "wear": self._handle_wear,
            "remove": self._handle_remove_equip,
            "search": self._handle_search,
            "listen": self._handle_listen,
            "smell": self._handle_smell,
            "wait": self._handle_wait,
            "push": self._handle_push,
            "pull": self._handle_pull,
            "climb": self._handle_climb,
            "jump": self._handle_jump,
            "help": self._handle_help,
            "hint": self._handle_hint,
            "score": self._handle_score,
            "diagnose": self._handle_diagnose,
        }

        handler = handlers.get(cmd.verb)
        if handler:
            return await handler(cmd)

        # Direction as verb fallback
        if cmd.verb in DIRECTION_ALIASES:
            cmd.noun = cmd.verb
            cmd.verb = "go"
            return await self._handle_go(cmd)

        return f"I don't understand the verb '{cmd.verb}'."

    # ── Movement ─────────────────────────────────────────────────

    async def _handle_go(self, cmd: ParsedCommand) -> str:
        direction = DIRECTION_ALIASES.get(cmd.noun)
        if not direction:
            return "Go where? Specify a direction (north, south, east, west, up, down)."

        room = self.rooms[self.current_room]

        if direction not in room.exits:
            return "You can't go that way."

        # Check locked exits
        if direction in room.locked_exits:
            key_id = room.locked_exits[direction]
            if key_id not in self.inventory:
                return f"The way {direction.value} is locked. You need a key."
            else:
                del room.locked_exits[direction]
                return (
                    f"You use the {self.items[key_id].name} to unlock the way {direction.value}.\n"
                    + self._move_to(room.exits[direction])
                )

        # Check NPC blocking
        for npc_id in room.npcs:
            npc = self.npcs.get(npc_id)
            if (npc and npc.alive and npc.block_direction == direction
                    and not self.flags.get(npc.defeat_flag)):
                return npc.block_message

        return self._move_to(room.exits[direction])

    def _move_to(self, room_id: str) -> str:
        self.current_room = room_id
        first_visit = room_id not in self.visited_rooms
        self.visited_rooms.add(room_id)

        room = self.rooms[room_id]

        # Grue check for dark rooms without light
        if room.dark and not self._has_light():
            if random.random() < 0.3:
                self.health -= 5
                extra = ("\nSomething lurches out of the darkness and strikes you! "
                         f"(-5 HP, now {self.health} HP)")
                if self.health <= 0:
                    self.game_over = True
                    return extra + "\n\nYou have perished in the darkness. Game Over."
                return self._describe_room() + extra

        desc = self._describe_room()

        # Score for new room
        if first_visit:
            self.score += 2

        return desc

    # ── Observation ──────────────────────────────────────────────

    async def _handle_look(self, cmd: ParsedCommand) -> str:
        if cmd.noun:
            cmd.verb = "examine"
            return await self._handle_examine(cmd)
        return self._describe_room()

    async def _handle_examine(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return self._describe_room()

        # Try item (inventory first, then room)
        item = self._find_item_by_name(cmd.noun)
        if item:
            return item.examine_text or item.description

        # Try NPC
        npc = self._find_npc_by_name(cmd.noun)
        if npc:
            return npc.description

        # Try direction
        direction = DIRECTION_ALIASES.get(cmd.noun)
        if direction:
            room = self.rooms[self.current_room]
            if direction in room.exits:
                target = self.rooms[room.exits[direction]]
                return f"Looking {direction.value}, you see the way to {target.name}."

        return f"You see nothing special about '{cmd.noun}'."

    async def _handle_search(self, cmd: ParsedCommand) -> str:
        room = self.rooms[self.current_room]
        if room.dark and not self._has_light():
            return "You can't search in the dark."

        found = []
        for iid in room.items:
            item = self.items.get(iid)
            if item and item.hidden:
                item.hidden = False
                found.append(item.name)

        if found:
            self.score += POINTS_SOLVE_PUZZLE
            return "Searching carefully, you discover: " + ", ".join(found) + "!"
        return "You search thoroughly but find nothing hidden."

    async def _handle_listen(self, cmd: ParsedCommand) -> str:
        room = self.rooms[self.current_room]
        ambient: dict[str, str] = {
            "underground_river": "You hear the rushing of water echoing through the cavern.",
            "crystal_grotto": "A low, pulsing hum emanates from the crystal formations.",
            "temple": "A faint, ethereal chant seems to drift from the very walls.",
            "troll_cave": "Crunching and gnawing sounds echo from deeper in the cave.",
            "deep_vault": "The machinery around you clicks and whirs, as if awakening.",
        }
        return ambient.get(room.id, "You hear nothing unusual.")

    async def _handle_smell(self, cmd: ParsedCommand) -> str:
        room = self.rooms[self.current_room]
        scents: dict[str, str] = {
            "troll_cave": "The stench is overwhelming—rotting meat and unwashed troll.",
            "temple": "A delicate fragrance of incense lingers after centuries.",
            "library": "The musty scent of ancient parchment fills the air.",
            "crystal_grotto": "The air smells of ozone and cold stone.",
        }
        return scents.get(room.id, "The air carries the scent of dust and ages.")

    # ── Inventory ────────────────────────────────────────────────

    async def _handle_take(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Take what?"

        item = self._find_item_by_name(cmd.noun, search_inventory=False, search_room=True)
        if not item:
            return f"You don't see any '{cmd.noun}' here."

        if not item.takeable:
            return f"The {item.name} can't be picked up."

        if self._inventory_weight() + item.weight > MAX_INVENTORY_WEIGHT:
            return "You're carrying too much. Drop something first."

        room = self.rooms[self.current_room]
        if item.id in room.items:
            room.items.remove(item.id)
        self.inventory.append(item.id)
        self.score += POINTS_TAKE_ITEM
        return f"Taken: {item.name}."

    async def _handle_drop(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Drop what?"

        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You're not carrying any '{cmd.noun}'."

        self.inventory.remove(item.id)
        room = self.rooms[self.current_room]
        room.items.append(item.id)

        if item.id == self.equipped_weapon:
            self.equipped_weapon = None
        if item.id == self.equipped_armor:
            self.equipped_armor = None

        return f"Dropped: {item.name}."

    async def _handle_inventory(self, cmd: ParsedCommand) -> str:
        if not self.inventory:
            return "You are empty-handed."

        lines = ["You are carrying:"]
        for iid in self.inventory:
            item = self.items.get(iid)
            if item:
                extras = []
                if iid == self.equipped_weapon:
                    extras.append("wielded")
                if iid == self.equipped_armor:
                    extras.append("worn")
                note = f" ({', '.join(extras)})" if extras else ""
                lines.append(f"  - {item.name}{note}")

        weight = self._inventory_weight()
        lines.append(f"\nTotal weight: {weight}/{MAX_INVENTORY_WEIGHT}")
        return "\n".join(lines)

    # ── Item usage ───────────────────────────────────────────────

    async def _handle_use(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Use what?"

        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."

        # Special use items
        if item.special_use == "ward_ghost" and "ghost_scholar" in self.rooms[self.current_room].npcs:
            self.flags["ghost_warded"] = True
            self.score += POINTS_SOLVE_PUZZLE
            return (
                "You hold up the silver amulet. The ghost recoils, then bows.\n"
                "'You bear the moon's blessing. I will share freely.'\n"
                "The ghost seems more willing to talk now."
            )

        if item.special_use == "calm_guardian" and "stone_guardian" in self.rooms[self.current_room].npcs:
            if not self.flags.get("guardian_answered"):
                self.flags["guardian_answered"] = True
                self.score += POINTS_SOLVE_PUZZLE
                return (
                    "You wind the music box. A gentle melody fills the hall.\n"
                    "The Stone Guardian freezes, then slowly steps aside.\n"
                    "'The old songs... I remember now. You may pass.'"
                )

        if item.is_light_source:
            return await self._handle_light(ParsedCommand(verb="light", noun=cmd.noun, raw=cmd.raw))

        if item.is_weapon:
            return await self._handle_wear(ParsedCommand(verb="wear", noun=cmd.noun, raw=cmd.raw))

        # Use on target
        if cmd.indirect_object:
            target_npc = self._find_npc_by_name(cmd.indirect_object)
            if target_npc:
                return f"You can't use the {item.name} on {target_npc.name} that way."

        return f"You're not sure how to use the {item.name} here."

    async def _handle_open(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Open what?"

        if cmd.noun in ("cage", "iron cage"):
            room = self.rooms[self.current_room]
            if "imprisoned_fairy" in room.npcs:
                npc = self.npcs["imprisoned_fairy"]
                if npc.alive and not self.flags.get("fairy_freed"):
                    # Need skeleton key or brute force
                    if "skeleton_key" in self.inventory:
                        self.flags["fairy_freed"] = True
                        self.score += POINTS_SOLVE_PUZZLE
                        return npc.dialogue["freed"]
                    else:
                        return "The cage is locked with a strange bone lock. You need the right key."

        return f"You can't open '{cmd.noun}'."

    async def _handle_give(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Give what?"

        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."

        target_name = cmd.indirect_object or ""
        npc = self._find_npc_by_name(target_name) if target_name else None

        if not npc:
            # Try to find NPC in room
            room = self.rooms[self.current_room]
            for npc_id in room.npcs:
                n = self.npcs.get(npc_id)
                if n and n.alive:
                    npc = n
                    break

        if not npc:
            return "Give it to whom?"

        # Special: give bread to troll
        if item.id == "loaf_of_bread" and npc.id == "cave_troll":
            self.inventory.remove(item.id)
            self.flags["troll_defeated"] = True
            npc.hostile = False
            self.score += POINTS_SOLVE_PUZZLE
            return npc.dialogue.get("food", "The troll takes it.")

        return f"{npc.name} doesn't seem interested in the {item.name}."

    async def _handle_eat(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Eat what?"
        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."
        if item.id == "loaf_of_bread":
            self.inventory.remove(item.id)
            heal = min(5, self.max_health - self.health)
            self.health += heal
            return f"You eat the bread. Delicious and restorative! (+{heal} HP, now {self.health} HP)"
        return f"You can't eat the {item.name}."

    async def _handle_drink(self, cmd: ParsedCommand) -> str:
        return "You have nothing to drink."

    async def _handle_light(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Light what?"
        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."
        if item.is_light_source:
            self.light_active = True
            return f"The {item.name} flares to life, casting warm light around you."
        return f"You can't light the {item.name}."

    async def _handle_wear(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Equip what?"
        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."
        if item.is_weapon:
            self.equipped_weapon = item.id
            return f"You wield the {item.name}."
        if item.id == "iron_shield":
            self.equipped_armor = item.id
            return f"You strap on the {item.name}."
        return f"You can't equip the {item.name}."

    async def _handle_remove_equip(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Remove what?"
        item = self._find_item_by_name(cmd.noun, search_inventory=True, search_room=False)
        if not item:
            return f"You don't have any '{cmd.noun}'."
        if item.id == self.equipped_weapon:
            self.equipped_weapon = None
            return f"You put away the {item.name}."
        if item.id == self.equipped_armor:
            self.equipped_armor = None
            return f"You remove the {item.name}."
        return f"You're not wearing or wielding the {item.name}."

    # ── Combat ───────────────────────────────────────────────────

    async def _handle_attack(self, cmd: ParsedCommand) -> str:
        if not cmd.noun:
            return "Attack what?"

        npc = self._find_npc_by_name(cmd.noun)
        if not npc:
            return f"There's no '{cmd.noun}' here to attack."

        if not npc.hostile and npc.id != "stone_guardian":
            return f"The {npc.name} isn't threatening you. Are you sure? (attack again to confirm)"

        # Player attack
        base_damage = 1
        if self.equipped_weapon:
            weapon = self.items.get(self.equipped_weapon)
            if weapon:
                base_damage = weapon.damage

        # Roll for hit (simplified d20)
        roll = random.randint(1, 20)
        lines = []

        if roll >= 5:
            damage = base_damage + random.randint(0, 2)
            npc.health -= damage
            weapon_name = self.items[self.equipped_weapon].name if self.equipped_weapon else "bare fists"
            lines.append(f"You strike the {npc.name} with your {weapon_name}! ({damage} damage)")

            if npc.health <= 0:
                npc.alive = False
                self.flags[npc.defeat_flag] = True
                self.score += POINTS_DEFEAT_ENEMY
                lines.append(f"The {npc.name} collapses!")

                # Drop loot
                room = self.rooms[self.current_room]
                for drop_id in npc.drops:
                    if drop_id in self.items:
                        room.items.append(drop_id)
                        lines.append(f"  It drops: {self.items[drop_id].name}")

                if npc.id == "shadow_wraith":
                    self.collected_shards += 1

                return "\n".join(lines)
        else:
            lines.append(f"You swing at the {npc.name} and miss!")

        # NPC counter-attack
        if npc.alive and npc.hostile:
            npc_roll = random.randint(1, 20)
            if npc_roll >= 8:
                defense = 0
                if self.equipped_armor == "iron_shield":
                    defense = 2
                npc_damage = max(1, npc.damage - defense + random.randint(-1, 1))
                self.health -= npc_damage
                lines.append(f"The {npc.name} strikes back! ({npc_damage} damage)")
                lines.append(f"Your health: {self.health}/{self.max_health}")

                if self.health <= 0:
                    self.game_over = True
                    lines.append(f"\nThe {npc.name} has defeated you. Game Over.")
            else:
                lines.append(f"The {npc.name} attacks but misses!")

        return "\n".join(lines)

    # ── Dialogue ─────────────────────────────────────────────────

    async def _handle_talk(self, cmd: ParsedCommand) -> str:
        target_name = cmd.noun or cmd.indirect_object
        if not target_name:
            # Talk to first NPC in room
            room = self.rooms[self.current_room]
            for npc_id in room.npcs:
                npc = self.npcs.get(npc_id)
                if npc and npc.alive:
                    return npc.dialogue.get("default", f"The {npc.name} has nothing to say.")
            return "There's no one here to talk to."

        npc = self._find_npc_by_name(target_name)
        if not npc:
            return f"You don't see '{target_name}' here."

        # Check topic from indirect object
        topic = cmd.indirect_object.lower() if cmd.indirect_object else ""

        # Special: answer guardian's riddle
        if npc.id == "stone_guardian":
            if topic in ("riddle", "trial", "wit"):
                return npc.dialogue.get("riddle", npc.dialogue["default"])
            if topic in ("mountain", "a mountain"):
                self.flags["guardian_answered"] = True
                self.score += POINTS_SOLVE_PUZZLE
                return npc.dialogue["mountain"]
            if topic and topic not in ("default",):
                # Check if they're trying to answer
                if "mountain" in topic:
                    self.flags["guardian_answered"] = True
                    self.score += POINTS_SOLVE_PUZZLE
                    return npc.dialogue["mountain"]
                return npc.dialogue.get("wrong", npc.dialogue["default"])

        if topic:
            response = npc.dialogue.get(topic, None)
            if response:
                return response

        return npc.dialogue.get("default", f"The {npc.name} has nothing to say.")

    # ── Misc actions ─────────────────────────────────────────────

    async def _handle_wait(self, cmd: ParsedCommand) -> str:
        messages = [
            "Time passes...",
            "You wait patiently. Nothing happens.",
            "A cold breeze stirs the dust.",
            "You hear distant echoes from deep within the ruins.",
            "The shadows seem to shift slightly.",
        ]
        return random.choice(messages)

    async def _handle_push(self, cmd: ParsedCommand) -> str:
        return f"Pushing the {cmd.noun or 'air'} accomplishes nothing."

    async def _handle_pull(self, cmd: ParsedCommand) -> str:
        return f"Pulling the {cmd.noun or 'air'} accomplishes nothing."

    async def _handle_climb(self, cmd: ParsedCommand) -> str:
        if self.current_room == "rocky_trail" and "rope" in self.inventory:
            return "You could climb down the cliff face, but there's nothing below but rocks."
        return "There's nothing here to climb."

    async def _handle_jump(self, cmd: ParsedCommand) -> str:
        return "Jumping here seems inadvisable."

    # ── Victory condition ────────────────────────────────────────

    async def _handle_use_crystal(self) -> str:
        """Called when player tries to use crystal shards in deep vault."""
        if self.current_room != "deep_vault":
            return "This doesn't seem like the right place for that."

        if self.collected_shards < 1 or "crystal_shard" not in self.inventory:
            return "You don't have the crystal shards."

        self.score += POINTS_VICTORY
        self.victory = True
        self.game_over = True

        mercy_note = ""
        if self.flags.get("fairy_freed"):
            mercy_note = (
                "\nThe fairy's blessing guides the crystal's reconstruction. "
                "The light is warm, benevolent."
            )
        elif self.flags.get("troll_defeated") and not self.flags.get("troll_killed"):
            mercy_note = (
                "\nYour mercy toward the troll resonates through the crystal. "
                "The light carries compassion."
            )

        return (
            "You place the crystal shards into the socket.\n"
            "\n"
            "Light erupts. The shards lift, spinning, drawing together.\n"
            "The machinery around you roars to life—gears turning, pipes\n"
            "humming with power not felt in millennia.\n"
            + mercy_note +
            "\n"
            "The Crystal of Zyl is restored.\n"
            "\n"
            "Power floods through the ruins. You feel the very stones\n"
            "strengthening around you. Somewhere above, the spires of Zyl\n"
            "begin to glow with their ancient light.\n"
            "\n"
            "══════════════════════════════════════════════\n"
            "   VICTORY — THE CRYSTAL OF ZYL IS RESTORED\n"
            f"   Final Score: {self.score} points in {self.moves} moves\n"
            "══════════════════════════════════════════════\n"
            "\n"
            "Thank you for playing The Ruins of Zyl."
        )

    # ── Info commands ────────────────────────────────────────────

    async def _handle_help(self, cmd: ParsedCommand) -> str:
        return (
            "═══ Commands ═══\n"
            "Movement: north/south/east/west/up/down (or n/s/e/w/u/d)\n"
            "Look:     look, examine <thing>, search\n"
            "Items:    take <item>, drop <item>, inventory (i)\n"
            "Actions:  use <item>, open <thing>, light <item>\n"
            "Equip:    wear <item>, remove <item>\n"
            "Social:   talk [to <npc>] [about <topic>], give <item> to <npc>\n"
            "Combat:   attack <target>\n"
            "Senses:   listen, smell\n"
            "Other:    wait, score, diagnose, hint\n"
            "System:   /save, /load, /undo, /redo, /status, /quit"
        )

    async def _handle_hint(self, cmd: ParsedCommand) -> str:
        hints = []
        if not self.flags.get("guardian_answered") and "main_plaza" in self.visited_rooms:
            hints.append("The Stone Guardian demands a riddle answered. Perhaps the library's ghost knows about the trials.")
        if "troll_cave" in self.visited_rooms and not self.flags.get("troll_defeated"):
            hints.append("The troll is hungry. Perhaps offering food would be kinder than fighting.")
        if "library" in self.visited_rooms and not self.flags.get("ghost_warded"):
            hints.append("The ghost scholar might be more forthcoming if calmed with the right artifact.")
        if self.flags.get("fairy_freed") is None and "inner_sanctum" in self.visited_rooms:
            hints.append("The fairy in the cage needs a key. Have you searched everywhere thoroughly?")
        if not hints:
            hints.append("Explore the ruins. Talk to everyone. Examine everything. The crystal shards are your goal.")
        return "── Hint ──\n" + "\n".join(f"• {h}" for h in hints)

    async def _handle_score(self, cmd: ParsedCommand) -> str:
        rank = "Novice"
        if self.score >= 200:
            rank = "Restorer of Zyl"
        elif self.score >= 150:
            rank = "Crystal Seeker"
        elif self.score >= 100:
            rank = "Ruin Delver"
        elif self.score >= 50:
            rank = "Explorer"
        elif self.score >= 20:
            rank = "Adventurer"

        return (
            f"Score: {self.score} points in {self.moves} moves.\n"
            f"Rank: {rank}\n"
            f"Rooms explored: {len(self.visited_rooms)}/{len(self.rooms)}\n"
            f"Crystal shards: {self.collected_shards}"
        )

    async def _handle_diagnose(self, cmd: ParsedCommand) -> str:
        status = "healthy" if self.health > 20 else "wounded" if self.health > 10 else "critical"
        lines = [
            f"Health: {self.health}/{self.max_health} ({status})",
            f"Weapon: {self.items[self.equipped_weapon].name if self.equipped_weapon else 'none'}",
            f"Armor: {self.items[self.equipped_armor].name if self.equipped_armor else 'none'}",
            f"Light: {'active' if self.light_active else 'inactive'}",
            f"Carrying: {self._inventory_weight()}/{MAX_INVENTORY_WEIGHT} weight",
        ]
        return "\n".join(lines)

    # ── Interface methods ────────────────────────────────────────

    async def get_help(self) -> str:
        return await self._handle_help(ParsedCommand(verb="help"))

    async def validate_input(self, user_input: str) -> bool:
        return bool(user_input.strip())

    async def generate_summary(self) -> str:
        if self.victory:
            return (
                f"Victory! You restored the Crystal of Zyl.\n"
                f"Score: {self.score} points in {self.moves} moves.\n"
                f"Rooms explored: {len(self.visited_rooms)}/{len(self.rooms)}"
            )
        if self.game_over:
            return (
                f"Game Over. You fell in the ruins of Zyl.\n"
                f"Score: {self.score} points in {self.moves} moves."
            )
        return (
            f"In progress — {self.rooms[self.current_room].name}\n"
            f"Score: {self.score}, Health: {self.health}/{self.max_health}"
        )
