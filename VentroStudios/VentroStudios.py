import asyncio
import discord
from discord.ext import commands
from discord.ui import View

# ==================================================
# CONFIG
# ==================================================

AWAITING_PLACEMENT_CATEGORY = 1507468762843054160

DEPARTMENT_CATEGORIES = {
    "01": 1502299888770351177,
    "02": 1502299890284367902,
    "03": 1502299891249189025,
    "04": 1502299891249189025,
    "05": 1507468762843054160,
}

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
    "03": 6,
    "04": 30,
    "05": 10,
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

        self.ticket_counter = 0

    # ==================================================
    # NAVIGATION
    # ==================================================

    async def send_navigation_embed(self, thread):

        embed = discord.Embed(
            title="Support Navigation",
            description=(
                "Welcome to **Ventro Studios**.\n\n"
                "Please select the department you require.\n\n"
                "**01** ▸ General Inquiries\n"
                "**02** ▸ Partnership\n"
                "**03** ▸ Legal & Abuse\n"
                "**04** ▸ Ventro Studios Ownership\n"
                "**05** ▸ Other / Unsure\n\n"
                "Reply with 1–5 or 01–05."
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def send_department_embed(self, thread, department_id):

        descriptions = {
            "01": "You have been connected to **General Inquiries**.\n\nA support agent will assist you shortly.",
            "02": "You have been connected to **Partnership Enquiries**.\n\nA PE team member will assist you shortly.",
            "03": "You have been connected to **Legal & Abuse**.\n\nA legal team member will review your case shortly.",
            "04": "You have been connected to **Ventro Studios Ownership**.\n\nAn Ownership Member will be with you shortly.",
            "05": "You have been connected to **Other / Unsure**.\n\nA support agent will direct your ticket shortly."
        }

        embed = discord.Embed(
            title="Department Selected",
            description=descriptions[department_id],
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def send_staff_department_log(self, thread, department_id, user):

        embed = discord.Embed(
            title="📂 Department Selected",
            description=(
                f"User: {user.mention}\n"
                f"Department: **{DEPARTMENTS[department_id]}**\n"
                f"Selection Code: {department_id}"
            ),
            color=self.color
        )

        await thread.channel.send(embed=embed)

    # ==================================================
    # CATEGORY MOVE
    # ==================================================

    async def move_ticket_to_department(self, thread, department_id):

        category_id = DEPARTMENT_CATEGORIES.get(department_id)
        if not category_id:
            return

        try:
            guild = thread.channel.guild
            category = guild.get_channel(category_id)

            if not category:
                return

            await thread.channel.edit(category=category)

        except Exception as e:
            print(f"Failed to move ticket: {e}")

    # ==================================================
    # LISTENERS
    # ==================================================

    @commands.Cog.listener()
    async def on_thread_create(self, thread):

        await asyncio.sleep(1)

        self.ticket_counter += 1
        self.ticket_numbers[thread.id] = self.ticket_counter
        self.ticket_created_at[thread.id] = discord.utils.utcnow()

        try:
            guild = thread.channel.guild
            category = guild.get_channel(AWAITING_PLACEMENT_CATEGORY)

            if category:
                await thread.channel.edit(category=category)

        except Exception as e:
            print(f"Failed to move ticket: {e}")

        await self.send_navigation_embed(thread)

    @commands.Cog.listener()
    async def on_thread_reply(self, thread, from_mod, message, anonymous, plain):

        if from_mod:
            return

        if thread.id in self.ticket_departments:
            return  # already selected

        content = message.content.strip()

        # allow 1 or 01 style input
        if content == "1":
            content = "01"
        elif content == "2":
            content = "02"
        elif content == "3":
            content = "03"
        elif content == "4":
            content = "04"
        elif content == "5":
            content = "05"

        if content not in DEPARTMENTS:
            return

        self.ticket_departments[thread.id] = content

        await self.move_ticket_to_department(thread, content)
        await self.send_department_embed(thread, content)
        await self.send_staff_department_log(thread, content, message.author)

        await asyncio.sleep(1)
        await self.update_department_queue(content)

    @commands.Cog.listener()
    async def on_thread_close(self, thread, *args, **kwargs):

        dept = self.ticket_departments.get(thread.id)

        self.claimed_tickets.discard(thread.id)

        if dept:
            self.currently_serving.pop(dept, None)
            await asyncio.sleep(1)
            await self.update_department_queue(dept)

    # ==================================================
    # CLAIM
    # ==================================================

    @commands.command(name="claim")
    async def claim_ticket(self, ctx):

        thread = await self.bot.threads.find(channel=ctx.channel)

        if not thread:
            return await ctx.send("❌ Must be used in a ticket.")

        if thread.id in self.claimed_tickets:
            return await ctx.send("❌ Already claimed.")

        dept = self.ticket_departments.get(thread.id, "05")

        self.claimed_tickets.add(thread.id)
        self.currently_serving[dept] = self.ticket_numbers.get(thread.id)

        embed = discord.Embed(
            title="🎉 You've Been Connected with a Support Agent",
            description=(
                f"A member of **{DEPARTMENTS[dept]}** has joined.\n\n"
                f"👤 Agent: {ctx.author.mention}"
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)
        await ctx.message.add_reaction("✅")

    # ==================================================
    # UNCLAIM
    # ==================================================

    @commands.command(name="unclaim")
    async def unclaim_ticket(self, ctx):

        thread = await self.bot.threads.find(channel=ctx.channel)

        if not thread:
            return

        if thread.id not in self.claimed_tickets:
            return await ctx.send("⚠️ Not claimed.")

        dept = self.ticket_departments.get(thread.id, "05")

        self.claimed_tickets.discard(thread.id)
        self.currently_serving.pop(dept, None)

        await ctx.send("✅ Unclaimed.")
        await self.send_queue_update(thread, dept)
        await self.update_department_queue(dept)

    # ==================================================
    # TRANSFER
    # ==================================================

    @commands.command(name="transfer")
    async def transfer_ticket(self, ctx, *, department: str = None):

        thread = await self.bot.threads.find(channel=ctx.channel)

        if not thread:
            return await ctx.send("❌ Must be used in a ticket.")

        # ==================================================
        # HELP EMBED
        # ==================================================

        if not department:

            embed = discord.Embed(
                title="📂 Transfer Ticket",
                description=(
                    "Transfer this ticket to another department.\n\n"
                    "**01** ▸ General Inquiries\n"
                    "**02** ▸ Partnership\n"
                    "**03** ▸ Legal & Abuse\n"
                    "**04** ▸ Ventro Studios Ownership\n"
                    "**05** ▸ Other / Unsure\n\n"
                    "Usage:\n"
                    "`.transfer 01`\n"
                    "`.transfer 1`\n"
                    "`.transfer General`\n"
                    "`.transfer Partnership`"
                ),
                color=self.color
            )

            return await ctx.send(embed=embed)

        # ==================================================
        # ALIASES
        # ==================================================

        department = department.lower().strip()

        aliases = {

            # 01
            "1": "01",
            "01": "01",
            "general": "01",
            "general inquiries": "01",
            "inquiries": "01",

            # 02
            "2": "02",
            "02": "02",
            "partnership": "02",
            "partnerships": "02",

            # 03
            "3": "03",
            "03": "03",
            "legal": "03",
            "abuse": "03",
            "legal & abuse": "03",

            # 04
            "4": "04",
            "04": "04",
            "ownership": "04",
            "ventro studios ownership": "04",

            # 05
            "5": "05",
            "05": "05",
            "other": "05",
            "unsure": "05",
            "other / unsure": "05",
        }

        department_id = aliases.get(department)

        if not department_id:
            return await ctx.send("❌ Invalid department.")

        old_department = self.ticket_departments.get(thread.id, "05")

        # ==================================================
        # UPDATE DATA
        # ==================================================

        self.ticket_departments[thread.id] = department_id

        self.claimed_tickets.discard(thread.id)
        self.currently_serving.pop(old_department, None)

        # ==================================================
        # MOVE CATEGORY
        # ==================================================

        await self.move_ticket_to_department(thread, department_id)

        # ==================================================
        # USER EMBED
        # ==================================================

        descriptions = {
            "01": "Your ticket has been transferred to **General Inquiries**.\n\nA support agent will assist you shortly.",
            "02": "Your ticket has been transferred to **Partnership Enquiries**.\n\nA PE team member will assist you shortly.",
            "03": "Your ticket has been transferred to **Legal & Abuse**.\n\nA legal team member will review your case shortly.",
            "04": "Your ticket has been transferred to **Ventro Studios Ownership**.\n\nAn Ownership Member will be with you shortly.",
            "05": "Your ticket has been transferred to **Other / Unsure**.\n\nA support agent will direct your ticket shortly."
        }

        embed = discord.Embed(
            title="📂 Ticket Transferred",
            description=descriptions[department_id],
            color=self.color
        )

        await thread.recipient.send(embed=embed)

        # ==================================================
        # STAFF EMBED
        # ==================================================

        embed = discord.Embed(
            title="🔄 Ticket Transferred",
            description=(
                f"Transferred By: {ctx.author.mention}\n"
                f"Department: **{DEPARTMENTS[department_id]}**\n"
                f"Transfer Code: {department_id}"
            ),
            color=self.color
        )

        await ctx.send(embed=embed)

        # ==================================================
        # UPDATE QUEUE
        # ==================================================

        await asyncio.sleep(1)

        await self.update_department_queue(old_department)
        await self.update_department_queue(department_id)

    # ==================================================
    # REQUEST CLOSE
    # ==================================================

    @commands.command(name="requestclose")
    async def request_close(self, ctx):

        thread = await self.bot.threads.find(channel=ctx.channel)

        if not thread:
            return await ctx.send("❌ Must be in ticket.")

        dept = self.ticket_departments.get(thread.id, "05")

        await thread.recipient.send(
            embed=discord.Embed(
                title="Ticket Close Request",
                description=f"Requested by {ctx.author.mention}",
                color=self.color
            )
        )


async def setup(bot):
    await bot.add_cog(VentroStudios(bot))
