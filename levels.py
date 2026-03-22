import discord
from discord.ext import commands
import random
from datetime import datetime, timezone
import config
import database as db


async def _assign_level_role(member: discord.Member, new_level: int) -> str | None:
    """Assign the highest applicable level milestone role. Returns a note string or None."""
    if not member.guild:
        return None

    # Find which milestones the member has now unlocked (highest one wins)
    target_name = None
    target_color = None
    for lvl in sorted(config.LEVEL_ROLES.keys()):
        if new_level >= lvl:
            target_name, target_color = config.LEVEL_ROLES[lvl]

    if not target_name:
        return None

    # Remove any old milestone roles
    milestone_names = {v[0] for v in config.LEVEL_ROLES.values()}
    old_roles = [r for r in member.roles if r.name in milestone_names and r.name != target_name]

    # Find or create the target role
    role = discord.utils.get(member.guild.roles, name=target_name)
    if not role:
        try:
            role = await member.guild.create_role(
                name=target_name,
                color=discord.Color(target_color),
                reason='Tainment+ level milestone role',
            )
        except discord.HTTPException:
            return None

    try:
        if old_roles:
            await member.remove_roles(*old_roles, reason='Level milestone upgrade')
        if role not in member.roles:
            await member.add_roles(role, reason=f'Reached level {new_level}')
            return f"\U0001f3c6 Unlocked role **{target_name}**!"
    except discord.HTTPException:
        pass
    return None


def xp_for_next(level: int) -> int:
    needed = config.LEVELS['xp_base']
    for _ in range(level):
        needed = int(needed * config.LEVELS['xp_factor'])
    return needed


def total_xp_for_level(level: int) -> int:
    total = 0
    needed = config.LEVELS['xp_base']
    for _ in range(level):
        total += needed
        needed = int(needed * config.LEVELS['xp_factor'])
    return total


class Levels(commands.Cog, name="Levels"):
    """XP and leveling system. Earn XP by chatting."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._xp_cooldowns: dict[tuple, float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith(config.COMMAND_PREFIX):
            return

        key = (message.author.id, message.guild.id)
        now = datetime.now(timezone.utc).timestamp()
        last = self._xp_cooldowns.get(key, 0)

        if now - last < config.LEVELS['xp_cooldown']:
            return
        self._xp_cooldowns[key] = now

        await db.ensure_user(message.author.id, message.author.name)

        # Tier XP multiplier
        tier = await db.get_tier(message.author.id)
        multiplier = config.SUBSCRIPTION_TIERS[tier]['xp_multiplier']

        # XP boost item
        if await db.has_active_item(message.author.id, 'xp_boost'):
            multiplier *= 2

        base_xp = random.randint(
            config.LEVELS['xp_per_message_min'],
            config.LEVELS['xp_per_message_max'],
        )
        xp_gained = max(1, int(base_xp * multiplier))

        result = await db.add_xp(message.author.id, message.guild.id, xp_gained)

        if result['leveled_up']:
            new_lvl = result['new_level']
            role_note = await _assign_level_role(message.author, new_lvl)
            embed = discord.Embed(
                title="Level Up!",
                description=(
                    f"{message.author.mention} reached **Level {new_lvl}**!\n"
                    f"Total XP: `{result['xp']:,}`"
                    + (f"\n\n{role_note}" if role_note else "")
                ),
                color=config.COLORS['gold'],
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await message.channel.send(embed=embed)

    @commands.hybrid_command(name='level', aliases=['lvl', 'xp'], description='Check your level and XP')
    async def level(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        await db.ensure_user(target.id, target.name)
        data = await db.get_level_data(target.id, ctx.guild.id)

        if not data:
            embed = discord.Embed(
                description=f"{target.display_name} hasn't earned any XP yet.",
                color=config.COLORS['warning'],
            )
            await ctx.send(embed=embed)
            return

        current_xp = data['xp']
        current_level = data['level']
        needed = xp_for_next(current_level)
        progress_xp = current_xp - total_xp_for_level(current_level)
        pct = min(1.0, progress_xp / needed) if needed else 1.0
        bar_len = 20
        filled = int(bar_len * pct)
        bar = '█' * filled + '░' * (bar_len - filled)

        embed = discord.Embed(
            title=f"{target.display_name}'s Level",
            color=config.COLORS['primary'],
        )
        embed.add_field(name="Level", value=f"`{current_level}`", inline=True)
        embed.add_field(name="Total XP", value=f"`{current_xp:,}`", inline=True)
        embed.add_field(
            name=f"Progress to Level {current_level + 1}",
            value=f"`{bar}` {int(pct*100)}%\n`{progress_xp:,}` / `{needed:,}` XP",
            inline=False,
        )

        tier = await db.get_tier(target.id)
        mult = config.SUBSCRIPTION_TIERS[tier]['xp_multiplier']
        embed.add_field(name="XP Multiplier", value=f"`{mult}x` ({tier})", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Tainment+ Levels")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='rank', description='View the server XP leaderboard')
    async def rank(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        rows = await db.get_level_leaderboard(ctx.guild.id, limit=10)
        if not rows:
            await ctx.send(embed=discord.Embed(description="No XP data yet.", color=config.COLORS['warning']))
            return

        medals = [':first_place:', ':second_place:', ':third_place:']
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            member = ctx.guild.get_member(row['user_id'])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"{medal} **{name}** — Level `{row['level']}` | `{row['xp']:,}` XP")

        embed = discord.Embed(
            title=f"{ctx.guild.name} — XP Leaderboard",
            description="\n".join(lines),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text="Earn XP by chatting!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Levels(bot))
