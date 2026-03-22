"""
AutoMod cog.
Commands (all require Manage Guild):
  automod status             — view current settings
  automod enable/disable     — toggle automod on/off
  automod log #channel       — set log channel
  automod action <warn|timeout|kick> — set action on violation
  automod spam <count> <seconds> — set spam threshold
  automod links <on|off>     — toggle link filter
  automod allowlink <domain> — whitelist a domain
  automod removelink <domain>
  automod caps <1-100>       — % caps threshold (0 = off)
  automod mentions <count>   — max mentions per message (0 = off)
  automod word add <word>    — add a banned word/phrase
  automod word remove <word> — remove a banned word
  automod word list          — list banned words
"""

import discord
from discord.ext import commands
import aiosqlite
import asyncio
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import config
from server_settings import get_server_tier


# Per-guild spam tracking: {guild_id: {user_id: [timestamps]}}
_spam_tracker: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))


async def _init_automod_tables():
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS automod_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                log_channel_id INTEGER,
                action TEXT DEFAULT 'warn',
                spam_count INTEGER DEFAULT 5,
                spam_window INTEGER DEFAULT 5,
                links_enabled INTEGER DEFAULT 0,
                caps_threshold INTEGER DEFAULT 0,
                mentions_max INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS automod_wordlist (
                guild_id INTEGER,
                word TEXT,
                PRIMARY KEY (guild_id, word)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS automod_allowlist (
                guild_id INTEGER,
                domain TEXT,
                PRIMARY KEY (guild_id, domain)
            )
        """)
        await conn.commit()


async def _get_settings(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone()


async def _ensure_settings(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO automod_settings (guild_id) VALUES (?)", (guild_id,)
        )
        await conn.commit()


async def _update_setting(guild_id: int, **kwargs):
    await _ensure_settings(guild_id)
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(f"UPDATE automod_settings SET {fields} WHERE guild_id = ?", values)
        await conn.commit()


async def _get_wordlist(guild_id: int) -> list[str]:
    async with aiosqlite.connect(config.DB_PATH) as conn:
        async with conn.execute(
            "SELECT word FROM automod_wordlist WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def _get_allowlist(guild_id: int) -> list[str]:
    async with aiosqlite.connect(config.DB_PATH) as conn:
        async with conn.execute(
            "SELECT domain FROM automod_allowlist WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def _send_log(bot: commands.Bot, guild_id: int, log_ch_id: int, embed: discord.Embed):
    if not log_ch_id:
        return
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    ch = guild.get_channel(log_ch_id)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


async def _take_action(bot: commands.Bot, member: discord.Member, settings, reason: str):
    action = settings['action'] if settings else 'warn'
    try:
        if action == 'timeout':
            until = datetime.now(timezone.utc) + timedelta(minutes=5)
            await member.timeout(until, reason=f"AutoMod: {reason}")
        elif action == 'kick':
            await member.kick(reason=f"AutoMod: {reason}")
        # warn = no extra action beyond delete + log
    except discord.HTTPException:
        pass


class AutoMod(commands.Cog, name="AutoMod"):
    """Automatic moderation for spam, links, banned words, and more."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """All AutoMod config commands require a Basic or Pro server subscription."""
        if not ctx.guild:
            return False
        tier = await get_server_tier(ctx.guild.id)
        if tier == 'Free':
            await ctx.send(embed=discord.Embed(
                title="Server Plan Required",
                description=(
                    "AutoMod configuration requires a **Basic** or **Pro** server subscription.\n\n"
                    "Use `t!serversubscribe` to view plans and upgrade."
                ),
                color=config.COLORS['warning'],
            ))
            return False
        return True

    # ── on_message listener ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        # Skip admins/manage_messages
        if message.author.guild_permissions.manage_messages:
            return

        settings = await _get_settings(message.guild.id)
        if not settings or not settings['enabled']:
            return

        content = message.content
        violations = []

        # 1. Banned word filter
        wordlist = await _get_wordlist(message.guild.id)
        content_lower = content.lower()
        for word in wordlist:
            if word.lower() in content_lower:
                violations.append(f"Banned word: `{word}`")
                break

        # 2. Link filter
        if settings['links_enabled'] and not violations:
            url_pattern = re.compile(r'https?://\S+|discord\.gg/\S+', re.IGNORECASE)
            urls = url_pattern.findall(content)
            if urls:
                allowlist = await _get_allowlist(message.guild.id)
                for url in urls:
                    # Extract domain
                    domain_match = re.search(r'https?://([^/\s]+)', url)
                    domain = domain_match.group(1).lower() if domain_match else ''
                    if not any(allowed in domain for allowed in allowlist):
                        violations.append("Unauthorized link")
                        break

        # 3. Caps filter
        if settings['caps_threshold'] and not violations:
            threshold = settings['caps_threshold']
            letters = [c for c in content if c.isalpha()]
            if len(letters) >= 10:
                caps_pct = sum(1 for c in letters if c.isupper()) / len(letters) * 100
                if caps_pct >= threshold:
                    violations.append(f"Excessive caps ({int(caps_pct)}%)")

        # 4. Mass mention filter
        if settings['mentions_max'] and not violations:
            mention_count = len(message.mentions) + len(message.role_mentions)
            if mention_count > settings['mentions_max']:
                violations.append(f"Mass mentions ({mention_count})")

        # 5. Spam filter
        if settings['spam_count'] and not violations:
            now = datetime.now(timezone.utc).timestamp()
            window = settings['spam_window']
            count = settings['spam_count']
            tracker = _spam_tracker[message.guild.id][message.author.id]
            tracker.append(now)
            # Prune old entries
            _spam_tracker[message.guild.id][message.author.id] = [
                t for t in tracker if now - t <= window
            ]
            if len(_spam_tracker[message.guild.id][message.author.id]) >= count:
                violations.append(f"Spam ({count} messages in {window}s)")
                # Clear tracker to avoid repeated triggers
                _spam_tracker[message.guild.id][message.author.id] = []

        if not violations:
            return

        reason = violations[0]

        # Delete the message
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        # Notify in channel (delete after 8s)
        try:
            warn_msg = await message.channel.send(
                embed=discord.Embed(
                    description=f"\U0001f6ab {message.author.mention} — **AutoMod:** {reason}",
                    color=config.COLORS['error'],
                ),
                delete_after=8,
            )
        except discord.HTTPException:
            pass

        # Take action
        await _take_action(self.bot, message.author, settings, reason)

        # Log
        log_embed = discord.Embed(
            title="\U0001f916 AutoMod Action",
            color=config.COLORS['error'],
            timestamp=datetime.now(timezone.utc),
        )
        log_embed.add_field(name="User", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        log_embed.add_field(name="Violation", value=reason, inline=True)
        log_embed.add_field(name="Action", value=(settings['action'] or 'warn').capitalize(), inline=True)
        if content:
            log_embed.add_field(name="Message", value=f"```{content[:200]}```", inline=False)
        log_embed.set_thumbnail(url=message.author.display_avatar.url)

        await _send_log(self.bot, message.guild.id, settings['log_channel_id'], log_embed)

    # ── automod group ─────────────────────────────────────────────────────────

    @commands.group(name='automod', aliases=['am'], description='AutoMod configuration (Manage Server)')
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def automod(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.automod_status)

    @automod.command(name='status', description='View current AutoMod settings')
    async def automod_status(self, ctx: commands.Context):
        await _ensure_settings(ctx.guild.id)
        settings = await _get_settings(ctx.guild.id)
        wordlist = await _get_wordlist(ctx.guild.id)
        allowlist = await _get_allowlist(ctx.guild.id)

        status = "\U0001f7e2 Enabled" if settings['enabled'] else "\U0001f534 Disabled"
        log_ch = ctx.guild.get_channel(settings['log_channel_id']) if settings['log_channel_id'] else None

        embed = discord.Embed(
            title=f"\U0001f916 AutoMod Settings — {ctx.guild.name}",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Action", value=(settings['action'] or 'warn').capitalize(), inline=True)
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "*Not set*", inline=True)
        embed.add_field(
            name="Spam Filter",
            value=f"`{settings['spam_count']}` messages in `{settings['spam_window']}s`",
            inline=True,
        )
        embed.add_field(
            name="Link Filter",
            value="\U0001f7e2 On" if settings['links_enabled'] else "\U0001f534 Off",
            inline=True,
        )
        embed.add_field(
            name="Caps Filter",
            value=f"`{settings['caps_threshold']}%`" if settings['caps_threshold'] else "\U0001f534 Off",
            inline=True,
        )
        embed.add_field(
            name="Mention Limit",
            value=f"`{settings['mentions_max']}` max" if settings['mentions_max'] else "\U0001f534 Off",
            inline=True,
        )
        embed.add_field(
            name=f"Banned Words ({len(wordlist)})",
            value=', '.join(f"`{w}`" for w in wordlist[:10]) + ('...' if len(wordlist) > 10 else '') if wordlist else "*None*",
            inline=False,
        )
        embed.add_field(
            name=f"Allowed Domains ({len(allowlist)})",
            value=', '.join(f"`{d}`" for d in allowlist) if allowlist else "*None*",
            inline=False,
        )
        embed.set_footer(text="t!automod enable/disable | t!automod word add <word>")
        await ctx.send(embed=embed)

    @automod.command(name='enable', description='Enable AutoMod')
    async def automod_enable(self, ctx: commands.Context):
        await _update_setting(ctx.guild.id, enabled=1)
        await ctx.send(embed=discord.Embed(
            description="\U0001f7e2 AutoMod **enabled**. Set a log channel with `t!automod log #channel`.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='disable', description='Disable AutoMod')
    async def automod_disable(self, ctx: commands.Context):
        await _update_setting(ctx.guild.id, enabled=0)
        await ctx.send(embed=discord.Embed(
            description="\U0001f534 AutoMod **disabled**.",
            color=config.COLORS['warning'],
        ))

    @automod.command(name='log', description='Set AutoMod log channel')
    async def automod_log(self, ctx: commands.Context, channel: discord.TextChannel):
        await _update_setting(ctx.guild.id, log_channel_id=channel.id)
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 AutoMod log channel set to {channel.mention}.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='action', description='Set action on violation: warn, timeout, kick')
    async def automod_action(self, ctx: commands.Context, action: str):
        action = action.lower()
        if action not in ('warn', 'timeout', 'kick'):
            await ctx.send(embed=discord.Embed(
                description="Valid actions: `warn`, `timeout`, `kick`",
                color=config.COLORS['error'],
            ))
            return
        await _update_setting(ctx.guild.id, action=action)
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 AutoMod action set to **{action}**.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='spam', description='Set spam threshold (e.g. 5 messages in 5 seconds)')
    async def automod_spam(self, ctx: commands.Context, count: int, seconds: int):
        if count < 2 or count > 20:
            await ctx.send(embed=discord.Embed(description="Count must be 2–20.", color=config.COLORS['error']))
            return
        if seconds < 2 or seconds > 30:
            await ctx.send(embed=discord.Embed(description="Window must be 2–30 seconds.", color=config.COLORS['error']))
            return
        await _update_setting(ctx.guild.id, spam_count=count, spam_window=seconds)
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Spam filter: **{count}** messages in **{seconds}s** triggers action.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='links', description='Toggle link filter on/off')
    async def automod_links(self, ctx: commands.Context, toggle: str):
        toggle = toggle.lower()
        if toggle not in ('on', 'off', 'enable', 'disable', '1', '0'):
            await ctx.send(embed=discord.Embed(description="Use `on` or `off`.", color=config.COLORS['error']))
            return
        val = 1 if toggle in ('on', 'enable', '1') else 0
        await _update_setting(ctx.guild.id, links_enabled=val)
        state = "enabled" if val else "disabled"
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Link filter **{state}**. Whitelist domains with `t!automod allowlink <domain>`.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='allowlink', description='Whitelist a domain from the link filter')
    async def automod_allowlink(self, ctx: commands.Context, domain: str):
        domain = domain.lower().strip().lstrip('https://').lstrip('http://').split('/')[0]
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO automod_allowlist (guild_id, domain) VALUES (?, ?)",
                (ctx.guild.id, domain)
            )
            await conn.commit()
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 `{domain}` added to the link allowlist.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='removelink', description='Remove a domain from the link allowlist')
    async def automod_removelink(self, ctx: commands.Context, domain: str):
        domain = domain.lower().strip()
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                "DELETE FROM automod_allowlist WHERE guild_id = ? AND domain = ?",
                (ctx.guild.id, domain)
            )
            await conn.commit()
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 `{domain}` removed from the allowlist.",
            color=config.COLORS['success'],
        ))

    @automod.command(name='caps', description='Set caps filter threshold % (0 to disable)')
    async def automod_caps(self, ctx: commands.Context, threshold: int):
        if threshold < 0 or threshold > 100:
            await ctx.send(embed=discord.Embed(description="Threshold must be 0–100 (0 = disabled).", color=config.COLORS['error']))
            return
        await _update_setting(ctx.guild.id, caps_threshold=threshold)
        if threshold == 0:
            await ctx.send(embed=discord.Embed(description="\u2705 Caps filter **disabled**.", color=config.COLORS['success']))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"\u2705 Caps filter: messages with **{threshold}%+** uppercase letters will be flagged.",
                color=config.COLORS['success'],
            ))

    @automod.command(name='mentions', description='Set max mentions per message (0 to disable)')
    async def automod_mentions(self, ctx: commands.Context, max_mentions: int):
        if max_mentions < 0 or max_mentions > 50:
            await ctx.send(embed=discord.Embed(description="Limit must be 0–50 (0 = disabled).", color=config.COLORS['error']))
            return
        await _update_setting(ctx.guild.id, mentions_max=max_mentions)
        if max_mentions == 0:
            await ctx.send(embed=discord.Embed(description="\u2705 Mention filter **disabled**.", color=config.COLORS['success']))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"\u2705 Mention filter: messages with **{max_mentions}+** mentions will be flagged.",
                color=config.COLORS['success'],
            ))

    # ── automod word subgroup ─────────────────────────────────────────────────

    @automod.group(name='word', aliases=['words', 'filter'], description='Manage the banned word list')
    async def automod_word(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.automod_word_list)

    @automod_word.command(name='add', description='Add a banned word or phrase')
    async def automod_word_add(self, ctx: commands.Context, *, word: str):
        word = word.lower().strip()
        if len(word) < 2:
            await ctx.send(embed=discord.Embed(description="Word must be at least 2 characters.", color=config.COLORS['error']))
            return
        async with aiosqlite.connect(config.DB_PATH) as conn:
            try:
                await conn.execute(
                    "INSERT INTO automod_wordlist (guild_id, word) VALUES (?, ?)",
                    (ctx.guild.id, word)
                )
                await conn.commit()
                await ctx.send(embed=discord.Embed(
                    description=f"\u2705 `{word}` added to the banned word list.",
                    color=config.COLORS['success'],
                ))
            except Exception:
                await ctx.send(embed=discord.Embed(
                    description=f"`{word}` is already in the banned word list.",
                    color=config.COLORS['warning'],
                ))

    @automod_word.command(name='remove', aliases=['delete', 'del'], description='Remove a banned word')
    async def automod_word_remove(self, ctx: commands.Context, *, word: str):
        word = word.lower().strip()
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                "DELETE FROM automod_wordlist WHERE guild_id = ? AND word = ?",
                (ctx.guild.id, word)
            )
            await conn.commit()
        await ctx.send(embed=discord.Embed(
            description=f"\u2705 `{word}` removed from the banned word list.",
            color=config.COLORS['success'],
        ))

    @automod_word.command(name='list', description='List all banned words')
    async def automod_word_list(self, ctx: commands.Context):
        wordlist = await _get_wordlist(ctx.guild.id)
        if not wordlist:
            await ctx.send(embed=discord.Embed(
                description="No banned words set. Add with `t!automod word add <word>`.",
                color=config.COLORS['warning'],
            ))
            return
        await ctx.send(embed=discord.Embed(
            title=f"\U0001f6ab Banned Words ({len(wordlist)})",
            description=', '.join(f"`{w}`" for w in sorted(wordlist)),
            color=config.COLORS['error'],
        ))

    @automod_word.command(name='clear', description='Clear all banned words')
    @commands.has_permissions(administrator=True)
    async def automod_word_clear(self, ctx: commands.Context):
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute("DELETE FROM automod_wordlist WHERE guild_id = ?", (ctx.guild.id,))
            await conn.commit()
        await ctx.send(embed=discord.Embed(
            description="\u2705 All banned words cleared.",
            color=config.COLORS['success'],
        ))


async def setup(bot: commands.Bot):
    await _init_automod_tables()
    await bot.add_cog(AutoMod(bot))
