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
from reply_utils import send_reply

logger = logging.getLogger('tainment.server_settings')

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
                leaderboard_channel INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add leaderboard_channel column if missing
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN leaderboard_channel INTEGER")
            await db.commit()
        except Exception:
            pass  # Column already exists
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

    @commands.command(name='prefix', description='View or set the server command prefix')
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
            await send_reply(ctx, embed=discord.Embed(
                description="You need **Manage Server** permission to change the prefix.",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        if len(new_prefix) > 5:
            await send_reply(ctx, embed=discord.Embed(
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

    @commands.command(name='togglecmd', description='Enable or disable a command in this server/channel')
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
            await send_reply(ctx, embed=discord.Embed(
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

    @commands.command(name='cmdlist', description='Show which commands are toggled in this server')
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

    @commands.command(name='afk', description='Set your AFK status')
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

    @commands.command(name='addemote', description='Add a custom emoji to the server')
    @commands.guild_only()
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def addemote(self, ctx: commands.Context, name: str, url: str = None):
        # Validate name
        if not re.match(r'^[a-zA-Z0-9_]{2,32}$', name):
            await send_reply(ctx, embed=discord.Embed(
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
                await send_reply(ctx, embed=discord.Embed(
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
                            await send_reply(ctx, embed=discord.Embed(
                                description="Could not download image from that URL.",
                                color=config.COLORS['error'],
                            ), ephemeral=True)
                            return
                        image_bytes = await resp.read()
            except Exception:
                await send_reply(ctx, embed=discord.Embed(
                    description="Failed to download image. Make sure the URL is a direct image link.",
                    color=config.COLORS['error'],
                ), ephemeral=True)
                return
        else:
            await send_reply(ctx, embed=discord.Embed(
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
            await send_reply(ctx, embed=discord.Embed(
                description=f"Failed to add emoji: {e}",
                color=config.COLORS['error'],
            ), ephemeral=True)

    # ── Random Color ──────────────────────────────────────────────────────────

    @commands.command(name='randomcolor', description='Generate a random color with preview')
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

    @commands.command(name='membercount', description='Get the server member count')
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

    @commands.command(name='servertier', description='View the server subscription tier and features')
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
                'Economy, fun, games, fishing, music',
                'Basic mod tools: purge (10), slowmode, lock/unlock, nick',
                'No warn/kick/ban/timeout — upgrade for full moderation',
            ]),
            'Basic': ('$7.99/mo', 0x3498db, [
                'All Free features',
                'Full moderation (warn, kick, ban, timeout, audit log)',
                'AutoMod configuration',
                'Welcome messages & custom log channel',
                '15% off user subscriptions for all members',
            ]),
            'Pro': ('$14.99/mo', 0xe040fb, [
                'All Basic features',
                '30% off user subscriptions for all members',
                'Server-wide XP multiplier',
                'Advanced audit log + server analytics',
                'Custom level roles',
                'Priority support',
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

    @commands.command(name='serversubscribe', aliases=['serversub', 'serverupgrade'], description='View or upgrade the server subscription plan')
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
                "• Economy, fun, games, fishing, music\n"
                "• Basic mod: purge (10 msgs), slowmode, lock/unlock, nick\n"
                "• No warn / kick / ban / timeout"
            ),
            inline=False,
        )
        embed.add_field(
            name="Basic — $7.99/mo",
            value=(
                "• All Free features\n"
                "• Full moderation (warn, kick, ban, timeout, up to 100 purge)\n"
                "• AutoMod configuration\n"
                "• Custom log channel & welcome messages\n"
                "• 15% off user subscriptions for all members"
            ),
            inline=False,
        )
        embed.add_field(
            name="Pro — $14.99/mo",
            value=(
                "• All Basic features\n"
                "• 30% off user subscriptions for all members\n"
                "• Server-wide XP multiplier\n"
                "• Advanced audit log & server analytics\n"
                "• Custom level roles\n"
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

    @commands.command(name='setbirthdaychannel', description='Set the channel for birthday announcements')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_birthday_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await update_server_setting(ctx.guild.id, birthday_channel=channel.id)
        embed = discord.Embed(
            description=f"Birthday announcements will be posted in {channel.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='setlevelupchannel', description='Set the channel for level-up announcements')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_levelup_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await update_server_setting(ctx.guild.id, levelup_channel=channel.id)
        embed = discord.Embed(
            description=f"Level-up announcements will be posted in {channel.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='setleaderboard', description='Set the dedicated leaderboard channel')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_leaderboard_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await update_server_setting(ctx.guild.id, leaderboard_channel=channel.id)
        embed = discord.Embed(
            description=f"Live leaderboard will be posted and kept updated in {channel.mention}.",
            color=config.COLORS['success'],
        )
        embed.set_footer(text="The bot will post and auto-update the leaderboard there every 5 minutes.")
        await ctx.send(embed=embed)

    @commands.command(name='clearleaderboard', description='Remove the dedicated leaderboard channel')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def clear_leaderboard_channel(self, ctx: commands.Context):
        await update_server_setting(ctx.guild.id, leaderboard_channel=None)
        await ctx.send(embed=discord.Embed(
            description="Leaderboard channel cleared. The auto-leaderboard is now disabled.",
            color=config.COLORS['success'],
        ))

    @commands.command(
        name='setupserver',
        aliases=['createserver', 'serverbootstrap'],
        description='Create the standard Tainment+ roles, channels, permissions, and genre panel',
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True, manage_messages=True)
    async def setup_server(self, ctx: commands.Context):
        progress = await ctx.send(embed=discord.Embed(
            title="Running Server Setup",
            description="Creating missing roles, channels, permissions, and bot panels.",
            color=config.COLORS['info'],
        ))
        summary = await _run_server_setup(ctx.guild)
        await update_server_setting(
            ctx.guild.id,
            leaderboard_channel=summary['leaderboard_channel_id'],
        )

        lines = [
            f"Roles created: `{summary['roles_created']}`",
            f"Categories created: `{summary['categories_created']}`",
            f"Channels created: `{summary['channels_created']}`",
            f"Starter messages posted: `{summary['messages_posted']}`",
            f"Genre panel refreshed: `{summary['genre_panel_refreshed']}`",
            f"Leaderboard channel linked: {summary['leaderboard_channel_mention']}",
        ]
        if summary['warnings']:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in summary['warnings'][:6])

        await progress.edit(embed=discord.Embed(
            title="Server Setup Complete",
            description="\n".join(lines),
            color=config.COLORS['success'],
        ))

    @commands.command(name='botsetup', description='View bot configuration status for this server')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def botsetup(self, ctx: commands.Context):
        import database as db
        settings = await get_server_settings(ctx.guild.id)
        guild = ctx.guild

        def ch(channel_id):
            if not channel_id:
                return None
            return guild.get_channel(channel_id)

        def status(channel_id, label, cmd):
            c = ch(channel_id)
            if c:
                return f"✅ **{label}** → {c.mention}"
            return f"❌ **{label}** — not set → `{cmd}`"

        # Check reaction role panel
        stored = await db.get_bot_message(guild.id, 'genre_roles')
        genre_panel = "✅ **Genre lane panel** → active" if stored else "❌ **Genre lane panel** — not set up → `t!setupgenreroles`"

        # Check server tier
        tier = settings['server_tier'] if settings else 'Free'
        tier_line = f"🏷️ **Server tier:** `{tier}` — upgrade with `t!serversubscribe`" if tier == 'Free' else f"✅ **Server tier:** `{tier}`"

        lines = [
            "**Channel Setup**",
            status(settings['birthday_channel'] if settings else None, "Birthday announcements", "t!setbirthdaychannel #channel"),
            status(settings['levelup_channel'] if settings else None, "Level-up announcements", "t!setlevelupchannel #channel"),
            status(settings['log_channel'] if settings else None, "Mod log", "t!setmodlog #channel"),
            status(settings['leaderboard_channel'] if settings else None, "Live leaderboard", "t!setleaderboard #channel"),
            "",
            "**Features**",
            genre_panel,
            "",
            "**Subscription**",
            tier_line,
        ]

        embed = discord.Embed(
            title="⚙️ Bot Setup Status",
            description="\n".join(lines),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text="Run each command above to complete setup | t!help for all commands")
        await ctx.send(embed=embed)


# ── Level role auto-creation ──────────────────────────────────────────────────

def _slugify(name: str) -> str:
    ascii_only = ''.join(c for c in name if ord(c) < 128)
    return re.sub(r'[^a-z0-9]+', '-', ascii_only.lower()).strip('-')


def _find_text_channel(guild: discord.Guild, target_name: str) -> discord.TextChannel | None:
    target_slug = _slugify(target_name)
    for channel in guild.text_channels:
        if channel.name == target_name or _slugify(channel.name) == target_slug:
            return channel
    return None


def _find_category(guild: discord.Guild, target_name: str) -> discord.CategoryChannel | None:
    target_slug = _slugify(target_name)
    for category in guild.categories:
        if category.name == target_name or _slugify(category.name) == target_slug:
            return category
    return None


async def _clear_recent_bot_messages(channel: discord.TextChannel, bot_member: discord.Member):
    try:
        async for message in channel.history(limit=20):
            if message.author.id == bot_member.id:
                await message.delete()
    except discord.HTTPException:
        pass


async def _ensure_genre_panel(guild: discord.Guild, channel: discord.TextChannel, bot_member: discord.Member) -> bool:
    import database as db

    await _clear_recent_bot_messages(channel, bot_member)
    embed = discord.Embed(
        title='\U0001f3b5 Choose Your Genre Lane',
        description=(
            'React below to get your genre role. Unreact to remove it. You can pick multiple!\n\n'
            '\U0001f3a4 **Pop Lane** - Chart-toppers & pop anthems\n'
            '\U0001f3b6 **Hip-Hop Lane** - Rap, trap & hip-hop culture\n'
            '\U0001f3b8 **Rock Lane** - Rock, punk & alternative\n'
            '\U0001f50a **Electronic Lane** - EDM, house, techno & electronic\n'
            '\U0001f3b7 **R&B & Soul Lane** - Smooth R&B and soul\n'
            '\U0001f3b9 **Jazz Lane** - Jazz, blues & smooth sounds\n'
            '\U0001f908 **Country Lane** - Country, folk & Americana\n'
            '\U0001f483 **Latin Lane** - Reggaeton, salsa & Latin pop\n'
            '\U0001f333 **Indie Lane** - Indie rock, indie pop & underground gems\n'
            '\U0001f305 **Lo-Fi Lane** - Lo-fi, chill beats & study music'
        ),
        color=0xe040fb,
    )
    panel = await channel.send(embed=embed)
    for emoji in [
        '\U0001f3a4',
        '\U0001f3b6',
        '\U0001f3b8',
        '\U0001f50a',
        '\U0001f3b7',
        '\U0001f3b9',
        '\U0001f908',
        '\U0001f483',
        '\U0001f333',
        '\U0001f305',
    ]:
        await panel.add_reaction(emoji)
    await db.upsert_bot_message(guild.id, 'genre_roles', channel.id, panel.id)
    return True


async def _run_server_setup(guild: discord.Guild) -> dict:
    me = guild.me
    warnings: list[str] = []
    roles_created = 0
    categories_created = 0
    channels_created = 0
    messages_posted = 0
    genre_panel_refreshed = False

    for name, color, mentionable in SETUP_ROLE_DEFS:
        if not discord.utils.get(guild.roles, name=name):
            try:
                await guild.create_role(
                    name=name,
                    color=discord.Color(color),
                    mentionable=mentionable,
                    reason='Tainment+ server setup',
                )
                roles_created += 1
            except discord.HTTPException as e:
                warnings.append(f"Could not create role '{name}': {e}")

    for name, color in SETUP_GENRE_ROLE_DEFS:
        if not discord.utils.get(guild.roles, name=name):
            try:
                await guild.create_role(
                    name=name,
                    color=discord.Color(color),
                    mentionable=True,
                    reason='Tainment+ genre lane role',
                )
                roles_created += 1
            except discord.HTTPException as e:
                warnings.append(f"Could not create genre role '{name}': {e}")

    await _create_level_roles(guild)

    for category_name, channel_names in SETUP_CATEGORY_CHANNELS.items():
        category = _find_category(guild, category_name)
        if not category:
            try:
                category = await guild.create_category(category_name, reason='Tainment+ server setup')
                categories_created += 1
            except discord.HTTPException as e:
                warnings.append(f"Could not create category '{category_name}': {e}")
                continue

        for channel_name in channel_names:
            channel = _find_text_channel(guild, channel_name)
            if not channel:
                try:
                    channel = await guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        reason='Tainment+ server setup',
                    )
                    channels_created += 1
                except discord.HTTPException as e:
                    warnings.append(f"Could not create channel '{channel_name}': {e}")
                    continue
            elif channel.category_id != category.id:
                try:
                    await channel.edit(category=category, reason='Tainment+ server setup')
                except discord.HTTPException as e:
                    warnings.append(f"Could not move channel '{channel.name}': {e}")

    role_lookup = {role.name: role for role in guild.roles}
    staff_roles = [
        role_lookup.get('\U0001f451 Owner'),
        role_lookup.get('\u26a1 Admin'),
        role_lookup.get('\U0001f6e1\ufe0f Moderator'),
        role_lookup.get('\U0001f3a7 Support'),
    ]
    staff_roles = [role for role in staff_roles if role is not None]

    for channel_name in READ_ONLY_SETUP_CHANNELS:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            continue
        try:
            await channel.set_permissions(
                guild.default_role,
                read_messages=True,
                send_messages=False,
                reason='Tainment+ read-only setup',
            )
            for role in staff_roles:
                await channel.set_permissions(
                    role,
                    read_messages=True,
                    send_messages=True,
                    reason='Tainment+ staff posting access',
                )
        except discord.HTTPException as e:
            warnings.append(f"Could not set read-only permissions for '{channel.name}': {e}")

    for channel_name in STAFF_ONLY_SETUP_CHANNELS:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            continue
        try:
            await channel.set_permissions(
                guild.default_role,
                read_messages=False,
                reason='Tainment+ staff-only setup',
            )
            for role in staff_roles:
                await channel.set_permissions(
                    role,
                    read_messages=True,
                    send_messages=True,
                    reason='Tainment+ staff-only access',
                )
        except discord.HTTPException as e:
            warnings.append(f"Could not set staff permissions for '{channel.name}': {e}")

    pick_your_lane = _find_text_channel(guild, '\U0001f3a4\u2503pick-your-lane')
    if pick_your_lane:
        try:
            await pick_your_lane.set_permissions(
                guild.default_role,
                read_messages=True,
                send_messages=False,
                add_reactions=True,
                reason='Tainment+ genre panel setup',
            )
            await pick_your_lane.set_permissions(
                me,
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                add_reactions=True,
                reason='Tainment+ genre panel setup',
            )
            genre_panel_refreshed = await _ensure_genre_panel(guild, pick_your_lane, me)
        except discord.HTTPException as e:
            warnings.append(f"Could not configure genre panel channel: {e}")

    for channel_name, content in SETUP_STARTER_MESSAGES.items():
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            continue
        try:
            await _clear_recent_bot_messages(channel, me)
            await channel.send(content)
            messages_posted += 1
        except discord.HTTPException as e:
            warnings.append(f"Could not post starter message in '{channel.name}': {e}")

    leaderboard_channel = _find_text_channel(guild, '\U0001f3c6\u2503leaderboards')

    return {
        'roles_created': roles_created,
        'categories_created': categories_created,
        'channels_created': channels_created,
        'messages_posted': messages_posted,
        'genre_panel_refreshed': 'yes' if genre_panel_refreshed else 'no',
        'leaderboard_channel_id': leaderboard_channel.id if leaderboard_channel else None,
        'leaderboard_channel_mention': leaderboard_channel.mention if leaderboard_channel else '`not found`',
        'warnings': warnings,
    }


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
