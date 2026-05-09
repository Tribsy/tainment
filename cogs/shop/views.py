"""
cogs/shop/views.py — shop UI Views (currency-section selector).

Phase 3b.2: extracted from cogs/shop/__init__.py. Two small View classes that
power the 3-section shop dropdown.
"""
import discord
from discord.ui import Select, View

import config

from .constants import SECTION_EMOJIS
from .service import _shop_embed


class ShopCurrencySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Coin Shop', value='coins', emoji='\U0001fa99', description='Buy with coins'),
            discord.SelectOption(label='Gem Shop', value='gems', emoji='\U0001f48e', description='Buy with gems'),
            discord.SelectOption(label='Token Shop', value='tokens', emoji='\U0001f3ab', description='Buy with tokens'),
        ]
        super().__init__(placeholder='Choose a shop section...', options=options)

    async def callback(self, interaction: discord.Interaction):
        currency = self.values[0]
        embed = _shop_embed(currency)
        await interaction.response.edit_message(embed=embed, view=self.view)


class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ShopCurrencySelect())
