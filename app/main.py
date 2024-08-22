import asyncio
import os
import logging
from jisho_api.word import Word
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption, ButtonStyle
from nextcord.ui import Button, View

from app.translationtools import hiragana_to_katakana, romaji_to_hiragana

intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

logger = logging.getLogger()


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
    logger.info(f"{inter.user} challenged {user} to a duel in {mode} mode with chat {chat}.")
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, inter.user, user, mode, chat)
        return

    accept_button = Button(label="Accept", style=ButtonStyle.green)
    decline_button = Button(label="Decline", style=ButtonStyle.red)

    view = View()
    view.add_item(accept_button)
    view.add_item(decline_button)

    async def accept_callback(interaction: Interaction):
        if interaction.user != user:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{user.display_name} has accepted the duel!", view=None)
        await initiate_duel(inter, inter.user, user, mode, chat)

    # Callback function for declining the duel
    async def decline_callback(interaction: Interaction):
        if interaction.user != user:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{user.display_name} has declined the duel.", view=None)
        await initiate_duel(inter, inter.user, user, mode, chat)

    accept_button.callback = accept_callback
    decline_button.callback = decline_callback

    await inter.response.send_message(
        f"{user.mention}, you have been challenged to a duel by {inter.user.mention}!", view=view)


async def initiate_duel(
        inter: nextcord.Interaction, challenger: nextcord.User, challenged: nextcord.User, mode="Normal", chat="on"
):
    if challenged != bot.user:
        await inter.channel.send(f"{challenged.display_name}, as the challenged, you have the right of the first word.")

    streak = 0
    current = challenger if challenged == bot.user else challenged
    previous_word = ""
    played_words = set()
    lives = {challenger: 3, challenged: 3}

    while True:
        if current == bot.user:
            await inter.channel.send(f"My turn!")
            wr = Word.request(str(previous_word[-1]))
            if not wr:
                await inter.channel.send(f"I have no words starting with {previous_word[-1]}. I lose!")
                return
            words = {}
            for x in wr.dict()['data']:
                for y in x['japanese']:
                    reading = y['reading']
                    if reading[0] != previous_word[-1] or reading[-1] == 'ん' or reading in played_words:
                        continue
                    if len(reading) == 1:
                        continue
                    word_info = {'word': y['word'],
                                 'meanings': [sense['english_definitions'][0] for sense in x['senses']]}

                    if reading in words:
                        words[reading].append(word_info)
                    else:
                        words[reading] = [word_info]

            if not words:
                await inter.channel.send(f"I have no words starting with {previous_word[-1]}. I lose!")
                return
            word = list(words.keys())[0]
            for i in range(3):
                if i >= len(words[word]):
                    break
                match = words[word][i]
                await inter.channel.send(f"{match['word']} ({word}):\n> {', '.join(match['meanings'])}")
            played_words.add(word)
            previous_word = word
            current = challenger
            continue

        if lives[current] == 0:
            await inter.channel.send(f"{current.mention} has lost all their lives. {challenger.mention} wins!")
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
                # return msg.author.id == 349456234878861313 and msg.channel == inter.channel
                return (msg.author.id == current.id and msg.channel == inter.channel and
                        (chat != "on" or msg.content[0] == "\"" and msg.content[-1] == "\""))

            response: nextcord.Message = await bot.wait_for(
                'message', timeout=15.0 if mode == "Speed" else 60.0, check=check)
        except asyncio.TimeoutError:
            await inter.channel.send(f"{current.mention} took too long to respond. You lose!")
            return

        hiragana = romaji_to_hiragana(response.content.strip("\""))

        logger.info(current.display_name, hiragana)

        if not hiragana:
            lives[current] -= 1
            await inter.channel.send(f"{response.content.strip("\"")} is not a valid Romaji word."
                                     f" You have {lives[current]} lives remaining.")
            continue

        if hiragana in played_words:
            lives[current] -= 1
            await inter.channel.send(f"{hiragana} has already been played."
                                     f" You have {lives[current]} lives remaining.")
            continue

        if previous_word and hiragana[0] != previous_word[-1]:
            if (previous_word[-1] == 'ぢ' and hiragana[0] == 'じ') or \
                    (previous_word[-1] == 'づ' and hiragana[0] == 'ず'):
                pass
            if previous_word[-1] == 'ゃ' or previous_word[-1] == 'ゅ' or previous_word[-1] == 'ょ':
                if previous_word[-2] == hiragana[0]:
                    pass
            lives[current] -= 1
            await inter.channel.send(f"{hiragana} does not start with {previous_word[-1]}!"
                                     f" You have {lives[current]} lives remaining.")
            continue

        if hiragana[-1] == 'ん':
            lives[current] -= 1
            await inter.channel.send(f"{hiragana} ends with ん!"
                                     f" You have {lives[current]} lives remaining.")
            continue

        wr = Word.request(response.content.strip("\""))
        if not wr:
            lives[current] -= 1
            await inter.channel.send(f"{hiragana} is not a valid word."
                                     f" You have {lives[current]} lives remaining.")
            continue

        words = {}
        for x in wr.dict()['data']:
            for y in x['japanese']:
                reading = y['reading']
                word_info = {'word': y['word'], 'meanings': [sense['english_definitions'][0] for sense in x['senses']]}

                if reading in words:
                    words[reading].append(word_info)
                else:
                    words[reading] = [word_info]

        katakana = hiragana_to_katakana(hiragana)

        if hiragana not in words and katakana not in words:
            lives[current] -= 1
            await inter.channel.send(f"{hiragana} is not a valid word."
                                     f" You have {lives[current]} lives remaining.")
            continue

        if hiragana in words:
            matches = words[hiragana]
        else:
            matches = words[katakana]

        for i in range(3):
            if i >= len(matches):
                break
            match = matches[i]
            await inter.channel.send(f"{match['word']} ({hiragana}):\n> {', '.join(match['meanings'])}")

        played_words.add(hiragana)
        previous_word = hiragana
        streak += 1
        current = challenger if current == challenged else challenged


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
