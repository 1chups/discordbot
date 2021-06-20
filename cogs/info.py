from typing import Optional
import discord
from discord.ext import commands


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #========== Events ===========
    @commands.Cog.listener()
    async def on_ready(self):
        print(">> Info cog is loaded")

    #========= Commands ===========
    @commands.command(name = "uinfo")
    async def userinfo_command(self, ctx, target: Optional[discord.Member]):
        target = target or ctx.author

        embed = discord.Embed(
            title = "Информация пользователя:",
            colour = target.colour,
            timestamp = ctx.message.created_at
        )

        embed.set_thumbnail(url =target.avatar_url)

        fields = [
            ("Имя", str(target), True),
            ("ID", target.id, True),
            ("Статус", str(target.status).title(), True),
            ("Присоединился к дискорду", target.created_at.strftime("%d.%m.%Y"), True),
            ("Присоединился к серверу", target.joined_at.strftime("%d.%m.%Y"), True),
            ("Имя", str(target), True),
        ]

        for name, value, inline, in fields:
            embed.add_field(name = name, value = value, inline = inline)

        await ctx.send(embed=embed)
        await ctx.message.delete()

def setup(bot):
    bot.add_cog(Information(bot))

    