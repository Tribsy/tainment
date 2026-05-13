"""
cogs/entertainment/constants.py — joke/story banks + hangman word list & ASCII stages.

Phase 3g: extracted verbatim from cogs/entertainment/__init__.py. Leaf module.
"""


JOKES = {
    'dad': [
        ("Why don't scientists trust atoms?", "Because they make up everything!"),
        ("I'm reading a book about anti-gravity.", "It's impossible to put down!"),
        ("Did you hear about the guy who invented Lifesavers?", "He made a mint."),
        ("Why can't you give Elsa a balloon?", "She'll let it go."),
        ("I used to hate facial hair...", "but then it grew on me."),
    ],
    'tech': [
        ("Why do programmers prefer dark mode?", "Because light attracts bugs!"),
        ("How many programmers does it take to change a lightbulb?", "None, that's a hardware problem."),
        ("Why did the developer go broke?", "Because he used up all his cache."),
        ("What do you call 8 hobbits?", "A hobbyte."),
        ("Why do Java developers wear glasses?", "Because they don't C#."),
    ],
    'puns': [
        ("I'm on a seafood diet.", "I see food and I eat it."),
        ("Time flies like an arrow.", "Fruit flies like a banana."),
        ("I told my wife she was drawing her eyebrows too high.", "She looked surprised."),
        ("I used to be a banker...", "but I lost interest."),
        ("I'm reading a book about mazes.", "I got lost in it."),
    ],
    'animal': [
        ("Why don't elephants use computers?", "Because they're afraid of the mouse."),
        ("What do you call a sleeping dinosaur?", "A dino-snore!"),
        ("Why can't a leopard hide?", "It's always spotted."),
        ("What do you call a fish without eyes?", "A fsh."),
        ("Why did the cat sit on the computer?", "To keep an eye on the mouse."),
    ],
    'food': [
        ("Why did the tomato turn red?", "Because it saw the salad dressing!"),
        ("What do you call a fake noodle?", "An impasta!"),
        ("Why don't eggs tell jokes?", "They'd crack each other up."),
        ("What did the sushi say to the bee?", "Wasabi!"),
        ("Why did the baker go to therapy?", "Because he had too many fillings."),
    ],
}


TIER_JOKES = {
    'Basic': ['dad', 'animal'],
    'Vibe': ['dad', 'animal', 'tech', 'puns', 'food'],
    'Premium': ['dad', 'animal', 'tech', 'puns', 'food'],
    'Pro': ['dad', 'animal', 'tech', 'puns', 'food'],
}


STORIES = {
    'adventure': (
        "The ancient map had led you here — a crumbling temple swallowed by jungle. "
        "Inside, golden light pulsed from a chamber. You stepped forward, heart pounding. "
        "A puzzle door blocked the passage, its stone gears frozen for centuries. "
        "After three attempts your hand found the hidden catch. The door groaned open. "
        "Beyond it lay not treasure, but a library — millions of preserved books from a forgotten civilization. "
        "The real treasure was knowledge, and you'd just saved it from oblivion."
    ),
    'mystery': (
        "The lighthouse had been dark for three days when Detective Marlowe arrived on the island. "
        "The keeper, old Ezra, was gone without a trace. No boat, no note, no struggle. "
        "But under the lens room floor Marlowe found a brass button — Navy issue, 1944 vintage. "
        "Following a hunch she climbed to the rocks below. There was Ezra, alive, guarding a sea cave "
        "that hid a smuggling ring operating for thirty years. He'd stayed quiet — until now."
    ),
    'sci-fi': (
        "The colony ship *Meridian* had been in deep sleep for 200 years when the alarm woke Navigator Shen. "
        "On the viewscreen: an impossibly large structure orbiting their destination planet. "
        "It was a ring — 40,000 kilometers across — and it was radiating a signal. "
        "After two days of translation work, the message was four words: 'We have been waiting.' "
        "Shen opened a channel and spoke for all humanity: 'So have we.'"
    ),
    'fantasy': (
        "They said the Dragon of Ashenveil hadn't moved in a hundred years. "
        "Kaela didn't believe them — not until she saw it herself, curled around a mountain like a sleeping cat. "
        "She approached, hands open, speaking the old tongue her grandmother had taught her. "
        "One amber eye cracked open. The dragon exhaled — a gentle warmth, not fire. "
        "It had been waiting for someone who still remembered the words. Together, they flew at dawn."
    ),
    'fable': (
        "A crow found a piece of cheese and flew to a branch to eat in peace. "
        "A fox below called up: 'Your feathers are magnificent! Your voice must match.' "
        "The crow, flattered, opened its beak to sing — and the cheese fell. "
        "The fox snatched it. 'Your voice is lovely,' the fox said, walking away, 'but your judgment needs work.' "
        "The crow learned: beware those whose compliments cost you something."
    ),
}


TIER_STORIES = {
    'Basic': ['adventure', 'fable'],
    'Vibe': ['adventure', 'fable', 'mystery', 'fantasy'],
    'Premium': ['adventure', 'fable', 'mystery', 'fantasy'],
    'Pro': list(STORIES.keys()),
}


HANGMAN_WORDS = {
    'easy': ['cat', 'dog', 'sun', 'hat', 'cup', 'pen', 'box', 'run', 'fly', 'hop'],
    'medium': ['python', 'castle', 'bridge', 'jungle', 'butter', 'rocket', 'wizard', 'planet'],
    'hard': ['labyrinth', 'quizzical', 'chrysalis', 'paradoxical', 'melancholy', 'archipelago'],
}


HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]
