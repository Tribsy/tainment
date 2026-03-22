import discord
from discord.ext import commands
import config


NUMBER_EMOJIS = ['1\ufe0f\u20e3', '2\ufe0f\u20e3', '3\ufe0f\u20e3', '4\ufe0f\u20e3', '5\ufe0f\u20e3']


class Polls(commands.Cog, name="Polls"):
    """Create polls for your server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='poll', description='Create a poll (separate options with |)')
    @commands.has_permissions(send_messages=True)
    async def poll(self, ctx: commands.Context, *, content: str):
        """
        Usage: t!poll Question | Option A | Option B | Option C
        Up to 5 options. If only a question is given, a yes/no poll is created.
        """
        parts = [p.strip() for p in content.split('|') if p.strip()]

        if len(parts) < 1:
            await ctx.send(embed=discord.Embed(
                description="Usage: `t!poll Question | Option 1 | Option 2`",
                color=config.COLORS['error'],
            ))
            return

        question = parts[0]
        options = parts[1:6]  # max 5 options

        if not options:
            # Yes/No poll
            embed = discord.Embed(
                title="Poll",
                description=f"**{question}**",
                color=config.COLORS['primary'],
            )
            embed.set_footer(text=f"Poll by {ctx.author.display_name} | React to vote!")
            msg = await ctx.channel.send(embed=embed)
            await msg.add_reaction('\U00002705')  # check mark
            await msg.add_reaction('\U0000274c')  # cross mark
        else:
            if len(options) > 5:
                await ctx.send(embed=discord.Embed(
                    description="Maximum 5 options allowed.",
                    color=config.COLORS['error'],
                ))
                return

            lines = '\n'.join(f"{NUMBER_EMOJIS[i]} {opt}" for i, opt in enumerate(options))
            embed = discord.Embed(
                title="Poll",
                description=f"**{question}**\n\n{lines}",
                color=config.COLORS['primary'],
            )
            embed.set_footer(text=f"Poll by {ctx.author.display_name} | React to vote!")
            msg = await ctx.channel.send(embed=embed)
            for i in range(len(options)):
                await msg.add_reaction(NUMBER_EMOJIS[i])

        # Delete the invoking message for a cleaner look (if we have perms)
        if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            try:
                await ctx.message.delete()
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Polls(bot))
