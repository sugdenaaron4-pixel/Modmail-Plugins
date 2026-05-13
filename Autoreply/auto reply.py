import asyncio
from collections import defaultdict

import discord
from discord.ext import commands

DEPARTMENTS = {
    "01": {
        "name": "General Inquiries",
        "description": "General questions about our services\nPre sales enquiries\nBasic information requests",
        "wait": None
    },
    "02": {
        "name": "Billing & Finance",
        "description": "Billing questions\nRefund requests\nPayment issues",
        "wait": None
    },
    "03": {
        "name": "Public Relations",
        "description": "Partnership enquiries\nMedia requests\nPublic relations support",
        "wait": None
    },
    "04": {
        "name": "Legal & Abuse",
        "description": "Legal reports\nAbuse complaints\nTerms of service violations",
        "wait": None
    },
    "05": {
        "name": "Senior Management",
        "description": "Escalated concerns\nManagement review requests",
        "wait": "12 to 48 hours"
    },
    "06": {
        "name": "Other / Unsure",
        "description": "General assistance for unclear or uncategorized issues",
        "wait": None
    }
}


class Jet2Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xe02e2e

        self.ticket_departments = {}
        self.claimed_tickets = set()
        self.claim_messages_sent = set()

    async def send_navigation_embed(self, thread):
        embed = discord.Embed(
            title="ᴀ Support Navigation",
            description=(
                "Welcome to **Jet2Support**. To ensure your inquiry is handled by "
                "the appropriate specialist, please identify your department "
                "from the options below.\n\n"
                "**01** ▸ General Inquiries\n"
                "**02** ▸ Billing & Finance\n"
                "**03** ▸ Public Relations\n"
                "**04** ▸ Legal & Abuse\n"
                "**05** ▸ Senior Management\n"
                "**06** ▸ Other / Unsure\n\n"
                "Reply with a number to be connected to the correct department."
            ),
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def send_department_embed(self, thread, department_id):
        data = DEPARTMENTS[department_id]

        desc = (
            f"Thank you for reaching out to **Jet2Support**.\n"
            f"You have been directed to our **{data['name']}** department.\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🔵 **This Department Handles:**\n"
            f"◇ {data['description'].replace(chr(10), chr(10) + '◇ ')}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
        )

        if data["wait"]:
            desc += f"⏳ **Estimated Wait Time:** {data['wait']}\n\n"

        desc += (
            "A member of our support team will be with you as soon as possible.\n"
            "Please provide as much detail as possible regarding your issue."
        )

        embed = discord.Embed(
            title=f"ᴀ You have selected {data['name']}",
            description=desc,
            color=self.color
        )

        await thread.recipient.send(embed=embed)

    async def get_queue_position(self, thread_id, department_id):
        open_threads = []

        for thread in self.bot.threads.cache.values():
            if getattr(thread, "closed", False):
                continue

            if thread.id in self.claimed_tickets:
                continue

            if self.ticket_departments.get(thread.id) != department_id:
                continue

            open_threads.append(thread.id)

        open_threads.sort()

        try:
            return open_threads.index(thread_id) + 1
        except ValueError:
            return 1

    async def send_queue_update(self, thread, department_id):
        if thread.id in self.claimed_tickets:
            return

        position = await self.get_queue_position(thread.id, department_id)

        suffix = "th"
        if position == 1:
            suffix = "st"
        elif position == 2:
            suffix = "nd"
        elif position == 3:
            suffix = "rd"

        embed = discord.Embed(
            title="📋 Your Queue Position",
            description=(
                f"`{position}{suffix} in queue`\n\n"
                "Jet2Support • Reply to this ticket to continue"
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
            except Exception:
                pass

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

        content = message.content.strip()

        if content not in DEPARTMENTS:
            return

        self.ticket_departments[thread.id] = content

        await self.send_department_embed(thread, content)
        await self.update_department_queue(content)

    @commands.Cog.listener()
    async def on_thread_close(self, thread, closer, silent, delete_channel):
        department_id = self.ticket_departments.get(thread.id)

        if department_id:
            await asyncio.sleep(2)
            await self.update_department_queue(department_id)

    @commands.Cog.listener()
    async def on_thread_claim(self, thread, user):
        if thread.id in self.claim_messages_sent:
            return

        self.claimed_tickets.add(thread.id)
        self.claim_messages_sent.add(thread.id)

        embed = discord.Embed(
            title="ᴀ You've Been Connected with a Support Agent",
            description=(
                "Great news. A member of the **Jet2Support** support team "
                "has joined your ticket.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **Your Support Agent**\n"
                f"{user.mention} , `{user}`\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "◇ Your agent is reviewing your issue now and will respond shortly.\n"
                "◇ Please feel free to provide any additional information."
            ),
            color=self.color
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        try:
            await thread.recipient.send(embed=embed)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
