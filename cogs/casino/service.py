"""
cogs/casino/service.py — Casino game logic + display helpers.

Phase 3a.2 step 2: extracted verbatim from cogs/casino/__init__.py. Every
function here was a private (underscore-prefixed) module-level helper. They
fall into a few groups:

  - Embed factories: _embed, _err, _build_roulette_embed, _roulette_board,
    _reel_display, _hand_display, _card_str, _cname
  - Game flow: _run_slots, _run_wheel
  - Bet validation + bank settlement: _validate, _settle
  - RNG primitives: _build_reel, _slots_result, _spin_wheel, _new_deck,
    _hand_value, _calc_roulette, _num_color, _color_emoji

When commands.py is extracted in step 3, the cog's command bodies will call
these directly via `from .service import ...`.
"""
import asyncio
import logging
import random

import discord
from discord.ui import Button, View

import config
import database as db
import casino_db as cdb

from .constants import C, CE, ROULETTE_TABLE_PATH, WHEEL_SPIN_PATH, SPIN_FRAMES, RED_NUMS, CARD_NAMES, SUITS, RANKS

logger = logging.getLogger("tainment.casino.service")


__all__ = [
    "_embed",
    "_err",
    "_validate",
    "_settle",
    "_build_reel",
    "_slots_result",
    "_reel_display",
    "_run_slots",
    "_spin_wheel",
    "_run_wheel",
    "_num_color",
    "_color_emoji",
    "_roulette_board",
    "_build_roulette_embed",
    "_calc_roulette",
    "_new_deck",
    "_card_str",
    "_hand_value",
    "_hand_display",
    "_cname",
]


# ─── Helper bodies (verbatim from __init__.py) ──────────────────────────────

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


def _cname(v: int) -> str:
    return CARD_NAMES.get(v, str(v))
