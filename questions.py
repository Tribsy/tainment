"""
500+ unique math questions organised by difficulty.
Used by the mathquiz command so players don't see the same question twice
in a session.  Each entry is (question_text, correct_int_answer).
"""

from typing import NamedTuple


class Q(NamedTuple):
    text: str
    answer: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _dedup(lst: list[Q]) -> list[Q]:
    seen: set[str] = set()
    out: list[Q] = []
    for q in lst:
        if q.text not in seen:
            seen.add(q.text)
            out.append(q)
    return out


# ── EASY  (~200 questions) ─────────────────────────────────────────────────────
# Simple addition, subtraction, and times-tables.

_easy: list[Q] = []

# Addition  a + b  (small numbers)
for _a in range(3, 30, 2):
    for _b in range(2, 25, 3):
        _easy.append(Q(f"{_a} + {_b}", _a + _b))

# Subtraction  a - b  (positive result guaranteed)
for _a in range(10, 55, 3):
    for _b in range(1, _a, 6):
        _easy.append(Q(f"{_a} - {_b}", _a - _b))

# Times tables  a x b  (1–12)
for _a in range(2, 13):
    for _b in range(2, 13):
        _easy.append(Q(f"{_a} x {_b}", _a * _b))

# Division (exact, no remainder)
for _a in range(2, 13):
    for _b in range(2, 13):
        _easy.append(Q(f"{_a * _b} / {_b}", _a))

# What number comes next (+3 sequences)
for _start in range(1, 30):
    _seq = [_start + 3 * i for i in range(4)]
    _easy.append(Q(f"Next: {_seq[0]}, {_seq[1]}, {_seq[2]}, ___", _seq[3]))

# Double a number
for _n in range(1, 51):
    _easy.append(Q(f"Double {_n}", _n * 2))

# Half a number (even numbers only)
for _n in range(2, 102, 2):
    _easy.append(Q(f"Half of {_n}", _n // 2))

EASY: list[Q] = _dedup(_easy)


# ── MEDIUM  (~220 questions) ───────────────────────────────────────────────────
# Larger arithmetic, percentages, squares.

_medium: list[Q] = []

# Larger addition  (50–200)
for _a in range(50, 200, 13):
    for _b in range(10, 100, 17):
        _medium.append(Q(f"{_a} + {_b}", _a + _b))

# Larger subtraction
for _a in range(50, 200, 11):
    for _b in range(5, 80, 14):
        _medium.append(Q(f"{_a} - {_b}", _a - _b))

# 2-digit × 1-digit
for _a in range(12, 99, 7):
    for _b in range(2, 10):
        _medium.append(Q(f"{_a} x {_b}", _a * _b))

# Percentages: X% of N  (common percentages)
_pct_pairs = [
    (10, 50), (10, 80), (10, 130), (10, 200), (10, 350),
    (20, 50), (20, 75), (20, 100), (20, 150), (20, 200),
    (25, 40), (25, 60), (25, 80), (25, 100), (25, 160),
    (50, 30), (50, 48), (50, 76), (50, 90), (50, 120),
    (5,  40), (5,  60), (5,  80), (5, 100), (5,  200),
    (40, 50), (40, 75), (40, 100),(40, 150),(40, 200),
    (75, 40), (75, 80), (75, 100),(75, 120),(75, 200),
    (30, 50), (30, 60), (30, 100),(30, 200),(30, 150),
    (15, 40), (15, 60), (15, 80), (15, 100),(15, 200),
    (60, 50), (60, 75), (60, 100),(60, 150),(60, 200),
]
for _pct, _n in _pct_pairs:
    _ans = _pct * _n // 100
    _medium.append(Q(f"{_pct}% of {_n}", _ans))

# Squares  1²–20²
for _n in range(1, 21):
    _medium.append(Q(f"{_n} squared", _n * _n))

# Cubes  1³–10³
for _n in range(1, 11):
    _medium.append(Q(f"{_n} cubed", _n ** 3))

# Missing number addition  a + ? = c
for _a in range(5, 50, 4):
    for _c in range(_a + 3, _a + 40, 7):
        _medium.append(Q(f"{_a} + ? = {_c}", _c - _a))

# Simple order of ops  a + b x c
for _a, _b, _c in [(2, 3, 4), (1, 5, 3), (3, 2, 5), (4, 3, 2),
                    (5, 4, 3), (2, 6, 3), (7, 2, 4), (3, 5, 2),
                    (6, 3, 4), (1, 7, 3), (4, 2, 6), (8, 2, 3)]:
    _medium.append(Q(f"{_a} + {_b} x {_c}", _a + _b * _c))

for _a, _b, _c in [(10, 2, 3), (15, 3, 2), (20, 4, 3), (12, 3, 4),
                    (8, 2, 5), (18, 3, 2), (16, 4, 3), (14, 2, 4)]:
    _medium.append(Q(f"{_a} - {_b} x {_c}", _a - _b * _c))

MEDIUM: list[Q] = _dedup(_medium)


# ── HARD  (~180 questions) ────────────────────────────────────────────────────
# Multi-step, brackets, harder percentages, factoring.

_hard: list[Q] = []

# (a + b) x c
for _a in range(2, 15, 2):
    for _b in range(2, 12, 3):
        for _c in range(2, 8, 2):
            _hard.append(Q(f"({_a} + {_b}) x {_c}", (_a + _b) * _c))

# a x (b - c)
for _a in range(2, 12, 2):
    for _b in range(8, 20, 3):
        for _c in range(1, _b, 4):
            _hard.append(Q(f"{_a} x ({_b} - {_c})", _a * (_b - _c)))

# a squared + b
for _a in range(2, 16):
    for _b in range(1, 20, 3):
        _hard.append(Q(f"{_a}² + {_b}", _a * _a + _b))

# a squared - b
for _a in range(4, 16):
    for _b in range(1, _a * _a, 7):
        _hard.append(Q(f"{_a}² - {_b}", _a * _a - _b))

# Percentage of a larger number
_hard_pct = [
    (15, 80), (35, 60), (45, 80), (65, 40), (85, 20),
    (12, 75), (18, 50), (22, 150),(28, 100),(32, 125),
    (42, 200),(55, 80), (68, 50), (72, 75), (88, 25),
    (14, 350),(16, 250),(24, 125),(36, 150),(44, 225),
    (48, 175),(52, 300),(56, 125),(64, 375),(76, 200),
]
for _pct, _n in _hard_pct:
    _ans = _pct * _n // 100
    _hard.append(Q(f"{_pct}% of {_n}", _ans))

# Three-number arithmetic
for _a, _b, _c in [
    (12, 8, 5), (15, 7, 3), (20, 6, 4), (25, 9, 3),
    (14, 11, 6),(18, 7, 5),(22, 9, 4),(16, 13, 7),
    (30, 8, 3),(24, 7, 4),(28, 6, 5),(32, 9, 2),
]:
    _hard.append(Q(f"{_a} + {_b} - {_c}", _a + _b - _c))
    _hard.append(Q(f"{_a} - {_b} + {_c}", _a - _b + _c))

# Division with larger numbers
for _a in range(3, 15):
    for _b in range(3, 15):
        if _a != _b:
            _hard.append(Q(f"{_a * _b * 2} / {_a}", _b * 2))

# Power of 2 questions
for _n in range(1, 13):
    _hard.append(Q(f"2 to the power of {_n}", 2 ** _n))

HARD: list[Q] = _dedup(_hard)


# ── Public API ─────────────────────────────────────────────────────────────────

ALL: dict[str, list[Q]] = {
    'easy': EASY,
    'medium': MEDIUM,
    'hard': HARD,
}


def pool_sizes() -> dict[str, int]:
    return {k: len(v) for k, v in ALL.items()}


def sample(difficulty: str, n: int) -> list[Q]:
    """Return n unique questions for the given difficulty (no repeats in one call)."""
    import random
    pool = ALL.get(difficulty, MEDIUM)
    return random.sample(pool, min(n, len(pool)))


if __name__ == '__main__':
    for d, qs in ALL.items():
        print(f"{d}: {len(qs)} questions")
