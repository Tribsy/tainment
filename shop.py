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


CURRENCY_EMOJI = {'coins': '\U0001fa99', 'gems': '\U0001f48e', 'tokens': '\U0001f3ab'}

# ── Shop catalogue ─────────────────────────────────────────────────────────────

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
        'description': 'Your next gamble has a 65% win chance',
        'currency': 'gems',
        'price': 25,
        'duration': None,
        'emoji': '\U0001f3b0',
    },

    # ── Fishing Rods ───────────────────────────────────────────────────────────
    'rod_silver': {
        'name': 'Silver Fishing Rod',
        'description': '+30% uncommon fish / +50% rare fish chance',
        'currency': 'coins',
        'price': 1500,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_gold': {
        'name': 'Golden Fishing Rod',
        'description': '+60% uncommon / +120% rare / +50% legendary fish chance',
        'currency': 'coins',
        'price': 5000,
        'duration': None,
        'emoji': '\U0001f3a3',
    },
    'rod_diamond': {
        'name': 'Diamond Fishing Rod',
        'description': '+100% rare / +200% legendary fish + 10s shorter cooldown',
        'currency': 'gems',
        'price': 20,
        'duration': None,
        'emoji': '\U0001f48e',
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
    'fishing_bait': {
        'name': 'Premium Bait',
        'description': '+40% rare fish chance for 10 casts',
        'currency': 'coins',
        'price': 800,
        'duration': None,
        'emoji': '\U0001fab1',
    },
    'gamble_shield': {
        'name': 'Gamble Shield',
        'description': 'Lose only half your bet on your next failed gamble',
        'currency': 'coins',
        'price': 350,
        'duration': None,
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
        'description': 'Instantly reset your daily cooldown',
        'currency': 'tokens',
        'price': 20,
        'duration': None,
        'emoji': '\U0001f504',
    },
    'work_reset': {
        'name': 'Work Reset',
        'description': 'Instantly reset your work cooldown',
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
        'description': 'Auto-sell all junk fish on your next t!fish (no bag clutter)',
        'currency': 'tokens',
        'price': 8,
        'duration': None,
        'emoji': '\U0001f9f9',
    },
    'streak_restore': {
        'name': 'Streak Restore',
        'description': 'Restore your daily streak to its previous value once',
        'currency': 'tokens',
        'price': 25,
        'duration': None,
        'emoji': '\U0001f504',
    },
}

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
        embed.add_field(
            name=f"{item['emoji']} {item['name']}  —  {item['price']:,} {emoji}",
            value=f"{item['description']}  *({_dur_str(item['duration'])})*\n**Buy:** `t!buy {key}`",
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

        # Special handling for consumable one-use items
        if item_key == 'daily_reset':
            await _apply_daily_reset(ctx.author.id)
        elif item_key == 'work_reset':
            await _apply_work_reset(ctx.author.id)

        # Permanent items — check already owned
        if item_data['duration'] is None and item_key not in ('daily_reset', 'work_reset', 'lucky_gamble'):
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
        await db.add_inventory_item(ctx.author.id, item_key, expires_at)

        emoji = CURRENCY_EMOJI[currency]
        embed = discord.Embed(
            title="Purchase successful!",
            description=(
                f"Bought **{item_data['name']}** for `{price:,}` {emoji}\n"
                f"{item_data['description']}"
            ),
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

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
        active = []
        for row in items:
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
            key = row['item_key']
            item_data = SHOP.get(key)
            if item_data:
                active.append((item_data['name'], item_data['description'], time_str))

        if not active:
            await ctx.send(embed=discord.Embed(
                description=f"{target.display_name} has no active items. Visit `t!shop`!",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=config.COLORS['primary'])
        for name, desc, time_str in active:
            embed.add_field(name=name, value=f"{desc}\n*{time_str}*", inline=True)
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


async def _apply_daily_reset(user_id: int):
    await db.update_economy_field(user_id, last_daily=None, daily_streak=0)


async def _apply_work_reset(user_id: int):
    await db.update_economy_field(user_id, last_work=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
