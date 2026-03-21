import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import config
import database as db

# -- Jokes --

JOKES = {
    'dad': [
        ("Why don't scientists trust atoms?", "Because they make up everything!"),
        ("I'm reading a book about anti-gravity.", "It's impossible to put down!"),
        ("Did you hear about the guy who invented Lifesavers?", "He made a mint."),
        ("Why can't you give Elsa a balloon?", "She'll let it go."),
        ("I used to hate facial hair...", "but then it grew on me."),
    ],
    'tech': [
        ("Why do programmers prefer dark mode?", "Because light attracts bugs!"),
        ("How many programmers does it take to change a lightbulb?", "None, that's a hardware problem."),
        ("Why did the developer go broke?", "Because he used up all his cache."),
        ("What do you call 8 hobbits?", "A hobbyte."),
        ("Why do Java developers wear glasses?", "Because they don't C#."),
    ],
    'puns': [
        ("I'm on a seafood diet.", "I see food and I eat it."),
        ("Time flies like an arrow.", "Fruit flies like a banana."),
        ("I told my wife she was drawing her eyebrows too high.", "She looked surprised."),
        ("I used to be a banker...", "but I lost interest."),
        ("I'm reading a book about mazes.", "I got lost in it."),
    ],
    'animal': [
        ("Why don't elephants use computers?", "Because they're afraid of the mouse."),
        ("What do you call a sleeping dinosaur?", "A dino-snore!"),
        ("Why can't a leopard hide?", "It's always spotted."),
        ("What do you call a fish without eyes?", "A fsh."),
        ("Why did the cat sit on the computer?", "To keep an eye on the mouse."),
    ],
    'food': [
        ("Why did the tomato turn red?", "Because it saw the salad dressing!"),
        ("What do you call a fake noodle?", "An impasta!"),
        ("Why don't eggs tell jokes?", "They'd crack each other up."),
        ("What did the sushi say to the bee?", "Wasabi!"),
        ("Why did the baker go to therapy?", "Because he had too many fillings."),
    ],
}

TIER_JOKES = {
    'Basic': ['dad', 'animal'],
    'Vibe': ['dad', 'animal', 'tech', 'puns', 'food'],
    'Premium': ['dad', 'animal', 'tech', 'puns', 'food'],
    'Pro': ['dad', 'animal', 'tech', 'puns', 'food'],
}

# -- Stories --

STORIES = {
    'adventure': (
        "The ancient map had led you here — a crumbling temple swallowed by jungle. "
        "Inside, golden light pulsed from a chamber. You stepped forward, heart pounding. "
        "A puzzle door blocked the passage, its stone gears frozen for centuries. "
        "After three attempts your hand found the hidden catch. The door groaned open. "
        "Beyond it lay not treasure, but a library — millions of preserved books from a forgotten civilization. "
        "The real treasure was knowledge, and you'd just saved it from oblivion."
    ),
    'mystery': (
        "The lighthouse had been dark for three days when Detective Marlowe arrived on the island. "
        "The keeper, old Ezra, was gone without a trace. No boat, no note, no struggle. "
        "But under the lens room floor Marlowe found a brass button — Navy issue, 1944 vintage. "
        "Following a hunch she climbed to the rocks below. There was Ezra, alive, guarding a sea cave "
        "that hid a smuggling ring operating for thirty years. He'd stayed quiet — until now."
    ),
    'sci-fi': (
        "The colony ship *Meridian* had been in deep sleep for 200 years when the alarm woke Navigator Shen. "
        "On the viewscreen: an impossibly large structure orbiting their destination planet. "
        "It was a ring — 40,000 kilometers across — and it was radiating a signal. "
        "After two days of translation work, the message was four words: 'We have been waiting.' "
        "Shen opened a channel and spoke for all humanity: 'So have we.'"
    ),
    'fantasy': (
        "They said the Dragon of Ashenveil hadn't moved in a hundred years. "
        "Kaela didn't believe them — not until she saw it herself, curled around a mountain like a sleeping cat. "
        "She approached, hands open, speaking the old tongue her grandmother had taught her. "
        "One amber eye cracked open. The dragon exhaled — a gentle warmth, not fire. "
        "It had been waiting for someone who still remembered the words. Together, they flew at dawn."
    ),
    'fable': (
        "A crow found a piece of cheese and flew to a branch to eat in peace. "
        "A fox below called up: 'Your feathers are magnificent! Your voice must match.' "
        "The crow, flattered, opened its beak to sing — and the cheese fell. "
        "The fox snatched it. 'Your voice is lovely,' the fox said, walking away, 'but your judgment needs work.' "
        "The crow learned: beware those whose compliments cost you something."
    ),
}

TIER_STORIES = {
    'Basic': ['adventure', 'fable'],
    'Vibe': ['adventure', 'fable', 'mystery', 'fantasy'],
    'Premium': ['adventure', 'fable', 'mystery', 'fantasy'],
    'Pro': list(STORIES.keys()),
}

# -- Hangman words --

HANGMAN_WORDS = {
    'easy': ['cat', 'dog', 'sun', 'hat', 'cup', 'pen', 'box', 'run', 'fly', 'hop'],
    'medium': ['python', 'castle', 'bridge', 'jungle', 'butter', 'rocket', 'wizard', 'planet'],
    'hard': ['labyrinth', 'quizzical', 'chrysalis', 'paradoxical', 'melancholy', 'archipelago'],
}

HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


def tier_check(tier: str, allowed_tiers: list[str]) -> bool:
    order = ['Basic', 'Premium', 'Pro']
    return order.index(tier) >= min(order.index(t) for t in allowed_tiers)


# -- RPS View --

class RPSView(discord.ui.View):
    OPTIONS = {'Rock': 'paper', 'Paper': 'scissors', 'Scissors': 'rock'}
    BEATS = {'rock': 'scissors', 'paper': 'rock', 'scissors': 'paper'}

    def __init__(self, player: discord.Member):
        super().__init__(timeout=30)
        self.player = player

    async def _handle(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        bot_choice = random.choice(['rock', 'paper', 'scissors'])
        p = choice.lower()
        if self.BEATS[p] == bot_choice:
            result, color = "You win!", config.COLORS['success']
        elif self.BEATS[bot_choice] == p:
            result, color = "You lose!", config.COLORS['error']
        else:
            result, color = "It's a tie!", config.COLORS['warning']

        embed = discord.Embed(
            title=f"Rock Paper Scissors — {result}",
            description=f"You: **{choice}** | Bot: **{bot_choice.capitalize()}**",
            color=color,
        )
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Rock', style=discord.ButtonStyle.secondary, emoji='\U0001faa8')
    async def rock(self, i, b): await self._handle(i, 'Rock')

    @discord.ui.button(label='Paper', style=discord.ButtonStyle.secondary, emoji='\U0001f4c4')
    async def paper(self, i, b): await self._handle(i, 'Paper')

    @discord.ui.button(label='Scissors', style=discord.ButtonStyle.secondary, emoji='\u2702\ufe0f')
    async def scissors(self, i, b): await self._handle(i, 'Scissors')


# -- Trivia View --

class TriviaView(discord.ui.View):
    def __init__(self, question: dict, player: discord.Member):
        super().__init__(timeout=20)
        self.player = player
        self.correct = question['correct_answer']
        self.answered = False
        options = question['incorrect_answers'] + [self.correct]
        random.shuffle(options)
        for opt in options[:4]:
            btn = discord.ui.Button(label=opt[:80], style=discord.ButtonStyle.primary)
            btn.callback = self._make_callback(opt)
            self.add_item(btn)

    def _make_callback(self, answer: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
            if self.answered:
                return
            self.answered = True
            self.stop()
            for child in self.children:
                child.disabled = True
                if isinstance(child, discord.ui.Button):
                    if child.label == self.correct:
                        child.style = discord.ButtonStyle.success
                    elif child.label == answer and answer != self.correct:
                        child.style = discord.ButtonStyle.danger

            if answer == self.correct:
                result = "Correct!"
                color = config.COLORS['success']
            else:
                result = f"Wrong! Answer: **{self.correct}**"
                color = config.COLORS['error']

            embed = discord.Embed(description=result, color=color)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback


class Entertainment(commands.Cog, name="Entertainment"):
    """Jokes, stories, and interactive games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- Joke --

    @commands.hybrid_command(name='joke', description='Get a joke')
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

    @commands.hybrid_command(name='story', description='Get a short story')
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

    @commands.hybrid_command(name='rps', description='Play Rock Paper Scissors')
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

    @commands.hybrid_command(name='trivia', description='Play trivia (easy/medium/hard)')
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

    @commands.hybrid_command(name='guess', description='Guess a number between 1 and 100')
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

    @commands.hybrid_command(name='hangman', description='Play Hangman (easy/medium/hard)')
    @commands.cooldown(1, config.COOLDOWNS['game'], commands.BucketType.user)
    async def hangman(self, ctx: commands.Context, difficulty: str = 'medium'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if tier in ('Basic', 'Vibe'):
            await ctx.send(embed=discord.Embed(
                description="Hangman requires **Premium** or higher. Use `t!subscribe` to upgrade!",
                color=config.COLORS['warning'],
            ))
            return

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

    @commands.hybrid_command(name='wordle', description='Play a Wordle-style word game')
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

    # -- Blackjack (Pro only) --

    @commands.hybrid_command(name='blackjack', aliases=['bj'], description='Play Blackjack (Pro tier)')
    @commands.cooldown(1, config.COOLDOWNS['game'], commands.BucketType.user)
    async def blackjack(self, ctx: commands.Context, bet: int = 100):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if tier != 'Pro':
            await ctx.send(embed=discord.Embed(
                description="Blackjack is a **Pro** exclusive feature.",
                color=config.COLORS['warning'],
            ))
            return

        bal = await db.get_balance(ctx.author.id)
        if bet <= 0 or bet > bal:
            await ctx.send(embed=discord.Embed(
                description=f"Invalid bet. You have `{bal:,}` coins.",
                color=config.COLORS['error'],
            ))
            return

        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [(r, s) for r in ranks for s in suits]
        random.shuffle(deck)

        def card_value(hand):
            total, aces = 0, 0
            for rank, _ in hand:
                if rank in ('J', 'Q', 'K'):
                    total += 10
                elif rank == 'A':
                    total += 11
                    aces += 1
                else:
                    total += int(rank)
            while total > 21 and aces:
                total -= 10
                aces -= 1
            return total

        def hand_str(hand):
            return '  '.join(f'[{r}]' for r, _ in hand)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        def make_embed(reveal_dealer=False):
            pv = card_value(player_hand)
            dv = card_value(dealer_hand)
            embed = discord.Embed(title="Blackjack", color=config.COLORS['primary'])
            embed.add_field(name=f"Your hand ({pv})", value=f"`{hand_str(player_hand)}`", inline=False)
            if reveal_dealer:
                embed.add_field(name=f"Dealer's hand ({dv})", value=f"`{hand_str(dealer_hand)}`", inline=False)
            else:
                embed.add_field(name="Dealer's hand (?)", value=f"`[{dealer_hand[0][0]}] [?]`", inline=False)
            embed.set_footer(text="React H to Hit, S to Stand")
            return embed

        msg = await ctx.send(embed=make_embed())
        await msg.add_reaction('\U0001f1ed')  # H
        await msg.add_reaction('\U0001f1f8')  # S

        def react_check(r, u):
            return u == ctx.author and str(r.emoji) in ('\U0001f1ed', '\U0001f1f8') and r.message.id == msg.id

        while True:
            pv = card_value(player_hand)
            if pv == 21:
                break
            if pv > 21:
                await msg.edit(embed=discord.Embed(
                    title="Bust! You went over 21.",
                    description=f"Hand: `{hand_str(player_hand)}` ({pv})\nLost **{bet:,}** coins.",
                    color=config.COLORS['error'],
                ))
                await db.update_balance(ctx.author.id, -bet)
                return

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', check=react_check, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(description="Game timed out. Bet returned.", color=config.COLORS['warning']))
                return

            if str(reaction.emoji) == '\U0001f1ed':
                player_hand.append(deck.pop())
                await msg.edit(embed=make_embed())
            else:
                break

        # Dealer plays
        while card_value(dealer_hand) < 17:
            dealer_hand.append(deck.pop())

        pv = card_value(player_hand)
        dv = card_value(dealer_hand)

        if dv > 21 or pv > dv:
            result = f"You win! +**{bet:,}** coins."
            color = config.COLORS['success']
            await db.update_balance(ctx.author.id, bet)
        elif pv == dv:
            result = "Push! Bet returned."
            color = config.COLORS['warning']
        else:
            result = f"Dealer wins. -**{bet:,}** coins."
            color = config.COLORS['error']
            await db.update_balance(ctx.author.id, -bet)

        final = make_embed(reveal_dealer=True)
        final.color = color
        final.add_field(name="Result", value=result, inline=False)
        await msg.edit(embed=final)


async def setup(bot: commands.Bot):
    await bot.add_cog(Entertainment(bot))
