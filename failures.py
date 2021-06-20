import discord
from discord.ext import commands

#---------------------------+
#           Errors          |
#---------------------------+
class IsNotModerator(commands.CheckFailure):
    pass


class CooldownResetSignal(commands.CommandError):
    pass