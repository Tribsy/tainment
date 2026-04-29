from __future__ import annotations


async def send_reply(ctx, *args, ephemeral: bool = False, **kwargs):
    """Send a response that works for both prefix and interaction contexts."""
    if ephemeral and getattr(ctx, 'interaction', None) is None:
        return await ctx.send(*args, **kwargs)
    return await ctx.send(*args, ephemeral=ephemeral, **kwargs)
