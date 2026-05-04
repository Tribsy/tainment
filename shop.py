"""
Multi-currency shop.
Currencies:
  coins  (🪙) - general, earned from work / daily / gambling
  gems   (💎) - skill-based, earned from winning games
  tokens (🎫) - activity-based, earned from streaks / events / duels
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import config
import database as db
from fish_data import RODS as _FISH_RODS


CURRENCY_EMOJI = {'coins': '\U0001fa99', 'gems': '\U0001f48e', 'tokens': '\U0001f3ab'}
PRESTIGE_ROLE_NAME = '\u2728 Prestige'

# ── Shop catalogue ─────────────────────────────────────────────────────────────

# Items consumed on use — stackable, removed from inventory when triggered
CONSUMABLE_KEYS = frozenset({
    'daily_reset', 'work_reset', 'lucky_gamble', 'streak_shield',
    'fish_vacuum', 'streak_restore', 'bingo_doubler', 'fishing_radar',
})

SHOP: dict[str, dict] = {
    # ── Coin items ─────────────────────────────────────────────────────────────
    'xp_boost': {
        'name': 'XP Boost',
        'description': '2x XP gain for 1 hour',
        'currency': 'coins',
        'price': 500,
        'duration': 3600,
        'emoji': '\u26a1',
    },
    'daily_boost': {
        'name': 'Daily Boost',
        'description': '2x daily coins for 1 day',
        'currency': 'coins',
        'price': 1000,
        'duration': 86400,
        'emoji': '\U0001f4ab',
    },
    'luck_charm': {
        'name': 'Luck Charm',
        'description': '+20% gambling win chance for 30 min',
        'currency': 'coins',
        'price': 750,
        'duration': 1800,
        'emoji': '\U0001f340',
    },
    'rob_shield': {
        'name': 'Rob Shield',
        'description': 'Immune to rob attempts for 2 hours',
        'currency': 'coins',
        'price': 400,
        'duration': 7200,
        'emoji': '\U0001f6e1\ufe0f',
    },

    # ── Gem items ──────────────────────────────────────────────────────────────
    'vip_badge': {
        'name': 'VIP Badge',
        'description': 'Permanent VIP badge shown on your profile',
        'currency': 'gems',
        'price': 50,
        'duration': None,
        'emoji': '\U0001f451',
    },
    'streak_shield': {
        'name': 'Streak Shield',
        'description': 'Saves your daily streak once if you miss a day',
        'currency': 'gems',
        'price': 30,
        'duration': None,
        'emoji': '\U0001f6e1\ufe0f',
    },
    'double_tokens': {
        'name': 'Token Doubler',
        'description': '2x token earnings for 1 hour',
        'currency': 'gems',
        'price': 75,
        'duration': 3600,
        'emoji': '\u00d72',
    },
    'lucky_gamble': {
        'name': 'Lucky Gamble',
        'description': 'Your next gamble has a 65% win chance (1-time use)',
        'currency': 'gems',
        'price': 25,
        'duration': None,
        'emoji': '\U0001f3b0',
    },

    # ── Fishing Rods ───────────────────────────────────────────────────────────
    'rod_silver': {
        'name': 'Silver Rod',
        'description': 'Unlocks Uncommon/Rare fish. Cooldown 18s.',
        'currency': 'coins',
        'price': 1500,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_gold': {
        'name': 'Golden Rod',
        'description': 'Unlocks Epic fish tier. Cooldown 15s.',
        'currency': 'coins',
        'price': 5000,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_diamond': {
        'name': 'Diamond Rod',
        'description': 'Unlocks Legendary fish tier. Cooldown 12s.',
        'currency': 'gems',
        'price': 20,
        'duration': None,
        'emoji': '\U0001f48e',
    },
    'rod_pearl': {
        'name': 'Pearl Rod',
        'description': 'Unlocks Mythic fish tier. Cooldown 10s.',
        'currency': 'gems',
        'price': 45,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_crystal': {
        'name': 'Crystal Rod',
        'description': 'Unlocks Ancient fish tier. Cooldown 8s.',
        'currency': 'gems',
        'price': 100,
        'duration': None,
        'emoji': '\U0001f52e',
    },
    'rod_titanium': {
        'name': 'Titanium Rod',
        'description': 'Unlocks Celestial fish tier. Cooldown 6s.',
        'currency': 'tokens',
        'price': 50,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_quantum': {
        'name': 'Quantum Rod',
        'description': 'Unlocks Void fish tier. Cooldown 5s.',
        'currency': 'tokens',
        'price': 150,
        'duration': None,
        'emoji': '\u26a1',
    },
    'rod_obsidian': {
        'name': 'Obsidian Rod',
        'description': 'Enhanced Void catch rates. Cooldown 4s.',
        'currency': 'tokens',
        'price': 300,
        'duration': None,
        'emoji': '\u2b1b',
    },
    'rod_cosmic': {
        'name': 'Cosmic Rod',
        'description': 'Max Void tier rates. Cooldown 3s.',
        'currency': 'tokens',
        'price': 500,
        'duration': None,
        'emoji': '\U0001f30c',
    },
    'rod_void': {
        'name': 'Void Rod',
        'description': 'The ultimate rod. Highest Void catch rate. Cooldown 2s.',
        'currency': 'tokens',
        'price': 1000,
        'duration': None,
        'emoji': '\u25aa\ufe0f',
    },

    # ── More Coin items ────────────────────────────────────────────────────────
    'coin_magnet': {
        'name': 'Coin Magnet',
        'description': '+25% coins from work for 2 hours',
        'currency': 'coins',
        'price': 600,
        'duration': 7200,
        'emoji': '\U0001f9f2',
    },
    'premium_bait': {
        'name': 'Premium Bait',
        'description': '+40% rare fish chance for 1 hour',
        'currency': 'coins',
        'price': 800,
        'duration': 3600,
        'emoji': '\U0001fab1',
    },
    'gamble_shield': {
        'name': 'Gamble Shield',
        'description': 'Lose only half your bet on failed gambles for 24 hours',
        'currency': 'coins',
        'price': 350,
        'duration': 86400,
        'emoji': '\U0001f6e1\ufe0f',
    },

    # ── More Gem items ─────────────────────────────────────────────────────────
    'xp_surge': {
        'name': 'XP Surge',
        'description': '3x XP gain for 30 minutes (stacks with tier multiplier)',
        'currency': 'gems',
        'price': 40,
        'duration': 1800,
        'emoji': '\U0001f9e8',
    },
    'prestige_badge': {
        'name': 'Prestige Badge',
        'description': 'Permanent ✨ Prestige badge shown on your profile',
        'currency': 'gems',
        'price': 100,
        'duration': None,
        'emoji': '\u2728',
    },
    'gem_booster': {
        'name': 'Gem Booster',
        'description': '2x gems from games and fishing for 1 hour',
        'currency': 'gems',
        'price': 60,
        'duration': 3600,
        'emoji': '\U0001f48e',
    },

    # ── Token items ────────────────────────────────────────────────────────────
    'daily_reset': {
        'name': 'Daily Reset',
        'description': 'Instantly reset your daily cooldown (Single Use \u2014 use with `t!use daily_reset`)',
        'currency': 'tokens',
        'price': 20,
        'duration': None,
        'emoji': '\U0001f504',
    },
    'work_reset': {
        'name': 'Work Reset',
        'description': 'Instantly reset your work cooldown (Single Use \u2014 use with `t!use work_reset`)',
        'currency': 'tokens',
        'price': 10,
        'duration': None,
        'emoji': '\u23f0',
    },
    'game_lives': {
        'name': 'Extra Lives',
        'description': '+2 lives in Hangman and Wordle',
        'currency': 'tokens',
        'price': 15,
        'duration': 3600,
        'emoji': '\u2764\ufe0f',
    },
    'bonus_round': {
        'name': 'Bonus Round',
        'description': '+5 extra questions in Math Quiz (earns more gems)',
        'currency': 'tokens',
        'price': 12,
        'duration': 3600,
        'emoji': '\u2795',
    },
    'typerace_boost': {
        'name': 'Typerace Booster',
        'description': '+50% coins from typerace wins for 1 hour',
        'currency': 'tokens',
        'price': 18,
        'duration': 3600,
        'emoji': '\u2328\ufe0f',
    },
    'fish_vacuum': {
        'name': 'Fish Vacuum',
        'description': 'Auto-discard all junk fish on your next t!fish (Single Use — activates automatically)',
        'currency': 'tokens',
        'price': 8,
        'duration': None,
        'emoji': '\U0001f9f9',
    },
    'streak_restore': {
        'name': 'Streak Restore',
        'description': 'Restore your daily streak to its previous value (Single Use — use with `t!use streak_restore`)',
        'currency': 'tokens',
        'price': 25,
        'duration': None,
        'emoji': '\U0001f504',
    },

    # ── Profile Customization ──────────────────────────────────────────────────
    'profile_banner_blue': {
        'name': 'Blue Profile Banner',
        'description': 'Sets your profile banner to ocean blue',
        'currency': 'coins',
        'price': 2000,
        'duration': None,
        'emoji': '\U0001f7e6',
    },
    'profile_banner_red': {
        'name': 'Red Profile Banner',
        'description': 'Sets your profile banner to fiery red',
        'currency': 'coins',
        'price': 2000,
        'duration': None,
        'emoji': '\U0001f7e5',
    },
    'profile_banner_gold': {
        'name': 'Gold Profile Banner',
        'description': 'Sets your profile banner to golden yellow',
        'currency': 'gems',
        'price': 30,
        'duration': None,
        'emoji': '\U0001f7e8',
    },
    'profile_banner_purple': {
        'name': 'Purple Profile Banner',
        'description': 'Sets your profile banner to royal purple',
        'currency': 'gems',
        'price': 30,
        'duration': None,
        'emoji': '\U0001f7ea',
    },
    'profile_banner_void': {
        'name': 'Void Profile Banner',
        'description': 'Sets your profile banner to deep void black',
        'currency': 'tokens',
        'price': 40,
        'duration': None,
        'emoji': '\u25aa\ufe0f',
    },
    'profile_frame_gold': {
        'name': 'Gold Avatar Frame',
        'description': 'Adds a golden frame around your avatar on the profile card',
        'currency': 'gems',
        'price': 50,
        'duration': None,
        'emoji': '\u2b50',
    },
    'profile_frame_cosmic': {
        'name': 'Cosmic Avatar Frame',
        'description': 'Adds an animated cosmic frame to your profile',
        'currency': 'tokens',
        'price': 80,
        'duration': None,
        'emoji': '\U0001f30c',
    },

    # ── Special / Utility ──────────────────────────────────────────────────────
    'fishing_radar': {
        'name': 'Fish Radar',
        'description': 'Preview your next 5 catches with exact fish names and values (Single Use — use with `t!radar`)',
        'currency': 'gems',
        'price': 15,
        'duration': None,
        'emoji': '\U0001f4e1',
    },
    'coin_surge': {
        'name': 'Coin Surge',
        'description': '3x coins from work and gambling for 30 minutes',
        'currency': 'gems',
        'price': 45,
        'duration': 1800,
        'emoji': '\U0001fa99',
    },
    'rob_boost': {
        'name': 'Rob Boost',
        'description': '+20% rob success rate for 1 hour',
        'currency': 'coins',
        'price': 500,
        'duration': 3600,
        'emoji': '\U0001f977',
    },
    'piggy_bank': {
        'name': 'Piggy Bank',
        'description': 'Protects up to 1000 coins from rob attempts (permanent)',
        'currency': 'coins',
        'price': 3000,
        'duration': None,
        'emoji': '\U0001f437',
    },
    'mystery_box': {
        'name': 'Mystery Box',
        'description': 'Contains a random item (could be anything!)',
        'currency': 'coins',
        'price': 1200,
        'duration': None,
        'emoji': '\U0001f381',
    },
    'fishing_magnet': {
        'name': 'Fishing Magnet',
        'description': 'Auto-sell all Trash tier fish on catch for 2 hours',
        'currency': 'tokens',
        'price': 20,
        'duration': 7200,
        'emoji': '\U0001f9f2',
    },

    # ── Music Items ────────────────────────────────────────────────────────────
    'music_hint': {
        'name': 'Lyrics Hint',
        'description': 'Reveals artist initial in lyricsguess/namethetune',
        'currency': 'coins',
        'price': 150,
        'duration': None,
        'emoji': '\U0001f4a1',
    },
    'trivia_skip': {
        'name': 'Trivia Skip',
        'description': 'Skip a music trivia question without penalty (1-time use)',
        'currency': 'coins',
        'price': 200,
        'duration': None,
        'emoji': '\u23ed\ufe0f',
    },
    'hot_boost': {
        'name': 'Hot Boost',
        'description': 'Your sharetrack contributions count double for 1 hour',
        'currency': 'coins',
        'price': 500,
        'duration': 3600,
        'emoji': '\U0001f525',
    },
    'bingo_doubler': {
        'name': 'Bingo Doubler',
        'description': '2 free pre-marked squares in Music Bingo (1-time use)',
        'currency': 'coins',
        'price': 800,
        'duration': None,
        'emoji': '\U0001f3b0',
    },
    'music_badge': {
        'name': 'Music Fanatic Badge',
        'description': 'Permanent \U0001f3b5 Music Fanatic badge on your profile',
        'currency': 'gems',
        'price': 40,
        'duration': None,
        'emoji': '\U0001f3b5',
    },
    'streak_amp': {
        'name': 'Streak Amplifier',
        'description': 'Music activity streak counts double for 24 hours',
        'currency': 'gems',
        'price': 55,
        'duration': 86400,
        'emoji': '\U0001f525',
    },
    'genre_unlock': {
        'name': 'Genre Pass',
        'description': 'Unlocks genresearch & moodsearch permanently for Basic users',
        'currency': 'gems',
        'price': 30,
        'duration': None,
        'emoji': '\U0001f3b6',
    },
    'wrapped_token': {
        'name': 'Wrapped Token',
        'description': 'Generate an early Music Wrapped mid-month',
        'currency': 'gems',
        'price': 20,
        'duration': None,
        'emoji': '\U0001f381',
    },
    'dj_crown': {
        'name': 'DJ Crown',
        'description': 'Permanent \U0001f451 DJ Crown badge + 10% music coin bonus',
        'currency': 'tokens',
        'price': 60,
        'duration': None,
        'emoji': '\U0001f451',
    },
    'playlist_slot': {
        'name': 'Playlist Slot',
        'description': '+1 permanent extra playlist slot',
        'currency': 'tokens',
        'price': 25,
        'duration': None,
        'emoji': '\U0001f4dc',
    },
    'queue_priority': {
        'name': 'Queue Priority',
        'description': 'Your song requests go to position 2 for 2 hours',
        'currency': 'tokens',
        'price': 35,
        'duration': 7200,
        'emoji': '\u23e9',
    },
    'trivia_surge': {
        'name': 'Trivia Surge',
        'description': '2x coin + gem rewards from all music trivia for 30 min',
        'currency': 'tokens',
        'price': 30,
        'duration': 1800,
        'emoji': '\u26a1',
    },
}


async def _grant_prestige_role(ctx: commands.Context) -> bool:
    if not ctx.guild or not ctx.guild.me.guild_permissions.manage_roles:
        return False

    role = discord.utils.get(ctx.guild.roles, name=PRESTIGE_ROLE_NAME)
    if role is None:
        try:
            role = await ctx.guild.create_role(
                name=PRESTIGE_ROLE_NAME,
                color=discord.Color(0xf1c40f),
                mentionable=False,
                reason='Tainment+ prestige badge role',
            )
        except discord.HTTPException:
            return False

    if role in ctx.author.roles:
        return True

    if role >= ctx.guild.me.top_role:
        return False

    try:
        await ctx.author.add_roles(role, reason='Purchased Prestige Badge')
        return True
    except discord.HTTPException:
        return False

SECTION_EMOJIS = {'coins': '\U0001fa99', 'gems': '\U0001f48e', 'tokens': '\U0001f3ab'}


def _items_by_currency(currency: str) -> dict[str, dict]:
    return {k: v for k, v in SHOP.items() if v['currency'] == currency}


def _dur_str(seconds: int | None) -> str:
    if seconds is None:
        return 'Permanent'
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    return f"{seconds // 60}m"


# ── Shop View ─────────────────────────────────────────────────────────────────

class ShopCurrencySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Coin Shop', value='coins', emoji='\U0001fa99', description='Buy with coins'),
            discord.SelectOption(label='Gem Shop', value='gems', emoji='\U0001f48e', description='Buy with gems'),
            discord.SelectOption(label='Token Shop', value='tokens', emoji='\U0001f3ab', description='Buy with tokens'),
        ]
        super().__init__(placeholder='Choose a shop section...', options=options)

    async def callback(self, interaction: discord.Interaction):
        currency = self.values[0]
        embed = _shop_embed(currency)
        await interaction.response.edit_message(embed=embed, view=self.view)


class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ShopCurrencySelect())


def _shop_embed(currency: str) -> discord.Embed:
    items = _items_by_currency(currency)
    emoji = SECTION_EMOJIS[currency]
    embed = discord.Embed(
        title=f"{emoji} {currency.capitalize()} Shop",
        description=f"Use `t!buy <item_id>` to purchase.\nCheck your {currency} with `t!balance`.",
        color=config.COLORS['gold'] if currency == 'coins' else config.COLORS['purple'] if currency == 'gems' else config.COLORS['info'],
    )
    for key, item in items.items():
        dur = "Single Use" if key in CONSUMABLE_KEYS else _dur_str(item['duration'])
        # Rod items: append fishing level requirement
        rod_key = key[4:] if key.startswith('rod_') else None
        lvl_note = ""
        if rod_key and rod_key in _FISH_RODS:
            min_lvl = _FISH_RODS[rod_key].get('min_level', 1)
            if min_lvl > 1:
                lvl_note = f" | **Req. Fishing Lvl {min_lvl}**"
        embed.add_field(
            name=f"{item['emoji']} {item['name']}  —  {item['price']:,} {emoji}",
            value=f"{item['description']}{lvl_note}  *({dur})*\n**Buy:** `t!buy {key}`",
            inline=False,
        )
    embed.set_footer(text="Active items are shown in t!inventory and t!profile")
    return embed


# ── Shop Cog ──────────────────────────────────────────────────────────────────

class Shop(commands.Cog, name="Shop"):
    """Multi-currency item shop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='shop', description='Browse the item shop (coins / gems / tokens)')
    async def shop_cmd(self, ctx: commands.Context, section: str = None):
        if section and section.lower() in ('coins', 'gems', 'tokens'):
            embed = _shop_embed(section.lower())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Tainment+ Shop",
                description=(
                    "Three currencies, three shops!\n\n"
                    f"\U0001fa99 **Coins** — earn from daily, work, gambling\n"
                    f"\U0001f48e **Gems** — earn by winning games & skill challenges\n"
                    f"\U0001f3ab **Tokens** — earn from duels, snap, scramble, streaks\n\n"
                    "Use the dropdown or `t!shop coins/gems/tokens`"
                ),
                color=config.COLORS['primary'],
            )
            view = ShopView()
            await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name='buy', description='Buy an item from the shop')
    async def buy(self, ctx: commands.Context, *, item: str):
        item_key = item.lower().strip().replace(' ', '_')
        if item_key not in SHOP:
            # Try fuzzy: find keys that contain the search term
            matches = [k for k in SHOP if item.lower() in k or item.lower() in SHOP[k]['name'].lower()]
            if len(matches) == 1:
                item_key = matches[0]
            else:
                keys = ', '.join(f'`{k}`' for k in SHOP)
                await ctx.send(embed=discord.Embed(
                    description=f"Item not found. Available: {keys}",
                    color=config.COLORS['error'],
                ))
                return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        item_data = SHOP[item_key]
        currency = item_data['currency']
        price = item_data['price']

        bal = await db.get_currency(ctx.author.id, currency)
        if bal < price:
            emoji = CURRENCY_EMOJI[currency]
            await ctx.send(embed=discord.Embed(
                description=f"You need `{price:,}` {emoji} but only have `{bal:,}` {emoji}.",
                color=config.COLORS['error'],
            ))
            return

        # Permanent items — check already owned
        _consumables = CONSUMABLE_KEYS
        if item_data['duration'] is None and item_key not in _consumables:
            if await db.has_active_item(ctx.author.id, item_key):
                await ctx.send(embed=discord.Embed(
                    description="You already own this item.",
                    color=config.COLORS['warning'],
                ))
                return

        expires_at = None
        if item_data['duration']:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=item_data['duration'])).isoformat()

        await db.spend_currency(ctx.author.id, currency, price)

        # Mystery box: open immediately, never stored in inventory
        if item_key == 'mystery_box':
            prize_label, prize_emoji = await _open_mystery_box(ctx.author.id)
            await ctx.send(embed=discord.Embed(
                title="📦 Mystery Box Opened!",
                description=(
                    f"You spent **1,200** 🪙 and cracked open a Mystery Box...\n\n"
                    f"{prize_emoji} You got: **{prize_label}**!"
                ),
                color=config.COLORS['gold'],
            ))
            return

        await db.add_inventory_item(ctx.author.id, item_key, expires_at, allow_stack=item_key in _consumables)
        prestige_role_granted = False
        if item_key == 'prestige_badge':
            prestige_role_granted = await _grant_prestige_role(ctx)

        emoji = CURRENCY_EMOJI[currency]
        extra_note = "\nRole granted: **✨ Prestige**" if prestige_role_granted else ""
        embed = discord.Embed(
            title="Purchase successful!",
            description=(
                f"Bought **{item_data['name']}** for `{price:,}` {emoji}\n"
                f"{item_data['description']}{extra_note}"
            ),
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='use', description='Use a consumable item from your inventory')
    async def use_item(self, ctx: commands.Context, item_key: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        item_key = item_key.lower()

        _use_handlers = {
            'daily_reset':    _apply_daily_reset,
            'work_reset':     _apply_work_reset,
            'streak_restore': _apply_streak_restore,
        }
        if item_key not in _use_handlers:
            await ctx.send(embed=discord.Embed(
                description=f"`{item_key}` is not a usable consumable.",
                color=config.COLORS['error'],
            ))
            return

        removed = await db.remove_inventory_item(ctx.author.id, item_key)
        if not removed:
            item_name = SHOP_ITEMS.get(item_key, {}).get('name', item_key)
            await ctx.send(embed=discord.Embed(
                description=f"You don't have a **{item_name}** in your inventory. Buy one with `t!buy {item_key}`.",
                color=config.COLORS['error'],
            ))
            return

        item_name = SHOP_ITEMS[item_key]['name']
        if item_key == 'streak_restore':
            prev = await _apply_streak_restore(ctx.author.id)
            desc = (
                f"Your daily streak has been restored to **{prev} days**! Item removed from inventory."
                if prev else
                "No saved streak to restore (streak hadn't reset recently). Item removed from inventory."
            )
        else:
            await _use_handlers[item_key](ctx.author.id)
            desc = f"Used **{item_name}** — cooldown reset. Item removed from inventory."

        await ctx.send(embed=discord.Embed(
            title="Item Used!",
            description=desc,
            color=config.COLORS['success'],
        ))

    @commands.hybrid_command(name='balance', aliases=['bal'], description='Check your currency balances')
    async def balance(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        eco = await db.get_economy(target.id)

        coins = eco['coins'] if eco else 0
        gems = eco['gems'] if eco else 0
        tokens = eco['tokens'] if eco else 0
        total_earned = eco['total_earned'] if eco else 0

        embed = discord.Embed(
            title=f"{target.display_name}'s Wallet",
            color=config.COLORS['gold'],
        )
        embed.add_field(name="\U0001fa99 Coins", value=f"`{coins:,}`", inline=True)
        embed.add_field(name="\U0001f48e Gems", value=f"`{gems:,}`", inline=True)
        embed.add_field(name="\U0001f3ab Tokens", value=f"`{tokens:,}`", inline=True)
        embed.add_field(name="Total Coins Earned", value=f"`{total_earned:,}`", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Earn gems by winning games | Tokens from duels & events")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='inventory', aliases=['inv'], description='View your active items')
    async def inventory(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        items = await db.get_inventory(target.id)

        now = datetime.now(timezone.utc)
        item_groups = {}  # key -> {name, desc, count, time_str (oldest expiry)}

        for row in items:
            key = row['item_key']
            item_data = SHOP.get(key)
            if not item_data:
                continue

            # Check if expired
            if row['expires_at']:
                exp = datetime.fromisoformat(row['expires_at']).replace(tzinfo=timezone.utc)
                if exp < now:
                    continue
                remaining = int((exp - now).total_seconds())
                h, s = divmod(remaining, 3600)
                m = s // 60
                time_str = f"Expires in {h}h {m}m"
            else:
                time_str = "Permanent"

            # Group by key
            if key not in item_groups:
                item_groups[key] = {
                    'name': item_data['name'],
                    'desc': item_data['description'],
                    'count': 0,
                    'time_str': time_str,
                }
            item_groups[key]['count'] += 1
            # Update to earliest expiry time if this one expires sooner
            if time_str != "Permanent" and item_groups[key]['time_str'] == "Permanent":
                item_groups[key]['time_str'] = time_str
            elif time_str != "Permanent" and item_groups[key]['time_str'] != "Permanent":
                # Keep the one that expires sooner (shows first)
                pass

        if not item_groups:
            await ctx.send(embed=discord.Embed(
                description=f"{target.display_name} has no active items. Visit `t!shop`!",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=config.COLORS['primary'])
        for key, group in item_groups.items():
            count_prefix = f"{group['count']}x " if group['count'] > 1 else ""
            name = f"{count_prefix}{group['name']}"
            value = f"{group['desc']}\n*{group['time_str']}*"
            embed.add_field(name=name, value=value, inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='transfer', aliases=['give', 'pay'], description='Transfer coins to another user')
    async def transfer(self, ctx: commands.Context, target: discord.Member, amount: int, currency: str = 'coins'):
        currency = currency.lower()
        if currency not in CURRENCY_EMOJI:
            await ctx.send(embed=discord.Embed(
                description="Currency must be `coins`, `gems`, or `tokens`.",
                color=config.COLORS['error'],
            ))
            return
        if target.id == ctx.author.id or target.bot:
            await ctx.send(embed=discord.Embed(description="Invalid target.", color=config.COLORS['error']))
            return
        if amount <= 0:
            await ctx.send(embed=discord.Embed(description="Amount must be positive.", color=config.COLORS['error']))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_user(target.id, target.name)
        bal = await db.get_currency(ctx.author.id, currency)

        if amount > bal:
            emoji = CURRENCY_EMOJI[currency]
            await ctx.send(embed=discord.Embed(
                description=f"You only have `{bal:,}` {emoji}.",
                color=config.COLORS['error'],
            ))
            return

        await db.spend_currency(ctx.author.id, currency, amount)
        await db.earn_currency(target.id, currency, amount)

        emoji = CURRENCY_EMOJI[currency]
        embed = discord.Embed(
            title="Transfer complete!",
            description=f"Sent **{amount:,}** {emoji} to {target.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='removeitem', description='[OWNER] Remove an item from a user\'s inventory')
    @commands.is_owner()
    async def removeitem(self, ctx: commands.Context, user: discord.Member, *, item_key: str):
        """Remove a single instance of an item from a user's inventory. Owner-only."""
        item_key = item_key.strip().lower()
        
        # Validate item exists in shop
        if item_key not in SHOP:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Item `{item_key}` not found in shop.",
                color=config.COLORS['error'],
            ))
            return
        
        await db.ensure_user(user.id, user.name)
        
        # Try to remove the item
        success = await db.remove_inventory_item(user.id, item_key)
        
        if success:
            item_name = SHOP[item_key]['name']
            await ctx.send(embed=discord.Embed(
                description=f"✅ Removed **{item_name}** from {user.mention}'s inventory.",
                color=config.COLORS['success'],
            ))
        else:
            item_name = SHOP[item_key]['name']
            await ctx.send(embed=discord.Embed(
                description=f"❌ {user.mention} doesn't have **{item_name}** in their inventory.",
                color=config.COLORS['error'],
            ))


async def _apply_daily_reset(user_id: int):
    await db.update_economy_field(user_id, last_daily=None, daily_streak=0)


async def _apply_work_reset(user_id: int):
    await db.update_economy_field(user_id, last_work=None)


async def _apply_streak_restore(user_id: int) -> int:
    """Restore previous streak. Returns the restored value (0 if nothing to restore)."""
    eco = await db.get_economy(user_id)
    if not eco:
        return 0
    prev = eco['previous_daily_streak'] if 'previous_daily_streak' in eco.keys() else 0
    if prev and prev > 0:
        await db.update_economy_field(user_id, daily_streak=prev, previous_daily_streak=0)
        return prev
    return 0


# Mystery box prize pool: (type, value_or_key, label, emoji, weight)
_MYSTERY_PRIZES = [
    ('coins',  300,           '300 Coins',        '🪙', 20),
    ('coins',  600,           '600 Coins',        '🪙', 17),
    ('coins',  1000,          '1,000 Coins',      '🪙', 13),
    ('coins',  2500,          '2,500 Coins',      '🪙',  7),
    ('coins',  6000,          '6,000 Coins',      '🪙',  2),
    ('gems',   10,            '10 Gems',          '💎', 16),
    ('gems',   25,            '25 Gems',          '💎', 10),
    ('gems',   60,            '60 Gems',          '💎',  4),
    ('tokens', 20,            '20 Tokens',        '🎫', 16),
    ('tokens', 50,            '50 Tokens',        '🎫',  9),
    ('tokens', 120,           '120 Tokens',       '🎫',  4),
    ('item',   'premium_bait','Premium Bait',     '🪱',  8),
    ('item',   'xp_boost',    'XP Boost',         '⚡',  7),
    ('item',   'luck_charm',  'Luck Charm',       '🍀',  6),
    ('item',   'rob_shield',  'Rob Shield',       '🛡️',  5),
    ('item',   'coin_magnet', 'Coin Magnet',      '🧲',  5),
    ('item',   'lucky_gamble','Lucky Gamble',     '🎰',  5),
    ('item',   'daily_reset', 'Daily Reset',      '🔄',  4),
    ('item',   'work_reset',  'Work Reset',       '⏰',  4),
    ('item',   'streak_shield','Streak Shield',   '🛡️',  3),
    ('item',   'xp_surge',    'XP Surge',         '🧨',  3),
    ('item',   'rod_silver',  'Silver Rod',       '🎣',  2),
    ('item',   'rod_gold',    'Golden Rod',       '🎣',  1),
]


async def _open_mystery_box(user_id: int) -> tuple[str, str]:
    """Roll a mystery box prize, grant it, return (label, emoji)."""
    import random
    weights = [p[4] for p in _MYSTERY_PRIZES]
    prize = random.choices(_MYSTERY_PRIZES, weights=weights, k=1)[0]
    kind, value, label, emoji, _ = prize

    if kind == 'coins':
        await db.earn_currency(user_id, 'coins', value)
    elif kind == 'gems':
        await db.earn_currency(user_id, 'gems', value)
    elif kind == 'tokens':
        await db.earn_currency(user_id, 'tokens', value)
    elif kind == 'item':
        await db.add_inventory_item(user_id, value, allow_stack=True)

    return label, emoji


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
