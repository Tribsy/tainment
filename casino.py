"""
casino.py  –  Self-contained Casino cog for Tainment Bot.

Games:
  /slots       –  Slot machine with sequential reel reveal
  /wheel       –  Wheel of Fortune with 3-phase animated spin
  /roulette    –  Interactive roulette with bet buttons + 30s timer
  /blackjack   –  Hit / Stand / Double Down
  /highlow     –  Higher or Lower card streak
  /duel        –  Coin-flip PvP duel
  /bank        –  Casino bank status

Admin group (/casino):
  /casino bank         –  Bank stats embed
  /casino ban          –  Ban a user from casino
  /casino unban        –  Unban a user
  /casino setlimit     –  Set a user's personal max-bet cap
  /casino topwinners   –  Leaderboard
  /casino flush        –  Pay bank balance to an admin
"""

import os
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import config
import database as db
import casino_db as cdb
import logging

logger = logging.getLogger("tainment.casino")

# ─── Asset paths ─────────────────────────────────────────────────────────────
_ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
ROULETTE_TABLE_PATH = os.path.join(_ASSET_DIR, "roulette_table.png")
WHEEL_SPIN_PATH = os.path.join(_ASSET_DIR, "wheel_spin.gif")


# ─── Prefix command adapter ─────────────────────────────────────────────────
class _PrefixResponse:
    """Makes ctx.send/edit behave like interaction.response for prefix commands."""
    def __init__(self, ctx):
        self._ctx = ctx
        self._msg = None
        self._deferred = False

    async def send_message(self, content=None, **kwargs):
        kwargs.pop("ephemeral", None)
        if self._deferred:
            self._msg = await self._ctx.send(content, **kwargs)
            self._deferred = False
        else:
            self._msg = await self._ctx.send(content, **kwargs)

    async def edit_message(self, content=None, **kwargs):
        if self._msg:
            return await self._msg.edit(content, **kwargs)
        logger.warning("_PrefixResponse.edit_message called before send_message")

    async def defer(self, **kwargs):
        kwargs.pop("ephemeral", None)
        if not self._deferred:
            self._deferred = True
            await self._ctx.typing()

    @property
    def msg(self):
        return self._msg


class _PrefixInteraction:
    """Wraps a prefix Context to look like a discord.Interaction."""
    def __init__(self, ctx):
        self._ctx = ctx
        self.user = ctx.author
        self.message = ctx.message
        self._response = _PrefixResponse(ctx)
        self.is_prefix = True
        logger.debug(f"_PrefixInteraction created for user {self.user.id} via prefix command '{ctx.command.name}'")

    @property
    def response(self):
        return self._response

    async def original_response(self):
        msg = self._response.msg
        if msg is None:
            logger.warning("original_response called before any message was sent")
        return msg

    @property
    def channel(self):
        return self._ctx.channel

    @property
    def guild(self):
        return self._ctx.guild

# ─────────────────────────────────────────────────────────────────────────────
# Helper: embed factory
# ─────────────────────────────────────────────────────────────────────────────

C = config.CASINO
CE = config.CURRENCY_EMOJI


def _embed(title: str, desc: str = "", color: int = None) -> discord.Embed:
    e = discord.Embed(
        title=f"{config.CASINO_NAME} │ {title}",
        description=desc,
        color=color or config.COLORS.get("gold", 0xf1c40f),
    )
    e.set_footer(text=config.CASINO_FOOTER)
    return e


def _err(msg: str) -> discord.Embed:
    return _embed("Error", msg, config.COLORS.get("error", 0xe74c3c))


async def _validate(interaction: discord.Interaction, bet: int) -> tuple[bool, int]:
    """
    Check ban, balance, and bet limits.
    Returns (ok, current_balance).  Sends an error reply if not ok.
    """
    uid = interaction.user.id
    if await cdb.is_casino_banned(uid):
        await interaction.response.send_message(
            embed=_err("You are banned from the casino."), ephemeral=True
        )
        return False, 0

    bal = await db.get_currency(uid, "coins")
    min_b = C["min_bet"]
    max_b = await cdb.get_user_max_bet(uid)

    if bet < min_b:
        await interaction.response.send_message(
            embed=_err(f"Minimum bet is **{min_b:,}** {CE}."), ephemeral=True
        )
        return False, bal

    if bet > max_b:
        await interaction.response.send_message(
            embed=_err(f"Your max bet is **{max_b:,}** {CE}."), ephemeral=True
        )
        return False, bal

    if bet > bal:
        await interaction.response.send_message(
            embed=_err(f"Not enough coins. Balance: **{bal:,}** {CE}."), ephemeral=True
        )
        return False, bal

    return True, bal


async def _settle(user_id: int, bet: int, net: int, game: str):
    """
    Apply net result to user balance, route house edge to bank, record stats.
    net > 0  → player won `net` coins
    net < 0  → player lost `abs(net)` coins
    net = 0  → push / refund
    """
    await db.update_balance(user_id, net)
    bal_after = await db.get_currency(user_id, "coins")

    # House edge: only on wins
    if net > 0:
        edge = int(net * C["house_edge"])
        await db.update_balance(user_id, -edge)
        await cdb.add_to_bank(edge)
        bal_after -= edge

    await cdb.record_game(user_id, game, bet, net, bal_after)
    return bal_after


# ─────────────────────────────────────────────────────────────────────────────
# ── SLOTS ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def _build_reel() -> list[str]:
    syms = C["slots_symbols"]  # key → (emoji, weight)
    keys   = list(syms.keys())
    weights = [syms[k][1] for k in keys]
    return random.choices(keys, weights=weights, k=3)


def _slots_result(reels: list[str]) -> tuple[float, str]:
    """Return (multiplier, label)."""
    syms = C["slots_symbols"]
    emojis = [syms[r][0] for r in reels]

    if reels[0] == reels[1] == reels[2]:
        if reels[0] == "seven":
            return C["slots_jackpot_mult"], "🏆 JACKPOT!"
        return C["slots_three_mult"], "🎰 Three of a kind!"
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return C["slots_two_mult"], "✨ Pair bonus!"
    return 0.0, "❌ No match"


def _reel_display(reels: list[str], revealed: int = 3) -> str:
    """Render slot display. Unrevealed reels show 🎰."""
    syms = C["slots_symbols"]
    cells = []
    for i, r in enumerate(reels):
        if i < revealed:
            cells.append(syms[r][0])
        else:
            cells.append("🎰")
    return f"╔══════════════╗\n║  {cells[0]}  {cells[1]}  {cells[2]}  ║\n╚══════════════╝"


async def _run_slots(interaction: discord.Interaction, bet: int):
    uid = interaction.user.id
    reels = _build_reel()
    mult, label = _slots_result(reels)

    # Phase 1 – spinning
    e = _embed("🎰 Slot Machine", _reel_display(reels, 0), config.COLORS.get("primary"))
    e.add_field(name="Bet", value=f"**{bet:,}** {CE}", inline=True)
    e.add_field(name="Status", value="🎲 Spinning…", inline=True)
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    await asyncio.sleep(1.2)

    # Phase 2 – reveal reel 1
    e2 = _embed("🎰 Slot Machine", _reel_display(reels, 1), config.COLORS.get("primary"))
    e2.add_field(name="Bet", value=f"**{bet:,}** {CE}", inline=True)
    e2.add_field(name="Status", value="🔮 Revealing… 1/3", inline=True)
    await msg.edit(embed=e2)
    await asyncio.sleep(0.9)

    # Phase 3 – reveal reel 2
    e3 = _embed("🎰 Slot Machine", _reel_display(reels, 2), config.COLORS.get("primary"))
    e3.add_field(name="Bet", value=f"**{bet:,}** {CE}", inline=True)
    e3.add_field(name="Status", value="🔮 Revealing… 2/3", inline=True)
    await msg.edit(embed=e3)
    await asyncio.sleep(0.9)

    # Final result
    if mult > 0:
        payout = int(bet * mult)
        net    = payout - bet
        bal    = await _settle(uid, bet, net, "slots")
        is_jackpot = reels[0] == reels[1] == reels[2] == "seven"
        if is_jackpot:
            await cdb.increment_jackpots(uid)
        color  = config.COLORS.get("gold") if is_jackpot else config.COLORS.get("success")
        ef = _embed(f"🎰 Slot Machine  –  {label}", _reel_display(reels, 3), color)
        ef.add_field(name="Bet",      value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Payout",   value=f"**{payout:,}** {CE}", inline=True)
        ef.add_field(name="Multiplier", value=f"**{mult}×**", inline=True)
        ef.add_field(name="Balance",  value=f"**{bal:,}** {CE}", inline=True)
    else:
        net = -bet
        bal = await _settle(uid, bet, net, "slots")
        ef = _embed("🎰 Slot Machine  –  ❌ No match", _reel_display(reels, 3), config.COLORS.get("error"))
        ef.add_field(name="Bet",  value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Lost", value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)

    await msg.edit(embed=ef)


# ─────────────────────────────────────────────────────────────────────────────
# ── WHEEL OF FORTUNE ──────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

SPIN_FRAMES = ["🌀", "🌪️", "💫", "⚡", "🌀"]


def _spin_wheel() -> dict:
    segs    = C["wheel_segments"]
    weights = [s["weight"] for s in segs]
    return random.choices(segs, weights=weights, k=1)[0]


async def _run_wheel(interaction: discord.Interaction, bet: int):
    uid    = interaction.user.id
    result = _spin_wheel()

    # Phase 1 – spinning with GIF animation
    segments_preview = "  ".join(f"{s['emoji']}{s['label']}" for s in C["wheel_segments"])
    e1 = _embed(
        "🎡 Wheel of Fortune",
        f"🌪️ **THE WHEEL IS SPINNING!**\n\n*Watch where it stops…*",
        config.COLORS.get("primary"),
    )
    e1.set_image(url="attachment://wheel_spin.gif")
    e1.add_field(name="Bet",    value=f"**{bet:,}** {CE}", inline=True)
    e1.add_field(name="Status", value="🌀 Spinning!", inline=True)
    await interaction.response.send_message(
        embed=e1,
        file=discord.File(WHEEL_SPIN_PATH, filename="wheel_spin.gif"),
    )
    msg = await interaction.original_response()

    # Phase 2 – slowing down (cycle through frames)
    for frame in SPIN_FRAMES:
        e2 = _embed(
            "🎡 Wheel of Fortune",
            f"{frame} **Slowing down…**\n\n{segments_preview}",
            config.COLORS.get("warning"),
        )
        e2.set_image(url="attachment://wheel_spin.gif")
        e2.add_field(name="Bet",    value=f"**{bet:,}** {CE}", inline=True)
        e2.add_field(name="Status", value=f"{frame} Slowing…", inline=True)
        await msg.edit(
            embed=e2,
            attachments=[discord.File(WHEEL_SPIN_PATH, filename="wheel_spin.gif")],
        )
        await asyncio.sleep(0.4)

    # Final result
    mult  = result["multiplier"]
    emoji = result["emoji"]
    label = result["label"]

    if mult == 0:
        net   = -bet
        bal   = await _settle(uid, bet, net, "wheel")
        color = config.COLORS.get("error")
        title = f"🎡 Wheel of Fortune  –  {emoji} BUST!"
        desc  = (
            f"The arrow landed on **{emoji} {label}**\n\n"
            f"Better luck next time!"
        )
        ef = _embed(title, desc, color)
        ef.add_field(name="Result",  value=f"{emoji} BUST", inline=True)
        ef.add_field(name="Bet",     value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Lost",    value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
    else:
        payout = int(bet * mult)
        net    = payout - bet
        bal    = await _settle(uid, bet, net, "wheel")
        color  = config.COLORS.get("gold") if mult >= 10 else config.COLORS.get("success")
        title  = f"🎡 Wheel of Fortune  –  {emoji} {label}!"
        desc   = f"The arrow landed on **{emoji} {label}** — **{mult}×** multiplier!"
        ef = _embed(title, desc, color)
        ef.add_field(name="Bet",        value=f"**{bet:,}** {CE}", inline=True)
        ef.add_field(name="Payout",     value=f"**{payout:,}** {CE}", inline=True)
        ef.add_field(name="Multiplier", value=f"**{mult}×**", inline=True)
        ef.add_field(name="Balance",    value=f"**{bal:,}** {CE}", inline=True)

    await msg.edit(embed=ef)


# ─────────────────────────────────────────────────────────────────────────────
# ── ROULETTE ──────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

RED_NUMS = config.CASINO["roulette_red"]


def _num_color(n: int) -> str:
    if n == 0:  return "green"
    return "red" if n in RED_NUMS else "black"


def _color_emoji(c: str) -> str:
    return {"red": "🔴", "black": "⚫", "green": "🟢"}[c]


def _roulette_board(bets: dict[str, int]) -> str:
    """Render a compact roulette board with active bets marked."""
    lines = []
    for row_start in range(1, 37, 3):
        row = ""
        for n in [row_start, row_start + 1, row_start + 2]:
            ce = "🔴" if n in RED_NUMS else "⚫"
            row += f"{ce}`{n:2}` "
        lines.append(row)
    # Summary of placed bets
    if bets:
        bet_str = "  ".join(f"**{k}** {v:,}{CE}" for k, v in bets.items())
        lines.append(f"\n🎯 Bets: {bet_str}")
    return "\n".join(lines)


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


def _build_roulette_embed(bets: dict, base_bet: int) -> discord.Embed:
    total = sum(bets.values())
    e = _embed(
        "🎰 Enhanced Roulette",
        (
            "**Place your bets using the buttons below!**\n"
            f"Each click bets **{base_bet:,}** {CE} on that outcome.\n"
            f"⏰ Auto-spins after 30 seconds.\n\n"
            "**Payouts:** Single # 35:1  •  Red/Black 1:1  •  Odd/Even 1:1  •  High/Low 1:1"
        ),
    )
    if bets:
        e.add_field(
            name="Current bets",
            value="\n".join(f"**{k}**: {v:,} {CE}" for k, v in bets.items()),
            inline=True,
        )
        e.add_field(name="Total at risk", value=f"**{total:,}** {CE}", inline=True)
    return e


async def _calc_roulette(user_id: int, bets: dict[str, int], spin: int) -> discord.Embed:
    """Evaluate all bets for a given spin, settle, return result embed."""
    spin_color = _num_color(spin)
    ce         = _color_emoji(spin_color)
    payouts    = C["roulette_payouts"]

    total_bet  = sum(bets.values())
    total_net  = 0

    breakdown  = []
    for bet_type, amount in bets.items():
        won = False
        mult = 0
        if bet_type == "red"   and spin_color == "red":    won = True; mult = payouts["red"]
        elif bet_type == "black" and spin_color == "black": won = True; mult = payouts["black"]
        elif bet_type == "green" and spin == 0:             won = True; mult = 35
        elif bet_type == "odd"  and spin != 0 and spin % 2 == 1: won = True; mult = payouts["odd"]
        elif bet_type == "even" and spin != 0 and spin % 2 == 0: won = True; mult = payouts["even"]
        elif bet_type == "low"  and 1 <= spin <= 18:        won = True; mult = payouts["low"]
        elif bet_type == "high" and 19 <= spin <= 36:       won = True; mult = payouts["high"]
        elif bet_type.startswith("#") and int(bet_type[1:]) == spin:
            won = True; mult = payouts["number"]

        if won:
            net = amount * mult
            total_net += net
            breakdown.append(f"✅ **{bet_type}** +{net:,} {CE} ({mult+1}×)")
        else:
            total_net -= amount
            breakdown.append(f"❌ **{bet_type}** -{amount:,} {CE}")

    bal = await _settle(user_id, total_bet, total_net, "roulette")

    color = config.COLORS.get("success") if total_net > 0 else config.COLORS.get("error")
    e = _embed(
        f"🎰 Roulette  –  {ce} **{spin}** ({spin_color.upper()})",
        "\n".join(breakdown),
        color,
    )
    if total_net > 0:
        total_payout = total_bet + total_net
        e.add_field(name="Payout",  value=f"**{total_payout:,}** {CE}", inline=True)
    elif total_net < 0:
        e.add_field(name="Lost",    value=f"**{abs(total_net):,}** {CE}", inline=True)
    else:
        e.add_field(name="Result",  value="Push — bet returned", inline=True)
    e.add_field(name="Balance", value=f"**{bal:,}** {CE}",             inline=True)
    return e


# ─────────────────────────────────────────────────────────────────────────────
# ── BLACKJACK ────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

SUITS  = ["♠", "♥", "♦", "♣"]
RANKS  = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def _new_deck() -> list[tuple[str, str]]:
    d = [(r, s) for r in RANKS for s in SUITS] * 2
    random.shuffle(d)
    return d


def _card_str(card: tuple[str, str]) -> str:
    return f"{card[0]}{card[1]}"


def _hand_value(hand: list[tuple[str, str]]) -> int:
    total = 0
    aces  = 0
    for rank, _ in hand:
        if rank in ("J", "Q", "K"):
            total += 10
        elif rank == "A":
            total += 11
            aces  += 1
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total


def _hand_display(hand: list, hidden: bool = False) -> str:
    if hidden and len(hand) > 1:
        return f"{_card_str(hand[0])}  🂠"
    return "  ".join(_card_str(c) for c in hand)


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


# ─────────────────────────────────────────────────────────────────────────────
# ── HIGHER OR LOWER ───────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}


def _cname(v: int) -> str:
    return CARD_NAMES.get(v, str(v))


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


# ─────────────────────────────────────────────────────────────────────────────
# ── DUEL ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# ── CASINO COG ───────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class Casino(commands.Cog, name="Casino"):
    """Interactive casino games with a live house bank and audit trail."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── slots ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="slots", description="Spin the slot machine")
    @app_commands.describe(bet="Amount to bet")
    @commands.cooldown(1, 8, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 8)
    async def slots(self, ctx: commands.Context, bet: int):
        logger.debug(f"slots invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} with bet={bet}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            await db.ensure_user(ix.user.id, ix.user.name)
            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"slots validation failed for {ix.user.id}")
                return
            await _run_slots(ix, bet)
        except Exception as e:
            logger.error(f"slots command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── wheel ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="wheel", description="Spin the Wheel of Fortune")
    @app_commands.describe(bet="Amount to bet")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 10)
    async def wheel(self, ctx: commands.Context, bet: int):
        logger.debug(f"wheel invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} with bet={bet}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            await db.ensure_user(ix.user.id, ix.user.name)
            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"wheel validation failed for {ix.user.id}")
                return
            await _run_wheel(ix, bet)
        except Exception as e:
            logger.error(f"wheel command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── roulette ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="roulette", description="Play interactive roulette")
    @app_commands.describe(bet="Base bet per click")
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 15)
    async def roulette(self, ctx: commands.Context, bet: int):
        logger.debug(f"roulette invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} with bet={bet}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            await db.ensure_user(ix.user.id, ix.user.name)
            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"roulette validation failed for {ix.user.id}")
                return
            view = RouletteView(ix.user, bet)
            e    = _build_roulette_embed({}, bet)
            e.set_image(url="attachment://roulette_table.png")
            rt_file = discord.File(ROULETTE_TABLE_PATH, filename="roulette_table.png")
            await ix.response.send_message(embed=e, file=rt_file, view=view)
            view.message = await ix.original_response()
            asyncio.create_task(view.start_countdown())
        except Exception as e:
            logger.error(f"roulette command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── blackjack ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="blackjack", description="Play blackjack against the dealer")
    @app_commands.describe(bet="Amount to bet")
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 15)
    async def blackjack(self, ctx: commands.Context, bet: int):
        logger.debug(f"blackjack invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} with bet={bet}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            await db.ensure_user(ix.user.id, ix.user.name)
            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"blackjack validation failed for {ix.user.id}")
                return
            deck   = _new_deck()
            player = [deck.pop(), deck.pop()]
            dealer = [deck.pop(), deck.pop()]
            view   = BlackjackView(ix.user, bet, deck, player, dealer)

            pv = _hand_value(player)
            if pv == 21:
                net = int(bet * C["blackjack_payout"])
                bal = await _settle(ix.user.id, bet, net, "blackjack")
                await cdb.increment_jackpots(ix.user.id)
                payout = bet + net
                e = _embed(
                    "🃏 Blackjack  –  🃏 Blackjack!",
                    (
                        f"**Dealer:** {_hand_display(dealer)}\n"
                        f"**You:** {_hand_display(player)}  *(= 21)*"
                    ),
                    config.COLORS.get("gold"),
                )
                e.add_field(name="Bet",     value=f"**{bet:,}** {CE}", inline=True)
                e.add_field(name="Payout",  value=f"**{payout:,}** {CE}", inline=True)
                e.add_field(name="Balance", value=f"**{bal:,}** {CE}", inline=True)
                await ix.response.send_message(embed=e)
                return

            await ix.response.send_message(embed=view._build_embed(), view=view)
            view.message = await ix.original_response()
        except Exception as e:
            logger.error(f"blackjack command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── highlow ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="highlow", description="Bet on the next card being higher or lower")
    @app_commands.describe(bet="Amount to bet per correct guess")
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 15)
    async def highlow(self, ctx: commands.Context, bet: int):
        logger.debug(f"highlow invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} with bet={bet}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            await db.ensure_user(ix.user.id, ix.user.name)
            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"highlow validation failed for {ix.user.id}")
                return
            deck    = list(range(1, 14)) * 4
            random.shuffle(deck)
            current = deck.pop()
            view    = HiLoView(ix.user, bet, deck, current)
            await ix.response.send_message(embed=view._embed(), view=view)
            view.message = await ix.original_response()
        except Exception as e:
            logger.error(f"highlow command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── duel ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="duel", description="Challenge someone to a coin flip duel")
    @app_commands.describe(opponent="The user to challenge", bet="Amount each player wagers")
    @commands.cooldown(1, 30, commands.BucketType.user)
    @app_commands.checks.cooldown(1, 30)
    async def duel(self, ctx: commands.Context, opponent: discord.Member, bet: int):
        logger.debug(f"duel invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id} bet={bet} target={opponent.id}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            if opponent.id == ix.user.id:
                await ix.response.send_message(
                    embed=_err("You can't duel yourself."), ephemeral=True
                )
                return
            if opponent.bot:
                await ix.response.send_message(
                    embed=_err("Bots don't carry coins."), ephemeral=True
                )
                return

            await db.ensure_user(ix.user.id, ix.user.name)
            await db.ensure_user(opponent.id, opponent.name)

            ok, _ = await _validate(ix, bet)
            if not ok:
                logger.debug(f"duel validation failed for {ix.user.id}")
                return

            opp_bal = await db.get_currency(opponent.id, "coins")
            if opp_bal < bet:
                await ix.response.send_message(
                    embed=_err(f"{opponent.mention} doesn't have **{bet:,}** {CE}."),
                    ephemeral=True,
                )
                return

            view = DuelAcceptView(ix.user, opponent, bet)
            e    = _embed(
                "🪙 Coin Flip Duel!",
                (
                    f"{ix.user.mention} challenges {opponent.mention} to a duel!\n"
                    f"**Wager:** {bet:,} {CE} each\n\n"
                    f"{opponent.mention}, do you accept?"
                ),
            )
            await ix.response.send_message(embed=e, view=view)
            view.message = await ix.original_response()
        except Exception as e:
            logger.error(f"duel command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ── bank ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="bank", description="View the casino bank status")
    async def bank(self, ctx: commands.Context):
        logger.debug(f"bank invoked via {'slash' if ctx.interaction else 'prefix'} by {ctx.author.id}")
        ix = ctx.interaction or _PrefixInteraction(ctx)
        try:
            stats = await cdb.get_bank_stats()
            e = _embed(
                f"🏦 {config.BANK_NAME}",
                "Current bank status and information",
                config.COLORS.get("primary"),
            )
            e.add_field(name="💰 Balance",        value=f"**{stats.get('balance', 0):,}** {CE}", inline=True)
            e.add_field(name="📥 Total collected", value=f"**{stats.get('total_collected', 0):,}** {CE}", inline=True)
            e.add_field(name="📤 Total paid out",  value=f"**{stats.get('total_paid_out', 0):,}** {CE}", inline=True)
            e.add_field(
                name="ℹ️ Info",
                value=(
                    f"Bank collects **{int(C['house_edge']*100)}%** house edge on wins\n"
                    f"and **{int(C['bank_fee_pct']*100)}%** transfer fees."
                ),
                inline=False,
            )
            await ix.response.send_message(embed=e)
        except Exception as e:
            logger.error(f"bank command error: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Admin group  /casino …  AND  t!casino <sub> …
    # ─────────────────────────────────────────────────────────────────────────

    casino_group = app_commands.Group(
        name="casino",
        description="Casino admin commands",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @commands.group(name="casino", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def casino_admin(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @casino_admin.command(name="bank", aliases=["stats"])
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_bank(self, ctx: commands.Context):
        stats = await cdb.get_bank_stats()
        e = _embed(
            f"🏦 {config.BANK_NAME}  –  Admin View",
            "",
            config.COLORS.get("primary"),
        )
        bal  = stats.get("balance", 0)
        col  = stats.get("total_collected", 0)
        paid = stats.get("total_paid_out", 0)
        profit = col - paid
        e.add_field(name="Current balance",   value=f"**{bal:,}** {CE}",    inline=True)
        e.add_field(name="Total collected",   value=f"**{col:,}** {CE}",    inline=True)
        e.add_field(name="Total paid out",    value=f"**{paid:,}** {CE}",   inline=True)
        e.add_field(name="Net profit",        value=f"**{profit:,}** {CE}", inline=True)
        e.add_field(name="Last updated",      value=stats.get("last_updated", "never"), inline=True)
        await ctx.send(embed=e)

    @casino_admin.command(name="ban")
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_ban(self, ctx: commands.Context, user: discord.Member, *, reason: str = None):
        await cdb.ban_user(user.id, ctx.author.id, reason)
        await ctx.send(
            embed=_embed("Casino Ban", f"🚫 {user.mention} has been banned from the casino.\nReason: {reason or 'No reason given'}"),
        )

    @casino_admin.command(name="unban")
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_unban(self, ctx: commands.Context, user: discord.Member):
        await cdb.unban_user(user.id)
        await ctx.send(
            embed=_embed("Casino Unban", f"✅ {user.mention} has been unbanned from the casino."),
        )

    @casino_admin.command(name="setlimit", aliases=["limit"])
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_setlimit(self, ctx: commands.Context, user: discord.Member, max_bet: int):
        if max_bet <= 0:
            await ctx.send(embed=_err("Limit must be positive."))
            return
        await cdb.set_bet_limit(user.id, max_bet)
        await ctx.send(
            embed=_embed("Bet Limit Set", f"✅ {user.mention}'s max bet is now **{max_bet:,}** {CE}."),
        )

    @casino_admin.command(name="topwinners", aliases=["winners", "leaderboard"])
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_topwinners(self, ctx: commands.Context):
        rows = await cdb.get_top_winners(10)
        if not rows:
            await ctx.send(embed=_embed("Top Winners", "No data yet."))
            return
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            wr    = f"{int(r['games_won']/r['games_played']*100)}%" if r['games_played'] else "—"
            lines.append(
                f"{medal} **{r['username'] or r['user_id']}**  "
                f"Won: **{r['total_won']:,}** {CE}  |  W/R: {wr}  |  🏆 {r['jackpots']}"
            )
        e = _embed("🏆 Casino Top Winners", "\n".join(lines))
        await ctx.send(embed=e)

    @casino_admin.command(name="flush", aliases=["withdraw"])
    @commands.has_permissions(manage_guild=True)
    async def casinoadmin_flush(self, ctx: commands.Context, amount: int = 0):
        bank_bal = await cdb.get_bank_balance()
        withdraw = bank_bal if amount == 0 else min(amount, bank_bal)
        if withdraw == 0:
            await ctx.send(embed=_err("Bank is empty."))
            return
        ok = await cdb.pay_from_bank(withdraw)
        if ok:
            await db.update_balance(ctx.author.id, withdraw)
            await ctx.send(
                embed=_embed(
                    "Bank Flush",
                    f"✅ Transferred **{withdraw:,}** {CE} from the bank to {ctx.author.mention}.",
                    config.COLORS.get("success"),
                ),
            )
        else:
            await ctx.send(embed=_err("Insufficient bank balance."))

    @casino_group.command(name="bank", description="[Admin] View detailed bank stats")
    async def admin_bank(self, interaction: discord.Interaction):
        stats = await cdb.get_bank_stats()
        e = _embed(
            f"🏦 {config.BANK_NAME}  –  Admin View",
            "",
            config.COLORS.get("primary"),
        )
        bal  = stats.get("balance", 0)
        col  = stats.get("total_collected", 0)
        paid = stats.get("total_paid_out", 0)
        profit = col - paid
        e.add_field(name="Current balance",   value=f"**{bal:,}** {CE}",    inline=True)
        e.add_field(name="Total collected",   value=f"**{col:,}** {CE}",    inline=True)
        e.add_field(name="Total paid out",    value=f"**{paid:,}** {CE}",   inline=True)
        e.add_field(name="Net profit",        value=f"**{profit:,}** {CE}", inline=True)
        e.add_field(name="Last updated",      value=stats.get("last_updated", "never"), inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @casino_group.command(name="ban", description="[Admin] Ban a user from the casino")
    @app_commands.describe(user="User to ban", reason="Reason for ban")
    async def admin_ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = None):
        await cdb.ban_user(user.id, interaction.user.id, reason)
        await interaction.response.send_message(
            embed=_embed("Casino Ban", f"🚫 {user.mention} has been banned from the casino.\nReason: {reason or 'No reason given'}"),
            ephemeral=True,
        )

    @casino_group.command(name="unban", description="[Admin] Unban a user from the casino")
    @app_commands.describe(user="User to unban")
    async def admin_unban(self, interaction: discord.Interaction, user: discord.Member):
        await cdb.unban_user(user.id)
        await interaction.response.send_message(
            embed=_embed("Casino Unban", f"✅ {user.mention} has been unbanned from the casino."),
            ephemeral=True,
        )

    @casino_group.command(name="setlimit", description="[Admin] Set a user's max bet cap")
    @app_commands.describe(user="Target user", max_bet="New max bet limit")
    async def admin_setlimit(self, interaction: discord.Interaction, user: discord.Member, max_bet: int):
        if max_bet <= 0:
            await interaction.response.send_message(embed=_err("Limit must be positive."), ephemeral=True)
            return
        await cdb.set_bet_limit(user.id, max_bet)
        await interaction.response.send_message(
            embed=_embed("Bet Limit Set", f"✅ {user.mention}'s max bet is now **{max_bet:,}** {CE}."),
            ephemeral=True,
        )

    @casino_group.command(name="topwinners", description="[Admin] Casino top winners leaderboard")
    async def admin_topwinners(self, interaction: discord.Interaction):
        rows = await cdb.get_top_winners(10)
        if not rows:
            await interaction.response.send_message(embed=_embed("Top Winners", "No data yet."), ephemeral=True)
            return
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            wr    = f"{int(r['games_won']/r['games_played']*100)}%" if r['games_played'] else "—"
            lines.append(
                f"{medal} **{r['username'] or r['user_id']}**  "
                f"Won: **{r['total_won']:,}** {CE}  |  W/R: {wr}  |  🏆 {r['jackpots']}"
            )
        e = _embed("🏆 Casino Top Winners", "\n".join(lines))
        await interaction.response.send_message(embed=e, ephemeral=True)

    @casino_group.command(name="flush", description="[Admin] Pay bank balance to yourself")
    @app_commands.describe(amount="Amount to withdraw (0 = all)")
    async def admin_flush(self, interaction: discord.Interaction, amount: int = 0):
        bank_bal = await cdb.get_bank_balance()
        withdraw = bank_bal if amount == 0 else min(amount, bank_bal)
        if withdraw == 0:
            await interaction.response.send_message(embed=_err("Bank is empty."), ephemeral=True)
            return
        ok = await cdb.pay_from_bank(withdraw)
        if ok:
            await db.update_balance(interaction.user.id, withdraw)
            await interaction.response.send_message(
                embed=_embed(
                    "Bank Flush",
                    f"✅ Transferred **{withdraw:,}** {CE} from the bank to {interaction.user.mention}.",
                    config.COLORS.get("success"),
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(embed=_err("Insufficient bank balance."), ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    cog = Casino(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.casino_group)
        logger.info("Registered /casino admin group")
    except Exception as e:
        logger.debug(f"/casino admin group already registered: {e}")
