"""
cogs/entertainment/views.py — Discord UI Views for entertainment games.

Phase 3g: extracted verbatim from cogs/entertainment/__init__.py. Holds
RPSView (Rock-Paper-Scissors buttons) and TriviaView (trivia choice buttons).
"""
import discord
from discord.ui import Button, View
import random
import config


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
