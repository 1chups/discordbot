import discord
from discord.ext import commands
import asyncio, random

#----------------------------------------------+
#                 Constants                    |
#----------------------------------------------+
from functions import timeout_embed, CustomColor
from failures import CooldownResetSignal

colors = CustomColor()
inv_capacity = 100
item_limit = 500
case_limit = 500
mkkey_tout = 60
name_limit = 52
edit_item_params = {
    "name": {
        "desc": "изменяет название шмота",
        "usage": "[Старое название] Новое название",
        "example": "[Футболка] Рубашка"
    },
    "price": {
        "desc": "изменяет цену шмотки",
        "usage": "[Название] Число",
        "example": "[Футболка] 100"
    },
    "role": {
        "desc": "привязывает роль к шмотке (при покупке будет даваться роль)",
        "usage": "[Название] Роль",
        "example": "[Футблока] @Покупатель"
    },
    "icon": {
        "desc": "настраивает иконку шмотки",
        "usage": "[Название] (прикрепить картинку или URL)",
        "example": "[Футболка] (прикрепить картинку или URL)"
    }
}
work_replies = [
    "Вы получили свой бонус в размере {earning}"
]


#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import is_moderator, find_alias, antiformat as anf, carve_cmd
from db_models import CustomerList, Customer, ItemStorage
from custom_converters import IntConverter


def isfloat(string: str):
    try:
        float(string)
    except Exception:
        return False
    else:
        return True


def unpack_args(string):
    if isinstance(string, str):
        if string[0] == "[":
            pair = string[1:].rsplit("]", maxsplit=1)
            if len(pair) < 2:
                pair = string.split(maxsplit=1)
        else:
            pair = string.split(maxsplit=1)
        if len(pair) < 2:
            return pair[0].strip(), None
        else:
            return pair[0].strip(), pair[1].strip()
    else:
        return None, None


def unpack_case_args(string):
    if string is None:
        return (None, None)
    else:
        pair = string.split(maxsplit=1)
        if len(pair) < 2:
            return (None, pair[0])
        else:
            pair[0].rstrip("%")
            if not isfloat(pair[0]):
                return (None, pair[1])
            elif float(pair[0]) <= 0:
                return (None, pair[1])
            else:
                return (float(pair[0]), pair[1])


def dupe_dump(array: list):
    out = {}
    for elem in array:
        if elem not in out:
            out[elem] = 1
        else:
            out[elem] += 1
    return out


def wordlike_rarities(percentages: list):
    words = []
    for p in percentages:
        if 0 < p <= 1:
            words.append("Легендарный")
        elif 1 < p <=5:
            words.append("Мистический")
        elif 5 < p <= 20:
            words.append("Эпический")
        elif 20 < p <= 50:
            words.append("Редкий")
        else:
            words.append("Обычный")
    return words


async def better_add_role(member, role):
    if isinstance(role, int):
        role = member.guild.get_role(role)
    if role is not None and role not in member.roles:
        try:
            await member.add_roles(role)
        except Exception:
            pass


class economy(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                Cog methods                   |
    #----------------------------------------------+
    async def ask_to_choose(self, ctx, _choice: list):
        """Returns chosen index or None"""
        interruption_keys = [ctx.command.name, *ctx.command.aliases]
        channel = ctx.channel; user = ctx.author; prefix = ctx.prefix
        del ctx
        tout = 60
        desc = ""
        for i, row in enumerate(_choice):
            desc += f"`{i + 1}.` {row}\n"
        emb = discord.Embed(
            title="🔎 | Результаты поиска",
            description=f"Найдено несколько результатов, пожалуйста, напишите **номер** подходящего:\n\n{desc}"
        )
        emb.set_footer(text=f"{user}", icon_url=f"{user.avatar_url}")
        botmsg = await channel.send(embed=emb)

        def check(m):
            return ( carve_cmd(prefix, m.content) in interruption_keys or
            (m.author.id == user.id and m.channel.id == channel.id and m.content.isdigit() and 0 < int(m.content) <= len(_choice)) )

        try:
            msg = await self.client.wait_for("message", check=check, timeout=tout)
        except asyncio.TimeoutError:
            await channel.send(embed=timeout_embed(tout, user))
        else:
            try:
                await botmsg.delete()
            except Exception:
                pass
            if carve_cmd(prefix, msg.content) not in interruption_keys:
                return int(msg.content) - 1

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(">> Economy cog is loaded")
    
    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    # Item related commands
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["create-item", "ci", "createitem"],
        description="создаёт новую шмотку на сервере",
        usage="Цена Название",
        brief="100 Фтуболка" )
    async def create_item(self, ctx, price: IntConverter, *, name):
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True})
        if len(server.items) >= item_limit:
            reply = discord.Embed(
                title="❌ | Переполнение",
                description=f"Создано слишком много шмоток - {item_limit}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif price < 0:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description=f"Цена шмотки не может быть отрицательной",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        else:
            server.create_item(ctx.message.id, name[:name_limit], price)
            desc = (
                f"Вы создали новую шмотку - **{name}**.\n"
                f"**Цена:** {price} {server.cy}\n"
                f"**Редактировать:** `{ctx.prefix}edit-item`"
            )
            if len(name) > name_limit:
                desc += f"\n\n*Название превышало {name_limit} символов в длину и было обрезано*"
            reply = discord.Embed(
                title="📦 | Новая вещь",
                description=desc,
                color=discord.Color.blue()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

    
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["edit-item", "ei", "edititem"],
        description="изменяет некоторые характеристики шмотки. Параметры:\n`name`, `price`, `role`, `icon`",
        usage="параметр [Название] Новое значние",
        brief=(
            "name [Старое название] Новое название\n"
            "price [Название] Новая цена\n"
            "role [Название] Роль\n"
            "icon [Название] (картинка)") )
    async def edit_item(self, ctx, param, *, string=None):
        search, value = unpack_args(string)
        atts = ctx.message.attachments
        p = ctx.prefix; cmd = str(ctx.invoked_with)
        params = {
            "name": ["название"],
            "price": ["цена"],
            "role": ["роль"],
            "icon": ["image", "avatar", "картинка"]
        }
        parameter = find_alias(params, param)
        if parameter is None:
            desc = ""
            for par in params:
                desc += f"> `{p}{cmd} {par}`\n"
            reply = discord.Embed(
                title="❌ | Неверный параметр",
                description=f"Параметра '{param}' не существует, попробуйте эти:\n{desc}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

        elif value is None and not (parameter == "icon" and atts != []):
            _help_ = edit_item_params[parameter]
            reply = discord.Embed(
                title=f"❓ | О параметре `{p}{cmd} {parameter}`",
                description=(
                    f"**Описание:** {_help_['desc']}\n"
                    f"**Использование:** `{p}{cmd} {parameter} {_help_['usage']}`\n"
                    f"**Пример:** `{p}{cmd} {parameter} {_help_['example']}`"
                )
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

        else:
            server = ItemStorage(ctx.guild.id, projection={"items"})
            items = server.search_items(search)
            item = None
            if len(items) == 0:
                reply = discord.Embed(
                    title="❌ | Вещь не найдена",
                    description=f"По поиску '{search}' не было найдено шмоток.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)

            elif len(items) < 2:
                item = items[0]
            else:
                ind = await self.ask_to_choose(ctx, [it.name for it in items])
                if ind is not None:
                    item = items[ind]
            
            if item is not None:
                updated = True
                if parameter == "name":
                    item.set_name(value[:name_limit])
                    item.name = value[:name_limit]
                elif parameter == "price":
                    if not value.isdigit():
                        updated = False
                        reply = discord.Embed(
                            title="❌ | Неверный аргумент",
                            description=f"Вместо '{value}' введите целое число",
                            color=discord.Color.dark_red()
                        )
                        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                        await ctx.send(embed=reply)
                    else:
                        item.set_price(int(value))
                elif parameter == "role":
                    role = await commands.RoleConverter().convert(ctx, value)
                    item.set_role(role.id)
                elif parameter == "icon":
                    if atts != []:
                        value = atts[0].url
                    item.set_icon_url(value)
                
                if updated:
                    reply = discord.Embed(
                        title="🔁 | Вещь обновлена",
                        description=f"Посмотреть подробнее: `{p}view-item {item.name}`",
                        color=discord.Color.blue()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["delete-item", "deleteitem", "di"],
        description="удаляет шмотку",
        usage="Название шмотки",
        brief="Футболка" )
    async def delete_item(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True})
        items = server.search_items(search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Visualising item
        if item is not None:
            item.delete()
            reply = discord.Embed(
                title="📦 | Удалена вещь",
                description=f"Шмотка {item.name} была удалена с сервера.",
                color=discord.Color.dark_blue()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["give-item", "giveitem", "gi"],
        description="выдаёт шмотку",
        usage="[Название шмотки] @Игрок (себя можно не тегать)",
        brief="[Футболка] @Player#0000" )
    async def give_item(self, ctx, *, string):
        search, member_s = unpack_args(string)
        if member_s is None:
            member = ctx.author
        else:
            member = await commands.MemberConverter().convert(ctx, member_s)
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True})
        items = server.search_items(search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Giving item
        if item is not None:
            customer = Customer(ctx.guild.id, member.id)
            if len(customer.raw_items) >= item_limit:
                reply = discord.Embed(
                    title="❌ | Недостаточно места",
                    description=f"Инвентарь **{member}** переполнен - в нём **{item_limit}** шмоток.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            else:
                customer.give_item(item)
                reply = discord.Embed(
                    title="📦 | Выдана шмотка",
                    description=f"Игрок **{member}** получил **{item.name}** себе в инвентарь.",
                    color=discord.Color.dark_blue()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
                await ctx.message.delete()


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["add-key", "ak", "addkey"],
        description="добавляет к шмотке ключ от кейса",
        usage="[Шмотка] Кейс",
        brief="[Футболка] Кейс с одеждой" )
    async def add_key(self, ctx, *, string):
        # Searching item
        item_search, case_search = unpack_args(string)
        if case_search is None:
            raise commands.MissingRequiredArgument("case_name")

        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})
        items = server.search_items(item_search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{item_search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Searching case
        if item is not None:
            cases = server.search_cases(case_search)
            case = None
            if len(cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(cases) < 2:
                case = cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in cases])
                if ind is not None:
                    case = cases[ind]
            
            if case is not None:
                item.bind_case(case.id)
                reply = discord.Embed(
                    title="🔑 | Добавлен ключ",
                    description=f"Теперь {item.name} открывает кейс {case.name}",
                    color=colors.cardboard
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
    
    
    @commands.cooldown(1, case_limit * mkkey_tout, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["remove-key", "remk", "removekey"],
        description="добавляет к шмотке ключ от кейса",
        usage="[Шмотка] Кейс",
        brief="[Футболка] Кейс с одеждой" )
    async def remove_key(self, ctx, *, string):
        # Searching item
        item_search, case_search = unpack_args(string)
        if case_search is None:
            raise commands.MissingRequiredArgument("case_name")

        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})
        items = server.search_items(item_search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{item_search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Searching case
        if item is not None:
            cases = server.search_cases(case_search)
            case = None
            if len(cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(cases) < 2:
                case = cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in cases])
                if ind is not None:
                    case = cases[ind]
            
            if case is not None:
                if case.id not in item.key_for:
                    reply = discord.Embed(
                        title="❌ | Такой ключ не найден",
                        description=f"{item.name} не является ключом для {case.name}.",
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                else:
                    item.unbind_case(case.id)
                    reply = discord.Embed(
                        title="🔑 | Убран ключ",
                        description=f"Теперь {item.name} не открывает кейс {case.name}",
                        color=colors.cardboard
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
        
        raise CooldownResetSignal()

    
    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["view-items", "all-items", "item-list"])
    async def items(self, ctx, page: IntConverter=1):
        interval = 10
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True})
        total_items = len(server.items)
        total_pages = abs(total_items - 1) // interval + 1
        if page > total_pages or page < 1:
            reply = discord.Embed(
                title="❌ | Страница не найдена",
                description=f"Всего страниц: {total_pages}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

        else:
            if total_items == 0:
                desc = "Отсутствуют"
            else:
                cy = server.cy
                items = sorted(server.items, key=lambda item: item.price)
                del server
                lb = (page - 1) * interval
                ub = min(page * interval, total_items)

                desc = ""
                for i in range(lb, ub):
                    item = items[i]
                    desc += f"`{i + 1}.` **{item.name}** | {item.price} {cy}\n"
            reply = discord.Embed(
                title=f"📦 | Шмотки сервера",
                description=desc,
                color=discord.Color.blue()
            )
            reply.set_footer(text=f"Стр. {page} / {total_pages} | {ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
            await ctx.message.delete()


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["view-item", "viewitem", "vi", "item"],
        description="показывает информацию о шмотке",
        usage="Название шмотки",
        brief="Футболка" )
    async def view_item(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})
        items = server.search_items(search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Visualising item
        if item is not None:
            reply = discord.Embed(
                title=f"📦 | {item.name}",
                color=discord.Color.blue()
            )

            if item.icon_url is not None:
                reply.set_thumbnail(url=item.icon_url)
            reply.add_field(name="Цена", value=f"> {item.price} {server.cy}", inline=False)
            if item.role is not None:
                reply.add_field(name="Роль", value=f"> <@&{item.role}>", inline=False)
            if item.key_for != []:
                desc = ""
                for case in server.cases:
                    if case.id in item.key_for:
                        desc += f"> {case.name}\n"
                reply.add_field(name="Ключи", value=desc, inline=False)
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")

            try:
                await ctx.send(embed=reply)
            except Exception:
                del reply.thumbnail
                await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["sell-item", "sellitem", "sell"],
        description="продаёт шмотку",
        usage="Название шмотки Количество (не обязательно)",
        brief="Футболка\nФтуболка 3\nall (продать всё)" )
    async def sell_item(self, ctx, *, search):
        customer = Customer(ctx.guild.id, ctx.author.id)
        arsearch = search.rsplit(maxsplit=1)
        search2 = ""
        num = 1
        if len(arsearch) > 1 and arsearch[1].isdigit():
            search2 = search
            search = arsearch[0]; num = int(arsearch[1])
        items = customer.search_item(search)

        if search.lower() == "all" and items == []:
            cy = ItemStorage(ctx.guild.id, {"cy": True}).cy
            earning = customer.sell_all_items()
            reply = discord.Embed(
                title="📦 | Проданы все шмотки",
                description=f"Вы продали весь свой инвентарь на сумму **{earning}** {cy}",
                color=discord.Color.dark_blue()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

        else:
            item = None
            if len(items) == 0:
                reply = discord.Embed(
                    title="❌ | Вещь не найдена",
                    description=f"По запросу '{search}' в Вашем инвентаре не было найдено шмоток.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(items) < 2:
                item = items[0]
            else:
                ind = await self.ask_to_choose(ctx, [it.name for it in items])
                if ind is not None:
                    item = items[ind]
            del items
            # Giving item
            if item is not None:
                if item.name.lower() == search2.lower():
                    num = 1
                
                x_item = customer.raw_items.count(item.id)
                if num > x_item:
                    num = x_item
                customer.sell_item(item, num)
                reply = discord.Embed(
                    title="📦 | Продана шмотка",
                    description=f"Вы продали **{item.name}** (x{num}) и стали богаче на **{item.price * num}**",
                    color=discord.Color.dark_blue()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
                await ctx.message.delete()


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["use-item", "useitem", "use"],
        description="Использует шмотку. При этом начисляются прикреплённые к шмотке ключи и выдаётся роль шмотки (при наличии)",
        usage="Название шмотки Количество (не обязательно)",
        brief="Футболка\nФутболка 3" )
    async def use_item(self, ctx, *, search):
        customer = Customer(ctx.guild.id, ctx.author.id)
        arsearch = search.rsplit(maxsplit=1)
        search2 = ""
        num = 1
        if len(arsearch) > 1 and arsearch[1].isdigit():
            search2 = search
            search = arsearch[0]; num = int(arsearch[1])
        items = customer.search_item(search)

        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По запросу '{search}' в Вашем инвентаре не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Giving item
        if item is not None:
            if item.name.lower() == search2.lower():
                num = 1
            
            if item.key_for == [] and item.role is None:
                reply = discord.Embed(
                    title="❌ | Вещь не имеет свойств",
                    description=f"**{item.name}** не имеет прикреплённых ключей или роли.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            else:
                max_num = customer.raw_items.count(item.id)
                if num > max_num:
                    num = max_num
                new_keys = customer.use_item(item, num)
                await better_add_role(ctx.author, item.role)

                desc = ""
                if new_keys != []:
                    desc += f"> **Ключей:** {len(new_keys)} 🔑\n"
                if item.role is not None:
                    desc += f"> **Роль <@&{item.role}>**\n"
                reply = discord.Embed(
                    title="📦 | Использована шмотка",
                    description=(
                        f"Вы использовали **{item.name}** (x{num}) и получили\n"
                        f"{desc}\n"
                        f"*Ваш инвентарь: `{ctx.prefix}inv`*"
                    ),
                    color=discord.Color.dark_blue()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
                await ctx.message.delete()

    # Case related commands
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["create-case", "cc", "createcase"],
        description="создаёт новый кейс на сервере",
        usage="Название",
        brief="Фтуболка" )
    async def create_case(self, ctx, *, name):
        server = ItemStorage(ctx.guild.id, {"cases": True})
        if len(server.cases) >= case_limit:
            reply = discord.Embed(
                title="❌ | Переполнение",
                description=f"Создано слишком много кейсов - {case_limit}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        else:
            server.create_case(ctx.message.id, name[:name_limit])
            desc = f"Вы создали новый кейс - {name}.\n**Добавить лут:** `{ctx.prefix}add-loot`\n"
            if len(name) > name_limit:
                desc += f"*Название превышало {name_limit} символов в длину и было обрезано*"
            reply = discord.Embed(
                title="📦 | Новый кейс",
                description=desc,
                color=colors.cardboard
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["delete-case", "deletecase", "delc"],
        description="удаляет кейс",
        usage="Название кейса",
        brief="Кейс Одежды" )
    async def delete_case(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"cases": True})
        cases = server.search_cases(search)
        case = None
        if len(cases) == 0:
            reply = discord.Embed(
                title="❌ | Кейс не найден",
                description=f"По поиску '{search}' не было найдено кейсов.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(cases) < 2:
            case = cases[0]
        else:
            ind = await self.ask_to_choose(ctx, [c.name for c in cases])
            if ind is not None:
                case = cases[ind]
        del cases
        # Visualising item
        if case is not None:
            case.delete()
            reply = discord.Embed(
                title="📦 | Удален кейс",
                description=f"Кейс {case.name} был удалён с сервера.",
                color=colors.cardboard
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["add-loot", "addloot", "addl"],
        description="Добавляет лут в кейс. Далее `Вес` будет влиять на шанс выпадения. Чем больше вес - тем выше шанс.",
        usage="[Название кейса] Вес Название_шмотки",
        brief="[Кейс Одежды] 50 Футболка\n[Кейс Одежды] 50 Рубашка" )
    async def add_loot(self, ctx, *, string):
        # Unpacking arguments
        case_search, caseargs = unpack_args(string)
        weight, item_search = unpack_case_args(caseargs)
        if None in [weight, item_search]:
            reply = discord.Embed(
                title="❌ | Недостаточно аргументов",
                description=(
                    f"В качестве кейса Вы указали `{case_search}`. После него нужно указать `Вес` и `Шмотку`, прчём `вес` должен быть числом больше нуля.\n"
                    f"Пример: `{ctx.prefix}add-loot [Некий кейс] 10 Некая шмотка`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            # Searching case
            server = ItemStorage(ctx.guild.id, {"items": True, "cases": True})
            _cases = server.search_cases(case_search)
            case = None
            if len(_cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(_cases) < 2:
                case = _cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in _cases])
                if ind is not None:
                    case = _cases[ind]
            del _cases
            if case is not None:
                # Searching item
                items = server.search_items(item_search)
                item = None
                if len(items) == 0:
                    reply = discord.Embed(
                        title="❌ | Вещь не найдена",
                        description=f"По поиску '{item_search}' не было найдено шмоток.",
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                elif len(items) < 2:
                    item = items[0]
                else:
                    ind = await self.ask_to_choose(ctx, [it.name for it in items])
                    if ind is not None:
                        item = items[ind]
                del items
                # Adding item to the case
                if item is not None:
                    case.add_item(item.id, weight)
                    reply = discord.Embed(
                        title="🔑 | Добавлен лут",
                        description=(
                            f"Теперь **{item.name}** выпадает из кейса **{case.name}** с весом {weight}.\n"
                            f"Просмотреть кейс: `{ctx.prefix}case {case.name}`"
                        ),
                        color=colors.cardboard
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["rename-case", "renamecase", "renc"],
        description="изменяет название кейса.",
        usage="[Старое название] Новое название",
        brief="[Кейс Одежды] Кейс с одеждой" )
    async def rename_case(self, ctx, *, string):
        # Unpacking arguments
        case_search, new_name = unpack_args(string)
        if new_name is None:
            reply = discord.Embed(
                title="❌ | Недостаточно аргументов",
                description=(
                    f"В качестве кейса Вы указали `{case_search}`. После него нужно указать новое название.\n"
                    f"Пример: `{ctx.prefix}rename-case [Старое название] Новое название`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            new_name = new_name[:name_limit]
            # Searching case
            server = ItemStorage(ctx.guild.id, {"cases": True})
            _cases = server.search_cases(case_search)
            case = None
            if len(_cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(_cases) < 2:
                case = _cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in _cases])
                if ind is not None:
                    case = _cases[ind]
            del _cases
            if case is not None:
                # Renaming case
                case.set_name(new_name)
                reply = discord.Embed(
                    title="📦 | Кейс переименован",
                    description=(
                        f"Теперь **{case.name}** называется **{new_name}**.\n"
                        f"Просмотреть кейс: `{ctx.prefix}case {new_name}`"
                    ),
                    color=colors.cardboard
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["case-icon", "caseicon"],
        description="изменяет иконку кейса.",
        usage="[Название] (Прикрепить картинку или URL)",
        brief="[Кейс Одежды] (Картинка или URL)" )
    async def case_icon(self, ctx, *, string):
        # Unpacking arguments
        case_search, url = unpack_args(string)
        atts = ctx.message.attachments
        if atts != []:
            url = atts[0].url
        if url is None:
            reply = discord.Embed(
                title="❌ | Недостаточно аргументов",
                description="Вы указали название кейса, но не прикрепили **картинку** или **ссылку**, которую вы бы хотели сделать иконкой кейса.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            # Searching case
            server = ItemStorage(ctx.guild.id, {"cases": True})
            _cases = server.search_cases(case_search)
            case = None
            if len(_cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(_cases) < 2:
                case = _cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in _cases])
                if ind is not None:
                    case = _cases[ind]
            del _cases
            if case is not None:
                # Setting new url
                case.set_icon_url(url)
                reply = discord.Embed(
                    title="📦 | Иконка кейса изменена",
                    description=(
                        f"Кейс: **{case.name}**\n"
                        f"Просмотреть кейс: `{ctx.prefix}case {case.name}`"
                    ),
                    color=colors.cardboard
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["remove-loot", "removeloot", "reml"],
        description="Убирает шмотку из кейса.",
        usage="[Название кейса] Название_шмотки",
        brief="[Кейс Одежды] Футболка" )
    async def remove_loot(self, ctx, *, string):
        # Unpacking arguments
        case_search, item_search = unpack_args(string)
        if item_search is None:
            reply = discord.Embed(
                title="❌ | Недостаточно аргументов",
                description=(
                    f"В качестве кейса Вы указали `{case_search}`. После него нужно указать `Шмотку`.\n"
                    f"Пример: `{ctx.prefix}remove-loot [Некий кейс] Некая шмотка`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            # Searching case
            server = ItemStorage(ctx.guild.id, {"items": True, "cases": True})
            _cases = server.search_cases(case_search)
            case = None
            if len(_cases) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс не найден",
                    description=f"По поиску '{case_search}' не было найдено кейсов.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(_cases) < 2:
                case = _cases[0]
            else:
                ind = await self.ask_to_choose(ctx, [c.name for c in _cases])
                if ind is not None:
                    case = _cases[ind]
            del _cases
            if case is not None:
                # Searching item
                items = case.search_item(item_search)
                item = None
                if len(items) == 0:
                    reply = discord.Embed(
                        title="❌ | Вещь не найдена",
                        description=f"По запросу '{item_search}' в кейсе **{case.name}** не было найдено шмоток.",
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                elif len(items) < 2:
                    item = items[0]
                else:
                    ind = await self.ask_to_choose(ctx, [it.name for it in items])
                    if ind is not None:
                        item = items[ind]
                del items
                # Removing item from the case
                if item is not None:
                    case.remove_item(item.id)
                    reply = discord.Embed(
                        title="🔑 | Убран лут",
                        description=(
                            f"Теперь **{item.name}** больше не выпадает из кейса **{case.name}**.\n"
                            f"Просмотреть кейс: `{ctx.prefix}case {case.name}`"
                        ),
                        color=colors.cardboard
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["case-config", "caseconfig", "case-conf"],
        description="показывает текущие настройки кейса",
        usage="Название кейса",
        brief="Кейс Одежды" )
    async def case_config(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})
        cases = server.search_cases(search)
        case = None
        if len(cases) == 0:
            reply = discord.Embed(
                title="❌ | Кейс не найден",
                description=f"По поиску '{search}' не было найдено кейсов.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(cases) < 2:
            case = cases[0]
        else:
            ind = await self.ask_to_choose(ctx, [c.name for c in cases])
            if ind is not None:
                case = cases[ind]
        del cases
        if case is not None:
            # Visualising item
            prcs = case.percentage
            desc = ""
            for i, pair in enumerate(case.loot):
                desc += f"{pair[0].name} | `Вес: {pair[1]}` | `~{prcs[i]} %`\n"
            if desc == "":
                desc = "Нет лута"
            if case is not None:
                reply = discord.Embed(
                    title=f"📦 | {case.name}",
                    color=colors.cardboard
                )
                reply.add_field(name="Шмотка | `Вес` | `Процент (исходя из веса)`", value=desc, inline=False)
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                if case.icon_url is not None:
                    reply.set_thumbnail(url=case.icon_url)
                await ctx.send(embed=reply)


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["view-cases", "all-cases", "case-list"])
    async def cases(self, ctx):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"cases": True})
        desc = ""
        for case in server.cases:
            desc += f"• **{case.name}**\n"
        if desc == "":
            desc = "Отсутствуют"
        reply = discord.Embed(
            title=f"📦 | Кейсы сервера",
            description=desc,
            color=colors.cardboard
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)
        await ctx.message.delete()


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["view-case", "viewcase", "vc", "case"],
        description="показывает информацию о кейсе",
        usage="Название кейса",
        brief="Кейс Одежды" )
    async def view_case(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})
        cases = server.search_cases(search)
        case = None
        if len(cases) == 0:
            reply = discord.Embed(
                title="❌ | Кейс не найден",
                description=f"По поиску '{search}' не было найдено кейсов.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(cases) < 2:
            case = cases[0]
        else:
            ind = await self.ask_to_choose(ctx, [c.name for c in cases])
            if ind is not None:
                case = cases[ind]
        del cases
        if case is not None:
            # Visualising item
            rars = wordlike_rarities(case.percentage)
            desc = ""
            for i, pair in enumerate(case.loot):
                desc += f"• {pair[0].name} | `{rars[i]}`\n"
            if desc == "":
                desc = "Нет лута"
            if case is not None:
                reply = discord.Embed(
                    title=f"📦 | {case.name}",
                    color=colors.cardboard
                )
                reply.add_field(name="Содержимое", value=desc, inline=False)
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                if case.icon_url is not None:
                    reply.set_thumbnail(url=case.icon_url)
                await ctx.send(embed=reply)
                await ctx.message.delete()


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["open-case", "opencase", "oc", "open"],
        description="вскрывает кейс(ы), при условии, что у Вас есть ключ(и)",
        usage="Название кейса Количество (не обязательно)",
        brief="Кейс Одежды\nКейс Одежды 5" )
    async def open_case(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "cy": True, "cases": True})

        arsearch = search.rsplit(maxsplit=1)
        search2 = ""
        num = 1
        if len(arsearch) > 1 and arsearch[1].isdigit():
            search2 = search
            search = arsearch[0]; num = int(arsearch[1])
        cases = server.search_cases(search)
        case = None
        if len(cases) == 0:
            reply = discord.Embed(
                title="❌ | Кейс не найден",
                description=f"По поиску '{search}' не было найдено кейсов.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(cases) < 2:
            case = cases[0]
        else:
            ind = await self.ask_to_choose(ctx, [c.name for c in cases])
            if ind is not None:
                case = cases[ind]
        del cases
        if case is not None:
            if case.name.lower() == search2.lower():
                num = 1
            # Looking at player's inventory
            customer = Customer(ctx.guild.id, ctx.author.id)
            if case.id not in customer.keys:
                reply = discord.Embed(
                    title="❌ | Нет ключа",
                    description=f"В Вашем инвентаре нет ключа от кейса **{case.name}**.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(case.loot) == 0:
                reply = discord.Embed(
                    title="❌ | Кейс пуст",
                    description=f"Кейс **{case.name}** пока что пуст, его невозможно открыть.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            elif len(customer.raw_items) >= inv_capacity:
                reply = discord.Embed(
                    title="❌ | Недостаточно места",
                    description=f"Ваш инвентарь переполнен - в нём {item_limit} шмоток. Продайте лишнее и попробуйте снова.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            else:
                items = customer.open_case(case, num)
                items = dupe_dump(items)
                desc = ""
                for item, x in items.items():
                    desc += f"x{x} | **{item.name}** • {item.price} {server.cy}\n"

                reply = discord.Embed(
                    title=f"📦 | Вскрыт кейс {case.name}",
                    description=f"**Выпавший дроп:**\n{desc[:2000]}",
                    color=colors.cardboard
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
                await ctx.message.delete()
    
    # Shop related commandы
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["shop-add"],
        description="добавляет шмотку в магазин сервера.",
        usage="Название шмотки",
        brief="Футболка" )
    async def shop_add(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "shop": True})
        items = server.search_items(search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Visualising item
        if item is not None:
            if item.id in server.raw_shop:
                reply = discord.Embed(
                    title="❌ | Вещь уже есть в магазине",
                    description=f"Шмотка **{item.name}** уже продаётся в магазине.",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)

            else:
                server.add_to_shop(item.id)
                reply = discord.Embed(
                    title=f"🛒 | Вещь добавлена в магазин",
                    description=f"**{item.name}** теперь продаётся в магазине",
                    color=discord.Color.green()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["shop-remove"],
        description="убирает шмотку из магазина сервера.",
        usage="Название шмотки",
        brief="Футболка" )
    async def shop_remove(self, ctx, *, search):
        # Searching item
        shop = ItemStorage(ctx.guild.id, {"items": True, "shop": True}).shop
        items = shop.search_item(search)
        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' в магазине не было найдено шмоток.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Visualising item
        if item is not None:
            shop.remove_item(item.id)
            reply = discord.Embed(
                title=f"🛒 | Вещь убрана из магазина",
                description=f"**{item.name}** больше не продаётся в магазине.",
                color=discord.Color.green()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["shop-clear"] )
    async def shop_clear(self, ctx):
        # Verifying deletion
        yes = ["да", "yes", "1"]; no = ["нет", "no", "0"]
        tout = 60
        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() in [*yes, *no]
        try:
            msg = await self.client.wait_for("message", check=check, timeout=tout)
        except asyncio.TimeoutError:
            await ctx.send(ctx.author.mention, embed=timeout_embed(tout, ctx.author))
        else:
            if msg.content.lower() in no:
                await ctx.send("🛒 Удаление магазина отменено")
            else:
                shop = ItemStorage(ctx.guild.id, {"items": True, "shop": True}).shop
                shop.clear()
                reply = discord.Embed(
                    title=f"🛒 | Магазин очищен",
                    description="Полки и витрины пустуют.",
                    color=discord.Color.green()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
                await ctx.message.delete()

    
    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["buy-item"],
        description="осуществляет покупку шмотки.",
        usage="Название шмотки Количество (не обязательно)",
        brief="Футболка\nФутболка 3" )
    async def buy(self, ctx, *, search):
        # Searching item
        server = ItemStorage(ctx.guild.id, {"items": True, "shop": True, "cy": True})
        shop = server.shop
        cy = server.cy
        p = ctx.prefix
        del server

        arsearch = search.rsplit(maxsplit=1)
        search2 = ""
        num = 1
        if len(arsearch) > 1 and arsearch[1].isdigit():
            search2 = search
            search = arsearch[0]; num = int(arsearch[1])
        items = shop.search_item(search)

        item = None
        if len(items) == 0:
            reply = discord.Embed(
                title="❌ | Вещь не найдена",
                description=f"По поиску '{search}' в магазине не было найдено шмоток.\nМагазин: `{p}shop`",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        elif len(items) < 2:
            item = items[0]
        else:
            ind = await self.ask_to_choose(ctx, [it.name for it in items])
            if ind is not None:
                item = items[ind]
        del items
        # Visualising item
        if item is not None:
            del shop
            if item.name.lower() == search2.lower():
                num = 1
            
            total_cost = num * item.price
            customer = Customer(ctx.guild.id, ctx.author.id)
            # Checking balance
            if customer.balance < total_cost:
                reply = discord.Embed(
                    title="❌ | Недостаточно денег",
                    description=f"**{item.name}** (x{num}) стоит **{total_cost}** {cy}, а Ваш баланс - **{customer.balance}** {cy}",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)

            else:
                num = customer.buy(item, num)
                if num is None:
                    reply = discord.Embed(
                        title="❌ | Недостаточно места в инвентаре",
                        description=f"Все ячейки забиты. Всего ячеек: **x{inv_capacity}**",
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                
                else:
                    total_cost = num * item.price
                    reply = discord.Embed(
                        title=f"🛒 | Спасибо за покупку!",
                        description=(
                            f"**Приобретено:** {item.name} (x{num})\n"
                            f"**Цена:** {total_cost} {cy}\n\n"
                            f"**Использовать:** `{p}use {item.name}`\n"
                            f"**Ваш профиль:** `{p}inv`"
                        ),
                        color=colors.emerald
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                    await ctx.message.delete()


    @commands.cooldown(1, 2, commands.BucketType.member)
    @commands.command(
        aliases=["server-shop"] )
    async def shop(self, ctx, page: IntConverter=1):
        interval = 10
        server = ItemStorage(ctx.guild.id, {"items": True, "shop": True, "cy": True})
        shop = server.shop
        cy = server.cy
        del server

        total_items = len(shop.items)
        total_pages = abs(total_items - 1) // interval + 1
        if page > total_pages or page < 1:
            reply = discord.Embed(
                title="❌ | Страница не найдена",
                description=f"Всего страниц: {total_pages}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            reply = discord.Embed(
                title=f"🛒 | Магазин сервера",
                description="",
                color=colors.emerald
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            
            lind = (page - 1) * interval
            uind = min(page * interval, total_items)
            for i in range(lind, uind):
                item = shop.items[i]
                reply.add_field(name=f"`{i + 1}.` {item.name}", value=f"> **Цена:** {item.price} {cy}", inline=False)
            if uind == 0:
                reply.description = "Магазин пока что пуст. Приходите позже 🧸"
            
            reply.set_footer(text=f"Стр. {page} / {total_pages} | {ctx.author}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
            await ctx.message.delete()

    # Money related commands
    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["change-bal", "cb", "change", "add-money", "change-balance"],
        description="изменяет баланс участника",
        usage="Кол-во @Участник",
        brief="-6 @User#1234" )
    async def change_bal(self, ctx, amount: IntConverter, *, member: discord.Member=None):
        if member is None:
            member = ctx.author
        
        amount_desc = f"{amount}"
        if amount_desc[0] != "-":
            amount_desc = f"+{amount_desc}"

        eco = ItemStorage(ctx.guild.id, {"cy": True})
        customer = Customer(ctx.guild.id, member.id)
        customer.inc_bal(amount)
        reply = discord.Embed(
            title="♻ Выполнено",
            description=f"{amount_desc} {eco.cy} участнику **{member}**",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)
        await ctx.message.delete()


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["reset-top", "rt", "resettop"],
        description="обнуляет баланс всех участников сервера",
        usage="",
        brief="" )
    async def reset_top(self, ctx):
        clist = CustomerList(ctx.guild.id)
        clist.reset_money()
        reply = discord.Embed(
            title="♻ Выполнено",
            description=f"Топ участников обнулён",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["clear-inventories", "clear-invs", "clearinvs", "cinvs"],
        description="очищает инвентари всех участников",
        usage="",
        brief="" )
    async def clear_inventories(self, ctx):
        clist = CustomerList(ctx.guild.id)
        clist.clear_inventories()
        reply = discord.Embed(
            title="♻ Выполнено",
            description=f"Инвентари участников очищены.",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        aliases=["clear-keys", "ck", "clearkeys", "removekeys"] )
    async def clear_keys(self, ctx):
        clist = CustomerList(ctx.guild.id)
        clist.clear_keys()
        reply = discord.Embed(
            title="♻ Выполнено",
            description=f"Ключи отобраны у всех участников.",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
        await ctx.send(embed=reply)


    @commands.cooldown(1, 3600, commands.BucketType.member)
    @commands.command(aliases=["w"])
    async def work(self, ctx):
        w_range = (50, 50)
        cur = ItemStorage(ctx.guild.id, {"cy": True}).cy
        player = Customer(ctx.guild.id, ctx.author.id, {})

        summ = random.randint(*w_range)
        text = random.choice(work_replies).replace("{earning}", f"{summ} {cur}")

        player.inc_bal(summ)
        
        reply = discord.Embed(
            title=f"✅ {ctx.author}",
            description=text,
            color=discord.Color.dark_green()
        )
        await ctx.send(embed=reply)
        await ctx.message.delete()


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.command(aliases=["$", "inventory", "inv"])
    async def balance(self, ctx, *, member: discord.Member=None):
        if member is None:
            member = ctx.author
        customer = Customer(ctx.guild.id, member.id)
        eco = ItemStorage(ctx.guild.id, {"cy": True, "cases": True})

        item_desc = ""
        for item, amount in dupe_dump(customer.items).items():
            item_desc += f"> **{item.name}** (x{amount})\n"
        keys = dupe_dump(customer.keys)
        keys_desc = ""
        for case in eco.cases:
            if case.id in keys:
                keys_desc += f"> **{case.name}** (x{keys[case.id]})\n"
        
        reply = discord.Embed(
            title=f"📦 | Инвентарь {member}",
            color=member.color
        )
        reply.add_field(name="Баланс", value=f"> **{customer.balance}** {eco.cy}", inline=False)
        if item_desc != "":
            reply.add_field(name="🧸 Шмотки", value=item_desc)
        if keys_desc != "":
            reply.add_field(name="🔑 Ключи", value=keys_desc)
        reply.set_thumbnail(url=member.avatar_url)
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
        await ctx.message.delete()

    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.command(aliases=["leaderboard", "leaders", "lb"])
    async def top(self, ctx, page: IntConverter=1):
        interval = 10
        member_list = CustomerList(ctx.guild.id).customers
        cur = ItemStorage(ctx.guild.id, {"cy": True}).cy

        if member_list == []:
            reply = discord.Embed(
                title="📊 Топ участников",
                description="Пуст",
                color=ctx.guild.me.color
            )
            reply.set_thumbnail(url=f"{ctx.guild.icon_url}")
            await ctx.send(embed=reply)
        
        else:
            total_pairs = len(member_list)
            total_pages = abs(total_pairs - 1) // interval + 1
            if page > total_pages or page < 1:
                reply = discord.Embed(
                    title="📖 Страница не найдена",
                    description=f"Всего страниц: {total_pages}"
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            
            else:
                member_list.sort(reverse=True, key=lambda cust: cust.balance)
                lower_bound = (page - 1) * interval
                upper_bound = min(page * interval, total_pairs)

                desc = ""
                for i in range(lower_bound, upper_bound):
                    cust = member_list[i]
                    member = ctx.guild.get_member(cust.id)
                    desc += f"**{i + 1}.** {anf(member)} • **{cust.balance}** {cur}\n"
                
                reply = discord.Embed(
                    title="📊 Топ участников",
                    description=desc,
                    color=ctx.guild.me.color
                )
                reply.set_thumbnail(url=f"{ctx.guild.icon_url}")
                reply.set_footer(text=f"Стр. {page} / {total_pages} | {ctx.author}", icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
                await ctx.message.delete()


    @commands.cooldown(1, 3, commands.BucketType.member)
    @commands.command(
        description="переводит деньги на счёт участника",
        usage="Кол-во @Участник",
        brief="60 @User#1234" )
    async def give(self, ctx, amount: IntConverter, *, member: discord.Member):
        customer = Customer(ctx.guild.id, ctx.author.id)
        server = ItemStorage(ctx.guild.id, {"cy": True})
        
        if ctx.author.id == member.id:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description="Самому себе платить нельзя.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)

        elif amount > customer.balance or amount < 1:
            reply = discord.Embed(
                title="💢 Ошибка",
                description="На Вашем балансе недостаточно денег.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            customer.pay_to(member.id, amount)
            reply = discord.Embed(
                title="♻ Выполнено",
                description=f"На баланс {member} переведено {amount} {server.cy}",
                color=discord.Color.dark_green()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
            await ctx.message.delete()


def setup(client):
    client.add_cog(economy(client))