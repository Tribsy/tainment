import discord
from discord.ext import commands, tasks
import re
from datetime import datetime, timezone, timedelta
import config
import database as db


def parse_duration(text: str) -> int | None:
    pattern = re.fullmatch(
        r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?',
        text.lower().strip(),
    )
    if not pattern or not any(pattern.groups()):
        return None
    days = int(pattern.group(1) or 0)
    hours = int(pattern.group(2) or 0)
    minutes = int(pattern.group(3) or 0)
    seconds = int(pattern.group(4) or 0)
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


class Reminders(commands.Cog, name="Reminders"):
    """Set personal reminders."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(seconds=15)
    async def check_reminders(self):
        due = await db.get_due_reminders()
        for reminder in due:
            await db.mark_reminder_sent(reminder['id'])
            channel = self.bot.get_channel(reminder['channel_id'])
            if not channel:
                # Try DM
                try:
                    user = await self.bot.fetch_user(reminder['user_id'])
                    channel = user.dm_channel or await user.create_dm()
                except Exception:
                    continue

            embed = discord.Embed(
                title="Reminder!",
                description=reminder['message'],
                color=config.COLORS['info'],
            )
            embed.set_footer(text=f"Reminder ID: {reminder['id']}")
            try:
                await channel.send(f"<@{reminder['user_id']}>", embed=embed)
            except Exception:
                pass

    @check_reminders.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @commands.command(name='remind', aliases=['reminder'], description='Set a reminder')
    async def remind(self, ctx: commands.Context, time: str, *, message: str):
        """
        Set a reminder. Time format: 1h30m, 2d, 45s, etc.
        Example: t!remind 1h Take the pasta off the stove
        """
        duration = parse_duration(time)
        if not duration:
            await ctx.send(embed=discord.Embed(
                description="Invalid time format. Use e.g. `1h`, `30m`, `1d12h`, `45s`.",
                color=config.COLORS['error'],
            ))
            return
        if duration > 30 * 86400:
            await ctx.send(embed=discord.Embed(
                description="Maximum reminder duration is **30 days**.",
                color=config.COLORS['error'],
            ))
            return

        remind_at = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()
        reminder_id = await db.create_reminder(ctx.author.id, ctx.channel.id, message, remind_at)

        h = duration // 3600
        m = (duration % 3600) // 60
        s = duration % 60
        parts = []
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        if s: parts.append(f"{s}s")
        human = ' '.join(parts)

        embed = discord.Embed(
            title="Reminder set!",
            description=f"I'll remind you in **{human}**.\n\n*{message}*",
            color=config.COLORS['success'],
        )
        embed.set_footer(text=f"Reminder ID: {reminder_id}")
        await ctx.send(embed=embed)

    @commands.command(name='reminders', description='List your active reminders')
    async def reminders_list(self, ctx: commands.Context):
        rows = await db.get_user_reminders(ctx.author.id)
        if not rows:
            await ctx.send(embed=discord.Embed(
                description="You have no active reminders.",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title="Your Reminders", color=config.COLORS['primary'])
        for row in rows:
            remind_at = datetime.fromisoformat(row['remind_at']).replace(tzinfo=timezone.utc)
            ts = int(remind_at.timestamp())
            embed.add_field(
                name=f"ID {row['id']} — <t:{ts}:R>",
                value=row['message'][:100],
                inline=False,
            )
        embed.set_footer(text="Use t!delreminder <id> to delete")
        await ctx.send(embed=embed)

    @commands.command(name='delreminder', description='Delete a reminder by ID')
    async def delreminder(self, ctx: commands.Context, reminder_id: int):
        success = await db.delete_reminder(reminder_id, ctx.author.id)
        if success:
            await ctx.send(embed=discord.Embed(
                description=f"Reminder `{reminder_id}` deleted.",
                color=config.COLORS['success'],
            ))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"No reminder with ID `{reminder_id}` found.",
                color=config.COLORS['error'],
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminders(bot))
