import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button

DEPARTMENTS = {
    "01": "General Inquiries",
    "02": "Billing & Finance",
    "03": "Public Relations",
    "04": "Legal & Abuse",
    "05": "Senior Management",
    "06": "Other / Unsure"
}

AVERAGE_HANDLE_TIME = {
    "01": 5,
    "02": 8,
    "03": 6,
    "04": 10,
    "05": 30,
    "06": 7
}

class Jet2Support(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xe02e2e

        self.ticket_departments = {}
        self.claimed_tickets = set()

        self.ticket_created_at = {}
        self.ticket_counter = 0
        self.ticket_numbers = {}
        self.currently_serving = {}

    # --------------------
    # Navigation
    # --------------------
    async def send_navigation_embed(self, thread):
        embed = discord.Embed(
            title="ᴀ Support Navigation",
            description=(
                "Welcome to **Jet2Support**.\n\n"
                "Please select the department you require.\n\n"
                "**01** ▸ General Inquiries\n"
                "**02** ▸ Billing & Finance\n"
                "**03** ▸ Public Relations\n"
                "**04** ▸ Legal & Abuse\n"
                "**05** ▸ Senior Management\n"
                "**06** ▸ Other / Unsure\n\n"
                "Reply with the number only."
            ),
            color=self.color
        )
        await thread.recipient.send(embed=embed)

    async def send_department_embed(self, thread, department_id):
        descriptions = {
            "01": "You have been connected to **General Inquiries**.\n\nA support agent will assist you shortly.",
            "02": "You have been connected to **Billing & Finance**.\n\nA finance team member will assist you shortly.",
            "03": "You have been connected to **Public Relations**.\n\nA PR team member will assist you shortly.",
            "04": "You have been connected to **Legal & Abuse**.\n\nA legal team member will review your case shortly.",
            "05": "You have been connected to **Senior Management**.\n\nEstimated wait time:\n**12 to 48 hours**.",
            "06": "You have been connected to **Other / Unsure**.\n\nA support agent will direct your ticket shortly."
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
            description=f"User: {user.mention}\nDepartment: **{DEPARTMENTS[department_id]}**\nSelection Code: `{department_id}`",
            color=self.color
        )
        await thread.channel.send(embed=embed)

    # --------------------
    # Queue System
    # --------------------
    async def get_queue_position(self, thread_id, department_id):
        active = []

        for thread in self.bot.threads.cache.values():
            if getattr(thread, "closed", False):
                continue
            if thread.id in self.claimed_tickets:
                continue
            if self.ticket_departments.get(thread.id) != department_id:
                continue
            active.append(thread)

        active.sort(key=lambda t: self.ticket_created_at.get(t.id))

        ids = [t.id for t in active]
        return ids.index(thread_id) + 1 if thread_id in ids else 1

    async def send_queue_update(self, thread, department_id):
        if thread.id in self.claimed_tickets:
            return

        position = await self.get_queue_position(thread.id, department_id)
        ticket_number = self.ticket_numbers.get(thread.id)
        serving = self.currently_serving.get(department_id)

        if 10 <= position % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")

        avg = AVERAGE_HANDLE_TIME.get(department_id, 5)
        min_wait = (position - 1) * avg
        max_wait = position * avg

        embed = discord.Embed(
            title="📋 Queue Update",
            description=(
                f"🎟️ **Your Ticket Number:** `{ticket_number}`\n"
                f"📞 **Currently Serving:** `{serving or 'None'}`\n\n"
                f"You are currently **{position}{suffix}** in the **{DEPARTMENTS[department_id]}** queue.\n\n"
                f"⏱️ Estimated Wait Time:\n**{min_wait} - {max_wait} minutes**"
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
            if self.ticket_departments.get(thread.id) != department_id:
                continue
            try:
                await self.send_queue_update(thread, department_id)
            except:
                pass

    # --------------------
    # Listeners
    # --------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await asyncio.sleep(1)

        self.ticket_counter += 1
        self.ticket_numbers[thread.id] = self.ticket_counter
        self.ticket_created_at[thread.id] = discord.utils.utcnow()

        await self.send_navigation_embed(thread)

    @commands.Cog.listener()
    async def on_thread_reply(self, thread, from_mod, message, anonymous, plain):
        if from_mod or thread.id in self.ticket_departments:
            return

        content = message.content.strip().zfill(2)
        if content not in DEPARTMENTS:
            return

        self.ticket_departments[thread.id] = content

        await self.send_department_embed(thread, content)
        await self.send_staff_department_log(thread, content, message.author)

        await asyncio.sleep(1)
        await self.update_department_queue(content)

    # --------------------
    # CLAIM
    # --------------------
    @commands.command(name="claim")
    async def claim_ticket(self, ctx):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)

        if thread is None:
            return await ctx.send("❌ This command can only be used inside a Modmail ticket.")

        if thread.id in self.claimed_tickets:
            return await ctx.send("❌ This ticket is already claimed by another support agent.")

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.add(thread.id)
        self.currently_serving[dept] = self.ticket_numbers.get(thread.id)

        embed = discord.Embed(
            title="🎉 You've Been Connected with a Support Agent",
            description=(
                f"Great news! A member of the **{DEPARTMENTS[dept]}** support team has joined your ticket.\n\n"
                "=================\n\n"
                f"👤 **Your Support Agent**\n{ctx.author.mention} — `{ctx.author.name}`\n\n"
                "=================\n\n"
                "- The agent will review your issue.\n"
                "- Please provide screenshots if possible.\n"
                "- Provide more info if requested.\n"
                "- You may request another agent if needed.\n\n"
                "=================\n\n"
                "Thank you for Choosing Jet2.\n"
                "> <:Jet2_Holidays:1501627858358112306> Package Holidays, You can Trust"
            ),
            color=self.color
        )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Jet2Support • Support Team Connected")

        await thread.recipient.send(embed=embed)
        await ctx.message.add_reaction("✅")

        await self.update_department_queue(dept)

    # --------------------
    # UNCLAIM
    # --------------------
    @commands.command(name="unclaim")
    async def unclaim_ticket(self, ctx):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)

        if thread is None:
            return

        if thread.id not in self.claimed_tickets:
            return await ctx.send("⚠️ This ticket is not currently claimed.")

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.discard(thread.id)
        self.currently_serving.pop(dept, None)

        embed = discord.Embed(
            title="🔄 Ticket Update",
            description=(
                f"The Agent from the **{DEPARTMENTS[dept]}** support team has unclaimed your ticket.\n\n"
                "=================\n\n"
                f"👤 **Previous Support Agent**\n{ctx.author.mention} — `{ctx.author.name}`\n\n"
                "=================\n\n"
                "- Your ticket has been returned to the queue.\n"
                "- A new support agent will assist you shortly.\n"
                "- You may be asked to re-explain your issue.\n"
                "- Please provide any additional details if needed.\n\n"
                "=================\n\n"
                "Thank you for your patience.\n"
                "> <:Jet2_Holidays:1501627858358112306> Package Holidays, You can Trust"
            ),
            color=self.color
        )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Jet2Support • Ticket Reassigned")

        await thread.recipient.send(embed=embed)
        await ctx.send("✅ Ticket unclaimed and returned to queue.")

        # 🔥 INSTANT QUEUE UPDATE (new)
        await self.send_queue_update(thread, dept)

        await self.update_department_queue(dept)

    # --------------------
    # REQUEST CLOSE
    # --------------------
    @commands.command(name="requestclose", aliases=["closerequest"])
    async def request_close(self, ctx):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)

        if thread is None:
            return await ctx.send("❌ This command can only be used inside a Modmail ticket.")

        class CloseView(View):
            @discord.ui.button(label="Accept & Close", style=discord.ButtonStyle.green)
            async def accept(self, i, b):
                await thread.close()
                await i.response.send_message("Closed.", ephemeral=True)

            @discord.ui.button(label="Deny & Stay Open", style=discord.ButtonStyle.red)
            async def deny(self, i, b):
                await i.response.send_message("Stayed open.", ephemeral=True)

        embed = discord.Embed(
            title="Ticket Close Request",
            description=(
                "A member of the **Jet2Support** support team has requested to\n"
                "**close your ticket.**\n\n"
                "=================\n\n"
                f"👤 **Requested By**\n{ctx.author.mention} — `{ctx.author.name}`\n\n"
                "=================\n\n"
                "- If your issue persists click **Deny & Stay Open**\n"
                "- If resolved click **Accept & Close**\n"
                "- This request expires in 5 minutes.\n\n"
                "=================\n\n"
                "Thank you for choosing **Jet2Support.**"
            ),
            color=self.color
        )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Jet2Support • This request expires in 5 minutes")

        await thread.recipient.send(embed=embed, view=CloseView())
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
