import os
from dotenv import load_dotenv

load_dotenv()

# -- Authentication --
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX', 't!')

# -- Database --
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tainment.db'))

# -- Subscription Tiers --
SUBSCRIPTION_TIERS = {
    'Basic': {
        'price': 0.00,
        'emoji': '\U0001f3b5',
        'color': 0x95a5a6,
        'features': [
            'Daily coins & streak rewards',
            'Economy (work, gamble, slots, rob)',
            'Basic fishing (no rod bonus)',
            'Number guessing & Rock Paper Scissors',
            'All fun commands (8ball, roll, flip, etc.)',
            'Word chain, hot potato, fast math',
            '150 daily coins',
        ],
        'daily_coins': 150,
        'xp_multiplier': 1.0,
        'work_bonus': 1.0,
        'games': ['guess', 'rps'],
    },
    'Vibe': {
        'price': 1.99,
        'emoji': '\U0001f525',
        'color': 0xe040fb,
        'features': [
            'All Basic features',
            'All joke & story categories',
            'Trivia, typerace, riddles, emoji decode',
            'Would You Rather with token rewards',
            '200 daily coins (+50 vs Basic)',
            '1.2x XP multiplier',
            'Vibe badge on profile',
            '+10% work coin bonus',
        ],
        'daily_coins': 200,
        'xp_multiplier': 1.2,
        'work_bonus': 1.1,
        'games': ['guess', 'rps', 'trivia'],
    },
    'Premium': {
        'price': 4.99,
        'emoji': '\u2b50',
        'color': 0xf1c40f,
        'features': [
            'All Vibe features',
            'Hangman & Wordle',
            'All mini-games (Scramble, Math Quiz, Higher/Lower)',
            '350 daily coins',
            '1.5x XP multiplier',
            '+20% work coin bonus',
            'Premium fishing: +15% rare fish chance',
            '1 free Lucky Gamble per week',
            'Premium badge on profile',
        ],
        'daily_coins': 350,
        'xp_multiplier': 1.5,
        'work_bonus': 1.2,
        'games': ['guess', 'rps', 'trivia', 'hangman', 'wordle'],
    },
    'Pro': {
        'price': 7.99,
        'emoji': '\u26a1',
        'color': 0x9b59b6,
        'features': [
            'All Premium features',
            'Blackjack (exclusive)',
            '500 daily coins',
            '3x XP multiplier',
            '+35% work coin bonus',
            'Pro fishing: +30% legendary fish chance',
            'Double fishing XP',
            '2 free Lucky Gambles per week',
            '50% larger daily streak bonus',
            'Priority support',
            'Pro badge on profile',
        ],
        'daily_coins': 500,
        'xp_multiplier': 3.0,
        'work_bonus': 1.35,
        'games': ['guess', 'rps', 'trivia', 'hangman', 'wordle', 'blackjack'],
    },
}

# -- Rate Limits (seconds) --
COOLDOWNS = {
    'joke': 5,
    'story': 10,
    'game': 30,
    'trivia': 20,
    'daily': 86400,
    'work': 3600,
    'rob': 7200,
    'gamble': 30,
    'slots': 15,
}

# -- Economy --
ECONOMY = {
    'starting_coins': 500,
    'daily_base': 200,
    'daily_streak_bonus': 50,
    'daily_streak_max': 30,
    'work_min': 50,
    'work_max': 250,
    'rob_success_rate': 0.45,
    'rob_min_pct': 0.10,
    'rob_max_pct': 0.30,
    'rob_fine_pct': 0.15,
    'gamble_win_chance': 0.45,
    'gamble_multiplier': 1.9,
    'slots_jackpot_multiplier': 10.0,
    'max_transfer': 100_000,
    'rob_min_balance': 500,
}

# Kept for backwards compat (has_active_item checks use this).
# Authoritative shop data with prices is in shop.py.
SHOP_ITEMS = {
    'xp_boost':      {'name': 'XP Boost',      'description': '2x XP for 1 hour',               'duration': 3600},
    'daily_boost':   {'name': 'Daily Boost',    'description': '2x daily coins for 1 day',        'duration': 86400},
    'luck_charm':    {'name': 'Luck Charm',     'description': '+20% gambling win chance 30 min', 'duration': 1800},
    'rob_shield':    {'name': 'Rob Shield',     'description': 'Immune to rob for 2 hours',       'duration': 7200},
    'vip_badge':     {'name': 'VIP Badge',      'description': 'Permanent VIP badge',             'duration': None},
    'streak_shield': {'name': 'Streak Shield',  'description': 'Saves daily streak once',         'duration': None},
    'double_tokens': {'name': 'Token Doubler',  'description': '2x token earnings for 1 hour',   'duration': 3600},
    'lucky_gamble':  {'name': 'Lucky Gamble',   'description': 'Next gamble has 65% win chance (1-time use)',  'duration': None},
    'gamble_shield': {'name': 'Gamble Shield',  'description': 'Half losses on failed gambles for 24h',        'duration': 86400},
    'daily_reset':   {'name': 'Daily Reset',    'description': 'Reset your daily cooldown',       'duration': None},
    'work_reset':    {'name': 'Work Reset',     'description': 'Reset your work cooldown',        'duration': None},
    'game_lives':    {'name': 'Extra Lives',    'description': '+2 lives in Hangman/Wordle',      'duration': 3600},
    'bonus_round':   {'name': 'Bonus Round',    'description': '+5 questions in Math Quiz',       'duration': 3600},
    'rod_silver':    {'name': 'Silver Rod',     'description': '+30% uncommon / +50% rare fish',  'duration': None},
    'rod_gold':      {'name': 'Golden Rod',     'description': '+60% uncommon / +120% rare fish', 'duration': None},
    'rod_diamond':   {'name': 'Diamond Rod',    'description': '+200% legendary + shorter cd',    'duration': None},
    # Music items
    'music_hint':    {'name': 'Lyrics Hint',    'description': 'Reveals artist initial in lyric games',    'duration': None},
    'trivia_skip':   {'name': 'Trivia Skip',    'description': 'Skip a music trivia question once',        'duration': None},
    'hot_boost':     {'name': 'Hot Boost',      'description': 'Track shares count double for 1 hour',     'duration': 3600},
    'bingo_doubler': {'name': 'Bingo Doubler',  'description': '2 free pre-marked bingo squares',          'duration': None},
    'music_badge':   {'name': 'Music Fanatic',  'description': 'Permanent Music Fanatic badge on profile', 'duration': None},
    'streak_amp':    {'name': 'Streak Amp',     'description': 'Music streak counts double for 24h',       'duration': 86400},
    'genre_unlock':  {'name': 'Genre Pass',     'description': 'Unlock genre/mood discovery permanently',  'duration': None},
    'wrapped_token': {'name': 'Wrapped Token',  'description': 'Generate an early Music Wrapped',          'duration': None},
    'dj_crown':      {'name': 'DJ Crown',       'description': 'Permanent DJ Crown badge + 10% music bonus','duration': None},
    'playlist_slot': {'name': 'Playlist Slot',  'description': '+1 permanent playlist slot',               'duration': None},
    'queue_priority':{'name': 'Queue Priority', 'description': 'Your requests go to position 2 for 2h',    'duration': 7200},
    'trivia_surge':  {'name': 'Trivia Surge',   'description': '2x trivia coin+gem rewards for 30 min',   'duration': 1800},
}

# -- Level milestone roles (PopFusion music theme) --
LEVEL_ROLES = {
    5:   ('\U0001f331 Newcomer',    0x95a5a6),   # gray
    10:  ('\U0001f3a7 Groover',     0x2ecc71),   # green
    20:  ('\U0001f4bf Fanatic',     0x3498db),   # blue
    30:  ('\U0001f3b8 Headliner',   0xe74c3c),   # red
    50:  ('\u26a1 Icon',            0xf39c12),   # gold
    75:  ('\U0001f3c6 Superstar',   0xe040fb),   # magenta
    100: ('\U0001f451 Legend',      0x9b59b6),   # purple
    150: ('\U0001f30c Cosmic',      0x00e5ff),   # cyan
    200: ('\U0001f31f Immortal',    0xffd700),   # bright gold
    300: ('\u2b1b Void Walker',     0x1a0a2e),   # void
}

# -- Genre lane roles (self-assignable interest tags) --
GENRE_ROLES = [
    ('\U0001f3a4 Pop Lane',        0xe040fb),   # magenta
    ('\U0001f3b6 Hip-Hop Lane',    0x00e5ff),   # cyan
    ('\U0001f3b8 Rock Lane',       0xff5722),   # deep orange
    ('\U0001f50a Electronic Lane', 0x7c4dff),   # purple
]

# -- Levels --
LEVELS = {
    'xp_per_message_min': 15,
    'xp_per_message_max': 25,
    'xp_cooldown': 60,
    'xp_base': 100,
    'xp_factor': 1.5,
}

# -- Colors --
COLORS = {
    'primary': 0x5865F2,
    'success': 0x57F287,
    'warning': 0xFEE75C,
    'error': 0xED4245,
    'info': 0xEB459E,
    'gold': 0xF1C40F,
    'purple': 0x9B59B6,
    'dark': 0x2C2F33,
}

# -- Docs --
TOS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tos.md')
PRIVACY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'privacy.md')

# -- Meta --
BOT_VERSION = '2.4.0'

# -- Music System --
MUSIC_REWARDS = {
    'trivia_win':        {'coins': 80,  'gems': 0,  'tokens': 0},
    'trivia_win_vibe':   {'coins': 80,  'gems': 5,  'tokens': 0},
    'trivia_win_pro':    {'coins': 80,  'gems': 5,  'tokens': 2},
    'namethetune_first': {'coins': 150, 'gems': 10, 'tokens': 0},
    'sharetrack_daily':  {'coins': 25,  'gems': 0,  'tokens': 0},
    'streak_7day':       {'coins': 300, 'gems': 10, 'tokens': 0},
    'streak_7day_pro':   {'coins': 300, 'gems': 10, 'tokens': 5},
}

MUSIC_TIER_LIMITS = {
    'max_artists': {'Basic': 5, 'Vibe': 10, 'Premium': 15, 'Pro': 999},
    'max_playlists': {'Basic': 0, 'Vibe': 3, 'Premium': 5, 'Pro': 999},
}
SUPPORT_SERVER = os.getenv('SUPPORT_SERVER', '')
INVITE_URL = os.getenv('INVITE_URL', '')
