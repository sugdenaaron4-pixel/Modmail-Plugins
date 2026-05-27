import asyncio
import discord

from discord.ext import commands
from discord.ui import View, Button

DEPARTMENTS = {
    "01": "General Inquiries",
    "02": "Partnership",
    "03": "Legal & Abuse",
    "04": "Ventro Studios Ownership",
    "05": "Other / Unsure"
}

AVERAGE_HANDLE_TIME = {
    "01": 5,
    "02": 8,
    "03": 10,
    "04": 30,
    "05": 7
}

AWAITING_PLACEMENT_CATEGORY = 1507468762843054160

DEPARTMENT_CATEGORIES = {
    "01": 1502299888770351177,
    "02": 1502299890284367902,
    "03": 1502299891249189025,
    "04": 1502299891249189025,
    "05": 1507468762843054160,
}


class VentroStudios(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xe02e2e

        self.ticket_departments = {}
        self.claimed_tickets = set()
        self.ticket_created_at = {}
        self.ticket_numbers = {}
        self.currently_serving = {}
        self.ticket_claimers = {}

        self.ticket_counter = 0

    # ==================================================
    # HELPERS
    # ==================================================

    def normalize_department(self, value):
        if not value:
            return None

        value = value.lower().strip()

        aliases = {
            "01": "01",
            "1": "01",
            "general": "01",
            "general inquiries": "01",

            "02": "02",
            "2": "02",
            "partnership": "02",
            "partner": "02",

            "03": "03",
            "3": "03",
            "legal": "03",
            "abuse": "03",

            "04": "04",
            "4": "04",
            "ownership": "04",
            "ventro studios ownership": "04",

            "05": "05",
            "5": "05",
            "other": "05",
            "unsure": "05"
        }

        return aliases.get(value)

    async def move_ticket_to_department(
        self,
        thread,
        department_id
    ):
        category_id = DEPARTMENT_CATEGORIES.get(department_id)

        if not category_id:
            return

        category = thread.guild.get_channel(category_id)

        if not category:
            return

        try:
            await thread.channel.edit(
                category=category
            )

        except Exception:
            pass

    async def can_staff_talk(
        self,
        member,
        thread
    ):
        if member.guild_permissions.administrator:
            return True

        if member.guild_permissions.manage_guild:
            return True

        if thread.id not in self.claimed_tickets:
            return False

        claimer_id = self.ticket_claimers.get(thread.id)

        return claimer_id == member.id

    # ==================================================
    # NAVIGATION
    # ==================================================

    async def send_navigation_embed(self, thread):
        embed = discord.Embed(
            title="ᴀ Support Navigation",
            description=(
                "Welcome to **Ventro Studios**.\n\n"
                "Please select the department you require.\n\n"
                "**01** ▸ General Inquiries\n"
                "**02** ▸ Partnership\n"
                "**03** ▸ Legal & Abuse\n"
                "**04** ▸ Ventro Studios Ownership\n"
                "**05** ▸ Other / Unsure\n\n"
                "Reply with the number only."
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def send_department_embed(self, thread, department_id):
        descriptions = {
            "01": (
                "You have been connected to "
                "**General Inquiries**.\n\n"
                "A support agent will assist you shortly."
            ),
            "02": (
                "You have been connected to "
                "**Partnership**.\n\n"
                "A partnerships team member will assist you shortly."
            ),
            "03": (
                "You have been connected to "
                "**Legal & Abuse**.\n\n"
                "A legal team member will review your case shortly."
            ),
            "04": (
                "You have been connected to "
                "**Ventro Studios Ownership**.\n\n"
                "Estimated wait time:\n"
                "**12 to 48 hours**."
            ),
            "05": (
                "You have been connected to "
                "**Other / Unsure**.\n\n"
                "A support agent will direct your ticket shortly."
            )
        }

        embed = discord.Embed(
            title="Department Selected",
            description=descriptions[department_id],
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def send_staff_department_log(
        self,
        thread,
        department_id,
        user
    ):
        embed = discord.Embed(
            title="📂 Department Selected",
            description=(
                f"User: {user.mention}\n"
                f"Department: "
                f"**{DEPARTMENTS[department_id]}**\n"
                f"Selection Code: {department_id}"
            ),
            color=self.color
        )

        await thread.channel.send(embed=embed)

    # ==================================================
    # QUEUE SYSTEM
    # ==================================================

    async def get_queue_position(
        self,
        thread_id,
        department_id
    ):
        active = []

        for thread in self.bot.threads.cache.values():
            if getattr(thread, "closed", False):
                continue

            if thread.id in self.claimed_tickets:
                continue

            if self.ticket_departments.get(thread.id) != department_id:
                continue

            active.append(thread)

        active.sort(
            key=lambda t: self.ticket_created_at.get(t.id)
        )

        ids = [t.id for t in active]

        return (
            ids.index(thread_id) + 1
            if thread_id in ids
            else 1
        )

    async def send_queue_update(
        self,
        thread,
        department_id
    ):
        if thread.id in self.claimed_tickets:
            return

        position = await self.get_queue_position(
            thread.id,
            department_id
        )

        ticket_number = self.ticket_numbers.get(thread.id)
        serving = self.currently_serving.get(department_id)

        if 10 <= position % 100 <= 20:
            suffix = "th"
        else:
            suffix = {
                1: "st",
                2: "nd",
                3: "rd"
            }.get(position % 10, "th")

        avg = AVERAGE_HANDLE_TIME.get(department_id, 5)

        min_wait = (position - 1) * avg
        max_wait = position * avg

        embed = discord.Embed(
            title="📋 Queue Update",
            description=(
                f"🎟️ **Your Ticket Number:** "
                f"{ticket_number}\n"
                f"📞 **Currently Serving:** "
                f"{serving or 'None'}\n\n"
                f"You are currently "
                f"**{position}{suffix}** in the "
                f"**{DEPARTMENTS[department_id]}** queue.\n\n"
                f"⏱️ Estimated Wait Time:\n"
                f"**{min_wait} - {max_wait} minutes**"
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def update_department_queue(self, department_id):
        for thread in self.bot.threads.cache.values():
            if getattr(thread, "closed", False):
                continue

            if thread.id in self.claimed_tickets:
                continue

            if (
                self.ticket_departments.get(thread.id)
                != department_id
            ):
                continue

            try:
                await self.send_queue_update(
                    thread,
                    department_id
                )

            except Exception:
                pass

    # ==================================================
    # LISTENERS
    # ==================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        ctx = await self.bot.get_context(message)

        if ctx.valid:
            return

        try:
            thread = await self.bot.threads.find(
                recipient=None,
                channel=message.channel
            )

        except Exception:
            return

        if thread is None:
            return

        if not message.author.guild_permissions.manage_messages:
            return

        allowed = await self.can_staff_talk(
            message.author,
            thread
        )

        if allowed:
            return

        try:
            await message.delete()
        except Exception:
            pass

        if thread.id not in self.claimed_tickets:
            warning = (
                "❌ You must `.claim` this ticket before replying."
            )
        else:
            warning = (
                "❌ This ticket is already claimed by another agent."
            )

        try:
            msg = await message.channel.send(warning)
            await asyncio.sleep(5)
            await msg.delete()

        except Exception:
            pass

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await asyncio.sleep(1)

        self.ticket_counter += 1

        self.ticket_numbers[thread.id] = self.ticket_counter
        self.ticket_created_at[thread.id] = (
            discord.utils.utcnow()
        )

        try:
            category = thread.guild.get_channel(
                AWAITING_PLACEMENT_CATEGORY
            )

            if category:
                await thread.channel.edit(
                    category=category
                )

        except Exception:
            pass

        await self.send_navigation_embed(thread)

    @commands.Cog.listener()
    async def on_thread_reply(
        self,
        thread,
        from_mod,
        message,
        anonymous,
        plain
    ):
        if from_mod:
            return

        if thread.id in self.ticket_departments:
            return

        content = message.content.strip().zfill(2)

        if content not in DEPARTMENTS:
            return

        self.ticket_departments[thread.id] = content

        await self.move_ticket_to_department(
            thread,
            content
        )

        await self.send_department_embed(
            thread,
            content
        )

        await self.send_staff_department_log(
            thread,
            content,
            message.author
        )

        await asyncio.sleep(1)

        await self.update_department_queue(content)

    @commands.Cog.listener()
    async def on_thread_close(
        self,
        thread,
        closer,
        silent,
        delete_channel
    ):
        dept = self.ticket_departments.get(thread.id)

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)

        if dept:
            self.currently_serving.pop(dept, None)

            await asyncio.sleep(1)

            await self.update_department_queue(dept)

    # ==================================================
    # CLAIM
    # ==================================================

    @commands.command(name="claim")
    async def claim_ticket(self, ctx):
        thread = await self.bot.threads.find(
            recipient=None,
            channel=ctx.channel
        )

        if thread is None:
            return await ctx.send(
                "❌ This command can only be used "
                "inside a Modmail ticket."
            )

        if thread.id in self.claimed_tickets:
            return await ctx.send(
                "❌ This ticket is already claimed "
                "by another support agent."
            )

        dept = self.ticket_departments.get(
            thread.id,
            "05"
        )

        self.claimed_tickets.add(thread.id)
        self.ticket_claimers[thread.id] = ctx.author.id

        self.currently_serving[dept] = (
            self.ticket_numbers.get(thread.id)
        )

        embed = discord.Embed(
            title="🎉 You've Been Connected with a Support Agent",
            description=(
                f"Great news! A member of the "
                f"**{DEPARTMENTS[dept]}** support team "
                f"has joined your ticket.\n\n"

                "=================\n\n"

                f"👤 **Your Support Agent**\n"
                f"{ctx.author.mention} "
                f"— {ctx.author.name}\n\n"

                "=================\n\n"

                "- The agent will review your issue.\n"
                "- Please provide screenshots if possible.\n"
                "- Provide more info if requested.\n"
                "- You may request another agent if needed.\n\n"

                "=================\n\n"

                "Thank you for Choosing Ventro Studios.\n"
                "<:VSWhiteBIG:1503144455417368788>"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Ventro Studios • Support Team Connected"
        )

        await thread.recipient.send(embed=embed)

        await ctx.message.add_reaction("✅")

        await self.update_department_queue(dept)

    # ==================================================
    # UNCLAIM
    # ==================================================

    @commands.command(name="unclaim")
    async def unclaim_ticket(self, ctx):
        thread = await self.bot.threads.find(
            recipient=None,
            channel=ctx.channel
        )

        if thread is None:
            return

        if thread.id not in self.claimed_tickets:
            return await ctx.send(
                "⚠️ This ticket is not currently claimed."
            )

        dept = self.ticket_departments.get(
            thread.id,
            "05"
        )

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)

        self.currently_serving.pop(dept, None)

        embed = discord.Embed(
            title="🔄 Ticket Update",
            description=(
                f"The Agent from the "
                f"**{DEPARTMENTS[dept]}** support team "
                f"has unclaimed your ticket.\n\n"

                "=================\n\n"

                f"👤 **Previous Support Agent**\n"
                f"{ctx.author.mention} "
                f"— {ctx.author.name}\n\n"

                "=================\n\n"

                "- Your ticket has been returned to the queue.\n"
                "- A new support agent will assist you shortly.\n"
                "- You may be asked to re explain your issue.\n"
                "- Please provide any additional details if needed.\n\n"

                "=================\n\n"

                "Thank you for your patience.\n"
                "<:VSWhiteBIG:1503144455417368788>"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Ventro Studios • Ticket Reassigned"
        )

        await thread.recipient.send(embed=embed)

        await ctx.send(
            "✅ Ticket unclaimed and returned to queue."
        )

        await self.send_queue_update(thread, dept)

        await self.update_department_queue(dept)

    # ==================================================
    # TRANSFER
    # ==================================================

    @commands.command(name="transfer")
    async def transfer_ticket(self, ctx, *, department=None):
        thread = await self.bot.threads.find(
            recipient=None,
            channel=ctx.channel
        )

        if thread is None:
            return await ctx.send(
                "❌ This command can only be used inside a Modmail ticket."
            )

        if not department:
            return await ctx.send(
                "**Usage:** `.transfer <department>`\n\n"
                "**Supported Departments:**\n"
                "`01` / `1` / `general`\n"
                "`02` / `2` / `partnership`\n"
                "`03` / `3` / `legal`\n"
                "`04` / `4` / `ownership`\n"
                "`05` / `5` / `other`"
            )

        dept = self.normalize_department(department)

        if dept is None:
            return await ctx.send(
                "❌ Invalid department.\n\n"
                "**Usage:** `.transfer <department>`"
            )

        old_dept = self.ticket_departments.get(
            thread.id,
            "05"
        )

        self.ticket_departments[thread.id] = dept

        await self.move_ticket_to_department(
            thread,
            dept
        )

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)

        self.currently_serving.pop(old_dept, None)

        embed = discord.Embed(
            title="🔄 Ticket Transferred",
            description=(
                "Your ticket has been transferred to:\n\n"
                f"**{DEPARTMENTS[dept]}**\n\n"
                "A support agent will assist you shortly."
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

        log_embed = discord.Embed(
            title="📂 Ticket Transferred",
            description=(
                f"Transferred By: {ctx.author.mention}\n"
                f"New Department: **{DEPARTMENTS[dept]}**\n"
                f"Department Code: `{dept}`"
            ),
            color=self.color
        )

        await ctx.send(embed=log_embed)

        await self.update_department_queue(old_dept)
        await self.update_department_queue(dept)

    # ==================================================
    # REQUEST CLOSE
    # ==================================================

    @commands.command(
        name="requestclose",
        aliases=["closerequest"]
    )
    async def request_close(self, ctx):
        thread = await self.bot.threads.find(
            recipient=None,
            channel=ctx.channel
        )

        if thread is None:
            return await ctx.send(
                "❌ This command can only be used "
                "inside a Modmail ticket."
            )

        dept = self.ticket_departments.get(
            thread.id,
            "05"
        )

        class CloseView(View):
            def __init__(self, cog, thread, dept):
                super().__init__(timeout=300)

                self.cog = cog
                self.thread = thread
                self.dept = dept

            @discord.ui.button(
                label="Accept & Close",
                style=discord.ButtonStyle.green
            )
            async def accept(
                self,
                interaction: discord.Interaction,
                button: Button
            ):
                self.cog.claimed_tickets.discard(
                    self.thread.id
                )

                self.cog.ticket_claimers.pop(
                    self.thread.id,
                    None
                )

                self.cog.currently_serving.pop(
                    self.dept,
                    None
                )

                try:
                    await self.thread.close(
                        closer=interaction.user
                    )

                    await self.cog.update_department_queue(
                        self.dept
                    )

                    await interaction.response.send_message(
                        "✅ Ticket closed successfully.",
                        ephemeral=True
                    )

                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to close ticket:\n{e}",
                        ephemeral=True
                    )

                self.stop()

            @discord.ui.button(
                label="Deny & Stay Open",
                style=discord.ButtonStyle.red
            )
            async def deny(
                self,
                interaction: discord.Interaction,
                button: Button
            ):
                await interaction.response.send_message(
                    "❌ Close request denied.",
                    ephemeral=True
                )

                self.stop()

        embed = discord.Embed(
            title="Ticket Close Request",
            description=(
                "A member of the **Ventro Studios** "
                "support team has requested to\n"
                "**close your ticket.**\n\n"

                "=================\n\n"

                f"👤 **Requested By**\n"
                f"{ctx.author.mention} "
                f"— {ctx.author.name}\n\n"

                "=================\n\n"

                "- If your issue persists click "
                "**Deny & Stay Open**\n"

                "- If resolved click "
                "**Accept & Close**\n"

                "- This request expires in 5 minutes.\n\n"

                "=================\n\n"

                "Thank you for choosing "
                "**Ventro Studios.**"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Ventro Studios • This request expires in 5 minutes"
        )

        await thread.recipient.send(
            embed=embed,
            view=CloseView(self, thread, dept)
        )

        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(VentroStudios(bot))
