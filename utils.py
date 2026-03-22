import discord
from discord.ext import commands
import logging
import os
import config

logger = logging.getLogger('tainment.utils')


def format_time(seconds: int) -> str:
    parts = []
    if seconds >= 86400:
        parts.append(f"{seconds // 86400} day{'s' if seconds // 86400 != 1 else ''}")
        seconds %= 86400
    if seconds >= 3600:
        parts.append(f"{seconds // 3600} hour{'s' if seconds // 3600 != 1 else ''}")
        seconds %= 3600
    if seconds >= 60:
        parts.append(f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}")
        seconds %= 60
    if seconds:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ', '.join(parts) if parts else '0 seconds'


def create_progress_bar(value: float, maximum: float, length: int = 20) -> str:
    pct = min(1.0, value / maximum) if maximum else 0
    filled = int(length * pct)
    bar = '█' * filled + '░' * (length - filled)
    return f"{bar} {int(pct * 100)}%"


def truncate_text(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + '...'


class Utils(commands.Cog, name="Utils"):
    """Utility commands and information."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='tos', description='View the Terms of Service')
    async def tos(self, ctx: commands.Context):
        await self._send_doc(ctx, config.TOS_PATH, "Terms of Service")

    @commands.command(name='privacy', description='View the Privacy Policy')
    async def privacy(self, ctx: commands.Context):
        await self._send_doc(ctx, config.PRIVACY_PATH, "Privacy Policy")

    async def _send_doc(self, ctx: commands.Context, path: str, title: str):
        try:
            if not os.path.exists(path):
                await ctx.send(embed=discord.Embed(
                    description=f"{title} document not found.",
                    color=config.COLORS['error'],
                ))
                return

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if len(content) <= 4000:
                embed = discord.Embed(title=title, description=content, color=config.COLORS['info'])
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=title,
                    description=truncate_text(content, 4000),
                    color=config.COLORS['info'],
                )
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error loading {title}: {e}")
            await ctx.send(embed=discord.Embed(
                description=f"Could not load {title}.",
                color=config.COLORS['error'],
            ))

    @commands.command(name='invite', description='Get the bot invite link')
    async def invite(self, ctx: commands.Context):
        if config.INVITE_URL:
            embed = discord.Embed(
                title="Invite Tainment+",
                description=f"[Click here to invite the bot]({config.INVITE_URL})",
                color=config.COLORS['primary'],
            )
        else:
            embed = discord.Embed(
                description="Invite link not configured.",
                color=config.COLORS['warning'],
            )
        await ctx.send(embed=embed)

    @commands.command(name='support', description='Get the support server link')
    async def support(self, ctx: commands.Context):
        if config.SUPPORT_SERVER:
            embed = discord.Embed(
                title="Support Server",
                description=f"[Join the support server]({config.SUPPORT_SERVER})",
                color=config.COLORS['primary'],
            )
        else:
            embed = discord.Embed(description="Support server not configured.", color=config.COLORS['warning'])
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))
