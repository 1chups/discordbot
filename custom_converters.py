def __init__():
    pass


from discord.ext.commands import BadArgument, Converter
from datetime import timedelta


#-----------------------------+
#         Exceptions          |
#-----------------------------+
class BadTimedelta(BadArgument):
    def __init__(self, argument):
        self.argument = argument


class BadInt(BadArgument):
    def __init__(self, argument):
        self.argument = argument

#-----------------------------+
#         Converters          |
#-----------------------------+
class TimedeltaConverter(Converter):
    async def convert(self, ctx, argument):
        # NOTE: argument should look like 5h30m10s
        rest = argument.lower()
        if rest.isdigit():
            td = timedelta(minutes=int(rest))
        else:
            tkeys = ["d", "h", "m", "s"]
            raw_delta = {tk: 0 for tk in tkeys}
            for tk in tkeys:
                pair = rest.split(tk, maxsplit=1)
                if len(pair) < 2:
                    raw_delta[tk] = 0
                else:
                    value, rest = pair
                    if not value.isdigit():
                        raise BadTimedelta(argument)
                    raw_delta[tk] = int(value)
            td = timedelta(days=raw_delta["d"], hours=raw_delta["h"], minutes=raw_delta["m"], seconds=raw_delta["s"])
        if td.total_seconds() > 0:
            return td
        raise BadTimedelta(argument)


class IntConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            return int(argument)
        except:
            raise BadInt(argument)