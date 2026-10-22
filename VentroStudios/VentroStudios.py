import asyncio
import json
import os
from pathlib import Path

import discord
from discord.ext import commands
from discord.ui import View, Button


# ============================================================
# EASTLIGHT PRIMARY SCHOOL MODMAIL CONFIGURATION
# ============================================================

EMBED_COLOUR = 0xE02E2E
PREFIX = "-"

# Role allowed to use ?closeapp and ?openapp.
# Replace 0 with your Discord role ID.
CLOSEAPP_ALLOWED_ROLE_ID = 1553769601186144409

# Users with Administrator permission can also manage closures.
ALLOW_ADMIN_OVERRIDE = True

# Category used while a ticket awaits department selection.
AWAITING_PLACEMENT_CATEGORY = 1559299230533947484  # Replace with your category ID.

# Department categories.
# Replace the zeroes with the correct Discord category IDs.
DEPARTMENT_CATEGORIES = {
    "01": 1562212040582373376,  # General Enquiries
    "02": 1562212125860958309,  # Careers
    "03": 1562212854189264986,  # Legal & Abuse
    "04": 1562520490545774714,  # Development Enquiries — set this to its Discord category ID
}

# Department staff role IDs. Replace each 0 with the matching Discord role ID.
# Members of a department role can view and reply to that department's tickets.
# Other configured department roles are explicitly denied access to those tickets.
DEPARTMENT_ROLE_IDS = {
    "01": 1562532416134848532,  # General Enquiries staff role
    "02": 1562532476629549197,  # Careers staff role
    "03": 1562532530429763625,  # Legal & Abuse staff role
    "04": 1562532614244671598,  # Development Enquiries staff role
}

# Optional individual Careers branch categories.
# Set each ID to 0 to use the general Careers category instead.
CAREER_BRANCH_CATEGORIES = {
    "LLT": 1562212125860958309,
    "MLT": 1562212187269759108,
    "SLT": 1562212268941517001,
    "SITE": 1562212772450672670,
}

DATA_DIR = Path("data")
APPLICATION_STATUS_FILE = DATA_DIR / "application_status.json"

DEPARTMENTS = {
    "01": "General Enquiries",
    "02": "Careers",
    "03": "Legal & Abuse",
    "04": "Development Enquiries",
}

CAREER_BRANCHES = {
    "LLT": "Lower Leadership Team (LLT)",
    "MLT": "Middle Leadership Team (MLT)",
    "SLT": "Senior Leadership Team (SLT)",
    "SITE": "Site Team (SITE)",
}

AVERAGE_HANDLE_TIME = {
    "01": 5,
    "02": 8,
    "03": 10,
    "04": 8,
}

DEPARTMENT_ALIASES = {
    "01": "01",
    "1": "01",
    "general": "01",
    "general enquiries": "01",
    "general inquiries": "01",

    "02": "02",
    "2": "02",
    "careers": "02",
    "career": "02",

    "03": "03",
    "3": "03",
    "legal": "03",
    "abuse": "03",
    "legal & abuse": "03",

    "04": "04",
    "development": "04",
    "development enquiry": "04",
    "development enquiries": "04",
    "development inquiry": "04",
    "development inquiries": "04",
}

BRANCH_ALIASES = {
    "LLT": "LLT",
    "LOWER LEADERSHIP TEAM": "LLT",
    "LOWER LEADERSHIP": "LLT",

    "MLT": "MLT",
    "MIDDLE LEADERSHIP TEAM": "MLT",
    "MIDDLE LEADERSHIP": "MLT",

    "SLT": "SLT",
    "SENIOR LEADERSHIP TEAM": "SLT",
    "SENIOR LEADERSHIP": "SLT",

    "SITE": "SITE",
    "SITE TEAM": "SITE",
}


# ============================================================
# MODMAIL COG
# ============================================================

class EastlightModmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Ticket information held while the bot is running.
        self.ticket_departments = {}
        self.ticket_branches = {}
        self.pending_careers = set()

        self.claimed_tickets = set()
        self.ticket_claimers = {}
        self.ticket_created_at = {}
        self.ticket_numbers = {}
        self.currently_serving = {}

        self.ticket_counter = 0

        # Branch closures survive bot restarts.
        self.application_status = {
            branch: True for branch in CAREER_BRANCHES
        }

        self.load_application_status()

    # ========================================================
    # APPLICATION STATUS STORAGE
    # ========================================================

    def load_application_status(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if not APPLICATION_STATUS_FILE.exists():
            self.save_application_status()
            return

        try:
            with APPLICATION_STATUS_FILE.open(
                "r", encoding="utf-8"
            ) as file:
                saved = json.load(file)

            for branch in CAREER_BRANCHES:
                self.application_status[branch] = bool(
                    saved.get(branch, True)
                )

        except (json.JSONDecodeError, OSError) as error:
            print(
                "[Eastlight Modmail] Could not load application "
                f"status: {error}"
            )

    def save_application_status(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        temporary_file = APPLICATION_STATUS_FILE.with_suffix(".tmp")

        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(
                self.application_status,
                file,
                indent=4
            )

        temporary_file.replace(APPLICATION_STATUS_FILE)

    # ========================================================
    # GENERAL HELPERS
    # ========================================================

    def normalize_department(self, value):
        if not value:
            return None

        return DEPARTMENT_ALIASES.get(value.strip().lower())

    def normalize_branch(self, value):
        if not value:
            return None

        return BRANCH_ALIASES.get(value.strip().upper())

    def get_category(self, guild, category_id):
        if not category_id:
            return None

        category = guild.get_channel(category_id)

        if isinstance(category, discord.CategoryChannel):
            return category

        return None

    async def apply_department_role_permissions(self, thread, department_id=None):
        """Restrict configured department roles to their own ticket category."""
        channel = thread.channel
        guild = channel.guild

        for role_department, role_id in DEPARTMENT_ROLE_IDS.items():
            if not role_id:
                continue

            role = guild.get_role(role_id)
            if role is None:
                print(
                    f"[Eastlight Modmail] Department role ID {role_id} "
                    f"for department {role_department} was not found."
                )
                continue

            overwrite = channel.overwrites_for(role)
            if department_id is not None and role_department == department_id:
                overwrite.view_channel = True
                overwrite.send_messages = True
                overwrite.read_message_history = True
                overwrite.attach_files = True
                overwrite.embed_links = True
            else:
                # Explicitly override any broad category permission for other
                # configured department roles, without changing recipient access.
                overwrite.view_channel = False
                overwrite.send_messages = False
                overwrite.read_message_history = False

            try:
                await channel.set_permissions(
                    role,
                    overwrite=overwrite,
                    reason="Eastlight Modmail department access control",
                )
            except (discord.Forbidden, discord.HTTPException) as error:
                print(
                    f"[Eastlight Modmail] Could not set department role "
                    f"permissions for {role.name} on {channel.id}: {error}"
                )

    async def move_ticket(self, thread, department_id, branch=None):
        """Move a ticket and report whether Discord confirmed the move."""
        category_id = DEPARTMENT_CATEGORIES.get(department_id)

        if department_id == "02" and branch:
            # A branch-specific category takes priority over the general
            # Careers category.
            category_id = CAREER_BRANCH_CATEGORIES.get(branch) or category_id

        category = self.get_category(thread.channel.guild, category_id)
        moved = False

        if category is None:
            print(
                f"[Eastlight Modmail] Cannot move ticket {thread.id}: "
                f"category ID {category_id!r} for department "
                f"{department_id} / branch {branch!r} was not found "
                "or is not a Discord category."
            )
        else:
            try:
                await thread.channel.edit(
                    category=category,
                    reason=f"Modmail department transfer: {department_id}"
                    + (f" / {branch}" if branch else "")
                )
                moved = True
            except (discord.Forbidden, discord.HTTPException) as error:
                print(
                    f"[Eastlight Modmail] Could not move ticket "
                    f"{thread.id} to category {category.id}: {error}"
                )

        # Keep the department access controls updated even if the move fails.
        await self.apply_department_role_permissions(thread, department_id)
        return moved

    def can_manage_application_status(self, member):
        if not isinstance(member, discord.Member):
            return False

        if (
            ALLOW_ADMIN_OVERRIDE
            and member.guild_permissions.administrator
        ):
            return True

        if CLOSEAPP_ALLOWED_ROLE_ID == 0:
            return False

        return any(
            role.id == CLOSEAPP_ALLOWED_ROLE_ID
            for role in member.roles
        )

    async def find_thread(self, channel):
        try:
            return await self.bot.threads.find(
                recipient=None,
                channel=channel
            )
        except Exception:
            return None

    async def notify_recipient(self, thread, embed):
        try:
            await thread.recipient.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ========================================================
    # EMBEDS
    # ========================================================

    async def send_navigation_embed(self, thread):
        embed = discord.Embed(
            title="Eastlight Primary School | Support",
            description=(
                "Welcome to **Eastlight Primary School** support.\n\n"
                "Please select the department you need by replying "
                "with the corresponding number.\n\n"
                "**01** — General Enquiries\n"
                "**02** — Careers\n"
                "**03** — Legal & Abuse\n"
                "**04** — Development Enquiries\n\n"
                "For Careers applications, you will then be asked "
                "to select a team."
            ),
            color=EMBED_COLOUR
        )

        embed.set_footer(text="Eastlight Primary School • Support")

        await self.notify_recipient(thread, embed)

    async def send_career_branch_embed(self, thread):
        lines = []

        for code, name in CAREER_BRANCHES.items():
            status = (
                "🟢 Open"
                if self.application_status.get(code, True)
                else "🔴 Closed"
            )
            lines.append(f"**{code}** — {name} · {status}")

        embed = discord.Embed(
            title="Careers | Choose a Team",
            description=(
                "Please reply with the code for the team you wish "
                "to apply to.\n\n"
                + "\n".join(lines)
                + "\n\nOnly open teams can accept new applications."
            ),
            color=EMBED_COLOUR
        )

        embed.set_footer(
            text="Eastlight Primary School • Careers"
        )

        await self.notify_recipient(thread, embed)

    async def send_department_embed(self, thread, department_id):
        descriptions = {
            "01": (
                "Your ticket has been placed in **General Enquiries**.\n\n"
                "A member of the appropriate team will assist you."
            ),
            "02": (
                "Your ticket has been placed in **Careers**.\n\n"
                "Your selected team will review your application."
            ),
            "03": (
                "Your ticket has been placed in **Legal & Abuse**.\n\n"
                "A suitable team member will review your enquiry."
            ),
            "04": (
                "Your ticket has been placed in **Development Enquiries**.\n\n"
                "The development team will review your enquiry."
            ),
        }

        embed = discord.Embed(
            title="Department Selected",
            description=descriptions[department_id],
            color=EMBED_COLOUR
        )

        await self.notify_recipient(thread, embed)

    async def send_staff_department_log(
        self, thread, department_id, user
    ):
        branch = self.ticket_branches.get(thread.id)

        description = (
            f"**User:** {user.mention}\n"
            f"**Department:** {DEPARTMENTS[department_id]}\n"
            f"**Ticket:** `{thread.id}`"
        )

        if branch:
            description += (
                f"\n**Careers Team:** {CAREER_BRANCHES[branch]}"
            )

        embed = discord.Embed(
            title="Department Selected",
            description=description,
            color=EMBED_COLOUR
        )

        await thread.channel.send(embed=embed)

    # ========================================================
    # QUEUE SYSTEM
    # ========================================================

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
            key=lambda ticket: self.ticket_created_at.get(
                ticket.id, discord.utils.utcnow()
            )
        )

        ids = [ticket.id for ticket in active]

        return ids.index(thread_id) + 1 if thread_id in ids else 1

    async def send_queue_update(self, thread, department_id):
        if thread.id in self.claimed_tickets:
            return

        position = await self.get_queue_position(
            thread.id,
            department_id
        )

        ticket_number = self.ticket_numbers.get(
            thread.id, "Unassigned"
        )

        serving = self.currently_serving.get(department_id)

        if 10 <= position % 100 <= 20:
            suffix = "th"
        else:
            suffix = {
                1: "st",
                2: "nd",
                3: "rd"
            }.get(position % 10, "th")

        average = AVERAGE_HANDLE_TIME.get(department_id, 5)
        minimum_wait = (position - 1) * average
        maximum_wait = position * average

        embed = discord.Embed(
            title="Support Queue Update",
            description=(
                f"**Ticket Number:** {ticket_number}\n"
                f"**Currently Serving:** {serving or 'None'}\n\n"
                f"You are **{position}{suffix}** in the "
                f"**{DEPARTMENTS[department_id]}** queue.\n\n"
                f"**Estimated wait:** {minimum_wait}–"
                f"{maximum_wait} minutes"
            ),
            color=EMBED_COLOUR
        )

        await self.notify_recipient(thread, embed)

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

    # ========================================================
    # MODMAIL LISTENERS
    # ========================================================

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await asyncio.sleep(1)

        self.ticket_counter += 1
        self.ticket_numbers[thread.id] = self.ticket_counter
        self.ticket_created_at[thread.id] = discord.utils.utcnow()

        category = self.get_category(
            thread.channel.guild,
            AWAITING_PLACEMENT_CATEGORY
        )

        if category:
            try:
                await thread.channel.edit(category=category)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await self.apply_department_role_permissions(thread, None)
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
        # Staff replies do not select departments or branches.
        if from_mod:
            return

        # Once a department/team has been selected, users cannot send
        # further replies until a staff member claims the ticket.
        # Career branch selection remains allowed while it is pending.
        if (
            thread.id in self.ticket_departments
            and thread.id not in self.claimed_tickets
            and thread.id not in self.pending_careers
        ):
            try:
                await message.delete()
            except (AttributeError, discord.Forbidden, discord.HTTPException):
                pass

            embed = discord.Embed(
                title="Please Wait for a Support Agent",
                description=(
                    "Your department has been selected, but your ticket "
                    "has not been claimed yet. You can send messages once "
                    "a member of staff claims your ticket."
                ),
                color=EMBED_COLOUR
            )
            await self.notify_recipient(thread, embed)
            return

        # First response: department selection.
        if (
            thread.id not in self.ticket_departments
            and thread.id not in self.pending_careers
        ):
            department_id = self.normalize_department(
                message.content
            )

            if department_id is None:
                return

            if department_id == "02":
                self.pending_careers.add(thread.id)

                await self.move_ticket(thread, "02")
                await self.send_career_branch_embed(thread)
                return

            self.ticket_departments[thread.id] = department_id

            await self.move_ticket(thread, department_id)
            await self.send_department_embed(thread, department_id)

            await self.send_staff_department_log(
                thread,
                department_id,
                message.author
            )

            await self.update_department_queue(department_id)
            return

        # Second response for Careers tickets: branch selection.
        if thread.id in self.pending_careers:
            branch = self.normalize_branch(message.content)

            if branch is None:
                return

            # Closed branches reject new applications only.
            # This does not close or modify existing tickets.
            if not self.application_status.get(branch, True):
                embed = discord.Embed(
                    title="Applications Currently Closed",
                    description=(
                        f"Applications for **{CAREER_BRANCHES[branch]}** "
                        "are currently closed.\n\n"
                        "Please choose another open team or contact "
                        "Eastlight Primary School for further information."
                    ),
                    color=EMBED_COLOUR
                )

                await self.notify_recipient(thread, embed)
                await self.send_career_branch_embed(thread)
                return

            self.pending_careers.discard(thread.id)
            self.ticket_departments[thread.id] = "02"
            self.ticket_branches[thread.id] = branch

            await self.move_ticket(thread, "02", branch)
            await self.send_department_embed(thread, "02")

            await self.send_staff_department_log(
                thread,
                "02",
                message.author
            )

            await self.update_department_queue("02")

    @commands.Cog.listener()
    async def on_thread_close(
        self,
        thread,
        closer,
        silent,
        delete_channel
    ):
        department_id = self.ticket_departments.get(thread.id)

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)
        self.pending_careers.discard(thread.id)

        if department_id:
            self.currently_serving.pop(department_id, None)
            await self.update_department_queue(department_id)

    # ========================================================
    # APPLICATION BRANCH MANAGEMENT
    # ========================================================

    @commands.command(name="closeapp")
    async def close_application_branch(self, ctx, branch=None):
        if not self.can_manage_application_status(ctx.author):
            return await ctx.send(
                "❌ You do not have permission to manage application "
                "branch availability."
            )

        if branch is None:
            return await ctx.send(
                "**Usage:** `?closeapp <LLT|MLT|SLT|SITE>`"
            )

        branch_code = self.normalize_branch(branch)

        if branch_code is None:
            return await ctx.send(
                "❌ Invalid branch. Use `LLT`, `MLT`, `SLT`, or `SITE`."
            )

        if not self.application_status.get(branch_code, True):
            return await ctx.send(
                f"⚠️ Applications for **{CAREER_BRANCHES[branch_code]}** "
                "are already closed."
            )

        self.application_status[branch_code] = False
        self.save_application_status()

        embed = discord.Embed(
            title="Applications Closed",
            description=(
                f"Applications for **{CAREER_BRANCHES[branch_code]}** "
                "are now closed.\n\n"
                "New applications for this branch will be rejected. "
                "Existing tickets will remain open."
            ),
            color=EMBED_COLOUR
        )

        await ctx.send(embed=embed)

    @commands.command(name="openapp")
    async def open_application_branch(self, ctx, branch=None):
        if not self.can_manage_application_status(ctx.author):
            return await ctx.send(
                "❌ You do not have permission to manage application "
                "branch availability."
            )

        if branch is None:
            return await ctx.send(
                "**Usage:** `?openapp <LLT|MLT|SLT|SITE>`"
            )

        branch_code = self.normalize_branch(branch)

        if branch_code is None:
            return await ctx.send(
                "❌ Invalid branch. Use `LLT`, `MLT`, `SLT`, or `SITE`."
            )

        if self.application_status.get(branch_code, True):
            return await ctx.send(
                f"⚠️ Applications for **{CAREER_BRANCHES[branch_code]}** "
                "are already open."
            )

        self.application_status[branch_code] = True
        self.save_application_status()

        embed = discord.Embed(
            title="Applications Opened",
            description=(
                f"Applications for **{CAREER_BRANCHES[branch_code]}** "
                "are now open again."
            ),
            color=EMBED_COLOUR
        )

        await ctx.send(embed=embed)

    @commands.command(name="appstatus")
    async def application_status_command(self, ctx):
        lines = []

        for branch_code, branch_name in CAREER_BRANCHES.items():
            status = (
                "🟢 Open"
                if self.application_status.get(branch_code, True)
                else "🔴 Closed"
            )

            lines.append(f"**{branch_name}:** {status}")

        embed = discord.Embed(
            title="Careers Application Status",
            description="\n".join(lines),
            color=EMBED_COLOUR
        )

        await ctx.send(embed=embed)

    # ========================================================
    # CLAIM
    # ========================================================

    @commands.command(name="claim")
    async def claim_ticket(self, ctx):
        thread = await self.find_thread(ctx.channel)

        if thread is None:
            return await ctx.send(
                "❌ Use this command inside a Modmail ticket."
            )

        if thread.id in self.claimed_tickets:
            return await ctx.send(
                "❌ This ticket has already been claimed."
            )

        department_id = self.ticket_departments.get(thread.id)

        if department_id is None:
            return await ctx.send(
                "⚠️ The user has not selected a department yet."
            )

        self.claimed_tickets.add(thread.id)
        self.ticket_claimers[thread.id] = ctx.author.id

        self.currently_serving[department_id] = (
            self.ticket_numbers.get(thread.id)
        )

        branch = self.ticket_branches.get(thread.id)
        team_name = (
            CAREER_BRANCHES[branch]
            if branch
            else DEPARTMENTS[department_id]
        )

        embed = discord.Embed(
            title="Your Support Ticket Has Been Claimed",
            description=(
                f"A member of **{team_name}** is now assisting you.\n\n"
                f"**Support Agent:** {ctx.author.mention}\n\n"
                "Please explain your enquiry clearly and provide "
                "any relevant information."
            ),
            color=EMBED_COLOUR
        )

        embed.set_footer(
            text="Eastlight Primary School • Support Team"
        )

        await self.notify_recipient(thread, embed)
        await ctx.message.add_reaction("✅")

        await self.update_department_queue(department_id)

    # ========================================================
    # UNCLAIM
    # ========================================================

    @commands.command(name="unclaim")
    async def unclaim_ticket(self, ctx):
        thread = await self.find_thread(ctx.channel)

        if thread is None:
            return await ctx.send(
                "❌ Use this command inside a Modmail ticket."
            )

        if thread.id not in self.claimed_tickets:
            return await ctx.send(
                "⚠️ This ticket is not currently claimed."
            )

        department_id = self.ticket_departments.get(thread.id, "01")

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)
        self.currently_serving.pop(department_id, None)

        embed = discord.Embed(
            title="Ticket Returned to the Queue",
            description=(
                "Your ticket has been returned to the support queue. "
                "Another agent will assist you when available."
            ),
            color=EMBED_COLOUR
        )

        await self.notify_recipient(thread, embed)
        await ctx.send("✅ Ticket unclaimed and returned to the queue.")

        await self.send_queue_update(thread, department_id)
        await self.update_department_queue(department_id)

    # ========================================================
    # TRANSFER
    # ========================================================

    @commands.command(name="transfer")
    async def transfer_ticket(self, ctx, department=None, branch=None):
        thread = await self.find_thread(ctx.channel)

        if thread is None:
            return await ctx.send(
                "❌ Use this command inside a Modmail ticket."
            )

        if not department:
            return await ctx.send(
                "**Usage:** `-transfer <department> [branch]`\\n"
                "`01` — General Enquiries\\n"
                "`02 <LLT|MLT|SLT|SITE>` — Careers (branch required)\\n"
                "`03` — Legal & Abuse\\n"
                "`04` — Development Enquiries\\n\\n"
                "**Example:** `-transfer 02 SLT`"
            )

        department_id = self.normalize_department(department)
        if department_id is None:
            return await ctx.send(
                "❌ Invalid department. Use `01`, `02`, `03`, or `04`."
            )

        branch_code = None
        if department_id == "02":
            if not branch:
                return await ctx.send(
                    "❌ A Careers branch is required. Use "
                    "`-transfer 02 LLT`, `-transfer 02 MLT`, "
                    "`-transfer 02 SLT`, or `-transfer 02 SITE`."
                )
            branch_code = self.normalize_branch(branch)
            if branch_code is None:
                return await ctx.send(
                    "❌ Invalid Careers branch. Use `LLT`, `MLT`, "
                    "`SLT`, or `SITE`."
                )
        elif branch is not None:
            return await ctx.send(
                "❌ Only Careers transfers use a branch. Example: "
                "`-transfer 03`."
            )

        old_department = self.ticket_departments.get(thread.id)

        self.pending_careers.discard(thread.id)
        self.ticket_departments[thread.id] = department_id
        self.ticket_branches.pop(thread.id, None)
        if branch_code:
            self.ticket_branches[thread.id] = branch_code

        self.claimed_tickets.discard(thread.id)
        self.ticket_claimers.pop(thread.id, None)

        moved = await self.move_ticket(thread, department_id, branch_code)

        await self.send_department_embed(thread, department_id)
        if department_id == "02":
            destination = f"Careers — {CAREER_BRANCHES[branch_code]}"
        else:
            destination = DEPARTMENTS[department_id]

        warning = "" if moved else (
            "\\n⚠️ Ticket details were updated, but Discord did not confirm "
            "the channel move. Check the category ID and the bot's "
            "**Manage Channels** permission."
        )
        await ctx.send(f"✅ Ticket transferred to **{destination}**.{warning}")

        if old_department:
            self.currently_serving.pop(old_department, None)
            await self.update_department_queue(old_department)

        await self.update_department_queue(department_id)

    # ========================================================
    # REQUEST CLOSE
    # ========================================================

    @commands.command(
        name="requestclose",
        aliases=["closerequest"]
    )
    async def request_close(self, ctx):
        thread = await self.find_thread(ctx.channel)

        if thread is None:
            return await ctx.send(
                "❌ Use this command inside a Modmail ticket."
            )

        department_id = self.ticket_departments.get(thread.id, "01")

        cog = self

        class CloseView(View):
            def __init__(self):
                super().__init__(timeout=300)

            @discord.ui.button(
                label="Accept & Close",
                style=discord.ButtonStyle.success
            )
            async def accept(
                self,
                interaction: discord.Interaction,
                button: Button
            ):
                if interaction.user.id != thread.recipient.id:
                    return await interaction.response.send_message(
                        "Only the ticket recipient can use these buttons.",
                        ephemeral=True
                    )

                try:
                    await interaction.response.send_message(
                        "Your ticket will now be closed.",
                        ephemeral=True
                    )

                    await thread.close(closer=cog.bot.user)

                except Exception as error:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"Failed to close the ticket: {error}",
                            ephemeral=True
                        )

                self.stop()

            @discord.ui.button(
                label="Deny & Stay Open",
                style=discord.ButtonStyle.danger
            )
            async def deny(
                self,
                interaction: discord.Interaction,
                button: Button
            ):
                if interaction.user.id != thread.recipient.id:
                    return await interaction.response.send_message(
                        "Only the ticket recipient can use these buttons.",
                        ephemeral=True
                    )

                await interaction.response.send_message(
                    "Your ticket will remain open.",
                    ephemeral=True
                )

                self.stop()

            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True

                # The original message is optional; timeout simply
                # prevents the buttons from being used again.

        embed = discord.Embed(
            title="Ticket Close Request",
            description=(
                "The support team believes your enquiry may be resolved.\n\n"
                "Select **Accept & Close** if your issue is resolved, "
                "or **Deny & Stay Open** if you still need help.\n\n"
                "This request expires in 5 minutes."
            ),
            color=EMBED_COLOUR
        )

        embed.set_footer(
            text="Eastlight Primary School • Support"
        )

        await self.notify_recipient(
            thread,
            embed
        )

        # Send the view with the embed directly to the recipient.
        try:
            await thread.recipient.send(
                embed=embed,
                view=CloseView()
            )
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(
                "❌ Could not send the close request to the recipient."
            )
            return

        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(EastlightModmail(bot))

