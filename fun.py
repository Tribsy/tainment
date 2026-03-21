import discord
from discord.ext import commands
import random
import re
import config
import database as db


EIGHT_BALL_RESPONSES = [
    # Positive
    "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
    "Yes.", "Signs point to yes.",
    # Neutral
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    # Negative
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

COMPLIMENTS = [
    "is an absolute legend.",
    "has the most contagious smile.",
    "makes every room better just by being in it.",
    "is the kind of person everyone wants on their team.",
    "has an incredible ability to make people feel valued.",
    "is genuinely one of the coolest people around.",
    "brightens everyone's day without even trying.",
    "has a heart of gold.",
    "is unrealistically talented.",
    "would win any 'best person' award hands down.",
]

ROASTS = [
    "is so boring their dreams have a loading screen.",
    "has a face only a mother could love — on a good day.",
    "could trip over a wireless network.",
    "is the human equivalent of a participation trophy.",
    "could get lost in a hallway.",
    "has a library card but only uses it to press flowers.",
    "brings such low energy they need a nap after sending a text.",
    "is the reason instruction manuals have pictures.",
    "once lost a staring contest with their own reflection.",
    "talks so slowly subtitles arrive the next day.",
]

QUOTES = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "In the middle of every difficulty lies opportunity. — Albert Einstein",
    "It does not matter how slowly you go as long as you do not stop. — Confucius",
    "Life is what happens when you're busy making other plans. — John Lennon",
    "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
    "Strive not to be a success, but rather to be of value. — Albert Einstein",
    "You miss 100% of the shots you don't take. — Wayne Gretzky",
    "Whether you think you can or think you can't, you're right. — Henry Ford",
    "The best time to plant a tree was 20 years ago. The second best time is now. — Chinese Proverb",
    "An unexamined life is not worth living. — Socrates",
]

MEME_SUBREDDITS = ['memes', 'dankmemes', 'ProgrammerHumor', 'me_irl', 'technicallythetruth']


class Fun(commands.Cog, name="Fun"):
    """Lighthearted fun commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='8ball', description='Ask the magic 8-ball a question')
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        response = random.choice(EIGHT_BALL_RESPONSES)
        embed = discord.Embed(color=config.COLORS['purple'])
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"*{response}*", inline=False)
        embed.set_footer(text="Magic 8-Ball")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='roll', description='Roll dice (e.g. 2d6, default 1d6)')
    async def roll(self, ctx: commands.Context, dice: str = '1d6'):
        pattern = re.fullmatch(r'(\d+)d(\d+)', dice.lower())
        if not pattern:
            await ctx.send(embed=discord.Embed(
                description="Format: `NdN` e.g. `2d6`, `1d20`",
                color=config.COLORS['error'],
            ))
            return

        count = int(pattern.group(1))
        sides = int(pattern.group(2))

        if count < 1 or count > 20 or sides < 2 or sides > 100:
            await ctx.send(embed=discord.Embed(
                description="Use 1-20 dice with 2-100 sides.",
                color=config.COLORS['error'],
            ))
            return

        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)

        embed = discord.Embed(
            title=f"Rolling {dice}",
            color=config.COLORS['primary'],
        )
        if count > 1:
            embed.add_field(name="Rolls", value=" + ".join(f"`{r}`" for r in results), inline=False)
            embed.add_field(name="Total", value=f"**{total}**", inline=False)
        else:
            embed.description = f"Rolled: **{total}**"
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='flip', description='Flip a coin')
    async def flip(self, ctx: commands.Context):
        result = random.choice(['Heads', 'Tails'])
        color = config.COLORS['success'] if result == 'Heads' else config.COLORS['info']
        embed = discord.Embed(
            title="Coin Flip",
            description=f"It landed on **{result}**!",
            color=color,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='meme', description='Get a random meme from Reddit')
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def meme(self, ctx: commands.Context):
        subreddit = random.choice(MEME_SUBREDDITS)
        url = f"https://meme-api.com/gimme/{subreddit}"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        raise Exception("API error")
                    data = await resp.json()
            if data.get('nsfw', False):
                await ctx.invoke(self.meme)
                return
            embed = discord.Embed(title=data['title'], url=data['postLink'], color=config.COLORS['primary'])
            embed.set_image(url=data['url'])
            embed.set_footer(text=f"r/{data['subreddit']} | {data.get('ups', 0):,} upvotes")
            await ctx.send(embed=embed)
        except Exception:
            await ctx.send(embed=discord.Embed(
                description="Couldn't fetch a meme right now. Try again!",
                color=config.COLORS['error'],
            ))

    @commands.hybrid_command(name='quote', description='Get an inspirational quote')
    async def quote(self, ctx: commands.Context):
        q = random.choice(QUOTES)
        parts = q.rsplit(' — ', 1)
        embed = discord.Embed(
            description=f'*"{parts[0]}"*',
            color=config.COLORS['info'],
        )
        if len(parts) > 1:
            embed.set_footer(text=f"— {parts[1]}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='compliment', description='Compliment a user')
    async def compliment(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        c = random.choice(COMPLIMENTS)
        embed = discord.Embed(
            description=f"{target.mention} {c}",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='roast', description='Friendly roast a user')
    async def roast(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        r = random.choice(ROASTS)
        embed = discord.Embed(
            description=f"{target.mention} {r}",
            color=config.COLORS['warning'],
        )
        embed.set_footer(text="All in good fun!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='choose', description='Pick from a list of options')
    async def choose(self, ctx: commands.Context, *, options: str):
        choices = [o.strip() for o in options.split('|') if o.strip()]
        if len(choices) < 2:
            await ctx.send(embed=discord.Embed(
                description="Provide at least 2 options separated by `|`. E.g. `pizza | tacos | burgers`",
                color=config.COLORS['error'],
            ))
            return
        chosen = random.choice(choices)
        embed = discord.Embed(
            title="I choose...",
            description=f"**{chosen}**",
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"From {len(choices)} options")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='mock', description='Convert text to SpOnGeBoB mocking format')
    async def mock(self, ctx: commands.Context, *, text: str):
        result = ''.join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(text)
        )
        embed = discord.Embed(description=result, color=config.COLORS['warning'])
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='reverse', description='Reverse a piece of text')
    async def reverse(self, ctx: commands.Context, *, text: str):
        embed = discord.Embed(description=text[::-1], color=config.COLORS['info'])
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
