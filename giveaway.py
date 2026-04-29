import discord
from discord.ext import commands, tasks
import random
import re
import logging
from datetime import datetime, timezone, timedelta
import config
import database as db
from reply_utils import send_reply

logger = logging.getLogger('tainment.giveaway')


def parse_duration(text: str) -> int | None:
    """Parse a duration string like '1h30m' into seconds."""
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


def giveaway_embed(prize: str, host: discord.Member, end_time: datetime, winners: int, entries: int = 0) -> discord.Embed:
    embed = discord.Embed(
        title=f"GIVEAWAY: {prize}",
        color=config.COLORS['gold'],
    )
    embed.add_field(name="Hosted by", value=host.mention, inline=True)
    embed.add_field(name="Winners", value=str(winners), inline=True)
    embed.add_field(name="Entries", value=str(entries), inline=True)
    ts = int(end_time.timestamp())
    embed.add_field(name="Ends", value=f"<t:{ts}:R> (<t:{ts}:F>)", inline=False)
    embed.set_footer(text="Click the button below to enter!")
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="Enter Giveaway", style=discord.ButtonStyle.success, custom_id="giveaway_enter", emoji="\U0001f389")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        gaw = await db.get_giveaway(self.giveaway_id)
        if not gaw or gaw['ended']:
            await interaction.response.send_message("This giveaway has already ended.", ephemeral=True)
            return

        end_time = datetime.fromisoformat(gaw['end_time']).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > end_time:
            await interaction.response.send_message("This giveaway has already ended.", ephemeral=True)
            return

        entered = await db.add_giveaway_entry(self.giveaway_id, interaction.user.id)
        if entered:
            entries = await db.get_giveaway_entries(self.giveaway_id)
            await interaction.response.send_message(
                f"You've entered the giveaway! Total entries: **{len(entries)}**", ephemeral=True
            )
            # Update entry count on the embed
            try:
                host = interaction.guild.get_member(gaw['host_id'])
                embed = giveaway_embed(gaw['prize'], host, end_time, gaw['winner_count'], len(entries))
                await interaction.message.edit(embed=embed)
            except Exception:
                pass
        else:
            # Already entered — let them leave
            await db.remove_giveaway_entry(self.giveaway_id, interaction.user.id)
            entries = await db.get_giveaway_entries(self.giveaway_id)
            await interaction.response.send_message(
                "You've been removed from the giveaway.", ephemeral=True
            )
            try:
                host = interaction.guild.get_member(gaw['host_id'])
                embed = giveaway_embed(gaw['prize'], host, end_time, gaw['winner_count'], len(entries))
                await interaction.message.edit(embed=embed)
            except Exception:
                pass


class Giveaways(commands.Cog, name="Giveaways"):
    """Host and manage giveaways with button-based entry."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        ended = await db.get_active_giveaways()
        for gaw in ended:
            await self._conclude_giveaway(gaw['id'])

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _conclude_giveaway(self, giveaway_id: int):
        gaw = await db.get_giveaway(giveaway_id)
        if not gaw or gaw['ended']:
            return
        await db.end_giveaway(giveaway_id)

        entries = await db.get_giveaway_entries(giveaway_id)
        channel = self.bot.get_channel(gaw['channel_id'])
        if not channel:
            return

        try:
            message = await channel.fetch_message(gaw['message_id'])
        except Exception as e:
            logger.error(f"[GiveawayCheck] Could not fetch message {gaw['message_id']} for giveaway {giveaway_id}: {e}")
            return

        if not entries:
            embed = discord.Embed(
                title=f"GIVEAWAY ENDED: {gaw['prize']}",
                description="No one entered. No winners.",
                color=config.COLORS['error'],
            )
            await message.edit(embed=embed, view=None)
            await channel.send(embed=embed)
            return

        num_winners = min(gaw['winner_count'], len(entries))
        winners = random.sample(entries, num_winners)
        winner_mentions = ', '.join(f"<@{w}>" for w in winners)

        embed = discord.Embed(
            title=f"GIVEAWAY ENDED: {gaw['prize']}",
            description=f"Winner{'s' if num_winners > 1 else ''}: {winner_mentions}",
            color=config.COLORS['success'],
        )
        embed.set_footer(text=f"Total entries: {len(entries)}")
        await message.edit(embed=embed, view=None)
        await channel.send(
            f"Congratulations {winner_mentions}! You won **{gaw['prize']}**!",
            embed=embed,
        )

    @commands.command(name='gcreate', description='Create a giveaway')
    @commands.has_permissions(manage_guild=True)
    async def gcreate(self, ctx: commands.Context):
        """Interactive giveaway creation via DM-style prompts."""
        questions = [
            ("What is the prize?", 120),
            ("How long should the giveaway run? (e.g. `1h`, `30m`, `1d12h`)", 60),
            ("How many winners? (1-10)", 30),
        ]

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        answers = []
        for question, timeout in questions:
            embed = discord.Embed(description=question, color=config.COLORS['primary'])
            await ctx.send(embed=embed)
            try:
                msg = await ctx.bot.wait_for('message', check=check, timeout=timeout)
                answers.append(msg.content.strip())
            except Exception:
                await ctx.send(embed=discord.Embed(description="Timed out. Giveaway cancelled.", color=config.COLORS['error']))
                return

        prize = answers[0]
        duration = parse_duration(answers[1])
        if not duration:
            await ctx.send(embed=discord.Embed(description="Invalid duration. Use e.g. `1h`, `30m`.", color=config.COLORS['error']))
            return

        try:
            winner_count = max(1, min(10, int(answers[2])))
        except ValueError:
            winner_count = 1

        end_time = datetime.now(timezone.utc) + timedelta(seconds=duration)
        giveaway_id_placeholder = -1

        embed = giveaway_embed(prize, ctx.author, end_time, winner_count, 0)
        view = GiveawayView(giveaway_id_placeholder)
        msg = await ctx.channel.send(embed=embed, view=view)

        giveaway_id = await db.create_giveaway(
            ctx.guild.id, ctx.channel.id, msg.id,
            ctx.author.id, prize, winner_count,
            end_time.isoformat(),
        )

        # Update view with real ID
        real_view = GiveawayView(giveaway_id)
        await msg.edit(view=real_view)
        self.bot.add_view(real_view)

    @commands.command(name='gend', description='End a giveaway early by message ID')
    @commands.has_permissions(manage_guild=True)
    async def gend(self, ctx: commands.Context, message_id: str):
        try:
            mid = int(message_id)
        except ValueError:
            await ctx.send(embed=discord.Embed(description="Invalid message ID.", color=config.COLORS['error']))
            return

        gaw = await db.get_giveaway_by_message(mid)
        if not gaw:
            await ctx.send(embed=discord.Embed(description="Giveaway not found.", color=config.COLORS['error']))
            return
        if gaw['ended']:
            await ctx.send(embed=discord.Embed(description="That giveaway already ended.", color=config.COLORS['warning']))
            return

        await self._conclude_giveaway(gaw['id'])
        await send_reply(ctx, embed=discord.Embed(description="Giveaway ended early.", color=config.COLORS['success']), ephemeral=True)

    @commands.command(name='greroll', description='Reroll winners for an ended giveaway')
    @commands.has_permissions(manage_guild=True)
    async def greroll(self, ctx: commands.Context, message_id: str):
        try:
            mid = int(message_id)
        except ValueError:
            await ctx.send(embed=discord.Embed(description="Invalid message ID.", color=config.COLORS['error']))
            return

        gaw = await db.get_giveaway_by_message(mid)
        if not gaw:
            await ctx.send(embed=discord.Embed(description="Giveaway not found.", color=config.COLORS['error']))
            return

        entries = await db.get_giveaway_entries(gaw['id'])
        if not entries:
            await ctx.send(embed=discord.Embed(description="No entries to reroll from.", color=config.COLORS['error']))
            return

        num_winners = min(gaw['winner_count'], len(entries))
        winners = random.sample(entries, num_winners)
        winner_mentions = ', '.join(f"<@{w}>" for w in winners)

        embed = discord.Embed(
            title=f"Giveaway Rerolled: {gaw['prize']}",
            description=f"New winner{'s' if num_winners > 1 else ''}: {winner_mentions}",
            color=config.COLORS['gold'],
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
