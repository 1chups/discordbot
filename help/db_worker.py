from pymongo import MongoClient
import os

app_string = str(os.environ.get('cluster_string'))
cluster = MongoClient(app_string)