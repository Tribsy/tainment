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
    "You will soon have a reason to celebrate.",
    "Your current struggles are laying the foundation for future success.",
    "The darkest night produces the brightest stars.",
    "Frugality today brings freedom tomorrow.",
    "A question you forgot you asked is about to be answered.",
    "Someone is thinking of you fondly right now.",
    "Stop overthinking and start doing.",
    "Love yourself first, and everything else falls into line.",
    "Less is often more.",
    "Debt will soon become a thing of the past.",
    "The only true wisdom is in knowing you know nothing.",
    "The time for hesitation is over.",
    "A long journey is in your immediate future.",
    "Do not let the noise of others' opinions drown out your inner voice.",
    "You are a magnet for good vibes.",
    "Keep your secrets close for the next 48 hours.",
    "What you seek is also seeking you.",
    "An unexpected message will bring joy to your heart.",
    "Pack your bags; a sudden trip is imminent.",
    "Worrying is like paying a debt you do not owe.",
    "Celebrate the quirks of your loved ones.",
    "You will soon be the reason for someone's smile.",
    "Stop planning and start executing.",
    "The next song you hear contains a message for you.",
    "Forgive others not because they deserve forgiveness, but because you deserve peace.",
    "A lucrative partnership is on the horizon.",
    "You are entering a season of vibrant joy.",
    "You will soon be recognized for your unique talents.",
    "A smooth sea never made a skilled sailor.",
    "Cherish the silence you share with a good friend.",
    "You are entering a period of great financial luck.",
    "Laughter is the best medicine, and you are about to get a big dose.",
    "Small joys will string together to make a wonderful day.",
    "A new friendship will change your perspective on life.",
    "You will soon discover a new favorite thing.",
    "Do not judge a day by the harvest you reap, but by the seeds you plant.",
    "True strength lies in gentleness.",
    "Surround yourself with colors that make you happy.",
    "Action cures fear.",
    "The project you are considering will be highly successful.",
    "Do not wait for the perfect moment; take the moment and make it perfect.",
    "A fascinating stranger will cross your path in transit.",
    "Listen more than you speak.",
    "A seemingly bad event will turn out to be a blessing in disguise.",
    "A piece of technology will glitch in your favor.",
    "You will find clarity in a complex emotional situation.",
    "The leap of faith you are considering will be worth it.",
    "A mysterious gift will arrive without a return address.",
    "You are closer to the truth than you realize.",
    "A pet or animal will bring immense joy into your home.",
    "An upcoming risk will yield a handsome reward.",
    "Your capacity to love is your greatest strength.",
    "Take the scenic route; adventure awaits.",
    "A celebration with loved ones is in your near future.",
    "Sometimes the best action is no action at all.",
    "Deep conversations will lead to deep connections.",
    "Financial freedom is within your reach.",
    "Peace of mind is arriving in the mail.",
    "Your unique perspective is highly valuable.",
    "A mentor will help guide you to the top.",
    "Your persistence will wear down any obstacles to your success.",
    "The obstacle is the path.",
    "Run towards the challenge, not away from it.",
    "Do not fear the wind; it only makes your roots grow deeper.",
    "Be ruthless with distractions.",
    "Trust your gut and jump.",
    "You are standing at a crossroads; choose the path less traveled.",
    "A casual acquaintance will become a vital ally.",
    "Defy expectations today.",
    "Comparison is the thief of joy.",
    "Sweet treats and sweet moments are in your future.",
    "Diligence is the mother of good luck.",
    "Tomorrow's sunrise brings a fresh revelation.",
    "A problem shared is a problem halved.",
    "Expect the unexpected on a Tuesday.",
    "Step into the spotlight; it is your time to shine.",
    "A delightful surprise will greet you at home.",
    "Dance like nobody is watching; it will free your soul.",
    "Momentum is building; keep pushing forward.",
    "Don't let doubt dictate your actions.",
    "Let your inner child come out to play today.",
    "Your positive attitude attracts positive cash flow.",
    "You will soon understand the true meaning of companionship.",
    "Make the first move.",
    "Your listening ear is someone's greatest comfort.",
    "Wisdom comes not from age, but from understanding.",
    "You will be the peacemaker in a coming conflict.",
    "A wise investment will secure your future.",
    "A detour will become the main destination.",
    "The answer you seek is hidden in a dream.",
    "Happiness is a choice, not a destination.",
    "Look closely at your reflection; a change is occurring.",
    "Confront your fears, and they will shrink.",
    "Your dedication will catch the eye of someone important.",
    "A reason to smile is just around the corner.",
    "Perfection is the enemy of progress.",
    "Patience is a bitter plant, but its fruit is sweet.",
    "A shadow from your past will return bringing closure.",
    "Embrace the unknown with open arms.",
    "A message hidden in a book will speak directly to you.",
    "Be proactive, not reactive.",
    "A bend in the road is not the end of the road.",
    "Serenity is washing over your life.",
    "Someone admires you from afar.",
    "A closed mind is a heavy burden.",
    "You will cross paths with a soulmate.",
    "The truth will always set you free.",
    "Gratitude turns what we have into enough.",
    "A long-held dream is about to become a profitable reality.",
    "Time heals what reason cannot.",
    "An unusual animal encounter will serve as an omen.",
    "Take charge of your destiny.",
    "Say yes to the next scary opportunity.",
    "You have the golden touch this month.",
    "You cannot direct the wind, but you can adjust your sails.",
    "Your determination is your greatest asset.",
    "You will soon be the life of the party.",
    "Protect your relationships as you would a treasure.",
    "Now is the time to try something completely new.",
    "Do not burn bridges; you may need to cross them again.",
    "Expect a heartfelt apology from someone soon.",
    "Volunteer for the difficult task; it will build your reputation.",
    "Let go of what you cannot control.",
    "A forgotten memory will provide the key to a current problem.",
    "Happiness is an inside job, and you are getting a promotion.",
    "Good food, good friends, and good times are guaranteed.",
    "A sudden decision will lead to a grand adventure.",
    "Your creative ideas will lead to financial gain.",
    "Seek respect, not attention. It lasts longer.",
    "True wealth is found in contentment.",
    "A bold move will change the course of your year.",
    "True love requires courage; be brave.",
    "The hardest tests yield the most valuable lessons.",
    "Your mind is a garden; your thoughts are the seeds.",
    "Your optimism will pay off beautifully.",
    "The coming storm will wash away your current troubles.",
    "Watch for a lucky coin; it marks the start of a streak.",
    "Embrace the silliness of life.",
    "Trust is the foundation of the love you seek.",
    "Trust the timing of your relationships.",
    "A cozy evening will restore your soul.",
    "Your boldness will inspire those around you.",
    "A sudden craving will lead you to an important encounter.",
    "A midnight thought will lead to a daytime breakthrough.",
    "Your charm will win over a difficult person.",
    "A golden opportunity will present itself this week.",
    "A misunderstanding will soon be resolved peacefully.",
    "You will soon find comfort in a stranger's words.",
    "Dare to be different.",
    "Your professional network will expand significantly.",
    "You will soon receive an invitation you cannot refuse.",
    "Fortune favors the bold in business.",
    "A shared laugh will be the start of something beautiful.",
    "You will laugh so hard you cry.",
    "Push through the final hurdle; victory is close.",
    "Romance will bloom in a highly unusual place.",
    "Don't be afraid to fail big.",
    "The weather will change your plans, but for the better.",
    "Your hard work is about to pay off in a major way.",
    "Financial stability is closer than you think.",
    "A breath of fresh air will revitalize your spirit.",
    "You will soon feel a deep sense of belonging.",
    "Forge your own path instead of following the crowd.",
    "Abundance is your birthright; claim it.",
    "Good cheer will follow you everywhere you go this week.",
    "Do it now. Sometimes "later" becomes "never".",
    "Your perspective defines your reality.",
    "Wealth comes to those who wait, but faster to those who work.",
    "A mistake is just a discovery of what doesn't work.",
    "Stand up for what you believe in, even if you stand alone.",
    "Someone is preparing a surprise for you behind the scenes.",
    "Allow yourself to be ridiculously happy.",
    "A nostalgic moment will bring warmth to your heart.",
    "Throw caution to the wind this weekend.",
    "Your comfort zone is a beautiful place, but nothing grows there.",
    "Love is closer than you think; look around.",
    "A simple compliment will make your entire day.",
    "You will soon discover a hidden talent you didn't know you had.",
    "You will find a lost item in the most unlikely place.",
    "Stop looking for love, and let it find you.",
    "Seize the day before it slips away.",
    "A stranger will offer you a piece of advice; take it.",
    "An antique or old object will bring you good fortune.",
    "You will find harmony in a previously chaotic situation.",
    "Ask for what you want; you just might get it.",
    "Expect the best, and your career will deliver it.",
    "A romantic getaway will spark a new flame.",
    "Your courage will be tested, and you will pass.",
    "What you lose today will be replaced by something better tomorrow.",
    "Love is the answer to the question you are asking.",
    "An inside joke will keep you smiling for days.",
    "Rest is a weapon; use it well.",
    "Find joy in the ordinary today.",
    "A happy coincidence is heading your way.",
    "Vulnerability will bring you closer to your partner.",
    "A hobby will bring you profound satisfaction.",
    "You are about to enter your happy era.",
    "An upcoming event will bring you pure childlike joy.",
    "A mysterious door will open for you soon.",
    "Prosperity will soon knock on your door.",
    "Pay attention to the signs; the universe is talking to you.",
    "Your kindness will forge an unbreakable bond.",
    "Stop asking for permission.",
    "You will soon experience a perfect, lazy Sunday.",
    "You will soon hold the keys to your own success.",
    "You are about to embark on a spiritual journey.",
    "Today is a great day to have a great day.",
    "Speak your mind; someone needs to hear your truth.",
    "An old friend will soon reconnect with you.",
    "You will soon witness a rare and beautiful event.",
    "The love you give will return to you magnified.",
    "Make time for those who matter most.",
    "An old hobby will become a new source of income.",
    "Silence is sometimes the best answer.",
    "A leap in the dark will land you in the light.",
    "Start before you are ready.",
    "Invest in yourself; it pays the best interest.",
    "Prepare for a sudden upward shift in your career.",
    "An act of bravery will earn you immense respect.",
    "Wisdom is knowing what to ignore.",
    "Your lucky numbers are 4, 17, 23, 38, 42, and 50.",
    "A romantic gesture is being planned for you.",
    "A physical challenge will bring mental clarity.",
    "A shared secret will deepen a friendship.",
    "Contentment will be your default state of mind soon.",
    "A secret will be revealed to you by accident.",
    "You will soon uncover a piece of hidden history.",
    "Your smile will brighten a stranger's dark day.",
    "Courage is fear that has said its prayers.",
    "A quiet mind hears the loudest truths.",
    "An empty cup is ready to be filled.",
    "The magic you are looking for is in the work you are avoiding.",
    "Break the rules carefully, but break them.",
    "Eliminate I can't from your vocabulary today.",
    "Open your heart to the possibility of a surprise romance.",
    "The seeds of success you planted are beginning to sprout.",
    "Happiness will find you when you stop looking for it.",
    "Every end is a new beginning.",
    "A small idea will turn into a massive triumph.",
    "Forgiveness will heal a broken relationship.",
    "Keep your eyes open; your next big break is near.",
    "A beautiful sunset will give you a moment of profound peace.",
    "A side hustle will turn into a main success.",
    "Prepare for a paradigm shift.",
    "A shift in the wind will bring a shift in your luck.",
    "A coincidence this week will be too strange to ignore.",
    "Your skills are in high demand.",
    "Keep your heart open to second chances.",
    "The journey of a thousand miles begins with a single step.",
    "Good news regarding a contract or agreement is coming.",
    "You will soon master a skill that brings great value.",
    "Laughter will be the soundtrack of your weekend.",
    "A new career path will open up for you.",
    "The universe is conspiring to make you smile.",
    "Keep a close eye on the number 7 this week.",
    "Knowledge speaks, but wisdom listens.",
    "Expect a pleasant surprise in your bank account.",
    "Do not take your closest friends for granted.",
    "Enjoy the little things, for one day you will realize they were the big things.",
    "Your family will bring you unexpected happiness this month.",
    "Let your heart be light.",
    "You will find joy in an unexpected chore.",
    "A new connection will feel like coming home.",
    "A beautiful, smart, and loving person will be coming into your life.",
    "Trust the synchronicity happening in your life right now.",
    "Your path will cross with someone going the exact same way.",
    "Generosity will bring wealth back to you tenfold.",
    "You will soon feel lighter than air.",
    "Look up; a sign is waiting for you in the sky.",
    "You will experience a moment of perfect clarity and peace.",
    "Action expresses priorities; align yours today.",
    "You are deeply loved by someone you haven't met yet.",
    "The simple things in life are the most extraordinary.",
    "You will soon wake up feeling completely rested and happy.",
    "A promotion or raise is heading your way.",
    "Trust your instincts when it comes to money.",
    "Do not let yesterday take up too much of today.",
    "Your character is your destiny.",
    "Take a chance on an unlikely idea.",
    "Your empathy will draw wonderful people to you.",
    "The puzzle pieces of your life are about to snap into place.",
    "Focus on the step in front of you, not the whole staircase.",
    "You will solve a problem that brings you great acclaim.",
    "Music will lift your spirits today.",
    "A burst of spontaneous energy will lead to fun.",
    "The best time to plant a tree was 20 years ago; the second best time is now.",
    "You will soon be celebrating a major milestone.",
    "You will stumble upon a hidden gem in your own city.",
    "Be the hero of your own story.",
    "An unexpected windfall is in your near future.",
    "A gesture of kindness will lead to lasting love.",
    "Look out for a stranger wearing red; they bring news.",
    "Success is a journey, and you are on the right path.",
    "The only constant in life is change; embrace it.",
    "You are precisely where you need to be right now.",
    "Do the thing you think you cannot do.",
    "Protect your boundaries fiercely.",
    "A favorite food will bring you immense comfort soon.",
    "Failure is simply the opportunity to begin again, this time more intelligently.",
    "Leadership is in your future; step up to the plate.",
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
