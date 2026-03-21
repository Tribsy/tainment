"""
Rebrand PopFusion Discord roles to match the website's music festival identity.
Renames existing roles, applies brand colours, creates genre lane roles.

Run:  python rebrand_roles.py
"""

import asyncio
import re
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN    = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163


def text_slug(name: str) -> str:
    """Strip emoji/symbols, lowercase, collapse spaces -> slug for matching."""
    ascii_only = ''.join(c for c in name if ord(c) < 128)
    return re.sub(r'\s+', ' ', ascii_only.strip()).lower()


# Maps normalised text slug → (new_name, hex_colour)
ROLE_MAP = {
    'owner':              ('\U0001f39b\ufe0f Founder',        0xe040fb),  # magenta
    'admin':              ('\U0001f39a\ufe0f Producer',        0x00e5ff),  # cyan
    'moderator':          ('\U0001f6e1\ufe0f Stage Manager',   0x7c4dff),  # purple
    'support':            ('\U0001f399\ufe0f Crew',             0x2ecc71),  # green
    'announcements ping': ('\U0001f4e2 Drop Alerts',            0xe040fb),
    'events ping':        ('\U0001f39f\ufe0f Event Pass',       0x00e5ff),
    'vip':                ('\u2728 VIP',                        0xf39c12),  # gold
    'subscriber':         ('\U0001f525 Fuser',                  0xe040fb),
    'member':             ('\U0001f3b5 Listener',               0x95a5a6),  # gray
    'muted':              ('\U0001f507 Muted',                  0x2c2f33),  # keep / recolour dark
}

# Genre lane roles to create (name, colour)
GENRE_ROLES = [
    ('\U0001f3a4 Pop Lane',         0xe040fb),  # magenta
    ('\U0001f3b6 Hip-Hop Lane',     0x00e5ff),  # cyan
    ('\U0001f3b8 Rock Lane',        0xff5722),  # deep-orange
    ('\U0001f50a Electronic Lane',  0x7c4dff),  # purple
]

# Skip these built-in / unrelated roles
SKIP_SLUGS = {'everyone', 'tainment+', 'vibebot', 'vibebit test', 'workers', 'fusionist', 'dj (music moderators)'}


class RebrandClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Connected as: {self.user}')
        guild = self.get_guild(GUILD_ID)
        if not guild:
            print('Guild not found.')
            await self.close()
            return

        print(f'Guild: {guild.name}  ({guild.member_count} members)\n')

        # ── Phase 1: Rename & recolour roles ──────────────────────────────────
        print('=' * 60)
        print('  PHASE 1 — RENAME & RECOLOUR ROLES')
        print('=' * 60)

        for role in guild.roles:
            slug = text_slug(role.name)
            if slug in SKIP_SLUGS:
                continue
            mapping = ROLE_MAP.get(slug)
            if mapping is None:
                continue
            new_name, colour = mapping
            if role.name == new_name:
                print(f'  [OK]       "{role.name}" already correct')
                continue
            try:
                await role.edit(name=new_name, colour=discord.Colour(colour), reason='PopFusion rebrand')
                print(f'  [RENAMED]  "{role.name}"  →  "{new_name}"')
            except discord.HTTPException as e:
                print(f'  [ERROR]    "{role.name}": {e}')
            await asyncio.sleep(0.5)

        # ── Phase 2: Create genre lane roles ──────────────────────────────────
        print()
        print('=' * 60)
        print('  PHASE 2 — GENRE LANE ROLES')
        print('=' * 60)

        await guild.fetch_roles()
        existing_names = {r.name for r in guild.roles}

        for name, colour in GENRE_ROLES:
            if name in existing_names:
                print(f'  [EXISTS]   {name}')
                continue
            try:
                await guild.create_role(
                    name=name,
                    colour=discord.Colour(colour),
                    mentionable=True,
                    reason='PopFusion genre lane role',
                )
                print(f'  [CREATED]  {name}')
            except discord.HTTPException as e:
                print(f'  [ERROR]    {name}: {e}')
            await asyncio.sleep(0.5)

        # ── Phase 3: Post genre info in bot-commands channel ──────────────────
        print()
        print('=' * 60)
        print('  PHASE 3 — GENRE LANE ANNOUNCEMENT')
        print('=' * 60)

        bot_ch = None
        for ch in guild.text_channels:
            if ('bot-chat' in ch.name or 'vibe-commands' in ch.name or 'bot' in ch.name):
                if ch.permissions_for(guild.me).send_messages:
                    bot_ch = ch
                    break

        if bot_ch:
            embed = discord.Embed(
                title='\U0001f3b5 Choose Your Genre Lane',
                description=(
                    'Tell us what you vibe with! Ask a **\U0001f6e1\ufe0f Stage Manager** to assign your genre role.\n\n'
                    '\U0001f3a4 **Pop Lane** — Chart-toppers & pop anthems\n'
                    '\U0001f3b6 **Hip-Hop Lane** — Rap, R&B & beats\n'
                    '\U0001f3b8 **Rock Lane** — Rock, metal & alternative\n'
                    '\U0001f50a **Electronic Lane** — EDM, house, techno & everything electronic\n\n'
                    '*Genre roles are cosmetic — they reflect your taste, nothing more.*'
                ),
                color=0xe040fb,
            )
            embed.set_footer(text='PopFusion — discover music. build community.')
            await bot_ch.send(embed=embed)
            print(f'  [POSTED]   Genre info in #{bot_ch.name}')
        else:
            print('  [SKIP]     No suitable channel found for genre announcement')

        # ── Summary ───────────────────────────────────────────────────────────
        print()
        print('=' * 60)
        print('  DONE')
        print('=' * 60)
        print()
        print('  Staff:     \U0001f39b\ufe0f Founder  |  \U0001f39a\ufe0f Producer  |  \U0001f6e1\ufe0f Stage Manager  |  \U0001f399\ufe0f Crew')
        print('  Community: \U0001f3b5 Listener  |  \U0001f525 Fuser  |  \u2728 VIP')
        print('  Pings:     \U0001f4e2 Drop Alerts  |  \U0001f39f\ufe0f Event Pass')
        print('  Genre:     \U0001f3a4 Pop Lane  |  \U0001f3b6 Hip-Hop Lane  |  \U0001f3b8 Rock Lane  |  \U0001f50a Electronic Lane')
        print('  Levels:    \U0001f331 Newcomer  \U0001f3a7 Groover  \U0001f4bf Fanatic  \U0001f3b8 Headliner  \u26a1 Icon')
        print()

        await self.close()


if __name__ == '__main__':
    client = RebrandClient()
    client.run(TOKEN, log_handler=None)
