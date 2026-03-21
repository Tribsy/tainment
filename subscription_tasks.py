import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import logging
import config
import database as db

logger = logging.getLogger('tainment.tasks')


class SubscriptionTasks(commands.Cog, name="SubscriptionTasks"):
    """Background tasks for subscription management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_expiring.start()
        self.process_expired.start()

    def cog_unload(self):
        self.check_expiring.cancel()
        self.process_expired.cancel()

    @tasks.loop(hours=24)
    async def check_expiring(self):
        """Notify users whose subscriptions expire within 3 days."""
        subs = await db.get_expiring_subscriptions(days=3)
        for sub in subs:
            try:
                user = await self.bot.fetch_user(sub['user_id'])
                end_dt = datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc)
                ts = int(end_dt.timestamp())
                embed = discord.Embed(
                    title="Subscription Expiring Soon",
                    description=(
                        f"Your **{sub['tier']}** subscription expires <t:{ts}:R>.\n\n"
                        "Renew with `t!renew` to keep your benefits.\n"
                        "After expiry you have a 3-day grace period before downgrade."
                    ),
                    color=config.COLORS['warning'],
                )
                embed.set_footer(text="Tainment+ Subscriptions")
                await user.send(embed=embed)
                await db.mark_renewal_reminder_sent(sub['user_id'])
                logger.info(f"Sent expiry reminder to user {sub['user_id']}")
            except Exception as e:
                logger.warning(f"Could not DM user {sub['user_id']}: {e}")

    @tasks.loop(hours=12)
    async def process_expired(self):
        """Downgrade users whose grace period has ended."""
        subs = await db.get_grace_period_subscriptions()
        for sub in subs:
            try:
                old_tier = sub['tier']
                await db.update_subscription(sub['user_id'], 'Basic', None, None)
                await db.log_subscription_change(sub['user_id'], old_tier, 'Basic', reason='Automatic downgrade after grace period')
                try:
                    user = await self.bot.fetch_user(sub['user_id'])
                    embed = discord.Embed(
                        title="Subscription Expired",
                        description=(
                            f"Your **{old_tier}** subscription has expired and your account "
                            f"has been downgraded to **Basic**.\n\n"
                            "Resubscribe anytime with `t!upgrade`."
                        ),
                        color=config.COLORS['error'],
                    )
                    await user.send(embed=embed)
                except Exception:
                    pass
                logger.info(f"Downgraded user {sub['user_id']} from {old_tier} to Basic")
            except Exception as e:
                logger.error(f"Error processing expired subscription for {sub['user_id']}: {e}")

    @check_expiring.before_loop
    @process_expired.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(SubscriptionTasks(bot))
