"""
Tainment+ Server Setup v2 — Cleanup & Polish
=============================================
- Detects and deletes duplicate channels (plain vs emoji-prefix)
- Renames new plain channels to emoji versions
- Renames plain roles to emoji versions
- Re-applies permissions to canonical channels
- Posts starter messages with live channel mentions

Run: python setup_server.py
"""

import asyncio
import os
import re
import sys
from collections import defaultdict

import discord
from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

TOKEN    = os.getenv('BOT_TOKEN', '')
GUILD_ID = int(os.getenv('MCP_DISCORD_GUILD_ID') or os.getenv('GUILD_ID') or 0)

if not TOKEN:   sys.exit('ERROR: BOT_TOKEN not set in .env')
if not GUILD_ID: sys.exit('ERROR: Set GUILD_ID or MCP_DISCORD_GUILD_ID in .env')

# ── Colour helper ─────────────────────────────────────────────────────────────
def col(h): return discord.Colour(int(h.lstrip('#'), 16))

# ── Channel emoji map  (semantic name → display name with emoji) ──────────────
CHANNEL_EMOJI: dict[str, str] = {
    'welcome':          '👋┃welcome',
    'rules':            '📜┃rules',
    'announcements':    '📢┃announcements',
    'updates':          '📰┃updates',
    'faq':              '❓┃faq',
    'general':          '💬┃general',
    'introductions':    '✨┃introductions',
    'media':            '📸┃media',
    'memes':            '😂┃memes',
    'bot-chat':         '🤖┃bot-chat',
    'suggestions':      '💡┃suggestions',
    'trivia-chat':      '🧠┃trivia-chat',
    'word-games':       '📝┃word-games',
    'economy-chat':     '💰┃economy-chat',
    'leaderboards':     '🏆┃leaderboards',
    'help':             '🆘┃help',
    'bug-reports':      '🐛┃bug-reports',
    'billing-support':  '💳┃billing-support',
    'feature-requests': '⭐┃feature-requests',
    'staff-chat':       '🛡️┃staff-chat',
    'mod-logs':         '📋┃mod-logs',
    'admin-panel':      '⚙️┃admin-panel',
}

# ── Role emoji map  (current name → new name with emoji) ─────────────────────
ROLE_EMOJI: dict[str, str] = {
    'Owner':              '👑 Owner',
    'Admin':              '⚡ Admin',
    'Moderator':          '🛡️ Moderator',
    'Support':            '🎧 Support',
    'Announcements Ping': '📢 Announcements Ping',
    'Events Ping':        '🎉 Events Ping',
    'VIP':                '💎 VIP',
    'Subscriber':         '⭐ Subscriber',
    'Member':             '👤 Member',
    'Muted':              '🔇 Muted',
}

# ── Permissions config ────────────────────────────────────────────────────────
READ_ONLY_CHANNELS    = {'welcome', 'rules', 'announcements', 'updates'}
STAFF_ROLES_POST      = ['👑 Owner', '⚡ Admin', '🛡️ Moderator', '🎧 Support']
STAFF_CHANNEL_ACCESS  = {
    'staff-chat':  ['👑 Owner', '⚡ Admin', '🛡️ Moderator', '🎧 Support'],
    'mod-logs':    ['👑 Owner', '⚡ Admin', '🛡️ Moderator'],
    'admin-panel': ['👑 Owner', '⚡ Admin'],
}

# ── Normaliser ────────────────────────────────────────────────────────────────
def norm(name: str) -> str:
    """Strip emoji + separators, return lowercase alphanumeric-and-hyphen slug."""
    ascii_only = ''.join(c for c in name if ord(c) < 128)
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_only.lower()).strip('-')
    return slug

# ── Logging ───────────────────────────────────────────────────────────────────
def P(*a, **kw):   print(*a, **kw, flush=True)
def ok(m):         P(f"  [OK]      {m}")
def created(m):    P(f"  [CREATED] {m}")
def renamed(m):    P(f"  [RENAMED] {m}")
def deleted(m):    P(f"  [DELETED] {m}")
def skipped(m):    P(f"  [EXISTS]  {m}")
def warn(m):       P(f"  [WARN]    {m}")
def section(t):    P(f"\n{'='*62}\n  {t}\n{'='*62}")

# ── Entry point ───────────────────────────────────────────────────────────────
async def run():
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            await setup(client)
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            await client.close()

    await client.start(TOKEN)


async def setup(client: discord.Client):
    guild = client.get_guild(GUILD_ID)
    if not guild:
        P(f"ERROR: Guild {GUILD_ID} not found.")
        return

    P(f"\nConnected as : {client.user}")
    P(f"Guild        : {guild.name}  (ID: {guild.id})")
    P(f"Members      : {guild.member_count}")

    # ── Phase 0: Inspect ─────────────────────────────────────────────────────
    section("PHASE 0 — INSPECT")

    all_text   = {ch.name: ch for ch in guild.text_channels}
    all_voice  = {ch.name: ch for ch in guild.voice_channels}
    all_roles  = {r.name:  r  for r  in guild.roles}
    all_cats   = {c.name:  c  for c  in guild.categories}

    P("\n  Roles:")
    for r in sorted(all_roles): P(f"    - {r}")

    P("\n  Categories:")
    for c in sorted(all_cats):  P(f"    - {c}")

    P("\n  Text channels:")
    for name in sorted(all_text):
        cat = all_text[name].category
        P(f"    - #{name}  [{cat.name if cat else 'no category'}]")

    P("\n  Voice channels:")
    for name in sorted(all_voice):
        cat = all_voice[name].category
        P(f"    - {name}  [{cat.name if cat else 'no category'}]")

    # Build normalised lookup: norm_slug → [channel, ...]
    norm_map: dict[str, list[discord.TextChannel]] = defaultdict(list)
    for ch in guild.text_channels:
        norm_map[norm(ch.name)].append(ch)

    # Identify duplicates
    P("\n  Duplicate groups (same normalised name):")
    has_dupes = False
    for slug, channels in norm_map.items():
        if len(channels) > 1:
            has_dupes = True
            P(f"    [{slug}] → " + ", ".join(f"#{c.name}" for c in channels))
    if not has_dupes:
        P("    None found.")

    await asyncio.sleep(1)

    # ── Phase 1: Delete duplicate plain-name channels ─────────────────────────
    section("PHASE 1 — DELETE DUPLICATES")

    deleted_names: set[str] = set()
    for slug, channels in norm_map.items():
        if len(channels) < 2:
            continue
        # The "plain" channel (ours from last run) has name == slug or == slug with hyphens
        plain = next((c for c in channels if norm(c.name) == c.name.lower()), None)
        if plain is None:
            # All have emoji prefixes — keep them all, just warn
            warn(f"Multiple emoji channels for '{slug}' — skipping: " +
                 ", ".join(f"#{c.name}" for c in channels))
            continue
        try:
            deleted(f"#{plain.name}  (duplicate of emoji channel)")
            await plain.delete(reason="Tainment+ setup v2: removing plain-name duplicate")
            deleted_names.add(plain.name)
        except discord.Forbidden:
            warn(f"No permission to delete #{plain.name}")
        except Exception as e:
            warn(f"Failed to delete #{plain.name}: {e}")
        await asyncio.sleep(0.5)

    if not deleted_names:
        P("  Nothing to delete.")

    # Refresh channel list after deletions
    all_text  = {ch.name: ch for ch in guild.text_channels}
    all_voice = {ch.name: ch for ch in guild.voice_channels}
    norm_map  = defaultdict(list)
    for ch in guild.text_channels:
        norm_map[norm(ch.name)].append(ch)

    # ── Phase 2: Rename plain-name channels → emoji versions ─────────────────
    section("PHASE 2 — RENAME CHANNELS (add emoji)")

    # Build map: semantic_slug → canonical channel object (post-deletion)
    canonical: dict[str, discord.TextChannel | discord.VoiceChannel] = {}

    for semantic, emoji_name in CHANNEL_EMOJI.items():
        slug = norm(semantic)
        matches = norm_map.get(slug, [])

        if not matches:
            warn(f"Channel '{semantic}' not found — skipping rename")
            continue

        ch = matches[0]  # only one should remain after phase 1

        if ch.name == emoji_name:
            skipped(f"#{ch.name}  already has emoji")
            canonical[semantic] = ch
        elif ch.name == semantic:
            # Plain name — rename it
            try:
                await ch.edit(name=emoji_name, reason="Tainment+ setup v2: add emoji prefix")
                renamed(f"#{semantic}  →  #{emoji_name}")
                canonical[semantic] = ch
            except discord.Forbidden:
                warn(f"No permission to rename #{ch.name}")
                canonical[semantic] = ch
            except Exception as e:
                warn(f"Rename failed for #{ch.name}: {e}")
                canonical[semantic] = ch
        else:
            # Has emoji but different from our target — keep as-is, still register it
            skipped(f"#{ch.name}  keeping existing emoji name (target was '{emoji_name}')")
            canonical[semantic] = ch

        await asyncio.sleep(0.4)

    # Also map voice channels (no emoji rename needed for voice)
    for ch in guild.voice_channels:
        canonical[ch.name] = ch

    # ── Phase 3: Rename roles → emoji versions ────────────────────────────────
    section("PHASE 3 — RENAME ROLES (add emoji)")

    role_map: dict[str, discord.Role] = {r.name: r for r in guild.roles}

    for plain_name, emoji_name in ROLE_EMOJI.items():
        if emoji_name in role_map:
            skipped(f"Role '{emoji_name}'  already has emoji")
            continue
        role = role_map.get(plain_name)
        if not role:
            warn(f"Role '{plain_name}' not found — was it created in the previous run?")
            continue
        try:
            await role.edit(name=emoji_name, reason="Tainment+ setup v2: add emoji prefix")
            renamed(f"Role '{plain_name}'  →  '{emoji_name}'")
        except discord.Forbidden:
            warn(f"No permission to rename role '{plain_name}'")
        except Exception as e:
            warn(f"Rename failed for role '{plain_name}': {e}")
        await asyncio.sleep(0.4)

    # Refresh role map after renames
    role_map = {r.name: r for r in guild.roles}

    # ── Phase 4: Permissions ──────────────────────────────────────────────────
    section("PHASE 4 — PERMISSIONS")

    everyone = guild.default_role

    # Read-only info channels
    for semantic in READ_ONLY_CHANNELS:
        ch = canonical.get(semantic)
        if not ch or not isinstance(ch, discord.TextChannel):
            warn(f"'{semantic}' not in canonical map — skipping")
            continue
        try:
            await ch.set_permissions(everyone, read_messages=True, send_messages=False,
                                     reason="Tainment+ setup v2: read-only")
            ok(f"#{ch.name}  @everyone → read-only")
            for rname in STAFF_ROLES_POST:
                role = role_map.get(rname)
                if role:
                    await ch.set_permissions(role, read_messages=True, send_messages=True,
                                             reason="Tainment+ setup v2: staff can post")
                    ok(f"#{ch.name}  {rname} → can send")
                await asyncio.sleep(0.25)
        except discord.Forbidden:
            warn(f"No permission to set overwrites on #{ch.name}")
        except Exception as e:
            warn(f"Error on #{ch.name}: {e}")
        await asyncio.sleep(0.4)

    # Staff-only channels
    for semantic, allowed_roles in STAFF_CHANNEL_ACCESS.items():
        ch = canonical.get(semantic)
        if not ch or not isinstance(ch, discord.TextChannel):
            warn(f"'{semantic}' not in canonical map — skipping")
            continue
        try:
            await ch.set_permissions(everyone, read_messages=False,
                                     reason="Tainment+ setup v2: hide from everyone")
            ok(f"#{ch.name}  @everyone → hidden")
            for rname in allowed_roles:
                role = role_map.get(rname)
                if role:
                    await ch.set_permissions(role, read_messages=True, send_messages=True,
                                             reason=f"Tainment+ setup v2: {rname} access")
                    ok(f"#{ch.name}  {rname} → visible + can send")
                await asyncio.sleep(0.25)
        except discord.Forbidden:
            warn(f"No permission to set overwrites on #{ch.name}")
        except Exception as e:
            warn(f"Error on #{ch.name}: {e}")
        await asyncio.sleep(0.4)

    # ── Phase 5: Starter messages ─────────────────────────────────────────────
    section("PHASE 5 — STARTER MESSAGES")

    # Resolve live channel mentions (uses actual IDs so links work in Discord)
    def mention(semantic: str) -> str:
        ch = canonical.get(semantic)
        return ch.mention if ch else f"#{semantic}"

    starter: dict[str, str] = {
        'welcome': (
            "**Welcome to Tainment+!**\n\n"
            f"We're glad you're here — your go-to server for entertainment, games, and community.\n\n"
            f"• Read {mention('rules')} before chatting\n"
            f"• Introduce yourself in {mention('introductions')}\n"
            f"• Run bot commands in {mention('bot-chat')} — try `t!help`\n"
            f"• Stay up to date in {mention('announcements')}\n"
            f"• Need help? Head to {mention('help')}\n\n"
            "Enjoy your stay!"
        ),
        'rules': (
            "**Server Rules**\n\n"
            "1. Be respectful — no hate speech, harassment, or discrimination.\n"
            "2. No spam, flooding, or excessive caps.\n"
            "3. Keep content in the correct channels.\n"
            "4. No NSFW content anywhere on this server.\n"
            "5. No unsolicited advertising.\n"
            "6. Follow Discord's Terms of Service at all times.\n"
            "7. Staff decisions are final — appeal in "
            f"{mention('help')} if needed.\n\n"
            "Breaking these rules may result in a mute, kick, or ban."
        ),
        'announcements': (
            "**Tainment+ is live!**\n\n"
            "Welcome to the official Tainment+ Discord server.\n\n"
            f"Watch this channel for bot updates, events, and news.\n"
            f"Post suggestions in {mention('suggestions')}.\n"
            f"Report issues in {mention('bug-reports')}."
        ),
        'bot-chat': (
            "**Bot Commands**\n\n"
            "Run all Tainment+ commands here.\n\n"
            "`t!help` — full command list\n"
            "`t!daily` — claim daily coins 🪙\n"
            "`t!balance` — coins / gems / tokens\n"
            "`t!shop` — browse the three-currency shop\n"
            "`t!profile` — your profile card\n"
            "`t!gamble` / `t!slots` — try your luck\n"
            "`t!ttt` / `t!c4` / `t!mathquiz` — games\n\n"
            f"Check {mention('leaderboards')} to see the top players.\n"
            "Slash commands work too — type `/` to explore."
        ),
    }

    for semantic, content in starter.items():
        ch = canonical.get(semantic)
        if not ch or not isinstance(ch, discord.TextChannel):
            warn(f"#{semantic} not found — skipping message")
            continue

        # Delete any existing messages from this bot
        try:
            async for msg in ch.history(limit=10):
                if msg.author.id == client.user.id:
                    await msg.delete()
                    ok(f"Deleted old bot message in #{ch.name}")
                    await asyncio.sleep(0.3)
        except discord.Forbidden:
            pass

        # Post new message
        try:
            msg = await ch.send(content)
            created(f"Message in #{ch.name}  (ID: {msg.id})")
        except discord.Forbidden:
            warn(f"No permission to post in #{ch.name}")
        except Exception as e:
            warn(f"Error posting in #{ch.name}: {e}")
        await asyncio.sleep(0.5)

    # ── Final summary ─────────────────────────────────────────────────────────
    section("DONE")
    P("\n  Canonical channel map:")
    for sem, ch in sorted(canonical.items()):
        if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
            P(f"    {sem:<20} → #{ch.name}  (ID: {ch.id})")
    P(f"\n  Guild: {guild.name}  |  Members: {guild.member_count}\n")


if __name__ == '__main__':
    asyncio.run(run())
