import discord
from discord.ext import commands
import csv
import io
from datetime import datetime, timezone, timedelta
import logging
import config
import database as db

logger = logging.getLogger('tainment.admin')

TIER_ORDER = {'Basic': 0, 'Vibe': 1, 'Premium': 2, 'Pro': 3}


class AdminSubscription(commands.Cog, name="Admin"):
    """Administrative subscription management. Requires Administrator permission."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        return ctx.author.guild_permissions.administrator

    @commands.command(name='subscribers', aliases=['subs'])
    async def subscribers(self, ctx: commands.Context, tier: str = None):
        """List all subscribers, optionally filtered by tier."""
        if tier:
            tier = tier.capitalize()
            if tier not in TIER_ORDER:
                await ctx.send(embed=discord.Embed(
                    description=f"Invalid tier. Use: {', '.join(f'`{t}`' for t in TIER_ORDER)}",
                    color=config.COLORS['error'],
                ))
                return

        rows = await db.get_all_subscribers(tier)
        if not rows:
            await ctx.send(embed=discord.Embed(description="No subscribers found.", color=config.COLORS['warning']))
            return

        pages = []
        page_size = 10
        for i in range(0, len(rows), page_size):
            chunk = rows[i:i + page_size]
            lines = []
            for row in chunk:
                exp = f" | exp: {row['end_date'][:10]}" if row['end_date'] else ""
                lines.append(f"`{row['user_id']}` — **{row['tier']}** — {row['username']}{exp}")
            pages.append("\n".join(lines))

        embed = discord.Embed(
            title=f"Subscribers{' — ' + tier if tier else ''} ({len(rows)} total)",
            description=pages[0],
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"Page 1/{len(pages)}")
        msg = await ctx.send(embed=embed)

        if len(pages) > 1:
            await msg.add_reaction('\u25c0')
            await msg.add_reaction('\u25b6')
            current = 0

            def check(r, u):
                return u == ctx.author and r.message.id == msg.id and str(r.emoji) in ('\u25c0', '\u25b6')

            import asyncio
            while True:
                try:
                    reaction, _ = await ctx.bot.wait_for('reaction_add', check=check, timeout=60)
                except asyncio.TimeoutError:
                    break
                if str(reaction.emoji) == '\u25b6':
                    current = min(current + 1, len(pages) - 1)
                else:
                    current = max(current - 1, 0)
                embed.description = pages[current]
                embed.set_footer(text=f"Page {current+1}/{len(pages)}")
                await msg.edit(embed=embed)

    @commands.command(name='export_subscribers', aliases=['exportsubs'])
    async def export_subscribers(self, ctx: commands.Context):
        """Export subscriber list as CSV."""
        rows = await db.get_all_subscribers()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_id', 'username', 'tier', 'start_date', 'end_date'])
        for row in rows:
            writer.writerow([
                row['user_id'], row['username'], row['tier'],
                row['start_date'], row['end_date'],
            ])
        output.seek(0)
        now = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        file = discord.File(fp=io.BytesIO(output.read().encode()), filename=f"subscribers_{now}.csv")
        await ctx.send(file=file, embed=discord.Embed(
            description=f"Exported **{len(rows)}** subscriber records.",
            color=config.COLORS['success'],
        ))

    @commands.command(name='view_subscription', aliases=['viewsub'])
    async def view_subscription(self, ctx: commands.Context, user: discord.Member):
        """View detailed subscription info for a user."""
        sub = await db.get_subscription(user.id)
        if not sub:
            await ctx.send(embed=discord.Embed(description="User not registered.", color=config.COLORS['error']))
            return

        history = await db.get_subscription_history(user.id, limit=5)
        payments = await db.get_payment_history(user.id, limit=3)

        embed = discord.Embed(
            title=f"Subscription — {user.display_name}",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Tier", value=sub['tier'], inline=True)
        embed.add_field(name="Start Date", value=sub['start_date'][:10] if sub['start_date'] else "N/A", inline=True)
        embed.add_field(name="End Date", value=sub['end_date'][:10] if sub['end_date'] else "Indefinite", inline=True)
        embed.add_field(name="Grace Period End", value=sub['grace_period_end'][:10] if sub['grace_period_end'] else "N/A", inline=True)

        if history:
            hist_lines = [f"`{h['changed_at'][:10]}` {h['old_tier']} → **{h['new_tier']}**" for h in history]
            embed.add_field(name="Recent History", value="\n".join(hist_lines), inline=False)

        if payments:
            pay_lines = [f"`${p['amount']:.2f}` {p['tier']} ({p['months']}mo) — `{p['status']}`" for p in payments]
            embed.add_field(name="Recent Payments", value="\n".join(pay_lines), inline=False)

        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='admin_upgrade', aliases=['aupgrade'])
    async def admin_upgrade(self, ctx: commands.Context, user: discord.Member, tier: str, months: int = 1):
        """Manually set a user's subscription tier."""
        tier = tier.capitalize()
        if tier not in TIER_ORDER:
            await ctx.send(embed=discord.Embed(
                description=f"Invalid tier: {', '.join(TIER_ORDER)}",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(user.id, user.name)
        old_tier = await db.get_tier(user.id)
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=months * 30)
        grace_end = end_date + timedelta(days=3)

        await db.update_subscription(user.id, tier, end_date.isoformat(), grace_end.isoformat())
        await db.log_subscription_change(
            user.id, old_tier, tier,
            changed_by=ctx.author.id,
            reason=f"Admin upgrade by {ctx.author}",
        )
        logger.info(f"Admin {ctx.author.id} upgraded {user.id} to {tier} for {months} months")

        embed = discord.Embed(
            description=f"Set **{user.mention}** to **{tier}** for `{months}` month(s).",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='admin_extend', aliases=['aextend'])
    async def admin_extend(self, ctx: commands.Context, user: discord.Member, days: int):
        """Extend a user's subscription by N days."""
        sub = await db.get_subscription(user.id)
        if not sub or sub['tier'] == 'Basic':
            await ctx.send(embed=discord.Embed(
                description="User has no active paid subscription.",
                color=config.COLORS['error'],
            ))
            return

        if sub['end_date']:
            current_end = datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc)
        else:
            current_end = datetime.now(timezone.utc)

        new_end = current_end + timedelta(days=days)
        new_grace = new_end + timedelta(days=3)
        await db.update_subscription(user.id, sub['tier'], new_end.isoformat(), new_grace.isoformat())
        logger.info(f"Admin {ctx.author.id} extended {user.id} by {days} days")

        embed = discord.Embed(
            description=f"Extended **{user.mention}**'s subscription by `{days}` days. New end: `{new_end.date()}`",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='subscription_report', aliases=['subreport'])
    async def subscription_report(self, ctx: commands.Context):
        """Generate a subscription metrics report."""
        counts = await db.get_subscriber_counts()
        expiring = await db.get_expiring_subscriptions(days=7)

        embed = discord.Embed(title="Subscription Report", color=config.COLORS['primary'])
        total = 0
        for row in counts:
            embed.add_field(name=row['tier'], value=f"`{row['count']:,}` users", inline=True)
            total += row['count']
        embed.add_field(name="Total", value=f"`{total:,}` users", inline=True)
        embed.add_field(name="Expiring (7d)", value=f"`{len(expiring)}` subscriptions", inline=True)
        embed.set_footer(text=f"Report generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        await ctx.send(embed=embed)

    @commands.command(name='subscription_history', aliases=['subhistory'])
    async def subscription_history_cmd(self, ctx: commands.Context, user: discord.Member):
        """View full subscription change history for a user."""
        history = await db.get_subscription_history(user.id, limit=20)
        if not history:
            await ctx.send(embed=discord.Embed(description="No history found.", color=config.COLORS['warning']))
            return

        lines = []
        for h in history:
            ts = h['changed_at'][:16]
            by = f" by <@{h['changed_by']}>" if h['changed_by'] else ""
            reason = f" — *{h['reason']}*" if h['reason'] else ""
            lines.append(f"`{ts}` {h['old_tier']} → **{h['new_tier']}**{by}{reason}")

        embed = discord.Embed(
            title=f"Subscription History — {user.display_name}",
            description="\n".join(lines),
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminSubscription(bot))
