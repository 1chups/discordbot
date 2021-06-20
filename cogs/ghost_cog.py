import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+

class ghost_cog(commands.Cog):
    def __init__(self, client):
        self.client = client


    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> ghost_cog cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.is_owner()
    @commands.command()
    async def call(self, ctx):
        client = self.client
        try:
# CODE INSERTION
            __smth__ = 1
# CODE INSERTION
        except Exception as e:
            await ctx.send(f"```>> {e}```")




    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(ghost_cog(client))