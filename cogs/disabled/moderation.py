import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import is_moderator

class moderation(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Moderation cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(manage_messages=True) )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(
        aliases=["clean"],
        description="",
        usage="",
        brief="" )
    async def clear(self, ctx, amount: int):
        await ctx.channel.purge(limit=amount + 1)
        reply = discord.Embed(
            title="🗑 | Чистка канала",
            description=f"Удалено **{amount}** сообщений",
            color=ctx.guild.me.color
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply, delete_after=3)

    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(moderation(client))