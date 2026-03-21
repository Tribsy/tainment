"""
Extra fun commands that earn coins, gems, and tokens.
Commands: typerace, riddle, wouldyourather, emojidecode, fastmath, hotpotato, wordchain
"""

import discord
from discord.ext import commands
import random
import asyncio
import time
import config
import database as db


# ── Type Race ─────────────────────────────────────────────────────────────────

TYPERACE_SENTENCES = [
    "the quick brown fox jumps over the lazy dog",
    "discord bots make communities more fun and interactive",
    "popfusion is a music discovery community built for fans",
    "fishing for legendary fish requires patience and a good rod",
    "the best way to earn gems is by winning skill challenges",
    "music brings people together no matter where they are from",
    "practice makes perfect when it comes to typing fast",
    "daily coins and streaks help you climb the leaderboard",
    "every great community starts with passionate members",
    "hip hop pop rock and electronic are the four genre lanes",
    "never stop exploring new music and discovering new artists",
    "the diamond fishing rod has the shortest cooldown of them all",
]


# ── Riddles ───────────────────────────────────────────────────────────────────

RIDDLES = [
    ("I speak without a mouth and hear without ears. I have no body but come alive with the wind. What am I?", "echo"),
    ("The more you take, the more you leave behind. What am I?", "footsteps"),
    ("I have cities but no houses. I have mountains but no trees. I have water but no fish. What am I?", "map"),
    ("What has hands but cannot clap?", "clock"),
    ("I am not alive but I grow. I don't have lungs but I need air. I don't have a mouth but water kills me. What am I?", "fire"),
    ("What can travel around the world while staying in a corner?", "stamp"),
    ("The more you have of it the less you see. What is it?", "darkness"),
    ("What has keys but no locks a space but no room and you can enter but can't go inside?", "keyboard"),
    ("I have a head and a tail but no body. What am I?", "coin"),
    ("What gets wetter the more it dries?", "towel"),
    ("What has one eye but cannot see?", "needle"),
    ("What goes up but never comes down?", "age"),
    ("What comes once in a minute twice in a moment but never in a thousand years?", "letter m"),
    ("I am always in front of you but cannot be seen. What am I?", "future"),
    ("What can you break even if you never pick it up or touch it?", "silence"),
    ("What runs but never walks has a mouth but never talks has a head but never weeps has a bed but never sleeps?", "river"),
    ("What has four legs in the morning two at noon and three in the evening?", "human"),
    ("The person who makes it sells it. The person who buys it never uses it. The person who uses it doesn't know they're using it. What is it?", "coffin"),
]


# ── Would You Rather ──────────────────────────────────────────────────────────

WYR_PAIRS = [
    ("Have unlimited money but never be able to travel", "Travel anywhere for free but have no savings"),
    ("Be able to fly but only 1 metre off the ground", "Be able to teleport but only to places you've been before"),
    ("Know every language in the world", "Play every musical instrument perfectly"),
    ("Live without music", "Live without the internet"),
    ("Always say what you're thinking", "Never be able to express your emotions"),
    ("Have a pause button on your life", "Have a rewind button on your life"),
    ("Be the funniest person in the room", "Be the smartest person in the room"),
    ("Never use social media again", "Never watch another movie or TV show"),
    ("Have 10 close friends", "Have 1000 acquaintances"),
    ("Be famous but hated", "Be unknown but loved"),
    ("Only be able to whisper", "Only be able to shout"),
    ("Age only physically", "Age only mentally"),
    ("Have no fingernails", "Have no eyebrows"),
    ("Always be 10 minutes late", "Always be 20 minutes early"),
    ("Live in the past", "Live in the future"),
]


# ── Emoji Decode ──────────────────────────────────────────────────────────────

EMOJI_PHRASES = [
    ("\U0001f3b5\U0001f3a4\U0001f3b8", "music artist rock"),
    ("\U0001f40d\U0001f34e", "snake apple"),
    ("\U0001f525\U0001f69a", "fire truck"),
    ("\U0001f3a3\U0001f420", "fishing fish"),
    ("\U0001f4fa\U0001f3ae", "television game"),
    ("\U0001f30a\U0001f3c4", "ocean surf"),
    ("\U0001f4f1\U0001f4f8", "phone camera"),
    ("\U0001f3e0\U0001f511", "house key"),
    ("\u2601\ufe0f\u26a1", "cloud lightning"),
    ("\U0001f30d\U0001f31f", "world star"),
    ("\U0001f9e0\U0001f4a1", "brain idea"),
    ("\U0001f3c6\U0001f947", "trophy gold"),
    ("\U0001f480\U0001f3b8", "skull guitar"),
    ("\U0001f40b\U0001f30a", "whale ocean"),
    ("\U0001f3a8\U0001f58c\ufe0f", "art paint"),
]


# ── Word Chain ────────────────────────────────────────────────────────────────

# Words that are definitely single valid English words for chain starts
CHAIN_STARTERS = [
    "apple", "ocean", "night", "eagle", "light", "tiger", "river", "earth",
    "house", "sword", "storm", "black", "flame", "crown", "music", "power",
]


# ── Cog ───────────────────────────────────────────────────────────────────────

class FunGames(commands.Cog, name="Fun Games"):
    """Extra fun commands with coin, gem, and token rewards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track active wordchain sessions per channel
        self._wordchain_active: set[int] = set()

    # ── Type Race ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='typerace', aliases=['tr', 'type'], description='Type a sentence as fast as you can to win coins!')
    @commands.cooldown(1, 20, commands.BucketType.channel)
    async def typerace(self, ctx: commands.Context):
        sentence = random.choice(TYPERACE_SENTENCES)
        embed = discord.Embed(
            title="\u2328\ufe0f Type Race!",
            description=(
                "Type the sentence below **exactly** as shown.\n"
                "First to finish wins! You have **25 seconds**.\n\n"
                f"```{sentence}```"
            ),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text="Copy and paste won't work — you must type it!")
        await ctx.send(embed=embed)

        start = time.monotonic()

        def check(m):
            return m.channel == ctx.channel and not m.author.bot and m.content.lower() == sentence

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=25)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description="Nobody finished in time.",
                color=config.COLORS['error'],
            ))
            return

        elapsed = time.monotonic() - start
        wpm = int((len(sentence.split()) / elapsed) * 60)
        # Reward: base 100 coins, bonus for speed
        coin_reward = max(50, 300 - int(elapsed * 8))
        token_reward = 2 if elapsed < 10 else 1

        await db.ensure_user(winner_msg.author.id, winner_msg.author.name)
        await db.earn_currency(winner_msg.author.id, 'coins', coin_reward)
        await db.earn_currency(winner_msg.author.id, 'tokens', token_reward)

        color = config.COLORS['gold'] if elapsed < 8 else config.COLORS['success'] if elapsed < 15 else config.COLORS['info']
        await ctx.send(embed=discord.Embed(
            title=f"\U0001f3c6 {winner_msg.author.display_name} wins!",
            description=(
                f"Time: **{elapsed:.2f}s** | ~**{wpm} WPM**\n"
                f"+**{coin_reward}** \U0001fa99  +**{token_reward}** \U0001f3ab"
            ),
            color=color,
        ))

    # ── Riddle ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='riddle', description='Answer a riddle to win coins and gems!')
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def riddle(self, ctx: commands.Context):
        question, answer = random.choice(RIDDLES)
        # Some answers have multiple valid words — accept any of them
        valid = set(answer.lower().split())

        embed = discord.Embed(
            title="\U0001f9e0 Riddle Time!",
            description=f"{question}\n\nYou have **30 seconds** — first correct answer wins!",
            color=config.COLORS['purple'],
        )
        embed.set_footer(text="Type your answer in chat")
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.channel == ctx.channel
                and not m.author.bot
                and bool(valid.intersection(m.content.lower().split()))
            )

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"The answer was **{answer}**.",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(winner_msg.author.id, winner_msg.author.name)
        await db.earn_currency(winner_msg.author.id, 'coins', 80)
        await db.earn_currency(winner_msg.author.id, 'gems', 1)

        await ctx.send(embed=discord.Embed(
            title=f"\u2705 {winner_msg.author.display_name} got it!",
            description=f"Answer: **{answer}**\n+**80** \U0001fa99  +**1** \U0001f48e",
            color=config.COLORS['success'],
        ))

    # ── Would You Rather ──────────────────────────────────────────────────────

    @commands.hybrid_command(name='wouldyourather', aliases=['wyr'], description='Vote on a would you rather question — earn tokens!')
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def wouldyourather(self, ctx: commands.Context):
        a, b = random.choice(WYR_PAIRS)
        votes = {'a': set(), 'b': set()}

        class WYRView(discord.ui.View):
            def __init__(inner_self):
                super().__init__(timeout=20)

            @discord.ui.button(label=f'Option A  (0)', style=discord.ButtonStyle.primary, custom_id='wyr_a')
            async def vote_a(inner_self, interaction: discord.Interaction, btn: discord.ui.Button):
                uid = interaction.user.id
                votes['b'].discard(uid)
                votes['a'].add(uid)
                inner_self._update_labels()
                await interaction.response.edit_message(view=inner_self)

            @discord.ui.button(label=f'Option B  (0)', style=discord.ButtonStyle.danger, custom_id='wyr_b')
            async def vote_b(inner_self, interaction: discord.Interaction, btn: discord.ui.Button):
                uid = interaction.user.id
                votes['a'].discard(uid)
                votes['b'].add(uid)
                inner_self._update_labels()
                await interaction.response.edit_message(view=inner_self)

            def _update_labels(inner_self):
                for item in inner_self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.custom_id == 'wyr_a':
                            item.label = f'Option A  ({len(votes["a"])})'
                        else:
                            item.label = f'Option B  ({len(votes["b"])})'

        view = WYRView()
        embed = discord.Embed(
            title="\U0001f914 Would You Rather...",
            color=config.COLORS['info'],
        )
        embed.add_field(name="\U0001f535 Option A", value=a, inline=False)
        embed.add_field(name="\U0001f534 Option B", value=b, inline=False)
        embed.set_footer(text="Vote! Everyone who votes earns 1 token.")
        msg = await ctx.send(embed=embed, view=view)

        await asyncio.sleep(20)

        # Disable buttons and show result
        for item in view.children:
            item.disabled = True

        total = len(votes['a']) + len(votes['b'])
        if total == 0:
            result = "No one voted!"
            color = config.COLORS['warning']
        else:
            a_pct = int(len(votes['a']) / total * 100)
            b_pct = 100 - a_pct
            winner_label = "A" if len(votes['a']) >= len(votes['b']) else "B"
            result = (
                f"\U0001f535 Option A: **{len(votes['a'])}** votes ({a_pct}%)\n"
                f"\U0001f534 Option B: **{len(votes['b'])}** votes ({b_pct}%)\n\n"
                f"**Option {winner_label}** wins!"
            )
            color = config.COLORS['success']

        final_embed = discord.Embed(
            title="\U0001f914 Would You Rather — Results",
            description=result,
            color=color,
        )
        final_embed.add_field(name="\U0001f535 Option A", value=a, inline=False)
        final_embed.add_field(name="\U0001f534 Option B", value=b, inline=False)
        await msg.edit(embed=final_embed, view=view)

        # Reward all voters
        all_voters = votes['a'] | votes['b']
        for uid in all_voters:
            try:
                await db.earn_currency(uid, 'tokens', 1)
            except Exception:
                pass

        if all_voters:
            await ctx.send(
                f"\u2705 {len(all_voters)} voter{'s' if len(all_voters) != 1 else ''} each earned **1** \U0001f3ab",
                delete_after=8,
            )

    # ── Emoji Decode ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name='emojidecode', aliases=['emoji', 'emojiquiz'], description='Decode an emoji phrase to win coins and tokens!')
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def emojidecode(self, ctx: commands.Context):
        emojis, answer = random.choice(EMOJI_PHRASES)
        valid = set(answer.lower().split())

        embed = discord.Embed(
            title="\U0001f50d Emoji Decode!",
            description=f"What does this represent?\n\n# {emojis}\n\nFirst correct answer wins! **20 seconds**.",
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Type any word from the answer")
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.channel == ctx.channel
                and not m.author.bot
                and bool(valid.intersection(m.content.lower().split()))
            )

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"The answer was **{answer}** {emojis}",
                color=config.COLORS['error'],
            ))
            return

        await db.ensure_user(winner_msg.author.id, winner_msg.author.name)
        await db.earn_currency(winner_msg.author.id, 'coins', 60)
        await db.earn_currency(winner_msg.author.id, 'tokens', 2)

        await ctx.send(embed=discord.Embed(
            title=f"\u2705 {winner_msg.author.display_name} decoded it!",
            description=f"**{answer}** {emojis}\n+**60** \U0001fa99  +**2** \U0001f3ab",
            color=config.COLORS['success'],
        ))

    # ── Fast Math ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='fastmath', aliases=['fm', 'mathrace'], description='Race to answer a math question — first wins coins!')
    @commands.cooldown(1, 12, commands.BucketType.channel)
    async def fastmath(self, ctx: commands.Context):
        a = random.randint(2, 30)
        b = random.randint(2, 30)
        op = random.choice(['+', '-', '*'])
        expr = f"{a} {op} {b}"
        answer = int(eval(expr))  # Safe: only +/-/* with integers

        embed = discord.Embed(
            title="\u26a1 Fast Math!",
            description=f"First to answer wins **100** \U0001fa99!\n\n## `{expr} = ?`",
            color=config.COLORS['info'],
        )
        embed.set_footer(text="Type just the number!")
        await ctx.send(embed=embed)

        start = time.monotonic()

        def check(m):
            if m.channel != ctx.channel or m.author.bot:
                return False
            try:
                return int(m.content.strip()) == answer
            except ValueError:
                return False

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=15)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"`{expr} = {answer}`",
                color=config.COLORS['error'],
            ))
            return

        elapsed = time.monotonic() - start
        bonus = 50 if elapsed < 3 else 0
        total = 100 + bonus

        await db.ensure_user(winner_msg.author.id, winner_msg.author.name)
        await db.earn_currency(winner_msg.author.id, 'coins', total)

        desc = f"`{expr} = {answer}` — answered in **{elapsed:.2f}s**\n+**{total}** \U0001fa99"
        if bonus:
            desc += " *(speed bonus!)*"

        await ctx.send(embed=discord.Embed(
            title=f"\u2705 {winner_msg.author.display_name} wins!",
            description=desc,
            color=config.COLORS['success'],
        ))

    # ── Hot Potato ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='hotpotato', aliases=['potato', 'hp'], description='Pass the hot potato — don\'t get caught holding it!')
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def hotpotato(self, ctx: commands.Context):
        holder = ctx.author
        pot = 50  # coins in the pot
        fuse = random.uniform(8, 20)  # when it explodes
        start = time.monotonic()

        await db.ensure_user(ctx.author.id, ctx.author.name)

        class PotatoView(discord.ui.View):
            def __init__(inner_self):
                super().__init__(timeout=fuse)
                inner_self.passed = False

            @discord.ui.button(label='\U0001f954 Pass the Potato!', style=discord.ButtonStyle.danger)
            async def pass_btn(inner_self, interaction: discord.Interaction, btn: discord.ui.Button):
                nonlocal holder
                if interaction.user.id == holder.id:
                    await interaction.response.send_message(
                        "You can't pass it to yourself! Someone else needs to click!", ephemeral=True
                    )
                    return
                await db.ensure_user(interaction.user.id, interaction.user.name)
                prev = holder
                holder = interaction.user
                inner_self.passed = True
                inner_self.stop()
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="\U0001f954 Hot Potato!",
                        description=f"{prev.display_name} passed it to **{holder.display_name}**!\nKeep passing!",
                        color=discord.Color.orange(),
                    ),
                    view=None,
                )

        while time.monotonic() - start < fuse:
            view = PotatoView()
            embed = discord.Embed(
                title="\U0001f954 Hot Potato!",
                description=(
                    f"**{holder.display_name}** is holding the potato!\n"
                    f"Click to grab it and pass it on!\n\n"
                    f"Pot: **{pot}** \U0001fa99 — loser pays it to the last passer."
                ),
                color=discord.Color.orange(),
            )
            embed.set_footer(text="Don't get caught holding it when it explodes!")
            msg = await ctx.send(embed=embed, view=view)

            await view.wait()
            if not view.passed:
                break
            # Update message reference for next round
            await msg.edit(view=None)

        # Whoever holds it when the loop ends loses
        loser = holder
        loser_bal = await db.get_currency(loser.id, 'coins')
        fine = min(pot, loser_bal)
        if fine > 0:
            await db.spend_currency(loser.id, 'coins', fine)

        await ctx.send(embed=discord.Embed(
            title="\U0001f4a5 BOOM!",
            description=(
                f"The potato exploded in **{loser.display_name}**'s hands!\n"
                f"-**{fine}** \U0001fa99"
            ),
            color=config.COLORS['error'],
        ))

    # ── Word Chain ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='wordchain', aliases=['wc', 'chain'], description='Chain words — each must start with the last letter of the previous!')
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def wordchain(self, ctx: commands.Context):
        if ctx.channel.id in self._wordchain_active:
            await ctx.send(embed=discord.Embed(
                description="A word chain game is already running in this channel!",
                color=config.COLORS['warning'],
            ))
            return

        self._wordchain_active.add(ctx.channel.id)
        starter = random.choice(CHAIN_STARTERS)
        chain = [starter]
        used = {starter}
        current_letter = starter[-1]
        scores: dict[int, int] = {}
        last_user = None
        streak = 0

        embed = discord.Embed(
            title="\U0001f4dd Word Chain!",
            description=(
                f"Starting word: **{starter}**\n"
                f"Next word must start with **{current_letter.upper()}**\n\n"
                "Rules:\n"
                "\u2022 Each word must start where the last one ended\n"
                "\u2022 No repeating words\n"
                "\u2022 No two turns in a row\n"
                "\u2022 Game ends after **45 seconds** of silence\n\n"
                "Top scorer earns **gems**! Every valid word earns **20** \U0001fa99."
            ),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"Chain length: 1  |  Next letter: {current_letter.upper()}")
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.channel == ctx.channel
                and not m.author.bot
                and m.content.isalpha()
            )

        try:
            while True:
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=45)
                except asyncio.TimeoutError:
                    break

                word = msg.content.lower().strip()

                # Validation
                if word[0] != current_letter:
                    await msg.add_reaction('\u274c')
                    await ctx.send(embed=discord.Embed(
                        description=f"**{word}** doesn't start with **{current_letter.upper()}**! Game over.",
                        color=config.COLORS['error'],
                    ), delete_after=5)
                    break

                if word in used:
                    await msg.add_reaction('\u274c')
                    await ctx.send(embed=discord.Embed(
                        description=f"**{word}** was already used! Game over.",
                        color=config.COLORS['error'],
                    ), delete_after=5)
                    break

                if msg.author.id == last_user:
                    await msg.add_reaction('\u274c')
                    await ctx.send(embed=discord.Embed(
                        description="You can't go twice in a row! Game over.",
                        color=config.COLORS['error'],
                    ), delete_after=5)
                    break

                # Valid
                await msg.add_reaction('\u2705')
                chain.append(word)
                used.add(word)
                current_letter = word[-1]
                last_user = msg.author.id
                streak += 1
                scores[msg.author.id] = scores.get(msg.author.id, 0) + 1

                await db.ensure_user(msg.author.id, msg.author.name)
                await db.earn_currency(msg.author.id, 'coins', 20)

        finally:
            self._wordchain_active.discard(ctx.channel.id)

        # Results
        if not scores:
            await ctx.send(embed=discord.Embed(
                description=f"Chain ended at length **{len(chain)}**. No rewards.",
                color=config.COLORS['warning'],
            ))
            return

        winner_id = max(scores, key=lambda k: scores[k])
        winner = ctx.guild.get_member(winner_id) if ctx.guild else None
        winner_name = winner.display_name if winner else f"User {winner_id}"

        gem_reward = min(len(chain) // 3, 10)
        if gem_reward > 0:
            await db.earn_currency(winner_id, 'gems', gem_reward)

        score_lines = []
        for uid, count in sorted(scores.items(), key=lambda x: -x[1]):
            m = ctx.guild.get_member(uid) if ctx.guild else None
            name = m.display_name if m else f"User {uid}"
            score_lines.append(f"**{name}** — {count} word{'s' if count != 1 else ''}")

        embed = discord.Embed(
            title="\U0001f4dd Word Chain Complete!",
            description=f"Chain length: **{len(chain)}**\n\n" + "\n".join(score_lines),
            color=config.COLORS['gold'],
        )
        if gem_reward:
            embed.set_footer(text=f"{winner_name} earned {gem_reward} gems for most words!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FunGames(bot))
