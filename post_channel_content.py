"""
One-time script that posts structured content to:
  - #👋┃welcome       (server welcome + bot intro)
  - #📰┃updates
  - #❓┃faq
  - #🆘┃help
  - #🐛┃bug-reports   (bug report form panel)
  - #💳┃billing-support (billing support form panel)

Run once after bot is started:
  python post_channel_content.py
  python post_channel_content.py welcome   # welcome channel only
"""

import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163

# Optional: pass "welcome" as CLI arg to only post the welcome message
TARGET = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'


class PostClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Connected as: {self.user}')
        guild = self.get_guild(GUILD_ID)
        if not guild:
            print('Guild not found.')
            await self.close()
            return

        ch = {c.name: c for c in guild.text_channels}

        def find(partial: str):
            for name, channel in ch.items():
                if partial in name:
                    return channel
            return None

        welcome_ch      = find('welcome')
        updates_ch      = find('updates')
        faq_ch          = find('faq')
        help_ch         = find('help')
        bug_ch          = find('bug')
        billing_ch      = find('billing')

        posted = []

        # ── #welcome ──────────────────────────────────────────────────────────
        if welcome_ch and TARGET in ('all', 'welcome'):
            await _clear_bot_messages(welcome_ch, self.user)

            # Header embed
            header = discord.Embed(
                title='Welcome to PopFusion — powered by Tainment+',
                description=(
                    'PopFusion is the community hub for music, entertainment, and competition.\n'
                    'Tainment+ is the Discord bot that runs it all.\n\n'
                    'Everything here is driven by the community — earn coins, climb leaderboards, '
                    'discover music, and compete with players from all over.\n\n'
                    '**Start here** — type `t!daily` to claim your first reward.'
                ),
                color=0xEB459E,
            )
            header.set_footer(text='PopFusion | Tainment+ Bot  •  prefix: t!')
            await welcome_ch.send(embed=header)
            await asyncio.sleep(0.5)

            # What can you do embed
            features = discord.Embed(title='What can you do here?', color=0x5865F2)
            features.add_field(
                name='🪙 Economy',
                value='`t!daily` `t!work` `t!gamble` `t!shop`\nEarn coins, gems & tokens. Buy upgrades from the shop.',
                inline=False,
            )
            features.add_field(
                name='🎣 Fishing',
                value='`t!fish` `t!fishbag` `t!sell all` `t!fishtop`\n2,300+ fish across 10 rarity tiers — can you catch a Void Fish?',
                inline=False,
            )
            features.add_field(
                name='🎮 Games',
                value='`t!trivia` `t!typerace` `t!wordle` `t!blackjack` `t!duel`\nPlay solo or challenge other members for rewards.',
                inline=False,
            )
            features.add_field(
                name='🎵 Music Discovery',
                value='`t!genresearch` `t!sharetrack` `t!musicprofile`\nExplore 16 genre lanes, share your tracks, and build your music profile.',
                inline=False,
            )
            features.add_field(
                name='📈 Levels & Roles',
                value='Chat to earn XP. Hit milestones to unlock exclusive roles:\n'
                      '⭐ Novice → 🌟 Regular → 💫 Veteran → 🔥 Elite → 👑 Legend',
                inline=False,
            )
            await welcome_ch.send(embed=features)
            await asyncio.sleep(0.5)

            # Server channels guide
            channels = discord.Embed(title='Find your way around', color=0x57F287)
            channels.add_field(
                name='Key Channels',
                value=(
                    f'📰 {updates_ch.mention if updates_ch else "#📰┃updates"} — Bot updates and patch notes\n'
                    f'❓ {faq_ch.mention if faq_ch else "#❓┃faq"} — Answers to common questions\n'
                    f'🆘 {help_ch.mention if help_ch else "#🆘┃help"} — Command guide\n'
                    f'🐛 {bug_ch.mention if bug_ch else "#🐛┃bug-reports"} — Report bugs\n'
                    f'💳 {billing_ch.mention if billing_ch else "#💳┃billing-support"} — Subscription help'
                ),
                inline=False,
            )
            channels.add_field(
                name='Subscription Tiers',
                value=(
                    '**Free** — Economy, fishing, basic games\n'
                    '**Vibe** ($1.99/mo) — Virtual pet, custom bio, music trivia\n'
                    '**Premium** ($4.99/mo) — All games, 1.5× XP, 350 daily coins\n'
                    '**Pro** ($9.99/mo) — Blackjack, 3× XP, 500 daily coins, exclusive content\n\n'
                    'Use `t!subscription` to view and manage your plan.'
                ),
                inline=False,
            )
            channels.set_footer(text='See tainment.trijbsworlds.nl for the full command list')
            await welcome_ch.send(embed=channels)
            posted.append('#👋┃welcome')

        # ── #updates ──────────────────────────────────────────────────────────
        if updates_ch and TARGET in ('all', 'updates'):
            await _clear_bot_messages(updates_ch, self.user)
            embed = discord.Embed(
                title='\U0001f4e2 Tainment+ Update Log',
                color=0x5865F2,
            )
            embed.add_field(
                name='v2.0.0 — Current Release',
                value=(
                    '\u2022 **Multi-currency economy** — Coins \U0001fa99, Gems \U0001f48e, Tokens \U0001f3ab\n'
                    '\u2022 **Competitive Fishing** — 18 fish types, 3 rod tiers, live leaderboard\n'
                    '\u2022 **New Games** — Tic-Tac-Toe, Connect Four, Scramble, Math Quiz, Higher/Lower, Duel, Snap\n'
                    '\u2022 **XP Milestone Roles** — Level up to earn exclusive roles (Novice → Legend)\n'
                    '\u2022 **Support Forms** — Bug reports and billing requests via modal forms\n'
                    '\u2022 **Auto Leaderboard** — #🏆┃leaderboards updates every 5 minutes\n'
                    '\u2022 **Premium Shop** — 15+ items across coins/gems/tokens\n'
                    '\u2022 **Giveaways, Polls & Reminders** — Full community tools'
                ),
                inline=False,
            )
            embed.add_field(
                name='Coming Soon',
                value=(
                    '\u2022 Fishing tournaments with seasonal prizes\n'
                    '\u2022 More fish types and special fishing events\n'
                    '\u2022 Guild-wide challenges and cooperative events'
                ),
                inline=False,
            )
            embed.set_footer(text='Follow this channel for all future updates')
            await updates_ch.send(embed=embed)
            posted.append('#📰┃updates')

        # ── #faq ──────────────────────────────────────────────────────────────
        if faq_ch and TARGET in ('all', 'faq'):
            await _clear_bot_messages(faq_ch, self.user)

            faq_items = [
                ('How do I get started?',
                 'Use `t!daily` to claim your first coins, then try `t!work` for more. '
                 'Check `t!help` for the full command list or use the `/help` slash command.'),
                ('What are the three currencies?',
                 '\U0001fa99 **Coins** — Earned from daily, work, gambling. Used in the coin shop.\n'
                 '\U0001f48e **Gems** — Earned by winning games and selling rare fish. Used in the gem shop.\n'
                 '\U0001f3ab **Tokens** — Earned from streaks, duels, snap, scramble. Used in the token shop.'),
                ('How does fishing work?',
                 'Use `t!fish` to cast your line (30s cooldown). Fish go into your bag — use `t!sell all` '
                 'to cash them in for coins, gems, and tokens. Buy better rods from `t!shop coins` to catch '
                 'rarer fish. Check `t!fishstats` for your progress.'),
                ('What are the subscription tiers?',
                 '**Basic** (Free) — Daily rewards, basic games, economy.\n'
                 '**Premium** ($4.99/mo) — All games, trivia, hangman, wordle, 350 daily coins, 1.5x XP.\n'
                 '**Pro** ($9.99/mo) — Everything + blackjack, 500 daily coins, 3x XP, exclusive content.'),
                ('How do I level up and earn roles?',
                 'Earn XP by chatting (60s cooldown per message). Level milestones unlock exclusive roles:\n'
                 '**Level 5** → ⭐ Novice  |  **Level 10** → 🌟 Regular\n'
                 '**Level 20** → 💫 Veteran  |  **Level 30** → 🔥 Elite  |  **Level 50** → 👑 Legend'),
                ('How do I report a bug or billing issue?',
                 f'Use the form buttons in the support channels — see {billing_ch.mention if billing_ch else "#💳┃billing-support"} '
                 f'and {bug_ch.mention if bug_ch else "#🐛┃bug-reports"}.'),
            ]

            for question, answer in faq_items:
                embed = discord.Embed(
                    title=f'\u2753 {question}',
                    description=answer,
                    color=0xEB459E,
                )
                await faq_ch.send(embed=embed)
                await asyncio.sleep(0.5)
            posted.append('#❓┃faq')

        # ── #help ─────────────────────────────────────────────────────────────
        if help_ch and TARGET in ('all', 'help'):
            await _clear_bot_messages(help_ch, self.user)
            embed = discord.Embed(
                title='\U0001f198 Tainment+ Help',
                description=(
                    'Need help? Here\'s how to get it:\n\n'
                    '\U0001f4ac **General help** — Use `t!help` or `/help` for the full command list.\n'
                    '\U0001f3ae **Games help** — Use `t!help games` or `t!help entertainment`.\n'
                    '\U0001fa99 **Economy help** — Use `t!help economy` or `t!help shop`.\n'
                    '\U0001f3a3 **Fishing help** — Use `t!fishstats`, `t!fishtop`, or see below.\n\n'
                    '**Fishing quick-start:**\n'
                    '`t!fish` — Cast your line  |  `t!fishbag` — View your bag\n'
                    '`t!sell all` — Sell everything  |  `t!fishstats` — View stats\n\n'
                    '**Support:**\n'
                    f'\U0001f41b Bug reports: {bug_ch.mention if bug_ch else "#🐛┃bug-reports"}\n'
                    f'\U0001f4b3 Billing: {billing_ch.mention if billing_ch else "#💳┃billing-support"}\n\n'
                    '**Staff** — Ping a \U0001f6e1\ufe0f Moderator or \u26a1 Admin for urgent issues.'
                ),
                color=0x57F287,
            )
            embed.add_field(
                name='Command Categories',
                value=(
                    '`economy` `entertainment` `games` `fishing`\n'
                    '`shop` `levels` `fun` `giveaway`\n'
                    '`polls` `reminders` `profile` `subscription`'
                ),
                inline=False,
            )
            embed.set_footer(text='All commands work as t!command or /command (slash)')
            await help_ch.send(embed=embed)
            posted.append('#🆘┃help')

        # ── #bug-reports — post the form panel ────────────────────────────────
        if bug_ch and TARGET in ('all', 'bug'):
            await _clear_bot_messages(bug_ch, self.user)
            from support_forms import BugReportView
            embed = discord.Embed(
                title='\U0001f41b Bug Report',
                description=(
                    'Found a bug with Tainment+? Help us fix it!\n\n'
                    'Click the button below to open the form. Please include:\n'
                    '\u2022 The exact command you used\n'
                    '\u2022 What went wrong\n'
                    '\u2022 What you expected\n'
                    '\u2022 Steps to reproduce (if possible)\n\n'
                    '*Staff review all reports.* \U0001f6e1\ufe0f'
                ),
                color=0xED4245,
            )
            embed.set_footer(text='Tainment+ Support  |  Your report is posted here for staff')
            await bug_ch.send(embed=embed, view=BugReportView())
            posted.append('#🐛┃bug-reports')

        # ── #billing-support — post the billing form panel ────────────────────
        if billing_ch and TARGET in ('all', 'billing'):
            await _clear_bot_messages(billing_ch, self.user)
            from support_forms import BillingView
            embed = discord.Embed(
                title='\U0001f4b3 Billing Support',
                description=(
                    'Having a payment or subscription issue? We\'re here to help!\n\n'
                    'Click the button below to submit a request.\n\n'
                    '**Common issues:**\n'
                    '\u2022 Payment not going through\n'
                    '\u2022 Subscription not activating\n'
                    '\u2022 Wrong tier applied\n'
                    '\u2022 Refund requests\n'
                    '\u2022 Renewal problems\n\n'
                    '*Our team will respond as soon as possible.* \U0001f3a7'
                ),
                color=0xFEE75C,
            )
            embed.set_footer(text='Tainment+ Support  |  Your request is posted here for staff')
            await billing_ch.send(embed=embed, view=BillingView())
            posted.append('#💳┃billing-support')

        print(f'\nPosted content to: {", ".join(posted)}')
        print('Done!')
        await self.close()


async def _clear_bot_messages(channel: discord.TextChannel, bot_user: discord.ClientUser):
    """Delete any existing messages from the bot in this channel."""
    try:
        async for msg in channel.history(limit=20):
            if msg.author == bot_user:
                await msg.delete()
                await asyncio.sleep(0.3)
    except discord.HTTPException:
        pass


if __name__ == '__main__':
    client = PostClient()
    client.run(TOKEN, log_handler=None)
