from os import environ as e


e["cluster_string"] = open("secret/cluster_string.txt", "r").read()
e["bot_token"] = open("secret/token.txt", "r").read()



import cogs_axis