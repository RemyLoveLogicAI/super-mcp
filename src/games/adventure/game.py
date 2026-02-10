"""Create-Your-Own-Adventure Engine — branching narrative with full replay.

Pre-mapped story graphs with all possible branches, rollback points,
and deterministic replay. Generates artifacts at completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.games.engine.runner import GameInterface, GameOutput
from src.games.engine.state import GameAction, GamePhase, GameState


@dataclass
class StoryNode:
    id: str
    text: str
    choices: list[tuple[str, str]] = field(default_factory=list)  # (choice_text, target_node_id)
    ending: bool = False
    ending_type: str = ""  # "victory", "defeat", "neutral"
    tags: list[str] = field(default_factory=list)


# === STORY: The Lost Temple (Adventure) ===
ADVENTURE_STORY: dict[str, StoryNode] = {
    "start": StoryNode(
        id="start",
        text=(
            "You stand at the entrance to a crumbling temple deep in the jungle. "
            "Vines cling to ancient stone pillars, and the air hums with forgotten power. "
            "Your map shows three possible approaches."
        ),
        choices=[
            ("Enter through the main gate", "main_gate"),
            ("Climb through the collapsed wall on the east side", "east_wall"),
            ("Search for a hidden entrance underground", "underground"),
        ],
    ),
    "main_gate": StoryNode(
        id="main_gate",
        text=(
            "The main gate groans as you push it open. Inside, a grand hall stretches before you. "
            "Faded murals depict a civilization of incredible technology. "
            "Ahead, two corridors branch off."
        ),
        choices=[
            ("Take the left corridor (marked with a sun symbol)", "sun_corridor"),
            ("Take the right corridor (marked with a moon symbol)", "moon_corridor"),
            ("Examine the murals more closely", "examine_murals"),
        ],
    ),
    "east_wall": StoryNode(
        id="east_wall",
        text=(
            "You scramble through the gap in the crumbling wall. Inside is a storage room "
            "filled with clay jars and ancient tools. A doorway leads deeper inside. "
            "One jar glows faintly."
        ),
        choices=[
            ("Open the glowing jar", "glowing_jar"),
            ("Proceed through the doorway", "storage_passage"),
            ("Search the tools for anything useful", "search_tools"),
        ],
    ),
    "underground": StoryNode(
        id="underground",
        text=(
            "You discover a narrow tunnel beneath a fallen tree. It descends steeply "
            "into darkness. Water drips somewhere ahead. After crawling for minutes, "
            "you emerge in a vast underground cavern beneath the temple."
        ),
        choices=[
            ("Follow the sound of water", "water_source"),
            ("Head toward a faint light in the distance", "faint_light"),
        ],
    ),
    "sun_corridor": StoryNode(
        id="sun_corridor",
        text=(
            "Golden light fills the sun corridor. You walk through beams of light "
            "projected by crystalline lenses. At the end: a chamber with a golden idol "
            "on a pedestal. The floor looks suspicious."
        ),
        choices=[
            ("Carefully approach and take the idol", "take_idol"),
            ("Look for traps before approaching", "check_traps"),
            ("Leave the idol and explore elsewhere", "main_gate"),
        ],
    ),
    "moon_corridor": StoryNode(
        id="moon_corridor",
        text=(
            "Silver moonlight — impossibly, deep inside the temple — illuminates "
            "a reflecting pool. In its depths, you see visions of the past: "
            "the temple builders and their powerful artifact."
        ),
        choices=[
            ("Reach into the pool", "reach_pool"),
            ("Meditate by the pool", "meditate"),
            ("Move past to the next chamber", "inner_sanctum"),
        ],
    ),
    "examine_murals": StoryNode(
        id="examine_murals",
        text=(
            "The murals reveal a hidden mechanism. By pressing certain symbols "
            "in sequence, a section of wall slides open, revealing a secret passage."
        ),
        choices=[
            ("Enter the secret passage", "secret_passage"),
            ("Return to the corridors", "main_gate"),
        ],
    ),
    "glowing_jar": StoryNode(
        id="glowing_jar",
        text=(
            "Inside the jar: a luminous crystal that fills the room with warm light. "
            "It hums when you hold it — a key of some kind. Ancient text on the jar "
            "reads: 'The heart opens the way.'"
        ),
        choices=[
            ("Take the crystal and proceed deeper", "storage_passage"),
            ("Leave the crystal and proceed carefully", "storage_passage"),
        ],
        tags=["crystal_obtained"],
    ),
    "storage_passage": StoryNode(
        id="storage_passage",
        text=(
            "The passage opens into a junction. Left leads down to the underground "
            "caverns. Right leads to the inner temple chambers."
        ),
        choices=[
            ("Go left to the caverns", "water_source"),
            ("Go right to the inner chambers", "inner_sanctum"),
        ],
    ),
    "search_tools": StoryNode(
        id="search_tools",
        text=(
            "Among the ancient tools, you find a bronze key etched with temple symbols "
            "and a leather satchel containing dried herbs."
        ),
        choices=[
            ("Take the key and herbs, then proceed", "storage_passage"),
        ],
        tags=["bronze_key"],
    ),
    "water_source": StoryNode(
        id="water_source",
        text=(
            "An underground river flows through the cavern. On the far bank, "
            "you see an ancient mechanism — a water-powered elevator "
            "that could take you to the temple's highest point."
        ),
        choices=[
            ("Swim across and activate the elevator", "elevator"),
            ("Follow the river downstream", "river_exit"),
        ],
    ),
    "faint_light": StoryNode(
        id="faint_light",
        text=(
            "The light comes from bioluminescent fungi growing on a massive "
            "stone door. The door bears an inscription: 'Only the worthy pass.' "
            "A handprint depression glows on the surface."
        ),
        choices=[
            ("Place your hand on the depression", "worthy_test"),
            ("Search for another way around", "water_source"),
        ],
    ),
    "take_idol": StoryNode(
        id="take_idol",
        text=(
            "As your fingers close around the golden idol, the floor gives way! "
            "You plummet into a pit. Fortunately, sand breaks your fall. "
            "But you're now trapped below with the idol."
        ),
        choices=[
            ("Search for an exit in the pit", "pit_escape"),
            ("Use the idol to pry open a crack in the wall", "idol_lever"),
        ],
    ),
    "check_traps": StoryNode(
        id="check_traps",
        text=(
            "Good instincts! You spot pressure plates across the floor. "
            "By stepping only on the stones marked with sun symbols, "
            "you reach the pedestal safely and claim the golden idol."
        ),
        choices=[
            ("Take the idol and head to the inner sanctum", "inner_sanctum"),
        ],
        tags=["idol_safe"],
    ),
    "reach_pool": StoryNode(
        id="reach_pool",
        text=(
            "Your hand breaks the water's surface and the visions intensify. "
            "You see the artifact: a crown of starlight. You know where it rests — "
            "the highest chamber of the temple."
        ),
        choices=[
            ("Rush to the inner sanctum", "inner_sanctum"),
        ],
        tags=["vision_seen"],
    ),
    "meditate": StoryNode(
        id="meditate",
        text=(
            "In meditation, the temple speaks to you. It was built to protect "
            "the Crown of Ages from those who would misuse its power. "
            "A guardian tests all seekers."
        ),
        choices=[
            ("Accept the test", "guardian_test"),
            ("Decline and continue exploring", "inner_sanctum"),
        ],
    ),
    "secret_passage": StoryNode(
        id="secret_passage",
        text=(
            "The passage leads to the temple treasury! Gold coins, jeweled daggers, "
            "and scrolls fill the room. But at the back — a sealed vault door "
            "with three keyholes."
        ),
        choices=[
            ("Try to pick the locks", "pick_locks"),
            ("Note the location and continue", "inner_sanctum"),
        ],
    ),
    "inner_sanctum": StoryNode(
        id="inner_sanctum",
        text=(
            "You enter the inner sanctum. A vast domed chamber stretches above, "
            "starlight filtering through crystal skylights. At the center, "
            "on a floating dais, rests the Crown of Ages. A stone guardian "
            "blocks the path."
        ),
        choices=[
            ("Challenge the guardian", "guardian_fight"),
            ("Try to reason with the guardian", "guardian_reason"),
            ("Look for a way to sneak past", "guardian_sneak"),
        ],
    ),
    "guardian_fight": StoryNode(
        id="guardian_fight",
        text=(
            "The stone guardian is formidable but you fight with courage. "
            "After a grueling battle, you land a decisive blow and the guardian "
            "crumbles. The path to the Crown is clear."
        ),
        choices=[
            ("Claim the Crown of Ages", "claim_crown"),
        ],
    ),
    "guardian_reason": StoryNode(
        id="guardian_reason",
        text=(
            "You speak of your purpose — not greed, but to protect the artifact "
            "from those who would misuse it. The guardian considers your words, "
            "then steps aside. 'You have wisdom, seeker.'"
        ),
        choices=[
            ("Claim the Crown of Ages", "claim_crown"),
        ],
        tags=["peaceful_resolution"],
    ),
    "guardian_sneak": StoryNode(
        id="guardian_sneak",
        text=(
            "You find a narrow ledge along the wall. With careful footing, "
            "you edge past the guardian's line of sight and reach the dais."
        ),
        choices=[
            ("Claim the Crown of Ages", "claim_crown"),
        ],
    ),
    "guardian_test": StoryNode(
        id="guardian_test",
        text=(
            "The pool presents three visions: power, knowledge, and compassion. "
            "Which do you choose?"
        ),
        choices=[
            ("Choose power", "test_power"),
            ("Choose knowledge", "test_knowledge"),
            ("Choose compassion", "test_compassion"),
        ],
    ),
    "test_power": StoryNode(
        id="test_power",
        text="The temple trembles. 'Power alone is not enough.' You are expelled from the vision.",
        choices=[("Continue to the inner sanctum", "inner_sanctum")],
    ),
    "test_knowledge": StoryNode(
        id="test_knowledge",
        text="The temple nods. You gain insight into the guardian's weakness. Proceed with advantage.",
        choices=[("Continue to the inner sanctum", "inner_sanctum")],
        tags=["guardian_weakness"],
    ),
    "test_compassion": StoryNode(
        id="test_compassion",
        text="The temple smiles. 'The truest strength.' A hidden path opens directly to the Crown.",
        choices=[("Take the hidden path", "claim_crown")],
        tags=["compassion_chosen"],
    ),
    "pit_escape": StoryNode(
        id="pit_escape",
        text="You find a tunnel in the pit wall leading to the underground river.",
        choices=[("Follow the tunnel", "water_source")],
    ),
    "idol_lever": StoryNode(
        id="idol_lever",
        text="The idol's base fits into a groove. A door grinds open, leading to the inner sanctum!",
        choices=[("Enter the inner sanctum", "inner_sanctum")],
    ),
    "elevator": StoryNode(
        id="elevator",
        text="The water elevator rises slowly, carrying you to the temple's apex. The Crown chamber is just ahead.",
        choices=[("Enter the Crown chamber", "inner_sanctum")],
    ),
    "river_exit": StoryNode(
        id="river_exit",
        text=(
            "The river carries you to the jungle outside. You're safe, but empty-handed. "
            "The temple's secrets remain hidden. Perhaps you'll return someday."
        ),
        ending=True,
        ending_type="neutral",
    ),
    "pick_locks": StoryNode(
        id="pick_locks",
        text=(
            "The locks are ancient but yield to patience. Inside the vault: "
            "a mountain of gold and the legendary Blade of the Sun King. "
            "You claim the treasure but trigger an alarm. The temple begins to collapse!"
        ),
        choices=[
            ("Grab what you can and run!", "treasure_escape"),
        ],
    ),
    "treasure_escape": StoryNode(
        id="treasure_escape",
        text=(
            "You dash through crumbling corridors, treasure in hand. "
            "Stones fall around you. Just as the entrance collapses, "
            "you dive through and tumble into the jungle. Rich, but the Crown remains within."
        ),
        ending=True,
        ending_type="neutral",
        tags=["treasure_obtained"],
    ),
    "worthy_test": StoryNode(
        id="worthy_test",
        text="The door reads your intent. Light floods through you. The door opens to reveal the inner sanctum.",
        choices=[("Enter the inner sanctum", "inner_sanctum")],
        tags=["worthy_proven"],
    ),
    "claim_crown": StoryNode(
        id="claim_crown",
        text=(
            "Your hands close around the Crown of Ages. Light erupts from it, "
            "filling the chamber, the temple, the jungle. For a moment, "
            "you understand everything — the temple, its builders, the world. "
            "Then, peace. You are the new guardian of the Crown.\n\n"
            "🏆 VICTORY — The Crown of Ages is yours."
        ),
        ending=True,
        ending_type="victory",
        tags=["crown_claimed"],
    ),
}

# === STORY: The Haunted Manor (Horror) ===
HORROR_STORY: dict[str, StoryNode] = {
    "start": StoryNode(
        id="start",
        text=(
            "Rain lashes the old Blackwood Manor as you approach. Your car broke down "
            "a mile back and this is the only shelter for miles. The front door is ajar. "
            "Lightning reveals a figure in an upper window — or was it your imagination?"
        ),
        choices=[
            ("Enter through the front door", "foyer"),
            ("Go around to the back entrance", "back_entrance"),
            ("Stay outside under the porch", "stay_outside"),
        ],
    ),
    "foyer": StoryNode(
        id="foyer",
        text=(
            "The foyer is dusty but intact. A grand staircase ascends into darkness. "
            "To the left, a sitting room with a dead fireplace. To the right, a dining hall. "
            "The front door slams shut behind you."
        ),
        choices=[
            ("Try the front door", "door_locked"),
            ("Go upstairs", "upstairs_hall"),
            ("Enter the sitting room", "sitting_room"),
            ("Enter the dining hall", "dining_hall"),
        ],
    ),
    "back_entrance": StoryNode(
        id="back_entrance",
        text=(
            "The kitchen entrance is unlocked. Inside, dishes sit as if dinner were just served — "
            "but the food is decades old. A newspaper on the counter is dated 1923."
        ),
        choices=[
            ("Read the newspaper", "newspaper"),
            ("Explore the kitchen", "kitchen_search"),
            ("Go through to the main house", "foyer"),
        ],
    ),
    "stay_outside": StoryNode(
        id="stay_outside",
        text=(
            "You huddle under the porch as the storm intensifies. "
            "Then you hear it: scratching from inside the walls. "
            "Something whispers your name. You didn't tell anyone you were coming here."
        ),
        choices=[
            ("Steel your nerves and enter", "foyer"),
            ("Run back to the road", "road_escape"),
        ],
    ),
    "door_locked": StoryNode(
        id="door_locked",
        text="The door won't budge. The lock has engaged from the outside. You're trapped.",
        choices=[
            ("Go upstairs", "upstairs_hall"),
            ("Enter the sitting room", "sitting_room"),
        ],
    ),
    "sitting_room": StoryNode(
        id="sitting_room",
        text=(
            "The sitting room has a cold fireplace, a bookshelf, and a portrait of the Blackwood family. "
            "As you look at the portrait, you notice the eyes seem to follow you. "
            "One book on the shelf is pulled out slightly."
        ),
        choices=[
            ("Pull the book", "secret_room"),
            ("Examine the portrait", "portrait_clue"),
            ("Return to the foyer", "foyer"),
        ],
    ),
    "dining_hall": StoryNode(
        id="dining_hall",
        text=(
            "A long table set for twelve. Candles flicker despite no draft. "
            "At the head of the table, a journal lies open."
        ),
        choices=[
            ("Read the journal", "journal"),
            ("Blow out the candles", "candles_out"),
            ("Return to the foyer", "foyer"),
        ],
    ),
    "upstairs_hall": StoryNode(
        id="upstairs_hall",
        text=(
            "The upstairs hallway stretches in both directions. Three doors line the hall. "
            "From behind the middle door, you hear... music. An old music box."
        ),
        choices=[
            ("Open the left door", "bedroom"),
            ("Open the middle door (music)", "music_room"),
            ("Open the right door", "study"),
        ],
    ),
    "newspaper": StoryNode(
        id="newspaper",
        text=(
            "The headline reads: 'BLACKWOOD FAMILY VANISHES — No bodies found, "
            "doors locked from inside. Police baffled.' The date: October 31, 1923."
        ),
        choices=[("Continue into the house", "foyer")],
        tags=["newspaper_read"],
    ),
    "kitchen_search": StoryNode(
        id="kitchen_search",
        text="You find a heavy iron key in a drawer. It's labeled 'CELLAR'.",
        choices=[("Take the key and continue", "foyer")],
        tags=["cellar_key"],
    ),
    "secret_room": StoryNode(
        id="secret_room",
        text=(
            "The bookshelf swings open! Behind it: a narrow room with ritual markings on the floor, "
            "candles arranged in a circle, and a leather-bound grimoire."
        ),
        choices=[
            ("Read the grimoire", "grimoire"),
            ("Leave quickly", "sitting_room"),
        ],
    ),
    "portrait_clue": StoryNode(
        id="portrait_clue",
        text=(
            "Behind the portrait, scratched into the wall: 'THE CELLAR HOLDS THE TRUTH. "
            "DO NOT TRUST THE MUSIC.' Signed with a bloody thumbprint."
        ),
        choices=[("Return to the foyer", "foyer")],
        tags=["portrait_warning"],
    ),
    "journal": StoryNode(
        id="journal",
        text=(
            "The journal belongs to Lord Blackwood. The final entry: 'It came through the mirror. "
            "We tried the banishing ritual but needed three — we are only two. "
            "If you read this, find the grimoire. Find the third.'"
        ),
        choices=[("Take the journal and continue", "foyer")],
        tags=["journal_read"],
    ),
    "candles_out": StoryNode(
        id="candles_out",
        text=(
            "As the last candle goes out, something cold grabs your ankle. "
            "You scream and pull free, stumbling back to the foyer. "
            "Scratch marks appear on your leg."
        ),
        choices=[("Flee to the foyer", "foyer")],
        tags=["entity_contact"],
    ),
    "bedroom": StoryNode(
        id="bedroom",
        text=(
            "A child's bedroom. Toys scattered. The window overlooks the storm. "
            "On the bed, a doll sits upright, staring at you. Its mouth is sewn shut."
        ),
        choices=[
            ("Take the doll", "take_doll"),
            ("Leave the room", "upstairs_hall"),
        ],
    ),
    "music_room": StoryNode(
        id="music_room",
        text=(
            "A music box plays a haunting waltz. In the center of the room: a tall mirror, "
            "ornate and dark. Your reflection... doesn't match your movements. "
            "It smiles at you."
        ),
        choices=[
            ("Touch the mirror", "mirror_trap"),
            ("Smash the mirror", "smash_mirror"),
            ("Back away slowly", "upstairs_hall"),
        ],
    ),
    "study": StoryNode(
        id="study",
        text=(
            "Lord Blackwood's study. Maps, letters, and a safe behind a painting. "
            "The safe has a combination lock."
        ),
        choices=[
            ("Try the combination 1923", "safe_open"),
            ("Search the desk", "desk_search"),
            ("Return to the hall", "upstairs_hall"),
        ],
    ),
    "grimoire": StoryNode(
        id="grimoire",
        text=(
            "The grimoire details a banishing ritual. Three people must speak the words "
            "while standing in the circle. The entity — a mirror-dweller — can be "
            "sent back through the glass."
        ),
        choices=[("Go find the mirror", "music_room")],
        tags=["ritual_known"],
    ),
    "take_doll": StoryNode(
        id="take_doll",
        text="The doll is cold. As you pick it up, it whispers: 'He's in the mirror.'",
        choices=[("Go to the music room", "music_room")],
        tags=["doll_taken"],
    ),
    "mirror_trap": StoryNode(
        id="mirror_trap",
        text=(
            "Your hand passes through the glass like water. Cold pulls you in. "
            "The mirror world is inverted, dark, and wrong. A shadow entity "
            "approaches. You're trapped."
        ),
        ending=True,
        ending_type="defeat",
    ),
    "smash_mirror": StoryNode(
        id="smash_mirror",
        text=(
            "The mirror shatters! A shriek fills the house as black mist pours from the frame. "
            "The entity is released but weakened. The house shudders. "
            "Light breaks through the cracks. Dawn comes. "
            "The entity dissolves in the sunlight.\n\n"
            "🏆 VICTORY — Blackwood Manor is cleansed."
        ),
        ending=True,
        ending_type="victory",
        tags=["mirror_destroyed"],
    ),
    "safe_open": StoryNode(
        id="safe_open",
        text="The safe clicks open. Inside: a silver crucifix and a letter: 'The mirror must be destroyed, not entered.'",
        choices=[("Take the crucifix and go", "upstairs_hall")],
        tags=["crucifix_found"],
    ),
    "desk_search": StoryNode(
        id="desk_search",
        text="A hidden drawer contains a photograph: the Blackwood family, circa 1920. Behind them, the mirror. In its reflection, something else stares out.",
        choices=[("Return to the hall", "upstairs_hall")],
    ),
    "road_escape": StoryNode(
        id="road_escape",
        text=(
            "You run through the storm. Behind you, every window of the manor "
            "lights up and then goes dark. You never look back. "
            "You survive, but the mystery of Blackwood Manor remains."
        ),
        ending=True,
        ending_type="neutral",
    ),
}

# === STORY: The Dragon's Realm (Fantasy) ===
FANTASY_STORY: dict[str, StoryNode] = {
    "start": StoryNode(
        id="start",
        text=(
            "You are a young mage of the Silver Tower. The High Council has chosen you "
            "for an impossible mission: retrieve the Dragon's Eye gem from the lair of "
            "Fyrthandor, the last great dragon. The fate of the realm depends on it."
        ),
        choices=[
            ("Take the mountain pass — direct but dangerous", "mountain_pass"),
            ("Travel through the Whispering Forest — safer but longer", "forest_path"),
            ("Seek the underground route through the Dwarven Mines", "dwarven_mines"),
        ],
    ),
    "mountain_pass": StoryNode(
        id="mountain_pass",
        text=(
            "The mountain air is thin and cold. You reach a narrow bridge of stone "
            "spanning a bottomless gorge. On the far side, a fire elemental blocks the path."
        ),
        choices=[
            ("Attempt to extinguish it with ice magic", "ice_spell"),
            ("Try to negotiate passage", "elemental_talk"),
            ("Find a way around the gorge", "gorge_detour"),
        ],
    ),
    "forest_path": StoryNode(
        id="forest_path",
        text=(
            "The forest is alive with whispers. Fae creatures flit between the trees. "
            "A fox with silver eyes blocks the path and speaks: "
            "'Answer my riddle, and I shall guide you. Fail, and wander forever.'"
        ),
        choices=[
            ("Accept the riddle", "fox_riddle"),
            ("Offer a gift instead", "fox_gift"),
            ("Push past the fox", "fox_angry"),
        ],
    ),
    "dwarven_mines": StoryNode(
        id="dwarven_mines",
        text=(
            "The Dwarven Mines echo with abandoned machinery. A lone dwarf guardian "
            "remains. 'The tunnel to the dragon's lair exists, but it is sealed. "
            "Help me restart the Great Engine, and I will open the way.'"
        ),
        choices=[
            ("Help restart the engine", "engine_puzzle"),
            ("Offer magic to open the seal", "magic_seal"),
        ],
    ),
    "ice_spell": StoryNode(
        id="ice_spell",
        text="Your ice magic clashes with the fire elemental. Steam fills the gorge. When it clears, the elemental is gone. The bridge is yours.",
        choices=[("Cross and continue", "dragon_approach")],
        tags=["elemental_defeated"],
    ),
    "elemental_talk": StoryNode(
        id="elemental_talk",
        text="The elemental speaks in crackles and pops. It wants fuel — something to burn. You offer your spare cloak. Satisfied, it steps aside.",
        choices=[("Cross the bridge", "dragon_approach")],
    ),
    "gorge_detour": StoryNode(
        id="gorge_detour",
        text="You find a precarious series of handholds around the gorge. One slip would be fatal. With careful climbing, you make it across.",
        choices=[("Continue up the mountain", "dragon_approach")],
    ),
    "fox_riddle": StoryNode(
        id="fox_riddle",
        text=(
            "'I have cities but no houses, forests but no trees, "
            "and water but no fish. What am I?'"
        ),
        choices=[
            ("A map", "fox_correct"),
            ("A dream", "fox_wrong"),
            ("A painting", "fox_wrong"),
        ],
    ),
    "fox_correct": StoryNode(
        id="fox_correct",
        text="'Clever mage!' The fox leads you through a shortcut, straight to the dragon's mountain.",
        choices=[("Follow the fox", "dragon_approach")],
        tags=["fox_ally"],
    ),
    "fox_wrong": StoryNode(
        id="fox_wrong",
        text="The fox shakes its head. 'A map, young mage. But I admire your courage. I'll guide you anyway — this once.'",
        choices=[("Follow the fox gratefully", "dragon_approach")],
    ),
    "fox_gift": StoryNode(
        id="fox_gift",
        text="You offer a silver coin. The fox takes it and reveals a hidden path through the forest.",
        choices=[("Take the hidden path", "dragon_approach")],
    ),
    "fox_angry": StoryNode(
        id="fox_angry",
        text="The fox snarls and the forest closes around you. You wander for hours before finding the path again, exhausted.",
        choices=[("Finally reach the mountain", "dragon_approach")],
        tags=["exhausted"],
    ),
    "engine_puzzle": StoryNode(
        id="engine_puzzle",
        text="The Great Engine requires three rune stones placed in order. Using your magical knowledge, you solve the sequence. The engine roars to life!",
        choices=[("Enter the opened tunnel", "dragon_approach")],
        tags=["dwarf_ally"],
    ),
    "magic_seal": StoryNode(
        id="magic_seal",
        text="Your magic strains against the ancient dwarven seal. It breaks, but the effort leaves you weakened.",
        choices=[("Enter the tunnel", "dragon_approach")],
        tags=["weakened"],
    ),
    "dragon_approach": StoryNode(
        id="dragon_approach",
        text=(
            "The dragon's lair opens before you. Fyrthandor is immense — scales of molten gold, "
            "eyes like twin suns. The Dragon's Eye gem sits in a crown atop his head. "
            "He is awake. He is watching."
        ),
        choices=[
            ("Challenge the dragon to a magical duel", "dragon_duel"),
            ("Attempt to steal the gem with illusion magic", "dragon_stealth"),
            ("Speak to the dragon as an equal", "dragon_parley"),
        ],
    ),
    "dragon_duel": StoryNode(
        id="dragon_duel",
        text=(
            "Fire meets frost in a spectacular clash. The mountain trembles. "
            "You pour everything into one final spell — a mirror of starlight "
            "that reflects the dragon's fire back. Fyrthandor falls.\n\n"
            "🏆 VICTORY — The Dragon's Eye is yours. The realm is saved."
        ),
        ending=True,
        ending_type="victory",
        tags=["dragon_defeated"],
    ),
    "dragon_stealth": StoryNode(
        id="dragon_stealth",
        text=(
            "Your illusion is convincing — until the dragon sniffs the air. "
            "'I smell human fear.' Fire engulfs the cavern. You barely escape "
            "with your life, but without the gem."
        ),
        ending=True,
        ending_type="defeat",
    ),
    "dragon_parley": StoryNode(
        id="dragon_parley",
        text=(
            "'Bold,' the dragon rumbles. 'No mage has spoken to me as an equal in a thousand years.' "
            "You explain the realm's need. Fyrthandor considers, then removes the gem. "
            "'Take it, and tell your kind: the age of dragons is not over.'\n\n"
            "🏆 VICTORY — The Dragon's Eye is given freely. Peace is forged."
        ),
        ending=True,
        ending_type="victory",
        tags=["peaceful_dragon"],
    ),
}

STORIES = {
    "adventure": ("The Lost Temple", ADVENTURE_STORY),
    "horror": ("The Haunted Manor", HORROR_STORY),
    "fantasy": ("The Dragon's Realm", FANTASY_STORY),
}


class AdventureGame(GameInterface):
    """Choose-your-own-adventure with branching narratives and full replay."""

    def game_type(self) -> str:
        return "adventure"

    async def initialize(self, state: GameState) -> GameOutput:
        state.phase = GamePhase.SETUP
        state.metadata["story_id"] = ""
        state.metadata["decision_tree"] = []

        story_list = "\n".join(
            f"  [{sid}] {name}" for sid, (name, _) in STORIES.items()
        )

        return GameOutput(
            narrative=(
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║           CREATE YOUR OWN ADVENTURE                        ║\n"
                "╚══════════════════════════════════════════════════════════════╝\n\n"
                "Choose your story:\n"
                f"{story_list}\n\n"
                "Type the story name to begin."
            ),
            prompt="Choose> ",
            options=list(STORIES.keys()),
        )

    async def process_input(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]:
        cmd = user_input.strip().lower()

        # Story selection
        if state.phase == GamePhase.SETUP:
            if cmd in STORIES:
                state.metadata["story_id"] = cmd
                state.metadata["current_node"] = "start"
                state.metadata["decision_tree"] = []
                state.metadata["tags_collected"] = []
                state.phase = GamePhase.PLAYING

                name, story = STORIES[cmd]
                node = story["start"]

                return self._render_node(node, state, f"Beginning: {name}")
            else:
                return (
                    GameOutput(narrative=f"Unknown story. Choose: {', '.join(STORIES.keys())}"),
                    GameAction(actor="player", action_type="invalid", valid=False),
                )

        # Game play
        story_id = state.metadata.get("story_id", "")
        if story_id not in STORIES:
            return (
                GameOutput(narrative="Error: no story loaded."),
                GameAction(actor="system", action_type="error", valid=False),
            )

        _, story = STORIES[story_id]
        current_node_id = state.metadata.get("current_node", "start")
        node = story.get(current_node_id)

        if not node:
            return (
                GameOutput(narrative="Error: lost in the story."),
                GameAction(actor="system", action_type="error", valid=False),
            )

        # Parse choice
        try:
            choice_idx = int(cmd) - 1
        except ValueError:
            # Try matching by text
            choice_idx = -1
            for i, (text, _) in enumerate(node.choices):
                if cmd in text.lower():
                    choice_idx = i
                    break

        if choice_idx < 0 or choice_idx >= len(node.choices):
            return (
                GameOutput(narrative=f"Choose 1-{len(node.choices)}."),
                GameAction(actor="player", action_type="invalid", valid=False),
            )

        choice_text, next_node_id = node.choices[choice_idx]
        state.metadata["decision_tree"].append({
            "from": current_node_id,
            "choice": choice_text,
            "to": next_node_id,
        })

        next_node = story.get(next_node_id)
        if not next_node:
            return (
                GameOutput(narrative="The story path leads nowhere... (bug)"),
                GameAction(actor="system", action_type="error"),
            )

        state.metadata["current_node"] = next_node_id

        # Collect tags
        if next_node.tags:
            state.metadata.setdefault("tags_collected", []).extend(next_node.tags)

        return self._render_node(
            next_node,
            state,
            f"Chose: {choice_text}",
        )

    def _render_node(
        self, node: StoryNode, state: GameState, action_desc: str
    ) -> tuple[GameOutput, GameAction]:
        lines = [node.text]

        game_over = node.ending

        if not node.ending and node.choices:
            lines.append("")
            for i, (text, _) in enumerate(node.choices):
                lines.append(f"  [{i+1}] {text}")

        output = GameOutput(
            narrative="\n".join(lines),
            options=[text for text, _ in node.choices],
            prompt="Choice> " if not node.ending else "",
            game_over=game_over,
        )

        if game_over:
            tree = state.metadata.get("decision_tree", [])
            output.narrative += f"\n\nDecisions made: {len(tree)}"
            output.narrative += f"\nEnding: {node.ending_type}"

        action = GameAction(
            actor="player",
            action_type="choose",
            description=action_desc,
            action_data={"node": node.id},
        )

        return output, action

    def validate_input(self, user_input: str, state: GameState) -> tuple[bool, str]:
        if not user_input.strip():
            return False, "Please make a choice."
        return True, ""

    async def get_help(self) -> str:
        return """
═══ ADVENTURE COMMANDS ═══

Enter a number to make your choice.
Type the beginning of a choice to select it.

META:
  /save    Save your progress
  /load    Load a save point
  /undo    Undo your last choice
  /redo    Redo a choice
  /status  View your journey so far
  /replay  See all decisions made
  /quit    End the adventure
"""

    async def generate_summary(self, state: GameState) -> str:
        story_id = state.metadata.get("story_id", "unknown")
        tree = state.metadata.get("decision_tree", [])
        tags = state.metadata.get("tags_collected", [])
        name = STORIES.get(story_id, (story_id, {}))[0]

        return (
            f"═══ ADVENTURE SUMMARY ═══\n"
            f"Story: {name}\n"
            f"Decisions: {len(tree)}\n"
            f"Current node: {state.metadata.get('current_node', 'start')}\n"
            f"Achievements: {', '.join(tags) if tags else 'None'}\n"
            f"Turns: {state.turn_number}"
        )
