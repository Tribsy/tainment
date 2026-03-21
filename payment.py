import discord
from discord.ext import commands
import random
import string
from datetime import datetime, timezone, timedelta
import logging
import config
import database as db

logger = logging.getLogger('tainment.payment')

DISCOUNTS = {1: 0, 3: 0.10, 6: 0.15, 12: 0.20}


def generate_txn_id() -> str:
    chars = string.ascii_uppercase + string.digits
    return 'TXN-' + ''.join(random.choices(chars, k=12))


def calculate_price(tier: str, months: int) -> float:
    base = config.SUBSCRIPTION_TIERS[tier]['price']
    discount = DISCOUNTS.get(months, 0)
    return round(base * months * (1 - discount), 2)


class SimulatedCheckoutView(discord.ui.View):
    """Fallback simulated checkout used when Stripe is not configured."""

    def __init__(self, ctx, tier: str, months: int, txn_id: str, total: float, is_renewal: bool = False):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.tier = tier
        self.months = months
        self.txn_id = txn_id
        self.total = total
        self.is_renewal = is_renewal

    @discord.ui.button(label='Confirm Payment', style=discord.ButtonStyle.success, emoji='\u2705')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your checkout.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        self.stop()

        # Simulate 90% success rate
        if random.random() > 0.90:
            await interaction.response.edit_message(
                embed=discord.Embed(title="Payment Failed", description="Simulated failure. Try again.", color=config.COLORS['error']),
                view=self,
            )
            return

        user_id = self.ctx.author.id
        await db.record_payment(user_id, self.txn_id, self.total, self.tier, self.months, 'completed')
        await db.complete_payment(self.txn_id)

        old_tier = await db.get_tier(user_id)
        now = datetime.now(timezone.utc)
        sub = await db.get_subscription(user_id)

        if sub and sub['end_date'] and not self.is_renewal:
            start = max(datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc), now)
        else:
            start = now

        end_date = start + timedelta(days=self.months * 30)
        grace_end = end_date + timedelta(days=3)

        await db.update_subscription(user_id, self.tier, end_date.isoformat(), grace_end.isoformat())
        await db.log_subscription_change(user_id, old_tier, self.tier, reason=f"Simulated payment {self.txn_id}")

        ts = int(end_date.timestamp())
        embed = discord.Embed(
            title="Payment Successful! (Simulated)",
            description=(
                f"**{self.tier}** subscription activated!\n\n"
                f"Transaction: `{self.txn_id}`\n"
                f"Amount: `${self.total:.2f}`\n"
                f"Active until: <t:{ts}:F>\n\n"
                f"*Configure STRIPE_SECRET_KEY for real payments.*"
            ),
            color=config.COLORS['success'],
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, emoji='\u274c')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your checkout.", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="Checkout cancelled.", color=config.COLORS['warning']),
            view=self,
        )


class Payment(commands.Cog, name="Payment"):
    """Handles subscription payments (Stripe when configured, simulated otherwise)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_stripe(self):
        return self.bot.cogs.get('StripePayment')

    async def initiate_upgrade(self, ctx: commands.Context, tier: str, months: int = 1):
        stripe_cog = self._get_stripe()
        if stripe_cog and stripe_cog.is_configured():
            await stripe_cog.create_checkout(ctx, tier, months)
        else:
            await self._simulated_checkout(ctx, tier, months, is_renewal=False)

    async def initiate_renew(self, ctx: commands.Context, tier: str, months: int):
        stripe_cog = self._get_stripe()
        if stripe_cog and stripe_cog.is_configured():
            await stripe_cog.create_checkout(ctx, tier, months)
        else:
            await self._simulated_checkout(ctx, tier, months, is_renewal=True)

    async def _simulated_checkout(self, ctx, tier, months, is_renewal):
        total = calculate_price(tier, months)
        txn_id = generate_txn_id()
        discount = DISCOUNTS.get(months, 0)
        base = config.SUBSCRIPTION_TIERS[tier]['price'] * months

        embed = discord.Embed(
            title=f"Checkout — {tier} {'Renewal' if is_renewal else 'Upgrade'}",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Tier", value=tier, inline=True)
        embed.add_field(name="Duration", value=f"{months} month{'s' if months != 1 else ''}", inline=True)
        embed.add_field(name="Transaction ID", value=f"`{txn_id}`", inline=False)
        if discount:
            embed.add_field(name="Subtotal", value=f"`${base:.2f}`", inline=True)
            embed.add_field(name=f"Discount ({int(discount*100)}%)", value=f"`-${base-total:.2f}`", inline=True)
        embed.add_field(name="Total", value=f"**${total:.2f}**", inline=False)
        embed.set_footer(text="SIMULATED — Add STRIPE_SECRET_KEY to .env for real payments")

        view = SimulatedCheckoutView(ctx, tier, months, txn_id, total, is_renewal)
        await ctx.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Payment(bot))
