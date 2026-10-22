
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
CLOSE_DELAY = 1.0


class CloseAll(commands.Cog):
    """Close all discoverable Modmail tickets."""

    def __init__(self, bot):
        self.bot = bot
        self._closing_all = False

    @commands.command(
        name="closeall",
        help="Close all Modmail tickets. Usage: -closeall <reason>"
    )
    async def closeall(self, ctx, *, reason: str = None):

        if ctx.author.id != OWNER_ID:
            return await ctx.send(
                "❌ You are not authorised to use this command."
            )

        if self._closing_all:
            return await ctx.send(
                "⚠️ A bulk closure is already in progress."
            )

        if not reason or not reason.strip():
            return await ctx.send(
                f"Usage: `{ctx.prefix}closeall <reason>`"
            )

        reason = reason.strip()
        guild = getattr(self.bot, "modmail_guild", None)

        if guild is None:
            return await ctx.send(
                "❌ Modmail's staff server could not be found."
            )

        # Ask Modmail to discover threads from all staff text channels.
        try:
            await self.bot.threads.populate_cache()

            discovered = {}

            # Include every thread currently registered with Modmail.
            for thread in list(self.bot.threads.cache.values()):
                discovered[thread.id] = thread

            # Explicitly scan every text channel as well.
            for channel in list(guild.text_channels):
                try:
                    thread = await self.bot.threads.find(
                        channel=channel
                    )

                    if thread is not None:
                        discovered[thread.id] = thread

                except Exception:
                    log.exception(
                        "Thread discovery failed for channel %s (%s)",
                        channel.name,
                        channel.id,
                    )

            threads = list(discovered.values())

        except Exception:
            log.exception("Failed to discover Modmail threads.")
            return await ctx.send(
                "❌ Could not discover tickets. Check the console."
            )

        if not threads:
            return await ctx.send(
                "No discoverable Modmail tickets were found."
            )

        # Confirmation prompt.
        embed = discord.Embed(
            title="⚠️ Confirm bulk ticket closure",
            description=(
                f"**Tickets found:** {len(threads)}\n"
                f"**Reason:** {reason}\n\n"
                "React with ✅ to close all tickets.\n"
                "React with ❌ to cancel.\n"
                f"Expires in {CONFIRMATION_TIMEOUT} seconds."
            ),
            colour=discord.Colour.orange(),
        )

        try:
            prompt = await ctx.send(embed=embed)
            await prompt.add_reaction("✅")
            await prompt.add_reaction("❌")
        except discord.HTTPException:
            log.exception("Failed to send confirmation prompt.")
            return

        def check(reaction, user):
            return (
                user.id == OWNER_ID
                and reaction.message.id == prompt.id
                and str(reaction.emoji) in ("✅", "❌")
            )

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                timeout=CONFIRMATION_TIMEOUT,
                check=check,
            )
        except asyncio.TimeoutError:
            return await prompt.edit(
                embed=discord.Embed(
                    title="Bulk closure cancelled",
                    description="Confirmation expired. No tickets were closed.",
                    colour=discord.Colour.red(),
                )
            )

        if str(reaction.emoji) == "❌":
            return await prompt.edit(
                embed=discord.Embed(
                    title="Bulk closure cancelled",
                    description="No tickets were closed.",
                    colour=discord.Colour.red(),
                )
            )

        self._closing_all = True
        closed = 0
        failed = 0
        details = []

        try:
            await prompt.edit(
                embed=discord.Embed(
                    title="Bulk closure in progress",
                    description=(
                        f"Attempting to close **{len(threads)}** tickets.\n"
                        f"**Reason:** {reason}"
                    ),
                    colour=discord.Colour.orange(),
                )
            )

            for thread in threads:
                try:
                    # Do NOT call channel.fetch().
                    # Modmail already provides the channel through thread.channel.
                    # Use the native closure lifecycle for each thread.
                    await thread.close(
                        closer=ctx.author,
                        message=reason,
                        silent=False,
                        delete_channel=True,
                    )

                    closed += 1

                    log.info(
                        "CloseAll: closed thread %s by user %s",
                        thread.id,
                        ctx.author.id,
                    )

                except Exception as exc:
                    failed += 1
                    details.append(
                        f"Thread {getattr(thread, 'id', 'unknown')}: "
                        f"{type(exc).__name__}: {str(exc)[:150]}"
                    )

                    log.exception(
                        "CloseAll failed for thread %s",
                        getattr(thread, "id", "unknown"),
                    )

                await asyncio.sleep(CLOSE_DELAY)

        finally:
            self._closing_all = False

        result = discord.Embed(
            title="Bulk closure finished",
            description=(
                f"**Reason:** {reason}\n\n"
                f"✅ Close method completed: **{closed}**\n"
                f"❌ Failed: **{failed}**\n"
                f"📋 Discovered: **{len(threads)}**"
            ),
            colour=(
                discord.Colour.green()
                if failed == 0
                else discord.Colour.orange()
            ),
        )

        if details:
            result.add_field(
                name="Failure details",
                value="\n".join(details[:5])[:1024],
                inline=False,
            )

            if len(details) > 5:
                result.set_footer(
                    text=f"{len(details) - 5} more failures are in the console."
                )

        try:
            await prompt.edit(embed=result)
        except discord.HTTPException:
            log.exception("Failed to update the final report.")

        log.info(
            "CloseAll complete: owner=%s closed=%s failed=%s total=%s",
            ctx.author.id,
            closed,
            failed,
            len(threads),
        )


async def setup(bot):
    await bot.add_cog(CloseAll(bot))
