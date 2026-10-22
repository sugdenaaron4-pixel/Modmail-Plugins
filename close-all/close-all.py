
import asyncio
import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)

# ==================================================
# CONFIGURATION
# ==================================================

OWNER_ID = 1178455890261721090  # Replace with your Discord user ID

CONFIRMATION_TIMEOUT = 60
CLOSE_DELAY = 0.5


class CloseAll(commands.Cog):
    """Close all active Modmail tickets using one command."""

    def __init__(self, bot):
        self.bot = bot
        self._closing_all = False

    @commands.command(
        name="closeall",
        help="Close all active Modmail tickets. Usage: -closeall <reason>"
    )
    async def closeall(self, ctx, *, reason: str = None):
        # Only the configured Discord account can use this command.
        if ctx.author.id != OWNER_ID:
            return await ctx.send(
                "❌ You are not authorised to use this command."
            )

        # Prevent multiple bulk closures running simultaneously.
        if self._closing_all:
            return await ctx.send(
                "⚠️ A bulk ticket closure is already in progress."
            )

        # A reason is mandatory.
        if not reason or not reason.strip():
            return await ctx.send(
                f"Please provide a reason.\n"
                f"Usage: `{ctx.prefix}closeall <reason>`"
            )

        reason = reason.strip()

        # Obtain a snapshot of the currently active Modmail threads.
        try:
            threads = list(self.bot.threads)
        except Exception:
            log.exception("Unable to retrieve active Modmail threads.")
            return await ctx.send(
                "❌ Could not retrieve active tickets. "
                "Check the bot console for errors."
            )

        if not threads:
            return await ctx.send(
                "There are no active Modmail tickets to close."
            )

        # Confirmation prompt.
        embed = discord.Embed(
            title="⚠️ Confirm bulk ticket closure",
            description=(
                f"This will attempt to close **{len(threads)} active tickets**.\n\n"
                f"**Reason:** {reason}\n\n"
                "React with ✅ to confirm or ❌ to cancel.\n"
                f"You have {CONFIRMATION_TIMEOUT} seconds to respond."
            ),
            colour=discord.Colour.orange()
        )

        try:
            confirmation = await ctx.send(embed=embed)
            await confirmation.add_reaction("✅")
            await confirmation.add_reaction("❌")
        except discord.HTTPException:
            log.exception("Could not send the confirmation prompt.")
            return

        def check(reaction, user):
            return (
                user.id == OWNER_ID
                and reaction.message.id == confirmation.id
                and str(reaction.emoji) in ("✅", "❌")
            )

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                timeout=CONFIRMATION_TIMEOUT,
                check=check
            )
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="Bulk closure cancelled",
                description="No confirmation was received. No tickets were closed.",
                colour=discord.Colour.red()
            )
            return await confirmation.edit(embed=timeout_embed)

        if str(reaction.emoji) == "❌":
            cancelled_embed = discord.Embed(
                title="Bulk closure cancelled",
                description="No tickets were closed.",
                colour=discord.Colour.red()
            )
            return await confirmation.edit(embed=cancelled_embed)

        # Start the bulk closure.
        self._closing_all = True
        closed = 0
        failed = 0
        skipped = 0

        progress_embed = discord.Embed(
            title="Bulk closure in progress",
            description=(
                f"Attempting to close {len(threads)} tickets.\n"
                f"**Reason:** {reason}"
            ),
            colour=discord.Colour.orange()
        )

        try:
            await confirmation.edit(embed=progress_embed)

            for thread in threads:
                try:
                    # Skip threads which are no longer active.
                    try:
                        active = thread.id in self.bot.threads
                    except (TypeError, AttributeError):
                        active = True

                    if not active:
                        skipped += 1
                        continue

                    # Use Modmail's own close functionality.
                    await thread.close(
                        closer=ctx.author,
                        message=reason,
                        silent=False,
                        delete_channel=True
                    )

                    closed += 1

                except Exception:
                    failed += 1
                    log.exception(
                        "Failed to close Modmail thread %s",
                        getattr(thread, "id", "unknown")
                    )

                # Reduce the chance of hitting Discord API rate limits.
                await asyncio.sleep(CLOSE_DELAY)

        finally:
            self._closing_all = False

        # Final results.
        result_embed = discord.Embed(
            title="Bulk ticket closure finished",
            description=(
                f"**Reason:** {reason}\n\n"
                f"✅ Successfully closed: **{closed}**\n"
                f"❌ Failed: **{failed}**\n"
                f"⏭️ Already closed/skipped: **{skipped}**\n"
                f"📋 Originally active: **{len(threads)}**"
            ),
            colour=(
                discord.Colour.green()
                if failed == 0
                else discord.Colour.orange()
            )
        )

        try:
            await confirmation.edit(embed=result_embed)
        except discord.HTTPException:
            log.exception("Could not update the final closure report.")

        log.info(
            "Bulk closure by %s (%s): closed=%s failed=%s skipped=%s reason=%r",
            ctx.author,
            ctx.author.id,
            closed,
            failed,
            skipped,
            reason
        )


async def setup(bot):
    await bot.add_cog(CloseAll(bot))
