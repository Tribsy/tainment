# ─────────────────────────────────────────────────────────────────────────────
# CASINO CONFIG  –  paste this block into config.py
# ─────────────────────────────────────────────────────────────────────────────

# ── Branding ─────────────────────────────────────────────────────────────────
BOT_NAME          = "YourBot"           # ← change to your bot name
CURRENCY_NAME     = "Coins"             # ← change e.g. "Credits" / "Gold"
CURRENCY_EMOJI    = "\U0001fa99"        # 🪙  replace with your custom emoji ID
                                        #   e.g. "<:mycoin:123456789012345678>"
CASINO_NAME       = "The Casino"        # shown in embed titles
BANK_NAME         = "Casino Bank"
CASINO_FOOTER     = "YourBot Casino"   # embed footer text

# ── House rules ───────────────────────────────────────────────────────────────
CASINO = {
    "min_bet":      10,
    "max_bet":      50_000,
    "house_edge":   0.05,    # 5 % of every win goes to the bank
    "bank_fee_pct": 0.10,    # 10 % fee on coin transfers (already used in economy)

    # ── Wheel of Fortune segments ────────────────────────────────────────────
    # Each entry: label shown in embed, emoji, payout multiplier (0 = bust), weight
    # Weights are relative – higher = more likely.  They don't need to sum to 100.
    "wheel_segments": [
        {"label": "BUST",     "emoji": "💥", "multiplier": 0.0,  "weight": 20},
        {"label": "½×",       "emoji": "📉", "multiplier": 0.5,  "weight": 18},
        {"label": "1×",       "emoji": "🔄", "multiplier": 1.0,  "weight": 22},
        {"label": "1.5×",     "emoji": "⭐", "multiplier": 1.5,  "weight": 18},
        {"label": "2×",       "emoji": "🎯", "multiplier": 2.0,  "weight": 12},
        {"label": "5×",       "emoji": "💎", "multiplier": 5.0,  "weight": 7},
        {"label": "JACKPOT",  "emoji": "🏆", "multiplier": 10.0, "weight": 3},
    ],

    # ── Slot machine ─────────────────────────────────────────────────────────
    # symbol key → (display emoji, weight)
    "slots_symbols": {
        "seven":   ("7️⃣",  2),
        "bar":     ("🎰",  5),
        "bell":    ("🔔", 10),
        "diamond": ("💎",  8),
        "cherry":  ("🍒", 18),
        "lemon":   ("🍋", 20),
        "orange":  ("🍊", 20),
        "grape":   ("🍇", 17),
    },
    # Payouts: (three-of-a-kind multiplier, two-of-a-kind multiplier)
    # Special: seven = jackpot_mult
    "slots_three_mult":   3.0,
    "slots_two_mult":     1.5,
    "slots_jackpot_mult": 15.0,   # three 7s

    # ── Roulette ─────────────────────────────────────────────────────────────
    # Red numbers on a standard wheel
    "roulette_red": {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36},
    "roulette_payouts": {
        "red":    1,   # 1:1
        "black":  1,
        "odd":    1,
        "even":   1,
        "low":    1,   # 1–18
        "high":   1,   # 19–36
        "number": 35,  # single number
        "dozen":  2,   # 1–12 / 13–24 / 25–36
        "column": 2,
    },

    # ── Blackjack ────────────────────────────────────────────────────────────
    "blackjack_payout":   1.5,   # blackjack pays 3:2

    # ── Higher or Lower ───────────────────────────────────────────────────────
    "highlow_max_streak": 8,     # auto cash-out at this streak
}
