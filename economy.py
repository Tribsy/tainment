import discord
from discord.ext import commands
import random
from datetime import datetime, timezone
import config
import database as db
from reply_utils import send_reply


def eco_embed(title: str, description: str, color=None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color or config.COLORS['gold'])
    embed.set_footer(text="Tainment+ Economy")
    return embed


class Economy(commands.Cog, name="Economy"):
    """Daily rewards, work, rob, gambling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- Daily --

    @commands.command(name='daily', description='Claim your daily coin reward')
    async def daily(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        eco = await db.get_economy(ctx.author.id)

        now = datetime.now(timezone.utc)
        last_daily = eco['last_daily']
        streak = eco['daily_streak'] or 0

        if last_daily:
            last_dt = datetime.fromisoformat(last_daily).replace(tzinfo=timezone.utc)
            diff = (now - last_dt).total_seconds()
            if diff < 86400:
                # Check for streak shield before rejecting
                if await db.has_active_item(ctx.author.id, 'streak_shield'):
                    pass  # allow through
                else:
                    remaining = 86400 - diff
                    h, m = divmod(int(remaining), 3600)
                    m = m // 60
                    await ctx.send(embed=eco_embed(
                        "Already claimed!",
                        f"Come back in **{h}h {m}m**.",
                        config.COLORS['warning'],
                    ))
                    return
            elif diff < 172800:
                streak += 1
            else:
                streak = 1
        else:
            streak = 1

        tier = await db.get_tier(ctx.author.id)
        base = config.SUBSCRIPTION_TIERS[tier]['daily_coins']

        has_boost = await db.has_active_item(ctx.author.id, 'daily_boost')
        multiplier = 2 if has_boost else 1

        streak_bonus = min(streak - 1, config.ECONOMY['daily_streak_max']) * config.ECONOMY['daily_streak_bonus']
        coin_reward = (base + streak_bonus) * multiplier

        # Milestone gem rewards
        gem_reward = 0
        if streak % 30 == 0:
            gem_reward = 20
        elif streak % 14 == 0:
            gem_reward = 10
        elif streak % 7 == 0:
            gem_reward = 5

        # Token reward for streak continuation
        has_doubler = await db.has_active_item(ctx.author.id, 'double_tokens')
        token_reward = (2 if has_doubler else 1) if streak > 1 else 0

        await db.earn_currency(ctx.author.id, 'coins', coin_reward)
        if gem_reward:
            await db.earn_currency(ctx.author.id, 'gems', gem_reward)
        if token_reward:
            await db.earn_currency(ctx.author.id, 'tokens', token_reward)
        await db.update_economy_field(
            ctx.author.id,
            last_daily=now.isoformat(),
            daily_streak=streak,
        )

        desc = (
            f"+**{coin_reward}** \U0001fa99"
            + (f"  +**{gem_reward}** \U0001f48e" if gem_reward else "")
            + (f"  +**{token_reward}** \U0001f3ab" if token_reward else "")
            + f"\n\nBase: `{base}` | Streak bonus: `{streak_bonus}` | Boost: `{'2x' if has_boost else '1x'}`"
            + f"\nStreak: **{streak} day{'s' if streak != 1 else ''}**"
        )
        if streak % 7 == 0 and gem_reward:
            desc += f"\n\n**{streak}-day streak milestone! Bonus gems awarded!**"

        await ctx.send(embed=eco_embed("Daily Reward!", desc, config.COLORS['success']))

    # -- Work --

    @commands.command(name='work', description='Work to earn coins (1h cooldown)')
    @commands.cooldown(1, config.COOLDOWNS['work'], commands.BucketType.user)
    async def work(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)

        jobs = [
            "delivered pizza", "wrote some code", "tutored students",
            "walked dogs", "fixed computers", "drove a taxi",
            "streamed on Twitch", "sold lemonade", "mowed lawns",
            "designed a logo", "ran a support desk", "tested an app",
            "packed warehouse orders", "translated documents",
        ]
        job = random.choice(jobs)
        amount = random.randint(config.ECONOMY['work_min'], config.ECONOMY['work_max'])
        await db.earn_currency(ctx.author.id, 'coins', amount)
        await ctx.send(embed=eco_embed(
            "Work complete!",
            f"You {job} and earned **{amount:,}** \U0001fa99",
            config.COLORS['success'],
        ))

    # -- Rob --

    @commands.command(name='rob', description='Attempt to rob another user')
    @commands.cooldown(1, config.COOLDOWNS['rob'], commands.BucketType.user)
    async def rob(self, ctx: commands.Context, target: discord.Member):
        if target.id == ctx.author.id or target.bot:
            await ctx.send(embed=eco_embed("Nope", "Invalid target.", config.COLORS['error']))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_user(target.id, target.name)

        if await db.has_active_item(target.id, 'rob_shield'):
            await ctx.send(embed=eco_embed(
                "Rob failed!",
                f"{target.display_name} is protected by a **Rob Shield**!",
                config.COLORS['warning'],
            ))
            return

        target_bal = await db.get_currency(target.id, 'coins')
        if target_bal < config.ECONOMY['rob_min_balance']:
            await ctx.send(embed=eco_embed(
                "Not worth it",
                f"{target.display_name} only has `{target_bal:,}` coins.",
                config.COLORS['warning'],
            ))
            return

        if random.random() < config.ECONOMY['rob_success_rate']:
            pct = random.uniform(config.ECONOMY['rob_min_pct'], config.ECONOMY['rob_max_pct'])
            stolen = int(target_bal * pct)
            await db.spend_currency(target.id, 'coins', stolen)
            await db.earn_currency(ctx.author.id, 'coins', stolen)
            embed = eco_embed(
                "Robbery successful!",
                f"You stole **{stolen:,}** \U0001fa99 ({int(pct*100)}%) from {target.mention}!",
                config.COLORS['success'],
            )
        else:
            my_bal = await db.get_currency(ctx.author.id, 'coins')
            fine = int(my_bal * config.ECONOMY['rob_fine_pct'])
            await db.spend_currency(ctx.author.id, 'coins', fine)
            embed = eco_embed(
                "Caught red-handed!",
                f"You were caught robbing {target.mention} and fined **{fine:,}** \U0001fa99",
                config.COLORS['error'],
            )
        await ctx.send(embed=embed)

    # -- Gamble --

    @commands.command(name='gamble', description='Gamble your coins')
    @commands.cooldown(1, config.COOLDOWNS['gamble'], commands.BucketType.user)
    async def gamble(self, ctx: commands.Context, amount: int):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        bal = await db.get_currency(ctx.author.id, 'coins')

        if amount <= 0 or amount > bal:
            await ctx.send(embed=eco_embed("Invalid", f"Balance: `{bal:,}` \U0001fa99", config.COLORS['error']))
            return

        win_chance = config.ECONOMY['gamble_win_chance']
        if await db.has_active_item(ctx.author.id, 'luck_charm'):
            win_chance += 0.20
        if await db.has_active_item(ctx.author.id, 'lucky_gamble'):
            win_chance = max(win_chance, 0.65)
            # Consume the item
            import aiosqlite
            async with aiosqlite.connect(config.DB_PATH) as conn:
                await conn.execute(
                    "DELETE FROM inventory WHERE user_id = ? AND item_key = 'lucky_gamble' LIMIT 1",
                    (ctx.author.id,)
                )
                await conn.commit()

        if random.random() < win_chance:
            payout = int(amount * config.ECONOMY['gamble_multiplier'])
            profit = payout - amount
            await db.earn_currency(ctx.author.id, 'coins', profit)
            embed = eco_embed(
                "You won!",
                f"Bet: `{amount:,}` \u2192 Payout: **+{payout:,}** \U0001fa99 *(bet returned + {profit:,} profit)*\nNew balance: `{bal + profit:,}`",
                config.COLORS['success'],
            )
        else:
            await db.spend_currency(ctx.author.id, 'coins', amount)
            embed = eco_embed(
                "You lost!",
                f"Bet: `{amount:,}` \u2192 Lost **{amount:,}** \U0001fa99\nNew balance: `{bal - amount:,}`",
                config.COLORS['error'],
            )
        await ctx.send(embed=embed)

    # -- Slots --

    @commands.command(name='slots', description='Play the slot machine')
    @commands.cooldown(1, config.COOLDOWNS['slots'], commands.BucketType.user)
    async def slots(self, ctx: commands.Context, bet: int):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        bal = await db.get_currency(ctx.author.id, 'coins')

        if bet <= 0 or bet > bal:
            await ctx.send(embed=eco_embed("Invalid bet", f"Balance: `{bal:,}` \U0001fa99", config.COLORS['error']))
            return

        symbols = ['7', 'BAR', 'Bell', 'Cherry', 'Lemon', 'Orange']
        weights = [2, 5, 10, 15, 15, 15]
        reels = random.choices(symbols, weights=weights, k=3)
        display = '  |  '.join(reels)

        gem_reward = 0
        if reels[0] == reels[1] == reels[2]:
            if reels[0] == '7':
                mult = config.ECONOMY['slots_jackpot_multiplier']
                result_text, color = "JACKPOT!", config.COLORS['gold']
                gem_reward = 15
            else:
                mult, result_text, color = 3.0, "Three of a kind!", config.COLORS['success']
                gem_reward = 3
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            mult, result_text, color = 1.5, "Two of a kind!", config.COLORS['info']
        else:
            mult, result_text, color = 0, "No match.", config.COLORS['error']

        if mult > 0:
            net = int(bet * mult) - bet
            await db.earn_currency(ctx.author.id, 'coins', net)
            if gem_reward:
                await db.earn_currency(ctx.author.id, 'gems', gem_reward)
            reward_str = f"Net: **+{net:,}** \U0001fa99"
            if gem_reward:
                reward_str += f"  +**{gem_reward}** \U0001f48e"
            desc = f"[ {display} ]\n\n**{result_text}** {mult}x\n{reward_str}"
        else:
            await db.spend_currency(ctx.author.id, 'coins', bet)
            desc = f"[ {display} ]\n\n**{result_text}**\nLost: **-{bet:,}** \U0001fa99"

        embed = discord.Embed(title="Slot Machine", description=desc, color=color)
        embed.set_footer(text="Tainment+ Economy")
        await ctx.send(embed=embed)

    # ── Admin Commands ─────────────────────────────────────────────────────────

    @commands.command(name='setbalance', aliases=['setbal'], description='[Admin] Set a user\'s currency balance')
    @commands.has_permissions(manage_guild=True)
    async def setbalance(self, ctx: commands.Context, target: discord.Member, amount: int, currency: str = 'coins'):
        currency = currency.lower()
        if currency not in ('coins', 'gems', 'tokens'):
            await send_reply(ctx, embed=eco_embed("Invalid currency", "Use `coins`, `gems`, or `tokens`.", config.COLORS['error']), ephemeral=True)
            return
        if amount < 0:
            await send_reply(ctx, embed=eco_embed("Invalid", "Amount cannot be negative.", config.COLORS['error']), ephemeral=True)
            return

        await db.ensure_user(target.id, target.name)
        import aiosqlite
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                f"UPDATE economy SET {currency} = ? WHERE user_id = ?",
                (amount, target.id)
            )
            await conn.commit()

        symbol = {'coins': '🪙', 'gems': '💎', 'tokens': '🎫'}[currency]
        await ctx.send(embed=eco_embed(
            "Balance Set",
            f"Set {target.mention}'s {currency} to **{amount:,}** {symbol}.",
            config.COLORS['success'],
        ))

    @commands.command(name='addbalance', aliases=['addbal', 'addcoins'], description='[Admin] Add currency to a user')
    @commands.has_permissions(manage_guild=True)
    async def addbalance(self, ctx: commands.Context, target: discord.Member, amount: int, currency: str = 'coins'):
        currency = currency.lower()
        if currency not in ('coins', 'gems', 'tokens'):
            await send_reply(ctx, embed=eco_embed("Invalid currency", "Use `coins`, `gems`, or `tokens`.", config.COLORS['error']), ephemeral=True)
            return
        if amount == 0:
            await send_reply(ctx, embed=eco_embed("Invalid", "Amount cannot be 0.", config.COLORS['error']), ephemeral=True)
            return

        await db.ensure_user(target.id, target.name)
        if amount > 0:
            await db.earn_currency(target.id, currency, amount)
        else:
            await db.spend_currency(target.id, currency, abs(amount))

        symbol = {'coins': '🪙', 'gems': '💎', 'tokens': '🎫'}[currency]
        action = "Added" if amount > 0 else "Removed"
        await ctx.send(embed=eco_embed(
            f"Balance {action}",
            f"{action} **{abs(amount):,}** {symbol} {'to' if amount > 0 else 'from'} {target.mention}.",
            config.COLORS['success'],
        ))

    @commands.command(name='removebalance', aliases=['removebal', 'deduct'], description='[Admin] Remove currency from a user')
    @commands.has_permissions(manage_guild=True)
    async def removebalance(self, ctx: commands.Context, target: discord.Member, amount: int, currency: str = 'coins'):
        currency = currency.lower()
        if currency not in ('coins', 'gems', 'tokens'):
            await send_reply(ctx, embed=eco_embed("Invalid currency", "Use `coins`, `gems`, or `tokens`.", config.COLORS['error']), ephemeral=True)
            return
        if amount <= 0:
            await send_reply(ctx, embed=eco_embed("Invalid", "Amount must be positive.", config.COLORS['error']), ephemeral=True)
            return

        await db.ensure_user(target.id, target.name)
        await db.spend_currency(target.id, currency, amount)

        symbol = {'coins': '🪙', 'gems': '💎', 'tokens': '🎫'}[currency]
        await ctx.send(embed=eco_embed(
            "Balance Removed",
            f"Removed **{amount:,}** {symbol} from {target.mention}.",
            config.COLORS['warning'],
        ))

    @commands.command(name='reseteconomy', aliases=['reseteco'], description='[Admin] Reset a user\'s economy data')
    @commands.has_permissions(administrator=True)
    async def reseteconomy(self, ctx: commands.Context, target: discord.Member):
        await db.ensure_user(target.id, target.name)

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False

            @discord.ui.button(label='Confirm Reset', style=discord.ButtonStyle.danger)
            async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your button.", ephemeral=True)
                    return
                self.confirmed = True
                for child in self.children:
                    child.disabled = True
                self.stop()
                await interaction.response.edit_message(view=self)

            @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
            async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your button.", ephemeral=True)
                    return
                for child in self.children:
                    child.disabled = True
                self.stop()
                await interaction.response.edit_message(view=self)

        view = ConfirmView()
        msg = await ctx.send(
            embed=eco_embed(
                "Confirm Reset",
                f"Reset **{target.mention}**'s economy? This will set coins/gems/tokens to 0 and clear streak.",
                config.COLORS['warning'],
            ),
            view=view,
        )
        await view.wait()

        if view.confirmed:
            import aiosqlite
            async with aiosqlite.connect(config.DB_PATH) as conn:
                await conn.execute(
                    "UPDATE economy SET coins=0, gems=0, tokens=0, total_earned=0, daily_streak=0, last_daily=NULL, last_work=NULL, last_rob=NULL WHERE user_id=?",
                    (target.id,)
                )
                await conn.commit()
            await msg.edit(embed=eco_embed(
                "Economy Reset",
                f"{target.mention}'s economy has been reset.",
                config.COLORS['success'],
            ), view=view)
        else:
            await msg.edit(embed=eco_embed("Cancelled", "No changes made.", config.COLORS['warning']), view=view)

    # -- Richest --

    @commands.command(name='richest', description='Server coin leaderboard')
    async def richest(self, ctx: commands.Context):
        import aiosqlite
        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT e.user_id, e.coins, e.gems, e.tokens, u.username FROM economy e JOIN users u ON e.user_id = u.user_id ORDER BY e.coins DESC LIMIT 10"
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await ctx.send(embed=eco_embed("No data", "No economy data yet.", config.COLORS['warning']))
            return

        medals = [':first_place:', ':second_place:', ':third_place:']
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            member = ctx.guild.get_member(row['user_id']) if ctx.guild else None
            name = member.display_name if member else row['username']
            lines.append(
                f"{medal} **{name}** — `{row['coins']:,}` \U0001fa99  `{row['gems']}` \U0001f48e  `{row['tokens']}` \U0001f3ab"
            )

        embed = discord.Embed(
            title="Richest Users",
            description="\n".join(lines),
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Tainment+ Economy")
        await ctx.send(embed=embed)


    # -- Coinflip --

    @commands.command(name='coinflip', aliases=['cf'], description='Bet coins on heads or tails (50/50)')
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def coinflip(self, ctx: commands.Context, bet: int, side: str = 'heads'):
        side = side.lower()
        if side not in ('heads', 'tails', 'h', 't'):
            await ctx.send(embed=eco_embed("Invalid side", "Choose `heads` or `tails`.", config.COLORS['error']))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        bal = await db.get_currency(ctx.author.id, 'coins')

        if bet <= 0 or bet > bal:
            await ctx.send(embed=eco_embed("Invalid bet", f"Balance: `{bal:,}` \U0001fa99", config.COLORS['error']))
            return

        chosen = 'heads' if side in ('heads', 'h') else 'tails'
        result = random.choice(['heads', 'tails'])
        won = chosen == result

        if won:
            await db.earn_currency(ctx.author.id, 'coins', bet)
            embed = eco_embed(
                f"It's {result}! You win!",
                f"You bet **{bet:,}** on `{chosen}` and won **+{bet:,}** \U0001fa99\nNew balance: `{bal + bet:,}`",
                config.COLORS['success'],
            )
        else:
            await db.spend_currency(ctx.author.id, 'coins', bet)
            embed = eco_embed(
                f"It's {result}! You lose.",
                f"You bet **{bet:,}** on `{chosen}` and lost **{bet:,}** \U0001fa99\nNew balance: `{bal - bet:,}`",
                config.COLORS['error'],
            )
        embed.set_footer(text="Coinflip | 50/50 odds")
        await ctx.send(embed=embed)

    # -- Streak --

    @commands.command(name='streak', description='View your daily streak and next milestone')
    async def streak(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        eco = await db.get_economy(ctx.author.id)
        streak = eco['daily_streak'] if eco else 0

        milestones = [7, 14, 30, 60, 90, 180, 365]
        next_ms = next((m for m in milestones if m > streak), None)

        lines = [f"Current streak: **{streak} day{'s' if streak != 1 else ''}** \U0001f525"]
        if next_ms:
            remaining = next_ms - streak
            bonus = {7: '+5 gems', 14: '+10 gems', 30: '+20 gems', 60: '+25 gems', 90: '+30 gems', 180: '+40 gems', 365: '+50 gems'}.get(next_ms, 'bonus')
            lines.append(f"\nNext milestone: **{next_ms} days** ({remaining} more) — {bonus}")
        else:
            lines.append("\nYou've hit every streak milestone! Keep it up!")

        lines.append(f"\nClaim with `t!daily` every 24 hours to keep your streak alive.")

        await ctx.send(embed=eco_embed("Daily Streak", "\n".join(lines), config.COLORS['gold']))


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
