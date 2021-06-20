import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio, os, datetime, random

from functions import find_alias, carve_int, get_field

from pymongo import MongoClient
app_string = str(os.environ.get('cluster_string'))
cluster = MongoClient(app_string)
db = cluster["guilds"]

#====== Roulette game rules ========
color_fields = {
    "красный": [1, 3, 7, 12, 16, 18, 21, 23, 25, 27, 32, 36],
    "зеленый": [4, 5, 9, 10, 14, 19, 20, 24, 28, 30, 33, 34]
}
color_aliases = {
    "красный": ["red", "r", "красный", "к"],
    "зеленый": ["green", "g", "зеленый", "зелёный", "з"],
    "черный": ["black", "b", "чёрный", "черный", "ч"]
}
roulette_url = "https://cdn.discordapp.com/attachments/698956854356738168/698957373875814520/roulette_board_upd.png"

roulette_games = {}
lotteries = {}
#======= Work replies=======
work_replies = [
    "Вы провели долгие часы на заводе, заработав {earning}",
    "Поработав 8 часов в офисе, Вы заработали {earning}",
    "За волонтёрскую деятельность Вам заплатили {earning}",
    "Фриланс сегодня принёс Вам {earning}",
    "Вы продали несколько товаров на алиэкспрессе в сумме на {earning}",
    "Вы порылись в карманах зимней куртки. {earning}."
]
#-------- Black jack---------
deck = None

#======= Functions ========
from functions import Customer, ItemStorage, CustomerList

def card_val(name):
    s = name.rsplit("_", maxsplit=1)[1]
    if s in ["j", "q", "k"]:
        return 10
    elif s == "a":
        return 11
    else:
        return int(s)

def get_deck(client):
    sid_1, sid_2 = 698646973347266560, 698992580234444801
    elist_1, elist_2 = client.get_guild(sid_1).emojis, client.get_guild(sid_2).emojis
    out = []
    is_card = lambda name: name.startswith("poke") or name.startswith("club") or name.startswith("diamond") or name.startswith("heart")
    for e in elist_1:
        if is_card(e.name):
            out.append((str(e), card_val(e.name)))
    for e in elist_2:
        if is_card(e.name):
            out.append((str(e), card_val(e.name)))
    return out

def is_command(text, prefix, client):
    out = False
    _1st_word = text.split(maxsplit=1)[0]
    if _1st_word.startswith(prefix):
        _1st_word = _1st_word[len(prefix):]
        for cmd in client.commands:
            if _1st_word == cmd.name or _1st_word in cmd.aliases:
                out = True
                break
    return out

async def read_message(channel, user, t_out, client):
    try:
        msg = await client.wait_for("message", check=lambda message: user.id==message.author.id and channel.id==message.channel.id, timeout=t_out)
    except asyncio.TimeoutError:
        reply=discord.Embed(
            title="🕑 Вы слишком долго не писали",
            description=f"Таймаут: {t_out} сек",
            color=discord.Color.blurple()
        )
        await channel.send(content=user.mention, embed=reply)
        return None
    else:
        return msg

async def do_roulette(channel):
    await asyncio.sleep(30)

    global roulette_games
    players = roulette_games[channel.guild.id]
    players.pop("started_at")
    roulette_games.pop(channel.guild.id)

    win_field = random.randint(1, 36)
    win_line = (win_field - 1) % 3 + 1
    win_col = None
    for color in color_fields:
        if win_field in color_fields[color]:
            win_col = color
            break
    if win_col is None:
        win_col = "черный"

    to_inc_list = []
    mass_ping = ""
    for user_id in players:
        bets = players[user_id]
        summ = 0
        for triplet in bets:
            typ, value, bet = triplet
            if typ == "field" and value == win_field:
                summ += 36 * bet
            elif typ == "line" and value == win_line:
                summ += 3 * bet
            elif typ == "color" and value == win_col:
                summ += 3 * bet
        if summ > 0:
            to_inc_list.append(user_id)
            mass_ping += f"> <@!{user_id}>\n"

    if to_inc_list != []:
        player_base = CustomerList(channel.guild.id, {"_id": True})
        player_base.mass_inc_bal(summ, to_inc_list)
    if mass_ping == "":
        mass_ping = "> Отсутствуют"
    
    msg = discord.Embed(
        title="🎲 Конец рулетки",
        description=(
            f"Шар упал на поле **№{win_field}** (линия {win_line}, {win_col} цвет)\n"
            f"Победители:\n{mass_ping}"
        ),
        color=channel.guild.me.color
    )
    msg.set_thumbnail(url=f"{channel.guild.icon_url}")
    await channel.send(embed=msg)

async def do_lottery(channel):
    await asyncio.sleep(60)

    global lotteries
    guild_id = channel.guild.id
    lot = lotteries[guild_id]
    lot.pop("started_at")
    lotteries.pop(guild_id)

    winner_id = random.choice(lot["ids"])
    winner = channel.guild.get_member(winner_id)

    player = Customer(channel.guild.id, winner_id, {})
    player.inc_bal(lot["pool"])
    
    win_emb = discord.Embed(
        title="🎉 Результаты лотереи",
        description=(
            f"**Призовой фонд:** {lot['pool']}\n"
            f"**Кол-во участников:** {len(lot['ids'])}\n"
            f"**Победитель:** {winner}, получает весь призовой фонд!"
        ),
        color=discord.Color.gold()
    )
    win_emb.set_thumbnail(url=f"{channel.guild.icon_url}")
    await channel.send(embed=win_emb)

class Deck:
    def __init__(self, deck_pairs):
        self.deck = deck_pairs
    
    def take_card(self):
        i = random.randint(0, len(self.deck) - 1)
        card = self.deck[i]
        self.deck.pop(i)
        return card

    def take_specific_card(self, value):
        card = None
        for c in self.deck:
            if c[1] == value:
                card = c
                break
        return card

class Hand:
    def __init__(self):
        self.cards = []
        self.value = 0
        self.values = []
    
    def __str__(self):
        return " ".join(self.cards)
    
    def add_card(self, paired_card):
        self.cards.append(paired_card[0])
        self.values.append(paired_card[1])
        self.value += paired_card[1]
        if self.value > 21:
            for i in range(len(self.values)):
                if self.values[i] == 11:
                    self.values[i] = 1
                    self.value -= 10
                    break

class economy(commands.Cog):
    def __init__(self, client):
        self.client = client

    #========== Events ===========
    @commands.Cog.listener()
    async def on_ready(self):
        print(">> Mini games cog is loaded")

    #========= Commands ==========
    @commands.cooldown(3, 3600, commands.BucketType.member)
    @commands.command(
        aliases=["r"],
        description="начинает рулетку или участвует в существующей игре.",
        usage="Размер Номер_поля\nРазмер line Номер_ряда\nРазмер Красный/Зеленый/Черный",
        brief="100 красный\n100 line 1\n100 25",
        help=roulette_url )
    async def roulette(self, ctx, bet, *, choice):
        p = ctx.prefix
        if not bet.isdigit():
            reply = discord.Embed(
                title="💢 Упс",
                description=f"Ставка ({bet}) должна быть целым числом",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            bet = int(bet)

            server = ItemStorage(ctx.guild.id, {"cy": True})
            cur = server.cy
            customer = Customer(ctx.guild.id, ctx.author.id)
            
            if bet > customer.balance or bet < 1:
                if bet < 1:
                    desc = f"Минимальная ставка 2 {cur}"
                else:
                    desc = f"У Вас недостаточно денег. Ваш баланс: {customer.balance} {cur}"
                reply = discord.Embed(
                    title="💢 Упс",
                    description=desc,
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            
            else:
                choice = choice.lower()
                correct_choice = False

                if choice.isdigit():
                    num = int(choice)
                    if num < 1 or num > 36:
                        error_desc = "Номер поля должен быть от 1 до 36, например `24`"
                    else:
                        desc = f"Поставлено **{bet}** {cur} на поле №{num}"
                        triplet = ("field", num, bet)
                        correct_choice = True
                
                elif "line" in choice:
                    line_num = carve_int(choice)
                    if line_num is None:
                        error_desc = "Укажите номер ряда, например `line 1`"
                    elif line_num < 1 or line_num > 3:
                        error_desc = "Номер ряда должен быть от 1 до 3, например `line 2`"
                    else:
                        correct_choice = True
                        triplet = ("line", line_num, bet)
                        desc = f"Поставлено **{bet}** {cur} на линию №{line_num}"
                
                elif find_alias(color_aliases, choice) is not None:
                    correct_choice = True
                    col = find_alias(color_aliases, choice)
                    triplet = ("color", col, bet)
                    desc = f"Поставлено **{bet}** {cur} на {col}"
                
                else:
                    error_desc = f"Укажите, на что Вы делаете ставку. Подробнее - напишите `{p}roulette`"
                
                if not correct_choice:
                    reply = discord.Embed(
                        title="💢 Ошибка",
                        description=error_desc,
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                    await ctx.send(embed=reply)
                
                else:
                    customer.inc_bal(-bet)

                    global roulette_games
                    its_new_game = False
                    now = datetime.datetime.now()

                    # Manipulating current games / adding new
                    if ctx.guild.id not in roulette_games:
                        roulette_games.update([
                            (ctx.guild.id, {"started_at": now})
                        ])
                        its_new_game = True
                    
                    if ctx.author.id not in roulette_games[ctx.guild.id]:
                        roulette_games[ctx.guild.id].update([(ctx.author.id, [triplet])])
                    
                    elif not triplet in roulette_games[ctx.guild.id][ctx.author.id]:
                        roulette_games[ctx.guild.id][ctx.author.id].append(triplet)

                    # Generating a reply
                    delta = now - roulette_games[ctx.guild.id]["started_at"]

                    reply = discord.Embed(
                        title=f"☑ Ставка {ctx.author}",
                        description=desc,
                        color=discord.Color.dark_blue()
                    )
                    reply.set_thumbnail(url=f"{ctx.author.avatar_url}")
                    reply.set_footer(text=f"До конца игры: {30 - delta.seconds} сек.")
                    await ctx.send(embed=reply)

                    if its_new_game:
                        await do_roulette(ctx.channel)


    @commands.cooldown(1, 3600, commands.BucketType.member)
    @commands.command(aliases=["w"])
    async def work(self, ctx):
        w_range = (50, 100)
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


    @commands.cooldown(3, 3600, commands.BucketType.member)
    @commands.command(
        aliases=["lot"],
        description="начинает новую лотерею или участвует в существующей.",
        usage="Ставка",
        brief="100" )
    async def lottery(self, ctx, bet):
        if not bet.isdigit():
            reply = discord.Embed(
                title="💢 Упс",
                description=f"Ставка ({bet}) должна быть целым числом",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            bet = int(bet)

            server = ItemStorage(ctx.guild.id, {"cy": True})
            cur = server.cy
            customer = Customer(ctx.guild.id, ctx.author.id)
            
            if bet > customer.balance or bet < 100:
                if bet < 1:
                    desc = f"Минимальная цена билета 100 {cur}"
                else:
                    desc = f"У Вас недостаточно денег. Ваш баланс: {customer.balance} {cur}"
                reply = discord.Embed(
                    title="💢 Упс",
                    description=desc,
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            
            else:
                customer.inc_bal(-bet)

                global lotteries
                new_game = False
                now = datetime.datetime.now()
                if ctx.guild.id in lotteries:
                    if not ctx.author.id in lotteries[ctx.guild.id]["ids"]:
                        lotteries[ctx.guild.id]["ids"].append(ctx.author.id)
                    lotteries[ctx.guild.id]["pool"] += bet
                
                else:
                    new_game = True
                    lotteries.update([(
                        ctx.guild.id,
                        {
                            "started_at": now,
                            "pool": bet,
                            "ids": [ctx.author.id]
                        }
                    )])
                
                prize_pool = lotteries[ctx.guild.id]["pool"]
                total_players = len(lotteries[ctx.guild.id]["ids"])
                delta = now - lotteries[ctx.guild.id]["started_at"]

                reply = discord.Embed(
                    title=f"🎫 {ctx.author}",
                    description=(
                        f"**Покупает билет и делает ставку** {bet} {cur}\n\n"
                        f"**Призовой фонд:** {prize_pool} {cur}\n"
                        f"**Участников:** {total_players}"
                    ),
                    color=ctx.author.color
                )
                reply.set_thumbnail(url=f"{ctx.author.avatar_url}")
                reply.set_footer(text=f"Осталось до конца: {60 - delta.seconds} сек")
                await ctx.send(embed=reply)

                if new_game:
                    await do_lottery(ctx.channel)


    @commands.cooldown(3, 3600, commands.BucketType.member)
    @commands.command(
        aliases=["black-jack", "bj"],
        description="начинает игру в Блэк Джек.",
        usage="Ставка",
        brief="100" )
    async def black_jack(self, ctx, bet):
        if not bet.isdigit():
            reply = discord.Embed(
                title="💢 Упс",
                description=f"Ставка ({bet}) должна быть целым числом",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
            await ctx.send(embed=reply)
        
        else:
            bet = int(bet)

            server = ItemStorage(ctx.guild.id, {"cy": True})
            cur = server.cy
            customer = Customer(ctx.guild.id, ctx.author.id)
            
            if bet > customer.balance or bet < 100:
                if bet < 100:
                    desc = f"Минимальная ставка - 100 {cur}"
                else:
                    desc = f"У Вас недостаточно денег. Ваш баланс: {customer.balance} {cur}"
                reply = discord.Embed(
                    title="💢 Упс",
                    description=desc,
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=f"{ctx.author}", icon_url=f"{ctx.author.avatar_url}")
                await ctx.send(embed=reply)
            
            else:
                d = Deck(get_deck(self.client))
                my_hand, dealer_hand = Hand(), Hand()
                my_hand.add_card(d.take_card())
                my_hand.add_card(d.take_card())
                dealer_hand.add_card(d.take_card())
                
                table = discord.Embed(
                    title=f"{ctx.author}",
                    description="`hit` - взять карту, `double down` - взять карту, удвоить ставку и завершить игру, `stand` - завершить игру",
                    color=ctx.author.color
                )
                table.add_field(name="**Ваша рука**", value=f"{my_hand}\nОчков: {my_hand.value}")
                table.add_field(name="**Рука дилера**", value=f"{dealer_hand}\nОчков: {dealer_hand.value}")
                
                ttt = await ctx.send(embed=table)

                playing = my_hand.value < 21
                if not playing and my_hand.value == 21:
                    bet = int(bet * 1.5)
                msg = 0
                while playing:
                    msg = await read_message(ctx.channel, ctx.author, 60, self.client)
                    if msg is None:
                        playing = False
                    elif is_command(msg.content, ctx.prefix, self.client):
                        await ttt.delete()
                        msg = None
                        playing = False
                    else:
                        move = msg.content.lower()
                        if move == "hit":
                            my_hand.add_card(d.take_card())
                            table.clear_fields()
                            table.add_field(name="**Ваша рука**", value=f"{my_hand}\nОчков: {my_hand.value}")
                            table.add_field(name="**Рука дилера**", value=f"{dealer_hand}\nОчков: {dealer_hand.value}")
                            await ttt.edit(embed=table)
                        elif move == "double down":
                            if customer.balance >= bet * 2:
                                my_hand.add_card(d.take_card())
                                bet *= 2
                                playing = False
                            else:
                                try:
                                    await msg.add_reaction("❌")
                                except Exception:
                                    pass
                        elif move == "stand":
                            playing = False
                        
                        if my_hand.value >= 21:
                            playing = False
                
                if msg is not None:
                    if my_hand.value == 21:
                        res = "Победа"
                    elif my_hand.value > 21:
                        res = "Проигрыш"
                    else:
                        # Dealer playing
                        while dealer_hand.value < 21:
                            commit_win = random.choice([True, True, False])
                            if commit_win:
                                req = 21 - dealer_hand.value
                                if req > 11:
                                    req = my_hand.value - dealer_hand.value + 1
                                if req < 1:
                                    req = 2
                                
                                card = None
                                while card is None and req > 0:
                                    card = d.take_specific_card(req)
                                    req -= 1
                                if card is None:
                                    card = d.take_card()
                                dealer_hand.add_card(card)
                                break
                            else:
                                dealer_hand.add_card(d.take_card())
                        
                        if dealer_hand.value == my_hand.value:
                            res = "Ничья"
                        elif dealer_hand.value < my_hand.value:
                            res = "Победа"
                        elif dealer_hand.value > 21:
                            res = "Победа"
                        else:
                            res = "Проигрыш"
                    
                    if res == "Ничья":
                        color = discord.Color.orange()
                        earning = 0
                    elif res == "Победа":
                        color = discord.Color.green()
                        earning = bet
                    elif res == "Проигрыш":
                        color = discord.Color.red()
                        earning = -bet

                    table = discord.Embed(
                        title=f"{ctx.author}",
                        description=f"{res}: {earning} {cur}",
                        color=color
                    )
                    table.add_field(name="**Ваша рука**", value=f"{my_hand}\nОчков: {my_hand.value}")
                    table.add_field(name="**Рука дилера**", value=f"{dealer_hand}\nОчков: {dealer_hand.value}")
                    await ttt.edit(embed=table)

                    if earning != 0:
                        customer.inc_bal(earning)


def setup(client):
    client.add_cog(economy(client))