import asyncio

import discord
from discord.ext import commands

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
        self.color = 0xe02e2e

        self.ticket_departments = {}
        self.claimed_tickets = set()
        self.claim_messages_sent = set()

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

    async def send_department_embed(
        self,
        thread,
        department_id
    ):

        if department_id == "01":

            description = (
                "You have been connected to "
                "**General Inquiries**.\n\n"
                "A support agent will assist "
                "you shortly."
            )

        elif department_id == "02":

            description = (
                "You have been connected to "
                "**Billing & Finance**.\n\n"
                "A finance team member will "
                "assist you shortly."
            )

        elif department_id == "03":

            description = (
                "You have been connected to "
                "**Public Relations**.\n\n"
                "A PR team member will "
                "assist you shortly."
            )

        elif department_id == "04":

            description = (
                "You have been connected to "
                "**Legal & Abuse**.\n\n"
                "A legal team member will "
                "review your case shortly."
            )

        elif department_id == "05":

            description = (
                "You have been connected to "
                "**Senior Management**.\n\n"
                "Estimated wait time:\n"
                "**12 to 48 hours**."
            )

        elif department_id == "06":

            description = (
                "You have been connected to "
                "**Other / Unsure**.\n\n"
                "A support agent will "
                "direct your ticket shortly."
            )

        else:
            return

        embed = discord.Embed(
            title="ᴀ Department Selected",
            description=description,
            color=self.color
        )

        await thread.recipient.send(
            embed=embed
        )

    async def send_staff_department_log(
        self,
        thread,
        department_id,
        user
    ):

        channel = thread.channel

        embed = discord.Embed(
            title="📂 Department Selected",
            description=(
                f"User: {user.mention}\n"
                f"Department: "
                f"**{DEPARTMENTS[department_id]}**\n"
                f"Selection Code: "
                f"`{department_id}`"
            ),
            color=self.color
        )

        await channel.send(
            embed=embed
        )

    async def get_queue_position(
        self,
        thread_id,
        department_id
    ):

        active = []

        for thread in self.bot.threads.cache.values():

            if getattr(
                thread,
                "closed",
                False
            ):
                continue

            if thread.id in self.claimed_tickets:
                continue

            if self.ticket_departments.get(
                thread.id
            ) != department_id:
                continue

            active.append(thread.id)

        active.sort()

        try:
            return (
                active.index(thread_id) + 1
            )

        except ValueError:
            return 1

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

        suffix = "th"

        if position == 1:
            suffix = "st"

        elif position == 2:
            suffix = "nd"

        elif position == 3:
            suffix = "rd"

        embed = discord.Embed(
            title="📋 Queue Update",
            description=(
                f"You are currently "
                f"**{position}{suffix}** "
                f"in the "
                f"**{DEPARTMENTS[department_id]}** "
                f"queue."
            ),
            color=self.color
        )

        await thread.recipient.send(
            embed=embed
        )

    async def update_department_queue(
        self,
        department_id
    ):

        for thread in self.bot.threads.cache.values():

            if getattr(
                thread,
                "closed",
                False
            ):
                continue

            if thread.id in self.claimed_tickets:
                continue

            if self.ticket_departments.get(
                thread.id
            ) != department_id:
                continue

            try:

                await self.send_queue_update(
                    thread,
                    department_id
                )

            except Exception:
                pass

    @commands.Cog.listener()
    async def on_thread_create(
        self,
        thread
    ):

        await asyncio.sleep(1)

        await self.send_navigation_embed(
            thread
        )

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

        content = (
            message.content
            .strip()
            .zfill(2)
        )

        if content not in DEPARTMENTS:
            return

        self.ticket_departments[
            thread.id
        ] = content

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

    @commands.Cog.listener()
    async def on_thread_close(
        self,
        thread,
        closer,
        silent,
        delete_channel
    ):

        department_id = (
            self.ticket_departments.get(
                thread.id
            )
        )

        if department_id:

            await asyncio.sleep(2)

            await self.update_department_queue(
                department_id
            )

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        if message.author.bot:
            return

        if not message.guild:
            return

        if message.content.lower().startswith(
            ".claim"
        ):

            try:

                thread = await self.bot.threads.find(
                    message.channel
                )

            except Exception:
                return

            if not thread:
                return

            if thread.id in self.claim_messages_sent:
                return

            self.claimed_tickets.add(
                thread.id
            )

            self.claim_messages_sent.add(
                thread.id
            )

            embed = discord.Embed(
                title="ᴀ Connected with Support",
                description=(
                    "A member of the "
                    "**Jet2Support** "
                    "team has claimed "
                    "your ticket.\n\n"
                    f"👤 Support Agent: "
                    f"{message.author.mention}\n\n"
                    "They will assist "
                    "you shortly."
                ),
                color=self.color
            )

            embed.set_thumbnail(
                url=message.author
                .display_avatar.url
            )

            try:

                await thread.recipient.send(
                    embed=embed
                )

            except Exception:
                pass


async def setup(bot):

    await bot.add_cog(
        Jet2Support(bot)
    )
