"""
Support forms for the community.
  #bug-reports      — submissions routed privately to #mod-logs (staff only)
  #billing-support  — submissions routed privately to #admin-panel (founder+producer only)
  #feature-requests — submissions posted publicly in the same channel

Admins post panels with:
  t!setupbugreport    — in #bug-reports
  t!setupbilling      — in #billing-support
  t!setupfeaturereq   — in #feature-requests
"""

import discord
from discord.ext import commands
import config
import database as db


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_channel(guild: discord.Guild, *fragments: str) -> discord.TextChannel | None:
    """Return first text channel whose name contains any of the given fragments."""
    for ch in guild.text_channels:
        for frag in fragments:
            if frag in ch.name.lower():
                return ch
    return None


# ── Bug Report ────────────────────────────────────────────────────────────────

class BugReportModal(discord.ui.Modal, title='Bug Report'):
    command_used = discord.ui.TextInput(
        label='Command Used',
        placeholder='e.g. t!fish, /daily, t!gamble',
        required=True,
        max_length=100,
    )
    what_happened = discord.ui.TextInput(
        label='What Happened?',
        style=discord.TextStyle.paragraph,
        placeholder='Describe the bug in detail...',
        required=True,
        max_length=1000,
    )
    expected = discord.ui.TextInput(
        label='What Did You Expect?',
        style=discord.TextStyle.paragraph,
        placeholder='What should have happened instead?',
        required=True,
        max_length=500,
    )
    steps = discord.ui.TextInput(
        label='Steps to Reproduce (optional)',
        style=discord.TextStyle.paragraph,
        placeholder='1. Used t!fish\n2. Error appeared',
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='\U0001f41b New Bug Report',
            color=config.COLORS['error'],
        )
        embed.add_field(name='Reported by', value=interaction.user.mention, inline=True)
        embed.add_field(name='Command Used', value=f'`{self.command_used.value}`', inline=True)
        embed.add_field(name='What Happened', value=self.what_happened.value, inline=False)
        embed.add_field(name='Expected Behavior', value=self.expected.value, inline=False)
        if self.steps.value:
            embed.add_field(name='Steps to Reproduce', value=self.steps.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f'User ID: {interaction.user.id}')

        await interaction.response.send_message(
            '\u2705 Your bug report has been submitted privately to our staff team. Thank you!',
            ephemeral=True,
        )

        # Route to staff-only mod-logs channel
        target = _find_channel(interaction.guild, 'mod-log', 'mod-logs', 'staff-chat')
        if target:
            await target.send(embed=embed)


# ── Billing Support ───────────────────────────────────────────────────────────

class BillingModal(discord.ui.Modal, title='Billing Support'):
    transaction_id = discord.ui.TextInput(
        label='Transaction ID (if available)',
        placeholder='Leave blank if unknown',
        required=False,
        max_length=100,
    )
    subscription_tier = discord.ui.TextInput(
        label='Your Subscription Tier',
        placeholder='Basic / Vibe / Premium / Pro',
        required=True,
        max_length=50,
    )
    issue = discord.ui.TextInput(
        label='Describe Your Issue',
        style=discord.TextStyle.paragraph,
        placeholder='Describe your billing problem clearly...',
        required=True,
        max_length=1000,
    )
    contact = discord.ui.TextInput(
        label='Additional Contact Info (optional)',
        placeholder='e.g. email address',
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='\U0001f4b3 New Billing Support Request',
            color=config.COLORS['warning'],
        )
        embed.add_field(name='User', value=interaction.user.mention, inline=True)
        embed.add_field(name='Tier', value=self.subscription_tier.value, inline=True)
        if self.transaction_id.value:
            embed.add_field(name='Transaction ID', value=f'`{self.transaction_id.value}`', inline=True)
        embed.add_field(name='Issue', value=self.issue.value, inline=False)
        if self.contact.value:
            embed.add_field(name='Contact Info', value=self.contact.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f'User ID: {interaction.user.id}')

        await interaction.response.send_message(
            '\u2705 Your billing request has been submitted privately to our admin team. We will contact you soon.',
            ephemeral=True,
        )

        # Route to admin-only channel (founder + producer only)
        target = _find_channel(interaction.guild, 'admin-panel', 'admin')
        if target:
            await target.send(embed=embed)


# ── Feature Request ───────────────────────────────────────────────────────────

class FeatureRequestModal(discord.ui.Modal, title='Feature Request'):
    feature_name = discord.ui.TextInput(
        label='Feature Name',
        placeholder='e.g. Daily fishing tournament, Custom profile themes',
        required=True,
        max_length=100,
    )
    problem = discord.ui.TextInput(
        label='What problem does it solve?',
        style=discord.TextStyle.paragraph,
        placeholder='Describe the gap or issue this would fix...',
        required=True,
        max_length=800,
    )
    usage = discord.ui.TextInput(
        label='How would you use it?',
        style=discord.TextStyle.paragraph,
        placeholder='Walk us through a typical use case...',
        required=True,
        max_length=600,
    )
    priority = discord.ui.TextInput(
        label='How important is this to you?',
        placeholder='Nice to have / Would use regularly / Essential',
        required=True,
        max_length=80,
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='\u2b50 Feature Request',
            color=config.COLORS['info'],
        )
        embed.add_field(name='Requested by', value=interaction.user.mention, inline=True)
        embed.add_field(name='Feature', value=f'**{self.feature_name.value}**', inline=True)
        embed.add_field(name='Problem it solves', value=self.problem.value, inline=False)
        embed.add_field(name='Use case', value=self.usage.value, inline=False)
        embed.add_field(name='Priority to requester', value=self.priority.value, inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f'User ID: {interaction.user.id}  \u2014  PopFusion Feature Tracker')

        await interaction.response.send_message(
            '\u2705 Feature request submitted! The community can see and vote on it below.',
            ephemeral=True,
        )
        await interaction.channel.send(embed=embed, view=FeatureVoteView())


# ── Persistent Buttons ────────────────────────────────────────────────────────

class BugReportButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Submit Bug Report',
            emoji='\U0001f41b',
            style=discord.ButtonStyle.danger,
            custom_id='tainment:bugreport',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BugReportModal())


class BillingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Billing Support Request',
            emoji='\U0001f4b3',
            style=discord.ButtonStyle.primary,
            custom_id='tainment:billing',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BillingModal())


class FeatureVoteView(discord.ui.View):
    """Persistent upvote/downvote buttons attached to feature request submissions."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='0', emoji='\U0001f44d', style=discord.ButtonStyle.success, custom_id='tainment:vote_up')
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, vote=1)

    @discord.ui.button(label='0', emoji='\U0001f44e', style=discord.ButtonStyle.danger, custom_id='tainment:vote_down')
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, vote=-1)

    async def _handle_vote(self, interaction: discord.Interaction, vote: int):
        msg_id = interaction.message.id
        user_id = interaction.user.id

        existing = await db.get_user_vote(msg_id, user_id)

        if existing == vote:
            # Same button clicked again — remove vote (toggle off)
            await db.remove_feature_vote(msg_id, user_id)
        else:
            # New vote or switching sides
            await db.set_feature_vote(msg_id, user_id, vote)

        ups, downs = await db.get_vote_counts(msg_id)

        # Update button labels
        view = FeatureVoteView()
        for item in view.children:
            if item.custom_id == 'tainment:vote_up':
                item.label = str(ups)
            elif item.custom_id == 'tainment:vote_down':
                item.label = str(downs)

        await interaction.response.edit_message(view=view)


class FeatureRequestButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Submit Feature Request',
            emoji='\u2b50',
            style=discord.ButtonStyle.success,
            custom_id='tainment:featurerequest',
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeatureRequestModal())


class BugReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BugReportButton())


class BillingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BillingButton())


class FeatureRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FeatureRequestButton())


# ── Cog ───────────────────────────────────────────────────────────────────────

class SupportForms(commands.Cog, name='Support Forms'):
    """Modal forms for bug reports, billing, and feature requests."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(BugReportView())
        bot.add_view(BillingView())
        bot.add_view(FeatureRequestView())
        bot.add_view(FeatureVoteView())

    @commands.command(name='setupbugreport', description='Post the bug report panel (Admin)')
    @commands.has_permissions(manage_channels=True)
    async def setup_bugreport(self, ctx: commands.Context):
        embed = discord.Embed(
            title='\U0001f41b Bug Report',
            description=(
                'Found a bug? Help us fix it!\n\n'
                'Click the button below and fill in the short form. '
                'Your report is sent **privately to staff** \u2014 no one else can see it.\n\n'
                '**Please include:**\n'
                '\u2022 The exact command you used\n'
                '\u2022 What went wrong\n'
                '\u2022 What you expected\n'
                '\u2022 Steps to reproduce (if possible)\n\n'
                '*All reports are reviewed by \U0001f6e1\ufe0f Stage Managers and above.*'
            ),
            color=config.COLORS['error'],
        )
        embed.set_footer(text='PopFusion Support  \u2014  Reports are private to staff')
        await ctx.send(embed=embed, view=BugReportView())

    @commands.command(name='setupbilling', description='Post the billing support panel (Admin)')
    @commands.has_permissions(manage_channels=True)
    async def setup_billing(self, ctx: commands.Context):
        embed = discord.Embed(
            title='\U0001f4b3 Billing Support',
            description=(
                'Having a payment or subscription issue?\n\n'
                'Click the button below. Your request is sent **privately to admins only**.\n\n'
                '**We can help with:**\n'
                '\u2022 Payment not processing\n'
                '\u2022 Subscription not activating\n'
                '\u2022 Wrong tier applied\n'
                '\u2022 Refund requests\n'
                '\u2022 Renewal problems\n\n'
                '*Handled by \U0001f39b\ufe0f Founders and \U0001f39a\ufe0f Producers only.*'
            ),
            color=config.COLORS['warning'],
        )
        embed.set_footer(text='PopFusion Support  \u2014  Requests are private to admins')
        await ctx.send(embed=embed, view=BillingView())

    @commands.command(name='setupfeaturereq', description='Post the feature request panel (Admin)')
    @commands.has_permissions(manage_channels=True)
    async def setup_feature_req(self, ctx: commands.Context):
        embed = discord.Embed(
            title='\u2b50 Feature Requests',
            description=(
                'Have an idea that would make PopFusion better?\n\n'
                'Click the button below to submit your idea. '
                'Requests are **posted publicly** so the community can see what\'s being suggested.\n\n'
                '**Good requests include:**\n'
                '\u2022 A clear name for the feature\n'
                '\u2022 The problem it would solve\n'
                '\u2022 How you\'d actually use it\n\n'
                '*Staff review all requests and consider them for future updates.*'
            ),
            color=config.COLORS['info'],
        )
        embed.set_footer(text='PopFusion  \u2014  Your ideas shape the community')
        await ctx.send(embed=embed, view=FeatureRequestView())


async def setup(bot: commands.Bot):
    await bot.add_cog(SupportForms(bot))
