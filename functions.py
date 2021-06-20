import failures
import discord
from discord.ext import commands
from db_models import ServerConfig

#-------------------------------------+
#             Constants               |
#-------------------------------------+
owner_ids = [
    301295716066787332
]
perms_tr = {
    "create_instant_invite": "Создавать приглашения",
    "kick_members": "Кикать участников",
    "ban_members": "Банить участников",
    "administrator": "Администратор",
    "manage_channels": "Управлять каналами",
    "manage_guild": "Управлять сервером",
    "add_reactions": "Добавлять реакции",
    "view_audit_log": "Просматривать журнал аудита",
    "priority_speaker": "Приоритетный режим",
    "stream": "Видео",
    "read_messages": "Читать сообщения",
    "view_channel": "Видеть канал",
    "send_messages": "Отправлять сообщения",
    "send_tts_messages": "Отправлять TTS сообщения",
    "manage_messages": "Управлять сообщениями",
    "embed_links": "Встраивать ссылки",
    "attach_files": "Прикреплять файлы",
    "read_message_history": "Просматривать историю сообщений",
    "mention_everyone": "Упоминать everyone / here",
    "external_emojis": "Использовать внешние эмодзи",
    "view_guild_insights": "View server insights",
    "connect": "Подключаться",
    "speak": "Говорить",
    "mute_members": "Выключать микрофон у участников",
    "deafen_members": "Заглушать участников",
    "move_members": "Перемещать участников",
    "use_voice_activation": "Использовать режим рации",
    "change_nickname": "Изменять никнейм",
    "manage_nicknames": "Управлять никнеймами",
    "manage_roles": "Управлять ролями",
    "manage_permissions": "Управлять правами",
    "manage_webhooks": "Управлять вебхуками",
    "manage_emojis": "Управлять эмодзи"
}

#-------------------------------------+
#            Custom Checks            |
#-------------------------------------+
def is_moderator():
    def predicate(ctx):
        server = ServerConfig(ctx.guild.id)
        mod_role_ids = server.mod_roles
        author_role_ids = [r.id for r in ctx.author.roles]
        has = False
        for role_id in mod_role_ids:
            if role_id in author_role_ids:
                has = True
                break
        if has:
            return True
        else:
            raise failures.IsNotModerator()
    return commands.check(predicate)

#-------------------------------------+
#           Other functions           |
#-------------------------------------+
def timeout_embed(timeout, reciever):
    if timeout % 10 == 1:
        timeword = "секунды"
    else:
        timeword = "секунд"
    reply = discord.Embed(
        title="🕑 Истекло время ожидания",
        description=f"{antiformat(reciever)}, Вы не отвечали больше {timeout} {timeword}.",
        color=discord.Color.blurple()
    )
    reply.set_footer(text=str(reciever), icon_url=reciever.avatar_url)
    return reply


def antiformat(text):
    formers = "~`*_|>\\"
    out = ""
    for s in str(text):
        if s in formers:
            out += "\\" + s
        else:
            out += s
    return out


def quote_list(_list):
    return "\n".join([f"> {elem}" for elem in _list])


def display_perms(missing_perms):
    out = ""
    for perm in missing_perms:
        out += f"> {perms_tr[perm]}\n"
    return out


def vis_aliases(aliases):
    if aliases not in [None, []]:
        out = "**Синонимы:** "
        for a in aliases:
            out += f"`{a}`, "
        return out[:-2]
    else:
        return ""


def pick_wordform(number: int, all_forms: list):
    """NOTE: all_forms = ["День" (один), "Дня" (два), "Дней" (пять)]"""
    if 10 < number < 20:
        return all_forms[2]
    else:
        number = number % 10
        if number == 1: return all_forms[0]
        elif 1 < number < 5: return all_forms[1]
        else: return all_forms[2]


def visual_delta(delta):
    if isinstance(delta, int):
        seconds = delta
        t_days = 0
    else:
        seconds = delta.seconds
        t_days = delta.days
    
    expanded_delta = {
        "сек": seconds % 60,
        "мин": seconds // 60 % 60,
        "ч": seconds // 3600 % 24,
        "дн": t_days % 7,
        "нед": t_days // 7
    }
    expwords = {
        "сек": ["секунда", "секунды", "секунд"],
        "мин": ["минута", "минуты", "минут"],
        "ч": ["час", "часа", "часов"],
        "дн": ["день", "дня", "дней"],
        "нед": ["неделя", "недели", "недель"]
    }

    out = ""
    for key in expanded_delta:
        num = expanded_delta[key]
        if num > 0:
            word = pick_wordform(num, expwords[key])
            out = f"{num} {word} " + out
    if out == "":
        out = "0.1 секунд"
    out.strip()
    return out


def rus_timestamp(datetime):
    months = [
        "января", "февраля",
        "марта", "апреля", "мая",
        "июня", "июля", "августа",
        "сентября", "октября", "ноября",
        "декабря"
    ]
    date = f"{datetime.day} {months[datetime.month - 1]} {datetime.year}"
    time = f"{datetime}"[-15:][:+8]
    return f"{date}, {time}"


def get_field(Dict, *key_words, default=None):
    if Dict is not None:
        for key in key_words:
            if key in Dict:
                Dict = Dict[key]
            else:
                Dict = None
                break
    if Dict is None:
        Dict = default
    return Dict


def find_alias(table: dict, value):
    out = None
    value = str(value).lower()
    for key in table:
        arr = [key, *table[key]]
        for elem in arr:
            if elem.lower().startswith(value):
                out = key
                break
        if out is not None:
            break
    return out


def carve_int(string):
    nums = [str(i) for i in range(10)]
    out = ""
    found = False
    for letter in string:
        if letter in nums:
            found = True
            out += letter
        elif found:
            break
    if out == "":
        out = None
    else:
        out = int(out)
    return out


def try_int(string):
    try:
        return int(string)
    except ValueError:
        return None


def has_permissions(member, perm_array):
    if member.id in owner_ids:
        return True
    else:
        perms_owned = dict(member.guild_permissions)
        total_needed = len(perm_array)
        for perm in perm_array:
            if perms_owned[perm]:
                total_needed -= 1
        return total_needed == 0


def is_command(client, prefix, text):
    out = False
    text = text.split()[0]
    if text.startswith(prefix):
        text = text[len(prefix):]
        for cmd in client.commands:
            if text == cmd.name or text in cmd.aliases:
                out = True
                break
    return out


def carve_cmd(prefix, text):
    text = text.split()[0]
    if text.startswith(prefix):
        return text[len(prefix):]


class detect:
    @staticmethod
    def member(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        member = guild.get_member(ID)
        if member is None:
            member = guild.get_member_named(search)
        return member
    
    @staticmethod
    def channel(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        channel = guild.get_channel(ID)
        if channel is None:
            for c in guild.channels:
                if c.name == search:
                    channel = c
                    break
        return channel
    
    @staticmethod
    def role(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        role = guild.get_role(ID)
        if role is None:
            for r in guild.roles:
                if r.name == search:
                    role = r
                    break
        return role
    
    @staticmethod
    def user(search, client):
        ID = carve_int(search)
        user = None
        if ID is not None:
            user = client.get_user(ID)
        return user


class CustomColor:
    def __init__(self):
        self.cardboard = int("FFCC84", 16)
        self.emerald = int("5DE897", 16)


class Custom_emoji:
    def __init__(self, client):
        self.server = client.get_guild(698646973347266560)
    
    def __call__(self, emoji_name):
        out = None
        for emoji in self.server.emojis:
            if emoji.name == emoji_name:
                out = emoji
                break
        return out

