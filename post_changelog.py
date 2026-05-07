"""
Changelog manager for Tainment+.

Modes:
  python post_changelog.py          → full repost (oldest first, newest last)
  python post_changelog.py --new    → append only the LATEST version as a new message

Full repost clears the bot's old messages and reposts all versions in order.
--new mode just sends the first entry in VERSIONS as a new message at the bottom.
"""

import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN    = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163
NEW_ONLY = '--new' in sys.argv

VERSIONS = [
    (
        'v2.0.0 | July 2025',
        0x7c4dff,
        [
            '\U0001f3a3 **Competitive fishing game**: 18 fish types across 6 tiers. Commands: `t!fish`, `t!fishbag`, `t!sell`, `t!fishstats`, `t!fishtop`.',
            '\U0001f3a3 **Fishing rods in shop**: Silver Rod (1500\U0001fa99), Gold Rod (5000\U0001fa99), Diamond Rod (20\U0001f48e). Each improves catch rates.',
            '\U0001f3c6 **Auto-updating leaderboard**: `#\U0001f3c6┃leaderboards` refreshes every 5 min with top richest, XP, and fishers.',
            '\U0001f331 **XP milestone roles**: Auto-assigned at Lvl 5/10/20/30/50: Newcomer, Groover, Fanatic, Headliner, Icon.',
            '\U0001f464 **Auto Member role on join**: New members automatically receive \U0001f3b5 Listener.',
            '\U0001f41b **Support forms**: Modal forms for bug reports and billing support (buttons in support channels).',
            '\U0001fa99 **Multi-currency economy**: Coins \U0001fa99, Gems \U0001f48e, Tokens \U0001f3ab across all games and the shop.',
            '\U0001f3ae **New games**: Tic-Tac-Toe, Connect Four, Scramble, Math Quiz, Higher/Lower, Duel, Snap.',
            '\U0001f6d2 **Premium shop**: 15+ items across three currency shops.',
            '\U0001f4e3 **Giveaways, polls, reminders**: Full community tools added.',
        ],
    ),
    (
        'v2.0.4 | July 2025',
        0x00e5ff,
        [
            '\U0001f3a3 **Fishing cooldown reduced**: Base 30s → 15s. Silver 30s → 12s. Gold 25s → 10s. Diamond 20s → 7s.',
            '\U0001f4b0 **Gambling display fixed**: Win now clearly shows "Payout: +190 (bet returned + profit)" so it\'s obvious your bet is safe.',
            '\U0001f39b️ **PopFusion role rebrand**: All roles renamed to match the music festival brand:\n'
            ' Owner→\U0001f39b️ Founder • Admin→\U0001f39a️ Producer • Moderator→\U0001f6e1️ Stage Manager • Support→\U0001f399️ Crew\n'
            ' Member→\U0001f3b5 Listener • Subscriber→\U0001f525 Fuser • Announcements Ping→\U0001f4e2 Drop Alerts',
            '\U0001f4b3 **New Vibe tier at $1.99/mo**: All joke/story categories, trivia, 200 daily coins, 1.2x XP.',
            '\U0001f4b8 **Pro tier reduced**: $9.99 → $7.99/mo.',
        ],
    ),
    (
        'v2.1.0 | August 2025',
        0xe040fb,
        [
            '\U0001f4ca **Upvote/Downvote on feature requests**: Community can vote on submitted ideas. Toggle off by clicking again.',
            '\U0001f4cb **#changelog channel**: Dedicated channel for tracking all bot updates (you\'re reading it!).',
            '\U0001f3b5 **Genre lane reaction roles**: `#\U0001f3a4┃pick-your-lane`: react to self-assign genre roles; unreact to remove.',
            '\U0001f4dd **Support forms routed privately**: Bug reports go to staff-only `#mod-logs`; billing requests go to admin-only `#admin-panel`.',
            '⭐ **Feature request form**: `#⭐┃feature-requests` now has a modal form with structured fields.',
            '\U0001f510 **Channel permissions hardened**: `#leaderboards` is bot-only; `#billing-support` restricted to admins.',
            '\U0001f3a4 **4 genre lane roles**: Pop Lane, Hip-Hop Lane, Rock Lane, Electronic Lane (cosmetic).',
            '\U0001f3b5 **4 new voice channels**: Vibe Lounge, Late Night Session, Hangout Spot, Game Night.',
            '\U0001f4dc **#rules redesigned**: 9 professional sections with PopFusion brand styling.',
            '\U0001f4ac **#faq updated**: Covers all tiers, fishing, genre lanes, and support channels.',
        ],
    ),
    (
        'v2.1.8 | September 2025',
        0xe040fb,
        [
            '⌨️ **7 new fun games**: `t!typerace`, `t!riddle`, `t!wouldyourather`, `t!emojidecode`, `t!fastmath`, `t!hotpotato`, `t!wordchain`: all earn coins, gems, or tokens.',
            '\U0001f6e1️ **Full moderation suite**: `t!warn`, `t!kick`, `t!ban`, `t!unban`, `t!timeout`, `t!purge`, `t!slowmode`, `t!lock`, `t!unlock`, `t!addrole`, `t!removerole`, `t!nick`, `t!modlog`, `t!setmodlog`, `t!modinfo`.',
            '\U0001f6d2 **9 new shop items**: Coin Magnet, Premium Bait, Gamble Shield (coins); XP Surge, Prestige Badge, Gem Booster (gems); Typerace Booster, Fish Vacuum, Streak Restore (tokens).',
            '\U0001f4b3 **Shop IDs now visible**: Every shop item shows its exact `t!buy <id>` so you always know what to type.',
            '\U0001f525 **Vibe tier content fixed**: Vibe subscribers now correctly access all joke/story categories, trivia, and get the Vibe badge on their profile.',
            '⏰ **Leaderboard timer updated**: Auto-leaderboard now refreshes every **10 minutes** (was 5).',
            '\U0001f4c4 **Subscription tiers expanded**: Each tier now has clearer, more distinct perks including work bonuses, fishing boosts, and free Lucky Gambles for Premium/Pro.',
            '\U0001f4cb **Help & FAQ refreshed**: `#help` and `#faq` channels updated with all current commands, tiers, and genre lane info.',
        ],
    ),
    (
        'v2.3.0 | November 2025',
        0xe040fb,
        [
            '\U0001f3a3 **2300+ fish across 10 tiers**: Trash / Common / Uncommon / Rare / Epic / Legendary / Mythic / Ancient / Celestial / Void. Each tier requires a specific rod to unlock.',
            '\U0001f3a3 **11 fishing rods**: Silver → Gold → Diamond → Pearl → Crystal → Titanium → Quantum → Obsidian → Cosmic → Void. Higher rods reduce cooldown and unlock rarer tiers.',
            '\U0001fab1 **Premium Bait reworked**: Now grants +40% rare fish chance for **1 hour** (was 10 casts). Purchasable for 800 \U0001fa99.',
            '\U0001f381 **New command: `t!rods`**: View all 11 rods, their tier requirements, prices, and what fish tiers they unlock.',
            '\U0001f382 **Birthday system**: `t!birthday set MM/DD` to register your birthday per server. Daily announcements in your chosen channel + **500 \U0001fa99 + 5 \U0001f48e** birthday gift.',
            '⚙️ **Server Settings cog**: Per-server prefix (`t!prefix`), command toggles per channel (`t!togglecmd`), AFK system (`t!afk`), `t!addemote`, `t!randomcolor`, `t!membercount`, `t!servertier`.',
            '\U0001f6e0️ **Admin economy commands**: `t!setbalance`, `t!addbalance`, `t!removebalance`, `t!reseteconomy` (requires Manage Server / Administrator).',
            '\U0001f3c6 **10 level milestone roles**: Added Superstar (75), Legend (100), Cosmic (150), Immortal (200), Void Walker (300). Auto-created when bot joins a server.',
            '\U0001f9f9 **Shop expanded**: 45+ items total. New: 8 advanced rods, profile banners (5 colors), avatar frames (2 styles), mystery box, piggy bank, fishing magnet, coin surge, rob boost.',
            '\U0001f464 **Profile card upgraded**: Now shows gems, tokens, fishing level, and equipped cosmetics (banner color, avatar frame, Prestige badge).',
        ],
    ),
    (
        'v2.4.0 | December 2025',
        0x00e5ff,
        [
            '\U0001f3b5 **Music discovery system**: `t!recommend`, `t!hotsongs`, `t!genresearch` (Vibe+), `t!moodsearch` (Vibe+), `t!artistinfo` (Premium+), `t!toptracks` (Premium+), `t!newreleases` (Pro).',
            '\U0001f3b6 **Music trivia games**: `t!musictrivia` (button voting, all tiers), `t!lyricsguess` (Vibe+), `t!namethetune` channel race (Vibe+). Win coins, gems, and tokens.',
            '\U0001f464 **Music profiles**: `t!musicprofile`, `t!setgenre`, `t!setartist`. Track your favourite genre, artists, listening streak, and lifetime music earnings.',
            '\U0001f4e4 **Track sharing + hot chart**: `t!sharetrack <song> - <artist>` earns daily coins and feeds the server’s `t!hotsongs` weekly chart.',
            '\U0001f3b5 **Music Wrapped**: `t!musicwrapped` gives you a monthly summary of your top genre, shared tracks, activity count, and earnings (Vibe+).',
            '\U0001f4dc **Playlists**: `t!playlist create/add/view/list/delete`: save and manage personal song playlists. Vibe+ gets 3 slots, Premium 5, Pro unlimited.',
            '\U0001f916 **AutoMod system**: `t!automod enable` to activate. Spam filter, link filter (with domain allowlist), caps %, mass mention limit, and banned word list.',
            '⚙️ **AutoMod actions**: Choose `warn` (default), `timeout` (5 min), or `kick` per violation. All actions logged to your configured `t!automod log #channel`.',
            '\U0001f6d2 **12 new shop items**: Music Hint, Trivia Skip, Hot Boost, Bingo Doubler (coins); Music Fanatic Badge, Streak Amp, Genre Pass, Wrapped Token (gems); DJ Crown, Playlist Slot, Queue Priority, Trivia Surge (tokens).',
        ],
    ),
    (
        'v2.5.0 | February 2026',
        0xe040fb,
        [
            '\U0001f3a3 **Rod equip system**: `t!equip <rod_key>` to manually choose which rod to fish with. `t!unequip` to go back to auto-best. `t!rods` now shows each rod\'s key.',
            '\U0001f3b5 **16 genres in `t!genresearch`**: Added indie, soul, reggae, classical, metal, folk, K-Pop, and lo-fi: each with 12 curated picks.',
            '\U0001f3a4 **10 genre lanes in pick-your-lane**: Added R&B & Soul, Jazz, Country, Latin, Indie, and Lo-Fi reaction role lanes. Run `t!setupgenreroles` to refresh.',
            '\U0001f4ca **Dedicated leaderboard channel**: `t!setleaderboard #channel` pins a live auto-updating leaderboard. `t!clearleaderboard` to remove.',
            '⚙️ **`t!botsetup` command**: Admins can run `t!botsetup` to see a full checklist of what channels are configured and what still needs setting up.',
            '\U0001f6d2 **Shop item fixes**: Gamble Shield is now 24-hour time-based (not permanent). Trivia Skip, Bingo Doubler, and Lucky Gamble now correctly labelled as 1-time use.',
            '\U0001f512 **Free moderation tools**: `t!purge` (up to 10 msgs), `t!slowmode`, `t!lock`, `t!unlock`, and `t!nick` are now available on all servers without a server plan.',
            '\U0001f4b8 **Server plan prices reduced**: Basic $14.99 → $7.99/mo. Pro $23.99 → $14.99/mo.',
            '⏱️ **`t!sharetrack` cooldown**: Reduced from 24 hours to 6 hours.',
            '\U0001f3a8 **`t!color` updated**: Calling with no arguments now shows a random generated color. Pass a hex code to preview a specific one.',
            '\U0001f916 **AutoMod double-message bug fixed**: AutoMod config commands no longer send both a "Server Plan Required" message and execute the command.',
            '\U0001f3c6 **XP milestone roles fixed**: Roles are now auto-created and assigned on bot startup for all existing guilds, not just newly joined ones.',
        ],
    ),
    (
        'v2.6.0 | March 2026',
        0x00e5ff,
        [
            '\U0001f3a3 **Fishing level requirements**: Each rod now requires a minimum Fishing Level to equip and use. Silver=5, Gold=10, Diamond=15, Pearl=20, Crystal=25, Titanium=30, Quantum=40, Obsidian=50, Cosmic=60, Void=75. Once you pass a level you can freely use any rod at or below it. `t!rods` shows your level, each rod’s requirement, and whether it’s locked.',
            '\U0001f9f9 **Fish Vacuum now works**: Buying one stores it in inventory. On your next `t!fish` it auto-discards all trash fish from your bag, then gets consumed. Stackable: buy multiple to protect several trips.',
            '\U0001f504 **Streak Restore now works**: `t!use streak_restore` restores your daily streak to the value it had before your last missed day. Only works if your streak reset recently.',
            '\U0001f381 **Mystery Box now works**: Opens immediately on purchase with a random reward: coins (300–6,000), gems, tokens, or a shop item (Premium Bait, XP Boost, rods, shields, and more). 23-item weighted prize pool with rare jackpots.',
            '\U0001f4e1 **Fish Radar now works**: Buy one (`t!buy fishing_radar`) then run `t!radar` to preview your next 5 catches: exact fish name, tier emoji, and estimated sell value: based on your current rod, level, and bait. Item is consumed on use.',
            '\U0001f527 **Rod equip bug fixed**: `t!equip cosmic` (and all rods) now correctly detects ownership. Previously the shop stored rods as `rod_cosmic` while equip checked for `cosmic`, causing a permanent “You don’t own this” error.',
            '\U0001f6d2 **Consumable item overhaul**: `daily_reset` and `work_reset` now sit in your inventory after purchase and are activated with `t!use daily_reset` / `t!use work_reset`. `streak_shield` is now consumed when it saves a cooldown instead of acting as permanent. All single-use items correctly show “Single Use” in the shop instead of “Permanent”.',
            '\U0001f4e6 **Stackable consumables**: You can now buy multiple copies of any single-use item (daily_reset, work_reset, streak_shield, fish_vacuum, streak_restore, fishing_radar) to stockpile them.',
        ],
    ),
    (
        'v2.7.0 | May 2026',
         0x7c4dff,
        [
            '\U0001f6e1\ufe0f **Owner-only command suite**: `t!ownerhelp` creates a private 🛡️ Owner Help category with admin-tools / bugs-glitches / notes channels for in-server moderation. `t!removeitem @user <item>` recovers from inventory glitches. `t!givesub`, `t!giveserversub`, and `t!viewserversub` let the bot owner grant or inspect subscriptions directly.',
            '\U0001f3e2 **Server subscription management**: `t!serversubscribe` shows the new server tiers ($7.99 Basic / $14.99 Pro), and `t!servertier` shows your current server\'s plan and expiry. Member discount lifted to 30% on Pro / 15% on Basic.',
            '\U0001f4ac **Unified ephemeral replies**: New `send_reply` utility makes ephemeral / public responses behave consistently across slash, hybrid, and prefix invocations. Fixes a class of subtle bugs where private command replies leaked into public channels.',
            '\U0001f36a **Fortune cookies expanded**: Added a fresh batch of `t!fortune` messages for a more varied daily roll.',
            '\U0001f510 **Security policy published**: New `SECURITY.md` documents the vulnerability disclosure process and security best practices.',
            '\U0001f9f0 **Behind the scenes — architecture migration begins**: Cog loading now uses dotted-paths (`cogs.<name>`) and the database layer is being split into per-domain modules. No user-facing changes from this work in 2.7.0 — it\'s groundwork that lets 2.8+ ship features faster and with fewer regressions.',
        ],
    ),
]


async def clear_bot(channel, me):
    try:
        async for msg in channel.history(limit=20):
            if msg.author == me:
                await msg.delete()
                await asyncio.sleep(0.3)
    except discord.HTTPException:
        pass


class ChangelogClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Connected as: {self.user}')
        g = self.get_guild(GUILD_ID)
        if not g:
            print('Guild not found.')
            await self.close()
            return

        # ── Find Info category ────────────────────────────────────────────────
        info_cat = discord.utils.find(lambda c: 'info' in c.name.lower(), g.categories)

        # ── Create or find #changelog ─────────────────────────────────────────
        changelog_ch = discord.utils.find(lambda c: 'changelog' in c.name.lower(), g.text_channels)
        if not changelog_ch:
            overwrites = {
                g.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                g.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
            }
            changelog_ch = await g.create_text_channel(
                name='\U0001f4cb\u2503changelog',
                category=info_cat,
                overwrites=overwrites,
                topic='All Tainment+ bot updates and changes.',
                reason='PopFusion changelog channel',
            )
            print(f'[CREATED] #{changelog_ch.name}')
        else:
            print(f'[EXISTS]  #{changelog_ch.name}')

        # ── Post changelog ────────────────────────────────────────────────────
        # Oldest first → newest last. --new mode appends only the latest without clearing.
        versions = VERSIONS

        if NEW_ONLY:
            # Append only the latest version (last in list) as a new message
            version, colour, changes = versions[-1]
            embed = discord.Embed(title=version, color=colour)
            embed.description = '\n'.join(f'\u2022 {c}' for c in changes)
            await changelog_ch.send(embed=embed)
            print(f'[OK] Appended {version}')
        else:
            await clear_bot(changelog_ch, self.user)

            header = discord.Embed(
                title='\U0001f4cb Tainment+ Changelog',
                description='A full history of updates to the PopFusion bot.',
                color=0xe040fb,
            )
            header.set_footer(text='PopFusion | Discover Music. Build A Community.')
            await changelog_ch.send(embed=header)
            await asyncio.sleep(0.4)

            for version, colour, changes in versions:
                embed = discord.Embed(title=version, color=colour)
                embed.description = '\n'.join(f'\u2022 {c}' for c in changes)
                await changelog_ch.send(embed=embed)
                await asyncio.sleep(0.5)

            print(f'[OK] Posted changelog ({len(versions)} versions)')

        # ── Refresh #announcements ────────────────────────────────────────────
        if not NEW_ONLY:
            ann_ch = discord.utils.find(lambda c: 'announcement' in c.name.lower(), g.text_channels)
            if ann_ch:
                await clear_bot(ann_ch, self.user)
                embed = discord.Embed(
                    title='\U0001f4e2 Welcome to PopFusion!',
                    description=(
                        'The **PopFusion** music discovery community is live!\n\n'
                        'We\'re a community built around music discovery, genre exploration, and having fun. '
                        'Whether you\'re into pop, hip-hop, rock or electronic, there\'s a lane for you.\n\n'
                        '**Get started:**\n'
                        '\u2022 Read \U0001f4dc\u2503rules before chatting\n'
                        '\u2022 Pick your genre in \U0001f3a4\u2503pick-your-lane\n'
                        '\u2022 Claim daily coins with `t!daily`\n'
                        '\u2022 Go fishing with `t!fish` \U0001f3a3\n'
                        '\u2022 See all commands with `t!help`\n\n'
                        '**Subscription tiers:**\n'
                        '\U0001f3b5 Basic: Free forever\n'
                        '\U0001f525 Vibe: $1.99/mo\n'
                        '\u2b50 Premium: $4.99/mo\n'
                        '\u26a1 Pro: $7.99/mo\n'
                        'Upgrade with `t!upgrade <tier>`\n\n'
                        '\U0001f4cb Stay up to date in \U0001f4cb\u2503changelog'
                    ),
                    color=0xe040fb,
                )
                embed.set_thumbnail(url=self.user.display_avatar.url)
                embed.set_footer(text='PopFusion | Discover Music. Build A Community.')
                await ann_ch.send(embed=embed)
                print(f'[OK] Updated #{ann_ch.name}')

        print('\nDone!')
        await self.close()


if __name__ == '__main__':
    client = ChangelogClient()
    client.run(TOKEN, log_handler=None)
