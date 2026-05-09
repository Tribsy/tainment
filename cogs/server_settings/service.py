"""
cogs/server_settings/service.py — DB helpers + setup orchestrator.

Phase 3c: extracted verbatim from cogs/server_settings/__init__.py.

Public helpers (re-exported by __init__.py for external `from cogs.server_settings
import X` usage by other cogs):
  - get_prefix, set_prefix
  - get_server_settings, ensure_server, update_server_setting
  - is_command_enabled, set_command_toggle
  - get_afk, set_afk, clear_afk
  - get_server_tier

Private helpers used internally:
  - _init_tables, _slugify, _find_text_channel, _find_category,
    _clear_recent_bot_messages, _ensure_genre_panel,
    _run_server_setup, _create_level_roles
"""
import discord
from discord.ext import commands
import aiosqlite
import random
import re
import logging
from datetime import datetime, timezone

import config

from .constants import (
    SETUP_ROLE_DEFS,
    SETUP_GENRE_ROLE_DEFS,
    SETUP_CATEGORY_CHANNELS,
    READ_ONLY_SETUP_CHANNELS,
    STAFF_ONLY_SETUP_CHANNELS,
    SETUP_STARTER_MESSAGES,
)

logger = logging.getLogger("tainment.server_settings.service")


__all__ = [
    "_init_tables",
    "get_prefix",
    "set_prefix",
    "get_server_settings",
    "ensure_server",
    "update_server_setting",
    "is_command_enabled",
    "set_command_toggle",
    "get_afk",
    "set_afk",
    "clear_afk",
    "get_server_tier",
    "_slugify",
    "_find_text_channel",
    "_find_category",
    "_clear_recent_bot_messages",
    "_ensure_genre_panel",
    "_run_server_setup",
    "_create_level_roles",
]


# ─── Function bodies (verbatim from source) ─────────────────────────────────

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
