"""
Creates #🎤┃pick-your-lane under the Community category,
posts the genre reaction-role panel, and stores the message ID in the DB.

Run: python setup_genre_channel.py
"""

import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import discord
from dotenv import load_dotenv
import database as db

load_dotenv()
TOKEN    = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163

GENRE_MAP = {
    '\U0001f3a4': '\U0001f3a4 Pop Lane',
    '\U0001f3b6': '\U0001f3b6 Hip-Hop Lane',
    '\U0001f3b8': '\U0001f3b8 Rock Lane',
    '\U0001f50a': '\U0001f50a Electronic Lane',
}


class SetupClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Connected as: {self.user}')
        await db.init_db()
        g = self.get_guild(GUILD_ID)
        if not g:
            print('Guild not found.')
            await self.close()
            return

        # Find or create the channel
        channel = discord.utils.find(
            lambda c: 'pick-your-lane' in c.name or 'genre-role' in c.name,
            g.text_channels,
        )

        if not channel:
            category = discord.utils.find(
                lambda c: 'community' in c.name.lower(),
                g.categories,
            )
            overwrites = {
                g.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    add_reactions=True,
                ),
                g.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    add_reactions=True,
                ),
            }
            channel = await g.create_text_channel(
                name='\U0001f3a4\u2503pick-your-lane',
                category=category,
                overwrites=overwrites,
                topic='React to pick your genre lane \u2014 unreact to remove it.',
                reason='Genre lane self-role channel',
            )
            print(f'[CREATED] #{channel.name}')
        else:
            print(f'[EXISTS]  #{channel.name}')
            # Clear old bot messages
            try:
                async for msg in channel.history(limit=20):
                    if msg.author == g.me:
                        await msg.delete()
                        await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass

        # Post the panel
        embed = discord.Embed(
            title='\U0001f3b5 Choose Your Genre Lane',
            description=(
                'React below to get your genre role. Unreact to remove it.\n\n'
                '\U0001f3a4 **Pop Lane** \u2014 Chart-toppers & pop anthems\n'
                '\U0001f3b6 **Hip-Hop Lane** \u2014 Rap, R\u0026B & beats\n'
                '\U0001f3b8 **Rock Lane** \u2014 Rock, metal & alternative\n'
                '\U0001f50a **Electronic Lane** \u2014 EDM, house, techno & everything electronic\n\n'
                '*Genre roles are cosmetic \u2014 they reflect your taste, nothing more.*'
            ),
            color=0xe040fb,
        )
        embed.set_footer(text='PopFusion \u2014 discover music. build community.')

        panel = await channel.send(embed=embed)
        for emoji in GENRE_MAP:
            await panel.add_reaction(emoji)
            await asyncio.sleep(0.3)

        await db.upsert_bot_message(g.id, 'genre_roles', channel.id, panel.id)
        print(f'[OK] Panel posted in #{channel.name} (message ID: {panel.id})')
        print('\nDone!')
        await self.close()


if __name__ == '__main__':
    client = SetupClient()
    client.run(TOKEN, log_handler=None)
