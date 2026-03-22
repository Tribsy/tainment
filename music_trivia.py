"""
Music Trivia cog.
Commands: musictrivia, lyricsguess, namethetune
"""

import discord
from discord.ext import commands
import random
import asyncio
import config
import database as db
import music_data as md


TIER_ORDER = ['Basic', 'Vibe', 'Premium', 'Pro']


def _tier_gte(user_tier: str, required: str) -> bool:
    return TIER_ORDER.index(user_tier) >= TIER_ORDER.index(required)


def _locked_embed(required: str) -> discord.Embed:
    return discord.Embed(
        title="\U0001f512 Feature Locked",
        description=f"This command requires **{required}** tier or higher.\nUpgrade with `t!subscribe`.",
        color=config.COLORS['error'],
    )


class MusicTrivia(commands.Cog, name="Music Trivia"):
    """Music trivia and lyric guessing games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── musictrivia ───────────────────────────────────────────────────────────

    @commands.hybrid_command(name='musictrivia', aliases=['mtrivia', 'mq'], description='Answer a music trivia question to win coins!')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def musictrivia(self, ctx: commands.Context, genre: str = None):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)

        # Pick question pool
        if genre and genre.lower() in md.TRIVIA_QUESTIONS:
            pool = md.TRIVIA_QUESTIONS[genre.lower()]
        else:
            pool = [q for qs in md.TRIVIA_QUESTIONS.values() for q in qs]

        q = random.choice(pool)
        options = q['options'][:]
        random.shuffle(options)

        labels = ['A', 'B', 'C', 'D']
        correct_label = labels[options.index(q['a'])]

        votes: dict[str, discord.User] = {}

        class TriviaView(discord.ui.View):
            def __init__(inner_self):
                super().__init__(timeout=20)
                for label, opt in zip(labels, options):
                    btn = discord.ui.Button(
                        label=f"{label}: {opt}",
                        style=discord.ButtonStyle.primary,
                        custom_id=f'trivia_{label}',
                    )
                    btn.callback = inner_self._make_callback(label)
                    inner_self.add_item(btn)

            def _make_callback(inner_self, label: str):
                async def callback(interaction: discord.Interaction):
                    if interaction.user.id in votes:
                        await interaction.response.send_message("You already answered!", ephemeral=True)
                        return
                    votes[str(interaction.user.id)] = label
                    await interaction.response.send_message(
                        f"You chose **{label}**! Wait for the result...", ephemeral=True
                    )
                return callback

        embed = discord.Embed(
            title="\U0001f3b5 Music Trivia!",
            description=f"**{q['q']}**\n\nYou have **20 seconds** — use the buttons to answer!",
            color=config.COLORS['purple'],
        )
        embed.set_footer(text=f"Genre: {genre or 'Mixed'}  |  First correct answer wins coins")
        msg = await ctx.send(embed=embed, view=TriviaView())
        await asyncio.sleep(20)

        # Disable buttons
        for item in msg.components:
            pass  # view timed out

        # Calculate rewards
        correct_users = [uid for uid, ans in votes.items() if ans == correct_label]
        coins_per = 80
        gems_per = 5 if _tier_gte(tier, 'Vibe') else 0
        tokens_per = 2 if _tier_gte(tier, 'Pro') else 0

        # Apply trivia_surge if applicable
        if await db.has_active_item(ctx.author.id, 'trivia_surge'):
            coins_per *= 2
            gems_per *= 2

        for uid_str in correct_users:
            uid = int(uid_str)
            await db.earn_currency(uid, 'coins', coins_per)
            if gems_per:
                await db.earn_currency(uid, 'gems', gems_per)
            if tokens_per:
                await db.earn_currency(uid, 'tokens', tokens_per)

        option_str = '\n'.join(f"**{l}:** {o}" for l, o in zip(labels, options))
        reward_parts = [f"+**{coins_per}** \U0001fa99"]
        if gems_per:
            reward_parts.append(f"+**{gems_per}** \U0001f48e")
        if tokens_per:
            reward_parts.append(f"+**{tokens_per}** \U0001f3ab")
        reward_str = '  '.join(reward_parts)

        result_embed = discord.Embed(
            title="\U0001f3b5 Music Trivia — Result!",
            color=config.COLORS['success'] if correct_users else config.COLORS['error'],
        )
        result_embed.add_field(name="Question", value=q['q'], inline=False)
        result_embed.add_field(name="Correct Answer", value=f"**{correct_label}: {q['a']}**", inline=False)
        if correct_users:
            result_embed.add_field(name=f"Correct ({len(correct_users)})", value=reward_str, inline=False)
        else:
            result_embed.add_field(name="No one got it right!", value="Better luck next time.", inline=False)

        await msg.edit(embed=result_embed, view=None)

    # ── lyricsguess ───────────────────────────────────────────────────────────

    @commands.hybrid_command(name='lyricsguess', aliases=['lyricguess', 'lg'], description='Guess the song from partial lyrics! (Vibe+)')
    @commands.cooldown(1, 20, commands.BucketType.channel)
    async def lyricsguess(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        snippet = random.choice(md.LYRIC_SNIPPETS)
        title_words = set(snippet['title'].lower().split())
        artist_words = set(snippet['artist'].lower().split())

        # Check for hint item
        hint_active = await db.has_active_item(ctx.author.id, 'music_hint')
        hint_text = f"\n\n\U0001f4a1 *Hint: Artist starts with **{snippet['artist'][0]}***" if hint_active else ''

        embed = discord.Embed(
            title="\U0001f3a4 Lyrics Guess!",
            description=(
                f"What song is this from?\n\n"
                f"```{snippet['lyrics']}```"
                f"Type the **song title** or **artist name** to win!\n"
                f"You have **30 seconds**."
                f"{hint_text}"
            ),
            color=config.COLORS['info'],
        )
        embed.set_footer(text="Type in chat — partial matches count!")
        await ctx.send(embed=embed)

        def check(m):
            if m.channel != ctx.channel or m.author.bot:
                return False
            content = m.content.lower()
            words = set(content.split())
            return bool(title_words.intersection(words)) or bool(artist_words.intersection(words))

        try:
            winner = await self.bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"**{snippet['title']}** by **{snippet['artist']}**",
                color=config.COLORS['error'],
            ))
            return

        coins = 120
        gems = 8 if _tier_gte(tier, 'Vibe') else 0
        if await db.has_active_item(ctx.author.id, 'trivia_surge'):
            coins = int(coins * 2)
            gems = int(gems * 2)

        await db.ensure_user(winner.author.id, winner.author.name)
        await db.earn_currency(winner.author.id, 'coins', coins)
        if gems:
            await db.earn_currency(winner.author.id, 'gems', gems)

        reward_str = f"+**{coins}** \U0001fa99"
        if gems:
            reward_str += f"  +**{gems}** \U0001f48e"

        await ctx.send(embed=discord.Embed(
            title=f"\u2705 {winner.author.display_name} got it!",
            description=f"**{snippet['title']}** by **{snippet['artist']}**\n{reward_str}",
            color=config.COLORS['success'],
        ))

    # ── namethetune ───────────────────────────────────────────────────────────

    @commands.hybrid_command(name='namethetune', aliases=['ntt', 'namethatsong'], description='Name the song from lyrics — first wins! (Vibe+)')
    @commands.cooldown(1, 25, commands.BucketType.channel)
    async def namethetune(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        snippet = random.choice(md.LYRIC_SNIPPETS)
        title_words = set(snippet['title'].lower().split())

        # Show genre as a hint
        embed = discord.Embed(
            title="\U0001f3b5 Name That Tune!",
            description=(
                f"Genre hint: **{snippet['genre'].capitalize()}**\n\n"
                f"```{snippet['lyrics']}```"
                f"**First** to type the song title wins!\n"
                f"You have **25 seconds**."
            ),
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Channel race — be the first!")
        await ctx.send(embed=embed)

        import time
        start = time.monotonic()

        def check(m):
            if m.channel != ctx.channel or m.author.bot:
                return False
            words = set(m.content.lower().split())
            return bool(title_words.intersection(words))

        try:
            winner = await self.bot.wait_for('message', check=check, timeout=25)
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="Time's up!",
                description=f"It was **{snippet['title']}** by **{snippet['artist']}**",
                color=config.COLORS['error'],
            ))
            return

        elapsed = time.monotonic() - start
        coins = 150
        gems = 10
        # Speed bonus
        if elapsed < 5:
            coins = 250
            gems = 15

        if await db.has_active_item(ctx.author.id, 'trivia_surge'):
            coins = int(coins * 2)
            gems = int(gems * 2)

        await db.ensure_user(winner.author.id, winner.author.name)
        await db.earn_currency(winner.author.id, 'coins', coins)
        await db.earn_currency(winner.author.id, 'gems', gems)

        speed_note = " *(speed bonus!)*" if elapsed < 5 else ""
        await ctx.send(embed=discord.Embed(
            title=f"\U0001f3c6 {winner.author.display_name} named that tune!",
            description=(
                f"**{snippet['title']}** by **{snippet['artist']}**\n"
                f"Time: **{elapsed:.2f}s**\n"
                f"+**{coins}** \U0001fa99  +**{gems}** \U0001f48e{speed_note}"
            ),
            color=config.COLORS['success'],
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicTrivia(bot))
