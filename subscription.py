import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import config
import database as db

TIER_ORDER = {'Basic': 0, 'Vibe': 1, 'Premium': 2, 'Pro': 3}


def tier_embed(tier_name: str) -> discord.Embed:
    tier = config.SUBSCRIPTION_TIERS[tier_name]
    color = config.COLORS['gold'] if tier_name == 'Premium' else (config.COLORS['purple'] if tier_name == 'Pro' else config.COLORS['info'])
    embed = discord.Embed(title=f"{tier_name} Tier", color=color)
    embed.add_field(name="Price", value=f"${tier['price']:.2f}/month" if tier['price'] > 0 else "Free", inline=True)
    embed.add_field(name="Daily Coins", value=f"`{tier['daily_coins']}`", inline=True)
    embed.add_field(name="XP Multiplier", value=f"`{tier['xp_multiplier']}x`", inline=True)
    embed.add_field(name="Features", value="\n".join(f"- {f}" for f in tier['features']), inline=False)
    return embed


class Subscription(commands.Cog, name="Subscription"):
    """Manage your Tainment+ subscription tier."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='subscribe', description='View subscription tiers and pricing')
    async def subscribe(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)

        embed = discord.Embed(
            title="Tainment+ Subscriptions",
            description="Unlock more features with a premium tier.",
            color=config.COLORS['primary'],
        )

        for name, tier in config.SUBSCRIPTION_TIERS.items():
            price = f"${tier['price']:.2f}/mo" if tier['price'] > 0 else "Free"
            features = ', '.join(tier['features'][:3])
            embed.add_field(
                name=f"{name} — {price}",
                value=features + ("..." if len(tier['features']) > 3 else ""),
                inline=False,
            )

        embed.add_field(
            name="How to upgrade",
            value="Use `t!upgrade Vibe`, `t!upgrade Premium`, or `t!upgrade Pro`",
            inline=False,
        )
        embed.set_footer(text="Tainment+ | Use t!benefits for full comparison")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='tier', description='Check your current subscription tier')
    async def tier(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        sub = await db.get_subscription(target.id)

        tier_name = sub['tier'] if sub else 'Basic'
        color_map = {'Basic': config.COLORS['info'], 'Premium': config.COLORS['gold'], 'Pro': config.COLORS['purple']}

        embed = discord.Embed(
            title=f"{target.display_name}'s Subscription",
            color=color_map.get(tier_name, config.COLORS['primary']),
        )
        embed.add_field(name="Tier", value=f"**{tier_name}**", inline=True)

        if sub and sub['end_date']:
            end_dt = datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc)
            ts = int(end_dt.timestamp())
            status = "Active" if end_dt > datetime.now(timezone.utc) else "Expired"
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Expires", value=f"<t:{ts}:R>", inline=True)
        elif tier_name != 'Basic':
            embed.add_field(name="Status", value="Active", inline=True)

        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Use t!subscribe to see upgrade options")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='benefits', description='Compare all subscription tiers')
    async def benefits(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Tier Benefits Comparison",
            color=config.COLORS['primary'],
        )
        for name, tier in config.SUBSCRIPTION_TIERS.items():
            price = f"${tier['price']:.2f}/mo" if tier['price'] > 0 else "Free"
            lines = [
                f"Price: **{price}**",
                f"Daily coins: `{tier['daily_coins']}`",
                f"XP multiplier: `{tier['xp_multiplier']}x`",
            ] + [f"- {f}" for f in tier['features']]
            embed.add_field(name=name, value="\n".join(lines), inline=True)
        embed.set_footer(text="Upgrade with t!upgrade <tier>")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='upgrade', description='Upgrade your subscription tier')
    async def upgrade(self, ctx: commands.Context, tier: str):
        tier = tier.capitalize()
        if tier not in TIER_ORDER:
            tiers = ', '.join(f'`{t}`' for t in TIER_ORDER if t != 'Basic')
            await ctx.send(embed=discord.Embed(
                description=f"Invalid tier. Choose from: {tiers}",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        current = await db.get_tier(ctx.author.id)

        if TIER_ORDER[tier] <= TIER_ORDER[current]:
            await ctx.send(embed=discord.Embed(
                description=f"You're already on **{current}**. You can only upgrade.",
                color=config.COLORS['warning'],
            ))
            return

        # Route to payment
        payment_cog = ctx.bot.cogs.get('Payment')
        if payment_cog:
            await payment_cog.initiate_upgrade(ctx, tier)
        else:
            await ctx.send(embed=discord.Embed(
                description="Payment system unavailable. Please try again later.",
                color=config.COLORS['error'],
            ))

    @commands.hybrid_command(name='renew', description='Renew your subscription')
    async def renew(self, ctx: commands.Context, months: int = 1):
        if months not in (1, 3, 6, 12):
            await ctx.send(embed=discord.Embed(
                description="Valid renewal periods: `1`, `3`, `6`, `12` months.",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        current = await db.get_tier(ctx.author.id)

        if current == 'Basic':
            await ctx.send(embed=discord.Embed(
                description="You're on the free tier. Use `t!upgrade` to subscribe.",
                color=config.COLORS['warning'],
            ))
            return

        payment_cog = ctx.bot.cogs.get('Payment')
        if payment_cog:
            await payment_cog.initiate_renew(ctx, current, months)
        else:
            await ctx.send(embed=discord.Embed(
                description="Payment system unavailable.",
                color=config.COLORS['error'],
            ))

    @commands.hybrid_command(name='payment_history', aliases=['payhistory'], description='View your payment history')
    async def payment_history(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        records = await db.get_payment_history(ctx.author.id)

        if not records:
            await ctx.send(embed=discord.Embed(
                description="No payment history found.",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title="Payment History", color=config.COLORS['primary'])
        for rec in records:
            ts = int(datetime.fromisoformat(rec['created_at']).replace(tzinfo=timezone.utc).timestamp())
            embed.add_field(
                name=f"{rec['tier']} — ${rec['amount']:.2f}",
                value=f"Status: `{rec['status']}` | <t:{ts}:D>",
                inline=False,
            )
        embed.set_footer(text=f"Showing last {len(records)} payments")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Subscription(bot))
