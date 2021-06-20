import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
import brawlstats
import os
from random import choice

#----------------------------------------------+
#       Connecting to Brawl Stars API          |
#----------------------------------------------+
brawl_token = str(os.environ.get("brawl_token"))
brawl = None
try:
    print("--> Connecting to BrawlStars API...")
    brawl = brawlstats.Client(brawl_token, is_async=True)
except Exception as e:
    print(f"--> Failed to connect: {e}")

#----------------------------------------------+
#                 Constants                    |
#----------------------------------------------+
from functions import bscolors, owner_ids, max_club_roles
from failures import CooldownResetSignal
from custom_emojis import *
emj = Emj()

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import timeout_embed, BrawlDiscordList, BrawlDiscordUser, antiformat as anf, is_moderator, ServerConfig, BrawlClubLoop


async def better_add_role(member, role):
    if isinstance(role, int):
        role = member.guild.get_role(role)
    if role is not None and role not in member.roles:
        try:
            await member.add_roles(role)
        except Exception:
            pass


class FakeBrawlProfile:
    def __init__(self):
        self.tag = "#EQUENOS"
        self.name = "EQUENOS"
        self.name_color = "#ffdead"
        self.trophies = 46756
        self.highest_trophies = 46756
        self.power_play_points = 1337
        self.highest_power_play_points = 1337
        self.exp_level = 347
        self.exp_points = 8976548
        self.is_qualified_from_championship_challenge = True
        self.x3vs3_victories = 20235
        self.team_victories = self.x3vs3_victories
        self.solo_victories = 30532
        self.duo_victories = 19321
        self.best_robo_rumble_time = 25
        self.best_time_as_big_brawler = 25
        self.club = FakeBrawlClub()
        self.brawlers = []


class FakeBrawlClub:
    def __init__(self):
        self.name = "Procrastination"
        self.tag = "#DISCORD"
    
    def __len__(self):
        return 2


class brawlactions(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Brawl Actions cog is loaded")

        while True:
            print("--> Launching club check loop...")
            bloop = BrawlClubLoop(self.client.user.id)
            await asyncio.sleep(bloop.time_left.total_seconds())
            bloop.update_timestamp()
            for data in bloop.get_servers():
                server = self.client.get_guild(data.get("_id", 0))
                if server is not None:
                    club_roles = data.get("club_roles", {})
                    bdlist = BrawlDiscordList()
                    # Looking at each verified member
                    for bduser in bdlist.find_matches([m.id for m in server.members]):
                        # Checking if he has any club roles
                        member = server.get_member(bduser.id)
                        role_ids = [r.id for r in member.roles]
                        his_club_roles = {}
                        for club_tag in club_roles:
                            role_id = club_roles[club_tag]
                            if role_id in role_ids:
                                his_club_roles[club_tag] = role_id
                        if len(his_club_roles) > 0:
                            # Getting player's current club
                            club_tag = None
                            try:
                                player = await brawl.get_player(bduser.tag)
                            except Exception:
                                pass
                            else:
                                if len(player.club) >= 2:
                                    club_tag = player.club.tag
                            # Looking for incorrect roles
                            wrong_roles = []
                            for ct in his_club_roles:
                                if club_tag != ct:
                                    wrong_roles.append(server.get_role(his_club_roles[ct]))
                            try:
                                await member.remove_roles(*wrong_roles)
                            except Exception:
                                pass
    
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if "#magic" in message.content.lower():
            await message.add_reaction(emj.mage_yes)
            await message.add_reaction(emj.mage_no)
    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.command()
    async def ip(self, ctx):
        if ctx.author.id in owner_ids:
            try:
                brawlstats.Client(brawl_token)
            except Exception as e:
                await ctx.send(str(e))


    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(aliases=["brawl-config", "bconfig"])
    async def brawl_config(self, ctx):
        server = ServerConfig(ctx.guild.id, projection={"verified_role": True, "club_roles": True, "vote_channel": True})

        crdesc = ""
        for club_tag in server.club_roles:
            crdesc += f"> **{club_tag}:** <@&{server.club_roles[club_tag]}>\n"
        if crdesc == "":
            crdesc = "> Отсутствуют"
        
        if server.verified_role is None:
            vrdesc = "> Отсутствует"
        else:
            vrdesc = f"> <@&{server.verified_role}>"
        
        # if server.vote_channel is None:
        #     vcdesc = "> Отсутствует"
        # else:
        #     vcdesc = f"> <#{server.vote_channel}>"
        
        reply = discord.Embed(
            title=":gear: | Настройки сервера",
            color=ctx.guild.me.color
        )
        reply.add_field(name="⭐ Роль за верификацию", value=vrdesc, inline=False)
        reply.add_field(name="🔰 Роли клубов", value=crdesc, inline=False)
        #reply.add_field(name="#️⃣ Канал заявок в клуб", value=vcdesc, inline=False)
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        reply.set_thumbnail(url=ctx.guild.icon_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 360, commands.BucketType.user)
    @commands.command()
    async def verify(self, ctx):
        bdlist = BrawlDiscordList()
        bduser = BrawlDiscordUser(ctx.author.id)
        # If user is already verified
        if bduser.tag is not None:
            # Getting server verified-role and club roles
            server = ServerConfig(ctx.guild.id, {"verified_role": True, "club_roles": True})
            svr = server.verified_role
            if svr is not None:
                svr = ctx.guild.get_role(svr)
            try:
                player = await brawl.get_player(bduser.tag)
            except Exception:
                club = {}
            else:
                club = player.club
            club_role = None
            if len(club) >= 2:
                club_role = server.club_roles.get(club.tag)
                if club_role is not None:
                    club_role = ctx.guild.get_role(club_role)
            # End of relevant roles search
            # Checking if the roles exist and are added to the member
            got_roles = False
            if svr is not None or club_role is not None:
                desc = ""
                if svr is not None and svr not in ctx.author.roles:
                    await better_add_role(ctx.author, svr)
                    desc += f"Вам выдана роль <@&{svr.id}>\n"
                if club_role is not None and club_role not in ctx.author.roles:
                    await better_add_role(ctx.author, club_role)
                    desc += f"Вам выдана роль <@&{club_role.id}>, поскольку вы участник клана **{club.name}**\n"
                
                if desc != "":
                    got_roles = True
                    reply2 = discord.Embed(
                        title="✅ | Вы подтвердили привязку",
                        description=desc,
                        color=discord.Color.dark_green()
                    )
                    reply2.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                    await ctx.send(embed=reply2)
            
            if not got_roles:
                reply2 = discord.Embed(
                    title="❌ | Вы уже подтвердили привязку",
                    description="Ваша учётная запись Discord привязана к аккаунту Brawl Stars.",
                    color=discord.Color.dark_red()
                )
                reply2.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply2)

                raise CooldownResetSignal()
        
        else:
            # Introduction
            reply = discord.Embed(
                title="🔗 | Привязка аккаунта Brawl Stars",
                description=(
                    "Сейчас я попрошу Вас написать свой тег в Brawl Stars, после чего у Вас будет ровно 3 минуты, чтобы временно сменить цвет ника в игре.\n"
                    "Это нужно, чтобы подтвердить, что владелец указанного аккаунта - именно Вы.\n\n"
                    "Пожалуйста, укажите тег в бравл старс. Пример - `#ABCDEFGH`\n"
                    "*Для отмены напишите `cancel`*"
                ),
                color=discord.Color.orange()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

            # Waiting for a valid brawl tag
            cycle = True
            player = None
            while cycle:
                try:
                    msg = await self.client.wait_for(
                        "message",
                        check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and len(m.content) >= 3,
                        timeout=180
                    )
                except asyncio.TimeoutError:
                    await ctx.send(embed=timeout_embed(180, ctx.author))
                    cycle = False
                else:
                    if msg.content.lower() in ["quit", "cancel", "отмена"]:
                        reply2 = discord.Embed(
                            title="↩ | Отмена",
                            description="Привязка аккаунта отменена.",
                            color=discord.Color.blurple()
                        )
                        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                        await ctx.send(embed=reply2)
                        cycle = False
                    
                    else:
                        try:
                            player = await brawl.get_player(msg.content)
                        except Exception:
                            pass
                        else:
                            if bdlist.contains_tag(player.tag):
                                reply2 = discord.Embed(
                                    title="❌ | Ошибка",
                                    description=f"Аккаунт **{player.name}** уже привязан к другому Discord-аккаунту.",
                                    color=discord.Color.dark_red()
                                )
                                reply2.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                                await ctx.send(embed=reply2)
                            
                            else:
                                cycle = False
            
            # Waiting for a color change
            if player is None:
                raise CooldownResetSignal()

            else:
                col = player.name_color
                req_col = choice([c for c in bscolors if c != col])
                rcnum = list(bscolors.keys()).index(req_col) + 1
                if req_col[4:] == "ffffff":
                    emb_col = discord.Color.from_rgb(254, 254, 254)
                else:
                    emb_col = int(req_col[4:], 16)
                
                reply = discord.Embed(
                    title="🔗 | Привязка аккаунта Brawl Stars",
                    description=(
                        f"Вы указали аккаунт **{player.name}**. Чтобы подтвердить, что он принадлежит Вам, сделайте следующее.\n"
                        f"У Вас есть 3 минуты на то, чтобы сменить цвет своего ника на **{bscolors[req_col]} ({rcnum}-й в списке игры, даже с Brawl Pass)**\n\n"
                        "Для Вашего удобства, данное сообщение слева подкрашено нужным цветом.\n\n"
                        "Через 3 минуты я скажу результат, после чего Вы сможете вернуть прежний цвет ника в игре."
                    ),
                    color = emb_col
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
            
                await asyncio.sleep(180)    # Should be 300?

                player = await brawl.get_player(player.tag)
                new_col = player.name_color
                if new_col != req_col:
                    reply = discord.Embed(
                        title="❌ | Верификация не пройдена",
                        description=(
                            f"На аккаунте **{player.name}** стоит не тот цвет, который был запрошен 3 минуты назад ({bscolors[req_col]}). "
                            "Ничего страшного, Вы можете попробовать снова."
                        ),
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                    await ctx.send(content=str(ctx.author.mention), embed=reply)
                
                else:
                    bdlist.link_together(ctx.author.id, player.tag)

                    reply = discord.Embed(
                        title="✅ | Верификация пройдена",
                        description=(
                            f"Теперь аккаунт Brawl Stars **{player.name}** привязан к Вашему аккаунту в Discord - **{ctx.author}**\n"
                            f"Ваш профиль: `{ctx.prefix}brawl-profile`"
                        ),
                        color=discord.Color.dark_green()
                    )
                    reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                    await ctx.send(content=str(ctx.author.mention), embed=reply)

                    server = ServerConfig(ctx.guild.id, {"verified_role": True, "club_roles": True})
                    await better_add_role(ctx.author, server.verified_role)
                    if len(player.club) >= 2:
                        club_role = server.club_roles.get(player.club.tag)
                        await better_add_role(ctx.author, club_role)


    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command()
    async def unverify(self, ctx):
        bdlist = BrawlDiscordList()
        if not bdlist.contains_id(ctx.author.id):
            reply = discord.Embed(
                title="❌ | Ошибка",
                description="Ваша учётная запись Discord не привязана ни к одному аккаунту Brawl Stars.",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            reply = discord.Embed(
                title="❓ | Вы уверены",
                description=(
                    "Напишите `да`, чтобы отвязать свой аккаунт Brawl Stars\n"
                    "Напишите `нет`, чтобы отменить действие."
                )
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            botmsg = await ctx.send(embed=reply)

            yes = ["yes", "да"]
            no = ["no", "нет"]
            msg = None

            try:
                msg = await self.client.wait_for(
                    "message",
                    check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() in [*yes, *no],
                    timeout=60
                )
            except asyncio.TimeoutError:
                await ctx.send(embed=timeout_embed(60, ctx.author))
            
            try:
                await botmsg.delete()
            except Exception:
                pass

            if msg is not None and msg.content.lower() in yes:
                bduser = BrawlDiscordUser(ctx.author.id)
                bduser.unlink()

                reply = discord.Embed(
                    title="✅ | Аккаунт отвязан",
                    description="Теперь к Вашему аккаунту Discord не привязано Brawl Stars-аккаунтов",
                    color=discord.Color.dark_green()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(content=str(ctx.author.mention), embed=reply)


    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(aliases=["brawl-profile", "bp"])
    async def brawl_profile(self, ctx, *, member: discord.Member=None):
        if member is None:
            member = ctx.author
            err_desc = f"Ваша учётная запись Discord не привязана ни к одному аккаунту Brawl Stars.\nПривязать: `{ctx.prefix}verify`"
        else:
            err_desc = f"Аккаунт {member} не привязан ни к одному аккаунту Brawl Stars."
        
        bduser = BrawlDiscordUser(member.id)
        if member.id in owner_ids:
            bduser.tag = "#EQUENOS"
        
        if bduser.tag is None:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description=err_desc,
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            async with ctx.channel.typing():
                if bduser.tag != "#EQUENOS":
                    player = await brawl.get_player(bduser.tag)
                else:
                    player = FakeBrawlProfile()
                
                reply = discord.Embed(
                    title=f"{emj.home} | Профиль {anf(player.name)} `aka` {anf(member)}",
                    description=f"**Lvl:** {emj.xp} {player.exp_level} | **XP:** {player.exp_points}",
                    color=int("3476EF", 16)
                )
                reply.set_footer(text=" - Brawl Stars API")
                if len(player.club) >= 2:
                    reply.add_field(name="**Клуб**", value=f"{emj.club} **{anf(player.club.name)}** ({player.club.tag})", inline=False)
                reply.add_field(name="Максимум трофеев", value=f"{emj.trophy} {player.highest_trophies}")
                reply.add_field(name="Макс. очков в силовой гонке", value=f"{emj.maxrace} {player.highest_power_play_points}")
                # reply.add_field(name="Макс. побед в испытании", value=f"{emj.maxevent} --")
                reply.add_field(name="Побед 3 на 3", value=f"{emj.trio} {player.x3vs3_victories}")
                reply.add_field(name="Одиночных побед", value=f"{emj.solo} {player.solo_victories}")
                reply.add_field(name="Парных побед", value=f"{emj.duo} {player.duo_victories}")
                reply.add_field(name="Уровень роборубки", value=f"{emj.robolevel} {player.best_robo_rumble_time}")
                # reply.add_field(name="Уровень боя с боссом", value=f"{emj.bosslevel} --")
                # reply.add_field(name="Уровень разгрома", value=f"{emj.destructlevel} --")

                await ctx.send(embed=reply)


    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command(aliases=["brawl-top", "bt"])
    async def brawl_top(self, ctx):
        await ctx.send("🕑 Собираю данные с BS API...")
        bdl = BrawlDiscordList()
        players = []
        for bdu in bdl.find_matches([ m.id for m in ctx.guild.members ]):
            try:
                player = await brawl.get_player(bdu.tag)
            except Exception:
                player = None
            else:
                players.append((bdu.id, player.name, player.trophies))
        players.sort(reverse=True, key=lambda tri: tri[2])
        desc = ""
        for i, p in enumerate(players[:10]):
            dtag = ctx.guild.get_member(p[0])
            desc += f"**{i + 1}.** {anf(dtag)} • `{p[1]}` • **{p[2]}** {emj.trophy}\n"
        
        reply = discord.Embed(
            title=f"{emj.club} | Топ участников сервера",
            description=desc,
            color=discord.Color.gold()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(
        aliases=["verify-role", "vr"],
        description="настраивает роль, которая будет выдаваться при успешной привязке аккаунта Brawl Stars",
        usage="@Роль\ndelete (сбрасывает настройку)",
        brief="@Verified\ndelete" )
    async def verify_role(self, ctx, *, param):
        if param.lower() == "delete":
            value = None
            desc = "удалена"
        else:
            value = await commands.RoleConverter().convert(ctx, param)
            value = value.id
            desc = f"настроена как <@&{value}>"
        
        server = ServerConfig(ctx.guild.id, {"_id": True})
        server.set_verified_role(value)

        reply = discord.Embed(
            title="✅ | Выполнено",
            description=f"Роль за успешную привязку аккаунта Brawl Stars {desc}",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(
        aliases=["add-club-role", "addclubrole", "acr"],
        description="настраивает роль, которая будет выдаваться участникам определённого клуба Brawl Stars после верификации.",
        usage="#ТЕГ_КЛУБА @Роль",
        brief="#ABCDEFG @ProClan Members" )
    async def add_club_role(self, ctx, club_tag, *, role: discord.Role):
        server = ServerConfig(ctx.guild.id, projection={"club_roles": True})
        if len(server.club_roles) >= max_club_roles:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description=f"Превышен максимум ролей клубов - {max_club_roles}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        elif club_tag in server.club_roles:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description="За клуб с таким тегом уже даются роли",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

        else:
            try:
                club = await brawl.get_club(club_tag)
            except Exception:
                reply = discord.Embed(
                    title="❌ | Ошибка",
                    description=f"По тегу **{club_tag}** не найдено клубов",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
            else:
                server.add_club_role(role.id, club.tag)
                reply = discord.Embed(
                    title="🔰 | Настроено",
                    description=f"Теперь верифицированным участникам из клана **{club.name}** будет даваться роль **<@&{role.id}>**",
                    color=discord.Color.teal()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)


    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(
        aliases=["remove-club-role", "removeclubrole", "rcr"],
        description="сбрасывает роль, которая выдаётся участникам определённого клуба Brawl Stars после верификации.",
        usage="#ТЕГ_КЛУБА",
        brief="#ABCDEFG" )
    async def remove_club_role(self, ctx, club_tag):
        server = ServerConfig(ctx.guild.id, projection={"club_roles": True})
        if club_tag not in server.club_roles:
            reply = discord.Embed(
                title="❌ | Ошибка",
                description="За клуб с таким тегом не даются роли",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            role_id = server.club_roles.get(club_tag, 0)
            server.remove_club_role(club_tag)
            reply = discord.Embed(
                title="🔰 | Настроено",
                description=f"Теперь верифицированным участникам из клана с тегом **{club_tag}** не даётся роль **<@&{role_id}>**",
                color=discord.Color.teal()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
    

    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(
        aliases=["vote-channel"],
        description="",
        usage="#канал\ndelete (сбрасывает настройку)",
        brief="#канал-для-голосований\ndelete" )
    async def vote_channel(self, ctx, *, param):
        if param.lower() == "delete":
            value = None
            desc = "удалён"
        else:
            value = await commands.TextChannelConverter().convert(ctx, param)
            value = value.id
            desc = f"настроен как <#{value}>"
        
        server = ServerConfig(ctx.guild.id, {"_id": True})
        server.set_vote_channel(value)

        reply = discord.Embed(
            title="✅ | Выполнено",
            description=f"Канал для голосований {desc}",
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(brawlactions(client))