import discord
from discord.ext import commands
import os, json
from pymongo import MongoClient


from functions import get_field, is_moderator
from db_models import ServerConfig


app_string = str(os.environ.get('cluster_string'))
cluster = MongoClient(app_string)
db = cluster["guilds"]

trigger_file = "msg_triggers.json"
mod_role_limit = 10

def delete(filename):
    if filename in os.listdir("."):
        os.remove(filename)

def load(filename, default=None):
    if filename in os.listdir("."):
        with open(filename, "r", encoding="utf8") as fff:
            default = json.load(fff)
    return default

def save(data, filename):
    with open(filename, "w", encoding="utf8") as fff:
        json.dump(data, fff)

#============= Cog itself ================

class settings(commands.Cog):
    def __init__(self, client):
        self.client = client

    #========== Events ===========
    @commands.Cog.listener()
    async def on_ready(self):
        delete(trigger_file)
        print(">> Settings cog is loaded")
    
    # On message
    @commands.Cog.listener()
    async def on_message(self, message):
        trig_data = load(trigger_file, {})
        if message.guild is not None:
            guild_id = message.guild.id
            
            if f"{guild_id}" not in trig_data:
                collection = db["msg_manip"]
                result = collection.find_one(
                    {"_id": guild_id}
                )
                trig = get_field(result, "trigger")
                rep = get_field(result, "reply")
                trig_data.update([(f"{guild_id}", {"trigger": trig, "reply": rep})])

                save(trig_data, trigger_file)
            else:
                trig = trig_data[f"{guild_id}"]["trigger"]
                rep = trig_data[f"{guild_id}"]["reply"]
            
            text = message.content.lower()
            if trig is not None and rep is not None and trig in text:
                reply = discord.Embed(
                    description=rep,
                    color=message.author.color
                )
                await message.channel.send(embed=reply)

    #========= Commands ===========
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.command(aliases=["set", "how-set", "hs"])
    async def how_set(self, ctx):
        server = ServerConfig(ctx.guild.id)

        mr_desc = ""
        for mr in server.mod_roles:
            mr_desc += f"> **<@&{mr}>**\n"
        if mr_desc == "":
            mr_desc = "> Отсутствуют"
        
        if server.log_channel is not None:
            log_desc = f"> <#{server.log_channel}>"
        else:
            log_desc = "> Отсутствует"

        reply = discord.Embed(
            title=":gear: | Текущие настройки",
            color=ctx.guild.me.color
        )
        reply.add_field(name="🛠 Роли модераторов", value=mr_desc)
        reply.add_field(name="📋 Канал логов", value=log_desc)
        reply.set_thumbnail(url=f"{ctx.guild.icon_url}")
        await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["add-mod-role", "add-moderator-role", "amr"],
        description="настраивает роль модератора на сервере",
        usage="Роль",
        brief="@Moderator" )
    async def add_mod_role(self, ctx, role: discord.Role):
        server = ServerConfig(ctx.guild.id, {"mod_roles": True})
        server.clear_outdated_roles(ctx.guild.roles)
        if len(server.mod_roles) >= mod_role_limit:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description=(
                    f"Добавлено слишком много ролей модераторов: {mod_role_limit}\n"
                    f"Убрать лишнюю: `{ctx.prefix}remove-mod-role`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

        else:
            server.add_mod_role(role.id)
            reply = discord.Embed(
                title="✅ Выполнено",
                description=f"Добавлена роль модератора: **<@&{role.id}>**",
                color=discord.Color.dark_green()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
    

    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["remove-mod-role", "remove-moderator-role", "rmr"],
        description="убирает роль модератора с сервера",
        usage="Роль",
        brief="@Moderator" )
    async def remove_mod_role(self, ctx, role: discord.Role):
        server = ServerConfig(ctx.guild.id, {"mod_roles": True})

        if role.id not in server.mod_roles:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description=f"Роль **<@&{role.id}>** не является модераторской.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

        else:
            server.remove_mod_role(role.id)
            reply = discord.Embed(
                title="✅ Выполнено",
                description=f"Убрана роль модератора: **<@&{role.id}>**",
                color=discord.Color.dark_green()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["set-currency", "set-cur", "setcur"],
        description="настраивает значок валюты",
        usage="Значок",
        brief="✨" )
    async def set_currency(self, ctx, string):
        p = ctx.prefix
        string = string[:+52]
        collection = db["items"]
        collection.find_one_and_update(
            {"_id": ctx.guild.id},
            {"$set": {"cy": string}},
            upsert=True
        )
        reply = discord.Embed(
            title="✅ Выполнено",
            description=(
                f"Новый значок валюты: {string}\n\n"
                f"Текущие настройки: `{p}how-set`"
            ),
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["work-range"],
        description="настраивает диапазон заработка с команды `timely`",
        usage="Мин.заработок Макс.заработок",
        brief="300 700" )
    async def work_range(self, ctx, lower_bound, upper_bound):
        p = ctx.prefix
        if not lower_bound.isdigit() or not upper_bound.isdigit():
            reply = discord.Embed(
                title="💢 Ошибка",
                description=(
                    "Минимальный и максимальный заработок должны быть целым числом.\n"
                    f"Пример: `{p}work-range 200 500`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        elif int(lower_bound) >= int(upper_bound):
            reply = discord.Embed(
                title="💢 Ошибка",
                description=(
                    "Минимальный заработок должен быть меньше максимального.\n"
                    f"Пример: `{p}work-range 200 500`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

        else:
            lower_bound, upper_bound = int(lower_bound), int(upper_bound)
            collection = db["money"]
            result = collection.find_one_and_update(
                {"_id": ctx.guild.id},
                {"$set": {"work_range": (lower_bound, upper_bound)}},
                upsert=True,
                projection={"cur": True}
            )
            cur = get_field(result, "cur")
            if cur is None:
                cur = "🕸️"
            
            reply = discord.Embed(
                title=f"✅ Настроено",
                description=(
                    f"Теперь команда `{p}work` приносит от **{lower_bound}** до **{upper_bound}** {cur}\n\n"
                    f"Текущие настройки: `{p}how-set`"
                ),
                color=discord.Color.dark_green()
            )
            await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["trig", "t"],
        description="настраивает триггер, провоцирующий ответ бота",
        usage="текст\ndelete",
        brief="привет" )
    async def trigger(self, ctx, *, string):
        p = ctx.prefix
        if string.lower() == "delete":
            desc = "Триггер сообщений удалён"
            string = None
        else:
            string = string[:+500].lower()
            desc = f"Теперь бот отслеживает сообщения с \"{string}\""

        collection = db["msg_manip"]
        collection.find_one_and_update(
            {"_id": ctx.guild.id},
            {"$set": {"trigger": string}},
            upsert=True
        )
        data = load(trigger_file, {})
        if f"{ctx.guild.id}" in data:
            data[f"{ctx.guild.id}"]["trigger"] = string
            save(data, trigger_file)

        reply = discord.Embed(
            title="✅ Выполнено",
            description=(
                f"{desc}\n\n"
                f"Текущие настройки: `{p}how-set`"
            ),
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["trigger-reply", "trig-reply", "tr"],
        description="настраивает ответ бота на сообщения с триггером (подробнее в команде `trigger`)",
        usage="текст\ndelete",
        brief="Здравствуй" )
    async def trigger_reply(self, ctx, *, text):
        p = ctx.prefix
        if text.lower() == "delete":
            desc = "Ответ на сообщения с определённым триггером удалён."
            text = None
        else:
            text = text[:+500]
            desc = f"Ответ на сообщения с определённым триггером:\n{text}"

        collection = db["msg_manip"]
        collection.find_one_and_update(
            {"_id": ctx.guild.id},
            {"$set": {"reply": text}},
            upsert=True
        )
        data = load(trigger_file, {})
        if f"{ctx.guild.id}" in data:
            data[f"{ctx.guild.id}"]["reply"] = text
            save(data, trigger_file)

        reply = discord.Embed(
            title="✅ Выполнено",
            description=(
                f"{desc}\n\n"
                f"Текущие настройки: `{p}how-set`"
            ),
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)

    # +---------------------------------------+
    # |            Group: welcome             |
    # +---------------------------------------+
    @commands.check_any(
        commands.has_permissions(administrator=True),
        is_moderator() )
    @commands.group()
    async def welcome(self, ctx):
        p = ctx.prefix
        if ctx.invoked_subcommand is None:
            reply = discord.Embed(
                title="❌ Ошибка",
                description=(
                    "Укажите одну их этих категорий:\n"
                    f"> `{p}{ctx.command} channel`\n"
                    f"> `{p}{ctx.command} message`\n"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
    
    @welcome.command(
        description="настраивает канал для приветствий",
        usage="channel #канал" )
    async def channel(self, ctx, *, channel: discord.TextChannel):
        collection = db["msg_manip"]
        collection.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"welcome_channel": channel.id}},
            upsert=True
        )
        reply = discord.Embed(
            title="✅ Выполнено",
            description=f"Теперь <#{channel.id}> - канал для приветствий.",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    

    @welcome.command(
        description="настраивает приветственное сообщение",
        usage="message Текст",
        brief=(
            "Добро пожаловать на сервер {server}\n"
            "Привет, {user}\n"
            "Ты участник под номером {member_count}!"
        ) )
    async def message(self, ctx, *, text):
        collection = db["msg_manip"]
        collection.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"welcome_message": text}},
            upsert=True
        )
        reply = discord.Embed(
            title="✅ Выполнено",
            description=f"**Новое приветственное сообщение:**\n{text}",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

    # +---------------------------------------+
    # |                Errors                 |
    # +---------------------------------------+

def setup(client):
    client.add_cog(settings(client))