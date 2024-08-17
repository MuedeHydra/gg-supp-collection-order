#!/bin/python3

import csv
import datetime
import os
import discord
from discord import app_commands
import asyncio

# init discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

config: dict = {}


def read_conf() -> dict:
    """read the config file and load the data"""
    config: dict = {}
    with open("gg-supp.conf", "r", encoding="utf-8") as conf:
        for i in conf:
            if i.startswith("#"):
                continue
            if i == "\n":
                continue
            i = i.split("=")
            # detect bool
            if i[1].strip() == "True":
                config.update({i[0].strip(): True})
            elif i[1].strip() == "False":
                config.update({i[0].strip(): False})
            else:
                try:
                    config.update({i[0].strip(): int(i[1].strip())})
                except ValueError:
                    config.update({i[0].strip(): i[1].strip()})

        return config


def sort_list(li: list) -> [list, str]:
    """format the input for csv"""
    di: dict = {"user": li[0], "amount": 1, "price": 36, "url": None}
    li_new: list = []
    operator = "add"

    for i in li[1:]:
        if "--" in i:
            if config["thirdparty_add"]:
                di["user"] = i[2:]
            else:
                return None, "thirdparty_add-False"

        elif i.endswith("x"):
            di["amount"] = int(i.removesuffix("x"))
        elif "CHF" in i:
            di["price"] = int(i.removesuffix("CHF"))
        elif "https://gamersupps.gg/products/" in i:
            di["url"] = i
        elif "remove" in i:
            operator = "remove"

    # convert to list
    for i in di.values():
        li_new.append(i)

    return li_new, operator


def csv_add(line: list, csv_filename: str = "open.csv") -> None:
    """add at the end a new line"""
    with open(csv_filename, 'a', newline="") as csvfile:
        cvswriter = csv.writer(csvfile)
        cvswriter.writerows([line])


def csv_list(csv_filename: str = "open.csv") -> list:
    """read the csv file and return a list"""
    with open(csv_filename, 'r', newline="") as csvfile:
        # reader = csv.DictReader(csvfile)
        reader = csv.reader(csvfile)

        li = []
        for row in reader:
            li.append(row)
        li.sort()
        return (li)


def csv_remove(li_old: list, csv_filename: str = "open.csv") -> None:
    """remove an item and overwrite the csv"""
    li = csv_list()
    li_new = []

    for i in li:
        if str(i[0]) == str(li_old[0]) and i[3] == li_old[3]:
            print("item removed")
        else:
            li_new.append(i)

    with open(csv_filename, 'w', newline="") as csvfile:
        cvswriter = csv.writer(csvfile)
        cvswriter.writerows(li_new)


def new_action(li: list) -> str:
    """handels the procces"""
    li_new, operator = sort_list(li)
    print(li_new)
    print(operator)

    # read list
    list_open = csv_list()
    if operator == "remove":
        csv_remove(li_new)
    elif operator == "add":
        # check if it allready exsists
        for i in list_open:
            if str(i[0]) == str(li_new[0]) and i[3] == li_new[3]:
                csv_remove(li_new)
                li_new[1] += int(i[1])
        csv_add(li_new)
    elif operator == "thirdparty_add-False":
        return "thirdparty_add are not enabled"


def update_list(titel: str, file_name: str = "open.csv"):
    """reads the file and upload it to channel_id_list"""
    li: list = csv_list(file_name)
    # check if list is empthy
    if len(li) == 0:
        return ("# Keine Bestellung offen")

    s: str = ""
    user_old = ""
    cost: int = 0

    s += titel + "\n"
    s += f"<@{li[0][0]}>\n"
    user_old = li[0][0]

    for i in li:
        if i[0] != user_old:
            s += "-"*10 + "\n"
            s += f"{cost}CHF\n"
            s += "="*10 + "\n"
            s += "\n"
            s += f"<@{i[0]}>\n"
            user_old = i[0]
            cost = 0
        s += f"- {i[1]}x {i[2]}CHF <{i[3]}>\n"
        cost += int(i[1]) * int(i[2])

    s += "-"*10 + "\n"
    s += f"{cost}CHF\n"
    s += "="*10 + "\n"

    return s


def get_time() -> str:
    """get and format time"""
    t = datetime.datetime.now()
    return (t.strftime("%Y-%m-%d_%H:%M:%S"))


def bestellung() -> None:
    """move csv to archiv and create new file"""
    date_time = get_time()
    os.system(f"mkdir -p archiv && mv open.csv archiv/{date_time}.csv")
    os.system("touch open.csv")


async def delet(channel_id: int, limit: int = 5) -> None:
    """delet the last msg from chanel"""
    channel = client.get_channel(channel_id)
    async for message in channel.history(limit=limit):
        await message.delete()
        await asyncio.sleep(1)


async def update_list_dc():
    """update the list from csv"""
    if config["autodelet_list"]:
        await delet(config["channel_id_list"])
    channel = client.get_channel(config["channel_id_list"])
    await channel.send(update_list("# Offene bestellung"))


async def ordered() -> None:
    """update the order and the archive"""
    channel = client.get_channel(config["channel_id_archiv"])
    name: str = (get_time().split("_"))[0]
    await channel.send(update_list(f"# Bestellt am {name}"))
    bestellung()
    # update open list
    await update_list_dc()


def slash() -> None:
    @tree.command(
        name="list",
        description="update the open order",
        guild=discord.Object(id=config["guild_id"])
    )
    async def first_command(interaction):

        await update_list_dc()
        await interaction.response.send_message(":thumbsup:")

    @tree.command(
        name="bestellt",
        description=("add the open order to the arcive"
                     "and update the open order with a blank list"),
        guild=discord.Object(id=config["guild_id"])
    )
    async def second_command(interaction):

        await ordered()
        await interaction.response.send_message(":thumbsup:")

    @tree.command(
        name="rebuild_archiv",
        description=(f"delet the last 100 msg from"
                     f"#{config["channel_id_archiv"]} and reuplod them"),
        guild=discord.Object(id=config["guild_id"])
    )
    async def rebuild_archiv(interaction):

        await interaction.response.send_message(":thumbsup:")
        await delet(config["channel_id_archiv"], 100)
        old_orders = os.listdir("archiv")
        old_orders.sort()
        channel = client.get_channel(config["channel_id_archiv"])
        for i in old_orders:
            title = (i.split("_"))[0]
            await channel.send(update_list(f"# Bestellt am {title}",
                                           f"archiv/{i}"))

    # @tree.command(guild=discord.Object(id=config["guild_id"]))
    # async def deletemsg(interaction: discord.Interaction,
    #                     number: int, chanel: str = None):
    #     if chanel is None:
    #         chanel = interaction.channel.id
    #     await interaction.response.send_message(":thumbsup:")
    #     await delet(int(chanel), number)
    #     # await interaction.response.send_message(f'{number=} {chanel=}',
    #     #                                         ephemeral=True)


@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=config["guild_id"]))
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message):
    global config

    if message.author == client.user:
        return

    if message.channel.id != config["channel_id_comand"]:
        return

    if message.content.startswith('!bestellt'):
        await ordered()

    elif message.content.startswith('!list'):
        await update_list_dc()

    else:
        li = [message.author.id]
        li.extend(f"{message.content}".split())
        print(li)
        msg: str = new_action(li)

        if msg is None:
            await update_list_dc()
        else:
            await message.channel.send(msg)

        if config["autodelet_command"]:
            await delet(config["channel_id_comand"])


def main() -> None:
    global config
    config = read_conf()
    slash()
    client.run(config["key"])


if __name__ == '__main__':
    main()
