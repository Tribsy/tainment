"""
core/helpers/time_format.py — human-readable duration formatting.

Promoted from utils.py in Phase 2. Currently has no callers; existing cogs
format durations inline with `divmod`. Future cogs and migrations should use
this helper instead.
"""


def format_time(seconds: int) -> str:
    """Render an integer second count as 'X days, Y hours, Z minutes, W seconds'.

    Skips zero-valued units. Pluralizes correctly. Returns '0 seconds' for 0.

        >>> format_time(0)
        '0 seconds'
        >>> format_time(61)
        '1 minute, 1 second'
        >>> format_time(86461)
        '1 day, 1 minute, 1 second'
    """
    parts = []
    if seconds >= 86400:
        parts.append(f"{seconds // 86400} day{'s' if seconds // 86400 != 1 else ''}")
        seconds %= 86400
    if seconds >= 3600:
        parts.append(f"{seconds // 3600} hour{'s' if seconds // 3600 != 1 else ''}")
        seconds %= 3600
    if seconds >= 60:
        parts.append(f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}")
        seconds %= 60
    if seconds:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ', '.join(parts) if parts else '0 seconds'
