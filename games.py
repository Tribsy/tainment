import discord
from discord.ext import commands
import random
import asyncio
import config
import database as db
import questions as qbank

# ── Tic-Tac-Toe ────────────────────────────────────────────────────────────────

EMPTY, X_MARK, O_MARK = 0, 1, 2
WINNING_LINES = [
    (0,1,2),(3,4,5),(6,7,8),  # rows
    (0,3,6),(1,4,7),(2,5,8),  # cols
    (0,4,8),(2,4,6),           # diagonals
]

def check_winner(board: list[int]) -> int:
    for a, b, c in WINNING_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return 0

def board_full(board: list[int]) -> bool:
    return all(c != EMPTY for c in board)

def bot_move(board: list[int]) -> int:
    """Simple AI: win > block > center > corner > random."""
    def can_win(mark):
        for a, b, c in WINNING_LINES:
            vals = [board[a], board[b], board[c]]
            if vals.count(mark) == 2 and vals.count(EMPTY) == 1:
                return [a, b, c][vals.index(EMPTY)]
        return None

    m = can_win(O_MARK)
    if m is not None: return m
    m = can_win(X_MARK)
    if m is not None: return m
    if board[4] == EMPTY: return 4
    corners = [i for i in (0,2,6,8) if board[i] == EMPTY]
    if corners: return random.choice(corners)
    return random.choice([i for i, c in enumerate(board) if c == EMPTY])


class TicTacToeView(discord.ui.View):
    LABELS = {EMPTY: '\u200b', X_MARK: 'X', O_MARK: 'O'}
    STYLES = {EMPTY: discord.ButtonStyle.secondary, X_MARK: discord.ButtonStyle.danger, O_MARK: discord.ButtonStyle.primary}

    def __init__(self, player: discord.Member):
        super().__init__(timeout=120)
        self.board = [EMPTY] * 9
        self.player = player
        self.game_over = False
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        for i in range(9):
            val = self.board[i]
            btn = discord.ui.Button(
                label=self.LABELS[val],
                style=self.STYLES[val],
                disabled=(val != EMPTY or self.game_over),
                row=i // 3,
            )
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _make_cb(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
            if self.board[idx] != EMPTY or self.game_over:
                return

            self.board[idx] = X_MARK
            winner = check_winner(self.board)

            if not winner and not board_full(self.board):
                move = bot_move(self.board)
                self.board[move] = O_MARK
                winner = check_winner(self.board)

            self._build_buttons()

            if winner == X_MARK:
                self.game_over = True
                embed = discord.Embed(title="You win! You're the best.", color=config.COLORS['success'])
            elif winner == O_MARK:
                self.game_over = True
                embed = discord.Embed(title="Bot wins! Better luck next time.", color=config.COLORS['error'])
            elif board_full(self.board):
                self.game_over = True
                embed = discord.Embed(title="It's a draw!", color=config.COLORS['warning'])
            else:
                embed = discord.Embed(title="Tic-Tac-Toe — Your turn (X)", color=config.COLORS['primary'])

            await interaction.response.edit_message(embed=embed, view=self)
        return callback


# ── Connect Four ───────────────────────────────────────────────────────────────

COLS, ROWS = 7, 6
RED, YELLOW = 1, 2
EMPTY_C4 = 0

def drop_piece(board, col, player):
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] == EMPTY_C4:
            board[row][col] = player
            return row
    return -1

def check_c4_winner(board):
    for r in range(ROWS):
        for c in range(COLS - 3):
            if board[r][c] and board[r][c] == board[r][c+1] == board[r][c+2] == board[r][c+3]:
                return board[r][c]
    for r in range(ROWS - 3):
        for c in range(COLS):
            if board[r][c] and board[r][c] == board[r+1][c] == board[r+2][c] == board[r+3][c]:
                return board[r][c]
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            if board[r][c] and board[r][c] == board[r+1][c+1] == board[r+2][c+2] == board[r+3][c+3]:
                return board[r][c]
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            if board[r][c] and board[r][c] == board[r-1][c+1] == board[r-2][c+2] == board[r-3][c+3]:
                return board[r][c]
    return 0

def board_c4_full(board):
    return all(board[0][c] != EMPTY_C4 for c in range(COLS))

def render_c4(board):
    pieces = {EMPTY_C4: '\u26ab', RED: '\U0001f534', YELLOW: '\U0001f7e1'}
    lines = []
    for row in board:
        lines.append(''.join(pieces[c] for c in row))
    lines.append(''.join(f'{i+1}\ufe0f\u20e3' for i in range(COLS)))
    return '\n'.join(lines)

def bot_c4_move(board):
    # Try to win, then block, then center, then random
    for player in (YELLOW, RED):
        for col in range(COLS):
            if board[0][col] != EMPTY_C4:
                continue
            test = [r[:] for r in board]
            drop_piece(test, col, player)
            if check_c4_winner(test):
                return col
    center = [3,2,4,1,5,0,6]
    for col in center:
        if board[0][col] == EMPTY_C4:
            return col
    return 0

class ConnectFourView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=180)
        self.board = [[EMPTY_C4]*COLS for _ in range(ROWS)]
        self.player = player
        self.game_over = False
        for i in range(COLS):
            btn = discord.ui.Button(label=str(i+1), style=discord.ButtonStyle.primary, row=0)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _make_cb(self, col: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
            if self.game_over or self.board[0][col] != EMPTY_C4:
                await interaction.response.send_message("That column is full!", ephemeral=True)
                return

            drop_piece(self.board, col, RED)
            winner = check_c4_winner(self.board)

            if not winner and not board_c4_full(self.board):
                bot_col = bot_c4_move(self.board)
                drop_piece(self.board, bot_col, YELLOW)
                winner = check_c4_winner(self.board)

            # Disable full columns
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label.isdigit():
                    c = int(item.label) - 1
                    item.disabled = self.board[0][c] != EMPTY_C4

            board_str = render_c4(self.board)
            if winner == RED:
                self.game_over = True
                embed = discord.Embed(title="You win!", description=board_str, color=config.COLORS['success'])
                for item in self.children:
                    item.disabled = True
            elif winner == YELLOW:
                self.game_over = True
                embed = discord.Embed(title="Bot wins!", description=board_str, color=config.COLORS['error'])
                for item in self.children:
                    item.disabled = True
            elif board_c4_full(self.board):
                self.game_over = True
                embed = discord.Embed(title="Draw!", description=board_str, color=config.COLORS['warning'])
                for item in self.children:
                    item.disabled = True
            else:
                embed = discord.Embed(title="Connect Four — Your turn (red)", description=board_str, color=config.COLORS['primary'])
            await interaction.response.edit_message(embed=embed, view=self)
        return callback


# ── Scramble words ─────────────────────────────────────────────────────────────

SCRAMBLE_WORDS = [
    'python', 'discord', 'server', 'channel', 'message', 'command',
    'premium', 'economy', 'fortune', 'captain', 'diamond', 'phantom',
    'journey', 'balance', 'thunder', 'crystal', 'quantum', 'mystery',
    'penguin', 'giraffe', 'volcano', 'horizon', 'lantern', 'courage',
]

def scramble(word: str) -> str:
    letters = list(word)
    for _ in range(10):
        random.shuffle(letters)
    if ''.join(letters) == word:
        letters[0], letters[-1] = letters[-1], letters[0]
    return ''.join(letters)


# ── Math problems ──────────────────────────────────────────────────────────────

def make_math_problem(difficulty: str) -> tuple[str, int]:
    if difficulty == 'easy':
        a, b = random.randint(1, 20), random.randint(1, 20)
        op = random.choice(['+', '-'])
    elif difficulty == 'medium':
        a, b = random.randint(1, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
    else:
        a, b = random.randint(2, 20), random.randint(2, 20)
        op = random.choice(['+', '-', '*'])

    expr = f"{a} {op} {b}"
    answer = eval(expr)  # Safe: only +/-/* with integers
    return expr, answer


# ── Games Cog ─────────────────────────────────────────────────────────────────

class Games(commands.Cog, name="Games"):
    """Extra games: Tic-Tac-Toe, Connect Four, Scramble, Math Quiz, Coin Flip Duel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- Tic-Tac-Toe --

    @commands.hybrid_command(name='ttt', aliases=['tictactoe'], description='Play Tic-Tac-Toe against the bot')
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def ttt(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        embed = discord.Embed(
            title="Tic-Tac-Toe — Your turn (X)",
            description="You are **X**, bot is **O**.",
            color=config.COLORS['primary'],
        )
        view = TicTacToeView(ctx.author)
        await ctx.send(embed=embed, view=view)

    # -- Connect Four --

    @commands.hybrid_command(name='c4', aliases=['connectfour'], description='Play Connect Four against the bot')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def c4(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        board = [[EMPTY_C4]*COLS for _ in range(ROWS)]
        view = ConnectFourView(ctx.author)
        embed = discord.Embed(
            title="Connect Four — Your turn (red)",
            description=render_c4(board),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text="Click a column number to drop your piece!")
        await ctx.send(embed=embed, view=view)

    # -- Word Scramble --

    @commands.hybrid_command(name='scramble', description='Unscramble a word before time runs out')
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def scramble_cmd(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        word = random.choice(SCRAMBLE_WORDS)
        jumbled = scramble(word)

        embed = discord.Embed(
            title="Word Scramble",
            description=f"Unscramble this word:\n\n# `{jumbled.upper()}`\n\nYou have **20 seconds**!",
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)

        def check(m):
            return m.channel == ctx.channel and not m.author.bot and m.content.lower() == word

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"Nobody got it. The word was **{word}**.",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(winner_msg.author.id, winner_msg.author.name)
        has_doubler = await db.has_active_item(winner_msg.author.id, 'double_tokens')
        tokens = 4 if has_doubler else 2
        coins = 75
        await db.earn_currency(winner_msg.author.id, 'coins', coins)
        await db.earn_currency(winner_msg.author.id, 'tokens', tokens)
        await ctx.send(embed=discord.Embed(
            title="Correct!",
            description=(
                f"{winner_msg.author.mention} unscrambled **{word}**!\n"
                f"+**{coins}** \U0001fa99  +**{tokens}** \U0001f3ab"
            ),
            color=config.COLORS['success'],
        ))

    # -- Math Quiz --

    @commands.hybrid_command(name='mathquiz', aliases=['math'], description='Rapid-fire math quiz (10 questions)')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def mathquiz(self, ctx: commands.Context, difficulty: str = 'medium'):
        difficulty = difficulty.lower()
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'

        await db.ensure_user(ctx.author.id, ctx.author.name)

        # Bonus Round item gives 15 questions instead of 10
        has_bonus = await db.has_active_item(ctx.author.id, 'bonus_round')
        total = 15 if has_bonus else 10
        score = 0

        qs = qbank.sample(difficulty, total)

        embed = discord.Embed(
            title=f"Math Quiz — {difficulty.capitalize()}",
            description=(
                f"**{total} questions** from a pool of {qbank.pool_sizes()[difficulty]:,}, 8 seconds each.\n"
                f"Type your answer!\n"
                f"\U0001fa99 30 per correct | \U0001f48e bonus gems for 60%+ score"
                + (" | **Bonus Round active!**" if has_bonus else "")
            ),
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)
        await asyncio.sleep(1.5)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        for i in range(1, total + 1):
            q = qs[i - 1]
            embed = discord.Embed(
                title=f"Question {i}/{total}",
                description=f"## `{q.text} = ?`",
                color=config.COLORS['info'],
            )
            await ctx.send(embed=embed)

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=8)
                try:
                    if int(msg.content.strip()) == q.answer:
                        score += 1
                        await msg.add_reaction('\u2705')
                    else:
                        await msg.add_reaction('\u274c')
                        await ctx.send(embed=discord.Embed(
                            description=f"Wrong! Answer was **{q.answer}**",
                            color=config.COLORS['error'],
                        ), delete_after=3)
                except ValueError:
                    await msg.add_reaction('\u274c')
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(
                    description=f"Time's up! Answer was **{q.answer}**.",
                    color=config.COLORS['warning'],
                ), delete_after=3)

        pct = int(score / total * 100)
        # Coins reward: 30 per correct
        coin_reward = score * 30
        # Gems reward: based on performance
        gem_reward = 0
        if pct == 100:
            gem_reward = 10
        elif pct >= 80:
            gem_reward = 5
        elif pct >= 60:
            gem_reward = 2

        await db.earn_currency(ctx.author.id, 'coins', coin_reward)
        if gem_reward:
            await db.earn_currency(ctx.author.id, 'gems', gem_reward)

        color = config.COLORS['success'] if pct >= 70 else config.COLORS['warning'] if pct >= 40 else config.COLORS['error']
        reward_str = f"+**{coin_reward}** \U0001fa99"
        if gem_reward:
            reward_str += f"  +**{gem_reward}** \U0001f48e"
        embed = discord.Embed(
            title="Quiz Complete!",
            description=(
                f"Score: **{score}/{total}** ({pct}%)\n"
                f"Rewards: {reward_str}"
            ),
            color=color,
        )
        await db.record_score(ctx.author.id, 'mathquiz', score)
        await ctx.send(embed=embed)

    # -- Higher or Lower --

    @commands.hybrid_command(name='highlow', aliases=['hilo'], description='Higher or Lower card game')
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def highlow(self, ctx: commands.Context, bet: int = 50):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        bal = await db.get_balance(ctx.author.id)

        if bet <= 0 or bet > bal:
            await ctx.send(embed=discord.Embed(
                description=f"Invalid bet. Balance: `{bal:,}`",
                color=config.COLORS['error'],
            ))
            return

        deck = list(range(1, 14)) * 4
        random.shuffle(deck)
        current = deck.pop()
        streak = 0
        total_won = 0

        CARD_NAMES = {1:'A',11:'J',12:'Q',13:'K'}

        def card_name(v): return CARD_NAMES.get(v, str(v))

        class HiLoView(discord.ui.View):
            def __init__(inner_self):
                super().__init__(timeout=30)
                inner_self.choice = None

            @discord.ui.button(label='Higher', style=discord.ButtonStyle.success, emoji='\u2b06\ufe0f')
            async def higher(inner_self, interaction: discord.Interaction, btn):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your game!", ephemeral=True)
                    return
                inner_self.choice = 'higher'
                inner_self.stop()
                await interaction.response.defer()

            @discord.ui.button(label='Lower', style=discord.ButtonStyle.danger, emoji='\u2b07\ufe0f')
            async def lower(inner_self, interaction: discord.Interaction, btn):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your game!", ephemeral=True)
                    return
                inner_self.choice = 'lower'
                inner_self.stop()
                await interaction.response.defer()

            @discord.ui.button(label='Cash Out', style=discord.ButtonStyle.secondary, emoji='\U0001f4b0')
            async def cashout(inner_self, interaction: discord.Interaction, btn):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your game!", ephemeral=True)
                    return
                inner_self.choice = 'cashout'
                inner_self.stop()
                await interaction.response.defer()

        msg = None
        while deck:
            view = HiLoView()
            embed = discord.Embed(
                title="Higher or Lower",
                description=(
                    f"Current card: **{card_name(current)}**\n"
                    f"Streak: `{streak}` | Potential win: **+{bet * (streak+1):,}** coins"
                ),
                color=config.COLORS['primary'],
            )
            if msg:
                await msg.edit(embed=embed, view=view)
            else:
                msg = await ctx.send(embed=embed, view=view)

            await view.wait()
            if view.choice is None or view.choice == 'cashout':
                if total_won > 0:
                    await db.update_balance(ctx.author.id, total_won)
                await msg.edit(embed=discord.Embed(
                    description=f"Cashed out! Net: **+{total_won:,}** coins.",
                    color=config.COLORS['success'],
                ), view=None)
                return

            next_card = deck.pop()
            correct = (view.choice == 'higher' and next_card >= current) or \
                      (view.choice == 'lower' and next_card <= current)

            if correct:
                streak += 1
                total_won += bet
                current = next_card
                if streak >= 8:
                    await db.update_balance(ctx.author.id, total_won)
                    await msg.edit(embed=discord.Embed(
                        title="Max streak reached!",
                        description=f"Won **+{total_won:,}** coins on a {streak}-card streak!",
                        color=config.COLORS['gold'],
                    ), view=None)
                    return
            else:
                await db.update_balance(ctx.author.id, -bet)
                await msg.edit(embed=discord.Embed(
                    title="Wrong!",
                    description=f"Next card was **{card_name(next_card)}**. Lost **{bet:,}** coins.",
                    color=config.COLORS['error'],
                ), view=None)
                return

    # -- Coin Flip Duel --

    @commands.hybrid_command(name='duel', description='Challenge another user to a coin flip duel')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def duel(self, ctx: commands.Context, opponent: discord.Member, bet: int):
        if opponent.id == ctx.author.id:
            await ctx.send(embed=discord.Embed(description="You can't duel yourself.", color=config.COLORS['error']))
            return
        if opponent.bot:
            await ctx.send(embed=discord.Embed(description="Bots don't have coins!", color=config.COLORS['error']))
            return
        if bet <= 0:
            await ctx.send(embed=discord.Embed(description="Bet must be positive.", color=config.COLORS['error']))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_user(opponent.id, opponent.name)

        challenger_bal = await db.get_balance(ctx.author.id)
        opponent_bal = await db.get_balance(opponent.id)

        if challenger_bal < bet:
            await ctx.send(embed=discord.Embed(description=f"You need `{bet:,}` coins but only have `{challenger_bal:,}`.", color=config.COLORS['error']))
            return
        if opponent_bal < bet:
            await ctx.send(embed=discord.Embed(description=f"{opponent.mention} doesn't have enough coins.", color=config.COLORS['error']))
            return

        class AcceptView(discord.ui.View):
            def __init__(inner_self):
                super().__init__(timeout=30)
                inner_self.accepted = None

            @discord.ui.button(label='Accept', style=discord.ButtonStyle.success)
            async def accept(inner_self, interaction, btn):
                if interaction.user.id != opponent.id:
                    await interaction.response.send_message("This duel isn't for you!", ephemeral=True)
                    return
                inner_self.accepted = True
                inner_self.stop()
                await interaction.response.defer()

            @discord.ui.button(label='Decline', style=discord.ButtonStyle.danger)
            async def decline(inner_self, interaction, btn):
                if interaction.user.id != opponent.id:
                    await interaction.response.send_message("This duel isn't for you!", ephemeral=True)
                    return
                inner_self.accepted = False
                inner_self.stop()
                await interaction.response.defer()

        view = AcceptView()
        embed = discord.Embed(
            title="Coin Flip Duel!",
            description=(
                f"{ctx.author.mention} challenges {opponent.mention} to a duel!\n"
                f"Bet: **{bet:,}** coins each\n\n"
                f"{opponent.mention}, do you accept?"
            ),
            color=config.COLORS['gold'],
        )
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if not view.accepted:
            await msg.edit(embed=discord.Embed(
                description=f"{opponent.mention} declined the duel.",
                color=config.COLORS['warning'],
            ), view=None)
            return

        winner = random.choice([ctx.author, opponent])
        loser = opponent if winner == ctx.author else ctx.author
        await db.earn_currency(winner.id, 'coins', bet)
        await db.spend_currency(loser.id, 'coins', bet)
        # Winner also earns a token
        has_doubler = await db.has_active_item(winner.id, 'double_tokens')
        tokens = 2 if has_doubler else 1
        await db.earn_currency(winner.id, 'tokens', tokens)

        await msg.edit(embed=discord.Embed(
            title="Coin flipped!",
            description=(
                f"{winner.mention} wins **{bet:,}** \U0001fa99 from {loser.mention}!\n"
                f"+**{tokens}** \U0001f3ab"
            ),
            color=config.COLORS['success'],
        ), view=None)

    # -- Snake (text-based, simplified) --

    @commands.hybrid_command(name='snap', description='Quick reaction snap game')
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def snap(self, ctx: commands.Context):
        """Type SNAP as fast as possible when the bot says GO!"""
        import time
        delay = random.uniform(2, 6)
        embed = discord.Embed(
            title="Get Ready...",
            description="Type **SNAP** as fast as you can when I say GO!",
            color=config.COLORS['primary'],
        )
        await ctx.send(embed=embed)
        await asyncio.sleep(delay)

        start = time.monotonic()
        go_msg = await ctx.send(embed=discord.Embed(
            title="GO!",
            description="Type **SNAP** now!",
            color=config.COLORS['success'],
        ))

        def check(m):
            return m.channel == ctx.channel and not m.author.bot and m.content.upper() == 'SNAP'

        try:
            reply = await self.bot.wait_for('message', check=check, timeout=5)
            elapsed = time.monotonic() - start
            ms = int(elapsed * 1000)
            coin_reward = max(20, 250 - ms // 5)
            has_doubler = await db.has_active_item(reply.author.id, 'double_tokens')
            token_reward = 2 if has_doubler else 1
            await db.ensure_user(reply.author.id, reply.author.name)
            await db.earn_currency(reply.author.id, 'coins', coin_reward)
            await db.earn_currency(reply.author.id, 'tokens', token_reward)
            color = config.COLORS['success'] if ms < 500 else config.COLORS['warning'] if ms < 1500 else config.COLORS['info']
            embed = discord.Embed(
                title=f"{reply.author.display_name} wins!",
                description=(
                    f"Reaction time: **{ms}ms**\n"
                    f"+**{coin_reward}** \U0001fa99  +**{token_reward}** \U0001f3ab"
                ),
                color=color,
            )
            await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            await go_msg.edit(embed=discord.Embed(
                description="Nobody reacted in time!",
                color=config.COLORS['error'],
            ))


    # -- Roulette (Premium+) --

    @commands.command(name='roulette', aliases=['rl'], description='Bet on red or black (Premium+)')
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def roulette(self, ctx: commands.Context, bet: int, color: str = 'red'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        tier_order = ['Basic', 'Vibe', 'Premium', 'Pro']
        if tier_order.index(tier) < tier_order.index('Premium'):
            await ctx.send(embed=discord.Embed(
                title="Premium Required",
                description="Roulette requires a **Premium** or **Pro** subscription.\nUse `t!subscribe` to upgrade.",
                color=config.COLORS['warning'],
            ))
            return

        color = color.lower()
        if color not in ('red', 'black', 'r', 'b'):
            await ctx.send(embed=discord.Embed(
                description="Choose `red` or `black`. Example: `t!roulette 100 red`",
                color=config.COLORS['error'],
            ))
            return

        bal = await db.get_currency(ctx.author.id, 'coins')
        if bet <= 0 or bet > bal:
            await ctx.send(embed=discord.Embed(
                description=f"Invalid bet. Balance: `{bal:,}` \U0001fa99",
                color=config.COLORS['error'],
            ))
            return

        chosen = 'red' if color in ('red', 'r') else 'black'
        # 18 red, 18 black, 2 green (0 and 00) — green = house wins
        roll = random.randint(0, 37)
        if roll == 0 or roll == 37:
            result_color = 'green'
        elif roll % 2 == 1:
            result_color = 'red'
        else:
            result_color = 'black'

        color_emoji = {'red': '\U0001f534', 'black': '\u26ab', 'green': '\U0001f7e2'}[result_color]

        if result_color == chosen:
            payout = int(bet * 1.9)
            profit = payout - bet
            await db.earn_currency(ctx.author.id, 'coins', profit)
            embed = discord.Embed(
                title=f"Roulette — {color_emoji} {result_color.capitalize()}!",
                description=f"You bet `{bet:,}` on **{chosen}** and won **+{payout:,}** \U0001fa99\nNew balance: `{bal + profit:,}`",
                color=config.COLORS['success'],
            )
        else:
            await db.spend_currency(ctx.author.id, 'coins', bet)
            embed = discord.Embed(
                title=f"Roulette — {color_emoji} {result_color.capitalize()}!",
                description=f"You bet `{bet:,}` on **{chosen}** and lost **{bet:,}** \U0001fa99\nNew balance: `{bal - bet:,}`",
                color=config.COLORS['error'],
            )

        embed.set_footer(text="Roulette | 1.9x payout | Premium")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
