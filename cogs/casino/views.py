"""
cogs/casino/views.py — Discord UI Views for casino games.

Phase 3a.2 step 1: extracted verbatim from cogs/casino/__init__.py. View
classes are moved as-is; their dependencies on game-logic helpers
(_settle, _calc_roulette, _hand_value, etc.) and config aliases (C, CE) are
imported from the package namespace below. When service.py is extracted in
step 2, those imports redirect to the new module.

The `from cogs.casino import ...` line below relies on Python's partial-package-
init behavior: when this module is imported by __init__.py, the names it
references must already be defined above the `from .views import ...` line in
__init__.py. That ordering invariant is documented in __init__.py.
"""
import logging

import discord
from discord.ui import Button, Modal, TextInput, View

import config
import database as db
import casino_db as cdb

logger = logging.getLogger("tainment.casino.views")

# Cross-package imports — module-level config aliases AND game-logic helpers.
# All of these are defined in __init__.py above the `from .views import ...` line,
# so this import resolves at module-load time despite the apparent circularity.
from cogs.casino import (
    # Config aliases
    C,                      # = config.CASINO (game tuning, payouts, limits)
    CE,                     # = config.CURRENCY_EMOJI
    # Asset paths
    ROULETTE_TABLE_PATH,
    # Game-logic helpers
    _embed,
    _err,
    _settle,
    _hand_value,
    _hand_display,
    _cname,
    _build_roulette_embed,
    _calc_roulette,
)




class BetModal(discord.ui.Modal, title="Place a Number Bet"):
    number = discord.ui.TextInput(
        label="Number (0 – 36)",
        placeholder="e.g. 17",
        min_length=1,
        max_length=2,
        required=True,
    )
    amount = discord.ui.TextInput(
        label="Bet amount",
        placeholder=f"Min {C['min_bet']}",
        min_length=1,
        max_length=8,
        required=True,
    )

    def __init__(self, view: "RouletteView"):
        super().__init__()
        self.roulette_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num = int(self.number.value)
            amt = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid integers.", ephemeral=True
            )
            return
        if not (0 <= num <= 36):
            await interaction.response.send_message(
                "Number must be 0–36.", ephemeral=True
            )
            return
        bal = await db.get_currency(interaction.user.id, "coins")
        total_bet = sum(self.roulette_view.bets.values()) + amt
        if total_bet > bal:
            await interaction.response.send_message(
                f"Insufficient balance. You have **{bal:,}** {CE}.", ephemeral=True
            )
            return
        self.roulette_view.bets[f"#{num}"] = amt
        await interaction.response.defer()
        await self.roulette_view.refresh(interaction)



class RouletteView(discord.ui.View):
    def __init__(self, user: discord.Member, base_bet: int):
        super().__init__(timeout=30)
        self.user      = user
        self.base_bet  = base_bet
        self.bets: dict[str, int] = {}   # bet_type → amount
        self.message   = None
        self._spin_task = None
        self._seconds_left = 30
        self._spinning = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )
            return False
        return True

    def _build_embed(self) -> discord.Embed:
        total = sum(self.bets.values())
        e = _build_roulette_embed(self.bets, self.base_bet)
        e.set_image(url="attachment://roulette_table.png")
        mins = self._seconds_left // 60
        secs = self._seconds_left % 60
        e.add_field(name="⏱️ Time left", value=f"`{mins}:{secs:02d}`", inline=False)
        return e

    async def _countdown_loop(self):
        while self._seconds_left > 0 and not self._spinning:
            await asyncio.sleep(1)
            if self._spinning:
                return
            self._seconds_left -= 1
            if self.message:
                e = self._build_embed()
                try:
                    await self.message.edit(embed=e, attachments=[
                        discord.File(ROULETTE_TABLE_PATH, filename="roulette_table.png")
                    ])
                except Exception:
                    pass

    async def start_countdown(self):
        self._spin_task = asyncio.create_task(self._countdown_loop())

    async def refresh(self, interaction: discord.Interaction):
        e = self._build_embed()
        try:
            await interaction.message.edit(embed=e, view=self, attachments=[
                discord.File(ROULETTE_TABLE_PATH, filename="roulette_table.png")
            ])
        except Exception:
            pass

    async def _add_bet(self, interaction: discord.Interaction, key: str, amount: int):
        bal = await db.get_currency(self.user.id, "coins")
        total = sum(self.bets.values()) + amount
        if total > bal:
            await interaction.response.send_message(
                f"Not enough coins! Balance: **{bal:,}** {CE}", ephemeral=True
            )
            return
        self.bets[key] = self.bets.get(key, 0) + amount
        await interaction.response.defer()
        await self.refresh(interaction)

    @discord.ui.button(label="🔴 Red",   style=discord.ButtonStyle.danger,    row=0)
    async def bet_red(self, i, b):   await self._add_bet(i, "red",   self.base_bet)

    @discord.ui.button(label="⚫ Black", style=discord.ButtonStyle.secondary,  row=0)
    async def bet_black(self, i, b): await self._add_bet(i, "black", self.base_bet)

    @discord.ui.button(label="🟢 Green (0)", style=discord.ButtonStyle.success, row=0)
    async def bet_green(self, i, b): await self._add_bet(i, "green", self.base_bet)

    @discord.ui.button(label="ODD",  style=discord.ButtonStyle.primary, row=1)
    async def bet_odd(self, i, b):   await self._add_bet(i, "odd",   self.base_bet)

    @discord.ui.button(label="EVEN", style=discord.ButtonStyle.primary, row=1)
    async def bet_even(self, i, b):  await self._add_bet(i, "even",  self.base_bet)

    @discord.ui.button(label="LOW 1–18",  style=discord.ButtonStyle.primary, row=1)
    async def bet_low(self, i, b):   await self._add_bet(i, "low",   self.base_bet)

    @discord.ui.button(label="HIGH 19–36", style=discord.ButtonStyle.primary, row=1)
    async def bet_high(self, i, b):  await self._add_bet(i, "high",  self.base_bet)

    @discord.ui.button(label="🎯 Number", style=discord.ButtonStyle.secondary, row=2)
    async def bet_number(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(BetModal(self))

    @discord.ui.button(label="🗑 Clear bets", style=discord.ButtonStyle.secondary, row=2)
    async def clear_bets(self, interaction: discord.Interaction, button):
        self.bets.clear()
        await interaction.response.defer()
        await self.refresh(interaction)

    @discord.ui.button(label="🎲 Spin Now", style=discord.ButtonStyle.success, row=2)
    async def spin_now(self, interaction: discord.Interaction, button):
        if self._spin_task:
            self._spin_task.cancel()
        self._spinning = True
        self.stop()
        await self._resolve(interaction)

    async def on_timeout(self):
        if self._spin_task:
            self._spin_task.cancel()
        if self.bets:
            await self._resolve_after_timeout()
        else:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(
                    embed=_embed("Roulette", "⏰ Time ran out — no bets placed."),
                    view=self,
                    attachments=[],
                )
            except Exception:
                pass

    async def _resolve_after_timeout(self):
        self._spinning = True
        for item in self.children:
            item.disabled = True
        spin = random.randint(0, 36)
        result_embed = await _calc_roulette(self.user.id, self.bets, spin)
        try:
            await self.message.edit(embed=result_embed, view=self, attachments=[])
        except Exception:
            pass

    async def _resolve(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        if not self.bets:
            await interaction.response.edit_message(
                embed=_err("No bets placed!"), view=self, attachments=[]
            )
            return
        spin = random.randint(0, 36)
        result_embed = await _calc_roulette(self.user.id, self.bets, spin)
        await interaction.response.edit_message(embed=result_embed, view=self, attachments=[])



class BlackjackView(discord.ui.View):
    def __init__(self, user: discord.Member, bet: int, deck, player_hand, dealer_hand):
        super().__init__(timeout=60)
        self.user        = user
        self.bet         = bet
        self.deck        = deck
        self.player      = player_hand
        self.dealer      = dealer_hand
        self.doubled     = False
        self.message     = None

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id:
            await i.response.send_message("Not your game!", ephemeral=True)
            return False
        return True

    def _build_embed(self, reveal_dealer: bool = False) -> discord.Embed:
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)
        desc = (
            f"**Dealer:** {_hand_display(self.dealer, hidden=not reveal_dealer)}"
            + (f"  *(= {dv})*" if reveal_dealer else "")
            + f"\n**You:** {_hand_display(self.player)}  *(= {pv})*"
        )
        color = config.COLORS.get("primary")
        if pv > 21:  color = config.COLORS.get("error")
        return _embed("🃏 Blackjack", desc, color)

    async def _finish(self, interaction, net: int, reason: str):
        self.stop()
        for item in self.children:
            item.disabled = True
        bal   = await _settle(self.user.id, self.bet, net, "blackjack")
        pv    = _hand_value(self.player)
        dv    = _hand_value(self.dealer)
        color = (config.COLORS.get("success") if net > 0
                 else config.COLORS.get("error") if net < 0
                 else config.COLORS.get("warning"))
        e = _embed(
            f"🃏 Blackjack  –  {reason}",
            (
                f"**Dealer:** {_hand_display(self.dealer)}  *(= {dv})*\n"
                f"**You:**    {_hand_display(self.player)}  *(= {pv})*"
            ),
            color,
        )
        e.add_field(name="Bet",     value=f"**{self.bet:,}** {CE}", inline=True)
        if net > 0:
            e.add_field(name="Payout",  value=f"**{self.bet + net:,}** {CE}", inline=True)
        elif net < 0:
            e.add_field(name="Lost",    value=f"**{self.bet:,}** {CE}", inline=True)
        else:
            e.add_field(name="Result",  value="Push — bet returned", inline=True)
        e.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
        await interaction.response.edit_message(embed=e, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=_embed("🃏 Blackjack", "⏰ Game timed out."),
                view=self,
            )
        except Exception:
            pass

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="👆")
    async def hit(self, interaction: discord.Interaction, button):
        self.player.append(self.deck.pop())
        pv = _hand_value(self.player)
        if pv > 21:
            await self._finish(interaction, -self.bet, "💥 Bust!")
        elif pv == 21:
            await self._stand_logic(interaction)
        else:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button):
        await self._stand_logic(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="💰")
    async def double(self, interaction: discord.Interaction, button):
        bal = await db.get_currency(self.user.id, "coins")
        if bal < self.bet:
            await interaction.response.send_message(
                "Not enough coins to double!", ephemeral=True
            )
            return
        self.bet    *= 2
        self.doubled = True
        self.player.append(self.deck.pop())
        pv = _hand_value(self.player)
        if pv > 21:
            await self._finish(interaction, -self.bet, "💥 Bust (doubled)!")
        else:
            await self._stand_logic(interaction)

    async def _stand_logic(self, interaction):
        # Dealer draws to 17
        while _hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)
        bj_payout = C["blackjack_payout"]

        if dv > 21 or pv > dv:
            # Player wins
            is_bj = len(self.player) == 2 and pv == 21
            mult   = bj_payout if is_bj else 1.0
            net    = int(self.bet * mult)
            reason = "🃏 Blackjack!" if is_bj else "🏆 You win!"
            await self._finish(interaction, net, reason)
        elif pv == dv:
            await self._finish(interaction, 0, "🤝 Push!")
        else:
            await self._finish(interaction, -self.bet, "😔 Dealer wins")



class HiLoView(discord.ui.View):
    def __init__(self, user: discord.Member, bet: int, deck: list, current: int):
        super().__init__(timeout=30)
        self.user     = user
        self.bet      = bet
        self.deck     = deck
        self.current  = current
        self.streak   = 0
        self.total_net = 0
        self.message  = None

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id:
            await i.response.send_message("Not your game!", ephemeral=True)
            return False
        return True

    def _embed(self) -> discord.Embed:
        potential = self.bet * (self.streak + 1)
        e = _embed(
            "🃏 Higher or Lower",
            (
                f"Current card: **{_cname(self.current)}**\n"
                f"Streak: {'🔥 ' * min(self.streak, 5)}`{self.streak}`\n"
                f"Potential payout: **{potential:,}** {CE}"
            ),
        )
        return e

    async def _process(self, interaction, choice: str):
        next_card = self.deck.pop()
        correct   = (choice == "higher" and next_card >= self.current) or \
                    (choice == "lower"  and next_card <= self.current)

        if correct:
            self.streak    += 1
            self.total_net += self.bet
            self.current    = next_card
            if self.streak >= C["highlow_max_streak"]:
                await self._finish(interaction, f"🏆 Max streak ({self.streak})! Auto cash-out.")
                return
            if not self.deck:
                await self._finish(interaction, "🃏 Deck exhausted — cashed out!")
                return
            await interaction.response.edit_message(embed=self._embed(), view=self)
        else:
            self.stop()
            for item in self.children:
                item.disabled = True
            net = -self.bet
            bal = await _settle(self.user.id, self.bet, net, "highlow")
            e   = _embed(
                "🃏 Higher or Lower  –  ❌ Wrong!",
                f"Next card was **{_cname(next_card)}**. Lost **{self.bet:,}** {CE}.",
                config.COLORS.get("error"),
            )
            e.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
            await interaction.response.edit_message(embed=e, view=self)

    async def _finish(self, interaction, reason: str):
        self.stop()
        for item in self.children:
            item.disabled = True
        bal = await _settle(self.user.id, self.bet, self.total_net, "highlow")
        payout = self.bet + self.total_net
        e   = _embed(
            f"🃏 Higher or Lower  –  {reason}",
            f"Streak: **{self.streak}**  •  Payout: **+{payout:,}** {CE}",
            config.COLORS.get("success"),
        )
        e.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
        await interaction.response.edit_message(embed=e, view=self)

    async def on_timeout(self):
        self.stop()
        for item in self.children:
            item.disabled = True
        if self.total_net > 0:
            bal = await _settle(self.user.id, self.bet, self.total_net, "highlow")
        else:
            bal = await db.get_currency(self.user.id, "coins")
        try:
            e = _embed("🃏 Higher or Lower  –  ⏰ Timed out")
            if self.total_net > 0:
                payout = self.bet + self.total_net
                e.description = f"Cashed out: **+{payout:,}** {CE}"
                e.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
            await self.message.edit(embed=e, view=self)
        except Exception:
            pass

    @discord.ui.button(label="Higher ⬆️", style=discord.ButtonStyle.success)
    async def higher(self, i, b): await self._process(i, "higher")

    @discord.ui.button(label="Lower ⬇️",  style=discord.ButtonStyle.danger)
    async def lower(self, i, b):  await self._process(i, "lower")

    @discord.ui.button(label="Cash Out 💰", style=discord.ButtonStyle.secondary)
    async def cashout(self, i, b):
        if self.total_net > 0:
            await self._finish(i, "💰 Cashed out!")
        else:
            self.stop()
            for item in self.children:
                item.disabled = True
            await i.response.edit_message(
                embed=_embed("🃏 Higher or Lower  –  No winnings to cash out."),
                view=self,
            )


class DuelAcceptView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent   = opponent
        self.bet        = bet
        self.accepted   = None
        self.message    = None

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.opponent.id:
            await i.response.send_message("This duel isn't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        self.accepted = True
        self.stop()
        await self._resolve(interaction)

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        self.accepted = False
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=_embed("Duel", f"{self.opponent.mention} declined the duel."),
            view=self,
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=_embed("Duel", "⏰ Duel expired — no response."),
                view=self,
            )
        except Exception:
            pass

    async def _resolve(self, interaction):
        for item in self.children:
            item.disabled = True

        # Flip
        winner = random.choice([self.challenger, self.opponent])
        loser  = self.opponent if winner == self.challenger else self.challenger

        await db.update_balance(winner.id,  self.bet)
        await db.update_balance(loser.id,  -self.bet)
        await cdb.record_game(winner.id, "duel",  self.bet,  self.bet,
                              await db.get_currency(winner.id, "coins"))
        await cdb.record_game(loser.id,  "duel",  self.bet, -self.bet,
                              await db.get_currency(loser.id, "coins"))

        # Flip animation
        e_flip = _embed("🪙 Coin Flip!", "🌀 The coin is in the air…", config.COLORS.get("primary"))
        await interaction.response.edit_message(embed=e_flip, view=self)
        await asyncio.sleep(1.5)

        e_result = _embed(
            "🪙 Coin Flip  –  Result!",
            f"🏆 **{winner.mention}** wins **{self.bet:,}** {CE} from {loser.mention}!",
            config.COLORS.get("success"),
        )
        await interaction.message.edit(embed=e_result, view=self)
