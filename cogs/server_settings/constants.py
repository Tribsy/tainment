"""
cogs/server_settings/constants.py — server-template definitions for `t!setupserver`.

Phase 3c: extracted verbatim from server_settings.py. Leaf module — no internal
imports beyond stdlib (none needed) and config.
"""


SETUP_ROLE_DEFS = [
    ('\U0001f451 Owner', 0xf1c40f, False),
    ('\u26a1 Admin', 0x00e5ff, False),
    ('\U0001f6e1\ufe0f Moderator', 0x7c4dff, False),
    ('\U0001f3a7 Support', 0x2ecc71, False),
    ('\U0001f4e2 Announcements Ping', 0xe040fb, True),
    ('\U0001f389 Events Ping', 0x00e5ff, True),
    ('\u2728 VIP', 0xf39c12, True),
    ('\U0001f525 Fuser', 0xe040fb, True),
    ('\U0001f3b5 Listener', 0x95a5a6, False),
    ('\U0001f507 Muted', 0x2c2f33, False),
]


SETUP_GENRE_ROLE_DEFS = [
    ('\U0001f3a4 Pop Lane', 0xe040fb),
    ('\U0001f3b6 Hip-Hop Lane', 0x00e5ff),
    ('\U0001f3b8 Rock Lane', 0xff5722),
    ('\U0001f50a Electronic Lane', 0x7c4dff),
    ('\U0001f3b7 R&B & Soul Lane', 0xf06292),
    ('\U0001f3b9 Jazz Lane', 0x16a085),
    ('\U0001f908 Country Lane', 0xd35400),
    ('\U0001f483 Latin Lane', 0xe74c3c),
    ('\U0001f333 Indie Lane', 0x27ae60),
    ('\U0001f305 Lo-Fi Lane', 0x5dade2),
]


SETUP_CATEGORY_CHANNELS = {
    'Information': [
        '\U0001f44b\u2503welcome',
        '\U0001f4dc\u2503rules',
        '\U0001f4e2\u2503announcements',
        '\U0001f4f0\u2503updates',
        '\u2753\u2503faq',
    ],
    'Community': [
        '\U0001f4ac\u2503general',
        '\u2728\u2503introductions',
        '\U0001f4f8\u2503media',
        '\U0001f602\u2503memes',
        '\U0001f916\u2503bot-chat',
        '\U0001f4a1\u2503suggestions',
        '\U0001f3a4\u2503pick-your-lane',
    ],
    'Games': [
        '\U0001f9e0\u2503trivia-chat',
        '\U0001f4dd\u2503word-games',
        '\U0001f4b0\u2503economy-chat',
        '\U0001f3c6\u2503leaderboards',
    ],
    'Support': [
        '\U0001f198\u2503help',
        '\U0001f41b\u2503bug-reports',
        '\U0001f4b3\u2503billing-support',
        '\u2b50\u2503feature-requests',
    ],
    'Staff': [
        '\U0001f6e1\ufe0f\u2503staff-chat',
        '\U0001f4cb\u2503mod-logs',
        '\u2699\ufe0f\u2503admin-panel',
    ],
}


READ_ONLY_SETUP_CHANNELS = {
    '\U0001f44b\u2503welcome',
    '\U0001f4dc\u2503rules',
    '\U0001f4e2\u2503announcements',
    '\U0001f4f0\u2503updates',
    '\u2753\u2503faq',
}


STAFF_ONLY_SETUP_CHANNELS = {
    '\U0001f6e1\ufe0f\u2503staff-chat',
    '\U0001f4cb\u2503mod-logs',
    '\u2699\ufe0f\u2503admin-panel',
}


SETUP_STARTER_MESSAGES = {
    '\U0001f44b\u2503welcome': (
        "**Welcome to Tainment+!**\n\n"
        "Read the rules, say hello, and use `t!help` in bot chat to get started."
    ),
    '\U0001f4dc\u2503rules': (
        "**Server Rules**\n\n"
        "1. Be respectful.\n"
        "2. No spam.\n"
        "3. Keep content in the right channels.\n"
        "4. No NSFW.\n"
        "5. Follow Discord ToS."
    ),
    '\U0001f4e2\u2503announcements': (
        "**Announcements**\n\n"
        "Server news, bot updates, and events will be posted here."
    ),
    '\U0001f916\u2503bot-chat': (
        "**Bot Commands**\n\n"
        "Try `t!help`, `t!daily`, `t!balance`, `t!shop`, and `t!profile`."
    ),
}
