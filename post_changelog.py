"""
Creates #📋┃changelog under the 📢 Info category and posts the full changelog.
Also refreshes the announcement in #📢┃announcements.

Run: python post_changelog.py
"""

import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN    = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163


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
        await clear_bot(changelog_ch, self.user)

        header = discord.Embed(
            title='\U0001f4cb Tainment+ Changelog',
            description='A full history of updates to the PopFusion bot.',
            color=0xe040fb,
        )
        header.set_footer(text='PopFusion \u2014 discover music. build community.')
        await changelog_ch.send(embed=header)
        await asyncio.sleep(0.4)

        versions = [
            (
                'v2.2.0 \u2014 March 2026',
                0xe040fb,
                [
                    '\u2328\ufe0f **7 new fun games** \u2014 `t!typerace`, `t!riddle`, `t!wouldyourather`, `t!emojidecode`, `t!fastmath`, `t!hotpotato`, `t!wordchain` \u2014 all earn coins, gems, or tokens.',
                    '\U0001f6e1\ufe0f **Full moderation suite** \u2014 `t!warn`, `t!kick`, `t!ban`, `t!unban`, `t!timeout`, `t!purge`, `t!slowmode`, `t!lock`, `t!unlock`, `t!addrole`, `t!removerole`, `t!nick`, `t!modlog`, `t!setmodlog`, `t!modinfo`.',
                    '\U0001f6d2 **9 new shop items** \u2014 Coin Magnet, Premium Bait, Gamble Shield (coins); XP Surge, Prestige Badge, Gem Booster (gems); Typerace Booster, Fish Vacuum, Streak Restore (tokens).',
                    '\U0001f4b3 **Shop IDs now visible** \u2014 Every shop item shows its exact `t!buy <id>` so you always know what to type.',
                    '\U0001f525 **Vibe tier content fixed** \u2014 Vibe subscribers now correctly access all joke/story categories, trivia, and get the Vibe badge on their profile.',
                    '\u23f0 **Leaderboard timer updated** \u2014 Auto-leaderboard now refreshes every **10 minutes** (was 5).',
                    '\U0001f4c4 **Subscription tiers expanded** \u2014 Each tier now has clearer, more distinct perks including work bonuses, fishing boosts, and free Lucky Gambles for Premium/Pro.',
                    '\U0001f4cb **Help & FAQ refreshed** \u2014 `#help` and `#faq` channels updated with all current commands, tiers, and genre lane info.',
                ],
            ),
            (
                'v2.1.0 \u2014 March 2026',
                0xe040fb,
                [
                    '\U0001f4ca **Upvote/Downvote on feature requests** \u2014 Community can vote on submitted ideas. Toggle off by clicking again.',
                    '\U0001f4cb **#changelog channel** \u2014 Dedicated channel for tracking all bot updates (you\'re reading it!).',
                    '\U0001f3b5 **Genre lane reaction roles** \u2014 `#\U0001f3a4\u2503pick-your-lane` — react to self-assign genre roles; unreact to remove.',
                    '\U0001f4dd **Support forms routed privately** \u2014 Bug reports go to staff-only `#mod-logs`; billing requests go to admin-only `#admin-panel`.',
                    '\u2b50 **Feature request form** \u2014 `#\u2b50\u2503feature-requests` now has a modal form with structured fields.',
                    '\U0001f510 **Channel permissions hardened** \u2014 `#leaderboards` is bot-only; `#billing-support` restricted to admins.',
                    '\U0001f3a4 **4 genre lane roles** \u2014 Pop Lane, Hip-Hop Lane, Rock Lane, Electronic Lane (cosmetic).',
                    '\U0001f3b5 **4 new voice channels** \u2014 Vibe Lounge, Late Night Session, Hangout Spot, Game Night.',
                    '\U0001f4dc **#rules redesigned** \u2014 9 professional sections with PopFusion brand styling.',
                    '\U0001f4ac **#faq updated** \u2014 Covers all tiers, fishing, genre lanes, and support channels.',
                ],
            ),
            (
                'v2.0.1 \u2014 March 2026',
                0x00e5ff,
                [
                    '\U0001f3a3 **Fishing cooldown reduced** \u2014 Base 30s \u2192 15s. Silver 30s \u2192 12s. Gold 25s \u2192 10s. Diamond 20s \u2192 7s.',
                    '\U0001f4b0 **Gambling display fixed** \u2014 Win now clearly shows "Payout: +190 (bet returned + profit)" so it\'s obvious your bet is safe.',
                    '\U0001f39b\ufe0f **PopFusion role rebrand** \u2014 All roles renamed to match the music festival brand:\n'
                    '\u2003Owner\u2192\U0001f39b\ufe0f Founder \u2022 Admin\u2192\U0001f39a\ufe0f Producer \u2022 Moderator\u2192\U0001f6e1\ufe0f Stage Manager \u2022 Support\u2192\U0001f399\ufe0f Crew\n'
                    '\u2003Member\u2192\U0001f3b5 Listener \u2022 Subscriber\u2192\U0001f525 Fuser \u2022 Announcements Ping\u2192\U0001f4e2 Drop Alerts',
                    '\U0001f4b3 **New Vibe tier at $1.99/mo** \u2014 All joke/story categories, trivia, 200 daily coins, 1.2x XP.',
                    '\U0001f4b8 **Pro tier reduced** \u2014 $9.99 \u2192 $7.99/mo.',
                ],
            ),
            (
                'v2.0.0 \u2014 March 2026',
                0x7c4dff,
                [
                    '\U0001f3a3 **Competitive fishing game** \u2014 18 fish types across 6 tiers. Commands: `t!fish`, `t!fishbag`, `t!sell`, `t!fishstats`, `t!fishtop`.',
                    '\U0001f3a3 **Fishing rods in shop** \u2014 Silver Rod (1500\U0001fa99), Gold Rod (5000\U0001fa99), Diamond Rod (20\U0001f48e). Each improves catch rates.',
                    '\U0001f3c6 **Auto-updating leaderboard** \u2014 `#\U0001f3c6\u2503leaderboards` refreshes every 5 min with top richest, XP, and fishers.',
                    '\U0001f331 **XP milestone roles** \u2014 Auto-assigned at Lvl 5/10/20/30/50: Newcomer, Groover, Fanatic, Headliner, Icon.',
                    '\U0001f464 **Auto Member role on join** \u2014 New members automatically receive \U0001f3b5 Listener.',
                    '\U0001f41b **Support forms** \u2014 Modal forms for bug reports and billing support (buttons in support channels).',
                    '\U0001fa99 **Multi-currency economy** \u2014 Coins \U0001fa99, Gems \U0001f48e, Tokens \U0001f3ab across all games and the shop.',
                    '\U0001f3ae **New games** \u2014 Tic-Tac-Toe, Connect Four, Scramble, Math Quiz, Higher/Lower, Duel, Snap.',
                    '\U0001f6d2 **Premium shop** \u2014 15+ items across three currency shops.',
                    '\U0001f4e3 **Giveaways, polls, reminders** \u2014 Full community tools added.',
                ],
            ),
        ]

        for version, colour, changes in versions:
            embed = discord.Embed(title=version, color=colour)
            embed.description = '\n'.join(f'\u2022 {c}' for c in changes)
            await changelog_ch.send(embed=embed)
            await asyncio.sleep(0.5)

        print(f'[OK] Posted changelog ({len(versions)} versions)')

        # ── Refresh #announcements ────────────────────────────────────────────
        ann_ch = discord.utils.find(lambda c: 'announcement' in c.name.lower(), g.text_channels)
        if ann_ch:
            await clear_bot(ann_ch, self.user)
            embed = discord.Embed(
                title='\U0001f4e2 Welcome to PopFusion!',
                description=(
                    'The **PopFusion** music discovery community is live!\n\n'
                    'We\'re a community built around music discovery, genre exploration, and having fun. '
                    'Whether you\'re into pop, hip-hop, rock or electronic \u2014 there\'s a lane for you.\n\n'
                    '**Get started:**\n'
                    '\u2022 Read \U0001f4dc\u2503rules before chatting\n'
                    '\u2022 Pick your genre in \U0001f3a4\u2503pick-your-lane\n'
                    '\u2022 Claim daily coins with `t!daily`\n'
                    '\u2022 Go fishing with `t!fish` \U0001f3a3\n'
                    '\u2022 See all commands with `t!help`\n\n'
                    '**Subscription tiers:**\n'
                    '\U0001f3b5 Basic \u2014 Free forever\n'
                    '\U0001f525 Vibe \u2014 $1.99/mo\n'
                    '\u2b50 Premium \u2014 $4.99/mo\n'
                    '\u26a1 Pro \u2014 $7.99/mo\n'
                    'Upgrade with `t!upgrade <tier>`\n\n'
                    '\U0001f4cb Stay up to date in \U0001f4cb\u2503changelog'
                ),
                color=0xe040fb,
            )
            embed.set_thumbnail(url=self.user.display_avatar.url)
            embed.set_footer(text='PopFusion \u2014 discover music. build community.')
            await ann_ch.send(embed=embed)
            print(f'[OK] Updated #{ann_ch.name}')

        print('\nDone!')
        await self.close()


if __name__ == '__main__':
    client = ChangelogClient()
    client.run(TOKEN, log_handler=None)
