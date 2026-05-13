"""
cogs/entertainment/commands.py — Entertainment cog (jokes, stories, games).

Phase 3g: extracted verbatim from cogs/entertainment/__init__.py.
"""
import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import logging

import config
import database as db
from core.permissions.tier_gate import require_tier

from .constants import JOKES, TIER_JOKES, STORIES, TIER_STORIES, HANGMAN_WORDS, HANGMAN_STAGES
from .service import *  # noqa: F401, F403
from .views import RPSView, TriviaView

logger = logging.getLogger("tainment.entertainment.commands")


# ─── Entertainment cog ──────────────────────────────────────────────────────

class Entertainment(commands.Cog, name="Entertainment"):
    """Jokes, stories, and interactive games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- Joke --

    @commands.command(name='joke', description='Get a joke')
    @commands.cooldown(1, config.COOLDOWNS['joke'], commands.BucketType.user)
    async def joke(self, ctx: commands.Context, category: str = None):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        allowed = TIER_JOKES.get(tier, ['dad'])

        if category and category.lower() not in JOKES:
            cats = ', '.join(f'`{c}`' for c in JOKES)
            await ctx.send(embed=discord.Embed(
                description=f"Invalid category. Choose from: {cats}",
                color=config.COLORS['error'],
            ))
            return

        if category and category.lower() not in allowed:
            await ctx.send(embed=discord.Embed(
                description=f"Category `{category}` requires **Premium** or higher.",
                color=config.COLORS['warning'],
            ))
            return

        chosen_cat = category.lower() if category else random.choice(allowed)
        setup, punchline = random.choice(JOKES[chosen_cat])

        embed = discord.Embed(
            title=setup,
            description=f"||{punchline}||",
            color=config.COLORS['info'],
        )
        embed.set_footer(text=f"Category: {chosen_cat.capitalize()} | Hover spoiler to reveal punchline")
        await ctx.send(embed=embed)
        await db.log_usage(ctx.author.id, f'joke_{chosen_cat}')

    # -- Story --

    @commands.command(name='story', description='Get a short story')
    @commands.cooldown(1, config.COOLDOWNS['story'], commands.BucketType.user)
    async def story(self, ctx: commands.Context, genre: str = None):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        allowed = TIER_STORIES.get(tier, ['adventure'])

        if genre and genre.lower() not in STORIES:
            genres = ', '.join(f'`{g}`' for g in STORIES)
            await ctx.send(embed=discord.Embed(
                description=f"Invalid genre. Choose from: {genres}",
                color=config.COLORS['error'],
            ))
            return

        if genre and genre.lower() not in allowed:
            await ctx.send(embed=discord.Embed(
                description=f"Genre `{genre}` requires **Premium** or higher.",
                color=config.COLORS['warning'],
            ))
            return

        chosen = genre.lower() if genre else random.choice(allowed)
        text = STORIES[chosen]

        embed = discord.Embed(
            title=f"Story: {chosen.capitalize()}",
            description=text,
            color=config.COLORS['purple'],
        )
        embed.set_footer(text=f"Genre: {chosen.capitalize()}")
        await ctx.send(embed=embed)
        await db.log_usage(ctx.author.id, f'story_{chosen}')

    # -- Rock Paper Scissors --

    @commands.command(name='rps', description='Play Rock Paper Scissors')
    async def rps(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        embed = discord.Embed(
            title="Rock Paper Scissors",
            description="Make your move!",
            color=config.COLORS['primary'],
        )
        view = RPSView(ctx.author)
        await ctx.send(embed=embed, view=view)

    # -- Trivia --

    @commands.command(name='trivia', description='Play trivia (easy/medium/hard)')
    @commands.cooldown(1, config.COOLDOWNS['trivia'], commands.BucketType.user)
    async def trivia(self, ctx: commands.Context, difficulty: str = 'medium'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if tier == 'Basic':
            await ctx.send(embed=discord.Embed(
                description="Trivia requires **Premium** or higher. Use `t!subscribe` to upgrade!",
                color=config.COLORS['warning'],
            ))
            return

        difficulty = difficulty.lower()
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'

        url = f"https://opentdb.com/api.php?amount=1&difficulty={difficulty}&type=multiple"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
            question = data['results'][0]
        except Exception:
            # Fallback question
            question = {
                'question': "What is 2 + 2?",
                'correct_answer': "4",
                'incorrect_answers': ["3", "5", "22"],
                'difficulty': difficulty,
                'category': 'Math',
            }

        import html
        q_text = html.unescape(question['question'])
        question['incorrect_answers'] = [html.unescape(a) for a in question['incorrect_answers']]
        question['correct_answer'] = html.unescape(question['correct_answer'])

        embed = discord.Embed(
            title=f"Trivia — {difficulty.capitalize()}",
            description=q_text,
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"Category: {question.get('category', 'General')} | 20 seconds to answer")
        view = TriviaView(question, ctx.author)
        await ctx.send(embed=embed, view=view)

    # -- Number Guess --

    @commands.command(name='guess', description='Guess a number between 1 and 100')
    @commands.cooldown(1, config.COOLDOWNS['game'], commands.BucketType.user)
    async def guess(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        number = random.randint(1, 100)
        attempts = 7
        guesses_left = attempts

        embed = discord.Embed(
            title="Number Guessing Game",
            description=f"I'm thinking of a number between **1 and 100**.\nYou have **{attempts} attempts**.",
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while guesses_left > 0:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(
                    description=f"Time's up! The number was **{number}**.",
                    color=config.COLORS['error'],
                ))
                return

            guess = int(msg.content)
            guesses_left -= 1

            if guess == number:
                score = guesses_left * 10 + 10
                await db.record_score(ctx.author.id, 'guess', score)
                coin_reward = score * 5
                await db.earn_currency(ctx.author.id, 'coins', coin_reward)
                embed = discord.Embed(
                    title="Correct!",
                    description=f"The number was **{number}**! Score: `{score}` | +**{coin_reward}** \U0001fa99",
                    color=config.COLORS['success'],
                )
                await ctx.send(embed=embed)
                return
            elif guess < number:
                hint = "Too low!"
            else:
                hint = "Too high!"

            color = config.COLORS['warning'] if guesses_left > 2 else config.COLORS['error']
            embed = discord.Embed(
                description=f"{hint} **{guesses_left}** guess{'es' if guesses_left != 1 else ''} remaining.",
                color=color,
            )
            await ctx.send(embed=embed)

        await ctx.send(embed=discord.Embed(
            title="Game over!",
            description=f"The number was **{number}**. Better luck next time!",
            color=config.COLORS['error'],
        ))

    # -- Hangman --

    @commands.command(name='hangman', description='Play Hangman (easy/medium/hard)')
    @commands.cooldown(1, config.COOLDOWNS['game'], commands.BucketType.user)
    @require_tier('Premium')
    async def hangman(self, ctx: commands.Context, difficulty: str = 'medium'):
        # Tier gate handled by @require_tier; user is auto-ensured there.
        difficulty = difficulty.lower()
        if difficulty not in HANGMAN_WORDS:
            difficulty = 'medium'

        word = random.choice(HANGMAN_WORDS[difficulty])
        guessed: set[str] = set()
        wrong = 0
        max_wrong = len(HANGMAN_STAGES) - 1

        def display():
            return ' '.join(c if c in guessed else '_' for c in word)

        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and len(m.content) == 1
                and m.content.isalpha()
            )

        while wrong < max_wrong:
            shown = display()
            embed = discord.Embed(
                title=f"Hangman — {difficulty.capitalize()}",
                color=config.COLORS['primary'],
            )
            embed.add_field(name="Word", value=f"`{shown}`", inline=False)
            embed.add_field(name="Stage", value=HANGMAN_STAGES[wrong], inline=False)
            if guessed:
                embed.add_field(name="Guessed", value=' '.join(sorted(guessed)), inline=False)
            embed.set_footer(text="Type a single letter to guess")
            await ctx.send(embed=embed)

            if '_' not in shown:
                score = (max_wrong - wrong) * 15
                await db.record_score(ctx.author.id, 'hangman', score)
                gem_reward = 3 if wrong == 0 else 1
                await db.earn_currency(ctx.author.id, 'gems', gem_reward)
                await db.earn_currency(ctx.author.id, 'coins', score * 4)
                await ctx.send(embed=discord.Embed(
                    title="You won!",
                    description=(
                        f"The word was **{word}**! Score: `{score}`\n"
                        f"+**{score * 4}** \U0001fa99  +**{gem_reward}** \U0001f48e"
                    ),
                    color=config.COLORS['success'],
                ))
                return

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(
                    description=f"Time's up! The word was **{word}**.",
                    color=config.COLORS['error'],
                ))
                return

            letter = msg.content.lower()
            if letter in guessed:
                await ctx.send(embed=discord.Embed(
                    description=f"You already guessed `{letter}`!",
                    color=config.COLORS['warning'],
                ), delete_after=3)
                continue

            guessed.add(letter)
            if letter not in word:
                wrong += 1

        shown = display()
        if '_' not in shown:
            await ctx.send(embed=discord.Embed(
                title="You won!",
                description=f"The word was **{word}**!",
                color=config.COLORS['success'],
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="You lost!",
                description=f"{HANGMAN_STAGES[max_wrong]}\nThe word was **{word}**.",
                color=config.COLORS['error'],
            ))

    # -- Wordle --

    WORDLE_WORDS = [
        'crane', 'light', 'stone', 'brave', 'plant', 'flame', 'chess', 'ghost',
        'sword', 'magic', 'storm', 'blade', 'ocean', 'river', 'mount', 'cloud',
        'shark', 'whale', 'eagle', 'tiger',
    ]

    @commands.command(name='wordle', description='Play a Wordle-style word game')
    @commands.cooldown(1, config.COOLDOWNS['game'], commands.BucketType.user)
    async def wordle(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if tier in ('Basic', 'Vibe'):
            await ctx.send(embed=discord.Embed(
                description="Wordle requires **Premium** or higher. Use `t!subscribe` to upgrade!",
                color=config.COLORS['warning'],
            ))
            return

        word = random.choice(self.WORDLE_WORDS)
        max_guesses = 6
        history = []

        embed = discord.Embed(
            title="Wordle",
            description=(
                "Guess the **5-letter** word in 6 tries.\n\n"
                "G = correct letter, correct position\n"
                "Y = correct letter, wrong position\n"
                "X = letter not in word"
            ),
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and len(m.content) == 5
                and m.content.isalpha()
            )

        def evaluate(guess: str) -> str:
            result = []
            for i, ch in enumerate(guess):
                if ch == word[i]:
                    result.append(f'[G]{ch.upper()}')
                elif ch in word:
                    result.append(f'[Y]{ch.upper()}')
                else:
                    result.append(f'[X]{ch.upper()}')
            return '  '.join(result)

        for attempt in range(1, max_guesses + 1):
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(
                    description=f"Time's up! The word was **{word}**.",
                    color=config.COLORS['error'],
                ))
                return

            guess = msg.content.lower()
            row = evaluate(guess)
            history.append(row)

            embed = discord.Embed(
                title=f"Wordle — Attempt {attempt}/{max_guesses}",
                description='\n'.join(f'`{r}`' for r in history),
                color=config.COLORS['primary'],
            )

            if guess == word:
                score = (max_guesses - attempt + 1) * 20
                await db.record_score(ctx.author.id, 'wordle', score)
                gem_reward = 5 if attempt == 1 else 3 if attempt <= 3 else 1
                await db.earn_currency(ctx.author.id, 'gems', gem_reward)
                await db.earn_currency(ctx.author.id, 'coins', score * 3)
                embed.color = config.COLORS['success']
                embed.title = "Wordle — You got it!"
                embed.add_field(
                    name="Rewards",
                    value=f"+**{score * 3}** \U0001fa99  +**{gem_reward}** \U0001f48e",
                    inline=False,
                )
                await ctx.send(embed=embed)
                return

            await ctx.send(embed=embed)

        await ctx.send(embed=discord.Embed(
            title="Wordle — Game Over",
            description=f"The word was **{word}**.",
            color=config.COLORS['error'],
        ))


# ─── Setup ──────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Entertainment(bot))
