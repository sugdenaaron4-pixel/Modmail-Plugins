import asyncio
import discord
from discord.ext import commands

DEPARTMENTS = {
    "01": {"name": "General Inquiries", "description": "General questions\nPre sales\nBasic info", "wait": None},
    "02": {"name": "Billing & Finance", "description": "Billing\nRefunds\nPayments", "wait": None},
    "03": {"name": "Public Relations", "description": "Partnerships\nMedia requests", "wait": None},
    "04": {"name": "Legal & Abuse", "description": "Legal reports\nAbuse complaints", "wait": None},
    "05": {"name": "Senior Management", "description": "Escalations\nManagement review", "wait": "12 to 48 hours"},
    "06": {"name": "Other / Unsure", "description": "General support", "wait": None}
}


class Jet2Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xe02e2e

        self.ticket_departments = {}
        self.claimed_tickets = set()

    async def send_navigation_embed(self, channel):
        embed = discord.Embed(
            title="Support Navigation",
            description=(
                "01 General Inquiries\n"
                "02 Billing & Finance\n"
                "03 Public Relations\n"
                "04 Legal & Abuse\n"
                "05 Senior Management\n"
                "06 Other / Unsure\n\n"
                "Reply with number"
            ),
            color=self.color
        )
        await channel.send(embed=embed)

    async def send_department_embed(self, channel, dept_id):
        data = DEPARTMENTS.get(dept_id)
        if not data:
            return

        desc = f"You selected {data['name']}\n\n{data['description']}"

        if data["wait"]:
            desc += f"\n\nWait time: {data['wait']}"

        embed = discord.Embed(
            title="Department Selected",
            description=desc,
            color=self.color
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel = message.channel

        if not isinstance(channel, discord.Thread):
            return

        content = message.content.strip()

        try:
            dept_id = f"{int(content):02d}"
        except:
            return

        if dept_id not in DEPARTMENTS:
            return

        self.ticket_departments[channel.id] = dept_id

        await self.send_department_embed(channel, dept_id)

    @commands.command(name="claim")
    async def claim(self, ctx):
        channel = ctx.channel

        if not isinstance(channel, discord.Thread):
            await ctx.send("Use this inside a ticket thread.")
            return

        if channel.id in self.claimed_tickets:
            return

        self.claimed_tickets.add(channel.id)

        embed = discord.Embed(
            title="Ticket Claimed",
            description=f"Claimed by {ctx.author.mention}",
            color=self.color
        )

        await channel.send(embed=embed)
        await ctx.send("Claimed")


async def setup(bot):
    await bot.add_cog(Jet2Support(bot))
