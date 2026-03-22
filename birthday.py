"""
Birthday cog — per-server birthday tracking with daily announcements.
Users set their birthday once per server. A background task checks daily
and posts an announcement in the configured channel.
"""

import discord
from discord.ext import commands, tasks
import aiosqlite
import logging
from datetime import datetime, timezone
import config

logger = logging.getLogger('tainment.birthday')


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _init_table():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS birthdays (
                user_id  INTEGER,
                guild_id INTEGER,
                month    INTEGER,
                day      INTEGER,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS birthday_sent (
                user_id  INTEGER,
                guild_id INTEGER,
                year     INTEGER,
                PRIMARY KEY (user_id, guild_id, year)
            )
        """)
        await db.commit()


def _parse_date(date_str: str):
    """Parse MM/DD or MM-DD or DD/MM. Returns (month, day) or raises ValueError."""
    date_str = date_str.strip()
    for sep in ('/', '-', '.'):
        if sep in date_str:
            parts = date_str.split(sep)
            break
    else:
        raise ValueError("Use MM/DD format, e.g. 03/15")

    if len(parts) != 2:
        raise ValueError("Use MM/DD format, e.g. 03/15")

    a, b = int(parts[0]), int(parts[1])

    # Detect DD/MM vs MM/DD heuristically: if a > 12, it must be the day
    if a > 12:
        month, day = b, a
    else:
        month, day = a, b

    # Validate
    if not (1 <= month <= 12):
        raise ValueError("Month must be between 1 and 12")
    max_days = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= day <= max_days[month]):
        raise ValueError(f"Day {day} is invalid for month {month}")

    return month, day


async def set_birthday(user_id: int, guild_id: int, month: int, day: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO birthdays (user_id, guild_id, month, day)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET month = excluded.month, day = excluded.day
        """, (user_id, guild_id, month, day))
        await db.commit()


async def get_birthday(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM birthdays WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        ) as cur:
            return await cur.fetchone()


async def delete_birthday(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM birthdays WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        await db.commit()


async def get_guild_birthdays(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM birthdays WHERE guild_id=? ORDER BY month, day",
            (guild_id,)
        ) as cur:
            return await cur.fetchall()


async def get_todays_birthdays(guild_id: int, month: int, day: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM birthdays WHERE guild_id=? AND month=? AND day=?",
            (guild_id, month, day)
        ) as cur:
            return await cur.fetchall()


async def mark_birthday_sent(user_id: int, guild_id: int, year: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO birthday_sent (user_id, guild_id, year) VALUES (?, ?, ?)",
            (user_id, guild_id, year)
        )
        await db.commit()


async def was_birthday_sent(user_id: int, guild_id: int, year: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM birthday_sent WHERE user_id=? AND guild_id=? AND year=?",
            (user_id, guild_id, year)
        ) as cur:
            return await cur.fetchone() is not None


# ── Cog ───────────────────────────────────────────────────────────────────────

_MONTH_NAMES = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

_BIRTHDAY_MESSAGES = [
    "Wishing you an amazing birthday! May this day be filled with joy!",
    "Hope your day is as special as you are!",
    "Another year of being awesome. Enjoy your day!",
    "Sending you the best birthday vibes!",
    "It's your day to shine! Happy Birthday!",
    "Wishing you all the happiness in the world today!",
    "May your birthday be filled with fun, laughter, and great vibes!",
    "Here's to another incredible year ahead!",
]

import random


class Birthday(commands.Cog, name="Birthday"):
    """Per-server birthday tracking and announcements."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.birthday_check.start()

    def cog_unload(self):
        self.birthday_check.cancel()

    # ── Background task ───────────────────────────────────────────────────────

    @tasks.loop(hours=1)
    async def birthday_check(self):
        now = datetime.now(timezone.utc)
        month, day = now.month, now.day
        year = now.year

        async with aiosqlite.connect(config.DB_PATH) as db:
            # Get all guilds with a birthday channel configured
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT guild_id, birthday_channel FROM server_settings WHERE birthday_channel IS NOT NULL"
            ) as cur:
                guilds = await cur.fetchall()

        for guild_row in guilds:
            guild_id = guild_row['guild_id']
            channel_id = guild_row['birthday_channel']

            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            rows = await get_todays_birthdays(guild_id, month, day)
            for row in rows:
                user_id = row['user_id']
                if await was_birthday_sent(user_id, guild_id, year):
                    continue

                member = guild.get_member(user_id)
                if not member:
                    continue

                msg = random.choice(_BIRTHDAY_MESSAGES)
                embed = discord.Embed(
                    title=f"Happy Birthday, {member.display_name}!",
                    description=f"{member.mention} — {msg}",
                    color=0xfc4f6a,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Tainment+ Birthday Bot | {_MONTH_NAMES[month]} {day}")

                try:
                    await channel.send(embed=embed)
                    await mark_birthday_sent(user_id, guild_id, year)
                    # Give a birthday bonus
                    try:
                        import database as dbm
                        await dbm.ensure_user(user_id, member.name)
                        await dbm.earn_currency(user_id, 'coins', 500)
                        await dbm.earn_currency(user_id, 'gems', 5)
                        await channel.send(
                            f"{member.mention} received a birthday gift: **500 coins** + **5 gems**! :birthday:",
                            delete_after=60,
                        )
                    except Exception:
                        pass
                except discord.HTTPException as e:
                    logger.warning(f"Could not post birthday for {user_id} in {guild_id}: {e}")

    @birthday_check.before_loop
    async def before_birthday_check(self):
        await self.bot.wait_until_ready()

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.group(name='birthday', aliases=['bday'], description='Birthday commands', invoke_without_command=True)
    async def birthday_group(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Birthday Commands",
            description=(
                "`t!birthday set MM/DD` — Set your birthday\n"
                "`t!birthday view [@user]` — View someone's birthday\n"
                "`t!birthday list` — All birthdays in this server\n"
                "`t!birthday del` — Remove your birthday"
            ),
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)

    @birthday_group.command(name='set', description='Set your birthday (MM/DD)')
    @commands.guild_only()
    async def birthday_set(self, ctx: commands.Context, date: str):
        try:
            month, day = _parse_date(date)
        except ValueError as e:
            await ctx.send(embed=discord.Embed(
                description=f"Invalid date: {e}",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        await set_birthday(ctx.author.id, ctx.guild.id, month, day)
        embed = discord.Embed(
            title="Birthday Set!",
            description=(
                f"Your birthday has been set to **{_MONTH_NAMES[month]} {day}** in **{ctx.guild.name}**.\n"
                "You'll receive a birthday bonus when the day arrives!"
            ),
            color=config.COLORS['success'],
        )
        embed.set_footer(text="Birthday announcements require t!setbirthdaychannel to be configured by an admin.")
        await ctx.send(embed=embed, ephemeral=True)

    @birthday_group.command(name='view', description='View your or another user\'s birthday')
    @commands.guild_only()
    async def birthday_view(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        row = await get_birthday(target.id, ctx.guild.id)

        if not row:
            name = "You haven't" if target == ctx.author else f"{target.display_name} hasn't"
            await ctx.send(embed=discord.Embed(
                description=f"{name} set a birthday in this server.",
                color=config.COLORS['warning'],
            ))
            return

        month, day = row['month'], row['day']
        now = datetime.now(timezone.utc)
        # Calculate next birthday
        try:
            next_bday = datetime(now.year, month, day, tzinfo=timezone.utc)
            if next_bday < now:
                next_bday = datetime(now.year + 1, month, day, tzinfo=timezone.utc)
        except ValueError:
            next_bday = None

        embed = discord.Embed(
            title=f"{target.display_name}'s Birthday",
            description=f"**{_MONTH_NAMES[month]} {day}**",
            color=0xfc4f6a,
        )
        if next_bday:
            ts = int(next_bday.timestamp())
            embed.add_field(name="Next Birthday", value=f"<t:{ts}:R>", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @birthday_group.command(name='list', description='View all birthdays in this server')
    @commands.guild_only()
    async def birthday_list(self, ctx: commands.Context):
        rows = await get_guild_birthdays(ctx.guild.id)
        if not rows:
            await ctx.send(embed=discord.Embed(
                description="No birthdays set in this server yet.",
                color=config.COLORS['warning'],
            ))
            return

        now = datetime.now(timezone.utc)
        entries = []
        for row in rows:
            member = ctx.guild.get_member(row['user_id'])
            if not member:
                continue
            m, d = row['month'], row['day']
            # Days until
            try:
                bday = datetime(now.year, m, d, tzinfo=timezone.utc)
                if bday < now:
                    bday = datetime(now.year + 1, m, d, tzinfo=timezone.utc)
                days_left = (bday.date() - now.date()).days
            except ValueError:
                days_left = 999
            entries.append((days_left, m, d, member.display_name))

        entries.sort()

        lines = []
        for days_left, m, d, name in entries[:25]:
            if days_left == 0:
                note = " — **TODAY!** :birthday:"
            elif days_left == 1:
                note = " — tomorrow!"
            else:
                note = f" — in {days_left} days"
            lines.append(f"**{_MONTH_NAMES[m]} {d}** — {name}{note}")

        embed = discord.Embed(
            title=f"Birthdays in {ctx.guild.name}",
            description="\n".join(lines),
            color=0xfc4f6a,
        )
        embed.set_footer(text=f"{len(entries)} birthdays registered")
        await ctx.send(embed=embed)

    @birthday_group.command(name='del', description='Remove your birthday from this server')
    @commands.guild_only()
    async def birthday_del(self, ctx: commands.Context):
        existing = await get_birthday(ctx.author.id, ctx.guild.id)
        if not existing:
            await ctx.send(embed=discord.Embed(
                description="You don't have a birthday set in this server.",
                color=config.COLORS['warning'],
            ), ephemeral=True)
            return
        await delete_birthday(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=discord.Embed(
            description="Your birthday has been removed from this server.",
            color=config.COLORS['success'],
        ), ephemeral=True)


async def setup(bot: commands.Bot):
    await _init_table()
    await bot.add_cog(Birthday(bot))
