"""
Server Settings cog — per-server configuration, command toggles, AFK system,
server subscriptions, and utility commands (prefix, addemote, randomcolor,
membercount).
"""

import discord
from discord.ext import commands
import aiosqlite
import random
import re
import logging
from datetime import datetime, timezone
import config

logger = logging.getLogger('tainment.server_settings')

# ── DB helpers ────────────────────────────────────────────────────────────────

async def _init_tables():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id        INTEGER PRIMARY KEY,
                prefix          TEXT    DEFAULT 't!',
                server_tier     TEXT    DEFAULT 'Free',
                tier_expires    TIMESTAMP,
                birthday_channel INTEGER,
                levelup_channel  INTEGER,
                welcome_channel  INTEGER,
                log_channel      INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS command_toggles (
                guild_id     INTEGER,
                channel_id   INTEGER DEFAULT 0,
                command_name TEXT,
                enabled      INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, channel_id, command_name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS afk_status (
                user_id  INTEGER,
                guild_id INTEGER,
                status   TEXT,
                set_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_subscriptions (
                guild_id        INTEGER PRIMARY KEY,
                tier            TEXT    DEFAULT 'Free',
                start_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date        TIMESTAMP,
                transaction_id  TEXT,
                activated_by    INTEGER
            )
        """)
        await db.commit()


async def get_prefix(guild_id: int) -> str:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT prefix FROM server_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 't!'


async def set_prefix(guild_id: int, prefix: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO server_settings (guild_id, prefix)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix
        """, (guild_id, prefix))
        await db.commit()


async def get_server_settings(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM server_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone()


async def ensure_server(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO server_settings (guild_id) VALUES (?)",
            (guild_id,)
        )
        await db.commit()


async def update_server_setting(guild_id: int, **kwargs):
    await ensure_server(guild_id)
    if not kwargs:
        return
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE server_settings SET {fields} WHERE guild_id = ?", values
        )
        await db.commit()


async def is_command_enabled(guild_id: int, channel_id: int, command_name: str) -> bool:
    """Check if a command is enabled (guild-wide first, then channel override)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        # Channel-specific override
        async with db.execute(
            "SELECT enabled FROM command_toggles WHERE guild_id=? AND channel_id=? AND command_name=?",
            (guild_id, channel_id, command_name)
        ) as cur:
            row = await cur.fetchone()
            if row is not None:
                return bool(row[0])
        # Guild-wide setting (channel_id = 0)
        async with db.execute(
            "SELECT enabled FROM command_toggles WHERE guild_id=? AND channel_id=0 AND command_name=?",
            (guild_id, command_name)
        ) as cur:
            row = await cur.fetchone()
            if row is not None:
                return bool(row[0])
    return True  # default: enabled


async def set_command_toggle(guild_id: int, channel_id: int, command_name: str, enabled: bool):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO command_toggles (guild_id, channel_id, command_name, enabled)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, channel_id, command_name) DO UPDATE SET enabled = excluded.enabled
        """, (guild_id, channel_id, command_name, int(enabled)))
        await db.commit()


async def get_afk(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM afk_status WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        ) as cur:
            return await cur.fetchone()


async def set_afk(user_id: int, guild_id: int, status: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO afk_status (user_id, guild_id, status)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET status = excluded.status, set_at = CURRENT_TIMESTAMP
        """, (user_id, guild_id, status))
        await db.commit()


async def clear_afk(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM afk_status WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        await db.commit()


async def get_server_tier(guild_id: int) -> str:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT tier FROM server_subscriptions WHERE guild_id=?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 'Free'


# ── Cog ───────────────────────────────────────────────────────────────────────

class ServerSettings(commands.Cog, name="ServerSettings"):
    """Per-server configuration, AFK system, and utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Listeners ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await ensure_server(guild.id)
        await _create_level_roles(guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Remove AFK if the author sends a message
        afk = await get_afk(message.author.id, message.guild.id)
        if afk and not message.content.startswith(('t!afk', '/afk')):
            await clear_afk(message.author.id, message.guild.id)
            try:
                embed = discord.Embed(
                    description=f"Welcome back {message.author.mention}! Your AFK has been removed.",
                    color=config.COLORS['success'],
                )
                await message.channel.send(embed=embed, delete_after=5)
            except discord.HTTPException:
                pass

        # Notify if a mentioned user is AFK
        for user in message.mentions:
            if user.bot or user.id == message.author.id:
                continue
            target_afk = await get_afk(user.id, message.guild.id)
            if target_afk:
                ts = int(datetime.fromisoformat(target_afk['set_at']).timestamp()) if target_afk['set_at'] else ''
                desc = f"{user.display_name} is AFK"
                if target_afk['status']:
                    desc += f": *{target_afk['status']}*"
                if ts:
                    desc += f"\n*Set <t:{ts}:R>*"
                embed = discord.Embed(description=desc, color=config.COLORS['warning'])
                try:
                    await message.channel.send(embed=embed, delete_after=8)
                except discord.HTTPException:
                    pass

    # ── Prefix ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='prefix', description='View or set the server command prefix')
    @commands.guild_only()
    async def prefix_cmd(self, ctx: commands.Context, new_prefix: str = None):
        if new_prefix is None:
            current = await get_prefix(ctx.guild.id)
            embed = discord.Embed(
                title="Server Prefix",
                description=f"Current prefix: `{current}`\n\nChange it with `t!prefix <new_prefix>`",
                color=config.COLORS['primary'],
            )
            await ctx.send(embed=embed)
            return

        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send(embed=discord.Embed(
                description="You need **Manage Server** permission to change the prefix.",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        if len(new_prefix) > 5:
            await ctx.send(embed=discord.Embed(
                description="Prefix must be 5 characters or fewer.",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        await set_prefix(ctx.guild.id, new_prefix)
        embed = discord.Embed(
            title="Prefix Updated",
            description=f"Server prefix changed to `{new_prefix}`",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    # ── Toggle command ─────────────────────────────────────────────────────────

    @commands.hybrid_command(name='togglecmd', description='Enable or disable a command in this server/channel')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def togglecmd(
        self,
        ctx: commands.Context,
        command_name: str,
        channel: discord.TextChannel = None,
        enabled: bool = None,
    ):
        target = channel or ctx.channel
        cmd = self.bot.get_command(command_name)
        if not cmd:
            await ctx.send(embed=discord.Embed(
                description=f"Unknown command: `{command_name}`",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        channel_id = target.id if channel else 0
        scope = f"#{target.name}" if channel else "server-wide"

        # Toggle if enabled not specified
        if enabled is None:
            current = await is_command_enabled(ctx.guild.id, target.id, command_name)
            enabled = not current

        await set_command_toggle(ctx.guild.id, channel_id, command_name, enabled)
        state = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            title="Command Toggle",
            description=f"`{command_name}` is now **{state}** {scope}.",
            color=config.COLORS['success'] if enabled else config.COLORS['warning'],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='cmdlist', description='Show which commands are toggled in this server')
    @commands.guild_only()
    async def cmdlist(self, ctx: commands.Context):
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM command_toggles WHERE guild_id=? ORDER BY command_name",
                (ctx.guild.id,)
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await ctx.send(embed=discord.Embed(
                description="No command toggles configured. All commands are enabled by default.",
                color=config.COLORS['info'],
            ))
            return

        lines = []
        for row in rows:
            scope = f"<#{row['channel_id']}>" if row['channel_id'] else "server-wide"
            state = "ON" if row['enabled'] else "OFF"
            lines.append(f"`{row['command_name']}` — **{state}** ({scope})")

        embed = discord.Embed(
            title="Command Toggles",
            description="\n".join(lines),
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)

    # ── AFK ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='afk', description='Set your AFK status')
    @commands.guild_only()
    async def afk(self, ctx: commands.Context, *, status: str = None):
        status = status or "AFK"
        if len(status) > 128:
            status = status[:128]
        await set_afk(ctx.author.id, ctx.guild.id, status)
        embed = discord.Embed(
            description=f"{ctx.author.mention} is now AFK: *{status}*",
            color=config.COLORS['warning'],
        )
        await ctx.send(embed=embed)

    # ── Add emote ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='addemote', description='Add a custom emoji to the server')
    @commands.guild_only()
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def addemote(self, ctx: commands.Context, name: str, url: str = None):
        # Validate name
        if not re.match(r'^[a-zA-Z0-9_]{2,32}$', name):
            await ctx.send(embed=discord.Embed(
                description="Emoji name must be 2-32 characters, letters/numbers/underscores only.",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        # Get image bytes
        image_bytes = None

        # Try attachment first
        if ctx.message.attachments:
            att = ctx.message.attachments[0]
            if not att.content_type or not att.content_type.startswith('image/'):
                await ctx.send(embed=discord.Embed(
                    description="Please attach an image file.",
                    color=config.COLORS['error'],
                ), ephemeral=True)
                return
            image_bytes = await att.read()
        elif url:
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            await ctx.send(embed=discord.Embed(
                                description="Could not download image from that URL.",
                                color=config.COLORS['error'],
                            ), ephemeral=True)
                            return
                        image_bytes = await resp.read()
            except Exception:
                await ctx.send(embed=discord.Embed(
                    description="Failed to download image. Make sure the URL is a direct image link.",
                    color=config.COLORS['error'],
                ), ephemeral=True)
                return
        else:
            await ctx.send(embed=discord.Embed(
                description="Please provide an image URL or attach an image.",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        try:
            emoji = await ctx.guild.create_custom_emoji(name=name, image=image_bytes)
            embed = discord.Embed(
                title="Emoji Added!",
                description=f"Successfully added {emoji} `:{name}:`",
                color=config.COLORS['success'],
            )
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            await ctx.send(embed=discord.Embed(
                description=f"Failed to add emoji: {e}",
                color=config.COLORS['error'],
            ), ephemeral=True)

    # ── Random Color ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name='randomcolor', description='Generate a random color with preview')
    async def randomcolor(self, ctx: commands.Context):
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        int_color = (r << 16) | (g << 8) | b

        embed = discord.Embed(
            title="Random Color",
            color=int_color,
        )
        embed.add_field(name="HEX", value=f"`{hex_color}`", inline=True)
        embed.add_field(name="RGB", value=f"`rgb({r}, {g}, {b})`", inline=True)
        embed.add_field(name="Integer", value=f"`{int_color}`", inline=True)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_color[1:]}/100x100")
        await ctx.send(embed=embed)

    # ── Member Count ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name='membercount', description='Get the server member count')
    @commands.guild_only()
    async def membercount(self, ctx: commands.Context):
        guild = ctx.guild
        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = total - humans
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)

        embed = discord.Embed(
            title=f"{guild.name} — Member Count",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Total", value=f"`{total:,}`", inline=True)
        embed.add_field(name="Humans", value=f"`{humans:,}`", inline=True)
        embed.add_field(name="Bots", value=f"`{bots:,}`", inline=True)
        embed.add_field(name="Online", value=f"`{online:,}`", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)

    # ── Server subscription info ───────────────────────────────────────────────

    @commands.hybrid_command(name='servertier', description='View the server subscription tier and features')
    @commands.guild_only()
    async def servertier(self, ctx: commands.Context):
        tier = await get_server_tier(ctx.guild.id)
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM server_subscriptions WHERE guild_id=?", (ctx.guild.id,)
            ) as cur:
                sub = await cur.fetchone()

        tiers_info = {
            'Free': ('No subscription', 0x95a5a6, [
                'Basic bot features',
                'Economy, fun, games',
                'No moderation tools',
            ]),
            'Basic': ('$14.99/mo', 0x3498db, [
                'All Free features',
                'Moderation commands (warn, kick, ban, mute)',
                'Auto-moderation',
                'Welcome messages',
                'Custom log channel',
                '15% off user subscriptions for members',
            ]),
            'Pro': ('$23.99/mo', 0xe040fb, [
                'All Basic features',
                '30% off user subscriptions for members',
                'Server XP multiplier',
                'Advanced moderation + audit log',
                'Priority support',
                'Custom level roles',
                'Server analytics',
            ]),
        }

        info = tiers_info.get(tier, tiers_info['Free'])
        embed = discord.Embed(
            title=f"Server Tier — {tier}",
            description=f"Price: **{info[0]}**",
            color=info[1],
        )
        for feat in info[2]:
            embed.add_field(name="\u2705 " + feat, value="\u200b", inline=False)

        if sub and sub['end_date']:
            ts = int(datetime.fromisoformat(sub['end_date']).timestamp())
            embed.add_field(name="Expires", value=f"<t:{ts}:F>", inline=False)

        if tier == 'Free':
            embed.set_footer(text="Upgrade with t!serversubscribe to unlock moderation and more!")
        await ctx.send(embed=embed)

    # ── serversubscribe ───────────────────────────────────────────────────────

    @commands.hybrid_command(name='serversubscribe', aliases=['serversub', 'serverupgrade'], description='View or upgrade the server subscription plan')
    @commands.guild_only()
    async def serversubscribe(self, ctx: commands.Context):
        tier = await get_server_tier(ctx.guild.id)
        embed = discord.Embed(
            title="Server Subscription Plans",
            description=(
                "Upgrade your server to unlock moderation tools, XP multipliers, and member discounts.\n"
                f"**Current tier:** {tier}"
            ),
            color=config.COLORS['primary'],
        )
        embed.add_field(
            name="Free — No cost",
            value=(
                "• Basic bot features\n"
                "• Economy, fun, games\n"
                "• Music system\n"
                "• No server moderation tools"
            ),
            inline=False,
        )
        embed.add_field(
            name="Basic — $14.99/mo",
            value=(
                "• All Free features\n"
                "• Full moderation suite (warn, kick, ban, timeout)\n"
                "• AutoMod integration\n"
                "• Custom log channel\n"
                "• Welcome messages\n"
                "• 15% off user subscriptions for all members"
            ),
            inline=False,
        )
        embed.add_field(
            name="Pro — $23.99/mo",
            value=(
                "• All Basic features\n"
                "• 30% off user subscriptions for all members\n"
                "• Server-wide XP multiplier\n"
                "• Advanced audit log\n"
                "• Custom level roles\n"
                "• Server analytics dashboard\n"
                "• Priority support"
            ),
            inline=False,
        )
        embed.add_field(
            name="How to upgrade",
            value=(
                f"Join our [support server](https://discord.gg/SgkYDqkZmt) and open a ticket, "
                f"or DM an admin to upgrade your server plan."
            ),
            inline=False,
        )
        embed.set_footer(text="Server plans are per-server, separate from user subscriptions.")
        await ctx.send(embed=embed)

    # ── Admin: set server channel settings ────────────────────────────────────

    @commands.hybrid_command(name='setbirthdaychannel', description='Set the channel for birthday announcements')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_birthday_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await update_server_setting(ctx.guild.id, birthday_channel=channel.id)
        embed = discord.Embed(
            description=f"Birthday announcements will be posted in {channel.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='setlevelupchannel', description='Set the channel for level-up announcements')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_levelup_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await update_server_setting(ctx.guild.id, levelup_channel=channel.id)
        embed = discord.Embed(
            description=f"Level-up announcements will be posted in {channel.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)


# ── Level role auto-creation ──────────────────────────────────────────────────

async def _create_level_roles(guild: discord.Guild):
    """Ensure all level milestone roles exist in the guild."""
    if not guild.me.guild_permissions.manage_roles:
        return
    for lvl, (name, color) in config.LEVEL_ROLES.items():
        if not discord.utils.get(guild.roles, name=name):
            try:
                await guild.create_role(
                    name=name,
                    color=discord.Color(color),
                    reason=f'Tainment+ level milestone role (Level {lvl})',
                )
                logger.info(f"Created level role '{name}' in {guild.name}")
            except discord.HTTPException as e:
                logger.warning(f"Could not create role '{name}' in {guild.name}: {e}")


async def setup(bot: commands.Bot):
    await _init_tables()
    await bot.add_cog(ServerSettings(bot))
