import asyncio
import logging

import nextcord
from nextcord import SlashOption
from nextcord.ext import commands

import botutils
import translationtools
from translationtools import hiragana_to_katakana, romaji_to_hiragana

intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

logger = logging.getLogger("shiritori-ref")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='app.log',
    filemode='a'
)
logger.addHandler(logging.StreamHandler())


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')


@bot.slash_command(
    name="duel",
    description="Challenge someone to a duel",
    guild_ids=[643165990695206920, 931645765980393624],
)
async def duel(
        inter: nextcord.Interaction,
        user: nextcord.User = SlashOption(description="The person you want to duel", required=True),
        mode: str = SlashOption(description="The mode of the duel. Default: Normal",
                                choices=["Normal", "Speed"], required=False),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Wrap your words in \" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False)
):
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, inter.user, user, mode, chat)
        return

    view = botutils.get_view(user, lambda: initiate_duel(inter, inter.user, user, mode, chat))

    await inter.response.send_message(
        f"{user.mention}, you have been challenged to a duel by {inter.user.mention}!", view=view)


async def initiate_duel(
        inter: nextcord.Interaction, challenger: nextcord.User, challenged: nextcord.User, mode, chat
):
    mode = mode or "Normal"
    chat = chat or "on"
    logger.info(f"{challenger} challenged {challenged} to a duel in {mode} mode with chat {chat}.")

    if challenged != bot.user:
        await inter.channel.send(f"{challenged.display_name}, as the challenged, you have the right of the first word.")

    streak = 0
    current = challenger if challenged == bot.user else challenged
    previous_word = ""
    played_words = set()
    lives = {challenger.id: 3, challenged.id: 3}

    while True:
        logger.info(f"Lives: {lives}")

        if current == bot.user:
            played_word = await botutils.take_bot_turn(inter, previous_word, played_words)
            if played_word:
                played_words.add(played_word)
                previous_word = played_word
                current = challenger
                continue
            else:
                return

        if lives[current.id] == 0:
            await inter.channel.send(f"{current.mention} has lost all their lives. "
                                     f"{challenger if current == challenged else challenged} wins!")
            return

        if streak != 0 and streak % 5 == 0:
            if streak % 100 == 0:
                await inter.channel.send(f"The streak is {streak}!")
                await inter.channel.send(f"https://tenor.com/view/orangutan-driving-gif-24461244")
            if streak % 50 == 0:
                await inter.channel.send(f"The streak is {streak}! :orangutan::orangutan::orangutan:")
            if streak % 25 == 0:
                await inter.channel.send(f"The streak is {streak}! :fire::fire::fire:")
            elif streak % 10 == 0:
                await inter.channel.send(f"The streak is {streak}! :fire:")
            else:
                await inter.channel.send(f"The streak is {streak}!")

        await inter.channel.send(f"{current.display_name}, your move!"
                                 f" You have {15 if mode == 'Speed' else 60} seconds to respond.")
        try:
            def check(msg: nextcord.Message):
                return (msg.author.id == current.id and msg.channel == inter.channel and
                        (chat != "on" or msg.content[0:2] == "> "))

            response: nextcord.Message = await bot.wait_for(
                'message', timeout=15.0 if mode == "Speed" else 60.0, check=check)
        except asyncio.TimeoutError:
            await inter.channel.send(f"{current.mention} took too long to respond. You lose!")
            return

        hiragana = romaji_to_hiragana(response.content.strip("\""))

        logger.info(f"{current.display_name} played {hiragana}")

        if not hiragana:
            lives[current.id] -= 1
            await inter.channel.send(f"{response.content.strip("\"")} is not a valid Romaji word."
                                     f" You have {lives[current.id]} lives remaining.")
            continue

        if hiragana in played_words:
            lives[current.id] -= 1
            await inter.channel.send(f"{hiragana} has already been played."
                                     f" You have {lives[current.id]} lives remaining.")
            continue

        if previous_word and hiragana[0] != previous_word[-1]:
            if (previous_word[-1] == 'ぢ' and hiragana[0] == 'じ') or \
                    (previous_word[-1] == 'づ' and hiragana[0] == 'ず'):
                pass
            if previous_word[-1] == 'ゃ' or previous_word[-1] == 'ゅ' or previous_word[-1] == 'ょ':
                if previous_word[-2] == hiragana[0]:
                    pass
            lives[current.id] -= 1
            await inter.channel.send(f"{hiragana} does not start with {previous_word[-1]}!"
                                     f" You have {lives[current.id]} lives remaining.")
            continue

        if hiragana[-1] == 'ん':
            lives[current.id] -= 1
            await inter.channel.send(f"{hiragana} ends with ん!"
                                     f" You have {lives[current.id]} lives remaining.")
            continue

        async def on_fail():
            lives[current.id] -= 1
            await inter.channel.send(f"{hiragana} is not a valid word."
                                     f" You have {lives[current.id]} lives remaining.")

        words = await translationtools.get_dictionary(hiragana, previous_word, played_words)
        katakana = hiragana_to_katakana(hiragana)

        if hiragana not in words and katakana not in words:
            await on_fail()
            continue

        if hiragana in words:
            matches = words[hiragana]
        else:
            matches = words[katakana]

        for i in range(3):
            if i >= len(matches):
                break
            match = matches[i]
            kanji = match['word'] or katakana
            await inter.channel.send(f"{kanji} ({hiragana}):\n> {', '.join(match['meanings'])}")

        played_words.add(hiragana)
        previous_word = hiragana
        streak += 1
        current = challenger if current == challenged else challenged


if __name__ == '__main__':
    bot.run("")
