import discord
from discord.ext import commands
import logging
import os
import sys
from dotenv import load_dotenv

import aiosqlite
import config
from database import init_db
import database as db


async def _get_prefix(bot, message):
    prefix = config.COMMAND_PREFIX
    if message.guild:
        async with aiosqlite.connect(config.DB_PATH) as db:
            async with db.execute(
                "SELECT prefix FROM server_settings WHERE guild_id = ?",
                (message.guild.id,),
            ) as cur:
                row = await cur.fetchone()
                if row:
                    prefix = row[0]
    return commands.when_mentioned_or(prefix)(bot, message)

# -- Logging --
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tainment_bot.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('tainment')

EXTENSIONS = [
    'entertainment',
    'economy',
    'shop',
    'levels',
    'fun',
    'games',
    'profile',
    'giveaway',
    'polls',
    'reminders',
    'leaderboard',
    'subscription',
    'payment',
    'lemonsqueezy_payment',
    'subscription_tasks',
    'admin_subscription',
    'utils',
    'fishing',
    'support_forms',
    'reaction_roles',
    'fun_games',
    'moderation',
    'server_settings',
    'birthday',
    'music_discovery',
    'music_trivia',
    'music_profiles',
    'spotify',
    'automod',
]


class TainmentBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=_get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

    async def setup_hook(self):
        await init_db()
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded: {ext}")
            except Exception as e:
                logger.error(f"Failed to load {ext}: {e}", exc_info=True)
        await self.tree.sync()
        logger.info("Slash commands synced.")

    async def on_ready(self):
        logger.info(f"Ready as {self.user} (ID: {self.user.id}) | {len(self.guilds)} guilds")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"t!help | {len(self.guilds)} servers",
            ),
        )

    async def on_member_join(self, member: discord.Member):
        role = discord.utils.get(member.guild.roles, name='\U0001f3b5 Listener')
        if role:
            try:
                await member.add_roles(role, reason='Auto-assigned on join')
                logger.info(f"Assigned Member role to {member} in {member.guild}")
            except discord.HTTPException as e:
                logger.warning(f"Could not assign Member role to {member}: {e}")
        prestige_role = discord.utils.get(member.guild.roles, name='\u2728 Prestige')
        if prestige_role and prestige_role < member.guild.me.top_role:
            try:
                if await db.has_active_item(member.id, 'prestige_badge'):
                    await member.add_roles(prestige_role, reason='Restored Prestige role on join')
            except discord.HTTPException as e:
                logger.warning(f"Could not assign Prestige role to {member}: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        # Ensure server settings row exists; server structure is managed explicitly.
        from server_settings import ensure_server
        await ensure_server(guild.id)

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="Thanks for adding Tainment+!",
                    description=(
                        "Your all-in-one premium entertainment bot is ready.\n\n"
                        "**Getting started:**\n"
                        "- `/help` or `t!help` - full command list\n"
                        "- `/daily` - claim free daily coins\n"
                        "- `/subscribe` - unlock premium features\n\n"
                        "**What I offer:**\n"
                        "Games & Trivia | Economy & Levels\n"
                        "Giveaways & Polls | Stories & Jokes"
                    ),
                    color=config.COLORS['primary'],
                )
                embed.set_thumbnail(url=self.user.display_avatar.url)
                embed.set_footer(text=f"Tainment+ v{config.BOT_VERSION}")
                await channel.send(embed=embed)
                break

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="Slow down!",
                description=f"Try again in **{error.retry_after:.1f}s**.",
                color=config.COLORS['warning'],
            )
            await ctx.send(embed=embed, delete_after=6)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="Missing argument",
                description=f"`{error.param.name}` is required. Use `t!help` for details.",
                color=config.COLORS['error'],
            )
            await ctx.send(embed=embed)
            return
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="No permission",
                description="You don't have permission to use this command.",
                color=config.COLORS['error'],
            )
            await ctx.send(embed=embed)
            return
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="I'm missing permissions",
                description=f"I need: {', '.join(error.missing_permissions)}",
                color=config.COLORS['error'],
            )
            await ctx.send(embed=embed)
            return
        logger.error(f"Unhandled error in {ctx.command}: {error}", exc_info=True)


bot = TainmentBot()


# -- Help command --

HELP_CATEGORIES = {
    'economy': {
        'title': 'Economy',
        'commands': [
            ('balance [@user]', 'Check all 3 currency balances'),
            ('coinflip <bet> [heads|tails]', 'Flip a coin for your bet (50/50)'),
            ('daily', 'Claim daily coins + streak gems/tokens'),
            ('gamble <amount>', 'Gamble coins'),
            ('richest', 'Server wealth leaderboard'),
            ('rob @user', 'Attempt to rob a user'),
            ('slots <bet>', 'Slot machine — jackpot pays gems!'),
            ('streak', 'View your daily streak and next milestone'),
            ('transfer @user <amount> [currency]', 'Send currency to someone'),
            ('work', 'Work for coins (1h cooldown)'),
        ],
    },
    'shop': {
        'title': 'Shop',
        'commands': [
            ('buy <item>', 'Purchase a shop item'),
            ('inventory [@user]', 'View active items'),
            ('shop [coins|gems|tokens]', 'Browse the 3-section shop'),
            ('use <item>', 'Use a consumable item (daily_reset / work_reset / streak_restore)'),
        ],
    },
    'fishing': {
        'title': 'Fishing',
        'commands': [
            ('equip <rod>', 'Equip a rod you own'),
            ('fish', 'Cast your line and catch a fish'),
            ('fishbag [@user]', 'View your fish bag by tier'),
            ('fishstats [@user]', 'Your fishing level and stats'),
            ('fishtop', 'Fishing leaderboard'),
            ('radar', 'Preview your next 5 catches (uses Fish Radar item)'),
            ('rods', 'View all 11 rods and their requirements'),
            ('sell [fish|all]', 'Sell fish for coins/gems/tokens'),
            ('unequip', 'Unequip rod — auto-selects best owned rod'),
        ],
    },
    'games': {
        'title': 'Games',
        'commands': [
            ('blackjack [bet]', 'Blackjack — Pro tier only'),
            ('c4', 'Connect Four vs bot (buttons)'),
            ('duel @user <bet>', 'Coin flip duel vs another user'),
            ('guess', 'Number guessing game (7 attempts)'),
            ('hangman [diff]', 'Hangman — easy / medium / hard  (Premium+)'),
            ('highlow [bet]', 'Higher or Lower card game'),
            ('mathquiz [diff]', 'Rapid-fire math quiz — easy / medium / hard'),
            ('roulette <bet> [red|black]', 'Bet on red or black — 1.9x payout  (Premium+)'),
            ('rps', 'Rock Paper Scissors with buttons'),
            ('scramble', 'Unscramble a word — channel race'),
            ('snap', 'Reaction speed game — type SNAP first!'),
            ('trivia [diff]', 'Live trivia — easy / medium / hard  (Vibe+)'),
            ('ttt', 'Tic-Tac-Toe vs bot (buttons)'),
            ('wordle', 'Wordle-style word game  (Premium+)'),
        ],
    },
    'fun': {
        'title': 'Fun',
        'commands': [
            ('8ball <question>', 'Ask the magic 8-ball'),
            ('choose <opt1|opt2|...>', 'Pick from a list of options'),
            ('color [hex]', 'Preview a hex color (random if omitted)'),
            ('compliment [@user]', 'Compliment someone'),
            ('emojidecode', 'Decode an emoji phrase — first correct wins'),
            ('fastmath', 'Channel race math question — speed bonus coins'),
            ('flip', 'Flip a coin'),
            ('fortune', 'Fortune cookie message (+1 coin, 1h cooldown)'),
            ('hotpotato', 'Pass the potato — holder when it explodes loses coins'),
            ('joke [category]', 'Get a joke — dad / puns / tech / animal / food'),
            ('meme [category]', 'Random meme — general / gaming / wholesome / anime / pop'),
            ('mock <text>', 'SpOnGeBoB mock text'),
            ('quote', 'Inspirational quote'),
            ('reverse <text>', 'Reverse text'),
            ('riddle', 'First correct answer wins 80 coins + 1 gem'),
        ],
    },
    'fun2': {
        'title': 'Fun (cont.)',
        'commands': [
            ('roast [@user]', 'Friendly roast someone'),
            ('roll [NdN]', 'Dice roller — e.g. 2d6'),
            ('story [genre]', 'Get a short story — adventure / mystery / sci-fi / fantasy'),
            ('typerace', 'Type a sentence fast — coins based on speed'),
            ('wordchain', 'Chain words — 20 coins per word, gems for top scorer'),
            ('wouldyourather', 'Vote on a dilemma — all voters earn 1 token'),
        ],
    },
    'music': {
        'title': 'Music',
        'commands': [
            ('artistinfo <artist>', 'Artist profile card  (Premium+)'),
            ('genresearch <genre>', 'Genre-filtered song picks  (Vibe+)'),
            ('hotsongs', "This server's hottest tracks this week"),
            ('lyricsguess', 'Guess the song from partial lyrics  (Vibe+)'),
            ('moodsearch <mood>', 'Mood picks: hype/chill/sad/focus/party/workout  (Vibe+)'),
            ('musicprofile [@user]', 'Your music taste card'),
            ('musictrivia [genre]', 'Music trivia with button choices'),
            ('musicwrapped', 'Your monthly music summary  (Vibe+)'),
            ('namethetune', 'Channel race — name the song first!  (Vibe+)'),
            ('newreleases', 'Curated new releases  (Pro)'),
            ('playlist create/add/view/list/delete', 'Manage playlists  (Vibe+)'),
            ('recommend [genre]', 'Get song recommendations'),
            ('setartist <artist>', 'Add a favourite artist to your profile'),
            ('setgenre <genre>', 'Set your favourite genre'),
            ('sharetrack <song> - <artist>', 'Share a track + daily coin reward'),
            ('toptracks', 'Global most-shared songs  (Premium+)'),
        ],
    },
    'spotify': {
        'title': 'Spotify',
        'commands': [
            ('mytoptracks [week|month|all]', 'Your top 5 tracks  (Premium+)'),
            ('nowplaying', "What you're listening to right now  (Vibe+)"),
            ('recenttracks', 'Your last 10 played tracks  (Vibe+)'),
            ('song <query>', 'Search Spotify for a track'),
            ('spotify connect', 'Link your Spotify account'),
            ('spotify disconnect', 'Unlink your Spotify account'),
            ('spotify status', 'Check your Spotify link status'),
            ('spotifyprofile', 'Full Spotify music card  (Pro)'),
            ('spotifyreleases', 'New album/single releases this week'),
            ('topartists [week|month|all]', 'Your top 5 artists  (Premium+)'),
        ],
    },
    'profile': {
        'title': 'Profile',
        'commands': [
            ('avatar [@user]', "View a user's avatar"),
            ('bio [text]', 'Set a custom bio on your profile  (Vibe+)'),
            ('leaderboard', 'Auto-updating richest, XP, and fishing board'),
            ('level [@user]', 'Check XP and level progress'),
            ('mystats', 'Detailed personal stats  (Premium+)'),
            ('profile [@user]', 'View your full profile card'),
            ('rank', 'Server XP leaderboard'),
            ('serverinfo', 'Server statistics'),
            ('userinfo [@user]', 'User information and roles'),
        ],
    },
    'server': {
        'title': 'Server',
        'commands': [
            ('afk [status]', 'Set your AFK status'),
            ('birthday set MM/DD', 'Set your birthday'),
            ('birthday view [@user]', "View someone's birthday"),
            ('birthday list', 'All birthdays in this server'),
            ('birthday del', 'Remove your birthday'),
            ('delreminder <id>', 'Delete a reminder by ID'),
            ('gcreate', 'Create a giveaway'),
            ('gend <msg_id>', 'End a giveaway early'),
            ('greroll <msg_id>', 'Reroll giveaway winners'),
            ('membercount', 'Server member count breakdown'),
            ('poll <question> | <opt1> | <opt2>...', 'Create a poll with up to 5 options'),
            ('randomcolor', 'Generate a random color with preview'),
            ('remind <time> <message>', 'Set a reminder — e.g. 1h30m'),
            ('reminders', 'List your active reminders'),
        ],
    },
    'subscription': {
        'title': 'Subscription',
        'commands': [
            ('benefits', 'Compare all tier benefits side by side'),
            ('renew [months]', 'Renew your subscription'),
            ('servertier', "View this server's subscription tier"),
            ('serversubscribe', 'View server plans — Basic $7.99 / Pro $14.99'),
            ('subscribe', 'View user subscription tiers and pricing'),
            ('tier [@user]', 'Check your current subscription tier'),
            ('upgrade <tier>', 'Upgrade your user subscription'),
        ],
    },
    'admin': {
        'title': 'Admin',
        'commands': [
            ('addbalance @user <amount> [currency]', 'Add/remove balance'),
            ('addemote <name> <url>', 'Add a custom emoji to the server'),
            ('botsetup', 'View bot configuration status for this server'),
            ('cmdlist', 'Show command toggle overrides for this server'),
            ('prefix [new]', 'View or set the server command prefix'),
            ('removebalance @user <amount> [currency]', 'Remove balance from a user'),
            ('reseteconomy @user', 'Reset a user\'s economy data'),
            ('setbalance @user <amount> [currency]', 'Set a user\'s currency balance'),
            ('setbirthdaychannel #channel', 'Set birthday announcement channel'),
            ('setleaderboard #channel', 'Set the live leaderboard channel'),
            ('setlevelupchannel #channel', 'Set level-up announcement channel'),
            ('setupserver', 'Create standard roles, channels, and genre panel'),
            ('togglecmd <cmd> [#channel]', 'Enable/disable a command server-wide or per channel'),
        ],
    },
    'moderation': {
        'title': 'Moderation',
        'commands': [
            ('addrole @user <role>', 'Give a role to a member'),
            ('automod status/enable/disable', 'View or toggle AutoMod'),
            ('automod log/action/spam/links/caps/mentions', 'Configure AutoMod rules'),
            ('automod word add/remove/list/clear', 'Manage the banned word list'),
            ('ban @user [reason]', 'Ban a member'),
            ('clearwarn <id>', 'Remove a warning by case ID'),
            ('kick @user [reason]', 'Kick a member'),
            ('lock / unlock [#channel]', 'Lock or unlock a channel'),
            ('modinfo', 'View moderation statistics for this server'),
            ('modlog [@user]', 'View recent mod cases'),
            ('nick @user [name]', "Change a member's nickname"),
            ('purge <amount>', 'Bulk delete messages'),
            ('removerole @user <role>', 'Remove a role from a member'),
            ('setmodlog #channel', 'Set the mod log channel'),
            ('slowmode <seconds>', 'Set channel slowmode (0 to disable)'),
            ('timeout @user <dur>', 'Temporarily mute a user — 10m / 2h / 1d'),
            ('unban <user_id>', 'Unban a user by ID'),
            ('untimeout @user', "Remove a member's timeout"),
            ('warn @user [reason]', 'Issue a warning — logged to mod log'),
            ('warnings @user', "View a user's warning history"),
        ],
    },
    'info': {
        'title': 'Info',
        'commands': [
            ('help [category]', 'Show this help menu'),
            ('invite', 'Get the bot invite link'),
            ('ping', 'Check bot latency'),
            ('privacy', 'View the Privacy Policy'),
            ('stats', 'Bot statistics'),
            ('support', 'Get the support server link'),
            ('tos', 'View the Terms of Service'),
        ],
    },
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, bot_ref):
        self.bot_ref = bot_ref
        options = [
            discord.SelectOption(label=v['title'], value=k)
            for k, v in HELP_CATEGORIES.items()
        ]
        super().__init__(placeholder="Choose a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = HELP_CATEGORIES[self.values[0]]
        embed = discord.Embed(
            title=f"{cat['title']} Commands",
            color=config.COLORS['primary'],
        )
        for cmd, desc in cat['commands']:
            embed.add_field(name=f"`t!{cmd}`", value=desc, inline=False)
        embed.set_footer(text="All commands also available as /slash commands")
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, bot_ref):
        super().__init__(timeout=120)
        self.add_item(HelpCategorySelect(bot_ref))


@bot.hybrid_command(name='help', description='Get help with all Tainment+ commands')
async def help_command(ctx: commands.Context, category: str = None):
    if category and category.lower() in HELP_CATEGORIES:
        cat = HELP_CATEGORIES[category.lower()]
        embed = discord.Embed(title=f"{cat['title']} Commands", color=config.COLORS['primary'])
        for cmd, desc in cat['commands']:
            embed.add_field(name=f"`t!{cmd}`", value=desc, inline=False)
        embed.set_footer(text="All commands also available as /slash commands")
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="Tainment+ Help",
        description=(
            "Premium entertainment, economy, and community features.\n"
            "Use the dropdown to explore commands, or run `t!help <category>`.\n\n"
            + "  ".join(f"`{k}`" for k in HELP_CATEGORIES)
        ),
        color=config.COLORS['primary'],
    )
    embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
    embed.set_footer(text=f"Tainment+ v{config.BOT_VERSION} | Prefix: t!")
    view = HelpView(ctx.bot)
    await ctx.send(embed=embed, view=view)


@bot.hybrid_command(name='ping', description='Check bot latency')
async def ping(ctx: commands.Context):
    ms = round(ctx.bot.latency * 1000)
    color = (
        config.COLORS['success'] if ms < 100
        else config.COLORS['warning'] if ms < 200
        else config.COLORS['error']
    )
    embed = discord.Embed(title="Pong!", description=f"Latency: **{ms}ms**", color=color)
    await ctx.send(embed=embed)


@bot.hybrid_command(name='stats', description='View bot statistics')
async def stats(ctx: commands.Context):
    import aiosqlite
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            user_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM giveaways WHERE ended = 0") as cur:
            active_giveaways = (await cur.fetchone())[0]

    embed = discord.Embed(title="Tainment+ Statistics", color=config.COLORS['primary'])
    embed.add_field(name="Servers", value=f"`{len(ctx.bot.guilds):,}`", inline=True)
    embed.add_field(name="Registered Users", value=f"`{user_count:,}`", inline=True)
    embed.add_field(name="Active Giveaways", value=f"`{active_giveaways}`", inline=True)
    embed.add_field(name="Latency", value=f"`{round(ctx.bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="Version", value=f"`v{config.BOT_VERSION}`", inline=True)
    embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
    embed.set_footer(text="Tainment+ Premium Bot")
    await ctx.send(embed=embed)


_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.bot.lock')


def _acquire_lock():
    """Exit immediately if another instance is already running."""
    import atexit
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE) as f:
                pid = int(f.read().strip())
            # Check if that PID is actually alive
            import signal
            os.kill(pid, 0)  # raises OSError if not running
            logger.critical(f"Bot already running (PID {pid}). Exiting.")
            sys.exit(1)
        except (OSError, ValueError):
            pass  # Stale lock — previous run crashed; proceed
    with open(_LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(_LOCK_FILE) and os.remove(_LOCK_FILE))


if __name__ == '__main__':
    load_dotenv()
    _acquire_lock()
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.critical("BOT_TOKEN not set. Add it to your .env file.")
        sys.exit(1)
    bot.run(token, log_handler=None)
