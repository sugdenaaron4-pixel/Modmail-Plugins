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

class Jet2Support(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.color = 0xe02e2e  # RED THEME
        self.ticket_departments = {}
        self.claimed_tickets = set()
        self.claim_messages_sent = set()

    # --------------------
    # Navigation & Department
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
        if department_id not in descriptions:
            return
        embed = discord.Embed(title="ᴀ Department Selected", description=descriptions[department_id], color=self.color)
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
        # Sort by oldest ticket first
        active.sort(key=lambda t: t.channel.created_at)
        try:
            ids = [t.id for t in active]
            return ids.index(thread_id) + 1
        except ValueError:
            return 1

    async def send_queue_update(self, thread, department_id):
        if thread.id in self.claimed_tickets:
            return
        position = await self.get_queue_position(thread.id, department_id)
        suffix = "th" if position > 3 else ["st", "nd", "rd"][position-1]
        embed = discord.Embed(
            title="📋 Queue Update",
            description=f"You are currently **{position}{suffix}** in the **{DEPARTMENTS[department_id]}** queue.",
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
            except Exception:
                pass

    # --------------------
    # Listeners
    # --------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await asyncio.sleep(1)
        await self.send_navigation_embed(thread)

    @commands.Cog.listener()
    async def on_thread_reply(self, thread, from_mod, message, anonymous, plain):
        if from_mod:
            return
        if thread.id in self.ticket_departments:
            return
        content = message.content.strip().zfill(2)
        if content not in DEPARTMENTS:
            return
        self.ticket_departments[thread.id] = content
        await self.send_department_embed(thread, content)
        await self.send_staff_department_log(thread, content, message.author)
        await asyncio.sleep(1)
        await self.update_department_queue(content)

    @commands.Cog.listener()
    async def on_thread_close(self, thread, closer, silent, delete_channel):
        department_id = self.ticket_departments.get(thread.id)
        if department_id:
            await asyncio.sleep(2)
            await self.update_department_queue(department_id)

    # --------------------
    # Commands
    # --------------------
    @commands.command(name="claim")
    async def claim_ticket(self, ctx):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)
        if thread is None:
            await ctx.send("❌ This command can only be used inside a Modmail ticket.")
            return
        if thread.id in self.claim_messages_sent:
            await ctx.message.add_reaction("⚠️")
            return
        department_id = self.ticket_departments.get(thread.id, "06")
        self.claimed_tickets.add(thread.id)
        self.claim_messages_sent.add(thread.id)
        embed = discord.Embed(
            title="🎉 You've Been Connected with a Support Agent",
            description=(
                f"Great news! A member of the **{DEPARTMENTS[department_id]}** support team has joined your ticket.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **Your Support Agent**\n{ctx.author.mention} — `{ctx.author.name}`\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "◈ Your agent is reviewing your issue now and will respond shortly.\n"
                "◈ Please feel free to provide any additional information that may help.\n"
                "◈ If you have screenshots or logs, you are welcome to share them here.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "Thank you for your patience.\n"
                "> <:Jet2_Holidays:1501627858358112306> Package Holidays, You can Trust"
            ),
            color=self.color
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Jet2Support • Support Team Connected")
        try:
            await thread.recipient.send(embed=embed)
            await ctx.message.add_reaction("✅")
            await self.update_department_queue(department_id)
        except Exception as e:
            await ctx.send(f"❌ Failed to send claim message:\n```{e}```")

    @commands.command(name="transfer")
    async def transfer_ticket(self, ctx, department_id: str = None):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)
        if thread is None:
            await ctx.send("❌ This command can only be used inside a Modmail ticket.")
            return
        if department_id is None:
            embed = discord.Embed(
                title="📂 Transfer Ticket",
                description=(
                    "Select a department using:\n`.transfer <department>`\n\n"
                    "**01** ▸ General Inquiries\n"
                    "**02** ▸ Billing & Finance\n"
                    "**03** ▸ Public Relations\n"
                    "**04** ▸ Legal & Abuse\n"
                    "**05** ▸ Senior Management\n"
                    "**06** ▸ Other / Unsure"
                ),
                color=self.color
            )
            await ctx.send(embed=embed)
            return
        department_id = department_id.strip().zfill(2)
        if department_id not in DEPARTMENTS:
            await ctx.send("❌ Invalid department number.")
            return
        old_department = self.ticket_departments.get(thread.id, "06")
        self.ticket_departments[thread.id] = department_id
        self.claimed_tickets.discard(thread.id)
        self.claim_messages_sent.discard(thread.id)
        user_embed = discord.Embed(
            title="📂 Ticket Transferred",
            description=f"Your ticket has been transferred to:\n\n**{DEPARTMENTS[department_id]}**\n\nA new support agent will assist you shortly.",
            color=self.color
        )
        staff_embed = discord.Embed(
            title="✅ Ticket Transferred",
            description=f"Transferred from:\n**{DEPARTMENTS[old_department]}**\n\nTransferred to:\n**{DEPARTMENTS[department_id]}**",
            color=self.color
        )
        try:
            await thread.recipient.send(embed=user_embed)
        except:
            pass
        await ctx.send(embed=staff_embed)
        await self.update_department_queue(old_department)
        await self.update_department_queue(department_id)

    # --------------------
    # Request Close with Buttons
    # --------------------
    @commands.command(name="requestclose", aliases=["closerequest"])
    async def request_close(self, ctx):
        thread = await self.bot.threads.find(recipient=None, channel=ctx.channel)
        if thread is None:
            await ctx.send("❌ This command can only be used inside a Modmail ticket.")
            return

        class CloseRequestView(View):
            def __init__(self, timeout=300):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Accept & Close", style=discord.ButtonStyle.green)
            async def accept(self, interaction: discord.Interaction, button: Button):
                await interaction.response.send_message("✅ Ticket closed. Thank you!", ephemeral=True)
                await thread.close()
                self.stop()  # Stop the view

            @discord.ui.button(label="Deny & Stay Open", style=discord.ButtonStyle.red)
            async def deny(self, interaction: discord.Interaction, button: Button):
                await interaction.response.send_message("❌ Close request denied. Ticket remains open.", ephemeral=True)
                self.stop()  # Stop the view

        embed = discord.Embed(
            title="ᴀ Ticket Close Request",
            description=(
                "A member of the **Jet2Support** support team has requested to\n**close your ticket.**\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **Requested By**\n{ctx.author.mention} — `{ctx.author.name}`\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "◈ If your issue has been **fully resolved**, click **Accept & Close.**\n"
                "◈ If you still need assistance, click **Deny & Stay Open.**\n"
                "◈ No action needed if you'd like more time — the request will expire after 5 minutes.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "Thank you for choosing **Jet2Support.**"
            ),
            color=self.color
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Jet2Support • This request expires in 5 minutes")
        try:
            await thread.recipient.send(embed=embed, view=CloseRequestView())
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(f"❌ Failed to send close request:\n```{e}```")

async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
