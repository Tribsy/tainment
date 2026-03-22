"""
Full moderation suite.
Commands: warn, warnings, clearwarn, kick, ban, unban, timeout, untimeout,
          purge, slowmode, lock, unlock, addrole, removerole, nick, modlog, setmodlog
"""

import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import aiosqlite
import re
import config
from server_settings import get_server_tier


MOD_COLORS = {
    'warn':    0xFEE75C,
    'kick':    0xFF6B35,
    'ban':     0xED4245,
    'unban':   0x57F287,
    'timeout': 0xFF6B35,
    'mute':    0xFF6B35,
    'lock':    0xED4245,
    'unlock':  0x57F287,
    'purge':   0x5865F2,
    'role':    0x5865F2,
    'nick':    0x5865F2,
    'info':    0x5865F2,
}


async def _init_mod_tables():
    """Create moderation tables if they don't exist."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                duration TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER
            )
        """)
        await db.commit()


async def _add_case(guild_id, user_id, mod_id, action, reason=None, duration=None) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO mod_cases (guild_id, user_id, moderator_id, action, reason, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, action, reason, duration)
        )
        await db.commit()
        return cur.lastrowid


async def _get_log_channel(bot: commands.Bot, guild_id: int) -> discord.TextChannel | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT log_channel_id FROM mod_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return None
    guild = bot.get_guild(guild_id)
    return guild.get_channel(row[0]) if guild else None


async def _send_log(bot: commands.Bot, guild_id: int, embed: discord.Embed):
    ch = await _get_log_channel(bot, guild_id)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


def _mod_embed(action: str, user: discord.Member | discord.User, mod: discord.Member,
               reason: str, case_id: int, duration: str = None) -> discord.Embed:
    color = MOD_COLORS.get(action.lower(), config.COLORS['primary'])
    embed = discord.Embed(
        title=f"\U0001f6e1\ufe0f {action.capitalize()} | Case #{case_id}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Moderator", value=mod.mention, inline=True)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed


def _parse_duration(s: str) -> timedelta | None:
    """Parse strings like 10m, 2h, 1d, 30s into timedelta."""
    pattern = re.fullmatch(r'(\d+)([smhd])', s.lower().strip())
    if not pattern:
        return None
    val, unit = int(pattern.group(1)), pattern.group(2)
    if unit == 's':
        return timedelta(seconds=val)
    if unit == 'm':
        return timedelta(minutes=val)
    if unit == 'h':
        return timedelta(hours=val)
    if unit == 'd':
        return timedelta(days=val)
    return None


class Moderation(commands.Cog, name="Moderation"):
    """Full moderation suite for PopFusion."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """All moderation commands require a server Basic or Pro subscription."""
        if not ctx.guild:
            return False
        tier = await get_server_tier(ctx.guild.id)
        if tier == 'Free':
            await ctx.send(embed=discord.Embed(
                title="Server Plan Required",
                description=(
                    "Moderation commands require a **Basic** or **Pro** server subscription.\n\n"
                    "Use `t!serversubscribe` to view plans and upgrade."
                ),
                color=config.COLORS['warning'],
            ))
            return False
        return True

    # ── Warn ──────────────────────────────────────────────────────────────────

    @commands.command(name='warn', description='Warn a member')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if member.bot or member == ctx.author:
            await ctx.send(embed=discord.Embed(description="Invalid target.", color=config.COLORS['error']))
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(embed=discord.Embed(description="You can't warn someone with an equal or higher role.", color=config.COLORS['error']))
            return

        case_id = await _add_case(ctx.guild.id, member.id, ctx.author.id, 'warn', reason)
        embed = _mod_embed('warn', member, ctx.author, reason, case_id)
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

        try:
            await member.send(embed=discord.Embed(
                title=f"You received a warning in {ctx.guild.name}",
                description=f"**Reason:** {reason or 'No reason provided'}\nCase #{case_id}",
                color=MOD_COLORS['warn'],
            ))
        except discord.HTTPException:
            pass

    # ── Warnings ──────────────────────────────────────────────────────────────

    @commands.command(name='warnings', aliases=['warns'], description='View a member\'s warnings')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM mod_cases WHERE guild_id = ? AND user_id = ? AND action = 'warn' AND active = 1 ORDER BY created_at DESC LIMIT 10",
                (ctx.guild.id, member.id)
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await ctx.send(embed=discord.Embed(
                description=f"{member.mention} has no active warnings.",
                color=config.COLORS['success'],
            ))
            return

        embed = discord.Embed(
            title=f"Warnings — {member.display_name}",
            color=MOD_COLORS['warn'],
        )
        for row in rows:
            mod = ctx.guild.get_member(row['moderator_id'])
            mod_str = mod.display_name if mod else f"ID:{row['moderator_id']}"
            ts = row['created_at'][:10]
            embed.add_field(
                name=f"Case #{row['id']} — {ts}",
                value=f"**Reason:** {row['reason'] or 'None'}\n**By:** {mod_str}",
                inline=False,
            )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    # ── Clear Warning ─────────────────────────────────────────────────────────

    @commands.command(name='clearwarn', aliases=['delwarn'], description='Clear a warning by case ID')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def clearwarn(self, ctx: commands.Context, case_id: int):
        async with aiosqlite.connect(config.DB_PATH) as db:
            async with db.execute(
                "SELECT * FROM mod_cases WHERE id = ? AND guild_id = ? AND action = 'warn'",
                (case_id, ctx.guild.id)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                await ctx.send(embed=discord.Embed(
                    description=f"No warn case #{case_id} found in this server.",
                    color=config.COLORS['error'],
                ))
                return
            await db.execute("UPDATE mod_cases SET active = 0 WHERE id = ?", (case_id,))
            await db.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Warning case #{case_id} cleared.",
            color=config.COLORS['success'],
        ))

    # ── Kick ──────────────────────────────────────────────────────────────────

    @commands.command(name='kick', description='Kick a member from the server')
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if member.bot:
            await ctx.send(embed=discord.Embed(description="Cannot kick bots.", color=config.COLORS['error']))
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(embed=discord.Embed(description="You can't kick someone with an equal or higher role.", color=config.COLORS['error']))
            return

        try:
            await member.send(embed=discord.Embed(
                title=f"You have been kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason or 'No reason provided'}",
                color=MOD_COLORS['kick'],
            ))
        except discord.HTTPException:
            pass

        await member.kick(reason=reason)
        case_id = await _add_case(ctx.guild.id, member.id, ctx.author.id, 'kick', reason)
        embed = _mod_embed('kick', member, ctx.author, reason, case_id)
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

    # ── Ban ───────────────────────────────────────────────────────────────────

    @commands.command(name='ban', description='Ban a member from the server')
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if member.bot:
            await ctx.send(embed=discord.Embed(description="Cannot ban bots.", color=config.COLORS['error']))
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(embed=discord.Embed(description="You can't ban someone with an equal or higher role.", color=config.COLORS['error']))
            return

        try:
            await member.send(embed=discord.Embed(
                title=f"You have been banned from {ctx.guild.name}",
                description=f"**Reason:** {reason or 'No reason provided'}",
                color=MOD_COLORS['ban'],
            ))
        except discord.HTTPException:
            pass

        await member.ban(reason=reason, delete_message_days=0)
        case_id = await _add_case(ctx.guild.id, member.id, ctx.author.id, 'ban', reason)
        embed = _mod_embed('ban', member, ctx.author, reason, case_id)
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

    # ── Unban ─────────────────────────────────────────────────────────────────

    @commands.command(name='unban', description='Unban a user by ID')
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx: commands.Context, user_id: int, *, reason: str = None):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            await ctx.send(embed=discord.Embed(
                description=f"User `{user_id}` is not banned or doesn't exist.",
                color=config.COLORS['error'],
            ))
            return

        case_id = await _add_case(ctx.guild.id, user_id, ctx.author.id, 'unban', reason)
        embed = _mod_embed('unban', user, ctx.author, reason, case_id)
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

    # ── Timeout ───────────────────────────────────────────────────────────────

    @commands.command(name='timeout', aliases=['mute'], description='Timeout a member (e.g. 10m, 2h, 1d)')
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = None):
        delta = _parse_duration(duration)
        if not delta:
            await ctx.send(embed=discord.Embed(
                description="Invalid duration. Use `10m`, `2h`, `1d`, `30s`.",
                color=config.COLORS['error'],
            ))
            return
        if delta > timedelta(days=28):
            await ctx.send(embed=discord.Embed(description="Max timeout is 28 days.", color=config.COLORS['error']))
            return
        if member.bot:
            await ctx.send(embed=discord.Embed(description="Cannot timeout bots.", color=config.COLORS['error']))
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(embed=discord.Embed(description="You can't timeout someone with an equal or higher role.", color=config.COLORS['error']))
            return

        until = datetime.now(timezone.utc) + delta
        await member.timeout(until, reason=reason)
        case_id = await _add_case(ctx.guild.id, member.id, ctx.author.id, 'timeout', reason, duration)
        embed = _mod_embed('timeout', member, ctx.author, reason, case_id, duration)
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

        try:
            await member.send(embed=discord.Embed(
                title=f"You have been timed out in {ctx.guild.name}",
                description=f"**Duration:** {duration}\n**Reason:** {reason or 'No reason provided'}",
                color=MOD_COLORS['timeout'],
            ))
        except discord.HTTPException:
            pass

    # ── Untimeout ─────────────────────────────────────────────────────────────

    @commands.command(name='untimeout', aliases=['unmute'], description='Remove a member\'s timeout')
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if not member.is_timed_out():
            await ctx.send(embed=discord.Embed(
                description=f"{member.mention} is not timed out.",
                color=config.COLORS['warning'],
            ))
            return
        await member.timeout(None, reason=reason)
        case_id = await _add_case(ctx.guild.id, member.id, ctx.author.id, 'untimeout', reason)
        await ctx.send(embed=discord.Embed(
            title=f"\u2705 Timeout removed — Case #{case_id}",
            description=f"{member.mention}'s timeout has been lifted.",
            color=config.COLORS['success'],
        ))

    # ── Purge ─────────────────────────────────────────────────────────────────

    @commands.command(name='purge', aliases=['clear', 'prune'], description='Bulk delete messages (1-100)')
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: int, member: discord.Member = None):
        if amount < 1 or amount > 100:
            await ctx.send(embed=discord.Embed(
                description="Amount must be between 1 and 100.",
                color=config.COLORS['error'],
            ))
            return

        # Delete the invocation silently for slash commands
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        def pred(m):
            return member is None or m.author == member

        try:
            deleted = await ctx.channel.purge(limit=amount, check=pred, bulk=True)
        except discord.HTTPException as e:
            await ctx.send(embed=discord.Embed(
                description=f"Failed to purge: {e}",
                color=config.COLORS['error'],
            ))
            return

        note = f"by {member.mention} " if member else ""
        msg = await ctx.send(embed=discord.Embed(
            description=f"\U0001f5d1\ufe0f Deleted **{len(deleted)}** message{'s' if len(deleted) != 1 else ''} {note}in {ctx.channel.mention}.",
            color=MOD_COLORS['purge'],
        ))

        log_embed = discord.Embed(
            title="\U0001f5d1\ufe0f Purge",
            description=f"**{len(deleted)}** messages deleted in {ctx.channel.mention} {note}by {ctx.author.mention}",
            color=MOD_COLORS['purge'],
            timestamp=datetime.now(timezone.utc),
        )
        await _send_log(self.bot, ctx.guild.id, log_embed)

        await asyncio.sleep(5)
        try:
            await msg.delete()
        except discord.HTTPException:
            pass

    # ── Slowmode ──────────────────────────────────────────────────────────────

    @commands.command(name='slowmode', aliases=['slow'], description='Set channel slowmode in seconds (0 to disable)')
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: int):
        if seconds < 0 or seconds > 21600:
            await ctx.send(embed=discord.Embed(
                description="Slowmode must be between 0 and 21600 seconds (6 hours).",
                color=config.COLORS['error'],
            ))
            return

        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            desc = f"Slowmode disabled in {ctx.channel.mention}."
        else:
            desc = f"Slowmode set to **{seconds}s** in {ctx.channel.mention}."

        await ctx.send(embed=discord.Embed(description=desc, color=config.COLORS['success']))

    # ── Lock ──────────────────────────────────────────────────────────────────

    @commands.command(name='lock', description='Lock a channel — prevents @everyone from sending')
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None, *, reason: str = None):
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)

        embed = discord.Embed(
            title="\U0001f512 Channel Locked",
            description=f"{ch.mention} has been locked.\n**Reason:** {reason or 'No reason provided'}",
            color=MOD_COLORS['lock'],
        )
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

    # ── Unlock ────────────────────────────────────────────────────────────────

    @commands.command(name='unlock', description='Unlock a channel')
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None, *, reason: str = None):
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None  # Reset to inherit
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)

        embed = discord.Embed(
            title="\U0001f513 Channel Unlocked",
            description=f"{ch.mention} has been unlocked.\n**Reason:** {reason or 'No reason provided'}",
            color=MOD_COLORS['unlock'],
        )
        await ctx.send(embed=embed)
        await _send_log(self.bot, ctx.guild.id, embed)

    # ── Add Role ──────────────────────────────────────────────────────────────

    @commands.command(name='addrole', aliases=['giverole'], description='Give a role to a member')
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def addrole(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send(embed=discord.Embed(description="That role is above my highest role.", color=config.COLORS['error']))
            return
        if role in member.roles:
            await ctx.send(embed=discord.Embed(
                description=f"{member.mention} already has {role.mention}.",
                color=config.COLORS['warning'],
            ))
            return

        await member.add_roles(role, reason=f"Added by {ctx.author}")
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Added {role.mention} to {member.mention}.",
            color=config.COLORS['success'],
        ))

    # ── Remove Role ───────────────────────────────────────────────────────────

    @commands.command(name='removerole', aliases=['takerole'], description='Remove a role from a member')
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def removerole(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send(embed=discord.Embed(description="That role is above my highest role.", color=config.COLORS['error']))
            return
        if role not in member.roles:
            await ctx.send(embed=discord.Embed(
                description=f"{member.mention} doesn't have {role.mention}.",
                color=config.COLORS['warning'],
            ))
            return

        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Removed {role.mention} from {member.mention}.",
            color=config.COLORS['success'],
        ))

    # ── Nick ──────────────────────────────────────────────────────────────────

    @commands.command(name='nick', aliases=['nickname'], description='Change a member\'s nickname')
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str = None):
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(embed=discord.Embed(description="You can't change the nickname of someone with an equal or higher role.", color=config.COLORS['error']))
            return

        old = member.display_name
        await member.edit(nick=nickname, reason=f"Changed by {ctx.author}")
        new = nickname or member.name
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Changed **{old}** → **{new}**",
            color=config.COLORS['success'],
        ))

    # ── Mod Log ───────────────────────────────────────────────────────────────

    @commands.command(name='modlog', aliases=['cases'], description='View recent mod cases for a user')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def modlog(self, ctx: commands.Context, member: discord.Member = None, limit: int = 5):
        limit = max(1, min(limit, 20))

        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if member:
                async with db.execute(
                    "SELECT * FROM mod_cases WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (ctx.guild.id, member.id, limit)
                ) as cur:
                    rows = await cur.fetchall()
                title = f"Mod Cases — {member.display_name}"
            else:
                async with db.execute(
                    "SELECT * FROM mod_cases WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
                    (ctx.guild.id, limit)
                ) as cur:
                    rows = await cur.fetchall()
                title = f"Recent Mod Cases — {ctx.guild.name}"

        if not rows:
            await ctx.send(embed=discord.Embed(
                description="No mod cases found.",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title=title, color=config.COLORS['primary'])
        action_emoji = {
            'warn': '\u26a0\ufe0f', 'kick': '\U0001f462', 'ban': '\U0001f6ab',
            'unban': '\u2705', 'timeout': '\U0001f507', 'untimeout': '\U0001f50a',
        }
        for row in rows:
            user = ctx.guild.get_member(row['user_id'])
            user_str = user.display_name if user else f"ID:{row['user_id']}"
            mod = ctx.guild.get_member(row['moderator_id'])
            mod_str = mod.display_name if mod else f"ID:{row['moderator_id']}"
            emoji = action_emoji.get(row['action'], '\U0001f6e1\ufe0f')
            ts = row['created_at'][:10]
            val = f"**User:** {user_str}\n**By:** {mod_str}\n**Reason:** {row['reason'] or 'None'}"
            if row['duration']:
                val += f"\n**Duration:** {row['duration']}"
            embed.add_field(
                name=f"{emoji} Case #{row['id']} — {row['action'].capitalize()} ({ts})",
                value=val,
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── Set Mod Log Channel ───────────────────────────────────────────────────

    @commands.command(name='setmodlog', description='Set the channel for mod action logs')
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setmodlog(self, ctx: commands.Context, channel: discord.TextChannel):
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mod_settings (guild_id, log_channel_id) VALUES (?, ?)",
                (ctx.guild.id, channel.id)
            )
            await db.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Mod log channel set to {channel.mention}.",
            color=config.COLORS['success'],
        ))

    # ── Moderation Info ───────────────────────────────────────────────────────

    @commands.command(name='modinfo', description='View moderation statistics for the server')
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def modinfo(self, ctx: commands.Context):
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT action, COUNT(*) as cnt FROM mod_cases WHERE guild_id = ? GROUP BY action",
                (ctx.guild.id,)
            ) as cur:
                rows = await cur.fetchall()

            async with db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM mod_cases WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cur:
                unique_users = (await cur.fetchone())[0]

        log_ch = await _get_log_channel(self.bot, ctx.guild.id)

        embed = discord.Embed(
            title=f"\U0001f6e1\ufe0f Moderation Info — {ctx.guild.name}",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Unique Users Actioned", value=f"`{unique_users}`", inline=True)
        embed.add_field(name="Mod Log Channel", value=log_ch.mention if log_ch else "*Not set* — use `t!setmodlog`", inline=True)

        action_emoji = {
            'warn': '\u26a0\ufe0f', 'kick': '\U0001f462', 'ban': '\U0001f6ab',
            'unban': '\u2705', 'timeout': '\U0001f507',
        }
        for row in rows:
            emoji = action_emoji.get(row['action'], '\U0001f6e1\ufe0f')
            embed.add_field(name=f"{emoji} {row['action'].capitalize()}s", value=f"`{row['cnt']}`", inline=True)

        embed.set_footer(text="Use t!modlog to view individual cases")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await _init_mod_tables()
    await bot.add_cog(Moderation(bot))
