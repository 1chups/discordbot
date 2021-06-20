import discord, random, json
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import is_moderator, visual_delta as vis_delta, antiformat as anf
from db_models import MuteList, MuteModel, get_saved_mutes
from custom_converters import TimedeltaConverter, IntConverter


class MuteSliceTimer:
    def __init__(self):
        self.last_at = datetime.utcnow()
        self.interval = timedelta(hours=1)
    @property
    def next_in(self):
        next_at = self.last_at + self.interval
        now = datetime.utcnow()
        return next_at - now if next_at > now else timedelta(seconds=0)

    def update(self):
        self.last_at = datetime.utcnow()
MST = MuteSliceTimer()
mute_role_name = "Мут"


async def process_mute_role(server, name):
    role = discord.utils.get(server.roles, name=name)
    if role is None:
        role = await server.create_role(name=name, permissions=discord.Permissions(send_messages=False, speak=False))
        tco = discord.PermissionOverwrite(send_messages=False)
        vco = discord.PermissionOverwrite(speak=False)
        catego = discord.PermissionOverwrite(send_messages=False, speak=False)
        for c in server.channels:
            if isinstance(c, discord.TextChannel):
                ovw = tco
            elif isinstance(c, discord.VoiceChannel):
                ovw = vco
            else:
                ovw = catego
            ovw = {**c.overwrites, role: ovw}
            await c.edit(overwrites=ovw)
    return role


class moderation(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                  Methods                     |
    #----------------------------------------------+
    async def process_unmute(self, mutemodel: MuteModel):
        await asyncio.sleep(mutemodel.time_remaining.total_seconds())
        mutemodel.end()
        # Role manipulations
        guild = self.client.get_guild(mutemodel.server_id)
        role = discord.utils.get(guild.roles, name=mute_role_name)
        member = guild.get_member(mutemodel.id)
        if member is not None and role is not None and role in member.roles:
            try:
                await member.remove_roles(role)
            except:
                pass
        try:
            await member.edit(mute=False)
        except:
            pass
        # Notifications
        reply = discord.Embed(color=0x2b2b2b, description="Время мута истекло, Вы были размучены.")
        reply.set_footer(text=f"Сервер {guild}", icon_url=guild.icon_url )
        try:
            await member.send(embed=reply)
        except:
            pass
        return

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Moderation cog is loaded")
        # Refreshing mutes every X hours
        while True:
            print(f"MuteSlicer: {MST.last_at}")
            for mutelist in get_saved_mutes(MST.last_at + MST.interval): # Gets all closest mutes
                for mm in mutelist.mutes:
                    self.client.loop.create_task(self.process_unmute(mm))
            await asyncio.sleep(MST.next_in.total_seconds())
            MST.update()


    @commands.Cog.listener()
    async def on_member_join(self, member):
        mm = MuteModel(member.guild.id, member.id)
        if mm.time_remaining > timedelta(seconds=0):
            role = discord.utils.get(member.guild.roles, name=mute_role_name)
            if role is not None and role not in member.roles:
                try:
                    await member.add_roles(role)
                except:
                    return
    

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

    
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.command(
        description="мутит пользователя во всех чатах",
        usage="@Участник Время Причина(не обязательно)",
        brief="@User#1234 30m Спам в чате" )
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def mute(self, ctx, member: discord.Member, time: TimedeltaConverter, *, reason=None):
        mutelist = MuteList(ctx.guild.id, data={})
        async with ctx.typing():
            try:
                muteRole = await process_mute_role(ctx.guild, mute_role_name)
                await member.add_roles(muteRole)
                mutelist.add(member.id, time, ctx.author.id, reason)
                await member.edit(mute=True)
            except:
                pass
        
        if reason is None:
            reason = "Не указана"

        reply = discord.Embed(colour=0xFFA500)
        reply.description = (
            f"**Длительность:** {vis_delta(time)}\n"
            f"**Причина:** {reason}"
        )
        reply.set_author(name=f" [🔇] {member} был замучен.")
        reply.set_footer(text= f"Выдал: {ctx.author}", icon_url = ctx.author.avatar_url )

        await ctx.send(embed=reply)
        await ctx.message.delete()

        notif = discord.Embed(color=0x2b2b2b, description=f"**[🔇]** Вы были замучены на сервере.")
        notif.set_thumbnail(url=f"{ctx.guild.icon_url}")
        notif.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.avatar_url )
        notif.add_field(name="Причина:", value=f"{reason}")
        notif.add_field(name="Продолжительность:", value=vis_delta(time))

        try:
            await member.send(embed=notif)
        except:
            pass
        # Mute length classification
        if time >= MST.next_in:
            return # Happens not to collide with mute slicer
        else:
            await asyncio.sleep(time.total_seconds())
            try:
                mutelist.remove(member.id)
                await member.remove_roles(muteRole)
                await member.edit(mute=False)
            except:
                pass

            notif = discord.Embed(color=0x2b2b2b, description="Время мута истекло, Вы были размучены.")
            notif.set_footer(text=f"Сервер {ctx.guild}", icon_url=ctx.guild.icon_url )
            try:
                await member.send(embed=notif)
            except:
                pass
    

    @commands.command(
        description="досрочно снимает мут",
        usage="Участник",
        brief="User#1234" )
    @commands.check_any(
        is_moderator(),
        commands.has_permissions(administrator=True) )
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def unmute(self, ctx, *, member: discord.Member):
        mm = MuteModel(ctx.guild.id, member.id)
        mm.end()
        # Role & mute manipulations
        try:
            await member.edit(mute=False)
        except:
            pass
        role = discord.utils.get(ctx.guild.roles, name=mute_role_name)
        if role in member.roles:
            try:
                await member.remove_roles(role)
            except:
                pass

        elif mm.time_remaining.total_seconds() == 0:
            reply = discord.Embed(color=discord.Color.red())
            reply.title = "❌ | Ошибка"
            reply.description = f"Участник **{anf(member)}** не замьючен."
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
            return #
        
        reply = discord.Embed(color=discord.Color.green())
        reply.title = "🔉 | Участник досрочно размучен"
        reply.description = f"Участник **{anf(member)}** был досрочно размучен."
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

        reply = discord.Embed(color=0x2b2b2b, description="Время мута истекло, Вы были размучены.")
        reply.set_footer(text=f"Сервер {ctx.guild}", icon_url=ctx.guild.icon_url )
        try:
            await member.send(embed=reply)
        except:
            pass


    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def mutes(self, ctx, page: IntConverter=1):
        interval = 10
        mutelist = MuteList(ctx.guild.id)
        mutes = sorted(mutelist.mutes, key=lambda mm: mm.ends_at)
        del mutelist

        total_mutes = len(mutes)
        if total_mutes == 0:
            total_pages = 1
        else:
            total_pages = (total_mutes - 1) // interval +  1
        
        if not (0 < page <= total_pages):
            page = total_pages
        lowerb = (page - 1) * interval
        upperb = min(page * interval, total_mutes)

        reply = discord.Embed(color=discord.Color.blurple())
        reply.title = "📑 | Список людей, находящихся в муте"
        reply.set_footer(text=f"Стр. {page} / {total_pages}")
        for i in range(lowerb, upperb):
            mm = mutes[i]
            member = ctx.guild.get_member(mm.id)
            mod = ctx.guild.get_member(mm.mod_id)
            reply.add_field(name=f"🔒 | {anf(member)}", value=(
                f"> **Осталось:** {vis_delta(mm.time_remaining)}\n"
                f"> **Модератор:** {anf(mod)}\n"
                f"> **Причина:** {mm.reason}"
            )[:256], inline=False)
        if len(reply.fields) == 0:
            reply.description = "Мутов нет, какие молодцы!"
        await ctx.send(embed=reply)


    @commands.command()
    async def duck(self, ctx):
        reply = discord.Embed(title="Кря!", color=0x176cd5)
        reply.set_image(url="https://cdn.discordapp.com/attachments/783675372327010324/787595801756434462/images.jpg")
    
        await ctx.send(embed=reply)




    
    @commands.command()
    async def пострелять(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://i.gifer.com/SJN7.gif",
        "https://pa1.narvii.com/6781/bfe91fa0398b8624ce16e1eaece5881aea9e2b4c_hq.gif",
        "https://i.pinimg.com/originals/ca/5e/b3/ca5eb3f253569fef7b3c22c6a43ac333.gif",
        "http://www.animacity.ru/sites/default/files/users/20586/photo/2017/91/Korona_viny_-_Inori_Bakh-bakh_Bakh-bakh.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} начал обстрел по {member.mention} ", color=0x161513)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()

        #https://cdn.discordapp.com/attachments/581816630326198291/659753122977284106/origi6nal.gif
    
    @commands.command()
    async def кусь(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://cdn.discordapp.com/attachments/581816630326198291/659753122977284106/origi6nal.gif",
        "https://cs8.pikabu.ru/images/big_size_comm_an/2017-09_3/1505480110157855233.gif",
        "https://cs9.pikabu.ru/post_img/2017/11/13/4/1510551238180467396.gif",
        "https://pa1.narvii.com/6655/fa3e28730b1015d217cb60cc61b3ce93557f9596_hq.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} наострил свои зубки, и сделал кусь {member.mention} ", color=0xa8f2ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def облизать(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://pa1.narvii.com/6392/81c1903de9fc160246b3636beed16ab19081dfe7_hq.gif",
        "https://i.gifer.com/JSWr.gif",
        "https://i.gifer.com/M4vj.gif",
        "https://cdn.discordapp.com/attachments/783701808609886218/787644148903444540/1483327087_24e.gif",
        "https://media.discordapp.net/attachments/772762959516401675/787644451165700166/f99384d0ebf0c8cfc1d3d15e3bb2e413.gif?width=512&height=288",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} высунул свой язычок и облизал {member.mention} ", color=0xf9a8ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def обнять(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/oct17/171021_8687.gif",
        "https://pa1.narvii.com/6562/a29f2b002883b92e62fd80f234d16a4e4e59c950_hq.gif",
        "https://anime-chan.me/uploads/posts/2016-01/1454009035_tumblr_o1nsh2VP191v6zp1jo2_540.gif",
        "https://99px.ru/sstorage/86/2019/02/image_860602190653473096170.gif",
        "https://images-ext-1.discordapp.net/external/hp1oYnk6JL8sV_yUGdy2_jeUq_tU-pCJUe0-loKR3p0/https/cdn.nekos.life/hug/hug_037.gif?width=384&height=216",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} обнял {member.mention} ", color=0xfffc9e)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def приставать(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://cdn.discordapp.com/attachments/605665948233367563/615624244226949120/ww_sx_gif.gif",
        "https://38.media.tumblr.com/aa0fffcf7782228b8d2259b8f603a9ad/tumblr_nhtg6xaPbv1sk6x9qo1_500.gif",
        "https://anime-chan.me/uploads/posts/2013-11/1384631428_etti-gifki-etti-anime-anime-gifki-934227.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} проявляет явно что-то большее, чем симпатию к {member.mention} ", color=0xdd9eff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def поцеловать(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://pa1.narvii.com/6389/b78a6ee7babb654d73d4dd830172c58824bfab78_hq.gif",
        "https://pa1.narvii.com/7108/0bd9fa66d904221f3ead13e3d8f287741b7858d3r1-540-302_hq.gif",
        "https://pa1.narvii.com/6703/c00954e4478e7495d240e56e1a28963d796adbd4_hq.gif",
        "https://pa1.narvii.com/6928/d0d6cbaa66d56b05728d91d205ef3b6f36c66e89r1-445-250_00.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} поцеловал {member.mention} ", color=0xff6161)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def тык(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://images-ext-1.discordapp.net/external/oOW6_8XMyqDMmIKToG7iWHFMbc1XXJ2FAeWoaCXGEXs/https/i.gifer.com/SKql.gif?width=400&height=225",
        "https://media.discordapp.net/attachments/581816630326198291/659756739054534692/9d25235a88f0fb52c3b72bf9404d2b7e.gif?width=282&height=158",
        "https://images-ext-1.discordapp.net/external/DbD6hyJsTpBTHtStLzxx5j-j_2P7PvQahxqgYSgnxmU/https/i.gifer.com/OWba.gif?width=574&height=320",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} тыкает {member.mention} ", color=0x9ef4ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def шлепнуть(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://anime-chan.me/uploads/posts/2013-11/1385498275_anime-pancu-etti-anime-gifs-936742.gif",
        "https://pa1.narvii.com/6420/c6a4d8016eb39afee4b2ebe0bdff0fe5ffad7217_hq.gif",
        "https://fc04.deviantart.net/fs71/f/2013/254/4/8/animation_commission__rikkaxtouka_by_altiz_studio-d6lvlub.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} шлепнул по попе {member.mention} ", color=0x9ef4ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def грустить(self, ctx):
        author = ctx.message.author
        variable = [
        "https://www.anibox.org/_nw/55/13487516.gif",
        "https://pa1.narvii.com/6784/1ac39e0282df79704f15ca2f203c65b70190d239_hq.gif",
        "https://anime-chan.me/uploads/posts/2018-03/1520660483_yIxwGIo.gif",
        "https://pa1.narvii.com/6696/ca5123a933e0120b0d6b31bdb47cba0b4f1c06bb_hq.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} грустит", color=0x6669ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()

    @commands.command()
    async def смеяться(self, ctx):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/nov17/171122_2546.gif",
        "https://animegif.ru/up/photos/album/nov17/171114_7474.gif",
        "https://animegif.ru/up/photos/album/oct17/171022_3815.gif",
        "https://animegif.ru/up/photos/album/oct17/171022_652.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} смеётся", color=0x6669ff)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def злость(self, ctx):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/jan18/180102_4591.gif",
        "https://animegif.ru/up/photos/album/nov17/171114_7431.gif",
        "https://animegif.ru/up/photos/album/oct17/171021_1133.gif",
        "https://animegif.ru/up/photos/album/jan18/180102_3882.gif",
        "https://animegif.ru/up/photos/album/oct17/171023_8329.gif",]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} очень сильно злится", color=0xAA2424)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def злиться(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/oct17/171023_8661.gif",
        "https://animegif.ru/up/photos/album/nov17/171114_4031.gif",
        "https://animegif.ru/up/photos/album/oct17/171023_5044.gif",
        "https://animegif.ru/up/photos/album/oct17/171021_1109.gif"]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} очень озлоблен на {member.mention} ", color=0xC6FFB8)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def пощёчина(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/oct17/171028_9178.gif",
        "https://animegif.ru/up/photos/album/oct17/171022_7378.gif",
        "https://animegif.ru/up/photos/album/oct17/171022_9663.gif",
        "https://animegif.ru/up/photos/album/dec18/181223_3375.gif",
        "https://animegif.ru/up/photos/album/oct17/171022_8835.gif"]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} дал пощёчину {member.mention} ", color=0xB8C3FF)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()


    @commands.command()
    async def погладить(self, ctx, member: discord.Member):
        author = ctx.message.author
        variable = [
        "https://animegif.ru/up/photos/album/oct17/171021_210.gif",
        "https://animegif.ru/up/photos/album/jan18/180102_2377.gif",
        "https://animegif.ru/up/photos/album/oct17/171021_7003.gif",
        "https://animegif.ru/up/photos/album/oct17/171021_7804.gif",
        "https://animegif.ru/up/photos/album/oct17/171021_1474.gif"]
    #"""Shoot someone."""
        embed = discord.Embed(description=f"{author.mention} аккуратно гладит {member.mention} ", color=0x7BC9FF)
        embed.set_image(url=format(random.choice(variable)))
        await ctx.send(embed=embed)
        await ctx.message.delete()



    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(moderation(client))
