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


# Phase 3a.2 step 2: helpers and constants moved out of __init__.py.
# constants.py holds C, CE, asset paths.  service.py holds the 20
# game-logic + embed-factory helpers.  Both are leaf modules — no
# circular imports remain.
from .constants import C, CE, ROULETTE_TABLE_PATH, WHEEL_SPIN_PATH  # noqa: F401
from .service import *  # noqa: F401, F403  (re-exports the 20 helpers)


# ─────────────────────────────────────────────────────────────────────────────
# ── SLOTS ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ── WHEEL OF FORTUNE ──────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ── ROULETTE ──────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ── BLACKJACK ────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# ── HIGHER OR LOWER ───────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ── DUEL ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Phase 3a.2 step 1: View classes extracted to .views — must be imported AFTER
# all helpers above are defined, since views.py imports those helpers from this package.
from .views import BetModal, RouletteView, BlackjackView, HiLoView, DuelAcceptView  # noqa: E402


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
    """Register the Casino cog.

    discord.py 2.x auto-registers any `app_commands.Group` declared as a class
    attribute when `add_cog` runs, so the `/casino` admin group is wired up
    automatically. The earlier `bot.tree.add_command(cog.casino_group)` call
    was redundant and caused duplicate entries in Discord's `/` autocomplete.
    """
    cog = Casino(bot)
    await bot.add_cog(cog)
    logger.info("Casino cog loaded")
