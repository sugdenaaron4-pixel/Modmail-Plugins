
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
    """Close all discoverable Modmail threads."""

    def __init__(self, bot):
        self.bot = bot
        self._closing_all = False

    @commands.command(
        name="closeall",
        help="Close all Modmail tickets. Usage: -closeall <reason>"
    )
    async def closeall(self, ctx, *, reason: str = None):

        # Restrict command access to one Discord account.
        if ctx.author.id != OWNER_ID:
            await ctx.send(
                "❌ You are not authorised to use this command."
            )
            return

        if self._closing_all:
            await ctx.send(
                "⚠️ A bulk closure is already in progress."
            )
            return

        if not reason or not reason.strip():
            await ctx.send(
                f"Usage: `{ctx.prefix}closeall <reason>`"
            )
            return

        reason = reason.strip()
        guild = getattr(self.bot, "modmail_guild", None)

        if guild is None:
            await ctx.send(
                "❌ Modmail's staff server could not be found."
            )
            return

        # Discover tickets from all staff-server text channels.
        # This rebuilds the cache and also explicitly checks channels.
        threads_by_channel = {}
        threads_by_recipient = {}

        try:
            await self.bot.threads.populate_cache()

            # Include all cached threads, including entries whose
            # channel is missing or which are no longer active.
            for thread in list(self.bot.threads.cache.values()):
                channel = getattr(thread, "channel", None)

                if channel is not None:
                    threads_by_channel[channel.id] = thread
                else:
                    threads_by_recipient[thread.id] = thread

            # Scan every text channel for a discoverable Modmail thread.
            for channel in list(guild.text_channels):
                try:
                    thread = await self.bot.threads.find(
                        channel=channel
                    )

                    if thread is not None:
                        threads_by_channel[channel.id] = thread

                except Exception:
                    log.exception(
                        "Could not identify a ticket in channel %s (%s)",
                        channel.name,
                        channel.id,
                    )

            threads = list(threads_by_channel.values())

            # Include cache-only entries, without duplicating recipients.
            known_ids = {thread.id for thread in threads}

            for recipient_id, thread in threads_by_recipient.items():
                if recipient_id not in known_ids:
                    threads.append(thread)
                    known_ids.add(recipient_id)

        except Exception:
            log.exception("Failed while discovering Modmail threads.")
            await ctx.send(
                "❌ Ticket discovery failed. Check the bot console."
            )
            return

        if not threads:
            await ctx.send(
                "No discoverable Modmail tickets were found."
            )
            return

        # Require confirmation before performing this destructive action.
        embed = discord.Embed(
            title="⚠️ Confirm closure of all tickets",
            description=(
                f"**Tickets discovered:** {len(threads)}\n"
                f"**Reason:** {reason}\n\n"
                "React with ✅ to close all discovered tickets.\n"
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
            log.exception("Could not send the confirmation prompt.")
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
            await prompt.edit(
                embed=discord.Embed(
                    title="Bulk closure cancelled",
                    description="Confirmation expired. No tickets were closed.",
                    colour=discord.Colour.red(),
                )
            )
            return

        if str(reaction.emoji) == "❌":
            await prompt.edit(
                embed=discord.Embed(
                    title="Bulk closure cancelled",
                    description="No tickets were closed.",
                    colour=discord.Colour.red(),
                )
            )
            return

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
                thread_id = getattr(thread, "id", "unknown")
                channel = getattr(thread, "channel", None)

                try:
                    # Skip only if Discord confirms the channel is
                    # already deleted. Cached threads without a channel
                    # are still attempted through Modmail's close API.
                    if channel is not None:
                        try:
                            await channel.fetch()
                        except discord.NotFound:
                            # The channel is already gone.
                            # Do not count it as a successful close here,
                            # because the normal close lifecycle may not run.
                            failed += 1
                            details.append(
                                f"Thread {thread_id}: channel already deleted"
                            )
                            continue

                    await thread.close(
                        closer=ctx.author,
                        message=reason,
                        silent=False,
                        delete_channel=True,
                    )

                    closed += 1

                    log.info(
                        "Bulk-closed thread %s by owner %s",
                        thread_id,
                        ctx.author.id,
                    )

                except Exception as exc:
                    failed += 1
                    details.append(
                        f"Thread {thread_id}: {type(exc).__name__}"
                    )

                    log.exception(
                        "Failed to close Modmail thread %s",
                        thread_id,
                    )

                await asyncio.sleep(CLOSE_DELAY)

        finally:
            self._closing_all = False

        result = discord.Embed(
            title="Bulk closure finished",
            description=(
                f"**Reason:** {reason}\n\n"
                f"✅ Close method completed: **{closed}**\n"
                f"❌ Failed or already deleted: **{failed}**\n"
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
                value="\n".join(details[:10])[:1024],
                inline=False,
            )

            if len(details) > 10:
                result.set_footer(
                    text=f"{len(details) - 10} additional failures in console."
                )

        try:
            await prompt.edit(embed=result)
        except discord.HTTPException:
            log.exception("Could not update final report.")

        log.info(
            "CloseAll finished: owner=%s closed=%s failed=%s discovered=%s",
            ctx.author.id,
            closed,
            failed,
            len(threads),
        )


async def setup(bot):
    await bot.add_cog(CloseAll(bot))
