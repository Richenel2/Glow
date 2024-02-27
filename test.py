import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")

mydb = myclient["kmerphone"]
mycol = mydb["chats"]
mycol.drop()