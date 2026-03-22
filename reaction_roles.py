"""
Reaction-role system for the genre lane channel.
Admin runs t!setupgenreroles to create the channel and post the panel.
Members react with an emoji to receive the role; unreact to remove it.
"""

import discord
from discord.ext import commands
import database as db
import config

# emoji string → role name
GENRE_MAP = {
    '\U0001f3a4': '\U0001f3a4 Pop Lane',
    '\U0001f3b6': '\U0001f3b6 Hip-Hop Lane',
    '\U0001f3b8': '\U0001f3b8 Rock Lane',
    '\U0001f50a': '\U0001f50a Electronic Lane',
}


class ReactionRoles(commands.Cog, name='Reaction Roles'):
    """Self-assignable genre lane roles via emoji reactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Reaction listeners ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        member = payload.member
        if not member or member.bot:
            return
        await self._toggle_role(payload, add=True, member=member)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        await self._toggle_role(payload, add=False, member=member)

    async def _toggle_role(
        self,
        payload: discord.RawReactionActionEvent,
        *,
        add: bool,
        member: discord.Member,
    ):
        stored = await db.get_bot_message(payload.guild_id, 'genre_roles')
        if not stored or stored['message_id'] != payload.message_id:
            return

        emoji_str = str(payload.emoji)
        role_name = GENRE_MAP.get(emoji_str)
        if not role_name:
            # Remove any unknown reaction to keep the panel clean
            if add:
                try:
                    channel = member.guild.get_channel(payload.channel_id)
                    if channel:
                        msg = await channel.fetch_message(payload.message_id)
                        await msg.remove_reaction(payload.emoji, member)
                except discord.HTTPException:
                    pass
            return

        role = discord.utils.get(member.guild.roles, name=role_name)
        if not role:
            return

        try:
            if add:
                await member.add_roles(role, reason='Genre lane self-selection')
            else:
                await member.remove_roles(role, reason='Genre lane self-deselection')
        except discord.HTTPException:
            pass

    # ── Setup command ─────────────────────────────────────────────────────────

    @commands.command(
        name='setupgenreroles',
        description='Create the genre lane channel and post the reaction-role panel (Admin)',
    )
    @commands.has_permissions(manage_channels=True)
    async def setup_genre_roles(self, ctx: commands.Context):
        guild = ctx.guild

        # Find or create the channel
        channel = discord.utils.find(
            lambda c: 'pick-your-lane' in c.name or 'genre-role' in c.name,
            guild.text_channels,
        )

        if not channel:
            category = discord.utils.find(
                lambda c: 'community' in c.name.lower(),
                guild.categories,
            )
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    add_reactions=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    add_reactions=True,
                ),
            }
            channel = await guild.create_text_channel(
                name='\U0001f3a4\u2503pick-your-lane',
                category=category,
                overwrites=overwrites,
                topic='React to pick your genre lane \u2014 unreact to remove it.',
                reason='Genre lane self-role channel',
            )

        # Clear any old bot messages in this channel
        try:
            async for msg in channel.history(limit=20):
                if msg.author == guild.me:
                    await msg.delete()
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

        await db.upsert_bot_message(guild.id, 'genre_roles', channel.id, panel.id)

        await ctx.send(
            f'\u2705 Genre lane channel ready: {channel.mention}',
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
