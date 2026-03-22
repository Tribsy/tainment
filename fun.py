import discord
from discord.ext import commands
import random
import re
import config
import database as db

FORTUNE_COOKIES = [
    "A beautiful, smart, and loving person will be coming into your life.",
    "A dubious friend may be an enemy in camouflage.",
    "A fresh start will put you on your way.",
    "A good time to finish up old tasks.",
    "A journey of a thousand miles begins with a single step.",
    "All things are difficult before they are easy.",
    "Believe in yourself and others will too.",
    "Change your thoughts and you change your world.",
    "Dedicate yourself with a calm mind to the task at hand.",
    "Do not be afraid of competition.",
    "Every day is a new opportunity to do better.",
    "Fortune favors the bold.",
    "Good things take time.",
    "Hard work pays off in the future; laziness pays off now.",
    "It's not the destination, it's the journey.",
    "Keep it simple.",
    "Luck is preparation meeting opportunity.",
    "New ideas could be profitable.",
    "No act of kindness, no matter how small, is ever wasted.",
    "Now is the time to try something new.",
    "Opportunities multiply as they are seized.",
    "Patience is your ally right now. Don't give up.",
    "Respect yourself and others will respect you.",
    "Soon you will be sitting on top of the world.",
    "Stay true to yourself.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "The greatest risk is not taking one.",
    "The secret of getting ahead is getting started.",
    "Today is a good day to have a great day.",
    "Your future looks bright.",
]


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

# ── Meme subreddit collection ─────────────────────────────────────────────────
# 60+ subreddits organised by vibe. t!meme [category] to filter.
MEME_CATEGORIES = {
    'general': [
        'memes', 'dankmemes', 'me_irl', '2meirl4meirl', 'technicallythetruth',
        'maybemaybemaybe', 'HolUp', 'facepalm', 'unexpected', 'cursedcomments',
        'rareinsults', 'clevercomebacks', 'ComedyCemetery', 'shitposting',
        'Wellthatsucks', 'Whatcouldgowrong', 'funny', 'AdviceAnimals',
        'mildlyinfuriating', 'tifu', 'NotMyJob', 'quityourbullshit',
    ],
    'gaming': [
        'gamingmemes', 'ProgrammerHumor', 'MinecraftMemes', 'pokemonmemes',
        'LeagueOfMemes', 'ValorantMemes', 'apexlegends', 'FortNiteBR',
        'GenshinImpactMemes', 'pcmasterrace', 'skyrim', 'AmongUsMemes',
        'shittydarksouls', 'Breath_of_the_Wild', 'gaming', 'bindingofisaac',
        'Competitiveoverwatch', 'Sekiro', 'PS5',
    ],
    'wholesome': [
        'wholesomememes', 'MadeMeSmile', 'HumansBeingBros', 'AnimalsBeingBros',
        'rarepuppers', 'eyebleach', 'dankchristianmemes', 'aww',
        'ContagiousLaughter', 'AnimalsBeingDerps', 'Zoomies',
    ],
    'anime': [
        'Animemes', 'anime_irl', 'ShingekiNoKyojin', 'BokuNoHeroAcademia',
        'dankruto', 'MemePiece', 'goodanimemes', 'weeaboo_irl',
        'evangelionmemes', 'AnimeIRL', 'Kaguya_sama', 'kimetsu_no_yaiba',
        'DragonBallSuper', 'BlueLock',
    ],
    'pop': [
        'PrequelMemes', 'SequelMemes', 'marvelmemes', 'theoffice',
        'brooklynninememes', 'HistoryMemes', 'lotrmemes', 'harrypottermemes',
        'DunderMifflin', 'SquaredCircle', 'MusicMemes', 'StrangerThings',
        'betterCallSaul', 'breakingbad', 'gameofthrones',
    ],
    'relatable': [
        'Adulting', 'antiwork', 'teenagers', 'workmemes', 'GenZ',
        'Showerthoughts', 'unpopularopinion', 'bruh', 'adhdmeme',
        'college', 'StudentLoans', 'ProgrammerHumor', 'TrueOffMyChest',
    ],
}

# Flat list of all subreddits for random picks
_ALL_SUBREDDITS = [s for subs in MEME_CATEGORIES.values() for s in subs]

# Aliases so users can type 'game', 'weeb', 'cute', etc.
CATEGORY_ALIASES = {
    'game': 'gaming', 'games': 'gaming', 'gamer': 'gaming', 'pc': 'gaming', 'video': 'gaming',
    'cute': 'wholesome', 'sweet': 'wholesome', 'nice': 'wholesome', 'happy': 'wholesome',
    'weeb': 'anime', 'weeaboo': 'anime', 'manga': 'anime', 'otaku': 'anime',
    'film': 'pop', 'movie': 'pop', 'movies': 'pop', 'culture': 'pop', 'tv': 'pop', 'show': 'pop',
    'life': 'relatable', 'work': 'relatable', 'school': 'relatable', 'real': 'relatable', 'irl': 'relatable',
    'random': 'general', 'dank': 'general', 'funny': 'general', 'lol': 'general',
}


class Fun(commands.Cog, name="Fun"):
    """Lighthearted fun commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='8ball', description='Ask the magic 8-ball a question')
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        response = random.choice(EIGHT_BALL_RESPONSES)
        embed = discord.Embed(color=config.COLORS['purple'])
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"*{response}*", inline=False)
        embed.set_footer(text="Magic 8-Ball")
        await ctx.send(embed=embed)

    @commands.command(name='roll', description='Roll dice (e.g. 2d6, default 1d6)')
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

    @commands.command(name='flip', description='Flip a coin')
    async def flip(self, ctx: commands.Context):
        result = random.choice(['Heads', 'Tails'])
        color = config.COLORS['success'] if result == 'Heads' else config.COLORS['info']
        embed = discord.Embed(
            title="Coin Flip",
            description=f"It landed on **{result}**!",
            color=color,
        )
        await ctx.send(embed=embed)

    @commands.command(name='meme', description='Get a random meme — optional category: general, gaming, wholesome, anime, pop, relatable')
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def meme(self, ctx: commands.Context, category: str = None):
        # Resolve category / alias
        pool = _ALL_SUBREDDITS
        resolved = None
        if category:
            key = category.lower()
            key = CATEGORY_ALIASES.get(key, key)
            if key in MEME_CATEGORIES:
                pool = MEME_CATEGORIES[key]
                resolved = key
            else:
                valid = ', '.join(f'`{k}`' for k in MEME_CATEGORIES)
                await ctx.send(embed=discord.Embed(
                    description=f"Unknown category **{category}**. Valid: {valid}\nYou can also use shortcuts like `game`, `weeb`, `cute`.",
                    color=config.COLORS['error'],
                ))
                return

        import aiohttp
        # Try up to 3 times to get a non-NSFW image post
        for attempt in range(3):
            subreddit = random.choice(pool)
            url = f"https://meme-api.com/gimme/{subreddit}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                if data.get('nsfw', False):
                    continue
                # Skip non-image posts (videos, text)
                img_url = data.get('url', '')
                if not any(img_url.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    continue
                label = f"r/{data['subreddit']}"
                if resolved:
                    label += f" [{resolved}]"
                embed = discord.Embed(title=data['title'], url=data['postLink'], color=config.COLORS['primary'])
                embed.set_image(url=img_url)
                embed.set_footer(text=f"{label} | {data.get('ups', 0):,} upvotes")
                await ctx.send(embed=embed)
                return
            except Exception:
                continue

        await ctx.send(embed=discord.Embed(
            description="Couldn't fetch a meme right now. Try again!",
            color=config.COLORS['error'],
        ))

    @commands.command(name='quote', description='Get an inspirational quote')
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

    @commands.command(name='compliment', description='Compliment a user')
    async def compliment(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        c = random.choice(COMPLIMENTS)
        embed = discord.Embed(
            description=f"{target.mention} {c}",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='roast', description='Friendly roast a user')
    async def roast(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        r = random.choice(ROASTS)
        embed = discord.Embed(
            description=f"{target.mention} {r}",
            color=config.COLORS['warning'],
        )
        embed.set_footer(text="All in good fun!")
        await ctx.send(embed=embed)

    @commands.command(name='choose', description='Pick from a list of options')
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

    @commands.command(name='mock', description='Convert text to SpOnGeBoB mocking format')
    async def mock(self, ctx: commands.Context, *, text: str):
        result = ''.join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(text)
        )
        embed = discord.Embed(description=result, color=config.COLORS['warning'])
        await ctx.send(embed=embed)

    @commands.command(name='reverse', description='Reverse a piece of text')
    async def reverse(self, ctx: commands.Context, *, text: str):
        embed = discord.Embed(description=text[::-1], color=config.COLORS['info'])
        await ctx.send(embed=embed)


    @commands.command(name='fortune', description='Get a fortune cookie message (+1 coin)')
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def fortune(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        msg = random.choice(FORTUNE_COOKIES)
        await db.earn_currency(ctx.author.id, 'coins', 1)
        embed = discord.Embed(
            title="\U0001f960 Fortune Cookie",
            description=f'*"{msg}"*',
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="+1 coin for opening your fortune!")
        await ctx.send(embed=embed)

    @commands.command(name='color', description='Show a random color, or preview a specific hex')
    async def color(self, ctx: commands.Context, hex_code: str = None):
        if hex_code:
            hex_code = hex_code.lstrip('#')
            if len(hex_code) != 6 or not all(c in '0123456789abcdefABCDEF' for c in hex_code):
                await ctx.send(embed=discord.Embed(
                    description="Provide a valid 6-digit hex color. Example: `t!color FF5733`",
                    color=config.COLORS['error'],
                ))
                return
            color_int = int(hex_code, 16)
        else:
            color_int = random.randint(0, 0xFFFFFF)
            hex_code = f"{color_int:06X}"

        r, g, b = (color_int >> 16) & 255, (color_int >> 8) & 255, color_int & 255
        embed = discord.Embed(
            title=f"#{hex_code.upper()}",
            description=f"**Hex:** `#{hex_code.upper()}`\n**RGB:** `{r}, {g}, {b}`",
            color=color_int,
        )
        embed.set_footer(text="t!color for a random color | t!color <hex> to preview a specific one")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
