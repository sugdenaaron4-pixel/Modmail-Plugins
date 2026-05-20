import asyncio
import os
import discord

from openai import AsyncOpenAI
from discord.ext import commands
from discord.ui import View, Button

ai_client = AsyncOpenAI(
    api_key="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"
)

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

        # AI
        self.ai_enabled = {}
        self.ai_cooldowns = {}

    # --------------------
    # AI
    # --------------------
    async def generate_ai_reply(
        self,
        department_id,
        content
    ):

        prompts = {

            "01": (
                "You are a professional airline "
                "customer support assistant."
            ),

            "02": (
                "You are a billing and finance "
                "support assistant."
            ),

            "03": (
                "You are a PR support assistant."
            ),

            "04": (
                "You are a legal and abuse "
                "support assistant."
            ),

            "05": (
                "You are a senior management "
                "support assistant."
            ),

            "06": (
                "You are a general airline "
                "support assistant."
            )
        }

        system_prompt = prompts.get(
            department_id,
            prompts["06"]
        )

        try:

            response = await ai_client.chat.completions.create(

                model="gpt-4.1-mini",

                messages=[

                    {
                        "role": "system",
                        "content": system_prompt
                    },

                    {
                        "role": "user",
                        "content": content
                    }
                ],

                max_tokens=300,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:

            return f"AI Error: {e}"

    # --------------------
    # Navigation
    # --------------------
    async def send_navigation_embed(
        self,
        thread
    ):

        embed = discord.Embed(

            title="ᴀ Support Navigation",

            description=(

                "Welcome to **Jet2Support**.\n\n"

                "Please select the department "
                "you require.\n\n"

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

    async def send_department_embed(
        self,
        thread,
        department_id
    ):

        descriptions = {

            "01": (
                "You have been connected to "
                "**General Inquiries**."
            ),

            "02": (
                "You have been connected to "
                "**Billing & Finance**."
            ),

            "03": (
                "You have been connected to "
                "**Public Relations**."
            ),

            "04": (
                "You have been connected to "
                "**Legal & Abuse**."
            ),

            "05": (
                "You have been connected to "
                "**Senior Management**."
            ),

            "06": (
                "You have been connected to "
                "**Other / Unsure**."
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
                f"Selection Code: `{department_id}`"
            ),

            color=self.color
        )

        await thread.channel.send(embed=embed)

    # --------------------
    # Queue
    # --------------------
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

            if (
                self.ticket_departments.get(thread.id)
                != department_id
            ):
                continue

            active.append(thread)

        active.sort(
            key=lambda t:
            self.ticket_created_at.get(t.id)
        )

        ids = [t.id for t in active]

        return (
            ids.index(thread_id) + 1
            if thread_id in ids else 1
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

        ticket_number = self.ticket_numbers.get(
            thread.id
        )

        serving = self.currently_serving.get(
            department_id
        )

        avg = AVERAGE_HANDLE_TIME.get(
            department_id,
            5
        )

        min_wait = (position - 1) * avg
        max_wait = position * avg

        embed = discord.Embed(

            title="📋 Queue Update",

            description=(

                f"🎟️ Ticket Number: "
                f"`{ticket_number}`\n"

                f"📞 Currently Serving: "
                f"`{serving or 'None'}`\n\n"

                f"Queue Position: "
                f"`{position}`\n\n"

                f"Estimated Wait:\n"
                f"**{min_wait} - "
                f"{max_wait} minutes**"
            ),

            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def update_department_queue(
        self,
        department_id
    ):

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

            except:
                pass

    # --------------------
    # THREAD CREATE
    # --------------------
    @commands.Cog.listener()
    async def on_thread_create(
        self,
        thread
    ):

        await asyncio.sleep(1)

        self.ticket_counter += 1

        self.ticket_numbers[thread.id] = (
            self.ticket_counter
        )

        self.ticket_created_at[thread.id] = (
            discord.utils.utcnow()
        )

        await self.send_navigation_embed(thread)

    # --------------------
    # CATEGORY SELECT
    # --------------------
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

        self.ai_enabled[thread.id] = True

        ai_embed = discord.Embed(

            title="🤖 Connected to AI Support Agent",

            description=(

                "You are now connected to the "
                "**Jet2 AI Support System**.\n\n"

                "An AI assistant will attempt "
                "to help you before a human "
                "agent joins.\n\n"

                "If a staff member claims "
                "the ticket, AI responses "
                "will automatically stop."
            ),

            color=self.color
        )

        await thread.recipient.send(embed=ai_embed)

        staff_embed = discord.Embed(

            title="🤖 AI Support Activated",

            description=(

                f"AI support has been enabled "
                f"for {message.author.mention}\n\n"

                f"Department:\n"
                f"**{DEPARTMENTS[content]}**"
            ),

            color=self.color
        )

        await thread.channel.send(embed=staff_embed)

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

        await self.update_department_queue(
            content
        )

    # --------------------
    # AI REPLIES
    # --------------------
    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        if message.author.bot:
            return

        if message.guild is not None:
            return

        thread = await self.bot.threads.find(
            recipient=message.author
        )

        if thread is None:
            return

        if thread.id not in self.ticket_departments:
            return

        if thread.id in self.claimed_tickets:
            return

        if not self.ai_enabled.get(thread.id):
            return

        content = message.content.strip().zfill(2)

        if content in DEPARTMENTS:
            return

        last = self.ai_cooldowns.get(thread.id)

        if last:

            diff = (
                discord.utils.utcnow() - last
            )

            if diff.total_seconds() < 8:
                return

        self.ai_cooldowns[thread.id] = (
            discord.utils.utcnow()
        )

        department_id = (
            self.ticket_departments.get(
                thread.id,
                "06"
            )
        )

        async with thread.channel.typing():

            reply = await self.generate_ai_reply(
                department_id,
                message.content
            )

        if len(reply) > 1900:
            reply = reply[:1900]

        await thread.reply(reply)

        embed = discord.Embed(
            title="🤖 AI Response",
            description=reply,
            color=self.color
        )

        await thread.channel.send(embed=embed)

    # --------------------
    # THREAD CLOSE
    # --------------------
    @commands.Cog.listener()
    async def on_thread_close(
        self,
        thread,
        closer,
        silent,
        delete_channel
    ):

        dept = self.ticket_departments.get(
            thread.id
        )

        self.claimed_tickets.discard(
            thread.id
        )

        self.ai_enabled.pop(
            thread.id,
            None
        )

        self.ai_cooldowns.pop(
            thread.id,
            None
        )

        if dept:

            self.currently_serving.pop(
                dept,
                None
            )

            await asyncio.sleep(1)

            await self.update_department_queue(
                dept
            )

    # --------------------
    # CLAIM
    # --------------------
    @commands.command(name="claim")
    async def claim_ticket(self, ctx):

        thread = await self.bot.threads.find(
            recipient=None,
            channel=ctx.channel
        )

        if thread is None:
            return await ctx.send(
                "❌ This command can only be used inside a Modmail ticket."
            )

        if thread.id in self.claimed_tickets:
            return await ctx.send(
                "❌ This ticket is already claimed by another support agent."
            )

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.add(thread.id)

        self.ai_enabled[thread.id] = False

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
                f"{ctx.author.mention} — "
                f"`{ctx.author.name}`\n\n"

                "=================\n\n"

                "- The agent will review your issue.\n"
                "- Please provide screenshots if possible.\n"
                "- Provide more info if requested.\n"
                "- You may request another agent if needed.\n\n"

                "=================\n\n"

                "🤖 AI support has now been disabled.\n\n"

                "Thank you for Choosing Jet2.\n"
                "> <:Jet2_Holidays:1501627858358112306> "
                "Package Holidays, You can Trust"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Jet2Support • Support Team Connected"
        )

        await thread.recipient.send(embed=embed)

        await ctx.message.add_reaction("✅")

        await self.update_department_queue(dept)

    # --------------------
    # UNCLAIM
    # --------------------
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

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.discard(thread.id)

        self.ai_enabled[thread.id] = True

        self.currently_serving.pop(dept, None)

        embed = discord.Embed(
            title="🔄 Ticket Update",
            description=(
                f"The Agent from the "
                f"**{DEPARTMENTS[dept]}** support team "
                f"has unclaimed your ticket.\n\n"

                "=================\n\n"

                f"👤 **Previous Support Agent**\n"
                f"{ctx.author.mention} — "
                f"`{ctx.author.name}`\n\n"

                "=================\n\n"

                "- Your ticket has been returned to the queue.\n"
                "- A new support agent will assist you shortly.\n"
                "- AI support has been re enabled.\n"
                "- You may be asked to re explain your issue.\n\n"

                "=================\n\n"

                "Thank you for your patience.\n"
                "> <:Jet2_Holidays:1501627858358112306> "
                "Package Holidays, You can Trust"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Jet2Support • Ticket Reassigned"
        )

        await thread.recipient.send(embed=embed)

        await ctx.send(
            "✅ Ticket unclaimed and returned to queue."
        )

        await self.send_queue_update(
            thread,
            dept
        )

        await self.update_department_queue(dept)

    # --------------------
    # REQUEST CLOSE
    # --------------------
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
                "❌ This command can only be used inside a Modmail ticket."
            )

        dept = self.ticket_departments.get(
            thread.id,
            "06"
        )

        class CloseView(View):

            def __init__(
                self,
                cog,
                thread,
                dept
            ):

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
                        f"❌ Failed to close ticket:\n```{e}```",
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
                "A member of the "
                "**Jet2Support** support team "
                "has requested to\n"
                "**close your ticket.**\n\n"

                "=================\n\n"

                f"👤 **Requested By**\n"
                f"{ctx.author.mention} — "
                f"`{ctx.author.name}`\n\n"

                "=================\n\n"

                "- If your issue persists click "
                "**Deny & Stay Open**\n"

                "- If resolved click "
                "**Accept & Close**\n"

                "- This request expires in "
                "5 minutes.\n\n"

                "=================\n\n"

                "Thank you for choosing "
                "**Jet2Support.**"
            ),
            color=self.color
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Jet2Support • This request expires in 5 minutes"
        )

        await thread.recipient.send(
            embed=embed,
            view=CloseView(self, thread, dept)
        )

        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
