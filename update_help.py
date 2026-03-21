"""
Updates #🆘┃help and #❓┃faq channels with current PopFusion content.

Run: python update_help.py
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
        async for msg in channel.history(limit=30):
            if msg.author == me:
                await msg.delete()
                await asyncio.sleep(0.3)
    except discord.HTTPException:
        pass


class HelpClient(discord.Client):
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

        def find(partial):
            for c in g.text_channels:
                if partial in c.name.lower():
                    return c
            return None

        help_ch    = find('help')
        faq_ch     = find('faq')
        bug_ch     = find('bug')
        billing_ch = find('billing')
        feature_ch = find('feature')

        posted = []

        # ── #help ─────────────────────────────────────────────────────────────
        if help_ch:
            await clear_bot(help_ch, self.user)

            header = discord.Embed(
                title='\U0001f198 PopFusion Help Centre',
                description=(
                    'Everything you need to enjoy the PopFusion community.\n'
                    'All commands work as `t!command` **or** `/command` (slash).'
                ),
                color=0xe040fb,
            )
            header.set_footer(text='PopFusion \u2014 discover music. build community.')
            await help_ch.send(embed=header)
            await asyncio.sleep(0.4)

            # Economy & Rewards
            e1 = discord.Embed(title='\U0001fa99 Economy & Rewards', color=0xf1c40f)
            e1.add_field(name='Daily & Work', value=(
                '`t!daily` \u2014 claim daily coins (streak bonuses apply)\n'
                '`t!work` \u2014 earn coins (1h cooldown)\n'
                '`t!balance` \u2014 check your coins \U0001fa99, gems \U0001f48e, tokens \U0001f3ab'
            ), inline=False)
            e1.add_field(name='Gambling', value=(
                '`t!gamble <amount>` \u2014 risk coins for profit\n'
                '`t!slots <bet>` \u2014 spin the slot machine\n'
                '`t!rob @user` \u2014 attempt to steal coins (30% chance)'
            ), inline=False)
            e1.add_field(name='Leaderboards', value=(
                '`t!richest` \u2014 top coin holders\n'
                '`t!leaderboard <game>` \u2014 game score boards\n'
                '\U0001f3c6 `#leaderboards` auto-updates every **10 minutes**'
            ), inline=False)
            await help_ch.send(embed=e1)
            await asyncio.sleep(0.4)

            # Fishing
            e2 = discord.Embed(title='\U0001f3a3 Fishing', color=0x3498db)
            e2.add_field(name='Commands', value=(
                '`t!fish` \u2014 cast your line (cooldown depends on rod)\n'
                '`t!fishbag` \u2014 view your caught fish\n'
                '`t!sell all` or `t!sell <fish>` \u2014 sell for coins/gems/tokens\n'
                '`t!fishstats` \u2014 your fishing stats & rod\n'
                '`t!fishtop` \u2014 fishing leaderboard'
            ), inline=False)
            e2.add_field(name='Rods & Cooldowns', value=(
                '\U0001f3a3 **No rod** \u2014 15s cooldown, base catch rates\n'
                '\U0001f948 **Silver Rod** (1500 \U0001fa99) \u2014 12s cooldown, better rates\n'
                '\U0001f947 **Gold Rod** (5000 \U0001fa99) \u2014 10s cooldown, great rates\n'
                '\U0001f48e **Diamond Rod** (20 \U0001f48e) \u2014 7s cooldown, best rates\n'
                'Buy rods with `t!shop coins` or `t!shop gems`'
            ), inline=False)
            e2.add_field(name='Fish Tiers', value=(
                'Common \u2022 Uncommon \u2022 Rare \u2022 Legendary \u2022 Special \u2022 Junk\n'
                'Higher-tier fish sell for more coins, gems, and tokens.'
            ), inline=False)
            await help_ch.send(embed=e2)
            await asyncio.sleep(0.4)

            # Games
            e3 = discord.Embed(title='\U0001f3ae Games', color=0x9b59b6)
            e3.add_field(name='Multiplayer', value=(
                '`t!ttt @user` \u2014 Tic-Tac-Toe\n'
                '`t!connect4 @user` \u2014 Connect Four\n'
                '`t!duel @user <bet>` \u2014 coin duel\n'
                '`t!snap @user` \u2014 reaction snap game'
            ), inline=False)
            e3.add_field(name='Solo', value=(
                '`t!trivia` \u2014 trivia quiz\n'
                '`t!hangman` \u2014 hangman\n'
                '`t!wordle` \u2014 daily word game\n'
                '`t!scramble` \u2014 unscramble the word\n'
                '`t!math` \u2014 math quiz\n'
                '`t!higherlower` \u2014 higher or lower'
            ), inline=False)
            await help_ch.send(embed=e3)
            await asyncio.sleep(0.4)

            # Levels & Roles
            e4 = discord.Embed(title='\u2b50 Levels & Roles', color=0x2ecc71)
            e4.add_field(name='Levelling Up', value=(
                'Earn XP by chatting (60s cooldown per message).\n'
                '`t!level` \u2014 your current level & XP\n'
                '`t!leaderboard` \u2014 top XP holders'
            ), inline=False)
            e4.add_field(name='XP Milestone Roles', value=(
                '\U0001f331 **Level 5** \u2192 \U0001f331 Newcomer\n'
                '\U0001f3a7 **Level 10** \u2192 \U0001f3a7 Groover\n'
                '\U0001f4bf **Level 20** \u2192 \U0001f4bf Fanatic\n'
                '\U0001f3b8 **Level 30** \u2192 \U0001f3b8 Headliner\n'
                '\u26a1 **Level 50** \u2192 \u26a1 Icon'
            ), inline=False)
            e4.add_field(name='Genre Lane Roles', value=(
                'Head to \U0001f3a4`#pick-your-lane` and react to get your genre role:\n'
                '\U0001f3a4 Pop Lane \u2022 \U0001f3a4 Hip-Hop Lane \u2022 \U0001f3a4 Rock Lane \u2022 \U0001f3a4 Electronic Lane'
            ), inline=False)
            await help_ch.send(embed=e4)
            await asyncio.sleep(0.4)

            # Subscriptions
            e5 = discord.Embed(title='\U0001f4b3 Subscription Tiers', color=0xe040fb)
            e5.add_field(name='Plans', value=(
                '\U0001f3b5 **Basic** \u2014 Free forever\n'
                '  Daily coins, basic games, economy\n\n'
                '\U0001f525 **Vibe** \u2014 $1.99/mo\n'
                '  All joke/story categories, trivia, 200 daily coins, 1.2x XP\n\n'
                '\u2b50 **Premium** \u2014 $4.99/mo\n'
                '  All games, trivia, hangman, wordle, 350 daily coins, 1.5x XP\n\n'
                '\u26a1 **Pro** \u2014 $7.99/mo\n'
                '  Everything + blackjack, 500 daily coins, 3x XP, exclusive content'
            ), inline=False)
            e5.add_field(name='Upgrade', value='`t!upgrade <tier>` \u2014 e.g. `t!upgrade premium`', inline=False)
            await help_ch.send(embed=e5)
            await asyncio.sleep(0.4)

            # Shop
            e6 = discord.Embed(title='\U0001f6d2 Shop', color=0xe67e22)
            e6.add_field(name='Commands', value=(
                '`t!shop coins` \u2014 items purchasable with \U0001fa99\n'
                '`t!shop gems` \u2014 items purchasable with \U0001f48e\n'
                '`t!shop tokens` \u2014 items purchasable with \U0001f3ab\n'
                '`t!buy <item>` \u2014 purchase an item\n'
                '`t!inventory` \u2014 view owned items'
            ), inline=False)
            await help_ch.send(embed=e6)
            await asyncio.sleep(0.4)

            # Support
            e7 = discord.Embed(title='\U0001f6e1\ufe0f Support', color=0xed4245)
            bug_ref     = bug_ch.mention if bug_ch else '`#bug-reports`'
            billing_ref = billing_ch.mention if billing_ch else '`#billing-support`'
            feature_ref = feature_ch.mention if feature_ch else '`#feature-requests`'
            e7.add_field(name='Report a Bug', value=f'Use the form in {bug_ref} \u2014 reports go privately to staff.', inline=False)
            e7.add_field(name='Billing Issues', value=f'Use the form in {billing_ref} \u2014 goes privately to admins.', inline=False)
            e7.add_field(name='Feature Requests', value=f'Submit an idea in {feature_ref} \u2014 community can upvote/downvote.', inline=False)
            e7.add_field(name='Urgent Issues', value='Ping a \U0001f6e1\ufe0f Stage Manager or \U0001f39a\ufe0f Producer.', inline=False)
            e7.set_footer(text='PopFusion Support \u2014 we read every submission')
            await help_ch.send(embed=e7)

            print(f'[OK] Updated #{help_ch.name} (7 embeds)')
            posted.append(help_ch.name)

        # ── #faq ──────────────────────────────────────────────────────────────
        if faq_ch:
            await clear_bot(faq_ch, self.user)

            faq_items = [
                (
                    'How do I get started?',
                    0xe040fb,
                    'React to your genre in \U0001f3a4`#pick-your-lane`, then use `t!daily` to claim coins.\n'
                    'Try `t!fish` for the fishing game or `t!help` for the full command list.',
                ),
                (
                    'What are the three currencies?',
                    0xf1c40f,
                    '\U0001fa99 **Coins** \u2014 daily, work, gambling, selling fish. Used in coin shop.\n'
                    '\U0001f48e **Gems** \u2014 rare fish sales, game wins, slot jackpots. Used in gem shop.\n'
                    '\U0001f3ab **Tokens** \u2014 streaks, duels, scramble, snap. Used in token shop.',
                ),
                (
                    'How does fishing work?',
                    0x3498db,
                    'Use `t!fish` to cast your line. Fish land in your bag \u2014 `t!fishbag` to view, `t!sell all` to cash in.\n'
                    'Buy better rods from `t!shop` to catch rarer fish faster. Base cooldown is 15s; Diamond Rod is 7s.',
                ),
                (
                    'What are the subscription tiers?',
                    0x9b59b6,
                    '\U0001f3b5 **Basic** (Free) \u2014 daily coins, basic games, economy.\n'
                    '\U0001f525 **Vibe** ($1.99/mo) \u2014 joke/story categories, trivia, 200 coins/day, 1.2x XP.\n'
                    '\u2b50 **Premium** ($4.99/mo) \u2014 all games, 350 coins/day, 1.5x XP.\n'
                    '\u26a1 **Pro** ($7.99/mo) \u2014 everything + blackjack, 500 coins/day, 3x XP.',
                ),
                (
                    'How do I earn XP milestone roles?',
                    0x2ecc71,
                    'Chat in any channel to earn XP (60s per-message cooldown).\n'
                    'Roles are auto-assigned when you hit the milestone:\n'
                    'Lvl 5 \u2192 \U0001f331 Newcomer \u2022 Lvl 10 \u2192 \U0001f3a7 Groover \u2022 Lvl 20 \u2192 \U0001f4bf Fanatic\n'
                    'Lvl 30 \u2192 \U0001f3b8 Headliner \u2022 Lvl 50 \u2192 \u26a1 Icon',
                ),
                (
                    'How do genre lane roles work?',
                    0xe67e22,
                    'Go to \U0001f3a4`#pick-your-lane` and react with the emoji for your genre:\n'
                    'Pop, Hip-Hop, Rock, or Electronic. React again to remove the role.',
                ),
                (
                    'How do I report a bug or billing issue?',
                    0xed4245,
                    f'Bug reports: use the form in {bug_ch.mention if bug_ch else "`#bug-reports`"} \u2014 goes privately to staff.\n'
                    f'Billing: use the form in {billing_ch.mention if billing_ch else "`#billing-support`"} \u2014 goes privately to admins.\n'
                    f'Feature ideas: submit in {feature_ch.mention if feature_ch else "`#feature-requests`"} \u2014 community can vote.',
                ),
            ]

            for question, colour, answer in faq_items:
                embed = discord.Embed(
                    title=f'\u2753 {question}',
                    description=answer,
                    color=colour,
                )
                embed.set_footer(text='PopFusion FAQ')
                await faq_ch.send(embed=embed)
                await asyncio.sleep(0.5)

            print(f'[OK] Updated #{faq_ch.name} ({len(faq_items)} entries)')
            posted.append(faq_ch.name)

        print(f'\nDone! Updated: {", ".join(posted)}')
        await self.close()


if __name__ == '__main__':
    client = HelpClient()
    client.run(TOKEN, log_handler=None)
