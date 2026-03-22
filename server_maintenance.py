"""
One-time server maintenance script:
  - Updates channel permissions (bug-reports, billing-support, leaderboards, mod-logs, admin-panel)
  - Adds new voice channels (Vibe Lounge, Late Night Session, Hangout Spot, Game Night)
  - Reposts #rules with a professional redesign
  - Reposts #faq with updated content
  - Posts form panels in #bug-reports, #billing-support, #feature-requests

Run:  python server_maintenance.py
"""

import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import discord
from dotenv import load_dotenv
from support_forms import BugReportView, BillingView, FeatureRequestView

load_dotenv()
TOKEN    = os.getenv('BOT_TOKEN')
GUILD_ID = 1390512546858926163

# Role name helpers
FOUNDER       = '\U0001f39b\ufe0f Founder'
PRODUCER      = '\U0001f39a\ufe0f Producer'
STAGE_MANAGER = '\U0001f6e1\ufe0f Stage Manager'
CREW          = '\U0001f399\ufe0f Crew'


def r(guild, name):
    """Get a role by name, or None."""
    return discord.utils.get(guild.roles, name=name)


def ch(guild, *fragments):
    """Get first text channel whose name contains any fragment."""
    for c in guild.text_channels:
        for frag in fragments:
            if frag in c.name.lower():
                return c
    return None


async def clear_bot_msgs(channel, me):
    try:
        async for msg in channel.history(limit=30):
            if msg.author == me:
                await msg.delete()
                await asyncio.sleep(0.3)
    except discord.HTTPException:
        pass


class MaintenanceClient(discord.Client):
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

        everyone = g.default_role
        me       = g.me

        # ── PHASE 1: Channel Permissions ──────────────────────────────────────
        print('\n' + '=' * 60)
        print('  PHASE 1 — CHANNEL PERMISSIONS')
        print('=' * 60)

        perms_tasks = [
            # (channel_fragments, overwrites_dict)

            # #bug-reports — everyone can view & click button, not type
            (['bug-report', 'bug'], {
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False),
                me:       discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                r(g, STAGE_MANAGER): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, CREW):          discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, PRODUCER):      discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, FOUNDER):       discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }),

            # #billing-support — everyone can view & click button, not type
            (['billing'], {
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False),
                me:       discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                r(g, PRODUCER): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, FOUNDER):  discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }),

            # #leaderboards — nobody types, only bot posts
            (['leaderboard'], {
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False),
                me:       discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
            }),

            # #mod-logs — staff only (bug report submissions land here)
            (['mod-log', 'mod-logs'], {
                everyone:            discord.PermissionOverwrite(view_channel=False),
                me:                  discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, STAGE_MANAGER): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, CREW):          discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, PRODUCER):      discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, FOUNDER):       discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }),

            # #admin-panel — founder + producer only (billing submissions land here)
            (['admin-panel', 'admin'], {
                everyone:       discord.PermissionOverwrite(view_channel=False),
                me:             discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, PRODUCER): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, FOUNDER):  discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }),

            # #feature-requests — everyone can view, only form submissions (no free typing)
            (['feature-request', 'feature'], {
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False),
                me:       discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                r(g, STAGE_MANAGER): discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, PRODUCER):      discord.PermissionOverwrite(view_channel=True, send_messages=True),
                r(g, FOUNDER):       discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }),
        ]

        for fragments, overwrites in perms_tasks:
            channel = ch(g, *fragments)
            if not channel:
                print(f'  [SKIP]  channel not found: {fragments}')
                continue
            # Filter out None keys (roles that don't exist)
            clean = {k: v for k, v in overwrites.items() if k is not None}
            try:
                await channel.edit(overwrites=clean, reason='PopFusion maintenance')
                print(f'  [OK]    #{channel.name}')
            except discord.HTTPException as e:
                print(f'  [ERR]   #{channel.name}: {e}')
            await asyncio.sleep(0.5)

        # ── PHASE 2: Voice Channels ───────────────────────────────────────────
        print('\n' + '=' * 60)
        print('  PHASE 2 — VOICE CHANNELS')
        print('=' * 60)

        voice_cat = discord.utils.find(lambda c: c.name.upper() == 'VOICE', g.categories)
        existing_vc_names = {vc.name for vc in g.voice_channels}

        new_vcs = [
            '\U0001f3b5 Vibe Lounge',
            '\U0001f3b6 Late Night Session',
            '\U0001f465 Hangout Spot',
            '\U0001f3ae Game Night',
        ]

        for name in new_vcs:
            if name in existing_vc_names:
                print(f'  [EXISTS] {name}')
                continue
            try:
                await g.create_voice_channel(
                    name=name,
                    category=voice_cat,
                    reason='PopFusion voice expansion',
                )
                print(f'  [CREATED] {name}')
            except discord.HTTPException as e:
                print(f'  [ERR]   {name}: {e}')
            await asyncio.sleep(0.5)

        # ── PHASE 3: Rules Channel ────────────────────────────────────────────
        print('\n' + '=' * 60)
        print('  PHASE 3 — #rules REDESIGN')
        print('=' * 60)

        rules_ch = ch(g, 'rules')
        if rules_ch:
            await clear_bot_msgs(rules_ch, self.user)

            header = discord.Embed(
                title='PopFusion \u2014 Community Guidelines',
                description=(
                    'Welcome to **PopFusion**, the music discovery community.\n'
                    'By participating in this server you agree to the rules below.\n'
                    'Violations may result in a warning, mute, or permanent ban at staff discretion.'
                ),
                color=0xe040fb,
            )
            header.set_footer(text='Last updated: March 2026  \u2014  Staff: \U0001f39b\ufe0f Founder \u2022 \U0001f39a\ufe0f Producer \u2022 \U0001f6e1\ufe0f Stage Manager \u2022 \U0001f399\ufe0f Crew')
            await rules_ch.send(embed=header)
            await asyncio.sleep(0.4)

            rules = [
                ('\u00a7 1 \u2014 Respect', 0xe040fb,
                 'Treat every member with respect. Harassment, hate speech, targeted toxicity, '
                 'and discrimination of any kind will not be tolerated \u2014 including through DMs initiated from this server.'),
                ('\u00a7 2 \u2014 No Spam', 0x00e5ff,
                 'Avoid message spam, emoji flooding, gibberish, or repeated posting. '
                 'Keep conversations relevant to the channel you\'re in.'),
                ('\u00a7 3 \u2014 Safe for Work', 0x7c4dff,
                 'All content must be SFW. No explicit, graphic, violent, or disturbing material anywhere in the server.'),
                ('\u00a7 4 \u2014 No Self-Promotion', 0xe040fb,
                 'Do not advertise other Discord servers, social media accounts, or external services '
                 'without prior written approval from a \U0001f39b\ufe0f Founder or \U0001f39a\ufe0f Producer.'),
                ('\u00a7 5 \u2014 English Only', 0x00e5ff,
                 'This is an English-speaking server. Please keep all public conversations in English '
                 'so every member can participate equally.'),
                ('\u00a7 6 \u2014 Discord Terms of Service', 0x7c4dff,
                 'All members must comply with [Discord\u2019s Terms of Service](https://discord.com/terms) '
                 'and [Community Guidelines](https://discord.com/guidelines) at all times.'),
                ('\u00a7 7 \u2014 Follow Staff', 0xe040fb,
                 'Follow instructions from \U0001f39b\ufe0f Founders, \U0001f39a\ufe0f Producers, '
                 '\U0001f6e1\ufe0f Stage Managers, and \U0001f399\ufe0f Crew at all times. '
                 'If you disagree with a decision, address it calmly via DM \u2014 not publicly.'),
                ('\u00a7 8 \u2014 No Drama', 0x00e5ff,
                 'Keep personal conflicts out of public channels. Contact staff if you have a dispute '
                 'with another member. Escalating publicly benefits nobody.'),
                ('\u00a7 9 \u2014 Stay On Topic', 0x7c4dff,
                 'Use channels for their intended purpose. Music talk goes in music channels, '
                 'bot commands in \U0001f916\u2503bot-chat, support requests in the support channels.'),
            ]

            for i, (title, colour, desc) in enumerate(rules):
                embed = discord.Embed(title=title, description=desc, color=colour)
                await rules_ch.send(embed=embed)
                await asyncio.sleep(0.3)

            footer_embed = discord.Embed(
                description=(
                    '\U0001f6e1\ufe0f **Enforcement**\n'
                    'Staff reserve the right to warn, mute, kick, or ban any member '
                    'whose behaviour disrupts the community, even if not explicitly covered above.\n\n'
                    '\U0001f4e7 **Report an issue** \u2014 DM any \U0001f6e1\ufe0f Stage Manager or use the support channels.\n'
                    '\U0001f3b5 **Enjoy the community** \u2014 discover music, share vibes, and have fun.'
                ),
                color=0x2c2f33,
            )
            footer_embed.set_footer(text='PopFusion \u2014 discover music. build community.')
            await rules_ch.send(embed=footer_embed)
            print(f'  [OK]    #{rules_ch.name} redesigned ({len(rules)+2} embeds)')

        # ── PHASE 4: FAQ Channel ──────────────────────────────────────────────
        print('\n' + '=' * 60)
        print('  PHASE 4 — #faq UPDATE')
        print('=' * 60)

        faq_ch = ch(g, 'faq')
        bug_ch   = ch(g, 'bug-report', 'bug')
        bill_ch  = ch(g, 'billing')
        feat_ch  = ch(g, 'feature')

        if faq_ch:
            await clear_bot_msgs(faq_ch, self.user)

            header = discord.Embed(
                title='\u2753 Frequently Asked Questions',
                description='Everything you need to know about PopFusion and Tainment+.',
                color=0xe040fb,
            )
            await faq_ch.send(embed=header)
            await asyncio.sleep(0.3)

            faqs = [
                ('How do I get started?',
                 'Use `t!daily` to claim your first coins, then `t!work` for more. '
                 'Type `t!help` for the full command list with categories.\n\n'
                 'Quick start: `t!daily` → `t!fish` → `t!shop` → `t!upgrade <tier>`'),

                ('What are the three currencies?',
                 '\U0001fa99 **Coins** \u2014 Earned from daily rewards, work, fishing, gambling. Spent in `t!shop coins`.\n'
                 '\U0001f48e **Gems** \u2014 Earned by winning games and selling rare fish. Spent in `t!shop gems`.\n'
                 '\U0001f3ab **Tokens** \u2014 Earned from duels, snap, scramble, daily streaks. Spent in `t!shop tokens`.'),

                ('How does fishing work?',
                 'Use `t!fish` to cast your line. Cooldown depends on your rod (15s basic → 3s Void rod).\n'
                 'Fish collect in your bag — use `t!sell all` to cash them in for coins, gems, and tokens.\n\n'
                 '**Rods:** `t!rods` to see all 11. Buy with `t!buy rod_silver` etc.\n'
                 '**Equip a specific rod:** `t!equip <rod_key>` — e.g. `t!equip rod_gold`\n'
                 '**Check stats:** `t!fishstats` | **Leaderboard:** `t!fishtop`'),

                ('What are the subscription tiers?',
                 '**Basic** (Free) \u2014 Economy, fishing, basic games, 150 daily coins.\n'
                 '**Vibe** ($1.99/mo) \u2014 All joke & story categories, music discovery, trivia, 200 daily coins, 1.2x XP.\n'
                 '**Premium** ($4.99/mo) \u2014 Hangman, Wordle, all mini-games, 350 daily coins, 1.5x XP.\n'
                 '**Pro** ($7.99/mo) \u2014 Blackjack, exclusive content, priority support, 3x XP, 500 daily coins.\n\n'
                 'Upgrade with `t!upgrade <tier>` | View perks with `t!tiers`'),

                ('How do I level up and earn roles?',
                 'Earn XP by chatting (60-second cooldown per message). Tier XP multipliers stack.\n'
                 'Milestone roles are auto-assigned:\n'
                 '\U0001f331 Newcomer (Lvl 5) \u2192 \U0001f3a7 Groover (10) \u2192 \U0001f4bf Fanatic (20) \u2192 \U0001f3b8 Headliner (30) \u2192 \u26a1 Icon (50)\n'
                 '\U0001f31f Superstar (75) \u2192 \U0001f3c6 Legend (100) \u2192 \U0001f30c Cosmic (150)\n\n'
                 'Check your level with `t!level`.'),

                ('How do I pick my genre lane?',
                 'Head to **#\U0001f3a4\u2503pick-your-lane** and react with the emoji for your genre(s). You can pick multiple!\n\n'
                 '\U0001f3a4 Pop  \u2022  \U0001f3b6 Hip-Hop  \u2022  \U0001f3b8 Rock  \u2022  \U0001f50a Electronic\n'
                 '\U0001f3b7 R\u0026B & Soul  \u2022  \U0001f3b9 Jazz  \u2022  \U0001f908 Country  \u2022  \U0001f483 Latin\n'
                 '\U0001f333 Indie  \u2022  \U0001f305 Lo-Fi\n\n'
                 'Unreact to remove a role. Roles are purely cosmetic interest tags.'),

                ('How does music discovery work?',
                 '`t!recommend` \u2014 3 random song picks (all tiers)\n'
                 '`t!genresearch <genre>` \u2014 5 picks for a specific genre — 16 genres available (Vibe+)\n'
                 '`t!moodsearch <mood>` \u2014 songs for hype / chill / sad / focus / party / workout (Vibe+)\n'
                 '`t!sharetrack <song> - <artist>` \u2014 share a track every 6 hours for coins\n'
                 '`t!hotsongs` \u2014 top 5 most shared tracks this week\n'
                 '`t!musictrivia` \u2014 4-option music quiz, earns coins & gems'),

                ('How do I report a bug or request a feature?',
                 f'Use the forms in the support channels:\n'
                 f'\U0001f41b Bug reports \u2192 {bug_ch.mention if bug_ch else "#\U0001f41b\u2503bug-reports"} (private to staff)\n'
                 f'\U0001f4b3 Billing issues \u2192 {bill_ch.mention if bill_ch else "#\U0001f4b3\u2503billing-support"} (private to admins)\n'
                 f'\u2b50 Feature ideas \u2192 {feat_ch.mention if feat_ch else "#\u2b50\u2503feature-requests"} (visible to everyone)'),
            ]

            for question, answer in faqs:
                embed = discord.Embed(title=question, description=answer, color=0x00e5ff)
                await faq_ch.send(embed=embed)
                await asyncio.sleep(0.4)

            print(f'  [OK]    #{faq_ch.name} updated ({len(faqs)} entries)')

        # ── PHASE 5: Support Form Panels ──────────────────────────────────────
        print('\n' + '=' * 60)
        print('  PHASE 5 — SUPPORT FORM PANELS')
        print('=' * 60)

        async def post_panel(channel, embed, view):
            if not channel:
                return
            await clear_bot_msgs(channel, self.user)
            await channel.send(embed=embed, view=view)
            print(f'  [OK]    #{channel.name}')

        # Bug reports
        await post_panel(
            ch(g, 'bug-report', 'bug'),
            discord.Embed(
                title='\U0001f41b Bug Report',
                description=(
                    'Found a bug? Help us fix it!\n\n'
                    'Click the button and fill in the short form. '
                    'Your report is sent **privately to staff** \u2014 no one else can see it.\n\n'
                    '**Include:**\n'
                    '\u2022 Command used\n'
                    '\u2022 What went wrong\n'
                    '\u2022 What you expected\n'
                    '\u2022 Steps to reproduce (optional)\n\n'
                    '*Reviewed by \U0001f6e1\ufe0f Stage Managers and above.*'
                ),
                color=0xED4245,
            ).set_footer(text='Reports are private to staff'),
            BugReportView(),
        )
        await asyncio.sleep(0.5)

        # Billing
        await post_panel(
            ch(g, 'billing'),
            discord.Embed(
                title='\U0001f4b3 Billing Support',
                description=(
                    'Having a payment or subscription issue?\n\n'
                    'Click the button. Your request is sent **privately to admins only**.\n\n'
                    '**We can help with:**\n'
                    '\u2022 Payment not processing\n'
                    '\u2022 Subscription not activating\n'
                    '\u2022 Wrong tier applied\n'
                    '\u2022 Refund requests\n'
                    '\u2022 Renewal problems\n\n'
                    '*Handled by \U0001f39b\ufe0f Founders and \U0001f39a\ufe0f Producers only.*'
                ),
                color=0xFEE75C,
            ).set_footer(text='Requests are private to admins'),
            BillingView(),
        )
        await asyncio.sleep(0.5)

        # Feature requests
        await post_panel(
            ch(g, 'feature'),
            discord.Embed(
                title='\u2b50 Feature Requests',
                description=(
                    'Have an idea that would make PopFusion better?\n\n'
                    'Click the button to submit your idea. '
                    'Requests are **posted publicly** so the community can see what\'s being suggested.\n\n'
                    '**Good requests include:**\n'
                    '\u2022 A clear feature name\n'
                    '\u2022 The problem it solves\n'
                    '\u2022 How you\'d use it\n\n'
                    '*Staff review all requests for future updates.*'
                ),
                color=0xEB459E,
            ).set_footer(text='Your ideas shape the community'),
            FeatureRequestView(),
        )

        print('\n' + '=' * 60)
        print('  ALL DONE')
        print('=' * 60)
        await self.close()


if __name__ == '__main__':
    client = MaintenanceClient()
    client.run(TOKEN, log_handler=None)
