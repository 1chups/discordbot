from pymongo import MongoClient, collection
import os
from datetime import datetime, timedelta
import random


app_string = str(os.environ.get('cluster_string'))
cluster = None; att = 2
while cluster is None:
    try:
        cluster = MongoClient(app_string)
    except Exception as e:
        att += 1
        print(f"--> functions.py: Retrying to connect to MongoDB (attempt {att}): [{e}]")
db = cluster["guilds"]


#-------------------------------------+
#             Constants               |
#-------------------------------------+
inv_capacity = 100
max_club_roles = 20
bscolors = {
    "0xffffffff": "белый",
    "0xffa2e3fe": "светло-голубой",
    "0xff4ddba2": "изумрудный",
    "0xffff9727": "оранжевый",
    "0xfff9775d": "кремовый красный",
    "0xfff05637": "красный",
    "0xfff9c908": "жёлтый",
    "0xffffce89": "бежевый",
    "0xffa8e132": "зелёный",
    "0xff1ba5f5": "синий",
    "0xffff8afb": "розовый",
    "0xffcb5aff": "фиолетовый"
}
default_cy = "🕸️"
default_item_icon_url = ""


#-------------------------------------+
#           Database Models           |
#-------------------------------------+
# General server configuration
class ServerConfig:
    def __init__(self, _id: int, projection=None):
        collection = db["config"]
        result = collection.find_one({"_id": _id}, projection=projection)
        if result is None:
            result = {}
        
        self.id = _id
        self.mod_roles = result.get("mod_roles", [])
        self.log_channel = result.get("log_channel")
        self.verified_role = result.get("verified_role")
        self.club_roles = result.get("club_roles", {})
        self.vote_channel = result.get("vote_channel")
    # Moderator role manipulators
    def add_mod_role(self, role_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"mod_roles": role_id}},
            upsert=True
        )
    
    def remove_mod_role(self, role_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$pull": {"mod_roles": { "$in": [role_id] }}}
        )
    
    def clear_outdated_roles(self, server_roles: list):
        server_roles = [r.id for r in server_roles]
        nonexist = []
        for r in self.mod_roles:
            if r not in server_roles:
                self.mod_roles.remove(r)
                nonexist.append(r)
        if nonexist != []:
            collection = db["config"]
            collection.update_one(
                {"_id": self.id},
                {"$pull": {"mod_roles": { "$in": nonexist }}}
            )

    def clear_mod_roles(self):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"mod_roles": ""}}
        )
    # Log channel manipulators
    def set_log_channel(self, channel_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"log_channel": channel_id}},
            upsert=True
        )

    def unset_log_channel(self):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"log_channel": ""}}
        )
    # Verified role
    def set_verified_role(self, role_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"verified_role": role_id}},
            upsert=True
        )

    def unset_verified_role(self):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"verified_role": ""}}
        )
    # Club role
    def add_club_role(self, role_id: int, club_tag: str):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"club_roles.{club_tag}": role_id}},
            upsert=True
        )

    def remove_club_role(self, club_tag: str):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {f"club_roles.{club_tag}": ""}}
        )
    
    def clear_club_roles(self):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"club_roles": ""}}
        )
    # Vote channel
    def set_vote_channel(self, channel_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"vote_channel": channel_id}},
            upsert=True
        )

    def unset_vote_channel(self):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"vote_channel": ""}}
        )
    
# Brawl Stars: Discord verification
class BrawlDiscordList:
    def __init__(self):
        pass

    def load(self):
        collection = db["brawlstars_tags"]
        result = collection.find({"tag": {"$exists": True}})
        return [] if result is None else [BrawlDiscordUser(doc["_id"], doc["tag"]) for doc in result]

    def contains_tag(self, tag: str):
        collection = db["brawlstars_tags"]
        result = collection.find_one({"tag": tag})
        return False if result is None else True
    
    def contains_id(self, _id: int):
        collection = db["brawlstars_tags"]
        result = collection.find_one({"_id": _id, "tag": {"$exists": True}})
        return False if result is None else True

    def find_matches(self, list_of_ids: list):
        collection = db["brawlstars_tags"]
        result = collection.find({"_id": {"$in": list_of_ids}, "tag": {"$exists": True}})
        return [] if result is None else [BrawlDiscordUser(doc["_id"], doc["tag"]) for doc in result]
    
    def link_together(self, _id: int, tag: str):
        collection = db["brawlstars_tags"]
        collection.update_one(
            {"_id": _id},
            {"$set": {"tag": tag}},
            upsert=True
        )


class BrawlDiscordUser:
    def __init__(self, user_id: int, tag: str=None):
        self.id = user_id

        if tag is None:
            collection = db["brawlstars_tags"]
            result = collection.find_one({"_id": self.id})
            if result is None:
                result = {}
            self.tag = result.get("tag")
        else:
            self.tag = tag
    
    def __str__(self):
        return f"<BDU(id={self.id}, tag={self.tag})>"

    def link_with(self, tag: str):
        collection = db["brawlstars_tags"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"tag": tag}},
            upsert=True
        )

    def unlink(self):
        collection = db["brawlstars_tags"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"tag": ""}}
        )


class BrawlClubLoop:
    def __init__(self, bot_id: int):
        hours = 24
        self.id = bot_id
        collection = db["brawl_loop_data"]
        result = collection.find_one({"_id": self.id})
        if result is None:
            result = {}
        
        now = datetime.utcnow()
        delta = timedelta(hours=hours)
        self.checked_at = result.get("checked_at", now - delta)
        self.next_check_at = self.checked_at + delta
        if self.next_check_at <= now:
            self.time_left = timedelta(seconds=0)
        else:
            self.time_left = self.next_check_at - now

    def get_servers(self):
        collection = db["config"]
        results = collection.find(
            {"club_roles": {"$exists": True}},
            projection={"club_roles": True, "_id": True}
        )
        return [res for res in results if len(res.get("club_roles", {})) > 0]

    def update_timestamp(self):
        collection = db["brawl_loop_data"]
        collection.update_one({"_id": self.id}, {"$set": {"checked_at": datetime.utcnow()}}, upsert=True)


# Reaction Roles manipulator
class ReactionRolesConfig:
    def __init__(self, server_id: int):
        self.id = server_id
    
    def get_role(self, message_id: int, emoji: str):
        collection = db["reaction_roles"]
        result = collection.find_one(
            {"_id": self.id, f"{message_id}.{emoji}": {"$exists": True}},
            projection={str(message_id): True}
        )
        return None if result is None else result.get(f"{message_id}", {}).get(f"{emoji}")
    
    def add_role(self, message_id: int, emoji: str, role_id: int):
        collection = db["reaction_roles"]
        collection.update_one(
            {"_id": self.id, f"{message_id}.{emoji}": {"$exists": False}},
            {"$set": {f"{message_id}.{emoji}": role_id}},
            upsert=True
        )
    
    def remove_reaction(self, message_id: int, emoji: str):
        collection = db["reaction_roles"]
        collection.update_one(
            {"_id": self.id, f"{message_id}.{emoji}": {"$exists": True}},
            {"$unset": {f"{message_id}.{emoji}": ""}}
        )

    def get_roles(self, message_id: int):
        collection = db["reaction_roles"]
        result = collection.find_one(
            {"_id": self.id, f"{message_id}": {"$exists": True}},
            projection={str(message_id): True}
        )
        return {} if result is None else result.get(str(message_id), {})

# Server economy tools
class Item:
    def __init__(self, item_id: int, data: dict, server_id: int):
        self.id = item_id
        self.server_id = server_id
        self.name = data.get("name", "[Удалённый предмет]")
        self.icon_url = data.get("icon_url")
        self.price = data.get("price", 0)
        self.role = data.get("role")
        self.key_for = data.get("key_for", [])

    def set_name(self, name: str):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"items.{self.id}.name": name}},
            upsert=True
        )
        self.name = name
    
    def set_icon_url(self, url: str):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"items.{self.id}.icon_url": url}},
            upsert=True
        )
        self.icon_url = url

    def set_price(self, price: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"items.{self.id}.price": price}}
        )
        self.price = price
    
    def set_role(self, role_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"items.{self.id}.role": role_id}}
        )
        self.role = role_id
    # case manipulators
    def bind_case(self, case_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$addToSet": {f"items.{self.id}.key_for": case_id}}
        )
        self.key_for.append(case_id)
    
    def unbind_case(self, case_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$pull": {f"items.{self.id}.key_for": {"$in": [case_id]}}}
        )
        self.key_for.remove(case_id)

    def unbind_all(self):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"items.{self.id}.key_for": ""}}
        )
        self.key_for = []
    # deletion
    def delete(self):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"items.{self.id}": ""}}
        )


class Case:
    def __init__(self, server_id:int, case_id: int, loot: list, data: dict={}):
        self.server_id = server_id
        self.id = case_id
        if "loot" in data:
            data.pop("loot")
        self.name = data.get("name", "???")
        self.icon_url = data.get("icon_url")
        self.loot = sorted(loot, key=lambda p: p[1])
    
    @property
    def percentage(self):
        s = 0
        for item in self.loot:
            s += item[1]
        out = []
        for item in self.loot:
            pr = 100 * item[1] / s
            l = len(str(pr)[2:]) - len(str(pr)[2:].lstrip("0"))
            if l > 0:
                out.append(round(pr, l + 1))
            else:
                out.append(round(pr, 1))
        return out

    def search_item(self, string):
        string = string.lower()
        return [item for item, w in self.loot if string in item.name.lower()]

    def open(self, amount=1):
        try:
            p = []; w = []
            for pair in self.loot:
                p.append(pair[0])
                w.append(pair[1])
            return random.choices(population=p, weights=w, k=amount)
        except Exception:
            return None

    def set_name(self, name: str):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"cases.{self.id}.name": name}},
            upsert=True
        )

    def set_icon_url(self, url: str):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"cases.{self.id}.icon_url": url}},
            upsert=True
        )

    def add_item(self, item_id: int, weight: float):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"cases.{self.id}.loot.{item_id}": weight}}
        )
    
    def remove_item(self, item_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"cases.{self.id}.loot.{item_id}": ""}}
        )
    
    def clear(self):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"cases.{self.id}.loot": ""}}
        )

    def delete(self):
        collection = db["items"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"cases.{self.id}": ""}}
        )


class Shop:
    def __init__(self, server_id: int, items: list):
        self.id = server_id
        self.items = sorted(items, key=lambda it: it.price)
    
    def search_item(self, string: str):
        string = string.lower()
        return [item for item in self.items if string in item.name.lower()]

    def add_item(self, item_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"shop": item_id}}
        )
    
    def remove_item(self, item_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.id},
            {"$pull": {"shop": item_id}}
        )
    
    def clear(self):
        collection = db["items"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {"shop": ""}}
        )


class ItemStorage:
    def __init__(self, server_id: int, projection=None):
        self.id = server_id
        if "items" in projection:
            self.items_loaded = True
        else:
            self.items_loaded = False
        
        collection = db["items"]
        result = collection.find_one({"_id": self.id}, projection=projection)
        if result is None:
            result = {}
        
        self.cy = result.get("cy", "💰")
        self.items = [ Item(int(_id), data, self.id) for _id, data in result.get("items", {}).items() ]
        self.raw_shop = result.get("shop", [])
        self.raw_cases = result.get("cases", {})
        self._cases = None
        del result
    
    @property
    def shop(self):
        shop_items = []
        nonexist = []
        for item_id in self.raw_shop:
            item = self.get(item_id)
            if item is None:
                nonexist.append(item_id)
            else:
                shop_items.append(item)
        if self.items_loaded:
            collection = db["items"]
            collection.update_one({"_id": self.id}, {"$pull": {"$in": nonexist}})
        return Shop( self.id, shop_items )
    
    @property
    def cases(self):
        if self._cases is None:
            self._cases = []
            nonexist = []
            for cid, data in self.raw_cases.items():
                loot = []
                for _id_, weight in data.get("loot", {}).items():
                    item = self.get(int(_id_))
                    if item is None:
                        nonexist.append((f"cases.{cid}.loot.{_id_}", ""))
                    else:
                        loot.append((item, weight))
                self._cases.append( Case(self.id, int(cid), loot, data) )
            if nonexist != [] and self.items_loaded:
                collection = db["items"]
                collection.update_one({"_id": self.id}, {"$unset": dict(nonexist)})
        return self._cases

    def get(self, item_id: int, result=None):
        for item in self.items:
            if item.id == item_id:
                result = item
                break
        return result

    def get_case(self, case_id: int, result=None):
        for case in self.cases:
            if case.id == case_id:
                result = case
                break
        return result

    def search_items(self, string: str):
        string = string.lower()
        return [item for item in self.items if string in item.name.lower()]

    def search_cases(self, string: str):
        string = string.lower()
        return [case for case in self.cases if string in case.name.lower()]
    # Item creation
    def create_item(self, item_id: int, name: str, price: int=0):
        collection = db["items"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"items.{item_id}": {"name": name, "price": price}}},
            upsert=True
        )
    # Case creation
    def create_case(self, case_id: int, name: str):
        collection = db["items"]
        try:
            collection.update_one(
                {"_id": self.id},
                {"$set": {f"cases.{case_id}": {"name": name}}},
                upsert=True
            )
        except Exception:
            pass
    # Add item to shop
    def add_to_shop(self, item_id: int):
        collection = db["items"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"shop": item_id}}
        )


class Customer:
    def __init__(self, server_id: int, user_id: int, data: dict=None):
        self.server_id = server_id
        self.id = user_id

        if data is None:
            collection = db["customers"]
            result = collection.find_one(
                {"_id": self.server_id, f"{self.id}": {"$exists": True}},
                projection={f"{self.id}": True}
            )
            if result is None:
                data = {}
            else:
                data = result.get(f"{self.id}")
            del result
            
        self.balance = data.get("balance", 0)
        self.raw_items = data.get("items", [])
        self.keys = data.get("keys", [])
        self._items = None
        del data
    
    @property
    def items(self):
        if self._items is None:
            server = ItemStorage(self.server_id, {"items": True})
            self._items = []; outdated = []
            for _id_ in self.raw_items:
                item = server.get(_id_)
                if item is None:
                    outdated.append(_id_)
                else:
                    self._items.append(item)
            if outdated != []:
                self.remove_items(*outdated)
        return self._items

    def search_item(self, string):
        string = string.lower()
        out = []
        for item in self.items:
            if item not in out and string in item.name.lower():
                out.append(item)
        return out

    def pay_to(self, user_id: int, number: int):
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {"$inc": {
                f"{self.id}.balance": -number,
                f"{user_id}.balance": number
            }},
            upsert=True
        )

    def inc_bal(self, number: int):
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {"$inc": {f"{self.id}.balance": number}},
            upsert=True
        )

    def give_item(self, item: Item):
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {"$push": {f"{self.id}.items": item.id}},
            upsert=True
        )

    def remove_items(self, *item_ids: list):
        for item_id in item_ids:
            self.raw_items.remove(item_id)
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"{self.id}.items": self.raw_items}}
        )
    
    def sell_item(self, item: Item, amount=1):
        earning = 0
        while amount > 0 and item.id in self.raw_items:
            amount -= 1
            self.raw_items.remove(item.id)
            earning += item.price
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {
                "$set": {f"{self.id}.items": self.raw_items},
                "$inc": {f"{self.id}.balance": earning}
            }
        )

    def sell_all_items(self):
        earning = 0
        for item in self.items:
            earning += item.price
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {
                "$unset": {f"{self.id}.items": ""},
                "$inc": {f"{self.id}.balance": earning}
            }
        )
        return earning

    def remove_keys(self, *case_ids: int):
        for case_id in case_ids:
            self.keys.remove(case_id)
        collection = db["customers"]
        collection.update_one(
            {"_id": self.server_id},
            {"$set": {f"{self.id}.keys": self.keys}}
        )

    def open_case(self, case: Case, amount=1):
        x_keys = self.keys.count(case.id)
        inv_weight = len(self.raw_items)
        if amount > x_keys:
            amount = x_keys
        if amount + inv_weight > inv_capacity:
            amount = inv_capacity - inv_weight
        
        if amount > 0:
            items = case.open(amount)
            if items is not None:
                while amount > 0:
                    amount -= 1
                    self.keys.remove(case.id)
                collection = db["customers"]
                collection.update_one(
                    {"_id": self.server_id},
                    {
                        "$push": {f"{self.id}.items": {"$each": [it.id for it in items]}},
                        "$set": {f"{self.id}.keys": self.keys}
                    },
                    upsert=True
                )
            return items

    def buy(self, item: Item, amount=1):
        inv_weight = len(self.raw_items)
        if inv_weight + amount > inv_capacity:
            amount = inv_capacity - inv_weight
        if amount > 0:
            collection = db["customers"]
            collection.update_one(
                {"_id": self.server_id},
                {
                    "$push": {f"{self.id}.items": {"$each": amount * [item.id]}},
                    "$inc": {f"{self.id}.balance": - item.price * amount}
                },
                upsert=True
            )
            return amount

    def use_item(self, item: Item, amount=1):
        """Doesn't add any roles, returns keys earned"""
        if amount < 1:
            amount = 1
        if item.id in self.raw_items:
            new_keys = amount * item.key_for
            while amount > 0 and item.id in self.raw_items:
                amount -= 1
                self.raw_items.remove(item.id)
            
            collection = db["customers"]
            collection.update_one(
                {"_id": self.server_id},
                {
                    "$push": {f"{self.id}.keys": {"$each": new_keys}},
                    "$set": {f"{self.id}.items": self.raw_items}
                },
                upsert=True
            )
            return new_keys


class CustomerList:
    def __init__(self, server_id: int, projection=None):
        self.id = server_id

        collection = db["customers"]
        result = collection.find_one({"_id": self.id}, projection=projection)
        if result is None:
            result = {}
        else:
            try:
                result.pop("_id")
            except Exception:
                pass
        
        self.customers = [Customer(self.id, int(_id_), data ) for _id_, data in result.items()]
        del result

    def get(self, user_id: int, result=None):
        for c in self.customers:
            if c.id == user_id:
                result = c
                break
        return result

    def mass_inc_bal(self, amount: int, user_ids: list):
        collection = db["customers"]
        collection.update_one(
            {"_id": self.id},
            {"$inc": {f"{user_id}.balance": amount for user_id in user_ids}},
            upsert=True
        )

    def reset_money(self):
        """Requires customers loaded"""
        collection = db["customers"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"{c.id}.balance": 0 for c in self.customers}}
        )

    def clear_inventories(self):
        """Requires customers loaded"""
        collection = db["customers"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"{c.id}.items": [] for c in self.customers}}
        )

    def clear_keys(self):
        """Requires customers loaded"""
        collection = db["customers"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"{c.id}.keys": [] for c in self.customers}}
        )

# Custom voices
class TemporaryVoices:
    def __init__(self, server_id: int, projection=None):
        self.id = server_id
        collection = db["vc_memory"]
        result = collection.find_one(
            {"_id": self.id},
            projection=projection
        )
        if result is None:
            result = {}
        self.custom_rooms = { int(ID): rooms for ID, rooms in result.get("custom_rooms", {}).items() }
    
    def get_owner(self, room_id: int):
        """Returns (OwnerID, RoomID)"""
        for owner, rooms in self.custom_rooms.items():
            if room_id in rooms:
                return owner

    def add_custom(self, owner_id: int, room_id: int):
        collection = db["vc_memory"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {f"custom_rooms.{owner_id}": room_id}},
            upsert=True
        )
    
    def remove_custom(self, owner_id: int, room_id: int):
        collection = db["vc_memory"]
        if len(self.custom_rooms.get(owner_id, [])) == 1:
            collection.update_one(
                {"_id": self.id},
                {"$unset": {f"custom_rooms.{owner_id}": ""}}
            )
        else:
            collection.update_one(
                {"_id": self.id},
                {"$push": {f"custom_rooms.{owner_id}": room_id}}
            )

    def clear_owner(self, owner_id: int):
        collection = db["vc_memory"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {f"custom_rooms.{owner_id}": ""}}
        )


class VoiceButton:
    def __init__(self, server_id: int, button_id: int, data: dict=None):
        """data = {limit: int, name: str}"""
        self.server_id = server_id
        self.id = int(button_id)
        if data is None:
            # Getting missing data
            collection = db["vc_config"]
            result = collection.find_one(
                {"_id": self.id, f"buttons.{self.id}": {"$exists": True}},
                projection={f"buttons.{self.id}": True}
            )
            if result is None:
                data = {}
            else:
                data = result.get("buttons", {}).get(f"{self.id}", {})
            del result
        
        self.limit = data.get("limit")
        self.name = data.get("name")


class VConfig:
    def __init__(self, _id: int, projection: dict=None):
        self.id = _id
        collection = db["vc_config"]
        result = collection.find_one(
            {"_id": self.id},
            projection=projection
        )
        if result is None:
            result = {}
        self.buttons = [VoiceButton(self.id, ID, data) for ID, data in result.get("buttons", {}).items()]
        self.waiting_room_ids = result.get("waiting_room_ids", [])
        self.room_creation_channel_ids = result.get("room_creation_channel_ids", [])
        del result
    
    def get(self, _id: int):
        for vb in self.buttons:
            if vb.id == _id:
                return vb
    
    def which_creates(self, limit: int, name: str):
        for button in self.buttons:
            if button.name == name and button.limit == limit:
                return button

    def add_button(self, _id: int, limit: int, name: str):
        data = {
            "limit": limit,
            "name": name
        }
        del limit, name
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"buttons.{_id}": data}},
            upsert=True
        )
    
    def remove_button(self, _id: int):
        if self.get(_id) is not None:
            collection = db["vc_config"]
            collection.update_one(
                {"_id": self.id},
                {"$unset": {f"buttons.{_id}": ""}},
                upsert=True
            )

    def add_waiting_room(self, _id: int):
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"waiting_room_ids": _id}},
            upsert=True
        )
    
    def remove_waiting_room(self, _id: int):
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$push": {"waiting_room_ids": _id}}
        )

    def set_room_creation_channels(self, channel_ids: list):
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"room_creation_channel_ids": channel_ids}},
            upsert=True
        )

# Moderation memory
class MuteModel:
    def __init__(self, server_id: int, member_id: int, data: dict=None):
        self.server_id = server_id
        self.id = member_id
        if data is None:
            # In case no data was given
            collection = db["mutes"]
            data = collection.find_one(
                {"_id": self.server_id, f"mutes.{self.id}": {"$exists": True}},
                projection={f"mutes.{self.id}": True}
            )
            if data is None:
                data = {}
            else:
                data = data.get("mutes", {}).get(f"{self.id}")
        self.ends_at = data.get("ends_at", datetime.utcnow()) # UTC
        self.reason = data.get("reason")
        if self.reason is None: self.reason = "Не указана"
        self.mod_id = data.get("mod_id")
    @property
    def time_remaining(self):
        now = datetime.utcnow()
        return self.ends_at - now if self.ends_at > now else timedelta(seconds=0)
    
    def end(self):
        collection = db["mutes"]
        collection.update_one(
            {"_id": self.server_id},
            {"$unset": {f"mutes.{self.id}": ""}}
        )


class MuteList:
    def __init__(self, server_id: int, projection: dict=None, data: dict=None, before: datetime=None):
        self.id = server_id
        if data is None:
            collection = db["mutes"]
            data = collection.find_one(
                {"_id": self.id},
                projection=projection
            )
            if data is None: data = {}
        if before is None:
            self.__mutes = data.get("mutes", {})
        else:
            self.__mutes = []
            for _id_, d in data.get("mutes", {}).items():
                mm = MuteModel(self.id, int(_id_), d)
                if mm.ends_at <= before:
                    self.__mutes.append(mm)
    @property
    def mutes(self):
        if isinstance(self.__mutes, dict):
            self.__mutes = [MuteModel(self.id, int(_id_), dat) for _id_, dat in self.__mutes.items()]
        return self.__mutes
    
    def get(self, member_id: int):
        if len(self.__mutes) < 1:
            return None
        if isinstance(self.__mutes, dict):
            for _id_, dat in self.__mutes.items():
                if int(_id_) == member_id:
                    return MuteModel(self.id, int(_id_), dat)
        else:
            for mm in self.__mutes:
                if mm.id == member_id:
                    return mm
    
    def add(self, member_id: int, timedelta: timedelta, mod_id: int, reason: str=None):
        payload = {
            "ends_at": datetime.utcnow() + timedelta,
            "mod_id": mod_id,
            "reason": reason
        }
        collection = db["mutes"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"mutes.{member_id}": payload}},
            upsert=True
        )

    def remove(self, member_id: int):
        collection = db["mutes"]
        collection.update_one(
            {"_id": self.id},
            {"$unset": {f"mutes.{member_id}": ""}}
        )


def get_saved_mutes(before: datetime):
    collection = db["mutes"]
    results = collection.find({})
    return [MuteList(r["_id"], data=r, before=before) for r in results]

# Event points
class EventUser:
    def __init__(self, server_id: int, user_id: int, data: dict=None):
        self.server_id = server_id
        self.id = user_id
        if data is None:
            collection = db["event"]
            data = collection.find_one(
                {"_id": self.server_id},
                projection={f"users.{user_id}": True}
            )
            if data is None: data = {}
            else: data = data.get("users", {}).get(f"{user_id}", {})
        self.balance = data.get("balance", 0)
    
    def change_bal(self, num: int):
        collection = db["event"]
        collection.update_one(
            {"_id": self.server_id},
            {"$inc": {f"users.{self.id}.balance": num}},
            upsert=True
        )


class EventList:
    def __init__(self, server_id: int, projection=None):
        self.id = server_id
        collection = db["event"]
        data = collection.find_one({"_id": self.id}, projection=projection)
        if data is None: data = {}
        self.__users = data.get("users", {})
    @property
    def users(self):
        if isinstance(self.__users, dict):
            self.__users = [EventUser(self.id, int(_id_), dat) for _id_, dat in self.__users.items()]
        return self.__users
    
    def get_user(self, user_id: int):
        if isinstance(self.__users, dict):
            user_id = str(user_id)
            for _id_, dat in self.__users.items():
                if _id_ == user_id:
                    return EventUser(self.id, int(_id_), dat)
        else:
            for user in self.__users:
                if user.id == user_id: return user

    def change_bal(self, user_id: int, num: int):
        collection = db["event"]
        collection.update_one(
            {"_id": self.id},
            {"$inc": {f"users.{user_id}.balance": num}},
            upsert=True
        )

    def reset(self):
        collection = db["event"]
        collection.update_one({"_id": self.id}, {"$unset": {"users": ""}})


# he he