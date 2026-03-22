import discord
from discord.ext import commands
import logging
import os
import sys
from dotenv import load_dotenv

import aiosqlite
import config
from database import init_db


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
        # Ensure level milestone roles exist in every guild
        from server_settings import _create_level_roles
        for guild in self.guilds:
            try:
                await _create_level_roles(guild)
            except Exception as e:
                logger.warning(f"Could not create level roles in {guild}: {e}")

    async def on_member_join(self, member: discord.Member):
        role = discord.utils.get(member.guild.roles, name='\U0001f3b5 Listener')
        if role:
            try:
                await member.add_roles(role, reason='Auto-assigned on join')
                logger.info(f"Assigned Member role to {member} in {member.guild}")
            except discord.HTTPException as e:
                logger.warning(f"Could not assign Member role to {member}: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        # Ensure server settings row and level roles exist
        from server_settings import ensure_server, _create_level_roles
        await ensure_server(guild.id)
        await _create_level_roles(guild)

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
    'entertainment': {
        'title': 'Entertainment',
        'commands': [
            ('joke [category]', 'Get a joke  (dad / puns / tech / animal / food)'),
            ('story [genre]', 'Get a story  (adventure / mystery / sci-fi / fantasy)'),
            ('trivia [diff]', 'Live trivia  (easy / medium / hard)'),
            ('rps', 'Rock Paper Scissors with buttons'),
            ('guess', 'Number guessing game'),
            ('hangman [diff]', 'Hangman  (easy / medium / hard)'),
            ('wordle', 'Daily Wordle-style game'),
            ('blackjack [bet]', 'Pro-tier Blackjack'),
        ],
    },
    'economy': {
        'title': 'Economy',
        'commands': [
            ('balance [@user]', 'Check all 3 currency balances'),
            ('daily', 'Claim daily coins + streak gems/tokens'),
            ('work', 'Work for coins (1h cooldown)'),
            ('rob @user', 'Attempt to rob a user'),
            ('coinflip <bet> [heads|tails]', 'Flip a coin for your bet (50/50)'),
            ('streak', 'View your daily streak and next milestone'),
            ('gamble <amount>', 'Gamble coins'),
            ('slots <bet>', 'Slot machine — jackpot pays gems!'),
            ('richest', 'Server wealth leaderboard'),
            ('shop [coins|gems|tokens]', 'Browse the 3-section shop'),
            ('buy <item>', 'Purchase a shop item'),
            ('inventory', 'View active items'),
            ('transfer @user <amount> [currency]', 'Send currency to someone'),
            ('setbalance @user <amount> [currency]', '[Admin] Set user balance'),
            ('addbalance @user <amount> [currency]', '[Admin] Add/remove balance'),
            ('removebalance @user <amount> [currency]', '[Admin] Remove balance'),
            ('reseteconomy @user', '[Admin] Reset user economy'),
        ],
    },
    'fishing': {
        'title': 'Fishing',
        'commands': [
            ('fish', 'Cast your line and catch a fish'),
            ('fishbag [@user]', 'View your fish bag by tier'),
            ('sell [fish|all]', 'Sell fish for coins/gems/tokens'),
            ('fishstats [@user]', 'Your fishing level and stats'),
            ('fishtop', 'Fishing leaderboard'),
            ('rods', 'View all 11 rods and their tier requirements'),
            ('buy rod_silver', 'Buy a rod from the shop'),
        ],
    },
    'levels': {
        'title': 'Levels',
        'commands': [
            ('level [@user]', 'Check XP and level'),
            ('rank', 'Server XP leaderboard'),
        ],
    },
    'fun': {
        'title': 'Fun',
        'commands': [
            ('8ball <question>', 'Magic 8-ball'),
            ('roll [NdN]', 'Dice roller  (e.g. 2d6)'),
            ('flip', 'Flip a coin'),
            ('fortune', 'Fortune cookie message (+1 coin, 1h cooldown)'),
            ('color <hex>', 'Preview a hex color'),
            ('meme', 'Random meme from Reddit'),
            ('quote', 'Inspirational quote'),
            ('compliment @user', 'Compliment someone'),
            ('roast @user', 'Friendly roast'),
            ('choose <a|b|c>', 'Pick from options'),
            ('mock <text>', 'SpOnGeBoB mock text'),
            ('reverse <text>', 'Reverse text'),
        ],
    },
    'fun_games': {
        'title': 'Fun Games',
        'commands': [
            ('typerace', 'Type a sentence fast — coins based on speed'),
            ('riddle', 'First correct answer wins 80 coins + 1 gem'),
            ('wouldyourather', 'Vote with buttons — all voters earn 1 token  (Vibe+)'),
            ('emojidecode', 'Decode an emoji phrase — coins and tokens  (Vibe+)'),
            ('fastmath', 'Channel race math question — speed bonus coins'),
            ('hotpotato', 'Pass the button — holder when it explodes loses coins'),
            ('wordchain', 'Chain words — 20 coins per word, gems for top scorer'),
        ],
    },
    'giveaway': {
        'title': 'Giveaways',
        'commands': [
            ('gcreate', 'Create a giveaway'),
            ('gend <msg_id>', 'End a giveaway early'),
            ('greroll <msg_id>', 'Reroll giveaway winners'),
        ],
    },
    'polls': {
        'title': 'Polls',
        'commands': [
            ('poll <question> | <opt1> | <opt2>...', 'Create a poll with up to 5 options'),
        ],
    },
    'reminders': {
        'title': 'Reminders',
        'commands': [
            ('remind <time> <message>', 'Set a reminder  (e.g. 1h30m)'),
            ('reminders', 'List your active reminders'),
            ('delreminder <id>', 'Delete a reminder'),
        ],
    },
    'subscription': {
        'title': 'Subscription',
        'commands': [
            ('subscribe', 'View user subscription tiers and pricing'),
            ('tier [@user]', 'Check your current subscription tier'),
            ('upgrade <tier>', 'Upgrade your user subscription'),
            ('renew [months]', 'Renew your subscription'),
            ('benefits', 'Compare all tier benefits side by side'),
            ('servertier', 'View this server\'s subscription tier'),
            ('serversubscribe', 'View server plans — Basic $14.99 / Pro $23.99 — 30% off user subs for members'),
        ],
    },
    'games': {
        'title': 'Games',
        'commands': [
            ('ttt', 'Tic-Tac-Toe vs bot (buttons)'),
            ('c4', 'Connect Four vs bot (buttons)'),
            ('scramble', 'Unscramble a word (channel race)'),
            ('mathquiz [diff]', 'Rapid-fire math quiz'),
            ('highlow [bet]', 'Higher or Lower card game'),
            ('duel @user <bet>', 'Coin flip duel vs another user'),
            ('snap', 'Reaction speed game'),
            ('roulette <bet> [red|black]', 'Bet on red or black — 1.9x payout  (Premium+)'),
        ],
    },
    'profile': {
        'title': 'Profile',
        'commands': [
            ('profile [@user]', 'View your full profile card'),
            ('bio [text]', 'Set a custom bio on your profile  (Vibe+)'),
            ('mystats', 'Detailed personal stats  (Premium+)'),
            ('serverinfo', 'Server statistics'),
            ('userinfo [@user]', 'User information'),
            ('avatar [@user]', "View a user's avatar"),
        ],
    },
    'utility': {
        'title': 'Utility',
        'commands': [
            ('prefix [new]', 'View or set the server prefix'),
            ('afk [status]', 'Set your AFK status'),
            ('addemote <name> <url>', 'Add an emoji to the server (admin)'),
            ('randomcolor', 'Generate a random color with preview'),
            ('membercount', 'Server member count breakdown'),
            ('togglecmd <cmd> [#channel]', 'Enable/disable a command in this server (admin)'),
            ('cmdlist', 'Show command toggle overrides'),
            ('setbirthdaychannel #channel', 'Set birthday announcement channel (admin)'),
            ('setlevelupchannel #channel', 'Set level-up announcement channel (admin)'),
        ],
    },
    'birthday': {
        'title': 'Birthday',
        'commands': [
            ('birthday set MM/DD', 'Set your birthday'),
            ('birthday view [@user]', "View someone's birthday"),
            ('birthday list', 'All birthdays in this server'),
            ('birthday del', 'Remove your birthday'),
        ],
    },
    'music': {
        'title': 'Music',
        'commands': [
            ('recommend [genre]', 'Get song recommendations (all tiers)'),
            ('hotsongs', 'This server\'s hottest tracks this week'),
            ('sharetrack <song> - <artist>', 'Share a track + daily coin reward'),
            ('genresearch <genre>', 'Genre-filtered picks (Vibe+)'),
            ('moodsearch <mood>', 'Mood-based picks: hype/chill/sad/focus/party/workout (Vibe+)'),
            ('musictrivia [genre]', 'Music trivia with button choices (all tiers)'),
            ('lyricsguess', 'Guess the song from partial lyrics (Vibe+)'),
            ('namethetune', 'Channel race — name the song first! (Vibe+)'),
            ('musicprofile [@user]', 'Your music taste card'),
            ('setgenre <genre>', 'Set your favourite genre'),
            ('setartist <artist>', 'Add a favourite artist'),
            ('musicwrapped', 'Monthly music summary (Vibe+)'),
            ('playlist create/add/view/list/delete', 'Manage playlists (Vibe+)'),
            ('artistinfo <artist>', 'Artist profile card (Premium+)'),
            ('toptracks', 'Global most-shared songs (Premium+)'),
            ('newreleases', 'Curated new releases (Pro)'),
        ],
    },
    'spotify': {
        'title': 'Spotify',
        'commands': [
            ('song <query>', 'Search Spotify for a track (Free)'),
            ('spotifyreleases', 'New album/single releases this week (Free)'),
            ('spotify connect', 'Link your Spotify account'),
            ('spotify disconnect', 'Unlink your Spotify account'),
            ('spotify status', 'Check your Spotify link status'),
            ('nowplaying', 'What you\'re listening to right now (Vibe+)'),
            ('recenttracks', 'Your last 10 played tracks (Vibe+)'),
            ('topartists [week|month|all]', 'Your top 5 artists (Premium+)'),
            ('mytoptracks [week|month|all]', 'Your top 5 tracks (Premium+)'),
            ('spotifyprofile', 'Full Spotify music card (Pro)'),
        ],
    },
    'automod': {
        'title': 'AutoMod',
        'commands': [
            ('automod status', 'View current AutoMod settings'),
            ('automod enable/disable', 'Toggle AutoMod on/off'),
            ('automod log #channel', 'Set AutoMod log channel'),
            ('automod action <warn|timeout|kick>', 'Set violation action'),
            ('automod spam <count> <seconds>', 'Set spam threshold'),
            ('automod links <on|off>', 'Toggle link filter'),
            ('automod allowlink <domain>', 'Whitelist a domain'),
            ('automod caps <0-100>', 'Set caps % threshold (0 = off)'),
            ('automod mentions <count>', 'Max mentions per message (0 = off)'),
            ('automod word add/remove/list/clear', 'Manage banned word list'),
        ],
    },
    'moderation': {
        'title': 'Moderation',
        'commands': [
            ('warn @user <reason>', 'Issue a warning (logged to mod log)'),
            ('warnings @user', "View a user's warning history"),
            ('clearwarn @user <id>', 'Remove a warning by ID'),
            ('kick @user [reason]', 'Kick a member'),
            ('ban @user [reason]', 'Ban a member'),
            ('unban <user_id>', 'Unban by user ID'),
            ('timeout @user <duration>', 'Temporarily mute a user'),
            ('purge <amount>', 'Bulk delete messages'),
            ('slowmode <seconds>', 'Set channel slowmode'),
            ('lock / unlock', 'Lock or unlock a channel'),
            ('modlog', 'View recent moderation cases'),
            ('setmodlog #channel', 'Set the mod log channel (admin)'),
            ('nick @user <name>', 'Change a member\'s nickname'),
            ('addrole / removerole @user <role>', 'Manage member roles'),
        ],
    },
    'profile': {
        'title': 'Profile',
        'commands': [
            ('profile [@user]', 'Full profile card — tier, level, gems, active items'),
            ('level [@user]', 'Check XP, level, and progress bar'),
            ('rank', 'Server XP leaderboard'),
            ('leaderboard', 'Auto-updating top richest, XP, and fishers'),
            ('serverinfo', 'Server statistics'),
            ('userinfo [@user]', 'User information'),
            ('avatar [@user]', "View a user's avatar"),
        ],
    },
    'info': {
        'title': 'Info',
        'commands': [
            ('help [category]', 'Show this menu'),
            ('ping', 'Check bot latency'),
            ('stats', 'Bot statistics'),
            ('verifypayment', 'Verify your LemonSqueezy payment'),
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
