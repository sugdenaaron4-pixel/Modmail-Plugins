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

        # AI STATE
        self.ai_enabled = {}
        self.ai_cooldowns = {}

    # --------------------
    # AI
    # --------------------
    async def generate_ai_reply(self, department_id, content):

        prompts = {
            "01": (
                "You are a professional airline customer support assistant. "
                "Answer politely and clearly."
            ),

            "02": (
                "You are an airline billing and finance support assistant."
            ),

            "03": (
                "You are a public relations support assistant."
            ),

            "04": (
                "You are a legal and abuse support assistant."
            ),

            "05": (
                "You are a senior management support assistant."
            ),

            "06": (
                "You are a general airline support assistant."
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
            "01": "You have been connected to **General Inquiries**.",
            "02": "You have been connected to **Billing & Finance**.",
            "03": "You have been connected to **Public Relations**.",
            "04": "You have been connected to **Legal & Abuse**.",
            "05": "You have been connected to **Senior Management**.",
            "06": "You have been connected to **Other / Unsure**."
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
                f"Department: **{DEPARTMENTS[department_id]}**"
            ),
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

        active.sort(
            key=lambda t: self.ticket_created_at.get(t.id)
        )

        ids = [t.id for t in active]

        return ids.index(thread_id) + 1 if thread_id in ids else 1

    async def send_queue_update(self, thread, department_id):

        if thread.id in self.claimed_tickets:
            return

        position = await self.get_queue_position(
            thread.id,
            department_id
        )

        ticket_number = self.ticket_numbers.get(thread.id)
        serving = self.currently_serving.get(department_id)

        avg = AVERAGE_HANDLE_TIME.get(department_id, 5)

        min_wait = (position - 1) * avg
        max_wait = position * avg

        embed = discord.Embed(
            title="📋 Queue Update",
            description=(
                f"🎟️ Ticket Number: `{ticket_number}`\n"
                f"📞 Currently Serving: `{serving or 'None'}`\n\n"
                f"Queue Position: `{position}`\n\n"
                f"Estimated Wait:\n"
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

            if self.ticket_departments.get(thread.id) != department_id:
                continue

            try:
                await self.send_queue_update(
                    thread,
                    department_id
                )

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

        self.ticket_created_at[thread.id] = (
            discord.utils.utcnow()
        )

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

        # --------------------
        # CATEGORY SELECT
        # --------------------
        if thread.id not in self.ticket_departments:

            content = message.content.strip().zfill(2)

            if content not in DEPARTMENTS:
                return

            self.ticket_departments[thread.id] = content

            # ENABLE AI
            self.ai_enabled[thread.id] = True

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

            return

        # --------------------
        # AI OFF IF CLAIMED
        # --------------------
        if thread.id in self.claimed_tickets:
            return

        # --------------------
        # AI DISABLED
        # --------------------
        if not self.ai_enabled.get(thread.id):
            return

        # --------------------
        # COOLDOWN
        # --------------------
        last = self.ai_cooldowns.get(thread.id)

        if last:

            diff = discord.utils.utcnow() - last

            if diff.total_seconds() < 8:
                return

        self.ai_cooldowns[thread.id] = (
            discord.utils.utcnow()
        )

        department_id = self.ticket_departments.get(
            thread.id,
            "06"
        )

        async with thread.channel.typing():

            reply = await self.generate_ai_reply(
                department_id,
                message.content
            )

        if len(reply) > 1900:
            reply = reply[:1900]

        await thread.reply(reply)

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

        self.ai_enabled.pop(thread.id, None)
        self.ai_cooldowns.pop(thread.id, None)

        if dept:

            self.currently_serving.pop(dept, None)

            await asyncio.sleep(1)

            await self.update_department_queue(dept)

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
                "❌ This command only works in tickets."
            )

        if thread.id in self.claimed_tickets:

            return await ctx.send(
                "❌ Ticket already claimed."
            )

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.add(thread.id)

        # DISABLE AI
        self.ai_enabled[thread.id] = False

        self.currently_serving[dept] = (
            self.ticket_numbers.get(thread.id)
        )

        await ctx.message.add_reaction("✅")

        embed = discord.Embed(
            title="Support Agent Connected",
            description=(
                f"{ctx.author.mention} has joined the ticket."
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

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
                "⚠️ Ticket is not claimed."
            )

        dept = self.ticket_departments.get(thread.id, "06")

        self.claimed_tickets.discard(thread.id)

        # RE ENABLE AI
        self.ai_enabled[thread.id] = True

        self.currently_serving.pop(dept, None)

        await ctx.send(
            "✅ Ticket returned to queue."
        )

        await self.send_queue_update(thread, dept)

        await self.update_department_queue(dept)


async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
