
import os
import re
from typing import Literal

import autogen
import nltk
import requests
import telebot
from autogen.agentchat.contrib.multimodal_conversable_agent import \
    MultimodalConversableAgent
from bs4 import BeautifulSoup as Soup
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field
from telebot import types
from typing_extensions import Annotated


def FindUrl(string):
 
    # findall() has been used
    # with valid conditions for urls in string
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, string)
    return [x[0] for x in url]

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")

mydb = myclient["Glow"]
mycol = mydb["chats"]



config_list = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
    filter_dict={
        "model": ["Maguida"],
    },
)

llm_config = {
    "config_list": config_list,
    "timeout": 120,
    "cache_seed":None
}

chatbot = MultimodalConversableAgent(
    name="Glow",
    system_message="""You're an expert assistant dermatologist in cameroun.
Objectives: Thanks to you, users will be able to determine their skin type, solve certain small skin problems, for more complicated problems, ask to see a specialist, you will be able to suggest certain make-up or skin care products that will go well with them, recommend skins care routines and tell them how to keep their skin healthy.

How it works: You'll need to ask the user questions to help you solve their problem more effectively, and use the functions provided to help you achieve your goal.

Characteristic: You will have to be very nice to the user, helpful and happy to chat with him. You will discuss with him on a language.
""",
    llm_config=llm_config,
    
)

# create a UserProxyAgent instance named "user_proxy"
user_proxy = autogen.UserProxyAgent(
    name="user",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=20,
    code_execution_config = {"use_docker":False}
)

@user_proxy.register_for_execution()
@chatbot.register_for_llm(description="Search product in Cameroon")
def search_product(
        keyword: Annotated[str, "Keyword to search the product in Cameroon"],
    ) -> str:
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(f"{keyword} price Cameroun", max_results=5)]
    return str(results)


@user_proxy.register_for_execution()
@chatbot.register_for_llm(description="search for product characteristics")
def search_carac(
        url: Annotated[str, "the url of the product website"],
    )->str:
    html = requests.get(url)
    raw = Soup(html.content, "html.parser").get_text()
    return raw

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    response = chatbot.generate_reply(messages=[{"role":"user","content":"Salut"}],sender=user_proxy)
    bot.reply_to(message, response,parse_mode="Markdown")
    people = list(mycol.find({"uuid":message.from_user.id},{}))
    if len(people) ==0 :
        mycol.insert_one({"uuid":message.from_user.id,"messages":[{"role":"user","content":"Salut"},{"role":"assistant","content":response}]})
    else :
        messages = people[0]["messages"]
        messages.append({"role":"user","content":"Salut"})
        messages.append({"role":"assistant","content":response})
        myquery = { "uuid":message.from_user.id }
        newvalues = { "$set": { "messages": messages } }
        mycol.update_one(myquery, newvalues)
@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    
    people =list(mycol.find({"uuid":message.from_user.id},{}).limit(10))
    if len(people) ==0 :
        messages=[]
        mycol.insert_one({"uuid":message.from_user.id,"messages":messages})
    else :
        messages = people[0]["messages"]
    txt = ""
    if message.photo:
        for i in message.photo:
            txt += f"<img {bot.get_file(i.file_id).file_path}> \n"
    txt += message.text
    messages.append({"role":"user","content":txt})
    msg = messages.copy()
    print(messages)
    response = chatbot.generate_reply(messages=messages,sender=user_proxy)
    while str(type(response))!="<class 'str'>":

        print(response)
        del response["function_call"]
        messages.append(response)
        response = user_proxy.generate_reply(messages=messages,sender=chatbot)
        print(response)
        messages.append(response)
        response = chatbot.generate_reply(messages=messages,sender=user_proxy)
    print(response)

    print(message.from_user)
    response.replace("**","\\*")
    # response = re.sub(r'[_*[\]()~>#\+\-=|{}.!]', lambda x: '\\' + x.group(), response)
    response = response.split("\n\n")


    for i in response:
        urls = FindUrl(i)
        if len(urls)!=0:
            button_foo = types.InlineKeyboardButton('Passer la Commande', callback_data='commande', url=urls[0])
            button_bar = types.InlineKeyboardButton('Visiter le site', callback_data='visiter',url=urls[0])

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(button_foo)
            keyboard.add(button_bar)
            bot.reply_to(message, i,parse_mode="Markdown",reply_markup=keyboard)
        else:
            bot.reply_to(message, i,parse_mode="Markdown")

    response = '\n\n'.join(response)
    msg.append({"role":"assistant","content":response})
    myquery = { "uuid":message.from_user.id }
    newvalues = { "$set": { "messages": msg } }
    mycol.update_one(myquery, newvalues)
    
bot.infinity_polling()

# user_proxy.initiate_chat(chatbot,message="Je veux un iphone 15")